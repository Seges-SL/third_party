# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.434: origin tokens stay English; overwrite leftover Native→Nativo."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_TOKENS = ('native', 'imported', 'pinned', 'extra')
_OLD_LABELS = ('Native', 'Imported', 'Pinned', 'Added', 'Injected')


def _table_exists(cr, table):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = %s
        """,
        (table,),
    )
    return bool(cr.fetchone())


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
    if _table_exists(cr, 'ir_translation'):
        cr.execute(
            """
            UPDATE ir_translation
               SET value = src
             WHERE module = 'pns_ai_mcp'
               AND src IN %s
               AND value IS DISTINCT FROM src
            """,
            (_TOKENS,),
        )
        cr.execute(
            """
            DELETE FROM ir_translation
             WHERE module = 'pns_ai_mcp'
               AND src IN %s
            """,
            (_OLD_LABELS,),
        )
        _logger.info(
            'pns_ai_mcp 3.1.434: reset token translations (%s leftover srcs)',
            _TOKENS,
        )
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ir.model.fields.selection' in env:
        sels = env['ir.model.fields.selection'].search([
            ('field_id.model', 'in', ['ai.context', 'ai.skill']),
            ('field_id.name', '=', 'composition_origin'),
            ('value', 'in', list(_TOKENS)),
        ])
        for sel in sels:
            if sel.name != sel.value:
                sel.name = sel.value
            _update_active_translations(
                sel, 'name', {'es_ES': sel.value, 'es': sel.value},
            )
    module = env['ir.module.module'].search(
        [('name', '=', 'pns_ai_mcp')], limit=1,
    )
    if not module:
        return
    try:
        module._update_translations(overwrite=True)
        _logger.info(
            'pns_ai_mcp 3.1.434: module translations reloaded (overwrite=True)',
        )
    except Exception:
        _logger.warning(
            'pns_ai_mcp 3.1.434: translation overwrite failed',
            exc_info=True,
        )
