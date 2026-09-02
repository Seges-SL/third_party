# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v2.1.266: pin Chatboo to self_chatboo; delete leftover ``self``.

2.1.265 unlinked ``self`` while the pin still listed it, so
``_restore_required_context_links`` re-attached the old row. Rewrite the
pin first, then drop the row.
"""
from odoo import api, SUPERUSER_ID


def _tokens(raw):
    out, seen = [], set()
    for part in (raw or '').replace(',', '\n').replace(';', '\n').split('\n'):
        token = part.strip()
        if token and token not in seen:
            seen.add(token)
            out.append(token)
    return out


def _rewrite(raw, drop, ensure=None):
    kept = [token for token in _tokens(raw) if token not in drop]
    if ensure and ensure not in kept:
        kept.append(ensure)
    return '\n'.join(kept)


def _own_self(agent_code):
    token = (agent_code or '').rsplit('_', 1)[-1]
    return 'self_%s' % token if token else ''


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env or 'ai.agent' not in env:
        return
    Context = env['ai.context'].with_context(
        skip_hardcoded_restrictions=True,
        active_test=False,
    )
    Agent = env['ai.agent']
    agents = Agent.search([])
    if hasattr(agents, '_unlink_foreign_identity_packs'):
        agents._unlink_foreign_identity_packs()
    else:
        for agent in agents:
            own = _own_self(agent.code)
            drop = {'self'}
            for token in _tokens(agent.required_context_codes) + _tokens(
                agent.default_context_codes
            ):
                if token.startswith('self_') and token != own:
                    drop.add(token)
            ensure = own if agent.code == 'pns_ai_chatboo' else None
            agent.with_context(_skip_required_context_restore=True).write({
                'required_context_codes': _rewrite(
                    agent.required_context_codes, drop, ensure=ensure,
                ),
                'default_context_codes': _rewrite(
                    agent.default_context_codes, drop,
                ),
            })
            foreign = agent.context_ids.filtered(
                lambda c, _own=own: (c.code or '') == 'self' or (
                    (c.code or '').startswith('self_') and c.code != _own
                )
            )
            if foreign:
                agent.with_context(_skip_required_context_restore=True).write({
                    'context_ids': [(3, cid) for cid in foreign.ids],
                })
    if hasattr(Context, '_retire_generic_self_row'):
        Context._retire_generic_self_row()
    else:
        old = Context.search([('code', '=', 'self')])
        if old:
            for agent in Agent.search([('context_ids', 'in', old.ids)]):
                agent.with_context(_skip_required_context_restore=True).write({
                    'context_ids': [(3, cid) for cid in old.ids],
                })
            xmlids = env['ir.model.data'].search([
                ('model', '=', 'ai.context'),
                ('res_id', 'in', old.ids),
            ])
            if xmlids:
                xmlids.unlink()
            try:
                old.unlink()
            except Exception:
                old.write({'active': False, 'code': 'self_retired'})
    try:
        Context.with_context(active_test=True)._import_all_from_module(
            replace_existing=True,
            module_name='pns_ai_chatboo',
            only_codes=('self_chatboo',),
        )
    except TypeError:
        Context.with_context(active_test=True)._import_all_from_module(
            replace_existing=True, module_name='pns_ai_chatboo',
        )
    chatboo = Agent.search([('code', '=', 'pns_ai_chatboo')], limit=1)
    if chatboo:
        try:
            if hasattr(chatboo, '_restore_required_context_links'):
                chatboo._restore_required_context_links()
            chatboo._sync_composition_and_cache()
        except Exception:
            pass
    mcp = Agent.search([('code', '=', 'pns_ai_mcp')], limit=1)
    if mcp:
        try:
            if hasattr(mcp, '_sync_composition_and_cache'):
                mcp._sync_composition_and_cache()
            else:
                mcp.get_content(force_rebuild=True)
        except Exception:
            pass
