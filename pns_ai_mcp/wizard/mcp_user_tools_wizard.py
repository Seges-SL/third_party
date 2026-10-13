# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Users Tools wizard (export / import)."""

from odoo import models


class McpUserToolsWizard(models.TransientModel):
    _name = 'ai.user.tools.wizard'
    _inherit = ['pns.export_import.tools.wizard.mixin']
    _description = 'Users Tools'

    def action_export(self):
        return self.env['ai.mcp.user'].action_export_users()

    def action_import(self):
        return self.env['ai.mcp.user'].action_import_users()

    def action_key_list(self):
        """The paste box is opened by the browser. This only closes the dialog."""
        return {'type': 'ir.actions.act_window_close'}
