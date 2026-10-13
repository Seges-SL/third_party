# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Pictures from another site, served from our own origin.

The page never calls the other site. Odoo fetches the picture only from a
host the URL policy allows (``ai.url.whitelist.may_show_remote_image``);
otherwise 404 and the browser shows the image's alt text.
"""
from __future__ import annotations

from odoo import http
from odoo.http import request

from ..utils.remote_image import (
    REMOTE_IMAGE_PATH,
    fetch_image_bytes,
    reencode_image,
)


class RemoteImage(http.Controller):

    @http.route(REMOTE_IMAGE_PATH, type='http', auth='user', methods=['GET'])
    def remote_image(self, url='', **kwargs):
        policy = request.env['ai.url.whitelist']
        picture = reencode_image(
            fetch_image_bytes(url, policy.may_show_remote_image),
        )
        if not picture:
            return request.not_found()
        payload, mime = picture
        return request.make_response(payload, headers=[
            ('Content-Type', mime),
            ('Content-Length', str(len(payload))),
            ('Cache-Control', 'private, max-age=3600'),
            ('X-Content-Type-Options', 'nosniff'),
            ('Content-Security-Policy', "default-src 'none'"),
        ])
