# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Markdown card for the record a Safe Plan just wrote.

Nameless: labels, types and the reference all come from the model, so the
card reads the same for a notice, an invoice or a contact. The database id
is not in it — nobody sees an id in Odoo.
"""
from __future__ import annotations

from .record_label import placed_label

_MAX_ROWS = 8
_MAX_TEXT = 160
_SKIP_TYPES = ('binary', 'image', 'html', 'one2many', 'many2many')


def _meta(rec, names):
    try:
        return rec.fields_get(names, ['string', 'type', 'selection']) or {}
    except Exception:
        return {}


def _short(text):
    out = ' '.join(str(text).split())
    return out[:_MAX_TEXT] + '…' if len(out) > _MAX_TEXT else out


def _date_text(env, value, is_datetime):
    try:
        from odoo.tools import format_date, format_datetime
        if is_datetime:
            return format_datetime(env, value)
        return format_date(env, value)
    except Exception:
        return _short(value)


def _value_text(env, rec, name, meta):
    """What a person would read in the form, not what the column stores."""
    ftype = meta.get('type')
    try:
        value = rec[name]
    except Exception:
        return None
    if ftype == 'many2one':
        if not value:
            return None
        # A related record is worth its address: the name alone does not say
        # which of the two companies with those words this one is.
        return placed_label(env, value._name, value.id) or _short(value.display_name)
    if value in (False, None, ''):
        return None
    if ftype == 'selection':
        for key, label in (meta.get('selection') or []):
            if key == value:
                return _short(label)
        return _short(value)
    if ftype == 'boolean':
        return None
    if ftype in ('date', 'datetime'):
        return _date_text(env, value, ftype == 'datetime')
    return _short(value)


def instance_assigned_fields(rec, written=()):
    """Char fields the instance pre-filled with a placeholder and replaced.

    That is how Odoo gives a record its reference: a default like ``/`` and a
    sequence on create. It is the name people use for the record, it is never
    in the values anyone sent, and it is what belongs at the top of the card.
    """
    names = [
        name for name, field in rec._fields.items()
        if field.type == 'char' and field.store and name not in written
    ]
    if not names:
        return []
    try:
        defaults = rec.browse().default_get(names)
    except Exception:
        return []
    out = []
    for name in names:
        placeholder = defaults.get(name)
        if not (isinstance(placeholder, str) and placeholder.strip()):
            continue
        try:
            value = rec[name]
        except Exception:
            continue
        if isinstance(value, str) and value.strip() and value != placeholder:
            out.append(name)
    return out


def record_reference(env, model, rid):
    """What people call this record out loud, or ``None``.

    The reference the instance gave it on create —a sequence behind a
    placeholder— which is what is written on the paperwork and said on the
    phone. Falls back to the record's own name and never to the id: an id
    is not on any screen in Odoo, so it answers no question anyone has.
    """
    if env is None or not model or not rid or model not in env:
        return None
    try:
        rec = env[model].browse(int(rid))
        if not rec.exists():
            return None
        for name in instance_assigned_fields(rec):
            value = rec[name]
            if isinstance(value, str) and value.strip():
                return _short(value)
        return _short(rec.display_name) or None
    except Exception:
        return None


def record_card(env, model, rid, values=None, title_of=None):
    """Markdown lines for one written record, or None when it cannot be read.

    ``title_of`` wraps the header in the caller's wording; without it the
    header is the record name and the model label on their own.
    """
    if env is None or not model or not rid or model not in env:
        return None
    try:
        rec = env[model].browse(int(rid))
        if not rec.exists():
            return None
        title = _short(rec.display_name)
        label = _short(rec._description or model)
    except Exception:
        return None
    written = [name for name in (values or {}) if name in rec._fields]
    order = instance_assigned_fields(rec, written=set(written)) + written
    meta = _meta(rec, order) if order else {}
    rows = []
    for name in order:
        info = meta.get(name) or {}
        if info.get('type') in _SKIP_TYPES:
            continue
        text = _value_text(env, rec, name, info)
        # The header already carries the record's own name.
        if not text or text == title:
            continue
        rows.append('  - %s: %s' % (info.get('string') or name, text))
        if len(rows) >= _MAX_ROWS:
            break
    head = '**%s** (%s)' % (title, label)
    return ['- ' + (title_of(head) if title_of else head)] + rows
