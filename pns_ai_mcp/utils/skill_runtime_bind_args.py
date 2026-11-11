# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Bind the arguments of a slash to the schema: dates, defaults, positional values and the final params."""

from __future__ import annotations
import json
import re
import shlex

from .skill_runtime_param_schema import (
    _coerce_schema_value,
    _param_value_resolved,
    _period_as_date_pair,
    _period_fits_key,
    _schema_key_is_year_slot,
    _schema_key_takes_period,
    _token_looks_canonical_temporal,
)

from .skill_runtime_read_values import (
    _apply_schema_kv,
    _coalesce_formal_code_tokens,
    _is_kv_token,
    kv_keys_from_raw,
    _schema_key_is_integer,
    _split_arg_tokens,
    _token_looks_formal_code_csv,
    _token_looks_formal_integer,
)


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
        if not _param_value_resolved(k, params.get(k), schema.get(k))
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


def normalize_unresolved_key(text):
    """Cache key for leftover slash prose: collapse spaces, NFC, casefold.

    Structural only — no locale synonym list.
    """
    s = ' '.join(str(text or '').split())
    if not s:
        return ''
    try:
        import unicodedata
        s = unicodedata.normalize('NFC', s)
    except Exception:
        pass
    return s.casefold()


def relative_param_keys(norm):
    """Keys the IA marked as unstable (time phrase or live ranking)."""
    if not isinstance(norm, dict):
        return ()
    raw = norm.get('_relative')
    if not isinstance(raw, (list, tuple)):
        return ()
    out = []
    for item in raw:
        name = str(item or '').strip()
        if name and not name.startswith('_') and name not in out:
            out.append(name)
    return tuple(out)


def param_cache_payload(norm):
    """IA-filled params worth storing. Relative keys are omitted.

    A leftover whose referent is not stable (time phrase or live ranking)
    must be re-read by IA on the next invoke (one call). Stable keys
    (codes, names, ISO dates) stay cached.
    """
    if not isinstance(norm, dict) or norm.get('_skill_args_reject'):
        return None
    skip = set(relative_param_keys(norm))
    out = {}
    for key, val in norm.items():
        if str(key).startswith('_') or val in (None, '', []):
            continue
        if key in skip:
            continue
        out[key] = val
    return out or None


def schema_required_keys(schema):
    """Identifiers marked required in ``param_schema``."""
    keys = []
    for key, spec in (schema or {}).items():
        if not isinstance(key, str) or key.startswith('_'):
            continue
        if isinstance(spec, dict) and spec.get('required'):
            keys.append(key)
    return keys


def apply_schema_defaults(params, schema, env=None):
    """Copy schema defaults onto empty keys. Does not invent values.

    Tokens from ``skill_param_token_specs`` (``{year}``, ``{year}-n``,
    ``{ytd}``, …) expand when ``env`` is the asking user. Unknown stay.
    """
    from .skill_param_tokens import expand_skill_param_text
    out = dict(params or {})
    for key, spec in (schema or {}).items():
        if not isinstance(spec, dict):
            continue
        default = spec.get('default')
        if default in (None, ''):
            continue
        if not _param_value_resolved(key, out.get(key), spec):
            if env is not None and isinstance(default, str):
                default = expand_skill_param_text(default, env)
            out[key] = _coerce_schema_value(spec, default)
    return out


def missing_required_params(params, schema):
    """Required keys that still have no usable value (after defaults)."""
    filled = apply_schema_defaults(params, schema)
    missing = []
    for key in schema_required_keys(schema):
        spec = schema.get(key) if isinstance(schema.get(key), dict) else {}
        if not _param_value_resolved(key, filled.get(key), spec):
            missing.append(key)
    return missing


def empty_args_need_required_ask(schema):
    """True when an empty slash cannot run because a required key has no default."""
    return bool(missing_required_params({}, schema))


def parse_param_cache_json(raw):
    """JSON object from a cache row, or None if not an object."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return {k: v for k, v in data.items() if not str(k).startswith('_')}


def named_schema_params(raw, schema):
    """``clave=valor`` onto schema keys, and whether every token is named."""
    params = {}
    _apply_schema_kv(params, schema, raw)
    tokens = _split_arg_tokens(raw)
    return params, bool(tokens) and all(_is_kv_token(t) for t in tokens)


def positional_tokens(raw):
    """Tokens that are not ``clave=valor`` (order preserved)."""
    tokens = [part for part in _split_arg_tokens(raw) if not _is_kv_token(part)]
    return _coalesce_formal_code_tokens(tokens)


def _classify_positional(tokens):
    """Split positional tokens into period, code, integer, word.

    A token lands in one bucket. Years and ISO stay periods, not integers.
    """
    period, code, integers, words = [], [], [], []
    for tok in tokens:
        if _token_looks_canonical_temporal(tok):
            period.append(tok)
        elif _token_looks_formal_code_csv(tok):
            code.append(tok)
        elif _token_looks_formal_integer(tok):
            integers.append(tok)
        else:
            words.append(tok)
    return period, code, integers, words


def _bind_periods(params, schema, keys, toks):
    """Each period token goes to the first free key it fits.

    With ``start_date`` and ``end_date`` both free, a range, month, day or
    year fills the pair. A token that fits no key leaves the whole bucket
    unbound, so the short call sees the phrase.
    """
    free = list(keys)
    plan = []
    for tok in toks:
        pair = None
        if 'start_date' in free and 'end_date' in free:
            pair = _period_as_date_pair(tok)
        if pair:
            plan.append(('start_date', pair[0], tok))
            plan.append(('end_date', pair[1], tok))
            free.remove('start_date')
            free.remove('end_date')
            continue
        key = next(
            (k for k in free if _period_fits_key(k, schema.get(k), tok)),
            None,
        )
        if key is None:
            return {}
        plan.append((key, _coerce_schema_value(schema.get(key), tok), tok))
        free.remove(key)
    bound = {}
    for key, val, tok in plan:
        params[key] = val
        bound[key] = tok
    return bound


def _bind_fitting_formal(params, schema, empty, period_toks, code_toks, int_toks):
    """Bind formal tokens that fit their slot. Words are never bound.

    Periods → temporal keys (or an integer year slot). Codes → the other
    string keys. Bare integers → integer keys. Too many for the holes →
    that bucket stays unbound so the short call sees them.
    """
    temporal_empty = [
        k for k in empty
        if _schema_key_takes_period(k, schema.get(k))
    ]
    year_empty = [
        k for k in empty
        if k not in temporal_empty
        and _schema_key_is_year_slot(k, schema.get(k))
    ]
    int_empty = [
        k for k in empty
        if k not in temporal_empty
        and k not in year_empty
        and _schema_key_is_integer(schema.get(k))
    ]
    # A 4-digit year token belongs on a year slot, not on a count.
    if period_toks and not temporal_empty:
        if year_empty:
            temporal_empty = list(year_empty)
        else:
            temporal_empty = list(int_empty)
            int_empty = []
    other_empty = [
        k for k in empty
        if k not in temporal_empty
        and k not in int_empty
        and k not in year_empty
    ]
    bound = {}
    if period_toks:
        bound.update(_bind_periods(params, schema, temporal_empty, period_toks))
    if code_toks:
        csv_keys = [
            k for k in other_empty
            if 'CSV' in str(
                (schema.get(k) or {}).get('desc')
                or (schema.get(k) or {}).get('description')
                or ''
            ).upper()
        ]
        if len(code_toks) > 1 and csv_keys:
            key = csv_keys[0]
            joined = ','.join(str(tok).strip() for tok in code_toks)
            params[key] = _coerce_schema_value(schema.get(key), joined)
            bound[key] = joined
        elif len(code_toks) <= len(other_empty):
            for key, tok in zip(other_empty, code_toks):
                params[key] = _coerce_schema_value(schema.get(key), tok)
                bound[key] = tok
    if int_toks and len(int_toks) <= len(int_empty):
        for key, tok in zip(int_empty, int_toks):
            params[key] = _coerce_schema_value(schema.get(key), tok)
            bound[key] = tok
    return bound


def apply_schema_ordinals(params, schema, raw):
    """Bind formal tokens onto empty schema keys. Words stay unbound.

    ``clave=valor`` wins. Catch-all ``lugar`` from ``parse_skill_arguments``
    does not count as already set. Formal tokens (year, ISO, ``YYYY-MM``,
    range, code CSV, a bare integer) bind by type when they fit. A word
    is not zipped onto the next hole — the short call sees the phrase.
    Returns ``(params, bound_map)``.
    """
    params = params if isinstance(params, dict) else {}
    if not isinstance(schema, dict) or not schema:
        return params, {}
    _apply_schema_kv(params, schema, raw)
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
        if _param_value_resolved(key, params.get(key), schema.get(key)):
            continue
        empty.append(key)
    if not empty:
        return params, {}
    period_toks, code_toks, int_toks, _words = _classify_positional(tokens)
    return params, _bind_fitting_formal(
        params, schema, empty, period_toks, code_toks, int_toks,
    )


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


def merge_hybrid_params(det, norm, schema, raw, args_policy='default', env=None):
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
    explicit_unset = bool(isinstance(filled, dict) and filled.get('_params_unset'))
    merged.pop('_relative', None)
    merged.pop('_params_unset', None)
    # A failed parse must not fall through to the default (FWLD: 4→12).
    # Explicit nulls mean the sentence named no key, so the default is right.
    if not explicit_unset and skill_args_unmapped(raw, merged, schema, args_policy):
        return {'_skill_args_reject': True}
    merged = apply_schema_defaults(merged, schema, env=env)
    return merged or None


def finalize_skill_params(merged, schema, env=None):
    """Defaults + required gate after the last fill (cache or IA)."""
    from .skill_param_tokens import expand_skill_param_values
    if not isinstance(merged, dict) or merged.get('_skill_args_reject'):
        return merged
    out = apply_schema_defaults(merged, schema, env=env)
    out = expand_skill_param_values(out, env)
    out.pop('_relative', None)
    if missing_required_params(out, schema):
        return {'_skill_args_reject': True, '_skill_args_missing': True}
    return out


def parse_skill_arguments(arguments):
    """Sandbox parameters from the slash args.

    Always defines ``arguments``, ``lugar``, ``fecha``, ``start_date``,
    ``end_date``, ``anio``, ``year`` (None if missing). Accepts:

    - ``clave=valor`` (start_date=2025-01-01, anio=2025, …)
    - single years: ``2025`` → 2025-01-01 .. 2025-12-31
    - two years: ``2023 2025`` → 2023-01-01 .. 2025-12-31
    - ISO dates: ``2024-01-01 2024-06-30``
    - the rest (no dates): free text in ``lugar`` (generic; the skill decides)

    The engine does NOT interpret the domain (weather, etc.): it hands over ``arguments`` (raw
    text) and ``lugar`` (the rest without dates). Common relative dates are enriched
    later via ``enrich_params_with_dates`` / opt-in AI.
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
            # YYYY-MM → mes (payroll-style skills)
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

    # Remaining free text → ``lugar`` (generic, without interpreting the domain).
    # The skill (weather or another) parses ``arguments`` / ``lugar`` as it likes.
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


def overlay_resolved_params(params, extra_params):
    """Schema keys win. The raw sentence is not left for the skill to parse again.

    Any skill reads ``desde_hasta`` / ``ba`` / … and uses its own default when
    the value is empty. ``arguments`` and ``lugar`` stay only when this call
    did not map a schema key (no schema, or the key itself is the text).
    """
    params = dict(params or {})
    extra = {}
    for key, val in (extra_params or {}).items():
        if not isinstance(key, str) or key.startswith('_'):
            continue
        extra[key] = val
        if val is not None:
            params[key] = val
        else:
            params.setdefault(key, None)
    mapped = [
        key for key in extra
        if key not in ('skill_state', 'arguments', 'lugar')
    ]
    if not mapped:
        return params
    if not str(extra.get('arguments') or '').strip():
        params['arguments'] = None
        for key in list(params):
            if key.startswith('arg') and key[3:].isdigit():
                params.pop(key, None)
    if not str(extra.get('lugar') or '').strip():
        params['lugar'] = None
    return params
