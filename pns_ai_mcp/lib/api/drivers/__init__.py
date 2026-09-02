# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from .base import APIDriver, APIDriverError, build_auth_headers
from .mcp_driver import MCPDriver
from .openapi_driver import OpenAPIDriver
from .registry import get_api_driver, list_api_driver_types, register_api_driver

register_api_driver('mcp', MCPDriver)
register_api_driver('openapi', OpenAPIDriver)

__all__ = [
    'APIDriver',
    'APIDriverError',
    'MCPDriver',
    'OpenAPIDriver',
    'build_auth_headers',
    'get_api_driver',
    'list_api_driver_types',
    'register_api_driver',
]
