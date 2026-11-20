# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Around the table: result page link, titles, notices, markdown-like text and footer."""

import html
import re

from .relaxaicode_render_base import (
    page_url_on_result,
    _t,
)

from .relaxaicode_render_geo import (
    _result_map_banner_html,
)


def _result_footer_text(result):
    """Optional human footer under the table (comparison, warm closing, …)."""
    if not isinstance(result, dict):
        return ''
    for key in ('footer', 'footer_md', 'pie'):
        val = result.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ''


def _result_page_link_html(result):
    """The page as a card. The chat shows it; the click opens the tab."""
    href = page_url_on_result(result)
    if not href:
        return ''
    label = result.get('title') or result.get('summary') or _t('Open')
    safe_href = html.escape(href, quote=True)
    safe_label = html.escape(str(label))
    icon = (
        '<svg class="o_ai_page_link_icon" viewBox="0 0 48 48" '
        'aria-hidden="true" focusable="false">'
        '<rect x="8" y="12" width="22" height="28" rx="2" fill="#fff" '
        'stroke="#5b6b7a" stroke-width="2"/>'
        '<rect x="16" y="8" width="22" height="28" rx="2" fill="#eef3fa" '
        'stroke="#0d6efd" stroke-width="2"/>'
        '</svg>'
    )
    return (
        '<div class="o_ai_page_link">'
        '<a class="o_ai_page_link_card" href="%s" target="_blank" '
        'rel="noopener noreferrer" title="%s">'
        '<span class="o_ai_page_link_preview" aria-hidden="true">%s</span>'
        '<span class="o_ai_page_link_meta">'
        '<span class="o_ai_page_link_title">%s</span>'
        '<span class="o_ai_page_link_cta">%s '
        '<i class="fa fa-external-link" aria-hidden="true"></i></span>'
        '</span></a></div>'
        % (safe_href, safe_label, icon, safe_label, html.escape(_t('Open')))
    )


def _result_page_html(result):
    """One painter for a result that is also a page.

    A map address gets the map card; anything else gets the link. A module
    that publishes a page only sets ``page_url``; nothing here names it.
    """
    return (
        _result_map_banner_html(result if isinstance(result, dict) else {})
        or _result_page_link_html(result if isinstance(result, dict) else {})
    )


def _title_html(title):
    """Title above the grid, more prominent than the footer."""
    if not title:
        return ''
    return (
        '<h3 class="pns-result-title o_ai_result_title" '
        'style="margin:0;font-size:1.65rem;font-weight:700;'
        'line-height:1.2;color:#1a1a1a;">%s</h3>' % title
    )


def _safe_title_bg(bg):
    """Optional pastel hex for the block header (`title_bg` / `header_bg`)."""
    if not bg:
        return ''
    s = str(bg).strip()
    if re.fullmatch(r'#[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?([0-9A-Fa-f]{2})?', s):
        return s
    return ''


def _block_title_html(title, bg=None):
    """Title shared by chart + table (first child of table_block)."""
    if not title:
        return ''
    # CSS (.o_ai_titled_block) controls margin/radius to join title+table.
    style = (
        'margin:0;font-size:1.15rem;font-weight:700;'
        'line-height:1.3;color:#1a1a1a;'
    )
    safe_bg = _safe_title_bg(bg)
    if safe_bg:
        style += (
            'background-color:%s;padding:0.55em 0.75em;'
            % html.escape(safe_bg, quote=True)
        )
    return (
        '<h3 class="pns-result-title o_ai_block_title" '
        'style="%s">%s</h3>' % (style, title)
    )


def _markdownish_to_html(text):
    """Light markdown → report HTML (headings, lists, bold, paragraphs).

    No raw HTML from the LLM: everything is escaped and only known marks apply.
    """
    if not text:
        return ''
    lines = str(text).replace('\r\n', '\n').replace('\r', '\n').split('\n')
    parts = []
    para = []

    def _inline(s):
        escaped = html.escape(s)
        return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', escaped)

    def _flush_para():
        if not para:
            return
        joined = _inline(' '.join(para))
        parts.append(
            '<p class="o_ai_prose_p" style="margin:0.45em 0;line-height:1.5;">'
            '%s</p>' % joined
        )
        para.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            _flush_para()
            continue
        hm = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if hm:
            _flush_para()
            level = min(len(hm.group(1)), 4)
            parts.append(
                '<h%d class="o_ai_prose_h" style="margin:0.85em 0 0.35em 0;'
                'font-weight:700;line-height:1.3;color:#1a1a1a;">%s</h%d>'
                % (level, _inline(hm.group(2)), level)
            )
            continue
        lm = re.match(r'^[-*•]\s+(.+)$', stripped)
        if lm:
            _flush_para()
            parts.append(
                '<p class="o_ai_prose_li" style="margin:0.2em 0 0.2em 0.85em;'
                'line-height:1.45;">• %s</p>' % _inline(lm.group(1))
            )
            continue
        om = re.match(r'^(\d+)\.\s+(.+)$', stripped)
        if om:
            _flush_para()
            parts.append(
                '<p class="o_ai_prose_li" style="margin:0.2em 0 0.2em 0.85em;'
                'line-height:1.45;">%s. %s</p>'
                % (html.escape(om.group(1)), _inline(om.group(2)))
            )
            continue
        para.append(stripped)
    _flush_para()
    return ''.join(parts)


def _result_notices_html(result):
    """Soft notice (geocode miss, etc.): it does not cut the result."""
    if not isinstance(result, dict):
        return ''
    raw = result.get('notices')
    if raw is None:
        raw = result.get('warnings')
    if raw is None and result.get('notice'):
        raw = [result.get('notice')]
    if isinstance(raw, str):
        items = [raw.strip()] if raw.strip() else []
    elif isinstance(raw, (list, tuple)):
        items = [str(x).strip() for x in raw if x not in (None, False, '')]
    else:
        items = []
    # Deduplicate preserving order
    seen = set()
    uniq = []
    for msg in items:
        if msg in seen:
            continue
        seen.add(msg)
        uniq.append(msg)
    if not uniq:
        return ''
    lis = ''.join(
        '<li>%s</li>' % html.escape(m) for m in uniq
    )
    return (
        '<div class="alert alert-warning o_ai_geo_notice" role="status" '
        'style="margin:0.75em 0;padding:0.65em 0.9em;border-radius:4px;'
        'border:1px solid #f0d48a;background:#fff8e6;color:#5c4a1a;'
        'font-size:0.92rem;line-height:1.4;">'
        '<strong>%s</strong><ul style="margin:0.35em 0 0 1.1em;padding:0;">'
        '%s</ul></div>'
    ) % (html.escape(_t('Notice')), lis)


def _footer_html(result):
    raw = _result_footer_text(result)
    # If footer is a __map_thumb__, the banner already paints it; do not duplicate.
    if isinstance(result, dict) and isinstance(result.get('footer'), dict):
        raw = ''
    if not raw:
        return ''
    return (
        '<div class="pns-result-footer o_ai_prose" style="margin:0.85em 0 0.25em 0;'
        'padding:0.55em 0.75em;background:#f4f7fa;border-radius:4px;'
        'border:1px solid #dde5ec;line-height:1.45;font-size:0.92rem;'
        'color:#334;">%s</div>'
        % _markdownish_to_html(raw)
    )
