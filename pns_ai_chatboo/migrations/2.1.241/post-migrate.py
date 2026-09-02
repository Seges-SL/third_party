# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v2.1.241: fill empty Chatboo Factory seed texts (noupdate XML never updates existing agents)."""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.agent' not in env:
        return
    env['ai.agent']._fill_empty_factory_seeds()
    _logger.info('pns_ai_chatboo 2.1.241: filled empty factory seeds')
