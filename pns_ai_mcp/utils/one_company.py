# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Which companies AI work runs in.

A host with a company switcher (a web screen) puts what the screen ticks
under ``SCREEN_COMPANIES``: the AI sees those, the active one first, like
any other screen. Without it (MCP, a phone, a skill from outside) it is one
company, the user's default one; if that one is archived, the first active
company the user belongs to. Only the user's own active companies
count, whatever the screen asks. Record rules hide the rest.
"""

SCREEN_COMPANIES = 'ai_screen_company_ids'


def _mine(env):
    companies = env.user.company_ids
    if 'active' in env['res.company']._fields:
        companies = companies.filtered('active')
    return companies


def the_company(env):
    """The default company the AI works in for ``env.user`` (empty if none)."""
    user = env.user
    Company = env['res.company']
    if 'active' not in Company._fields:
        return user.company_id
    if user.company_id.active:
        return user.company_id
    return user.company_ids.filtered('active')[:1]


def screen_ids(requested):
    """Company ids as the screen sent them, in order, without repeats."""
    ids = []
    for value in requested or ():
        try:
            cid = int(value)
        except (TypeError, ValueError):
            continue
        if cid > 0 and cid not in ids:
            ids.append(cid)
    return ids


def ai_companies(env, requested=None):
    """The companies the AI works in, the active one first.

    ``requested`` is what a screen asked for; ``None`` reads it from
    ``env.context``. Ids the user does not belong to are dropped; if none is
    left, it is the default company.
    """
    if requested is None:
        requested = env.context.get(SCREEN_COMPANIES)
    wanted = screen_ids(requested)
    if wanted:
        mine = set(_mine(env).ids)
        kept = [cid for cid in wanted if cid in mine]
        if kept:
            return env['res.company'].browse(kept)
    return the_company(env)


def one_company_context(env, context=None, requested=None):
    """``context`` (or ``env.context``) narrowed to ``ai_companies``."""
    ctx = dict(env.context if context is None else context or {})
    if requested is None:
        requested = ctx.get(SCREEN_COMPANIES)
    wanted = screen_ids(requested)
    if wanted:
        ctx[SCREEN_COMPANIES] = wanted
    else:
        ctx.pop(SCREEN_COMPANIES, None)
    companies = ai_companies(env, wanted)
    if companies:
        ctx['allowed_company_ids'] = companies.ids
    return ctx
