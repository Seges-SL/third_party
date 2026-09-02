# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
import uuid

from odoo.exceptions import AccessError
from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.tests._helpers import ensure_test_agents
from odoo.addons.pns_ai_mcp.utils.compat import user_add_group, user_has_group_direct


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestKnowledgeOwnership(TransactionCase):
    """Ownership sin create de res.users (en O14+website_slides cuelga el suite).

    Usa ``base.user_admin`` + ``base.user_demo`` si existe; si no, skip.
    """

    def setUp(self):
        super().setUp()
        self.agent = ensure_test_agents(self.env)
        self.writer_group = self.env.ref('pns_ai_mcp.group_ai_writer')
        self.admin_group = self.env.ref('pns_ai_mcp.group_ai_admin')
        self.admin_user = self.env.ref('base.user_admin')
        if not user_has_group_direct(self.admin_user, self.admin_group):
            user_add_group(self.admin_user, self.admin_group)

        demo = self.env.ref('base.user_demo', raise_if_not_found=False)
        if not demo:
            self.skipTest('base.user_demo no instalado — se evita create res.users')
        self.user_a = demo
        if not user_has_group_direct(self.user_a, self.writer_group):
            user_add_group(self.user_a, self.writer_group)

        # Segundo “escritor”: el propio admin sin quitarle AI Admin no sirve para
        # privacidad. Usamos un partner/usuario portal si hay; si no, reutilizamos
        # demo solo en tests que no necesiten dos escritores distintos.
        self.user_b = self.env['res.users'].search([
            ('share', '=', False),
            ('id', 'not in', [self.admin_user.id, self.user_a.id]),
            ('active', '=', True),
        ], limit=1)
        if not self.user_b:
            self.user_b = False
        else:
            if not user_has_group_direct(self.user_b, self.writer_group):
                user_add_group(self.user_b, self.writer_group)

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
        if not self.user_b:
            self.skipTest('hace falta un segundo usuario interno además de demo')
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
        if not self.user_b:
            self.skipTest('hace falta un segundo usuario interno además de demo')
        Skill = self.env['ai.skill']
        private_code = self._code('ownership-private-skill')
        shared_code = self._code('ownership-shared-skill')
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
