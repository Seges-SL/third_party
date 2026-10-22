# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Import AI providers from JSON (legacy servers wizard)."""

import base64
import json
import logging

from odoo import api, models, fields, _
from odoo.exceptions import UserError

from ..utils import mcp_ui

_logger = logging.getLogger(__name__)


class ImportServersWizard(models.TransientModel):
    _name = 'ai.import.servers.wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'Wizard to import AI Servers from JSON'

    json_file = fields.Binary(string='JSON File', required=True, attachment=True)
    filename = fields.Char(string='File name')
    replace_existing = fields.Boolean(
        string='Replace existing',
        default=True,
        help='If checked, providers with the same name will be updated. Otherwise, they will be skipped.'
    )
    def action_import(self):
        """Process the JSON file and import/update the providers."""
        self.ensure_one()
        if not self.json_file:
            raise UserError(_("Please upload a JSON file."))

        try:
            json_content = base64.b64decode(self.json_file)
            json_data, extract_warnings = mcp_ui.extract_json_from_upload(json_content)
        except (ValueError, Exception) as e:
            raise UserError(_("Error reading the file: %s") % e)

        imported_count = 0
        updated_count = 0
        skipped_count = 0
        created_names = []
        updated_names = []
        skipped_names = []
        errors = []
        import_warnings = list(extract_warnings)

        server_model = self.env['ai.provider']
        model_fields = server_model._fields
        SPECIAL_KEYS = {
            'name', 'api_key', 'provider_api_key', 'router_api_key', 'is_api_key',
            'available_models', 'available_model_ids',
            'selected_model', 'model_id',
            'failovers', 'agent_provider_ids', 'failover_ids', 'role_failovers',
            'role_failover_ids', 'agent_ids',
            'usage_days', 'usage_day_ids',
        }

        for server_data in json_data:
            name = server_data.get('name') or _('(no name)')
            try:
                existing = server_model.with_context(active_test=False).search(
                    [('name', '=', server_data.get('name'))], limit=1
                )
                if existing and not self.replace_existing:
                    skipped_count += 1
                    skipped_names.append(name)
                    _logger.info("MCP: Servidor existente omitido: %s", name)
                    continue

                vals = {'name': name}

                old_api_key = server_data.get('is_api_key', '')
                if isinstance(old_api_key, bool):
                    old_api_key = ''
                api_key = (server_data.get('api_key')
                           or server_data.get('provider_api_key')
                           or server_data.get('router_api_key')
                           or old_api_key)
                if api_key and 'api_key' in model_fields:
                    vals['api_key'] = api_key

                for key, value in server_data.items():
                    if key in SPECIAL_KEYS:
                        continue
                    field = model_fields.get(key)
                    if field is None:
                        continue
                    if field.type in ('one2many', 'many2many', 'many2one'):
                        continue
                    if getattr(field, 'compute', None) and not getattr(field, 'store', False):
                        continue
                    if getattr(field, 'related', None):
                        continue
                    if field.type == 'selection':
                        sel = field.selection
                        if isinstance(sel, (list, tuple)) and value not in [s[0] for s in sel]:
                            continue
                    vals[key] = value

                if existing:
                    existing.write(vals)
                    target_server = existing
                    updated_count += 1
                    updated_names.append(name)
                else:
                    target_server = server_model.create(vals)
                    imported_count += 1
                    created_names.append(name)

                sel = server_data.get('selected_model')
                if isinstance(sel, str):
                    sel = sel.strip()
                if sel:
                    Model = self.env['ai.provider.model']
                    match = target_server.available_model_ids.filtered(
                        lambda m: m.name == sel,
                    )
                    if not match:
                        match = Model.create({
                            'name': sel,
                            'provider_id': target_server.id,
                        })
                    target_server.model_id = match[0].id

            except Exception as e:
                error_msg = "%s: %s" % (name or 'Sin nombre', str(e))
                errors.append(error_msg)
                _logger.error("MCP: Error importando servidor: %s", error_msg)

        return self._apply_operation_result(
            view_xmlid='pns_ai_mcp.view_import_servers_result_form',
            created=imported_count,
            updated=updated_count,
            skipped=skipped_count,
            errors=errors,
            warnings=import_warnings,
            created_names=created_names,
            updated_names=updated_names,
            skipped_names=skipped_names,
        )
