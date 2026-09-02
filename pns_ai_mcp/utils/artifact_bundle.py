# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Partial export/import bundle for portable AI artifacts.

One ZIP with optional nested payloads. Import applies only what is present;
``replace_existing`` upserts rows matched by business key (``code``, ``name``,
``login``, ``domain``, …).
"""
from __future__ import annotations

import datetime as _dt
import io
import json
import zipfile

from odoo import _
from odoo.exceptions import UserError

from .config_backup import (
    _export_settings,
    export_selected_agents,
    export_selected_providers,
    export_selected_servers,
    export_selected_users,
    export_selected_whitelist,
    import_partial,
)
from .import_export_guard import ensure_ai_admin

BUNDLE_SCHEMA_VERSION = '1.1'
BUNDLE_TYPE = 'pns.ai.artifact.bundle'

_BUNDLE_SECTION_FILES = frozenset({
    'skills.zip',
    'contexts.zip',
    'providers.json',
    'agents.json',
    'mcp_servers.json',
    'servers.json',  # legacy 1.0 name
    'mcp_users.json',
    'url_whitelists.json',
    'settings.json',
})


def export_bundle(
    env,
    skills=None,
    contexts=None,
    providers=None,
    agents=None,
    servers=None,
    users=None,
    whitelists=None,
    include_secrets=False,
    include_settings=False,
    export_tag=None,
    export_artifact=None,
):
    """Build a partial artifact bundle ZIP. Returns attachment-ready dict."""
    ensure_ai_admin(env)
    Skill = env['ai.skill'].sudo().with_context(active_test=False)
    Context = env['ai.context'].sudo().with_context(active_test=False)
    Provider = env['ai.provider'].sudo().with_context(active_test=False)
    Agent = env['ai.agent'].sudo().with_context(active_test=False)
    Server = env['ai.api.server'].sudo().with_context(active_test=False)
    User = env['ai.mcp.user'].sudo()
    Whitelist = env['ai.url.whitelist'].sudo().with_context(active_test=False)

    skills = skills.exists() if skills is not None else Skill.browse()
    contexts = contexts.exists() if contexts is not None else Context.browse()
    providers = providers.exists() if providers is not None else Provider.browse()
    agents = agents.exists() if agents is not None else Agent.browse()
    servers = servers.exists() if servers is not None else Server.browse()
    users = users.exists() if users is not None else User.browse()
    whitelists = whitelists.exists() if whitelists is not None else Whitelist.browse()

    selected = (
        skills or contexts or providers or agents or servers or users or whitelists
        or include_settings
    )
    if not selected:
        raise UserError(_(
            'Select at least one artifact section to export '
            '(skills, contexts, providers, agents, servers, MCP users, '
            'URL whitelist or settings).'
        ))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        if skills:
            payload = Skill._build_skills_zip_bytes(skills, 'bundle-skills')
            if payload:
                zf.writestr('skills.zip', payload)
        if contexts:
            payload = Context._build_contexts_zip_bytes(contexts, 'bundle-contexts')
            if payload:
                zf.writestr('contexts.zip', payload)
        if providers:
            rows = export_selected_providers(providers, include_secrets=include_secrets)
            zf.writestr(
                'providers.json',
                json.dumps(rows, indent=2, ensure_ascii=False),
            )
        if agents:
            rows = export_selected_agents(agents)
            zf.writestr(
                'agents.json',
                json.dumps(rows, indent=2, ensure_ascii=False),
            )
        if servers:
            rows = export_selected_servers(servers, include_secrets=include_secrets)
            zf.writestr(
                'mcp_servers.json',
                json.dumps(rows, indent=2, ensure_ascii=False),
            )
        if users:
            rows = export_selected_users(users, include_secrets=include_secrets)
            zf.writestr(
                'mcp_users.json',
                json.dumps(rows, indent=2, ensure_ascii=False),
            )
        if whitelists:
            rows = export_selected_whitelist(whitelists)
            zf.writestr(
                'url_whitelists.json',
                json.dumps(rows, indent=2, ensure_ascii=False),
            )
        if include_settings:
            settings = _export_settings(env)
            zf.writestr(
                'settings.json',
                json.dumps(settings, indent=2, ensure_ascii=False),
            )

        artifact_slug = (export_artifact or 'ai_artifact_bundle').strip()
        tag = (export_tag or '').strip() or None
        from . import mcp_ui
        export_filename = mcp_ui.build_export_filename(
            env, artifact_slug, 'zip', tag=tag,
        )

        manifest = {
            'type': BUNDLE_TYPE,
            'schema_version': BUNDLE_SCHEMA_VERSION,
            'exported_at': _dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
            'source_database': env.cr.dbname,
            'export_tag': tag,
            'export_artifact': artifact_slug,
            'export_filename': export_filename,
            'include_secrets': bool(include_secrets),
            'include_settings': bool(include_settings),
            'skill_codes': skills.mapped('code'),
            'context_codes': contexts.mapped('code'),
            'provider_names': providers.mapped('name'),
            'agent_codes': agents.mapped('code'),
            'server_codes': servers.mapped('code'),
            'mcp_user_logins': users.mapped('login'),
            'whitelist_domains': whitelists.mapped('domain'),
        }
        zf.writestr(
            'bundle_manifest.json',
            json.dumps(manifest, indent=2, ensure_ascii=False),
        )

    buf.seek(0)
    counts = {
        'skills': len(skills),
        'contexts': len(contexts),
        'providers': len(providers),
        'agents': len(agents),
        'servers': len(servers),
        'users': len(users),
        'whitelists': len(whitelists),
        'settings': 1 if include_settings else 0,
    }
    return {
        'payload': buf.getvalue(),
        'counts': counts,
        'manifest': manifest,
        'export_filename': export_filename,
    }


def import_bundle(env, zip_bytes, replace_existing=True):
    """Import a partial artifact bundle. Only sections present are applied."""
    ensure_ai_admin(env)
    Skill = env['ai.skill'].sudo()
    Context = env['ai.context'].sudo()

    report = {
        'skills': {},
        'contexts': {},
        'sections': {},
        'manifest': {},
        'warnings': [],
        'errors': [],
    }
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            names = set(zf.namelist())
            manifest = {}
            if 'bundle_manifest.json' in names:
                try:
                    manifest = json.loads(
                        zf.read('bundle_manifest.json').decode('utf-8')
                    )
                    report['manifest'] = manifest
                    if manifest.get('type') and manifest['type'] != BUNDLE_TYPE:
                        report['warnings'].append(_(
                            'Unexpected bundle type: %s'
                        ) % manifest.get('type'))
                except Exception:
                    report['warnings'].append(_('Could not read bundle_manifest.json.'))

            if 'skills.zip' in names:
                report['skills'] = Skill.import_skills_zip(
                    zf.read('skills.zip'),
                    replace_existing=replace_existing,
                )
            if 'contexts.zip' in names:
                ctx_result = Context.import_contexts_zip(
                    zf.read('contexts.zip'),
                    replace_existing=replace_existing,
                )
                report['contexts'] = ctx_result.get('files') or {}
                report['warnings'].extend(ctx_result.get('warnings') or [])

            partial = {}
            if 'providers.json' in names:
                partial['providers'] = json.loads(
                    zf.read('providers.json').decode('utf-8')
                )
            if 'agents.json' in names:
                partial['agents'] = json.loads(
                    zf.read('agents.json').decode('utf-8')
                )
            server_file = None
            if 'mcp_servers.json' in names:
                server_file = 'mcp_servers.json'
            elif 'servers.json' in names:
                server_file = 'servers.json'
            if server_file:
                partial['mcp_servers'] = json.loads(
                    zf.read(server_file).decode('utf-8')
                )
            if 'mcp_users.json' in names:
                partial['mcp_users'] = json.loads(
                    zf.read('mcp_users.json').decode('utf-8')
                )
            if 'url_whitelists.json' in names:
                partial['url_whitelists'] = json.loads(
                    zf.read('url_whitelists.json').decode('utf-8')
                )
            if 'settings.json' in names:
                partial['settings'] = json.loads(
                    zf.read('settings.json').decode('utf-8')
                )

            if partial:
                partial_report = import_partial(
                    env, partial, replace_existing=replace_existing,
                )
                report['sections'] = partial_report.get('sections') or {}
                report['warnings'].extend(partial_report.get('warnings') or [])
                report['errors'].extend(partial_report.get('errors') or [])

            if not _BUNDLE_SECTION_FILES & names:
                raise UserError(_(
                    'Invalid bundle: no recognized artifact section found.'
                ))
    except zipfile.BadZipFile as exc:
        raise UserError(_('Could not read artifact bundle ZIP: %s') % exc) from exc
    return report


def bundle_export_attachment(env, result, filename='ai_artifact_bundle', tag=None):
    """Create ir.attachment from :func:`export_bundle` result."""
    from . import mcp_ui
    name = result.get('export_filename') or mcp_ui.build_export_filename(
        env, filename, 'zip', tag=tag,
    )
    return mcp_ui.write_export_attachment(
        env, name, result['payload'], 'application/zip',
    )
