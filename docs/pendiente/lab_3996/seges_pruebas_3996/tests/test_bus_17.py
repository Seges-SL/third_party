# Copyright 2026 Seges
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
"""Bus notifications of the pns_ai modules on the Odoo 17 core (stage F1.3, case 20).

On Odoo 17, bus.bus._sendone (addons/bus/models/bus.py:111-125) queues the
row in cr.precommit and NOTIFY in cr.postcommit. The channel of a partner is
(db, 'res.partner', id) and the message is {"type": <type>, "payload": <dict>}.
Each test runs cr.precommit.run() (as addons/mail/tests/common.py:1254) and
reads the bus.bus rows created after a mark, filtered by channel and type.

- test_files_updated_to_session_owner (1): notify_files_updated sends one
  pns_chatboo_sync / message_received to the session owner's partner.
- test_skills_changed_to_current_user (2): _chatboo_notify_skills_changed as
  user U sends exactly one row, to U's partner.
- test_page_shared_to_new_reader_only (3): sharing a page with R sends one
  page_shared row to R and none to the owner; exact payload keys; relative url.
- test_async_error_to_job_owner (4): _notify('error') of a job sends one row
  to the job owner's partner with is_error true.
- test_safe_plan_to_owner_and_ai_admins (5): _notify_safe_plan_hosts sends
  pns_safe_plan to the plan owner and the AI Administrators, not to others.
- test_key_pin_changed_to_ai_admins (6): notify_changed sends
  pns_key_pin_changed to the AI Administrators (and the caller), not to others.

No network, no LLM. Only users, sessions, pages, jobs and plans created here.

Every failure message starts with a tag:
- [CHECK]: the behaviour this test documents did not hold;
- [SETUP]: a precondition failed; says nothing about the bus.
"""

import json
from datetime import timedelta

from odoo import fields
from odoo.addons.bus.models.bus import channel_with_db, json_dump
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

SYNC = "pns_chatboo_sync"
SAFE_PLAN = "pns_safe_plan"
PIN_CHANGED = "pns_key_pin_changed"


@tagged("post_install", "-at_install")
class TestBus17(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_u = new_test_user(
            cls.env, login="lab3996_bus_u", groups="base.group_user",
        )
        cls.user_r = new_test_user(
            cls.env, login="lab3996_bus_r", groups="base.group_user",
        )
        cls.user_t = new_test_user(
            cls.env, login="lab3996_bus_t", groups="base.group_user",
        )
        cls.user_a = new_test_user(
            cls.env, login="lab3996_bus_a",
            groups="base.group_user,pns_ai_mcp.group_ai_admin",
        )

    # ---------------------------------------------------------------- helpers
    def _mark(self):
        """Create the queued rows and return the last bus.bus id."""
        self.env.cr.precommit.run()
        last = self.env["bus.bus"].sudo().search([], order="id desc", limit=1)
        return last.id or 0

    def _rows(self, mark, ntype):
        """[(partner_id, message dict)] of type *ntype* created after *mark*."""
        self.env.cr.precommit.run()
        dbname = self.env.cr.dbname
        out = []
        for row in self.env["bus.bus"].sudo().search([("id", ">", mark)], order="id"):
            message = json.loads(row.message)
            if message.get("type") != ntype:
                continue
            channel = json.loads(row.channel)
            if len(channel) == 3 and channel[0] == dbname and channel[1] == "res.partner":
                out.append((channel[2], message))
            else:
                out.append((None, message))
        return out

    def _channel(self, partner):
        return json_dump(channel_with_db(self.env.cr.dbname, partner))

    def _session(self, user):
        try:
            return self.env["chatboo.session"].sudo().create({
                "name": "lab3996 bus session", "user_id": user.id,
            })
        except Exception as exc:  # noqa: BLE001
            self.fail(f"[SETUP] could not create a chatboo.session: {exc!r}")

    def _ai_admin_partners(self):
        group = self.env.ref("pns_ai_mcp.group_ai_admin", raise_if_not_found=False)
        self.assertTrue(group, "[SETUP] pns_ai_mcp.group_ai_admin not found")
        self.assertIn(self.user_a, group.users, "[SETUP] user A is not an AI Administrator")
        self.assertNotIn(self.user_t, group.users, "[SETUP] user T is an AI Administrator")
        return set(group.users.mapped("partner_id").ids)

    # ------------------------------------------------------------------ tests
    def test_files_updated_to_session_owner(self):
        session = self._session(self.user_u)
        mark = self._mark()
        session.notify_files_updated()
        rows = self._rows(mark, SYNC)
        expected = {
            "type": SYNC,
            "payload": {"type": SYNC, "action": "message_received", "session_id": session.id},
        }
        self.assertEqual(
            rows, [(self.user_u.partner_id.id, expected)],
            f"[CHECK] expected one {SYNC} row to the owner's partner; got {rows!r}",
        )
        raw = self.env["bus.bus"].sudo().search([("id", ">", mark)])
        self.assertIn(
            self._channel(self.user_u.partner_id), raw.mapped("channel"),
            "[CHECK] the stored channel is not json_dump((db, 'res.partner', id))",
        )

    def test_skills_changed_to_current_user(self):
        session = self._session(self.user_u)
        mark = self._mark()
        self.env["ai.skill"].with_user(self.user_u)._chatboo_notify_skills_changed(
            confirm=True, session_id=session.id,
        )
        rows = self._rows(mark, SYNC)
        expected = {
            "type": SYNC,
            "payload": {
                "type": SYNC, "action": "skills_changed",
                "confirm": True, "session_id": session.id,
            },
        }
        self.assertEqual(
            rows, [(self.user_u.partner_id.id, expected)],
            f"[CHECK] expected exactly one {SYNC} row, to U's partner; got {rows!r}",
        )

    def test_page_shared_to_new_reader_only(self):
        mark = self._mark()
        try:
            page = self.env["chatboo.canvas.page"].sudo().create({
                "name": "lab3996 page",
                "design": "<p>lab3996</p>",
                "owner_id": self.user_u.id,
                "user_ids": [(6, 0, [self.user_r.id])],
            })
        except Exception as exc:  # noqa: BLE001
            self.fail(f"[SETUP] could not create a chatboo.canvas.page: {exc!r}")
        rows = self._rows(mark, SYNC)
        partners = [pid for pid, _msg in rows]
        self.assertEqual(
            partners, [self.user_r.partner_id.id],
            f"[CHECK] expected one {SYNC} row, to the new reader only; got partners {partners!r}",
        )
        payload = rows[0][1]["payload"]
        self.assertEqual(
            set(payload), {"type", "action", "page_id", "title", "owner", "url"},
            f"[CHECK] unexpected payload keys {sorted(payload)!r}",
        )
        self.assertEqual(
            (payload["action"], payload["page_id"], payload["title"], payload["owner"]),
            ("page_shared", page.id, "lab3996 page", self.user_u.name),
            f"[CHECK] unexpected page_shared payload {payload!r}",
        )
        self.assertTrue(
            payload["url"].startswith("/chatboo/page/"),
            f"[CHECK] the url does not start with /chatboo/page/: {payload['url']!r}",
        )

    def test_async_error_to_job_owner(self):
        session = self._session(self.user_u)
        try:
            job = self.env["chatboo.async.request"].sudo().create({
                "session_id": session.id,
                "user_id": self.user_u.id,
                "prompt": "lab3996",
            })
        except Exception as exc:  # noqa: BLE001
            self.fail(f"[SETUP] could not create a chatboo.async.request: {exc!r}")
        mark = self._mark()
        job._notify("error")
        rows = self._rows(mark, SYNC)
        expected = {
            "type": SYNC,
            "payload": {
                "type": SYNC, "action": "error", "session_id": session.id,
                "request_id": job.id, "is_error": True,
            },
        }
        self.assertEqual(
            rows, [(self.user_u.partner_id.id, expected)],
            f"[CHECK] expected one {SYNC} error row to the job owner; got {rows!r}",
        )

    def test_safe_plan_to_owner_and_ai_admins(self):
        admins = self._ai_admin_partners()
        try:
            plan = self.env["ai.safe.operation"].sudo().create({
                "operation_type": "write",
                "model_name": "res.partner",
                "records_count": 1,
                "user_id": self.user_u.id,
                # Required in the table; the module always passes it
                # (pns_ai_mcp/models/safe_operation.py:520-535).
                "expires_at": fields.Datetime.now() + timedelta(minutes=10),
            })
        except Exception as exc:  # noqa: BLE001
            self.fail(f"[SETUP] could not create an ai.safe.operation: {exc!r}")
        mark = self._mark()
        plan._notify_safe_plan_hosts()
        rows = self._rows(mark, SAFE_PLAN)
        got = {pid for pid, _msg in rows}
        expected = admins | {self.user_u.partner_id.id}
        self.assertEqual(
            got, expected,
            f"[CHECK] {SAFE_PLAN} recipients {sorted(got)!r}, expected owner + AI admins {sorted(expected)!r}",
        )
        self.assertNotIn(
            self.user_t.partner_id.id, got,
            f"[CHECK] {SAFE_PLAN} reached a user who is neither the owner nor an AI admin",
        )
        self.assertEqual(len(rows), len(got), f"[CHECK] duplicate {SAFE_PLAN} rows: {rows!r}")
        for _pid, msg in rows:
            self.assertEqual(
                msg["payload"],
                {
                    "type": SAFE_PLAN, "verification_id": plan.verification_id,
                    "status": "pending", "executed": False,
                },
                f"[CHECK] unexpected {SAFE_PLAN} payload {msg['payload']!r}",
            )

    def test_key_pin_changed_to_ai_admins(self):
        admins = self._ai_admin_partners()
        Desk = self.env["ai.key.pin.desk"]
        live = set(Desk.sudo()._live().mapped("user_id.partner_id").ids)
        mark = self._mark()
        Desk.with_user(self.user_a).notify_changed()
        rows = self._rows(mark, PIN_CHANGED)
        got = {pid for pid, _msg in rows}
        expected = admins | live | {self.user_a.partner_id.id}
        self.assertEqual(
            got, expected,
            f"[CHECK] {PIN_CHANGED} recipients {sorted(got)!r}, expected {sorted(expected)!r}",
        )
        self.assertNotIn(
            self.user_t.partner_id.id, got,
            f"[CHECK] {PIN_CHANGED} reached a user who is not an AI admin",
        )
        for _pid, msg in rows:
            self.assertEqual(
                msg["payload"], {"type": PIN_CHANGED},
                f"[CHECK] unexpected {PIN_CHANGED} payload {msg['payload']!r}",
            )
