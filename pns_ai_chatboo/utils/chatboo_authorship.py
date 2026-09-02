# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
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

# Same headings as pns_ai_mcp.utils.agent_identity (idempotent prepend).
AUTHORSHIP_HEADING = '## Vendor (host, resolved)'
PRODUCT_HEADING = '## Product name (host, resolved)'

AUTHORSHIP_PROMPT_BLOCK = """%s
This knowledge layer is a product of **%s**, %s, %s —
%s
Do not invent another author.
""" % (
    AUTHORSHIP_HEADING,
    VENDOR_NAME,
    VENDOR_PLACE,
    VENDOR_YEARS,
    VENDOR_URL,
)

PRODUCT_PROMPT_BLOCK = """%s
You present yourself as **%s**. This name was resolved by the host
(owning-module constants, then identity-pack metadata, then the agent record).
""" % (PRODUCT_HEADING, PRODUCT_NAME)


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


def _prepend_host_block(agent_code, prompt, heading, block):
    text = prompt or ''
    if agent_code != CHATBOO_AGENT_CODE:
        return text
    body = block.strip()
    if heading in text:
        return text
    if not text:
        return body
    return '%s\n\n%s' % (body, text)


def apply_host_authorship(agent_code, prompt):
    """Prepend the vendor facts block for the Chatboo agent only."""
    return _prepend_host_block(
        agent_code, prompt, AUTHORSHIP_HEADING, AUTHORSHIP_PROMPT_BLOCK,
    )


def apply_host_product_name(agent_code, prompt):
    """Prepend the product-name block for the Chatboo agent only."""
    return _prepend_host_block(
        agent_code, prompt, PRODUCT_HEADING, PRODUCT_PROMPT_BLOCK,
    )


def apply_host_locks(agent_code, prompt):
    """Vendor first, then product name, then the rest of the prompt."""
    text = apply_host_product_name(agent_code, prompt)
    return apply_host_authorship(agent_code, text)
