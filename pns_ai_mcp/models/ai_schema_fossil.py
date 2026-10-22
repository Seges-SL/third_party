# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Drop named leftover tables during module update (Odoo 14 leftover skip)."""
import logging

from odoo import models

from ..utils.schema_fossils import (
    FOSSIL_TABLES,
    PROTECTED_TABLES,
    drop_leftover_columns,
    promote_compose_column,
    promote_decision_provider,
    promote_engine_params,
    promote_turn_columns,
    rename_leftover_xmlids,
)

_logger = logging.getLogger(__name__)


class AiSchemaFossil(models.AbstractModel):
    _name = 'ai.schema.fossil'
    _description = 'Named leftover table drop'

    def init(self):
        cr = self.env.cr
        for table in FOSSIL_TABLES:
            if table in PROTECTED_TABLES:
                continue
            cr.execute('DROP TABLE IF EXISTS "%s" CASCADE' % table)
            _logger.info('pns_ai_mcp: DROP leftover %s', table)
        rename_leftover_xmlids(cr)
        promote_compose_column(cr)
        promote_turn_columns(cr)
        promote_decision_provider(cr)
        drop_leftover_columns(cr)
        promote_engine_params(cr)
