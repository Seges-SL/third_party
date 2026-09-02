# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Replace cost_policy with is_on_premise (no vendor-name heuristics).

If a DB already has ``cost_policy='free'`` from 3.1.290, map those rows to
``is_on_premise=True``. New installs only get the boolean (default False);
operators mark own-server gateways themselves.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.provider' not in env:
        return
    Provider = env['ai.provider'].sudo()
    if 'is_on_premise' not in Provider._fields:
        return

    # Carry over any rows that briefly had cost_policy=free.
    try:
        cr.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'ai_provider' AND column_name = 'cost_policy'
            LIMIT 1
            """
        )
        if cr.fetchone():
            cr.execute(
                """
                UPDATE ai_provider
                   SET is_on_premise = true
                 WHERE cost_policy = 'free'
                   AND COALESCE(is_on_premise, false) = false
                """
            )
            n = cr.rowcount
            if n:
                _logger.info(
                    'MCP 3.1.291: mapped cost_policy=free → is_on_premise (%s)',
                    n,
                )
            cr.execute('ALTER TABLE ai_provider DROP COLUMN IF EXISTS cost_policy')
    except Exception:
        _logger.warning(
            'MCP 3.1.291: cost_policy → is_on_premise migrate failed',
            exc_info=True,
        )
