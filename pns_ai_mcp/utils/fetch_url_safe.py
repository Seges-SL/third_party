# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""HTTP method policy for ``op=fetch_url`` (box B).

No Odoo deps: unit-testable on host. Mutations (POST/PUT/…) go through
``api_call`` on a registered server, not fetch_url.

Validation errors are English (ai.log / LLM lingua franca).
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

# Safe / idempotent HTTP methods for fetch_url (ad-hoc web read). Mutating
# methods (POST/PUT/PATCH/DELETE) are out of core — use api_call on a
# registered MCP/OpenAPI server.
FETCH_URL_SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS', 'QUERY'})

FETCH_URL_MAX_REDIRECTS = 5
FETCH_URL_MAX_BYTES = 20 * 1024 * 1024


def non_public_host_error(url):
    """English reason when the URL's host is not on the public internet, else ''.

    Every address the name resolves to must be global: one private answer is
    enough to refuse (localhost, the database, cloud metadata, the LAN).
    Internal APIs go through ``api_call`` on a server an admin registered.
    """
    host = urlsplit(url or '').hostname
    if not host:
        return 'URL without a host.'
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError) as exc:
        return 'Cannot resolve %s: %s' % (host, exc)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split('%', 1)[0])
        if not ip.is_global:
            return 'fetch_url does not reach internal addresses (%s is %s).' % (host, ip)
    return ''


def normalize_fetch_url_method(method=None):
    """Return the method in uppercase (default GET)."""
    return str(method if method is not None else 'GET').upper()


def validate_fetch_url_step(step, step_index=0):
    """Validate a fetch_url step (url + safe method + QUERY body).

    ``step`` is a dict; not mutated. Returns ``(ok, error_message|None)``.
    """
    i = int(step_index) + 1
    if not isinstance(step, dict):
        return False, "Step %s: each operation must be an object." % i

    url = step.get('url', '')
    if not isinstance(url, str) or not url:
        return False, "Step %s: 'fetch_url' requires 'url' (string)." % i
    if not url.startswith(('http://', 'https://')):
        return False, (
            "Step %s: 'fetch_url' only allows http:// or https://." % i
        )

    method = normalize_fetch_url_method(step.get('method'))
    if method not in FETCH_URL_SAFE_METHODS:
        return False, (
            "Step %s: 'fetch_url' only allows safe methods "
            "(GET, HEAD, OPTIONS, QUERY); got: %r. "
            "POST/PUT/PATCH/DELETE: use api_call on a registered server "
            "(MCP/OpenAPI) or a new closed verb in a binding extension "
            "(in Odoo: a separate module)."
            % (i, method)
        )

    if method == 'QUERY':
        # RFC 10008: QUERY carries the query in the body; the server
        # MUST reject requests without a coherent Content-Type.
        body = step.get('body')
        if not isinstance(body, str) or not body:
            return False, (
                "Step %s: 'fetch_url' with method QUERY requires "
                "'body' (string with the query)." % i
            )
        content_type = step.get('content_type')
        if not isinstance(content_type, str) or not content_type:
            return False, (
                "Step %s: 'fetch_url' with method QUERY requires "
                "'content_type' (e.g. application/json)." % i
            )
    return True, None


_AUTH_HEADER_NAMES = frozenset({
    'authorization', 'cookie', 'proxy-authorization',
    'x-api-key', 'x-mcp-api-key', 'x-mcp-token',
})


def _strip_auth_headers(headers):
    if not headers:
        return {}
    return {
        key: value for key, value in headers.items()
        if str(key).lower() not in _AUTH_HEADER_NAMES
    }


def request_public_http(
        method, url, headers=None, timeout=None, data=None, params=None,
        max_bytes=None, max_redirects=None,
):
    """HTTP request that never follows a redirect onto a non-public host.

    Auth headers stay on the first host only. The body is capped.
    Returns the final ``requests.Response`` (content already loaded).
    Raises ``ValueError`` with an English reason on refusal.
    """
    import requests
    from urllib.parse import urljoin, urlsplit

    method = (method or 'GET').upper()
    headers = dict(headers or {})
    timeout = timeout if timeout is not None else (5, 30)
    cap = FETCH_URL_MAX_BYTES if max_bytes is None else int(max_bytes)
    hops = FETCH_URL_MAX_REDIRECTS if max_redirects is None else int(max_redirects)
    first_host = (urlsplit(url).hostname or '').lower()
    kwargs = {}
    if data is not None:
        kwargs['data'] = data
    if params is not None:
        kwargs['params'] = params

    for _hop in range(hops + 1):
        refused = non_public_host_error(url)
        if refused:
            raise ValueError(refused)
        scheme = (urlsplit(url).scheme or '').lower()
        if scheme not in ('http', 'https'):
            raise ValueError('Only http:// or https:// URLs are allowed.')
        try:
            resp = requests.request(
                method, url, timeout=timeout, allow_redirects=False,
                stream=True, headers=headers, **kwargs,
            )
        except requests.RequestException as exc:
            raise ValueError('HTTP request failed: %s' % exc)
        location = resp.headers.get('Location') if resp.is_redirect else None
        if not location:
            break
        resp.close()
        url = urljoin(url, location)
        next_host = (urlsplit(url).hostname or '').lower()
        if next_host != first_host:
            headers = _strip_auth_headers(headers)
        if resp.status_code == 303 and method != 'HEAD':
            method = 'GET'
            kwargs = {}
    else:
        raise ValueError('More than %d redirects.' % hops)

    declared = resp.headers.get('Content-Length') or ''
    if declared.isdigit() and int(declared) > cap:
        resp.close()
        raise ValueError('The response is larger than %d MB.' % (cap // (1024 * 1024)))
    body = bytearray()
    for chunk in resp.iter_content(chunk_size=65536):
        body.extend(chunk)
        if len(body) > cap:
            resp.close()
            raise ValueError('The response is larger than %d MB.' % (cap // (1024 * 1024)))
    resp._content = bytes(body)
    resp._content_consumed = True
    return resp
