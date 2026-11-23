# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""What the turn asked for: requested formats, refusals, on-screen table and the session-file protocol."""

from __future__ import annotations
import re
from collections.abc import Mapping

from .artifact_export_table import (
    public_columns,
    public_rows,
    tabular_rows,
)


_XLSX_MIME = (
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)


# The host's client assembles these (table + ECharts PNG). Excel/md stay here
# (icon Excel uses this same writer).
CLIENT_ASSEMBLED_KINDS = frozenset(('doc', 'pdf', 'html'))


# Canonical kind → extension + mimetype. excel/xls still emit xlsx.
FORMAT_SPECS = {
    'pdf': {'kind': 'pdf', 'ext': 'pdf', 'mimetype': 'application/pdf'},
    'excel': {'kind': 'xlsx', 'ext': 'xlsx', 'mimetype': _XLSX_MIME},
    'xlsx': {'kind': 'xlsx', 'ext': 'xlsx', 'mimetype': _XLSX_MIME},
    'xls': {'kind': 'xlsx', 'ext': 'xlsx', 'mimetype': _XLSX_MIME},
    'txt': {'kind': 'txt', 'ext': 'txt', 'mimetype': 'text/plain; charset=utf-8'},
    'md': {'kind': 'md', 'ext': 'md', 'mimetype': 'text/markdown; charset=utf-8'},
    'markdown': {'kind': 'md', 'ext': 'md', 'mimetype': 'text/markdown; charset=utf-8'},
    'html': {'kind': 'html', 'ext': 'html', 'mimetype': 'text/html; charset=utf-8'},
    'word': {'kind': 'doc', 'ext': 'doc', 'mimetype': 'application/msword'},
    'docx': {'kind': 'doc', 'ext': 'doc', 'mimetype': 'application/msword'},
    'doc': {'kind': 'doc', 'ext': 'doc', 'mimetype': 'application/msword'},
}


# ASCII edges only: ``\\b`` misses CJK (``PDFを`` has no Unicode word break).
# A leading dot (``.odt``) is not ``[a-z0-9_]``, so these already match.
_FORMAT_RE = re.compile(
    r'(?i)(?<![a-z0-9_])(?:markdown|xlsx|xls|excel|pdf|html|txt|md|'
    r'docx|word|doc)(?![a-z0-9_])',
)


_REFUSE_RE = re.compile(
    r'(?i)(?<![a-z0-9_])'
    r'(?:pptx|powerpoint|odt|ods|odp|rtf|ppt)'
    r'(?![a-z0-9_])',
)


# Dotted token not in the closed list (``.rtf``, ``.csv``). ``foo.com`` does
# not match: the letter before the dot fails the lookbehind.
_DOT_EXT_RE = re.compile(
    r'(?i)(?<![a-z0-9_])\.([a-z][a-z0-9]{1,4})(?![a-z0-9_])',
)


# Engine injects this when the utterance names a download format. Protocol,
# not a locale verb list (same pattern as ``self``).
SESSION_FILE_PROTOCOL = (
    'The user named a download format. Query structured rows (return '
    'data) and set result __title__ to a short Locale phrase that names '
    'the content (not a copy of the user prompt). Optional: '
    '__filename_stem__ (slug, no extension), __sheet_caption__ (one '
    'line on a single Excel sheet), __column_labels__ (key to visible '
    'header). Derived columns (difference, ratio, %) MUST set '
    '__excel_formulas__ (xlsx-only map of public column key to '
    '{other_key} arithmetic; chat, PDF, and Word keep values) — same '
    'map as any tabular turn, not only this named download. The '
    'server serializes the file and pins a session '
    'download card (same box as a clipboard, a manual attach, or a '
    'session file). The user may name one or more formats; the server '
    'pins one card per format. FORBIDDEN this turn: reportlab, '
    'openpyxl, ir.attachment, and safe_plan_request for files. '
    'Do not paint a listing unless __show_table__ or show_mode '
    'show-table / chart-table / table. show-chart without '
    '__show_table__ keeps the chart and hides the listing. Word, PDF, '
    'and HTML mirror this turn (table, chart, or both) and are '
    'assembled by the chat client (same file for the session card '
    'and the bubble icons; the canvas paints the chart). Do not '
    'rebuild those files in RelaxAICode. Word is a session download '
    '(Office HTML .doc). Optional __rich_doc__ true wraps this turn '
    'HTML in that Word file (Locale like self). Page flag is '
    '__landscape__ true or false; do not invent other orientation keys. '
    'Excel and Markdown stay server tables (no chart).'
)


SESSION_FILE_META_PROTOCOL = (
    'The rows are ready. Return the SAME data and set __title__ '
    '(Locale: what the file contains). Optional __filename_stem__, '
    '__sheet_caption__, __column_labels__. Derived columns MUST keep '
    '__excel_formulas__. Word, '
    'PDF, and HTML with a '
    'chart are assembled by the chat client. Do not rebuild the '
    'file in Python. Do not call safe_plan_request.'
)


SESSION_FILE_PROPOSE_ERROR = (
    'Session files are not caja B. Return structured rows (data); '
    'the server will serialize and attach a session download chip. '
    'Do not call safe_plan_request for ir.attachment.'
)


SESSION_FILE_ATTACHED_NOTE = (
    'The server attached the session download card. Do not propose '
    'ir.attachment. Point the user to the card in one sentence.'
)


# Report / compose-model: named format still keeps the narrative in the bubble.
SESSION_FILE_REPORT_NOTE = (
    'The user also named a download format. Write the FULL report in the '
    'bubble (every outline heading). The server attaches the session '
    'download card under the prose. Do not replace the narrative with a '
    'pointer to the card. Do not call safe_plan_request for files.'
)


REFUSED_EXPORT_REPLY = (
    'That file type is not available as a session download. '
    'I can send PDF, Excel, Word, text, Markdown, or HTML.'
)


REFUSED_PARTIAL_REPLY = (
    'These file types are not available as a session download: %s. '
    'I can send PDF, Excel, Word, text, Markdown, or HTML.'
)


def _spec_for_ext(ext):
    """FORMAT_SPECS row for a dotted extension, or None."""
    ext = (ext or '').lower()
    if ext in FORMAT_SPECS:
        return ext, FORMAT_SPECS[ext]
    for key, spec in FORMAT_SPECS.items():
        if spec.get('ext') == ext:
            return key, spec
    return None, None


def _hit_from_token(token):
    """FORMAT_SPECS row for a word token, or None."""
    token = (token or '').lower()
    spec = FORMAT_SPECS.get(token)
    if not spec:
        return None
    return {
        'format': token,
        'refused': False,
        'kind': spec['kind'],
        'ext': spec['ext'],
        'mimetype': spec['mimetype'],
    }


def _attached_file_kinds(names):
    """Kinds and raw extensions of the files attached to this turn."""
    kinds = set()
    for name in names or ():
        if not isinstance(name, str) or '.' not in name:
            continue
        ext = name.rsplit('.', 1)[-1].strip().lower()
        if not ext:
            continue
        kinds.add(ext)
        _token, spec = _spec_for_ext(ext)
        if spec:
            kinds.add(spec['kind'])
    return kinds


def _token_kind(token):
    """Kind a format token names (``excel`` → ``xlsx``), else the bare token."""
    token = (token or '').lower().lstrip('.')
    spec = FORMAT_SPECS.get(token)
    if not spec:
        _key, spec = _spec_for_ext(token)
    return spec['kind'] if spec else token


def drop_attached_file_formats(text, names):
    """``text`` without the format tokens that name an attached file's type.

    With a PDF attached, ``pdf`` in the sentence is the attachment, not a
    download ask. Another type in the same sentence still asks for one.
    """
    if not isinstance(text, str) or not text:
        return text if isinstance(text, str) else ''
    kinds = _attached_file_kinds(names)
    if not kinds:
        return text

    def _blank(match):
        return ' ' if _token_kind(match.group(0)) in kinds else match.group(0)

    for regex in (_DOT_EXT_RE, _FORMAT_RE, _REFUSE_RE):
        text = regex.sub(_blank, text)
    return text


def turn_export_utterance(env, fallback=''):
    """User-typed text for format detection. Never engine-rewritten handoff.

    Skill bodies and report handoffs mention HTML/Markdown as *medium*;
    those words must not spawn download cards. A host that attaches files
    lists their names in ``turn_file_names``; a token naming one of those
    types is the attachment, not a download.
    """
    ctx = getattr(env, 'context', None) or {}
    # Odoo 20's frozendict is a mappingproxy, not a dict.
    if not isinstance(ctx, Mapping):
        ctx = {}
    raw = ctx.get('user_message')
    if not (isinstance(raw, str) and raw.strip()):
        raw = fallback if isinstance(fallback, str) else ''
    return drop_attached_file_formats(raw, ctx.get('turn_file_names'))


def payload_has_report_outline(payload):
    """True when the skill declared a narrative skeleton (keep prose)."""
    if not isinstance(payload, dict):
        return False
    outline = payload.get('report_outline')
    if not isinstance(outline, (list, tuple)):
        return False
    return any(isinstance(h, str) and h.strip() for h in outline)


def parse_requested_export(user_message):
    """Return format intent from the utterance, or None.

    File-type tokens only (pdf/xlsx/…), not a locale verb list. Table vs
    card is the always-on pack (same pattern as ``self``). Collects every
    unique serializable kind in appearance order. Known formats win over
    a refused token in the same sentence: ``refused`` is True only when
    nothing valid was named. Compat: ``format`` / ``kind`` are the first
    valid hit; ``formats`` and ``refused_tokens`` list the rest.
    """
    text = user_message if isinstance(user_message, str) else ''
    if not text.strip():
        return None
    events = []
    for match in _FORMAT_RE.finditer(text):
        hit = _hit_from_token(match.group(0))
        if hit:
            events.append((match.start(), 'ok', hit, match.group(0)))
    for match in _DOT_EXT_RE.finditer(text):
        ext = match.group(1)
        token, spec = _spec_for_ext(ext)
        if spec:
            events.append((match.start(), 'ok', {
                'format': token,
                'refused': False,
                'kind': spec['kind'],
                'ext': spec['ext'],
                'mimetype': spec['mimetype'],
            }, match.group(0)))
        else:
            events.append((match.start(), 'refuse', None, match.group(0)))
    for match in _REFUSE_RE.finditer(text):
        events.append((match.start(), 'refuse', None, match.group(0)))
    if not events:
        return None
    events.sort(key=lambda item: item[0])
    formats = []
    seen_kinds = set()
    refused_tokens = []
    seen_refuse = set()
    for _pos, etype, hit, raw in events:
        if etype == 'ok':
            kind = hit['kind']
            if kind in seen_kinds:
                continue
            seen_kinds.add(kind)
            formats.append(hit)
            continue
        label = ' '.join(str(raw or '').split())
        if not label:
            continue
        key = label.lower().lstrip('.')
        if not key or key in seen_refuse:
            continue
        seen_refuse.add(key)
        refused_tokens.append(label)
    if formats:
        first = dict(formats[0])
        first['formats'] = formats
        first['refused_tokens'] = refused_tokens
        first['refused'] = False
        return first
    return {
        'format': None,
        'refused': True,
        'formats': [],
        'refused_tokens': refused_tokens,
    }


# Shape heuristic: many columns (or a very wide header row) need A4 landscape.
PDF_LANDSCAPE_MIN_COLS = 6


PDF_LANDSCAPE_MIN_HEADER_CHARS = 48


def _payload_landscape_flag(payload):
    """``__landscape__`` wins; ``__orientation__`` is landscape|portrait only."""
    if not isinstance(payload, dict):
        return None
    if '__landscape__' in payload:
        return bool(payload.get('__landscape__'))
    raw = payload.get('__orientation__')
    if raw is None or isinstance(raw, bool):
        return None
    token = str(raw).strip().lower()
    if token == 'landscape':
        return True
    if token == 'portrait':
        return False
    return None


def pdf_landscape(payload=None, default=None, col_count=None, rows=None):
    """Session PDF orientation.

    ``__landscape__`` on the payload always wins (pack / Locale, like
    ``self``). ``__orientation__`` accepts only the product tokens
    landscape / portrait. Otherwise a shape heuristic: wide tables go
    landscape. Not a locale word list.
    """
    flagged = _payload_landscape_flag(payload)
    if flagged is not None:
        return flagged
    n = col_count
    keys = None
    if n is None:
        public = public_rows(tabular_rows(payload, rows) or [])
        if public:
            keys = public_columns(public)
            n = len(keys)
    if n is not None:
        if n >= PDF_LANDSCAPE_MIN_COLS:
            return True
        if keys is None and rows:
            keys = public_columns(public_rows(rows))
        if keys and sum(len(str(k)) for k in keys) >= PDF_LANDSCAPE_MIN_HEADER_CHARS:
            return True
        return False
    return True if default is None else bool(default)


_CHART_ONLY_SHOW_MODES = frozenset(('show-chart', 'chart'))


_TABLE_VISIBLE_SHOW_MODES = frozenset(('table', 'show-table', 'chart-table'))


_CHART_FILE_SHOW_MODES = frozenset((
    'show-chart', 'chart', 'chart-table', 'dashboard',
))


def payload_show_mode(payload):
    """Normalized ``show_mode`` / ``showmode`` token, or empty."""
    if not isinstance(payload, dict):
        return ''
    raw = payload.get('show_mode') or payload.get('showmode') or ''
    return str(raw).strip().lower()


def wants_on_screen_table(payload):
    """True when the listing must stay visible next to the card.

    ``__show_table__`` is the explicit flag. ``show-table`` / ``table`` /
    ``chart-table`` also keep the listing. ``show-chart`` alone does not
    (dataset stays for the canvas).
    """
    if not isinstance(payload, dict):
        return False
    if payload.get('__show_table__'):
        return True
    if payload_has_report_outline(payload):
        return True
    return payload_show_mode(payload) in _TABLE_VISIBLE_SHOW_MODES


def clip_include_table(payload):
    """File listing unless this turn is chart-only."""
    if not isinstance(payload, dict):
        return True
    if payload.get('__show_table__'):
        return True
    if payload_show_mode(payload) in _CHART_ONLY_SHOW_MODES:
        return False
    return True


def wants_rich_doc(payload):
    """True when the pack asked for a showpiece Word (flag only)."""
    if not isinstance(payload, dict):
        return False
    return bool(payload.get('__rich_doc__'))


def payload_allows_charts(payload):
    """False only on explicit opt-out (``__no_charts__`` / ``charts is False``)."""
    if not isinstance(payload, dict):
        return True
    if payload.get('__no_charts__') is True:
        return False
    if payload.get('charts') is False:
        return False
    return True


def payload_formatted_html(payload):
    """Turn HTML from a RelaxAICode payload, or empty."""
    if not isinstance(payload, dict):
        return ''
    html = payload.get('formatted_text')
    if isinstance(html, str) and html.strip():
        return html
    return ''


def export_hides_on_screen_table(user_message, payload=None):
    """Named download without ``__show_table__``: card only, no server table.

    A ``report_outline`` payload keeps prose (and tables) next to the card.
    """
    if not requested_named_format(user_message):
        return False
    return not wants_on_screen_table(payload)


def requested_named_format(user_message):
    """Parsed format when the utterance names a serializable type, else None."""
    parsed = parse_requested_export(user_message)
    if parsed and parsed.get('format') and not parsed.get('refused'):
        return parsed
    return None


def is_refused_export(user_message):
    """True when every named file type is outside the closed list.

    Mixed utterances (PDF + PowerPoint) stay False so the turn can query
    and serialize the kinds that work.
    """
    parsed = parse_requested_export(user_message)
    if not parsed:
        return False
    formats = parsed.get('formats')
    if isinstance(formats, list) and formats:
        return False
    return bool(parsed.get('refused') and not parsed.get('format'))


def refused_token_labels(tokens):
    """Comma-separated utterance tokens, first spelling wins."""
    seen = set()
    labels = []
    for tok in tokens or []:
        text = ' '.join(str(tok).split())
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        labels.append(text)
    return ', '.join(labels)


def merge_refused_note(body, tokens, note=None):
    """Append the partial-refuse sentence, or return body unchanged."""
    labels = refused_token_labels(tokens)
    if not labels:
        return body or ''
    template = note if note is not None else REFUSED_PARTIAL_REPLY
    text = template % labels
    body = (body or '').rstrip()
    if body:
        return body + '\n\n' + text
    return text
