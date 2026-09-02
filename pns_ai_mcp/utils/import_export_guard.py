# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Central guard: only AI Administrators may import/export configuration artifacts."""


def ensure_ai_admin(env):
    """Raise AccessError unless the user is AI admin (or superuser / module bootstrap)."""
    if env.context.get('skip_hardcoded_restrictions'):
        return
    if env.user._is_superuser() or env.user.has_group('pns_ai_mcp.group_ai_admin'):
        return
    from odoo.exceptions import AccessError
    from odoo import _
    raise AccessError(_(
        'Only AI Administrators can import or export AI configuration artifacts.'
    ))
