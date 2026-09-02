# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Security → Changes stays hidden from writers when menu groups were left empty."""
from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.tests._helpers import (
    _clear_registry_caches,
    create_test_user,
)


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestChangeJournalMenu(TransactionCase):

    def test_writer_does_not_see_changes_menu_if_groups_empty(self):
        menu = self.env.ref('pns_ai_mcp.menu_mcp_change_journal')
        field = 'group_ids' if 'group_ids' in menu._fields else 'groups_id'
        menu.sudo().write({field: [(5, 0, 0)]})
        _clear_registry_caches(self.env.registry)

        writer = create_test_user(
            self.env,
            prefix='pns_chg_writer',
            groups=[
                self.env.ref('base.group_user').id,
                self.env.ref('pns_ai_mcp.group_ai_writer').id,
            ],
        )
        visible = self.env['ir.ui.menu'].with_user(writer)._visible_menu_ids()
        self.assertNotIn(menu.id, visible)

        admin = create_test_user(
            self.env,
            prefix='pns_chg_admin',
            groups=[
                self.env.ref('base.group_user').id,
                self.env.ref('pns_ai_mcp.group_ai_admin').id,
            ],
        )
        visible_admin = self.env['ir.ui.menu'].with_user(admin)._visible_menu_ids()
        self.assertIn(menu.id, visible_admin)
