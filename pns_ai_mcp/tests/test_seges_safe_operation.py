# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 13 (tests de la entrega E1′). Ver docs/pendiente/parches_pns_ai.md
"""Parche 13 (M10): solo el sistema crea operaciones supervisadas.

Sin el parche, un AI Administrator crea por RPC una operación ya confirmada,
con el ``confirmed_by_uid`` y el plan que quiera, y la hace ejecutar con la
identidad de ese usuario (docs/specs/comparacion_pns_ai_3-1-879.md, §8.7, M10).
El rechazo llega antes de abrir ningún cursor: no hace falta cursor propio.
"""

import json
from datetime import timedelta

from odoo import api, fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

REFUSED = 'Only the system can create a supervised operation'
PLAN = {
    'plan_steps': [{
        'op': 'write', 'model': 'res.partner', 'ids': [1],
        'values': {'comment': 'seges-e1p-m10'},
    }],
    'title': 'seges e1p m10',
    'plan': ['write partner'],
    'danger_level': 'medium',
}


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e1p')
class TestSegesSafeOperationCreate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.adm = new_test_user(
            self.env, login='seges_e1p_m10_adm',
            groups='base.group_user,pns_ai_mcp.group_ai_admin',
        )
        self.env_adm = api.Environment(self.env.cr, self.adm.id, {})
        self.admin = self.env.ref('base.user_admin')
        self.Op = self.env['ai.safe.operation'].sudo()

    def _verification(self, env, user_id):
        return env['ai.safe.operation'].create_verification(
            operation_type='write',
            model_name='res.partner',
            records_count=1,
            changes_info={'plan': ['write partner'], 'danger_level': 'medium'},
            user_id=user_id,
            tool_name='seges_e1p_m10',
            operation_data=PLAN,
        )

    def test_rpc_create_confirmed_refused(self):
        before = self.Op.search_count([])
        with self.assertRaisesRegex(AccessError, REFUSED):
            self.env_adm['ai.safe.operation'].create({
                'verification_id': 'SEGESM10',
                'operation_type': 'write',
                'model_name': 'res.partner',
                'records_count': 1,
                'user_id': self.admin.id,
                'confirmed_by_uid': self.admin.id,
                'status': 'confirmed',
                'executed': False,
                'operation_data': json.dumps(PLAN),
                'expires_at': fields.Datetime.now() + timedelta(minutes=10),
            })
        self.assertEqual(self.Op.search_count([]), before)

    def test_create_verification_for_other_refused(self):
        before = self.Op.search_count([])
        with self.assertRaisesRegex(AccessError, REFUSED):
            self._verification(self.env_adm, self.admin.id)
        self.assertEqual(self.Op.search_count([]), before)

    def test_copy_refused(self):
        op = self._verification(self.env, self.adm.id)
        before = self.Op.search_count([])
        with self.assertRaisesRegex(AccessError, REFUSED):
            op.with_user(self.adm).copy({
                'status': 'confirmed',
                'confirmed_by_uid': self.admin.id,
                'expires_at': fields.Datetime.now() + timedelta(minutes=10),
            })
        self.assertEqual(self.Op.search_count([]), before)

    def test_system_create_still_works(self):
        op = self._verification(self.env, self.adm.id)
        self.assertEqual(op.status, 'pending')
        self.assertEqual(op.user_id, self.adm)
        self.assertFalse(op.confirmed_by_uid)
