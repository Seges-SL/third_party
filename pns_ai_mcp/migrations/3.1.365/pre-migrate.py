# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.365: hub tokens translation→locale, discover→discovery.

Rewrites rows and columns once. After this, the ORM does not understand
the old names (no runtime aliases).
"""
import logging

_logger = logging.getLogger(__name__)

_FIELD_RENAMES = (
    ('discover_target_kind', 'discovery_target_kind'),
    ('discover_target', 'discovery_target'),
    ('discover_triggers', 'discovery_triggers'),
    ('discover_priority', 'discovery_priority'),
    ('discover_soft_depends', 'discovery_soft_depends'),
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
        _logger.info('MCP 3.1.365: %s.%s → %s', table, old, new)
    elif _column_exists(cr, table, new):
        _logger.info('MCP 3.1.365: %s.%s already present', table, new)
    else:
        _logger.info(
            'MCP 3.1.365: %s.%s not found (fresh install?)', table, old,
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
    if not _table_exists(cr, 'ai_context'):
        _logger.info('MCP 3.1.365: ai_context missing (fresh install?)')
        return

    if _column_exists(cr, 'ai_context', 'context_type'):
        cr.execute(
            """
            UPDATE ai_context
               SET context_type = 'discovery'
             WHERE context_type = 'discover'
            """
        )
        cr.execute(
            """
            UPDATE ai_context
               SET context_type = 'locale'
             WHERE context_type = 'translation'
            """
        )
        _logger.info('MCP 3.1.365: context_type tokens rewritten')

    if _column_exists(cr, 'ai_context', 'code'):
        cr.execute(
            """
            UPDATE ai_context
               SET code = regexp_replace(code, '^disc_', 'discovery_')
             WHERE code LIKE 'disc_%'
            """
        )

    if _column_exists(cr, 'ai_context', 'rel_path'):
        cr.execute(
            """
            UPDATE ai_context
               SET rel_path = replace(rel_path, '/discover/', '/discovery/')
             WHERE rel_path LIKE '%/discover/%'
            """
        )
        cr.execute(
            """
            UPDATE ai_context
               SET rel_path = replace(rel_path, '/translation/', '/locale/')
             WHERE rel_path LIKE '%/translation/%'
            """
        )
        cr.execute(
            """
            UPDATE ai_context
               SET rel_path = replace(rel_path, '/disc_', '/discovery_')
             WHERE rel_path LIKE '%/disc_%'
            """
        )
        _logger.info('MCP 3.1.365: code/rel_path rewritten')

    for old, new in _FIELD_RENAMES:
        _rename_column(cr, 'ai_context', old, new)
        _rename_field_metadata(cr, 'ai.context', old, new)
