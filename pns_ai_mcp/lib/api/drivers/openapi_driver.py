# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""
openapi_driver.py — API driver for OpenAPI/Swagger servers (api_type='openapi').

STRUCTURAL RULE (no domain hardcode): nothing here knows any concrete API.
The whole surface comes from the spec document: each operation with an
``operationId`` becomes a tool (name + description + inputSchema in MCP
shape), and calls are executed generically from the spec's method/path/
parameter declarations.

The spec is loaded from ``spec_url`` (remote JSON) unless ``spec_manual``
is set, in which case the pasted ``spec_json`` is the source of truth and
is never re-downloaded.

Argument convention for calls (mirrors the tool inputSchema this driver
generates): path/query parameters are TOP-LEVEL keys of ``arguments``; the
JSON request body, when the operation declares one, goes under the reserved
key ``body``.
"""

import json
import logging
import re
from urllib.parse import quote, urljoin, urlparse

import requests

from .base import APIDriver, APIDriverError, build_auth_headers

_logger = logging.getLogger(__name__)

# HTTP methods that can appear as OpenAPI path operations.
_HTTP_METHODS = ('get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace', 'query')
# Methods whose semantics accept a request body.
_BODY_METHODS = {'post', 'put', 'patch', 'delete', 'query'}


def _slug(text):
    return re.sub(r'[^A-Za-z0-9_]+', '_', text or '').strip('_')


class OpenAPIDriver(APIDriver):
    """Driver for OpenAPI/Swagger described HTTP APIs."""

    api_type = 'openapi'

    # ── Spec handling ─────────────────────────────────────────────────────

    @staticmethod
    def _spec_is_manual(server):
        """True when the admin froze a pasted/converted spec_json."""
        return bool(getattr(server, 'spec_manual', False))

    @staticmethod
    def _as_spec_dict(spec, origin):
        """Reject documents that are not an OpenAPI/Swagger spec with paths."""
        if not isinstance(spec, dict) or not isinstance(spec.get('paths'), dict):
            raise APIDriverError(
                'The document %s does not look like an OpenAPI spec '
                "(missing 'paths')." % origin)
        return spec

    def _fetch_spec(self, server):
        """Download and parse the OpenAPI spec (JSON) from ``spec_url``."""
        spec_url = (server.spec_url or '').strip()
        if not spec_url:
            raise APIDriverError(
                "No spec URL configured for OpenAPI server '%s'" % server.code)
        try:
            resp = requests.get(
                spec_url,
                timeout=(5, server.timeout or 30),
                headers={
                    'Accept': 'application/json',
                    'User-Agent': 'PNS-AI-APIDriver/1.0',
                    **build_auth_headers(server),
                },
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise APIDriverError('Fetching OpenAPI spec failed: %s' % e)
        try:
            spec = resp.json()
        except ValueError:
            raise APIDriverError(
                'The spec at %s is not valid JSON. Point spec_url at the '
                'openapi.json / swagger.json document.' % spec_url)
        return self._as_spec_dict(spec, 'at %s' % spec_url)

    @staticmethod
    def _load_cached_spec(server, strict=False):
        """Parse the cached spec (``spec_json``); empty dict when absent.

        ``strict`` raises on invalid JSON (manual paste). Remote servers fall
        through to a re-fetch instead of failing on a stale cache.
        """
        raw = server.spec_json or ''
        if not str(raw).strip():
            return {}
        try:
            spec = json.loads(raw)
            return spec if isinstance(spec, dict) else {}
        except (json.JSONDecodeError, TypeError) as e:
            if strict:
                raise APIDriverError(
                    "Pasted OpenAPI spec for server '%s' is not valid JSON: %s"
                    % (getattr(server, 'code', None) or '?', e))
            return {}

    def _resolve_spec(self, server, fetch=True):
        """Working spec: pasted cache when manual, else cache or download."""
        strict = self._spec_is_manual(server)
        spec = self._load_cached_spec(server, strict=strict)
        if spec:
            return self._as_spec_dict(
                spec, "pasted spec_json of server '%s'" % (
                    getattr(server, 'code', None) or '?'))
        if strict or not fetch:
            raise APIDriverError(
                "No OpenAPI spec pasted for server '%s'. Paste the JSON in "
                'the OpenAPI Spec tab.' % (getattr(server, 'code', None) or '?'))
        return self._fetch_spec(server)

    @staticmethod
    def _resolve_schema(spec, schema):
        """Resolve one level of local ``$ref`` (components/schemas)."""
        if not isinstance(schema, dict):
            return {}
        ref = schema.get('$ref')
        if isinstance(ref, str) and ref.startswith('#/'):
            node = spec
            for part in ref[2:].split('/'):
                node = node.get(part) if isinstance(node, dict) else None
                if node is None:
                    return {}
            return node if isinstance(node, dict) else {}
        return schema

    # ── Catalogue (spec → MCP-shaped tools) ───────────────────────────────

    def _spec_to_tools(self, spec):
        """Map every operation of the spec to an MCP-shaped tool dict."""
        tools = []
        for path, path_item in (spec.get('paths') or {}).items():
            if not isinstance(path_item, dict):
                continue
            shared_params = path_item.get('parameters') or []
            for method in _HTTP_METHODS:
                op = path_item.get(method)
                if not isinstance(op, dict):
                    continue
                name = op.get('operationId') or _slug('%s_%s' % (method, path))
                desc_bits = [op.get('summary') or '', op.get('description') or '']
                description = ' — '.join(b.strip() for b in desc_bits if b.strip())
                properties, required = {}, []
                for param in list(shared_params) + list(op.get('parameters') or []):
                    param = self._resolve_schema(spec, param)
                    pname = param.get('name')
                    if not pname or param.get('in') not in ('path', 'query'):
                        continue
                    pschema = self._resolve_schema(spec, param.get('schema') or {})
                    properties[pname] = {
                        'type': pschema.get('type') or 'string',
                        'description': (param.get('description') or '').strip(),
                    }
                    if param.get('required') or param.get('in') == 'path':
                        required.append(pname)
                body = self._resolve_schema(spec, op.get('requestBody') or {})
                if body:
                    content = body.get('content') or {}
                    json_media = next(
                        (v for k, v in content.items() if 'json' in k), None)
                    if isinstance(json_media, dict):
                        body_schema = self._resolve_schema(
                            spec, json_media.get('schema') or {})
                        properties['body'] = body_schema or {'type': 'object'}
                        if body.get('required'):
                            required.append('body')
                tools.append({
                    'name': name,
                    'description': description,
                    'inputSchema': {
                        'type': 'object',
                        'properties': properties,
                        'required': required,
                    },
                    # Execution metadata (driver-internal, harmless in prompts).
                    'x-http': {'method': method.upper(), 'path': path},
                })
        return tools

    def discover(self, server):
        if self._spec_is_manual(server):
            spec = self._resolve_spec(server, fetch=False)
        else:
            spec = self._fetch_spec(server)
        return {
            'tools': self._spec_to_tools(spec),
            'resources': [],
            'prompts': [],
            'spec': spec,
            'warnings': [],
        }

    def test_connection(self, server):
        if self._spec_is_manual(server):
            spec = self._resolve_spec(server, fetch=False)
            info = spec.get('info') or {}
            return 'OpenAPI %s: %s %s (manual spec)' % (
                spec.get('openapi') or spec.get('swagger') or '?',
                info.get('title') or '?',
                info.get('version') or '',
            )
        spec = self._fetch_spec(server)
        info = spec.get('info') or {}
        return 'OpenAPI %s: %s %s' % (
            spec.get('openapi') or spec.get('swagger') or '?',
            info.get('title') or '?',
            info.get('version') or '',
        )

    @staticmethod
    def api_key_header_names(spec):
        """Header names of ``apiKey`` schemes in the spec (unique, document order).

        OpenAPI 3 ``components.securitySchemes`` and OAS2 ``securityDefinitions``.
        Query/cookie apiKeys are ignored.
        """
        if not isinstance(spec, dict):
            return []
        schemes = {}
        components = spec.get('components')
        if isinstance(components, dict) and isinstance(
                components.get('securitySchemes'), dict):
            schemes.update(components['securitySchemes'])
        definitions = spec.get('securityDefinitions')
        if isinstance(definitions, dict):
            schemes.update(definitions)
        names = []
        for sch in schemes.values():
            if not isinstance(sch, dict):
                continue
            if sch.get('type') != 'apiKey':
                continue
            if (sch.get('in') or '').lower() != 'header':
                continue
            name = (sch.get('name') or '').strip()
            if name and name not in names:
                names.append(name)
        return names

    @staticmethod
    def api_key_header_name(spec):
        """Unique ``apiKey`` header name declared in the spec, or None.

        Ambiguous (0 or >1 header apiKeys) returns None — the form must not
        guess a header that is not on the ficha.
        """
        names = OpenAPIDriver.api_key_header_names(spec)
        if len(names) == 1:
            return names[0]
        return None

    # ── Execution ─────────────────────────────────────────────────────────

    def _base_url(self, server, spec):
        """Effective base URL: server override → spec servers[0] → spec origin."""
        if server.base_url:
            return server.base_url.rstrip('/')
        servers = spec.get('servers') or []
        if servers and isinstance(servers[0], dict) and servers[0].get('url'):
            # Spec server URLs may be relative to the spec document location.
            return urljoin(server.spec_url or '', servers[0]['url']).rstrip('/')
        parsed = urlparse(server.spec_url or '')
        if parsed.scheme and parsed.netloc:
            return '%s://%s' % (parsed.scheme, parsed.netloc)
        raise APIDriverError(
            "Cannot determine the base URL for OpenAPI server '%s': set "
            'base_url or use a spec with a servers[] entry.' % server.code)

    def _find_operation(self, spec, tool_name):
        """Locate (method, path, declared params, operation) for an operationId."""
        for path, path_item in (spec.get('paths') or {}).items():
            if not isinstance(path_item, dict):
                continue
            shared_params = path_item.get('parameters') or []
            for method in _HTTP_METHODS:
                op = path_item.get(method)
                if not isinstance(op, dict):
                    continue
                name = op.get('operationId') or _slug('%s_%s' % (method, path))
                if name == tool_name:
                    params = list(shared_params) + list(op.get('parameters') or [])
                    return method.upper(), path, [
                        self._resolve_schema(spec, p) for p in params
                    ], op
        raise APIDriverError(
            "Operation '%s' is not in the discovered spec. Re-run Discover "
            'Tools and use only catalogued operation names.' % tool_name)

    @staticmethod
    def _operation_expects_binary(op):
        """True when OpenAPI declares non-JSON success content (files, streams)."""
        content_types = set()
        for code, resp in (op.get('responses') or {}).items():
            if not str(code).startswith('2'):
                continue
            for ct in ((resp or {}).get('content') or {}):
                content_types.add(ct.split(';', 1)[0].strip().lower())
        if not content_types:
            return False
        if content_types == {'application/json'}:
            return False
        return any(
            'octet-stream' in ct or 'pdf' in ct or ct.startswith('image/')
            or ct.startswith('audio/') or ct.startswith('video/')
            or ('json' not in ct and ct.startswith('application/'))
            for ct in content_types
        )

    def call(self, server, tool_name, arguments=None, auth_token=None):
        arguments = dict(arguments or {})
        spec = self._resolve_spec(server, fetch=not self._spec_is_manual(server))
        method, path, params, operation = self._find_operation(spec, tool_name)
        expects_binary = self._operation_expects_binary(operation)

        # Path parameters (required by definition).
        for param in params:
            if param.get('in') != 'path':
                continue
            pname = param.get('name')
            if pname not in arguments:
                raise APIDriverError(
                    "Missing required path parameter '%s' for operation '%s'."
                    % (pname, tool_name))
            path = path.replace(
                '{%s}' % pname, quote(str(arguments.pop(pname)), safe=''))

        # Declared query parameters present in the arguments.
        query = {}
        for param in params:
            pname = param.get('name')
            if param.get('in') == 'query' and pname in arguments:
                value = arguments.pop(pname)
                if value is not None:
                    query[pname] = value

        body = arguments.pop('body', None)
        headers = {
            'User-Agent': 'PNS-AI-APIDriver/1.0',
            **build_auth_headers(server, auth_token),
        }
        if expects_binary:
            headers['Accept'] = (
                'application/octet-stream, application/pdf, application/*, */*'
            )
        else:
            headers['Accept'] = 'application/json, */*'
        data = None
        if body is not None and method.lower() in _BODY_METHODS:
            headers['Content-Type'] = 'application/json'
            data = (body if isinstance(body, str)
                    else json.dumps(body, ensure_ascii=False)).encode('utf-8')

        url = self._base_url(server, spec) + path
        try:
            resp = requests.request(
                method,
                url,
                params=query or None,
                data=data,
                headers=headers,
                timeout=(5, server.timeout or 30),
            )
        except requests.RequestException as e:
            raise APIDriverError('HTTP request to %s failed: %s' % (url, e))
        if resp.status_code >= 400:
            raise APIDriverError(
                "Operation '%s' returned HTTP %s: %s"
                % (tool_name, resp.status_code, (resp.text or '')[:500]))
        content_type = resp.headers.get('Content-Type', '')
        content_disposition = resp.headers.get('Content-Disposition', '')
        raw = resp.content or b''
        try:
            from ....utils.session_download import (
                is_binary_content_type,
                looks_like_binary_bytes,
            )
            if (
                expects_binary
                or is_binary_content_type(content_type, content_disposition)
                or looks_like_binary_bytes(raw)
            ):
                return {
                    '_binary': True,
                    'content': raw,
                    'content_type': content_type or 'application/octet-stream',
                    'content_disposition': content_disposition,
                    'url': url,
                }
        except Exception:
            pass
        return resp.text or ''
