# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Single snapshot for ``system://info`` (tool, resource, get_context bridge).

The Chatboo async worker often has no HTTP request. ``url`` must not fall
back to the English sentinel ``Unknown``: use ``web.base.url`` when the
request host is missing.
"""
from __future__ import annotations

from datetime import datetime


def request_host_url():
    """Werkzeug ``host_url`` when an HTTP request is on the stack, else ``''``."""
    try:
        from odoo.http import request
        if request and getattr(request, 'httprequest', None):
            return (request.httprequest.host_url or '').strip()
    except Exception:
        return ''
    return ''


def resolve_public_base_url(env=None, host_url=None):
    """Public base URL: live request first, then ``ir.config_parameter``.

    Returns ``''`` (never the word ``Unknown``) if neither source is set.
    """
    url = (host_url if host_url is not None else request_host_url()) or ''
    url = str(url).strip()
    if url:
        return url
    if env is None:
        return ''
    try:
        param = env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
    except Exception:
        return ''
    return str(param).strip()


def _odoo_version():
    try:
        import odoo.release
        return (
            getattr(odoo.release, 'version', None)
            or getattr(odoo.release, 'serie', None)
            or ''
        )
    except Exception:
        pass
    try:
        import odoo.service.common
        info = odoo.service.common.exp_version() or {}
        return info.get('server_version') or info.get('server_serie') or ''
    except Exception:
        return ''


def _python_version():
    try:
        import sys
        return sys.version.split(' ')[0]
    except Exception:
        return ''


def system_info_facts(env=None, host_url=None, now=None):
    """Flat facts painted by ``fetch_native_mcp_resource`` (key/value table)."""
    when = now or datetime.now()
    db_name = ''
    if env is not None:
        try:
            db_name = env.cr.dbname or ''
        except Exception:
            db_name = ''
    return {
        'odoo_version': _odoo_version(),
        'db_name': db_name,
        'server_time': when.strftime('%Y-%m-%d %H:%M:%S'),
        'url': resolve_public_base_url(env, host_url),
    }


def resource_system_info(env=None, host_url=None, now=None):
    """Richer MCP ``resources/read`` / ``get_context`` envelope (same URL SoT)."""
    facts = system_info_facts(env, host_url=host_url, now=now)
    serie = ''
    version = facts.get('odoo_version') or ''
    try:
        import odoo.release
        serie = getattr(odoo.release, 'serie', '') or ''
        version = getattr(odoo.release, 'version', None) or version
    except Exception:
        pass
    when = now or datetime.now()
    return {
        'server_version': version,
        'server_serie': serie,
        'database': facts.get('db_name') or '',
        'base_url': facts.get('url') or '',
        'server_time': when.isoformat(),
        'mcp_server_version': '1.0.0',
        'python_version': _python_version(),
    }
