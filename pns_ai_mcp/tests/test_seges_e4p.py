# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: tests de la entrega E4′ (parches 30, 31, 32 y 33). Ver docs/pendiente/parches_pns_ai.md
# Seges: adaptado a 3.1.973 (fase 2a): 30 y 31 retirados; sus casos quedan como no regresión de los nombres privados del fabricante. Ver docs/pendiente/parches_pns_ai.md
# Seges: adaptado a la 17 (fase 2, T0): solo los casos del 30 y del 31 (los del 32 y el 33, en T1), flush_all(),
# assertRaises(AttributeError) en los tres casos en Python y mute_logger('odoo.http') en _rpc;
# los documentos que citan las líneas anteriores están en 14.0. Ver docs/pendiente/parches_pns_ai.md
"""Parches 30 a 33 (M11, M12, PNS-97 y PNS-29, resto 3).

En 3.1.973 el fabricante pasa los seis ``log_*`` y ``chat_completion`` a
privados (``_log_*``, ``_chat_completion``): los parches 30 y 31 se retiran. Sus
negativos aceptan también el error del nombre que ya no existe
(``AttributeError``) y los controles en Python llaman al método privado.

- 30: los ``log_*`` públicos del motor solo escriben, fuera del sistema, a nombre
  del usuario actual y si es interno.
- 31: ``chat_completion`` solo en ``su``.
- 32: ``create``, ``write`` y ``unlink`` de ``ai.trusted.action`` exigen Ajustes
  fuera de ``su`` y, dentro de un plan supervisado, también a quien lo propuso y
  a quien lo confirmó.
- 33: ``month_usage`` pasa a privado y ``default_get`` del asistente exige su ACL.

En 3.1.973 ``_create_log_entry`` no escribe mientras corre un test
(``test_is_running``): ``TestSegesE4pLogRows`` lo simula en lugar de contar
filas confirmadas.

En la 17 (fase 2, T0) solo están los casos del 30 y del 31; los del 32
(``TestSegesE4pTrustedAction``) y los del 33 (``TestSegesE4pUsage`` y los tres
de ``TestSegesE4pRpc``) entran en la tanda T1, con su parche.
"""

import inspect
import json
from unittest.mock import MagicMock, patch

from odoo import SUPERUSER_ID
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger

LOG_ENDPOINT = 'seges_e4p_m11'
AGENT = 'pns_ai_mcp'
MESSAGES = [{'role': 'user', 'content': 'x'}]
FAKE_RESPONSE = {'choices': [{'message': {'content': 'seges e4p'}}]}

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
# Seges: adaptado a 3.1.973 (parches 30 y 31 retirados: nombre privado). Ver docs/pendiente/parches_pns_ai.md
REFUSED_OR_GONE = ('odoo.exceptions.AccessError', 'builtins.AttributeError')


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
        # Seges: adaptado a la 17 (BaseModel.flush ya no existe: Environment.flush_all, odoo/api.py:735).
        self.env.flush_all()
        self.authenticate(login, login)
        payload = {
            'jsonrpc': '2.0', 'method': 'call', 'id': 1,
            'params': {
                'model': model, 'method': method,
                'args': args, 'kwargs': kwargs or {},
            },
        }
        # Seges: adaptado a la 17 (fase 2, T0): las llamadas rechazadas a propósito dejan su traza ERROR
        # en odoo.http; se silencia solo aquí, como en test_seges_rpc_access.py (decisión 136).
        with mute_logger('odoo.http'):
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

    # Seges: adaptado a 3.1.973 (parches 30 y 31 retirados: nombre privado). Ver docs/pendiente/parches_pns_ai.md
    def _assert_refused_or_gone(self, res):
        self.assertNotIn('result', res, res)
        self.assertIn('error', res, res)
        self.assertIn(res['error']['data']['name'], REFUSED_OR_GONE, res)


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
                    # Seges: adaptado a 3.1.973 (parche 30 retirado: nombre privado). Ver docs/pendiente/parches_pns_ai.md
                    self._assert_refused_or_gone(res)

    def test_log_portal_refused(self):
        for method, args, kwargs in LOG_CALLS:
            with self.subTest(method=method):
                res = self._rpc(
                    self.user_portal.login, 'ai.execution.engine', method,
                    [[]] + args, kwargs)
                # Seges: adaptado a 3.1.973 (parche 30 retirado: nombre privado). Ver docs/pendiente/parches_pns_ai.md
                self._assert_refused_or_gone(res)

    # Seges: adaptado a 3.1.973 (parche 30 retirado: nombre privado). Ver docs/pendiente/parches_pns_ai.md
    def test_log_own_rpc_refused(self):
        # Antes test_log_own_rpc_allowed (con el parche 30, un interno escribía
        # a su propio nombre). Negativo desde 3.1.973: el fabricante cierra
        # también esa escritura por RPC, porque los log_* ya no son públicos.
        for method, args, kwargs in WRITING_LOG_CALLS:
            with self.subTest(method=method):
                res = self._rpc(
                    self.user_internal.login, 'ai.execution.engine', method,
                    [[]] + args, kwargs)
                self._assert_error(res, 'builtins.AttributeError')

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
                    # Seges: adaptado a 3.1.973 (parche 31 retirado: nombre privado). Ver docs/pendiente/parches_pns_ai.md
                    self._assert_refused_or_gone(res)
        make_driver.assert_not_called()
        driver.chat_completion.assert_not_called()


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e4p')
class TestSegesE4pLogRows(TransactionCase):
    """Parche 30 (retirado en 3.1.973), en Python.

    Seges: adaptado a 3.1.973 (fase 2a). En 3.1.973 ``_create_log_entry`` no
    escribe mientras corre un test (``test_is_running``, ``utils/compat.py``):
    en lugar de contar filas confirmadas, se simula ``_create_log_entry`` y se
    comprueba si se llama y con qué ``user_id``.
    """

    def setUp(self):
        super().setUp()
        self.admin = self.env.ref('base.user_admin')

    # Seges: adaptado a 3.1.973 (parche 30 retirado: nombre privado). Ver docs/pendiente/parches_pns_ai.md
    def _log(self, user, method='log_llm_inference', **kwargs):
        engine = self.env['ai.execution.engine'].with_user(user)
        return getattr(engine, method)(
            False, {'total_tokens': 1}, endpoint=LOG_ENDPOINT, **kwargs)

    # Seges: adaptado a 3.1.973 (ai.log no escribe durante los tests). Ver docs/pendiente/parches_pns_ai.md
    def _patch_create_log_entry(self):
        return patch.object(
            type(self.env['ai.log']), '_create_log_entry', autospec=True)

    # Seges: adaptado a 3.1.973 (ai.log no escribe durante los tests). Ver docs/pendiente/parches_pns_ai.md
    def _logged_user_id(self, create):
        # Por nombre o por posición: se enlaza con la firma real del método.
        args, kwargs = create.call_args
        bound = inspect.signature(
            type(self.env['ai.log'])._create_log_entry).bind(*args, **kwargs)
        return bound.arguments['user_id']

    def test_foreign_user_leaves_no_row(self):
        # Seges: adaptado a 3.1.973 (parche 30 retirado: nombre privado). Ver docs/pendiente/parches_pns_ai.md
        with self._patch_create_log_entry() as create:
            # Seges: en la 14 se aceptaba AccessError o AttributeError; en la 17, AttributeError: el modelo
            # solo tiene _log_* (models/ai_execution_engine.py:425-781) y BaseModel no tiene __getattr__.
            with self.assertRaises(AttributeError):
                self._log(self.admin, user_id=SUPERUSER_ID)
        create.assert_not_called()

    def test_external_user_leaves_no_row(self):
        # Seges: adaptado a 3.1.973 (parche 30 retirado: nombre privado). Ver docs/pendiente/parches_pns_ai.md
        with self._patch_create_log_entry() as create:
            # Seges: en la 14 se aceptaba AccessError o AttributeError; en la 17, AttributeError: el modelo
            # solo tiene _log_* (models/ai_execution_engine.py:425-781) y BaseModel no tiene __getattr__.
            with self.assertRaises(AttributeError):
                self._log(self.env.ref('base.public_user'))
        create.assert_not_called()

    def test_own_row_written(self):
        # Seges: adaptado a 3.1.973 (parche 30 retirado: nombre privado; ai.log no escribe durante los tests). Ver docs/pendiente/parches_pns_ai.md
        with self._patch_create_log_entry() as create:
            self._log(self.admin, method='_log_llm_inference')
        create.assert_called_once()
        self.assertEqual(self._logged_user_id(create), self.admin.id)


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
        # Seges: adaptado a 3.1.973 (parche 31 retirado: nombre privado). Ver docs/pendiente/parches_pns_ai.md
        # Seges: en la 14 se aceptaba AccessError o AttributeError; en la 17, AttributeError: el modelo solo
        # tiene _chat_completion (models/ai_execution_engine.py:872; el :38 es del envoltorio del driver).
        with self.assertRaises(AttributeError):
            engine.chat_completion(AGENT, MESSAGES)
        self.make_driver.assert_not_called()
        self.driver.chat_completion.assert_not_called()

    def test_sudo_call_works(self):
        engine = self.env['ai.execution.engine'].with_user(self.internal)
        # Seges: adaptado a 3.1.973 (parche 31 retirado: nombre privado). Ver docs/pendiente/parches_pns_ai.md
        res = engine.sudo()._chat_completion(AGENT, MESSAGES)
        self.assertEqual(res, FAKE_RESPONSE)
        self.driver.chat_completion.assert_called_once()
