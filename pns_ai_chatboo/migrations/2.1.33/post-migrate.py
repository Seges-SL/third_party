# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""v2.1.33: reimport Chatboo contexts (ui_focus, self) and rebuild agent cache.

Requires pns_ai_mcp >= 3.0.107 (XML metadata parses agent_codes for linking).
"""

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    env['ai.context'].with_context(
        skip_hardcoded_restrictions=True,
    )._import_all_from_module(
        replace_existing=True, module_name='pns_ai_chatboo',
    )
    agent = env['ai.agent'].search([('code', '=', 'pns_ai_chatboo')], limit=1)
    if agent:
        try:
            agent._sync_composition_and_cache()
        except Exception:
            pass
