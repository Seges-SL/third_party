# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Relaxaicode AST tags, deny lists, shared reject texts and small AST helpers.

The AST check and the runtime guards (``context_builder``) read the same lists here.
No import from this addon: ``context_builder`` loads it by path in unit tests."""

import ast
import re


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
# not a syntax hole. The LLM must switch (get_context / api_call / prose),
# not rewrite.
AST_SWITCH_TOOL_CODES = frozenset({
    'SORT_KEY',
    'CONTEXT_CATALOGUE',
    'API_CATALOGUE',
    'SKILL_CATALOGUE',
    'ACTION_CATALOGUE',
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
    "For external HTTP data use safe_plan_request with op='fetch_url' "
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
#   ai.skill      — slash en Chatboo; leer procedure/code_body reescribe el turno.
#   ai.trusted.action — action_code ya está en safe_plan_request; listar no es search.
RELAXAICODE_FORBIDDEN_API_SERVER_MODEL = 'ai.api.server'
RELAXAICODE_FORBIDDEN_CONTEXT_MODEL = 'ai.context'
RELAXAICODE_FORBIDDEN_SKILL_MODEL = 'ai.skill'
RELAXAICODE_FORBIDDEN_TRUSTED_ACTION_MODEL = 'ai.trusted.action'

# Private attributes are the engine's own machinery: several open their own
# cursor and commit, so box A's READ ONLY cursor does not hold them. A name
# list would miss the next private method, so every ``_name`` is closed but
# these read-only pieces of model metadata.
RELAXAICODE_PRIVATE_ATTR_EXCEPTIONS = frozenset({
    '_name', '_fields', '_description', '_rec_name', '_order', '__last_update',
    '__name__',
})


def blocked_private_attr(name):
    """True when *name* is a private attribute the sandbox may not touch."""
    return (
        isinstance(name, str)
        and name.startswith('_')
        and name not in RELAXAICODE_PRIVATE_ATTR_EXCEPTIONS
    )


def _private_attr_error(name):
    return format_ast_error(
        'PRIVATE_ATTR',
        "RelaxAICode cannot use private attribute %r. Code runs as the "
        "asking user over public names only; private methods are the "
        "engine's own and several write outside this read-only run. Do not "
        "retry with another private name." % (name,),
    )


# Credentials are for humans: MCP keys, the temporary PIN, provider API
# keys and system parameters, plus every model that leads to them by a
# relation (the agent chain reaches a provider in two hops). The asking
# user's access is not enough here: an admin's turn may carry injected text.
RELAXAICODE_CREDENTIAL_MODELS = frozenset({
    'ai.mcp.user',
    'ai.key.pin.ask',
    'ai.key.pin.block',
    'ai.key.pin.desk',
    'ai.api.key.wizard',
    'ai.artifact.bundle.export.wizard',
    'ai.provider',
    'ai.provider.model',
    'ai.agent.provider',
    'ai.agent',
    'ai.agent.skill.import.wizard',
    'ai.agent.cache.rebuild.wizard',
    'ai.agent.context.import.wizard',
    'ai.context.stats.wizard',
    'ai.skill.capture.wizard',
    'ai.agent.import.wizard',
    'ai.agent.compose.wizard',
    'ai.agent.compose.line',
    'ai.skill.capture.param.line',
    'ir.config_parameter',
    'res.users.apikeys',
})

# Atributos ORM de catálogo/secreto/drivers de ai.api.server. RelaxAICode
# debe usar safe_plan_request op=api_call — misma denylist en AST y runtime.
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

# Business methods that write without calling .write(): most open their own
# cursor and commit, so box A's rollback does not undo them. Blocked by name
# both literally (AST) and through getattr/attrgetter/methodcaller (runtime).
RELAXAICODE_SIDE_EFFECT_METHODS = frozenset({
    'confirm_by_user',
    '_confirm_by_user',
    'cancel_by_user',
    'execute_plan_now',
    'resolve_confirm_and_execute',
    '_resolve_confirm_and_execute',
    'resolve_confirm',
    '_resolve_confirm',
    'resolve_execute',
    '_resolve_execute',
    'action_confirm_and_execute',
    'action_execute_plan',
    'action_cancel',
    '_mint_confirm_token',
    '_consume_confirm_token',
    'cleanup_expired',
    'cleanup_stuck_state',
    'create_verification',
    'button_immediate_install',
    'button_immediate_upgrade',
    'button_immediate_uninstall',
})

# RelaxAICode always runs as the asking user. These names hand out another
# identity: ``sudo()``, ``with_user(1)`` (uid 1 is superuser), ``with_env``,
# and ``record.env`` / ``env._env`` (the raw environment, outside the
# catalogue gate). ``groups=`` and record rules only hold while none of them
# is reachable.
RELAXAICODE_PRIVILEGE_ATTRS = frozenset({
    'sudo', 'with_user', 'with_env', 'env', '_env',
})
RELAXAICODE_PRIVILEGE_HINT = (
    "RelaxAICode runs as the asking user: %r is not available. "
    "Read with the user's own access (env['model'].search(...)); "
    "what the user cannot read stays out of the answer."
)

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


# Python 3.7 (Odoo 14) parses literals as Str / Num / NameConstant / Bytes;
# 3.8+ parses them all as Constant. Names, not classes: 3.14 drops the old ones.
_AST_LITERAL_NODES = frozenset({'Constant', 'Str', 'Num', 'NameConstant', 'Bytes'})


def ast_literal(node):
    """``(True, value)`` if *node* is a literal, else ``(False, None)``."""
    if type(node).__name__ not in _AST_LITERAL_NODES:
        return False, None
    for attr in ('value', 's', 'n'):
        if attr in node._fields:
            return True, getattr(node, attr)
    return False, None


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


def _is_name_env(node):
    """True when *node* is the sandbox/global Name ``env``."""
    return isinstance(node, ast.Name) and node.id == 'env'


def _external_api_server_inspect_error():
    return format_ast_error(
        'API_CATALOGUE',
        "RelaxAICode cannot inspect ai.api.server "
        "(catalogue/config/spec). Do not retry with relaxaicode — "
        "use the injected catalogue and safe_plan_request with "
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
        "pack XML. Creating discovery rows is safe_plan_request, "
        "not a sandbox search.",
    )


def _skill_inspect_error():
    return format_ast_error(
        'SKILL_CATALOGUE',
        "RelaxAICode cannot inspect ai.skill "
        "(slash catalogue). Do not retry with relaxaicode — "
        "do not dump procedure or code_body. Do not copy another skill's "
        "Code or Procedure for a similar page; query the business models. "
        "A skill runs when the user types "
        "/command, or when the engine matches the sentence to that "
        "skill's own trigger phrases; the model does not launch it. "
        "On the MCP endpoint you do "
        "not run slash skills: answer in prose that you serve tools and "
        "knowledge packs. Creating or editing skills is not a sandbox search.",
    )


def _trusted_action_inspect_error():
    return format_ast_error(
        'ACTION_CATALOGUE',
        "RelaxAICode cannot inspect ai.trusted.action "
        "(action catalogue). Do not retry with relaxaicode — "
        "the closed action_code list is already in safe_plan_request. "
        "If the write still has a choice the user did not give, show "
        "the rows you have and ask. Do not inspect wizards to guess.",
    )


def _credential_inspect_error(model):
    return format_ast_error(
        'CREDENTIALS',
        "RelaxAICode cannot read %s: it holds keys, PINs or provider "
        "secrets, which only a person handles. Do not retry with "
        "relaxaicode; say that the assistant does not read them." % model,
    )


def catalogue_inspect_error(model):
    """LLM-facing reject text if *model* is a forbidden catalogue, else None."""
    if model == RELAXAICODE_FORBIDDEN_API_SERVER_MODEL:
        return _external_api_server_inspect_error()
    if model == RELAXAICODE_FORBIDDEN_CONTEXT_MODEL:
        return _context_inspect_error()
    if model == RELAXAICODE_FORBIDDEN_SKILL_MODEL:
        return _skill_inspect_error()
    if model == RELAXAICODE_FORBIDDEN_TRUSTED_ACTION_MODEL:
        return _trusted_action_inspect_error()
    if model in RELAXAICODE_CREDENTIAL_MODELS:
        return _credential_inspect_error(model)
    return None
