# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Which model an id belonged to, for the length of one turn.

A row that stands for a record carries its id, and the link to the form needs
the model that goes with it. The engine learns that pair the moment a step
reads the ORM. A later step in the same turn often rebuilds the rows from a
literal — same ids, no recordset left in the sandbox to say where they came
from — and the row would reach the screen with nothing behind it to point at.

So the pairs are kept while the turn lasts. An id seen under two models is
dropped instead of guessed: a link to the wrong record is worse than no link.
"""
from __future__ import annotations

_MISSING = object()
# Enough for the tables a turn puts on screen, and bounded so a listing of
# thousands of rows cannot grow the turn in memory.
_MAX = 2000


def remember_record(memory, model, rid):
    """Pair an id with its model. A second model for the same id erases both."""
    if not isinstance(memory, dict) or not model or not isinstance(model, str):
        return
    try:
        rid = int(rid)
    except (TypeError, ValueError):
        return
    if rid <= 0:
        return
    known = memory.get(rid, _MISSING)
    if known is _MISSING:
        if len(memory) < _MAX:
            memory[rid] = model
    elif known != model:
        memory[rid] = None


def remember_rows(memory, rows):
    """Learn the pairs carried by rows that already reached a screen."""
    if not isinstance(rows, (list, tuple)):
        return
    for row in rows:
        if isinstance(row, dict):
            remember_record(memory, row.get('__model'), row.get('id'))


def known_models(memory):
    """The pairs that are not in doubt, as ``{id: model}``."""
    if not isinstance(memory, dict):
        return {}
    return {
        rid: model for rid, model in memory.items()
        if model and isinstance(model, str) and isinstance(rid, int)
    }
