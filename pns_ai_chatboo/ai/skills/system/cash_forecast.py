# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Cash forecast slash skill: weekly inflows, outflows and running balance.

Today's bank and cash balance plus the open receivable and payable items of
the active company by due date. In Chatboo the figures open as one page;
elsewhere they come back as tables.
"""
from datetime import date, timedelta

try:
    _weeks = weeks
except NameError:
    _weeks = None
if not isinstance(_weeks, int) or _weeks <= 0:
    _weeks = 12
_weeks = min(_weeks, 26)
try:
    _lang = user_lang
except NameError:
    _lang = None
_lang = str(_lang or env.user.lang or 'en_US').replace('_', '-')

_T_META = 'Meta'
_T_KPI = 'Key figures'
_T_WEEKS = 'Cash by week'
_T_IN = 'Biggest receipts ahead'
_T_OUT = 'Biggest payments ahead'

today = date.today()
_company = env.company
_cid = _company.id
_symbol = _company.currency_id.symbol or ''
_notice = ''
_blocks = []
_kpis = []


def _money(value):
    try:
        return format_amount(value, symbol=_symbol, decimals=0)
    except NameError:
        return '%.0f %s' % (value or 0.0, _symbol)


def _item(line, due, label):
    return {
        label: line.partner_id.display_name or '',
        'Document': line.move_id.name or '',
        'Due': due.isoformat(),
        'Amount': round(abs(line.amount_residual), 2),
        'Days': (due - today).days,
        '_id': line.move_id.id,
    }


if 'account.move.line' not in env:
    _notice = 'The Invoicing app is not installed.'
else:
    AML = env['account.move.line']
    if 'account_type' in env['account.account']._fields:
        _kind = 'account_type'
        _recv, _pay, _cash = ['asset_receivable'], ['liability_payable'], ['asset_cash']
    else:
        _kind = 'internal_type'
        _recv, _pay, _cash = ['receivable'], ['payable'], ['liquidity']
    _path = 'account_id.' + _kind

    _cash_dom = [
        ('company_id', '=', _cid),
        ('parent_state', '=', 'posted'),
        (_path, 'in', _cash),
    ]
    cash_today = 0.0
    try:
        _grp = AML.read_group(_cash_dom, ['balance:sum'], [])
        cash_today = float((_grp[0].get('balance') if _grp else 0.0) or 0.0)
    except Exception:
        cash_today = float(sum(AML.search(_cash_dom).mapped('balance')))

    lines = AML.search([
        ('company_id', '=', _cid),
        ('parent_state', '=', 'posted'),
        ('reconciled', '=', False),
        (_path, 'in', _recv + _pay),
        ('amount_residual', '!=', 0),
    ], limit=20000)

    monday = today - timedelta(days=today.weekday())
    end = monday + timedelta(days=7 * _weeks)
    buckets = [{'Week': 'Overdue', 'From': '', 'in': 0.0, 'out': 0.0}]
    for _i in range(_weeks):
        start = monday + timedelta(days=7 * _i)
        buckets.append({
            'Week': 'W%02d' % start.isocalendar()[1],
            'From': start.isoformat(),
            'in': 0.0, 'out': 0.0,
        })
    later_in = 0.0
    later_out = 0.0
    over_in = 0.0
    over_out = 0.0
    n_in = 0
    n_out = 0
    receipts = []
    payments = []
    for line in lines:
        due = line.date_maturity or line.date
        residual = float(line.amount_residual or 0.0)
        incoming = getattr(line.account_id, _kind) in _recv
        flow = residual if incoming else -residual
        if due >= end:
            if incoming:
                later_in += flow
            else:
                later_out += flow
            continue
        if due < today:
            slot = buckets[0]
        else:
            slot = buckets[1 + (due - monday).days // 7]
        if incoming:
            slot['in'] += flow
            n_in += 1
            if due < today:
                over_in += flow
            elif residual > 0:
                receipts.append(_item(line, due, 'Customer'))
        else:
            slot['out'] += flow
            n_out += 1
            if due < today:
                over_out += flow
            elif residual < 0:
                payments.append(_item(line, due, 'Supplier'))

    week_rows = []
    running = cash_today
    low = None
    for slot in buckets:
        if slot['Week'] == 'Overdue' and not (slot['in'] or slot['out']):
            continue
        running += slot['in'] - slot['out']
        row = {
            'Week': slot['Week'],
            'From': slot['From'],
            'Inflow': round(slot['in'], 2),
            'Outflow': round(slot['out'], 2),
            'Net': round(slot['in'] - slot['out'], 2),
            'Balance': round(running, 2),
        }
        week_rows.append(row)
        if low is None or row['Balance'] < low['Balance']:
            low = row
    total_in = sum(r['Inflow'] for r in week_rows)
    total_out = sum(r['Outflow'] for r in week_rows)
    receipts = sorted(receipts, key=lambda r: -r['Amount'])[:10]
    payments = sorted(payments, key=lambda r: -r['Amount'])[:10]

    _kpis = [
        {'Metric': 'Cash today', 'Value': round(cash_today, 2), 'Format': 'money',
         'Hint': 'bank and cash accounts'},
        {'Metric': 'Expected inflows', 'Value': round(total_in, 2), 'Format': 'money',
         'Hint': '%d open customer items' % n_in},
        {'Metric': 'Expected outflows', 'Value': round(total_out, 2), 'Format': 'money',
         'Hint': '%d open supplier items' % n_out},
        {'Metric': 'Overdue receivables', 'Value': round(over_in, 2), 'Format': 'money',
         'Hint': 'due before today'},
        {'Metric': 'Overdue payables', 'Value': round(over_out, 2), 'Format': 'money',
         'Hint': 'due before today'},
        {'Metric': 'Lowest balance', 'Value': low['Balance'] if low else None,
         'Format': 'money', 'Hint': low['Week'] if low else ''},
        {'Metric': 'Balance at the horizon', 'Value': round(running, 2), 'Format': 'money',
         'Hint': '%d weeks ahead' % _weeks},
        {'Metric': 'Beyond the horizon', 'Value': round(later_in - later_out, 2),
         'Format': 'money', 'Hint': 'net of items due later'},
    ]
    _meta = [{
        'Company': _company.name or '',
        'Currency': _company.currency_id.name or '',
        'Locale': _lang,
        'Generated': today.isoformat(),
        'Low week': low['Week'] if low else '',
    }]
    _blocks = [
        {'title': _T_META, 'data': _meta},
        {'title': _T_KPI, 'data': _kpis},
        {'title': _T_WEEKS, 'data': week_rows},
        {'title': _T_IN, 'data': receipts},
        {'title': _T_OUT, 'data': payments},
    ]

_page_template = r'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cash forecast</title>
<style>
:root{--bg:#f4f7f6;--card:#fff;--ink:#0f172a;--mute:#64748b;--line:#e3e9ec;--grid:rgba(15,23,42,.07);--axis:rgba(15,23,42,.25);--in:#10b981;--out:#f43f5e;--bal:#4f46e5;--bal-ink:#4f46e5;--warn:#f59e0b;--warn-ink:#b45309;--dot:#fff;--below:rgba(244,63,94,.06);--tag:rgba(245,158,11,.16);--late:rgba(244,63,94,.14);--late-ink:#be123c;--low:rgba(79,70,229,.08);--shadow:0 1px 2px rgba(15,23,42,.04),0 10px 30px rgba(15,23,42,.07)}
html[data-theme="dark"]{--bg:#081316;--card:#0f1e22;--ink:#e6eef0;--mute:#93a6ad;--line:#1d3036;--grid:rgba(255,255,255,.07);--axis:rgba(255,255,255,.25);--in:#34d399;--out:#fb7185;--bal:#818cf8;--bal-ink:#a5b4fc;--warn-ink:#fbbf24;--dot:#0f1e22;--below:rgba(251,113,133,.09);--tag:rgba(245,158,11,.2);--late:rgba(251,113,133,.2);--late-ink:#fda4af;--low:rgba(129,140,248,.14);--shadow:0 0 0 1px rgba(255,255,255,.03),0 10px 30px rgba(0,0,0,.35)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:1260px;margin:0 auto;padding:24px 20px 40px}
.hero{position:relative;overflow:hidden;border-radius:22px;padding:28px 30px;color:#fff;background:radial-gradient(900px 260px at 90% -30%,rgba(255,255,255,.22),transparent 60%),linear-gradient(120deg,#047857 0%,#0f766e 50%,#1e40af 100%);box-shadow:var(--shadow);display:flex;justify-content:space-between;align-items:flex-end;gap:20px;flex-wrap:wrap}
.hero h1{margin:0;font-size:28px;letter-spacing:-.02em;font-weight:750}
.hero .sub{margin-top:6px;opacity:.85}
.hero .big{text-align:right}
.hero .big .l{font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.8}
.hero .big .v{font-size:34px;font-weight:800;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:15px 17px;box-shadow:var(--shadow);animation:rise .5s ease both}
.kpi .l{color:var(--mute);font-size:12px;text-transform:uppercase;letter-spacing:.06em;font-weight:600}
.kpi .v{font-size:23px;font-weight:750;letter-spacing:-.02em;margin-top:6px;font-variant-numeric:tabular-nums}
.kpi .h{color:var(--mute);font-size:12px;margin-top:2px}
.kpi.neg .v{color:var(--out)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media (max-width:960px){.grid{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px 20px;box-shadow:var(--shadow);animation:rise .6s ease both;min-width:0}
.card h2{margin:0 0 12px;font-size:15px;font-weight:700}
.full{grid-column:1/-1}
.legend{display:flex;gap:16px;color:var(--mute);font-size:12px;margin:-4px 0 6px;flex-wrap:wrap}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.items{display:grid;gap:8px}
.it{display:grid;grid-template-columns:1fr auto;gap:4px 12px;padding:10px 12px;border:1px solid var(--line);border-radius:12px;position:relative;overflow:hidden}
.it .bg{position:absolute;inset:0 auto 0 0;opacity:.09;transform-origin:left;animation:grow .9s cubic-bezier(.2,.8,.2,1) both}
.it .p{font-weight:650;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;position:relative}
.it .a{font-weight:750;font-variant-numeric:tabular-nums;text-align:right;position:relative}
.it .m{grid-column:1/-1;color:var(--mute);font-size:12px;position:relative;display:flex;gap:10px;flex-wrap:wrap}
.it a{color:inherit;text-decoration:none}.it a:hover{text-decoration:underline}
.tag{display:inline-block;padding:0 8px;border-radius:99px;font-size:11px;font-weight:700;background:var(--tag);color:var(--warn-ink)}
.tag.late{background:var(--late);color:var(--late-ink)}
.tw{overflow:auto}
table.t{width:100%;border-collapse:separate;border-spacing:0;font-size:13px}
table.t th{text-align:right;color:var(--mute);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.05em;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
table.t th:first-child,table.t th:nth-child(2),table.t td:first-child,table.t td:nth-child(2){text-align:left}
table.t td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
table.t tr.low td{background:var(--low)}
.pos{color:var(--in)}.neg{color:var(--out)}
.foot{margin-top:18px;color:var(--mute);font-size:12px;text-align:right}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
.bars rect{transition:opacity .15s}.bars g:hover rect{opacity:.8}
.gl{stroke:var(--grid)}.gl0{stroke:var(--axis)}.ax{fill:var(--mute)}.axb{fill:var(--bal-ink)}
.fi{fill:var(--in)}.fo{fill:var(--out)}.below{fill:var(--below)}
.bl{fill:none;stroke:var(--bal)}.dt{fill:var(--bal);stroke:var(--dot)}.dt.lo{fill:var(--warn)}.dt.neg{fill:var(--out)}
.lo-t{fill:var(--warn-ink)}.lo-t.neg{fill:var(--out)}
</style></head>
<body><div class="wrap">
<section class="hero"><div><h1 id="ttl"></h1><div class="sub" id="sub"></div></div><div class="big" id="big"></div></section>
<section class="kpis" id="kpis"></section>
<section class="grid">
<div class="card full" id="c-weeks"><h2></h2><div class="legend" id="lg"></div><div id="chart"></div></div>
<div class="card" id="c-in"><h2></h2><div class="items" id="in"></div></div>
<div class="card" id="c-out"><h2></h2><div class="items" id="out"></div></div>
<div class="card full" id="c-table"><h2></h2><div class="tw" id="table"></div></div>
</section>
<div class="foot" id="foot"></div>
<section id="pns-page-rows"></section>
</div>
<script>
const DATA = [{"title": "_", "data": []}];
const TITLE = "Cash forecast";
(function(){
  var B = {};
  DATA.forEach(function(b){ B[b.title] = b.data || []; });
  var meta = (B['Meta'] || [])[0] || {};
  var LOC = meta.Locale || undefined, CUR = meta.Currency || 'EUR';
  function nf(o){ try { return new Intl.NumberFormat(LOC, o); } catch (e) { return new Intl.NumberFormat(undefined, o); } }
  var money = nf({style:'currency', currency:CUR, maximumFractionDigits:0});
  var compact = nf({style:'currency', currency:CUR, notation:'compact', maximumFractionDigits:1});
  var num = nf({maximumFractionDigits:0});
  function m(v){ return v === null || v === undefined || v === '' ? '\u2014' : money.format(v); }
  function el(tag, cls, text){ var n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; }
  var NS = 'http://www.w3.org/2000/svg';
  function sv(tag, attrs, text){ var n = document.createElementNS(NS, tag); for (var k in attrs) n.setAttribute(k, attrs[k]); if (text !== undefined) n.textContent = text; return n; }
  function card(id, title, rows){
    var c = document.getElementById(id);
    if (!rows || !rows.length) { c.remove(); return null; }
    c.querySelector('h2').textContent = title;
    return c;
  }
  function day(iso){
    if (!/^\d{4}-\d{2}-\d{2}$/.test(iso || '')) return iso || '';
    var d = new Date(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));
    try { return d.toLocaleDateString(LOC, {day:'numeric', month:'short'}); } catch (e) { return iso; }
  }

  document.getElementById('ttl').textContent = TITLE;
  document.title = TITLE;
  document.getElementById('sub').textContent = [meta.Company, meta.Generated].filter(Boolean).join(' \u00b7 ');
  document.getElementById('foot').textContent = [meta.Currency, meta.Locale].filter(Boolean).join(' \u00b7 ');

  var kpis = B['Key figures'] || [];
  var kp = document.getElementById('kpis');
  kpis.forEach(function(r, i){
    if (i === 0) {
      var big = document.getElementById('big');
      big.appendChild(el('div', 'l', r.Metric));
      big.appendChild(el('div', 'v', m(r.Value)));
      return;
    }
    var k = el('div', 'kpi' + (typeof r.Value === 'number' && r.Value < 0 ? ' neg' : ''));
    k.style.animationDelay = (i * 50) + 'ms';
    k.appendChild(el('div', 'l', r.Metric));
    k.appendChild(el('div', 'v', m(r.Value)));
    if (r.Hint) k.appendChild(el('div', 'h', r.Hint));
    kp.appendChild(k);
  });

  var weeks = B['Cash by week'] || [];
  if (card('c-weeks', 'Cash by week', weeks)) {
    var lg = document.getElementById('lg');
    [['Inflow', 'var(--in)'], ['Outflow', 'var(--out)'], ['Balance', 'var(--bal)']].forEach(function(p){
      var s = el('span'); var i = el('i'); i.style.background = p[1]; s.appendChild(i); s.appendChild(document.createTextNode(p[0])); lg.appendChild(s);
    });
    var W = 1200, H = 380, pl = 70, pr = 80, pt = 24, pb = 46, n = weeks.length;
    var iw = W - pl - pr, ih = H - pt - pb;
    var maxF = Math.max.apply(null, weeks.map(function(w){ return Math.max(w.Inflow || 0, w.Outflow || 0); }).concat([1]));
    var bals = weeks.map(function(w){ return w.Balance || 0; });
    var bMin = Math.min.apply(null, bals.concat([0])), bMax = Math.max.apply(null, bals.concat([0]));
    if (bMax === bMin) bMax = bMin + 1;
    var mid = pt + ih / 2;
    function yF(v){ return mid - (ih / 2) * v / maxF; }
    function yB(v){ return pt + ih * (1 - (v - bMin) / (bMax - bMin)); }
    var svg = sv('svg', {viewBox:'0 0 ' + W + ' ' + H, width:'100%', 'class':'bars'});
    var defs = sv('defs', {});
    var ga = sv('linearGradient', {id:'ba', x1:'0', x2:'0', y1:'0', y2:'1'});
    ga.appendChild(sv('stop', {offset:'0', style:'stop-color:var(--bal);stop-opacity:.28'}));
    ga.appendChild(sv('stop', {offset:'1', style:'stop-color:var(--bal);stop-opacity:0'}));
    defs.appendChild(ga); svg.appendChild(defs);
    for (var t = -2; t <= 2; t++) {
      var yv = mid - (ih / 2) * t / 2;
      svg.appendChild(sv('line', {x1:pl, x2:W - pr, y1:yv, y2:yv, 'class':t === 0 ? 'gl0' : 'gl'}));
      svg.appendChild(sv('text', {x:pl - 8, y:yv + 4, 'text-anchor':'end', 'font-size':'11', 'class':'ax'}, compact.format(maxF * t / 2)));
      var bv = bMin + (bMax - bMin) * (t + 2) / 4;
      svg.appendChild(sv('text', {x:W - pr + 8, y:yB(bv) + 4, 'font-size':'11', 'class':'axb'}, compact.format(bv)));
    }
    if (bMin < 0) {
      svg.appendChild(sv('rect', {x:pl, y:yB(0), width:iw, height:Math.max(0, pt + ih - yB(0)), 'class':'below'}));
    }
    var slot = iw / n, bw = Math.min(30, slot * 0.34);
    var pts = [];
    weeks.forEach(function(w, i){
      var cx = pl + slot * i + slot / 2;
      var g = sv('g', {});
      var hi = mid - yF(w.Inflow || 0), ho = yF(-(w.Outflow || 0)) - mid;
      var late = !w.From;
      g.appendChild(sv('rect', {x:cx - bw - 1, y:mid - hi, width:bw, height:Math.max(hi, 0), rx:4, 'class':'fi', opacity:late ? '.55' : '1'}));
      g.appendChild(sv('rect', {x:cx + 1, y:mid, width:bw, height:Math.max(ho, 0), rx:4, 'class':'fo', opacity:late ? '.55' : '1'}));
      g.appendChild(sv('text', {x:cx, y:H - pb + 18, 'text-anchor':'middle', 'font-size':'12', 'font-weight':'650', fill:'currentColor'}, w.Week));
      if (w.From) g.appendChild(sv('text', {x:cx, y:H - pb + 33, 'text-anchor':'middle', 'font-size':'10', 'class':'ax'}, day(w.From)));
      g.appendChild(sv('title', {}, w.Week + (w.From ? ' \u00b7 ' + w.From : '') + '\nInflow ' + m(w.Inflow) + '\nOutflow ' + m(w.Outflow) + '\nNet ' + m(w.Net) + '\nBalance ' + m(w.Balance)));
      svg.appendChild(g);
      pts.push([cx, yB(w.Balance || 0)]);
    });
    var line = pts.map(function(p, i){ return (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join('');
    svg.appendChild(sv('path', {d:line + 'L' + pts[pts.length - 1][0] + ',' + (pt + ih) + 'L' + pts[0][0] + ',' + (pt + ih) + 'Z', fill:'url(#ba)'}));
    var path = sv('path', {d:line, 'class':'bl', 'stroke-width':'3', 'stroke-linejoin':'round', 'stroke-linecap':'round'});
    svg.appendChild(path);
    var lowIdx = bals.indexOf(Math.min.apply(null, bals));
    pts.forEach(function(p, i){
      svg.appendChild(sv('circle', {cx:p[0], cy:p[1], r:i === lowIdx ? 7 : 3.5, 'class':i === lowIdx ? (bals[i] < 0 ? 'dt neg' : 'dt lo') : 'dt', 'stroke-width':'2'}));
    });
    if (lowIdx >= 0) {
      var lp = pts[lowIdx], lx = Math.min(Math.max(lp[0], pl + 60), W - pr - 60);
      svg.appendChild(sv('text', {x:lx, y:Math.max(lp[1] - 14, pt + 10), 'text-anchor':'middle', 'font-size':'12', 'font-weight':'750', 'class':bals[lowIdx] < 0 ? 'lo-t neg' : 'lo-t'}, m(bals[lowIdx])));
    }
    document.getElementById('chart').appendChild(svg);
    try { var len = path.getTotalLength(); path.style.strokeDasharray = len; path.style.strokeDashoffset = len; path.getBoundingClientRect(); path.style.transition = 'stroke-dashoffset 1.4s ease'; path.style.strokeDashoffset = '0'; } catch (e) {}
  }

  function items(id, boxId, title, rows, color){
    if (!card(id, title, rows)) return;
    var box = document.getElementById(boxId);
    var label = Object.keys(rows[0]).filter(function(k){ return k.charAt(0) !== '_'; })[0];
    var max = Math.max.apply(null, rows.map(function(r){ return r.Amount || 0; }).concat([1]));
    rows.forEach(function(r, i){
      var it = el('div', 'it');
      var bg = el('div', 'bg'); bg.style.width = (100 * (r.Amount || 0) / max) + '%'; bg.style.background = color; bg.style.animationDelay = (i * 50) + 'ms'; it.appendChild(bg);
      it.appendChild(el('div', 'p', r[label] || r.Document));
      it.appendChild(el('div', 'a', m(r.Amount)));
      var meta2 = el('div', 'm');
      var doc = el('a', '', r.Document); if (r._id) { doc.href = '/web#id=' + r._id + '&model=account.move&view_type=form'; doc.target = '_blank'; doc.rel = 'noopener'; }
      meta2.appendChild(doc);
      meta2.appendChild(el('span', '', day(r.Due)));
      if (typeof r.Days === 'number') meta2.appendChild(el('span', 'tag' + (r.Days < 0 ? ' late' : ''), (r.Days > 0 ? '+' : '') + num.format(r.Days)));
      it.appendChild(meta2);
      box.appendChild(it);
    });
  }
  items('c-in', 'in', 'Biggest receipts ahead', B['Biggest receipts ahead'] || [], 'var(--in)');
  items('c-out', 'out', 'Biggest payments ahead', B['Biggest payments ahead'] || [], 'var(--out)');

  if (card('c-table', 'Cash by week', weeks)) {
    var keys = Object.keys(weeks[0]).filter(function(k){ return k.charAt(0) !== '_'; });
    var tb = el('table', 't'), hr = el('tr'), th = el('thead');
    keys.forEach(function(k){ hr.appendChild(el('th', '', k)); });
    th.appendChild(hr); tb.appendChild(th);
    var body = el('tbody');
    weeks.forEach(function(w){
      var tr = el('tr', w.Week === meta['Low week'] ? 'low' : '');
      keys.forEach(function(k){
        var v = w[k], td = el('td');
        if (typeof v === 'number') { td.textContent = m(v); if (k === 'Net' || k === 'Balance') td.className = v < 0 ? 'neg' : 'pos'; }
        else td.textContent = v || '';
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
    tb.appendChild(body);
    document.getElementById('table').appendChild(tb);
  }
})();
</script>
</body></html>'''

_page_title = 'Cash forecast'
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
    _kpi_rows = [
        {
            'Metric': row['Metric'],
            'Value': _money(row['Value']) if row['Value'] is not None else '',
            'Note': row['Hint'],
        }
        for row in _kpis
    ]
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
                for b in _blocks[2:] if b['data']
            ],
            'title': _page_title,
        }
    result['__return_direct__'] = True
    result['__stop_after_direct__'] = True
