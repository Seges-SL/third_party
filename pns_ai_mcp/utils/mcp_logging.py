# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Helpers for ai.log: client identity, remote IP, readable labels."""

import logging

_logger = logging.getLogger(__name__)

CLIENT_CHATBOO = 'Chatboo'
CLIENT_INTERNAL = 'Internal'
CLIENT_UNKNOWN = 'Unknown'


def normalize_remote_ip(remote_ip=None):
    """Return caller IP (max 64 chars) from argument or current HTTP request."""
    if remote_ip:
        return str(remote_ip)[:64]
    try:
        from odoo.http import request
        if request and getattr(request, 'httprequest', None):
            addr = request.httprequest.remote_addr
            if addr:
                return str(addr)[:64]
    except Exception:
        pass
    return None


def resolve_remote_ip():
    return normalize_remote_ip(None)


def request_log_stamp():
    """Identity the host stamped on the live HTTP request, if any."""
    try:
        from odoo.http import request
        if not request:
            return {}
        return {
            'source_channel': getattr(request, 'mcp_source_channel', None),
            'agent_code': getattr(request, 'mcp_agent_code', None),
            'client_label': getattr(request, 'mcp_client_label', None),
            'turn_prefix': getattr(request, 'mcp_turn_prefix', None),
            'turn': getattr(request, 'mcp_turn', None),
        }
    except Exception:
        return {}


def resolve_log_agent(env, agent_code=None):
    """``ai.agent`` row for this turn, or empty. Code comes from the caller."""
    code = (agent_code or '').strip()
    if not code and env is not None:
        code = str((env.context or {}).get('mcp_agent_code') or '').strip()
    if not code or env is None or 'ai.agent' not in env:
        return env['ai.agent'] if env is not None and 'ai.agent' in env else None
    return env['ai.agent'].sudo().search([('code', '=', code)], limit=1)


def agent_log_label(agent):
    """Agents-list name. Empty if the row is missing."""
    if not agent:
        return ''
    return (agent.name or agent.code or '').strip()


def resolve_client_label(env, user_id, origin, explicit=None, agent_code=None):
    """Human client name for ai.log.client_label (stored, English base strings)."""
    if explicit:
        return str(explicit)[:255]
    agent = resolve_log_agent(env, agent_code)
    name = agent_log_label(agent)
    if name:
        return name[:255]
    channel = origin or 'internal'
    if channel == 'chatboo':
        return CLIENT_CHATBOO
    if channel == 'internal':
        return CLIENT_INTERNAL
    if channel == 'mcp_client':
        from .session_store import MCPClientRegistry
        label = MCPClientRegistry().get(user_id, env=env)
        return label or CLIENT_UNKNOWN
    return CLIENT_UNKNOWN
