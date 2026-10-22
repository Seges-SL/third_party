# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""PAAP I1 and I3 on a live registry: a proposal changes nothing, and a verb
outside the closed vocabulary never runs."""
from odoo import SUPERUSER_ID, api
from odoo.tests import tagged, TransactionCase
from odoo.tests.common import new_test_user

from odoo.addons.pns_ai_mcp.controllers.safe_plan import (
    execute_safe_plan,
    request_safe_plan,
    validate_safe_plan,
)


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestPaapCore(TransactionCase):

    def setUp(self):
        super().setUp()
        self.writer = new_test_user(
            self.env, login='pns_paap_core_writer',
            groups='base.group_user,base.group_partner_manager,'
                   'pns_ai_mcp.group_ai_writer',
        )
        self.env_w = api.Environment(self.env.cr, self.writer.id, {})
        self.partner = self.env['res.partner'].create({
            'name': 'PAAP core', 'comment': 'before',
        })

    def _unlink_verification(self, verification_id):
        if not verification_id:
            return
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            env['ai.safe.operation'].search([
                ('verification_id', '=', verification_id),
            ]).unlink()
            cr.commit()

    def test_paap_i1_a_proposal_changes_nothing_and_hands_out_no_credential(self):
        """PAAP I1: propose stores a pending plan; the record stays as it was."""
        result = request_safe_plan(self.env_w, [{
            'op': 'write', 'model': 'res.partner',
            'ids': [self.partner.id], 'values': {'comment': 'after'},
        }], title='PAAP I1')
        self.addCleanup(self._unlink_verification, result.get('verification_id'))
        self.assertTrue(result.get('success'), result)
        self.assertEqual(self.partner.comment, 'before')
        self.assertEqual(
            set(result),
            {'success', 'verification_id', 'plan', 'danger_level', 'title', 'user_id'},
        )

    def test_paap_i3_a_verb_outside_the_vocabulary_never_runs(self):
        """PAAP I3: closed verbs at propose and at execute; no method call by name."""
        for op in ('eval', 'sql', 'method', 'call_kw', 'mcp_exec'):
            step = {
                'op': op, 'model': 'res.partner',
                'ids': [self.partner.id], 'method': 'unlink',
            }
            ok, err = validate_safe_plan([dict(step)], self.env_w)
            self.assertFalse(ok, op)
            self.assertIn("invalid 'op'", err)
            with self.assertRaises(PermissionError):
                execute_safe_plan(self.env_w, [dict(step)])
        self.assertTrue(self.partner.exists())
