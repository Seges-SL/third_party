# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.546: Detection rows hang off existing API servers (identity tokens)."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.api.server' not in env:
        return
    Server = env['ai.api.server'].with_context(active_test=False)
    servers = Server.search([])
    if not servers:
        return
    if hasattr(servers, '_ensure_identity_detection'):
        servers._ensure_identity_detection()
    _logger.info(
        'pns_ai_mcp 3.1.546: identity Detection upserted for %s server(s)',
        len(servers),
    )
