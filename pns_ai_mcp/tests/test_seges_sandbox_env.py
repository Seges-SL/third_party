# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 23 (tests de la entrega E2′). Ver docs/pendiente/parches_pns_ai.md
# Seges: adaptado a 3.1.973 (fase 3a, decisión 5): parche 23 retirado; no regresión de la lista de GuardedSandboxEnv del fabricante. Ver docs/pendiente/parches_pns_ai.md
"""Parche 23 (PNS-101): el ``env`` de la caja A no lleva a los entornos reales
del hilo.

En Odoo 14 la caché y el conjunto de entornos (``env.all``) son uno por hilo:
desde la caja A, ``env.all`` daba el entorno del cursor de la petición (sin la
marca del parche 18, sin ``READ ONLY`` y con commit al final) y ``env.cache``
lo que cualquiera de ellos había leído. Se cierran como atributo (AST y
``guarded_getattr``), y ``GuardedSandboxEnv`` solo da una lista de atributos.

Como en ``TestSegesBoxAReal``, se usa la herramienta real con
``base.user_admin`` y el secreto confirmado ``database.secret``.

En 3.1.973 el parche 23 se retira: lo cubre la lista cerrada de
``GuardedSandboxEnv`` del fabricante (``user``, ``company``, ``companies``,
``context``, ``lang``, ``uid``, ``ref``, ``with_context`` y ``with_company``) y
``sandbox_attr``/``guarded_getattr``, que rechazan los objetos de base de datos
(``Environment``, ``Environments``, ``Cache``…). Los negativos comprueban que se
rechaza y que no sale el secreto, sin el mensaje (decisión 5 del plan).
"""

import json

from odoo.tests import TransactionCase, tagged

from odoo.addons.pns_ai_mcp.controllers.context_builder import (
    GuardedSandboxEnv,
    guarded_getattr,
)
from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import tool_relaxaicode
from odoo.addons.pns_ai_mcp.tests.seges_common import _StubController

NOT_AVAILABLE = 'is not available'


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

    def _refused(self, code):
        """Se rechaza (sea cual sea el mensaje) y no sale el secreto."""
        text = self._tool(code)
        self.assertTrue('ERROR (' in text or '"isError": true' in text, code)
        # assertFalse(... in text, 'filtra'): el secreto no entra en el mensaje del assert.
        self.assertFalse(self.secret in text, 'filtra')
        for name in ('Environments', 'WeakSet', 'StackMap', "'Cache'"):
            self.assertNotIn(name, text, code)
        return text

    # Negativos: env.cache, env.all y sus variantes.

    def test_env_cache(self):
        self._refused("result = type(env.cache).__name__\n")

    def test_env_cache_get_warm(self):
        # El motor deja el secreto en la caché del hilo; el sandbox no la alcanza.
        warm = self.env['ir.config_parameter'].sudo().browse(self.secret_id).value
        self.assertEqual(warm, self.secret)
        self._refused(
            "p = " + self.ref + "\n"
            "result = {'data': [{'v': env.cache.get(p, p._fields['value'], None)}]}\n")

    def test_env_all(self):
        self._refused("result = type(env.all).__name__\n")

    def test_alias_all(self):
        self._refused("x = env\nresult = type(x.all).__name__\n")

    def test_state_attrs(self):
        for name in ('envs', 'towrite', 'tocompute', 'protected'):
            with self.subTest(name=name):
                self._refused(f"result = type(env.{name}).__name__\n")

    def test_composite_getattr(self):
        for expr in ("getattr(env, 'al' + 'l')", "getattr(env, 'ca' + 'che')",
                     "getattr(env, ''.join(['e', 'nvs']))"):
            with self.subTest(expr=expr):
                self._refused(f"result = type({expr}).__name__\n")

    def test_attrgetter(self):
        self._refused(
            "from operator import attrgetter\n"
            "result = type(attrgetter('al' + 'l')(env)).__name__\n")

    def test_walk_to_other_environment(self):
        """El recorrido de la reproducción: otro Environment del hilo lee el secreto."""
        self._refused(
            "rows = []\n"
            "for e in getattr(env, 'al' + 'l'):\n"
            "    p = e['mail.template.preview'].new("
            f"{{'resource_ref': 'ir.config_parameter,{self.secret_id}'}}).resource_ref\n"
            "    rows.append({'uid': e.uid, 'v': p.value})\n"
            "result = {'data': rows}\n")

    def test_wrapper_allowlist(self):
        genv = GuardedSandboxEnv(self.env(user=self.admin))
        for name in ('cache', 'all', 'envs', 'towrite', 'clear', 'values', 'items',
                     'args', 'protecting', 'add_to_compute', 'uid_origin'):
            with self.subTest(name=name):
                with self.assertRaises(AttributeError):
                    getattr(genv, name)
        # El Environments del hilo es un objeto de base de datos: se rechaza.
        with self.assertRaises(AttributeError):
            guarded_getattr(self.env, 'all')

    # Positivos: lo permitido sigue funcionando.

    def test_builtin_all_and_cache_name(self):
        row = self._row(
            "cache = {'a': 4}\n"
            "result = {'data': [{'all': all([1, 2, 3]), 'any': any([0]),"
            " 'cache': cache['a']}]}\n")
        self.assertEqual((row['all'], row['any'], row['cache']), (True, False, 4))

    def test_allowed_attrs(self):
        # Seges: adaptado a 3.1.973 (fase 3a, decisión 5): invertido al criterio del
        # fabricante. Funcionan los nombres de su lista (with_context/with_company no
        # existen en el Environment de Odoo 14); su, is_admin e is_system, que daba el
        # parche 23, se rechazan. Ver docs/pendiente/parches_pns_ai.md
        row = self._row(
            "result = {'data': [{'uid': env.uid, 'login': env.user.login,"
            " 'company': env.company.name, 'n': len(env.companies),"
            " 'lang': env.lang or '', 'ctx': 'tz' in env.context or True,"
            " 'ref': env.ref('base.user_admin').login,"
            " 'users': env(context={'active_test': False})['res.users'].search_count([])}]}\n")
        self.assertEqual(row['uid'], self.admin.id)
        self.assertEqual(row['login'], self.admin.login)
        self.assertEqual(row['ref'], self.admin.login)
        self.assertEqual(row['company'], self.admin.company_id.name)
        self.assertTrue(row['users'])
        for name in ('su', 'is_admin', 'is_system'):
            with self.subTest(name=name):
                self._refused(f"result = {{'data': [{{'v': str(env.{name})}}]}}\n")

    def test_engine_attrs_refused_on_wrapper(self):
        """Antes ``test_engine_attrs_on_wrapper``. Invertido al criterio del fabricante:
        el envoltorio no da ``cr`` ni ``registry`` (en la rama 3879 los daba al motor)."""
        # Seges: adaptado a 3.1.973 (fase 3a, decisión 5). Ver docs/pendiente/parches_pns_ai.md
        genv = GuardedSandboxEnv(self.env(user=self.admin))
        for name in ('cr', 'registry'):
            with self.subTest(name=name):
                with self.assertRaisesRegex(AttributeError, NOT_AVAILABLE):
                    getattr(genv, name)
        self.assertEqual(genv.user, self.admin)
