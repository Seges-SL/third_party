# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 12 (tests de la entrega E2). Ver docs/pendiente/parches_pns_ai.md
"""Parche 12 (PNS-01/02): dar o quitar grupos nativos con un plan exige
base.group_system además de AI Administrator, sobre el usuario real."""

from odoo import api
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from odoo.addons.pns_ai_mcp.controllers.safe_plan import (
    execute_safe_plan,
    validate_safe_plan,
)


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2')
class TestSegesUserGroupActions(TransactionCase):

    def setUp(self):
        super().setUp()
        self.adm = new_test_user(
            self.env, login='seges_e2_adm',
            groups='base.group_user,pns_ai_mcp.group_ai_admin',
        )
        self.sys_adm = new_test_user(
            self.env, login='seges_e2_sys',
            groups='base.group_user,base.group_system,pns_ai_mcp.group_ai_admin',
        )
        self.target = new_test_user(
            self.env, login='seges_e2_target', groups='base.group_user',
        )
        self.target_sys = new_test_user(
            self.env, login='seges_e2_target_sys',
            groups='base.group_user,base.group_system',
        )
        self.env_adm = api.Environment(self.env.cr, self.adm.id, {})
        self.env_sys = api.Environment(self.env.cr, self.sys_adm.id, {})

    def _step(self, code, user, group):
        return {
            'op': 'action', 'action_code': code,
            'args': {'user_id': user.id, 'group': group},
        }

    def test_propose_rejected_without_settings(self):
        for step in (
            self._step('user.add_group', self.adm, 'base.group_system'),
            self._step('user.remove_group', self.target_sys, 'base.group_system'),
        ):
            ok, err = validate_safe_plan([step], self.env_adm)
            self.assertFalse(ok)
            self.assertIn('Only a Settings administrator', err or '')

    def test_confirmed_add_group_rejected_without_settings(self):
        with self.assertRaises(UserError):
            execute_safe_plan(self.env_adm, [
                self._step('user.add_group', self.adm, 'base.group_system')])
        self.assertFalse(self.adm.has_group('base.group_system'))

    def test_confirmed_remove_group_rejected_without_settings(self):
        with self.assertRaises(UserError):
            execute_safe_plan(self.env_adm, [
                self._step('user.remove_group', self.target_sys,
                           'base.group_system')])
        self.assertTrue(self.target_sys.has_group('base.group_system'))

    def test_registry_edit_does_not_lift_check(self):
        action = self.env_adm['ai.trusted.action']._get('user.add_group')
        action.write({'group_ids': [(5, 0, 0)]})
        with self.assertRaises(UserError):
            action._apply(user_id=self.adm.id, group='base.group_system')
        self.assertFalse(self.adm.has_group('base.group_system'))

    def test_direct_methods_rejected_without_settings(self):
        kwargs = {'user_id': self.adm.id, 'group': 'base.group_system'}
        for model in (self.env_adm['ai.system.action'],
                      self.env_adm['ai.system.action'].sudo()):
            for name in ('_preview_user_add_group', '_apply_user_add_group',
                         '_preview_user_remove_group', '_apply_user_remove_group'):
                with self.assertRaises(UserError, msg=name):
                    getattr(model, name)(**kwargs)

    def test_settings_admin_adds_and_removes(self):
        add = self._step('user.add_group', self.target, 'base.group_system')
        remove = self._step('user.remove_group', self.target, 'base.group_system')
        ok, err = validate_safe_plan([add], self.env_sys)
        self.assertTrue(ok, err)
        rows = execute_safe_plan(self.env_sys, [add])
        self.assertEqual(rows[0]['op'], 'action')
        self.assertTrue(rows[0]['result']['ok'])
        self.assertTrue(self.target.has_group('base.group_system'))
        rows = execute_safe_plan(self.env_sys, [remove])
        self.assertTrue(rows[0]['result']['ok'])
        self.assertFalse(self.target.has_group('base.group_system'))

    def test_view_actions_unchanged_for_ai_admin(self):
        view = self.env['ir.ui.view'].create({
            'name': 'seges.e2.user.groups.form',
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
