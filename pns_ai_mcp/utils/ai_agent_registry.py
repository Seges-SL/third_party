# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""
Fixed agent codes for module-owned AI features.

Each product feature uses the agent declared by its Odoo module (origin=module).
There is no runtime swap via settings or ir.config_parameter.

Extension: install a module that declares ``ai.agent`` in XML; it appears in
AI Engine settings under Internal (inference) or External (endpoint).
"""

MCP_BARE_AGENT_CODE = 'pns_ai_mcp'
CHATBOO_AGENT_CODE = 'pns_ai_chatboo'

# Legacy aliases (tests / imports).
MCP_BARE_AGENT_CODE_DEFAULT = MCP_BARE_AGENT_CODE
DEFAULT_INFERENCE_AGENT_CODE_DEFAULT = CHATBOO_AGENT_CODE

# Feature key → fixed agent code (hard-bound at compile time per module).
FEATURE_AGENT_CODES = {
    'chatboo': CHATBOO_AGENT_CODE,
}
