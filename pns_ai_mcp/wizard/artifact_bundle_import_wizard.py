# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
import base64

from odoo import fields, models, _
from odoo.exceptions import UserError

from ..utils import artifact_bundle


# English source strings only — never call _() at import time (Odoo 19 warns
# "no translation language detected" during module load).
_SECTION_LABELS = {
    'providers': 'Providers',
    'agents': 'Agents',
    'mcp_servers': 'External servers',
    'mcp_users': 'MCP users',
    'url_whitelists': 'URL whitelist',
    'settings': 'Settings',
}


class AIArtifactBundleImportWizard(models.TransientModel):
    _name = 'pns_ai_mcp.artifact_bundle.import.wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'Import AI artifacts bundle'

    import_file = fields.Binary(string='Bundle ZIP', attachment=True)
    filename = fields.Char()
    replace_existing = fields.Boolean(
        string='Replace existing (same business key)',
        default=True,
        help='Update records that already exist with the same code, name, login, '
             'domain or setting key. When off, existing rows are left unchanged.',
    )

    def action_import(self):
        self.ensure_one()
        if not self.import_file:
            raise UserError(_('Please upload an artifact bundle ZIP file.'))
        if not (self.filename or '').lower().endswith('.zip'):
            raise UserError(_('The file must be a .zip artifact bundle.'))

        report = artifact_bundle.import_bundle(
            self.env,
            base64.b64decode(self.import_file),
            replace_existing=self.replace_existing,
        )
        skills = report.get('skills') or {}
        contexts = report.get('contexts') or {}
        sections = report.get('sections') or {}
        manifest = report.get('manifest') or {}
        warnings = list(report.get('warnings') or [])

        detail_lines = []
        if manifest.get('export_tag'):
            detail_lines.append(_('Bundle tag: %s') % manifest['export_tag'])
        if manifest.get('source_database'):
            detail_lines.append(_('Source instance: %s') % manifest['source_database'])
        if manifest.get('export_filename'):
            detail_lines.append(_('Original file name: %s') % manifest['export_filename'])
        if skills:
            detail_lines.append(_(
                'Skills — created: %(c)s, updated: %(u)s, skipped: %(s)s'
            ) % {
                'c': skills.get('created', 0),
                'u': skills.get('updated', 0),
                's': skills.get('skipped', 0),
            })
        if contexts:
            detail_lines.append(_(
                'Contexts — created: %(c)s, updated: %(u)s, skipped: %(s)s'
            ) % {
                'c': contexts.get('imported', 0),
                'u': contexts.get('updated', 0),
                's': contexts.get('skipped', 0),
            })
        for key, label_src in _SECTION_LABELS.items():
            sec = sections.get(key) or {}
            if not sec:
                continue
            detail_lines.append(_(
                '%(label)s — created: %(c)s, updated: %(u)s, skipped: %(s)s'
            ) % {
                'label': _(label_src),
                'c': sec.get('created', 0),
                'u': sec.get('updated', 0),
                's': sec.get('skipped', 0),
            })

        errors = list(report.get('errors') or [])
        errors.extend(skills.get('errors') or [])
        errors.extend(contexts.get('errors') or [])

        created = skills.get('created', 0) + contexts.get('imported', 0)
        updated = skills.get('updated', 0) + contexts.get('updated', 0)
        skipped = skills.get('skipped', 0) + contexts.get('skipped', 0)
        for sec in sections.values():
            created += sec.get('created', 0)
            updated += sec.get('updated', 0)
            skipped += sec.get('skipped', 0)

        return self._apply_operation_result(
            view_xmlid='pns_ai_mcp.view_artifact_bundle_import_result_form',
            created=created,
            updated=updated,
            skipped=skipped,
            errors=errors or None,
            warnings=warnings or None,
            detail='\n'.join(detail_lines) if detail_lines else None,
        )
