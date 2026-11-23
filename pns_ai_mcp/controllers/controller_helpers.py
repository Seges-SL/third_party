# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Helper functions for the MCP controller."""

import logging
from odoo import SUPERUSER_ID
from odoo.http import request
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

def get_mcp_odoo_user():
    """
    Odoo user of the MCP request authenticated by API key.

    Do not use request.env.user: in HTTP requests without a web session it can be
    an empty res.users() (e.g. Odoo 19 depending on DB setup), even when
    request.mcp_user / request.mcp_user_id are set correctly.
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
    """Check group membership of the authenticated MCP user."""
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
            'Write permission denied: safe_plan_request includes CRUD steps '
            'but the user is not in the AI Writer group.'
        )
    if needs_url and not user.has_group(GROUP_AI_EXTERNAL_URL):
        return False, (
            'External URL permission denied: safe_plan_request includes '
            'fetch_url steps but the user is not in the AI External URL group.'
        )
    if needs_api and not user.has_group(GROUP_AI_EXTERNAL_API):
        return False, (
            'External API permission denied: safe_plan_request includes '
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
    Get the right Odoo env for the operation type
    
    Args:
        controller: Controller instance
        operation_type: 'read' or 'write'
    
    Returns:
        env: Odoo env with the right user
    
    Raises:
        MCPJSONRPCError: If the user lacks permission for the operation
    """
    # Check permissions before building the env
    has_permission, error_message = check_mcp_permissions(controller, operation_type)
    if not has_permission:
        request_id = None
        if hasattr(request, 'jsonrequest') and request.jsonrequest:
            request_id = request.jsonrequest.get('id')
        raise MCPJSONRPCError(-32000, error_message, request_id)
    
    # Use the real user (Odoo checks permissions on its own)
    return request.env(user=request.mcp_user_id)


def tool_env(controller, sudo=False):
    """
    Odoo env for tools called through HTTP MCP or AgentEngine (host/SSE).

    Do not use request.env here: inside the host SSE generator, request is not
    bound and get_context (and the like) fail with «object is not bound».
    """
    env = controller._get_env_for_operation('read')
    if not sudo:
        return env
    # api.Environment has no .sudo() in Odoo 14–18; elevate with su=True (__call__).
    try:
        return env.sudo()
    except AttributeError:
        return env(su=True)


def get_readonly_env(controller):
    """
    Return (env, cr) on an isolated cursor: "box A".

    Reads can trigger side-effect ORM writes (mail, tracking, business
    methods). The cursor is always rolled back on close, so nothing
    persists in the DB. Intentional writes (.create/.write/.unlink)
    are blocked by the AST and must go through box B (safe_plan_request).

    The PostgreSQL transaction is also marked READ ONLY: if the AST misses one
    (e.g. confirm_by_user), the write aborts at once instead of taking row
    locks that leave the human confirmation toast spinning forever.

    If READ ONLY cannot be set, it fails closed (box A does not run).

    The caller MUST close the cursor (rollback + close) when done; the result
    must be serialized to plain data before closing it.
    """
    return open_readonly_env(controller._get_env_for_operation('read'))


def open_readonly_env(base_env):
    """Box A on its own cursor, as the user and with the context of ``base_env``.

    Same contract as ``get_readonly_env``: the caller rolls back and closes it.
    """
    from odoo import api
    from odoo.exceptions import UserError
    from ..utils.sandbox_secrets import SANDBOX_CURSOR_FLAG
    from ..utils.one_company import one_company_context
    context = one_company_context(base_env)
    cr = base_env.registry.cursor()
    try:
        # Must be the first real statement of the transaction.
        cr.execute('SET TRANSACTION READ ONLY')
        # Without the flag, secret columns would be readable (models/sandbox_secret_read.py).
        setattr(cr, SANDBOX_CURSOR_FLAG, True)
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
            'MCP: box A aborted — could not mark cursor READ ONLY: %s', exc,
        )
        raise UserError(
            'Relaxaicode sandbox unavailable: cannot open a READ ONLY database '
            'transaction. Retry later or contact an administrator.'
        )
    env = api.Environment(cr, base_env.uid, {
        **context,
        'tracking_disable': True,
        'mail_notrack': True,
        'mail_create_nosubscribe': True,
        'mail_auto_subscribe_no_notify': True,
    })
    # Defence in depth: if the ORM calls cr.commit() halfway through an obfuscated
    # write, the final rollback can no longer undo it. Neutralize commit.
    _real_commit = cr.commit

    def _caja_a_commit_blocked(*_a, **_kw):
        _logger.warning(
            'MCP: box A ignored cr.commit() (the sandbox does not persist writes)'
        )
        return None

    try:
        cr.commit = _caja_a_commit_blocked  # type: ignore[method-assign]
    except Exception:
        # C-level cursor or another binding: cannot be reassigned; READ ONLY is enough.
        _logger.debug('MCP: could not monkey-patch cr.commit in box A', exc_info=True)
        del _real_commit  # unused when patch fails
    else:
        # Keep a reference to avoid GC of the original bound method on some
        # interpreters; it is never called from box A.
        cr._pns_caja_a_real_commit = _real_commit  # type: ignore[attr-defined]
    return env, cr
