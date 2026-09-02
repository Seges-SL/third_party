# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Correlation ID and step sequence for MCP log threading."""

import random
import string

_CORR_CHARS = string.ascii_uppercase + string.digits


def new_correlation_id():
    return ''.join(random.choices(_CORR_CHARS, k=4))


def start_new_turn(req):
    """Start a new conversation turn (Chatboo stream, etc.)."""
    req.mcp_corr_id = new_correlation_id()
    req.mcp_step_counter = {}
    return req.mcp_corr_id


def ensure_turn_correlation(req):
    if not getattr(req, 'mcp_corr_id', None):
        req.mcp_corr_id = new_correlation_id()
    if not getattr(req, 'mcp_step_counter', None):
        req.mcp_step_counter = {}
    return req.mcp_corr_id


def next_step_seq(req, corr_id=None):
    cid = corr_id or ensure_turn_correlation(req)
    counter = req.mcp_step_counter
    counter[cid] = counter.get(cid, 0) + 1
    return counter[cid]


def bind_session_correlation(req, session):
    """Reuse correlation id from an MCP SSE / Streamable HTTP session."""
    if not session:
        return ensure_turn_correlation(req)
    req.mcp_corr_id = session.correlation_id
    if not getattr(req, 'mcp_step_counter', None):
        req.mcp_step_counter = {}
    counter = req.mcp_step_counter
    counter[session.correlation_id] = session.step_seq
    return session.correlation_id


def next_step_for_session(req, session):
    cid = bind_session_correlation(req, session)
    if session is not None:
        session.step_seq += 1
        req.mcp_step_counter[cid] = session.step_seq
        return session.step_seq
    return next_step_seq(req, cid)
