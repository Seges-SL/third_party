# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Open-Meteo geocode + purge poisoned miss cache + refresh geo context."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    # Drop miss/error rows that blocked retries under old Nominatim-only flow.
    try:
        cr.execute(
            "DELETE FROM ai_geo_place "
            "WHERE status IN ('miss', 'error') AND COALESCE(corrected, false) IS NOT TRUE"
        )
        _logger.info(
            'MCP 3.1.116: purged %s geo cache miss/error row(s)',
            cr.rowcount,
        )
    except Exception:
        _logger.warning(
            'MCP 3.1.116: geo cache purge skipped', exc_info=True,
        )

    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' in env:
        try:
            env['ai.context'].with_context(
                skip_hardcoded_restrictions=True,
            )._import_all_from_module(
                replace_existing=True,
                module_name='pns_ai_mcp',
                only_codes=['geo'],
            )
            _logger.info('MCP 3.1.116: geo context refreshed')
        except Exception:
            _logger.warning(
                'MCP 3.1.116: geo context refresh failed', exc_info=True,
            )
