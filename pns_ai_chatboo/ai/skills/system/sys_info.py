# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Read-only Odoo system facts slash skill."""
pairs = [
    ('Odoo version', odoo_version),
    ('Series', odoo_series),
    ('Server date and time', now.strftime('%Y-%m-%d %H:%M:%S')),
    ('User timezone', user_tz),
    ('User language', lang),
    ('Current user', '%s (%s)' % (user_name, user.login)),
    ('Current company', company_name),
    ('Companies', env['res.company'].search_count([])),
    ('Users (total)', env['res.users'].with_context(active_test=False).search_count([])),
    ('Active users', env['res.users'].search_count([])),
    ('Installed modules', env['ir.module.module'].search_count([('state', '=', 'installed')])),
]

if web_base_url:
    pairs.append(('Base URL', web_base_url))

result = {
    'data': [{'Property': k, 'Value': v} for k, v in pairs],
    '__return_direct__': True,
    '__stop_after_direct__': True,
    '__no_footer__': True,
}
