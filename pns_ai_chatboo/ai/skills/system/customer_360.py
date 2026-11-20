# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Customer 360 slash skill: one customer across invoicing, CRM and calendar.

Finds the customer by name, VAT or email and gathers what the asking user
can read. Apps that are not installed are left out. In Chatboo the figures
open as one page; elsewhere they come back as tables.
"""
import re
from datetime import date, datetime, timedelta

try:
    _q = customer
except NameError:
    _q = None
_q = str(_q or '').strip()
try:
    _lang = user_lang
except NameError:
    _lang = None
_lang = str(_lang or env.user.lang or 'en_US').replace('_', '-')

_T_META = 'Meta'
_T_PROFILE = 'Profile'
_T_KPI = 'Key figures'
_T_REVENUE = 'Revenue by month'
_T_INVOICES = 'Open invoices'
_T_DEALS = 'Open opportunities'
_T_MEETINGS = 'Meetings'
_T_ACTIVITIES = 'Planned activities'
_T_MESSAGES = 'Latest messages'
_T_OTHERS = 'Other matches'

today = date.today()
now = datetime.now()
_company = env.company
_cid = _company.id
_symbol = _company.currency_id.symbol or ''
_notice = ''
_blocks = []
_kpis = []
partner = None
P = env['res.partner']
_pf = P._fields


def _money(value):
    try:
        return format_amount(value, symbol=_symbol, decimals=0)
    except NameError:
        return '%.0f %s' % (value or 0.0, _symbol)


def _rank(rec):
    exact = 1 if (rec.name or '').strip().lower() == _q.lower() else 0
    rank = rec.customer_rank if 'customer_rank' in _pf else 0
    return (exact, rank or 0, -rec.id)


def _plain(html_text):
    text = re.sub(r'<[^>]+>', ' ', str(html_text or ''))
    for code, char in (('&nbsp;', ' '), ('&amp;', '&'), ('&lt;', '<'),
                       ('&gt;', '>'), ('&quot;', '"'), ('&#39;', "'")):
        text = text.replace(code, char)
    text = ' '.join(text.split())
    return text[:177] + '...' if len(text) > 180 else text


def _iso(value):
    if not value:
        return ''
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')
    return value.isoformat()


if not _q:
    _notice = 'Which customer? Give a name, VAT or email.'
else:
    _cands = P.search([
        '|', '|', ('name', 'ilike', _q), ('vat', 'ilike', _q), ('email', 'ilike', _q),
    ], limit=60)
    _coms = _cands.mapped('commercial_partner_id')
    if not _coms:
        _notice = 'No customer matches "%s".' % _q
    else:
        _ordered = sorted(_coms, key=_rank, reverse=True)
        partner = _ordered[0]
        _others = [
            {
                'Customer': rec.name or '',
                'VAT': rec.vat or '',
                'City': rec.city or '',
            }
            for rec in _ordered[1:6]
        ]

if partner:
    family = P.search([('id', 'child_of', partner.id)])
    ids = family.ids
    first = date(today.year, today.month, 1)
    _base = today.year * 12 + today.month - 1 - 23
    start24 = date(_base // 12, _base % 12 + 1, 1)
    keys = []
    for _i in range(24):
        _m = _base + _i
        keys.append('%04d-%02d' % (_m // 12, _m % 12 + 1))

    revenue = dict((k, 0.0) for k in keys)
    counts = dict((k, 0) for k in keys)
    r12 = p12 = open_total = overdue = 0.0
    open_n = overdue_n = 0
    since = ''
    last_inv = None
    invoice_rows = []
    move_ids = []
    if 'account.move' in env:
        Move = env['account.move']
        mine = [
            ('state', '=', 'posted'),
            ('company_id', '=', _cid),
            ('commercial_partner_id', '=', partner.id),
        ]
        for inv in Move.search(mine + [
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('invoice_date', '>=', str(start24)),
        ]):
            key = '%04d-%02d' % (inv.invoice_date.year, inv.invoice_date.month)
            if key in revenue:
                revenue[key] += float(inv.amount_untaxed_signed or 0.0)
                if inv.move_type == 'out_invoice':
                    counts[key] += 1
        r12 = sum(revenue[k] for k in keys[12:])
        p12 = sum(revenue[k] for k in keys[:12])
        out_inv = mine + [('move_type', '=', 'out_invoice')]
        _first = Move.search(out_inv, order='invoice_date asc, id asc', limit=1)
        _last = Move.search(out_inv, order='invoice_date desc, id desc', limit=1)
        since = _iso(_first.invoice_date) if _first else ''
        last_inv = _last.invoice_date if _last else None
        move_ids = Move.search(mine, order='date desc', limit=100).ids
        for inv in Move.search(out_inv + [('amount_residual', '>', 0)],
                               order='invoice_date_due asc, id asc'):
            due = inv.invoice_date_due or inv.invoice_date
            residual = float(inv.amount_residual_signed or 0.0)
            late = (today - due).days if due and due < today else 0
            open_total += residual
            open_n += 1
            if late:
                overdue += residual
                overdue_n += 1
            if len(invoice_rows) < 12:
                invoice_rows.append({
                    'Invoice': inv.name or '',
                    'Date': _iso(inv.invoice_date),
                    'Due': _iso(due),
                    'Total': round(float(inv.amount_total_signed or 0.0), 2),
                    'Open': round(residual, 2),
                    'Days overdue': late,
                    '_id': inv.id,
                })

    deal_rows = []
    lead_ids = []
    pipe = 0.0
    won_n = 0
    won_amount = 0.0
    if 'crm.lead' in env:
        Lead = env['crm.lead']
        _rev = 'expected_revenue' if 'expected_revenue' in Lead._fields else 'planned_revenue'
        opens = Lead.search([
            ('partner_id', 'child_of', partner.id),
            ('type', '=', 'opportunity'),
            ('probability', '<', 100),
            ('stage_id.is_won', '=', False),
        ], order=_rev + ' desc, id desc', limit=50)
        won = Lead.search([
            ('partner_id', 'child_of', partner.id),
            ('stage_id.is_won', '=', True),
            ('date_closed', '>=', str(start24)),
        ])
        lead_ids = opens.ids + won.ids
        won_n = len(won)
        won_amount = sum(float(getattr(w, _rev) or 0.0) for w in won)
        for lead in opens:
            amount = float(getattr(lead, _rev) or 0.0)
            pipe += amount
            if len(deal_rows) < 10:
                deal_rows.append({
                    'Opportunity': lead.name or '',
                    'Stage': lead.stage_id.name or '',
                    'Salesperson': lead.user_id.name or '',
                    'Expected': round(amount, 2),
                    'Probability': round(float(lead.probability or 0.0)),
                    'Close date': _iso(lead.date_deadline),
                    '_id': lead.id,
                })

    meeting_rows = []
    next_meeting = None
    if 'calendar.event' in env:
        Ev = env['calendar.event']
        _now_s = now.strftime('%Y-%m-%d %H:%M:%S')
        _up = Ev.search([('partner_ids', 'in', ids), ('start', '>=', _now_s)],
                        order='start asc', limit=5)
        _past = Ev.search([('partner_ids', 'in', ids), ('start', '<', _now_s)],
                          order='start desc', limit=5)
        for status, events in (('Upcoming', _up), ('Past', _past)):
            for ev in events:
                meeting_rows.append({
                    'Meeting': ev.name or '',
                    'When': getattr(ev, 'display_time', '') or _iso(ev.start),
                    'Organizer': ev.user_id.name or '',
                    'Attendees': len(ev.partner_ids),
                    'Status': status,
                    '_id': ev.id,
                })
        if _up:
            next_meeting = meeting_rows[0]

    activity_rows = []
    if 'mail.activity' in env:
        for act in env['mail.activity'].search([
            '|',
            '&', ('res_model', '=', 'res.partner'), ('res_id', 'in', ids),
            '&', ('res_model', '=', 'crm.lead'), ('res_id', 'in', lead_ids),
        ], order='date_deadline asc', limit=8):
            activity_rows.append({
                'Activity': act.summary or act.activity_type_id.name or '',
                'Due': _iso(act.date_deadline),
                'Assigned': act.user_id.name or '',
                'On': act.res_name or '',
                'Days': (act.date_deadline - today).days if act.date_deadline else 0,
            })

    message_rows = []
    for msg in env['mail.message'].search([
        '|', '|',
        '&', ('model', '=', 'res.partner'), ('res_id', 'in', ids),
        '&', ('model', '=', 'crm.lead'), ('res_id', 'in', lead_ids),
        '&', ('model', '=', 'account.move'), ('res_id', 'in', move_ids),
        ('message_type', 'in', ['comment', 'email']),
    ], order='date desc, id desc', limit=40):
        text = _plain(msg.body) or (msg.subject or '')
        if not text:
            continue
        message_rows.append({
            'Date': _iso(msg.date)[:10],
            'Author': msg.author_id.name or msg.email_from or '',
            'On': msg.record_name or '',
            'Message': text,
        })
        if len(message_rows) >= 12:
            break

    discipline = 40.0 * (1 - overdue / open_total) if open_total > 0 else 40.0
    if p12 > 0:
        growth = (r12 - p12) / p12
        trend = max(0.0, min(30.0, 15 + 15 * growth))
    else:
        growth = None
        trend = 30.0 if r12 > 0 else 0.0
    quiet = (today - last_inv).days if last_inv else None
    if quiet is None:
        recency = 0
    elif quiet <= 30:
        recency = 30
    elif quiet <= 90:
        recency = 20
    elif quiet <= 180:
        recency = 10
    else:
        recency = 0
    score = int(round(discipline + trend + recency))
    health = 'Healthy' if score >= 70 else ('Watch' if score >= 40 else 'At risk')
    dso = round(open_total / r12 * 365) if r12 > 0 else None

    _kpis = [
        {'Metric': 'Health score', 'Value': score, 'Format': 'score', 'Hint': health},
        {'Metric': 'Revenue (12 months)', 'Value': round(r12, 2), 'Format': 'money',
         'Hint': ('%+d%% vs the 12 months before' % round(growth * 100))
         if growth is not None else 'nothing in the 12 months before'},
        {'Metric': 'Open receivable', 'Value': round(open_total, 2), 'Format': 'money',
         'Hint': '%d open invoices' % open_n},
        {'Metric': 'Overdue', 'Value': round(overdue, 2), 'Format': 'money',
         'Hint': '%d overdue invoices' % overdue_n},
        {'Metric': 'DSO', 'Value': dso, 'Format': 'number', 'Hint': 'days of revenue unpaid'},
    ]
    if 'crm.lead' in env:
        _kpis += [
            {'Metric': 'Open pipeline', 'Value': round(pipe, 2), 'Format': 'money',
             'Hint': '%d opportunities' % len(opens)},
            {'Metric': 'Won (24 months)', 'Value': round(won_amount, 2), 'Format': 'money',
             'Hint': '%d deals' % won_n},
        ]
    if next_meeting:
        _kpis.append({'Metric': 'Next meeting', 'Value': next_meeting['When'],
                      'Format': 'text', 'Hint': next_meeting['Meeting']})

    _place = ', '.join([x for x in (partner.city, partner.country_id.name) if x])
    _phone = partner.phone or getattr(partner, 'mobile', '') or ''
    _terms = getattr(partner, 'property_payment_term_id', None)
    _profile = [{
        'Customer': partner.name or '',
        'VAT': partner.vat or '',
        'Email': partner.email or '',
        'Phone': _phone,
        'City': _place,
        'Salesperson': partner.user_id.name or '',
        'Customer since': since,
        'Payment terms': _terms.name if _terms else '',
        '_id': partner.id,
    }]
    _meta = [{
        'Company': _company.name or '',
        'Currency': _company.currency_id.name or '',
        'Locale': _lang,
        'Generated': today.isoformat(),
    }]
    _revenue_rows = [
        {'Month': k, 'Revenue': round(revenue[k], 2), 'Invoices': counts[k]}
        for k in keys
    ]
    _blocks = [
        {'title': _T_META, 'data': _meta},
        {'title': _T_PROFILE, 'data': _profile},
        {'title': _T_KPI, 'data': _kpis},
        {'title': _T_REVENUE, 'data': _revenue_rows if (r12 or p12) else []},
        {'title': _T_INVOICES, 'data': invoice_rows},
        {'title': _T_DEALS, 'data': deal_rows},
        {'title': _T_MEETINGS, 'data': meeting_rows},
        {'title': _T_ACTIVITIES, 'data': activity_rows},
        {'title': _T_MESSAGES, 'data': message_rows},
        {'title': _T_OTHERS, 'data': _others},
    ]

_page_template = r'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Customer 360</title>
<style>
:root{--bg:#f6f5fb;--card:#fff;--ink:#0f172a;--mute:#64748b;--line:#e7e5f0;--grid:rgba(15,23,42,.07);--mark:rgba(15,23,42,.18);--acc:#7c3aed;--acc2:#db2777;--old:rgba(124,58,237,.28);--pos:#10b981;--neg:#f43f5e;--warn:#f59e0b;--late:rgba(244,63,94,.13);--late-ink:#be123c;--pill:rgba(124,58,237,.12);--shadow:0 1px 2px rgba(15,23,42,.04),0 10px 30px rgba(15,23,42,.07)}
html[data-theme="dark"]{--bg:#0e0b1a;--card:#171329;--ink:#ebe8f5;--mute:#a19bb8;--line:#2a2443;--grid:rgba(255,255,255,.07);--mark:rgba(255,255,255,.2);--acc:#a78bfa;--acc2:#f472b6;--old:rgba(167,139,250,.3);--neg:#fb7185;--late:rgba(251,113,133,.2);--late-ink:#fda4af;--pill:rgba(167,139,250,.18);--shadow:0 0 0 1px rgba(255,255,255,.03),0 10px 30px rgba(0,0,0,.35)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:1260px;margin:0 auto;padding:24px 20px 40px}
.hero{position:relative;overflow:hidden;border-radius:24px;padding:26px 28px;color:#fff;background:radial-gradient(900px 300px at 0% -40%,rgba(255,255,255,.22),transparent 60%),linear-gradient(120deg,#5b21b6 0%,#7c3aed 45%,#db2777 100%);box-shadow:var(--shadow);display:grid;grid-template-columns:auto 1fr auto;gap:22px;align-items:center}
@media (max-width:760px){.hero{grid-template-columns:1fr}}
.av{width:78px;height:78px;border-radius:22px;background:rgba(255,255,255,.18);display:grid;place-items:center;font-size:30px;font-weight:800;letter-spacing:-.02em;border:1px solid rgba(255,255,255,.3)}
.hero h1{margin:0;font-size:28px;letter-spacing:-.02em;font-weight:780}
.hero .sub{opacity:.82;font-size:13px;margin-top:2px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.chip{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.22);border-radius:10px;padding:4px 10px;font-size:12.5px;max-width:320px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chip small{opacity:.7;margin-right:6px;text-transform:uppercase;letter-spacing:.05em;font-size:10px}
.ring{display:grid;place-items:center;text-align:center}
.ring .lbl{font-size:12px;font-weight:700;margin-top:4px;opacity:.95}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:15px 17px;box-shadow:var(--shadow);animation:rise .5s ease both}
.kpi .l{color:var(--mute);font-size:12px;text-transform:uppercase;letter-spacing:.06em;font-weight:600}
.kpi .v{font-size:22px;font-weight:750;letter-spacing:-.02em;margin-top:6px;font-variant-numeric:tabular-nums}
.kpi .h{color:var(--mute);font-size:12px;margin-top:2px}
.kpi.bad .v{color:var(--neg)}
.kpi.txt .v{font-size:15px;line-height:1.3}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media (max-width:960px){.grid{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px 20px;box-shadow:var(--shadow);animation:rise .6s ease both;min-width:0}
.card h2{margin:0 0 12px;font-size:15px;font-weight:700}
.full{grid-column:1/-1}
.tw{overflow:auto}
table.t{width:100%;border-collapse:separate;border-spacing:0;font-size:13px}
table.t th{text-align:left;color:var(--mute);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.05em;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
table.t td{padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
table.t .num{text-align:right;font-variant-numeric:tabular-nums}
a{color:inherit;text-decoration:none}a:hover{color:var(--acc);text-decoration:underline}
.late{display:inline-block;padding:1px 8px;border-radius:99px;font-size:11.5px;font-weight:700;background:var(--late);color:var(--late-ink)}
.ok{color:var(--mute)}
.deal{display:grid;grid-template-columns:1fr auto;gap:6px 12px;padding:11px 0;border-bottom:1px solid var(--line)}
.deal:last-child{border-bottom:0}
.deal .n{font-weight:650;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.deal .a{font-weight:750;font-variant-numeric:tabular-nums}
.deal .m{grid-column:1/-1;display:flex;gap:10px;align-items:center;color:var(--mute);font-size:12px;flex-wrap:wrap}
.pill{display:inline-block;padding:1px 9px;border-radius:99px;background:var(--pill);color:var(--acc);font-weight:700;font-size:11.5px}
.pb{display:inline-block;width:70px;height:6px;border-radius:9px;background:var(--line);overflow:hidden}
.pb b{display:block;height:100%;background:linear-gradient(90deg,var(--acc),var(--acc2))}
.tl{position:relative;margin-left:8px;padding-left:18px;border-left:2px solid var(--line)}
.tl .e{position:relative;padding:0 0 14px}
.tl .e:before{content:"";position:absolute;left:-25px;top:4px;width:12px;height:12px;border-radius:50%;background:var(--card);border:3px solid var(--acc)}
.tl .e.past:before{border-color:var(--line)}
.tl .e .h{font-weight:650}
.tl .e .s{color:var(--mute);font-size:12px}
.tl .e .b{margin-top:3px;font-size:13px}
.foot{margin-top:18px;color:var(--mute);font-size:12px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.others{display:flex;gap:8px;flex-wrap:wrap}
.others span{border:1px solid var(--line);border-radius:10px;padding:3px 9px;background:var(--card)}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes bar{from{transform:scaleY(0)}to{transform:scaleY(1)}}
.rev rect.b{transform-box:fill-box;transform-origin:bottom;animation:bar .8s cubic-bezier(.2,.8,.2,1) both}
.rev rect.o{fill:var(--old)}.gl{stroke:var(--grid)}.mk{stroke:var(--mark)}.ax{fill:var(--mute)}
</style></head>
<body><div class="wrap">
<section class="hero"><div class="av" id="av"></div><div><h1 id="ttl"></h1><div class="sub" id="sub"></div><div class="chips" id="chips"></div></div><div class="ring" id="ring"></div></section>
<section class="kpis" id="kpis"></section>
<section class="grid">
<div class="card full" id="c-rev"><h2></h2><div id="rev"></div></div>
<div class="card" id="c-inv"><h2></h2><div class="tw" id="inv"></div></div>
<div class="card" id="c-deals"><h2></h2><div id="deals"></div></div>
<div class="card" id="c-meet"><h2></h2><div class="tl" id="meet"></div></div>
<div class="card" id="c-act"><h2></h2><div class="tl" id="act"></div></div>
<div class="card full" id="c-msg"><h2></h2><div class="tl" id="msg"></div></div>
</section>
<div class="foot"><div class="others" id="others"></div><div id="foot"></div></div>
<section id="pns-page-rows"></section>
</div>
<script>
const DATA = [{"title": "_", "data": []}];
const TITLE = "Customer 360";
(function(){
  var B = {};
  DATA.forEach(function(b){ B[b.title] = b.data || []; });
  var meta = (B['Meta'] || [])[0] || {};
  var prof = (B['Profile'] || [])[0] || {};
  var LOC = meta.Locale || undefined, CUR = meta.Currency || 'EUR';
  function nf(o){ try { return new Intl.NumberFormat(LOC, o); } catch (e) { return new Intl.NumberFormat(undefined, o); } }
  var money = nf({style:'currency', currency:CUR, maximumFractionDigits:0});
  var compact = nf({style:'currency', currency:CUR, notation:'compact', maximumFractionDigits:1});
  var num = nf({maximumFractionDigits:0});
  var pct = nf({style:'percent', maximumFractionDigits:0});
  function fmt(v, f){
    if (v === null || v === undefined || v === '') return '\u2014';
    if (typeof v !== 'number') return String(v);
    if (f === 'money') return money.format(v);
    return num.format(v);
  }
  function el(tag, cls, text){ var n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; }
  var NS = 'http://www.w3.org/2000/svg';
  function sv(tag, attrs, text){ var n = document.createElementNS(NS, tag); for (var k in attrs) n.setAttribute(k, attrs[k]); if (text !== undefined) n.textContent = text; return n; }
  function card(id, title, rows){
    var c = document.getElementById(id);
    if (!rows || !rows.length) { c.remove(); return null; }
    c.querySelector('h2').textContent = title;
    return c;
  }
  function link(text, model, id){
    var a = el('a', '', text);
    if (id) { a.href = '/web#id=' + id + '&model=' + model + '&view_type=form'; a.target = '_blank'; a.rel = 'noopener'; }
    return a;
  }
  function monthLabel(key){
    var d = new Date(+key.slice(0, 4), +key.slice(5, 7) - 1, 1);
    try { return d.toLocaleDateString(LOC, {month:'short'}); } catch (e) { return key; }
  }

  document.title = TITLE;
  document.getElementById('ttl').appendChild(link(prof.Customer || TITLE, 'res.partner', prof._id));
  document.getElementById('sub').textContent = TITLE.split(' \u00b7 ')[0];
  var words = String(prof.Customer || '?').replace(/[^\p{L}\p{N} ]/gu, ' ').trim().split(/\s+/);
  document.getElementById('av').textContent = ((words[0] || '?').charAt(0) + (words.length > 1 ? words[1].charAt(0) : '')).toUpperCase();
  var chips = document.getElementById('chips');
  Object.keys(prof).forEach(function(k){
    if (k === 'Customer' || k.charAt(0) === '_' || !prof[k]) return;
    var c = el('span', 'chip'); c.appendChild(el('small', '', k)); c.appendChild(document.createTextNode(prof[k])); c.title = k + ': ' + prof[k]; chips.appendChild(c);
  });
  document.getElementById('foot').textContent = [meta.Company, meta.Generated, meta.Currency, meta.Locale].filter(Boolean).join(' \u00b7 ');

  var kp = document.getElementById('kpis');
  (B['Key figures'] || []).forEach(function(r, i){
    if (r.Format === 'score') {
      var s = Math.max(0, Math.min(100, r.Value || 0)), R = 44, C = 2 * Math.PI * R;
      var col = s >= 70 ? '#34d399' : (s >= 40 ? '#fbbf24' : '#fb7185');
      var svg = sv('svg', {viewBox:'0 0 110 110', width:'110', height:'110'});
      svg.appendChild(sv('circle', {cx:55, cy:55, r:R, fill:'none', stroke:'rgba(255,255,255,.2)', 'stroke-width':10}));
      var arc = sv('circle', {cx:55, cy:55, r:R, fill:'none', stroke:col, 'stroke-width':10, 'stroke-linecap':'round', transform:'rotate(-90 55 55)', 'stroke-dasharray':C, 'stroke-dashoffset':C});
      svg.appendChild(arc);
      svg.appendChild(sv('text', {x:55, y:62, 'text-anchor':'middle', 'font-size':'28', 'font-weight':'800', fill:'#fff'}, num.format(s)));
      var ring = document.getElementById('ring');
      ring.appendChild(svg); ring.appendChild(el('div', 'lbl', r.Metric + ' \u00b7 ' + r.Hint));
      requestAnimationFrame(function(){ arc.style.transition = 'stroke-dashoffset 1.2s ease'; arc.setAttribute('stroke-dashoffset', C * (1 - s / 100)); });
      return;
    }
    var k = el('div', 'kpi' + (r.Metric === 'Overdue' && r.Value > 0 ? ' bad' : '') + (r.Format === 'text' ? ' txt' : ''));
    k.style.animationDelay = (i * 50) + 'ms';
    k.appendChild(el('div', 'l', r.Metric));
    k.appendChild(el('div', 'v', fmt(r.Value, r.Format)));
    if (r.Hint) k.appendChild(el('div', 'h', r.Hint));
    kp.appendChild(k);
  });

  var rev = B['Revenue by month'] || [];
  if (card('c-rev', 'Revenue by month', rev)) {
    var W = 1200, H = 260, pl = 64, pb = 40, pt = 16, n = rev.length;
    var vals = rev.map(function(r){ return r.Revenue || 0; });
    var maxR = Math.max.apply(null, vals.concat([1])), minR = Math.min.apply(null, vals.concat([0]));
    var span = maxR - minR || 1, ih = H - pt - pb;
    function y(v){ return pt + ih * (maxR - v) / span; }
    var svg2 = sv('svg', {viewBox:'0 0 ' + W + ' ' + H, width:'100%', 'class':'rev'});
    var defs = sv('defs', {});
    var g1 = sv('linearGradient', {id:'rg', x1:'0', x2:'0', y1:'0', y2:'1'});
    g1.appendChild(sv('stop', {offset:'0', style:'stop-color:var(--acc2)'})); g1.appendChild(sv('stop', {offset:'1', style:'stop-color:var(--acc)'}));
    defs.appendChild(g1); svg2.appendChild(defs);
    for (var t = 0; t <= 4; t++) {
      var v = minR + span * t / 4, yy = y(v);
      svg2.appendChild(sv('line', {x1:pl, x2:W, y1:yy, y2:yy, 'class':'gl'}));
      svg2.appendChild(sv('text', {x:pl - 8, y:yy + 4, 'text-anchor':'end', 'font-size':'11', 'class':'ax'}, compact.format(v)));
    }
    var slot = (W - pl) / n, bw = slot * 0.62;
    rev.forEach(function(r, i){
      var x = pl + slot * i + (slot - bw) / 2, v = r.Revenue || 0, y0 = y(0), yv = y(v);
      var g = sv('g', {});
      var rect = sv('rect', {'class':i < n - 12 ? 'b o' : 'b', x:x, y:Math.min(y0, yv), width:bw, height:Math.max(Math.abs(y0 - yv), 1), rx:4, fill:'url(#rg)'});
      rect.style.animationDelay = (i * 25) + 'ms';
      g.appendChild(rect);
      g.appendChild(sv('text', {x:x + bw / 2, y:H - pb + 16, 'text-anchor':'middle', 'font-size':'10.5', 'class':'ax'}, monthLabel(r.Month)));
      if (i === 0 || r.Month.slice(5) === '01') g.appendChild(sv('text', {x:x + bw / 2, y:H - pb + 31, 'text-anchor':'middle', 'font-size':'10.5', 'font-weight':'700', fill:'currentColor'}, r.Month.slice(0, 4)));
      g.appendChild(sv('title', {}, r.Month + ' \u00b7 ' + money.format(v) + ' \u00b7 ' + num.format(r.Invoices || 0)));
      svg2.appendChild(g);
    });
    svg2.appendChild(sv('line', {x1:pl + slot * (n - 12), x2:pl + slot * (n - 12), y1:pt, y2:H - pb, 'class':'mk', 'stroke-dasharray':'4 4'}));
    document.getElementById('rev').appendChild(svg2);
  }

  var inv = B['Open invoices'] || [];
  if (card('c-inv', 'Open invoices', inv)) {
    var keys = Object.keys(inv[0]).filter(function(k){ return k.charAt(0) !== '_'; });
    var tb = el('table', 't'), th = el('thead'), hr = el('tr');
    keys.forEach(function(k){ hr.appendChild(el('th', typeof inv[0][k] === 'number' ? 'num' : '', k)); });
    th.appendChild(hr); tb.appendChild(th);
    var body = el('tbody');
    inv.forEach(function(r){
      var tr = el('tr');
      keys.forEach(function(k){
        var v = r[k], td = el('td', typeof v === 'number' ? 'num' : '');
        if (k === 'Invoice') td.appendChild(link(v, 'account.move', r._id));
        else if (k === 'Days overdue') td.appendChild(v > 0 ? el('span', 'late', num.format(v)) : el('span', 'ok', '\u2014'));
        else td.textContent = typeof v === 'number' ? money.format(v) : (v || '');
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
    tb.appendChild(body);
    document.getElementById('inv').appendChild(tb);
  }

  var deals = B['Open opportunities'] || [];
  if (card('c-deals', 'Open opportunities', deals)) {
    var box = document.getElementById('deals');
    deals.forEach(function(d){
      var row = el('div', 'deal');
      var n = el('div', 'n'); n.appendChild(link(d.Opportunity, 'crm.lead', d._id)); row.appendChild(n);
      row.appendChild(el('div', 'a', money.format(d.Expected || 0)));
      var m = el('div', 'm');
      if (d.Stage) m.appendChild(el('span', 'pill', d.Stage));
      var pb = el('span', 'pb'); var f = el('b'); f.style.width = (d.Probability || 0) + '%'; pb.appendChild(f); m.appendChild(pb);
      m.appendChild(el('span', '', pct.format((d.Probability || 0) / 100)));
      if (d['Close date']) m.appendChild(el('span', '', d['Close date']));
      if (d.Salesperson) m.appendChild(el('span', '', d.Salesperson));
      row.appendChild(m);
      box.appendChild(row);
    });
  }

  function timeline(id, boxId, title, rows, head, sub, bodyKey, pastOf, model){
    if (!card(id, title, rows)) return;
    var box = document.getElementById(boxId);
    rows.forEach(function(r){
      var e = el('div', 'e' + (pastOf(r) ? ' past' : ''));
      var h = el('div', 'h'); h.appendChild(model ? link(r[head], model, r._id) : document.createTextNode(r[head] || '')); e.appendChild(h);
      e.appendChild(el('div', 's', sub.map(function(k){ return r[k]; }).filter(function(v){ return v !== '' && v !== null && v !== undefined; }).join(' \u00b7 ')));
      if (bodyKey && r[bodyKey]) e.appendChild(el('div', 'b', r[bodyKey]));
      box.appendChild(e);
    });
  }
  timeline('c-meet', 'meet', 'Meetings', B['Meetings'] || [], 'Meeting', ['Status', 'When', 'Organizer'], null, function(r){ return r.Status !== 'Upcoming'; }, 'calendar.event');
  timeline('c-act', 'act', 'Planned activities', B['Planned activities'] || [], 'Activity', ['Due', 'Assigned', 'On'], null, function(r){ return false; }, null);
  timeline('c-msg', 'msg', 'Latest messages', B['Latest messages'] || [], 'Author', ['Date', 'On'], 'Message', function(r){ return true; }, null);

  var others = B['Other matches'] || [];
  if (others.length) {
    var ob = document.getElementById('others');
    ob.appendChild(el('b', '', 'Other matches'));
    others.forEach(function(o){ ob.appendChild(el('span', '', [o.Customer, o.VAT, o.City].filter(Boolean).join(' \u00b7 '))); });
  }
})();
</script>
</body></html>'''

_page_title = 'Customer view' + (' \u00b7 ' + partner.name if partner else '')
_opened = ''
if _blocks:
    try:
        _opened = page_html(_page_template, _blocks, _page_title)
    except NameError:
        _opened = ''

if _notice:
    result = {
        'formatted_text': _notice,
        '__return_direct__': True,
        '__stop_after_direct__': True,
    }
else:
    _kpi_rows = []
    for row in _kpis:
        value = row['Value']
        if value is None:
            shown = ''
        elif row['Format'] == 'money':
            shown = _money(value)
        else:
            shown = str(value)
        _kpi_rows.append({'Metric': row['Metric'], 'Value': shown, 'Note': row['Hint']})
    if _opened:
        result = {
            'tables': [{'title': _T_KPI, 'data': _kpi_rows}],
            'page_url': _opened,
            'title': _page_title,
        }
    else:
        result = {
            'tables': [{'title': _T_KPI, 'data': _kpi_rows}] + [
                {'title': b['title'], 'data': [
                    dict((k, v) for k, v in r.items() if not k.startswith('_'))
                    for r in b['data']
                ]}
                for b in _blocks[3:] if b['data'] and b['title'] != _T_REVENUE
            ],
            'title': _page_title,
        }
    result['__return_direct__'] = True
    result['__stop_after_direct__'] = True
