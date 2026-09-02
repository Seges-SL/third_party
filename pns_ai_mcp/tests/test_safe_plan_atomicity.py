# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Regression: ``execute_plan_now()`` must never mark ``executed=True`` unless
the business mutation commit actually succeeded first.

This is the exact atomicity bug behind the Rogelio incident: a Safe Plan
(``unlink acl.role.line`` + ``write res.users.groups_id``) was reported as
executed while none of it had actually persisted, because the old code
committed ``executed=True`` (in a short separate cursor) BEFORE the caller
committed the real mutations on its own cursor. If that later commit failed
or rolled back, the toast still said "done".

These tests call ``execute_plan_now()`` the same way every real call-site
does: bound to an ``env`` on its OWN cursor obtained via
``registry.cursor()`` (never on the outer TransactionCase's savepoint
cursor) — see ``_execute_plan_with_timeouts`` / auto-confirm /
``_retry_confirmed_not_executed`` in ``mcp_safe_operation.py``. Because these
sub-cursors do real commits against the test database (outside the test's
own rollback-on-teardown safety net), each test cleans up the rows it
creates explicitly.
"""
from unittest.mock import patch

from odoo import SUPERUSER_ID, api
from odoo.exceptions import UserError
from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestSafePlanAtomicity(TransactionCase):

    def _propose_and_confirm(self, cr, partner_name):
        """Create + confirm a one-step 'create res.partner' plan on ``cr``.

        Commits on ``cr`` so the 'confirmed' state is durable BEFORE the
        (possibly failing) mutation attempt below — exactly like a real
        pending operation confirmed in an earlier HTTP request/transaction.
        """
        env = api.Environment(cr, SUPERUSER_ID, {})
        steps = [{
            'op': 'create',
            'model': 'res.partner',
            'values': {'name': partner_name},
        }]
        op = env['ai.safe.operation'].create_verification(
            operation_type='create',
            model_name='res.partner',
            records_count=1,
            changes_info={'plan': ['create 1 res.partner'], 'danger_level': 'low'},
            user_id=SUPERUSER_ID,
            tool_name='test_safe_plan_atomicity',
            operation_data={
                'plan_steps': steps, 'title': 'atomicity test',
                'plan': ['create 1 res.partner'], 'danger_level': 'low',
            },
        )
        op.confirm_by_user(confirmed_uid=SUPERUSER_ID)
        cr.commit()
        return op.id

    def _cleanup(self, op_id, partner_name):
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            env['ai.safe.operation'].browse(op_id).unlink()
            env['res.partner'].search([('name', '=', partner_name)]).unlink()
            cr.commit()

    def test_commit_failure_keeps_executed_false_and_no_mutation(self):
        """Simulated failure of the final commit → no false 'executed'."""
        partner_name = 'pns-atomicity-fail-%s' % self.env.cr.dbname
        op_id = None
        with self.env.registry.cursor() as cr:
            op_id = self._propose_and_confirm(cr, partner_name)
            env = api.Environment(cr, SUPERUSER_ID, {})
            op = env['ai.safe.operation'].browse(op_id)
            # execute_plan_now commits twice on the caller cursor: (1) the
            # post-claim snapshot renewal (empty tx) and (2) the FINAL commit
            # that persists mutations + executed=True together in one
            # transaction. Let (1) succeed and fail (2): the plan must roll
            # back atomically — no partner AND executed=False. Every OTHER
            # cursor opened via registry.cursor() (claim/release) is untouched.
            real_commit = cr.commit
            calls = {'n': 0}

            def _fail_final_commit():
                calls['n'] += 1
                if calls['n'] == 1:
                    return real_commit()
                raise Exception('simulated commit failure')

            with patch.object(cr, 'commit', side_effect=_fail_final_commit):
                with self.assertRaises(Exception):
                    op.execute_plan_now()

        try:
            with self.env.registry.cursor() as verify_cr:
                verify_env = api.Environment(verify_cr, SUPERUSER_ID, {})
                reread = verify_env['ai.safe.operation'].browse(op_id)
                self.assertFalse(
                    reread.executed,
                    'executed must stay False when the mutation commit fails '
                    '— this is the exact "lying toast" bug (Rogelio incident)',
                )
                self.assertEqual(
                    reread.status, 'cancelled',
                    'a failed execute must revoke the Confirm so a later '
                    'code fix cannot replay the same authorization',
                )
                ghost = verify_env['res.partner'].search([('name', '=', partner_name)])
                self.assertFalse(
                    ghost,
                    'the partner must NOT exist — the mutation must have '
                    'rolled back together with the failed commit',
                )
        finally:
            self._cleanup(op_id, partner_name)

    def test_normal_execution_marks_executed_and_applies_mutation(self):
        """Sanity check: the happy path still works after the reorder."""
        partner_name = 'pns-atomicity-ok-%s' % self.env.cr.dbname
        op_id = None
        with self.env.registry.cursor() as cr:
            op_id = self._propose_and_confirm(cr, partner_name)
            env = api.Environment(cr, SUPERUSER_ID, {})
            op = env['ai.safe.operation'].browse(op_id)
            results = op.execute_plan_now()
            self.assertTrue(results, 'execute_plan_now should return the step results')

        try:
            with self.env.registry.cursor() as verify_cr:
                verify_env = api.Environment(verify_cr, SUPERUSER_ID, {})
                reread = verify_env['ai.safe.operation'].browse(op_id)
                self.assertTrue(reread.executed)
                self.assertTrue(
                    verify_env['res.partner'].search([('name', '=', partner_name)]),
                    'partner must exist after a successful execute_plan_now',
                )
        finally:
            self._cleanup(op_id, partner_name)

    def test_failed_execute_cancels_authorization_no_replay(self):
        """Invalid module.update must cancel Confirm; a later execute is a no-op."""
        op_id = None
        steps = [{
            'op': 'action',
            'action_code': 'module.update',
            'args': {'module': 'base', 'operation': 'not_a_real_op'},
        }]
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            op = env['ai.safe.operation'].create_verification(
                operation_type='action',
                model_name='ir.module.module',
                records_count=1,
                changes_info={'plan': ['module.update'], 'danger_level': 'high'},
                user_id=SUPERUSER_ID,
                tool_name='test_safe_plan_atomicity',
                operation_data={
                    'plan_steps': steps, 'title': 'cancel-on-fail',
                    'plan': ['module.update'], 'danger_level': 'high',
                },
            )
            op.confirm_by_user(confirmed_uid=SUPERUSER_ID)
            cr.commit()
            op_id = op.id
            with self.assertRaises(UserError):
                env['ai.safe.operation'].browse(op_id).execute_plan_now()

        try:
            with self.env.registry.cursor() as verify_cr:
                verify_env = api.Environment(verify_cr, SUPERUSER_ID, {})
                reread = verify_env['ai.safe.operation'].browse(op_id)
                self.assertFalse(reread.executed)
                self.assertEqual(reread.status, 'cancelled')
                replay = reread.execute_plan_now()
                self.assertIsNone(
                    replay,
                    'cancelled ops must not re-run (claim skip)',
                )
                reread = verify_env['ai.safe.operation'].browse(op_id)
                self.assertFalse(reread.executed)
                self.assertEqual(reread.status, 'cancelled')
        finally:
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                env['ai.safe.operation'].browse(op_id).unlink()
                cr.commit()
