# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""MCP + Chatboo share slim cache; MCP gets catalog / query inject (3.1.295)."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.agent' not in env:
        return
    for agent in env['ai.agent'].search([
        ('code', 'in', ['pns_ai_mcp', 'pns_ai_chatboo', 'pns_acl_manager']),
    ]):
        try:
            if hasattr(agent, 'action_rebuild_cache'):
                agent.action_rebuild_cache()
            else:
                agent.get_content(force_rebuild=True)
            _logger.info(
                'MCP 3.1.295: rebuilt cache for agent %s (%s chars, type=%s)',
                agent.code,
                len(agent.cached_content or ''),
                agent.agent_type,
            )
        except Exception:
            _logger.warning(
                'MCP 3.1.295: cache rebuild failed for %s',
                agent.code, exc_info=True,
            )
