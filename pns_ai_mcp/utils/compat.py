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
