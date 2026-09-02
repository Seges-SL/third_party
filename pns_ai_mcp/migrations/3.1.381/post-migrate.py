# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.381: re-run disc_* purge after the O19 MissingError on stale recordsets."""
from odoo import api, SUPERUSER_ID
from odoo.tools import sql


def migrate(cr, version):
    if not sql.table_exists(cr, 'ai_context'):
        return
    env = api.Environment(cr, SUPERUSER_ID, {
        'active_test': False,
        'skip_hardcoded_restrictions': True,
    })
    env['ai.context']._purge_legacy_disc_leftovers()
