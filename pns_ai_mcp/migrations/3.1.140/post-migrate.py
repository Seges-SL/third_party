# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""v3.1.140: align menu/action labels (Geography/Places, Authorizations).

XML already uses the new English names; force-write on existing DBs so stale
ir.ui.menu / act_window names (and ES translations) catch up after -u.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# xmlid → (english source, spanish)
_LABELS = (
    ('pns_ai_mcp.menu_ai_geo', 'Geography', 'Geografía'),
    ('pns_ai_mcp.menu_ai_geo_cache', 'Places', 'Lugares'),
    ('pns_ai_mcp.action_ai_geo_cache', 'Places', 'Lugares'),
    ('pns_ai_mcp.menu_mcp_safe_operation_admin', 'Authorizations', 'Autorizaciones'),
    ('pns_ai_mcp.action_mcp_safe_operation_admin', 'Authorizations', 'Autorizaciones'),
    ('pns_ai_mcp.menu_mcp_safe_operation', 'My Authorizations', 'Mis Autorizaciones'),
    ('pns_ai_mcp.action_mcp_safe_operation', 'My Authorizations', 'Mis Autorizaciones'),
    ('pns_ai_mcp.action_geo_cache_tools_wizard', 'Places Tools', 'Herramientas de lugares'),
    ('pns_ai_mcp.action_import_geo_cache_wizard', 'Import Places (JSON)', 'Importar lugares (JSON)'),
    ('pns_ai_mcp.action_safe_operation_tools_wizard', 'Authorization Tools', 'Herramientas de autorizaciones'),
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    updated = 0
    for xmlid, en_name, es_name in _LABELS:
        rec = env.ref(xmlid, raise_if_not_found=False)
        if not rec or 'name' not in rec._fields:
            continue
        rec.with_context(lang=False).write({'name': en_name})
        for lang in ('es_ES', 'es'):
            try:
                rec.with_context(lang=lang).write({'name': es_name})
            except Exception:
                pass
        updated += 1
    _logger.info('MCP 3.1.140: refreshed %s menu/action label(s)', updated)
