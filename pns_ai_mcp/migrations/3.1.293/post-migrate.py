# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Drop legacy domain_index_shadow ICP; ensure inject flag defaults ON."""
import logging

_logger = logging.getLogger(__name__)

INJECT_KEY = 'pns_ai_mcp.domain_index_inject'
LEGACY_SHADOW_KEY = 'pns_ai_mcp.domain_index_shadow'


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    ICP = env['ir.config_parameter'].sudo()
    try:
        ICP.set_param(INJECT_KEY, ICP.get_param(INJECT_KEY, 'True') or 'True')
        stale = ICP.search([('key', '=', LEGACY_SHADOW_KEY)])
        if stale:
            stale.unlink()
            _logger.info('MCP 3.1.293: removed legacy %s', LEGACY_SHADOW_KEY)
    except Exception:
        _logger.warning('MCP 3.1.293: domain_index ICP cleanup failed', exc_info=True)
