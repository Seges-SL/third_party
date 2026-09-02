# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Extract inline SVGs from assistant HTML into session chips.

Drawings leave the bubble (PDF-like chip). Click opens the file in a
browser tab (inline), not as a download.
"""
from __future__ import annotations

import html as html_lib
import logging
import re
import unicodedata

_logger = logging.getLogger(__name__)

# Decorative Chatboo chrome — not a drawing the user asked to keep.
_DECORATIVE_MARKERS = (
    'o_chatboo_map_banner_pins',
    'o_chatboo_link_banner_mark',
    'o_chatboo_chart_',
    'o_chatboo_dashboard_',
    'o_chatboo_export_bar',
)

_SVG_OPEN = re.compile(r'<svg\b[^>]*>', re.IGNORECASE)
_SVG_CLOSE = re.compile(r'</svg\s*>', re.IGNORECASE)
_ESC_OPEN = re.compile(r'&lt;svg\b', re.IGNORECASE)
_ESC_CLOSE = re.compile(r'&lt;/svg\s*&gt;', re.IGNORECASE)
_FENCE = re.compile(
    r'(?:\A|\r?\n)([`~]{3,})[ \t]*([^\n]*)\r?\n(.*?)(?:\r?\n\1[ \t]*)(?=\r?\n|\Z)',
    re.DOTALL,
)
_PRE_CODE = re.compile(
    r'<pre\b[^>]*>\s*<code\b[^>]*>(.*?)</code>\s*</pre>',
    re.IGNORECASE | re.DOTALL,
)
_XML_DECL = re.compile(r'^<\?xml\b[^>]*\?>\s*', re.IGNORECASE)
_TITLE = re.compile(r'<title[^>]*>([^<]+)</title>', re.IGNORECASE)
_ON_ATTR = re.compile(
    r'\son[a-z]+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)',
    re.IGNORECASE,
)
_JS_HREF = re.compile(
    r'''\s(?:xlink:)?href\s*=\s*['"]\s*javascript:[^'"]*['"]''',
    re.IGNORECASE,
)

MIN_SVG_CHARS = 400
MAX_SVGS_PER_TURN = 5


def _slug(text):
    raw = unicodedata.normalize('NFKD', text or '')
    raw = ''.join(c for c in raw if not unicodedata.combining(c))
    slug = re.sub(r'[^A-Za-z0-9]+', '_', raw).strip('_').lower()
    return slug[:50]


# Structural particles / request verbs / format words — not business nouns.
_FUNCTION_WORDS = frozenset({
    'a', 'an', 'the', 'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
    'de', 'del', 'al', 'y', 'o', 'e', 'u', 'en', 'con', 'por', 'para', 'sin',
    'mi', 'me', 'te', 'se', 'le', 'les', 'nos', 'os', 'tu', 'su', 'my', 'your',
    'que', 'qué', 'como', 'cómo', 'cual', 'cuál', 'when', 'where', 'what', 'who',
    'please', 'porfa', 'porfavor', 'pls', 'plz', 'gracias', 'favor',
    'can', 'could', 'would', 'will', 'want',
    'quiero', 'quieres', 'quisiera', 'puedes', 'puede', 'podrias', 'podrias',
    'haz', 'hazme', 'dame', 'dame', 'pasame', 'mandame', 'envia', 'enviame',
    'make', 'create', 'generate', 'give', 'show', 'need', 'necesito',
    'draw', 'paint', 'pinta', 'pintas', 'pintame', 'dibuja', 'dibujas', 'dibujame',
    'escribe', 'muestra', 'ponme', 'pon', 'this', 'that', 'esto', 'eso',
    'here', 'ahi', 'aquí', 'aqui', 'there', 'va', 'un',
})

_FORMAT_WORDS = frozenset({
    'svg', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'html', 'htm',
    'xlsx', 'xls', 'csv', 'zip', 'docx', 'doc', 'file', 'archivo', 'fichero',
    'documento', 'imagen', 'image', 'drawing', 'dibujo', 'export', 'download',
    'descarga', 'descargar', 'descargame', 'bajame',
})

_GENERIC_STEMS = frozenset({
    'download', 'file', 'document', 'attachment', 'drawing', 'export',
    'unnamed', 'response', 'chatboo', 'bin', 'data',
})

_EXPLICIT_FILE = re.compile(
    r'([A-Za-z0-9][A-Za-z0-9._-]{0,80})\.'
    r'(svg|pdf|png|jpe?g|gif|webp|xlsx?|csv|zip|docx?)\b',
    re.IGNORECASE,
)

_GENERIC_INDEXED = re.compile(
    r'^(?:drawing|download|file|document|export|response)(?:[-_]\d+)?$',
    re.IGNORECASE,
)
# Storage keys / object ids are not a human file name.
_UUID_STEM = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)
_HEX_STEM = re.compile(r'^[0-9a-f]{16,}$', re.IGNORECASE)


def _axis_tokens():
    try:
        from .formatting_mode_policy import AXIS_COMMANDS
        return set(AXIS_COMMANDS)
    except Exception:
        return {
            'painter-local', 'painter-free', 'foot-verbose', 'foot-laconic',
            'show-table', 'show-chart',
        }


def split_utterance(text):
    """Strip axis slashes; first other ``/token`` is the skill code."""
    rest = (text or '').strip()
    skill = None
    axis = _axis_tokens()
    while rest.startswith('/'):
        body = rest[1:].lstrip()
        if not body:
            break
        token, _sep, after = body.partition(' ')
        token = token.strip().rstrip('.,;:!?')
        if not token:
            break
        if token.lower() in axis:
            rest = after.strip()
            continue
        if skill is None:
            skill = token
        rest = after.strip()
        break
    return rest, skill


def _content_slug(text):
    tokens = re.split(r'[^A-Za-z0-9]+', _slug(text).replace('_', ' '))
    kept = []
    skip = _FUNCTION_WORDS | _FORMAT_WORDS
    for tok in tokens:
        if not tok or tok in skip or tok.isdigit():
            continue
        kept.append(tok)
    return '_'.join(kept)[:50]


def utterance_stem(prompt=None, skill_code=None, title=None):
    """Subject stem from the user prompt or skill — no business-word lists."""
    rest, slash_skill = split_utterance(prompt)
    skill = (skill_code or slash_skill or '').strip()
    explicit = _EXPLICIT_FILE.search(rest or '')
    if explicit:
        return _slug(explicit.group(1))
    from_rest = _content_slug(rest)
    if from_rest:
        return from_rest
    if skill:
        slugged = _slug(skill)
        if slugged:
            return slugged
    return _slug(title) or ''


def utterance_filename(prompt=None, skill_code=None, title=None, ext='svg',
                       fallback='drawing', index=1):
    """``gato.svg`` / ``informe_financiero.pdf`` from prompt or skill."""
    stem = utterance_stem(prompt=prompt, skill_code=skill_code, title=title)
    if not stem:
        if not fallback:
            return ''
        stem = _slug(fallback) or 'drawing'
    idx = int(index or 1)
    if idx > 1:
        stem = '%s-%d' % (stem, idx)
    ext = (ext or 'svg').lstrip('.').lower() or 'svg'
    return '%s.%s' % (stem, ext)


def is_opaque_attachment_stem(name):
    """True for UUID / long-hex stems (not a display name)."""
    if not name or not isinstance(name, str):
        return True
    stem = name.rsplit('.', 1)[0] if '.' in name else name
    stem = stem.strip().lower()
    if not stem:
        return True
    return bool(_UUID_STEM.match(stem) or _HEX_STEM.match(stem))


def is_generic_attachment_name(name):
    if not name or not isinstance(name, str):
        return True
    stem = name.rsplit('.', 1)[0] if '.' in name else name
    stem = stem.strip().lower()
    return (
        stem in _GENERIC_STEMS
        or bool(_GENERIC_INDEXED.match(stem))
        or is_opaque_attachment_stem(name)
    )


def ext_from_name_or_mime(name=None, mimetype=None):
    if name and '.' in name:
        ext = name.rsplit('.', 1)[-1].strip().lower()
        if ext and len(ext) <= 5 and ext.isalnum():
            return ext
    ct = (mimetype or '').split(';', 1)[0].strip().lower()
    mapping = {
        'image/svg+xml': 'svg',
        'application/pdf': 'pdf',
        'image/png': 'png',
        'image/jpeg': 'jpg',
        'image/gif': 'gif',
        'image/webp': 'webp',
        'application/zip': 'zip',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    }
    for key, ext in mapping.items():
        if ct == key or ct.startswith(key):
            return ext
    return ''


def sanitize_svg(chunk):
    """Drop script/handlers; keep drawing markup. Structural, not a domain list."""
    if not chunk or not isinstance(chunk, str):
        return ''
    out = chunk.strip()
    out = re.sub(
        r'<script\b[^>]*>.*?</script>', '', out,
        flags=re.IGNORECASE | re.DOTALL,
    )
    out = re.sub(
        r'<foreignObject\b[^>]*>.*?</foreignObject>', '', out,
        flags=re.IGNORECASE | re.DOTALL,
    )
    out = _ON_ATTR.sub('', out)
    out = _JS_HREF.sub('', out)
    head = out[:240].lower()
    if '<svg' in head and 'xmlns=' not in head:
        out = re.sub(
            r'<svg\b',
            '<svg xmlns="http://www.w3.org/2000/svg"',
            out, count=1, flags=re.IGNORECASE,
        )
    if not re.match(r'<svg\b', out, re.IGNORECASE):
        return ''
    return out.strip()


def _is_decorative(chunk):
    blob = (chunk or '').lower()
    return any(marker in blob for marker in _DECORATIVE_MARKERS)


def _first_svg_chunk(blob):
    """Return ``(chunk, start, end)`` of the first raw ``<svg>…</svg>`` or None."""
    if not blob:
        return None
    opened = _SVG_OPEN.search(blob)
    if not opened:
        return None
    closed = _SVG_CLOSE.search(blob, opened.end())
    if not closed:
        return None
    return blob[opened.start():closed.end()], opened.start(), closed.end()


def _as_drawing(chunk, min_chars=MIN_SVG_CHARS):
    if not chunk or len(chunk) < min_chars or _is_decorative(chunk):
        return ''
    clean = sanitize_svg(chunk)
    if clean and len(clean) >= min_chars:
        return clean
    return ''


def _body_is_svg_document(body):
    """True when the block *is* a drawing, not a script that merely mentions SVG."""
    raw = (body or '').strip()
    if not raw:
        return False
    if '&lt;svg' in raw[:80].lower() or raw.lower().startswith('&lt;?xml'):
        raw = html_lib.unescape(raw)
    raw = _XML_DECL.sub('', raw.strip())
    return bool(re.match(r'<svg\b', raw, re.IGNORECASE))


def _drawing_from_body(body, min_chars=MIN_SVG_CHARS):
    raw = (body or '').strip()
    if '&lt;svg' in raw.lower() or '&lt;?xml' in raw[:80].lower():
        raw = html_lib.unescape(raw)
    raw = _XML_DECL.sub('', raw.strip())
    found = _first_svg_chunk(raw)
    if not found:
        return ''
    return _as_drawing(found[0], min_chars=min_chars)


def _span_overlaps(start, end, ranges):
    for a, b in ranges:
        if start < b and end > a:
            return True
    return False


def _apply_removals(text, ranges):
    if not ranges:
        return text
    ordered = sorted(ranges, key=lambda pair: pair[0])
    merged = []
    for start, end in ordered:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    parts = []
    last = 0
    for start, end in merged:
        parts.append(text[last:start])
        last = end
    parts.append(text[last:])
    cleaned = ''.join(parts)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def harvest_drawing_svgs(text, min_chars=MIN_SVG_CHARS, max_count=MAX_SVGS_PER_TURN):
    """Return ``(documents, cleaned_text)``.

    Drawings (raw SVG, markdown fences, ``<pre><code>``, HTML-escaped) are
    extracted and removed from the bubble text. Decorative chrome stays.
    """
    if not text or not isinstance(text, str):
        return [], text or ''
    lowered = text.lower()
    if '<svg' not in lowered and '&lt;svg' not in lowered:
        return [], text

    docs = []
    ranges = []
    protected = []

    def _take(chunk, span):
        if len(docs) >= max_count:
            return
        if _span_overlaps(span[0], span[1], ranges) or _span_overlaps(
            span[0], span[1], protected,
        ):
            return
        clean = _as_drawing(chunk, min_chars=min_chars)
        if not clean:
            return
        docs.append(clean)
        ranges.append(span)

    for match in _FENCE.finditer(text):
        if len(docs) >= max_count:
            break
        body = match.group(3) or ''
        if not _body_is_svg_document(body):
            protected.append(match.span())
            continue
        drawing = _drawing_from_body(body, min_chars=min_chars)
        if drawing:
            _take(drawing, match.span())

    for match in _PRE_CODE.finditer(text):
        if len(docs) >= max_count:
            break
        body = match.group(1) or ''
        if not _body_is_svg_document(body):
            protected.append(match.span())
            continue
        drawing = _drawing_from_body(body, min_chars=min_chars)
        if drawing:
            _take(drawing, match.span())

    pos = 0
    while len(docs) < max_count:
        opened = _SVG_OPEN.search(text, pos)
        if not opened:
            break
        closed = _SVG_CLOSE.search(text, opened.end())
        if not closed:
            break
        span = (opened.start(), closed.end())
        pos = closed.end()
        _take(text[span[0]:span[1]], span)

    pos = 0
    while len(docs) < max_count:
        opened = _ESC_OPEN.search(text, pos)
        if not opened:
            break
        closed = _ESC_CLOSE.search(text, opened.end())
        if not closed:
            break
        span = (opened.start(), closed.end())
        pos = closed.end()
        _take(html_lib.unescape(text[span[0]:span[1]]), span)

    if not docs:
        return [], text
    return docs, _apply_removals(text, ranges)


def extract_inline_svgs(html, min_chars=MIN_SVG_CHARS, max_count=MAX_SVGS_PER_TURN):
    """Return sanitized SVG documents large enough to be a drawing, not an icon."""
    return harvest_drawing_svgs(html, min_chars=min_chars, max_count=max_count)[0]


def svg_filename(svg, index=1, prompt=None, skill_code=None):
    title = None
    match = _TITLE.search(svg or '')
    if match:
        title = match.group(1)
    return utterance_filename(
        prompt=prompt, skill_code=skill_code, title=title,
        ext='svg', fallback='drawing', index=index,
    )


def svg_inline_view_url(chip):
    """Open an SVG session chip in a tab (inline). Never download=true.

    Odoo ``/web/content`` often forces ``Content-Disposition: attachment`` on
    SVG (XSS). Point the chip at ``/pns_ai_mcp/session_file/<id>`` instead.
    Named PDF/MD/HTML chips use ``download=true`` so they save instead of
    opening in the browser.
    """
    if not isinstance(chip, dict):
        return ''
    url = chip.get('url') or ''
    url = re.sub(r'([?&])download=[^&]*', r'\1', url)
    url = url.replace('?&', '?').rstrip('?&')
    match = re.search(r'/web/content/(\d+)', url)
    if not match:
        match = re.search(r'/pns_ai_mcp/session_file/(\d+)', url)
    if not match:
        return url
    token_m = re.search(r'access_token=([^&]+)', url)
    token = token_m.group(1) if token_m else ''
    path = '/pns_ai_mcp/session_file/%s' % match.group(1)
    return '%s?access_token=%s' % (path, token) if token else path


def persist_inline_svgs_from_html(env, session_id, html, prompt=None, skill_code=None):
    """Store each drawing as ir.attachment; return ``(chips, cleaned_html)``.

    On success the bubble text no longer contains the drawing or its source
    fence — same gesture as a PDF chip. If nothing is stored, html is unchanged.
    Chip names follow the user prompt or skill (``gato.svg``), not ``drawing-1``.
    """
    from .session_download import persist_chatboo_session_file

    docs, cleaned = harvest_drawing_svgs(html)
    chips = []
    for index, svg in enumerate(docs, 1):
        raw = svg.encode('utf-8')
        name = svg_filename(svg, index, prompt=prompt, skill_code=skill_code)
        chip = persist_chatboo_session_file(
            env, session_id, raw, name, mimetype='image/svg+xml',
        )
        if not chip:
            continue
        chip = dict(chip)
        chip['source'] = 'inline_svg'
        chip['url'] = svg_inline_view_url(chip)
        chips.append(chip)
    if not chips:
        return [], html
    return chips, cleaned
