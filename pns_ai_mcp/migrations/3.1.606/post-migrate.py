# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Refresh factory openapi_gen_prompt (crawl scope: one level, same host).

Odoo 14 does not run migrations/3.1.*; ai.api.server.init() also refreshes.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        n = env['ai.api.server']._fill_empty_openapi_gen_prompts()
    except Exception:
        _logger.warning(
            'pns_ai_mcp 3.1.606: openapi_gen_prompt refresh failed',
            exc_info=True,
        )
        return
    _logger.info(
        'pns_ai_mcp 3.1.606: refreshed openapi_gen_prompt on %s server(s)', n)
