# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""v3.1.142: regenerate route minimaps (road polyline when available).

Old thumbs drew a straight A→B line (OSM tiles / Google Static without
encoded geometry). Refresh display fields so new Static Maps use markers
only until the next live ``distance()`` stores a real polyline.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.geo.route' not in env:
        return
    Route = env['ai.geo.route'].sudo()
    rows = Route.search([])
    if not rows:
        return
    try:
        rows._enrich_display_fields()
        _logger.info(
            'MCP 3.1.142: refreshed route minimap for %s row(s)',
            len(rows),
        )
    except Exception:
        _logger.warning(
            'MCP 3.1.142: route minimap refresh skipped',
            exc_info=True,
        )
