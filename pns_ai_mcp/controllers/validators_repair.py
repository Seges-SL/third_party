# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Rewrites of common model mistakes before the AST check (dir(), cr.dbname, %, registry, leaked markup)."""

import ast
import re
import logging

from .validators_base import (
    _is_name_env,
    ast_literal,
)

_logger = logging.getLogger(__name__)


def repair_locals_dir_checks(code):
    """Reescribe comprobaciones `in dir()/locals()/globals()/vars()` → uso directo
    y ``dir(model)`` → ``sorted(model._fields)``.

    El sandbox ya define previous_result/raw_data/lugar/fecha (None si faltan),
    así que `if lugar:` basta. ``dir(obj)`` es el patrón típico del LLM para
    listar campos; el validador lo prohíbe — aquí se reescribe al idiom
    documentado. Devuelve (nuevo_código, hubo_cambio).
    """
    if not code or not isinstance(code, str):
        return code, False
    original = code
    # name if 'name' in dir() and name else X  →  name if name else X
    code = re.sub(
        r"(\b\w+)\s+if\s+(['\"])\1\2\s+in\s+"
        r"(?:dir|locals|globals|vars)\(\)\s+and\s+\1\b",
        r"\1 if \1",
        code,
    )
    # 'name' in dir() and name  →  name
    code = re.sub(
        r"(['\"])(\w+)\1\s+in\s+(?:dir|locals|globals|vars)\(\)\s+and\s+\2\b",
        r"\2",
        code,
    )
    # 'name' in dir()  →  (\2 is not None)  — presencia del nombre inyectado
    code = re.sub(
        r"(['\"])(\w+)\1\s+in\s+(?:dir|locals|globals|vars)\(\)",
        r"(\2 is not None)",
        code,
    )
    # name in locals() / name in globals() (sin comillas) → name is not None
    code = re.sub(
        r"\b(\w+)\s+in\s+(?:locals|globals|vars)\(\)",
        r"(\1 is not None)",
        code,
    )
    code, _dir_calls = _rewrite_dir_calls(code)
    return code, code != original


class _RewriteDirCalls(ast.NodeTransformer):
    """dir(x) → sorted(x._fields); dir(x._fields) → sorted(x._fields)."""

    def __init__(self):
        ast.NodeTransformer.__init__(self)
        self.changed = False

    def visit_Call(self, node):
        node = self.generic_visit(node)
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == 'dir'):
            return node
        if node.keywords or len(node.args) != 1:
            return node
        target = node.args[0]
        if isinstance(target, ast.Attribute) and target.attr == '_fields':
            fields_expr = target
        else:
            fields_expr = ast.Attribute(
                value=target, attr='_fields', ctx=ast.Load(),
            )
        self.changed = True
        return ast.copy_location(
            ast.Call(
                func=ast.Name(id='sorted', ctx=ast.Load()),
                args=[fields_expr],
                keywords=[],
            ),
            node,
        )


def _rewrite_dir_calls(code):
    """AST rewrite of one-arg ``dir(x)`` used as field probing."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, False
    rewriter = _RewriteDirCalls()
    new_tree = rewriter.visit(tree)
    if not rewriter.changed:
        return code, False
    try:
        ast.fix_missing_locations(new_tree)
    except Exception:
        pass
    try:
        return ast.unparse(new_tree), True
    except Exception:
        _logger.warning('repair dir()→_fields: ast.unparse failed', exc_info=True)
        return code, False


_CR_DBNAME_TERNARY = re.compile(
    r"env\._?cr\.dbname\s+if\s+hasattr\(\s*env\s*,\s*['\"]_?cr['\"]\s*\)"
    r"\s+else\s+(?:''|\"\"|None|\S+)"
)
_CR_DBNAME_GETATTR = re.compile(
    r"getattr\(\s*env\._?cr\s*,\s*['\"]dbname['\"]\s*(?:,\s*[^)]*)?\)"
)
_CR_DBNAME_ATTR = re.compile(r"\benv\._?cr\.dbname\b")


def repair_cr_dbname(code):
    """Reescribe `env.cr.dbname` (y variantes) → `''`.

    El cursor está prohibido en el sandbox y el nombre de la base de datos ya
    no se publica: la expresión queda como cadena vacía, sin filtrar el nombre.
    No reescribe `env.cr` genérico (sigue bloqueado). Devuelve (código, cambió).
    """
    if not code or not isinstance(code, str):
        return code, False
    out = _CR_DBNAME_TERNARY.sub("''", code)
    out = _CR_DBNAME_GETATTR.sub("''", out)
    out = _CR_DBNAME_ATTR.sub("''", out)
    return out, out != code


# Old-style ``'… % …' % value``: a literal percent before ``=`` (KPI footers)
# is not a conversion and raises ValueError at exec. Keep valid ``%s`` / ``%.0f``.
_PERCENT_TYPES = frozenset('diouxXeEfFgGcrsa')
_PERCENT_FLAGS = frozenset('#0- +')


def _consume_percent_conversion(fmt, start):
    """Index after a valid ``%`` conversion at *start*, or None."""
    n = len(fmt)
    j = start + 1
    if j >= n:
        return None
    if fmt[j] == '%':
        return j + 1
    if fmt[j] == '(':
        close = fmt.find(')', j + 1)
        if close < 0:
            return None
        j = close + 1
    while j < n and fmt[j] in _PERCENT_FLAGS:
        j += 1
    if j < n and fmt[j] == '*':
        j += 1
    else:
        while j < n and fmt[j].isdigit():
            j += 1
    if j < n and fmt[j] == '.':
        j += 1
        if j < n and fmt[j] == '*':
            j += 1
        else:
            while j < n and fmt[j].isdigit():
                j += 1
    if j < n and fmt[j] in 'hlL':
        j += 1
    if j < n and fmt[j] in _PERCENT_TYPES:
        return j + 1
    return None


def escape_stray_percent_in_format(fmt):
    """Turn stray ``%`` into ``%%``; leave real conversions and ``%%`` alone."""
    if not fmt or '%' not in fmt:
        return fmt
    out = []
    i = 0
    n = len(fmt)
    while i < n:
        if fmt[i] != '%':
            out.append(fmt[i])
            i += 1
            continue
        end = _consume_percent_conversion(fmt, i)
        if end is None:
            out.append('%%')
            i += 1
        else:
            out.append(fmt[i:end])
            i = end
    return ''.join(out)


class _RewritePercentFormat(ast.NodeTransformer):
    """``'Deuda % = … %.0f%%' % x`` → escape the KPI percent, keep ``%.0f``."""

    def __init__(self):
        ast.NodeTransformer.__init__(self)
        self.changed = False

    def visit_BinOp(self, node):
        node = self.generic_visit(node)
        if not isinstance(node.op, ast.Mod):
            return node
        left = node.left
        ok, text = ast_literal(left)
        if not (ok and isinstance(text, str)):
            return node
        fixed = escape_stray_percent_in_format(text)
        if fixed == text:
            return node
        self.changed = True
        node.left = ast.copy_location(ast.Constant(value=fixed), left)
        return node


def repair_percent_format_strings(code):
    """Escape literal ``%`` in ``str % value`` that are not conversions.

    LLM KPI footers like ``'Deuda % = residual / billed' % threshold`` raise
    ``unsupported format character '='``. Numeric ``n % 2`` and dict keys
    ``'Deuda %'`` are left alone. Returns ``(code, changed)``.
    """
    if not code or not isinstance(code, str) or '%' not in code:
        return code, False
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, False
    rewriter = _RewritePercentFormat()
    new_tree = rewriter.visit(tree)
    if not rewriter.changed:
        return code, False
    try:
        ast.fix_missing_locations(new_tree)
    except Exception:
        pass
    try:
        return ast.unparse(new_tree), True
    except Exception:
        _logger.warning('repair percent-format: ast.unparse failed', exc_info=True)
        return code, False


_REGISTRY_ATTRS = frozenset({'registry', '_registry', 'pool'})
_REGISTRY_LISTING_FUNCS = frozenset({'list', 'sorted', 'set', 'tuple'})


def _is_env_registry_attr(node):
    """True for ``env.registry`` / ``env._registry`` / ``env.pool``."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr in _REGISTRY_ATTRS
        and _is_name_env(node.value)
    )


def _is_env_registry_models(node):
    """True for ``env.registry.models`` (and _registry/pool)."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == 'models'
        and _is_env_registry_attr(node.value)
    )


def _ir_model_names_expr():
    """AST for ``env['ir.model'].search([]).mapped('model')``."""
    ir_model = ast.Subscript(
        value=ast.Name(id='env', ctx=ast.Load()),
        slice=ast.Constant(value='ir.model'),
        ctx=ast.Load(),
    )
    search_call = ast.Call(
        func=ast.Attribute(value=ir_model, attr='search', ctx=ast.Load()),
        args=[ast.List(elts=[], ctx=ast.Load())],
        keywords=[],
    )
    return ast.Call(
        func=ast.Attribute(value=search_call, attr='mapped', ctx=ast.Load()),
        args=[ast.Constant(value='model')],
        keywords=[],
    )


class _RewriteRegistryModels(ast.NodeTransformer):
    """Idioma Odoo de listar modelos vía registry → ``ir.model``.

    Reescribe solo listing/membership/subscript. ``env.registry.cursor()`` y
    otros attrs siguen prohibidos.
    """

    def __init__(self):
        ast.NodeTransformer.__init__(self)
        self.changed = False

    def visit_Call(self, node):
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == 'keys'
            and not node.args
            and not node.keywords
            and (
                _is_env_registry_models(func.value)
                or _is_env_registry_attr(func.value)
            )
        ):
            self.changed = True
            return _ir_model_names_expr()
        if (
            isinstance(func, ast.Name)
            and func.id in _REGISTRY_LISTING_FUNCS
            and len(node.args) == 1
            and not node.keywords
            and _is_env_registry_attr(node.args[0])
        ):
            self.changed = True
            node = ast.copy_location(
                ast.Call(
                    func=func,
                    args=[_ir_model_names_expr()],
                    keywords=[],
                ),
                node,
            )
            return node
        return self.generic_visit(node)

    def visit_Attribute(self, node):
        if _is_env_registry_models(node):
            self.changed = True
            return _ir_model_names_expr()
        return self.generic_visit(node)

    def visit_Compare(self, node):
        node = self.generic_visit(node)
        if (
            len(node.ops) == 1
            and isinstance(node.ops[0], ast.In)
            and len(node.comparators) == 1
            and _is_env_registry_attr(node.comparators[0])
        ):
            self.changed = True
            node.comparators[0] = ast.Name(id='env', ctx=ast.Load())
        return node

    def visit_Subscript(self, node):
        node = self.generic_visit(node)
        if _is_env_registry_attr(node.value):
            self.changed = True
            node.value = ast.Name(id='env', ctx=ast.Load())
        return node

    def visit_comprehension(self, node):
        node = self.generic_visit(node)
        if _is_env_registry_attr(node.iter):
            self.changed = True
            node.iter = _ir_model_names_expr()
        return node

    def visit_For(self, node):
        node = self.generic_visit(node)
        if _is_env_registry_attr(node.iter):
            self.changed = True
            node.iter = _ir_model_names_expr()
        return node


def repair_registry_models(code):
    """Reescribe listing/membership de ``env.registry`` → ``ir.model``.

    Idioma típico del LLM (UBWS/PR1Y): iterar ``env.registry.models`` o
    ``env.registry`` para descubrir nombres. El candado sigue bloqueando
    ``env.registry.cursor()`` y el resto de attrs. Devuelve (código, cambió).
    """
    if not code or not isinstance(code, str):
        return code, False
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, False
    rewriter = _RewriteRegistryModels()
    new_tree = rewriter.visit(tree)
    if not rewriter.changed:
        return code, False
    try:
        ast.fix_missing_locations(new_tree)
    except Exception:
        pass
    try:
        return ast.unparse(new_tree), True
    except Exception:
        _logger.warning(
            'repair env.registry→ir.model: ast.unparse failed', exc_info=True,
        )
        return code, False


_LEAKED_PARAM_TAG = re.compile(r'</?parameter\b', re.IGNORECASE)


def strip_leaked_tool_markup(code):
    """Drop a tool-call ``<parameter>`` tail the model glued onto the script.

    Seed-style calls sometimes close ``code`` with ``</parameter name="summary"…>``
    and that tag lands inside the Python. Only a trailing line, or a suffix
    whose removal leaves a script that parses, is removed.
    """
    if not isinstance(code, str) or not code:
        return code, False
    low = code.lower()
    if '<parameter' not in low and '</parameter' not in low:
        return code, False
    lines = code.split('\n')
    changed = False
    while lines:
        raw = lines[-1]
        stripped = raw.strip()
        if not stripped:
            lines.pop()
            continue
        if _LEAKED_PARAM_TAG.match(stripped):
            lines.pop()
            changed = True
            continue
        match = _LEAKED_PARAM_TAG.search(raw)
        if match and match.start() > 0:
            prefix = raw[:match.start()].rstrip()
            candidate_lines = lines[:-1] + ([prefix] if prefix else [])
            candidate = '\n'.join(candidate_lines)
            try:
                ast.parse(candidate)
            except SyntaxError:
                break
            lines = candidate_lines
            changed = True
            continue
        break
    if not changed:
        return code, False
    repaired = '\n'.join(lines)
    if repaired and not repaired.endswith('\n'):
        repaired += '\n'
    return repaired, True
