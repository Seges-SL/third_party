# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""MCP UI layer: re-exports pns_base and adds domain reports/helpers."""

from odoo import _

from odoo.addons.pns_base.utils import portable_io as pio
from odoo.addons.pns_base.utils import ui_feedback as pns_ui

client_notification = pns_ui.client_notification
build_operation_report_html = pns_ui.build_operation_report_html
derive_operation_status = pns_ui.derive_operation_status
build_plain_operation_message = pns_ui.build_plain_operation_message

_WIZARD = 'ai.json.export.wizard'


def build_export_filename(env, artifact, ext, tag=None, secrets=False):
    """MCP name: ``YYYYmmddTHHMMSS_<db>[_tag]_<artifact>[_secrets].<ext>``."""
    return pio.build_export_filename(
        env, artifact, ext, tag=tag, style='mcp', secrets=secrets,
    )


def extract_json_from_upload(raw_bytes, *, expect_list=True):
    return pio.extract_json_from_upload(raw_bytes, expect_list=expect_list)


def write_json_attachment(env, filename, data, res_model=None, res_id=0):
    return pio.write_json_attachment(
        env, filename, data, res_model=res_model, res_id=res_id,
    )


def write_export_attachment(
    env, filename, raw_bytes, mimetype, res_model=None, res_id=0,
):
    return pio.write_export_attachment(
        env, filename, raw_bytes, mimetype,
        res_model=res_model, res_id=res_id,
    )


def created_updated_skipped_rows(created=0, updated=0, skipped=0, extra_rows=None):
    rows = [
        (_('Created'), created),
        (_('Updated'), updated),
        (_('Skipped (already existed)'), skipped),
    ]
    if extra_rows:
        rows.extend(extra_rows)
    return rows


def build_json_import_report(
    title,
    created=0,
    updated=0,
    skipped=0,
    *,
    errors=None,
    warnings=None,
    extra_rows=None,
    sections=None,
    footer_html=None,
    failed_text=None,
    warnings_text=None,
    success_text=None,
):
    errors = list(errors or [])
    extra_warnings = list(warnings or [])
    success_count = created + updated
    status_class, status_icon, status_text, _ntype = pns_ui.derive_operation_status(
        errors,
        success_count,
        failed_text=failed_text or _('Import failed.'),
        warnings_text=warnings_text or _('Import completed with warnings.'),
        success_text=success_text or _('Import completed successfully.'),
        extra_warnings=extra_warnings,
    )
    rows = created_updated_skipped_rows(created, updated, skipped, extra_rows=extra_rows)
    report_sections = None
    if sections:
        report_sections = [{'title': _('Summary'), 'rows': rows}] + list(sections)
    return pns_ui.build_operation_report_html(
        title,
        status_text,
        status_class,
        status_icon,
        rows=rows if not report_sections else None,
        sections=report_sections,
        errors=errors,
        warnings=extra_warnings,
        footer_html=footer_html,
    )


def build_json_export_report(count, filename, *, success_text=None):
    return pio.build_json_export_report(
        count, filename, success_text=success_text,
    )


def open_json_export_wizard(env, *, dialog_title, summary_text, count, attachment):
    return pio.open_export_wizard(
        env,
        dialog_title=dialog_title,
        summary_text=summary_text,
        count=count,
        attachment=attachment,
        wizard_model=_WIZARD,
    )


def open_json_export_empty_wizard(env, *, dialog_title, message):
    return pio.open_export_empty_wizard(
        env, dialog_title=dialog_title, message=message, wizard_model=_WIZARD,
    )


def client_notification_close(title, message, notification_type='success'):
    action = client_notification(
        title, message, notification_type, sticky=False,
    )
    action['params']['next'] = {'type': 'ir.actions.act_window_close'}
    return action


def warning_notification(title, message):
    return client_notification(title, message, 'warning', sticky=False)
