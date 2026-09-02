# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from odoo import models


class ExternalServerToolsWizard(models.TransientModel):
    _name = 'pns_ai_mcp.external_server.tools.wizard'
    _inherit = ['pns.export_import.tools.wizard.mixin']
    _description = 'External Servers Tools'

    def action_export(self):
        return self.env['ai.api.server'].action_export_external_servers()

    def action_import(self):
        return self.env['ai.api.server'].action_import_external_servers()
