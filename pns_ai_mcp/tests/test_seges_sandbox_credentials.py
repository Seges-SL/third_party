# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 18 (tests de la entrega E2′). Ver docs/pendiente/parches_pns_ai.md
"""Parche 18 (PNS-19): en la caja A, los modelos de credenciales solo dan sus
campos de identificación, se llegue como se llegue (relación, ``env.ref``,
``new()``, campo ``Reference``, ``read``, ``read_group``, dominio) y aunque
se lea en ``sudo``.

Casi todos los tests ponen la marca en el cursor del test (``addCleanup`` la
quita) y vacían de la caché lo que la caja A no puede leer, como hace
``tool_relaxaicode`` con el de la caja A: la caché es una por hilo y la del test
llega llena (``create`` deja ahí la clave). Se lee con ``rec.campo``. Los de la clase
``TestSegesBoxAReal`` usan la herramienta real o la caja A real
(``get_readonly_env``), que abre un cursor propio: ahí solo hay datos
confirmados, así que el secreto es ``database.secret`` y el usuario,
``base.user_admin`` (Ajustes), sin conceder ni confirmar grupos.
"""

import json

from odoo import SUPERUSER_ID, api
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from odoo.addons.pns_ai_mcp.controllers.context_builder import GuardedSandboxEnv
from odoo.addons.pns_ai_mcp.controllers.controller_helpers import get_readonly_env
from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import tool_relaxaicode
from odoo.addons.pns_ai_mcp.models.box_a_guard import BOX_A_MARK, _box_a_clear_cache

API_KEY = 'sk-seges-e2p-19-provider'
SMTP_PASS = 'pw-seges-e2p-19'
TOKEN = 'tok-seges-e2p-19'
REFUSED = 'cannot be read from the RelaxAICode sandbox'


def _field(rec, fname):
    """Lee un campo como lo haría el código del sandbox (``rec.campo``)."""
    return rec[fname]


class _SegesBoxACase(TransactionCase):  # pylint: disable=too-many-instance-attributes

    def setUp(self):
        super().setUp()
        self.aa = new_test_user(
            self.env, login='seges_e2p_19_aa',
            groups='base.group_user,base.group_system,pns_ai_mcp.group_ai_admin',
        )
        su = self.env['base'].sudo().env
        self.provider = su['ai.provider'].create({
            'name': 'Seges E2p 19', 'api_key': API_KEY,
            'endpoint': 'https://seges.invalid/v1/chat/completions',
        })
        self.log = su['ai.log'].create({
            'access_mode': 'read', 'primitive': 'llm', 'endpoint': 'seges-e2p-19',
            'provider_id': self.provider.id, 'user_id': self.aa.id,
        })
        self.server = su['ai.api.server'].create({
            'name': 'Seges E2p 19', 'code': 'seges_e2p_19', 'auth_token': TOKEN,
            'base_url': 'https://seges.invalid/api',
        })
        self.mail_server = su['ir.mail_server'].create({
            'name': 'Seges E2p 19', 'smtp_host': 'seges.invalid',
            'smtp_pass': SMTP_PASS,
        })
        self.message = su['mail.message'].create({
            'body': 'seges e2p 19', 'model': 'res.partner',
            'res_id': self.aa.partner_id.id, 'message_type': 'comment',
            'mail_server_id': self.mail_server.id,
        })
        self.secret_id = su['ir.config_parameter'].search(
            [('key', '=', 'database.secret')]).id
        self.env['base'].flush()
        self.env_aa = self.env(user=self.aa)

    def _mark(self, on=True):
        """Como tool_relaxaicode: la marca y, con ella, la caché sin lo cerrado."""
        setattr(self.env.cr, BOX_A_MARK, on)
        self.addCleanup(setattr, self.env.cr, BOX_A_MARK, False)
        if on:
            _box_a_clear_cache(self.env)


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesSandboxCredentials(_SegesBoxACase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super().setUp()
        self._mark()

    def test_gate_env_getitem(self):
        with self.assertRaises(KeyError):
            _field(GuardedSandboxEnv(self.env_aa), 'ai.provider')

    def test_env_ref_agent_provider_key(self):
        agent = self.env_aa.ref('pns_ai_mcp.ai_agent_admin')
        self.env['ai.agent.provider'].sudo().create({
            'agent_id': agent.id, 'provider_id': self.provider.id})
        with self.assertRaisesRegex(AccessError, REFUSED):
            agent.provider_ids.mapped('provider_id.api_key')
        self.assertIn('Seges E2p 19', agent.provider_ids.mapped('provider_id.name'))

    def test_new_many2one(self):
        rec = self.env_aa['ai.log'].new({'provider_id': self.provider.id})
        with self.assertRaisesRegex(AccessError, REFUSED):
            _field(rec.provider_id, 'api_key')

    def test_reference_field(self):
        rec = self.env_aa['mail.template.preview'].new(
            {'resource_ref': f'ai.provider,{self.provider.id}'})
        with self.assertRaisesRegex(AccessError, REFUSED):
            _field(rec.resource_ref, 'api_key')

    def test_sudo_does_not_lift(self):
        log = self.env_aa['ai.log'].sudo().browse(self.log.id)
        with self.assertRaisesRegex(AccessError, REFUSED):
            _field(log.provider_id, 'api_key')

    def test_read_group(self):
        with self.assertRaisesRegex(AccessError, REFUSED):
            self.env_aa['ai.provider'].read_group([], ['api_key'], ['api_key'])
        groups = self.env_aa['ai.log'].read_group(
            [('id', '=', self.log.id)], ['provider_id'], ['provider_id'])
        self.assertEqual(groups[0]['provider_id'][1], 'Seges E2p 19')

    def test_display_name(self):
        log = self.env_aa['ai.log'].browse(self.log.id)
        self.assertEqual(log.provider_id.display_name, 'Seges E2p 19')

    def test_related_field(self):
        wiz = self.env_aa['ai.openapi.spec.generate.wizard'].new(
            {'server_id': self.server.id})
        with self.assertRaisesRegex(AccessError, REFUSED):
            _field(wiz, 'base_url')

    def test_search_oracle(self):
        with self.assertRaisesRegex(AccessError, REFUSED):
            self.env_aa['ai.log'].search_count(
                [('provider_id.api_key', '=like', 's%')])

    def test_prefetch_no_secret(self):
        log = self.env_aa['ai.log'].browse(self.log.id)
        self.assertEqual(log.provider_id.name, 'Seges E2p 19')
        field = self.provider._fields['api_key']
        self.assertFalse(self.env.cache.contains(self.provider, field))

    def test_mail_server_secret(self):
        msg = self.env_aa['mail.message'].browse(self.message.id)
        with self.assertRaisesRegex(AccessError, REFUSED):
            _field(msg.mail_server_id, 'smtp_pass')
        self.assertEqual(msg.mail_server_id.name, 'Seges E2p 19')

    def test_icp_blocked_key(self):
        rec = self.env_aa['mail.template.preview'].new(
            {'resource_ref': f'ir.config_parameter,{self.secret_id}'})
        with self.assertRaisesRegex(AccessError, REFUSED):
            _field(rec.resource_ref, 'value')

    def test_icp_cached_get_param(self):
        icp = self.env_aa['ir.config_parameter'].sudo()
        setattr(self.env.cr, BOX_A_MARK, False)
        self.assertTrue(icp.get_param('database.secret'))
        setattr(self.env.cr, BOX_A_MARK, True)
        with self.assertRaisesRegex(AccessError, REFUSED):
            icp.get_param('database.secret')

    def test_icp_value_search_refused(self):
        with self.assertRaisesRegex(AccessError, REFUSED):
            self.env_aa['ir.config_parameter'].search_count([
                ('key', '=', 'database.secret'), ('value', '=like', 'a%')])

    # Read_group con alias: 'alias:max(campo)' lee el campo con otro nombre.

    def test_read_group_alias_provider(self):
        # groupby con campos permitidos: el rechazo es por el alias.
        for spec, groupby in (('display_name:max(api_key)', ['name']),
                              ('name:max(api_key)', ['id'])):
            with self.subTest(spec=spec):
                with self.assertRaisesRegex(AccessError, REFUSED):
                    self.env_aa['ai.provider'].read_group(
                        [('id', '=', self.provider.id)], [spec], groupby)

    def test_read_group_alias_icp(self):
        ICP = self.env_aa['ir.config_parameter']
        for spec, groupby in (('display_name:max(value)', ['key']),
                              ('key:max(value)', ['id']),
                              ('value:max(key)', ['id'])):
            with self.subTest(spec=spec):
                with self.assertRaisesRegex(AccessError, REFUSED):
                    ICP.read_group([('key', '=', 'database.secret')], [spec], groupby)

    def test_read_group_alias_allowed(self):
        groups = self.env_aa['ai.provider'].read_group(
            [('id', '=', self.provider.id)], ['display_name:count(id)'], ['name'])
        self.assertEqual(groups[0]['name'], 'Seges E2p 19')
        self.assertEqual(groups[0]['display_name'], 1)

    # Ids que no son enteros: el SQL encuentra la misma fila.

    def test_icp_float_id(self):
        rec = self.env_aa['ir.config_parameter'].browse([float(self.secret_id)])
        with self.assertRaisesRegex(AccessError, REFUSED):
            self.assertFalse(bool(rec.value))
        with self.assertRaisesRegex(AccessError, REFUSED):
            rec.read(['value'])

    def test_icp_str_id(self):
        rec = self.env_aa['ir.config_parameter'].browse(str(self.secret_id))
        with self.assertRaisesRegex(AccessError, REFUSED):
            self.assertFalse(bool(rec.value))

    def test_icp_new_origin(self):
        ICP = self.env_aa['ir.config_parameter']
        for origin in (ICP.browse(self.secret_id), ICP.browse([float(self.secret_id)])):
            with self.subTest(origin=origin._ids):
                rec = ICP.new({}, origin=origin)
                with self.assertRaisesRegex(AccessError, REFUSED):
                    self.assertFalse(bool(rec.value))

    def test_icp_int_id_allowed_key(self):
        url = self.env_aa['ir.config_parameter'].search([('key', '=', 'web.base.url')])
        self.assertTrue(url.value)

    def test_icp_allowed_key(self):
        self.assertTrue(
            self.env_aa['ir.config_parameter'].sudo().get_param('web.base.url'))

    # No regresión: con la marca, lo que no es secreto se sigue leyendo.

    def test_log_read_no_fields(self):
        row = self.env_aa['ai.log'].browse(self.log.id).read()[0]
        self.assertEqual(row['provider_id'], (self.provider.id, 'Seges E2p 19'))

    def test_log_search_read_no_fields(self):
        rows = self.env_aa['ai.log'].search_read([('id', '=', self.log.id)], limit=1)
        self.assertEqual(rows[0]['provider_id'], (self.provider.id, 'Seges E2p 19'))

    def test_message_search_read_no_fields(self):
        rows = self.env_aa['mail.message'].search_read(
            [('id', '=', self.message.id), ('mail_server_id', '!=', False)], limit=1)
        self.assertEqual(
            rows[0]['mail_server_id'], (self.mail_server.id, 'Seges E2p 19'))

    def test_provider_read_no_fields(self):
        row = self.env_aa['ai.provider'].browse(self.provider.id).read()[0]
        self.assertEqual(set(row), {'id', 'display_name', 'name'})
        self.assertEqual(row['name'], 'Seges E2p 19')


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesOutsideBoxA(_SegesBoxACase):

    def test_outside_box_a_chatboo_reads_provider(self):
        """Sin la marca, el motor de un usuario de chat sigue leyendo la clave."""
        chat = new_test_user(
            self.env, login='seges_e2p_19_chat',
            groups='base.group_user,pns_ai_mcp.group_ai_conversational',
        )
        agent = self.env.ref('pns_ai_mcp.ai_agent_admin')
        self.env['ai.agent.provider'].sudo().create({
            'agent_id': agent.id, 'provider_id': self.provider.id,
            'priority': -100})
        engine = self.env(user=chat)['ai.execution.engine']
        providers = engine.get_providers_for_agent(agent.code)
        self.assertIn(self.provider.id, providers.ids)
        provider = providers.filtered(lambda p: p.id == self.provider.id)
        self.assertEqual(provider._api_key_for_inference(), API_KEY)


class _StubController:
    """Lo que tool_relaxaicode pide al controlador (como el test e2e del fabricante)."""

    def __init__(self, env):
        self.env = env
        self.cursors = []

    def _get_env_for_operation(self, operation_type='read'):
        return self.env

    def _get_readonly_env(self):
        ro_env, ro_cr = get_readonly_env(self)
        self.cursors.append(ro_cr)
        return ro_env, ro_cr

    def _check_mcp_permissions(self, operation_type):
        return True, ''

    def _cancel_pending_verifications_for_user(self, user_id, reason=''):
        return 0

    def _get_user_locale(self):
        return 'en_US'

    def _get_company_lang(self):
        return False

    def _log_mcp_operation(self, *args, **kwargs):
        return None


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesBoxAReal(TransactionCase):

    def setUp(self):
        super().setUp()
        self.admin = self.env.ref('base.user_admin')
        self.env.cr.execute(
            "SELECT id, value FROM ir_config_parameter WHERE key = 'database.secret'")
        self.secret_id, self.secret = self.env.cr.fetchone()

    def _tool(self, code):
        stub = _StubController(self.env(user=self.admin))
        resp = tool_relaxaicode(stub, {'code': code})
        return stub, json.dumps(resp, default=str)

    def test_box_a_reference_secret_refused(self):
        code = (
            "p = env['mail.template.preview'].new("
            f"{{'resource_ref': 'ir.config_parameter,{self.secret_id}'}})\n"
            "result = {'data': [{'v': p.resource_ref.value}]}\n"
        )
        _stub, text = self._tool(code)
        # assertFalse(... in text, 'filtra'): no vuelca el secreto ni la
        # respuesta entera al log si el assert falla.
        self.assertFalse(self.secret in text, 'filtra')
        self.assertIn('"isError": true', text)
        self.assertIn('cannot be read from the RelaxAICode sandbox', text)

    def test_marker_cleared_after_box_a(self):
        for code in ("result = {'ok': sum([1, 2, 3])}", "result = 1 / 0"):
            stub, _text = self._tool(code)
            self.assertEqual(len(stub.cursors), 1, code)
            self.assertFalse(getattr(stub.cursors[0], BOX_A_MARK, False), code)

    def test_box_a_cannot_lift_mark(self):
        """La ventana del lienzo (_box_a_trusted) y la marca no se alcanzan desde la caja A."""
        attempts = (
            "from odoo.addons.pns_ai_mcp.models.box_a_guard import _box_a_trusted\n"
            "result = 1\n",
            "import odoo\nresult = 1\n",
            "with _box_a_trusted(env.cr):\n    result = 1\n",
            "env.cr._seges_box_a = False\nresult = 1\n",
            "result = getattr(getattr(env, 'c' + 'r'), '_seges' + '_box_a')\n",
        )
        for code in attempts:
            _stub, text = self._tool(code)
            self.assertIn('ERROR (', text, code)
        # El último intento cae por el getattr compuesto, no por un env.cr literal.
        self.assertIn("'_seges_box_a'", text)
        self.assertNotIn("Cannot access 'cr'", text)
        # Control: el mismo camino, con código permitido, sí corre.
        _stub, text = self._tool("result = {'data': [{'v': sum([1, 2, 3])}]}\n")
        self.assertNotIn('ERROR (', text)
        self.assertIn('6', text)

    def test_box_a_engine_cache_before_run(self):
        """El motor lee la clave en el mismo hilo; después, la caja A real no la ve.

        La caché es una por hilo: sin vaciarla al poner la marca, la caja A
        recibiría la clave sin pasar por _fetch_field (ni por la marca).
        """
        provider = self.env['ai.provider'].sudo().create({
            'name': 'Seges E2p 19 engine', 'api_key': API_KEY,
            'endpoint': 'https://seges.invalid/v1/chat/completions',
        })
        self.env['base'].flush()
        self.assertEqual(provider._api_key_for_inference(), API_KEY)
        self.assertTrue(self.env.cache.contains(provider, provider._fields['api_key']))
        # La fila no está confirmada: la caja A solo la alcanza por la caché.
        # new() no comprueba que exista (un campo Reference, sí).
        code = (
            f"p = env['ai.log'].new({{'provider_id': {provider.id}}}).provider_id\n"
            "result = {'data': [{'v': p.api_key}]}\n"
        )
        _stub, text = self._tool(code)
        self.assertNotIn(API_KEY, text)
        self.assertIn(REFUSED, text)

    def test_box_a_cursor_is_marked(self):
        """Con la caja A real (get_readonly_env + marca), el secreto no sale."""
        stub = _StubController(self.env(user=self.admin))
        ro_env, ro_cr = stub._get_readonly_env()
        try:
            setattr(ro_cr, BOX_A_MARK, True)
            _box_a_clear_cache(ro_env)
            preview = ro_env['mail.template.preview'].new(
                {'resource_ref': f'ir.config_parameter,{self.secret_id}'})
            with self.assertRaisesRegex(AccessError, REFUSED):
                _field(preview.resource_ref, 'value')
            # Control en el mismo cursor, sin la marca.
            setattr(ro_cr, BOX_A_MARK, False)
            ro_env.cache.invalidate()
            self.assertEqual(
                api.Environment(ro_cr, SUPERUSER_ID, {})['ir.config_parameter']
                .browse(self.secret_id).value, self.secret)
        finally:
            ro_cr.rollback()
            ro_cr.close()
