# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""v3.1.136: rename ai.geo.cache→ai.geo.place and ai.geo.distance.cache→ai.geo.route.

Runs before the ORM loads the new _name so data is not left in orphan tables.

Also purges / renames Selection xmlids: Odoo 14 `_process_ondelete` KeyErrors
when orphan `ir.model.fields.selection` rows still point at a model no longer
in the registry (known upstream bug; fixed only from 15+).
"""

import logging

_logger = logging.getLogger(__name__)


def _table_exists(cr, name):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
         WHERE table_name = %s AND table_schema = 'public'
        """,
        (name,),
    )
    return bool(cr.fetchone())


def _rename_table(cr, old, new):
    if _table_exists(cr, old) and not _table_exists(cr, new):
        cr.execute('ALTER TABLE "%s" RENAME TO "%s"' % (old, new))
        _logger.info('MCP 3.1.136: renamed table %s → %s', old, new)
    elif _table_exists(cr, new):
        _logger.info('MCP 3.1.136: table %s already present', new)
    else:
        _logger.info('MCP 3.1.136: table %s not found (fresh install?)', old)


def _purge_selection_metadata(cr, model_name):
    """Delete selection rows + xmlids for *model_name* via SQL (no ORM).

    Must run before `_process_end` tries to unlink them through the ORM.
    """
    cr.execute(
        """
        WITH ids AS (
            DELETE FROM ir_model_fields_selection irms
             USING ir_model_fields imf
             WHERE imf.id = irms.field_id
               AND imf.model = %s
            RETURNING irms.id
        )
        DELETE FROM ir_model_data
         WHERE model = 'ir.model.fields.selection'
           AND res_id IN (SELECT id FROM ids)
        """,
        (model_name,),
    )
    table = model_name.replace('.', '_')
    cr.execute(
        """
        DELETE FROM ir_model_fields_selection
         WHERE id IN (
            SELECT res_id FROM ir_model_data
             WHERE module = 'pns_ai_mcp'
               AND model = 'ir.model.fields.selection'
               AND name LIKE %s
         )
        """,
        ('selection__%s__%%' % table,),
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'pns_ai_mcp'
           AND model = 'ir.model.fields.selection'
           AND name LIKE %s
        """,
        ('selection__%s__%%' % table,),
    )
    _logger.info('MCP 3.1.136: purged selection metadata for %s', model_name)


def _rename_xmlid_prefix(cr, old_prefix, new_prefix):
    """Rename auto field/selection xmlids: field_* / selection__* prefixes."""
    cr.execute(
        """
        UPDATE ir_model_data
           SET name = replace(name, %s, %s)
         WHERE module = 'pns_ai_mcp'
           AND name LIKE %s
           AND NOT EXISTS (
                SELECT 1 FROM ir_model_data d2
                 WHERE d2.module = 'pns_ai_mcp'
                   AND d2.name = replace(ir_model_data.name, %s, %s)
           )
        """,
        (old_prefix, new_prefix, old_prefix + '%', old_prefix, new_prefix),
    )


def _rename_model(cr, old_model, new_model, old_xmlid, new_xmlid):
    # Purge selections first while field.model still equals old_model (or
    # leftover xmlids use the old table prefix). Recreated on next load.
    _purge_selection_metadata(cr, old_model)

    old_table = old_model.replace('.', '_')
    new_table = new_model.replace('.', '_')
    _rename_xmlid_prefix(cr, 'field_%s__' % old_table, 'field_%s__' % new_table)
    _rename_xmlid_prefix(
        cr, 'selection__%s__' % old_table, 'selection__%s__' % new_table,
    )

    cr.execute(
        "UPDATE ir_model SET model = %s WHERE model = %s",
        (new_model, old_model),
    )
    # ir.model.data xmlid for the model record
    cr.execute(
        """
        UPDATE ir_model_data
           SET name = %s
         WHERE module = 'pns_ai_mcp'
           AND model = 'ir.model'
           AND name = %s
        """,
        (new_xmlid, old_xmlid),
    )
    # Fields / access / rules store the model name as text in some tables
    for table, column in (
        ('ir_model_fields', 'model'),
        ('ir_model_access', None),  # via model_id FK — no text
        ('ir_rule', 'model_id'),  # FK
    ):
        if column == 'model':
            cr.execute(
                "UPDATE %s SET model = %%s WHERE model = %%s" % table,
                (new_model, old_model),
            )
    # ir_model_data entries that reference the old model name in `model` column
    # (records of the renamed model themselves)
    cr.execute(
        """
        UPDATE ir_model_data
           SET model = %s
         WHERE module = 'pns_ai_mcp'
           AND model = %s
        """,
        (new_model, old_model),
    )
    _logger.info('MCP 3.1.136: model %s → %s', old_model, new_model)


def migrate(cr, version):
    _rename_table(cr, 'ai_geo_cache', 'ai_geo_place')
    _rename_table(cr, 'ai_geo_distance_cache', 'ai_geo_route')
    _rename_model(
        cr,
        'ai.geo.cache', 'ai.geo.place',
        'model_ai_geo_cache', 'model_ai_geo_place',
    )
    _rename_model(
        cr,
        'ai.geo.distance.cache', 'ai.geo.route',
        'model_ai_geo_distance_cache', 'model_ai_geo_route',
    )
    # Access rights csv ids may still point at old xmlids until module update;
    # update ir_model_data for access lines if present under old names.
    for old_name, new_name in (
        ('access_ai_geo_cache_user', 'access_ai_geo_place_user'),
        ('access_ai_geo_cache_admin', 'access_ai_geo_place_admin'),
        ('access_ai_geo_distance_cache_user', 'access_ai_geo_route_user'),
        ('access_ai_geo_distance_cache_admin', 'access_ai_geo_route_admin'),
    ):
        cr.execute(
            """
            UPDATE ir_model_data
               SET name = %s
             WHERE module = 'pns_ai_mcp'
               AND name = %s
            """,
            (new_name, old_name),
        )
