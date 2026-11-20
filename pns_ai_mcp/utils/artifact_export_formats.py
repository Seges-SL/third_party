# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Each file format (TSV, Markdown, HTML, Word, PDF, xlsx with openpyxl) and the file name."""

from __future__ import annotations
import base64
import html as html_lib
import io
import logging
import re

from .ai_disclosure import HTML_META

from .artifact_export_loader import (
    _load_formatters,
    _load_sibling,
)

from .artifact_export_table import (
    column_widths,
    columns_config,
    _excel_number,
    _plain_flag,
    public_columns,
    public_rows,
    _STEM_MAX,
    _TITLE_MAX,
    _xlsx_plain_text,
    _xlsx_safe_text,
)

from .artifact_export_request import (
    _XLSX_MIME,
)

from .artifact_export_pdf_chart import (
    pdf_chart_series,
)

from .artifact_export_excel_formulas import (
    excel_formulas_from_section,
    _FOOTER_FLAGS,
    infer_footer_rows,
    _plan_xlsx_cells,
    _xlsx_fill_cached,
)

from .artifact_export_xlsx_writer import (
    _as_xlsx_ooxml_book,
    _unique_sheet_title,
    _xlsx_cell_number_format,
    xlsx_number_style,
    _xlsx_photo_col_chars,
    _xlsx_sheet_photos,
)

_logger = logging.getLogger(__name__)


def serialize_rows(rows, kind, title='Export', landscape=True, labels=None,
                   caption=None, env=None, html=None, charts=True,
                   formulas=None):
    """Return bytes for ``kind`` (txt/md/html/xlsx/pdf/doc), or None."""
    public = public_rows(rows)
    kind = (kind or '').lower()
    labels = labels or {}
    if kind == 'doc':
        return _as_word_html(
            public, title, labels=labels, html=html, env=env,
        )
    if not public:
        return None
    if kind == 'txt':
        return _as_tsv(public).encode('utf-8')
    if kind == 'md':
        return _as_markdown(public, title=title, labels=labels).encode('utf-8')
    if kind == 'html':
        return _as_html(public, title, labels=labels).encode('utf-8')
    if kind == 'xlsx':
        return _as_xlsx(
            public, title, labels=labels, caption=caption, formulas=formulas,
            number_style=xlsx_number_style(env), env=env,
        )
    if kind == 'pdf':
        return _as_pdf(
            public, title, landscape=landscape, labels=labels, env=env,
            charts=charts,
        )
    return None


def _slug_stem(text):
    try:
        svg = _load_sibling('svg_download.py', '_ae_svg_download')
        slug = svg._slug(text or '')
        if slug:
            return slug[:_STEM_MAX]
    except Exception:
        _logger.debug('artifact_export: slug fallback', exc_info=True)
    slug = re.sub(r'[^A-Za-z0-9]+', '_', str(text or '')).strip('_').lower()
    return slug[:_STEM_MAX]


def export_filename(prompt, ext, fallback='export', payload=None, title=None):
    """Prefer payload stem/title; else slug the utterance."""
    ext = (ext or 'bin').lstrip('.').lower() or 'bin'
    stem = ''
    if isinstance(payload, dict):
        stem = _slug_stem(_plain_flag(payload.get('__filename_stem__'), _STEM_MAX))
        if not stem:
            stem = _slug_stem(_plain_flag(payload.get('__title__'), _TITLE_MAX))
    if not stem and title:
        stem = _slug_stem(title)
    if stem:
        return '%s.%s' % (stem, ext)
    try:
        svg = _load_sibling('svg_download.py', '_ae_svg_download')
        name = svg.utterance_filename(
            prompt=prompt or '',
            ext=ext,
            fallback=fallback,
        )
        if name:
            return name
    except Exception:
        _logger.debug('artifact_export: utterance_filename fallback', exc_info=True)
    return '%s.%s' % ((fallback or 'export'), ext)


def _as_tsv(rows):
    keys = public_columns(rows)
    lines = ['\t'.join(_cell(k) for k in keys)]
    for row in rows:
        lines.append('\t'.join(_cell(row.get(k)) for k in keys))
    return '\n'.join(lines) + '\n'


def _as_markdown(rows, title=None, labels=None):
    keys = public_columns(rows)
    labels = labels or {}
    heads = [_cell(labels.get(k) or k) for k in keys]
    header = '| ' + ' | '.join(heads) + ' |'
    sep = '| ' + ' | '.join('---' for _k in keys) + ' |'
    body = [
        '| ' + ' | '.join(_cell(row.get(k)) for k in keys) + ' |'
        for row in rows
    ]
    parts = []
    if title:
        parts.append('# %s' % _cell(title))
        parts.append('')
    parts.extend([header, sep] + body)
    return '\n'.join(parts) + '\n'


def _as_html(rows, title, labels=None):
    keys = public_columns(rows)
    labels = labels or {}
    title_h = html_lib.escape(str(title or 'Export'))
    thead = ''.join(
        '<th>%s</th>' % html_lib.escape(_cell(labels.get(k) or k))
        for k in keys
    )
    body_rows = []
    for row in rows:
        tds = ''.join(
            '<td>%s</td>' % html_lib.escape(_cell(row.get(k))) for k in keys
        )
        body_rows.append('<tr>%s</tr>' % tds)
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"/>%s'
        '<title>%s</title></head><body><h1>%s</h1>'
        '<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
        '</body></html>'
    ) % (HTML_META, title_h, title_h, thead, ''.join(body_rows))


_WORD_KILL_CLASS_RE = re.compile(
    r'class="[^"]*(?:o_ai_chart_toolbar|o_ai_export_bar|'
    r'o_ai_copy_btn|o_ai_noexport|o_ai_ts|'
    r'o_ai_chart_host|o_ai_echarts_surface|echarts-tooltip)[^"]*"',
    re.I,
)


_WORD_TAG_RE = re.compile(r'<(/?)([a-zA-Z][\w:-]*)([^>]*)>', re.S)


_WORD_VOID = frozenset((
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
    'link', 'meta', 'param', 'source', 'track', 'wbr',
))


_WORD_SCRIPT_RE = re.compile(r'<script[\s\S]*?</script>', re.I)


_WORD_STYLE = (
    'body{font-family:Helvetica,Arial,sans-serif;color:#1a1a1a;font-size:11pt;}'
    'h1{font-size:16pt;color:#1a1a1a;margin:0 0 12pt;}'
    'table{border-collapse:collapse;width:100%;}'
    'th{background:#eceff1;color:#1a1a1a;font-weight:bold;'
    'padding:6px 8px;border:0.5pt solid #c8c8c8;text-align:left;}'
    'td{padding:5px 8px;border:0.5pt solid #c8c8c8;color:#282828;'
    'vertical-align:middle;}'
    'tr:nth-child(even) td{background:#f8f9fa;}'
    'td img{max-width:72px;max-height:72px;}'
    'p.o_ai_word_figure img{max-width:100%;width:100%;height:auto;}'
)


def _word_matching_close(text, start, name):
    """Index after the close tag that matches ``name`` at ``start``."""
    depth = 1
    name_l = name.lower()
    for match in _WORD_TAG_RE.finditer(text, start):
        slash, other, attrs = match.group(1), match.group(2), match.group(3)
        if other.lower() != name_l:
            continue
        if slash:
            depth -= 1
            if depth == 0:
                return match.end()
            continue
        if (attrs or '').rstrip().endswith('/') or other.lower() in _WORD_VOID:
            continue
        depth += 1
    return len(text)


def _word_strip_kill_nodes(html):
    """Drop chart chrome / tooltips with matching close tags (not first ``</``)."""
    text = str(html or '')
    while True:
        found = None
        for match in _WORD_TAG_RE.finditer(text):
            slash, name, attrs = match.group(1), match.group(2), match.group(3)
            if slash or not _WORD_KILL_CLASS_RE.search(attrs or ''):
                continue
            if (attrs or '').rstrip().endswith('/') or name.lower() in _WORD_VOID:
                found = (match.start(), match.end())
                break
            end = _word_matching_close(text, match.end(), name)
            found = (match.start(), end)
            break
        if not found:
            return text
        text = text[:found[0]] + text[found[1]:]


def _word_sanitize_html(html):
    text = str(html or '')
    text = _WORD_SCRIPT_RE.sub('', text)
    text = _word_strip_kill_nodes(text)
    return text.strip()


def _word_wrap(title, body):
    title_h = html_lib.escape(str(title or 'Export'))
    return (
        '<html xmlns:o="urn:schemas-microsoft-com:office:office" '
        'xmlns:w="urn:schemas-microsoft-com:office:word">'
        '<head><meta charset="utf-8"/>%s<title>%s</title>'
        '<style>%s</style></head><body>%s</body></html>'
    ) % (HTML_META, title_h, _WORD_STYLE, body)


def _word_cell_html(value, key, env=None):
    fmt = _load_formatters()
    if fmt is not None:
        reader = getattr(fmt, '_pdf_image_bytes', None)
        if callable(reader):
            raw = reader(value, key=key, env=env)
            if raw:
                import base64
                b64 = base64.b64encode(raw).decode('ascii')
                return '<img src="data:image/png;base64,%s" alt=""/>' % b64
        skip = getattr(fmt, '_pdf_is_image_ref', None)
        if callable(skip) and skip(value):
            return ''
    return html_lib.escape(_cell(value))


def _word_table_html(rows, title, labels=None, env=None):
    rows = _printed_rows(rows, env)
    keys = public_columns(rows)
    labels = labels or {}
    title_h = html_lib.escape(str(title or 'Export'))
    thead = ''.join(
        '<th>%s</th>' % html_lib.escape(_cell(labels.get(k) or k))
        for k in keys
    )
    body_rows = []
    for row in rows:
        tds = ''.join(
            '<td>%s</td>' % _word_cell_html(row.get(k), k, env=env)
            for k in keys
        )
        body_rows.append('<tr>%s</tr>' % tds)
    return (
        '<h1>%s</h1><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
    ) % (title_h, thead, ''.join(body_rows))


def _as_word_html(rows, title, labels=None, html=None, env=None):
    """Office Word HTML (.doc). Rich body or chat table. No new deps."""
    body = ''
    if html and str(html).strip():
        body = _word_sanitize_html(html)
        if body and '<h1' not in body.lower() and title:
            body = '<h1>%s</h1>%s' % (
                html_lib.escape(str(title)), body,
            )
    elif rows:
        body = _word_table_html(rows, title, labels=labels, env=env)
    if not body:
        return None
    return _word_wrap(title, body).encode('utf-8')


_MAX_XLSX_SHEETS = 32


_MAX_XLSX_ROWS = 20000


_MAX_XLSX_COLS = 256


def _as_xlsx(rows, title, labels=None, caption=None, formulas=None,
             number_style=None, env=None):
    """Prefer styled openpyxl; always fall back to stdlib OOXML."""
    return serialize_xlsx_sheets([{
        'title': title,
        'rows': rows,
        'labels': labels,
        'caption': caption,
        'formulas': formulas,
    }], number_style=number_style, env=env)


def serialize_xlsx_sheets(sheets, number_style=None, env=None):
    """One workbook from ``[{title, rows, labels, caption}]``."""
    specs = _normalize_xlsx_sheets(sheets)
    if not specs:
        return None
    style = number_style or xlsx_number_style(env)
    for spec in specs:
        spec['number_style'] = spec.get('number_style') or style
        spec['env'] = env
    fmt = _load_formatters()
    if fmt is not None and hasattr(fmt, 'format_excel_workbook'):
        try:
            raw = fmt.format_excel_workbook([
                {
                    'data': spec['rows'],
                    'columns_config': spec['cfg'],
                    'title': spec['title'],
                    'include_row_index': False,
                    'caption': spec['caption'] or None,
                    'widths': spec['widths'],
                    'cell_formulas': _cell_formulas(spec),
                    'number_style': spec.get('number_style') or style,
                    'env': env,
                }
                for spec in specs
            ])
            coerced = _coerce_xlsx_bytes(raw)
            if coerced:
                return _xlsx_fill_cached(coerced, specs)
        except Exception:
            _logger.debug(
                'artifact_export: format_excel_workbook failed', exc_info=True,
            )
    if fmt is not None and len(specs) == 1:
        spec = specs[0]
        try:
            raw = fmt.format_data_as_excel(
                spec['rows'], spec['cfg'], title=spec['title'],
                include_row_index=False, caption=spec['caption'] or None,
                widths=spec['widths'],
                cell_formulas=_cell_formulas(spec),
                number_style=spec.get('number_style') or style,
            )
            coerced = _coerce_xlsx_bytes(raw)
            if coerced:
                return _xlsx_fill_cached(coerced, specs)
        except Exception:
            _logger.debug(
                'artifact_export: format_data_as_excel failed', exc_info=True,
            )
    try:
        raw = _as_xlsx_openpyxl_book(specs)
        coerced = _coerce_xlsx_bytes(raw)
        if coerced:
            return _xlsx_fill_cached(coerced, specs)
    except ImportError:
        _logger.info(
            'artifact_export: openpyxl not installed; using stdlib xlsx',
        )
    except Exception:
        _logger.debug('artifact_export: openpyxl write failed', exc_info=True)
    try:
        return _as_xlsx_ooxml_book(specs)
    except Exception:
        _logger.warning('artifact_export: stdlib xlsx failed', exc_info=True)
        return None


def _cell_formulas(spec):
    return {pos: formula for pos, (formula, _v) in (spec.get('cells') or {}).items()}


def sheets_from_aoa_sections(sections):
    """Icon payload ``[{title, aoa}]`` → serialize_xlsx_sheets specs."""
    out = []
    used = set()
    for spec in (sections or [])[:_MAX_XLSX_SHEETS]:
        if not isinstance(spec, dict):
            continue
        rows_in = spec.get('rows')
        if (
            isinstance(rows_in, list)
            and rows_in
            and isinstance(rows_in[0], dict)
        ):
            rows = public_rows(rows_in[:_MAX_XLSX_ROWS])
            labels = spec.get('labels') or {
                k: str(k) for k in public_columns(rows)
            }
            if not (rows or labels):
                continue
            item = {
                'title': _unique_sheet_title(spec.get('title'), used),
                'rows': rows,
                'labels': labels,
                'caption': (spec.get('caption') or '').strip(),
            }
            formulas = excel_formulas_from_section(spec)
            if formulas:
                item['formulas'] = formulas
            out.append(item)
            continue
        aoa = spec.get('aoa')
        parsed = _sheet_from_aoa(aoa, spec.get('title'), used)
        if parsed:
            parsed['caption'] = (spec.get('caption') or '').strip()
            formulas = excel_formulas_from_section(spec)
            if formulas:
                parsed['formulas'] = formulas
            out.append(parsed)
    return out


def icon_xlsx_payload(sections, filename=None, env=None):
    """Base64 download dict for the chat Excel icon, or None."""
    raw = serialize_xlsx_sheets(
        sheets_from_aoa_sections(sections), env=env,
    )
    if not raw:
        return None
    return {
        'filename': _safe_xlsx_filename(filename),
        'mimetype': _XLSX_MIME,
        'datas': base64.b64encode(raw).decode('ascii'),
    }


def _sheet_from_aoa(aoa, title, used):
    if not isinstance(aoa, list) or not aoa:
        return None
    header = [_aoa_cell(c) for c in (aoa[0] or [])][:_MAX_XLSX_COLS]
    keys = []
    seen = {}
    labels = {}
    for idx, raw_h in enumerate(header):
        label = str(raw_h).strip() if raw_h not in (None, '') else ''
        key = label or ('Col%d' % (idx + 1))
        n = seen.get(key, 0)
        seen[key] = n + 1
        if n:
            key = '%s_%d' % (key, n + 1)
        keys.append(key)
        labels[key] = label or key
    if not keys:
        return None
    rows = []
    for raw in aoa[1:_MAX_XLSX_ROWS + 1]:
        if not isinstance(raw, (list, tuple)):
            continue
        row = {}
        for idx, key in enumerate(keys):
            row[key] = _aoa_cell(raw[idx]) if idx < len(raw) else ''
        rows.append(row)
    return {
        'title': _unique_sheet_title(title, used),
        'rows': rows,
        'labels': labels,
    }


def _aoa_cell(value):
    if isinstance(value, dict):
        if 'content' in value:
            return value.get('content')
        return ''
    return value


def _safe_xlsx_filename(filename):
    text = str(filename or '').strip() or 'export'
    text = text.replace('\\', '/').split('/')[-1]
    if '.' in text:
        text = text.rsplit('.', 1)[0]
    stem = _slug_stem(text) or 'export'
    return '%s.xlsx' % stem


def _normalize_xlsx_sheets(sheets):
    specs = []
    used = set()
    for spec in (sheets or [])[:_MAX_XLSX_SHEETS]:
        if not isinstance(spec, dict):
            continue
        labels_in = spec.get('labels') or {}
        rows = public_rows((spec.get('rows') or [])[:_MAX_XLSX_ROWS])
        keys = public_columns(rows)
        if not keys:
            keys = [
                k for k in labels_in
                if not str(k).startswith('_')
            ][:_MAX_XLSX_COLS]
        if not keys:
            continue
        labels = {
            k: str(labels_in.get(k) or k) for k in keys
        }
        widths = spec.get('widths') or column_widths(
            rows or [{k: labels[k] for k in keys}], labels,
        )
        typed = []
        for row in rows:
            item = {k: _excel_typed(row.get(k)) for k in keys}
            for flag in _FOOTER_FLAGS:
                if row.get(flag):
                    item[flag] = True
            typed.append(item)
        infer_footer_rows(typed, keys)
        formulas = excel_formulas_from_section(spec)
        if formulas:
            formulas = {k: formulas[k] for k in keys if k in formulas}
        item = {
            'title': _unique_sheet_title(spec.get('title'), used),
            'rows': typed,
            'labels': labels,
            'caption': (spec.get('caption') or '').strip(),
            'widths': widths,
            'keys': keys,
            'cfg': columns_config(typed or [{k: '' for k in keys}], labels),
            'formulas': formulas,
        }
        item['cells'] = _plan_xlsx_cells(item)
        specs.append(item)
    return specs


def _as_xlsx_openpyxl_book(specs):
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter

    fmt = _load_formatters()
    wb = Workbook()
    first = True
    for spec in specs:
        if first:
            ws = wb.active
            first = False
        else:
            ws = wb.create_sheet()
        photos, photo_cols = _xlsx_sheet_photos(spec, fmt)
        ws.title = spec['title']
        keys = spec['keys']
        labels = spec['labels']
        caption = spec['caption']
        header_row = 2 if caption else 1
        if caption:
            ws.merge_cells(
                start_row=1, start_column=1,
                end_row=1, end_column=max(1, len(keys)),
            )
            ws.cell(row=1, column=1, value=_xlsx_plain_text(caption))
        for col, key in enumerate(keys, 1):
            ws.cell(
                row=header_row, column=col,
                value=str(labels.get(key) or key),
            )
        plan = spec.get('cells') or {}
        style = spec.get('number_style') or xlsx_number_style()
        for ridx, row in enumerate(spec['rows'], header_row + 1):
            if photo_cols:
                ws.row_dimensions[ridx].height = fmt._XLSX_IMG_ROW_PT
            for col, key in enumerate(keys, 1):
                if col in photo_cols:
                    photo = photos.get((ridx, col))
                    if photo:
                        fmt._excel_put_photo(
                            ws, photo, ridx, col,
                            _xlsx_photo_col_chars(spec, col, fmt),
                        )
                    continue
                compiled = (plan.get((ridx, col)) or (None,))[0]
                value = compiled if compiled else _excel_value(row.get(key))
                cell = ws.cell(row=ridx, column=col, value=value)
                num_fmt = _xlsx_cell_number_format(
                    value if not compiled else None,
                    formula=compiled, style=style,
                )
                if num_fmt:
                    cell.number_format = num_fmt
        for col, width in enumerate(spec['widths'], 1):
            if col in photo_cols:
                width = _xlsx_photo_col_chars(spec, col, fmt)
            ws.column_dimensions[get_column_letter(col)].width = width
        ws.freeze_panes = 'A%d' % (header_row + 1)
    fmt.mark_ai_workbook(wb)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _as_pdf(rows, title, landscape=True, labels=None, env=None, charts=True):
    fmt = _load_formatters()
    cfg = columns_config(rows, labels)
    chart_series = pdf_chart_series(rows, labels) if charts else None
    rows = _printed_rows(rows, env)
    if fmt is not None:
        try:
            return fmt.format_data_as_pdf(
                rows, cfg, title=title or 'Export', landscape=landscape,
                env=env, chart_series=chart_series,
            )
        except TypeError:
            try:
                return fmt.format_data_as_pdf(
                    rows, cfg, title=title or 'Export', landscape=landscape,
                    env=env,
                )
            except TypeError:
                try:
                    return fmt.format_data_as_pdf(
                        rows, cfg, title=title or 'Export', landscape=landscape,
                    )
                except TypeError:
                    try:
                        return fmt.format_data_as_pdf(
                            rows, cfg, title=title or 'Export',
                        )
                    except Exception:
                        _logger.debug(
                            'artifact_export: format_data_as_pdf failed',
                            exc_info=True,
                        )
                except Exception:
                    _logger.debug(
                        'artifact_export: format_data_as_pdf failed',
                        exc_info=True,
                    )
            except Exception:
                _logger.debug('artifact_export: format_data_as_pdf failed', exc_info=True)
        except Exception:
            _logger.debug('artifact_export: format_data_as_pdf failed', exc_info=True)
    return None


def _excel_typed(value):
    number = _excel_number(value)
    return value if number is None else number


def _excel_value(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return value
    number = _excel_number(value)
    if number is not None:
        return number
    return _xlsx_safe_text(_xlsx_plain_text(value))


def _coerce_xlsx_bytes(raw):
    """Accept bytes / bytearray / BytesIO; require a ZIP signature."""
    if hasattr(raw, 'getvalue') and not isinstance(raw, (bytes, bytearray)):
        try:
            raw.seek(0)
        except Exception:
            pass
        try:
            raw = raw.getvalue()
        except Exception:
            return None
    if isinstance(raw, memoryview):
        raw = raw.tobytes()
    if isinstance(raw, bytearray):
        raw = bytes(raw)
    if isinstance(raw, bytes) and raw[:2] == b'PK':
        return raw
    return None


def _printed_rows(rows, env=None):
    """Rows as the chat table prints them: a decimal column carries the
    configured decimals with the user's separators. Integers and text stay."""
    try:
        from .relaxaicode_render import (
            _column_has_decimals,
            _fmt_number,
            render_context_from_env,
        )
    except Exception:
        return rows
    keys = [k for k in public_columns(rows) if _column_has_decimals(rows, k)]
    if not keys:
        return rows
    ctx = {}
    if env is not None:
        try:
            ctx = render_context_from_env(env) or {}
        except Exception:
            ctx = {}
    d_sep = ctx.get('pk_decimal_sep', '.')
    t_sep = ctx.get('pk_thousands_sep', ',')
    decimals = ctx.get('pk_float_decimals', 2)
    out = []
    for row in rows:
        if not isinstance(row, dict):
            out.append(row)
            continue
        row = dict(row)
        for key in keys:
            if _excel_number(row.get(key)) is not None:
                row[key] = _fmt_number(row[key], d_sep, t_sep, decimals=decimals)
        out.append(row)
    return out


def _cell(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    text = str(value).replace('\t', ' ').replace('\n', ' ')
    return text
