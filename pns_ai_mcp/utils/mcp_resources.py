# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Native MCP resource URIs (tool + resources/read).

Unknown URIs must return not-found, never KeyError on a missing model.
"""
from __future__ import annotations

SYSTEM_URIS = frozenset({
    'system://info',
    'system://version',
    'system://locale',
})
WHITELIST_URIS = frozenset({
    'url_whitelist',
    'system://url_whitelist',
})


def normalize_resource_uri(uri):
    """Strip and collapse aliases. Empty string if missing."""
    return str(uri or '').strip()


def is_system_uri(uri):
    return normalize_resource_uri(uri) in SYSTEM_URIS


def is_whitelist_uri(uri):
    return normalize_resource_uri(uri) in WHITELIST_URIS


def is_context_pack_uri(uri):
    return normalize_resource_uri(uri).startswith('mcp://contexts/')


def whitelist_facts(env=None):
    """Active, in-window whitelist rows for the LLM (no secrets, not terminal)."""
    if env is None or 'ai.url.whitelist' not in env:
        return {'entries': [], 'count': 0}
    now = None
    try:
        from odoo import fields
        now = fields.Datetime.now()
    except Exception:
        now = None
    rows = []
    recs = env['ai.url.whitelist'].sudo().search([('active', '=', True)])
    for rec in recs:
        if now is not None:
            if rec.valid_from and rec.valid_from > now:
                continue
            if rec.valid_until and rec.valid_until < now:
                continue
        rows.append({
            'domain': rec.domain or '',
            'kind': rec.kind or 'web',
            'notes': rec.notes or '',
            'valid_from': str(rec.valid_from) if rec.valid_from else '',
            'valid_until': str(rec.valid_until) if rec.valid_until else '',
        })
    return {'entries': rows, 'count': len(rows)}


def unknown_resource_error(uri):
    """JSON-RPC error for a URI this server does not serve."""
    return {
        'error': {
            'code': -32602,
            'message': (
                'Resource not found: %s. Known URIs: system://info, '
                'system://version, system://locale, url_whitelist. '
                'Knowledge packs: get_context, not this tool.'
            ) % (uri or ''),
        }
    }


def context_pack_use_get_context_error(uri):
    """Packs stay on get_context (no XML dump via this tool)."""
    return {
        'error': {
            'code': -32602,
            'message': (
                'Knowledge pack %s is loaded with get_context, '
                'not fetch_native_mcp_resource.'
            ) % (uri or ''),
        }
    }
