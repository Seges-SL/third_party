# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""v3.1.325: ReAct loop is a round, not a user turn.

Renames:
  ai.agent.max_agent_turns → max_agent_rounds
  ai.agent.provider.llm_turn_timeout → llm_round_timeout

Runs before the ORM loads the new field names so custom values are kept
(Odoo would otherwise ADD the new column with the default and drop the old).
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
        _logger.info('MCP 3.1.325: %s.%s → %s', table, old, new)
    elif _column_exists(cr, table, new):
        _logger.info('MCP 3.1.325: %s.%s already present', table, new)
    else:
        _logger.info(
            'MCP 3.1.325: %s.%s not found (fresh install?)', table, old,
        )


def _rename_field_metadata(cr, model, old, new):
    """Keep ir.model.fields + xmlid in sync so Odoo does not recreate the field."""
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
    _rename_column(cr, 'ai_agent', 'max_agent_turns', 'max_agent_rounds')
    _rename_field_metadata(
        cr, 'ai.agent', 'max_agent_turns', 'max_agent_rounds',
    )
    _rename_column(
        cr, 'ai_agent_provider', 'llm_turn_timeout', 'llm_round_timeout',
    )
    _rename_field_metadata(
        cr, 'ai.agent.provider', 'llm_turn_timeout', 'llm_round_timeout',
    )
