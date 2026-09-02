# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Unlink retired Chatboo skills and re-seed this addon's pack from disk."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_RETIRED = ('flota', 'payroll')
_RETIRED_PATHS = (
    'skills/system/flota.md',
    'skills/system/payroll.md',
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.skill' not in env:
        return
    Skill = env['ai.skill'].sudo().with_context(
        active_test=False,
        skip_hardcoded_restrictions=True,
    )
    rows = Skill.search([
        '|', '|',
        ('command', 'in', _RETIRED),
        ('code', 'in', _RETIRED),
        ('rel_path', 'in', _RETIRED_PATHS),
    ])
    if rows:
        codes = rows.mapped('code')
        rows.unlink()
        _logger.info(
            'pns_ai_chatboo 2.1.300: unlinked retired skills %s', codes,
        )
    if hasattr(Skill, 'import_from_module'):
        stats = Skill.import_from_module('pns_ai_chatboo')
        _logger.info('pns_ai_chatboo 2.1.300: skill seed %s', stats)
    else:
        _logger.warning(
            'pns_ai_chatboo 2.1.300: ai.skill.import_from_module missing; '
            'upgrade pns_ai_mcp first',
        )
