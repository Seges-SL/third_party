# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Import domain context ``geo`` (multipin map guidance) on upgrade.

``post_init_hook`` only runs on install; a plain ``-u`` would leave ``geo.xml``
out of ``ai.context``. Force-sync via the shipped-domain whitelist path.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    try:
        env['ai.context'].with_context(
            skip_hardcoded_restrictions=True,
        )._import_all_from_module(
            replace_existing=True,
            module_name='pns_ai_mcp',
            only_codes=['geo'],
        )
        # Refresh Chatboo / MCP agent caches so the new context is visible.
        for agent in env['ai.agent'].search([
            ('code', 'in', ['pns_ai_chatboo', 'pns_ai_mcp']),
        ]):
            try:
                if hasattr(agent, 'action_rebuild_cache'):
                    agent.action_rebuild_cache()
                elif hasattr(agent, '_rebuild_context_cache'):
                    agent._rebuild_context_cache()
            except Exception:
                _logger.debug(
                    'MCP 3.1.105: agent cache rebuild skipped for %s',
                    agent.code, exc_info=True,
                )
        _logger.info('MCP 3.1.105: domain context geo imported from files')
    except Exception:
        _logger.warning(
            'MCP 3.1.105: failed to import geo context', exc_info=True,
        )
