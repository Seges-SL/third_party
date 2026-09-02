# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Wall clock for Chatboo UI: user tz, else company, else UTC.

Odoo stores Datetime in UTC. Message stamps in the session JSON are *display*
strings, so they must follow the same tz the rest of the ERP uses — not the
container clock.
"""
from __future__ import annotations

from datetime import datetime, timezone


def resolve_display_tz(*candidates):
    """First non-empty IANA name. Last resort UTC."""
    for name in candidates:
        if name is None or name is False:
            continue
        text = str(name).strip()
        if text and text.lower() not in ('false', '0', 'none'):
            return text
    return 'UTC'


def env_tz_candidates(env):
    """(context tz, user tz, company tz) from an Odoo env."""
    ctx = getattr(env, 'context', None) or {}
    ctx_tz = ctx.get('tz')
    user = getattr(env, 'user', None)
    user_tz = getattr(user, 'tz', None) if user else None
    company_tz = None
    company = getattr(env, 'company', None)
    if company:
        partner = getattr(company, 'partner_id', None)
        if partner:
            company_tz = getattr(partner, 'tz', None)
        if not company_tz:
            calendar = getattr(company, 'resource_calendar_id', None)
            if calendar:
                company_tz = getattr(calendar, 'tz', None)
    return ctx_tz, user_tz, company_tz


def format_wallclock(utc_naive, tz_name):
    """Naive UTC datetime → ``YYYY-MM-DD HH:MM:SS`` in ``tz_name``."""
    dt = utc_naive
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif getattr(dt, 'tzinfo', None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    zi = _tzinfo(tz_name)
    return dt.astimezone(zi).strftime('%Y-%m-%d %H:%M:%S')


def format_env_wallclock(env, utc_naive=None):
    """Display stamp for Chatboo using the env's user/company tz."""
    tz_name = resolve_display_tz(*env_tz_candidates(env))
    return format_wallclock(utc_naive, tz_name)


def _tzinfo(tz_name):
    try:
        from odoo.addons.pns_ai_mcp.utils.user_time import resolve_tzinfo
        return resolve_tzinfo(tz_name)
    except Exception:
        pass
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
        return timezone.utc
