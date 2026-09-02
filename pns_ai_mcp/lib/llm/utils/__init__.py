# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>

from .tool_utils import extract_tool_calls_from_response, format_tool_result_for_model
from .mcp_utils import (
    should_load_mcp_tools,
    DEFAULT_DOMAIN_TRIGGER_KEYWORDS,
    extract_user_token_from_request,
    get_locale_settings,
    build_mcp_extra_headers
)

__all__ = [
    "extract_tool_calls_from_response",
    "format_tool_result_for_model",
    "should_load_mcp_tools",
    "DEFAULT_DOMAIN_TRIGGER_KEYWORDS",
    "extract_user_token_from_request",
    "get_locale_settings",
    "build_mcp_extra_headers"
]
