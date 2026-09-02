# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Seed ICP slash-hidden codes from existing show_in_slash=False (3.1.297)."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.skill' not in env:
        return
    Skill = env['ai.skill']
    if not hasattr(Skill, 'sync_slash_hidden_from_field'):
        return
    try:
        added = Skill.sync_slash_hidden_from_field()
        Skill.search([])._apply_slash_hidden_from_icp()
        _logger.info(
            'MCP 3.1.297: synced skills_slash_hidden ICP (+%s codes)',
            added,
        )
    except Exception:
        _logger.exception('MCP 3.1.297: could not sync slash-hidden ICP')
