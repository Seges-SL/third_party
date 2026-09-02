# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Tell Chatboo to refresh the slash menu when the skill catalog changes."""
import json
import logging

from odoo import api, models, _

_logger = logging.getLogger(__name__)


class AISkill(models.Model):
    _inherit = 'ai.skill'

    def _chatboo_notify_skills_changed(self, confirm=False, session_id=None):
        """Ping the current user's Chatboo so `/` re-reads the catalog."""
        if self.env.context.get('skip_hardcoded_restrictions'):
            return
        if self.env.context.get('skip_chatboo_skills_bus'):
            return
        partner = self.env.user.partner_id
        if not partner or 'bus.bus' not in self.env:
            return
        payload = {
            'type': 'pns_chatboo_sync',
            'action': 'skills_changed',
        }
        if confirm:
            payload['confirm'] = True
        if session_id:
            try:
                payload['session_id'] = int(session_id)
            except (TypeError, ValueError):
                pass
        bus = self.env['bus.bus']
        try:
            bus._sendone(partner, 'pns_chatboo_sync', payload)
            return
        except (AttributeError, TypeError):
            pass
        try:
            channel = (self.env.cr.dbname, 'res.partner', partner.id)
            bus.sendone(channel, json.dumps(payload, ensure_ascii=False))
        except Exception:
            _logger.debug(
                'Chatboo: skills_changed bus notify failed', exc_info=True,
            )

    def _chatboo_confirm_session(self):
        raw = self.env.context.get('chatboo_session_id')
        if not raw:
            return self.env['chatboo.session']
        try:
            sid = int(raw)
        except (TypeError, ValueError):
            return self.env['chatboo.session']
        session = self.env['chatboo.session'].browse(sid)
        if not session.exists() or session.user_id.id != self.env.user.id:
            return self.env['chatboo.session']
        return session

    def _chatboo_append_catalog_note(self, op):
        """Persist a local Chatboo note. Slash comes from the record, never invented."""
        session = self._chatboo_confirm_session()
        if not session:
            return
        old = (self.env.context.get('chatboo_confirm_old') or '').strip()
        lines = []
        for rec in self:
            slash = ''
            if hasattr(rec, 'invoke_code'):
                slash = (rec.invoke_code() or '').strip()
            if not slash:
                slash = (rec.code or '').strip()
            if not slash:
                continue
            if op == 'created':
                lines.append(_('Skill /%s created.') % slash)
            elif op == 'deleted':
                lines.append(_('Skill /%s deleted.') % slash)
            elif op == 'renamed':
                if old:
                    lines.append(_('Skill renamed: /%s → /%s') % (old, slash))
                else:
                    lines.append(_('Skill /%s renamed.') % slash)
        if not lines:
            return
        session.append_local_ack('\n'.join(lines))

    def _chatboo_after_catalog_change(self, op=None):
        confirm = bool(op) and bool(self.env.context.get('chatboo_session_id'))
        if confirm and op:
            self._chatboo_append_catalog_note(op)
        self._chatboo_notify_skills_changed(
            confirm=confirm,
            session_id=self.env.context.get('chatboo_session_id'),
        )

    @api.model
    def action_delete_owned(self, token):
        return super(AISkill, self.with_context(
            chatboo_confirm_op='deleted',
        )).action_delete_owned(token)

    @api.model
    def action_rename_owned(self, old_token, new_token):
        skill = self._owned_mutable_skill(old_token)
        old_slash = ''
        if hasattr(skill, 'invoke_code'):
            old_slash = (skill.invoke_code() or '').strip()
        if not old_slash:
            old_slash = (skill.code or '').strip()
        return super(AISkill, self.with_context(
            chatboo_confirm_op='renamed',
            chatboo_confirm_old=old_slash,
        )).action_rename_owned(old_token, new_token)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        op = (
            'created'
            if self.env.context.get('chatboo_confirm_op') == 'created'
            else None
        )
        records._chatboo_after_catalog_change(op)
        return records

    def write(self, vals):
        res = super().write(vals)
        op = (
            'renamed'
            if self.env.context.get('chatboo_confirm_op') == 'renamed'
            else None
        )
        self._chatboo_after_catalog_change(op)
        return res

    def unlink(self):
        op = (
            'deleted'
            if self.env.context.get('chatboo_confirm_op') == 'deleted'
            else None
        )
        if op:
            self._chatboo_append_catalog_note(op)
        res = super().unlink()
        self._chatboo_notify_skills_changed(
            confirm=bool(op) and bool(self.env.context.get('chatboo_session_id')),
            session_id=self.env.context.get('chatboo_session_id'),
        )
        return res
