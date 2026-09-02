# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v2.1.265: rename context self → self_chatboo and refresh the pin."""
from odoo import api, SUPERUSER_ID


def _replace_pin_token(raw, old, new):
    tokens = [
        t.strip() for t in (raw or '').replace(',', '\n').split('\n') if t.strip()
    ]
    out = []
    seen = set()
    for token in tokens:
        token = new if token == old else token
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    if new not in seen:
        out.append(new)
    return '\n'.join(out)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    Context = env['ai.context'].with_context(skip_hardcoded_restrictions=True)
    old = Context.search([('code', '=', 'self')], limit=1)
    new = Context.search([('code', '=', 'self_chatboo')], limit=1)
    if old and not new:
        old.write({'code': 'self_chatboo'})
    elif old and new and old.id != new.id:
        for agent in old.agent_ids:
            agent.write({
                'context_ids': [(3, old.id), (4, new.id)],
            })
        try:
            old.unlink()
        except Exception:
            old.write({'active': False})
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
    agent = env['ai.agent'].search([('code', '=', 'pns_ai_chatboo')], limit=1)
    if agent:
        agent.write({
            'required_context_codes': _replace_pin_token(
                agent.required_context_codes, 'self', 'self_chatboo',
            ),
        })
        try:
            if hasattr(agent, '_restore_required_context_links'):
                agent._restore_required_context_links()
            agent._sync_composition_and_cache()
        except Exception:
            pass
