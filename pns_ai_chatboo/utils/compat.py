# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Compatibility facade for pns_ai_chatboo.

Generic multi-version helpers live once in pns_base
(odoo.addons.pns_base.utils.compat) and are re-exported here to avoid
duplication. Module-specific utilities (if any) would be defined locally here.
"""

from odoo.addons.pns_base.utils.compat import (  # noqa: F401
    ODOO_VERSION,
    JSON_ROUTE_TYPE,
    USER_GROUPS_FIELD,
    USER_ALL_GROUPS_FIELD,
    invalidate_recordset_fields,
    user_has_group,
    user_has_group_direct,
)
