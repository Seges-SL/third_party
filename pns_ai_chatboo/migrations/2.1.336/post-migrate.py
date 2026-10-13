# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v2.1.336: refresh host packs — Excel example, Bootstrap HTML, chat chrome."""
from odoo import api, SUPERUSER_ID

_CODES = ('presentation_grids', 'ui_focus')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    Context = env['ai.context'].with_context(skip_hardcoded_restrictions=True)
    try:
        Context._import_all_from_module(
            replace_existing=True,
            module_name='pns_ai_chatboo',
            only_codes=_CODES,
        )
    except TypeError:
        Context._import_all_from_module(
            replace_existing=True, module_name='pns_ai_chatboo',
        )
    agent = env['ai.agent'].search([('code', '=', 'pns_ai_chatboo')], limit=1)
    if agent:
        try:
            if hasattr(agent, '_restore_required_context_links'):
                agent._restore_required_context_links()
            if hasattr(agent, '_sync_composition_and_cache'):
                agent._sync_composition_and_cache()
            elif hasattr(agent, 'action_rebuild_cache'):
                agent.action_rebuild_cache()
            else:
                agent.get_content(force_rebuild=True)
        except Exception:
            pass
