# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Odoo TransactionCase suite for pns_ai_chatboo."""

from . import test_chat_agent_composition
from . import test_chatboo_perimeter
# Seges: tests de la fase 2 en la 17, tanda T0 (esqueleto de E0′ y no regresión del
# parche 23, retirado). Ver docs/pendiente/parches_pns_ai.md
from . import test_seges_chatboo_smoke
from . import test_seges_skill_env
