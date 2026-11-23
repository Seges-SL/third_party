# Copyright 2026 Seges
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
"""Can box A read a secret it finds in its cache in Odoo 17? (patch 18, PNS-19)

Box A (open_readonly_env, pns_ai_mcp/controllers/controller_helpers.py:179) runs
the sandbox as the asking user on its own READ ONLY cursor, marked with
SANDBOX_CURSOR_FLAG. The vendor's guard (models/sandbox_secret_read.py) refuses a
secret column when Odoo fetches it from the database: check_field_access_rights,
called by _fetch_field (odoo/models.py:3809). A value already in the cache is
returned without any check (odoo/fields.py:1152-1154), and a non-stored computed
field is computed without one (odoo/fields.py:1209-1231).

(a) Patch 18 part B emptied the secret columns of the cache when box A opened.
    Odoo 14 shared that cache in the thread; in Odoo 17 a new cursor gets a new
    Transaction (odoo/api.py:518-520), so box A should open without secrets or
    caller values in its cache, and invalidating it should never touch the
    caller's pending writes (odoo/api.py:1300-1302). Expected green.
(b) Vendor code the sandbox calls reads a secret with sudo() on box A's cursor
    (auth_call_preview, user_has_mcp_api_key): the value stays in box A's cache
    and the sandbox code then reads it. Expected red.
(c) In Odoo 17 core, res.users.totp_secret and res.partner.signup_token are
    non-stored fields computed by SQL: reading them computes them, with no check
    and no cache involved. Expected red.

TransactionCase on purpose, as test_side_cursors.py: registry.cursor() returns
real cursors. Each test commits new tagged rows on a side cursor, plays the
caller (a request) on another real cursor opened after that commit, and deletes
the rows on a third cursor before its assertions. Creating the API server also
commits its detection row (ai.context, ondelete cascade); with no url it adds no
URL whitelist entry. The tool itself commits nothing outside box A with this stub
(_log_mcp_operation does nothing); the cursor spy checks it. Secrets are random
and never printed: the sandbox returns a SHA-256 fingerprint (16 hex) and the
tests compare fingerprints.

Every failure message starts with a tag:
- [HYPOTHESIS]: the check this test exists for failed;
- [SETUP]: a precondition failed; says nothing about the hypothesis;
- [GUARD]: a check that must hold with and without the patch failed.
Unexpected exceptions show up as errors, not as failures.
"""

import contextlib
import hashlib
import json
import logging
import secrets

from odoo import SUPERUSER_ID, api
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger

from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import tool_relaxaicode
from odoo.addons.pns_ai_mcp.utils.sandbox_secrets import (
    SECRET_DENIED_PREFIX,
    sandbox_cursor,
    secret_column,
)

from .test_side_cursors import _CursorSpy, _StubController

_logger = logging.getLogger(__name__)

TAG = "seges_3996_p18_"
PROBE_TEXT = "seges3996-probe"
FP_CODE = "hashlib.sha256(str({}).encode()).hexdigest()[:16]"
QUIET = {
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_create_nosubscribe": True,
    "mail_notrack": True,
    "no_reset_password": True,
}


def _fp(value):
    """The fingerprint FP_CODE computes in the sandbox: 16 hex of SHA-256."""
    return hashlib.sha256(str(value).encode()).hexdigest()[:16]


def _code(*lines, read=None, flag=None):
    """Sandbox code: ``lines``, then a result with the probe, fp(``read``) and ``flag``.

    The probe fingerprint proves the code ran to its end. It is computed at run
    time, so it never appears in the code or in an error that quotes the code.
    """
    body = list(lines)
    data = ["'probe': " + FP_CODE.format(repr(PROBE_TEXT))]
    if read:
        body.append(f"v = {read}")
        data.append("'fp': " + FP_CODE.format("v"))
    if flag:
        data.append(f"'flag': {flag}")
    body.append("result = {'data': [{" + ", ".join(data) + "}]}")
    return "\n".join(body) + "\n"


def _cache_ids(cache):
    """{field: ids} held by an ORM Cache.

    Cache._data is private; it is read here only to report what a cache holds.
    Context-dependent fields keep one dict per context key.
    """
    found = {}
    for field, field_cache in cache._data.items():
        if not field_cache:
            continue
        if isinstance(next(iter(field_cache)), tuple):
            ids = set()
            for sub in field_cache.values():
                ids.update(sub)
        else:
            ids = set(field_cache)
        if ids:
            found[field] = ids
    return found


class _Run:
    """One call of the real tool: its text, whether it failed, the cursors it opened."""

    def __init__(self, resp, cursors, stub_errors):
        try:
            self.text = resp["content"][0]["text"]
        except (KeyError, IndexError, TypeError):
            self.text = json.dumps(resp, default=str)
        self.is_error = bool(
            (isinstance(resp, dict) and resp.get("isError")) or "ERROR (" in self.text
        )
        self.cursors = cursors
        self.stub_errors = stub_errors

    def outcome(self, fingerprint, model, fname):
        """'read' (the value came out), 'refused' or 'other'.

        'refused' only with the field guard's own text
        (pns_ai_mcp/models/sandbox_secret_read.py:39-45, raised at :75-76). The
        model gate (validators_base.py:407-413) shares SECRET_DENIED_PREFIX and
        the parameter guard (sandbox_secret_read.py:46-51) too: both are 'other'.
        """
        if not self.is_error and fingerprint in self.text:
            return "read"
        denial = f"{SECRET_DENIED_PREFIX}{model}.{fname}: it holds a credential"
        if self.is_error and fingerprint not in self.text and denial in self.text:
            return "refused"
        return "other"


class _OpenProbeStub(_StubController):
    """_StubController that calls ``on_open(ro_env)`` as soon as box A is open.

    Errors of ``on_open`` are kept, not raised: tool_relaxaicode would lose the
    cursor it has not received yet (tools_relaxaicode.py:178 and :271-281).
    """

    def __init__(self, env, on_open=None):
        super().__init__(env)
        self.on_open = on_open
        self.errors = []

    def _get_readonly_env(self):
        ro_env, ro_cr = super()._get_readonly_env()
        if self.on_open:
            try:
                self.on_open(ro_env)
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                self.errors.append(type(exc).__name__)
        return ro_env, ro_cr


class _BoxASecretCase(TransactionCase):
    """Committed tagged rows, the caller on its own cursor and the real tool. No tests."""

    def setUp(self):
        super().setUp()
        self.assertFalse(
            self.registry.in_test_mode(),
            "[SETUP] expected the registry outside test mode (real cursors); "
            "found it in test mode (registry.cursor() would return a TestCursor)",
        )
        self.tag = TAG + secrets.token_hex(4)
        self.secret = {
            key: f"{self.tag}_{key}_{secrets.token_hex(16)}"
            for key in ("auth", "hash", "totp", "signup")
        }
        self.row = {}
        self.user_ids = []
        self.partner_ids = []
        self.spy = _CursorSpy(self)
        self.addCleanup(self._remove_committed)
        self._create_committed()
        self.rec = dict(self.row)

    # -- committed rows ------------------------------------------------------

    def _create_committed(self):
        cr = self.registry.cursor()
        try:
            env = api.Environment(cr, SUPERUSER_ID, {})
            for key in ("asker", "target"):
                user = new_test_user(
                    env, login=f"{self.tag}_{key}", name=f"{self.tag} {key}",
                    groups="base.group_user", context=QUIET,
                )
                self.row[key] = user.id
                self.row[key + "_partner"] = user.partner_id.id
                self.user_ids.append(user.id)
                self.partner_ids.append(user.partner_id.id)
            contact = env["res.partner"].with_context(**QUIET).create(
                {"name": f"{self.tag} contact"}
            )
            self.row["contact"] = contact.id
            self.partner_ids.append(contact.id)
            # No url: an MCP/SSE server adds a URL whitelist entry only for its url
            # (external_server.py:932-950); its detection row is an ai.context.
            server = env["ai.api.server"].create({
                "name": f"{self.tag} server", "code": self.tag, "auth_type": "bearer",
            })
            self.row["server"] = server.id
            mcp = env["ai.mcp.user"].with_context(mcp_skip_ensure_all_users=True).search(
                [("user_id", "=", self.row["target"])], limit=1,
            ) or env["ai.mcp.user"].create({"user_id": self.row["target"]})
            self.row["mcp"] = mcp.id
            # The secrets, without the SQL log: a bad query would print them.
            with mute_logger("odoo.sql_db"):
                server.write({"auth_token": self.secret["auth"]})
                mcp.write({"mcp_api_key_hash": self.secret["hash"]})
                target = env["res.users"].with_context(**QUIET).browse(self.row["target"])
                if "totp_secret" in target._fields:
                    target.write({"totp_secret": self.secret["totp"]})
                if "signup_token" in contact._fields:
                    contact.write({
                        "signup_token": self.secret["signup"],
                        "signup_type": False,
                        "signup_expiration": False,
                    })
                env.flush_all()
            cr.commit()  # pylint: disable=invalid-commit
        finally:
            cr.close()

    def _remove_committed(self):
        """Delete the tagged rows on a cursor of their own and commit. Idempotent."""
        if not self.row:
            return
        row, self.row = self.row, {}
        cr = self.registry.cursor()
        try:
            cr.execute("SET LOCAL lock_timeout = '3s'")
            env = api.Environment(cr, SUPERUSER_ID, {})
            steps = []
            if row.get("server"):
                steps.append(env["ai.context"].with_context(active_test=False).search(
                    [("api_server_id", "=", row["server"])]
                ))
            for model, key in (
                ("ai.mcp.user", "mcp"), ("ai.api.server", "server"),
                ("res.users", "asker"), ("res.users", "target"),
                ("res.partner", "contact"), ("res.partner", "asker_partner"),
                ("res.partner", "target_partner"),
            ):
                if row.get(key):
                    steps.append(env[model].with_context(active_test=False).browse(row[key]))
            for recs in steps:
                recs = recs.exists()
                if not recs:
                    continue
                try:
                    with cr.savepoint(), mute_logger("odoo.sql_db"):
                        recs.unlink()
                except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                    # Kept by a foreign key: no secret and archived; the [GUARD] reports it.
                    try:
                        with cr.savepoint(), mute_logger("odoo.sql_db"):
                            self._scrub(recs)
                    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                        _logger.warning("seges 3996 p18: could not scrub %s", recs._name)
            # Mail rows of the deleted users and partners, if any were made.
            refs = [("res.users", self.user_ids), ("res.partner", self.partner_ids)]
            for model, ids in refs:
                if ids:
                    cr.execute(
                        "DELETE FROM mail_followers WHERE res_model = %s AND res_id = ANY(%s)",
                        [model, ids],
                    )
                    cr.execute(
                        "DELETE FROM mail_message WHERE model = %s AND res_id = ANY(%s)",
                        [model, ids],
                    )
            cr.commit()  # pylint: disable=invalid-commit
        finally:
            cr.close()

    @staticmethod
    def _scrub(recs):
        vals = {
            name: False
            for name in ("auth_token", "mcp_api_key_hash", "totp_secret", "signup_token")
            if name in recs._fields
        }
        if "active" in recs._fields:
            vals["active"] = False
        if vals:
            recs.write(vals)

    def _tagged_rows(self):
        """{table: count} of the rows the test left behind (plain SQL, own cursor)."""
        users = self.user_ids or [0]
        partners = self.partner_ids or [0]
        checks = (
            ("res_users", "SELECT count(*) FROM res_users WHERE left(login, %s) = %s",
             [len(self.tag), self.tag]),
            ("res_partner", "SELECT count(*) FROM res_partner WHERE left(name, %s) = %s",
             [len(self.tag), self.tag]),
            ("ai_api_server", "SELECT count(*) FROM ai_api_server WHERE code = %s",
             [self.tag]),
            ("ai_mcp_user", "SELECT count(*) FROM ai_mcp_user WHERE user_id = ANY(%s)",
             [users]),
            ("ai_context", "SELECT count(*) FROM ai_context WHERE discovery_target = %s",
             [self.tag]),
            ("ai_url_whitelist",
             "SELECT count(*) FROM ai_url_whitelist WHERE position(%s in coalesce(notes, '')) > 0",
             [self.tag]),
            ("mail_message",
             ("SELECT count(*) FROM mail_message WHERE (model = 'res.users' AND res_id = ANY(%s))"
              " OR (model = 'res.partner' AND res_id = ANY(%s))"),
             [users, partners]),
            ("mail_followers",
             ("SELECT count(*) FROM mail_followers WHERE (res_model = 'res.users'"
              " AND res_id = ANY(%s)) OR (res_model = 'res.partner' AND res_id = ANY(%s))"
              " OR partner_id = ANY(%s)"),
             [users, partners, partners]),
        )
        cr = self.registry.cursor()
        try:
            found = {}
            for table, query, params in checks:
                cr.execute(query, params)
                count = cr.fetchone()[0]
                if count:
                    found[table] = count
            return found
        finally:
            cr.rollback()
            cr.close()

    def _release(self):
        """Delete the rows now and check it; call it before the assertions."""
        self._remove_committed()
        left = self._tagged_rows()
        self.assertFalse(
            left, f"[GUARD] expected no rows of the test after the cleanup ({self.tag!r}); "
            f"found {left}",
        )

    # -- the caller and the tool ---------------------------------------------

    @contextlib.contextmanager
    def _caller(self):
        """The caller (a request) on a real cursor opened after the commit; rolled back."""
        cr = self.registry.cursor()
        try:
            yield api.Environment(cr, SUPERUSER_ID, {})
        finally:
            cr.rollback()
            cr.close()

    def _run(self, caller, code, on_open=None):
        """The real tool, as the asker, on the caller's cursor."""
        stub = _OpenProbeStub(caller(user=self.rec["asker"]), on_open=on_open)
        self.spy.cursors = []
        with self.spy.watching():
            resp = tool_relaxaicode(stub, {"code": code})
        return _Run(resp, list(self.spy.cursors), list(stub.errors))

    def _server_ref(self):
        return (
            "s = env['mail.template.preview'].new("
            f"{{'resource_ref': 'ai.api.server,{self.rec['server']}'}}).resource_ref"
        )

    def _mcp_ref(self):
        return (
            "m = env['mail.template.preview'].new("
            f"{{'resource_ref': 'ai.mcp.user,{self.rec['mcp']}'}}).resource_ref"
        )

    def _show(self, run):
        """At most 300 characters of a run's text; never a text that holds a secret."""
        if any(value in run.text for value in self.secret.values()):
            return "<hidden: the text holds a secret>"
        return run.text[:300]

    # -- shared checks -------------------------------------------------------

    def _assert_box_a(self, run, what):
        kinds = sorted({c["kind"] for c in run.cursors})
        self.assertEqual(
            kinds, ["Cursor"],
            f"[SETUP] expected {what} to open box A on real Cursor objects only; found {kinds}",
        )
        self.assertTrue(
            any(c["rollbacks"] for c in run.cursors),
            f"[SETUP] expected box A of {what} rolled back; found no rollback",
        )
        self.assertFalse(
            any(c["commits"] for c in run.cursors),
            f"[SETUP] expected no commit on the cursors {what} opened; found one",
        )
        self.assertFalse(
            run.stub_errors,
            f"[SETUP] expected the opening probe of {what} to run; found {run.stub_errors}",
        )

    def _assert_ran(self, run, what, flag=None):
        self._assert_box_a(run, what)
        self.assertFalse(run.is_error, f"[SETUP] expected {what} to run; found: {self._show(run)}")
        self.assertTrue(
            _fp(PROBE_TEXT) in run.text,
            f"[SETUP] expected the probe fingerprint from {what}; found none",
        )
        if flag:
            self.assertTrue(
                flag in run.text, f"[SETUP] expected {flag!r} from {what}; found: {self._show(run)}",
            )

    def _assert_refused(self, run, fingerprint, model, fname, what):
        self._assert_box_a(run, what)
        self.assertEqual(
            run.outcome(fingerprint, model, fname), "refused",
            f"[SETUP] expected {what} refused by the field guard on {model}.{fname}; "
            f"found: {self._show(run)}",
        )

    def _assert_hypothesis_refused(self, run, fingerprint, model, fname, what):
        self._assert_box_a(run, what)
        outcome = run.outcome(fingerprint, model, fname)
        self.assertNotEqual(
            outcome, "other",
            f"[SETUP] expected {what} to end refused by the field guard or with the value; "
            f"found: {self._show(run)}",
        )
        self.assertEqual(
            outcome, "refused",
            f"[HYPOTHESIS] expected {what} refused by the field guard; found the secret's "
            "fingerprint in the result (read with no check)",
        )


@tagged("post_install", "-at_install")
class TestBoxACacheAtOpening(_BoxASecretCase):
    """(a) Patch 18 part B: box A's cache when it opens, and the caller's pending writes."""

    def _server(self, caller):
        server = caller["ai.api.server"].browse(self.rec["server"])
        return server, server._fields["auth_token"]

    @staticmethod
    def _dirty(cache, record, field):
        return bool(
            cache.has_dirty_fields(record, [field])
            and record.id in cache.get_dirty_records(record, field)._ids
        )

    def _pending_state(self, caller, server, field, pending):
        """'pending', 'changed', 'flushed' or 'lost' for the caller's new token."""
        if self._dirty(caller.cache, server, field):
            if caller.cache.get(server, field, None) == pending:
                return "pending"
            return "changed"
        caller.cr.execute("SELECT auth_token FROM ai_api_server WHERE id = %s", [server.id])
        row = caller.cr.fetchone()
        return "flushed" if row and row[0] == pending else "lost"

    def _assert_pending(self, state, when):
        self.assertNotEqual(
            state, "flushed",
            f"[SETUP] expected the caller's new token still pending {when}; "
            "found the tool flushed the caller: written, not lost",
        )
        self.assertEqual(
            state, "pending",
            f"[HYPOTHESIS] expected the caller's new token still pending {when}; "
            f"found it {state}",
        )

    def _pending_secret_write(self, caller):
        """The caller reads the token with sudo (now cached) and leaves a new one pending."""
        server, field = self._server(caller)
        self.assertTrue(
            server.auth_token == self.secret["auth"],
            "[SETUP] expected the caller to read the committed token with sudo; "
            "found another value",
        )
        pending = f"{self.tag}_pending_{secrets.token_hex(16)}"
        server.write({"auth_token": pending})
        self.assertEqual(
            self._pending_state(caller, server, field, pending), "pending",
            "[SETUP] expected the new token pending in the caller (get_dirty_*) before box A",
        )
        return server, field, pending

    def test_box_a_opens_without_secret_or_caller_values_in_cache(self):
        """Box A opens with no secret column and no caller value in its cache.

        Anything else found there is logged (model.field and count), not failed.
        The caller keeps its pending write through box A.
        """
        seen = {}
        with self._caller() as caller:
            server, field, pending = self._pending_secret_write(caller)

            def on_open(ro_env):
                held = _cache_ids(ro_env.cache)
                callers = _cache_ids(caller.cache)
                secret = sorted(
                    f"{f.model_name}.{f.name}" for f in held
                    if ro_env[f.model_name]._pns_hidden_column(f.name)
                )
                shared = sorted(
                    f"{f.model_name}.{f.name}" for f, ids in held.items()
                    if ids & callers.get(f, set())
                )
                other = {
                    f"{f.model_name}.{f.name}": len(ids) for f, ids in held.items()
                    if f"{f.model_name}.{f.name}" not in secret + shared
                }
                seen.update(
                    marked=sandbox_cursor(ro_env.cr), su=ro_env.su, uid=ro_env.uid,
                    secret=secret, shared=shared,
                    at_open=self._pending_state(caller, server, field, pending),
                )
                _logger.info(
                    "seges 3996 p18: box A cache at opening: own transaction=%s, own cache=%s, "
                    "dirty fields=%s, to compute=%s, secret=%s, from the caller=%s, other=%s",
                    ro_env.transaction is not caller.transaction,
                    ro_env.cache is not caller.cache,
                    len(ro_env.cache.get_dirty_fields()), len(ro_env.transaction.tocompute),
                    secret, shared, other or "nothing",
                )

            run = self._run(caller, _code("x = sum([1, 2, 3])"), on_open=on_open)
            after = self._pending_state(caller, server, field, pending)
        self._release()
        self._assert_ran(run, "the run")
        self.assertTrue(seen, "[SETUP] expected the opening probe to run; found it not called")
        self.assertTrue(
            seen["marked"] and not seen["su"] and seen["uid"] == self.rec["asker"],
            f"[SETUP] expected box A marked, without su, as the asker; found marked="
            f"{seen['marked']}, su={seen['su']}, asker={seen['uid'] == self.rec['asker']}",
        )
        self.assertFalse(
            seen["secret"],
            f"[HYPOTHESIS] expected no secret column in box A's cache at opening; "
            f"found {seen['secret']}",
        )
        self.assertFalse(
            seen["shared"],
            f"[HYPOTHESIS] expected no caller value in box A's cache at opening; "
            f"found {seen['shared']}",
        )
        self._assert_pending(seen["at_open"], "when box A opens")
        self._assert_pending(after, "after box A closes")

    def test_caller_cached_token_not_readable_in_box_a(self):
        """NUEVO-1 in Odoo 17: a token the caller read with sudo does not reach box A."""
        with self._caller() as caller:
            server, field = self._server(caller)
            self.assertTrue(
                server.auth_token == self.secret["auth"],
                "[SETUP] expected the caller to read the committed token with sudo; "
                "found another value",
            )
            self.assertTrue(
                caller.cache.contains(server, field),
                "[SETUP] expected the token in the caller's cache; found it missing",
            )
            run = self._run(caller, _code(self._server_ref(), read="s['auth_token']"))
        self._release()
        self._assert_hypothesis_refused(
            run, _fp(self.secret["auth"]), "ai.api.server", "auth_token",
            "s['auth_token'] with the token in the caller's cache",
        )

    def test_simulated_b_keeps_caller_pending_secret_write(self):
        """Part B as in Odoo 14, on opening: it only touches box A's own cache."""
        seen = {}
        with self._caller() as caller:
            server, field, pending = self._pending_secret_write(caller)

            def part_b(ro_env):
                secret_fields = [
                    model_field
                    for name in ro_env.registry
                    for fname, model_field in ro_env[name]._fields.items()
                    if ro_env[name]._pns_hidden_column(fname)
                ]
                ro_env.cache.invalidate([(f, None) for f in secret_fields])
                seen.update(
                    count=len(secret_fields), token=field in secret_fields,
                    at_open=self._pending_state(caller, server, field, pending),
                )

            run = self._run(caller, _code("x = sum([1, 2, 3])"), on_open=part_b)
            after = self._pending_state(caller, server, field, pending)
            caller.flush_all()
            caller.cr.execute("SELECT auth_token FROM ai_api_server WHERE id = %s", [server.id])
            written = caller.cr.fetchone()[0] == pending
        self._release()
        self._assert_ran(run, "the run")
        self.assertTrue(
            seen and seen["count"] and seen["token"],
            "[SETUP] expected the simulated part B over the secret columns, "
            f"ai.api.server.auth_token among them; found {seen.get('count')} columns, "
            f"token={seen.get('token')}",
        )
        self._assert_pending(seen["at_open"], "right after part B")
        self._assert_pending(after, "after box A closes")
        self.assertTrue(
            written,
            "[HYPOTHESIS] expected the caller's flush to write its pending token; "
            "found another value",
        )

    def test_invalidating_the_callers_cache_drops_its_pending_value(self):
        """Why part B must never reach the caller (odoo/api.py:1300-1302)."""
        with self._caller() as caller:
            server, field, _pending = self._pending_secret_write(caller)
            caller.cache.invalidate([(field, None)])
            dropped = not caller.cache.contains(server, field)
            still_dirty = self._dirty(caller.cache, server, field)
            caller.transaction.clear()  # nothing may be flushed now; the cursor rolls back
        self._release()
        self.assertTrue(
            dropped and still_dirty,
            "[GUARD] expected Cache.invalidate to drop the caller's pending value and keep "
            f"its dirty flag; found dropped={dropped}, dirty={still_dirty}",
        )


@tagged("post_install", "-at_install")
class TestBoxASecretReadInside(_BoxASecretCase):
    """(b) A secret read with sudo() on box A's cursor, then by the sandbox code."""

    def test_v1_auth_call_preview_then_token(self):
        """Real path: auth_call_preview reads auth_token with sudo() (external_server.py:393)."""
        head = self._server_ref()
        with self._caller() as caller:
            control = self._run(caller, _code(head, read="s['auth_token']"))
            reach = self._run(caller, _code(
                head, "pv = s.auth_call_preview",
                flag="'seges3996-' + ('token-set' if 'token set' in str(pv) else 'no-token')",
            ))
            via = self._run(caller, _code(head, "pv = s.auth_call_preview", read="s['auth_token']"))
        self._release()
        fingerprint = _fp(self.secret["auth"])
        self._assert_refused(
            control, fingerprint, "ai.api.server", "auth_token", "s['auth_token'] alone",
        )
        self._assert_ran(reach, "auth_call_preview alone", flag="seges3996-token-set")
        self._assert_hypothesis_refused(
            via, fingerprint, "ai.api.server", "auth_token",
            "s['auth_token'] after auth_call_preview",
        )

    def test_v2_user_has_mcp_api_key_then_hash(self):
        """Real path: user_has_mcp_api_key reads the hash with sudo() (mcp_user.py:318-319)."""
        head = self._mcp_ref()
        has_key = f"k = m.user_has_mcp_api_key(env['res.users'].browse({self.rec['target']}))"
        with self._caller() as caller:
            control = self._run(caller, _code(head, read="m['mcp_api_key_hash']"))
            reach = self._run(caller, _code(
                head, has_key, flag="'seges3996-' + ('has-key' if k else 'no-key')",
            ))
            via = self._run(caller, _code(head, has_key, read="m['mcp_api_key_hash']"))
        self._release()
        fingerprint = _fp(self.secret["hash"])
        self._assert_refused(
            control, fingerprint, "ai.mcp.user", "mcp_api_key_hash",
            "m['mcp_api_key_hash'] alone",
        )
        self._assert_ran(reach, "user_has_mcp_api_key alone", flag="seges3996-has-key")
        self._assert_hypothesis_refused(
            via, fingerprint, "ai.mcp.user", "mcp_api_key_hash",
            "m['mcp_api_key_hash'] after user_has_mcp_api_key",
        )

    def test_synthetic_engine_sudo_read_before_code(self):
        """SYNTHETIC: no engine code reads a secret with sudo() on box A today.

        Stands for patch 18 part B2's case: the engine (a sandbox helper) reads the
        token with sudo() on box A's environment before the sandbox code runs.
        """
        seen = {}

        def warm(ro_env):
            server = ro_env["ai.api.server"].sudo().browse(self.rec["server"])
            seen["warm"] = bool(server.auth_token) and ro_env.cache.contains(
                server, server._fields["auth_token"]
            )

        code = _code(self._server_ref(), read="s['auth_token']")
        with self._caller() as caller:
            control = self._run(caller, code)
            warmed = self._run(caller, code, on_open=warm)
        self._release()
        fingerprint = _fp(self.secret["auth"])
        self._assert_refused(
            control, fingerprint, "ai.api.server", "auth_token", "s['auth_token'] alone",
        )
        self.assertTrue(
            seen.get("warm"),
            "[SETUP] expected the synthetic engine read to leave the token in box A's cache; "
            "found it missing",
        )
        self._assert_hypothesis_refused(
            warmed, fingerprint, "ai.api.server", "auth_token",
            "SYNTHETIC: s['auth_token'] after an engine read with sudo()",
        )


@tagged("post_install", "-at_install")
class TestBoxAComputedSecret(_BoxASecretCase):
    """(c) Odoo 17 core secrets computed by SQL: read with no check and no cache."""

    def _assert_computed_secret(self, model_name, fname):
        model = self.env[model_name]
        self.assertTrue(
            fname in model._fields, f"[SETUP] expected {model_name}.{fname}; found no such field",
        )
        field = model._fields[fname]
        self.assertTrue(
            field.compute and not field.store,
            f"[SETUP] expected {model_name}.{fname} computed and not stored; "
            f"found compute={bool(field.compute)}, store={field.store}",
        )
        self.assertTrue(
            secret_column(model, fname),
            f"[SETUP] expected the vendor's criterion to call {model_name}.{fname} secret; "
            "found it not secret",
        )

    def _computed(self, model_name, rec_key, var, plain, plain_value, fname, secret_key):
        """Same record, same path: a plain field must come out, then the computed secret."""
        self._assert_computed_secret(model_name, fname)
        head = f"{var} = env['{model_name}'].browse({self.rec[rec_key]})"
        with self._caller() as caller:
            control = self._run(caller, _code(head, read=f"{var}['{plain}']"))
            run = self._run(caller, _code(head, read=f"{var}['{fname}']"))
        self._release()
        self._assert_ran(control, f"{var}['{plain}'] on the same record")
        self.assertTrue(
            _fp(plain_value) in control.text,
            f"[SETUP] expected the control to return the fingerprint of {model_name}.{plain}; "
            f"found: {self._show(control)}",
        )
        self._assert_hypothesis_refused(
            run, _fp(self.secret[secret_key]), model_name, fname,
            f"{var}['{fname}'] with nothing cached",
        )

    def test_core_totp_secret_without_cache(self):
        self._computed(
            "res.users", "target", "u", "login", f"{self.tag}_target", "totp_secret", "totp",
        )

    def test_core_signup_token_without_cache(self):
        self._computed(
            "res.partner", "contact", "p", "name", f"{self.tag} contact", "signup_token", "signup",
        )
