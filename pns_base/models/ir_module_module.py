# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Apps sheet: embed a module's own index page when its author asks for it.

A module opts in by pointing ``website`` in its own ``__manifest__.py`` at
``/<module>/static/description/index.html``. The sheet then embeds that page
below the Odoo chrome (Update / Uninstall). Every other module keeps Odoo's
standard description and the ``website`` its author wrote: nothing here
rewrites another vendor's data.
"""

from odoo import api, fields, models


def _local_index(module_name):
    return '/%s/static/description/index.html' % module_name


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    pns_index_url = fields.Char(
        compute='_compute_pns_index_url',
        string='Index',
        help='Local Apps index, when the module manifest points website at it.',
    )

    @api.depends('name', 'website')
    def _compute_pns_index_url(self):
        for rec in self:
            local = _local_index(rec.name) if rec.name else False
            rec.pns_index_url = local if local and rec.website == local else False
