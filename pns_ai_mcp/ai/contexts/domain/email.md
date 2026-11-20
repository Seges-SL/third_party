---
code: email
tipo: domain
description: Email in Odoo — mail.mail (mailbox) vs mail.notification (delivery)
version: 1.3
---

# Email (mail.mail + mail.notification)

There are **two** models. Mixing them up produces "there are no emails" while the mailbox does show them.

| User question | Model | Useful fields |
|---|---|---|
| Are there emails **to/from** a domain or address? (Sent/Received mailbox) | **`mail.mail`** | `email_to`, `email_from`, `subject`, `state`, `date` / `create_date`, `mail_message_id` |
| Delivery status / bounce? | **`mail.notification`** | `notification_type='email'`, `notification_status`, `mail_message_id`, `res_partner_id` |

**Common trap:** searching only `mail.message` with `partner_ids` / `author_id`.
**Sent** emails usually carry the recipient in `mail.mail.email_to` (text), **without**
filling `mail.message.partner_ids` or `mail.message.email_to`. Result: 0 rows
even though the email UI shows several Sent.

NEVER invent a field named `pns_delivery_status`. If this instance added a
custom tracking field, discover it from `_fields` before using it.

## 1. List emails by address or domain (mailbox)

```python
# PREFERRED for "emails to X / with Y / domain Z"
# Replace DOMAIN_OR_ADDRESS with what the user said (e.g. a domain or an email)
needle = 'DOMAIN_OR_ADDRESS'
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

`state` on **`mail.mail`**: `outgoing` / `sent` / `received` / `exception` / `cancel`
(that is the outgoing queue, not the bounce table).

## 2. Delivery tracking (sent / bounced)

**Model:** `mail.notification`  
**Field:** `notification_status`  
ALWAYS filter `notification_type = 'email'`.

| Value | Meaning |
|-------|---------|
| `ready` | Waiting to be sent |
| `sent` | Sent |
| `bounce` | Bounced |
| `exception` | Sending error |
| `canceled` | Canceled |

```python
[('notification_type', '=', 'email')]
[('notification_type', '=', 'email'), ('notification_status', '=', 'bounce')]
[('notification_type', '=', 'email'), ('notification_status', 'in', ['bounce', 'exception'])]
```

Bridge from a `mail.mail` you found:

```python
msg = mail.mail_message_id  # may be empty
notes = env['mail.notification'].search([
    ('mail_message_id', '=', msg.id),
    ('notification_type', '=', 'email'),
]) if msg else env['mail.notification']
statuses = notes.mapped('notification_status')
```

Open / click tracking is not a standard `mail.message` field. If the user
asked for opens, look for a real field on this instance; do not invent one.

## 3. Count tracking by status over a period

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

## Critical rules

- "Emails with / to / from &lt;contact or domain&gt;" → **`mail.mail`** + `email_to` /
  `email_from` (`ilike`). Do not say "there are none" without searching there.
- Send / bounce tracking → **`mail.notification`** + `notification_status`
  (never an invented field on `mail.message`).
- Do NOT rely only on `partner_ids` / `author_id` to conclude there is no email with
  an external recipient.
- A notification may not exist if the email did not go through the Odoo bus.
