# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v2.1.267: drop leftover self + self_es_ES (locale clone of the old slot)."""
from odoo import api, SUPERUSER_ID

_RETIRED = ('self', 'self_es_ES', 'self_en_US', 'self_retired')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    Context = env['ai.context'].with_context(
        skip_hardcoded_restrictions=True,
        active_test=False,
    )
    Agent = env['ai.agent']
    if hasattr(Agent, '_unlink_foreign_identity_packs'):
        Agent.search([])._unlink_foreign_identity_packs()
    if hasattr(Context, '_retire_generic_self_row'):
        Context._retire_generic_self_row()
    else:
        old = Context.search([
            '|', '|',
            ('code', 'in', list(_RETIRED)),
            ('base_code', '=', 'self'),
            ('rel_path', '=like', 'contexts/domain/self/%'),
        ])
        old = old.filtered(lambda r: (r.code or '') not in ('self_chatboo', 'self_mcp'))
        if old:
            for agent in Agent.search([('context_ids', 'in', old.ids)]):
                agent.with_context(_skip_required_context_restore=True).write({
                    'context_ids': [(3, cid) for cid in old.ids],
                })
            try:
                old.unlink()
            except Exception:
                old.write({'active': False})
    chatboo = Agent.search([('code', '=', 'pns_ai_chatboo')], limit=1)
    if chatboo:
        try:
            if hasattr(chatboo, '_restore_required_context_links'):
                chatboo._restore_required_context_links()
            chatboo._sync_composition_and_cache()
        except Exception:
            pass
