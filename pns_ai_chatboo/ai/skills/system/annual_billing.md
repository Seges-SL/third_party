---
skill: annual-billing
name: Annual billing by week
description: Customer invoicing (posted out_invoice) by ISO week for a year or date range; pastel bar chart by month.
agent_codes: pns_ai_chatboo
version: 2.2
param_schema: {"year": {"type": "integer", "desc": "Calendar year (e.g. 2024). null if the user does not specify one or gives an explicit date range."}, "start_date": {"type": "string", "desc": "Start date YYYY-MM-DD only for an explicit range. null otherwise."}, "end_date": {"type": "string", "desc": "End date YYYY-MM-DD only for an explicit range. null otherwise."}}
arg_hint: year=2024
args_policy: default
sequence: 50
active: true
context_codes:
---
[ANNUAL-BILLING]
Use when the user types /annual-billing or asks for weekly customer billing for a year or range.

WHAT IT DOES
Groups posted customer invoices (out_invoice) by ISO week and renders █ bars
with pastel month backgrounds, legend and total.

PARAMETERS (sandbox; may be None) — hybrid
Slash text is parsed deterministically first (`parse_skill_arguments` + date enrich).
`param_schema` enables a light LLM fallback only when free text leaves unresolved keys.
- year / anio: integer year (deterministic or LLM fallback). Takes priority.
- start_date / end_date: YYYY-MM-DD for an explicit range.
- arguments: raw slash text; if params are empty, years are parsed from text.

If missing, the code_body uses the current calendar year.

EXAMPLES
  /annual-billing
  /annual-billing 2025
  /annual-billing 2024-01-01 2024-06-30
  /annual-billing 2023 2025

PRESENTATION
result = {'formatted_text': html, '__return_direct__': True, '__stop_after_direct__': True}.
Do not invent figures or change the period.
