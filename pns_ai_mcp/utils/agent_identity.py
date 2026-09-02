# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Host-resolved agent display name and vendor. Facts only — no greeting policy.

Owning modules register constants per ``ai.agent.code``. The engine does not
keep a catalogue of product brands. Greeting / off-topic voice lives in each
agent's optional ``self_*`` pack, not here.
"""
import re

IDENTITY_HEADING = '## Product name (host, resolved)'
AUTHORSHIP_HEADING = '## Vendor (host, resolved)'

# Retired generic slot. Identity packs are ``self_<last_token>`` per agent.
RETIRED_SELF_CODE = 'self'
RETIRED_SELF_ALIAS = 'self_retired'
# Locale clones of the old generic slot (self_es_ES, self_en_US, self_ES).
_RETIRED_SELF_LOCALE_RE = re.compile(
    r'^self_[a-zA-Z]{2}(?:[_-][a-zA-Z]{2})?$'
)


def parse_pin_tokens(raw):
    """Split a CSV/newline pin or pull list, preserving first-seen order."""
    tokens = []
    seen = set()
    for part in (raw or '').replace(',', '\n').replace(';', '\n').split('\n'):
        token = part.strip()
        if token and token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


def drop_pin_tokens(raw, drops):
    drop = set(drops or ())
    return '\n'.join(
        token for token in parse_pin_tokens(raw) if token not in drop
    )


def ensure_pin_token(raw, token):
    tokens = parse_pin_tokens(raw)
    if token and token not in tokens:
        tokens.append(token)
    return '\n'.join(tokens)


def own_self_pack_code(agent_code):
    """Canonical identity pack: ``pns_ai_chatboo`` → ``self_chatboo``."""
    token = (agent_code or '').strip().rsplit('_', 1)[-1]
    if not token:
        return ''
    return 'self_%s' % token


def is_retired_self_pack_code(context_code):
    """True for the generic ``self`` slot and its locale clones, not ``self_mcp``."""
    code = (context_code or '').strip()
    if code in (RETIRED_SELF_CODE, RETIRED_SELF_ALIAS):
        return True
    return bool(_RETIRED_SELF_LOCALE_RE.match(code))


def is_retired_self_source_path(rel_path):
    """True for leftover files under ``contexts/domain/self/``."""
    path = (rel_path or '').replace('\\', '/').strip()
    return (
        path.startswith('contexts/domain/self/')
        or path.startswith('domain/self/')
        or '/domain/self/' in path
    )


def is_identity_pack_code(context_code):
    code = (context_code or '').strip()
    return code == RETIRED_SELF_CODE or code.startswith('self_')


def is_foreign_identity_pack(agent_code, context_code):
    """True for retired ``self`` or another agent's ``self_*`` pack."""
    code = (context_code or '').strip()
    if not is_identity_pack_code(code):
        return False
    return code != own_self_pack_code(agent_code)


def foreign_identity_on_demand_message(agent_code, context_code):
    """Error text when a client asks for another agent's identity pack."""
    if not is_foreign_identity_pack(agent_code, context_code):
        return None
    return (
        'Identity pack %s belongs to another agent. Identity is already in '
        'system_prompt; do not load another agent\'s self pack.'
    ) % (context_code or '')


def first_identity_text(*values):
    """First non-empty stripped string among identity candidates."""
    for value in values:
        if value is None:
            continue
        text = value.strip() if isinstance(value, str) else str(value).strip()
        if text:
            return text
    return ''


def format_product_name_block(product_name):
    name = first_identity_text(product_name)
    if not name:
        return ''
    return (
        '%s\nYou present yourself as **%s**. This name was resolved by the '
        'host (owning-module constants, then identity-pack metadata, then '
        'the agent record).\n'
    ) % (IDENTITY_HEADING, name)


def format_vendor_block(vendor, vendor_place=None, vendor_years=None, vendor_url=None):
    name = (vendor or '').strip()
    if not name:
        return ''
    bits = [name]
    place = (vendor_place or '').strip()
    years = (vendor_years or '').strip()
    url = (vendor_url or '').strip()
    if place:
        bits.append(place)
    if years:
        bits.append(years)
    line = ', '.join(bits)
    if url:
        line = '%s — %s' % (line, url)
    return (
        '%s\nThis knowledge layer is a product of **%s**.\n'
        'Do not invent another author.\n'
    ) % (AUTHORSHIP_HEADING, line)


def _prepend_heading_block(prompt, heading, block):
    text = prompt or ''
    body = (block or '').strip()
    if not body or not heading:
        return text
    if heading in text:
        return text
    if not text:
        return body
    return '%s\n\n%s' % (body, text)


def apply_resolved_identity(
    prompt,
    product_name=None,
    vendor=None,
    vendor_place=None,
    vendor_years=None,
    vendor_url=None,
    display_name=None,
):
    """Prepend at most one name block and one vendor block (vendor first).

    ``display_name`` is a read alias of ``product_name``.
    """
    text = _prepend_heading_block(
        prompt or '',
        IDENTITY_HEADING,
        format_product_name_block(product_name or display_name),
    )
    return _prepend_heading_block(
        text,
        AUTHORSHIP_HEADING,
        format_vendor_block(
            vendor,
            vendor_place=vendor_place,
            vendor_years=vendor_years,
            vendor_url=vendor_url,
        ),
    )
