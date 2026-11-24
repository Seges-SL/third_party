# Copyright 2026 Seges
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
"""pns_base/models/ir_ui_view_patch.py on Odoo 17 (stage F1.1, cases 3 to 6).

Five ordinary tests: each one documents what the patch does today and is
expected green. None of them asserts a safe behaviour that a defect would
turn red, so none carries [HYPOTHESIS].

- test_converter_difficult_values (case 3): _auto_convert_attrs with values
  holding }, {, <, &, quotes; several terms, negation, parent., an empty
  domain; and the forms it leaves unconverted with an ERROR.
- test_no_pns_view_keeps_attrs (case 3): no installed pns* view keeps attrs
  in arch_db and all of them pass _check_xml.
- test_write_hints (case 4): (a) attrs written on a view with no hint is
  rejected by the core with its literal message
  (odoo/addons/base/models/ir_ui_view.py:392-394); (b) on a view whose model
  carries the 'ai.' hint and whose xml_id is NOT pns*, attrs is converted:
  the hint wins over the xml_id; (c) an arch without old syntax is stored
  unchanged on a hinted view.
- test_get_view_class_and_cost (case 6): o_pns_view only on a pns* root
  view, and exactly one extra query per get_view on a non-pns model.
- test_arch_from_file_and_reset (case 5): the file arch (which keeps attrs)
  is converted when read with read_arch_from_file, and reset_arch('hard')
  stores it without a validation error.

Only synthetic views created here and the archs of the installed modules.

Every failure message starts with a tag:
- [CHECK]: the behaviour this test documents did not hold;
- [SETUP]: a precondition failed; says nothing about the patch.
Unexpected exceptions show up as errors, not as failures.
"""

from lxml import etree
from odoo.addons.pns_base.models.ir_ui_view_patch import Base as PnsBase
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_path
from odoo.tools.safe_eval import safe_eval

PATCH_LOGGER = "odoo.addons.pns_base.models.ir_ui_view_patch"
FILE_VIEW = "pns_base.view_module_form_pns_index"
CORE_ATTRS_MSG = (
    'Since 17.0, the "attrs" and "states" attributes are no longer used.\n'
    "View: {name} in {file}"
)


def _field_with_attrs(attrs_src):
    """A <form> with one field whose attrs is serialised by lxml (real escaping)."""
    form = etree.Element("form")
    etree.SubElement(form, "field", name="x", attrs=attrs_src)
    return etree.tostring(form, encoding="unicode")


@tagged("post_install", "-at_install")
class TestViewPatch17(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.View = cls.env["ir.ui.view"]

    def _convert_field(self, attrs_src):
        out = self.View._auto_convert_attrs(_field_with_attrs(attrs_src))
        return etree.fromstring(out).find("field")

    # ------------------------------------------------------------------ case 3
    def test_converter_difficult_values(self):
        strings = {
            "x}y": "a == 'x}y'",
            "x{y": "a == 'x{y'",
            "x<y&z": "a == 'x<y&z'",
            "it's \"q\"": "a == 'it\\'s \"q\"'",
        }
        for value, expected in strings.items():
            node = self._convert_field(f"{{'invisible': [('a', '=', {value!r})]}}")
            self.assertIsNone(node.get("attrs"), f"[CHECK] attrs left for value {value!r}")
            self.assertEqual(
                node.get("invisible"), expected, f"[CHECK] expression for value {value!r}"
            )
            self.assertTrue(
                safe_eval(node.get("invisible"), {"a": value}),
                f"[CHECK] expression false for its own value {value!r}",
            )
            self.assertFalse(
                safe_eval(node.get("invisible"), {"a": "other"}),
                f"[CHECK] expression true for another value ({value!r})",
            )

        node = self._convert_field(
            "{'invisible': ['|', ('a', '=', 1), '&', ('b', '!=', False), "
            "('a', 'in', [1, 2])], 'required': [('a', '=', 3), ('b', '=', False)]}"
        )
        self.assertEqual(
            node.get("invisible"),
            "(a == 1 or (b and a in [1, 2]))",
            "[CHECK] prefix | and & with a nested term",
        )
        self.assertEqual(
            node.get("required"),
            "(a == 3) and (not b)",
            "[CHECK] implicit AND between top-level terms",
        )

        for attrs_src, key, expected in (
            ("{'invisible': ['!', ('a', '=', 1)]}", "invisible", "not (a == 1)"),
            (
                "{'invisible': [('parent.state', '=', 'draft')]}",
                "invisible",
                "parent.state == 'draft'",
            ),
            ("{'readonly': []}", "readonly", "True"),
            (
                "{'column_invisible': [('parent.state', '=', 'done')]}",
                "column_invisible",
                "parent.state == 'done'",
            ),
        ):
            node = self._convert_field(attrs_src)
            self.assertIsNone(node.get("attrs"), f"[CHECK] attrs left: {attrs_src}")
            self.assertEqual(node.get(key), expected, f"[CHECK] {attrs_src}")

        for attrs_src in (
            "{'readonly': [('a', '=', context.get('x'))]}",
            "{'invisible': [('a', 'ilike', 'x')]}",
        ):
            with self.assertLogs(PATCH_LOGGER, "ERROR"):
                node = self._convert_field(attrs_src)
            self.assertEqual(
                node.get("attrs"),
                attrs_src,
                f"[CHECK] unconvertible attrs must be left as-is: {attrs_src}",
            )
            for key in ("invisible", "readonly", "required"):
                self.assertIsNone(node.get(key), f"[CHECK] {key} added for {attrs_src}")

    def test_no_pns_view_keeps_attrs(self):
        imd = self.env["ir.model.data"].search(
            [("model", "=", "ir.ui.view"), ("module", "=like", "pns%")]
        )
        views = self.View.browse(imd.mapped("res_id")).exists()
        self.assertTrue(views, "[SETUP] no pns* view installed")
        with_attrs = []
        for view in views:
            arch = view.arch_db or ""
            if "attrs=" in arch or etree.fromstring(arch.encode()).xpath("//*[@attrs]"):
                with_attrs.append(view.xml_id)
        self.assertFalse(with_attrs, f"[CHECK] pns* views with attrs: {with_attrs}")
        # Raises ValidationError on the first invalid view.
        views._check_xml()

    # ------------------------------------------------------------------ case 4
    def test_write_hints(self):
        attrs_arch = (
            "<form><field name=\"name\" "
            "attrs=\"{'invisible': [('name', '=', False)]}\"/></form>"
        )
        # (a) No hint: the patch does nothing and the core rejects attrs.
        partner_view = self.View.create(
            {
                "name": "seges.3996.partner.form.attrs",
                "model": "res.partner",
                "type": "form",
                "priority": 99,
                "arch": '<form><field name="name"/></form>',
            }
        )
        with self.assertRaises(ValidationError) as cm:
            partner_view.write({"arch": attrs_arch})
        expected = CORE_ATTRS_MSG.format(name=partner_view.name, file=partner_view.arch_fs)
        self.assertEqual(cm.exception.args[0], expected, "[CHECK] core message")

        # (b) Model hint 'ai.' with a non-pns xml_id: the hint wins.
        agent_view = self.View.create(
            {
                "name": "seges.3996.agent.form.hint",
                "model": "ai.agent",
                "type": "form",
                "priority": 99,
                "arch": '<form><field name="name"/></form>',
            }
        )
        self.env["ir.model.data"].create(
            {
                "module": "seges_pruebas_3996",
                "name": "view_3996_agent_hint",
                "model": "ir.ui.view",
                "res_id": agent_view.id,
            }
        )
        agent_view.invalidate_recordset(["xml_id"])
        self.assertEqual(
            agent_view.xml_id,
            "seges_pruebas_3996.view_3996_agent_hint",
            "[SETUP] xml_id of the synthetic view",
        )
        agent_view.write({"arch": attrs_arch})
        node = etree.fromstring(agent_view.arch_db.encode()).find("field")
        self.assertIsNone(node.get("attrs"), "[CHECK] attrs left on the hinted view")
        self.assertEqual(
            node.get("invisible"),
            "not name",
            "[CHECK] hinted view with a non-pns xml_id is converted",
        )

        # (c) No old syntax: stored as written.
        new_arch = '<form><field name="name" invisible="not name"/></form>'
        agent_view.write({"arch": new_arch})
        self.assertEqual(agent_view.arch_db, new_arch, "[CHECK] arch changed")

    # ------------------------------------------------------------------ case 6
    def test_get_view_class_and_cost(self):
        partner = self.env["res.partner"]
        res = partner.get_view(view_type="form")
        root = etree.fromstring(res["arch"])
        self.assertNotIn(
            "o_pns_view",
            (root.get("class") or "").split(),
            "[CHECK] o_pns_view on a non-pns view",
        )

        agent = self.env["ai.agent"]
        res = agent.get_view(view_type="form")
        xml_id = self.View.browse(res["id"]).xml_id
        self.assertTrue(xml_id.startswith("pns"), f"[SETUP] ai.agent form root is {xml_id!r}")
        root = etree.fromstring(res["arch"])
        self.assertIn(
            "o_pns_view",
            (root.get("class") or "").split(),
            f"[CHECK] o_pns_view missing on {xml_id}",
        )

        # Only PnsBase.get_view may sit between the full call and super(PnsBase).
        mro = type(partner).__mro__
        above = [c for c in mro[: mro.index(PnsBase)] if "get_view" in vars(c)]
        self.assertFalse(above, f"[SETUP] get_view overridden above PnsBase: {above}")

        cr = self.env.cr
        # Warm the ormcaches of both paths.
        partner.get_view(view_type="form")
        super(PnsBase, partner).get_view(view_type="form")

        self.env.invalidate_all()
        start = cr.sql_log_count
        partner.get_view(view_type="form")
        full = cr.sql_log_count - start

        self.env.invalidate_all()
        start = cr.sql_log_count
        super(PnsBase, partner).get_view(view_type="form")
        core = cr.sql_log_count - start

        self.assertEqual(
            full - core,
            1,
            f"[CHECK] extra queries per get_view: {full - core} (full {full}, core {core})",
        )

    # ------------------------------------------------------------------ case 5
    def test_arch_from_file_and_reset(self):
        view = self.env.ref(FILE_VIEW)
        self.assertTrue(view.arch_fs, f"[SETUP] {FILE_VIEW} has no arch_fs")
        with open(file_path(view.arch_fs), encoding="utf-8") as fh:
            self.assertIn("attrs=", fh.read(), "[SETUP] the file has no attrs")

        arch = view.with_context(read_arch_from_file=True).arch
        self.assertNotIn("attrs=", arch, "[CHECK] file arch read with attrs")
        self.assertIn(
            'invisible="not pns_index_url"',
            arch,
            "[CHECK] converted modifier missing in the file arch",
        )

        view.reset_arch("hard")
        self.assertNotIn("attrs=", view.arch_db, "[CHECK] attrs stored by reset_arch")
