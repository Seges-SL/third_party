# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""v3.1.362: drop factory French discover row; spoken locale is es_ES only."""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

_ORPHAN_CODE = 'disc_geo_fr_FR'


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    Context = env['ai.context'].with_context(
        skip_hardcoded_restrictions=True,
        active_test=False,
    )
    rows = Context.search([('code', '=', _ORPHAN_CODE)])
    if 'source_module' in Context._fields:
        rows = rows.filtered(
            lambda r: (not r.source_module) or r.source_module == 'pns_ai_mcp'
        )
    if rows:
        _logger.info(
            'pns_ai_mcp 3.1.362: unlink orphan discover %s',
            rows.mapped('code'),
        )
        rows.unlink()
