---
code: email
tipo: domain
description: Correos en Odoo — mail.mail (bandeja) vs mail.notification (entrega)
version: 1.2
---

# Correos electrónicos (mail.mail + mail.notification)

Hay **dos** modelos. Mezclarlos produce “no hay correos” cuando la bandeja sí los muestra.

| Pregunta del usuario | Modelo | Campos útiles |
|---|---|---|
| ¿Hay correos **a/desde** un dominio o dirección? (bandeja Enviados/Recibidos) | **`mail.mail`** | `email_to`, `email_from`, `subject`, `state`, `date` / `create_date`, `mail_message_id` |
| ¿Estado de entrega / rebote? | **`mail.notification`** | `notification_type='email'`, `notification_status`, `mail_message_id`, `res_partner_id` |

**Trampa habitual:** buscar solo en `mail.message` con `partner_ids` / `author_id`.
Los **enviados** suelen tener el destinatario en `mail.mail.email_to` (texto), **sin**
rellenar `mail.message.partner_ids` ni `mail.message.email_to`. Resultado: 0 filas
aunque la UI de correos muestre varios Enviados.

NEVER invent a field named `pns_delivery_status`. If this instance added a
custom tracking field, discover it from `_fields` before using it.

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
(that is the outgoing queue, not the bounce table).

## 2. Tracking de entrega (enviado / rebote)

**Modelo:** `mail.notification`  
**Campo:** `notification_status`  
Filtrar SIEMPRE `notification_type = 'email'`.

| Valor | Significado |
|-------|-------------|
| `ready` | Pendiente de enviar |
| `sent` | Enviado |
| `bounce` | Rebotado |
| `exception` | Error de envío |
| `canceled` | Cancelado |

```python
[('notification_type', '=', 'email')]
[('notification_type', '=', 'email'), ('notification_status', '=', 'bounce')]
[('notification_type', '=', 'email'), ('notification_status', 'in', ['bounce', 'exception'])]
```

Puente desde un `mail.mail` encontrado:

```python
msg = mail.mail_message_id  # puede ser vacío
notes = env['mail.notification'].search([
    ('mail_message_id', '=', msg.id),
    ('notification_type', '=', 'email'),
]) if msg else env['mail.notification']
statuses = notes.mapped('notification_status')
```

Open / click tracking is not a standard `mail.message` field. If the user
asked for opens, look for a real field on this instance; do not invent one.

## 3. Contar tracking por estado en un periodo

```python
start_date = date(date.today().year, date.today().month, 1).strftime('%Y-%m-%d')
end_date = date.today().strftime('%Y-%m-%d')
notes = env['mail.notification'].search([
    ('notification_type', '=', 'email'),
    ('mail_message_id.create_date', '>=', start_date),
    ('mail_message_id.create_date', '<=', end_date),
])
counts = {}
for note in notes:
    v = note.notification_status
    counts[v] = counts.get(v, 0) + 1
result = counts
```

## Reglas críticas

- “Correos con / a / de &lt;contacto o dominio&gt;” → **`mail.mail`** + `email_to` /
  `email_from` (`ilike`). No digas “no hay” sin haber buscado ahí.
- Tracking de envío / rebote → **`mail.notification`** + `notification_status`
  (nunca un campo inventado en `mail.message`).
- NO uses solo `partner_ids` / `author_id` para concluir que no hay correo con
  un destinatario externo.
- Una notificación puede no existir si el correo no pasó por el bus de Odoo.
