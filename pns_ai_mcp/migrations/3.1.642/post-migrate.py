# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.642: drop redundant ai.log.operation_code column."""
import logging

_logger = logging.getLogger(__name__)


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
    if not _column_exists(cr, 'ai_log', 'operation_code'):
        return
    cr.execute('ALTER TABLE "ai_log" DROP COLUMN "operation_code"')
    _logger.info('pns_ai_mcp 3.1.642: dropped ai_log.operation_code')
