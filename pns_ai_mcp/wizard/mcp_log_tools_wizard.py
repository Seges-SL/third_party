# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""History Tools: export logs or open the clear-history wizard."""

from odoo import models


class McpLogToolsWizard(models.TransientModel):
    _name = 'ai.log.tools.wizard'
    _description = 'History Tools'

    def action_export(self):
        return self.env['ai.log'].action_export_logs()

    def action_clear(self):
        return self.env.ref(
            'pns_ai_mcp.action_ai_log_delete_menu_window'
        ).sudo().read()[0]
