# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Centralized constants for pns_ai_mcp."""

# Minutes a pending Safe Plan waits for the human before it expires.
PENDING_OPERATION_TTL_MINUTES = 15

# Seconds the card of a high-danger plan must stay on screen before Confirm
# is accepted. The browser shows the same wait; the server enforces it.
HIGH_CONFIRM_WAIT_SECONDS = 5
