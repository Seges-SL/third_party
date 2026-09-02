# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Minimal MCP client for calling external MCP servers."""

import json
import logging
import subprocess

import requests

_logger = logging.getLogger(__name__)

# JSON-RPC 2.0 counter (module-level, not critical if shared between threads).
_request_id = 0


def _next_id():
    global _request_id
    _request_id += 1
    return _request_id


def _jsonrpc_request(method, params=None):
    """Build a JSON-RPC 2.0 request dict."""
    msg = {
        'jsonrpc': '2.0',
        'id': _next_id(),
        'method': method,
    }
    if params:
        msg['params'] = params
    return msg


class MCPClientError(Exception):
    """Raised when the MCP client encounters a protocol or transport error."""
    pass


class MCPClient:
    """Minimal MCP client for external server communication.

    Usage::

        client = MCPClient(server_record)
        client.connect()        # initialize handshake
        tools = client.list_tools()  # discover tools
        result = client.call_tool('search', {'query': 'hello'})
        client.close()

    Args:
        server_record: An ``ai.api.server`` Odoo record with
            the server's transport config (type, url, command, auth...).
        auth_token: Optional per-call credential (e.g. the calling user's
            ``ai.api.server.key``). Falls back to the server's default
            ``auth_token`` when not provided.
    """

    def __init__(self, server_record, auth_token=None):
        self.server = server_record
        self.transport = server_record.server_type
        self.timeout = server_record.timeout or 30
        self._auth_token = auth_token
        self._process = None  # subprocess for stdio
        self._session = None  # requests session for SSE
        self._server_info = None

    # ── Transport: SSE (HTTP) ─────────────────────────────────────────────

    def _build_headers(self):
        """Build HTTP headers with authentication."""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
        }
        auth_type = self.server.auth_type
        token = self._auth_token if self._auth_token is not None else (
            self.server.auth_token or '')
        if auth_type == 'bearer' and token:
            headers['Authorization'] = f'Bearer {token}'
        elif auth_type == 'api_key' and token:
            header_name = self.server.auth_header_name or 'Authorization'
            headers[header_name] = token
        elif auth_type == 'custom_header' and token:
            header_name = self.server.auth_header_name or 'X-API-Key'
            headers[header_name] = token
        return headers

    def _http_post(self, payload):
        """POST a JSON-RPC message to the SSE server and return the response."""
        url = self.server.url
        if not url:
            raise MCPClientError("No URL configured for SSE server '%s'" % self.server.code)
        if not self._session:
            self._session = requests.Session()
        try:
            resp = self._session.post(
                url,
                json=payload,
                headers=self._build_headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise MCPClientError("HTTP request to '%s' failed: %s" % (url, e))

        # Parse response — could be plain JSON or SSE event stream.
        ct = resp.headers.get('Content-Type', '')
        if 'text/event-stream' in ct:
            return self._parse_sse_response(resp.text)
        try:
            return resp.json()
        except (ValueError, json.JSONDecodeError):
            raise MCPClientError(
                "Invalid JSON response from '%s': %s" % (url, resp.text[:500]))

    def _parse_sse_response(self, text):
        """Extract the last JSON-RPC result from an SSE event stream."""
        last_data = None
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('data:'):
                last_data = line[5:].strip()
        if last_data:
            try:
                return json.loads(last_data)
            except (ValueError, json.JSONDecodeError):
                pass
        raise MCPClientError("No valid data event in SSE response")

    # ── Transport: stdio ──────────────────────────────────────────────────

    def _stdio_start(self):
        """Spawn the subprocess for stdio transport."""
        cmd = self.server.command
        if not cmd:
            raise MCPClientError(
                "No command configured for stdio server '%s'" % self.server.code)
        try:
            args_json = json.loads(self.server.command_args or '[]')
        except (json.JSONDecodeError, TypeError):
            args_json = []
        try:
            env_json = json.loads(self.server.env_vars or '{}')
        except (json.JSONDecodeError, TypeError):
            env_json = {}

        import os
        env = dict(os.environ)
        env.update(env_json)

        full_cmd = [cmd] + (args_json if isinstance(args_json, list) else [])
        try:
            self._process = subprocess.Popen(
                full_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
        except (OSError, FileNotFoundError) as e:
            raise MCPClientError(
                "Failed to start stdio server '%s' (cmd: %s): %s" % (
                    self.server.code, ' '.join(full_cmd), e))

    def _stdio_send(self, payload):
        """Send a JSON-RPC message via stdin and read the response from stdout."""
        if not self._process or self._process.poll() is not None:
            raise MCPClientError("stdio process is not running")
        msg = json.dumps(payload, ensure_ascii=False) + '\n'
        try:
            self._process.stdin.write(msg.encode('utf-8'))
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise MCPClientError("Failed to write to stdio: %s" % e)

        # Read one line from stdout (JSON-RPC response).
        try:
            line = self._process.stdout.readline()
        except (OSError,) as e:
            raise MCPClientError("Failed to read from stdio: %s" % e)
        if not line:
            stderr = ''
            try:
                stderr = self._process.stderr.read().decode('utf-8', errors='replace')
            except Exception:
                pass
            raise MCPClientError(
                "stdio process closed without response. stderr: %s" % stderr[:500])
        try:
            return json.loads(line.decode('utf-8'))
        except (ValueError, json.JSONDecodeError):
            raise MCPClientError(
                "Invalid JSON from stdio: %s" % line.decode('utf-8', errors='replace')[:500])

    # ── Protocol methods ──────────────────────────────────────────────────

    def _send(self, payload):
        """Send a JSON-RPC message via the configured transport."""
        if self.transport == 'sse':
            return self._http_post(payload)
        elif self.transport == 'stdio':
            return self._stdio_send(payload)
        raise MCPClientError("Unknown transport: %s" % self.transport)

    def _extract_result(self, response):
        """Extract the 'result' from a JSON-RPC response, raising on error."""
        if not isinstance(response, dict):
            raise MCPClientError("Unexpected response type: %s" % type(response))
        if 'error' in response:
            err = response['error']
            msg = err.get('message', str(err)) if isinstance(err, dict) else str(err)
            raise MCPClientError("MCP error: %s" % msg)
        return response.get('result')

    def connect(self):
        """Perform the MCP initialize handshake.

        Returns the server info dict from the initialize response.
        """
        if self.transport == 'stdio':
            self._stdio_start()

        payload = _jsonrpc_request('initialize', {
            'protocolVersion': '2024-11-05',
            'capabilities': {},
            'clientInfo': {
                'name': 'PNS-AI-Odoo',
                'version': '1.0',
            },
        })
        resp = self._send(payload)
        self._server_info = self._extract_result(resp)

        # Send initialized notification (no response expected for notifications).
        notif = {
            'jsonrpc': '2.0',
            'method': 'notifications/initialized',
        }
        try:
            self._send(notif)
        except MCPClientError:
            pass  # notifications may not return a response

        return self._server_info

    def list_tools(self):
        """Discover available tools (tools/list).

        Returns a list of tool dicts: [{'name': ..., 'description': ..., ...}]
        """
        payload = _jsonrpc_request('tools/list')
        resp = self._send(payload)
        result = self._extract_result(resp)
        if isinstance(result, dict) and 'tools' in result:
            return result['tools']
        if isinstance(result, list):
            return result
        return []

    def list_resources(self):
        """Discover available resources (resources/list).

        Returns a list of resource dicts: [{'uri': ..., 'name': ..., ...}].
        Servers that do not advertise the ``resources`` capability may reply
        with a JSON-RPC error; the caller is expected to handle that.
        """
        payload = _jsonrpc_request('resources/list')
        resp = self._send(payload)
        result = self._extract_result(resp)
        if isinstance(result, dict) and 'resources' in result:
            return result['resources']
        if isinstance(result, list):
            return result
        return []

    def list_prompts(self):
        """Discover available prompts/contexts (prompts/list).

        Returns a list of prompt dicts: [{'name': ..., 'description': ..., ...}].
        Servers that do not advertise the ``prompts`` capability may reply with
        a JSON-RPC error; the caller is expected to handle that.
        """
        payload = _jsonrpc_request('prompts/list')
        resp = self._send(payload)
        result = self._extract_result(resp)
        if isinstance(result, dict) and 'prompts' in result:
            return result['prompts']
        if isinstance(result, list):
            return result
        return []

    def call_tool(self, tool_name, arguments=None):
        """Call a tool on the external server (tools/call).

        Args:
            tool_name: Name of the tool to call.
            arguments: Dict of arguments to pass to the tool.

        Returns:
            The tool result (content array from the MCP response).
        """
        payload = _jsonrpc_request('tools/call', {
            'name': tool_name,
            'arguments': arguments or {},
        })
        resp = self._send(payload)
        result = self._extract_result(resp)
        # MCP tools/call returns {content: [...], isError: bool}
        if isinstance(result, dict):
            if result.get('isError'):
                content = result.get('content', [])
                error_text = ''
                for c in content:
                    if isinstance(c, dict) and c.get('type') == 'text':
                        error_text += c.get('text', '')
                raise MCPClientError("Tool '%s' returned error: %s" % (
                    tool_name, error_text or str(result)))
            return result.get('content', [])
        return result

    def close(self):
        """Cleanup: close HTTP session or kill subprocess."""
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None
        if self._process:
            try:
                self._process.stdin.close()
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
