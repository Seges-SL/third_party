# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Format LLM usage for UI labels (tokens + display currency)."""
from __future__ import annotations

from .display_currency import format_amount_with_symbol, get_display_currency
from .llm_usage import extract_cost, normalize_usage, usage_has_tokens


def format_turn_tokens_label(usage):
    """Compact token label (e.g. ``2.50k``) or ``-``."""
    piece = normalize_usage(usage or {})
    total = int(piece.get('total_tokens') or 0)
    if not total:
        pt = int(piece.get('prompt_tokens') or 0)
        ct = int(piece.get('completion_tokens') or 0)
        total = pt + ct
    if total <= 0:
        return '-'
    if total < 1024:
        return str(total)
    return '%.2fk' % (total / 1024.0)


def format_cost_label(env, usd):
    """Return ``{label, title}`` for a USD amount in display currency."""
    if usd is None:
        return {'label': '-', 'title': 'Cost unknown'}
    try:
        n = float(usd)
    except (TypeError, ValueError):
        return {'label': '-', 'title': 'Cost unknown'}
    if n < 0:
        return {'label': '-', 'title': 'Cost unknown'}
    currency = get_display_currency(env)
    converted = env['ai.fx.source'].convert_usd(n, currency)
    if not converted:
        code = 'USD'
        amount = n
        rate = 1.0
        failed = currency != 'USD'
    else:
        code = converted.get('currency') or 'USD'
        amount = float(converted.get('amount') or n)
        rate = float(converted.get('rate') or 1.0)
        failed = False
    label = format_amount_with_symbol(code, amount)
    title = code
    if failed:
        label += ' (!)'
        title = 'Shown in USD (no %s rate)' % currency
    return {'label': label, 'title': title}


def format_usage_chip(env, usage):
    """``tokens · cost`` label for notifications and summaries."""
    if not usage_has_tokens(usage) and extract_cost(usage) is None:
        return ''
    tokens = format_turn_tokens_label(usage)
    cost = format_cost_label(env, extract_cost(normalize_usage(usage or {})))
    if cost['label'] == '-':
        return tokens
    return '%s · %s' % (tokens, cost['label'])
