# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Deterministic file export from tabular rows (no LLM, no domain literals).

When the user names a known download format, serialize public columns to
bytes. Word is Office HTML (``.doc``). PowerPoint stays refused.
Host-testable without Odoo.
"""

from __future__ import annotations
from .engine_params import (
    ICP_XLSX_FLOAT_DECIMALS,
    ICP_XLSX_THOUSANDS,
)

from .artifact_export_loader import (
    _load_formatters,
)

from .artifact_export_table import (
    _clip_cell,
    column_labels,
    column_widths,
    _excel_number,
    export_result_chips,
    export_title,
    has_export_meta,
    is_session_file_propose,
    public_columns,
    public_rows,
    sheet_caption,
    tabular_rows,
    _xlsx_col_letter,
    _xlsx_safe_text,
)

from .artifact_export_request import (
    CLIENT_ASSEMBLED_KINDS,
    clip_include_table,
    export_hides_on_screen_table,
    is_refused_export,
    merge_refused_note,
    parse_requested_export,
    payload_allows_charts,
    payload_formatted_html,
    payload_has_report_outline,
    pdf_landscape,
    REFUSED_EXPORT_REPLY,
    REFUSED_PARTIAL_REPLY,
    requested_named_format,
    SESSION_FILE_ATTACHED_NOTE,
    SESSION_FILE_META_PROTOCOL,
    SESSION_FILE_PROPOSE_ERROR,
    SESSION_FILE_PROTOCOL,
    SESSION_FILE_REPORT_NOTE,
    turn_export_utterance,
    wants_on_screen_table,
    wants_rich_doc,
    _XLSX_MIME,
)

from .artifact_export_pdf_chart import (
    clip_include_chart,
    coerce_chart_number,
    pdf_chart_series,
    wants_on_screen_blocks,
)

from .artifact_export_excel_formulas import (
    compile_excel_formula,
    excel_formulas_from_payload,
    infer_excel_formulas,
)

from .artifact_export_xlsx_writer import (
    _as_xlsx_ooxml_book,
    xlsx_number_format,
    xlsx_number_style,
)

from .artifact_export_formats import (
    _as_pdf,
    _as_xlsx,
    _as_xlsx_openpyxl_book,
    _excel_typed,
    _excel_value,
    export_filename,
    icon_xlsx_payload,
    _normalize_xlsx_sheets,
    _printed_rows,
    serialize_rows,
    serialize_xlsx_sheets,
    sheets_from_aoa_sections,
    _word_sanitize_html,
    _word_table_html,
)


def clip_data_from_payload(payload=None, rows=None):
    """JSON rows for bubble clip icons (same shape as data-ai-dataset)."""
    public = public_rows(tabular_rows(payload, rows))
    if not public:
        return None
    rows_out = []
    for row in public:
        item = {}
        for key, val in row.items():
            cell = _clip_cell(val)
            if cell is not None or val is None:
                item[key] = cell
        if item:
            rows_out.append(item)
    if not rows_out:
        return None
    title = export_title(payload, fallback='')
    out = {
        'rows': rows_out,
        'landscape': bool(pdf_landscape(payload, rows=rows_out)),
        'include_table': clip_include_table(payload),
        'include_chart': clip_include_chart(payload, rows_out),
    }
    if title and title != 'Export':
        out['title'] = title
    formulas = excel_formulas_from_payload(payload)
    if formulas:
        out['excel_formulas'] = formulas
    if isinstance(payload, dict):
        src = payload.get('__column_labels__')
        if isinstance(src, dict) and src:
            labels = {}
            for key in public_columns(rows_out):
                lab = src.get(key)
                if lab is None:
                    lab = src.get(str(key))
                if lab not in (None, ''):
                    labels[key] = str(lab).strip()
            if labels:
                out['column_labels'] = labels
    return out


def _parsed_format_specs(parsed):
    """Unique format dicts in appearance order (compat: first hit)."""
    if not parsed:
        return []
    specs = parsed.get('formats')
    if isinstance(specs, list) and specs:
        return [s for s in specs if isinstance(s, dict) and s.get('kind')]
    if parsed.get('format') and not parsed.get('refused'):
        return [parsed]
    return []


def apply_requested_exports(
    user_message,
    rows=None,
    payload=None,
    persist=None,
    prompt=None,
    env=None,
    client_fulfill=False,
):
    """Parse + serialize every unique kind + optional persist.

    One chip per serializable kind; refused tokens stay on the result
    without blocking the rest. Never raises for bad utterances.
    ``persist(raw, filename, mimetype) -> chip|None``. When omitted
    (host tests), a synthetic chip is returned per kind.

    ``client_fulfill``: Word / PDF / HTML become pending chips. The host
    assembles the real file (table + painted chart) and replaces them.
    Excel and Markdown still serialize here.
    """
    empty = {
        'parsed': None,
        'acted': False,
        'chip': None,
        'chips': [],
        'raw': None,
        'filename': None,
        'refused_tokens': [],
    }
    parsed = parse_requested_export(user_message)
    empty['parsed'] = parsed
    if parsed:
        empty['refused_tokens'] = list(parsed.get('refused_tokens') or [])
    specs = _parsed_format_specs(parsed)
    if not specs:
        return empty
    row_list = tabular_rows(payload, rows)
    public = public_rows(row_list)
    html_body = payload_formatted_html(payload)
    rich = wants_rich_doc(payload)
    has_doc = any(s.get('kind') == 'doc' for s in specs)
    if not public:
        if not (rich and html_body and has_doc):
            return empty
        specs = [s for s in specs if s.get('kind') == 'doc']
    title = export_title(payload, fallback='Export')
    labels = column_labels(payload, public)
    caption = sheet_caption(payload)
    formulas = excel_formulas_from_payload(payload)
    landscape = pdf_landscape(
        payload,
        col_count=len(public_columns(public)) if public else None,
        rows=public,
    )
    chips = []
    last_raw = None
    last_filename = None
    for spec in specs:
        filename = export_filename(
            prompt or user_message, spec['ext'],
            payload=payload, title=title,
        )
        if client_fulfill and spec.get('kind') in CLIENT_ASSEMBLED_KINDS:
            chip = {
                'name': filename,
                'mimetype': spec['mimetype'],
                'size': 0,
                'pending': True,
                'fulfill': spec['kind'],
                'source': 'download',
            }
            chips.append(chip)
            last_filename = filename
            continue
        extra_html = html_body if (spec.get('kind') == 'doc' and rich) else None
        raw = serialize_rows(
            public, spec['kind'], title=title,
            landscape=landscape, labels=labels, caption=caption, env=env,
            html=extra_html,
            charts=payload_allows_charts(payload),
            formulas=formulas if spec.get('kind') == 'xlsx' else None,
        )
        if not raw:
            continue
        chip = None
        if persist is not None:
            chip = persist(raw, filename, spec['mimetype'])
            if not chip:
                continue
        else:
            chip = {
                'name': filename,
                'url': '#',
                'mimetype': spec['mimetype'],
                'size': len(raw),
            }
        chips.append(chip)
        last_raw = raw
        last_filename = filename
    if not chips:
        return empty
    return {
        'parsed': parsed,
        'acted': True,
        'chip': chips[0],
        'chips': chips,
        'raw': last_raw,
        'filename': last_filename,
        'refused_tokens': list(parsed.get('refused_tokens') or []),
    }
