# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""System users with their live presence. Each row opens the user form."""
try:
    _online_only = online
except NameError:
    _online_only = None
_online_only = _online_only is True or str(_online_only or '').strip().lower() in ('true', '1')

# Odoo 18+ keeps presence in mail.presence; 14 to 17 in bus.presence.
_presence_model = None
for _name in ('mail.presence', 'bus.presence'):
    if _name in env:
        _presence_model = _name
        break
_status = {}
if _presence_model:
    for _p in env[_presence_model].search([('status', 'in', ['online', 'away'])]):
        if _p.user_id:
            _status[_p.user_id.id] = _p.status

_users = env['res.users'].with_context(active_test=False).search([], order='login')
if _online_only:
    _users = _users.filtered(lambda u: u.id in _status)

rows = [
    {
        'id': u.id,
        '__model': 'res.users',
        'Name': u.name,
        'Login': u.login,
        'Type': 'Portal / public' if u.share else 'Internal',
        'Active': 'Yes' if u.active else 'No',
        'Presence': _status.get(u.id, ''),
        'Last login': u.login_date.strftime('%Y-%m-%d %H:%M') if u.login_date else '',
    }
    for u in _users
]

if rows:
    result = {
        'data': rows,
        'summary': '%d users%s.' % (len(rows), ' connected now' if _online_only else ''),
        '__hide_columns__': ['id'],
        '__return_direct__': True,
        '__stop_after_direct__': True,
        '__no_footer__': True,
    }
else:
    result = {
        'formatted_text': '<p class="text-muted">Nobody is connected right now.</p>',
        '__return_direct__': True,
        '__stop_after_direct__': True,
        '__no_footer__': True,
    }
