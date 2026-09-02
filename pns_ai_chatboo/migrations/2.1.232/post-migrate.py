# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""v2.1.232: drop cloned self locale packs; identity is language-neutral."""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

_CLONE_CODES = ('self_es_ES', 'self_en_US')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    Context = env['ai.context'].with_context(
        skip_hardcoded_restrictions=True,
        active_test=False,
    )
    rows = Context.search([('code', 'in', list(_CLONE_CODES))])
    if 'source_module' in Context._fields:
        rows = rows.filtered(
            lambda r: (not r.source_module) or r.source_module == 'pns_ai_chatboo'
        )
    if rows:
        _logger.info(
            'pns_ai_chatboo 2.1.232: unlink cloned self locales %s',
            rows.mapped('code'),
        )
        rows.unlink()
    agent = env['ai.agent'].search([('code', '=', 'pns_ai_chatboo')], limit=1)
    if agent:
        try:
            agent._sync_composition_and_cache()
        except Exception:
            _logger.warning(
                'pns_ai_chatboo 2.1.232: agent cache sync failed',
                exc_info=True,
            )
