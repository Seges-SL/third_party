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


def resolve_client_label(env, user_id, origin, explicit=None):
    """Human client name for ai.log.client_label (stored, English base strings)."""
    if explicit:
        return str(explicit)[:255]
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
