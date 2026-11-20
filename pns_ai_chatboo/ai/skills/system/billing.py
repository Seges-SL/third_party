# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Posted customer invoices by month, drawn as a chart: last N months or one year."""
from datetime import date

try:
    _months = int(months)
except (NameError, TypeError, ValueError):
    _months = 12
_months = max(1, min(60, _months))
try:
    _year = int(year)
except (NameError, TypeError, ValueError):
    _year = None

_today = date.today()
if _year:
    _start = date(_year, 1, 1)
    _end = min(date(_year, 12, 31), _today)
    _label = str(_year)
else:
    _y, _m = _today.year, _today.month - (_months - 1)
    while _m <= 0:
        _m += 12
        _y -= 1
    _start = date(_y, _m, 1)
    _end = _today
    _label = 'last %d months' % _months

if 'account.move' not in env:
    result = {
        'formatted_text': '<p class="text-muted">Billing needs the Invoicing app.</p>',
        '__return_direct__': True,
        '__stop_after_direct__': True,
        '__no_footer__': True,
    }
else:
    _by_month = {}
    _invoices = env['account.move'].search([
        ('move_type', '=', 'out_invoice'),
        ('state', '=', 'posted'),
        ('invoice_date', '>=', str(_start)),
        ('invoice_date', '<=', str(_end)),
        ('company_id', '=', env.company.id),
    ])
    for _inv in _invoices:
        _slot = _by_month.setdefault(
            _inv.invoice_date.strftime('%Y-%m'), {'Amount': 0.0, 'Invoices': 0},
        )
        _slot['Amount'] += _inv.amount_untaxed
        _slot['Invoices'] += 1
    rows = [
        {'Month': key, 'Amount': round(val['Amount'], 2), 'Invoices': val['Invoices']}
        for key, val in sorted(_by_month.items())
    ]
    if rows:
        result = {
            'data': rows,
            'summary': 'Billing · %s (%s to %s) · %s untaxed, %d invoices.' % (
                _label, _start, _end,
                format_amount(sum(r['Amount'] for r in rows), decimals=0),
                len(_invoices),
            ),
            'show_mode': 'show-chart',
            'chart_engine': 'echarts',
            '__return_direct__': True,
            '__stop_after_direct__': True,
        }
    else:
        result = {
            'formatted_text': (
                '<p class="text-muted">No posted customer invoices from %s to %s.</p>'
                % (_start, _end)
            ),
            '__return_direct__': True,
            '__stop_after_direct__': True,
            '__no_footer__': True,
        }
