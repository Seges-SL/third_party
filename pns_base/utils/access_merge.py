# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Old access rows (ir.model.access + ir.rule) as Odoo 20 ir.access rows.

No Odoo import: unit tests load this file as-is.

Before Odoo 20, a user may do an operation when one of their groups has
an ir.model.access row for it. Then every global rule cuts the records,
and the group rules that touch the user are OR-ed together and cut them
too. When no group rule touches the user, the group rules cut nothing.

On Odoo 20, ir.access rows with a group grant (OR-ed together), and rows
without a group cut (all of them apply). So, for one model and one
operation:

- A global rule becomes a row without a group, with its domain.
- Without group rules, each access row becomes a row for its group.
- With group rules, each rule group that has access becomes a row with
  the rule domain. An access group is covered when all its users are in
  some rule group (it implies one). An access group that is not covered,
  or a rule group without access, cannot be said on Odoo 20 without
  giving more than before: it is left out and named in the warnings.
- A group rule on an operation no access row grants is left out and
  named too: where Odoo's own ir.access grants it, it no longer cuts.
"""

OPS = (('create', 'c'), ('read', 'r'), ('write', 'u'), ('unlink', 'd'))


def operation_code(ops):
    """'crud' letters, in that order, for a set of operation names."""
    return ''.join(letter for op, letter in OPS if op in ops)


def merge_model_access(acls, rules, implied):
    """ir.access rows for one model.

    ``acls``: dicts with ``name``, ``group`` (id) and ``ops`` (set of
    create/read/write/unlink). The caller turns a row without a group into
    the group every user has.
    ``rules``: dicts with ``name``, ``groups`` (ids, empty = global),
    ``domain`` (text, empty = all) and ``ops``.
    ``implied``: group id → ids of the groups it implies, itself included.

    Returns ``(rows, warnings)``. Each row has ``name``, ``group`` (id or
    None), ``operation`` ('crud' letters) and ``domain``.
    """
    rows = {}

    def add(group, domain, op, name):
        row = rows.setdefault((group, domain or ''), [name, set()])
        row[1].add(op)

    warnings = []
    for rule in rules:
        if not rule['groups']:
            for op in rule['ops']:
                add(None, rule['domain'], op, rule['name'])

    for op, _letter in OPS:
        acl_groups = {}
        for acl in acls:
            if op in acl['ops']:
                acl_groups.setdefault(acl['group'], acl['name'])
        group_rules = [rule for rule in rules if rule['groups'] and op in rule['ops']]
        if not acl_groups:
            for rule in group_rules:
                warnings.append(
                    '%s: groups %s have a %s rule but no access row grants %s; '
                    'left out (where Odoo grants it, the rule no longer cuts)'
                    % (rule['name'], sorted(rule['groups']), op, op))
            continue
        if not group_rules:
            for group, name in acl_groups.items():
                add(group, '', op, name)
            continue
        rule_groups = {group for rule in group_rules for group in rule['groups']}
        for group, name in acl_groups.items():
            if not rule_groups & implied.get(group, {group}):
                warnings.append(
                    '%s: group %s has %s access but no group rule covers all '
                    'its users; left out' % (name, group, op))
        for rule in group_rules:
            for group in rule['groups']:
                if acl_groups.keys() & implied.get(group, {group}):
                    add(group, rule['domain'], op, rule['name'])
                else:
                    warnings.append(
                        '%s: group %s has a %s rule but no access row for '
                        'all its users; left out' % (rule['name'], group, op))

    result = [
        {'name': name, 'group': group, 'operation': operation_code(ops), 'domain': domain}
        for (group, domain), (name, ops) in rows.items()
    ]
    return result, warnings
