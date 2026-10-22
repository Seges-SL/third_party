# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Generate a draft OpenAPI 3 document from human-readable API documentation.

Admin UI only (External Servers form). Not used from Chatboo turns or
relaxaicode — the draft must be reviewed before ``spec_json`` is written.
"""

import json
import logging
import re
from urllib.parse import urlparse

import requests


def _request_public_http(*args, **kwargs):
    """Same hop checks as fetch_url. Loaded by path so unit tests that
    import this file as a top-level module still work."""
    import importlib.util
    import sys
    from pathlib import Path

    key = 'pns_ai_mcp_fetch_url_safe'
    mod = sys.modules.get(key)
    if mod is None:
        path = Path(__file__).resolve().parents[1] / 'utils' / 'fetch_url_safe.py'
        spec = importlib.util.spec_from_file_location(key, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        spec.loader.exec_module(mod)
    return mod.request_public_http(*args, **kwargs)

_logger = logging.getLogger(__name__)

_MAX_DOC_CHARS = 120_000
# Prompt is capped; convert is one silent RPC (same pattern as skill params).
_MAX_LLM_CHARS = 24_000
# Grok needs ~8k completion tokens for a compact Admin-API page (logs: 5–9k).
_LLM_MAX_TOKENS = 8192
# Live O14 runs took 80–180s; 40s aborted the JSON mid-stream.
_LLM_TIMEOUT = 120
_LLM_MAX_PROVIDERS = 2
_MIN_USEFUL_CHARS = 400
_BROWSER_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/122.0.0.0 Safari/537.36'
)

DEFAULT_OPENAPI_GEN_SYSTEM_PROMPT = (
    'You analyze one human-readable API documentation page (the text in the '
    'user message). There is no official openapi.json — infer the HTTP API '
    'and write a valid OpenAPI 3.0 document from that page only.\n\n'
    'Output rules:\n'
    '- Reply with a single JSON object only (no markdown fences, no commentary).\n'
    '- Include paths only for endpoints this page describes; use exact path '
    'strings from the page.\n'
    '- Each operation needs a unique operationId (camelCase).\n'
    '- Do not invent endpoints, fields, or pages that are not on this page.\n'
    '- Set servers[] when this page states a base URL; otherwise omit servers.\n'
    '- Keep the document compact: no long examples, no extra schemas the page '
    'does not name.\n\n'
    'Scope:\n'
    '- This page only. Do not follow links — not on the same host, not on the '
    'same domain, not elsewhere.\n'
    '- Do not crawl, search, or open other URLs.'
)

# Prior factory texts — refreshed to DEFAULT on -u / migrate when still unmodified.
_LEGACY_OPENAPI_GEN_SYSTEM_PROMPTS = (
    (
        'You analyze human-readable API documentation (HTML or markdown web pages). '
        'There is no official openapi.json — infer the HTTP API and write a valid '
        'OpenAPI 3.0 document from what the page describes.\n\n'
        'Output rules:\n'
        '- Reply with a single JSON object only (no markdown fences, no commentary).\n'
        '- Include paths for every documented endpoint; use exact path strings from '
        'the docs.\n'
        '- Each operation needs a unique operationId (camelCase).\n'
        '- Do not invent endpoints that are not described in the documentation.\n'
        '- Set servers[] when the docs state a base URL; otherwise omit servers.\n\n'
        'Fetch / browse scope (when you are allowed to retrieve pages):\n'
        '- Stay on the same registrable domain (same eTLD+1 / public-suffix domain). '
        'Subdomains of that domain are allowed (e.g. docs.example.com and '
        'api.example.com); other companies or other base domains are not.\n'
        '- Do not follow links more than one path level beyond the documentation '
        'URL you were given (e.g. from /docs/a/b you may open /docs/a/b/c but not '
        '/docs/other).\n'
        '- Do not use search engines, web archives, or unrelated hosts to gather '
        'API docs.\n'
        '- Prefer the single documentation page; do not crawl the whole site.'
    ),
    (
        'You analyze human-readable API documentation (HTML or markdown web pages). '
        'There is no official openapi.json — infer the HTTP API and write a valid '
        'OpenAPI 3.0 document from what the page describes.\n\n'
        'Output rules:\n'
        '- Reply with a single JSON object only (no markdown fences, no commentary).\n'
        '- Include paths for every documented endpoint; use exact path strings from '
        'the docs.\n'
        '- Each operation needs a unique operationId (camelCase).\n'
        '- Do not invent endpoints that are not described in the documentation.\n'
        '- Set servers[] when the docs state a base URL; otherwise omit servers.\n\n'
        'Fetch / browse scope (when you are allowed to retrieve pages):\n'
        '- Start from the documentation URL you were given; stay on that same host.\n'
        '- Do not follow links more than one path level beyond that URL '
        '(same host only; e.g. from /docs/a/b you may open /docs/a/b/c but not '
        '/docs/other or a different site).\n'
        '- Do not use search engines, web archives, or unrelated hosts to gather '
        'API docs.\n'
        '- Prefer the single documentation page; do not crawl the whole site.'
    ),
    (
        'You analyze human-readable API documentation (HTML or markdown web pages). '
        'There is no official openapi.json — infer the HTTP API and write a valid '
        'OpenAPI 3.0 document from what the page describes.\n\n'
        'Output rules:\n'
        '- Reply with a single JSON object only (no markdown fences, no commentary).\n'
        '- Include paths for every documented endpoint; use exact path strings from '
        'the docs.\n'
        '- Each operation needs a unique operationId (camelCase).\n'
        '- Do not invent endpoints that are not described in the documentation.\n'
        '- Set servers[] when the docs state a base URL; otherwise omit servers.'
    ),
)


class OpenAPISpecGeneratorError(Exception):
    """Raised when documentation fetch or spec synthesis fails."""

    def __init__(self, message, raw_text=None):
        super().__init__(message)
        self.raw_text = raw_text or ''


def documentation_to_text(raw):
    """Normalize HTML or markdown documentation to plain text for the LLM."""
    from ..utils.history_compact import _strip_html

    text = (raw or '').strip()
    if not text:
        return ''
    if '<' in text and '>' in text:
        text = _strip_html(text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def _extract_tag_inner(html, tag):
    match = re.search(
        r'<%s\b[^>]*>(.*?)</%s>' % (tag, tag),
        html or '',
        re.DOTALL | re.I,
    )
    return match.group(1) if match else ''


def _collect_readable_strings(node, out, min_len=80):
    """Pull long strings from nested JSON (Next.js / MDX payloads)."""
    if isinstance(node, str):
        s = node.strip()
        if len(s) >= min_len and (
                '/' in s or 'http' in s.lower() or 'GET' in s or 'POST' in s
                or 'endpoint' in s.lower() or '##' in s or '```' in s):
            out.append(s)
        return
    if isinstance(node, dict):
        for value in node.values():
            _collect_readable_strings(value, out, min_len=min_len)
        return
    if isinstance(node, (list, tuple)):
        for item in node:
            _collect_readable_strings(item, out, min_len=min_len)


def extract_documentation_payload(raw, content_type=''):
    """Prefer markdown/plain, else main/article HTML, else Next.js JSON text."""
    body = (raw or '').strip()
    if not body:
        return ''
    ctype = (content_type or '').lower()
    if 'markdown' in ctype or 'text/plain' in ctype:
        return documentation_to_text(body)

    if body.lstrip().startswith('{') or body.lstrip().startswith('['):
        try:
            parsed = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if parsed is not None:
            chunks = []
            _collect_readable_strings(parsed, chunks)
            if chunks:
                return documentation_to_text('\n\n'.join(chunks))

    html = body
    next_data = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.I,
    )
    next_chunks = []
    if next_data:
        try:
            payload = json.loads(next_data.group(1))
            _collect_readable_strings(payload, next_chunks, min_len=60)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    for tag in ('article', 'main'):
        inner = _extract_tag_inner(html, tag)
        if inner and len(inner) > 200:
            plain = documentation_to_text(inner)
            if len(plain) >= _MIN_USEFUL_CHARS:
                return plain

    role_main = re.search(
        r'<[^>]+role=["\']main["\'][^>]*>(.*?)</[^>]+>',
        html,
        re.DOTALL | re.I,
    )
    if role_main:
        plain = documentation_to_text(role_main.group(1))
        if len(plain) >= _MIN_USEFUL_CHARS:
            return plain

    if next_chunks:
        plain = documentation_to_text('\n\n'.join(next_chunks))
        if plain:
            return plain

    return documentation_to_text(html)


def looks_like_api_documentation(text):
    """Cheap structural check: paths or HTTP verbs present."""
    sample = (text or '')[:8000]
    if re.search(r'(?i)\b(GET|POST|PUT|PATCH|DELETE)\b', sample):
        return True
    if re.search(r'/[A-Za-z0-9_\-./{}]+', sample):
        return True
    if re.search(r'(?i)\b(endpoint|openapi|swagger|api)\b', sample):
        return True
    return False


def assert_useful_documentation(text):
    """Raise when the scrape is too thin to bother the LLM."""
    plain = (text or '').strip()
    if len(plain) < _MIN_USEFUL_CHARS:
        raise OpenAPISpecGeneratorError(
            'The fetched page has little readable documentation '
            '(%d characters). It may be a JavaScript shell (SPA). '
            'Try another URL or paste the markdown/spec manually.'
            % len(plain))
    if not looks_like_api_documentation(plain):
        raise OpenAPISpecGeneratorError(
            'The fetched page (%d characters) does not look like API '
            'documentation (no paths or HTTP methods found). '
            'Try another URL or paste the markdown/spec manually.'
            % len(plain))
    return plain


def _balanced_json_object(text):
    """Extract the first balanced ``{...}`` object (handles nested braces)."""
    start = (text or '').find('{')
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for idx, ch in enumerate(text[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(text[start:idx + 1])
                except (json.JSONDecodeError, TypeError):
                    return None
                return parsed if isinstance(parsed, dict) else None
    return None


def _escape_raw_controls_in_json_strings(text):
    """Escape literal newlines/tabs the model leaves inside JSON strings."""
    start = (text or '').find('{')
    if start < 0:
        return text or ''
    out = [text[:start]]
    in_str = False
    esc = False
    for ch in text[start:]:
        if in_str:
            if esc:
                out.append(ch)
                esc = False
                continue
            if ch == '\\':
                out.append(ch)
                esc = True
                continue
            if ch == '"':
                out.append(ch)
                in_str = False
                continue
            if ord(ch) < 32:
                if ch == '\n':
                    out.append('\\n')
                elif ch == '\r':
                    out.append('\\r')
                elif ch == '\t':
                    out.append('\\t')
                else:
                    out.append('\\u%04x' % ord(ch))
                continue
            out.append(ch)
            continue
        out.append(ch)
        if ch == '"':
            in_str = True
    return ''.join(out)


def _json_closers(chunk):
    """Suffix that closes open objects/arrays, or None if still inside a string."""
    stack = []
    in_str = False
    esc = False
    for ch in chunk or '':
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == '{':
            stack.append('}')
        elif ch == '[':
            stack.append(']')
        elif ch in '}]' and stack:
            stack.pop()
    if in_str or esc:
        return None
    return ''.join(reversed(stack))


def _repair_truncated_json_object(text):
    """Close an OpenAPI object the model cut mid-stream (max_tokens)."""
    start = (text or '').find('{')
    if start < 0:
        return None
    raw = text[start:]
    stack = []
    in_str = False
    esc = False
    expect_value = False
    last_good = None
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
                if expect_value:
                    last_good = i + 1
                    expect_value = False
            i += 1
            continue
        if ch.isspace():
            i += 1
            continue
        if ch == '"':
            in_str = True
            i += 1
            continue
        if ch == '{':
            stack.append('}')
            expect_value = False
            i += 1
            continue
        if ch == '[':
            stack.append(']')
            expect_value = True
            i += 1
            continue
        if ch in '}]':
            if stack:
                stack.pop()
            last_good = i + 1
            expect_value = False
            if not stack:
                try:
                    parsed = json.loads(raw[:i + 1])
                except (json.JSONDecodeError, TypeError):
                    return None
                return parsed if isinstance(parsed, dict) else None
            i += 1
            continue
        if ch == ':':
            expect_value = True
            i += 1
            continue
        if ch == ',':
            expect_value = bool(stack and stack[-1] == ']')
            i += 1
            continue
        if ch in 'tfn0123456789+-':
            if raw.startswith('true', i):
                i += 4
            elif raw.startswith('false', i):
                i += 5
            elif raw.startswith('null', i):
                i += 4
            else:
                i += 1
                while i < n and raw[i] in '0123456789.eE+-':
                    i += 1
            last_good = i
            expect_value = False
            continue
        i += 1

    if last_good is None:
        return None
    piece = raw[:last_good].rstrip().rstrip(',')
    closers = _json_closers(piece)
    if closers is None:
        return None
    try:
        parsed = json.loads(piece + closers)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def extract_json_object(text):
    """Return the first JSON object found in an LLM response.

    The model always replies with JSON. Do not drop it because of a
    literal newline, a missing closer, or a markdown fence.
    """
    raw = (text or '').strip()
    if not raw:
        return None
    fence = re.search(r'```(?:json)?\s*(\{.*\})\s*```', raw, re.DOTALL | re.I)
    if fence:
        raw = fence.group(1).strip()
    raw = _escape_raw_controls_in_json_strings(raw)
    balanced = _balanced_json_object(raw)
    if balanced is not None:
        return balanced
    start = raw.find('{')
    if start < 0:
        return None
    try:
        parsed = json.loads(raw[start:])
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        pass
    end = raw.rfind('}')
    if end > start:
        try:
            parsed = json.loads(raw[start:end + 1])
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return _repair_truncated_json_object(raw)


def normalize_generated_spec(spec, server=None):
    """Fill OpenAPI skeleton gaps and operationIds like the runtime driver."""
    from ..lib.api.drivers.openapi_driver import _HTTP_METHODS, _slug

    if not isinstance(spec, dict):
        return spec
    spec = json.loads(json.dumps(spec))
    spec.setdefault('openapi', '3.0.3')
    info = spec.get('info')
    if not isinstance(info, dict):
        info = {}
        spec['info'] = info
    if server:
        if not (info.get('title') or '').strip():
            info['title'] = (server.name or server.code or 'API').strip()
        if not (info.get('version') or '').strip():
            info['version'] = '1.0'
    paths = spec.get('paths')
    if not isinstance(paths, dict):
        paths = {}
        spec['paths'] = paths
    used = set()
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in _HTTP_METHODS:
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue
            oid = (op.get('operationId') or '').strip()
            if not oid:
                oid = _slug('%s_%s' % (method, path))
            base = oid
            suffix = 2
            while oid in used:
                oid = '%s_%s' % (base, suffix)
                suffix += 1
            if op.get('operationId') != oid:
                path_item[method] = dict(op)
                path_item[method]['operationId'] = oid
            used.add(oid)
    return spec


def validate_openapi_spec(spec, base_url=''):
    """Structural checks before persisting a generated spec.

    Returns ``(spec, warnings)``; raises ``OpenAPISpecGeneratorError`` on
    hard failures.
    """
    from ..lib.api.drivers.openapi_driver import OpenAPIDriver

    if not isinstance(spec, dict):
        raise OpenAPISpecGeneratorError(
            'The generated document is not a JSON object.')
    driver = OpenAPIDriver()
    try:
        driver._as_spec_dict(spec, 'generated draft')
    except Exception as exc:
        raise OpenAPISpecGeneratorError(str(exc))

    warnings = []
    paths = spec.get('paths') or {}
    if not paths:
        raise OpenAPISpecGeneratorError(
            'The generated spec has no paths.')

    has_operations = False
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, op in path_item.items():
            if method not in (
                    'get', 'put', 'post', 'delete', 'patch', 'options', 'head'):
                continue
            if isinstance(op, dict):
                has_operations = True
                break
        if has_operations:
            break
    if not has_operations:
        raise OpenAPISpecGeneratorError(
            'The generated spec has no HTTP operations in paths.')

    base = (base_url or '').strip().rstrip('/')
    servers = spec.get('servers') or []
    if base and not servers:
        spec = dict(spec)
        spec['servers'] = [{'url': base}]
        warnings.append(
            'Added servers[0] from the server Base URL (%s).' % base)
    elif base and isinstance(servers, list) and servers:
        first = servers[0] if isinstance(servers[0], dict) else {}
        url = (first.get('url') or '').strip()
        if url and not url.startswith('http'):
            spec = dict(spec)
            spec['servers'] = [{'url': base}] + list(servers[1:])
            warnings.append(
                'Replaced relative servers[0] with the configured Base URL.')

    return spec, warnings


def fetch_documentation(env, url, timeout=30):
    """GET documentation and return useful plain text (not raw SPA shell)."""
    url = (url or '').strip()
    if not url:
        raise OpenAPISpecGeneratorError('Documentation URL is required.')
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise OpenAPISpecGeneratorError('Invalid documentation URL: %s' % url)

    Whitelist = env['ai.url.whitelist'].sudo()
    if not Whitelist.is_domain_whitelisted(parsed.hostname, kind='web'):
        raise OpenAPISpecGeneratorError(
            'Documentation host %s is not on the web URL whitelist. '
            'Add it under AI Engine → URL Whitelist, then retry.'
            % parsed.hostname)

    try:
        resp = _request_public_http(
            'GET',
            url,
            timeout=(5, timeout),
            headers={
                'Accept': (
                    'text/markdown, text/plain, text/html;q=0.9, '
                    'application/json;q=0.8, */*;q=0.5'
                ),
                'User-Agent': _BROWSER_UA,
            },
        )
        resp.raise_for_status()
    except (ValueError, requests.RequestException) as exc:
        raise OpenAPISpecGeneratorError(
            'Could not reach the documentation URL: %s' % exc)

    body = resp.text or ''
    raw_len = len(body)
    if len(body) > _MAX_DOC_CHARS:
        body = body[:_MAX_DOC_CHARS]
        _logger.info(
            'openapi_spec_generator: truncated documentation from %s', url)
    if not body.strip():
        raise OpenAPISpecGeneratorError(
            'The documentation URL returned an empty body.')

    ctype = resp.headers.get('Content-Type') or ''
    plain = extract_documentation_payload(body, content_type=ctype)
    _logger.info(
        'openapi_spec_generator: url=%s raw_bytes=%s plain_chars=%s ctype=%s',
        url, raw_len, len(plain or ''), ctype[:80])
    return assert_useful_documentation(plain)


def resolve_openapi_gen_system_prompt(server):
    """Per-server system prompt; falls back to the module default."""
    custom = (getattr(server, 'openapi_gen_prompt', None) or '').strip()
    return custom or DEFAULT_OPENAPI_GEN_SYSTEM_PROMPT


def _build_llm_prompts(server, docs_text):
    """System = server prompt; user = documentation only."""
    system = resolve_openapi_gen_system_prompt(server)
    user = (
        'Use only this documentation page. Do not follow links.\n\n'
        'Documentation page:\n\n%s' % docs_text[:_MAX_LLM_CHARS]
    )
    return system, user


def _llm_call(env, system, user, usage_acc,
              max_tokens=_LLM_MAX_TOKENS, timeout=_LLM_TIMEOUT):
    from ..utils.agent_engine import llm_json_completion_for_agent
    from ..utils.llm_usage import add_usage

    result = llm_json_completion_for_agent(
        env, system, user,
        consumer_key='admin',
        max_tokens=max_tokens, timeout=timeout, json_mode=False,
        failover_on_overflow=True,
        max_providers=_LLM_MAX_PROVIDERS,
    )
    usage_acc = add_usage(usage_acc, (result or {}).get('usage') or {})
    content = ((result or {}).get('content') or '').strip()
    if content:
        return content, usage_acc
    err = ((result or {}).get('error') or '').strip()
    if err:
        raise OpenAPISpecGeneratorError(_format_llm_call_error(err, result))
    raise OpenAPISpecGeneratorError(
        'The AI provider returned an empty response. '
        'Check the model timeout and max output tokens.')


def _format_llm_call_error(err, result=None):
    """Human-readable conversion failure (timeout / cascade exhausted)."""
    text = (err or '').strip()
    lower = text.lower()
    provider = (result or {}).get('provider')
    pname = ''
    try:
        if provider and getattr(provider, 'name', None):
            pname = provider.name or ''
    except Exception:
        pname = ''
    timed_out = (
        'timed out' in lower
        or 'timeout' in lower
        or 'errno 110' in lower
        or 'connection timed out' in lower
    )
    if timed_out:
        base = (
            'AI conversion timed out after %ss'
            % _LLM_TIMEOUT
        )
        if pname:
            base += ' (last provider: %s)' % pname
        return (
            '%s. Tried up to %s Admin providers. Check AI Admin failovers '
            '(Settings → AI Engine → AI Admin) or try again. Detail: %s'
            % (base, _LLM_MAX_PROVIDERS, text[:400])
        )
    if pname:
        return (
            'AI provider error during conversion (%s): %s'
            % (pname, text[:500])
        )
    return 'AI provider error during conversion: %s' % text[:500]


def generate_spec_from_documentation(env, server, docs_text, after_llm=None):
    """Call the AI Admin provider cascade and return ``(spec, warnings, usage)``.

    ``after_llm(text, usage)`` runs as soon as the model replies, before parse.
    The wizard uses it to persist the JSON so a dying HTTP request cannot
    throw the spec away.
    """
    # Presence check (tests may mock this); live path uses admin failover.
    provider = server._detection_llm_provider()
    if not provider:
        raise OpenAPISpecGeneratorError(
            'No AI provider is configured for conversion.')

    plain = documentation_to_text(docs_text)
    if not plain:
        raise OpenAPISpecGeneratorError(
            'The fetched documentation page has no readable text.')
    plain = assert_useful_documentation(plain)

    system, user = _build_llm_prompts(server, plain)
    usage_acc = {}
    text, usage_acc = _llm_call(env, system, user, usage_acc)
    if after_llm:
        after_llm(text, usage_acc)
    cleaned = _escape_raw_controls_in_json_strings((text or '').strip())
    spec = extract_json_object(cleaned)
    extra_warnings = []
    if spec and _balanced_json_object(cleaned) is None:
        extra_warnings.append(
            'The model output was truncated; the draft was closed '
            'automatically. Review missing paths before applying.'
        )
    if spec:
        spec = normalize_generated_spec(spec, server)
        try:
            spec, warnings = validate_openapi_spec(
                spec, base_url=(server.base_url or '').strip())
        except OpenAPISpecGeneratorError as exc:
            return spec, extra_warnings + [str(exc)], usage_acc
        return spec, extra_warnings + list(warnings or []), usage_acc

    raise OpenAPISpecGeneratorError(
        'The model JSON could not be parsed. The raw draft is on the form.',
        raw_text=text,
    )

