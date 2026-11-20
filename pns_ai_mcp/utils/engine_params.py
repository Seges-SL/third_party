# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""System parameters the engine reads: charts, layout, numbers, downloads.

They serve every host (chat, voice, MCP), so the engine owns the keys.
A host's settings screen writes them through these names.
"""

ICP_CHART_ENGINE = 'pns_ai.chart_engine'
ICP_DEFAULT_SHOW_MODE = 'pns_ai.default_show_mode'
ICP_XLSX_FLOAT_DECIMALS = 'pns_ai.xlsx_float_decimals'
ICP_XLSX_THOUSANDS = 'pns_ai.xlsx_thousands'
ICP_DOWNLOAD_MAX_BYTES = 'pns_ai.download_max_bytes'

DEFAULT_CHART_ENGINE = 'echarts'
VALID_CHART_ENGINES = frozenset({'echarts', 'chartjs'})
# Layout pair a conversation starts with. ``table`` / ``dashboard`` are
# result-only and never a default.
DEFAULT_LAYOUT_SHOW_MODE = 'show-table'
VALID_LAYOUT_SHOW_MODES = frozenset({'show-table', 'show-chart'})
DEFAULT_XLSX_FLOAT_DECIMALS = 2
DEFAULT_XLSX_THOUSANDS = True
XLSX_FLOAT_DECIMALS_MAX = 10
DEFAULT_DOWNLOAD_MAX_BYTES = 15 * 1024 * 1024

# Named leftover: the keys these values had before the engine owned them.
# Renamed once on ``-u`` by ``schema_fossils.promote_engine_params``.
# The first old key wins when two map to the same new key.
PREVIOUS_KEYS = (
    ('pns_ai_chatboo.chart_engine', ICP_CHART_ENGINE),
    ('pns_ai_chatboo.default_show_mode', ICP_DEFAULT_SHOW_MODE),
    ('pns_ai_chatboo.default_showmode', ICP_DEFAULT_SHOW_MODE),
    ('pns_ai_chatboo.xlsx_float_decimals', ICP_XLSX_FLOAT_DECIMALS),
    ('pns_ai_chatboo.xlsx_thousands', ICP_XLSX_THOUSANDS),
    ('pns_ai_chatboo.download_max_bytes', ICP_DOWNLOAD_MAX_BYTES),
)

# PAAP §14.3 spellings of the same pair.
_LAYOUT_LEGACY = {
    'table-chart': 'show-table',
    'chart-table': 'show-chart',
}


def normalize_chart_engine(value, default=DEFAULT_CHART_ENGINE):
    val = str(value or default).strip().lower()
    return val if val in VALID_CHART_ENGINES else default


def normalize_layout_show_mode(value, default=DEFAULT_LAYOUT_SHOW_MODE):
    val = str(value or default).strip().lower()
    val = _LAYOUT_LEGACY.get(val, val)
    return val if val in VALID_LAYOUT_SHOW_MODES else default


def normalize_xlsx_float_decimals(value, default=DEFAULT_XLSX_FLOAT_DECIMALS):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(XLSX_FLOAT_DECIMALS_MAX, n))


def param_bool(value, default=True):
    if value is None:
        return default
    return str(value) not in ('False', 'false', '0', '')


def _icp(env):
    return env['ir.config_parameter'].sudo()


def chart_engine(env):
    return normalize_chart_engine(
        _icp(env).get_param(ICP_CHART_ENGINE, DEFAULT_CHART_ENGINE),
    )


def raw_default_show_mode(env):
    """Stored default layout, unnormalized (callers apply their own set)."""
    return _icp(env).get_param(ICP_DEFAULT_SHOW_MODE, DEFAULT_LAYOUT_SHOW_MODE)


def currency_decimals(env):
    """Decimal places of the company currency (EUR 2, KWD 3, JPY 0)."""
    try:
        places = env.company.currency_id.decimal_places
    except Exception:
        return DEFAULT_XLSX_FLOAT_DECIMALS
    return normalize_xlsx_float_decimals(places)


def xlsx_float_decimals(env):
    """Decimal places of a decimal number in the chat table, PDF, Word and
    Excel. Unset, they follow the company currency."""
    raw = _icp(env).get_param(ICP_XLSX_FLOAT_DECIMALS)
    if raw in (None, False, ''):
        return currency_decimals(env)
    return normalize_xlsx_float_decimals(raw, default=currency_decimals(env))


def xlsx_thousands(env):
    return param_bool(
        _icp(env).get_param(
            ICP_XLSX_THOUSANDS, 'True' if DEFAULT_XLSX_THOUSANDS else 'False',
        ),
        DEFAULT_XLSX_THOUSANDS,
    )


def download_max_bytes(env):
    raw = _icp(env).get_param(ICP_DOWNLOAD_MAX_BYTES, DEFAULT_DOWNLOAD_MAX_BYTES)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_DOWNLOAD_MAX_BYTES
