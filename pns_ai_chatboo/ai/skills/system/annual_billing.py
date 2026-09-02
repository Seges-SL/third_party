# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# SKILL: annual-billing — start_date/end_date/year/anio/arguments in sandbox
from datetime import date
import re

_today = date.today()
_y = _today.year

_sd = start_date
_ed = end_date
_anio = year or anio
_blob = ' '.join([str(x) for x in (arguments, lugar, fecha) if x])
_ys = [
    int(m) for m in re.findall(r'\b(19\d{2}|20\d{2})\b', _blob)
    if 1990 <= int(m) <= 2100
]
if not _anio and _ys:
    _anio = _ys[0]
if not _sd and _ys:
    _sd = '%04d-01-01' % _ys[0]
if not _ed and _ys:
    _ed = '%04d-12-31' % _ys[-1]
if not _sd and _anio:
    _sd = '%04d-01-01' % int(_anio)
if not _ed and _anio:
    _ed = '%04d-12-31' % int(_anio)
if not _sd:
    _sd = str(date(_y, 1, 1))
if not _ed:
    _ed = str(date(_y, 12, 31))

start_date = str(_sd)[:10]
end_date = str(_ed)[:10]

domain = [
    ('move_type', '=', 'out_invoice'),
    ('state', '=', 'posted'),
    ('invoice_date', '>=', start_date),
    ('invoice_date', '<=', end_date),
]
invoices = env['account.move'].search(domain)

by_week = {}
for inv in invoices:
    if inv.invoice_date:
        iso = inv.invoice_date.isocalendar()
        week_key = '%s-W%02d' % (iso[0], iso[1])
        month = inv.invoice_date.month
        if week_key not in by_week:
            by_week[week_key] = {'amount': 0.0, 'month': month}
        by_week[week_key]['amount'] += inv.amount_untaxed

rows = sorted(
    [
        {'week': k, 'amount': v['amount'], 'month': v['month']}
        for k, v in by_week.items()
    ],
    key=lambda x: x['week'],
)

if not rows:
    result = {
        'formatted_text': (
            '<p class="text-muted">No invoices in the period '
            '%s — %s.</p>' % (start_date, end_date)
        ),
        '__return_direct__': True,
        '__stop_after_direct__': True,
        '__no_footer__': True,
    }
else:
    max_val = max(r['amount'] for r in rows) or 1.0
    bar_max = 35
    BLOCK = '█'

    month_colors = {
        1: {'bg': '#fff0f0', 'bar': '#e57373', 'label': 'January'},
        2: {'bg': '#fff4e6', 'bar': '#ff9800', 'label': 'February'},
        3: {'bg': '#fffde7', 'bar': '#f9c74f', 'label': 'March'},
        4: {'bg': '#f1f8e9', 'bar': '#8bc34a', 'label': 'April'},
        5: {'bg': '#e8f5e9', 'bar': '#43a047', 'label': 'May'},
        6: {'bg': '#e0f7fa', 'bar': '#00acc1', 'label': 'June'},
        7: {'bg': '#e3f2fd', 'bar': '#1e88e5', 'label': 'July'},
        8: {'bg': '#ede7f6', 'bar': '#7e57c2', 'label': 'August'},
        9: {'bg': '#fce4ec', 'bar': '#e91e63', 'label': 'September'},
        10: {'bg': '#fff8e1', 'bar': '#fb8c00', 'label': 'October'},
        11: {'bg': '#f3e5f5', 'bar': '#ab47bc', 'label': 'November'},
        12: {'bg': '#e8eaf6', 'bar': '#3949ab', 'label': 'December'},
    }

    total = sum(r['amount'] for r in rows)

    html = (
        "<div style='font-family:monospace;font-size:13px;"
        "max-width:100%;overflow-x:auto;'>"
    )
    html += (
        "<div style='margin-bottom:8px;font-weight:bold;font-size:14px;'>"
        "Billing %s — %s</div>" % (start_date, end_date)
    )

    html += (
        "<div style='margin-bottom:10px;display:flex;"
        "flex-wrap:wrap;gap:6px;'>"
    )
    months_used = sorted(set(r['month'] for r in rows))
    for m in months_used:
        c = month_colors[m]
        html += (
            "<span style='background:%s;border:1px solid %s;border-radius:4px;"
            "padding:2px 8px;font-size:11px;color:%s;font-weight:bold;'>%s</span>"
            % (c['bg'], c['bar'], c['bar'], c['label'])
        )
    html += '</div>'

    html += "<table style='border-collapse:collapse;width:100%;'>"
    html += '<thead><tr>'
    html += (
        "<th style='text-align:left;padding:3px 10px;"
        "border-bottom:2px solid #ccc;'>Month</th>"
    )
    html += (
        "<th style='text-align:left;padding:3px 10px;"
        "border-bottom:2px solid #ccc;'>Week</th>"
    )
    html += (
        "<th style='text-align:right;padding:3px 10px;"
        "border-bottom:2px solid #ccc;'>Amount</th>"
    )
    html += (
        "<th style='text-align:left;padding:3px 10px;"
        "border-bottom:2px solid #ccc;'>Chart</th>"
    )
    html += '</tr></thead><tbody>'

    prev_month = None
    for r in rows:
        m = r['month']
        c = month_colors[m]
        bars = max(1, int(r['amount'] / max_val * bar_max))
        bar = "<span style='color:%s'>%s</span>" % (c['bar'], BLOCK * bars)
        amount_fmt = format_amount(r['amount'], decimals=0)

        if m != prev_month:
            mes_label = "<strong style='color:%s'>%s</strong>" % (
                c['bar'], c['label'],
            )
            prev_month = m
        else:
            mes_label = ''

        html += "<tr style='background:%s;'>" % c['bg']
        html += (
            "<td style='padding:2px 10px;white-space:nowrap;'>%s</td>"
            % mes_label
        )
        html += "<td style='padding:2px 10px;'>%s</td>" % r['week']
        html += (
            "<td style='text-align:right;padding:2px 10px;'>%s</td>"
            % amount_fmt
        )
        html += "<td style='padding:2px 10px;'>%s</td>" % bar
        html += '</tr>'

    total_fmt = format_amount(total, decimals=0)
    html += (
        "<tr style='font-weight:bold;border-top:2px solid #999;"
        "background:#f5f5f5;'>"
    )
    html += "<td colspan='2' style='padding:4px 10px;'>TOTAL</td>"
    html += (
        "<td style='text-align:right;padding:4px 10px;'>%s</td>" % total_fmt
    )
    html += '<td></td></tr>'
    html += '</tbody></table>'
    html += '</div>'

    result = {
        'formatted_text': html,
        '__return_direct__': True,
        '__stop_after_direct__': True,
        '__no_footer__': True,
        'start_date': start_date,
        'end_date': end_date,
    }
