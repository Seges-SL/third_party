# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# SKILL: financial-health — EXACT base JYDY-14 (financial_situation_report)
# + credit-facility / occ-polizas + neutral pajama (46Z6)
from datetime import date

from collections import defaultdict
import re

import calendar

_CHUNK = 5


def _add_part(out, x):
    if x is None:
        return
    if isinstance(x, dict):
        for v in x.values():
            if v is not None and str(v).strip() and str(v).strip().lower() not in ('none', 'null'):
                out.append(str(v).strip())
    elif isinstance(x, (list, tuple)):
        for v in x:
            if v is not None and str(v).strip():
                out.append(str(v).strip())
    else:
        s = str(x).strip()
        if s and s.lower() not in ('none', 'null'):
            out.append(s)


def _collect_blob():
    out = []
    try:
        _add_part(out, arguments)
    except NameError:
        pass
    try:
        _add_part(out, periodo)
    except NameError:
        pass
    try:
        _add_part(out, lugar)
    except NameError:
        pass
    try:
        _add_part(out, fecha)
    except NameError:
        pass
    try:
        _add_part(out, mes)
    except NameError:
        pass
    try:
        _add_part(out, meses)
    except NameError:
        pass
    try:
        _add_part(out, anio)
    except NameError:
        pass
    try:
        _add_part(out, year)
    except NameError:
        pass
    return ' '.join(out).strip()


def _is_help(blob_l):
    words = (
        '?', 'ayuda', 'help', 'opciones', 'options', 'params', 'parametros',
        'parámetros', '/?', '/ayuda', '/help', 'usage', 'uso',
    )
    if blob_l in words or (blob_l and re.match(r'^[?]+$', blob_l)):
        return True
    if blob_l:
        for w in ('ayuda', 'help', 'opciones', 'options', 'parametros', 'parámetros', 'usage'):
            if re.search(r'(^|\s|/)' + w + r'(\s|$|\?|!|\.)', blob_l):
                return True
    return blob_l.find('?') >= 0 and len(blob_l) <= 12


def _parse_period(blob, today):
    blob = (blob or '').strip()
    if not blob:
        return None, None, None, None
    blob_l = blob.lower()
    yms = ['%s-%s' % (a, b) for a, b in re.findall(
        r'\b((?:19|20)\d{2})-(0[1-9]|1[0-2])\b', blob,
    )]
    yms = sorted(set(yms))
    if re.search(r'\bytd\b', blob_l) or blob_l in (
        'year to date', 'año en curso', 'ano en curso', 'ytm',
    ):
        return date(today.year, 1, 1), today, 'YTD %s' % today.year, None
    m_range = re.search(
        r'\b(19\d{2}|20\d{2})\s*[-–—a]\s*(19\d{2}|20\d{2})\b', blob_l,
    )
    if m_range:
        y1, y2 = int(m_range.group(1)), int(m_range.group(2))
        if y1 > y2:
            y1, y2 = y2, y1
        end_d = date(y2, 12, 31)
        if end_d > today:
            end_d = today
        return date(y1, 1, 1), end_d, '%s–%s' % (y1, y2), None
    if yms:
        y1, m1 = int(yms[0][:4]), int(yms[0][5:7])
        y2, m2 = int(yms[-1][:4]), int(yms[-1][5:7])
        start_d = date(y1, m1, 1)
        end_d = date(y2, m2, calendar.monthrange(y2, m2)[1])
        if end_d > today:
            end_d = today
        lab = yms[0] if len(yms) == 1 else 'months'
        return start_d, end_d, lab, yms
    m_year = re.search(r'\b(19\d{2}|20\d{2})\b', blob)
    if m_year:
        yy = int(m_year.group(1))
        end_d = date(yy, 12, 31)
        if end_d > today:
            end_d = today
        return date(yy, 1, 1), end_d, str(yy), None
    # Structural: "2 años" / "3 years" → N*12 months (digits only; NL words → hybrid).
    m_years = re.search(
        r'\b([1-9]|[1-5][0-9]|60)\s*(años?|years?)\b', blob_l,
    )
    if m_years:
        n = int(m_years.group(1)) * 12
        if n > 60:
            n = 60
        y, m = today.year, today.month - (n - 1)
        while m <= 0:
            m += 12
            y -= 1
        return date(y, m, 1), today, 'last %s months' % n, None
    m_n = re.search(r'\b([1-9]|[1-5][0-9]|60)\b', blob_l)
    if m_n:
        n = int(m_n.group(1))
        y, m = today.year, today.month - (n - 1)
        while m <= 0:
            m += 12
            y -= 1
        return date(y, m, 1), today, 'last %s months' % n, None
    return None, None, None, None


def _chunk_wide_rows(wide, months, month_labels, series_key, selected=None):
    use = list(selected) if selected else list(months)
    if not use:
        return [wide]
    out = []
    for i in range(0, len(use), _CHUNK):
        part = use[i:i + _CHUNK]
        block = []
        for row in wide:
            nr = {series_key: row.get(series_key)}
            for ym in part:
                lab = month_labels.get(ym, ym)
                if lab in row:
                    nr[lab] = row[lab]
                elif ym in row:
                    nr[ym] = row[ym]
            block.append(nr)
        out.append(block)
    return out



def _is_facility_journal(j):
    jname = (j.name or '').lower()
    aname = (j.default_account_id.name or '').lower() if j.default_account_id else ''
    code = (j.code or '').lower()
    markers = (
        'póliza', 'poliza', 'credit facility', 'line of credit',
        'credit line', 'revolving',
    )
    if any(m in jname or m in aname for m in markers):
        return True
    return bool(re.match(r'^p\d', code))


def _facilities_ytd(start_d, end_d, lab):
    if 'account.journal' not in env or 'account.move.line' not in env:
        return None, None, 0.0, 0.0, lab['note']
    journals = env['account.journal'].search([
        '|', '|', '|', '|', '|',
        ('name', 'ilike', 'póliza'),
        ('name', 'ilike', 'poliza'),
        ('name', 'ilike', 'credit facility'),
        ('name', 'ilike', 'line of credit'),
        ('code', '=like', 'P%'),
        ('default_account_id.name', 'ilike', 'póliza'),
    ])
    series_meta = []
    seen = set()
    for j in journals:
        if not _is_facility_journal(j):
            continue
        acc = j.default_account_id
        if not acc or not acc.code or acc.id in seen:
            continue
        seen.add(acc.id)
        name = (j.name or acc.name or acc.code).strip()
        name = re.sub(r'^\[\s*p[oó]liza\s*\]\s*', '', name, flags=re.I).strip() or acc.code
        series_meta.append({'aid': acc.id, 'code': acc.code, 'label': name})
    series_meta = sorted(series_meta, key=lambda x: x['code'])
    if not series_meta:
        return None, None, 0.0, 0.0, lab['note']
    aids = [s['aid'] for s in series_meta]
    sd, ed = str(start_d), str(end_d)
    months = []
    y, m = start_d.year, start_d.month
    while (y, m) <= (end_d.year, end_d.month):
        months.append('%04d-%02d' % (y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    opening = {s['aid']: 0.0 for s in series_meta}
    for line in env['account.move.line'].search([
        ('account_id', 'in', aids),
        ('move_id.state', '=', 'posted'),
        ('date', '<', sd),
    ]):
        opening[line.account_id.id] += line.credit - line.debit
    by_ym = defaultdict(float)
    for line in env['account.move.line'].search([
        ('account_id', 'in', aids),
        ('move_id.state', '=', 'posted'),
        ('date', '>=', sd),
        ('date', '<=', ed),
    ]):
        by_ym[(str(line.date)[:7], line.account_id.id)] += line.credit - line.debit
    running = dict(opening)
    totals = []
    wide = [{lab['series']: s['label']} for s in series_meta]
    for ym in months:
        tot = 0.0
        for i, s in enumerate(series_meta):
            running[s['aid']] = running.get(s['aid'], 0.0) + by_ym.get((ym, s['aid']), 0.0)
            bal = round(running[s['aid']], 2)
            wide[i][ym] = bal
            tot += bal
        totals.append(round(tot, 2))
    row_t = {lab['series']: lab['total'] % len(series_meta)}
    for i, ym in enumerate(months):
        row_t[ym] = totals[i]
    wide.append(row_t)
    first = totals[0] if totals else 0.0
    last = totals[-1] if totals else 0.0
    detail = [{
        lab['journal']: s['label'],
        lab['account']: s['code'],
        lab['drawn']: wide[i][months[-1]] if months else 0.0,
    } for i, s in enumerate(series_meta)]
    return wide, detail, first, last, None


def _pajama(rows):
    """Subtle grey zebra only (report tables; no quartile / no traffic lights)."""
    if not rows:
        return rows
    soft = ('#f7f8fa', '#eef1f5')
    for i, r in enumerate(rows):
        if isinstance(r, dict):
            r.pop('_row_color', None)
            r['_row_color'] = soft[i % 2]
    return rows


def financial_situation_report(start_d, end_d, label):
    """Financial situation report for the given period."""
    ref = end_d
    y0, m0, d0 = ref.year, ref.month, ref.day
    start_ytd = start_d
    end_ytd = end_d
    end_pytd = date(end_d.year - 1, end_d.month, min(end_d.day, 28))
    try:
        end_pytd = date(end_d.year - 1, end_d.month, end_d.day)
    except ValueError:
        end_pytd = date(end_d.year - 1, end_d.month, 28)
    start_pytd = date(start_d.year - 1, start_d.month, min(start_d.day, 28))
    try:
        start_pytd = date(start_d.year - 1, start_d.month, start_d.day)
    except ValueError:
        start_pytd = date(start_d.year - 1, start_d.month, 28)
    start_prev = date(y0 - 1, 1, 1)
    end_prev = date(y0 - 1, 12, 31)
    start_prev2 = date(y0 - 2, 1, 1)
    end_prev2 = date(y0 - 2, 12, 31)
    pay_cut = date(y0 - 2, m0, 1)

    def inv_agg(date_from, date_to, types):
        moves = env['account.move'].search([
            ('state', '=', 'posted'),
            ('move_type', 'in', types),
            ('invoice_date', '>=', str(date_from)),
            ('invoice_date', '<=', str(date_to)),
        ])
        base = total = 0.0
        n_inv = n_ref = 0
        by_partner = {}
        by_month = {}
        by_pay = {}
        for mv in moves:
            sign = 1.0 if mv.move_type in ('out_invoice', 'in_invoice') else -1.0
            b = (mv.amount_untaxed or 0.0) * sign
            t = (mv.amount_total or 0.0) * sign
            base += b
            total += t
            if mv.move_type in ('out_invoice', 'in_invoice'):
                n_inv += 1
            else:
                n_ref += 1
            if mv.move_type in ('out_invoice', 'out_refund') and mv.partner_id:
                pid = mv.partner_id.id
                if pid not in by_partner:
                    by_partner[pid] = {
                        'id': pid, 'Customer': mv.partner_id.name or '',
                        'Base': 0.0, 'Total': 0.0, 'Invoices': 0,
                    }
                by_partner[pid]['Base'] += b
                by_partner[pid]['Total'] += t
                if mv.move_type == 'out_invoice':
                    by_partner[pid]['Invoices'] += 1
            if mv.move_type in ('out_invoice', 'out_refund') and mv.invoice_date:
                mk = str(mv.invoice_date)[:7]
                by_month[mk] = by_month.get(mk, 0.0) + b
            if mv.move_type in ('out_invoice', 'out_refund'):
                st = mv.payment_state or 'unknown'
                by_pay[st] = by_pay.get(st, 0) + 1
        return {
            'base': base, 'total': total, 'n_inv': n_inv, 'n_ref': n_ref,
            'by_partner': by_partner, 'by_month': by_month, 'by_pay': by_pay,
        }

    s_ytd = inv_agg(start_ytd, end_ytd, ['out_invoice', 'out_refund'])
    s_pytd = inv_agg(start_pytd, end_pytd, ['out_invoice', 'out_refund'])
    s_prev = inv_agg(start_prev, end_prev, ['out_invoice', 'out_refund'])
    s_prev2 = inv_agg(start_prev2, end_prev2, ['out_invoice', 'out_refund'])
    p_ytd = inv_agg(start_ytd, end_ytd, ['in_invoice', 'in_refund'])
    p_pytd = inv_agg(start_pytd, end_pytd, ['in_invoice', 'in_refund'])

    var_ytd = 0.0
    if s_pytd['base']:
        var_ytd = round((s_ytd['base'] - s_pytd['base']) * 100.0 / s_pytd['base'], 2)

    open_ar = env['account.move'].search([
        ('state', '=', 'posted'),
        ('move_type', 'in', ['out_invoice', 'out_refund']),
        ('payment_state', 'in', ['not_paid', 'partial', 'in_payment']),
    ])
    total_residual = 0.0
    overdue_residual = 0.0
    ar_by = {}
    for mv in open_ar:
        if mv.move_type == 'out_refund':
            res = -abs(mv.amount_residual or 0.0)
        else:
            res = abs(mv.amount_residual or 0.0)
        total_residual += res
        idate = mv.invoice_date_due or mv.invoice_date
        if idate and idate < ref and res > 0:
            overdue_residual += res
        if not mv.partner_id:
            continue
        pid = mv.partner_id.id
        if pid not in ar_by:
            ar_by[pid] = {
                'id': pid,
                'Customer': mv.partner_id.name or '',
                'VAT': mv.partner_id.vat or '',
                'Open invoices': 0,
                'Open amount': 0.0,
                'Paid hist. 24m': 0.0,
                'paid_n': 0,
                'pend_n': 0,
            }
        ar_by[pid]['Open amount'] += res
        if res > 0 and mv.move_type == 'out_invoice':
            ar_by[pid]['Open invoices'] += 1
            ar_by[pid]['pend_n'] += 1

    paid_hist = env['account.move'].search([
        ('state', '=', 'posted'),
        ('move_type', '=', 'out_invoice'),
        ('payment_state', '=', 'paid'),
        ('invoice_date', '>=', str(pay_cut)),
        ('partner_id', 'in', list(ar_by.keys()) or [0]),
    ])
    for mv in paid_hist:
        pid = mv.partner_id.id
        if pid in ar_by:
            ar_by[pid]['Paid hist. 24m'] += mv.amount_total or 0.0
            ar_by[pid]['paid_n'] += 1

    ar_rows = []
    for pid, d in ar_by.items():
        if d['Open amount'] <= 0.01:
            continue
        tot_n = d['paid_n'] + d['pend_n']
        ratio = round(d['paid_n'] * 100.0 / tot_n, 2) if tot_n else 0.0
        risk = 'ok' if (d['paid_n'] >= 3 and ratio >= 70.0) else 'risk'
        row = {
            'id': d['id'],
            'Customer': d['Customer'],
            'VAT': d['VAT'],
            'Open invoices': d['Open invoices'],
            'Open amount': round(d['Open amount'], 2),
            'Paid hist. 24m': round(d['Paid hist. 24m'], 2),
            'Pay ratio %': ratio,
            'Risk': risk,
        }
        ar_rows.append(row)
    ar_rows = sorted(ar_rows, key=lambda x: x['Open amount'], reverse=True)[:15]

    open_ap = env['account.move'].search([
        ('state', '=', 'posted'),
        ('move_type', 'in', ['in_invoice', 'in_refund']),
        ('payment_state', 'in', ['not_paid', 'partial', 'in_payment']),
    ])
    ap_total = 0.0
    for mv in open_ap:
        ap_total += abs(mv.amount_residual or 0.0)

    ytd_invoiced = 0.0
    ytd_res = 0.0
    ytd_moves = env['account.move'].search([
        ('state', '=', 'posted'),
        ('move_type', 'in', ['out_invoice', 'out_refund']),
        ('invoice_date', '>=', str(start_ytd)),
        ('invoice_date', '<=', str(end_ytd)),
    ])
    for mv in ytd_moves:
        sign = 1.0 if mv.move_type == 'out_invoice' else -1.0
        ytd_invoiced += (mv.amount_total or 0.0) * sign
        if mv.payment_state in ('not_paid', 'partial'):
            ytd_res += abs(mv.amount_residual or 0.0)
    cobrado_pct = 0.0
    if ytd_invoiced:
        cobrado_pct = round(max(0.0, (ytd_invoiced - ytd_res) * 100.0 / ytd_invoiced), 2)

    top_partners = sorted(s_ytd['by_partner'].values(), key=lambda x: x['Base'], reverse=True)
    top3 = sum(x['Base'] for x in top_partners[:3])
    conc = round(top3 * 100.0 / s_ytd['base'], 2) if s_ytd['base'] else 0.0
    top10 = []
    for i, p in enumerate(top_partners[:10]):
        r = {
            'id': p['id'],
            'Customer': p['Customer'],
            'Base': round(p['Base'], 2),
            'Total': round(p['Total'], 2),
            'Invoices': p['Invoices'],
        }
        top10.append(r)

    months = sorted(s_ytd['by_month'].items())
    month_rows = [{'Month': k, 'Untaxed base': round(v, 2)} for k, v in months]
    pay_rows = [{'State': k, 'Invoice count': v} for k, v in sorted(s_ytd['by_pay'].items(), key=lambda x: -x[1])]

    def bal_prefix(prefixes):
        domain = [('move_id.state', '=', 'posted'), ('account_id', '!=', False)]
        lines = env['account.move.line'].search(domain)
        total = 0.0
        detail = {}
        for line in lines:
            code = line.account_id.code or ''
            ok = False
            for pfx in prefixes:
                if code.startswith(pfx):
                    ok = True
                    break
            if not ok:
                continue
            s = (line.debit or 0.0) - (line.credit or 0.0)
            total += s
            aid = line.account_id.id
            if aid not in detail:
                detail[aid] = {
                    'code': code,
                    'account': line.account_id.name or '',
                    'saldo': 0.0,
                }
            detail[aid]['saldo'] += s
        return total, detail

    cash, cash_d = bal_prefix(['57'])
    ar_acc, _ = bal_prefix(['430', '431', '432'])
    ap_acc, ap_d = bal_prefix(['400', '401'])
    acr_acc, acr_d = bal_prefix(['410', '411'])
    fin_cp, fin_cp_d = bal_prefix(['52'])
    fin_lp, fin_lp_d = bal_prefix(['17'])
    fiscal, fiscal_d = bal_prefix(['475', '476', '477', '465'])

    def as_liab(x):
        return round(-x if x < 0 else x, 2)

    pos_rows = [
        {'Item': 'Cash (57*)', 'Balance': round(cash, 2), 'Nature': 'Asset'},
        {'Item': 'Receivables ledger (430-432)', 'Balance': round(ar_acc, 2), 'Nature': 'Asset'},
        {'Item': 'Vendors (400-401)', 'Balance': as_liab(ap_acc), 'Nature': 'Liability'},
        {'Item': 'Creditors (410-411)', 'Balance': as_liab(acr_acc), 'Nature': 'Liability'},
        {'Item': 'ST financial debt (52*)', 'Balance': as_liab(fin_cp), 'Nature': 'Liability'},
        {'Item': 'LT financial debt (17*)', 'Balance': as_liab(fin_lp), 'Nature': 'Liability'},
        {'Item': 'Tax / SS / payroll', 'Balance': as_liab(fiscal), 'Nature': 'Liability'},
    ]

    cash_rows = sorted(
        [{'code': d['code'], 'account': d['account'], 'saldo': round(d['saldo'], 2)}
         for d in cash_d.values() if abs(d['saldo']) > 0.01],
        key=lambda x: x['code'],
    )

    liab_merged = []
    for d in list(fin_cp_d.values()) + list(fin_lp_d.values()) + list(ap_d.values()) + list(acr_d.values()) + list(fiscal_d.values()):
        s = -d['saldo'] if d['saldo'] < 0 else d['saldo']
        if abs(s) < 1:
            continue
        code = d['code']
        if code.startswith('52'):
            tipo = 'deuda_cp'
        elif code.startswith('17'):
            tipo = 'deuda_lp'
        elif code.startswith('40'):
            tipo = 'proveedores'
        elif code.startswith('41'):
            tipo = 'acreedores'
        else:
            tipo = 'hp_ss'
        liab_merged.append({
            'code': code,
            'account': d['account'],
            'type': tipo,
            'saldo': round(s, 2),
        })
    liab_merged = sorted(liab_merged, key=lambda x: x['saldo'], reverse=True)[:25]

    fm = round(cash + ar_acc - as_liab(ap_acc) - as_liab(acr_acc), 2)
    fin_tot = as_liab(fin_cp) + as_liab(fin_lp)
    pas_op = as_liab(ap_acc) + as_liab(acr_acc) + as_liab(fiscal)
    cov = round(cash / as_liab(fin_cp), 2) if as_liab(fin_cp) else 0.0

    ratio_rows = [
        {'Ratio': 'Net cash', 'Value': round(cash, 2)},
        {'Ratio': 'Approx. working capital (cash+AR − AP/creditors)', 'Value': fm},
        {'Ratio': 'Total financial debt', 'Value': round(fin_tot, 2)},
        {'Ratio': 'Operating liabilities (AP+creditors+tax)', 'Value': round(pas_op, 2)},
        {'Ratio': 'Cash / ST financial debt', 'Value': cov},
    ]

    kpis = [
        {'Metric': 'Net sales base (%s)' % label, 'Value': round(s_ytd['base'], 2)},
        {'Metric': 'Net sales base prior-year comparable period', 'Value': round(s_pytd['base'], 2)},
        {'Metric': 'Period vs prior-year %', 'Value': var_ytd},
        {'Metric': 'Full-year sales base %s' % (y0 - 1), 'Value': round(s_prev['base'], 2)},
        {'Metric': 'Full-year sales base %s' % (y0 - 2), 'Value': round(s_prev2['base'], 2)},
        {'Metric': 'Customer invoices (%s)' % label, 'Value': s_ytd['n_inv']},
        {'Metric': 'Purchases base (%s)' % label, 'Value': round(p_ytd['base'], 2)},
        {'Metric': 'Purchases base prior-year comparable period', 'Value': round(p_pytd['base'], 2)},
        {'Metric': 'Approx. gross margin (%s, sales−purchases)' % label, 'Value': round(s_ytd['base'] - p_ytd['base'], 2)},
        {'Metric': 'Open AR (net residual)', 'Value': round(total_residual, 2)},
        {'Metric': 'Overdue AR', 'Value': round(overdue_residual, 2)},
        {'Metric': 'Customers with open AR', 'Value': len([1 for x in ar_by.values() if x['Open amount'] > 0.01])},
        {'Metric': 'Open AP (vendors)', 'Value': round(ap_total, 2)},
        {'Metric': 'Collected vs invoiced (%s) %%' % label, 'Value': cobrado_pct},
        {'Metric': 'Top-3 customer concentration (%s) %%' % label, 'Value': conc},
    ]

    return {
        'tables': [
            {'title': 'Financial KPIs · %s (ref. %s)' % (label, ref.isoformat()), 'data': kpis, 'title_bg': '#eef2f8'},
            {'title': 'Liquidity and debts (ledger balances)', 'data': pos_rows, 'title_bg': '#eef2f8'},
            {'title': 'Liquidity / debt ratios', 'data': ratio_rows, 'title_bg': '#eef6f0'},
            {'title': 'Monthly sales · %s (base)' % label, 'data': month_rows, 'title_bg': '#eef2f8'},
            {'title': 'Top 10 customers · %s' % label, 'data': top10, 'title_bg': '#eef2f8'},
            {'title': 'Top open receivables', 'data': ar_rows, 'title_bg': '#eef2f8'},
            {'title': 'Main liability accounts', 'data': liab_merged, 'title_bg': '#eef3f8'},
            {'title': 'Cash accounts detail', 'data': cash_rows, 'title_bg': '#eef6f0'},
            {'title': 'Customer invoice payment states · %s' % label, 'data': pay_rows, 'title_bg': '#eef2f8'},
        ],
        'footer': (
            'Single temporal scope for the whole report: %s (%s → %s). '
            'Ledger and invoicing as of %s. '
            'Margin ≈ sales base − purchases base.'
        ) % (label, start_d.isoformat(), end_d.isoformat(), ref.strftime('%d/%m/%Y')),
        '__return_direct__': True,
    }


_blob = _collect_blob()
_today = date.today()
# Prefer hybrid-resolved ``periodo`` when it already parses as a canonical token.
try:
    _periodo_only = (periodo or '').strip() if periodo else ''
except NameError:
    _periodo_only = ''
if _periodo_only:
    _ps, _pe, _pl, _psel = _parse_period(_periodo_only, _today)
    if _ps is not None:
        _blob = _periodo_only
_blob_l = _blob.lower()

if _is_help(_blob_l):
    # Fixed HTML (like /nominas). Do not %-format with CSS "100%" → ValueError.
    result = {
        'formatted_text': (
            '<div class="card border-0 shadow-sm" style="max-width:100%">'
            '<div class="card-body">'
            '<h5 class="card-title">/financial-health — options</h5>'
            '<ul class="mb-2">'
            '<li><code>/financial-health</code> — '
            '<strong>last 12 months</strong> (default)</li>'
            '<li><code>/financial-health ytd</code> — '
            '<strong>year to date</strong></li>'
            '<li><code>/financial-health 12</code> — last '
            '<strong>N months</strong> (1–60)</li>'
            '<li><code>/financial-health 2025</code> — '
            '<strong>full year</strong></li>'
            '<li><code>/financial-health 2024-2025</code> — year range</li>'
            '<li><code>/financial-health 2025-03</code> — specific month '
            '(YYYY-MM)</li>'
            '<li><code>/financial-health ?</code> / <code>help</code> / '
            '<code>ayuda</code> — this help</li>'
            '</ul>'
            '<p class="text-muted small mb-0">'
            'Free text (e.g. «last two years») → AI extraction to a canonical '
            'token; if the period is missing, reply in chat to continue.'
            '</p></div></div>'
        ),
        '__return_direct__': True,
        '__stop_after_direct__': True,
        '__no_footer__': True,
    }
elif 'account.move' not in env:
    result = {
        'formatted_text': (
            '<p class="text-muted">Accounting (account.move) is required.</p>'
        ),
        '__return_direct__': True,
        '__stop_after_direct__': True,
        '__no_footer__': True,
    }
else:
    if not _blob:
        _blob = '12'  # default: last 12 months
    _start, _end, _label, _sel = _parse_period(_blob, _today)
    if _start is None:
        result = {
            'formatted_text': (
                '<div class="card border-0 shadow-sm" style="max-width:100%">'
                '<div class="card-body">'
                '<h5 class="card-title">/financial-health</h5>'
                '<p class="mb-2">Could not parse the period. Which one do you want?</p>'
                '<p class="text-muted small mb-0">'
                'Examples: <code>ytd</code>, <code>12</code>, <code>2025</code>, '
                '<code>2024-2025</code>, <code>2025-03</code> · '
                'reply here with the period (no need to retype the slash) · '
                '<code>/financial-health ?</code> for help.'
                '</p></div></div>'
            ),
            '__return_direct__': True,
            '__stop_after_direct__': True,
            '__await_skill_args__': True,
            '__no_footer__': True,
        }
    else:
        result = financial_situation_report(_start, _end, _label)
        _lab = {
            'series': 'Series', 'total': 'Total %s facilities',
            'journal': 'Journal', 'account': 'Account', 'drawn': 'Drawn',
            'note': 'No facility journals detected',
        }
        _cf_wide, _cf_det, _cf_first, _cf_last, _cf_note = _facilities_ytd(
            _start, _end, _lab,
        )
        _tables = list(result.get('tables') or [])
        if _tables and isinstance(_tables[0].get('data'), list):
            _tables[0]['data'].append({
                'Metric': 'Credit facilities drawn (period-end)',
                'Value': round(_cf_last or 0.0, 2),
            })
            _tables[0]['data'].append({
                'Metric': 'Facilities drawn change (period)',
                'Value': round((_cf_last or 0.0) - (_cf_first or 0.0), 2),
            })
            if _cf_note:
                _tables[0]['data'].append({'Metric': 'Facilities', 'Value': _cf_note})
        for _t in _tables:
            _pajama(_t.get('data') or [])
        if _cf_wide:
            _months = []
            _y, _m = _start.year, _start.month
            while (_y, _m) <= (_end.year, _end.month):
                _months.append('%04d-%02d' % (_y, _m))
                _m += 1
                if _m > 12:
                    _m, _y = 1, _y + 1
            _mlabels = {ym: ym for ym in _months}
            if _cf_wide and isinstance(_cf_wide[0], dict):
                _keys = [k for k in _cf_wide[0].keys() if k != 'Series']
                if _keys and not all(k in _mlabels for k in _keys):
                    _use = _keys
                    _blocks = []
                    for _i in range(0, len(_use), _CHUNK):
                        _part = _use[_i:_i + _CHUNK]
                        _block = []
                        for _row in _cf_wide:
                            _nr = {'Series': _row.get('Series')}
                            for _k in _part:
                                if _k in _row:
                                    _nr[_k] = _row[_k]
                            _block.append(_nr)
                        _blocks.append(_block)
                else:
                    _blocks = _chunk_wide_rows(
                        _cf_wide, _months, _mlabels, 'Series', _sel,
                    )
            else:
                _blocks = [_cf_wide]
            _nb = len(_blocks)
            for _bi, _block in enumerate(_blocks):
                _pajama(_block)
                _title = 'Credit facilities — month-end drawn (%s)' % _label
                if _nb > 1:
                    _title = '%s · block %s/%s' % (_title, _bi + 1, _nb)
                _tables.append({
                    'title': _title,
                    'data': _block,
                    'title_bg': '#eef2f8',
                })
        if _cf_det:
            _pajama(_cf_det)
            _tables.append({
                'title': 'Credit facilities — by entity (period-end)',
                'data': _cf_det,
                'title_bg': '#eef2f8',
            })
        result['tables'] = _tables
        result['title'] = 'Financial health · %s' % _label
        result['summary'] = 'Financial health · %s' % _label
        result['__no_charts__'] = True
        result['__subtle_zebra__'] = True
        try:
            result['company'] = (company.name or '').strip() or None
        except NameError:
            try:
                result['company'] = (env.company.name or '').strip() or None
            except Exception:
                result['company'] = None
        # Narrative contract: engine re-injects / completes if the LLM truncates.
        result['report_outline'] = [
            '## Analysis',
            '### Strengths',
            '### Weaknesses and risks',
            '### Liquidity and debts',
            '### Credit facilities',
            '## Conclusion',
            '## Recommendations',
        ]
        _overdue = _drawn = None
        for _t in _tables:
            for _row in (_t.get('data') or []):
                if not isinstance(_row, dict):
                    continue
                _ind = (_row.get('Indicator') or _row.get('Indicador') or '').lower()
                _val = _row.get('Value') if 'Value' in _row else _row.get('Valor')
                if 'overdue' in _ind or 'vencida' in _ind:
                    _overdue = _val
                elif ('drawn' in _ind or 'dispuesto' in _ind) and (
                    'end' in _ind or 'fin' in _ind or 'facility' in _ind
                    or 'póliza' in _ind or 'poliza' in _ind
                ):
                    _drawn = _val
        _stub = []
        _acts = []
        try:
            if _overdue is not None and float(_overdue) > 1000:
                _stub.append(
                    'Accelerate collection of overdue AR (%.0f).' % float(_overdue)
                )
                _acts.append(
                    'accelerate collection of overdue AR (%.0f)' % float(_overdue)
                )
        except (TypeError, ValueError):
            pass
        try:
            if _drawn is not None and float(_drawn) > 0:
                _stub.append(
                    'Monitor facility drawn (%.0f at period-end).' % float(_drawn)
                )
                _acts.append(
                    'monitor facility drawn (%.0f)' % float(_drawn)
                )
        except (TypeError, ValueError):
            pass
        if not _stub:
            _stub.append(
                'Keep monitoring liquidity, collections and facilities.'
            )
        result['recommendations_stub'] = _stub
        if _acts:
            result['closing_required'] = (
                'Recommended action line: %s.' % '; '.join(_acts)
            )
        else:
            result['closing_required'] = (
                'Recommended action line: no urgent action; keep monitoring.'
            )
        result['__stop_after_direct__'] = True
        result.setdefault('__return_direct__', True)
