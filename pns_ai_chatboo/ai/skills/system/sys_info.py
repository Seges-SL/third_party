# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# Información del sistema Odoo (solo lectura).
pairs = [
    ('Versión de Odoo', odoo_version),
    ('Serie', odoo_series),
    ('Base de datos', dbname),
    ('Fecha y hora del servidor', now.strftime('%Y-%m-%d %H:%M:%S')),
    ('Zona horaria del usuario', user_tz),
    ('Idioma del usuario', lang),
    ('Usuario actual', '%s (%s)' % (user_name, user.login)),
    ('Compañía actual', company_name),
    ('Nº de compañías', env['res.company'].search_count([])),
    ('Nº de usuarios (total)', env['res.users'].with_context(active_test=False).search_count([])),
    ('Nº de usuarios activos', env['res.users'].search_count([])),
    ('Nº de módulos instalados', env['ir.module.module'].search_count([('state', '=', 'installed')])),
]

base_url = env['ir.config_parameter'].sudo().get_param('web.base.url')
if base_url:
    pairs.append(('URL base', base_url))

result = {
    'data': [{'Propiedad': k, 'Valor': v} for k, v in pairs],
    '__return_direct__': True,
    '__stop_after_direct__': True,
    '__no_footer__': True,
}
