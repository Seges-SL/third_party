# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Pure helpers: strip RelaxAICode / JSON-RPC noise from errors shown in Chatboo.

No Odoo imports — unit-testable without the runtime.
"""
from __future__ import annotations

import re

_DETAILS_JSON_RE = re.compile(r'\nDetails:\s*\{[\s\S]*\}\s*$')
_ERROR_CODE_RE = re.compile(r'^ERROR\s*\(-\d+\):\s*', re.IGNORECASE)
_EXEC_PREFIX_RE = re.compile(r'^Error executing code:\s*', re.IGNORECASE)
_JOIN_SEQUENCE_RE = re.compile(
    r'sequence item \d+: expected str instance, \w+ found',
    re.IGNORECASE,
)
_PERM_HINTS = (
    'accesserror',
    'permission',
    'permiso',
    'not allowed',
    'no tienes',
    'restricciones de seguridad',
    'due to security',
    'security restrictions',
)


def exception_user_text(exc):
    """Human sentence from UserError / RedirectWarning. Not ``str(exc)``.

    Odoo packs RedirectWarning as ``(message, action_id, button, extra)``.
    ``str(exc)`` is that tuple; a walkie would read the button and the id.
    """
    if exc is None:
        return ''
    args = getattr(exc, 'args', ()) or ()
    if args:
        first = args[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    name = getattr(exc, 'name', None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return (str(exc) or '').strip()


def strip_tool_error_wrappers(raw):
    """Remove JSON-RPC / RelaxAICode envelopes; keep the human sentence."""
    text = (raw or '').strip()
    if not text:
        return ''
    text = _DETAILS_JSON_RE.sub('', text).strip()
    text = _ERROR_CODE_RE.sub('', text).strip()
    text = _EXEC_PREFIX_RE.sub('', text).strip()
    return text


def format_int_id_hint(error_msg):
    """Retry hint when code reads .id on a value that is already the id."""
    text = (error_msg or '').strip()
    if not text or "'int' object has no attribute 'id'" not in text:
        return None
    return (
        "Error executing code: %s\n"
        "[HINT] That value is already the id (an int). Use it in the domain "
        "as ('field', '=', the_int). Do not read .id on it."
    ) % text


def format_join_sequence_hint(error_msg):
    """Retry hint when ``str.join`` receives row dicts instead of strings."""
    text = (error_msg or '').strip()
    if not text or not _JOIN_SEQUENCE_RE.search(text):
        return None
    return (
        'Error executing code: %s\n'
        '[HINT] str.join needs strings. Rows in previous_result or raw_data '
        'are dicts. Do not join those rows. Return {\'data\': rows}.'
    ) % text


def is_permission_denied_message(raw):
    """True when the tool/error text is clearly an ACL / AccessError denial."""
    blob = (raw or '').lower()
    return any(hint in blob for hint in _PERM_HINTS)


_CATALOGUE_REJECT_MARKERS = (
    'CONTEXT_CATALOGUE',
    'API_CATALOGUE',
    'SKILL_CATALOGUE',
    'cannot inspect ai.context',
    'cannot inspect ai.api.server',
    'cannot inspect ai.skill',
)

_DEFAULT_RETRY_NUDGE = (
    "STOP: that was only a progress note. The previous "
    "tool call FAILED and nothing useful was shown to "
    "the user. You MUST call the tool again NOW with "
    "corrected arguments/code. Do not send text without "
    "a tool call until the tool succeeds."
)

_CATALOGUE_RETRY_NUDGE = (
    "STOP: relaxaicode cannot inspect the knowledge/API catalogue. "
    "Do NOT call relaxaicode again. Call get_context("
    "context_name='contexts_index_core') now, then get_context("
    "context_name='<code>') for one pack. Do not dump pack XML; "
    "answer from what is already injected, in prose. "
    "Creating discovery rows "
    "is safe_plan_request, not a sandbox search."
)

_SKILL_CATALOGUE_RETRY_NUDGE = (
    "STOP: relaxaicode cannot inspect ai.skill. "
    "Do NOT call relaxaicode again. A skill runs when the user types "
    "/command, or when the engine matches the sentence to that skill's "
    "own trigger phrases; the model does not launch it. "
    "On the MCP endpoint you do not "
    "run slash skills — answer in prose that you serve tools and "
    "knowledge packs. Do not dump procedure or code_body."
)


def is_catalogue_inspect_reject(raw):
    """True when RelaxAICode was rejected for inspecting a catalogue model."""
    blob = raw or ''
    return any(marker in blob for marker in _CATALOGUE_REJECT_MARKERS)


_GROUPBY_STORED_HINT = (
    "STOP: groupby failed because a field is computed (not stored). "
    "Call the tool again. groupby only database-persisted fields "
    "(store=True). Do not group by a computed or related-without-store "
    "field. Use search() and aggregate in Python when the figure has "
    "no stored column."
)


def is_groupby_computed_field_error(raw):
    """True for the ORM refusal to group by a non-stored field.

    The sentence is Odoo's, always English. It is a code mistake, not
    an answer for the user.
    """
    blob = (raw or '').lower()
    if 'groupby' not in blob:
        return False
    return (
        'computed' in blob
        or 'database-persisted' in blob
        or 'not stored' in blob
        or 'non-stored' in blob
        or 'no stored column' in blob
    )


def groupby_stored_field_retry_hint():
    """LLM-facing correction. Not shown in the chat bubble."""
    return _GROUPBY_STORED_HINT


def retry_nudge_after_tool_error(raw):
    """LLM-facing user message after a retryable tool failure (English)."""
    blob = raw or ''
    if is_groupby_computed_field_error(blob):
        return _GROUPBY_STORED_HINT
    if 'SKILL_CATALOGUE' in blob or 'cannot inspect ai.skill' in blob:
        return _SKILL_CATALOGUE_RETRY_NUDGE
    if is_catalogue_inspect_reject(raw):
        return _CATALOGUE_RETRY_NUDGE
    return _DEFAULT_RETRY_NUDGE


def humanize_exhausted_tool_error(raw):
    """Sanitize last RelaxAICode retry error for Chatboo.

    Returns ``(message, is_permission)``. ``message`` is None when nothing
    useful remains after stripping technical wrappers.
    """
    if is_groupby_computed_field_error(raw):
        return None, False
    cleaned = strip_tool_error_wrappers(raw)
    if not cleaned:
        return None, is_permission_denied_message(raw or '')
    return cleaned, is_permission_denied_message(raw or cleaned)
