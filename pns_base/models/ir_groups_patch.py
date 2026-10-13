# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Load-time rewrite of res.groups XML (category_id → privilege on Odoo 19).

Source XML is always the old form: category_id + users. On 19 this patch
creates or reuses res.groups.privilege for that category and sets
privilege_id. On 17/18 the vals stay native.
"""

from odoo import models, api

from ..utils.compat import ODOO_VERSION
from ..utils.version_gates import applies_group_privilege, rewrite_group_vals


def _category_id_value(raw):
    """Unwrap a category id from XML/ORM vals (int, browse, or NewId)."""
    if raw is False or raw is None:
        return None
    if isinstance(raw, models.BaseModel):
        return raw.id if raw else None
    return raw


def _privilege_id_for_category(env, category_id):
    """Find or create the privilege row for an ir.module.category id."""
    Privilege = env['res.groups.privilege'].sudo()
    existing = Privilege.search([('category_id', '=', category_id)], limit=1)
    if existing:
        return existing.id
    category = env['ir.module.category'].browse(category_id)
    name = category.name if category.exists() else 'PNS'
    return Privilege.create({
        'name': name,
        'category_id': category_id,
    }).id


class ResGroups(models.Model):
    _inherit = 'res.groups'

    def _pns_rewrite_group_vals(self, vals):
        """Mutate res.groups vals for the running Odoo major."""
        if not isinstance(vals, dict) or not vals:
            return
        privilege_id = None
        if applies_group_privilege(ODOO_VERSION) and 'category_id' in vals:
            category_id = _category_id_value(vals.get('category_id'))
            if category_id:
                privilege_id = _privilege_id_for_category(self.env, category_id)
        rewrite_group_vals(vals, ODOO_VERSION, self._fields, privilege_id=privilege_id)

    @api.model
    def _load_records(self, data_list, update=False):
        for data in data_list:
            self._pns_rewrite_group_vals(data.get('values', {}))
        return super(ResGroups, self)._load_records(data_list, update)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._pns_rewrite_group_vals(vals)
        return super(ResGroups, self).create(vals_list)

    def write(self, vals):
        self._pns_rewrite_group_vals(vals)
        return super(ResGroups, self).write(vals)
