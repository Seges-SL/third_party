# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""What the database refused, said to the person who asked for it.

A failed write came back as the driver wrote it —constraint names, ``DETAIL:``
lines, the column as it is spelled in the table— and that is neither readable
nor actionable: the user who dictated a sentence cannot tell from it whether
to say the sentence again, change a word or call someone.

Nameless: the shapes matched here are PostgreSQL's own wording, the same in
any database, and the field is named back with the label its model publishes.
Anything else comes out as its first line, without the machinery.
"""
from __future__ import annotations

import re

try:  # loaded on its own by the tests, with no Odoo runtime under it
    from odoo import _
except ImportError:  # pragma: no cover
    def _(source):
        return source

_DUPLICATE = re.compile(r'duplicate key value violates unique', re.I)
_KEY = re.compile(r'Key \(([^)]+)\)=\((.*?)\) already exists', re.I | re.S)
_NOT_NULL = re.compile(
    r'null value in column "([^"]+)" violates not-null', re.I,
)
_FOREIGN = re.compile(r'violates foreign key constraint', re.I)
_NOISE = re.compile(r'^(DETAIL|CONTEXT|HINT|LINE \d+|STATEMENT)\s*:', re.I)
_MAX = 200


def _first_line(text):
    """The sentence of the error, without the machinery under it."""
    for line in str(text).splitlines():
        line = line.strip()
        if line and not _NOISE.match(line):
            return line[:_MAX]
    return str(text).strip()[:_MAX]


def _label(env, model, fname):
    """The field as the form calls it, or the column when there is no model."""
    if env is None or not model or not fname:
        return fname
    try:
        field = env[model]._fields.get(fname)
    except Exception:
        return fname
    return getattr(field, 'string', None) or fname


def _model_label(env, model):
    if env is None or not model:
        return model
    try:
        return env[model]._description or model
    except Exception:
        return model


def human_db_error(env, error, model=None, translate=None):
    """The refusal as a sentence. Unknown shapes keep their first line.

    ``translate`` is the ack translator of the caller: this runs under a
    public request, so the plain ``_`` would answer in English while the rest
    of the card speaks the user's language.
    """
    text = str(error or '').strip()
    if not text:
        return ''
    say = translate if callable(translate) else (lambda source: _(source))

    if _DUPLICATE.search(text):
        found = _KEY.search(text)
        if found:
            field = _label(env, model, found.group(1).split(',')[0].strip())
            value = ' '.join(found.group(2).split())[:60]
            return say(
                'There is already a record with that %(field)s («%(value)s»).'
            ) % {'field': field, 'value': value}
        return say('That record already exists.')

    found = _NOT_NULL.search(text)
    if found:
        return say('«%s» cannot be empty.') % _label(
            env, model, found.group(1),
        )

    if _FOREIGN.search(text):
        return say(
            'Something the operation pointed at is no longer there.'
        )

    return _first_line(text)


def failed_ack(env, title, error, model=None, translate=None):
    """The line the card shows when the write did not happen."""
    say = translate if callable(translate) else (lambda source: _(source))
    reason = human_db_error(env, error, model=model, translate=translate)
    head = say('Nothing was written: «%s» could not be completed.') % (
        title or say('the operation')
    )
    return '%s\n\n%s' % (head, reason) if reason else head
