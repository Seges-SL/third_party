# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""RelaxAICode sandbox E2E: real pipeline (AST → context → compile → exec).

Unlike the host unit file (unit_tests/test_relaxaicode_sandbox_escapes.py),
this runs the full ``tool_relaxaicode`` tool on a real Odoo env (box-A
read-only cursor included). Each escape payload must end in a controlled
error (never an uncaught exception or a result that reached dangerous
objects), and legitimate code must still work.

The corpus is inlined here (a minimal copy of unit_tests/) because
unit_tests/ is not shipped inside the addon at Odoo runtime.

Production: tag ``pns_intrusion`` + skip unless the DB is *prueba*/*test*
(the isolated box-A cursor can escape the TransactionCase rollback).
Safe host suite: ``./t.sh --intrusion-only``.
"""
import json

from odoo.tests import tagged, TransactionCase
from odoo.tools import mute_logger

from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import (
    tool_relaxaicode,
)
from odoo.addons.pns_ai_mcp.tests._helpers import (
    SKIP_CONTACT_ORIGIN,
    skip_unless_safe_test_db_for_intrusion,
)
from odoo.addons.pns_ai_mcp.utils.compat import invalidate_recordset_fields


# Payloads that MUST fail under control (AST or runtime).
ESCAPE_PAYLOADS = [
    # ── AST block (literal) ────────────────────────────────────────────────
    "result = ().__class__.__bases__[0].__subclasses__()",
    "result = {}.__class__.__mro__",
    "result = '{0.__class__}'.format(())",
    "result = string.Formatter().get_field('0.__class__', [()], {})",
    "import os\nresult = os.getcwd()",
    "result = __import__('os').getcwd()",
    "class X(object):\n    pass\nresult = 1",
    "result = type('X', (), {})",
    "try:\n    1 / 0\nexcept Exception as e:\n    result = e.__traceback__\n",
    # ── RUNTIME block (dynamic name, invisible to the AST) ─────────────────
    "n = '__cla' + 'ss__'\nresult = getattr((), n)",
    "n1 = '__cla' + 'ss__'\nn2 = '__ba' + 'ses__'\nresult = getattr(getattr((), n1), n2)",
    "n = 'f_' + 'globals'\nresult = getattr((lambda: 0), n, 'NO')",
    # ── External API bypass via ORM (Safe Plan api_call is mandatory) ─────
    "srv = env['ai.api.server'].search([], limit=1)\nresult = srv._get_driver().call(srv, 'X', {}, auth_token='t')",
    "n = '_get_' + 'driver'\nresult = getattr(env['ai.api.server'].search([], limit=1), n)",
    # F1IZ theater: search/browse + spec_json (no drivers).
    "srv = env['ai.api.server'].search([('code', '=', 'x')], limit=1)\nresult = srv.spec_json",
    "srv = env['ai.api.server'].browse(6)\nresult = srv.spec_json",
    "recs = env['ai.context'].search([('code', 'ilike', 'self')])\nresult = [{'id': r.id, 'code': r.code} for r in recs]",
    "result = env.sudo()['ai.context'].search([])",
    "recs = env['ai.skill'].search([])\nresult = [{'code': r.code} for r in recs]",
    "result = env.sudo()['ai.skill'].search([])",
    # ── A safe module is not a door to os/sys or to open() ────────────────
    "import platform\nresult = platform.os.getcwd()",
    "result = uuid.os.getcwd()",
    "result = datetime.sys.modules",
    "result = io.open('/etc/hostname').read()",
    # ── Always as the user who asks: no sudo / with_user / env(su) ─────────
    "result = env.sudo()['ai.provider'].search([]).mapped('api_key')",
    "result = getattr(env.user, 'su' + 'do')().name",
    "result = env(su=True)['res.users'].search_count([])",
    # ── A public name that leads to the connection (env.args, env.all, .cursor) ─
    "result = str(type(env.args[0]))",
    "x = getattr(env.args[0], 'exe' + 'cute')\nx('ROLLBACK')\nresult = 1",
    "result = type(env.all[0])",
    "try:\n    env['res.partner'].search([('create_date', '=', 'not-a-date')])\n"
    "except Exception as e:\n    run = e.cursor.execute\n    run('ROLLBACK')\nresult = 1",
    # ── Readers that walk attributes in C (Formatter, str.format, match) ───
    "import string\nF = getattr(string, 'Form' + 'atter')()\n"
    "x = getattr(F, 'get_' + 'field')('0.env.cr.execute', [env.user], {})[0]\n"
    "x('ROLLBACK')\nresult = 1",
    "t = '{0.e' + 'nv.cr}'\nresult = t.format(env.user)",
    "result = str.format('{u.e' + 'nv.cr}', u=env.user)",
    "u = env.user\nT = type(u)\nmatch u:\n    case T(env=E):\n        pass\nresult = str(E)",
]

# Obfuscated ORM mutators: they must flag requires_write (box B) or fail
# under control — never run a write in box A (finding A6 2026-08-12).
WRITE_BYPASS_PAYLOADS = [
    "p = env['res.partner'].search([], limit=1)\ngateway = getattr(p, 'wr' + 'ite')\nresult = gateway({'comment': 'PNS_INTRUSION_SHOULD_NOT_PERSIST'})",
    "p = env['res.partner'].search([], limit=1)\nresult = getattr(p, 'write')({'comment': 'PNS_INTRUSION_SHOULD_NOT_PERSIST'})",
    "from operator import attrgetter\np = env['res.partner'].search([], limit=1)\nresult = attrgetter('write')(p)({'comment': 'PNS_INTRUSION_SHOULD_NOT_PERSIST'})",
]


# Markers that must never show up in a reply (they would mean a real leak).
LEAK_MARKERS = (
    "subprocess",
    "posix",
    "_frozen_importlib",
    "<frame",
    "built-in function system",
    "os.getcwd",
)


def _is_controlled_write_reject(text):
    """True if box A rejected the write (requires_write) or a controlled error."""
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
    """Each escape attempt ends in a controlled error; legitimate code works."""

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

    # Some payloads send PostgreSQL a bad value on purpose; it logs the query.
    @mute_logger('odoo.sql_db')
    def test_escape_payloads_fail_controlled(self):
        """PAAP I9: Escape payloads fail under control on a live registry."""
        for code in ESCAPE_PAYLOADS:
            resp, text = self._run(code)
            # 1) It ended in a controlled error (never a success dict with data).
            self.assertIn(
                'ERROR (', text,
                "El payload de fuga debería fallar de forma controlada:\n%s\n→ %s"
                % (code, text[:400]),
            )
            # 2) It leaked no sign of having reached dangerous objects.
            low = text.lower()
            for marker in LEAK_MARKERS:
                self.assertNotIn(
                    marker.lower(), low,
                    "FUGA: el payload alcanzó '%s':\n%s\n→ %s"
                    % (marker, code, text[:400]),
                )

    def test_legit_code_still_works(self):
        # Anti false-positive: pure computation must not be blocked or fail.
        resp, text = self._run("result = {'ok': sum([1, 2, 3])}")
        self.assertNotIn('ERROR (', text, "Código legítimo NO debería fallar: %s" % text[:400])

    def test_legit_getattr_and_format_ok(self):
        # ORM getattr (normal name) and str.format without dunders stay allowed.
        resp, text = self._run(
            "u = env.user\n"
            "result = {'name': getattr(u, 'name', ''), 's': '{0}-{1}'.format('a', 'b')}"
        )
        self.assertNotIn('ERROR (', text, text[:400])

    def test_obfuscated_orm_write_rejected(self):
        """PAAP I2 / A6: getattr/attrgetter towards write must not run in box A."""
        for code in WRITE_BYPASS_PAYLOADS:
            resp, text = self._run(code)
            self.assertTrue(
                _is_controlled_write_reject(text),
                "Write ofuscado debería requires_write o ERROR controlado:\n%s\n→ %s"
                % (code, text[:500]),
            )

    def test_obfuscated_write_does_not_persist(self):
        """A6 no-persistence oracle: comment does not change after the attempt."""
        partner = self.env['res.partner'].with_context(**SKIP_CONTACT_ORIGIN).create({
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
        invalidate_recordset_fields(partner, ['comment'])
        self.assertNotEqual(
            partner.comment,
            marker,
            "FUGA A6: el write ofuscado PERSISTIÓ en res.partner(%s)" % partner.id,
        )
