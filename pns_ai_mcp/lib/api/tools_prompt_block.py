# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Render the external-API catalogue injected into the agent prompt.

No Odoo, no vendor names. Inactive rows are skipped (same contract as
Odoo ``active_test``): archived servers stay in the DB, they just do not
appear here.
"""
from __future__ import annotations

TOOLS_PROMPT_HEADER = (
    'External API servers callable via propose_safe_operations → api_call. '
    'Use ONLY these exact server codes and tool names; never invent tools '
    '(e.g. do NOT use search_read/list_tools unless listed below). '
    'Server codes are instance-specific (they may have suffixes); there is '
    'no shorter canonical code. When the user names a service, match a '
    'listed row by code or name and use that code verbatim — do not invent '
    'a shorter code. Relaxaicode on ai.api.server is rejected; use the '
    'catalogue below and api_call (never search/browse/spec_json to discover '
    'codes or specs — usage_guide is the source). '
    'Only active servers are listed; do not inspect archived/inactive '
    'ai.api.server records (no active_test=False, no browse of unlisted ids). '
    'Prefer each server\'s usage_guide over dumping spec_json or sibling records. '
    'Spoken detection triggers are instance data: propose create on ai.context '
    '(context_type=discovery, discovery_target_kind=api_server, '
    'discovery_target=<exact listed server code>, locale, discovery_triggers). '
    'The server link is resolved from that code.'
)


def format_tool_arg_token(name, schema):
    """Compact arg token: ``body{data}`` when object has nested required keys."""
    if not isinstance(schema, dict):
        return name
    required = schema.get('required') or []
    is_object = (
        schema.get('type') == 'object'
        or schema.get('properties')
        or required
    )
    if is_object and required:
        kids = ','.join(str(k) for k in required[:6])
        return '%s{%s}' % (name, kids)
    return name


def format_tools_prompt_block(servers, max_tools_per_server=40, compact_chunk=24):
    """Return the prompt block, or ``''`` when nothing usable is active.

    ``servers``: iterable of mappings with ``code``, ``name``, ``usage_guide``,
    ``tools`` (list of tool dicts), and optional ``active`` (default True).
    """
    groups = []
    for srv in servers or []:
        if not isinstance(srv, dict):
            continue
        if srv.get('active', True) is False:
            continue
        tools = srv.get('tools') or []
        has_tools = isinstance(tools, list) and tools
        guide = (srv.get('usage_guide') or '').strip()
        if not has_tools and not guide:
            continue
        code = srv.get('code') or '?'
        name = srv.get('name') or code
        lines = ['• server "%s" (%s):' % (code, name)]
        if guide:
            for gline in guide.splitlines():
                lines.append('  ' + gline)
        detailed = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            tname = tool.get('name') or '?'
            if tname != '?':
                detailed.append((tname, tool))
        for tname, tool in detailed[:max_tools_per_server]:
            schema = tool.get('inputSchema') or {}
            props = schema.get('properties') if isinstance(schema, dict) else None
            if isinstance(props, dict):
                args = ', '.join(
                    format_tool_arg_token(k, props.get(k) or {})
                    for k in list(props.keys())[:8]
                )
            else:
                args = ''
            desc = (tool.get('description') or '').strip().splitlines()
            desc = desc[0][:120] if desc else ''
            sig = '%s(%s)' % (tname, args) if args else '%s()' % tname
            lines.append('  - %s' % sig + (' — %s' % desc if desc else ''))
        extra_names = [n for n, _t in detailed[max_tools_per_server:]]
        if extra_names:
            lines.append(
                '  (+ %s more tools, names only — still callable via api_call:)'
                % len(extra_names)
            )
            for i in range(0, len(extra_names), compact_chunk):
                chunk = extra_names[i:i + compact_chunk]
                lines.append('  ' + ', '.join(chunk))
        groups.append('\n'.join(lines))
    if not groups:
        return ''
    return TOOLS_PROMPT_HEADER + '\n\n' + '\n\n'.join(groups)
