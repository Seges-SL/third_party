# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v2.1.237: write Chatboo pull lists (noupdate XML never reached existing DBs)."""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

_PIN_CODES = ('self', 'presentation_grids', 'ui_focus')
_DEFAULT_CTX = '@pns_ai_mcp\n@pns_ai_chatboo\nacl_security'
_DEFAULT_SKILL = '@pns_ai_chatboo'


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.agent' not in env:
        return
    Agent = env['ai.agent']
    agent = Agent.search([('code', '=', 'pns_ai_chatboo')], limit=1)
    if not agent:
        return
    vals = {}
    if 'required_context_codes' in Agent._fields:
        existing = agent._required_context_codes_set()
        merged = existing | set(_PIN_CODES)
        ordered = [c for c in _PIN_CODES if c in merged] + sorted(
            merged - set(_PIN_CODES)
        )
        vals['required_context_codes'] = '\n'.join(ordered)
    if 'default_context_codes' in Agent._fields and not (
        agent.default_context_codes or ''
    ).strip():
        vals['default_context_codes'] = _DEFAULT_CTX
    if 'default_skill_codes' in Agent._fields and not (
        agent.default_skill_codes or ''
    ).strip():
        vals['default_skill_codes'] = _DEFAULT_SKILL
    if vals:
        agent.write(vals)
    _logger.info('pns_ai_chatboo 2.1.237: pull lists %s', vals)
