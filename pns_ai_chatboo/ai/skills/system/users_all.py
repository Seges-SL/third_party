# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""List every system user (including archived), sorted by login."""
rows = []
users = env['res.users'].with_context(active_test=False).search([], order='login')
for u in users:
    rows.append({
        'Login': u.login,
        'Name': u.name,
        'Email': u.email or '',
        'Type': 'Portal/Public' if u.share else 'Internal',
        'Active': 'Yes' if u.active else 'No',
        'Last login': u.login_date.strftime('%Y-%m-%d %H:%M:%S') if u.login_date else '—',
    })

result = {
    'data': rows,
    '__return_direct__': True,
    '__stop_after_direct__': True,
    '__no_footer__': True,
}
