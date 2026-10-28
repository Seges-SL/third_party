# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 24 (tests de la entrega E2′). Ver docs/pendiente/parches_pns_ai.md
"""Parche 24 (PNS-102): ``user`` / ``company`` / ``companies`` del sandbox SIN su.

``env.user`` / ``env.company`` / ``env.companies`` del ORM fuerzan ``su=True``
(``api.py``: ``self(su=True)``). El sandbox corre como el usuario que pregunta,
así que se reconstruyen desde ``uid`` sin su, para que ACL y record rules se
apliquen (C2: por el registro ``user`` inyectado se leía un campo ``NO_ACCESS``
y datos de terceros).
"""

import json

from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from odoo.addons.pns_ai_mcp.controllers.context_builder import (
    GuardedSandboxEnv,
    _identity_no_su,
)
from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import tool_relaxaicode
from odoo.addons.pns_ai_mcp.tests.test_seges_sandbox_credentials import _StubController


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesIdentityNoSu(TransactionCase):

    def setUp(self):
        super().setUp()
        self.demo = new_test_user(
            self.env, login='seges_e2p_24_demo', groups='base.group_user')
        self.admin = self.env.ref('base.user_admin')

    def _tool(self, code):
        stub = _StubController(self.env(user=self.demo))
        resp = tool_relaxaicode(stub, {'code': code})
        return json.dumps(resp, default=str)

    # ── Identidad sin su (preciso, siempre corre) ────────────────────────────

    def test_wrapper_user_not_su(self):
        genv = GuardedSandboxEnv(self.env(user=self.demo))
        self.assertFalse(genv.user.env.su)
        self.assertEqual(genv.user.env.uid, self.demo.id)
        self.assertEqual(genv.user.id, self.demo.id)

    def test_wrapper_company_not_su(self):
        genv = GuardedSandboxEnv(self.env(user=self.demo))
        self.assertFalse(genv.company.env.su)
        self.assertFalse(genv.companies.env.su)

    def test_identity_helper_not_su(self):
        env = self.env(user=self.demo)
        for name in ('user', 'company', 'companies'):
            with self.subTest(name=name):
                self.assertFalse(_identity_no_su(env, name).env.su)

    def test_positive_reads_own_user_company(self):
        # Las skills de fábrica leen env.user.lang y env.company.name/.id sin su.
        text = self._tool(
            "result = {'data': [{'lang': env.user.lang, "
            "'co': env.company.name, 'cid': env.company.id, "
            "'ulogin': user.login}]}\n")
        self.assertNotIn('ERROR (', text)
        row = json.loads(json.loads(text)['content'][0]['text'])['data'][0]
        self.assertEqual(row['ulogin'], self.demo.login)
        self.assertEqual(row['cid'], self.demo.company_id.id)

    # ── C2: el campo NO_ACCESS no sale por el registro `user` (su) ────────────

    def test_c2_no_access_field_via_user(self):
        if 'totp_secret' not in self.env['res.users']._fields:
            self.skipTest('auth_totp no instalado en esta BD')
        # Antes: `user` era su y entregaba totp_secret (campo NO_ACCESS). Ahora, sin
        # su, el control de grupos de campo lo deniega: AccessError («enough rights»)
        # y el campo no sale (no se llega a 'leido').
        aid = self.admin.id
        text = self._tool(
            f"v = user.browse({aid}).totp_secret\n"
            "result = {'data': [{'v': 'leido'}]}\n")
        self.assertIn('"isError": true', text)
        self.assertIn('enough rights', text)
        self.assertNotIn('leido', text)
