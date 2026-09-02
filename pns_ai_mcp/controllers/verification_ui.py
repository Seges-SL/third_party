# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Session-bound confirmation endpoints for dangerous writes."""

import logging
from odoo import http
from odoo.http import request
from ..utils.compat import JSON_ROUTE_TYPE

_logger = logging.getLogger(__name__)


class MCPVerificationUI(http.Controller):

    def _get_owned_verification(self, verification_id):
        """Devuelve la verificación si la sesión puede resolverla, o (None, error).

        Puede resolverla el usuario que la solicitó O un administrador de MCP
        (group_ai_admin), que puede confirmar/cancelar las de otros usuarios.
        """
        if not verification_id:
            return None, 'missing_id'
        verification = request.env['ai.safe.operation'].sudo().search(
            [('verification_id', '=', verification_id)], limit=1
        )
        if not verification:
            return None, 'not_found'
        is_owner = verification.user_id.id == request.env.user.id
        is_manager = request.env.user.has_group('pns_ai_mcp.group_ai_admin')
        if not (is_owner or is_manager):
            _logger.warning(
                "MCP: usuario %s intentó confirmar/cancelar verificación %s de otro usuario %s",
                request.env.user.id, verification_id, verification.user_id.id
            )
            return None, 'forbidden'
        return verification, None

    @http.route('/pns_ai_mcp/verification/confirm', type=JSON_ROUTE_TYPE, auth='user')
    def confirm(self, verification_id=None, **kwargs):
        """Solo marca confirmed. Nunca ejecuta el plan (ver /execute)."""
        verification, error = self._get_owned_verification(verification_id)
        if error:
            return {'success': False, 'error': error}

        out = verification.resolve_confirm(confirmed_uid=request.env.user.id)
        if out.get('busy'):
            return {
                'success': False,
                'busy': True,
                'error': 'busy',
                'verification_id': verification_id,
            }
        return out

    @http.route('/pns_ai_mcp/verification/execute', type=JSON_ROUTE_TYPE, auth='user')
    def execute(self, verification_id=None, **kwargs):
        """Aplica el plan de una op ya confirmed. Timeouts; no cancela el confirm."""
        verification, error = self._get_owned_verification(verification_id)
        if error:
            return {'success': False, 'error': error}

        out = verification.resolve_execute(confirmed_uid=request.env.user.id)
        return out

    @http.route('/pns_ai_mcp/verification/cancel', type=JSON_ROUTE_TYPE, auth='user')
    def cancel(self, verification_id=None, **kwargs):
        verification, error = self._get_owned_verification(verification_id)
        if error:
            return {'success': False, 'error': error}
        if verification.status == 'cancelled':
            return {
                'success': True,
                'status': 'cancelled',
                'idempotent': True,
                'verification_id': verification_id,
            }
        if verification.executed or verification.status not in ('pending',):
            return {
                'success': False,
                'error': 'not_pending',
                'status': verification.status,
                'verification_id': verification_id,
            }
        try:
            verification.cancel_by_user(cancelled_uid=request.env.user.id)
        except Exception as e:
            return {'success': False, 'error': str(e)}
        from ..controllers.safe_plan import (
            attach_verification_chat_hints,
            build_verification_followup_message,
        )
        data = verification.get_operation_data() or {}
        title = data.get('title') or verification.display_name or ''
        steps = data.get('plan_steps') or []
        return attach_verification_chat_hints(
            {
                'success': True,
                'status': 'cancelled',
                'verification_id': verification_id,
                'followup_message': build_verification_followup_message(
                    title, action='cancel',
                ),
            },
            title, action='cancel', steps=steps,
        )

    @http.route('/pns_ai_mcp/verification/pending', type=JSON_ROUTE_TYPE, auth='user')
    def pending(self, **kwargs):
        """Read-only list of this user's pending cards (Security menu SoT)."""
        items = request.env['ai.safe.operation'].chatboo_pending_card_payloads()
        return {'success': True, 'items': items}
