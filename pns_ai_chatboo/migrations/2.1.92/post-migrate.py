# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""v2.1.92: re-siembra skills de módulo (p. ej. cuadro-mando) tras -u."""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.skill' not in env:
        return
    Skill = env['ai.skill'].with_context(skip_hardcoded_restrictions=True)
    stats = Skill.import_from_files(replace_existing=True)
    errors = stats.get('errors') or []
    if errors:
        _logger.warning(
            'pns_ai_chatboo 2.1.92: skill import warnings: %s', errors,
        )
    agent = env['ai.agent'].search([('code', '=', 'pns_ai_chatboo')], limit=1)
    if not agent:
        return
    codes = Skill.default_skill_codes_for_agent('pns_ai_chatboo')
    if not codes:
        return
    default_sk = Skill.search([
        ('code', 'in', list(codes)), ('active', '=', True),
    ])
    agent.write({'skill_ids': [(6, 0, default_sk.ids)]})
