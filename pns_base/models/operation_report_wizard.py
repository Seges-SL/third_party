# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Mixin for wizards that show a bulk-operation result."""

import ast
import json

from lxml import etree

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import html_sanitize

from odoo.addons.pns_base.utils import ui_feedback as pns_ui

_PREVIEW_SAVEPOINT = 'pns_import_preview'


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
    result_created_names = fields.Text(string='Will create', readonly=True)
    result_updated_names = fields.Text(string='Will replace', readonly=True)
    result_skipped_names = fields.Text(string='Will leave', readonly=True)
    result_removed = fields.Integer(string='Removed', readonly=True)
    result_linked = fields.Integer(string='Linked', readonly=True)
    result_manifest = fields.Char(string='Manifest', readonly=True)
    result_errors = fields.Text(string='Errors', readonly=True)
    result_warnings = fields.Text(string='Warnings', readonly=True)
    result_detail = fields.Text(string='Details', readonly=True)
    result_params = fields.Text(string='Options', readonly=True)

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

    def _store_operation_result(
        self,
        *,
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
        created_names=None,
        updated_names=None,
        skipped_names=None,
        params=None,
    ):
        self.ensure_one()
        errors = list(errors or [])
        warnings = list(warnings or [])
        if success_count is None:
            success_count = created + updated
        vals = {
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
            'result_created_names': self._name_list_text(created_names),
            'result_updated_names': self._name_list_text(updated_names),
            'result_skipped_names': self._name_list_text(skipped_names),
            'result_detail': self._compose_result_detail(detail),
        }
        if params is not None:
            vals['result_params'] = params or False
        self.write(vals)

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
        created_names=None,
        updated_names=None,
        skipped_names=None,
        params=None,
        title=None,
    ):
        """Escribe contadores/estado y reabre la vista XML de resultado."""
        self._store_operation_result(
            errors=errors,
            warnings=warnings,
            success_count=success_count,
            created=created,
            updated=updated,
            skipped=skipped,
            removed=removed,
            linked=linked,
            manifest=manifest,
            detail=detail,
            created_names=created_names,
            updated_names=updated_names,
            skipped_names=skipped_names,
            params=params,
        )
        return self._reopen_result_view(view_xmlid, title=title)

    def _preview_param_text(self):
        """Boolean import flags on this wizard, one line each."""
        lines = []
        for name, field in self._fields.items():
            if name in ('show_result',) or getattr(field, 'type', None) != 'boolean':
                continue
            if not (name.startswith('replace_') or name in ('overwrite',)):
                continue
            label = field.string or name
            if self[name]:
                lines.append(_('%s is on') % label)
            else:
                lines.append(_('%s is off') % label)
        return '\n'.join(lines) if lines else False

    def _name_list_text(self, names):
        """One name per line. Empty list is omitted."""
        names = [str(n).strip() for n in (names or []) if n]
        if not names:
            return False
        return '\n'.join('- %s' % n for n in names)

    def _names_from_stored(self, text):
        if not text:
            return None
        out = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith('- '):
                line = line[2:]
            if line:
                out.append(line)
        return out or None

    def _name_bucket_detail(self, created=None, updated=None, skipped=None):
        """Names in each bucket. Empty buckets are omitted."""
        def block(title, names):
            text = self._name_list_text(names)
            if not text:
                return ''
            return '%s\n%s' % (title, text)

        parts = [
            block(self._preview_bucket_title('created'), created),
            block(self._preview_bucket_title('updated'), updated),
            block(self._preview_bucket_title('skipped'), skipped),
        ]
        return '\n\n'.join(p for p in parts if p) or False

    def _preview_bucket_title(self, kind):
        return {
            'created': _('Will create'),
            'updated': _('Will replace'),
            'skipped': _('Will leave'),
        }[kind]

    def _compose_result_detail(self, detail=None):
        extra = str(detail).strip() if detail else ''
        return extra or False

    def _apply_import_preview(self, view_xmlid=None, title=None, **kwargs):
        """Show what the file would do. Prefer a wizard-specific view."""
        title = title or _('Review this import')
        kwargs = dict(kwargs)
        if kwargs.get('params') is None:
            kwargs['params'] = self._preview_param_text()
        if view_xmlid:
            view = self.env.ref(view_xmlid, raise_if_not_found=False)
            if view and view.model == self._name:
                return self._apply_operation_result(
                    view_xmlid=view_xmlid, title=title, **kwargs)
        self._store_operation_result(**kwargs)
        return self._reopen_import_preview(title=title)

    def _window_context(self, extra=None):
        ctx = dict(self.env.context)
        # False must be set: a missing key loses to the parent True.
        ctx['pns_import_preview'] = False
        ctx['pns_operation_result'] = False
        if extra:
            ctx.update(extra)
        return ctx

    def _reopen_result_view(self, view_xmlid, title=None):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': title or _('Operation result'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': self._window_context({'pns_operation_result': True}),
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
            'context': self._window_context(),
        }

    def _reopen_import_preview(self, title=None):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': title or _('Review this import'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': self._window_context({'pns_import_preview': True}),
        }

    def _preview_snapshot(self):
        self.ensure_one()
        errors = [line for line in (self.result_errors or '').splitlines() if line]
        warnings = [line for line in (self.result_warnings or '').splitlines() if line]
        return {
            'created': self.result_created,
            'updated': self.result_updated,
            'skipped': self.result_skipped,
            'removed': self.result_removed,
            'linked': self.result_linked,
            'manifest': self.result_manifest or None,
            'errors': errors,
            'warnings': warnings,
            'detail': self.result_detail or None,
            'created_names': self._names_from_stored(self.result_created_names),
            'updated_names': self._names_from_stored(self.result_updated_names),
            'skipped_names': self._names_from_stored(self.result_skipped_names),
        }

    def _invalidate_after_preview_rollback(self):
        self.invalidate_cache()

    def _wizard_defines_import(self):
        for cls in type(self).mro():
            if cls is PnsOperationReportWizard:
                break
            if 'action_import' in cls.__dict__:
                return True
        return False

    def action_import(self):
        """Hook for the review view. Concrete wizards override this."""
        raise UserError(_("This wizard has no import to review."))

    def action_preview(self):
        """Count what the file would do. Nothing is kept."""
        self.ensure_one()
        if not self._wizard_defines_import():
            raise UserError(_("This wizard has no import to review."))
        cr = self.env.cr
        cr.execute('SAVEPOINT %s' % _PREVIEW_SAVEPOINT)
        try:
            self.with_context(pns_import_preview=False).action_import()
            snap = self._preview_snapshot()
        except Exception:
            cr.execute('ROLLBACK TO SAVEPOINT %s' % _PREVIEW_SAVEPOINT)
            cr.execute('RELEASE SAVEPOINT %s' % _PREVIEW_SAVEPOINT)
            self._invalidate_after_preview_rollback()
            raise
        cr.execute('ROLLBACK TO SAVEPOINT %s' % _PREVIEW_SAVEPOINT)
        cr.execute('RELEASE SAVEPOINT %s' % _PREVIEW_SAVEPOINT)
        self._invalidate_after_preview_rollback()
        return self._apply_import_preview(**snap)

    def _stamp_view_modifiers(self, node):
        """Odoo 14 hides attrs only if modifiers are on the node."""
        for el in node.iter():
            mods = {}
            raw = el.get('attrs')
            if raw:
                try:
                    parsed = ast.literal_eval(raw)
                except (ValueError, SyntaxError):
                    parsed = None
                if isinstance(parsed, dict):
                    mods.update(parsed)
            if el.get('invisible') in ('1', 'True', 'true'):
                mods['invisible'] = True
            if el.get('readonly') in ('1', 'True', 'true'):
                mods['readonly'] = True
            if mods:
                el.set('modifiers', json.dumps(mods))

    def _prepare_import_preview_arch(self, arch):
        node = etree.fromstring(arch)
        self._stamp_view_modifiers(node)
        return etree.tostring(node, encoding='unicode')

    def _inject_import_preview_arch(self, result):
        src = self.env.ref('pns_base.view_pns_import_preview_form')
        result = dict(result)
        result['arch'] = self._prepare_import_preview_arch(src.arch)
        return result

    def _inject_operation_result_arch(self, result):
        src = self.env.ref('pns_base.view_pns_operation_result_form')
        result = dict(result)
        result['arch'] = self._prepare_import_preview_arch(src.arch)
        return result

    def _stamp_review_button(self, arch):
        node = etree.fromstring(arch)
        changed = False
        for btn in node.xpath("//button[@name='action_preview']"):
            btn.set('string', _('Review this import'))
            changed = True
        if not changed:
            return arch
        return etree.tostring(node, encoding='unicode')

    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        if view_type == 'form' and self.env.context.get('pns_import_preview'):
            result = super().fields_view_get(
                view_id=False, view_type='form', toolbar=toolbar, submenu=submenu,
            )
            return self._inject_import_preview_arch(result)
        if view_type == 'form' and self.env.context.get('pns_operation_result'):
            result = super().fields_view_get(
                view_id=False, view_type='form', toolbar=toolbar, submenu=submenu,
            )
            return self._inject_operation_result_arch(result)
        result = super().fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu,
        )
        if view_type == 'form':
            result = dict(result)
            result['arch'] = self._stamp_review_button(result['arch'])
        return result
