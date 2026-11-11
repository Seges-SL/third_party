# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Open the form a ``kind=form`` card asks for. Nothing is written here.

A skill proposes a record; the person opens the form, checks it and saves or
discards. Everything runs as the person who clicks: no ``sudo()``. Saving is
the ordinary Odoo save, with their rights and record rules.

Proposed values become ``default_*`` keys. Only fields the person can see
(``fields_get`` hides those of other groups) and edit (not readonly) are
passed; the rest is returned as ``dropped`` and never reaches the form.
What a document type is (a vendor bill, not a journal entry) comes from the
Odoo action the card names, not from the values.
"""

import datetime

from odoo import _
from odoo.exceptions import AccessError, UserError

from odoo.addons.pns_base.utils.compat import ODOO_VERSION

_SCALAR_TYPES = frozenset((
    'char', 'text', 'integer', 'float', 'monetary', 'boolean',
    'date', 'datetime', 'selection', 'many2one',
))


def _may(record_or_model, operation):
    try:
        if ODOO_VERSION >= 18:
            record_or_model.check_access(operation)
        else:
            record_or_model.check_access_rights(operation)
            if record_or_model.ids:
                record_or_model.check_access_rule(operation)
    except AccessError:
        return False
    return True


def _window_action(env, xmlid):
    act = env.ref(xmlid, raise_if_not_found=False)
    if not act or act._name != 'ir.actions.act_window':
        raise UserError(_('That form is not available.'))
    return act


def _clean_value(env, field, value):
    """The value the form may take, or ``None`` to leave the field alone."""
    ftype = field.get('type')
    if ftype == 'boolean':
        return bool(value)
    if value in (None, ''):
        return None
    if ftype in ('char', 'text'):
        return str(value)[:5000]
    if ftype == 'integer':
        return int(value)
    if ftype in ('float', 'monetary'):
        return float(value)
    if ftype == 'date':
        return datetime.date.fromisoformat(str(value)[:10]).isoformat()
    if ftype == 'datetime':
        text = str(value).replace('T', ' ')[:19]
        return datetime.datetime.fromisoformat(text).strftime('%Y-%m-%d %H:%M:%S')
    if ftype == 'selection':
        keys = {str(key) for key, _label in (field.get('selection') or [])}
        return str(value) if str(value) in keys else None
    if ftype == 'many2one':
        relation = field.get('relation')
        if not relation or relation not in env:
            return None
        record = env[relation].browse(int(value)).exists()
        if not record or not _may(record, 'read'):
            return None
        return record.id
    return None


def _editable(field, birth_state):
    """Not readonly, or (Odoo 14 ``states``) editable in the state a new record starts in."""
    if not field.get('readonly'):
        return True
    for modifier in (field.get('states') or {}).get(birth_state) or ():
        if tuple(modifier) == ('readonly', False):
            return True
    return False


def form_action(env, action=None, model=None, res_id=None, values=None):
    """Return ``(action, defaults, dropped)`` for the client's ``doAction``.

    ``res_id`` opens that record to edit, with no proposed values. Without it
    the form is a new record carrying ``defaults``.
    """
    act = _window_action(env, action) if action else None
    res_model = act.res_model if act else (model or '')
    if not res_model or res_model not in env:
        raise UserError(_('That form is not available.'))
    Model = env[res_model]
    try:
        res_id = int(res_id or 0)
    except (TypeError, ValueError):
        res_id = 0

    result = {
        'type': 'ir.actions.act_window',
        'name': act.name if act else Model._description,
        'res_model': res_model,
        'view_mode': 'form',
        'views': [[False, 'form']],
        'target': 'new',
    }
    if act and act.context:
        result['context'] = act.context

    if res_id:
        record = Model.browse(res_id).exists()
        if not record or not _may(record, 'write'):
            raise UserError(_('You cannot edit that record.'))
        result['res_id'] = record.id
        return result, {'form_view_initial_mode': 'edit'}, []

    if not _may(Model, 'create'):
        raise UserError(_('You cannot create that kind of record.'))
    fields = Model.fields_get(
        attributes=['type', 'readonly', 'relation', 'selection', 'states'],
    )
    birth_state = None
    if 'state' in fields:
        birth_state = Model.default_get(['state']).get('state')
    defaults = {}
    dropped = []
    for name, value in (values or {}).items():
        field = fields.get(name)
        if (
            not field
            or not _editable(field, birth_state)
            or field.get('type') not in _SCALAR_TYPES
        ):
            dropped.append(name)
            continue
        try:
            clean = _clean_value(env, field, value)
        except (TypeError, ValueError):
            clean = None
        if clean is None:
            dropped.append(name)
            continue
        defaults['default_%s' % name] = clean
    return result, defaults, sorted(dropped)
