# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from odoo import models


class SafeOperationToolsWizard(models.TransientModel):
    _name = 'pns_ai_mcp.safe.operation.tools.wizard'
    _description = 'Authorization Tools'

    def action_refresh_expiry(self):
        return self.env['ai.safe.operation'].action_refresh_expiry_statuses()

    def action_export(self):
        return self.env['ai.safe.operation'].action_export_operations()
