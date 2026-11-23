# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""The table that gets exported: columns, rows, title, widths, and how one cell value is read."""

from __future__ import annotations


_FILE_VALUE_KEYS = ('datas', 'datas_fname', 'db_datas')


_TITLE_MAX = 120


_CAPTION_MAX = 200


_STEM_MAX = 80


_WIDTH_MIN = 8.0


_WIDTH_MAX = 50.0


_WIDTH_SAMPLE = 80


def _plain_flag(value, max_len):
    if not isinstance(value, str):
        return ''
    text = ' '.join(value.split())
    return text[:max_len]


def export_title(payload=None, fallback='Export'):
    """Interior title from ``__title__`` / stem, else ``fallback``."""
    if isinstance(payload, dict):
        title = _plain_flag(payload.get('__title__'), _TITLE_MAX)
        if title:
            return title
        stem = _plain_flag(payload.get('__filename_stem__'), _STEM_MAX)
        if stem:
            return stem.replace('_', ' ').strip() or (fallback or 'Export')
    return fallback or 'Export'


def has_export_meta(payload=None):
    """True when RelaxAICode named the file (title or stem)."""
    if not isinstance(payload, dict):
        return False
    if _plain_flag(payload.get('__title__'), _TITLE_MAX):
        return True
    return bool(_plain_flag(payload.get('__filename_stem__'), _STEM_MAX))


def sheet_caption(payload=None):
    """One-line Excel caption, or empty (document name is enough)."""
    if not isinstance(payload, dict):
        return ''
    return _plain_flag(payload.get('__sheet_caption__'), _CAPTION_MAX)


def column_labels(payload=None, rows=None):
    """Visible headers: ``__column_labels__`` overlay, else public keys."""
    raw = {}
    if isinstance(payload, dict):
        src = payload.get('__column_labels__')
        if isinstance(src, dict):
            raw = src
    out = {}
    for key in public_columns(rows):
        lab = raw.get(key)
        if lab is None:
            lab = raw.get(str(key))
        if lab not in (None, ''):
            out[key] = str(lab).strip() or str(key)
        else:
            out[key] = str(key)
    return out


def column_widths(rows, labels=None):
    """Excel column widths from header + sampled cell text. No locale list."""
    keys = public_columns(rows)
    labels = labels or {}
    sample = [r for r in (rows or [])[:_WIDTH_SAMPLE] if isinstance(r, dict)]
    widths = []
    for key in keys:
        label = str(labels.get(key) or key)
        longest = len(label)
        numeric = True
        saw_value = False
        for row in sample:
            val = row.get(key)
            if val is None or val == '':
                continue
            saw_value = True
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                numeric = False
            text = _xlsx_plain_text(val) if not isinstance(
                val, (int, float),
            ) or isinstance(val, bool) else ('%s' % val)
            if len(text) > longest:
                longest = len(text)
        width = float(longest + 2)
        if saw_value and numeric:
            width = max(width, 12.0)
        width = min(_WIDTH_MAX, max(_WIDTH_MIN, width))
        widths.append(width)
    return widths


def export_result_chips(result):
    """Download chips from ``apply_requested_exports`` (N or one)."""
    if not isinstance(result, dict) or not result.get('acted'):
        return []
    out = []
    chips = result.get('chips')
    if isinstance(chips, list):
        for chip in chips:
            if isinstance(chip, dict) and (chip.get('url') or chip.get('name')):
                out.append(chip)
    if out:
        return out
    chip = result.get('chip')
    if isinstance(chip, dict) and (chip.get('url') or chip.get('name')):
        return [chip]
    return []


def is_session_file_propose(steps):
    """True when a Safe Plan dumps a file onto orphan ``ir.attachment``.

    Business attachments (``res_model`` = ``res.partner``, invoice, …)
    stay False. Host-testable; no Odoo.
    """
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        op = str(step.get('op') or '').strip().lower()
        if op not in ('create', 'write'):
            continue
        if str(step.get('model') or '').strip() != 'ir.attachment':
            continue
        values = step.get('values')
        if not isinstance(values, dict):
            values = {}
        res_model = values.get('res_model')
        if isinstance(res_model, str):
            res_model = res_model.strip()
        if res_model:
            continue
        if op == 'create':
            return True
        has_file = any(
            values.get(key) not in (None, '', [])
            for key in _FILE_VALUE_KEYS
        )
        if has_file:
            return True
    return False


def public_columns(rows):
    """Column keys that do not start with ``_``, in first-seen order."""
    keys = []
    seen = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        for key in row:
            if str(key).startswith('_'):
                continue
            if key in seen:
                continue
            seen.add(key)
            keys.append(key)
    return keys


def public_rows(rows):
    keys = public_columns(rows)
    if not keys:
        return []
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        item = {k: row.get(k) for k in keys}
        if row.get('_tfoot'):
            item['_tfoot'] = True
        out.append(item)
    return out


def _clip_cell(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (str, int, float)):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    return str(value)


def tabular_rows(payload=None, rows=None):
    """First list-of-dicts from an explicit list or a RelaxAICode payload."""
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return list(rows)
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return list(payload)
    if not isinstance(payload, dict):
        return None
    data = payload.get('data')
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return list(data)
    items = payload.get('items')
    if isinstance(items, list) and items and isinstance(items[0], dict):
        return list(items)
    for envelope in ('groups', 'sections', 'tables'):
        blocks = payload.get(envelope)
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            for key in ('data', 'items', 'rows'):
                nested = block.get(key)
                if isinstance(nested, list) and nested and isinstance(nested[0], dict):
                    return list(nested)
    for key, val in payload.items():
        if str(key).startswith('_'):
            continue
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return list(val)
    return None


def columns_config(rows, labels=None):
    """``format_data_as_excel`` / ``format_data_as_pdf`` tuples."""
    labels = labels or {}
    cfg = []
    for key in public_columns(rows):
        label = labels.get(key)
        cfg.append((key, str(label if label not in (None, '') else key), 'text', 'left'))
    return cfg


def _excel_number(value):
    """Native int/float only. A digit string stays text (ids, codes)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value or value in (float('inf'), float('-inf')):
            return None
        return value
    return None


def _xlsx_col_letter(index):
    """1-based column index → A, B, …, Z, AA."""
    n = int(index)
    letters = []
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters.append(chr(65 + rem))
    return ''.join(reversed(letters)) or 'A'


def _xlsx_plain_text(value):
    if value is None:
        return ''
    text = str(value)
    return ''.join(
        ch for ch in text if ord(ch) >= 32 or ch in '\t\n\r'
    )[:32767]


def _xlsx_safe_text(text):
    """Text a spreadsheet would read as a formula goes out quoted as text."""
    if text and text.lstrip(' \t')[:1] in ('=', '+', '-', '@'):
        return "'" + text
    return text
