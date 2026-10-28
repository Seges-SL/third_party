# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 23 ampliado (tests de la entrega E2′). Ver docs/pendiente/parches_pns_ai.md
"""Parche 23 ampliado (PNS-101): formateador propio de ``str.format`` /
``str.format_map``.

``str.format`` resuelve la cadena de atributos de la plantilla sobre el objeto
real sin pasar por ``guarded_getattr``; con la plantilla en variable el AST no la
ve. El acceso a ``.format`` / ``.format_map`` se reescribe a ``_sandbox_str_attr``
(lo ve el AST sea cual sea el receptor), que liga el formateo a un
``SandboxFormatter`` cuyos campos pasan por ``guarded_getattr``
(``sandbox_forbidden_name``). Además ``format`` / ``format_map`` están en
``sandbox_forbidden_name``, así que no se obtiene el método nativo por
``getattr`` / ``attrgetter`` / ``methodcaller``.

Como en ``TestSegesBoxAReal``: herramienta real, ``base.user_admin`` y el secreto
confirmado ``database.secret``.
"""

import json

from markupsafe import Markup

from odoo.tests import TransactionCase, tagged

from odoo.addons.pns_ai_mcp.controllers.relaxaicode_format_guard import (
    _sandbox_str_attr,
)
from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import tool_relaxaicode
from odoo.addons.pns_ai_mcp.controllers.validators import (
    validate_relaxaicode_source_ast,
)
from odoo.addons.pns_ai_mcp.tests.test_seges_sandbox_credentials import _StubController

ERROR = 'ERROR ('
ENGINE_NAME = '[PROHIBITED:ENGINE_NAME]'
ENGINE = '_sandbox_str_attr'


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesFormatGuard(TransactionCase):

    def setUp(self):
        super().setUp()
        self.admin = self.env.ref('base.user_admin')
        self.env.cr.execute(
            "SELECT value FROM ir_config_parameter WHERE key = 'database.secret'")
        row = self.env.cr.fetchone()
        self.secret = row[0] if row else '__no_secret__'

    def _tool(self, code):
        stub = _StubController(self.env(user=self.admin))
        resp = tool_relaxaicode(stub, {'code': code})
        return json.dumps(resp, default=str)

    def _refused(self, code):
        text = self._tool(code)
        self.assertIn(ERROR, text, code)
        # assertFalse(... in text, 'filtra'): ni el secreto ni la respuesta
        # entera entran en el mensaje del assert (no se vuelcan al log si falla).
        self.assertFalse(self.secret in text, 'filtra')
        for name in ('configmanager', 'admin_passwd', 'db_password',
                     'function', 'ConfigManager', "'config'"):
            self.assertFalse(name in text, 'filtra')
        return text

    def _row(self, code):
        text = self._tool(code)
        self.assertNotIn(ERROR, text, code)
        resp = json.loads(text)
        return json.loads(resp['content'][0]['text'])['data'][0]

    # ── Negativos: la familia C1 por todas sus vías ──────────────────────────

    def test_c1_exact_payload(self):
        # El payload del revisor: .format con plantilla en variable hasta config.
        self._refused(
            "t = '{0.mapped.__func__.__globals__[config][admin_passwd]}'\n"
            "result = {'data': [{'v': t.format(user)}]}\n")

    def test_template_in_variable(self):
        self._refused(
            "t = '{0.__class__}'\nresult = {'data': [{'v': t.format(user)}]}\n")

    def test_template_concatenated(self):
        self._refused(
            "t = '{0.' + '__class__}'\nresult = {'data': [{'v': t.format(user)}]}\n")

    def test_template_from_call(self):
        self._refused(
            "def mk():\n    return '{0.__dict__}'\n"
            "result = {'data': [{'v': mk().format(user)}]}\n")

    def test_bound_method_in_variable(self):
        self._refused(
            "t = '{0.__globals__}'\nf = t.format\n"
            "result = {'data': [{'v': f(user)}]}\n")

    def test_str_format_unbound(self):
        self._refused(
            "result = {'data': [{'v': str.format('{0.__class__}', user)}]}\n")

    def test_getattr_format(self):
        # getattr con nombre literal y con nombre partido: ninguno llega al nativo.
        for expr in ("getattr(t, 'format')", "getattr(t, 'for' + 'mat')"):
            with self.subTest(expr=expr):
                self._refused(
                    "t = '{0.__class__}'\nf = " + expr + "\n"
                    "result = {'data': [{'v': f(user)}]}\n")

    def test_attrgetter_methodcaller_format(self):
        self._refused(
            "from operator import attrgetter\n"
            "t = '{0.__class__}'\nf = attrgetter('format')(t)\n"
            "result = {'data': [{'v': f(user)}]}\n")
        self._refused(
            "from operator import methodcaller\n"
            "result = {'data': [{'v': methodcaller('format', user)('{0.__class__}')}]}\n")

    def test_nested_spec_dunder(self):
        self._refused(
            "t = '{0:{1.__class__}}'\n"
            "result = {'data': [{'v': t.format(5, user)}]}\n")

    def test_format_map_dunder(self):
        self._refused(
            "t = '{x.__class__}'\n"
            "result = {'data': [{'v': t.format_map({'x': user})}]}\n")

    def test_v1_import_formatter(self):
        # from string import Formatter: lo cierra el facade (sandbox_forbidden_name).
        self._refused(
            "from string import Formatter\n"
            "result = {'data': [{'v': Formatter().get_field('0.__class__', (user,), {})}]}\n")

    def test_v2_type_attrgetter(self):
        # type(attrgetter(...)) da el objeto real; su único canal dunder (format
        # con plantilla en variable) queda cerrado.
        self._refused(
            "from operator import attrgetter\n"
            "k = type(attrgetter('id')(user))\n"
            "t = '{0.__init__.__globals__}'\n"
            "result = {'data': [{'v': t.format(k)}]}\n")

    def test_markup_rejected_unit(self):
        # Markup no es alcanzable en el sandbox; se construye aquí. isinstance(Markup)
        # va ANTES que str para no perder el escape; misma excepción que un nombre
        # prohibido.
        with self.assertRaises(AttributeError):
            _sandbox_str_attr(Markup('{0.__class__}'), 'format')
        with self.assertRaises(AttributeError):
            _sandbox_str_attr(Markup('{k}'), 'format_map')

    # ── No regresión: el formateo normal sigue funcionando ───────────────────

    def test_literal_attr(self):
        row = self._row(
            "result = {'data': [{'v': '{0.login}'.format(user)}]}\n")
        self.assertEqual(row['v'], self.admin.login)

    def test_numeric_spec(self):
        row = self._row("result = {'data': [{'v': '{:,.2f}'.format(1234.5)}]}\n")
        self.assertEqual(row['v'], '1,234.50')

    def test_format_map_dict(self):
        row = self._row(
            "result = {'data': [{'v': '{k}'.format_map({'k': 9})}]}\n")
        self.assertEqual(row['v'], '9')

    def test_translated_template_in_variable(self):
        row = self._row(
            "t = 'Hello {0.login}'\n"
            "result = {'data': [{'v': t.format(user)}]}\n")
        self.assertEqual(row['v'], f'Hello {self.admin.login}')

    def test_getitem_mapping(self):
        row = self._row(
            "result = {'data': [{'v': '{0[k]}'.format({'k': 'ok'})}]}\n")
        self.assertEqual(row['v'], 'ok')

    def test_control_sandbox_ok(self):
        row = self._row(
            "result = {'data': [{'v': all([1, 2]), 'u': env.user.login}]}\n")
        self.assertTrue(row['v'])
        self.assertEqual(row['u'], self.admin.login)


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesEngineNames(TransactionCase):
    """Los nombres internos del motor (``_sandbox_str_attr``) se leen, no se ligan:
    si el script los sombrea, la reescritura del AST llamaría a lo suyo."""

    def _engine_refused(self, code):
        valid, error, _write = validate_relaxaicode_source_ast(code)
        self.assertFalse(valid, code)
        self.assertTrue(error.startswith(ENGINE_NAME), error)

    def test_engine_name_store(self):
        self._engine_refused(f"{ENGINE} = len\nresult = 1\n")
        self._engine_refused(f"a, {ENGINE} = 1, 2\nresult = 1\n")
        self._engine_refused(f"{ENGINE} += 1\nresult = 1\n")

    def test_engine_name_del(self):
        self._engine_refused(f"del {ENGINE}\nresult = 1\n")

    def test_engine_name_global(self):
        self._engine_refused(
            f"def f():\n    global {ENGINE}\n    return 1\nresult = f()\n")

    def test_engine_name_nonlocal(self):
        self._engine_refused(
            f"def f():\n    {ENGINE} = 1\n    def g():\n"
            f"        nonlocal {ENGINE}\n        return 1\n"
            "    return g()\nresult = f()\n")

    def test_engine_name_argument(self):
        for head in (f"def f({ENGINE}):", f"def f(*{ENGINE}):",
                     f"def f(*, {ENGINE}=1):", f"def f(**{ENGINE}):"):
            with self.subTest(head=head):
                self._engine_refused(f"{head}\n    return 1\nresult = 1\n")
        self._engine_refused(f"g = lambda {ENGINE}: 1\nresult = g(1)\n")

    def test_engine_name_def_class(self):
        self._engine_refused(f"def {ENGINE}(a, b):\n    return a\nresult = 1\n")
        self._engine_refused(f"class {ENGINE}:\n    pass\nresult = 1\n")

    def test_engine_name_import(self):
        self._engine_refused(f"import math as {ENGINE}\nresult = 1\n")
        self._engine_refused(f"from math import floor as {ENGINE}\nresult = 1\n")

    def test_engine_name_for(self):
        self._engine_refused(f"for {ENGINE} in [1]:\n    pass\nresult = 1\n")
        self._engine_refused(f"result = [1 for {ENGINE} in [1]]\n")

    def test_engine_name_with(self):
        self._engine_refused(f"with x as {ENGINE}:\n    pass\nresult = 1\n")

    def test_engine_name_except(self):
        self._engine_refused(
            f"try:\n    x = 1\nexcept Exception as {ENGINE}:\n    pass\n"
            "result = 1\n")

    def test_engine_name_shadow_tool(self):
        # Por la herramienta real: sombrear el nombre no llega a ejecutarse.
        stub = _StubController(self.env(user=self.env.ref('base.user_admin')))
        text = json.dumps(tool_relaxaicode(stub, {'code': (
            f"{ENGINE} = lambda r, a: getattr(r, a)\n"
            "result = {'data': [{'v': '{0.__class__}'.format(user)}]}\n")}),
            default=str)
        self.assertIn(ERROR, text)
        self.assertIn('ENGINE_NAME', text)
        self.assertNotIn('<class', text)
