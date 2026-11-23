# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Knowledge ownership: private and shared contexts and skills between two writers."""

import uuid

from odoo.exceptions import AccessError
from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.tests._helpers import create_test_user, ensure_test_agents
from odoo.addons.pns_ai_mcp.utils.compat import user_add_group, user_has_group_direct


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestKnowledgeOwnership(TransactionCase):

    def setUp(self):
        super().setUp()
        self.agent = ensure_test_agents(self.env)
        self.writer_group = self.env.ref('pns_ai_mcp.group_ai_writer')
        self.admin_group = self.env.ref('pns_ai_mcp.group_ai_admin')
        self.admin_user = self.env.ref('base.user_admin')
        if not user_has_group_direct(self.admin_user, self.admin_group):
            user_add_group(self.admin_user, self.admin_group)

        writers = [self.env.ref('base.group_user').id, self.writer_group.id]
        self.user_a = create_test_user(self.env, prefix='pns_ownership_a', groups=writers)
        self.user_b = create_test_user(self.env, prefix='pns_ownership_b', groups=writers)

        self._uid = uuid.uuid4().hex[:8]

    def _code(self, base):
        return '%s_%s' % (base, self._uid)

    def _ctx_body(self, code):
        return (
            '<context><metadata><code>%s</code></metadata>'
            '<body>%s</body></context>'
        ) % (code, code)

    def _create_owned_context(self, env, code, owner):
        ctx = env['ai.context'].create({
            'code': code,
            'description': code,
            'context_type': 'domain',
            'content': self._ctx_body(code),
            'owner_id': owner.id,
        })
        self.agent.with_user(self.admin_user).write({
            'context_ids': [(4, ctx.id)],
        })
        return ctx

    def test_private_context_not_in_other_user_prompt(self):
        code = self._code('ownership_private_ctx')
        self._create_owned_context(
            self.env(user=self.user_a), code, self.user_a,
        )
        content_a = self.agent.with_user(self.user_a).get_content(
            user_locale='en_US', active_user=self.user_a,
        )
        self.assertIn(code, content_a)
        content_b = self.agent.with_user(self.user_b).get_content(
            user_locale='en_US', active_user=self.user_b,
        )
        self.assertNotIn(code, content_b)

    def test_writer_cannot_edit_module_context(self):
        module_ctx = self.env['ai.context'].search([
            ('source_module', '!=', False),
            ('context_type', '!=', 'core'),
        ], limit=1)
        if not module_ctx:
            code = self._code('ownership_module_ctx')
            module_ctx = self.env['ai.context'].sudo().create({
                'code': code,
                'description': 'module',
                'context_type': 'domain',
                'content': self._ctx_body(code),
                'source_module': 'pns_ai_mcp',
            })
        with self.assertRaises(AccessError):
            module_ctx.with_user(self.user_a).write({'description': 'hacked'})

    def test_skill_visibility_get_for_agent(self):
        Skill = self.env['ai.skill']
        private_code = self._code('ownership_private_skill')
        shared_code = self._code('ownership_shared_skill')
        Skill.with_user(self.user_a).create({
            'code': private_code,
            'name': 'Private',
            'description': 'private',
            'content': 'private skill',
            'owner_id': self.user_a.id,
        })
        Skill.with_user(self.user_a).create({
            'code': shared_code,
            'name': 'Other private',
            'description': 'other',
            'content': 'other skill',
            'owner_id': self.user_a.id,
        })
        visible_b = Skill.with_user(self.user_b).get_for_agent(
            self.agent.code, user=self.user_b,
        )
        codes_b = set(visible_b.mapped('code'))
        self.assertNotIn(private_code, codes_b)
        self.assertNotIn(shared_code, codes_b)

    def test_admin_hands_a_skill_over_or_opens_it_to_everyone(self):
        """The owner can be changed or cleared by an AI administrator, not by a writer."""
        Skill = self.env['ai.skill']
        code = self._code('ownership_handover_skill')
        skill = Skill.with_user(self.user_a).create({
            'code': code,
            'name': 'Handover',
            'description': 'handover',
            'content': 'handover skill',
        })
        self.assertEqual(skill.owner_id, self.user_a)
        with self.assertRaises(Exception):
            skill.with_user(self.user_a).write({'owner_id': self.user_b.id})
        skill.with_user(self.admin_user).write({'owner_id': self.user_b.id})
        self.assertEqual(skill.owner_id, self.user_b)
        self.assertFalse(Skill.with_user(self.user_a).search([('code', '=', code)]))
        skill.with_user(self.admin_user).write({'owner_id': False})
        self.assertFalse(skill.owner_id)
        for user in (self.user_a, self.user_b):
            self.assertTrue(Skill.with_user(user).search([('code', '=', code)]))

    def test_owner_shares_a_skill_with_a_group(self):
        """Members of a ticked group see and run the skill; the owner keeps editing it."""
        Skill = self.env['ai.skill']
        code = self._code('ownership_shared_group_skill')
        skill = Skill.with_user(self.user_a).create({
            'code': code,
            'name': 'Shared',
            'description': 'shared',
            'content': 'shared skill',
        })
        self.assertFalse(Skill.with_user(self.user_b).search([('code', '=', code)]))
        skill.with_user(self.user_a).write({
            'required_group_ids': [(6, 0, [self.writer_group.id])],
        })
        self.assertTrue(Skill.with_user(self.user_b).search([('code', '=', code)]))
        self.assertTrue(skill.with_user(self.user_b).user_may_run(self.user_b))
        self.assertTrue(skill.user_may_run(self.user_a))
        with self.assertRaises(AccessError):
            skill.with_user(self.user_b).write({'description': 'not mine'})
        outsider = create_test_user(
            self.env, prefix='pns_ownership_c', groups=[self.env.ref('base.group_user').id],
        )
        self.assertFalse(Skill.with_user(outsider).search([('code', '=', code)]))
        self.assertFalse(skill.user_may_run(outsider))

    def test_a_context_shared_with_a_group_reaches_only_its_members(self):
        """Shared contexts leave the agent cache and go per user."""
        code = self._code('ownership_shared_group_ctx')
        ctx = self._create_owned_context(
            self.env(user=self.user_a), code, self.user_a,
        )
        ctx.with_user(self.user_a).write({
            'required_group_ids': [(6, 0, [self.writer_group.id])],
        })
        content_b = self.agent.with_user(self.user_b).get_content(
            user_locale='en_US', active_user=self.user_b,
        )
        self.assertIn(code, content_b)
        outsider = create_test_user(
            self.env, prefix='pns_ownership_d', groups=[self.env.ref('base.group_user').id],
        )
        content_out = self.agent.with_user(outsider).get_content(
            user_locale='en_US', active_user=outsider,
        )
        self.assertNotIn(code, content_out)
        self.assertNotIn(ctx, self.agent._shared_contexts_for_cache())

    def test_admin_can_edit_any_owned_context(self):
        ctx = self._create_owned_context(
            self.env(user=self.user_a), self._code('ownership_admin_edit'),
            self.user_a,
        )
        ctx.with_user(self.admin_user).write({'description': 'admin edit'})
        self.assertEqual(ctx.description, 'admin edit')

    def test_writer_cannot_export_or_import_skills(self):
        Skill = self.env['ai.skill'].with_user(self.user_a)
        with self.assertRaises(AccessError):
            Skill.action_export_skills()
        with self.assertRaises(AccessError):
            Skill.action_open_import_wizard()

    def test_writer_cannot_export_owned_context(self):
        ctx = self._create_owned_context(
            self.env(user=self.user_a), self._code('ownership_export_block'),
            self.user_a,
        )
        with self.assertRaises(AccessError):
            ctx.with_user(self.user_a).action_export_selected()
        with self.assertRaises(AccessError):
            self.env['ai.context'].with_user(self.user_a).action_import_from_zip()
