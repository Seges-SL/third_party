# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Legend chips for ai.log negotiation states include the inline SVGs."""
from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestFlowLegend(TransactionCase):

    def test_legend_chips_include_svg_icons(self):
        html = self.env['ai.log'].render_flow_legend(layout='form')
        self.assertEqual(html.count('o_mcp_flow_chip_icon'), 8)
        self.assertEqual(html.count('class="o_mcp_flow_chip"'), 8)
        self.assertNotIn('c2pa', html)
        self.assertIn('viewBox="0 0 24 24"', html)
        for label in (
            'Discovery',
            'AI Engine \u2192 LLM (request)',
            'LLM \u2192 AI Engine (response)',
            'AI Engine \u2192 Tool',
            'Supervised',
            'Turn completed',
            'Provider failover',
            'MCP client \u2192 Odoo',
        ):
            self.assertIn(label, html)
        grid = self.env['ai.log'].render_flow_legend(layout='grid')
        self.assertIn('o_mcp_log_legend_bar', grid)
        self.assertIn('o_mcp_log_usage_chip', grid)
        self.assertIn('o_mcp_log_legend_chips', grid)
        self.assertNotIn('Colors:', grid)
        self.assertNotIn('o_mcp_log_legend_prefix', grid)
        self.assertEqual(grid.count('o_mcp_flow_chip_icon'), 8)

    def test_every_legend_row_has_an_icon(self):
        Log = self.env['ai.log']
        for _bg, _fg, label, _italic, icon_key in Log._FLOW_LEGEND:
            self.assertIn(icon_key, Log._FLOW_ICON_INNER, label)
            self.assertTrue(Log._flow_chip_icon_html(icon_key), label)

    def test_mcp_chip_is_a_plug_not_the_wrench(self):
        Log = self.env['ai.log']
        inner = Log._FLOW_ICON_INNER['mcp_client_to_odoo']
        self.assertNotEqual(inner, Log._FLOW_WRENCH)
        self.assertIn('<rect', inner)
        self.assertIn('rotate(90 12 12)', inner)

    def test_row_icon_follows_flow_and_write_uses_flag(self):
        Log = self.env['ai.log']
        self.assertEqual(
            Log._icon_key_for_row('llm_request', 'read'),
            'engine_to_llm_request',
        )
        self.assertEqual(
            Log._icon_key_for_row('external', 'read'),
            'mcp_client_to_odoo',
        )
        self.assertEqual(
            Log._icon_key_for_row('tool_call', 'write'),
            'safe_plan',
        )
        self.assertFalse(Log._icon_key_for_row('other', 'read'))
        for flow, _label in Log._fields['flow'].selection:
            if flow == 'other':
                continue
            self.assertIn(flow, Log._FLOW_ICON_BY_TYPE, flow)
