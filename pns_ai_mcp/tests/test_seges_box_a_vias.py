# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 18 (tests de la fase 3b sobre 3.1.973: confirmación de V1 a V4). Ver docs/pendiente/parches_pns_ai.md
# Seges: parche 18 (tests de la fase 3b sobre 3.1.973: diseño de O1, B y B2). Ver docs/pendiente/parches_pns_ai.md
# Seges: adaptado a la 17 (fase 2, T3): sin B; los controles, positivos y getitem
# de V1 a V4 los sustituyen las clases TestSegesBoxA* de seges_pruebas_3996
# (test_box_a_secret_cache.py), copiadas al final con el [GUARD] de B2;
# test_o1_acl_cached_field_refused carga el valor en la caché de la caja A;
# flush_all() e invalidate_all(); los documentos que citan las líneas anteriores
# están en 14.0. Ver docs/pendiente/parches_pns_ai.md
# pylint: disable=too-many-lines
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
se rechaza antes de leer nada (``odoo/models.py:1139``).
"""
import contextlib
import hashlib
import json
import logging
import secrets

import odoo
from odoo import SUPERUSER_ID, api, fields
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import get_db_name, new_test_user
from odoo.tools import mute_logger

from odoo.addons.pns_ai_mcp.controllers.controller_helpers import open_readonly_env
from odoo.addons.pns_ai_mcp.controllers.relaxaicode_models import _score_record_fit
from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import tool_relaxaicode
from odoo.addons.pns_ai_mcp.tests.seges_common import _CursorSpy, _StubController
from odoo.addons.pns_ai_mcp.utils import sandbox_helpers, seges_box_a_cache
from odoo.addons.pns_ai_mcp.utils.sandbox_secrets import (
    SECRET_DENIED_PREFIX,
    sandbox_cursor,
    secret_column,
)

_logger = logging.getLogger(__name__)

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
                env.flush_all()
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
        self.env.flush_all()
        self.env.invalidate_all()

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

    def test_decision2_v3_browse(self):
        """Decisión 2 con V3: cálculo en sudo y después browse(id).<secreto>."""
        self._skip_v3()
        self._not_cached('res.users', self.rid['target'], 'totp_secret')
        text = self._tool(self._v3(
            f"env['res.users'].browse({self.rid['target']}).totp_secret"))
        self._refused(text, 'totp')

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

    def test_decision2_v4_browse(self):
        """Decisión 2 con V4: cálculo en sudo y después browse(id).<secreto>."""
        self._skip_v4()
        self._not_cached('res.partner', self.rid['contact'], 'signup_token')
        text = self._tool(self._v4(
            f"env['res.partner'].browse({self.rid['contact']}).signup_token"))
        self._refused(text, 'signup')

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

    def test_v1_literal_attr_refused(self):
        """No regresión del fabricante: .auth_token literal se rechaza por nombre."""
        self._not_cached('ai.api.server', self.rid['server'], 'auth_token')
        text = self._tool(self._v1("s.auth_token"))
        self._no_leak(text, 'auth')
        self.assertTrue('"isError": true' in text, 'no se rechaza')

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

    def test_v2_mapped(self):
        self._not_cached('ai.mcp.user', self.rid['mcp'], 'mcp_api_key_hash')
        self._refused(self._tool(self._v2("m.mapped('mcp_api_key_hash')")), 'hash')

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
        # Seges: adaptado a la 17 (fase 2, T3): la caja A tiene caché propia
        # (odoo/api.py:518-520) y lo que el motor lee en el cursor del test no llega a
        # ella; sin valor en caché, fetch ya comprueba el ACL (odoo/models.py:3859,
        # con _search, y :3861). El motor lee en su dentro de la caja A, como el
        # stub del desk.
        # Ver docs/pendiente/parches_pns_ai.md
        mid = self.rid['mcp']
        warmed = []

        class _WarmMcpStub(_StubController):
            def _get_readonly_env(self):
                ro_env, ro_cr = _StubController._get_readonly_env(self)
                mcp = ro_env['ai.mcp.user'].sudo().browse(mid)
                loaded = bool(mcp.user_id)
                field = mcp._fields['user_id']
                warmed.append(loaded and ro_env.cache.contains(mcp, field))
                return ro_env, ro_cr

        code = self._mcp() + "v = m['user_id']\n" + REACHED
        text = self._tool(code, stub_cls=_WarmMcpStub)
        self.assertTrue(
            warmed == [True],
            'precondición: user_id no estaba en la caché de la caja A')
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

# ── Caja A en la 17 (seges_pruebas_3996, test_box_a_secret_cache.py) ─────────
# Seges: parche 18, copiado de seges_pruebas_3996 (fase 2, T3, decisiones 117 y 164),
# con el [GUARD] de B2 (decisión 165). Ver docs/pendiente/parches_pns_ai.md

TAG = "seges_3996_p18_"
PROBE_TEXT = "seges3996-probe"
FP_CODE = "hashlib.sha256(str({}).encode()).hexdigest()[:16]"
QUIET = {
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_create_nosubscribe": True,
    "mail_notrack": True,
    "no_reset_password": True,
}


def _fp(value):
    """The fingerprint FP_CODE computes in the sandbox: 16 hex of SHA-256."""
    return hashlib.sha256(str(value).encode()).hexdigest()[:16]


def _code(*lines, read=None, flag=None):
    """Sandbox code: ``lines``, then a result with the probe, fp(``read``) and ``flag``.

    The probe fingerprint proves the code ran to its end. It is computed at run
    time, so it never appears in the code or in an error that quotes the code.
    """
    body = list(lines)
    data = ["'probe': " + FP_CODE.format(repr(PROBE_TEXT))]
    if read:
        body.append(f"v = {read}")
        data.append("'fp': " + FP_CODE.format("v"))
    if flag:
        data.append(f"'flag': {flag}")
    body.append("result = {'data': [{" + ", ".join(data) + "}]}")
    return "\n".join(body) + "\n"


def _cache_ids(cache):
    """{field: ids} held by an ORM Cache.

    Cache._data is private; it is read here only to report what a cache holds.
    Context-dependent fields keep one dict per context key.
    """
    found = {}
    for field, field_cache in cache._data.items():
        if not field_cache:
            continue
        if isinstance(next(iter(field_cache)), tuple):
            ids = set()
            for sub in field_cache.values():
                ids.update(sub)
        else:
            ids = set(field_cache)
        if ids:
            found[field] = ids
    return found


class _Run:
    """One call of the real tool: its text, whether it failed, the cursors it opened."""

    def __init__(self, resp, cursors, stub_errors):
        try:
            self.text = resp["content"][0]["text"]
        except (KeyError, IndexError, TypeError):
            self.text = json.dumps(resp, default=str)
        self.is_error = bool(
            (isinstance(resp, dict) and resp.get("isError")) or "ERROR (" in self.text
        )
        self.cursors = cursors
        self.stub_errors = stub_errors

    def outcome(self, fingerprint, model, fname):
        """'read' (the value came out), 'refused' or 'other'.

        'refused' only with the field guard's own text
        (pns_ai_mcp/models/sandbox_secret_read.py:39-45, raised at :75-76). The
        model gate (validators_base.py:407-413) shares SECRET_DENIED_PREFIX and
        the parameter guard (sandbox_secret_read.py:46-51) too: both are 'other'.
        """
        if not self.is_error and fingerprint in self.text:
            return "read"
        denial = f"{SECRET_DENIED_PREFIX}{model}.{fname}: it holds a credential"
        if self.is_error and fingerprint not in self.text and denial in self.text:
            return "refused"
        return "other"


class _OpenProbeStub(_StubController):
    """_StubController that calls ``on_open(ro_env)`` as soon as box A is open.

    Errors of ``on_open`` are kept, not raised: tool_relaxaicode would lose the
    cursor it has not received yet (tools_relaxaicode.py:178 and :271-281).
    """

    def __init__(self, env, on_open=None):
        super().__init__(env)
        self.on_open = on_open
        self.errors = []

    def _get_readonly_env(self):
        ro_env, ro_cr = super()._get_readonly_env()
        if self.on_open:
            try:
                self.on_open(ro_env)
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                self.errors.append(type(exc).__name__)
        return ro_env, ro_cr


class _SegesBoxASecretCase(TransactionCase):
    """Committed tagged rows, the caller on its own cursor and the real tool. No tests."""

    def setUp(self):
        super().setUp()
        self.assertFalse(
            self.registry.in_test_mode(),
            "[SETUP] expected the registry outside test mode (real cursors); "
            "found it in test mode (registry.cursor() would return a TestCursor)",
        )
        self.tag = TAG + secrets.token_hex(4)
        self.secret = {
            key: f"{self.tag}_{key}_{secrets.token_hex(16)}"
            for key in ("auth", "hash", "totp", "signup")
        }
        self.row = {}
        self.user_ids = []
        self.partner_ids = []
        self.spy = _CursorSpy(self)
        self.addCleanup(self._remove_committed)
        self._create_committed()
        self.rec = dict(self.row)

    # -- committed rows ------------------------------------------------------

    def _create_committed(self):
        cr = self.registry.cursor()
        try:
            env = api.Environment(cr, SUPERUSER_ID, {})
            for key in ("asker", "target"):
                user = new_test_user(
                    env, login=f"{self.tag}_{key}", name=f"{self.tag} {key}",
                    groups="base.group_user", context=QUIET,
                )
                self.row[key] = user.id
                self.row[key + "_partner"] = user.partner_id.id
                self.user_ids.append(user.id)
                self.partner_ids.append(user.partner_id.id)
            contact = env["res.partner"].with_context(**QUIET).create(
                {"name": f"{self.tag} contact"}
            )
            self.row["contact"] = contact.id
            self.partner_ids.append(contact.id)
            # No url: an MCP/SSE server adds a URL whitelist entry only for its url
            # (external_server.py:932-950); its detection row is an ai.context.
            server = env["ai.api.server"].create({
                "name": f"{self.tag} server", "code": self.tag, "auth_type": "bearer",
            })
            self.row["server"] = server.id
            mcp = env["ai.mcp.user"].with_context(mcp_skip_ensure_all_users=True).search(
                [("user_id", "=", self.row["target"])], limit=1,
            ) or env["ai.mcp.user"].create({"user_id": self.row["target"]})
            self.row["mcp"] = mcp.id
            # The secrets, without the SQL log: a bad query would print them.
            with mute_logger("odoo.sql_db"):
                server.write({"auth_token": self.secret["auth"]})
                mcp.write({"mcp_api_key_hash": self.secret["hash"]})
                target = env["res.users"].with_context(**QUIET).browse(self.row["target"])
                if "totp_secret" in target._fields:
                    target.write({"totp_secret": self.secret["totp"]})
                if "signup_token" in contact._fields:
                    contact.write({
                        "signup_token": self.secret["signup"],
                        "signup_type": False,
                        "signup_expiration": False,
                    })
                env.flush_all()
            cr.commit()  # pylint: disable=invalid-commit
        finally:
            cr.close()

    def _remove_committed(self):
        """Delete the tagged rows on a cursor of their own and commit. Idempotent."""
        if not self.row:
            return
        row, self.row = self.row, {}
        cr = self.registry.cursor()
        try:
            cr.execute("SET LOCAL lock_timeout = '3s'")
            env = api.Environment(cr, SUPERUSER_ID, {})
            steps = []
            if row.get("server"):
                steps.append(env["ai.context"].with_context(active_test=False).search(
                    [("api_server_id", "=", row["server"])]
                ))
            for model, key in (
                ("ai.mcp.user", "mcp"), ("ai.api.server", "server"),
                ("res.users", "asker"), ("res.users", "target"),
                ("res.partner", "contact"), ("res.partner", "asker_partner"),
                ("res.partner", "target_partner"),
            ):
                if row.get(key):
                    steps.append(env[model].with_context(active_test=False).browse(row[key]))
            for recs in steps:
                recs = recs.exists()
                if not recs:
                    continue
                try:
                    with cr.savepoint(), mute_logger("odoo.sql_db"):
                        recs.unlink()
                except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                    # Kept by a foreign key: no secret and archived; the [GUARD] reports it.
                    try:
                        with cr.savepoint(), mute_logger("odoo.sql_db"):
                            self._scrub(recs)
                    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                        _logger.warning("seges 3996 p18: could not scrub %s", recs._name)
            # Mail rows of the deleted users and partners, if any were made.
            refs = [("res.users", self.user_ids), ("res.partner", self.partner_ids)]
            for model, ids in refs:
                if ids:
                    cr.execute(
                        "DELETE FROM mail_followers WHERE res_model = %s AND res_id = ANY(%s)",
                        [model, ids],
                    )
                    cr.execute(
                        "DELETE FROM mail_message WHERE model = %s AND res_id = ANY(%s)",
                        [model, ids],
                    )
            cr.commit()  # pylint: disable=invalid-commit
        finally:
            cr.close()

    @staticmethod
    def _scrub(recs):
        vals = {
            name: False
            for name in ("auth_token", "mcp_api_key_hash", "totp_secret", "signup_token")
            if name in recs._fields
        }
        if "active" in recs._fields:
            vals["active"] = False
        if vals:
            recs.write(vals)

    def _tagged_rows(self):
        """{table: count} of the rows the test left behind (plain SQL, own cursor)."""
        users = self.user_ids or [0]
        partners = self.partner_ids or [0]
        checks = (
            ("res_users", "SELECT count(*) FROM res_users WHERE left(login, %s) = %s",
             [len(self.tag), self.tag]),
            ("res_partner", "SELECT count(*) FROM res_partner WHERE left(name, %s) = %s",
             [len(self.tag), self.tag]),
            ("ai_api_server", "SELECT count(*) FROM ai_api_server WHERE code = %s",
             [self.tag]),
            ("ai_mcp_user", "SELECT count(*) FROM ai_mcp_user WHERE user_id = ANY(%s)",
             [users]),
            ("ai_context", "SELECT count(*) FROM ai_context WHERE discovery_target = %s",
             [self.tag]),
            ("ai_url_whitelist",
             "SELECT count(*) FROM ai_url_whitelist WHERE position(%s in coalesce(notes, '')) > 0",
             [self.tag]),
            ("mail_message",
             ("SELECT count(*) FROM mail_message WHERE (model = 'res.users' AND res_id = ANY(%s))"
              " OR (model = 'res.partner' AND res_id = ANY(%s))"),
             [users, partners]),
            ("mail_followers",
             ("SELECT count(*) FROM mail_followers WHERE (res_model = 'res.users'"
              " AND res_id = ANY(%s)) OR (res_model = 'res.partner' AND res_id = ANY(%s))"
              " OR partner_id = ANY(%s)"),
             [users, partners, partners]),
        )
        cr = self.registry.cursor()
        try:
            found = {}
            for table, query, params in checks:
                cr.execute(query, params)
                count = cr.fetchone()[0]
                if count:
                    found[table] = count
            return found
        finally:
            cr.rollback()
            cr.close()

    def _release(self):
        """Delete the rows now and check it; call it before the assertions."""
        self._remove_committed()
        left = self._tagged_rows()
        self.assertFalse(
            left, f"[GUARD] expected no rows of the test after the cleanup ({self.tag!r}); "
            f"found {left}",
        )

    # -- the caller and the tool ---------------------------------------------

    @contextlib.contextmanager
    def _caller(self):
        """The caller (a request) on a real cursor opened after the commit; rolled back."""
        cr = self.registry.cursor()
        try:
            yield api.Environment(cr, SUPERUSER_ID, {})
        finally:
            cr.rollback()
            cr.close()

    def _run(self, caller, code, on_open=None):
        """The real tool, as the asker, on the caller's cursor."""
        stub = _OpenProbeStub(caller(user=self.rec["asker"]), on_open=on_open)
        self.spy.cursors = []
        with self.spy.watching():
            resp = tool_relaxaicode(stub, {"code": code})
        return _Run(resp, list(self.spy.cursors), list(stub.errors))

    def _server_ref(self):
        return (
            "s = env['mail.template.preview'].new("
            f"{{'resource_ref': 'ai.api.server,{self.rec['server']}'}}).resource_ref"
        )

    def _mcp_ref(self):
        return (
            "m = env['mail.template.preview'].new("
            f"{{'resource_ref': 'ai.mcp.user,{self.rec['mcp']}'}}).resource_ref"
        )

    def _show(self, run):
        """At most 300 characters of a run's text; never a text that holds a secret."""
        if any(value in run.text for value in self.secret.values()):
            return "<hidden: the text holds a secret>"
        return run.text[:300]

    # -- shared checks -------------------------------------------------------

    def _assert_box_a(self, run, what):
        kinds = sorted({c["kind"] for c in run.cursors})
        self.assertEqual(
            kinds, ["Cursor"],
            f"[SETUP] expected {what} to open box A on real Cursor objects only; found {kinds}",
        )
        self.assertTrue(
            any(c["rollbacks"] for c in run.cursors),
            f"[SETUP] expected box A of {what} rolled back; found no rollback",
        )
        self.assertFalse(
            any(c["commits"] for c in run.cursors),
            f"[SETUP] expected no commit on the cursors {what} opened; found one",
        )
        self.assertFalse(
            run.stub_errors,
            f"[SETUP] expected the opening probe of {what} to run; found {run.stub_errors}",
        )

    def _assert_ran(self, run, what, flag=None):
        self._assert_box_a(run, what)
        self.assertFalse(run.is_error, f"[SETUP] expected {what} to run; found: {self._show(run)}")
        self.assertTrue(
            _fp(PROBE_TEXT) in run.text,
            f"[SETUP] expected the probe fingerprint from {what}; found none",
        )
        if flag:
            self.assertTrue(
                flag in run.text, f"[SETUP] expected {flag!r} from {what}; found: {self._show(run)}",
            )

    def _assert_refused(self, run, fingerprint, model, fname, what):
        self._assert_box_a(run, what)
        self.assertEqual(
            run.outcome(fingerprint, model, fname), "refused",
            f"[SETUP] expected {what} refused by the field guard on {model}.{fname}; "
            f"found: {self._show(run)}",
        )

    def _assert_hypothesis_refused(self, run, fingerprint, model, fname, what):
        self._assert_box_a(run, what)
        outcome = run.outcome(fingerprint, model, fname)
        self.assertNotEqual(
            outcome, "other",
            f"[SETUP] expected {what} to end refused by the field guard or with the value; "
            f"found: {self._show(run)}",
        )
        self.assertEqual(
            outcome, "refused",
            f"[HYPOTHESIS] expected {what} refused by the field guard; found the secret's "
            "fingerprint in the result (read with no check)",
        )


@tagged("post_install", "-at_install", "pns_ai_mcp", "seges_e2p")
class TestSegesBoxACacheAtOpening(_SegesBoxASecretCase):
    """(a) Patch 18 part B: box A's cache when it opens, and the caller's pending writes."""

    def _server(self, caller):
        server = caller["ai.api.server"].browse(self.rec["server"])
        return server, server._fields["auth_token"]

    @staticmethod
    def _dirty(cache, record, field):
        return bool(
            cache.has_dirty_fields(record, [field])
            and record.id in cache.get_dirty_records(record, field)._ids
        )

    def _pending_state(self, caller, server, field, pending):
        """'pending', 'changed', 'flushed' or 'lost' for the caller's new token."""
        if self._dirty(caller.cache, server, field):
            if caller.cache.get(server, field, None) == pending:
                return "pending"
            return "changed"
        caller.cr.execute("SELECT auth_token FROM ai_api_server WHERE id = %s", [server.id])
        row = caller.cr.fetchone()
        return "flushed" if row and row[0] == pending else "lost"

    def _assert_pending(self, state, when):
        self.assertNotEqual(
            state, "flushed",
            f"[SETUP] expected the caller's new token still pending {when}; "
            "found the tool flushed the caller: written, not lost",
        )
        self.assertEqual(
            state, "pending",
            f"[HYPOTHESIS] expected the caller's new token still pending {when}; "
            f"found it {state}",
        )

    def _pending_secret_write(self, caller):
        """The caller reads the token with sudo (now cached) and leaves a new one pending."""
        server, field = self._server(caller)
        self.assertTrue(
            server.auth_token == self.secret["auth"],
            "[SETUP] expected the caller to read the committed token with sudo; "
            "found another value",
        )
        pending = f"{self.tag}_pending_{secrets.token_hex(16)}"
        server.write({"auth_token": pending})
        self.assertEqual(
            self._pending_state(caller, server, field, pending), "pending",
            "[SETUP] expected the new token pending in the caller (get_dirty_*) before box A",
        )
        return server, field, pending

    def test_box_a_opens_without_secret_or_caller_values_in_cache(self):
        """Box A opens with no secret column and no caller value in its cache.

        Anything else found there is logged (model.field and count), not failed.
        The caller keeps its pending write through box A.
        """
        seen = {}
        with self._caller() as caller:
            server, field, pending = self._pending_secret_write(caller)

            def on_open(ro_env):
                held = _cache_ids(ro_env.cache)
                callers = _cache_ids(caller.cache)
                secret = sorted(
                    f"{f.model_name}.{f.name}" for f in held
                    if ro_env[f.model_name]._pns_hidden_column(f.name)
                )
                shared = sorted(
                    f"{f.model_name}.{f.name}" for f, ids in held.items()
                    if ids & callers.get(f, set())
                )
                other = {
                    f"{f.model_name}.{f.name}": len(ids) for f, ids in held.items()
                    if f"{f.model_name}.{f.name}" not in secret + shared
                }
                seen.update(
                    marked=sandbox_cursor(ro_env.cr), su=ro_env.su, uid=ro_env.uid,
                    secret=secret, shared=shared,
                    at_open=self._pending_state(caller, server, field, pending),
                )
                _logger.info(
                    "seges 3996 p18: box A cache at opening: own transaction=%s, own cache=%s, "
                    "dirty fields=%s, to compute=%s, secret=%s, from the caller=%s, other=%s",
                    ro_env.transaction is not caller.transaction,
                    ro_env.cache is not caller.cache,
                    len(ro_env.cache.get_dirty_fields()), len(ro_env.transaction.tocompute),
                    secret, shared, other or "nothing",
                )

            run = self._run(caller, _code("x = sum([1, 2, 3])"), on_open=on_open)
            after = self._pending_state(caller, server, field, pending)
        self._release()
        self._assert_ran(run, "the run")
        self.assertTrue(seen, "[SETUP] expected the opening probe to run; found it not called")
        self.assertTrue(
            seen["marked"] and not seen["su"] and seen["uid"] == self.rec["asker"],
            f"[SETUP] expected box A marked, without su, as the asker; found marked="
            f"{seen['marked']}, su={seen['su']}, asker={seen['uid'] == self.rec['asker']}",
        )
        self.assertFalse(
            seen["secret"],
            f"[HYPOTHESIS] expected no secret column in box A's cache at opening; "
            f"found {seen['secret']}",
        )
        self.assertFalse(
            seen["shared"],
            f"[HYPOTHESIS] expected no caller value in box A's cache at opening; "
            f"found {seen['shared']}",
        )
        self._assert_pending(seen["at_open"], "when box A opens")
        self._assert_pending(after, "after box A closes")

    def test_caller_cached_token_not_readable_in_box_a(self):
        """NUEVO-1 in Odoo 17: a token the caller read with sudo does not reach box A."""
        with self._caller() as caller:
            server, field = self._server(caller)
            self.assertTrue(
                server.auth_token == self.secret["auth"],
                "[SETUP] expected the caller to read the committed token with sudo; "
                "found another value",
            )
            self.assertTrue(
                caller.cache.contains(server, field),
                "[SETUP] expected the token in the caller's cache; found it missing",
            )
            run = self._run(caller, _code(self._server_ref(), read="s['auth_token']"))
        self._release()
        self._assert_hypothesis_refused(
            run, _fp(self.secret["auth"]), "ai.api.server", "auth_token",
            "s['auth_token'] with the token in the caller's cache",
        )

    def test_simulated_b_keeps_caller_pending_secret_write(self):
        """Part B as in Odoo 14, on opening: it only touches box A's own cache."""
        seen = {}
        with self._caller() as caller:
            server, field, pending = self._pending_secret_write(caller)

            def part_b(ro_env):
                secret_fields = [
                    model_field
                    for name in ro_env.registry
                    for fname, model_field in ro_env[name]._fields.items()
                    if ro_env[name]._pns_hidden_column(fname)
                ]
                ro_env.cache.invalidate([(f, None) for f in secret_fields])
                seen.update(
                    count=len(secret_fields), token=field in secret_fields,
                    at_open=self._pending_state(caller, server, field, pending),
                )

            run = self._run(caller, _code("x = sum([1, 2, 3])"), on_open=part_b)
            after = self._pending_state(caller, server, field, pending)
            caller.flush_all()
            caller.cr.execute("SELECT auth_token FROM ai_api_server WHERE id = %s", [server.id])
            written = caller.cr.fetchone()[0] == pending
        self._release()
        self._assert_ran(run, "the run")
        self.assertTrue(
            seen and seen["count"] and seen["token"],
            "[SETUP] expected the simulated part B over the secret columns, "
            f"ai.api.server.auth_token among them; found {seen.get('count')} columns, "
            f"token={seen.get('token')}",
        )
        self._assert_pending(seen["at_open"], "right after part B")
        self._assert_pending(after, "after box A closes")
        self.assertTrue(
            written,
            "[HYPOTHESIS] expected the caller's flush to write its pending token; "
            "found another value",
        )

    def test_invalidating_the_callers_cache_drops_its_pending_value(self):
        """Why part B must never reach the caller (odoo/api.py:1300-1302)."""
        with self._caller() as caller:
            server, field, _pending = self._pending_secret_write(caller)
            caller.cache.invalidate([(field, None)])
            dropped = not caller.cache.contains(server, field)
            still_dirty = self._dirty(caller.cache, server, field)
            caller.transaction.clear()  # nothing may be flushed now; the cursor rolls back
        self._release()
        self.assertTrue(
            dropped and still_dirty,
            "[GUARD] expected Cache.invalidate to drop the caller's pending value and keep "
            f"its dirty flag; found dropped={dropped}, dirty={still_dirty}",
        )


    def test_b2_helper_keeps_caller_pending_write(self):
        """[GUARD] B2 in the real box A forgets box A's cache, never the caller's.

        A module helper (collect_sandbox_helpers, utils/sandbox_helpers.py) reads the
        token as sudo on box A's cursor; when it ends, B2 invalidates the secret
        columns of box A's cache (utils/seges_box_a_cache.py). Cache.invalidate drops
        pending values (odoo/api.py:1300-1302): the caller's pending token must stay.
        """
        sid = self.rec["server"]
        seen = []
        real_forget = seges_box_a_cache._seges_forget_secret_columns

        def probe_helpers(rec):
            def seges_probe():
                return bool(rec.env["ai.api.server"].browse(sid).auth_token)
            return {"seges_probe": seges_probe}

        model_cls = type(self.env["res.partner"])
        model_cls.sandbox_helpers = probe_helpers
        self.addCleanup(delattr, model_cls, "sandbox_helpers")
        self.patch(
            sandbox_helpers, "iter_provider_model_names", lambda env: ["res.partner"],
        )
        self.patch(
            sandbox_helpers, "is_sandbox_helper_provider", lambda env, name: True,
        )
        with self._caller() as caller:
            server, field, pending = self._pending_secret_write(caller)

            def forget(env):
                box_server = env["ai.api.server"].browse(sid)
                box_field = box_server._fields["auth_token"]
                before = env.cache.contains(box_server, box_field)
                real_forget(env)
                seen.append({
                    "box_a": sandbox_cursor(env.cr),
                    "before": before,
                    "after": env.cache.contains(box_server, box_field),
                    "caller": self._pending_state(caller, server, field, pending),
                })

            self.patch(seges_box_a_cache, "_seges_forget_secret_columns", forget)
            run = self._run(caller, _code(
                "ok = seges_probe()",
                flag="'seges3996-' + ('probe-ok' if ok else 'probe-no')",
            ))
            after = self._pending_state(caller, server, field, pending)
            caller.flush_all()
            caller.cr.execute(
                "SELECT auth_token FROM ai_api_server WHERE id = %s", [sid],
            )
            written = caller.cr.fetchone()[0] == pending
        self._release()
        self._assert_ran(run, "the run with the helper", flag="seges3996-probe-ok")
        self.assertTrue(
            seen and all(s["box_a"] and s["before"] and not s["after"] for s in seen),
            "[SETUP] expected B2 to run on box A's cursor and forget the token the "
            f"helper left in box A's cache; found {len(seen)} calls, "
            f"{[(s['box_a'], s['before'], s['after']) for s in seen]}",
        )
        self.assertEqual(
            [s["caller"] for s in seen], ["pending"] * len(seen),
            "[GUARD] expected the caller's new token still pending when B2 ran",
        )
        self._assert_pending(after, "after box A closes")
        self.assertTrue(
            written,
            "[GUARD] expected the caller's flush to write its pending token; "
            "found another value",
        )


@tagged("post_install", "-at_install", "pns_ai_mcp", "seges_e2p")
class TestSegesBoxASecretReadInside(_SegesBoxASecretCase):
    """(b) A secret read with sudo() on box A's cursor, then by the sandbox code."""

    def test_v1_auth_call_preview_then_token(self):
        """Real path: auth_call_preview reads auth_token with sudo() (external_server.py:393)."""
        head = self._server_ref()
        with self._caller() as caller:
            control = self._run(caller, _code(head, read="s['auth_token']"))
            reach = self._run(caller, _code(
                head, "pv = s.auth_call_preview",
                flag="'seges3996-' + ('token-set' if 'token set' in str(pv) else 'no-token')",
            ))
            via = self._run(caller, _code(head, "pv = s.auth_call_preview", read="s['auth_token']"))
        self._release()
        fingerprint = _fp(self.secret["auth"])
        self._assert_refused(
            control, fingerprint, "ai.api.server", "auth_token", "s['auth_token'] alone",
        )
        self._assert_ran(reach, "auth_call_preview alone", flag="seges3996-token-set")
        self._assert_hypothesis_refused(
            via, fingerprint, "ai.api.server", "auth_token",
            "s['auth_token'] after auth_call_preview",
        )

    def test_v2_user_has_mcp_api_key_then_hash(self):
        """Real path: user_has_mcp_api_key reads the hash with sudo() (mcp_user.py:318-319)."""
        head = self._mcp_ref()
        has_key = f"k = m.user_has_mcp_api_key(env['res.users'].browse({self.rec['target']}))"
        with self._caller() as caller:
            control = self._run(caller, _code(head, read="m['mcp_api_key_hash']"))
            reach = self._run(caller, _code(
                head, has_key, flag="'seges3996-' + ('has-key' if k else 'no-key')",
            ))
            via = self._run(caller, _code(head, has_key, read="m['mcp_api_key_hash']"))
        self._release()
        fingerprint = _fp(self.secret["hash"])
        self._assert_refused(
            control, fingerprint, "ai.mcp.user", "mcp_api_key_hash",
            "m['mcp_api_key_hash'] alone",
        )
        self._assert_ran(reach, "user_has_mcp_api_key alone", flag="seges3996-has-key")
        self._assert_hypothesis_refused(
            via, fingerprint, "ai.mcp.user", "mcp_api_key_hash",
            "m['mcp_api_key_hash'] after user_has_mcp_api_key",
        )

    def test_synthetic_engine_sudo_read_before_code(self):
        """SYNTHETIC: no engine code reads a secret with sudo() on box A today.

        Stands for patch 18 part B2's case: the engine (a sandbox helper) reads the
        token with sudo() on box A's environment before the sandbox code runs.
        """
        seen = {}

        def warm(ro_env):
            server = ro_env["ai.api.server"].sudo().browse(self.rec["server"])
            seen["warm"] = bool(server.auth_token) and ro_env.cache.contains(
                server, server._fields["auth_token"]
            )

        code = _code(self._server_ref(), read="s['auth_token']")
        with self._caller() as caller:
            control = self._run(caller, code)
            warmed = self._run(caller, code, on_open=warm)
        self._release()
        fingerprint = _fp(self.secret["auth"])
        self._assert_refused(
            control, fingerprint, "ai.api.server", "auth_token", "s['auth_token'] alone",
        )
        self.assertTrue(
            seen.get("warm"),
            "[SETUP] expected the synthetic engine read to leave the token in box A's cache; "
            "found it missing",
        )
        self._assert_hypothesis_refused(
            warmed, fingerprint, "ai.api.server", "auth_token",
            "SYNTHETIC: s['auth_token'] after an engine read with sudo()",
        )


@tagged("post_install", "-at_install", "pns_ai_mcp", "seges_e2p")
class TestSegesBoxAComputedSecret(_SegesBoxASecretCase):
    """(c) Odoo 17 core secrets computed by SQL: read with no check and no cache."""

    def _assert_computed_secret(self, model_name, fname):
        model = self.env[model_name]
        if fname not in model._fields:
            # auth_totp / auth_signup: auto_install, not in the depends (decision 115).
            self.skipTest(f"{model_name}.{fname} not installed")
        field = model._fields[fname]
        self.assertTrue(
            field.compute and not field.store,
            f"[SETUP] expected {model_name}.{fname} computed and not stored; "
            f"found compute={bool(field.compute)}, store={field.store}",
        )
        self.assertTrue(
            secret_column(model, fname),
            f"[SETUP] expected the vendor's criterion to call {model_name}.{fname} secret; "
            "found it not secret",
        )

    def _computed(  # pylint: disable=too-many-positional-arguments
            self, model_name, rec_key, var, plain, plain_value, fname, secret_key):
        """Same record, same path: a plain field must come out, then the computed secret."""
        self._assert_computed_secret(model_name, fname)
        head = f"{var} = env['{model_name}'].browse({self.rec[rec_key]})"
        with self._caller() as caller:
            control = self._run(caller, _code(head, read=f"{var}['{plain}']"))
            run = self._run(caller, _code(head, read=f"{var}['{fname}']"))
        self._release()
        self._assert_ran(control, f"{var}['{plain}'] on the same record")
        self.assertTrue(
            _fp(plain_value) in control.text,
            f"[SETUP] expected the control to return the fingerprint of {model_name}.{plain}; "
            f"found: {self._show(control)}",
        )
        self._assert_hypothesis_refused(
            run, _fp(self.secret[secret_key]), model_name, fname,
            f"{var}['{fname}'] with nothing cached",
        )

    def test_core_totp_secret_without_cache(self):
        self._computed(
            "res.users", "target", "u", "login", f"{self.tag}_target", "totp_secret", "totp",
        )

    def test_core_signup_token_without_cache(self):
        self._computed(
            "res.partner", "contact", "p", "name", f"{self.tag} contact", "signup_token", "signup",
        )
