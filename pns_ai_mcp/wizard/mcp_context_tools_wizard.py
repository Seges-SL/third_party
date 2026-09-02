# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from odoo import fields, models, _

from ..utils.import_export_guard import ensure_ai_admin
from .operation_result import context_zip_files_to_result


class McpContextToolsWizard(models.TransientModel):
    _name = 'pns_ai_mcp.context.tools.wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'Contexts Tools'

    replace_existing = fields.Boolean(
        string='Overwrite matching contexts',
        default=True,
        help='When restoring from the module: overwrite contexts whose code already '
             'exists in the database. Uncheck to only add new contexts and keep '
             'existing ones untouched. Restore never deletes existing records.',
    )

    def action_stats(self):
        return self.env['ai.context'].action_open_stats_wizard()

    def action_restore(self):
        self.ensure_one()
        ensure_ai_admin(self.env)
        result = self.env['ai.context'].with_context(
            skip_hardcoded_restrictions=True,
        )._import_all_from_module(replace_existing=self.replace_existing)
        return self._apply_operation_result(
            view_xmlid='pns_ai_mcp.view_mcp_context_tools_restore_result_form',
            created=result.get('imported', 0),
            updated=result.get('updated', 0),
            skipped=result.get('skipped', 0),
            removed=result.get('deleted', 0),
            errors=result.get('errors'),
        )

    def action_export(self):
        ensure_ai_admin(self.env)
        return self.env['ai.context'].export_all_to_zip()

    def action_import(self):
        ensure_ai_admin(self.env)
        return self.env['ai.context'].action_import_from_zip()
