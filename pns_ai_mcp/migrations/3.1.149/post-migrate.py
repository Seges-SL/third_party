# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""v3.1.149: drop AI Geo menus/actions/models after move to pns_geo."""
import logging

_logger = logging.getLogger(__name__)

_XMLIDS = (
    'pns_ai_mcp.menu_ai_geo',
    'pns_ai_mcp.menu_ai_geo_cache',
    'pns_ai_mcp.menu_ai_geo_route',
    'pns_ai_mcp.action_ai_geo_cache',
    'pns_ai_mcp.action_ai_geo_route',
    'pns_ai_mcp.action_geo_cache_tools_wizard',
    'pns_ai_mcp.action_import_geo_cache_wizard',
    'pns_ai_mcp.action_geocode_contacts_wizard',
    'pns_ai_mcp.action_server_export_geo_cache',
    'pns_ai_mcp.action_server_import_geo_cache',
)

_MODELS = (
    'ai.geo.place',
    'ai.geo.route',
    'ai.geo.map',
    'pns_ai_mcp.geo_cache.tools.wizard',
    'pns_ai_mcp.import_geo_cache_wizard',
    'pns_ai_mcp.geocode_contacts_wizard',
)


def migrate(cr, version):
    try:
        from odoo import api, SUPERUSER_ID
        env = api.Environment(cr, SUPERUSER_ID, {})
    except Exception:
        _logger.exception('3.1.149 geo purge: cannot build env')
        return

    for xid in _XMLIDS:
        try:
            rec = env.ref(xid, raise_if_not_found=False)
            if rec:
                rec.unlink()
        except Exception:
            _logger.info('3.1.149: skip unlink %s', xid, exc_info=True)

    IrModel = env['ir.model'].sudo()
    for name in _MODELS:
        try:
            model = IrModel.search([('model', '=', name)], limit=1)
            if model:
                model.unlink()
        except Exception:
            _logger.info('3.1.149: skip model %s', name, exc_info=True)