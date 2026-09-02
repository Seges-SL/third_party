# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
import uuid

from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.tests._helpers import create_test_agent

ORIGIN_TOKENS = [
    ('native', 'native'),
    ('imported', 'imported'),
    ('pinned', 'pinned'),
    ('extra', 'extra'),
]


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestKnowledgeComposition(TransactionCase):
    """Skill @module pull matches contexts; live rows show four origin tokens."""

    def test_wants_skill_code_pack_and_exclusive(self):
        agent = create_test_agent(
            self.env,
            'demo_skill_pull_%s' % uuid.uuid4().hex[:8],
            default_skill_codes='@pns_demo_pack\nlisted_skill',
        )
        self.assertTrue(agent.wants_skill_code(
            'any_from_pack', source_module='pns_demo_pack',
        ))
        self.assertFalse(agent.wants_skill_code(
            'exclusive_skill',
            source_module='pns_demo_pack',
            pack_exclusive=True,
        ))
        self.assertTrue(agent.wants_skill_code(
            'listed_skill',
            source_module='pns_demo_pack',
            pack_exclusive=True,
        ))

    def test_default_skill_codes_at_module_includes_empty_agent_codes(self):
        """@pns_ai_chatboo pulls factory skills that omit agent_codes."""
        Mod = self.env['ir.module.module']
        if not Mod.search([
            ('name', '=', 'pns_ai_chatboo'),
            ('state', '=', 'installed'),
        ], limit=1):
            self.skipTest('pns_ai_chatboo not installed')
        agent = create_test_agent(
            self.env,
            'demo_skill_drawer_%s' % uuid.uuid4().hex[:8],
            default_skill_codes='@pns_ai_chatboo',
        )
        codes = self.env['ai.skill'].default_skill_codes_for_agent(agent.code)
        self.assertIn('sys_info', codes)

    def _make_ctx(self, source_module, suffix):
        return self.env['ai.context'].create({
            'code': 'comp_%s_%s' % (suffix, uuid.uuid4().hex[:8]),
            'description': suffix,
            'context_type': 'domain',
            'source_module': source_module,
            'content': '<context><body>%s</body></context>' % suffix,
            'active': True,
        })

    def test_composition_origin_four_tokens(self):
        Agent = self.env['ai.agent']
        mcp = Agent.search([('code', '=', 'pns_ai_mcp')], limit=1)
        if not mcp:
            self.skipTest('MCP agent missing')
        native_ctx = self._make_ctx('pns_ai_mcp', 'native')
        imported_ctx = self._make_ctx('pns_geo', 'imported')
        pin_ctx = self._make_ctx('occ_custom_ai', 'pinned')
        extra_ctx = self._make_ctx('pns_other', 'extra')
        empty_ctx = self._make_ctx(False, 'unstamped')
        seed = mcp._module_factory_seed() or {}
        live = '%s\n%s\n@occ_custom_ai\n%s' % (
            mcp.default_context_codes or '',
            seed.get('default_context_codes') or '',
            empty_ctx.code,
        )
        mcp.write({
            'default_context_codes': live,
            'context_ids': [
                (4, native_ctx.id), (4, imported_ctx.id),
                (4, pin_ctx.id), (4, extra_ctx.id), (4, empty_ctx.id),
            ],
        })
        ctx = {'composition_agent_id': mcp.id}
        self.assertEqual(
            native_ctx.with_context(**ctx).composition_origin, 'native',
        )
        self.assertEqual(
            imported_ctx.with_context(**ctx).composition_origin, 'imported',
        )
        self.assertEqual(
            pin_ctx.with_context(**ctx).composition_origin, 'pinned',
        )
        self.assertEqual(
            extra_ctx.with_context(**ctx).composition_origin, 'extra',
        )
        self.assertEqual(
            empty_ctx.with_context(**ctx).composition_origin, 'extra',
        )
        self.assertFalse(native_ctx.with_context(**ctx).composition_locked)

    def test_composition_read_orders_by_origin(self):
        Agent = self.env['ai.agent']
        mcp = Agent.search([('code', '=', 'pns_ai_mcp')], limit=1)
        if not mcp:
            self.skipTest('MCP agent missing')
        extra_ctx = self._make_ctx('pns_other', 'ord_x')
        pin_ctx = self._make_ctx('occ_custom_ai', 'ord_p')
        native_ctx = self._make_ctx('pns_ai_mcp', 'ord_n')
        imported_ctx = self._make_ctx('pns_geo', 'ord_i')
        seed = mcp._module_factory_seed() or {}
        live = '%s\n%s\n@occ_custom_ai' % (
            mcp.default_context_codes or '',
            seed.get('default_context_codes') or '',
        )
        mcp.write({
            'default_context_codes': live,
            'context_ids': [
                (4, extra_ctx.id), (4, pin_ctx.id),
                (4, native_ctx.id), (4, imported_ctx.id),
            ],
        })
        ctx = {'composition_agent_id': mcp.id}
        self.assertEqual(
            native_ctx.with_context(**ctx).composition_origin, 'native',
        )
        self.assertEqual(
            imported_ctx.with_context(**ctx).composition_origin, 'imported',
        )
        self.assertEqual(
            pin_ctx.with_context(**ctx).composition_origin, 'pinned',
        )
        self.assertEqual(
            extra_ctx.with_context(**ctx).composition_origin, 'extra',
        )
        ids = mcp.read(['context_ids'])[0]['context_ids']
        ids = [i if isinstance(i, int) else i[0] for i in ids]
        positions = [
            ids.index(rec.id)
            for rec in (native_ctx, imported_ctx, pin_ctx, extra_ctx)
        ]
        self.assertEqual(positions, sorted(positions))

    def test_factory_restore_excludes_pinned(self):
        Agent = self.env['ai.agent']
        mcp = Agent.search([('code', '=', 'pns_ai_mcp')], limit=1)
        if not mcp:
            self.skipTest('MCP agent missing')
        pin_ctx = self._make_ctx('occ_custom_ai', 'pinrest')
        mcp.write({
            'default_context_codes': (
                (mcp.default_context_codes or '') + '\n@occ_custom_ai'
            ),
            'context_ids': [(4, pin_ctx.id)],
        })
        restore = mcp._factory_restore_codes('context')
        self.assertNotIn(pin_ctx.code, restore)
        self.assertTrue(restore, 'XML seed must expand to restore codes')

    def test_link_ids_shown_filters_without_unlinking(self):
        Agent = self.env['ai.agent']
        mcp = Agent.search([('code', '=', 'pns_ai_mcp')], limit=1)
        if not mcp:
            self.skipTest('MCP agent missing')
        native_ctx = self._make_ctx('pns_ai_mcp', 'shown_n')
        extra_ctx = self._make_ctx('pns_other', 'shown_x')
        mcp.write({
            'default_context_codes': (mcp.default_context_codes or '') + '\n%s' % native_ctx.code,
            'context_ids': [(4, native_ctx.id), (4, extra_ctx.id)],
            'link_show_native': True,
            'link_show_imported': True,
            'link_show_pinned': True,
            'link_show_extra': False,
        })
        self.assertIn(native_ctx, mcp.context_ids_shown)
        self.assertNotIn(extra_ctx, mcp.context_ids_shown)
        self.assertIn(extra_ctx, mcp.context_ids)
        mcp.with_context(link_show_token='extra').action_toggle_link_show()
        self.assertTrue(mcp.link_show_extra)
        self.assertIn(extra_ctx, mcp.context_ids_shown)
        mcp.context_ids_shown = mcp.context_ids_shown - extra_ctx
        self.assertNotIn(extra_ctx, mcp.context_ids)
        mcp.write({
            'context_ids': [(4, extra_ctx.id)],
            'link_show_extra': False,
        })
        remaining = mcp.context_ids_shown
        mcp.context_ids_shown = remaining
        self.assertIn(extra_ctx, mcp.context_ids)

    def test_composition_origin_fields_get_uses_tokens(self):
        info = self.env['ai.context'].fields_get(['composition_origin'])
        selection = info['composition_origin']['selection']
        self.assertEqual(selection, ORIGIN_TOKENS)
        labels = [label for _key, label in selection]
        self.assertEqual(labels, ['native', 'imported', 'pinned', 'extra'])
        self.assertNotIn('Native', labels)
        self.assertNotIn('Added', labels)
        self.assertNotIn('Nativo', labels)
        skill_info = self.env['ai.skill'].fields_get(['composition_origin'])
        self.assertEqual(
            skill_info['composition_origin']['selection'],
            ORIGIN_TOKENS,
        )
        self.assertEqual(info['composition_origin']['string'], 'Origin')
        self.assertEqual(skill_info['composition_origin']['string'], 'Origin')

    def test_chatboo_mcp_pack_is_imported(self):
        Agent = self.env['ai.agent']
        chatboo = Agent.search([('code', '=', 'pns_ai_chatboo')], limit=1)
        if not chatboo:
            self.skipTest('Chatboo agent missing')
        ctx = {'composition_agent_id': chatboo.id}
        corp = self.env['ai.context'].search([
            ('code', '=', 'corporate_terms'),
        ], limit=1)
        _codes, packs = chatboo._default_context_tokens()
        if corp and 'pns_ai_mcp' in packs:
            self.assertEqual(
                corp.with_context(**ctx).composition_origin, 'imported',
            )
        self_chat = self.env['ai.context'].search([
            ('code', '=', 'self_chatboo'),
        ], limit=1)
        if self_chat:
            self.assertEqual(
                self_chat.with_context(**ctx).composition_origin, 'native',
            )
        sys_info = self.env['ai.skill'].search([
            ('code', '=', 'sys_info'),
        ], limit=1)
        if sys_info:
            self.assertEqual(
                sys_info.with_context(**ctx).composition_origin, 'native',
            )

    def test_composition_locked_required_code(self):
        Agent = self.env['ai.agent']
        mcp = Agent.search([('code', '=', 'pns_ai_mcp')], limit=1)
        if not mcp:
            self.skipTest('MCP agent missing')
        self_mcp = self.env['ai.context'].search([
            ('code', '=', 'self_mcp'),
        ], limit=1)
        if not self_mcp:
            self.skipTest('self_mcp missing')
        ctx = {'composition_agent_id': mcp.id}
        self.assertEqual(
            self_mcp.with_context(**ctx).composition_origin, 'native',
        )
        self.assertTrue(self_mcp.with_context(**ctx).composition_locked)
