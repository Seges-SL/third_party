# Copyright 2026 Seges
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
"""Can an AI Administrator without Settings open the Review and result
screens? (patch 36, PNS-103)

get_view of pns.operation.report.wizard swaps the wizard's form for a pns_base
screen when the context carries its form_view_ref
(pns_base/models/operation_report_wizard.py:354-360). _inject_screen_arch
reads that screen as the current user: self.env.ref(xmlid).arch (:332-333).
In Odoo 17 only base.group_system reads ir.ui.view
(odoo/addons/base/security/ir.model.access.csv:34-35): without the patch an
AI Administrator without Settings gets AccessError on both screens.

The web client sends get_views only lang and *_view_ref, so the screens are
requested with form_view_ref alone.

The ORM cache is shared by every user of the transaction and arch is a
non-stored compute: an arch left in cache by a sudo read would skip the ACL.
Every read first empties the cache of both screens.

Every failure message starts with a tag:
- [HYPOTHESIS]: the check this test exists for failed;
- [SETUP]: a precondition failed; says nothing about the hypothesis;
- [GUARD]: a check that must hold with and without the patch failed.
Unexpected exceptions show up as errors, not as failures.
"""

import base64
import json

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

MODELS = ("ai.import.servers.wizard", "ai.import.users.wizard")
PREVIEW_VIEW = "pns_base.view_pns_import_preview_form"
RESULT_VIEW = "pns_base.view_pns_operation_result_form"
SCREENS = (PREVIEW_VIEW, RESULT_VIEW)
PREVIEW_MARK = "o_pns_import_preview"
RESULT_MARK = "o_pns_op_result"


@tagged("post_install", "-at_install")
class TestReviewViews(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.aiadm = new_test_user(
            cls.env,
            login="seges_3996_p36_aiadm",
            groups="base.group_user,pns_ai_mcp.group_ai_admin",
        )
        cls.access = new_test_user(
            cls.env,
            login="seges_3996_p36_access",
            groups="base.group_user,base.group_erp_manager,pns_ai_mcp.group_ai_admin",
        )
        cls.plain = new_test_user(
            cls.env,
            login="seges_3996_p36_plain",
            groups="base.group_user,pns_ai_mcp.group_ai_conversational",
        )
        cls.target = new_test_user(
            cls.env, login="seges_3996_p36_target", groups="base.group_user"
        )
        McpUser = cls.env["ai.mcp.user"]
        cls.target_mcp = McpUser.search(
            [("user_id", "=", cls.target.id)], limit=1
        ) or McpUser.create({"user_id": cls.target.id})
        cls.screens = cls.env["ir.ui.view"].browse(
            [cls.env.ref(xmlid).id for xmlid in SCREENS]
        )
        cls.admins = (cls.aiadm, cls.access)

    def _forget_screens(self):
        self.screens.invalidate_recordset()

    def _screen_arch(self, user, model, screen):
        """The form get_view gives *user* for *screen*; AccessError propagates."""
        self._forget_screens()
        Wizard = self.env[model].with_user(user).with_context(form_view_ref=screen)
        return Wizard.get_view(view_type="form")["arch"]

    def _check_screen(self, user, model, screen, mark, problems):
        try:
            arch = self._screen_arch(user, model, screen)
        except AccessError as exc:
            first = str(exc).splitlines()[0]
            problems.append(f"{user.login} / {model} / {screen}: AccessError: {first}")
            return
        self.assertIn(
            mark,
            arch,
            f"[SETUP] {user.login} / {model}: expected the screen {screen} "
            f"(class {mark}) | found another form",
        )

    def _fail_if(self, problems):
        if problems:
            self.fail(
                "[HYPOTHESIS] an AI Administrator without Settings cannot open the "
                "screen: expected its arch | found:\n" + "\n".join(problems)
            )

    def _wizard(self, user, model, rows):
        data = base64.b64encode(json.dumps(rows).encode())
        return (
            self.env[model]
            .with_user(user)
            .create(
                {
                    "json_file": data,
                    "filename": "seges_3996_p36.json",
                    "replace_existing": True,
                }
            )
        )

    def _check_action(self, user, action, screen):
        found = action["context"].get("form_view_ref")
        self.assertEqual(
            found,
            screen,
            f"[SETUP] {user.login}: expected form_view_ref {screen!r} | found {found!r}",
        )

    def test_precondition_screens_not_readable(self):
        for user in self.admins:
            self.assertFalse(
                user.has_group("base.group_system"),
                f"[SETUP] {user.login} has Settings: expected a user without "
                f"base.group_system",
            )
            for xmlid in SCREENS:
                self._forget_screens()
                view = self.env.ref(xmlid).with_user(user)
                with self.assertRaises(
                    AccessError,
                    msg=f"[SETUP] {user.login} reads {xmlid}.arch: expected "
                    f"AccessError on ir.ui.view | found no error",
                ):
                    self.assertTrue(view.arch)
        self.assertFalse(
            self.aiadm.has_group("base.group_erp_manager"),
            "[SETUP] expected aiadm without base.group_erp_manager | found it",
        )
        self.assertTrue(
            self.access.has_group("base.group_erp_manager"),
            "[SETUP] expected access with base.group_erp_manager | found it missing",
        )

    def test_admin_gets_review_screen(self):
        problems = []
        for user in self.admins:
            for model in MODELS:
                self._check_screen(user, model, PREVIEW_VIEW, PREVIEW_MARK, problems)
        self._fail_if(problems)

    def test_admin_gets_result_screen(self):
        problems = []
        for user in self.admins:
            for model in MODELS:
                self._check_screen(user, model, RESULT_VIEW, RESULT_MARK, problems)
        self._fail_if(problems)

    def test_admin_users_review_and_result(self):
        model = "ai.import.users.wizard"
        problems = []
        for user in self.admins:
            label = f"seges-3996-p36-{user.login}"
            wizard = self._wizard(
                user, model, [{"login": self.target.login, "last_mcp_client_label": label}]
            )
            action = wizard.action_preview()
            self._check_action(user, action, PREVIEW_VIEW)
            self._check_screen(user, model, PREVIEW_VIEW, PREVIEW_MARK, problems)
            action = wizard.action_import()
            self._check_action(user, action, RESULT_VIEW)
            found = (wizard.result_errors, wizard.result_updated)
            self.assertEqual(
                found,
                (False, 1),
                f"[SETUP] {user.login}: expected (errors, updated) = (False, 1) "
                f"| found {found}",
            )
            self._check_screen(user, model, RESULT_VIEW, RESULT_MARK, problems)
        self._fail_if(problems)

    def test_admin_servers_review_and_result(self):
        model = "ai.import.servers.wizard"
        Provider = self.env["ai.provider"].with_context(active_test=False)
        problems = []
        for user in self.admins:
            name = f"Seges 3996 p36 {user.login}"
            wizard = self._wizard(user, model, [{"name": name, "temperature": 0.42}])
            action = wizard.action_preview()
            self._check_action(user, action, PREVIEW_VIEW)
            self._check_screen(user, model, PREVIEW_VIEW, PREVIEW_MARK, problems)
            action = wizard.action_import()
            self._check_action(user, action, RESULT_VIEW)
            found = (
                wizard.result_errors,
                wizard.result_created,
                Provider.search_count([("name", "=", name)]),
            )
            self.assertEqual(
                found,
                (False, 1, 1),
                f"[SETUP] {user.login}: expected (errors, created, providers) = "
                f"(False, 1, 1) | found {found}",
            )
            self._check_screen(user, model, RESULT_VIEW, RESULT_MARK, problems)
        self._fail_if(problems)

    def test_non_admin_still_refused(self):
        self.assertFalse(
            self.plain.has_group("pns_ai_mcp.group_ai_admin"),
            "[SETUP] expected plain without group_ai_admin | found it",
        )
        for model in MODELS:
            for screen in SCREENS:
                with self.assertRaises(
                    AccessError,
                    msg=f"[GUARD] {self.plain.login} opened {screen} on {model}: "
                    f"expected AccessError | found the screen",
                ):
                    self._screen_arch(self.plain, model, screen)
            with self.assertRaises(
                AccessError,
                msg=f"[GUARD] {self.plain.login} created {model}: expected "
                f"AccessError | found a wizard",
            ):
                self._wizard(self.plain, model, [])
