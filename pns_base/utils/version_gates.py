# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Load-time version gates for pns_base converters.

No Odoo import: unit tests load this file as-is. Thresholds:

- 17+: attrs → invisible/readonly/required expressions
- 18+: <tree> → <list>, view_mode tree→list
- 19+: res.groups category_id → privilege_id
"""

ATTRS_CONVERT_FROM = 17
TREE_TO_LIST_FROM = 18
GROUP_PRIVILEGE_FROM = 19


def applies_attrs_convert(odoo_version):
    """True when attrs= must become modifier expressions."""
    return odoo_version >= ATTRS_CONVERT_FROM


def applies_tree_to_list(odoo_version):
    """True when list views use <list> / view_mode 'list' (Odoo 18+)."""
    return odoo_version >= TREE_TO_LIST_FROM


def applies_group_privilege(odoo_version):
    """True when res.groups uses privilege_id (Odoo 19+)."""
    return odoo_version >= GROUP_PRIVILEGE_FROM


def apply_group_users_alias(vals, fields):
    """Rename users ↔ user_ids so vals match ``fields``. Mutates vals."""
    if not isinstance(vals, dict) or not vals or not fields:
        return
    if 'users' in vals and 'users' not in fields and 'user_ids' in fields:
        vals['user_ids'] = vals.pop('users')
    elif 'user_ids' in vals and 'user_ids' not in fields and 'users' in fields:
        vals['users'] = vals.pop('user_ids')


def rewrite_group_vals(vals, odoo_version, fields, privilege_id=None):
    """Rewrite res.groups vals for this major. Mutates vals.

    On 19+, ``category_id`` is removed and ``privilege_id`` is set when given.
    ``users`` / ``user_ids`` are aliased to the fields the model actually has.
    On 17/18 the dict is left with ``category_id`` (native).
    """
    if not isinstance(vals, dict) or not vals:
        return
    apply_group_users_alias(vals, fields)
    if applies_group_privilege(odoo_version) and 'category_id' in vals:
        if privilege_id is not None:
            vals['privilege_id'] = privilege_id
        vals.pop('category_id', None)
