# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.424: origin filter checkboxes default on for existing agents."""
from odoo.tools import sql

_COLS = (
    'link_show_native',
    'link_show_imported',
    'link_show_injected',
    'link_show_extra',
)


def migrate(cr, version):
    if not sql.table_exists(cr, 'ai_agent'):
        return
    present = [col for col in _COLS if sql.column_exists(cr, 'ai_agent', col)]
    if not present:
        return
    sets = ', '.join('%s = TRUE' % col for col in present)
    cr.execute('UPDATE ai_agent SET %s' % sets)
