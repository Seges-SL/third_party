# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.239: skill catalog ids snake_case; slash stays kebab in command."""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.skill' not in env:
        return
    stats = env['ai.skill']._migrate_kebab_catalog_ids()
    _logger.info('pns_ai_mcp 3.1.239: kebab catalog split %s', stats)
