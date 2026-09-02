# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.370: pin context_type labels to tokens; drop leftover columns."""
import logging

from odoo import api, SUPERUSER_ID
from odoo.tools import sql

_logger = logging.getLogger(__name__)

_TOKENS = ('core', 'domain', 'locale', 'discovery')


def _drop_column(cr, table, column):
    if sql.table_exists(cr, table) and sql.column_exists(cr, table, column):
        cr.execute('ALTER TABLE %s DROP COLUMN %s' % (table, column))
        _logger.info('pns_ai_mcp 3.1.370: dropped %s.%s', table, column)


def _pin_context_type_labels(env):
    Field = env['ir.model.fields']
    field = Field.search([
        ('model', '=', 'ai.context'),
        ('name', '=', 'context_type'),
    ], limit=1)
    if not field or 'ir.model.fields.selection' not in env:
        return
    rows = env['ir.model.fields.selection'].search([
        ('field_id', '=', field.id),
        ('value', 'in', list(_TOKENS)),
    ])
    for row in rows:
        if row.name != row.value:
            row.name = row.value
    if 'ir.translation' not in env:
        return
    Trans = env['ir.translation']
    stale = Trans.search([
        ('name', '=', 'ir.model.fields.selection,name'),
        ('res_id', 'in', rows.ids),
    ])
    if stale:
        stale.unlink()
    extra = Trans.search([
        ('module', '=', 'pns_ai_mcp'),
        ('type', '=', 'selection'),
        '|',
        ('name', 'ilike', '%context_type%'),
        ('name', 'ilike', '%selection__ai_context__context_type%'),
    ])
    if extra:
        extra.unlink()
    _logger.info(
        'pns_ai_mcp 3.1.370: pinned %s context_type selection labels',
        len(rows),
    )


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _pin_context_type_labels(env)
    _drop_column(cr, 'ai_agent', 'auto_link_mcp_nucleus')
    _drop_column(cr, 'ai_context', 'is_shared')
    _drop_column(cr, 'ai_skill', 'is_shared')
