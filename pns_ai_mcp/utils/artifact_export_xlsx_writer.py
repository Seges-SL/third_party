# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""The xlsx written by hand: sheets, number formats, sheet names, frozen header, formulas and photos."""

from __future__ import annotations
import html as html_lib
import io
import re
import zipfile
from . import engine_params
from .engine_params import (
    DEFAULT_XLSX_FLOAT_DECIMALS,
    DEFAULT_XLSX_THOUSANDS,
    XLSX_FLOAT_DECIMALS_MAX,
)

from .ai_disclosure import (
    OOXML_CORE_PART,
    OOXML_CORE_REL,
    OOXML_CORE_TYPE,
    OOXML_CORE_XML,
)

from .artifact_export_loader import (
    _load_formatters,
)

from .artifact_export_table import (
    _excel_number,
    _xlsx_col_letter,
    _xlsx_plain_text,
    _xlsx_safe_text,
)


def xlsx_number_format(decimals, thousands, kind):
    """Excel format code. ``kind`` is ``int`` or ``float`` (formulas use float)."""
    try:
        n = int(decimals)
    except (TypeError, ValueError):
        n = DEFAULT_XLSX_FLOAT_DECIMALS
    n = max(0, min(XLSX_FLOAT_DECIMALS_MAX, n))
    prefix = '#,##0' if thousands else '0'
    if kind == 'int':
        return prefix
    return prefix if n == 0 else '%s.%s' % (prefix, '0' * n)


def xlsx_number_style(env=None):
    """``int_format`` / ``float_format`` from the engine parameters, or defaults."""
    decimals = DEFAULT_XLSX_FLOAT_DECIMALS
    thousands = DEFAULT_XLSX_THOUSANDS
    if env is not None:
        try:
            decimals = engine_params.xlsx_float_decimals(env)
            thousands = engine_params.xlsx_thousands(env)
        except Exception:
            decimals = DEFAULT_XLSX_FLOAT_DECIMALS
            thousands = DEFAULT_XLSX_THOUSANDS
    thousands = bool(thousands)
    return {
        'decimals': decimals,
        'thousands': thousands,
        'int_format': xlsx_number_format(decimals, thousands, 'int'),
        'float_format': xlsx_number_format(decimals, thousands, 'float'),
    }


def _xlsx_cell_number_format(value, formula=None, style=None):
    style = style or xlsx_number_style()
    if formula:
        return style['float_format']
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return style['int_format']
    if isinstance(value, float):
        return style['float_format']
    return None


_XLSX_SHEET_BAD = re.compile(r'[:\\/\?\*\[\]]')


_XLSX_NS_MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


_XLSX_NS_PKG_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'


_XLSX_NS_OD_REL = (
    'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
)


_XLSX_NS_TYPES = 'http://schemas.openxmlformats.org/package/2006/content-types'


_XLSX_NS_XDR = (
    'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing'
)


_XLSX_NS_A = 'http://schemas.openxmlformats.org/drawingml/2006/main'


_XLSX_EMU_PER_PX = 9525


def _xlsx_sheet_title(title):
    name = _XLSX_SHEET_BAD.sub(' ', str(title or 'Export')).strip() or 'Export'
    name = name.strip("'") or 'Export'
    return name[:31]


def _unique_sheet_title(title, used):
    base = _xlsx_sheet_title(title)
    name = base
    n = 1
    while name in used:
        suffix = '_%d' % n
        name = (base[:max(1, 31 - len(suffix))] + suffix)[:31]
        n += 1
    used.add(name)
    return name


def _xlsx_frozen_header_xml(header_row):
    """Freeze every row above the first data row (caption + column names)."""
    split = int(header_row)
    return (
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="%d" topLeftCell="A%d" '
        'activePane="bottomLeft" state="frozen"/>'
        '</sheetView></sheetViews>'
    ) % (split, split + 1)


def _xlsx_xml_text(value):
    return html_lib.escape(_xlsx_plain_text(value), quote=True)


def _xlsx_num_style_index(value, formula=None, number_style=None):
    """0 general, 1 integer, 2 float/formula."""
    if not number_style:
        return 0
    if formula:
        return 2
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return 1
    if isinstance(value, float):
        return 2
    return 0


def _xlsx_style_attr(index):
    return ' s="%d"' % index if index else ''


def _xlsx_formula_cell_xml(col, row, formula, cached=None, style=0):
    ref = '%s%s' % (_xlsx_col_letter(col), row)
    body = formula[1:] if str(formula).startswith('=') else str(formula)
    fxml = html_lib.escape(body, quote=True)
    s_attr = _xlsx_style_attr(style)
    number = _excel_number(cached)
    if number is not None:
        if isinstance(number, float):
            cached_xml = repr(number)
        else:
            cached_xml = '%d' % number
        return '<c r="%s"%s><f>%s</f><v>%s</v></c>' % (
            ref, s_attr, fxml, cached_xml,
        )
    return '<c r="%s"%s><f>%s</f></c>' % (ref, s_attr, fxml)


def _xlsx_cell_xml(col, row, value, formula=None, number_style=None):
    style = _xlsx_num_style_index(
        value, formula=formula, number_style=number_style,
    )
    if formula:
        return _xlsx_formula_cell_xml(
            col, row, formula, cached=value, style=style,
        )
    ref = '%s%s' % (_xlsx_col_letter(col), row)
    s_attr = _xlsx_style_attr(style)
    if isinstance(value, bool):
        return '<c r="%s"%s t="b"><v>%d</v></c>' % (
            ref, s_attr, 1 if value else 0,
        )
    if isinstance(value, int) and not isinstance(value, bool):
        return '<c r="%s"%s><v>%d</v></c>' % (ref, s_attr, value)
    if isinstance(value, float):
        if value != value or value in (float('inf'), float('-inf')):
            value = ''
        else:
            return '<c r="%s"%s><v>%s</v></c>' % (ref, s_attr, repr(value))
    text = _xlsx_xml_text(_xlsx_safe_text(_xlsx_plain_text(value)))
    return (
        '<c r="%s" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>'
        % (ref, text)
    )


def _xlsx_styles_xml(number_style=None):
    style = number_style or xlsx_number_style()
    int_fmt = html_lib.escape(style['int_format'], quote=True)
    float_fmt = html_lib.escape(style['float_format'], quote=True)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="%s">'
        '<numFmts count="2">'
        '<numFmt numFmtId="164" formatCode="%s"/>'
        '<numFmt numFmtId="165" formatCode="%s"/>'
        '</numFmts>'
        '<fonts count="1"><font/></fonts>'
        '<fills count="2">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '</fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
        '</cellStyleXfs>'
        '<cellXfs count="3">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0"'
        ' applyNumberFormat="1"/>'
        '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0"'
        ' applyNumberFormat="1"/>'
        '</cellXfs>'
        '<cellStyles count="1">'
        '<cellStyle name="Normal" xfId="0" builtinId="0"/>'
        '</cellStyles>'
        '</styleSheet>'
    ) % (_XLSX_NS_MAIN, int_fmt, float_fmt)


def _xlsx_sheet_photos(spec, fmt):
    """``({(row, col): (png, w, h)}, photo columns)`` for the stdlib writer."""
    if fmt is None or not hasattr(fmt, '_excel_photo_png'):
        return {}, set()
    keys = spec['keys']
    rows = spec['rows'] or []
    cols = {
        col for col, key in enumerate(keys, 1)
        if any(
            isinstance(row, dict) and fmt._pdf_is_image_ref(row.get(key))
            for row in rows
        )
    }
    if not cols:
        return {}, set()
    header_row = 2 if spec['caption'] else 1
    photos = {}
    for ridx, row in enumerate(rows, header_row + 1):
        if not isinstance(row, dict):
            continue
        for col in cols:
            photo = fmt._excel_photo_png(row.get(keys[col - 1]), spec.get('env'))
            if photo:
                photos[(ridx, col)] = photo
    return photos, cols


def _xlsx_photo_col_chars(spec, col, fmt):
    keys = spec['keys']
    key = keys[col - 1] if col <= len(keys) else ''
    return fmt._excel_photo_col_chars(spec['labels'].get(key))


def _xlsx_drawing_parts(photos, first_image, col_chars, fmt):
    """drawing XML, its rels XML and ``[(media path, png)]`` for one sheet."""
    anchors = []
    rels = []
    media = []
    for n, ((row, col), (png, width, height)) in enumerate(sorted(photos.items()), 1):
        cx = int(width) * _XLSX_EMU_PER_PX
        cy = int(height) * _XLSX_EMU_PER_PX
        dx, dy = fmt._excel_photo_offsets(col_chars[col], width, height)
        image_no = first_image + n - 1
        anchors.append(
            '<xdr:oneCellAnchor>'
            '<xdr:from><xdr:col>%d</xdr:col><xdr:colOff>%d</xdr:colOff>'
            '<xdr:row>%d</xdr:row><xdr:rowOff>%d</xdr:rowOff></xdr:from>'
            '<xdr:ext cx="%d" cy="%d"/>'
            '<xdr:pic><xdr:nvPicPr><xdr:cNvPr id="%d" name="Picture %d"/>'
            '<xdr:cNvPicPr><a:picLocks noChangeAspect="1"/></xdr:cNvPicPr>'
            '</xdr:nvPicPr>'
            '<xdr:blipFill><a:blip r:embed="rId%d"/>'
            '<a:stretch><a:fillRect/></a:stretch></xdr:blipFill>'
            '<xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/>'
            '</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            '</xdr:spPr></xdr:pic><xdr:clientData/></xdr:oneCellAnchor>'
            % (col - 1, dx, row - 1, dy, cx, cy, n + 1, n, n, cx, cy)
        )
        rels.append(
            '<Relationship Id="rId%d" Type="%s/image" '
            'Target="../media/image%d.png"/>'
            % (n, _XLSX_NS_OD_REL, image_no)
        )
        media.append(('xl/media/image%d.png' % image_no, png))
    drawing = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<xdr:wsDr xmlns:xdr="%s" xmlns:a="%s" xmlns:r="%s">%s</xdr:wsDr>'
    ) % (_XLSX_NS_XDR, _XLSX_NS_A, _XLSX_NS_OD_REL, ''.join(anchors))
    drawing_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="%s">%s</Relationships>'
    ) % (_XLSX_NS_PKG_REL, ''.join(rels))
    return drawing, drawing_rels, media


def _xlsx_sheet_xml(spec, photos=None, photo_cols=(), fmt=None):
    keys = spec['keys']
    labels = spec['labels']
    caption = spec['caption']
    widths = spec['widths']
    rows = spec['rows']
    plan = spec.get('cells') or {}
    number_style = spec.get('number_style') or xlsx_number_style()
    header_row = 2 if caption else 1
    photos = photos or {}
    col_bits = []
    for idx, width in enumerate(widths, 1):
        if idx in photo_cols:
            width = _xlsx_photo_col_chars(spec, idx, fmt)
        col_bits.append(
            '<col min="%d" max="%d" width="%.2f" customWidth="1"/>'
            % (idx, idx, float(width))
        )
    cols_xml = '<cols>%s</cols>' % ''.join(col_bits) if col_bits else ''
    freeze_xml = _xlsx_frozen_header_xml(header_row)
    body = []
    merge_xml = ''
    if caption:
        last = _xlsx_col_letter(len(keys))
        body.append(
            '<row r="1">%s</row>' % _xlsx_cell_xml(1, 1, caption)
        )
        merge_xml = (
            '<mergeCells count="1"><mergeCell ref="A1:%s1"/></mergeCells>'
            % last
        )
    header = ''.join(
        _xlsx_cell_xml(col, header_row, str(labels.get(key) or key))
        for col, key in enumerate(keys, 1)
    )
    body.append('<row r="%d">%s</row>' % (header_row, header))
    for ridx, row in enumerate(rows or [], header_row + 1):
        if not isinstance(row, dict):
            continue
        cells = ''.join(
            _xlsx_cell_xml(
                col, ridx,
                (plan.get((ridx, col)) or (None, row.get(key)))[1],
                formula=(plan.get((ridx, col)) or (None,))[0],
                number_style=number_style,
            )
            for col, key in enumerate(keys, 1)
            if col not in photo_cols
        )
        body.append(
            '<row r="%d"%s>%s</row>' % (
                ridx,
                ' ht="%d" customHeight="1"' % fmt._XLSX_IMG_ROW_PT
                if photo_cols else '',
                cells,
            )
        )
    drawing_xml = '<drawing r:id="rId1"/>' if photos else ''
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="%s" xmlns:r="%s">%s%s<sheetData>%s</sheetData>'
        '%s%s</worksheet>'
    ) % (
        _XLSX_NS_MAIN, _XLSX_NS_OD_REL, freeze_xml, cols_xml, ''.join(body),
        merge_xml, drawing_xml,
    )


def _as_xlsx_ooxml_book(specs):
    if not specs:
        return None
    sheet_tags = []
    rel_tags = []
    override_tags = []
    files = []
    fmt = _load_formatters()
    drawings = 0
    images = 0
    for idx, spec in enumerate(specs, 1):
        photos, photo_cols = _xlsx_sheet_photos(spec, fmt)
        if photos:
            drawings += 1
            drawing, drawing_rels, media = _xlsx_drawing_parts(
                photos, images + 1,
                {c: _xlsx_photo_col_chars(spec, c, fmt) for c in photo_cols},
                fmt,
            )
            images += len(media)
            files.append((
                'xl/worksheets/_rels/sheet%d.xml.rels' % idx,
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="%s"><Relationship Id="rId1" '
                'Type="%s/drawing" Target="../drawings/drawing%d.xml"/>'
                '</Relationships>' % (_XLSX_NS_PKG_REL, _XLSX_NS_OD_REL, drawings),
            ))
            files.append(('xl/drawings/drawing%d.xml' % drawings, drawing))
            files.append((
                'xl/drawings/_rels/drawing%d.xml.rels' % drawings, drawing_rels,
            ))
            files.extend(media)
            override_tags.append(
                '<Override PartName="/xl/drawings/drawing%d.xml" ContentType="'
                'application/vnd.openxmlformats-officedocument.drawing+xml"/>'
                % drawings
            )
        name = html_lib.escape(spec['title'], quote=True)
        sheet_tags.append(
            '<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (name, idx, idx)
        )
        rel_tags.append(
            '<Relationship Id="rId%d" Type="%s/worksheet" '
            'Target="worksheets/sheet%d.xml"/>'
            % (idx, _XLSX_NS_OD_REL, idx)
        )
        override_tags.append(
            '<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="'
            'application/vnd.openxmlformats-officedocument.spreadsheetml.'
            'worksheet+xml"/>' % idx
        )
        files.append((
            'xl/worksheets/sheet%d.xml' % idx,
            _xlsx_sheet_xml(spec, photos, photo_cols, fmt),
        ))
    style = specs[0].get('number_style') or xlsx_number_style()
    style_rid = len(specs) + 1
    rel_tags.append(
        '<Relationship Id="rId%d" Type="%s/styles" Target="styles.xml"/>'
        % (style_rid, _XLSX_NS_OD_REL)
    )
    override_tags.append(
        '<Override PartName="/xl/styles.xml" ContentType="'
        'application/vnd.openxmlformats-officedocument.spreadsheetml.'
        'styles+xml"/>'
    )
    files.append(('xl/styles.xml', _xlsx_styles_xml(style)))
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="%s" xmlns:r="%s"><sheets>%s</sheets></workbook>'
    ) % (_XLSX_NS_MAIN, _XLSX_NS_OD_REL, ''.join(sheet_tags))
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="%s">%s</Relationships>'
    ) % (_XLSX_NS_PKG_REL, ''.join(rel_tags))
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="%s">'
        '<Relationship Id="rId1" Type="%s/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="%s" Target="%s"/>'
        '</Relationships>'
    ) % (_XLSX_NS_PKG_REL, _XLSX_NS_OD_REL, OOXML_CORE_REL, OOXML_CORE_PART)
    ctypes = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="%s">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-'
        'package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '%s'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/%s" ContentType="%s"/>'
        '%s</Types>'
    ) % (
        _XLSX_NS_TYPES,
        '<Default Extension="png" ContentType="image/png"/>' if images else '',
        OOXML_CORE_PART, OOXML_CORE_TYPE,
        ''.join(override_tags),
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        def _put(name, data):
            info = zipfile.ZipInfo(filename=name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            zf.writestr(info, data)
        _put('[Content_Types].xml', ctypes)
        _put('_rels/.rels', root_rels)
        _put('xl/workbook.xml', workbook_xml)
        _put('xl/_rels/workbook.xml.rels', workbook_rels)
        _put(OOXML_CORE_PART, OOXML_CORE_XML)
        for name, data in files:
            _put(name, data)
    return buf.getvalue()
