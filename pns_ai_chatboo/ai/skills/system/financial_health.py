# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Financial health: the code computes the figures, the model writes the report.

Sales and purchases against the same span a year earlier, money owed both
ways, cash in the bank and cash journals, days to collect and how much the
top customers weigh. Any chart of accounts: it reads invoices and journal
types, never account codes.
"""
from datetime import date, timedelta

try:
    _months = int(months)
except (NameError, TypeError, ValueError):
    _months = 12
_months = max(1, min(60, _months))

_today = date.today()
_y, _m = _today.year, _today.month - (_months - 1)
while _m <= 0:
    _m += 12
    _y -= 1
_start = date(_y, _m, 1)
_prior_start = date(_start.year - 1, _start.month, 1)
_prior_end = _today - timedelta(days=365)
_cid = env.company.id
_label = 'last %d months' % _months


def _moves(types, date_from, date_to):
    return env['account.move'].search([
        ('move_type', 'in', types),
        ('state', '=', 'posted'),
        ('invoice_date', '>=', str(date_from)),
        ('invoice_date', '<=', str(date_to)),
        ('company_id', '=', _cid),
    ])


def _net(moves):
    """Untaxed total; refunds count negative."""
    return sum(
        (-1 if mv.move_type in ('out_refund', 'in_refund') else 1) * mv.amount_untaxed
        for mv in moves
    )


def _open(types):
    return env['account.move'].search([
        ('move_type', 'in', types),
        ('state', '=', 'posted'),
        ('payment_state', 'in', ['not_paid', 'partial']),
        ('company_id', '=', _cid),
    ])


def _owed(moves):
    total = overdue = 0.0
    for mv in moves:
        left = abs(mv.amount_residual) * (-1 if mv.move_type in ('out_refund', 'in_refund') else 1)
        total += left
        if (mv.invoice_date_due or mv.invoice_date or _today) < _today:
            overdue += left
    return round(total, 2), round(overdue, 2)


def _pct(part, whole):
    return round(part * 100.0 / whole, 1) if whole else 0.0


if 'account.move' not in env:
    result = {
        'formatted_text': '<p class="text-muted">Financial health needs the Invoicing app.</p>',
        '__return_direct__': True,
        '__stop_after_direct__': True,
        '__no_footer__': True,
    }
else:
    _sales_moves = _moves(['out_invoice', 'out_refund'], _start, _today)
    _sales = _net(_sales_moves)
    _sales_prior = _net(_moves(['out_invoice', 'out_refund'], _prior_start, _prior_end))
    _buys = _net(_moves(['in_invoice', 'in_refund'], _start, _today))
    _buys_prior = _net(_moves(['in_invoice', 'in_refund'], _prior_start, _prior_end))

    _ar_moves = _open(['out_invoice', 'out_refund'])
    _ar, _ar_overdue = _owed(_ar_moves)
    _ap, _ap_overdue = _owed(_open(['in_invoice', 'in_refund']))

    _cash_accounts = env['account.journal'].search([
        ('type', 'in', ['bank', 'cash']), ('company_id', '=', _cid),
    ]).mapped('default_account_id')
    _cash = round(sum(env['account.move.line'].search([
        ('account_id', 'in', _cash_accounts.ids),
        ('move_id.state', '=', 'posted'),
        ('date', '<=', str(_today)),
    ]).mapped('balance')), 2)

    _days = max(1, (_today - _start).days + 1)
    _sales_taxed = sum(
        (-1 if mv.move_type == 'out_refund' else 1) * mv.amount_total for mv in _sales_moves
    )
    _dso = round(_ar * _days / _sales_taxed) if _sales_taxed > 0 else 0

    _by_customer = {}
    for _mv in _sales_moves:
        _p = _mv.partner_id.commercial_partner_id
        _row = _by_customer.setdefault(_p.id, {
            'id': _p.id, '__model': 'res.partner', 'Customer': _p.name or '',
            'Sales': 0.0, 'Share %': 0.0,
        })
        _row['Sales'] += (-1 if _mv.move_type == 'out_refund' else 1) * _mv.amount_untaxed
    _top = sorted(_by_customer.values(), key=lambda r: -r['Sales'])[:10]
    for _row in _top:
        _row['Sales'] = round(_row['Sales'], 2)
        _row['Share %'] = _pct(_row['Sales'], _sales)
    _top3 = _pct(sum(r['Sales'] for r in _top[:3]), _sales)

    _late = {}
    for _mv in _ar_moves:
        if _mv.move_type != 'out_invoice' or (_mv.invoice_date_due or _today) >= _today:
            continue
        _p = _mv.partner_id.commercial_partner_id
        _row = _late.setdefault(_p.id, {
            'id': _p.id, '__model': 'res.partner', 'Customer': _p.name or '',
            'Overdue': 0.0, 'Invoices': 0, 'Oldest due': _mv.invoice_date_due,
        })
        _row['Overdue'] += abs(_mv.amount_residual)
        _row['Invoices'] += 1
        _row['Oldest due'] = min(_row['Oldest due'], _mv.invoice_date_due)
    _late_rows = sorted(_late.values(), key=lambda r: -r['Overdue'])[:10]
    for _row in _late_rows:
        _row['Overdue'] = round(_row['Overdue'], 2)
        _row['Oldest due'] = str(_row['Oldest due'])

    _kpis = [
        {'Metric': 'Sales, untaxed', 'Value': round(_sales, 2)},
        {'Metric': 'Sales, same span a year earlier', 'Value': round(_sales_prior, 2)},
        {'Metric': 'Sales change %', 'Value': _pct(_sales - _sales_prior, _sales_prior)},
        {'Metric': 'Purchases, untaxed', 'Value': round(_buys, 2)},
        {'Metric': 'Purchases, same span a year earlier', 'Value': round(_buys_prior, 2)},
        {'Metric': 'Sales minus purchases', 'Value': round(_sales - _buys, 2)},
        {'Metric': 'Cash in bank and cash journals', 'Value': _cash},
        {'Metric': 'Customers owe', 'Value': _ar},
        {'Metric': 'Customers owe, overdue', 'Value': _ar_overdue},
        {'Metric': 'We owe suppliers', 'Value': _ap},
        {'Metric': 'We owe suppliers, overdue', 'Value': _ap_overdue},
        {'Metric': 'Days to collect (DSO)', 'Value': _dso},
        {'Metric': 'Top 3 customers, share of sales %', 'Value': _top3},
    ]
    _tables = [{'title': 'Key figures · %s (%s to %s)' % (_label, _start, _today), 'data': _kpis}]
    if _top:
        _tables.append({'title': 'Top customers · %s' % _label, 'data': _top})
    if _late_rows:
        _tables.append({'title': 'Customers with overdue invoices', 'data': _late_rows})

    _actions = []
    if _ar_overdue > 0:
        _actions.append('collect %s overdue from customers' % format_amount(_ar_overdue, decimals=0))
    if _ap_overdue > 0:
        _actions.append('settle %s overdue to suppliers' % format_amount(_ap_overdue, decimals=0))
    if _ap > _cash + _ar:
        _actions.append('cover payables above cash plus receivables')
    if _top3 >= 50:
        _actions.append('widen the customer base: the top 3 bring %s%% of sales' % _top3)

    result = {
        'tables': _tables,
        'title': 'Financial health · %s' % _label,
        'summary': 'Financial health · %s' % _label,
        'company': env.company.name,
        'footer': 'Invoices posted from %s to %s; balances as of %s.' % (_start, _today, _today),
        'report_outline': [
            '## Analysis',
            '### Strengths',
            '### Weaknesses and risks',
            '### Liquidity',
            '## Conclusion',
            '## Recommendations',
        ],
        'recommendations_stub': [a[0].upper() + a[1:] + '.' for a in _actions]
        or ['Keep monitoring sales, collections and cash.'],
        'closing_required': 'Recommended action line: %s.' % (
            '; '.join(_actions) if _actions else 'no urgent action; keep monitoring'
        ),
        '__no_charts__': True,
        '__subtle_zebra__': True,
        '__return_direct__': True,
        '__stop_after_direct__': True,
    }
