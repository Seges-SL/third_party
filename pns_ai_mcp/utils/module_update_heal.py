# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Helpers for ``module.update`` after ``button_immediate_*`` resets the registry.

No Odoo import. ``button_immediate_install/upgrade/uninstall`` commits and
reloads the registry; the Safe Plan cursor then looks dead even when the
module operation already succeeded. Heal by reading the live module state.
"""
from __future__ import annotations

import json

MODULE_UPDATE_CODE = 'module.update'
DESIRED_MODULE_STATE = {
    'install': 'installed',
    'upgrade': 'installed',
    'uninstall': 'uninstalled',
}
BUTTON_TO_OPERATION = {
    'button_immediate_install': 'install',
    'button_install': 'install',
    'install': 'install',
    'button_immediate_upgrade': 'upgrade',
    'button_upgrade': 'upgrade',
    'upgrade': 'upgrade',
    'button_immediate_uninstall': 'uninstall',
    'button_uninstall': 'uninstall',
    'uninstall': 'uninstall',
}


def steps_fingerprint(steps):
    """Stable JSON of a Safe Plan step list (key order independent)."""
    return json.dumps(steps or [], sort_keys=True, ensure_ascii=False, default=str)


def operation_from_args(args):
    """Closed ``install``/``upgrade``/``uninstall``, including LLM button aliases."""
    args = args or {}
    op = (args.get('operation') or args.get('op') or '')
    if isinstance(op, str):
        op = op.strip().lower()
        if op in DESIRED_MODULE_STATE:
            return op
    button = args.get('button') or args.get('method') or ''
    key = str(button).strip()
    return BUTTON_TO_OPERATION.get(key) or BUTTON_TO_OPERATION.get(key.lower())


def module_name_from_args(args):
    args = args or {}
    for key in ('module', 'name', 'technical_name'):
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def module_ids_from_args(args):
    args = args or {}
    if args.get('module_id') is not None:
        try:
            return [int(args.get('module_id'))]
        except (TypeError, ValueError):
            return []
    ids = args.get('module_ids') or args.get('ids')
    if isinstance(ids, bool):
        return []
    if isinstance(ids, int):
        return [ids]
    if isinstance(ids, (list, tuple)):
        out = []
        for item in ids:
            try:
                out.append(int(item))
            except (TypeError, ValueError):
                continue
        return out
    return []


def module_update_args_from_steps(steps):
    """First ``module.update`` payload: ``(name, operation, module_ids)``."""
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        if step.get('op') != 'action':
            continue
        if step.get('action_code') != MODULE_UPDATE_CODE:
            continue
        args = step.get('args') or {}
        return (
            module_name_from_args(args),
            operation_from_args(args),
            module_ids_from_args(args),
        )
    return None, None, []


def module_update_from_steps(steps):
    """First ``module.update`` ``(technical_name, operation)``; ids resolved later."""
    name, op, _ids = module_update_args_from_steps(steps)
    if name and op:
        return name, op
    if op or name or _ids:
        return name, op
    return None, None


def plan_has_module_update(steps):
    for step in steps or []:
        if isinstance(step, dict) and step.get('action_code') == MODULE_UPDATE_CODE:
            return True
    return False


def module_state_matches(operation, state, loaded=None):
    """True when the live module has reached the requested operation.

    ``install`` / ``upgrade`` require ``state == 'installed'``. If *loaded* is
    given (module currently in the Odoo registry), it must also be True —
    otherwise Apps still shows Install (ghost ``installed`` row / stale cache).
    """
    op = (operation or '').strip().lower()
    desired = DESIRED_MODULE_STATE.get(op)
    if not desired or state != desired:
        return False
    if op in ('install', 'upgrade') and loaded is not None:
        return bool(loaded)
    return True


def should_skip_module_op(operation, state, loaded=None):
    """Skip only when the requested operation is already in effect."""
    op = (operation or '').strip().lower()
    if op == 'install':
        return state == 'installed' and loaded is True
    if op == 'uninstall':
        return state == 'uninstalled'
    return False
