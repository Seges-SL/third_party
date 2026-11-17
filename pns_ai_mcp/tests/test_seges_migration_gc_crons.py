# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 35 (NUEVO-2, robustez). Ver docs/pendiente/parches_pns_ai.md
"""NUEVO-2: the cache GC crons keep their old code after an upgrade to 3.1.973.

``ir_cron_ai_fetch_cache_gc`` and ``ir_cron_ai_api_result_cache_gc`` are noupdate data. In
3.1.782 and 3.1.879 their code was ``model.gc_expired()``; 3.1.973 renamed the method to
``_gc_expired``, so an upgraded database keeps a cron that fails on every run. Patch 35 adds
``migrations/14.0.3.1.973/post-migrate.py``, which Odoo only runs on an upgrade that crosses
that version (never on an install), so the script is loaded and called here by hand.

A cron started by hand (``method_direct_trigger``) runs its code through ``safe_eval``, which
turns the ``AttributeError`` into a ``ValueError`` (odoo/tools/safe_eval.py:346-347 of the
image). Every call to ``migrate`` runs inside ``assertLogs`` of the script's logger; a DEBUG
witness line stands for "no line" (Python 3.7 has no ``assertNoLogs``).
"""

import logging

from odoo.modules.migration import load_script
from odoo.modules.module import get_module_resource
from odoo.tests import TransactionCase, tagged

LOGGER_NAME = 'odoo.addons.pns_ai_mcp.migrations.seges_35'
WITNESS = 'seges-35 witness'
FETCH_XMLID = 'pns_ai_mcp.ir_cron_ai_fetch_cache_gc'
API_XMLID = 'pns_ai_mcp.ir_cron_ai_api_result_cache_gc'
OLD_CODE = 'model.gc_expired()'
NEW_CODE = 'model._gc_expired()'
EDITED_CODE = 'model.gc_expired()  # edited'
FROM_VERSION = '14.0.3.1.879'


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesMigrationGcCrons(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        path = get_module_resource(
            'pns_ai_mcp', 'migrations', '14.0.3.1.973', 'post-migrate.py')
        cls.script = load_script(path, 'post-migrate')

    def setUp(self):
        super().setUp()
        self.fetch_cron = self.env.ref(FETCH_XMLID)
        self.api_cron = self.env.ref(API_XMLID)
        (self.fetch_cron | self.api_cron).write({'code': OLD_CODE})

    # ── helpers ───────────────────────────────────────────────────

    def _db_code(self, cron):
        """Code stored in the database, not in the ORM cache."""
        self.env['base'].flush()
        self.env.cr.execute(
            'SELECT code FROM ir_act_server WHERE id = %s', (cron.ir_actions_server_id.id,))
        return self.env.cr.fetchone()[0]

    def _migrate(self, version):
        """Run the script; return its log lines other than the witness."""
        with self.assertLogs(LOGGER_NAME, level='DEBUG') as logs:
            logging.getLogger(LOGGER_NAME).debug(WITNESS)
            self.script.migrate(self.env.cr, version)
        self.assertEqual(logs.records[0].getMessage(), WITNESS)
        return logs.records[1:]

    def _assert_silent(self, records):
        self.assertEqual(
            [r.getMessage() for r in records], [],
            'patch 35 must not log anything here')

    # ── tests ─────────────────────────────────────────────────────

    def test_1_old_code_fails_when_run_by_hand(self):
        """NUEVO-2: with the old code, starting the cron by hand fails."""
        for cron in (self.fetch_cron, self.api_cron):
            with self.subTest(cron=cron.name):
                with self.assertRaises(ValueError) as caught:
                    cron.method_direct_trigger()
                self.assertIn('AttributeError', str(caught.exception))
                self.assertIn('gc_expired', str(caught.exception))

    def test_2_migrate_fixes_both_crons(self):
        records = self._migrate(FROM_VERSION)
        self.assertEqual(self._db_code(self.fetch_cron), NEW_CODE)
        self.assertEqual(self._db_code(self.api_cron), NEW_CODE)
        self.assertEqual([r.levelno for r in records], [logging.INFO, logging.INFO])
        self.assertIn(FETCH_XMLID, records[0].getMessage())
        self.assertIn(API_XMLID, records[1].getMessage())
        for record in records:
            self.assertIn('fixed (gc_expired -> _gc_expired)', record.getMessage())

    def test_3_fixed_crons_run_by_hand(self):
        self._migrate(FROM_VERSION)
        for cron in (self.fetch_cron, self.api_cron):
            with self.subTest(cron=cron.name):
                self.assertEqual(self._db_code(cron), NEW_CODE)
                cron.method_direct_trigger()

    def test_4_second_run_changes_nothing(self):
        self._migrate(FROM_VERSION)
        self._assert_silent(self._migrate(FROM_VERSION))
        self.assertEqual(self._db_code(self.fetch_cron), NEW_CODE)
        self.assertEqual(self._db_code(self.api_cron), NEW_CODE)

    def test_5_edited_code_is_left_unchanged(self):
        self.fetch_cron.write({'code': EDITED_CODE})
        records = self._migrate(FROM_VERSION)
        self.assertEqual(self._db_code(self.fetch_cron), EDITED_CODE)
        warnings = [r for r in records if r.levelno == logging.WARNING]
        self.assertEqual(len(warnings), 1)
        message = warnings[0].getMessage()
        self.assertIn(FETCH_XMLID, message)
        self.assertIn('unexpected code; left unchanged', message)
        self.assertNotIn('edited', message)
        self.assertNotIn(OLD_CODE, message)

    def test_6_new_code_is_not_touched(self):
        (self.fetch_cron | self.api_cron).write({'code': NEW_CODE})
        self._assert_silent(self._migrate(FROM_VERSION))
        self.assertEqual(self._db_code(self.fetch_cron), NEW_CODE)
        self.assertEqual(self._db_code(self.api_cron), NEW_CODE)

    def test_7_missing_cron_is_reported_and_the_other_fixed(self):
        self.fetch_cron.unlink()
        records = self._migrate(FROM_VERSION)
        warnings = [r.getMessage() for r in records if r.levelno == logging.WARNING]
        self.assertEqual(len(warnings), 1)
        self.assertIn(FETCH_XMLID, warnings[0])
        self.assertIn('not found; nothing changed', warnings[0])
        self.assertEqual(self._db_code(self.api_cron), NEW_CODE)
        infos = [r.getMessage() for r in records if r.levelno == logging.INFO]
        self.assertEqual(len(infos), 1)
        self.assertIn(API_XMLID, infos[0])

    def test_8_no_version_changes_nothing(self):
        # Odoo passes '' when there is no installed version (odoo/modules/migration.py:144).
        for version in (None, ''):
            with self.subTest(version=version):
                self._assert_silent(self._migrate(version))
                self.assertEqual(self._db_code(self.fetch_cron), OLD_CODE)
                self.assertEqual(self._db_code(self.api_cron), OLD_CODE)

    def test_9_old_code_with_surrounding_whitespace_is_fixed(self):
        """D35: the old code is compared after strip()."""
        (self.fetch_cron | self.api_cron).write({'code': f'\n  {OLD_CODE}\n'})
        records = self._migrate(FROM_VERSION)
        self.assertEqual(self._db_code(self.fetch_cron), NEW_CODE)
        self.assertEqual(self._db_code(self.api_cron), NEW_CODE)
        self.assertEqual([r.levelno for r in records], [logging.INFO, logging.INFO])
