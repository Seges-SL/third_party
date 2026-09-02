# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.465: strip domain_knowledge_ prefix from nucleus context codes."""
import logging
import re

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_DOMAIN_RENAMES = {
    'domain_knowledge_partners': 'partners',
    'domain_knowledge_invoice_concepts': 'invoice_concepts',
    'domain_knowledge_account': 'account',
    'domain_knowledge_cost_accounting': 'cost_accounting',
    'domain_knowledge_filters': 'filters',
    'domain_knowledge_geography': 'geography',
    'domain_knowledge_dates': 'dates',
    'domain_knowledge_email': 'email',
}

_AGENT_FIELDS = (
    'default_context_codes',
    'required_context_codes',
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    Context = env['ai.context'].with_context(
        active_test=False,
        skip_hardcoded_restrictions=True,
    )
    _rename_domain_codes(Context)
    _unlink_prefixed_discovery(Context)
    _rewrite_agent_tokens(env)
    if hasattr(Context, '_unlink_retired_factory_discovery'):
        retired = Context._unlink_retired_factory_discovery()
        _logger.info(
            'pns_ai_mcp 3.1.465: retired factory discovery=%s', retired,
        )


def _rename_domain_codes(Context):
    for old, new in _DOMAIN_RENAMES.items():
        src = Context.search([('code', '=', old)], limit=1)
        if not src:
            continue
        if src.owner_id:
            _logger.info('pns_ai_mcp 3.1.465: keep user-owned %s', old)
            continue
        dst = Context.search([('code', '=', new)], limit=1)
        if dst and dst.id != src.id:
            src.unlink()
            _logger.info(
                'pns_ai_mcp 3.1.465: unlinked leftover %s (kept %s)',
                old, new,
            )
            continue
        src.write({'code': new})
        _logger.info('pns_ai_mcp 3.1.465: renamed %s → %s', old, new)


def _unlink_prefixed_discovery(Context):
    rows = Context.search([
        ('context_type', '=', 'discovery'),
        ('code', '=like', 'discovery_domain_knowledge_%'),
    ])
    stale = rows.filtered(lambda rec: not rec.owner_id)
    if stale:
        codes = stale.mapped('code')
        stale.unlink()
        _logger.info(
            'pns_ai_mcp 3.1.465: unlinked prefixed discovery %s', codes,
        )


def _rewrite_agent_tokens(env):
    if 'ai.agent' not in env:
        return
    mapping = dict(_DOMAIN_RENAMES)
    pattern = re.compile(
        r'\b(?:%s)\b' % '|'.join(
            re.escape(k) for k in sorted(mapping, key=len, reverse=True)
        ),
    )
    Agent = env['ai.agent'].sudo().with_context(active_test=False)
    for agent in Agent.search([]):
        vals = {}
        for field in _AGENT_FIELDS:
            if field not in agent._fields:
                continue
            blob = agent[field] or ''
            if not blob:
                continue
            rewritten = pattern.sub(lambda m: mapping[m.group(0)], blob)
            if rewritten != blob:
                vals[field] = rewritten
        if vals:
            agent.write(vals)
            _logger.info(
                'pns_ai_mcp 3.1.465: rewrote tokens on agent %s',
                agent.code,
            )
