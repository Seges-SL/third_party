# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 22 (tests de la entrega E2′). Ver docs/pendiente/parches_pns_ai.md
# Seges: adaptado a la 17 (fase 2, T4): listas de la 17 (22 y 39) y E3 (parche 41);
# _StubController de seges_common; los documentos que citan las líneas anteriores
# están en 14.0. Ver docs/pendiente/parches_pns_ai.md
"""Parche 22 (PNS-100): el sandbox no llama a métodos públicos que envían correo,
abren conexiones o ejecutan otro código sin escribir antes en la BD (el READ
ONLY de la caja A no los frena).

Los tests de caja A ejecutan ``tool_relaxaicode`` real como ``base.user_admin``
(guardado en la BD, sin AI Administrator en una BD nueva). El método de cada vía
se sustituye en la clase del registro: así se ve si el código del sandbox llegó
a llamarlo, sin enviar nada y sin depender de que el registro exista en el
cursor propio de la caja A. ``smtplib.SMTP`` y ``requests.get`` también se
sustituyen, por si algo los alcanzara.

En la 17 (T4): las listas del punto 7 de la clasificación (salen los nombres que
desaparecen o están vacíos; entran ``partner_autocomplete``, ``get_services``,
``execute_import``, ``button_immediate_install_app``, ``action_disconnect`` y los
de la localización india; ``get_view``, ``get_views``, ``authenticate`` y
``check`` solo en su modelo) y el parche 41 (E3): un nombre de la lista leído
sin llamarlo (``f = rec.connect``) sobre un modelo. Además de ``smtplib.SMTP`` y
``requests.get``, se sustituyen ``smtplib.SMTP_SSL``, ``requests.post``,
``requests.Session.request`` e ``iap_jsonrpc``: ni con una neutralización sale
nada fuera.
"""

import contextlib
import json
from unittest import mock

from odoo.models import BaseModel
from odoo.tests import TransactionCase, tagged

from odoo.addons.pns_ai_mcp.controllers import context_builder
from odoo.addons.pns_ai_mcp.controllers.context_builder import (
    guarded_getattr,
    guarded_methodcaller,
    sandbox_attr,
)
from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import tool_relaxaicode
from odoo.addons.pns_ai_mcp.controllers.validators import (
    validate_relaxaicode_source_ast,
)
from odoo.addons.pns_ai_mcp.controllers.validators_base import (
    RELAXAICODE_SIDE_EFFECT_METHODS,
)
from odoo.addons.pns_ai_mcp.tests.seges_common import _StubController

# Seges: adaptado a la 17 (fase 2, T4). Ver docs/pendiente/parches_pns_ai.md
# Los 6 del fabricante y los 26 del parche 22 en la 17.
E2P_NAMES = (
    'send_email', 'connect', 'test_smtp_connection', 'load_remote_url', 'send',
    'process_email_queue', 'fetch_mail', 'button_confirm_login', 'get_credits',
    'send_letter', 'snailmail_print', 'update_notification',
    'action_process_edi_web_services', 'get_usd_fx', 'run',
    'method_direct_trigger', 'upgrade_module', 'action_start_automatic_process',
    'parent_migration_process_cb', 'send_mail', 'message_process', 'message_route',
    'autocomplete_by_name', 'autocomplete_by_vat', 'enrich_by_duns', 'enrich_by_gst',
    'enrich_by_domain', 'iap_enrich_auto', 'get_services', 'execute_import',
    'button_immediate_install_app', 'action_disconnect',
)
# Contraseña ficticia de los casos de res.users (se busca en los logs: 0).
FAKE_PASSWORD = 'seges-t4-pw-e3c1'
SMS = "{'composition_mode': 'numbers', 'numbers': '+34600000000', 'body': 'x'}"
# Casos del grupo A del 39: (modelo, nombre, registros, argumentos).
P39_CASES = (
    ('iap.account', 'get_credits_url', "env['iap.account']", "'seges_p39'"),
    ('iap.account', 'get_config_account_url', "env['iap.account']", ""),
    ('res.config.settings', 'redirect_to_buy_autocomplete_credit',
     "env['res.config.settings'].new({})", ""),
    ('sms.resend', 'action_buy_credits', "env['sms.resend'].new({})", ""),
    ('mailing.mailing', 'action_buy_sms_credits',
     "env['mailing.mailing'].new({})", ""),
    ('sms.composer', 'action_send_sms', f"env['sms.composer'].new({SMS})", ""),
    ('mailing.sms.test', 'action_send_sms',
     "env['mailing.sms.test'].new({'numbers': '+34600000000'})", ""),
    ('sms.composer', 'action_send_sms_mass_now', f"env['sms.composer'].new({SMS})", ""),
    ('crm.iap.lead.mining.request', 'action_submit',
     "env['crm.iap.lead.mining.request'].new({'name': 'seges_p39'})", ""),
    # Seges: adaptado a la 17 (fase 2, T4). Ver docs/pendiente/parches_pns_ai.md
    ('crm.iap.lead.mining.request', 'action_buy_credits',
     "env['crm.iap.lead.mining.request'].new({'name': 'seges_p39'})", ""),
    ('res.config.settings', 'l10n_in_edi_buy_iap',
     "env['res.config.settings'].new({})", ""),
    ('res.config.settings', 'l10n_in_edi_test',
     "env['res.config.settings'].new({})", ""),
    ('res.config.settings', 'l10n_in_edi_ewaybill_test',
     "env['res.config.settings'].new({})", ""),
)
# Seges: adaptado a la 17 (fase 2, T4). Ver docs/pendiente/parches_pns_ai.md
# Nombres nuevos del 22 en la 17: (modelo, nombre, registros, argumentos).
P22_NEW_CASES = (
    ('res.partner', 'autocomplete_by_name', "env['res.partner']", "'seges', False"),
    ('res.partner', 'autocomplete_by_vat', "env['res.partner']",
     "'ESB00000000', False"),
    ('res.partner', 'enrich_by_duns', "env['res.partner']", "'000000000'"),
    ('res.partner', 'enrich_by_gst', "env['res.partner']", "'00AAAAA0000A0Z0'"),
    ('res.partner', 'enrich_by_domain', "env['res.partner']", "'seges.invalid'"),
    ('res.company', 'iap_enrich_auto', "env['res.company'].browse(1)", ""),
    ('iap.account', 'get_services', "env['iap.account']", ""),
    ('base_import.import', 'execute_import',
     "env['base_import.import'].new({'res_model': 'res.partner'})",
     "['image_1920'], ['image'], {}"),
    ('ir.module.module', 'button_immediate_install_app',
     "env['ir.module.module'].browse(1)", ""),
    ('discuss.channel.rtc.session', 'action_disconnect',
     "env['discuss.channel.rtc.session'].browse(1)", ""),
)
# Solo en la tabla por modelo (nombres comunes).
P22_TABLE_CASES = (
    ('iap.account', 'get_view', "env['iap.account']", "view_type='tree'"),
    ('iap.account', 'get_views', "env['iap.account']", "[[False, 'tree']]"),
    ('res.users', 'authenticate', "env['res.users']",
     f"'x', 'admin', {FAKE_PASSWORD!r}, {{}}"),
    ('res.users', 'check', "env['res.users']", f"'x', 2, {FAKE_PASSWORD!r}"),
)


@contextlib.contextmanager
def _no_outside_effects():
    """Correo, HTTP e IAP sustituidos; devuelve los sustitutos por nombre."""
    targets = (
        'smtplib.SMTP', 'smtplib.SMTP_SSL', 'requests.get', 'requests.post',
        'requests.Session.request', 'odoo.addons.iap.tools.iap_tools.iap_jsonrpc',
    )
    with contextlib.ExitStack() as stack:
        yield {t: stack.enter_context(mock.patch(t)) for t in targets}


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
# 24 casos, uno por vía: se aceptan más de 20 métodos públicos.
# pylint: disable-next=too-many-public-methods
class TestSegesSandboxSideEffects(TransactionCase):

    def setUp(self):
        super().setUp()
        self.admin = self.env.ref('base.user_admin')

    def test_names_in_denylist(self):
        for name in E2P_NAMES:
            self.assertIn(name, RELAXAICODE_SIDE_EFFECT_METHODS, name)
            with self.assertRaises(AttributeError, msg=name):
                guarded_getattr(object(), name)
            with self.assertRaises(AttributeError, msg=name):
                guarded_methodcaller(name)

    def test_ast_flags_literal_call(self):
        for name in E2P_NAMES:
            code = (
                f"x = env['res.partner'].browse(1).{name}()\n"
                "result = {'data': 1}\n"
            )
            valid, _error, requires_write = validate_relaxaicode_source_ast(code)
            # requires_write lleva a _read_only_response: no se ejecuta.
            self.assertTrue(requires_write or not valid, name)

    def _assert_box_a_refused(self, model, method, code):
        if model not in self.env or not hasattr(type(self.env[model]), method):
            self.skipTest(f'{model}.{method} no está instalado en esta BD')
        cls = type(self.env[model])
        # Seges: adaptado a la 17 (fase 2, T4). Ver docs/pendiente/parches_pns_ai.md
        # authenticate y check son classmethod heredados en la clase del registro:
        # con autospec, el sustituto se enlaza al registro y rechaza la llamada
        # (TypeError) antes de anotarla; sin autospec, la anota.
        autospec = method not in ('authenticate', 'check')
        with mock.patch.object(cls, method, autospec=autospec) as called, \
                _no_outside_effects() as outside:
            resp = tool_relaxaicode(
                _StubController(self.env(user=self.admin)), {'code': code})
        text = json.dumps(resp, default=str)
        self.assertFalse(called.called, f'{model}.{method}: {text[:300]}')
        for target, sub in outside.items():
            self.assertFalse(sub.called, f'{model}.{method}: {target}')
        # Rechazo del AST (_read_only_response) o error de ejecución (isError).
        inner = resp['content'][0]['text']
        self.assertTrue(
            '"requires_write": true' in inner or resp.get('isError'), text[:300])

    def _assert_alias_refused(self, model, method, records, args):
        # A bare read, then the call: the AST sees no call by that name.
        self._assert_box_a_refused(model, method, (
            f"f = {records}.{method}\n"
            f"f({args})\n"
            "result = 1\n"
        ))

    def test_box_a_send_email_refused(self):
        self._assert_box_a_refused('ir.mail_server', 'send_email', (
            "S = env['ir.mail_server']\n"
            "m = S.build_email('a@seges.invalid', ['b@seges.invalid'], 's', 'b')\n"
            "S.send_email(m, smtp_server='seges.invalid')\n"
            "result = 1\n"
        ))

    def test_box_a_connect_refused(self):
        self._assert_box_a_refused('ir.mail_server', 'connect', (
            "env['ir.mail_server'].connect('seges.invalid', 2525)\n"
            "result = 1\n"
        ))

    def test_box_a_load_remote_url_refused(self):
        self._assert_box_a_refused('ir.qweb.field.image', 'load_remote_url', (
            "env['ir.qweb.field.image'].load_remote_url("
            "'https://seges.invalid/x.png?d=secret')\n"
            "result = 1\n"
        ))

    def test_box_a_server_action_run_refused(self):
        self._assert_box_a_refused('ir.actions.server', 'run', (
            "env['ir.actions.server'].browse(1).run()\n"
            "result = 1\n"
        ))

    def test_box_a_cron_trigger_refused(self):
        self._assert_box_a_refused('ir.cron', 'method_direct_trigger', (
            "env['ir.cron'].browse(1).method_direct_trigger()\n"
            "result = 1\n"
        ))

    def test_box_a_mail_queue_refused(self):
        self._assert_box_a_refused('mail.mail', 'process_email_queue', (
            "env['mail.mail'].process_email_queue()\n"
            "result = 1\n"
        ))
        self._assert_box_a_refused('mail.mail', 'send', (
            "env['mail.mail'].browse(1).send()\n"
            "result = 1\n"
        ))

    # Seges: adaptado a la 17 (fase 2, T4): read_by_vat está vacío en la 17.
    # Ver docs/pendiente/parches_pns_ai.md
    def test_box_a_iap_refused(self):
        self._assert_box_a_refused('iap.account', 'get_credits', (
            "env['iap.account'].get_credits('partner_autocomplete')\n"
            "result = 1\n"
        ))
        self._assert_box_a_refused('res.partner', 'autocomplete_by_name', (
            "env['res.partner'].autocomplete_by_name('seges', False)\n"
            "result = 1\n"
        ))

    # Seges: adaptado a la 17 (fase 2, T4): install_from_urls no existe en la 17;
    # el que descarga e instala es button_immediate_install_app.
    # Ver docs/pendiente/parches_pns_ai.md
    def test_box_a_module_from_urls_refused(self):
        self._assert_box_a_refused('ir.module.module', 'button_immediate_install_app', (
            "env['ir.module.module'].browse(1).button_immediate_install_app()\n"
            "result = 1\n"
        ))

    # Seges: parche 39 (PNS-107, seguridad). Ver docs/pendiente/parches_pns_ai.md
    def test_box_a_iap_get_refused(self):
        self._assert_box_a_refused('iap.account', 'get', (
            "env['iap.account'].get('seges_p39')\n"
            "result = 1\n"
        ))

    def test_box_a_iap_get_dynamic_refused(self):
        if 'iap.account' not in self.env:
            self.skipTest('iap.account no está instalado en esta BD')
        records = self.env['iap.account']
        with mock.patch.object(type(records), 'get', autospec=True) as called:
            with self.assertRaises(AttributeError):
                guarded_getattr(records, 'get')
            with self.assertRaises(AttributeError):
                guarded_getattr(type(records), 'get')
            with self.assertRaises(AttributeError):
                guarded_methodcaller('get', 'seges_p39')(records)
        self.assertFalse(called.called)

    def test_box_a_get_controls_pass(self):
        if 'iap.account' not in self.env:
            self.skipTest('iap.account no está instalado en esta BD')
        self.assertEqual(guarded_getattr({'k': 1}, 'get')('k'), 1)
        self.assertTrue(callable(guarded_getattr({}, 'get')))
        self.assertTrue(callable(guarded_getattr(self.env['iap.account'], 'search')))
        code = (
            "result = {'a': {'k': 1}.get('k'), "
            "'n': env['iap.account'].search_count([])}\n"
        )
        resp = tool_relaxaicode(
            _StubController(self.env(user=self.admin)), {'code': code})
        text = json.dumps(resp, default=str)
        self.assertFalse(resp.get('isError'), text[:300])

    # Seges: parche 39 (PNS-107, seguridad). Ver docs/pendiente/parches_pns_ai.md
    # Seges: adaptado a la 17 (fase 2, T4): action_buy_credits de crm_iap_mine y
    # los 3 de la localización india. Ver docs/pendiente/parches_pns_ai.md
    def test_box_a_iap_get_indirect_refused(self):
        for model, method, records, args in P39_CASES:
            with self.subTest(model=model, method=method):
                installed = model in self.env and hasattr(type(self.env[model]), method)
                if installed:
                    # First: without the patch the sandbox reaches the method.
                    self._assert_box_a_refused(
                        model, method, f"{records}.{method}({args})\nresult = 1\n")
                self.assertIn(method, RELAXAICODE_SIDE_EFFECT_METHODS)
                with self.assertRaises(AttributeError):
                    guarded_getattr(object(), method)
                if not installed:
                    self.skipTest(f'{model}.{method} no está instalado en esta BD')

    # Seges: parche 39 (PNS-107, seguridad). Ver docs/pendiente/parches_pns_ai.md
    def test_box_a_iap_get_alias_refused(self):
        for model, method, records, args in P39_CASES:
            with self.subTest(model=model, method=method):
                self._assert_alias_refused(model, method, records, args)

    # Seges: adaptado a la 17 (fase 2, T4): casos nuevos del punto 7 (parche 22).
    # Ver docs/pendiente/parches_pns_ai.md
    def test_box_a_iap_services_refused(self):
        """``get_services`` (lista global) y una vista de lista (tabla por modelo)."""
        cases = (
            ('get_services', "env['iap.account'].get_services()"),
            ('get_view', "env['iap.account'].get_view(view_type='tree')"),
            ('get_views', "env['iap.account'].get_views([[False, 'tree']])"),
        )
        for method, call in cases:
            with self.subTest(method=method):
                self._assert_box_a_refused(
                    'iap.account', method, f"{call}\nresult = 1\n")

    def test_box_a_import_url_refused(self):
        self._assert_box_a_refused('base_import.import', 'execute_import', (
            "w = env['base_import.import'].new({'res_model': 'res.partner'})\n"
            "w.execute_import(['image_1920'], ['image'], {})\n"
            "result = 1\n"
        ))

    def test_box_a_partner_autocomplete_refused(self):
        for model, method, records, args in P22_NEW_CASES[:6]:
            with self.subTest(model=model, method=method):
                self._assert_box_a_refused(
                    model, method, f"{records}.{method}({args})\nresult = 1\n")

    def test_box_a_login_check_refused(self):
        """``authenticate`` confirma en su cursor; ``check`` prueba contraseñas."""
        for model, method, records, args in P22_TABLE_CASES[2:]:
            with self.subTest(model=model, method=method):
                self._assert_box_a_refused(
                    model, method, f"{records}.{method}({args})\nresult = 1\n")

    def test_box_a_rtc_disconnect_refused(self):
        self._assert_box_a_refused('discuss.channel.rtc.session', 'action_disconnect', (
            "env['discuss.channel.rtc.session'].browse(1).action_disconnect()\n"
            "result = 1\n"
        ))

    def test_box_a_new_names_alias_refused(self):
        """Alias sin llamada de los nombres nuevos: 41 (lista) y tabla por modelo."""
        for model, method, records, args in P22_NEW_CASES + P22_TABLE_CASES:
            with self.subTest(model=model, method=method):
                self._assert_alias_refused(model, method, records, args)

    # Seges: parche 41 (E3, seguridad). Ver docs/pendiente/parches_pns_ai.md
    def test_box_a_alias_of_listed_names_refused(self):
        """E3: ``f = rec.<nombre de la lista>`` y después ``f(...)``.

        Solo modelos del core: los de ``pns_*`` los rechaza antes la puerta de
        credenciales, y el caso no mediría el 41.
        """
        cases = (
            ('ir.mail_server', 'connect', "env['ir.mail_server']",
             "'seges.invalid', 2525"),
            ('iap.account', 'get_credits', "env['iap.account']", "'seges_p39'"),
            ('res.partner', 'message_route', "env['res.partner']", "None, {}"),
            ('ir.actions.server', 'run', "env['ir.actions.server'].browse(1)", ""),
            ('mail.mail', 'send', "env['mail.mail'].browse(1)", ""),
            ('ir.mail_server', 'connect', "type(env['ir.mail_server'])",
             "env['ir.mail_server'], 'seges.invalid', 2525"),
        )
        for model, method, records, args in cases:
            with self.subTest(model=model, method=method, records=records):
                self._assert_alias_refused(model, method, records, args)

    # Seges: parche 41 (E3, seguridad). Ver docs/pendiente/parches_pns_ai.md
    def test_box_a_alias_controls_pass(self):
        """Control: un método fuera de la lista y uno de la lista fuera de un modelo."""
        code = (
            "f = env['res.partner'].search_count\n"
            "g = (i for i in [1])\n"
            "s = g.send\n"
            "d = {'k': 1}.get\n"
            "result = {'n': f([]), 'k': d('k'), 's': callable(s)}\n"
        )
        resp = tool_relaxaicode(
            _StubController(self.env(user=self.admin)), {'code': code})
        text = json.dumps(resp, default=str)
        self.assertFalse(resp.get('isError'), text[:300])
        inner = resp['content'][0]['text']
        self.assertNotIn('"requires_write": true', inner, text[:300])

    # Seges: parche 41 (E3, seguridad). Ver docs/pendiente/parches_pns_ai.md
    def test_alias_check_keeps_fields(self):
        """Control: un campo con un nombre de la lista (``send_mail``) se lee."""
        # [SETUP]: dentro de Odoo el 41 no puede quedar apagado en silencio.
        self.assertIs(context_builder._SegesBaseModel, BaseModel, '[SETUP]')
        partner = self.env['res.partner']
        cls = type(partner)
        self.assertIn('send_mail', RELAXAICODE_SIDE_EFFECT_METHODS, '[SETUP]')
        with mock.patch.dict(cls._fields, {'send_mail': cls._fields['name']}), \
                mock.patch.object(cls, 'send_mail', 'seges-field', create=True):
            self.assertEqual(sandbox_attr(partner, 'send_mail'), 'seges-field')
