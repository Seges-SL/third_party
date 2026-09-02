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


def strip_tool_error_wrappers(raw):
    """Remove JSON-RPC / RelaxAICode envelopes; keep the human sentence."""
    text = (raw or '').strip()
    if not text:
        return ''
    text = _DETAILS_JSON_RE.sub('', text).strip()
    text = _ERROR_CODE_RE.sub('', text).strip()
    text = _EXEC_PREFIX_RE.sub('', text).strip()
    return text


def is_permission_denied_message(raw):
    """True when the tool/error text is clearly an ACL / AccessError denial."""
    blob = (raw or '').lower()
    return any(hint in blob for hint in _PERM_HINTS)


_CATALOGUE_REJECT_MARKERS = (
    'CONTEXT_CATALOGUE',
    'API_CATALOGUE',
    'cannot inspect ai.context',
    'cannot inspect ai.api.server',
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
    "is propose_safe_operations, not a sandbox search."
)


def is_catalogue_inspect_reject(raw):
    """True when RelaxAICode was rejected for inspecting a catalogue model."""
    blob = raw or ''
    return any(marker in blob for marker in _CATALOGUE_REJECT_MARKERS)


def retry_nudge_after_tool_error(raw):
    """LLM-facing user message after a retryable tool failure (English)."""
    if is_catalogue_inspect_reject(raw):
        return _CATALOGUE_RETRY_NUDGE
    return _DEFAULT_RETRY_NUDGE


def humanize_exhausted_tool_error(raw):
    """Sanitize last RelaxAICode retry error for Chatboo.

    Returns ``(message, is_permission)``. ``message`` is None when nothing
    useful remains after stripping technical wrappers.
    """
    cleaned = strip_tool_error_wrappers(raw)
    if not cleaned:
        return None, is_permission_denied_message(raw or '')
    return cleaned, is_permission_denied_message(raw or cleaned)
