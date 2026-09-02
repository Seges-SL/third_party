# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Compatibility facade for pns_ai_mcp."""

from odoo.addons.pns_base.utils.compat import (  # noqa: F401
    ODOO_VERSION,
    JSON_ROUTE_TYPE,
    NEEDS_ROOT_GET_REQUEST_PATCH,
    USER_GROUPS_FIELD,
    USER_ALL_GROUPS_FIELD,
    locale_field_separator,
    format_login_name_line,
    invalidate_recordset_fields,
    user_has_group,
    user_has_group_direct,
    user_add_group,
    user_remove_group,
    search_users_with_group,
    get_odoo_admin_groups,
    user_is_odoo_admin,
)


def grant_mcp_manager_to_odoo_admins(env, users=None):
    """Asigna MCP Administrator a usuarios con Ajustes que aún no lo tengan."""
    mcp_group = env.ref('pns_ai_mcp.group_ai_admin', raise_if_not_found=False)
    admin_groups = get_odoo_admin_groups(env)
    if not mcp_group or not admin_groups:
        return 0

    if users is None:
        domain = ['|'] * max(0, len(admin_groups) - 1)
        for group in admin_groups:
            domain.append((USER_ALL_GROUPS_FIELD, 'in', group.id))
        users = env['res.users'].sudo().search(domain)

    added = 0
    for user in users:
        if not user_is_odoo_admin(user, env):
            continue
        if not user_has_group_direct(user, mcp_group):
            user_add_group(user, mcp_group)
            added += 1
    return added


def load_odoo14_assets_if_needed(env):
    """
    Carga el XML de assets en Odoo <= 14 de forma dinámica durante la inicialización.
    En Odoo 15+ los assets se cargan desde el __manifest__.py.
    """
    if ODOO_VERSION > 14:
        return

    import logging
    import inspect
    from odoo.tools import convert_file

    _logger = logging.getLogger(__name__)
    try:
        _logger.info("MCP: Loading assets.xml dynamically for Odoo 14 compatibility")

        # Auto-detect whether convert_file wants `env` or `cr` as first parameter
        sig = inspect.signature(convert_file)
        first_param = list(sig.parameters.keys())[0]
        env_or_cr = env if first_param == 'env' else env.cr

        convert_file(env_or_cr, 'pns_ai_mcp', 'views/assets.xml', {}, mode='update', noupdate=False, kind='data')
    except Exception as e:
        _logger.error("MCP: Error loading assets.xml dynamically: %s", str(e), exc_info=True)
