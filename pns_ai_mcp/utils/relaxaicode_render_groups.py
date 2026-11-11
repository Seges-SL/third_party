# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Several tables in one result: fallback table, grouped tables and the dashboard."""

import html
import re

from .relaxaicode_render_base import (
    _paints,
    _result_groups,
    _result_items,
    _t,
)

from .relaxaicode_render_tint import (
    _tint_section_rows,
)

from .relaxaicode_render_page import (
    _block_title_html,
    _footer_html,
    _result_notices_html,
    _result_page_html,
    _title_html,
)

from .relaxaicode_render_table import (
    _normalize_chart_engine_value,
    _normalize_show_mode_value,
    _render_table,
    _table_block_open,
)


def _record_count(items):
    """Rows that are records: a ``_tfoot`` totals row is not one."""
    return sum(
        1 for it in (items or [])
        if not (isinstance(it, dict) and it.get('_tfoot'))
    )


@_paints
def fallback_table_html(result, summary='', render_context=None):
    """Pure-Python HTML renderer for ONE flat table."""
    items = _result_items(result)
    if not items:
        return _result_page_html(result) or None
    ctx = render_context or {}
    # Do not put long map URLs in the title (they get escaped and are not clickable).
    raw_title = (
        summary
        or (result.get('title') if isinstance(result, dict) else '')
        or (result.get('summary') if isinstance(result, dict) else '')
        or ''
    )
    if isinstance(raw_title, str) and 'http' in raw_title:
        # Strip the raw URL from the title; the map_url banner shows it properly.
        raw_title = re.sub(r'https?://\S+', '', raw_title).strip(' .;:—-')
    title = html.escape(raw_title)
    parts = [
        _table_block_open(items, render_context=ctx),
        _block_title_html(title),
        _result_notices_html(result if isinstance(result, dict) else {}),
        _result_page_html(result),
        '<div class="table-responsive" style="margin:1em 0;">',
        _render_table(items, ctx, caption=None),
        '<p class="text-muted small"><strong>%s</strong></p>' % html.escape(
            _t('Total: %d records') % _record_count(items),
        ),
        _footer_html(result),
        '</div>',
        '</div>',
    ]
    return ''.join(parts)


def _dashboard_id(result, sections):
    """Stable id for client-side layout persistence."""
    import hashlib
    parts = [str((result or {}).get('summary') or '')]
    for title, _items, *_rest in sections:
        parts.append(str(title or ''))
    raw = '|'.join(parts).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()[:16]


def _dashboard_card_id(index, title):
    slug = re.sub(r'[^a-z0-9]+', '-', (title or '').lower()).strip('-')[:36]
    return 'c%d-%s' % (index, slug or 'block')


@_paints
def grouped_dashboard_html(result, summary='', render_context=None):
    """Dashboard layout: draggable/closable cards over grouped tables/charts."""
    sections = _result_groups(result)
    if not sections:
        return None
    ctx = dict(render_context or {})
    outer_mode = _normalize_show_mode_value(
        ctx.get('show_mode') or ctx.get('showmode'),
    )
    if outer_mode != 'dashboard':
        return None

    chart_engine = _normalize_chart_engine_value(ctx.get('chart_engine'))
    dash_id = (result.get('dashboard_id') if isinstance(result, dict) else None)
    if not dash_id:
        dash_id = _dashboard_id(result, sections)

    restore_label = _t('Restore')

    parts = [
        '<div class="o_ai_dashboard" data-ai-dashboard-id="%s" '
        'data-ai-show-mode="dashboard" '
        'data-ai-chart-engine="%s">' % (
            html.escape(str(dash_id), quote=True),
            html.escape(chart_engine, quote=True),
        ),
        '<div class="o_ai_dashboard_toolbar o_ai_noexport">',
        '<button type="button" class="btn btn-sm btn-link o_ai_dashboard_reset" '
        'title="%s">%s</button>' % (
            html.escape(restore_label, quote=True),
            html.escape(restore_label),
        ),
        '</div>',
        '<div class="o_ai_dashboard_grid">',
    ]
    top = html.escape(
        summary or (result.get('summary') if isinstance(result, dict) else '') or '',
    )
    if top:
        parts.insert(
            1,
            '<h3 class="pns-result-title o_ai_dashboard_title">%s</h3>' % top,
        )
    # Multi-point banner at root level (also in the grouped dashboard).
    banner = _result_page_html(result)
    if banner:
        # After the title (index 1) or at the start of the content if there is no title.
        parts.insert(2 if top else 1, banner)

    grand_total = 0
    for index, section in enumerate(sections):
        title, items = section[0], section[1]
        opts = section[2] if len(section) > 2 else {}
        card_block_mode = 'show-chart'
        _tint_section_rows(
            items,
            result=result,
            render_context=render_context,
            group_opts=opts,
        )
        card_id = _dashboard_card_id(index, title)
        span = 1
        raw_groups = result.get('groups') if isinstance(result, dict) else None
        if isinstance(raw_groups, list) and index < len(raw_groups):
            grp = raw_groups[index]
            if isinstance(grp, dict):
                try:
                    span = int(grp.get('span') or grp.get('cols') or 1)
                except (TypeError, ValueError):
                    span = 1
                grp_mode = grp.get('show_mode') or grp.get('showmode')
                if grp_mode:
                    card_block_mode = _normalize_show_mode_value(
                        grp_mode, default=card_block_mode,
                    )
        span = max(1, min(span, 2))
        span_cls = (
            ' o_ai_dashboard_card_span2' if span >= 2 else ''
        )
        safe_title = html.escape(title or (_t('Block %d') % (index + 1)))
        parts.append(
            '<div class="o_ai_dashboard_card%s" data-card-id="%s">' % (
                span_cls, html.escape(card_id, quote=True),
            )
        )
        parts.append('<div class="o_ai_dashboard_card_header">')
        parts.append(
            '<span class="o_ai_dashboard_drag" aria-hidden="true" '
            'title="%s">&#8942;&#8942;</span>' % html.escape(_t('Drag'), quote=True)
        )
        parts.append('<span class="o_ai_dashboard_card_title">%s</span>' % safe_title)
        parts.append('<div class="o_ai_dashboard_card_actions">')
        # Classic MDI order: minimize · maximize/restore · close.
        # The JS fills in geometric icons; the HTML leaves accessible titles.
        for kind, expanded, label in (
            ('collapse', ' aria-expanded="true"', _t('Minimize')),
            ('maximize', ' aria-expanded="false"', _t('Maximize')),
            ('close', '', _t('Close')),
        ):
            safe_label = html.escape(label, quote=True)
            parts.append(
                '<button type="button" class="o_ai_dashboard_winbtn '
                'o_ai_dashboard_%s"%s title="%s" aria-label="%s"></button>'
                % (kind, expanded, safe_label, safe_label)
            )
        parts.append('</div></div>')
        parts.append('<div class="o_ai_dashboard_card_body">')
        card_ctx = dict(ctx)
        card_ctx['show_mode'] = card_block_mode
        parts.append(_table_block_open(items, render_context=card_ctx))
        map_payload = (opts or {}).get('map_payload')
        if map_payload:
            parts.append(_result_page_html(map_payload))
        parts.append('<div class="table-responsive">')
        if items:
            parts.append(_render_table(items, card_ctx))
        parts.append('</div></div></div></div>')
        grand_total += _record_count(items)
    parts.append('</div>')
    parts.append(
        '<p class="text-muted small o_ai_dashboard_footer">'
        '<strong>%s</strong></p>' % html.escape(
            _t('%(records)d records · %(cards)d cards') % {
                'records': grand_total, 'cards': len(sections),
            },
        )
    )
    parts.append(_footer_html(result))
    parts.append('</div>')
    return ''.join(parts)


@_paints
def grouped_table_html(result, summary='', render_context=None):
    """Render the repeated «title → table» pattern for each group."""
    sections = _result_groups(result)
    if not sections:
        return None
    ctx = render_context or {}
    parts = ['<div class="o_ai_grouped_result" style="margin:0.25em 0 1em 0;">']
    top = html.escape(summary or (result.get('title') if isinstance(result, dict) else '') or '')
    if top:
        parts.append(_title_html(top))
    parts.append(_result_notices_html(result if isinstance(result, dict) else {}))
    # Root integral map (only if the root itself carries map_*).
    # Per-section maps (turn presentation basket) are rendered inside the loop.
    parts.append(_result_page_html(result))
    grand_total = 0
    for section in sections:
        title, items = section[0], section[1]
        opts = section[2] if len(section) > 2 else {}
        _tint_section_rows(
            items, result=result, render_context=ctx, group_opts=opts,
        )
        block_open = _table_block_open(items, render_context=ctx)
        if title:
            block_open = block_open.replace(
                'class="o_ai_table_block"',
                'class="o_ai_table_block o_ai_titled_block"',
                1,
            )
        parts.append(block_open)
        map_payload = (opts or {}).get('map_payload')
        if map_payload:
            parts.append(_result_page_html(map_payload))
        # Title inside the <thead> ⇒ no gap with the column header.
        parts.append('<div class="table-responsive o_ai_ficha">')
        if items:
            parts.append(_render_table(
                items,
                ctx,
                section_title=html.escape(title) if title else None,
                title_bg=(opts or {}).get('title_bg') if title else None,
            ))
        elif title:
            parts.append(
                '<div class="o_ai_ficha_title" style="padding:0.55em 0.75em;'
                'font-weight:700;">%s</div>' % html.escape(title)
            )
        parts.append('</div>')
        parts.append('</div>')
        grand_total += _record_count(items)
    parts.append(
        '<p class="text-muted small"><strong>%s</strong></p>' % html.escape(
            _t('Total: %(records)d records · %(groups)d groups') % {
                'records': grand_total, 'groups': len(sections),
            },
        )
    )
    parts.append(_footer_html(result))
    parts.append('</div>')
    return ''.join(parts)
