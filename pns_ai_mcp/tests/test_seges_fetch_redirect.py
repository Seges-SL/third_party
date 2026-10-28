# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 19 (tests de la entrega E2′). Ver docs/pendiente/parches_pns_ai.md
"""Parche 19 (PNS-17): la cabecera de autenticación no sigue a otro host.

Sin red: ``requests`` está sustituido. En ``request_public_http`` el primer
salto redirige a otro host público y el segundo responde; los dos hosts pasan
por públicos (``non_public_host_error`` sustituido). El cliente MCP por HTTP ya
no sigue redirecciones: da un error claro.
"""

from types import SimpleNamespace
from unittest import mock

from odoo.tests import TransactionCase, tagged

from odoo.addons.pns_ai_mcp.utils import fetch_url_safe
from odoo.addons.pns_ai_mcp.utils.mcp_client import MCPClient, MCPClientError

AUTH = {
    'apikey': 'seges-e2p-17-a',
    'Ocp-Apim-Subscription-Key': 'seges-e2p-17-b',
    'User-Agent': 'seges-e2p-17',
    'Accept': 'application/json',
}


class _Resp:
    """Lo que request_public_http y el cliente MCP leen de una respuesta."""

    def __init__(self, status, location=None):
        self.status_code = status
        self.headers = {'Location': location} if location else {}
        self.is_redirect = bool(location)

    def close(self):
        return None

    def iter_content(self, chunk_size=1):
        return iter([b'{}'])

    def raise_for_status(self):
        return None

    def json(self):
        return {'jsonrpc': '2.0', 'id': 1, 'result': {}}


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesFetchRedirect(TransactionCase):

    def _follow(self, first, second):
        sent = []

        def _request(method, url, **kwargs):
            sent.append((url, dict(kwargs.get('headers') or {})))
            if len(sent) == 1:
                return _Resp(302, location=second)
            return _Resp(200)

        with mock.patch.object(fetch_url_safe, 'non_public_host_error',
                               return_value=None), \
                mock.patch('requests.request', side_effect=_request):
            fetch_url_safe.request_public_http('GET', first, headers=dict(AUTH))
        self.assertEqual(len(sent), 2)
        return sent[1][1]

    def test_custom_auth_header_dropped_on_other_host(self):
        headers = self._follow(
            'https://api.seges.invalid/v1', 'https://other.seges-e2p.invalid/v1')
        self.assertNotIn('apikey', headers)
        self.assertNotIn('Ocp-Apim-Subscription-Key', headers)
        self.assertEqual(headers.get('User-Agent'), 'seges-e2p-17')
        self.assertEqual(headers.get('Accept'), 'application/json')

    def test_same_host_keeps_header(self):
        headers = self._follow(
            'https://api.seges.invalid/v1', 'https://api.seges.invalid/v2')
        self.assertEqual(headers.get('apikey'), 'seges-e2p-17-a')

    def test_mcp_client_redirect_refused(self):
        server = SimpleNamespace(
            server_type='sse', timeout=5, url='https://mcp.seges.invalid/mcp',
            code='seges_e2p_17', auth_type='custom_header',
            auth_header_name='apikey')
        client = MCPClient(server, auth_token='seges-e2p-17-a')
        calls = []

        def _post(_session, url, **kwargs):
            calls.append(kwargs)
            return _Resp(302, location='https://other.seges-e2p.invalid/mcp')

        with mock.patch('requests.Session.post', autospec=True, side_effect=_post):
            with self.assertRaisesRegex(MCPClientError, 'redirect'):
                client._http_post({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'})
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0].get('allow_redirects'), False)
