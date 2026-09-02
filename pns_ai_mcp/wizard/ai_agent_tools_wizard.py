# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from odoo import models


class AiAgentToolsWizard(models.TransientModel):
    _name = 'pns_ai_mcp.agent.tools.wizard'
    _inherit = ['pns.export_import.tools.wizard.mixin']
    _description = 'Agents Tools'

    def action_export(self):
        return self.env['ai.agent'].action_export_agents()

    def action_import(self):
        return self.env['ai.agent'].action_import_agents()
