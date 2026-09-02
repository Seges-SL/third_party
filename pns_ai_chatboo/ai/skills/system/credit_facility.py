# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# SKILL: credit-facility — dispuesto fin de mes; chunk PDF; periodo + help + ask
from datetime import date
from collections import defaultdict
import re
import calendar

result = {}
_today = date.today()
_CHUNK = 5
_SERIES = 'Series'
_MONTH = 'Month'
_MON = {
    1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
    7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec',
}


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
        lab = ('month %s' % yms[0]) if len(yms) == 1 else 'specific months'
        return start_d, end_d, lab, yms
    m_year = re.search(r'\b(19\d{2}|20\d{2})\b', blob)
    if m_year:
        yy = int(m_year.group(1))
        end_d = date(yy, 12, 31)
        if end_d > today:
            end_d = today
        return date(yy, 1, 1), end_d, str(yy), None
    m_n = re.search(r'\b([1-9]|[1-5][0-9]|60)\b', blob_l)
    if m_n:
        n = int(m_n.group(1))
        y, m = today.year, today.month - (n - 1)
        while m <= 0:
            m += 12
            y -= 1
        return date(y, m, 1), today, 'last %s months' % n, None
    return None, None, None, None


def _chunk_wide(wide, months, month_labels, selected=None):
    use = list(selected) if selected else list(months)
    if not use:
        return [wide]
    out = []
    for i in range(0, len(use), _CHUNK):
        part = use[i:i + _CHUNK]
        block = []
        for row in wide:
            nr = {_SERIES: row.get(_SERIES)}
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


_blob = _collect_blob()
_blob_l = _blob.lower()

if _is_help(_blob_l):
    # Fixed HTML. Do not %-format with CSS "100%" → ValueError.
    result = {
        'formatted_text': (
            '<div class="card border-0 shadow-sm" style="max-width:100%">'
            '<div class="card-body">'
            '<h5 class="card-title">/credit-facility — options</h5>'
            '<ul class="mb-2">'
            '<li><code>/credit-facility ytd</code> — year to date</li>'
            '<li><code>/credit-facility 12</code> — last <strong>N months</strong> (1–60)</li>'
            '<li><code>/credit-facility 2025</code> — full <strong>year</strong></li>'
            '<li><code>/credit-facility 2024-2025</code> — year range</li>'
            '<li><code>/credit-facility 2025-03</code> — specific month (YYYY-MM)</li>'
            '<li><code>/credit-facility 2025-01,2025-06</code> — specific months</li>'
            '<li><code>/credit-facility ?</code> / <code>help</code> — this help</li>'
            '</ul>'
            '<p class="text-muted small mb-0">'
            'Empty period: ask lightly (do not assume 12 months). '
            'Drawn = creditor balance (credit−debit) at month-end. '
            'Monthly series is split into blocks of '
            + str(_CHUNK)
            + ' months (PDF).'
            '</p></div></div>'
        ),
        '__return_direct__': True,
        '__stop_after_direct__': True,
        '__no_footer__': True,
    }
else:
    start_d, end_d, label, selected_yms = _parse_period(_blob, _today)
    if start_d is None:
        result = {
            'formatted_text': (
                '<div class="card border-0 shadow-sm" style="max-width:100%">'
                '<div class="card-body">'
                '<h5 class="card-title">/credit-facility</h5>'
                '<p class="mb-2">Which period should we analyse?</p>'
                '<p class="text-muted small mb-0">'
                'Examples: <code>ytd</code>, <code>12</code>, <code>2025</code>, '
                '<code>2024-2025</code>, <code>2025-03</code> · '
                '<code>/credit-facility ?</code> for help.'
                '</p></div></div>'
            ),
            '__return_direct__': True,
            '__stop_after_direct__': True,
            '__await_skill_args__': True,
            '__no_footer__': True,
        }
    elif 'account.journal' not in env or 'account.move.line' not in env:
        result = {
            'formatted_text': (
                '<p class="text-muted">Accounting journals/moves are required '
                '(account.journal / account.move.line).</p>'
            ),
            '__return_direct__': True,
            '__stop_after_direct__': True,
            '__no_footer__': True,
        }
    else:
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
            lab = (j.name or acc.name or acc.code).strip()
            lab = re.sub(r'^\[\s*p[oó]liza\s*\]\s*', '', lab, flags=re.I).strip() or acc.code
            short = lab
            m_short = re.search(r'([A-Za-zÁÉÍÓÚáéíóúñÑ.]+)\s*\(?(\d{3,})\)?', lab)
            if m_short:
                short = '%s (%s)' % (m_short.group(1).strip(), m_short.group(2))
            elif len(short) > 18:
                short = short[:16] + '…'
            series_meta.append({
                'aid': acc.id, 'code': acc.code, 'label': lab, 'short': short,
            })
        series_meta = sorted(series_meta, key=lambda x: x['code'])
        if not series_meta:
            result = {
                'formatted_text': (
                    '<div class="alert alert-info">No credit-facility journals '
                    'found in this environment.</div>'
                ),
                '__return_direct__': True,
                '__stop_after_direct__': True,
                '__no_footer__': True,
            }
        else:
            sd, ed = start_d.strftime('%Y-%m-%d'), end_d.strftime('%Y-%m-%d')
            aids = [s['aid'] for s in series_meta]
            months = []
            y, m = start_d.year, start_d.month
            while (y, m) <= (end_d.year, end_d.month):
                months.append('%04d-%02d' % (y, m))
                m += 1
                if m > 12:
                    m, y = 1, y + 1
            month_labels = {}
            for ym in months:
                month_labels[ym] = '%s %02d' % (
                    _MON[int(ym[5:7])], int(ym[:4]) % 100,
                )
            opening = {s['aid']: 0.0 for s in series_meta}
            for line in env['account.move.line'].search([
                ('account_id', 'in', aids),
                ('move_id.state', '=', 'posted'),
                ('date', '<', sd),
            ]):
                if line.account_id.id in opening:
                    opening[line.account_id.id] += line.credit - line.debit
            by_ym = defaultdict(float)
            for line in env['account.move.line'].search([
                ('account_id', 'in', aids),
                ('move_id.state', '=', 'posted'),
                ('date', '>=', sd),
                ('date', '<=', ed),
            ]):
                by_ym[(str(line.date)[:7], line.account_id.id)] += (
                    line.credit - line.debit
                )
            running = dict(opening)
            series_vals = {s['aid']: [] for s in series_meta}
            series_total = []
            monthly = []
            for ym in months:
                row = {_MONTH: month_labels[ym]}
                tot = 0.0
                for s in series_meta:
                    aid = s['aid']
                    running[aid] = running.get(aid, 0.0) + by_ym.get((ym, aid), 0.0)
                    bal = round(running[aid], 2)
                    series_vals[aid].append(bal)
                    row[s['short'] + ' €'] = bal
                    tot += bal
                row['Total €'] = round(tot, 2)
                series_total.append(round(tot, 2))
                monthly.append(row)
            wide = []
            for s in series_meta:
                row = {_SERIES: s['label']}
                for i, ym in enumerate(months):
                    row[month_labels[ym]] = series_vals[s['aid']][i]
                wide.append(row)
            row_t = {_SERIES: 'Total %s facilities' % len(series_meta)}
            for i, ym in enumerate(months):
                row_t[month_labels[ym]] = series_total[i]
            wide.append(row_t)
            first_tot = series_total[0] if series_total else 0.0
            last_tot = series_total[-1] if series_total else 0.0
            delta = round(last_tot - first_tot, 2)
            pct = round(delta / first_tot * 100, 1) if abs(first_tot) > 0.01 else None
            pct_txt = (' (%.1f %%)' % pct) if pct is not None else ''
            blocks = _chunk_wide(wide, months, month_labels, selected_yms)
            n_blocks = len(blocks)
            groups = []
            for bi, block in enumerate(blocks):
                title = 'Month-end drawn — %s' % label
                if n_blocks > 1:
                    title = '%s · block %s/%s' % (title, bi + 1, n_blocks)
                groups.append({
                    'title': title,
                    'data': block,
                    # Chart-first: time-series drawn-credit chart (skill answer).
                    'show_mode': 'show-chart',
                    'chart_engine': 'echarts',
                })
            groups.append({
                'title': 'Monthly detail of drawn credit',
                'data': monthly,
            })
            result = {
                'groups': groups,
                'footer': (
                    'Drawn = creditor balance (credit − debit), posted moves. '
                    'Period: %s (%s — %s). Entities: %s. '
                    'Total start: %.2f · Total end: %.2f · Change: %+.2f%s.'
                ) % (
                    label, sd, ed,
                    ', '.join(s['label'] for s in series_meta),
                    first_tot, last_tot, delta, pct_txt,
                ),
                'summary': (
                    'Credit facilities · %s · %s entities · '
                    'total change %+.2f%s'
                ) % (label, len(series_meta), delta, pct_txt),
                # Chart-first for the wide series groups above.
                'show_mode': 'show-chart',
                'chart_engine': 'echarts',
                '__return_direct__': True,
                '__stop_after_direct__': True,
            }
