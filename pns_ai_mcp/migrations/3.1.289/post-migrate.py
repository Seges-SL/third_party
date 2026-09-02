# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""v3.1.289: rebuild caches after indexing all nucleus domain packs."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.agent' not in env:
        return
    try:
        env['ir.config_parameter'].sudo().set_param(
            'pns_ai_mcp.domain_index_inject', 'True',
        )
    except Exception:
        _logger.debug('3.1.289: could not set domain_index_inject ICP', exc_info=True)

    for agent in env['ai.agent'].search([
        ('code', 'in', ['pns_ai_chatboo', 'pns_ai_mcp', 'pns_acl_manager']),
    ]):
        try:
            if hasattr(agent, 'action_rebuild_cache'):
                agent.action_rebuild_cache()
            else:
                agent.get_content(force_rebuild=True)
            _logger.info(
                'MCP 3.1.289: rebuilt cache for agent %s (%s chars)',
                agent.code,
                len(agent.cached_content or ''),
            )
        except Exception:
            _logger.warning(
                'MCP 3.1.289: cache rebuild failed for %s',
                agent.code, exc_info=True,
            )
