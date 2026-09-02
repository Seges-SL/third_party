# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""AI Engine menu visibility: hide operator-only menus from AI administrators.

The AI Engine app icon follows XML ``groups_id`` (IA groups), not the MCP API
key carnet. The carnet gates Chatboo. Forcing the app root into the drawer for
key holders without IA groups yields an empty root and crashes Odoo 14
AppsMenu (``action.split`` on ``false``).
"""

from odoo import api, models

_OPERATOR_MENU_XMLIDS = (
    'pns_ai_mcp.menu_mcp_contexts_writer',
    'pns_ai_mcp.menu_ai_skill_writer',
    'pns_ai_mcp.menu_mcp_safe_operation',
    'pns_ai_mcp.menu_mcp_logs',
)

# Security → Changes is AI admin only. XML already says so; this hides the
# item when ir.ui.menu.groups_id was left empty (Odoo 19 dropped groups_id
# on the window action, so a leftover empty menu group became visible).
_ADMIN_ONLY_MENU_XMLIDS = (
    'pns_ai_mcp.menu_mcp_change_journal',
)


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _menu_ids_for_xmlids(self, xmlids):
        ids = set()
        for xmlid in xmlids:
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu:
                ids.add(menu.id)
        return ids

    @api.model
    def _without_menu_ids(self, visible, hide_ids):
        if not hide_ids:
            return visible
        if isinstance(visible, (list, tuple)):
            return [mid for mid in visible if mid not in hide_ids]
        return visible - hide_ids

    @api.model
    def _visible_menu_ids(self, debug=False):
        visible = super()._visible_menu_ids(debug=debug)

        if not self.env.user.has_group('pns_ai_mcp.group_ai_admin'):
            return self._without_menu_ids(
                visible, self._menu_ids_for_xmlids(_ADMIN_ONLY_MENU_XMLIDS),
            )

        return self._without_menu_ids(
            visible, self._menu_ids_for_xmlids(_OPERATOR_MENU_XMLIDS),
        )
