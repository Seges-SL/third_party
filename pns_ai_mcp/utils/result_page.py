# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""A result that is also a page in its own browser tab.

One key, one meaning. ``page_url`` is a link: the chat shows it, the click
opens the page. Any module may publish a sandbox helper that returns such a
url; it sets this key and changes nothing in the engine. The engine never
names the module that made the page, and never decides what is inside it.

``map_url`` / ``pins_url`` are the older spelling of the same fact. They are
read so a pack or a stored turn written before the key existed still paints.
"""
from __future__ import annotations

# Read order. Engine contract, not a product catalogue: a module that wants
# a page sets ``page_url`` and touches nothing here.
PAGE_URL_KEYS = ('page_url', 'map_url', 'pins_url')
# Mutable bag the engine plants on the turn context. A helper that was
# asked for a page with no rows stores a fulfill() here; when rows arrive
# the engine calls it. No module name.
PAGE_REQUEST_KEY = 'page_request'


def page_url_on_result(payload):
    """First usable page url on ``payload``, or '' when there is none."""
    if not isinstance(payload, dict):
        return ''
    for key in PAGE_URL_KEYS:
        value = payload.get(key)
        if not isinstance(value, str):
            continue
        href = value.strip()
        if href.startswith('http') or href.startswith('/'):
            return href
    return ''


def has_page_url(payload):
    """True when this payload carries a page the user can open."""
    return bool(page_url_on_result(payload))


def rows_on_payload(payload):
    """Row list on ``payload``, or []. Groups / tables are flattened."""
    blocks = blocks_on_payload(payload)
    out = []
    for block in blocks:
        out.extend(block.get('data') or [])
    return out


def blocks_on_payload(payload):
    """Titled tables as they came. Different tables stay apart."""
    if not isinstance(payload, dict):
        return []
    out = []
    for key in ('tables', 'groups', 'sections'):
        blocks = payload.get(key)
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            rows = block.get('data')
            if rows is None:
                rows = block.get('rows')
            if not (isinstance(rows, list) and rows):
                continue
            title = (
                block.get('title') or block.get('summary')
                or block.get('name') or ''
            )
            out.append({'title': title, 'data': list(rows)})
        if out:
            return out
    data = payload.get('data')
    if isinstance(data, list) and data:
        title = payload.get('title') or payload.get('summary') or ''
        return [{'title': title, 'data': list(data)}]
    return []


def note_page_wanted(env):
    """This turn asked for a page. The chat will show only the card."""
    ctx = getattr(env, 'context', None) or {}
    req = ctx.get(PAGE_REQUEST_KEY)
    if not isinstance(req, dict):
        return False
    req['wanted'] = True
    return True


def page_wanted(env):
    """True when this turn asked for a page, not a chat report."""
    ctx = getattr(env, 'context', None) or {}
    req = ctx.get(PAGE_REQUEST_KEY)
    return isinstance(req, dict) and bool(req.get('wanted'))


def note_page_waiting(env, fulfill):
    """Remember that a page was asked for and rows have not arrived yet."""
    ctx = getattr(env, 'context', None) or {}
    req = ctx.get(PAGE_REQUEST_KEY)
    if not isinstance(req, dict) or not callable(fulfill):
        return False
    req['waiting'] = True
    req['fulfill'] = fulfill
    return True


def note_page_untitled(env, retitle):
    """A page went out with no title. The result may name it afterwards.

    ``retitle(env, href, title)`` is called once, with the title the result
    carries. No module name.
    """
    ctx = getattr(env, 'context', None) or {}
    req = ctx.get(PAGE_REQUEST_KEY)
    if not isinstance(req, dict) or not callable(retitle):
        return False
    req['retitle'] = retitle
    return True


def title_on_payload(payload, fallback=''):
    """The name the result gives itself, else ``fallback``. Never invented."""
    candidates = []
    if isinstance(payload, dict):
        candidates = [payload.get('title'), payload.get('summary')]
    candidates.append(fallback)
    for candidate in candidates:
        text = ' '.join(str(candidate or '').split())
        if text:
            return text
    return ''


def title_untitled_page(env, payload, fallback=''):
    """Give the untitled page of this turn the name its result carries."""
    if not has_page_url(payload):
        return False
    ctx = getattr(env, 'context', None) or {}
    req = ctx.get(PAGE_REQUEST_KEY)
    if not isinstance(req, dict):
        return False
    fn = req.get('retitle')
    title = title_on_payload(payload, fallback)
    if not callable(fn) or not title:
        return False
    req['retitle'] = None
    try:
        fn(env, page_url_on_result(payload), title)
    except Exception:
        return False
    return True


def mark_page_only(payload):
    """The bubble is the card. No table, no report, no copied HTML."""
    if not isinstance(payload, dict) or not has_page_url(payload):
        return payload
    payload['__page_only__'] = True
    return payload


def fulfill_waiting_page(env, payload):
    """If a page is waiting and ``payload`` has rows, lay it out now."""
    if not isinstance(payload, dict) or has_page_url(payload):
        if page_wanted(env):
            mark_page_only(payload)
        return payload
    blocks = blocks_on_payload(payload)
    if not blocks:
        return payload
    ctx = getattr(env, 'context', None) or {}
    req = ctx.get(PAGE_REQUEST_KEY)
    if not isinstance(req, dict) or not req.get('waiting'):
        return payload
    fn = req.get('fulfill')
    req['waiting'] = False
    req['fulfill'] = None
    if not callable(fn):
        return payload
    try:
        href = fn(env, blocks)
    except Exception:
        href = ''
    if isinstance(href, str):
        href = href.strip()
        if href.startswith('http') or href.startswith('/'):
            payload['page_url'] = href
            if req.get('wanted') or page_wanted(env):
                mark_page_only(payload)
    return payload
