# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from odoo import fields, models

from ..utils.chatboo_product_icp import (
    DEFAULT_CHART_ENGINE,
    DEFAULT_PRESENTATION_SHOW_MODE,
    read_product_settings,
    write_product_settings,
)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    chatboo_show_systray = fields.Boolean(
        string='Show Chatboo in systray',
        help='Show the Chatboo launcher icon in the top navigation bar.',
        default=True,
    )

    # ── Reutilización de datos entre turnos (Nivel 2) ──
    chatboo_dataset_cache_max_mb = fields.Integer(
        string='Dataset reuse limit (MB)',
        help="Max size of the dataset cached from a data query so the NEXT turn "
             "can reformat/reorder the SAME list without re-querying (kernel-like "
             "reuse; data never enters the model context). Bigger datasets are "
             "not cached (the model just reuses the query code). 0 = no limit. "
             "Guards per-turn (de)serialization cost, not DB storage.",
        default=8,
    )
    chatboo_query_data_ttl_hours = fields.Integer(
        string='Dataset reuse expiry (hours)',
        help="How long a cached dataset stays reusable. After this it is ignored "
             "and purged by the maintenance cron so blobs never pile up. "
             "0 = never expires (only cleared by session retention).",
        default=12,
    )

    chatboo_chart_engine = fields.Selection(
        selection=[
            ('echarts', 'ECharts'),
            ('chartjs', 'Chart.js'),
        ],
        string='Chart engine',
        help='Library used to render charts under server-built tables. '
             'ECharts is recommended for combined bar/line charts.',
        default=DEFAULT_CHART_ENGINE,
        required=True,
    )
    chatboo_default_show_mode = fields.Selection(
        selection=[
            ('show-table', 'show-table (table first; smart chart when eligible)'),
            ('show-chart', 'show-chart (chart open, table always available)'),
        ],
        string='Default showmode',
        help='Starting showmode for each new Chatboo conversation: show-table '
             'or show-chart. Stays until /show-table, /show-chart or phrasing '
             '(“show as chart” / “show as table”). Suspended under painter-free. '
             'Not a per-turn LLM choice.',
        default=DEFAULT_PRESENTATION_SHOW_MODE,
        required=True,
    )

    def get_values(self):
        res = super().get_values()
        product = read_product_settings(self.env)
        res.update({
            'chatboo_show_systray': product['show_systray'],
            'chatboo_dataset_cache_max_mb': product['dataset_cache_max_mb'],
            'chatboo_query_data_ttl_hours': product['query_data_ttl_hours'],
            'chatboo_chart_engine': product['chart_engine'],
            'chatboo_default_show_mode': product['default_show_mode'],
        })
        return res

    def set_values(self):
        super().set_values()
        write_product_settings(
            self.env,
            show_systray=self.chatboo_show_systray,
            dataset_cache_max_mb=self.chatboo_dataset_cache_max_mb,
            query_data_ttl_hours=self.chatboo_query_data_ttl_hours,
            chart_engine=self.chatboo_chart_engine,
            default_show_mode=self.chatboo_default_show_mode,
        )
