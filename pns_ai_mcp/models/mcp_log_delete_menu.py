# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Wizard to clear the AI operation history (delete oldest, keep newest)."""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError


class MCPLogDeleteMenu(models.TransientModel):
    """Wizard to clear the AI operation history.

    Philosophy: delete the oldest logs, keep the most recent ones.
    """
    _name = 'pns_ai_mcp.log_delete_menu'
    _description = 'AI Log Delete Menu'

    delete_all = fields.Boolean(
        string='Clear all',
        default=False,
        help='When checked, all logs will be deleted. Otherwise the N most recent will be kept per the selected option.'
    )
    
    keep_recent = fields.Boolean(
        string='Keep recent',
        default=True,
        help='Keep the N most recent logs and delete the rest'
    )
    
    keep_count = fields.Selection(
        [
            ('10', '10'),
            ('100', '100'),
            ('1000', '1,000'),
            ('10000', '10,000'),
            ('100000', '100,000'),
        ],
        string='Amount to keep',
        default='1000',
        help='Number of most recent logs to keep'
    )
    
    @api.onchange('delete_all')
    def _onchange_delete_all(self):
        """Disable 'Keep recent' when 'Clear all' is selected."""
        if self.delete_all:
            self.keep_recent = False
    
    @api.onchange('keep_recent')
    def _onchange_keep_recent(self):
        """Disable 'Clear all' when 'Keep recent' is selected."""
        if self.keep_recent:
            self.delete_all = False
    
    def action_confirm(self):
        """Confirm deletion according to the selected options."""
        if not (
            self.env.user.has_group('pns_ai_mcp.group_ai_admin')
            or self.env.user.has_group('base.group_system')
        ):
            raise AccessError(_('Only MCP administrators can clear the log history.'))
        if not self.delete_all and not self.keep_recent:
            raise UserError(_('You must choose an option: "Clear all" or "Keep recent".'))
        
        if self.delete_all:
            return self.env['ai.log']._delete_oldest_logs(keep_count=None)
        keep_count = int(self.keep_count)
        return self.env['ai.log']._delete_oldest_logs(keep_count=keep_count)

