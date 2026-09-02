# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""v3.1.146: rename menu Geography → Geo (loanword label).

XML already uses name=\"Geo\"; force-write existing DBs so stale ir.ui.menu
names (and ES translations Geografía) catch up after -u.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    menu = env.ref('pns_ai_mcp.menu_ai_geo', raise_if_not_found=False)
    if not menu or 'name' not in menu._fields:
        return
    menu.with_context(lang=False).write({'name': 'Geo'})
    for lang in ('es_ES', 'es'):
        try:
            menu.with_context(lang=lang).write({'name': 'Geo'})
        except Exception:
            pass
    _logger.info('MCP 3.1.146: menu_ai_geo label set to Geo')
