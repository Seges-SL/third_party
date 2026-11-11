# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Map cells, coordinates, geo columns to hide and the map banner."""

import html
import re

from .relaxaicode_render_base import (
    _flatten_cell_value,
    _is_blank_cell,
    _is_coords_cell,
    _is_map_thumb,
    _MAP_THUMB_STYLE,
    page_url_on_result,
    _safe_card_href,
    _t,
)


def _map_thumb_title(val):
    prov = (val.get('provider') or 'osm').lower()
    tiles = (val.get('tile_source') or '').lower()
    if prov == 'google' and tiles == 'osm':
        return _t('OSM view · opens in Google Maps')
    if prov == 'google':
        return 'Google Maps'
    return 'OpenStreetMap'


def _render_map_thumb_cell(val):
    """``__map_thumb__`` cell: clickable PNG thumbnail (+ badge) or text link."""
    href = _safe_card_href(val.get('href'))
    alt = html.escape(str(val.get('alt') or _t('Map')), quote=True)
    png = (val.get('png_b64') or '').strip()
    prov = (val.get('provider') or 'osm').lower()
    tiles = (val.get('tile_source') or ('google' if prov == 'google' else 'osm')).lower()
    badge = html.escape(str(val.get('alt') or ('GM' if prov == 'google' else 'OSM')))
    title = html.escape(_map_thumb_title(val), quote=True)
    cls = ['o_ai_mapthumb']
    if prov == 'google':
        cls.append('o_ai_mapthumb_gm')
    else:
        cls.append('o_ai_mapthumb_osm')
    if tiles == 'google':
        cls.append('o_ai_mapthumb_tiles_gm')
    else:
        cls.append('o_ai_mapthumb_tiles_osm')
    if prov == 'google' and tiles == 'osm':
        cls.append('o_ai_mapthumb_hybrid')
    class_attr = ' '.join(cls)

    if png:
        if png.startswith('data:image'):
            src = html.escape(png, quote=True)
        else:
            src = 'data:image/png;base64,%s' % html.escape(png, quote=True)
        inner = (
            '<span class="o_ai_mapthumb_wrap">'
            '<img src="%s" alt="%s" style="%s">'
            '<span class="o_ai_mapthumb_badge">%s</span>'
            '</span>'
        ) % (src, alt, _MAP_THUMB_STYLE, badge)
        if href:
            return (
                '<a href="%s" target="_blank" rel="noopener" '
                'title="%s" class="%s">%s</a>'
            ) % (html.escape(href, quote=True), title, class_attr, inner)
        return '<span class="%s" title="%s">%s</span>' % (class_attr, title, inner)

    label = badge
    if href:
        return (
            '<a href="%s" target="_blank" rel="noopener" '
            'title="%s" class="o_ai_maplink %s">%s</a>'
        ) % (html.escape(href, quote=True), title, class_attr, label)
    return '<span class="text-muted small">%s</span>' % label


def _render_coords_cell(val):
    """Clickable ``lat,lon`` coords (map) + copy button."""
    text = (val.get('text') or val.get('copy') or '').strip()
    if not text and val.get('lat') is not None and val.get('lon') is not None:
        try:
            text = '%.6f,%.6f' % (float(val['lat']), float(val['lon']))
        except (TypeError, ValueError):
            text = ''
    if not text:
        return '<span class="text-muted small">—</span>'
    copy = (val.get('copy') or text).strip()
    href = _safe_card_href(val.get('href'))
    if not href and val.get('lat') is not None:
        try:
            lat_f = float(val['lat'])
            lon_f = float(val['lon'])
            provider = (val.get('provider') or 'google').strip().lower()
            if provider in ('osm', 'openstreetmap', 'nominatim'):
                href = (
                    'https://www.openstreetmap.org/'
                    '?mlat=%.6f&mlon=%.6f#map=16/%.6f/%.6f'
                ) % (lat_f, lon_f, lat_f, lon_f)
            else:
                href = (
                    'https://www.google.com/maps?q=%.6f,%.6f'
                ) % (lat_f, lon_f)
        except (TypeError, ValueError):
            href = ''
    safe_text = html.escape(text)
    safe_copy = html.escape(copy, quote=True)
    if href:
        safe_href = html.escape(href, quote=True)
        text_html = (
            '<a class="o_ai_coords_link" href="%s" target="_blank" '
            'rel="noopener noreferrer" title="%s">'
            '<code class="o_ai_coords_text">%s</code></a>'
        ) % (safe_href, html.escape(_t('Open in map'), quote=True), safe_text)
    else:
        text_html = (
            '<code class="o_ai_coords_text">%s</code>' % safe_text
        )
    return (
        '<span class="o_ai_coords" title="%s">'
        '%s'
        '<button type="button" class="o_ai_cell_copy o_ai_noexport" '
        'data-copy-text="%s" title="%s" '
        'aria-label="%s">'
        '<i class="fa fa-copy" aria-hidden="true"></i>'
        '</button>'
        '</span>'
    ) % (
        html.escape(_t('lat,lon (decimal degrees)'), quote=True),
        text_html, safe_copy,
        html.escape(_t('Copy coordinates'), quote=True),
        html.escape(_t('Copy coordinates'), quote=True),
    )


# Per-row geo detail columns (B/C) go when there is a whole map (A) and the
# result does not keep them with geo_coords / geo_thumbs. A column is told by
# its cells (``__coords__`` / ``__map_thumb__``), never by the name the
# skill gave it; bare numeric latitude/longitude only by these field tokens.
_GEO_LATLON_KEYS = frozenset({'lat', 'lon', 'lng', 'latitude', 'longitude'})


def _geo_flag_enabled(result, *keys):
    if not isinstance(result, dict):
        return False
    for k in keys:
        v = result.get(k)
        if v is True or v in (1, '1', 'true', 'True'):
            return True
    return False


def _geo_rows(result):
    if isinstance(result.get('data'), list):
        yield result['data']
    for block in result.get('tables') or []:
        if isinstance(block, dict):
            yield block.get('data')
    for block in result.get('groups') or []:
        if isinstance(block, dict):
            yield block.get('rows') or block.get('data')


def _geo_column_keys(result, is_geo_cell):
    keys = set()
    for rows in _geo_rows(result):
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            for k, cell in row.items():
                if is_geo_cell(cell):
                    keys.add(k)
    return keys


def _is_row_thumb(cell):
    return _is_map_thumb(cell) and (
        cell.get('lat') is not None or cell.get('png_b64')
    )


def _latlon_keys(result):
    keys = set()
    for rows in _geo_rows(result):
        for row in rows or []:
            if isinstance(row, dict):
                keys |= {k for k in row if str(k).strip().lower() in _GEO_LATLON_KEYS}
    return keys


def _geo_hide_column_keys(result):
    """Column names to omit from the HTML table when a shared map is present.

    Invariant: hide B/C geo columns in the chat table, but **keep** Lat/Lon
    on the payload so a later pins-only remake can reuse the rows.
    """
    if not isinstance(result, dict):
        return set()
    has_shared = bool(
        result.get('map_pins')
        or result.get('map_cell')
        or _is_map_href(page_url_on_result(result))
    )
    if not has_shared:
        return set()
    keep_coords = _geo_flag_enabled(
        result, 'geo_coords', 'row_coords', 'geo_row_coords',
    )
    keep_thumbs = _geo_flag_enabled(
        result, 'geo_thumbs', 'row_thumbs', 'geo_row_thumbs',
    )
    if keep_coords and keep_thumbs:
        return set()
    hide = set()
    if not keep_coords:
        hide |= _geo_column_keys(result, _is_coords_cell) | _latlon_keys(result)
    if not keep_thumbs:
        hide |= _geo_column_keys(result, _is_row_thumb)
    return hide


def _strip_unsolicited_row_geo(result):
    """Mark geo columns hidden for the table; do not mutate row payloads."""
    hide = _geo_hide_column_keys(result)
    if hide:
        result['__hide_columns__'] = sorted(hide)


def _table_display_keys(items, hide=None):
    """Visible columns: skips `_…` meta, the hide-set and empty columns."""
    if not items or not isinstance(items[0], dict):
        return []
    hide = set(hide or ())
    keys = [
        k for k in items[0].keys()
        if not str(k).startswith('_')
        and k not in hide
        and str(k) not in ('id', '__model')
    ]
    kept = []
    for key in keys:
        if any(not _is_blank_cell(_flatten_cell_value(it.get(key))) for it in items):
            kept.append(key)
    return kept or keys


def _map_banner_pin_count(result, cell=None):
    """Best-effort pin count from map_pins alt / pin_count / summary."""
    if isinstance(cell, dict):
        for key in ('pin_count', 'pins', 'n'):
            try:
                n = int(cell.get(key))
                if n > 0:
                    return n
            except (TypeError, ValueError):
                pass
        alt = str(cell.get('alt') or '')
        m = re.search(r'\((\d+)\)', alt)
        if m:
            return int(m.group(1))
    if isinstance(result, dict):
        for key in ('pin_count', 'map_pin_count', 'located'):
            try:
                n = int(result.get(key))
                if n > 0:
                    return n
            except (TypeError, ValueError):
                pass
        summary = str(result.get('summary') or '')
        m = re.search(
            r'(\d+)\s+localizad', summary, flags=re.IGNORECASE,
        )
        if m:
            return int(m.group(1))
    return 0


def _map_banner_card_html(href, label, pin_count=0, provider='osm'):
    """Clickable card that looks like a map (CSS + SVG), not just a text link."""
    href = _safe_card_href(href)
    if not href:
        return ''
    safe_href = html.escape(href, quote=True)
    safe_label = html.escape(label)
    n = int(pin_count or 0)
    prov = 'gm' if str(provider or '').lower() in (
        'google', 'gm', 'gmaps',
    ) else 'osm'
    prov_name = 'Google Maps' if prov == 'gm' else 'OpenStreetMap'
    if n > 0:
        pins = _t('1 pin') if n == 1 else _t('%d pins') % n
        count_html = (
            '<span class="o_ai_map_banner_count">%s · %s</span>'
            % (html.escape(pins), html.escape(prov_name))
        )
    else:
        count_html = (
            '<span class="o_ai_map_banner_count">%s</span>'
            % html.escape(prov_name)
        )
    # Decorative pins (not geodata) — visual affordance only.
    pins_svg = (
        '<svg class="o_ai_map_banner_pins" viewBox="0 0 120 72" '
        'aria-hidden="true" focusable="false">'
        '<ellipse cx="28" cy="48" rx="22" ry="10" fill="rgba(34,139,34,0.18)"/>'
        '<ellipse cx="78" cy="40" rx="28" ry="12" fill="rgba(70,130,180,0.16)"/>'
        '<path d="M34 18c0-7 5.5-12 12-12s12 5 12 12c0 9-12 22-12 22S34 27 34 18z" '
        'fill="#e74c3c"/>'
        '<circle cx="46" cy="17" r="3.2" fill="#fff"/>'
        '<path d="M62 28c0-5.5 4.2-10 9.5-10S81 22.5 81 28c0 7.5-9.5 18-9.5 18'
        'S62 35.5 62 28z" fill="#c0392b"/>'
        '<circle cx="71.5" cy="27" r="2.6" fill="#fff"/>'
        '<path d="M18 34c0-4.5 3.5-8 7.5-8S33 29.5 33 34c0 6-7.5 14.5-7.5 14.5'
        'S18 40 18 34z" fill="#e67e22"/>'
        '<circle cx="25.5" cy="33" r="2.2" fill="#fff"/>'
        '</svg>'
    )
    return (
        '<div class="pns-result-map o_ai_map_banner '
        'o_ai_map_banner_%s">'
        '<a class="o_ai_map_banner_card" href="%s" target="_blank" '
        'rel="noopener noreferrer" title="%s">'
        '<span class="o_ai_map_banner_preview" aria-hidden="true">'
        '%s'
        '</span>'
        '<span class="o_ai_map_banner_meta">'
        '<span class="o_ai_map_banner_title">%s</span>'
        '%s'
        '<span class="o_ai_map_banner_cta">%s '
        '<i class="fa fa-external-link" aria-hidden="true"></i></span>'
        '</span>'
        '</a></div>'
    ) % (prov, safe_href, safe_label, pins_svg, safe_label, count_html,
         html.escape(_t('Open map')))


def _is_shared_geo_map_href(href):
    """Shared pin viewer (/geo/map/…) — GM or OSM by settings.

    Prefers ``pns_geo.utils.geo_urls`` when Geo is installed; otherwise the
    same canonical path constant (must stay in sync with ``GEO_MAP_PATH``).
    """
    try:
        from odoo.addons.pns_geo.utils.geo_urls import is_geo_map_href
        return is_geo_map_href(href)
    except Exception:
        h = (href or '').strip().lower()
        return '/geo/map/' in h


def _is_map_href(href):
    """True when this address is a map page (shared viewer, Google, OSM)."""
    if not href:
        return False
    return bool(
        _is_shared_geo_map_href(href)
        or 'google.com/maps' in href
        or 'openstreetmap' in href
    )


def _is_provider_badge_alt(alt):
    """True when alt is only a GM/OSM badge, not a human map title."""
    a = (alt or '').strip().lower()
    if not a:
        return True
    return bool(re.match(
        r'^(osm|gm|google(\s+maps)?|openstreetmap)(\s*\(\d+\))?$',
        a,
    ))


def _map_banner_context_label(result, alt=''):
    """Prefer human title/summary over provider acronyms."""
    if not isinstance(result, dict):
        result = {}
    for key in ('title', 'summary', 'header', 'name', 'label'):
        val = result.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    alt = (alt or '').strip()
    if alt and not _is_provider_badge_alt(alt):
        return alt
    return ''


def _result_map_banner_html(result):
    """Visible multi-point map widget (do not rely on LLM prose).

    Accepts ``map_pins`` / ``map_cell`` (dict ``__map_thumb__``), or
    ``map_url`` / ``pins_url`` (string http).

    Shared maps (``/geo/map/``) follow provider priority; use the
    cell ``provider`` for GM/OSM styling when present.
    """
    if not isinstance(result, dict):
        return ''
    cell = None
    for key in ('map_pins', 'map_cell'):
        val = result.get(key)
        if isinstance(val, dict) and val.get('__map_thumb__') and (
            val.get('href') or val.get('png_b64')
        ):
            cell = val
            break
    href = ''
    label = _t('Pin map')
    provider = 'osm'
    if cell is not None:
        href = (cell.get('href') or '').strip()
        provider = cell.get('provider') or 'osm'
        alt = str(cell.get('alt') or '').strip()
        if cell.get('map_kind') == 'route':
            label = (
                _map_banner_context_label(result, alt)
                or alt
                or _t('Route map')
            )
        elif _is_shared_geo_map_href(href):
            label = (
                _map_banner_context_label(result, alt)
                or _t('Shared map')
            )
            # Keep cell.provider (google/osm) for banner styling.
        elif alt:
            label = alt
        # Prefer the map card over a tiny text thumb link when there is no PNG.
        if href and not (cell.get('png_b64') or '').strip():
            return _map_banner_card_html(
                href, label,
                pin_count=_map_banner_pin_count(result, cell),
                provider=provider,
            )
        if href or cell.get('png_b64'):
            inner = _render_map_thumb_cell(cell)
            return (
                '<div class="pns-result-map o_ai_map_banner '
                'o_ai_map_banner_thumb">'
                '%s</div>'
            ) % inner
    href = page_url_on_result(result)
    # The card is chosen by the content: only a map address gets the map
    # card. Any other page is a plain link (``_result_page_link_html``).
    if not _is_map_href(href):
        return ''
    context = _map_banner_context_label(result)
    if _is_shared_geo_map_href(href):
        label = context or _t('Shared map')
        # Without a cell, default neutral osm styling.
        provider = 'osm'
    elif 'google.com/maps' in href:
        label = context or _t('Pin map')
        provider = 'google'
    else:
        label = context or _t('Pin map')
        provider = 'osm'
    return _map_banner_card_html(
        href, label,
        pin_count=_map_banner_pin_count(result, cell),
        provider=provider,
    )
