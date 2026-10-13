# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Session user's timezone (Odoo ``tz``), no business literals.

The process clock (container) is usually UTC. Cards and the sandbox must
use the user's IANA tz (``env.context['tz']`` / ``user.tz``).
"""
from __future__ import annotations

from datetime import datetime, timezone


def resolve_tzinfo(tz_name):
    """``tzinfo`` para un nombre IANA. UTC si el nombre no resuelve."""
    name = (tz_name or '').strip() or 'UTC'
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        pass
    try:
        import pytz
        return pytz.timezone(name)
    except Exception:
        pass
    return timezone.utc


def user_local_now(tz_name=None):
    """``datetime`` aware en el huso del usuario (ahora)."""
    return datetime.now(resolve_tzinfo(tz_name))


def parse_iso_datetime(iso):
    """Parsea ISO-8601. ``Z`` → UTC. None si no es parseable."""
    raw = (iso or '').strip()
    if not raw:
        return None
    if raw.endswith('Z') or raw.endswith('z'):
        raw = raw[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def normalize_clock_iso(iso, tz_name=None):
    """ISO de card reloj → (iso_con_offset, tz_name).

    Invariante: un instante naive se trata como UTC (reloj de proceso) y
    se reescribe en ``tz_name`` (huso de la card, o el de sesión si la
    card no trae ``tz``). Si no hay ``tz_name``, se deja el iso.
    """
    name = (tz_name or '').strip()
    dt = parse_iso_datetime(iso)
    if dt is None:
        return iso, name or None
    if not name:
        if dt.tzinfo is None:
            return iso, None
        return dt.isoformat(timespec='seconds'), name or None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    localized = dt.astimezone(resolve_tzinfo(name))
    return localized.isoformat(timespec='seconds'), name
