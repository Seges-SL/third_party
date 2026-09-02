# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
import base64
import logging

from odoo import models, fields, _
from odoo.exceptions import UserError

from ..utils import mcp_ui
from ..utils.portable_io import import_vals_from_dict

_logger = logging.getLogger(__name__)


def _normalize_server_rows(data):
    """Accept a JSON array, a single object, or a backup section — never abort."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ('mcp_servers', 'external_api_servers', 'servers'):
            section = data.get(key)
            if isinstance(section, list):
                return section
        if data.get('code') or data.get('name'):
            return [data]
    return []


class ImportExternalServersWizard(models.TransientModel):
    """Wizard to import external API servers (MCP / OpenAPI) from JSON.

    Import rules (portable_io):
      - Every JSON key that has a writable field on ``ai.api.server`` is applied.
      - Unknown keys / fields absent on destination are skipped (no abort).
      - Per-record exceptions are collected; the batch always finishes.
      - Match key: ``code``.
      - URL whitelist is a separate model — never mixed into this import.
    """
    _name = 'pns_ai_mcp.import_external_servers_wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'Wizard to import External API Servers from JSON'

    json_file = fields.Binary(string='JSON File', required=True, attachment=True)
    filename = fields.Char(string='File name')
    replace_existing = fields.Boolean(
        string='Replace existing',
        default=True,
        help='If checked, servers with the same code will be updated. Otherwise, they will be skipped.',
    )

    def action_import(self):
        """Process the uploaded file and import/update external API servers."""
        self.ensure_one()
        if not self.json_file:
            raise UserError(_("Please upload a JSON file."))

        try:
            raw = base64.b64decode(self.json_file)
            data, extract_warnings = mcp_ui.extract_json_from_upload(raw)
        except (ValueError, Exception) as e:
            raise UserError(_("Error reading the file: %s") % e)

        rows = _normalize_server_rows(data)
        Server = self.env['ai.api.server']
        created = updated = skipped = 0
        errors = []
        warnings = list(extract_warnings)
        if not rows:
            warnings.append(_(
                'No external server rows found in the file '
                '(expected a JSON array of ai.api.server objects).'
            ))

        for entry in rows:
            if not isinstance(entry, dict):
                errors.append(_("Non-object entry skipped."))
                continue
            code = (entry.get('code') or '').strip()
            if not code:
                errors.append(_("Entry without 'code' field skipped."))
                continue
            try:
                existing = Server.with_context(active_test=False).search(
                    [('code', '=', code)], limit=1,
                )
                if existing and not self.replace_existing:
                    skipped += 1
                    continue

                vals, field_warnings = import_vals_from_dict(Server, entry)
                warnings.extend(
                    '%s: %s' % (code, w) for w in field_warnings
                )
                vals['code'] = code
                if not vals.get('name'):
                    vals['name'] = entry.get('name') or code

                if existing:
                    existing.write(vals)
                    updated += 1
                else:
                    Server.create(vals)
                    created += 1
            except Exception as e:
                errors.append("%s: %s" % (code, e))
                _logger.error("External server import error for %s: %s", code, e)

        return self._apply_operation_result(
            view_xmlid='pns_ai_mcp.view_import_external_servers_result_form',
            created=created,
            updated=updated,
            skipped=skipped,
            errors=errors,
            warnings=warnings,
        )
