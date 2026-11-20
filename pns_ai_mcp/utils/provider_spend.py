# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Monthly spend cap for one inference provider (shape only, no Odoo).

Empty / 0 = no cap. A reported cost uses the USD cap; otherwise the token
cap. Never invents euros from tokens.
"""
from __future__ import annotations


def _as_float(value):
    if value in (None, False, ''):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def cap_is_set(value):
    return _as_float(value) > 0


def spend_cap_hit(usage, cap_usd=None, cap_tokens=None):
    """True when this month already meets a cap that can be measured."""
    usage = usage if isinstance(usage, dict) else {}
    cost = _as_float(usage.get('cost') or usage.get('cost_usd'))
    tokens = _as_float(
        usage.get('total_tokens')
        or (
            _as_float(usage.get('prompt_tokens'))
            + _as_float(usage.get('completion_tokens'))
        ),
    )
    if cap_is_set(cap_usd) and cost > 0:
        return cost >= _as_float(cap_usd)
    if cap_is_set(cap_tokens) and tokens > 0:
        return tokens >= _as_float(cap_tokens)
    return False
