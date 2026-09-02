---
skill: credit-facility
name: Credit facilities
description: Month-end drawn (creditor balance) on facility journals; configurable period; PDF-safe month blocks.
agent_codes: pns_ai_chatboo
version: 2.4
arg_hint: ytd | 12 | 2025 | 2024-2025 | 2025-03 | ?
args_policy: ask
sequence: 47
active: true
context_codes:
---
[CREDIT-FACILITY]
Use with /credit-facility (Occidente Spanish twin lives in occ_custom_ai: /occ-polizas).

ARGS
Slash text must reach `periodo` and/or `arguments` unchanged.
`param_schema` enables a light LLM fallback only when free text leaves unresolved keys.
Help/? must arrive as-is (never rewrite into a default period).

PERIOD
- (empty) → ask lightly (do NOT assume 12 months)
- ytd · N (1–60) · YYYY · YYYY-YYYY · YYYY-MM · YYYY-MM list
- ? | help → help card

WHAT IT COMPUTES
Facility journals (póliza / credit facility / P####); drawn = credit−debit at
month-end (+ opening). Wide series split into blocks of 5 months for PDF.

PRESENTATION
code_body forces chart-first (`show_mode=show-chart`): this answer is a
time-series of drawn credit. Show groups as returned. Do not invent
contracted limits.
