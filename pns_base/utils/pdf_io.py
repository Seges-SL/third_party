# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""PDF and picture files on bytes: open, write, turn, read, draw.

Pure Python, no Odoo and no AI. A module that wants a model to look at a
page asks here for the pictures and hands them to its own providers.

A PDF made by a program carries its text. A scanned one carries one
picture per page and no text. Text comes from the best reader this
server has (PyMuPDF and pdfminer understand more fonts than PyPDF2 1.x,
the Odoo 14 one). When there is no usable text, the pages become
pictures: drawn by a renderer when there is one, else the scans embedded
in the file. One package, PyMuPDF, covers both routes.

Odoo 19 ships ``pypdf``; Odoo 14 ships ``PyPDF2`` 1.x. Both are opened and
written the same way here.
"""
import io
import os
import re
import shutil
import subprocess
import tempfile

MAX_PAGES = 4
MAX_SIDE = 2000
MIN_SIDE = 300
MIN_LETTERS = 20
DRAW_DPI = 150
# A scanned page covers most of its sheet. A logo or a stamp does not, and
# reading it alone tells the model nothing but a brand name.
SCAN_SHARE = 0.4


# ── Open and write ────────────────────────────────────────────────────

def is_pdf(raw):
    return bool(raw) and raw.lstrip()[:5] == b'%PDF-'


def reader(raw):
    stream = io.BytesIO(raw)
    try:
        from pypdf import PdfReader
        return PdfReader(stream, strict=False)
    except ImportError:
        pass
    from PyPDF2 import PdfFileReader
    return PdfFileReader(stream, strict=False)


def writer():
    try:
        from pypdf import PdfWriter
        return PdfWriter()
    except ImportError:
        pass
    from PyPDF2 import PdfFileWriter
    return PdfFileWriter()


def add_page(pdf_writer, page):
    fn = getattr(pdf_writer, 'add_page', None) or getattr(pdf_writer, 'addPage', None)
    fn(page)


def turn_page(page, degrees):
    """Turn one page clockwise. pypdf: rotate(); PyPDF2 1.x: rotateClockwise()."""
    fn = getattr(page, 'rotate', None) or getattr(page, 'rotateClockwise')
    fn(degrees)


def _obj(value):
    for name in ('get_object', 'getObject'):
        fn = getattr(value, name, None)
        if fn:
            return fn()
    return value


def _pages(pdf_reader, pages):
    return list(pdf_reader.pages)[:pages]


# ── Pictures ──────────────────────────────────────────────────────────

def _open_picture(raw):
    """The picture in ``raw``, stood up the way the camera held it, and its format."""
    from PIL import Image, ImageOps
    image = Image.open(io.BytesIO(raw))
    kind = (image.format or 'PNG').upper()
    image.load()
    # Seges: parche de compatibilidad con Odoo 14 (Python 3.7 / Pillow 5.4). Ver docs/pendiente/parches_pns_ai.md
    transpose = getattr(ImageOps, 'exif_transpose', None) or _exif_transpose_pil5
    return transpose(image), kind


# Seges: parche de compatibilidad con Odoo 14 (Python 3.7 / Pillow 5.4). Ver docs/pendiente/parches_pns_ai.md
def _exif_transpose_pil5(image):
    """ImageOps.exif_transpose for Pillow < 6.0 (orientation from _getexif(), JPEG)."""
    from PIL import Image
    try:
        orientation = (image._getexif() or {}).get(0x0112)
    except Exception:
        orientation = None
    method = {
        2: Image.FLIP_LEFT_RIGHT, 3: Image.ROTATE_180, 4: Image.FLIP_TOP_BOTTOM,
        5: Image.TRANSPOSE, 6: Image.ROTATE_270, 7: Image.TRANSVERSE, 8: Image.ROTATE_90,
    }.get(orientation)
    return image.transpose(method) if method is not None else image


def _on_white(image):
    """RGB. What was transparent becomes white, not black."""
    from PIL import Image
    if image.mode == 'P' and 'transparency' in image.info:
        image = image.convert('RGBA')
    if image.mode in ('RGBA', 'LA'):
        sheet = Image.new('RGB', image.size, 'white')
        sheet.paste(image, mask=image.getchannel('A'))
        return sheet
    return image.convert('RGB')


def to_jpeg(image, side=MAX_SIDE, quality=85):
    image = _on_white(image)
    image.thumbnail((side, side))
    out = io.BytesIO()
    image.save(out, format='JPEG', quality=quality, optimize=True)
    return out.getvalue()


def as_picture(raw, side=MAX_SIDE, quality=85):
    """A photo or scan file (JPEG, PNG, WEBP…) as JPEG bytes. None if it is not one."""
    try:
        image, _kind = _open_picture(raw)
        return to_jpeg(image, side, quality)
    except Exception:
        return None


def picture_size(raw):
    """``(width, height)`` of a picture file, stood up. None if it is not one."""
    try:
        image, _kind = _open_picture(raw)
        return image.size
    except Exception:
        return None


def shrink_picture(raw, side=MAX_SIDE):
    """``(bytes, mimetype)`` of a picture no larger than ``side``. None if it is not one.

    A photo (JPEG) stays JPEG. Any other picture becomes PNG, which keeps
    small letters sharp in a screenshot and keeps what is transparent.
    """
    try:
        image, kind = _open_picture(raw)
        if kind == 'JPEG':
            return to_jpeg(image, side), 'image/jpeg'
        if image.mode not in ('RGB', 'RGBA', 'L', 'LA'):
            image = image.convert('RGBA')
        image.thumbnail((side, side))
        out = io.BytesIO()
        image.save(out, format='PNG')
        return out.getvalue(), 'image/png'
    except Exception:
        return None


def turn_picture(raw, degrees):
    """The picture turned clockwise by ``degrees``, in its own format. None if it is not one."""
    try:
        image, kind = _open_picture(raw)
        image = image.rotate(-int(degrees or 0), expand=True)
        if kind == 'JPEG':
            image = _on_white(image)
        out = io.BytesIO()
        image.save(out, format=kind)
        return out.getvalue()
    except Exception:
        return None


def picture_pdf(raw, side=MAX_SIDE):
    """A one-page PDF of a picture file. None if it is not one."""
    jpeg = as_picture(raw, side)
    if not jpeg:
        return None
    try:
        from PIL import Image
        out = io.BytesIO()
        Image.open(io.BytesIO(jpeg)).save(out, format='PDF')
        return out.getvalue()
    except Exception:
        return None


# ── Text ──────────────────────────────────────────────────────────────

_CID = re.compile(r'\(cid:\d+\)')


def usable(text):
    """Enough letters and digits to be a document, not stray glyphs.

    ``(cid:66)`` is pdfminer saying it could not map a glyph; those tokens
    are not letters of the document.
    """
    text = _CID.sub('', text or '')
    return sum(1 for char in text if char.isalnum()) >= MIN_LETTERS


def _text_fitz(raw, pages):
    """Text by PyMuPDF, which reads fonts PyPDF2 1.x turns into ``(cid:66)``."""
    try:
        import fitz
    except ImportError:
        return []
    try:
        with fitz.open(stream=raw, filetype='pdf') as doc:
            return [
                (doc[index].get_text() or '').strip()
                for index in range(min(pages, doc.page_count))
            ]
    except Exception:
        return []


def _text_pdfminer(raw, pages):
    try:
        from pdfminer.high_level import extract_text
    except ImportError:
        return []
    try:
        text = extract_text(io.BytesIO(raw), maxpages=pages) or ''
    except Exception:
        return []
    # pdfminer ends every page with a form feed.
    found = [part.strip() for part in text.split('\f')]
    if found and not found[-1]:
        found.pop()
    return found[:pages]


def _text_pypdf(raw, pages):
    try:
        found = _pages(reader(raw), pages)
    except Exception:
        return []
    out = []
    for page in found:
        fn = getattr(page, 'extract_text', None) or getattr(page, 'extractText', None)
        try:
            text = fn() if fn else ''
        except Exception:
            text = ''
        out.append((text or '').strip())
    return out


def pdf_page_texts(raw, pages=MAX_PAGES):
    """The text of each of the first ``pages`` pages, an empty page included.

    ``[]`` when no reader finds usable text in the whole document.
    """
    for read in (_text_fitz, _text_pdfminer, _text_pypdf):
        found = [(text or '').strip() for text in (read(raw, pages) or [])]
        if usable('\n'.join(found)):
            return found
    return []


def pdf_text(raw, pages=MAX_PAGES):
    """The text of the first ``pages`` pages. Empty when no reader finds usable text."""
    return '\n\n'.join(text for text in pdf_page_texts(raw, pages) if text)


# ── Page pictures ─────────────────────────────────────────────────────

def _filters(xobj):
    raw = xobj.get('/Filter')
    if raw is None:
        return []
    raw = _obj(raw)
    if isinstance(raw, (list, tuple)):
        return [str(_obj(item)) for item in raw]
    return [str(raw)]


def _picture(xobj, side):
    """One embedded picture as JPEG bytes, or None."""
    from PIL import Image

    width = int(xobj.get('/Width') or 0)
    height = int(xobj.get('/Height') or 0)
    if min(width, height) < MIN_SIDE:
        return None
    kinds = _filters(xobj)
    if kinds and kinds[-1] in ('/DCTDecode', '/JPXDecode') and len(kinds) == 1:
        data = getattr(xobj, '_data', None)
        if not data:
            return None
        return to_jpeg(Image.open(io.BytesIO(data)), side)
    get = getattr(xobj, 'get_data', None) or getattr(xobj, 'getData', None)
    if not get:
        return None
    data = get()
    space = str(_obj(xobj.get('/ColorSpace') or ''))
    bits = int(xobj.get('/BitsPerComponent') or 8)
    if bits == 1:
        mode = '1'
    elif 'RGB' in space:
        mode = 'RGB'
    elif 'Gray' in space:
        mode = 'L'
    elif 'CMYK' in space:
        mode = 'CMYK'
    else:
        return None
    return to_jpeg(Image.frombytes(mode, (width, height), data), side)


def _page_box(page):
    """Width and height of the sheet in points, or (0, 0)."""
    for name in ('mediabox', 'mediaBox'):
        box = getattr(page, name, None)
        if box is None:
            continue
        try:
            width = float(box.width) if hasattr(box, 'width') else float(box.getWidth())
            height = float(box.height) if hasattr(box, 'height') else float(box.getHeight())
            return abs(width), abs(height)
        except Exception:
            continue
    return 0.0, 0.0


def _covers_page(xobj, page):
    """Does this picture fill the sheet the way a scan does?

    Pixels are compared to points (1/72 inch); a scan at 72 dpi or more
    has at least as many pixels as the sheet has points. A logo of a few
    hundred pixels on an A4 sheet does not come close.
    """
    sheet_w, sheet_h = _page_box(page)
    if not sheet_w or not sheet_h:
        return True
    width = int(xobj.get('/Width') or 0)
    height = int(xobj.get('/Height') or 0)
    share = (width * height) / (sheet_w * sheet_h)
    return share >= SCAN_SHARE


def _embedded(raw, pages, side):
    try:
        found = _pages(reader(raw), pages)
    except Exception:
        return []
    out = []
    for page in found:
        try:
            res = _obj(page.get('/Resources') or {})
            xobjects = _obj(res.get('/XObject') or {})
        except Exception:
            continue
        for key in list(xobjects.keys()):
            try:
                xobj = _obj(xobjects[key])
                if str(xobj.get('/Subtype')) != '/Image':
                    continue
                if not _covers_page(xobj, page):
                    continue
                jpeg = _picture(xobj, side)
            except Exception:
                jpeg = None
            if jpeg:
                out.append(jpeg)
    return out


def _drawn_fitz(raw, pages, dpi, side):
    try:
        import fitz
    except ImportError:
        return []
    from PIL import Image

    out = []
    with fitz.open(stream=raw, filetype='pdf') as doc:
        for index in range(min(pages, doc.page_count)):
            pix = doc[index].get_pixmap(dpi=dpi)
            out.append(to_jpeg(Image.open(io.BytesIO(pix.tobytes('png'))), side))
    return out


def _drawn_tool(raw, pages, dpi, side):
    """Pages drawn by pdftoppm (poppler) or gs (ghostscript), if installed."""
    from PIL import Image

    pdftoppm = shutil.which('pdftoppm')
    gs = shutil.which('gs')
    if not pdftoppm and not gs:
        return []
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, 'in.pdf')
        with open(src, 'wb') as handle:
            handle.write(raw)
        if pdftoppm:
            cmd = [pdftoppm, '-r', str(dpi), '-l', str(pages), '-png', src,
                   os.path.join(tmp, 'page')]
        else:
            cmd = [gs, '-q', '-dSAFER', '-dBATCH', '-dNOPAUSE', '-sDEVICE=png16m',
                   '-r%d' % dpi, '-dLastPage=%d' % pages,
                   '-sOutputFile=%s' % os.path.join(tmp, 'page-%d.png'), src]
        subprocess.run(cmd, check=True, timeout=60,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        names = sorted(name for name in os.listdir(tmp) if name.endswith('.png'))
        out = []
        for name in names[:pages]:
            with Image.open(os.path.join(tmp, name)) as image:
                out.append(to_jpeg(image, side))
        return out


def renderer():
    """Name of the page renderer this server has, or ''.

    A PDF made by a program carries no picture of its page: only fonts,
    lines and maybe a logo. Someone has to draw the page before a vision
    model can read it, the way a ticket photo shows the whole sheet.
    """
    try:
        import fitz  # noqa: F401
        return 'PyMuPDF'
    except ImportError:
        pass
    if shutil.which('pdftoppm'):
        return 'pdftoppm'
    if shutil.which('gs'):
        return 'gs'
    return ''


def pdf_pictures(raw, pages=MAX_PAGES, dpi=DRAW_DPI, side=MAX_SIDE):
    """The first ``pages`` pages as JPEG bytes.

    Drawn whole by a renderer when this server has one; without one, the
    scans embedded in the file (a logo does not count); else [].
    """
    for draw in (_drawn_fitz, _drawn_tool):
        try:
            found = draw(raw, pages, dpi, side)
        except Exception:
            found = []
        if found:
            return found
    return _embedded(raw, pages, side)
