# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from odoo import models


class JsonExportWizard(models.TransientModel):
    _name = 'pns_ai_mcp.json_export_wizard'
    _inherit = 'pns.export.file.wizard'
    _description = 'JSON export result wizard'
