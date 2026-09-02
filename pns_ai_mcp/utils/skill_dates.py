# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Deterministic relative/absolute *day* resolution for skill args.

Agnostic of domain: no business rules, only common calendar day phrases (ES/EN).
Used before any LLM param extraction so common day cases stay zero-cost.

Month / period phrases (hace N meses, last quarter, …) are NOT resolved here —
those stay free text so the hybrid path invokes the LLM via param_schema.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

# Folded keys only (accents stripped).
_WEEKDAYS = {
    'lunes': 0, 'monday': 0, 'mon': 0,
    'martes': 1, 'tuesday': 1, 'tue': 1, 'tues': 1,
    'miercoles': 2, 'wednesday': 2, 'wed': 2,
    'jueves': 3, 'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
    'viernes': 4, 'friday': 4, 'fri': 4,
    'sabado': 5, 'saturday': 5, 'sat': 5,
    'domingo': 6, 'sunday': 6, 'sun': 6,
}

# Longest names first so "thursday" wins over "thu".
_WEEKDAY_NAMES = sorted(_WEEKDAYS.keys(), key=len, reverse=True)

_NEXT_MARKERS = (
    'que viene', 'proximo', 'siguiente', 'next',
)
_THIS_MARKERS = (
    'este', 'esta', 'this',
)


def _fold(text):
    text = (text or '').strip().lower()
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    return ' '.join(text.split())


def _next_weekday(today, weekday, allow_today=False):
    """Next occurrence of ``weekday`` (Mon=0). If allow_today and today matches, today."""
    delta = (weekday - today.weekday()) % 7
    if delta == 0 and not allow_today:
        delta = 7
    return today + timedelta(days=delta)


def _find_weekday(folded_text):
    for name in _WEEKDAY_NAMES:
        if re.search(r'\b%s\b' % re.escape(name), folded_text):
            return _WEEKDAYS[name]
    return None


def is_help_like(text):
    """True for ?, help, ayuda, options… — deterministic; never hybrid LLM."""
    raw = (text or '').strip()
    if not raw:
        return False
    t = _fold(raw)
    if t in (
        '?', '¿', '？', 'ayuda', 'help', 'opciones', 'options', 'params',
        'parametros', 'parametros', 'uso', 'usage', '/?', '/ayuda', '/help',
        '/options', '/opciones',
    ):
        return True
    if re.fullmatch(r'[?¿？]+', t):
        return True
    # Short phrases that are clearly help (e.g. "ayuda?", "help please", "options")
    if len(t) <= 32 and any(
        re.search(r'(^|\s|/)' + re.escape(w) + r'(\s|$|\?|!|\.)', t)
        for w in (
            'ayuda', 'help', 'opciones', 'options', 'params', 'parametros',
            'usage', 'uso',
        )
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

    Handles: hoy/ayer/mañana/ISO, weekdays with este/próximo/que viene/next.
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

    if t in ('hoy', 'today'):
        return today
    if t in ('ayer', 'yesterday'):
        return today - timedelta(days=1)
    if t in ('anteayer', 'day before yesterday'):
        return today - timedelta(days=2)
    if t in ('manana', 'tomorrow'):
        return today + timedelta(days=1)
    if t in ('pasado manana', 'pasadomanana', 'day after tomorrow'):
        return today + timedelta(days=2)

    m = re.fullmatch(r'(20\d{2}|19\d{2})-(\d{2})-(\d{2})', t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    wd = _find_weekday(t)
    if wd is not None:
        if any(mkr in t for mkr in _NEXT_MARKERS):
            return _next_weekday(today, wd, allow_today=False)
        if any(mkr in t for mkr in _THIS_MARKERS):
            return _next_weekday(today, wd, allow_today=True)
        return _next_weekday(today, wd, allow_today=False)

    return None


def date_phrase_unresolved(text, today=None):
    """True when ``text`` is non-empty free text that is not a known day phrase."""
    raw = (text or '').strip()
    if not raw:
        return False
    if is_help_like(raw):
        return False
    return try_resolve_date(raw, today=today) is None
