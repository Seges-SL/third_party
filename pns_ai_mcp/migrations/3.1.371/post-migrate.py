# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.371: drop leftover disc_* twins; rewrite stale discover/translation types."""
import logging

from odoo import api, SUPERUSER_ID
from odoo.tools import sql

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not sql.table_exists(cr, 'ai_context'):
        return

    cr.execute(
        """
        UPDATE ai_context
           SET context_type = 'discovery'
         WHERE context_type = 'discover'
        """
    )
    cr.execute(
        """
        UPDATE ai_context
           SET context_type = 'locale'
         WHERE context_type = 'translation'
        """
    )

    env = api.Environment(cr, SUPERUSER_ID, {
        'active_test': False,
        'skip_hardcoded_restrictions': True,
    })
    Ctx = env['ai.context']
    leftovers = Ctx.search([]).filtered(
        lambda c: (c.code or '').startswith('disc_')
        and not (c.code or '').startswith('discovery_')
    )
    twins = Ctx.browse()
    rename = Ctx.browse()
    for old in leftovers:
        new_code = 'discovery_' + old.code[5:]
        if Ctx.search([('code', '=', new_code)], limit=1):
            twins |= old
        else:
            rename |= old
    if twins:
        twins.unlink()
        _logger.info(
            'pns_ai_mcp 3.1.371: removed %s superseded disc_* rows',
            len(twins),
        )
    for old in rename:
        old.write({
            'code': 'discovery_' + old.code[5:],
            'context_type': 'discovery',
            'rel_path': (old.rel_path or '')
            .replace('/discover/', '/discovery/')
            .replace('/disc_', '/discovery_'),
        })
    _logger.info('pns_ai_mcp 3.1.371: leftover discover types rewritten')
