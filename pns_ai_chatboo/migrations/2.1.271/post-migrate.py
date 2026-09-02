# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v2.1.271: rewrite leftover self pin to self_chatboo."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.agent' not in env:
        return
    Agent = env['ai.agent']
    if hasattr(Agent, '_unlink_foreign_identity_packs'):
        Agent.search([])._unlink_foreign_identity_packs()
    agent = Agent.search([('code', '=', 'pns_ai_chatboo')], limit=1)
    if agent and hasattr(agent, '_restore_required_context_links'):
        try:
            agent._restore_required_context_links()
            agent._sync_composition_and_cache()
        except Exception:
            pass
