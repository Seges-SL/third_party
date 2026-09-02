# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from odoo.exceptions import UserError
from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.models.ai_agent_consumer import MCP_BARE_AGENT_CODE
from odoo.addons.pns_ai_mcp.tests._helpers import create_test_user, ensure_test_agents
from odoo.addons.pns_ai_mcp.utils.ai_agent_registry import (
    CHATBOO_AGENT_CODE,
    FEATURE_AGENT_CODES,
)


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestMcpAgent(TransactionCase):

    def setUp(self):
        super().setUp()
        ensure_test_agents(self.env)

    def test_get_mcp_bare_agent_code(self):
        Agent = self.env['ai.agent']
        self.assertEqual(Agent.get_mcp_bare_agent_code(), MCP_BARE_AGENT_CODE)

    def test_resolve_mcp_agent_none_is_bare(self):
        Agent = self.env['ai.agent']
        self.assertEqual(Agent.resolve_mcp_agent_code(None), MCP_BARE_AGENT_CODE)
        self.assertEqual(Agent.resolve_mcp_agent_code(''), MCP_BARE_AGENT_CODE)

    def test_resolve_mcp_agent_explicit(self):
        Agent = self.env['ai.agent']
        mcp_agent = Agent.search([
            ('code', '=', 'pns_ai_mcp'), ('active', '=', True),
        ], limit=1)
        self.assertTrue(mcp_agent)
        self.assertEqual(
            Agent.resolve_mcp_agent_code('pns_ai_mcp'), 'pns_ai_mcp',
        )

    def test_resolve_mcp_agent_unknown_raises(self):
        Agent = self.env['ai.agent']
        with self.assertRaises(UserError):
            Agent.resolve_mcp_agent_code('no_such_agent_xyz')

    def test_mcp_bare_agent_exists_and_active(self):
        agent = self.env['ai.agent'].search([
            ('code', '=', MCP_BARE_AGENT_CODE),
            ('active', '=', True),
        ], limit=1)
        self.assertTrue(agent)

    def test_module_agent_not_deletable(self):
        agent = self.env['ai.agent'].search([
            ('code', '=', MCP_BARE_AGENT_CODE),
        ], limit=1)
        self.assertTrue(agent)
        with self.assertRaises(UserError):
            agent.unlink()

    def test_resolve_inference_via_feature_key(self):
        Agent = self.env['ai.agent']
        self.assertEqual(
            Agent.resolve_inference_agent_code(None, consumer_key='chatboo'),
            CHATBOO_AGENT_CODE,
        )

    def test_resolve_inference_missing_code_raises(self):
        Agent = self.env['ai.agent']
        with self.assertRaises(UserError):
            Agent.resolve_inference_agent_code(None)

    def test_feature_agent_codes_chatboo(self):
        self.assertEqual(FEATURE_AGENT_CODES['chatboo'], CHATBOO_AGENT_CODE)

    def test_settings_open_module_endpoint_agents(self):
        settings = self.env['res.config.settings'].create({})
        action = settings.action_open_module_endpoint_agents()
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'ai.agent')
        list_mode = 'list' if action['view_mode'].startswith('list') else 'tree'
        self.assertIn(list_mode, action['view_mode'])
        agents = self.env['ai.agent'].search(action['domain'])
        self.assertIn(MCP_BARE_AGENT_CODE, agents.mapped('code'))

    def test_settings_open_module_inference_agents(self):
        settings = self.env['res.config.settings'].create({})
        action = settings.action_open_module_inference_agents()
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'ai.agent')
        agents = self.env['ai.agent'].search(action['domain'])
        for agent in agents:
            self.assertEqual(agent.origin, 'module')
            self.assertEqual(agent.agent_type, 'inference')

    def test_action_open_module_agent_by_code(self):
        settings = self.env['res.config.settings'].create({})
        action = settings.with_context(
            agent_code=MCP_BARE_AGENT_CODE,
        ).action_open_module_agent()
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'ai.agent')
        agent = self.env['ai.agent'].browse(action['res_id'])
        self.assertEqual(agent.code, MCP_BARE_AGENT_CODE)

    def test_action_open_form(self):
        agent = self.env['ai.agent'].search([
            ('code', '=', MCP_BARE_AGENT_CODE),
        ], limit=1)
        action = agent.action_open_form()
        self.assertEqual(action['res_model'], 'ai.agent')
        self.assertEqual(action['res_id'], agent.id)

    def test_get_providers_for_agent_without_admin_acl(self):
        """Chatboo users must resolve provider chains without AI Administrator."""
        agent = self.env['ai.agent'].search([
            ('code', '=', CHATBOO_AGENT_CODE), ('active', '=', True),
        ], limit=1)
        self.assertTrue(agent, 'chatboo agent must exist')
        if not agent.provider_ids:
            provider = self.env['ai.provider'].search([], limit=1)
            self.assertTrue(provider, 'need at least one ai.provider for test')
            self.env['ai.agent.provider'].sudo().create({
                'agent_id': agent.id,
                'provider_id': provider.id,
                'priority': 0,
            })

        plain_user = create_test_user(self.env, prefix='ai_plain_user')
        engine = self.env['ai.execution.engine'].with_user(plain_user)
        providers = engine.get_providers_for_agent(CHATBOO_AGENT_CODE)
        self.assertTrue(providers, 'plain user should resolve providers')
        resolved = engine.resolve_provider(CHATBOO_AGENT_CODE)
        self.assertTrue(resolved)

    def test_api_key_for_inference_without_admin_acl(self):
        """Inference must read provider credentials without exposing them in UI."""
        from odoo.addons.pns_ai_mcp.utils.compat import invalidate_recordset_fields

        provider = self.env['ai.provider'].search([], limit=1)
        self.assertTrue(provider, 'need at least one ai.provider for test')
        provider.sudo().write({'api_key': 'test-secret-key'})
        invalidate_recordset_fields(provider, ['api_key'])

        plain_user = create_test_user(self.env, prefix='ai_plain_user2')
        # Browse fresco: evita cache del recordset admin (groups= no siempre raise).
        prov_as_user = self.env['ai.provider'].with_user(plain_user).browse(provider.id)
        try:
            exposed = prov_as_user.api_key
        except Exception:
            exposed = None
        self.assertFalse(
            exposed,
            'plain user must not see provider api_key (got %r)' % (exposed,),
        )
        self.assertEqual(prov_as_user._api_key_for_inference(), 'test-secret-key')
