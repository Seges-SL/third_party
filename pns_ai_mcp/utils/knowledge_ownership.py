# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Who may use a context or a skill, and create defaults for user-owned rows.

One rule for both models, in three places that must agree: the record rule
(``security.xml``, through the searchable ``shared_user_ids``), the ORM
domain (``ownership_read_domain``) and the Python filter
(``filter_visible_records`` / ``user_may_use``).

- The owner always may.
- With groups (``required_group_ids``): a member of one of them may.
- No owner and no groups: everyone with access to the agent may.

So an owner shares with a group by ticking it; an administrator opens a
row to everyone by clearing the owner and the groups.
"""
from .compat import USER_ALL_GROUPS_FIELD

GROUPS_FIELD = 'required_group_ids'
SHARED_USERS_FIELD = 'shared_user_ids'


def _uid(user):
    return user.id if hasattr(user, 'id') else user


def ownership_read_domain(user):
    """ORM domain of the rows ``user`` may use (same rule as the record rule)."""
    uid = _uid(user)
    return [
        '|', '|',
        ('owner_id', '=', uid),
        (SHARED_USERS_FIELD, 'in', [uid]),
        '&', ('owner_id', '=', False), (GROUPS_FIELD, '=', False),
    ]


def user_group_ids(user):
    """Ids of the user's groups, implied ones included."""
    return set(user[USER_ALL_GROUPS_FIELD].ids)


def user_may_use(record, user, group_ids=None):
    """True when ``user`` may see and use ``record`` (owner, member, or open row)."""
    owner = record.owner_id
    if owner and owner.id == user.id:
        return True
    groups = record[GROUPS_FIELD] if GROUPS_FIELD in record._fields else None
    if groups:
        mine = user_group_ids(user) if group_ids is None else group_ids
        return bool(set(groups.ids) & mine)
    return not owner


def filter_visible_records(records, user=None):
    """Runtime filter aligned with ownership_read_domain."""
    user = user or records.env.user
    mine = user_group_ids(user)
    return records.filtered(lambda r: user_may_use(r, user, group_ids=mine))


def search_shared_user_ids(model, operator, value):
    """``(shared_user_ids, in, [uid])`` → the rows whose groups the user has.

    Lets the record rule say ``[('shared_user_ids', 'in', [user.id])]`` and
    keep the version-specific name of the user's groups field in Python.
    """
    if operator not in ('in', '=') or not value:
        return [('id', '=', False)]
    # Odoo 19 hands the ``in`` value as an OrderedSet, older versions as a
    # list; a bare id also arrives with ``=``. psycopg adapts none of the
    # set types, so everything becomes a plain list of ints first.
    if isinstance(value, (str, bytes, int)):
        value = [value]
    ids = [int(v) for v in value if v]
    users = model.env['res.users'].sudo().browse(ids).exists()
    group_ids = set()
    for user in users:
        group_ids |= user_group_ids(user)
    if not group_ids:
        return [('id', '=', False)]
    return [(GROUPS_FIELD, 'in', list(group_ids))]


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


def factory_lock_open(env):
    """True when factory rows may be rewritten by this environment.

    ``call_kw`` copies the client context, so ``skip_hardcoded_restrictions``
    alone is not a grant. It counts only inside ``sudo()``. The superuser
    (install, ``-u``, shell) is not a browser session.
    """
    if env.user._is_superuser():
        return True
    return bool(
        env.su and env.context.get('skip_hardcoded_restrictions')
    )


def assert_writer_can_write_records(records, env):
    """Extra guard for module/system rows (record rules should already block).

    Superuser, ``sudo()`` plus the seed flag, and AI Administrator bypass it,
    so file→DB upserts of shipped skills/contexts are allowed.
    """
    if factory_lock_open(env) or env.user.has_group('pns_ai_mcp.group_ai_admin'):
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
