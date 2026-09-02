# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Turn presentation basket — keep N presentable tool results in one bubble.

See ``docs/decisions/turn_presentation_basket.md``. Domain-agnostic: no map /
business hardcode. Orthogonal to local vs LLM formatting mode.
"""
from __future__ import annotations

import copy
import logging

_logger = logging.getLogger(__name__)

# Keys copied into a tables[] entry (presentation contract, not domain).
_BLOCK_KEYS = (
    'data', 'groups', 'sections', 'tables', 'formatted_text',
    'map_url', 'map_pins', 'pins_url', 'summary', 'title', 'name',
    'geo_coords', 'geo_thumbs', 'notices',
    '__model', '__subtle_zebra__', '__no_charts__', '__row_links__',
)


def is_extraction_probe(payload):
    """True for mid-turn extraction that must not enter the chat basket."""
    if not isinstance(payload, dict):
        return True
    phase = payload.get('__phase__')
    if phase == 'extraction' and not (
        payload.get('__presentation_complete__')
        or payload.get('__ready_for_presentation__')
    ):
        return True
    return False


def has_presentable_content(payload):
    """Something the renderer / banner can show (rows, HTML, map card, …)."""
    if not isinstance(payload, dict):
        return False
    if payload.get('formatted_text'):
        return True
    if payload.get('map_url') or payload.get('map_pins') or payload.get('pins_url'):
        return True
    for key in ('data', 'groups', 'sections', 'tables'):
        val = payload.get(key)
        if isinstance(val, list) and val:
            return True
    return False


def is_basket_presentable(payload):
    """Eligible for the turn basket (user-facing, not an extraction probe)."""
    if not isinstance(payload, dict):
        return False
    if payload.get('error') or payload.get('__force_retry__'):
        return False
    if is_extraction_probe(payload):
        return False
    if not has_presentable_content(payload):
        return False
    # Align with retorno_directo: explicit user-facing, presentation phase,
    # or trusted formatted_text ready for chat.
    if (
        payload.get('__direct_return__')
        or payload.get('__return_direct__')
        or payload.get('__return_direct_to_user__')
        or payload.get('__presentation_complete__')
        or payload.get('__phase__') == 'presentation'
        or payload.get('__satisfied__')
    ):
        return True
    if (
        payload.get('__extraction_complete__')
        and payload.get('__ready_for_presentation__')
        and payload.get('summary')
    ):
        return True
    # Server already attached chat HTML (trusted types).
    if payload.get('formatted_text') and payload.get('__fmt_type__') in (
        'server_side_python', 'author_html', 'local_json', 'local_raw',
    ):
        return True
    return False


def _multi_section_list(payload):
    """Return a multi-entry tables/groups/sections list, or None."""
    if not isinstance(payload, dict):
        return None
    for key in ('tables', 'groups', 'sections'):
        raw = payload.get(key)
        if isinstance(raw, list) and len(raw) > 1:
            return raw
    return None


def payload_already_unified(payload):
    """LLM (or prior merge) already shipped a multi-block envelope."""
    return _multi_section_list(payload) is not None


def payload_to_basket_block(payload, title=None):
    """Normalize a presentable payload into one ``tables[]`` entry."""
    if not isinstance(payload, dict):
        return None
    # Single nested table entry → unwrap.
    tables = payload.get('tables')
    if isinstance(tables, list) and len(tables) == 1 and isinstance(tables[0], dict):
        block = copy.deepcopy(tables[0])
    else:
        block = {}
        for key in _BLOCK_KEYS:
            if key == 'tables':
                continue
            if key in payload and payload[key] is not None:
                block[key] = copy.deepcopy(payload[key])
        # Keep nested multi-tables only when this payload IS the unified one
        # (caller should not append siblings in that case).
        if isinstance(tables, list) and tables:
            block['tables'] = copy.deepcopy(tables)

    t = title
    if not t:
        t = payload.get('title') or payload.get('summary') or payload.get('name')
    if t and not block.get('title'):
        block['title'] = t if isinstance(t, str) else str(t)
    return block


def append_presentable(basket, payload, title=None, *, allow_unified_replace=True):
    """Push a presentable payload onto ``basket`` (mutates list). Returns True if added.

    ``allow_unified_replace=False`` keeps index 0 (the primary artifact) when a
    later multi-block envelope arrives — probes must not wipe the basket.
    """
    if not isinstance(basket, list):
        return False
    if not is_basket_presentable(payload):
        return False
    # Unified multi-block payload replaces the whole basket (LLM already merged)
    # only when the caller allows it (empty basket / no primary pinned).
    if payload_already_unified(payload) and allow_unified_replace:
        basket[:] = [copy.deepcopy(payload)]
        return True
    block = payload_to_basket_block(payload, title=title)
    if not block:
        return False
    basket.append(block)
    return True


def synthesize_basket_payload(basket):
    """Build a single presentable dict from the basket, or None.

    - 0 blocks → None
    - 1 block that is already a full unified payload → that payload
    - 1 block entry → that entry as a normal result (data/map/…)
    - N blocks → ``{'tables': [...], …flags}``
    """
    if not basket:
        return None
    if len(basket) == 1:
        only = basket[0]
        if payload_already_unified(only):
            out = copy.deepcopy(only)
        else:
            out = copy.deepcopy(only)
        out.setdefault('__return_direct__', True)
        out.setdefault('__phase__', 'presentation')
        return out

    # Prefer a single already-unified payload if somehow alone in spirit.
    tables = []
    for item in basket:
        if payload_already_unified(item) and len(basket) == 1:
            return copy.deepcopy(item)
        nested = item.get('tables') if isinstance(item, dict) else None
        if isinstance(nested, list) and nested and not item.get('data'):
            for entry in nested:
                if isinstance(entry, dict):
                    tables.append(copy.deepcopy(entry))
            continue
        tables.append(copy.deepcopy(item) if isinstance(item, dict) else item)

    return {
        'tables': tables,
        '__return_direct__': True,
        '__phase__': 'presentation',
        '__presentation_complete__': True,
    }


def render_basket_html(basket, *, fallback_html=None, env=None, render_context=None):
    """HTML for the basket, or ``fallback_html`` when a single/empty basket.

    Index 0 is the primary artifact for the turn. Callers must not wipe the
    basket after a mid-turn ``replace`` — later rounds may append minors or
    upgrade index 0. A probe must never replace the whole list.
    """
    if not basket or len(basket) <= 1:
        return fallback_html

    payload = synthesize_basket_payload(basket)
    if not payload:
        return fallback_html

    try:
        from .relaxaicode_render import (
            maybe_attach_formatted_text,
            render_context_from_env,
            wrap_bare_images_clickable,
        )
    except ImportError:  # unit tests without package parent
        from relaxaicode_render import (  # type: ignore
            maybe_attach_formatted_text,
            render_context_from_env,
            wrap_bare_images_clickable,
        )

    work = copy.deepcopy(payload)
    work.pop('formatted_text', None)
    rcx = render_context
    if rcx is None and env is not None:
        try:
            rcx = render_context_from_env(env, result=work)
        except Exception:
            rcx = None
    maybe_attach_formatted_text(
        work,
        summary=work.get('summary') or '',
        render_context=rcx,
        force=True,
    )
    html = work.get('formatted_text')
    if not html:
        _logger.debug('turn_presentation_basket: merge produced no HTML')
        return fallback_html
    try:
        return wrap_bare_images_clickable(html)
    except Exception:
        return html
