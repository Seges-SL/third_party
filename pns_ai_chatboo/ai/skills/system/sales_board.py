# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Sales board: movable cards in the chat.

``show_mode='dashboard'`` plus ``groups`` paints one card per group. Each
group picks its own body: ``'table'`` (plain table) or ``'show-chart'``
(chart with a data toggle); ``span: 2`` makes a wide card. A fixed
``dashboard_id`` keeps the user's layout when the figures change.
"""
from datetime import date

_today = date.today()
_y, _m = _today.year, _today.month - 11
while _m <= 0:
    _m += 12
    _y -= 1
_since = date(_y, _m, 1)
_cid = env.company.id
_cur = env.company.currency_id
_QUOTED = ('draft', 'sent')
_CONFIRMED = ('sale', 'done')


def _money(value):
    return format_amount(
        value,
        symbol=_cur.symbol or _cur.name or '',
        decimals=0,
        symbol_after=(_cur.position != 'before'),
    )


def _add(bucket, key, so, extra):
    row = bucket.get(key)
    if row is None:
        row = dict(extra)
        row.update({'Quoted': 0.0, 'Confirmed': 0.0})
        bucket[key] = row
    col = 'Confirmed' if so['state'] in _CONFIRMED else 'Quoted'
    row[col] += so['amount_untaxed'] or 0.0


def _rounded(rows):
    for row in rows:
        for key in ('Quoted', 'Confirmed', 'Sales'):
            if key in row:
                row[key] = round(row[key], 2)
    return rows


def _orders():
    return env['sale.order'].search_read(
        [
            ('state', 'in', list(_QUOTED + _CONFIRMED)),
            ('company_id', '=', _cid),
            ('date_order', '>=', '%s 00:00:00' % _since),
        ],
        ['state', 'date_order', 'amount_untaxed', 'user_id', 'partner_id'],
    )


def _quotations():
    rows = []
    for so in env['sale.order'].search_read(
        [('state', 'in', list(_QUOTED)), ('company_id', '=', _cid)],
        ['name', 'partner_id', 'date_order', 'amount_untaxed'],
        order='amount_untaxed desc',
        limit=10,
    ):
        rows.append({
            'id': so['id'],
            '__model': 'sale.order',
            'Quotation': so['name'],
            'Customer': so['partner_id'][1] if so['partner_id'] else '',
            'Date': str(so['date_order'])[:10],
            'Amount': round(so['amount_untaxed'] or 0.0, 2),
        })
    return rows


def _pipeline():
    if 'crm.lead' not in env:
        return []
    stages = {}
    for lead in env['crm.lead'].search_read(
        [('type', '=', 'opportunity'), ('company_id', 'in', [_cid, False])],
        ['stage_id', 'expected_revenue'],
    ):
        name = lead['stage_id'][1] if lead['stage_id'] else '(no stage)'
        row = stages.setdefault(name, {'Stage': name, 'Expected': 0.0, 'Opportunities': 0})
        row['Expected'] += lead['expected_revenue'] or 0.0
        row['Opportunities'] += 1
    rows = list(stages.values())
    for row in rows:
        row['Expected'] = round(row['Expected'], 2)
    return rows


if 'sale.order' not in env:
    result = {
        'formatted_text': '<p class="text-muted">Sales board needs the Sales app.</p>',
        '__return_direct__': True,
        '__stop_after_direct__': True,
        '__no_footer__': True,
    }
else:
    _by_month, _by_user, _by_customer = {}, {}, {}
    _quoted = _confirmed = 0.0
    _n_quoted = _n_confirmed = 0
    for so in _orders():
        amount = so['amount_untaxed'] or 0.0
        if so['state'] in _CONFIRMED:
            _confirmed += amount
            _n_confirmed += 1
            if so['partner_id']:
                pid = so['partner_id'][0]
                row = _by_customer.setdefault(pid, {
                    'id': pid, '__model': 'res.partner',
                    'Customer': so['partner_id'][1], 'Sales': 0.0, 'Orders': 0,
                })
                row['Sales'] += amount
                row['Orders'] += 1
        else:
            _quoted += amount
            _n_quoted += 1
        month = str(so['date_order'])[:7]
        _add(_by_month, month, so, {'Month': month})
        user = so['user_id'][1] if so['user_id'] else '(no salesperson)'
        _add(_by_user, user, so, {'Salesperson': user})

    if not (_n_quoted or _n_confirmed):
        result = {
            'formatted_text': (
                '<p class="text-muted">No quotations or sales orders since %s.</p>' % _since
            ),
            '__return_direct__': True,
            '__stop_after_direct__': True,
            '__no_footer__': True,
        }
    else:
        _months = _rounded([_by_month[k] for k in sorted(_by_month)])
        _users = _rounded(sorted(
            _by_user.values(), key=lambda r: -(r['Confirmed'] + r['Quoted']),
        ))
        _customers = _rounded(sorted(
            _by_customer.values(), key=lambda r: -r['Sales'],
        )[:10])
        groups = [
            {
                'title': 'Key figures',
                'show_mode': 'table',
                'data': [
                    {'Figure': 'Confirmed sales (untaxed)', 'Value': _money(_confirmed)},
                    {'Figure': 'Confirmed orders', 'Value': str(_n_confirmed)},
                    {'Figure': 'Quoted (untaxed)', 'Value': _money(_quoted)},
                    {'Figure': 'Quotations', 'Value': str(_n_quoted)},
                    {'Figure': 'Customers with orders', 'Value': str(len(_by_customer))},
                ],
            },
            {'title': 'Quoted and confirmed by month', 'show_mode': 'show-chart',
             'span': 2, 'data': _months},
            {'title': 'By salesperson', 'show_mode': 'show-chart', 'data': _users},
            {'title': 'Top customers', 'show_mode': 'table', 'data': _customers},
            {'title': 'Largest open quotations', 'show_mode': 'table', 'data': _quotations()},
            {'title': 'Pipeline by stage', 'show_mode': 'show-chart', 'data': _pipeline()},
        ]
        result = {
            'summary': 'Sales board since %s · confirmed %s · quoted %s (untaxed).' % (
                _since, _money(_confirmed), _money(_quoted),
            ),
            'groups': [g for g in groups if g['data']],
            'show_mode': 'dashboard',
            'dashboard_id': 'sales-board',
            'chart_engine': 'echarts',
            '__hide_columns__': ['id'],
            '__return_direct__': True,
            '__stop_after_direct__': True,
        }
