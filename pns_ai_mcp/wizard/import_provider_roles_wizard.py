# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Import provider roles from JSON (the Roles list export)."""

from odoo import fields, models, _
from odoo.exceptions import UserError

from ..utils import mcp_ui
from ..utils.compat import binary_bytes
from ..utils.config_backup import _import_provider_roles
from ..utils.import_export_guard import ensure_ai_admin


class ImportProviderRolesWizard(models.TransientModel):
    _name = 'ai.import.provider.roles.wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'Wizard to import provider roles from JSON'

    json_file = fields.Binary(string='JSON File', required=True, attachment=True)
    filename = fields.Char(string='File name')
    replace_existing = fields.Boolean(
        string='Replace existing',
        default=True,
        help='If checked, each role takes the settings and the providers of '
             'the file. Otherwise, roles are left as they are.',
    )

    def action_import(self):
        self.ensure_one()
        ensure_ai_admin(self.env)
        if not self.json_file:
            raise UserError(_("Please upload a JSON file."))
        try:
            rows, extract_warnings = mcp_ui.extract_json_from_upload(
                binary_bytes(self.json_file),
            )
        except Exception as e:
            raise UserError(_("Error reading the file: %s") % e)
        report = {'sections': {}, 'warnings': list(extract_warnings), 'errors': []}
        _import_provider_roles(
            self.env, rows, report, replace_existing=self.replace_existing,
        )
        sec = report['sections'].get('provider_roles') or {}
        return self._apply_operation_result(
            view_xmlid='pns_ai_mcp.view_import_provider_roles_result_form',
            updated=sec.get('updated', 0),
            skipped=sec.get('skipped', 0),
            errors=report['errors'],
            warnings=report['warnings'],
            updated_names=sec.get('updated_names') or [],
            skipped_names=sec.get('skipped_names') or [],
        )
