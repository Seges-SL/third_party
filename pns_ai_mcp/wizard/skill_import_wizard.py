# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
import base64

from odoo import fields, models, _
from odoo.exceptions import UserError


class AISkillImportWizard(models.TransientModel):
    _name = 'pns_ai_mcp.skill.import.wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'Import skills from ZIP'

    import_file = fields.Binary(string='ZIP file', attachment=True)
    filename = fields.Char()
    replace_existing = fields.Boolean(
        string='Replace existing skills',
        default=False,
        help='Update skills that already exist with the same code.',
    )

    def action_import(self):
        self.ensure_one()
        if not self.import_file:
            raise UserError(_('Please upload a skills export ZIP file.'))
        if not (self.filename or '').lower().endswith('.zip'):
            raise UserError(_('The file must be a .zip export of skills.'))
        stats = self.env['ai.skill'].import_skills_zip(
            base64.b64decode(self.import_file),
            replace_existing=self.replace_existing,
        )
        detail_parts = []
        if stats.get('missing_contexts'):
            detail_parts.append(', '.join(stats['missing_contexts']))
        if stats.get('missing_agents'):
            detail_parts.append(', '.join(stats['missing_agents']))
        return self._apply_operation_result(
            view_xmlid='pns_ai_mcp.view_skill_import_result_form',
            created=stats.get('created', 0),
            updated=stats.get('updated', 0),
            skipped=stats.get('skipped', 0),
            errors=stats.get('errors'),
            detail='\n'.join(detail_parts) if detail_parts else None,
        )
