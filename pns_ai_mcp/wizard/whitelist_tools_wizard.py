# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Whitelist Tools wizard (export / import)."""

from odoo import models


class UrlWhitelistToolsWizard(models.TransientModel):
    _name = 'ai.whitelist.tools.wizard'
    _inherit = ['pns.export_import.tools.wizard.mixin']
    _description = 'Whitelist Tools'

    def action_export(self):
        return self.env['ai.url.whitelist'].action_export_whitelist()

    def action_import(self):
        return self.env['ai.url.whitelist'].action_import_whitelist()
