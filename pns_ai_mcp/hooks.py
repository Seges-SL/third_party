# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Install / uninstall / factory-knowledge re-seed for pns_ai_mcp.

- Install: factory knowledge + first-install shells (providers, APIs,
  whitelist, ICP).
- Reinstall / ``-u``: ``maybe_sync_factory_knowledge`` (version stamp)
  reseeds this addon's factory contexts and system skills. User-owned
  rows stay.
- Uninstall: drop factory rows of this module.

One-shot leftover wipes and translation overwrites live in versioned
``migrations/``, not here.
"""

from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

# Stamp is every installed module that ships ai/contexts or ai/skills
# (see knowledge_stamp.module_has_ai_knowledge). No fixed name list.
ICP_FACTORY_STAMP = 'pns_ai.factory_knowledge_stamp'


def post_init_hook(*args):
    """First install: factory knowledge, then instance shells.

    Signature: Odoo 14 ``(cr, registry)`` · Odoo 17+ ``(env,)``.
    """
    from odoo.release import version_info

    if version_info[0] >= 17:
        env = args[0]
    else:
        cr, registry = args
        env = api.Environment(cr, SUPERUSER_ID, {})

    sync_factory_knowledge(env, reason='post_init')
    # After knowledge sync: API discovery rows exist for the orphan link.
    _load_first_install_data(env)


def _load_first_install_data(env):
    """LLM / API / whitelist / ICP shells. ``post_init`` only — never on ``-u``.

    These XML files stay off the manifest ``data:`` list on purpose: a new
    file there would create xmlids on upgrade of an already-installed engine.
    """
    import inspect
    import os
    from odoo.modules.module import get_module_path
    from odoo.tools import convert_file

    base = get_module_path('pns_ai_mcp')
    if not base:
        _logger.warning('MCP: first-install data skipped (module path missing)')
        return
    files = (
        'data/ai_provider_data.xml',
        'data/external_server_openapi_data.xml',
        'data/url_whitelist_data.xml',
        'data/instance_defaults_data.xml',
    )
    sig = inspect.signature(convert_file)
    params = sig.parameters
    first = next(iter(params))
    env_or_cr = env if first == 'env' else env.cr
    for rel in files:
        path = os.path.join(base, rel)
        if not os.path.isfile(path):
            _logger.warning('MCP: first-install data missing %s', rel)
            continue
        kwargs = {
            'mode': 'init',
            'noupdate': True,
        }
        if 'kind' in params:
            kwargs['kind'] = 'data'
        if 'pathname' in params:
            kwargs['pathname'] = path
        try:
            convert_file(env_or_cr, 'pns_ai_mcp', rel, {}, **kwargs)
            _logger.info('MCP: loaded first-install data %s', rel)
        except Exception:
            _logger.warning(
                'MCP: first-install data failed %s', rel, exc_info=True,
            )
    try:
        if 'ai.api.server' in env:
            env['ai.api.server']._link_orphan_api_discovery()
    except Exception:
        _logger.warning(
            'MCP: first-install API discovery link failed', exc_info=True,
        )


def uninstall_hook(cr, registry):
    """Remove factory knowledge owned by this module (not user-owned rows)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    uninstall_factory_knowledge_for_module(env, 'pns_ai_mcp')


def uninstall_factory_knowledge_for_module(env, module_name):
    """Delete factory contexts/skills with ``source_module == module_name``.

    Rows with ``owner_id`` (user knowledge) are kept. Safe to call from any
    knowledge-pack uninstall hook.
    """
    if not module_name:
        return
    if 'ai.context' in env:
        try:
            ctx = env['ai.context'].with_context(
                skip_hardcoded_restrictions=True,
                tracking_disable=True,
            ).search([
                ('source_module', '=', module_name),
                ('owner_id', '=', False),
            ])
            n = len(ctx)
            if ctx:
                ctx.unlink()
            _logger.info(
                'MCP: uninstall factory contexts for %s: %s removed',
                module_name, n,
            )
        except Exception:
            _logger.warning(
                'MCP: uninstall contexts for %s failed', module_name,
                exc_info=True,
            )
    if 'ai.skill' in env:
        try:
            skill = env['ai.skill'].with_context(
                skip_hardcoded_restrictions=True,
                tracking_disable=True,
            ).search([
                ('source_module', '=', module_name),
                ('owner_id', '=', False),
            ])
            n = len(skill)
            if skill:
                skill.unlink()
            _logger.info(
                'MCP: uninstall factory skills for %s: %s removed',
                module_name, n,
            )
        except Exception:
            _logger.warning(
                'MCP: uninstall skills for %s failed', module_name,
                exc_info=True,
            )


def sync_factory_knowledge(env, reason='manual'):
    """Re-seed this addon's factory knowledge; keep user-owned rows.

    Contexts and system skills of ``pns_ai_mcp`` only. The ``custom/``
    drawer and neighbor packs seed themselves. ``owner_id`` rows are
    skipped inside the import helpers. Idempotent.
    """
    if 'ai.context' not in env or 'ai.skill' not in env:
        return None
    ctx_report = None
    skill_stats = None
    try:
        ctx_report = env['ai.context'].with_context(
            skip_hardcoded_restrictions=True,
        )._import_all_from_module(
            replace_existing=True, module_name='pns_ai_mcp',
        )
        _logger.info(
            'MCP: factory contexts synced (%s): %s', reason, ctx_report,
        )
    except Exception:
        _logger.warning(
            'MCP: factory context sync failed (%s)', reason, exc_info=True,
        )
    try:
        skill_stats = env['ai.skill'].with_context(
            skip_hardcoded_restrictions=True,
        ).import_from_module('pns_ai_mcp', scopes=('system',))
        _logger.info(
            'MCP: factory skills synced (%s): %s', reason, skill_stats,
        )
    except Exception:
        _logger.warning(
            'MCP: factory skill sync failed (%s)', reason, exc_info=True,
        )
    _sync_agent_caches(env)
    _write_factory_stamp(env)
    return {'contexts': ctx_report, 'skills': skill_stats}


def factory_knowledge_stamp(env):
    """Stable stamp of installed modules that ship ``ai/contexts`` or ``ai/skills``."""
    from odoo.modules.module import get_module_path

    from .utils.knowledge_stamp import (
        format_factory_knowledge_stamp,
        module_has_ai_knowledge,
    )

    Module = env['ir.module.module'].sudo()
    pairs = []
    for mod in Module.search([('state', '=', 'installed')]):
        path = get_module_path(mod.name)
        if not path or not module_has_ai_knowledge(path):
            continue
        ver = (mod.latest_version or mod.installed_version or '').strip()
        pairs.append((mod.name, ver))
    return format_factory_knowledge_stamp(pairs)


def maybe_sync_factory_knowledge(env, reason='registry'):
    """Sync when the knowledge-module version stamp changed (e.g. after ``-u``)."""
    if 'ir.config_parameter' not in env or 'ai.context' not in env:
        return False
    try:
        stamp = factory_knowledge_stamp(env)
        ICP = env['ir.config_parameter'].sudo()
        prev = (ICP.get_param(ICP_FACTORY_STAMP, '') or '').strip()
        if prev == stamp and stamp:
            return False
        sync_factory_knowledge(env, reason=reason)
        return True
    except Exception:
        _logger.warning(
            'MCP: maybe_sync_factory_knowledge failed (%s)', reason,
            exc_info=True,
        )
        return False


def _write_factory_stamp(env):
    try:
        stamp = factory_knowledge_stamp(env)
        env['ir.config_parameter'].sudo().set_param(ICP_FACTORY_STAMP, stamp)
    except Exception:
        _logger.warning('MCP: could not persist factory stamp', exc_info=True)


def _sync_agent_caches(env):
    """Refresh composition and cache for every agent."""
    if 'ai.agent' not in env:
        return
    agents = env['ai.agent'].search([])
    for agent in agents:
        try:
            agent._sync_composition_and_cache()
        except Exception:
            _logger.warning(
                'MCP: cache sync failed for agent %s', agent.code, exc_info=True,
            )
