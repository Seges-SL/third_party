# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Cross-version Odoo names (13–19+): JSON routes, groups, cache.

Generic suite helpers only. Module-specific names (own groups, assets)
stay in that module and import from here when needed.
"""

import base64

import odoo

# Odoo major version (int).
ODOO_VERSION = odoo.release.version_info[0]

# Odoo 19+ renamed route type='json' to type='jsonrpc'.
JSON_ROUTE_TYPE = 'jsonrpc' if ODOO_VERSION >= 19 else 'json'

# Odoo 20+ split odoo.http into a package; content_disposition lives in its stream module.
if ODOO_VERSION >= 20:
    from odoo.http.stream import content_disposition  # noqa: F401
else:
    from odoo.http import content_disposition  # noqa: F401

# Odoo 16+ merged HttpRequest and JsonRequest into Request, so the
# Root.get_request patch is only needed up to 15.
NEEDS_ROOT_GET_REQUEST_PATCH = ODOO_VERSION <= 15

# Odoo 19+: res.users.groups_id -> group_ids (direct) / all_group_ids (with implied).
USER_GROUPS_FIELD = 'group_ids' if ODOO_VERSION >= 19 else 'groups_id'
USER_ALL_GROUPS_FIELD = 'all_group_ids' if ODOO_VERSION >= 19 else 'groups_id'

# Odoo 19+: res.groups.category_id -> privilege_id; users -> user_ids.
GROUP_CATEGORY_FIELD = 'privilege_id' if ODOO_VERSION >= 19 else 'category_id'
GROUP_USERS_FIELD = 'user_ids' if ODOO_VERSION >= 19 else 'users'

# Odoo 16+: invalidate_cache() → invalidate_recordset().
_USE_INVALIDATE_RECORDSET = ODOO_VERSION >= 16


def binary_bytes(value):
    """Raw bytes of a Binary field read on a record (b'' when empty).

    Up to 19 the field reads as base64. Odoo 20+ reads it as a BinaryValue
    that already holds the bytes. Attachments: ``raw`` holds the bytes in
    every series (``datas`` is gone in 20); read it with ``bytes(att.raw or b'')``.
    """
    if not value:
        return b''
    if ODOO_VERSION >= 20:
        return bytes(value)
    return base64.b64decode(value)


# Separator between login and name in import reports (per-language convention).
_LOCALE_SEMICOLON_LANGS = ('es', 'de', 'fr', 'it', 'pt', 'ca', 'gl', 'eu')


def locale_field_separator(env):
    """Readable separator between fields in import lists (active language)."""
    lang = (env.context.get('lang') or env.user.lang or 'en_US').replace('-', '_').lower()
    prefix = lang.split('_')[0]
    if prefix in _LOCALE_SEMICOLON_LANGS:
        return '; '
    return ', '


def format_login_name_line(env, login, name):
    """One line with login and name for import reports."""
    name = (name or '').strip()
    if not name:
        return login
    return f"{login}{locale_field_separator(env)}{name}"


def invalidate_recordset_fields(recordset, field_names):
    """Invalidate cached fields (O13–O19+)."""
    if not recordset:
        return
    if _USE_INVALIDATE_RECORDSET:
        recordset.invalidate_recordset(field_names)
    else:
        recordset.invalidate_cache(field_names)


def user_has_group(user, group):
    """True if the user has the group (direct or implied)."""
    return group in user[USER_ALL_GROUPS_FIELD]


def user_has_group_direct(user, group):
    """True if the group is assigned directly to the user."""
    return group in user[USER_GROUPS_FIELD]


def apply_groups_field_alias(vals, fields):
    """Rename groups_id ↔ group_ids to match ``fields``.

    Odoo 19+ renamed it on res.users, ir.ui.menu, ir.ui.view and
    ir.actions.*. Mutates ``vals`` in place.
    """
    if not isinstance(vals, dict) or not vals or not fields:
        return
    if 'groups_id' in vals and 'groups_id' not in fields and 'group_ids' in fields:
        vals['group_ids'] = vals.pop('groups_id')
    elif 'group_ids' in vals and 'group_ids' not in fields and 'groups_id' in fields:
        vals['groups_id'] = vals.pop('group_ids')


def normalize_res_users_write_values(values, env):
    """Map groups_id ↔ group_ids to the fields the registry really has.

    Odoo 19+ renamed the groups m2m on res.users. Declarative writes
    (e.g. propose_write_operations) may use the legacy name when the target
    only has the new one, and the other way round on O14–18.
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
    """Fit write/create values to the fields the model has (cross-version)."""
    if model == 'res.users':
        return normalize_res_users_write_values(values, env)
    return values


def user_add_group(user, group):
    """Add a direct group to the user if it is not there yet."""
    if not user_has_group_direct(user, group):
        user.write({USER_GROUPS_FIELD: [(4, group.id)]})


def user_remove_group(user, group):
    """Remove a direct group from the user."""
    if user_has_group_direct(user, group):
        user.write({USER_GROUPS_FIELD: [(3, group.id)]})


def search_users_with_group(env, group):
    """Users who have the group (direct or implied)."""
    return env['res.users'].sudo().search([(USER_ALL_GROUPS_FIELD, 'in', group.id)])


def get_odoo_admin_groups(env):
    """Odoo groups with Settings access."""
    group = env.ref('base.group_system', raise_if_not_found=False)
    return [group] if group else []


def user_is_odoo_admin(user, env):
    """True if the user has Settings (base.group_system)."""
    return any(user_has_group(user, group) for group in get_odoo_admin_groups(env))
