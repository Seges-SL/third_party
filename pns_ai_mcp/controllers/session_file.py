# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Serve session SVG chips inline in the browser (like PDF, not download)."""
from __future__ import annotations

import base64
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ChatbooSessionFile(http.Controller):

    @http.route(
        '/pns_ai_mcp/session_file/<int:attachment_id>',
        type='http',
        auth='public',
    )
    def session_file(self, attachment_id, access_token=None, **kwargs):
        token = (access_token or '').strip()
        if not token:
            return request.not_found()
        att = request.env['ir.attachment'].sudo().browse(int(attachment_id))
        if not att.exists():
            return request.not_found()
        stored = (getattr(att, 'access_token', None) or '').strip()
        if not stored or stored != token:
            return request.not_found()
        mime = (att.mimetype or '').split(';', 1)[0].strip().lower()
        name = att.name or 'drawing.svg'
        if mime != 'image/svg+xml' and not name.lower().endswith('.svg'):
            return request.not_found()
        try:
            raw = base64.b64decode(att.datas or b'')
        except Exception:
            _logger.warning('session_file: could not decode attachment %s', att.id)
            return request.not_found()
        from ..utils.svg_download import sanitize_svg

        text = raw.decode('utf-8', errors='replace')
        clean = sanitize_svg(text)
        if not clean:
            return request.not_found()
        payload = clean.encode('utf-8')
        filename = name.replace('"', '').replace('\r', '').replace('\n', '')
        headers = [
            ('Content-Type', 'image/svg+xml; charset=utf-8'),
            ('Content-Length', str(len(payload))),
            ('Content-Disposition', 'inline; filename="%s"' % filename),
            ('X-Content-Type-Options', 'nosniff'),
        ]
        return request.make_response(payload, headers=headers)
