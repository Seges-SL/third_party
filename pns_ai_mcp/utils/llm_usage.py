# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Normalize LLM completion ``usage`` (tokens + optional cost).

Shape-only: OpenAI, Anthropic (already mapped), OpenRouter and xAI ticks
share the same object. No host / vendor name checks.
"""
from __future__ import annotations

from contextvars import ContextVar

# Satellite spend (Design, skill params, …) of the open Chatboo turn.
# The engine binds it at turn start so helpers that do not hold the
# AgentEngine instance can still fold their usage into the footer.
_turn_side_usage = ContextVar('pns_turn_side_usage', default=None)


def bind_turn_side_usage():
    """Open an empty bag for this turn. Returns a token for ``reset``."""
    return _turn_side_usage.set({})


def reset_turn_side_usage(token):
    if token is None:
        return
    _turn_side_usage.reset(token)


def note_turn_side_usage(usage):
    """Fold one satellite completion into the open turn, if any."""
    bag = _turn_side_usage.get()
    if bag is None:
        return
    add_usage(bag, usage)


def bound_turn_side_usage():
    bag = _turn_side_usage.get()
    return dict(bag) if isinstance(bag, dict) else {}


def _as_int(value):
    if value is None or value is False:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_float(value):
    if value is None or value is False:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_cost(usage):
    """USD cost from a usage dict, or None if the vendor sent none.

    Accepts ``cost`` / ``total_cost`` / ``cost_usd``, or
    ``cost_in_usd_ticks`` (1 USD = 10^10 ticks). Does not invent prices.
    """
    if not isinstance(usage, dict):
        return None
    for key in ('cost', 'total_cost', 'cost_usd'):
        n = _as_float(usage.get(key))
        if n is not None and n >= 0:
            return n
    ticks = usage.get('cost_in_usd_ticks')
    if ticks is None:
        return None
    n = _as_float(ticks)
    if n is None or n < 0:
        return None
    return n / 1e10


def advertise_cost(usage):
    """Return a usage dict. Missing cost stays missing; a reported 0 stays 0."""
    if not isinstance(usage, dict):
        usage = {}
    return dict(usage)


def usage_has_tokens(usage):
    """True when the usage object reports any token count."""
    if not isinstance(usage, dict):
        return False
    for key in (
        'prompt_tokens', 'completion_tokens', 'total_tokens',
        'input_tokens', 'output_tokens',
    ):
        if _as_int(usage.get(key)) > 0:
            return True
    return False


def classify_usage_support(response):
    """``yes`` / ``no`` / ``unknown`` from a completion body."""
    if not isinstance(response, dict):
        return 'unknown'
    usage = response.get('usage')
    if usage_has_tokens(usage) or extract_cost(usage) is not None:
        return 'yes'
    if response.get('choices') or response.get('content'):
        return 'no'
    return 'unknown'


def normalize_usage(usage):
    """Canonical keys: prompt/completion/total/cached tokens + optional cost."""
    if not isinstance(usage, dict):
        return {}
    prompt = _as_int(usage.get('prompt_tokens') or usage.get('input_tokens'))
    completion = _as_int(
        usage.get('completion_tokens') or usage.get('output_tokens'),
    )
    created = _as_int(usage.get('cache_creation_input_tokens'))
    if created:
        prompt += created
    total = _as_int(usage.get('total_tokens')) or (
        (prompt + completion) if (prompt or completion) else 0
    )
    details = usage.get('prompt_tokens_details')
    cached = _as_int(
        usage.get('cached_tokens')
        or (details.get('cached_tokens') if isinstance(details, dict) else None)
        or usage.get('cache_read_input_tokens')
    )
    out = {}
    if prompt:
        out['prompt_tokens'] = prompt
    if completion:
        out['completion_tokens'] = completion
    if total:
        out['total_tokens'] = total
    if cached:
        out['cached_tokens'] = cached
    if created:
        out['cache_creation_tokens'] = created
    cost = extract_cost(usage)
    if cost is not None:
        out['cost'] = cost
    return out


def add_usage(acc, usage):
    """Add ``usage`` into accumulator ``acc`` (mutates and returns it)."""
    piece = normalize_usage(usage)
    if not piece:
        return acc if isinstance(acc, dict) else {}
    if not isinstance(acc, dict):
        acc = {}
    for key in (
        'prompt_tokens', 'completion_tokens', 'total_tokens',
        'cached_tokens', 'cache_creation_tokens',
    ):
        if key in piece:
            acc[key] = int(acc.get(key) or 0) + int(piece[key])
    if 'cost' in piece:
        acc['cost'] = float(acc.get('cost') or 0.0) + float(piece['cost'])
    return acc


def usage_since(now, before):
    """What ``now`` has on top of ``before``, both running totals."""
    later = normalize_usage(now)
    earlier = normalize_usage(before)
    out = {}
    for key in (
        'prompt_tokens', 'completion_tokens', 'total_tokens',
        'cached_tokens', 'cache_creation_tokens',
    ):
        delta = int(later.get(key) or 0) - int(earlier.get(key) or 0)
        if delta > 0:
            out[key] = delta
    cost = float(later.get('cost') or 0.0) - float(earlier.get('cost') or 0.0)
    if cost > 0:
        out['cost'] = cost
    return out


def usage_log_fields(usage):
    """Token + USD fields for ``ai.log._create_log_entry``."""
    piece = advertise_cost(normalize_usage(usage or {}))
    ptok = piece.get('prompt_tokens')
    ctok = piece.get('completion_tokens')
    ttok = piece.get('total_tokens') or (
        ((ptok or 0) + (ctok or 0)) or None
    )
    cost_usd = extract_cost(piece)
    return ptok, ctok, ttok, cost_usd
