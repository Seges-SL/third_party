# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Turn id and step counter for MCP log threading."""

import random
import string

_TURN_CHARS = string.ascii_uppercase + string.digits
_TURN_BODY = 4
_TURN_MAX = 8


def _clean_prefix(prefix):
    raw = ''.join(
        ch for ch in str(prefix or '').upper() if ch.isalnum()
    )
    return raw[:_TURN_MAX - _TURN_BODY]


def new_turn_id(prefix=''):
    """One algorithm for every host.

    Chatboo / MCP keep the historic 4-char chip (no prefix). Other hosts
    pass a short prefix so a walkie turn cannot group with a Chatboo chip.
    Stored ``ai.log.turn`` is at most 8 chars.
    """
    head = _clean_prefix(prefix)
    body = ''.join(random.choices(_TURN_CHARS, k=_TURN_BODY))
    return (head + body)[:_TURN_MAX]


def start_new_turn(req, prefix=''):
    """Start a new conversation turn. Hosts that are not Chatboo pass prefix."""
    req.mcp_turn = new_turn_id(prefix=prefix)
    req.mcp_turn_step_counter = {}
    return req.mcp_turn


def ensure_turn(req):
    if not getattr(req, 'mcp_turn', None):
        prefix = getattr(req, 'mcp_turn_prefix', None) or ''
        try:
            req.mcp_turn = new_turn_id(prefix=prefix)
        except TypeError:
            req.mcp_turn = new_turn_id()
    if not getattr(req, 'mcp_turn_step_counter', None):
        req.mcp_turn_step_counter = {}
    return req.mcp_turn


def next_turn_step(req, turn_id=None):
    tid = turn_id or ensure_turn(req)
    counter = req.mcp_turn_step_counter
    counter[tid] = counter.get(tid, 0) + 1
    return counter[tid]


def bind_session_turn(req, session):
    """Reuse turn id from an MCP SSE / Streamable HTTP session."""
    if not session:
        return ensure_turn(req)
    req.mcp_turn = session.turn
    if not getattr(req, 'mcp_turn_step_counter', None):
        req.mcp_turn_step_counter = {}
    counter = req.mcp_turn_step_counter
    counter[session.turn] = session.turn_step
    return session.turn


def next_turn_step_for_session(req, session):
    tid = bind_session_turn(req, session)
    if session is not None:
        session.turn_step += 1
        req.mcp_turn_step_counter[tid] = session.turn_step
        return session.turn_step
    return next_turn_step(req, tid)
