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


def _has_summary(payload):
    summary = payload.get('summary') if isinstance(payload, dict) else None
    return isinstance(summary, str) and bool(summary.strip())


def is_chat_deliverable(payload):
    """True when the model marked this payload as the user-facing answer."""
    if not isinstance(payload, dict):
        return False
    if payload_marked_user_facing(payload):
        return True
    if (
        payload.get('__presentation_complete__')
        or payload.get('__phase__') == 'presentation'
        or payload.get('__satisfied__')
    ):
        return True
    if (
        payload.get('__extraction_complete__')
        and payload.get('__ready_for_presentation__')
        and _has_summary(payload)
    ):
        return True
    return False


def is_unmarked_multi_probe(payload):
    """Two sibling row lists that were not marked as the answer.

    A lookup that still mixes a catalogue and the records it found
    (stages plus leads, fields plus rows) is not the deliverable.
    A titled table, a presentation, or an explicit direct flag still is.
    """
    if not isinstance(payload, dict) or is_chat_deliverable(payload):
        return False
    from .relaxaicode_render import _sibling_tabular_lists
    return len(_sibling_tabular_lists(payload)) >= 2


CLOSING_AFTER_PROBE = (
    'Tool rounds are finished. The last lookup was NOT shown to the user. '
    'Reply in the user\'s language, in a few sentences, and do not call tools. '
    'You did not create or change any record unless safe_plan_request in this '
    'turn returned executed. Do not paste catalogues, stages, field lists, or '
    'technical columns. If the lookup shows a record that already matches what '
    'the user asked to create, name that record and say it already exists, and '
    'ask whether to open it or propose a new one. Otherwise say you have not '
    'done it yet.'
)


def should_show_direct_to_chat(
    payload, *, round_n, max_rounds, tool_name, force_retry=False,
    has_primary=False, user_message=None, user_lang=None,
):
    """Gate server-rendered HTML: probes stay in tool JSON; finals may show.

    ``has_primary``: a complete artifact is already pinned this turn. The
    last-round fallback must not then dump a probe over that document.

    Delivery shape is the model's ``return_mode`` / ``__return_direct__``
    (same idea as skill compose). ``user_message`` / ``user_lang`` kept for
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
    # Extracción final con tabla server-side + summary en result (p. ej. ranking):
    # el LLM devuelve {data, summary} sin phase=presentation; maybe_attach
    # ya generó formatted_text pero el gating lo ocultaba mid-turn. Los probes
    # no suelen incluir summary en el dict result — siguen ocultos.
    if (
        payload.get('__extraction_complete__')
        and payload.get('__ready_for_presentation__')
        and payload.get('summary')
    ):
        return True
    if round_n >= max_rounds and not has_primary:
        # A mash-up of sibling lists (catalogue + records) is still a probe
        # when the rounds run out. Do not paint it as the answer.
        if is_unmarked_multi_probe(payload):
            return False
        return True
    return False
