# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v2.1.269: delete leftover domain/self files from the Chatboo addon path."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    Context = env['ai.context'].with_context(skip_hardcoded_restrictions=True)
    if hasattr(Context, '_purge_retired_self_source_files'):
        Context._purge_retired_self_source_files()
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
