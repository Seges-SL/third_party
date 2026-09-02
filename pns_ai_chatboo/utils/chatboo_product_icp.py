# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Read/write Chatboo product settings stored in ir.config_parameter."""

ICP_SHOW_SYSTRAY = 'pns_ai_chatboo.show_systray'
ICP_DATASET_CACHE_MAX_BYTES = 'pns_ai_mcp.dataset_cache_max_bytes'
ICP_QUERY_DATA_TTL_HOURS = 'pns_ai_chatboo.query_data_ttl_hours'
ICP_CHART_ENGINE = 'pns_ai_chatboo.chart_engine'
ICP_DEFAULT_SHOW_MODE = 'pns_ai_chatboo.default_show_mode'
ICP_LEGACY_DEFAULT_SHOWMODE = 'pns_ai_chatboo.default_showmode'

DEFAULT_DATASET_CACHE_BYTES = 8 * 1024 * 1024
DEFAULT_QUERY_DATA_TTL_HOURS = 12
DEFAULT_CHART_ENGINE = 'echarts'
# Layout pair only (table-first / chart-first). Not result modes table|dashboard.
DEFAULT_PRESENTATION_SHOW_MODE = 'show-table'

VALID_CHART_ENGINES = frozenset({'echarts', 'chartjs'})
VALID_PRESENTATION_SHOW_MODES = frozenset({'show-table', 'show-chart'})
_SHOW_MODE_LEGACY = {
    'table-chart': 'show-table',
    'chart-table': 'show-chart',
}

CHATBOO_AGENT_CODE = 'pns_ai_chatboo'


def _icp_bool(icp, key, default=True):
    val = icp.get_param(key, 'True' if default else 'False')
    return val not in ('False', 'false', '0', '')


def normalize_chart_engine(value, default=DEFAULT_CHART_ENGINE):
    val = str(value or default).strip().lower()
    return val if val in VALID_CHART_ENGINES else default


def normalize_default_show_mode(value, default=DEFAULT_PRESENTATION_SHOW_MODE):
    val = str(value or default).strip().lower()
    val = _SHOW_MODE_LEGACY.get(val, val)
    return val if val in VALID_PRESENTATION_SHOW_MODES else default


def read_product_settings(env):
    """Return Chatboo product settings as a plain dict."""
    icp = env['ir.config_parameter'].sudo()
    try:
        cache_bytes = int(
            icp.get_param(ICP_DATASET_CACHE_MAX_BYTES, DEFAULT_DATASET_CACHE_BYTES)
        )
    except (TypeError, ValueError):
        cache_bytes = DEFAULT_DATASET_CACHE_BYTES
    try:
        ttl_hours = int(
            icp.get_param(ICP_QUERY_DATA_TTL_HOURS, DEFAULT_QUERY_DATA_TTL_HOURS)
        )
    except (TypeError, ValueError):
        ttl_hours = DEFAULT_QUERY_DATA_TTL_HOURS
    show_mode_raw = icp.get_param(ICP_DEFAULT_SHOW_MODE)
    if not show_mode_raw:
        show_mode_raw = icp.get_param(
            ICP_LEGACY_DEFAULT_SHOWMODE, DEFAULT_PRESENTATION_SHOW_MODE,
        )
    return {
        'show_systray': _icp_bool(icp, ICP_SHOW_SYSTRAY, True),
        'dataset_cache_max_mb': (
            0 if cache_bytes <= 0 else max(1, cache_bytes // (1024 * 1024))
        ),
        'query_data_ttl_hours': ttl_hours,
        'chart_engine': normalize_chart_engine(
            icp.get_param(ICP_CHART_ENGINE, DEFAULT_CHART_ENGINE),
        ),
        'default_show_mode': normalize_default_show_mode(show_mode_raw),
    }


def write_product_settings(
    env,
    show_systray=None,
    dataset_cache_max_mb=None,
    query_data_ttl_hours=None,
    chart_engine=None,
    default_show_mode=None,
):
    """Persist only the keys explicitly passed (partial update)."""
    icp = env['ir.config_parameter'].sudo()
    if show_systray is not None:
        icp.set_param(ICP_SHOW_SYSTRAY, 'True' if show_systray else 'False')
    if dataset_cache_max_mb is not None:
        mb = dataset_cache_max_mb or 0
        cache_bytes = 0 if mb <= 0 else mb * 1024 * 1024
        icp.set_param(ICP_DATASET_CACHE_MAX_BYTES, str(cache_bytes))
    if query_data_ttl_hours is not None:
        ttl = query_data_ttl_hours or 0
        icp.set_param(ICP_QUERY_DATA_TTL_HOURS, str(max(0, ttl)))
    if chart_engine is not None:
        icp.set_param(
            ICP_CHART_ENGINE,
            normalize_chart_engine(chart_engine),
        )
    if default_show_mode is not None:
        icp.set_param(
            ICP_DEFAULT_SHOW_MODE,
            normalize_default_show_mode(default_show_mode),
        )
