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


def mark_terminal_resource(facts):
    """Marca un JSON plano de recurso como respuesta final (pinta y para).

    Invariante de esquema ``system://``: el snapshot YA es la respuesta.
    El motor no debe devolverlo al LLM (eso dispara Relaxaicode de adorno).
    No añade hechos: solo flags de entrega y una vista ``data`` key/value
    de los mismos campos.
    """
    if not isinstance(facts, dict):
        facts = {}
    payload = dict(facts)
    payload['data'] = [
        {'key': key, 'value': facts[key]}
        for key in facts
        if not str(key).startswith('_')
    ]
    payload['__return_direct__'] = True
    payload['__stop_after_direct__'] = True
    payload['__no_footer__'] = True
    return payload


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


def summarize_propose_tool_result(result_str, max_len=480):
    """One-line ai.log summary for ``propose_safe_operations`` tool results.

    Failures must surface the real ``error`` (schema, permissions, …). Never
    paint ``safe plan []`` when ``verification_id`` is missing on a reject —
    that hides why propose failed and nudges the LLM into catalogue theatre.
    """
    fallback = 'Proposed supervised write (safe plan)'
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
            'Propose failed: %s' % (err or 'propose_safe_operations failed')
        )[:max_len]
    title = payload.get('title') or 'safe plan'
    vid = payload.get('verification_id') or ''
    status = payload.get('status') or ''
    return (
        'Proposed supervised write: %s [%s] %s' % (title, vid, status)
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
    if 'o_chatboo_local_footer' in html_content:
        return html_content
    return (
        '%s<p class="text-muted mt-2 mb-0 o_chatboo_local_footer">%s</p>'
        % (html_content, html.escape(text))
    )


# ---------------------------------------------------------------------------
# painter-free (provider, /painter-free, or skill painter: painter-free)
#
# painter-local (OFF): Chatboo paints HTML tables + charts; LLM writes a short
# footer (or nothing if foot-laconic).
# painter-free (ON): the LLM owns the ENTIRE response UI — Markdown, HTML,
# Chatboo table/chart blocks, mix. Nothing is forbidden. The server does not
# auto-push a table into the bubble; it hands data + optional formatted_text
# so the model can embed native charts if it wants. footmode and showmode
# are suspended for that bubble.
#
# Isolation: painter-free branches MUST gate on the remote flag. When OFF,
# handoff/hints are never applied. Pure author_html without rows still
# delivers locally.
# ---------------------------------------------------------------------------

REMOTE_FORMAT_SYSTEM_HINT = (
    '[painter-free] You own the ENTIRE response UI for this turn. '
    'The server will NOT auto-push a Chatboo table or Gráfico toolbar. '
    'Markdown/HTML prose for narrative, greetings, captions and drawings — '
    'never a pipe table. footmode and showmode do not apply. '
    'A drawing the user asked for: emit the SVG markup; Chatboo files it as a '
    'session chip — leftover text stays prose. Do not wrap that text in a table. '
    'DATA PLOTS only when THIS turn has real rows/series: then you MAY embed '
    'data-chatboo-dataset or formatted_text table HTML. SINGLE-FACT CARD: '
    '{"card": {kind: "fact"|"link", …}} (data-chatboo-card). '
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


def strip_chatboo_chart_affordances(html_content):
    """Remove chart dataset/toolbar hooks so Chatboo cannot hydrate Gráfico UI.

    Opt-out helper for explicit ``show_mode=table`` / ``__no_charts__``.
    painter-free must NOT call this — the LLM may embed native charts.
    """
    if not html_content or not isinstance(html_content, str):
        return html_content
    out = html_content
    out = re.sub(r'\s*data-chatboo-dataset="[^"]*"', '', out)
    out = re.sub(r"\s*data-chatboo-dataset='[^']*'", '', out)
    out = re.sub(
        r'\s*data-chatboo-show-mode="[^"]*"',
        ' data-chatboo-show-mode="table"',
        out,
    )
    out = re.sub(
        r"\s*data-chatboo-show-mode='[^']*'",
        " data-chatboo-show-mode='table'",
        out,
    )
    # Mark blocks so the client never hydrates a Gráfico toolbar.
    out = re.sub(
        r'(<div[^>]*\bo_chatboo_table_block\b)([^>]*)(>)',
        lambda m: (
            m.group(1)
            + (
                '' if 'data-chatboo-no-charts=' in m.group(2)
                else ' data-chatboo-no-charts="1"'
            )
            + m.group(2)
            + m.group(3)
        ),
        out,
        flags=re.IGNORECASE,
    )
    # Drop any toolbar already embedded in the HTML string.
    out = re.sub(
        r'<div[^>]*\bo_chatboo_chart_toolbar\b[^>]*>[\s\S]*?</div>',
        '',
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r'<div[^>]*\bo_chatboo_chart_host\b[^>]*>[\s\S]*?</div>',
        '',
        out,
        flags=re.IGNORECASE,
    )
    return out


def is_server_side_table_payload(payload):
    """True when formatted_text came from the server table renderer."""
    if not isinstance(payload, dict) or not payload.get('formatted_text'):
        return False
    return payload.get('__fmt_type__') == 'server_side_python'


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


def remote_owns_tabular_presentation(remote_flag, payload):
    """True when painter-free owns presentation of this payload.

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


def tool_result_json_for_llm(result, remote_flag):
    """Serialize a tool result for the LLM; mark HTML as not-yet-shown if ON."""
    import json as _json
    if remote_flag:
        result = strip_server_html_for_remote(result)
    return _json.dumps(result, ensure_ascii=False, default=str)


def strip_server_html_for_remote(result):
    """Mark tool HTML as not-yet-shown; keep ``formatted_text`` for the LLM.

    painter-free: the model owns the bubble. It needs the rendered HTML
    (chart datasets included) so it can embed native tables/charts.
    Delivery flags (``__return_direct__`` …) are dropped so the engine
    does not auto-push. Pure author_html without rows is left intact.

    Callers MUST only invoke this when painter-free is active.
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

