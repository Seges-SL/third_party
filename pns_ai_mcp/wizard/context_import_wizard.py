# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
import base64
import io
import zipfile
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

from .operation_result import context_zip_files_to_result

_logger = logging.getLogger(__name__)


class ContextImportWizard(models.TransientModel):
    _name = 'pns_ai_mcp.context_import_wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'Wizard to import Custom Contexts from files'

    import_file = fields.Binary(
        string='File', required=True, attachment=True,
        help='Upload a .txt, .md, .xml or .zip file',
    )
    filename = fields.Char(string='File name')
    replace_existing = fields.Boolean(
        string='Replace existing',
        default=False,
        help='When checked, contexts with the same code and path will be updated. Otherwise they will be skipped.',
    )
    import_mode = fields.Selection(
        [
            ('', 'General'),
            ('zip', 'Contexts ZIP'),
            ('zip_selected', 'Selected contexts ZIP'),
        ],
        string='Import mode',
        readonly=True,
        default='',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        mode = self.env.context.get('default_import_mode')
        if mode in ('zip', 'zip_selected'):
            res['import_mode'] = mode
        return res

    def _import_zip_with_report(self, file_content, require_selected_scope=False):
        self.ensure_one()
        Context = self.env['ai.context']
        result = Context.import_contexts_zip(
            file_content,
            replace_existing=self.replace_existing,
            require_selected_scope=require_selected_scope,
        )
        vals = context_zip_files_to_result(result['files'], warnings=result.get('warnings'))
        return self._apply_operation_result(
            view_xmlid='pns_ai_mcp.view_context_import_result_form',
            **vals,
        )

    def action_import(self):
        """
        Procesa el archivo (TXT, MD, XML, o ZIP), lee los contextos y los importa/actualiza.
        Si replace_existing=True, sobrescribe existentes (mismo code + rel_path).
        """
        self.ensure_one()
        if not self.import_file:
            raise UserError(_("Please upload a file (.txt, .md, .xml or .zip)."))

        try:
            file_content = base64.b64decode(self.import_file)
            filename = self.filename or 'unknown'

            if self.import_mode in ('zip', 'zip_selected'):
                if not filename.lower().endswith('.zip'):
                    raise UserError(_('Please upload a .zip export file.'))
                return self._import_zip_with_report(
                    file_content,
                    require_selected_scope=(self.import_mode == 'zip_selected'),
                )

            imported_count = 0
            updated_count = 0
            skipped_count = 0
            protocol_skipped_count = 0
            errors = []

            if filename.endswith('.zip'):
                zip_buffer = io.BytesIO(file_content)
                with zipfile.ZipFile(zip_buffer, 'r') as zf:
                    for file_info in zf.infolist():
                        if not file_info.filename.endswith(('.txt', '.md', '.xml')):
                            continue
                        if file_info.filename.startswith('__MACOSX') or '/.' in file_info.filename:
                            continue
                        try:
                            content = zf.read(file_info.filename).decode('utf-8')
                            zip_path = file_info.filename.replace('\\', '/')
                            result = self.env['ai.context'].import_context_file(
                                file_info.filename, content, zip_path=zip_path,
                                replace_existing=self.replace_existing,
                            )
                            if result['action'] == 'imported':
                                imported_count += 1
                            elif result['action'] == 'updated':
                                updated_count += 1
                            elif result['action'] == 'skipped':
                                skipped_count += 1
                            elif result['action'] == 'protocol_skipped':
                                protocol_skipped_count += 1
                            elif result['action'] == 'error':
                                errors.append(result['message'])
                        except Exception as exc:
                            errors.append("%s: %s" % (file_info.filename, exc))
            else:
                if filename.endswith(('.txt', '.md', '.xml')):
                    content = file_content.decode('utf-8')
                    result = self.env['ai.context'].import_context_file(
                        filename, content, zip_path=None,
                        replace_existing=self.replace_existing,
                    )
                    if result['action'] == 'imported':
                        imported_count += 1
                    elif result['action'] == 'updated':
                        updated_count += 1
                    elif result['action'] == 'skipped':
                        skipped_count += 1
                    elif result['action'] == 'protocol_skipped':
                        protocol_skipped_count += 1
                    elif result['action'] == 'error':
                        errors.append(result['message'])
                else:
                    raise UserError(_("Unsupported file format. Use .txt, .md, .xml or .zip"))

            return self._apply_operation_result(
                view_xmlid='pns_ai_mcp.view_context_import_result_form',
                created=imported_count,
                updated=updated_count,
                skipped=skipped_count,
                removed=protocol_skipped_count,
                errors=errors,
            )

        except zipfile.BadZipFile:
            raise UserError(_("The file is not a valid ZIP."))
        except UserError:
            raise
        except Exception as e:
            raise UserError(_('Error processing file: %s') % e)
