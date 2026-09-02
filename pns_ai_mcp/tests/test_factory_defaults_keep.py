# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
import uuid

from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.tests._helpers import create_test_agent


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestFactoryDefaultsKeepOthers(TransactionCase):
    """Defaults re-adds the seed and keeps links other modules added."""

    def _ctx(self, suffix):
        code = 'factory_demo_%s_%s' % (suffix, uuid.uuid4().hex[:8])
        return self.env['ai.context'].create({
            'code': code,
            'description': 'test %s' % code,
            'context_type': 'domain',
            'locale': False,
            'content': (
                '<context><metadata><code>%s</code></metadata>'
                '<body>%s</body></context>' % (code, code)
            ),
            'active': True,
        })

    def test_defaults_keeps_extra_context(self):
        seed = self._ctx('seed')
        extra = self._ctx('extra')
        agent = create_test_agent(
            self.env,
            'test_factory_keep_%s' % uuid.uuid4().hex[:8],
            default_context_codes=seed.code,
            context_ids=[(6, 0, [extra.id])],
        )
        self.assertNotIn(seed, agent.context_ids)
        self.assertIn(extra, agent.context_ids)
        agent.action_reset_contexts_to_default()
        self.assertIn(seed, agent.context_ids)
        self.assertIn(extra, agent.context_ids)

    def test_defaults_keeps_extra_skill(self):
        suffix = uuid.uuid4().hex[:8]
        seed = self.env['ai.skill'].create({
            'code': 'factory_skill_seed_%s' % suffix,
            'name': 'Seed skill',
            'description': 'seed',
            'content': 'seed skill',
        })
        extra = self.env['ai.skill'].create({
            'code': 'factory_skill_extra_%s' % suffix,
            'name': 'Extra skill',
            'description': 'extra',
            'content': 'extra skill',
        })
        agent = create_test_agent(
            self.env,
            'test_factory_skill_%s' % suffix,
            default_skill_codes=seed.code,
            skill_ids=[(6, 0, [extra.id])],
        )
        self.assertNotIn(seed, agent.skill_ids)
        self.assertIn(extra, agent.skill_ids)
        agent.action_reset_skills_to_default()
        self.assertIn(seed, agent.skill_ids)
        self.assertIn(extra, agent.skill_ids)

    def test_factory_seed_does_not_name_foreign_modules(self):
        """Product XML/Python must not list modules this addon does not depend on."""
        Agent = self.env['ai.agent']
        mcp = Agent.search([('code', '=', 'pns_ai_mcp')], limit=1)
        if not mcp:
            self.skipTest('MCP agent missing')
        blob = (mcp._module_factory_seed() or {}).get('default_context_codes') or ''
        self.assertIn('@pns_ai_mcp', blob)
        self.assertNotIn('@pns_geo', blob)
        self.assertNotIn('@occ_custom_ai', blob)
        self.assertNotIn('@pns_ocr', blob)
        self.assertNotIn('acl_security', blob)
        self.assertNotIn('@pns_acl_manager', blob)
        chatboo = Agent.search([('code', '=', 'pns_ai_chatboo')], limit=1)
        if not chatboo:
            return
        chat_blob = (
            chatboo._module_factory_seed() or {}
        ).get('default_context_codes') or ''
        if chat_blob:
            self.assertNotIn('@pns_geo', chat_blob)
            self.assertNotIn('@occ_custom_ai', chat_blob)
            self.assertNotIn('acl_security', chat_blob)
            self.assertNotIn('@pns_acl_manager', chat_blob)
