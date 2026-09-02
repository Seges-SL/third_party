# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Mixin placeholder for JSON export/import tool wizards (help text lives in XML views)."""

from odoo import models


class PnsExportImportToolsWizardMixin(models.AbstractModel):
    _name = 'pns.export_import.tools.wizard.mixin'
    _description = 'Mixin for JSON export/import tool wizards'
