# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Primary artifact lock — first complete user-facing result of a turn.

Invariant (no domain): the first *complete* artifact delivered in a turn is
the principal document. Later tool results may upgrade it in place or append
as a minor. They must never replace or hide it.

See ``docs/decisions/primary_artifact.md``.
"""
from __future__ import annotations

import copy
import re

PIN = 'pin'
UPGRADE = 'upgrade'
MINOR = 'minor'
PROBE = 'probe'

# Presentation-contract keys (same family as turn_presentation_basket._BLOCK_KEYS).
# Not a domain list: surfaces the renderer / banner already understand.
PRESENTATION_KEYS = (
    'data', 'groups', 'sections', 'tables', 'formatted_text',
    'map_url', 'map_pins', 'pins_url', 'summary', 'title', 'name',
    'geo_coords', 'geo_thumbs', 'notices', 'show_mode',
    '__model', '__subtle_zebra__', '__no_charts__', '__row_links__',
)

_TAG_RE = re.compile(r'<[^>]+>')


def _code_references_reuse(code):
    """True if AST uses previous_result / raw_data as a Name."""
    if not code or not isinstance(code, str):
        return False
    try:
        from .response_anti_echo import code_references_reuse_names
        return bool(code_references_reuse_names(code))
    except ImportError:
        pass
    try:
        import ast
        tree = ast.parse(code)
    except (SyntaxError, ValueError, TypeError):
        return False
    wanted = {'previous_result', 'raw_data'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in wanted:
            return True
    return False


def _nonempty_rows(payload):
    if not isinstance(payload, dict):
        return False
    for key in ('data', 'items', 'rows'):
        val = payload.get(key)
        if isinstance(val, list) and val:
            return True
    for env in ('groups', 'sections', 'tables'):
        blocks = payload.get(env)
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if isinstance(block, dict) and _nonempty_rows(block):
                return True
    return False


def _has_map_surface(payload):
    if not isinstance(payload, dict):
        return False
    for key in ('map_url', 'pins_url'):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return True
    pins = payload.get('map_pins')
    if isinstance(pins, str) and pins.strip():
        return True
    if isinstance(pins, dict) and (
        pins.get('href') or pins.get('png_b64') or pins.get('url')
    ):
        return True
    return False


def _has_chart_surface(payload):
    if not isinstance(payload, dict):
        return False
    if payload.get('charts') is False:
        return False
    if payload.get('chart'):
        return True
    charts = payload.get('charts')
    if charts:
        return True
    mode = payload.get('show_mode') or ''
    return isinstance(mode, str) and 'chart' in mode


def _has_useful_html(payload):
    html = payload.get('formatted_text') if isinstance(payload, dict) else None
    if not html or not isinstance(html, str):
        return False
    text = _TAG_RE.sub('', html).strip()
    return len(text) >= 20


def is_hollow(payload):
    """True when there is no user-facing surface (rows, map, chart, HTML)."""
    if not isinstance(payload, dict):
        return True
    if _nonempty_rows(payload):
        return False
    if _has_map_surface(payload):
        return False
    if _has_chart_surface(payload):
        return False
    if _has_useful_html(payload):
        return False
    return True


def is_complete_artifact(payload):
    """True for a non-hollow payload that opted into user-facing delivery."""
    if not isinstance(payload, dict):
        return False
    if payload.get('error') or payload.get('__force_retry__'):
        return False
    if is_hollow(payload):
        return False
    if (
        payload.get('__satisfied__')
        or payload.get('__presentation_complete__')
        or payload.get('__phase__') == 'presentation'
    ):
        return True
    if (
        payload.get('__direct_return__')
        or payload.get('__return_direct__')
        or payload.get('__return_direct_to_user__')
    ):
        return True
    if (
        payload.get('__extraction_complete__')
        and payload.get('__ready_for_presentation__')
        and payload.get('summary')
    ):
        return True
    return False


def _shares_envelope(primary, payload):
    """Same document: identical title (restyle without renaming)."""
    if not isinstance(primary, dict) or not isinstance(payload, dict):
        return False
    pt = primary.get('title')
    nt = payload.get('title')
    return bool(pt and nt and pt == nt)


def _is_upgrade(primary, payload, code):
    if primary is None or not isinstance(payload, dict):
        return False
    if _code_references_reuse(code):
        return True
    if payload.get('__phase__') == 'presentation' and _shares_envelope(
        primary, payload,
    ):
        return True
    return False


def classify_vs_primary(primary, payload, *, code=''):
    """Return pin | upgrade | minor | probe. Domain-agnostic."""
    if not isinstance(payload, dict):
        return PROBE
    if payload.get('error') or payload.get('__force_retry__'):
        return PROBE
    complete = is_complete_artifact(payload)
    if primary is None:
        return PIN if complete else PROBE
    if _is_upgrade(primary, payload, code) and (
        complete or not is_hollow(payload)
    ):
        return UPGRADE
    if complete:
        return MINOR
    return PROBE


def presentation_payload(payload):
    """Full presentation envelope for sandbox ``previous_result`` (not rows only)."""
    if not isinstance(payload, dict):
        return {'data': []}
    out = {}
    for key in PRESENTATION_KEYS:
        if key in payload and payload[key] is not None:
            out[key] = copy.deepcopy(payload[key])
    if 'data' not in out:
        data = payload.get('data')
        if isinstance(data, list):
            out['data'] = copy.deepcopy(data)
        else:
            out['data'] = []
    return out


def _import_basket():
    try:
        from .turn_presentation_basket import (
            append_presentable,
            payload_to_basket_block,
        )
        return append_presentable, payload_to_basket_block
    except ImportError:
        from turn_presentation_basket import (  # type: ignore
            append_presentable,
            payload_to_basket_block,
        )
        return append_presentable, payload_to_basket_block


def apply(primary, basket, payload, code=''):
    """Mutate ``basket``. Return ``(new_primary, action)``.

    PIN clears the basket and places the artifact at index 0.
    UPGRADE replaces index 0 in place.
    MINOR appends after the primary (never unified-replaces the basket).
    PROBE leaves primary and basket unchanged.
    """
    action = classify_vs_primary(primary, payload, code=code)
    if action == PROBE or not isinstance(payload, dict):
        return primary, PROBE
    append_presentable, payload_to_basket_block = _import_basket()
    if action == PIN:
        new_primary = copy.deepcopy(payload)
        if isinstance(basket, list):
            del basket[:]
            append_presentable(basket, new_primary)
        return new_primary, PIN
    if action == UPGRADE:
        new_primary = copy.deepcopy(payload)
        if isinstance(basket, list):
            block = payload_to_basket_block(new_primary)
            if block and basket:
                basket[0] = block
            elif block is not None:
                append_presentable(basket, new_primary)
        return new_primary, UPGRADE
    # MINOR
    if isinstance(basket, list):
        append_presentable(
            basket, payload, allow_unified_replace=False,
        )
    return primary, MINOR
