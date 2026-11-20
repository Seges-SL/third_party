# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Closed tokens for skill parameter defaults (``{year}``, ``{ytd}``, …).

The legend and the expander share ``skill_param_token_specs``. Unknown
``{names}`` are left as-is. ``{year}-n`` (n = 1, 2, …) is the same
allowlist, not eval. No sudo, no other user's row.
"""
from __future__ import annotations

import re
from datetime import date
from html import escape

# ``{year}-1`` is previous year. ``{year}-01-01`` stays a date fragment.
_YEAR_AGO_RE = re.compile(r'\{year\}-([1-9]\d*)(?!-)')
_TOKEN_RE = re.compile(r'\{([a-z][a-z0-9_]*)\}')


def skill_param_token_specs():
    """``(display, name_or_None, english msgid)``.

    ``name`` is the ``{name}`` expander key. ``None`` is a documented
    pattern expanded by ``_YEAR_AGO_RE``, not a second catalog.
    """
    return (
        ('{year}', 'year', 'Calendar year of today'),
        ('{year}-n', None, 'Calendar year n years ago (n = 1, 2, …)'),
        ('{today}', 'today', 'Today (YYYY-MM-DD)'),
        ('{ytd}', 'ytd', 'From 1 January this year to today (YYYY-MM-DD..YYYY-MM-DD)'),
        ('{user}', 'user', 'Current user name'),
        ('{company}', 'company', 'Current company name'),
        ('{vat}', 'vat', 'Current company tax ID'),
    )


def skill_param_token_names():
    return frozenset(
        name for _display, name, _label in skill_param_token_specs() if name
    )


def skill_param_token_legend_text():
    """Plain legend. Same tokens the expander knows."""
    try:
        from odoo import _
    except ImportError:
        def _(text):
            return text
    lines = [_('In Default you may write:')]
    for display, _name, label in skill_param_token_specs():
        lines.append('%s — %s' % (display, _(label)))
    return '\n'.join(lines)


def skill_param_token_legend_html():
    """Readonly banner above the parameter list."""
    return '<br/>'.join(
        escape(line) for line in skill_param_token_legend_text().split('\n')
    )


# Form views keep this slot; fields_view_get fills it from the same specs.
SKILL_PARAM_TOKEN_LEGEND_SLOT = '__SKILL_PARAM_TOKEN_LEGEND__'


def fill_skill_param_token_legend_arch(arch):
    """Put the legend HTML in the form arch. No field widget."""
    if not arch:
        return arch
    if isinstance(arch, bytes):
        arch = arch.decode('utf-8')
    if SKILL_PARAM_TOKEN_LEGEND_SLOT not in arch:
        return arch
    return arch.replace(SKILL_PARAM_TOKEN_LEGEND_SLOT, skill_param_token_legend_html())


def _plain_attr(record, name):
    """Field value on the asking user's record. Never sudo."""
    if record is None:
        return ''
    try:
        value = getattr(record, name, None)
    except Exception:
        return ''
    if value is None:
        return ''
    return str(value).strip()


def skill_param_token_values(env):
    """Values for the asking user and their current company. No sudo."""
    if env is None:
        return {}
    today = date.today()
    user = getattr(env, 'user', None)
    company = getattr(env, 'company', None)
    ytd_from = date(today.year, 1, 1).isoformat()
    return {
        'year': str(today.year),
        'today': today.isoformat(),
        'ytd': '%s..%s' % (ytd_from, today.isoformat()),
        'user': _plain_attr(user, 'name') or _plain_attr(user, 'login'),
        'company': _plain_attr(company, 'name'),
        'vat': _plain_attr(company, 'vat'),
    }


def expand_skill_param_text(text, env):
    """Replace allowlisted tokens in a default string. Unknown stay."""
    if not isinstance(text, str) or '{' not in text:
        return text
    if env is None:
        return text
    today = date.today()

    def _year_ago(match):
        return str(today.year - int(match.group(1)))

    text = _YEAR_AGO_RE.sub(_year_ago, text)
    allowed = skill_param_token_names()
    values = skill_param_token_values(env)

    def _replace(match):
        name = match.group(1)
        if name not in allowed:
            return match.group(0)
        return values.get(name, '')

    return _TOKEN_RE.sub(_replace, text)


def expand_skill_param_values(params, env):
    """Expand tokens in every string value. Leaves non-strings untouched."""
    if env is None or not params:
        return params
    out = dict(params)
    for key, val in list(out.items()):
        if isinstance(val, str) and '{' in val:
            out[key] = expand_skill_param_text(val, env)
    return out
