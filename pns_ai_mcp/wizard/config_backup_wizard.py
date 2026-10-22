# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Config backup import wizard — restore the whole AI configuration from JSON.

Companion of :mod:`..utils.config_backup`. The export side is a one-click button
in Settings (no upload needed); the import side needs a file, hence this wizard.
Review first (dry-run), then confirm writes.
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

_NAME_CAP = 20


class ConfigBackupWizard(models.TransientModel):
    _name = 'ai.config.backup.wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'AI configuration backup import wizard'

    json_file = fields.Binary(string='Backup file (.json)', required=True, attachment=True)
    filename = fields.Char(string='File name')
    replace_existing = fields.Boolean(
        string='Overwrite existing records',
        default=False,
        help='Unchecked: records that already exist here are left as they are '
             'and only the missing ones are created.',
    )

    def _read_backup_json(self):
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
        return data, list(extract_warnings or [])

    def _format_name_block(self, title, names):
        names = [n for n in (names or []) if n]
        if not names:
            return ''
        shown = names[:_NAME_CAP]
        lines = [title] + ['- %s' % n for n in shown]
        if len(names) > _NAME_CAP:
            lines.append('- %s' % (_('… and %s more') % (len(names) - _NAME_CAP)))
        return '\n'.join(lines)

    def _detail_from_report(self, report):
        parts = []
        sections = report.get('sections') or {}
        for key, label in _SECTION_LABELS.items():
            s = sections.get(key)
            if not s:
                continue
            created = s.get('created', 0)
            updated = s.get('updated', 0)
            skipped = s.get('skipped', 0)
            if not (created or updated or skipped):
                continue
            blocks = [_(label)]
            for kind, key in (
                ('created', 'created_names'),
                ('updated', 'updated_names'),
                ('skipped', 'skipped_names'),
            ):
                block = self._format_name_block(
                    self._preview_bucket_title(kind), s.get(key),
                )
                if block:
                    blocks.append(block)
            parts.append('\n'.join(blocks))
        return '\n\n'.join(parts) or False

    def _totals(self, report):
        sections = report.get('sections') or {}
        return (
            sum(s.get('created', 0) for s in sections.values()),
            sum(s.get('updated', 0) for s in sections.values()),
            sum(s.get('skipped', 0) for s in sections.values()),
        )

    def action_preview(self):
        """Show what the file would do. Nothing is written."""
        data, warnings = self._read_backup_json()
        report = config_backup.import_config(
            self.env, data,
            replace_existing=self.replace_existing,
            dry_run=True,
        )
        warnings = warnings + (report.get('warnings') or [])
        created, updated, skipped = self._totals(report)
        return self._apply_import_preview(
            created=created,
            updated=updated,
            skipped=skipped,
            errors=report.get('errors') or [],
            warnings=warnings,
            detail=self._detail_from_report(report) or False,
        )

    def action_import(self):
        """Apply the uploaded backup after the review step."""
        data, extract_warnings = self._read_backup_json()
        report = config_backup.import_config(
            self.env, data, replace_existing=self.replace_existing,
        )
        warnings = extract_warnings + (report.get('warnings') or [])
        errors = report.get('errors') or []
        created, updated, skipped = self._totals(report)
        return self._apply_operation_result(
            view_xmlid='pns_ai_mcp.view_config_backup_result_form',
            created=created,
            updated=updated,
            skipped=skipped,
            errors=errors,
            warnings=warnings,
            detail=self._detail_from_report(report) or False,
            title=_('Configuration import result'),
        )
