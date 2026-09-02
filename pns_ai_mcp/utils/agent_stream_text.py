# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Pure helpers for LLM stream text (no Odoo imports — unit-testable).

Anti-noise policy (structural, no phrase lists):
- Final answer (no tool_calls) → may go to the chat bubble.
- Same round as tool_calls → never into the chat bubble (keeps history for the LLM).
  Short one-line progress may surface as a transient ``status`` event.
  Longer / dump-shaped text is withheld from the UI entirely.
"""

from __future__ import annotations

import re

_THINK_BLOCK_RE = re.compile(r'<think>.*?</think>', re.DOTALL | re.IGNORECASE)

# Upper bound for a human progress line on the status bar (not the chat body).
_STATUS_MAX_CHARS = 160


def strip_think_blocks(text):
    """Remove inline <think>...</think> spans from a final answer (safety net).

    Models that don't separate reasoning into ``reasoning_content`` may inline it
    as ``<think>...</think>`` inside ``content``. This keeps the visible answer
    clean. Streaming display is handled by only emitting ``content`` tokens.
    """
    if not text or '<think>' not in text.lower():
        return text
    return _THINK_BLOCK_RE.sub('', text).strip()


def _looks_like_data_dump(text):
    """True when text is shaped like temporary/raw payload, not a progress line."""
    s = (text or '').strip()
    if not s:
        return True
    if len(s) > _STATUS_MAX_CHARS:
        return True
    if s.count('\n') >= 2:
        return True
    if s.startswith(('{', '[', '<')):
        return True
    if '```' in s:
        return True
    if '|---' in s or '| ---' in s:
        return True
    if s.count('{') + s.count('[') >= 2:
        return True
    # Una barra de progreso es una sola frase; varias oraciones = rumiar detalle.
    if sum(s.count(c) for c in '.!?。') >= 2:
        return True
    return False


def pretool_progress_status(content):
    """Transient status label for a tool round, or None if not status-shaped.

    Structural gate only (length / shape). No keyword or language lists.
    """
    s = strip_think_blocks(content or '').strip()
    if not s or _looks_like_data_dump(s):
        return None
    one = ' '.join(s.split())
    if not one or len(one) > _STATUS_MAX_CHARS:
        return None
    return one


def user_visible_round_text(content, has_tool_calls):
    """Text from one ReAct round that may be appended to the chat bubble.

    Tool rounds never write into the bubble (progress goes via status if short).
    Final answers pass through as-is.
    """
    if has_tool_calls:
        return ''
    return content or ''


def should_block_progress_as_final(
    content, *, has_tool_calls, has_pending_retry, rounds_left,
):
    """True when progress chatter must not end the turn after a tool failure.

    Invariant: after a retryable tool error, a short progress-shaped line
    without tool_calls is not a user answer (e.g. «Corrijo… y vuelvo a
    generar el mapa» with no second relaxaicode call).
    """
    if has_tool_calls or not has_pending_retry or not rounds_left:
        return False
    return pretool_progress_status(content) is not None


# First-round essays without a tool are not greetings; bounce them (NTU0).
# Align with the protocol "under 150 words" so a scope/limits list can close
# without collapsing to the greeting one-liner. Longer stall essays still bounce.
_FINISHED_PROSE_MAX_CHARS = 1200

NO_TOOL_FINAL_NUDGE = (
    "STOP: if the user asked for Odoo data or an action, call a tool NOW "
    "(propose_safe_operations for supervised writes including op=action, or "
    "relaxaicode for reads). Do not repeat a previous assistant reply and "
    "do not re-introduce yourself. If this turn is only a greeting, "
    "who-you-are, or scope/limits (no data/action), write a FRESH prose "
    "reply for THIS question — do not collapse it to the greeting "
    "one-liner, do not refuse, and do not add a policy line."
)

# International file-type tokens (not locale words). Same family as export.
_WORK_FILE_RE = re.compile(
    r'(?i)(?<![a-z0-9])(?:pdf|xlsx|xls|csv|docx|doc)(?![a-z0-9])',
)
_WORD_RE = re.compile(r'[^\W_]+', re.UNICODE)
_MD_MARK_RE = re.compile(r'[*_`#]+')


def user_turn_looks_like_work(user_message):
    """True when the utterance is shaped like data/action, not a greeting.

    Structural only: digits, file-type tokens, slash commands, or a
    multi-token statement with no ``?``. No language word list.
    """
    raw = (user_message or '').strip()
    if not raw:
        return False
    if re.search(r'\d', raw):
        return True
    if _WORK_FILE_RE.search(raw):
        return True
    if raw.lstrip().startswith('/') or re.search(r'\s/\w', raw):
        return True
    tokens = _WORD_RE.findall(raw)
    if len(tokens) >= 3 and '?' not in raw and '？' not in raw:
        return True
    return False


def _normalize_prose(text):
    s = strip_think_blocks(text or '')
    s = _MD_MARK_RE.sub(' ', s)
    return ' '.join(s.lower().split())


def is_prior_prose_echo(content, prior_texts, *, min_chars=40):
    """True when *content* repeats a previous assistant bubble (shape only)."""
    text = _normalize_prose(content)
    if len(text) < min_chars:
        return False
    now_tokens = set(_WORD_RE.findall(text))
    if not now_tokens:
        return False
    for prev in prior_texts or ():
        old = _normalize_prose(prev)
        if len(old) < min_chars:
            continue
        if text == old or text in old or old in text:
            return True
        old_tokens = set(_WORD_RE.findall(old))
        if not old_tokens:
            continue
        overlap = len(now_tokens & old_tokens)
        denom = float(min(len(now_tokens), len(old_tokens)))
        if denom and (overlap / denom) >= 0.85:
            return True
    return False


def announced_tool_names(content, tool_names):
    """True when prose cites a schema tool name but issued no tool_calls."""
    s = (content or '').lower()
    if not s:
        return False
    for name in tool_names or ():
        token = (name or '').strip().lower()
        if token and token in s:
            return True
    return False


def should_block_no_tool_as_final(
    *, has_tool_calls, is_first_round, rounds_left, has_tools,
    content='', tool_names=(), user_message='', prior_assistant=(),
):
    """True when round 1 with tools in the payload has zero tool_calls.

    Invariant: the first LLM round of a data/action turn is not a user
    answer until a tool runs (or no rounds remain). No language lexicon —
    CRUD and op=action share the same horn.

    Shape exception (language-agnostic): on a non-work utterance, finished
    prose that does not name a tool is a greeting, who-are-you, or
    scope/limits answer and may close (up to ``_FINISHED_PROSE_MAX_CHARS``).
    Work-shaped utterances, prior-bubble echoes, progress one-liners,
    tool-name mentions, and long stall essays still bounce.
    """
    if (
        not has_tools
        or has_tool_calls
        or not is_first_round
        or not rounds_left
    ):
        return False
    text = strip_think_blocks(content or '').strip()
    if announced_tool_names(text, tool_names):
        return True
    if pretool_progress_status(text):
        return True
    if is_prior_prose_echo(text, prior_assistant):
        return True
    if user_turn_looks_like_work(user_message):
        return True
    if text and len(text) <= _FINISHED_PROSE_MAX_CHARS:
        return False
    return True
