# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""v3.1.47: overwrite module .po into ir.translation (stale menu labels).

Plain ``-u`` updates English XML sources but keeps old Spanish values in
``ir.translation`` (e.g. menu still showing «Recetas RelaxiCode» while the
``.po`` already says «Recetas»). Force-reload catalogs on this upgrade.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    module = env['ir.module.module'].search(
        [('name', '=', 'pns_ai_mcp')], limit=1,
    )
    if not module:
        return
    try:
        module._update_translations(overwrite=True)
        _logger.info(
            'pns_ai_mcp 3.1.47: module translations reloaded (overwrite=True)',
        )
    except Exception:
        _logger.warning(
            'pns_ai_mcp 3.1.47: translation overwrite failed',
            exc_info=True,
        )
