# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Chatboo host identity constants. Not ai.context — source only.

Greeting / off-topic voice lives in the ``self_chatboo`` pack. This module
only registers the two locked facts (product name + vendor) for
``pns_ai_chatboo``. The engine cascade injects one resolved block; it does
not list other agents' brands.
"""
try:
    from .chatboo_product_icp import CHATBOO_AGENT_CODE
except ImportError:  # unit tests load this file outside the Odoo package
    CHATBOO_AGENT_CODE = 'pns_ai_chatboo'

VENDOR_NAME = 'PATANEGRA Soft'
VENDOR_PLACE = 'Seville (Spain)'
VENDOR_YEARS = '1996–2026'
VENDOR_URL = 'https://www.patanegra.com'
PRODUCT_NAME = 'Chatboo'


def chatboo_host_identity_registry():
    """``agent.code`` → constants for the Chatboo inference agent."""
    return {
        CHATBOO_AGENT_CODE: {
            'product_name': PRODUCT_NAME,
            'vendor': VENDOR_NAME,
            'vendor_place': VENDOR_PLACE,
            'vendor_years': VENDOR_YEARS,
            'vendor_url': VENDOR_URL,
        },
    }
