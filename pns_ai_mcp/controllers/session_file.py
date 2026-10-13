# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Serve the files a turn produced to the user who may see them.

SVG drawings open in the tab (sanitized); every other file downloads.
"""
from __future__ import annotations

import base64
import logging

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request, content_disposition

_logger = logging.getLogger(__name__)


def _may_read(env, att):
    """The creator, a system user, or whoever may read the record it hangs on."""
    if env.is_system() or att.create_uid.id == env.uid:
        return True
    if not (att.res_model and att.res_id) or att.res_model not in env:
        return False
    try:
        record = env[att.res_model].browse(att.res_id)
        record.check_access_rights('read')
        record.check_access_rule('read')
    except AccessError:
        return False
    return record.exists()


class ChatbooSessionFile(http.Controller):

    @http.route([
        '/pns_ai_mcp/session_file/<int:attachment_id>',
        '/pns_ai_mcp/session_file/<int:attachment_id>/<string:filename>',
    ], type='http', auth='user')
    def session_file(self, attachment_id, filename=None, **kwargs):
        att = request.env['ir.attachment'].sudo().browse(int(attachment_id))
        if not att.exists() or att.res_field or not _may_read(request.env, att):
            return request.not_found()
        try:
            raw = base64.b64decode(att.datas or b'')
        except Exception:
            _logger.warning('session_file: could not decode attachment %s', att.id)
            return request.not_found()
        mime = (att.mimetype or '').split(';', 1)[0].strip().lower()
        name = att.name or 'download'
        if mime == 'image/svg+xml' or name.lower().endswith('.svg'):
            from ..utils.svg_download import sanitize_svg

            clean = sanitize_svg(raw.decode('utf-8', errors='replace'))
            if not clean:
                return request.not_found()
            payload = clean.encode('utf-8')
            safe_name = name.replace('"', '').replace('\r', '').replace('\n', '')
            headers = [
                ('Content-Type', 'image/svg+xml; charset=utf-8'),
                ('Content-Disposition', 'inline; filename="%s"' % safe_name),
            ]
        else:
            payload = raw
            headers = [
                ('Content-Type', mime or 'application/octet-stream'),
                ('Content-Disposition', content_disposition(name)),
            ]
        headers += [
            ('Content-Length', str(len(payload))),
            ('X-Content-Type-Options', 'nosniff'),
        ]
        return request.make_response(payload, headers=headers)
