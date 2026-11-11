# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""The sandbox fences, checked against the Odoo that is installed.

``is_db_handle`` matches classes by module and name, and ``GuardedSandboxEnv``
lets through a fixed list of env attributes. A new Odoo series can move a
class or add a public attribute; these tests then fail on that series
instead of the sandbox quietly opening.
"""
import json

from odoo.tests import tagged, TransactionCase
from odoo.tools import mute_logger

from odoo.addons.pns_ai_mcp.controllers.context_builder import (
    GuardedSandboxEnv,
    is_db_handle,
)
from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import (
    tool_relaxaicode,
)


class _SameCursorController(object):
    """Runs the tool on the test cursor: a box A cursor would leave the test."""

    def __init__(self, env):
        self.env = env

    def _get_env_for_operation(self, operation_type='read'):
        return self.env

    def _get_readonly_env(self):
        return self.env, None

    def _check_mcp_permissions(self, operation_type):
        return True, ''

    def _cancel_pending_verifications_for_user(self, user_id, reason=''):
        return 0

    def _get_user_locale(self):
        return self.env.user.lang or 'en_US'

    def _get_company_lang(self):
        return False

    def _log_mcp_operation(self, *args, **kwargs):
        return None


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestSandboxLiveHandles(TransactionCase):

    def test_live_connection_objects_are_handles(self):
        env = self.env
        live = {
            'env': env,
            'type(env)': type(env),
            'env.cr': env.cr,
            'env.registry': env.registry,
        }
        for name in ('all', 'cache', 'transaction'):
            value = getattr(env, name, None)
            if value is not None:
                live['env.%s' % name] = value
        for name in ('_obj', '_cnx'):
            value = getattr(env.cr, name, None)
            if value is not None:
                live['env.cr.%s' % name] = value
        for label, value in live.items():
            self.assertTrue(
                is_db_handle(value),
                '%s (%s.%s) is not recognised as a database handle'
                % (label, type(value).__module__, type(value).__name__),
            )

    def test_a_database_error_cursor_is_a_handle(self):
        with self.assertRaises(Exception) as caught, mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.env.cr.execute("SELECT 'not-a-date'::date")
        cursor = getattr(caught.exception, 'cursor', None)
        if cursor is not None:
            self.assertTrue(is_db_handle(cursor), type(cursor))

    def test_every_public_env_attribute_is_allowed_or_refused(self):
        guarded = GuardedSandboxEnv(self.env)
        allowed = GuardedSandboxEnv._ALLOWED_ENV_ATTRS | set(
            GuardedSandboxEnv._WRAP_METHODS)
        for name in dir(self.env):
            if name.startswith('_') or name in allowed:
                continue
            if name in ('get',):
                continue
            with self.assertRaises(AttributeError, msg=name):
                getattr(guarded, name)

    def test_engine_paints_with_the_real_env(self):
        resp = tool_relaxaicode(
            _SameCursorController(self.env),
            {'code': "result = [{'name': env.user.name, 'lang': env.lang}]",
             'return_mode': 'inspect_result'},
        )
        text = json.dumps(resp, default=str, ensure_ascii=False)
        self.assertNotIn('ERROR (', text, text[:400])
        self.assertIn(self.env.user.name, text)
