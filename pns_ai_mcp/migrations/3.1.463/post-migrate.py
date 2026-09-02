# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.463: retire commercial_documents → business_documents leftover."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_OLD_CODES = (
    'domain_knowledge_commercial_documents',
    'discovery_domain_knowledge_commercial_documents',
    'discovery_domain_knowledge_commercial_documents_es_ES',
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    Context = env['ai.context'].with_context(
        active_test=False,
        skip_hardcoded_restrictions=True,
    )
    stale = Context.search([('code', 'in', list(_OLD_CODES))])
    if stale:
        codes = stale.mapped('code')
        stale.unlink()
        _logger.info(
            'pns_ai_mcp 3.1.463: unlinked leftover commercial_documents %s',
            codes,
        )
    if hasattr(Context, '_unlink_retired_factory_discovery'):
        retired = Context._unlink_retired_factory_discovery()
        _logger.info(
            'pns_ai_mcp 3.1.463: retired factory discovery=%s', retired,
        )
