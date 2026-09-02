# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
import uuid

from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.tests._helpers import create_test_agent, ensure_test_agents


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestAgentEffectiveContexts(TransactionCase):
    """Agents own their contexts directly; there is no agent-to-agent
    inheritance. Shared knowledge is materialised at import time by linking a
    context to every agent whose code it declares (see
    ``ai.context._resolve_import_agent_codes``)."""

    def setUp(self):
        super().setUp()
        ensure_test_agents(self.env)
        self._uid = uuid.uuid4().hex[:8]

    def _code(self, base):
        return '%s_%s' % (base, self._uid)

    def _create_domain_context(self, code):
        # ai.context no tiene campo name (_rec_name=code).
        return self.env['ai.context'].create({
            'code': code,
            'description': 'Test %s' % code,
            'context_type': 'domain',
            'content': 'test content for %s' % code,
            'source_module': 'pns_ai_mcp',
        })

    def test_effective_contexts_returns_own_contexts(self):
        own = self._create_domain_context(self._code('test_own'))
        agent = create_test_agent(
            self.env, self._code('test_agent_own'),
            context_ids=[(6, 0, [own.id])],
        )
        self.assertEqual(agent._get_effective_contexts(), own)

    def test_effective_contexts_are_independent_between_agents(self):
        own_a = self._create_domain_context(self._code('test_own_a'))
        own_b = self._create_domain_context(self._code('test_own_b'))
        agent_a = create_test_agent(
            self.env, self._code('test_agent_a'),
            context_ids=[(6, 0, [own_a.id])],
        )
        agent_b = create_test_agent(
            self.env, self._code('test_agent_b'),
            context_ids=[(6, 0, [own_b.id])],
        )
        self.assertEqual(agent_a._get_effective_contexts(), own_a)
        self.assertEqual(agent_b._get_effective_contexts(), own_b)
        self.assertNotIn(own_b, agent_a._get_effective_contexts())
