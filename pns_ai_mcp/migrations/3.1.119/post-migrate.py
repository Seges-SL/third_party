# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Geocode Google/OSM only (no Open-Meteo); soft notices; refresh geo context."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

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
            _logger.info('MCP 3.1.119: geo context refreshed')
        except Exception:
            _logger.warning(
                'MCP 3.1.119: geo context refresh failed', exc_info=True,
            )
