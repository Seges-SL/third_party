# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""HTTP JSON-RPC smoke tests against the /mcp endpoint."""

import json

from odoo.tests import tagged, HttpCase

from odoo.addons.pns_ai_mcp.tests._helpers import (
    http_response_text,
    http_status_code,
    mcp_test_headers,
    mcp_test_url,
    setup_http_mcp_fixtures,
    teardown_http_mcp_fixtures,
)


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestMcpHttp(HttpCase):

    @classmethod
    def tearDownClass(cls):
        teardown_http_mcp_fixtures(cls)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        setup_http_mcp_fixtures(type(self), self.env)
        self.test_api_key = type(self).test_api_key

    def _mcp_jsonrpc(self, method, params=None, req_id=1):
        payload = {
            'jsonrpc': '2.0',
            'id': req_id,
            'method': method,
            'params': params or {},
        }
        return self.url_open(
            mcp_test_url('/mcp', self.test_api_key),
            data=json.dumps(payload).encode('utf-8'),
            headers=mcp_test_headers(self.test_api_key),
        )

    def _parse_json_response(self, response, context):
        status = http_status_code(response)
        text = http_response_text(response)
        self.assertEqual(
            status, 200,
            '%s: HTTP %s body=%r' % (context, status, text[:500]),
        )
        try:
            body = json.loads(text)
        except ValueError as exc:
            self.fail('%s: invalid JSON (%s) body=%r' % (context, exc, text[:500]))
        if 'error' in body and 'result' not in body:
            self.fail('%s: MCP error %s' % (context, body['error']))
        return body

    def test_mcp_initialize(self):
        response = self._mcp_jsonrpc('initialize', {
            'protocolVersion': '2024-11-05',
            'capabilities': {},
            'clientInfo': {'name': 'unit-test', 'version': '1.0'},
        }, req_id=1)
        body = self._parse_json_response(response, 'initialize')
        self.assertIn('result', body)
        self.assertEqual(body['result']['serverInfo']['name'], 'pns_ai_mcp')
        self.assertIn('protocolVersion', body['result'])
        self.assertNotIn('resources', body['result']['capabilities'])

    def test_mcp_resources_methods_not_found(self):
        for method in ('resources/list', 'resources/read'):
            response = self._mcp_jsonrpc(method, {'uri': 'system://info'})
            status = http_status_code(response)
            text = http_response_text(response)
            self.assertEqual(
                status, 200,
                '%s: HTTP %s body=%r' % (method, status, text[:500]),
            )
            body = json.loads(text)
            self.assertIn('error', body, '%s: expected Method not found' % method)
            self.assertEqual(body['error']['code'], -32601)

    def _mcp_stateless_params(self, extra=None):
        params = {
            '_meta': {
                'io.modelcontextprotocol/protocolVersion': '2026-07-28',
                'io.modelcontextprotocol/clientInfo': {
                    'name': 'stateless-test',
                    'version': '1.0',
                },
                'io.modelcontextprotocol/clientCapabilities': {},
            },
        }
        if extra:
            params.update(extra)
        return params

    def _mcp_stateless_headers(self):
        headers = mcp_test_headers(self.test_api_key)
        headers['MCP-Protocol-Version'] = '2026-07-28'
        headers['Mcp-Method'] = 'server/discover'
        return headers

    def test_mcp_server_discover_stateless(self):
        payload = {
            'jsonrpc': '2.0',
            'id': 'discover-1',
            'method': 'server/discover',
            'params': self._mcp_stateless_params(),
        }
        headers = self._mcp_stateless_headers()
        response = self.url_open(
            mcp_test_url('/mcp', self.test_api_key),
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
        )
        body = self._parse_json_response(response, 'server/discover')
        result = body['result']
        self.assertEqual(result.get('resultType'), 'complete')
        self.assertIn('2026-07-28', result.get('supportedVersions', []))
        self.assertIn('io.modelcontextprotocol/serverInfo', result.get('_meta', {}))
        self.assertNotIn('resources', result.get('capabilities') or {})

    def test_mcp_stateless_tools_list(self):
        payload = {
            'jsonrpc': '2.0',
            'id': 2,
            'method': 'tools/list',
            'params': self._mcp_stateless_params(),
        }
        headers = mcp_test_headers(self.test_api_key)
        headers['MCP-Protocol-Version'] = '2026-07-28'
        headers['Mcp-Method'] = 'tools/list'
        response = self.url_open(
            mcp_test_url('/mcp', self.test_api_key),
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
        )
        body = self._parse_json_response(response, 'tools/list stateless')
        result = body['result']
        self.assertEqual(result.get('resultType'), 'complete')
        self.assertIn('tools', result)
        self.assertIn('ttlMs', result)
