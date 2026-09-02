# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""v2.1.217: dual wire — pull lists; take ownership of UI contexts; drop auto_link."""
import logging

_logger = logging.getLogger(__name__)

_CHATBOO_OWNED = (
    'presentation_grids',
    'ui_focus',
    'self',
    'self_es_ES',
    'self_en_US',
)
_DEFAULT_CTX = '@pns_ai_mcp\n@pns_ai_chatboo\nacl_security'
_DEFAULT_SKILL = '@pns_ai_chatboo'


def migrate(cr, version):
    try:
        from odoo import api, SUPERUSER_ID
        env = api.Environment(cr, SUPERUSER_ID, {})
    except Exception:
        _logger.warning(
            'pns_ai_chatboo 2.1.217: could not build env', exc_info=True,
        )
        env = None

    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'ai_agent'
          AND column_name = 'default_context_codes'
        """
    )
    if not cr.fetchone():
        _logger.info('pns_ai_chatboo 2.1.217: columns missing; skip agent seed')
    else:
        cr.execute(
            """
            UPDATE ai_agent
               SET auto_link_mcp_nucleus = FALSE,
                   default_context_codes = %s,
                   default_skill_codes = %s
             WHERE code = 'pns_ai_chatboo'
            """,
            (_DEFAULT_CTX, _DEFAULT_SKILL),
        )
        _logger.info(
            'pns_ai_chatboo 2.1.217: dual-wire pull on Chatboo (%s rows)',
            cr.rowcount,
        )

    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ai_context' AND column_name = 'source_module'
        """
    )
    if cr.fetchone():
        cr.execute(
            """
            UPDATE ai_context
               SET source_module = 'pns_ai_chatboo'
             WHERE code IN %s
               AND (owner_id IS NULL)
            """,
            (_CHATBOO_OWNED,),
        )
        _logger.info(
            'pns_ai_chatboo 2.1.217: ownership transfer for UI contexts (%s)',
            cr.rowcount,
        )

    if env is not None and 'ai.context' in env:
        try:
            env['ai.context'].with_context(
                skip_hardcoded_restrictions=True,
            )._import_all_from_module(
                replace_existing=True,
                module_name='pns_ai_chatboo',
                only_codes=list(_CHATBOO_OWNED),
            )
            agent = env['ai.agent'].search(
                [('code', '=', 'pns_ai_chatboo')], limit=1,
            )
            if agent:
                agent.action_reset_contexts_to_default()
        except Exception:
            _logger.warning(
                'pns_ai_chatboo 2.1.217: reimport/reset failed',
                exc_info=True,
            )
