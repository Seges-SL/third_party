# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Reimport skills + geo pin colors (sesame-geo in/out)."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.skill' in env:
        try:
            stats = env['ai.skill'].with_context(
                skip_hardcoded_restrictions=True,
            ).import_from_files()
            _logger.info('MCP 3.1.115: skills reimported (%s)', stats)
        except Exception:
            _logger.warning(
                'MCP 3.1.115: skill import failed', exc_info=True,
            )
    if 'ai.context' in env:
        try:
            env['ai.context'].with_context(
                skip_hardcoded_restrictions=True,
            )._import_all_from_module(
                replace_existing=True,
                module_name='pns_ai_mcp',
                only_codes=['geo'],
            )
        except Exception:
            _logger.warning(
                'MCP 3.1.115: geo context refresh failed', exc_info=True,
            )
