# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 17 (tests de la entrega E2′). Ver docs/pendiente/parches_pns_ai.md
"""Parche 17 (PNS-37): el diario solo lo escribe el sistema y el paso ``unlink``
de un plan exige permiso de borrado antes de archivar.

Sin el parche, un AI Administrator sin Ajustes reescribe por RPC una fila
antigua como borrado en papelera y el cron la vacía como superusuario; y un
plan de borrado sobre un modelo archivable solo exige escritura.

Además, un test de no regresión por cada vía que escribe en el diario
(inventario de docs/pendiente/e2_propuesta_3879.md, «PNS-37 (decisiones 1 y 2)»).
Las filas que se escriben en un cursor propio (vías 3 y 4) van en
``TestSegesFailedPlanRow``, sin ``enter_test_mode`` ni ``HttpCase``.
"""

import uuid

from odoo import SUPERUSER_ID, api
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from odoo.addons.pns_ai_mcp.controllers.safe_plan import execute_safe_plan

REFUSED = 'Only the system can write the AI change journal'
QUARANTINE_JSON = '{"ids": [%d], "meta": {"quarantine": true}}'


class _SegesJournalCase(TransactionCase):

    def setUp(self):
        super().setUp()
        self.aa = new_test_user(
            self.env, login='seges_e2p_37_aa',
            groups='base.group_user,base.group_partner_manager,'
                   'pns_ai_mcp.group_ai_admin',
        )
        self.Journal = self.env['ai.change.journal']

    def _plan(self, user, steps):
        env = api.Environment(
            self.env.cr, user.id, {'ai_journal_origin': 'internal'})
        return execute_safe_plan(env, steps)

    def _rows(self, op, record_id):
        return self.Journal.search([
            ('op', '=', op), ('record_ids_display', '=', str(record_id)),
        ])

    def _category(self, name):
        return self.env['res.partner.category'].create({'name': name})


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesChangeJournal(_SegesJournalCase):

    # Vía 12: por RPC (call_kw usa el ORM con el usuario, sin su).

    def test_ai_admin_write_refused(self):
        cat = self._category('seges-e2p-37-w')
        row = self.Journal.sudo().create({
            'op': 'write', 'model_name': 'res.partner.category',
            'record_ids_display': str(cat.id),
        })
        with self.assertRaisesRegex(AccessError, REFUSED):
            row.with_user(self.aa).write({
                'op': 'unlink', 'state': 'applied', 'reversible': True,
                'after_json': QUARANTINE_JSON % cat.id,
            })
        row.invalidate_cache()
        self.assertEqual(row.op, 'write')
        self.assertFalse(row.reversible)

    def test_ai_admin_create_refused(self):
        cat = self._category('seges-e2p-37-c')
        before = self.Journal.search_count([])
        with self.assertRaisesRegex(AccessError, REFUSED):
            self.Journal.with_user(self.aa).create({
                'op': 'unlink', 'state': 'applied', 'reversible': True,
                'model_name': 'res.partner.category',
                'after_json': QUARANTINE_JSON % cat.id,
            })
        self.assertEqual(self.Journal.search_count([]), before)

    def test_plan_unlink_requires_unlink_right(self):
        group = self.env['res.groups'].create({'name': 'Seges E2p category writer'})
        self.env['ir.model.access'].create({
            'name': 'seges e2p category writer',
            'model_id': self.env.ref('base.model_res_partner_category').id,
            'group_id': group.id,
            'perm_read': True, 'perm_write': True,
            'perm_create': False, 'perm_unlink': False,
        })
        writer = new_test_user(
            self.env, login='seges_e2p_37_w',
            groups='base.group_user,pns_ai_mcp.group_ai_writer',
        )
        writer.groups_id = [(4, group.id)]
        cat = self._category('seges-e2p-37-u')
        with self.assertRaisesRegex(
                AccessError, r'not allowed to delete .*\(res\.partner\.category\)'):
            self._plan(writer, [{
                'op': 'unlink', 'model': 'res.partner.category', 'ids': [cat.id],
            }])
        cat.invalidate_cache()
        self.assertTrue(cat.active)
        self.assertFalse(self._rows('unlink', cat.id))

    # Vía 1: ejecución correcta, con un AI Writer (sin su).

    def test_applied_row_as_ai_writer(self):
        writer = new_test_user(
            self.env, login='seges_e2p_37_aw',
            groups='base.group_user,base.group_partner_manager,'
                   'pns_ai_mcp.group_ai_writer',
        )
        res = self._plan(writer, [{
            'op': 'create', 'model': 'res.partner',
            'values': {'name': 'seges-e2p-37-p'}, 'ref': 'p',
        }])
        pid = res[0]['id']
        self._plan(writer, [{
            'op': 'write', 'model': 'res.partner', 'ids': [pid],
            'values': {'name': 'seges-e2p-37-p2'},
        }])
        for op in ('create', 'write'):
            row = self._rows(op, pid)
            self.assertEqual(len(row), 1, op)
            self.assertEqual(row.state, 'applied', op)

    # Vía 2: tras recargar el registro (misma llamada que safe_operation.py:1611).

    def test_heal_shape_creates_row(self):
        turn = 'SEGESE2P37H'
        jenv = api.Environment(
            self.env.cr, SUPERUSER_ID, {'ai_journal_turn': turn})
        mod = self.env.ref('base.module_base')
        result = {'op': 'action', 'action_code': 'module.update', 'result': {
            'state': mod.state,
            'change_journal': {
                'model': 'ir.module.module', 'ids': [mod.id],
                'change_kind': 'module', 'reversible': False,
                'reversible_reason': 'module install/upgrade/uninstall',
            },
        }}
        jenv['ai.change.journal'].sudo().record_executed_step(
            jenv, {'op': 'action', 'action_code': 'module.update'}, 'action',
            result, None, 1,
        )
        rows = self.Journal.search([('turn', '=', turn)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.action_code, 'module.update')

    # Vía 6: revertir (el write de la fila pasa a sudo).

    def test_revert_still_works_for_ai_admin(self):
        cat = self._category('seges-e2p-37-r')
        self._plan(self.aa, [{
            'op': 'write', 'model': 'res.partner.category', 'ids': [cat.id],
            'values': {'name': 'seges-e2p-37-r2'},
        }])
        row = self._rows('write', cat.id)
        self.assertEqual(len(row), 1)
        row.with_user(self.aa).action_revert()
        cat.invalidate_cache()
        row.invalidate_cache()
        self.assertEqual(cat.name, 'seges-e2p-37-r')
        self.assertEqual(row.state, 'reverted')
        self.assertTrue(self.Journal.search([('reverts_id', '=', row.id)]))

    # Vía 7: vaciar la papelera a mano (el write de la fila pasa a sudo).

    def test_empty_one_and_settings_still_work_for_ai_admin(self):
        cat_one = self._category('seges-e2p-37-e1')
        cat_all = self._category('seges-e2p-37-e2')
        Category = self.env['res.partner.category'].with_context(active_test=False)
        self._plan(self.aa, [{
            'op': 'unlink', 'model': 'res.partner.category', 'ids': [cat_one.id],
        }])
        row = self._rows('unlink', cat_one.id)
        self.assertTrue(row._is_quarantine())
        row.with_user(self.aa).action_empty_one()
        self.assertFalse(Category.browse(cat_one.id).exists())
        row.invalidate_cache()
        self.assertFalse(row.reversible)
        # Desde Ajustes: lo usa quien tiene Ajustes (res.config.settings).
        sysadm = new_test_user(
            self.env, login='seges_e2p_37_sys',
            groups='base.group_user,base.group_system,'
                   'base.group_partner_manager,pns_ai_mcp.group_ai_admin',
        )
        self._plan(sysadm, [{
            'op': 'unlink', 'model': 'res.partner.category', 'ids': [cat_all.id],
        }])
        self.env['res.config.settings'].with_user(sysadm).create(
            {}).action_empty_journal_trash()
        self.assertFalse(Category.browse(cat_all.id).exists())
        self.assertFalse(self._rows('unlink', cat_all.id).reversible)

    # Vía 8: el cron, como superusuario, con una fila legítima antigua.

    def test_cron_empties_old_row(self):
        cat = self._category('seges-e2p-37-cron')
        self._plan(self.aa, [{
            'op': 'unlink', 'model': 'res.partner.category', 'ids': [cat.id],
        }])
        row = self._rows('unlink', cat.id)
        self.env['base'].flush()
        self.env.cr.execute(
            "UPDATE ai_change_journal SET create_date = now() - interval '400 days' "
            "WHERE id = %s", (row.id,))
        self.Journal.invalidate_cache()
        cron_env = api.Environment(self.env.cr, SUPERUSER_ID, {})
        self.assertGreaterEqual(
            cron_env['ai.change.journal']._cron_empty_journal_trash(), 1)
        self.assertFalse(
            self.env['res.partner.category'].with_context(
                active_test=False).browse(cat.id).exists())
        row.invalidate_cache()
        self.assertFalse(row.reversible)

    # Vía 9: el related almacenado verification_id se recalcula sin write.

    def test_related_verification_id_recompute(self):
        op = self.env['ai.safe.operation'].create_verification(
            operation_type='write', model_name='res.partner', records_count=1,
            changes_info={'plan': ['write partner'], 'danger_level': 'medium'},
            user_id=self.aa.id, tool_name='seges_e2p_37',
            operation_data={
                'plan_steps': [], 'title': 'seges e2p 37',
                'plan': ['write partner'], 'danger_level': 'medium',
            },
        )
        row = self.Journal.sudo().create({'op': 'write', 'safe_operation_id': op.id})
        op.sudo().write({'verification_id': 'SEGESE2P37V'})
        self.env['base'].flush()
        row.invalidate_cache()
        self.assertEqual(row.verification_id, 'SEGESE2P37V')


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesFailedPlanRow(_SegesJournalCase):
    """Vías 3 y 4: la fila ``failed`` se escribe en un cursor propio y sobrevive
    al rollback del plan. ``base.user_admin`` existe para ese cursor; un usuario
    creado en el test, no (clave foránea de ``user_id``)."""

    def setUp(self):
        super().setUp()
        self.admin = self.env.ref('base.user_admin')
        self.turn = f'SEGESE2P37F{uuid.uuid4().hex[:8].upper()}'
        self.addCleanup(self._purge)

    def _committed_failed(self):
        with self.env.registry.cursor() as cr:
            cr.execute(
                "SELECT count(*) FROM ai_change_journal "
                "WHERE turn = %s AND state = 'failed'", (self.turn,))
            return cr.fetchone()[0]

    def _purge(self):
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            env['ai.change.journal'].search([('turn', '=', self.turn)]).unlink()
            # La fila está confirmada en otra transacción: se borra igual.
            cr.commit()  # pylint: disable=invalid-commit

    def _journal_ctx(self):
        return {
            'ai_journal_turn': self.turn,
            'ai_journal_user_id': self.admin.id,
            'ai_journal_confirmed_by_uid': self.admin.id,
        }

    def test_failed_plan_row_survives_rollback(self):
        steps = [{
            'op': 'write', 'model': 'res.partner', 'ids': [self.admin.partner_id.id],
            'values': {'comment': 'seges-e2p-37-f'},
        }]
        env_admin = self.env(user=self.admin, context=self._journal_ctx())
        self.assertFalse(env_admin.su)
        env_admin['ai.change.journal']._record_failed_plan(
            steps, 'seges e2p 37 failed', env=env_admin)
        self.env.cr.rollback()
        self.assertEqual(self._committed_failed(), 1)

    def test_rejected_plan_journals_failed_row(self):
        group = self.env['res.groups'].create({'name': 'Seges E2p category writer'})
        self.env['ir.model.access'].create({
            'name': 'seges e2p category writer',
            'model_id': self.env.ref('base.model_res_partner_category').id,
            'group_id': group.id,
            'perm_read': True, 'perm_write': True,
            'perm_create': False, 'perm_unlink': False,
        })
        writer = new_test_user(
            self.env, login='seges_e2p_37_fw',
            groups='base.group_user,pns_ai_mcp.group_ai_writer',
        )
        writer.groups_id = [(4, group.id)]
        cat = self._category('seges-e2p-37-fr')
        steps = [{'op': 'unlink', 'model': 'res.partner.category', 'ids': [cat.id]}]
        exec_env = api.Environment(
            self.env.cr, writer.id,
            dict(self._journal_ctx(), ai_journal_origin='internal'))
        with self.assertRaises(AccessError) as caught:
            execute_safe_plan(exec_env, steps)
        # Como safe_operation.py:1516, en el except de execute_plan_now.
        self.env['ai.change.journal'].sudo()._record_failed_plan(
            steps, str(caught.exception), env=exec_env)
        self.assertEqual(self._committed_failed(), 1)
