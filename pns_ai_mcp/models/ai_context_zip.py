# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ai.context: export and import contexts as a ZIP or a single file, and their wizards."""

import json
import zipfile
import io
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..utils import mcp_ui as pns_ui
from ..utils import context_roles
from ..utils.import_export_guard import ensure_ai_admin


class AIContextZip(models.Model):
    _inherit = 'ai.context'

    @api.model
    def action_import_from_zip(self):
        """Abre el wizard de importación de contextos desde ZIP"""
        ensure_ai_admin(self.env)
        return self.env.ref('pns_ai_mcp.action_context_import_wizard').read()[0]

    def _build_export_content(self, record, extension):
        content = record.content or ''
        filename = f"{record.code}{extension}"

        if extension == '.py':
            header_lines = ['# -*- coding: utf-8 -*-', f'# Archivo: {filename}']
            if record.description:
                header_lines.append(f'# Descripción: {record.description}')
            if record.author:
                header_lines.append(f'# Autor: {record.author}')
            if record.version:
                header_lines.append(f'# Versión: {record.version}')
            if record.date_modified:
                header_lines.append(f'# Modificado: {record.date_modified}')
            header_lines.append(f'# Tipo: {record.context_type}')
            if record.locale:
                header_lines.append(f'# Locale: {record.locale}')
            header_lines.append(f'# Activo: {str(record.active).lower()}')
            header_lines.append('')
            return '\n'.join(header_lines) + (content or '')

        if extension == '.xml':
            xml_lines = ['<!--', f'contexto: {record.code}']
            if record.description:
                xml_lines.append(f'descripción: {record.description}')
            xml_lines.append(f'tipo: {record.context_type}')
            xml_lines.append(f'activo: {str(record.active).lower()}')
            xml_lines.append('-->')
            xml_lines.append('')
            return '\n'.join(xml_lines) + content

        yaml_lines = ['---', f'contexto: {record.code}']
        if record.description:
            yaml_lines.append(f'descripción: {record.description}')
        yaml_lines.append(f'tipo: {record.context_type}')
        if record.locale:
            yaml_lines.append(f'locale: {record.locale}')
        if record.author:
            yaml_lines.append(f'autor: {record.author}')
        if record.version:
            yaml_lines.append(f'versión: {record.version}')
        if record.date_modified:
            yaml_lines.append(f'fecha_modificacion: {record.date_modified}')
        yaml_lines.append(f'activo: {str(record.active).lower()}')
        yaml_lines.append('---')
        yaml_lines.append('')
        return '\n'.join(yaml_lines) + content

    @api.model
    def _contexts_zip_filename(self, scope_label):
        return pns_ui.build_export_filename(
            self.env, 'contexts_%s' % (scope_label or 'all'), 'zip')

    def _zip_path_for_record(self, record):
        ext = '.md'
        if context_roles.is_discovery(record.context_type):
            ext = '.json'
        elif record.content and (
            record.content.startswith('# -*-')
            or 'import odoo' in record.content
            or 'def ' in record.content
        ):
            ext = '.py'
        elif record.content and record.content.strip().startswith('<') and '>' in record.content:
            ext = '.xml'

        zip_path = None
        if record.rel_path:
            cleaned_path = record.rel_path.replace('\\', '/')
            if cleaned_path.startswith('contexts/'):
                zip_path = cleaned_path[9:]
            else:
                zip_path = cleaned_path
        if not zip_path:
            folder = record.context_type if record.context_type in context_roles.ALL_TYPES else 'domain'
            zip_path = '%s/%s%s' % (folder, record.code, ext)
        return zip_path, ext

    def _export_content_for_record(self, record, ext):
        content_to_write = record.content or ''
        # Discovery rows are raw JSON routing; never wrap in md front-matter.
        if context_roles.is_discovery(record.context_type) or ext == '.json':
            return content_to_write
        if ext == '.md' and not content_to_write.startswith('---'):
            agent_code = record.agent_ids[:1].code or 'pns_ai_mcp'
            metadata_block = (
                '---\n'
                'code: %s\n'
                'description: %s\n'
                'tipo: %s\n'
                'locale: %s\n'
                'agent_code: %s\n'
                'active: %s\n'
                '---\n\n'
            ) % (
                record.code,
                record.description or '',
                record.context_type or '',
                record.locale or '',
                agent_code,
                str(record.active),
            )
            content_to_write = metadata_block + content_to_write
        return content_to_write

    def _build_export_manifest(self, records, scope_label, agent=None):
        manifest = {
            'format_version': 1,
            'exported_at': fields.Datetime.now().isoformat(),
            'scope': scope_label,
            'contexts': [],
        }
        if agent:
            manifest['agent'] = {
                'code': agent.code,
                'name': agent.name,
                'context_codes': records.sorted(
                    key=lambda c: (c.context_type or '', c.code),
                ).mapped('code'),
            }
        for record in records:
            manifest['contexts'].append({
                'code': record.code,
                'context_type': record.context_type,
                'locale': record.locale or False,
                'agent_code': record.agent_ids[:1].code or False,
                'active': record.active,
                'rel_path': record.rel_path,
            })
        return manifest

    @api.model
    def import_context_file(
        self, filename, content, zip_path=None, replace_existing=False, force_agent=None,
    ):
        """Import or update one context file. Match key: code + rel_path."""
        ensure_ai_admin(self.env)
        metadata = self._extract_metadata_from_content(content, filename)

        raw_code_meta = metadata.get('contexto') or metadata.get('context') or metadata.get('code')
        if raw_code_meta:
            original_code = self.normalize_code(raw_code_meta)
        else:
            original_code = self.generate_code_from_name(filename)

        description = (
            metadata.get('descripción') or metadata.get('descripcion')
            or metadata.get('description') or _('Imported from %s') % filename
        )
        _cat = metadata.get('tipo') or 'domain'
        _folder_probe = (zip_path or filename or '').replace('\\', '/')
        discovery_folder = 'discovery' in _folder_probe.strip('/').split('/')
        context_type = context_roles.canonical_type(
            _cat, discovery_folder=discovery_folder,
        )
        source_mod = metadata.get('source_module') or 'pns_ai_mcp'
        if context_roles.is_discovery(context_type):
            agent_codes = []
        else:
            agent_codes = self._resolve_import_agent_codes(
                metadata, source_mod, context_type=context_type,
            )
        if force_agent:
            agent = force_agent
            agent_codes = [force_agent.code] if force_agent else agent_codes
        else:
            agent = False

        if zip_path:
            if not zip_path.startswith('contexts/'):
                if zip_path.startswith(('custom/', 'system/')):
                    rel_path = 'contexts/%s' % zip_path
                else:
                    rel_path = 'contexts/custom/%s' % zip_path
            else:
                rel_path = zip_path
        else:
            rel_path = 'contexts/custom/%s' % filename
        rel_path = (rel_path or '').replace('\\', '/').strip()

        existing = self.search([
            ('code', '=', original_code),
            ('rel_path', '=', rel_path or ''),
        ], limit=1)

        if existing and existing.context_type == 'core':
            return {'action': 'protocol_skipped', 'code': original_code}
        if context_type == 'core':
            return {'action': 'protocol_skipped', 'code': original_code}

        if existing:
            if not replace_existing:
                return {'action': 'skipped', 'code': original_code}
            existing.write({
                'content': content,
                'description': description,
                'context_type': context_type,
                'rel_path': rel_path,
                'locale': self._infer_explicit_locale(
                    original_code, content, metadata,
                ) or False,
                **(
                    self._discovery_vals_from_metadata(metadata)
                    if context_roles.is_discovery(context_type) else {}
                ),
            })
            self._link_context_after_import(
                existing, agent_codes, source_mod=source_mod,
            )
            if agent and not agent_codes:
                agent.context_ids = [(4, existing.id)]
            return {'action': 'updated', 'code': original_code}

        record = self.create({
            'code': original_code,
            'content': content,
            'description': description,
            'context_type': context_type,
            'active': True,
            'rel_path': rel_path,
            'locale': self._infer_explicit_locale(
                original_code, content, metadata,
            ) or False,
            **(
                self._discovery_vals_from_metadata(metadata)
                if context_roles.is_discovery(context_type) else {}
            ),
        })
        self._link_context_after_import(
            record, agent_codes, source_mod=source_mod,
        )
        if agent and not agent_codes:
            agent.context_ids = [(4, record.id)]
        return {'action': 'imported', 'code': original_code}

    @api.model
    def _tally_import_result(self, stats, result):
        action = result.get('action')
        if action == 'imported':
            stats['imported'] += 1
        elif action == 'updated':
            stats['updated'] += 1
        elif action == 'skipped':
            stats['skipped'] += 1
        elif action == 'protocol_skipped':
            stats['protocol_skipped'] += 1
        elif action == 'error':
            stats['errors'].append(result.get('message', ''))

    @api.model
    def _read_zip_manifest(self, zip_buffer):
        try:
            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                if 'manifest.json' not in zf.namelist():
                    return {}
                return json.loads(zf.read('manifest.json').decode('utf-8'))
        except Exception:
            return {}

    @api.model
    def _resolve_import_code(self, content, filename):
        metadata = self._extract_metadata_from_content(content, filename)
        raw_code_meta = (
            metadata.get('contexto') or metadata.get('context') or metadata.get('code')
        )
        if raw_code_meta:
            return self.normalize_code(raw_code_meta)
        return self.generate_code_from_name(filename)

    @api.model
    def import_contexts_from_zip_buffer(
        self, zip_buffer, replace_existing=False, force_agent=None, allowed_codes=None,
    ):
        """Import context files from a ZIP buffer."""
        stats = {
            'imported': 0, 'updated': 0, 'skipped': 0,
            'protocol_skipped': 0, 'skipped_manifest': 0, 'errors': [],
        }
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            for file_info in zf.infolist():
                if not file_info.filename.endswith(('.txt', '.md', '.xml')):
                    continue
                if file_info.filename.startswith('__MACOSX') or '/.' in file_info.filename:
                    continue
                try:
                    content = zf.read(file_info.filename).decode('utf-8')
                    if allowed_codes is not None:
                        code = self._resolve_import_code(content, file_info.filename)
                        if code not in allowed_codes:
                            stats['skipped_manifest'] += 1
                            continue
                    zip_path = file_info.filename.replace('\\', '/')
                    result = self.import_context_file(
                        file_info.filename, content, zip_path=zip_path,
                        replace_existing=replace_existing, force_agent=force_agent,
                    )
                    self._tally_import_result(stats, result)
                except Exception as exc:
                    stats['errors'].append('%s: %s' % (file_info.filename, exc))
        return stats

    @api.model
    def import_contexts_zip(
        self, zip_bytes, replace_existing=False, force_agent=None,
        require_selected_scope=False,
    ):
        """Import contexts from a ZIP export (reads manifest.json when present)."""
        ensure_ai_admin(self.env)
        zip_buffer = io.BytesIO(zip_bytes)
        manifest = self._read_zip_manifest(zip_buffer)
        scope = (manifest or {}).get('scope', '')
        warnings = []
        allowed_codes = None

        if require_selected_scope:
            if not scope.startswith('sel-'):
                raise UserError(_(
                    'ZIP must come from "Export selected contexts to ZIP" '
                    '(manifest scope sel-*).'
                ))
            allowed_codes = {
                c['code'] for c in manifest.get('contexts', []) if c.get('code')
            }
            if not allowed_codes:
                warnings.append(_('Manifest lists no context codes.'))

        agent_manifest = (manifest or {}).get('agent') or {}
        if force_agent and agent_manifest.get('code') and agent_manifest['code'] != force_agent.code:
            warnings.append(_(
                'Manifest agent is "%s"; contexts were assigned to target agent "%s".'
            ) % (agent_manifest['code'], force_agent.code))

        zip_buffer.seek(0)
        file_stats = self.import_contexts_from_zip_buffer(
            zip_buffer,
            replace_existing=replace_existing,
            force_agent=force_agent,
            allowed_codes=allowed_codes,
        )
        return {
            'files': file_stats,
            'manifest': {
                'scope': scope,
                'context_count': len(manifest.get('contexts', [])),
            },
            'warnings': warnings,
        }

    @api.model
    def import_agent_contexts_zip(self, agent, zip_bytes, replace_existing=False):
        """Import an agent contexts export ZIP into the target agent."""
        ensure_ai_admin(self.env)
        agent.ensure_one()
        return self.import_contexts_zip(
            zip_bytes,
            replace_existing=replace_existing,
            force_agent=agent,
        )

    @api.model
    def _build_context_zip_import_report_html(self, result, title=None):
        files = result['files']
        manifest = result.get('manifest') or {}
        warnings = result.get('warnings') or []
        errors = files.get('errors') or []
        success_count = files['imported'] + files['updated']
        status_class, status_icon, status_text, _ntype = pns_ui.derive_operation_status(
            errors,
            success_count,
            failed_text=_('Import failed.'),
            warnings_text=_('Import completed with warnings.'),
            success_text=_('Import completed successfully.'),
            extra_warnings=warnings,
        )
        sections = []
        if manifest.get('scope'):
            manifest_rows = [(_('Scope'), manifest['scope'])]
            if manifest.get('context_count'):
                manifest_rows.append(
                    (_('Contexts in manifest'), manifest['context_count']),
                )
            sections.append({'title': _('Manifest'), 'rows': manifest_rows})
        sections.append({
            'title': _('Context files'),
            'rows': [
                (_('Created'), files['imported']),
                (_('Updated'), files['updated']),
                (_('Skipped (existing, not replaced)'), files['skipped']),
                (_('Skipped (not in manifest)'), files.get('skipped_manifest', 0)),
                (_('Protocol (protected)'), files['protocol_skipped']),
            ],
        })
        return pns_ui.build_operation_report_html(
            title,
            status_text,
            status_class,
            status_icon,
            sections=sections,
            errors=errors,
            warnings=warnings,
        )

    def action_open_import_zip_wizard(self):
        ensure_ai_admin(self.env)
        return self._action_open_context_import_wizard('zip')

    def action_open_import_selected_zip_wizard(self):
        ensure_ai_admin(self.env)
        return self._action_open_context_import_wizard('zip_selected')

    @api.model
    def _action_open_context_import_wizard(self, import_mode):
        titles = {
            'zip': _('Import contexts from ZIP'),
            'zip_selected': _('Import selected contexts from ZIP'),
        }
        return {
            'type': 'ir.actions.act_window',
            'name': titles.get(import_mode, _('Import contexts')),
            'res_model': 'ai.context.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_import_mode': import_mode},
        }

    @api.model
    def import_agent_zip(
        self, agent, zip_bytes, replace_existing=False, replace_composition=True,
    ):
        """Import a context pack ZIP into the target agent (files + composition)."""
        ensure_ai_admin(self.env)
        agent.ensure_one()
        zip_buffer = io.BytesIO(zip_bytes)
        manifest = {}
        warnings = []

        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            if 'manifest.json' in zf.namelist():
                try:
                    manifest = json.loads(
                        zf.read('manifest.json').decode('utf-8'),
                    )
                except Exception as exc:
                    warnings.append(_('Invalid manifest.json: %s') % exc)

        zip_buffer.seek(0)
        file_stats = self.import_contexts_from_zip_buffer(
            zip_buffer,
            replace_existing=replace_existing,
            force_agent=None,
        )

        composition_stats = {
            'applied': 0, 'missing_codes': [], 'removed': 0, 'manifest_agent': None,
        }
        agent_manifest = (manifest or {}).get('agent') or {}
        composition_stats['manifest_agent'] = agent_manifest.get('code')
        context_codes = agent_manifest.get('context_codes') or []

        if agent_manifest.get('code') and agent_manifest.get('code') != agent.code:
            warnings.append(_(
                'Manifest agent is "%s"; composition is applied to "%s".'
            ) % (agent_manifest['code'], agent.code))

        if replace_composition and context_codes:
            before_ids = set(agent.context_ids.ids)
            contexts = self.search([
                ('code', 'in', context_codes),
                ('active', '=', True),
            ])
            found_codes = set(contexts.mapped('code'))
            composition_stats['missing_codes'] = sorted(
                set(context_codes) - found_codes,
            )
            canonical_ids = self.normalize_context_ids(contexts)
            agent.write({'context_ids': [(6, 0, canonical_ids)]})
            composition_stats['applied'] = len(canonical_ids)
            composition_stats['removed'] = len(before_ids - set(canonical_ids))
            agent._sync_composition_and_cache()
        elif context_codes and not replace_composition:
            warnings.append(_(
                'Composition from manifest was not applied (replace composition is off).'
            ))

        return {
            'files': file_stats,
            'composition': composition_stats,
            'warnings': warnings,
        }

    def _build_contexts_zip_bytes(self, records, scope_label, agent=None):
        """Build contexts export ZIP payload (no UI). Returns None if empty."""
        records = records.exists()
        if not records:
            return None
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            manifest = self._build_export_manifest(
                records, scope_label, agent=agent,
            )
            zip_file.writestr(
                'manifest.json',
                json.dumps(manifest, indent=2, ensure_ascii=False),
            )
            for record in records:
                zip_path, ext = self._zip_path_for_record(record)
                zip_file.writestr(
                    zip_path,
                    self._export_content_for_record(record, ext),
                )
        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    def _export_records_to_zip(self, records, scope_label, agent=None, title='Export'):
        records = records.exists()
        if not records:
            return pns_ui.open_json_export_empty_wizard(
                self.env,
                dialog_title=title,
                message=_('No contexts to export.'),
            )

        zip_filename = self._contexts_zip_filename(scope_label)
        payload = self._build_contexts_zip_bytes(records, scope_label, agent=agent)
        attachment = pns_ui.write_export_attachment(
            self.env, zip_filename, payload, 'application/zip',
        )
        return pns_ui.open_json_export_wizard(
            self.env,
            dialog_title=title,
            summary_text=_('%s context(s) exported to ZIP.') % len(records),
            count=len(records),
            attachment=attachment,
        )

    @api.model
    def export_all_to_zip(self):
        """Export all contexts to ZIP with manifest."""
        ensure_ai_admin(self.env)
        return self._export_records_to_zip(self.search([]), 'all', title='Export All')

    def action_export_selected(self):
        """Export selected list rows to ZIP."""
        ensure_ai_admin(self.env)
        active_ids = self.env.context.get('active_ids') or self.ids
        records = self.browse(active_ids).exists()
        if not records:
            raise UserError(_('Select at least one context to export.'))
        return records._export_records_to_zip(
            records, 'sel-%d' % len(records), title='Export Selected',
        )

    @api.model
    def export_agent_contexts_to_zip(self, agent):
        """Export all contexts composed by an AI agent (its M2M members)."""
        ensure_ai_admin(self.env)
        records = agent.context_ids
        return self._export_records_to_zip(
            records, 'agent-%s' % agent.code, agent=agent, title='Export Agent Contexts',
        )
