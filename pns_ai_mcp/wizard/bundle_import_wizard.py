# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Wizard: import an agent's context pack from a ZIP file.

The ZIP is produced by the JSON export action and contains:
- ``manifest.json`` with metadata and context codes.
- Individual context files (Markdown/XML).

The wizard allows replacing existing contexts and/or overwriting
the agent's composition (context_ids) from the manifest.

Model: ``pns_ai_mcp.agent.import.wizard``
"""
import base64

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .operation_result import agent_pack_to_result


class AIAgentImportWizard(models.TransientModel):
    """Import a context pack ZIP into an agent.

    Inherits ``pns.operation.report.wizard`` for the result view.
    """
    _name = 'pns_ai_mcp.agent.import.wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'Import context pack from ZIP'

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
    replace_composition = fields.Boolean(
        string='Replace composition',
        default=True,
        help='Set agent composition (context membership) from manifest.json context_codes.',
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
        """Parse the uploaded ZIP and import contexts into the agent."""
        self.ensure_one()
        if not self.import_file:
            raise UserError(_('Please upload a context pack ZIP file.'))
        if not (self.filename or '').lower().endswith('.zip'):
            raise UserError(_('The file must be a .zip context pack export.'))

        zip_bytes = base64.b64decode(self.import_file)
        result = self.env['ai.context'].import_agent_zip(
            self.agent_id,
            zip_bytes,
            replace_existing=self.replace_existing,
            replace_composition=self.replace_composition,
        )
        return self._apply_operation_result(
            view_xmlid='pns_ai_mcp.view_agent_pack_import_result_form',
            **agent_pack_to_result(result),
        )
