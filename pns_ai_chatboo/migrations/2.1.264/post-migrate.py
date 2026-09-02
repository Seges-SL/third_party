# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v2.1.264: refresh self — greeting at most once, never on data turns."""

from odoo import api, SUPERUSER_ID

_SELF_CODES = ('self', 'self_es_ES', 'self_en_US')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    Context = env['ai.context'].with_context(skip_hardcoded_restrictions=True)
    try:
        Context._import_all_from_module(
            replace_existing=True,
            module_name='pns_ai_chatboo',
            only_codes=_SELF_CODES,
        )
    except TypeError:
        Context._import_all_from_module(
            replace_existing=True, module_name='pns_ai_chatboo',
        )
    agent = env['ai.agent'].search([('code', '=', 'pns_ai_chatboo')], limit=1)
    if agent:
        try:
            agent._sync_composition_and_cache()
        except Exception:
            pass
