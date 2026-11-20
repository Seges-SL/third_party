# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Run one skill when the sentence hits its own trigger phrases.

The phrases live on the skill. This module does not name a skill or a
business topic. Zero hits or several hits do not run anything.
"""
from __future__ import annotations

from .domain_index import normalize_text, score_entry


def parse_triggers(raw):
    """Comma or newline list. Blank pieces are dropped."""
    if isinstance(raw, (list, tuple)):
        parts = raw
    else:
        parts = str(raw or '').replace('\n', ',').split(',')
    out = []
    for part in parts:
        text = str(part or '').strip()
        if text and text not in out:
            out.append(text)
    return out


def match_one_skill(message, rows):
    """Return ``(command, sentence)`` when exactly one row hits.

    ``rows`` items are ``{command, triggers}``. The sentence is the
    arguments, so the skill's own period parser can read it. Several
    matches return None.
    """
    text = (message or '').strip()
    if not text or text.startswith('/'):
        return None
    hits = []
    norm = normalize_text(text)
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        command = (row.get('command') or '').strip()
        triggers = parse_triggers(row.get('triggers'))
        if not command or not triggers:
            continue
        score, _matched = score_entry(norm, {'triggers': triggers})
        if score > 0 and command not in hits:
            hits.append(command)
    if len(hits) != 1:
        return None
    return hits[0], text
