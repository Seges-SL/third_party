# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: tests de la entrega E0′ (no regresión de los parches 7 a 10, retirados en 3.1.879). Ver docs/pendiente/parches_pns_ai.md
"""Parches 7 a 10 (PNS-90, PNS-91, PNS-85, PNS-83), cubiertos por el fabricante
desde 3.1.879: métodos que dejan de ser públicos, flujos internos que siguen
funcionando y bloqueo de los nombres privados en el sandbox.

Portado de la rama 14.0-pns-ai-correcciones (entrega E1) y adaptado a 3.1.879
(docs/specs/comparacion_pns_ai_3-1-879.md, §4.1)."""

import hashlib
import inspect
import json
import os
import re
import uuid
from datetime import timedelta
from unittest.mock import patch

import requests

from odoo import fields
from odoo.modules.module import get_module_path
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger

from odoo.addons.pns_ai_mcp.controllers import safe_plan
from odoo.addons.pns_ai_mcp.controllers.context_builder import (
    guarded_getattr,
    guarded_methodcaller,
)
from odoo.addons.pns_ai_mcp.controllers.validators import (
    validate_relaxaicode_source_ast,
)
from odoo.addons.pns_ai_mcp.controllers.validators_base import (
    ast_error_code,
    blocked_private_attr,
)
from odoo.addons.pns_ai_mcp.utils.engine_skills import SkillsMixin

SAFE_PLAN = 'odoo.addons.pns_ai_mcp.controllers.safe_plan'

# (modelo, nombre antiguo, nombre nuevo)
RENAMED = (
    ('ai.fetch.cache', 'get_cached', '_get_cached'),
    ('ai.fetch.cache', 'store', '_store'),
    ('ai.url.whitelist', 'ensure_domain_whitelisted', '_ensure_domain_whitelisted'),
    ('ai.skill.param.cache', 'remember_for_skill', '_remember_for_skill'),
    ('ai.skill.param.cache', 'lookup_for_skill', '_lookup_for_skill'),
    ('ai.skill', 'remember_param_cache', '_remember_param_cache'),
    ('ai.skill', 'lookup_param_cache', '_lookup_param_cache'),
    ('ai.mcp.user', 'redeem_key_pin', '_redeem_key_pin'),
    ('ai.key.pin.block', 'release_all', '_release_all'),
    ('ai.key.pin.block', 'note_failure', '_note_failure'),
    ('ai.key.pin.block', 'is_blocked', '_is_blocked'),
)

NEW_NAMES = tuple(new for _model, _old, new in RENAMED)

SEED_URL = 'https://seges-e1.invalid/seed'
SEED_BODY = 'seges-e1-seed-body'
ARCHIVED = 'seges-e1-archived.invalid'
BLOCKED_IP = '198.51.100.1'


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e0')
class TestSegesRpcAccess(HttpCase):
    """Negativos por RPC real: interno y portal no pueden usar los métodos."""

    def setUp(self):
        super().setUp()
        self.user_internal = new_test_user(
            self.env, login='seges_e1_internal', groups='base.group_user',
            password='seges_e1_internal',
        )
        self.user_portal = new_test_user(
            self.env, login='seges_e1_portal', groups='base.group_portal',
            password='seges_e1_portal',
        )
        now = fields.Datetime.now()
        self.env['ai.fetch.cache'].sudo().create({
            'url': SEED_URL,
            'url_hash': hashlib.sha256(SEED_URL.encode('utf-8')).hexdigest(),
            'body': SEED_BODY,
            'status_code': 200,
            'fetched_at': now,
            'expires_at': now + timedelta(hours=1),
        })
        self.env['ai.url.whitelist'].sudo().create({
            'domain': ARCHIVED, 'kind': 'web', 'active': False,
        })
        self.skill = self.env['ai.skill'].sudo().create({
            'code': f'seges_e1_skill_{uuid.uuid4().hex[:8]}',
            'name': 'Seges E1 skill',
            'description': 'seges e1',
            'content': 'seges e1',
        })
        self.env['ai.skill.param.cache'].sudo().create({
            'skill_id': self.skill.id,
            'unresolved': 'seges e1 seed',
            'params_json': '{"seed": "1"}',
        })
        self.env['ai.key.pin.block'].sudo().create({
            'ip': BLOCKED_IP,
            'failures': 0,
            'blocked_until': now + timedelta(hours=1),
        })

    def _rpc(self, login, model, method, args, kwargs=None):
        self.env['base'].flush()
        self.authenticate(login, login)
        payload = {
            'jsonrpc': '2.0', 'method': 'call', 'id': 1,
            'params': {
                'model': model, 'method': method,
                'args': args, 'kwargs': kwargs or {},
            },
        }
        resp = self.url_open(
            f'/web/dataset/call_kw/{model}/{method}',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        return resp.json()

    def _assert_refused(self, res, private):
        self.assertNotIn('result', res, res)
        expected = (
            'odoo.exceptions.AccessError' if private
            else 'builtins.AttributeError'
        )
        self.assertEqual(res['error']['data']['name'], expected, res)

    def _snapshot(self):
        self.env['base'].flush()
        snap = []
        for query in (
            'SELECT id, url_hash, body, expires_at FROM ai_fetch_cache ORDER BY id',
            'SELECT id, domain, kind, active, notes FROM ai_url_whitelist ORDER BY id',
            'SELECT id, skill_id, key, params_json FROM ai_skill_param_cache ORDER BY id',
            'SELECT id, ip, failures, blocked_until FROM ai_key_pin_block ORDER BY id',
        ):
            self.cr.execute(query)
            snap.append(self.cr.fetchall())
        return snap

    def _logins(self):
        return ('seges_e1_internal', 'seges_e1_portal')

    def _run_calls(self, calls):
        """Ejecuta (modelo, método, args, privado) con U y P; devuelve respuestas."""
        before = self._snapshot()
        responses = []
        with mute_logger('odoo.http'):
            for login in self._logins():
                for model, method, args, private in calls:
                    res = self._rpc(login, model, method, args)
                    self._assert_refused(res, private)
                    responses.append(json.dumps(res))
        self.assertEqual(self._snapshot(), before)
        return responses

    def test_control_session_ok(self):
        # Control: método del core al que pueden llamar internos y portal.
        for login in self._logins():
            res = self._rpc(login, 'res.users', 'context_get', [])
            self.assertIn('result', res, res)
            self.assertIsInstance(res['result'], dict)

    def test_fetch_cache_refused(self):
        poison = {'success': True, 'status_code': 200, 'body': 'seges-e1-poison'}
        responses = self._run_calls([
            ('ai.fetch.cache', 'get_cached', [SEED_URL], False),
            ('ai.fetch.cache', 'store', [SEED_URL, poison, 600], False),
            ('ai.fetch.cache', 'store',
             ['https://seges-e1.invalid/new', poison, 600], False),
            ('ai.fetch.cache', '_get_cached', [SEED_URL], True),
            ('ai.fetch.cache', '_store', [SEED_URL, poison, 600], True),
        ])
        for text in responses:
            self.assertNotIn(SEED_BODY, text)

    def test_url_whitelist_refused(self):
        self._run_calls([
            ('ai.url.whitelist', 'ensure_domain_whitelisted',
             ['seges-e1-new.invalid', 'x', 'web'], False),
            ('ai.url.whitelist', 'ensure_domain_whitelisted',
             [ARCHIVED, 'x', 'web'], False),
            ('ai.url.whitelist', '_ensure_domain_whitelisted',
             ['seges-e1-new.invalid', 'x', 'web'], True),
            ('ai.url.whitelist', '_ensure_domain_whitelisted',
             [ARCHIVED, 'x', 'web'], True),
        ])
        Whitelist = self.env['ai.url.whitelist'].with_context(active_test=False)
        self.assertFalse(Whitelist.search([('domain', '=', 'seges-e1-new.invalid')]))
        archived = Whitelist.search([('domain', '=', ARCHIVED)])
        self.assertFalse(archived.active)

    def test_skill_param_cache_refused(self):
        sid = self.skill.id
        responses = self._run_calls([
            ('ai.skill.param.cache', 'remember_for_skill',
             [sid, 'seges e1 phrase', {'k': 'v'}], False),
            ('ai.skill.param.cache', 'lookup_for_skill',
             [sid, 'seges e1 seed'], False),
            ('ai.skill', 'remember_param_cache',
             [[sid], 'seges e1 phrase', {'k': 'v'}], False),
            ('ai.skill', 'lookup_param_cache', [[sid], 'seges e1 seed'], False),
            ('ai.skill.param.cache', '_remember_for_skill',
             [sid, 'seges e1 phrase', {'k': 'v'}], True),
            ('ai.skill.param.cache', '_lookup_for_skill',
             [sid, 'seges e1 seed'], True),
            ('ai.skill', '_remember_param_cache',
             [[sid], 'seges e1 phrase', {'k': 'v'}], True),
            ('ai.skill', '_lookup_param_cache', [[sid], 'seges e1 seed'], True),
        ])
        for text in responses:
            self.assertNotIn('"seed"', text)

    def test_key_pin_refused(self):
        self._run_calls([
            ('ai.mcp.user', 'redeem_key_pin', ['12345678', '203.0.113.9'], False),
            ('ai.key.pin.block', 'release_all', [], False),
            ('ai.key.pin.block', 'note_failure', ['203.0.113.9'], False),
            ('ai.key.pin.block', 'is_blocked', [BLOCKED_IP], False),
            ('ai.mcp.user', '_redeem_key_pin', ['12345678', '203.0.113.9'], True),
            ('ai.key.pin.block', '_release_all', [], True),
            ('ai.key.pin.block', '_note_failure', ['203.0.113.9'], True),
            ('ai.key.pin.block', '_is_blocked', [BLOCKED_IP], True),
        ])
        Block = self.env['ai.key.pin.block'].sudo()
        self.assertTrue(Block._is_blocked(BLOCKED_IP))
        self.assertFalse(Block.search([('ip', '=', '203.0.113.9')]))

    def test_public_names_gone(self):
        for model, old, new in RENAMED:
            klass = type(self.env[model])
            self.assertFalse(hasattr(klass, old), f'{model}.{old}')
            self.assertTrue(hasattr(klass, new), f'{model}.{new}')


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e0')
class TestSegesInternalFlows(TransactionCase):
    """Positivos: los flujos internos siguen funcionando con los nombres nuevos."""

    def setUp(self):
        super().setUp()
        self.user = new_test_user(
            self.env, login='seges_e1_flow_user', groups='base.group_user',
        )
        self.env_u = self.env(user=self.user)
        self.ICP = self.env['ir.config_parameter'].sudo()

    def _fake_response(self):
        class FakeResponse:
            status_code = 200
            headers = requests.structures.CaseInsensitiveDict({
                'Content-Type': 'application/json',
                'Cache-Control': 'max-age=600',
            })
            content = b'{"a": 1}'
            text = '{"a": 1}'

        return FakeResponse()

    def test_fetch_cache_roundtrip(self):
        url = 'https://seges-e1.invalid/roundtrip'
        Cache = self.env_u['ai.fetch.cache']
        Cache._store(url, {
            'success': True, 'status_code': 200,
            'content_type': 'text/plain', 'body': 'b',
        }, 600)
        got = Cache._get_cached(url)
        self.assertEqual(got['body'], 'b')
        self.assertIs(got['_from_cache'], True)

    def test_execute_fetch_url_serves_cache(self):
        url = 'https://seges-e1.invalid/serves-cache'
        self.env_u['ai.fetch.cache']._store(url, {
            'success': True, 'status_code': 200,
            'content_type': 'text/plain', 'body': 'cached',
        }, 600)
        with patch(SAFE_PLAN + '._fetch_url_request',
                   side_effect=AssertionError('network')):
            res = safe_plan._execute_fetch_url(
                self.env_u, {'op': 'fetch_url', 'url': url})
        self.assertTrue(res['success'])
        self.assertIs(res['_from_cache'], True)

    def test_execute_fetch_url_stores_cacheable(self):
        url = 'https://seges-e1.invalid/stores-cacheable'
        step = {'op': 'fetch_url', 'url': url}
        with patch(SAFE_PLAN + '._fetch_url_request',
                   return_value=(self._fake_response(), '')) as mocked:
            first = safe_plan._execute_fetch_url(self.env_u, step)
            self.assertTrue(first['success'])
            self.assertEqual(mocked.call_count, 1)
            rows = self.env['ai.fetch.cache'].sudo().search([
                ('url_hash', '=', hashlib.sha256(url.encode('utf-8')).hexdigest()),
            ])
            self.assertEqual(len(rows), 1)
            second = safe_plan._execute_fetch_url(self.env_u, step)
            self.assertIs(second.get('_from_cache'), True)
            self.assertEqual(mocked.call_count, 1)

    def test_whitelist_internal_paths(self):
        Whitelist = self.env['ai.url.whitelist'].sudo().with_context(
            active_test=False)
        # (a) alta directa
        self.assertTrue(self.env_u['ai.url.whitelist']._ensure_domain_whitelisted(
            'seges-e1-flow.invalid', 'n', 'web'))
        row = Whitelist.search([('domain', '=', 'seges-e1-flow.invalid')])
        self.assertTrue(row.active)
        # (b) reactivación con whitelist_only
        self.ICP.set_param('pns_ai_mcp.url_access_policy', 'whitelist_only')
        archived = Whitelist.create({
            'domain': ARCHIVED, 'kind': 'web', 'active': False})
        safe_plan._ensure_fetch_url_whitelist(
            self.env_u, {'url': f'https://{ARCHIVED}/x'})
        archived.invalidate_cache()
        self.assertTrue(archived.active)
        # (c) con política open la petición se deja pasar, pero desde 3.1.879
        # no se da de alta el dominio (safe_plan._ensure_fetch_url_whitelist).
        self.ICP.set_param('pns_ai_mcp.url_access_policy', 'open')
        safe_plan._ensure_fetch_url_whitelist(
            self.env_u, {'url': 'https://seges-e1-open.invalid/'})
        row = Whitelist.search([('domain', '=', 'seges-e1-open.invalid')])
        self.assertFalse(row)

    def test_skill_param_cache_roundtrip(self):
        skill = self.env['ai.skill'].create({
            'code': f'seges_e1_flow_{uuid.uuid4().hex[:8]}',
            'name': 'Seges E1 flow',
            'description': 'seges e1',
            'content': 'seges e1',
        })
        Cache = self.env['ai.skill.param.cache']
        # TransactionCase usa un cursor real: sin este parche la escritura se
        # haría con un cursor propio y commit (fuera de los tests es lo normal).
        with patch.object(type(Cache), '_own_cursor_env', return_value=False):
            skill_u = skill.with_user(self.user)
            skill_u._remember_param_cache('Seges  E1   frase', {'k': 'v'})
            row = Cache.sudo().search([('skill_id', '=', skill.id)])
            self.assertEqual(len(row), 1)
            self.assertEqual(
                skill_u._lookup_param_cache('seges e1 FRASE'), {'k': 'v'})
            skill_u._remember_param_cache('seges e1 frase', {'k': 'otro'})
            self.assertEqual(
                skill_u._lookup_param_cache('seges e1 frase'), {'k': 'v'})
            self.assertEqual(
                Cache.sudo().search_count([('skill_id', '=', skill.id)]), 1)

    def test_agent_engine_uses_private_names(self):
        # 3.1.879: el método vive en el mixin de utils/engine_skills.py.
        source = inspect.getsource(SkillsMixin._normalize_skill_params)
        self.assertIn("'_lookup_param_cache'", source)
        self.assertIn("'_remember_param_cache'", source)
        self.assertNotIn("getattr(skill, 'lookup_param_cache'", source)
        self.assertNotIn("getattr(skill, 'remember_param_cache'", source)

    def test_no_caller_uses_public_names(self):
        patterns = [re.compile(p) for p in (
            r"\['ai\.fetch\.cache'\]\.(get_cached|store)\(",
            r"\.ensure_domain_whitelisted\(",
            r"\.(remember_for_skill|lookup_for_skill)\(",
            r"'(lookup|remember)_param_cache'",
            r"\.(redeem_key_pin|release_all|note_failure|is_blocked)\(",
        )]
        found = []
        for module in ('pns_ai_mcp', 'pns_ai_chatboo', 'pns_base'):
            path = get_module_path(module)
            if not path:
                continue
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in ('tests', 'node_modules')]
                for fname in files:
                    if not fname.endswith(('.py', '.xml')):
                        continue
                    fpath = os.path.join(root, fname)
                    with open(fpath, encoding='utf-8') as handle:
                        for num, line in enumerate(handle, 1):
                            if any(p.search(line) for p in patterns):
                                found.append(f'{fpath}:{num}')
        self.assertEqual(found, [])

    def test_key_pin_block_flow(self):
        self.ICP.set_param('pns_ai_mcp.key_pin_attempts', '1')
        Block = self.env['ai.key.pin.block'].sudo()
        ip = '203.0.113.20'
        self.assertFalse(Block._note_failure(ip))
        self.assertTrue(Block._note_failure(ip))
        self.assertTrue(Block._is_blocked(ip))
        admin = new_test_user(
            self.env, login='seges_e1_flow_admin',
            groups='base.group_user,base.group_system,pns_ai_mcp.group_ai_admin',
        )
        settings = self.env['res.config.settings'].with_user(admin).create({})
        result = settings.action_key_pin_release()
        self.assertTrue(result)
        self.assertFalse(Block._is_blocked(ip))

    def test_redeem_key_pin_python(self):
        self.ICP.set_param('pns_ai_mcp.key_pin_attempts', '5')
        User = self.env['ai.mcp.user']
        self.assertEqual(
            User._redeem_key_pin('abc'),
            {'ok': False, 'error': 'invalid', 'counted': False},
        )
        # 3.1.879: sin una mesa del PIN abierta no hay canje ni se cuenta el
        # intento. El intento contado pasa por collect_pin (PNS-83, entrega E1′).
        res = User._redeem_key_pin('12345678', '203.0.113.21')
        self.assertEqual(
            res, {'ok': False, 'error': 'no_desk', 'counted': False})
        block = self.env['ai.key.pin.block'].sudo().search(
            [('ip', '=', '203.0.113.21')])
        self.assertFalse(block)


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e0')
class TestSegesSandboxDenylist(TransactionCase):
    """El sandbox rechaza los nombres privados (en 3.1.879, todos los que
    empiezan por `_`, no una lista de nombres)."""

    def test_names_in_denylist(self):
        for name in NEW_NAMES:
            self.assertTrue(blocked_private_attr(name), name)

    def test_guarded_getattr_and_methodcaller(self):
        for name in NEW_NAMES:
            with self.assertRaises(AttributeError):
                guarded_getattr(object(), name)
            with self.assertRaises(AttributeError):
                guarded_methodcaller(name)

    def _assert_private_rejected(self, code, label):
        valid, error, requires_write = validate_relaxaicode_source_ast(code)
        self.assertFalse(valid, label)
        self.assertEqual(ast_error_code(error), 'PRIVATE_ATTR', error)
        self.assertFalse(requires_write, label)

    def test_ast_flags_literal_and_static_getattr(self):
        # 3.1.879: el AST rechaza el nombre privado (antes lo marcaba como
        # escritura), también si se compone con '_st' + 'ore'.
        for name in NEW_NAMES:
            code = (
                f"x = env['ai.fetch.cache'].{name}('a')\n"
                "result = {'data': 1}\n"
            )
            self._assert_private_rejected(code, name)
        code = (
            "x = getattr(env['ai.fetch.cache'], '_st' + 'ore')('a')\n"
            "result = {'data': 1}\n"
        )
        self._assert_private_rejected(code, 'getattr')
        control = (
            "x = env['res.partner'].search_count([])\n"
            "result = {'data': x}\n"
        )
        self.assertEqual(
            validate_relaxaicode_source_ast(control), (True, None, False))
