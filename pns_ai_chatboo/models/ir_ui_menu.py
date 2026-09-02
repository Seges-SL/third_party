# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Hide the Chatboo app icon unless the user has an MCP API key carnet."""

from odoo import api, models

from ..utils.chatboo_access import user_has_chatboo_access

_CHATBOO_APP_MENU_XMLIDS = (
    'pns_ai_chatboo.menu_chatboo_root',
)


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _chatboo_menu_ids(self):
        ids = set()
        for xmlid in _CHATBOO_APP_MENU_XMLIDS:
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu:
                ids.add(menu.id)
        return ids

    @api.model
    def _visible_menu_ids(self, debug=False):
        visible = super()._visible_menu_ids(debug=debug)
        if user_has_chatboo_access(self.env):
            return visible
        hide_ids = self._chatboo_menu_ids()
        if not hide_ids:
            return visible
        if isinstance(visible, (list, tuple)):
            return [mid for mid in visible if mid not in hide_ids]
        return visible - hide_ids
