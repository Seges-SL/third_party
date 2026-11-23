# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Engine markup renamed from ``data-chatboo-*`` / ``o_chatboo_*`` to ``data-ai-*`` / ``o_ai_*``.

A host that stores engine HTML (chat messages, pages) renames its own column
from ``Model.init()``: Odoo 14 does not run ``migrations/3.1.*``. A row
already renamed no longer matches, so a later ``-u`` touches nothing.
Classes a host adds for its own state (``o_chatboo_dashboard_card_collapsed``)
are longer names and are left alone.
"""

ENGINE_MARKUP = (
    'card', 'chart-engine', 'dashboard-id', 'dataset',
    'dual-axis', 'show-mode', 'sort-col', 'sort',
)
OLD_PREFIX = 'data-chatboo-'
NEW_PREFIX = 'data-ai-'

# The engine wrote ``showmode`` for a few hours on 2026-07-29 before ``show-mode``.
RENAMED = tuple(
    (OLD_PREFIX + name + '=', NEW_PREFIX + name + '=') for name in ENGINE_MARKUP
) + ((OLD_PREFIX + 'showmode=', NEW_PREFIX + 'show-mode='),)

# Class names the engine wrote as ``o_chatboo_<name>`` up to 2026-10-18.
ENGINE_CLASSES = (
    'block_title', 'cell_copy', 'chart_host', 'chart_toolbar', 'coords',
    'coords_link', 'coords_text', 'copy_btn', 'dashboard', 'dashboard_card',
    'dashboard_card_actions', 'dashboard_card_body', 'dashboard_card_header',
    'dashboard_card_span2', 'dashboard_card_title', 'dashboard_close',
    'dashboard_collapse', 'dashboard_drag', 'dashboard_footer', 'dashboard_grid',
    'dashboard_maximize', 'dashboard_reset', 'dashboard_title', 'dashboard_toolbar',
    'dashboard_winbtn', 'data_table', 'echarts_surface', 'export_bar', 'ficha',
    'ficha_table', 'ficha_title', 'geo_notice', 'grouped_result', 'link_banner',
    'link_banner_card', 'link_banner_cta', 'link_banner_host', 'link_banner_mark',
    'link_banner_meta', 'link_banner_preview', 'link_banner_title', 'local_footer',
    'map', 'map_banner', 'map_banner_card', 'map_banner_count', 'map_banner_cta',
    'map_banner_gm', 'map_banner_meta', 'map_banner_osm', 'map_banner_pins',
    'map_banner_preview', 'map_banner_thumb', 'map_banner_title', 'maplink',
    'mapthumb', 'mapthumb_badge', 'mapthumb_gm', 'mapthumb_hybrid', 'mapthumb_osm',
    'mapthumb_tiles_gm', 'mapthumb_tiles_osm', 'mapthumb_wrap', 'namelink',
    'noexport', 'num', 'page_link', 'page_link_card', 'page_link_cta',
    'page_link_icon', 'page_link_meta', 'page_link_preview', 'page_link_title',
    'prose', 'prose_h', 'prose_host', 'prose_li', 'prose_p', 'result_title',
    'svg_card', 'svg_cards', 'table_block', 'table_title', 'th_sort', 'tiptarget',
    'titled_block', 'ts', 'word_figure',
)
OLD_CLASS = 'o_chatboo_'
NEW_CLASS = 'o_ai_'
CLASS_PATTERN = '%s(%s)(?![A-Za-z0-9_])' % (
    OLD_CLASS, '|'.join(sorted(ENGINE_CLASSES, key=len, reverse=True)),
)


def rename_stored_markup(cr, table, column):
    """Rewrite the old engine names in ``table.column``; returns rows touched."""
    expr = '"%s"' % column
    params = []
    for old, new in RENAMED:
        expr = 'replace(%s, %%s, %%s)' % expr
        params += [old, new]
    expr = "regexp_replace(%s, %%s, %%s, 'g')" % expr
    params += [CLASS_PATTERN, NEW_CLASS + r'\1']
    attributes = '%s(%s)=' % (
        OLD_PREFIX, '|'.join(old[len(OLD_PREFIX):-1] for old, _new in RENAMED),
    )
    cr.execute(
        'UPDATE "%s" SET "%s" = %s WHERE "%s" ~ %%s OR "%s" ~ %%s'
        % (table, column, expr, column, column),
        params + [attributes, CLASS_PATTERN],
    )
    return cr.rowcount
