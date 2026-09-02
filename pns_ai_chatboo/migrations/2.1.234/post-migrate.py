# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v2.1.234: pin host packs on the Chatboo agent Contexts list."""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

_PIN_CODES = ('self', 'presentation_grids', 'ui_focus')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.agent' not in env:
        return
    Agent = env['ai.agent']
    if 'required_context_codes' not in Agent._fields:
        return
    agent = Agent.search([('code', '=', 'pns_ai_chatboo')], limit=1)
    if not agent:
        return
    existing = agent._required_context_codes_set()
    merged = existing | set(_PIN_CODES)
    ordered = [c for c in _PIN_CODES if c in merged] + sorted(merged - set(_PIN_CODES))
    agent.write({'required_context_codes': '\n'.join(ordered)})
    _logger.info(
        'pns_ai_chatboo 2.1.234: required_context_codes=%s',
        ordered,
    )
