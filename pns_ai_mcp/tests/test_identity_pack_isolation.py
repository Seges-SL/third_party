# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
import uuid

from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.tests._helpers import create_test_agent


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestIdentityPackIsolation(TransactionCase):
    """A leftover foreign self_* pack must not enter another agent's bundle."""

    def _ctx(self, code, product_name, tag='product_name'):
        return self.env['ai.context'].create({
            'code': code,
            'description': 'test %s' % code,
            'context_type': 'domain',
            'locale': False,
            'content': (
                '<context><metadata><code>%s</code>'
                '<%s>%s</%s>'
                '<vendor>Test Vendor</vendor></metadata>'
                '<body>%s</body></context>'
            ) % (code, tag, product_name, tag, code),
            'active': True,
        })

    def test_effective_contexts_drop_foreign_identity(self):
        suffix = uuid.uuid4().hex[:8]
        own = self._ctx('self_%s' % suffix, 'Own Agent')
        foreign = self._ctx('self_other_%s' % suffix, 'Other Agent')
        extra = self.env['ai.context'].create({
            'code': 'iso_extra_%s' % suffix,
            'description': 'extra',
            'context_type': 'domain',
            'locale': False,
            'content': '<context><body>extra</body></context>',
            'active': True,
        })
        agent = create_test_agent(
            self.env,
            'demo_iso_%s' % suffix,
            context_ids=[(6, 0, [own.id, foreign.id, extra.id])],
        )
        effective = agent._get_effective_contexts()
        self.assertIn(own, effective)
        self.assertIn(extra, effective)
        self.assertNotIn(foreign, effective)
        meta = agent._identity_self_metadata()
        self.assertEqual(meta.get('product_name'), 'Own Agent')

    def test_identity_metadata_reads_display_name_alias(self):
        suffix = uuid.uuid4().hex[:8]
        own = self._ctx('self_%s' % suffix, 'Alias Agent', tag='display_name')
        agent = create_test_agent(
            self.env,
            'demo_alias_%s' % suffix,
            context_ids=[(6, 0, [own.id])],
        )
        self.assertEqual(
            agent._identity_self_metadata().get('product_name'),
            'Alias Agent',
        )

    def test_listable_hides_identity_packs(self):
        listed = self.env['ai.context'].get_listable_for_mcp()
        codes = set(listed.mapped('code'))
        self.assertNotIn('self', codes)
        self.assertFalse(any(
            (code or '').startswith('self_') for code in codes
        ))
