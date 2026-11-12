# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 18 (tests de la fase 3b sobre 3.1.973: confirmación de V1 a V4). Ver docs/pendiente/parches_pns_ai.md
# Seges: parche 18 (tests de la fase 3b sobre 3.1.973: diseño de O1, B y B2). Ver docs/pendiente/parches_pns_ai.md
"""Confirmación de V1 a V4 (propuesta de la fase 3, «Inventario de la decisión 2»).

Todo por la herramienta real (``tool_relaxaicode`` con la caja A real: cursor propio,
READ ONLY y marcado), como un usuario interno sin Ajustes ni AI Administrator.

**Datos confirmados.** La caja A abre su propio cursor y solo ve lo confirmado, como en
producción. ``setUpClass`` crea y confirma los datos con un cursor aparte en la BD de tests
de ``odoo-dev tests``, que es nueva en cada batería y se borra al acabar. ``tearDownClass``
los borra, y lo hace también ``setUpClass`` si falla a medias. Los secretos son aleatorios
en cada ejecución y no se imprimen nunca: los asserts solo dicen «filtra».

**Caché.** Cada test empieza con la caché del hilo vacía y comprueba que el secreto no está
en ella: solo puede llegar por la vía que se prueba. Cada vía tiene un control (sin el
cálculo, la lectura se rechaza) y un positivo (el cálculo se alcanza desde el sandbox).

**Esperado sobre el código actual** (sin O1): F en los tests de vía donde la vía existe.

**Diseño (parche 18):** con O1, B y B2 pasan todos. Los ``test_o1_*`` prueban los enganches
de O1 (negativos tras ``totp_enabled``, ACL del modelo y positivos); los ``test_b_*`` miden
la caché del hilo directamente (``env.cache.contains``), no a través del sandbox, para que
O1 no tape a B. El ``asker`` tiene ``base.group_allow_export``: sin él, ``export_data``
se rechaza antes de leer nada (``odoo/models.py:958-959``).
"""
import json
import secrets

import odoo
from odoo import SUPERUSER_ID, api, fields
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import get_db_name, new_test_user
from odoo.tools import mute_logger

from odoo.addons.pns_ai_mcp.controllers.controller_helpers import open_readonly_env
from odoo.addons.pns_ai_mcp.controllers.relaxaicode_models import _score_record_fit
from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import tool_relaxaicode
from odoo.addons.pns_ai_mcp.tests.seges_common import _StubController

PREFIX = 'seges_3b_v'
REFUSED = 'holds a credential'
RESULT_V = "result = {'data': [{'v': str(v)}]}\n"
# Marca de «se llega a la línea siguiente», partida para que no salga en el código ni en un error.
REACHED = "result = {'data': [{'v': 'le' + 'ido'}]}\n"


def _payload(text):
    """``result`` de la herramienta como dict (solo para los positivos, que no llevan secretos)."""
    return json.loads(json.loads(text)['content'][0]['text'])


class _SegesBoxAViasCase(TransactionCase):

    # ── Datos confirmados (cursor aparte) ────────────────────────────────────

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Prefijo distinguible + 32 hexadecimales aleatorios: se pueden contar en el log
        # sin conocer el valor. totp_enabled, signup_valid, user_has_mcp_api_key y
        # auth_call_preview solo miran que no estén vacíos.
        cls.secret = {
            'totp': f'seges-3b-totp-{secrets.token_hex(16)}',
            'signup': f'seges-3b-st-{secrets.token_hex(16)}',
            'auth': f'seges-3b-tok-{secrets.token_hex(16)}',
            'hash': f'seges-3b-h-{secrets.token_hex(16)}',
            'pk': f'seges-3b-pk-{secrets.token_hex(16)}',
            # P-22: credenciales en claro de modelos que el fabricante cierra en su puerta.
            'p22_pin': f'seges-3b-p22-{secrets.token_hex(16)}',
            'p22_sup': f'seges-3b-p22-{secrets.token_hex(16)}',
            'p22_gen': f'seges-3b-p22-{secrets.token_hex(16)}',
            'p22_man': f'seges-3b-p22-{secrets.token_hex(16)}',
            'p22_tok': f'seges-3b-p22-{secrets.token_hex(16)}',
        }
        cls.rid = {}
        try:
            cls._create_committed()
        except Exception:
            cls._remove_committed()
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            cls._remove_committed()
        finally:
            super().tearDownClass()

    @classmethod
    def _create_committed(cls):
        registry = odoo.registry(get_db_name())
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            asker = new_test_user(env, login=PREFIX + '_asker',
                                  groups='base.group_user,base.group_allow_export')
            cls.rid['asker'] = asker.id
            cls.rid['asker_partner'] = asker.partner_id.id
            target = new_test_user(env, login=PREFIX + '_target', groups='base.group_user')
            cls.rid['target'] = target.id
            cls.rid['target_partner'] = target.partner_id.id
            contact = env['res.partner'].create({'name': 'Seges 3b contacto'})
            cls.rid['contact'] = contact.id
            server = env['ai.api.server'].create({
                'name': 'Seges 3b', 'code': PREFIX,
                'base_url': 'https://seges.invalid/api', 'auth_type': 'bearer',
            })
            cls.rid['server'] = server.id
            mcp = env['ai.mcp.user'].search([('user_id', '=', target.id)], limit=1) \
                or env['ai.mcp.user'].create({'user_id': target.id})
            cls.rid['mcp'] = mcp.id
            provider = env['ai.provider'].create({
                'name': 'Seges 3b', 'endpoint': 'https://seges.invalid/v1/chat/completions',
            })
            cls.rid['provider'] = provider.id
            aiadm = new_test_user(env, login=PREFIX + '_aiadm',
                                  groups='base.group_user,pns_ai_mcp.group_ai_admin')
            cls.rid['aiadm'] = aiadm.id
            cls.rid['aiadm_partner'] = aiadm.partner_id.id
            ask = env['ai.key.pin.ask'].create({'login': PREFIX + '_target'})
            cls.rid['p22_ask'] = ask.id
            wiz = env['ai.api.key.wizard'].create({'mcp_user_id': mcp.id})
            cls.rid['p22_wiz'] = wiz.id
            # Los secretos, aparte y sin el log de SQL: un «bad query» imprimiría los valores.
            with mute_logger('odoo.sql_db'):
                if 'totp_secret' in target._fields:
                    target.write({'totp_secret': cls.secret['totp']})
                # V4 separada de signup_url (core): sin signup_type, la URL no lleva el token.
                if 'signup_token' in contact._fields:
                    contact.write({
                        'signup_token': cls.secret['signup'],
                        'signup_type': False,
                        'signup_expiration': False,
                    })
                server.write({'auth_token': cls.secret['auth']})
                mcp.write({'mcp_api_key_hash': cls.secret['hash']})
                provider.write({'api_key': cls.secret['pk']})
                ask.write({'pin': cls.secret['p22_pin'], 'supplied_key': cls.secret['p22_sup']})
                wiz.write({'generated_key': cls.secret['p22_gen'],
                           'manual_key': cls.secret['p22_man']})
                desk = env['ai.key.pin.desk'].create({
                    'token': cls.secret['p22_tok'], 'user_id': aiadm.id,
                    'last_seen': fields.Datetime.now(),
                })
                cls.rid['p22_desk'] = desk.id
                env['base'].flush()
            cr.commit()  # pylint: disable=invalid-commit

    @classmethod
    def _remove_committed(cls):
        if not cls.rid:
            return
        registry = odoo.registry(get_db_name())
        order = (
            ('p22_wiz', 'ai.api.key.wizard'), ('p22_ask', 'ai.key.pin.ask'),
            ('p22_desk', 'ai.key.pin.desk'),
            ('mcp', 'ai.mcp.user'), ('server', 'ai.api.server'), ('provider', 'ai.provider'),
            ('target', 'res.users'), ('asker', 'res.users'),
            ('aiadm', 'res.users'),
            ('contact', 'res.partner'), ('target_partner', 'res.partner'),
            ('asker_partner', 'res.partner'), ('aiadm_partner', 'res.partner'),
        )
        left = []
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            for key, model in order:
                if not cls.rid.get(key):
                    continue
                rec = env[model].browse(cls.rid[key]).exists()
                if not rec:
                    continue
                try:
                    with cr.savepoint(), mute_logger('odoo.sql_db'):
                        rec.unlink()
                except Exception:  # pylint: disable=broad-exception-caught
                    # Si una FK impide borrarlo: sin secreto y archivado.
                    try:
                        with cr.savepoint(), mute_logger('odoo.sql_db'):
                            cls._scrub(rec)
                    except Exception:  # pylint: disable=broad-exception-caught
                        left.append(key)
            # Lo que se haya podido borrar se confirma siempre.
            cr.commit()  # pylint: disable=invalid-commit
        cls.rid = {}
        if left:
            # Solo nombres de clave, nunca valores.
            raise AssertionError('limpieza incompleta: ' + ', '.join(left))

    @staticmethod
    def _scrub(rec):
        vals = {name: False for name in (
            'totp_secret', 'signup_token', 'auth_token', 'mcp_api_key_hash', 'api_key',
            'pin', 'supplied_key', 'generated_key', 'manual_key')
            if name in rec._fields}
        if 'active' in rec._fields:
            vals['active'] = False
        if vals:
            rec.write(vals)

    # ── Por test ─────────────────────────────────────────────────────────────

    def setUp(self):
        super().setUp()
        self.asker = self.env['res.users'].browse(self.rid['asker'])
        for xmlid in ('base.group_system', 'base.group_erp_manager',
                      'pns_ai_mcp.group_ai_admin'):
            self.assertNotIn(self.env.ref(xmlid), self.asker.groups_id, xmlid)
        self.assertIn(self.env.ref('base.group_allow_export'), self.asker.groups_id)
        # La caché del hilo, vacía: lo de setUpClass o de otros tests no cuenta.
        self.env['base'].flush()
        self.env['base'].invalidate_cache()

    def _not_cached(self, model, rid, fname):
        rec = self.env[model].browse(rid)
        self.assertFalse(
            self.env.cache.contains(rec, rec._fields[fname]),
            'precondición: el secreto ya estaba en la caché')

    def _tool(self, code, user=None, stub_cls=_StubController):
        stub = stub_cls(self.env(user=user or self.asker))
        resp = tool_relaxaicode(stub, {'code': code})
        return json.dumps(resp, default=str)

    def _no_leak(self, text, key):
        # Nunca assertIn/assertNotIn con el secreto: el mensaje lo imprimiría.
        self.assertFalse(self.secret[key] in text, 'filtra')

    def _refused(self, text, key):
        self._no_leak(text, key)
        self.assertTrue('"isError": true' in text, 'no se rechaza')
        self.assertTrue(REFUSED in text, 'se rechaza, pero no por el guardián')

    def _reached(self, text, flag):
        self.assertFalse('"isError": true' in text, 'la vía no se alcanza desde el sandbox')
        self.assertIs(_payload(text)['data'][0][flag], True, 'el cálculo no da lo esperado')

    def _refused_not_reached(self, text):
        self.assertTrue('"isError": true' in text, 'no se rechaza')
        self.assertFalse('leido' in text, 'se llega a la línea siguiente')

    def _box_a(self, user=None):
        """La caja A real (open_readonly_env), que se cierra al acabar el test."""
        ro_env, ro_cr = open_readonly_env(self.env(user=user or self.asker))

        def _close():
            ro_cr.rollback()
            ro_cr.close()
        self.addCleanup(_close)
        return ro_env


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesBoxAVias(_SegesBoxAViasCase):  # pylint: disable=too-many-public-methods

    # ── V3: res.users.totp_secret por la caché que deja totp_enabled ────────

    def _skip_v3(self):
        if 'totp_secret' not in self.env['res.users']._fields:
            self.skipTest('auth_totp no instalado')

    def _v3(self, read):
        return (
            f"u = env['res.users'].browse({self.rid['target']})\n"
            "on = u.totp_enabled\n"
            f"v = {read}\n" + RESULT_V)

    def test_v3_control_direct_read_refused(self):
        self._skip_v3()
        self._not_cached('res.users', self.rid['target'], 'totp_secret')
        text = self._tool(
            f"v = env['res.users'].browse({self.rid['target']}).totp_secret\n" + RESULT_V)
        self._refused(text, 'totp')

    def test_v3_reachable(self):
        self._skip_v3()
        text = self._tool(
            f"on = env['res.users'].browse({self.rid['target']}).totp_enabled\n"
            "result = {'data': [{'on': bool(on)}]}\n")
        self._reached(text, 'on')

    def test_decision2_v3_browse(self):
        """Decisión 2 con V3: cálculo en sudo y después browse(id).<secreto>."""
        self._skip_v3()
        self._not_cached('res.users', self.rid['target'], 'totp_secret')
        text = self._tool(self._v3(
            f"env['res.users'].browse({self.rid['target']}).totp_secret"))
        self._refused(text, 'totp')

    def test_v3_getitem(self):
        self._skip_v3()
        self._not_cached('res.users', self.rid['target'], 'totp_secret')
        self._refused(self._tool(self._v3("u['totp_secret']")), 'totp')

    def test_v3_mapped(self):
        self._skip_v3()
        self._not_cached('res.users', self.rid['target'], 'totp_secret')
        self._refused(self._tool(self._v3("u.mapped('totp_secret')")), 'totp')

    def test_v3_recordset_as_result(self):
        """El motor convierte el resultado: un recordset devuelto no saca el secreto.

        Esperado: pasa también sin O1 (el resultado se serializa con str(), que da
        «res.users(id,)», relaxaicode_outcome.py:497).
        """
        self._skip_v3()
        self._not_cached('res.users', self.rid['target'], 'totp_secret')
        tid = self.rid['target']
        head = f"u = env['res.users'].browse({tid})\non = u.totp_enabled\n"
        for tail in (f"result = {{'data': [{{'id': {tid}, 'u': u}}]}}\n", "result = u\n"):
            with self.subTest(code=tail.strip()):
                self._no_leak(self._tool(head + tail), 'totp')

    # ── V4: res.partner.signup_token por la caché que deja signup_valid ─────

    def _skip_v4(self):
        if 'signup_token' not in self.env['res.partner']._fields:
            self.skipTest('auth_signup no instalado')

    def _v4(self, read):
        return (
            f"p = env['res.partner'].browse({self.rid['contact']})\n"
            "ok = p.signup_valid\n"
            f"v = {read}\n" + RESULT_V)

    def test_v4_control_direct_read_refused(self):
        self._skip_v4()
        self._not_cached('res.partner', self.rid['contact'], 'signup_token')
        text = self._tool(
            f"v = env['res.partner'].browse({self.rid['contact']}).signup_token\n" + RESULT_V)
        self._refused(text, 'signup')

    def test_v4_reachable(self):
        self._skip_v4()
        text = self._tool(
            f"ok = env['res.partner'].browse({self.rid['contact']}).signup_valid\n"
            "result = {'data': [{'ok': bool(ok)}]}\n")
        self._reached(text, 'ok')

    def test_decision2_v4_browse(self):
        """Decisión 2 con V4: cálculo en sudo y después browse(id).<secreto>."""
        self._skip_v4()
        self._not_cached('res.partner', self.rid['contact'], 'signup_token')
        text = self._tool(self._v4(
            f"env['res.partner'].browse({self.rid['contact']}).signup_token"))
        self._refused(text, 'signup')

    def test_v4_getitem(self):
        self._skip_v4()
        self._not_cached('res.partner', self.rid['contact'], 'signup_token')
        self._refused(self._tool(self._v4("p['signup_token']")), 'signup')

    def test_v4_mapped(self):
        self._skip_v4()
        self._not_cached('res.partner', self.rid['contact'], 'signup_token')
        self._refused(self._tool(self._v4("p.mapped('signup_token')")), 'signup')

    # ── V1: ai.api.server.auth_token por la caché que deja auth_call_preview ─

    def _server(self):
        return (
            "s = env['mail.template.preview'].new("
            f"{{'resource_ref': 'ai.api.server,{self.rid['server']}'}}).resource_ref\n")

    def _v1(self, read):
        return self._server() + f"pv = s.auth_call_preview\nv = {read}\n" + RESULT_V

    def test_v1_reachable(self):
        text = self._tool(self._server() + "pv = s.auth_call_preview\n"
                          "result = {'data': [{'pv': bool(pv)}]}\n")
        self._reached(text, 'pv')

    def test_v1_control_getitem_refused(self):
        self._not_cached('ai.api.server', self.rid['server'], 'auth_token')
        text = self._tool(self._server() + "v = s['auth_token']\n" + RESULT_V)
        self._refused(text, 'auth')

    def test_v1_literal_attr_refused(self):
        """No regresión del fabricante: .auth_token literal se rechaza por nombre."""
        self._not_cached('ai.api.server', self.rid['server'], 'auth_token')
        text = self._tool(self._v1("s.auth_token"))
        self._no_leak(text, 'auth')
        self.assertTrue('"isError": true' in text, 'no se rechaza')

    def test_v1_getitem(self):
        self._not_cached('ai.api.server', self.rid['server'], 'auth_token')
        self._refused(self._tool(self._v1("s['auth_token']")), 'auth')

    def test_v1_mapped(self):
        self._not_cached('ai.api.server', self.rid['server'], 'auth_token')
        self._refused(self._tool(self._v1("s.mapped('auth_token')")), 'auth')

    # ── V2: ai.mcp.user.mcp_api_key_hash por la caché de user_has_mcp_api_key ─

    def _mcp(self):
        return (
            "m = env['mail.template.preview'].new("
            f"{{'resource_ref': 'ai.mcp.user,{self.rid['mcp']}'}}).resource_ref\n")

    def _has_key(self):
        return f"k = m.user_has_mcp_api_key(env['res.users'].browse({self.rid['target']}))\n"

    def _v2(self, read):
        return self._mcp() + self._has_key() + f"v = {read}\n" + RESULT_V

    def test_v2_reachable(self):
        text = self._tool(self._mcp() + self._has_key()
                          + "result = {'data': [{'k': bool(k)}]}\n")
        self._reached(text, 'k')

    def test_v2_control_getitem_refused(self):
        self._not_cached('ai.mcp.user', self.rid['mcp'], 'mcp_api_key_hash')
        text = self._tool(self._mcp() + "v = m['mcp_api_key_hash']\n" + RESULT_V)
        self._refused(text, 'hash')

    def test_v2_getitem(self):
        self._not_cached('ai.mcp.user', self.rid['mcp'], 'mcp_api_key_hash')
        self._refused(self._tool(self._v2("m['mcp_api_key_hash']")), 'hash')

    def test_v2_mapped(self):
        self._not_cached('ai.mcp.user', self.rid['mcp'], 'mcp_api_key_hash')
        self._refused(self._tool(self._v2("m.mapped('mcp_api_key_hash')")), 'hash')

    # ── Camino del cálculo (variante de LIYBEN), con un campo del contenedor ─

    def test_computed_secret_column_refused(self):
        """Un campo calculado no guardado con nombre de secreto no pasa por el guardián.

        En el contenedor, res.users.password/new_password (base/models/res_users.py:288-296,
        _compute_password en :396-399) siempre valen '' : el test no maneja ningún secreto,
        solo comprueba si la lectura se rechaza. Es el mismo camino que totp_secret y
        signup_token en LIYBEN (calculados por SQL).
        """
        for fname in ('password', 'new_password'):
            with self.subTest(field=fname):
                text = self._tool(
                    f"v = env['res.users'].browse({self.rid['target']}).{fname}\n"
                    "result = {'data': [{'v': 'leido'}]}\n")
                self.assertTrue('"isError": true' in text, 'no se rechaza')
                self.assertTrue(REFUSED in text, 'se rechaza, pero no por el guardián')
                self.assertFalse('leido' in text, 'se llega a la línea siguiente')

    # ── O1: otras lecturas del secreto en caché, tras totp_enabled ──────────

    def test_o1_itemgetter_refused(self):
        self._skip_v3()
        self._not_cached('res.users', self.rid['target'], 'totp_secret')
        code = "from operator import itemgetter\n" + self._v3("itemgetter('totp_secret')(u)")
        self._refused(self._tool(code), 'totp')

    def test_o1_sorted_refused(self):
        self._skip_v3()
        self._not_cached('res.users', self.rid['target'], 'totp_secret')
        self._refused(self._tool(self._v3("u.sorted('totp_secret')")), 'totp')

    def test_o1_filtered_refused(self):
        self._skip_v3()
        self._not_cached('res.users', self.rid['target'], 'totp_secret')
        self._refused(self._tool(self._v3("u.filtered('totp_secret')")), 'totp')

    def test_o1_field_mapped_refused(self):
        """Enganche 4: Field.mapped lee la caché sin pasar por __getitem__."""
        self._skip_v3()
        self._not_cached('res.users', self.rid['target'], 'totp_secret')
        text = self._tool(self._v3("u._fields['totp_secret'].mapped(u)"))
        self._no_leak(text, 'totp')
        self.assertTrue('"isError": true' in text, 'no se rechaza')

    def test_o1_str_format_refused(self):
        self._skip_v3()
        self._not_cached('res.users', self.rid['target'], 'totp_secret')
        self._refused(self._tool(self._v3("'{0.totp_secret}'.format(u)")), 'totp')

    def test_o1_field_compute_value_refused(self):
        """Enganche 4: compute_value de totp_enabled deja totp_secret en la caché."""
        self._skip_v3()
        text = self._tool(
            f"u = env['res.users'].browse({self.rid['target']})\n"
            "u._fields['totp_enabled'].compute_value(u)\n" + REACHED)
        self._no_leak(text, 'totp')
        self._refused_not_reached(text)

    def test_o1_field_callable_refused(self):
        """Enganche 4: ningún método de un Field, salvo get_description."""
        head = f"p = env['res.partner'].browse({self.rid['contact']})\n"
        calls = {
            # Binary con adjunto: lee ir.attachment en sudo y lo deja en la caché.
            'read': "p._fields['image_1920'].read(p)\n",
            'recompute': "p._fields['display_name'].recompute(p)\n",
            # Many2one: display_name en sudo del registro que se le pase.
            'convert_to_read': (
                "p._fields['parent_id'].convert_to_read("
                f"env['res.users'].browse({self.rid['target']}), p)\n"),
        }
        for name, call in calls.items():
            with self.subTest(attr=name):
                self._refused_not_reached(self._tool(head + call + REACHED))

    def test_o1_export_data_refused(self):
        self._skip_v3()
        self._not_cached('res.users', self.rid['target'], 'totp_secret')
        self._refused(self._tool(self._v3("u.export_data(['totp_secret'])")), 'totp')

    def test_o1_acl_cached_field_refused(self):
        """ACL del modelo: un campo no secreto en caché, de un modelo sin permiso de lectura."""
        asker_env = self.env(user=self.asker)
        self.assertFalse(
            asker_env['ai.mcp.user'].check_access_rights('read', raise_exception=False),
            'precondición: el asker lee ai.mcp.user')
        # El motor en su, como /mcp al validar la clave (controllers/main.py:845-857).
        self.assertTrue(self.env['ai.mcp.user'].sudo().browse(self.rid['mcp']).user_id)
        text = self._tool(self._mcp() + "v = m['user_id']\n" + REACHED)
        self._refused_not_reached(text)

    # ── O1: positivos ────────────────────────────────────────────────────────

    def test_o1_engine_sudo_in_box_a(self):
        """El motor sigue leyendo en sudo dentro de la caja A real."""
        ro_env = self._box_a()
        provider = ro_env['ai.provider'].browse(self.rid['provider'])
        self.assertTrue(
            provider._api_key_for_inference() == self.secret['pk'],
            'el motor no lee la clave en la caja A')
        self.assertTrue(ro_env['ir.config_parameter'].sudo().get_param('web.base.url'))

    def test_o1_engine_outside_box_a(self):
        asker_env = self.env(user=self.asker)
        provider = asker_env['ai.provider'].browse(self.rid['provider'])
        self.assertTrue(
            provider._api_key_for_inference() == self.secret['pk'],
            'el motor no lee la clave fuera de la caja A')
        server = asker_env['ai.api.server'].browse(self.rid['server'])
        self.assertTrue(
            server._resolve_auth_token() == self.secret['auth'],
            'el motor no lee el token fuera de la caja A')

    def test_o1_icp_row_by_row(self):
        """ir.config_parameter fila a fila: un parámetro que no es secreto se lee."""
        text = self._tool(
            "r = env['ir.config_parameter'].search([('key', '=', 'web.base.url')])\n"
            "result = {'data': [{'a': bool(r.value), 'b': bool(r.mapped('value')[0])}]}\n",
            user=self.env.ref('base.user_admin'))
        self._reached(text, 'a')
        self._reached(text, 'b')

    def test_o1_plain_names_ok(self):
        text = self._tool(
            "from operator import itemgetter\n"
            f"ps = env['res.partner'].browse([{self.rid['contact']}, {self.rid['target_partner']}])\n"
            "a = ps.sorted('name').ids\n"
            "b = ps.filtered('name').ids\n"
            "c = itemgetter('name')(ps[0])\n"
            f"d = env['res.users'].browse({self.rid['target']}).mapped('partner_id.name')\n"
            "result = {'data': [{'a': len(a), 'b': len(b), 'c': bool(c), 'd': len(d)}]}\n")
        self.assertFalse('"isError": true' in text, 'se rechaza una lectura normal')
        row = _payload(text)['data'][0]
        self.assertEqual((row['a'], row['b'], row['c'], row['d']), (2, 2, True, 1))

    def test_o1_score_fit_after_secret_cached(self):
        """_score_record_fit (motor, caja A sin su) sigue puntuando con el secreto en caché."""
        self._skip_v3()
        ro_env = self._box_a()
        user = ro_env['res.users'].browse(self.rid['target'])
        self.assertTrue(user.totp_enabled)  # deja totp_secret en la caché (sudo)
        score = _score_record_fit(ro_env, 'res.users', user.id, {'name': user.name})
        self.assertGreaterEqual(score, 80)

    # ── B: la caché del hilo al abrir la caja A (medida directa) ────────────

    def test_b_open_forgets_secret(self):
        provider = self.env['ai.provider'].sudo().browse(self.rid['provider'])
        field = provider._fields['api_key']
        self.assertTrue(provider.api_key)
        self.assertTrue(self.env.cache.contains(provider, field), 'precondición: sin la clave en caché')
        self._box_a()
        self.assertFalse(self.env.cache.contains(provider, field), 'la clave sigue en la caché')

    def test_b_open_keeps_non_secret(self):
        partner = self.env['res.partner'].browse(self.rid['contact'])
        field = partner._fields['name']
        self.assertTrue(partner.name)
        self.assertTrue(self.env.cache.contains(partner, field), 'precondición: sin el nombre en caché')
        self._box_a()
        self.assertTrue(self.env.cache.contains(partner, field), 'se vacía lo que no es secreto')


    # ── P-22: modelos de credenciales del fabricante, por Reference ─────────

    def test_o1_p22_credential_models_refused(self):
        """Un AI Administrator (con ACL de lectura) no lee esas credenciales en la caja A.

        El fabricante cierra estos modelos en su puerta (env[...]), pero un campo Reference la
        salta. pin, supplied_key, generated_key y manual_key se guardan en claro; el
        display_name del desk es su token (_rec_name). En el desk hay doble barrera: el criterio
        de token en el cálculo (name_get lee record['token']) y la entrada display_name para el
        valor ya en la caché, que es lo que mide este subtest.
        """
        aiadm = self.env['res.users'].browse(self.rid['aiadm'])
        self.assertNotIn(self.env.ref('base.group_system'), aiadm.groups_id)
        cases = (
            ('pin', 'ai.key.pin.ask', 'p22_ask', 'pin', 'p22_pin'),
            ('supplied_key', 'ai.key.pin.ask', 'p22_ask', 'supplied_key', 'p22_sup'),
            ('generated_key', 'ai.api.key.wizard', 'p22_wiz', 'generated_key', 'p22_gen'),
            ('manual_key', 'ai.api.key.wizard', 'p22_wiz', 'manual_key', 'p22_man'),
            ('desk display_name', 'ai.key.pin.desk', 'p22_desk', 'display_name', 'p22_tok'),
        )
        warmed = []
        desk_id = self.rid['p22_desk']

        class _WarmDeskStub(_StubController):
            """Ya en la caja A (B hecho), el motor lee en sudo el display_name del desk.

            Entre aquí y la lectura del sandbox solo corren build_safe_context,
            _fill_run_context y la compilación (tools_relaxaicode.py:178-200): mide O1, no B.
            """

            def _get_readonly_env(self):
                ro_env, ro_cr = _StubController._get_readonly_env(self)
                desk = ro_env['ai.key.pin.desk'].sudo().browse(desk_id)
                loaded = bool(desk.display_name)
                warmed.append(loaded and ro_env.cache.contains(desk, desk._fields['display_name']))
                return ro_env, ro_cr

        for label, model, rkey, fname, skey in cases:
            with self.subTest(field=label):
                self.assertTrue(
                    self.env[model].with_user(aiadm).check_access_rights(
                        'read', raise_exception=False),
                    'precondición: el AI Administrator no tiene ACL de lectura')
                code = (
                    "r = env['mail.template.preview'].new("
                    f"{{'resource_ref': '{model},{self.rid[rkey]}'}}).resource_ref\n"
                    f"v = r.{fname}\n" + RESULT_V)
                if model == 'ai.key.pin.desk':
                    # El valor en caché es lo que justifica la entrada display_name del desk.
                    text = self._tool(code, user=aiadm, stub_cls=_WarmDeskStub)
                    self.assertTrue(
                        warmed == [True],
                        'precondición: el display_name del desk no estaba en la caché')
                else:
                    text = self._tool(code, user=aiadm)
                self._refused(text, skey)

    def test_o1_p22_wizard_shows_key_outside_box_a(self):
        """Fuera de la caja A, el asistente sigue mostrando la clave a quien la genera."""
        aiadm = self.env['res.users'].browse(self.rid['aiadm'])
        wiz = self.env['ai.api.key.wizard'].with_user(aiadm).create({
            'mcp_user_id': self.rid['mcp'], 'confirmed': True,
        })
        wiz.action_generate()
        shown = wiz.read(['generated_key'])[0]['generated_key']
        self.assertTrue(
            bool(shown) and len(shown) == 32, 'el asistente no muestra la clave generada')
