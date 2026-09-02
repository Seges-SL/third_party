# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Policy for when server-rendered tool output reaches the Chatboo bubble."""

TRUSTED_CHAT_FMT_TYPES = frozenset({
    'server_side_python', 'author_html', 'local_json', 'local_raw',
})


def payload_marked_user_facing(payload):
    """True when the tool payload explicitly opts into the chat bubble."""
    if not isinstance(payload, dict):
        return False
    return bool(
        payload.get('__direct_return__')
        or payload.get('__return_direct__')
        or payload.get('__return_direct_to_user__')
    )


def should_show_direct_to_chat(
    payload, *, round_n, max_rounds, tool_name, force_retry=False,
    has_primary=False, user_message=None, user_lang=None,
):
    """Gate server-rendered HTML: probes stay in tool JSON; finals may show.

    ``has_primary``: a complete artifact is already pinned this turn. The
    last-round fallback must not then dump a probe over that document.

    Delivery shape is the model's ``return_mode`` / ``__return_direct__``
    (same idea as skill painter). ``user_message`` / ``user_lang`` kept for
    call-site compatibility; no lexical classifier.
    """
    del user_message, user_lang
    if not isinstance(payload, dict) or force_retry:
        return False
    if payload_marked_user_facing(payload):
        return True
    if tool_name != 'relaxaicode':
        return False
    if not payload.get('formatted_text'):
        return False
    if payload.get('__fmt_type__') not in TRUSTED_CHAT_FMT_TYPES:
        return False
    # Fase 2 / presentación terminada: mostrar aunque no sea la última ronda
    # del orquestador (3.1.5 ocultaba probes mid-turn pero también estos finals).
    if (
        payload.get('__presentation_complete__')
        or payload.get('__phase__') == 'presentation'
        or payload.get('__satisfied__')
    ):
        return True
    # Extracción final con tabla server-side + summary en result (p. ej. ranking
    # Sesame): el LLM devuelve {data, summary} sin phase=presentation; maybe_attach
    # ya generó formatted_text pero el gating lo ocultaba mid-turn. Los probes
    # no suelen incluir summary en el dict result — siguen ocultos.
    if (
        payload.get('__extraction_complete__')
        and payload.get('__ready_for_presentation__')
        and payload.get('summary')
    ):
        return True
    if round_n >= max_rounds and not has_primary:
        return True
    return False
