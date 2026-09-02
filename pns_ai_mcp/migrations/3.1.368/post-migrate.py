# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.368: show context_type tokens (O14 does not overwrite stale ir.translation)."""
import logging

_logger = logging.getLogger(__name__)

_TOKENS = (
    'core', 'domain', 'locale', 'discovery',
    'discover', 'translation',
)


def _table_exists(cr, table):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = %s
        """,
        (table,),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not _table_exists(cr, 'ir_translation'):
        _logger.info('pns_ai_mcp 3.1.368: no ir_translation; skip')
        return
    cr.execute(
        """
        UPDATE ir_translation
           SET value = src
         WHERE module = 'pns_ai_mcp'
           AND src IN %s
           AND value IS DISTINCT FROM src
           AND (
                type = 'selection'
             OR name ILIKE %s
             OR name ILIKE %s
           )
        """,
        (_TOKENS, '%context_type%', '%selection__ai_context__context_type%'),
    )
    cr.execute(
        """
        UPDATE ir_translation
           SET value = lower(src)
         WHERE module = 'pns_ai_mcp'
           AND type = 'selection'
           AND src IN ('Core', 'Domain', 'Locale', 'Discover', 'Discovery', 'Translation')
           AND value IS DISTINCT FROM lower(src)
        """,
    )
    _logger.info(
        'pns_ai_mcp 3.1.368: reset context_type selection translations (%s rows)',
        cr.rowcount,
    )
