# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.451: drop discovery leftovers with a spoken locale other than es_ES."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    Context = env['ai.context']
    if hasattr(Context, '_unlink_retired_factory_discovery'):
        retired = Context._unlink_retired_factory_discovery()
        _logger.info('pns_ai_mcp 3.1.451: retired factory discovery=%s', retired)
    if hasattr(Context, '_unlink_non_es_locale_discovery'):
        n = Context._unlink_non_es_locale_discovery()
        _logger.info('pns_ai_mcp 3.1.451: non-es_ES discovery leftovers=%s', n)
