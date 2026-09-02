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


class ImportWhitelistWizard(models.TransientModel):
    """Wizard to import URL whitelist entries from a JSON file.

    JSON format (array of objects)::

        [
            {"domain": "api.example.com", "active": true, "notes": "Currency"},
            {"domain": "wttr.in", "active": true, "valid_until": null}
        ]

    With 'Replace existing' checked (default), entries with the same domain
    are updated.  Otherwise existing domains are skipped.
    """
    _name = 'pns_ai_mcp.import_whitelist_wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'Wizard to import URL Whitelist from JSON'

    json_file = fields.Binary(string='JSON File', required=True, attachment=True)
    filename = fields.Char(string='File name')
    replace_existing = fields.Boolean(
        string='Replace existing',
        default=True,
        help='If checked, domains already in the whitelist will be updated. Otherwise, they will be skipped.',
    )
    def action_import(self):
        """Process the uploaded file and import/update whitelist entries.

        Accepts ``.json`` or ``.zip`` (containing .json files inside).
        Each JSON entry is matched by ``domain`` (case-insensitive).

        Resilience guarantees:
            - Unknown keys in JSON are silently ignored.
            - Invalid datetime strings are caught per-entry (not fatal).
            - Entries without a ``domain`` field are skipped with a warning.
            - Any per-entry exception is logged and collected, never aborts.

        Returns:
            dict: Odoo action showing the operation report wizard with
                  created/updated/skipped counters and any errors/warnings.
        """
        self.ensure_one()
        if not self.json_file:
            raise UserError(_("Please upload a JSON file."))

        try:
            raw = base64.b64decode(self.json_file)
            data, extract_warnings = mcp_ui.extract_json_from_upload(raw)
        except (ValueError, Exception) as e:
            raise UserError(_("Error reading the file: %s") % e)

        Whitelist = self.env['ai.url.whitelist']
        created = updated = skipped = 0
        errors = []
        warnings = list(extract_warnings)

        for entry in data:
            domain = (entry.get('domain') or '').strip().lower()
            if not domain:
                errors.append(_("Entry without 'domain' field skipped."))
                continue
            try:
                existing = Whitelist.with_context(active_test=False).search(
                    [('domain', '=', domain)], limit=1,
                )
                if existing and not self.replace_existing:
                    skipped += 1
                    continue

                vals = {'domain': domain}
                for fld in ('active', 'notes'):
                    if fld in entry:
                        vals[fld] = entry[fld]
                for dt_fld in ('valid_from', 'valid_until'):
                    raw_val = entry.get(dt_fld)
                    if raw_val:
                        vals[dt_fld] = fields.Datetime.to_datetime(raw_val)
                    elif dt_fld in entry:
                        vals[dt_fld] = False

                if existing:
                    existing.write(vals)
                    updated += 1
                else:
                    Whitelist.create(vals)
                    created += 1
            except Exception as e:
                errors.append("%s: %s" % (domain, e))
                _logger.error("Whitelist import error for %s: %s", domain, e)

        return self._apply_operation_result(
            view_xmlid='pns_ai_mcp.view_import_whitelist_result_form',
            created=created,
            updated=updated,
            skipped=skipped,
            errors=errors,
            warnings=warnings,
        )
