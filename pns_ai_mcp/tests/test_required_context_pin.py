# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
import uuid

from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.tests._helpers import create_test_agent


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestRequiredContextPin(TransactionCase):
    """required_context_codes stay on the agent's Contexts list."""

    def _ctx(self, suffix, active=True):
        code = 'pin_demo_%s_%s' % (suffix, uuid.uuid4().hex[:8])
        return self.env['ai.context'].create({
            'code': code,
            'description': 'test %s' % code,
            'context_type': 'domain',
            'locale': False,
            'content': (
                '<context><metadata><code>%s</code></metadata>'
                '<body>%s</body></context>' % (code, code)
            ),
            'active': active,
        })

    def test_required_contexts_survive_clear(self):
        pin_a = self._ctx('a')
        pin_b = self._ctx('b')
        extra = self._ctx('extra')
        agent = create_test_agent(
            self.env,
            'test_pin_host_%s' % uuid.uuid4().hex[:8],
            required_context_codes='%s\n%s' % (pin_a.code, pin_b.code),
            context_ids=[(6, 0, [pin_a.id, extra.id])],
        )
        self.assertIn(pin_a, agent.context_ids)
        self.assertIn(pin_b, agent.context_ids)
        self.assertIn(extra, agent.context_ids)

        agent.write({'context_ids': [(5, 0, 0)]})
        self.assertEqual(set(agent.context_ids.ids), {pin_a.id, pin_b.id})

        agent.action_select_none_contexts()
        self.assertEqual(set(agent.context_ids.ids), {pin_a.id, pin_b.id})

    def test_required_skips_inactive_and_missing(self):
        live = self._ctx('live')
        off = self._ctx('off', active=False)
        agent = create_test_agent(
            self.env,
            'test_pin_skip_%s' % uuid.uuid4().hex[:8],
            required_context_codes='%s\n%s\npin_demo_ghost' % (live.code, off.code),
            context_ids=[(6, 0, [live.id])],
        )
        agent.write({'context_ids': [(5, 0, 0)]})
        self.assertEqual(agent.context_ids, live)
