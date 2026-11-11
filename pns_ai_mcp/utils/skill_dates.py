# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Deterministic relative/absolute *day* resolution for skill args.

Agnostic of domain: no business rules, only common calendar day phrases.
The words come from ``data/spoken/*.json`` (one file per language).
Used before any LLM param extraction so common day cases stay zero-cost.

Month / period phrases (last quarter, …) are NOT resolved here —
those stay free text so the hybrid path invokes the LLM via param_schema.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

_QUESTION_MARKS = '?¿？'


def _spoken():
    try:
        from . import spoken_words
        return spoken_words
    except ImportError:
        import importlib.util
        import os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'spoken_words.py')
        spec = importlib.util.spec_from_file_location('spoken_words', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def _fold(text):
    return _spoken().fold(text)


def _next_weekday(today, weekday, allow_today=False):
    """Next occurrence of ``weekday`` (Mon=0). If allow_today and today matches, today."""
    delta = (weekday - today.weekday()) % 7
    if delta == 0 and not allow_today:
        delta = 7
    return today + timedelta(days=delta)


def _find_weekday(folded_text):
    days = _spoken().weekdays()
    # Longest names first so "thursday" wins over "thu".
    for name in sorted(days, key=len, reverse=True):
        if re.search(r'\b%s\b' % re.escape(name), folded_text):
            return days[name]
    return None


def is_help_like(text):
    """True for ?, or a help word of any language file — deterministic; never hybrid LLM."""
    raw = (text or '').strip()
    if not raw:
        return False
    t = _fold(raw)
    if re.fullmatch(r'/?[%s]+' % re.escape(_QUESTION_MARKS), t):
        return True
    help_words = _spoken().words('help')
    if t.lstrip('/') in help_words:
        return True
    # Short phrases that are clearly help (e.g. "help?", "help please")
    if len(t) <= 32 and any(
        re.search(r'(^|\s|/)' + re.escape(w) + r'(\s|$|\?|!|\.)', t)
        for w in help_words
    ):
        return True
    return False


def skill_args_are_help(args):
    """True when slash args mean help for ANY skill (raw or parsed keys)."""
    raw = (args or '').strip()
    if is_help_like(raw):
        return True
    # Also inspect common sandbox keys after deterministic parse.
    try:
        from .skill_runtime import parse_skill_arguments
        params = parse_skill_arguments(raw)
    except Exception:
        return False
    for key in ('arguments', 'lugar', 'periodo', 'mes', 'fecha'):
        val = params.get(key)
        if val is not None and is_help_like(str(val)):
            return True
    return False


def try_resolve_date(text, today=None):
    """Parse a free-text day phrase → ``date`` or None if unresolved.

    Handles: today/yesterday/tomorrow/ISO, weekdays with this/next markers.
    Returns None when the phrase is empty, help-like, or not a date.
    """
    if today is None:
        today = date.today()
    raw = (text or '').strip()
    if not raw:
        return None
    t = _fold(raw)
    if is_help_like(raw):
        return None

    spoken = _spoken()
    for key, delta in (
        ('today', 0), ('yesterday', -1), ('day_before_yesterday', -2),
        ('tomorrow', 1), ('day_after_tomorrow', 2),
    ):
        if t in spoken.words(key):
            return today + timedelta(days=delta)

    m = re.fullmatch(r'(20\d{2}|19\d{2})-(\d{2})-(\d{2})', t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    wd = _find_weekday(t)
    if wd is not None:
        if any(mkr in t for mkr in spoken.words('next')):
            return _next_weekday(today, wd, allow_today=False)
        if any(mkr in t for mkr in spoken.words('this')):
            return _next_weekday(today, wd, allow_today=True)
        return _next_weekday(today, wd, allow_today=False)

    return None

