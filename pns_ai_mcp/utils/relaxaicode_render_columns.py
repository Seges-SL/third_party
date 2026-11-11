# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""What each table column holds (numbers, booleans, text, chips) and which cell links to the record."""

import html
import re

from .relaxaicode_render_base import (
    _column_is_image,
    _t,
    _TECHNICAL_LINK_KEYS,
)


_NUM_STR_RE = re.compile(
    r'^[\s]*[+-]?'
    r'(?:'
    r'\d{1,3}(?:([.,\s])\d{3})*(?:([.,])\d+)?'  # 1.234.567,89 / 1,234,567.89
    r'|\d+(?:([.,])\d+)?'  # 1234,56 / 1234.56
    r')'
    r'[\s]*$'
)


def _parse_numeric(val):
    """Turn an int/float/numeric str into (number, is_float) or None."""
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
    # Strip spaces (some locales use a thin space for thousands).
    compact = s.replace(' ', '').replace('\u00a0', '')
    # Last . or , = decimal if there is more than one separator or a clear pattern.
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
        # Commas only: decimal if there is exactly one final group of 1–2 digits
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
            compact = compact.replace('.', '')  # 1.234.567 thousands
    try:
        if '.' in compact:
            return (float(compact), True)
        return (int(compact), False)
    except Exception:
        return None


def _column_is_numeric(items, key):
    """True if the column is mostly numeric (types or parseable strings)."""
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


def _column_has_decimals(items, key):
    """True if a sampled cell is a decimal number (float or ``12,50``): 2 decimals for all."""
    for item in items[:25]:
        if isinstance(item, dict):
            parsed = _parse_numeric(item.get(key))
            if parsed is not None and parsed[1]:
                return True
    return False


def _normalize_col_key(key):
    return str(key).lower().replace(' ', '_').replace('-', '_')


def _is_technical_link_key(key):
    key_l = _normalize_col_key(key)
    if key_l in _TECHNICAL_LINK_KEYS:
        return True
    # raw many2one / x2many ids, not labels.
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
    """Column with readable text (not numeric, not bool, not image)."""
    if _column_is_numeric(items, key) or _column_is_boolean(items, key):
        return False
    if _column_is_image(items, key):
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


def _column_is_chip_styled(items, key):
    """True when ``_style_<key>`` paints an inline chip (not a label to link)."""
    for item in items[:25]:
        if not isinstance(item, dict):
            continue
        if _style_is_inline_chip(item.get('_style_' + str(key))):
            return True
    return False


def _select_name_link_keys(keys, items, numeric_keys):
    """Pick ONE column whose value links to the record (no domain hardcode).

    Structural preference:
    1) Odoo canonical fields ``display_name`` / ``name`` if they are text.
    2) Non-meta text column with the **highest cardinality** of values
       (record labels ≈ unique; buckets/filters ≈ few repeated
       values). Tie → row order.
    3) ``id`` column (linking the id is fine; better than a widget).
    4) First column with some displayable value.
    A chip (``display:inline-block`` in ``_style_*``) is a badge, not the
    record label — skip it so the description/name keeps the link.
    """
    by_norm = {_normalize_col_key(k): k for k in keys}
    for preferred in ('display_name', 'name'):
        key = by_norm.get(preferred)
        if (
            key is not None
            and _column_is_textual(items, key)
            and not _column_is_chip_styled(items, key)
        ):
            return {key}
    textual = []
    for key in keys:
        if key in numeric_keys or _is_technical_link_key(key):
            continue
        if _column_is_chip_styled(items, key):
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
        if _column_is_chip_styled(items, key):
            continue
        if _column_has_display_value(items, key):
            return {key}
    return set()


def row_label_for_record(item):
    """Text label of a record row (same preference as namelink).

    Structural: ``display_name`` / ``name`` → first non-meta text → ``id``.
    No domain literals. Returns str or None.
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
    """Row id: accepts ``id`` / ``ID`` (the LLM often capitalizes it)."""
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


def _name_cell_link_html(item, text, inherit_color=False):
    """Link in the name/description text → the record's form."""
    url = _record_form_url(item)
    if not url or text is None or text == '':
        return ''
    if inherit_color:
        link_style = 'color:inherit;text-decoration:none;'
    else:
        link_style = 'color:#0d6efd;text-decoration:underline;'
    return (
        '<a href="%s" target="_blank" rel="noopener" '
        'class="o_ai_namelink" title="%s" '
        'style="%s">%s</a>'
    ) % (url, html.escape(_t('Open record'), quote=True), link_style,
         html.escape(str(text)))


def _style_is_inline_chip(style):
    """``display:inline-block`` in ``_style_*`` → chip inside the cell, not a painted td."""
    return 'inline-block' in str(style or '')
