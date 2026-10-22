# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Chatboo's door on the engine's activity log and change journal.

The engine lists only its own doors (MCP client, internal). Each host adds
the one it stamps on the request (``mcp_source_channel``).
"""
from odoo import fields, models

DOOR = ('chatboo', 'Chatboo')


def _keep_rows(records):
    """Old rows keep the door they came by when Chatboo is uninstalled."""


class AiLog(models.Model):
    _inherit = 'ai.log'

    origin = fields.Selection(
        selection_add=[DOOR],
        ondelete={DOOR[0]: _keep_rows},
    )


class AiChangeJournal(models.Model):
    _inherit = 'ai.change.journal'

    origin = fields.Selection(
        selection_add=[DOOR],
        ondelete={DOOR[0]: _keep_rows},
    )
