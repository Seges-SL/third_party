# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Users currently connected (bus presence), or latest logins if the bus is empty."""
rows = []
try:
    presences = env['bus.presence'].search([('status', 'in', ['online', 'away'])])
    for pr in presences:
        u = pr.user_id
        if not u:
            continue
        last = pr.last_presence or pr.last_poll
        rows.append({
            'User': u.name,
            'Login': u.login,
            'Status': pr.status,
            'Last signal': last.strftime('%Y-%m-%d %H:%M:%S') if last else '',
        })
except Exception:
    rows = []

if not rows:
    # login_date is not always SQL-sortable across majors: fetch and sort in Python.
    recent = env['res.users'].search([]).filtered(lambda u: u.login_date)
    recent = recent.sorted(key=lambda u: u.login_date, reverse=True)[:20]
    for u in recent:
        rows.append({
            'User': u.name,
            'Login': u.login,
            'Status': 'last login',
            'Last signal': u.login_date.strftime('%Y-%m-%d %H:%M:%S') if u.login_date else '',
        })

result = {
    'data': sorted(rows, key=operator.itemgetter('User')),
    '__return_direct__': True,
    '__stop_after_direct__': True,
    '__no_footer__': True,
}
