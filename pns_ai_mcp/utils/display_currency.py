# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ISO display currencies for AI Engine cost labels (no res.currency)."""
from __future__ import annotations

ICP_DISPLAY_CURRENCY = 'pns_ai_mcp.display_currency'

# ~50 widely used ISO 4217 codes. Vendor cost stays USD; this is presentation.
CURRENCY_SELECTION = [
    ('USD', 'USD — US Dollar'),
    ('EUR', 'EUR — Euro'),
    ('GBP', 'GBP — Pound Sterling'),
    ('JPY', 'JPY — Japanese Yen'),
    ('CHF', 'CHF — Swiss Franc'),
    ('CAD', 'CAD — Canadian Dollar'),
    ('AUD', 'AUD — Australian Dollar'),
    ('NZD', 'NZD — New Zealand Dollar'),
    ('CNY', 'CNY — Chinese Yuan'),
    ('HKD', 'HKD — Hong Kong Dollar'),
    ('SGD', 'SGD — Singapore Dollar'),
    ('KRW', 'KRW — South Korean Won'),
    ('TWD', 'TWD — New Taiwan Dollar'),
    ('INR', 'INR — Indian Rupee'),
    ('IDR', 'IDR — Indonesian Rupiah'),
    ('MYR', 'MYR — Malaysian Ringgit'),
    ('THB', 'THB — Thai Baht'),
    ('PHP', 'PHP — Philippine Peso'),
    ('VND', 'VND — Vietnamese Dong'),
    ('PKR', 'PKR — Pakistani Rupee'),
    ('MXN', 'MXN — Mexican Peso'),
    ('BRL', 'BRL — Brazilian Real'),
    ('ARS', 'ARS — Argentine Peso'),
    ('CLP', 'CLP — Chilean Peso'),
    ('COP', 'COP — Colombian Peso'),
    ('PEN', 'PEN — Peruvian Sol'),
    ('UYU', 'UYU — Uruguayan Peso'),
    ('CRC', 'CRC — Costa Rican Colón'),
    ('ZAR', 'ZAR — South African Rand'),
    ('NGN', 'NGN — Nigerian Naira'),
    ('EGP', 'EGP — Egyptian Pound'),
    ('KES', 'KES — Kenyan Shilling'),
    ('MAD', 'MAD — Moroccan Dirham'),
    ('AED', 'AED — UAE Dirham'),
    ('SAR', 'SAR — Saudi Riyal'),
    ('QAR', 'QAR — Qatari Riyal'),
    ('KWD', 'KWD — Kuwaiti Dinar'),
    ('BHD', 'BHD — Bahraini Dinar'),
    ('ILS', 'ILS — Israeli Shekel'),
    ('TRY', 'TRY — Turkish Lira'),
    ('SEK', 'SEK — Swedish Krona'),
    ('NOK', 'NOK — Norwegian Krone'),
    ('DKK', 'DKK — Danish Krone'),
    ('PLN', 'PLN — Polish Zloty'),
    ('CZK', 'CZK — Czech Koruna'),
    ('HUF', 'HUF — Hungarian Forint'),
    ('RON', 'RON — Romanian Leu'),
    ('BGN', 'BGN — Bulgarian Lev'),
    ('RUB', 'RUB — Russian Ruble'),
    ('UAH', 'UAH — Ukrainian Hryvnia'),
]


def currency_codes():
    return [row[0] for row in CURRENCY_SELECTION]


def normalize_currency(code):
    """Return a known ISO code or USD."""
    raw = (code or '').strip().upper()
    if raw in currency_codes():
        return raw
    return 'USD'


def get_display_currency(env):
    """Global Chatboo cost-chip currency from AI Engine settings."""
    try:
        raw = env['ir.config_parameter'].sudo().get_param(
            ICP_DISPLAY_CURRENCY, 'USD',
        )
    except Exception:
        return 'USD'
    return normalize_currency(raw)
