# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""friendly_skill_error() maps ORM/ACL failures to short UX strings."""
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.utils.skill_errors import friendly_skill_error


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestFriendlySkillError(TransactionCase):

    def test_access_error_keeps_odoo_message(self):
        msg = friendly_skill_error(
            AccessError(
                "Por restricciones de seguridad no tienes permiso "
                "para acceder a los informes de 'Cuenta' (account.account)."
            ),
            self.env,
        )
        self.assertIn('Cuenta', msg)
        self.assertNotIn('AccessError', msg)
        self.assertNotIn('ERROR', msg)

    def test_access_error_empty_falls_back(self):
        msg = friendly_skill_error(AccessError(''), self.env)
        self.assertIn('permission', msg.lower())

    def test_missing_error(self):
        msg = friendly_skill_error(MissingError('gone'), self.env)
        self.assertTrue(msg)
        self.assertNotIn('MissingError', msg)

    def test_user_error_passthrough(self):
        msg = friendly_skill_error(UserError('Pick a period first.'), self.env)
        self.assertEqual(msg, 'Pick a period first.')

    def test_invalid_field_on_public_model(self):
        msg = friendly_skill_error(
            ValueError(
                "Invalid field 'gp_employee_id' on model 'hr.employee.public'"
            ),
            self.env,
        )
        self.assertIn('permission', msg.lower())
        self.assertNotIn('gp_employee_id', msg)
        self.assertNotIn('ValueError', msg)

    def test_generic_fallback(self):
        msg = friendly_skill_error(RuntimeError('boom'), self.env)
        self.assertIn('RuntimeError', msg)
        self.assertIn('administrator', msg.lower())
