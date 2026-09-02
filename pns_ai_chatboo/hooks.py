# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Uninstall hook for Chatboo.

Translations load from ``i18n/*.po`` on install / ``-u``. Do not rewrite
``ir.translation`` here. Leftover msgstr → bump + one-shot migrate.
Do not ship a stale ``*.pot`` beside the Spanish catalog: Odoo 14
``PoFileReader`` would mark new ``_t()`` tips obsolete.
"""
from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def uninstall_hook(cr, registry):
    """Drop Chatboo-owned factory contexts/skills (keep user-owned)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        from odoo.addons.pns_ai_mcp.hooks import (
            uninstall_factory_knowledge_for_module,
        )
        uninstall_factory_knowledge_for_module(env, 'pns_ai_chatboo')
    except Exception:
        _logger.warning(
            'Chatboo: uninstall factory knowledge failed', exc_info=True,
        )
