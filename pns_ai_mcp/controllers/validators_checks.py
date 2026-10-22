# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Single AST checks of relaxaicode code and the reject texts they return."""

import ast

from .validators_base import (
    AST_KIND_MANDATORY,
    RELAXAICODE_DRIVER_METHODS,
    RELAXAICODE_EXTERNAL_API_METHODS,
    RELAXAICODE_MAX_FUNCTION_DEFS,
    RELAXAICODE_MAX_FUNCTION_NESTING_DEPTH,
    RELAXAICODE_ORM_WRITE_ATTRS,
    RELAXAICODE_PRIVILEGE_ATTRS,
    RELAXAICODE_PRIVILEGE_HINT,
    RELAXAICODE_SIDE_EFFECT_METHODS,
    _is_name_env,
    ast_literal,
    catalogue_inspect_error,
    format_ast_error,
)


def _dangerous_name_error(name):
    """Hint al rechazar builtins de introspección (dir/locals/…)."""
    if name == 'dir':
        return format_ast_error(
            'DIR',
            "Cannot use 'dir'. List fields with sorted(Model._fields); "
            "do not probe methods via dir().",
        )
    if name in ('locals', 'globals', 'vars'):
        return format_ast_error(
            name.upper(),
            "Cannot use '%s'. Initialize variables explicitly "
            "(e.g. result = {}) instead of "
            "'name' in locals()/globals()/vars()." % name,
        )
    return format_ast_error(
        name.upper() if str(name).isidentifier() else 'NAME',
        "Cannot use '%s'. This name is blocked in RelaxAICode." % name,
    )


def _dangerous_attr_error(attr):
    """Hint al rechazar attrs de sandbox (registry/cr/frames…)."""
    if attr in ('registry', '_registry', 'pool'):
        return format_ast_error(
            'REGISTRY',
            "Cannot access '%s'. "
            "Discover models with env['ir.model'].search([('model', 'ilike', '…')]) "
            "and fields with env['model.name']._fields — never env.registry."
            % attr,
        )
    if attr in ('cr', '_cr'):
        return format_ast_error(
            'CR',
            "Cannot access '%s'. Use the ORM (env['model']) — no raw SQL. "
            "The database name is not available in the sandbox. "
            "Never write env.cr.dbname."
            % attr,
        )
    if attr == '__name__':
        return format_ast_error(
            'DUNDER_NAME',
            "Cannot access '__name__'. "
            "Allowed only as type(value).__name__ (a plain string label). "
            "Do NOT use obj.__name__, exc.__class__.__name__, or getattr(..., '__name__'). "
            "Prefer isinstance(value, …) or a fixed literal string.",
        )
    return format_ast_error(
        attr.upper() if str(attr).isidentifier() else 'ATTR',
        "Cannot access '%s'. This attribute is blocked in RelaxAICode." % attr,
    )


def _is_safe_type_name_access(node):
    """True solo para type(...).__name__ (etiqueta str; no vector de escape)."""
    if not isinstance(node, ast.Attribute) or node.attr != '__name__':
        return False
    val = node.value
    if not isinstance(val, ast.Call):
        return False
    func = val.func
    return isinstance(func, ast.Name) and func.id == 'type'


def _check_env_parameter_binding(tree):
    """Refuse calls that bind parameter ``env`` to anything but Name ``env``.

    Structural contract: ``env`` is the Odoo Environment injected in the
    sandbox. Passing ``previous_result`` / ``raw_data`` / lists into a param
    named ``env`` yields ``TypeError: list indices must be integers…`` when
    the body does ``env['model']``.

    Returns:
        (ok, error_message|None)
    """
    funcs = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs[node.name] = node

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        fdef = funcs.get(node.func.id)
        if fdef is None:
            continue

        env_pos = None
        for i, arg in enumerate(fdef.args.args):
            if arg.arg == 'env':
                env_pos = i
                break
        has_kwonly_env = any(a.arg == 'env' for a in fdef.args.kwonlyargs)
        if env_pos is None and not has_kwonly_env:
            continue

        for kw in node.keywords:
            if kw.arg == 'env' and not _is_name_env(kw.value):
                return False, (
                    "[PROHIBITED] Parameter 'env' must receive the sandbox "
                    "variable 'env', not previous_result/raw_data/lists. "
                    "Correct: result = %s(env). "
                    "Wrong: result = %s(previous_result.get('data') or [])."
                    % (node.func.id, node.func.id)
                )

        if env_pos is not None and len(node.args) > env_pos:
            if not _is_name_env(node.args[env_pos]):
                return False, (
                    "[PROHIBITED] Parameter 'env' must receive the sandbox "
                    "variable 'env', not previous_result/raw_data/lists. "
                    "Correct: result = %s(env). "
                    "Wrong: result = %s(previous_result.get('data') or [])."
                    % (node.func.id, node.func.id)
                )

    return True, None


_SEARCH_DOMAIN_METHODS = frozenset({
    'search', 'search_count', 'search_read', 'read_group', 'web_search_read',
})
_PRIOR_RESULT_NAMES = frozenset({'previous_result', 'raw_data'})
_SEARCH_DOMAIN_KEYWORDS = frozenset({'domain', 'args'})


def _is_empty_domain_filler(node):
    """None / False / [] / () — not a real ORM domain, just the recipe fallback."""
    ok, val = ast_literal(node)
    if ok:
        return val in (None, False, (), '', 0)
    if isinstance(node, (ast.List, ast.Tuple, ast.Dict)):
        return not (getattr(node, 'elts', None) or getattr(node, 'keys', None))
    return False


def _is_prior_result_alias(node, aliases):
    """True when *node* is previous_result/raw_data or a name bound from them.

    Structural: the whole expression is the prior dataset (or the recipe
    ``previous_result.get('data') or raw_data or []``). A listcomp of ids
    or a real domain list is not an alias.
    """
    if isinstance(node, ast.Name):
        return node.id in _PRIOR_RESULT_NAMES or node.id in aliases
    if isinstance(node, ast.Attribute):
        return _is_prior_result_alias(node.value, aliases)
    if isinstance(node, ast.Subscript):
        return _is_prior_result_alias(node.value, aliases)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            return _is_prior_result_alias(node.func.value, aliases)
        if isinstance(node.func, ast.Name) and node.func.id in ('list', 'tuple'):
            return any(_is_prior_result_alias(a, aliases) for a in node.args)
        return False
    if isinstance(node, ast.BoolOp):
        has_prior = False
        for val in node.values:
            if _is_prior_result_alias(val, aliases):
                has_prior = True
            elif _is_empty_domain_filler(val):
                continue
            else:
                return False
        return has_prior
    if isinstance(node, ast.IfExp):
        body_ok = (
            _is_prior_result_alias(node.body, aliases)
            or _is_empty_domain_filler(node.body)
        )
        else_ok = (
            _is_prior_result_alias(node.orelse, aliases)
            or _is_empty_domain_filler(node.orelse)
        )
        has_prior = (
            _is_prior_result_alias(node.body, aliases)
            or _is_prior_result_alias(node.orelse, aliases)
        )
        return body_ok and else_ok and has_prior
    return False


def _bind_assign_aliases(targets, value, aliases):
    is_alias = _is_prior_result_alias(value, aliases)
    names = []
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            names.extend(
                elt.id for elt in target.elts if isinstance(elt, ast.Name)
            )
    for name in names:
        if is_alias:
            aliases.add(name)
        else:
            aliases.discard(name)


def _collect_prior_result_aliases(body, aliases):
    for stmt in body or ():
        if isinstance(stmt, ast.Assign):
            _bind_assign_aliases(stmt.targets, stmt.value, aliases)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if stmt.value is not None:
                _bind_assign_aliases([stmt.target], stmt.value, aliases)
        elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
            if _is_prior_result_alias(stmt.value, aliases):
                aliases.add(stmt.target.id)
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _collect_prior_result_aliases(stmt.body, aliases)
        elif isinstance(stmt, ast.If):
            _collect_prior_result_aliases(stmt.body, aliases)
            _collect_prior_result_aliases(stmt.orelse, aliases)
        elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            _collect_prior_result_aliases(stmt.body, aliases)
            _collect_prior_result_aliases(stmt.orelse, aliases)
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            _collect_prior_result_aliases(stmt.body, aliases)
        elif isinstance(stmt, ast.Try):
            _collect_prior_result_aliases(stmt.body, aliases)
            for handler in stmt.handlers:
                _collect_prior_result_aliases(handler.body, aliases)
            _collect_prior_result_aliases(stmt.orelse, aliases)
            _collect_prior_result_aliases(stmt.finalbody, aliases)


def _search_domain_arg(node):
    """First positional domain, or domain=/args= keyword."""
    if node.args:
        return node.args[0]
    for kw in node.keywords:
        if kw.arg in _SEARCH_DOMAIN_KEYWORDS:
            return kw.value
    return None


def _check_search_domain_not_prior_result(tree):
    """Refuse Model.search(previous_result) and the SQHX3 recipe alias.

    Invariant: the domain argument is an ORM domain (list of tuples and
    '|','&','!'), never the prior-tool dataset. No model or field names.
    """
    aliases = set()
    _collect_prior_result_aliases(getattr(tree, 'body', ()) or (), aliases)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in _SEARCH_DOMAIN_METHODS:
            continue
        domain = _search_domain_arg(node)
        if domain is None:
            continue
        if _is_prior_result_alias(domain, aliases):
            return False, format_ast_error(
                'SEARCH_DOMAIN',
                "Model.search/search_count/read_group first argument must be "
                "an ORM domain (list of tuples and '|', '&', '!'), not "
                "previous_result, raw_data, or rows from a prior tool. "
                "Wrong: Model.search(domain) after "
                "domain = previous_result.get('data') or []. "
                "Correct: Model.search([('field', '=', value)]).",
            )
    return True, None


def _check_function_def_limits(tree):
    """Valida nº total y profundidad de anidamiento de def/async def.

    Returns:
        (ok, error_message|None)
    """
    total = 0
    max_depth = 0
    error = []

    class _Visitor(ast.NodeVisitor):
        def __init__(self):
            self.depth = 0

        def _enter_def(self, node):
            nonlocal total, max_depth
            total += 1
            self.depth += 1
            if self.depth > max_depth:
                max_depth = self.depth
            if total > RELAXAICODE_MAX_FUNCTION_DEFS:
                error.append(
                    "[PROHIBITED] Too many function definitions (%s). "
                    "Relaxaicode allows at most %s def/async def in one script. "
                    "Inline helpers or split the work."
                    % (total, RELAXAICODE_MAX_FUNCTION_DEFS)
                )
            elif self.depth > RELAXAICODE_MAX_FUNCTION_NESTING_DEPTH:
                error.append(
                    "[PROHIBITED] Function nesting too deep (depth %s). "
                    "Relaxaicode allows at most %s levels "
                    "(module-level def = 1; def inside def = 2). "
                    "Keep helpers flat."
                    % (self.depth, RELAXAICODE_MAX_FUNCTION_NESTING_DEPTH)
                )
            self.generic_visit(node)
            self.depth -= 1

        def visit_FunctionDef(self, node):
            self._enter_def(node)

        def visit_AsyncFunctionDef(self, node):
            self._enter_def(node)

    _Visitor().visit(tree)
    if error:
        return False, error[0]
    return True, None


def _privilege_error(name):
    return format_ast_error('PRIVILEGE', RELAXAICODE_PRIVILEGE_HINT % (name,))


def _privilege_attr_in_call(node):
    """``getattr(x, 'sudo')`` / ``attrgetter('env')`` / ``methodcaller('sudo')``."""
    if not isinstance(node, ast.Call) or not node.args:
        return None
    func = node.func
    name = func.id if isinstance(func, ast.Name) else (
        func.attr if isinstance(func, ast.Attribute) else None)
    if name == 'getattr' and len(node.args) >= 2:
        literal = _ast_static_str(node.args[1])
    elif name in ('attrgetter', 'methodcaller'):
        literal = _ast_static_str(node.args[0])
    else:
        return None
    if not isinstance(literal, str):
        return None
    for part in literal.split('.'):
        if part in RELAXAICODE_PRIVILEGE_ATTRS:
            return part
    return None


def _external_api_bypass_error(method_name):
    return format_ast_error(
        'API_CATALOGUE',
        "RelaxAICode cannot access external API catalogue/secrets "
        "via ORM (%r). Use the injected catalogue and safe_plan_request "
        "with op='api_call' — never read ai.api.server drivers or specs from code."
        % method_name,
    )


def _ast_is_env_root(node):
    """True for ``env`` or ``env.sudo()`` / ``with_context`` / ``with_user`` chains."""
    if isinstance(node, ast.Name) and node.id == 'env':
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in (
            'sudo', 'with_context', 'with_user', 'with_env', 'with_company',
        ):
            return _ast_is_env_root(node.func.value)
    return False


def _ast_env_model_literal(node):
    """Return model name if *node* is ``env['model']`` / ``env.sudo()['model']``."""
    if not isinstance(node, ast.Subscript):
        return None
    if not _ast_is_env_root(node.value):
        return None
    return _ast_static_str(node.slice) or _ast_static_str(
        getattr(node.slice, 'value', None)  # Index(value) on py<3.9
    )


def _ast_env_get_model_literal(node):
    """Return model name if *node* is ``env.get('model', ...)`` (incl. sudo chain)."""
    if not isinstance(node, ast.Call):
        return None
    if not isinstance(node.func, ast.Attribute) or node.func.attr != 'get':
        return None
    if not _ast_is_env_root(node.func.value):
        return None
    if not node.args:
        return None
    return _ast_static_str(node.args[0])


def _receiver_is_get_driver_call(node):
    """True when *node* is ``something._get_driver()``."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    val = node.func.value
    return (
        isinstance(val, ast.Call)
        and isinstance(val.func, ast.Attribute)
        and val.func.attr == '_get_driver'
    )


def _detect_external_api_bypass_from_ast(tree):
    """Block ORM shortcuts to catalogue inspect / external HTTP (bypass tools)."""
    forbidden = RELAXAICODE_EXTERNAL_API_METHODS
    driver_methods = RELAXAICODE_DRIVER_METHODS

    for node in ast.walk(tree):
        model = _ast_env_model_literal(node) or _ast_env_get_model_literal(node)
        inspect_err = catalogue_inspect_error(model) if model else None
        if inspect_err:
            return inspect_err
        if isinstance(node, ast.Attribute) and node.attr in forbidden:
            return _external_api_bypass_error(node.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            method = node.func.attr
            if method in forbidden:
                return _external_api_bypass_error(method)
            if method in driver_methods and _receiver_is_get_driver_call(node):
                return _external_api_bypass_error(method)
    return None


def _ast_static_str(node):
    """Resolve a compile-time string expression (Constant / Str / 'a'+'b')."""
    if node is None:
        return None
    ok, value = ast_literal(node)
    if ok and isinstance(value, str):
        return value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _ast_static_str(node.left)
        right = _ast_static_str(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _detect_requires_write_from_ast(tree):
    """
    Detecta escritura ORM intencional (caja B).

    No marca .sudo() (solo eleva permisos), acumuladores locales (total += 1)
    ni copy.deepcopy() / copy.copy() del módulo copy.

    También marca métodos de Safe Plan que escriben sin llamarse .write()
    (confirm_by_user, execute_plan_now, …): si corren en caja A toman locks
    de fila y el toast humano se queda en spinner hasta el rollback.

    Cubre ofuscación estática: getattr(rec, 'wr'+'ite'), attrgetter('write').
    """
    orm_write_methods = frozenset({'create', 'write', 'unlink'})
    side_effect_methods = RELAXAICODE_SIDE_EFFECT_METHODS
    by_name = RELAXAICODE_ORM_WRITE_ATTRS | side_effect_methods

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            method = node.func.attr
            if method in orm_write_methods or method in side_effect_methods:
                return True
            if method == 'copy':
                base = node.func.value
                if isinstance(base, ast.Name) and base.id == 'copy':
                    continue
                return True
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == 'operator'
                and node.func.attr in ('attrgetter', 'methodcaller')
                and node.args
            ):
                attr = _ast_static_str(node.args[0])
                if attr in by_name:
                    return True

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            # getattr(obj, 'write') / getattr(obj, 'wr'+'ite')
            if node.func.id == 'getattr' and len(node.args) >= 2:
                attr = _ast_static_str(node.args[1])
                if attr in by_name:
                    return True
            if node.func.id in ('attrgetter', 'methodcaller') and node.args:
                attr = _ast_static_str(node.args[0])
                if attr in by_name:
                    return True

        if isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Attribute) and isinstance(
                node.op, (ast.BitOr, ast.Add, ast.Sub)
            ):
                return True

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    return True

    return False


def _target_is_result(node):
    return isinstance(node, ast.Name) and node.id == 'result'


def _stmt_assigns_result(node):
    """Check if a statement assigns to 'result', including inside if/else/for/while."""
    if isinstance(node, ast.Assign):
        return any(_target_is_result(t) for t in node.targets)
    if isinstance(node, ast.AugAssign):
        return _target_is_result(node.target)
    if isinstance(node, ast.AnnAssign):
        return node.target is not None and _target_is_result(node.target)
    # Recurse into compound statements (if/else, for, while, try, with)
    if isinstance(node, ast.If):
        return (any(_stmt_assigns_result(s) for s in node.body) or
                any(_stmt_assigns_result(s) for s in node.orelse))
    if isinstance(node, (ast.For, ast.While)):
        return any(_stmt_assigns_result(s) for s in node.body)
    if isinstance(node, ast.Try):
        return (any(_stmt_assigns_result(s) for s in node.body) or
                any(_stmt_assigns_result(s) for s in node.orelse) or
                any(_stmt_assigns_result(s) for s in node.finalbody) or
                any(_stmt_assigns_result(s) for handler in node.handlers for s in handler.body))
    if isinstance(node, ast.With):
        return any(_stmt_assigns_result(s) for s in node.body)
    return False


def _validate_result_assignment(tree):
    """
    Valida que `result` se asigne antes de cualquier uso (código plano, sin funciones).
    Returns:
        tuple: (is_valid, error_message)
    """
    assigned = False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        loads = [
            n for n in ast.walk(node)
            if isinstance(n, ast.Name) and n.id == 'result' and isinstance(n.ctx, ast.Load)
        ]
        assigns_here = _stmt_assigns_result(node)

        # Same top-level statement may both assign and load (typical LLM pattern:
        # if …: result = {} else: result = []; result.append(...)).
        # ast.walk sees those Loads before we flip `assigned`; do not reject
        # when this statement itself assigns to result.
        if loads and not assigned and not assigns_here:
            return False, format_ast_error(
                'RESULT',
                "Variable 'result' is used before assignment. "
                "Initialize first: result = [] or result = {...}. "
                "Never use a bare 'result' line or result.append(...) without result = [] first.",
                kind=AST_KIND_MANDATORY,
            )

        if assigns_here:
            assigned = True

    if not assigned:
        return False, format_ast_error(
            'RESULT',
            "Code must assign the output to variable 'result'. "
            "Example: result = {'data': rows}. Do not use 'return' or a bare 'result' expression.",
            kind=AST_KIND_MANDATORY,
        )

    return True, None
