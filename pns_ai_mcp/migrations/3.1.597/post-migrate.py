# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Fill empty openapi_gen_prompt with the factory English default."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        n = env['ai.api.server']._fill_empty_openapi_gen_prompts()
    except Exception:
        _logger.warning(
            'pns_ai_mcp 3.1.597: openapi_gen_prompt fill failed',
            exc_info=True,
        )
        return
    _logger.info(
        'pns_ai_mcp 3.1.597: filled openapi_gen_prompt on %s server(s)', n)
