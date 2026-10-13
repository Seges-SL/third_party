# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Odoo's own export (Action → Export) never carries a declared secret.

That dialog cannot ask whether secrets go in the file, so a column that ends
in a field its model lists in ``_pns_secret_fields`` comes out empty, also
when reached through a relation. The portable exports (⚙️ Tools) ask.
"""

from odoo import models


def names_a_secret(model, path):
    """True when the export *path* (``a/b/c``) lands on a declared secret."""
    for name in (path or '').split('/'):
        field = model._fields.get(name)
        if field is None:
            return False
        if name in (getattr(model, '_pns_secret_fields', ()) or ()):
            return True
        if not field.relational:
            return False
        model = model.env[field.comodel_name]
    return False


class Base(models.AbstractModel):
    _inherit = 'base'

    def export_data(self, fields_to_export):
        result = super().export_data(fields_to_export)
        hidden = [
            i for i, path in enumerate(fields_to_export or [])
            if names_a_secret(self, path)
        ]
        if hidden:
            for row in result.get('datas') or []:
                for i in hidden:
                    if i < len(row):
                        row[i] = ''
        return result
