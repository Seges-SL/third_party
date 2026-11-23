# Copyright 2026 Seges
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
"""Does "Review" leave the import written? (patch 21, PNS-20)

action_preview (pns_base/models/operation_report_wizard.py) runs the import
between a raw SAVEPOINT and ROLLBACK TO SAVEPOINT, and then calls
env.invalidate_all(), which flushes the ORM's pending writes before
invalidating. Whatever the import left pending is written after the rollback,
outside the savepoint, and is committed with the request.

The end of the Review request is simulated with env.flush_all() (cr.commit()
flushes first). Rows are then read with plain SQL, so the test sees what would
be committed, not the ORM cache. write_date cannot tell (now() is constant in
the test transaction); ctid can: it changes on every UPDATE and comes back
after ROLLBACK TO SAVEPOINT.

Every failure message starts with a tag:
- [HYPOTHESIS]: the check this test exists for failed;
- [SETUP]: a precondition failed; says nothing about the hypothesis;
- [GUARD]: a check that must hold with and without the patch failed.
Unexpected exceptions show up as errors, not as failures.
"""

import base64
import json
from unittest import mock

from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

LABEL = "seges-3996-p21"
WRITER = "pns_ai_mcp.group_ai_writer"
_ROW_QUERIES = {
    "ai_mcp_user": (
        "SELECT ctid::text, last_mcp_client_label FROM ai_mcp_user WHERE id = %s"
    ),
    "ai_provider": "SELECT ctid::text, temperature FROM ai_provider WHERE id = %s",
}


@tagged("post_install", "-at_install")
class TestImportReview(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(
            cls.env, login="seges_3996_p21", groups="base.group_user"
        )
        McpUser = cls.env["ai.mcp.user"]
        cls.mcp_user = McpUser.search(
            [("user_id", "=", cls.user.id)], limit=1
        ) or McpUser.create({"user_id": cls.user.id})
        cls.provider = cls.env["ai.provider"].create(
            {
                "name": "Seges 3996 p21",
                "temperature": 0.7,
                "endpoint": "https://seges.invalid/v1/chat/completions",
            }
        )
        cls.provider.model_id = cls.env["ai.provider.model"].create(
            {"name": "seges-3996-p21-model", "provider_id": cls.provider.id}
        )

    def _row(self, table, rec_id):
        """(ctid, value) as stored in the database, after flushing the ORM."""
        self.env.flush_all()
        self.env.cr.execute(_ROW_QUERIES[table], (rec_id,))
        return self.env.cr.fetchone()

    def _in_group_db(self, group):
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT 1 FROM res_groups_users_rel WHERE uid = %s AND gid = %s",
            (self.user.id, group.id),
        )
        return bool(self.env.cr.fetchone())

    def _wizard(self, model, rows):
        data = base64.b64encode(json.dumps(rows).encode())
        return self.env[model].create(
            {"json_file": data, "filename": "seges_3996.json", "replace_existing": True}
        )

    def _review(self, wizard, updated):
        """Press Review, end the request, check the import ran inside it."""
        wizard.action_preview()
        # End of the Review request: cr.commit() flushes what is pending.
        self.env.flush_all()
        expected = (0, updated, False)
        found = (wizard.result_created, wizard.result_updated, wizard.result_errors)
        self.assertEqual(
            found,
            expected,
            f"[SETUP] the import did not run inside Review: expected "
            f"(created, updated, errors) = {expected} | found {found}",
        )

    def test_users_review_writes_nothing(self):
        before = self._row("ai_mcp_user", self.mcp_user.id)
        self.assertNotEqual(
            before[1], LABEL, f"[SETUP] ai_mcp_user already holds {LABEL!r}"
        )
        wizard = self._wizard(
            "ai.import.users.wizard",
            [{"login": self.user.login, "last_mcp_client_label": LABEL}],
        )
        self._review(wizard, updated=1)
        after = self._row("ai_mcp_user", self.mcp_user.id)
        self.assertEqual(
            after,
            before,
            f"[HYPOTHESIS] Review left the import written in ai_mcp_user: "
            f"expected (ctid, last_mcp_client_label) = {before} | found {after}",
        )

    def test_providers_review_writes_nothing(self):
        before = self._row("ai_provider", self.provider.id)
        self.assertEqual(
            float(before[1]), 0.7, f"[SETUP] expected temperature 0.7 | found {before[1]}"
        )
        wizard = self._wizard(
            "ai.import.servers.wizard",
            [
                {
                    "name": "Seges 3996 p21",
                    "temperature": 0.42,
                    "selected_model": "seges-3996-p21-model",
                }
            ],
        )
        self._review(wizard, updated=1)
        after = self._row("ai_provider", self.provider.id)
        self.assertEqual(
            after,
            before,
            f"[HYPOTHESIS] Review left the import written in ai_provider: "
            f"expected (ctid, temperature) = {before} | found {after}",
        )

    def test_users_review_keeps_groups(self):
        writer = self.env.ref(WRITER)
        self.assertFalse(
            self._in_group_db(writer), "[SETUP] the user is already in group_ai_writer"
        )
        wizard = self._wizard(
            "ai.import.users.wizard", [{"login": self.user.login, "is_ai_writer": True}]
        )
        cls = type(wizard)
        snapshot = cls._preview_snapshot
        seen = []

        def _snapshot(wiz):
            # Code that asks has_group during the preview (as
            # ai.mcp.user._export_user_dict does): the answer lands in the ormcache.
            seen.append(self.user.has_group(WRITER))
            return snapshot(wiz)

        with mock.patch.object(cls, "_preview_snapshot", _snapshot):
            self._review(wizard, updated=1)
        self.assertEqual(
            seen,
            [True],
            f"[SETUP] the import did not add group_ai_writer inside Review: "
            f"expected has_group() == [True] during the preview | found {seen}",
        )
        self.assertFalse(
            self._in_group_db(writer),
            "[HYPOTHESIS] Review left the user in group_ai_writer: "
            "expected no row in res_groups_users_rel | found one",
        )
        self.assertFalse(
            self.user.has_group(WRITER),
            "[HYPOTHESIS] has_group('pns_ai_mcp.group_ai_writer') is still True "
            "after Review, while the database has no row: expected False | found "
            "True (the ormcache kept the answer from the rolled-back savepoint)",
        )

    def test_import_still_applies(self):
        wizard = self._wizard(
            "ai.import.users.wizard",
            [{"login": self.user.login, "last_mcp_client_label": LABEL}],
        )
        wizard.action_import()
        found = self._row("ai_mcp_user", self.mcp_user.id)[1]
        self.assertEqual(
            found,
            LABEL,
            f"[GUARD] Import does not write last_mcp_client_label: expected "
            f"{LABEL!r} | found {found!r}; a green Review test would mean nothing",
        )
