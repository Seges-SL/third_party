# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Tab side of the temporary key PIN. The key list never lands in a field."""

import json

from odoo import http
from odoo.http import request


def _admin():
    user = request.env.user
    if user._is_superuser() or user.has_group('pns_ai_mcp.group_ai_admin'):
        return user
    return None


class KeyPinDeskController(http.Controller):

    @http.route('/pns_ai_mcp/key_pin/desk', type='json', auth='user')
    def key_pin_desk(self, token=None, **kwargs):
        user = _admin()
        if not user:
            return {'ok': False}
        return request.env['ai.key.pin.desk'].touch(token, user)

    @http.route('/pns_ai_mcp/key_pin/supply', type='json', auth='user')
    def key_pin_supply(self, ask_id=None, api_key=None, **kwargs):
        user = _admin()
        if not user:
            return {'ok': False}
        return request.env['ai.key.pin.ask'].supply(ask_id, api_key, user)

    @http.route(
        '/pns_ai_mcp/key_pin/stop', type='http', auth='user',
        methods=['POST'], csrf=False,
    )
    def key_pin_stop(self, **kwargs):
        user = _admin()
        if not user:
            return request.make_response('{}', headers=[('Content-Type', 'application/json')])
        token = kwargs.get('token') or ''
        if not token:
            raw = request.httprequest.get_data(as_text=True) or ''
            try:
                token = (json.loads(raw) or {}).get('token') or ''
            except (TypeError, ValueError):
                token = ''
        request.env['ai.key.pin.desk'].close(token)
        return request.make_response(
            '{"ok": true}',
            headers=[('Content-Type', 'application/json')],
        )
