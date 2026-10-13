# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.548: drop leftover pns_ai_mcp wizard tables before schema FK check.

Renaming TransientModels to ai.* leaves dirty Many2many rels (stale
wizard_id). Odoo retargets those FKs to the new table during init_models
and dies. Must run before the module update.
"""
import logging

_logger = logging.getLogger(__name__)


def _drop_table(cr, table):
    cr.execute('SELECT to_regclass(%s)', ('public.%s' % table,))
    if not cr.fetchone()[0]:
        return
    cr.execute('DROP TABLE IF EXISTS "%s" CASCADE' % table)
    _logger.info('pns_ai_mcp 3.1.548: dropped leftover table %s', table)


def migrate(cr, version):
    cr.execute(
        "SELECT tablename FROM pg_tables "
        "WHERE schemaname = 'public' AND tablename LIKE %s "
        "ORDER BY 1",
        ('%pns_ai_mcp%',),
    )
    leftovers = [row[0] for row in cr.fetchall()]
    for table in leftovers:
        try:
            _drop_table(cr, table)
        except Exception:
            _logger.info(
                '3.1.548: skip leftover table %s', table, exc_info=True,
            )

    try:
        cr.execute(
            "DELETE FROM ir_model_relation WHERE name LIKE %s",
            ('%pns_ai_mcp%',),
        )
    except Exception:
        _logger.info('3.1.548: skip ir_model_relation cleanup', exc_info=True)
