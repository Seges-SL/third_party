# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""External API access layer (self-documented APIs: MCP, OpenAPI).

Mirror of ``lib/llm``: a small SPI with one driver per ``api_type`` of the
``ai.api.server`` model. The engine never hardcodes a concrete API: everything
comes from the server record + the catalogue the driver discovers.
"""
from . import drivers
