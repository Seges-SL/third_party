# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 15 (tests de la entrega E1′). Ver docs/pendiente/parches_pns_ai.md
"""Parche 15 (PNS-07): el sandbox no alcanza métodos públicos que escriben en un
cursor propio (``fulfill_client_export`` y los demás de la lista de E1′).

Sin ``enter_test_mode`` ni ``HttpCase``: con el registro en modo test, el cursor
propio comparte la transacción del test y el defecto no se ve. El código se
ejecuta en la caja A real (``get_readonly_env``, cursor READ ONLY con el commit
bloqueado) como un usuario ya guardado en la BD (``base.user_admin``): uno
creado en la transacción del test no existe para el cursor propio y
``_run_on_committed_cursor`` volvería al entorno del llamador, escondiendo el
defecto. Lo que se escape se busca y se borra desde un cursor nuevo.
"""

import base64

from odoo import SUPERUSER_ID, api
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger

from odoo.addons.pns_ai_mcp.controllers.context_builder import (
    build_safe_context,
    guarded_getattr,
    guarded_methodcaller,
)
from odoo.addons.pns_ai_mcp.controllers.controller_helpers import get_readonly_env
from odoo.addons.pns_ai_mcp.controllers.validators import (
    validate_relaxaicode_source_ast,
)
from odoo.addons.pns_ai_mcp.controllers.validators_base import (
    RELAXAICODE_SIDE_EFFECT_METHODS,
)
from odoo.addons.pns_ai_mcp.utils.session_download import persist_turn_file

# Métodos públicos con cursor propio añadidos a la lista en E1′ (parche 15).
E1P_NAMES = (
    'fulfill_client_export', 'mark_seen', 'sandbox_helpers', 'page_url',
    'page_html', 'page_edit', 'paint_canvas', 'get_content', 'get_for_agent',
    'chat_completion', 'log_role_without_provider', 'log_provider_failover',
    'log_provider_llm_request', 'log_provider_llm_response',
    'log_llm_inference', 'log_provider_inference', 'test_connection',
    'author_param_schema', 'author_param_help', 'rewrite_code_for_params',
    'collect', 'action_suggest_detection', 'action_author_params',
    'action_author_help', 'action_adapt_code', 'action_generate_openapi',
    'action_generate', 'action_log_generation_usage',
)
LEAK_NAME = 'seges-e1p-07-leak.pdf'
CONTROL_NAME = 'seges-e1p-07-control.pdf'


class _StubController:
    """Lo que la caja A pide al controlador MCP."""

    def __init__(self, env):
        self._env = env

    def _get_env_for_operation(self, operation_type='read'):
        return self._env

    def _get_user_locale(self):
        return 'en_US'


@tagged('post_install', '-at_install', 'pns_ai_chatboo', 'seges_e1p')
class TestSegesChatbooExport(TransactionCase):

    def setUp(self):
        super().setUp()
        self.admin = self.env.ref('base.user_admin')
        self.addCleanup(self._purge, (LEAK_NAME, CONTROL_NAME))

    def _committed_count(self, name):
        with self.env.registry.cursor() as cr:
            cr.execute('SELECT count(*) FROM ir_attachment WHERE name = %s', (name,))
            return cr.fetchone()[0]

    def _purge(self, names):
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            env['ir.attachment'].search([('name', 'in', list(names))]).unlink()
            # Lo que se escapó está confirmado en otra transacción: se borra igual.
            cr.commit()  # pylint: disable=invalid-commit

    def _run_in_box_a(self, code):
        """Ejecuta *code* en la caja A, como lo hace tool_relaxaicode."""
        stub = _StubController(self.env(user=self.admin))
        ro_env, ro_cr = get_readonly_env(stub)
        try:
            ctx = build_safe_context(stub, 'read', env_override=ro_env)
            # Igual que tool_relaxaicode: el código corre con el contexto del sandbox.
            exec(compile(code, '<relaxaicode>', 'exec'), ctx)  # noqa: S102  # pylint: disable=exec-used
            return ctx.get('result')
        finally:
            ro_cr.rollback()
            ro_cr.close()

    def test_names_in_denylist(self):
        for name in E1P_NAMES:
            self.assertIn(name, RELAXAICODE_SIDE_EFFECT_METHODS, name)
            with self.assertRaises(AttributeError, msg=name):
                guarded_getattr(object(), name)
            with self.assertRaises(AttributeError, msg=name):
                guarded_methodcaller(name)

    def test_ast_flags_literal_call(self):
        for name in E1P_NAMES:
            code = (
                f"x = env['chatboo.session'].browse(1).{name}()\n"
                "result = {'data': 1}\n"
            )
            valid, _error, requires_write = validate_relaxaicode_source_ast(code)
            # requires_write lleva a _read_only_response: no se ejecuta.
            self.assertTrue(requires_write or not valid, name)

    def test_control_own_cursor_commits(self):
        # Control: sin la caja A, persist_turn_file sí deja el adjunto confirmado.
        self.assertEqual(self._committed_count(CONTROL_NAME), 0)
        persist_turn_file(
            self.env(user=self.admin), 0, b'%PDF-1.4 seges', CONTROL_NAME,
            mimetype='application/pdf')
        self.assertEqual(self._committed_count(CONTROL_NAME), 1)

    def test_box_a_leaves_no_attachment(self):
        session = self.env['chatboo.session'].with_user(self.admin).create(
            {'name': 'Seges E1p 07'})
        datas = base64.b64encode(b'%PDF-1.4 seges').decode()
        code = (
            f"s = env['chatboo.session'].browse({session.id})\n"
            "f = getattr(s, 'fulfill_' + 'client_export')\n"
            f"f({LEAK_NAME!r}, '', {datas!r}, 'pdf')\n"
            "result = {'data': 1}\n"
        )
        outcome = None
        with mute_logger('odoo.addons.pns_ai_mcp.utils.session_download'):
            try:
                self._run_in_box_a(code)
            except Exception as exc:  # pylint: disable=broad-except
                # Sin el parche la llamada pasa y falla después (la sesión no
                # existe en la caja A): lo que cuenta es si el adjunto quedó.
                outcome = exc
        self.assertEqual(self._committed_count(LEAK_NAME), 0, outcome)
        self.assertIsInstance(outcome, AttributeError, outcome)


@tagged('post_install', '-at_install', 'pns_ai_chatboo', 'seges_e1p')
class TestSegesChatbooExportOwn(TransactionCase):
    """No regresión: la exportación propia se sigue enganchando a la sesión.

    Portado de 14.0-pns-ai-correcciones (``test_fulfill_client_export_claims_own``).
    Aquí, sin modo test, el usuario nuevo no existe para el cursor propio y el
    adjunto se crea por la vía de respaldo del fabricante (entorno del llamador).
    """

    def setUp(self):
        super().setUp()
        self.user_a = new_test_user(
            self.env, login='seges_e1p_07_a', groups='base.group_user',
        )
        self.cs_a = self.env['chatboo.session'].with_user(self.user_a).create(
            {'name': 'Seges E1p 07 A'})

    def _att_row(self, att_id):
        self.env['base'].flush()
        self.env.cr.execute(
            'SELECT res_model, res_id, create_uid FROM ir_attachment WHERE id = %s',
            (att_id,))
        return self.env.cr.fetchone()

    def _staged(self):
        self.env['base'].flush()
        self.env.cr.execute(
            'SELECT id, staged_assistant_files FROM chatboo_session WHERE id = %s',
            (self.cs_a.id,))
        return self.env.cr.fetchall()

    def test_fulfill_client_export_claims_own(self):
        cs = self.cs_a.with_user(self.user_a)
        chip = cs.fulfill_client_export(
            'seges-e1p.pdf', 'application/pdf',
            base64.b64encode(b'%PDF-1.4 seges').decode(), kind='pdf')
        self.assertTrue(chip)
        self.assertEqual(
            self._att_row(chip['attachment_id']),
            ('chatboo.session', self.cs_a.id, self.user_a.id))
        self.env['base'].flush()
        chips = cs._consume_staged_assistant_download_chips()
        self.assertEqual([c.get('attachment_id') for c in chips],
                         [chip['attachment_id']])
        self.assertIn((self.cs_a.id, None), self._staged())
