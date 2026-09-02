# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Trusted system actions: view modifiers, propose group gate, reset."""
from odoo import SUPERUSER_ID, api
from odoo.exceptions import UserError
from odoo.tests import tagged, TransactionCase
from odoo.tests.common import new_test_user

from odoo.addons.pns_ai_mcp.controllers.safe_plan import (
    create_pending_safe_operation,
    execute_safe_plan,
    validate_safe_plan,
)
from odoo.addons.pns_ai_mcp.utils.field_required_plan import accept_choice


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestSystemTrustedActions(TransactionCase):

    def _form(self, field_name='comment'):
        return self.env['ir.ui.view'].create({
            'name': 'pns.test.system.action.form',
            'model': 'res.partner',
            'type': 'form',
            'arch': (
                '<?xml version="1.0"?>'
                '<form><sheet>'
                '<field name="name"/>'
                '<field name="%s"/>'
                '</sheet></form>'
            ) % field_name,
        })

    def test_required_inherit_and_reset(self):
        view = self._form()
        Action = self.env['ai.system.action']
        preview = Action.preview_view_set_field_required(
            model='res.partner', field='comment', required=True,
            view_ids=[view.id],
        )
        self.assertIn('comment', preview)
        result = Action.apply_view_set_field_required(
            model='res.partner', field='comment', required=True,
            view_ids=[view.id],
        )
        self.assertTrue(result.get('ok'))
        inherit_ids = result.get('ids') or []
        self.assertEqual(len(inherit_ids), 1)
        inherit = self.env['ir.ui.view'].browse(inherit_ids[0])
        self.assertTrue(inherit.exists())
        self.assertIn('required">1', inherit.arch or '')
        policy = self.env['ai.view.policy'].search([
            ('model_name', '=', 'res.partner'),
            ('field_name', '=', 'comment'),
            ('view_id', '=', view.id),
        ])
        self.assertEqual(len(policy), 1)

        Action.apply_view_reset_field_modifiers(
            model='res.partner', field='comment',
        )
        self.assertFalse(inherit.exists())
        self.assertFalse(self.env['ai.view.policy'].search([
            ('model_name', '=', 'res.partner'),
            ('field_name', '=', 'comment'),
            ('view_id', '=', view.id),
        ]))

    def test_unknown_field_rejected(self):
        with self.assertRaises(UserError):
            self.env['ai.system.action'].preview_view_set_field_required(
                model='res.partner',
                field='no_such_pns_field_xyz',
                required=True,
            )

    def test_view_without_field_rejected(self):
        view = self._form('name')
        with self.assertRaises(UserError):
            self.env['ai.system.action'].apply_view_set_field_required(
                model='res.partner', field='comment', required=True,
                view_ids=[view.id],
            )

    def test_propose_rejects_view_without_field(self):
        """Propose lists views later; execute still fails if the view hides the field."""
        admin = new_test_user(
            self.env, login='pns_aiadmin_noview',
            groups='base.group_user,pns_ai_mcp.group_ai_admin',
        )
        view = self._form('name')
        env_a = api.Environment(self.env.cr, admin.id, {})
        ok, err = validate_safe_plan([{
            'op': 'field_required',
            'model': 'res.partner',
            'field': 'comment',
            'required': True,
            'view_ids': [view.id],
        }], env_a)
        self.assertTrue(ok, err)
        with self.assertRaises(UserError):
            execute_safe_plan(env_a, [{
                'op': 'field_required',
                'model': 'res.partner',
                'field': 'comment',
                'required': True,
                'view_only': True,
                'view_ids': [view.id],
            }])

    def test_view_id_alias_and_extension_inherit(self):
        Action = self.env['ai.system.action']
        parent = self._form('name')
        Model = self.env['ir.model'].search(
            [('model', '=', 'res.partner')], limit=1,
        )
        self.env['ir.model.fields'].create({
            'name': 'x_pns_test_alias',
            'field_description': 'PNS test alias',
            'model_id': Model.id,
            'ttype': 'char',
            'state': 'manual',
        })
        inherit = self.env['ir.ui.view'].create({
            'name': 'pns.test.alias.inherit',
            'model': 'res.partner',
            'type': 'form',
            'inherit_id': parent.id,
            'arch': (
                '<?xml version="1.0"?>'
                '<xpath expr="//field[@name=\'name\']" position="after">'
                '<field name="x_pns_test_alias"/>'
                '</xpath>'
            ),
        })
        preview = Action.preview_view_set_field_required(
            model='res.partner', field='x_pns_test_alias',
            required=True, view_id=inherit.id,
        )
        self.assertIn('x_pns_test_alias', preview)
        preview_empty = Action.preview_view_set_field_required(
            model='res.partner', field='x_pns_test_alias', required=True,
        )
        self.assertIn('x_pns_test_alias', preview_empty)

    def test_empty_view_ids_prefers_form_not_tree(self):
        Model = self.env['ir.model'].search(
            [('model', '=', 'res.partner')], limit=1,
        )
        self.env['ir.model.fields'].create({
            'name': 'x_pns_test_req_only',
            'field_description': 'PNS test required only',
            'model_id': Model.id,
            'ttype': 'char',
            'state': 'manual',
        })
        form = self._form('x_pns_test_req_only')
        tree = self.env['ir.ui.view'].create({
            'name': 'pns.test.system.action.tree',
            'model': 'res.partner',
            'type': 'tree',
            'arch': (
                '<?xml version="1.0"?>'
                '<tree><field name="name"/>'
                '<field name="x_pns_test_req_only"/></tree>'
            ),
        })
        Action = self.env['ai.system.action']
        preview = Action.preview_view_set_field_required(
            model='res.partner', field='x_pns_test_req_only', required=True,
        )
        self.assertIn('1 view', preview)
        result = Action.apply_view_set_field_required(
            model='res.partner', field='x_pns_test_req_only', required=True,
        )
        inherit_ids = result.get('ids') or []
        self.assertEqual(len(inherit_ids), 1)
        inherit = self.env['ir.ui.view'].browse(inherit_ids[0])
        self.assertEqual(inherit.inherit_id.id, form.id)
        self.assertNotEqual(inherit.inherit_id.id, tree.id)
        tree_preview = Action.preview_view_set_field_required(
            model='res.partner', field='x_pns_test_req_only', required=True,
            view_type='tree',
        )
        self.assertIn('1 view', tree_preview)

    def test_required_arch_skips_read_only_copies(self):
        view = self.env['ir.ui.view'].create({
            'name': 'pns.test.alias.copies.form',
            'model': 'res.partner',
            'type': 'form',
            'arch': (
                '<?xml version="1.0"?>'
                '<form><sheet>'
                '<div class="oe_read_only"><field name="comment"/></div>'
                '<div class="oe_edit_only"><field name="comment"/></div>'
                '</sheet></form>'
            ),
        })
        result = self.env['ai.system.action'].apply_view_set_field_required(
            model='res.partner', field='comment', required=True,
            view_ids=[view.id],
        )
        inherit = self.env['ir.ui.view'].browse(result['ids'][0])
        self.assertIn("not(ancestor::*[hasclass('oe_read_only')])", inherit.arch)
        self.assertIn("not(@invisible='1')", inherit.arch)

    def test_propose_rejects_view_and_field_crud(self):
        admin = new_test_user(
            self.env, login='pns_aiadmin_noviewcrud',
            groups='base.group_user,pns_ai_mcp.group_ai_admin',
        )
        env_a = api.Environment(self.env.cr, admin.id, {})
        ok, err = validate_safe_plan([{
            'op': 'write',
            'model': 'ir.ui.view',
            'ids': [1],
            'values': {'arch': '<data/>'},
        }], env_a)
        self.assertFalse(ok)
        self.assertIn('field_required', (err or ''))
        ok_f, err_f = validate_safe_plan([{
            'op': 'write',
            'model': 'ir.model.fields',
            'ids': [1],
            'values': {'required': True},
        }], env_a)
        self.assertFalse(ok_f)
        self.assertIn('ir.model.fields', (err_f or ''))

    def test_propose_without_ai_admin_fails(self):
        writer = new_test_user(
            self.env, login='pns_writer_sysact',
            groups='base.group_user,pns_ai_mcp.group_ai_writer',
        )
        env_w = api.Environment(self.env.cr, writer.id, {})
        ok, err = validate_safe_plan([{
            'op': 'field_required',
            'model': 'res.partner',
            'field': 'comment',
            'required': True,
        }], env_w)
        self.assertFalse(ok)
        self.assertIn('Administrator', (err or ''))

    def test_apply_via_safe_plan_as_admin(self):
        admin = new_test_user(
            self.env, login='pns_aiadmin_sysact',
            groups='base.group_user,pns_ai_mcp.group_ai_admin',
        )
        view = self._form()
        env_a = api.Environment(self.env.cr, admin.id, {})
        ok, err = validate_safe_plan([{
            'op': 'field_required',
            'model': 'res.partner',
            'field': 'comment',
            'required': True,
            'view_ids': [view.id],
        }], env_a)
        self.assertTrue(ok, err)
        rows = execute_safe_plan(env_a, [{
            'op': 'field_required',
            'model': 'res.partner',
            'field': 'comment',
            'required': True,
            'view_ids': [view.id],
        }])
        inherit_id = rows[0]['views']['ids'][0]
        inherit = self.env['ir.ui.view'].browse(inherit_id)
        self.assertTrue(inherit.exists())
        self.assertIn('required">1', inherit.arch or '')
        self.assertNotIn("oe_read_only", inherit.arch)

    def test_module_preview_no_apply(self):
        text = self.env['ai.system.action'].preview_module_update(
            module='base', operation='upgrade',
        )
        self.assertIn('base', text.lower())
        with self.assertRaises(UserError):
            self.env['ai.system.action'].preview_module_update(
                module='base', operation='uninstall',
            )
        with self.assertRaises(UserError):
            self.env['ai.system.action'].preview_module_update(
                module='no_such_pns_module_xyz', operation='install',
            )
        base = self.env['ir.module.module'].search(
            [('name', '=', 'base')], limit=1,
        )
        alias_text = self.env['ai.system.action'].preview_module_update(
            module_ids=[base.id], button='button_immediate_upgrade',
        )
        self.assertIn('base', alias_text.lower())

    def test_user_group_preview(self):
        target = new_test_user(
            self.env, login='pns_grp_target',
            groups='base.group_user',
        )
        text = self.env['ai.system.action'].preview_user_add_group(
            user_id=target.id,
            group='pns_ai_mcp.group_ai_writer',
        )
        self.assertIn(target.name, text)
        applied = self.env['ai.system.action'].apply_user_add_group(
            user_id=target.id,
            group='pns_ai_mcp.group_ai_writer',
        )
        self.assertTrue(applied.get('ok'))
        self.assertTrue(target.has_group('pns_ai_mcp.group_ai_writer'))
        self.env['ai.system.action'].apply_user_remove_group(
            user_id=target.id,
            group='pns_ai_mcp.group_ai_writer',
        )
        self.assertFalse(target.has_group('pns_ai_mcp.group_ai_writer'))

    def test_propose_rejects_required_atoms(self):
        admin = new_test_user(
            self.env, login='pns_aiadmin_atoms',
            groups='base.group_user,pns_ai_mcp.group_ai_admin',
        )
        env_a = api.Environment(self.env.cr, admin.id, {})
        ok, err = validate_safe_plan([{
            'op': 'action',
            'action_code': 'field.set_required',
            'args': {'model': 'res.partner', 'field': 'comment', 'required': True},
        }], env_a)
        self.assertFalse(ok)
        self.assertIn('field_required', (err or ''))

    def test_field_required_propose_opens_choice(self):
        admin = new_test_user(
            self.env, login='pns_aiadmin_choice',
            groups='base.group_user,pns_ai_mcp.group_ai_admin',
        )
        env_a = api.Environment(self.env.cr, admin.id, {})
        pending = create_pending_safe_operation(env_a, [{
            'op': 'field_required',
            'model': 'res.partner',
            'field': 'comment',
            'required': True,
        }], title='Alias required')
        self.assertTrue(pending.get('success'), pending)
        self.assertEqual(pending.get('status'), 'pending_choice')
        self.assertTrue(pending.get('choice_id'))
        self.assertFalse(pending.get('verification_id'))
        self.addCleanup(self._unlink_choice, pending['choice_id'])

    def test_views_picked_stripped_on_validate(self):
        admin = new_test_user(
            self.env, login='pns_aiadmin_strip',
            groups='base.group_user,pns_ai_mcp.group_ai_admin',
        )
        env_a = api.Environment(self.env.cr, admin.id, {})
        step = {
            'op': 'field_required',
            'model': 'res.partner',
            'field': 'comment',
            'required': True,
            '_views_picked': True,
            'view_ids': [1],
        }
        ok, err = validate_safe_plan([step], env_a)
        self.assertTrue(ok, err)
        self.assertNotIn('_views_picked', step)

    def test_view_only_empty_execute_rejected(self):
        admin = new_test_user(
            self.env, login='pns_aiadmin_vonly',
            groups='base.group_user,pns_ai_mcp.group_ai_admin',
        )
        env_a = api.Environment(self.env.cr, admin.id, {})
        with self.assertRaises(UserError):
            execute_safe_plan(env_a, [{
                'op': 'field_required',
                'model': 'res.partner',
                'field': 'comment',
                'required': True,
                'view_only': True,
            }])

    def test_accept_choice_creates_verification(self):
        admin = new_test_user(
            self.env, login='pns_aiadmin_accept',
            groups='base.group_user,pns_ai_mcp.group_ai_admin',
        )
        view = self._form()
        env_a = api.Environment(self.env.cr, admin.id, {})
        pending = create_pending_safe_operation(env_a, [{
            'op': 'field_required',
            'model': 'res.partner',
            'field': 'comment',
            'required': True,
        }], title='Comment required')
        self.addCleanup(self._unlink_choice, pending.get('choice_id'))
        item_ids = [it['id'] for it in (pending.get('items') or [])]
        self.assertIn(view.id, item_ids)
        result = accept_choice(
            env_a, pending['choice_id'], [view.id],
            create_pending_safe_operation,
        )
        self.assertTrue(result.get('success'), result)
        self.assertTrue(result.get('verification_id'))
        self.assertEqual(result.get('status'), 'pending_confirmation')
        self.addCleanup(self._unlink_verification, result['verification_id'])

    def test_apply_uniform_marks_all_copies(self):
        view = self.env['ir.ui.view'].create({
            'name': 'pns.test.alias.uniform.form',
            'model': 'res.partner',
            'type': 'form',
            'arch': (
                '<?xml version="1.0"?>'
                '<form><sheet>'
                '<div class="oe_read_only"><field name="comment"/></div>'
                '<div class="oe_edit_only"><field name="comment"/></div>'
                '</sheet></form>'
            ),
        })
        result = self.env['ai.system.action'].apply_view_set_field_required(
            model='res.partner', field='comment', required=True,
            view_ids=[view.id], uniform=True,
        )
        inherit = self.env['ir.ui.view'].browse(result['ids'][0])
        self.assertNotIn('oe_read_only', inherit.arch)
        self.assertIn("expr=\"//field[@name='comment']\"", inherit.arch)

    def _unlink_choice(self, choice_id):
        if not choice_id:
            return
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            env['ai.safe.choice'].search([
                ('choice_id', '=', choice_id),
            ]).unlink()
            cr.commit()

    def _unlink_verification(self, verification_id):
        if not verification_id:
            return
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            env['ai.safe.operation'].search([
                ('verification_id', '=', verification_id),
            ]).unlink()
            cr.commit()
