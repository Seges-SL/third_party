# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Skill parameters: infer them from the code, temporal and period slots, schema to rows and back."""

from __future__ import annotations
import ast
import json
import re


# Parameters: deterministic first (`parse_skill_arguments` + relative dates
# in ``skill_dates``). If the skill declares ``param_schema`` and free text
# is left unresolved, the engine may ask the LLM for ONE short extraction (opt-in).
# No NL routing and no sticky continuity.


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


_CANONICAL_TEMPORAL_TOKEN = re.compile(
    r'^('
    r'\d{4}'
    r'|\d{4}-\d{4}'
    r'|\d{4}-\d{2}(-\d{2})?'
    r'|\d{8}(-\d{8})?'
    r'|\d{4}-\d{2}-\d{2}\.\.\d{4}-\d{2}-\d{2}'
    r')$'
)


def _token_looks_canonical_temporal(val):
    """True for year / ISO / compact range tokens (no locale words)."""
    if val in (None, '', []):
        return False
    if isinstance(val, (list, tuple)):
        return any(_token_looks_canonical_temporal(v) for v in val)
    s = str(val).strip().replace(' ', '')
    s = s.replace('/', '-').replace('–', '-').replace('—', '-')
    return bool(_CANONICAL_TEMPORAL_TOKEN.match(s) or _RANGE_PARAM.match(s))


def _param_value_resolved(key, val, spec=None):
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
    if pat is not None:
        return bool(pat.match(str(val).strip()))
    if _schema_key_is_temporal(key, spec):
        s = str(val).strip().replace(' ', '')
        s = s.replace('/', '-').replace('–', '-').replace('—', '-')
        if _CANONICAL_PARAM['fecha'].match(s):
            return True
        if _CANONICAL_PARAM['mes'].match(s):
            return True
        if _RANGE_PARAM.match(s):
            return True
        if re.fullmatch(r'\d{4}', s):
            return True
        if re.fullmatch(r'\d{4}-\d{4}', s):
            return True
        if re.fullmatch(r'\d{8}-\d{8}', s):
            return True
        return False
    return True


def _schema_key_is_temporal(key, spec):
    """True when the key (or its desc) is a date/month/range slot."""
    if key in _CANONICAL_PARAM or key == 'periodos':
        return True
    spec = spec if isinstance(spec, dict) else {}
    desc = str(spec.get('desc') or spec.get('description') or '')
    return 'YYYY-MM-DD' in desc or 'YYYY-MM' in desc


def _schema_key_takes_period(key, spec):
    """Temporal slot, or a string key whose contract writes ``YYYY``."""
    if _schema_key_is_temporal(key, spec):
        return True
    spec = spec if isinstance(spec, dict) else {}
    if (spec.get('type') or 'string').lower() != 'string':
        return False
    desc = str(spec.get('desc') or spec.get('description') or '')
    return 'YYYY' in desc


_PERIOD_SHAPES = (
    (re.compile(r'^\d{4}-\d{2}-\d{2}\.\.\d{4}-\d{2}-\d{2}$'),
     re.compile(r'YYYY-MM-DD\.\.YYYY-MM-DD')),
    (re.compile(r'^\d{8}-\d{8}$'), re.compile(r'YYYYMMDD-YYYYMMDD')),
    (re.compile(r'^\d{4}-\d{2}-\d{2}$'),
     re.compile(r'(?<![-\w.])YYYY-MM-DD(?![-\w]|\.\.)')),
    (re.compile(r'^\d{4}-\d{2}$'), re.compile(r'(?<![-\w.])YYYY-MM(?![-\w])')),
    (re.compile(r'^\d{4}-\d{4}$'), re.compile(r'YYYY-YYYY')),
    (re.compile(r'^\d{4}$'),
     re.compile(r'(?<![-\w.])YYYY(?![-\w])|YYYY-YYYY')),
)


def _contract_writes_shape(spec, tok):
    """True when the key's desc writes the token's shape (``YYYY-MM`` …)."""
    spec = spec if isinstance(spec, dict) else {}
    desc = str(spec.get('desc') or spec.get('description') or '')
    s = str(tok or '').strip().replace(' ', '')
    s = s.replace('/', '-').replace('–', '-').replace('—', '-')
    for token_re, desc_re in _PERIOD_SHAPES:
        if token_re.match(s):
            return bool(desc_re.search(desc))
    return False


def _period_fits_key(key, spec, tok):
    """A period token fits a free key: canonical slot, or the shape it writes."""
    if not _param_value_resolved(key, _coerce_schema_value(spec, tok), spec):
        return False
    if (
        key in _CANONICAL_PARAM
        or key == 'periodos'
        or not _schema_key_takes_period(key, spec)
    ):
        return True
    return _contract_writes_shape(spec, tok)


def _period_as_date_pair(tok):
    """``(first_day, last_day)`` ISO for a formal period token, or None."""
    s = str(tok or '').strip().replace(' ', '')
    s = s.replace('/', '-').replace('–', '-').replace('—', '-')
    m = re.fullmatch(r'(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})', s)
    if m:
        return m.group(1), m.group(2)
    m = re.fullmatch(r'(\d{4})(\d{2})(\d{2})-(\d{4})(\d{2})(\d{2})', s)
    if m:
        g = m.groups()
        return '%s-%s-%s' % g[:3], '%s-%s-%s' % g[3:]
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
        return s, s
    m = re.fullmatch(r'(\d{4})-(\d{2})', s)
    if m and 1 <= int(m.group(2)) <= 12:
        import calendar
        y, mo = int(m.group(1)), int(m.group(2))
        last = calendar.monthrange(y, mo)[1]
        return '%04d-%02d-01' % (y, mo), '%04d-%02d-%02d' % (y, mo, last)
    m = re.fullmatch(r'(\d{4})(?:-(\d{4}))?', s)
    if m:
        a = int(m.group(1))
        b = int(m.group(2) or a)
        a, b = min(a, b), max(a, b)
        return '%04d-01-01' % a, '%04d-12-31' % b
    return None


def _schema_key_is_year_slot(key, spec):
    """True when the hole is a calendar year, not a count.

    Structural: ``{year}`` / ``{year}-n`` default, a 4-digit integer
    default, or the inferred year keys. A bare count (``24``) must not
    land here.
    """
    spec = spec if isinstance(spec, dict) else {}
    default = str(spec.get('default') or '').strip()
    if _YEAR_SLOT_DEFAULT_RE.fullmatch(default):
        return True
    if _INT_DEFAULT.fullmatch(default) and len(default.lstrip('-')) == 4:
        return True
    return (key or '').strip().casefold() in ('year', 'anio')


# Sandbox names that are never slash-arg keys (always injected or leftover).
_SANDBOX_NON_PARAMS = frozenset({
    'env', 'result', 'user', 'company', 'odoo_version', 'odoo_series',
    'user_lang', 'lang', 'locale', 'previous_result', 'skill_state',
    'arguments',
    'page_url',
})


_INFERRED_SPEC = {
    'fecha': {'type': 'string', 'desc': 'YYYY-MM-DD. Empty if absent.'},
    'start_date': {'type': 'string', 'desc': 'YYYY-MM-DD. Empty if absent.'},
    'end_date': {'type': 'string', 'desc': 'YYYY-MM-DD. Empty if absent.'},
    'mes': {'type': 'string', 'desc': 'YYYY-MM. Empty if absent.'},
    'anio': {'type': 'integer', 'desc': 'Calendar year. Empty if absent.'},
    'year': {'type': 'integer', 'desc': 'Calendar year. Empty if absent.'},
    'periodos': {'type': 'string', 'desc': 'Date range. Empty if absent.'},
}


_DEFAULT_INFERRED_SPEC = {'type': 'string', 'desc': 'Empty if absent.'}


def _handler_catches_nameerror(handler):
    typ = handler.type
    if typ is None:
        return False
    if isinstance(typ, ast.Name) and typ.id == 'NameError':
        return True
    if isinstance(typ, ast.Tuple):
        return any(
            isinstance(elt, ast.Name) and elt.id == 'NameError'
            for elt in typ.elts
        )
    return False


def _is_slash_param_key(name):
    if not name or not name.isidentifier() or name.startswith('_'):
        return False
    if name in _SANDBOX_NON_PARAMS:
        return False
    if name.startswith('arg') and name[3:].isdigit():
        return False
    return True


def infer_param_keys_from_code(code):
    """Slash-arg names the code reads via ``try/except NameError``.

    Only names that appear in the source (RHS of ``x = name`` inside a
    NameError guard). Does not invent keys and does not scan local
    assignments like ``fecha = '2025-01-01'``.
    """
    code = (code or '').strip()
    if not code:
        return []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    keys = []
    seen = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        if not any(_handler_catches_nameerror(h) for h in node.handlers):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            if not isinstance(stmt.value, ast.Name):
                continue
            key = stmt.value.id
            if key in seen or not _is_slash_param_key(key):
                continue
            seen.add(key)
            keys.append(key)
    return keys


def infer_param_schema_from_code(code):
    """Minimal ``param_schema`` dict from NameError globals in ``code``."""
    keys = infer_param_keys_from_code(code)
    return {
        key: dict(_INFERRED_SPEC.get(key, _DEFAULT_INFERRED_SPEC))
        for key in keys
    }


def param_schema_to_json(schema):
    if not schema:
        return ''
    return json.dumps(schema, ensure_ascii=False, separators=(',', ':'))


def infer_arg_hint_from_schema(schema):
    """Placeholder from schema keys only — never invents example values."""
    if not schema:
        return ''
    return ' '.join('%s=…' % key for key in schema)


def fill_capture_params(code, schema_txt='', hint=''):
    """Keep an authored schema; otherwise infer from the Code.

    If ``schema_txt`` is already valid JSON, it wins (create-skill must
    not overwrite a catalog skill). Hint is derived from keys when empty.
    Invalid JSON is returned as-is so the wizard can raise.
    """
    schema_txt = (schema_txt or '').strip()
    hint = (hint or '').strip()
    if schema_txt:
        try:
            parsed = json.loads(schema_txt)
        except Exception:
            return schema_txt, hint
        if not isinstance(parsed, dict):
            return schema_txt, hint
        parsed = drop_result_param_keys(parsed)
        dumped = json.dumps(parsed, ensure_ascii=False, separators=(',', ':')) if parsed else ''
        if not hint:
            hint = infer_arg_hint_from_schema(parsed)
        return dumped, hint
    inferred = drop_result_param_keys(infer_param_schema_from_code(code))
    if not inferred:
        return '', hint
    dumped = param_schema_to_json(inferred)
    if not hint:
        hint = infer_arg_hint_from_schema(inferred)
    return dumped, hint


_INT_DEFAULT = re.compile(r'^-?\d+$')


_NUM_DEFAULT = re.compile(r'^-?\d+\.\d+$')


# ``{year}`` / ``{year}-n`` expand to a calendar year. ``{year}-01-01`` is a date.
_YEAR_SLOT_DEFAULT_RE = re.compile(r'^\{year\}(?:-[1-9]\d*)?$')


def infer_type_from_default(default):
    """``string`` unless the default is an integer, a number, or a year token."""
    text = '' if default is None else str(default).strip()
    if not text:
        return 'string'
    if _YEAR_SLOT_DEFAULT_RE.fullmatch(text):
        return 'integer'
    if _INT_DEFAULT.fullmatch(text):
        return 'integer'
    if _NUM_DEFAULT.fullmatch(text):
        return 'number'
    return 'string'


def schema_to_param_rows(schema):
    """JSON schema → ``[{key, label, desc, default, required}, ...]``."""
    if isinstance(schema, str):
        parsed = parse_param_schema_txt(schema)
    elif isinstance(schema, dict):
        parsed = schema
    else:
        parsed = {}
    rows = []
    for key, spec in parsed.items():
        spec = spec if isinstance(spec, dict) else {}
        label = (spec.get('label') or key or '').strip()
        desc = (spec.get('desc') or spec.get('description') or '').strip()
        default = spec.get('default')
        if default is None:
            default = ''
        else:
            default = str(default)
        rows.append({
            'key': key,
            'label': label,
            'desc': desc,
            'default': default,
            'required': bool(spec.get('required')),
        })
    return rows


def param_rows_fingerprint(rows):
    """Stable fingerprint of the human columns (not identifiers)."""
    parts = []
    for row in rows or []:
        default = row.get('default')
        parts.append((
            (row.get('label') or '').strip(),
            (row.get('desc') or '').strip(),
            '' if default is None else str(default).strip(),
            bool(row.get('required')),
        ))
    return json.dumps(parts, ensure_ascii=False)


_TURN_CHIP_RE = re.compile(r'^[A-Za-z0-9]{4}(?:-\d+)?$')


def help_without_turn_chips(text):
    """Drop 4-character turn chips (``PMCZ``) from trainer/help prose."""
    kept = [
        part for part in (text or '').split()
        if part and not _TURN_CHIP_RE.match(part)
    ]
    return ' '.join(kept).strip()


def is_placeholder_skill_help(text, *names):
    """True when Help is empty, only a name/code, or a name plus a turn chip."""
    raw = help_without_turn_chips(text)
    folded = raw.casefold()
    if not folded:
        return True
    compact = re.sub(r'[\s-]+', '', folded)
    for name in names:
        n = help_without_turn_chips(name).casefold()
        if n and folded == n:
            return True
        n_compact = re.sub(r'[\s-]+', '', n)
        if n_compact and compact == n_compact:
            return True
        if n_compact and compact.startswith(n_compact):
            rest = compact[len(n_compact):]
            if _TURN_CHIP_RE.match(rest):
                return True
    return False


def capture_help_text(catalog_help='', user_prompt='', name_hint='',
                      turn_id='', names=()):
    """Help for a new capture. The slash and the turn chip are not help."""
    extra = tuple(
        part for part in (name_hint, turn_id) + tuple(names or ()) if part
    )
    help_txt = (catalog_help or '').strip()
    if is_placeholder_skill_help(help_txt, *extra):
        help_txt = ''
    if not help_txt:
        help_txt = (user_prompt or '').strip()
    if is_placeholder_skill_help(help_txt, *extra):
        help_txt = ''
    return help_txt[:120]


def param_rows_need_author(rows):
    """True when a concept exists without a schema key."""
    for row in rows or []:
        label = (row.get('label') or '').strip()
        desc = (row.get('desc') or '').strip()
        key = (row.get('key') or '').strip()
        if (label or desc) and not key:
            return True
    return False


def param_rows_to_prose(rows):
    """Trainer text from the list (concept / desc / default)."""
    lines = []
    for row in rows or []:
        label = (row.get('label') or row.get('key') or '').strip()
        desc = (row.get('desc') or '').strip()
        default = row.get('default')
        default = '' if default is None else str(default).strip()
        if not label and not desc:
            continue
        if label and desc:
            chunk = '%s: %s' % (label, desc)
        else:
            chunk = label or desc
        if default:
            chunk = '%s Default: %s.' % (chunk.rstrip('.'), default)
        if row.get('required'):
            chunk = '%s Required.' % chunk.rstrip('.')
        lines.append(chunk)
    return '\n'.join(lines)


def _looks_like_param_key(name):
    """True for snake_case identifiers (not a Title Case concept)."""
    if not name or not name.isidentifier() or name.startswith('_'):
        return False
    return name == name.lower()


def apply_code_keys_to_rows(rows, code_keys):
    """Assign identifiers from Code NameError keys; do not invent names.

    Keeps a row key that is already snake_case. Else uses the label
    when it is snake_case (not a human concept). Else the next unused
    Code key. Rows still without a key stay empty for a later light IA.
    """
    used = set()
    out = []
    for raw in rows or []:
        row = dict(raw)
        key = (row.get('key') or '').strip()
        if _looks_like_param_key(key):
            row['key'] = key
            used.add(key)
            out.append(row)
            continue
        label = (row.get('label') or '').strip()
        if _looks_like_param_key(label):
            row['key'] = label
            used.add(label)
            out.append(row)
            continue
        row['key'] = ''
        out.append(row)
    unused = [k for k in (code_keys or []) if k not in used]
    for row in out:
        if row.get('key'):
            continue
        if unused:
            row['key'] = unused.pop(0)
    return out


def assign_extracted_keys_to_rows(rows, extracted, code_keys=None):
    """Give leftover IA identifiers to rows that still have no key."""
    extracted = extracted if isinstance(extracted, dict) else {}
    extracted_keys = [
        k for k in extracted
        if (
            k != '_reject'
            and isinstance(k, str)
            and k.isidentifier()
            and not k.startswith('_')
        )
    ]
    used = {
        (r.get('key') or '').strip()
        for r in (rows or [])
        if (r.get('key') or '').strip()
    }
    leftover = [k for k in extracted_keys if k not in used]
    code_keys = list(code_keys or [])
    leftover.sort(key=lambda k: (0 if k in code_keys else 1, extracted_keys.index(k)))
    out = []
    for raw in rows or []:
        row = dict(raw)
        if not (row.get('key') or '').strip() and leftover:
            row['key'] = leftover.pop(0)
        out.append(row)
    return out


def param_rows_to_schema(rows, existing_schema=None):
    """Rows that already have keys → schema dict. Keeps ``choices_*``."""
    if isinstance(existing_schema, str):
        existing = parse_param_schema_txt(existing_schema)
    elif isinstance(existing_schema, dict):
        existing = existing_schema
    else:
        existing = {}
    out = {}
    for row in rows or []:
        key = (row.get('key') or '').strip()
        if not key.isidentifier() or key.startswith('_'):
            continue
        prev = existing.get(key) if isinstance(existing.get(key), dict) else {}
        spec = dict(prev)
        default = row.get('default')
        inferred = infer_type_from_default(default)
        if default not in (None, '') and inferred != 'string':
            spec['type'] = inferred
        else:
            spec['type'] = spec.get('type') or inferred or 'string'
        label = (row.get('label') or '').strip()
        if label and label != key:
            spec['label'] = label
        else:
            spec.pop('label', None)
        desc = (row.get('desc') or '').strip()
        if desc:
            spec['desc'] = desc
        if default not in (None, ''):
            spec['default'] = str(default).strip()
        else:
            spec.pop('default', None)
        if row.get('required'):
            spec['required'] = True
        else:
            spec.pop('required', None)
        out[key] = spec
    return out


def overlay_rows_on_schema(rows, schema):
    """List wins for label/desc/default; leftover schema keys are kept."""
    if isinstance(schema, str):
        parsed = parse_param_schema_txt(schema)
    elif isinstance(schema, dict):
        parsed = dict(schema)
    else:
        parsed = {}
    out = param_rows_to_schema(rows, parsed)
    for key, spec in parsed.items():
        if key not in out and isinstance(spec, dict):
            out[key] = dict(spec)
    return out


def author_copy_locale(lang=None):
    """Locale for generated Help / desc. Identifiers stay snake_case."""
    code = (lang or '').strip() or 'en_US'
    return (
        ' Write "help" and human-facing desc in the language of locale %s. '
        'Identifiers stay snake_case. Format tokens (YYYY, CSV) stay as-is.'
        % code
    )


def parse_param_schema_txt(schema_txt):
    raw = (schema_txt or '').strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    out = {}
    for key, spec in data.items():
        if isinstance(key, str) and key.isidentifier() and isinstance(spec, dict):
            out[key] = dict(spec)
    return out


def drop_result_param_keys(schema):
    """Drop result helpers (``page_url``) that are not slash arguments."""
    if isinstance(schema, str):
        parsed = parse_param_schema_txt(schema)
        if not parsed:
            return {}
        return drop_result_param_keys(parsed)
    if not isinstance(schema, dict):
        return {}
    return {
        key: spec for key, spec in schema.items()
        if _is_slash_param_key(key)
    }


def _schema_key_set(schema):
    if isinstance(schema, dict):
        return {key for key in schema if _is_slash_param_key(key)}
    if isinstance(schema, str):
        return _schema_key_set(parse_param_schema_txt(schema))
    return {key for key in (schema or []) if _is_slash_param_key(key)}


def _schema_as_dict(schema):
    if isinstance(schema, dict):
        return schema
    if isinstance(schema, str):
        return parse_param_schema_txt(schema)
    return {}


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
