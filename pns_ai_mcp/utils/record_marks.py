# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Records the user pointed at, as words the engine can hear.

Pointing at a row is naming a record without spelling it. The engine only
reads text, so the pick has to arrive as a sentence; narrowing the cached
dataset on its own left the model free to search the name again.

Plain functions over ``{model, id, label}`` dicts: no session model, no
channel. Each host keeps its own marks and calls these.
"""
from __future__ import annotations

MAX_MARKS = 24
MARK_LABEL_CHARS = 80

# Not user-facing copy: this travels to the engine, which reads English.
MARKS_SENTENCE = (
    'The user tapped these records on screen and they are what this sentence '
    'is about: %s. Use those exact ids as the subject, do not search the name '
    'again and do not offer other records unless asked.'
)

# What was just written is what «add this» and «change that» are about. A
# hint and not an order: the next sentence may well name something else.
LAST_WRITE_SENTENCE = (
    'The last record written in this conversation is %s. If this sentence '
    'says to change or add something without saying what to, it is that '
    'one. If it names or describes another record, find that one instead.'
)


def clean_marks(refs, *, limit=MAX_MARKS, label_chars=MARK_LABEL_CHARS):
    """Keep the rows that name a record: a real model and a positive id."""
    marks = []
    seen = set()
    for ref in refs if isinstance(refs, list) else ():
        if not isinstance(ref, dict):
            continue
        model = ref.get('model')
        try:
            rid = int(ref.get('id'))
        except (TypeError, ValueError):
            continue
        if not isinstance(model, str) or not model or rid <= 0:
            continue
        key = (model, rid)
        if key in seen:
            continue
        seen.add(key)
        label = ref.get('label')
        marks.append({
            'model': model,
            'id': rid,
            'label': (label or '').strip()[:label_chars]
            if isinstance(label, str) else '',
        })
        if len(marks) >= limit:
            break
    return marks


def marked_labels(marks):
    """Names of the marked records, for a transcriber to lean on."""
    return [
        m['label'] for m in (marks or [])
        if isinstance(m, dict) and m.get('label')
    ]


def marks_sentence(marks):
    """The pick, said out loud for the engine. Empty when nothing is marked."""
    bits = []
    for mark in marks or ():
        if not isinstance(mark, dict) or not mark.get('model'):
            continue
        label = (mark.get('label') or '').strip()
        ref = '%s#%s' % (mark['model'], mark['id'])
        bits.append('%s (%s)' % (ref, label) if label else ref)
    if not bits:
        return ''
    return MARKS_SENTENCE % ', '.join(bits)


def last_write_sentence(ref):
    """The record just written, said out loud for the engine.

    Said and not used to narrow anything: a dataset filtered down to it
    would answer the next question about something else with this one.
    """
    if not isinstance(ref, dict) or not ref.get('model'):
        return ''
    try:
        rid = int(ref.get('id'))
    except (TypeError, ValueError):
        return ''
    if rid <= 0:
        return ''
    named = '%s#%s' % (ref['model'], rid)
    label = (ref.get('label') or '').strip()
    return LAST_WRITE_SENTENCE % ('%s (%s)' % (named, label) if label else named)


def narrow_rows(marks, rows):
    """The marked rows of a cached dataset, or all of them.

    Marks that are no longer in the dataset change nothing: the user is
    pointing at an answer that has already scrolled away.
    """
    if not marks or not isinstance(rows, list):
        return rows
    wanted = {
        (m['model'], m['id']) for m in marks
        if isinstance(m, dict) and m.get('model')
    }
    picked = [
        row for row in rows
        if isinstance(row, dict)
        and (row.get('__model'), row.get('id')) in wanted
    ]
    return picked or rows
