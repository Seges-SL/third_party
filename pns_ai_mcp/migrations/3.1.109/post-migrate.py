# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Refresh domain context ``geo`` (enrich_geo street/postal/province aliases)."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    try:
        env['ai.context'].with_context(
            skip_hardcoded_restrictions=True,
        )._import_all_from_module(
            replace_existing=True,
            module_name='pns_ai_mcp',
            only_codes=['geo'],
        )
        _logger.info(
            'MCP 3.1.109: domain context geo refreshed (address aliases)',
        )
    except Exception:
        _logger.warning(
            'MCP 3.1.109: failed to refresh geo context', exc_info=True,
        )
