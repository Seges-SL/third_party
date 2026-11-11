# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""The chat agent's composition: what it pulls, what is its own, what it never names."""

import uuid

from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.tests._helpers import create_test_agent

_AGENT_CODE = 'pns_ai_chatboo'


@tagged('post_install', '-at_install', 'pns_ai_chatboo')
class TestChatAgentComposition(TransactionCase):

    def _agent(self):
        agent = self.env['ai.agent'].search([('code', '=', _AGENT_CODE)], limit=1)
        if not agent:
            self.skipTest('Chatboo agent missing')
        return agent

    def test_default_skill_codes_at_module_includes_empty_agent_codes(self):
        """@pns_ai_chatboo pulls factory skills that omit agent_codes."""
        agent = create_test_agent(
            self.env,
            'demo_skill_drawer_%s' % uuid.uuid4().hex[:8],
            default_skill_codes='@%s' % _AGENT_CODE,
        )
        codes = self.env['ai.skill'].default_skill_codes_for_agent(agent.code)
        self.assertIn('users', codes)

    def test_engine_pack_is_imported(self):
        chat = self._agent()
        ctx = {'composition_agent_id': chat.id}
        corp = self.env['ai.context'].search([
            ('code', '=', 'corporate_terms'),
        ], limit=1)
        _codes, packs = chat._default_context_tokens()
        if corp and 'pns_ai_mcp' in packs:
            self.assertEqual(
                corp.with_context(**ctx).composition_origin, 'imported',
            )
        self_chat = self.env['ai.context'].search([
            ('code', '=', 'self_chatboo'),
        ], limit=1)
        if self_chat:
            self.assertEqual(
                self_chat.with_context(**ctx).composition_origin, 'own',
            )
        users = self.env['ai.skill'].search([
            ('code', '=', 'users'),
        ], limit=1)
        if users:
            self.assertEqual(
                users.with_context(**ctx).composition_origin, 'own',
            )

    def test_factory_seed_does_not_name_foreign_modules(self):
        blob = (
            self._agent()._module_factory_seed() or {}
        ).get('default_context_codes') or ''
        if not blob:
            return
        self.assertNotIn('@pns_geo', blob)
        self.assertNotIn('acl_security', blob)
        self.assertNotIn('@pns_acl_manager', blob)
