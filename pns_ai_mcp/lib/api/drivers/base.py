# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""
base.py — Abstract driver for external self-documented APIs.

One driver per ``api_type`` of ``ai.api.server``:

    - ``mcp``:     Anthropic Model Context Protocol (JSON-RPC over SSE/stdio).
    - ``openapi``: OpenAPI/Swagger described HTTP APIs (FastAPI, etc.).
      A pasted ``spec_json`` (``spec_manual``) is supported; it is not a
      third protocol.

The contract is deliberately tiny and catalogue-centric: ``discover`` returns
a NORMALIZED tool catalogue (MCP ``tools/list`` shape: name, description,
inputSchema) regardless of the underlying protocol, so prompt injection,
counts and HTML rendering work identically for every api_type.
"""


class APIDriverError(Exception):
    """Transport or protocol error raised by an API driver."""


def build_auth_headers(server, token=None):
    """HTTP auth headers from the server's auth config + a resolved token.

    ``token`` is the PER-CALL credential (user key or server default); the
    header placement (bearer / api_key / custom_header) stays on the server.
    """
    headers = {}
    auth_type = server.auth_type
    token = token if token is not None else (server.auth_token or '')
    if not token or auth_type == 'none':
        return headers
    if auth_type == 'bearer':
        headers['Authorization'] = 'Bearer %s' % token
    elif auth_type == 'api_key':
        headers[server.auth_header_name or 'Authorization'] = token
    elif auth_type == 'custom_header':
        headers[server.auth_header_name or 'X-API-Key'] = token
    return headers


class APIDriver:
    """Abstract external-API driver.

    Instances are created fresh per operation via ``get_api_driver()`` and
    receive the ``ai.api.server`` record on each method (stateless SPI).
    """

    api_type = None

    def discover(self, server):
        """Fetch the server's self-description.

        Returns a dict::

            {
                'tools': [...],      # MCP tools/list shape (normalized)
                'resources': [...],  # optional
                'prompts': [...],    # optional
                'spec': {...} | None,  # raw spec when the protocol has one
                'warnings': [...],   # non-fatal discovery notes
            }

        Raises:
            APIDriverError: on transport/protocol failure.
        """
        raise NotImplementedError

    def test_connection(self, server):
        """Cheap connectivity check. Returns a short human summary string."""
        raise NotImplementedError

    def call(self, server, tool_name, arguments=None, auth_token=None):
        """Invoke one catalogued operation and return its text body.

        Args:
            server: ``ai.api.server`` record.
            tool_name: catalogue name (MCP tool / OpenAPI operationId).
            arguments: dict of call arguments.
            auth_token: resolved credential (user key or server default).

        Returns:
            str: raw text result (caller truncates / packages it).

        Raises:
            APIDriverError: on transport/protocol failure or remote error.
        """
        raise NotImplementedError
