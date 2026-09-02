# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v2.1.268: reimport self_chatboo; drop leftover self / self_es_ES after import."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    Context = env['ai.context'].with_context(skip_hardcoded_restrictions=True)
    try:
        Context._import_all_from_module(
            replace_existing=True,
            module_name='pns_ai_chatboo',
            only_codes=('self_chatboo',),
        )
    except TypeError:
        Context._import_all_from_module(
            replace_existing=True, module_name='pns_ai_chatboo',
        )
    if hasattr(Context, '_retire_generic_self_row'):
        Context._retire_generic_self_row()
    agent = env['ai.agent'].search([('code', '=', 'pns_ai_chatboo')], limit=1)
    if agent:
        try:
            if hasattr(agent, '_restore_required_context_links'):
                agent._restore_required_context_links()
            agent._sync_composition_and_cache()
        except Exception:
            pass
