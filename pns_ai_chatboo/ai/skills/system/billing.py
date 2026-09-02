# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# SKILL: billing — period totals from posted out_invoice (no BA / local catalogs)
from datetime import date
import re

result = {}
_today = date.today()

try:
    _arguments = arguments
except NameError:
    _arguments = None
try:
    _periodo = periodo
except NameError:
    _periodo = None
try:
    _lugar = lugar
except NameError:
    _lugar = None
try:
    _fecha = fecha
except NameError:
    _fecha = None

_parts = []
for _x in (_arguments, _periodo, _lugar, _fecha):
    if _x is None:
        continue
    if isinstance(_x, dict):
        for _v in _x.values():
            if _v is not None and str(_v).strip() and str(_v).strip().lower() not in ('none', 'null'):
                _parts.append(str(_v).strip())
    elif isinstance(_x, (list, tuple)):
        for _v in _x:
            if _v is not None and str(_v).strip():
                _parts.append(str(_v).strip())
    else:
        _s = str(_x).strip()
        if _s and _s.lower() not in ('none', 'null'):
            _parts.append(_s)
_blob = ' '.join(_parts).strip()
_blob_l = _blob.lower()

_help_words = (
    '?', 'help', 'ayuda', 'options', 'opciones', 'params', 'usage', 'uso',
    '/?', '/help', '/ayuda',
)
_is_help = False
if _blob_l in _help_words:
    _is_help = True
elif _blob_l and re.match(r'^[?]+$', _blob_l):
    _is_help = True
elif _blob_l:
    for _w in ('help', 'ayuda', 'options', 'opciones', 'params', 'usage'):
        if re.search(r'(^|\s|/)' + _w + r'(\s|$|\?|!|\.)', _blob_l):
            _is_help = True
if _blob_l.find('?') >= 0 and len(_blob_l) <= 12:
    _is_help = True

if _is_help:
    result = {
        'formatted_text': (
            '<div class="card border-0 shadow-sm" style="max-width:100%">'
            '<div class="card-body">'
            '<h5 class="card-title">/billing — options</h5>'
            '<ul class="mb-2">'
            '<li><code>/billing</code> — last <strong>12 months</strong></li>'
            '<li><code>/billing 6</code> — last <strong>N months</strong> (1–12)</li>'
            '<li><code>/billing 2025</code> — full <strong>year</strong></li>'
            '<li><code>/billing 2024-2025</code> — year range</li>'
            '<li><code>/billing ytd</code> — year to date</li>'
            '</ul>'
            '<p class="mb-0 text-muted small">Posted customer invoices '
            '(out_invoice), untaxed amount by month.</p>'
            '</div></div>'
        ),
        '__return_direct__': True,
        '__stop_after_direct__': True,
        '__no_footer__': True,
    }
else:
    _n_months = 12
    _sd = None
    _ed = str(_today)
    _label = 'last 12 months'

    if _blob_l in ('ytd', 'year to date', 'año en curso', 'ano en curso'):
        _sd = '%04d-01-01' % _today.year
        _label = 'YTD %s' % _today.year
    else:
        _m_range = re.search(
            r'\b(19\d{2}|20\d{2})\s*[-–a]+\s*(19\d{2}|20\d{2})\b', _blob_l,
        )
        _m_year = re.search(r'\b(19\d{2}|20\d{2})\b', _blob)
        _m_n = re.fullmatch(r'\s*([1-9]|1[0-2])\s*', _blob or '')
        if _m_range:
            y1, y2 = int(_m_range.group(1)), int(_m_range.group(2))
            if y1 > y2:
                y1, y2 = y2, y1
            _sd = '%04d-01-01' % y1
            _ed = '%04d-12-31' % y2
            _label = '%s–%s' % (y1, y2)
        elif _m_year and not re.search(r'\b([1-9]|1[0-2])\b', _blob or ''):
            y = int(_m_year.group(1))
            _sd = '%04d-01-01' % y
            _ed = '%04d-12-31' % y
            _label = str(y)
        elif _m_n:
            _n_months = int(_m_n.group(1))
            _label = 'last %s months' % _n_months
        if _sd is None:
            y, m = _today.year, _today.month - (_n_months - 1)
            while m <= 0:
                m += 12
                y -= 1
            _sd = '%04d-%02d-01' % (y, m)

    invoices = env['account.move'].search([
        ('move_type', '=', 'out_invoice'),
        ('state', '=', 'posted'),
        ('invoice_date', '>=', _sd),
        ('invoice_date', '<=', _ed),
    ])
    by_month = {}
    for inv in invoices:
        if not inv.invoice_date:
            continue
        key = inv.invoice_date.strftime('%Y-%m')
        slot = by_month.setdefault(key, {'Amount': 0.0, 'Invoices': 0})
        slot['Amount'] += inv.amount_untaxed
        slot['Invoices'] += 1

    rows = [
        {
            'Month': k,
            'Amount': round(v['Amount'], 2),
            'Invoices': v['Invoices'],
        }
        for k, v in sorted(by_month.items())
    ]
    if not rows:
        result = {
            'formatted_text': (
                '<div class="alert alert-info">No posted customer invoices '
                'in period <strong>%s</strong> (%s — %s).</div>'
                % (_label, _sd, _ed)
            ),
            '__return_direct__': True,
            '__stop_after_direct__': True,
            '__no_footer__': True,
        }
    else:
        result = {
            'data': rows,
            'summary': (
                'Billing by month · %s (%s — %s). Untaxed amount; '
                'posted out_invoice only.'
                % (_label, _sd, _ed)
            ),
            # Chart-first: this skill returns a time-series chart (not sticky guess).
            'show_mode': 'show-chart',
            'chart_engine': 'echarts',
            '__return_direct__': True,
            '__stop_after_direct__': True,
        }
