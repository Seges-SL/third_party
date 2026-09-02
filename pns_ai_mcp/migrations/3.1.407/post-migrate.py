# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.407: skip leftover self files on import; retire rows after import."""
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
            only_codes=('self_mcp',),
        )
    except TypeError:
        Context._import_all_from_module(
            replace_existing=True, module_name='pns_ai_mcp',
        )
    if hasattr(Context, '_retire_generic_self_row'):
        Context._retire_generic_self_row()
    for code in ('pns_ai_mcp', 'pns_ai_chatboo'):
        agent = env['ai.agent'].search([('code', '=', code)], limit=1)
        if not agent:
            continue
        try:
            if hasattr(agent, '_restore_required_context_links'):
                agent._restore_required_context_links()
            if hasattr(agent, '_sync_composition_and_cache'):
                agent._sync_composition_and_cache()
        except Exception:
            pass
