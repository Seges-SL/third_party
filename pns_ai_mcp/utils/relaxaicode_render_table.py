# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Cells and the HTML table: chart dataset, show mode and the table block."""

import html
import json

from .relaxaicode_render_base import (
    _B64_IMG_PREFIXES,
    _column_is_image,
    _flatten_cell_value,
    _fmt_date,
    _fmt_number,
    _IMG_STYLE,
    _is_coords_cell,
    _is_image_ref,
    _is_iso_date,
    _is_map_thumb,
    _largest_image_url,
)

from .relaxaicode_render_columns import (
    _column_has_decimals,
    _column_is_numeric,
    _name_cell_link_html,
    _parse_numeric,
    _record_form_url,
    _row_record_id,
    _select_name_link_keys,
    _style_is_inline_chip,
)

from .relaxaicode_render_geo import (
    _render_coords_cell,
    _render_map_thumb_cell,
    _table_display_keys,
)

from .relaxaicode_render_page import (
    _safe_title_bg,
)


def _render_cell(key, val, ctx, numeric_column=False, item=None):
    """HTML cell: numbers, dates, base64 images, images by URL/path
    (/web/image/...) and escaped text by default.
    URL images are clickable: they open the full version in a new tab.
    The column picked by ``_select_name_link_keys`` links to the record
    (even when numeric, e.g. ``id``)."""
    if _is_map_thumb(val):
        return _render_map_thumb_cell(val)
    if _is_coords_cell(val):
        return _render_coords_cell(val)
    val = _flatten_cell_value(val)
    d_sep = ctx.get('pk_decimal_sep', ',')
    t_sep = ctx.get('pk_thousands_sep', '.')
    name_links_on = True if not isinstance(ctx, dict) else ctx.get('name_links', True)
    link_keys = ctx.get('name_link_keys') if isinstance(ctx, dict) else None
    want_record_link = (
        name_links_on
        and item is not None
        and link_keys
        and key in link_keys
        and bool(_record_form_url(item))
        and not _style_is_inline_chip(
            item.get('_style_' + str(key)) if item else None,
        )
    )

    inherit_color = False
    if item is not None:
        _st = item.get('_style_' + str(key))
        if _st and 'color:' in str(_st):
            inherit_color = True

    def _as_record_link(text):
        if not want_record_link or text is None or text == '':
            return None
        return _name_cell_link_html(item, text, inherit_color=inherit_color)

    # Integers with no decimals (ids, counters); floats with the setting's digits
    # (by default, those of the company currency). bool goes to text.
    parsed = _parse_numeric(val)
    decimal_col = key in (ctx.get('decimal_keys') or ())
    if parsed is not None and (numeric_column or isinstance(val, (int, float))):
        number, is_float = parsed
        if decimal_col or is_float or isinstance(val, float):
            decimals = ctx.get('pk_float_decimals', 2)
        else:
            decimals = 0
        formatted = _fmt_number(number, d_sep, t_sep, decimals=decimals)
        linked = _as_record_link(formatted)
        if linked is not None:
            return linked
        return html.escape(formatted)
    if _is_iso_date(val):
        formatted = _fmt_date(val, ctx.get('pk_date_format', '%d/%m/%Y'))
        linked = _as_record_link(formatted)
        if linked is not None:
            return linked
        return html.escape(formatted)
    val_str = '' if val is None else str(val)
    clean = val_str[2:-1] if val_str.startswith(("b'", 'b"')) else val_str
    if len(clean) > 64:
        for prefix, mime in _B64_IMG_PREFIXES:
            if clean.startswith(prefix):
                return '<img src="data:image/%s;base64,%s" style="%s">' % (
                    mime, html.escape(clean, quote=True), _IMG_STYLE,
                )
    if _is_image_ref(clean):
        env = ctx.get('env') if isinstance(ctx, dict) else None
        full_url = _largest_image_url(clean, env)
        return (
            '<a href="%s" target="_blank" rel="noopener">'
            '<img src="%s" style="%s">'
            '</a>'
        ) % (html.escape(full_url, quote=True), html.escape(clean, quote=True), _IMG_STYLE)
    linked = _as_record_link(clean)
    if linked is not None:
        return linked
    return html.escape(val_str)


def _cell_sort_atom(val, numeric_column=False):
    """Raw value for ``data-ai-sort`` (number string or plain text)."""
    flat = _flatten_cell_value(val)
    parsed = _parse_numeric(flat)
    if parsed is not None and (
        numeric_column
        or isinstance(flat, (int, float)) and not isinstance(flat, bool)
    ):
        return str(parsed[0])
    if flat in (None, ''):
        return ''
    return str(flat)


def _render_table(items, ctx, caption=None, section_title=None, title_bg=None):
    """Build a single <table> (header + rows) for a list of dicts.
    Images (base64 and /web/image/...), row/cell colouring and locale
    number/date format. No wrapper or total: the caller adds those.

    ``section_title``: title row inside the ``<thead>`` (right on top of the
    columns; avoids the CSS gap between h3 and table).
    """
    hide = ()
    if isinstance(ctx, dict):
        hide = ctx.get('hide_columns') or ()
    keys = _table_display_keys(items, hide=hide)
    numeric_keys = {k for k in keys if _column_is_numeric(items, k)}
    # Record (model+id) ⇒ link in ONE existing cell. Never an icon widget
    # column: the id or another cell is enough (opt-out: __row_links__/links=False).
    name_links_on = ctx.get('name_links', True) if isinstance(ctx, dict) else True
    has_record_rows = any(
        isinstance(it, dict) and _row_record_id(it) and it.get('__model')
        for it in items
    )
    name_link_keys = set()
    if name_links_on and has_record_rows:
        name_link_keys = _select_name_link_keys(keys, items, numeric_keys)
    # Passed on to _render_cell without mutating the caller's ctx.
    if isinstance(ctx, dict):
        ctx = dict(ctx)
        ctx['name_link_keys'] = name_link_keys
        ctx['decimal_keys'] = {k for k in numeric_keys if _column_has_decimals(items, k)}
    parts = [
        '<table class="table table-bordered table-sm o_ai_data_table'
        '%s" style="width:100%%;margin:0;">'
        % (' o_ai_ficha_table' if section_title else '')
    ]
    if caption:
        parts.append(f'<caption class="h5">{caption}</caption>')
    parts.append('<thead>')
    if section_title:
        n = max(1, len(keys))
        safe_bg = _safe_title_bg(title_bg) or '#eef2f8'
        parts.append(
            '<tr class="o_ai_ficha_title">'
            '<th colspan="%d" style="background-color:%s;color:#1a1a1a;'
            'font-size:1.15rem;font-weight:700;line-height:1.3;'
            'text-align:start;text-transform:none;letter-spacing:0;'
            'padding:0.55em 0.75em;border-bottom:0;">%s</th></tr>'
            % (n, html.escape(safe_bg, quote=True), section_title)
        )
    parts.append('<tr>')
    for idx, key in enumerate(keys):
        classes = ['o_ai_th_sort']
        if key in numeric_keys:
            classes.extend(['o_ai_num', 'text-end'])
        parts.append(
            '<th class="%s" data-ai-sort-col="%d" aria-sort="none">%s</th>'
            % (
                html.escape(' '.join(classes), quote=True),
                idx,
                html.escape(str(key).replace('_', ' ').title()),
            )
        )
    parts.append('</tr></thead>')

    def _emit_rows(row_items, foot=False):
        bits = []
        for item in row_items:
            tr_attrs = ''
            row_class = item.get('_row_class')
            row_color = item.get('_row_color')
            if row_class:
                tr_attrs += ' class="%s"' % html.escape(
                    str(row_class), quote=True,
                )
            tr_style = ''
            if row_color:
                tr_style += 'background-color:%s;' % row_color
            if foot:
                tr_style += 'font-weight:700;border-top:2px solid #adb5bd;'
            if tr_style:
                tr_attrs += ' style="%s"' % html.escape(tr_style, quote=True)
            bits.append('<tr%s>' % tr_attrs)
            for key in keys:
                val = item.get(key, '')
                is_num = key in numeric_keys
                classes = []
                if is_num:
                    classes.append('o_ai_num')
                    classes.append('text-end')
                cell_class = item.get('_class_' + str(key))
                if cell_class:
                    classes.append(str(cell_class))
                td_attrs = ''
                if classes:
                    td_attrs += ' class="%s"' % html.escape(
                        ' '.join(classes), quote=True,
                    )
                style = ''
                cell_color = item.get('_color_' + str(key))
                if cell_color:
                    style += 'color:%s;' % cell_color
                cell_style = item.get('_style_' + str(key))
                inner_style = ''
                if cell_style:
                    if _style_is_inline_chip(cell_style):
                        inner_style = str(cell_style)
                    else:
                        style += str(cell_style)
                if style:
                    td_attrs += ' style="%s"' % html.escape(style, quote=True)
                sort_v = _cell_sort_atom(val, numeric_column=is_num)
                if sort_v != '':
                    td_attrs += ' data-ai-sort="%s"' % html.escape(
                        sort_v, quote=True,
                    )
                cell_title = item.get('_title_' + str(key))
                if cell_title not in (None, False, ''):
                    tip = html.escape(str(cell_title), quote=True)
                    if ' class="' in td_attrs:
                        td_attrs = td_attrs.replace(
                            ' class="', ' class="o_ai_tiptarget ', 1,
                        )
                    else:
                        td_attrs += ' class="o_ai_tiptarget"'
                    td_attrs += ' data-tip="%s"' % tip
                cell_html = _render_cell(
                    key, val, ctx, numeric_column=is_num, item=item,
                )
                if inner_style:
                    cell_html = '<span style="%s">%s</span>' % (
                        html.escape(inner_style, quote=True),
                        cell_html,
                    )
                bits.append('<td%s>%s</td>' % (td_attrs, cell_html))
            bits.append('</tr>')
        return bits

    body_items = []
    foot_items = []
    for item in items:
        if isinstance(item, dict) and item.get('_tfoot'):
            foot_items.append(item)
        else:
            body_items.append(item)
    parts.append('<tbody>')
    parts.extend(_emit_rows(body_items))
    parts.append('</tbody>')
    if foot_items:
        parts.append('<tfoot>')
        parts.extend(_emit_rows(foot_items, foot=True))
        parts.append('</tfoot>')
    parts.append('</table>')
    return ''.join(parts)


def _json_safe_cell(val):
    """JSON-serializable value for data-ai-dataset (no base64, no objects)."""
    if val is None or isinstance(val, (bool, int, float)):
        return val
    if isinstance(val, str):
        # Base64 / long blobs: useless for Chart.js and they bloat the HTML.
        if len(val) > 256:
            for prefix, _mime in _B64_IMG_PREFIXES:
                if val.startswith(prefix) or (
                    val.startswith(("b'", 'b"')) and len(val) > 70
                    and val[2:-1].startswith(prefix)
                ):
                    return None
            if val.startswith('/web/image/') or 'base64' in val[:40].lower():
                return None
            return val[:256]
        return val
    if isinstance(val, (list, dict)):
        try:
            json.dumps(val, ensure_ascii=False, default=str)
            return val
        except (TypeError, ValueError):
            return str(val)[:256]
    try:
        if hasattr(val, 'isoformat'):
            return val.isoformat()
    except Exception:
        pass
    try:
        return float(val)
    except (TypeError, ValueError):
        return str(val)[:256]


def _chart_dataset_rows(items):
    """Rows sanitized for charts: no _… keys, id, __model or image columns."""
    if not items or not isinstance(items[0], dict):
        return []
    skip = {'id', '__model'}
    keys = [
        k for k in items[0].keys()
        if not str(k).startswith('_')
        and str(k) not in skip
        and not _column_is_image(items, k)
    ]
    if not keys:
        return []
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        row = {}
        for key in keys:
            safe = _json_safe_cell(item.get(key))
            if safe is not None:
                row[str(key)] = safe
        if item.get('_tfoot'):
            row['_tfoot'] = True
        if row:
            rows.append(row)
    return rows


_VALID_SHOW_MODES = frozenset({
    'show-table', 'show-chart', 'dashboard', 'table',
    'table-chart', 'chart-table',
})


_VALID_CHART_ENGINES = frozenset({'echarts', 'chartjs'})


def _normalize_show_mode_value(value, default='show-table'):
    """Normalize show_mode with optional presentation_mode import."""
    try:
        from .presentation_mode import normalize_show_mode
        return normalize_show_mode(value or default)
    except Exception:
        val = str(value or default).strip().lower()
        val = {
            'table-chart': 'show-table',
            'chart-table': 'show-chart',
        }.get(val, val)
        return val if val in _VALID_SHOW_MODES else default


def _charts_enabled(render_context=None, result=None):
    """False ⇒ no data-ai-dataset / no chart toolbar."""
    ctx = render_context or {}
    if ctx.get('charts') is False or ctx.get('__no_charts__') is True:
        return False
    sm = _normalize_show_mode_value(
        ctx.get('show_mode') or ctx.get('showmode'),
    )
    if sm == 'table':
        return False
    if isinstance(result, dict):
        if result.get('charts') is False or result.get('__no_charts__') is True:
            return False
        rsm = result.get('show_mode') or result.get('showmode')
        if rsm and _normalize_show_mode_value(rsm) == 'table':
            return False
    return True


def _normalize_chart_engine_value(value, default='echarts'):
    """Normalize chart engine with optional presentation_mode import."""
    try:
        from .presentation_mode import normalize_chart_engine
        return normalize_chart_engine(value or default)
    except Exception:
        val = str(value or default).strip().lower()
        return val if val in _VALID_CHART_ENGINES else default


def _dual_axis_attr(value):
    """HTML fragment for data-ai-dual-axis, or empty when auto."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return ' data-ai-dual-axis="%s"' % ('1' if value else '0')
    try:
        from .presentation_mode import normalize_dual_axis
        normalized = normalize_dual_axis(value)
    except Exception:
        normalized = None
        val = str(value).strip().lower()
        if val in ('0', 'false', 'off', 'single', 'one', 'no'):
            normalized = False
        elif val in ('1', 'true', 'on', 'dual', 'two', 'yes'):
            normalized = True
    if normalized is None:
        return ''
    return ' data-ai-dual-axis="%s"' % ('1' if normalized else '0')


def _table_block_attrs(show_mode, chart_engine, dataset_attr='', dual_axis=None):
    sm = html.escape(show_mode, quote=True)
    ce = html.escape(chart_engine, quote=True)
    da = _dual_axis_attr(dual_axis)
    if dataset_attr:
        return (
            '<div class="o_ai_table_block" %s '
            'data-ai-show-mode="%s" data-ai-chart-engine="%s"%s>'
            % (dataset_attr, sm, ce, da)
        )
    return (
        '<div class="o_ai_table_block" data-ai-show-mode="%s" '
        'data-ai-chart-engine="%s"%s>'
        % (sm, ce, da)
    )


def _table_block_open(items, render_context=None):
    """Open a wrapper with data-ai-dataset (escaped JSON) for client-side charts."""
    ctx = render_context or {}
    show_mode = _normalize_show_mode_value(
        ctx.get('show_mode') or ctx.get('showmode'),
    )
    chart_engine = _normalize_chart_engine_value(ctx.get('chart_engine'))
    dual_axis = ctx.get('dual_axis')
    if dual_axis is None and 'dualAxis' in ctx:
        dual_axis = ctx.get('dualAxis')
    if not _charts_enabled(ctx):
        return _table_block_attrs(show_mode, chart_engine, dual_axis=dual_axis)
    rows = _chart_dataset_rows(items)
    if not rows:
        return _table_block_attrs(show_mode, chart_engine, dual_axis=dual_axis)
    try:
        payload = json.dumps(rows, ensure_ascii=False, separators=(',', ':'), default=str)
    except (TypeError, ValueError):
        return _table_block_attrs(show_mode, chart_engine, dual_axis=dual_axis)
    dataset_attr = 'data-ai-dataset="%s"' % html.escape(payload, quote=True)
    return _table_block_attrs(
        show_mode, chart_engine, dataset_attr=dataset_attr, dual_axis=dual_axis,
    )
