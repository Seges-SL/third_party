# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Prompts that write a skill help and its parameters, and reading their answer back into the schema."""

from __future__ import annotations
import ast
import json
import re

from .skill_runtime_param_schema import (
    author_copy_locale,
    infer_param_keys_from_code,
    _is_slash_param_key,
    param_rows_fingerprint,
    param_rows_to_prose,
    _schema_as_dict,
    _schema_key_set,
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
