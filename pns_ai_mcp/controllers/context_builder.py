# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Build a safe execution context for relaxaicode code."""

import _string
import ast as _ast
import builtins as _builtins
import operator as _operator
import string as _string_mod
import types as _types

# SINGLE denylist of dangerous attributes, shared with the AST (validators_base.py).
# One place, so the static layer (AST) and the dynamic one (guarded_getattr)
# never drift apart. At Odoo runtime it is imported by its addon path; in the
# unit tests (which load this .py by path, without Odoo) the sibling
# validators_base.py is loaded by file.
try:  # pragma: no cover - Odoo runtime path
    from odoo.addons.pns_ai_mcp.controllers.validators_base import (
        DANGEROUS_ATTR_NAMES,
        DANGEROUS_FORMAT_NAMES,
        RELAXAICODE_DANGEROUS_MODULES,
        RELAXAICODE_FORBIDDEN_ORM_ATTRS,
        RELAXAICODE_ORM_WRITE_ATTRS,
        RELAXAICODE_PRIVILEGE_ATTRS,
        RELAXAICODE_PRIVILEGE_HINT,
        RELAXAICODE_SAFE_INTERNAL_MODULES,
        RELAXAICODE_SAFE_MODULES,
        RELAXAICODE_SIDE_EFFECT_METHODS,
        _unsafe_import_error,
        blocked_private_attr,
        catalogue_inspect_error,
    )
except Exception:  # pragma: no cover - unit test / standalone path
    import importlib.util as _ilu
    import os as _os
    _vp = _os.path.join(_os.path.dirname(__file__), 'validators_base.py')
    _sp = _ilu.spec_from_file_location('_pns_relax_validators', _vp)
    _vm = _ilu.module_from_spec(_sp)
    _sp.loader.exec_module(_vm)
    DANGEROUS_ATTR_NAMES = _vm.DANGEROUS_ATTR_NAMES
    DANGEROUS_FORMAT_NAMES = _vm.DANGEROUS_FORMAT_NAMES
    RELAXAICODE_FORBIDDEN_ORM_ATTRS = _vm.RELAXAICODE_FORBIDDEN_ORM_ATTRS
    RELAXAICODE_ORM_WRITE_ATTRS = _vm.RELAXAICODE_ORM_WRITE_ATTRS
    RELAXAICODE_PRIVILEGE_ATTRS = _vm.RELAXAICODE_PRIVILEGE_ATTRS
    RELAXAICODE_PRIVILEGE_HINT = _vm.RELAXAICODE_PRIVILEGE_HINT
    RELAXAICODE_DANGEROUS_MODULES = _vm.RELAXAICODE_DANGEROUS_MODULES
    RELAXAICODE_SAFE_MODULES = _vm.RELAXAICODE_SAFE_MODULES
    RELAXAICODE_SAFE_INTERNAL_MODULES = _vm.RELAXAICODE_SAFE_INTERNAL_MODULES
    RELAXAICODE_SIDE_EFFECT_METHODS = _vm.RELAXAICODE_SIDE_EFFECT_METHODS
    _unsafe_import_error = _vm._unsafe_import_error
    blocked_private_attr = _vm.blocked_private_attr
    catalogue_inspect_error = _vm.catalogue_inspect_error

try:  # pragma: no cover - Odoo runtime
    from odoo.addons.pns_ai_mcp.utils.sandbox_helpers import (
        collect_sandbox_helpers,
    )
except Exception:  # pragma: no cover - host unit test / standalone
    import importlib.util as _ilu_sh
    import os as _os_sh
    _shp = _os_sh.path.join(
        _os_sh.path.dirname(__file__), '..', 'utils', 'sandbox_helpers.py',
    )
    _shs = _ilu_sh.spec_from_file_location('_pns_sandbox_helpers', _shp)
    _shm = _ilu_sh.module_from_spec(_shs)
    _shs.loader.exec_module(_shm)
    collect_sandbox_helpers = _shm.collect_sandbox_helpers


class GuardedSandboxEnv(object):
    """Sandbox ``env``: ALLOWLIST of what the sandbox may touch.

    Default-deny, not default-allow. A denylist always misses the next public
    attribute Odoo adds to ``Environment``: ``env.args`` is the raw
    ``(cr, uid, context, su)`` tuple and ``env.all`` is every live Environment
    (both public, no leading ``_``), so either one hands out the real cursor
    without ever writing ``cr``. Only the names below are exposed; everything
    else — ``args``, ``all``, ``cache``, ``registry``, ``uid_origin`` and any
    future addition — raises.

    ``ai.api.server`` / ``ai.context`` / ``ai.skill`` /
    ``ai.trusted.action`` are catalogues kept off the ORM (``__getitem__`` /
    ``get``). List/load knowledge via ``get_context``; skills via ``/`` in the
    chat; external calls via ``api_call``. ``with_context`` / ``with_company``
    return another wrapper so the gate holds down the chain. Nothing here
    changes the identity: ``sudo``, ``with_user``, ``with_env`` and
    ``env(user=…, su=…)`` raise.
    """

    _WRAP_METHODS = ('with_context', 'with_company')
    # The whole public env surface the sandbox legitimately reads (as the
    # asking user): identity, company set, locale and a record by XML id.
    # ``__getitem__`` / ``get`` / ``__contains__`` are real methods below.
    _ALLOWED_ENV_ATTRS = frozenset({
        'user', 'company', 'companies', 'context', 'lang', 'uid', 'ref',
    })

    def __init__(self, env):
        object.__setattr__(self, '_env', env)

    def __getitem__(self, model):
        err = catalogue_inspect_error(model)
        if err:
            raise KeyError(err)
        return self._env[model]

    def get(self, model, default=None):
        err = catalogue_inspect_error(model)
        if err:
            raise KeyError(err)
        getter = getattr(self._env, 'get', None)
        if callable(getter):
            return getter(model, default)
        try:
            return self._env[model]
        except KeyError:
            return default

    def __contains__(self, model):
        return model in self._env

    def __getattr__(self, name):
        if blocked_private_attr(name):
            raise AttributeError(
                "Access to private attribute %r is not allowed in "
                "RelaxAICode (sandbox)." % (name,)
            )
        if name in RELAXAICODE_PRIVILEGE_ATTRS:
            raise AttributeError(RELAXAICODE_PRIVILEGE_HINT % (name,))
        if name in self._WRAP_METHODS:
            attr = getattr(self._env, name)
            if callable(attr):
                def _wrapped(*args, **kwargs):
                    return GuardedSandboxEnv(attr(*args, **kwargs))
                return _wrapped
            return attr
        if name in self._ALLOWED_ENV_ATTRS:
            return getattr(self._env, name)
        raise AttributeError(
            "RelaxAICode exposes only env['model'] and env.user / company / "
            "companies / context / lang / uid / ref / with_context / "
            "with_company; %r is not available. Read records through "
            "env['model'].search(...)." % (name,)
        )

    def __call__(self, *args, **kwargs):
        if args or set(kwargs) - {'context'}:
            raise AttributeError(RELAXAICODE_PRIVILEGE_HINT % ('env(...)',))
        return GuardedSandboxEnv(self._env(**kwargs))

    def __bool__(self):
        return bool(self._env)

    def __repr__(self):
        return '<GuardedSandboxEnv %r>' % (self._env,)


# Live database handles. Holding one is raw SQL and transaction control: a
# ROLLBACK ends box A's READ ONLY transaction and the next one can write.
# Matched by class over the MRO, so the attribute that led there does not
# matter (``env.args[0]``, a psycopg2 error's ``.cursor``, the next one).
# Module names cover Odoo 14 (``odoo.api``) and later series (``odoo.orm``).
_DB_HANDLE_MODULES = frozenset({
    'odoo.sql_db', 'odoo.api', 'odoo.modules.registry',
    'odoo.orm.environments', 'odoo.orm.registry',
    'psycopg2.extensions', 'psycopg2._psycopg',
})
_DB_HANDLE_CLASSES = frozenset({
    'BaseCursor', 'Cursor', 'TestCursor', 'PsycoConnection', 'Connection',
    'ConnectionPool', 'cursor', 'connection',
    'Environment', 'Environments', 'Transaction', 'Cache', 'Registry',
})
_db_handle_by_class = {}

_DB_HANDLE_HINT = (
    "RelaxAICode cannot reach %r: it leads to the database connection, "
    "outside the ORM and the read-only run. Read with env['model'].search(...)."
)


def is_db_handle(value):
    """True for a cursor, a connection, a raw Environment or a registry (or their class)."""
    cls = value if isinstance(value, type) else type(value)
    try:
        return _db_handle_by_class[cls]
    except KeyError:
        pass
    except TypeError:
        return False
    hit = any(
        getattr(k, '__module__', None) in _DB_HANDLE_MODULES
        and getattr(k, '__name__', None) in _DB_HANDLE_CLASSES
        for k in getattr(cls, '__mro__', ())
    )
    if len(_db_handle_by_class) > 4096:
        _db_handle_by_class.clear()
    _db_handle_by_class[cls] = hit
    return hit


def _refuse_attr_name(name, dynamic):
    """Raise if sandbox code may not read attribute *name*.

    The literal reads follow the AST rules. A dynamic name (``getattr``,
    ``attrgetter``, ``methodcaller``) also refuses the ORM mutators and the
    methods that write with their own cursor: the AST flags those as writes
    only when it can see the name.
    """
    if blocked_private_attr(name):
        raise AttributeError(
            "Access to private attribute %r is not allowed in "
            "RelaxAICode (sandbox)." % (name,)
        )
    if name in RELAXAICODE_PRIVILEGE_ATTRS:
        raise AttributeError(RELAXAICODE_PRIVILEGE_HINT % (name,))
    if name in RELAXAICODE_FORBIDDEN_ORM_ATTRS:
        raise AttributeError(
            "Access to attribute %r is not allowed in RelaxAICode "
            "(external API catalogue/secrets; use api_call)." % (name,)
        )
    if dynamic and name in RELAXAICODE_ORM_WRITE_ATTRS:
        raise AttributeError(
            "Access to ORM mutator %r via getattr is not allowed in RelaxAICode "
            "(use safe_plan_request for writes)." % (name,)
        )
    if dynamic and name in RELAXAICODE_SIDE_EFFECT_METHODS:
        raise AttributeError(
            "Method %r writes outside RelaxAICode's rollback and is not "
            "allowed here (use safe_plan_request for writes)." % (name,)
        )
    if name in DANGEROUS_ATTR_NAMES:
        raise AttributeError(
            "Access to attribute %r is not allowed in RelaxAICode (sandbox)." % (name,)
        )
    if name in DANGEROUS_FORMAT_NAMES:
        raise AttributeError(
            "%r (string.Formatter) is not allowed in RelaxAICode: it reads "
            "attributes outside the sandbox. Use f-strings or '{}'.format()." % (name,)
        )
    if len(name) >= 5 and name.startswith('__') and name.endswith('__'):
        raise AttributeError(
            "Access to dunder attribute %r is not allowed in RelaxAICode (sandbox)." % (name,)
        )


def _read_attr(obj, name, default):
    if is_db_handle(obj):
        raise AttributeError(_DB_HANDLE_HINT % (name,))
    if name in _STR_FORMAT_METHODS and (
            isinstance(obj, str)
            or (isinstance(obj, type) and issubclass(obj, str))):
        return _guarded_str_format(obj, name)
    value = getattr(obj, name, *default)
    if isinstance(value, _types.ModuleType):
        raise AttributeError(
            "Access to module %r is not allowed in RelaxAICode (sandbox)." % (name,)
        )
    if is_db_handle(value):
        raise AttributeError(_DB_HANDLE_HINT % (name,))
    return value


def guarded_getattr(obj, name, *default):
    """The sandbox ``getattr``: a name built at run time, checked once resolved.

    Same rules as a literal read, plus the ORM mutators and the methods that
    commit on their own cursor. Public names and a few read-only metadata
    pieces (``_name``, ``_fields``, ``__last_update``…) pass. Neither the
    object read from nor the value returned may be a database handle.
    """
    if isinstance(name, str):
        _refuse_attr_name(name, dynamic=True)
    return _read_attr(obj, name, default)


def sandbox_attr(obj, name):
    """Every literal ``obj.name`` read in sandbox code (``compile_sandbox``).

    The AST only sees names; this sees the object. A public name that leads
    to the database (``env.args``, an exception's ``.cursor``) is refused
    here whatever it is called.
    """
    if name == '__name__' and isinstance(obj, type):
        return obj.__name__
    _refuse_attr_name(name, dynamic=False)
    return _read_attr(obj, name, ())


_STR_FORMAT_METHODS = frozenset({'format', 'format_map'})


class _SandboxFormatter(_string_mod.Formatter):
    """``str.format`` whose ``{0.a}`` / ``{0[k]}`` fields read like sandbox code.

    The builtin walks the field's attributes in C, past ``sandbox_attr``.
    """

    def get_field(self, field_name, args, kwargs):
        first, rest = _string.formatter_field_name_split(field_name)
        obj = self.get_value(first, args, kwargs)
        for is_attr, key in rest:
            obj = sandbox_attr(obj, key) if is_attr else obj[key]
        return obj, first


_SANDBOX_FORMATTER = _SandboxFormatter()


def _template_reads_fields(template):
    for _text, field, spec, _conv in _SANDBOX_FORMATTER.parse(template):
        if field and ('.' in field or '[' in field):
            return True
        if spec and _template_reads_fields(spec):
            return True
    return False


def _guarded_str_format(obj, name):
    """``format`` / ``format_map`` of a string (or of ``str`` itself) for the sandbox."""
    if isinstance(obj, type):
        def _unbound(template, *args, **kwargs):
            if not isinstance(template, str):
                raise TypeError('%s.%s needs a string' % (obj.__name__, name))
            return _guarded_str_format(template, name)(*args, **kwargs)
        return _unbound
    if type(obj) is not str:
        # A str subclass (Markup…) keeps its own escaping formatter, which
        # also walks fields in C: plain positional / named fields only.
        bound = getattr(obj, name)

        def _plain_fields_only(*args, **kwargs):
            if _template_reads_fields(obj):
                raise AttributeError(
                    "RelaxAICode: %s.%s cannot read attributes or items in "
                    "its fields; pass the values as arguments."
                    % (type(obj).__name__, name))
            return bound(*args, **kwargs)
        return _plain_fields_only
    if name == 'format':
        def _format(*args, **kwargs):
            return _SANDBOX_FORMATTER.vformat(obj, args, kwargs)
        return _format

    def _format_map(mapping):
        return _SANDBOX_FORMATTER.vformat(obj, (), mapping)
    return _format_map


SANDBOX_ATTR_BUILTIN = '__pns_sandbox_attr__'


class _AttributeReadsThroughSandbox(_ast.NodeTransformer):
    """``a.b`` (read) → ``__pns_sandbox_attr__(a, 'b')``. Stores and deletes stay."""

    def visit_Attribute(self, node):
        self.generic_visit(node)
        if not isinstance(node.ctx, _ast.Load):
            return node
        call = _ast.Call(
            func=_ast.Name(id=SANDBOX_ATTR_BUILTIN, ctx=_ast.Load()),
            args=[node.value, _ast.Constant(value=node.attr)],
            keywords=[],
        )
        return _ast.copy_location(call, node)


def compile_sandbox(code, filename):
    """Compile sandbox code so every attribute read goes through ``sandbox_attr``.

    Run it only with a namespace from ``build_safe_context`` (it binds the
    builtin). The reserved name may not appear in the code: whoever could
    rebind it would read attributes unchecked.
    """
    if SANDBOX_ATTR_BUILTIN in code:
        raise SyntaxError('%r is reserved by the sandbox' % (SANDBOX_ATTR_BUILTIN,))
    tree = _ast.parse(code, filename, 'exec')
    tree = _AttributeReadsThroughSandbox().visit(tree)
    _ast.fix_missing_locations(tree)
    return compile(tree, filename, 'exec')


def guarded_import(name, *args, **kwargs):
    """
    Guard that blocks dangerous imports even when they are called dynamically.
    This function is added to the context as __import__ to block dynamic imports.
    Lists shared with the AST (validators_base.py).
    """
    # Get the module name (without submodules)
    module_name = name.split('.')[0] if '.' in name else name

    # urllib.parse: pure text functions (quote, urlencode, urlparse, parse_qs,
    # urljoin...), no network, no FS. ONLY the form
    # `from urllib.parse import <name>` (non-empty fromlist) is allowed; it binds
    # only the functions. `import urllib.parse` (empty fromlist) is blocked because
    # it would bind the `urllib` package, from which urllib.request (network) is reachable.
    if name == 'urllib.parse':
        fromlist = kwargs.get('fromlist')
        if fromlist is None and len(args) >= 3:
            fromlist = args[2]
        if fromlist:
            return safe_module(__import__(name, *args, **kwargs))
        raise ImportError(
            "Use 'from urllib.parse import quote, urlencode, urlparse'. "
            "'import urllib.parse' is not allowed (it would expose urllib)."
        )

    if module_name in RELAXAICODE_DANGEROUS_MODULES:
        raise ImportError(_unsafe_import_error(module_name))

    # Internal helpers of safe modules (CPython lazy imports).
    if module_name in RELAXAICODE_SAFE_INTERNAL_MODULES:
        return safe_module(__import__(name, *args, **kwargs))

    if module_name in RELAXAICODE_SAFE_MODULES:
        return safe_module(__import__(name, *args, **kwargs))

    raise ImportError(_unsafe_import_error(module_name))


# A "safe" module (datetime, platform, uuid, random, calendar, io…) must NOT
# be a door to another module: almost all of them carry `os` / `sys` inside as
# a CPython helper, and `platform.os.system(...)` would be command execution.
# The facade below never returns a module, nor a file/process call
# (`open`, `popen`, `system`…). The attribute and dunder denylist is the same
# as the hardened getattr one: a single criterion for both layers.
_MODULE_FACADE_FORBIDDEN_CALLABLES = frozenset({
    'open', 'fdopen', 'popen', 'system', 'exec', 'execv', 'spawn',
    'FileIO', 'open_code', 'remove', 'unlink', 'rmdir', 'getenv', 'putenv',
})


def _module_facade_rejects(name, value):
    """Shared policy: True when a module attribute must not be exposed."""
    if blocked_private_attr(name):
        return True
    if name in DANGEROUS_ATTR_NAMES or name in DANGEROUS_FORMAT_NAMES:
        return True
    if name in _MODULE_FACADE_FORBIDDEN_CALLABLES:
        return True
    if len(name) >= 5 and name.startswith('__') and name.endswith('__'):
        return True
    return isinstance(value, _types.ModuleType)


class SafeModuleFacade(object):
    """Read-only view over a safe stdlib module.

    Exposes classes, functions and constants, but never another module nor a
    file/process primitive, so `platform.os`, `datetime.sys` or `io.open`
    cannot be reached by plain dot-access (the AST only sees literal names and
    does not know an attribute resolves to a module).
    """

    __slots__ = ('_module', '_module_name')

    def __init__(self, module):
        object.__setattr__(self, '_module', module)
        object.__setattr__(
            self, '_module_name', getattr(module, '__name__', '?'))

    def __getattr__(self, name):
        value = getattr(self._module, name)  # AttributeError propagates as-is
        if _module_facade_rejects(name, value):
            raise AttributeError(
                "Access to %r via module %r is not allowed in RelaxAICode "
                "(sandbox)." % (name, self._module_name))
        if value is _operator.attrgetter:
            return guarded_attrgetter
        if value is _operator.methodcaller:
            return guarded_methodcaller
        return value

    def __setattr__(self, name, value):
        raise AttributeError(
            "RelaxAICode cannot set attributes on module %r." % (
                self._module_name,))

    def __dir__(self):
        return [
            n for n in dir(self._module)
            if not _module_facade_rejects(n, getattr(self._module, n, None))
        ]

    def __repr__(self):
        return "<SafeModuleFacade %r>" % (self._module_name,)


def _check_attr_path(path):
    """Run every dotted part of ``path`` through the guarded getattr policy."""
    if not isinstance(path, str):
        raise TypeError('attribute name must be a string')
    for part in path.split('.'):
        guarded_getattr(_ATTR_PROBE, part, None)


class _AttrProbe(object):
    """Has no attributes: the policy check raises before getattr matters."""
    __slots__ = ()


_ATTR_PROBE = _AttrProbe()


def _walk_attr_path(obj, path):
    for part in path.split('.'):
        obj = guarded_getattr(obj, part)
    return obj


def guarded_attrgetter(*paths):
    """``operator.attrgetter`` that reads through ``guarded_getattr`` on each call.

    The real one reads in C: checking the name up front would still hand
    back whatever object sits behind it.
    """
    if not paths:
        raise TypeError('attrgetter expected 1 argument, got 0')
    for path in paths:
        _check_attr_path(path)

    def _get(obj):
        if len(paths) == 1:
            return _walk_attr_path(obj, paths[0])
        return tuple(_walk_attr_path(obj, path) for path in paths)
    return _get


def guarded_methodcaller(name, *args, **kwargs):
    """``operator.methodcaller`` that looks the method up through ``guarded_getattr``."""
    _check_attr_path(name)

    def _call(obj):
        return guarded_getattr(obj, name)(*args, **kwargs)
    return _call


def safe_module(module):
    """Wrap a stdlib module in its read-only facade (idempotent)."""
    if isinstance(module, SafeModuleFacade):
        return module
    return SafeModuleFacade(module)


def sandbox_print(*_args, **_kwargs):
    """The model's ``print``: swallowed. Writes neither to the log nor to stdout.

    The model adds it to look at a value halfway through the script. Without
    this, ``name 'print' is not defined`` kills the query. The answer is still
    ``result``; a stray ``print`` at the end is already rewritten earlier.
    """
    return None


def build_safe_context(controller, operation_type='read', previous_result=None, env_override=None):
    """
    Build the safe context to run native Python code.
    
    Args:
        controller: Controller instance, to reach _get_env_for_operation
        operation_type: 'read' or 'write', depending on the operation type
        previous_result: Result of a previous run (for Phase 2: presentation)
        env_override: If given, this env is used instead of deriving it from the
            controller. Used to inject "box A" (READ ONLY cursor) into the
            read-only relaxaicode run.
    
    Returns:
        dict: Safe context with limited builtins and safe modules
    """
    import datetime as _datetime
    import collections as _collections
    import itertools as _itertools
    import functools as _functools
    import math as _math
    import statistics as _statistics
    import decimal as _decimal
    import json as _json
    import base64 as _base64
    import hashlib as _hashlib
    import re as _re
    import string as _string
    import operator as _operator
    import csv as _csv
    import io as _io
    import copy as _copy
    import uuid as _uuid
    import random as _random
    import calendar as _calendar
    import textwrap as _textwrap
    import unicodedata as _unicodedata
    import types as _types
    try:
        from zoneinfo import ZoneInfo as _ZoneInfo
    except Exception:
        # Python < 3.9 (Odoo 14): the prompt promises ZoneInfo. dateutil
        # ships with Odoo and, unlike pytz, is safe as ``tzinfo=``.
        try:
            from dateutil import tz as _dateutil_tz

            def _ZoneInfo(key):
                zone = _dateutil_tz.gettz(key)
                if zone is None:
                    raise KeyError('No time zone found with key %s' % key)
                return zone
        except Exception:
            _ZoneInfo = None

    # TRIMMED `string`: exposed without Formatter/Template. string.Formatter()
    # .get_field()/.vformat() return the real OBJECT (not its repr), which lets
    # you walk classes up to object.__subclasses__ without '.' or getattr (H3).
    # The AST already blocks those names; trimming the exposed module is defence
    # in depth. Useful constants/functions are kept (ascii_letters,
    # digits, punctuation, capwords, whitespace…).
    _safe_string = _types.SimpleNamespace(**{
        _k: getattr(_string, _k)
        for _k in dir(_string)
        if not _k.startswith('_') and _k not in ('Formatter', 'Template')
    })

    # Allowed built-in functions
    ALLOWED_BUILTINS_NAMES = [
        'len', 'sum', 'max', 'min', 'sorted', 'range',
        'enumerate', 'zip', 'map', 'filter', 'reversed',
        'int', 'float', 'str', 'list', 'dict', 'tuple', 'set',
        'bytes', 'bytearray', 'memoryview', 'frozenset',
        'bool', 'type', 'isinstance', 'issubclass', 'callable', 'abs', 'round', 'pow',
        'divmod', 'any', 'all', 'hasattr', 'getattr',
        # 'setattr'/'delattr' removed: they allowed hidden ORM writes
        # (setattr(rec, 'campo', valor)) that skipped the detector and box B.
        'iter', 'next', 'slice', 'hash', 'id',
        'ord', 'chr', 'bin', 'hex', 'oct',
        'repr', 'ascii', 'format',
    ]
    
    # Build the dict of allowed functions
    ALLOWED_BUILTINS = {}
    for name in ALLOWED_BUILTINS_NAMES:
        if hasattr(_builtins, name):
            ALLOWED_BUILTINS[name] = getattr(_builtins, name)
    
    # Add the guarded __import__
    ALLOWED_BUILTINS['__import__'] = guarded_import

    # Silent print: the model debugs with print() halfway through the script. The
    # real builtin is not on the list (it would write to the worker log).
    ALLOWED_BUILTINS['print'] = sandbox_print

    # HARDENED getattr: replaces the raw builtin with guarded_getattr to close
    # dynamic access to dangerous attributes whose name is built at
    # runtime (H1). The AST covers literals; this covers dynamic names.
    ALLOWED_BUILTINS['getattr'] = guarded_getattr
    # Literal attribute reads, once compile_sandbox has rewritten them.
    ALLOWED_BUILTINS[SANDBOX_ATTR_BUILTIN] = sandbox_attr
    
    # Get the Odoo env (or the injected one: box A in READ ONLY)
    env = env_override if env_override is not None else controller._get_env_for_operation(operation_type)
    
    # Extract infrastructure variables (Technical Protocol)
    user = env.user
    company = env.company
    
    # Odoo version info
    try:
        import odoo
        odoo_version = odoo.release.version
        odoo_series = odoo.release.series if hasattr(odoo.release, 'series') else odoo_version
    except (ImportError, AttributeError):
        odoo_version = '14.0'
        odoo_series = '14.0'

    # The database name is not published to the sandbox (PNS-36): instance
    # facts the code may use are the version, the URL and the locale.

    # Public URL of the instance: only system admins read ir.config_parameter
    # (no sudo in the sandbox), so the engine publishes this one fact to all.
    try:
        _web_base_url = env['ir.config_parameter'].sudo().get_param(
            'web.base.url') or ''
    except Exception:
        _web_base_url = ''
    
    # Get user/company locale info
    user_lang = 'en_US'  # Base Default
    locale_info = {'thousands_sep': ',', 'decimal_sep': '.', 'date_format': '%Y-%m-%d', 'csv_sep': ','}
    
    import logging
    _logger = logging.getLogger(__name__)
    
    try:
        # The user's session locale (res.lang) = source of truth for
        # separators and dates. corporate_terms only fills gaps, never overrides.
        user_lang = controller._get_user_locale()
        lang_record = env['res.lang'].with_context(active_test=False).search(
            [('code', '=', user_lang)], limit=1,
        )
        if lang_record:
            t_sep = lang_record.thousands_sep or ','
            d_sep = lang_record.decimal_point or '.'
            date_fmt = lang_record.date_format or '%Y-%m-%d'
            csv_sep = ';' if d_sep == ',' else ','
            locale_info = {
                'thousands_sep': t_sep,
                'decimal_sep': d_sep,
                'date_format': date_fmt,
                'csv_sep': csv_sep,
            }
        elif str(user_lang).startswith('es'):
            locale_info = {
                'thousands_sep': '.', 'decimal_sep': ',',
                'date_format': '%d/%m/%Y', 'csv_sep': ';',
            }

        try:
            mcp_formatting = env['ai.context'].get_formatting_conventions(
                user_locale=user_lang,
            ) or {}
        except Exception:
            mcp_formatting = {}
        for key, value in mcp_formatting.items():
            if value and key not in (
                'thousands_sep', 'decimal_sep', 'date_format', 'csv_sep',
            ):
                # Do not override res.lang conventions (avoids an erratic locale).
                locale_info[key] = value

        _logger.info(
            'MCP ContextBuilder: locale %s → %s', user_lang, locale_info,
        )

    except Exception as e:
        _logger.warning(f"MCP DEBUG [ContextBuilder]: Error resolving locale: {e}")
    
    # The user's clock (session time zone), not the process/container UTC.
    _user_tz = env.context.get('tz') or getattr(user, 'tz', None) or 'UTC'
    try:
        from odoo.addons.pns_ai_mcp.utils.user_time import user_local_now
        _user_now = user_local_now(_user_tz)
    except Exception:
        try:
            import importlib.util as _ilu_ut
            import os as _os_ut
            _utp = _os_ut.path.join(
                _os_ut.path.dirname(__file__), '..', 'utils', 'user_time.py',
            )
            _uts = _ilu_ut.spec_from_file_location('_pns_user_time', _utp)
            _utm = _ilu_ut.module_from_spec(_uts)
            _uts.loader.exec_module(_utm)
            _user_now = _utm.user_local_now(_user_tz)
        except Exception:
            _user_now = _datetime.datetime.now()
    _user_today = _user_now.date()

    # Build the safe context
    safe_context = {
        '__builtins__': ALLOWED_BUILTINS,
        '__import__': guarded_import,
        
        # Odoo env (ai.api.server / ai.context catalogues kept off the ORM)
        'env': GuardedSandboxEnv(env),
        
        'odoo_version': odoo_version,
        'odoo_series': odoo_series,
        
        # Odoo Objects
        'user': user,
        'company': company,
        
        # Locale variables (available directly in the generated code)
        'user_lang': user_lang,
        'lang': user_lang,          # Standard Odoo alias
        'locale': user_lang,        # Generic alias
        'userlang': user_lang,      # Emergency alias (no underscore)
        'user_language': user_lang, # Descriptive alias
        'language': user_lang,      # Simple alias
        
        'pk_decimal_sep': locale_info.get('decimal_sep', '.'),
        'pk_thousands_sep': locale_info.get('thousands_sep', ','),
        'pk_date_format': locale_info.get('date_format', '%Y-%m-%d'),
        'pk_csv_sep': locale_info.get('csv_sep', ','),

        'user_tz': env.context.get('tz') or user.tz or 'UTC',
        'user_name': user.name,
        'user_id': user.id,
        'web_base_url': _web_base_url,
        'company_name': company.name,
        'company_id': company.id,
        'today': _user_today,
        'now': _user_now,
        'server_today': _user_today.isoformat(),
        
        # Standard exceptions (needed for try/except)
        'NameError': NameError,
        'ValueError': ValueError,
        'TypeError': TypeError,
        'AttributeError': AttributeError,
        'KeyError': KeyError,
        'IndexError': IndexError,
        'ImportError': ImportError,
        'Exception': Exception,
        
        # Safe modules available directly (always behind their facade)
        'datetime': safe_module(_datetime),
        # datetime aliases the LLM uses without import (date.today(), timedelta(…)).
        # Contexts/docs teach date.today(); without these names → NameError
        # "name 'date' is not defined" in fresh code.
        'date': _datetime.date,
        'timedelta': _datetime.timedelta,
        'timezone': _datetime.timezone,
        'collections': safe_module(_collections),
        'itertools': safe_module(_itertools),
        'functools': safe_module(_functools),
        'math': safe_module(_math),
        'statistics': safe_module(_statistics),
        'decimal': safe_module(_decimal),
        'json': safe_module(_json),
        'base64': safe_module(_base64),
        'hashlib': safe_module(_hashlib),
        're': safe_module(_re),
        'string': _safe_string,  # without Formatter/Template (see above)
        'operator': safe_module(_operator),
        'csv': safe_module(_csv),
        'io': safe_module(_io),
        'copy': safe_module(_copy),
        'uuid': safe_module(_uuid),
        'random': safe_module(_random),
        'calendar': safe_module(_calendar),
        'textwrap': safe_module(_textwrap),
        'unicodedata': safe_module(_unicodedata),
    }
    if _ZoneInfo is not None:
        safe_context['ZoneInfo'] = _ZoneInfo

    # Grid presentation (pyjama / pastels): same palette as the HTML render.
    try:
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import (
            PASTEL_ROW_COLORS,
            apply_pajama_coloring,
        )
        safe_context['PASTEL_ROW_COLORS'] = PASTEL_ROW_COLORS
        safe_context['apply_pajama_coloring'] = apply_pajama_coloring
    except Exception:
        pass

    # Locale number formatting (pk_*): available in every skill/relaxaicode.
    # Avoids `{:,.2f}` (English) skill by skill. `data`/`groups` tables already use
    # the same criterion via relaxaicode_render; this covers hand-made HTML.
    _d_sep = locale_info.get('decimal_sep', '.')
    _t_sep = locale_info.get('thousands_sep', ',')
    try:
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import (
            format_amount as _format_amount,
            format_number as _format_number,
        )

        def format_number(value, decimals=2):
            return _format_number(
                value,
                decimals=decimals,
                decimal_sep=_d_sep,
                thousands_sep=_t_sep,
            )

        def format_amount(value, symbol=u'€', decimals=2, symbol_after=True):
            return _format_amount(
                value,
                symbol=symbol,
                decimals=decimals,
                decimal_sep=_d_sep,
                thousands_sep=_t_sep,
                symbol_after=symbol_after,
            )

        safe_context['format_number'] = format_number
        safe_context['format_amount'] = format_amount
    except Exception:
        pass

    # Selection labels: field.selection may be a list or a callable (any series).
    try:
        from odoo.addons.pns_ai_mcp.utils.field_selection import (
            resolve_field_selection as _resolve_field_selection,
        )

        def field_selection(model, name):
            return _resolve_field_selection(env, model, name)

        safe_context['field_selection'] = field_selection
    except Exception:
        pass

    # Spoken / transposed identifiers: ilike on the full token is not enough.
    try:
        from odoo.addons.pns_ai_mcp.utils.name_affinity import (
            search_by_affinity as _search_by_affinity,
        )

        def search_by_affinity(model, needles, fields=None, domain=None,
                               limit=15, min_score=None):
            return _search_by_affinity(
                env, model, needles, fields=fields, domain=domain,
                limit=limit, min_score=min_score,
            )

        safe_context['search_by_affinity'] = search_by_affinity
    except Exception:
        try:
            import importlib.util as _ilu_aff
            import os as _os_aff
            _ap = _os_aff.path.join(
                _os_aff.path.dirname(__file__), '..', 'utils', 'name_affinity.py',
            )
            _asp = _ilu_aff.spec_from_file_location('_pns_name_affinity', _ap)
            _am = _ilu_aff.module_from_spec(_asp)
            _asp.loader.exec_module(_am)

            def search_by_affinity(model, needles, fields=None, domain=None,
                                   limit=15, min_score=None):
                return _am.search_by_affinity(
                    env, model, needles, fields=fields, domain=domain,
                    limit=limit, min_score=min_score,
                )

            safe_context['search_by_affinity'] = search_by_affinity
        except Exception:
            pass

    # Always defined (None if there is no dataset): avoids `if 'x' in locals()/dir()`,
    # which the AST rejects and which caused wasted rounds.
    if previous_result is not None:
        safe_context['previous_result'] = previous_result
        if isinstance(previous_result, dict):
            safe_context['raw_data'] = previous_result.get('data', previous_result)
        else:
            safe_context['raw_data'] = previous_result
    else:
        safe_context['previous_result'] = None
        safe_context['raw_data'] = None

    # Safe Plan presentation: unwrap step list / body without guessing envelopes.
    try:
        from odoo.addons.pns_ai_mcp.utils.record_delivery_gate import (
            get_safe_plan_steps as _get_safe_plan_steps,
            parse_safe_plan_step_body as _parse_safe_plan_step_body,
        )
        safe_context['get_safe_plan_steps'] = _get_safe_plan_steps
        safe_context['parse_safe_plan_step_body'] = _parse_safe_plan_step_body
    except Exception:  # pragma: no cover - host unit path without odoo
        try:
            import importlib.util as _ilu
            import os as _os
            _rp = _os.path.join(
                _os.path.dirname(__file__), '..', 'utils', 'record_delivery_gate.py',
            )
            _sp = _ilu.spec_from_file_location('_pns_rdg', _rp)
            _rm = _ilu.module_from_spec(_sp)
            _sp.loader.exec_module(_rm)
            safe_context['get_safe_plan_steps'] = _rm.get_safe_plan_steps
            safe_context['parse_safe_plan_step_body'] = _rm.parse_safe_plan_step_body
        except Exception:
            pass

    # Optional skill/query parameters: always present (None) so you
    # can write `if lugar:` / `if anio:` without forbidden introspection.
    for _opt in (
        'lugar', 'fecha', 'start_date', 'end_date',
        'anio', 'year', 'mes', 'arguments',
    ):
        safe_context.setdefault(_opt, None)

    # Sandbox-module sync: opted-in models publish extra callables.
    # Engine keys already in safe_context win. No addon names here.
    try:
        module_helpers = collect_sandbox_helpers(env, occupied=safe_context)
        if module_helpers:
            safe_context.update(module_helpers)
    except Exception:
        pass

    return safe_context
