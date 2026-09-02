# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.404: nucleus without brand; pin self_mcp on the endpoint agent."""
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
            only_codes=('system_prompt', 'self_mcp'),
        )
    except TypeError:
        Context._import_all_from_module(
            replace_existing=True,
            module_name='pns_ai_mcp',
        )
    Agent = env['ai.agent']
    mcp = Agent.search([('code', '=', 'pns_ai_mcp')], limit=1)
    if mcp:
        required = (mcp.required_context_codes or '').strip()
        tokens = [
            t.strip() for t in required.replace(',', '\n').split('\n') if t.strip()
        ]
        if 'self_mcp' not in tokens:
            tokens.append('self_mcp')
            mcp.write({'required_context_codes': '\n'.join(tokens)})
        try:
            if hasattr(mcp, '_restore_required_context_links'):
                mcp._restore_required_context_links()
            if hasattr(mcp, '_sync_composition_and_cache'):
                mcp._sync_composition_and_cache()
            else:
                mcp.get_content(force_rebuild=True)
        except Exception:
            pass
    chatboo = Agent.search([('code', '=', 'pns_ai_chatboo')], limit=1)
    if chatboo:
        try:
            if hasattr(chatboo, '_sync_composition_and_cache'):
                chatboo._sync_composition_and_cache()
            else:
                chatboo.get_content(force_rebuild=True)
        except Exception:
            pass
