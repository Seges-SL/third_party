# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Chatboo capture: session note + re-apply fetch wrap the wizard onchange strips."""
from odoo import api, fields, models


class SkillCaptureWizard(models.TransientModel):
    _inherit = 'pns_ai_mcp.skill.capture.wizard'

    chatboo_session_id = fields.Integer(readonly=True)

    def _reapply_turn_fetch_wrap(self):
        """The MCP onchange copies raw ``code_to_execute`` and drops the wrap."""
        self.ensure_one()
        if not self.from_chatboo:
            return
        corr = ''
        if self.source_log_id:
            corr = (self.source_log_id.correlation_id or '').strip()
        wrapped, _note = self.env['chatboo.session'].compose_capture_code(
            self.code_body, corr,
        )
        if wrapped != (self.code_body or ''):
            self.code_body = wrapped

    @api.onchange('source_log_id')
    def _onchange_source_log_id(self):
        res = super()._onchange_source_log_id()
        self._reapply_turn_fetch_wrap()
        return res

    def action_create_draft(self):
        if not self.from_chatboo:
            return super().action_create_draft()
        self._reapply_turn_fetch_wrap()
        ctx = {'chatboo_confirm_op': 'created'}
        sid = self.chatboo_session_id or self.env.context.get('chatboo_session_id')
        if sid:
            ctx['chatboo_session_id'] = sid
        return super(
            SkillCaptureWizard, self.with_context(**ctx),
        ).action_create_draft()
