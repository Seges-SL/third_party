# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.431: drop leftover Link origin labels (Odoo keeps the old field msgstr)."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _table_exists(cr, table):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = %s
        """,
        (table,),
    )
    return bool(cr.fetchone())


def _column_udt(cr, table, column):
    cr.execute(
        """
        SELECT udt_name
          FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = %s
           AND column_name = %s
        """,
        (table, column),
    )
    row = cr.fetchone()
    return (row[0] or '').lower() if row else ''


def _wipe_varchar_label(cr):
    cr.execute(
        """
        UPDATE ir_model_fields
           SET field_description = 'Origin'
         WHERE name = 'composition_origin'
           AND model IN ('ai.context', 'ai.skill')
           AND field_description IS DISTINCT FROM 'Origin'
        """
    )


def _wipe_json_label(cr):
    # Odoo 17+ stores translated Char as jsonb. Comparing to the text
    # 'Origin' raises InvalidTextRepresentation and aborts the upgrade.
    cr.execute(
        """
        UPDATE ir_model_fields
           SET field_description = jsonb_set(
                 COALESCE(field_description::jsonb, '{}'::jsonb),
                 '{en_US}',
                 to_jsonb('Origin'::text)
               )
         WHERE name = 'composition_origin'
           AND model IN ('ai.context', 'ai.skill')
           AND COALESCE(field_description::jsonb->>'en_US', '')
               IS DISTINCT FROM 'Origin'
        """
    )


def _active_lang_codes(env):
    Lang = env['res.lang']
    getter = getattr(Lang, 'get_installed', None)
    if getter:
        return {code for code, _name in getter()}
    return set(Lang.search([('active', '=', True)]).mapped('code'))


def _update_active_translations(record, field_name, wanted):
    updater = getattr(record, 'update_field_translations', None)
    if not updater:
        return
    installed = _active_lang_codes(record.env)
    payload = {
        code: text for code, text in wanted.items() if code in installed
    }
    if payload:
        updater(field_name, payload)


def migrate(cr, version):
    udt = _column_udt(cr, 'ir_model_fields', 'field_description')
    if udt in ('json', 'jsonb'):
        _wipe_json_label(cr)
    else:
        _wipe_varchar_label(cr)
    if _table_exists(cr, 'ir_translation'):
        cr.execute(
            """
            DELETE FROM ir_translation
             WHERE src = 'Link origin'
               AND (
                    name ILIKE %s
                 OR name ILIKE %s
               )
            """,
            ('%composition_origin%', '%field_ai_%__composition_origin%'),
        )
        _logger.info(
            'pns_ai_mcp 3.1.431: dropped leftover Link origin translations',
        )
    env = api.Environment(cr, SUPERUSER_ID, {})
    Field = env['ir.model.fields']
    recs = Field.search([
        ('model', 'in', ['ai.context', 'ai.skill']),
        ('name', '=', 'composition_origin'),
    ])
    for rec in recs:
        if rec.field_description != 'Origin':
            rec.field_description = 'Origin'
        _update_active_translations(
            rec, 'field_description', {'es_ES': 'Origen', 'es': 'Origen'},
        )
