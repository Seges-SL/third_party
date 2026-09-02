# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
import base64
import json
import logging

from odoo import api, models, fields, _
from odoo.exceptions import UserError

from ..utils.compat import format_login_name_line
from ..utils import mcp_ui

_logger = logging.getLogger(__name__)


class ImportUsersWizard(models.TransientModel):
    _name = 'pns_ai_mcp.import_users_wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'Wizard to import MCP Users from JSON'

    json_file = fields.Binary(string='JSON File', required=True, attachment=True)
    filename = fields.Char(string='File name')
    replace_existing = fields.Boolean(
        string='Replace existing',
        default=True,
        help='If checked, users with the same login are fully updated (including API key). '
             'If unchecked, existing rows are skipped unless they have no API key yet.',
    )
    def action_import(self):
        """Process JSON file and import/update MCP users."""
        self.ensure_one()
        if not self.json_file:
            raise UserError(_("Please upload a JSON file."))

        try:
            json_content = base64.b64decode(self.json_file)
            json_data, extract_warnings = mcp_ui.extract_json_from_upload(json_content)
        except (ValueError, Exception) as e:
            raise UserError(_("Error reading the file: %s") % e)

        created_count = 0
        updated_count = 0
        skipped_count = 0
        keys_imported_count = 0
        missing_logins = []
        other_errors = []

        user_model = self.env['ai.mcp.user']
        res_users_model = self.env['res.users']

        for user_data in json_data:
            login = ''
            try:
                login = (user_data.get('login') or '').strip()
                if not login:
                    other_errors.append(
                        _("User without login: %s")
                        % (user_data.get('name') or _('Unnamed'))
                    )
                    continue

                odoo_user = res_users_model.search([('login', '=', login)], limit=1)
                if not odoo_user:
                    missing_logins.append(
                        format_login_name_line(
                            self.env,
                            login,
                            user_data.get('name'),
                        )
                    )
                    continue

                # _import_vals_from_json_row returns (vals, has_key, warnings)
                result = user_model._import_vals_from_json_row(user_data)
                if len(result) == 3:
                    vals, has_key, row_warnings = result
                else:
                    # Backwards compat if old signature (vals, has_key)
                    vals, has_key = result
                    row_warnings = []
                vals['user_id'] = odoo_user.id

                # Report field-level warnings but NEVER skip the user
                for w in row_warnings:
                    other_errors.append("%s: (warn) %s" % (login, w))

                existing = user_model.search([('user_id', '=', odoo_user.id)], limit=1)

                if existing:
                    if self.replace_existing:
                        try:
                            existing.sudo().write(vals)
                        except Exception as we:
                            # If full write fails, try field by field
                            _logger.warning("MCP import: full write failed for %s: %s, trying field-by-field", login, we)
                            for k, v in vals.items():
                                try:
                                    existing.sudo().write({k: v})
                                except Exception as fe:
                                    other_errors.append("%s: field '%s' failed: %s" % (login, k, fe))
                        updated_count += 1
                        if has_key:
                            keys_imported_count += 1
                    elif has_key and not (existing.mcp_api_key_hash or '').strip():
                        key_vals = {
                            k: v for k, v in vals.items()
                            if k.startswith('mcp_api_key')
                        }
                        try:
                            existing.sudo().write(key_vals)
                        except Exception as we:
                            other_errors.append("%s: API key write failed: %s" % (login, we))
                        updated_count += 1
                        keys_imported_count += 1
                    else:
                        skipped_count += 1
                else:
                    try:
                        user_model.sudo().create(vals)
                    except Exception as ce:
                        # If create fails, try without optional fields
                        _logger.warning("MCP import: create failed for %s: %s, retrying minimal", login, ce)
                        minimal = {k: v for k, v in vals.items()
                                   if k in ('user_id', 'mcp_api_key_hash', 'mcp_api_key_state', 'mcp_api_key_generated_date')}
                        try:
                            user_model.sudo().create(minimal)
                        except Exception as ce2:
                            other_errors.append("%s: create failed: %s" % (login, ce2))
                            continue
                    created_count += 1
                    if has_key:
                        keys_imported_count += 1

            except Exception as e:
                login = login or user_data.get('login') or _('no login')
                other_errors.append("%s: %s" % (login, e))
                _logger.error("MCP: error importing user %s: %s", login, e)

        return self._apply_operation_result(
            view_xmlid='pns_ai_mcp.view_import_users_result_form',
            created=created_count,
            updated=updated_count,
            skipped=skipped_count,
            linked=keys_imported_count,
            errors=other_errors,
            detail='\n'.join(missing_logins) if missing_logins else None,
        )
