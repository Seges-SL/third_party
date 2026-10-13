# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""What the user attached earlier in a conversation, kept as text.

A file's text reaches the model only in the turn it is attached. Like the
rows of a table, the text stays on the session and the next turns get a
short note instead. The model reads the part it needs from the sandbox with
``read_document`` and gets it back; the user does not see it.

A document is ``{'name': str, 'pages': [str]}``. A PDF has one entry per
page (an empty page included, so page 3 stays the third); any other file
has one. A photo whose point is its text (a ticket, a letter) is kept the
same way, with the ``checksum`` of its file so it is not sent again as a
picture.
"""
import re

KEPT = 5
MAX_CHARS = 2000000
READ_CHARS = 8000
PAGE_MARK = '=== PAGE %d ==='
_PAGE_MARK = re.compile(r'^\s*=== PAGE (\d+) ===\s*$', re.MULTILINE)


def clean(documents):
    """Only well-formed documents, in order."""
    out = []
    for doc in documents or []:
        if not isinstance(doc, dict):
            continue
        name = doc.get('name')
        pages = doc.get('pages')
        if not name or not isinstance(pages, list):
            continue
        item = {
            'name': str(name),
            'pages': [page if isinstance(page, str) else '' for page in pages],
        }
        if isinstance(doc.get('checksum'), str) and doc['checksum']:
            item['checksum'] = doc['checksum']
        out.append(item)
    return out


def checksums(documents):
    """Checksums of the files kept as text: their pictures need not be sent again."""
    return {doc['checksum'] for doc in clean(documents) if doc.get('checksum')}


def size(doc):
    return sum(len(page) for page in doc['pages'])


def merge(documents, new, kept=KEPT, max_chars=MAX_CHARS):
    """Old documents plus the new ones. A new one replaces the same name.

    The oldest go first when there are more than ``kept`` or more than
    ``max_chars`` of text.
    """
    new = [doc for doc in clean(new) if any(page.strip() for page in doc['pages'])]
    names = {doc['name'] for doc in new}
    out = [doc for doc in clean(documents) if doc['name'] not in names] + new
    out = out[-kept:] if kept > 0 else []
    while out and sum(size(doc) for doc in out) > max_chars:
        out.pop(0)
    return out


def note(documents):
    """The block the model reads in place of the text. Empty with no documents."""
    documents = clean(documents)
    if not documents:
        return ''
    lines = ['[Earlier attachments in this conversation. Their text is not in this message.]']
    for doc in documents:
        count = len(doc['pages'])
        lines.append('- %s (%d %s)' % (doc['name'], count, 'page' if count == 1 else 'pages'))
    first = documents[-1]['name']
    lines.append(
        "To read one, run relaxaicode with result = read_document(%r, page=1) "
        "for a page, or result = read_document(%r, find='some words') for the "
        "pages that contain them. The text comes back to you, not to the user. "
        "Then answer in prose." % (first, first)
    )
    return '\n'.join(lines)


def _pick(documents, name):
    wanted = (name or '').strip()
    for doc in documents:
        if doc['name'] == wanted:
            return doc
    folded = wanted.casefold()
    for doc in documents:
        if doc['name'].casefold() == folded:
            return doc
    found = [doc for doc in documents if folded and folded in doc['name'].casefold()]
    return found[0] if len(found) == 1 else None


def _page_block(doc, index):
    return '%s, page %d of %d:\n%s' % (
        doc['name'], index + 1, len(doc['pages']), doc['pages'][index] or '(empty page)',
    )


def read(documents, name, page=None, find=None, budget=READ_CHARS):
    """The text the model asked for, or a sentence saying why there is none."""
    documents = clean(documents)
    if not documents:
        return 'There are no attached documents in this conversation.'
    doc = _pick(documents, name)
    if doc is None:
        return 'No document named %r. Documents: %s.' % (
            name, ', '.join(item['name'] for item in documents),
        )
    count = len(doc['pages'])
    if page is not None:
        try:
            index = int(page) - 1
        except (TypeError, ValueError):
            index = -1
        if not 0 <= index < count:
            return '%s has %d %s.' % (doc['name'], count, 'page' if count == 1 else 'pages')
        return _page_block(doc, index)[:budget]
    if find:
        folded = str(find).casefold()
        hits = [i for i, text in enumerate(doc['pages']) if folded in text.casefold()]
        if not hits:
            return 'No page of %s contains %r.' % (doc['name'], find)
        indexes = hits
    else:
        indexes = range(count)
    out = '\n\n'.join(_page_block(doc, i) for i in indexes)
    return out[:budget]


def split_pages(text, count):
    """A transcription of ``count`` pages, cut at the page marks.

    Without marks the whole text is one page.
    """
    text = (text or '').strip()
    if not text:
        return []
    marks = list(_PAGE_MARK.finditer(text))
    if not marks:
        return [text]
    pages = [''] * count
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        number = int(mark.group(1))
        if 1 <= number <= count:
            body = text[mark.end():end].strip()
            pages[number - 1] = (pages[number - 1] + '\n' + body).strip()
    return pages
