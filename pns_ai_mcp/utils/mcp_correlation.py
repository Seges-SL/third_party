# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Turn id and step counter for MCP log threading."""

import random
import string
import threading
from collections import OrderedDict

_TURN_CHARS = string.ascii_uppercase + string.digits
_TURN_BODY = 4
_TURN_MAX = 8

# Last step written per turn, in this process. The engine and the work it
# starts (a tool, a side model call in a job thread) share no HTTP request,
# so they count here to keep one order on the turn.
_TURN_STEPS = OrderedDict()
_TURN_STEPS_LOCK = threading.Lock()
_TURN_STEPS_KEEP = 2000


def open_turn_steps(turn_id):
    """A turn starts: its steps count from 1 again."""
    if not turn_id:
        return
    with _TURN_STEPS_LOCK:
        _TURN_STEPS[turn_id] = 0
        _TURN_STEPS.move_to_end(turn_id)
        while len(_TURN_STEPS) > _TURN_STEPS_KEEP:
            _TURN_STEPS.popitem(last=False)


def claim_turn_step(turn_id, seed=None):
    """Next step of ``turn_id``.

    ``seed()`` returns the last step already stored, for a turn this
    process has not counted yet.
    """
    if not turn_id:
        return None
    with _TURN_STEPS_LOCK:
        known = turn_id in _TURN_STEPS
    start = 0
    if not known and seed is not None:
        try:
            start = int(seed() or 0)
        except Exception:
            start = 0
    with _TURN_STEPS_LOCK:
        step = _TURN_STEPS.get(turn_id, start) + 1
        _TURN_STEPS[turn_id] = step
        _TURN_STEPS.move_to_end(turn_id)
        while len(_TURN_STEPS) > _TURN_STEPS_KEEP:
            _TURN_STEPS.popitem(last=False)
    return step


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
