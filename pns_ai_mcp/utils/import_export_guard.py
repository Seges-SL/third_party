# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Central guard: only AI Administrators may import/export configuration artifacts."""


def ensure_ai_admin(env):
    """Raise AccessError unless the user is AI admin (or superuser / module bootstrap).

    A context flag from RPC is not enough. ``sudo()`` plus the seed flag, or
    the superuser, still passes: module install and ``-u`` use those.
    """
    from .knowledge_ownership import factory_lock_open
    if factory_lock_open(env):
        return
    if env.user.has_group('pns_ai_mcp.group_ai_admin'):
        return
    from odoo.exceptions import AccessError
    from odoo import _
    raise AccessError(_(
        'Only AI Administrators can import or export AI configuration artifacts.'
    ))
