# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Safe lambdas and sort keys: what the AST accepts and how an unsafe key is rewritten."""

import ast
import copy
import logging

from .validators_base import (
    ast_literal,
    format_ast_error,
)

_logger = logging.getLogger(__name__)


_SAFE_LAMBDA_CALL_NAMES = frozenset({
    'str', 'int', 'float', 'len', 'bool', 'abs', 'sum', 'max', 'min', 'round',
    'isinstance',
    # Empty buckets: defaultdict(lambda: defaultdict(lambda: {...})).
    # Constructors only. A lambda that calls env/open still fails.
    'dict', 'list', 'set', 'tuple', 'defaultdict',
})
_SAFE_LAMBDA_METHODS = frozenset({
    'lower', 'upper', 'strip', 'lstrip', 'rstrip', 'get', 'replace', 'index',
    'casefold', 'startswith', 'endswith', 'isdigit', 'isnumeric', 'isalpha',
    'find', 'rfind', 'zfill', 'join', 'strptime', 'strftime',
    'split', 'rsplit', 'partition', 'rpartition',
})
_SAFE_BUILTIN_SORT_KEYS = frozenset({'str', 'int', 'len', 'float', 'abs', 'bool'})


_SAFE_LAMBDA_MSG = format_ast_error(
    'SORT_KEY',
    "Unsafe lambda / sort key. "
    "Allowed: key=operator.itemgetter('field'), "
    "key=lambda x: x['field'], key=lambda x: float(x['Lon']) "
    "(also .get/.lower/.casefold/.split, len/str/int/float), "
    "calls to defs already defined in this script, "
    "and simple comprehensions whose calls stay in that allow-list. "
    "FORBIDDEN: yield/raise inside key=, and calls to names that are not "
    "builtins/helpers/script defs. "
    "Other metrics: PRECOMPUTE r['_ord']=… in a for-loop, then "
    "sorted(rows, key=operator.itemgetter('_ord')).",
)


def _collect_user_def_names(tree):
    """Names of def/async def in the script (bodies already AST-validated)."""
    return frozenset(
        n.name for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


def _is_safe_accessor_expr(expr, extra_call_names=()):
    """True si la expresión solo usa accesos/calls permitidos (cuerpo de lambda o return de def).

    Comprehensions are OK when nested calls stay on the allow-list (same sandbox
    surface as a for-loop). yield/raise remain forbidden inside key=/lambda.
    """
    if expr is None:
        return False
    extra = frozenset(extra_call_names or ())
    for child in ast.walk(expr):
        if isinstance(child, (ast.Yield, ast.YieldFrom, ast.Raise)):
            return False
        if isinstance(child, ast.Call):
            allow_call = False
            if isinstance(child.func, ast.Name) and (
                child.func.id in _SAFE_LAMBDA_CALL_NAMES
                or child.func.id in extra
            ):
                allow_call = True
            elif isinstance(child.func, ast.Attribute) and child.func.attr in _SAFE_LAMBDA_METHODS:
                allow_call = True
            if not allow_call:
                return False
    return True


def _is_safe_lambda(node, extra_call_names=()):
    """True si el cuerpo de la lambda solo usa accesos/calls permitidos."""
    return (
        isinstance(node, ast.Lambda)
        and _is_safe_accessor_expr(node.body, extra_call_names=extra_call_names)
    )


def _is_safe_sort_key_function(node, extra_call_names=()):
    """def sort_key(x): return x['field'] — un arg, un return accessor."""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    args = node.args
    if len(args.args) != 1 or args.vararg or args.kwarg or args.kwonlyargs:
        return False
    stmts = list(node.body or [])
    if (stmts and isinstance(stmts[0], ast.Expr)
            and isinstance(getattr(stmts[0], 'value', None), (ast.Constant, ast.Str))):
        stmts = stmts[1:]
    if len(stmts) != 1 or not isinstance(stmts[0], ast.Return):
        return False
    return _is_safe_accessor_expr(stmts[0].value, extra_call_names=extra_call_names)


def _is_safe_itemgetter_call(node):
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Attribute):
        if (isinstance(node.func.value, ast.Name) and
                node.func.value.id == 'operator' and
                node.func.attr in ('itemgetter', 'attrgetter')):
            return True
    elif isinstance(node.func, ast.Name):
        if node.func.id in ('itemgetter', 'attrgetter'):
            return True
    return False


def _collect_safe_sort_key_refs(tree):
    """Nombres usables como key=: lambdas/itemgetter, defs del script, builtins."""
    user_defs = _collect_user_def_names(tree)
    safe = set(user_defs)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_safe_sort_key_function(node, extra_call_names=user_defs):
                safe.add(node.name)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    val = node.value
                    if isinstance(val, ast.Lambda) and _is_safe_lambda(
                        val, extra_call_names=user_defs,
                    ):
                        safe.add(target.id)
                    elif _is_safe_itemgetter_call(val):
                        safe.add(target.id)
                    elif isinstance(val, ast.Name) and val.id in _SAFE_BUILTIN_SORT_KEYS:
                        safe.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            val = node.value
            if isinstance(val, ast.Lambda) and _is_safe_lambda(
                val, extra_call_names=user_defs,
            ):
                safe.add(node.target.id)
            elif _is_safe_itemgetter_call(val):
                safe.add(node.target.id)
            elif isinstance(val, ast.Name) and val.id in _SAFE_BUILTIN_SORT_KEYS:
                safe.add(node.target.id)
    return safe


def _is_safe_sort_key_value(node, safe_sort_key_refs):
    """True si key= de sorted/sort/min/max es seguro."""
    # (lambda x: ...) con paréntesis extra
    if isinstance(node, ast.Tuple) and len(node.elts) == 1:
        node = node.elts[0]
    if ast_literal(node)[0]:
        return True
    if isinstance(node, ast.Lambda):
        return _is_safe_lambda(node, extra_call_names=safe_sort_key_refs)
    if isinstance(node, ast.Name):
        if node.id in _SAFE_BUILTIN_SORT_KEYS:
            return True
        if node.id in ('itemgetter', 'attrgetter'):
            return True
        if node.id in safe_sort_key_refs:
            return True
        return False
    if _is_safe_itemgetter_call(node):
        return True
    return False


def _lambda_arg_name(lam):
    if not isinstance(lam, ast.Lambda):
        return None
    args = lam.args
    if len(args.args) != 1 or args.vararg or args.kwarg or args.kwonlyargs:
        return None
    return args.args[0].arg


def _rename_name_in_expr(expr, old_name, new_name):
    """Deep-copy expr renaming Load/Store of old_name → new_name."""
    expr = copy.deepcopy(expr)

    class _Ren(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id == old_name:
                return ast.Name(id=new_name, ctx=node.ctx)
            return node

    return _Ren().visit(expr)


def _resolve_unsafe_sort_key(key_node, safe_sort_key_refs, tree):
    """Return (arg_name, body_expr) for an unsafe sort key, else None."""
    if isinstance(key_node, ast.Tuple) and len(key_node.elts) == 1:
        key_node = key_node.elts[0]
    if isinstance(key_node, ast.Lambda):
        if _is_safe_lambda(key_node, extra_call_names=safe_sort_key_refs):
            return None
        arg = _lambda_arg_name(key_node)
        if not arg:
            return None
        return arg, key_node.body
    if isinstance(key_node, ast.Name):
        if _is_safe_sort_key_value(key_node, safe_sort_key_refs):
            return None
        name = key_node.id
        # Assigned lambda: key_fn = lambda x: …
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == name:
                        val = node.value
                        if isinstance(val, ast.Lambda):
                            if _is_safe_lambda(
                                val, extra_call_names=safe_sort_key_refs,
                            ):
                                return None
                            arg = _lambda_arg_name(val)
                            if not arg:
                                return None
                            return arg, val.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Script defs are already safe as key= callables.
                if node.name == name:
                    return None
        return None
    return None


def _sort_call_meta(call):
    """If call is sorted/min/max(/list.sort), return (kind, iterable, reverse_expr)."""
    if not isinstance(call, ast.Call):
        return None
    kind = None
    iterable = None
    if isinstance(call.func, ast.Name) and call.func.id in ('sorted', 'min', 'max'):
        kind = call.func.id
        if not call.args:
            return None
        iterable = call.args[0]
    elif isinstance(call.func, ast.Attribute) and call.func.attr == 'sort':
        kind = 'list_sort'
        iterable = call.func.value
    else:
        return None
    reverse = None
    for kw in call.keywords or ():
        if kw.arg == 'reverse':
            reverse = kw.value
    return kind, iterable, reverse


def _build_decorate_sort_stmts(iterable, arg_name, body, reverse, kind, target):
    """Build statements for decorate-sort-undecorate (unsafe key= → loop + itemgetter)."""
    n = _build_decorate_sort_stmts._counter
    _build_decorate_sort_stmts._counter = n + 1
    pairs = '__pns_sk%d' % n
    item = '__pns_skx%d' % n
    body2 = _rename_name_in_expr(body, arg_name, item)

    sort_keywords = [
        ast.keyword(
            arg='key',
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id='operator', ctx=ast.Load()),
                    attr='itemgetter',
                    ctx=ast.Load(),
                ),
                args=[ast.Constant(value=0)],
                keywords=[],
            ),
        ),
    ]
    if reverse is not None:
        sort_keywords.append(
            ast.keyword(arg='reverse', value=copy.deepcopy(reverse)),
        )

    stmts = [
        ast.Assign(
            targets=[ast.Name(id=pairs, ctx=ast.Store())],
            value=ast.List(elts=[], ctx=ast.Load()),
        ),
        ast.For(
            target=ast.Name(id=item, ctx=ast.Store()),
            iter=copy.deepcopy(iterable),
            body=[
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id=pairs, ctx=ast.Load()),
                            attr='append',
                            ctx=ast.Load(),
                        ),
                        args=[
                            ast.Tuple(
                                elts=[body2, ast.Name(id=item, ctx=ast.Load())],
                                ctx=ast.Load(),
                            ),
                        ],
                        keywords=[],
                    ),
                ),
            ],
            orelse=[],
        ),
        ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id=pairs, ctx=ast.Load()),
                    attr='sort',
                    ctx=ast.Load(),
                ),
                args=[],
                keywords=sort_keywords,
            ),
        ),
    ]

    undress = ast.ListComp(
        elt=ast.Name(id=item, ctx=ast.Load()),
        generators=[
            ast.comprehension(
                target=ast.Tuple(
                    elts=[
                        ast.Name(id='_', ctx=ast.Store()),
                        ast.Name(id=item, ctx=ast.Store()),
                    ],
                    ctx=ast.Store(),
                ),
                iter=ast.Name(id=pairs, ctx=ast.Load()),
                ifs=[],
                is_async=0,
            ),
        ],
    )
    if kind == 'sorted':
        stmts.append(ast.Assign(targets=[target], value=undress))
    elif kind == 'min':
        stmts.append(
            ast.Assign(
                targets=[target],
                value=ast.Subscript(
                    value=ast.Call(
                        func=ast.Name(id='min', ctx=ast.Load()),
                        args=[ast.Name(id=pairs, ctx=ast.Load())],
                        keywords=[],
                    ),
                    slice=ast.Constant(value=1),
                    ctx=ast.Load(),
                ),
            ),
        )
    elif kind == 'max':
        stmts.append(
            ast.Assign(
                targets=[target],
                value=ast.Subscript(
                    value=ast.Call(
                        func=ast.Name(id='max', ctx=ast.Load()),
                        args=[ast.Name(id=pairs, ctx=ast.Load())],
                        keywords=[],
                    ),
                    slice=ast.Constant(value=1),
                    ctx=ast.Load(),
                ),
            ),
        )
    elif kind == 'list_sort':
        stmts.append(
            ast.Assign(
                targets=[
                    ast.Subscript(
                        value=copy.deepcopy(iterable),
                        slice=ast.Slice(lower=None, upper=None, step=None),
                        ctx=ast.Store(),
                    ),
                ],
                value=undress,
            ),
        )
    return stmts


_build_decorate_sort_stmts._counter = 0


def repair_unsafe_sort_keys(code):
    """Rewrite sorted/min/max/list.sort with unsafe key= via decorate-sort.

    Moves calls like band_dist/haversine out of key= into a for-loop, then
    sorts with operator.itemgetter(0). Returns (code, changed).
    """
    if not code or not isinstance(code, str):
        return code, False
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, False

    safe_refs = _collect_safe_sort_key_refs(tree)
    _build_decorate_sort_stmts._counter = 0
    changed = [False]

    def _key_from_call(call):
        for kw in call.keywords or ():
            if kw.arg == 'key':
                return kw.value
        return None

    def transform_stmts(stmts):
        out = []
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                stmt.body = transform_stmts(stmt.body)
                out.append(stmt)
                continue
            if isinstance(stmt, ast.ClassDef):
                out.append(stmt)
                continue
            if isinstance(stmt, ast.If):
                stmt.body = transform_stmts(stmt.body)
                stmt.orelse = transform_stmts(stmt.orelse)
                out.append(stmt)
                continue
            if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                stmt.body = transform_stmts(stmt.body)
                stmt.orelse = transform_stmts(stmt.orelse)
                out.append(stmt)
                continue
            if isinstance(stmt, ast.With) or (
                    hasattr(ast, 'AsyncWith') and isinstance(stmt, ast.AsyncWith)):
                stmt.body = transform_stmts(stmt.body)
                out.append(stmt)
                continue
            if isinstance(stmt, ast.Try):
                stmt.body = transform_stmts(stmt.body)
                stmt.orelse = transform_stmts(stmt.orelse)
                stmt.finalbody = transform_stmts(stmt.finalbody)
                for h in stmt.handlers or ():
                    h.body = transform_stmts(h.body)
                out.append(stmt)
                continue

            # target = sorted/min/max(...)
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                call = stmt.value
                meta = _sort_call_meta(call)
                if meta and meta[0] in ('sorted', 'min', 'max'):
                    kind, iterable, reverse = meta
                    key_node = _key_from_call(call)
                    resolved = (
                        _resolve_unsafe_sort_key(key_node, safe_refs, tree)
                        if key_node is not None else None
                    )
                    if resolved:
                        arg_name, body = resolved
                        out.extend(
                            _build_decorate_sort_stmts(
                                iterable, arg_name, body, reverse, kind,
                                stmt.targets[0],
                            ),
                        )
                        changed[0] = True
                        continue

            # rows.sort(key=...)
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                meta = _sort_call_meta(call)
                if meta and meta[0] == 'list_sort':
                    kind, iterable, reverse = meta
                    key_node = _key_from_call(call)
                    resolved = (
                        _resolve_unsafe_sort_key(key_node, safe_refs, tree)
                        if key_node is not None else None
                    )
                    if resolved:
                        arg_name, body = resolved
                        out.extend(
                            _build_decorate_sort_stmts(
                                iterable, arg_name, body, reverse, kind,
                                None,
                            ),
                        )
                        changed[0] = True
                        continue

            out.append(stmt)
        return out

    tree.body = transform_stmts(tree.body)
    if not changed[0]:
        return code, False

    # Drop orphaned unsafe lambda assigns left after rewriting their sort uses.
    loaded = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            loaded.add(node.id)

    def _strip_unused_unsafe_lambdas(stmts):
        out = []
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                stmt.body = _strip_unused_unsafe_lambdas(stmt.body)
                out.append(stmt)
                continue
            if isinstance(stmt, ast.If):
                stmt.body = _strip_unused_unsafe_lambdas(stmt.body)
                stmt.orelse = _strip_unused_unsafe_lambdas(stmt.orelse)
                out.append(stmt)
                continue
            if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                stmt.body = _strip_unused_unsafe_lambdas(stmt.body)
                stmt.orelse = _strip_unused_unsafe_lambdas(stmt.orelse)
                out.append(stmt)
                continue
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                t = stmt.targets[0]
                if (
                    isinstance(t, ast.Name)
                    and isinstance(stmt.value, ast.Lambda)
                    and not _is_safe_lambda(
                        stmt.value, extra_call_names=safe_refs,
                    )
                    and t.id not in loaded
                ):
                    changed[0] = True
                    continue
            out.append(stmt)
        return out

    tree.body = _strip_unused_unsafe_lambdas(tree.body)

    try:
        ast.fix_missing_locations(tree)
    except Exception:
        pass
    try:
        return ast.unparse(tree), True
    except Exception:
        _logger.warning('repair_unsafe_sort_keys: ast.unparse failed', exc_info=True)
        return code, False
