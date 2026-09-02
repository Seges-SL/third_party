---
skill: billing
name: Billing by period
description: Posted customer invoice totals for a period (last N months, year, YTD or range); chart-ready table without business-area coupling.
agent_codes: pns_ai_chatboo
version: 1.2
param_schema: {"periodo": {"type": "string", "desc": "Period hint: empty=last 12 months, 1-12=N months, YYYY=year, YYYY-YYYY=range, ytd=year to date. null if absent."}}
arg_hint: ytd
args_policy: default
sequence: 48
active: true
context_codes:
---
[BILLING]
Use when the user types /billing or asks for customer invoicing totals by period.

PARAMETERS
Slash text is parsed deterministically first (`parse_skill_arguments` + date enrich).
`param_schema` enables a light LLM fallback only when free text leaves unresolved keys.

IMPORTANT ARGS
Pass slash text into `periodo` and/or `arguments` unchanged. Help/? must arrive
as-is (never rewrite help into a default 12-month period).

PERIOD
- (empty) → last 12 months
- 1–12 → last N months
- YYYY → full year
- YYYY-YYYY → range
- ytd → current year to date
- ? | help → help text (no query)

PRESENTATION
Returns Month|Amount|Invoice count (time series). code_body forces chart-first
(`show_mode=show-chart`) because this skill answer is a chart — not an LLM
layout pick. Execute code_body as-is. Do not invent figures.
