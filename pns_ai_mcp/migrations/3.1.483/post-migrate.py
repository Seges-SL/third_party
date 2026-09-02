# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.483: leftover empty groups on Security → Changes (writers saw the menu)."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    admin = env.ref('pns_ai_mcp.group_ai_admin', raise_if_not_found=False)
    if not admin:
        return
    menu = env.ref('pns_ai_mcp.menu_mcp_change_journal', raise_if_not_found=False)
    if not menu or 'groups_id' not in menu._fields:
        return
    imd = env['ir.model.data'].search([
        ('module', '=', 'pns_ai_mcp'),
        ('name', '=', 'menu_mcp_change_journal'),
    ], limit=1)
    if imd and imd.noupdate:
        imd.noupdate = False
    menu.write({'groups_id': [(6, 0, [admin.id])]})
    _logger.info('pns_ai_mcp 3.1.483: Changes menu groups=AI admin')
