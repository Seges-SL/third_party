# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""v3.1.145: drop obsolete Entities menu group.

Children were reparented to Knowledge / Connections / Security.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    menu = env.ref('pns_ai_mcp.menu_ai_entities', raise_if_not_found=False)
    if not menu:
        return
    try:
        menu.unlink()
        _logger.info('MCP 3.1.145: removed obsolete menu_ai_entities')
    except Exception:
        _logger.warning(
            'MCP 3.1.145: could not unlink menu_ai_entities',
            exc_info=True,
        )
