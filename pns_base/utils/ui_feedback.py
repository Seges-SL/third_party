# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Generic HTML reports and client notifications (import / restore / export)."""

import html as html_lib

from odoo import _


def _e(text):
    return html_lib.escape(str(text) if text is not None else '')


def derive_result_status(errors, success_count, extra_warnings=None):
    """Status key for XML views: success | warning | danger."""
    errors = list(errors or [])
    extra_warnings = list(extra_warnings or [])
    if errors and not success_count:
        return 'danger'
    if errors or extra_warnings:
        return 'warning'
    return 'success'


def derive_operation_status(
    errors,
    success_count,
    *,
    failed_text,
    warnings_text,
    success_text,
    extra_warnings=None,
):
    """Return (alert_class, fa_icon, status_text, notification_type)."""
    status = derive_result_status(errors, success_count, extra_warnings=extra_warnings)
    if status == 'danger':
        return 'alert-danger', 'fa-times-circle', failed_text, 'danger'
    if status == 'warning':
        return 'alert-warning', 'fa-exclamation-triangle', warnings_text, 'warning'
    return 'alert-success', 'fa-check-circle', success_text, 'success'


def _render_table(rows, title=None):
    parts = []
    if title:
        parts.append('<h6>%s</h6>' % _e(title))
    parts.append(
        '<table class="table table-sm table-striped" style="margin-bottom:10px;">'
        '<tbody>'
    )
    for label, value in rows or []:
        parts.append(
            '<tr><td><b>%s</b></td><td>%s</td></tr>' % (_e(label), _e(value))
        )
    parts.append('</tbody></table>')
    return ''.join(parts)


def build_operation_report_html(
    title,
    status_text,
    status_class,
    status_icon,
    rows=None,
    *,
    sections=None,
    errors=None,
    warnings=None,
    footer_html=None,
    max_errors=10,
    max_warnings=10,
):
    """Standard HTML report for bulk-operation wizards.

    sections: list of {'title': str, 'rows': [(label, value), ...]}
    """
    html = '<div style="font-size:13px;">'
    if title:
        html += '<h5 style="margin-top:0;">%s</h5>' % _e(title)
    html += (
        '<div class="alert %s" style="padding:8px 12px;margin-bottom:10px;">'
        '<i class="fa %s"></i> <strong>%s</strong></div>'
    ) % (_e(status_class), _e(status_icon), _e(status_text))

    if rows:
        html += _render_table(rows)

    for section in sections or []:
        html += _render_table(
            section.get('rows'),
            title=section.get('title'),
        )

    warnings = list(warnings or [])
    if warnings:
        html += '<h6>%s</h6><ul>' % _e(_('Warnings'))
        for warning in warnings[:max_warnings]:
            html += '<li>%s</li>' % _e(warning)
        html += '</ul>'

    errors = list(errors or [])
    if errors:
        html += '<h6>%s</h6><ul>' % _e(_('Errors'))
        for error in errors[:max_errors]:
            html += '<li>%s</li>' % _e(error)
        html += '</ul>'

    if footer_html:
        html += footer_html

    html += '</div>'
    return html


def build_plain_operation_message(header, rows, errors=None, max_errors=5):
    """Plain text for toasts (display_notification)."""
    lines = [header]
    for label, value in rows or []:
        lines.append('%s: %s' % (label, value))
    errors = list(errors or [])
    if errors:
        lines.append('')
        lines.append(_('Errors (%s):') % len(errors))
        for err in errors[:max_errors]:
            lines.append('  • %s' % err)
    return '\n'.join(lines)


def client_notification(
    title,
    message,
    notification_type='success',
    *,
    sticky=True,
    reload=False,
):
    """ir.actions.client display_notification action with the PNS defaults."""
    params = {
        'title': title,
        'message': message,
        'type': notification_type,
        'sticky': sticky,
    }
    if reload:
        params['next'] = {'type': 'ir.actions.client', 'tag': 'reload'}
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': params,
    }
