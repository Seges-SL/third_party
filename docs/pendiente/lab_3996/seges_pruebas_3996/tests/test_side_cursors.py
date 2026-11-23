# Copyright 2026 Seges
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
"""Do side cursors touch the caller's pending work in Odoo 17? (patches 37 and 38)

Odoo 14 kept the ORM cache, the pending writes and the pending computations per
thread, shared by every environment of the thread, so committing or rolling
back any cursor with an Environment flushed or cleared the caller's work:

- patch 37 (PNS-104): closing box A (open_readonly_env, a READ ONLY cursor that
  tool_relaxaicode rolls back) dropped the caller's pending writes and
  computations, and a box A read of a column with a pending caller write tried
  to flush it on the READ ONLY cursor;
- patch 38 (PNS-105): a side cursor that commits (ai.log, the API result
  cache...) committed the caller's pending writes outside the caller's
  transaction, lost them on records the caller had created, waited for rows
  the caller held, and cleared the caller's cache.

Odoo 17 keeps them per cursor: Environment.__new__ reuses cr.transaction or
creates a new Transaction (odoo/api.py:518-520), and Cursor.commit and
Cursor.rollback only flush or clear their own (odoo/sql_db.py:481, :492).
These tests expect both patches to be unnecessary: they pass on the unpatched
code.

TransactionCase on purpose: outside test mode registry.cursor() returns a real
Cursor on its own connection (odoo/modules/registry.py:931-938), as in
production. It does not see the test's uncommitted rows and its commits are
real, so side cursors here only commit new tagged rows, deleted afterwards on a
separate cursor. Checks from outside the test transaction use plain SQL on a
separate cursor, with no Environment.

Every failure message starts with a tag:
- [HYPOTHESIS]: the check this test exists for failed;
- [SETUP]: a precondition failed; says nothing about the hypothesis;
- [GUARD]: a check that must hold with and without the patch failed.
Unexpected exceptions show up as errors, not as failures.
"""

import contextlib
import json
import re
import secrets

import psycopg2
from psycopg2 import errorcodes

from odoo.tests import TransactionCase, tagged

from odoo.addons.pns_ai_mcp.controllers.controller_helpers import get_readonly_env
from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import tool_relaxaicode
from odoo.addons.pns_ai_mcp.models import ai_log as ai_log_module

TAG = "seges-3996-p3738-"
PROBE_ENDPOINT = "seges_3996_side_probe"
RUN_OK = "result = {'data': [{'v': sum([1, 2, 3])}]}\n"
SAW_PENDING = "seges3996-saw-pending"
SAW_DB = "seges3996-saw-db"
_PARTNER_SQL = {
    "ref": "SELECT ref FROM res_partner WHERE id = %s",
    "complete_name": "SELECT complete_name FROM res_partner WHERE id = %s",
}
_LOG_ROW = "SELECT 1 FROM ai_log WHERE id = %s AND endpoint = %s"
_CACHE_ROW = "SELECT 1 FROM ai_api_result_cache WHERE server_code = %s"
_WRITE_TABLE = re.compile(
    r'^\s*(?:UPDATE\s+(?:ONLY\s+)?|INSERT\s+INTO\s+|DELETE\s+FROM\s+)"?(\w+)"?',
    re.IGNORECASE,
)


def _table_of(query):
    """Table a query writes (never its parameters), or '?'."""
    text = query if isinstance(query, str) else getattr(query, "code", "")
    found = _WRITE_TABLE.match(text or "")
    return found.group(1) if found else "?"


class _CursorSpy:
    """Watch the cursors that registry.cursor() opens while ``watching()`` is on.

    For each one: its class, its commits and rollbacks, the lock timeouts it hit
    and, right before every commit or rollback, the value of ``probe`` (a check
    of the caller's state). With ``lock_timeout``, each watched cursor first runs
    SET LOCAL lock_timeout, so waiting for a row the test holds becomes an error
    instead of a hang.
    """

    def __init__(self, test, lock_timeout=False):
        self.on = False
        self.probe = None
        self.cursors = []
        self.lock_timeout = lock_timeout
        registry_cls = type(test.registry)
        real_cursor = registry_cls.cursor
        spy = self

        def cursor(registry):
            cr = real_cursor(registry)
            if spy.on:
                spy._watch(cr)
            return cr

        test.patch(registry_cls, "cursor", cursor)

    def _watch(self, cr):
        info = {
            "kind": type(cr).__name__,
            "commits": 0,
            "rollbacks": 0,
            "probes": [],
            "lock_waits": [],
        }
        self.cursors.append(info)
        real_commit, real_rollback, real_execute = cr.commit, cr.rollback, cr.execute
        spy = self

        def commit():
            info["commits"] += 1
            if spy.probe:
                info["probes"].append(("commit", spy.probe()))
            return real_commit()

        def rollback():
            info["rollbacks"] += 1
            if spy.probe:
                info["probes"].append(("rollback", spy.probe()))
            return real_rollback()

        def execute(query, params=None, log_exceptions=True):
            try:
                return real_execute(query, params, log_exceptions)
            except psycopg2.Error as exc:
                if exc.pgcode == errorcodes.LOCK_NOT_AVAILABLE:
                    info["lock_waits"].append(_table_of(query))
                raise

        cr.commit, cr.rollback, cr.execute = commit, rollback, execute
        if self.lock_timeout:
            real_execute("SET LOCAL lock_timeout = '3s'")

    @contextlib.contextmanager
    def watching(self, probe=None):
        self.on, self.probe = True, probe
        try:
            yield self
        finally:
            self.on, self.probe = False, None


class _StubController:
    """What tool_relaxaicode asks of its controller.

    Same as the vendor's e2e test (pns_ai_mcp/tests/test_relaxaicode_sandbox_escapes_e2e.py),
    except the locale, which is constant so the tool reads nothing more on the
    caller's environment.
    """

    def __init__(self, env):
        self.env = env

    def _get_env_for_operation(self, operation_type="read"):
        return self.env

    def _get_readonly_env(self):
        return get_readonly_env(self)

    def _check_mcp_permissions(self, operation_type):
        return True, ""

    def _cancel_pending_verifications_for_user(self, user_id, reason=""):
        return 0

    def _get_user_locale(self):
        return "en_US"

    def _get_company_lang(self):
        return False

    def _log_mcp_operation(self, *args, **kwargs):
        return None


class _SideCursorCase(TransactionCase):
    """Shared helpers and checks; no tests of its own."""

    def setUp(self):
        super().setUp()
        self.assertFalse(
            self.registry.in_test_mode(),
            "[SETUP] expected the registry outside test mode (real side cursors); "
            "found it in test mode (registry.cursor() would return a TestCursor)",
        )
        self.admin = self.env.ref("base.user_admin")
        self.marker = TAG + secrets.token_hex(4)

    # -- outside the test transaction: plain SQL, no Environment -----------

    def _outside_one(self, query, params):
        cr = self.registry.cursor()
        try:
            cr.execute(query, params)
            return cr.fetchone()
        finally:
            cr.rollback()
            cr.close()

    def _outside_write(self, query, params):
        cr = self.registry.cursor()
        try:
            cr.execute("SET LOCAL lock_timeout = '3s'")
            cr.execute(query, params)
            cr.commit()  # pylint: disable=invalid-commit
        finally:
            cr.close()

    # -- the caller's state --------------------------------------------------

    def _pending(self, record, fname):
        return self.env.cache.has_dirty_fields(record, [record._fields[fname]])

    def _caller_value(self, record, column):
        """Flush the caller, then read ``column`` in the caller's transaction."""
        self.env.flush_all()
        self.env.cr.execute(_PARTNER_SQL[column], [record.id])
        row = self.env.cr.fetchone()
        return row[0] if row else None

    def _cached(self, *pairs):
        return all(self.env.cache.contains(rec, rec._fields[f]) for rec, f in pairs)

    def _assert_watched(self, spy, what, event, require_probe=True):
        """[SETUP]: real cursors that did ``event``.

        With ``require_probe``, the caller's state must also be in place at the
        first ``event`` (the scenario really happened).
        """
        self.assertTrue(spy.cursors, f"[SETUP] expected {what} to open a cursor; found none")
        kinds = sorted({c["kind"] for c in spy.cursors})
        self.assertEqual(
            kinds, ["Cursor"],
            f"[SETUP] expected only real Cursor objects from {what}; found {kinds}",
        )
        counter = "commits" if event == "commit" else "rollbacks"
        self.assertTrue(
            any(c[counter] for c in spy.cursors),
            f"[SETUP] expected a {event} of {what}'s cursor; found none",
        )
        if not require_probe:
            return
        probes = [value for c in spy.cursors for name, value in c["probes"] if name == event]
        self.assertTrue(probes, f"[SETUP] expected a {event} of {what}'s cursor; found none")
        self.assertTrue(
            probes[0],
            f"[SETUP] expected the caller's pending state in place at the first {event} "
            f"of {what}; found it already gone (the scenario did not happen)",
        )


@tagged("post_install", "-at_install")
class TestBoxACallerPending(_SideCursorCase):
    """Patch 37 (PNS-104): closing box A keeps the caller's pending work.

    Box A is opened and closed by the real tool: cursor at
    controller_helpers.py:189, rollback and close at tools_relaxaicode.py:273-279.
    """

    def setUp(self):
        super().setUp()
        self.spy = _CursorSpy(self)

    def _new_partner(self):
        partner = self.env["res.partner"].create({"name": "Seges 3996 p37 probe"})
        partner.flush_recordset()
        return partner

    def _run_box_a(self, code, probe, error_tag="[SETUP]"):
        with self.spy.watching(probe):
            resp = tool_relaxaicode(_StubController(self.env(user=self.admin)), {"code": code})
        try:
            text = resp["content"][0]["text"]
        except (KeyError, IndexError, TypeError):
            text = json.dumps(resp, default=str)
        failed = (isinstance(resp, dict) and resp.get("isError")) or "ERROR (" in text
        self.assertFalse(
            failed, f"{error_tag} expected box A to run the code; found an error: {text[:300]}"
        )
        self._assert_watched(self.spy, "box A", "rollback")
        return text

    def test_pending_write_survives_box_a_close(self):
        """A pending write of the caller is still there after box A's rollback."""
        partner = self._new_partner()
        partner.write({"ref": self.marker})
        self.assertTrue(
            self._pending(partner, "ref"),
            "[SETUP] expected ref pending in the caller before box A; found it not pending",
        )
        self._run_box_a(RUN_OK, lambda: self._pending(partner, "ref"))
        self.assertTrue(
            self._pending(partner, "ref"),
            "[HYPOTHESIS] expected ref still pending in the caller after box A's rollback; "
            "found it dropped",
        )
        found = self._caller_value(partner, "ref")
        self.assertEqual(
            found, self.marker,
            f"[HYPOTHESIS] expected the caller's flush to write {self.marker!r}; found {found!r}",
        )

    def test_pending_compute_survives_box_a_close(self):
        """A pending stored computation of the caller survives box A's rollback.

        Only the computation is pending: name changes with plain SQL and
        complete_name is marked by hand (env.add_to_compute).
        """
        partner = self._new_partner()
        field = partner._fields["complete_name"]
        new_name = "Seges 3996 p37 " + secrets.token_hex(4)
        self.env.cr.execute(
            "UPDATE res_partner SET name = %s WHERE id = %s", [new_name, partner.id]
        )
        partner.invalidate_recordset(["name"])
        self.env.add_to_compute(field, partner)

        def to_compute():
            return partner in self.env.records_to_compute(field)

        self.assertTrue(
            to_compute(),
            "[SETUP] expected complete_name pending to compute before box A; found it not pending",
        )
        self._run_box_a(RUN_OK, to_compute)
        self.assertTrue(
            to_compute(),
            "[HYPOTHESIS] expected complete_name still pending to compute after box A's "
            "rollback; found it dropped",
        )
        stored = self._caller_value(partner, "complete_name") or ""
        self.assertIn(
            new_name, stored,
            f"[HYPOTHESIS] expected the caller's flush to store a complete_name with "
            f"{new_name!r}; found {stored!r}",
        )

    def test_box_a_reads_column_pending_in_caller(self):
        """Condition a: box A reads a column the caller has a pending write on."""
        partner = self.env.ref("base.main_partner")
        partner.write({"ref": self.marker})
        self.assertTrue(
            self._pending(partner, "ref"),
            "[SETUP] expected ref pending in the caller before box A; found it not pending",
        )
        code = (
            f"v = env['res.partner'].browse({partner.id}).ref\n"
            f"result = {{'data': [{{'v': '{SAW_PENDING}' if v == '{self.marker}' "
            f"else '{SAW_DB}'}}]}}\n"
        )
        text = self._run_box_a(
            code, lambda: self._pending(partner, "ref"), error_tag="[HYPOTHESIS]"
        )
        self.assertIn(
            SAW_DB, text,
            f"[GUARD] expected box A to read the committed value on its own cursor; "
            f"found: {text[:300]}",
        )
        self.assertTrue(
            self._pending(partner, "ref"),
            "[HYPOTHESIS] expected ref still pending in the caller after box A read it; "
            "found it dropped or flushed",
        )
        found = self._caller_value(partner, "ref")
        self.assertEqual(
            found, self.marker,
            f"[HYPOTHESIS] expected the caller's flush to write {self.marker!r}; found {found!r}",
        )

    def test_box_a_close_keeps_caller_cache_and_new(self):
        """Box A's rollback keeps the caller's cache and its new() records."""
        partner = self.env.ref("base.main_partner")
        self.assertTrue(partner.name, "[SETUP] expected base.main_partner to have a name")
        new_partner = self.env["res.partner"].new({"name": self.marker})
        pairs = ((partner, "name"), (new_partner, "name"))
        self.assertTrue(
            self._cached(*pairs),
            "[SETUP] expected both names in the caller's cache before box A; found them missing",
        )
        self._run_box_a(RUN_OK, lambda: self._cached(*pairs))
        self.assertTrue(
            self._cached((partner, "name")),
            "[HYPOTHESIS] expected the caller's cached name of base.main_partner after box A's "
            "rollback; found it cleared",
        )
        self.assertTrue(
            self._cached((new_partner, "name")) and new_partner.name == self.marker,
            f"[HYPOTHESIS] expected the caller's new() record to keep {self.marker!r}; "
            f"found {new_partner.name!r}",
        )


@tagged("post_install", "-at_install")
class TestSideCursorCommit(_SideCursorCase):
    """Patch 38 (PNS-105): a side cursor's commit leaves the caller's pending work alone.

    Two real openings: ai.log (ai_log.py:731-858) and the API result cache
    (api_result_cache.py:132).
    """

    def setUp(self):
        super().setUp()
        self.spy = _CursorSpy(self, lock_timeout=True)
        self.server = TAG + secrets.token_hex(4)
        self.addCleanup(
            self._outside_write,
            "DELETE FROM ai_api_result_cache WHERE server_code = %s", [self.server],
        )
        self.addCleanup(
            self._outside_write, "DELETE FROM ai_log WHERE endpoint = %s", [PROBE_ENDPOINT]
        )

    def _create_log(self, probe):
        with self.spy.watching(probe):
            return self.env["ai.log"].sudo()._create_log_entry(
                user_id=self.admin.id, operation_type="read", tool_name=PROBE_ENDPOINT,
            )

    def _call_log(self, probe):
        """ai.log on its own cursor, with the vendor's caller flush skipped.

        ai_log.py:721-730 flushes the caller before opening the cursor (a fix
        for Odoo 14). Skipping it only during the call lets the side commit meet
        the caller's pending work, as in 3.1.973.
        """
        self.patch(ai_log_module, "test_is_running", lambda *args, **kwargs: False)
        env_cls = type(self.env)
        real_flush_all = env_cls.flush_all
        caller_cr = self.env.cr
        skip = {"on": True, "skipped": 0}

        def flush_all(env):
            if skip["on"] and env.cr is caller_cr:
                skip["skipped"] += 1
                return None
            return real_flush_all(env)

        self.patch(env_cls, "flush_all", flush_all)
        try:
            log = self._create_log(probe)
        finally:
            skip["on"] = False
        self.assertTrue(
            skip["skipped"],
            "[SETUP] expected the vendor's caller flush (ai_log.py:721-730) to be called and "
            "skipped; found it not called",
        )
        self.assertTrue(log, "[SETUP] expected _create_log_entry to return the log; found None")
        self._assert_watched(self.spy, "ai.log", "commit")
        return log

    def _store(self, probe):
        with self.spy.watching(probe):
            self.env["ai.api.result.cache"]._store(
                self.server, "seges_probe", {}, '{"ok": true}', ttl_seconds=600
            )

    def _restore_ref_if_committed(self, partner_id, original):
        row = self._outside_one(_PARTNER_SQL["ref"], [partner_id])
        if row and row[0] == self.marker:
            self._outside_write(
                "UPDATE res_partner SET ref = %s WHERE id = %s", [original, partner_id]
            )

    def test_log_does_not_commit_caller_pending_write(self):
        """E1: ai.log's commit does not commit the caller's pending write."""
        partner = self.env.ref("base.main_partner")
        original = self._outside_one(_PARTNER_SQL["ref"], [partner.id])[0]
        self.addCleanup(self._restore_ref_if_committed, partner.id, original)
        partner.write({"ref": self.marker})
        self.assertTrue(
            self._pending(partner, "ref"),
            "[SETUP] expected ref pending in the caller before the log; found it not pending",
        )
        log = self._call_log(lambda: self._pending(partner, "ref"))
        outside = self._outside_one(_PARTNER_SQL["ref"], [partner.id])[0]
        self.assertNotEqual(
            outside, self.marker,
            "[HYPOTHESIS] expected the caller's pending write not committed by ai.log's "
            "cursor; found it visible from a separate cursor",
        )
        self.assertTrue(
            self._pending(partner, "ref"),
            "[HYPOTHESIS] expected ref still pending in the caller after ai.log's commit; "
            "found it flushed or dropped",
        )
        self.assertTrue(
            self._outside_one(_LOG_ROW, [log.id, PROBE_ENDPOINT]),
            "[SETUP] expected the log row committed (visible from a separate cursor); "
            "found it missing",
        )
        found = self._caller_value(partner, "ref")
        self.assertEqual(
            found, self.marker,
            f"[HYPOTHESIS] expected the caller's flush to write {self.marker!r}; found {found!r}",
        )

    def test_log_keeps_pending_write_on_new_record(self):
        """E2: a pending write on a record the caller created is not lost."""
        partner = self.env["res.partner"].create({"name": "Seges 3996 p38 probe"})
        partner.flush_recordset()
        partner.write({"ref": self.marker})
        self.assertTrue(
            self._pending(partner, "ref"),
            "[SETUP] expected ref pending in the caller before the log; found it not pending",
        )
        log = self._call_log(lambda: self._pending(partner, "ref"))
        self.assertTrue(
            self._pending(partner, "ref"),
            "[HYPOTHESIS] expected ref still pending in the caller after ai.log's commit; "
            "found it flushed or dropped",
        )
        self.assertTrue(
            self._outside_one(_LOG_ROW, [log.id, PROBE_ENDPOINT]),
            "[SETUP] expected the log row committed (visible from a separate cursor); "
            "found it missing",
        )
        found = self._caller_value(partner, "ref")
        self.assertEqual(
            found, self.marker,
            f"[HYPOTHESIS] expected the caller's flush to write {self.marker!r} on its own "
            f"record; found {found!r}",
        )

    def test_log_as_shipped_keeps_caller_write(self):
        """ai.log as shipped (with its caller flush): the caller's write stays its own.

        The vendor's flush (ai_log.py:721-730) moves the pending write into the
        caller's transaction before the side cursor opens, so nothing is required
        to be pending at the side commit.
        """
        self.patch(ai_log_module, "test_is_running", lambda *args, **kwargs: False)
        partner = self.env.ref("base.main_partner")
        original = self._outside_one(_PARTNER_SQL["ref"], [partner.id])[0]
        self.addCleanup(self._restore_ref_if_committed, partner.id, original)
        partner.write({"ref": self.marker})
        self.assertTrue(
            self._pending(partner, "ref"),
            "[SETUP] expected ref pending in the caller before the log; found it not pending",
        )
        log = self._create_log(None)
        self.assertTrue(log, "[SETUP] expected _create_log_entry to return the log; found None")
        self._assert_watched(self.spy, "ai.log", "commit", require_probe=False)
        outside = self._outside_one(_PARTNER_SQL["ref"], [partner.id])[0]
        self.assertNotEqual(
            outside, self.marker,
            "[HYPOTHESIS] expected the caller's write not committed by ai.log's cursor; "
            "found it visible from a separate cursor",
        )
        self.assertTrue(
            self._outside_one(_LOG_ROW, [log.id, PROBE_ENDPOINT]),
            "[SETUP] expected the log row committed (visible from a separate cursor); "
            "found it missing",
        )
        found = self._caller_value(partner, "ref")
        self.assertEqual(
            found, self.marker,
            f"[HYPOTHESIS] expected the caller to keep {self.marker!r}; found {found!r}",
        )

    def test_store_does_not_wait_for_caller_locked_row(self):
        """E3: the side commit does not compute the caller's pending field on a locked row."""
        partner = self.env.ref("base.main_partner")
        field = partner._fields["complete_name"]
        self.env.cr.execute(
            "SELECT id FROM res_partner WHERE id = %s FOR UPDATE", [partner.id]
        )
        self.env.add_to_compute(field, partner)

        def to_compute():
            return partner in self.env.records_to_compute(field)

        self.assertTrue(
            to_compute(),
            "[SETUP] expected complete_name pending to compute in the caller; found it not pending",
        )
        self._store(to_compute)
        waits = [table for c in self.spy.cursors for table in c["lock_waits"]]
        self.assertFalse(
            waits,
            f"[HYPOTHESIS] expected the side cursor not to wait for rows the caller holds; "
            f"found lock timeouts on {waits}",
        )
        self._assert_watched(self.spy, "the API result cache", "commit")
        self.assertTrue(
            to_compute(),
            "[HYPOTHESIS] expected complete_name still pending in the caller after the side "
            "commit; found it computed elsewhere or dropped",
        )
        self.assertTrue(
            self._outside_one(_CACHE_ROW, [self.server]),
            "[SETUP] expected the cache row committed (visible from a separate cursor); "
            "found it missing",
        )

    def test_store_keeps_caller_cache_and_new(self):
        """E4: the side commit keeps the caller's cache and its new() records."""
        partner = self.env.ref("base.main_partner")
        self.assertTrue(partner.name, "[SETUP] expected base.main_partner to have a name")
        new_partner = self.env["res.partner"].new({"name": self.marker})
        pairs = ((partner, "name"), (new_partner, "name"))
        self.assertTrue(
            self._cached(*pairs),
            "[SETUP] expected both names in the caller's cache before the side cursor; "
            "found them missing",
        )
        self._store(lambda: self._cached(*pairs))
        self._assert_watched(self.spy, "the API result cache", "commit")
        self.assertTrue(
            self._cached((partner, "name")),
            "[HYPOTHESIS] expected the caller's cached name of base.main_partner after the side "
            "commit; found it cleared",
        )
        self.assertTrue(
            self._cached((new_partner, "name")) and new_partner.name == self.marker,
            f"[HYPOTHESIS] expected the caller's new() record to keep {self.marker!r}; "
            f"found {new_partner.name!r}",
        )
        self.assertTrue(
            self._outside_one(_CACHE_ROW, [self.server]),
            "[SETUP] expected the cache row committed (visible from a separate cursor); "
            "found it missing",
        )
