# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Approximate identifier lookup (shape only — no business names).

Full-token ``ilike`` misses letter swaps. This helper gathers candidates
from ``name_search``, token ``ilike`` and short windows, then ranks them
with ``difflib``. The caller names the model and the spoken tokens.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

_NON_ALNUM = re.compile(r'[^0-9a-z]+')
_DEFAULT_FIELDS = ('name', 'display_name')
_DEFAULT_LIMIT = 15
_DEFAULT_MIN_SCORE = 0.55
_CANDIDATE_CAP = 250
_WINDOW = 4


def fold_text(text):
    """Lowercase ASCII-ish form (accents stripped)."""
    raw = '' if text is None else str(text)
    if not raw:
        return ''
    norm = unicodedata.normalize('NFKD', raw)
    return ''.join(ch for ch in norm if not unicodedata.combining(ch)).lower()


def compact_text(text):
    """Letters and digits only."""
    return _NON_ALNUM.sub('', fold_text(text))


def text_words(text):
    return [part for part in _NON_ALNUM.split(fold_text(text)) if part]


def windows_of(text, size=_WINDOW):
    """Overlapping compact slices used to widen an empty token search."""
    compact = compact_text(text)
    if not compact:
        return []
    if len(compact) <= size:
        return [compact]
    return [compact[i:i + size] for i in range(0, len(compact) - size + 1)]


def affinity_score(needle, label):
    """0..1 how close *needle* is to *label* (full text and longest word)."""
    needle_c = compact_text(needle)
    if not needle_c:
        return 0.0
    labels = [compact_text(label)]
    words = text_words(label)
    if words:
        labels.append(max(words, key=len))
        labels.append(''.join(words))
    best = 0.0
    for lab in labels:
        if not lab:
            continue
        if needle_c == lab:
            return 1.0
        if needle_c in lab or lab in needle_c:
            best = max(best, 0.92)
        best = max(best, difflib.SequenceMatcher(None, needle_c, lab).ratio())
    return best


def _as_needles(needles):
    if needles is None:
        return []
    if isinstance(needles, str):
        raw = [needles]
    elif isinstance(needles, (list, tuple, set)):
        raw = list(needles)
    else:
        raw = [needles]
    out = []
    seen = set()
    for item in raw:
        text = str(item).strip() if item is not None else ''
        if not text:
            continue
        key = fold_text(text)
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _model_key(model):
    if isinstance(model, str):
        key = model.strip()
        if key:
            return key, None
        raise ValueError('search_by_affinity(model, needles) needs a model name')
    key = getattr(model, '_name', None)
    if isinstance(key, str) and key.strip():
        return key.strip(), model
    raise ValueError(
        'search_by_affinity(model, needles) needs a model name or recordset'
    )


def _model_in_env(env, model_name):
    try:
        return model_name in env
    except Exception:
        return False


def _recordset(env, model):
    model_name, given = _model_key(model)
    if given is not None and getattr(given, '_fields', None) is not None:
        return given, model_name
    if env is None or not _model_in_env(env, model_name):
        raise KeyError(model_name)
    return env[model_name], model_name


def _usable_fields(Model, fields):
    wanted = list(fields) if fields else list(_DEFAULT_FIELDS)
    have = getattr(Model, '_fields', None) or {}
    out = []
    for name in wanted:
        if not isinstance(name, str) or not name.strip():
            continue
        name = name.strip()
        if name in have and name not in out:
            out.append(name)
    return out or [name for name in _DEFAULT_FIELDS if name in have]


def _label_of(rec, fields):
    display = getattr(rec, 'display_name', None)
    if isinstance(display, str) and display.strip():
        return display
    for name in fields:
        val = getattr(rec, name, None)
        if isinstance(val, str) and val.strip():
            return val
    return ''


def _search_ilike(Model, field, needle, domain, limit):
    clause = [(field, 'ilike', needle)]
    if domain:
        clause = list(domain) + clause
    try:
        return Model.search(clause, limit=limit)
    except Exception:
        return None


def _name_search(Model, needle, domain, limit):
    getter = getattr(Model, 'name_search', None)
    if not callable(getter):
        return []
    try:
        found = getter(
            needle, args=domain or [], operator='ilike', limit=limit,
        )
    except TypeError:
        try:
            found = getter(needle, domain=domain or [], operator='ilike', limit=limit)
        except Exception:
            return []
    except Exception:
        return []
    ids = []
    for row in found or []:
        if isinstance(row, (list, tuple)) and row:
            ids.append(row[0])
        elif isinstance(row, int):
            ids.append(row)
    return ids


def _collect_ids(Model, needles, fields, domain):
    ids = []
    seen = set()

    def _add(recset_or_ids):
        if recset_or_ids is None:
            return
        if isinstance(recset_or_ids, (list, tuple, set)):
            values = recset_or_ids
        else:
            values = getattr(recset_or_ids, 'ids', None)
            if values is None:
                try:
                    values = [rec.id for rec in recset_or_ids]
                except Exception:
                    return
        for rec_id in values:
            if rec_id in seen:
                continue
            seen.add(rec_id)
            ids.append(rec_id)
            if len(ids) >= _CANDIDATE_CAP:
                return True
        return False

    for needle in needles:
        if _add(_name_search(Model, needle, domain, 80)):
            return ids
        for field in fields:
            if _add(_search_ilike(Model, field, needle, domain, 80)):
                return ids
        for gram in windows_of(needle, _WINDOW):
            if len(gram) < 3:
                continue
            for field in fields:
                if _add(_search_ilike(Model, field, gram, domain, 80)):
                    return ids
        if len(seen) < 3:
            for gram in windows_of(needle, 3):
                if len(gram) < 3:
                    continue
                for field in fields:
                    if _add(_search_ilike(Model, field, gram, domain, 80)):
                        return ids
    return ids


def search_by_affinity(env, model, needles, fields=None, domain=None,
                       limit=_DEFAULT_LIMIT, min_score=None):
    """Ranked rows for spoken / transposed tokens.

    Returns ``[{id, name, score}, …]``. Empty needles or no close match → ``[]``.
    """
    tokens = _as_needles(needles)
    if not tokens:
        return []
    Model, model_name = _recordset(env, model)
    use_fields = _usable_fields(Model, fields)
    if not use_fields:
        return []
    try:
        cap = int(limit) if limit is not None else _DEFAULT_LIMIT
    except (TypeError, ValueError):
        cap = _DEFAULT_LIMIT
    if cap <= 0:
        return []
    floor = _DEFAULT_MIN_SCORE if min_score is None else float(min_score)
    extra_domain = list(domain) if domain else None
    ids = _collect_ids(Model, tokens, use_fields, extra_domain)
    if not ids:
        return []
    try:
        recs = Model.browse(ids)
    except Exception:
        return []
    ranked = []
    for rec in recs:
        label = _label_of(rec, use_fields)
        score = 0.0
        for token in tokens:
            score = max(score, affinity_score(token, label))
        if score < floor:
            continue
        ranked.append({
            'id': rec.id,
            'name': label,
            'score': round(score, 3),
            '__model': model_name,
        })
    ranked.sort(key=lambda row: (-row['score'], row['id']))
    return ranked[:cap]
