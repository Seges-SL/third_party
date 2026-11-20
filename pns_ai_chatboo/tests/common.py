# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: tests de la entrega E0′ (esqueleto de los tests de Chatboo). Ver docs/pendiente/parches_pns_ai.md
"""Base común de los tests de Seges en Chatboo.

HttpCase de Odoo 14 pone el registro en modo test: las peticiones HTTP y los
cursores que abre el código (``registry.cursor()``) comparten la transacción
del test, así que no hace falta confirmar nada en la BD.
"""

import json
import uuid

from odoo.tests import HttpCase
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger

from odoo.addons.pns_ai_mcp.utils.api_key import hash_api_key


class SegesChatbooCase(HttpCase):
    """Usuarios con o sin acceso a Chatboo y llamadas JSON-RPC autenticadas."""

    def setUp(self):
        super().setUp()
        self._auth_login = None

    def _chat_user(self, login, access=True, groups='base.group_user'):
        """Usuario con contraseña = login.

        Con ``access``, el acceso que exige Chatboo (``utils/chatboo_access.py``):
        grupo conversacional y clave MCP generada.
        """
        if access:
            groups += ',pns_ai_mcp.group_ai_conversational'
        user = new_test_user(
            self.env, login=login, groups=groups, password=login,
        )
        if access:
            vals = {
                'mcp_api_key_hash': hash_api_key(f'seges-{uuid.uuid4().hex}'),
                'mcp_api_key_state': 'generated',
            }
            McpUser = self.env['ai.mcp.user'].sudo()
            row = McpUser.search([('user_id', '=', user.id)], limit=1)
            if row:
                row.write(vals)
            else:
                McpUser.create(dict(vals, user_id=user.id))
        return user

    def _login(self, login):
        self.env['base'].flush()
        if self._auth_login != login:
            self.authenticate(login, login)
            self._auth_login = login

    def _jsonrpc(self, login, url, params):
        """POST JSON-RPC a una ruta ``type='json'``; devuelve la respuesta entera."""
        self._login(login)
        payload = {
            'jsonrpc': '2.0', 'method': 'call', 'id': 1, 'params': params,
        }
        with mute_logger('odoo.http'):
            resp = self.url_open(
                url, data=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
            )
        return resp.json()

    def _rpc(self, login, model, method, args, kwargs=None):
        return self._jsonrpc(login, f'/web/dataset/call_kw/{model}/{method}', {
            'model': model, 'method': method,
            'args': args, 'kwargs': kwargs or {},
        })

    def _assert_refused(self, res, private):
        """Privado: el core lo rechaza (AccessError); público inexistente: AttributeError."""
        self.assertNotIn('result', res, res)
        expected = (
            'odoo.exceptions.AccessError' if private
            else 'builtins.AttributeError'
        )
        self.assertEqual(res['error']['data']['name'], expected, res)

    def _get(self, login, url):
        self._login(login)
        with mute_logger('odoo.http'):
            return self.url_open(url)
