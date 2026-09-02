---
skill: financial-health
name: Financial health
description: Narrative financial situation report (JYDY-14): KPIs, liquidity, debts, collections, ratios, facilities; configurable period.
agent_codes: pns_ai_chatboo
version: 2.14
painter: painter-free
param_schema: {"periodo": {"type": "string", "desc": "Canonical period ONLY: null/empty, ytd, integer 1-60 (= last N months), YYYY, YYYY-YYYY, or YYYY-MM. Convert NL like 'últimos dos años'/'last 2 years' → '24'. Never return prose."}}
arg_hint: ytd | 12 | 2025 | 2024-2025 | 2025-03 | ?
args_policy: default
sequence: 44
active: true
context_codes:
---
[FINANCIAL-HEALTH]
Use with /financial-health (Spanish twin: /analisis-financiero).

FIGURES / TABLES = code_body (deterministic; engine paints HTML).
NARRATIVE = you (LLM) with a FIXED skeleton — no Markdown tables.
Params: deterministic first; `param_schema` enables ONE AI extraction only when
free text leaves the period unresolved (NL → canonical token).
`?` / help / ayuda / options → engine already painted HTML; do not rewrite.
JSON includes `report_outline` + `closing_required`: follow them literally.

SINGLE TEMPORAL SCOPE: the JSON period (`PERIOD` / label / titles) applies to EVERY
table and the narrative. Do NOT say «YTD» unless the label is actually YTD.

TITLE: the FIRST line of the report is a single H1 (`# …`) that you write from
the period (do not copy `PERIOD=` or the technical summary). Shape examples
(adapt N / year / range): `# Financial health over the last 12 months`;
`# Financial health YTD 2026`; `# Financial health for 2025`;
`# Financial health for 2024–2025`.
Immediately BELOW the H1, if JSON has `company`, write that name AS-IS
(from the active Odoo company; do not translate it or add an
«Empresa»/«Company» label).

ARGS (fixed; copy literally after the slash)
- empty → last **12 months** (default)
- ytd · N (1–60) · YYYY · YYYY-YYYY · YYYY-MM
- free text (e.g. «last two years») → AI → canonical token
- ? | help | ayuda | options → HTML help (never AI)

FIXED SKELETON (after the H1; copy these headings EVERY time, in this order; = `report_outline`):
## Analysis
### Strengths
### Weaknesses and risks
### Liquidity and debts
### Credit facilities
## Conclusion
## Recommendations

Under **Recommendations** (ALWAYS the last section; never omit):
- 2–4 concrete action bullets with figures.
- Close with exactly: `Recommended action line: …`
  (If nothing urgent: `Recommended action line: no urgent action; keep monitoring.`)
Lead with the few material facts (what changed, what is tight, what to do).
Do not inventory every JSON table or list every line item; the HTML tables
already show the figures. Cite a number only when it supports the judgment.
If a skeleton heading has nothing material, one short sentence is enough.
No pipe tables (HTML already). No invented chart buttons.
