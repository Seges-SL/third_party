# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Per-user Chatboo UI prefs (card width follows the login, any browser)."""
from odoo import api, fields, models


def normalize_card_width_ratio(value):
    """0 = client default (two thirds). Else clamp to (0, 1]."""
    if value in (None, False, '', 0, 0.0):
        return 0.0
    try:
        ratio = float(value)
    except (TypeError, ValueError):
        return 0.0
    if ratio <= 0:
        return 0.0
    return min(1.0, ratio)


class ResUsers(models.Model):
    _inherit = 'res.users'

    chatboo_card_width_ratio = fields.Float(
        string='Chatboo card width',
        default=0.0,
        help='0 = default (two thirds of the chat canvas). Else 0–1 of that canvas.',
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['chatboo_card_width_ratio']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['chatboo_card_width_ratio']

    def chatboo_card_width_ratio_value(self):
        self.ensure_one()
        return normalize_card_width_ratio(self.chatboo_card_width_ratio)

    @api.model
    def chatboo_set_own_card_width_ratio(self, value):
        """Write only the current user's card width. Never another uid."""
        ratio = normalize_card_width_ratio(value)
        user = self.env.user
        user.sudo().write({'chatboo_card_width_ratio': ratio})
        return ratio
