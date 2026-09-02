# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""PNS AI MCP - PATANEGRA Soft (https://patanegra.com).

Part of Patanegra Soft Suite (`pns_suite`), distributed via Patanegra Soft Hub.
MCP server and reference implementation of the Patanegra Application Agent Protocol (PAAP).
Licensed under the Apache License 2.0 - see LICENSE.
"""

from . import models
from .hooks import post_init_hook, uninstall_hook
from . import wizard
from . import controllers
from . import http_patch  # noqa: F401 - Parche para POST /mcp/sse con application/json
