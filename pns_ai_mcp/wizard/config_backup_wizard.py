# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Config backup import wizard — restore the whole AI configuration from JSON.

Companion of :mod:`..utils.config_backup`. The export side is a one-click button
in Settings (no upload needed); the import side needs a file, hence this wizard.
"""

import base64
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..utils import mcp_ui
from ..utils import config_backup
from ..utils.import_export_guard import ensure_ai_admin

_logger = logging.getLogger(__name__)

_SECTION_LABELS = {
    'providers': 'Providers',
    'agents': 'Agents',
    'contexts': 'Contexts',
    'skills': 'Skills',
    'mcp_servers': 'External MCP servers',
    'url_whitelists': 'URL whitelist',
    'mcp_users': 'User API keys',
    'settings': 'Settings',
}


class ConfigBackupWizard(models.TransientModel):
    _name = 'pns_ai_mcp.config_backup_wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'AI configuration backup import wizard'

    json_file = fields.Binary(string='Backup file (.json)', required=True, attachment=True)
    filename = fields.Char(string='File name')

    def action_import(self):
        """Parse the uploaded backup and restore the whole AI configuration."""
        self.ensure_one()
        ensure_ai_admin(self.env)
        if not self.json_file:
            raise UserError(_("Please upload a backup JSON file."))

        try:
            raw = base64.b64decode(self.json_file)
            data, extract_warnings = mcp_ui.extract_json_from_upload(
                raw, expect_list=False)
        except (ValueError, Exception) as e:
            raise UserError(_("Error reading the file: %s") % e)

        report = config_backup.import_config(self.env, data)
        warnings = list(extract_warnings or []) + (report.get('warnings') or [])
        errors = report.get('errors') or []

        sections_data = report.get('sections') or {}
        total_created = sum(s.get('created', 0) for s in sections_data.values())
        total_updated = sum(s.get('updated', 0) for s in sections_data.values())
        total_skipped = sum(s.get('skipped', 0) for s in sections_data.values())

        detail_lines = []
        for key, label in _SECTION_LABELS.items():
            s = sections_data.get(key)
            if not s:
                continue
            detail_lines.append(
                _('%(label)s: %(created)s created, %(updated)s updated, '
                  '%(skipped)s skipped') % {
                    'label': _(label),
                    'created': s.get('created', 0),
                    'updated': s.get('updated', 0),
                    'skipped': s.get('skipped', 0),
                })

        return self._apply_operation_result(
            view_xmlid='pns_ai_mcp.view_config_backup_result_form',
            created=total_created,
            updated=total_updated,
            skipped=total_skipped,
            errors=errors,
            warnings=warnings,
            detail='\n'.join(detail_lines) or False,
            title=_('Configuration import result'),
        )
