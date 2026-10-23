# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 12 (tests de la entrega E1′, adaptado a 3.1.879). Ver docs/pendiente/parches_pns_ai.md
"""Parche 12 (PNS-01/02), adaptado a 3.1.879: dar o quitar cualquier grupo con
un plan exige base.group_system, por la acción de confianza y por CRUD en
res.groups. La cúspide del fabricante se mantiene: nadie la da con un plan.

Portado de la rama 14.0-pns-ai-correcciones (entrega E2) y reescrito con un
grupo que no es cúspide (docs/specs/comparacion_pns_ai_3-1-879.md, §4.1, P-01).
"""

from odoo import api
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from odoo.addons.pns_ai_mcp.controllers.safe_plan import (
    execute_safe_plan,
    validate_safe_plan,
)

GROUP = 'base.group_partner_manager'
SETTINGS_ONLY = 'Only a Settings administrator'


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e1p')
class TestSegesUserGroupActions(TransactionCase):

    def setUp(self):
        super().setUp()
        self.adm = new_test_user(
            self.env, login='seges_e1p_adm',
            groups='base.group_user,pns_ai_mcp.group_ai_admin',
        )
        self.sys_adm = new_test_user(
            self.env, login='seges_e1p_sys',
            groups='base.group_user,base.group_system,pns_ai_mcp.group_ai_admin',
        )
        self.target = new_test_user(
            self.env, login='seges_e1p_target', groups='base.group_user',
        )
        self.target_grp = new_test_user(
            self.env, login='seges_e1p_target_grp',
            groups='base.group_user,' + GROUP,
        )
        self.env_adm = api.Environment(self.env.cr, self.adm.id, {})
        self.env_sys = api.Environment(self.env.cr, self.sys_adm.id, {})

    def _step(self, code, user, group=GROUP):
        return {
            'op': 'action', 'action_code': code,
            'args': {'user_id': user.id, 'group': group},
        }

    def test_propose_rejected_without_settings(self):
        for step in (
            self._step('user.add_group', self.adm),
            self._step('user.remove_group', self.target_grp),
        ):
            ok, err = validate_safe_plan([step], self.env_adm)
            self.assertFalse(ok)
            self.assertIn(SETTINGS_ONLY, err or '')

    def test_confirmed_add_group_rejected_without_settings(self):
        with self.assertRaises(UserError):
            execute_safe_plan(self.env_adm, [
                self._step('user.add_group', self.adm)])
        self.assertFalse(self.adm.has_group(GROUP))

    def test_confirmed_remove_group_rejected_without_settings(self):
        with self.assertRaises(UserError):
            execute_safe_plan(self.env_adm, [
                self._step('user.remove_group', self.target_grp)])
        self.assertTrue(self.target_grp.has_group(GROUP))

    def test_registry_edit_does_not_lift_check(self):
        action = self.env_adm['ai.trusted.action']._get('user.add_group')
        action.write({'group_ids': [(5, 0, 0)]})
        with self.assertRaises(UserError):
            action._apply(user_id=self.adm.id, group=GROUP)
        self.assertFalse(self.adm.has_group(GROUP))

    def test_direct_methods_rejected_without_settings(self):
        kwargs = {'user_id': self.adm.id, 'group': GROUP}
        for model in (self.env_adm['ai.system.action'],
                      self.env_adm['ai.system.action'].sudo()):
            for name in ('_preview_user_add_group', '_apply_user_add_group',
                         '_preview_user_remove_group', '_apply_user_remove_group'):
                with self.assertRaises(UserError, msg=name):
                    getattr(model, name)(**kwargs)
        self.assertFalse(self.adm.has_group(GROUP))

    def test_settings_admin_adds_and_removes(self):
        add = self._step('user.add_group', self.target)
        remove = self._step('user.remove_group', self.target)
        ok, err = validate_safe_plan([add], self.env_sys)
        self.assertTrue(ok, err)
        rows = execute_safe_plan(self.env_sys, [add])
        self.assertEqual(rows[0]['op'], 'action')
        self.assertTrue(rows[0]['result']['ok'])
        self.assertTrue(self.target.has_group(GROUP))
        rows = execute_safe_plan(self.env_sys, [remove])
        self.assertTrue(rows[0]['result']['ok'])
        self.assertFalse(self.target.has_group(GROUP))

    def test_settings_admin_refused_on_cusp(self):
        # Criterio del fabricante, que se mantiene: la cúspide no se da con un plan.
        step = self._step('user.add_group', self.target, 'base.group_system')
        ok, err = validate_safe_plan([step], self.env_sys)
        self.assertFalse(ok)
        self.assertIn('maximum-privilege', err or '')
        with self.assertRaises(UserError):
            execute_safe_plan(self.env_sys, [step])
        self.assertFalse(self.target.has_group('base.group_system'))

    def test_context_identities_checked(self):
        # Una operación supervisada pone en el contexto quién la propuso y
        # quién la confirmó: los dos necesitan Ajustes, aunque ejecute otro.
        step = self._step('user.add_group', self.target)
        for key in ('ai_journal_user_id', 'ai_journal_confirmed_by_uid'):
            env = self.env_sys(context={key: self.adm.id})
            with self.assertRaises(UserError, msg=key):
                execute_safe_plan(env, [dict(step)])
        self.assertFalse(self.target.has_group(GROUP))
        env = self.env_sys(context={
            'ai_journal_user_id': self.sys_adm.id,
            'ai_journal_confirmed_by_uid': self.sys_adm.id,
        })
        execute_safe_plan(env, [dict(step)])
        self.assertTrue(self.target.has_group(GROUP))

    def test_view_actions_unchanged_for_ai_admin(self):
        view = self.env['ir.ui.view'].create({
            'name': 'seges.e1p.user.groups.form',
            'model': 'res.partner',
            'type': 'form',
            'arch': (
                '<?xml version="1.0"?>'
                '<form><sheet><field name="name"/><field name="comment"/>'
                '</sheet></form>'
            ),
        })
        action = self.env_adm['ai.trusted.action']._get('view.set_field_readonly')
        result = action._apply(
            model='res.partner', field='comment', readonly=True,
            view_ids=[view.id])
        self.assertTrue(result.get('ok'))
        self.assertTrue(result.get('ids'))


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e1p')
class TestSegesUserGroupCrud(TransactionCase):
    """Vía CRUD: escribir en res.groups también exige Ajustes."""

    def setUp(self):
        super().setUp()
        self.access_adm = new_test_user(
            self.env, login='seges_e1p_access',
            groups=('base.group_user,base.group_erp_manager,'
                    'pns_ai_mcp.group_ai_admin,pns_ai_mcp.group_ai_writer'),
        )
        self.sys_adm = new_test_user(
            self.env, login='seges_e1p_crud_sys',
            groups=('base.group_user,base.group_system,'
                    'pns_ai_mcp.group_ai_admin,pns_ai_mcp.group_ai_writer'),
        )
        self.target = new_test_user(
            self.env, login='seges_e1p_crud_target', groups='base.group_user',
        )
        self.group = self.env.ref(GROUP)

    def _step(self):
        return {
            'op': 'write', 'model': 'res.groups', 'ids': [self.group.id],
            'values': {'users': [[4, self.target.id]]},
        }

    def test_crud_res_groups_refused_without_settings(self):
        self.assertFalse(self.access_adm.has_group('base.group_system'))
        env = api.Environment(self.env.cr, self.access_adm.id, {})
        ok, err = validate_safe_plan([self._step()], env)
        self.assertFalse(ok)
        self.assertIn(SETTINGS_ONLY, err or '')
        with self.assertRaises(PermissionError):
            execute_safe_plan(env, [self._step()])
        self.assertFalse(self.target.has_group(GROUP))

    def test_crud_res_groups_settings_ok(self):
        env = api.Environment(self.env.cr, self.sys_adm.id, {})
        ok, err = validate_safe_plan([self._step()], env)
        self.assertTrue(ok, err)
        execute_safe_plan(env, [self._step()])
        self.assertTrue(self.target.has_group(GROUP))
