# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Compact conversation history for the next LLM round (stubs, not gzip).

Invariant (no domain): the user-facing bubble may keep the full HTML/table.
The prompt that goes to the model between turns must not replay rendered
rows. Point at the on-screen artifact and the server-side dataset cache
(``previous_result``). Same-turn ReAct tool results stay intact.

See ``docs/decisions/historial_llm_stubs.md``.
"""
from __future__ import annotations

import html as html_lib
import json
import re

STUB_PREFIX = '[On-screen artifact'
STUB_FOOTER = (
    'The full document is already visible to the user. Do not reprint the '
    'rows. Cached dataset is previous_result if you need to reformat or '
    'recompute. If the user asks about this artifact or its image, answer '
    'from this stub (including any [image: …] refs). Use tools only for a '
    'genuinely new query.'
)

USER_MAX_CHARS = 4000
ASSISTANT_KEEP_CHARS = 1500
FAT_CHARS = 2500
MAX_COLUMNS = 12
MAX_TITLE_CHARS = 160

_TAG_RE = re.compile(r'<[^>]+>', re.DOTALL)
_IMG_TAG_RE = re.compile(r'<img\b([^>]*)/?>', re.IGNORECASE | re.DOTALL)
_IMG_SRC_RE = re.compile(r'''\bsrc\s*=\s*["']([^"']+)["']''', re.IGNORECASE)
_IMG_ALT_RE = re.compile(r'''\balt\s*=\s*["']([^"']*)["']''', re.IGNORECASE)
_DATASET_ATTR_RE = re.compile(
    r'data-chatboo-dataset=(["\'])(.*?)\1',
    re.IGNORECASE | re.DOTALL,
)
_TITLE_RE = re.compile(
    r'<h[1-3][^>]*>(.*?)</h[1-3]>'
    r'|<caption[^>]*>(.*?)</caption>'
    r'|class="[^"]*o_chatboo_table_title[^"]*"[^>]*>(.*?)<',
    re.IGNORECASE | re.DOTALL,
)
_MD_SEP_RE = re.compile(r'^\s*\|?\s*[-:| ]+\s*\|?\s*$')
_INTERNAL_KEY_RE = re.compile(r'^_')


def is_already_stub(text):
    """True if this content is already an LLM history stub."""
    if not isinstance(text, str):
        return False
    return text.lstrip().startswith(STUB_PREFIX)


def compact_history_for_llm(history):
    """Return user/assistant turns with fat assistant payloads replaced by stubs.

    Drops ``system`` and ``tool`` roles (and assistant-only tool_calls with no
    text). Does not mutate the input list. Result starts at a user turn.
    """
    out = []
    for msg in history or []:
        if not isinstance(msg, dict):
            continue
        role = msg.get('role')
        if role in ('system', 'tool'):
            continue
        if role == 'assistant' and msg.get('tool_calls') and not _message_text(msg):
            continue
        if role == 'user':
            text = _clip(_message_text(msg), USER_MAX_CHARS)
            out.append({'role': 'user', 'content': text})
        elif role == 'assistant':
            out.append({
                'role': 'assistant',
                'content': compact_assistant_content(_message_text(msg)),
            })
    while out and out[0].get('role') != 'user':
        out.pop(0)
    return out


def append_turn_stub(prior_compacted, user_text, *, payload=None, visible=None):
    """Prior compact history + this turn's user prompt + assistant stub."""
    out = list(prior_compacted or [])
    user_content = _clip(_as_text(user_text), USER_MAX_CHARS)
    if user_content:
        out.append({'role': 'user', 'content': user_content})
    out.append({
        'role': 'assistant',
        'content': compact_assistant_content(visible, payload=payload),
    })
    return out


def compact_assistant_content(content, payload=None):
    """Stub a presented artifact; keep short prose as-is."""
    text = _as_text(content)
    if is_already_stub(text):
        return text
    meta = inspect_payload(payload) if payload is not None else _empty_meta()
    if not meta.get('is_artifact'):
        html_meta = inspect_content(text)
        if html_meta.get('is_artifact') or (
            html_meta.get('rows') or html_meta.get('tables')
        ):
            meta = _merge_meta(meta, html_meta)
        elif not meta.get('title'):
            meta = html_meta
    if meta.get('is_artifact') or len(text) > FAT_CHARS:
        if not meta.get('chars'):
            meta['chars'] = len(text)
        if not meta.get('kind') or meta.get('kind') == 'reply':
            meta['kind'] = 'table' if meta.get('rows') else 'text'
        meta['is_artifact'] = True
        return format_stub(meta)
    kept = _strip_html(text) if '<' in text else text
    return _clip(kept, ASSISTANT_KEEP_CHARS)


def inspect_payload(payload):
    """Structural shape of a presentation payload (rows/columns/title)."""
    meta = _empty_meta()
    if not isinstance(payload, dict):
        return meta
    title = payload.get('title') or payload.get('name')
    if isinstance(title, str) and title.strip():
        meta['title'] = title.strip()
    rows, columns, ntables = _collect_rows(payload)
    if rows:
        meta['is_artifact'] = True
        meta['kind'] = 'table'
        meta['rows'] = rows
        meta['columns'] = columns
        meta['tables'] = ntables
        return meta
    formatted = payload.get('formatted_text')
    if isinstance(formatted, str) and formatted.strip():
        html_meta = inspect_content(formatted)
        if meta.get('title') and not html_meta.get('title'):
            html_meta['title'] = meta['title']
        return html_meta
    pins = payload.get('map_pins')
    if payload.get('map_url') or payload.get('pins_url') or pins:
        n = len(pins) if isinstance(pins, list) else 0
        meta['is_artifact'] = True
        meta['kind'] = 'map'
        meta['rows'] = n
        return meta
    return meta


def inspect_content(text):
    """Detect tables/maps in HTML, Markdown, or stripped cell dumps."""
    meta = _empty_meta()
    if not text or not isinstance(text, str):
        return meta
    meta['chars'] = len(text)
    title = _title_from_html(text)
    if title:
        meta['title'] = title
    images = _images_from_html(text)
    rows, columns, ntables = _datasets_from_html(text)
    if rows or ntables:
        meta['is_artifact'] = True
        meta['kind'] = 'table'
        meta['rows'] = rows
        meta['columns'] = columns
        meta['tables'] = ntables or (1 if rows else 0)
        if images:
            meta['images'] = images
        return meta
    if 'o_chatboo_table_block' in text or '<table' in text.lower():
        tr = max(0, text.lower().count('<tr') - 1)
        meta['is_artifact'] = True
        meta['kind'] = 'table'
        meta['rows'] = tr
        meta['tables'] = max(1, text.lower().count('<table'))
        if images:
            meta['images'] = images
        return meta
    if 'o_chatboo_map' in text or 'map_url' in text:
        meta['is_artifact'] = True
        meta['kind'] = 'map'
        return meta
    if images:
        meta['is_artifact'] = True
        meta['kind'] = 'image'
        meta['images'] = images
        return meta
    md = _markdown_table_meta(text)
    if md.get('is_artifact'):
        if title:
            md['title'] = title
        return md
    if len(text) > FAT_CHARS:
        meta['is_artifact'] = True
        meta['kind'] = 'text'
    return meta


def format_stub(meta):
    """One short English stub. No cell values (they are identifiers, not facts)."""
    meta = meta or {}
    kind = meta.get('kind') or 'text'
    parts = [STUB_PREFIX, 'kind=%s' % kind]
    ntables = int(meta.get('tables') or 0)
    if ntables > 1:
        parts.append('%s tables' % ntables)
    rows = int(meta.get('rows') or 0)
    columns = _public_columns(meta.get('columns') or [])
    if kind == 'map' and rows:
        parts.append('%s pins' % rows)
    elif rows:
        if columns:
            parts.append('%s rows × %s columns' % (rows, len(columns)))
        else:
            parts.append('%s rows' % rows)
    elif meta.get('chars'):
        parts.append('~%s characters' % int(meta.get('chars') or 0))
    images = meta.get('images') or []
    if images:
        parts.append('%s image%s' % (len(images), '' if len(images) == 1 else 's'))
        refs = [_image_ref_label(src, alt) for src, alt in images[:3]]
        if refs:
            parts.append('[%s]' % '; '.join(refs))
    if columns:
        parts.append('columns: %s' % ', '.join(columns))
    title = meta.get('title')
    if isinstance(title, str) and title.strip():
        safe = _clip(_strip_html(title), MAX_TITLE_CHARS).replace('|', '/')
        if safe:
            parts.append('title=%s' % safe)
    header = ' | '.join(parts) + ']'
    return header + '\n' + STUB_FOOTER


def history_char_count(history):
    """Cheap size metric for logs (not a tokenizer)."""
    total = 0
    for msg in history or []:
        if not isinstance(msg, dict):
            continue
        total += len(_as_text(msg.get('content')))
        if msg.get('tool_calls'):
            try:
                total += len(json.dumps(msg.get('tool_calls'), ensure_ascii=False))
            except Exception:
                pass
    return total


def _empty_meta():
    return {
        'is_artifact': False,
        'kind': 'reply',
        'rows': 0,
        'columns': [],
        'title': None,
        'tables': 0,
        'chars': 0,
        'images': [],
    }


def _merge_meta(base, extra):
    out = dict(base or _empty_meta())
    extra = extra or {}
    if extra.get('is_artifact'):
        out['is_artifact'] = True
    if extra.get('kind') and extra.get('kind') != 'reply':
        out['kind'] = extra['kind']
    if extra.get('rows') and not out.get('rows'):
        out['rows'] = extra['rows']
    if extra.get('columns') and not out.get('columns'):
        out['columns'] = extra['columns']
    if extra.get('tables') and not out.get('tables'):
        out['tables'] = extra['tables']
    if extra.get('title') and not out.get('title'):
        out['title'] = extra['title']
    if extra.get('chars') and not out.get('chars'):
        out['chars'] = extra['chars']
    if extra.get('images') and not out.get('images'):
        out['images'] = extra['images']
    return out


def _public_columns(columns):
    out = []
    for col in columns or []:
        name = str(col).strip()
        if not name or _INTERNAL_KEY_RE.match(name):
            continue
        out.append(name)
        if len(out) >= MAX_COLUMNS:
            break
    return out


def _collect_rows(payload):
    """Count rows and first-row columns from a presentation envelope."""
    total = 0
    columns = []
    ntables = 0

    def _eat(rows):
        nonlocal total, columns, ntables
        if not isinstance(rows, list) or not rows:
            return
        ntables += 1
        total += len(rows)
        if not columns and isinstance(rows[0], dict):
            columns = list(rows[0].keys())

    if isinstance(payload.get('data'), list) and payload.get('data'):
        _eat(payload.get('data'))
    for key in ('tables', 'groups', 'sections'):
        for block in payload.get(key) or []:
            if not isinstance(block, dict):
                continue
            _eat(block.get('data') or block.get('rows'))
    return total, _public_columns(columns), ntables


def _datasets_from_html(text):
    total = 0
    columns = []
    ntables = 0
    for match in _DATASET_ATTR_RE.finditer(text or ''):
        raw = html_lib.unescape(match.group(2) or '')
        try:
            data = json.loads(raw)
        except Exception:
            ntables += 1
            continue
        if isinstance(data, list) and data:
            ntables += 1
            total += len(data)
            if not columns and isinstance(data[0], dict):
                columns = _public_columns(list(data[0].keys()))
        elif data:
            ntables += 1
    return total, columns, ntables


def _title_from_html(text):
    match = _TITLE_RE.search(text or '')
    if not match:
        return None
    raw = next((g for g in match.groups() if g), '') or ''
    title = _strip_html(raw)
    return _clip(title, MAX_TITLE_CHARS) or None


def _markdown_table_meta(text):
    meta = _empty_meta()
    lines = [
        ln for ln in (text or '').splitlines()
        if ln.strip().startswith('|')
    ]
    if len(lines) < 2:
        return meta
    header = [c.strip() for c in lines[0].strip().strip('|').split('|')]
    header = [c for c in header if c]
    body = [
        ln for ln in lines[1:]
        if not _MD_SEP_RE.match(ln.strip())
    ]
    if not header or not body:
        return meta
    meta['is_artifact'] = True
    meta['kind'] = 'table'
    meta['rows'] = len(body)
    meta['columns'] = _public_columns(header)
    meta['tables'] = 1
    return meta


def _message_text(msg):
    if not isinstance(msg, dict):
        return ''
    return _as_text(msg.get('content'))


def _as_text(content):
    if content is None:
        return ''
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get('type') == 'text':
                    parts.append(item.get('text') or '')
                elif item.get('text'):
                    parts.append(str(item.get('text')))
        return '\n'.join(p for p in parts if p)
    return str(content)


def _image_ref_label(src, alt=''):
    """Short [image: path] token for stubs (never a data: payload)."""
    src = (src or '').strip()
    alt = (alt or '').strip()
    if src.lower().startswith('data:'):
        src = 'inline-image'
    elif '?' in src:
        src = src.split('?', 1)[0]
    if len(src) > 160:
        src = '…' + src[-159:]
    if alt:
        return 'image: %s (%s)' % (src, alt)
    return 'image: %s' % (src or 'unnamed')


def _images_from_html(text):
    """(src, alt) pairs from ``<img>`` tags. Structural, no domain."""
    out = []
    for match in _IMG_TAG_RE.finditer(text or ''):
        attrs = match.group(1) or ''
        src_m = _IMG_SRC_RE.search(attrs)
        alt_m = _IMG_ALT_RE.search(attrs)
        src = src_m.group(1) if src_m else ''
        alt = alt_m.group(1) if alt_m else ''
        if src or alt:
            out.append((src, alt))
    return out


def _strip_html(text):
    if not text:
        return ''

    def _keep_img(match):
        attrs = match.group(1) or ''
        src_m = _IMG_SRC_RE.search(attrs)
        alt_m = _IMG_ALT_RE.search(attrs)
        src = src_m.group(1) if src_m else ''
        alt = alt_m.group(1) if alt_m else ''
        return ' [%s] ' % _image_ref_label(src, alt)

    kept = _IMG_TAG_RE.sub(_keep_img, str(text))
    cleaned = _TAG_RE.sub(' ', kept)
    cleaned = html_lib.unescape(cleaned)
    return re.sub(r'\s+', ' ', cleaned).strip()


def _clip(text, limit):
    text = text or ''
    if limit <= 0 or len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + '…'
