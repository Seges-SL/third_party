# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""
Fixed codes of the agents this module declares.

Each product feature uses the agent declared by its Odoo module (origin=module).
There is no runtime swap via settings or ir.config_parameter. A host module
(chat, voice, …) passes its own agent code; the engine does not list them.

Extension: install a module that declares ``ai.agent`` in XML; it appears in
AI Engine settings under Internal (inference) or External (endpoint).
"""

MCP_BARE_AGENT_CODE = 'pns_ai_mcp'
ADMIN_AGENT_CODE = 'pns_ai_admin'

# Legacy alias (tests / imports).
MCP_BARE_AGENT_CODE_DEFAULT = MCP_BARE_AGENT_CODE

# Feature key → agent code, for the engine's own features.
FEATURE_AGENT_CODES = {
    'admin': ADMIN_AGENT_CODE,
}
