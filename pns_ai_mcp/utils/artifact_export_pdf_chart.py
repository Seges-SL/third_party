# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""The chart printed inside the PDF."""

from __future__ import annotations

from .artifact_export_table import (
    public_columns,
    public_rows,
    tabular_rows,
)

from .artifact_export_request import (
    _CHART_FILE_SHOW_MODES,
    payload_allows_charts,
    payload_show_mode,
    wants_on_screen_table,
)


def wants_on_screen_blocks(payload, rows=None):
    """Keep turn HTML when the listing or a chart should paint."""
    return wants_on_screen_table(payload) or clip_include_chart(payload, rows)


_PDF_CHART_MIN_ROWS = 3


_PDF_CHART_MAX_CATS = 24


_PDF_CHART_MAX_SERIES = 4


_PDF_CHART_SCALE_RATIO = 8.0


def _is_chart_id_key(key):
    name = str(key or '')
    return name == 'id' or name.endswith('_id')


def coerce_chart_number(value):
    """Parse a cell into a float. Separators only; no locale word list."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if value != value or value in (float('inf'), float('-inf')):
            return None
        return float(value)
    text = str(value or '').strip()
    if not text:
        return None
    cleaned = []
    for ch in text:
        if ch.isdigit() or ch in '.,-':
            cleaned.append(ch)
    text = ''.join(cleaned)
    if text in ('', '-', '--', '.', ',', '-.', '-,'):
        return None
    if text.count(',') == 1 and text.count('.') > 1:
        text = text.replace('.', '').replace(',', '.')
    elif text.count(',') == 1 and text.count('.') == 0:
        text = text.replace(',', '.')
    elif text.count(',') == 1 and text.count('.') == 1:
        if text.rfind(',') > text.rfind('.'):
            text = text.replace('.', '').replace(',', '.')
        else:
            text = text.replace(',', '')
    try:
        return float(text)
    except ValueError:
        return None


def _column_is_numeric(rows, key):
    hits = 0
    seen = 0
    for row in rows:
        val = row.get(key) if isinstance(row, dict) else None
        if val in (None, ''):
            continue
        seen += 1
        if coerce_chart_number(val) is not None:
            hits += 1
    return seen >= 2 and hits >= max(2, int(seen * 0.7))


def payload_has_chart_series(payload=None, rows=None):
    """True when public rows have at least two columns and one numeric series."""
    public = public_rows(tabular_rows(payload, rows) or [])
    if not public:
        return False
    keys = public_columns(public)
    if len(keys) < 2:
        return False
    return any(_column_is_numeric(public, key) for key in keys)


def clip_include_chart(payload, rows=None):
    """File/bubble chart when the turn asked for a graphic view and series exist."""
    if not payload_allows_charts(payload):
        return False
    mode = payload_show_mode(payload)
    if mode not in _CHART_FILE_SHOW_MODES:
        return False
    return payload_has_chart_series(payload, rows)


def pdf_chart_series(rows, labels=None):
    """Category + 1–4 numeric series, or None. Shape only (no domain lexicon)."""
    public = public_rows(rows)
    if not public or len(public) < _PDF_CHART_MIN_ROWS:
        return None
    if len(public) > _PDF_CHART_MAX_CATS:
        return None
    keys = public_columns(public)
    if len(keys) < 2:
        return None
    cat_key = None
    for key in keys:
        if _is_chart_id_key(key):
            continue
        cat_key = key
        break
    if not cat_key:
        return None
    numeric = [
        key for key in keys
        if key != cat_key
        and not _is_chart_id_key(key)
        and _column_is_numeric(public, key)
    ][:_PDF_CHART_MAX_SERIES]
    if not numeric:
        return None
    categories = []
    raw_series = {key: [] for key in numeric}
    for row in public:
        cat = row.get(cat_key)
        if cat is None or str(cat).strip() == '':
            return None
        categories.append(str(cat).strip())
        for key in numeric:
            raw_series[key].append(coerce_chart_number(row.get(key)))
    labels = labels or {}
    series = []
    for key in numeric:
        values = raw_series[key]
        if all(val is None for val in values):
            continue
        series.append({
            'name': str(labels.get(key) or key),
            'values': [0.0 if val is None else val for val in values],
        })
    if not series:
        return None
    maxes = [max(abs(val) for val in item['values']) for item in series]
    peak = max(maxes) if maxes else 0.0
    if peak > 0:
        kept = []
        dropped_scale = False
        for item, magnitude in zip(series, maxes):
            if magnitude <= 0:
                continue
            ratio = peak / max(magnitude, 1e-9)
            if ratio <= _PDF_CHART_SCALE_RATIO:
                kept.append(item)
            else:
                dropped_scale = True
        if dropped_scale:
            return None
        series = kept
        if not series:
            return None
    return {
        'categories': categories,
        'series': series,
        'kind': 'line' if len(categories) >= 8 else 'bar',
    }
