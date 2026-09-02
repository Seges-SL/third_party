# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""No-op: superseded by ``is_on_premise`` in 3.1.291 (no name hardcoding)."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(
        'MCP 3.1.290: skipped (cost_policy replaced by is_on_premise in 3.1.291)',
    )
