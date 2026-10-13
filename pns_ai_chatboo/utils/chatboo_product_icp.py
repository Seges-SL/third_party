# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Read/write Chatboo product settings stored in ir.config_parameter."""

ICP_SHOW_SYSTRAY = 'pns_ai_chatboo.show_systray'
ICP_DATASET_CACHE_MAX_BYTES = 'pns_ai_mcp.dataset_cache_max_bytes'
ICP_QUERY_DATA_TTL_HOURS = 'pns_ai_chatboo.query_data_ttl_hours'
ICP_HISTORY_RETENTION_DAYS = 'pns_ai_chatboo.history_retention_days'
ICP_DOWNLOAD_MAX_BYTES = 'pns_ai_chatboo.download_max_bytes'
ICP_UPLOAD_MAX_BYTES = 'pns_ai_chatboo.upload_max_bytes'
ICP_CHART_ENGINE = 'pns_ai_chatboo.chart_engine'
ICP_DEFAULT_SHOW_MODE = 'pns_ai_chatboo.default_show_mode'
ICP_LEGACY_DEFAULT_SHOWMODE = 'pns_ai_chatboo.default_showmode'
ICP_XLSX_FLOAT_DECIMALS = 'pns_ai_chatboo.xlsx_float_decimals'
ICP_XLSX_THOUSANDS = 'pns_ai_chatboo.xlsx_thousands'

DEFAULT_DATASET_CACHE_BYTES = 8 * 1024 * 1024
DEFAULT_QUERY_DATA_TTL_HOURS = 12
DEFAULT_HISTORY_RETENTION_DAYS = 30
DEFAULT_DOWNLOAD_MAX_BYTES = 15 * 1024 * 1024
DEFAULT_UPLOAD_MAX_BYTES = 15 * 1024 * 1024
DEFAULT_CHART_ENGINE = 'echarts'
# Layout pair only (table-first / chart-first). Not result modes table|dashboard.
DEFAULT_PRESENTATION_SHOW_MODE = 'show-table'
DEFAULT_XLSX_FLOAT_DECIMALS = 2
DEFAULT_XLSX_THOUSANDS = True
XLSX_FLOAT_DECIMALS_MAX = 10

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


def normalize_xlsx_float_decimals(value, default=DEFAULT_XLSX_FLOAT_DECIMALS):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(XLSX_FLOAT_DECIMALS_MAX, n))


def upload_max_bytes(env):
    """Per-file limit for pictures and files sent to the chat. 0 = no limit."""
    raw = env['ir.config_parameter'].sudo().get_param(
        ICP_UPLOAD_MAX_BYTES, DEFAULT_UPLOAD_MAX_BYTES,
    )
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_UPLOAD_MAX_BYTES


def _data_url_bytes(value):
    """Decoded size of a base64 payload, with or without ``data:...;base64,``."""
    text = value if isinstance(value, str) else ''
    if text.startswith('data:') and ',' in text:
        text = text.split(',', 1)[1]
    text = text.strip()
    return (len(text) * 3) // 4 - text[-2:].count('=')


def oversized_upload(env, images=None, files=None, image_names=None):
    """Name ('' if unnamed) of the first upload over the limit, else None."""
    limit = upload_max_bytes(env)
    if not limit:
        return None
    names = list(image_names or [])
    for idx, image in enumerate(images or []):
        if _data_url_bytes(image) > limit:
            return (names[idx] if idx < len(names) else '') or ''
    for item in files or []:
        item = item if isinstance(item, dict) else {}
        if _data_url_bytes(item.get('data')) > limit:
            return item.get('name') or ''
    return None


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
    try:
        retention_days = int(
            icp.get_param(
                ICP_HISTORY_RETENTION_DAYS, DEFAULT_HISTORY_RETENTION_DAYS,
            )
        )
    except (TypeError, ValueError):
        retention_days = DEFAULT_HISTORY_RETENTION_DAYS
    try:
        download_bytes = int(
            icp.get_param(ICP_DOWNLOAD_MAX_BYTES, DEFAULT_DOWNLOAD_MAX_BYTES)
        )
    except (TypeError, ValueError):
        download_bytes = DEFAULT_DOWNLOAD_MAX_BYTES
    upload_bytes = upload_max_bytes(env)
    show_mode_raw = icp.get_param(ICP_DEFAULT_SHOW_MODE)
    if not show_mode_raw:
        show_mode_raw = icp.get_param(
            ICP_LEGACY_DEFAULT_SHOWMODE, DEFAULT_PRESENTATION_SHOW_MODE,
        )
    return {
        'show_systray': _icp_bool(icp, ICP_SHOW_SYSTRAY, True),
        'dataset_cache_max_bytes': 0 if cache_bytes <= 0 else cache_bytes,
        'dataset_cache_max_mb': (
            0 if cache_bytes <= 0 else max(1, cache_bytes // (1024 * 1024))
        ),
        'query_data_ttl_hours': ttl_hours,
        'history_retention_days': max(0, retention_days),
        'download_max_mb': (
            0 if download_bytes <= 0 else max(1, download_bytes // (1024 * 1024))
        ),
        'upload_max_mb': (
            0 if upload_bytes <= 0 else max(1, upload_bytes // (1024 * 1024))
        ),
        'chart_engine': normalize_chart_engine(
            icp.get_param(ICP_CHART_ENGINE, DEFAULT_CHART_ENGINE),
        ),
        'default_show_mode': normalize_default_show_mode(show_mode_raw),
        'xlsx_float_decimals': normalize_xlsx_float_decimals(
            icp.get_param(
                ICP_XLSX_FLOAT_DECIMALS, DEFAULT_XLSX_FLOAT_DECIMALS,
            ),
        ),
        'xlsx_thousands': _icp_bool(
            icp, ICP_XLSX_THOUSANDS, DEFAULT_XLSX_THOUSANDS,
        ),
    }


def write_product_settings(
    env,
    show_systray=None,
    dataset_cache_max_mb=None,
    query_data_ttl_hours=None,
    history_retention_days=None,
    download_max_mb=None,
    upload_max_mb=None,
    chart_engine=None,
    default_show_mode=None,
    xlsx_float_decimals=None,
    xlsx_thousands=None,
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
    if history_retention_days is not None:
        days = history_retention_days or 0
        icp.set_param(ICP_HISTORY_RETENTION_DAYS, str(max(0, days)))
    if download_max_mb is not None:
        mb = download_max_mb or 0
        download_bytes = 0 if mb <= 0 else mb * 1024 * 1024
        icp.set_param(ICP_DOWNLOAD_MAX_BYTES, str(download_bytes))
    if upload_max_mb is not None:
        mb = upload_max_mb or 0
        upload_bytes = 0 if mb <= 0 else mb * 1024 * 1024
        icp.set_param(ICP_UPLOAD_MAX_BYTES, str(upload_bytes))
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
    if xlsx_float_decimals is not None:
        icp.set_param(
            ICP_XLSX_FLOAT_DECIMALS,
            str(normalize_xlsx_float_decimals(xlsx_float_decimals)),
        )
    if xlsx_thousands is not None:
        icp.set_param(
            ICP_XLSX_THOUSANDS, 'True' if xlsx_thousands else 'False',
        )
