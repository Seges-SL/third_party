# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Wizard: display the result of an agent's cache rebuild.

After the user clicks "Rebuild cache" on an agent form, this wizard
shows an HTML report with before/after sizes, timestamps, and the
list of contexts that were assembled.

Model: ``pns_ai_mcp.agent.cache.rebuild.wizard``
"""
from odoo import api, fields, models


class AIAgentCacheRebuildWizard(models.TransientModel):
    """Shows the result of rebuilding an agent's cached system prompt.

    Inherits ``pns.operation.report.wizard`` which provides the
    ``result_html`` field and the standard report layout.
    """
    _name = 'pns_ai_mcp.agent.cache.rebuild.wizard'
    _inherit = ['pns.operation.report.wizard']
    _description = 'Agent cache rebuild result'

    agent_id = fields.Many2one(
        'ai.agent',
        required=True,
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        agent = self.env['ai.agent'].browse(
            res.get('agent_id') or self.env.context.get('default_agent_id')
        )
        if agent:
            res['agent_id'] = agent.id
            res['result_html'] = agent._build_cache_rebuild_report_html()
        return res
