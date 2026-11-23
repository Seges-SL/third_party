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
    'o_ai_table_block',
    'o_ai_data_table',
    'o_ai_namelink',
)


def content_has_delivery(text):
    """True if the content already delivers a table or a deep-link (no cross import)."""
    if not text or not isinstance(text, str):
        return False
    if _WEB_ID_RE.search(text):
        return True
    return any(m in text for m in _TABLE_MARKERS)


# Shape threshold (Unicode chars), not a word dictionary.
SHORT_USER_MSG_CHARS = 64
# LLM close without tabular delivery: if it is long, it is another answer (do not
# re-inject the dataset). Structural, not lexical.
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
    """1a: there was a tabular payload this turn and the bubble did not deliver records.

    Does not force it if the close is already substantial: the AI chose to narrate (inspect /
    prose). Only re-injects when the close is thin (it forgot to paint the listing).
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
    """First tabular list of dicts of a RelaxAICode result (for the cache)."""
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


TABLE_KEY = '__table__'


def _block_rows(block):
    for key in ('data', 'items', 'rows'):
        rows = block.get(key)
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            return rows
    return None


def all_tabular_rows(result):
    """Rows of every table in the result, for the next turn's ``previous_result``.

    With several tables each row carries ``__table__`` (its table title, or its
    position) so ``previous_result_envelope`` can rebuild the same tables.
    One table: the same rows as ``first_tabular_rows``.
    """
    if isinstance(result, dict):
        for envelope in ('groups', 'sections', 'tables'):
            blocks = result.get(envelope)
            if not isinstance(blocks, list):
                continue
            filled = [
                (b, _block_rows(b)) for b in blocks if isinstance(b, dict)
            ]
            filled = [(b, rows) for b, rows in filled if rows]
            if len(filled) < 2:
                break
            out = []
            for index, (block, rows) in enumerate(filled):
                label = block.get('title') or block.get('name') or str(index + 1)
                for row in rows:
                    tagged = dict(row)
                    tagged[TABLE_KEY] = str(label)
                    out.append(tagged)
            return out
    return first_tabular_rows(result)


def skill_result_events(code_body, payload, max_bytes=0):
    """The ``query_code`` / ``query_data`` events of a skill result.

    A skill resolved outside the tool loop (fast-path HTML, report handoff)
    leaves the session what a successful ``relaxaicode`` leaves: the code
    that made the table and its rows. The next turn then gets them as
    ``prior_query_code`` and ``previous_result``, so "now for 2025" after a
    skill narrows the same data instead of starting over. Same byte cap as
    the tool loop (0 = none); over it, only the code travels.
    """
    import json

    if isinstance(code_body, str) and code_body.strip():
        yield {'event': 'query_code', 'code': code_body}
    try:
        rows = all_tabular_rows(payload)
    except Exception:
        rows = None
    if not (isinstance(rows, list) and rows):
        return
    try:
        size = len(json.dumps(rows, default=str, ensure_ascii=False).encode('utf-8'))
    except Exception:
        return
    if not max_bytes or max_bytes <= 0 or size <= max_bytes:
        yield {'event': 'query_data', 'data': list(rows)}


def previous_result_envelope(rows):
    """``{'data': rows}``, plus ``tables`` when the rows came from several tables."""
    envelope = {'data': rows}
    if not isinstance(rows, list):
        return envelope
    tables = []
    by_label = {}
    for row in rows:
        if not isinstance(row, dict) or TABLE_KEY not in row:
            return envelope
        label = row[TABLE_KEY]
        if label not in by_label:
            by_label[label] = {'title': label, 'data': []}
            tables.append(by_label[label])
        clean = dict(row)
        clean.pop(TABLE_KEY, None)
        by_label[label]['data'].append(clean)
    if len(tables) > 1:
        envelope['tables'] = tables
    return envelope


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
