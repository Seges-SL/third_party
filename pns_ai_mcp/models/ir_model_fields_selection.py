# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Odoo 14 backport: skip selection ondelete when the model left the registry.

Upstream (15+) uses ``env.get`` instead of ``env[]`` in
``ir.model.fields.selection._process_ondelete``. Without it, module upgrades
that rename/remove a model with Selection fields crash in ``_process_end``:

    KeyError: 'ai.geo.distance.cache'
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class IrModelFieldsSelection(models.Model):
    _inherit = 'ir.model.fields.selection'

    def _process_ondelete(self):
        # Upstream Odoo 15+ fix (PR #184764): model may already be absent after
        # a rename/removal; skipping is safe — table/rows are migrated or dropped.
        missing = self.browse()
        for selection in self:
            model_name = selection.field_id.model
            if model_name and model_name not in self.env:
                _logger.info(
                    "Skip selection ondelete for missing model %r",
                    model_name,
                )
                missing |= selection
        remaining = self - missing
        if remaining:
            return super(IrModelFieldsSelection, remaining)._process_ondelete()

    def _get_records(self):
        self.ensure_one()
        if self.field_id.model not in self.env:
            return self.env['ir.model'].browse()
        return super()._get_records()
