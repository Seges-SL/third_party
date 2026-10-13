# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.547: drop leftover pns_ai_mcp.* wizard models and recipe fossils."""
import logging

_logger = logging.getLogger(__name__)

_OLD_MODELS = (
    'pns_ai_mcp.artifact_bundle.export.wizard',
    'pns_ai_mcp.artifact_bundle.import.wizard',
    'pns_ai_mcp.skill.capture.wizard',
    'pns_ai_mcp.log_delete_menu',
    'pns_ai_mcp.json_export_wizard',
    'pns_ai_mcp.agent.compose.wizard',
    'pns_ai_mcp.agent.compose.line',
    'pns_ai_mcp.api_key_wizard',
    'pns_ai_mcp.config_backup_wizard',
    'pns_ai_mcp.import_servers_wizard',
    'pns_ai_mcp.import_whitelist_wizard',
    'pns_ai_mcp.import_users_wizard',
    'pns_ai_mcp.import_external_servers_wizard',
    'pns_ai_mcp.import_agents_wizard',
    'pns_ai_mcp.context_import_wizard',
    'pns_ai_mcp.agent.context.import.wizard',
    'pns_ai_mcp.skill.import.wizard',
    'pns_ai_mcp.agent.skill.import.wizard',
    'pns_ai_mcp.agent.import.wizard',
    'pns_ai_mcp.bundle.compose.wizard',
    'pns_ai_mcp.agent.cache.rebuild.wizard',
    'pns_ai_mcp.provider.tools.wizard',
    'pns_ai_mcp.context.tools.wizard',
    'pns_ai_mcp.agent.tools.wizard',
    'pns_ai_mcp.user.tools.wizard',
    'pns_ai_mcp.whitelist.tools.wizard',
    'pns_ai_mcp.external_server.tools.wizard',
    'pns_ai_mcp.log.tools.wizard',
    'pns_ai_mcp.skill.tools.wizard',
    'pns_ai_mcp.context_stats_wizard',
    'ai.relaxaicode.recipe',
    'pns_ai_mcp.relaxaicode_library',
    'pns_ai_mcp.relaxaicode_raw_result',
)

_FOSSIL_TABLES = (
    'ai_relaxaicode_recipe',
    'pns_ai_mcp_relaxaicode_library',
    'pns_ai_mcp_relaxaicode_raw_result',
)


def _drop_table(cr, table):
    cr.execute(
        'SELECT to_regclass(%s)',
        ('public.%s' % table,),
    )
    if not cr.fetchone()[0]:
        return
    cr.execute('DROP TABLE IF EXISTS "%s" CASCADE' % table)
    _logger.info('pns_ai_mcp 3.1.547: dropped table %s', table)


def migrate(cr, version):
    try:
        from odoo import SUPERUSER_ID, api
        env = api.Environment(cr, SUPERUSER_ID, {})
    except Exception:
        _logger.exception('3.1.547 leftover: cannot build env')
        return

    IrModel = env['ir.model'].sudo()
    for name in _OLD_MODELS:
        try:
            model = IrModel.search([('model', '=', name)], limit=1)
            if model:
                model.unlink()
        except Exception:
            _logger.info('3.1.547: skip model %s', name, exc_info=True)

    for table in _FOSSIL_TABLES:
        try:
            _drop_table(cr, table)
        except Exception:
            _logger.info('3.1.547: skip table %s', table, exc_info=True)

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
            _logger.info('3.1.547: skip leftover %s', table, exc_info=True)
