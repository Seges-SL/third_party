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
    has_hidden_reasoning=False,
):
    """True when progress chatter must not end the turn.

    After a retryable tool error, or when the model hid a reasoning
    channel (OpenRouter ``reasoning`` / ``<think>``) and only a short
    progress line landed in ``content``, that line is not the answer.
    """
    if has_tool_calls or not rounds_left:
        return False
    if not has_pending_retry and not has_hidden_reasoning:
        return False
    return pretool_progress_status(content) is not None


# First-round essays without a tool are not greetings; bounce them (NTU0).
# Align with the protocol "under 150 words" so a scope/limits list can close
# without collapsing to the greeting one-liner. Longer stall essays still bounce.
_FINISHED_PROSE_MAX_CHARS = 1200

PROGRESS_FILLER_NUDGE = (
    "STOP: that line is not the answer the user should read. "
    "Write the reply now. Do not describe that you are still composing. "
    "If this turn is a greeting, who-you-are, or scope/limits, answer in "
    "prose. If it needs data or an action, call a tool."
)

NO_TOOL_FINAL_NUDGE = (
    "STOP: the user may have agreed to what YOU just offered, not started "
    "a new request. If that offer was Odoo data or an action, or if this "
    "message asks for data/action, call a tool NOW "
    "(safe_plan_request for supervised writes including op=action, or "
    "relaxaicode for reads). Do not parse a short assent as a query. "
    "Do not repeat a previous assistant reply and do not re-introduce "
    "yourself. If this turn is only a greeting, who-you-are, scope/limits, "
    "or they answered a conversational question you asked (no data/action "
    "offered), write a FRESH prose reply for THIS question — do not "
    "collapse it to the greeting one-liner, do not refuse, and do not "
    "add a policy line."
)

# International file-type tokens (not locale words). Same family as export.
_WORK_FILE_RE = re.compile(
    r'(?i)(?<![a-z0-9])(?:pdf|xlsx|xls|csv|docx|doc)(?![a-z0-9])',
)
_WORD_RE = re.compile(r'[^\W_]+', re.UNICODE)
_MD_MARK_RE = re.compile(r'[*_`#]+')

# Question-mark glyphs (not locale words). Same family as file-type tokens.
# ASCII, inverted, fullwidth, Arabic. Not ';' (shares the glyph with semicolon).
_QUESTION_MARK_GLYPHS = frozenset('?¿？؟')


def _has_question_mark_glyph(text):
    return bool(text) and not _QUESTION_MARK_GLYPHS.isdisjoint(text)


def _last_assistant_text(prior_assistant):
    if not prior_assistant:
        return ''
    if isinstance(prior_assistant, str):
        return strip_think_blocks(prior_assistant).strip()
    for item in reversed(list(prior_assistant)):
        if isinstance(item, dict):
            text = item.get('content') or ''
        else:
            text = item or ''
        text = strip_think_blocks(text).strip()
        if text:
            return text
    return ''


def user_turn_looks_like_work(user_message, prior_assistant=None):
    """True when the utterance is shaped like data/action, not a greeting.

    Structural only: digits, file-type tokens, slash commands, or a
    multi-token statement with no question-mark glyph. No language word list.

    Exception: a statement that answers the last assistant bubble (that
    bubble has a question-mark glyph) is not work-shaped unless it also
    has a hard marker. The words are assent, not a new query. If the
    offer was instance data or an action, the model still calls a tool
    because of the offer — the gate must not treat the assent as the
    request text.
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
    if len(tokens) >= 3 and not _has_question_mark_glyph(raw):
        if _has_question_mark_glyph(_last_assistant_text(prior_assistant)):
            return False
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


def prior_turn_has_delivered_body(prior_assistant):
    """True when the last assistant bubble already delivered a body.

    Structural only: a markdown table, or prose longer than a greeting /
    scope list. A follow-up can then close without a tool (the read
    already happened). A who-are-you bubble does not qualify.
    """
    last = _last_assistant_text(prior_assistant)
    if not last:
        return False
    if '|---' in last or '| ---' in last:
        return True
    return len(last) > _FINISHED_PROSE_MAX_CHARS


_DISPLACED_THIN_CHARS = 280


def recover_displaced_turn_body(messages, current, *, thin_limit=_DISPLACED_THIN_CHARS):
    """Reuse this turn's earlier assistant body when a thin closer replaced it.

    Same job as ``recover_turn_report_body``, without a report outline:
    a bounced first-round table must not lose to «tell me the next step».
    """
    current = strip_think_blocks(current or '').strip()
    if current and len(current) > thin_limit:
        return current
    best = ''
    for msg in messages or []:
        if not isinstance(msg, dict) or msg.get('role') != 'assistant':
            continue
        text = strip_think_blocks(msg.get('content') or '').strip()
        if not text or text == current:
            continue
        if pretool_progress_status(text) is not None:
            continue
        if len(text) > len(best):
            best = text
    if not best or len(best) <= len(current):
        return current
    if current and current not in best:
        return best.rstrip() + '\n\n' + current
    return best


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
    inline_file_text=False,
):
    """True when round 1 with tools in the payload has zero tool_calls.

    Invariant: the first LLM round of a data/action turn is not a user
    answer until a tool runs (or no rounds remain). No language lexicon —
    CRUD and op=action share the same horn.

    Shape exception (language-agnostic): on a non-work utterance, finished
    prose that does not name a tool is a greeting, who-are-you,
    scope/limits, or an answer to the last assistant question and may
    close (up to ``_FINISHED_PROSE_MAX_CHARS``).
    Work-shaped utterances, prior-bubble echoes, tool-name mentions,
    and long stall essays still bounce. A one-line reply on a non-work
    turn (assent to the last question) may close; the same one-liner
    on a work turn still bounces because the turn is work-shaped.

    File text already in the prompt, or a prior bubble that already
    delivered a body, is the read: a long no-tool reply is that answer
    (not a missing ORM call). Progress one-liners and tool-name teases
    still bounce.
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
    if is_prior_prose_echo(text, prior_assistant):
        return True
    already_read = inline_file_text or prior_turn_has_delivered_body(
        prior_assistant,
    )
    if already_read and text:
        if pretool_progress_status(text) is not None:
            return True
        # Greeting one-liners stay under the status-bar bound; a file
        # or follow-up answer is longer and is already the read.
        if len(text) > _STATUS_MAX_CHARS:
            return False
    if user_turn_looks_like_work(
        user_message, prior_assistant=prior_assistant,
    ):
        return True
    if text and len(text) <= _FINISHED_PROSE_MAX_CHARS:
        return False
    return True
