# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ai.agent inherit: delete guards and inference/MCP agent-code resolution."""

import logging

from odoo import api, models, _
from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
from odoo.exceptions import UserError

from ..utils.ai_agent_registry import (
    FEATURE_AGENT_CODES,
    MCP_BARE_AGENT_CODE,
)

_logger = logging.getLogger(__name__)

# Backward-compatible alias for tests and controllers.
MCP_BARE_AGENT_CODE_DEFAULT = MCP_BARE_AGENT_CODE


class AIAgent(models.Model):
    _inherit = 'ai.agent'

    def unlink(self):
        # A module's uninstall removes its own agent; links go with it (cascade).
        # An agent the module no longer ships is a leftover: the person deletes
        # the row, and its provider links and context links go with it. The
        # context records stay in the catalog.
        if self.env.context.get(MODULE_UNINSTALL_FLAG):
            return super(AIAgent, self).unlink()
        for agent in self:
            if agent.origin == 'module' and not agent._module_ships_agent(agent):
                continue
            if agent.provider_ids:
                raise UserError(_(
                    "Cannot delete agent '%s': remove provider failovers first."
                ) % agent.name)
            if agent.context_ids:
                raise UserError(_(
                    "Cannot delete agent '%s': remove or reassign its contexts first."
                ) % agent.name)
        return super(AIAgent, self).unlink()

    @api.model
    def resolve_inference_agent_code(self, agent_code=None, consumer_key=None):
        """Resolve inference agent from explicit code or a fixed feature key."""
        code = (agent_code or '').strip()
        if not code and consumer_key:
            code = (FEATURE_AGENT_CODES.get(consumer_key) or '').strip()
        if not code:
            raise UserError(_(
                "Inference agent code is required. "
                "Pass agent_code or a known feature key."
            ))
        agent = self.search([('code', '=', code), ('active', '=', True)], limit=1)
        if not agent:
            raise UserError(_(
                "Inference agent '%s' is not configured or inactive."
            ) % code)
        return code

    @api.model
    def get_mcp_bare_agent_code(self):
        """Agent code for bare /mcp URLs (no path segment)."""
        return MCP_BARE_AGENT_CODE

    @api.model
    def resolve_mcp_agent_code(self, agent_code=None):
        """MCP entry: explicit path segment or fixed bare /mcp agent."""
        explicit = (agent_code or '').strip()
        code = explicit or MCP_BARE_AGENT_CODE
        agent = self.search([('code', '=', code), ('active', '=', True)], limit=1)
        if not agent:
            raise UserError(_(
                "MCP agent '%s' is not configured or inactive. "
                "Install the module that owns this agent or check the URL path."
            ) % code)
        return code

    def action_open_form(self):
        """Open this agent configuration form (from settings catalog)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'ai.agent',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }
