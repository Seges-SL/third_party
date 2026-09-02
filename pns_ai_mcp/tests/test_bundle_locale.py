# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.tests._helpers import (
    create_test_agent,
    ensure_test_agents,
    locale_from_code,
)


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestAgentLocale(TransactionCase):

    def setUp(self):
        super().setUp()
        self.agent = ensure_test_agents(self.env)

    @property
    def Context(self):
        return self.env['ai.context']

    @property
    def Agent(self):
        return self.env['ai.agent']

    def _create_context(self, code, context_type='domain', content=None, locale=None):
        """Crea contexto de test; locale explícito (el modelo ya no lo infiere del code)."""
        if locale is None:
            locale = locale_from_code(code) or False
        ctx = self.Context.create({
            'code': code,
            'description': 'test %s' % code,
            'context_type': context_type,
            'locale': locale,
            'content': content or '<context><metadata><code>%s</code></metadata><body>%s</body></context>' % (code, code),
            'active': True,
        })
        # Membership is now the authoritative M2M (agent.context_ids), not agent_id.
        self.agent.context_ids = [(4, ctx.id)]
        return ctx

    def test_assemble_agent_parts_deduplicates_locales(self):
        generic = self._create_context('demo_terms', context_type='locale')
        es = self._create_context('demo_terms_es_ES', context_type='locale')
        de = self._create_context('demo_terms_de_DE', context_type='locale')
        parts = self.Context.assemble_context_parts(generic | es | de, user_locale='es_ES')
        self.assertEqual(len(parts), 1)
        self.assertIn('demo_terms_es_ES', parts[0])

    def test_normalize_agent_context_ids_prefers_generic(self):
        generic = self._create_context('demo_payroll', context_type='domain')
        es = self._create_context('demo_payroll_es_ES', context_type='domain')
        de = self._create_context('demo_payroll_de_DE', context_type='domain')
        canonical = self.Context.normalize_context_ids(generic | es | de)
        self.assertEqual(canonical, [generic.id])

    def test_agent_build_uses_locale_resolution(self):
        from odoo.addons.pns_ai_mcp.utils.context_utils import strip_xml_metadata

        generic = self._create_context('demo_balance', context_type='domain')
        es = self._create_context('demo_balance_es_ES', context_type='domain')
        agent = create_test_agent(self.env, 'test_agent_locale', context_ids=[(6, 0, (generic | es).ids)])
        parts = self.Context.assemble_context_parts(
            agent.context_ids, user_locale='es_ES',
        )
        self.assertEqual(len(parts), 1)
        self.assertIn('demo_balance_es_ES', parts[0])
        self.assertNotIn('demo_balance</body>', parts[0])
        two_stripped = (
            len(strip_xml_metadata(generic.content).encode('utf-8'))
            + len(strip_xml_metadata(es.content).encode('utf-8'))
        )
        self.assertLess(len(parts[0].encode('utf-8')), two_stripped)
        content = agent._build_content(user_locale='es_ES')
        self.assertIn('demo_balance_es_ES', content)
        self.assertNotIn('demo_balance_de_DE', content)

    def test_get_canonical_contexts_for_agent_one_per_base(self):
        self._create_context('demo_canon', context_type='domain')
        self._create_context('demo_canon_es_ES', context_type='domain')
        canonical = self.Context.get_canonical_contexts_for_agent(self.agent)
        codes = canonical.mapped('code')
        self.assertIn('demo_canon', codes)
        self.assertNotIn('demo_canon_es_ES', codes)

    def test_system_context_is_cross_cutting(self):
        """context_type=core contexts are injected into EVERY agent's prompt,
        even when they are NOT listed as agent members."""
        sys_ctx = self.Context.create({
            'code': 'demo_sys_rule',
            'description': 'test demo_sys_rule',
            'context_type': 'core',
            'content': (
                '<context><metadata><code>demo_sys_rule</code></metadata>'
                '<body>demo_sys_rule</body></context>'
            ),
            'active': True,
        })
        agent = create_test_agent(self.env, 'test_xcut_agent', name='No members')
        self.assertFalse(agent.context_ids)
        content = agent._build_content(user_locale='en_US')
        self.assertIn('demo_sys_rule', content)
        self.assertIn(str(sys_ctx.id), agent._context_signature())

    def test_default_agent_excludes_system_members(self):
        """Seeding yields domain_prompt and never keeps system contexts as members."""
        ensure_test_agents(self.env)
        mcp_agent = self.env['ai.agent'].search([('code', '=', 'pns_ai_mcp')], limit=1)
        self.assertTrue(mcp_agent)
        self.assertFalse(mcp_agent.context_ids.filtered(lambda c: c.context_type == 'core'))

    def test_resolve_import_agent_codes_nucleus_defaults_to_mcp_only(self):
        codes = self.Context._resolve_import_agent_codes(
            {}, 'pns_ai_mcp', context_type='domain',
        )
        self.assertEqual(codes, ['pns_ai_mcp'])

    def test_resolve_import_agent_codes_plugin_is_catalog_only(self):
        codes = self.Context._resolve_import_agent_codes(
            {}, 'pns_fleet', context_type='domain',
        )
        self.assertEqual(codes, [])

    def test_resolve_import_agent_codes_own_module_push(self):
        from odoo.addons.pns_ai_mcp.tests._helpers import create_test_agent
        create_test_agent(
            self.env,
            'demo_pack_owner',
            module_name='pns_demo_pack',
        )
        codes = self.Context._resolve_import_agent_codes(
            {}, 'pns_demo_pack', context_type='domain',
        )
        self.assertEqual(codes, ['demo_pack_owner'])

    def test_explicit_agent_codes_blocks_module_pull(self):
        """@module pull must not attach packs with exclusive agent_codes."""
        from odoo.addons.pns_ai_mcp.tests._helpers import create_test_agent
        consumer = create_test_agent(
            self.env,
            'demo_exclusive_pull',
            default_context_codes='@pns_ai_mcp',
        )
        codes = self.Context._pull_agent_codes_for_context(
            'self_mcp', 'pns_ai_mcp', pack_exclusive=True,
        )
        self.assertNotIn(consumer.code, codes)
        codes_open = self.Context._pull_agent_codes_for_context(
            'geo', 'pns_ai_mcp', pack_exclusive=False,
        )
        self.assertIn(consumer.code, codes_open)

    def test_pull_agent_codes_for_context(self):
        from odoo.addons.pns_ai_mcp.tests._helpers import create_test_agent
        agent = create_test_agent(
            self.env,
            'demo_pull_consumer',
            default_context_codes='geo\n@pns_demo_pack',
        )
        codes = self.Context._pull_agent_codes_for_context('geo', 'pns_ai_mcp')
        self.assertIn(agent.code, codes)
        codes_pack = self.Context._pull_agent_codes_for_context(
            'anything', 'pns_demo_pack',
        )
        self.assertIn(agent.code, codes_pack)

    def test_resolve_import_agent_codes_explicit_none(self):
        codes = self.Context._resolve_import_agent_codes(
            {'agent_codes': 'none'}, 'pns_fleet', context_type='domain',
        )
        self.assertEqual(codes, [])

    def test_plugin_context_not_linked_to_mcp_agent(self):
        """Foreign plugin contexts stay in catalog unless agent_codes is set."""
        ensure_test_agents(self.env)
        mcp_agent = self.env['ai.agent'].search([('code', '=', 'pns_ai_mcp')], limit=1)
        fleet_ctx = self.Context.create({
            'code': 'demo_fleet_ops',
            'description': 'fleet test',
            'context_type': 'domain',
            'source_module': 'pns_fleet',
            'content': (
                '<context><metadata><code>demo_fleet_ops</code></metadata>'
                '<body>fleet</body></context>'
            ),
            'active': True,
        })
        self.Context._link_context_to_import_agents(fleet_ctx, [])
        self.assertNotIn(fleet_ctx, mcp_agent.context_ids)

    def test_agent_composition_stats_deduplicated(self):
        generic = self._create_context('demo_stats', context_type='locale')
        es = self._create_context('demo_stats_es_ES', context_type='locale')
        de = self._create_context('demo_stats_de_DE', context_type='locale')
        stats = self.Context.get_composition_stats(
            generic | es | de,
            user_locale='es_ES',
        )
        self.assertEqual(stats['total_count'], 1)
        self.assertEqual(stats['library_count'], 3)
        self.assertGreater(stats['library_size_optimized'], stats['total_size_optimized'])

    def test_hr_payroll_resolves_es_es_with_cascade(self):
        """Shipped hr_payroll_es_ES: accounting-first cascade, bruto/neto PGC, payslip fallback."""
        resolved = self.Context.get_context_for_country('hr_payroll', 'es_ES')
        if not resolved or resolved.code != 'hr_payroll_es_ES':
            self.skipTest('hr_payroll_es_ES not imported in this database')
        parts = self.Context.assemble_context_parts(resolved, user_locale='es_ES')
        self.assertTrue(parts)
        joined = '\n'.join(parts)
        self.assertIn('Step 1: Accounting', joined)
        self.assertIn('640', joined)
        self.assertIn('4751', joined)
        self.assertIn("'gross'", joined)
        self.assertIn("'net'", joined)
        self.assertIn('Payslip fallback', joined)
        self.assertIn('No hay datos de nómina', joined)
        self.assertIn('hr_payroll_accounting_present', joined)
        # Accounting step must precede payslip fallback in the locale context body.
        self.assertLess(joined.index('640'), joined.index('Payslip fallback'))

    def test_hr_payroll_accounting_present_shared(self):
        """Shared accounting presentation context is importable."""
        ctx = self.Context.search(
            [('code', '=', 'hr_payroll_accounting_present')], limit=1,
        )
        if not ctx:
            self.skipTest('hr_payroll_accounting_present not imported')
        # Match por nombre (AST inline); address_home_id solo como prohibido.
        self.assertIn('name_to_emp', ctx.content)
        self.assertIn('address_home_id', ctx.content)
        self.assertIn('has_breakdown', ctx.content)
        self.assertIn("'gross'", ctx.content)

    def test_domain_has_my_locale_filter_ignores_non_list_domain(self):
        """O19 fields_get may pass DomainBool; locale chip logic must skip it."""
        class FakeDomainObject:
            pass

        self.assertFalse(
            self.Context._domain_has_my_locale_filter(FakeDomainObject()),
        )
        self.assertFalse(self.Context._domain_has_my_locale_filter(None))
