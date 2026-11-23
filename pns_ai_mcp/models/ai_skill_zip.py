# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ai.skill: export and import skills as a ZIP."""

import io
import json
import zipfile
from datetime import datetime

from odoo import api, models, _
from odoo.exceptions import UserError
from ..utils import mcp_ui as pns_ui
from ..utils.import_export_guard import ensure_ai_admin
from ..utils.portable_io import export_record_dict
from ..utils.skill_files import snake_catalog_id

from .ai_skill import (
    EXPORT_FORMAT_VERSION,
)


class AISkillZip(models.Model):
    _inherit = 'ai.skill'

    # ------------------------------------------------------------------
    # Export / import (ZIP) — Phase 3
    # ------------------------------------------------------------------
    def _skills_zip_filename(self, scope_label):
        return pns_ui.build_export_filename(
            self.env, 'ai_skills_%s' % (scope_label or 'all'), 'zip')

    def _build_skills_zip_bytes(self, records, scope_label):
        """Build skills export ZIP payload (no UI). Returns None if empty."""
        records = records.exists()
        if not records:
            return None
        skills_meta = []
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for skill in records:
                content_file = 'skills/%s.md' % skill.code
                zip_file.writestr(content_file, (skill.content or '').encode('utf-8'))
                code_file = None
                if skill.code_body:
                    code_file = 'code/%s.py' % skill.code
                    zip_file.writestr(code_file, skill.code_body.encode('utf-8'))
                try:
                    meta = export_record_dict(skill, skip_fields={
                        'id', 'content', 'code_body', 'show_in_slash',
                        'param_cache_ids', 'param_line_ids',
                    })
                except Exception:
                    meta = {'code': skill.code, 'name': skill.name or '?'}
                meta['content_file'] = content_file
                meta['code_file'] = code_file
                try:
                    meta['agent_codes'] = skill.agent_ids.mapped('code')
                except Exception:
                    pass
                try:
                    meta['context_codes'] = skill.context_ids.mapped('code')
                except Exception:
                    pass
                try:
                    meta['required_groups'] = list(
                        skill.required_group_ids.get_external_id().values())
                except Exception:
                    pass
                skills_meta.append(meta)
            manifest = {
                'type': 'ai.skill.export',
                'format_version': EXPORT_FORMAT_VERSION,
                'scope': scope_label,
                'exported_at': datetime.now().isoformat(),
                'skills': skills_meta,
            }
            zip_file.writestr(
                'manifest.json',
                json.dumps(manifest, indent=2, ensure_ascii=False),
            )
        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    def _export_skills_to_zip(self, records, scope_label, title='Export skills'):
        records = records.exists()
        if not records:
            return pns_ui.open_json_export_empty_wizard(
                self.env,
                dialog_title=title,
                message=_('No skills to export.'),
            )
        payload = self._build_skills_zip_bytes(records, scope_label)
        attachment = pns_ui.write_export_attachment(
            self.env, self._skills_zip_filename(scope_label),
            payload, 'application/zip',
        )
        return pns_ui.open_json_export_wizard(
            self.env,
            dialog_title=title,
            summary_text=_('%s skill(s) exported to ZIP.') % len(records),
            count=len(records),
            attachment=attachment,
        )

    @api.model
    def export_all_to_zip(self):
        """Export all skills to ZIP with manifest."""
        ensure_ai_admin(self.env)
        return self._export_skills_to_zip(
            self.search([]), 'all', title=_('Export all skills'),
        )

    def action_export_selected(self):
        """Export selected list rows to ZIP."""
        ensure_ai_admin(self.env)
        active_ids = self.env.context.get('active_ids') or self.ids
        records = self.browse(active_ids).exists()
        if not records:
            raise UserError(_('Select at least one skill to export.'))
        return records._export_skills_to_zip(
            records, 'sel-%d' % len(records), title=_('Export selected skills'),
        )

    @api.model
    def action_open_import_wizard(self):
        ensure_ai_admin(self.env)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import skills from ZIP'),
            'res_model': 'ai.skill.import.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def export_agent_skills_to_zip(self, agent):
        """Export the skills exposed by an AI agent (its ``skill_ids``)."""
        ensure_ai_admin(self.env)
        agent.ensure_one()
        return self._export_skills_to_zip(
            agent.skill_ids, 'agent-%s' % agent.code,
            title=_('Export agent skills'),
        )

    @api.model
    def import_agent_skills_zip(self, agent, zip_bytes, replace_existing=False):
        """Import a skills export ZIP into the target agent (linked to it)."""
        ensure_ai_admin(self.env)
        agent.ensure_one()
        return self.import_skills_zip(
            zip_bytes, replace_existing=replace_existing, force_agent=agent,
        )

    @api.model
    def action_export_skills(self):
        """Cog-menu entry point: export all skills to ZIP."""
        ensure_ai_admin(self.env)
        return self.export_all_to_zip()

    @api.model
    def action_import_skills(self):
        """Cog-menu entry point: open the import wizard."""
        ensure_ai_admin(self.env)
        return self.action_open_import_wizard()

    @api.model
    def import_skills_zip(self, zip_bytes, replace_existing=False, force_agent=None):
        """Recreate skills from a ZIP export. Contexts are linked only if they exist.

        force_agent: when set, every imported/updated skill is also linked to
        that agent (added to its ``agent_ids`` and to the agent's ``skill_ids``).
        Used by the per-agent import scope.
        """
        ensure_ai_admin(self.env)
        Agent = self.env['ai.agent']
        Context = self.env['ai.context']
        stats = {
            'created': 0, 'updated': 0, 'skipped': 0,
            'missing_contexts': [], 'missing_agents': [], 'errors': [],
        }
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
                manifest = json.loads(zf.read('manifest.json').decode('utf-8'))
                for entry in manifest.get('skills', []):
                    raw_code = (entry.get('code') or '').strip()
                    if not raw_code:
                        stats['errors'].append(_('Skill without code skipped.'))
                        continue
                    code = snake_catalog_id(raw_code)
                    command = (entry.get('command') or '').strip()
                    if not command and raw_code != code:
                        command = raw_code
                    content = entry.get('content', '') or ''
                    content_file = entry.get('content_file')
                    if content_file:
                        try:
                            content = zf.read(content_file).decode('utf-8')
                        except KeyError:
                            pass
                    code_body = entry.get('code_body', '') or ''
                    code_file = entry.get('code_file')
                    if code_file:
                        try:
                            code_body = zf.read(code_file).decode('utf-8')
                        except KeyError:
                            pass
                    agent_codes = entry.get('agent_codes')
                    if agent_codes is None:
                        single = entry.get('agent_code')
                        agent_codes = [single] if single else []
                    agents = Agent.browse()
                    for ac in agent_codes:
                        found_agent = Agent.search([('code', '=', ac)], limit=1)
                        if found_agent:
                            agents |= found_agent
                        elif ac not in stats['missing_agents']:
                            stats['missing_agents'].append(ac)
                    if force_agent:
                        agents |= force_agent
                    ctx_codes = entry.get('context_codes') or []
                    contexts = (
                        Context.search([('code', 'in', ctx_codes)])
                        if ctx_codes else Context.browse()
                    )
                    found = set(contexts.mapped('code'))
                    for missing in ctx_codes:
                        if missing not in found and missing not in stats['missing_contexts']:
                            stats['missing_contexts'].append(missing)
                    values = {
                        'code': code,
                        'name': entry.get('name') or code,
                        'description': entry.get('description') or code,
                        'content': content,
                        'code_body': code_body or False,
                        'agent_ids': [(6, 0, agents.ids)],
                        'version': entry.get('version') or False,
                        'sequence': entry.get('sequence', 10),
                        'active': entry.get('active', True),
                        'required_group_ids': [(6, 0, self._required_groups_from_meta({
                            'required_groups': ','.join(
                                entry.get('required_groups') or []),
                        }).ids)] if 'required_groups' in entry else [],
                        'context_ids': [(6, 0, contexts.ids)],
                        'command': command if command and command != code else False,
                    }
                    existing = self.search([
                        '|', '|',
                        ('code', '=', code),
                        ('code', '=', command or code),
                        ('command', '=', command or code),
                    ], limit=1)
                    if existing:
                        if replace_existing:
                            # Slash visibility lives in ICP, not in the ZIP.
                            existing.write(values)
                            existing._apply_slash_hidden_from_icp()
                            stats['updated'] += 1
                        else:
                            stats['skipped'] += 1
                    else:
                        values['code'] = code
                        self.create(values)
                        stats['created'] += 1
        except KeyError:
            raise UserError(_('Invalid ZIP: manifest.json not found.'))
        except (zipfile.BadZipFile, ValueError) as exc:
            raise UserError(_('Could not read skills ZIP: %s') % exc)
        return stats
