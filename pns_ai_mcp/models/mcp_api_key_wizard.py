# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Wizard that generates MCP API keys."""

import logging
from odoo import api, fields, models
from odoo import _
from odoo.exceptions import ValidationError

from ..utils import mcp_ui

_logger = logging.getLogger(__name__)


class MCPApiKeyWizard(models.TransientModel):
    _name = 'ai.api.key.wizard'
    _description = 'MCP API Key Regeneration Wizard'

    mcp_user_id = fields.Many2one(
        'ai.mcp.user',
        string='MCP User',
        required=True,
        readonly=True
    )

    has_api_key = fields.Boolean(
        string='Has API Key',
        compute='_compute_has_api_key',
        help='Technical field to check whether the user already has an API key'
    )

    generated_key = fields.Char(
        string='API Key',
        readonly=True,
        help='Freshly generated key, shown only once. Copy it now: it is not '
             'stored in plain text and cannot be shown again.'
    )

    @api.depends('mcp_user_id', 'mcp_user_id.mcp_api_key_hash')
    def _compute_has_api_key(self):
        """Tell whether the user already has an API key (by its hash)."""
        for record in self:
            if record.mcp_user_id:
                record.has_api_key = bool(record.mcp_user_id.mcp_api_key_hash)
            else:
                record.has_api_key = False

    is_clear = fields.Boolean(
        string='Is deletion',
        default=False,
        help='Indicates whether the API key is being deleted instead of generated'
    )

    is_import = fields.Boolean(
        string='Is import',
        default=False,
        help='Indicates whether an existing key is being imported instead of generating a new one'
    )

    manual_key = fields.Char(
        string='Existing API Key',
        help='Paste an API key from another instance here to reuse it'
    )

    confirmed = fields.Boolean(
        string='Confirmed',
        default=False,
        help='The user must explicitly confirm to proceed'
    )

    def action_generate(self):
        """
        Generate a new API key after checking the confirmation.
        """
        self.ensure_one()

        if not self.confirmed:
            raise ValidationError(_("You must confirm the action to proceed"))

        if not self.mcp_user_id:
            raise ValidationError(_("Invalid MCP User"))

        if self.is_clear:
            # Remove the API key (clears the hash)
            self.mcp_user_id.sudo().write({
                'mcp_api_key_hash': False,
                'mcp_api_key_state': 'not_generated',
                'mcp_api_key_generated_date': False
            })
            _logger.info("MCP: API key deleted for user %s (ID: %s)",
                        self.mcp_user_id.user_id.name, self.mcp_user_id.user_id.id)
            return mcp_ui.client_notification_close(
                _('Success'),
                _('API Key deleted successfully'),
            )

        if self.is_import:
            # Force/import a key chosen by the admin (plain text or a hash
            # from another instance). Only the hash is stored; the admin already
            # knows it, so there is no need to show it again.
            if not self.manual_key or not self.manual_key.strip():
                raise ValidationError(_("You must paste a valid API key in the 'Existing API Key' field"))
            self.mcp_user_id.set_mcp_api_key(self.manual_key.strip())
            return mcp_ui.client_notification_close(
                _('Success'),
                _('API Key imported successfully'),
            )

        # Generate a new key automatically. The plain key is shown ONCE
        # in this same wizard ("copy it now" pattern): we only store its
        # hash and it cannot be recovered again.
        raw_key = self.mcp_user_id.action_generate_mcp_api_key()
        if not raw_key:
            raise ValidationError(_("Error generating API key"))
        self.write({'generated_key': raw_key, 'confirmed': False})
        return {
            'type': 'ir.actions.act_window',
            'name': _('API Key generated'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context, mcp_show_generated_key=True),
        }

