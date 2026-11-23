# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Extends ai.agent with Chatboo chat settings (host identity, product ICP)."""
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
        string='Hidden list copy (MB)',
        help="Copy of the last table, kept aside so the next message can "
             "reorder it without a new query. Those rows stay out of the "
             "prompt: sending the whole table every turn used to fill it. "
             "A heavier list is skipped. 0 = no size cap.",
        compute='_compute_chatboo_product_settings',
        inverse='_inverse_chatboo_dataset_cache_max_mb',
    )
    chatboo_query_data_ttl_hours = fields.Integer(
        string='Hours that copy lasts',
        help="After this the aside copy is dropped. Tables already on "
             "screen and files you uploaded stay in the session. A later "
             "\"same list, but…\" runs the query again. "
             "0 = the copy lasts as long as the session.",
        compute='_compute_chatboo_product_settings',
        inverse='_inverse_chatboo_query_data_ttl_hours',
    )
    chatboo_history_retention_days = fields.Integer(
        string='Session retention (days)',
        help="The chat you reopen: messages, tables on screen, and uploaded "
             "files. Deleted after this many days with no use. 0 = keep.",
        compute='_compute_chatboo_product_settings',
        inverse='_inverse_chatboo_history_retention_days',
    )
    chatboo_download_max_mb = fields.Integer(
        string='Download limit (MB)',
        help="Max size of a session file chip (named PDF/Excel/Word). "
             "The bubble Excel icon does not use this limit. 0 = no limit.",
        compute='_compute_chatboo_product_settings',
        inverse='_inverse_chatboo_download_max_mb',
    )
    chatboo_allow_remote_voices = fields.Boolean(
        string='Allow remote voices',
        help='Unchecked: Chatboo only reads aloud with a voice installed on '
             'this computer. Checked: if none is installed, the browser may '
             'send the text to its vendor (Google, Microsoft, …).',
        compute='_compute_chatboo_product_settings',
        inverse='_inverse_chatboo_allow_remote_voices',
    )
    chatboo_upload_max_mb = fields.Integer(
        string='Upload limit (MB)',
        help="Max size of each picture or file sent to the chat. "
             "Bigger ones are refused before the turn starts. 0 = no limit.",
        compute='_compute_chatboo_product_settings',
        inverse='_inverse_chatboo_upload_max_mb',
    )

    @api.depends('code')
    def _compute_chatboo_product_settings(self):
        product = read_product_settings(self.env)
        for agent in self:
            if agent.code == CHATBOO_AGENT_CODE:
                agent.chatboo_show_systray = product['show_systray']
                agent.chatboo_dataset_cache_max_mb = product['dataset_cache_max_mb']
                agent.chatboo_query_data_ttl_hours = product['query_data_ttl_hours']
                agent.chatboo_history_retention_days = product['history_retention_days']
                agent.chatboo_download_max_mb = product['download_max_mb']
                agent.chatboo_upload_max_mb = product['upload_max_mb']
                agent.chatboo_allow_remote_voices = product['allow_remote_voices']
            else:
                agent.chatboo_show_systray = False
                agent.chatboo_dataset_cache_max_mb = 0
                agent.chatboo_query_data_ttl_hours = 0
                agent.chatboo_history_retention_days = 0
                agent.chatboo_download_max_mb = 0
                agent.chatboo_upload_max_mb = 0
                agent.chatboo_allow_remote_voices = False

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

    def _inverse_chatboo_history_retention_days(self):
        for agent in self.filtered(lambda a: a.code == CHATBOO_AGENT_CODE):
            write_product_settings(
                agent.env,
                history_retention_days=agent.chatboo_history_retention_days,
            )

    def _inverse_chatboo_download_max_mb(self):
        for agent in self.filtered(lambda a: a.code == CHATBOO_AGENT_CODE):
            write_product_settings(
                agent.env,
                download_max_mb=agent.chatboo_download_max_mb,
            )

    def _inverse_chatboo_upload_max_mb(self):
        for agent in self.filtered(lambda a: a.code == CHATBOO_AGENT_CODE):
            write_product_settings(
                agent.env,
                upload_max_mb=agent.chatboo_upload_max_mb,
            )

    def _inverse_chatboo_allow_remote_voices(self):
        for agent in self.filtered(lambda a: a.code == CHATBOO_AGENT_CODE):
            write_product_settings(
                agent.env,
                allow_remote_voices=agent.chatboo_allow_remote_voices,
            )

    def _module_factory_seed(self):
        if self.code == CHATBOO_AGENT_CODE:
            return {
                'default_context_codes': '@pns_ai_mcp\n@pns_ai_chatboo',
                'required_context_codes': 'self_chatboo\npresentation_grids\nui_focus',
                'default_skill_codes': '@pns_ai_chatboo',
                'is_agent_conversational': True,
            }
        return super()._module_factory_seed()

    @api.model
    def _host_identity_registry(self):
        reg = dict(super()._host_identity_registry())
        reg.update(chatboo_host_identity_registry())
        return reg
