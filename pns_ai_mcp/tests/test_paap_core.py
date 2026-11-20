# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""PAAP I1 and I3 on a live registry: a proposal changes nothing, and a verb
outside the closed vocabulary never runs."""
from odoo import api
from odoo.tests import tagged, TransactionCase
from odoo.addons.pns_ai_mcp.tests._helpers import (
    SKIP_CONTACT_ORIGIN,
    make_user,
    one_cursor,
)

from odoo.addons.pns_ai_mcp.controllers.safe_plan import (
    execute_safe_plan,
    request_safe_plan,
    validate_safe_plan,
)


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestPaapCore(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, **SKIP_CONTACT_ORIGIN))
        self.writer = make_user(
            self.env, 'pns_paap_core_writer',
            groups='base.group_user,base.group_partner_manager,'
                   'pns_ai_mcp.group_ai_writer',
        )
        self.env_w = api.Environment(self.env.cr, self.writer.id, {})
        self.partner = self.env['res.partner'].create({
            'name': 'PAAP core', 'ref': 'before',
        })

    def test_paap_i1_a_proposal_changes_nothing_and_hands_out_no_credential(self):
        """PAAP I1: propose stores a pending plan; the record stays as it was."""
        with one_cursor(self):
            result = request_safe_plan(self.env_w, [{
                'op': 'write', 'model': 'res.partner',
                'ids': [self.partner.id], 'values': {'ref': 'after'},
            }], title='PAAP I1')
        self.assertTrue(result.get('success'), result)
        self.assertEqual(self.partner.ref, 'before')
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
