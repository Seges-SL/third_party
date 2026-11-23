# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Odoo tests for presentation show_mode."""

from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.utils.presentation_mode import (
    SHOW_MODE_CHART_TABLE,
    SHOW_MODE_TABLE_CHART,
    normalize_show_mode,
)
from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import _table_block_open


@tagged('standard', 'post_install', '-at_install')
class TestPresentationMode(TransactionCase):
    def test_normalize_show_mode(self):
        self.assertEqual(normalize_show_mode('show-chart'), SHOW_MODE_CHART_TABLE)
        self.assertEqual(normalize_show_mode('chart-table'), SHOW_MODE_CHART_TABLE)
        self.assertEqual(normalize_show_mode('invalid'), SHOW_MODE_TABLE_CHART)

    def test_table_block_show_mode_attr(self):
        html = _table_block_open(
            [{'a': 1, 'b': 2}],
            render_context={'show_mode': SHOW_MODE_CHART_TABLE},
        )
        self.assertIn('data-ai-show-mode="show-chart"', html)
