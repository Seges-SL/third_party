# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Chatboo access: MCP API key hash is the server-side carnet (fail-closed)."""


def user_has_chatboo_access(env, user=None):
    """True only if the user has a non-empty ``ai.mcp.user.mcp_api_key_hash``.

    Chatboo UI auth is the Odoo session; this carnet gates who may use the
    assistant. Fail-closed: any error → no access.
    """
    try:
        user = user or env.user
        McpUser = env['ai.mcp.user'].sudo()
        if hasattr(McpUser, 'user_has_mcp_api_key'):
            return bool(McpUser.user_has_mcp_api_key(user))
        return bool(McpUser.search_count([
            ('user_id', '=', user.id),
            ('mcp_api_key_hash', '!=', False),
        ]))
    except Exception:
        return False
