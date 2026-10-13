# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.643: drop ORM-removed leftover columns (O14 uses ai.schema.fossil.init)."""
import logging

_logger = logging.getLogger(__name__)

_LEFTOVER_COLUMNS = (
    ('ai_log', 'operation_code'),
    ('ai_agent', 'auto_link_mcp_nucleus'),
    ('ai_context', 'is_shared'),
    ('ai_skill', 'is_shared'),
    ('ai_provider', 'cost_policy'),
)


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = %s
           AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if _column_exists(cr, 'ai_provider', 'cost_policy'):
        if _column_exists(cr, 'ai_provider', 'is_on_premise'):
            cr.execute(
                """
                UPDATE ai_provider
                   SET is_on_premise = true
                 WHERE cost_policy = 'free'
                   AND COALESCE(is_on_premise, false) = false
                """
            )
    for table, column in _LEFTOVER_COLUMNS:
        if not _column_exists(cr, table, column):
            continue
        cr.execute('ALTER TABLE "%s" DROP COLUMN "%s"' % (table, column))
        _logger.info('pns_ai_mcp 3.1.643: dropped %s.%s', table, column)
