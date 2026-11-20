# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: tests de la entrega E0′ (esqueleto de los tests de Chatboo). Ver docs/pendiente/parches_pns_ai.md
"""Prueba mínima de Chatboo: el módulo se instala y un usuario con acceso abre
una sesión por las rutas del chat. Cada entrega del plan añade su archivo
``test_seges_chatboo_<tema>.py`` sobre ``SegesChatbooCase``."""

from odoo.tests import tagged

from .common import SegesChatbooCase


@tagged('post_install', '-at_install', 'pns_ai_chatboo', 'seges_e0')
class TestSegesChatbooSmoke(SegesChatbooCase):

    def test_open_session(self):
        user = self._chat_user('seges_e0_chat')
        res = self._jsonrpc(
            'seges_e0_chat', '/chatboo/sessions/create', {'name': 'Seges E0'})
        result = res.get('result') or {}
        self.assertEqual(result.get('status'), 'ok', res)
        session_id = result['session']['id']
        session = self.env['chatboo.session'].browse(session_id)
        self.assertEqual(session.user_id, user)
        res = self._jsonrpc(
            'seges_e0_chat', '/chatboo/sessions/load',
            {'session_id': session_id})
        result = res.get('result') or {}
        self.assertEqual(result.get('status'), 'ok', res)
        self.assertEqual(result['session']['id'], session_id)
        self.assertIsInstance(result['session']['messages'], list)

    def test_no_access_without_key(self):
        self._chat_user('seges_e0_nokey', access=False)
        Session = self.env['chatboo.session']
        before = Session.search_count([])
        res = self._jsonrpc(
            'seges_e0_nokey', '/chatboo/sessions/create', {'name': 'Seges E0'})
        result = res.get('result') or {}
        self.assertEqual(result.get('status'), 'error', res)
        self.assertIs(result.get('has_api_key'), False, res)
        self.assertEqual(Session.search_count([]), before)
