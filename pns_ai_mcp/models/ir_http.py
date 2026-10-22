# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Session flag so the PIN desk JS only boots for AI Administrator."""

from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        info = super().session_info()
        user = request.env.user
        info['pns_is_ai_admin'] = bool(
            user and user.has_group('pns_ai_mcp.group_ai_admin')
        )
        return info
