# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from odoo import models


class AiProviderToolsWizard(models.TransientModel):
    _name = 'pns_ai_mcp.provider.tools.wizard'
    _inherit = ['pns.export_import.tools.wizard.mixin']
    _description = 'Providers Tools'

    def action_export(self):
        return self.env['ai.provider'].action_export_providers()

    def action_import(self):
        return self.env['ai.provider'].action_import_providers()
