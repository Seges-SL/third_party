# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# Usuarios actualmente conectados (presencia del bus). Si el módulo de bus no está
# disponible o no hay presencia, se muestran los últimos accesos por fecha de login.
rows = []
try:
    presences = env['bus.presence'].search([('status', 'in', ['online', 'away'])])
    for pr in presences:
        u = pr.user_id
        if not u:
            continue
        last = pr.last_presence or pr.last_poll
        rows.append({
            'Usuario': u.name,
            'Login': u.login,
            'Estado': pr.status,
            'Última señal': last.strftime('%Y-%m-%d %H:%M:%S') if last else '',
        })
except Exception:
    rows = []

if not rows:
    # login_date no siempre es columna ordenable en SQL (varía por versión):
    # traemos los usuarios con acceso y ordenamos/limitamos en Python.
    recent = env['res.users'].search([]).filtered(lambda u: u.login_date)
    recent = recent.sorted(key=lambda u: u.login_date, reverse=True)[:20]
    for u in recent:
        rows.append({
            'Usuario': u.name,
            'Login': u.login,
            'Estado': 'último acceso',
            'Última señal': u.login_date.strftime('%Y-%m-%d %H:%M:%S') if u.login_date else '',
        })

result = {
    'data': sorted(rows, key=operator.itemgetter('Usuario')),
    '__return_direct__': True,
    '__stop_after_direct__': True,
    '__no_footer__': True,
}
