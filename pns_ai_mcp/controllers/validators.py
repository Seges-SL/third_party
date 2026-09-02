# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""AST validation helpers for relaxaicode code."""

import ast
import copy
import re
import logging

_logger = logging.getLogger(__name__)

# Machine-plane AST tags. ASCII only. Repair / two-box inspect these codes,
# never translated narrative and never _(). Hint text is English msgid for the LLM.
AST_KIND_PROHIBITED = 'PROHIBITED'
AST_KIND_MANDATORY = 'MANDATORY'
AST_KIND_SYNTAX = 'SYNTAX'
_AST_TAG_RE = re.compile(
    r'^\[(?P<kind>PROHIBITED|MANDATORY|SYNTAX)(?::(?P<code>[A-Z][A-Z0-9_]*))?\]'
)
# Second-pass auto-repair may act on these codes (AST rewrite or syntax patch).
REPAIRABLE_AST_CODES = frozenset({
    'SYNTAX',
    'DIR',
    'LOCALS',
    'GLOBALS',
    'VARS',
    'RESULT',
    'SORT_KEY',
})
# Rejects that must NOT be followed by "generate valid Python" — wrong tool,
# not a syntax hole. The LLM must switch (get_context / api_call), not rewrite.
AST_SWITCH_TOOL_CODES = frozenset({
    'SORT_KEY',
    'CONTEXT_CATALOGUE',
    'API_CATALOGUE',
})


def format_ast_error(code, hint, kind=AST_KIND_PROHIBITED):
    """Stable tag + English hint. Control plane is the tag, not the prose."""
    if kind == AST_KIND_SYNTAX or not code:
        return '[%s] %s' % (kind, hint)
    return '[%s:%s] %s' % (kind, code, hint)


def ast_error_code(message):
    """ASCII code from an AST error hint (DIR, SYNTAX, …). None if untagged."""
    if not message or not isinstance(message, str):
        return None
    match = _AST_TAG_RE.match(message.lstrip())
    if not match:
        return None
    if match.group('kind') == AST_KIND_SYNTAX:
        return 'SYNTAX'
    return match.group('code')

# Límites de defs en RelaxAICode (no números mágicos sueltos en el walker).
# Profundidad 1 = def a nivel de módulo; 2 = def dentro de otro def.
# El nesting es el límite de seguridad real (combinatoria / recursión estructural).
# El conteo total es solo backstop patológico: cada cuerpo ya se valida igual.
RELAXAICODE_MAX_FUNCTION_NESTING_DEPTH = 2
RELAXAICODE_MAX_FUNCTION_DEFS = 1000

# Imports de red/FS: mensaje único hacia el camino seguro (fetch_url).
RELAXAICODE_NETWORK_IMPORT_MODULES = frozenset({
    'requests', 'urllib', 'http', 'httplib', 'httpx', 'aiohttp',
    'socket', 'ftplib', 'os', 'sys', 'pathlib', 'subprocess',
})
RELAXAICODE_NETWORK_IMPORT_HINT = (
    "For external HTTP data use propose_safe_operations with op='fetch_url' "
    "(GET only; whitelisted domains auto-confirm). "
    "Do NOT import requests/urllib/http/os — they are blocked in RelaxAICode."
)

# Allow/deny de imports: un solo sitio para AST y guarded_import (runtime).
RELAXAICODE_DANGEROUS_MODULES = frozenset({
    'odoo',
    'os', 'sys', 'pathlib', 'shutil', 'tempfile',
    'socket', 'urllib', 'http', 'requests', 'ftplib',
    'subprocess', 'multiprocessing',
    'pickle', 'marshal', 'ctypes', 'importlib',
    'builtins', '__builtin__', '__builtins__',
})
RELAXAICODE_SAFE_MODULES = frozenset({
    'datetime', 'date', 'time',
    'collections', 'itertools', 'functools',
    'math', 'statistics', 'decimal',
    'json', 'base64', 'hashlib',
    're', 'string', 'operator',
    'csv', 'io', 'copy', 'uuid', 'random',
    'calendar', 'textwrap', 'unicodedata', 'platform',
    'zoneinfo',
})
# Imports perezosos CPython de módulos seguros (solo runtime; el LLM no los pide).
RELAXAICODE_SAFE_INTERNAL_MODULES = frozenset({
    '_strptime', '_datetime', '_decimal', '_json', '_csv', '_random',
    '_collections', '_collections_abc', '_functools', '_operator',
    '_string', '_sre', 'copyreg',
})

# ── Denylist ÚNICA de atributos peligrosos (la comparten el AST de aquí y el
# guarded_getattr de runtime en context_builder). Un solo sitio para no dejar
# huecos entre capas. Cubre:
#   · introspección de tipos / MRO  → llegar a object y sus __subclasses__
#   · globals/builtins/código        → builtins reales del proceso
#   · frames y tracebacks            → f_back.f_globals del frame LLAMANTE (RCE)
#   · reducción/serialización        → reconstrucción arbitraria de objetos
#   · cursor/registry de la BD       → SQL crudo, control de transacción
# NOTA: son de DOBLE guion o nombres de frame SIN guion (f_back, tb_frame…). Los
# atributos ORM de UN guion (_name, _fields, _cr… salvo cr/_cr) no entran aquí:
# _cr y cr sí, por ser vector de SQL crudo.
DANGEROUS_ATTR_NAMES = frozenset({
    # Introspección de tipos / MRO
    '__class__', '__bases__', '__base__', '__subclasses__', '__mro__',
    '__mro_entries__', '__init_subclass__', '__instancecheck__',
    '__subclasshook__',
    # Globals / builtins / código
    '__globals__', '__builtins__', '__dict__', '__code__', '__func__',
    '__self__', '__closure__', '__wrapped__', '__module__', '__name__',
    '__file__', '__qualname__', '__objclass__', '__loader__', '__spec__',
    # Descriptores / reducción / serialización (reconstrucción de objetos)
    '__get__', '__getattribute__', '__reduce__', '__reduce_ex__',
    '__setstate__', '__getstate__',
    # Frames y tracebacks → builtins reales del proceso (vector RCE clásico)
    '__traceback__', 'tb_frame', 'tb_next', 'tb_lasti',
    'f_back', 'f_globals', 'f_locals', 'f_builtins', 'f_code', 'f_trace',
    'gi_frame', 'gi_code', 'cr_frame', 'cr_code', 'ag_frame',
    # Cursor / registro de la BD (SQL crudo, transacciones)
    'cr', '_cr', 'pool', 'registry', '_registry',
})

# Nombres de string.Formatter cuyo get_field/vformat devuelven el OBJETO real
# (no su repr), permitiendo recorrer clases desde un format string sin usar '.'
# ni getattr. Se bloquean por NOMBRE (cubre string.Formatter() y `import string`).
DANGEROUS_FORMAT_NAMES = frozenset({
    'Formatter', 'get_field', 'vformat', 'convert_field', 'format_field',
    'get_value',
})

# Modelos de catálogo: RelaxAICode no los inspecciona por ORM.
#   ai.api.server — teatro F1IZ; fuente = bloque inyectado + usage_guide; llamadas = api_call.
#   ai.context    — packs ya inyectados / get_context; listar no es search+content XML.
RELAXAICODE_FORBIDDEN_API_SERVER_MODEL = 'ai.api.server'
RELAXAICODE_FORBIDDEN_CONTEXT_MODEL = 'ai.context'
RELAXAICODE_FORBIDDEN_CATALOGUE_MODELS = frozenset({
    RELAXAICODE_FORBIDDEN_API_SERVER_MODEL,
    RELAXAICODE_FORBIDDEN_CONTEXT_MODEL,
})

# Atributos ORM de catálogo/secreto/drivers de ai.api.server. RelaxAICode
# debe usar propose_safe_operations op=api_call — misma denylist en AST y runtime.
RELAXAICODE_FORBIDDEN_ORM_ATTRS = frozenset({
    '_get_driver',
    '_resolve_auth_token',
    'spec_json',
    'tools_json',
    'resources_json',
    'prompts_json',
    'auth_token',
    'config_json',
    'env_vars',
})

# ORM mutators accessed via getattr/attrgetter (literal .write caught elsewhere).
RELAXAICODE_ORM_WRITE_ATTRS = frozenset({
    'create', 'write', 'unlink', 'copy',
})

RELAXAICODE_EXTERNAL_API_METHODS = frozenset({
    '_get_driver',
    '_resolve_auth_token',
    'action_discover_tools',
    'action_discover_auth',
    'action_test_connection',
})

RELAXAICODE_DRIVER_METHODS = frozenset({
    'call',
    'discover',
})


def _ast_parent_map(tree):
    """Mapa hijo → padre para consultar ancestros (return dentro de def, etc.)."""
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _is_inside_function(node, parents):
    cur = node
    while cur in parents:
        cur = parents[cur]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return True
    return False


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
    """Reescribe `env.cr.dbname` (y variantes) → `dbname` preloaded.

    El cursor está prohibido en el sandbox; el nombre de BD ya está inyectado.
    No reescribe `env.cr` genérico (sigue bloqueado). Devuelve (código, cambió).
    """
    if not code or not isinstance(code, str):
        return code, False
    out = _CR_DBNAME_TERNARY.sub('dbname', code)
    out = _CR_DBNAME_GETATTR.sub('dbname', out)
    out = _CR_DBNAME_ATTR.sub('dbname', out)
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
        if not (isinstance(left, ast.Constant) and isinstance(left.value, str)):
            return node
        fixed = escape_stray_percent_in_format(left.value)
        if fixed == left.value:
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


def _network_import_error(module_name):
    return (
        "[PROHIBITED] Cannot import '%s'. %s"
        % (module_name, RELAXAICODE_NETWORK_IMPORT_HINT)
    )


def _unsafe_import_error(module_name):
    """Mensaje al rechazar un import fuera de la allowlist."""
    if module_name == 'inspect':
        return (
            "[PROHIBITED] Cannot import Python module 'inspect'. "
            "Read models via env['model'] and Model._fields / record fields (ORM)."
        )
    if module_name in RELAXAICODE_NETWORK_IMPORT_MODULES:
        return _network_import_error(module_name)
    return (
        "[PROHIBITED] Relaxaicode can only import SAFE modules. "
        "'%s' is not allowed. Allowed modules: %s"
        % (module_name, ', '.join(sorted(RELAXAICODE_SAFE_MODULES)))
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
            "Database name is the preloaded `dbname` (aliases db_name, database). "
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


def _is_name_env(node):
    """True when *node* is the sandbox/global Name ``env``."""
    return isinstance(node, ast.Name) and node.id == 'env'


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


def _external_api_bypass_error(method_name):
    return format_ast_error(
        'API_CATALOGUE',
        "RelaxAICode cannot access external API catalogue/secrets "
        "via ORM (%r). Use the injected catalogue and propose_safe_operations "
        "with op='api_call' — never read ai.api.server drivers or specs from code."
        % method_name,
    )


def _external_api_server_inspect_error():
    return format_ast_error(
        'API_CATALOGUE',
        "RelaxAICode cannot inspect ai.api.server "
        "(catalogue/config/spec). Do not retry with relaxaicode — "
        "use the injected catalogue and propose_safe_operations with "
        "op='api_call' (fix arguments if propose failed).",
    )


def _context_inspect_error():
    return format_ast_error(
        'CONTEXT_CATALOGUE',
        "RelaxAICode cannot inspect ai.context "
        "(knowledge catalogue). Do not retry with relaxaicode — "
        "list packs with get_context(context_name='contexts_index_core'); "
        "load one pack with get_context(context_name='<code>'). "
        "Always-on packs are already in the agent bundle; do not dump "
        "pack XML. Creating discovery rows is propose_safe_operations, "
        "not a sandbox search.",
    )


def catalogue_inspect_error(model):
    """LLM-facing reject text if *model* is a forbidden catalogue, else None."""
    if model == RELAXAICODE_FORBIDDEN_API_SERVER_MODEL:
        return _external_api_server_inspect_error()
    if model == RELAXAICODE_FORBIDDEN_CONTEXT_MODEL:
        return _context_inspect_error()
    return None


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
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Str):  # pragma: no cover - py<3.8 AST
        return node.s
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
    # Escritura por API de negocio (no pasan el filtro .write/.create/.unlink).
    side_effect_methods = frozenset({
        'confirm_by_user',
        'cancel_by_user',
        'execute_plan_now',
        'resolve_confirm_and_execute',
        'resolve_confirm',
        'resolve_execute',
        'action_confirm_and_execute',
        'action_execute_plan',
        'action_cancel',
        'cleanup_expired',
        'cleanup_stuck_state',
        'create_verification',
        'button_immediate_install',
        'button_immediate_upgrade',
        'button_immediate_uninstall',
    })

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
                and node.func.attr in ('attrgetter', 'itemgetter')
                and node.args
            ):
                attr = _ast_static_str(node.args[0])
                if attr in RELAXAICODE_ORM_WRITE_ATTRS:
                    return True

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            # getattr(obj, 'write') / getattr(obj, 'wr'+'ite')
            if node.func.id == 'getattr' and len(node.args) >= 2:
                attr = _ast_static_str(node.args[1])
                if attr in RELAXAICODE_ORM_WRITE_ATTRS:
                    return True
            # attrgetter('write') / itemgetter — only attrgetter matters for methods
            if node.func.id == 'attrgetter' and node.args:
                attr = _ast_static_str(node.args[0])
                if attr in RELAXAICODE_ORM_WRITE_ATTRS:
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


_SAFE_LAMBDA_CALL_NAMES = frozenset({
    'str', 'int', 'float', 'len', 'bool', 'abs', 'sum', 'max', 'min', 'round',
    'isinstance',
})
_SAFE_LAMBDA_METHODS = frozenset({
    'lower', 'upper', 'strip', 'lstrip', 'rstrip', 'get', 'replace', 'index',
    'casefold', 'startswith', 'endswith', 'isdigit', 'isnumeric', 'isalpha',
    'find', 'rfind', 'zfill', 'join', 'strptime', 'strftime',
    'split', 'rsplit', 'partition', 'rpartition',
})
_SAFE_BUILTIN_SORT_KEYS = frozenset({'str', 'int', 'len', 'float', 'abs', 'bool'})


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
    if isinstance(node, (ast.Constant, ast.NameConstant)):
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


def validate_relaxaicode_source_ast(code):
    """
    Valida código Python usando AST completo.
    Detecta imports peligrosos, funciones peligrosas, y código dinámico.
    
    Returns:
        tuple: (is_valid, error_message, requires_write)
            - is_valid: True si el código es válido
            - error_message: Mensaje de error si no es válido, None si es válido
            - requires_write: True si el código requiere permisos de escritura
    """
    # CRÍTICO: Validar que code sea string
    if not isinstance(code, str):
        return False, f"Invalid code type: expected string, got {type(code).__name__}. Code must be a Python string.", False
    
    if not code or not code.strip():
        return False, "Code is empty or contains only whitespace", False
    
    try:
        # Parsear código a AST
        tree = ast.parse(code, '<relaxaicode>', 'exec')
    except SyntaxError as e:
        # Proporcionar mensaje de error más descriptivo
        error_msg = str(e)
        error_line = getattr(e, 'lineno', None)
        error_offset = getattr(e, 'offset', None)
        
        # Si hay información de línea, incluirla en el mensaje
        if error_line:
            # Obtener la línea problemática para contexto
            lines = code.split('\n')
            if error_line <= len(lines):
                problem_line = lines[error_line - 1]
                # Truncar si es muy larga
                if len(problem_line) > 100:
                    problem_line = problem_line[:97] + '...'
                error_msg = f"Syntax error at line {error_line}: {error_msg}\nProblematic line: {problem_line}"
            else:
                error_msg = f"Syntax error at line {error_line}: {error_msg}"
        
        return False, format_ast_error(
            None, 'Syntax error: %s' % error_msg, kind=AST_KIND_SYNTAX,
        ), False
    except Exception as e:
        return False, format_ast_error(
            None, 'Failed to parse code: %s' % e, kind=AST_KIND_SYNTAX,
        ), False

    safe_sort_key_refs = _collect_safe_sort_key_refs(tree)
    parents = _ast_parent_map(tree)

    nest_ok, nest_err = _check_function_def_limits(tree)
    if not nest_ok:
        return False, nest_err, False

    env_ok, env_err = _check_env_parameter_binding(tree)
    if not env_ok:
        return False, env_err, False

    dangerous_modules = RELAXAICODE_DANGEROUS_MODULES
    safe_modules = RELAXAICODE_SAFE_MODULES

    # Funciones peligrosas completamente prohibidas
    dangerous_functions = {
        'open', 'eval', 'exec', 'compile', '__import__',
        'input', 'raw_input', 'file',
    }

    # Atributos peligrosos: denylist ÚNICA (DANGEROUS_ATTR_NAMES) compartida
    # con guarded_getattr de runtime.
    dangerous_attrs = DANGEROUS_ATTR_NAMES

    # Variables peligrosas completamente prohibidas
    dangerous_vars = {
        'locals', 'globals', 'vars', 'dir',
    }
    
    # Analizar AST completo
    for node in ast.walk(tree):
        # ============================================================
        # VALIDAR IMPORTS DIRECTOS
        # ============================================================
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split('.')[0]  # Solo el primer nivel
                
                # Bloquear módulos peligrosos
                if module_name in dangerous_modules:
                    if module_name == 'odoo':
                        return False, (
                            "[SyntaxError] DO NOT use 'import odoo'. Use global variables directly: "
                            "odoo_version (str), odoo_series (str), env (Odoo Environment). "
                            "Example: result = {'version': odoo_version}"
                        ), False
                    if module_name in RELAXAICODE_NETWORK_IMPORT_MODULES:
                        return False, _network_import_error(module_name), False
                    return False, (
                        f"[SyntaxError] Cannot import '{module_name}'. "
                        "Access models with env['model'] or use available global variables."
                    ), False

                if module_name not in safe_modules:
                    return False, _unsafe_import_error(module_name), False

        # ============================================================
        # VALIDAR IMPORTS FROM
        # ============================================================
        if isinstance(node, ast.ImportFrom):
            if node.module:
                # urllib.parse: funciones puras de texto (quote, urlencode, urlparse,
                # parse_qs, urljoin...) para COMPONER/TROCEAR URLs. No tiene red ni FS.
                # Se permite SOLO la forma `from urllib.parse import <nombre>`, que liga
                # las funciones y nunca el paquete `urllib` (por el que se alcanzaría
                # urllib.request). `import urllib.parse` sigue prohibido (ver ast.Import).
                if node.module == 'urllib.parse':
                    continue

                module_name = node.module.split('.')[0]  # Solo el primer nivel

                # Bloquear módulos peligrosos
                if module_name in dangerous_modules:
                    if module_name in RELAXAICODE_NETWORK_IMPORT_MODULES:
                        return False, _network_import_error(module_name), False
                    return False, (
                        f"[PROHIBITED] Relaxaicode cannot import from '{module_name}' or any of its submodules. "
                        "Use available global variables (env, odoo_version) or access models via env['model']."
                    ), False

                if module_name not in safe_modules:
                    return False, _unsafe_import_error(module_name), False

        # ============================================================
        # VALIDAR LLAMADAS A FUNCIONES PELIGROSAS
        # ============================================================
        if isinstance(node, ast.Call):
            # Llamadas directas: open(), eval(), exec(), print(), etc.
            if isinstance(node.func, ast.Name):
                if node.func.id in dangerous_functions:
                    if node.func.id in ('eval', 'exec', 'compile'):
                        return False, (
                            f"[PROHIBITED] Cannot use '{node.func.id}()'. "
                            "Never probe helpers with eval/exec. "
                            "[MANDATORY] Preloaded helpers (if a module published them) "
                            "are called directly. To test if a name exists: "
                            "try: _ = name\\nexcept NameError: … — never eval('name')."
                        ), False
                    return False, (
                        f"[PROHIBITED] Cannot use '{node.func.id}()'. "
                        "This function is prohibited for security."
                    ), False
            
            # Llamadas a métodos: obj.open(), obj.eval(), etc.
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in dangerous_functions:
                    return False, (
                        f"[PROHIBITED] Relaxaicode cannot use method '.{node.func.attr}()'. "
                        "This method is prohibited for security reasons."
                    ), False
                # Métodos de cursor/transacción: SQL crudo y control de transacción quedan
                # fuera de la caja A. Las escrituras se hacen SOLO vía la caja B (verbos ORM).
                dangerous_cursor_methods = {
                    'execute', 'executemany', 'commit', 'rollback', 'savepoint',
                    'dictfetchall', 'dictfetchone',
                }
                if node.func.attr in dangerous_cursor_methods:
                    return False, (
                        f"[PROHIBITED] Relaxaicode cannot use '.{node.func.attr}()' (raw SQL / "
                        "transaction control). Use the ORM (env['model']) for reads; writes go "
                        "through confirmed write operations, never raw SQL."
                    ), False
            
            # Bloquear __import__() dinámico
            if isinstance(node.func, ast.Name) and node.func.id == '__import__':
                return False, (
                    "[PROHIBITED] Relaxaicode cannot use '__import__()' dynamically. "
                    "Imports must be static/direct (import module or from module import)."
                ), False

            # Bloquear type(name, bases, dict): crea CLASES dinámicamente, saltándose
            # la prohibición de 'class'. Se preserva type(x) de 1 argumento (chequeo
            # de tipo, uso legítimo). 3 args = metaclase → fuera de la caja A.
            if isinstance(node.func, ast.Name) and node.func.id == 'type' and len(node.args) == 3:
                return False, (
                    "[PROHIBITED] Relaxaicode cannot use 'type(name, bases, dict)' to create "
                    "classes dynamically. Only type(x) for type checks is allowed."
                ), False
        
        # ============================================================
        # VALIDAR RETURN: solo dentro de def (el script sigue usando result=)
        # ============================================================
        if isinstance(node, ast.Return):
            if not _is_inside_function(node, parents):
                return False, (
                    "[PROHIBITED] DO NOT use 'return' at module level. "
                    "Code executes as a script (NOT a function). "
                    "[MANDATORY] Assign output to variable 'result'. "
                    "Example: result = {'odoo_version': odoo_version}. "
                    "'return' is only allowed inside a def helper."
                ), False

        # ============================================================
        # VALIDAR PATRONES INCORRECTOS COMUNES (self.env, context.get, etc.)
        # ============================================================
        # Detectar self.env (patrón de métodos de Odoo, NO existe en relaxaicode)
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == 'self' and node.attr == 'env':
                return False, (
                    "[PROHIBITED] DO NOT use 'self.env'. Code executes directly (NOT a method, no 'self'). "
                    "[MANDATORY] Use 'env' directly as a global variable. "
                    "Correct: partners = env['res.partner'].search([]). "
                    "Wrong: partners = self.env['res.partner'].search([])"
                ), False
        
        # Detectar context.get('env') o context['env'] (patrón de wizards, NO existe en relaxaicode)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == 'context':
                    if node.func.attr == 'get':
                        # Verificar si está buscando 'env' (compatible con Python 3.8+ y anteriores)
                        if node.args:
                            first_arg = node.args[0]
                            arg_value = None
                            if isinstance(first_arg, ast.Constant):  # Python 3.8+
                                arg_value = first_arg.value
                            elif isinstance(first_arg, ast.Str):  # Python < 3.8
                                arg_value = first_arg.s
                            
                            if arg_value == 'env':
                                return False, (
                                    "[PROHIBITED] DO NOT use 'context.get('env')'. Variable 'context' does NOT exist. "
                                    "[MANDATORY] Use 'env' directly as a global variable. "
                                    "Correct: partners = env['res.partner'].search([]). "
                                    "Wrong: env = context.get('env'); partners = env['res.partner'].search([])"
                                ), False
                    elif node.func.attr in ('get', '__getitem__'):
                        return False, (
                            "[PROHIBITED] DO NOT use 'context.get()' or 'context[]'. Variable 'context' does NOT exist. "
                            "[MANDATORY] Variables are available directly: env, odoo_version, odoo_series. "
                            "Example: result = {'odoo_version': odoo_version}"
                        ), False
        
        # Detectar acceso a context['env'] o context.get('env')
        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name) and node.value.id == 'context':
                return False, (
                    "[PROHIBITED] DO NOT use 'context['env']' or 'context['variable']'. Variable 'context' does NOT exist. "
                    "[MANDATORY] Variables are available directly: env, odoo_version, odoo_series. "
                    "Example: result = {'odoo_version': odoo_version}"
                ), False
        
        # ============================================================
        # VALIDAR ACCESO A ATRIBUTOS PELIGROSOS
        # ============================================================
        if isinstance(node, ast.Attribute):
            if node.attr in RELAXAICODE_FORBIDDEN_ORM_ATTRS:
                return False, _external_api_bypass_error(node.attr), False
            if node.attr in dangerous_attrs:
                # type(x).__name__ → string label; no abre introspección de sandbox.
                if not _is_safe_type_name_access(node):
                    return False, _dangerous_attr_error(node.attr), False
            # string.Formatter().get_field(...) / .vformat(...) devuelven el OBJETO
            # real (no su repr) → traversal de clases sin '.' ni getattr. Se bloquea
            # por nombre, cubriendo tanto `string.Formatter` como `import string`.
            if node.attr in DANGEROUS_FORMAT_NAMES:
                return False, format_ast_error(
                    'FORMATTER',
                    "Relaxaicode cannot use '%s' (string.Formatter). "
                    "It returns internal objects and allows sandbox escape."
                    % node.attr,
                ), False
        
        # ============================================================
        # VALIDAR USO DE VARIABLES PELIGROSAS
        # ============================================================
        if isinstance(node, ast.Name):
            if node.id in dangerous_vars:
                # Verificar si se está usando como llamada a función
                # Buscar en el árbol si este Name está dentro de un Call
                # Como ast.walk no mantiene relaciones padre-hijo, verificamos
                # si hay un Call cercano que use esta variable
                # La mejor forma es verificar el contexto: si es Load y está en un Call
                if isinstance(node.ctx, ast.Load):
                    # Sin mapa padre aquí: cualquier Load de estas builtins se bloquea.
                    return False, _dangerous_name_error(node.id), False
        
        # ============================================================
        # VALIDAR ACCESO A __BUILTINS__ DIRECTAMENTE
        # ============================================================
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == '__builtins__':
                return False, format_ast_error(
                    'BUILTINS',
                    "Relaxaicode cannot access '__builtins__' directly. "
                    "This is blocked for security.",
                ), False
        
        # ============================================================
        # VALIDAR getattr()/setattr()/delattr() CON ATRIBUTOS PELIGROSOS (literal)
        # OJO: esto sólo cubre nombres LITERALES. El nombre construido dinámicamente
        # (p.ej. getattr(x, '__cla'+'ss__')) lo bloquea el guarded_getattr de runtime
        # en context_builder, que evalúa el nombre real contra la MISMA denylist.
        # ============================================================
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ('getattr', 'setattr', 'delattr'):
                if len(node.args) >= 2:
                    # Segundo argumento string literal (Py3.8+: Constant; <3.8: Str)
                    attr_name = None
                    if isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                        attr_name = node.args[1].value
                    elif isinstance(node.args[1], ast.Str):
                        attr_name = node.args[1].s
                    if attr_name is not None:
                        if attr_name in RELAXAICODE_FORBIDDEN_ORM_ATTRS:
                            return False, _external_api_bypass_error(attr_name), False
                        if attr_name in dangerous_attrs:
                            return False, format_ast_error(
                                'DUNDER',
                                "Relaxaicode cannot use %s() to access '%s'. "
                                "This attribute is blocked for security."
                                % (node.func.id, attr_name),
                            ), False

        # ============================================================
        # VALIDAR FORMAT-STRINGS CON ACCESO A DUNDER: "{0.__class__}".format(x)
        # str.format resuelve la cadena de atributos sobre el objeto REAL antes de
        # formatear. Aunque devuelva su repr (no el objeto), es fuga de introspección
        # y puede encadenarse. Se bloquea SOLO si el literal accede a un dunder
        # ({...__x__...}); se preserva el uso normal ({0}, {name}, {0.name}).
        # ============================================================
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ('format', 'format_map'):
                fmt_str = None
                if isinstance(node.func.value, ast.Constant) and isinstance(node.func.value.value, str):
                    fmt_str = node.func.value.value
                elif isinstance(node.func.value, ast.Str):
                    fmt_str = node.func.value.s
                if fmt_str and re.search(r'\{[^{}]*__[A-Za-z0-9_]*__', fmt_str):
                    return False, format_ast_error(
                        'FORMAT',
                        "Relaxaicode cannot use .format() with dunder attribute "
                        "access ('__...__') in the template. Blocked for security.",
                    ), False
        
        # ============================================================
        # VALIDAR CONSTRUCCIONES: lambda segura; class prohibida.
        # def/async def: permitidos (límites arriba); el cuerpo se valida
        # en este mismo walk (open/eval/cr/imports…).
        # ============================================================
        if isinstance(node, ast.Lambda):
            if not _is_safe_lambda(node, extra_call_names=safe_sort_key_refs):
                return False, _SAFE_LAMBDA_MSG, False

        if isinstance(node, ast.ClassDef):
            return False, (
                "[PROHIBITED] Relaxaicode does NOT allow defining classes. "
                "Use plain dicts/lists and optional def helpers instead."
            ), False

        # ============================================================
        # VALIDAR SORT/SORTED/MIN/MAX CON KEY ARGUMENT
        # ============================================================
        if isinstance(node, ast.Call):
            is_sort_call = False
            if isinstance(node.func, ast.Name) and node.func.id in ('sorted', 'min', 'max'):
                is_sort_call = True
            elif isinstance(node.func, ast.Attribute) and node.func.attr in ('sort', 'sorted'):
                is_sort_call = True
            
            if is_sort_call:
                for keyword in node.keywords:
                    if keyword.arg == 'key':
                        kv = keyword.value
                        if isinstance(kv, ast.Lambda) and not _is_safe_lambda(
                            kv, extra_call_names=safe_sort_key_refs,
                        ):
                            return False, _SAFE_LAMBDA_MSG, False
                        if not _is_safe_sort_key_value(kv, safe_sort_key_refs):
                            return False, _SAFE_LAMBDA_MSG, False
    # ============================================================
    # VALIDAR ASIGNACIÓN REAL A 'result'
    # ============================================================
    assign_ok, assign_err = _validate_result_assignment(tree)
    if not assign_ok:
        return False, assign_err, False
    
    # ============================================================
    # BLOQUEAR BYPASS DE API EXTERNA VÍA ORM (Caja A → red sin Safe Plan)
    # ============================================================
    bypass_err = _detect_external_api_bypass_from_ast(tree)
    if bypass_err:
        return False, bypass_err, False

    # ============================================================
    # DETECTAR OPERACIONES DE ESCRITURA (AST, sin falsos positivos)
    # ============================================================
    requires_write = _detect_requires_write_from_ast(tree)
    
    # ============================================================
    # VALIDAR QUE NO SE REDEFINAN MÓDULOS PERMITIDOS
    # ============================================================
    shadow_pattern = r'^\s*(json|datetime|math|statistics|re|string)\s*='
    if re.search(shadow_pattern, code, flags=re.MULTILINE):
        return False, (
            "No redefinas módulos permitidos (json, datetime, math, statistics, re, string). "
            "Usa otro nombre de variable (por ejemplo, json_data)."
        ), False
    
    return True, None, requires_write


def detect_dangerous_operations(code):
    """
    Detecta operaciones peligrosas en código relaxaicode que requieren verificación.
    Usa análisis AST para detectar operaciones de escritura y contar registros.
    
    Returns:
        tuple: (requires_verification, operation_info)
            - requires_verification: True si requiere verificación
            - operation_info: dict con información de la operación peligrosa
    """
    operation_info = {
        'operation_type': None,
        'model_name': None,
        'records_count': None,
        'is_massive': False,
    }
    requires_verification = False
    
    try:
        # Parsear código a AST
        tree = ast.parse(code)
        
        # Visitor para detectar operaciones de escritura y bucles
        class WriteOperationVisitor(ast.NodeVisitor):
            def __init__(self, ast_tree):
                self.write_operations = []
                self.model_names = set()
                self.loop_contexts = []  # Pila de contextos de bucles (para detectar bucles anidados)
                self.ast_tree = ast_tree  # Guardar referencia al árbol AST completo
                self.list_variables = {}  # Cache de longitudes de listas encontradas
                self.variable_models = {}  # Rastrear modelo de cada variable (ej: {'existing_filter': 'ir.filters'})
            
            def visit_Assign(self, node):
                # Rastrear asignaciones para detectar modelos de variables
                # Ejemplo: existing_filter = env['ir.filters'].search(...)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        var_name = target.id
                        # Analizar el valor asignado
                        if isinstance(node.value, ast.Call):
                            # Llamada a método (search, browse, create, etc.)
                            if isinstance(node.value.func, ast.Attribute):
                                # Obtener el modelo si es env['modelo'].method(...)
                                if isinstance(node.value.func.value, ast.Subscript):
                                    if isinstance(node.value.func.value.value, ast.Name) and node.value.func.value.value.id == 'env':
                                        if isinstance(node.value.func.value.slice, ast.Constant):
                                            model_name = node.value.func.value.slice.value
                                            self.variable_models[var_name] = model_name
                                            self.model_names.add(model_name)
                                            _logger.debug(f"MCP: AST - Variable '{var_name}' asignada a modelo '{model_name}'")
                        elif isinstance(node.value.func.value.slice, ast.Str):  # Python < 3.8
                            model_name = node.value.func.value.slice.s
                            self.variable_models[var_name] = model_name
                            self.model_names.add(model_name)
                            _logger.debug(f"MCP: AST - Variable '{var_name}' asignada a modelo '{model_name}'")

                # Asignación por ATRIBUTO = escritura ORM encubierta: rec.campo = valor
                # (sin pasar por .write()). Solo se marca cuando la base es claramente un
                # recordset (variable rastreada como modelo, o env['modelo']) para evitar
                # falsos positivos en objetos no-ORM (dicts/clases locales). Cierra el
                # vector por el que la IA podría escribir o autoconfirmarse sin verificación.
                for target in node.targets:
                    if isinstance(target, ast.Attribute):
                        base = target.value
                        attr_model = None
                        is_orm_base = False
                        if isinstance(base, ast.Name) and base.id in self.variable_models:
                            attr_model = self.variable_models[base.id]
                            is_orm_base = True
                        elif isinstance(base, ast.Subscript) and isinstance(base.value, ast.Name) and base.value.id == 'env':
                            is_orm_base = True
                            if isinstance(base.slice, ast.Constant):
                                attr_model = base.slice.value
                            elif isinstance(base.slice, ast.Str):  # Python < 3.8
                                attr_model = base.slice.s
                        if is_orm_base:
                            self.write_operations.append({
                                'method': 'write',
                                'model_name': attr_model,
                                'records_count': None,
                                'is_massive': True,
                                'node': node,
                                'in_loop': len(self.loop_contexts) > 0,
                                'operator': '=attr',
                            })
                            if attr_model:
                                self.model_names.add(attr_model)

                # Continuar visitando otros nodos
                self.generic_visit(node)
            
            def visit_AugAssign(self, node):
                # Detectar operadores de asignación in-place: |=, +=, -=
                # Estos operadores modifican campos relacionales (Many2many, One2many) en Odoo
                if isinstance(node.op, (ast.BitOr, ast.Add, ast.Sub)):
                    # Verificar si el target es un atributo (campo relacional)
                    if isinstance(node.target, ast.Attribute):
                        # Es una operación de escritura en un campo relacional
                        # Ejemplo: antonio.groups_id |= groups
                        method_name = 'write'  # |=, +=, -= son operaciones de escritura
                        model_name = None
                        
                        # Intentar extraer el modelo del atributo
                        # Si es user.groups_id, el modelo es res.users
                        if isinstance(node.target.value, ast.Name):
                            # Variable (ej: antonio, user, etc.)
                            # No podemos determinar el modelo directamente, pero sabemos que es escritura
                            pass
                        
                        # Detectar número de registros afectados
                        records_count = None
                        is_massive = False
                        
                        # Si el valor es una lista o recordset, contar elementos
                        if isinstance(node.value, ast.List):
                            records_count = len(node.value.elts)
                            is_massive = records_count > 1
                        elif isinstance(node.value, ast.Name):
                            # Variable - buscar en cache de listas
                            var_name = node.value.id
                            if var_name in self.list_variables:
                                records_count = self.list_variables[var_name]
                                is_massive = records_count > 1
                            else:
                                # No se puede determinar, marcar como masivo
                                records_count = None
                                is_massive = True
                        elif isinstance(node.value, ast.Call):
                            # Llamada a función (ej: env['res.groups'].browse(...))
                            # No se puede determinar con certeza, marcar como masivo
                            records_count = None
                            is_massive = True
                        else:
                            # Otro tipo de expresión, asumir masivo
                            records_count = None
                            is_massive = True
                        
                        # Si estamos dentro de un bucle, multiplicar
                        loop_multiplier = 1
                        if self.loop_contexts:
                            current_loop = self.loop_contexts[-1]
                            loop_count = current_loop['count']
                            if isinstance(loop_count, int):
                                loop_multiplier = loop_count
                            elif isinstance(loop_count, str) and loop_count.startswith('len('):
                                var_name = loop_count[4:-1]
                                if var_name in self.list_variables:
                                    loop_multiplier = self.list_variables[var_name]
                                else:
                                    loop_multiplier = None
                                    is_massive = True
                        
                        if loop_multiplier is not None and records_count is not None:
                            records_count = records_count * loop_multiplier
                            is_massive = records_count > 1
                        elif loop_multiplier is None or records_count is None:
                            records_count = None
                            is_massive = True
                        
                        self.write_operations.append({
                            'method': method_name,
                            'model_name': model_name,
                            'records_count': records_count,
                            'is_massive': is_massive,
                            'node': node,
                            'in_loop': len(self.loop_contexts) > 0,
                            'operator': '|=' if isinstance(node.op, ast.BitOr) else '+=' if isinstance(node.op, ast.Add) else '-='
                        })
                
                # Continuar visitando otros nodos
                self.generic_visit(node)
            
            def visit_While(self, node):
                # Detectar bucles while que pueden contener operaciones de escritura
                # Intentar determinar cuántas iteraciones tendrá el bucle
                loop_count = None
                
                # Patrón: while i < len(lista)
                if isinstance(node.test, ast.Compare):
                    if len(node.test.ops) == 1 and isinstance(node.test.ops[0], (ast.Lt, ast.LtE)):
                        # Comparación con < o <=
                        if isinstance(node.test.left, ast.Name):
                            # Variable de índice (i, j, etc.)
                            if isinstance(node.test.comparators[0], ast.Call):
                                # len(lista)
                                len_call = node.test.comparators[0]
                                if isinstance(len_call.func, ast.Name) and len_call.func.id == 'len':
                                    if len_call.args and isinstance(len_call.args[0], ast.Name):
                                        # len(variable) - buscar la variable en el código
                                        list_var_name = len_call.args[0].id
                                        # Buscar la definición de esta variable en el código
                                        # Por ahora, marcamos que hay un bucle con una lista
                                        loop_count = f"len({list_var_name})"  # Marcador especial
                                    elif len_call.args and isinstance(len_call.args[0], ast.List):
                                        # len([...]) - lista literal
                                        loop_count = len(len_call.args[0].elts)
                
                # Añadir contexto de bucle
                self.loop_contexts.append({
                    'type': 'while',
                    'count': loop_count,
                    'node': node
                })
                
                # Visitar el cuerpo del bucle
                self.generic_visit(node)
                
                # Remover contexto de bucle
                self.loop_contexts.pop()
            
            def visit_For(self, node):
                # Detectar bucles for que pueden contener operaciones de escritura
                loop_count = None
                
                # Patrón: for item in lista
                if isinstance(node.iter, ast.Name):
                    # for x in variable - buscar la variable
                    list_var_name = node.iter.id
                    loop_count = f"len({list_var_name})"  # Marcador especial
                elif isinstance(node.iter, ast.List):
                    # for x in [...] - lista literal
                    loop_count = len(node.iter.elts)
                elif isinstance(node.iter, ast.Call):
                    # for x in search(...) - búsqueda de Odoo
                    if isinstance(node.iter.func, ast.Attribute) and node.iter.func.attr == 'search':
                        # Buscar limit en los argumentos
                        for keyword in node.iter.keywords:
                            if keyword.arg == 'limit':
                                if isinstance(keyword.value, ast.Constant):
                                    loop_count = keyword.value.value
                                elif isinstance(keyword.value, ast.Num):  # Python < 3.8
                                    loop_count = keyword.value.n
                                break
                        if loop_count is None:
                            loop_count = None  # Sin limit, no se puede determinar
                
                # Añadir contexto de bucle
                self.loop_contexts.append({
                    'type': 'for',
                    'count': loop_count,
                    'node': node
                })
                
                # Visitar el cuerpo del bucle
                self.generic_visit(node)
                
                # Remover contexto de bucle
                self.loop_contexts.pop()
            
            def visit_Call(self, node):
                # Detectar llamadas a métodos de escritura
                if isinstance(node.func, ast.Attribute):
                    method_name = node.func.attr
                    
                    if method_name in ('create', 'write', 'unlink', 'copy'):
                        # Obtener modelo si es posible
                        model_name = None
                        if isinstance(node.func.value, ast.Subscript):
                            # env['modelo'].create(...)
                            if isinstance(node.func.value.value, ast.Name) and node.func.value.value.id == 'env':
                                if isinstance(node.func.value.slice, ast.Constant):
                                    model_name = node.func.value.slice.value
                                elif isinstance(node.func.value.slice, ast.Str):  # Python < 3.8
                                    model_name = node.func.value.slice.s
                        elif isinstance(node.func.value, ast.Name):
                            # variable.write(...) - buscar modelo en variable_models
                            var_name = node.func.value.id
                            if var_name in self.variable_models:
                                model_name = self.variable_models[var_name]
                                _logger.debug(f"MCP: AST - Modelo detectado desde variable '{var_name}': {model_name}")
                        
                        # Detectar tipo de operación y contar registros
                        records_count = None
                        is_massive = False
                        
                        # Si estamos dentro de un bucle, multiplicar por el número de iteraciones
                        loop_multiplier = 1
                        if self.loop_contexts:
                            # Estamos dentro de un bucle
                            current_loop = self.loop_contexts[-1]
                            loop_count = current_loop['count']
                            
                            if isinstance(loop_count, int):
                                # Número exacto de iteraciones
                                loop_multiplier = loop_count
                            elif isinstance(loop_count, str) and loop_count.startswith('len('):
                                # len(variable) - necesitamos buscar la variable en el código
                                # Extraer nombre de variable de "len(variable_name)"
                                var_name = loop_count[4:-1]  # Quitar "len(" y ")"
                                _logger.debug(f"MCP: AST - Buscando longitud de lista '{var_name}' en cache: {self.list_variables}")
                                # Buscar en cache primero
                                if var_name in self.list_variables:
                                    list_length = self.list_variables[var_name]
                                    _logger.debug(f"MCP: AST - Encontrada en cache: {list_length}")
                                else:
                                    # Buscar la definición de esta variable en el árbol AST
                                    list_length = self.find_list_variable_length(var_name, self.ast_tree)
                                    # Guardar en cache
                                    self.list_variables[var_name] = list_length
                                    _logger.debug(f"MCP: AST - Buscada en AST: {list_length}")
                                
                                if list_length is not None:
                                    loop_multiplier = list_length
                                    _logger.debug(f"MCP: AST - Loop multiplier establecido a: {loop_multiplier}")
                                else:
                                    # No se pudo determinar, marcar como masivo
                                    loop_multiplier = None
                                    _logger.debug(f"MCP: AST - No se pudo determinar longitud, marcando como masivo")
                        
                        if method_name == 'create':
                            # Analizar argumentos de create
                            if node.args and isinstance(node.args[0], ast.List):
                                # create([{...}, {...}]) - lista de diccionarios
                                base_count = len(node.args[0].elts)
                                if loop_multiplier is None:
                                    records_count = None
                                    is_massive = True
                                else:
                                    records_count = base_count * loop_multiplier
                                    is_massive = records_count > 1
                            elif node.args and isinstance(node.args[0], ast.Dict):
                                # create({...}) - un solo diccionario
                                if loop_multiplier is None:
                                    records_count = None
                                    is_massive = True
                                else:
                                    records_count = 1 * loop_multiplier
                                    is_massive = records_count > 1
                            else:
                                # create con variable o expresión compleja
                                if loop_multiplier is None:
                                    records_count = None
                                else:
                                    records_count = loop_multiplier
                                is_massive = True  # Asumir masivo si no se puede determinar
                        
                        elif method_name == 'write':
                            # write() puede ser masivo si se llama sobre un recordset sin limit
                            # Verificar si viene de un search sin limit
                            if isinstance(node.func.value, ast.Call):
                                # .search(...).write(...)
                                search_call = node.func.value
                                if isinstance(search_call.func, ast.Attribute) and search_call.func.attr == 'search':
                                    # Buscar limit en los argumentos de search
                                    has_limit = False
                                    limit_value = None
                                    for keyword in search_call.keywords:
                                        if keyword.arg == 'limit':
                                            has_limit = True
                                            if isinstance(keyword.value, ast.Constant):
                                                limit_value = keyword.value.value
                                            elif isinstance(keyword.value, ast.Num):  # Python < 3.8
                                                limit_value = keyword.value.n
                                            break
                                    
                                    if has_limit and limit_value == 1:
                                        records_count = 1 * (loop_multiplier if loop_multiplier is not None else 1)
                                    else:
                                        # Sin limit o limit > 1, asumir masivo
                                        if loop_multiplier is None:
                                            records_count = None
                                        else:
                                            records_count = (limit_value if has_limit else None) or loop_multiplier
                                        is_massive = True
                                else:
                                    # write() sobre algo que no es search
                                    if loop_multiplier is None:
                                        records_count = None
                                        is_massive = True
                                    else:
                                        records_count = 1 * loop_multiplier
                                        is_massive = records_count > 1
                            elif isinstance(node.func.value, ast.Name):
                                # variable.write() - verificar si la variable viene de un search con limit=1
                                var_name = node.func.value.id
                                # Si encontramos el modelo, asumir que es un solo registro (típico en updates)
                                # Esto es una heurística: si se hace variable.write(), normalmente es un solo registro
                                records_count = 1 * (loop_multiplier if loop_multiplier is not None else 1)
                                is_massive = records_count > 1
                            else:
                                # write() directo sobre otro tipo de expresión
                                if loop_multiplier is None:
                                    records_count = None
                                    is_massive = True
                                else:
                                    records_count = 1 * loop_multiplier
                                    is_massive = records_count > 1
                        
                        elif method_name == 'unlink':
                            # unlink() siempre requiere verificación
                            if loop_multiplier is None:
                                records_count = None
                                is_massive = True
                            else:
                                records_count = 1 * loop_multiplier
                                is_massive = records_count > 1
                        
                        elif method_name == 'copy':
                            # copy() crea nuevos registros, es una operación de escritura
                            # copy() normalmente se llama sobre un solo registro, pero puede estar en un bucle
                            if loop_multiplier is None:
                                records_count = None
                                is_massive = True
                            else:
                                records_count = 1 * loop_multiplier
                                is_massive = records_count > 1
                        
                        self.write_operations.append({
                            'method': method_name,
                            'model_name': model_name,
                            'records_count': records_count,
                            'is_massive': is_massive,
                            'node': node,
                            'in_loop': len(self.loop_contexts) > 0
                        })
                        
                        if model_name:
                            self.model_names.add(model_name)
                
                # Continuar visitando otros nodos
                self.generic_visit(node)
            
            def find_list_variable_length(self, var_name, tree):
                """Busca la definición de una variable y cuenta elementos si es una lista"""
                class ListFinder(ast.NodeVisitor):
                    def __init__(self, target_var):
                        self.target_var = target_var
                        self.found_length = None
                    
                    def visit_Assign(self, node):
                        # Buscar asignaciones a la variable objetivo
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id == self.target_var:
                                # Encontramos la asignación
                                if isinstance(node.value, ast.List):
                                    # Es una lista literal
                                    self.found_length = len(node.value.elts)
                                # También podríamos buscar otros patrones aquí
                
                finder = ListFinder(var_name)
                finder.visit(tree)
                return finder.found_length
        
        # Primero, buscar todas las listas definidas en el código para tenerlas en cache
        class ListVariableFinder(ast.NodeVisitor):
            def __init__(self):
                self.list_vars = {}
            
            def visit_Assign(self, node):
                # Buscar asignaciones de listas
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        var_name = target.id
                        if isinstance(node.value, ast.List):
                            # Es una lista literal
                            self.list_vars[var_name] = len(node.value.elts)
                            _logger.debug(f"MCP: AST - Encontrada lista '{var_name}' con {len(node.value.elts)} elementos")
        
        list_finder = ListVariableFinder()
        list_finder.visit(tree)
        
        # Analizar código con el visitor (pasar el árbol y el cache de listas)
        visitor = WriteOperationVisitor(tree)
        visitor.list_variables = list_finder.list_vars.copy()  # Pasar el cache de listas (copia)
        _logger.debug(f"MCP: AST - Cache de listas: {visitor.list_variables}")
        visitor.visit(tree)
        
        # Si hay operaciones de escritura, crear información de operación
        if visitor.write_operations:
            requires_verification = True
            
            # Agrupar operaciones por tipo
            create_ops = [op for op in visitor.write_operations if op['method'] == 'create']
            write_ops = [op for op in visitor.write_operations if op['method'] == 'write']
            unlink_ops = [op for op in visitor.write_operations if op['method'] == 'unlink']
            copy_ops = [op for op in visitor.write_operations if op['method'] == 'copy']
            
            # Determinar tipo de operación principal
            # Si hay copy_ops, tiene prioridad para mostrar concepto de duplicación
            if copy_ops:
                # copy() se trata como create (crea nuevos registros)
                operation_info['operation_type'] = 'create'
                # Marcar como duplicación para mostrar concepto descriptivo
                operation_info['operation_concept'] = 'duplicacion'
                # Sumar registros de todas las operaciones copy
                total_records = 0
                has_unknown = False
                for op in copy_ops:
                    if op['records_count'] is not None:
                        total_records += op['records_count']
                    else:
                        has_unknown = True
                
                if has_unknown:
                    operation_info['records_count'] = None  # No se puede determinar con certeza
                else:
                    operation_info['records_count'] = total_records if total_records > 0 else 1
                
                operation_info['is_massive'] = operation_info['records_count'] is None or operation_info['records_count'] > 1
            
            elif create_ops:
                operation_info['operation_type'] = 'create'
                # Sumar registros de todas las operaciones create
                total_records = 0
                has_unknown = False
                for op in create_ops:
                    if op['records_count'] is not None:
                        total_records += op['records_count']
                    else:
                        has_unknown = True
                
                if has_unknown:
                    operation_info['records_count'] = None  # No se puede determinar con certeza
                else:
                    operation_info['records_count'] = total_records if total_records > 0 else 1
                
                operation_info['is_massive'] = operation_info['records_count'] is None or operation_info['records_count'] > 1
            
            elif write_ops:
                operation_info['operation_type'] = 'write'
                # Sumar registros de todas las operaciones write
                total_records = 0
                has_unknown = False
                for op in write_ops:
                    if op['records_count'] is not None:
                        total_records += op['records_count']
                    else:
                        has_unknown = True
                
                if has_unknown:
                    operation_info['records_count'] = None  # No se puede determinar con certeza
                else:
                    operation_info['records_count'] = total_records if total_records > 0 else 1
                
                operation_info['is_massive'] = operation_info['records_count'] is None or operation_info['records_count'] > 1
            
            elif unlink_ops:
                operation_info['operation_type'] = 'unlink'
                # No podemos saber la cantidad exacta hasta ejecutar el código,
                # así que dejamos records_count en None para forzar el dry-run.
                operation_info['records_count'] = None
                operation_info['is_massive'] = len(unlink_ops) > 1
            
            # Obtener modelo principal
            # PRIORIDAD ABSOLUTA: Si hay operaciones create/copy, usar SIEMPRE el modelo donde se crea (más relevante)
            # Esto evita que se detecte un modelo auxiliar (ej: res.country.state) en lugar del modelo principal (ej: ir.filters)
            if create_ops or copy_ops:
                # Para create/copy, usar el modelo donde se hace la operación
                # IMPORTANTE: Priorizar create_ops sobre copy_ops si ambos existen
                ops_to_check = create_ops if create_ops else copy_ops
                model_from_create = None
                for op in ops_to_check:
                    model_name_candidate = op.get('model_name')
                    if model_name_candidate:
                        model_from_create = model_name_candidate
                        _logger.debug(f"MCP: AST - Modelo detectado en create/copy: {model_from_create}")
                        break  # Usar el primer modelo encontrado en create/copy
                
                # SIEMPRE usar el modelo de create/copy si existe, NUNCA usar visitor.model_names como fallback
                if model_from_create:
                    operation_info['model_name'] = model_from_create
                    _logger.debug(f"MCP: AST - Modelo final establecido desde create/copy: {model_from_create}")
                else:
                    # Solo si NO se pudo detectar el modelo en create/copy, intentar con visitor.model_names
                    # Pero esto es un caso muy raro
                    if visitor.model_names:
                        fallback_model = list(visitor.model_names)[0]
                        operation_info['model_name'] = fallback_model
                        _logger.warning(f"MCP: AST - No se detectó modelo en create/copy, usando fallback: {fallback_model}")
            elif write_ops:
                # Para write, también priorizar el modelo donde se escribe
                model_from_write = None
                for op in write_ops:
                    if op.get('model_name'):
                        model_from_write = op['model_name']
                        break
                if model_from_write:
                    operation_info['model_name'] = model_from_write
                elif visitor.model_names:
                    operation_info['model_name'] = list(visitor.model_names)[0]
            elif visitor.model_names:
                operation_info['model_name'] = list(visitor.model_names)[0]  # Usar el primero encontrado
            else:
                # Intentar extraer modelo con regex como fallback
                model_match = re.search(r"env\s*\[\s*['\"]([^'\"]+)['\"]\s*\]", code, flags=re.IGNORECASE)
                if model_match:
                    operation_info['model_name'] = model_match.group(1)
    
    except SyntaxError:
        # Si hay error de sintaxis, usar detección básica con regex como fallback
        if re.search(r'\.(create|write|unlink|copy)\s*\(', code, flags=re.IGNORECASE | re.MULTILINE):
            requires_verification = True
            operation_info['operation_type'] = 'write'
            operation_info['records_count'] = None  # No se puede determinar
            operation_info['is_massive'] = True
    except Exception as e:
        # Si hay error en el análisis AST, usar detección básica con regex como fallback
        _logger.warning(f"MCP: Error analizando AST para detectar operaciones peligrosas: {e}")
        if re.search(r'\.(create|write|unlink|copy)\s*\(', code, flags=re.IGNORECASE | re.MULTILINE):
            requires_verification = True
            operation_info['operation_type'] = 'write'
            operation_info['records_count'] = None  # No se puede determinar
            operation_info['is_massive'] = True
    
    return requires_verification, operation_info

