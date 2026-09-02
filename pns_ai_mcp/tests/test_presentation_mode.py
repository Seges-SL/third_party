# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Odoo tests for presentation show_mode."""

import unittest

from odoo.addons.pns_ai_mcp.utils.presentation_mode import (
    SHOW_MODE_CHART_TABLE,
    SHOW_MODE_TABLE_CHART,
    normalize_show_mode,
    resolve_show_mode_from_message,
)
from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import _table_block_open


class TestPresentationMode(unittest.TestCase):
    def test_normalize_show_mode(self):
        self.assertEqual(normalize_show_mode('show-chart'), SHOW_MODE_CHART_TABLE)
        self.assertEqual(normalize_show_mode('chart-table'), SHOW_MODE_CHART_TABLE)
        self.assertEqual(normalize_show_mode('invalid'), SHOW_MODE_TABLE_CHART)

    def test_spanish_chart_hint(self):
        self.assertEqual(
            resolve_show_mode_from_message('ver en gráfico', 'es_ES'),
            SHOW_MODE_CHART_TABLE,
        )

    def test_table_block_show_mode_attr(self):
        html = _table_block_open(
            [{'a': 1, 'b': 2}],
            render_context={'show_mode': SHOW_MODE_CHART_TABLE},
        )
        self.assertIn('data-chatboo-show-mode="show-chart"', html)
