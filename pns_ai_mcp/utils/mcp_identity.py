# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Host identity constants for the MCP endpoint agent only.

Not a brand catalogue. Other modules register their own ``agent.code`` entries
via ``ai.agent._host_identity_registry``.
"""
MCP_AGENT_CODE = 'pns_ai_mcp'
MCP_PRODUCT_NAME = 'MCP Server'
MCP_VENDOR = 'PATANEGRA Soft'
MCP_VENDOR_PLACE = 'Seville (Spain)'
MCP_VENDOR_YEARS = '1996–2026'
MCP_VENDOR_URL = 'https://www.patanegra.com'


def mcp_host_identity_registry():
    """``agent.code`` → constants for the MCP endpoint agent."""
    return {
        MCP_AGENT_CODE: {
            'product_name': MCP_PRODUCT_NAME,
            'vendor': MCP_VENDOR,
            'vendor_place': MCP_VENDOR_PLACE,
            'vendor_years': MCP_VENDOR_YEARS,
            'vendor_url': MCP_VENDOR_URL,
        },
    }
