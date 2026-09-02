# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# Archivo: utils/compat.py
# Descripción: Utilidades de compatibilidad entre versiones de Odoo (13 a 19+).
#   Capa GENÉRICA del ecosistema PNS. Las utilidades específicas de un módulo
#   (que dependen de datos propios: grupos, assets, etc.) NO van aquí; viven en
#   el módulo correspondiente y, si lo necesitan, importan estos helpers.

import odoo

# Versión principal de Odoo (entero).
ODOO_VERSION = odoo.release.version_info[0]

# Odoo 19+ cambió type='json' por type='jsonrpc'.
JSON_ROUTE_TYPE = 'jsonrpc' if ODOO_VERSION >= 19 else 'json'

# Odoo 16+ unificó HttpRequest y JsonRequest en Request, por lo que el parche
# de Root.get_request solo es necesario en versiones <= 15.
NEEDS_ROOT_GET_REQUEST_PATCH = ODOO_VERSION <= 15

# Odoo 19+: res.users.groups_id -> group_ids (directo) / all_group_ids (con implicados).
USER_GROUPS_FIELD = 'group_ids' if ODOO_VERSION >= 19 else 'groups_id'
USER_ALL_GROUPS_FIELD = 'all_group_ids' if ODOO_VERSION >= 19 else 'groups_id'

# Odoo 19+: res.groups.category_id -> privilege_id; users -> user_ids.
GROUP_CATEGORY_FIELD = 'privilege_id' if ODOO_VERSION >= 19 else 'category_id'
GROUP_USERS_FIELD = 'user_ids' if ODOO_VERSION >= 19 else 'users'

# Odoo 17+: invalidate_cache() → invalidate_recordset().
_USE_INVALIDATE_RECORDSET = ODOO_VERSION >= 17

# Separador login + nombre en informes de importación (convención por idioma).
_LOCALE_SEMICOLON_LANGS = ('es', 'de', 'fr', 'it', 'pt', 'ca', 'gl', 'eu')


def locale_field_separator(env):
    """Separador legible entre campos en listas de importación (idioma activo)."""
    lang = (env.context.get('lang') or env.user.lang or 'en_US').replace('-', '_').lower()
    prefix = lang.split('_')[0]
    if prefix in _LOCALE_SEMICOLON_LANGS:
        return '; '
    return ', '


def format_login_name_line(env, login, name):
    """Una línea login + nombre para informes de importación."""
    name = (name or '').strip()
    if not name:
        return login
    return f"{login}{locale_field_separator(env)}{name}"


def invalidate_recordset_fields(recordset, field_names):
    """Invalida campos en caché (O13–O19+)."""
    if not recordset:
        return
    if _USE_INVALIDATE_RECORDSET:
        recordset.invalidate_recordset(field_names)
    else:
        recordset.invalidate_cache(field_names)


def user_has_group(user, group):
    """True si el usuario tiene el grupo (directo o implicado)."""
    return group in user[USER_ALL_GROUPS_FIELD]


def user_has_group_direct(user, group):
    """True si el grupo está asignado directamente al usuario."""
    return group in user[USER_GROUPS_FIELD]


def apply_groups_field_alias(vals, fields):
    """Renombra groups_id ↔ group_ids para que coincida con ``fields``.

    Odoo 19+ cambió el nombre en res.users, ir.ui.menu, ir.ui.view y
    ir.actions.*. Mutates ``vals`` in place.
    """
    if not isinstance(vals, dict) or not vals or not fields:
        return
    if 'groups_id' in vals and 'groups_id' not in fields and 'group_ids' in fields:
        vals['group_ids'] = vals.pop('groups_id')
    elif 'group_ids' in vals and 'group_ids' not in fields and 'groups_id' in fields:
        vals['groups_id'] = vals.pop('group_ids')


def normalize_res_users_write_values(values, env):
    """Traduce groups_id ↔ group_ids según los campos reales del registro.

    Odoo 19+ renombró el m2m de grupos en res.users. Para escrituras declarativas
    (p. ej. propose_write_operations) aceptamos el nombre legacy si el destino
    solo expone el nuevo, y viceversa en O14–18.
    """
    if not isinstance(values, dict) or not values:
        return values
    try:
        fields = env['res.users']._fields
    except KeyError:
        return values
    vals = dict(values)
    apply_groups_field_alias(vals, fields)
    return vals


def normalize_model_write_values(model, values, env):
    """Ajusta valores de write/create a campos válidos del modelo (cross-version)."""
    if model == 'res.users':
        return normalize_res_users_write_values(values, env)
    return values


def user_add_group(user, group):
    """Añade un grupo directo al usuario si aún no lo tiene."""
    if not user_has_group_direct(user, group):
        user.write({USER_GROUPS_FIELD: [(4, group.id)]})


def user_remove_group(user, group):
    """Quita un grupo directo del usuario."""
    if user_has_group_direct(user, group):
        user.write({USER_GROUPS_FIELD: [(3, group.id)]})


def search_users_with_group(env, group):
    """Usuarios que tienen el grupo (directo o implicado)."""
    return env['res.users'].sudo().search([(USER_ALL_GROUPS_FIELD, 'in', group.id)])


def get_odoo_admin_groups(env):
    """Grupos Odoo con Ajustes (Settings)."""
    group = env.ref('base.group_system', raise_if_not_found=False)
    return [group] if group else []


def user_is_odoo_admin(user, env):
    """True si el usuario tiene Ajustes (base.group_system)."""
    return any(user_has_group(user, group) for group in get_odoo_admin_groups(env))
