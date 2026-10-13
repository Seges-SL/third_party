# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Holds the raw model catalogue so the form can copy it."""

from odoo import fields, models


class AIProviderCatalogueCopy(models.TransientModel):
    _name = 'ai.provider.catalogue.copy'
    _description = 'Model catalogue copy'

    catalogue_json = fields.Text(string='Catalogue', readonly=True)
