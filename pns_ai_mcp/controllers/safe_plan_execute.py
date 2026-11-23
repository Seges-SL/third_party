# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Running a confirmed plan: records, change journal and pending notes."""

import logging
from odoo import _
from odoo.exceptions import UserError
from odoo.addons.pns_base.utils.compat import normalize_model_write_values
from .controller_helpers import check_safe_plan_permissions

from .safe_plan_validate import (
    ALLOWED_OPS,
    _canonical_op,
    _meta_crud_block_error,
    _resolve_refs,
)

from .safe_plan_describe import (
    _ack_tr,
)

from .safe_plan_http import (
    _execute_api_call,
    _execute_fetch_url,
)

_logger = logging.getLogger(__name__)


def _select_records(Model, step, ref_map):
    """Pick the target recordset of a write/unlink by ids or by domain."""
    if step.get('ids') is not None:
        ids = _resolve_refs(step['ids'], ref_map)
        if isinstance(ids, int):
            ids = [ids]
        return Model.browse([int(x) for x in ids])
    domain = step.get('domain') or []
    return Model.search(domain)


def _ensure_fetch_url_whitelist(env, step):
    """Add or reactivate whitelist row before fetch_url executes."""
    from urllib.parse import urlparse
    Whitelist = env['ai.url.whitelist']
    hostname = (urlparse(step.get('url', '')).hostname or '').lower()
    if not hostname:
        return
    if Whitelist.is_url_access_open():
        # Open policy lets the fetch run. It does not grow the list.
        return
    entry = Whitelist._match_whitelist_entry(hostname)
    if entry and not entry.active:
        Whitelist._ensure_domain_whitelisted(
            hostname,
            notes='Reactivated on fetch_url confirm',
        )


def execute_safe_plan(env, steps):
    """Run the plan (Safe Plan / Box B) with fixed verbs. Atomic: the confirmation
    endpoint calls it inside its transaction; if something fails, the caller
    rolls back.

    It runs with the `env` of the session's HUMAN user: their permissions and Odoo
    record rules still apply as the last security layer.
    """
    has_permission, perm_error = check_safe_plan_permissions(steps, user=env.user)
    if not has_permission:
        raise PermissionError(perm_error or 'Insufficient permissions to execute safe plan.')
    from ..utils.module_update_heal import module_update_alone_error
    alone_err = module_update_alone_error(steps)
    if alone_err:
        raise PermissionError(alone_err)

    ok, policy_error = env['ai.url.whitelist'].check_fetch_url_steps(steps, user=env.user)
    if not ok:
        raise PermissionError(policy_error)

    from ..utils.session_download import resolve_session_ref
    _sid = resolve_session_ref(env)
    _ctx = dict(env.context or {})
    if _sid:
        _ctx['ai_session_ref'] = int(_sid)
    labels = _ctx.get('file_label_by_id')
    if not isinstance(labels, dict):
        labels = {}
        _ctx['file_label_by_id'] = labels
    env = env(context=_ctx)

    ref_map = {}
    results = []
    journal_seq = 0
    for step in steps:
        op = _canonical_op(step['op'])
        if op not in ALLOWED_OPS:
            raise PermissionError("invalid 'op' (%r)" % (op,))
        if op == 'fetch_url':
            _ensure_fetch_url_whitelist(env, step)
            result = _execute_fetch_url(env, step)
            results.append(result)
            continue
        if op == 'api_call':
            result = _execute_api_call(env, step)
            try:
                from ..utils.session_download import file_labels_from_steps
                file_labels_from_steps([result], labels)
            except Exception:
                pass
            results.append(result)
            continue
        if op == 'field_required':
            Action = env['ai.system.action']
            model = step.get('model')
            field = step.get('field')
            required = step.get('required', True)
            view_only = step.get('view_only')
            view_ids = list(step.get('view_ids') or [])
            if step.get('view_id') not in (None, False, ''):
                view_ids.append(int(step['view_id']))
            if view_only and not view_ids:
                raise UserError(_('view_only requires at least one selected view.'))
            row = {'op': 'field_required', 'model': model, 'field': field}
            if not view_only:
                row['orm'] = Action._apply_field_set_required(
                    model=model, field=field, required=required,
                )
            if view_ids:
                row['views'] = Action._apply_view_set_field_required(
                    model=model, field=field, required=required,
                    view_ids=view_ids, uniform=True,
                )
            results.append(row)
            journal_seq += 1
            _record_change_journal(env, step, op, row, None, journal_seq)
            continue
        if op == 'action':
            action = env['ai.trusted.action']._get(step.get('action_code'))
            if not action:
                raise ValueError('Unknown trusted action %r' % step.get('action_code'))
            from ..utils.field_required_plan import is_required_atom
            if is_required_atom(action.code):
                from ..utils.field_required_plan import field_required_hint
                raise UserError(field_required_hint())
            args = _resolve_refs(step.get('args') or {}, ref_map)
            result = action._apply(**args)
            row = {'op': 'action', 'action_code': action.code, 'result': result}
            results.append(row)
            journal_seq += 1
            _record_change_journal(env, step, op, row, None, journal_seq)
            continue
        model = step['model']
        blocked = _meta_crud_block_error(model)
        if blocked:
            raise UserError(blocked)
        from ..utils.privilege_cusp import crud_cusp_error
        Model = env[model]
        if op == 'create':
            vals = normalize_model_write_values(
                model, _resolve_refs(step.get('values') or {}, ref_map), env)
            cusp = crud_cusp_error(env, model, op, {'values': vals})
            if cusp:
                raise PermissionError(cusp)
            rec = Model.create(vals)
            if step.get('ref'):
                ref_map[step['ref']] = rec.id
            row = {'op': 'create', 'model': model, 'id': rec.id, 'name': rec.display_name}
            pending = _form_pending(env, model, rec)
            if pending.get(rec.id):
                row['pending'] = [label for _name, label in pending[rec.id]]
            _post_pending_note(env, rec, pending)
            results.append(row)
            journal_seq += 1
            _record_change_journal(env, step, op, row, None, journal_seq)
        elif op == 'write':
            vals = normalize_model_write_values(
                model, _resolve_refs(step.get('values') or {}, ref_map), env)
            recs = _select_records(Model, step, ref_map)
            cusp = crud_cusp_error(env, model, op, {'values': vals}, records=recs.sudo())
            if cusp:
                raise PermissionError(cusp)
            before = _journal_snapshot(env, recs, list(vals.keys()))
            pending_before = _form_pending(env, model, recs)
            recs.write(vals)
            row = {'op': 'write', 'model': model, 'ids': recs.ids, 'count': len(recs)}
            _post_pending_note(
                env, recs, _form_pending(env, model, recs), pending_before,
            )
            results.append(row)
            journal_seq += 1
            _record_change_journal(env, step, op, row, before, journal_seq)
        elif op == 'copy':
            rid = int(_resolve_refs(step.get('id'), ref_map))
            overrides = _resolve_refs(step.get('overrides') or {}, ref_map)
            cusp = crud_cusp_error(
                env, model, op, {'overrides': overrides},
                records=Model.sudo().browse(rid),
            )
            if cusp:
                raise PermissionError(cusp)
            new = Model.browse(rid).copy(overrides)
            if step.get('ref'):
                ref_map[step['ref']] = new.id
            row = {'op': 'copy', 'model': model, 'source_id': rid,
                   'new_id': new.id, 'name': new.display_name}
            pending = _form_pending(env, model, new)
            if pending.get(new.id):
                row['pending'] = [label for _name, label in pending[new.id]]
            _post_pending_note(env, new, pending)
            results.append(row)
            journal_seq += 1
            _record_change_journal(env, step, op, row, None, journal_seq)
        elif op == 'unlink':
            recs = _select_records(Model, step, ref_map)
            cusp = crud_cusp_error(env, model, op, {}, records=recs.sudo())
            if cusp:
                raise PermissionError(cusp)
            ids = recs.ids
            before = _journal_snapshot(env, recs, None)
            quarantine = False
            if (
                'ai.change.journal' in env
                and env['ai.change.journal'].model_can_archive(model)
            ):
                recs.write({'active': False})
                quarantine = True
            else:
                recs.unlink()
            row = {
                'op': 'unlink',
                'model': model,
                'ids': ids,
                'count': len(ids),
                'quarantine': quarantine,
            }
            results.append(row)
            journal_seq += 1
            _record_change_journal(env, step, op, row, before, journal_seq)
    return results


def _journal_snapshot(env, recs, field_names):
    """Best-effort before snapshot; never blocks the plan if the model is missing."""
    if 'ai.change.journal' not in env or not recs:
        return None
    return env['ai.change.journal'].sudo().snapshot_records(recs, field_names=field_names)


def _record_change_journal(env, step, op, result, before_records, step_seq):
    """Permanent journal row in the same transaction as the mutation."""
    if 'ai.change.journal' not in env:
        return
    env['ai.change.journal'].sudo().record_executed_step(
        env, step, op, result, before_records, step_seq,
    )


def _form_pending(env, model, records):
    """What the form still asks for on those records, read after the write."""
    try:
        from ..utils.required_fields import form_pending_by_record

        return form_pending_by_record(env, model, records)
    except Exception:  # pragma: no cover - a card is never worth a rollback
        _logger.exception('Safe Plan: could not read pending fields on %s', model)
        return {}


def _post_pending_note(env, records, pending, before=None):
    """Leave on the record itself what the assistant could not fill in.

    A record born short says so. A write only says so when it changed the
    situation: touching a phone number on a record that was already missing
    its origin is not news. Nothing complete is ever posted about.
    """
    if not records or not hasattr(records, 'message_post'):
        return
    for record in records:
        empty = pending.get(record.id) or []
        if not empty:
            continue
        if before is not None and (before.get(record.id) or []) == empty:
            continue
        try:
            record.message_post(body=_ack_tr(env, _(
                'Written through the assistant. Still to fill in: %s'
            )) % ', '.join(label for _name, label in empty))
        except Exception:  # pragma: no cover - a note is never worth a rollback
            _logger.exception(
                'Safe Plan: could not note pending fields on %s#%s',
                record._name, record.id,
            )


_CRUD_OPS = frozenset({'create', 'write', 'copy', 'unlink', 'field_required'})


def _plan_has_crud(results=None, steps=None):
    """True when the plan/results include Odoo writes (not only fetch_url/mcp)."""
    for item in results or []:
        if isinstance(item, dict) and item.get('op') in _CRUD_OPS:
            return True
    for step in steps or []:
        if isinstance(step, dict) and step.get('op') in _CRUD_OPS:
            return True
    return False


def _needs_llm_followup(results=None, steps=None, action='confirm'):
    """LLM follow-up for fetch_url / api_call bodies; writes use local chat ack."""
    if action == 'cancel':
        return False
    for item in results or []:
        if isinstance(item, dict) and item.get('op') in ('fetch_url', 'api_call', 'mcp_call'):
            return True
    if not results:
        for step in steps or []:
            if isinstance(step, dict) and step.get('op') in ('fetch_url', 'api_call', 'mcp_call'):
                return True
    return False
