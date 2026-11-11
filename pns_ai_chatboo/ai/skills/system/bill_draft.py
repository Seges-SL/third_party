# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Bill draft: an attached supplier bill, turned into a vendor bill form.

Nothing is written. The skill reads the newest attachment of the
conversation (or the one named), finds the vendor by a tax id that appears in
its text, the first date and the largest amount, and returns a ``kind=form``
card. The person opens the vendor bill form with what was found filled in,
checks it, and saves or closes it. Bills of that vendor with the same total
(and date, when found) are listed as possible duplicates. Dates follow the order of the user's
language (day/month or month/day); amounts accept either decimal mark.
"""
import re
from datetime import date

try:
    _wanted = (document or '').strip()
except NameError:
    _wanted = ''


def _alnum(text):
    return re.sub(r'[^0-9A-Z]', '', (text or '').upper())


def _pick_document():
    try:
        docs = documents()
    except NameError:
        return None, 'Bill draft reads the files attached to a Chatboo conversation.'
    if not docs:
        return None, (
            'No readable attachment. Attach the supplier bill (PDF, spreadsheet, '
            'or a scan or photo such as jpg, png or webp) with /bill-draft. A scan '
            'or a photo is read by an AI provider with the Vision role (it uses '
            'tokens); if none could read it, nothing was kept.'
        )
    if not _wanted:
        return docs[-1]['name'], ''
    for doc in docs:
        if _wanted.lower() in doc['name'].lower():
            return doc['name'], ''
    return None, 'No attachment named %s. Attached: %s.' % (
        _wanted, ', '.join(doc['name'] for doc in docs),
    )


def _vendor(text):
    flat = _alnum(text)
    own = {_alnum(c.vat) for c in env.company if c.vat}
    found = []
    for row in env['res.partner'].search_read(
        [('vat', '!=', False), ('parent_id', '=', False)], ['vat'],
    ):
        vat = _alnum(row['vat'])
        if len(vat) < 8 or vat in own:
            continue
        bare = vat[2:] if vat[:2].isalpha() and len(vat) >= 10 else vat
        if vat in flat or bare in flat:
            found.append(row['id'])
    Partner = env['res.partner']
    if not found:
        return Partner
    if Partner.fields_get(['supplier_rank']):
        supplier = Partner.search([('id', 'in', found), ('supplier_rank', '>', 0)], limit=1)
        if supplier:
            return supplier
    return Partner.browse(found[:1])


def _day_first():
    lang = env['res.lang'].search([('code', '=', env.user.lang)], limit=1)
    fmt = lang.date_format or '%d/%m/%Y'
    return fmt.find('%d') < fmt.find('%m')


def _first_date(text):
    today = date.today()
    day_first = _day_first()
    for a, b, c in re.findall(r'\b(\d{1,4})[/.\-](\d{1,2})[/.\-](\d{2,4})\b', text):
        if len(a) == 4:
            y, m, d = int(a), int(b), int(c)
        else:
            y = int(c) + (2000 if len(c) == 2 else 0)
            d, m = (int(a), int(b)) if day_first else (int(b), int(a))
        try:
            found = date(y, m, d)
        except ValueError:
            continue
        if today.year - 3 <= found.year <= today.year + 1:
            return found
    return None


def _largest_amount(text):
    best = None
    for whole, cents in re.findall(
        r'(?<![\w.,])(\d{1,3}(?:[.,\u00a0 ]\d{3})+|\d+)[.,](\d{2})(?![.,]?\w)', text,
    ):
        value = float(re.sub(r'\D', '', whole) + '.' + cents)
        if best is None or value > best:
            best = value
    return best


def _duplicates(vendor, total, when):
    if not vendor or not total:
        return []
    domain = [
        ('move_type', 'in', ['in_invoice', 'in_refund']),
        ('partner_id', 'child_of', vendor.id),
        ('state', '!=', 'cancel'),
        ('amount_total', '>=', total - 0.01),
        ('amount_total', '<=', total + 0.01),
    ]
    if when:
        domain.append(('invoice_date', '=', when.isoformat()))
    moves = env['account.move'].search(domain, limit=5, order='invoice_date desc')
    states = dict(env['account.move'].fields_get(['state'])['state']['selection'])
    return [
        'Possible duplicate: %s · %s · %s' % (
            m.name or m.ref or '#%d' % m.id,
            m.invoice_date or '',
            states.get(m.state, m.state),
        )
        for m in moves
    ]


def _message(text):
    return {
        'formatted_text': '<p class="text-muted mb-0">%s</p>' % text,
        '__return_direct__': True,
        '__stop_after_direct__': True,
    }


_name, _problem = _pick_document()
if 'account.move' not in env:
    result = _message('Bill draft needs the Invoicing app.')
elif not _name:
    result = _message(_problem)
else:
    _text = read_document(_name)
    _partner = _vendor(_text)
    _when = _first_date(_text)
    _total = _largest_amount(_text)
    _values = {}
    _lines = []
    if _partner:
        _values['partner_id'] = _partner.id
        _lines.append('Vendor: %s (its tax id is in the document)' % _partner.display_name)
    else:
        _lines.append(
            'Vendor: not found. No tax id in the document matches a contact. '
            'This skill only fills in vendors you already have; to propose the '
            'vendor and the bill with its lines, drop the bill and ask to register it.'
        )
    if _when:
        _values['invoice_date'] = _when.isoformat()
        _lines.append('Bill date: %s' % _when.isoformat())
    else:
        _lines.append('Bill date: not found.')
    if _total is not None:
        _lines.append('Largest amount in the document: %s (check it against the total)' % (
            format_amount(_total, decimals=2),
        ))
    _lines.extend(_duplicates(_partner, _total, _when))
    result = {
        'card': {
            'kind': 'form',
            'action': 'account.action_move_in_invoice_type',
            'title': 'Vendor bill from %s' % _name,
            'subtitle': 'Lines, taxes and the reference are yours to fill in.',
            'values': _values,
            'lines': _lines,
        },
        'summary': 'Vendor bill draft proposed from %s.' % _name,
        '__return_direct__': True,
        '__stop_after_direct__': True,
    }
