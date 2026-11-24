# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Maximum-privilege roles (PAAP I7): an AI plan neither gives nor takes them.

Whoever holds one of the roots can change every access right in Odoo. A group
that implies a root carries it, so it is part of the cusp too. Nothing here
depends on who approves: an AI Administrator confirming the plan is still
refused.
"""
from __future__ import annotations

CUSP_ROOTS = ('base.group_system', 'base.group_erp_manager')

# Odoo writes the user's groups through these too (Odoo 14 form fields).
_REIFIED_GROUP_PREFIXES = ('in_group_', 'sel_groups_')


def _as_id(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


def ids_in(value):
    """Record ids a many2many value names: bare ids, or Odoo commands.

    ``(1|2|3|4, id, …)`` name one id, ``(6, 0, ids)`` a list, ``(0, 0, vals)``
    and ``(5,)`` none. The command code itself is never an id.
    """
    found = set()
    one = _as_id(value)
    if one is not None:
        found.add(one)
        return found
    if not isinstance(value, (list, tuple)):
        return found
    for item in value:
        one = _as_id(item)
        if one is not None:
            found.add(one)
            continue
        if not isinstance(item, (list, tuple)) or not item:
            continue
        code = _as_id(item[0])
        if code in (1, 2, 3, 4) and len(item) > 1:
            rid = _as_id(item[1])
            if rid is not None:
                found.add(rid)
        elif code == 6 and len(item) > 2:
            found |= ids_in(list(item[2] or []))
    return found


def writes_user_groups(model_fields, values):
    """Field names in *values* that change which groups a user has."""
    hit = []
    for name in values or {}:
        if str(name).startswith(_REIFIED_GROUP_PREFIXES):
            hit.append(name)
            continue
        field = model_fields.get(name)
        if field is not None and getattr(field, 'comodel_name', None) == 'res.groups':
            hit.append(name)
    return hit


def cusp_groups(env):
    """The root groups plus every group that implies one of them."""
    Groups = env['res.groups'].sudo()
    roots = Groups.browse()
    for xmlid in CUSP_ROOTS:
        group = env.ref(xmlid, raise_if_not_found=False)
        if group is not None and group._name == 'res.groups':
            roots |= group
    if not roots:
        return roots
    implied = 'all_implied_ids' if 'all_implied_ids' in Groups._fields else 'trans_implied_ids'
    cusp = roots
    for group in Groups.with_context(active_test=False).search([]):
        if group[implied] & roots:
            cusp |= group
    return cusp


def _targets(env, model, step):
    Model = env[model].sudo().with_context(active_test=False)
    if step.get('ids') is not None:
        return Model.browse(sorted(ids_in(step.get('ids'))))
    if step.get('id') is not None:
        return Model.browse(sorted(ids_in(step.get('id'))))
    if step.get('domain') is not None:
        return Model.search(step.get('domain'))
    return Model.browse()


# Seges: parche 12 (PNS-01/02, seguridad). Ver docs/pendiente/parches_pns_ai.md
SETTINGS_ADMIN_ONLY = 'Only a Settings administrator can add or remove user groups.'


# Seges: parche 12 (PNS-01/02, seguridad). Ver docs/pendiente/parches_pns_ai.md
def settings_admin_error(env):
    """Seges: a plan changes groups only for Settings administrators.

    Checks the user who runs the plan and, when a supervised operation runs
    it, who proposed and confirmed it (``execute_plan_now`` puts them in the
    context). Those keys can only add a refusal, never lift one.
    """
    ctx = env.context or {}
    users = env.user
    for key in ('ai_journal_user_id', 'ai_journal_confirmed_by_uid'):
        if ctx.get(key):
            users |= env['res.users'].sudo().browse(int(ctx[key]))
    for user in users:
        if not (user._is_superuser() or user.has_group('base.group_system')):
            return SETTINGS_ADMIN_ONLY
    return None


def crud_cusp_error(env, model, op, step, records=None):
    """LLM-facing reason a CRUD step touches the cusp, or ``None``."""
    if env is None or model not in ('res.users', 'res.groups'):
        return None
    values = step.get('overrides') if op == 'copy' else step.get('values')
    values = values if isinstance(values, dict) else {}
    if model == 'res.users':
        touched = writes_user_groups(env['res.users']._fields, values)
        if touched and op in ('create', 'write', 'copy'):
            return (
                "A user's groups are not changed through %s on res.users "
                "(%s). Use op=action with user.add_group / user.remove_group; "
                "maximum-privilege roles (Settings, Access Rights) stay out of "
                "reach of a plan." % (op, ', '.join(sorted(touched)))
            )
        return None
    cusp = cusp_groups(env)
    if not cusp:
        # Seges: parche 12 (PNS-01/02, seguridad). Ver docs/pendiente/parches_pns_ai.md
        return settings_admin_error(env)
    if op in ('write', 'unlink', 'copy'):
        targets = records if records is not None else _targets(env, model, step)
        hit = targets & cusp
        if hit:
            return (
                "%s is a maximum-privilege role; a plan cannot %s it. "
                "It is changed by hand in Settings → Users & Companies → Groups."
                % (', '.join(hit.mapped('display_name')), op)
            )
    group_fields = env['res.groups']._fields
    for name, value in values.items():
        field = group_fields.get(name)
        if field is None or getattr(field, 'comodel_name', None) != 'res.groups':
            continue
        if ids_in(value) & set(cusp.ids):
            return (
                "res.groups.%s would link a maximum-privilege role "
                "(Settings, Access Rights); a plan cannot do that." % name
            )
    # Seges: parche 12 (PNS-01/02, seguridad). Ver docs/pendiente/parches_pns_ai.md
    return settings_admin_error(env)
