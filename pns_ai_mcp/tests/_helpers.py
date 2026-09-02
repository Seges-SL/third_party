# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Helpers compartidos por tests Odoo del addon (O14 + O19)."""
import re
import uuid

# Sufijo de locale en code (solo para fixtures de test; el modelo exige locale explícito).
_LOCALE_CODE_RE = re.compile(r'_([a-z]{2}_[A-Z]{2})$')


def locale_from_code(code):
    """Extrae locale de un code tipo demo_terms_es_ES → es_ES (o False)."""
    match = _LOCALE_CODE_RE.search(code or '')
    return match.group(1) if match else False


def unique_login(prefix='pns_test'):
    """Login único por ejecución (evita UniqueViolation si quedó basura en BD)."""
    return '%s_%s@mcp.test' % (prefix, uuid.uuid4().hex[:10])


def db_name_looks_like_safe_test(env):
    """True si el nombre de BD sugiere instancia de test/prueba (no producción).

    Coincide con ``prueba`` (cubre ``pruebas``) o ``test`` en el nombre.
    """
    db = ''
    try:
        db = getattr(env.cr, 'dbname', None) or ''
    except Exception:
        db = ''
    if not db:
        try:
            db = getattr(env.registry, 'db_name', None) or ''
        except Exception:
            db = ''
    low = (db or '').lower()
    return ('prueba' in low) or ('test' in low)


# Alias histórico (mismo criterio).
db_name_looks_like_pruebas = db_name_looks_like_safe_test


def skip_unless_safe_test_db_for_intrusion(testcase):
    """Salta tests de intrusión/caja A fuera de BD de prueba/test.

    Motivo: el pipeline real de relaxaicode abre un **cursor aislado** fuera del
    savepoint del TransactionCase. Un bypass (o un commit colateral) puede
    persistir en la BD real — inaceptable en producción.

    Opt-in consciente: env ``PNS_ALLOW_INTRUSION_TESTS=1``.
    """
    import os

    allow = (os.environ.get('PNS_ALLOW_INTRUSION_TESTS') or '').strip().lower()
    if allow in ('1', 'true', 'yes', 'on'):
        return
    if db_name_looks_like_safe_test(testcase.env):
        return
    db = getattr(testcase.env.cr, 'dbname', '?')
    testcase.skipTest(
        'Intrusión caja A solo en BD *prueba*/*test* (db=%s). '
        'Host: ./t.sh --intrusion-only. Forzar: PNS_ALLOW_INTRUSION_TESTS=1.'
        % db
    )


# Alias histórico.
skip_unless_pruebas_for_intrusion = skip_unless_safe_test_db_for_intrusion


def create_test_user(env, prefix='pns_test', groups=None, **vals):
    """Crea res.users con login único; groups por defecto = internal user.

    - Contextos mail: en O14 website_slides/digest rompen savepoints si no se
      silencian.
    - ``lock_timeout`` local: si el Odoo vivo sigue activo, falla en ~15s en
      vez de colgar el suite indefinidamente.
    """
    if groups is None:
        groups = [env.ref('base.group_user').id]
    login = vals.pop('login', None) or unique_login(prefix)
    password = vals.pop('password', None) or ('test_%s' % uuid.uuid4().hex[:12])
    payload = {
        'name': vals.pop('name', login),
        'login': login,
        'email': vals.pop('email', login),
        'password': password,
        'groups_id': [(6, 0, groups)],
    }
    payload.update(vals)
    try:
        env.cr.execute("SET LOCAL lock_timeout = '15s'")
    except Exception:
        pass
    Users = env['res.users'].sudo().with_context(
        no_reset_password=True,
        mail_create_nolog=True,
        mail_create_nosubscribe=True,
        mail_notrack=True,
        tracking_disable=True,
        mail_auto_delete=False,
    )
    return Users.create(payload)


def ensure_test_agents(env):
    """Ensure pns_ai_mcp agent exists; clear message if seed data is missing."""
    agent = env['ai.agent'].search([
        ('code', '=', 'pns_ai_mcp'),
        ('active', '=', True),
    ], limit=1)
    if not agent:
        raise AssertionError(
            'AI agent "pns_ai_mcp" not found. '
            'Sync addon to Docker (t.sh --sync: common/ + stack) and upgrade pns_ai_mcp (-u).'
        )
    return agent


def create_test_agent(env, code, **vals):
    """Create a module-origin agent for TransactionCase tests."""
    payload = {
        'name': vals.pop('name', 'Test %s' % code),
        'code': code,
        'origin': 'module',
        'module_name': 'pns_ai_mcp',
    }
    payload.update(vals)
    return env['ai.agent'].create(payload)


def _clear_registry_caches(registry):
    """O14: clear_caches(); O16+: clear_cache()."""
    if hasattr(registry, 'clear_cache'):
        registry.clear_cache()
    elif hasattr(registry, 'clear_caches'):
        registry.clear_caches()


def _write_mcp_http_fixtures(fix_env, api_key):
    """Crea/actualiza usuario MCP de prueba; devuelve el modelo sudo."""
    from odoo.addons.pns_ai_mcp.utils.api_key import hash_api_key
    ensure_test_agents(fix_env)
    test_user = fix_env.ref('base.user_admin')
    test_user.write({'active': True})
    key_hash = hash_api_key(api_key)
    mcp_user_model = fix_env['ai.mcp.user'].sudo()
    mcp_user_model.search([('mcp_api_key_hash', '=', key_hash)]).write({
        'mcp_api_key_hash': False,
        'mcp_api_key_state': 'not_generated',
    })
    mcp_user = mcp_user_model.search([('user_id', '=', test_user.id)], limit=1)
    if not mcp_user:
        mcp_user = mcp_user_model.create({'user_id': test_user.id})
    mcp_user.write({
        'mcp_api_key_hash': key_hash,
        'mcp_api_key_state': 'generated',
    })
    return mcp_user_model


def _count_active_mcp_key(env, api_key):
    from odoo.addons.pns_ai_mcp.utils.api_key import hash_api_key
    return env['ai.mcp.user'].sudo().search_count([
        ('mcp_api_key_hash', '=', hash_api_key(api_key)),
        ('user_id.active', '=', True),
    ])


def setup_http_mcp_fixtures(cls, env):
    """API key MCP para HttpCase: commit según versión Odoo."""
    from odoo import api, SUPERUSER_ID
    from odoo.addons.pns_ai_mcp.utils.compat import NEEDS_ROOT_GET_REQUEST_PATCH

    if not getattr(cls, 'test_api_key', None):
        cls.test_api_key = 'pns-http-test-%s' % env.cr.dbname
    api_key = cls.test_api_key

    if NEEDS_ROOT_GET_REQUEST_PATCH:
        # O14: mismo cursor que enter_test_mode / url_open.
        fix_env = env(user=SUPERUSER_ID)
        _write_mcp_http_fixtures(fix_env, api_key)
        env.cr.commit()
    else:
        # O16+: commit en cursor de test prohibido — cursor aparte con commit.
        with env.registry.cursor() as cr:
            fix_env = api.Environment(cr, SUPERUSER_ID, {})
            _write_mcp_http_fixtures(fix_env, api_key)
            cr.commit()

    _clear_registry_caches(env.registry)
    found = _count_active_mcp_key(env(user=SUPERUSER_ID), api_key)
    if not found:
        raise AssertionError(
            'MCP test API key not visible after commit (%s). '
            'Check ai.mcp.user for admin on db %s.' % (api_key, env.cr.dbname)
        )
    cls._pns_http_fixtures_done = True


def http_status_code(response):
    """Odoo 14 url_open → Werkzeug (.status); O19 suele exponer .status_code."""
    code = getattr(response, 'status_code', None)
    if code is not None:
        return int(code)
    status = getattr(response, 'status', '200 OK')
    return int(str(status).split()[0])


def http_response_text(response):
    """Cuerpo HTTP: .content (requests) o .data (Werkzeug en O14)."""
    raw = getattr(response, 'content', None)
    if raw is None:
        raw = getattr(response, 'data', b'') or b''
    if isinstance(raw, str):
        return raw
    return raw.decode('utf-8')


def mcp_test_url(path, api_key):
    """URL MCP con api_key en query (smoke + fallback si cabeceras no llegan)."""
    from urllib.parse import urlencode

    sep = '&' if '?' in path else '?'
    return '%s%s%s' % (path, sep, urlencode({'api_key': api_key}))


def mcp_test_headers(api_key):
    """Cabeceras MCP alineadas con smoke_mcp_http.sh y portabilidad O14."""
    from odoo.addons.pns_ai_mcp.utils.compat import NEEDS_ROOT_GET_REQUEST_PATCH

    content_type = 'text/plain' if NEEDS_ROOT_GET_REQUEST_PATCH else 'application/json'
    return {
        'Content-Type': content_type,
        'X-MCP-API-Key': api_key,
        'X-Mcp-Token': api_key,
    }
