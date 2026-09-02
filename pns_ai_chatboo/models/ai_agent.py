# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""PNS AI Chatboo - Agent extension. PATANEGRA Soft (https://patanegra.com).

Part of Patanegra Soft Suite (`pns_suite`), distributed via Patanegra Soft Hub.
Extends the Patanegra Application Agent Protocol (PAAP) agent with Chatboo chat
settings.
Licensed under the Apache License 2.0 - see LICENSE.
"""
from odoo import api, fields, models

from ..utils.chatboo_authorship import chatboo_host_identity_registry
from ..utils.chatboo_product_icp import (
    CHATBOO_AGENT_CODE,
    read_product_settings,
    write_product_settings,
)


class AIAgent(models.Model):
    _inherit = 'ai.agent'

    chatboo_show_systray = fields.Boolean(
        string='Show Chatboo in systray',
        help='Show the Chatboo launcher icon in the top navigation bar.',
        compute='_compute_chatboo_product_settings',
        inverse='_inverse_chatboo_show_systray',
    )
    chatboo_dataset_cache_max_mb = fields.Integer(
        string='Dataset reuse limit (MB)',
        help="Max size of the dataset cached from a data query so the NEXT turn "
             "can reformat/reorder the SAME list without re-querying (kernel-like "
             "reuse; data never enters the model context). Bigger datasets are "
             "not cached (the model just reuses the query code). 0 = no limit. "
             "Guards per-turn (de)serialization cost, not DB storage.",
        compute='_compute_chatboo_product_settings',
        inverse='_inverse_chatboo_dataset_cache_max_mb',
    )
    chatboo_query_data_ttl_hours = fields.Integer(
        string='Dataset reuse expiry (hours)',
        help="How long a cached dataset stays reusable. After this it is ignored "
             "and purged by the maintenance cron so blobs never pile up. "
             "0 = never expires (only cleared by session retention).",
        compute='_compute_chatboo_product_settings',
        inverse='_inverse_chatboo_query_data_ttl_hours',
    )

    @api.depends('code')
    def _compute_chatboo_product_settings(self):
        product = read_product_settings(self.env)
        for agent in self:
            if agent.code == CHATBOO_AGENT_CODE:
                agent.chatboo_show_systray = product['show_systray']
                agent.chatboo_dataset_cache_max_mb = product['dataset_cache_max_mb']
                agent.chatboo_query_data_ttl_hours = product['query_data_ttl_hours']
            else:
                agent.chatboo_show_systray = False
                agent.chatboo_dataset_cache_max_mb = 0
                agent.chatboo_query_data_ttl_hours = 0

    def _inverse_chatboo_show_systray(self):
        for agent in self.filtered(lambda a: a.code == CHATBOO_AGENT_CODE):
            write_product_settings(agent.env, show_systray=agent.chatboo_show_systray)

    def _inverse_chatboo_dataset_cache_max_mb(self):
        for agent in self.filtered(lambda a: a.code == CHATBOO_AGENT_CODE):
            write_product_settings(
                agent.env,
                dataset_cache_max_mb=agent.chatboo_dataset_cache_max_mb,
            )

    def _inverse_chatboo_query_data_ttl_hours(self):
        for agent in self.filtered(lambda a: a.code == CHATBOO_AGENT_CODE):
            write_product_settings(
                agent.env,
                query_data_ttl_hours=agent.chatboo_query_data_ttl_hours,
            )

    def _module_factory_seed(self):
        if self.code == CHATBOO_AGENT_CODE:
            return {
                'default_context_codes': '@pns_ai_mcp\n@pns_ai_chatboo',
                'required_context_codes': 'self_chatboo\npresentation_grids\nui_focus',
                'default_skill_codes': '@pns_ai_chatboo',
            }
        return super()._module_factory_seed()

    @api.model
    def _host_identity_registry(self):
        reg = dict(super()._host_identity_registry())
        reg.update(chatboo_host_identity_registry())
        return reg
