# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: test de confirmación del anexo de PNS-26, sin parche. Ver docs/pendiente/propuesta_fase3_3973.md
# Seges: adaptado a la 17 (fase 2, T0): cr.flush() y env.reset() como service.model.retrying, flush_all(),
# cache.get_dirty_fields(), bus {"type", "payload"}, comment Html (subcadena), mute_logger('odoo.sql_db') en el
# primer intento, aserción del 40001 en test_execute_retry_is_idempotent, citas de R17 y texto de los skip;
# los documentos que citan las líneas anteriores están en 14.0. Ver docs/pendiente/parches_pns_ai.md
"""PNS-26 annex: ``/pns_ai_mcp/verification/execute`` and the request's REPEATABLE READ snapshot.

Already recorded on 3.1.879 (docs/pendiente/diagnostico_r6_staging_e1p.md, 5.2) and confirmed on 3.1.973; both
documents are in 14.0. Ported to 17.0.3.1.996 (phase 2, T0) without a patch. Lines below: R17 and the Odoo 17
core of the lab container (17.0-20260908).

The route (``controllers/verification_ui.py:79-97``) reads the operation row on the request
cursor (``:24``, ``:41``), then ``_resolve_execute`` (``models/safe_operation.py:802``) runs the plan on its own
cursors (opening 13, ``:966``): the claim commits the row (``:1290``) and the plan cursor commits ``executed``
(``:1499``). Back on the request cursor, ``_consume_confirm_token`` (``:96`` → ``safe_operation.py:594-600``)
updates the same row. Its UPDATE goes out in ``env.cr.flush()`` inside ``service.model.retrying``
(``odoo/service/model.py:155``, called from ``odoo/http.py:1985``), with the snapshot taken at the first query of
the request (session check): PostgreSQL answers 40001.

``retrying`` retries it (``odoo/service/model.py:23-24``, ``:137-187``) after ``rollback`` and ``env.reset()``
(``:160-161``): the whole controller runs again and takes the idempotent branch (``safe_operation.py:832-852``).

The test plays the request with a real cursor P: ``TransactionCase`` does not put the registry in test mode
(only ``HttpCase`` does, ``odoo/tests/common.py:1934``), so each ``registry.cursor()`` is a new connection
(``odoo/modules/registry.py:931``). In 17 each cursor has its own ``Transaction`` (``odoo/api.py:518-520``): P
shares no cache with ``self.env``. Patch 38 (``seges_side_env``) is not ported (it does not apply to 17): the
plan's cursors are new connections, there is no HTTP request on the stack, and P has nothing pending when
opening 13 runs (the consume comes after).

Side cursors (checks and cleanup) use plain SQL and no Environment. The test database is
disposable.

Two tests are skipped by the decision not to patch (13/11/2026);
``test_execute_retry_is_idempotent`` covers the success of the plan inside opening 13.
"""

import contextlib
import json
import secrets
import unittest

import psycopg2
from psycopg2 import errorcodes

import odoo
from odoo import SUPERUSER_ID, api
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import get_db_name
from odoo.tools import mute_logger

from odoo.addons.pns_ai_mcp.tests._helpers import (
    AI_PLAN_GROUPS,
    SKIP_CONTACT_ORIGIN,
    grant_groups,
    revoke_groups,
)

PREFIX = 'seges-pns-v40-'
PRECONDITION = 'PRECONDITION (not the finding): '
KEYS = ('a', 'b', 'c')
# odoo/service/model.py:23-24 (PG_CONCURRENCY_ERRORS_TO_RETRY, MAX_TRIES_ON_CONCURRENCY_FAILURE)
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
            # 17: no towrite; pending writes are the cache's dirty fields (odoo/api.py:1260).
            if any(env.cache.get_dirty_fields()) or any(env.all.tocompute.values()):
                raise AssertionError(
                    PRECONDITION + 'dirty fields or tocompute not empty before creating the data')
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
            env.flush_all()  # odoo/api.py:735
            cr.commit()  # pylint: disable=invalid-commit

    @classmethod
    def _mint_tokens(cls):
        """Card token, after the operations are committed (value discarded, never printed)."""
        with _registry().cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            for key in KEYS:
                env['ai.safe.operation'].browse(cls.rid['op_' + key])._mint_confirm_token()
            env.flush_all()  # odoo/api.py:735
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
        self.env.flush_all()  # odoo/api.py:735
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
            # 17: comment is fields.Html (odoo/addons/base/models/res_partner.py:239; Text in 14), stored with
            # markup: compare by substring with the run-unique value the plan writes (tag + key).
            cr.execute(
                'SELECT COALESCE(position(%s in comment) > 0, false) FROM res_partner WHERE id = %s',
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

        In 17 the host notice goes through ``bus.bus._sendone`` (safe_operation.py:1753, :1768-1769), which
        stores ``{"type": ..., "payload": ...}`` (odoo/addons/bus/models/bus.py:111-120). The legacy branch of
        Odoo 14 (a JSON string inside JSON, ``sendone``) is still decoded.
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
            if payload.get('type') == 'pns_safe_plan' and isinstance(payload.get('payload'), dict):
                payload = dict(payload['payload'], type='pns_safe_plan')  # 17: {"type", "payload"}
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
        """Cursor P plays the HTTP request cursor (REPEATABLE READ, odoo/sql_db.py:275; opened in
        odoo/http.py:1981).

        In 17 its Environment gets the cursor's own ``Transaction`` (odoo/api.py:518-520), like
        ``request.env`` in a request.
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
        # First query of the request transaction (session check, odoo/service/security.py:15).
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
        cr.flush()  # odoo/service/model.py:155 (retrying), odoo/sql_db.py:134
        return out

    def _run_request(self, key, retry):
        """``service.model.retrying`` (odoo/service/model.py:137-187), as ``_serve_db`` calls it (odoo/http.py:1985).

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
                # odoo/service/model.py:160-161. In 17 the rollback and the reset only touch
                # P's own Transaction (odoo/api.py:501, :886), not self.env's.
                self.cr_p.rollback()
                env_p.reset()
            seen = first_seen if not attempt else {}
            attempt += 1
            # Seges: the first attempt hits the 40001 on purpose and odoo.sql_db logs its 'bad query' as
            # ERROR; only that attempt is muted (decision 136).
            quiet = mute_logger('odoo.sql_db') if attempt == 1 else contextlib.nullcontext()
            try:
                with quiet:
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
            self.cr_p.commit()  # odoo/service/model.py:192  # pylint: disable=invalid-commit
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
        'PNS-26 annex: no Seges patch (decision 13/11/2026). Failed on 3.1.973 by design; '
        'not measured on 17.0.3.1.996. Remove the skip if a patch is proposed.'
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
        # Seges: the race is the premise, not the finding; the test checks it itself because the
        # mute_logger of the first attempt hides the 'bad query' from the log (decisions 136 and 138).
        self.assertEqual(
            codes, [errorcodes.SERIALIZATION_FAILURE],
            PRECONDITION + 'the first attempt did not hit 40001: the race did not happen',
        )
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
        'PNS-26 annex: no Seges patch (decision 13/11/2026). Failed on 3.1.973 by design; '
        'not measured on 17.0.3.1.996. Remove the skip if a patch is proposed.'
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
