# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Capa UI MCP: reexporta pns_base y añade informes/helpers de dominio."""

from odoo import _

from odoo.addons.pns_base.utils import portable_io as pio
from odoo.addons.pns_base.utils import ui_feedback as pns_ui

client_notification = pns_ui.client_notification
build_operation_report_html = pns_ui.build_operation_report_html
derive_operation_status = pns_ui.derive_operation_status
build_plain_operation_message = pns_ui.build_plain_operation_message

_WIZARD = 'pns_ai_mcp.json_export_wizard'


def build_export_filename(env, artifact, ext, tag=None):
    """MCP name: ``YYYYmmddTHHMMSS_<db>[_tag]_<artifact>.<ext>``."""
    return pio.build_export_filename(
        env, artifact, ext, tag=tag, style='mcp',
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


def build_users_import_report(
    created,
    updated,
    skipped,
    keys_imported,
    missing_logins,
    other_errors,
):
    missing_logins = list(missing_logins or [])
    sections = []
    if missing_logins:
        sections.append({
            'title': _('Odoo users not found (%s)') % len(missing_logins),
            'rows': [(login, '') for login in missing_logins],
        })
    footer = None
    if missing_logins:
        footer = (
            '<p class="text-muted" style="font-size:11px;margin-bottom:0;">'
            + _('Create missing users in Settings → Users, then re-import.')
            + '</p>'
        )
    return build_json_import_report(
        None,
        created=created,
        updated=updated,
        skipped=skipped,
        errors=other_errors,
        extra_rows=[(_('API keys applied'), keys_imported)],
        sections=sections or None,
        footer_html=footer,
    )


def build_context_file_import_report(
    imported=0,
    updated=0,
    skipped=0,
    protocol_skipped=0,
    errors=None,
    title=None,
):
    extra_rows = []
    if protocol_skipped:
        extra_rows.append((_('Protocol (protected)'), protocol_skipped))
    return build_json_import_report(
        None,
        created=imported,
        updated=updated,
        skipped=skipped,
        errors=errors,
        extra_rows=extra_rows or None,
    )


def build_template_zip_import_report(imported_count, errors=None):
    return build_json_import_report(
        None,
        created=imported_count,
        errors=errors,
        success_text=_('Import completed.'),
    )


def build_agent_import_report(files, composition, warnings, title=None, footer_html=None):
    errors = list(files.get('errors') or [])
    warnings = list(warnings or [])
    missing_codes = composition.get('missing_codes') or []
    success_count = files['imported'] + files['updated']
    status_class, status_icon, status_text, _ntype = pns_ui.derive_operation_status(
        errors,
        success_count,
        failed_text=_('Import failed.'),
        warnings_text=_('Import completed with warnings.'),
        success_text=_('Import completed successfully.'),
        extra_warnings=warnings + ([
            '%s: %s' % (_('Missing codes'), ', '.join(missing_codes)),
        ] if missing_codes else []),
    )
    sections = [
        {
            'title': _('Context files'),
            'rows': [
                (_('Created'), files['imported']),
                (_('Updated'), files['updated']),
                (_('Skipped (existing, not replaced)'), files['skipped']),
                (_('Protocol (protected)'), files['protocol_skipped']),
            ],
        },
        {
            'title': _('Agent composition'),
            'rows': [
                (_('Manifest composition'), composition.get('manifest_agent') or '—'),
                (_('Contexts linked'), composition.get('applied', 0)),
                (_('Removed from agent'), composition.get('removed', 0)),
            ],
        },
    ]
    return pns_ui.build_operation_report_html(
        title,
        status_text,
        status_class,
        status_icon,
        sections=sections,
        errors=errors,
        warnings=warnings,
        footer_html=footer_html,
    )


def build_cache_rebuild_report(agent, user_locale, before_size, before_updated,
                               before_signature, parts_count, signature_changed,
                               size_changed):
    if signature_changed or size_changed or not before_updated:
        status_class = 'alert-success'
        status_icon = 'fa-check-circle'
        status_text = _('Cache regenerated successfully.')
    else:
        status_class = 'alert-info'
        status_icon = 'fa-info-circle'
        status_text = _('Cache refreshed (content was already up to date).')

    rows = [
        (_('Agent'), agent.code),
        (_('Used by consumers'), ', '.join(agent.agent_ids.mapped('code')) or '—'),
        (_('Locale'), user_locale),
        (_('Contexts in composition'), str(len(agent.context_ids))),
        (_('Resolved parts (locale)'), str(parts_count)),
        (_('Cache size (before)'), agent._format_cache_size(before_size)),
        (_('Cache size (after)'), agent._format_cache_size(
            len((agent.cached_content or '').encode('utf-8')),
        )),
        (_('Previous update'), before_updated and str(before_updated) or '—'),
        (_('New update'), str(agent.cache_updated)),
        (_('Signature changed'), _('Yes') if signature_changed else _('No')),
    ]
    footer = (
        '<p class="text-muted" style="font-size:11px;margin-bottom:0;">'
        '<i class="fa fa-lightbulb-o"></i> '
        + _('Editing a context or changing composition invalidates the cache '
            'automatically on the next MCP request (signature from write_date). '
            'Use this action after module upgrades or unusual direct edits to '
            'cached fields.')
        + '</p>'
    )
    return pns_ui.build_operation_report_html(
        _('Regenerate cache'),
        status_text,
        status_class,
        status_icon,
        rows=rows,
        footer_html=footer,
    )


def client_notification_close(title, message, notification_type='success'):
    action = client_notification(
        title, message, notification_type, sticky=False,
    )
    action['params']['next'] = {'type': 'ir.actions.act_window_close'}
    return action


def warning_notification(title, message):
    return client_notification(title, message, 'warning', sticky=False)
