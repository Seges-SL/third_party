# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Temporary key PIN: length and the per-IP attempt budget.

The PIN is a short number an admin reads out. The browser tab holding the
key list mints one PIN per person; while that tab is open, the PIN can hand
that person's existing API key to an app. The list and the PINs stay in the
tab. Odoo never stores a PIN, in clear or as a hash.
"""

DEFAULT_PIN_LENGTH = 8
DEFAULT_PIN_ATTEMPTS = 100
DEFAULT_PIN_BLOCK_HOURS = 1

PIN_LENGTH_MIN = 4
PIN_LENGTH_MAX = 12

ICP_PIN_LENGTH = 'pns_ai_mcp.key_pin_length'
ICP_PIN_ATTEMPTS = 'pns_ai_mcp.key_pin_attempts'
ICP_PIN_BLOCK_HOURS = 'pns_ai_mcp.key_pin_block_hours'

# A desk that has not called in this long is closed.
DESK_TTL_SECONDS = 45


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clamp_pin_length(value):
    """Digits in a new PIN. Out of range or empty falls back to 8."""
    number = _as_int(value)
    if number is None or number < PIN_LENGTH_MIN or number > PIN_LENGTH_MAX:
        return DEFAULT_PIN_LENGTH
    return number


def clamp_positive(value, default):
    """A setting that must be at least 1. Empty or lower keeps ``default``."""
    number = _as_int(value)
    if number is None or number < 1:
        return default
    return number


def compact_pin(raw, length):
    """Digits of a PIN typed with or without spaces between groups of four.

    Anything that is not only digits and separators is left as it was,
    so an API key is not stripped.
    """
    text = (raw or '').strip()
    if not text:
        return text
    number = _as_int(length) or DEFAULT_PIN_LENGTH
    for ch in text:
        if ch not in '0123456789 -':
            return text
    digits = ''.join(ch for ch in text if ch.isdigit())
    if len(digits) == number:
        return digits
    return text


def pin_shaped(raw, length):
    """True when ``raw`` is a PIN attempt: exactly ``length`` digits."""
    if not isinstance(raw, str):
        return False
    text = raw.strip()
    return bool(text) and text.isdigit() and len(text) == length


def failure_starts_block(failures, limit):
    """True once this IP has gone past the allowed PIN failures.

    ``limit`` failures are still answered. The next one starts the block.
    A successful handoff does not increment ``failures``.
    """
    cap = clamp_positive(limit, DEFAULT_PIN_ATTEMPTS)
    try:
        count = int(failures)
    except (TypeError, ValueError):
        return False
    return count > cap


def pin_length(env):
    ICP = env['ir.config_parameter'].sudo()
    return clamp_pin_length(ICP.get_param(ICP_PIN_LENGTH))


def pin_attempts(env):
    ICP = env['ir.config_parameter'].sudo()
    return clamp_positive(ICP.get_param(ICP_PIN_ATTEMPTS), DEFAULT_PIN_ATTEMPTS)


def pin_block_hours(env):
    ICP = env['ir.config_parameter'].sudo()
    return clamp_positive(
        ICP.get_param(ICP_PIN_BLOCK_HOURS), DEFAULT_PIN_BLOCK_HOURS,
    )
