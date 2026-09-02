# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Drop leftover flota/payroll after the seed can see this addon's disk."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_RETIRED = ('flota', 'payroll')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.skill' not in env:
        return
    Skill = env['ai.skill'].sudo().with_context(
        active_test=False,
        skip_hardcoded_restrictions=True,
    )
    if hasattr(Skill, 'import_from_module'):
        stats = Skill.import_from_module('pns_ai_chatboo')
        _logger.info('pns_ai_chatboo 2.1.301: skill seed %s', stats)
    if hasattr(Skill, 'unlink_named_factory_skills'):
        n = Skill.unlink_named_factory_skills(list(_RETIRED))
        _logger.info(
            'pns_ai_chatboo 2.1.301: unlinked named leftovers %s', n,
        )
        return
    rows = Skill.search([
        '|',
        ('command', 'in', _RETIRED),
        ('code', 'in', _RETIRED),
    ])
    if rows:
        codes = rows.mapped('code')
        rows.unlink()
        _logger.info(
            'pns_ai_chatboo 2.1.301: unlinked retired skills %s', codes,
        )
