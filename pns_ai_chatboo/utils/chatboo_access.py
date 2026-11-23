# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Chatboo access: carnet (API key hash) AND conversational permission."""


def user_has_chatboo_access(env, user=None):
    """True only with a non-empty MCP API-key hash and the conversational group.

    Chatboo UI auth is the Odoo session; the carnet is identity, the group is
    the dialogue door. Fail-closed: any error → no access.
    """
    try:
        user = user or env.user
        try:
            from odoo.addons.pns_ai_mcp.utils.conversational import (
                user_is_ai_conversational,
            )
        except ImportError:
            return False
        if not user_is_ai_conversational(user):
            return False
        McpUser = env['ai.mcp.user'].sudo()
        if hasattr(McpUser, 'user_has_mcp_api_key'):
            return bool(McpUser.user_has_mcp_api_key(user))
        return bool(McpUser.search_count([
            ('user_id', '=', user.id),
            ('mcp_api_key_hash', '!=', False),
        ]))
    except Exception:
        return False
