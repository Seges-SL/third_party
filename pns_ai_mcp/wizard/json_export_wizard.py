# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""JSON export result wizard."""

from odoo import models


class JsonExportWizard(models.TransientModel):
    _name = 'ai.json.export.wizard'
    _inherit = 'pns.export.file.wizard'
    _description = 'JSON export result wizard'
