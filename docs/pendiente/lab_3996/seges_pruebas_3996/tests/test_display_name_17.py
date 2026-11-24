# Copyright 2026 Seges
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
"""display_name of two pns_ai_mcp models on the Odoo 17 core (stage F1.4, case 25).

On Odoo 17, display_name is computed by _compute_display_name, which converts
the _rec_name field and never calls name_get (odoo/models.py:1660-1675);
name_get is deprecated and only reads display_name (:1677-1695). Both models
keep the Odoo 14 name_get override and have no _compute_display_name.

- test_provider_model_label_from_name_get (1, [HYPOTHESIS], F1-2):
  ai.provider.model with a title different from its name shows
  "<title> (<name>)", the label of its name_get (ai_provider.py:80-87).
  Expected red while the name_get is not used: the label is the name.
- test_mcp_user_label_is_user_name (2): the display_name of ai.mcp.user
  (_rec_name = 'user_id') is the name of its user, the label of its
  name_get (mcp_user.py:536-543). Expected green.

No network, no LLM. Only records created here.

Every failure message starts with a tag:
- [HYPOTHESIS]: the label this test asserts did not hold (test 1);
- [CHECK]: the behaviour this test documents did not hold;
- [SETUP]: a precondition failed; says nothing about display_name.
"""

from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestDisplayName17(TransactionCase):
    def test_provider_model_label_from_name_get(self):
        rec = self.env["ai.provider.model"].create(
            {"name": "lab-slug", "title": "Lab Title"}
        )
        self.assertEqual(
            (rec.name, rec.title),
            ("lab-slug", "Lab Title"),
            "[SETUP] expected the record with the given name and title",
        )
        self.assertEqual(
            rec.display_name,
            "Lab Title (lab-slug)",
            "[HYPOTHESIS] expected the display_name of ai.provider.model "
            "to be the label of its name_get",
        )

    def test_mcp_user_label_is_user_name(self):
        user = new_test_user(
            self.env, login="lab3996_dn_user", name="Lab Display User",
            groups="base.group_user",
        )
        McpUser = self.env["ai.mcp.user"].sudo().with_context(
            mcp_skip_ensure_all_users=True
        )
        row = McpUser.search([("user_id", "=", user.id)], limit=1)
        if not row:
            row = McpUser.create({"user_id": user.id})
        self.assertEqual(
            row.user_id, user,
            "[SETUP] expected one ai.mcp.user for the test user",
        )
        self.assertEqual(
            row.display_name,
            user.name,
            "[CHECK] expected the display_name of ai.mcp.user to be "
            "the name of its user",
        )
