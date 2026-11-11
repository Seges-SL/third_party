# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Transient wizard: download a file produced by a portable export."""
from odoo import fields, models, _
from odoo.exceptions import UserError

from ..utils.portable_io import EXPORT_MARK


class PnsExportFileWizard(models.TransientModel):
    _name = 'pns.export.file.wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'Export file result wizard'

    attachment_id = fields.Many2one('ir.attachment', string='Attachment', readonly=True)
    export_filename = fields.Char(string='File name', readonly=True)

    def unlink(self):
        # attachment_id is writable over RPC: only the caller's own export goes.
        files = self.sudo().mapped('attachment_id').filtered(
            lambda a: a.description == EXPORT_MARK
            and (self.env.su or a.create_uid == self.env.user)
        )
        res = super().unlink()
        files.unlink()
        return res

    def action_download(self):
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_('No file available for download.'))
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % self.attachment_id.id,
            'target': 'self',
        }
