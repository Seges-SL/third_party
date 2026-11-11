---
skill: billing
name: Billing by month
description: Posted customer invoices by month as a chart, for the last N months or one calendar year.
agent_codes: pns_ai_chatboo
version: 2.0
param_schema: {"months": {"type": "integer", "desc": "Last N months up to today, from 1 to 60.", "default": 12}, "year": {"type": "integer", "desc": "One calendar year as four digits. null unless the user names a year."}}
arg_hint: months=6 · year=2025
args_policy: default
sequence: 30
active: true
context_codes:
---
[BILLING]
Use with /billing, or when the user asks how much was invoiced per month.

WHAT IT SHOWS
Untaxed amount and number of posted customer invoices per month, for the
active company, drawn as a chart. A year wins over a number of months.

HOW TO PRESENT THE RESULT
- The code already returns the chart. Do not invent figures.
