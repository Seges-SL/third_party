# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.425: copy origin filter injected → pinned."""
from odoo.tools import sql


def migrate(cr, version):
    if not sql.table_exists(cr, 'ai_agent'):
        return
    if not sql.column_exists(cr, 'ai_agent', 'link_show_pinned'):
        return
    if sql.column_exists(cr, 'ai_agent', 'link_show_injected'):
        cr.execute("""
            UPDATE ai_agent
               SET link_show_pinned = COALESCE(link_show_injected, TRUE)
        """)
        return
    cr.execute('UPDATE ai_agent SET link_show_pinned = TRUE')
