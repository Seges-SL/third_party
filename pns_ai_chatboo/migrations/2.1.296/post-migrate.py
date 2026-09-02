# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Unlink retired Chatboo system skills flota and payroll (files gone)."""
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
        _logger.info('pns_ai_chatboo 2.1.296: unlinked retired skills %s', codes)
