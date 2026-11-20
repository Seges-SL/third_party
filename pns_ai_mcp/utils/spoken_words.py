# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Words a person says, per language, read from ``data/spoken/*.json``.

The engine holds no word of a human language. A language is one file next
to ``en.json``; every reader uses the union of all files, so a new language
works after a restart without touching Python.
"""
from __future__ import annotations

import functools
import json
import logging
import os
import unicodedata

_logger = logging.getLogger(__name__)

_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'spoken',
)


def fold(text):
    """Lowercase, no accents, single spaces."""
    text = (text or '').strip().lower()
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    return ' '.join(text.split())


@functools.lru_cache(maxsize=1)
def _packs():
    packs = []
    if not os.path.isdir(_DIR):
        return ()
    for name in sorted(os.listdir(_DIR)):
        if not name.endswith('.json'):
            continue
        try:
            with open(os.path.join(_DIR, name), encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            _logger.warning('Spoken words: cannot read %s', name, exc_info=True)
            continue
        if isinstance(data, dict):
            packs.append(data)
    return tuple(packs)


@functools.lru_cache(maxsize=None)
def words(key):
    """Folded words under ``key`` across every language file."""
    out = set()
    for pack in _packs():
        for word in pack.get(key) or ():
            if isinstance(word, str) and fold(word):
                out.add(fold(word))
    return frozenset(out)


@functools.lru_cache(maxsize=1)
def weekdays():
    """``{folded name: weekday}`` (Monday = 0) from each file's seven lists."""
    out = {}
    for pack in _packs():
        days = pack.get('weekdays') or ()
        for index, names in enumerate(days[:7]):
            for name in names or ():
                if isinstance(name, str) and fold(name):
                    out[fold(name)] = index
    return out
