# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Shared helpers for this addon's Odoo tests (O14 + O19)."""
import re
import uuid

# Locale suffix in code (test fixtures only; the model requires an explicit locale).
_LOCALE_CODE_RE = re.compile(r'_([a-z]{2}_[A-Z]{2})$')


def locale_from_code(code):
    """Extract the locale from a code like demo_terms_es_ES → es_ES (or False)."""
    match = _LOCALE_CODE_RE.search(code or '')
    return match.group(1) if match else False


def unique_login(prefix='pns_test'):
    """Unique login per run (avoids UniqueViolation if junk was left in the DB)."""
    return '%s_%s@mcp.test' % (prefix, uuid.uuid4().hex[:10])


# Instance add-ons may demand an origin on every contact; tests create bare ones.
SKIP_CONTACT_ORIGIN = {'pns_skip_source_required': True}


def make_user(env, prefix, groups):
    """``new_test_user`` with a login of its own run.

    Safe Plan commits the caller's cursor, so a user a test created may stay
    in the database; a fixed login would collide on the next run.
    """
    from odoo.tests.common import new_test_user
    return new_test_user(
        env, login=unique_login(prefix), groups=groups,
        context={
            **SKIP_CONTACT_ORIGIN,
            'no_reset_password': True,
            'mail_create_nosubscribe': True,
            'mail_notrack': True,
            'tracking_disable': True,
        },
    )


def _test_cursor_view(cr):
    """The test cursor seen as a fresh one: commit and close do nothing.

    A subclass on the cursor's connection, because Odoo asserts the type.
    """
    class _View(type(cr)):
        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def __del__(self):
            pass

    view = object.__new__(_View)
    # Same connection and transaction objects. O16+ tests also forbid
    # commit/rollback on the cursor instance itself: those stay behind.
    state = dict(cr.__dict__)
    for name in ('commit', 'rollback', 'close'):
        state.pop(name, None)
    view.__dict__ = state
    return view


def one_cursor(testcase):
    """Code that opens its own cursor runs inside the test transaction.

    Two transactions in one process can wait on each other forever (the
    test holds a row the other cursor needs). Inside this block nothing is
    committed and the test rollback undoes everything.
    """
    from unittest.mock import patch
    registry = testcase.env.registry
    return patch.object(
        type(registry), 'cursor',
        lambda self, *a, **kw: _test_cursor_view(testcase.env.cr),
    )


def db_name_looks_like_safe_test(env):
    """True if the DB name suggests a test instance (not production).

    Matches ``prueba`` (covers ``pruebas``) or ``test`` in the name.
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


# Historical alias (same criterion).
db_name_looks_like_pruebas = db_name_looks_like_safe_test


def skip_unless_safe_test_db_for_intrusion(testcase):
    """Skip intrusion/box A tests outside a test DB.

    Why: the real relaxaicode pipeline opens an **isolated cursor** outside the
    TransactionCase savepoint. A bypass (or a side commit) can persist in the
    real DB — not acceptable in production.

    Deliberate opt-in: env ``PNS_ALLOW_INTRUSION_TESTS=1``.
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


# Historical alias.
skip_unless_pruebas_for_intrusion = skip_unless_safe_test_db_for_intrusion


def create_test_user(env, prefix='pns_test', groups=None, **vals):
    """Create res.users with a unique login; default groups = internal user.

    - Mail contexts: on O14 website_slides/digest break savepoints if not
      silenced.
    - Local ``lock_timeout``: if the live Odoo is still running, it fails in
      ~15s instead of hanging the suite forever.
    """
    from odoo.addons.pns_base.utils.compat import USER_GROUPS_FIELD
    if groups is None:
        groups = [env.ref('base.group_user').id]
    login = vals.pop('login', None) or unique_login(prefix)
    password = vals.pop('password', None) or ('test_%s' % uuid.uuid4().hex[:12])
    payload = {
        'name': vals.pop('name', login),
        'login': login,
        'email': vals.pop('email', login),
        'password': password,
        USER_GROUPS_FIELD: [(6, 0, groups)],
    }
    payload.update(vals)
    try:
        env.cr.execute("SET LOCAL lock_timeout = '15s'")
    except Exception:
        pass
    Users = env['res.users'].sudo().with_context(
        **SKIP_CONTACT_ORIGIN,
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


_ADMIN_KEY_FIELDS = (
    'mcp_api_key_hash', 'mcp_api_key_state', 'mcp_api_key_generated_date',
)


AI_PLAN_GROUPS = ('pns_ai_mcp.group_ai_writer', 'pns_ai_mcp.group_ai_admin')


def grant_groups(user, xmlids):
    """Give *user* the groups it lacks; return those, for ``revoke_groups``."""
    from odoo.addons.pns_base.utils.compat import USER_GROUPS_FIELD
    missing = [x for x in xmlids if not user.has_group(x)]
    if missing:
        user.write({USER_GROUPS_FIELD: [(4, user.env.ref(x).id) for x in missing]})
    return missing


def revoke_groups(user, xmlids):
    from odoo.addons.pns_base.utils.compat import USER_GROUPS_FIELD
    if xmlids:
        user.write({USER_GROUPS_FIELD: [(3, user.env.ref(x).id) for x in xmlids]})


def _write_mcp_http_fixtures(fix_env, api_key):
    """Put ``api_key`` and the conversational group on admin.

    Returns what admin had before, for ``_restore_admin_key``.
    """
    from odoo.addons.pns_ai_mcp.utils.api_key import hash_api_key
    from odoo.addons.pns_ai_mcp.utils.conversational import GROUP_AI_CONVERSATIONAL
    ensure_test_agents(fix_env)
    test_user = fix_env.ref('base.user_admin')
    test_user.write({'active': True})
    key_hash = hash_api_key(api_key)
    mcp_user_model = fix_env['ai.mcp.user'].sudo()
    mcp_user = mcp_user_model.search([('user_id', '=', test_user.id)], limit=1)
    previous = {
        'key': {f: mcp_user[f] for f in _ADMIN_KEY_FIELDS} if mcp_user else None,
    }
    if not mcp_user:
        mcp_user = mcp_user_model.create({'user_id': test_user.id})
    mcp_user.write({
        'mcp_api_key_hash': key_hash,
        'mcp_api_key_state': 'generated',
    })
    previous['groups_added'] = grant_groups(test_user, [GROUP_AI_CONVERSATIONAL])
    return previous


def _restore_admin_key(fix_env, previous):
    test_user = fix_env.ref('base.user_admin')
    revoke_groups(test_user, previous.get('groups_added'))
    mcp_user = fix_env['ai.mcp.user'].sudo().search(
        [('user_id', '=', test_user.id)], limit=1,
    )
    if not mcp_user:
        return
    if previous.get('key') is None:
        mcp_user.unlink()
    else:
        mcp_user.write(previous['key'])


def _count_active_mcp_key(env, api_key):
    from odoo.addons.pns_ai_mcp.utils.api_key import hash_api_key
    return env['ai.mcp.user'].sudo().search_count([
        ('mcp_api_key_hash', '=', hash_api_key(api_key)),
        ('user_id.active', '=', True),
    ])


def setup_http_mcp_fixtures(cls, env):
    """MCP API key for HttpCase: commit depending on the Odoo version.

    The key is committed (the HTTP worker reads it on another cursor), so it
    is random per class and ``teardown_http_mcp_fixtures`` gives admin back
    the key it had.
    """
    import secrets
    from odoo import api, SUPERUSER_ID
    from odoo.addons.pns_ai_mcp.utils.compat import ODOO_VERSION

    if not getattr(cls, 'test_api_key', None):
        cls.test_api_key = 'pns-http-test-%s' % secrets.token_urlsafe(24)
    api_key = cls.test_api_key

    if ODOO_VERSION <= 14:
        # O14: each test owns its cursor (no savepoint); same one as url_open.
        fix_env = env(user=SUPERUSER_ID)
        previous = _write_mcp_http_fixtures(fix_env, api_key)
        env.cr.commit()
    else:
        # O15+: the tests of a class share one cursor with a savepoint each;
        # a commit there drops the savepoints. Separate cursor with commit.
        with env.registry.cursor() as cr:
            fix_env = api.Environment(cr, SUPERUSER_ID, {})
            previous = _write_mcp_http_fixtures(fix_env, api_key)
            cr.commit()
    if not hasattr(cls, '_pns_admin_key_backup'):
        cls._pns_admin_key_backup = previous

    _clear_registry_caches(env.registry)
    found = _count_active_mcp_key(env(user=SUPERUSER_ID), api_key)
    if not found:
        raise AssertionError(
            'MCP test API key not visible after commit (%s). '
            'Check ai.mcp.user for admin on db %s.' % (api_key, env.cr.dbname)
        )
    cls._pns_http_fixtures_done = True


def teardown_http_mcp_fixtures(cls):
    """Give admin back the MCP key it had before ``setup_http_mcp_fixtures``."""
    from odoo import api, SUPERUSER_ID
    from odoo.modules.registry import Registry
    from odoo.tests.common import get_db_name
    if not hasattr(cls, '_pns_admin_key_backup'):
        return
    previous = cls._pns_admin_key_backup
    del cls._pns_admin_key_backup
    registry = Registry(get_db_name())
    with registry.cursor() as cr:
        _restore_admin_key(api.Environment(cr, SUPERUSER_ID, {}), previous)
        cr.commit()
    _clear_registry_caches(registry)


def http_status_code(response):
    """Odoo 14 url_open → Werkzeug (.status); O19 usually exposes .status_code."""
    code = getattr(response, 'status_code', None)
    if code is not None:
        return int(code)
    status = getattr(response, 'status', '200 OK')
    return int(str(status).split()[0])


def http_response_text(response):
    """HTTP body: .content (requests) or .data (Werkzeug on O14)."""
    raw = getattr(response, 'content', None)
    if raw is None:
        raw = getattr(response, 'data', b'') or b''
    if isinstance(raw, str):
        return raw
    return raw.decode('utf-8')


def mcp_test_url(path, api_key):
    """MCP URL without the key: the key only travels in the mcp_test_headers headers."""
    return path


def mcp_test_headers(api_key):
    """MCP headers in line with smoke_mcp_http.sh and O14 portability."""
    from odoo.addons.pns_ai_mcp.utils.compat import NEEDS_ROOT_GET_REQUEST_PATCH

    content_type = 'text/plain' if NEEDS_ROOT_GET_REQUEST_PATCH else 'application/json'
    return {
        'Content-Type': content_type,
        'X-MCP-API-Key': api_key,
        'X-Mcp-Token': api_key,
    }
