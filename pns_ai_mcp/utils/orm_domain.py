# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""ORM domain helpers (shape only — no business literals)."""
from __future__ import annotations


def alias_name_leaves(domain, rec_name, has_name_field=False):
    """Rewrite ``('name', op, val)`` to ``(rec_name, op, val)`` when the model
    has no ``name`` field. Leaves ``name.foo`` and non-list domains untouched.
    """
    if has_name_field or not rec_name:
        return domain
    if not isinstance(domain, (list, tuple)):
        return domain
    out = []
    for token in domain:
        if (
            isinstance(token, (list, tuple))
            and len(token) >= 3
            and token[0] == 'name'
        ):
            leaf = list(token)
            leaf[0] = rec_name
            out.append(type(token)(leaf) if not isinstance(token, tuple) else tuple(leaf))
        else:
            out.append(token)
    return out


def is_neutral_locale_value(val):
    return val in (False, None, '')


def is_spoken_locale_value(val):
    return isinstance(val, str) and bool(val.strip())


def is_locale_eq_leaf(token):
    return (
        isinstance(token, (list, tuple))
        and len(token) >= 3
        and token[0] == 'locale'
        and token[1] == '='
    )


def is_my_locale_or_triple(domain, index):
    """True when ``domain[index:index+3]`` is ``'|', neutral, spoken`` (either order).

    ``'|', (locale,=,False), (locale,=,'')`` is *No locale*, not My language.
    """
    if not isinstance(domain, (list, tuple)) or index + 2 >= len(domain):
        return False
    if domain[index] != '|':
        return False
    left = domain[index + 1]
    right = domain[index + 2]
    if not (is_locale_eq_leaf(left) and is_locale_eq_leaf(right)):
        return False
    a, b = left[2], right[2]
    return (
        (is_neutral_locale_value(a) and is_spoken_locale_value(b))
        or (is_spoken_locale_value(a) and is_neutral_locale_value(b))
    )


def is_my_locale_or_quad(domain, index):
    """True when ``domain[index:index+5]`` is ``'|', '|', n, n, spoken``.

    Matches ``my_locale_domain()`` (NULL + empty + lang).
    """
    if not isinstance(domain, (list, tuple)) or index + 4 >= len(domain):
        return False
    if domain[index] != '|' or domain[index + 1] != '|':
        return False
    leaves = domain[index + 2:index + 5]
    if not all(is_locale_eq_leaf(tok) for tok in leaves):
        return False
    vals = [tok[2] for tok in leaves]
    neutrals = sum(1 for val in vals if is_neutral_locale_value(val))
    spokens = sum(1 for val in vals if is_spoken_locale_value(val))
    return neutrals == 2 and spokens == 1


def domain_has_my_locale_filter(domain):
    """True when the search-view 'My language' filter chip is present."""
    if not isinstance(domain, (list, tuple)):
        return False
    i = 0
    while i < len(domain):
        if is_my_locale_or_quad(domain, i) or is_my_locale_or_triple(domain, i):
            return True
        i += 1
    return False


def domain_arity_balance(domain):
    """Return the Odoo prefix-domain balance (0 = complete/valid)."""
    if not isinstance(domain, (list, tuple)):
        return 0
    expected = 1
    for token in domain:
        if token in ('&', '|'):
            expected += 1
        elif token != '!':
            expected -= 1
    return expected


def drop_redundant_unary_ops(domain):
    """Drop leading ``&``/``|`` that only wrap one complete expression.

    After stripping a filter, domains like ``['&', (active,=,True)]`` are left
    syntactically invalid (unary AND). Unwrap them.
    """
    if not isinstance(domain, (list, tuple)):
        return domain
    out = list(domain)
    while out and out[0] in ('&', '|') and domain_arity_balance(out[1:]) == 0:
        out = out[1:]
    return out


def strip_my_locale_filter(domain):
    """Remove the 'My language' OR-triple from a domain without leaving junk.

    Odoo ANDs action domain + filter as::

        ['&', '|', (locale,=,False), (locale,=,lang), (context_type,=,discover)]

    Stripping only the ``'|', locale, locale`` triple would leave a dangling
    unary ``'&'`` and crash ``normalize_domain``. Drop that ``'&'`` too.
    """
    if not isinstance(domain, (list, tuple)):
        return domain
    cleaned = []
    i = 0
    while i < len(domain):
        if is_my_locale_or_quad(domain, i):
            i += 5
            if cleaned and cleaned[-1] == '&':
                cleaned.pop()
            continue
        if is_my_locale_or_triple(domain, i):
            i += 3
            if cleaned and cleaned[-1] == '&':
                cleaned.pop()
            continue
        cleaned.append(domain[i])
        i += 1
    return drop_redundant_unary_ops(cleaned)


def domain_is_odoo_prefix_ok(domain):
    """True when Odoo ``normalize_domain`` would accept ``domain``.

    A naive arity of 0 is not enough: if a complete expression is followed
    by extra ``|``/leaves, Odoo inserts an implicit ``&`` and then the
    leftover OR-tree is short one operand.
    """
    if not isinstance(domain, (list, tuple)):
        return True
    expected = 1
    for token in domain:
        if expected == 0:
            expected = 1
        if token in ('&', '|'):
            expected += 1
        elif token != '!':
            expected -= 1
    return expected == 0


def non_locale_leaves(domain):
    """Complete non-locale leaves (skip ``(1, '=', 1)`` no-ops)."""
    if not isinstance(domain, (list, tuple)):
        return []
    out = []
    for token in domain:
        if token in ('&', '|', '!'):
            continue
        if not isinstance(token, (list, tuple)) or len(token) < 3:
            continue
        if is_locale_eq_leaf(token):
            continue
        if token[0] == 1:
            continue
        out.append(token)
    return out


def rewrite_my_locale_domain(domain, user_lang):
    """Replace the search-view chip with NULL/empty/lang. Recover if broken."""
    cleaned = strip_my_locale_filter(domain)
    rewritten = and_join(my_locale_domain(user_lang), cleaned)
    if domain_is_odoo_prefix_ok(rewritten):
        return rewritten
    return and_join(my_locale_domain(user_lang), non_locale_leaves(domain))


def and_join(left, right):
    """Prefix-AND two domains. An empty side is dropped."""
    left = list(left or [])
    right = list(right or [])
    if not left:
        return right
    if not right:
        return left
    return ['&'] + left + right


def my_locale_domain(user_lang):
    """Neutral rows (NULL/empty) plus the spoken locale."""
    lang = (user_lang or '').strip() or 'en_US'
    return [
        '|', '|',
        ('locale', '=', False),
        ('locale', '=', ''),
        ('locale', '=', lang),
    ]
