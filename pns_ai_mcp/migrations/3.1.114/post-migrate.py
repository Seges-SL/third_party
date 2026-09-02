# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Reimport skills (sesame-geo __return_direct__ fix)."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.skill' not in env:
        return
    try:
        stats = env['ai.skill'].with_context(
            skip_hardcoded_restrictions=True,
        ).import_from_files()
        _logger.info('MCP 3.1.114: skills reimported (%s)', stats)
    except Exception:
        _logger.warning(
            'MCP 3.1.114: skill import failed', exc_info=True,
        )
