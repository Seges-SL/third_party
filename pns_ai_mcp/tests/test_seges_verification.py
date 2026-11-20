# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 16 (tests de la entrega E1′). Ver docs/pendiente/parches_pns_ai.md
"""Parche 16 (PNS-54): confirmar desde Autorizaciones pide la contraseña y el
token de la tarjeta solo se genera para el dueño de la operación.

Un script en la página llamaba por RPC a ``action_confirm_and_execute`` (o a
su alias ``action_execute_plan``) y confirmaba y ejecutaba sin token ni espera
(docs/specs/comparacion_pns_ai_3-1-879.md, §3, PNS-54). El parche no cubre la
tarjeta del chat del propio dueño (opción c), riesgo aceptado con D29.
"""

import json

from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e1p')
class TestSegesVerification(HttpCase):

    def setUp(self):
        super().setUp()
        self.owner = new_test_user(
            self.env, login='seges_e1p_54_owner',
            groups='base.group_user,pns_ai_mcp.group_ai_writer',
            password='seges_e1p_54_owner',
        )
        self.adm = new_test_user(
            self.env, login='seges_e1p_54_adm',
            groups='base.group_user,pns_ai_mcp.group_ai_admin',
            password='seges_e1p_54_adm',
        )
        self.partner = self.env['res.partner'].create({'name': 'Seges E1p 54'})
        self.op = self.env['ai.safe.operation'].create_verification(
            operation_type='write',
            model_name='res.partner',
            records_count=1,
            changes_info={'plan': ['write partner'], 'danger_level': 'medium'},
            user_id=self.owner.id,
            tool_name='seges_e1p_54',
            operation_data={
                'plan_steps': [{
                    'op': 'write', 'model': 'res.partner',
                    'ids': [self.partner.id],
                    'values': {'comment': 'seges-e1p-54'},
                }],
                'title': 'seges e1p 54',
                'plan': ['write partner'],
                'danger_level': 'medium',
            },
        )

    def _rpc(self, login, method):
        self.env['base'].flush()
        self.authenticate(login, login)
        payload = {
            'jsonrpc': '2.0', 'method': 'call', 'id': 1,
            'params': {
                'model': 'ai.safe.operation', 'method': method,
                'args': [[self.op.id]], 'kwargs': {},
            },
        }
        resp = self.url_open(
            f'/web/dataset/call_kw/ai.safe.operation/{method}',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        return resp.json()

    def _assert_untouched(self):
        self.op.invalidate_cache()
        self.partner.invalidate_cache()
        self.assertEqual(self.op.status, 'pending')
        self.assertFalse(self.op.executed)
        self.assertFalse(self.op.confirmed_by_uid)
        self.assertFalse(self.partner.comment)

    def test_confirm_and_execute_requires_identity(self):
        for login in ('seges_e1p_54_owner', 'seges_e1p_54_adm'):
            for method in ('action_confirm_and_execute', 'action_execute_plan'):
                with mute_logger('odoo.http'):
                    res = self._rpc(login, method)
                self.assertIn('result', res, (login, method, res))
                self.assertEqual(
                    res['result'].get('res_model'), 'res.users.identitycheck',
                    (login, method, res))
                self._assert_untouched()

    def test_card_payload_mint_only_owner(self):
        payload = self.op.with_user(self.adm).card_payload()
        self.assertNotIn('confirm_token', payload)
        self.op.invalidate_cache()
        self.assertFalse(self.op.sudo().confirm_token_hash)
        payload = self.op.with_user(self.owner).card_payload()
        self.assertTrue(payload.get('confirm_token'))
        self.op.invalidate_cache()
        self.assertTrue(self.op.sudo().confirm_token_hash)
