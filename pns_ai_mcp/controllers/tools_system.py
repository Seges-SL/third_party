# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""MCP tools for system maintenance."""

import json
import logging
from .mcp_decorators import mcp_tool
from ..utils.mcp_tool_payload import mark_terminal_resource
from ..utils.mcp_resources import (
    context_pack_use_get_context_error,
    is_context_pack_uri,
    is_whitelist_uri,
    normalize_resource_uri,
    unknown_resource_error,
    whitelist_facts,
)
from ..utils.system_info import system_info_facts


_logger = logging.getLogger(__name__)


def _system_uri_result(controller, uri, facts, summary):
    """Sobre MCP de un recurso ``system://``: hechos + entrega directa."""
    payload = mark_terminal_resource(facts)
    result = {
        'content': [{
            'type': 'text',
            'text': json.dumps(payload, indent=2, default=str),
        }]
    }
    controller._log_mcp_operation(
        'read', 'fetch_native_mcp_resource', {'uri': uri}, result,
        result_summary=summary,
    )
    return result


@mcp_tool(
    name='clean_system',
    description='Limpia acciones MCP huérfanas (solo aquellas sin menús, sin filtros asociados y que no sean wizards).',
    is_write=True,
    validate_schema=False  # No tiene parámetros, no necesita validación
)
def tool_clean_system(controller, arguments):
    """
    Tool: Limpia acciones MCP huérfanas sin menús ni filtros asociados.
    """
    try:
        env = controller._get_env_for_operation('write')
        actions_model = env['ir.actions.act_window']
        menus_model = env['ir.ui.menu']
        filters_model = env['ir.filters']
        model_data = env['ir.model.data']

        actions = actions_model.search([])
        mcp_actions = []
        mcp_action_ids = set()

        xml_map = {}
        xml_records = model_data.search([
            ('model', '=', 'ir.actions.act_window'),
            ('module', '=', 'pns_ai_mcp')
        ])
        idx = 0
        while idx < len(xml_records):
            xml_record = xml_records[idx]
            if xml_record.res_id:
                xml_map[xml_record.res_id] = f"{xml_record.module}.{xml_record.name}"
            idx += 1

        i = 0
        while i < len(actions):
            action = actions[i]
            if (action.res_model or '').startswith('pns_ai_mcp.'):
                mcp_actions.append(action)
                mcp_action_ids.add(action.id)
            i += 1

        menus = menus_model.search([('action', '!=', False)])
        menu_action_ids = set()
        i = 0
        while i < len(menus):
            menu = menus[i]
            action_ref = menu.action or ''
            if ',' in action_ref:
                parts = action_ref.split(',')
                if len(parts) == 2:
                    try:
                        action_id = int(parts[1])
                        menu_action_ids.add(action_id)
                    except Exception:
                        pass
            i += 1

        filters = filters_model.search([('action_id', '!=', False)])
        filter_action_ids = set()
        i = 0
        while i < len(filters):
            filtro = filters[i]
            if filtro.action_id:
                filter_action_ids.add(filtro.action_id.id)
            i += 1

        orphan_action_ids = []
        orphan_details = []
        i = 0
        while i < len(mcp_actions):
            action = mcp_actions[i]
            if action.id in menu_action_ids or action.id in filter_action_ids:
                i += 1
                continue
            if action.target == 'new' or action.id in xml_map:
                i += 1
                continue

            orphan_action_ids.append(action.id)
            orphan_details.append({
                'id': action.id,
                'name': action.name or 'Sin nombre',
                'res_model': action.res_model or '',
                'target': action.target or '',
                'xml_id': xml_map.get(action.id)
            })
            i += 1

        deleted_count = 0
        if orphan_action_ids:
            actions_model.browse(orphan_action_ids).unlink()
            deleted_count = len(orphan_action_ids)

        result = {
            'deleted_actions': deleted_count,
            'deleted_actions_details': orphan_details,
            'menu_action_count': len(menu_action_ids),
            'filter_action_count': len(filter_action_ids),
            'total_mcp_actions': len(mcp_actions),
            'skipped_actions_with_xml_id': len(xml_map)
        }

        return {
            'content': [
                {
                    'type': 'text',
                    'text': json.dumps(result, indent=2, default=str)
                }
            ]
        }
    except Exception as e:
        _logger.exception("MCP: Error ejecutando limpieza del sistema")
        return {
            'error': {
                'code': -32603,
                'message': f'Error cleaning system: {str(e)}'
            }
        }


@mcp_tool(
    name='fetch_native_mcp_resource',
    description=(
        'Read an MCP resource by URI (system://version, system://info, '
        'system://locale, url_whitelist). Use only when the user asks for '
        'those facts, or to inspect the URL whitelist before fetch_url. '
        'Do not use this tool to describe an on-screen image, icon, or '
        'chat artifact. Do not write Python to fetch system info.'
    ),
    is_write=False,
    validate_schema=True,
    input_schema={
        "type": "object",
        "properties": {
            "uri": {
                "type": "string",
                "description": "The URI of the resource to read."
            }
        },
        "required": ["uri"]
    }
)
def tool_fetch_native_mcp_resource(controller, arguments):
    """
    Tool: Reads an MCP resource.
    Supports system:// URIs and url_whitelist. Unknown URIs return
    not-found (no stored-resource table).
    """
    try:
        uri = normalize_resource_uri(arguments.get('uri'))
        if not uri:
            return {'error': {'code': -32602, 'message': 'Missing uri parameter'}}

        # 1. System Resources (Hardcoded for performance/safety)
        if uri == 'system://info':
            env = None
            try:
                env = controller._get_env_for_operation('read')
            except Exception:
                env = None
            info = system_info_facts(env)
            return _system_uri_result(
                controller, uri, info, 'Read System Info',
            )

        if uri == 'system://version':
            import odoo.release
            info = {
                'version': odoo.release.serie,
                'full_version': odoo.release.version,
                'serie': odoo.release.serie
            }
            return _system_uri_result(
                controller, uri, info, 'Read Version: %s' % info['version'],
            )
        
        if uri == 'system://locale':
            # Usa cascada de locale (ver docs/GESTION_LOCALE_Y_DISCRIMINACION_PAIS.md)
            if hasattr(controller, '_get_user_locale'):
                lang = controller._get_user_locale()
            else:
                # Fallback: Chatboo/LocalMCPClient sin _get_user_locale
                try:
                    from odoo.http import request
                    lang = (request.env.context.get('lang') or
                            (request.env.user.lang if request.env.user else None) or
                            'en_US')
                except Exception:
                    lang = 'en_US'
            return _system_uri_result(
                controller, uri, {'locale': lang}, 'Read Locale: %s' % lang,
            )

        if is_whitelist_uri(uri):
            env = controller._get_env_for_operation('read')
            facts = whitelist_facts(env)
            result = {
                'content': [{
                    'type': 'text',
                    'text': json.dumps(facts, indent=2, default=str),
                }]
            }
            controller._log_mcp_operation(
                'read', 'fetch_native_mcp_resource', {'uri': uri}, result,
                result_summary='Read URL whitelist (%s)' % facts.get('count', 0),
            )
            return result

        if is_context_pack_uri(uri):
            return context_pack_use_get_context_error(uri)

        # Optional: model schema (never KeyError on a missing model).
        if uri.startswith('odoo://models/'):
            env = controller._get_env_for_operation('read')
            model_name = uri.replace('odoo://models/', '')
            if model_name in env:
                model = env[model_name]
                fields_info = model.fields_get()
                clean_fields = {
                    k: {'type': v['type'], 'string': v['string']}
                    for k, v in fields_info.items()
                }
                result = {
                    'content': [{
                        'type': 'text',
                        'text': json.dumps(
                            {'model': model_name, 'fields': clean_fields},
                            indent=2, default=str,
                        ),
                    }]
                }
                controller._log_mcp_operation(
                    'read', 'fetch_native_mcp_resource', {'uri': uri}, result,
                    result_summary='Read Model Schema: %s' % model_name,
                )
                return result

        return unknown_resource_error(uri)

    except Exception as e:
        _logger.exception(f"MCP: Error reading resource {arguments.get('uri')}")
        return {'error': {'code': -32603, 'message': str(e)}}


# REMOVED: list_resources tool - Resources are automatically injected into system message by AgentOrchestrator
# The LLM should NOT call this tool - resources are already available in the system message
# Keeping this tool causes confusion and infinite loops
# @mcp_tool(
#     name='list_resources',
#     description='List available MCP resources (system and database).',
#     is_write=False,
#     validate_schema=False
# )
# def tool_list_resources(controller, arguments):
#     """REMOVED - Resources are auto-injected in system message"""
