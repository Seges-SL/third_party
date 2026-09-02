# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Build a safe execution context for relaxaicode code."""

import builtins as _builtins

# Denylist ÚNICA de atributos peligrosos, compartida con el AST (validators.py).
# Un solo sitio para que la capa estática (AST) y la dinámica (guarded_getattr)
# no se desincronicen. En runtime Odoo se importa por su ruta de addon; en los
# unit tests (que cargan este .py por ruta, sin Odoo) se carga validators.py
# hermano por fichero.
try:  # pragma: no cover - camino de runtime Odoo
    from odoo.addons.pns_ai_mcp.controllers.validators import (
        DANGEROUS_ATTR_NAMES,
        RELAXAICODE_DANGEROUS_MODULES,
        RELAXAICODE_FORBIDDEN_ORM_ATTRS,
        RELAXAICODE_ORM_WRITE_ATTRS,
        RELAXAICODE_SAFE_INTERNAL_MODULES,
        RELAXAICODE_SAFE_MODULES,
        _unsafe_import_error,
        catalogue_inspect_error,
    )
except Exception:  # pragma: no cover - camino unit test / standalone
    import importlib.util as _ilu
    import os as _os
    _vp = _os.path.join(_os.path.dirname(__file__), 'validators.py')
    _sp = _ilu.spec_from_file_location('_pns_relax_validators', _vp)
    _vm = _ilu.module_from_spec(_sp)
    _sp.loader.exec_module(_vm)
    DANGEROUS_ATTR_NAMES = _vm.DANGEROUS_ATTR_NAMES
    RELAXAICODE_FORBIDDEN_ORM_ATTRS = _vm.RELAXAICODE_FORBIDDEN_ORM_ATTRS
    RELAXAICODE_ORM_WRITE_ATTRS = _vm.RELAXAICODE_ORM_WRITE_ATTRS
    RELAXAICODE_DANGEROUS_MODULES = _vm.RELAXAICODE_DANGEROUS_MODULES
    RELAXAICODE_SAFE_MODULES = _vm.RELAXAICODE_SAFE_MODULES
    RELAXAICODE_SAFE_INTERNAL_MODULES = _vm.RELAXAICODE_SAFE_INTERNAL_MODULES
    _unsafe_import_error = _vm._unsafe_import_error
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
    """Sandbox ``env``: catalogue models stay off ORM (AST + runtime).

    ``ai.api.server`` / ``ai.context`` are injected catalogues. List/load
    knowledge via ``get_context``; external calls via ``api_call``.
    ``sudo`` / ``with_context`` chains return another wrapper so
    ``env.sudo()['ai.context']`` cannot skip the gate.
    """

    _WRAP_METHODS = (
        'sudo', 'with_context', 'with_user', 'with_env', 'with_company',
    )

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
        attr = getattr(self._env, name)
        if name in self._WRAP_METHODS and callable(attr):
            def _wrapped(*args, **kwargs):
                return GuardedSandboxEnv(attr(*args, **kwargs))
            return _wrapped
        return attr

    def __call__(self, *args, **kwargs):
        return GuardedSandboxEnv(self._env(*args, **kwargs))

    def __bool__(self):
        return bool(self._env)

    def __repr__(self):
        return '<GuardedSandboxEnv %r>' % (self._env,)


def guarded_getattr(obj, name, *default):
    """`getattr` endurecido para el sandbox (caja A).

    Cierra el hueco H1: el AST sólo ve nombres LITERALES, así que
    `getattr(x, '__cla' + 'ss__')` esquivaba la denylist estática. Aquí el
    nombre se evalúa en RUNTIME (ya resuelto) contra la MISMA denylist, más un
    bloqueo genérico de dunders `__x__`. Se rechaza:
      · cualquier nombre de DANGEROUS_ATTR_NAMES (incl. frames: f_back, tb_frame…)
      · cualquier dunder `__x__` (introspección de tipos/código/globals)
      · mutadores ORM (`create`/`write`/`unlink`/`copy`) vía getattr dinámico
    Se permiten atributos ORM normales y de UN guion (name, _name, _fields,
    __last_update —que NO termina en '__'—, etc.).
    """
    if isinstance(name, str):
        if name in RELAXAICODE_FORBIDDEN_ORM_ATTRS:
            raise AttributeError(
                "Access to attribute %r is not allowed in RelaxAICode "
                "(external API catalogue/secrets; use api_call)." % (name,)
            )
        if name in RELAXAICODE_ORM_WRITE_ATTRS:
            raise AttributeError(
                "Access to ORM mutator %r via getattr is not allowed in RelaxAICode "
                "(use propose_safe_operations for writes)." % (name,)
            )
        if name in DANGEROUS_ATTR_NAMES:
            raise AttributeError(
                "Access to attribute %r is not allowed in RelaxAICode (sandbox)." % (name,)
            )
        if len(name) >= 5 and name.startswith('__') and name.endswith('__'):
            raise AttributeError(
                "Access to dunder attribute %r is not allowed in RelaxAICode (sandbox)." % (name,)
            )
    return getattr(obj, name, *default)


def guarded_import(name, *args, **kwargs):
    """
    Guarda para bloquear imports peligrosos incluso si se llaman dinámicamente.
    Esta función se añade como __import__ al contexto para bloquear imports dinámicos.
    Listas compartidas con el AST (validators.py).
    """
    # Obtener nombre del módulo (sin submódulos)
    module_name = name.split('.')[0] if '.' in name else name

    # urllib.parse: funciones puras de texto (quote, urlencode, urlparse, parse_qs,
    # urljoin...), sin red ni FS. Se permite EXCLUSIVAMENTE la forma
    # `from urllib.parse import <nombre>` (fromlist no vacío), que liga solo las
    # funciones. `import urllib.parse` (fromlist vacío) queda bloqueado porque ligaría
    # el paquete `urllib`, desde el que se podría alcanzar urllib.request (red).
    if name == 'urllib.parse':
        fromlist = kwargs.get('fromlist')
        if fromlist is None and len(args) >= 3:
            fromlist = args[2]
        if fromlist:
            return __import__(name, *args, **kwargs)
        raise ImportError(
            "Use 'from urllib.parse import quote, urlencode, urlparse'. "
            "'import urllib.parse' is not allowed (it would expose urllib)."
        )

    if module_name in RELAXAICODE_DANGEROUS_MODULES:
        raise ImportError(_unsafe_import_error(module_name))

    # Ayudantes internos de módulos seguros (imports perezosos de CPython).
    if module_name in RELAXAICODE_SAFE_INTERNAL_MODULES:
        return __import__(name, *args, **kwargs)

    if module_name in RELAXAICODE_SAFE_MODULES:
        return __import__(name, *args, **kwargs)

    raise ImportError(_unsafe_import_error(module_name))


def build_safe_context(controller, operation_type='read', previous_result=None, env_override=None):
    """
    Construye el contexto seguro para ejecutar código Python nativo.
    
    Args:
        controller: Instancia del controlador para acceder a _get_env_for_operation
        operation_type: 'read' o 'write' según el tipo de operación
        previous_result: Resultado de una ejecución previa (para Fase 2: presentación)
        env_override: Si se proporciona, se usa este env en vez de derivarlo del
            controlador. Sirve para inyectar la "caja A" (cursor READ ONLY) en la
            ejecución de relaxaicode de lectura.
    
    Returns:
        dict: Contexto seguro con builtins limitados y módulos seguros
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
        _ZoneInfo = None

    # `string` RECORTADO: se expone sin Formatter/Template. string.Formatter()
    # .get_field()/.vformat() devuelven el OBJETO real (no su repr), permitiendo
    # recorrer clases hasta object.__subclasses__ sin usar '.' ni getattr (H3).
    # El AST ya bloquea esos nombres; recortar el módulo expuesto es defensa en
    # profundidad. Se conservan constantes/funciones útiles (ascii_letters,
    # digits, punctuation, capwords, whitespace…).
    _safe_string = _types.SimpleNamespace(**{
        _k: getattr(_string, _k)
        for _k in dir(_string)
        if not _k.startswith('_') and _k not in ('Formatter', 'Template')
    })

    # Funciones built-in permitidas
    ALLOWED_BUILTINS_NAMES = [
        'len', 'sum', 'max', 'min', 'sorted', 'range',
        'enumerate', 'zip', 'map', 'filter', 'reversed',
        'int', 'float', 'str', 'list', 'dict', 'tuple', 'set',
        'bytes', 'bytearray', 'memoryview', 'frozenset',
        'bool', 'type', 'isinstance', 'issubclass', 'callable', 'abs', 'round', 'pow',
        'divmod', 'any', 'all', 'hasattr', 'getattr',
        # 'setattr'/'delattr' eliminados: permitían escritura ORM encubierta
        # (setattr(rec, 'campo', valor)) saltándose el detector y la caja B.
        'iter', 'next', 'slice', 'hash', 'id',
        'ord', 'chr', 'bin', 'hex', 'oct',
        'repr', 'ascii', 'format',
    ]
    
    # Crear diccionario con las funciones permitidas
    ALLOWED_BUILTINS = {}
    for name in ALLOWED_BUILTINS_NAMES:
        if hasattr(_builtins, name):
            ALLOWED_BUILTINS[name] = getattr(_builtins, name)
    
    # Añadir __import__ guardado
    ALLOWED_BUILTINS['__import__'] = guarded_import

    # getattr ENDURECIDO: reemplaza el builtin crudo por guarded_getattr para
    # cerrar el acceso dinámico a atributos peligrosos con nombre construido en
    # runtime (H1). El AST cubre los literales; esto cubre los dinámicos.
    ALLOWED_BUILTINS['getattr'] = guarded_getattr
    
    # Obtener entorno de Odoo (o el inyectado: caja A en READ ONLY)
    env = env_override if env_override is not None else controller._get_env_for_operation(operation_type)
    
    # Extraer variables de infraestructura (Protocolo Técnico)
    user = env.user
    company = env.company
    
    # Información de versión de Odoo
    try:
        import odoo
        odoo_version = odoo.release.version
        odoo_series = odoo.release.series if hasattr(odoo.release, 'series') else odoo_version
    except (ImportError, AttributeError):
        odoo_version = '14.0'
        odoo_series = '14.0'

    try:
        _dbname = env.cr.dbname or ''
    except Exception:
        _dbname = ''
    
    # Obtener información de locale del usuario/empresa
    user_lang = 'en_US'  # Base Default
    locale_info = {'thousands_sep': ',', 'decimal_sep': '.', 'date_format': '%Y-%m-%d', 'csv_sep': ','}
    
    import logging
    _logger = logging.getLogger(__name__)
    
    try:
        # Locale de la sesión del usuario (res.lang) = fuente de verdad para
        # separadores y fechas. corporate_terms solo rellena huecos, no pisa.
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
                # No pisar convenciones de res.lang (evita locale errático).
                locale_info[key] = value

        _logger.info(
            'MCP ContextBuilder: locale %s → %s', user_lang, locale_info,
        )

    except Exception as e:
        _logger.warning(f"MCP DEBUG [ContextBuilder]: Error resolving locale: {e}")
    
    # Reloj del usuario (huso de sesión), no el UTC del proceso/contenedor.
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

    # Construir contexto seguro
    safe_context = {
        '__builtins__': ALLOWED_BUILTINS,
        '__import__': guarded_import,
        
        # Entorno de Odoo (catálogos ai.api.server / ai.context fuera del ORM)
        'env': GuardedSandboxEnv(env),
        
        'odoo_version': odoo_version,
        'odoo_series': odoo_series,
        
        # Odoo Objects
        'user': user,
        'company': company,
        
        # Variables de locale (disponibles directamente en el código generado)
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
        'dbname': _dbname,
        'db_name': _dbname,
        'database': _dbname,
        'company_name': company.name,
        'company_id': company.id,
        'today': _user_today,
        'now': _user_now,
        'server_today': _user_today.isoformat(),
        
        # Excepciones estándar (necesarias para try/except)
        'NameError': NameError,
        'ValueError': ValueError,
        'TypeError': TypeError,
        'AttributeError': AttributeError,
        'KeyError': KeyError,
        'IndexError': IndexError,
        'ImportError': ImportError,
        'Exception': Exception,
        
        # Módulos seguros disponibles directamente
        'datetime': _datetime,
        # Alias de datetime que el LLM usa sin import (date.today(), timedelta(…)).
        # Contextos/docs enseñan date.today(); sin estos nombres → NameError
        # "name 'date' is not defined" en código fresco.
        'date': _datetime.date,
        'timedelta': _datetime.timedelta,
        'timezone': _datetime.timezone,
        'collections': _collections,
        'itertools': _itertools,
        'functools': _functools,
        'math': _math,
        'statistics': _statistics,
        'decimal': _decimal,
        'json': _json,  # Módulo JSON para serialización (disponible directamente)
        'base64': _base64,
        'hashlib': _hashlib,
        're': _re,
        'string': _safe_string,  # sin Formatter/Template (ver arriba)
        'operator': _operator,
        'csv': _csv,
        'io': _io,
        'copy': _copy,
        'uuid': _uuid,
        'random': _random,
        'calendar': _calendar,
        'textwrap': _textwrap,
        'unicodedata': _unicodedata,
    }
    if _ZoneInfo is not None:
        safe_context['ZoneInfo'] = _ZoneInfo

    # Presentación de grids (pijama / pasteles): misma paleta que el render HTML.
    try:
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import (
            PASTEL_ROW_COLORS,
            apply_pajama_coloring,
        )
        safe_context['PASTEL_ROW_COLORS'] = PASTEL_ROW_COLORS
        safe_context['apply_pajama_coloring'] = apply_pajama_coloring
    except Exception:
        pass

    # Formateo numérico por locale (pk_*): disponible en todo skill/relaxaicode.
    # Evita `{:,.2f}` (inglés) skill a skill. Tablas `data`/`groups` ya usan
    # el mismo criterio vía relaxaicode_render; esto cubre HTML a mano.
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

    # Siempre definidos (None si no hay dataset): evita `if 'x' in locals()/dir()`
    # que el AST rechaza y provocaba rondas improductivas.
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

    # Parámetros opcionales de skills/consultas: siempre presentes (None) para
    # poder escribir `if lugar:` / `if anio:` sin introspection prohibida.
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
