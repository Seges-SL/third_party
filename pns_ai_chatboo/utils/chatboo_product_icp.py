# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Read/write Chatboo product settings stored in ir.config_parameter.

Charts, default layout, numbers and download limit are engine parameters:
the keys and their normalizers live in ``pns_ai_mcp``. Chatboo only shows
them on its settings screen.
"""
from odoo.addons.pns_ai_mcp.utils.engine_params import (
    ICP_CHART_ENGINE,
    ICP_DEFAULT_SHOW_MODE,
    ICP_DOWNLOAD_MAX_BYTES,
    ICP_XLSX_FLOAT_DECIMALS,
    ICP_XLSX_THOUSANDS,
    chart_engine as read_chart_engine,
    currency_decimals,
    download_max_bytes as read_download_max_bytes,
    normalize_chart_engine,
    normalize_layout_show_mode,
    normalize_xlsx_float_decimals,
    param_bool,
    raw_default_show_mode as read_default_show_mode,
    xlsx_float_decimals as read_xlsx_float_decimals,
    xlsx_thousands as read_xlsx_thousands,
)

ICP_SHOW_SYSTRAY = 'pns_ai_chatboo.show_systray'
ICP_DATASET_CACHE_MAX_BYTES = 'pns_ai_mcp.dataset_cache_max_bytes'
ICP_QUERY_DATA_TTL_HOURS = 'pns_ai_chatboo.query_data_ttl_hours'
ICP_HISTORY_RETENTION_DAYS = 'pns_ai_chatboo.history_retention_days'
ICP_UPLOAD_MAX_BYTES = 'pns_ai_chatboo.upload_max_bytes'
ICP_ALLOW_REMOTE_VOICES = 'pns_ai_chatboo.allow_remote_voices'

DEFAULT_DATASET_CACHE_BYTES = 8 * 1024 * 1024
DEFAULT_QUERY_DATA_TTL_HOURS = 12
DEFAULT_UPLOAD_MAX_BYTES = 15 * 1024 * 1024
# Hard caps a setting cannot switch off: how many files ride one message
# and how much they may weigh together.
MAX_UPLOAD_FILES = 20
MAX_UPLOAD_TOTAL_BYTES = 50 * 1024 * 1024

CHATBOO_AGENT_CODE = 'pns_ai_chatboo'


def upload_max_bytes(env):
    """Per-file limit for pictures and files sent to the chat.

    There is always a limit: an empty, invalid or 0 setting means the
    default, never "no limit".
    """
    raw = env['ir.config_parameter'].sudo().get_param(
        ICP_UPLOAD_MAX_BYTES, DEFAULT_UPLOAD_MAX_BYTES,
    )
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_UPLOAD_MAX_BYTES
    return value if value > 0 else DEFAULT_UPLOAD_MAX_BYTES


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
    names = list(image_names or [])
    for idx, image in enumerate(images or []):
        if _data_url_bytes(image) > limit:
            return (names[idx] if idx < len(names) else '') or ''
    for item in files or []:
        item = item if isinstance(item, dict) else {}
        if _data_url_bytes(item.get('data')) > limit:
            return item.get('name') or ''
    return None


def upload_violation(env, images=None, files=None, image_names=None):
    """Why this turn's uploads are refused, or None when they may go up.

    Returns {'kind': 'file'|'count'|'total', 'name': str, 'limit': int}:
    one file over the per-file limit, too many files in one message, or
    the files together over the total cap.
    """
    images = list(images or [])
    files = list(files or [])
    if len(images) + len(files) > MAX_UPLOAD_FILES:
        return {'kind': 'count', 'name': '', 'limit': MAX_UPLOAD_FILES}
    total = sum(_data_url_bytes(image) for image in images)
    total += sum(
        _data_url_bytes(item.get('data') if isinstance(item, dict) else None)
        for item in files
    )
    if total > MAX_UPLOAD_TOTAL_BYTES:
        return {'kind': 'total', 'name': '', 'limit': MAX_UPLOAD_TOTAL_BYTES}
    name = oversized_upload(env, images, files, image_names)
    if name is not None:
        return {'kind': 'file', 'name': name, 'limit': upload_max_bytes(env)}
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
    raw_retention = icp.get_param(ICP_HISTORY_RETENTION_DAYS)
    if raw_retention is None or raw_retention is False or str(raw_retention).strip() == '':
        retention_days = 0
    else:
        try:
            retention_days = int(raw_retention)
        except (TypeError, ValueError):
            retention_days = 0
    download_bytes = read_download_max_bytes(env)
    upload_bytes = upload_max_bytes(env)
    return {
        'show_systray': param_bool(icp.get_param(ICP_SHOW_SYSTRAY, 'True')),
        'dataset_cache_max_bytes': 0 if cache_bytes <= 0 else cache_bytes,
        'dataset_cache_max_mb': (
            0 if cache_bytes <= 0 else max(1, cache_bytes // (1024 * 1024))
        ),
        'query_data_ttl_hours': ttl_hours,
        'history_retention_days': max(0, retention_days),
        'download_max_mb': (
            0 if download_bytes <= 0 else max(1, download_bytes // (1024 * 1024))
        ),
        'upload_max_mb': max(1, upload_bytes // (1024 * 1024)),
        'chart_engine': read_chart_engine(env),
        'default_show_mode': normalize_layout_show_mode(
            read_default_show_mode(env),
        ),
        'xlsx_float_decimals': read_xlsx_float_decimals(env),
        'xlsx_thousands': read_xlsx_thousands(env),
        'allow_remote_voices': param_bool(
            icp.get_param(ICP_ALLOW_REMOTE_VOICES), False,
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
    allow_remote_voices=None,
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
            normalize_layout_show_mode(default_show_mode),
        )
    if xlsx_float_decimals is not None:
        decimals = normalize_xlsx_float_decimals(xlsx_float_decimals)
        # Equal to the currency, nothing is stored: it keeps following it.
        icp.set_param(
            ICP_XLSX_FLOAT_DECIMALS,
            False if decimals == currency_decimals(env) else str(decimals),
        )
    if xlsx_thousands is not None:
        icp.set_param(
            ICP_XLSX_THOUSANDS, 'True' if xlsx_thousands else 'False',
        )
    if allow_remote_voices is not None:
        icp.set_param(
            ICP_ALLOW_REMOTE_VOICES,
            'True' if allow_remote_voices else 'False',
        )
