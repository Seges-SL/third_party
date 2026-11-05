# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: tests de la entrega E4′ (parches 30, 31, 32 y 33). Ver docs/pendiente/parches_pns_ai.md
"""Parches 30 a 33 (M11, M12, PNS-97 y PNS-29, resto 3).

- 30: los ``log_*`` públicos del motor solo escriben, fuera del sistema, a nombre
  del usuario actual y si es interno.
- 31: ``chat_completion`` solo en ``su``.
- 32: ``create``, ``write`` y ``unlink`` de ``ai.trusted.action`` exigen Ajustes
  fuera de ``su`` y, dentro de un plan supervisado, también a quien lo propuso y
  a quien lo confirmó.
- 33: ``month_usage`` pasa a privado y ``default_get`` del asistente exige su ACL.

Las filas de ``ai.log`` se cuentan en un ``TransactionCase`` sin modo test y con
usuarios ya guardados en la BD: en un ``HttpCase`` ``_create_log_entry`` no
escribe nunca (cursor de test).
"""

import json
from unittest.mock import MagicMock, patch

from odoo import SUPERUSER_ID, api
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import convert_file

from odoo.addons.pns_ai_mcp.controllers.safe_plan import execute_safe_plan

LOG_ENDPOINT = 'seges_e4p_m11'
AGENT = 'pns_ai_mcp'
MESSAGES = [{'role': 'user', 'content': 'x'}]
FAKE_RESPONSE = {'choices': [{'message': {'content': 'seges e4p'}}]}
NEW_CODE = 'seges.e4p'
TRUSTED_XMLIDS = (
    'trusted_action_field_set_required',
    'trusted_action_view_set_field_required',
    'trusted_action_view_set_field_readonly',
    'trusted_action_view_set_field_invisible',
    'trusted_action_view_set_field_domain',
    'trusted_action_view_reset_field_modifiers',
    'trusted_action_module_update',
    'trusted_action_user_add_group',
    'trusted_action_user_remove_group',
)

# (método, args JSON sin ids, kwargs JSON) de los seis log_* públicos.
LOG_CALLS = (
    ('log_role_without_provider', [AGENT, 'conversation'], {}),
    ('log_provider_failover', [AGENT, False, False, 'seges'], {}),
    ('log_provider_llm_request', [False], {'agent_code': AGENT}),
    ('log_provider_llm_response', [False],
     {'agent_code': AGENT, 'content_preview': 'seges'}),
    ('log_llm_inference', [False, {'total_tokens': 1}],
     {'endpoint': LOG_ENDPOINT}),
    ('log_provider_inference', [False, [], {}], {}),
)
# log_provider_failover necesita registros: por RPC no llega a escribir.
WRITING_LOG_CALLS = tuple(c for c in LOG_CALLS if c[0] != 'log_provider_failover')


def _engine_class(env):
    return type(env['ai.execution.engine'])


def _fake_providers(fake_id):
    """get_providers_for_agent simulado: siempre el proveedor de prueba."""
    def get_providers_for_agent(engine, agent_code, provider_id=None, need=None):
        return engine.env['ai.provider'].browse(fake_id)
    return get_providers_for_agent


class _SegesE4pRpcBase:
    """Arnés RPC de test_seges_rpc_access.py, sin importar su clase (Odoo
    volvería a ejecutar sus tests)."""

    def _rpc(self, login, model, method, args, kwargs=None):
        self.env['base'].flush()
        self.authenticate(login, login)
        payload = {
            'jsonrpc': '2.0', 'method': 'call', 'id': 1,
            'params': {
                'model': model, 'method': method,
                'args': args, 'kwargs': kwargs or {},
            },
        }
        resp = self.url_open(
            f'/web/dataset/call_kw/{model}/{method}',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        return resp.json()

    def _assert_error(self, res, name):
        self.assertNotIn('result', res, res)
        self.assertIn('error', res, res)
        self.assertEqual(res['error']['data']['name'], name, res)


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e4p')
class TestSegesE4pRpc(_SegesE4pRpcBase, HttpCase):
    """Negativos por RPC real: interno y portal."""

    def setUp(self):
        super().setUp()
        self.user_internal = new_test_user(
            self.env, login='seges_e4p_internal', groups='base.group_user',
            password='seges_e4p_internal',
        )
        self.user_portal = new_test_user(
            self.env, login='seges_e4p_portal', groups='base.group_portal',
            password='seges_e4p_portal',
        )
        self.logins = (self.user_internal.login, self.user_portal.login)
        self.provider = self.env['ai.provider'].sudo().create({
            'name': 'Seges E4p',
            'endpoint': 'https://seges.invalid/v1/chat/completions',
        })

    # ── Parche 30 ────────────────────────────────────────────────────────────

    def test_log_foreign_user_refused(self):
        admin_id = self.env.ref('base.user_admin').id
        for login in self.logins:
            for method, args, kwargs in LOG_CALLS:
                with self.subTest(login=login, method=method):
                    res = self._rpc(
                        login, 'ai.execution.engine', method, [[]] + args,
                        dict(kwargs, user_id=admin_id))
                    self._assert_error(res, 'odoo.exceptions.AccessError')

    def test_log_portal_refused(self):
        for method, args, kwargs in LOG_CALLS:
            with self.subTest(method=method):
                res = self._rpc(
                    self.user_portal.login, 'ai.execution.engine', method,
                    [[]] + args, kwargs)
                self._assert_error(res, 'odoo.exceptions.AccessError')

    def test_log_own_rpc_allowed(self):
        # Aceptado (hoja, ficha 1): un interno escribe a su propio nombre.
        for method, args, kwargs in WRITING_LOG_CALLS:
            with self.subTest(method=method):
                res = self._rpc(
                    self.user_internal.login, 'ai.execution.engine', method,
                    [[]] + args, kwargs)
                self.assertNotIn('error', res, res)

    # ── Parche 31 ────────────────────────────────────────────────────────────

    def test_chat_completion_rpc_refused(self):
        driver = MagicMock()
        driver.chat_completion.return_value = FAKE_RESPONSE
        Engine = _engine_class(self.env)
        with patch.object(Engine, 'get_providers_for_agent',
                          _fake_providers(self.provider.id)), \
                patch.object(Engine, '_driver_for_provider',
                             return_value=driver) as make_driver:
            for login in self.logins:
                with self.subTest(login=login):
                    res = self._rpc(
                        login, 'ai.execution.engine', 'chat_completion',
                        [[], AGENT, MESSAGES])
                    self._assert_error(res, 'odoo.exceptions.AccessError')
        make_driver.assert_not_called()
        driver.chat_completion.assert_not_called()

    # ── Parche 33 ────────────────────────────────────────────────────────────

    def test_month_usage_rpc_refused(self):
        for login in self.logins:
            with self.subTest(login=login):
                res = self._rpc(
                    login, 'ai.provider', 'month_usage', [[self.provider.id]])
                self._assert_error(res, 'builtins.AttributeError')
                res = self._rpc(
                    login, 'ai.provider', '_month_usage', [[self.provider.id]])
                self._assert_error(res, 'odoo.exceptions.AccessError')

    def test_usage_wizard_default_get_rpc_refused(self):
        for login in self.logins:
            with self.subTest(login=login):
                res = self._rpc(
                    login, 'ai.provider.usage.wizard', 'default_get',
                    [['total_tokens', 'cost_display']],
                    {'context': {'default_provider_id': self.provider.id}})
                self._assert_error(res, 'odoo.exceptions.AccessError')
                self.assertNotIn('total_tokens', json.dumps(res))

    def test_usage_wizard_onchange_rpc_refused(self):
        # Primera llamada de onchange: Odoo 14 llama a default_get.
        for login in self.logins:
            with self.subTest(login=login):
                res = self._rpc(
                    login, 'ai.provider.usage.wizard', 'onchange',
                    [[], {}, [], {
                        'provider_id': '', 'total_tokens': '',
                        'cost_display': '',
                    }],
                    {'context': {'default_provider_id': self.provider.id}})
                self._assert_error(res, 'odoo.exceptions.AccessError')
                self.assertNotIn('total_tokens', json.dumps(res))


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e4p')
class TestSegesE4pLogRows(TransactionCase):
    """Parche 30: sin enter_test_mode, ``_create_log_entry`` confirma en su
    cursor. Usuarios ya guardados en la BD: uno creado en la transacción del
    test no existe para ese cursor y el INSERT fallaría, escondiendo el defecto.
    """

    def setUp(self):
        super().setUp()
        self.admin = self.env.ref('base.user_admin')
        self._purge()
        self.addCleanup(self._purge)

    def _committed_count(self):
        with self.env.registry.cursor() as cr:
            cr.execute(
                'SELECT count(*) FROM ai_log WHERE endpoint = %s', (LOG_ENDPOINT,))
            return cr.fetchone()[0]

    def _committed_user_ids(self):
        with self.env.registry.cursor() as cr:
            cr.execute(
                'SELECT user_id FROM ai_log WHERE endpoint = %s', (LOG_ENDPOINT,))
            return [row[0] for row in cr.fetchall()]

    def _purge(self):
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            env['ai.log'].search([('endpoint', '=', LOG_ENDPOINT)]).unlink()
            # Lo que se escapó está confirmado en otra transacción: se borra igual.
            cr.commit()  # pylint: disable=invalid-commit

    def _log(self, user, **kwargs):
        engine = self.env['ai.execution.engine'].with_user(user)
        return engine.log_llm_inference(
            False, {'total_tokens': 1}, endpoint=LOG_ENDPOINT, **kwargs)

    def test_foreign_user_leaves_no_row(self):
        with self.assertRaises(AccessError):
            self._log(self.admin, user_id=SUPERUSER_ID)
        self.assertEqual(self._committed_count(), 0)

    def test_external_user_leaves_no_row(self):
        with self.assertRaises(AccessError):
            self._log(self.env.ref('base.public_user'))
        self.assertEqual(self._committed_count(), 0)

    def test_own_row_written(self):
        self._log(self.admin)
        self.assertEqual(self._committed_count(), 1)
        self.assertEqual(self._committed_user_ids(), [self.admin.id])


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e4p')
class TestSegesE4pChatCompletion(TransactionCase):
    """Parche 31 desde Python. El driver simulado no es el
    ``_LoggedProviderDriver``: no se escriben filas."""

    def setUp(self):
        super().setUp()
        self.internal = new_test_user(
            self.env, login='seges_e4p_cc_internal', groups='base.group_user',
        )
        self.provider = self.env['ai.provider'].sudo().create({
            'name': 'Seges E4p cc',
            'endpoint': 'https://seges.invalid/v1/chat/completions',
        })
        self.driver = MagicMock()
        self.driver.chat_completion.return_value = FAKE_RESPONSE
        Engine = _engine_class(self.env)
        patcher = patch.object(
            Engine, 'get_providers_for_agent', _fake_providers(self.provider.id))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.object(
            Engine, '_driver_for_provider', return_value=self.driver)
        self.make_driver = patcher.start()
        self.addCleanup(patcher.stop)

    def test_direct_call_refused(self):
        engine = self.env['ai.execution.engine'].with_user(self.internal)
        with self.assertRaises(AccessError):
            engine.chat_completion(AGENT, MESSAGES)
        self.make_driver.assert_not_called()
        self.driver.chat_completion.assert_not_called()

    def test_sudo_call_works(self):
        engine = self.env['ai.execution.engine'].with_user(self.internal)
        res = engine.sudo().chat_completion(AGENT, MESSAGES)
        self.assertEqual(res, FAKE_RESPONSE)
        self.driver.chat_completion.assert_called_once()


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e4p')
class TestSegesE4pTrustedAction(TransactionCase):
    """Parche 32. ``execute_safe_plan`` escribe el diario en el mismo cursor:
    todo se deshace con la transacción del test."""

    def setUp(self):
        super().setUp()
        self.adm = new_test_user(
            self.env, login='seges_e4p_adm',
            groups='base.group_user,pns_ai_mcp.group_ai_admin',
        )
        self.sys_adm = new_test_user(
            self.env, login='seges_e4p_sys',
            groups='base.group_user,base.group_system,pns_ai_mcp.group_ai_admin',
        )
        self.env_adm = api.Environment(self.env.cr, self.adm.id, {})
        self.env_sys = api.Environment(self.env.cr, self.sys_adm.id, {})
        self.ai_admin_group = self.env.ref('pns_ai_mcp.group_ai_admin')
        self.readonly = self.env.ref(
            'pns_ai_mcp.trusted_action_view_set_field_readonly')
        # Como lo pone execute_plan_now: propuso el AI Administrator sin
        # Ajustes y confirmó el administrador de Ajustes.
        self.plan_ctx = {
            'ai_journal_user_id': self.adm.id,
            'ai_journal_confirmed_by_uid': self.sys_adm.id,
        }

    def _new_vals(self, code=NEW_CODE):
        return {
            'code': code,
            'label': 'Seges E4p',
            'model_id': self.env['ir.model']._get('res.partner').id,
            'preview_method': '_seges_e4p_preview',
            'apply_method': '_seges_e4p_apply',
        }

    def _count(self, code=NEW_CODE):
        return self.env['ai.trusted.action'].sudo().with_context(
            active_test=False).search_count([('code', '=', code)])

    def _clear_groups_step(self):
        return {
            'op': 'write', 'model': 'ai.trusted.action',
            'ids': [self.readonly.id], 'values': {'group_ids': [(5, 0, 0)]},
        }

    def _assert_readonly_groups_kept(self):
        self.readonly.invalidate_cache()
        self.assertEqual(self.readonly.group_ids, self.ai_admin_group)

    # ── Negativos: AI Administrator sin Ajustes ──────────────────────────────

    def test_ai_admin_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env_adm['ai.trusted.action'].create(self._new_vals())
        self.assertEqual(self._count(), 0)

    def test_ai_admin_cannot_write(self):
        action = self.env_adm['ai.trusted.action']._get('user.add_group')
        for vals in (
            {'apply_method': '_seges_e4p_apply'},
            {'group_ids': [(5, 0, 0)]},
            {'label': 'Seges E4p'},
            {'danger': 'low'},
            {'active': False},
        ):
            with self.subTest(vals=vals):
                with self.assertRaises(AccessError):
                    action.write(vals)
        action.invalidate_cache()
        action = action.sudo()
        self.assertEqual(action.apply_method, '_apply_user_add_group')
        self.assertEqual(action.group_ids, self.ai_admin_group)
        self.assertEqual(action.label, 'Add native security group to user')
        self.assertEqual(action.danger, 'high')
        self.assertTrue(action.active)

    def test_ai_admin_cannot_unlink(self):
        action = self.env_adm['ai.trusted.action']._get('user.add_group')
        with self.assertRaises(AccessError):
            action.unlink()
        self.assertTrue(action.sudo().exists())

    def test_ai_admin_cannot_copy(self):
        action = self.env_adm['ai.trusted.action']._get('user.add_group')
        with self.assertRaises(AccessError):
            action.copy({'code': NEW_CODE})
        self.assertEqual(self._count(), 0)

    def test_plan_create_step_refused(self):
        with self.assertRaises(AccessError):
            execute_safe_plan(self.env_adm, [{
                'op': 'create', 'model': 'ai.trusted.action',
                'values': self._new_vals(),
            }])
        self.assertEqual(self._count(), 0)

    def test_plan_write_step_refused(self):
        with self.assertRaises(AccessError):
            execute_safe_plan(self.env_adm, [self._clear_groups_step()])
        self._assert_readonly_groups_kept()

    # ── Negativos: «confused deputy» ─────────────────────────────────────────

    def test_plan_confirmed_for_ai_admin_refused(self):
        # El caso que deja pasar is_system() solo.
        with self.assertRaises(AccessError):
            execute_safe_plan(
                self.env_sys(context=self.plan_ctx), [self._clear_groups_step()])
        self._assert_readonly_groups_kept()

    def test_sudo_in_plan_context_refused(self):
        action = self.env_sys['ai.trusted.action'].with_context(
            **self.plan_ctx).sudo().browse(self.readonly.id)
        with self.assertRaises(AccessError):
            action.write({'group_ids': [(5, 0, 0)]})
        self._assert_readonly_groups_kept()

    # ── Controles ────────────────────────────────────────────────────────────

    def test_settings_admin_can_edit(self):
        action = self.env_sys['ai.trusted.action'].create(self._new_vals())
        action.write({'label': 'Seges E4p 2', 'danger': 'low'})
        self.assertEqual(action.label, 'Seges E4p 2')
        action.unlink()
        self.assertEqual(self._count(), 0)

    def test_sudo_can_edit(self):
        action = self.env_adm['ai.trusted.action'].sudo().create(self._new_vals())
        action.write({'label': 'Seges E4p 2', 'danger': 'low'})
        self.assertEqual(action.label, 'Seges E4p 2')
        action.unlink()
        self.assertEqual(self._count(), 0)

    def test_factory_data_reload(self):
        Data = self.env['ir.model.data']
        before = {
            xmlid: Data.xmlid_to_res_id('pns_ai_mcp.' + xmlid)
            for xmlid in TRUSTED_XMLIDS
        }
        # Como un -u: la carga de datos corre en su.
        convert_file(
            self.cr, 'pns_ai_mcp', 'data/trusted_actions_system.xml', {},
            'update', False, 'data')
        Data.invalidate_cache()
        for xmlid in TRUSTED_XMLIDS:
            with self.subTest(xmlid=xmlid):
                res_id = Data.xmlid_to_res_id('pns_ai_mcp.' + xmlid)
                self.assertTrue(before[xmlid])
                self.assertEqual(res_id, before[xmlid])
                self.assertTrue(
                    self.env['ai.trusted.action'].browse(res_id).exists())

    def test_plan_settings_admin_allowed(self):
        # Propuesto y confirmado por el administrador de Ajustes: se aplica.
        ctx = {
            'ai_journal_user_id': self.sys_adm.id,
            'ai_journal_confirmed_by_uid': self.sys_adm.id,
        }
        execute_safe_plan(self.env_sys(context=ctx), [self._clear_groups_step()])
        self.readonly.invalidate_cache()
        self.assertFalse(self.readonly.group_ids)


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e4p')
class TestSegesE4pUsage(TransactionCase):
    """Parche 33 desde Python. ``_month_usage`` solo lee."""

    def setUp(self):
        super().setUp()
        self.internal = new_test_user(
            self.env, login='seges_e4p_usage_internal', groups='base.group_user',
        )
        self.ai_admin = new_test_user(
            self.env, login='seges_e4p_usage_adm',
            groups='base.group_user,pns_ai_mcp.group_ai_admin',
        )
        self.provider = self.env['ai.provider'].sudo().create({
            'name': 'Seges E4p usage',
            'endpoint': 'https://seges.invalid/v1/chat/completions',
        })

    def _wizard(self, user):
        return self.env['ai.provider.usage.wizard'].with_user(user).with_context(
            default_provider_id=self.provider.id)

    def test_month_usage_public_name_gone(self):
        Provider = type(self.env['ai.provider'])
        self.assertFalse(hasattr(Provider, 'month_usage'))
        self.assertTrue(hasattr(Provider, '_month_usage'))

    def test_default_get_refused_for_internal(self):
        with self.assertRaises(AccessError):
            self._wizard(self.internal).default_get(
                ['provider_id', 'period_label', 'total_tokens'])

    def test_default_get_ai_admin_sees_figures(self):
        res = self._wizard(self.ai_admin).default_get(
            ['provider_id', 'period_label', 'total_tokens'])
        self.assertEqual(res.get('provider_id'), self.provider.id)
        self.assertIn('period_label', res)
        self.assertIn('total_tokens', res)

    def test_spend_cap_still_works(self):
        res = self.provider.with_user(self.internal).spend_cap_reached()
        self.assertIsInstance(res, bool)
