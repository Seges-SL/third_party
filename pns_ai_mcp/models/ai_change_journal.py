# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Permanent journal of ERP mutations applied via Safe Plan (not ``ai.log``)."""
from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError

from ..utils.change_journal import (
    SCHEMA_VERSION,
    build_payload,
    classify_change_kind,
    dumps_payload,
    initial_reversible,
    loads_payload,
    one_line_summary,
    redact_record,
    write_vals_from_before,
)
import logging

_logger = logging.getLogger(__name__)

_SKIP_FIELD_TYPES = frozenset({'binary', 'image'})
_JOURNAL_CTX = {
    'safe_operation_id': 'ai_journal_safe_operation_id',
    'correlation_id': 'ai_journal_correlation_id',
    'user_id': 'ai_journal_user_id',
    'confirmed_by_uid': 'ai_journal_confirmed_by_uid',
    'origin': 'ai_journal_origin',
    'note': 'ai_journal_note',
}


def _ensure_journal_manager(user):
    if user._is_superuser():
        return
    if user.has_group('pns_ai_mcp.group_ai_admin') or user.has_group('base.group_system'):
        return
    raise AccessError(_(
        'Only system administrators and AI administrators can revert journalled changes.'
    ))


class AiChangeJournal(models.Model):
    """One row per applied Safe Plan step (sequence: correlation + step_seq)."""
    _name = 'ai.change.journal'
    _description = 'AI Change'
    _order = 'create_date desc, step_seq desc, id desc'
    _rec_name = 'summary'

    user_id = fields.Many2one(
        'res.users', string='Requested by', readonly=True, index=True,
        ondelete='restrict',
        help='User who proposed the change via AI / Safe Plan.',
    )
    confirmed_by_uid = fields.Many2one(
        'res.users', string='Confirmed by', readonly=True, index=True,
        ondelete='restrict',
        help='User who confirmed the toast (or who clicked Revert).',
    )
    origin = fields.Selection(
        [
            ('chatboo', 'Chatboo'),
            ('mcp_client', 'MCP Client'),
            ('internal', 'Internal'),
            ('revert', 'Revert'),
        ],
        string='Origin', readonly=True, index=True,
    )
    safe_operation_id = fields.Many2one(
        'ai.safe.operation', string='Authorization', readonly=True, index=True,
        ondelete='set null',
    )
    verification_id = fields.Char(
        related='safe_operation_id.verification_id', string='Verification ID',
        readonly=True, store=True, index=True,
    )
    correlation_id = fields.Char(string='Request ID', readonly=True, index=True)
    step_seq = fields.Integer(string='Step', readonly=True, default=1)

    op = fields.Selection(
        [
            ('create', 'Create'),
            ('write', 'Update'),
            ('copy', 'Copy'),
            ('unlink', 'Delete'),
            ('action', 'Action'),
            ('field_required', 'Field required'),
        ],
        string='Operation', readonly=True, required=True, index=True,
    )
    change_kind = fields.Selection(
        [
            ('view_modifier', 'View'),
            ('field_meta', 'Field metadata'),
            ('acl', 'Access'),
            ('module', 'Module'),
            ('report', 'Report'),
            ('trusted_action', 'Trusted action'),
            ('generic', 'Generic'),
        ],
        string='Kind', readonly=True, index=True, default='generic',
    )
    action_code = fields.Char(string='Action code', readonly=True)

    model_name = fields.Char(string='Model', readonly=True, index=True)
    record_ids_display = fields.Char(string='Record IDs', readonly=True, index=True)
    record_name = fields.Char(string='Record', readonly=True)
    field_name = fields.Char(string='Field', readonly=True, index=True)
    view_id = fields.Many2one('ir.ui.view', string='View', readonly=True, ondelete='set null')
    module_name = fields.Char(string='Module', readonly=True, index=True)

    before_json = fields.Text(string='Before (JSON)', readonly=True)
    after_json = fields.Text(string='After (JSON)', readonly=True)
    schema_version = fields.Integer(string='JSON schema', readonly=True, default=SCHEMA_VERSION)

    state = fields.Selection(
        [
            ('applied', 'Applied'),
            ('reverted', 'Reverted'),
            ('failed', 'Failed'),
        ],
        string='Status', readonly=True, required=True, default='applied', index=True,
    )
    reversible = fields.Boolean(string='Reversible', readonly=True, default=False)
    reversible_reason = fields.Char(string='Reversible reason', readonly=True)
    can_revert = fields.Boolean(
        string='Can revert', compute='_compute_can_revert',
        help='Applied, reversible, not itself a revert, and live data still matches.',
    )
    reverts_id = fields.Many2one(
        'ai.change.journal', string='Reverts', readonly=True, index=True,
        ondelete='restrict',
        help='If set, this row is the undo of that journal entry.',
    )
    note = fields.Text(string='Notes', readonly=True)
    summary = fields.Char(string='Summary', readonly=True)

    @api.depends(
        'state', 'reversible', 'reverts_id', 'op', 'after_json', 'before_json',
        'model_name',
    )
    def _compute_can_revert(self):
        for rec in self:
            rec.can_revert = rec._check_can_revert()

    def _check_can_revert(self):
        self.ensure_one()
        if self.state != 'applied' or not self.reversible or self.reverts_id:
            return False
        return self._live_data_matches_after()

    def _live_data_matches_after(self):
        """False when someone changed the same records after this step."""
        self.ensure_one()
        after = loads_payload(self.after_json)
        model = self.model_name
        if self.op in ('create', 'copy'):
            ids = after.get('ids') or []
            if not ids or model not in self.env:
                return False
            recs = self.env[model].browse(ids).exists()
            return len(recs) == len(ids)
        if self.op == 'write':
            if model not in self.env:
                return False
            fields_list = after.get('fields') or []
            for row in after.get('records') or []:
                rec_id = row.get('id')
                if rec_id is None:
                    return False
                rec = self.env[model].browse(int(rec_id))
                if not rec.exists():
                    return False
                names = [f for f in fields_list if f in rec._fields and f != 'id']
                if not names:
                    continue
                current = redact_record(rec.read(names)[0])
                for name in names:
                    if name == 'id':
                        continue
                    if current.get(name) != row.get(name):
                        return False
            return True
        return False

    @api.model
    def snapshot_records(self, recs, field_names=None):
        """Normalized, redacted ``read()`` rows. ``field_names=None`` → safe stored."""
        if not recs:
            return []
        names = list(field_names or self._safe_field_names(recs))
        extra = [n for n in ('display_name',) if n in recs._fields and n not in names]
        try:
            rows = recs.read(names + extra)
        except Exception:
            _logger.exception('AI change journal: snapshot read failed on %s', recs._name)
            return [{'id': i} for i in recs.ids]
        return [redact_record(row) for row in rows]

    @api.model
    def _safe_field_names(self, recs):
        names = []
        for name, field in recs._fields.items():
            if getattr(field, 'compute', None) and not getattr(field, 'store', False):
                continue
            ftype = getattr(field, 'type', None)
            if ftype in _SKIP_FIELD_TYPES:
                continue
            if name in ('password',):
                continue
            names.append(name)
        return names

    @api.model
    def record_executed_step(self, env, step, op, result, before_records, step_seq):
        """Write one journal row for a mutating Safe Plan step. Same transaction."""
        ctx = env.context or {}
        model = (step or {}).get('model') or (result or {}).get('model') or ''
        action_code = (step or {}).get('action_code') or (result or {}).get('action_code')
        enrich = {}
        if op == 'action' and isinstance(result, dict):
            raw = result.get('result')
            if isinstance(raw, dict) and isinstance(raw.get('change_journal'), dict):
                enrich = raw['change_journal']
                if not model:
                    model = enrich.get('model') or raw.get('model') or ''

        fields_list = []
        ids = []
        after_records = []
        if op == 'create':
            rid = (result or {}).get('id')
            ids = [rid] if rid else []
            fields_list = list(((step or {}).get('values') or {}).keys())
            if rid and model in env:
                after_records = self.snapshot_records(
                    env[model].browse(rid), field_names=fields_list or None,
                )
        elif op == 'write':
            ids = list((result or {}).get('ids') or [])
            fields_list = list(((step or {}).get('values') or {}).keys())
            if ids and model in env:
                after_records = self.snapshot_records(
                    env[model].browse(ids), field_names=fields_list or None,
                )
        elif op == 'copy':
            rid = (result or {}).get('new_id')
            ids = [rid] if rid else []
            if rid and model in env:
                after_records = self.snapshot_records(env[model].browse(rid))
        elif op == 'unlink':
            ids = list((result or {}).get('ids') or [])
        elif op == 'action':
            ids = list(enrich.get('ids') or [])
            after_records = list(enrich.get('records') or [])
            fields_list = list(enrich.get('fields') or [])
            if enrich.get('after'):
                after_records = list((enrich['after'].get('records') if isinstance(enrich['after'], dict) else []) or after_records)
        elif op == 'field_required':
            view_res = (result or {}).get('views') or {}
            ids = list(view_res.get('ids') or [])
            field_name = (step or {}).get('field') or (result or {}).get('field')
            fields_list = [field_name] if field_name else []

        before_payload = build_payload(
            op, model, ids, fields_list, before_records or [],
            meta={'change_kind': enrich.get('change_kind') or classify_change_kind(model, op, action_code)},
        )
        after_meta = dict(before_payload['meta'])
        if action_code:
            after_meta['action_code'] = action_code
        if enrich:
            after_meta.update({
                k: enrich[k] for k in ('change_kind', 'reversible', 'reversible_reason')
                if k in enrich
            })
        after_payload = build_payload(
            op, model, ids, fields_list, after_records, meta=after_meta,
        )
        if enrich.get('before') and isinstance(enrich['before'], dict):
            before_payload = enrich['before']
        if enrich.get('after') and isinstance(enrich['after'], dict):
            after_payload = enrich['after']

        kind = after_payload.get('meta', {}).get('change_kind') or classify_change_kind(
            model, op, action_code,
        )
        reversible, reason = initial_reversible(op, before_payload, after_payload)
        if enrich.get('reversible') is False:
            reversible, reason = False, enrich.get('reversible_reason') or reason

        rec_name = ''
        if after_records:
            rec_name = after_records[0].get('display_name') or after_records[0].get('name') or ''
        elif before_records:
            rec_name = (before_records[0] or {}).get('display_name') or (before_records[0] or {}).get('name') or ''

        view_id = False
        module_name = ''
        field_name = (fields_list[0] if len(fields_list) == 1 else '') or ''
        if model == 'ir.ui.view' and ids:
            view_id = ids[0]
        if op == 'field_required' and ids:
            view_id = ids[0]
        if model == 'ir.module.module' and after_records:
            module_name = after_records[0].get('name') or ''

        origin = ctx.get(_JOURNAL_CTX['origin']) or 'internal'
        if origin not in ('chatboo', 'mcp_client', 'internal', 'revert'):
            origin = 'internal'
        user_id = ctx.get(_JOURNAL_CTX['user_id']) or env.uid
        confirmed = ctx.get(_JOURNAL_CTX['confirmed_by_uid']) or env.uid
        safe_op = ctx.get(_JOURNAL_CTX['safe_operation_id']) or False

        return self.create({
            'user_id': user_id,
            'confirmed_by_uid': confirmed,
            'origin': origin,
            'safe_operation_id': safe_op or False,
            'correlation_id': ctx.get(_JOURNAL_CTX['correlation_id']) or False,
            'step_seq': int(step_seq or 1),
            'op': op,
            'change_kind': kind,
            'action_code': action_code or False,
            'model_name': model or False,
            'record_ids_display': ','.join(str(i) for i in ids if i is not None),
            'record_name': rec_name or False,
            'field_name': field_name or False,
            'view_id': view_id or False,
            'module_name': module_name or False,
            'before_json': dumps_payload(before_payload),
            'after_json': dumps_payload(after_payload),
            'schema_version': SCHEMA_VERSION,
            'state': 'applied',
            'reversible': reversible,
            'reversible_reason': reason,
            'note': (ctx.get(_JOURNAL_CTX['note']) or '') or False,
            'summary': one_line_summary(op, model, ids, kind),
        })

    @api.model
    def record_failed_plan(self, steps, error, env=None):
        """Persist failed attempt on a dedicated cursor (survives plan rollback)."""
        from odoo import SUPERUSER_ID, api as odoo_api

        src = env or self.env
        ctx = src.context or {}
        mutating = []
        for i, step in enumerate(steps or [], start=1):
            op = (step or {}).get('op')
            if op not in ('create', 'write', 'copy', 'unlink', 'action', 'field_required'):
                continue
            mutating.append((i, step, op))
        if not mutating:
            return self.browse()

        created_ids = []
        registry = src.registry
        with registry.cursor() as cr:
            jenv = odoo_api.Environment(cr, SUPERUSER_ID, ctx)
            Journal = jenv['ai.change.journal'].sudo()
            err = (error or '')[:2000]
            for step_seq, step, op in mutating:
                model = step.get('model') or ''
                action_code = step.get('action_code')
                ids = list(step.get('ids') or [])
                if not ids and step.get('id') is not None:
                    ids = [step.get('id')]
                fields_list = list((step.get('values') or {}).keys())
                kind = classify_change_kind(model, op, action_code)
                after = build_payload(
                    op, model, ids, fields_list, [],
                    meta={
                        'change_kind': kind,
                        'error': err,
                        'intended_values': step.get('values') or {},
                    },
                )
                rec = Journal.create({
                    'user_id': ctx.get(_JOURNAL_CTX['user_id']) or src.uid,
                    'confirmed_by_uid': ctx.get(_JOURNAL_CTX['confirmed_by_uid']) or src.uid,
                    'origin': (
                        ctx.get(_JOURNAL_CTX['origin'])
                        if ctx.get(_JOURNAL_CTX['origin']) in (
                            'chatboo', 'mcp_client', 'internal', 'revert',
                        ) else 'internal'
                    ),
                    'safe_operation_id': ctx.get(_JOURNAL_CTX['safe_operation_id']) or False,
                    'correlation_id': ctx.get(_JOURNAL_CTX['correlation_id']) or False,
                    'step_seq': step_seq,
                    'op': op,
                    'change_kind': kind,
                    'action_code': action_code or False,
                    'model_name': model or False,
                    'record_ids_display': ','.join(str(i) for i in ids if i is not None),
                    'field_name': (fields_list[0] if len(fields_list) == 1 else '') or False,
                    'before_json': dumps_payload(build_payload(op, model, ids, fields_list, [])),
                    'after_json': dumps_payload(after),
                    'schema_version': SCHEMA_VERSION,
                    'state': 'failed',
                    'reversible': False,
                    'reversible_reason': _('Plan failed; nothing was applied'),
                    'note': err or (ctx.get(_JOURNAL_CTX['note']) or False),
                    'summary': _('FAILED: %s') % one_line_summary(op, model, ids, kind),
                })
                created_ids.append(rec.id)
            cr.commit()
        return self.browse(created_ids)

    def action_revert(self):
        """Human Revert: Odoo confirm dialog (not Safe Plan). Closed afterwards."""
        self.ensure_one()
        _ensure_journal_manager(self.env.user)
        if self.reverts_id:
            raise UserError(_('A revert row cannot be reverted again.'))
        if self.state != 'applied':
            raise UserError(_('Only applied changes can be reverted.'))
        if not self._check_can_revert():
            raise UserError(
                self.reversible_reason
                or _('This change can no longer be reverted (data has moved on).')
            )
        after = loads_payload(self.after_json)
        before = loads_payload(self.before_json)
        model = self.model_name
        if self.op in ('create', 'copy'):
            ids = after.get('ids') or []
            if not ids or model not in self.env:
                raise UserError(_('Cannot revert: created record is missing.'))
            recs = self.env[model].browse(ids).exists()
            recs.unlink()
            after_undo = build_payload(self.op, model, ids, [], [], meta={'reverted': True})
        elif self.op == 'write':
            mapping = write_vals_from_before(before)
            if not mapping or model not in self.env:
                raise UserError(_('Cannot revert: no before snapshot.'))
            for rec_id, vals in mapping.items():
                rec = self.env[model].browse(rec_id)
                if not rec.exists():
                    raise UserError(_('Cannot revert: record %s no longer exists.') % rec_id)
                if vals:
                    rec.write(vals)
            ids = list(mapping.keys())
            after_undo = build_payload(
                self.op, model, ids, list(before.get('fields') or []),
                self.snapshot_records(self.env[model].browse(ids), before.get('fields')),
                meta={'reverted': True},
            )
        else:
            raise UserError(_('This operation type cannot be reverted from the journal.'))

        self.write({
            'state': 'reverted',
            'reversible': False,
            'reversible_reason': _('Already reverted'),
        })
        undo = self.sudo().create({
            'user_id': self.env.uid,
            'confirmed_by_uid': self.env.uid,
            'origin': 'revert',
            'safe_operation_id': False,
            'correlation_id': self.correlation_id or False,
            'step_seq': (self.step_seq or 0) + 1,
            'op': self.op,
            'change_kind': self.change_kind,
            'action_code': self.action_code,
            'model_name': model,
            'record_ids_display': self.record_ids_display,
            'record_name': self.record_name,
            'field_name': self.field_name,
            'view_id': self.view_id.id if self.view_id else False,
            'module_name': self.module_name,
            'before_json': self.after_json,
            'after_json': dumps_payload(after_undo),
            'schema_version': SCHEMA_VERSION,
            'state': 'applied',
            'reversible': False,
            'reversible_reason': _('Fruit of a human revert; cannot be re-reverted'),
            'reverts_id': self.id,
            'note': _('Revert of journal row %s') % self.id,
            'summary': _('Revert: %s') % (self.summary or self.id),
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Change reverted'),
                'message': _('Journal row %s recorded the undo.') % undo.id,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def unlink(self):
        if self.env.user._is_superuser():
            return super(AiChangeJournal, self).unlink()
        raise UserError(_('AI change journal rows cannot be deleted.'))
