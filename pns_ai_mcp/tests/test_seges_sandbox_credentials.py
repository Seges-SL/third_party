# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 18 (tests de la entrega E2′). Ver docs/pendiente/parches_pns_ai.md
# Seges: reescrito para 3.1.973 (fase 3b): criterio del fabricante, O1, B y B2. Ver docs/pendiente/parches_pns_ai.md
"""Parche 18 (PNS-19) sobre 3.1.973: en la caja A, sin su, una credencial no se lee.

El criterio es el del fabricante (``_pns_hidden_column``, ``models/sandbox_secret_read.py``):
la columna secreta se rechaza («holds a credential») y el resto de la fila se lee. Los
modelos que la rama 3879 cerraba enteros ya no se cierran (P-22): ``test_related_field`` y
``test_provider_read_no_fields`` lo reflejan.

Casi todos los tests ponen la marca del fabricante en el cursor del test (``addCleanup`` la
quita) y vacían de la caché las columnas secretas, como ``open_readonly_env`` (B). Los de
``TestSegesBoxAReal`` usan la herramienta real o la caja A real, que abre un cursor propio:
ahí solo hay datos confirmados, así que el secreto es ``database.secret`` y el usuario,
``base.user_admin``.

Los secretos no se imprimen nunca: se comparan con ``assertTrue``/``assertFalse`` sobre una
expresión, no con ``assertEqual``/``assertIn``.
"""

import json
import secrets

from odoo import SUPERUSER_ID, api
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from odoo.addons.pns_ai_mcp.controllers.context_builder import GuardedSandboxEnv
from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import tool_relaxaicode
from odoo.addons.pns_ai_mcp.tests.seges_common import _StubController
from odoo.addons.pns_ai_mcp.utils import sandbox_helpers
from odoo.addons.pns_ai_mcp.utils.sandbox_secrets import (
    SANDBOX_CURSOR_FLAG,
    cached_setting_params,
    secret_param_key,
)
from odoo.addons.pns_ai_mcp.utils.seges_box_a_cache import _seges_forget_secret_columns

API_KEY = f'seges-3b-pk-{secrets.token_hex(16)}'
SMTP_PASS = f'seges-3b-smtp-{secrets.token_hex(16)}'
TOKEN = f'seges-3b-tok-{secrets.token_hex(16)}'
REFUSED = 'holds a credential'
PARAM_REFUSED = 'its key names a credential'
STR_ID_REFUSED = REFUSED + '|Database fetch misses ids .* extra ids'
# Marca de «se llega a la línea siguiente», partida para que no salga en el código ni en un error.
REACHED = "result = {'data': [{'v': 'le' + 'ido'}]}\n"


def _field(rec, fname):
    """Lee un campo como lo haría el código del sandbox (``rec['campo']``)."""
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
        """Como open_readonly_env: la marca del fabricante y, con ella, B."""
        self.env.cr.__dict__[SANDBOX_CURSOR_FLAG] = on
        self.addCleanup(self.env.cr.__dict__.pop, SANDBOX_CURSOR_FLAG, None)
        if on:
            _seges_forget_secret_columns(self.env)

    def _secret_param_values(self):
        """Valores de los parámetros secretos (criterio del fabricante), sin imprimirlos.

        Solo los de 6 caracteres o más: uno corto ('True', '1') aparecería en cualquier texto.
        """
        setting_keys = cached_setting_params(self.env)
        self.env.cr.execute('SELECT key, value FROM ir_config_parameter')
        return [
            value for key, value in self.env.cr.fetchall()
            if value and len(value) >= 6 and secret_param_key(key, setting_keys)
        ]


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesSandboxCredentials(_SegesBoxACase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super().setUp()
        self._mark()

    def test_gate_env_getitem(self):
        # En 3.1.973 ai.provider ya no está cerrado: la puerta sigue para estos.
        for model in ('ai.mcp.user', 'ai.api.server'):
            with self.subTest(model=model), self.assertRaises(KeyError):
                _field(GuardedSandboxEnv(self.env_aa), model)

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
        """P-22: base_url no es una credencial; en 3.1.973 se lee (la rama 3879 lo rechazaba)."""
        wiz = self.env_aa['ai.openapi.spec.generate.wizard'].new(
            {'server_id': self.server.id})
        self.assertEqual(_field(wiz, 'base_url'), 'https://seges.invalid/api')

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
        """get_param sin su se rechaza aunque el valor esté en el ormcache; en su, se olvida."""
        icp = self.env_aa['ir.config_parameter']
        self.env.cr.__dict__[SANDBOX_CURSOR_FLAG] = False
        self.assertTrue(icp.sudo().get_param('database.secret'))
        self.env.cr.__dict__[SANDBOX_CURSOR_FLAG] = True
        with self.assertRaisesRegex(AccessError, PARAM_REFUSED):
            icp.get_param('database.secret')
        # El motor (sudo) sí lo lee, y no queda en la caché (sandbox_secret_read.py:153-163).
        self.assertTrue(icp.sudo().get_param('database.secret'))
        rec = icp.sudo().browse(self.secret_id)
        self.assertFalse(self.env.cache.contains(rec, rec._fields['value']))

    def test_icp_value_search_refused(self):
        with self.assertRaisesRegex(AccessError, REFUSED):
            self.env_aa['ir.config_parameter'].search_count([
                ('key', '=', 'database.secret'), ('value', '=like', 'a%')])

    # Read_group con alias: 'alias:max(campo)' lee el campo con otro nombre.

    def test_read_group_alias_provider(self):
        # groupby con campos permitidos: el rechazo es por el campo agregado.
        for spec, groupby in (('display_name:max(api_key)', ['name']),
                              ('name:max(api_key)', ['id'])):
            with self.subTest(spec=spec):
                with self.assertRaisesRegex(AccessError, REFUSED):
                    self.env_aa['ai.provider'].read_group(
                        [('id', '=', self.provider.id)], [spec], groupby)

    def test_read_group_alias_icp(self):
        ICP = self.env_aa['ir.config_parameter']
        for spec, groupby in (('display_name:max(value)', ['key']),
                              ('key:max(value)', ['id'])):
            with self.subTest(spec=spec):
                with self.assertRaisesRegex(AccessError, REFUSED):
                    ICP.read_group([('key', '=', 'database.secret')], [spec], groupby)
        # 'value:max(key)' no lee value (solo lo usa como alias): se permite y no da ningún secreto.
        # Agrupado por key: con id, Odoo 14 genera un ORDER BY "id" ambiguo (models.py:2385).
        groups = ICP.read_group(
            [('key', '=', 'database.secret')], ['value:max(key)'], ['key'])
        self.assertTrue(groups, 'sin grupos')
        text = json.dumps(groups, default=str)
        self.assertFalse(
            any(value in text for value in self._secret_param_values()),
            'el resultado contiene el valor de un parámetro secreto')

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
        """Id de texto: lo rechaza el guardián del fabricante o, antes, Odoo.

        Al comprobar la fila, el guardián lee ``key`` y la comprobación de tipos de id de
        Odoo («Database fetch misses ids … extra ids») puede cortar antes. Solo esos dos.
        """
        rec = self.env_aa['ir.config_parameter'].browse(str(self.secret_id))
        reached = []
        with self.assertRaisesRegex(AccessError, STR_ID_REFUSED):
            reached.append(rec.value)
        self.assertFalse(bool(reached), 'el valor llega')

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
        """P-22: read() da los campos no secretos del proveedor, sin la clave."""
        row = self.env_aa['ai.provider'].browse(self.provider.id).read()[0]
        self.assertFalse('api_key' in row, 'read() da la clave')
        self.assertFalse(API_KEY in json.dumps(row, default=str), 'filtra')
        self.assertEqual(row['name'], 'Seges E2p 19')

    # B2: lo que un helper de módulo lee en sudo no queda en la caché.

    def test_helper_sudo_read_forgotten(self):
        provider = self.provider
        field = provider._fields['api_key']

        def seges_probe():
            return bool(self.env['ai.provider'].sudo().browse(provider.id).api_key)

        model_cls = type(self.env['res.partner'])
        model_cls.sandbox_helpers = lambda _self: {'seges_probe': seges_probe}
        self.addCleanup(delattr, model_cls, 'sandbox_helpers')
        self.patch(sandbox_helpers, 'iter_provider_model_names', lambda env: ['res.partner'])
        self.patch(sandbox_helpers, 'is_sandbox_helper_provider', lambda env, name: True)
        helpers = sandbox_helpers.collect_sandbox_helpers(self.env)
        self.assertTrue(helpers['seges_probe'](), 'el helper no lee la clave en sudo')
        self.assertFalse(
            self.env.cache.contains(provider, field),
            'la clave leída por el helper sigue en la caché')


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
        self.assertTrue(provider._api_key_for_inference() == API_KEY, 'no da la clave')


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
        self.assertIn(REFUSED, text)

    def test_sandbox_cannot_reach_sudo(self):
        """Sustituye a test_sudo_does_not_lift: el sandbox no llega a su por ningún nombre."""
        rec = f"env['ir.config_parameter'].browse({self.secret_id})"
        attempts = (
            f"v = {rec}.sudo().value\n",
            f"v = getattr({rec}, 'su' + 'do')().value\n",
            f"v = {rec}.with_user(1).value\n",
            f"v = env(su=True)['ir.config_parameter'].browse({self.secret_id}).value\n",
            "v = env.su\n",
        )
        for code in attempts:
            with self.subTest(code=code.strip()):
                _stub, text = self._tool(code + REACHED)
                self.assertFalse(self.secret in text, 'filtra')
                self.assertTrue('"isError": true' in text, 'no se rechaza')
                self.assertFalse('leido' in text, 'se llega a la línea siguiente')

    def test_box_a_cannot_lift_mark(self):
        """La marca del fabricante no se alcanza desde la caja A."""
        attempts = (
            "from odoo.addons.pns_ai_mcp.utils.sandbox_secrets import SANDBOX_CURSOR_FLAG\n"
            "result = 1\n",
            "import odoo\nresult = 1\n",
            "env.cr._pns_ai_sandbox = False\nresult = 1\n",
            "result = getattr(getattr(env, 'c' + 'r'), '_pns' + '_ai_sandbox')\n",
        )
        for code in attempts:
            _stub, text = self._tool(code)
            self.assertIn('ERROR (', text, code)
        # Control: el mismo camino, con código permitido, sí corre.
        _stub, text = self._tool("result = {'data': [{'v': sum([1, 2, 3])}]}\n")
        self.assertNotIn('ERROR (', text)
        self.assertIn('6', text)

    def test_box_a_engine_cache_before_run(self):
        """El motor lee la clave en el mismo hilo; después, la caja A real no la ve.

        La caché es una por hilo: sin vaciarla al abrir la caja A (B), la caja A
        recibiría la clave sin pasar por _fetch_field.
        """
        provider = self.env['ai.provider'].sudo().create({
            'name': 'Seges E2p 19 engine', 'api_key': API_KEY,
            'endpoint': 'https://seges.invalid/v1/chat/completions',
        })
        self.env['base'].flush()
        self.assertTrue(provider._api_key_for_inference() == API_KEY, 'no da la clave')
        self.assertTrue(self.env.cache.contains(provider, provider._fields['api_key']))
        # La fila no está confirmada: la caja A solo la alcanza por la caché.
        # new() no comprueba que exista (un campo Reference, sí).
        code = (
            f"p = env['ai.log'].new({{'provider_id': {provider.id}}}).provider_id\n"
            "result = {'data': [{'v': p.api_key}]}\n"
        )
        _stub, text = self._tool(code)
        self.assertFalse(API_KEY in text, 'filtra')
        self.assertIn(REFUSED, text)

    def test_box_a_cursor_is_marked(self):
        """Con la caja A real (get_readonly_env), el secreto no sale."""
        stub = _StubController(self.env(user=self.admin))
        ro_env, ro_cr = stub._get_readonly_env()
        try:
            self.assertTrue(ro_cr.__dict__.get(SANDBOX_CURSOR_FLAG), 'sin la marca')
            preview = ro_env['mail.template.preview'].new(
                {'resource_ref': f'ir.config_parameter,{self.secret_id}'})
            with self.assertRaisesRegex(AccessError, REFUSED):
                _field(preview.resource_ref, 'value')
            # Control en el mismo cursor, en su (el motor): se lee.
            ro_env.cache.invalidate()
            value = api.Environment(ro_cr, SUPERUSER_ID, {})['ir.config_parameter'] \
                .browse(self.secret_id).value
            self.assertTrue(value == self.secret, 'el motor no lee el parámetro')
        finally:
            ro_cr.rollback()
            ro_cr.close()

    def test_box_a_icp_cache_before_run(self):
        """B con value de ir.config_parameter: medido en la caché, no a través del sandbox."""
        icp = self.env['ir.config_parameter'].sudo().browse(self.secret_id)
        field = icp._fields['value']
        self.assertTrue(icp.value)
        self.assertTrue(self.env.cache.contains(icp, field), 'precondición: sin el valor en caché')
        stub = _StubController(self.env(user=self.admin))
        _ro_env, ro_cr = stub._get_readonly_env()
        try:
            self.assertFalse(self.env.cache.contains(icp, field), 'el valor sigue en la caché')
        finally:
            ro_cr.rollback()
            ro_cr.close()
