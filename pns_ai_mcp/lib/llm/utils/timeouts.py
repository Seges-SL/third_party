# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""
utils/timeouts.py — Centralized timeout constants for the LLM drivers.

All timeout values (in seconds) live here so they can be adjusted in one place.
"""

# ---------------------------------------------------------------------------
# MCP Client (httpx) — calls from orchestrator → Odoo MCP server
# ---------------------------------------------------------------------------

# TCP connection + write + pool (shared for all calls)
MCP_CONNECT_TIMEOUT: float = 10.0
MCP_WRITE_TIMEOUT:   float = 10.0
MCP_POOL_TIMEOUT:    float = 10.0

# Read timeouts vary by operation
MCP_READ_DEFAULT:         float = 60.0   # tools/list, resources/list, get_context, …
MCP_READ_EXECUTE_CODE:    float = 120.0  # relaxaicode  (Python runs server-side)
MCP_READ_RESOURCE:        float = 120.0  # resources/read       (may load large contexts)

# Cache TTL for list_tools / list_resources responses (seconds)
MCP_CACHE_TTL: float = 300.0  # 5 minutes

# ---------------------------------------------------------------------------
# LLM Driver (HTTP/requests) — calls from driver → LLM backend
# ---------------------------------------------------------------------------

# Default timeout for a single LLM HTTP request (OpenAI-compat or Anthropic)
LLM_HTTP_DEFAULT:    float = 240.0  # normal prompts (raised: 120→240 — qwen3:30b needs headroom)
# Retry attempt after Ollama 500 — intentionally shorter to detect hangs fast
LLM_HTTP_RETRY:      float = 90.0
