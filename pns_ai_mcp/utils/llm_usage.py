# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Normalize LLM completion ``usage`` (tokens + optional cost).

Shape-only: OpenAI, Anthropic (already mapped), OpenRouter and xAI ticks
share the same object. No host / vendor name checks.
"""
from __future__ import annotations


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


def advertise_cost(usage, on_premise=False):
    """Return a usage dict that Chatboo can price.

    Cloud / unknown (default): leave cost as reported (or absent → UI "-").
    On premises: if the gateway omitted cost, advertise ``cost=0.0`` so the
    chip shows 0. If it did report a cost (tokens, electricity, …), keep it.
    """
    if not isinstance(usage, dict):
        usage = {}
    out = dict(usage)
    if on_premise and extract_cost(out) is None:
        out['cost'] = 0.0
    return out


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
    for key in ('prompt_tokens', 'completion_tokens', 'total_tokens', 'cached_tokens'):
        if key in piece:
            acc[key] = int(acc.get(key) or 0) + int(piece[key])
    if 'cost' in piece:
        acc['cost'] = float(acc.get('cost') or 0.0) + float(piece['cost'])
    return acc
