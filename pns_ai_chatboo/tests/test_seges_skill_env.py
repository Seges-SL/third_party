# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 23 (tests de la entrega E2′). Ver docs/pendiente/parches_pns_ai.md
"""Parche 23 (PNS-101), no regresión: una skill de fábrica que usa ``env``
(``env.user``, ``env.company``, ``env[...]``, ``'modelo' in env``) sigue
corriendo en la caja A real con la lista de atributos de ``GuardedSandboxEnv``.
"""

import json

from odoo.modules.module import get_module_resource
from odoo.tests import TransactionCase, tagged

from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import tool_relaxaicode
from odoo.addons.pns_ai_mcp.tests.test_seges_sandbox_credentials import _StubController


@tagged('post_install', '-at_install', 'pns_ai_chatboo', 'seges_e2p')
class TestSegesSkillEnv(TransactionCase):

    def test_customer_360_runs(self):
        path = get_module_resource(
            'pns_ai_chatboo', 'ai', 'skills', 'system', 'customer_360.py')
        with open(path, encoding='utf-8') as source:
            code = source.read()
        admin = self.env.ref('base.user_admin')
        # Sin cliente: lee env.user, env.company y env['res.partner'] en el nivel
        # superior y acaba con un aviso de texto (que el motor no enseña).
        resp = tool_relaxaicode(_StubController(self.env(user=admin)), {'code': code})
        text = json.dumps(resp, default=str)
        self.assertNotIn('ERROR (', text)
        self.assertNotIn('"isError": true', text)
        self.assertNotIn('is not available in RelaxAICode', text)
        self.assertIn('__extraction_complete__', text)
