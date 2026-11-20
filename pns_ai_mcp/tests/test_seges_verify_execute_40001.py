# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: test de confirmación del anexo de PNS-26, sin parche. Ver docs/pendiente/propuesta_fase3_3973.md
"""PNS-26 annex: ``/pns_ai_mcp/verification/execute`` and the request's REPEATABLE READ snapshot.

Already recorded on 3.1.879 (docs/pendiente/diagnostico_r6_staging_e1p.md, 5.2); this test
confirms it on 3.1.973.

The route (``controllers/verification_ui.py:79-97``) reads the operation row on the request
cursor (``:24``, ``:41``), then ``_resolve_execute`` runs the plan on its own cursors (opening
13, ``models/safe_operation.py:972``): the claim commits the row (``:1296``) and the plan cursor
commits ``executed`` (``:1505``). Back on the request cursor, ``_consume_confirm_token``
(``:96`` → ``safe_operation.py:601-604``) updates the same row. Its UPDATE goes out in
``flush_env`` inside ``checked_call`` (``odoo/http.py:365``), with the snapshot taken at the
first query of the request (session check): PostgreSQL answers 40001.

``service.model.check`` retries it (``odoo/service/model.py:22-23``, ``:89-105``) after
``rollback`` and ``env.clear()`` (``odoo/http.py:345-347``): the whole controller runs again and
takes the idempotent branch (``safe_operation.py:837-857``).

The test plays the request with a real cursor P (``TransactionCase``: each ``registry.cursor()``
is a new connection, ``odoo/modules/registry.py:706``). P's Environment is created in the
thread's current set, like ``request.env``. Patch 38 (``seges_side_env``) is not involved: the
plan's cursors are new connections, there is no HTTP request on the stack, and P has nothing
pending when opening 13 runs (the consume comes after).

Side cursors (checks and cleanup) use plain SQL and no Environment. The test database is
disposable.

Two tests are skipped by the decision not to patch (13/11/2026);
``test_execute_retry_is_idempotent`` covers the success of the plan inside opening 13 of patch 38.
"""

import json
import secrets
import unittest

import psycopg2
from psycopg2 import errorcodes

import odoo
from odoo import SUPERUSER_ID, api
from odoo.sql_db import flush_env
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import get_db_name

from odoo.addons.pns_ai_mcp.tests._helpers import (
    AI_PLAN_GROUPS,
    SKIP_CONTACT_ORIGIN,
    grant_groups,
    revoke_groups,
)

PREFIX = 'seges-pns-v40-'
PRECONDITION = 'PRECONDITION (not the finding): '
KEYS = ('a', 'b', 'c')
# odoo/service/model.py:22-23
RETRY_CODES = (
    errorcodes.LOCK_NOT_AVAILABLE,
    errorcodes.SERIALIZATION_FAILURE,
    errorcodes.DEADLOCK_DETECTED,
)
MAX_TRIES = 5
CREATE_CONTEXT = dict(
    SKIP_CONTACT_ORIGIN,
    mail_create_nolog=True,
    mail_create_nosubscribe=True,
    tracking_disable=True,
)


def _registry():
    return odoo.registry(get_db_name())


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesVerifyExecute40001(TransactionCase):
    """PNS-26 annex: the request cursor of ``verification/execute`` after opening 13."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tag = PREFIX + secrets.token_hex(4)
        cls.rid = {}
        cls.vid = {}
        cls.granted = []
        try:
            cls._create_committed()
            cls._mint_tokens()
        except Exception:
            cls._remove_committed()
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            cls._remove_committed()
        finally:
            super().tearDownClass()

    @classmethod
    def _create_committed(cls):
        """One confirmed operation per test (each test leaves its own executed)."""
        with _registry().cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, dict(CREATE_CONTEXT))
            if any(env.all.towrite.values()) or any(env.all.tocompute.values()):
                raise AssertionError(
                    PRECONDITION + 'towrite or tocompute not empty before creating the data')
            admin = env.ref('base.user_admin')
            cls.admin_uid = admin.id
            cls.granted = grant_groups(admin, AI_PLAN_GROUPS)
            for key in KEYS:
                name = f'{cls.tag}-{key}'
                partner = env['res.partner'].create({'name': name})
                cls.rid['partner_' + key] = partner.id
                steps = [{
                    'op': 'write', 'model': 'res.partner', 'ids': [partner.id],
                    'values': {'comment': name},
                }]
                plan = ['write 1 res.partner']
                title = 'Seges PNS-26 annex ' + key
                op = env['ai.safe.operation'].create_verification(
                    operation_type='write',
                    model_name='res.partner',
                    records_count=1,
                    changes_info={'plan': plan, 'danger_level': 'low'},
                    user_id=admin.id,
                    tool_name='seges_pns_v40',
                    operation_data={
                        'plan_steps': steps, 'title': title,
                        'plan': plan, 'danger_level': 'low',
                    },
                )
                cls.rid['op_' + key] = op.id
                op.with_user(admin)._confirm_by_user()
                cls.vid[key] = op.verification_id
            env['base'].flush()
            cr.commit()  # pylint: disable=invalid-commit

    @classmethod
    def _mint_tokens(cls):
        """Card token, after the operations are committed (value discarded, never printed)."""
        with _registry().cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            for key in KEYS:
                env['ai.safe.operation'].browse(cls.rid['op_' + key])._mint_confirm_token()
            env['base'].flush()
            cr.commit()  # pylint: disable=invalid-commit
        cr = _registry().cursor()
        try:
            cr.execute(
                "SELECT COUNT(*) FROM ai_safe_operation WHERE id IN %s "
                "AND status = 'confirmed' AND COALESCE(confirm_token_hash, '') <> ''",
                (tuple(cls.rid['op_' + key] for key in KEYS),),
            )
            ready = cr.fetchone()[0]
        finally:
            cr.rollback()
            cr.close()
        if ready != len(KEYS):
            raise AssertionError(
                PRECONDITION + 'not every operation is confirmed with a card token hash')

    @classmethod
    def _remove_committed(cls):
        """Delete the committed rows (plain SQL), then give back the groups."""
        left = []
        ops = tuple(rid for k, rid in cls.rid.items() if k.startswith('op_'))
        partners = tuple(rid for k, rid in cls.rid.items() if k.startswith('partner_'))
        if ops or partners:
            cr = _registry().cursor()
            try:
                statements = []
                if ops:
                    statements += [
                        ('journal',
                         'DELETE FROM ai_change_journal WHERE safe_operation_id IN %s', (ops,)),
                    ]
                    statements += [
                        ('bus', 'DELETE FROM bus_bus WHERE message LIKE %s', ('%' + vid + '%',))
                        for vid in cls.vid.values() if vid
                    ]
                    statements += [
                        ('op', 'DELETE FROM ai_safe_operation WHERE id IN %s', (ops,)),
                    ]
                if partners:
                    statements += [
                        ('partner', 'DELETE FROM res_partner WHERE id IN %s', (partners,)),
                    ]
                for key, query, params in statements:
                    try:
                        with cr.savepoint():
                            cr.execute(query, params)
                    except psycopg2.Error:
                        left.append(key)
                cr.commit()  # pylint: disable=invalid-commit
            finally:
                cr.close()
            cls.rid = {}
            cls.vid = {}
        if cls.granted:
            # revoke_groups needs the ORM: its own cursor, after the SQL cleanup.
            with _registry().cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                revoke_groups(env.ref('base.user_admin'), cls.granted)
                cr.commit()  # pylint: disable=invalid-commit
            cls.granted = []
        if left:
            raise AssertionError('incomplete cleanup: ' + ', '.join(left))

    def setUp(self):
        super().setUp()
        self.cr_p = None
        self.addCleanup(self._close_p)
        self.env['base'].flush()
        self.bus_floor = self._side_scalar('SELECT COALESCE(MAX(id), 0) FROM bus_bus')

    # -- side cursors: plain SQL, no Environment --------------------------------

    def _side_scalar(self, query, params=None):
        cr = _registry().cursor()
        try:
            cr.execute(query, params)
            row = cr.fetchone()
            return row[0] if row else None
        finally:
            cr.rollback()
            cr.close()

    def _side_row_state(self, key):
        """Booleans and counts of the operation, its contact and its journal."""
        cr = _registry().cursor()
        try:
            cr.execute(
                'SELECT status, COALESCE(executed, false), confirm_token_hash IS NULL '
                'FROM ai_safe_operation WHERE id = %s',
                (self.rid['op_' + key],),
            )
            status, executed, hash_empty = cr.fetchone() or (None, False, False)
            cr.execute(
                'SELECT comment = %s FROM res_partner WHERE id = %s',
                (f'{self.tag}-{key}', self.rid['partner_' + key]),
            )
            row = cr.fetchone()
            applied = bool(row and row[0])
            cr.execute(
                'SELECT COUNT(*) FROM ai_change_journal WHERE safe_operation_id = %s',
                (self.rid['op_' + key],),
            )
            journal = cr.fetchone()[0]
            return {
                'status': status, 'executed': executed, 'hash_empty': hash_empty,
                'applied': applied, 'journal': journal,
            }
        finally:
            cr.rollback()
            cr.close()

    def _bus_notices(self, key, status=None, since_floor=True):
        """Count ``pns_safe_plan`` notices of the operation (decoded in Python, nothing printed).

        Odoo 14 only has ``bus.bus.sendone`` (odoo/addons/bus/models/bus.py:77), so the host
        notice takes the legacy branch (safe_operation.py:1777-1784): a JSON string inside JSON.
        """
        vid = self.vid[key]
        cr = _registry().cursor()
        try:
            cr.execute(
                'SELECT message FROM bus_bus WHERE id > %s AND message LIKE %s',
                (self.bus_floor if since_floor else 0, '%' + vid + '%'),
            )
            rows = cr.fetchall()
        finally:
            cr.rollback()
            cr.close()
        count = 0
        for (raw,) in rows:
            try:
                payload = json.loads(raw)
                if isinstance(payload, str):
                    payload = json.loads(payload)
            except ValueError:
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get('type') != 'pns_safe_plan' or payload.get('verification_id') != vid:
                continue
            if status is None or payload.get('status') == status:
                count += 1
        return count

    # -- cursor P: the request ---------------------------------------------------

    def _close_p(self):
        cr, self.cr_p = self.cr_p, None
        if cr is None:
            return
        try:
            cr.rollback()
        finally:
            cr.close()

    def _open_p(self):
        """Cursor P plays the HTTP request cursor (REPEATABLE READ, odoo/http.py:232).

        Its Environment is created in the thread's current set, the same one as ``self.env``,
        like ``request.env`` in a request.
        """
        self.cr_p = _registry().cursor()
        self.cr_p.execute('SHOW transaction_isolation')
        self.assertEqual(
            self.cr_p.fetchone()[0], 'repeatable read',
            PRECONDITION + 'cursor P is not REPEATABLE READ',
        )
        return api.Environment(self.cr_p, self.admin_uid, {})

    def _attempt(self, env_p, key, seen):
        """One run of ``verification_ui.execute`` (``:79-97``) plus ``checked_call``'s flush."""
        cr = env_p.cr
        cr.execute("SET LOCAL lock_timeout = '3s'")
        cr.execute("SET LOCAL statement_timeout = '15s'")
        # First query of the request transaction (session check, odoo/service/security.py:17).
        cr.execute('SELECT id FROM res_users WHERE id = %s', (self.admin_uid,))
        verification = env_p['ai.safe.operation'].sudo().search(
            [('verification_id', '=', self.vid[key])], limit=1,
        )  # :24
        seen['found'] = bool(verification) and verification.user_id.id == self.admin_uid  # :29
        if not seen['found']:
            return None
        seen['status'] = verification.status
        seen['hash'] = bool((verification.sudo().confirm_token_hash or '').strip())  # :41
        out = verification._resolve_execute(confirmed_uid=self.admin_uid)  # :94
        seen['out_status'] = (out or {}).get('status')
        if out.get('success') and out.get('status') == 'executed':  # :95
            verification._consume_confirm_token()  # :96
        flush_env(cr)  # odoo/http.py:365
        return out

    def _run_request(self, key, retry):
        """``checked_call`` (odoo/http.py:341-367) under ``check`` (odoo/service/model.py:89-105).

        No sleep between attempts. Returns the final result, the codes caught, what the first
        attempt saw and the row state right after the first attempt.
        """
        env_p = self._open_p()
        codes = []
        first_seen = {}
        after_first = None
        out = None
        attempt = 0
        while True:
            if attempt:
                # odoo/http.py:345-347. The rollback also clears the cache of the set shared
                # with self.env (Cursor.rollback -> clear_env); harmless: the test has nothing
                # pending (flush in setUp).
                self.cr_p.rollback()
                env_p.clear()
            seen = first_seen if not attempt else {}
            attempt += 1
            try:
                out = self._attempt(env_p, key, seen)
                failed = False
            except psycopg2.OperationalError as exc:
                if exc.pgcode not in RETRY_CODES:
                    raise
                codes.append(exc.pgcode)
                out = None
                failed = True
            if after_first is None:
                after_first = self._side_row_state(key)
            if not failed or not retry or len(codes) > MAX_TRIES:
                break
        if not failed:
            self.cr_p.commit()  # odoo/http.py:280  # pylint: disable=invalid-commit
        self._check_first_attempt(first_seen)
        return out, codes, after_first, failed

    def _check_first_attempt(self, seen):
        self.assertTrue(seen.get('found'), PRECONDITION + 'P does not see the operation as admin')
        self.assertEqual(
            seen.get('status'), 'confirmed',
            PRECONDITION + 'the operation was not confirmed when the request read it',
        )
        self.assertTrue(seen.get('hash'), PRECONDITION + 'the card token hash was empty at :41')
        self.assertEqual(
            seen.get('out_status'), 'executed',
            PRECONDITION + 'opening 13 did not execute the plan in the first attempt',
        )

    # -- tests -------------------------------------------------------------------

    @unittest.skip(
        'PNS-26 annex: no Seges patch (decision 13/11/2026). Fails on 3.1.973 by design; '
        'remove the skip if a patch is proposed.'
    )
    def test_execute_success_no_serialization_failure(self):
        """PNS-26 annex: consuming the token after opening 13 must not hit 40001.

        Correct behaviour: the first attempt flushes the consume without a serialization
        failure.
        """
        _out, codes, _after, _failed = self._run_request('a', retry=False)
        self.assertNotIn(
            errorcodes.SERIALIZATION_FAILURE, codes,
            "PNS-26 annex: verification/execute: the request cursor's UPDATE of the token hit a "
            'serialization failure after the plan cursor committed the same row (REPEATABLE '
            f"READ snapshot taken before the plan). Codes: {', '.join(codes)}",
        )

    def test_execute_retry_is_idempotent(self):
        """PNS-26 annex: with the retry of ``service.model.check`` the plan runs once.

        Covers the success of the plan inside opening 13.
        """
        out, codes, after_first, failed = self._run_request('b', retry=True)
        self.assertTrue(
            after_first['executed'] and after_first['applied'],
            PRECONDITION + 'the plan was not applied and committed by opening 13',
        )
        self.assertGreater(
            after_first['journal'], 0,
            PRECONDITION + 'the successful plan wrote no change journal row',
        )
        self.assertFalse(
            failed,
            f"PNS-26 annex: the request still failed after {len(codes) + 1} attempts "
            f"(codes: {', '.join(codes)})",
        )
        final = self._side_row_state('b')
        problems = []
        if (out or {}).get('status') != 'executed':
            problems.append('final response status is not executed')
        if codes and not (out or {}).get('idempotent'):
            problems.append('the retried response is not idempotent')
        if not (final['status'] == 'executed' and final['executed']):
            problems.append('the operation row is not executed')
        if not final['hash_empty']:
            problems.append('the card token hash was not consumed')
        if not final['applied']:
            problems.append('the plan change is not in the database')
        if final['journal'] != after_first['journal']:
            problems.append('the change journal changed after the first attempt (plan re-run)')
        self.assertFalse(
            problems,
            f"PNS-26 annex (retry): {'; '.join(problems)}; attempts: {len(codes) + 1}; "
            f"codes: {', '.join(codes) or '-'}",
        )

    @unittest.skip(
        'PNS-26 annex: no Seges patch (decision 13/11/2026). Fails on 3.1.973 by design; '
        'remove the skip if a patch is proposed.'
    )
    def test_execute_bus_notice_survives_retry(self):
        """PNS-26 annex: the ``executed`` host notice must reach ``bus_bus`` after the request."""
        self.assertGreater(
            self._bus_notices('c', since_floor=False), 0,
            PRECONDITION + 'create_verification left no pns_safe_plan notice in bus_bus',
        )
        out, codes, _after, failed = self._run_request('c', retry=True)
        self.assertTrue(
            not failed and (out or {}).get('status') == 'executed',
            PRECONDITION + 'the request did not end executed',
        )
        self.assertGreaterEqual(
            self._bus_notices('c', status='executed'), 1,
            'PNS-26 annex: the executed bus notice of the request was rolled back with the retry '
            'and '
            f"the idempotent branch does not send it again (attempts: {len(codes) + 1}; "
            f"codes: {', '.join(codes) or '-'})",
        )
