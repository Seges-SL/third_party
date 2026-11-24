# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 21 (tests de la entrega E2′). Ver docs/pendiente/parches_pns_ai.md
# Seges: adaptado a la 17 (fase 2, T2): los casos de seges_pruebas_3996
# (test_import_review.py), con la lectura ORM y el caso del llamador; los documentos
# que citan las líneas anteriores están en 14.0. Ver docs/pendiente/parches_pns_ai.md
"""Parche 21 (PNS-20): «Review» (``action_preview``) no deja nada escrito.

``action_preview`` (``pns_base/models/operation_report_wizard.py:317-345``)
importa entre un ``SAVEPOINT`` y su ``ROLLBACK TO SAVEPOINT``. Sin el parche,
``_invalidate_after_preview_rollback`` llamaba a ``env.invalidate_all()``, que
vuelca lo pendiente antes de invalidar: lo que la importación dejaba pendiente
se escribía después del rollback y quedaba con la petición. Con el parche
(``:294-303`` y ``:323-335``), como ``_FlushingSavepoint`` del core: se vuelca
lo del llamador antes del ``SAVEPOINT`` (``cr.flush()``) y la importación
dentro (``flush_all()``), y tras el rollback se descarta lo que queda
(``cr.clear()``) y se vacía el ormcache (``registry.clear_cache()``).

El final de la petición de «Review» se simula con ``env.flush_all()``. Las filas
se leen con SQL: el valor y el ``ctid``, que cambia con cada ``UPDATE`` y vuelve
tras ``ROLLBACK TO SAVEPOINT`` (``write_date`` no sirve: ``now()`` es constante en
la transacción del test).

Cada mensaje de fallo empieza con una etiqueta:
- [HYPOTHESIS]: falla la comprobación para la que existe el test;
- [SETUP]: falla una condición previa; no dice nada de la hipótesis;
- [GUARD]: falla algo que debe cumplirse con el parche y sin él.
"""

import base64
import json
from unittest import mock

from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

LABEL = "seges-3996-p21"
CALLER = "seges-3996-p21-caller"
WRITER = "pns_ai_mcp.group_ai_writer"
_ROW_QUERIES = {
    "ai_mcp_user": (
        "SELECT ctid::text, last_mcp_client_label FROM ai_mcp_user WHERE id = %s"
    ),
    "ai_provider": "SELECT ctid::text, temperature FROM ai_provider WHERE id = %s",
}


@tagged("post_install", "-at_install", "pns_ai_mcp", "seges_e2p")
class TestSegesImportPreview(TransactionCase):
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

    def _sql_row(self, table, rec_id):
        """(ctid, value) in the database as it is now, without flushing."""
        self.env.cr.execute(_ROW_QUERIES[table], (rec_id,))
        return self.env.cr.fetchone()

    def _row(self, table, rec_id):
        """(ctid, value) as stored in the database, after flushing the ORM."""
        self.env.flush_all()
        return self._sql_row(table, rec_id)

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

    def _providers_wizard(self):
        return self._wizard(
            "ai.import.servers.wizard",
            [
                {
                    "name": "Seges 3996 p21",
                    "temperature": 0.42,
                    "selected_model": "seges-3996-p21-model",
                }
            ],
        )

    def _check_import_ran(self, wizard, updated):
        expected = (0, updated, False)
        found = (wizard.result_created, wizard.result_updated, wizard.result_errors)
        self.assertEqual(
            found,
            expected,
            f"[SETUP] the import did not run inside Review: expected "
            f"(created, updated, errors) = {expected} | found {found}",
        )

    def _review(self, wizard, updated):
        """Press Review, end the request, check the import ran inside it."""
        wizard.action_preview()
        # End of the Review request: cr.commit() flushes what is pending.
        self.env.flush_all()
        self._check_import_ran(wizard, updated)

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
        wizard = self._providers_wizard()
        self._review(wizard, updated=1)
        # Read through the ORM without invalidating: the cache must not keep
        # the value the rollback undid.
        found = self.provider.temperature
        self.assertEqual(
            found,
            0.7,
            f"[HYPOTHESIS] after Review the ORM still gives the import's value: "
            f"expected temperature 0.7 | found {found}",
        )
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

    def test_caller_pending_write_survives_review(self):
        """What the caller left pending before Review is written, not lost."""
        wizard = self._providers_wizard()
        self.mcp_user.last_mcp_client_label = CALLER
        field = self.mcp_user._fields["last_mcp_client_label"]
        self.assertIn(
            field,
            self.env.cache.get_dirty_fields(),
            "[SETUP] the caller's write is not pending in the cache",
        )
        stored = self._sql_row("ai_mcp_user", self.mcp_user.id)[1]
        self.assertNotEqual(
            stored,
            CALLER,
            f"[SETUP] the caller's write is already in the database: found {stored!r}",
        )
        wizard.action_preview()
        stored = self._sql_row("ai_mcp_user", self.mcp_user.id)[1]
        self.assertEqual(
            stored,
            CALLER,
            f"[GUARD] right after Review the caller's write is not in the database: "
            f"expected {CALLER!r} | found {stored!r}",
        )
        # End of the Review request.
        self.env.flush_all()
        self._check_import_ran(wizard, updated=1)
        stored = self._sql_row("ai_mcp_user", self.mcp_user.id)[1]
        self.assertEqual(
            stored,
            CALLER,
            f"[GUARD] at the end of the request the caller's write is lost: "
            f"expected {CALLER!r} | found {stored!r}",
        )
        found = self.mcp_user.last_mcp_client_label
        self.assertEqual(
            found,
            CALLER,
            f"[GUARD] the ORM lost the caller's write: expected {CALLER!r} "
            f"| found {found!r}",
        )
