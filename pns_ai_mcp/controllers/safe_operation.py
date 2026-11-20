# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Functions for verifying dangerous write operations."""

import logging
from odoo import SUPERUSER_ID
from odoo.http import request
from datetime import timedelta
from odoo import fields

_logger = logging.getLogger(__name__)

def cancel_pending_verifications_for_user(user_id, reason="missing permissions"):
    """
    Automatically cancel every pending verification of a user
    within the cancellation window (CANCELATION_PERIOD_SECONDS).
    
    :param user_id: User ID
    :param reason: Cancellation reason (for logging)
    """
    try:
        env_su = request.env(user=SUPERUSER_ID)
        verification_model = env_su['ai.safe.operation']
        from odoo.addons.pns_ai_mcp.constants import PENDING_OPERATION_TTL_MINUTES
        
        time_limit = fields.Datetime.now() - timedelta(minutes=PENDING_OPERATION_TTL_MINUTES)
        pending_verifications = verification_model.search([
            ('user_id', '=', user_id),
            ('status', '=', 'pending'),
            ('create_date', '>=', time_limit),
        ])
        
        if pending_verifications:
            now = fields.Datetime.now()
            pending_verifications.sudo().write({
                'status': 'cancelled',
                'resolved_at': now
            })
            _logger.info(f"MCP: Automatically cancelled {len(pending_verifications)} pending verification(s) due to {reason}")
            return len(pending_verifications)
    except Exception as e:
        _logger.warning(f"MCP: Error cancelling pending verifications: {e}")
    return 0

