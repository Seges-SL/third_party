# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 23 ampliado (tests de la entrega E2′). Ver docs/pendiente/parches_pns_ai.md
"""Parche 23 ampliado (PNS-101), segunda vuelta: la clase nativa de las fachadas
y la vía de skills.

CRÍTICO 1: ``guarded_attrgetter`` / ``guarded_methodcaller`` devolvían el objeto
real de ``operator``; con ``type()`` permitido se obtenía la clase nativa
(``type(attrgetter('id'))``) y con ella un getter nuevo que esquivaba
``_check_attr_path``. Hoy las fachadas devuelven una función: ``type()`` sobre
ella da ``function`` y su constructor no sirve para recorrer atributos.

CRÍTICO 2: ``bootstrap_skill_code_body`` (la vía real de las skills con ``/``)
compilaba con ``compile()`` normal, sin reescribir ``.format``; una plantilla en
variable esquivaba el formateador. Hoy usa ``run_sandbox_code``, igual que
``tool_relaxaicode``.

Las comprobaciones de no filtración leen ``database.secret`` en tiempo de test y
comparan con ``assertFalse(secreto in texto, 'filtra')``: así ni el secreto ni la
respuesta completa entran en el mensaje del assert (no se vuelcan al log si el
test falla, por ejemplo durante una neutralización).
"""

import json

from odoo.tests import TransactionCase, tagged

from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import tool_relaxaicode
from odoo.addons.pns_ai_mcp.tests.test_seges_sandbox_credentials import _StubController
from odoo.addons.pns_ai_mcp.utils.skill_runtime import bootstrap_skill_code_body

ERROR = 'ERROR ('
# Nombres que solo aparecen si una ruta dunder alcanzó odoo.tools.config.
LEAK_NAMES = ('admin_passwd', 'db_password', 'ConfigManager', 'configmanager')


class _SegesSecretCase(TransactionCase):

    def setUp(self):
        super().setUp()
        self.admin = self.env.ref('base.user_admin')
        self.env.cr.execute(
            "SELECT value FROM ir_config_parameter WHERE key = 'database.secret'")
        row = self.env.cr.fetchone()
        self.secret = row[0] if row else '__no_secret__'

    def _no_leak(self, text):
        self.assertFalse(self.secret in text, 'filtra')
        for name in LEAK_NAMES:
            self.assertFalse(name in text, 'filtra')


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesFacadeClass(_SegesSecretCase):
    """CRÍTICO 1: la clase nativa de attrgetter/methodcaller ya no esquiva el
    guard, y el uso legítimo de las fachadas sigue funcionando."""

    def _tool(self, code):
        stub = _StubController(self.env(user=self.admin))
        return json.dumps(tool_relaxaicode(stub, {'code': code}), default=str)

    def _refused(self, code):
        text = self._tool(code)
        self.assertIn(ERROR, text, code)
        self._no_leak(text)
        return text

    def _row(self, code):
        text = self._tool(code)
        self.assertNotIn(ERROR, text, code)
        resp = json.loads(text)
        return json.loads(resp['content'][0]['text'])['data'][0]

    # ── Negativos: la clase nativa de la fachada ─────────────────────────────

    def test_type_attrgetter_class(self):
        # type(attrgetter('id')) daba operator.attrgetter; con él se construía un
        # getter nuevo que llegaba a un dunder sin pasar por el guard. Hoy da
        # 'function': llamarla con una ruta no la resuelve.
        self._refused(
            "from operator import attrgetter\n"
            "AG = type(attrgetter('id'))\n"
            "g = AG('__class__')\n"
            "result = {'data': [{'v': str(g(user))}]}\n")

    def test_type_methodcaller_class(self):
        # type(methodcaller('strip')) daba operator.methodcaller; con él se
        # llamaba str.format nativo (sin reescritura). Hoy da 'function'.
        self._refused(
            "from operator import methodcaller\n"
            "MC = type(methodcaller('strip'))\n"
            "m = MC('format', user)\n"
            "result = {'data': [{'v': m('{0.__class__}')}]}\n")

    def test_type_itemgetter_class(self):
        # type(itemgetter('x')) ya no da la clase nativa operator.itemgetter:
        # la fachada devuelve una función, así que type() da 'function' y
        # llamarla como constructor (dos argumentos) falla.
        self._refused(
            "from operator import itemgetter\n"
            "IG = type(itemgetter(0))\n"
            "g = IG('a', 'b')\n"
            "result = {'data': [{'v': str(g({'a': 1, 'b': 2}))}]}\n")

    # ── Positivos de no regresión: las fachadas siguen sirviendo ─────────────

    def test_attrgetter_sorted_key(self):
        row = self._row(
            "from operator import attrgetter\n"
            "recs = env['res.country'].search([], limit=5)\n"
            "s = sorted(recs, key=attrgetter('name'))\n"
            "result = {'data': [{'v': s[0].name if s else ''}]}\n")
        self.assertTrue(row['v'])

    def test_attrgetter_multiple_paths(self):
        row = self._row(
            "from operator import attrgetter\n"
            "g = attrgetter('login', 'id')\n"
            "pair = g(user)\n"
            "result = {'data': [{'v': pair[0], 'i': pair[1]}]}\n")
        self.assertEqual(row['v'], self.admin.login)
        self.assertEqual(row['i'], self.admin.id)

    def test_attrgetter_dotted_path(self):
        row = self._row(
            "from operator import attrgetter\n"
            "g = attrgetter('partner_id.name')\n"
            "result = {'data': [{'v': g(user)}]}\n")
        self.assertEqual(row['v'], self.admin.partner_id.name)

    def test_methodcaller_legit(self):
        row = self._row(
            "from operator import methodcaller\n"
            "g = methodcaller('upper')\n"
            "result = {'data': [{'v': g('hola')}]}\n")
        self.assertEqual(row['v'], 'HOLA')

    def test_itemgetter_legit(self):
        # Subíndice y uso como key= siguen funcionando con la fachada-función.
        row = self._row(
            "from operator import itemgetter\n"
            "rows = [{'n': 'b', 'k': 2}, {'n': 'a', 'k': 1}]\n"
            "s = sorted(rows, key=itemgetter('n'))\n"
            "result = {'data': [{'v': s[0]['n'], 'k': itemgetter('k')(s[0])}]}\n")
        self.assertEqual(row['v'], 'a')
        self.assertEqual(row['k'], 1)


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesSkillFormat(_SegesSecretCase):
    """CRÍTICO 2: la vía de skills (bootstrap_skill_code_body) reescribe .format
    igual que relaxaicode."""

    def test_skill_format_blocked(self):
        # Plantilla C1 en variable por la vía de skills: el formateador propio la
        # bloquea (antes compilaba con compile() normal y la dejaba pasar).
        diag = {}
        res = bootstrap_skill_code_body(
            self.env,
            "t = '{0.__class__}'\n"
            "result = {'data': [{'v': t.format(user)}]}\n",
            skill_code='seges_neg', diag=diag)
        self.assertIsNone(res)
        self._no_leak(json.dumps(diag, default=str))

    def test_skill_format_ok(self):
        # Skill normal: plantilla con campo público, sigue funcionando.
        res = bootstrap_skill_code_body(
            self.env,
            "result = {'data': [{'v': '{0.login}'.format(user)}]}\n",
            skill_code='seges_pos', diag={})
        self.assertIsInstance(res, dict)
        self.assertEqual(res['data'][0]['v'], self.env.user.login)

    def _no_leak(self, text):
        self.assertFalse(self.secret in text, 'filtra')
        for name in LEAK_NAMES:
            self.assertFalse(name in text, 'filtra')
