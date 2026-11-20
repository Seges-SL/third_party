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
    binary_bytes,
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


def read_sums(model, domain, field_names):
    """Sum of each numeric field over the records in ``domain``, as a dict.

    Odoo 17+ has ``_read_group(domain, groupby, aggregates)`` returning tuples
    (in 20 the public ``read_group`` is that one too). Up to 16 the public
    ``read_group(domain, fields, groupby)`` returns dicts.
    """
    if ODOO_VERSION >= 17:
        rows = model._read_group(domain, [], ['%s:sum' % name for name in field_names])
        values = rows[0] if rows else ()
        return {name: value or 0 for name, value in zip(field_names, values)}
    rows = model.read_group(domain, list(field_names), [])
    row = rows[0] if rows else {}
    return {name: row.get(name) or 0 for name in field_names}


def test_is_running(env):
    """True while an Odoo test runs (O14 marks the thread, O19 the module).

    A short side cursor that commits must not run then: it cannot see the
    test's uncommitted rows, can wait on its locks, and a row it commits
    breaks the class transaction's later write (PG 40001).
    ``--test-enable`` alone stays True for the whole server life.
    """
    import threading
    from odoo.modules import module as odoo_module
    from odoo.tools import config
    return bool(
        (config['test_enable'] and type(env.cr).__name__ == 'TestCursor')
        or getattr(threading.current_thread(), 'testing', False)
        or getattr(odoo_module, 'current_test', False)
    )



def load_odoo14_assets_if_needed(env):
    """
    Load the assets XML dynamically on Odoo <= 14 during initialization.
    On Odoo 15+ the assets are loaded from __manifest__.py.
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
