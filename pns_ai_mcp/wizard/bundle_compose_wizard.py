# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Wizard: compose an agent's context membership interactively.

Opens a checklist of all candidate contexts (canonical, non-hardcoded)
and lets the administrator add/remove them from the agent's composition.
After each change the agent's cached system prompt is rebuilt.

Models
------
``pns_ai_mcp.agent.compose.wizard``
    TransientModel — one wizard instance per compose session.
``pns_ai_mcp.agent.compose.line``
    TransientModel — one line per candidate context.
"""
from odoo import api, fields, models, _

from ..utils import context_roles


class AIAgentComposeWizard(models.TransientModel):
    """Interactive context composition wizard for an ai.agent.

    Usage (from the agent form view):
        1. Click "Compose" → wizard opens pre-populated with all
           candidate contexts and their current membership status.
        2. Check contexts to add/remove, click the corresponding button.
        3. The agent's context_ids and cached_content are updated
           immediately.

    The wizard is reloaded after each action so the "in composition"
    column reflects the new state.
    """
    _name = 'pns_ai_mcp.agent.compose.wizard'
    _description = 'Compose agent context membership'

    agent_id = fields.Many2one(
        'ai.agent',
        required=True,
        ondelete='cascade',
    )
    line_ids = fields.One2many(
        'pns_ai_mcp.agent.compose.line',
        'wizard_id',
        string='Candidate contexts',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        agent = self.env['ai.agent'].browse(
            res.get('agent_id') or self.env.context.get('default_agent_id')
        )
        if agent:
            res['agent_id'] = agent.id
            res['line_ids'] = self._prepare_lines(agent)
        return res

    def _prepare_lines(self, agent):
        """Build One2many creation commands for all candidate contexts.

        Candidates = canonical contexts (non-hardcoded).  Hardcoded
        contexts are transversal — they are injected into every agent's
        prompt automatically and should not appear here.

        Args:
            agent: ai.agent record whose composition is being edited.

        Returns:
            list of (0, 0, vals) commands for line_ids.
        """
        Context = self.env['ai.context']
        contexts = Context.get_canonical_contexts_for_agent().filtered(
            lambda c: context_roles.is_agent_composable(c.context_type)
        )
        lines = []
        for ctx in contexts:
            lines.append((0, 0, {
                'context_id': ctx.id,
                'in_composition': self._family_in_agent(ctx, agent),
                'selected': False,
            }))
        return lines

    def _family_in_agent(self, context, agent):
        """Check if any locale variant of *context* is in the agent's composition."""
        family_ids = set(context.family_context_ids())
        return bool(family_ids & set(agent.context_ids.ids))

    def _reload_wizard(self):
        """Reload the wizard form with fresh data after a composition change."""
        self.ensure_one()
        self.line_ids.unlink()
        for command in self._prepare_lines(self.agent_id):
            self.write({'line_ids': [command]})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_add_to_agent(self):
        """Add selected contexts to the agent's composition."""
        self.ensure_one()
        to_add = self.line_ids.filtered(
            lambda line: line.selected and not line.in_composition
        ).mapped('context_id')
        if to_add:
            self.agent_id.write({
                'context_ids': [(4, ctx.id) for ctx in to_add],
            })
            self.agent_id._sync_composition_and_cache()
        return self._reload_wizard()

    def action_remove_from_agent(self):
        """Remove selected contexts from the agent's composition."""
        self.ensure_one()
        to_remove_ids = []
        for line in self.line_ids.filtered(lambda l: l.selected and l.in_composition):
            to_remove_ids.extend(line.context_id.family_context_ids())
        if to_remove_ids:
            self.agent_id.write({
                'context_ids': [(3, ctx_id) for ctx_id in set(to_remove_ids)],
            })
            self.agent_id._sync_composition_and_cache()
        return self._reload_wizard()


class AIAgentComposeLine(models.TransientModel):
    """One line per candidate context in the compose wizard.

    Fields:
        selected: user checkbox — pick this context for the next action.
        in_composition: read-only — True if any locale variant of this
            context is currently in the agent's context_ids.
    """
    _name = 'pns_ai_mcp.agent.compose.line'
    _description = 'Agent composition line'
    # Ordenamos por 'code' (almacenado abajo). El antiguo 'category' ya no existe
    # y en Odoo 19 un _order con un campo inexistente rompe cualquier search
    # (incluido el autovacuum): "Invalid field 'category'".
    _order = 'code'

    wizard_id = fields.Many2one(
        'pns_ai_mcp.agent.compose.wizard',
        required=True,
        ondelete='cascade',
    )
    context_id = fields.Many2one(
        'ai.context',
        required=True,
        ondelete='cascade',
    )
    selected = fields.Boolean(string='Select')
    in_composition = fields.Boolean(string='In composition', readonly=True)
    code = fields.Char(related='context_id.code', store=True, readonly=True)
    context_type = fields.Selection(related='context_id.context_type', readonly=True)
    description = fields.Text(related='context_id.description', readonly=True)

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super().fields_get(allfields=allfields, attributes=attributes)
        info = res.get('context_type')
        if info and info.get('selection'):
            info['selection'] = list(context_roles.TYPE_SELECTION)
        return res
