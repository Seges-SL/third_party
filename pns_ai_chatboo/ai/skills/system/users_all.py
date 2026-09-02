# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# Todos los usuarios del sistema (incluye archivados), ordenados por login.
rows = []
users = env['res.users'].with_context(active_test=False).search([], order='login')
for u in users:
    rows.append({
        'Login': u.login,
        'Nombre': u.name,
        'Email': u.email or '',
        'Tipo': 'Portal/Público' if u.share else 'Interno',
        'Activo': 'Sí' if u.active else 'No',
        'Último acceso': u.login_date.strftime('%Y-%m-%d %H:%M:%S') if u.login_date else '—',
    })

result = {
    'data': rows,
    '__return_direct__': True,
    '__stop_after_direct__': True,
    '__no_footer__': True,
}
