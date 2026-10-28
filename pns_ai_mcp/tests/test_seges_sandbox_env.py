# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 23 (tests de la entrega E2′). Ver docs/pendiente/parches_pns_ai.md
"""Parche 23 (PNS-101): el ``env`` de la caja A no lleva a los entornos reales
del hilo.

En Odoo 14 la caché y el conjunto de entornos (``env.all``) son uno por hilo:
desde la caja A, ``env.all`` daba el entorno del cursor de la petición (sin la
marca del parche 18, sin ``READ ONLY`` y con commit al final) y ``env.cache``
lo que cualquiera de ellos había leído. Se cierran como atributo (AST y
``guarded_getattr``), y ``GuardedSandboxEnv`` solo da una lista de atributos.

Como en ``TestSegesBoxAReal``, se usa la herramienta real con
``base.user_admin`` y el secreto confirmado ``database.secret``.
"""

import json

from odoo.tests import TransactionCase, tagged

from odoo.addons.pns_ai_mcp.controllers.context_builder import (
    GuardedSandboxEnv,
    guarded_getattr,
)
from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import tool_relaxaicode
from odoo.addons.pns_ai_mcp.tests.test_seges_sandbox_credentials import _StubController

ENV_STATE = "it is the ORM's own state"
NOT_AVAILABLE = 'is not available in RelaxAICode'


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesSandboxEnv(TransactionCase):

    def setUp(self):
        super().setUp()
        self.admin = self.env.ref('base.user_admin')
        self.env.cr.execute(
            "SELECT id, value FROM ir_config_parameter WHERE key = 'database.secret'")
        self.secret_id, self.secret = self.env.cr.fetchone()
        self.ref = (
            "env['mail.template.preview'].new("
            f"{{'resource_ref': 'ir.config_parameter,{self.secret_id}'}}).resource_ref")

    def _tool(self, code):
        stub = _StubController(self.env(user=self.admin))
        resp = tool_relaxaicode(stub, {'code': code})
        return json.dumps(resp, default=str)

    def _row(self, code):
        """La primera fila de una ejecución correcta (el texto va en JSON)."""
        text = self._tool(code)
        self.assertNotIn('ERROR (', text, code)
        self.assertNotIn(NOT_AVAILABLE, text, code)
        resp = json.loads(text)
        return json.loads(resp['content'][0]['text'])['data'][0]

    def _refused(self, code, message):
        text = self._tool(code)
        self.assertIn('ERROR (', text, code)
        self.assertIn(message, text, code)
        self.assertNotIn(self.secret, text, code)
        for name in ('Environments', 'WeakSet', 'StackMap', "'Cache'"):
            self.assertNotIn(name, text, code)
        return text

    # Negativos: env.cache, env.all y sus variantes.

    def test_env_cache(self):
        self._refused("result = type(env.cache).__name__\n", ENV_STATE)

    def test_env_cache_get_warm(self):
        # El motor deja el secreto en la caché del hilo; el sandbox no la alcanza.
        warm = self.env['ir.config_parameter'].sudo().browse(self.secret_id).value
        self.assertEqual(warm, self.secret)
        self._refused(
            "p = " + self.ref + "\n"
            "result = {'data': [{'v': env.cache.get(p, p._fields['value'], None)}]}\n",
            ENV_STATE)

    def test_env_all(self):
        self._refused("result = type(env.all).__name__\n", ENV_STATE)

    def test_alias_all(self):
        self._refused("x = env\nresult = type(x.all).__name__\n", ENV_STATE)

    def test_state_attrs(self):
        for name in ('envs', 'towrite', 'tocompute', 'protected'):
            with self.subTest(name=name):
                self._refused(f"result = type(env.{name}).__name__\n", ENV_STATE)

    def test_composite_getattr(self):
        for expr in ("getattr(env, 'al' + 'l')", "getattr(env, 'ca' + 'che')",
                     "getattr(env, ''.join(['e', 'nvs']))"):
            with self.subTest(expr=expr):
                self._refused(f"result = type({expr}).__name__\n", ENV_STATE)

    def test_attrgetter(self):
        self._refused(
            "from operator import attrgetter\n"
            "result = type(attrgetter('al' + 'l')(env)).__name__\n", ENV_STATE)

    def test_walk_to_other_environment(self):
        """El recorrido de la reproducción: otro Environment del hilo lee el secreto."""
        self._refused(
            "rows = []\n"
            "for e in getattr(env, 'al' + 'l'):\n"
            "    p = e['mail.template.preview'].new("
            f"{{'resource_ref': 'ir.config_parameter,{self.secret_id}'}}).resource_ref\n"
            "    rows.append({'uid': e.uid, 'v': p.value})\n"
            "result = {'data': rows}\n", ENV_STATE)

    def test_wrapper_allowlist(self):
        genv = GuardedSandboxEnv(self.env(user=self.admin))
        for name in ('cache', 'all', 'envs', 'towrite', 'clear', 'values', 'items',
                     'args', 'protecting', 'add_to_compute', 'uid_origin'):
            with self.subTest(name=name):
                with self.assertRaisesRegex(AttributeError, NOT_AVAILABLE):
                    getattr(genv, name)
        with self.assertRaisesRegex(AttributeError, ENV_STATE):
            guarded_getattr(self.env, 'all')

    # Positivos: lo permitido sigue funcionando.

    def test_builtin_all_and_cache_name(self):
        row = self._row(
            "cache = {'a': 4}\n"
            "result = {'data': [{'all': all([1, 2, 3]), 'any': any([0]),"
            " 'cache': cache['a']}]}\n")
        self.assertEqual((row['all'], row['any'], row['cache']), (True, False, 4))

    def test_allowed_attrs(self):
        row = self._row(
            "result = {'data': [{'uid': env.uid, 'login': env.user.login,"
            " 'company': env.company.name, 'n': len(env.companies),"
            " 'lang': env.lang or '', 'ctx': 'tz' in env.context or True,"
            " 'ref': env.ref('base.user_admin').login, 'admin': env.is_admin(),"
            " 'system': env.is_system(), 'su': env.su,"
            " 'users': env(context={'active_test': False})['res.users'].search_count([])}]}\n")
        self.assertEqual(row['uid'], self.admin.id)
        self.assertEqual(row['login'], self.admin.login)
        self.assertEqual(row['ref'], self.admin.login)
        self.assertEqual(row['company'], self.admin.company_id.name)
        self.assertTrue(row['admin'] and row['system'])
        self.assertFalse(row['su'])
        self.assertTrue(row['users'])

    def test_engine_attrs_on_wrapper(self):
        """El motor recibe este env tras la ejecución (render, respuestas de error)."""
        genv = GuardedSandboxEnv(self.env(user=self.admin))
        self.assertTrue(genv.cr)
        self.assertIn('res.users', genv.registry)
        self.assertEqual(genv.user, self.admin)
