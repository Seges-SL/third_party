# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# Archivo: models/operation_report_wizard.py
# Descripción: Mixin para wizards que muestran resultado de operación masiva.

from odoo import fields, models, _

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

    def _show_operation_report(self, html, title=None):
        """Legacy: informe HTML generado en Python. Preferir _apply_operation_result."""
        self.ensure_one()
        self.result_html = html
        return self._reopen_operation_wizard(title=title or _('Operation result'))
