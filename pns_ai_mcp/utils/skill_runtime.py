# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Runtime genérico de skills: bootstrap, fast-path y presenters.

El motor es AGNÓSTICO de dominio: no sabe qué es la meteorología, la
facturación ni nada concreto. Toda esa lógica vive en el ``code_body`` del
skill (en su propio módulo). Aquí solo hay mecanismos genéricos.

Contrato (cualquier skill)
--------------------------
``code_body`` puede devolver un ``result`` dict con:

- ``propose_steps``: lista Safe Plan. Si todos los pasos son auto-confirmables
  (``fetch_url`` en whitelist **o** ``api_call`` a servidor ``trusted``), el
  servidor los ejecuta sin ronda LLM ni toast intermedio.
- ``continue``: si es verdadero y se ejecutaron ``propose_steps``, el motor
  vuelve a llamar al ``code_body`` con los resultados en la global
  ``previous_result``. Así un skill encadena fases dependientes (p. ej.
  geocodificar → pronóstico → presentar) por sí mismo, en varias rondas.
- ``presentation`` / flags ``__return_direct__`` + ``data``|``groups``|
  ``sections``|``tables``|``formatted_text``: respuesta ya lista → HTML al chat
  sin tools. El skill compone también su ``footer`` (el motor no inventa pies).
- Espera de args (genérica): ficha de help markdown sin filas + invocación
  sin args → el siguiente mensaje humano sin slash reanuda el skill. Flag
  explícito ``__await_skill_args__`` True/False para forzar u optar por no
  esperar. Help (``?``) nunca espera.
- ``__skill_state__``: dict libre que el skill quiere recuperar en la ronda
  siguiente. Vuelve como global ``skill_state`` del sandbox (``{}`` en una
  invocación nueva). El motor lo transporta sin mirar dentro: qué slots
  existen y cuándo están completos lo decide **el skill**, no el motor.
- Metadatos libres para el LLM si no hay fast-path.

Presenters (opcional): registro genérico ``register_presenter`` para que un
módulo aporte formateadores post-fetch. El motor NO trae ninguno de fábrica.
"""
from __future__ import annotations

import json
import logging
import re
import shlex

_logger = logging.getLogger(__name__)

# Callables: (exec_result, steps=None, meta=None) -> presentation dict | None
_PRESENTERS = []


def register_presenter(fn):
    """Decorador / registro de formateadores deterministas post-fetch."""
    if fn not in _PRESENTERS:
        _PRESENTERS.append(fn)
    return fn


# Parámetros: determinista primero (`parse_skill_arguments` + fechas relativas
# en ``skill_dates``). Si el skill declara ``param_schema`` y queda texto libre
# sin resolver, el motor puede pedir UNA extracción corta al LLM (opt-in).
# Sin enrutado NL ni continuidad pegajosa.


# Canonical forms for temporal sandbox keys already defined by parse_skill_arguments.
# Non-matching values count as unresolved holes → hybrid LLM fills them.
_CANONICAL_PARAM = {
    'fecha': re.compile(r'^\d{4}-\d{2}-\d{2}$'),
    'mes': re.compile(r'^\d{4}-\d{2}$'),
    'start_date': re.compile(r'^\d{4}-\d{2}-\d{2}$'),
    'end_date': re.compile(r'^\d{4}-\d{2}-\d{2}$'),
}
_RANGE_PARAM = re.compile(
    r'^\d{4}-\d{2}-\d{2}(\.\.\d{4}-\d{2}-\d{2})?$'
)


def _param_value_resolved(key, val):
    """True when ``val`` is a usable value for ``key`` (empty → False)."""
    if val in (None, '', []):
        return False
    if key == 'periodos':
        items = val if isinstance(val, (list, tuple)) else [val]
        ok = 0
        for item in items:
            if isinstance(item, dict):
                a = (item.get('from') or item.get('start') or '')
                b = (item.get('to') or item.get('end') or a)
                s = '%s..%s' % (str(a)[:10], str(b)[:10])
            else:
                s = str(item).strip().replace(' ', '')
                s = s.replace('/', '-')
            if _RANGE_PARAM.match(s) or _CANONICAL_PARAM['fecha'].match(s):
                ok += 1
        return ok > 0
    pat = _CANONICAL_PARAM.get(key)
    if pat is None:
        return True
    return bool(pat.match(str(val).strip()))


def _schema_key_is_temporal(key, spec):
    """True when the key (or its desc) is a date/month/range slot."""
    if key in _CANONICAL_PARAM or key == 'periodos':
        return True
    spec = spec if isinstance(spec, dict) else {}
    desc = str(spec.get('desc') or spec.get('description') or '')
    return 'YYYY-MM-DD' in desc or 'YYYY-MM' in desc


def build_param_extraction_prompt(schema, raw, locale=None, arg_hint=''):
    """Build (system, user) so the LLM maps free text → formal schema JSON.

    ``schema`` is ``{key: {"type": ..., "desc": ...}}``. ``arg_hint`` is the
    skill's formal examples. Short/cheap call: it picks a contract token,
    never business data. ISO resolution only for temporal keys.
    """
    import datetime as _dt
    today = _dt.date.today().isoformat()
    lines = []
    temporal = []
    for key, spec in (schema or {}).items():
        spec = spec if isinstance(spec, dict) else {}
        typ = spec.get('type') or 'string'
        desc = spec.get('desc') or spec.get('description') or ''
        lines.append('- "%s" (%s): %s' % (key, typ, desc))
        if _schema_key_is_temporal(key, spec):
            temporal.append(key)
    keys = ', '.join('"%s"' % k for k in (schema or {}).keys())
    locale_hint = (' Locale: %s.' % locale) if locale else ''
    hint = (arg_hint or '').strip()
    hint_block = (
        'Formal examples (arg_hint): %s\n' % hint
    ) if hint else ''
    temporal_block = ''
    if temporal:
        temporal_block = (
            'Temporal keys (%s): resolve relatives with Today '
            '(day → YYYY-MM-DD, month → YYYY-MM). '
            'For period arrays use "YYYY-MM-DD..YYYY-MM-DD" (same day twice '
            'if single day). Weekend phrases → one range Saturday..Sunday of '
            'that weekend (if Today is Sat/Sun, that weekend). Several ranges '
            '→ several array items. Do NOT return a weekday-only day for a '
            'weekend request. '
        ) % (', '.join('"%s"' % k for k in temporal))
    system = (
        'You are a parameter-extraction function. From the user request, return '
        'EXCLUSIVELY a valid JSON object (no prose, no markdown fences) with '
        'EXACTLY these keys: %s.\n'
        'Today is %s.%s\n'
        'Key definitions:\n%s\n'
        '%s'
        'Rules: use null when a value is absent; do NOT invent keys or '
        'business facts. Map informal prose onto this formal contract: if the '
        'phrase is not an exact token, pick the closest accepted formal value '
        'from the key definitions and the examples. Do not copy '
        'natural-language phrases into a field. '
        '%s'
        'Return {"_reject": true} and nothing else only when the text is junk '
        'and no formal value is a reasonable match. '
        'For ambiguous place names add the country after a comma. '
        'Reply with JSON only.'
    ) % (
        keys, today, locale_hint, '\n'.join(lines),
        hint_block, temporal_block,
    )
    return system, (raw or '')


def parse_and_validate_params(text, schema):
    """LLM text → dict validated against ``schema`` (or None if unusable)."""
    if not text or not isinstance(schema, dict) or not schema:
        return None
    s = str(text).strip()
    s = re.sub(r'^```(?:json)?', '', s).strip()
    s = re.sub(r'```$', '', s).strip()
    start, end = s.find('{'), s.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(s[start:end + 1])
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if data.get('_reject') is True:
        return {'_skill_args_reject': True}
    out = {}
    for key, spec in schema.items():
        spec = spec if isinstance(spec, dict) else {}
        typ = (spec.get('type') or 'string').lower()
        val = data.get(key)
        if val is None:
            out[key] = None
        elif typ == 'array':
            if isinstance(val, (list, tuple)):
                items = []
                for v in val:
                    if isinstance(v, dict):
                        a = (v.get('from') or v.get('start') or '')
                        b = (v.get('to') or v.get('end') or a)
                        a, b = str(a)[:10], str(b)[:10]
                        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', a or ''):
                            if b and b != a and re.fullmatch(r'\d{4}-\d{2}-\d{2}', b):
                                items.append('%s..%s' % (a, b))
                            else:
                                items.append(a)
                    else:
                        s = str(v).strip().replace(' ', '')
                        if s:
                            items.append(s)
                out[key] = items or None
            elif isinstance(val, str) and val.strip():
                out[key] = [val.strip()]
            else:
                out[key] = None
        elif typ in ('integer', 'number'):
            try:
                out[key] = int(val) if typ == 'integer' else float(val)
            except (TypeError, ValueError):
                out[key] = None
        else:
            out[key] = (str(val).strip() or None)
    if all(v is None for v in out.values()):
        return None
    return out


def _skill_dates():
    """Load skill_dates whether we are a package module or a flat unit-test load."""
    try:
        from . import skill_dates as mod
        return mod
    except ImportError:
        import importlib.util
        import os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skill_dates.py')
        spec = importlib.util.spec_from_file_location('skill_dates', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def enrich_params_with_dates(params):
    """Fill ``fecha`` from known day phrases (hoy, weekdays, ISO). Zero LLM cost.

    Does NOT resolve months/periods — those stay unresolved so hybrid LLM runs.
    """
    if not isinstance(params, dict):
        return params
    if _param_value_resolved('fecha', params.get('fecha')):
        return params
    try_resolve_date = _skill_dates().try_resolve_date
    for key in ('lugar', 'arguments'):
        raw = params.get(key)
        if not raw:
            continue
        resolved = try_resolve_date(str(raw))
        if resolved is not None:
            params['fecha'] = resolved.isoformat()
            break
    return params


def schema_needs_ai_resolution(params, schema, raw, leftover=None):
    """True when free text remains and schema still has holes after determinism.

    Hybrid contract: day phrases may be enriched; everything else unresolved
    (months, places, sort synonyms, …) → one short LLM call. No extra parsers.
    ``leftover`` is the unbound prose after ordinal bind (empty → no LLM).
    """
    raw = (raw or '').strip()
    if not raw or not isinstance(schema, dict) or not schema:
        return False
    sd = _skill_dates()
    # Help/?/ayuda is always deterministic (skill help card).
    # Never spend an LLM call to "resolve" it into periodo/mes/…
    if sd.skill_args_are_help(raw):
        return False
    params = params or {}
    holes = [
        k for k in schema.keys()
        if not _param_value_resolved(k, params.get(k))
    ]
    # ``arguments`` mirrors the raw slash text — never a reason alone to call AI.
    holes = [k for k in holes if k != 'arguments']
    if not holes:
        return False

    lugar = (params.get('lugar') or '').strip()
    blob = lugar or raw
    if sd.skill_args_are_help(lugar) or sd.skill_args_are_help(blob):
        return False

    # Schema is only ``fecha`` and day enrich already filled it.
    if (
        set(schema.keys()) <= {'fecha'}
        and _param_value_resolved('fecha', params.get('fecha'))
    ):
        return False
    if (
        set(schema.keys()) <= {'fecha'}
        and sd.try_resolve_date(blob) is not None
    ):
        return False

    if leftover is None:
        free_blob = lugar or leftover_free_text(raw)
    else:
        free_blob = leftover

    if not free_blob:
        return False
    # Known day phrase with no other holes beyond fecha → determinism enough.
    if (
        sd.try_resolve_date(free_blob) is not None
        and all(k == 'fecha' or k in ('arguments',) for k in holes)
    ):
        return False
    # Unresolved free text + holes → LLM (the whole point of hybrid params).
    return True


def leftover_free_text(raw):
    """Slash text that is not ``key=value`` and not an ISO / year token."""
    leftovers = []
    for part in _split_arg_tokens(raw):
        if _is_kv_token(part):
            continue
        if re.fullmatch(r'\d{4}(-\d{2}(-\d{2})?)?', part or ''):
            continue
        leftovers.append(part)
    return ' '.join(leftovers).strip()


def leftover_after_ordinals(raw, params, bound_map):
    """Prose still unbound after ordinal assignment (empty → skip the LLM)."""
    if bound_map:
        bits = [
            tok for key, tok in bound_map.items()
            if not _param_value_resolved(key, (params or {}).get(key))
        ]
        return ' '.join(str(b) for b in bits if b).strip()
    return leftover_free_text(raw)


def _split_arg_tokens(raw):
    raw = (raw or '').strip()
    if not raw:
        return []
    try:
        return shlex.split(raw)
    except ValueError:
        return raw.split()


def _is_kv_token(part):
    return '=' in (part or '') and not part.startswith(('http://', 'https://'))


def kv_keys_from_raw(raw):
    keys = set()
    for part in _split_arg_tokens(raw):
        if not _is_kv_token(part):
            continue
        key = part.split('=', 1)[0].strip()
        if key.isidentifier():
            keys.add(key)
    return keys


def positional_tokens(raw):
    """Tokens that are not ``clave=valor`` (order preserved)."""
    return [part for part in _split_arg_tokens(raw) if not _is_kv_token(part)]


def _coerce_schema_value(spec, token):
    spec = spec if isinstance(spec, dict) else {}
    typ = (spec.get('type') or 'string').lower()
    if typ == 'integer':
        try:
            return int(token)
        except (TypeError, ValueError):
            return token
    if typ == 'number':
        try:
            return float(token)
        except (TypeError, ValueError):
            return token
    if typ == 'array':
        if isinstance(token, (list, tuple)):
            return list(token)
        s = str(token).strip()
        if ',' in s:
            return [p.strip() for p in s.split(',') if p.strip()]
        return [s] if s else None
    return token


def apply_schema_ordinals(params, schema, raw):
    """Bind leftover tokens to empty schema keys, in declaration order.

    ``clave=valor`` wins. Catch-all ``lugar`` from ``parse_skill_arguments``
    does not count as already set. Bind only when ``len(tokens) <=`` empty
    keys (more tokens = prose → LLM). Returns ``(params, bound_map)``.
    """
    params = params if isinstance(params, dict) else {}
    if not isinstance(schema, dict) or not schema:
        return params, {}
    tokens = positional_tokens(raw)
    if not tokens:
        return params, {}
    filled_kv = kv_keys_from_raw(raw)
    empty = []
    for key in schema:
        if key == 'arguments' or key in filled_kv:
            continue
        if key == 'lugar':
            empty.append(key)
            continue
        if _param_value_resolved(key, params.get(key)):
            continue
        empty.append(key)
    if not empty or len(tokens) > len(empty):
        return params, {}
    bound = {}
    for key, tok in zip(empty, tokens):
        params[key] = _coerce_schema_value(schema.get(key), tok)
        bound[key] = tok
    return params, bound


def skill_args_unmapped(raw, resolved_params, schema, args_policy='default'):
    """True when leftover text cannot be mapped onto the skill schema.

    Empty args and help tokens never count. ``args_policy=none`` rejects any
    non-empty leftover. Without a formal schema, leftover travels to the
    sandbox as ``arguments`` (not a miss). ``arguments`` in the schema is a
    catch-all, not a formal hit. A schema that is only ``arguments`` is not a
    miss. With other formal keys, leftover plus zero resolved formal keys
    is a miss (LLM failed or the phrase is junk).
    """
    skill_args_are_help = _skill_dates().skill_args_are_help
    raw = (raw or '').strip()
    if not raw or skill_args_are_help(raw):
        return False
    policy = (args_policy or 'default').strip() or 'default'
    leftover = leftover_free_text(raw)
    if policy == 'none':
        return True
    if not leftover:
        return False
    if not isinstance(schema, dict) or not schema:
        return False
    formal_keys = [key for key in schema if key != 'arguments']
    if not formal_keys:
        return False
    resolved = [
        key for key in formal_keys
        if _param_value_resolved(key, (resolved_params or {}).get(key))
    ]
    return not resolved


def merge_hybrid_params(det, norm, schema, raw, args_policy='default'):
    """Combine deterministic fill + LLM JSON. ``_reject`` is not a veto.

    Returns the merged dict, or ``{'_skill_args_reject': True}`` only when
    leftover prose still has no usable formal key (``arguments`` is a
    catch-all, not a formal hit).
    """
    det = dict(det or {})
    filled = None
    if isinstance(norm, dict) and not norm.get('_skill_args_reject'):
        filled = dict(norm)
        for key in list(filled.keys()):
            if key in ('fecha', 'mes', 'start_date', 'end_date'):
                if (
                    filled[key] is not None
                    and not _param_value_resolved(key, filled[key])
                ):
                    filled[key] = None
    merged = dict(filled or {})
    merged.update(det)
    if skill_args_unmapped(raw, merged, schema, args_policy):
        return {'_skill_args_reject': True}
    return merged or None


def parse_skill_arguments(arguments):
    """Parámetros de sandbox desde args del slash.

    Siempre define ``arguments``, ``lugar``, ``fecha``, ``start_date``,
    ``end_date``, ``anio``, ``year`` (None si faltan). Acepta:

    - ``clave=valor`` (start_date=2025-01-01, anio=2025, …)
    - años sueltos: ``2025`` → 2025-01-01 .. 2025-12-31
    - dos años: ``2023 2025`` → 2023-01-01 .. 2025-12-31
    - fechas ISO: ``2024-01-01 2024-06-30``
    - resto (sin fechas): texto libre en ``lugar`` (genérico; el skill decide)

    El motor NO interpreta el dominio (meteo, etc.): entrega ``arguments`` (texto
    crudo) y ``lugar`` (resto sin fechas). Fechas relativas comunes se enriquecen
    después vía ``enrich_params_with_dates`` / IA opt-in.
    """
    raw = (arguments or '').strip()
    out = {
        'arguments': raw or None,
        'lugar': None,
        'fecha': None,
        'start_date': None,
        'end_date': None,
        'anio': None,
        'year': None,
        'mes': None,
    }
    if not raw:
        return out
    try:
        parts = shlex.split(raw)
    except ValueError:
        parts = raw.split()

    years = []
    iso_dates = []
    other = []
    for i, part in enumerate(parts):
        out['arg%d' % i] = part
        if '=' in part and not part.startswith(('http://', 'https://')):
            key, val = part.split('=', 1)
            key = key.strip()
            if key.isidentifier():
                out[key] = val
                if key in ('anio', 'year', 'año') and re.fullmatch(r'\d{4}', val or ''):
                    y = int(val)
                    out['anio'] = y
                    out['year'] = y
                if key == 'mes' and re.fullmatch(r'\d{4}-\d{2}', val or ''):
                    out['mes'] = val
                continue
        if re.fullmatch(r'\d{4}', part):
            y = int(part)
            if 1990 <= y <= 2100:
                years.append(y)
                continue
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', part):
            iso_dates.append(part)
            continue
        if re.fullmatch(r'\d{4}-\d{2}', part):
            # YYYY-MM → mes (skills tipo nominas)
            if not out.get('mes'):
                out['mes'] = part
            continue
        other.append(part)

    if out.get('start_date') and not out.get('end_date'):
        out['end_date'] = out['start_date']
    if iso_dates and not out.get('start_date'):
        out['start_date'] = iso_dates[0]
        out['end_date'] = iso_dates[-1]
    if years and not out.get('start_date'):
        out['anio'] = years[0]
        out['year'] = years[0]
        out['start_date'] = '%04d-01-01' % years[0]
        out['end_date'] = '%04d-12-31' % years[-1]
    elif out.get('anio') or out.get('year'):
        y = int(out.get('anio') or out.get('year'))
        out['anio'] = y
        out['year'] = y
        if not out.get('start_date'):
            out['start_date'] = '%04d-01-01' % y
        if not out.get('end_date'):
            out['end_date'] = '%04d-12-31' % y

    # Texto libre restante → ``lugar`` (genérico, sin interpretar el dominio).
    # El skill (meteo u otro) parsea ``arguments`` / ``lugar`` a su gusto.
    if (
        out.get('lugar') is None
        and not years
        and not iso_dates
        and not out.get('start_date')
    ):
        rest = ' '.join(other).strip() or raw
        if rest and '=' not in rest:
            out['lugar'] = rest or None
    return out


def bootstrap_skill_code_body(env, code, arguments='', skill_code='skill',
                              extra_params=None, previous_result=None,
                              diag=None):
    """Ejecuta code_body en sandbox seguro. Devuelve ``result`` dict o None.

    ``extra_params`` (opcional): dict de parámetros deterministas ya resueltos.
    Se fusiona sobre el parse determinista: un valor no-None **sobrescribe** al
    determinista; un valor None solo **asegura** que la clave exista en el
    sandbox (no borra el determinista). Así el skill puede leer siempre las
    claves del schema sin NameError.

    ``previous_result`` (opcional): resultados de los ``fetch_url`` ejecutados en
    la ronda anterior (ver ``try_skill_fast_path``). Se inyecta como global
    ``previous_result`` (None en la 1ª ronda) para que un skill orqueste varias
    fases dependientes (p. ej. geocodificar → pronóstico → presentar) SIN que el
    motor sepa nada del dominio.

    ``diag`` (dict opcional): si el ``code_body`` lanza, se guarda la excepción
    en ``diag['bootstrap_error']`` para que el error mostrado al usuario sea
    accionable (no una degradación silenciosa).
    """
    code = (code or '').strip()
    if not code:
        return None
    params = parse_skill_arguments(arguments)
    enrich_params_with_dates(params)
    if extra_params:
        for key, val in extra_params.items():
            if val is not None:
                params[key] = val
            else:
                params.setdefault(key, None)
    try:
        from ..controllers.context_builder import build_safe_context

        class _Ctrl(object):
            def __init__(self, _env):
                self.env = _env

            def _get_env_for_operation(self, _op):
                return self.env

            def _get_user_locale(self):
                # Misma cascada que el resto del MCP: sesión → usuario → en_US
                try:
                    from odoo.http import request as http_request
                    ctx_lang = (
                        http_request.env.context.get('lang')
                        if http_request and getattr(http_request, 'env', None)
                        else None
                    )
                except Exception:
                    ctx_lang = None
                try:
                    return (
                        ctx_lang
                        or self.env.context.get('lang')
                        or self.env.user.lang
                        or 'en_US'
                    )
                except Exception:
                    return 'en_US'

        ctx = build_safe_context(
            _Ctrl(env), 'read', previous_result=previous_result,
        )
        ctx.setdefault('previous_result', None)
        for key, val in params.items():
            ctx[key] = val
        exec(
            compile(code, '<skill:%s>' % (skill_code or 'x'), 'exec'),
            ctx, ctx,
        )
        result = ctx.get('result')
        if isinstance(result, dict):
            # Skill-authored help/ask cards: stamp trust so report mode can
            # paint HTML without rejecting formatted_text as sandbox junk.
            if result.get('formatted_text') and (
                result.get('__return_direct__')
                or result.get('__stop_after_direct__')
            ):
                result.setdefault('__fmt_type__', 'author_html')
            return result
        # Contrato único (ver norma §4): el code_body DEBE asignar un dict a
        # `result`. Cualquier otra forma es un error del skill, no algo que el
        # motor deba adivinar/envolver. Se reporta con motivo claro.
        if isinstance(diag, dict):
            diag['result_not_dict'] = True
            diag['result_type'] = type(result).__name__
            diag['bootstrap_error'] = (
                "code_body asignó `result` de tipo %s; el contrato exige un dict "
                "(data / groups / formatted_text / propose_steps)."
                % type(result).__name__
            )
        return None
    except Exception as exc:
        from .skill_errors import friendly_skill_error
        friendly = friendly_skill_error(exc, env)
        if isinstance(diag, dict):
            diag['bootstrap_error'] = friendly
        _logger.warning(
            'Skill bootstrap failed for %s: %s: %s',
            skill_code, type(exc).__name__, exc,
        )
        return None


def is_fetch_url_only_plan(steps):
    """True si todos los pasos son ``fetch_url`` (utilidad auxiliar).

    El fast-path usa ``_all_steps_auto_confirmable`` (``fetch_url`` whitelist +
    ``api_call`` trusted); no llama a esta función.
    """
    if not isinstance(steps, list) or not steps:
        return False
    return all(
        isinstance(s, dict) and s.get('op') == 'fetch_url' for s in steps
    )


def collect_external_sources(steps):
    """Hosts / etiquetas API de pasos o resultados Safe Plan.

    fetch_url → hostname; api_call / mcp_call → ``API: server/tool``.
    Ignora pasos sin dato o con ``success=False``. Agnóstico de dominio.
    """
    from urllib.parse import urlparse
    out = set()
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        if step.get('success') is False:
            continue
        op = step.get('op')
        if op == 'fetch_url' and step.get('url'):
            try:
                host = urlparse(step['url']).hostname
                if host:
                    out.add(host)
            except Exception:
                pass
        elif op in ('api_call', 'mcp_call') and step.get('server'):
            srv = step.get('server')
            tool = step.get('tool')
            out.add('API: %s/%s' % (srv, tool) if tool else 'API: %s' % srv)
    return sorted(out)


def _has_presentable_payload(pres):
    """True if dict already carries a renderable envelope for direct return."""
    if not isinstance(pres, dict):
        return False
    return (
        pres.get('data') is not None
        or pres.get('groups') is not None
        or pres.get('sections') is not None
        or pres.get('tables') is not None
        or bool(pres.get('formatted_text'))
    )


def _stamp_author_html(pres):
    """Platform trust mark for skill-authored HTML (not free LLM sandbox)."""
    if isinstance(pres, dict) and pres.get('formatted_text'):
        if not pres.get('__fmt_type__'):
            pres['__fmt_type__'] = 'author_html'
    return pres


def presentation_from_bootstrap(bootstrap):
    """Si el code_body ya dejó una presentation, la devuelve.

    A presentable envelope (``formatted_text`` / ``data`` / ``groups`` /
    ``sections`` / ``tables``) is enough. ``__return_direct__`` is optional
    (captured skills often omit it). ``propose_steps`` wins: do not paint
    a leftover card and skip the fetch round.
    """
    if not isinstance(bootstrap, dict):
        return None
    pres = bootstrap.get('presentation')
    if _has_presentable_payload(pres):
        return _stamp_author_html(dict(pres))
    steps = bootstrap.get('propose_steps')
    if isinstance(steps, list) and steps:
        return None
    if _has_presentable_payload(bootstrap):
        return _stamp_author_html(dict(bootstrap))
    return None


def _has_row_payload(presentation):
    """True when the envelope already carries row/group/table data."""
    if not isinstance(presentation, dict):
        return False
    for key in ('data', 'items', 'groups', 'sections', 'tables'):
        val = presentation.get(key)
        if isinstance(val, list) and val:
            return True
    return False


def skill_state_from_params(raw):
    """Decode the state a skill left behind (session JSON blob or dict).

    Never raises: a corrupt or foreign blob simply means "no state".
    """
    params = raw
    if isinstance(params, (bytes, bytearray)):
        params = params.decode('utf-8', 'ignore')
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except Exception:
            return {}
    if not isinstance(params, dict):
        return {}
    state = params.get('state')
    return dict(state) if isinstance(state, dict) else {}


def skill_state_for_await(*sources):
    """First non-empty ``__skill_state__`` among the given dicts."""
    for src in sources:
        if not isinstance(src, dict):
            continue
        state = src.get('__skill_state__')
        if isinstance(state, dict) and state:
            return dict(state)
    return {}


def should_await_skill_args(presentation, arguments='', is_help=False,
                            accepts_args=True, args_policy=None):
    """Whether the next non-slash human reply should resume this skill.

    Invariant (no domain): a direct HTML card with no tabular payload, after
    an invocation that did not already carry args, is asking for them.
    A skill that declares no parameters (``accepts_args`` False) cannot be
    waiting for any, so its empty states never turn sticky and never swallow
    the next free-chat message.

    Handing back ``__skill_state__`` also means "I expect a follow-up": that is
    how a multi-question skill stays in the conversation on rounds 2..N, where
    the args are no longer empty. Drop the state (or set the flag to False) on
    the round that finishes the job.

    Explicit ``__await_skill_args__`` True/False overrides. Help never awaits.
    """
    if is_help:
        return False
    if not isinstance(presentation, dict):
        return False
    flag = presentation.get('__await_skill_args__')
    if flag is False:
        return False
    if flag is True:
        return True
    if skill_state_for_await(presentation):
        return True
    policy = (args_policy or '').strip() or 'default'
    if policy in ('default', 'none'):
        return False
    if not accepts_args:
        return False
    if (arguments or '').strip():
        return False
    if not (presentation.get('formatted_text') or '').strip():
        return False
    return not _has_row_payload(presentation)


def try_present(exec_result, steps=None, meta=None):
    """Prueba presenters registrados; primero que devuelva dict gana.

    El motor no registra ninguno de fábrica (agnóstico de dominio). Un módulo
    puede aportar el suyo con ``register_presenter``. Sin presenters, devuelve
    None y el resultado va al LLM para que lo presente.
    """
    meta = meta or {}
    for fn in list(_PRESENTERS):
        try:
            out = fn(exec_result, steps=steps, meta=meta)
            if _has_presentable_payload(out):
                out = dict(out)
                out.setdefault('__return_direct__', True)
                out.setdefault('__stop_after_direct__', True)
                return _stamp_author_html(out)
        except Exception as exc:
            _logger.debug('skill presenter %s skipped: %s', fn, exc)
    return None


def render_presentation_html(presentation, env=None):
    """Dict presentation → HTML chat (o None). Evita import circular con agent_engine."""
    if not isinstance(presentation, dict):
        return None
    presentation = _stamp_author_html(dict(presentation))
    presentation.setdefault('__return_direct__', True)
    presentation.setdefault('__stop_after_direct__', True)
    try:
        from .relaxaicode_render import (
            render_context_from_env,
            render_for_direct_return,
            render_result_html,
            is_tabulable,
            _result_items,
            wrap_bare_images_clickable,
        )
        render_ctx = render_context_from_env(env, result=presentation) if env is not None else None
        ft = presentation.get('formatted_text')
        if ft:
            return wrap_bare_images_clickable(ft)
        rendered = render_for_direct_return(
            presentation,
            presentation.get('summary') or '',
            render_context=render_ctx,
        )
        if rendered:
            return rendered
        if _result_items(presentation) and is_tabulable(presentation):
            return render_result_html(
                presentation,
                presentation.get('summary') or '',
                render_context=render_ctx,
            )
    except Exception as exc:
        _logger.debug('render_presentation_html failed: %s', exc)
    return None


def try_skill_fast_path(env, bootstrap, title='Skill', *, code=None,
                        arguments='', skill_code='skill', extra_params=None,
                        max_rounds=5, diag=None):
    """Ejecuta el ciclo determinista de un skill sin recurrir al LLM.

    Genérico y agnóstico de dominio. En cada ronda el ``code_body`` (ya
    ejecutado en ``bootstrap`` la 1ª vez) devuelve:

    - una **presentación directa** (``presentation`` / ``__return_direct__``
      con ``data``|``groups``|``sections``|``tables``|``formatted_text``)
      → se renderiza a HTML y fin;
    - o ``propose_steps`` **CRUD / mixtos** → crea ``ai.safe.operation`` pendiente
      y devuelve ``verification_id`` (+ HTML corto) para el toast Confirm;
    - o ``propose_steps`` **solo pasos auto-confirmables** (``fetch_url`` en
      whitelist o ``api_call`` a servidor ``trusted``); el motor los ejecuta y,
      si el skill puso ``continue`` verdadero, vuelve a llamar al
      ``code_body`` con los resultados **acumulados** en la global
      ``previous_result`` (siguiente ronda). Así el skill encadena fases
      (geocode → fetch → presentar) sin que el motor conozca
      el dominio.

    Devuelve ``{html, presentation, verification_id, plan, danger_level, title,
    exec_payload}`` o None si no aplica. En skills con ``code_body``, un bail
    se muestra como error claro (no degrada a ReAct).

    ``code`` es el ``code_body`` del skill; si es None solo se evalúa la ronda
    ya provista en ``bootstrap`` (compatibilidad: sin re-ejecución).

    ``diag`` (dict opcional): se rellena con ``reason`` (motivo de la degradación
    al LLM) y ``round`` para poder diagnosticar en el log SIN especular.
    """
    def _bail(reason):
        if isinstance(diag, dict):
            diag['reason'] = reason
            diag['round'] = round_i
        _logger.info('skill fast-path bail [%s]: %s', skill_code, reason)
        return None

    round_i = 0
    if not isinstance(bootstrap, dict):
        return _bail('bootstrap_not_dict')

    try:
        from ..controllers.safe_plan import (
            _all_steps_auto_confirmable,
            create_pending_safe_operation,
            execute_safe_plan,
            validate_safe_plan,
        )
    except Exception as exc:
        return _bail('safe_plan_import_error: %s' % exc)

    prev = None
    for round_i in range(max_rounds):
        if round_i > 0:
            if not code:
                return _bail('no_code_body_for_next_round')
            _bd = {}
            bootstrap = bootstrap_skill_code_body(
                env, code, arguments=arguments, skill_code=skill_code,
                extra_params=extra_params, previous_result=prev, diag=_bd,
            )
            if not isinstance(bootstrap, dict):
                err = _bd.get('bootstrap_error')
                return _bail('reexec_not_dict'
                             + (': %s' % err if err else ''))

        # 1) ¿El skill ya trae una presentación lista?
        direct = presentation_from_bootstrap(bootstrap)
        if direct:
            html = render_presentation_html(direct, env=env)
            if html:
                return {
                    'html': html,
                    'presentation': direct,
                    'verification_id': None,
                    'exec_payload': prev,
                    'sources': collect_external_sources(prev),
                }
            return _bail('presentation_no_html')

        # 2) ¿Propone pasos?
        steps = bootstrap.get('propose_steps')
        if not isinstance(steps, list) or not steps:
            return _bail('no_propose_steps(keys=%s)'
                         % sorted(bootstrap.keys()))

        ok, err = validate_safe_plan(steps, env)
        if not ok:
            return _bail('invalid_plan: %s' % err)

        # Planes no auto-confirmables (CRUD, URL/API no trusted) → toast.
        # Trusted fetch_url + trusted api_call se ejecutan aquí (multi-ronda).
        if not _all_steps_auto_confirmable(env, steps):
            pending = create_pending_safe_operation(
                env, steps,
                title=bootstrap.get('title') or title,
                tool_name='skill:%s' % skill_code,
            )
            if not pending.get('success'):
                return _bail('pending_create_failed: %s'
                             % (pending.get('error') or 'unknown'))
            n_steps = len(steps)
            html = (
                'Prepared <b>%s</b> supervised step(s). '
                '<b>Confirm the toast in Odoo</b> to apply them.'
            ) % n_steps
            return {
                'html': html,
                'presentation': None,
                'verification_id': pending['verification_id'],
                'plan': pending.get('plan') or [],
                'danger_level': pending.get('danger_level') or 'medium',
                'title': pending.get('title') or title,
                'exec_payload': prev,
                'sources': collect_external_sources(prev or steps),
            }

        try:
            round_results = execute_safe_plan(env, steps)
        except Exception as exc:
            from .skill_errors import friendly_skill_error
            _logger.warning(
                'Skill fast-path exec failed for %s: %s: %s',
                skill_code, type(exc).__name__, exc,
            )
            return _bail(friendly_skill_error(exc, env))

        # Acumular resultados de todas las rondas para que el skill pueda
        # paginar (p. ej. varias api_call) y presentar con el histórico completo.
        if prev is None:
            prev = round_results
        elif isinstance(prev, list) and isinstance(round_results, list):
            prev = prev + round_results
        else:
            prev = round_results

        # Sin ``continue`` no hay fase de presentación propia del skill: el motor
        # no tiene presenter de dominio, así que degrada al LLM.
        if not bootstrap.get('continue'):
            return _bail('no_continue_no_presentation')

    return _bail('max_rounds_exhausted')
