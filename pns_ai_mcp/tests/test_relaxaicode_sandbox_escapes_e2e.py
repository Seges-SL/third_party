# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""E2E del sandbox RelaxAICode: pipeline REAL (AST → contexto → compile → exec).

A diferencia del unit de host (unit_tests/test_relaxaicode_sandbox_escapes.py),
aquí se ejecuta la herramienta completa `tool_relaxaicode` sobre un env
Odoo real (cursor caja A READ ONLY incluido). Se comprueba que cada payload de
fuga termina en un error CONTROLADO (nunca una excepción no capturada ni un
resultado que haya alcanzado objetos peligrosos) y que el código legítimo sigue
funcionando.

El corpus se mantiene aquí en línea (una copia mínima del de unit_tests/), porque
unit_tests/ no viaja dentro del addon en runtime de Odoo.

**Producción:** tag ``pns_intrusion`` + skip si la BD no es *prueba*/*test*
(el cursor aislado de caja A puede escapar del rollback del TransactionCase).
Suite host segura: ``./t.sh --intrusion-only``.
"""
import json

from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import (
    tool_relaxaicode,
)
from odoo.addons.pns_ai_mcp.tests._helpers import (
    skip_unless_safe_test_db_for_intrusion,
)


# Payloads que DEBEN fallar de forma controlada (AST o runtime).
ESCAPE_PAYLOADS = [
    # ── Bloqueo AST (literal) ──────────────────────────────────────────────
    "result = ().__class__.__bases__[0].__subclasses__()",
    "result = {}.__class__.__mro__",
    "result = '{0.__class__}'.format(())",
    "result = string.Formatter().get_field('0.__class__', [()], {})",
    "import os\nresult = os.getcwd()",
    "result = __import__('os').getcwd()",
    "class X(object):\n    pass\nresult = 1",
    "result = type('X', (), {})",
    "try:\n    1 / 0\nexcept Exception as e:\n    result = e.__traceback__\n",
    # ── Bloqueo en RUNTIME (nombre dinámico, invisible al AST) ──────────────
    "n = '__cla' + 'ss__'\nresult = getattr((), n)",
    "n1 = '__cla' + 'ss__'\nn2 = '__ba' + 'ses__'\nresult = getattr(getattr((), n1), n2)",
    "n = 'f_' + 'globals'\nresult = getattr((lambda: 0), n, 'NO')",
    # ── Bypass API externa vía ORM (Safe Plan api_call obligatorio) ───────
    "srv = env['ai.api.server'].search([], limit=1)\nresult = srv._get_driver().call(srv, 'X', {}, auth_token='t')",
    "n = '_get_' + 'driver'\nresult = getattr(env['ai.api.server'].search([], limit=1), n)",
    # Teatro F1IZ: search/browse + spec_json (sin drivers).
    "srv = env['ai.api.server'].search([('code', '=', 'x')], limit=1)\nresult = srv.spec_json",
    "srv = env['ai.api.server'].browse(6)\nresult = srv.spec_json",
    "recs = env['ai.context'].search([('code', 'ilike', 'self')])\nresult = [{'id': r.id, 'code': r.code} for r in recs]",
    "result = env.sudo()['ai.context'].search([])",
]

# Mutadores ORM ofuscados: deben marcar requires_write (caja B) o fallar
# controlado — nunca ejecutar write en caja A (hallazgo A6 2026-08-12).
WRITE_BYPASS_PAYLOADS = [
    "p = env['res.partner'].search([], limit=1)\ngateway = getattr(p, 'wr' + 'ite')\nresult = gateway({'comment': 'PNS_INTRUSION_SHOULD_NOT_PERSIST'})",
    "p = env['res.partner'].search([], limit=1)\nresult = getattr(p, 'write')({'comment': 'PNS_INTRUSION_SHOULD_NOT_PERSIST'})",
    "from operator import attrgetter\np = env['res.partner'].search([], limit=1)\nresult = attrgetter('write')(p)({'comment': 'PNS_INTRUSION_SHOULD_NOT_PERSIST'})",
]


# Marcadores que jamás deben aparecer en una respuesta (indicarían fuga real).
LEAK_MARKERS = (
    "subprocess",
    "posix",
    "_frozen_importlib",
    "<frame",
    "built-in function system",
    "os.getcwd",
)


def _is_controlled_write_reject(text):
    """True si caja A rechazó escritura (requires_write) o error controlado."""
    if 'requires_write' in text:
        return True
    if 'ERROR (' in text:
        return True
    low = text.lower()
    if 'mutator' in low or 'not allowed in relaxaicode' in low:
        return True
    return False


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'pns_intrusion')
class TestRelaxAICodeSandboxEscapesE2E(TransactionCase):
    """Cada intento de fuga acaba en error controlado; lo legítimo funciona."""

    def setUp(self):
        super(TestRelaxAICodeSandboxEscapesE2E, self).setUp()
        skip_unless_safe_test_db_for_intrusion(self)

    def _make_controller(self):
        env = self.env

        class _StubController:
            def __init__(self, e):
                self.env = e

            def _get_env_for_operation(self, operation_type='read'):
                return self.env

            def _get_readonly_env(self):
                from odoo.addons.pns_ai_mcp.controllers.controller_helpers import (
                    get_readonly_env,
                )
                return get_readonly_env(self)

            def _check_mcp_permissions(self, operation_type):
                return True, ""

            def _cancel_pending_verifications_for_user(self, user_id, reason=""):
                return 0

            def _get_user_locale(self):
                try:
                    return self.env.user.lang or 'en_US'
                except Exception:
                    return 'en_US'

            def _get_company_lang(self):
                return False

            def _log_mcp_operation(self, *args, **kwargs):
                return None

        return _StubController(env)

    def _run(self, code):
        resp = tool_relaxaicode(self._make_controller(), {'code': code})
        try:
            text = resp['content'][0]['text']
        except Exception:
            text = json.dumps(resp, default=str)
        return resp, text

    def test_escape_payloads_fail_controlled(self):
        for code in ESCAPE_PAYLOADS:
            resp, text = self._run(code)
            # 1) Terminó en error controlado (nunca dict de éxito con datos).
            self.assertIn(
                'ERROR (', text,
                "El payload de fuga debería fallar de forma controlada:\n%s\n→ %s"
                % (code, text[:400]),
            )
            # 2) No filtró evidencia de haber alcanzado objetos peligrosos.
            low = text.lower()
            for marker in LEAK_MARKERS:
                self.assertNotIn(
                    marker.lower(), low,
                    "FUGA: el payload alcanzó '%s':\n%s\n→ %s"
                    % (marker, code, text[:400]),
                )

    def test_legit_code_still_works(self):
        # Anti falso-positivo: cálculo puro no debe bloquearse ni fallar.
        resp, text = self._run("result = {'ok': sum([1, 2, 3])}")
        self.assertNotIn('ERROR (', text, "Código legítimo NO debería fallar: %s" % text[:400])

    def test_legit_getattr_and_format_ok(self):
        # getattr ORM (nombre normal) y str.format sin dunder siguen permitidos.
        resp, text = self._run(
            "u = env.user\n"
            "result = {'name': getattr(u, 'name', ''), 's': '{0}-{1}'.format('a', 'b')}"
        )
        self.assertNotIn('ERROR (', text, text[:400])

    def test_obfuscated_orm_write_rejected(self):
        """A6: getattr/attrgetter hacia write no debe ejecutar en caja A."""
        for code in WRITE_BYPASS_PAYLOADS:
            resp, text = self._run(code)
            self.assertTrue(
                _is_controlled_write_reject(text),
                "Write ofuscado debería requires_write o ERROR controlado:\n%s\n→ %s"
                % (code, text[:500]),
            )

    def test_obfuscated_write_does_not_persist(self):
        """A6 oráculo de no-persistencia: comment no cambia tras el intento."""
        partner = self.env['res.partner'].create({
            'name': 'PNS_INTRUSION_E2E_CANARY',
            'comment': False,
        })
        marker = 'PNS_INTRUSION_E2E_WRITE_MARKER'
        code = (
            "p = env['res.partner'].browse(%d)\n"
            "getattr(p, 'wr' + 'ite')({'comment': %r})\n"
            "result = {'wrote': True}"
        ) % (partner.id, marker)
        resp, text = self._run(code)
        self.assertTrue(
            _is_controlled_write_reject(text),
            "Debe rechazar write ofuscado:\n%s" % text[:500],
        )
        partner.invalidate_cache()
        self.assertNotEqual(
            partner.comment,
            marker,
            "FUGA A6: el write ofuscado PERSISTIÓ en res.partner(%s)" % partner.id,
        )
