# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""get_param / set_param on Odoo 20, which only has typed getters and setters.

Source code always calls get_param(key, default) and set_param(key, value).
On 20 they go through get_str / set_str and answer as before: get_param
gives the stored text, or ``default`` when it is missing or empty;
set_param stores the text (False or None empties it) and gives the old
value, or False. Below 20 nothing here is defined.
"""

from odoo import api, models

from ..utils.compat import ODOO_VERSION
from ..utils.version_gates import applies_typed_params

if applies_typed_params(ODOO_VERSION):

    class IrConfigParameter(models.Model):
        _inherit = 'ir.config_parameter'

        @api.model
        def get_param(self, key, default=False):
            return self.get_str(key, None) or default

        @api.model
        def set_param(self, key, value):
            return self.set_str(key, value) or False
