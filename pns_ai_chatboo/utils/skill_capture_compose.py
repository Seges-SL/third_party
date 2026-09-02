# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Compose a slash skill from a Chatboo turn: fetch plan + painter.

A ReAct turn often logs ``propose_safe_operations`` (api_call / fetch_url)
and a later relaxaicode that only paints ``previous_result``. Capturing the
painter alone yields an empty card on ``/slash``. These helpers are nameless:
they wrap whatever presentation code the turn left with the turn's own
auto-confirmable steps. Writes are never inlined.
"""
from __future__ import annotations

import json

_PRIOR_PLAN_MARKERS = (
    'previous_result',
    'get_safe_plan_steps',
    'parse_safe_plan_step_body',
)
_FETCH_OPS = frozenset(('api_call', 'fetch_url', 'mcp_call'))
_STEP_KEYS = ('op', 'server', 'tool', 'arguments', 'url', 'method')


def code_needs_prior_plan(code):
    """True when the snippet paints a prior safe-plan and does not fetch."""
    body = code or ''
    if not body.strip():
        return False
    if 'propose_steps' in body:
        return False
    return any(marker in body for marker in _PRIOR_PLAN_MARKERS)


def plan_steps_from_operation_data(raw):
    """``ai.safe.operation.operation_data`` → list of step dicts."""
    if not raw:
        return []
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return []
    if not isinstance(data, dict):
        return []
    steps = data.get('plan_steps') or data.get('steps')
    if not isinstance(steps, list):
        nested = (
            data.get('arguments')
            or data.get('operation_data')
            or data.get('result')
        )
        if nested and nested is not data:
            return plan_steps_from_operation_data(nested)
        return []
    return [step for step in steps if isinstance(step, dict)]


def sanitize_fetch_steps(steps):
    """Keep auto-confirmable fetch verbs only. Any other op → empty (no wrap)."""
    out = []
    for step in steps or []:
        if not isinstance(step, dict):
            return []
        op = step.get('op')
        if op not in _FETCH_OPS:
            return []
        kept = {
            key: step[key]
            for key in _STEP_KEYS
            if key in step and step[key] not in (None, '')
        }
        if 'op' not in kept:
            return []
        out.append(kept)
    return out


def wrap_presentation_with_turn_fetch(present_code, steps):
    """If ``present_code`` needs a prior plan, prepend the turn fetch round."""
    body = (present_code or '').strip()
    clean = sanitize_fetch_steps(steps)
    if not body or not clean or not code_needs_prior_plan(body):
        return present_code or ''
    steps_lit = json.dumps(clean, ensure_ascii=False, indent=4)
    prefixed = '\n'.join(
        ('    ' + line) if line.strip() else line
        for line in body.splitlines()
    )
    return (
        '# Fetch round from the source turn (empty previous_result on /slash).\n'
        '_TURN_FETCH_STEPS = %s\n'
        'try:\n'
        '    _turn_prev = previous_result\n'
        'except NameError:\n'
        '    _turn_prev = None\n'
        '_turn_have = False\n'
        'if _turn_prev:\n'
        '    try:\n'
        '        _turn_have = bool(get_safe_plan_steps(_turn_prev))\n'
        '    except NameError:\n'
        '        _turn_have = False\n'
        'if not _turn_have:\n'
        '    result = {\'propose_steps\': _TURN_FETCH_STEPS, \'continue\': True}\n'
        'else:\n'
        '%s\n'
    ) % (steps_lit, prefixed)
