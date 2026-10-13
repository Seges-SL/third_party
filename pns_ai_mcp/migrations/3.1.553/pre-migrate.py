# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.553: drop leftover pns_* wizard rels before schema recreates them.

Odoo keeps ir.model.relation names after a TransientModel _name change.
Must run before init_models. Does not touch ai_safe_choice / ai_change_journal.
"""
import logging

_logger = logging.getLogger(__name__)

_NAMED_TABLES = (
    'ai_agent_pns_ai_mcp_artifact_bundle_export_wizard_rel',
    'ai_api_server_pns_ai_mcp_artifact_bundle_export_wizard_rel',
    'ai_context_pns_ai_mcp_artifact_bundle_export_wizard_rel',
    'ai_mcp_user_pns_ai_mcp_artifact_bundle_export_wizard_rel',
    'ai_provider_pns_ai_mcp_artifact_bundle_export_wizard_rel',
    'ai_skill_pns_ai_mcp_artifact_bundle_export_wizard_rel',
    'ai_url_whitelist_pns_ai_mcp_artifact_bundle_export_wizard_rel',
    'ai_relaxaicode_recipe',
    'pns_ai_mcp_relaxaicode_library',
    'pns_ai_mcp_relaxaicode_raw_result',
)


def _drop_table(cr, table):
    cr.execute('SELECT to_regclass(%s)', ('public.%s' % table,))
    if not cr.fetchone()[0]:
        return
    cr.execute('DROP TABLE IF EXISTS "%s" CASCADE' % table)
    _logger.info('pns_ai_mcp 3.1.553: dropped leftover table %s', table)


def migrate(cr, version):
    seen = set()
    for table in _NAMED_TABLES:
        try:
            _drop_table(cr, table)
            seen.add(table)
        except Exception:
            _logger.info('3.1.553: skip table %s', table, exc_info=True)

    cr.execute(
        "SELECT tablename FROM pg_tables "
        "WHERE schemaname = 'public' AND tablename LIKE %s "
        "ORDER BY 1",
        ('%pns_ai_mcp%',),
    )
    for (table,) in cr.fetchall():
        if table in seen:
            continue
        try:
            _drop_table(cr, table)
        except Exception:
            _logger.info('3.1.553: skip leftover %s', table, exc_info=True)

    try:
        cr.execute(
            "DELETE FROM ir_model_relation WHERE name LIKE %s",
            ('%pns_ai_mcp%',),
        )
    except Exception:
        _logger.info('3.1.553: skip ir_model_relation cleanup', exc_info=True)
