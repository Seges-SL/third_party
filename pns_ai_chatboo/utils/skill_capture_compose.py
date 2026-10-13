# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Compose a slash skill from a Chatboo turn: fetch plan + presentation.

A ReAct turn often logs ``safe_plan_request`` (api_call / fetch_url)
and a later relaxaicode that only paints ``previous_result``. Capturing the
presentation alone yields an empty card on ``/slash``. These helpers are nameless:
they wrap whatever presentation code the turn left with the turn's own
auto-confirmable steps. Writes are never inlined.
"""
from __future__ import annotations

import json
import re

_PRESENTABLE_TOKENS = (
    '__return_direct__',
    'formatted_text',
    'propose_steps',
)

_PRIOR_PLAN_MARKERS = (
    'previous_result',
    'get_safe_plan_steps',
    'parse_safe_plan_step_body',
)
_FETCH_OPS = frozenset(('api_call', 'fetch_url', 'mcp_call'))
_STEP_KEYS = ('op', 'server', 'tool', 'arguments', 'url', 'method')
# Engine tools that mean "this turn already ran a catalog skill" (no
# relaxaicode snippet). Structural names, not a slash lexicon.
CATALOG_SKILL_TURN_TOOLS = frozenset((
    'skill_fast_path',
    'skill_fast_path_error',
    'skill_report_direct',
    'skill_report_handoff',
    'skill_help_direct',
    'skill_args_ask',
    'skill_args_reject',
))


def is_catalog_skill_turn_tool(tool_name):
    """True when ``tool_name`` is a catalog-skill execution log."""
    return (tool_name or '').strip() in CATALOG_SKILL_TURN_TOOLS


def slash_from_skill_turn_prompt(prompt_data):
    """Catalog slash stored on a skill-turn ``prompt_data``, or ``''``.

    Accepts the JSON object or the serialized text ``ai.log`` keeps.
    """
    data = prompt_data
    if isinstance(data, str):
        raw = data.strip()
        if not raw:
            return ''
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return ''
    if not isinstance(data, dict):
        return ''
    slash = (data.get('skill') or '').strip()
    if slash.startswith('/'):
        slash = slash[1:].strip()
    return slash


def slash_from_skill_turn_logs(rows):
    """First catalog slash from turn logs ``(tool_name, prompt_data)``."""
    for tool_name, prompt_data in rows or ():
        if not is_catalog_skill_turn_tool(tool_name):
            continue
        slash = slash_from_skill_turn_prompt(prompt_data)
        if slash:
            return slash
    return ''


def last_result_literal(code):
    """Right-hand side of the last ``result = …`` line, or ``''``."""
    assigns = re.findall(r'^\s*result\s*=\s*(.+)$', code or '', flags=re.M)
    return assigns[-1].strip() if assigns else ''


def snippet_is_empty_result(code):
    """True when the snippet's last ``result`` is an empty dict."""
    return last_result_literal(code) in ('{}', '{ }')


def snippet_has_presentable_contract(code):
    """True when the snippet can paint or fetch on its own."""
    body = code or ''
    return any(tok in body for tok in _PRESENTABLE_TOKENS)


def snippet_is_probe_code(code):
    """True for diagnostic relaxaicode snippets, not capturable logic."""
    body = (code or '').strip()
    if not body:
        return True
    if '__phase__' in body:
        return True
    if (
        'md_len' in body
        and 'md_head' in body
        and 'data' not in body
        and '__show_table__' not in body
    ):
        return True
    if snippet_is_empty_result(body) and code_needs_prior_plan(body):
        return not snippet_has_presentable_contract(body)
    return False


def snippet_is_formatter_only(code):
    """True when the snippet only reformats rows already in ``previous_result``."""
    body = code or ''
    if not body.strip() or 'propose_steps' in body:
        return False
    if not any(marker in body for marker in _PRIOR_PLAN_MARKERS):
        return False
    if re.search(r"previous_result\.get\(['\"]rows['\"]", body):
        return True
    if re.search(r"previous_result\.get\(['\"]data['\"]", body):
        return True
    if (
        snippet_has_presentable_contract(body)
        and 'get_safe_plan_steps' not in body
        and 'parse_safe_plan_step_body' not in body
    ):
        return True
    return False


def score_capture_snippet(code, relaxaicode_count=1):
    """Rank a turn snippet for capture. Higher wins.

    A first-round ``result = {}`` that only names ``previous_result`` must
    lose to a later snippet that already returns ``data`` / HTML / a fetch.
    Mentioning ``previous_result`` is not a plus by itself.
    """
    body = (code or '').strip()
    if not body:
        return -999
    score = 0
    if snippet_is_probe_code(body):
        score -= 200
    if snippet_is_empty_result(body):
        score -= 80
    if snippet_has_presentable_contract(body):
        score += 50
    if 'propose_steps' in body:
        score += 20
    elif (
        snippet_has_presentable_contract(body)
        and any(tok in body for tok in _PRIOR_PLAN_MARKERS)
    ):
        if relaxaicode_count > 1:
            score -= 40
        else:
            score += 30
    if relaxaicode_count > 1 and snippet_is_formatter_only(body):
        score -= 120
    if snippet_has_presentable_contract(body) and 'previous_result' not in body:
        score += 25
    score += min(len(body) // 120, 25)
    return score


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


def merge_fetch_steps(step_lists):
    """Merge fetch steps from several safe plans, deduplicated, order preserved."""
    seen = set()
    out = []
    for steps in step_lists or ():
        clean = sanitize_fetch_steps(steps)
        if not clean and steps:
            return []
        for step in clean:
            key = json.dumps(step, sort_keys=True, default=str)
            if key in seen:
                continue
            seen.add(key)
            out.append(step)
    return out


def _indent_code_block(code):
    return '\n'.join(
        ('    ' + line) if line.strip() else line
        for line in (code or '').splitlines()
    )


def _merge_transform_and_present(transform_codes, present_code):
    """Inline transform relaxaicode phases before the presentation snippet."""
    inner_parts = ['_pipeline_rows = []']
    for tcode in transform_codes or ():
        body = (tcode or '').strip()
        if not body:
            continue
        inner_parts.append('result = {}')
        inner_parts.extend((tcode or '').splitlines())
        inner_parts.append('_pipeline_rows = []')
        inner_parts.append('if isinstance(result, dict):')
        inner_parts.append(
            "    _pipeline_rows = result.get('rows') or result.get('data') or []"
        )
    inner_parts.append(
        "previous_result = {'rows': _pipeline_rows, 'data': _pipeline_rows}"
    )
    inner_parts.append('result = {}')
    inner_parts.extend((present_code or '').splitlines())
    return '\n'.join(inner_parts)


def compose_capture_pipeline(relaxaicode_codes, fetch_steps):
    """Build one capturable ``code_body`` from turn relaxaicode + fetch steps.

    Returns ``(code, incomplete)`` where ``incomplete`` is True when the turn
    still depends on data the composer could not recover (no fetch steps).
    """
    codes = [
        (code or '').strip()
        for code in (relaxaicode_codes or ())
        if (code or '').strip() and not snippet_is_probe_code(code)
    ]
    if not codes:
        return '', True

    clean_fetch = sanitize_fetch_steps(fetch_steps or [])

    if len(codes) == 1:
        body = codes[0]
        if clean_fetch and code_needs_prior_plan(body):
            return wrap_presentation_with_turn_fetch(body, clean_fetch), False
        incomplete = code_needs_prior_plan(body) and not clean_fetch
        return body, incomplete

    transforms = codes[:-1]
    present = codes[-1]
    merged_inner = _merge_transform_and_present(transforms, present)
    prefixed = _indent_code_block(merged_inner)

    if clean_fetch:
        steps_lit = json.dumps(clean_fetch, ensure_ascii=False, indent=4)
        return (
            '# Composed from a multi-phase source turn.\n'
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
            "    result = {'propose_steps': _TURN_FETCH_STEPS, 'continue': True}\n"
            'else:\n'
            '%s\n'
        ) % (steps_lit, prefixed), False

    incomplete = (
        not any('propose_steps' in code for code in codes)
        and code_needs_prior_plan(present)
    )
    return merged_inner, incomplete


def capture_is_incomplete(code, fetch_steps):
    """True when slash would likely need data the capture did not embed."""
    body = (code or '').strip()
    if not body:
        return True
    if '_TURN_FETCH_STEPS' in body or 'propose_steps' in body:
        return False
    if code_needs_prior_plan(body) and not sanitize_fetch_steps(fetch_steps or []):
        return True
    return snippet_is_formatter_only(body) and not sanitize_fetch_steps(fetch_steps or [])


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
