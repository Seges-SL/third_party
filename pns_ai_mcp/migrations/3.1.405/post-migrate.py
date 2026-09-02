# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.405: drop retired ``self`` and unlink foreign identity packs."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.agent' not in env or 'ai.context' not in env:
        return
    Agent = env['ai.agent']
    Context = env['ai.context'].with_context(skip_hardcoded_restrictions=True)
    agents = Agent.search([])
    if hasattr(agents, '_unlink_foreign_identity_packs'):
        agents._unlink_foreign_identity_packs()
    if hasattr(Context, '_retire_generic_self_row'):
        Context._retire_generic_self_row()
    try:
        Context._import_all_from_module(
            replace_existing=True,
            module_name='pns_ai_mcp',
            only_codes=('self_mcp',),
        )
    except TypeError:
        Context._import_all_from_module(
            replace_existing=True, module_name='pns_ai_mcp',
        )
    for code in ('pns_ai_mcp', 'pns_ai_chatboo'):
        agent = Agent.search([('code', '=', code)], limit=1)
        if not agent:
            continue
        try:
            if hasattr(agent, '_restore_required_context_links'):
                agent._restore_required_context_links()
            if hasattr(agent, '_sync_composition_and_cache'):
                agent._sync_composition_and_cache()
            else:
                agent.get_content(force_rebuild=True)
        except Exception:
            pass
