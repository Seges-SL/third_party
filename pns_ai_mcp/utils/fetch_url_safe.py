# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""HTTP method policy for ``op=fetch_url`` (box B).

No Odoo deps: unit-testable on host. Mutations (POST/PUT/…) go through
``api_call`` on a registered server, not fetch_url.

Validation errors are English (ai.log / LLM lingua franca).
"""
from __future__ import annotations

# Safe / idempotent HTTP methods for fetch_url (ad-hoc web read). Mutating
# methods (POST/PUT/PATCH/DELETE) are out of core — use api_call on a
# registered MCP/OpenAPI server.
FETCH_URL_SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS', 'QUERY'})


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
