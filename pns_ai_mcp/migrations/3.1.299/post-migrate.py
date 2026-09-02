# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""v3.1.299: domain index becomes context_type='discover'.

The bespoke ``ai/domain_index/*.json`` loader and the transient
``ai.domain.index.entry`` model are retired. Routing now lives as
``ai.context`` rows seeded from ``contexts/discover/*.json``. Reimport the
context library so those rows materialise, then rebuild agent caches (the
turn-scoped indexed codes now derive from discover rows).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return

    # 1) Reimport contexts from files → materialise discover rows.
    try:
        res = env['ai.context'].sudo()._import_all_from_module(
            replace_existing=True,
        )
        _logger.info('MCP 3.1.299: context reimport %s', res)
    except Exception:
        _logger.warning('MCP 3.1.299: context reimport failed', exc_info=True)

    # 2) Rebuild agent caches (indexed codes now come from discover rows).
    if 'ai.agent' not in env:
        return
    for agent in env['ai.agent'].search([]):
        try:
            if hasattr(agent, 'action_rebuild_cache'):
                agent.action_rebuild_cache()
            else:
                agent.get_content(force_rebuild=True)
        except Exception:
            _logger.warning(
                'MCP 3.1.299: cache rebuild failed for %s',
                agent.code, exc_info=True,
            )
