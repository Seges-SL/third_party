# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Helper functions for the MCP controller."""

import logging
from odoo import SUPERUSER_ID
from odoo.http import request
from odoo.tools import misc
from odoo.tools.safe_eval import safe_eval
from .utils import MCPJSONRPCError

_logger = logging.getLogger(__name__)

GROUP_AI_WRITER = 'pns_ai_mcp.group_ai_writer'
GROUP_AI_EXTERNAL_URL = 'pns_ai_mcp.group_ai_external_url'
GROUP_AI_EXTERNAL_API = 'pns_ai_mcp.group_ai_external_api'

# 'action' (trusted action): requires the same baseline AI Writer group as
# CRUD; the action's OWN required groups are checked at propose
# (validate_safe_plan) and again in execute_safe_plan before apply.
CRUD_SAFE_OPS = frozenset({
    'create', 'write', 'copy', 'unlink', 'action', 'field_required',
})


def get_mcp_user_record():
    """
    Obtiene el registro ai.mcp.user asociado al usuario actual de la petición
    
    Returns:
        ai.mcp.user recordset o None si no existe
    """
    if not hasattr(request, 'mcp_user_id') or not request.mcp_user_id:
        return None
    
    try:
        # Usar SUPERUSER_ID solo para buscar el registro (no para operaciones)
        env_temp = request.env(user=SUPERUSER_ID)
        if 'ai.mcp.user' not in env_temp:
            return None
        mcp_user_record = env_temp['ai.mcp.user'].search([
            ('user_id', '=', request.mcp_user_id)
        ], limit=1)
        return mcp_user_record if mcp_user_record else None
    except Exception:
        return None


def get_mcp_odoo_user():
    """
    Usuario Odoo de la petición MCP autenticada por API key.

    No usar request.env.user: en peticiones HTTP sin sesión web puede ser
    res.users() vacío (p.ej. Odoo 19 según configuración de BD), aunque
    request.mcp_user / request.mcp_user_id estén correctamente asignados.
    """
    user = getattr(request, 'mcp_user', None)
    if user and user.id:
        return user
    mcp_user_id = getattr(request, 'mcp_user_id', None)
    if mcp_user_id:
        try:
            user = request.env(user=SUPERUSER_ID)['res.users'].browse(mcp_user_id)
            if user.exists():
                return user
        except Exception:
            pass
    if request.env.user and request.env.user.id:
        return request.env.user
    return request.env['res.users']


def mcp_user_has_group(group_xml_id):
    """Comprueba pertenencia a grupo sobre el usuario MCP autenticado."""
    user = get_mcp_odoo_user()
    if not user or not user.id:
        return False
    return user.has_group(group_xml_id)


def check_safe_plan_permissions(steps, user=None):
    """Check orthogonal AI permissions required by each safe-plan step.

    Returns:
        tuple: (has_permission, error_message)
    """
    user = user or get_mcp_odoo_user()
    if not user or not user.id:
        return False, 'No authenticated MCP user for permission check.'

    needs_writer = needs_url = needs_api = False
    for step in steps or []:
        op = (step or {}).get('op')
        if op in CRUD_SAFE_OPS:
            needs_writer = True
        elif op == 'fetch_url':
            needs_url = True
        elif op in ('api_call', 'mcp_call'):  # mcp_call = legacy alias
            needs_api = True

    if needs_writer and not user.has_group(GROUP_AI_WRITER):
        return False, (
            'Write permission denied: propose_safe_operations includes CRUD steps '
            'but the user is not in the AI Writer group.'
        )
    if needs_url and not user.has_group(GROUP_AI_EXTERNAL_URL):
        return False, (
            'External URL permission denied: propose_safe_operations includes '
            'fetch_url steps but the user is not in the AI External URL group.'
        )
    if needs_api and not user.has_group(GROUP_AI_EXTERNAL_API):
        return False, (
            'External API permission denied: propose_safe_operations includes '
            'api_call steps but the user is not in the AI External API group.'
        )
    return True, None


def check_mcp_permissions(controller, operation_type='read'):
    """
    Check AI permissions for the current user.

    - Read: always allowed (implicit user via API key).
    - Write: requires group_ai_writer (or group_ai_admin, which implies it).

    Returns:
        tuple: (has_permission, error_message)
    """
    if operation_type == 'read':
        return True, None

    if operation_type == 'write':
        if not mcp_user_has_group(GROUP_AI_WRITER):
            return False, 'Write permission denied: user is not in the AI Writer group.'
        return True, None

    return True, None


def get_env_for_operation(controller, operation_type='read'):
    """
    Obtiene el entorno Odoo apropiado según el tipo de operación
    
    Args:
        controller: Instancia del controlador
        operation_type: 'read' o 'write'
    
    Returns:
        env: Entorno Odoo con el usuario apropiado
    
    Raises:
        MCPJSONRPCError: Si no tiene permisos para la operación
    """
    # Verificar permisos antes de crear el entorno
    has_permission, error_message = check_mcp_permissions(controller, operation_type)
    if not has_permission:
        request_id = None
        if hasattr(request, 'jsonrequest') and request.jsonrequest:
            request_id = request.jsonrequest.get('id')
        raise MCPJSONRPCError(-32000, error_message, request_id)
    
    # Usar el usuario real (Odoo validará permisos automáticamente)
    return request.env(user=request.mcp_user_id)


def tool_env(controller, sudo=False):
    """
    Entorno Odoo para tools invocadas vía HTTP MCP o AgentEngine (chatboo/SSE).

    No usar request.env aquí: dentro del generador SSE de chatboo request no está
    ligado y get_context (y similares) fallan con «object is not bound».
    """
    env = controller._get_env_for_operation('read')
    if not sudo:
        return env
    # api.Environment no tiene .sudo() en Odoo 14–18; elevar con su=True (__call__).
    try:
        return env.sudo()
    except AttributeError:
        return env(su=True)


def get_readonly_env(controller):
    """
    Devuelve (env, cr) sobre un cursor aislado: la "caja A".

    Las lecturas pueden provocar escrituras colaterales del ORM (mail, tracking,
    métodos de negocio). El cursor se revierte siempre al cerrar (rollback), así
    que nada persiste en BD. Las escrituras intencionales (.create/.write/.unlink)
    las bloquea el AST y deben ir por la caja B (propose_safe_operations).

    Además se marca la transacción PostgreSQL como READ ONLY: si el AST falla
    (p. ej. confirm_by_user), el write aborta al instante en vez de tomar locks
    de fila que dejan el toast de confirmación humana en spinner infinito.

    Si no se puede activar READ ONLY, se falla cerrado (no se ejecuta caja A).

    El llamador DEBE cerrar el cursor (rollback + close) al terminar; el resultado
    debe haberse serializado a datos planos antes de cerrarlo.
    """
    from odoo import api
    from odoo.exceptions import UserError
    base_env = controller._get_env_for_operation('read')
    cr = base_env.registry.cursor()
    try:
        # Debe ser la primera sentencia útil de la transacción.
        cr.execute('SET TRANSACTION READ ONLY')
    except Exception as exc:
        try:
            cr.rollback()
        except Exception:
            pass
        try:
            cr.close()
        except Exception:
            pass
        _logger.error(
            'MCP: caja A abortada — no se pudo marcar cursor READ ONLY: %s', exc,
        )
        raise UserError(
            'Relaxaicode sandbox unavailable: cannot open a READ ONLY database '
            'transaction. Retry later or contact an administrator.'
        )
    env = api.Environment(cr, base_env.uid, {
        **dict(base_env.context or {}),
        'tracking_disable': True,
        'mail_notrack': True,
        'mail_create_nosubscribe': True,
        'mail_auto_subscribe_no_notify': True,
    })
    # Defensa en profundidad: si el ORM llama cr.commit() a mitad de un write
    # ofuscado, el rollback final ya no puede deshacer. Neutralizar commit.
    _real_commit = cr.commit

    def _caja_a_commit_blocked(*_a, **_kw):
        _logger.warning(
            'MCP: caja A ignoró cr.commit() (sandbox no persiste escrituras)'
        )
        return None

    try:
        cr.commit = _caja_a_commit_blocked  # type: ignore[method-assign]
    except Exception:
        # Cursor C-level u otro binding: no se puede reasignar; READ ONLY basta.
        _logger.debug('MCP: no se pudo monkey-patch cr.commit en caja A', exc_info=True)
        del _real_commit  # unused when patch fails
    else:
        # Mantener referencia para evitar GC del bound method original en algunos
        # intérpretes; no se invoca nunca desde caja A.
        cr._pns_caja_a_real_commit = _real_commit  # type: ignore[attr-defined]
    return env, cr


def load_module_manifest(controller, module_name):
    """Lee el manifest de un módulo de forma compatible con versiones anteriores de Odoo"""
    manifest_files = ('__manifest__.py', '__openerp__.py')
    for manifest_file in manifest_files:
        manifest_path = f"{module_name}/{manifest_file}"
        try:
            with misc.file_open(manifest_path, 'rb') as manifest_file_obj:
                manifest_content = manifest_file_obj.read().decode('utf-8')
            manifest_dict = safe_eval(manifest_content, {'__builtins__': {}})
            if isinstance(manifest_dict, dict):
                return manifest_dict
        except FileNotFoundError:
            continue
        except Exception as manifest_error:
            _logger.warning("MCP: Error leyendo manifest %s: %s", manifest_path, manifest_error)
            break
    return {}

