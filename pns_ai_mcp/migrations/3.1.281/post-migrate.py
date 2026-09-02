# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""v3.1.281: dual-wire pull defaults on MCP agent; soft ACL context."""
import logging

_logger = logging.getLogger(__name__)

_DEFAULT_CTX = '@pns_ai_mcp\nacl_security'


def migrate(cr, version):
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'ai_agent'
          AND column_name IN (
            'default_context_codes', 'default_skill_codes',
            'required_context_codes'
          )
        """
    )
    cols = {r[0] for r in cr.fetchall()}
    if 'default_context_codes' not in cols:
        _logger.info('pns_ai_mcp 3.1.281: default_context_codes column missing; skip')
        return
    cr.execute(
        """
        UPDATE ai_agent
           SET default_context_codes = %s
         WHERE code = 'pns_ai_mcp'
           AND (default_context_codes IS NULL OR default_context_codes = '')
        """,
        (_DEFAULT_CTX,),
    )
    _logger.info(
        'pns_ai_mcp 3.1.281: seeded default_context_codes on pns_ai_mcp (%s rows)',
        cr.rowcount,
    )
