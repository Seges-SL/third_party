# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Deterministic slash help cards (no LLM, no business literals)."""
from __future__ import annotations

import json

ARGS_POLICIES = ('default', 'ask', 'none')


def _label(text):
    """English msgid; wrap with Odoo ``_`` when the registry is present."""
    try:
        from odoo import _
        return _(text)
    except ImportError:
        return text


def normalize_args_policy(value, *, has_params=False):
    """Return default|ask|none. Unknown/empty → default (empty runs)."""
    raw = (value or '').strip().lower()
    if raw in ARGS_POLICIES:
        return raw
    return 'default'


def _schema_rows(schema_txt):
    raw = (schema_txt or '').strip()
    if not raw:
        return []
    try:
        schema = json.loads(raw)
    except Exception:
        return []
    if not isinstance(schema, dict):
        return []
    rows = []
    for key, spec in schema.items():
        spec = spec if isinstance(spec, dict) else {}
        default = spec.get('default')
        if default is None:
            default = ''
        rows.append({
            'name': str(key),
            'type': str(spec.get('type') or 'string'),
            'desc': str(
                spec.get('desc') or spec.get('description') or ''
            ),
            'default': default if default == '' else str(default),
        })
    return rows


def _owner_line(meta):
    kind = (meta.get('owner_kind') or '').strip().lower()
    name = (meta.get('owner_name') or '').strip()
    if kind == 'user' and name:
        return name
    return _label('Common')


def _policy_line(policy):
    if policy == 'default':
        return _label(
            'Empty arguments run with the built-in default. '
            'Help is deterministic (no AI).'
        )
    if policy == 'ask':
        return _label(
            'This command asks for arguments when none are given. '
            'Help is deterministic (no AI).'
        )
    return _label(
        'This command takes no arguments. Help is deterministic (no AI).'
    )


def build_slash_help_markdown(meta, *, rejected=False, reject_reason='',
                              asking=False):
    """Markdown card for ``/code ?``, an empty ``ask``, or a rejected argument.

    ``meta``: code, name, description, arg_hint, param_schema, args_policy,
    owner_kind (``user``|``common``), owner_name.
    """
    meta = meta or {}
    code = (meta.get('code') or meta.get('command') or '').strip() or 'skill'
    name = (meta.get('name') or code).strip()
    desc = (meta.get('description') or '').strip()
    hint = (meta.get('arg_hint') or '').strip()
    policy = normalize_args_policy(meta.get('args_policy'))
    rows = _schema_rows(meta.get('param_schema'))

    lines = ['# /%s' % code, '', '**%s**' % name, '']
    if rejected:
        reason = (reject_reason or '').strip() or _label(
            'Those arguments do not match this command.'
        )
        lines.extend(['**%s**' % reason, ''])
    elif asking:
        lines.extend([
            _label('This command needs arguments before it can run.'),
            '',
        ])
    if desc:
        lines.extend([desc, ''])
    lines.extend([
        '**%s:** %s' % (_label('Owner'), _owner_line(meta)),
        '',
        '**%s:**' % _label('Parameters'),
        '',
    ])
    if rows:
        lines.append(
            '| %s | %s | %s | %s |' % (
                _label('Name'), _label('Type'),
                _label('Description'), _label('Default'),
            )
        )
        lines.append('| --- | --- | --- | --- |')
        for row in rows:
            lines.append(
                '| `%s` | %s | %s | %s |' % (
                    row['name'], row['type'],
                    row['desc'] or '—', row['default'] or '—',
                )
            )
        lines.append('')
    else:
        lines.append(_label('No formal parameters.'))
        lines.append('')
    if hint:
        lines.extend(['`/%s %s`' % (code, hint), ''])
    lines.append(_policy_line(policy))
    return '\n'.join(lines).rstrip() + '\n'


def build_slash_help_html(meta, *, rejected=False, reject_reason='',
                          asking=False):
    """Back-compat alias: help SoT is markdown."""
    return build_slash_help_markdown(
        meta, rejected=rejected, reject_reason=reject_reason, asking=asking,
    )


def skill_help_meta(skill):
    """Serialize an ``ai.skill`` record for the help card."""
    invoke = ''
    try:
        invoke = skill.invoke_code() or skill.code or ''
    except Exception:
        invoke = getattr(skill, 'code', '') or ''
    owner = getattr(skill, 'owner_id', None)
    owner_name = ''
    if owner:
        owner_name = (
            getattr(owner, 'name', None)
            or getattr(owner, 'display_name', None)
            or ''
        )
        if not owner_name and getattr(owner, 'id', None):
            owner_name = str(owner)
    return {
        'code': invoke,
        'name': getattr(skill, 'name', '') or invoke,
        'description': getattr(skill, 'description', '') or '',
        'arg_hint': getattr(skill, 'arg_hint', '') or '',
        'param_schema': getattr(skill, 'param_schema', '') or '',
        'args_policy': normalize_args_policy(
            getattr(skill, 'args_policy', None),
        ),
        'owner_kind': 'user' if owner_name else 'common',
        'owner_name': owner_name,
    }


# Builtins / presentation axes — description lives to the right of /code.
# No business literals: only command UX.
BUILTIN_SLASH_META = {
    'skills': {
        'code': 'skills',
        'name': 'Skills',
        'description': 'List the available skills in the slash menu.',
        'args_policy': 'none',
        'owner_kind': 'common',
    },
    'mode': {
        'code': 'mode',
        'name': 'Mode',
        'description': 'List presentation modes (painter, footer, table/chart).',
        'args_policy': 'none',
        'owner_kind': 'common',
    },
    'create-skill': {
        'code': 'create-skill',
        'name': 'Create skill',
        'description': (
            'Capture a turn as an instance skill (extra, with you as author). '
            'Typing /create-skill fills the last chip (you can change it), '
            'then the slash name. Settings prefixes apply to the slash and '
            'the catalog code. Other users do not see it unless an admin '
            'publishes it. Help is /create-skill ?'
        ),
        'arg_hint': 'VWVN slash-name  |  ? help',
        'param_schema': (
            '{"turn_id":{"type":"string","desc":"4-character MCP turn id '
            '(chip). Required.","default":"last turn"},'
            '"name":{"type":"string","desc":"Slash name (kebab). Instance '
            'prefix from Settings is applied. Required."}}'
        ),
        'args_policy': 'ask',
        'owner_kind': 'common',
    },
    'delete-skill': {
        'code': 'delete-skill',
        'name': 'Delete skill',
        'description': (
            'Delete a skill you created. Empty opens the picker. '
            'The stem or the prefixed slash both resolve. Help is /delete-skill ?'
        ),
        'arg_hint': 'slash-name  |  ? help',
        'param_schema': (
            '{"name":{"type":"string","desc":"Slash of a skill you created. '
            'Stem or prefixed.","default":"opens picker"}}'
        ),
        'args_policy': 'ask',
        'owner_kind': 'common',
    },
    'rename-skill': {
        'code': 'rename-skill',
        'name': 'Rename skill',
        'description': (
            'Rename a skill you created. Empty opens the picker. '
            'The new slash gets the instance prefix. Help is /rename-skill ?'
        ),
        'arg_hint': 'old-name new-name  |  ? help',
        'param_schema': (
            '{"old":{"type":"string","desc":"Current slash (stem or prefixed)."},'
            '"new":{"type":"string","desc":"New slash name. Instance prefix '
            'is applied."}}'
        ),
        'args_policy': 'ask',
        'owner_kind': 'common',
    },
    'painter-local': {
        'code': 'painter-local',
        'name': 'Painter local',
        'description': 'Chatboo composes tables and charts for this turn.',
        'args_policy': 'none',
        'arg_hint': 'optional question…',
        'owner_kind': 'common',
    },
    'painter-free': {
        'code': 'painter-free',
        'name': 'Painter free',
        'description': 'The model owns the whole bubble for this turn.',
        'args_policy': 'none',
        'arg_hint': 'optional question…',
        'owner_kind': 'common',
    },
    'foot-laconic': {
        'code': 'foot-laconic',
        'name': 'Foot laconic',
        'description': 'No footer after local tables (this turn).',
        'args_policy': 'none',
        'arg_hint': 'optional question…',
        'owner_kind': 'common',
    },
    'foot-verbose': {
        'code': 'foot-verbose',
        'name': 'Foot verbose',
        'description': 'Warm footer after local tables (this turn).',
        'args_policy': 'none',
        'arg_hint': 'optional question…',
        'owner_kind': 'common',
    },
    'show-table': {
        'code': 'show-table',
        'name': 'Show table',
        'description': 'Table first for this session (painter-local).',
        'args_policy': 'none',
        'arg_hint': 'optional question…',
        'owner_kind': 'common',
    },
    'show-chart': {
        'code': 'show-chart',
        'name': 'Show chart',
        'description': 'Chart first for this session (painter-local).',
        'args_policy': 'none',
        'arg_hint': 'optional question…',
        'owner_kind': 'common',
    },
}


def builtin_slash_help_meta(code):
    """Return help meta for a builtin / axis slash, or None."""
    key = (code or '').strip().lower().replace('_', '-')
    if key in ('skill', 'help', 'ayuda', '?'):
        key = 'skills'
    meta = BUILTIN_SLASH_META.get(key)
    return dict(meta) if meta else None
