# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
import base64
import json
import logging

from odoo import api, models, fields, _
from odoo.exceptions import UserError

from ..utils import mcp_ui

_logger = logging.getLogger(__name__)


class ImportAgentsWizard(models.TransientModel):
    _name = 'pns_ai_mcp.import_agents_wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'Wizard to import AI Agents from JSON'

    json_file = fields.Binary(string='JSON File', required=True, attachment=True)
    filename = fields.Char(string='File name')
    replace_existing = fields.Boolean(
        string='Replace existing',
        default=True,
        help='If checked, agents with the same code will be updated (including their '
             'provider chain). Otherwise, existing agents are skipped.'
    )
    def action_import(self):
        """Process the JSON file and import/update the AI agents."""
        self.ensure_one()
        if not self.json_file:
            raise UserError(_("Please upload a JSON file."))

        try:
            json_content = base64.b64decode(self.json_file)
            json_data, extract_warnings = mcp_ui.extract_json_from_upload(json_content)
        except (ValueError, Exception) as e:
            raise UserError(_("Error reading the file: %s") % e)

        Agent = self.env['ai.agent']
        Provider = self.env['ai.provider']
        Assignment = self.env['ai.agent.provider']

        imported_count = 0
        updated_count = 0
        skipped_count = 0
        missing_providers = set()
        errors = []

        for agent_data in json_data:
            code = (agent_data.get('code') or '').strip()
            if not code:
                errors.append(_("Entry without 'code' field skipped."))
                continue
            try:
                existing = Agent.with_context(active_test=False).search(
                    [('code', '=', code)], limit=1
                )
                if existing and not self.replace_existing:
                    skipped_count += 1
                    continue

                vals = {
                    'name': agent_data.get('name') or code,
                    'code': code,
                    'sequence': agent_data.get('sequence', 10),
                    'description': agent_data.get('description', ''),
                    'active': agent_data.get('active', True),
                }

                if existing:
                    existing.write(vals)
                    agent_rec = existing
                    updated_count += 1
                    Assignment.with_context(active_test=False).search(
                        [('agent_id', '=', agent_rec.id)]
                    ).unlink()
                else:
                    agent_rec = Agent.create(vals)
                    imported_count += 1

                for failover_entry in agent_data.get('failovers', []):
                    provider_name = failover_entry.get('provider')
                    provider = Provider.with_context(active_test=False).search(
                        [('name', '=', provider_name)], limit=1
                    )
                    if not provider:
                        missing_providers.add(provider_name or '?')
                        continue
                    Assignment.create({
                        'agent_id': agent_rec.id,
                        'provider_id': provider.id,
                        'priority': failover_entry.get('priority', 0),
                        'active': failover_entry.get('active', True),
                    })

            except Exception as e:
                error_msg = "%s: %s" % (code or _('No code'), str(e))
                errors.append(error_msg)
                _logger.error("MCP: Error importing agent: %s", error_msg)

        return self._apply_operation_result(
            view_xmlid='pns_ai_mcp.view_import_agents_result_form',
            created=imported_count,
            updated=updated_count,
            skipped=skipped_count,
            errors=errors,
            detail=', '.join(sorted(missing_providers)) if missing_providers else None,
        )
