# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.636: Rename turn threading columns on ai.log, journal and safe operation.

correlation_id -> turn
step_seq -> turn_step (log + journal only)

Runs before the ORM loads the new field names so existing values are kept.
"""

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


def _rename_column(cr, table, old, new):
    if _column_exists(cr, table, old) and not _column_exists(cr, table, new):
        cr.execute(
            'ALTER TABLE "%s" RENAME COLUMN "%s" TO "%s"' % (table, old, new)
        )
        _logger.info('MCP 3.1.636: %s.%s -> %s', table, old, new)
    elif _column_exists(cr, table, new):
        _logger.info('MCP 3.1.636: %s.%s already present', table, new)
    else:
        _logger.info(
            'MCP 3.1.636: %s.%s not found (fresh install?)', table, old,
        )


def _rename_field_metadata(cr, model, old, new):
    cr.execute(
        """
        UPDATE ir_model_fields
           SET name = %s
         WHERE model = %s AND name = %s
        """,
        (new, model, old),
    )
    table = model.replace('.', '_')
    old_xmlid = 'field_%s__%s' % (table, old)
    new_xmlid = 'field_%s__%s' % (table, new)
    cr.execute(
        """
        UPDATE ir_model_data
           SET name = %s
         WHERE module = 'pns_ai_mcp'
           AND name = %s
           AND NOT EXISTS (
                SELECT 1 FROM ir_model_data d2
                 WHERE d2.module = 'pns_ai_mcp'
                   AND d2.name = %s
           )
        """,
        (new_xmlid, old_xmlid, new_xmlid),
    )


def migrate(cr, version):
    _rename_column(cr, 'ai_log', 'correlation_id', 'turn')
    _rename_field_metadata(cr, 'ai.log', 'correlation_id', 'turn')
    _rename_column(cr, 'ai_log', 'step_seq', 'turn_step')
    _rename_field_metadata(cr, 'ai.log', 'step_seq', 'turn_step')

    _rename_column(cr, 'ai_change_journal', 'correlation_id', 'turn')
    _rename_field_metadata(cr, 'ai.change.journal', 'correlation_id', 'turn')
    _rename_column(cr, 'ai_change_journal', 'step_seq', 'turn_step')
    _rename_field_metadata(cr, 'ai.change.journal', 'step_seq', 'turn_step')

    _rename_column(cr, 'ai_safe_operation', 'correlation_id', 'turn')
    _rename_field_metadata(cr, 'ai.safe.operation', 'correlation_id', 'turn')
