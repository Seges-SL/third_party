# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Transient wizard: ask, on every export, whether secrets go in the file."""
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_METHOD_PREFIX = '_pns_export_'


class PnsExportSecretsWizard(models.TransientModel):
    _name = 'pns.export.secrets.wizard'
    _description = 'Ask whether an export carries secrets'

    res_model = fields.Char(readonly=True)
    res_ids = fields.Char(readonly=True)
    method = fields.Char(readonly=True)
    include_secrets = fields.Boolean(
        string='Include secrets',
        default=False,
        help='Adds API keys and tokens in clear text to the exported file.',
    )

    @api.model
    def ask(self, records, method):
        """Open the question; the answer calls ``records.<method>(include_secrets)``."""
        if not method.startswith(_METHOD_PREFIX):
            raise UserError(_('This export cannot ask for secrets.'))
        wizard = self.create({
            'res_model': records._name,
            'res_ids': json.dumps(records.ids),
            'method': method,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Export'),
            'res_model': self._name,
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }

    def action_export(self):
        self.ensure_one()
        method = self.method or ''
        if not method.startswith(_METHOD_PREFIX) or self.res_model not in self.env:
            raise UserError(_('This export cannot ask for secrets.'))
        target = self.env[self.res_model].browse(json.loads(self.res_ids or '[]'))
        export = getattr(target.exists(), method, None)
        if export is None:
            raise UserError(_('This export cannot ask for secrets.'))
        return export(include_secrets=self.include_secrets)
