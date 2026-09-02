# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Draft pick-list shown in Chatboo before the Safe Plan Confirm aviso."""
from odoo import api, fields, models


class AiSafeChoice(models.Model):
    _name = 'ai.safe.choice'
    _description = 'AI Safe Plan — view choice (before Confirm)'
    _order = 'id desc'

    choice_id = fields.Char(
        required=True, index=True, copy=False,
        default=lambda self: self._generate_choice_id(),
    )
    user_id = fields.Many2one(
        'res.users', required=True, ondelete='cascade', index=True,
        default=lambda self: self.env.user,
    )
    title = fields.Char()
    status = fields.Selection([
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ], default='pending', required=True, index=True)
    expires_at = fields.Datetime(index=True)
    payload = fields.Text(help='JSON: steps, items, title')

    _sql_constraints = [
        ('choice_id_uniq', 'unique(choice_id)',
         'A choice with this id already exists.'),
    ]

    @api.model
    def _generate_choice_id(self):
        seq = self.env['ir.sequence'].sudo().search([
            ('code', '=', 'pns_ai_mcp.safe_choice'),
        ], limit=1)
        if not seq:
            seq = self.env['ir.sequence'].sudo().create({
                'name': 'Safe Plan choice',
                'code': 'pns_ai_mcp.safe_choice',
                'implementation': 'standard',
                'prefix': 'CHC',
                'padding': 8,
            })
        return self.env['ir.sequence'].next_by_code('pns_ai_mcp.safe_choice') or 'CHC0000'
