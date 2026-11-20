# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""
mcp_driver.py — API driver for MCP servers (api_type='mcp').

Thin adapter over MCPClient; supports binary content blocks (image/resource/
JSON-with-base64) for document downloads.
"""

import logging

from .base import APIDriver, APIDriverError

_logger = logging.getLogger(__name__)


class MCPDriver(APIDriver):
    """Driver for external MCP servers (Anthropic Model Context Protocol)."""

    api_type = 'mcp'

    @staticmethod
    def _client(server, auth_token=None):
        from odoo.addons.pns_ai_mcp.utils.mcp_client import MCPClient
        return MCPClient(server, auth_token=auth_token)

    def discover(self, server):
        from odoo.addons.pns_ai_mcp.utils.mcp_client import MCPClientError
        warnings = []
        client = self._client(server)
        try:
            client.connect()
            tools = client.list_tools()
            resources = self._optional(client.list_resources, 'resources/list', warnings)
            prompts = self._optional(client.list_prompts, 'prompts/list', warnings)
        except MCPClientError as e:
            raise APIDriverError(str(e))
        finally:
            client.close()
        return {
            'tools': tools,
            'resources': resources,
            'prompts': prompts,
            'spec': None,
            'warnings': warnings,
        }

    @staticmethod
    def _optional(list_fn, label, warnings):
        try:
            return list_fn() or []
        except Exception as e:
            _logger.info('MCP discovery: %s not available (%s)', label, e)
            warnings.append('%s: %s' % (label, e))
            return []

    def test_connection(self, server):
        from odoo.addons.pns_ai_mcp.utils.mcp_client import MCPClientError
        client = self._client(server)
        try:
            info = client.connect()
        except MCPClientError as e:
            raise APIDriverError(str(e))
        finally:
            client.close()
        name = info.get('serverInfo', {}).get('name', '?') if info else '?'
        return 'MCP server: %s' % name

    def call(self, server, tool_name, arguments=None, auth_token=None):
        from odoo.addons.pns_ai_mcp.utils.mcp_client import MCPClientError
        from ....utils.session_download import extract_binary_from_mcp_blocks
        arguments = dict(arguments or {})
        client = self._client(server, auth_token=auth_token)
        try:
            client.connect()
            content = client.call_tool(tool_name, arguments)
        except MCPClientError as e:
            raise APIDriverError(str(e))
        finally:
            client.close()

        binary = extract_binary_from_mcp_blocks(
            content, tool_name=tool_name, arguments=arguments,
        )
        if binary:
            return binary

        text_parts = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get('type') == 'text':
                    text_parts.append(block.get('text', ''))
        elif isinstance(content, str):
            text_parts.append(content)
        return '\n'.join(text_parts)
