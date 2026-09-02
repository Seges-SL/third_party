# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""v3.1.363: factory spoken knowledge is EN + es_ES; drop linguistic clones."""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

# Import never deletes orphans. Spoken factory = generic + es_ES only.
# Payroll country packs are NOT in this list.
_ORPHAN_CODES = (
    'corporate_terms_en_US',
    'corporate_terms_fr_FR',
    'corporate_terms_de_DE',
    'corporate_terms_it_IT',
    'corporate_terms_es_MX',
    'corporate_terms_es_AR',
    'corporate_terms_pt_BR',
    'trial_balance_en_US',
    'trial_balance_fr_FR',
    'trial_balance_de_DE',
    'trial_balance_it_IT',
    'trial_balance_es_MX',
    'trial_balance_es_AR',
    'trial_balance_pt_BR',
    'hr_contracts_es_ES',
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.context' not in env:
        return
    Context = env['ai.context'].with_context(
        skip_hardcoded_restrictions=True,
        active_test=False,
    )
    rows = Context.search([('code', 'in', list(_ORPHAN_CODES))])
    if 'source_module' in Context._fields:
        rows = rows.filtered(
            lambda r: (not r.source_module) or r.source_module == 'pns_ai_mcp'
        )
    if rows:
        _logger.info(
            'pns_ai_mcp 3.1.363: unlink factory spoken clones %s',
            rows.mapped('code'),
        )
        rows.unlink()
