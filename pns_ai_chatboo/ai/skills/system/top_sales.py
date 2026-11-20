# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Top sales, asked step by step: what to rank, then how many months.

Each question returns ``__skill_state__`` and ``__await_skill_args__`` (the
first state is empty, and an empty state alone does not wait); the engine
hands the state back as ``skill_state`` with the next reply. Answers are numbers, so any language
works. ``/top-sales 2 6`` answers both at once.
"""
import re
from datetime import date

_CHOICES = (
    ('customer', 'Customers'),
    ('product', 'Products'),
    ('salesperson', 'Salespeople'),
)


def _ask(question, options, state):
    items = ''.join('<li><b>%d</b> · %s</li>' % (i + 1, label) for i, label in enumerate(options))
    return {
        'formatted_text': (
            '<p class="mb-1"><b>%s</b></p>%s'
            '<p class="text-muted small mb-0">Reply with the number.</p>'
        ) % (question, '<ul class="mb-1">%s</ul>' % items if items else ''),
        '__skill_state__': state,
        '__await_skill_args__': True,
        '__return_direct__': True,
        '__stop_after_direct__': True,
        '__no_footer__': True,
    }


def _since(months):
    y, m = date.today().year, date.today().month - (months - 1)
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def _ranking(what, since):
    cid = env.company.id
    totals = {}
    if what == 'product':
        lines = env['account.move.line'].search([
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
            ('move_id.state', '=', 'posted'),
            ('move_id.invoice_date', '>=', str(since)),
            ('move_id.company_id', '=', cid),
            ('product_id', '!=', False),
        ])
        for line in lines:
            sign = -1 if line.move_id.move_type == 'out_refund' else 1
            rec = line.product_id
            row = totals.setdefault(rec.id, {
                'id': rec.id, '__model': 'product.product', 'Name': rec.display_name, 'Sales': 0.0,
            })
            row['Sales'] += sign * line.price_subtotal
    else:
        moves = env['account.move'].search([
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', str(since)),
            ('company_id', '=', cid),
        ])
        for mv in moves:
            sign = -1 if mv.move_type == 'out_refund' else 1
            if what == 'customer':
                rec, model = mv.partner_id.commercial_partner_id, 'res.partner'
            else:
                rec, model = mv.invoice_user_id, 'res.users'
            row = totals.setdefault(rec.id or 0, {
                'id': rec.id or 0, '__model': model, 'Name': rec.name or '(none)', 'Sales': 0.0,
            })
            row['Sales'] += sign * mv.amount_untaxed
    rows = sorted(totals.values(), key=lambda r: -r['Sales'])[:10]
    for row in rows:
        row['Sales'] = round(row['Sales'], 2)
        if not row['id']:
            row.pop('__model')
    return rows


try:
    _state = dict(skill_state or {})
except NameError:
    _state = {}
try:
    _numbers = [int(n) for n in re.findall(r'\d+', str(arguments or ''))]
except NameError:
    _numbers = []

if 'what' not in _state and _numbers:
    _pick = _numbers.pop(0)
    if 1 <= _pick <= len(_CHOICES):
        _state['what'] = _CHOICES[_pick - 1][0]
if 'what' in _state and 'months' not in _state and _numbers:
    _state['months'] = max(1, min(60, _numbers.pop(0)))

if 'account.move' not in env:
    result = {
        'formatted_text': '<p class="text-muted">Top sales needs the Invoicing app.</p>',
        '__return_direct__': True,
        '__stop_after_direct__': True,
        '__no_footer__': True,
    }
elif 'what' not in _state:
    result = _ask('What do you want to rank?', [label for _code, label in _CHOICES], _state)
elif 'months' not in _state:
    result = _ask('How many months back? From 1 to 60.', [], _state)
else:
    _label = dict(_CHOICES)[_state['what']]
    _from = _since(_state['months'])
    _rows = _ranking(_state['what'], _from)
    if _rows:
        result = {
            'data': _rows,
            'summary': 'Top %s by untaxed sales since %s.' % (_label.lower(), _from),
            '__hide_columns__': ['id'],
            'show_mode': 'show-chart',
            'chart_engine': 'echarts',
            '__return_direct__': True,
            '__stop_after_direct__': True,
        }
    else:
        result = {
            'formatted_text': '<p class="text-muted">No posted sales since %s.</p>' % _from,
            '__return_direct__': True,
            '__stop_after_direct__': True,
            '__no_footer__': True,
        }
