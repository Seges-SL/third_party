# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""v3.1.285: rebuild agent caches after turn-scoped domain index inject."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.agent' not in env:
        return
    # Default ON: indexed domains leave always-on cache (kill-switch = False).
    try:
        env['ir.config_parameter'].sudo().set_param(
            'pns_ai_mcp.domain_index_inject', 'True',
        )
    except Exception:
        _logger.debug('3.1.285: could not set domain_index_inject ICP', exc_info=True)

    for agent in env['ai.agent'].search([
        ('code', 'in', ['pns_ai_chatboo', 'pns_ai_mcp']),
    ]):
        try:
            if hasattr(agent, 'action_rebuild_cache'):
                agent.action_rebuild_cache()
            else:
                agent.get_content(force_rebuild=True)
            _logger.info(
                'MCP 3.1.285: rebuilt cache for agent %s (%s chars)',
                agent.code,
                len(agent.cached_content or ''),
            )
        except Exception:
            _logger.warning(
                'MCP 3.1.285: cache rebuild failed for %s',
                agent.code, exc_info=True,
            )
