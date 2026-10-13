# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Report-mode outline guard: detect missing headings and complete the closing.

Generic — skills declare ``report_outline`` / ``closing_required`` /
``recommendations_stub``; this module never hardcodes domain labels beyond
matching the headings the skill already provided.
"""
from __future__ import annotations

_NEUTRAL_RECO_STUB = 'Revisar las tablas anteriores.'


def _heading_label(heading):
    return (heading or '').lstrip('#').strip().lower()


def heading_present(text, heading):
    """True if ``text`` already has a Markdown heading matching ``heading``."""
    want = _heading_label(heading)
    if not want:
        return True
    for line in (text or '').splitlines():
        s = line.strip()
        if not s.startswith('#'):
            continue
        if _heading_label(s) == want:
            return True
    return False


def missing_outline_headings(text, outline):
    """Return outline headings (same strings) not yet present in ``text``."""
    if not isinstance(outline, (list, tuple)):
        return []
    return [h for h in outline if h and not heading_present(text, h)]


def closing_present(text, closing):
    """True if the fixed closing prefix (before ':') appears in ``text``."""
    if not closing or not isinstance(closing, str):
        return True
    prefix = closing.strip().split(':')[0].strip().lower()
    if not prefix:
        return True
    return prefix in (text or '').lower()


def report_body_started(text, outline=None):
    """True when ``text`` already opened the report (H1 or an outline heading)."""
    body = (text or '').lstrip()
    if body.startswith('#'):
        return True
    return any(heading_present(text, h) for h in (outline or []) if h)


def is_report_closer(text, outline=None):
    """True when the text never opened the report (warm footer / aside).

    After tools the model is told to write 1–2 warm sentences. That must
    not be treated as a truncated report (which used to spawn
    ``Pendiente de narrativa`` stubs and wipe the real prose).
    """
    body = (text or '').strip()
    if not body:
        return True
    return not report_body_started(body, outline)


def recover_turn_report_body(messages, current, outline=None):
    """Reuse this turn's earlier assistant narrative when the closer replaced it.

    ``messages`` may already include ``current`` as the last assistant turn.
    """
    current = (current or '').strip()
    if current and not is_report_closer(current, outline):
        return current
    best = ''
    for msg in messages or []:
        if not isinstance(msg, dict) or msg.get('role') != 'assistant':
            continue
        text = msg.get('content') or ''
        if not isinstance(text, str):
            continue
        text = text.strip()
        if not text or text == current:
            continue
        if is_report_closer(text, outline):
            continue
        if not report_body_started(text, outline):
            continue
        if len(text) > len(best):
            best = text
    if not best:
        return current
    if current and current not in best:
        return best.rstrip() + '\n\n' + current
    return best


def stub_section_heading(outline, recommendations_heading=None):
    """Heading that receives ``recommendations_stub`` (contract, not lexicon).

    Prefer the skill-supplied heading; otherwise the last outline heading.
    """
    if recommendations_heading and str(recommendations_heading).strip():
        return str(recommendations_heading).strip()
    if isinstance(outline, (list, tuple)):
        for heading in reversed(outline):
            if heading and str(heading).strip():
                return str(heading).strip()
    return None


def ensure_report_completion(
    text,
    outline=None,
    closing=None,
    recommendations_stub=None,
    recommendations_heading=None,
):
    """Append any missing outline headings + closing so the report cannot end early.

    Returns ``(new_text, changed)``. Does nothing when ``text`` is only a
    closer (no report has started) — fabricating headings would hide the
    real narrative from an earlier round.

    The section that receives ``recommendations_stub`` is identified by
    contract (``recommendations_heading`` or the last outline heading),
    never by locale words.
    """
    body = (text or '').rstrip()
    missing = missing_outline_headings(body, outline)
    need_closing = not closing_present(body, closing)
    if not missing and not need_closing:
        return body, False
    if not report_body_started(body, outline):
        return body, False

    chunks = [body, ''] if body else ['']
    stub = [
        str(b).strip() for b in (recommendations_stub or [])
        if b is not None and str(b).strip()
    ]
    stub_heading = stub_section_heading(outline, recommendations_heading)
    stub_label = _heading_label(stub_heading) if stub_heading else ''
    for heading in missing:
        chunks.append(heading)
        chunks.append('')
        if stub_label and _heading_label(heading) == stub_label:
            if stub:
                for b in stub:
                    chunks.append('- %s' % b)
            else:
                chunks.append('- %s' % _NEUTRAL_RECO_STUB)
            if closing and isinstance(closing, str) and closing.strip():
                chunks.append(closing.strip())
                need_closing = False
        else:
            chunks.append(
                '_Pendiente de narrativa; cifras en las tablas anteriores._'
            )
        chunks.append('')

    if need_closing and closing and isinstance(closing, str) and closing.strip():
        chunks.append(closing.strip())
        chunks.append('')

    return '\n'.join(chunks).rstrip() + '\n', True


def contract_from_payload(payload):
    """Narrative contract from a free-text tool result, or None.

    Same keys the slash report handoff stores. A listing without
    ``report_outline`` stays a listing.
    """
    if not isinstance(payload, dict):
        return None
    outline = payload.get('report_outline')
    if not isinstance(outline, (list, tuple)):
        return None
    headings = [h.strip() for h in outline if isinstance(h, str) and h.strip()]
    if not headings:
        return None
    closing = payload.get('closing_required')
    stub = payload.get('recommendations_stub')
    heading = payload.get('recommendations_heading')
    return {
        'report_outline': headings,
        'closing_required': closing if isinstance(closing, str) else None,
        'recommendations_stub': stub if isinstance(stub, (list, tuple)) else None,
        'recommendations_heading': heading if isinstance(heading, str) else None,
    }


_LISTING_FOLLOWUP = (
    'El documento principal YA está en pantalla '
    '(%s fila(s) renderizadas). Las tools siguientes '
    'solo pueden MEJORARLO (previous_result / raw_data) '
    'o añadir un documento menor. PROHIBIDO emitir un '
    'volcado autónomo que lo sustituya u oculte. Si ese '
    'número es 0 o MUY inferior a lo pedido (p. ej. te '
    'pidieron "los 50" y hay 0/unas pocas), NO afirmes '
    'que estan todos: tu filtro es casi seguro erróneo '
    '(ojo REGIÓN vs PROVINCIA). Corrige el código y '
    'VUELVE A LLAMAR a la herramienta. Si las filas '
    'coinciden con lo pedido, escribe 1–2 frases de '
    'cierre CÁLIDAS y NO reproduzcas la tabla. PROHIBIDO '
    'en ese cierre: cifras, importes, fechas, años, '
    'periodos, nombres propios, totales o "insights" '
    'numéricos — el artefacto visible es la fuente de '
    'verdad; el pie solo puede ser acogida u oferta de '
    'ayuda ("si quieres otro periodo…"), SIN nombrar el '
    'año ni el periodo.'
)

_REPORT_FOLLOWUP = (
    'The tables are already on screen (%s row(s)). '
    'report_outline is set. Write the prose NOW, with these '
    'headings in this order:\n%s\n'
    'Cite only figures already in those tables. Do not invent '
    'figures. Do not paste the table again. Do not call the '
    'tool again if the rows cover the request.'
)


def followup_note_after_tables(row_label, report_contract=None):
    """Second-round note after the server painted the tables.

    A payload with ``report_outline`` may cite those figures. A listing
    keeps the short close with no figures.
    """
    outline = None
    if isinstance(report_contract, dict):
        outline = report_contract.get('report_outline')
    headings = []
    if isinstance(outline, (list, tuple)):
        headings = [h.strip() for h in outline if isinstance(h, str) and h.strip()]
    label = row_label if row_label is not None else '?'
    if headings:
        titles = '\n'.join('- %s' % h for h in headings)
        return _REPORT_FOLLOWUP % (label, titles)
    return _LISTING_FOLLOWUP % label
