# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.449: archive leftover slashes that duplicate a prefixed factory command."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.skill' not in env:
        return
    Skill = env['ai.skill']
    if hasattr(Skill, 'hide_unprefixed_slash_twins'):
        n = Skill.hide_unprefixed_slash_twins()
        _logger.info('pns_ai_mcp 3.1.449: hid unprefixed slash twins=%s', n)
