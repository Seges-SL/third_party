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


class ImportServersWizard(models.TransientModel):
    _name = 'pns_ai_mcp.import_servers_wizard'
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
            name = server_data.get('name')
            try:
                existing = server_model.with_context(active_test=False).search(
                    [('name', '=', name)], limit=1
                )
                if existing and not self.replace_existing:
                    skipped_count += 1
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
                else:
                    target_server = server_model.create(vals)
                    imported_count += 1

                available_models = server_data.get('available_models', [])
                if available_models:
                    target_server.available_model_ids.unlink()
                    new_models = self.env['ai.provider.model']
                    for model_name in available_models:
                        new_models |= self.env['ai.provider.model'].create({
                            'name': model_name,
                            'provider_id': target_server.id
                        })
                    selected_model = server_data.get('selected_model')
                    if selected_model:
                        matching = new_models.filtered(lambda m: m.name == selected_model)
                        if matching:
                            target_server.model_id = matching[0].id

                import_warnings += self._import_failovers(
                    target_server,
                    server_data.get('failovers', server_data.get('role_failovers', [])),
                )
                self.env['ai.provider.usage.day'].import_missing_days(
                    target_server,
                    server_data.get('usage_days') or [],
                )

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
        )

    def _import_failovers(self, provider, failovers):
        """Best-effort: vincula el proveedor a agentes (por code) con su prioridad.

        Usa un savepoint por asignación para que un conflicto puntual (la
        restricción global unique(agent_id, priority) cuando otro proveedor ya
        ocupa ese hueco, o un agente inexistente en destino) se omita sin abortar
        el resto de la importación. Devuelve avisos legibles para el informe.
        """
        warnings = []
        if not failovers:
            return warnings
        Agent = self.env['ai.agent']
        Assignment = self.env['ai.agent.provider']
        for entry in failovers:
            if not isinstance(entry, dict):
                continue
            code = (entry.get('agent_code') or '').strip()
            if not code:
                continue
            agent = Agent.with_context(active_test=False).search(
                [('code', '=', code)], limit=1
            )
            if not agent:
                warnings.append(
                    _("Provider '%s': agent '%s' does not exist here; failover entry skipped.")
                    % (provider.name, code)
                )
                continue
            avals = {
                'agent_id': agent.id,
                'provider_id': provider.id,
                'priority': entry.get('priority', 0),
                'active': entry.get('active', True),
            }
            existing = Assignment.with_context(active_test=False).search([
                ('agent_id', '=', agent.id),
                ('provider_id', '=', provider.id),
            ], limit=1)
            try:
                with self.env.cr.savepoint():
                    if existing:
                        existing.write(avals)
                    else:
                        Assignment.create(avals)
            except Exception as e:
                warnings.append(
                    _("Provider '%s': agent '%s' at priority %s could not be assigned "
                      "(slot already taken).") % (provider.name, code, entry.get('priority', 0))
                )
                _logger.info("MCP: Assignment omitido %s/%s: %s", provider.name, code, e)
        return warnings
