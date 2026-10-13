# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Exported files do not stay in the database (they may carry secrets)."""

import logging
from datetime import timedelta

from odoo import api, fields, models

from ..utils.portable_io import EXPORT_MARK

_logger = logging.getLogger(__name__)

RETENTION_PARAM = 'pns_base.export_retention_hours'
DEFAULT_RETENTION_HOURS = 24


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def _cron_purge_pns_exports(self):
        """Delete export files older than ``pns_base.export_retention_hours``."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            RETENTION_PARAM, DEFAULT_RETENTION_HOURS,
        )
        try:
            hours = int(raw)
        except (TypeError, ValueError):
            hours = DEFAULT_RETENTION_HOURS
        if hours <= 0:
            return 0
        edge = fields.Datetime.now() - timedelta(hours=hours)
        old = self.sudo().search([
            ('description', '=', EXPORT_MARK),
            ('create_date', '<', edge),
        ])
        count = len(old)
        if count:
            old.unlink()
            _logger.info('pns_base: deleted %d export file(s) older than %d h', count, hours)
        return count
