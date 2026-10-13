# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""A picture from another site, fetched by Odoo and handed back as our own.

The browser never calls the other site: it asks ``REMOTE_IMAGE_PATH`` and
Odoo fetches the picture only when the caller says the host is allowed.
What comes back is decoded and saved again as a plain raster, so no SVG,
script or foreign bytes reach the page. The picture work is pns_base's
(``utils/pdf_io.py``).
"""
from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from .fetch_url_safe import non_public_host_error

REMOTE_IMAGE_PATH = '/pns_ai_mcp/remote_image'
REMOTE_IMAGE_MAX_BYTES = 8 * 1024 * 1024
REMOTE_IMAGE_MAX_PX = 1024
REMOTE_IMAGE_MAX_REDIRECTS = 3


def fetch_image_bytes(url, host_allowed):
    """Raw bytes at *url*, or ``None``.

    Every hop must be http(s), public and pass ``host_allowed(hostname)``.
    """
    import requests as _requests
    for _hop in range(REMOTE_IMAGE_MAX_REDIRECTS + 1):
        parts = urlsplit(url or '')
        if parts.scheme not in ('http', 'https') or not parts.hostname:
            return None
        if not host_allowed(parts.hostname.lower()):
            return None
        if non_public_host_error(url):
            return None
        try:
            resp = _requests.get(
                url, timeout=(3, 10), allow_redirects=False, stream=True,
            )
        except _requests.RequestException:
            return None
        location = resp.headers.get('Location') if resp.is_redirect else None
        if not location:
            break
        resp.close()
        url = urljoin(url, location)
    else:
        return None
    if resp.status_code != 200:
        resp.close()
        return None
    declared = resp.headers.get('Content-Length') or ''
    if declared.isdigit() and int(declared) > REMOTE_IMAGE_MAX_BYTES:
        resp.close()
        return None
    body = bytearray()
    try:
        for chunk in resp.iter_content(chunk_size=65536):
            body.extend(chunk)
            if len(body) > REMOTE_IMAGE_MAX_BYTES:
                return None
    except _requests.RequestException:
        return None
    finally:
        resp.close()
    return bytes(body)


def reencode_image(raw):
    """``(bytes, mime)`` of *raw* decoded and saved again, or ``None``.

    JPEG stays JPEG; any other raster becomes PNG. Larger than
    ``REMOTE_IMAGE_MAX_PX`` on a side is shrunk (pns_base).
    """
    if not raw:
        return None
    from odoo.addons.pns_base.utils.pdf_io import shrink_picture

    return shrink_picture(raw, REMOTE_IMAGE_MAX_PX)
