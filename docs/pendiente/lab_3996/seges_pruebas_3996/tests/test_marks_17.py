# Copyright 2026 Seges
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
"""Marked rows of the chat (stage F1.5, F1-11, decision 106).

The real flow: /chatboo/stream calls session.remember_marks(data.get('refs'))
as the user (pns_ai_chatboo/controllers/chatboo.py:836); remember_marks keeps
what pns_ai_mcp/utils/record_marks.py clean_marks returns, and the next turn
sends it to the engine as "the records the user tapped". clean_marks only
checks that the model is a string and the id positive.

- test_t3_marks_checked_on_save (T3): as an internal user, remember_marks with
  three refs: a record the user cannot read (an ir.config_parameter created
  here), an id that does not exist, and a partner the user can read. Only the
  partner should stay. Red today.

No network, no LLM. Only a user, a session, a parameter and a partner created here.

Every failure message starts with a tag:
- [HYPOTHESIS]: the check this test exists for failed (expected today);
- [SETUP]: a precondition failed; says nothing about the marks.
"""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestMarks17(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_u = new_test_user(
            cls.env, login="lab3996_marks_u", groups="base.group_user",
        )
        cls.param = cls.env["ir.config_parameter"].sudo().create({
            "key": "lab3996.marks.unreadable", "value": "x",
        })
        cls.partner = cls.env["res.partner"].create({"name": "lab3996 marks partner"})

    def test_t3_marks_checked_on_save(self):
        try:
            session = self.env["chatboo.session"].sudo().create({
                "name": "lab3996 marks session", "user_id": self.user_u.id,
            })
        except Exception as exc:  # noqa: BLE001
            self.fail(f"[SETUP] could not create a chatboo.session: {exc!r}")
        Param = self.env["ir.config_parameter"].with_user(self.user_u)
        with self.assertRaises(AccessError, msg="[SETUP] user U can read ir.config_parameter"):
            Param.browse(self.param.id).read(["key"])
        self.partner.with_user(self.user_u).read(["name"])  # [SETUP] U reads the partner
        self.env.cr.execute("SELECT COALESCE(MAX(id), 0) + 100000 FROM res_partner")
        missing_id = self.env.cr.fetchone()[0]
        self.assertFalse(
            self.env["res.partner"].browse(missing_id).exists(),
            "[SETUP] the missing partner id exists",
        )

        refs = [
            {"model": "ir.config_parameter", "id": self.param.id, "label": "t"},
            {"model": "res.partner", "id": missing_id, "label": "t"},
            {"model": "res.partner", "id": self.partner.id, "label": "t"},
        ]
        session.with_user(self.user_u).remember_marks(refs)
        kept = [(m["model"], m["id"]) for m in session.get_marks()]
        self.assertEqual(
            kept, [("res.partner", self.partner.id)],
            f"[HYPOTHESIS] remember_marks kept marks the user cannot read or "
            f"that do not exist; kept {kept!r} (unreadable "
            f"ir.config_parameter#{self.param.id}, missing res.partner#{missing_id})",
        )
