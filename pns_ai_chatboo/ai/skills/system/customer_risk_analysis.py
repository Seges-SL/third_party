# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from datetime import date

# Parámetros refinables por `clave=valor` (deterministas; pueden faltar).
try:
    _meses = meses
except NameError:
    _meses = None
if not isinstance(_meses, int) or _meses <= 0:
    _meses = 24
try:
    _min_deuda = min_deuda
except NameError:
    _min_deuda = None
if not isinstance(_min_deuda, (int, float)) or _min_deuda < 0:
    _min_deuda = 0.0
try:
    _top = top
except NameError:
    _top = None
if not isinstance(_top, int) or _top <= 0:
    _top = 30

today = date.today()
# Retroceder _meses desde el primer día del mes actual.
_base = today.year * 12 + (today.month - 1) - _meses
cutoff = date(_base // 12, _base % 12 + 1, 1)

# 1. Obtener todas las facturas de clientes (posted)
invoices = env['account.move'].search([
    ('move_type', 'in', ['out_invoice', 'out_refund']),
    ('state', '=', 'posted'),
    ('invoice_date', '>=', str(cutoff)),
])

# Detectar el campo de cuenta de cobro según la versión de Odoo:
# Odoo 17+ usa account_id.account_type='asset_receivable';
# Odoo 14 usa account_id.user_type_id.type='receivable'.
try:
    env['account.move.line'].search(
        [('account_id.account_type', 'in', ['asset_receivable'])], limit=1)
    recv_leaf = ('account_id.account_type', 'in', ['asset_receivable'])
except Exception:
    recv_leaf = ('account_id.user_type_id.type', '=', 'receivable')

# 2. Agrupar por cliente
by_partner = {}
for inv in invoices:
    pid = inv.partner_id.id
    if not pid:
        continue
    if pid not in by_partner:
        by_partner[pid] = {
            'name': inv.partner_id.name,
            'vat': inv.partner_id.vat or '',
            'total': 0, 'paid': 0, 'pending': 0,
            'amount_paid': 0.0, 'amount_pending': 0.0,
            'dso_days': [], 'months_paid': set(),
            'last_payment': None, 'on_time': 0,
            'late': 0,
        }
    p = by_partner[pid]
    p['total'] += 1
    if inv.payment_state == 'paid':
        p['paid'] += 1
        p['amount_paid'] += inv.amount_total
        # DSO: días entre invoice_date y fecha de pago
        if inv.invoice_date and inv.invoice_date_due:
            # Aproximamos fecha pago como invoice_date_due si está pagada
            # (Odoo no siempre guarda fecha exacta de pago en account.move)
            pay_lines = env['account.move.line'].search([
                ('move_id', '=', inv.id),
                recv_leaf,
                ('reconciled', '=', True),
            ], limit=1)
            if pay_lines and pay_lines.date:
                pay_date = pay_lines.date
                dso = (pay_date - inv.invoice_date).days
                if dso >= 0:
                    p['dso_days'].append(dso)
                # Recency
                if p['last_payment'] is None or pay_date > p['last_payment']:
                    p['last_payment'] = pay_date
                # Dispersión temporal
                p['months_paid'].add((pay_date.year, pay_date.month))
                # Cumplimiento vencimiento
                if inv.invoice_date_due:
                    if pay_date <= inv.invoice_date_due:
                        p['on_time'] += 1
                    else:
                        p['late'] += 1
    elif inv.payment_state in ('not_paid', 'partial'):
        p['pending'] += 1
        p['amount_pending'] += inv.amount_residual

# 3. Calcular score compuesto
result = []
for pid, p in by_partner.items():
    if p['amount_pending'] <= 0 and p['paid'] == 0:
        continue

    # --- Criterio 1: Ratio de pago (25%) ---
    ratio = (p['paid'] / p['total'] * 100) if p['total'] > 0 else 0
    score_ratio = min(ratio, 100)

    # --- Criterio 2: DSO medio (20%) ---
    dso_medio = sum(p['dso_days']) / len(p['dso_days']) if p['dso_days'] else 999
    if dso_medio <= 30:
        score_dso = 100
    elif dso_medio <= 60:
        score_dso = 75
    elif dso_medio <= 90:
        score_dso = 40
    else:
        score_dso = 10

    # --- Criterio 3: Dispersión temporal (15%) ---
    dispersion = len(p['months_paid']) / _meses * 100
    score_dispersion = min(dispersion, 100)

    # --- Criterio 4: Volumen monetario pagado (15%) ---
    # Se normaliza respecto al máximo del dataset (se calcula después)
    vol_paid = p['amount_paid']

    # --- Criterio 5: Recency (15%) ---
    if p['last_payment']:
        days_since = (today - p['last_payment']).days
        if days_since <= 30:
            score_recency = 100
        elif days_since <= 90:
            score_recency = 75
        elif days_since <= 180:
            score_recency = 50
        elif days_since <= 365:
            score_recency = 25
        else:
            score_recency = 5
    else:
        score_recency = 0

    # --- Criterio 6: Cumplimiento vencimiento (10%) ---
    total_pagadas = p['on_time'] + p['late']
    score_cumplimiento = (p['on_time'] / total_pagadas * 100) if total_pagadas > 0 else 0

    result.append({
        'pid': pid,
        'name': p['name'],
        'vat': p['vat'],
        'total_fact': p['total'],
        'paid_fact': p['paid'],
        'pending_fact': p['pending'],
        'amount_pending': p['amount_pending'],
        'amount_paid': p['amount_paid'],
        'dso_medio': round(dso_medio if dso_medio < 999 else 0, 1),
        'dispersion': round(len(p['months_paid']) / _meses * 100, 1),
        'ratio_pago': round(ratio, 1),
        'score_ratio': score_ratio,
        'score_dso': score_dso,
        'score_dispersion': score_dispersion,
        'vol_paid': vol_paid,
        'score_recency': score_recency,
        'score_cumplimiento': score_cumplimiento,
    })

# 4. Normalizar volumen monetario respecto al máximo
max_vol = max((r['vol_paid'] for r in result), default=1)
for r in result:
    score_vol = (r['vol_paid'] / max_vol * 100) if max_vol > 0 else 0
    # Score final ponderado
    score = (
        r['score_ratio']       * 0.25 +
        r['score_dso']         * 0.20 +
        r['score_dispersion']  * 0.15 +
        score_vol              * 0.15 +
        r['score_recency']     * 0.15 +
        r['score_cumplimiento']* 0.10
    )
    r['score'] = round(score, 1)
    # Etiqueta
    if score >= 80:
        r['fiabilidad'] = '🟢 Premium'
        r['_row_color'] = '#e8f5e9'
        r['_color_score'] = '#2e7d32'
    elif score >= 60:
        r['fiabilidad'] = '🟡 Fiable'
        r['_row_color'] = '#fffde7'
        r['_color_score'] = '#f9a825'
    elif score >= 40:
        r['fiabilidad'] = '🟠 Con Riesgo'
        r['_row_color'] = '#fff3e0'
        r['_color_score'] = '#e65100'
    elif score >= 20:
        r['fiabilidad'] = '🔴 Problemático'
        r['_row_color'] = '#fde8e8'
        r['_color_score'] = 'red'
    else:
        r['fiabilidad'] = '⛔ Bloqueado'
        r['_row_color'] = '#f3e5f5'
        r['_color_score'] = '#6a1b9a'
    # Limpiar campos internos
    del r['pid'], r['score_ratio'], r['score_dso']
    del r['score_dispersion'], r['vol_paid'], r['score_recency']
    del r['score_cumplimiento']

# 5. Ordenar por importe pendiente desc, filtrar por deuda mínima
result = [r for r in result if r['amount_pending'] > _min_deuda]
result = sorted(result, key=operator.itemgetter('amount_pending'), reverse=True)
result = result[:_top]

# 6. Renombrar columnas para presentación
final = []
for r in result:
    final.append({
        'Cliente': r['name'],
        'NIF': r['vat'],
        'F.Pend.': r['pending_fact'],
        'Deuda €': r['amount_pending'],
        'F.Pagadas': r['paid_fact'],
        'Ratio %': r['ratio_pago'],
        'DSO días': r['dso_medio'],
        'Dispersión %': r['dispersion'],
        'Score': r['score'],
        'Fiabilidad': r['fiabilidad'],
        '_row_color': r.get('_row_color', ''),
        '_color_Score': r.get('_color_score', ''),
    })
result = {
    'data': final,
    '__return_direct__': True,
    '__stop_after_direct__': True,
}
