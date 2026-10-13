# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Chatboo Settings fields: systray, dataset reuse, chart engine, Excel ICP."""
from odoo import fields, models

from ..utils.chatboo_product_icp import (
    DEFAULT_CHART_ENGINE,
    DEFAULT_PRESENTATION_SHOW_MODE,
    DEFAULT_XLSX_FLOAT_DECIMALS,
    DEFAULT_XLSX_THOUSANDS,
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
        string='Hidden list copy (MB)',
        help="Copy of the last table, kept aside so the next message can "
             "reorder it without a new query. Those rows stay out of the "
             "prompt: sending the whole table every turn used to fill it. "
             "A heavier list is skipped. 0 = no size cap.",
        default=8,
    )
    chatboo_query_data_ttl_hours = fields.Integer(
        string='Hours that copy lasts',
        help="After this the aside copy is dropped. Tables already on "
             "screen and files you uploaded stay in the session. A later "
             "\"same list, but…\" runs the query again. "
             "0 = the copy lasts as long as the session.",
        default=12,
    )
    chatboo_history_retention_days = fields.Integer(
        string='Session retention (days)',
        help="The chat you reopen: messages, tables on screen, and uploaded "
             "files. Deleted after this many days with no use. 0 = keep.",
        default=30,
    )
    chatboo_download_max_mb = fields.Integer(
        string='Download limit (MB)',
        help="Max size of a session file chip (named PDF/Excel/Word). "
             "The bubble Excel icon does not use this limit. 0 = no limit.",
        default=15,
    )
    chatboo_upload_max_mb = fields.Integer(
        string='Upload limit (MB)',
        help="Max size of each picture or file sent to the chat. "
             "Bigger ones are refused before the turn starts. 0 = no limit.",
        default=15,
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
             '(“show as chart” / “show as table”). Suspended under compose-model. '
             'Not a per-turn LLM choice.',
        default=DEFAULT_PRESENTATION_SHOW_MODE,
        required=True,
    )
    chatboo_xlsx_float_decimals = fields.Integer(
        string='Excel float decimals',
        help='Decimal places for floating-point values and formula cells in '
             'Excel exports. Integers stay whole. 0–10.',
        default=DEFAULT_XLSX_FLOAT_DECIMALS,
    )
    chatboo_xlsx_thousands = fields.Boolean(
        string='Excel thousand separators',
        help='Show thousand separators on every numeric Excel cell '
             '(integers, floats, and formulas). Separators follow the '
             'spreadsheet locale.',
        default=DEFAULT_XLSX_THOUSANDS,
    )

    def get_values(self):
        res = super().get_values()
        product = read_product_settings(self.env)
        res.update({
            'chatboo_show_systray': product['show_systray'],
            'chatboo_dataset_cache_max_mb': product['dataset_cache_max_mb'],
            'chatboo_query_data_ttl_hours': product['query_data_ttl_hours'],
            'chatboo_history_retention_days': product['history_retention_days'],
            'chatboo_download_max_mb': product['download_max_mb'],
            'chatboo_upload_max_mb': product['upload_max_mb'],
            'chatboo_chart_engine': product['chart_engine'],
            'chatboo_default_show_mode': product['default_show_mode'],
            'chatboo_xlsx_float_decimals': product['xlsx_float_decimals'],
            'chatboo_xlsx_thousands': product['xlsx_thousands'],
        })
        return res

    def set_values(self):
        super().set_values()
        write_product_settings(
            self.env,
            show_systray=self.chatboo_show_systray,
            dataset_cache_max_mb=self.chatboo_dataset_cache_max_mb,
            query_data_ttl_hours=self.chatboo_query_data_ttl_hours,
            history_retention_days=self.chatboo_history_retention_days,
            download_max_mb=self.chatboo_download_max_mb,
            upload_max_mb=self.chatboo_upload_max_mb,
            chart_engine=self.chatboo_chart_engine,
            default_show_mode=self.chatboo_default_show_mode,
            xlsx_float_decimals=self.chatboo_xlsx_float_decimals,
            xlsx_thousands=self.chatboo_xlsx_thousands,
        )
