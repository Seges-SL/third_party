# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""A skill's code_body runs in box A, like relaxaicode.

Its own READ ONLY cursor, closed when the body ends. The caller's cursor can
write; the skill never holds it.
"""
from unittest.mock import patch

from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.controllers import controller_helpers
from odoo.addons.pns_ai_mcp.utils.skill_runtime import bootstrap_skill_code_body


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestSkillBoxA(TransactionCase):

    def _run(self, code):
        opened = []
        real = controller_helpers.open_readonly_env

        def _spy(env):
            ro_env, cr = real(env)
            opened.append(cr)
            return ro_env, cr

        diag = {}
        with patch.object(controller_helpers, 'open_readonly_env', _spy):
            result = bootstrap_skill_code_body(
                self.env, code, skill_code='box_a_test', diag=diag,
            )
        return result, opened, diag

    def test_body_runs_on_its_own_cursor_and_closes_it(self):
        result, opened, diag = self._run("result = {'uid': env.uid}")
        self.assertEqual(result, {'uid': self.env.uid}, diag)
        self.assertEqual(len(opened), 1)
        self.assertIsNot(opened[0], self.env.cr)
        cr = opened[0]
        self.assertTrue(getattr(cr, 'closed', getattr(cr, '_closed', False)))

    def test_a_returned_record_is_usable_after_the_box_closes(self):
        result, _opened, diag = self._run("result = {'me': env.user}")
        self.assertTrue(result, diag)
        self.assertIs(result['me'].env.cr, self.env.cr)
        self.assertEqual(result['me'].name, self.env.user.name)
