# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.402: refresh system_prompt so scope/limits are not who-are-you."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    Context = env['ai.context'].with_context(skip_hardcoded_restrictions=True)
    try:
        Context._import_all_from_module(
            replace_existing=True,
            module_name='pns_ai_mcp',
            only_codes=('system_prompt',),
        )
    except TypeError:
        Context._import_all_from_module(
            replace_existing=True,
            module_name='pns_ai_mcp',
            core_only=True,
        )
    agent = env['ai.agent'].search([('code', '=', 'pns_ai_chatboo')], limit=1)
    if agent:
        try:
            if hasattr(agent, '_sync_composition_and_cache'):
                agent._sync_composition_and_cache()
            elif hasattr(agent, 'action_rebuild_cache'):
                agent.action_rebuild_cache()
            else:
                agent.get_content(force_rebuild=True)
        except Exception:
            pass
