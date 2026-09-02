# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""PNS AI MCP - External API Server Key. PATANEGRA Soft (https://patanegra.com).

Part of Patanegra Soft Suite (`pns_suite`), distributed via Patanegra Soft Hub.
OUTBOUND per-user credentials for external API servers (``ai.api.server``):
when the AI executes an api_call on behalf of a user, the call authenticates
with that user's key; without one, the server's default auth token applies.

NOT to be confused with the other two credential classes of the suite:
  - ``ai.mcp.user.mcp_api_key_hash``: INBOUND key of external MCP clients
    (Cursor, Claude…) against the /mcp endpoint. One per user, hashed.
  - ``ai.provider.api_key``: credential Odoo uses against LLM gateways.

Here we are the CLIENT of the remote API (not the verifier), so the token is
stored as-is — same policy as ``ai.provider.api_key`` and the server's own
``auth_token``. Visibility is restricted by record rules: each user manages
their own keys; AI Administrators see all.
Licensed under the Apache License 2.0 - see LICENSE.
"""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ExternalAPIServerKey(models.Model):
    """One outbound credential of one Odoo user for one external API server."""
    _name = 'ai.api.server.key'
    _description = 'External API Server Key'
    _order = 'server_id, user_id'
    _rec_name = 'user_id'

    server_id = fields.Many2one(
        'ai.api.server',
        string='Server',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        default=lambda self: self.env.uid,
        ondelete='cascade',
        index=True,
        help='Odoo user whose api_call executions authenticate with this key.',
    )
    token = fields.Char(
        string='Token',
        required=True,
        help='API key / bearer token sent to the external server. The header '
             "placement follows the server's Auth Type.",
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="Inactive keys are ignored; the server's default token applies.",
    )
    notes = fields.Char(string='Notes')

    _sql_constraints = [
        ('server_user_unique', 'UNIQUE(server_id, user_id)',
         'This user already has a key for this server.'),
    ]
