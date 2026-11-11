# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Read parameter values from what the person typed: formal tokens, choices and the extraction prompt."""

from __future__ import annotations
import json
import logging
import re
import shlex

from .skill_runtime_param_schema import (
    _coerce_schema_value,
    _param_value_resolved,
    _RANGE_PARAM,
    _schema_key_is_year_slot,
    _schema_key_takes_period,
    _token_looks_canonical_temporal,
)

_logger = logging.getLogger(__name__)


def _token_looks_formal_period_range(val):
    """YYYY / YYYY-YYYY / YYYYMMDD-YYYYMMDD / ISO day range — not ``ytd``."""
    if val in (None, '', []):
        return False
    s = str(val).strip().replace(' ', '')
    s = s.replace('/', '-').replace('–', '-').replace('—', '-')
    if re.fullmatch(r'\d{4}', s):
        return True
    if re.fullmatch(r'\d{4}-\d{4}', s):
        return True
    if re.fullmatch(r'\d{8}-\d{8}', s):
        return True
    return bool(_RANGE_PARAM.match(s))


def _token_looks_formal_integer(val):
    """A bare integer (``30``), not a year / ISO token."""
    if isinstance(val, bool):
        return False
    if isinstance(val, int):
        return not _token_looks_canonical_temporal(str(val))
    s = str(val or '').strip()
    if not re.fullmatch(r'-?\d+', s):
        return False
    return not _token_looks_canonical_temporal(s)


def _value_is_formal_token(val):
    """Year, ISO, code CSV or bare integer. Not a word."""
    return bool(
        _token_looks_canonical_temporal(val)
        or _token_looks_formal_code_csv(val)
        or _token_looks_formal_integer(val)
    )


def _schema_key_is_integer(spec):
    spec = spec if isinstance(spec, dict) else {}
    return (spec.get('type') or '').lower() in ('integer', 'number')


def _token_looks_formal_code_csv(val):
    """Short codes: ``ABC`` / ``ABC,XYZ`` / ``abc,xyz``. Not ``ytd`` / ``Seville``."""
    s = str(val or '').strip()
    if not re.fullmatch(
        r'[A-Za-z0-9]{2,8}(?:\s*,\s*[A-Za-z0-9]{2,8})*',
        s,
    ):
        return False
    if not re.search(r'[A-Za-z]', s):
        return False
    # A lone word (ytd, Seville, tomorrow) is not a code list.
    if ',' in s:
        return True
    return s == s.upper()


def _token_is_code_piece(val):
    """One 2–8 alnum chunk with a letter (continuation after ``ABC,``)."""
    s = str(val or '').strip().strip(',')
    return bool(
        s
        and re.fullmatch(r'[A-Za-z0-9]{2,8}', s)
        and re.search(r'[A-Za-z]', s)
    )


def _token_is_code_fragment(val):
    """CSV, uppercase code, or a comma-tailed piece of a spaced CSV."""
    s = str(val or '').strip()
    trailed = s.endswith(',')
    if trailed:
        s = s[:-1].strip()
    if not s:
        return False
    if _token_looks_formal_code_csv(s):
        return True
    return trailed and _token_is_code_piece(s)


def _join_code_frags(parts):
    codes = []
    for part in parts:
        for bit in re.split(r'\s*,\s*', str(part or '').strip()):
            bit = bit.strip().strip(',')
            if bit:
                codes.append(bit)
    return ','.join(codes)


def _stem_is_upper_code(val):
    """``COR`` / ``COR,`` — a sigla, not a lowercase word with a comma."""
    s = str(val or '').strip().strip(',')
    return bool(s) and s == s.upper() and _token_is_code_piece(s)


def _utterance_is_only_formal_pieces(tokens):
    """True for ``abc, xyz 2026``. False when the phrase also has words."""
    if not tokens:
        return False
    for tok in tokens:
        if _token_looks_canonical_temporal(tok) or _token_looks_formal_period_range(tok):
            continue
        if _token_looks_formal_integer(tok):
            continue
        if (
            _token_looks_formal_code_csv(tok)
            or _token_is_code_fragment(tok)
            or _token_is_code_piece(tok)
        ):
            continue
        return False
    return True


def _coalesce_formal_code_tokens(tokens):
    """``ABC, DEF`` and ``abc, xyz`` are one CSV. A comma in a sentence is not.

    ``pasado, solo COR`` keeps ``COR`` and leaves the words alone.
    """
    code_list = _utterance_is_only_formal_pieces(tokens)
    out = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if _token_looks_formal_period_range(tok):
            out.append(tok)
            i += 1
            continue
        trailed = str(tok).rstrip().endswith(',')
        if trailed and _token_is_code_fragment(tok) and (
            code_list or _stem_is_upper_code(tok)
        ):
            if not code_list:
                out.append(str(tok).strip().rstrip(',').strip())
                i += 1
                continue
            buf = [tok]
            i += 1
            while i < n:
                nxt = tokens[i]
                if _token_looks_formal_period_range(nxt):
                    break
                if not (
                    _token_is_code_fragment(nxt) or _token_is_code_piece(nxt)
                ):
                    break
                buf.append(nxt)
                i += 1
                if not str(nxt).rstrip().endswith(','):
                    break
            out.append(_join_code_frags(buf))
            continue
        out.append(tok)
        i += 1
    return out


def _apply_schema_kv(params, schema, raw):
    """Copy ``clave=valor`` onto matching schema keys."""
    for part in _split_arg_tokens(raw):
        if not _is_kv_token(part):
            continue
        key, val = part.split('=', 1)
        key = key.strip()
        if key in schema and key != 'arguments':
            params[key] = _coerce_schema_value(schema.get(key), val)
    return params


def deterministic_schema_hits(params, schema, raw=None):
    """Formal fills safe to keep when the hybrid LLM also runs.

    A year/ISO token on a non-temporal key is a bad zip (``an=2025-2026``),
    not a hit — leave that hole for the LLM. With ``raw``, a prose dump
    (``lugar`` = the whole sentence) is not a hit either: only ``clave=valor``
    and formal tokens override the JSON.
    """
    params = params or {}
    schema = schema if isinstance(schema, dict) else {}
    kv = kv_keys_from_raw(raw) if raw is not None else None
    det = {}
    for key in schema:
        spec = schema.get(key)
        val = params.get(key)
        if not _param_value_resolved(key, val, spec):
            continue
        if (
            not _schema_key_takes_period(key, spec)
            and not _schema_key_is_year_slot(key, spec)
            and _token_looks_canonical_temporal(val)
        ):
            continue
        if kv is not None and key not in kv and not _value_is_formal_token(val):
            continue
        det[key] = val
    return det


_CHOICES_LIMIT = 200


def _choice_field_text(record, path):
    """Read a simple field or one-level related name. Empty if missing."""
    path = (path or '').strip()
    parts = path.split('.') if path else []
    if not parts or not all(p.isidentifier() for p in parts):
        return ''
    cur = record
    for part in parts:
        if cur is None or cur is False:
            return ''
        try:
            cur = cur[part]
        except Exception:
            return ''
    if cur is None or cur is False:
        return ''
    name = getattr(cur, '_name', None)
    if name:
        try:
            if not cur:
                return ''
        except Exception:
            return ''
        try:
            return str(cur.name or '').strip()
        except Exception:
            return ''
    return str(cur).strip()


def _spec_label_paths(spec):
    raw = spec.get('choices_label') or spec.get('choices_name') or 'name'
    if isinstance(raw, (list, tuple)):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw).strip()
    return [text] if text else ['name']


def _strip_code_bracket_prefix(code, label):
    """Drop a leading ``[CODE]`` from a label (structural, not a lexicon)."""
    label = (label or '').strip()
    code = (code or '').strip()
    if not label or not code:
        return label
    prefix = '[%s]' % code
    while len(label) >= len(prefix) and label[:len(prefix)].upper() == prefix.upper():
        label = label[len(prefix):].strip()
    return label


def _format_choice_row(code, labels):
    """Code + distinct description, or None if only the code remains."""
    seen = {code.casefold()}
    extra = []
    for label in labels:
        label = _strip_code_bracket_prefix(code, label)
        if not label or label.casefold() in seen:
            continue
        seen.add(label.casefold())
        extra.append(label)
    if not extra:
        return None
    return {'code': code, 'label': ' — '.join(extra)}


def attach_schema_choices(schema, env):
    """Fill ``spec['choices']`` from ``choices_model`` the skill named.

    The engine does not invent rows. Missing model or field → that key
    stays without choices (same prompt as today). Already-set ``choices``
    win (authored list). Called only on the hybrid LLM path.
    """
    if not isinstance(schema, dict) or env is None:
        return schema
    for spec in schema.values():
        if not isinstance(spec, dict):
            continue
        if spec.get('choices'):
            continue
        model = (spec.get('choices_model') or '').strip()
        code_field = (spec.get('choices_code') or '').strip()
        if not model or not code_field or not code_field.isidentifier():
            continue
        try:
            if model not in env:
                continue
        except Exception:
            continue
        domain = spec.get('choices_domain')
        if domain in (None, False, ''):
            domain = []
        if not isinstance(domain, list):
            continue
        try:
            rows = env[model].search(domain, limit=_CHOICES_LIMIT)
        except Exception:
            _logger.debug(
                'schema choices: search %s failed', model, exc_info=True,
            )
            continue
        label_paths = _spec_label_paths(spec)
        exclude = {
            str(x).strip()
            for x in (spec.get('choices_exclude') or [])
            if str(x).strip()
        }
        choices = []
        seen = set()
        for rec in rows:
            code = _choice_field_text(rec, code_field)
            if not code or code in exclude or code in seen:
                continue
            seen.add(code)
            labels = [_choice_field_text(rec, path) for path in label_paths]
            row = _format_choice_row(code, labels)
            if row:
                choices.append(row)
        if choices:
            spec['choices'] = choices
    return schema


def _choice_prompt_lines(choices):
    lines = []
    for row in choices or []:
        if isinstance(row, dict):
            code = str(row.get('code') or row.get('id') or '').strip()
            label = str(row.get('label') or row.get('name') or '').strip()
            if not code:
                continue
            if label:
                lines.append('  - %s — %s' % (code, label))
            else:
                lines.append('  - %s' % code)
        else:
            text = str(row).strip()
            if text:
                lines.append('  - %s' % text)
    return lines


def build_param_extraction_prompt(schema, leftover, locale=None, arg_hint=''):
    """Build (system, leftover) so the LLM maps human text → rigid schema JSON.

    ``schema`` is the output contract (``{key: {"type", "desc"}}``). The
    skill owns the meaning of each key. The engine only demands that shape.
    Live ``choices`` (code + label) are listed when the skill attached them.
    ``arg_hint`` is unused (human placeholder, not an IA lexicon).
    """
    del arg_hint
    import datetime as _dt
    today = _dt.date.today().isoformat()
    lines = []
    has_choices = False
    required_keys = []
    for key, spec in (schema or {}).items():
        spec = spec if isinstance(spec, dict) else {}
        typ = spec.get('type') or 'string'
        desc = spec.get('desc') or spec.get('description') or ''
        mark = ' required' if spec.get('required') else ''
        lines.append('- "%s" (%s)%s: %s' % (key, typ, mark, desc))
        if spec.get('required'):
            required_keys.append(key)
        choice_lines = _choice_prompt_lines(spec.get('choices'))
        if choice_lines:
            has_choices = True
            lines.append('  Values (code — label):')
            lines.extend(choice_lines)
    keys = ', '.join('"%s"' % k for k in (schema or {}).keys())
    locale_hint = (' Locale: %s.' % locale) if locale else ''
    choice_rule = (
        ' When Values are listed for a key, emit those codes (CSV), '
        'not the labels.'
        if has_choices else ''
    )
    if required_keys:
        req_rule = (
            ' Required keys: %s. Leave null if the leftover does not '
            'mention a required key; the engine will ask. Do not invent '
            'a value.'
            % ', '.join('"%s"' % k for k in required_keys)
        )
    else:
        req_rule = (
            ' Fill every key the leftover names. Use null only when the '
            'leftover does not mention that key. Do not leave a named '
            'key null. Keys the leftover never names stay null.'
        )
    system = (
        'Convert leftover slash text into a JSON object. '
        'Reply with JSON only (no prose, no markdown). '
        'Exact keys: %s.\n'
        'Today is %s.%s\n'
        'Output contract:\n%s\n'
        '%s If the leftover names something that belongs '
        'to a key, fill that key in the contract format even if the '
        'wording is informal. Do not invent keys.%s '
        'If a filled value is not a stable identifier — it would '
        'resolve to someone or something else later — also emit '
        '"_relative": ["key", …] for those keys. That includes time '
        'phrases (today, last year, next Wednesday) and live rankings '
        '(the current top / most expensive / best by a metric). '
        'Do not mark an ISO date, year, code or name the leftover '
        'already wrote as a literal. '
        'Return {"_reject": true} only when the text is junk '
        'and no key can be filled.'
    ) % (keys, today, locale_hint, '\n'.join(lines), req_rule, choice_rule)
    return system, (leftover or '')


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
    relative = []
    raw_rel = data.get('_relative')
    if isinstance(raw_rel, (list, tuple)):
        for item in raw_rel:
            name = str(item or '').strip()
            if name in schema and name not in relative:
                relative.append(name)
    if relative:
        out['_relative'] = relative
    values = [v for k, v in out.items() if not str(k).startswith('_')]
    if all(v is None for v in values):
        # The model read the sentence and named no key. That is not a
        # failed parse (``None``): defaults may run.
        out['_params_unset'] = True
    return out


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
