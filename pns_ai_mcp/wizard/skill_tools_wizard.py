# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from odoo import fields, models

from ..utils.import_export_guard import ensure_ai_admin


class AISkillToolsWizard(models.TransientModel):
    _name = 'pns_ai_mcp.skill.tools.wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'Skills Tools'

    replace_existing = fields.Boolean(
        string='Overwrite matching skills',
        default=True,
        help='When reloading from server: overwrite skills whose code already '
             'exists in the database. Uncheck to only add new skills and keep '
             'existing ones untouched. Reload never deletes existing records.',
    )

    def action_reload(self):
        self.ensure_one()
        ensure_ai_admin(self.env)
        stats = self.env['ai.skill'].import_from_files(
            replace_existing=self.replace_existing,
        )
        return self._apply_operation_result(
            view_xmlid='pns_ai_mcp.view_skill_tools_reload_result_form',
            created=stats.get('created', 0),
            updated=stats.get('updated', 0),
            skipped=stats.get('skipped', 0),
            removed=stats.get('pruned', 0),
            errors=stats.get('errors'),
        )

    def action_export_zip(self):
        ensure_ai_admin(self.env)
        return self.env['ai.skill'].export_all_to_zip()

    def action_import(self):
        ensure_ai_admin(self.env)
        return self.env['ai.skill'].action_open_import_wizard()
