# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""v2.1.134: help/? as deterministic HTML for financial report skills."""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.skill' not in env:
        return
    Skill = env['ai.skill'].with_context(
        skip_hardcoded_restrictions=True,
        active_test=False,
    )
    stats = Skill.import_from_files(replace_existing=True)
    errors = stats.get('errors') or []
    if errors:
        _logger.warning(
            'pns_ai_chatboo 2.1.134: skill import warnings: %s', errors,
        )
    else:
        _logger.info('pns_ai_chatboo 2.1.134: skills import %s', stats)
