# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Enrich the client-captured screen_context (model, id, view) with a compact ORM
summary for runtime injection into AgentEngine.
"""

import json
import logging

_logger = logging.getLogger(__name__)

# Campos opcionales a incluir si existen en el modelo (sin hardcodear por app).
_CANDIDATE_SUMMARY_FIELDS = (
    'state',
    'stage_id',
    'partner_id',
    'user_id',
    'amount_total',
    'amount_untaxed',
    'date_order',
    'date',
    'invoice_date',
    'name',
)


def _safe_int(value):
    try:
        if value in (None, False, ''):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_field_value(record, field_name):
    field = record._fields.get(field_name)
    if not field:
        return None
    try:
        val = record[field_name]
    except Exception:
        return None
    if val is False or val is None:
        return None
    if field.type == 'many2one':
        return val.display_name
    if field.type == 'selection':
        return dict(field.selection).get(val, val)
    if field.type in ('monetary', 'float'):
        return '%s' % val
    if field.type == 'date':
        return val.isoformat() if hasattr(val, 'isoformat') else str(val)
    if field.type == 'datetime':
        return val.isoformat(sep=' ', timespec='seconds') if hasattr(val, 'isoformat') else str(val)
    return str(val)


def _minimal_label(action):
    if not action:
        return ''
    model = action.get('res_model') or ''
    if not model:
        return ''
    name = action.get('name') or model
    res_id = _safe_int(action.get('res_id'))
    view_type = action.get('view_type') or ''
    if res_id:
        return '%s #%s' % (name, res_id)
    active_ids = action.get('active_ids') or []
    if len(active_ids) > 1:
        return '%s (%s selected)' % (name, len(active_ids))
    if view_type:
        return '%s · %s' % (name, view_type)
    return name


def _format_minimal_block(raw, action):
    lines = ['[Active screen]']
    if action.get('name'):
        lines.append('Menu/action: %s' % action['name'])
    if action.get('res_model'):
        lines.append('Model: %s' % action['res_model'])
    if action.get('view_type'):
        lines.append('View: %s' % action['view_type'])
    res_id = _safe_int(action.get('res_id'))
    if res_id:
        lines.append('Record id: %s' % res_id)
    active_ids = action.get('active_ids') or []
    if active_ids:
        lines.append('Selected ids: %s' % active_ids[:20])
    url_hash = raw.get('url_hash')
    if url_hash:
        lines.append('URL hash: %s' % url_hash)
    return '\n'.join(lines)


def enrich_screen_context(env, raw):
    """Return {'block': str, 'label': str} for runtime injection and UI chip."""
    if not raw:
        return {'block': '', 'label': ''}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {'block': '', 'label': ''}
    if not isinstance(raw, dict):
        return {'block': '', 'label': ''}

    action = raw.get('action') or {}
    label = _minimal_label(action)
    model_name = action.get('res_model')
    if not model_name or model_name not in env:
        block = _format_minimal_block(raw, action)
        return {'block': block, 'label': label}

    res_id = _safe_int(action.get('res_id'))
    active_ids = [
        i for i in (_safe_int(x) for x in (action.get('active_ids') or []))
        if i
    ]
    lines = ['[Active screen]']
    if action.get('name'):
        lines.append('Action: %s' % action['name'])
    lines.append('View: %s · Model: %s' % (
        action.get('view_type') or '?',
        model_name,
    ))
    _append_resolved_view_id(env, action, lines)

    Model = env[model_name]
    record = Model.browse(res_id).exists() if res_id else Model.browse()
    if res_id and not record:
        lines.append('Record: #%s (not accessible or missing)' % res_id)
    elif record:
        display = record.display_name
        lines.append('Record: #%s "%s"' % (record.id, display))
        summary_parts = []
        for fname in _CANDIDATE_SUMMARY_FIELDS:
            if fname == 'name' and display:
                continue
            formatted = _format_field_value(record, fname)
            if formatted is not None:
                summary_parts.append('%s=%s' % (fname, formatted))
        if summary_parts:
            lines.append('Summary: ' + ' · '.join(summary_parts[:8]))
    elif active_ids:
        existing = Model.browse(active_ids).exists()
        lines.append('Selection: %s record(s), ids=%s' % (
            len(existing), existing.ids[:20],
        ))
    else:
        lines.append('No single record focused (list/kanban or dashboard).')
        _append_list_view_stats(env, Model, action, lines)

    lines.append(
        'Note: assume implicit references target this screen unless the user '
        'clearly asks about something else (see ui_focus context).'
    )
    return {'block': '\n'.join(lines), 'label': label}


def _append_resolved_view_id(env, action, lines):
    action_id = action.get('action_id')
    if not action_id:
        return
    try:
        from odoo.addons.pns_ai_mcp.utils.field_required_plan import (
            resolve_act_window_view,
        )
        view = resolve_act_window_view(
            env, action_id, action.get('view_type') or 'form',
        )
        xmlid = ''
        try:
            xmlid = (view.get_external_id() or {}).get(view.id) or ''
        except Exception:
            xmlid = ''
        extra = (' %s' % xmlid) if xmlid else ''
        lines.append('View id: %s%s' % (view.id, extra))
    except Exception:
        _logger.debug('screen_context view id resolve failed', exc_info=True)


def _parse_domain(raw_domain):
    if not raw_domain:
        return []
    if isinstance(raw_domain, list):
        return raw_domain
    if isinstance(raw_domain, str):
        try:
            return json.loads(raw_domain.replace("'", '"'))
        except Exception:
            return []
    return []


def _append_list_view_stats(env, Model, action, lines):
    """Add search_count for list/kanban views (answers «¿cuántos registros?»)."""
    view_type = (action.get('view_type') or '').lower()
    if view_type not in ('list', 'tree', 'kanban'):
        return
    if _safe_int(action.get('res_id')):
        return
    domain = _parse_domain(action.get('domain'))
    try:
        count = Model.search_count(domain)
        if domain:
            lines.append(
                'List scope: %s record(s) matching the current action domain '
                '(use this model for «how many records» on this screen).' % count
            )
        else:
            lines.append(
                'List scope: %s accessible record(s) in %s '
                '(use this model for «how many records» on this screen).' % (
                    count, Model._name,
                )
            )
    except Exception as exc:
        _logger.debug('screen_context search_count failed: %s', exc)
