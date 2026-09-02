# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Single source of truth for ``ai.context`` composition roles (``context_type``).

Every inject / assemble / agent-link / listing decision MUST key off these
names instead of re-listing literal tuples like ``('core', 'discovery')``. That
way adding or changing a role can't silently leak ``discovery`` (routing
metadata, an *index* — never prose) into the LLM prompt or onto an agent.

Roles:
    core       Always-on base prompt. Injected; not hand-composed onto agents.
    domain     On-demand knowledge body. Injected (turn-scoped) + agent-composable.
    locale     Linguistic glue (glossary/terms). Injected; internal, not MCP-listed.
    discovery  Routing index (target_kind + target + triggers). NEVER injected,
               NEVER linked to an agent — the engine reads it as structure
               (domain pack or short api_call hint).
"""
from __future__ import annotations

CORE = 'core'
DOMAIN = 'domain'
LOCALE = 'locale'
DISCOVERY = 'discovery'

#: All valid roles (Selection order on the field).
ALL_TYPES = (CORE, DOMAIN, LOCALE, DISCOVERY)

#: Selection pairs: key = label = token. Never a translated word (Domain/Locale
#: collide with other field labels in ir.translation).
TYPE_SELECTION = [(token, token) for token in ALL_TYPES]

#: Roles whose CONTENT is assembled into the prompt. ``discovery`` is an index,
#: never prose, so it is deliberately absent here.
INJECTABLE_TYPES = (CORE, DOMAIN, LOCALE)

#: Roles advertised via MCP ``prompts``/``resources`` listings (the
#: user-selectable knowledge). ``locale`` is internal glue; ``discovery`` is
#: routing — both excluded.
MCP_LISTABLE_TYPES = (CORE, DOMAIN)

#: Roles that are NEVER hand-composed onto an agent: ``core`` is the always-on
#: base and ``discovery`` is engine-consumed routing.
AGENT_LINK_EXCLUDED_TYPES = (CORE, DISCOVERY)


def is_injectable(context_type) -> bool:
    """True when a role's content is assembled into the prompt."""
    return context_type in INJECTABLE_TYPES


def is_discovery(context_type) -> bool:
    """True for the routing-index role (never injected, never agent-linked)."""
    return context_type == DISCOVERY


def canonical_type(tipo, *, discovery_folder=False, is_system=False):
    """Resolve a factory ``tipo`` to a ``context_type`` token.

    Unknown values fall back to ``core`` when the file lives under ``core/``
    (or ``system/``), else ``domain``. The ``discovery/`` folder always wins.
    """
    raw = (tipo or '').strip().lower()
    if discovery_folder or raw == DISCOVERY:
        return DISCOVERY
    if raw in ALL_TYPES:
        return raw
    if is_system:
        return CORE
    return DOMAIN


def is_agent_composable(context_type) -> bool:
    """True when a user may hand-link the role onto an agent."""
    return context_type not in AGENT_LINK_EXCLUDED_TYPES


def canonical_discovery_code(code):
    """Rewrite leftover ``disc_`` prefix to ``discovery_``.

    ``discovery_*`` is already canonical. Other codes are unchanged.
    """
    raw = (code or '').strip()
    if raw.startswith('discovery_'):
        return raw
    if raw.startswith('disc_'):
        return 'discovery_' + raw[5:]
    return raw
