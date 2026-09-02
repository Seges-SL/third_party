# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Chatboo pick-list endpoints — before the Safe Plan Confirm aviso."""
import logging

from odoo import http
from odoo.http import request
from ..utils.compat import JSON_ROUTE_TYPE
from ..utils.field_required_plan import accept_choice, cancel_choice

_logger = logging.getLogger(__name__)


class MCPChoiceUI(http.Controller):

    @http.route('/pns_ai_mcp/choice/accept', type=JSON_ROUTE_TYPE, auth='user')
    def accept(self, choice_id=None, selected_ids=None, **kwargs):
        from .safe_plan import create_pending_safe_operation
        return accept_choice(
            request.env,
            choice_id,
            selected_ids or [],
            create_pending_safe_operation,
        )

    @http.route('/pns_ai_mcp/choice/cancel', type=JSON_ROUTE_TYPE, auth='user')
    def cancel(self, choice_id=None, **kwargs):
        return cancel_choice(request.env, choice_id)
