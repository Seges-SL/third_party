# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Pure helpers for the relaxaicode sandbox (literals, result call, pins)."""
from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional, Tuple


_MAX_MODULE_LITERAL_ELTS = 8


def _literal_collection_size(node: ast.AST) -> int:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return len(node.elts)
    if isinstance(node, ast.Dict):
        return len(node.keys)
    return 0


def _try_eval_data_node(node: ast.AST):
    """Best-effort value from an AST data node (literals + round/arithmetic).

    Invariant: recover pasted datasets without executing arbitrary code — only
    constants and a tiny fold of ``round`` / numeric BinOp.
    """
    try:
        return ast.literal_eval(node)
    except Exception:
        pass
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _try_eval_data_node(node.operand)
        if isinstance(v, (int, float)):
            return v if isinstance(node.op, ast.UAdd) else -v
        return None
    if isinstance(node, ast.BinOp) and isinstance(
        node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod),
    ):
        left = _try_eval_data_node(node.left)
        right = _try_eval_data_node(node.right)
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            return None
        try:
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.FloorDiv):
                return left // right
            if isinstance(node.op, ast.Mod):
                return left % right
        except Exception:
            return None
        return None
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == 'round'
        and not node.keywords
    ):
        args = [_try_eval_data_node(a) for a in node.args]
        if args and all(a is not None for a in args):
            try:
                return round(*args)
            except Exception:
                return None
        return None
    if isinstance(node, (ast.List, ast.Tuple)):
        out = []
        for elt in node.elts:
            v = _try_eval_data_node(elt)
            if v is None and not isinstance(elt, ast.Constant):
                # Allow None constants only; failed fold → abort.
                try:
                    if ast.literal_eval(elt) is None:
                        out.append(None)
                        continue
                except Exception:
                    return None
                return None
            out.append(v)
        return out if isinstance(node, ast.List) else tuple(out)
    if isinstance(node, ast.Dict):
        out = {}
        for k_node, v_node in zip(node.keys, node.values):
            if k_node is None:
                return None
            k = _try_eval_data_node(k_node)
            v = _try_eval_data_node(v_node)
            if k is None and not isinstance(k_node, ast.Constant):
                return None
            if v is None and not isinstance(v_node, ast.Constant):
                try:
                    if ast.literal_eval(v_node) is None:
                        out[k] = None
                        continue
                except Exception:
                    return None
                return None
            out[k] = v
        return out
    return None


def module_level_data_literal_error(code: str) -> Optional[str]:
    """Refuse scripts that paste live datasets as module-level literals.

    Invariant: never paste snapshot rows. Module-level
    ``rows = [{…}, …]`` blows up the ReAct loop.
    """
    try:
        tree = ast.parse(code or '')
    except SyntaxError:
        return None
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value if isinstance(node, ast.AnnAssign) else node.value
        size = _literal_collection_size(value)
        if size > _MAX_MODULE_LITERAL_ELTS:
            return (
                "relaxaicode must not hardcode a large dataset as a module-level "
                "literal (%s elements). Query/fetch live data inside the named "
                "def (or accept rows as a parameter from a prior tool result via "
                "previous_result/raw_data). Do not paste API/table snapshots into "
                "the script."
            ) % size
    return None


def strip_module_level_data_literals(
    code: str,
) -> Tuple[str, List[str], Dict[str, Any]]:
    """Drop large module-level list/dict assigns.

    Returns ``(cleaned_code, names, extracted)`` where *extracted* maps each
    stripped name to its recovered Python value when the AST can be folded
    (so callers can rebind without an empty ``previous_result``).
    """
    try:
        tree = ast.parse(code or '')
    except SyntaxError:
        return code or '', [], {}
    stripped: List[str] = []
    extracted: Dict[str, Any] = {}
    keep: List[ast.stmt] = []
    for node in tree.body:
        value = None
        targets: List[ast.expr] = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value = node.value
            targets = [node.target]
        if value is not None and _literal_collection_size(value) > _MAX_MODULE_LITERAL_ELTS:
            recovered = _try_eval_data_node(value)
            for t in targets:
                if isinstance(t, ast.Name) and t.id not in stripped:
                    stripped.append(t.id)
                    if recovered is not None:
                        extracted[t.id] = recovered
            continue
        keep.append(node)
    if not stripped:
        return code or '', [], {}
    new_mod = ast.Module(body=keep, type_ignores=[])
    try:
        ast.fix_missing_locations(new_mod)
        cleaned = ast.unparse(new_mod)
    except Exception:
        return code or '', [], {}
    return cleaned, stripped, extracted


def bind_stripped_names_from_prior(
    names: List[str],
    extracted: Optional[Dict[str, Any]] = None,
) -> str:
    """Python preamble: bind stripped names from recovered values or prior data."""
    import json as _json
    lines = []
    extracted = extracted or {}
    for name in names or []:
        n = (name or '').strip()
        if not n or not n.isidentifier():
            continue
        if n in extracted:
            payload = _json.dumps(extracted[n], ensure_ascii=False, default=str)
            lines.append('%s = json.loads(%s)' % (n, repr(payload)))
            continue
        lines.append(
            "%s = (previous_result.get('data') if isinstance(previous_result, dict) "
            "else None) or raw_data or []" % n
        )
    return '\n'.join(lines)


_DATE_PARAM_HINTS = (
    'date', 'day', 'fecha', 'when', 'on_date', 'as_of', 'target_date',
    'work_date', 'dia',
)

_DATE_FROM_NAMES = frozenset({
    'start', 'start_date', 'date_from', 'desde', 'inicio', 'begin',
})
_DATE_TO_NAMES = frozenset({
    'end', 'end_date', 'date_to', 'hasta', 'fin', 'until',
})


def _is_date_param(pname: str) -> bool:
    pl = (pname or '').casefold()
    return any(h == pl or h in pl for h in _DATE_PARAM_HINTS)


def _date_range_role(pname: str) -> str:
    """'from' | 'to' | 'single' — structural, no business names."""
    pl = (pname or '').casefold()
    if pl.endswith('_from') or pl.endswith('_start') or pl in _DATE_FROM_NAMES:
        return 'from'
    if pl.endswith('_to') or pl.endswith('_end') or pl in _DATE_TO_NAMES:
        return 'to'
    return 'single'


def _date_call_expr(pname: str, required: bool) -> Optional[str]:
    """Expression for a date-like param, or None to omit it.

    Never invent a period (no timedelta, no "last month"). Optional range
    args stay omitted so the def computes the range. Required from/to also
    stay omitted — the call site or the def must supply them. A required
    single date may use ``str(today)`` (sandbox preload, not a range).
    Filling both ends with ``str(today)`` collapsed ranges to one day
    (production 909E).
    """
    if not required:
        return None
    if _date_range_role(pname) in ('from', 'to'):
        return None
    return 'str(today)'


def _module_assigns_result(tree: ast.AST) -> bool:
    for node in getattr(tree, 'body', []) or []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == 'result':
                    return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == 'result':
                return True
    return False


def _call_is_named(node: Optional[ast.AST], name: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    )


def _function_body_without_docstring(node: ast.FunctionDef) -> List[ast.stmt]:
    body = list(node.body or [])
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(getattr(body[0], 'value', None), (ast.Constant, ast.Str))
    ):
        return body[1:]
    return body


def is_direct_self_recursive_def(node: ast.AST) -> bool:
    """True when a FunctionDef body only calls itself (infinite recursion).

    Structural anti-pattern: a real ``def`` shadowed by
    ``def f(...): return f(...)`` to change defaults.
    """
    if not isinstance(node, ast.FunctionDef):
        return False
    name = node.name
    body = _function_body_without_docstring(node)
    if not body:
        return False
    if len(body) == 1:
        stmt = body[0]
        if isinstance(stmt, ast.Return) and _call_is_named(stmt.value, name):
            return True
        if isinstance(stmt, ast.Expr) and _call_is_named(stmt.value, name):
            return True
        return False
    if len(body) == 2:
        first, second = body
        if not (
            isinstance(first, ast.Assign)
            and len(first.targets) == 1
            and isinstance(first.targets[0], ast.Name)
            and _call_is_named(first.value, name)
        ):
            return False
        assigned = first.targets[0].id
        if not isinstance(second, ast.Return):
            return False
        if second.value is None:
            return True
        if isinstance(second.value, ast.Name) and second.value.id == assigned:
            return True
        if _call_is_named(second.value, name):
            return True
    return False


def strip_self_recursive_shadow_defs(code: str) -> Tuple[str, List[str]]:
    """Drop module-level self-call wrappers that shadow an earlier real def.

    Keeps the first non-recursive ``def name`` and removes later
    ``def name(...): return name(...)`` shadows. Sole self-recursive defs
    (no prior body) are left for ``self_recursive_def_error``.
    """
    try:
        tree = ast.parse(code or '')
    except SyntaxError:
        return code or '', []
    seen_real: set = set()
    keep: List[ast.stmt] = []
    stripped: List[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            if is_direct_self_recursive_def(node) and node.name in seen_real:
                stripped.append(node.name)
                continue
            if not is_direct_self_recursive_def(node):
                seen_real.add(node.name)
        keep.append(node)
    if not stripped:
        return code or '', []
    new_mod = ast.Module(body=keep, type_ignores=[])
    try:
        ast.fix_missing_locations(new_mod)
        cleaned = ast.unparse(new_mod)
    except Exception:
        return code or '', []
    if not cleaned.endswith('\n'):
        cleaned += '\n'
    return cleaned, stripped


def self_recursive_def_error(code: str) -> Optional[str]:
    """Reject a sole self-recursive root def (no prior real body to keep)."""
    try:
        tree = ast.parse(code or '')
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and is_direct_self_recursive_def(node):
            return (
                "Function %r only calls itself (infinite recursion). "
                "Do not redefine a function to wrap itself. Call the existing "
                "def with new arguments: result = %s(...). "
                "If you need different defaults, pass them at the call site "
                "or rewrite the body once."
            ) % (node.name, node.name)
    return None


def ensure_module_result_call(code: str) -> Tuple[str, bool]:
    """Append ``result = root_def(...)`` when the script is only a named def.

    Invariant: the script must assign ``result`` at module level. LLMs
    often paste a complete ``def`` with ``return`` and forget the call — recover
    structurally from the signature + module-level names (strip binders).
    Do not invent a date period: omit optional from/to; skip the auto-call
    if from/to are required and unbound.
    """
    try:
        tree = ast.parse(code or '')
    except SyntaxError:
        return code or '', False
    if _module_assigns_result(tree):
        return code or '', False
    funcs = [
        n for n in tree.body
        if isinstance(n, ast.FunctionDef)
    ]
    if not funcs:
        return code or '', False
    func = None
    for f in reversed(funcs):
        if (ast.get_docstring(f) or '').strip():
            func = f
            break
    if func is None:
        func = funcs[-1]

    module_names: List[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id not in module_names:
                    module_names.append(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id not in module_names:
                module_names.append(node.target.id)

    posonly = list(getattr(func.args, 'posonlyargs', None) or [])
    all_args = posonly + list(func.args.args or [])
    defaults = list(func.args.defaults or [])
    n_required = len(all_args) - len(defaults)
    used = set()
    call_args: List[str] = []
    missing_required_range = False

    for i, arg in enumerate(all_args):
        pname = arg.arg
        required = i < n_required
        if pname in module_names:
            call_args.append(pname)
            used.add(pname)
            continue
        if _is_date_param(pname):
            expr = _date_call_expr(pname, required)
            if expr is not None:
                call_args.append(expr)
            elif required and _date_range_role(pname) in ('from', 'to'):
                missing_required_range = True
            continue
        leftover = [n for n in module_names if n not in used and n != 'result']
        if leftover:
            pick = leftover[0]
            call_args.append(pick)
            used.add(pick)
            continue
        if required:
            call_args.append(
                "(previous_result.get('data') if isinstance(previous_result, dict) "
                "else None) or raw_data or []"
            )
            continue
        break

    if missing_required_range:
        return code or '', False

    call = 'result = %s(%s)' % (func.name, ', '.join(call_args))
    out = (code or '').rstrip() + '\n\n' + call + '\n'
    return out, True


def _root_cacheable_def(tree: ast.AST) -> Optional[ast.FunctionDef]:
    funcs = [
        n for n in getattr(tree, 'body', []) or []
        if isinstance(n, ast.FunctionDef)
    ]
    if not funcs:
        return None
    for f in reversed(funcs):
        if (ast.get_docstring(f) or '').strip():
            return f
    return funcs[-1]


def _date_args_of_def(func: ast.FunctionDef) -> List[str]:
    posonly = list(getattr(func.args, 'posonlyargs', None) or [])
    all_args = posonly + list(func.args.args or [])
    return [a.arg for a in all_args if _is_date_param(a.arg)]


def ensure_date_param_coercion(code: str) -> Tuple[str, bool]:
    """Coerce ISO date strings on date-like args so ``.isoformat()`` is safe.

    Calls often pass ``str(today)``. Bodies that then do
    ``date_from.isoformat()`` crash with AttributeError on str (909E).
    """
    src = code or ''
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src, False
    func = _root_cacheable_def(tree)
    if func is None:
        return src, False
    names = _date_args_of_def(func)
    if not names:
        return src, False
    body = list(func.body or [])
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(getattr(body[0], 'value', None), (ast.Constant, ast.Str))
    ):
        first_real = body[1] if len(body) > 1 else None
    else:
        first_real = body[0] if body else None
    if first_real is None:
        return src, False
    already = ast.get_source_segment(src, func) or src
    pending = [
        n for n in names
        if ('fromisoformat(%s[:10])' % n) not in already
        and ('fromisoformat(%s[' % n) not in already
    ]
    if not pending:
        return src, False
    indent = ' ' * (first_real.col_offset or 4)
    chunks = []
    for n in pending:
        chunks.append(
            '%sif isinstance(%s, str) and %s:\n'
            '%s    try:\n'
            '%s        %s = date.fromisoformat(%s[:10])\n'
            '%s    except ValueError:\n'
            '%s        pass\n'
            % (indent, n, n, indent, indent, n, n, indent, indent)
        )
    lines = src.splitlines(True)
    insert_at = first_real.lineno - 1
    if insert_at < 0 or insert_at > len(lines):
        return src, False
    lines[insert_at:insert_at] = chunks
    return ''.join(lines), True


def inject_map_pins_origin_from_distance(code: str):
    """No-op: ``distance()`` is not a route request.

    Invariant: a pin map stays pins-only unless the script already passed
    ``origin=`` / ``routes=``. Kept as a stable pre-exec hook.
    Returns ``(code, changed)``.
    """
    return code or '', False
