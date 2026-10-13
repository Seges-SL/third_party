# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.517: drop leftover TransientModel after stem rename to safe.tools.wizard."""
import logging

_logger = logging.getLogger(__name__)

_MODELS = (
    'pns_ai_mcp.safe.operation.tools.wizard',
)


def migrate(cr, version):
    try:
        from odoo import api, SUPERUSER_ID
        env = api.Environment(cr, SUPERUSER_ID, {})
    except Exception:
        _logger.exception('3.1.517 safe tools wizard leftover: cannot build env')
        return

    IrModel = env['ir.model'].sudo()
    for name in _MODELS:
        try:
            model = IrModel.search([('model', '=', name)], limit=1)
            if model:
                model.unlink()
        except Exception:
            _logger.info('3.1.517: skip model %s', name, exc_info=True)
