# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Presentation axes: painter, footmode, showmode.

Slash token = internal value. User slashes /report and /table are retired
(no aliases). See docs/decisions/presentation_three_axes.md.
"""
from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

_logger = logging.getLogger(__name__)

PAINTER_LOCAL = 'painter-local'
PAINTER_FREE = 'painter-free'
VALID_PAINTERS = frozenset({PAINTER_LOCAL, PAINTER_FREE})
DEFAULT_PAINTER = PAINTER_LOCAL

FOOT_VERBOSE = 'foot-verbose'
FOOT_LACONIC = 'foot-laconic'
VALID_FOOTMODES = frozenset({FOOT_VERBOSE, FOOT_LACONIC})
DEFAULT_FOOTMODE = FOOT_VERBOSE

SHOW_TABLE = 'show-table'
SHOW_CHART = 'show-chart'
VALID_SHOWMODE_SLASHES = frozenset({SHOW_TABLE, SHOW_CHART})

AXIS_PAINTER = 'painter'
AXIS_FOOTMODE = 'footmode'
AXIS_SHOWMODE = 'showmode'

# cmd → (axis, value)
AXIS_COMMANDS = {
    PAINTER_LOCAL: (AXIS_PAINTER, PAINTER_LOCAL),
    PAINTER_FREE: (AXIS_PAINTER, PAINTER_FREE),
    FOOT_VERBOSE: (AXIS_FOOTMODE, FOOT_VERBOSE),
    FOOT_LACONIC: (AXIS_FOOTMODE, FOOT_LACONIC),
    SHOW_TABLE: (AXIS_SHOWMODE, SHOW_TABLE),
    SHOW_CHART: (AXIS_SHOWMODE, SHOW_CHART),
}

_SLASH_RE = re.compile(
    r'^/(painter-local|painter-free|foot-verbose|foot-laconic|'
    r'show-table|show-chart)(?:\s+(.*))?$',
    re.IGNORECASE | re.DOTALL,
)

# YAML / DB leftovers only — never user slashes.
_PAINTER_LEGACY = {
    'table': PAINTER_LOCAL,
    'local': PAINTER_LOCAL,
    'false': PAINTER_LOCAL,
    '0': PAINTER_LOCAL,
    'off': PAINTER_LOCAL,
    'report': PAINTER_FREE,
    'remote': PAINTER_FREE,
    'true': PAINTER_FREE,
    '1': PAINTER_FREE,
    'on': PAINTER_FREE,
    'free': PAINTER_FREE,
}


def parse_axis_slash(text: Optional[str]) -> Tuple[Optional[str], Optional[str], str]:
    """Return ``(axis, value, remainder)``. Remainder is the prompt without the slash."""
    raw = (text or '').strip()
    if not raw:
        return None, None, text or ''
    m = _SLASH_RE.match(raw)
    if not m:
        return None, None, text or ''
    cmd = m.group(1).lower()
    axis, value = AXIS_COMMANDS[cmd]
    rest = (m.group(2) or '').strip()
    return axis, value, rest


def parse_formatting_slash(text: Optional[str]) -> Tuple[Optional[str], str]:
    """Painter slash only — ``(painter-local|painter-free|None, remainder)``."""
    axis, value, rest = parse_axis_slash(text)
    if axis == AXIS_PAINTER:
        return value, rest
    return None, text or ''


def normalize_painter(value) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip().lower()
    if not v:
        return None
    if v in VALID_PAINTERS:
        return v
    return _PAINTER_LEGACY.get(v)


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


def normalize_mode(value) -> Optional[str]:
    """Normalize a painter token (legacy name kept for callers)."""
    return normalize_painter(value)


def _session_short_write(session, vals) -> None:
    """Write session fields on a short cursor (not the ReAct/worker txn).

    Without ``session.env.registry`` (unit tests / stubs) fall back to sudo write.
    """
    try:
        if not session or not getattr(session, 'id', None) or not vals:
            return
        registry = getattr(getattr(session, 'env', None), 'registry', None)
        if registry is None:
            session.sudo().write(vals)
            return
        with registry.cursor() as cr:
            env = type(session.env)(cr, session.env.uid, dict(session.env.context or {}))
            rec = env[session._name].browse(session.id)
            if rec.exists():
                rec.sudo().write(vals)
            cr.commit()
    except Exception:
        _logger.debug('session short write skipped', exc_info=True)


def _clear_legacy_session_sticky(session) -> None:
    """Drop leftover session sticky from older builds (one-shot slash contract)."""
    try:
        if not session or not getattr(session, 'id', None):
            return
        if getattr(session, 'llm_formatting_mode', False):
            _session_short_write(session, {'llm_formatting_mode': False})
    except Exception:
        _logger.debug('painter sticky clear skipped', exc_info=True)


def _write_session_showmode(session, value: str) -> None:
    try:
        if not session or not getattr(session, 'id', None):
            return
        _session_short_write(session, {'presentation_show_mode': value})
    except Exception:
        _logger.debug('showmode session write skipped', exc_info=True)


def apply_turn_axis(
    session, prompt: str,
) -> Tuple[Optional[str], Optional[str], str]:
    """Parse a leading axis slash for THIS turn.

    * painter / footmode — one-shot (do not write the provider).
    * showmode — writes ``chatboo.session.presentation_show_mode``.
    Alone slash → value set, empty remainder (caller confirms, no LLM).
    """
    _clear_legacy_session_sticky(session)
    axis, value, rest = parse_axis_slash(prompt)
    if not axis:
        return None, None, prompt or ''
    if axis == AXIS_SHOWMODE and value:
        _write_session_showmode(session, value)
    return axis, value, rest


def apply_turn_formatting_mode(session, prompt: str) -> Tuple[Optional[str], str]:
    """Painter-only helper: ``(painter value|None, remainder)``."""
    axis, value, rest = apply_turn_axis(session, prompt)
    if axis == AXIS_PAINTER:
        return value, rest
    if axis:
        return None, rest
    return None, prompt or ''


apply_sticky_formatting_mode = apply_turn_formatting_mode


def resolve_painter(
    turn_value=None,
    skill_value=None,
    provider_value=None,
    explicit=None,
) -> str:
    """Effective painter. Priority: explicit → turn slash → skill → provider → local."""
    if explicit is True:
        return PAINTER_FREE
    if explicit is False:
        return PAINTER_LOCAL
    for candidate in (explicit, turn_value, skill_value, provider_value):
        painted = normalize_painter(candidate)
        if painted:
            return painted
    return DEFAULT_PAINTER


def resolve_footmode(turn_value=None, provider_value=None) -> str:
    return (
        normalize_footmode(turn_value)
        or normalize_footmode(provider_value)
        or DEFAULT_FOOTMODE
    )


def resolve_remote_formatting_override(
    session=None,
    turn_mode: Optional[str] = None,
    explicit=None,
) -> Optional[bool]:
    """Whether this turn uses painter-free (model formats) vs painter-local (HTML).

    Returns:
      True  → painter-free
      False → painter-local (explicit)
      None  → no turn/explicit signal (caller uses provider.painter)

    Priority: explicit payload → turn slash → None.
    Session sticky is intentionally ignored (one-shot slash contract).
    """
    del session  # legacy sticky removed
    if explicit is True or explicit is False:
        return explicit
    mode = normalize_painter(explicit) if explicit is not None else None
    if mode is None:
        mode = normalize_painter(turn_mode)
    if mode == PAINTER_FREE:
        return True
    if mode == PAINTER_LOCAL:
        return False
    return None
