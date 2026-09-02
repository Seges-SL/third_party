# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""MCP protocol era detection and stateless (2026-07-28) helpers."""

MCP_META_PROTOCOL_VERSION = 'io.modelcontextprotocol/protocolVersion'
MCP_META_CLIENT_INFO = 'io.modelcontextprotocol/clientInfo'
MCP_META_CLIENT_CAPABILITIES = 'io.modelcontextprotocol/clientCapabilities'
MCP_META_SERVER_INFO = 'io.modelcontextprotocol/serverInfo'

MCP_VERSION_2026_07_28 = '2026-07-28'

MCP_MODERN_VERSIONS = frozenset({MCP_VERSION_2026_07_28})

MCP_LEGACY_VERSIONS = frozenset({
    '2024-11-05',
    '2025-03-26',
    '2025-06-18',
    '2025-11-25',
})

# Advertised on server/discover and UnsupportedProtocolVersionError.
MCP_SUPPORTED_VERSIONS = (
    MCP_VERSION_2026_07_28,
    '2025-06-18',
    '2025-03-26',
    '2024-11-05',
)

MCP_LIST_METHODS = frozenset({'tools/list', 'prompts/list', 'resources/list'})

MCP_SERVER_INFO = {'name': 'pns_ai_mcp', 'version': '2.0.0'}

MCP_SERVER_INSTRUCTIONS = (
    'Use prompts/get(name="system_prompt") to load the system knowledge context '
    'and start dialogue. Tools available via tools/list and tools/call.'
)


def extract_params_meta(params):
    if not isinstance(params, dict):
        return {}
    meta = params.get('_meta')
    return meta if isinstance(meta, dict) else {}


def _header_protocol_version(headers):
    if not headers:
        return None
    for key in ('MCP-Protocol-Version', 'Mcp-Protocol-Version', 'HTTP_MCP_PROTOCOL_VERSION'):
        value = headers.get(key)
        if value:
            return str(value).strip()
    return None


def protocol_version_from_request(params, headers=None):
    """Protocol version from _meta or MCP-Protocol-Version header."""
    meta = extract_params_meta(params)
    pv = meta.get(MCP_META_PROTOCOL_VERSION)
    if pv:
        return str(pv).strip()
    return _header_protocol_version(headers)


def detect_mcp_era(method, params, headers=None):
    """Return ``modern`` (stateless 2026-07-28) or ``legacy`` (initialize handshake).

    Dual-era rule from MCP spec: ``initialize`` always selects legacy semantics;
    per-request ``_meta`` or a modern protocol version selects stateless.
    """
    if method in ('initialize', 'notifications/initialized'):
        return 'legacy'
    meta = extract_params_meta(params)
    if MCP_META_PROTOCOL_VERSION in meta:
        return 'modern'
    header_pv = _header_protocol_version(headers)
    if header_pv in MCP_MODERN_VERSIONS:
        return 'modern'
    return 'legacy'


def client_info_from_params(params):
    return extract_params_meta(params).get(MCP_META_CLIENT_INFO) or {}


def validate_modern_protocol_version(requested):
    """Return JSON-RPC error dict or None if the version is supported."""
    if requested in MCP_MODERN_VERSIONS:
        return None
    return {
        'code': -32022,
        'message': 'Unsupported protocol version',
        'data': {
            'supported': list(MCP_SUPPORTED_VERSIONS),
            'requested': requested or '',
        },
    }


def header_protocol_mismatch(headers, params):
    """Return JSON-RPC error dict when header and _meta disagree."""
    header_pv = _header_protocol_version(headers)
    if not header_pv:
        return None
    meta_pv = extract_params_meta(params).get(MCP_META_PROTOCOL_VERSION)
    if meta_pv and str(meta_pv).strip() != header_pv:
        return {
            'code': -32020,
            'message': 'MCP-Protocol-Version header does not match _meta protocolVersion',
        }
    return None


def discover_result():
    return {
        'resultType': 'complete',
        'supportedVersions': list(MCP_SUPPORTED_VERSIONS),
        'capabilities': {
            'tools': {'listChanged': False},
            'prompts': {'listChanged': False},
            'resources': {'listChanged': False},
        },
        '_meta': {
            MCP_META_SERVER_INFO: dict(MCP_SERVER_INFO),
        },
        'instructions': MCP_SERVER_INSTRUCTIONS,
        'ttlMs': 3600000,
        'cacheScope': 'public',
    }


def wrap_modern_result(result, method=None):
    """Attach resultType, serverInfo _meta and optional list cache hints."""
    if not isinstance(result, dict) or 'error' in result:
        return result
    wrapped = dict(result)
    wrapped.setdefault('resultType', 'complete')
    meta = dict(wrapped.get('_meta') or {})
    meta.setdefault(MCP_META_SERVER_INFO, dict(MCP_SERVER_INFO))
    wrapped['_meta'] = meta
    if method in MCP_LIST_METHODS:
        wrapped.setdefault('ttlMs', 3600000)
        wrapped.setdefault('cacheScope', 'private')
    return wrapped
