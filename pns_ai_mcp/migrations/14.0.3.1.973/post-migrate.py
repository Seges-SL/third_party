# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 35 (NUEVO-2, robustez). Ver docs/pendiente/parches_pns_ai.md
"""Fix the code of the two cache GC crons after an upgrade to 3.1.973.

Both crons are noupdate data, so an upgrade from 3.1.782 or 3.1.879 keeps their old code
``model.gc_expired()``, a method that 3.1.973 renamed to ``_gc_expired``: the crons then
fail every hour. Only the exact old code is rewritten; a code edited by hand is left alone
with a warning, and a code already correct is not touched.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger('odoo.addons.pns_ai_mcp.migrations.seges_35')

OLD_CODE = 'model.gc_expired()'
NEW_CODE = 'model._gc_expired()'
CRON_XMLIDS = (
    'pns_ai_mcp.ir_cron_ai_fetch_cache_gc',
    'pns_ai_mcp.ir_cron_ai_api_result_cache_gc',
)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in CRON_XMLIDS:
        cron = env.ref(xmlid, raise_if_not_found=False)
        if not cron or cron._name != 'ir.cron':
            _logger.warning('Seges patch 35: %s not found; nothing changed', xmlid)
            continue
        code = (cron.code or '').strip()
        if code == NEW_CODE:
            continue
        if code != OLD_CODE:
            _logger.warning('Seges patch 35: %s has unexpected code; left unchanged', xmlid)
            continue
        cron.write({'code': NEW_CODE})
        _logger.info('Seges patch 35: %s fixed (gc_expired -> _gc_expired)', xmlid)
