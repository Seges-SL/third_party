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

    def _chatboo_skill_slash(self, rec):
        slash = ''
        if hasattr(rec, 'invoke_code'):
            slash = (rec.invoke_code() or '').strip()
        if not slash:
            slash = (rec.code or '').strip()
        return slash

    def _chatboo_skill_card(self, rec, op, old=''):
        """Markdown result card. Slash comes from the record, never invented."""
        slash = self._chatboo_skill_slash(rec)
        if not slash:
            return '', ''
        if op == 'created':
            preamble = _('Skill /%s created.') % slash
            prompt = '/create-skill %s' % slash
        elif op == 'updated':
            preamble = _('Skill /%s updated.') % slash
            prompt = '/edit-skill %s' % slash
        elif op == 'deleted':
            return (
                '# /%s\n\n**%s**\n' % (slash, _('Skill /%s deleted.') % slash),
                '/delete-skill %s' % slash,
            )
        elif op == 'renamed':
            if old:
                preamble = _('Skill renamed: /%s → /%s') % (old, slash)
                prompt = '/rename-skill %s %s' % (old, slash)
            else:
                preamble = _('Skill /%s renamed.') % slash
                prompt = '/rename-skill %s' % slash
        else:
            return '', ''
        body = '**%s**\n' % preamble
        if op in ('created', 'updated', 'renamed'):
            try:
                from odoo.addons.pns_ai_mcp.utils.skill_help import (
                    build_slash_help_markdown,
                    skill_help_meta,
                )
                body = '%s\n%s' % (
                    body, build_slash_help_markdown(skill_help_meta(rec)),
                )
            except Exception:
                body = '%s\n# /%s\n' % (body, slash)
        return body.strip() + '\n', prompt

    def _chatboo_append_catalog_note(self, op):
        """Persist a result card. Slash comes from the record, never invented."""
        session = self._chatboo_confirm_session()
        if not session:
            return
        old = (self.env.context.get('chatboo_confirm_old') or '').strip()
        usage = self.env.context.get('skill_author_usage') or {}
        if not isinstance(usage, dict):
            usage = {}
        provider = self.env.context.get('skill_author_provider') or {}
        if not isinstance(provider, dict):
            provider = {}
        blocks = []
        prompt = ''
        for rec in self:
            card, user_line = self._chatboo_skill_card(rec, op, old)
            if not card:
                continue
            blocks.append(card)
            if user_line and not prompt:
                prompt = user_line
        if not blocks:
            return
        session.append_local_ack(
            '\n'.join(blocks),
            usage=usage,
            provider_meta=provider,
            user_prompt=prompt,
        )

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
        ctx_op = self.env.context.get('chatboo_confirm_op')
        if ctx_op == 'renamed':
            op = 'renamed'
        elif ctx_op in ('created', 'updated'):
            op = 'updated'
        else:
            op = None
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
