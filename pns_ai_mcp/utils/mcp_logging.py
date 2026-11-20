# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Helpers for ai.log: client identity, remote IP, readable labels."""

import logging

_logger = logging.getLogger(__name__)


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


def resolve_client_label(env, user_id, origin, explicit=None):
    """The program that called, as it named itself. Empty if it said nothing."""
    if explicit:
        return str(explicit)[:255]
    if origin == 'mcp_client':
        from .session_store import MCPClientRegistry
        label = MCPClientRegistry().get(user_id, env=env)
        return str(label)[:255] if label else None
    return None


def known_doors(env, model='ai.log'):
    """Door tokens ``model.origin`` lists: the engine's plus each host's ``selection_add``."""
    if env is None or model not in env:
        return ('mcp_client', 'internal')
    return tuple(env[model]._fields['origin'].get_values(env))
