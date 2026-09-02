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
    _name = 'pns_ai_mcp.api_key_wizard'
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
        """Determina si el usuario ya tiene una API key (por su hash)."""
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
        Genera una nueva API key después de validar la confirmación.
        """
        self.ensure_one()

        if not self.confirmed:
            raise ValidationError(_("You must confirm the action to proceed"))

        if not self.mcp_user_id:
            raise ValidationError(_("Invalid MCP User"))

        if self.is_clear:
            # Eliminar la API key (borra el hash)
            self.mcp_user_id.sudo().write({
                'mcp_api_key_hash': False,
                'mcp_api_key_state': 'not_generated',
                'mcp_api_key_generated_date': False
            })
            _logger.info("MCP: API key eliminada para usuario %s (ID: %s)",
                        self.mcp_user_id.user_id.name, self.mcp_user_id.user_id.id)
            return mcp_ui.client_notification_close(
                _('Success'),
                _('API Key eliminada correctamente'),
            )

        if self.is_import:
            # Forzar/importar una key elegida por el admin (texto plano o hash
            # de otra instancia). Se guarda solo el hash; el admin ya la conoce,
            # así que no hace falta mostrarla de nuevo.
            if not self.manual_key or not self.manual_key.strip():
                raise ValidationError(_("You must paste a valid API key in the 'Existing API Key' field"))
            self.mcp_user_id.set_mcp_api_key(self.manual_key.strip())
            return mcp_ui.client_notification_close(
                _('Success'),
                _('API Key importada correctamente'),
            )

        # Generar nueva key automáticamente. La clave en claro se muestra UNA
        # vez en este mismo wizard (patrón "cópiala ahora"): solo guardamos su
        # hash y no se puede volver a recuperar.
        raw_key = self.mcp_user_id.action_generate_mcp_api_key()
        if not raw_key:
            raise ValidationError(_("Error generando API key"))
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

