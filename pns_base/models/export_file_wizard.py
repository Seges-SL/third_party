# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from odoo import fields, models, _
from odoo.exceptions import UserError


class PnsExportFileWizard(models.TransientModel):
    _name = 'pns.export.file.wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'Export file result wizard'

    attachment_id = fields.Many2one('ir.attachment', string='Attachment', readonly=True)
    export_filename = fields.Char(string='File name', readonly=True)

    def action_download(self):
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_('No file available for download.'))
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % self.attachment_id.id,
            'target': 'self',
        }
