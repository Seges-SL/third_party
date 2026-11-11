---
skill: financial-health
name: Financial health
description: A written report on the company's finances over the last N months: sales and purchases against a year earlier, money owed both ways, cash, days to collect and customer concentration.
agent_codes: pns_ai_chatboo
version: 3.0
compose: compose-model
param_schema: {"months": {"type": "integer", "desc": "Last N months up to today, from 1 to 60. A year spoken as a span becomes months (two years = 24).", "default": 12}}
arg_hint: months=24
args_policy: default
sequence: 48
active: true
context_codes:
---
[FINANCIAL-HEALTH]
Use with /financial-health.

THE FIGURES are the code's tables; the server paints them. YOU write the
report on top of them, in the user's language.

TITLE: the first line is one H1 you write from the period, e.g.
`# Financial health over the last 12 months`. Right below it, the `company`
name from the JSON, as it is.

FIXED SKELETON (= `report_outline`, these headings in this order):
## Analysis
### Strengths
### Weaknesses and risks
### Liquidity
## Conclusion
## Recommendations

Lead with the few material facts: what changed, what is tight, what to do.
Do not walk through every table; cite a number only when it supports a
judgment. A heading with nothing material gets one short sentence.

Under Recommendations, always last: two to four concrete bullets with
figures, then the `closing_required` line exactly as the JSON gives it.
No pipe tables and no invented figures.
