# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.519: xmlids of ai.log / ai.context / ai.change.journal follow _name.

Must run before XML load. Changing id= in XML without this creates
duplicate menus/actions/rules and leaves the old rows.
"""
import logging

_logger = logging.getLogger(__name__)

_XMLID_RENAMES = (
    ('mcp_log_user_rule', 'ai_log_user_rule'),
    ('mcp_log_admin_rule', 'ai_log_admin_rule'),
    ('menu_mcp_logs', 'menu_ai_log'),
    ('menu_mcp_logs_admin', 'menu_ai_log_admin'),
    ('action_mcp_logs', 'action_ai_log'),
    ('action_mcp_logs_technical', 'action_ai_log_technical'),
    ('action_mcp_logs_delete_menu_window', 'action_ai_log_delete_menu_window'),
    ('view_mcp_log_tree_simple', 'view_ai_log_tree_simple'),
    ('view_mcp_log_tree', 'view_ai_log_tree'),
    ('view_mcp_log_form', 'view_ai_log_form'),
    ('view_mcp_log_search', 'view_ai_log_search'),
    ('access_mcp_log_user', 'access_ai_log_user'),
    ('access_mcp_log_admin', 'access_ai_log_admin'),
    ('menu_mcp_contexts', 'menu_ai_context'),
    ('menu_mcp_contexts_writer', 'menu_ai_context_writer'),
    ('action_mcp_contexts', 'action_ai_context'),
    ('action_mcp_contexts_writer', 'action_ai_context_writer'),
    ('view_mcp_context_tree', 'view_ai_context_tree'),
    ('view_mcp_context_search', 'view_ai_context_search'),
    ('view_mcp_context_form', 'view_ai_context_form'),
    ('access_mcp_context_user', 'access_ai_context_user'),
    ('access_mcp_context_writer', 'access_ai_context_writer'),
    ('menu_mcp_change_journal', 'menu_ai_change_journal'),
    ('action_mcp_change_journal', 'action_ai_change_journal'),
    ('view_mcp_change_journal_search', 'view_ai_change_journal_search'),
    ('view_mcp_change_journal_tree', 'view_ai_change_journal_tree'),
    ('view_mcp_change_journal_form', 'view_ai_change_journal_form'),
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
        _logger.info('3.1.519: xmlid %s already present', new)
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
        _logger.info('3.1.519: xmlid %s → %s', old, new)


def migrate(cr, version):
    for old, new in _XMLID_RENAMES:
        try:
            _rename_xmlid(cr, old, new)
        except Exception:
            _logger.info('3.1.519: skip xmlid %s', old, exc_info=True)
