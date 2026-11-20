# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""The label a person needs to recognise a record someone else picked.

A name on its own rarely settles it: two companies carry the same words and
tell themselves apart by where they are. Odoo already knows how to place a
record, and the shape of that line comes from the country of the record, not
from a list of fields written here. So this asks for it and tidies the holes
the format leaves when a part of the address is empty. A model that cannot
place itself simply answers with its name.
"""
from __future__ import annotations

import re

# An address format prints its parts blind: drop one and the punctuation that
# was holding it stays behind.
_EMPTY_OPEN = re.compile(r'\(\s*,\s*')
_EMPTY_CLOSE = re.compile(r'\s*,\s*\)')
_COMMA_RUN = re.compile(r'(,\s*)+')
_MAX = 180


def _tidy(text):
    out = _EMPTY_OPEN.sub('(', text)
    out = _EMPTY_CLOSE.sub(')', out)
    out = _COMMA_RUN.sub(', ', out)
    out = ' '.join(out.split()).strip(' ,')
    return out.replace('( ', '(').replace(' )', ')')


def where_it_is(rec):
    """The address of a record in one line, empty when the model has none."""
    try:
        placed = rec.with_context(show_address=True).name_get()[0][1] or ''
    except Exception:
        return ''
    # The first line is the name, which the caller already has.
    return _tidy(' '.join(placed.splitlines()[1:]))


def placed_label(env, model, rid):
    """``Name — street, zip city (province, country)``, or just the name."""
    if env is None or not model or not rid or model not in env:
        return ''
    try:
        rec = env[model].sudo().browse(int(rid))
        if not rec.exists():
            return ''
        name = ' '.join((rec.display_name or '').split())
    except Exception:
        return ''
    if not name:
        return ''
    where = where_it_is(rec)
    label = '%s — %s' % (name, where) if where else name
    return label[:_MAX] + '…' if len(label) > _MAX else label
