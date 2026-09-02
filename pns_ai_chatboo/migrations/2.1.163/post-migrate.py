# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""v2.1.163: opt into MCP nucleus via auto_link_mcp_nucleus (no MCP hardcode).

ai_agent_data.xml is noupdate=1, so existing DBs need this write. Then re-sync
factory knowledge so nucleus contexts re-link using the flag.
"""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.agent' not in env:
        return
    Agent = env['ai.agent']
    if 'auto_link_mcp_nucleus' not in Agent._fields:
        _logger.warning(
            'pns_ai_chatboo 2.1.163: auto_link_mcp_nucleus missing '
            '(upgrade pns_ai_mcp first)',
        )
        return
    agent = Agent.search([('code', '=', 'pns_ai_chatboo')], limit=1)
    if agent:
        agent.write({'auto_link_mcp_nucleus': True})
        _logger.info(
            'pns_ai_chatboo 2.1.163: auto_link_mcp_nucleus=True on %s',
            agent.code,
        )
    try:
        from odoo.addons.pns_ai_mcp import hooks as mcp_hooks
        mcp_hooks.sync_factory_knowledge(
            env, reason='chatboo_2.1.163_nucleus_opt_in',
        )
    except Exception:
        _logger.warning(
            'pns_ai_chatboo 2.1.163: factory sync failed',
            exc_info=True,
        )
