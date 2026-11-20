# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 38 (PNS-105, datos). Ver docs/pendiente/parches_pns_ai.md
"""PNS-105: a side cursor with an Environment must not touch the caller's pending work.

``ai.log._create_log_entry`` (like every own cursor of the inventory) opens its own cursor,
builds an Environment on it and commits. In Odoo 14, ``Cursor.commit`` calls ``flush_env``
(odoo/sql_db.py:448-457, at :451), which flushes ``towrite``; ``towrite`` belongs to the
whole thread (odoo/api.py:757-765), not to the cursor. Without patch 38 the caller's pending
writes were written and committed in the side transaction:

* on a confirmed record, they survived the caller's rollback;
* on a record created in the caller's transaction, the side cursor could not see the row,
  ``flush`` retried with ``exists()`` (odoo/models.py:5479-5482) and the write was lost.

The first three tests confirmed the finding (they failed before patch 38) and now guard the
fix. ``TestSegesSideEnv`` tests the helper itself (``pns_base/utils/seges_side_env.py``).

The log is off while tests run (``test_is_running``), so it is patched here. Side cursors
(checks and cleanup) use plain SQL and no Environment, so their own commit does not flush the
test's pending writes. The test database is disposable.
"""

import re
import secrets

import psycopg2
from psycopg2 import errorcodes

import odoo
from odoo import SUPERUSER_ID, api, http
from odoo.modules.registry import Registry
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import get_db_name

import odoo.addons.pns_base.utils.seges_side_env as side_env_module
from odoo.addons.pns_ai_mcp.controllers import safe_plan_http
from odoo.addons.pns_ai_mcp.lib.api import drivers as api_drivers
from odoo.addons.pns_ai_mcp.models import ai_log as ai_log_module
from odoo.addons.pns_ai_mcp.tests._helpers import grant_groups, revoke_groups
from odoo.addons.pns_ai_mcp.utils import api_call_result

PROBE_ENDPOINT = 'seges_3b_probe'
PRECONDITION = 'PRECONDITION (not the PNS-105 result): '
BOX_B_PREFIX = 'seges-pns105-b-'
BOX_B_GROUPS = ('pns_ai_mcp.group_ai_writer', 'pns_ai_mcp.group_ai_external_api')
BOX_B_RESULT = (
    "PNS-105 (box B): step 2's own cursor waited for a row the plan cursor had already "
    "updated (lock timeout in the test; _store sets none, so in production the worker hangs)"
)
# Table of a SQL template (never its parameters).
_WRITE_TABLE = re.compile(
    r'^\s*(?:UPDATE\s+(?:ONLY\s+)?|INSERT\s+INTO\s+|DELETE\s+FROM\s+)"?(\w+)"?', re.I)
_LOCK_TABLE = re.compile(r'\bFROM\s+"?(\w+)"?.*\bFOR\s+(?:NO\s+KEY\s+)?UPDATE\b', re.I | re.S)


def _table_of(query):
    if not isinstance(query, str):
        return '?'
    found = _WRITE_TABLE.match(query) or _LOCK_TABLE.search(query)
    return found.group(1) if found else '?'


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesSideCursorCommit(TransactionCase):
    """PNS-105: ``_create_log_entry`` commits and drops the caller's pending writes."""

    def setUp(self):
        super().setUp()
        self.patch(ai_log_module, 'test_is_running', lambda *args, **kwargs: False)
        self.admin = self.env.ref('base.user_admin')
        self.marker = 'seges-pns105-' + secrets.token_hex(4)
        self.env['base'].flush()

    # -- side cursors: plain SQL, no Environment --------------------------

    def _side_comment(self, partner_id):
        """Read ``comment`` from a separate cursor (never commits)."""
        cr = self.registry.cursor()
        try:
            cr.execute('SELECT comment FROM res_partner WHERE id = %s', (partner_id,))
            row = cr.fetchone()
            return row[0] if row else None
        finally:
            cr.rollback()
            cr.close()

    def _side_log_exists(self, log_id):
        """True when the probe row is committed and visible from a separate cursor."""
        cr = self.registry.cursor()
        try:
            cr.execute(
                'SELECT 1 FROM ai_log WHERE id = %s AND endpoint = %s',
                (log_id, PROBE_ENDPOINT),
            )
            return bool(cr.fetchone())
        finally:
            cr.rollback()
            cr.close()

    def _cleanup(self, partner_id=None, original=None):
        """Restore ``comment`` and delete the probe rows, on a new cursor."""
        # Release any row lock the test transaction may hold before touching the row.
        self.env.cr.rollback()
        cr = self.registry.cursor()
        try:
            if partner_id:
                cr.execute(
                    'UPDATE res_partner SET comment = %s WHERE id = %s',
                    (original, partner_id),
                )
            cr.execute('DELETE FROM ai_log WHERE endpoint = %s', (PROBE_ENDPOINT,))
            cr.commit()  # pylint: disable=invalid-commit
        finally:
            cr.close()

    # -- helpers ----------------------------------------------------------

    def _pending_comment(self, partner):
        towrite = self.env.all.towrite.get('res.partner', {})
        return 'comment' in towrite.get(partner.id, {})

    def _call_log(self):
        log = self.env['ai.log'].sudo()._create_log_entry(
            user_id=self.admin.id,
            operation_type='read',
            tool_name=PROBE_ENDPOINT,
        )
        self.assertTrue(log, PRECONDITION + '_create_log_entry returned no record')
        self.assertTrue(
            self._side_log_exists(log.id),
            PRECONDITION + 'the probe ai.log row is not visible from a separate cursor',
        )
        return log

    # -- tests ------------------------------------------------------------

    def test_log_commits_caller_pending_write(self):
        """PNS-105: a pending write on a confirmed record is committed by the log's cursor.

        Correct behaviour: the write is neither visible from a separate cursor after the
        call nor surviving the caller's rollback.
        """
        partner = self.env.ref('base.main_partner')
        original = self._side_comment(partner.id)
        self.addCleanup(self._cleanup, partner.id, original)

        partner.write({'comment': self.marker})
        self.assertTrue(
            self._pending_comment(partner),
            PRECONDITION + 'comment is not pending in towrite before the call',
        )
        self._call_log()

        confirmed_outside = self._side_comment(partner.id) == self.marker
        self.env.cr.rollback()
        survived_rollback = self._side_comment(partner.id) == self.marker

        happened = []
        if confirmed_outside:
            happened.append('the pending write was committed outside the test transaction')
        if survived_rollback:
            happened.append("the pending write survived the test transaction's rollback")
        self.assertFalse(
            confirmed_outside or survived_rollback,
            'PNS-105: ' + '; '.join(happened),
        )

    def test_log_drops_pending_write_on_new_record(self):
        """PNS-105: a pending write on a record created by the caller is lost.

        Correct behaviour: after the call, the caller's flush still writes the marker.
        """
        self.addCleanup(self._cleanup)

        partner = self.env['res.partner'].create({'name': 'Seges PNS-105 probe'})
        partner.flush()
        partner.write({'comment': self.marker})
        self.assertTrue(
            self._pending_comment(partner),
            PRECONDITION + 'comment is not pending in towrite before the call',
        )
        self._call_log()

        partner.flush()
        self.env.cr.execute('SELECT comment FROM res_partner WHERE id = %s', (partner.id,))
        self.assertEqual(
            self.env.cr.fetchone()[0],
            self.marker,
            'PNS-105: the pending write on a record created in the test transaction was lost '
            '(flushed on the side cursor, which cannot see the row, then cleared)',
        )


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesSideCursorBoxB(TransactionCase):
    """PNS-105, box B: step 2's own cursor (``ai.api.result.cache._store``) flushes the plan.

    Plan: (1) ``write`` of ``email`` on a contact P; (2) ``api_call``. Step 1 writes P's row on
    the plan cursor and leaves ``email_normalized`` of P to compute. ``_store`` opens its own
    cursor with an Environment and commits: the commit computes it and updates P's row on that
    cursor, which waits for the plan cursor in the same thread.

    The only check is whether a cursor opened during step 2 hit a lock timeout. A guard gives
    those cursors ``lock_timeout = '3s'``: it only changes times, and turns the hang into an
    error. Side cursors (checks and cleanup) use plain SQL and no Environment.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tag = BOX_B_PREFIX + secrets.token_hex(4)
        cls.rid = {}
        cls.granted = []
        try:
            cls._create_committed()
        except Exception:
            cls._remove_committed()
            raise

    @classmethod
    def _create_committed(cls):
        with odoo.registry(get_db_name()).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            if any(env.all.towrite.values()) or any(env.all.tocompute.values()):
                raise AssertionError(
                    PRECONDITION + 'towrite or tocompute not empty before creating the data')
            admin = env.ref('base.user_admin')
            cls.admin_uid = admin.id
            cls.granted = grant_groups(admin, BOX_B_GROUPS)
            partner = env['res.partner'].create({
                'name': cls.tag, 'email': cls.tag + '-ini@example.com',
            })
            cls.rid['partner'] = partner.id
            server = env['ai.api.server'].create({'name': cls.tag, 'code': cls.tag})
            cls.rid['server'] = server.id
            steps = [
                {'op': 'write', 'model': 'res.partner', 'ids': [partner.id],
                 'values': {'email': cls.tag + '@example.com'}},
                {'op': 'api_call', 'server': cls.tag, 'tool': 'seges_probe', 'arguments': {}},
            ]
            cls.title = 'Seges PNS-105 box B'
            plan = ['write 1 res.partner', 'api_call ' + cls.tag]
            op = env['ai.safe.operation'].create_verification(
                operation_type='write',
                model_name='res.partner',
                records_count=2,
                changes_info={'plan': plan, 'danger_level': 'low'},
                user_id=admin.id,
                tool_name='seges_pns105_b',
                operation_data={
                    'plan_steps': steps, 'title': cls.title,
                    'plan': plan, 'danger_level': 'low',
                },
            )
            cls.rid['op'] = op.id
            op.with_user(admin)._confirm_by_user()
            cls.vid = op.verification_id
            env['base'].flush()
            cr.execute(
                'SELECT email, email_normalized FROM res_partner WHERE id = %s', (partner.id,))
            cls.initial = cr.fetchone()
            cr.commit()  # pylint: disable=invalid-commit

    @classmethod
    def _remove_committed(cls):
        """Delete the committed rows (plain SQL), then give back the groups."""
        left = []
        if cls.rid:
            cr = odoo.registry(get_db_name()).cursor()
            try:
                statements = (
                    ('journal', 'DELETE FROM ai_change_journal WHERE safe_operation_id = %s',
                     cls.rid.get('op')),
                    ('op', 'DELETE FROM ai_safe_operation WHERE id = %s', cls.rid.get('op')),
                    ('cache', 'DELETE FROM ai_api_result_cache WHERE server_code = %s', cls.tag),
                    ('server', 'DELETE FROM ai_api_server WHERE id = %s', cls.rid.get('server')),
                    ('partner', 'DELETE FROM res_partner WHERE id = %s', cls.rid.get('partner')),
                )
                for key, query, value in statements:
                    if not value:
                        continue
                    try:
                        with cr.savepoint():
                            cr.execute(query, (value,))
                    except psycopg2.Error:
                        left.append(key)
                cr.commit()  # pylint: disable=invalid-commit
            finally:
                cr.close()
            cls.rid = {}
        if cls.granted:
            # revoke_groups needs the ORM: its own cursor, after the SQL cleanup.
            with odoo.registry(get_db_name()).cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                revoke_groups(env.ref('base.user_admin'), cls.granted)
                cr.commit()  # pylint: disable=invalid-commit
            cls.granted = []
        if left:
            raise AssertionError('incomplete cleanup: ' + ', '.join(left))

    def setUp(self):
        super().setUp()
        self.guard_on = False
        self.waits = []
        self.spy = {}
        self.addCleanup(self._cleanup)
        self._patch_guard()
        self.patch(api_drivers, 'get_api_driver', lambda api_type: _SpyDriver(self))
        self.patch(safe_plan_http, '_api_call_schema_error', lambda *args, **kwargs: None)
        self.patch(api_call_result, 'format_api_call_body_for_llm', self._stop_step_2)
        self.env['base'].flush()

    def _cleanup(self):
        self.guard_on = False
        self.env.cr.rollback()
        type(self)._remove_committed()

    # -- guard: lock timeout on the cursors opened during step 2 ---------------

    def _patch_guard(self):
        test = self
        original_cursor = Registry.cursor

        def guarded_cursor(registry, *args, **kwargs):
            cr = original_cursor(registry, *args, **kwargs)
            if test.guard_on:
                cr.execute("SET LOCAL lock_timeout = '3s'")
                original_execute = cr.execute

                def execute(query, params=None, log_exceptions=None):
                    try:
                        return original_execute(query, params, log_exceptions)
                    except psycopg2.Error as exc:
                        if getattr(exc, 'pgcode', None) == errorcodes.LOCK_NOT_AVAILABLE:
                            test.waits.append(_table_of(query))
                        raise

                cr.execute = execute
            return cr

        self.patch(Registry, 'cursor', guarded_cursor)

    def _stop_step_2(self, *args, **kwargs):
        """Step 2 fails after ``_store``: the plan rolls back."""
        self.guard_on = False
        raise RuntimeError('PNS-105 box B: step 2 stops after _store')

    def _side_partner_unchanged(self):
        """Control (not the result): P keeps its committed values. Plain SQL."""
        cr = self.registry.cursor()
        try:
            cr.execute(
                'SELECT email, email_normalized FROM res_partner WHERE id = %s',
                (self.rid['partner'],))
            row = cr.fetchone() or (None, None)
            return row[0] == self.initial[0], row[1] == self.initial[1]
        finally:
            cr.rollback()
            cr.close()

    # -- test -------------------------------------------------------------------

    def test_box_b_side_cursor_waits_for_plan_row(self):
        """PNS-105, box B: ``_store`` must not wait for a row the plan cursor updated."""
        self.assertFalse(
            any(self.env.all.towrite.values()),
            PRECONDITION + 'towrite is not empty at the start',
        )
        admin = self.env['res.users'].browse(self.admin_uid)
        self.assertTrue(
            all(admin.has_group(group) for group in BOX_B_GROUPS),
            PRECONDITION + 'admin lacks the plan or api_call group',
        )

        plan = None
        try:
            out = self.env['ai.safe.operation']._execute_plan_with_timeouts(
                self.rid['op'], self.admin_uid, {}, self.vid, self.title,
            )
            plan = f"status={(out or {}).get('status')}"
        except Exception as exc:  # pylint: disable=broad-exception-caught
            plan = f'exception={type(exc).__name__}'
        finally:
            self.guard_on = False

        email_kept, normalized_kept = self._side_partner_unchanged()

        self.assertTrue(self.spy.get('ran'), PRECONDITION + 'the spy (driver.call) did not run')
        self.assertFalse(
            self.spy.get('error'),
            PRECONDITION + f"the spy failed: {self.spy.get('error')}",
        )
        self.assertFalse(
            self.spy.get('email_in_towrite'),
            PRECONDITION + "P still has 'email' in towrite at step 2 (step 1 did not flush it)",
        )
        self.assertTrue(
            self.spy.get('p_in_tocompute'),
            PRECONDITION + 'P is not in tocompute of email_normalized at step 2',
        )
        self.assertFalse(
            self.waits,
            f"{BOX_B_RESULT}. Waits on: {', '.join(self.waits)}; plan: {plan}; "
            f"control: email kept={email_kept}, email_normalized kept={normalized_kept}",
        )


class _SpyDriver:
    """``get_api_driver`` stub: notes what is pending at step 2 and turns the guard on."""

    def __init__(self, test):
        self.test = test

    def call(self, server, tool_name, arguments=None, auth_token=None):
        spy = self.test.spy
        spy['ran'] = True
        try:
            pending = server.env.all
            partner_id = self.test.rid['partner']
            row = pending.towrite.get('res.partner', {}).get(partner_id, {})
            spy['email_in_towrite'] = 'email' in row
            field = server.env['res.partner']._fields['email_normalized']
            spy['p_in_tocompute'] = partner_id in pending.tocompute.get(field, ())
        except Exception as exc:  # pylint: disable=broad-exception-caught
            spy['error'] = type(exc).__name__
        self.test.guard_on = True
        return '{"ok": true}'


# Seges: parche 38 (PNS-105, datos). Ver docs/pendiente/parches_pns_ai.md
SIDE_ENV_LOGGER = 'odoo.addons.pns_base.utils.seges_side_env'
SIDE_ENV_TAG = 'seges_side_env: '


class _FakeRequest:
    """Minimal request for ``http._request_stack``: cursor open, ``env`` not built yet."""

    def __init__(self, cr, uid):
        self._cr = cr
        self._env = None
        self.uid = uid
        self.context = {'seges_pns105_req': 1}

    @property
    def cr(self):
        return self._cr

    @property
    def env(self):
        # Same as WebRequest.env (odoo/http.py:256-261).
        if self._env is None:
            self._env = odoo.api.Environment(self.cr, self.uid, self.context)
        return self._env


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesSideEnv(TransactionCase):
    """Parche 38: ``seges_side_env`` isolates a side cursor's Environment from the caller's.

    Side cursors outside the helper (checks and cleanup) use plain SQL and no Environment.
    """

    def setUp(self):
        super().setUp()
        self.admin = self.env.ref('base.user_admin')
        self.env['base'].flush()

    # -- side cursors: plain SQL, no Environment --------------------------

    def _sql_comment(self, partner_id):
        cr = self.registry.cursor()
        try:
            cr.execute('SELECT comment FROM res_partner WHERE id = %s', (partner_id,))
            row = cr.fetchone()
            return row[0] if row else None
        finally:
            cr.rollback()
            cr.close()

    def _restore_comment(self, partner_id, original):
        self.env.cr.rollback()
        cr = self.registry.cursor()
        try:
            cr.execute(
                'UPDATE res_partner SET comment = %s WHERE id = %s', (original, partner_id))
            cr.commit()  # pylint: disable=invalid-commit
        finally:
            cr.close()

    def _cleanup_probe_log(self):
        self.env.cr.rollback()
        cr = self.registry.cursor()
        try:
            cr.execute('DELETE FROM ai_log WHERE endpoint = %s', (PROBE_ENDPOINT,))
            cr.commit()  # pylint: disable=invalid-commit
        finally:
            cr.close()

    def _pop_request(self, fake):
        if http._request_stack.top is fake:
            http._request_stack.pop()

    # -- tests ------------------------------------------------------------

    def test_side_cursor_keeps_caller_cache_and_new(self):
        """The log's own cursor no longer clears the caller's cache or its new() records."""
        self.patch(ai_log_module, 'test_is_running', lambda *args, **kwargs: False)
        self.addCleanup(self._cleanup_probe_log)

        partner = self.env.ref('base.main_partner')
        name_field = partner._fields['name']
        self.assertTrue(partner.name, PRECONDITION + 'base.main_partner has no name')
        self.assertTrue(
            self.env.cache.contains(partner, name_field),
            PRECONDITION + 'the name of base.main_partner is not in the cache',
        )
        marker = 'seges-pns105-new-' + secrets.token_hex(4)
        new_partner = self.env['res.partner'].new({'name': marker})
        self.assertTrue(
            self.env.cache.contains(new_partner, name_field),
            PRECONDITION + 'the name of the new() record is not in the cache',
        )

        log = self.env['ai.log'].sudo()._create_log_entry(
            user_id=self.admin.id,
            operation_type='read',
            tool_name=PROBE_ENDPOINT,
        )
        self.assertTrue(log, PRECONDITION + '_create_log_entry returned no record')

        self.assertTrue(
            self.env.cache.contains(partner, name_field),
            "PNS-105: the side cursor cleared the caller's cache",
        )
        self.assertTrue(
            self.env.cache.contains(new_partner, name_field)
            and new_partner.name == marker,
            'PNS-105: the side cursor cleared the value of the caller\'s new() record',
        )

    def test_nested_side_env_restores_stack(self):
        """Nested blocks restore each previous set; the inner commit does not flush the outer."""
        partner_id = self.env.ref('base.main_partner').id
        original = self._sql_comment(partner_id)
        self.addCleanup(self._restore_comment, partner_id, original)
        marker = 'seges-pns105-n-' + secrets.token_hex(4)
        local = api.Environment._local
        caller_set = local.environments

        with side_env_module.seges_side_env():
            outer_set = local.environments
            cr_o = self.registry.cursor()
            try:
                cr_o.execute("SET LOCAL lock_timeout = '3s'")
                env_o = api.Environment(cr_o, SUPERUSER_ID, {})
                env_o['res.partner'].browse(partner_id).write({'comment': marker})

                def outer_pending():
                    towrite = env_o.all.towrite.get('res.partner', {})
                    return 'comment' in towrite.get(partner_id, {})

                self.assertTrue(
                    outer_pending(),
                    PRECONDITION + 'comment is not pending in the outer towrite',
                )
                with side_env_module.seges_side_env(), self.registry.cursor() as cr_i:
                    cr_i.execute("SET LOCAL lock_timeout = '3s'")
                    env_i = api.Environment(cr_i, SUPERUSER_ID, {})
                    inner_is_new = local.environments is not outer_set
                    inner_env_apart = env_i.all is not outer_set
                self.assertTrue(
                    inner_is_new and inner_env_apart,
                    'PNS-105: the inner block did not get a set of its own',
                )
                self.assertIs(
                    local.environments, outer_set,
                    'PNS-105: the inner block did not restore the outer set',
                )
                self.assertTrue(
                    outer_pending(),
                    "PNS-105: the inner commit flushed the outer block's pending write",
                )
            finally:
                cr_o.rollback()
                cr_o.close()

        self.assertIs(
            local.environments, caller_set,
            "PNS-105: the outer block did not restore the caller's set",
        )
        self.assertFalse(
            self._sql_comment(partner_id) == marker,
            'PNS-105: the outer pending write was committed',
        )

    def test_request_env_forced_before_swap(self):
        """With a request cursor open, request.env is built in the caller's set."""
        fake = _FakeRequest(self.env.cr, self.env.uid)
        self.addCleanup(self._pop_request, fake)
        http._request_stack.push(fake)
        caller_set = api.Environment._local.environments

        with side_env_module.seges_side_env():
            temp = api.Environment._local.environments

        self.assertIsNotNone(fake._env, 'PNS-105: request.env was not built before the swap')
        self.assertIs(fake._env.cr, self.env.cr, "PNS-105: request.env is not on the request's cursor")
        self.assertIs(fake._env.all, caller_set, "PNS-105: request.env is not in the caller's set")
        self.assertNotIn(fake._env, list(temp), 'PNS-105: request.env is in the temporary set')

    def test_caller_env_inside_side_env_fails_in_tests(self):
        """An Environment on the caller's cursor created inside the block fails in tests."""
        made = []  # keeps the Environment alive: the set is a WeakSet
        with self.assertLogs(SIDE_ENV_LOGGER, 'ERROR') as logs:
            with self.assertRaisesRegex(
                    AssertionError, r'^seges_side_env: [1-9][0-9]* caller environment'):
                with side_env_module.seges_side_env():
                    made.append(self.env['res.partner'].with_context(seges_pns105=1))
        self.assertTrue(
            any(record.getMessage().startswith(SIDE_ENV_TAG) for record in logs.records),
            'PNS-105: no ERROR with the seges_side_env tag',
        )

    def test_caller_env_inside_side_env_warns_in_production(self):
        """Outside tests, the same case logs a WARNING with the fixed tag."""
        self.patch(side_env_module, '_in_tests', lambda: False)
        made = []  # keeps the Environment alive: the set is a WeakSet
        with self.assertLogs(SIDE_ENV_LOGGER, 'WARNING') as logs:
            with side_env_module.seges_side_env():
                made.append(self.env['res.partner'].with_context(seges_pns105=1))
        self.assertTrue(
            any(record.getMessage().startswith(SIDE_ENV_TAG) for record in logs.records),
            'PNS-105: no WARNING with the seges_side_env tag',
        )

    def test_caller_pending_changed_inside_side_env_fails_in_tests(self):
        """A change to the caller's pending computes inside the block fails in tests."""
        field = self.env['res.partner']._fields['display_name']
        partner = self.env.ref('base.main_partner')
        try:
            with self.assertLogs(SIDE_ENV_LOGGER, 'ERROR') as logs:
                with self.assertRaisesRegex(
                        AssertionError, r'^seges_side_env: 0 caller environment.*changed: yes'):
                    with side_env_module.seges_side_env():
                        self.env.add_to_compute(field, partner)
        finally:
            self.env.remove_to_compute(field, partner)
        self.assertTrue(
            any(record.getMessage().startswith(SIDE_ENV_TAG) for record in logs.records),
            'PNS-105: no ERROR with the seges_side_env tag',
        )
