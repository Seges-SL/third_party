# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Anti-eco de tablas: no reemitir datasets ya mostrados en el historial.

Invariante: el contexto (historial + cache) se recuerda; la burbuja del turno
NO puede repetir un bloque tabular cuya huella de dataset ya salió en un
mensaje assistant anterior, salvo que este mismo turno lo haya regenerado
vía tool (``allow_fingerprints``).

Sin hardcode de dominio: solo huella estructural de ``data-chatboo-dataset``.
"""
from __future__ import annotations

import hashlib
import html
import json
import re

_DATASET_ATTR_RE = re.compile(
    r'data-chatboo-dataset=(["\'])(.*?)\1',
    re.IGNORECASE | re.DOTALL,
)
_TABLE_OPEN_RE = re.compile(
    r'<div\b[^>]*\bo_chatboo_table_block\b[^>]*>',
    re.IGNORECASE,
)


def fingerprint_dataset_payload(raw_json_or_obj) -> str:
    """Huella estable del dataset (JSON canónico)."""
    if isinstance(raw_json_or_obj, (list, dict)):
        data = raw_json_or_obj
    else:
        text = html.unescape(str(raw_json_or_obj or ''))
        try:
            data = json.loads(text)
        except Exception:
            data = text
    try:
        canon = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    except Exception:
        canon = str(data)
    return hashlib.sha256(canon.encode('utf-8')).hexdigest()


def extract_dataset_fingerprints(content: str) -> set:
    """Huellas de todos los data-chatboo-dataset en un HTML/texto."""
    fps = set()
    if not content or not isinstance(content, str):
        return fps
    for match in _DATASET_ATTR_RE.finditer(content):
        fps.add(fingerprint_dataset_payload(match.group(2)))
    return fps


def fingerprints_from_history(history) -> set:
    """Huellas de tablas ya entregadas en mensajes assistant previos."""
    fps = set()
    for msg in history or []:
        if not isinstance(msg, dict):
            continue
        if msg.get('role') != 'assistant':
            continue
        fps |= extract_dataset_fingerprints(msg.get('content') or '')
    return fps


def _find_div_block_end(text: str, start: int) -> int:
    """Fin (exclusivo) del ``<div>...</div>`` que empieza en ``start``."""
    if start < 0 or start >= len(text) or not text.startswith('<div', start):
        return -1
    i = start
    depth = 0
    lower = text  # case-sensitive find of tags; Odoo HTML uses lowercase
    n = len(lower)
    while i < n:
        if lower.startswith('</div', i):
            end_gt = lower.find('>', i)
            if end_gt < 0:
                return -1
            depth -= 1
            i = end_gt + 1
            if depth == 0:
                return i
            continue
        if lower.startswith('<div', i):
            # '<div' but not '</div' (already handled)
            end_gt = lower.find('>', i)
            if end_gt < 0:
                return -1
            # self-closing rare; treat as open
            depth += 1
            i = end_gt + 1
            continue
        i += 1
    return -1


def iter_table_block_spans(content: str):
    """Yields (start, end, fingerprint|None) for each o_chatboo_table_block."""
    if not content or 'o_chatboo_table_block' not in content:
        return
    for open_m in _TABLE_OPEN_RE.finditer(content):
        start = open_m.start()
        end = _find_div_block_end(content, start)
        if end < 0:
            continue
        block = content[start:end]
        fps = extract_dataset_fingerprints(block)
        fp = next(iter(fps), None) if fps else None
        yield start, end, fp


def strip_echoed_table_blocks(
    content: str,
    prior_fingerprints: set,
    *,
    allow_fingerprints: set | None = None,
) -> str:
    """Elimina bloques tabla cuyo dataset ya salió en historial (salvo allow)."""
    if not content or not prior_fingerprints:
        return content
    allow = allow_fingerprints or set()
    spans = list(iter_table_block_spans(content))
    if not spans:
        return content
    remove = [
        (start, end)
        for start, end, fp in spans
        if fp and fp in prior_fingerprints and fp not in allow
    ]
    if not remove:
        return content
    out = []
    cursor = 0
    for start, end in remove:
        out.append(content[cursor:start])
        cursor = end
        while cursor < len(content) and content[cursor] in '\n\r':
            cursor += 1
    out.append(content[cursor:])
    return ''.join(out).strip()


def code_references_reuse_names(code: str) -> bool:
    """True si el AST usa ``previous_result`` o ``raw_data`` como Name (no comentario)."""
    if not code or not isinstance(code, str):
        return False
    import ast
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    wanted = {'previous_result', 'raw_data'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in wanted:
            return True
    return False
