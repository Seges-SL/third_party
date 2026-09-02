# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Root.get_request patch (Odoo <= 15): serve MCP type='http' routes that carry
a Content-Type of application/json (Cursor Streamable HTTP, Antigravity, etc.).
"""

import odoo
from .utils.compat import NEEDS_ROOT_GET_REQUEST_PATCH

_MCP_JSON_MIMETYPES = frozenset({'application/json', 'application/json-rpc'})


def _mcp_route_needs_http_request(path, method, mimetype):
    if method != 'POST' or mimetype not in _MCP_JSON_MIMETYPES:
        return False
    if not path:
        return False
    return path == '/mcp' or path.startswith('/mcp/')


if NEEDS_ROOT_GET_REQUEST_PATCH:
    from odoo.http import Root, HttpRequest

    _original_get_request = Root.get_request

    def _patched_get_request(self, httprequest):
        path = getattr(httprequest, 'path', '') or ''
        if _mcp_route_needs_http_request(
            path, httprequest.method, httprequest.mimetype,
        ):
            return HttpRequest(httprequest)
        return _original_get_request(self, httprequest)

    Root.get_request = _patched_get_request
