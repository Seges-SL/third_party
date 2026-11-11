# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Common utilities and classes for the MCP server."""

import json
import logging
import re

# Apply the filter to the module logger
_logger = logging.getLogger(__name__)


class APIKeyLogFilter(logging.Filter):
    """Filter that strips API keys from the logs"""
    
    def filter(self, record):
        """Mask any api_key=VALUE mention in log messages"""
        if hasattr(record, 'msg') and record.msg:
            # Convert to string if it is not one
            msg = str(record.msg)
            # Pattern for api_key=VALUE (any value)
            # Replace api_key=VALUE with api_key=***
            msg = re.sub(
                r'(?i)(api[_-]?key\s*=\s*)([^\s&"\'\)]+)',
                r'\1***',
                msg
            )
            # Pattern for api_key in query strings
            msg = re.sub(
                r'(?i)([?&]api[_-]?key=)([^&\s"]+)',
                r'\1***',
                msg
            )
            record.msg = msg
        
        # Also filter the args, if any
        if hasattr(record, 'args') and record.args:
            filtered_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    arg = re.sub(
                        r'(?i)(api[_-]?key\s*=\s*)([^\s&"\'\)]+)',
                        r'\1***',
                        arg
                    )
                    arg = re.sub(
                        r'(?i)([?&]api[_-]?key=)([^&\s"]+)',
                        r'\1***',
                        arg
                    )
                filtered_args.append(arg)
            record.args = tuple(filtered_args)
        
        return True


# Apply the filter to the logger
_logger.addFilter(APIKeyLogFilter())


def mcp_jsonrpc_http_status(error_message, explicit=None):
    """JSON-RPC body stays in the payload. Auth failures are HTTP 401."""
    if explicit is not None:
        return int(explicit)
    if 'api key' in (error_message or '').lower():
        return 401
    return 200


class MCPJSONRPCError(Exception):
    """Custom exception for MCP errors in JSON-RPC format"""
    def __init__(self, error_code, error_message, request_id=None, http_status=None):
        self.error_code = error_code
        self.error_message = error_message
        self.request_id = request_id
        self.http_status = mcp_jsonrpc_http_status(error_message, http_status)
        # Build the full JSON-RPC response as a string
        error_response = {
            'jsonrpc': '2.0',
            'error': {
                'code': error_code,
                'message': error_message
            },
            'id': request_id
        }
        self.jsonrpc_response = json.dumps(error_response)
        super().__init__(error_message)

