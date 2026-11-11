# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Odoo TransactionCase suite for pns_ai_chatboo."""

from . import test_chat_agent_composition
from . import test_chatboo_perimeter
# Seges: tests de la fase 2b sobre 3.1.973 (parches 11, 15, 25, 26 y 28; esqueleto de E0′ sin parche). Ver docs/pendiente/parches_pns_ai.md
from . import test_seges_chatboo_smoke
from . import test_seges_chatboo_access
from . import test_seges_chatboo_export
from . import test_seges_chatboo_canvas
