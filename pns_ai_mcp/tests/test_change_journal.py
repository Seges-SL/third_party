# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Journal rows from execute_safe_plan; revert without Safe Plan toast."""
from odoo import SUPERUSER_ID, api
from odoo.exceptions import UserError
from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.controllers.safe_plan import execute_safe_plan


# Seges: parche de tests E0′ (datos de prueba). Ver docs/pendiente/parches_pns_ai.md
def _set_superuser_ai_writer(env):
    """execute_safe_plan exige AI Writer; el usuario 1 no lo tiene en una BD nueva.

    Solo en la transacción del test (se deshace al terminar)."""
    env.ref('pns_ai_mcp.group_ai_writer').write({
        'users': [(4, SUPERUSER_ID)],
    })


@tagged('standard', 'post_install', '-at_install', 'pns_ai_mcp')
class TestChangeJournal(TransactionCase):

    def _exec(self, steps, **ctx):
        # Seges: parche de tests E0′ (datos de prueba). Ver docs/pendiente/parches_pns_ai.md
        _set_superuser_ai_writer(self.env)
        env = api.Environment(
            self.env.cr, SUPERUSER_ID, dict(self.env.context or {}, **ctx),
        )
        return execute_safe_plan(env, steps)

    def test_create_write_sequence_and_revert(self):
        name = 'pns-journal-%s' % self.env.cr.dbname
        results = self._exec(
            [{'op': 'create', 'model': 'res.partner', 'values': {'name': name}, 'ref': 'p'}],
            ai_journal_origin='internal',
            ai_journal_note='unit create',
        )
        pid = results[0]['id']
        created = self.env['ai.change.journal'].search([
            ('model_name', '=', 'res.partner'),
            ('record_ids_display', '=', str(pid)),
            ('op', '=', 'create'),
        ])
        self.assertEqual(len(created), 1)
        self.assertEqual(created.turn_step, 1)
        self.assertTrue(created.reversible)
        self.assertTrue(created.can_revert)
        self.assertIn('"schema_version": 1', created.after_json or '')

        self._exec(
            [{'op': 'write', 'model': 'res.partner', 'ids': [pid], 'values': {'name': name + '-b'}}],
            ai_journal_origin='internal',
        )
        written = self.env['ai.change.journal'].search([
            ('record_ids_display', '=', str(pid)),
            ('op', '=', 'write'),
        ])
        self.assertEqual(len(written), 1)
        self.assertEqual(self.env['res.partner'].browse(pid).name, name + '-b')

        written.action_revert()
        self.assertEqual(self.env['res.partner'].browse(pid).name, name)
        self.assertEqual(written.state, 'reverted')
        undo = self.env['ai.change.journal'].search([('reverts_id', '=', written.id)])
        self.assertEqual(len(undo), 1)
        self.assertFalse(undo.can_revert)
        with self.assertRaises(UserError):
            undo.action_revert()

        self.env['ai.change.journal'].browse(created.id).action_revert()
        self.assertFalse(self.env['res.partner'].browse(pid).exists())

    def test_unlink_archives_then_revert_and_empty_trash(self):
        name = 'pns-journal-trash-%s' % self.env.cr.dbname
        partner = self.env['res.partner'].create({'name': name})
        pid = partner.id
        self._exec(
            [{'op': 'unlink', 'model': 'res.partner', 'ids': [pid]}],
            ai_journal_origin='internal',
        )
        archived = self.env['res.partner'].with_context(active_test=False).browse(pid)
        self.assertTrue(archived.exists())
        self.assertFalse(archived.active)
        row = self.env['ai.change.journal'].search([
            ('op', '=', 'unlink'),
            ('record_ids_display', '=', str(pid)),
        ], limit=1)
        self.assertTrue(row.reversible)
        self.assertTrue(row.can_revert)
        row.action_revert()
        live = self.env['res.partner'].browse(pid)
        self.assertTrue(live.exists())
        self.assertTrue(live.active)
        self._exec(
            [{'op': 'unlink', 'model': 'res.partner', 'ids': [pid]}],
            ai_journal_origin='internal',
        )
        again = self.env['ai.change.journal'].search([
            ('op', '=', 'unlink'),
            ('record_ids_display', '=', str(pid)),
            ('state', '=', 'applied'),
            ('reversible', '=', True),
        ], limit=1)
        again.action_empty_one()
        self.assertFalse(
            self.env['res.partner'].with_context(active_test=False).browse(pid).exists()
        )
        self.assertFalse(again.reversible)

    def test_cancelled_safe_plan_does_not_journal(self):
        before = self.env['ai.change.journal'].search_count([])
        op = self.env['ai.safe.operation'].create_verification(
            operation_type='create',
            model_name='res.partner',
            records_count=1,
            changes_info={'plan': ['create'], 'danger_level': 'low'},
            user_id=self.env.uid,
            tool_name='test_change_journal',
            operation_data={
                'plan_steps': [{
                    'op': 'create', 'model': 'res.partner',
                    'values': {'name': 'pns-journal-cancel'},
                }],
                'title': 'cancel test',
                'plan': ['create'],
                'danger_level': 'low',
            },
        )
        op.action_cancel()
        self.assertEqual(self.env['ai.change.journal'].search_count([]), before)

    def test_failed_execute_journals_outside_rollback(self):
        field = self.env['ir.model.fields'].search([
            ('model', '=', 'res.partner'),
            ('name', '=', 'name'),
        ], limit=1)
        self.assertTrue(field)
        steps = [{
            'op': 'write',
            'model': 'ir.model.fields',
            'ids': [field.id],
            'values': {'required': True},
        }]
        op_id = None
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            op = env['ai.safe.operation'].create_verification(
                operation_type='write',
                model_name='ir.model.fields',
                records_count=1,
                changes_info={'plan': ['write field'], 'danger_level': 'medium'},
                user_id=SUPERUSER_ID,
                tool_name='test_change_journal',
                operation_data={
                    'plan_steps': steps, 'title': 'fail journal',
                    'plan': ['write field'], 'danger_level': 'medium',
                    'log_origin': 'internal',
                },
                turn='FAILTEST',
            )
            op._confirm_by_user()
            cr.commit()
            op_id = op.id
            try:
                env['ai.safe.operation'].browse(op_id).execute_plan_now()
            except Exception:
                pass
        failed = self.env['ai.change.journal'].search([
            ('turn', '=', 'FAILTEST'),
            ('state', '=', 'failed'),
        ])
        self.assertTrue(failed)
        self.assertIn('base fields', (failed[0].note or '').lower() + (failed[0].after_json or '').lower())
        failed.sudo().unlink()
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            env['ai.safe.operation'].browse(op_id).unlink()
            cr.commit()
