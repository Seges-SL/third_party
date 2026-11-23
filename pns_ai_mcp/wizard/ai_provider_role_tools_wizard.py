# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Provider roles Tools wizard (export / import)."""

from odoo import models


class AiProviderRoleToolsWizard(models.TransientModel):
    _name = 'ai.provider.role.tools.wizard'
    _inherit = ['pns.export_import.tools.wizard.mixin']
    _description = 'Provider Roles Tools'

    def action_export(self):
        return self.env['ai.provider.role'].action_export_roles()

    def action_import(self):
        return self.env['ai.provider.role'].action_import_roles()
