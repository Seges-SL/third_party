# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.518: rename leftover mcp_ xmlids on the safe.operation family.

Must run before XML load. Changing id= in XML without this creates
duplicate menus/actions/rules and leaves the old rows.
"""
import logging

_logger = logging.getLogger(__name__)

_XMLID_RENAMES = (
    ('mcp_safe_operation_user_rule', 'ai_safe_operation_user_rule'),
    ('mcp_safe_operation_admin_rule', 'ai_safe_operation_admin_rule'),
    ('menu_mcp_safe_operation', 'menu_ai_safe_operation'),
    ('menu_mcp_safe_operation_admin', 'menu_ai_safe_operation_admin'),
    ('action_mcp_safe_operation', 'action_ai_safe_operation'),
    ('action_mcp_safe_operation_admin', 'action_ai_safe_operation_admin'),
    ('view_mcp_safe_operation_search', 'view_ai_safe_operation_search'),
    ('view_mcp_safe_operation_tree', 'view_ai_safe_operation_tree'),
    ('view_mcp_safe_operation_form', 'view_ai_safe_operation_form'),
    ('access_mcp_safe_operation_user', 'access_ai_safe_operation_user'),
    ('access_mcp_safe_operation_admin', 'access_ai_safe_operation_admin'),
)


def _rename_xmlid(cr, old, new):
    cr.execute(
        """
        SELECT id FROM ir_model_data
         WHERE module = 'pns_ai_mcp' AND name = %s
        """,
        (new,),
    )
    if cr.fetchone():
        _logger.info('3.1.518: xmlid %s already present', new)
        return
    cr.execute(
        """
        UPDATE ir_model_data
           SET name = %s
         WHERE module = 'pns_ai_mcp' AND name = %s
        """,
        (new, old),
    )
    if cr.rowcount:
        _logger.info('3.1.518: xmlid %s → %s', old, new)


def migrate(cr, version):
    for old, new in _XMLID_RENAMES:
        try:
            _rename_xmlid(cr, old, new)
        except Exception:
            _logger.info('3.1.518: skip xmlid %s', old, exc_info=True)
