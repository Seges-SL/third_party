# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 36 (tests de la fase 2c sobre 3.1.973). Ver docs/pendiente/parches_pns_ai.md
"""Parche 36 (PNS-103): vistas de revisión y de resultado sin Ajustes.

``_inject_import_preview_arch`` y ``_inject_operation_result_arch``
(``pns_base/models/operation_report_wizard.py``) leen la ``arch`` de una vista
de ``pns_base``. ``ir.ui.view`` solo lo lee ``base.group_system``: sin el parche,
un AI Administrator sin Ajustes recibe ``AccessError`` al abrir «Review this
import» y el resultado de la importación.

Antes de cada lectura se vacía la caché de las dos vistas: si la ``arch`` ya
estuviera en caché (leída en ``sudo``), leerla como otro usuario no pasaría por
el ACL y el test no mediría el parche.
"""

import base64
import json

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

MODELS = ('ai.import.servers.wizard', 'ai.import.users.wizard')
PREVIEW = 'pns_import_preview'
RESULT = 'pns_operation_result'
VIEWS = (
    'pns_base.view_pns_import_preview_form',
    'pns_base.view_pns_operation_result_form',
)


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesReviewViews(TransactionCase):

    def setUp(self):
        super().setUp()
        self.aiadm = new_test_user(
            self.env, login='seges_36_aiadm',
            groups='base.group_user,pns_ai_mcp.group_ai_admin')
        self.access = new_test_user(
            self.env, login='seges_36_access',
            groups='base.group_user,base.group_erp_manager,pns_ai_mcp.group_ai_admin')
        self.plain = new_test_user(
            self.env, login='seges_36_int',
            groups='base.group_user,pns_ai_mcp.group_ai_conversational')
        self.target = new_test_user(
            self.env, login='seges_36_target', groups='base.group_user')
        McpUser = self.env['ai.mcp.user'].sudo()
        self.target_mcp = McpUser.search([('user_id', '=', self.target.id)], limit=1) \
            or McpUser.create({'user_id': self.target.id})
        self.view_ids = [self.env.ref(xmlid).id for xmlid in VIEWS]
        self.admins = (self.aiadm, self.access)

    def _forget_views(self):
        self.env['ir.ui.view'].invalidate_cache(ids=self.view_ids)

    def _form_arch(self, user, model, context):
        self._forget_views()
        Wizard = self.env[model].with_user(user).with_context(**context)
        return Wizard.fields_view_get(view_id=False, view_type='form')['arch']

    def _wizard(self, user, model, rows):
        data = base64.b64encode(json.dumps(rows).encode())
        return self.env[model].with_user(user).create({
            'json_file': data, 'filename': 'seges_36.json', 'replace_existing': True})

    def test_precondition_view_not_readable(self):
        for user in self.admins:
            self.assertFalse(user.has_group('base.group_system'))
            for xmlid in VIEWS:
                with self.subTest(user=user.login, view=xmlid):
                    self._forget_views()
                    view = self.env.ref(xmlid).with_user(user)
                    with self.assertRaises(AccessError):
                        self.assertFalse(view.arch)
        self.assertFalse(self.aiadm.has_group('base.group_erp_manager'))
        self.assertTrue(self.access.has_group('base.group_erp_manager'))

    def test_aiadm_gets_review_view(self):
        for user in self.admins:
            for model in MODELS:
                with self.subTest(user=user.login, model=model):
                    arch = self._form_arch(user, model, {PREVIEW: True})
                    self.assertIn('o_pns_import_preview', arch)
                    self.assertIn('No data has been written.', arch)

    def test_aiadm_gets_result_view(self):
        for user in self.admins:
            for model in MODELS:
                with self.subTest(user=user.login, model=model):
                    arch = self._form_arch(user, model, {RESULT: True})
                    self.assertIn('o_pns_op_result', arch)

    def test_aiadm_users_review_and_result(self):
        model = 'ai.import.users.wizard'
        for user in self.admins:
            label = f'seges-36-{user.login}'
            wizard = self._wizard(user, model, [
                {'login': self.target.login, 'last_mcp_client_label': label}])
            with self.subTest(user=user.login, step='review'):
                action = wizard.action_preview()
                self.assertTrue(action['context'].get(PREVIEW))
                arch = self._form_arch(user, model, action['context'])
                self.assertIn('No data has been written.', arch)
            with self.subTest(user=user.login, step='result'):
                action = wizard.action_import()
                self.assertTrue(action['context'].get(RESULT))
                self.assertFalse(wizard.result_errors)
                self.assertEqual(wizard.result_updated, 1)
                self.target_mcp.invalidate_cache()
                self.assertEqual(self.target_mcp.last_mcp_client_label, label)
                arch = self._form_arch(user, model, action['context'])
                self.assertIn('o_pns_op_result', arch)

    def test_aiadm_servers_review_and_result(self):
        model = 'ai.import.servers.wizard'
        Provider = self.env['ai.provider'].sudo().with_context(active_test=False)
        for user in self.admins:
            name = f'Seges 36 {user.login}'
            wizard = self._wizard(user, model, [{'name': name, 'temperature': 0.42}])
            with self.subTest(user=user.login, step='review'):
                action = wizard.action_preview()
                self.assertTrue(action['context'].get(PREVIEW))
                arch = self._form_arch(user, model, action['context'])
                self.assertIn('No data has been written.', arch)
            with self.subTest(user=user.login, step='result'):
                action = wizard.action_import()
                self.assertTrue(action['context'].get(RESULT))
                self.assertFalse(wizard.result_errors)
                self.assertEqual(wizard.result_created, 1)
                provider = Provider.search([('name', '=', name)])
                self.assertEqual(len(provider), 1)
                self.assertEqual(provider.temperature, 0.42)
                arch = self._form_arch(user, model, action['context'])
                self.assertIn('o_pns_op_result', arch)

    def test_non_admin_still_refused(self):
        self.assertFalse(self.plain.has_group('pns_ai_mcp.group_ai_admin'))
        for model in MODELS:
            for key in (PREVIEW, RESULT):
                with self.subTest(model=model, view=key):
                    with self.assertRaises(AccessError):
                        self._form_arch(self.plain, model, {key: True})
            with self.subTest(model=model, step='create'):
                with self.assertRaises(AccessError):
                    self._wizard(self.plain, model, [])
