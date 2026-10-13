# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.555: drop leftover pns_* bundle rels and recipe after schema."""
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


def migrate(cr, version):
    for table in _NAMED_TABLES:
        cr.execute('DROP TABLE IF EXISTS "%s" CASCADE' % table)
        _logger.info('pns_ai_mcp 3.1.555-post: DROP %s', table)

    cr.execute(
        "SELECT tablename FROM pg_tables "
        "WHERE schemaname = 'public' "
        "AND (tablename LIKE %s OR tablename LIKE %s) "
        "ORDER BY 1",
        ('%pns_ai_mcp%rel%', 'pns_ai_mcp_relaxaicode%'),
    )
    for (table,) in cr.fetchall():
        cr.execute('DROP TABLE IF EXISTS "%s" CASCADE' % table)
        _logger.info('pns_ai_mcp 3.1.555-post: DROP leftover %s', table)

    cr.execute(
        "DELETE FROM ir_model_relation WHERE name LIKE %s",
        ('%pns_ai_mcp%',),
    )
