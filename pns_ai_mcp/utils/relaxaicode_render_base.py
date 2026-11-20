# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Shared pieces of the renderer: translation, result shape, images, numbers, dates and the render context."""

import functools
import logging
import re
from contextvars import ContextVar
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlparse

try:  # loaded on its own by the tests, with no Odoo runtime under it
    from odoo import _ as _odoo_translate
except ImportError:  # pragma: no cover
    _odoo_translate = None

_logger = logging.getLogger(__name__)


_RENDER_CONTEXT = ContextVar('relaxaicode_render_context', default=None)


def _t(source, env=None):
    """English msgid in the language of the person the result is painted for."""
    if _odoo_translate is None:
        return source
    rcx = _RENDER_CONTEXT.get()
    if rcx is None and env is not None:
        rcx = {'user_lang': env.user.lang or env.lang, 'env': env}
    rcx = rcx or {}
    # Odoo's ``_`` reads the language from its caller's locals: ``context``
    # (O14 and O19) and ``cr`` (O14). The turn runs in a thread with no request.
    context = {'lang': rcx.get('user_lang') or 'en_US'}  # noqa: F841
    if rcx.get('env') is not None:
        cr = rcx['env'].cr  # noqa: F841
    return _odoo_translate(source)


def _paints(func):
    """Keep the caller's ``render_context`` for ``_t`` while ``func`` paints."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        rcx = kwargs.get('render_context')
        if rcx is None:
            return func(*args, **kwargs)
        token = _RENDER_CONTEXT.set(rcx)
        try:
            return func(*args, **kwargs)
        finally:
            _RENDER_CONTEXT.reset(token)
    return wrapper


def _load_page_url_resolver():
    """``result_page.page_url_on_result`` (Odoo package or bare file path)."""
    try:
        from .result_page import page_url_on_result
        return page_url_on_result
    except ImportError:
        import importlib.util
        import os
        path = os.path.join(os.path.dirname(__file__), 'result_page.py')
        spec = importlib.util.spec_from_file_location('_pns_result_page', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.page_url_on_result


page_url_on_result = _load_page_url_resolver()


# Transport / meta keys that are never "data tables".
_META_LIST_KEYS = frozenset({
    'content', 'groups', 'sections', 'tables', 'propose_steps',
    'messages', 'tool_calls', 'choices', 'cards',
})


# Meta/identifiers: skipped when looking for a text label; ``id`` may still
# be linked as a fallback (invariant: record ⇒ link in a cell, never a widget).
# No domain synonym lists — see ``_select_name_link_keys``.
_TECHNICAL_LINK_KEYS = frozenset({
    'id', 'ids', 'ref', 'code', 'default_code', 'xml', 'xml_id', 'xmlid',
})


# Label of a dict nested in a cell (presentation convention, not domain).
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
    """Sibling lists of dicts inside a dict (e.g. by_units + by_amount).

    With ≥2, the LLM asked for several tables; we must not take only the first.
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
        return _t('Table')
    return text[:1].upper() + text[1:]


def _result_items(result):
    # List of dicts at the top level (result = [{...}, ...]).
    if isinstance(result, list):
        return result if (result and isinstance(result[0], dict)) else None
    if not isinstance(result, dict):
        return None
    items = result.get('data') or result.get('items')
    if isinstance(items, list) and items and isinstance(items[0], dict):
        return items
    # Several sibling tabular lists → do not pick just one (that “erases” the rest).
    siblings = _sibling_tabular_lists(result)
    if len(siblings) >= 2:
        return None
    if len(siblings) == 1:
        return siblings[0][1]
    # The model may have nested the list under any key (e.g.
    # result = {'empleados': [...]}). We detect the first list of dicts
    # so the server-side render does not depend on the variable name the
    # LLM chose; otherwise the model improvises a misaligned markdown table.
    for key, value in result.items():
        if str(key).startswith('_') or key in _META_LIST_KEYS:
            continue
        if isinstance(value, list) and value and isinstance(value[0], dict):
            # The 'content' array of the MCP envelope ([{'type':'text','text':...}]) is
            # transport, not data: we do not tabulate it (it would give "Type | Text" junk).
            if key == 'content' and 'type' in value[0]:
                continue
            return value
    return None


# Base64 image prefixes → mime.
_B64_IMG_PREFIXES = (('iVBORw', 'png'), ('/9j/', 'jpeg'), ('R0lGOD', 'gif'), ('UklGR', 'webp'))


# Image file extensions (international tokens, like pdf/xlsx).
_IMG_PATH_EXT_RE = re.compile(r'(?i)\.(?:jpe?g|png|gif|webp|bmp|avif)$')


_IMG_STYLE = 'max-height:60px;border-radius:4px;object-fit:contain;'


_MAP_THUMB_STYLE = (
    'max-height:100px;max-width:160px;border-radius:4px;'
    'object-fit:cover;display:block;'
)


# ISO 8601 date or datetime, as Odoo and APIs send it.
_ISO_DATE_RE = re.compile(
    r'^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$'
)


def _is_b64_image(text):
    return len(text) > 64 and any(text.startswith(p) for p, _m in _B64_IMG_PREFIXES)


# /web/image/<model>/<id>/<field>[/filename][?query]
_WEB_IMAGE_PATH_RE = re.compile(
    r'^(?P<head>/web/image/)'
    r'(?P<model>[a-z][a-z0-9_.]*)/(?P<rid>\d+)/'
    r'(?P<field>[A-Za-z_][A-Za-z0-9_]*)'
    r'(?P<tail>(?:/[^?]*)?)(?P<query>\?.*)?$'
)


# image_128, avatar_512: the size is the trailing number, the rest is the stem.
_SIZED_IMAGE_FIELD_RE = re.compile(r'^(?P<base>.+)_(?P<size>\d+)$')


def _largest_image_url(url, env=None):
    """Same picture, at the biggest size this model actually stores.

    ``image_128`` becomes ``image_1920`` only when that field exists.
    A picture stored only as ``image_128`` stays on ``image_128``. The
    web route answers a missing field with the generic placeholder, and
    the viewer then swaps the real picture for that icon.
    """
    if not isinstance(url, str) or not url.startswith('/web/image/') or env is None:
        return url
    found = _WEB_IMAGE_PATH_RE.match(url)
    sized = _SIZED_IMAGE_FIELD_RE.match(found.group('field')) if found else None
    if not sized:
        return url
    model = found.group('model')
    try:
        if model not in env:
            return url
        fields = env[model]._fields
    except Exception:
        return url
    base = sized.group('base')
    best_size = int(sized.group('size'))
    best_name = found.group('field')
    for name, field in fields.items():
        other = _SIZED_IMAGE_FIELD_RE.match(name)
        if not other or other.group('base') != base:
            continue
        if getattr(field, 'type', None) != 'binary':
            continue
        size = int(other.group('size'))
        if size > best_size:
            best_size = size
            best_name = name
    if best_name == found.group('field'):
        return url
    return '%s%s/%s/%s%s%s' % (
        found.group('head'), model, found.group('rid'), best_name,
        found.group('tail') or '', found.group('query') or '',
    )


def _is_image_ref(val):
    """True when the cell value itself is a picture, whatever the column is called.

    Odoo path ``/web/image/…``, a ``data:image`` URI, raw base64 of an image,
    or an http(s) URL whose path ends in an image file extension.
    """
    if not isinstance(val, str):
        return False
    s = val.strip()
    s = s[2:-1] if s.startswith(("b'", 'b"')) else s
    low = s.lower()
    if s.startswith(('/web/image/', '/web/image?')) or low.startswith('data:image/'):
        return True
    if low.startswith(('http://', 'https://')):
        return bool(_IMG_PATH_EXT_RE.search(urlparse(s).path or ''))
    return _is_b64_image(s)


def _column_is_image(items, key):
    """True when every filled cell of *key* (sampled) is a picture."""
    seen = 0
    for item in items[:25]:
        if not isinstance(item, dict):
            continue
        val = item.get(key)
        if val is None or val is False or val == '':
            continue
        if _is_map_thumb(val):
            seen += 1
            continue
        if not _is_image_ref(_flatten_cell_value(val)):
            return False
        seen += 1
    return seen > 0


def _has_image_columns(items):
    """True if the tabular list has image columns (photos, logos, avatars)."""
    if not items or not isinstance(items[0], dict):
        return False
    return any(
        _column_is_image(items, key)
        for key in items[0]
        if not str(key).startswith('_')
    )


def _is_homogeneous_table(items):
    """True if there is ≥1 row of dicts with ≥2 columns and homogeneous keys.

    Covers a 1-day forecast / 1 record: the old 5-row threshold
    left no server-side HTML and the LLM squashed headers+values.
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
    """True if an HTML table should be rendered."""
    if isinstance(result, list):
        result = {'data': result}
    if not isinstance(result, dict):
        return False
    if result.get('formatted_text'):
        return True
    # Explicit grouped structure: the title→table pattern is always rendered
    # (it is a clear user intent), with no minimum row count.
    if _result_groups(result):
        return True
    items = _result_items(result)
    if not items:
        return False
    if force:
        return True
    if _has_image_columns(items):
        return True
    # 1+ homogeneous rows with several columns = intended table (one
    # record, one day, etc.).
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
        places = int(decimals)
        if isinstance(val, bool):
            return str(val)
        quant = val if isinstance(val, Decimal) else Decimal(str(val))
        q = (Decimal(10) ** -places) if places else Decimal(1)
        quant = quant.quantize(q, rounding=ROUND_HALF_UP)
        s = format(quant, ',.%df' % places)
        return s.replace(',', '\x00').replace('.', d_sep).replace('\x00', t_sep)
    except (InvalidOperation, ValueError, TypeError, ArithmeticError):
        return str(val)


def format_number(value, decimals=2, decimal_sep='.', thousands_sep=','):
    """Number with locale separators (sandbox / skills / relaxaicode).

    Better than ``{:,.2f}`` (always English). The sandbox already has
    ``format_number`` / ``format_amount`` closed over ``pk_*``.
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
    """Amount with currency symbol per locale (e.g. ``1.234,56 €``)."""
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


def _is_iso_date(val):
    return bool(_ISO_DATE_RE.match(str(val).strip())) if val else False


def _fmt_date(val, date_format):
    if not val:
        return ''
    try:
        import datetime
        s = str(val).strip().replace('T', ' ', 1)
        if len(s) >= 19:
            return datetime.datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S').strftime(date_format)
        if len(s) >= 10:
            return datetime.datetime.strptime(s[:10], '%Y-%m-%d').strftime(date_format)
        return s
    except Exception:
        return str(val)


def render_context_from_env(env, result=None):
    """Locale of the user's session (res.lang) for table formatting.

    Source of truth: ``env.user.lang`` → ``res.lang``. It does not depend on
    corporate_terms nor on US/ES defaults hardcoded in the caller.
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
        show_mode = resolve_show_mode_for_render(env, result=result)
        chart_engine = resolve_chart_engine_for_render(env, result=result)
        dual_axis = resolve_dual_axis_for_render(env, result=result)
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
    float_decimals = 2
    try:
        from .engine_params import xlsx_float_decimals
        float_decimals = xlsx_float_decimals(env)
    except Exception as exc:
        _logger.debug('render_context_from_env decimals: %s', exc)
    return {
        'pk_decimal_sep': d_sep,
        'pk_thousands_sep': t_sep,
        'pk_float_decimals': float_decimals,
        'pk_date_format': date_fmt,
        'user_lang': lang,
        'user_tz': user_tz,
        'show_mode': show_mode,
        'chart_engine': chart_engine,
        'dual_axis': dual_axis,
        'env': env,
    }


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


def _flatten_cell_value(val):
    """Nested dict/list → scalar label (never a raw JSON dump)."""
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


def _group_map_payload(grp):
    """Extract per-section page/map fields from a tables/groups entry."""
    if not isinstance(grp, dict):
        return None
    out = {}
    for key in ('page_url', 'map_url', 'pins_url', 'map_pins', 'map_cell'):
        if key in grp and grp[key] is not None:
            out[key] = grp[key]
    return out or None


def _result_groups(result):
    """Detect a grouped structure (sections with title + table).

    Accepted shapes (by priority):

    1. Explicit — ``groups`` / ``sections`` / ``tables``:

        result = {'tables': [
            {'title': 'Por unidades', 'data': [{...}, ...]},
            {'title': 'Por importe', 'data': [{...}, ...]},
        ]}

    2. Implicit — several sibling tabular lists (e.g. the OTBR bug):

        result = {'by_units': [...], 'by_amount': [...]}

       Each key becomes a humanized title. It keeps the 2nd one from
       overwriting the 1st when only ``{'data': …}`` is handed back.

    Returns a list of ``(title, items, opts)`` tuples or None.
    ``opts`` may include ``title_bg`` / ``header_bg`` (pastel header hex)
    and ``map_payload`` (the block's map_url / map_pins, for a per-section banner).
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
    # Auto: by_units + by_amount (or other keys) without a `tables` envelope.
    siblings = _sibling_tabular_lists(result)
    if len(siblings) >= 2:
        return [(_humanize_table_key(k), rows, {}) for k, rows in siblings]
    return None


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
