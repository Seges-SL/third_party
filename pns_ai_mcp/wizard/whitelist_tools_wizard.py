# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from odoo import models


class UrlWhitelistToolsWizard(models.TransientModel):
    _name = 'pns_ai_mcp.whitelist.tools.wizard'
    _inherit = ['pns.export_import.tools.wizard.mixin']
    _description = 'Whitelist Tools'

    def action_export(self):
        return self.env['ai.url.whitelist'].action_export_whitelist()

    def action_import(self):
        return self.env['ai.url.whitelist'].action_import_whitelist()
