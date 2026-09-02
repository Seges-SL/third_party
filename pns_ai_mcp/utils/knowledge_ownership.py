# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Visibility and create defaults for user-owned ai.context / ai.skill records."""


def ownership_read_domain(user):
    """ORM domain: module knowledge (no owner) + own user-owned rows."""
    uid = user.id if hasattr(user, 'id') else user
    return ['|', ('owner_id', '=', False), ('owner_id', '=', uid)]


def ownership_write_domain(user):
    """ORM domain: only private records owned by the user."""
    uid = user.id if hasattr(user, 'id') else user
    return [('owner_id', '=', uid)]


def filter_visible_records(records, user=None):
    """Runtime filter aligned with ownership_read_domain."""
    user = user or records.env.user
    uid = user.id
    return records.filtered(
        lambda r: not r.owner_id or r.owner_id.id == uid
    )


def apply_create_ownership(vals, env, *, module_markers=('source_module', 'is_system')):
    """Set owner_id on manual Writer creates (not module import)."""
    if vals.get('owner_id'):
        return vals
    if any(vals.get(k) for k in module_markers):
        return vals
    user = env.user
    if user._is_superuser():
        return vals
    if user.has_group('pns_ai_mcp.group_ai_writer'):
        vals = dict(vals)
        vals['owner_id'] = user.id
    return vals


def assert_writer_can_write_records(records, env):
    """Extra guard for module/system rows (record rules should already block).

    Escape hatches (consistent with the other guards in this module): the
    superuser and the ``skip_hardcoded_restrictions`` context (used by module
    seeding / ``i.sh --restore`` / the UI "restore from module" flow) bypass it,
    so file→DB upserts of shipped ``is_system`` skills/contexts are allowed.
    """
    if (env.context.get('skip_hardcoded_restrictions')
            or env.user._is_superuser()
            or env.user.has_group('pns_ai_mcp.group_ai_admin')):
        return
    forbidden = records.filtered(
        lambda r: (
            getattr(r, 'context_type', None) == 'core'
            or getattr(r, 'is_system', False)
            or not r.owner_id
        )
    )
    if forbidden:
        from odoo.exceptions import AccessError
        from odoo import _
        raise AccessError(_(
            'You can only edit your own user-created knowledge records.'
        ))
