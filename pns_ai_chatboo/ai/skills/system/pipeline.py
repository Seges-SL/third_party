# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Sales pipeline slash skill: funnel, forecast, leaderboard, stalled deals.

Reads the open CRM opportunities of the active company with the asking
user's access. In Chatboo the figures open as one page; elsewhere they come
back as tables.
"""
from datetime import date, datetime, timedelta

try:
    _team = team
except NameError:
    _team = None
_team = str(_team or '').strip()
try:
    _seller = salesperson
except NameError:
    _seller = None
_seller = str(_seller or '').strip()
try:
    _idle = stalled_days
except NameError:
    _idle = None
if not isinstance(_idle, int) or _idle <= 0:
    _idle = 21
try:
    _lang = user_lang
except NameError:
    _lang = None
_lang = str(_lang or env.user.lang or 'en_US').replace('_', '-')

_T_META = 'Meta'
_T_KPI = 'Key figures'
_T_STAGES = 'Funnel by stage'
_T_MONTHS = 'Weighted forecast by close month'
_T_SELLERS = 'Pipeline by salesperson'
_T_STALLED = 'Stalled deals'

today = date.today()
now = datetime.now()
_company = env.company
_cid = _company.id
_symbol = _company.currency_id.symbol or ''
_scope = []
_notice = ''
_blocks = []
_kpis = []


def _money(value):
    try:
        return format_amount(value, symbol=_symbol, decimals=0)
    except NameError:
        return '%.0f %s' % (value or 0.0, _symbol)


def _month_key(day):
    return '%04d-%02d' % (day.year, day.month)


if 'crm.lead' not in env:
    _notice = 'The CRM app is not installed.'
else:
    Lead = env['crm.lead']
    _lf = Lead._fields
    _rev = 'expected_revenue' if 'expected_revenue' in _lf else 'planned_revenue'
    base = [('type', '=', 'opportunity')]
    if 'company_id' in _lf:
        base += ['|', ('company_id', '=', False), ('company_id', '=', _cid)]
    teams = env['crm.team']
    if _team:
        teams = env['crm.team'].search([('name', 'ilike', _team)])
        if teams:
            base.append(('team_id', 'in', teams.ids))
            _scope.append(', '.join(teams.mapped('name')))
        else:
            _notice = 'No sales team matches "%s".' % _team
    if _seller and not _notice:
        sellers = env['res.users'].search([('name', 'ilike', _seller)])
        if sellers:
            base.append(('user_id', 'in', sellers.ids))
            _scope.append(', '.join(sellers.mapped('name')))
        else:
            _notice = 'No salesperson matches "%s".' % _seller

if 'crm.lead' in env and not _notice:
    opens = Lead.search(
        base + [('probability', '<', 100), ('stage_id.is_won', '=', False)],
        limit=5000,
    )
    first = date(today.year, today.month, 1)
    horizon = []
    cursor = first
    for _i in range(6):
        horizon.append(_month_key(cursor))
        cursor = date(cursor.year + cursor.month // 12, cursor.month % 12 + 1, 1)
    months = {}
    stages = {}
    sellers_map = {}
    stalled = []
    total = 0.0
    weighted = 0.0
    for lead in opens:
        amount = float(getattr(lead, _rev) or 0.0)
        prob = float(lead.probability or 0.0)
        part = amount * prob / 100.0
        total += amount
        weighted += part
        stage = lead.stage_id
        skey = stage.name or 'No stage'
        srow = stages.setdefault(skey, {
            'seq': stage.sequence if stage else 9999,
            'n': 0, 'amount': 0.0, 'weighted': 0.0, 'prob': 0.0,
        })
        srow['n'] += 1
        srow['amount'] += amount
        srow['weighted'] += part
        srow['prob'] += prob
        deadline = lead.date_deadline
        if not deadline:
            mkey = 'No date'
        elif deadline < first:
            mkey = 'Past due'
        else:
            mkey = _month_key(deadline)
            if mkey not in horizon:
                mkey = 'Later'
        mrow = months.setdefault(mkey, {'n': 0, 'amount': 0.0, 'weighted': 0.0})
        mrow['n'] += 1
        mrow['amount'] += amount
        mrow['weighted'] += part
        uname = lead.user_id.name or 'Unassigned'
        urow = sellers_map.setdefault(uname, {'n': 0, 'amount': 0.0, 'weighted': 0.0})
        urow['n'] += 1
        urow['amount'] += amount
        urow['weighted'] += part
        moved = (
            getattr(lead, 'date_last_stage_update', None)
            or lead.write_date or lead.create_date
        )
        idle = (now - moved).days if moved else 0
        if idle >= _idle:
            stalled.append({
                'Opportunity': lead.name or '',
                'Customer': lead.partner_id.display_name or '',
                'Stage': skey,
                'Salesperson': uname,
                'Expected': round(amount, 2),
                'Probability': round(prob),
                'Idle days': idle,
                'Last move': moved.date().isoformat() if moved else '',
                '_id': lead.id,
            })

    stage_dom = [('is_won', '=', False)]
    for stage in env['crm.stage'].search(stage_dom, order='sequence, id'):
        stage_team = getattr(stage, 'team_id', None)
        if stage_team and teams and stage_team not in teams:
            continue
        if stage_team and not teams:
            continue
        stages.setdefault(stage.name, {
            'seq': stage.sequence, 'n': 0, 'amount': 0.0,
            'weighted': 0.0, 'prob': 0.0,
        })
    stage_rows = []
    for name in sorted(stages, key=lambda k: (stages[k]['seq'], k)):
        srow = stages[name]
        stage_rows.append({
            'Stage': name,
            'Deals': srow['n'],
            'Expected': round(srow['amount'], 2),
            'Weighted': round(srow['weighted'], 2),
            'Avg probability': round(srow['prob'] / srow['n']) if srow['n'] else 0,
        })

    month_rows = []
    for mkey in ['Past due'] + horizon + ['Later', 'No date']:
        mrow = months.get(mkey)
        if mrow is None and mkey not in horizon:
            continue
        mrow = mrow or {'n': 0, 'amount': 0.0, 'weighted': 0.0}
        month_rows.append({
            'Month': mkey,
            'Deals': mrow['n'],
            'Expected': round(mrow['amount'], 2),
            'Weighted': round(mrow['weighted'], 2),
        })

    seller_rows = []
    for uname in sorted(sellers_map, key=lambda k: -sellers_map[k]['weighted'])[:8]:
        urow = sellers_map[uname]
        seller_rows.append({
            'Salesperson': uname,
            'Deals': urow['n'],
            'Expected': round(urow['amount'], 2),
            'Weighted': round(urow['weighted'], 2),
        })

    stalled_n = len(stalled)
    stalled = sorted(stalled, key=lambda r: -r['Expected'])[:15]

    since = str(today - timedelta(days=365))
    won = Lead.search(base + [
        ('stage_id.is_won', '=', True), ('date_closed', '>=', since),
    ])
    lost_n = Lead.search_count(base + [
        ('active', '=', False), ('probability', '=', 0),
        ('date_closed', '>=', since),
    ])
    won_n = len(won)
    won_amount = sum(float(getattr(w, _rev) or 0.0) for w in won)
    cycles = [
        (w.date_closed - w.create_date).days
        for w in won if w.date_closed and w.create_date
    ]
    rate = round(won_n * 100.0 / (won_n + lost_n), 1) if (won_n + lost_n) else None
    cycle = round(sum(cycles) / len(cycles)) if cycles else None
    share = round(weighted * 100.0 / total) if total else 0

    _kpis = [
        {'Metric': 'Open pipeline', 'Value': round(total, 2), 'Format': 'money',
         'Hint': '%d open deals' % len(opens)},
        {'Metric': 'Weighted forecast', 'Value': round(weighted, 2), 'Format': 'money',
         'Hint': '%d%% of the open pipeline' % share},
        {'Metric': 'Win rate (12 months)', 'Value': rate, 'Format': 'percent',
         'Hint': '%d won, %d lost' % (won_n, lost_n)},
        {'Metric': 'Won (12 months)', 'Value': round(won_amount, 2), 'Format': 'money',
         'Hint': '%d deals' % won_n},
        {'Metric': 'Average days to win', 'Value': cycle, 'Format': 'number',
         'Hint': 'from creation to won'},
        {'Metric': 'Stalled deals', 'Value': stalled_n, 'Format': 'number',
         'Hint': 'no stage change in %d days' % _idle},
    ]
    _meta = [{
        'Company': _company.name or '',
        'Currency': _company.currency_id.name or '',
        'Locale': _lang,
        'Generated': today.isoformat(),
        'Stalled after': _idle,
    }]
    _blocks = [
        {'title': _T_META, 'data': _meta},
        {'title': _T_KPI, 'data': _kpis},
        {'title': _T_STAGES, 'data': stage_rows},
        {'title': _T_MONTHS, 'data': month_rows},
        {'title': _T_SELLERS, 'data': seller_rows},
        {'title': _T_STALLED, 'data': stalled},
    ]

_page_template = r'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sales pipeline</title>
<style>
:root{--bg:#f5f6fb;--card:#fff;--ink:#0f172a;--mute:#64748b;--line:#e5e7f0;--grid:rgba(15,23,42,.07);--acc:#6366f1;--acc2:#8b5cf6;--acc3:#06b6d4;--pos:#10b981;--neg:#f43f5e;--warn:#f59e0b;--soft:rgba(99,102,241,.2);--hover:rgba(99,102,241,.05);--chip:rgba(245,158,11,.14);--chip-ink:#b45309;--hot:rgba(244,63,94,.14);--hot-ink:#be123c;--f1:#4f46e5;--f2:#7c3aed;--f3:#0891b2;--core:rgba(255,255,255,.34);--col:rgba(99,102,241,.06);--shadow:0 1px 2px rgba(15,23,42,.04),0 10px 30px rgba(15,23,42,.07)}
html[data-theme="dark"]{--bg:#0b1020;--card:#131b31;--ink:#e6e9f2;--mute:#94a0b8;--line:#222c47;--grid:rgba(255,255,255,.08);--soft:rgba(129,140,248,.26);--hover:rgba(129,140,248,.08);--chip:rgba(245,158,11,.18);--chip-ink:#fbbf24;--hot:rgba(244,63,94,.2);--hot-ink:#fb7185;--f1:#6366f1;--f2:#8b5cf6;--f3:#06b6d4;--core:rgba(255,255,255,.26);--col:rgba(129,140,248,.09);--shadow:0 0 0 1px rgba(255,255,255,.03),0 10px 30px rgba(0,0,0,.35)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:1260px;margin:0 auto;padding:24px 20px 40px}
.hero{position:relative;overflow:hidden;border-radius:22px;padding:28px 30px;color:#fff;background:radial-gradient(1200px 300px at 10% -40%,rgba(255,255,255,.25),transparent 60%),linear-gradient(120deg,#4f46e5 0%,#7c3aed 55%,#0891b2 100%);box-shadow:var(--shadow)}
.hero h1{margin:0;font-size:28px;letter-spacing:-.02em;font-weight:750}
.hero .sub{margin-top:6px;opacity:.85;font-size:14px}
.hero .glow{position:absolute;right:-60px;top:-60px;width:260px;height:260px;border-radius:50%;background:rgba(255,255,255,.12);filter:blur(2px)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:18px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px 18px;box-shadow:var(--shadow);position:relative;overflow:hidden;animation:rise .5s ease both}
.kpi:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--c,var(--acc))}
.kpi .l{color:var(--mute);font-size:12px;text-transform:uppercase;letter-spacing:.06em;font-weight:600}
.kpi .v{font-size:26px;font-weight:750;letter-spacing:-.02em;margin-top:6px;font-variant-numeric:tabular-nums}
.kpi .h{color:var(--mute);font-size:12px;margin-top:2px}
.grid{display:grid;grid-template-columns:1.25fr 1fr;gap:16px}
@media (max-width:960px){.grid{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px 20px;box-shadow:var(--shadow);animation:rise .6s ease both;min-width:0}
.card h2{margin:0 0 12px;font-size:15px;font-weight:700;letter-spacing:-.01em}
.full{grid-column:1/-1}
svg text{font-family:inherit}
.legend{display:flex;gap:14px;color:var(--mute);font-size:12px;margin:-4px 0 8px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.lb{display:grid;gap:10px}
.lb .row{display:grid;grid-template-columns:150px 1fr auto;gap:10px;align-items:center}
.lb .n{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:600}
.lb .bar{height:12px;border-radius:99px;background:var(--line);overflow:hidden}
.lb .bar span{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,var(--acc),var(--acc3));transform-origin:left;animation:grow .9s cubic-bezier(.2,.8,.2,1) both}
.lb .x{font-variant-numeric:tabular-nums;color:var(--mute);font-size:12px;text-align:right}
.lb .x b{color:var(--ink);font-size:13px}
.tw{overflow:auto}
table.t{width:100%;border-collapse:separate;border-spacing:0;font-size:13px}
table.t th{text-align:left;color:var(--mute);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.05em;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
table.t td{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:middle}
table.t tr:hover td{background:var(--hover)}
table.t .num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
table.t a{color:inherit;text-decoration:none;font-weight:600}
table.t a:hover{color:var(--acc);text-decoration:underline}
.chip{display:inline-block;padding:2px 9px;border-radius:99px;font-weight:700;font-size:12px;background:var(--chip);color:var(--chip-ink)}
.chip.hot{background:var(--hot);color:var(--hot-ink)}
.prob{display:inline-flex;align-items:center;gap:6px}
.prob i{display:inline-block;width:44px;height:6px;border-radius:9px;background:var(--line);overflow:hidden}
.prob i b{display:block;height:100%;background:var(--acc)}
.foot{margin-top:18px;color:var(--mute);font-size:12px;text-align:right}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
.ax{fill:var(--mute)}.gl{stroke:var(--grid)}
.bx{fill:var(--soft)}.bw{fill:var(--acc)}.bw.off{fill:var(--warn)}
.fxw{overflow-x:auto;margin:0 -4px;padding:0 4px}
.fx{--n:1;position:relative;min-width:calc(var(--n) * 128px)}
.fx-row{display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr))}
.fx-c{padding:0 10px;min-width:0;position:relative}
.fx-c+.fx-c{border-left:1px dashed var(--line)}
.fx-top .fx-c{padding-bottom:14px}
.fx-i{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:7px;font-size:11px;font-weight:800;color:#fff;background:var(--sc)}
.fx-name{margin-top:8px;font-weight:700;font-size:14px;letter-spacing:-.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fx-deals{color:var(--mute);font-size:12px;margin-top:1px}
.fx-mid{position:relative;height:190px}
.fx-mid svg{position:absolute;inset:0;width:100%;height:100%;display:block}
.fx-mid .fx-row{position:absolute;inset:0}
.fx-mid .fx-c{display:flex;align-items:center;justify-content:center;transition:background .2s;border-left-color:transparent}
.fx-mid .fx-c:hover{background:var(--col)}
.fx-pct{font-size:13px;font-weight:800;color:#fff;padding:3px 10px;border-radius:99px;background:rgba(15,23,42,.28);backdrop-filter:blur(4px);font-variant-numeric:tabular-nums;box-shadow:0 1px 0 rgba(255,255,255,.25) inset}
.fx-bot .fx-c{padding-top:14px}
.fx-amt{font-size:19px;font-weight:780;letter-spacing:-.02em;font-variant-numeric:tabular-nums;white-space:nowrap}
.fx-w{color:var(--mute);font-size:12px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fx-w b{color:var(--ink);font-weight:650}
.fx-p{display:flex;align-items:center;gap:6px;margin-top:8px;font-size:11px;color:var(--mute);font-variant-numeric:tabular-nums}
.fx-p i{flex:1;height:5px;border-radius:9px;background:var(--line);overflow:hidden;max-width:90px}
.fx-p i b{display:block;height:100%;border-radius:9px;background:var(--sc)}
.fx-band{animation:flow 1s cubic-bezier(.2,.8,.2,1) both;transform-origin:left center}
@keyframes flow{from{clip-path:inset(0 100% 0 0)}to{clip-path:inset(0 0 0 0)}}
.fx-key{display:flex;gap:16px;color:var(--mute);font-size:12px;margin:-4px 0 14px}
.fx-key i{display:inline-block;width:18px;height:8px;border-radius:9px;margin-right:6px;vertical-align:0}
@media print{.fx-band{animation:none}.fxw{overflow:visible}}
</style></head>
<body><div class="wrap">
<section class="hero"><div class="glow"></div><h1 id="ttl"></h1><div class="sub" id="sub"></div></section>
<section class="kpis" id="kpis"></section>
<section class="grid">
<div class="card full" id="c-funnel"><h2></h2><div id="funnel"></div></div>
<div class="card" id="c-months"><h2></h2><div class="legend" id="lg"></div><div id="months"></div></div>
<div class="card" id="c-sellers"><h2></h2><div class="lb" id="sellers"></div></div>
<div class="card full" id="c-stalled"><h2></h2><div class="tw" id="stalled"></div></div>
</section>
<div class="foot" id="foot"></div>
<section id="pns-page-rows"></section>
</div>
<script>
const DATA = [{"title": "_", "data": []}];
const TITLE = "Sales pipeline";
(function(){
  var B = {};
  DATA.forEach(function(b){ B[b.title] = b.data || []; });
  var meta = (B['Meta'] || [])[0] || {};
  var LOC = meta.Locale || undefined, CUR = meta.Currency || 'EUR';
  function nf(o){ try { return new Intl.NumberFormat(LOC, o); } catch (e) { return new Intl.NumberFormat(undefined, o); } }
  var money = nf({style:'currency', currency:CUR, maximumFractionDigits:0});
  var compact = nf({style:'currency', currency:CUR, notation:'compact', maximumFractionDigits:1});
  var num = nf({maximumFractionDigits:0});
  var pct = nf({style:'percent', maximumFractionDigits:1});
  function fmt(v, f){
    if (v === null || v === undefined || v === '') return '\u2014';
    if (typeof v !== 'number') return String(v);
    if (f === 'money') return money.format(v);
    if (f === 'percent') return pct.format(v / 100);
    return num.format(v);
  }
  function el(tag, cls, text){ var n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; }
  var NS = 'http://www.w3.org/2000/svg';
  function sv(tag, attrs, text){ var n = document.createElementNS(NS, tag); for (var k in attrs) n.setAttribute(k, attrs[k]); if (text !== undefined) n.textContent = text; return n; }
  function tip(node, text){ node.appendChild(sv('title', {}, text)); return node; }
  function card(id, title, rows){
    var c = document.getElementById(id);
    if (!rows || !rows.length) { c.remove(); return null; }
    c.querySelector('h2').textContent = title;
    return c;
  }
  function monthLabel(key){
    if (!/^\d{4}-\d{2}$/.test(key)) return key;
    var d = new Date(+key.slice(0, 4), +key.slice(5, 7) - 1, 1);
    try { return d.toLocaleDateString(LOC, {month:'short', year:'2-digit'}); } catch (e) { return key; }
  }

  document.getElementById('ttl').textContent = TITLE;
  document.title = TITLE;
  document.getElementById('sub').textContent = [meta.Company, meta.Generated].filter(Boolean).join(' \u00b7 ');
  document.getElementById('foot').textContent = [meta.Currency, meta.Locale].filter(Boolean).join(' \u00b7 ');

  var colors = ['#6366f1', '#8b5cf6', '#10b981', '#06b6d4', '#f59e0b', '#f43f5e'];
  var kp = document.getElementById('kpis');
  (B['Key figures'] || []).forEach(function(r, i){
    var k = el('div', 'kpi'); k.style.setProperty('--c', colors[i % colors.length]); k.style.animationDelay = (i * 60) + 'ms';
    k.appendChild(el('div', 'l', r.Metric));
    k.appendChild(el('div', 'v', fmt(r.Value, r.Format)));
    if (r.Hint) k.appendChild(el('div', 'h', r.Hint));
    kp.appendChild(k);
  });

  var stages = B['Funnel by stage'] || [];
  if (card('c-funnel', 'Funnel by stage', stages)) {
    var N = stages.length, VH = 200, MID = VH / 2, TOP = 92, FLOOR = 0.14;
    var maxA = Math.max.apply(null, stages.map(function(s){ return s.Expected || 0; }).concat([1]));
    var totalA = stages.reduce(function(a, s){ return a + (s.Expected || 0); }, 0) || 1;
    var outer = stages.map(function(s){ return TOP * (FLOOR + (1 - FLOOR) * (s.Expected || 0) / maxA); });
    var inner = stages.map(function(s, i){ return (s.Expected ? outer[i] * Math.min(1, (s.Weighted || 0) / s.Expected) : 0); });
    function band(h){
      var top = 'M0,' + (MID - h[0]), bot = '';
      h.forEach(function(v, i){
        var x0 = i * 100, a = x0 + 16, b = x0 + 84;
        top += (i ? '' : 'L' + a + ',' + (MID - v)) + 'L' + b + ',' + (MID - v);
        if (i + 1 < N) {
          var w = h[i + 1];
          top += 'C' + (x0 + 100) + ',' + (MID - v) + ' ' + (x0 + 100) + ',' + (MID - w) + ' ' + (x0 + 116) + ',' + (MID - w);
        }
      });
      top += 'L' + (N * 100) + ',' + (MID - h[N - 1]) + 'L' + (N * 100) + ',' + (MID + h[N - 1]);
      for (var i = N - 1; i >= 0; i--) {
        var x0 = i * 100, v = h[i];
        bot += 'L' + (x0 + 84) + ',' + (MID + v) + 'L' + (x0 + 16) + ',' + (MID + v);
        if (i > 0) {
          var w = h[i - 1];
          bot += 'C' + x0 + ',' + (MID + v) + ' ' + x0 + ',' + (MID + w) + ' ' + (x0 - 16) + ',' + (MID + w);
        }
      }
      return top + bot + 'L0,' + (MID + h[0]) + 'Z';
    }
    function hue(i){ var t = N > 1 ? i / (N - 1) : 0; return t < 0.34 ? 'var(--f1)' : t < 0.67 ? 'var(--f2)' : 'var(--f3)'; }
    function row(cls){ var r = el('div', 'fx-row ' + cls); return r; }

    var key = document.createElement('div'); key.className = 'fx-key';
    [['Expected', 'linear-gradient(90deg,var(--f1),var(--f3))'], ['Weighted', 'var(--core)']].forEach(function(p, i){
      var s = el('span'), sw = el('i'); sw.style.background = p[1];
      if (i) sw.style.boxShadow = 'inset 0 0 0 1.5px var(--f2)';
      s.appendChild(sw); s.appendChild(document.createTextNode(p[0])); key.appendChild(s);
    });

    var fx = el('div', 'fx'); fx.style.setProperty('--n', N);
    var head = row('fx-top'), mid = el('div', 'fx-mid'), foot = row('fx-bot'), over = row('');
    var svg = sv('svg', {viewBox:'0 0 ' + (N * 100) + ' ' + VH, preserveAspectRatio:'none', role:'img', 'aria-label':'Funnel by stage'});
    var defs = sv('defs', {}), grad = sv('linearGradient', {id:'fxg', x1:'0', x2:'1', y1:'0', y2:'0'});
    [['0', '--f1'], ['.5', '--f2'], ['1', '--f3']].forEach(function(p){ grad.appendChild(sv('stop', {offset:p[0], style:'stop-color:var(' + p[1] + ')'})); });
    var sheen = sv('linearGradient', {id:'fxs', x1:'0', x2:'0', y1:'0', y2:'1'});
    sheen.appendChild(sv('stop', {offset:'0', style:'stop-color:#fff;stop-opacity:.22'}));
    sheen.appendChild(sv('stop', {offset:'.5', style:'stop-color:#fff;stop-opacity:0'}));
    sheen.appendChild(sv('stop', {offset:'1', style:'stop-color:#000;stop-opacity:.10'}));
    defs.appendChild(grad); defs.appendChild(sheen); svg.appendChild(defs);
    var g = sv('g', {'class':'fx-band'});
    g.appendChild(sv('path', {d:band(outer), fill:'url(#fxg)'}));
    g.appendChild(sv('path', {d:band(outer), fill:'url(#fxs)'}));
    g.appendChild(sv('path', {d:band(inner.map(function(v){ return Math.max(v, 0.6); })), style:'fill:var(--core)'}));
    svg.appendChild(g);
    mid.appendChild(svg);

    stages.forEach(function(s, i){
      var sc = hue(i);
      var h = el('div', 'fx-c'); h.style.setProperty('--sc', sc);
      h.appendChild(el('span', 'fx-i', String(i + 1)));
      var nm = el('div', 'fx-name', s.Stage); nm.title = s.Stage; h.appendChild(nm);
      h.appendChild(el('div', 'fx-deals', num.format(s.Deals || 0) + ' deals'));
      head.appendChild(h);

      var o = el('div', 'fx-c');
      o.title = s.Stage + ' \u00b7 ' + money.format(s.Expected || 0) + ' \u00b7 Weighted ' + money.format(s.Weighted || 0);
      o.appendChild(el('span', 'fx-pct', pct.format((s.Expected || 0) / totalA)));
      over.appendChild(o);

      var f = el('div', 'fx-c'); f.style.setProperty('--sc', sc);
      f.appendChild(el('div', 'fx-amt', money.format(s.Expected || 0)));
      var w = el('div', 'fx-w'); w.appendChild(document.createTextNode('Weighted ')); w.appendChild(el('b', '', money.format(s.Weighted || 0))); f.appendChild(w);
      var p = el('div', 'fx-p'), bar = el('i'), fill = el('b');
      fill.style.width = Math.min(100, s['Avg probability'] || 0) + '%'; bar.appendChild(fill);
      p.appendChild(bar); p.appendChild(document.createTextNode(pct.format((s['Avg probability'] || 0) / 100)));
      f.appendChild(p);
      foot.appendChild(f);
    });
    mid.appendChild(over);
    fx.appendChild(head); fx.appendChild(mid); fx.appendChild(foot);
    var wrap = el('div', 'fxw'); wrap.appendChild(fx);
    var box = document.getElementById('funnel'); box.appendChild(key); box.appendChild(wrap);
  }

  var months = B['Weighted forecast by close month'] || [];
  if (card('c-months', 'Weighted forecast by close month', months)) {
    var lg = document.getElementById('lg');
    [['Expected', 'var(--soft)'], ['Weighted', 'var(--acc)']].forEach(function(p){
      var s = el('span'); var i = el('i'); i.style.background = p[1]; s.appendChild(i); s.appendChild(document.createTextNode(p[0])); lg.appendChild(s);
    });
    var W2 = 640, H2 = 280, pl = 64, pb = 34, pt = 10, n = months.length;
    var maxM = Math.max.apply(null, months.map(function(m){ return m.Expected || 0; }).concat([1]));
    var svg2 = sv('svg', {viewBox:'0 0 ' + W2 + ' ' + H2, width:'100%'});
    for (var t = 0; t <= 4; t++) {
      var yv = pt + (H2 - pt - pb) * (1 - t / 4);
      svg2.appendChild(sv('line', {x1:pl, x2:W2, y1:yv, y2:yv, 'class':'gl'}));
      svg2.appendChild(sv('text', {x:pl - 8, y:yv + 4, 'text-anchor':'end', 'font-size':'11', 'class':'ax'}, compact.format(maxM * t / 4)));
    }
    var slot = (W2 - pl) / n, bw = Math.min(46, slot * 0.62);
    months.forEach(function(m, i){
      var x = pl + slot * i + (slot - bw) / 2, ih = H2 - pt - pb;
      var he = ih * (m.Expected || 0) / maxM, hw = ih * (m.Weighted || 0) / maxM;
      var g = sv('g', {});
      g.appendChild(sv('rect', {x:x, y:H2 - pb - he, width:bw, height:Math.max(he, 0), rx:6, 'class':'bx'}));
      g.appendChild(sv('rect', {x:x + bw * 0.18, y:H2 - pb - hw, width:bw * 0.64, height:Math.max(hw, 0), rx:5, 'class':/^\d/.test(m.Month) ? 'bw' : 'bw off'}));
      g.appendChild(sv('text', {x:x + bw / 2, y:H2 - pb + 18, 'text-anchor':'middle', 'font-size':'11', 'class':'ax'}, monthLabel(m.Month)));
      tip(g, m.Month + ' \u00b7 Deals ' + num.format(m.Deals || 0) + ' \u00b7 Expected ' + money.format(m.Expected || 0) + ' \u00b7 Weighted ' + money.format(m.Weighted || 0));
      svg2.appendChild(g);
    });
    document.getElementById('months').appendChild(svg2);
  }

  var sellers = B['Pipeline by salesperson'] || [];
  if (card('c-sellers', 'Pipeline by salesperson', sellers)) {
    var box = document.getElementById('sellers');
    var maxS = Math.max.apply(null, sellers.map(function(s){ return s.Weighted || 0; }).concat([1]));
    sellers.forEach(function(s, i){
      var r = el('div', 'row');
      r.appendChild(el('div', 'n', s.Salesperson));
      var b = el('div', 'bar'); var f = el('span'); f.style.width = (100 * (s.Weighted || 0) / maxS) + '%'; f.style.animationDelay = (i * 70) + 'ms'; b.appendChild(f); r.appendChild(b);
      var x = el('div', 'x'); x.appendChild(el('b', '', money.format(s.Weighted || 0))); x.appendChild(document.createTextNode(' \u00b7 ' + num.format(s.Deals || 0))); r.appendChild(x);
      box.appendChild(r);
    });
  }

  var stalled = B['Stalled deals'] || [];
  if (card('c-stalled', 'Stalled deals', stalled)) {
    var keys = Object.keys(stalled[0]).filter(function(k){ return k.charAt(0) !== '_'; });
    var numeric = {'Expected':'money', 'Probability':'prob', 'Idle days':'idle'};
    var limit = meta['Stalled after'] || 21;
    var tb = el('table', 't'), th = el('thead'), hr = el('tr');
    keys.forEach(function(k){ var c = el('th', numeric[k] ? 'num' : '', k); hr.appendChild(c); });
    th.appendChild(hr); tb.appendChild(th);
    var body = el('tbody');
    stalled.forEach(function(r){
      var tr = el('tr');
      keys.forEach(function(k){
        var td = el('td', numeric[k] ? 'num' : ''), v = r[k];
        if (k === 'Opportunity' && r._id) { var a = el('a', '', v); a.href = '/web#id=' + r._id + '&model=crm.lead&view_type=form'; a.target = '_blank'; a.rel = 'noopener'; td.appendChild(a); }
        else if (numeric[k] === 'money') td.textContent = money.format(v || 0);
        else if (numeric[k] === 'prob') { var p = el('span', 'prob'); var bar = el('i'); var fill = el('b'); fill.style.width = (v || 0) + '%'; bar.appendChild(fill); p.appendChild(bar); p.appendChild(document.createTextNode(pct.format((v || 0) / 100))); td.appendChild(p); }
        else if (numeric[k] === 'idle') td.appendChild(el('span', 'chip' + (v >= 2 * limit ? ' hot' : ''), num.format(v || 0)));
        else td.textContent = v === null || v === undefined ? '' : String(v);
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
    tb.appendChild(body);
    document.getElementById('stalled').appendChild(tb);
  }
})();
</script>
</body></html>'''

_page_title = 'Sales pipeline' + (' \u00b7 ' + ' \u00b7 '.join(_scope) if _scope else '')
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
        elif row['Format'] == 'percent':
            shown = '%s %%' % value
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
                for b in _blocks[2:] if b['data']
            ],
            'title': _page_title,
        }
    result['__return_direct__'] = True
    result['__stop_after_direct__'] = True
