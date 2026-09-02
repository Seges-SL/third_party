# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.448: unlink factory discovery rows whose JSON file is gone (fr_FR)."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    Context = env['ai.context']
    if hasattr(Context, '_unlink_retired_factory_discovery'):
        n = Context._unlink_retired_factory_discovery()
        _logger.info('pns_ai_mcp 3.1.448: retired factory discovery=%s', n)
