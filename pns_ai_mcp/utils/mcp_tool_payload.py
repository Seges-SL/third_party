# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Desenvolver el sobre MCP {content:[{type:text, text:<json>}]} → payload."""
from __future__ import annotations

import html
import json
import re
import logging

_logger = logging.getLogger(__name__)

# Pie cálido local (sin LLM): sin cifras, sin años, sin periodos concretos.
# Neutro a propósito: no todo lo que se pide tiene un "periodo".
_DEFAULT_WARM_FOOTER_EN = (
    'Here you go. If you need anything else, just tell me.'
)


def unwrap_tool_payload(tool_result):
    """Payload interno de un resultado de tool, o el dict original si ya lo es."""
    if not isinstance(tool_result, dict):
        return None
    blocks = tool_result.get('content')
    if (
        isinstance(blocks, list) and blocks
        and isinstance(blocks[0], dict) and blocks[0].get('type') == 'text'
    ):
        try:
            inner = json.loads(blocks[0].get('text') or '{}')
        except Exception:
            return None
        return inner if isinstance(inner, dict) else None
    return tool_result


def rewrap_tool_payload(tool_result, payload):
    """Write ``payload`` back where ``unwrap_tool_payload`` read it.

    The inner payload of a wrapped result is a copy parsed from text. What
    the engine adds to that copy (a page url laid out from the rows) is
    lost unless it goes back into the text the bubble reads.
    """
    if not isinstance(tool_result, dict) or not isinstance(payload, dict):
        return False
    if payload is tool_result:
        return True
    blocks = tool_result.get('content')
    if not (
        isinstance(blocks, list) and blocks
        and isinstance(blocks[0], dict) and blocks[0].get('type') == 'text'
    ):
        return False
    try:
        blocks[0]['text'] = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return False
    return True


def summarize_safe_plan_request(result_str, max_len=480):
    """One-line ai.log summary for ``safe_plan_request`` tool results.

    Failures must surface the real ``error`` (schema, permissions, …). Never
    paint ``safe plan []`` when ``verification_id`` is missing on a reject —
    that hides why the request failed and nudges the LLM into catalogue theatre.
    """
    fallback = 'Proposed (supervised)'
    try:
        wrapper = json.loads(result_str or '{}')
    except Exception:
        return fallback
    payload = unwrap_tool_payload(wrapper) if isinstance(wrapper, dict) else None
    if not isinstance(payload, dict):
        return fallback
    err = payload.get('error')
    if payload.get('success') is False or err:
        return (
            'Propose failed: %s' % (err or 'safe_plan_request failed')
        )[:max_len]
    title = payload.get('title') or 'safe plan'
    vid = payload.get('verification_id') or ''
    status = payload.get('status') or ''
    return (
        'Proposed: %s [%s] %s' % (title, vid, status)
    )[:max_len]


def is_author_html_payload(payload):
    """True si el HTML lo generó el skill/código (no la tabla server-side)."""
    if not isinstance(payload, dict) or not payload.get('formatted_text'):
        return False
    return payload.get('__fmt_type__') != 'server_side_python'


def resolve_author_footer(payload):
    """Preferencia de pie declarada por el skill/código (author_html).

    El pie ya no es un texto fijo impuesto siempre: cada skill decide.
    Devuelve ``(suppress, text)``:

    - ``suppress=True`` → omitir el pie (no repetir obviedades; p. ej. un
      listado que ya trae su propio contador «Total: N»). Se activa con
      ``__no_footer__``/``__skip_footer__`` o con ``footer=''`` explícito.
    - ``text`` (str no vacío) → pie compuesto por el AUTOR del skill
      (determinista, sin alucinación); tiene prioridad sobre el genérico.
    - ``(False, None)`` → sin preferencia: pie cálido genérico por defecto.
    """
    if not isinstance(payload, dict):
        return (False, None)
    if payload.get('__no_footer__') or payload.get('__skip_footer__'):
        return (True, None)
    for key in ('__footer__', 'footer', 'pie'):
        if key in payload:
            val = payload.get(key)
            if isinstance(val, str):
                stripped = val.strip()
                return (False, stripped) if stripped else (True, None)
    return (False, None)


def append_local_warm_footer(html_content, footer_text=None):
    """Añade un pie humano fijo al HTML (el servidor, no el LLM).

    Evita la 2.ª vuelta en la que el modelo inventaba años o cifras.
    """
    if not html_content:
        return html_content
    text = (footer_text or _DEFAULT_WARM_FOOTER_EN).strip()
    if not text:
        return html_content
    # No duplicar si el skill ya cerró con un párrafo similar
    if 'o_ai_local_footer' in html_content:
        return html_content
    return (
        '%s<p class="text-muted mt-2 mb-0 o_ai_local_footer">%s</p>'
        % (html_content, html.escape(text))
    )


# ---------------------------------------------------------------------------
# compose-model (provider, /compose-model, or skill compose: compose-model)
#
# compose-agent (OFF): Chatboo paints HTML tables + charts; LLM writes a short
# footer (or nothing if foot-laconic).
# compose-model (ON): the LLM owns the ENTIRE response UI — Markdown, HTML,
# Chatboo table/chart blocks, mix. Nothing is forbidden. The server does not
# auto-push a table into the bubble; it hands data + optional formatted_text
# so the model can embed native charts if it wants. footmode and showmode
# are suspended for that bubble.
#
# Isolation: compose-model branches MUST gate on the remote flag. When OFF,
# handoff/hints are never applied. Pure author_html without rows still
# delivers locally.
# ---------------------------------------------------------------------------

REMOTE_FORMAT_SYSTEM_HINT = (
    '[compose-model] You own the ENTIRE response UI for this turn. '
    'The server will NOT auto-push a chat table or Gráfico toolbar. '
    'Markdown/HTML prose for narrative, greetings, captions and drawings — '
    'never a pipe table. footmode and showmode do not apply. '
    'A drawing the user asked for: emit the SVG markup; the chat files it as a '
    'session chip — leftover text stays prose. Do not wrap that text in a table. '
    'DATA PLOTS only when THIS turn has real rows/series: then you MAY embed '
    'data-ai-dataset or formatted_text table HTML. SINGLE-FACT CARD: '
    '{"card": {kind: "fact"|"link", …}} (data-ai-card). '
    'Time/date: several places → structured rows; not kind clock. LINK CARD: '
    '{"card": {kind: "link", url, title}}. Do not emit SVG paths for bar/line/pie '
    'plots. Do NOT claim a table is already visible unless you embedded it. '
    'Do NOT answer with only a warm footer.'
)

_REMOTE_FORMAT_NOTE = (
    'This dataset was NOT shown to the user yet. You compose the bubble. '
    'You may embed `formatted_text` (native tables/charts), write Markdown, '
    'or mix both. Charts are allowed. Use ONLY these figures. Do NOT claim '
    'a table is already visible unless you embedded it. Do NOT write only a '
    'short footer.'
)



def payload_has_svg_cards(payload):
    """True when the result carries a Chatboo SVG card (facts, not a table)."""
    if not isinstance(payload, dict):
        return False
    card = payload.get('card')
    if isinstance(card, dict) and card:
        return True
    if isinstance(card, list) and any(isinstance(c, dict) for c in card):
        return True
    cards = payload.get('cards')
    return isinstance(cards, list) and any(isinstance(c, dict) for c in cards)


def payload_has_tabular_rows(payload):
    """True when payload carries row/group data the LLM can format as Markdown."""
    if not isinstance(payload, dict):
        return False
    data = payload.get('data')
    if not (isinstance(data, list) and data and isinstance(data[0], dict)):
        data = payload.get('items')
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return True
    return any(
        isinstance(payload.get(k), list) and payload.get(k)
        for k in ('groups', 'sections', 'tables')
    )


# compose-agent same-turn stub (no cells). Errors stay intact.
_LOCAL_STUB_MAX_COLUMNS = 12
_LOCAL_STUB_TITLE_CHARS = 160
LOCAL_TABULAR_STUB_NOTE = (
    'Dataset is already shown to the user and cached as previous_result. '
    'Do not reprint the rows. Write a short footer only if needed.'
)
COMPOSE_MODEL_OVERFLOW_HINT = (
    'compose-model could not format that list in the model. '
    'Ask again with /compose-agent for a server table. '
    'The compose mode did not change.'
)


def _payload_is_tool_error(payload):
    if not isinstance(payload, dict):
        return False
    return bool(
        payload.get('__force_retry__')
        or payload.get('error')
        or payload.get('isError')
    )


def _first_tabular_row_list(payload):
    """First list of row dicts. Column names / count only — no cell values."""
    if not isinstance(payload, dict):
        return []
    for key in ('data', 'items'):
        data = payload.get(key)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data
    for key in ('groups', 'sections', 'tables'):
        block = payload.get(key)
        if not isinstance(block, list):
            continue
        for item in block:
            if isinstance(item, dict):
                rows = item.get('data') or item.get('rows') or item.get('items')
                if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                    return rows
            elif isinstance(item, list) and item and isinstance(item[0], dict):
                return item
    return []


def _tabular_row_count(payload):
    rows = _first_tabular_row_list(payload)
    if rows:
        return len(rows)
    total = 0
    for key in ('groups', 'sections', 'tables'):
        block = payload.get(key) if isinstance(payload, dict) else None
        if not isinstance(block, list):
            continue
        for item in block:
            if isinstance(item, dict):
                inner = item.get('data') or item.get('rows') or item.get('items')
                if isinstance(inner, list):
                    total += len(inner)
            elif isinstance(item, list):
                total += len(item)
    if total:
        return total
    for key in ('groups', 'sections', 'tables'):
        block = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(block, list) and block:
            return len(block)
    return 0


def _tabular_columns(payload):
    rows = _first_tabular_row_list(payload)
    if not rows:
        return []
    keys = []
    for key in rows[0].keys():
        if str(key).startswith('_'):
            continue
        keys.append(key)
        if len(keys) >= _LOCAL_STUB_MAX_COLUMNS:
            break
    return keys


def local_tabular_stub_payload(payload):
    """Structural stub: rows × columns, no cell values."""
    stub = {
        'on_screen': True,
        'previous_result': True,
        'data_rendered': True,
        'rows': _tabular_row_count(payload),
        'columns': _tabular_columns(payload),
        'note': LOCAL_TABULAR_STUB_NOTE,
    }
    if isinstance(payload, dict):
        for key in ('summary', 'title'):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                stub[key] = val.strip()[:_LOCAL_STUB_TITLE_CHARS]
    return stub


def local_tool_result_for_llm(result):
    """Replace tabular cells with a stub. Errors / ``__force_retry__`` stay intact."""
    if not isinstance(result, dict):
        return result
    if _payload_is_tool_error(result):
        return result
    inner = unwrap_tool_payload(result)
    if inner is None:
        return result
    if _payload_is_tool_error(inner):
        return result
    if not payload_has_tabular_rows(inner):
        return result
    stub = local_tabular_stub_payload(inner)
    blocks = result.get('content')
    if (
        isinstance(blocks, list) and blocks
        and isinstance(blocks[0], dict)
        and blocks[0].get('type') == 'text'
    ):
        out = dict(result)
        out['content'] = [{
            'type': 'text',
            'text': json.dumps(stub, ensure_ascii=False, default=str),
        }]
        return out
    return stub


def local_owns_tabular_paint(
    remote_flag, payload, *, force_retry=False, inspect_only=False,
):
    """True when compose-agent must paint this table (and stub the LLM).

    ``inspect_only``: the model asked ``return_mode=inspect_result``. Its
    rows are a lookup for the next step, not the answer, so they stay off
    the bubble. A page it built or changed is still shown.
    """
    if remote_flag or force_retry:
        return False
    if _payload_is_tool_error(payload):
        return False
    try:
        from .result_page import has_page_url
    except ImportError:
        from result_page import has_page_url  # type: ignore
    if has_page_url(payload):
        return True
    if inspect_only:
        return False
    return payload_has_tabular_rows(payload)


def append_compose_model_overflow_hint(
    err, *, compose, sent_tabular, translate=None,
):
    """Visible hint when compose-model died after sending rows. Does not paint."""
    if compose != 'compose-model' or not sent_tabular:
        return err
    hint = COMPOSE_MODEL_OVERFLOW_HINT
    if translate:
        hint = translate(hint)
    if not err:
        return hint
    return '%s\n%s' % (err, hint)


def remote_owns_tabular_presentation(remote_flag, payload):
    """True when compose-model owns presentation of this payload.

    Isolation: with ``remote_flag`` False always False (local path unchanged).
    With True, any tabular payload is owned by the LLM (it may embed the
    HTML, rewrite it, or mix Markdown+charts). Pure author_html without
    rows stays local.
    """
    if not remote_flag:
        return False
    if payload_has_tabular_rows(payload):
        return True
    if payload_has_svg_cards(payload):
        return False
    if is_author_html_payload(payload):
        return False
    return True


_PROBE_NOT_SHOWN_NOTE = (
    'These rows were NOT shown to the user. They are a lookup, not the answer. '
    'Do not paste them as a table.'
)


def probe_json_for_llm(result):
    """Keep row values and drop chat HTML. The bubble did not get this probe."""
    if not isinstance(result, dict):
        return result
    inner = unwrap_tool_payload(result)
    if not isinstance(inner, dict):
        return result
    clean = dict(inner)
    for key in (
        'formatted_text',
        '__return_direct__',
        '__direct_return__',
        '__return_direct_to_user__',
        '__presentation_complete__',
        '__satisfied__',
        '__ready_for_presentation__',
    ):
        clean.pop(key, None)
    clean['__shown_to_user__'] = False
    clean['note'] = _PROBE_NOT_SHOWN_NOTE
    blocks = result.get('content')
    if (
        isinstance(blocks, list) and blocks
        and isinstance(blocks[0], dict)
        and blocks[0].get('type') == 'text'
    ):
        out = dict(result)
        out['content'] = [{
            'type': 'text',
            'text': json.dumps(clean, ensure_ascii=False, default=str),
        }]
        return out
    return clean


def tool_result_json_for_llm(result, remote_flag, shown_to_user=True):
    """Serialize a tool result for the LLM.

    compose-model: keep rows (strip delivery flags so the model formats).
    compose-agent: stub tabular cells; the chat already has the table.
    An unmarked multi-list probe (``shown_to_user=False``) keeps the row
    values and says the bubble did not get them.
    Errors / ``__force_retry__`` stay intact in both modes.
    """
    import json as _json
    if remote_flag:
        result = strip_server_html_for_remote(result)
    elif shown_to_user:
        result = local_tool_result_for_llm(result)
    else:
        result = probe_json_for_llm(result)
    return _json.dumps(result, ensure_ascii=False, default=str)


def strip_server_html_for_remote(result):
    """Mark tool HTML as not-yet-shown; keep ``formatted_text`` for the LLM.

    compose-model: the model owns the bubble. It needs the rendered HTML
    (chart datasets included) so it can embed native tables/charts.
    Delivery flags (``__return_direct__`` …) are dropped so the engine
    does not auto-push. Pure author_html without rows is left intact.

    Callers MUST only invoke this when compose-model is active.
    """
    if not isinstance(result, dict):
        return result

    def _strip_inner(inner):
        if not isinstance(inner, dict):
            return inner
        if is_author_html_payload(inner) and not payload_has_tabular_rows(inner):
            return inner
        if payload_has_svg_cards(inner) and not payload_has_tabular_rows(inner):
            return inner
        if not inner.get('formatted_text') and not payload_has_tabular_rows(inner):
            return inner
        if (
            inner.get('__fmt_type__') not in (None, 'server_side_python', 'author_html')
            and not payload_has_tabular_rows(inner)
        ):
            return inner
        cleaned = dict(inner)
        cleaned.pop('__return_direct__', None)
        cleaned.pop('__direct_return__', None)
        cleaned.pop('__stop_after_direct__', None)
        cleaned.pop('__presentation_complete__', None)
        cleaned['remote_format'] = True
        cleaned['data_rendered'] = False
        cleaned.setdefault('note', _REMOTE_FORMAT_NOTE)
        return cleaned

    blocks = result.get('content')
    if (
        isinstance(blocks, list) and blocks
        and isinstance(blocks[0], dict) and blocks[0].get('type') == 'text'
    ):
        try:
            inner = json.loads(blocks[0].get('text') or '{}')
        except Exception:
            return result
        cleaned_inner = _strip_inner(inner)
        if cleaned_inner is inner:
            return result
        out = dict(result)
        out['content'] = [{
            'type': 'text',
            'text': json.dumps(cleaned_inner, ensure_ascii=False, default=str),
        }]
        return out
    return _strip_inner(result)


def remote_format_handoff_payload(payload):
    """Tool-message body when remote formatting owns presentation.

    Returns None for non-tabular payloads (pure author_html stays local).
    Includes ``formatted_text`` when present so the LLM can embed native
    tables/charts. Callers MUST only use the result when report is active.
    """
    if not isinstance(payload, dict):
        return None
    if not payload_has_tabular_rows(payload):
        return None
    data = payload.get('data')
    if not (isinstance(data, list) and data and isinstance(data[0], dict)):
        data = payload.get('items')
    has_rows = isinstance(data, list) and data and isinstance(data[0], dict)
    out = {
        'remote_format': True,
        'data_rendered': False,
        'note': _REMOTE_FORMAT_NOTE,
    }
    if has_rows:
        out['data'] = data
    for key in (
        'summary', 'title', 'groups', 'sections', 'tables',
        # Keep rendered HTML so the LLM can embed native tables/charts.
        'formatted_text', '__fmt_type__', 'show_mode',
        # Skill-authored narrative contract (report mode): headings / closing
        # line the LLM must honour. Generic keys — no domain meaning here.
        'report_outline', 'closing_required', 'recommendations_stub',
        'recommendations_heading',
        # Optional company display name from the sandbox (res.company), not
        # translated — the LLM copies it as-is under the report title.
        'company',
    ):
        if payload.get(key) is not None:
            out[key] = payload[key]
    return out

