# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Helpers for Safe Plan op=field_required — list primary views, resolve action.

No business literals. Callers pass model/field/action ids.
"""
import json
import logging
from datetime import timedelta

from odoo import _, api, fields, SUPERUSER_ID
from odoo.exceptions import UserError

from .view_policy_arch import arch_contains_field, check_ident

_logger = logging.getLogger(__name__)

_FIELD_REQUIRED_HINT = (
    "Use op=field_required with {model, field, required} "
    "(optional view_id or action_id; view_only=true to skip the ORM)."
)

_REQUIRED_ATOMS = frozenset({
    'view.set_field_required',
    'field.set_required',
})


def is_required_atom(action_code):
    return (action_code or '') in _REQUIRED_ATOMS


def field_required_hint():
    return _FIELD_REQUIRED_HINT


def _as_int_list(value):
    if value in (None, False, '', []):
        return []
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [int(value)]
    if isinstance(value, str) and value.strip().isdigit():
        return [int(value.strip())]
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            if item in (None, False, ''):
                continue
            out.append(int(item))
        return out
    raise UserError(_('view_ids must be a list of view ids (or empty).'))


def primary_of(view):
    """Walk inherit_id until the root view."""
    seen = set()
    while view and view.inherit_id and view.id not in seen:
        seen.add(view.id)
        view = view.inherit_id
    return view


def combined_arch(view):
    """Arch of a view after inherits (best-effort, both Odoo families)."""
    try:
        read_combined = getattr(view, 'read_combined', None)
        if callable(read_combined):
            data = read_combined()
            if isinstance(data, dict) and data.get('arch'):
                return data['arch']
    except Exception:
        _logger.debug('read_combined failed for view %s', view.id, exc_info=True)
    try:
        if view.model and view.model in view.env:
            fv = view.env[view.model].fields_view_get(
                view_id=view.id, view_type=view.type or 'form',
            )
            if fv.get('arch'):
                return fv['arch']
    except Exception:
        _logger.debug('fields_view_get failed for view %s', view.id, exc_info=True)
    return view.arch or ''


def resolve_act_window_view(env, action_id, view_type=None):
    """Primary ir.ui.view for an act_window + type (form/tree)."""
    action = env['ir.actions.act_window'].sudo().browse(int(action_id))
    if not action.exists():
        raise UserError(_('Unknown action id: %s') % action_id)
    vt = (view_type or 'form') or 'form'
    vt = str(vt).split(',')[0].strip().lower()
    if vt == 'list':
        vt = 'tree'
    if action.view_id and action.view_id.type in (vt, 'list' if vt == 'tree' else vt):
        return primary_of(action.view_id)
    lines = action.view_ids.filtered(
        lambda r: (r.view_mode or '') in (vt, 'list' if vt == 'tree' else vt)
    )
    if lines and lines[0].view_id:
        return primary_of(lines[0].view_id)
    View = env['ir.ui.view'].sudo()
    default_view = getattr(View, 'default_view', None)
    did = default_view(action.res_model, vt) if callable(default_view) else False
    if did:
        return primary_of(View.browse(did))
    hit = View.search([
        ('model', '=', action.res_model),
        ('type', '=', vt),
        ('inherit_id', '=', False),
    ], limit=1, order='priority, id')
    if hit:
        return primary_of(hit)
    raise UserError(
        _('No %s view for action %s') % (vt, action_id)
    )


def list_primary_views_showing_field(env, model, field):
    """Primary form/tree views whose combined arch displays ``field``."""
    check_ident(model, 'model')
    check_ident(field, 'field')
    View = env['ir.ui.view'].sudo()
    primaries = View.search([
        ('model', '=', model),
        ('type', 'in', ('form', 'tree')),
        ('inherit_id', '=', False),
    ], order='type, priority, id')
    hits = []
    for view in primaries:
        try:
            arch = combined_arch(view)
        except Exception:
            continue
        if arch_contains_field(arch, field):
            hits.append(view)
    return hits


def _xmlid_of(view):
    try:
        data = view.get_external_id()
        return data.get(view.id) or ''
    except Exception:
        return ''


def view_choice_item(view, selected=False):
    return {
        'id': view.id,
        'label': view.name or view.display_name or str(view.id),
        'type': view.type or '',
        'xmlid': _xmlid_of(view),
        'selected': bool(selected),
    }


def step_requested_view_ids(env, step):
    """Ids named on the step (preselection only; not a skip of the list)."""
    ids = _as_int_list(step.get('view_ids'))
    if step.get('view_id') not in (None, False, ''):
        ids.extend(_as_int_list(step.get('view_id')))
    action_id = step.get('action_id')
    if action_id not in (None, False, ''):
        view = resolve_act_window_view(
            env, action_id, step.get('view_type') or 'form',
        )
        ids.append(view.id)
    # unique, keep order
    seen = set()
    out = []
    for vid in ids:
        if vid in seen:
            continue
        seen.add(vid)
        out.append(vid)
    return out


def chatboo_preselected_view_id(env, model):
    """Primary view under Chatboo, if the session stored a screen."""
    try:
        from .session_download import resolve_chatboo_session_id
    except Exception:
        return None
    sid = resolve_chatboo_session_id(env)
    if not sid:
        return None
    if 'chatboo.session' not in env:
        return None
    session = env['chatboo.session'].sudo().browse(int(sid))
    raw = session.last_screen_context if session.exists() else False
    if not raw:
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None
    action = (data or {}).get('action') or {}
    res_model = action.get('res_model')
    if res_model and res_model != model:
        return None
    action_id = action.get('action_id')
    if not action_id:
        return None
    try:
        view = resolve_act_window_view(
            env, action_id, action.get('view_type') or 'form',
        )
        return view.id
    except Exception:
        return None


def build_choice_items(env, step):
    model = step.get('model')
    field = step.get('field')
    views = list_primary_views_showing_field(env, model, field)
    wanted = set(step_requested_view_ids(env, step))
    if not wanted:
        screen = chatboo_preselected_view_id(env, model)
        if screen:
            wanted.add(screen)
    return [view_choice_item(v, selected=(v.id in wanted)) for v in views]


def create_field_required_choice(env, steps, title):
    """Persist a view-pick draft. Does not create the Confirm aviso."""
    fr_steps = [s for s in steps if isinstance(s, dict) and s.get('op') == 'field_required']
    if len(fr_steps) != 1:
        return {
            'success': False,
            'error': (
                'op=field_required must be the only field_required step '
                'in the plan (one model/field gesture).'
            ),
        }
    step = fr_steps[0]
    try:
        items = build_choice_items(env, step)
    except UserError as exc:
        return {'success': False, 'error': exc.args[0] if exc.args else str(exc)}
    except ValueError as exc:
        return {'success': False, 'error': str(exc)}
    title_s = title or _('Field required')
    payload = json.dumps({
        'steps': steps,
        'title': title,
        'items': items,
        'model': step.get('model'),
        'field': step.get('field'),
    }, ensure_ascii=False)
    expires = fields.Datetime.now() + timedelta(minutes=30)
    nctx = dict(env.context or {})
    choice_id = None
    # Own cursor: SSE keeps the request TX open; Accept is another HTTP call.
    with env.registry.cursor() as ncr:
        nenv = api.Environment(ncr, SUPERUSER_ID, nctx)
        rec = nenv['ai.safe.choice'].create({
            'user_id': env.uid,
            'title': title_s,
            'status': 'pending',
            'expires_at': expires,
            'payload': payload,
        })
        choice_id = rec.choice_id
        ncr.commit()
    return {
        'success': True,
        'status': 'pending_choice',
        'choice_id': choice_id,
        'title': title_s,
        'items': items,
        'message': (
            '[PENDING] Pick the views in Chatboo. The ERP has NOT changed. '
            'Do not call write on ir.ui.view. Do not use op=action.'
        ),
    }


def accept_choice(env, choice_id, selected_ids, create_pending):
    """Lock selected view ids onto the draft steps and open the Confirm aviso."""
    Choice = env['ai.safe.choice'].sudo()
    rec = Choice.search([('choice_id', '=', choice_id)], limit=1)
    if not rec:
        return {'success': False, 'error': 'not_found'}
    if rec.user_id.id != env.uid and not env.user.has_group('pns_ai_mcp.group_ai_admin'):
        return {'success': False, 'error': 'forbidden'}
    if rec.status != 'pending':
        return {'success': False, 'error': 'not_pending'}
    if rec.expires_at and rec.expires_at < fields.Datetime.now():
        rec.status = 'expired'
        return {'success': False, 'error': 'expired'}
    payload = json.loads(rec.payload or '{}')
    allowed = {int(it['id']) for it in (payload.get('items') or [])}
    picked = []
    for raw in selected_ids or []:
        vid = int(raw)
        if vid not in allowed:
            return {
                'success': False,
                'error': 'View %s is not in the candidate list.' % vid,
            }
        if vid not in picked:
            picked.append(vid)
    steps = payload.get('steps') or []
    for step in steps:
        if not isinstance(step, dict) or step.get('op') != 'field_required':
            continue
        if step.get('view_only') and not picked:
            return {
                'success': False,
                'error': 'view_only requires at least one selected view.',
            }
        step['view_ids'] = picked
        step['_views_picked'] = True
    rec.write({
        'status': 'accepted',
        'payload': json.dumps(payload, ensure_ascii=False),
    })
    pending = create_pending(
        env, steps, title=payload.get('title') or rec.title,
        views_locked=True,
    )
    if pending.get('success') and pending.get('verification_id'):
        pending.setdefault('status', 'pending_confirmation')
    return pending


def cancel_choice(env, choice_id):
    Choice = env['ai.safe.choice'].sudo()
    rec = Choice.search([('choice_id', '=', choice_id)], limit=1)
    if not rec:
        return {'success': False, 'error': 'not_found'}
    if rec.user_id.id != env.uid and not env.user.has_group('pns_ai_mcp.group_ai_admin'):
        return {'success': False, 'error': 'forbidden'}
    if rec.status == 'cancelled':
        return {'success': True, 'status': 'cancelled', 'idempotent': True}
    if rec.status != 'pending':
        return {'success': False, 'error': 'not_pending'}
    rec.status = 'cancelled'
    return {'success': True, 'status': 'cancelled'}
