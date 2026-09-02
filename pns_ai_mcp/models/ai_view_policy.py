# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ai.view.policy — which ``ir.ui.view`` inherit an AI system action created.

Persistence for reset and for the change-journal JSON. No business literals.
"""
from odoo import fields, models


class AiViewPolicy(models.Model):
    _name = 'ai.view.policy'
    _description = 'AI View Modifier Policy'
    _order = 'model_name, field_name, modifier, view_id'

    model_name = fields.Char(required=True, index=True)
    field_name = fields.Char(required=True, index=True)
    modifier = fields.Selection([
        ('required', 'Required'),
        ('readonly', 'Readonly'),
        ('invisible', 'Invisible'),
        ('domain', 'Domain'),
    ], required=True, index=True)
    value = fields.Char(
        help="Stored flag ('1'/'0') or domain Python-literal.",
    )
    view_id = fields.Many2one(
        'ir.ui.view', required=True, ondelete='cascade',
        help="Primary (or chosen) view the inherit extends.",
    )
    inherit_view_id = fields.Many2one(
        'ir.ui.view', required=True, ondelete='cascade',
        help="Extension view created by the trusted action.",
    )

    _sql_constraints = [
        ('policy_uniq',
         'unique(model_name, field_name, modifier, view_id)',
         'A view-modifier policy already exists for this field and view.'),
    ]

    def unlink(self):
        inherits = self.mapped('inherit_view_id')
        xmlids = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'pns_ai_mcp'),
            ('model', '=', 'ir.ui.view'),
            ('res_id', 'in', inherits.ids),
        ])
        res = super(AiViewPolicy, self).unlink()
        xmlids.unlink()
        inherits.sudo().unlink()
        return res
