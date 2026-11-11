# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Row colours: pastel palette, zebra, quartiles and the tint of a section."""

from .relaxaicode_render_columns import (
    _is_technical_link_key,
    _row_record_id,
)


# --- Soft pastel palette (row backgrounds) ---------------------------------
# Desaturated tones so black / red / blue / green text stays readable.
# Same family the chat uses for the "pyjama effect".
PASTEL_ROW_COLORS = (
    '#eef2f8',  # lavender mist
    '#fff9e8',  # soft yellow
    '#fff0e8',  # peach
    '#eaf6ee',  # mint
    '#e8f4f8',  # cyan mist
    '#f5f0e8',  # cream
    '#f3eef6',  # lilac
    '#eef6f3',  # sage
    '#f8efe8',  # warm sand
    '#e8eef6',  # powder blue
    '#f6f3e8',  # butter
    '#f0eef6',  # soft violet
)


# --- Quartile colouring (deterministic, server-side) -------------------
# The rule "colour sorted money columns by quartiles" is applied here in
# Python, not left to the LLM (which ignored it every time).
# Soft pastels (same family as PASTEL_ROW_COLORS); avoids loud colours.
_TIER_RED = '#f8eeee'    # worst / negative


_TIER_GREEN = '#eef6f0'  # middle


_TIER_BLUE = '#eef3f8'   # best


def apply_pajama_coloring(items, unique=True):
    """Give each dict in the list a soft pastel `_row_color`.

    unique=True: walks PASTEL_ROW_COLORS (pyjama with no repeated tone until
    the palette runs out; then it cycles). unique=False: two-tone zebra.
    Returns the same list (mutated) so it can be chained in RelaxAICode.
    """
    if not items:
        return items
    palette = PASTEL_ROW_COLORS
    n = len(palette)
    if n < 2:
        return items
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        if unique:
            it['_row_color'] = palette[i % n]
        else:
            it['_row_color'] = palette[0 if (i % 2 == 0) else 1]
    return items


# Subtle zebra (report / non-comparable tables): two very soft greys.
SUBTLE_ZEBRA_COLORS = (
    '#f7f8fa',  # near white
    '#eef1f5',  # soft grey-blue
)


def apply_subtle_zebra_coloring(items):
    """Two-tone grey zebra; overwrites existing `_row_color`."""
    if not items:
        return items
    a, b = SUBTLE_ZEBRA_COLORS
    for i, it in enumerate(items):
        if isinstance(it, dict):
            it['_row_color'] = a if (i % 2 == 0) else b
    return items


def _wants_subtle_zebra(result=None, render_context=None):
    """True when report/plain table path asked for subtle zebra (no quartiles)."""
    ctx = render_context or {}
    if ctx.get('subtle_zebra') or ctx.get('__subtle_zebra__') or ctx.get('plain_tables'):
        return True
    if isinstance(result, dict):
        if result.get('__subtle_zebra__') or result.get('plain_tables'):
            return True
        if result.get('subtle_zebra'):
            return True
    return False


def _normalize_tint_mode(value):
    """Map payload tint → ``quartile`` | ``zebra`` | ``none`` | None."""
    if value is None or value is False:
        return None
    if value is True:
        return 'quartile'
    v = str(value).strip().lower()
    if v in ('quartile', 'quartiles', 'tiers', 'tier'):
        return 'quartile'
    if v in ('zebra', 'subtle', 'subtle_zebra', 'pajama_soft', 'grey', 'gray'):
        return 'zebra'
    if v in ('none', 'off', 'false', '0', 'no'):
        return 'none'
    return None


def _resolve_tint_override(result=None, render_context=None, group_opts=None):
    """Explicit tint from group / context / result, else forced report zebra."""
    for src in (
        group_opts or {},
        render_context or {},
        result if isinstance(result, dict) else {},
    ):
        for key in ('tint', '__row_tint__', 'row_tint'):
            if key not in src or src.get(key) is None:
                continue
            mode = _normalize_tint_mode(src.get(key))
            if mode:
                return mode
    if _wants_subtle_zebra(result=result, render_context=render_context):
        return 'zebra'
    return None


def _has_explicit_row_colors(items):
    for it in items or []:
        if not isinstance(it, dict):
            continue
        if any(str(k).startswith(('_row_color', '_color_')) for k in it.keys()):
            return True
    return False


def _rows_are_records(items):
    """Every row is an Odoo record (``__model`` + id): peers of one model."""
    return bool(items) and all(
        isinstance(it, dict) and it.get('__model') and _row_record_id(it)
        for it in items
    )


def _numeric_column_keys(items):
    if not items or not isinstance(items[0], dict):
        return []
    keys = [k for k in items[0].keys() if not str(k).startswith('_')]
    out = []
    for key in keys:
        vals = [it.get(key) for it in items if isinstance(it, dict)]
        if sum(1 for v in vals if _is_number(v)) >= max(2, len(items) * 0.6):
            out.append(key)
    return out


def _is_kpi_card_shape(items):
    """True for 2-col label+value tables (a KPI card or a ranking: same shape).

    Structural shape only (column roles), never the column names.
    """
    if not items or not isinstance(items[0], dict):
        return False
    keys = [k for k in items[0].keys() if not str(k).startswith('_')]
    if len(keys) != 2:
        return False
    label_keys = []
    value_keys = []
    for key in keys:
        vals = [it.get(key) for it in items if isinstance(it, dict)]
        n_num = sum(1 for v in vals if _is_number(v))
        n_str = sum(
            1 for v in vals
            if isinstance(v, str) and str(v).strip() and not _is_number(v)
        )
        if n_num >= max(2, len(items) * 0.6):
            value_keys.append(key)
        elif n_str >= max(2, len(items) * 0.5):
            label_keys.append(key)
    return len(label_keys) == 1 and len(value_keys) == 1


def _tint_section_rows(items, result=None, render_context=None, group_opts=None):
    """Row tint: quartile tiers for comparable series, else subtle grey zebra.

    Priority: explicit ``tint`` / ``__row_tint__`` → report ``__subtle_zebra__``
    → auto (comparable → quartile, else zebra). Respects pre-set ``_row_color``
    in auto mode; forced zebra (report/override) overwrites.
    """
    items = [
        it for it in (items or [])
        if not (isinstance(it, dict) and it.get('_tfoot'))
    ]
    if not items:
        return
    mode = _resolve_tint_override(
        result=result, render_context=render_context, group_opts=group_opts,
    )
    try:
        if mode == 'none':
            return
        if mode == 'zebra':
            apply_subtle_zebra_coloring(items)
            return
        if mode == 'quartile':
            if not _has_explicit_row_colors(items):
                apply_quartile_coloring(items, asked=True)
                if not _has_explicit_row_colors(items):
                    apply_subtle_zebra_coloring(items)
            return
        # Auto (table mode): comparable ranking → quartiles; else grey zebra.
        if _has_explicit_row_colors(items):
            return
        if _is_comparable_series(items):
            apply_quartile_coloring(items)
            if not _has_explicit_row_colors(items):
                apply_subtle_zebra_coloring(items)
        else:
            apply_subtle_zebra_coloring(items)
    except Exception:
        pass


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _monotonic(seq):
    """True if the sequence is non-increasing or non-decreasing (sorted data)."""
    if len(seq) < 2:
        return False
    inc = all(seq[i] <= seq[i + 1] for i in range(len(seq) - 1))
    dec = all(seq[i] >= seq[i + 1] for i in range(len(seq) - 1))
    return inc or dec


def _quantile(sorted_vals, q):
    if not sorted_vals:
        return 0
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def _sorted_metric_key(items):
    """The only non-technical numeric column, when it is sorted; else None."""
    if not items or not isinstance(items[0], dict) or len(items) < 5:
        return None
    numeric = [k for k in _numeric_column_keys(items) if not _is_technical_link_key(k)]
    if len(numeric) != 1:
        return None
    key = numeric[0]
    seq = [it.get(key) for it in items if _is_number(it.get(key))]
    return key if len(seq) >= 5 and _monotonic(seq) else None


def _detect_metric_key(items):
    """Metric of a peer ranking, only when the shape leaves no doubt.

    A 2-col label+value table can be a KPI card or a ranking; only record rows
    (one model) settle it. Otherwise the author asks with ``__row_tint__``.
    """
    key = _sorted_metric_key(items)
    if key and _is_kpi_card_shape(items) and not _rows_are_records(items):
        return None
    return key


def _is_comparable_series(items):
    """True when rows look like a sortable peer ranking (quartile-worthy)."""
    if not items or len(items) < 5:
        return False
    if _has_explicit_row_colors(items):
        return False
    return _detect_metric_key(items) is not None


def apply_quartile_coloring(items, asked=False):
    """Inject _row_color by terciles on the sorted metric column.
    Keeps explicit colours already there (does not override what the user asks).
    ``asked``: the author asked for tiers, so a label+value table qualifies."""
    if not items or len(items) < 5:
        return
    if _has_explicit_row_colors(items):
        return
    key = _sorted_metric_key(items) if asked else _detect_metric_key(items)
    if not key:
        return
    vals = sorted(v for v in (it.get(key) for it in items) if _is_number(v))
    if len(vals) < 5:
        return
    q33 = _quantile(vals, 1 / 3.0)
    q66 = _quantile(vals, 2 / 3.0)
    for it in items:
        v = it.get(key)
        if not _is_number(v):
            continue
        if v < 0 or v < q33:
            it['_row_color'] = _TIER_RED
        elif v < q66:
            it['_row_color'] = _TIER_GREEN
        else:
            it['_row_color'] = _TIER_BLUE
