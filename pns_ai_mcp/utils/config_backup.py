# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Unified AI configuration backup — export/import the whole ``ai.*`` config.

Purpose
-------
Provide a single portable JSON that captures ALL the configurable state of the
AI engine so an admin can save it before an uninstall/reinstall and restore it
in one click (the "magic button"), and seed a fleet of instances from one file.

Entities covered (business keys used for matching on import):
    - ai.provider            → key: name  (+ ai.provider.model by name, + selected)
    - ai.agent               → key: code  (UPDATE only; agents are module-owned)
    - ai.context             → key: code  (non-core only; core is module-seeded)
    - ai.skill               → key: code  (non-system only; system is module-seeded)
    - ai.api.server          → key: code
    - ai.url.whitelist       → key: domain
    - ai.mcp.user            → key: login (only the API key is restored; group
                                membership stays manual by design)
    - settings               → ir.config_parameter (URL policy, domain index,
                                skill code/command prefixes, slash-hidden skill codes)

Secrets (provider api_key, server auth_token/env_vars) are included only when
``include_secrets=True``. The file then contains third-party credentials in
clear text — treat it as sensitive.

The MCP user key is NOT a plaintext secret: only its SHA-256 hash is stored and
exported. The hash is portable (the same client key keeps validating on the
target instance) and is not usable on its own, so it is always included,
regardless of ``include_secrets``.

Design notes
------------
- Import is idempotent (upsert by business key) and resilient: a bad row never
  aborts the batch; it is collected as an error in the report.
- Relations are wired in a second pass, after every entity exists, so ordering
  between agents/contexts/skills/providers does not matter.
- ``ai.agent`` records are UPDATED, never created: agents are owned by their
  module and re-seeded on (re)install, so restore only reapplies their config
  (failover chain, context/skill links, scalar tuning).
"""

import logging

from odoo import _, fields

from odoo.addons.pns_base.utils import settings_io as sio

from .api_key import normalize_to_hash
from .display_currency import normalize_currency
from .portable_io import export_record_dict, import_vals_from_dict
from .skill_code_prefix import (
    normalize_skill_code_prefix,
    normalize_skill_command_prefix,
)

_logger = logging.getLogger(__name__)

SCHEMA_VERSION = '1.0'
MODULE = 'pns_ai_mcp'
ICP_PREFIX = 'pns_ai_mcp.'
ICP_SKILLS_SLASH_HIDDEN = 'pns_ai_mcp.skills_slash_hidden'

_AGENT_IMPORT_SKIP = {
    'id', 'code', 'origin', 'module_name',
    'cached_content', 'cache_locale', 'cache_updated', 'cache_context_signature',
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _norm_dt(value):
    """Normalize an ISO/‘T’ datetime string to Odoo's ``YYYY-MM-DD HH:MM:SS``."""
    if not value or not isinstance(value, str):
        return value
    v = value.replace('T', ' ').strip()
    # Drop timezone / microseconds if present (keep first 19 chars).
    return v[:19]


def _section():
    return {'created': 0, 'updated': 0, 'skipped': 0}


# ─────────────────────────────────────────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────────────────────────────────────────

def export_config(env, include_secrets=True):
    """Return a portable dict with the whole AI configuration.

    Args:
        env: Odoo environment.
        include_secrets: when True (default) include api keys / tokens.

    Returns:
        dict ready for ``json.dumps`` (schema-versioned).
    """
    import datetime as _dt

    data = {
        'schema_version': SCHEMA_VERSION,
        'exported_at': _dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'include_secrets': bool(include_secrets),
        'providers': _export_providers(env, include_secrets),
        'agents': _export_agents(env),
        'contexts': _export_contexts(env),
        'skills': _export_skills(env),
        'mcp_servers': _export_servers(env, include_secrets),
        'url_whitelists': _export_whitelist(env),
        'mcp_users': _export_users(env, include_secrets),
        'settings': _export_settings(env),
    }
    return data


def _export_providers(env, include_secrets):
    Provider = env['ai.provider'].sudo().with_context(active_test=False)
    out = []
    for p in Provider.search([]):
        d = export_record_dict(p, skip_fields={'id', 'model_name'})
        if not include_secrets:
            d.pop('api_key', None)
        d['models'] = [{'name': m.name} for m in p.available_model_ids]
        d['selected_model'] = p.model_id.name or None
        d['usage_days'] = p.usage_day_ids.to_export_rows()
        out.append(d)
    return out


def _export_agents(env):
    Agent = env['ai.agent'].sudo().with_context(active_test=False)
    Link = env['ai.agent.provider'].sudo().with_context(active_test=False)
    out = []
    for a in Agent.search([]):
        d = export_record_dict(a, skip_fields={
            'id', 'cached_content', 'cache_locale',
            'cache_updated', 'cache_context_signature',
        })
        d['context_codes'] = a.context_ids.mapped('code')
        d['skill_codes'] = a.skill_ids.mapped('code')
        d['failovers'] = [
            {
                'provider': l.provider_id.name,
                'priority': l.priority,
                'active': l.active,
                'llm_idle_timeout': l.llm_idle_timeout,
                'llm_round_timeout': l.llm_round_timeout,
                'skip_sync_fallback': l.skip_sync_fallback,
            }
            for l in Link.search([('agent_id', '=', a.id)])
        ]
        out.append(d)
    return out


def _export_contexts(env):
    # Core contexts are module-seeded and identical after reinstall; exporting
    # them would risk clobbering system prompts on restore. Skip them.
    Ctx = env['ai.context'].sudo().with_context(active_test=False)
    return [
        export_record_dict(c, skip_fields={'id'})
        for c in Ctx.search([('context_type', '!=', 'core')])
    ]


def _export_skills(env):
    # System skills come from module files; only user skills are portable config.
    Skill = env['ai.skill'].sudo().with_context(active_test=False)
    out = []
    for s in Skill.search([('is_system', '=', False)]):
        d = export_record_dict(s, skip_fields={'id', 'show_in_slash'})
        d['agent_codes'] = s.agent_ids.mapped('code')
        d['context_codes'] = s.context_ids.mapped('code')
        out.append(d)
    return out


def _export_servers(env, include_secrets):
    """Dynamic dump of every portable field on ai.api.server (incl. trusted)."""
    Srv = env['ai.api.server'].sudo().with_context(active_test=False)
    out = []
    for s in Srv.search([]):
        row = export_record_dict(s)
        if not include_secrets:
            row['auth_token'] = ''
            row['env_vars'] = '{}'
        out.append(row)
    return out


def _export_whitelist(env):
    W = env['ai.url.whitelist'].sudo().with_context(active_test=False)
    return [export_record_dict(r) for r in W.search([])]


def _export_users(env, include_secrets):
    # The user key is exported as its SHA-256 hash (not a usable secret), so it
    # is always included — ``include_secrets`` does not gate it. Moving the hash
    # keeps the very same client key valid on the target instance.
    del include_secrets
    U = env['ai.mcp.user'].sudo()
    out = []
    for u in U.search([]):
        if not u.login or u.mcp_api_key_state != 'generated':
            continue
        row = {
            'login': u.login,
            'name': u.name or '',
            'mcp_api_key_state': u.mcp_api_key_state,
        }
        try:
            row['is_ai_admin'] = u.user_id.has_group('pns_ai_mcp.group_ai_admin')
            row['is_ai_writer'] = u.user_id.has_group('pns_ai_mcp.group_ai_writer')
            row['is_ai_external_url'] = u.user_id.has_group(
                'pns_ai_mcp.group_ai_external_url')
            row['is_ai_external_api'] = u.user_id.has_group(
                'pns_ai_mcp.group_ai_external_api')
        except Exception:
            pass
        if u.mcp_api_key_hash:
            row['mcp_api_key_hash'] = u.mcp_api_key_hash
            row['mcp_api_key_generated_date'] = (
                fields.Datetime.to_string(u.mcp_api_key_generated_date)
                if u.mcp_api_key_generated_date else None
            )
        out.append(row)
    return out


def _clamp_mcp_settings(values, fields_map=None):
    del fields_map
    if 'display_currency' in values:
        values['display_currency'] = normalize_currency(values.get('display_currency'))
    if 'skill_code_prefix' in values:
        values['skill_code_prefix'] = normalize_skill_code_prefix(
            values.get('skill_code_prefix'),
        )
    if 'skill_command_prefix' in values:
        values['skill_command_prefix'] = normalize_skill_command_prefix(
            values.get('skill_command_prefix'),
        )


def _export_settings(env):
    Settings = env['res.config.settings']
    catalog = list(sio.iter_settings_fields(
        Settings, module=MODULE, icp_prefix=ICP_PREFIX,
    ))
    out = sio.collect_settings_payload(
        Settings.get_values(), catalog, include_secrets=True,
        icp_prefix=ICP_PREFIX,
    )
    hidden = env['ir.config_parameter'].sudo().get_param(ICP_SKILLS_SLASH_HIDDEN)
    if hidden is not None:
        out[ICP_SKILLS_SLASH_HIDDEN] = hidden
    return out


# ─────────────────────────────────────────────────────────────────────────────
# IMPORT
# ─────────────────────────────────────────────────────────────────────────────

def import_config(env, data):
    """Upsert the whole AI configuration from a portable dict.

    Resilient: per-row errors are collected, never abort the batch. Relations
    are wired in a second pass so entity order is irrelevant.

    Args:
        env: Odoo environment.
        data: dict produced by :func:`export_config` (or an equivalent).

    Returns:
        report dict: ``{'sections': {name: {created,updated,skipped}},
                        'warnings': [...], 'errors': [...]}``
    """
    report = {'sections': {}, 'warnings': [], 'errors': []}
    if not isinstance(data, dict):
        report['errors'].append(_("Invalid backup file: expected a JSON object."))
        return report

    # ── Pass 1: scalar upsert ────────────────────────────────────────────────
    replace = True
    _import_providers(env, data.get('providers') or [], report, replace_existing=replace)
    _import_contexts(env, data.get('contexts') or [], report, replace_existing=replace)
    _import_skills(env, data.get('skills') or [], report, replace_existing=replace)
    _import_servers(env, data.get('mcp_servers') or [], report, replace_existing=replace)
    _import_whitelist(env, data.get('url_whitelists') or [], report, replace_existing=replace)
    _import_users(env, data.get('mcp_users') or [], report, replace_existing=replace)
    _import_agents_scalar(env, data.get('agents') or [], report, replace_existing=replace)

    # ── Pass 2: relations ────────────────────────────────────────────────────
    _wire_agent_relations(env, data.get('agents') or [], report, replace_existing=replace)
    _wire_skill_relations(env, data.get('skills') or [], report, replace_existing=replace)
    _import_settings(env, data.get('settings') or {}, report, replace_existing=replace)

    return report


def import_partial(env, data, replace_existing=True):
    """Import only the sections present in *data* (partial artifact bundle).

    Each section upserts by its business key (``name``, ``code``, ``login``,
    ``domain``, …). When *replace_existing* is False, existing rows are left
    untouched (including relation wiring for agents/skills).
    """
    report = {'sections': {}, 'warnings': [], 'errors': []}
    if not isinstance(data, dict):
        report['errors'].append(_("Invalid bundle section: expected a JSON object."))
        return report

    if 'providers' in data:
        _import_providers(
            env, data['providers'] or [], report, replace_existing=replace_existing,
        )
    if 'contexts' in data:
        _import_contexts(
            env, data['contexts'] or [], report, replace_existing=replace_existing,
        )
    if 'mcp_servers' in data:
        _import_servers(
            env, data['mcp_servers'] or [], report, replace_existing=replace_existing,
        )
    if 'url_whitelists' in data:
        _import_whitelist(
            env, data['url_whitelists'] or [], report, replace_existing=replace_existing,
        )
    if 'mcp_users' in data:
        _import_users(
            env, data['mcp_users'] or [], report, replace_existing=replace_existing,
        )
    if 'agents' in data:
        rows = data['agents'] or []
        _import_agents_scalar(
            env, rows, report, replace_existing=replace_existing,
        )
        _wire_agent_relations(
            env, rows, report, replace_existing=replace_existing,
        )
    if 'skills' in data:
        rows = data['skills'] or []
        _import_skills(env, rows, report, replace_existing=replace_existing)
        if replace_existing:
            _wire_skill_relations(env, rows, report)
    if 'settings' in data:
        _import_settings(
            env, data['settings'] or {}, report, replace_existing=replace_existing,
        )
    return report


def export_selected_providers(providers, include_secrets=True):
    """Portable rows for a subset of ``ai.provider`` records."""
    out = []
    for p in providers:
        d = export_record_dict(p, skip_fields={'id', 'model_name'})
        if not include_secrets:
            d.pop('api_key', None)
        d['models'] = [{'name': m.name} for m in p.available_model_ids]
        d['selected_model'] = p.model_id.name or None
        d['usage_days'] = p.usage_day_ids.to_export_rows()
        out.append(d)
    return out


def export_selected_agents(agents):
    """Portable rows for a subset of ``ai.agent`` records."""
    Link = agents.env['ai.agent.provider'].sudo().with_context(active_test=False)
    out = []
    for a in agents:
        d = export_record_dict(a, skip_fields={
            'id', 'cached_content', 'cache_locale',
            'cache_updated', 'cache_context_signature',
        })
        d['context_codes'] = a.context_ids.mapped('code')
        d['skill_codes'] = a.skill_ids.mapped('code')
        d['failovers'] = [
            {
                'provider': l.provider_id.name,
                'priority': l.priority,
                'active': l.active,
                'llm_idle_timeout': l.llm_idle_timeout,
                'llm_round_timeout': l.llm_round_timeout,
                'skip_sync_fallback': l.skip_sync_fallback,
            }
            for l in Link.search([('agent_id', '=', a.id)])
        ]
        out.append(d)
    return out


def export_selected_servers(servers, include_secrets=True):
    """Portable rows for a subset of ``ai.api.server`` records."""
    out = []
    for s in servers:
        row = export_record_dict(s)
        if not include_secrets:
            row['auth_token'] = ''
            row['env_vars'] = '{}'
        out.append(row)
    return out


def export_selected_whitelist(entries):
    """Portable rows for a subset of ``ai.url.whitelist`` records."""
    return [export_record_dict(r) for r in entries]


def export_selected_users(users, include_secrets=True):
    """Portable rows for a subset of ``ai.mcp.user`` records."""
    del include_secrets
    out = []
    for u in users:
        if not u.login or u.mcp_api_key_state != 'generated':
            continue
        row = {
            'login': u.login,
            'name': u.name or '',
            'mcp_api_key_state': u.mcp_api_key_state,
        }
        try:
            row['is_ai_admin'] = u.user_id.has_group('pns_ai_mcp.group_ai_admin')
            row['is_ai_writer'] = u.user_id.has_group('pns_ai_mcp.group_ai_writer')
            row['is_ai_external_url'] = u.user_id.has_group(
                'pns_ai_mcp.group_ai_external_url')
            row['is_ai_external_api'] = u.user_id.has_group(
                'pns_ai_mcp.group_ai_external_api')
        except Exception:
            pass
        if u.mcp_api_key_hash:
            row['mcp_api_key_hash'] = u.mcp_api_key_hash
            row['mcp_api_key_generated_date'] = (
                fields.Datetime.to_string(u.mcp_api_key_generated_date)
                if u.mcp_api_key_generated_date else None
            )
        out.append(row)
    return out


def _import_providers(env, rows, report, replace_existing=True):
    Provider = env['ai.provider'].sudo().with_context(active_test=False)
    Model = env['ai.provider.model'].sudo()
    sec = report['sections'].setdefault('providers', _section())
    for row in rows:
        name = (row.get('name') or '').strip()
        if not name:
            report['errors'].append(_("Provider without 'name' skipped."))
            continue
        try:
            vals, warns = import_vals_from_dict(
                Provider, row,
                skip_fields={
                    'id', 'model_name', 'usage_days',
                    'models', 'selected_model', 'failovers',
                },
            )
            report['warnings'].extend('provider %s: %s' % (name, w) for w in warns)
            existing = Provider.search([('name', '=', name)], limit=1)
            if existing and not replace_existing:
                sec['skipped'] += 1
                continue
            if existing:
                existing.write(vals)
                provider = existing
                sec['updated'] += 1
            else:
                provider = Provider.create(vals)
                sec['created'] += 1
            # Models (upsert by name within provider) — the list feeds the
            # model selector. context_window lives on the provider now, so a
            # model record is just its name.
            existing_models = {m.name: m for m in provider.available_model_ids}
            for m in row.get('models') or []:
                mname = (m.get('name') or '').strip()
                if not mname or mname in existing_models:
                    continue
                Model.create({'name': mname, 'provider_id': provider.id})
            # Selected model
            sel = row.get('selected_model')
            if sel:
                target = provider.available_model_ids.filtered(lambda x: x.name == sel)
                if target:
                    provider.model_id = target[0].id
            env['ai.provider.usage.day'].import_missing_days(
                provider, row.get('usage_days') or [],
            )
        except Exception as e:
            report['errors'].append("provider %s: %s" % (name, e))
            _logger.exception("config_backup import provider %s", name)


def _import_contexts(env, rows, report, replace_existing=True):
    Ctx = env['ai.context'].sudo().with_context(active_test=False)
    sec = report['sections'].setdefault('contexts', _section())
    for row in rows:
        code = (row.get('code') or '').strip()
        if not code:
            report['errors'].append(_("Context without 'code' skipped."))
            continue
        if (row.get('context_type') or '') == 'core':
            sec['skipped'] += 1  # module-owned, never overwritten
            continue
        try:
            vals, warns = import_vals_from_dict(Ctx, row, skip_fields={'id'})
            report['warnings'].extend('context %s: %s' % (code, w) for w in warns)
            existing = Ctx.search([('code', '=', code)], limit=1)
            if existing and not replace_existing:
                sec['skipped'] += 1
                continue
            if existing:
                existing.write(vals)
                sec['updated'] += 1
            else:
                Ctx.create(vals)
                sec['created'] += 1
        except Exception as e:
            report['errors'].append("context %s: %s" % (code, e))


def _import_skills(env, rows, report, replace_existing=True):
    Skill = env['ai.skill'].sudo().with_context(active_test=False)
    sec = report['sections'].setdefault('skills', _section())
    for row in rows:
        code = (row.get('code') or '').strip()
        if not code:
            report['errors'].append(_("Skill without 'code' skipped."))
            continue
        if row.get('is_system'):
            sec['skipped'] += 1  # module-owned
            continue
        try:
            vals, warns = import_vals_from_dict(
                Skill, row,
                skip_fields={'id', 'show_in_slash', 'agent_codes', 'context_codes'},
            )
            report['warnings'].extend('skill %s: %s' % (code, w) for w in warns)
            existing = Skill.search([('code', '=', code)], limit=1)
            if existing and not replace_existing:
                sec['skipped'] += 1
                continue
            if existing:
                existing.write(vals)
                existing._apply_slash_hidden_from_icp()
                sec['updated'] += 1
            else:
                Skill.create(vals)
                sec['created'] += 1
        except Exception as e:
            report['errors'].append("skill %s: %s" % (code, e))


def _import_servers(env, rows, report, replace_existing=True):
    Srv = env['ai.api.server'].sudo().with_context(active_test=False)
    sec = report['sections'].setdefault('mcp_servers', _section())
    for row in rows:
        code = (row.get('code') or '').strip()
        if not code:
            report['errors'].append(_("MCP server without 'code' skipped."))
            continue
        try:
            vals, warns = import_vals_from_dict(Srv, row, skip_fields={'id'})
            report['warnings'].extend('server %s: %s' % (code, w) for w in warns)
            existing = Srv.search([('code', '=', code)], limit=1)
            if existing and not replace_existing:
                sec['skipped'] += 1
                continue
            if existing:
                existing.write(vals)
                sec['updated'] += 1
            else:
                Srv.create(vals)
                sec['created'] += 1
        except Exception as e:
            report['errors'].append("server %s: %s" % (code, e))


def _import_whitelist(env, rows, report, replace_existing=True):
    W = env['ai.url.whitelist'].sudo().with_context(active_test=False)
    sec = report['sections'].setdefault('url_whitelists', _section())
    for row in rows:
        domain = (row.get('domain') or '').strip().lower()
        if not domain:
            report['errors'].append(_("Whitelist entry without 'domain' skipped."))
            continue
        try:
            vals, warns = import_vals_from_dict(W, row, skip_fields={'id'})
            report['warnings'].extend('whitelist %s: %s' % (domain, w) for w in warns)
            vals['domain'] = domain
            for k in ('valid_from', 'valid_until'):
                if k in vals and isinstance(vals[k], str) and vals[k]:
                    vals[k] = _norm_dt(vals[k])
            existing = W.search([('domain', '=', domain)], limit=1)
            if existing and not replace_existing:
                sec['skipped'] += 1
                continue
            if existing:
                existing.write(vals)
                sec['updated'] += 1
            else:
                W.create(vals)
                sec['created'] += 1
        except Exception as e:
            report['errors'].append("whitelist %s: %s" % (domain, e))


def _import_users(env, rows, report, replace_existing=True):
    McpUser = env['ai.mcp.user'].sudo()
    Users = env['res.users'].sudo()
    sec = report['sections'].setdefault('mcp_users', _section())
    for row in rows:
        login = (row.get('login') or '').strip()
        # Prefer the hash (new exports); accept a legacy plaintext key and hash
        # it. We never persist plaintext.
        raw = (row.get('mcp_api_key_hash') or row.get('mcp_api_key') or '').strip()
        key_hash = normalize_to_hash(raw) if raw else ''
        if not login:
            report['errors'].append(_("MCP user without 'login' skipped."))
            continue
        if not key_hash:
            sec['skipped'] += 1  # nothing restorable
            continue
        try:
            user = Users.search([('login', '=', login)], limit=1)
            if not user:
                report['warnings'].append(
                    _("Odoo user '%s' not found — API key not restored.") % login)
                sec['skipped'] += 1
                continue
            vals = {
                'mcp_api_key_hash': key_hash,
                'mcp_api_key_state': 'generated',
            }
            gen_date = _norm_dt(row.get('mcp_api_key_generated_date'))
            if gen_date:
                vals['mcp_api_key_generated_date'] = gen_date
            else:
                vals['mcp_api_key_generated_date'] = fields.Datetime.now()
            mcp = McpUser.with_context(mcp_skip_ensure_all_users=True).search(
                [('user_id', '=', user.id)], limit=1)
            if mcp and not replace_existing:
                sec['skipped'] += 1
                continue
            if mcp:
                mcp.write(vals)
                sec['updated'] += 1
            else:
                vals['user_id'] = user.id
                McpUser.with_context(mcp_skip_ensure_all_users=True).create(vals)
                sec['created'] += 1
        except Exception as e:
            report['errors'].append("user %s: %s" % (login, e))


def _import_agents_scalar(env, rows, report, replace_existing=True):
    Agent = env['ai.agent'].sudo().with_context(active_test=False)
    sec = report['sections'].setdefault('agents', _section())
    for row in rows:
        code = (row.get('code') or '').strip()
        if not code:
            report['errors'].append(_("Agent without 'code' skipped."))
            continue
        try:
            existing = Agent.search([('code', '=', code)], limit=1)
            if not existing:
                # Agents are module-owned; they reappear on (re)install. We do
                # not create them here (create is blocked for non-module origin).
                report['warnings'].append(
                    _("Agent '%s' not present (install its module) — config "
                      "not applied.") % code)
                sec['skipped'] += 1
                continue
            if not replace_existing:
                sec['skipped'] += 1
                continue
            vals, warns = import_vals_from_dict(
                Agent, row,
                skip_fields=_AGENT_IMPORT_SKIP | {
                    'context_codes', 'skill_codes', 'failovers',
                },
                key_aliases={'max_agent_turns': 'max_agent_rounds'},
            )
            report['warnings'].extend('agent %s: %s' % (code, w) for w in warns)
            if vals:
                existing.write(vals)
            sec['updated'] += 1
        except Exception as e:
            report['errors'].append("agent %s: %s" % (code, e))


def _wire_agent_relations(env, rows, report, replace_existing=True):
    Agent = env['ai.agent'].sudo().with_context(active_test=False)
    Provider = env['ai.provider'].sudo().with_context(active_test=False)
    Ctx = env['ai.context'].sudo().with_context(active_test=False)
    Skill = env['ai.skill'].sudo().with_context(active_test=False)
    Link = env['ai.agent.provider'].sudo().with_context(active_test=False)
    for row in rows:
        code = (row.get('code') or '').strip()
        agent = Agent.search([('code', '=', code)], limit=1) if code else None
        if not agent:
            continue
        if not replace_existing:
            continue
        try:
            write_vals = {}
            ctx_codes = row.get('context_codes')
            if ctx_codes is not None:
                ctxs = Ctx.search([('code', 'in', ctx_codes)]) if ctx_codes else Ctx
                write_vals['context_ids'] = [(6, 0, ctxs.ids)]
                missing = set(ctx_codes) - set(ctxs.mapped('code'))
                if missing:
                    report['warnings'].append(
                        _("agent %s: contexts not found: %s")
                        % (code, ', '.join(sorted(missing))))
            skill_codes = row.get('skill_codes')
            if skill_codes is not None:
                skills = Skill.search([('code', 'in', skill_codes)]) if skill_codes else Skill
                write_vals['skill_ids'] = [(6, 0, skills.ids)]
            if write_vals:
                agent.write(write_vals)
            # Failover chain: rebuild from scratch to mirror the source exactly.
            failovers = row.get('failovers')
            if failovers is not None:
                Link.search([('agent_id', '=', agent.id)]).unlink()
                for fo in failovers:
                    pname = fo.get('provider')
                    provider = Provider.search([('name', '=', pname)], limit=1)
                    if not provider:
                        report['warnings'].append(
                            _("agent %s: provider '%s' not found for failover.")
                            % (code, pname or '?'))
                        continue
                    Link.create({
                        'agent_id': agent.id,
                        'provider_id': provider.id,
                        'priority': fo.get('priority', 0),
                        'active': fo.get('active', True),
                        'llm_idle_timeout': fo.get('llm_idle_timeout', 45),
                        'llm_round_timeout': fo.get(
                            'llm_round_timeout',
                            fo.get('llm_turn_timeout', 120),
                        ),
                        'skip_sync_fallback': fo.get('skip_sync_fallback', False),
                    })
        except Exception as e:
            report['errors'].append("agent %s relations: %s" % (code, e))


def _wire_skill_relations(env, rows, report):
    Skill = env['ai.skill'].sudo().with_context(active_test=False)
    Agent = env['ai.agent'].sudo().with_context(active_test=False)
    Ctx = env['ai.context'].sudo().with_context(active_test=False)
    for row in rows:
        code = (row.get('code') or '').strip()
        if not code or row.get('is_system'):
            continue
        skill = Skill.search([('code', '=', code)], limit=1)
        if not skill:
            continue
        try:
            write_vals = {}
            ctx_codes = row.get('context_codes')
            if ctx_codes is not None:
                ctxs = Ctx.search([('code', 'in', ctx_codes)]) if ctx_codes else Ctx
                write_vals['context_ids'] = [(6, 0, ctxs.ids)]
            agent_codes = row.get('agent_codes')
            if agent_codes is not None:
                agents = Agent.search([('code', 'in', agent_codes)]) if agent_codes else Agent
                write_vals['agent_ids'] = [(6, 0, agents.ids)]
            if write_vals:
                skill.write(write_vals)
        except Exception as e:
            report['errors'].append("skill %s relations: %s" % (code, e))


def _import_settings(env, settings, report, replace_existing=True):
    if not isinstance(settings, dict):
        return
    payload = dict(settings)
    hidden = payload.pop(ICP_SKILLS_SLASH_HIDDEN, None)
    sub = sio.import_settings(
        env, {'settings': payload},
        module=MODULE, icp_prefix=ICP_PREFIX,
        replace_existing=replace_existing,
        clamp=_clamp_mcp_settings,
    )
    report['warnings'].extend(sub.get('warnings') or [])
    report['errors'].extend(sub.get('errors') or [])
    sec = report['sections'].setdefault('settings', _section())
    src = (sub.get('sections') or {}).get('settings') or {}
    sec['created'] += src.get('created', 0)
    sec['updated'] += src.get('updated', 0)
    sec['skipped'] += src.get('skipped', 0)
    if hidden is None:
        return
    try:
        env['ir.config_parameter'].sudo().set_param(
            ICP_SKILLS_SLASH_HIDDEN, hidden or '',
        )
        env['ai.skill'].sudo().search([])._apply_slash_hidden_from_icp()
        sec['updated'] += 1
    except Exception as e:
        report['errors'].append("skills_slash_hidden apply: %s" % e)
