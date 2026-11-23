# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""HTML rendering of relaxaicode results (pure Python, no extra packages)."""

import html
import logging
import re

from .relaxaicode_render_base import (
    _flatten_cell_value,
    _fmt_number,
    format_amount,
    format_number,
    _has_image_columns,
    is_tabulable,
    _largest_image_url,
    page_url_on_result,
    _paints,
    render_context_from_env,
    _result_groups,
    _result_items,
    _sibling_tabular_lists,
    _t,
)

from .relaxaicode_render_columns import (
    _column_has_decimals,
    _column_is_numeric,
    _parse_numeric,
    row_label_for_record,
    _select_name_link_keys,
)

from .relaxaicode_render_geo import (
    _geo_hide_column_keys,
    _is_provider_badge_alt,
    _map_banner_card_html,
    _render_coords_cell,
    _render_map_thumb_cell,
    _result_map_banner_html,
    _strip_unsolicited_row_geo,
    _table_display_keys,
)

from .relaxaicode_render_tint import (
    apply_pajama_coloring,
    _is_comparable_series,
    PASTEL_ROW_COLORS,
    SUBTLE_ZEBRA_COLORS,
    _TIER_BLUE,
    _TIER_GREEN,
    _TIER_RED,
    _tint_section_rows,
    _wants_subtle_zebra,
)

from .relaxaicode_render_page import (
    _markdownish_to_html,
    _result_page_html,
)

from .relaxaicode_render_table import (
    _chart_dataset_rows,
    _normalize_show_mode_value,
    _render_cell,
    _render_table,
    _table_block_open,
)

from .relaxaicode_render_groups import (
    fallback_table_html,
    grouped_dashboard_html,
    grouped_table_html,
)

from .relaxaicode_render_cards import (
    collect_svg_cards,
    render_svg_cards_html,
)

_logger = logging.getLogger(__name__)


@_paints
def render_result_html(result, summary='', render_context=None):
    """Render the result to HTML with the Python renderer (server-side)."""
    if isinstance(result, list):
        result = {'data': result}
    if not isinstance(result, dict):
        return None
    if result.get('formatted_text'):
        return result['formatted_text']
    _strip_unsolicited_row_geo(result)

    render_context = dict(render_context or {})
    hide_cols = result.get('__hide_columns__')
    if hide_cols:
        render_context['hide_columns'] = list(hide_cols)

    # dual_axis from the result if the caller did not put it in the context.
    if render_context.get('dual_axis') is None:
        if 'dual_axis' in result:
            render_context['dual_axis'] = result.get('dual_axis')
        elif 'dualAxis' in result:
            render_context['dual_axis'] = result.get('dualAxis')

    # Chart opt-out: does not override a dashboard (draggable cards).
    if (result.get('show_mode') or result.get('showmode')):
        render_context.setdefault(
            'show_mode',
            result.get('show_mode') or result.get('showmode'),
        )
    if result.get('charts') is False or result.get('__no_charts__') is True:
        render_context['charts'] = False
        render_context['__no_charts__'] = True
        sm = _normalize_show_mode_value(
            render_context.get('show_mode') or result.get('show_mode'),
        )
        if sm != 'dashboard':
            render_context['show_mode'] = 'table'

    # Report auxiliary tables: subtle zebra, never quartile tiers.
    if _wants_subtle_zebra(result=result, render_context=render_context):
        render_context['subtle_zebra'] = True
        render_context['__subtle_zebra__'] = True

    # Link to the record in a cell: ON by default when there is model+id.
    # Opt-out: result['__row_links__']=False / links=False / __name_links__=False
    # (clean table to copy/export). There is no icon widget column.
    if render_context.get('row_links') is None:
        _rl = result.get('__row_links__')
        if _rl is None:
            _rl = result.get('links')
        render_context['row_links'] = (_rl is not False)
    if render_context.get('name_links') is None:
        _nl = result.get('__name_links__')
        if _nl is None:
            _nl = result.get('name_links')
        if render_context.get('row_links') is False:
            render_context['name_links'] = False
        else:
            render_context['name_links'] = (_nl is not False)

    # Dashboard (movable cards): only if show_mode=dashboard and there are groups.
    grouped = grouped_dashboard_html(result, summary, render_context=render_context)
    if grouped:
        return grouped

    # Vertical grouped structure (title→table per group).
    grouped = grouped_table_html(result, summary, render_context=render_context)
    if grouped:
        return grouped

    items = _result_items(result)
    if items:
        _tint_section_rows(items, result=result, render_context=render_context)

    # Server-side render in pure Python (the only path). Images (base64 and
    # /web/image/...), row tinting and number/date formatting in the locale.
    # Works the same on any instance, with no external dependencies.
    return fallback_table_html(result, summary, render_context=render_context)


@_paints
def maybe_attach_formatted_text(result, summary='', render_context=None, force=False):
    """Add formatted_text to the result dict when it applies. Returns True if it rendered."""
    if not isinstance(result, dict) or result.get('error'):
        return False
    if page_url_on_result(result):
        # A page or map in its own tab: the bubble is the card, like Geo.
        # Discovery is not required; the url on the result is enough.
        rendered = _result_page_html(result) or ''
        if rendered:
            result['formatted_text'] = rendered
            result['__fmt_type__'] = 'server_side_python'
            result['__phase__'] = 'presentation'
            result['__presentation_complete__'] = True
            result['__satisfied__'] = True
            result['__return_direct__'] = True
            result['__stop_after_direct__'] = True
            result['__page_only__'] = True
            result.pop('__records__', None)
            return True
    card_html = render_svg_cards_html(result, render_context=render_context)
    existing = result.get('formatted_text')
    if existing:
        if card_html and 'data-ai-card' not in existing:
            result['formatted_text'] = card_html + existing
            return True
        return False
    _strip_unsolicited_row_geo(result)
    table_ok = is_tabulable(result, force=force)
    rendered = ''
    if table_ok:
        rendered = render_result_html(
            result, summary=summary, render_context=render_context,
        ) or ''
    page_only = False
    if not rendered and page_url_on_result(result):
        rendered = _result_page_html(result) or ''
        page_only = bool(rendered)
    if not rendered and not card_html:
        return False
    result['formatted_text'] = (card_html or '') + (rendered or '')
    result['__fmt_type__'] = 'server_side_python'
    result.pop('__records__', None)
    only_cards = bool(card_html) and not rendered
    if force or only_cards or page_only:
        result['__phase__'] = 'presentation'
        result['__presentation_complete__'] = True
        result['__satisfied__'] = True
        result['__return_direct__'] = True
    else:
        # Table for the LLM context (tool JSON), not for the chat bubble.
        result.setdefault('__phase__', 'extraction')
        result.pop('__return_direct__', None)
        result.pop('__direct_return__', None)
        result.pop('__return_direct_to_user__', None)
    _logger.info(
        'relaxaicode_render: HTML generated (%s chars, force=%s, user_facing=%s, cards=%s)',
        len(result['formatted_text']), force, force or only_cards, bool(card_html),
    )
    return True


def _image_link_href(url, env=None):
    """URL to open the image in a new tab. None if it cannot be opened (e.g. data:)."""
    if not url or url.startswith('data:'):
        return None
    if url.startswith('/web/image/'):
        return _largest_image_url(url, env)
    if url.startswith('http') or url.startswith('/'):
        return url
    return None


def wrap_bare_images_clickable(html_content, env=None):
    """Wrap loose <img> tags in target=_blank links. Skips data: URIs and imgs already linked."""
    if not html_content or '<img' not in html_content:
        return html_content
    title = html.escape(_t('View full image', env), quote=True)

    def _wrap(m):
        img_tag = m.group(1)
        if re.search(r'<a\s[^>]*>\s*$', html_content[:m.start()]):
            return img_tag
        src_match = re.search(r'src=["\']([^"\']+)["\']', img_tag)
        if not src_match:
            return img_tag
        href = _image_link_href(src_match.group(1), env)
        if not href:
            return img_tag
        return (
            '<a href="%s" target="_blank" rel="noopener" title="%s">'
            '%s</a>'
        ) % (html.escape(href, quote=True), title, img_tag)

    out = re.sub(r'(<img\s[^>]*>)', _wrap, html_content)
    out = re.sub(
        r'(<a\s[^>]*>)\s*<a\s[^>]*>(<img\s[^>]*>)</a>',
        r'\1\2',
        out,
    )
    return out


@_paints
def render_for_direct_return(result, summary='', render_context=None):
    """HTML for direct return to the chat (without mutating result)."""
    if not isinstance(result, dict):
        return None
    if result.get('formatted_text'):
        return result['formatted_text']
    force = bool(
        result.get('__return_direct__')
        or result.get('__return_direct_to_user__')
        or result.get('direct_return')
    )
    if not is_tabulable(result, force=force):
        return None
    return render_result_html(
        result,
        summary=summary or result.get('summary') or '',
        render_context=render_context,
    )
