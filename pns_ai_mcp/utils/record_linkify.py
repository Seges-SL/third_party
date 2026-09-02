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
_TABLE_MARKERS = (
    'o_chatboo_table_block',
    'o_chatboo_data_table',
    'o_chatboo_namelink',
)


def content_delivers_records(text):
    """True si el contenido ya entrega tabla server-side o un deep-link Odoo."""
    if not text or not isinstance(text, str):
        return False
    if _WEB_ID_RE.search(text):
        return True
    return any(m in text for m in _TABLE_MARKERS)


def _record_form_md_url(model, rec_id):
    return '/web#id=%d&model=%s&view_type=form' % (int(rec_id), model)


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
