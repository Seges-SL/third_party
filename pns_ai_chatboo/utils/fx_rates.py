# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Chatboo FX adapter: the engine owns feeds; Chatboo only consumes them."""
from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


def get_usd_fx(env):
    """Return ``{base, rates, as_of, error}`` from ``ai.fx.source``.

    A failure is reported with empty ``rates`` plus ``error`` instead of
    ``None`` so the chip can say it is falling back to USD.
    """
    try:
        payload = env['ai.fx.source'].get_usd_fx()
    except Exception as exc:
        _logger.warning('FX rates unavailable from ai.fx.source: %s', exc, exc_info=True)
        return {'base': 'USD', 'rates': {}, 'as_of': '', 'error': str(exc)}
    if not isinstance(payload, dict):
        return {
            'base': 'USD',
            'rates': {},
            'as_of': '',
            'error': 'ai.fx.source returned no rates',
        }
    return payload
