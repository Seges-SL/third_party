# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""v3.1.135: enrich distance cache places + route minimap for existing rows."""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.geo.route' not in env:
        return
    Cache = env['ai.geo.route'].sudo()
    rows = Cache.search([])
    if not rows:
        return
    try:
        rows._enrich_display_fields()
        _logger.info(
            'MCP 3.1.135: enriched %s distance cache row(s) (places + route map)',
            len(rows),
        )
    except Exception:
        _logger.warning(
            'MCP 3.1.135: distance cache enrich skipped',
            exc_info=True,
        )
