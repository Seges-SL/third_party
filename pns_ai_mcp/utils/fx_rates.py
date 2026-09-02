# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""USD FX helpers for cost presentation (no persistence of converted amounts)."""
from __future__ import annotations


def parse_feed_rates(body):
    """Extract a USD-based rate map from a feed JSON object."""
    if not isinstance(body, dict):
        return None
    rates = body.get('rates')
    if not isinstance(rates, dict) or not rates:
        return None
    out = {}
    for key, val in rates.items():
        try:
            n = float(val)
        except (TypeError, ValueError):
            continue
        if n <= 0:
            continue
        code = str(key or '').strip().upper()
        if len(code) == 3:
            out[code] = n
    if not out:
        return None
    out['USD'] = 1.0
    return out


def convert_usd_amount(amount, currency, fx):
    """Return ``{amount, currency, rate, as_of}`` for presentation.

    Vendor cost stays USD. If ``fx`` lacks the requested ISO, keep USD.
    """
    try:
        n = float(amount)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    want = str(currency or 'USD').strip().upper() or 'USD'
    as_of = (fx or {}).get('as_of') if isinstance(fx, dict) else None
    rates = (fx or {}).get('rates') if isinstance(fx, dict) else None
    if want != 'USD' and isinstance(rates, dict) and rates.get(want):
        try:
            rate = float(rates[want])
        except (TypeError, ValueError):
            rate = 0
        if rate > 0:
            return {
                'amount': n * rate,
                'currency': want,
                'rate': rate,
                'as_of': as_of,
            }
    return {
        'amount': n,
        'currency': 'USD',
        'rate': 1.0,
        'as_of': as_of,
    }
