# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Structural gate for delivering records with a link (no verb lexicon).

1a — same turn: there were tabular rows and the close did not deliver them.
    If the LLM already wrote a substantial (not thin) reply, keep it: it
    chose narrative delivery via return_mode/inspect — do not re-inject the grid.
1b — OFF: never re-inject prior_query_data into the bubble (topic echo).
    Reuse stays in the sandbox via previous_result/raw_data only when the
    code references it; the output anti-echo covers the HTML.
"""
from __future__ import annotations

import re

_WEB_ID_RE = re.compile(r'/web#id=\d+', re.IGNORECASE)
_TABLE_MARKERS = (
    'o_chatboo_table_block',
    'o_chatboo_data_table',
    'o_chatboo_namelink',
)


def content_has_delivery(text):
    """True si el contenido ya entrega tabla o deep-link (sin import cruzado)."""
    if not text or not isinstance(text, str):
        return False
    if _WEB_ID_RE.search(text):
        return True
    return any(m in text for m in _TABLE_MARKERS)


# Umbral de forma (Unicode chars), no diccionario de palabras.
SHORT_USER_MSG_CHARS = 64
# Cierre LLM sin entrega tabular: si es largo, es otra respuesta (no reinyectar
# el dataset). Estructural, no léxico.
THIN_FINAL_CHARS = 280



def is_thin_final_content(text, *, limit=THIN_FINAL_CHARS):
    if not isinstance(text, str):
        return True
    return len(text.strip()) <= int(limit)


def bubble_with_delivered(delivered_html, html):
    """What a closing ``replace`` must carry: the table already on screen.

    A client reads ``replace`` as "this is the bubble now". The closing line
    of a turn that already painted a grid is prose — sent on its own it wipes
    the rows the user is about to tap.
    """
    if not delivered_html:
        return html
    if content_has_delivery(html):
        return html
    prose = (html or '').strip()
    if not prose:
        return delivered_html
    return '%s\n\n%s' % (delivered_html, prose)


def should_force_turn_payload(
    final_content,
    *,
    last_tabulable_payload,
    table_already_delivered,
):
    """1a: hubo payload tabulable este turno y la burbuja no entregó registros.

    No fuerza si el cierre ya es sustancial: la IA eligió narrar (inspect /
    prosa). Solo reinyecta cuando el cierre es thin (olvidó pintar el listing).
    """
    if table_already_delivered:
        return False
    if not last_tabulable_payload:
        return False
    if content_has_delivery(final_content):
        return False
    if not is_thin_final_content(final_content):
        return False
    return True


def first_tabular_rows(result):
    """Primera lista de dicts tabulable de un resultado RelaxAICode (para cache)."""
    if isinstance(result, list) and result and isinstance(result[0], dict):
        return list(result)
    if not isinstance(result, dict):
        return None
    data = result.get('data')
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return list(data)
    items = result.get('items')
    if isinstance(items, list) and items and isinstance(items[0], dict):
        return list(items)
    for envelope in ('groups', 'sections', 'tables'):
        blocks = result.get(envelope)
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            for key in ('data', 'items', 'rows'):
                rows = block.get(key)
                if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                    return list(rows)
    for key, val in result.items():
        if str(key).startswith('_'):
            continue
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return list(val)
    return None


def rows_from_safe_plan_steps(steps):
    """Extract list-of-dicts from confirmed safe-plan step results.

    Invariant: structural only — parse ``body`` JSON from successful
    ``api_call`` / ``fetch_url`` steps; never hardcode servers or tools.
    Concatenates list payloads; single-object ``data`` dicts become one row each.
    """
    import json as _json

    lists = []
    singles = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        if step.get('success') is False:
            continue
        op = (step.get('op') or '').strip()
        if op not in ('api_call', 'mcp_call', 'fetch_url'):
            continue
        body = step.get('body')
        if body is None:
            body = step.get('result')
        if isinstance(body, str):
            try:
                body = _json.loads(body)
            except Exception:
                continue
        rows = first_tabular_rows(body) if isinstance(body, (dict, list)) else None
        if rows:
            lists.append(rows)
            continue
        if isinstance(body, dict):
            data = body.get('data')
            if isinstance(data, dict):
                singles.append(data)
    if lists:
        out = []
        for chunk in lists:
            out.extend(chunk)
        return out or None
    if singles:
        return list(singles)
    return None


def previous_result_envelope_from_safe_plan(steps, rows=None):
    """Build the Nivel-2 envelope after a confirmed safe plan.

    ``data`` — flattened tabulable rows (restyle / strip-rebind).
    ``safe_plan_steps`` — raw step results (incl. failures) so presentation
    code can branch by ``tool`` / ``op`` / ``body`` without guessing unwrap.
    """
    if rows is None:
        rows = rows_from_safe_plan_steps(steps)
    envelope = {}
    if isinstance(rows, list) and rows:
        envelope['data'] = list(rows)
    if isinstance(steps, list) and steps:
        envelope['safe_plan_steps'] = list(steps)
    return envelope or None


def get_safe_plan_steps(previous_result=None):
    """Return the step-result list from a Nivel-2 ``previous_result`` envelope.

    Prefers ``safe_plan_steps``. Also accepts a bare list of steps, or
    ``result`` / ``steps`` keys. Does **not** treat flattened ``data`` rows
    as steps (those lack ``op``/``tool``/``body``).
    """
    if previous_result is None:
        return []
    if isinstance(previous_result, list):
        if (
            previous_result
            and isinstance(previous_result[0], dict)
            and _looks_like_safe_plan_step(previous_result[0])
        ):
            return list(previous_result)
        return []
    if not isinstance(previous_result, dict):
        return []
    for key in ('safe_plan_steps', 'result', 'steps'):
        val = previous_result.get(key)
        if (
            isinstance(val, list)
            and val
            and isinstance(val[0], dict)
            and _looks_like_safe_plan_step(val[0])
        ):
            return list(val)
    return []


def _looks_like_safe_plan_step(row):
    if not isinstance(row, dict):
        return False
    if row.get('op') in ('api_call', 'mcp_call', 'fetch_url', 'create', 'write',
                         'unlink', 'copy'):
        return True
    if row.get('tool') and (row.get('body') is not None or 'success' in row):
        return True
    if row.get('url') and row.get('op') == 'fetch_url':
        return True
    return False


def parse_safe_plan_step_body(step):
    """Parse ``body`` (JSON string or dict) from one step; ``{}`` on failure."""
    import json as _json

    if not isinstance(step, dict):
        return {}
    body = step.get('body')
    if body is None:
        body = step.get('result')
    if isinstance(body, str):
        try:
            body = _json.loads(body)
        except Exception:
            return {}
    return body if isinstance(body, dict) else {}
