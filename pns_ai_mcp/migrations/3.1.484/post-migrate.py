# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.484: write Changes menu groups on the field Odoo actually has."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    admin = env.ref('pns_ai_mcp.group_ai_admin', raise_if_not_found=False)
    if not admin:
        return
    menu = env.ref('pns_ai_mcp.menu_mcp_change_journal', raise_if_not_found=False)
    if not menu:
        return
    field = 'group_ids' if 'group_ids' in menu._fields else (
        'groups_id' if 'groups_id' in menu._fields else None
    )
    if not field:
        return
    menu.write({field: [(6, 0, [admin.id])]})
    _logger.info('pns_ai_mcp 3.1.484: Changes menu %s=AI admin', field)
