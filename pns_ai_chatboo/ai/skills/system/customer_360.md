---
skill: customer-360
name: Customer 360
description: One-page customer view across apps: profile, health score, revenue by month, open and overdue invoices, CRM opportunities, meetings, planned activities and the latest messages.
agent_codes: pns_ai_chatboo
version: 1.1
param_schema: {"customer": {"type": "string", "desc": "Customer name, VAT or email, or part of it. Never invent one.", "required": true}}
arg_hint: customer name, VAT or email
args_policy: ask
sequence: 52
active: true
context_codes:
---
[CUSTOMER-360]
Use when the user asks for everything about one customer, a customer
overview or profile, how a customer is doing, or a briefing before meeting
a customer (/customer-360 <name>).

WHAT IT DOES
Finds the customer (name, VAT or email; the company of a contact) and opens
one page with what the asking user can read: profile, health score, revenue
for the last 24 months, open and overdue invoices, open opportunities,
upcoming and past meetings, planned activities and the latest messages.
Apps that are not installed are left out. Outside Chatboo the same figures
come back as tables.

PARAMETERS (sandbox; may be None)
- customer (required): name, VAT or email, or part of it.

HOW TO PRESENT THE RESULT
- The page is the answer. Do not repeat its figures in prose.
- If several customers match, the page shows the one picked and the others
  under «Other matches». If none matches, say so; never guess.

METHODOLOGY (informative; the code is authoritative)
- Revenue = posted customer invoices minus refunds, untaxed, company
  currency.
- Health score 0–100: payment discipline (40, share of the open balance that
  is not overdue), trend (30, last 12 months against the 12 before) and
  recency (30, days since the last invoice). Healthy ≥ 70, Watch ≥ 40,
  otherwise At risk.
- DSO = open receivable / revenue of the last 12 months × 365.
