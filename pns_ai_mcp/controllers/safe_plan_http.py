# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""The fetch_url and api_call steps: request, cache, binary results and schema errors."""

import hashlib
import json
import re
from odoo.addons.pns_ai_mcp.utils.fetch_url_safe import (
    FETCH_URL_MAX_BYTES,
    FETCH_URL_MAX_REDIRECTS,
    FETCH_URL_SAFE_METHODS,
    non_public_host_error,
    non_public_peer_error,
    normalize_fetch_url_method,
)

from .safe_plan_validate import (
    _api_call_schema_error,
)


# ── fetch_url: safe methods; whitelist + policy gate access ───────────────

def _cache_ttl_from_headers(headers, max_ttl=604800):
    """Derive a cache TTL (seconds) from standard HTTP response headers.

    The ORIGIN decides — exactly like browsers, CDNs and proxies. We never
    invent a TTL: an immutable geocoding API advertises a long ``max-age`` and
    gets cached; a live weather API sends ``no-cache`` / ``max-age=0`` and is
    never cached. No per-domain configuration to maintain.

    Rules (RFC 7234, simplified):
        - ``Cache-Control: no-store | no-cache | private`` → 0 (never cache).
        - ``Cache-Control: s-maxage=N`` (preferred) or ``max-age=N`` → N.
        - else ``Expires`` header → seconds until that instant.
        - else → 0 (no explicit permission = don't cache).
    Result is clamped to ``[0, max_ttl]`` so a bogus huge max-age can't pin a
    stale entry for months.
    """
    try:
        cc = (headers.get('Cache-Control') or '').lower()
        if 'no-store' in cc or 'no-cache' in cc or 'private' in cc:
            return 0
        m = re.search(r's-maxage\s*=\s*(\d+)', cc) or re.search(r'max-age\s*=\s*(\d+)', cc)
        if m:
            return max(0, min(int(m.group(1)), max_ttl))
        exp = headers.get('Expires')
        if exp:
            from email.utils import parsedate_to_datetime
            import datetime as _dt
            dt = parsedate_to_datetime(exp)
            if dt is not None:
                now = _dt.datetime.now(dt.tzinfo) if dt.tzinfo else _dt.datetime.utcnow()
                return max(0, min(int((dt - now).total_seconds()), max_ttl))
        return 0
    except Exception:
        return 0


def _label_fetch_url_result(result, step):
    """Copy city/name/label from the step to the result (also after a cache hit)."""
    if not isinstance(result, dict) or not isinstance(step, dict):
        return result
    out = dict(result)
    for _k in ('city', 'name', 'label'):
        if step.get(_k):
            out[_k] = step.get(_k)
            break
    return out


def _binary_fetch_url_result(env, url, resp, step):
    """Store a binary fetch_url body as a turn download."""
    import json as _json
    from ..utils.session_download import (
        resolve_session_ref,
        filename_from_http,
        persist_turn_file_detail,
        build_binary_stored_meta,
        PERSIST_REASON_NO_BYTES,
        is_binary_content_type,
        mimetype_from_magic_bytes,
    )

    content_type = resp.headers.get('Content-Type', '')
    content_disposition = resp.headers.get('Content-Disposition', '')
    raw = resp.content or b''
    if not is_binary_content_type(content_type, content_disposition):
        inferred = mimetype_from_magic_bytes(raw)
        if inferred:
            content_type = inferred
    filename = filename_from_http(url, content_type, content_disposition)
    session_id = resolve_session_ref(env)
    persist_detail = (
        persist_turn_file_detail(
            env, session_id, raw, filename, content_type,
        )
        if raw else {'ok': False, 'reason': PERSIST_REASON_NO_BYTES}
    )
    chip = persist_detail.get('chip') if persist_detail.get('ok') else None
    stored_meta = build_binary_stored_meta(persist_detail, filename, len(raw))
    result = {
        'op': 'fetch_url',
        'url': url,
        'success': True,
        'status_code': resp.status_code,
        'content_type': content_type,
        'body': _json.dumps(stored_meta, ensure_ascii=False),
        'binary': True,
    }
    if chip:
        result['download_chip'] = chip
    return _label_fetch_url_result(result, step)


def _binary_api_call_result(env, server_code, tool_name, raw_response, url='',
                            arguments=None):
    """Store a binary api_call body as a turn download."""
    import json as _json
    from ..utils.session_download import (
        resolve_session_ref,
        filename_from_http,
        persist_turn_file_detail,
        build_binary_stored_meta,
        preferred_download_filename,
        PERSIST_REASON_NO_BYTES,
    )

    content_type = raw_response.get('content_type') or ''
    content_disposition = raw_response.get('content_disposition') or ''
    raw = raw_response.get('content') or b''
    labels = (env.context or {}).get('file_label_by_id')
    filename = preferred_download_filename(
        raw_response.get('filename')
        or filename_from_http(
            url or '%s/%s' % (server_code, tool_name),
            content_type,
            content_disposition,
        ),
        arguments=arguments,
        labels=labels if isinstance(labels, dict) else None,
    )
    session_id = resolve_session_ref(env)
    persist_detail = (
        persist_turn_file_detail(
            env, session_id, raw, filename, content_type,
        )
        if raw else {'ok': False, 'reason': PERSIST_REASON_NO_BYTES}
    )
    chip = persist_detail.get('chip') if persist_detail.get('ok') else None
    stored_meta = build_binary_stored_meta(persist_detail, filename, len(raw))
    result = {
        'op': 'api_call',
        'server': server_code,
        'tool': tool_name,
        'success': True,
        'body': _json.dumps(stored_meta, ensure_ascii=False),
        'binary': True,
    }
    if chip:
        result['download_chip'] = chip
    return result


def _fetch_cache_key(url, method, body):
    """Cache key: the exact URL, extended with the body hash for QUERY.

    RFC 10008 guidance: a QUERY response is cacheable and its cache key MUST
    include the request content — same URL with a different query body is a
    different resource representation.
    """
    if method == 'QUERY' and body:
        digest = hashlib.sha256(body.encode('utf-8')).hexdigest()
        return '%s#query-sha256=%s' % (url, digest)
    return url


def _headers_summary_for_llm(resp_headers):
    """Compact header dump for HEAD/OPTIONS (no response body by design)."""
    prefer = (
        'allow', 'content-type', 'content-length', 'content-disposition',
        'cache-control', 'expires', 'etag', 'last-modified', 'location',
        'server', 'www-authenticate', 'access-control-allow-origin',
        'access-control-allow-methods', 'access-control-allow-headers',
    )
    out = {}
    lower_map = {k.lower(): (k, v) for k, v in (resp_headers or {}).items()}
    for key in prefer:
        if key in lower_map:
            orig, val = lower_map[key]
            out[orig] = val
    if not out:
        # Fallback: first headers only (avoid dumping huge sets).
        for i, (k, v) in enumerate((resp_headers or {}).items()):
            if i >= 20:
                break
            out[k] = v
    return out


def _fetch_url_request(env, method, url, headers, request_kwargs):
    """Send the request; return ``(response, refusal)``.

    Redirects are followed here, one hop at a time: each target must be
    http(s), public and allowed by the URL policy, like the first URL.
    The body is read in chunks and refused past ``FETCH_URL_MAX_BYTES``.
    """
    import requests as _requests
    from urllib.parse import urljoin, urlparse
    for _hop in range(FETCH_URL_MAX_REDIRECTS + 1):
        refused = non_public_host_error(url)
        if refused:
            return None, refused
        # (connect, read): a hung DNS/TLS must not block propose/orchestration.
        resp = _requests.request(
            method,
            url,
            timeout=(3, 12),
            allow_redirects=False,
            stream=True,
            headers=headers,
            **request_kwargs,
        )
        refused = non_public_peer_error(resp, url)
        if refused:
            resp.close()
            return None, refused
        location = resp.headers.get('Location') if resp.is_redirect else None
        if not location:
            break
        resp.close()
        url = urljoin(url, location)
        if urlparse(url).scheme not in ('http', 'https'):
            return None, 'fetch_url redirect to a non-http(s) URL: %s' % url
        ok, policy_error = env['ai.url.whitelist'].check_fetch_url_steps(
            [{'op': 'fetch_url', 'url': url}], user=env.user,
        )
        if not ok:
            return None, 'fetch_url redirect refused: %s' % policy_error
        if resp.status_code == 303 and method != 'HEAD':
            method = 'GET'
            request_kwargs = {}
    else:
        return None, 'fetch_url: more than %d redirects.' % FETCH_URL_MAX_REDIRECTS

    declared = resp.headers.get('Content-Length') or ''
    if declared.isdigit() and int(declared) > FETCH_URL_MAX_BYTES:
        resp.close()
        return None, 'fetch_url: the response is larger than %d MB.' % (
            FETCH_URL_MAX_BYTES // (1024 * 1024))
    body = bytearray()
    for chunk in resp.iter_content(chunk_size=65536):
        body.extend(chunk)
        if len(body) > FETCH_URL_MAX_BYTES:
            resp.close()
            return None, 'fetch_url: the response is larger than %d MB.' % (
                FETCH_URL_MAX_BYTES // (1024 * 1024))
    resp._content = bytes(body)
    resp._content_consumed = True
    return resp, ''


def _execute_fetch_url(env, step):
    """Execute a fetch_url step with a safe HTTP method to an allowed domain.

    Allowed: GET, HEAD, OPTIONS, QUERY (RFC 10008). QUERY carries the query in
    the request body (mandatory Content-Type). Access was validated at
    propose/confirm time (user permission + whitelist policy). Under open
    policy the request runs without growing the list
    (see ``_ensure_fetch_url_whitelist``).
    """
    import requests as _requests
    url = step['url']
    method = normalize_fetch_url_method(step.get('method'))
    if method not in FETCH_URL_SAFE_METHODS:
        # Defence in depth: propose already validates; do not go out to the network.
        return {
            'success': False,
            'op': 'fetch_url',
            'url': url,
            'error': (
                "fetch_url only allows safe methods "
                "(GET, HEAD, OPTIONS, QUERY); got: %r" % method
            ),
        }
    body = step.get('body') if method == 'QUERY' else None

    # Cache of IMMUTABLES driven by the ORIGIN (HTTP headers), not by manual
    # config: if there is a fresh entry for this exact key we serve it without
    # going to the network (for QUERY the key includes the body hash). The server
    # sets the TTL with Cache-Control/Expires (like browsers/CDNs);
    # if it does not allow caching, nothing is stored. See _cache_ttl_from_headers.
    cache_key = _fetch_cache_key(url, method, body)
    try:
        cached = env['ai.fetch.cache']._get_cached(cache_key)
        if cached is not None:
            # The label (city) lives in the step, not in the HTTP cache.
            cached['url'] = url
            return _label_fetch_url_result(cached, step)
    except Exception:
        pass

    try:
        headers = {'User-Agent': 'PNS-AI-SafePlan/1.0'}
        request_kwargs = {}
        if method == 'QUERY':
            # RFC 10008: the body Content-Type is required (checked at
            # propose); without it the request must fail on the server.
            headers['Content-Type'] = step.get('content_type') or 'application/json'
            request_kwargs['data'] = (body or '').encode('utf-8')
        resp, refused = _fetch_url_request(
            env, method, url, headers, request_kwargs,
        )
        if refused:
            return {'op': 'fetch_url', 'url': url, 'success': False, 'error': refused}

        content_type = resp.headers.get('Content-Type', '')
        content_disposition = resp.headers.get('Content-Disposition', '')
        raw = resp.content or b''

        # HEAD/OPTIONS: no useful body; return selected response headers.
        if method in ('HEAD', 'OPTIONS'):
            hdrs = _headers_summary_for_llm(resp.headers)
            result = {
                'op': 'fetch_url',
                'url': url,
                'method': method,
                'success': True,
                'status_code': resp.status_code,
                'content_type': content_type,
                'headers': hdrs,
                'body': json.dumps(hdrs, ensure_ascii=False),
                'truncated': False,
            }
            result = _label_fetch_url_result(result, step)
            if resp.status_code == 200:
                ttl = _cache_ttl_from_headers(resp.headers)
                if ttl > 0:
                    cache_payload = {
                        k: v for k, v in result.items()
                        if k not in ('city', 'name', 'label')
                    }
                    env['ai.fetch.cache']._store(cache_key, cache_payload, ttl)
            return result

        from ..utils.session_download import (
            is_binary_content_type,
            looks_like_binary_bytes,
        )
        if (
            is_binary_content_type(content_type, content_disposition)
            or looks_like_binary_bytes(raw)
        ):
            return _binary_fetch_url_result(env, url, resp, step)

        body_raw = resp.text[:10240] if resp.text else ''

        # SPA detection: if HTML, strip tags and check visible text length
        is_html = 'text/html' in content_type
        if is_html and resp.status_code == 200:
            # Remove <script>, <style>, <head> blocks, then all tags
            stripped = re.sub(r'<(script|style|head)[^>]*>.*?</\1>', '', body_raw,
                              flags=re.DOTALL | re.IGNORECASE)
            stripped = re.sub(r'<[^>]+>', ' ', stripped)
            stripped = re.sub(r'\s+', ' ', stripped).strip()
            if len(stripped) < 200:
                return {
                    'op': 'fetch_url',
                    'url': url,
                    'success': False,
                    'status_code': resp.status_code,
                    'error': (
                        'SPA detected: the page is rendered by JavaScript and '
                        'contains almost no readable text in the raw HTML. '
                        'Try a JSON API endpoint instead.'
                    ),
                    'visible_text_length': len(stripped),
                }

        result = {
            'op': 'fetch_url',
            'url': url,
            'success': True,
            'status_code': resp.status_code,
            'content_type': content_type,
            'body': body_raw,
            'truncated': len(resp.text) > 10240 if resp.text else False,
        }
        result = _label_fetch_url_result(result, step)
        # We cache ONLY the HTTP payload (no step label): the city is
        # re-injected on each hit. So a fetch with no name does not «burn» the title.
        if resp.status_code == 200:
            ttl = _cache_ttl_from_headers(resp.headers)
            if ttl > 0:
                cache_payload = {
                    k: v for k, v in result.items()
                    if k not in ('city', 'name', 'label')
                }
                env['ai.fetch.cache']._store(cache_key, cache_payload, ttl)
        return result
    except _requests.RequestException as e:
        return {
            'op': 'fetch_url',
            'url': url,
            'success': False,
            'error': str(e),
        }


def _execute_api_call(env, step):
    """Execute an api_call step on a configured external API server.

    The server must be registered in ai.api.server and active; its
    ``api_type`` selects the protocol driver (mcp / openapi). The outbound
    credential is resolved per user: the caller's ai.api.server.key if any,
    else the server's default auth token.

    Full responses are cached server-side (``ai.api.result.cache``). The LLM
    channel receives a JSON-aware preview plus pagination hints when needed.
    """
    from ..lib.api.drivers import APIDriverError, get_api_driver
    from ..utils.api_call_result import (
        API_CALL_CACHE_TTL_SECONDS,
        cache_key_for_api_call,
        format_api_call_body_for_llm,
    )

    server_code = step.get('server', '')
    tool_name = step.get('tool', '')
    arguments = step.get('arguments') or {}
    if not isinstance(arguments, dict):
        arguments = {}

    # Find the server record
    srv = env['ai.api.server'].sudo().search(
        [('code', '=', server_code), ('active', '=', True)], limit=1)
    if not srv:
        return {
            'op': 'api_call',
            'server': server_code,
            'tool': tool_name,
            'success': False,
            'error': f"External API server '{server_code}' not found or inactive.",
        }

    schema_error = _api_call_schema_error(srv, tool_name, arguments)
    if schema_error:
        return {
            'op': 'api_call',
            'server': server_code,
            'tool': tool_name,
            'success': False,
            'error': schema_error,
        }

    cache_key = cache_key_for_api_call(
        server_code, tool_name, arguments, uid=env.uid)
    Cache = env['ai.api.result.cache']

    try:
        cached_body = Cache._get_cached(server_code, tool_name, arguments)
        if cached_body is not None:
            body = cached_body
            from_cache = True
        else:
            driver = get_api_driver(srv.api_type)
            auth_token = srv._resolve_auth_token(env.user)
            body = driver.call(srv, tool_name, arguments, auth_token=auth_token)
            from_cache = False
            if isinstance(body, dict) and body.get('_binary'):
                return _binary_api_call_result(
                    env, server_code, tool_name, body,
                    url=body.get('url') or '',
                    arguments=arguments,
                )
            if isinstance(body, str) and body.strip():
                from ..utils.session_download import try_extract_binary_payload
                extracted = try_extract_binary_payload(
                    body,
                    tool_name=tool_name,
                    server_code=server_code,
                    arguments=arguments,
                )
                if extracted:
                    return _binary_api_call_result(
                        env, server_code, tool_name, {
                            '_binary': True,
                            'content': extracted['content'],
                            'content_type': extracted['content_type'],
                            'content_disposition': extracted['content_disposition'],
                            'filename': extracted.get('filename'),
                            'url': extracted.get('url') or '',
                        },
                        url=extracted.get('url') or '',
                        arguments=arguments,
                    )
    except (APIDriverError, ValueError) as e:
        return {
            'op': 'api_call',
            'server': server_code,
            'tool': tool_name,
            'success': False,
            'error': str(e),
        }
    except Exception as e:
        return {
            'op': 'api_call',
            'server': server_code,
            'tool': tool_name,
            'success': False,
            'error': f"Unexpected error: {e}",
        }

    body = body or ''
    if not from_cache:
        try:
            Cache._store(
                server_code, tool_name, arguments, body,
                ttl_seconds=API_CALL_CACHE_TTL_SECONDS,
            )
        except Exception:
            pass

    llm_body, truncated, pagination = format_api_call_body_for_llm(body, arguments)

    result = {
        'op': 'api_call',
        'server': server_code,
        'tool': tool_name,
        'success': True,
        'body': llm_body,
        'truncated': truncated,
        'cache_key': cache_key,
        '_from_cache': from_cache,
    }
    if pagination:
        result['pagination'] = pagination
    return result
