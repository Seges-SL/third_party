---
skill: dashboard
name: Business dashboard
description: Nine chart cards — team (or journal), top customers and trend for month, quarter and YTD from posted customer invoices.
agent_codes: pns_ai_chatboo
version: 1.4
args_policy: none
sequence: 45
active: true
context_codes:
---
[DASHBOARD]
Use when the user types /dashboard or asks for a business dashboard / KPI overview.

PARAMETERS
No parameters — fine. This skill takes no slash args (`param_schema` omitted).

WHAT IT DOES
Returns nine chart cards (three periods × three views):
- Revenue + invoice count by sales team (`team_id`; journal if the field is missing)
- Top customers by untaxed amount (mix: revenue + invoice count)
- Trend (daily in the current month, monthly in quarter / YTD)

Posted `out_invoice` only. No local BA / acronym catalogs. If account.move is
unavailable, explain.

PRESENTATION
`show_mode=dashboard` (draggable cards) and per-card `show-chart` (data via
"Ver datos"). Short 2–3 sentence summary. Do not invent figures.
