# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
import base64

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .operation_result import context_zip_files_to_result


class AIAgentContextImportWizard(models.TransientModel):
    _name = 'pns_ai_mcp.agent.context.import.wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'Import agent contexts from ZIP'

    agent_id = fields.Many2one(
        'ai.agent',
        required=True,
        readonly=True,
    )
    import_file = fields.Binary(string='ZIP file', attachment=True)
    filename = fields.Char()
    replace_existing = fields.Boolean(
        string='Replace existing contexts',
        default=False,
        help='Update contexts that already exist with the same code and file path.',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        agent = self.env['ai.agent'].browse(
            res.get('agent_id') or self.env.context.get('default_agent_id')
        )
        if agent:
            res['agent_id'] = agent.id
        return res

    def action_import(self):
        self.ensure_one()
        if not self.import_file:
            raise UserError(_('Please upload an agent contexts export ZIP file.'))
        if not (self.filename or '').lower().endswith('.zip'):
            raise UserError(_('The file must be a .zip export from an AI agent.'))

        zip_bytes = base64.b64decode(self.import_file)
        result = self.env['ai.context'].import_agent_contexts_zip(
            self.agent_id, zip_bytes, replace_existing=self.replace_existing,
        )
        vals = context_zip_files_to_result(result['files'], warnings=result.get('warnings'))
        return self._apply_operation_result(
            view_xmlid='pns_ai_mcp.view_agent_context_import_result_form',
            **vals,
        )
