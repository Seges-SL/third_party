# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# Renderizado HTML de resultados relaxaicode (Python puro, sin dependencias externas).

import html
import json
import logging
import re
from urllib.parse import urlparse

_logger = logging.getLogger(__name__)


# Claves de transporte / meta que nunca son "tablas de datos".
_META_LIST_KEYS = frozenset({
    'content', 'groups', 'sections', 'tables', 'propose_steps',
    'messages', 'tool_calls', 'choices', 'cards',
})
# Meta/identificadores: se saltan al buscar etiqueta textual; ``id`` sí puede
# enlazarse como fallback (invariante: registro ⇒ enlace en celda, nunca widget).
# Sin listas de sinónimos de dominio — ver ``_select_name_link_keys``.
_TECHNICAL_LINK_KEYS = frozenset({
    'id', 'ids', 'ref', 'code', 'default_code', 'xml', 'xml_id', 'xmlid',
})
# Etiqueta de un dict anidado en celda (convención de presentación, no dominio).
_NESTED_LABEL_KEYS = (
    'name', 'display_name', 'label', 'title', 'text', 'value',
)


def _is_dict_row_list(value):
    return (
        isinstance(value, list)
        and value
        and isinstance(value[0], dict)
    )


def _sibling_tabular_lists(result):
    """Listas de dicts hermanas en un dict (p. ej. by_units + by_amount).

    Cuando hay ≥2, el LLM pidió varias tablas; no debemos coger solo la primera.
    """
    if not isinstance(result, dict):
        return []
    found = []
    for key, value in result.items():
        if str(key).startswith('_') or key in _META_LIST_KEYS:
            continue
        if not _is_dict_row_list(value):
            continue
        if key == 'content' and 'type' in value[0]:
            continue
        if not _is_homogeneous_table(value):
            continue
        found.append((str(key), value))
    return found


def _humanize_table_key(key):
    """by_units → By units; Más_vendidos → Más vendidos."""
    text = str(key).replace('_', ' ').strip()
    if not text:
        return 'Tabla'
    return text[:1].upper() + text[1:]


def _result_items(result):
    # Lista de dicts en el nivel superior (result = [{...}, ...]).
    if isinstance(result, list):
        return result if (result and isinstance(result[0], dict)) else None
    if not isinstance(result, dict):
        return None
    items = result.get('data') or result.get('items')
    if isinstance(items, list) and items and isinstance(items[0], dict):
        return items
    # Varias listas tabulares hermanas → no elegir una sola (eso “borra” las demás).
    siblings = _sibling_tabular_lists(result)
    if len(siblings) >= 2:
        return None
    if len(siblings) == 1:
        return siblings[0][1]
    # El modelo pudo anidar la lista bajo cualquier clave (p. ej.
    # result = {'empleados': [...]}). Detectamos la primera lista de dicts
    # para que el render server-side no dependa del nombre de variable que
    # eligió el LLM; si no, el modelo improvisa una tabla markdown descuadrada.
    for key, value in result.items():
        if str(key).startswith('_') or key in _META_LIST_KEYS:
            continue
        if isinstance(value, list) and value and isinstance(value[0], dict):
            # El array 'content' del sobre MCP ([{'type':'text','text':...}]) es
            # transporte, no datos: no lo tabulamos (saldría "Type | Text" basura).
            if key == 'content' and 'type' in value[0]:
                continue
            return value
    return None


# Prefijos base64 de imagen → mime.
_B64_IMG_PREFIXES = (('iVBORw', 'png'), ('/9j/', 'jpeg'), ('R0lGOD', 'gif'), ('UklGR', 'webp'))
# Pistas de nombre de columna que indican una imagen (URL/ruta /web/image/...).
# Incluye miniaturas de mapa (OSM/GM) generadas por ``map_thumbnail``.
_IMG_KEY_HINTS = (
    'image', 'imagen', 'logo', 'avatar', 'foto', 'photo',
    'mapa', 'map_osm', 'map_gm', 'mapthumb', 'staticmap',
)
_IMG_STYLE = 'max-height:60px;border-radius:4px;object-fit:contain;'
_MAP_THUMB_STYLE = (
    'max-height:100px;max-width:160px;border-radius:4px;'
    'object-fit:cover;display:block;'
)
# Columnas monetarias / importes (alineación numérica + 2 decimales).
_MONEY_HINTS = (
    'amount', 'total', 'importe', 'monto', 'saldo', 'balance', 'revenue',
    'ingreso', 'precio', 'price', 'coste', 'cost', 'debe', 'haber',
    'beneficio', 'margen', 'deuda', 'pend', 'subtotal', 'neto',
)


def _has_image_columns(items):
    """True si la lista tabular incluye columnas de imagen (fotos, logos, avatares)."""
    if not items or not isinstance(items[0], dict):
        return False
    for key in items[0]:
        if str(key).startswith('_'):
            continue
        key_l = str(key).lower()
        if any(h in key_l for h in _IMG_KEY_HINTS):
            return True
        # Celdas ``__map_thumb__`` aunque el nombre de columna no tenga hint.
        for it in items[:5]:
            if isinstance(it, dict) and _is_map_thumb(it.get(key)):
                return True
    return False


def _is_homogeneous_table(items):
    """True si hay ≥1 fila de dicts con ≥2 columnas y claves homogéneas.

    Cubre previsión de 1 día / 1 registro: el umbral antiguo de 5 filas
    dejaba sin HTML server-side y el LLM aplastaba cabeceras+valores.
    """
    if not items or not isinstance(items[0], dict):
        return False
    sample = {k for k in items[0] if not str(k).startswith('_')}
    if len(sample) < 2:
        return False
    for item in items[:10]:
        if not isinstance(item, dict):
            return False
        keys = {k for k in item if not str(k).startswith('_')}
        if len(keys ^ sample) > max(1, int(len(sample) * 0.3)):
            return False
    return True


def is_tabulable(result, force=False):
    """True si conviene renderizar una tabla HTML."""
    if isinstance(result, list):
        result = {'data': result}
    if not isinstance(result, dict):
        return False
    if result.get('formatted_text'):
        return True
    # Estructura agrupada explícita: el patrón título→tabla siempre se renderiza
    # (es intención clara del usuario), sin umbral mínimo de filas.
    if _result_groups(result):
        return True
    items = _result_items(result)
    if not items:
        return False
    if force:
        return True
    if _has_image_columns(items):
        return True
    # 1+ filas homogéneas con varias columnas = tabla intencional (un
    # registro, un día, etc.).
    if _is_homogeneous_table(items):
        return True
    if len(items) < 5:
        return False
    sample_keys = set(items[0].keys())
    heterogeneous = sum(
        1 for item in items[:10]
        if isinstance(item, dict) and len(set(item.keys()) ^ sample_keys) > len(sample_keys) * 0.3
    )
    return heterogeneous <= 3


def _fmt_number(val, d_sep, t_sep, decimals=2):
    try:
        s = '{:,.{}f}'.format(val, decimals)
        return s.replace(',', '\x00').replace('.', d_sep).replace('\x00', t_sep)
    except Exception:
        return str(val)


def format_number(value, decimals=2, decimal_sep='.', thousands_sep=','):
    """Número con separadores de locale (sandbox / skills / relaxaicode).

    Preferible a ``{:,.2f}`` (siempre inglés). En el sandbox ya vienen
    ``format_number`` / ``format_amount`` cerrados sobre ``pk_*``.
    """
    if value is None:
        return '-'
    return _fmt_number(value, decimal_sep, thousands_sep, decimals=decimals)


def format_amount(
    value,
    symbol=u'€',
    decimals=2,
    decimal_sep='.',
    thousands_sep=',',
    symbol_after=True,
):
    """Importe con símbolo de moneda según locale (p. ej. ``1.234,56 €``)."""
    text = format_number(
        value,
        decimals=decimals,
        decimal_sep=decimal_sep,
        thousands_sep=thousands_sep,
    )
    if not symbol:
        return text
    if symbol_after:
        return u'%s %s' % (text, symbol)
    return u'%s%s' % (symbol, text)


def _fmt_date(val, date_format):
    if not val:
        return ''
    try:
        import datetime
        s = str(val)
        if len(s) >= 19:
            return datetime.datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').strftime(date_format)
        if len(s) >= 10:
            return datetime.datetime.strptime(s[:10], '%Y-%m-%d').strftime(date_format)
        return s
    except Exception:
        return str(val)


def render_context_from_env(env, result=None, user_message=None):
    """Locale de la sesión del usuario (res.lang) para formateo de tablas.

    Fuente de verdad: ``env.user.lang`` → ``res.lang``. No depende de
    corporate_terms ni de defaults US/ES hardcodeados en el llamante.
    """
    lang = 'en_US'
    try:
        lang = (env.user.lang or env.context.get('lang') or 'en_US')
    except Exception:
        lang = env.context.get('lang') or 'en_US'
    lang = str(lang).replace('-', '_')
    d_sep, t_sep, date_fmt = '.', ',', '%Y-%m-%d'
    try:
        lang_rec = env['res.lang'].with_context(active_test=False).search(
            [('code', '=', lang)], limit=1,
        )
        if not lang_rec and '_' in lang:
            lang_rec = env['res.lang'].with_context(active_test=False).search(
                [('code', '=ilike', lang.split('_')[0] + '_%')], limit=1,
            )
        if lang_rec:
            d_sep = lang_rec.decimal_point or '.'
            t_sep = lang_rec.thousands_sep or ','
            date_fmt = lang_rec.date_format or '%Y-%m-%d'
        elif lang.lower().startswith('es'):
            d_sep, t_sep, date_fmt = ',', '.', '%d/%m/%Y'
    except Exception as exc:
        _logger.debug('render_context_from_env: %s', exc)
    show_mode = 'show-table'
    chart_engine = 'echarts'
    dual_axis = None
    try:
        from .presentation_mode import (
            resolve_chart_engine_for_render,
            resolve_dual_axis_for_render,
            resolve_show_mode_for_render,
        )
        if not user_message:
            user_message = (env.context or {}).get('user_message')
        show_mode = resolve_show_mode_for_render(
            env, result=result, user_message=user_message,
        )
        chart_engine = resolve_chart_engine_for_render(env, result=result)
        dual_axis = resolve_dual_axis_for_render(
            env, result=result, user_message=user_message,
        )
    except Exception as exc:
        _logger.debug('render_context_from_env show_mode: %s', exc)
    user_tz = 'UTC'
    try:
        user_tz = (
            env.context.get('tz')
            or getattr(env.user, 'tz', None)
            or 'UTC'
        )
    except Exception:
        user_tz = (getattr(env, 'context', None) or {}).get('tz') or 'UTC'
    return {
        'pk_decimal_sep': d_sep,
        'pk_thousands_sep': t_sep,
        'pk_date_format': date_fmt,
        'user_lang': lang,
        'user_tz': user_tz,
        'show_mode': show_mode,
        'chart_engine': chart_engine,
        'dual_axis': dual_axis,
    }


_NUM_STR_RE = re.compile(
    r'^[\s]*[+-]?'
    r'(?:'
    r'\d{1,3}(?:([.,\s])\d{3})*(?:([.,])\d+)?'  # 1.234.567,89 / 1,234,567.89
    r'|\d+(?:([.,])\d+)?'  # 1234,56 / 1234.56
    r')'
    r'[\s]*$'
)


def _parse_numeric(val):
    """Convierte int/float/str numérica a (number, is_float) o None."""
    if isinstance(val, bool):
        return None
    if isinstance(val, int):
        return (val, False)
    if isinstance(val, float):
        return (val, True)
    if not isinstance(val, str):
        return None
    s = val.strip()
    if not s or not _NUM_STR_RE.match(s):
        return None
    # Quitar espacios (algunos locales usan espacio fino como miles).
    compact = s.replace(' ', '').replace('\u00a0', '')
    # Último . o , = decimal si hay más de un separador o patrón claro.
    last_dot = compact.rfind('.')
    last_comma = compact.rfind(',')
    if last_dot >= 0 and last_comma >= 0:
        if last_dot > last_comma:
            # 1,234.56
            compact = compact.replace(',', '')
        else:
            # 1.234,56
            compact = compact.replace('.', '').replace(',', '.')
    elif last_comma >= 0:
        # Solo comas: decimal si hay exactamente un grupo final de 1–2 dígitos
        parts = compact.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2:
            compact = parts[0].replace('.', '') + '.' + parts[1]
        else:
            compact = compact.replace(',', '')
    elif last_dot >= 0:
        parts = compact.split('.')
        if len(parts) == 2 and len(parts[1]) <= 2:
            pass  # 1234.56
        else:
            compact = compact.replace('.', '')  # 1.234.567 miles
    try:
        if '.' in compact:
            return (float(compact), True)
        return (int(compact), False)
    except Exception:
        return None


def _column_is_numeric(items, key):
    """True si la columna es mayoritariamente numérica (tipos o strings parseables)."""
    seen = 0
    numeric = 0
    for item in items[:25]:
        if not isinstance(item, dict):
            continue
        val = item.get(key)
        if val is None or val == '':
            continue
        seen += 1
        if _parse_numeric(val) is not None:
            numeric += 1
    return seen > 0 and numeric >= max(1, int(seen * 0.8))


def _normalize_col_key(key):
    return str(key).lower().replace(' ', '_').replace('-', '_')


def _is_technical_link_key(key):
    key_l = _normalize_col_key(key)
    if key_l in _TECHNICAL_LINK_KEYS:
        return True
    # ids crudos many2one / x2many, no etiquetas.
    return key_l.endswith('_id') or key_l.endswith('_ids')


def _column_is_boolean(items, key):
    seen = 0
    for item in items[:25]:
        if not isinstance(item, dict):
            continue
        val = item.get(key)
        if val is None or val == '':
            continue
        seen += 1
        if isinstance(val, bool):
            continue
        if isinstance(val, str) and val.strip().lower() in ('true', 'false', '1', '0'):
            continue
        return False
    return seen > 0


def _column_is_textual(items, key):
    """Columna con texto legible (no numérica, no bool, no imagen)."""
    if _column_is_numeric(items, key) or _column_is_boolean(items, key):
        return False
    key_l = _normalize_col_key(key)
    if any(h in key_l for h in _IMG_KEY_HINTS):
        return False
    for item in items[:25]:
        if not isinstance(item, dict):
            continue
        val = item.get(key)
        if val is None or val is False or val == '':
            continue
        if isinstance(val, (bool, int, float)):
            continue
        if str(val).strip():
            return True
    return False


def _column_has_display_value(items, key):
    for item in items[:25]:
        if not isinstance(item, dict):
            continue
        val = item.get(key)
        if val is None or val is False or val == '':
            continue
        return True
    return False


def _column_text_cardinality(items, key):
    """Ratio distinct/non-empty textual values in a sample (0..1).

    Structural signal: record labels (invoice number, partner name) tend to
    be near-unique per row; grouping/bucket labels (``1 mes``, status bands)
    repeat. No domain vocabulary — only value diversity.
    """
    seen = []
    for item in items[:80]:
        if not isinstance(item, dict):
            continue
        val = item.get(key)
        if val is None or val is False or val == '':
            continue
        if isinstance(val, bool):
            continue
        if isinstance(val, (int, float)):
            continue
        text = str(val).strip()
        if not text:
            continue
        seen.append(text.casefold())
    if not seen:
        return 0.0
    return len(set(seen)) / float(len(seen))


def _select_name_link_keys(keys, items, numeric_keys):
    """Elige UNA columna cuyo valor enlaza al registro (sin hardcode de dominio).

    Preferencia estructural:
    1) Campos canónicos Odoo ``display_name`` / ``name`` si son texto.
    2) Columna textual no meta con **mayor cardinalidad** de valores
       (etiquetas de registro ≈ únicas; buckets/filtros ≈ pocos valores
       repetidos). Empate → orden de fila.
    3) Columna ``id`` (vale enlazar el id; mejor que un widget).
    4) Primera columna con algún valor mostrable.
    """
    by_norm = {_normalize_col_key(k): k for k in keys}
    for preferred in ('display_name', 'name'):
        key = by_norm.get(preferred)
        if key is not None and _column_is_textual(items, key):
            return {key}
    textual = []
    for key in keys:
        if key in numeric_keys or _is_technical_link_key(key):
            continue
        if _column_is_textual(items, key):
            textual.append(key)
    if textual:
        # Highest distinct-value ratio; stable tie-break = earlier column.
        best = max(
            textual,
            key=lambda k: (_column_text_cardinality(items, k), -textual.index(k)),
        )
        return {best}
    id_key = by_norm.get('id')
    if id_key is not None:
        return {id_key}
    for key in keys:
        if _column_has_display_value(items, key):
            return {key}
    return set()


def row_label_for_record(item):
    """Etiqueta textual de una fila-registro (misma preferencia que namelink).

    Estructural: ``display_name`` / ``name`` → primera textual no meta → ``id``.
    Sin literales de dominio. Devuelve str o None.
    """
    if not isinstance(item, dict):
        return None
    keys = [k for k in item.keys() if not str(k).startswith('_')]
    if not keys:
        return None
    items = [item]
    numeric_keys = {k for k in keys if _column_is_numeric(items, k)}
    link_keys = _select_name_link_keys(keys, items, numeric_keys)
    for key in link_keys:
        val = item.get(key)
        if val is None or val is False or val == '':
            continue
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return str(int(val) if val == int(val) else val)
    return None


def _coerce_row_id(value):
    if isinstance(value, bool) or value is None or value is False:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value == int(value):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _row_record_id(item):
    """id de fila: acepta ``id`` / ``ID`` (el LLM capitaliza a menudo)."""
    if not isinstance(item, dict):
        return None
    for key in ('id', 'ID', 'Id'):
        rid = _coerce_row_id(item.get(key))
        if rid is not None:
            if item.get('id') != rid:
                item['id'] = rid
            return rid
    return None


def _record_form_url(item):
    model = item.get('__model') if isinstance(item, dict) else None
    rid = _row_record_id(item) if isinstance(item, dict) else None
    if not model or not isinstance(model, str) or not rid:
        return ''
    return '/web#id=%d&amp;model=%s&amp;view_type=form' % (
        rid, html.escape(model, quote=True),
    )


def _name_cell_link_html(item, text):
    """Enlace en el texto de nombre/descripción → formulario del registro."""
    url = _record_form_url(item)
    if not url or text is None or text == '':
        return ''
    return (
        '<a href="%s" target="_blank" rel="noopener" '
        'class="o_chatboo_namelink" title="Abrir registro" '
        'style="color:#0d6efd;text-decoration:underline;">%s</a>'
    ) % (url, html.escape(str(text)))


def _is_blank_cell(val):
    if isinstance(val, dict) and val.get('__map_thumb__'):
        return not (val.get('png_b64') or val.get('href'))
    if isinstance(val, dict) and val.get('__coords__'):
        return not (val.get('text') or val.get('copy'))
    return val is None or val == '' or val == [] or val == {}


def _is_map_thumb(val):
    return isinstance(val, dict) and bool(val.get('__map_thumb__'))


def _is_coords_cell(val):
    return isinstance(val, dict) and bool(val.get('__coords__'))


def _map_thumb_title(val):
    prov = (val.get('provider') or 'osm').lower()
    tiles = (val.get('tile_source') or '').lower()
    if prov == 'google' and tiles == 'osm':
        return 'Vista OSM · abre en Google Maps'
    if prov == 'google':
        return 'Google Maps'
    return 'OpenStreetMap'


def _render_map_thumb_cell(val):
    """Celda ``__map_thumb__``: miniatura PNG clicable (+ badge) o enlace texto."""
    href = (val.get('href') or '').strip()
    alt = html.escape(str(val.get('alt') or 'mapa'), quote=True)
    png = (val.get('png_b64') or '').strip()
    prov = (val.get('provider') or 'osm').lower()
    tiles = (val.get('tile_source') or ('google' if prov == 'google' else 'osm')).lower()
    badge = html.escape(str(val.get('alt') or ('GM' if prov == 'google' else 'OSM')))
    title = html.escape(_map_thumb_title(val), quote=True)
    cls = ['o_chatboo_mapthumb']
    if prov == 'google':
        cls.append('o_chatboo_mapthumb_gm')
    else:
        cls.append('o_chatboo_mapthumb_osm')
    if tiles == 'google':
        cls.append('o_chatboo_mapthumb_tiles_gm')
    else:
        cls.append('o_chatboo_mapthumb_tiles_osm')
    if prov == 'google' and tiles == 'osm':
        cls.append('o_chatboo_mapthumb_hybrid')
    class_attr = ' '.join(cls)

    if png:
        if png.startswith('data:image'):
            src = html.escape(png, quote=True)
        else:
            src = 'data:image/png;base64,%s' % html.escape(png, quote=True)
        inner = (
            '<span class="o_chatboo_mapthumb_wrap">'
            '<img src="%s" alt="%s" style="%s">'
            '<span class="o_chatboo_mapthumb_badge">%s</span>'
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
            'title="%s" class="o_chatboo_maplink %s">%s</a>'
        ) % (html.escape(href, quote=True), title, class_attr, label)
    return '<span class="text-muted small">%s</span>' % label


def _render_coords_cell(val):
    """Coords ``lat,lon`` clicables (mapa) + botón copiar."""
    text = (val.get('text') or val.get('copy') or '').strip()
    if not text and val.get('lat') is not None and val.get('lon') is not None:
        try:
            text = '%.6f,%.6f' % (float(val['lat']), float(val['lon']))
        except (TypeError, ValueError):
            text = ''
    if not text:
        return '<span class="text-muted small">—</span>'
    copy = (val.get('copy') or text).strip()
    href = (val.get('href') or '').strip()
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
            '<a class="o_chatboo_coords_link" href="%s" target="_blank" '
            'rel="noopener noreferrer" title="Abrir en mapa">'
            '<code class="o_chatboo_coords_text">%s</code></a>'
        ) % (safe_href, safe_text)
    else:
        text_html = (
            '<code class="o_chatboo_coords_text">%s</code>' % safe_text
        )
    return (
        '<span class="o_chatboo_coords" title="lat,lon (grados decimales)">'
        '%s'
        '<button type="button" class="o_chatboo_cell_copy o_chatboo_noexport" '
        'data-copy-text="%s" title="Copiar coordenadas" '
        'aria-label="Copiar coordenadas">'
        '<i class="fa fa-copy" aria-hidden="true"></i>'
        '</button>'
        '</span>'
    ) % (text_html, safe_copy)


# Columnas de detalle geo por fila (B/C). Se quitan si hay mapa integral (A)
# y el result no opta explícitamente con geo_coords / geo_thumbs.
_GEO_COORD_COL_KEYS = frozenset({
    'Coords', 'coords', 'Coordenadas', 'coordenadas',
    'Lat', 'Lon', 'lat', 'lon', 'Latitude', 'Longitude',
})
_GEO_THUMB_COL_KEYS = frozenset({
    'Mapa', 'Map', 'Mapa OSM', 'Mapa GM', 'Mapa Google', 'Miniatura',
})


def _geo_flag_enabled(result, *keys):
    if not isinstance(result, dict):
        return False
    for k in keys:
        v = result.get(k)
        if v is True or v in (1, '1', 'true', 'True', 'yes', 'si', 'sí'):
            return True
    return False


def _geo_hide_column_keys(result):
    """Column names to omit from the HTML table when a shared map is present.

    Invariant: hide B/C geo columns in the chat table, but **keep** Lat/Lon
    on the payload so a later pins-only remake can reuse the rows.
    """
    if not isinstance(result, dict):
        return set()
    has_shared = bool(
        result.get('map_url') or result.get('map_pins') or result.get('pins_url')
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
        hide |= _GEO_COORD_COL_KEYS
    if not keep_thumbs:
        hide |= _GEO_THUMB_COL_KEYS

        def _thumb_keys(rows):
            keys = set()
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                for k, cell in row.items():
                    if (
                        isinstance(cell, dict)
                        and cell.get('__map_thumb__')
                        and (cell.get('lat') is not None or cell.get('png_b64'))
                    ):
                        keys.add(k)
            return keys

        if isinstance(result.get('data'), list):
            hide |= _thumb_keys(result['data'])
        for block in result.get('tables') or []:
            if isinstance(block, dict):
                hide |= _thumb_keys(block.get('data'))
        for block in result.get('groups') or []:
            if isinstance(block, dict):
                hide |= _thumb_keys(block.get('rows') or block.get('data'))
    return hide


def _strip_unsolicited_row_geo(result):
    """Mark geo columns hidden for the table; do not mutate row payloads."""
    hide = _geo_hide_column_keys(result)
    if hide:
        result['__hide_columns__'] = sorted(hide)



def _flatten_cell_value(val):
    """Dict/list anidados → etiqueta escalar (nunca dump JSON crudo)."""
    if _is_map_thumb(val) or _is_coords_cell(val):
        return val
    if isinstance(val, dict):
        for k in _NESTED_LABEL_KEYS:
            if k in val and not _is_blank_cell(val.get(k)):
                inner = val[k]
                if not isinstance(inner, (dict, list)):
                    return inner
        for k, v in val.items():
            if str(k).startswith('_'):
                continue
            if not _is_blank_cell(v) and not isinstance(v, (dict, list)):
                return v
        return ''
    if isinstance(val, list):
        if not val:
            return ''
        parts = []
        for item in val[:8]:
            flat = _flatten_cell_value(item) if isinstance(item, (dict, list)) else item
            if not _is_blank_cell(flat):
                parts.append(str(flat))
        return ', '.join(parts)
    return val


def _table_display_keys(items, hide=None):
    """Columnas visibles: omite meta `_…`, hide-set y columnas vacías."""
    if not items or not isinstance(items[0], dict):
        return []
    hide = set(hide or ())
    keys = [
        k for k in items[0].keys()
        if not str(k).startswith('_') and k not in hide
    ]
    kept = []
    for key in keys:
        if any(not _is_blank_cell(_flatten_cell_value(it.get(key))) for it in items):
            kept.append(key)
    return kept or keys


def _render_cell(key, val, ctx, numeric_column=False, item=None):
    """Celda HTML: números, fechas, imágenes base64, imágenes por URL/ruta
    (/web/image/...) y texto escapado por defecto.
    Las imágenes URL son clickables: abren la versión completa en nueva pestaña.
    La columna elegida por ``_select_name_link_keys`` enlaza al registro
    (también si es numérica, p. ej. ``id``)."""
    if _is_map_thumb(val):
        return _render_map_thumb_cell(val)
    if _is_coords_cell(val):
        return _render_coords_cell(val)
    val = _flatten_cell_value(val)
    key_l = str(key).lower()
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
    )

    def _as_record_link(text):
        if not want_record_link or text is None or text == '':
            return None
        return _name_cell_link_html(item, text)

    # Enteros sin decimales (ids, contadores); floats con 2 (importes). bool va a texto.
    parsed = _parse_numeric(val)
    money_col = any(h in key_l for h in _MONEY_HINTS)
    if parsed is not None and (
        numeric_column
        or isinstance(val, (int, float))
        or money_col
    ):
        number, is_float = parsed
        if money_col or is_float or isinstance(val, float):
            decimals = 2
        else:
            decimals = 0
        formatted = _fmt_number(number, d_sep, t_sep, decimals=decimals)
        linked = _as_record_link(formatted)
        if linked is not None:
            return linked
        return html.escape(formatted)
    if 'date' in key_l or 'fecha' in key_l:
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
                return '<img src="data:image/%s;base64,%s" style="%s">' % (mime, clean, _IMG_STYLE)
    if any(hint in key_l for hint in _IMG_KEY_HINTS):
        if not val:
            return '<span class="text-muted small">Sin imagen</span>'
        if clean.startswith('/web/image/'):
            if re.search(r'/image_\d+$', clean):
                full_url = re.sub(r'image_\d+$', 'image_1920', clean)
            else:
                full_url = clean
            return (
                '<a href="%s" target="_blank" rel="noopener" title="Ver imagen completa">'
                '<img src="%s" style="%s">'
                '</a>'
            ) % (html.escape(full_url, quote=True), html.escape(clean, quote=True), _IMG_STYLE)
        if clean.startswith('http') or clean.startswith('/'):
            return (
                '<a href="%s" target="_blank" rel="noopener" title="Ver imagen completa">'
                '<img src="%s" style="%s">'
                '</a>'
            ) % (html.escape(clean, quote=True), html.escape(clean, quote=True), _IMG_STYLE)
        return '<span class="text-muted small">Formato desconocido</span>'
    linked = _as_record_link(clean)
    if linked is not None:
        return linked
    return html.escape(val_str)


def _render_table(items, ctx, caption=None, section_title=None, title_bg=None):
    """Construye un único <table> (cabecera + filas) para una lista de dicts.
    Imágenes (base64 y /web/image/...), coloreado por filas/celdas y formato de
    número/fecha en locale. Sin envoltorio ni total: eso lo añade el llamante.

    ``section_title``: fila de título dentro del ``<thead>`` (pegada a las
    columnas; evita el hueco CSS entre h3 y tabla).
    """
    hide = ()
    if isinstance(ctx, dict):
        hide = ctx.get('hide_columns') or ()
    keys = _table_display_keys(items, hide=hide)
    numeric_keys = {k for k in keys if _column_is_numeric(items, k)}
    # Registro (model+id) ⇒ enlace en UNA celda existente. Nunca columna-widget
    # de icono: el id u otra celda basta (opt-out: __row_links__/links=False).
    name_links_on = ctx.get('name_links', True) if isinstance(ctx, dict) else True
    has_record_rows = any(
        isinstance(it, dict) and _row_record_id(it) and it.get('__model')
        for it in items
    )
    name_link_keys = set()
    if name_links_on and has_record_rows:
        name_link_keys = _select_name_link_keys(keys, items, numeric_keys)
    # Propaga a _render_cell sin mutar el ctx del llamante.
    if isinstance(ctx, dict):
        ctx = dict(ctx)
        ctx['name_link_keys'] = name_link_keys
    parts = [
        '<table class="table table-bordered table-sm o_chatboo_data_table'
        '%s" style="width:100%%;margin:0;">'
        % (' o_chatboo_ficha_table' if section_title else '')
    ]
    if caption:
        parts.append(f'<caption class="h5">{caption}</caption>')
    parts.append('<thead>')
    if section_title:
        n = max(1, len(keys))
        safe_bg = _safe_title_bg(title_bg) or '#eef2f8'
        parts.append(
            '<tr class="o_chatboo_ficha_title">'
            '<th colspan="%d" style="background-color:%s;color:#1a1a1a;'
            'font-size:1.15rem;font-weight:700;line-height:1.3;'
            'text-align:start;text-transform:none;letter-spacing:0;'
            'padding:0.55em 0.75em;border-bottom:0;">%s</th></tr>'
            % (n, html.escape(safe_bg, quote=True), section_title)
        )
    parts.append('<tr>')
    for key in keys:
        th_class = 'o_chatboo_num text-end' if key in numeric_keys else ''
        cls_attr = (' class="%s"' % th_class) if th_class else ''
        parts.append(
            '<th%s>%s</th>' % (
                cls_attr,
                html.escape(str(key).replace('_', ' ').title()),
            )
        )
    parts.append('</tr></thead><tbody>')
    for item in items:
        tr_attrs = ''
        row_class = item.get('_row_class')
        row_color = item.get('_row_color')
        if row_class:
            tr_attrs += ' class="%s"' % html.escape(str(row_class), quote=True)
        if row_color:
            tr_attrs += ' style="background-color:%s;"' % html.escape(str(row_color), quote=True)
        parts.append('<tr%s>' % tr_attrs)
        for key in keys:
            val = item.get(key, '')
            is_num = key in numeric_keys
            classes = []
            if is_num:
                classes.append('o_chatboo_num')
                classes.append('text-end')
            cell_class = item.get('_class_' + str(key))
            if cell_class:
                classes.append(str(cell_class))
            td_attrs = ''
            if classes:
                td_attrs += ' class="%s"' % html.escape(' '.join(classes), quote=True)
            style = ''
            cell_color = item.get('_color_' + str(key))
            if cell_color:
                style += 'color:%s;' % cell_color
            cell_style = item.get('_style_' + str(key))
            if cell_style:
                style += str(cell_style)
            if style:
                td_attrs += ' style="%s"' % html.escape(style, quote=True)
            # Styled Chatboo tip via data-tip (native title is not themeable).
            cell_title = item.get('_title_' + str(key))
            if cell_title not in (None, False, ''):
                tip = html.escape(str(cell_title), quote=True)
                if ' class="' in td_attrs:
                    td_attrs = td_attrs.replace(
                        ' class="', ' class="o_chatboo_tiptarget ', 1,
                    )
                else:
                    td_attrs += ' class="o_chatboo_tiptarget"'
                td_attrs += ' data-tip="%s"' % tip
            parts.append(
                '<td%s>%s</td>' % (
                    td_attrs,
                    _render_cell(
                        key, val, ctx, numeric_column=is_num, item=item,
                    ),
                )
            )
        parts.append('</tr>')
    parts.append('</tbody></table>')
    return ''.join(parts)


def _is_image_key(key):
    """True si el nombre de columna sugiere imagen (no embeber en dataset de gráfico)."""
    key_l = str(key).lower()
    return any(h in key_l for h in _IMG_KEY_HINTS)


def _json_safe_cell(val):
    """Valor JSON-serializable para data-chatboo-dataset (sin base64 ni objetos)."""
    if val is None or isinstance(val, (bool, int, float)):
        return val
    if isinstance(val, str):
        # Base64 / blobs largos: no sirven para Chart.js y hinchan el HTML.
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
    """Filas sanitizadas para gráficos: sin claves _…, id, __model ni columnas imagen."""
    if not items or not isinstance(items[0], dict):
        return []
    skip = {'id', '__model'}
    keys = [
        k for k in items[0].keys()
        if not str(k).startswith('_')
        and str(k) not in skip
        and not _is_image_key(k)
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
    """False ⇒ no data-chatboo-dataset / no toolbar de gráfico."""
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
    """HTML fragment for data-chatboo-dual-axis, or empty when auto."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return ' data-chatboo-dual-axis="%s"' % ('1' if value else '0')
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
    return ' data-chatboo-dual-axis="%s"' % ('1' if normalized else '0')


def _table_block_attrs(show_mode, chart_engine, dataset_attr='', dual_axis=None):
    sm = html.escape(show_mode, quote=True)
    ce = html.escape(chart_engine, quote=True)
    da = _dual_axis_attr(dual_axis)
    if dataset_attr:
        return (
            '<div class="o_chatboo_table_block" %s '
            'data-chatboo-show-mode="%s" data-chatboo-chart-engine="%s"%s>'
            % (dataset_attr, sm, ce, da)
        )
    return (
        '<div class="o_chatboo_table_block" data-chatboo-show-mode="%s" '
        'data-chatboo-chart-engine="%s"%s>'
        % (sm, ce, da)
    )


def _table_block_open(items, render_context=None):
    """Abre wrapper con data-chatboo-dataset (JSON escapado) para charts en el cliente."""
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
    dataset_attr = 'data-chatboo-dataset="%s"' % html.escape(payload, quote=True)
    return _table_block_attrs(
        show_mode, chart_engine, dataset_attr=dataset_attr, dual_axis=dual_axis,
    )


def _result_footer_text(result):
    """Pie humano opcional bajo la tabla (Comparativa, cierre cálido, …)."""
    if not isinstance(result, dict):
        return ''
    for key in ('footer', 'footer_md', 'pie'):
        val = result.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ''


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
    """Tarjeta clicable con aspecto de mapa (CSS + SVG), no solo enlace texto."""
    safe_href = html.escape(href, quote=True)
    safe_label = html.escape(label)
    n = int(pin_count or 0)
    prov = 'gm' if str(provider or '').lower() in (
        'google', 'gm', 'gmaps',
    ) else 'osm'
    prov_name = 'Google Maps' if prov == 'gm' else 'OpenStreetMap'
    if n > 0:
        count_html = (
            '<span class="o_chatboo_map_banner_count">%d pin%s · %s</span>'
            % (n, '' if n == 1 else 's', html.escape(prov_name))
        )
    else:
        count_html = (
            '<span class="o_chatboo_map_banner_count">%s</span>'
            % html.escape(prov_name)
        )
    # Decorative pins (not geodata) — visual affordance only.
    pins_svg = (
        '<svg class="o_chatboo_map_banner_pins" viewBox="0 0 120 72" '
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
        '<div class="pns-result-map o_chatboo_map_banner '
        'o_chatboo_map_banner_%s">'
        '<a class="o_chatboo_map_banner_card" href="%s" target="_blank" '
        'rel="noopener noreferrer" title="%s">'
        '<span class="o_chatboo_map_banner_preview" aria-hidden="true">'
        '%s'
        '</span>'
        '<span class="o_chatboo_map_banner_meta">'
        '<span class="o_chatboo_map_banner_title">%s</span>'
        '%s'
        '<span class="o_chatboo_map_banner_cta">Abrir mapa '
        '<i class="fa fa-external-link" aria-hidden="true"></i></span>'
        '</span>'
        '</a></div>'
    ) % (prov, safe_href, safe_label, pins_svg, safe_label, count_html)


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



def _is_provider_badge_alt(alt):
    """True when alt is only a GM/OSM badge, not a human map title."""
    a = (alt or '').strip().lower()
    if not a:
        return True
    return bool(re.match(
        r'^(mapa\s+)?'
        r'(osm|gm|google(\s+maps)?|openstreetmap)'
        r'(\s*\(\d+\))?'
        r'(\s*\(pinchitos\))?$',
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
        if alt.lower().startswith('mapa'):
            return alt
        return 'Mapa %s' % alt
    return ''


def _result_map_banner_html(result):
    """Widget de mapa multipunto visible (no depender de prosa del LLM).

    Acepta ``map_pins`` / ``map_cell`` (dict ``__map_thumb__``), o
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
    label = 'Mapa de pinchitos'
    provider = 'osm'
    if cell is not None:
        href = (cell.get('href') or '').strip()
        provider = cell.get('provider') or 'osm'
        alt = str(cell.get('alt') or '').strip()
        if cell.get('map_kind') == 'route':
            label = (
                _map_banner_context_label(result, alt)
                or alt
                or 'Mapa de ruta'
            )
        elif _is_shared_geo_map_href(href):
            label = (
                _map_banner_context_label(result, alt)
                or 'Mapa compartido'
            )
            # Keep cell.provider (google/osm) for banner styling.
        elif alt:
            label = alt if alt.lower().startswith('mapa') else (
                'Mapa %s' % alt
            )
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
                '<div class="pns-result-map o_chatboo_map_banner '
                'o_chatboo_map_banner_thumb">'
                '%s</div>'
            ) % inner
    for key in ('map_url', 'pins_url'):
        val = result.get(key)
        if isinstance(val, str) and (
            val.strip().startswith('http') or val.strip().startswith('/')
        ):
            href = val.strip()
            break
    if not href:
        return ''
    context = _map_banner_context_label(result)
    if _is_shared_geo_map_href(href):
        label = context or 'Mapa compartido'
        # Without a cell, default neutral osm styling.
        provider = 'osm'
    elif 'google.com/maps' in href:
        label = context or 'Mapa Google Maps (pinchitos)'
        provider = 'google'
    elif 'openstreetmap' in href:
        label = context or 'Mapa OpenStreetMap (pinchitos)'
        provider = 'osm'
    else:
        label = context or 'Mapa de pinchitos'
    return _map_banner_card_html(
        href, label,
        pin_count=_map_banner_pin_count(result, cell),
        provider=provider,
    )


def _title_html(title):
    """Título por encima del grid, más destacado que el pie."""
    if not title:
        return ''
    return (
        '<h3 class="pns-result-title o_chatboo_result_title" '
        'style="margin:0;font-size:1.65rem;font-weight:700;'
        'line-height:1.2;color:#1a1a1a;">%s</h3>' % title
    )


def _safe_title_bg(bg):
    """Hex pastel opcional para cabecera de bloque (`title_bg` / `header_bg`)."""
    if not bg:
        return ''
    s = str(bg).strip()
    if re.fullmatch(r'#[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?([0-9A-Fa-f]{2})?', s):
        return s
    return ''


def _block_title_html(title, bg=None):
    """Título compartido gráfico + tabla (primer hijo del table_block)."""
    if not title:
        return ''
    # Margin/radius los controla CSS (.o_chatboo_titled_block) para pegar título+tabla.
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
        '<h3 class="pns-result-title o_chatboo_block_title" '
        'style="%s">%s</h3>' % (style, title)
    )


def _markdownish_to_html(text):
    """Markdown ligero → HTML de informe (títulos, listas, negrita, párrafos).

    Sin HTML crudo del LLM: se escapa todo y solo se aplican marcas conocidas.
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
            '<p class="o_chatboo_prose_p" style="margin:0.45em 0;line-height:1.5;">'
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
                '<h%d class="o_chatboo_prose_h" style="margin:0.85em 0 0.35em 0;'
                'font-weight:700;line-height:1.3;color:#1a1a1a;">%s</h%d>'
                % (level, _inline(hm.group(2)), level)
            )
            continue
        lm = re.match(r'^[-*•]\s+(.+)$', stripped)
        if lm:
            _flush_para()
            parts.append(
                '<p class="o_chatboo_prose_li" style="margin:0.2em 0 0.2em 0.85em;'
                'line-height:1.45;">• %s</p>' % _inline(lm.group(1))
            )
            continue
        om = re.match(r'^(\d+)\.\s+(.+)$', stripped)
        if om:
            _flush_para()
            parts.append(
                '<p class="o_chatboo_prose_li" style="margin:0.2em 0 0.2em 0.85em;'
                'line-height:1.45;">%s. %s</p>'
                % (html.escape(om.group(1)), _inline(om.group(2)))
            )
            continue
        para.append(stripped)
    _flush_para()
    return ''.join(parts)


def _result_notices_html(result):
    """Aviso blando (geocode miss, etc.): no corta el resultado."""
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
        '<div class="alert alert-warning o_chatboo_geo_notice" role="status" '
        'style="margin:0.75em 0;padding:0.65em 0.9em;border-radius:4px;'
        'border:1px solid #f0d48a;background:#fff8e6;color:#5c4a1a;'
        'font-size:0.92rem;line-height:1.4;">'
        '<strong>Aviso</strong><ul style="margin:0.35em 0 0 1.1em;padding:0;">'
        '%s</ul></div>'
    ) % lis


def _footer_html(result):
    raw = _result_footer_text(result)
    # Si footer es un __map_thumb__, ya lo pinta el banner; no duplicar.
    if isinstance(result, dict) and isinstance(result.get('footer'), dict):
        raw = ''
    if not raw:
        return ''
    return (
        '<div class="pns-result-footer o_chatboo_prose" style="margin:0.85em 0 0.25em 0;'
        'padding:0.55em 0.75em;background:#f4f7fa;border-radius:4px;'
        'border:1px solid #dde5ec;line-height:1.45;font-size:0.92rem;'
        'color:#334;">%s</div>'
        % _markdownish_to_html(raw)
    )


def fallback_table_html(result, summary='', render_context=None):
    """Renderizador HTML en Python puro para UNA tabla plana."""
    items = _result_items(result)
    if not items:
        return None
    ctx = render_context or {}
    # No meter URLs largas de mapa en el título (se escapan y no son clicables).
    raw_title = (
        summary
        or (result.get('title') if isinstance(result, dict) else '')
        or (result.get('summary') if isinstance(result, dict) else '')
        or 'Resultados'
    )
    if isinstance(raw_title, str) and 'http' in raw_title:
        # Quitar URL cruda del título; el banner map_url la muestra bien.
        raw_title = re.sub(r'https?://\S+', '', raw_title).strip(' .;:—-') or 'Resultados'
    title = html.escape(raw_title)
    parts = [
        _table_block_open(items, render_context=ctx),
        _block_title_html(title),
        _result_notices_html(result if isinstance(result, dict) else {}),
        _result_map_banner_html(result if isinstance(result, dict) else {}),
        '<div class="table-responsive" style="margin:1em 0;">',
        _render_table(items, ctx, caption=None),
        f'<p class="text-muted small"><strong>Total: {len(items)} registros</strong></p>',
        _footer_html(result),
        '</div>',
        '</div>',
    ]
    return ''.join(parts)


def _group_map_payload(grp):
    """Extract integral-map fields from a tables/groups entry (domain-agnostic)."""
    if not isinstance(grp, dict):
        return None
    out = {}
    for key in ('map_url', 'pins_url', 'map_pins', 'map_cell'):
        if key in grp and grp[key] is not None:
            out[key] = grp[key]
    return out or None


def _result_groups(result):
    """Detecta una estructura agrupada (secciones con título + tabla).

    Formas aceptadas (prioridad):

    1. Explícita — ``groups`` / ``sections`` / ``tables``:

        result = {'tables': [
            {'title': 'Por unidades', 'data': [{...}, ...]},
            {'title': 'Por importe', 'data': [{...}, ...]},
        ]}

    2. Implícita — varias listas tabulares hermanas (p. ej. el fallo OTBR):

        result = {'by_units': [...], 'by_amount': [...]}

       Cada clave se convierte en título humanizado. Evita que la 2ª
       sobrescriba a la 1ª al reentregar solo ``{'data': …}``.

    Devuelve una lista de tuplas ``(título, items, opts)`` o None.
    ``opts`` puede incluir ``title_bg`` / ``header_bg`` (hex pastel de cabecera)
    y ``map_payload`` (map_url / map_pins del bloque, para banner por sección).
    """
    if not isinstance(result, dict):
        return None
    raw = result.get('groups')
    if raw is None:
        raw = result.get('sections')
    if raw is None:
        raw = result.get('tables')
    if isinstance(raw, list) and raw:
        sections = []
        for grp in raw:
            if not isinstance(grp, dict):
                continue
            items = _result_items(grp) or []
            map_payload = _group_map_payload(grp)
            if not items and not map_payload:
                continue
            title = (grp.get('title') or grp.get('header') or grp.get('name')
                     or grp.get('label') or grp.get('summary') or '')
            if not title and map_payload:
                # Neutral placeholder — never invent business context.
                title = 'Map result'
            opts = {
                'title_bg': grp.get('title_bg') or grp.get('header_bg') or '',
            }
            if map_payload:
                # Carry section title into the banner so shared maps are not
                # labelled only as a provider acronym.
                payload = dict(map_payload)
                if title and not payload.get('title'):
                    payload['title'] = title
                if grp.get('summary') and not payload.get('summary'):
                    payload['summary'] = grp.get('summary')
                opts['map_payload'] = payload
            # Per-group row tint override (quartile | zebra | none).
            _tint = grp.get('tint') or grp.get('__row_tint__') or grp.get('row_tint')
            if _tint is not None:
                opts['tint'] = _tint
            sections.append((str(title), items, opts))
        if sections:
            return sections
    # Auto: by_units + by_amount (u otras claves) sin envelope `tables`.
    siblings = _sibling_tabular_lists(result)
    if len(siblings) >= 2:
        return [(_humanize_table_key(k), rows, {}) for k, rows in siblings]
    return None


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

    lang = str(ctx.get('user_lang') or 'en_US').replace('-', '_').lower()
    if lang.startswith('es'):
        restore_label = 'Restaurar'
        restore_title = 'Restaurar'
    else:
        restore_label = 'Restore'
        restore_title = 'Restore'

    parts = [
        '<div class="o_chatboo_dashboard" data-chatboo-dashboard-id="%s" '
        'data-chatboo-show-mode="dashboard" '
        'data-chatboo-chart-engine="%s">' % (
            html.escape(str(dash_id), quote=True),
            html.escape(chart_engine, quote=True),
        ),
        '<div class="o_chatboo_dashboard_toolbar o_chatboo_noexport">',
        '<button type="button" class="btn btn-sm btn-link o_chatboo_dashboard_reset" '
        'title="%s">%s</button>' % (
            html.escape(restore_title, quote=True),
            html.escape(restore_label),
        ),
        '</div>',
        '<div class="o_chatboo_dashboard_grid">',
    ]
    top = html.escape(
        summary or (result.get('summary') if isinstance(result, dict) else '') or '',
    )
    if top:
        parts.insert(
            1,
            '<h3 class="pns-result-title o_chatboo_dashboard_title">%s</h3>' % top,
        )
    # Banner multipunto a nivel raíz (también en dashboard agrupado).
    banner = _result_map_banner_html(result if isinstance(result, dict) else {})
    if banner:
        # Tras título (índice 1) o al inicio del contenido si no hay título.
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
            ' o_chatboo_dashboard_card_span2' if span >= 2 else ''
        )
        safe_title = html.escape(title or ('Bloque %d' % (index + 1)))
        parts.append(
            '<div class="o_chatboo_dashboard_card%s" data-card-id="%s">' % (
                span_cls, html.escape(card_id, quote=True),
            )
        )
        parts.append('<div class="o_chatboo_dashboard_card_header">')
        parts.append(
            '<span class="o_chatboo_dashboard_drag" aria-hidden="true" '
            'title="Arrastrar">&#8942;&#8942;</span>'
        )
        parts.append('<span class="o_chatboo_dashboard_card_title">%s</span>' % safe_title)
        parts.append('<div class="o_chatboo_dashboard_card_actions">')
        # Orden MDI clásico: minimizar · maximizar/restaurar · cerrar.
        # El JS rellena iconos geométricos; el HTML deja títulos accesibles.
        parts.append(
            '<button type="button" class="o_chatboo_dashboard_winbtn '
            'o_chatboo_dashboard_collapse" aria-expanded="true" '
            'title="Minimizar" aria-label="Minimizar"></button>'
        )
        parts.append(
            '<button type="button" class="o_chatboo_dashboard_winbtn '
            'o_chatboo_dashboard_maximize" aria-expanded="false" '
            'title="Maximizar" aria-label="Maximizar"></button>'
        )
        parts.append(
            '<button type="button" class="o_chatboo_dashboard_winbtn '
            'o_chatboo_dashboard_close" title="Cerrar" '
            'aria-label="Cerrar"></button>'
        )
        parts.append('</div></div>')
        parts.append('<div class="o_chatboo_dashboard_card_body">')
        card_ctx = dict(ctx)
        card_ctx['show_mode'] = card_block_mode
        parts.append(_table_block_open(items, render_context=card_ctx))
        map_payload = (opts or {}).get('map_payload')
        if map_payload:
            parts.append(_result_map_banner_html(map_payload))
        parts.append('<div class="table-responsive">')
        if items:
            parts.append(_render_table(items, card_ctx))
        parts.append('</div></div></div></div>')
        grand_total += len(items)
    parts.append('</div>')
    parts.append(
        '<p class="text-muted small o_chatboo_dashboard_footer">'
        '<strong>%d registros · %d tarjetas</strong></p>' % (
            grand_total, len(sections),
        )
    )
    parts.append(_footer_html(result))
    parts.append('</div>')
    return ''.join(parts)


def grouped_table_html(result, summary='', render_context=None):
    """Renderiza el patrón repetido «título → tabla» por cada grupo."""
    sections = _result_groups(result)
    if not sections:
        return None
    ctx = render_context or {}
    parts = ['<div class="o_chatboo_grouped_result" style="margin:0.25em 0 1em 0;">']
    top = html.escape(summary or (result.get('title') if isinstance(result, dict) else '') or '')
    if top:
        parts.append(_title_html(top))
    parts.append(_result_notices_html(result if isinstance(result, dict) else {}))
    # Root integral map (only if the root itself carries map_*).
    # Per-section maps (turn presentation basket) are rendered inside the loop.
    parts.append(_result_map_banner_html(result if isinstance(result, dict) else {}))
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
                'class="o_chatboo_table_block"',
                'class="o_chatboo_table_block o_chatboo_titled_block"',
                1,
            )
        parts.append(block_open)
        map_payload = (opts or {}).get('map_payload')
        if map_payload:
            parts.append(_result_map_banner_html(map_payload))
        # Título dentro del <thead> ⇒ cero hueco con la cabecera de columnas.
        parts.append('<div class="table-responsive o_chatboo_ficha">')
        if items:
            parts.append(_render_table(
                items,
                ctx,
                section_title=html.escape(title) if title else None,
                title_bg=(opts or {}).get('title_bg') if title else None,
            ))
        elif title:
            parts.append(
                '<div class="o_chatboo_ficha_title" style="padding:0.55em 0.75em;'
                'font-weight:700;">%s</div>' % html.escape(title)
            )
        parts.append('</div>')
        parts.append('</div>')
        grand_total += len(items)
    parts.append(
        '<p class="text-muted small"><strong>Total: %d registros · %d grupos'
        '</strong></p>' % (grand_total, len(sections))
    )
    parts.append(_footer_html(result))
    parts.append('</div>')
    return ''.join(parts)


# --- Paleta pastel suave (fondos de fila) ---------------------------------
# Tonos desaturados para que negro / rojo / azul / verde de texto sigan legibles.
# Misma familia que usa Chatboo en "efecto pijama".
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

# --- Coloreado por cuartiles (determinista, server-side) -------------------
# La norma de "colorear por cuartiles las columnas monetarias ordenadas" se
# aplica aquí en Python, no se delega al LLM (que la ignoraba sistemáticamente).
# Pasteles suaves (misma familia que PASTEL_ROW_COLORS); evita estridentes.
_TIER_RED = '#f8eeee'    # peor / negativo
_TIER_GREEN = '#eef6f0'  # medio
_TIER_BLUE = '#eef3f8'   # mejor


def apply_pajama_coloring(items, unique=True):
    """Asigna `_row_color` pastel suave a cada dict de la lista.

    unique=True: recorre PASTEL_ROW_COLORS (pijama sin repetir tono hasta
    agotar la paleta; luego cicla). unique=False: cebra de dos tonos.
    Devuelve la misma lista (mutada) para encadenar en RelaxAICode.
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


# Cebra sutil (report / tablas no comparables): dos grises muy suaves.
SUBTLE_ZEBRA_COLORS = (
    '#f7f8fa',  # near white
    '#eef1f5',  # soft grey-blue
)

# Columnas de etiqueta en fichas KPI (forma estructural, no dominio).
_LABEL_COL_HINTS = (
    'indicador', 'indicator', 'metric', 'concepto', 'concept', 'kpi',
    'label', 'nombre', 'name', 'descripcion', 'description',
    'serie', 'series',
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


def _is_label_column_key(key):
    kl = str(key).lower()
    return any(h in kl for h in _LABEL_COL_HINTS)


def _is_money_column_key(key):
    kl = str(key).lower()
    return any(h in kl for h in _MONEY_HINTS)


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
    """True for 2-col label+value cards where the value is not a money ranking.

    Structural shape only (column roles), not domain-specific skill names.
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
        elif n_str >= max(2, len(items) * 0.5) or _is_label_column_key(key):
            label_keys.append(key)
    if len(label_keys) != 1 or len(value_keys) != 1:
        return False
    # Money-named value column can still be a sorted ranking of peers.
    if _is_money_column_key(value_keys[0]):
        return False
    return True


def _tint_section_rows(items, result=None, render_context=None, group_opts=None):
    """Row tint: quartile tiers for comparable series, else subtle grey zebra.

    Priority: explicit ``tint`` / ``__row_tint__`` → report ``__subtle_zebra__``
    → auto (comparable → quartile, else zebra). Respects pre-set ``_row_color``
    in auto mode; forced zebra (report/override) overwrites.
    """
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
                apply_quartile_coloring(items)
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
    """True si la secuencia es no-creciente o no-decreciente (datos ordenados)."""
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


def _detect_metric_key(items):
    """Columna numérica de un ranking comparable, o None.

    Prioriza hints monetarios. Sin hint: solo si hay una única columna
    numérica, es monótona y la tabla no es ficha KPI etiqueta+valor.
    """
    if not items or not isinstance(items[0], dict) or len(items) < 5:
        return None
    numeric = _numeric_column_keys(items)
    if not numeric:
        return None
    money = [k for k in numeric if _is_money_column_key(k)]
    for key in money:
        seq = [it.get(key) for it in items if _is_number(it.get(key))]
        if len(seq) >= 5 and _monotonic(seq):
            return key
    if len(numeric) == 1 and not _is_kpi_card_shape(items):
        key = numeric[0]
        seq = [it.get(key) for it in items if _is_number(it.get(key))]
        if len(seq) >= 5 and _monotonic(seq):
            return key
    return None


def _is_comparable_series(items):
    """True when rows look like a sortable peer ranking (quartile-worthy)."""
    if not items or len(items) < 5:
        return False
    if _has_explicit_row_colors(items):
        return False
    return _detect_metric_key(items) is not None


def apply_quartile_coloring(items):
    """Inyecta _row_color por terciles sobre la columna métrica ordenada.
    Respeta colores explícitos ya presentes (no pisa lo que pida el usuario)."""
    if not items or len(items) < 5:
        return
    if _has_explicit_row_colors(items):
        return
    key = _detect_metric_key(items)
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
# ---------------------------------------------------------------------------


def render_result_html(result, summary='', render_context=None):
    """Renderiza el resultado a HTML con el renderer Python (server-side)."""
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

    # dual_axis desde el result si el caller no lo puso en el contexto.
    if render_context.get('dual_axis') is None:
        if 'dual_axis' in result:
            render_context['dual_axis'] = result.get('dual_axis')
        elif 'dualAxis' in result:
            render_context['dual_axis'] = result.get('dualAxis')

    # Opt-out de gráficos: no pisa un dashboard (tarjetas arrastrables).
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

    # Enlace al registro en celda: ON por defecto cuando hay model+id.
    # Opt-out: result['__row_links__']=False / links=False / __name_links__=False
    # (tabla limpia para copiar/exportar). No hay columna-widget de icono.
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

    # Dashboard (tarjetas movibles): solo si show_mode=dashboard y hay groups.
    grouped = grouped_dashboard_html(result, summary, render_context=render_context)
    if grouped:
        return grouped

    # Estructura agrupada vertical (título→tabla por grupo).
    grouped = grouped_table_html(result, summary, render_context=render_context)
    if grouped:
        return grouped

    items = _result_items(result)
    if items:
        _tint_section_rows(items, result=result, render_context=render_context)

    # Render server-side en Python puro (única vía). Imágenes (base64 y
    # /web/image/...), tintado de filas y formato de número/fecha en locale.
    # Funciona igual en cualquier instancia, sin dependencias externas.
    return fallback_table_html(result, summary, render_context=render_context)


def _safe_card_href(raw):
    """Allow http(s) and same-origin paths. Reject javascript/data/protocol-relative."""
    href = (raw or '').strip() if isinstance(raw, str) else ''
    if not href or href.startswith('//'):
        return ''
    if any(c in href for c in ('\n', '\r', '\t', '"', "'", '<', '>')):
        return ''
    if href.startswith('/') and not href.startswith('//'):
        return href
    if re.match(r'^[A-Za-z0-9][A-Za-z0-9.-]+\.[A-Za-z]{2,}([/?#].*)?$', href):
        href = 'https://%s' % href
    try:
        parsed = urlparse(href)
    except Exception:
        return ''
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return ''
    return href


def _link_host_label(href):
    """Hostname (or path) for the banner subtitle. Structural, not a domain list."""
    href = (href or '').strip()
    if href.startswith('/'):
        return (href.split('#', 1)[0] or '/')[:48]
    try:
        host = (urlparse(href).hostname or '').lower()
    except Exception:
        return ''
    if host.startswith('www.'):
        host = host[4:]
    return host


def _link_banner_mark_svg():
    """Decorative chain mark (not a fetched favicon)."""
    return (
        '<svg class="o_chatboo_link_banner_mark" viewBox="0 0 120 72" '
        'aria-hidden="true" focusable="false">'
        '<rect x="22" y="18" width="44" height="36" rx="8" fill="none" '
        'stroke="#0d6efd" stroke-width="3"/>'
        '<rect x="54" y="18" width="44" height="36" rx="8" fill="none" '
        'stroke="#5b6b7a" stroke-width="3"/>'
        '</svg>'
    )


def _link_banner_card_html(card):
    """Clickable banner (same gesture as the map card): preview + title + CTA."""
    href = _safe_card_href(
        card.get('url') or card.get('href') or card.get('link'),
    )
    if not href:
        return ''
    host = _link_host_label(href)
    title = (card.get('title') or host or href).strip()
    subtitle = (card.get('subtitle') or card.get('value') or '').strip()
    if not subtitle and host and host != title:
        subtitle = host
    safe_href = html.escape(href, quote=True)
    safe_title = html.escape(title)
    host_html = ''
    if subtitle:
        host_html = (
            '<span class="o_chatboo_link_banner_host">%s</span>'
            % html.escape(subtitle)
        )
    return (
        '<a class="o_chatboo_link_banner_card" href="%s" target="_blank" '
        'rel="noopener noreferrer" title="%s">'
        '<span class="o_chatboo_link_banner_preview" aria-hidden="true">'
        '%s</span>'
        '<span class="o_chatboo_link_banner_meta">'
        '<span class="o_chatboo_link_banner_title">%s</span>'
        '%s'
        '<span class="o_chatboo_link_banner_cta">Abrir '
        '<i class="fa fa-external-link" aria-hidden="true"></i></span>'
        '</span></a>'
    ) % (safe_href, safe_title, _link_banner_mark_svg(), safe_title, host_html)


def _normalize_clock_iso(iso, tz_name):
    """Load ``user_time.normalize_clock_iso`` (Odoo package or file path)."""
    try:
        from .user_time import normalize_clock_iso
        return normalize_clock_iso(iso, tz_name)
    except ImportError:
        import importlib.util
        import os
        path = os.path.join(os.path.dirname(__file__), 'user_time.py')
        spec = importlib.util.spec_from_file_location('_pns_user_time', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.normalize_clock_iso(iso, tz_name)


def collect_svg_cards(result, render_context=None):
    """Card dicts from ``card`` / ``cards``. Clock without ``iso`` is dropped.

    Clock ``iso`` naive = reloj de proceso (UTC). El huso de la card
    (``tz``) gana; ``user_tz`` de sesión solo si la card no trae ``tz``.
    """
    if not isinstance(result, dict):
        return []
    ctx = render_context or {}
    user_tz = (ctx.get('user_tz') or '').strip() or None
    raw = []
    cards = result.get('cards')
    if isinstance(cards, list):
        raw.extend(cards)
    card = result.get('card')
    if isinstance(card, dict):
        raw.append(card)
    elif isinstance(card, list):
        raw.extend(card)
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind = str(item.get('kind') or 'fact').strip().lower() or 'fact'
        payload = {'kind': kind}
        for key in (
            'title', 'value', 'unit', 'tz', 'iso',
            'url', 'href', 'link', 'subtitle',
        ):
            val = item.get(key)
            if val not in (None, ''):
                payload[key] = str(val)
        if kind == 'link':
            href = _safe_card_href(
                payload.get('url') or payload.get('href') or payload.get('link'),
            )
            if not href:
                continue
            payload['url'] = href
            payload.pop('href', None)
            payload.pop('link', None)
            if not payload.get('title'):
                payload['title'] = _link_host_label(href) or href
            out.append(payload)
            continue
        if kind == 'clock' and not payload.get('iso'):
            continue
        if kind == 'clock':
            try:
                iso_out, tz_out = _normalize_clock_iso(
                    payload.get('iso'),
                    (payload.get('tz') or '').strip() or user_tz,
                )
                if iso_out:
                    payload['iso'] = iso_out
                if tz_out:
                    payload['tz'] = tz_out
            except Exception:
                pass
        if kind != 'clock' and not payload.get('title') and not payload.get('value'):
            continue
        out.append(payload)
    return out


def render_svg_cards_html(result, render_context=None):
    """HTML envelope ``data-chatboo-card``; Chatboo hydrates clock/fact SVG.

    ``kind=link`` is a real ``<a>`` banner (like the map card), painted here
    so it works without JS; the envelope remains for client re-hydrate.
    """
    cards = collect_svg_cards(result, render_context=render_context)
    if not cards:
        return ''
    parts = []
    for card in cards:
        try:
            payload = json.dumps(
                card, ensure_ascii=False, separators=(',', ':'), default=str,
            )
        except (TypeError, ValueError):
            continue
        attr = html.escape(payload, quote=True)
        if card.get('kind') == 'link':
            inner = _link_banner_card_html(card)
            if not inner:
                continue
            parts.append(
                '<div class="o_chatboo_svg_card o_chatboo_link_banner" '
                'data-chatboo-card="%s">%s</div>'
                % (attr, inner)
            )
            continue
        parts.append(
            '<div class="o_chatboo_svg_card" data-chatboo-card="%s"></div>'
            % attr
        )
    if not parts:
        return ''
    return '<div class="o_chatboo_svg_cards">%s</div>' % ''.join(parts)


def maybe_attach_formatted_text(result, summary='', render_context=None, force=False):
    """Añade formatted_text al dict result si procede. Devuelve True si se renderizó."""
    if not isinstance(result, dict) or result.get('error'):
        return False
    card_html = render_svg_cards_html(result, render_context=render_context)
    existing = result.get('formatted_text')
    if existing:
        if card_html and 'data-chatboo-card' not in existing:
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
    if not rendered and not card_html:
        return False
    result['formatted_text'] = (card_html or '') + (rendered or '')
    result['__fmt_type__'] = 'server_side_python'
    result.pop('__records__', None)
    only_cards = bool(card_html) and not rendered
    if force or only_cards:
        result['__phase__'] = 'presentation'
        result['__presentation_complete__'] = True
        result['__satisfied__'] = True
        result['__return_direct__'] = True
    else:
        # Tabla para contexto del LLM (tool JSON), no para burbuja de chat.
        result.setdefault('__phase__', 'extraction')
        result.pop('__return_direct__', None)
        result.pop('__direct_return__', None)
        result.pop('__return_direct_to_user__', None)
    _logger.info(
        'relaxaicode_render: HTML generado (%s chars, force=%s, user_facing=%s, cards=%s)',
        len(result['formatted_text']), force, force or only_cards, bool(card_html),
    )
    return True


def _image_link_href(url):
    """URL para abrir imagen en pestaña nueva. None si no es abrible (p. ej. data:)."""
    if not url or url.startswith('data:'):
        return None
    if url.startswith('/web/image/') and re.search(r'/image_\d+$', url):
        return re.sub(r'image_\d+$', 'image_1920', url)
    if url.startswith('http') or url.startswith('/'):
        return url
    return None


def wrap_bare_images_clickable(html_content):
    """Envuelve <img> sueltas en enlaces target=_blank. Omite data: URI y imgs ya enlazadas."""
    if not html_content or '<img' not in html_content:
        return html_content

    def _wrap(m):
        img_tag = m.group(1)
        if re.search(r'<a\s[^>]*>\s*$', html_content[:m.start()]):
            return img_tag
        src_match = re.search(r'src=["\']([^"\']+)["\']', img_tag)
        if not src_match:
            return img_tag
        href = _image_link_href(src_match.group(1))
        if not href:
            return img_tag
        return (
            '<a href="%s" target="_blank" rel="noopener" title="Ver imagen completa">'
            '%s</a>'
        ) % (html.escape(href, quote=True), img_tag)

    out = re.sub(r'(<img\s[^>]*>)', _wrap, html_content)
    out = re.sub(
        r'(<a\s[^>]*>)\s*<a\s[^>]*>(<img\s[^>]*>)</a>',
        r'\1\2',
        out,
    )
    return out


def render_for_direct_return(result, summary='', render_context=None):
    """HTML para retorno directo al chat (sin mutar result)."""
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
