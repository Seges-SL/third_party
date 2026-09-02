# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Harden language/PO import against CardinalityViolation (Odoo 13–15).

When updating a language with overwrite, Odoo 14 inserts ``type='code'``
rows with::

    ON CONFLICT (type, lang, md5(src)) DO UPDATE ...

If a single ``.po`` yields two code rows with the same English ``src``,
PostgreSQL raises::

    ON CONFLICT DO UPDATE command cannot affect row a second time

Dedupe happens on the in-memory ``_rows`` buffer *before* stock ``finish()``
loads the temp table (SQL dedupe on an empty temp table was a no-op).
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# push() tuple layout in IrTranslationImport (Odoo 14):
# (name, lang, res_id, src, type, imd_model, module, imd_name, value, state, comments)
_IDX_NAME = 0
_IDX_LANG = 1
_IDX_SRC = 3
_IDX_TYPE = 4
_IDX_MODULE = 6
_IDX_IMD_NAME = 7


class IrTranslation(models.Model):
    _inherit = 'ir.translation'

    @api.model
    def _get_import_cursor(self, overwrite=False):
        cursor = super(IrTranslation, self)._get_import_cursor(overwrite=overwrite)
        if not overwrite:
            return cursor
        orig_finish = cursor.finish

        def finish_with_dedupe():
            self._pns_dedupe_import_rows(cursor)
            return orig_finish()

        cursor.finish = finish_with_dedupe
        return cursor

    @api.model
    def _pns_dedupe_import_rows(self, cursor):
        """Drop duplicate pending rows that would break ON CONFLICT DO UPDATE."""
        rows = getattr(cursor, '_rows', None)
        if not rows:
            return

        def conflict_key(row):
            typ = row[_IDX_TYPE]
            lang = row[_IDX_LANG]
            src = row[_IDX_SRC]
            name = row[_IDX_NAME]
            if typ == 'code':
                # ON CONFLICT (type, lang, md5(src))
                return ('code', lang, src)
            if typ == 'model':
                # res_id still unresolved → xmlid identity
                return (
                    'model',
                    lang,
                    name,
                    row[_IDX_MODULE],
                    row[_IDX_IMD_NAME],
                )
            if typ == 'model_terms':
                return (
                    'model_terms',
                    lang,
                    name,
                    row[_IDX_MODULE],
                    row[_IDX_IMD_NAME],
                    src,
                )
            return ('other', id(row))

        seen = {}
        kept = []
        dropped = 0
        for row in rows:
            key = conflict_key(row)
            if key in seen:
                dropped += 1
                prev = kept[seen[key]]
                _logger.warning(
                    "pns_base: language import drop duplicate %s src=%r "
                    "module=%s name=%s (keeping later; was module=%s name=%s)",
                    key[0],
                    (row[_IDX_SRC] or '')[:160],
                    row[_IDX_MODULE],
                    row[_IDX_NAME],
                    prev[_IDX_MODULE],
                    prev[_IDX_NAME],
                )
                kept[seen[key]] = row
                continue
            seen[key] = len(kept)
            kept.append(row)

        if dropped:
            cursor._rows = kept
            _logger.warning(
                "pns_base: removed %s duplicate translation row(s) before import "
                "(%s → %s)",
                dropped,
                len(rows),
                len(kept),
            )
