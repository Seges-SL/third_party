# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Mixin for wizards that show a bulk-operation result."""

from odoo import api, fields, models, _
from odoo.tools import html_sanitize

from odoo.addons.pns_base.utils import ui_feedback as pns_ui


class PnsOperationReportWizard(models.AbstractModel):
    _name = 'pns.operation.report.wizard'
    _description = 'Wizard with operation result report'

    show_result = fields.Boolean(default=False)
    result_status = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('warning', 'Warning'),
            ('danger', 'Danger'),
        ],
        readonly=True,
    )
    result_created = fields.Integer(string='Created', readonly=True)
    result_updated = fields.Integer(string='Updated', readonly=True)
    result_skipped = fields.Integer(string='Skipped', readonly=True)
    result_removed = fields.Integer(string='Removed', readonly=True)
    result_linked = fields.Integer(string='Linked', readonly=True)
    result_manifest = fields.Char(string='Manifest', readonly=True)
    result_errors = fields.Text(string='Errors', readonly=True)
    result_warnings = fields.Text(string='Warnings', readonly=True)
    result_detail = fields.Text(string='Details', readonly=True)

    # Legacy: informes dinámicos (cache rebuild, export JSON, estadísticas).
    result_html = fields.Html(string='Result', readonly=True, sanitize=False)

    # The report HTML is built by platform code under sudo. Anything a user
    # sends by RPC is sanitized: in Odoo 14 another user can open the record.
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            for vals in vals_list:
                if vals.get('result_html'):
                    vals['result_html'] = html_sanitize(vals['result_html'])
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and vals.get('result_html'):
            vals = dict(vals, result_html=html_sanitize(vals['result_html']))
        return super().write(vals)

    def _apply_operation_result(
        self,
        *,
        view_xmlid,
        errors=None,
        warnings=None,
        success_count=None,
        created=0,
        updated=0,
        skipped=0,
        removed=0,
        linked=0,
        manifest=None,
        detail=None,
        title=None,
    ):
        """Escribe contadores/estado y reabre la vista XML de resultado."""
        self.ensure_one()
        errors = list(errors or [])
        warnings = list(warnings or [])
        if success_count is None:
            success_count = created + updated
        self.write({
            'show_result': True,
            'result_status': pns_ui.derive_result_status(
                errors, success_count, extra_warnings=warnings,
            ),
            'result_created': created,
            'result_updated': updated,
            'result_skipped': skipped,
            'result_removed': removed,
            'result_linked': linked,
            'result_manifest': manifest or False,
            'result_errors': '\n'.join(errors) if errors else False,
            'result_warnings': '\n'.join(warnings) if warnings else False,
            'result_detail': detail or False,
        })
        return self._reopen_result_view(view_xmlid, title=title)

    def _reopen_result_view(self, view_xmlid, title=None):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': title or _('Operation result'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref(view_xmlid).id, 'form')],
            'target': 'new',
        }

    def _reopen_operation_wizard(self, title=None):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': title or _('Operation result'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }
