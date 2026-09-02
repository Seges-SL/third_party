# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""JSON contract for ``ai.change.journal`` — no Odoo import.

Heterogeneous before/after payloads: the same document is used by the Revert
button, the inspection form, and a later AI session. Indexed columns on the
model are a projection of this payload, not a substitute.
"""
from __future__ import annotations

import json

SCHEMA_VERSION = 1

MUTATING_OPS = frozenset({
    'create', 'write', 'copy', 'unlink', 'action', 'field_required',
})

KIND_BY_MODEL = {
    'ir.ui.view': 'view_modifier',
    'ir.model.fields': 'field_meta',
    'ir.module.module': 'module',
    'ir.actions.report': 'report',
    'res.groups': 'acl',
    'ir.model.access': 'acl',
    'ir.rule': 'acl',
}

_SENSITIVE_PARTS = (
    'password', 'api_key', 'secret', 'token', 'private_key', 'otp',
    'smtp_pass', 'oauth',
)


def is_sensitive_key(name):
    n = (name or '').lower()
    return any(part in n for part in _SENSITIVE_PARTS)


def classify_change_kind(model, op, action_code=None):
    """Domain-agnostic kind from technical model / verb. No business literals."""
    if op == 'field_required':
        return 'field_meta'
    if op == 'action':
        return 'trusted_action'
    kind = KIND_BY_MODEL.get(model)
    if kind:
        return kind
    if model and (model.startswith('acl.') or model.endswith('.rule')):
        return 'acl'
    return 'generic'


def normalize_value(value):
    """Make ``read()`` output JSON- and write()-friendly (m2o → id)."""
    if isinstance(value, tuple) and len(value) >= 1 and isinstance(value[0], int):
        return value[0]
    if isinstance(value, list) and value:
        ids = []
        all_ok = True
        for item in value:
            if isinstance(item, int):
                ids.append(item)
            elif isinstance(item, tuple) and item and isinstance(item[0], int):
                ids.append(item[0])
            else:
                all_ok = False
                break
        if all_ok:
            return ids
    if hasattr(value, 'isoformat'):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return value


def redact_record(record):
    out = {}
    for key, value in (record or {}).items():
        if key == 'id':
            out[key] = value
            continue
        if is_sensitive_key(key):
            out[key] = '***'
        else:
            out[key] = normalize_value(value)
    return out


def build_payload(op, model, ids, fields, records, meta=None):
    return {
        'schema_version': SCHEMA_VERSION,
        'op': op,
        'model': model or '',
        'ids': list(ids or []),
        'fields': list(fields or []),
        'records': list(records or []),
        'meta': dict(meta or {}),
    }


def dumps_payload(payload):
    return json.dumps(payload or {}, ensure_ascii=False, default=str)


def loads_payload(text):
    if not text:
        return {}
    if isinstance(text, dict):
        return text
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def initial_reversible(op, before_payload, after_payload):
    """Return ``(reversible, reason)`` for a freshly applied step."""
    after = after_payload or {}
    before = before_payload or {}
    if op in ('create', 'copy'):
        ids = after.get('ids') or []
        if ids:
            return True, 'create/copy can unlink the new record'
        return False, 'no created id to unlink'
    if op == 'write':
        if before.get('records'):
            return True, 'write can restore before_json'
        return False, 'no before snapshot'
    if op == 'unlink':
        return False, 'unlink revert is not supported in this version'
    if op == 'action':
        meta = after.get('meta') or {}
        if meta.get('reversible'):
            return True, meta.get('reversible_reason') or 'trusted action declared undo'
        return False, 'trusted action has no undo'
    if op == 'field_required':
        return False, 'field_required revert is not supported in this version'
    return False, 'operation is not reversible'


def write_vals_from_before(before_payload):
    """``{id: vals}`` for a write revert. Drops id / display_name / redacted."""
    mapping = {}
    for row in (before_payload or {}).get('records') or []:
        if not isinstance(row, dict) or row.get('id') is None:
            continue
        rec_id = int(row['id'])
        vals = {}
        for key, value in row.items():
            if key in ('id', 'display_name'):
                continue
            if value == '***':
                continue
            vals[key] = value
        mapping[rec_id] = vals
    return mapping


def one_line_summary(op, model, ids, change_kind=None):
    n = len(ids or [])
    kind = (' [%s]' % change_kind) if change_kind and change_kind != 'generic' else ''
    return '%s %s × %s%s' % (op or '?', model or '?', n, kind)
