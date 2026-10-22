# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Origin check for the /mcp endpoints.

Desktop and server MCP clients send no Origin header and always pass. A
browser page only passes when its Origin is the instance itself
(web.base.url) or one an admin listed in ``pns_ai_mcp.mcp_allowed_origins``
(one per line or comma separated).
"""
import re
from urllib.parse import urlparse

ICP_MCP_ALLOWED_ORIGINS = 'pns_ai_mcp.mcp_allowed_origins'


def parse_allowed_origins(raw):
    """Configured extra origins, normalised (no trailing slash)."""
    out = set()
    for part in re.split(r'[\s,]+', raw or ''):
        part = part.strip().rstrip('/')
        if part:
            out.add(part)
    return out


def origin_of(url):
    """scheme://netloc of a URL, or '' when it has none."""
    try:
        parsed = urlparse(url or '')
    except Exception:
        return ''
    if parsed.scheme and parsed.netloc:
        return '%s://%s' % (parsed.scheme, parsed.netloc)
    return ''


def origin_allowed(origin, allowed_raw, base_url):
    """True when a request with this Origin header may use /mcp."""
    if origin is None:
        return True
    origin = (origin or '').strip().rstrip('/')
    if not origin:
        return True
    allowed = parse_allowed_origins(allowed_raw)
    base = origin_of(base_url)
    if base:
        allowed.add(base)
    return origin in allowed
