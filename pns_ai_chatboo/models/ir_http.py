# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Systray visibility at login, so the backend does not call check_health."""

from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        info = super().session_info()
        from ..utils.chatboo_access import user_has_chatboo_access
        from ..utils.chatboo_product_icp import read_product_settings
        show = False
        allow_remote = False
        try:
            env = request.env
            if user_has_chatboo_access(env):
                product = read_product_settings(env)
                show = bool(product.get('show_systray', True))
                allow_remote = bool(product.get('allow_remote_voices'))
        except Exception:
            show = False
            allow_remote = False
        info['pns_chatboo_show_systray'] = show
        info['pns_chatboo_allow_remote_voices'] = allow_remote
        return info
