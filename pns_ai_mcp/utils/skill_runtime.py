# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Generic skill runtime: bootstrap, fast-path, and presenters.

The engine is domain-agnostic. Domain logic lives in the skill's
``code_body`` (in its own module). This file only has generic mechanisms.

Contract (any skill)
--------------------
``code_body`` may return a ``result`` dict with:

- ``propose_steps``: Safe Plan list. If every step is auto-confirmable
  (``fetch_url`` on the whitelist **or** ``api_call`` to a ``trusted``
  server), the server runs them with no extra LLM round and no toast.
- ``continue``: if true and ``propose_steps`` ran, the engine calls
  ``code_body`` again with results in the ``previous_result`` global so
  a skill can chain dependent phases across rounds.
- ``presentation`` / ``__return_direct__`` plus ``data``|``groups``|
  ``sections``|``tables``|``formatted_text``: ready reply → HTML to chat
  without tools. The skill also composes its ``footer`` (the engine does
  not invent footers).
- Generic arg wait: help markdown card with no rows + invoke with no
  args → the next human message without a slash resumes the skill.
  Explicit ``__await_skill_args__`` True/False forces or skips the wait.
  Help (``?``) never waits.
- ``__skill_state__``: free dict the skill wants back next round. It
  returns as the sandbox global ``skill_state`` (``{}`` on a new invoke).
  The engine transports it without looking inside: slots and completeness
  are the skill's decision, not the engine's.
- Free metadata for the LLM when there is no fast-path.

Presenters (optional): generic ``register_presenter`` so a module can
add post-fetch formatters. The engine ships none.
"""
from __future__ import annotations

import ast
import io
import json
import logging
import re
import shlex
import tokenize
from datetime import date as _date

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


_PARAM_HELP_SYSTEM = (
    'Write one short slash-help sentence: what the skill does '
    '(JSON only, no markdown). '
    'Shape: {"help": "<one sentence>"}. '
    'Use only the Procedure and Code. '
    'The parameter list is already shown on the card — do not list '
    'parameters unless the sources name them as the purpose. '
    'Do not invent a capability, model, or parameter that is not '
    'in the sources. '
    'Prefer Procedure when it says when/what. If Procedure is empty, '
    'use the Code. '
    'Return {"help": ""} if the sources are empty or only a template.'
)
_PROCEDURE_TEMPLATE_HEAD = (
    'When to use: describe the user request this skill answers.'
)
# Same English block the capture wizard stores via ``_()``. Used only to
# ignore that placeholder; a real Procedure starts with a different line.
_PROCEDURE_TEMPLATE = (
    "When to use: describe the user request this skill answers.\n"
    "Parameters: always list them. Form Default or Code default; "
    "required keys show Help, never a Code fallback.\n"
    "Output: explain how to present the result.\n"
    "Run the Code with relaxaicode; do not recompute its logic.\n"
    "\n"
    "Code habits (sandbox AST — save will reject otherwise):\n"
    "- sorted/min/max key=: only operator.itemgetter('field') or "
    "lambda x: x['field']. Precompute complex sort keys as a field.\n"
    "- Helpers: flat defs (nesting depth max 2). No classes.\n"
    "- Params: try/except NameError; never invent dates if required.\n"
    "- External data: propose_steps (fetch_url / api_call), never requests."
)
_CODE_HELP_LIMIT = 2500


def _procedure_template_heads():
    """First lines of the wizard Procedure placeholder (source + locale)."""
    heads = [_PROCEDURE_TEMPLATE_HEAD]
    try:
        from odoo import _
        for src in (_PROCEDURE_TEMPLATE_HEAD, _PROCEDURE_TEMPLATE):
            trans = _(src)
            if trans:
                heads.append(trans.strip().split('\n', 1)[0])
    except ImportError:
        pass
    seen = set()
    out = []
    for head in heads:
        text = (head or '').strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def procedure_for_help(text):
    """Trainer Procedure, or empty when it is still the wizard template."""
    raw = (text or '').strip()
    if not raw:
        return ''
    for head in _procedure_template_heads():
        if raw.startswith(head):
            return ''
    return raw


def code_for_help(code, limit=_CODE_HELP_LIMIT):
    raw = (code or '').strip()
    if not raw:
        return ''
    if len(raw) <= limit:
        return raw
    return raw[:limit]


def skill_help_fingerprint(procedure, code, rows=None):
    """Stable fingerprint of the sources for the stored slash-help sentence."""
    return json.dumps([
        (procedure or '').strip(),
        (code or '').strip(),
        json.loads(param_rows_fingerprint(rows)),
    ], ensure_ascii=False)


def build_skill_help_user(procedure, code, rows=None):
    """Trainer payload for the slash-help sentence. Empty if no source."""
    parts = []
    prose = procedure_for_help(procedure)
    if prose:
        parts.append('Procedure:\n%s' % prose)
    body = code_for_help(code)
    if body:
        parts.append('Code:\n%s' % body)
    listed = param_rows_to_prose(rows)
    if listed:
        parts.append('Parameters (already on the card):\n%s' % listed)
    return '\n\n'.join(parts)


def build_param_help_prompt(rows, procedure='', code_body='', lang=None):
    """Light IA: one stored slash-help sentence from Procedure / Code."""
    user = build_skill_help_user(procedure, code_body, rows)
    return _PARAM_HELP_SYSTEM + author_copy_locale(lang), user


_PARAM_AUTHOR_SYSTEM = (
    'Convert the trainer description into JSON only (no prose, no markdown). '
    'Shape: {"keys": {"<identifier>": {"type": "string"|"integer"|"number", '
    '"desc": "output format only", "required": true}}, '
    '"choices": {"<identifier>": {"model": "model.name", "code": "field", '
    '"label": "field or related.path"}}}. '
    'Each distinct thing the trainer asks for becomes one snake_case key. '
    'Prefer a word they already used as an identifier; otherwise a short '
    'English snake_case of that idea (geographic places → locations). '
    'desc is the output contract (format and examples), not business copy. '
    'Set required true only when the trainer marked that concept required. '
    'Include choices only when the trainer wrote a model and field names. '
    'Do not invent a model, field, or domain. '
    'Also emit "help": one short slash-help sentence from the trainer text. '
    'Return {"_reject": true} only when the text is empty, nonsense, '
    'or not about parameters.'
)
_CHOICES_SPEC_KEYS = (
    'choices_model', 'choices_code', 'choices_label',
    'choices_domain', 'choices_exclude',
)


def build_param_author_prompt(trainer_text, code_keys=None, lang=None):
    """Short JSON call: trainer prose → param_schema keys. No invented models."""
    extra = ''
    names = [k for k in (code_keys or []) if isinstance(k, str) and k.isidentifier()]
    if names:
        extra = (
            ' The skill code already reads these names: %s. '
            'Prefer those identifiers when the trainer describes them.'
            % ', '.join(names)
        )
    return (
        _PARAM_AUTHOR_SYSTEM + extra + author_copy_locale(lang),
        trainer_text or '',
    )


def _extract_json_object(text):
    if not text:
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
    return data if isinstance(data, dict) else None


def _param_author_key_spec(spec):
    spec = spec if isinstance(spec, dict) else {}
    typ = (spec.get('type') or 'string').strip().lower()
    if typ not in ('string', 'integer', 'number'):
        typ = 'string'
    desc = (spec.get('desc') or spec.get('description') or '').strip()
    row = {'type': typ}
    if desc:
        row['desc'] = desc
    model = (spec.get('choices_model') or spec.get('model') or '').strip()
    code = (spec.get('choices_code') or spec.get('code') or '').strip()
    label = (spec.get('choices_label') or spec.get('label') or '').strip()
    if model:
        row['choices_model'] = model
    if code:
        row['choices_code'] = code
    if label:
        row['choices_label'] = label
    domain = spec.get('choices_domain')
    if domain is None:
        domain = spec.get('domain')
    if domain not in (None, False, ''):
        row['choices_domain'] = domain
    exclude = spec.get('choices_exclude')
    if exclude not in (None, False, ''):
        row['choices_exclude'] = exclude
    if spec.get('required') in (True, 'true', 'True', 1, '1'):
        row['required'] = True
    return row


def parse_param_author_json(text):
    """LLM text → ``{key: spec}`` or ``{'_reject': True}`` or None."""
    data = _extract_json_object(text)
    if not data:
        return None
    if data.get('_reject') is True:
        return {'_reject': True}
    keys = data.get('keys')
    extra_choices = data.get('choices') if isinstance(data.get('choices'), dict) else {}
    if not isinstance(keys, dict):
        skip = {'_reject', 'choices', 'arg_hint', 'keys', 'help', 'description'}
        guessed = {
            k: v for k, v in data.items()
            if k not in skip and isinstance(v, dict)
        }
        keys = guessed or None
    if not isinstance(keys, dict):
        return None
    out = {}
    for key, spec in keys.items():
        if not isinstance(key, str) or not key.isidentifier() or key.startswith('_'):
            continue
        row = _param_author_key_spec(spec)
        ch = extra_choices.get(key)
        if isinstance(ch, dict):
            overlay = _param_author_key_spec(ch)
            for ck in _CHOICES_SPEC_KEYS:
                if ck in overlay:
                    row[ck] = overlay[ck]
        out[key] = row
    return out or None


def parse_param_author_help(text):
    """Optional ``help`` sentence from the same author JSON (empty if none)."""
    data = _extract_json_object(text)
    if not data:
        return ''
    return (data.get('help') or '').strip()[:120]


def ground_choices_on_spec(spec, trainer_text):
    """Drop ``choices_*`` unless the trainer named the model and code field."""
    spec = dict(spec or {})
    blob = (trainer_text or '').lower()
    model = (spec.get('choices_model') or '').strip()
    code = (spec.get('choices_code') or '').strip()
    if not model or model.lower() not in blob or not code or code.lower() not in blob:
        for key in _CHOICES_SPEC_KEYS:
            spec.pop(key, None)
        return spec
    label = (spec.get('choices_label') or '').strip()
    if label and '.' in label and label.lower() not in blob:
        spec.pop('choices_label', None)
    if spec.get('choices_domain') is not None and '[' not in (trainer_text or ''):
        spec.pop('choices_domain', None)
    return spec


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


def merge_authored_param_schema(existing, extracted, trainer_text):
    """Overlay extracted keys onto the current schema. Ground choices."""
    out = {}
    if isinstance(existing, dict):
        for key, spec in existing.items():
            if isinstance(key, str) and key.isidentifier() and isinstance(spec, dict):
                out[key] = dict(spec)
    if not isinstance(extracted, dict):
        return out
    for key, spec in extracted.items():
        if key == '_reject' or not isinstance(key, str):
            continue
        if not key.isidentifier() or key.startswith('_') or not isinstance(spec, dict):
            continue
        grounded = ground_choices_on_spec(spec, trainer_text)
        prev = out.get(key) if isinstance(out.get(key), dict) else {}
        merged = dict(prev)
        if grounded.get('type'):
            merged['type'] = grounded['type']
        if grounded.get('desc'):
            merged['desc'] = grounded['desc']
        if grounded.get('choices_model'):
            for ck in _CHOICES_SPEC_KEYS:
                if ck in grounded:
                    merged[ck] = grounded[ck]
                else:
                    merged.pop(ck, None)
        if grounded.get('required'):
            merged['required'] = True
        out[key] = merged
    return out


def _schema_key_has_default(spec):
    spec = spec if isinstance(spec, dict) else {}
    default = spec.get('default')
    if default is None:
        return False
    if isinstance(default, str) and not default.strip():
        return False
    return True


def _param_names_mentioned_in_code(code):
    """Store/Load identifiers in the Code. Keyword arg names do not count."""
    try:
        tree = ast.parse(code or '')
    except SyntaxError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
    return names


def schema_keys_that_need_place(schema, code=None):
    """Keys that must exist in the Code: default, required, or already used.

    Unused keys without a default are ignored. A keyword ``months=-12``
    does not count as using the ``months`` variable.
    """
    parsed = _schema_as_dict(schema)
    if not parsed:
        return [key for key in _schema_key_set(schema)]
    mentioned = _param_names_mentioned_in_code(code)
    needed = []
    for key in parsed:
        if not _is_slash_param_key(key):
            continue
        spec = parsed.get(key) if isinstance(parsed.get(key), dict) else {}
        if (
            _schema_key_has_default(spec)
            or spec.get('required')
            or key in mentioned
        ):
            needed.append(key)
    return needed


def schema_keys_unread_by_code(schema, code):
    """Needed schema keys the Code does not read via ``try/except NameError``."""
    needed = schema_keys_that_need_place(schema, code)
    read = set(infer_param_keys_from_code(code))
    return [key for key in needed if key not in read]


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


def param_read_stub(name):
    """``try/except NameError`` read for one slash-arg key."""
    if not _is_slash_param_key(name):
        return ''
    return (
        'try:\n'
        '    %s = %s\n'
        'except NameError:\n'
        '    %s = None\n' % (name, name, name)
    )


def inject_unread_param_reads(code, schema):
    """Prepend NameError reads for schema keys the Code does not read yet."""
    unread = schema_keys_unread_by_code(schema, code)
    if not unread:
        return code or ''
    stubs = ''.join(param_read_stub(key) for key in unread)
    body = (code or '').lstrip('\n')
    if not stubs:
        return body
    if not body:
        return stubs
    return stubs + '\n' + body


# ``yearall = 2026`` from a captured turn must not overwrite the sandbox.
_LITERAL_ASSIGN_RE = re.compile(
    r'^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*'
    r'(-?\d+(?:\.\d+)?|'
    r"'(?:\\.|[^'])*'|"
    r'"(?:\\.|[^"])*"|'
    r'True|False|None)'
    r'\s*(#.*)?$'
)


def _schema_key_set(schema):
    if isinstance(schema, dict):
        return {key for key in schema if _is_slash_param_key(key)}
    if isinstance(schema, str):
        return _schema_key_set(parse_param_schema_txt(schema))
    return {key for key in (schema or []) if _is_slash_param_key(key)}


def drop_schema_literal_assigns(code, schema):
    """Drop ``key = <literal>`` so the sandbox value of that key wins.

    ``key = None`` is the NameError fallback, not a turn literal.
    Only keys that need a place (default, required, or already used).
    """
    keys = set(schema_keys_that_need_place(schema, code))
    if not keys:
        keys = _schema_key_set(schema)
    if not keys or not code:
        return code or ''
    kept = []
    changed = False
    for line in code.splitlines(True):
        raw = line[:-1] if line.endswith('\n') else line
        match = _LITERAL_ASSIGN_RE.match(raw)
        if match and match.group(2) in keys:
            value = (match.group(3) or '').strip()
            if value not in ('None', 'True', 'False'):
                changed = True
                continue
        kept.append(line)
    if not changed:
        return code
    return ''.join(kept)


def bind_code_to_schema_params(code, schema, env=None):
    """NameError reads plus the schema names used in the query and title."""
    return _replace_unique_default_literals(
        drop_schema_literal_assigns(
            inject_unread_param_reads(code, schema),
            schema,
        ),
        schema,
        env,
    )


def _schema_as_dict(schema):
    if isinstance(schema, dict):
        return schema
    if isinstance(schema, str):
        return parse_param_schema_txt(schema)
    return {}


def _schema_default_int_literal(spec, env=None):
    """Expanded integer default, or None. Tokens stay tokens without ``env``."""
    spec = spec if isinstance(spec, dict) else {}
    raw = spec.get('default')
    if raw in (None, ''):
        return None
    text = str(raw).strip()
    if env is not None:
        from .skill_param_tokens import expand_skill_param_text
        text = expand_skill_param_text(text, env)
    if _INT_DEFAULT.fullmatch(text):
        return text
    return None


def _unique_int_default_map(schema, env=None):
    """``{'12': 'months'}`` when exactly one key has that integer default."""
    parsed = _schema_as_dict(schema)
    hits = {}
    for key in _schema_key_set(parsed):
        lit = _schema_default_int_literal(parsed.get(key), env)
        if lit is None:
            continue
        hits.setdefault(lit, []).append(key)
    return {lit: names[0] for lit, names in hits.items() if len(names) == 1}


def _replace_number_tokens(src, mapping, schema=None):
    """Put the schema name in the parameter's slot, not in every matching number.

    A count (``12``) only replaces ``months=12`` / ``months=-12`` and
    ``else 12`` / ``or 12``. A year also replaces a bare 4-digit NUMBER
    (``date(2026, 1, 1)``). ``if n > 12`` stays.
    """
    if not src or not mapping:
        return src
    parsed = _schema_as_dict(schema)
    year_lits = set()
    for lit, key in mapping.items():
        if _schema_key_is_year_slot(key, parsed.get(key)):
            year_lits.add(lit)
    keys = set(mapping.values())
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError):
        return src
    spans = []
    n = len(tokens)
    i = 0
    while i < n:
        tok = tokens[i]
        if (
            tok.type == tokenize.NAME
            and tok.string in keys
            and i + 1 < n
            and tokens[i + 1].string == '='
        ):
            j = i + 2
            if j < n and tokens[j].string == '-':
                j += 1
            if j < n and tokens[j].type == tokenize.NUMBER:
                raw = tokens[j].string.lstrip('-')
                if mapping.get(raw) == tok.string:
                    spans.append((tokens[j].start, tokens[j].end, tok.string))
                    i = j + 1
                    continue
        if (
            tok.string in ('else', 'or')
            and i + 1 < n
            and tokens[i + 1].type == tokenize.NUMBER
        ):
            raw = tokens[i + 1].string.lstrip('-')
            name = mapping.get(raw)
            if name and raw not in year_lits:
                spans.append((tokens[i + 1].start, tokens[i + 1].end, name))
                i += 2
                continue
        if tok.type == tokenize.NUMBER:
            raw = tok.string.lstrip('-')
            name = mapping.get(raw)
            if name and raw in year_lits:
                spans.append((tok.start, tok.end, name))
        i += 1
    if not spans:
        return src
    lines = src.splitlines(True)
    for (sr, sc), (er, ec), name in reversed(spans):
        if sr != er or sr < 1 or sr > len(lines):
            continue
        line = lines[sr - 1]
        lines[sr - 1] = line[:sc] + name + line[ec:]
    return ''.join(lines)


# Card title (``result['title']`` / ``summary``) and the wrap ``_page_title``.
_TITLE_LINE_RE = re.compile(
    r'^(\s*(?:'
    r'_page_title\s*=\s*'
    r'|result\s*\[\s*[\'"]title[\'"]\s*\]\s*=\s*'
    r'|[\'"]title[\'"]\s*:\s*'
    r'|[\'"]summary[\'"]\s*:\s*'
    r'))([\'"])(.*)\2(\s*,?\s*)$',
)

_ISO_ASSIGN_RE = re.compile(
    r'^([ \t]*)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*[\'"](\d{4}-\d{2}-\d{2})[\'"][ \t]*$',
    re.M,
)
_ISO_STR_RE = re.compile(r'[\'"](\d{4}-\d{2}-\d{2})[\'"]')


def _is_title_line(line):
    raw = line[:-1] if line.endswith('\n') else line
    return bool(_TITLE_LINE_RE.match(raw))


def _replace_title_literals(line, mapping):
    """Title / summary / ``_page_title`` with ``12`` → ``%s`` % (months,)."""
    raw = line[:-1] if line.endswith('\n') else line
    match = _TITLE_LINE_RE.match(raw)
    if not match or not mapping:
        return line
    prefix, quote, body, suffix = match.groups()
    ordered = sorted(mapping, key=len, reverse=True)
    pattern = re.compile(
        r'(?<![0-9-])(%s)(?![0-9-])' % '|'.join(re.escape(lit) for lit in ordered),
    )
    names = []
    pieces = []
    last = 0
    for hit in pattern.finditer(body):
        pieces.append(body[last:hit.start()].replace('%', '%%'))
        pieces.append('%s')
        names.append(mapping[hit.group(1)])
        last = hit.end()
    if not names:
        return line
    pieces.append(body[last:].replace('%', '%%'))
    fmt = '%s%s%s%s %% (%s,)%s' % (
        prefix, quote, ''.join(pieces), quote, ', '.join(names), suffix,
    )
    if line.endswith('\n'):
        fmt += '\n'
    return fmt


def _parse_iso_day(text):
    parts = (text or '').split('-')
    if len(parts) != 3:
        return None
    try:
        return _date(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def _month_span(start, end):
    if end < start:
        start, end = end, start
    return (end.year - start.year) * 12 + (end.month - start.month)


def _is_calendar_year_window(start, end):
    if start > end:
        start, end = end, start
    return (
        start.month == 1 and start.day == 1
        and end.month == 12 and end.day >= 28
        and start.year == end.year
    )


def _year_slot_key(mapping, schema):
    parsed = _schema_as_dict(schema)
    for _lit, key in mapping.items():
        if _schema_key_is_year_slot(key, parsed.get(key)):
            return key
    for key, spec in parsed.items():
        if _is_slash_param_key(key) and _schema_key_is_year_slot(key, spec):
            return key
    return None


def _count_slot_key(mapping, schema):
    """The months/count hole, even when the captured span is not that default."""
    parsed = _schema_as_dict(schema)
    preferred = []
    others = []
    seen = set()
    names = list(mapping.values())
    for key in parsed:
        if key not in names:
            names.append(key)
    for key in names:
        if not key or key in seen:
            continue
        if not _is_slash_param_key(key):
            continue
        if _schema_key_is_year_slot(key, parsed.get(key)):
            continue
        spec = parsed.get(key) if isinstance(parsed.get(key), dict) else {}
        typ = str(spec.get('type') or '').strip().lower()
        if typ and typ not in ('integer', 'number', 'int'):
            continue
        seen.add(key)
        if (key or '').strip().casefold() in ('months', 'meses'):
            preferred.append(key)
        elif typ in ('integer', 'number', 'int') or key in mapping.values():
            others.append(key)
    return (preferred or others or [None])[0]


def _count_key_for_span(span, mapping, schema):
    parsed = _schema_as_dict(schema)
    for lit, key in mapping.items():
        if _schema_key_is_year_slot(key, parsed.get(key)):
            continue
        try:
            n = int(lit)
        except (TypeError, ValueError):
            continue
        if abs(span - n) <= 1:
            return key
    return _count_slot_key(mapping, schema)


def _iso_assign_hits(head):
    hits = []
    for match in _ISO_ASSIGN_RE.finditer(head or ''):
        day = _parse_iso_day(match.group(3))
        if day:
            hits.append((day, match))
    return hits


def _iso_window_plan(head, mapping, schema):
    """How to bind a captured from/to ISO window, or None."""
    if not head:
        return None
    mapping = mapping or {}
    hits = _iso_assign_hits(head)
    unique = sorted({day for day, _match in hits})
    if not unique:
        found = []
        for match in _ISO_STR_RE.finditer(head):
            if _iso_on_comment_line(head, match.start()):
                continue
            day = _parse_iso_day(match.group(1))
            if day:
                found.append(day)
        unique = sorted(set(found))
        hits = []
    if not unique or len(unique) > 2:
        return None
    start = unique[0]
    end = unique[-1]
    ykey = _year_slot_key(mapping, schema)
    if len(unique) == 1:
        ckey = _count_key_for_span(
            _month_span(start, _date.today()), mapping, schema,
        )
        if not ckey:
            return None
        start_match = hits[0][1] if hits else None
        return {
            'kind': 'year_or_count' if ykey else 'count',
            'key': ckey,
            'year_key': ykey,
            'start_match': start_match,
            'end_match': None,
            'start_iso': start.isoformat(),
            'end_iso': '',
            'start_name': start_match.group(2) if start_match else 'date_from',
            'end_name': '',
        }
    ckey = _count_key_for_span(_month_span(start, end), mapping, schema)
    start_match = end_match = None
    for day, match in hits:
        if day == start:
            start_match = match
        if day == end:
            end_match = match
    base = {
        'start_match': start_match,
        'end_match': end_match,
        'start_iso': start.isoformat(),
        'end_iso': end.isoformat(),
        'start_name': start_match.group(2) if start_match else 'date_from',
        'end_name': end_match.group(2) if end_match else 'date_to',
    }
    if ykey and ckey:
        base.update(kind='year_or_count', key=ckey, year_key=ykey)
        return base
    if _is_calendar_year_window(start, end) and ykey:
        base.update(kind='year', key=ykey, year_key=ykey)
        return base
    if ckey:
        base.update(kind='count', key=ckey)
        return base
    return None


def _leading_ws(line):
    text = line or ''
    i = 0
    while i < len(text) and text[i] in ' \t':
        i += 1
    return text[:i]


def _line_span(text, pos):
    start = (text or '').rfind('\n', 0, pos) + 1
    end = (text or '').find('\n', pos)
    if end < 0:
        end = len(text or '')
    return start, end


def _iso_on_comment_line(text, pos):
    start, end = _line_span(text, pos)
    return (text or '')[start:end].lstrip().startswith('#')


def _insert_before_statement(text, pos):
    """Line start and indent of the statement that contains ``pos``."""
    start, end = _line_span(text, pos)
    cur_start = start
    cur_indent = _leading_ws((text or '')[start:end])
    scan = start
    while scan > 0:
        prev_start = text.rfind('\n', 0, scan - 1) + 1
        pline = text[prev_start:scan].rstrip('\n')
        raw = pline.strip()
        if not raw or raw.startswith('#'):
            scan = prev_start
            continue
        pindent = _leading_ws(pline)
        if len(pindent) < len(cur_indent):
            if raw.endswith(':'):
                return cur_start, cur_indent
            cur_start = prev_start
            cur_indent = pindent
        scan = prev_start
    return cur_start, cur_indent


def _iso_plan_block(plan, indent):
    if plan['kind'] == 'year':
        return _year_iso_block(
            indent, plan['key'], plan['start_name'], plan['end_name'],
        )
    if plan['kind'] == 'year_or_count':
        return _year_or_count_iso_block(
            indent, plan['year_key'], plan['key'],
            plan['start_name'], plan['end_name'],
        )
    return _rolling_iso_block(
        indent, plan['key'], plan['start_name'], plan['end_name'],
    )


def _iso_assign_line_indexes(head, matches):
    indexes = []
    for match in matches:
        if match is None:
            continue
        indexes.append(head[:match.start()].count('\n'))
    return indexes


def _rolling_iso_block(indent, key, start_name, end_name):
    lines = [
        '%s_end = today' % indent,
        '%s_m = int(%s)' % (indent, key),
        '%s_mi = _end.month - 1 - _m' % indent,
        (
            '%s%s = date(_end.year + _mi // 12, _mi %% 12 + 1, 1)'
            '.strftime(\'%%Y-%%m-%%d\')'
        ) % (indent, start_name),
    ]
    if end_name:
        lines.append(
            '%s%s = _end.strftime(\'%%Y-%%m-%%d\')' % (indent, end_name),
        )
    return '\n'.join(lines) + '\n'


def _year_iso_block(indent, key, start_name, end_name):
    lines = [
        '%s%s = \'%%04d-01-01\' %% int(%s)' % (indent, start_name, key),
    ]
    if end_name:
        lines.append(
            '%s%s = \'%%04d-12-31\' %% int(%s)' % (indent, end_name, key),
        )
    return '\n'.join(lines) + '\n'


def _year_or_count_iso_block(indent, year_key, count_key, start_name, end_name):
    """``year`` if the slash set it, otherwise the months count."""
    inner = indent + '    '
    year_body = _year_iso_block(inner, year_key, start_name, end_name)
    count_body = _rolling_iso_block(inner, count_key, start_name, end_name)
    return '%sif %s:\n%s%selse:\n%s' % (
        indent, year_key, year_body, indent, count_body,
    )


def _replace_iso_windows(head, mapping, schema):
    """Turn a captured ``date_from = '2025-11-01'`` window into the param."""
    plan = _iso_window_plan(head, mapping, schema)
    if not plan:
        return head
    indent = ''
    start_match = plan.get('start_match')
    if start_match is not None:
        indent = start_match.group(1)
    elif plan.get('end_match') is not None:
        indent = plan['end_match'].group(1)
    drop = set(_iso_assign_line_indexes(
        head, (plan.get('start_match'), plan.get('end_match')),
    ))
    lines = head.splitlines(True)
    if drop:
        block = _iso_plan_block(plan, indent)
        out = []
        inserted = False
        for idx, line in enumerate(lines):
            if idx in drop:
                if not inserted:
                    out.append(block)
                    inserted = True
                continue
            out.append(line)
        head = ''.join(out)
    else:
        first = None
        for match in _ISO_STR_RE.finditer(head):
            if match.group(1) not in (plan['start_iso'], plan['end_iso']):
                continue
            if _iso_on_comment_line(head, match.start()):
                continue
            first = match
            break
        if first is None:
            return head
        line_start, indent = _insert_before_statement(head, first.start())
        block = _iso_plan_block(plan, indent)
        head = head[:line_start] + block + head[line_start:]
    if plan['start_iso']:
        head = re.sub(
            r'[\'"]%s[\'"]' % re.escape(plan['start_iso']),
            plan['start_name'],
            head,
        )
    if plan['end_iso'] and plan['end_name']:
        head = re.sub(
            r'[\'"]%s[\'"]' % re.escape(plan['end_iso']),
            plan['end_name'],
            head,
        )
    return head


def _replace_unique_default_literals(code, schema, env=None):
    """Use schema names in the query, titles and date window. Not the HTML."""
    mapping = _unique_int_default_map(schema, env)
    if not code:
        return code or ''
    if (
        not mapping
        and not _year_slot_key({}, schema)
        and not _count_slot_key({}, schema)
    ):
        return code or ''
    head, tail = split_page_html_skill_code(code)
    head_out = []
    for line in head.splitlines(True):
        if _is_title_line(line):
            head_out.append(_replace_title_literals(line, mapping))
        else:
            head_out.append(line)
    head = _replace_iso_windows(''.join(head_out), mapping, schema)
    head = _replace_number_tokens(head, mapping, schema)
    kept = []
    for line in tail.splitlines(True):
        if _is_title_line(line):
            kept.append(_replace_title_literals(line, mapping))
        else:
            kept.append(line)
    return head + ''.join(kept)


def _literal_assigns_remain(code, schema):
    keys = set(schema_keys_that_need_place(schema, code))
    if not keys:
        keys = _schema_key_set(schema)
    if not keys:
        return False
    for line in (code or '').splitlines():
        match = _LITERAL_ASSIGN_RE.match(line)
        if not match or match.group(2) not in keys:
            continue
        if (match.group(3) or '').strip() in ('None', 'True', 'False'):
            continue
        return True
    return False


def _unique_default_literals_remain(code, schema, env=None):
    """True when a default still sits in its slot, title or date window."""
    mapping = _unique_int_default_map(schema, env)
    if not mapping or not code:
        return False
    head, tail = split_page_html_skill_code(code)
    title = ''.join(
        line for line in (head + tail).splitlines(True)
        if _is_title_line(line)
    )
    if _iso_window_plan(head, mapping, schema):
        return True
    for lit, key in mapping.items():
        slot = re.compile(
            r'\b%s\s*=\s*-?%s\b' % (re.escape(key), re.escape(lit)),
        )
        if slot.search(head):
            return True
        if title and re.search(
            r'(?<![0-9-])%s(?![0-9-])' % re.escape(lit),
            title,
        ):
            return True
    return False


def schema_params_need_place(code, schema, env=None):
    """True when a default/required key is unread, overwritten, or still a turn literal."""
    if not schema_keys_that_need_place(schema, code):
        return False
    if schema_keys_unread_by_code(schema, code):
        return True
    if _literal_assigns_remain(code, schema):
        return True
    return _unique_default_literals_remain(code, schema, env)


def split_page_html_skill_code(code):
    """``(query head, page tail)``. Tail starts at ``_page_template`` / ``page_html``."""
    text = code or ''
    match = re.search(r'\n_page_template\s*=', text)
    if match:
        return text[:match.start()].rstrip(), text[match.start():]
    idx = text.find('page_html(')
    if idx < 0:
        return text, ''
    line_start = text.rfind('\n', 0, idx) + 1
    return text[:line_start].rstrip(), text[line_start:]


def query_head_for_param_rewrite(code):
    """Query head plus ``_page_title``. The HTML template stays in the tail."""
    head, tail = split_page_html_skill_code(code)
    titles = []
    rest = []
    for line in tail.splitlines(True):
        if _is_title_line(line) or line.lstrip().startswith('_page_title'):
            titles.append(line)
        else:
            rest.append(line)
    if titles:
        block = ''.join(titles)
        if head:
            head = head.rstrip() + '\n' + block
        else:
            head = block
    return head, ''.join(rest)


_CODE_PARAM_REWRITE_SYSTEM = (
    'Rewrite the skill Python so every parameter WITH A DEFAULT exists in '
    'the Code as a sandbox variable and is used in the query, result title '
    'and _page_title. '
    'Return Python only: no markdown fences, no prose, no JSON. '
    'Keep the same models, searches, metrics and result shape. '
    'Do not add a model, field, or filter that is not already in the Code '
    'or named in the trainer description. '
    'For each of those keys, the Code must read the sandbox global with:\n'
    'try:\n'
    '    name = name\n'
    'except NameError:\n'
    '    name = None\n'
    'Replace the turn hardcoded numbers, ISO dates and title text with '
    'those names. Use preloaded date, today and calendar. Do not import '
    'dateutil. A required key has no fallback in the Code (not `else 12`): '
    'empty shows Help. A key with no Default on the skill form MUST keep '
    'a second-level default in the Code (the turn value). A form Default '
    'already fills the sandbox: do not overwrite it. Parameters with no '
    'default that the Code does not use may be omitted.'
)


def build_code_param_rewrite_prompt(code, schema, trainer_text=''):
    """Short Python call: keys with a default must have a place in the Code."""
    unread = schema_keys_unread_by_code(schema, code)
    parsed = _schema_as_dict(schema)
    needed = schema_keys_that_need_place(schema, code)
    optional = [
        k for k in parsed
        if _is_slash_param_key(k) and k not in needed
    ]
    extra = ''
    if unread:
        extra = ' Keys with a default the Code does not read yet: %s.' % (
            ', '.join(unread),
        )
    elif needed:
        extra = (
            ' Keys that must be used (default or already in the Code), '
            'including in _page_title: %s.' % ', '.join(needed)
        )
    parts = []
    if needed:
        parts.append('Parameters that need a place: %s' % ', '.join(needed))
    if optional:
        parts.append(
            'Parameters with no default, unused — omit them: %s'
            % ', '.join(optional)
        )
    desc = (trainer_text or '').strip()
    if desc:
        parts.append('Trainer description:\n%s' % desc)
    parts.append('Code:\n%s' % (code or ''))
    return _CODE_PARAM_REWRITE_SYSTEM + extra, '\n\n'.join(parts)


def parse_rewritten_skill_code(text):
    """Strip markdown fences; return Python source or empty."""
    s = (text or '').strip()
    if not s:
        return ''
    s = re.sub(r'^```(?:python|py)?\s*\n?', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\n?```\s*$', '', s)
    return s.strip()


def accept_rewritten_code(code, schema):
    """Cleaned Python if it parses and reads every schema key; else empty."""
    cleaned = parse_rewritten_skill_code(code)
    if not cleaned:
        return ''
    try:
        ast.parse(cleaned)
    except SyntaxError:
        return ''
    if schema_keys_unread_by_code(schema, cleaned):
        return ''
    return cleaned


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


def leftover_after_ordinals(raw, params, bound_map, schema=None):
    """Positional tokens still unbound (empty → skip the LLM)."""
    del params, schema
    bound_vals = set()
    for val in (bound_map or {}).values():
        bound_vals.add(str(val).strip())
    unbound = [
        tok for tok in positional_tokens(raw)
        if str(tok).strip() not in bound_vals
    ]
    if unbound:
        return ' '.join(str(tok) for tok in unbound).strip()
    if bound_map:
        return ''
    return leftover_free_text(raw)


def hybrid_unresolved_text(raw, leftover, bound_map):
    """Phrase the short call should see.

    Prose left over → the whole slash text, not the chopped tail. Formal
    binds stay in the deterministic fill and win on merge. Nothing left
    and something already bound → empty (no call).
    """
    if (leftover or '').strip():
        return ' '.join(str(raw or '').split())
    if bound_map:
        return ''
    return ' '.join(str(raw or '').split())


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
    tokens = [part for part in _split_arg_tokens(raw) if not _is_kv_token(part)]
    return _coalesce_formal_code_tokens(tokens)


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


def skill_code_refusal(code, skill_code='skill'):
    """Why this code_body may not run, or empty.

    Checked on save and again on every run: a row saved before a rule was
    tightened still runs with the caller's rights.
    """
    from odoo import _
    from ..controllers.validators import validate_relaxaicode_source_ast

    ok, err, writes = validate_relaxaicode_source_ast(code)
    if not ok:
        return _(
            'The code of skill «%s» breaks the sandbox rules:\n\n%s'
        ) % (skill_code or '?', err)
    if writes:
        return _(
            'The code of skill «%s» writes to the database. A skill only '
            'reads; changes go in propose_steps and the user confirms them.'
        ) % (skill_code or '?')
    return ''


def bootstrap_skill_code_body(env, code, arguments='', skill_code='skill',
                              extra_params=None, previous_result=None,
                              diag=None, param_schema=None):
    """Ejecuta code_body en sandbox seguro. Devuelve ``result`` dict o None.

    ``extra_params`` (opcional): claves ya resueltas por el schema. Se fusionan
    sobre el parse. Si hay alguna clave de schema, ``arguments`` y ``lugar``
    dejan de llevar la frase: el skill no la vuelve a interpretar. Un valor
    None solo asegura que la clave exista.

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
    refused = skill_code_refusal(code, skill_code)
    if refused:
        if isinstance(diag, dict):
            diag['bootstrap_error'] = refused
        _logger.warning('Skill bootstrap refused for %s: %s', skill_code, refused)
        return None
    from .skill_param_tokens import expand_skill_param_values
    params = parse_skill_arguments(arguments)
    enrich_params_with_dates(params)
    params = overlay_resolved_params(params, extra_params)
    params = expand_skill_param_values(params, env)
    live = [
        key for key, val in params.items()
        if _is_slash_param_key(key) and val not in (None, '', [])
    ]
    if param_schema:
        code = bind_code_to_schema_params(code, param_schema, env)
    elif live:
        code = drop_schema_literal_assigns(code, live)
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
            return wrap_bare_images_clickable(ft, env=env)
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
                        max_rounds=5, diag=None, probe=False,
                        param_schema=None):
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

    ``probe``: a plan that needs the toast returns ``needs_confirmation``
    instead of creating the pending operation, which is committed on a cursor
    of its own and would outlive the caller's rollback.
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
            request_safe_plan,
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
                param_schema=param_schema,
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
            keys = sorted(bootstrap.keys())
            if not keys:
                return _bail('empty_result')
            return _bail('no_propose_steps(keys=%s)' % keys)

        ok, err = validate_safe_plan(steps, env)
        if not ok:
            return _bail('invalid_plan: %s' % err)

        # Planes no auto-confirmables (CRUD, URL/API no trusted) → toast.
        # Trusted fetch_url + trusted api_call se ejecutan aquí (multi-ronda).
        if not _all_steps_auto_confirmable(env, steps):
            if probe:
                return {'needs_confirmation': True, 'verification_id': None}
            pending = request_safe_plan(
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


_FAST_PATH_PUBLISH_BLOCKERS = frozenset((
    'presentation_no_html',
    'empty_result',
    'max_rounds_exhausted',
    'no_continue_no_presentation',
))


def check_skill_fast_path_publishable(
    env, code, arguments='', args_policy='default', param_schema='',
    skill_code='skill',
):
    """Return a user-facing error when ``/slash`` would fail with empty args.

    Returns ``None`` when publishable or when empty-args validation does not
    apply (required parameters, bootstrap exception, install-time registry).
    """
    body = (code or '').strip()
    if not body or env is None:
        return None
    if (getattr(env, 'context', None) or {}).get('skill_skip_body_check'):
        return None
    if not getattr(env.registry, 'ready', False):
        return None
    policy = (args_policy or 'default').strip() or 'default'
    if policy != 'none':
        schema = parse_param_schema_txt(param_schema or '')
        if schema_required_keys(schema):
            return None
    diag = {}
    try:
        # A publish check must not open a page or spend a design call.
        check_env = env(context=dict(env.context, skill_publish_check=True))
        bootstrap = bootstrap_skill_code_body(
            check_env, body, arguments=arguments, skill_code=skill_code,
            diag=diag, param_schema=param_schema,
        )
    except Exception:
        return None
    if not isinstance(bootstrap, dict):
        return None
    fast = try_skill_fast_path(
        env, bootstrap, code=body, arguments=arguments,
        skill_code=skill_code, diag=diag, probe=True,
        param_schema=param_schema,
    )
    from odoo import _
    label = skill_code or 'skill'
    if isinstance(fast, dict) and fast.get('needs_confirmation'):
        return _(
            'Skill "%s" needs supervised safe-plan confirmation (toast). '
            'Capture only auto-confirmable fetch_url or trusted api_call '
            'steps, or edit the Code before publishing.'
        ) % label
    if fast is not None:
        return None
    reason = (diag or {}).get('reason') or ''
    if reason in _FAST_PATH_PUBLISH_BLOCKERS:
        return _(
            'Skill "%s" would fail on /slash with no arguments (%s). '
            'The Code must fetch live data on each run and include every '
            'phase from the source turn (fetch, transform, present).'
        ) % (label, reason)
    return None
