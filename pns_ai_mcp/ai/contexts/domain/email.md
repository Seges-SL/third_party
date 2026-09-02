---
code: email
tipo: domain
description: Correos en Odoo — mail.mail (bandeja enviados/recibidos) vs mail.message (tracking pns_delivery_status)
version: 1.1
---

# Correos electrónicos (mail.mail + mail.message)

Hay **dos** modelos. Mezclarlos produce “no hay correos” cuando la bandeja sí los muestra.

| Pregunta del usuario | Modelo | Campos útiles |
|---|---|---|
| ¿Hay correos **a/desde** un dominio o dirección? (bandeja Enviados/Recibidos) | **`mail.mail`** | `email_to`, `email_from`, `subject`, `state`, `date` / `create_date`, `mail_message_id` |
| ¿Estado de entrega/apertura/rebote? | **`mail.message`** | `message_type='email'`, `pns_delivery_status`, `date`, `email_from` |

**Trampa habitual:** buscar solo en `mail.message` con `partner_ids` / `author_id`.
Los **enviados** suelen tener el destinatario en `mail.mail.email_to` (texto), **sin**
rellenar `mail.message.partner_ids` ni `mail.message.email_to`. Resultado: 0 filas
aunque la UI de correos muestre varios Enviados.

## 1. Listar correos por dirección o dominio (bandeja)

```python
# PREFERRED for “correos a X / con Y / dominio Z”
# Sustituir DOMINIO/DIRECCION por lo que diga el usuario (p.ej. dominio o email)
needle = 'DOMINIO_O_DIRECCION'
mails = env['mail.mail'].search([
    '|',
    ('email_to', 'ilike', needle),
    ('email_from', 'ilike', needle),
], order='id desc', limit=50)
result = [{
    'id': m.id,
    'date': str(m.date or m.create_date),
    'subject': m.subject,
    'email_from': m.email_from,
    'email_to': m.email_to,
    'state': m.state,
    'message_id': m.mail_message_id.id if m.mail_message_id else None,
} for m in mails]
```

`state` en **`mail.mail`**: `outgoing` / `sent` / `received` / `exception` / `cancel`
(no confundir con `pns_delivery_status`).

## 2. Tracking de entrega (apertura / rebote)

**Modelo:** `mail.message`  
**Campo:** `pns_delivery_status` (Char)  
Filtrar SIEMPRE `message_type = 'email'`.

| Valor | Significado |
|-------|-------------|
| `sent` | Enviado |
| `opened` | Abierto |
| `clicked` | Clic en enlace |
| `bounced` | Rebotado |
| `error` | Error de envío |

```python
[('message_type', '=', 'email')]
[('message_type', '=', 'email'), ('pns_delivery_status', '=', 'opened')]
[('message_type', '=', 'email'), ('pns_delivery_status', 'in', ['bounced', 'error'])]
```

Puente desde un `mail.mail` encontrado:

```python
msg = mail.mail_message_id  # puede ser vacío
status = msg.pns_delivery_status if msg else None
```

## 3. Contar tracking por estado en un periodo

```python
start_date = date(date.today().year, date.today().month, 1).strftime('%Y-%m-%d')
end_date = date.today().strftime('%Y-%m-%d')
lines = env['mail.message'].search([
    ('message_type', '=', 'email'),
    ('date', '>=', start_date),
    ('date', '<=', end_date),
    ('pns_delivery_status', '!=', False),
])
counts = {}
for m in lines:
    v = m.pns_delivery_status
    counts[v] = counts.get(v, 0) + 1
result = counts
```

## Reglas críticas

- “Correos con / a / de &lt;contacto o dominio&gt;” → **`mail.mail`** + `email_to` /
  `email_from` (`ilike`). No digas “no hay” sin haber buscado ahí.
- Tracking abierto/rebote → **`mail.message`** + `pns_delivery_status` (nunca
  `mail.message.state`).
- NO uses solo `partner_ids` / `author_id` para concluir que no hay correo con
  un destinatario externo.
- `pns_delivery_status` puede estar vacío en mensajes no rastreados.
