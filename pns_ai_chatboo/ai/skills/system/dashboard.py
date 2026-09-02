# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# SKILL: dashboard — 9 chart cards (3 periods × team / top / trend)
from datetime import date
import calendar

_today = date.today()
_y, _m = _today.year, _today.month
_month_start = date(_y, _m, 1)
_month_end = date(_y, _m, calendar.monthrange(_y, _m)[1])
_q = (_m - 1) // 3 + 1
_q_start_m = 3 * (_q - 1) + 1
_quarter_start = date(_y, _q_start_m, 1)
_year_start = date(_y, 1, 1)

def _add(bucket, key, revenue, count=1):
    row = bucket.get(key)
    if row is None:
        bucket[key] = {'Revenue': 0.0, 'Invoices': 0}
        row = bucket[key]
    row['Revenue'] += revenue
    row['Invoices'] += count


def _chart_rows(bucket, label_key, limit=None, sort='revenue'):
    if sort == 'label':
        items = sorted(bucket.items(), key=lambda kv: kv[0])
    else:
        items = sorted(bucket.items(), key=lambda kv: -kv[1]['Revenue'])
    if limit:
        items = items[:limit]
    rows = [
        {
            label_key: name,
            'Revenue': round(vals['Revenue'], 2),
            'Invoices': vals['Invoices'],
        }
        for name, vals in items
    ]
    return rows or [
        {label_key: '—', 'Revenue': 0.0, 'Invoices': 0},
    ]


def _period_groups(start, end, title, grain, has_team):
    moves = env['account.move'].search([
        ('move_type', '=', 'out_invoice'),
        ('state', '=', 'posted'),
        ('invoice_date', '>=', str(start)),
        ('invoice_date', '<=', str(end)),
    ])
    by_team = {}
    by_partner = {}
    by_period = {}
    total = 0.0
    for m in moves:
        amt = m.amount_untaxed or 0.0
        total += amt
        if has_team and m.team_id:
            team = m.team_id.name
        elif has_team:
            team = '(no team)'
        else:
            team = m.journal_id.name if m.journal_id else '(no journal)'
        _add(by_team, team, amt)
        partner = m.partner_id.name if m.partner_id else '(no partner)'
        _add(by_partner, partner, amt)
        d = m.invoice_date
        if grain == 'day':
            key = d.strftime('%Y-%m-%d') if d else '—'
        else:
            key = d.strftime('%Y-%m') if d else '—'
        _add(by_period, key, amt)

    dim = 'Team' if has_team else 'Journal'
    return [
        {
            'title': '%s — %s' % (dim, title),
            'data': _chart_rows(by_team, dim),
            'show_mode': 'show-chart',
        },
        {
            'title': 'Top customers — %s' % title,
            'data': _chart_rows(by_partner, 'Customer', limit=10),
            'show_mode': 'show-chart',
        },
        {
            'title': 'Trend — %s' % title,
            'data': _chart_rows(by_period, 'Period', sort='label') if by_period else [
                {'Period': '—', 'Revenue': 0.0, 'Invoices': 0},
            ],
            'show_mode': 'show-chart',
        },
    ], total, len(moves)


if 'account.move' not in env:
    result = {
        'formatted_text': (
            '<p class="text-muted">Dashboard requires Accounting '
            '(account.move).</p>'
        ),
        '__return_direct__': True,
        '__stop_after_direct__': True,
        '__no_footer__': True,
    }
else:
    specs = [
        (_month_start, min(_today, _month_end),
         'Month %04d-%02d' % (_y, _m), 'day'),
        (_quarter_start, _today,
         'Quarter Q%s %s' % (_q, _y), 'month'),
        (_year_start, _today,
         'YTD %s' % _y, 'month'),
    ]
    has_team = 'team_id' in env['account.move'].fields_get()
    groups = []
    totals = []
    for start, end, title, grain in specs:
        cards, total, _n = _period_groups(start, end, title, grain, has_team)
        groups.extend(cards)
        totals.append(total)
    result = {
        'summary': (
            'Dashboard · month %s · quarter %s · YTD %s '
            '(posted customer invoices, untaxed).'
            % (
                format_amount(totals[0], decimals=0),
                format_amount(totals[1], decimals=0),
                format_amount(totals[2], decimals=0),
            )
        ),
        'groups': groups,
        'show_mode': 'dashboard',
        'chart_engine': 'echarts',
        '__return_direct__': True,
        '__stop_after_direct__': True,
    }
