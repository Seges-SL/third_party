# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""MCP UI layer: re-exports pns_base and adds domain reports/helpers."""

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
