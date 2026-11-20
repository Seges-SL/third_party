# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Presentation axes: compose, footmode, showmode.

Slash token = internal value. No aliases.
See docs/decisions/presentation_three_axes.md.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

COMPOSE_AGENT = 'compose-agent'
COMPOSE_MODEL = 'compose-model'
# Previous token, still accepted on a slash or a skill file until -u rewrites it.
_COMPOSE_REMAP = {'compose-chatboo': COMPOSE_AGENT}
VALID_COMPOSE = frozenset({COMPOSE_AGENT, COMPOSE_MODEL})
DEFAULT_COMPOSE = COMPOSE_AGENT

FOOT_VERBOSE = 'foot-verbose'
FOOT_LACONIC = 'foot-laconic'
VALID_FOOTMODES = frozenset({FOOT_VERBOSE, FOOT_LACONIC})
DEFAULT_FOOTMODE = FOOT_VERBOSE

SHOW_TABLE = 'show-table'
SHOW_CHART = 'show-chart'
VALID_SHOWMODE_SLASHES = frozenset({SHOW_TABLE, SHOW_CHART})

AXIS_COMPOSE = 'compose'
AXIS_FOOTMODE = 'footmode'
AXIS_SHOWMODE = 'showmode'

# cmd → (axis, value)
AXIS_COMMANDS = {
    COMPOSE_AGENT: (AXIS_COMPOSE, COMPOSE_AGENT),
    COMPOSE_MODEL: (AXIS_COMPOSE, COMPOSE_MODEL),
    FOOT_VERBOSE: (AXIS_FOOTMODE, FOOT_VERBOSE),
    FOOT_LACONIC: (AXIS_FOOTMODE, FOOT_LACONIC),
    SHOW_TABLE: (AXIS_SHOWMODE, SHOW_TABLE),
    SHOW_CHART: (AXIS_SHOWMODE, SHOW_CHART),
}

_SLASH_RE = re.compile(
    r'^/(compose-agent|compose-chatboo|compose-model|foot-verbose|foot-laconic|'
    r'show-table|show-chart)(?:\s+(.*))?$',
    re.IGNORECASE | re.DOTALL,
)

def parse_axis_slash(text: Optional[str]) -> Tuple[Optional[str], Optional[str], str]:
    """Return ``(axis, value, remainder)``. Remainder is the prompt without the slash."""
    raw = (text or '').strip()
    if not raw:
        return None, None, text or ''
    m = _SLASH_RE.match(raw)
    if not m:
        return None, None, text or ''
    cmd = _COMPOSE_REMAP.get(m.group(1).lower(), m.group(1).lower())
    axis, value = AXIS_COMMANDS[cmd]
    rest = (m.group(2) or '').strip()
    return axis, value, rest


def normalize_compose(value) -> Optional[str]:
    if value is None:
        return None
    v = _COMPOSE_REMAP.get(str(value).strip().lower(), str(value).strip().lower())
    if v in VALID_COMPOSE:
        return v
    return None


def normalize_footmode(value) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip().lower()
    if v in VALID_FOOTMODES:
        return v
    if v in ('true', '1', 'on', 'laconic'):
        return FOOT_LACONIC
    if v in ('false', '0', 'off', 'verbose'):
        return FOOT_VERBOSE
    return None


def apply_turn_axis(
    session, prompt: str,
) -> Tuple[Optional[str], Optional[str], str]:
    """Parse a leading axis slash for THIS turn.

    * compose / footmode — one-shot (do not write the provider).
    * showmode — parsed here; the chat client writes its own sticky.
    Alone slash → value set, empty remainder (caller confirms, no LLM).
    """
    del session  # compose/footmode are one-shot; they do not write the session
    axis, value, rest = parse_axis_slash(prompt)
    if not axis:
        return None, None, prompt or ''
    return axis, value, rest


def resolve_compose(
    turn_value=None,
    skill_value=None,
    provider_value=None,
    explicit=None,
) -> str:
    """Effective compose. Priority: explicit → turn slash → skill → provider → agent."""
    if explicit is True:
        return COMPOSE_MODEL
    if explicit is False:
        return COMPOSE_AGENT
    for candidate in (explicit, turn_value, skill_value, provider_value):
        composed = normalize_compose(candidate)
        if composed:
            return composed
    return DEFAULT_COMPOSE


def resolve_footmode(turn_value=None, provider_value=None) -> str:
    return (
        normalize_footmode(turn_value)
        or normalize_footmode(provider_value)
        or DEFAULT_FOOTMODE
    )
