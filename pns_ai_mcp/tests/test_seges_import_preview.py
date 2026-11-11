# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 21 (tests de la entrega E2′). Ver docs/pendiente/parches_pns_ai.md
"""Parche 21 (PNS-20): «Review» (``action_preview``) no deja nada escrito.

Sin el parche, lo que la importación deja pendiente en el ORM (``towrite``)
se vuelca al final de la petición, después del ``ROLLBACK TO SAVEPOINT`` (P-20
en el laboratorio, 27/10/2026). Aquí el final de la petición se simula con un
``flush``. ``write_date`` no sirve para detectarlo (``now()`` es constante en
la transacción del test): se usa ``ctid``, que cambia con cada ``UPDATE`` y
vuelve al original tras un ``ROLLBACK TO SAVEPOINT``.
"""

import base64
import json
from unittest import mock

from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

LABEL = 'seges-e2p-20'


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesImportPreview(TransactionCase):

    def setUp(self):
        super().setUp()
        self.user = new_test_user(
            self.env, login='seges_e2p_20_u', groups='base.group_user')
        McpUser = self.env['ai.mcp.user'].sudo()
        self.mcp_user = McpUser.search([('user_id', '=', self.user.id)], limit=1) \
            or McpUser.create({'user_id': self.user.id})
        self.provider = self.env['ai.provider'].sudo().create({
            'name': 'Seges E2p 20', 'temperature': 0.7,
            'endpoint': 'https://seges.invalid/v1/chat/completions',
        })
        self.model = self.env['ai.provider.model'].sudo().create({
            'name': 'seges-e2p-20-model', 'provider_id': self.provider.id})
        self.provider.model_id = self.model.id
        self.env['base'].flush()

    def _ctid(self, table, rec_id):
        self.env['base'].flush()
        query = {
            'ai_mcp_user': 'SELECT ctid FROM ai_mcp_user WHERE id = %s',
            'ai_provider': 'SELECT ctid FROM ai_provider WHERE id = %s',
        }[table]
        self.env.cr.execute(query, (rec_id,))
        return self.env.cr.fetchone()[0]

    def _wizard(self, model, rows):
        data = base64.b64encode(json.dumps(rows).encode())
        return self.env[model].create({
            'json_file': data, 'filename': 'seges.json', 'replace_existing': True})

    def _preview_then_end_request(self, wizard):
        wizard.action_preview()
        # Final de la petición de «Review»: Odoo vuelca lo pendiente y confirma.
        self.env['base'].flush()

    def test_users_preview_keeps_value(self):
        before = self._ctid('ai_mcp_user', self.mcp_user.id)
        wizard = self._wizard('ai.import.users.wizard', [
            {'login': self.user.login, 'last_mcp_client_label': LABEL}])
        self._preview_then_end_request(wizard)
        self.mcp_user.invalidate_cache()
        self.assertFalse(self.mcp_user.last_mcp_client_label)
        self.assertEqual(self._ctid('ai_mcp_user', self.mcp_user.id), before)

    def test_providers_preview_no_update(self):
        before = self._ctid('ai_provider', self.provider.id)
        wizard = self._wizard('ai.import.servers.wizard', [{
            'name': 'Seges E2p 20', 'temperature': 0.42,
            'selected_model': 'seges-e2p-20-model'}])
        self._preview_then_end_request(wizard)
        self.provider.invalidate_cache()
        self.assertEqual(self.provider.temperature, 0.7)
        self.assertEqual(self._ctid('ai_provider', self.provider.id), before)

    def test_users_preview_keeps_groups(self):
        writer = self.env.ref('pns_ai_mcp.group_ai_writer')
        self.assertNotIn(writer, self.user.groups_id)
        wizard = self._wizard('ai.import.users.wizard', [
            {'login': self.user.login, 'is_ai_writer': True}])
        cls = type(wizard)
        snapshot = cls._preview_snapshot

        def _snapshot(wiz):
            # Código que pregunta has_group durante la vista previa (como
            # ai.mcp.user._export_user_dict): la respuesta queda en el ormcache.
            self.assertTrue(self.user.has_group('pns_ai_mcp.group_ai_writer'))
            return snapshot(wiz)

        with mock.patch.object(cls, '_preview_snapshot', _snapshot):
            self._preview_then_end_request(wizard)
        # El ROLLBACK no deshace el ormcache: sin clear_caches(), has_group seguiría en True.
        self.assertFalse(self.user.has_group('pns_ai_mcp.group_ai_writer'))
        self.user.invalidate_cache()
        self.assertNotIn(writer, self.user.groups_id)

    def test_import_still_applies(self):
        wizard = self._wizard('ai.import.users.wizard', [
            {'login': self.user.login, 'last_mcp_client_label': LABEL}])
        wizard.action_import()
        self.env['base'].flush()
        self.mcp_user.invalidate_cache()
        self.assertEqual(self.mcp_user.last_mcp_client_label, LABEL)
