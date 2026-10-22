# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Auto-enlace de prosa con refs (model, id, name) ya resueltas en el turno.

Agnóstico de dominio: no ramifica por modelo ni por sinónimos de cabecera.
Solo enlaza etiquetas exactas presentes en ``collected_records``.
"""
from __future__ import annotations

import re

_WEB_ID_RE = re.compile(r'/web#id=\d+', re.IGNORECASE)
_MD_WEB_LINK = re.compile(
    r'\[([^\]]+)\]\((/web#id=(\d+)[^)]*)\)',
    re.IGNORECASE,
)
_HTML_A = re.compile(r'<a\b([^>]*)>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_HREF_IN_ATTRS = re.compile(
    r'''href\s*=\s*(["'])([^"']+)\1''',
    re.IGNORECASE,
)
_MODEL_IN_URL = re.compile(
    r'(?:[?&#]|amp;)model=([A-Za-z0-9._]+)',
    re.IGNORECASE,
)
_BARE_WEB = re.compile(r'(?<![("\'])(/web#id=\d+[^\s)<]*)', re.IGNORECASE)
_TABLE_MARKERS = (
    'o_ai_table_block',
    'o_ai_data_table',
    'o_ai_namelink',
)



def _record_form_md_url(model, rec_id):
    return '/web#id=%d&model=%s&view_type=form' % (int(rec_id), model)


def _pairs_from_records(records):
    """Allowed ``(model, id)`` from the tool, not from the model text."""
    pairs = set()
    ids = {}
    for ref in records or ():
        if not isinstance(ref, dict):
            continue
        model = ref.get('model') or ref.get('__model')
        rec_id = ref.get('id')
        if not model or not isinstance(model, str):
            continue
        try:
            rec_id = int(rec_id)
        except (TypeError, ValueError):
            continue
        model = model.strip()
        if not model:
            continue
        pairs.add((model, rec_id))
        ids[rec_id] = ids.get(rec_id, 0) + 1
    return pairs, ids


def _target_of_url(url):
    match = _WEB_ID_RE.search(url or '')
    if not match:
        return None, None
    try:
        rec_id = int(re.search(r'\d+', match.group(0)).group(0))
    except (TypeError, ValueError, AttributeError):
        return None, None
    model_m = _MODEL_IN_URL.search(url)
    model = model_m.group(1) if model_m else None
    return model, rec_id


def _is_allowed(model, rec_id, pairs, ids):
    if rec_id is None:
        return False
    if model and (model, rec_id) in pairs:
        return True
    if not model and ids.get(rec_id) == 1:
        return True
    return False


def drop_unverified_record_links(text, records, *, drop_all=False):
    """Keep ``/web#id=`` only when that pair came from the tool.

    Invented markdown or HTML links become the label. Renderer namelinks
    (``o_ai_namelink``) stay: those ids were written from the row, not
    from the model. No model-name check — a pair is a pair.
    """
    if not text or not isinstance(text, str):
        return text
    pairs, ids = _pairs_from_records(records)

    def keep(url):
        if drop_all:
            return False
        model, rec_id = _target_of_url(url)
        return _is_allowed(model, rec_id, pairs, ids)

    def md_sub(match):
        label, url = match.group(1), match.group(2)
        if keep(url):
            return match.group(0)
        return label

    out = _MD_WEB_LINK.sub(md_sub, text)

    def html_sub(match):
        attrs, inner = match.group(1), match.group(2)
        if 'o_ai_namelink' in attrs:
            return match.group(0)
        href_m = _HREF_IN_ATTRS.search(attrs)
        if not href_m or '/web#id=' not in href_m.group(2).lower():
            return match.group(0)
        if keep(href_m.group(2)):
            return match.group(0)
        return inner

    out = _HTML_A.sub(html_sub, out)

    def bare_sub(match):
        url = match.group(1)
        if keep(url):
            return url
        return ''

    return _BARE_WEB.sub(bare_sub, out)


def seal_record_links(text, records, *, links_off=False):
    """Drop invented ``/web#id=``, then wrap labels the tool already named."""
    cleaned = drop_unverified_record_links(
        text, records, drop_all=links_off,
    )
    if links_off:
        return cleaned
    return linkify_prose(cleaned, records, links_off=False)


def _already_linked(text, label, rec_id):
    if re.search(
        r'\[' + re.escape(label) + r'\]\(/web#id=%d\b' % rec_id,
        text,
    ):
        return True
    if re.search(
        r'href=["\'][^"\']*id=%d[^"\']*["\'][^>]*>[^<]*%s'
        % (rec_id, re.escape(label)),
        text,
        re.IGNORECASE,
    ):
        return True
    return False


def linkify_prose(text, records, *, links_off=False):
    """Envuelve etiquetas de ``records`` en Markdown ``[label](/web#…)``.

    - No inventa ids: solo usa refs del argumento.
    - No vuelve a enlazar si la etiqueta ya apunta a ese id.
    - Opt-out: ``links_off=True`` → texto intacto.
    - Empates: etiquetas más largas primero.
    """
    if links_off or not text or not isinstance(text, str):
        return text
    if not records:
        return text

    by_label = {}
    for ref in records:
        if not isinstance(ref, dict):
            continue
        model = ref.get('model')
        rec_id = ref.get('id')
        name = ref.get('name')
        if not model or not isinstance(model, str) or not name:
            continue
        try:
            rec_id = int(rec_id)
        except (TypeError, ValueError):
            continue
        label = str(name).strip()
        if len(label) < 2:
            continue
        key = label.casefold()
        if key not in by_label:
            by_label[key] = (label, model, rec_id)

    if not by_label:
        return text

    ordered = sorted(by_label.values(), key=lambda t: len(t[0]), reverse=True)
    out = text
    for label, model, rec_id in ordered:
        if _already_linked(out, label, rec_id):
            continue
        url = _record_form_md_url(model, rec_id)
        md = '[%s](%s)' % (label, url)
        # Word-boundary cuando el label es “palabra”; si no (códigos con /), find.
        if re.search(r'\w', label) and not re.search(r'[/\\]', label):
            pattern = re.compile(r'(?<!\[)\b' + re.escape(label) + r'\b(?!\]\()')
            out, n = pattern.subn(md, out, count=1)
            if n:
                continue
        idx = out.find(label)
        while idx >= 0:
            before = out[max(0, idx - 1):idx]
            # Ya dentro de [label](
            if before == '[':
                idx = out.find(label, idx + len(label))
                continue
            window = out[max(0, idx - 48):idx].lower()
            if 'href=' in window:
                idx = out.find(label, idx + len(label))
                continue
            out = out[:idx] + md + out[idx + len(label):]
            break
    return out
