# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Deterministic domain index: match user text against routing entries.

Pure helpers (no ``env``). The routing entries (target code + triggers +
priority + soft_depends) now live as ``ai.context`` rows with
``context_type='discovery'`` and are composed in
``ai.context.get_discovery_entries`` — see
``docs/decisions/domain_index_dynamic_load.md``. This module keeps only the
env-free scoring/formatting helpers.

A hit's *effect* depends on ``target_kind`` (same channel, different payload):
domain pack body, short ``api_call`` hint, or (phase 2) whitelist hint.
"""
from __future__ import annotations

import logging
import re
import time
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

_logger = logging.getLogger(__name__)

DEFAULT_MAX_PACKS = 2
DEFAULT_MAX_SERVICES = 4
# Single kill-switch (Settings → AI Engine). Default ON.
INJECT_ICP_KEY = 'pns_ai_mcp.domain_index_inject'
# Legacy observation flag (removed from product; migrate may delete the ICP).
LEGACY_SHADOW_ICP_KEY = 'pns_ai_mcp.domain_index_shadow'

TARGET_KIND_DOMAIN = 'domain'
TARGET_KIND_API_SERVER = 'api_server'
TARGET_KIND_URL_WHITELIST = 'url_whitelist'


def entry_target_kind(entry: Dict[str, Any]) -> str:
    """Normalize ``target_kind``; missing/empty means a domain pack (compat)."""
    kind = str(entry.get('target_kind') or TARGET_KIND_DOMAIN).strip()
    return kind or TARGET_KIND_DOMAIN


def filter_entries_by_kind(
    entries: Sequence[Dict[str, Any]],
    kind: str,
) -> List[Dict[str, Any]]:
    want = (kind or TARGET_KIND_DOMAIN).strip() or TARGET_KIND_DOMAIN
    return [e for e in (entries or []) if entry_target_kind(e) == want]


def detection_row_code(server_code: str, locale: str = '') -> str:
    """Stable discovery ``code`` for an ``ai.api.server`` detection row."""
    safe = re.sub(r'[^a-zA-Z0-9_]+', '_', (server_code or '').strip())
    safe = safe.strip('_').lower() or 'server'
    base = 'discovery_api_%s' % safe
    loc = (locale or '').strip().replace('-', '_')
    return '%s_%s' % (base, loc) if loc else base


def compose_discovery_entries(
    rows: Sequence[Dict[str, Any]],
    *,
    core_codes: Optional[Set[str]] = None,
    active_server_codes: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """Locale-collapsed rows → matchable index entries.

    Each *row* is already the chosen locale variant and has ``target``,
    optional ``target_kind``, ``triggers``, ``priority``, ``soft_depends``.
    Domain rows that target core, and ``api_server`` rows whose server is
    missing or inactive, are soft-skipped (same idea as orphan packs).
    """
    core = set(core_codes or ())
    servers = set(active_server_codes or ())
    entries: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str]] = set()
    for row in rows or []:
        kind = entry_target_kind(row)
        target = (row.get('target') or row.get('code') or '')
        target = str(target).strip()
        if not target:
            continue
        if kind == TARGET_KIND_DOMAIN and target in core:
            continue
        if kind == TARGET_KIND_API_SERVER and target not in servers:
            continue
        key = (kind, target)
        if key in seen:
            continue
        seen.add(key)
        soft = [
            str(s).strip()
            for s in (row.get('soft_depends') or [])
            if str(s).strip()
        ]
        entries.append({
            'code': target,
            'target_kind': kind,
            'triggers': list(row.get('triggers') or []),
            'priority': int(row.get('priority') or 0),
            'soft_depends': soft,
            'source_module': row.get('source_module') or '',
        })
    return entries


def indexed_codes_from_entries(entries: Sequence[Dict[str, Any]]) -> set:
    """Turn-scoped **domain** codes (primary + soft_depends).

    ``api_server`` / whitelist hits do not occupy the pack cache exclusion
    set — they are hints, not context bodies.
    """
    codes = set()
    for entry in entries or []:
        if entry_target_kind(entry) != TARGET_KIND_DOMAIN:
            continue
        code = (entry.get('code') or '').strip()
        if code:
            codes.add(code)
        for dep in entry.get('soft_depends') or []:
            dep_c = str(dep).strip()
            if dep_c:
                codes.add(dep_c)
    return codes


def icp_flag_enabled(raw, default=True) -> bool:
    """Parse ICP string; missing/empty uses ``default``."""
    if raw is None or raw is False or str(raw).strip() == '':
        return bool(default)
    return str(raw).strip().lower() not in ('0', 'false', 'no', 'off')


def strip_accents(text: str) -> str:
    if not text:
        return ''
    norm = unicodedata.normalize('NFKD', text)
    return ''.join(ch for ch in norm if not unicodedata.combining(ch))


def normalize_text(text: str) -> str:
    return strip_accents((text or '').lower())


def _word_pattern(trigger: str) -> re.Pattern:
    """Whole-word-ish match; multi-word triggers match as substring phrase."""
    t = normalize_text(trigger).strip()
    if ' ' in t:
        return re.compile(re.escape(t))
    return re.compile(r'(?<!\w)%s(?!\w)' % re.escape(t))


def score_entry(norm_message: str, entry: Dict[str, Any]) -> Tuple[int, List[str]]:
    hits = []
    score = 0
    for trigger in entry.get('triggers') or []:
        pat = _word_pattern(trigger)
        if pat.search(norm_message):
            hits.append(trigger)
            # Longer triggers weigh more (phrase > token).
            score += max(1, len(normalize_text(trigger).split()))
    return score, hits


def match_domains(
    message: str,
    entries: Sequence[Dict[str, Any]],
    *,
    max_packs: int = DEFAULT_MAX_PACKS,
) -> Dict[str, Any]:
    """Return ranked domain codes for ``message``.

    Output::
        {
          'codes': [...],           # primary + soft_depends, capped
          'matches': [{'code', 'score', 'priority', 'hits'}, ...],
          'elapsed_ms': float,
        }
    """
    t0 = time.perf_counter()
    norm = normalize_text(message)
    ranked = []
    for entry in entries:
        score, hits = score_entry(norm, entry)
        if score <= 0:
            continue
        ranked.append({
            'code': entry['code'],
            'target_kind': entry_target_kind(entry),
            'score': score,
            'priority': int(entry.get('priority') or 0),
            'hits': hits,
            'soft_depends': list(entry.get('soft_depends') or []),
        })
    ranked.sort(key=lambda m: (m['score'], m['priority']), reverse=True)
    primary = ranked[: max(0, int(max_packs or 0))]
    codes: List[str] = []
    for m in primary:
        if m['code'] not in codes:
            codes.append(m['code'])
        for dep in m.get('soft_depends') or []:
            if dep not in codes:
                codes.append(dep)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return {
        'codes': codes,
        'matches': ranked,
        'elapsed_ms': elapsed_ms,
    }


def format_inject_header(codes: Sequence[str], elapsed_ms: float) -> str:
    """Section header before turn-scoped domain bodies."""
    if not codes:
        return ''
    return (
        '\n\n---\n[DOMAIN_PACKS codes=%s elapsed_ms=%.2f]\n'
        % (','.join(codes), float(elapsed_ms or 0.0))
    )


def format_service_detect_hint(matches: Sequence[Dict[str, Any]]) -> str:
    """Short post-catalogue hint when discover hits ``api_server`` codes.

    Cheap: does not consume the 1–2 domain-pack budget. No vendor literals.
    """
    codes: List[str] = []
    for match in matches or []:
        code = (match.get('code') or '').strip()
        if code and code not in codes:
            codes.append(code)
    if not codes:
        return ''
    listed = ', '.join(codes)
    return (
        '\n\n---\n[EXTERNAL_SERVICE codes=%s]\n'
        'Matched external service: use propose api_call with server code %s. '
        'Do not inspect ai.api.server; the catalogue above lists the tools.\n'
        % (listed, listed)
    )


def format_index_catalog(entries: Sequence[Dict[str, Any]], max_entries: int = 48) -> str:
    """Compact always-available index for MCP clients without a query yet.

    Lists **domain** ``code`` + a few triggers so the model can
    ``get_context(code)`` or re-call ``system_prompt`` with ``query``.
    Service rows are not packs and stay out of this listing.
    """
    domain_entries = filter_entries_by_kind(entries, TARGET_KIND_DOMAIN)
    if not domain_entries:
        return ''
    lines = [
        '',
        '---',
        '[DOMAIN_INDEX catalog — pass arguments.query on prompts/get(system_prompt) '
        'to inject matched pack bodies; or get_context(context_name=<code>)]',
    ]
    shown = 0
    for entry in domain_entries:
        code = (entry.get('code') or '').strip()
        if not code:
            continue
        triggers = [
            str(t).strip() for t in (entry.get('triggers') or []) if str(t).strip()
        ][:6]
        trig_txt = ', '.join(triggers) if triggers else '—'
        lines.append('- %s: %s' % (code, trig_txt))
        shown += 1
        if shown >= max_entries:
            lines.append('… (%s more packs in index)' % (len(domain_entries) - shown))
            break
    return '\n'.join(lines)


# Identity tokens that are protocol noise, not spoken vocabulary.
_IDENTITY_STOP = frozenset({
    'api', 'server', 'http', 'https', 'www', 'mcp', 'openapi', 'swagger',
    'json', 'the', 'and', 'for', 'of',
})
DETECTION_TRIGGER_CAP = 24
DETECTION_TRIGGER_SCHEMA = {
    'triggers': {
        'type': 'array',
        'desc': (
            'Short spoken words or phrases a user would say to name this '
            'external service or its typical tasks. Locale-specific. '
            'No secrets, no URLs, no invented server codes.'
        ),
    },
}


def identity_detection_triggers(code: str, name: str) -> List[str]:
    """Zero-cost tokens from server code + name (same idea as skill key=value)."""
    raw: List[str] = []
    code = (code or '').strip()
    name = (name or '').strip()
    if code:
        raw.append(code)
        raw.extend(re.split(r'[^0-9A-Za-z]+', code))
    if name:
        raw.extend(re.split(r'[\s,/;|]+', name))
    return merge_trigger_lists(raw)


def merge_trigger_lists(*groups: Sequence[Any]) -> List[str]:
    """Dedupe by accent-folded key; keep first spelling; cap length."""
    out: List[str] = []
    seen = set()
    for group in groups:
        for item in group or []:
            text = str(item).strip()
            if len(text) < 2:
                continue
            key = normalize_text(text)
            if not key or key in seen or key in _IDENTITY_STOP:
                continue
            seen.add(key)
            out.append(text)
            if len(out) >= DETECTION_TRIGGER_CAP:
                return out
    return out


def build_detection_triggers_prompt(
    *,
    locale: str,
    code: str,
    name: str,
    usage_guide: str,
    already: Sequence[str],
) -> Tuple[str, str]:
    """Short JSON extraction prompt — same family as skill ``param_schema``.

    No tools, no ReAct. The model only fills the ``triggers`` array.
    """
    locale = (locale or '').strip()
    already_txt = ', '.join(already) if already else '—'
    guide = (usage_guide or '').strip()
    if len(guide) > 1500:
        guide = guide[:1500] + '…'
    system = (
        'You are a parameter-extraction function. Return EXCLUSIVELY a valid '
        'JSON object (no prose, no markdown fences) with EXACTLY the key '
        '"triggers" (array of short strings).\n'
        'Locale: %s.\n'
        'Rules: do NOT invent a different server code; do NOT copy secrets, '
        'tokens, URLs or header names; prefer spoken vocabulary for this '
        'locale; keep items short; if nothing useful beyond the already-'
        'extracted tokens, return {"triggers": []}. Reply with JSON only.'
        % (locale or 'neutral')
    )
    user = (
        'Server code: %s\n'
        'Server name: %s\n'
        'Usage guide:\n%s\n'
        'Already extracted (keep these, add locale synonyms only):\n%s\n'
        % (code or '', name or code or '', guide or '—', already_txt)
    )
    return system, user
