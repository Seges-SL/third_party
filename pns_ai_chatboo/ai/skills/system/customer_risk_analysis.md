---
skill: customer-risk-analysis
name: Customer risk analysis
description: Customer collection-risk score from six criteria: payment ratio, DSO, temporal spread, monetary volume, recency and due-date compliance.
agent_codes:
version: 1.6
param_schema: {"meses": {"type": "integer", "desc": "Calendar months to look back (default 24). null if the user does not specify."}, "min_deuda": {"type": "number", "desc": "Minimum outstanding debt in euros to include a customer (default 0). null if not specified."}, "top": {"type": "integer", "desc": "Maximum customers to show, highest debt first (default 30). null if not specified."}}
arg_hint: meses=24 min_deuda=0 top=30
args_policy: default
sequence: 10
active: true
context_codes:
---
[CUSTOMER-RISK-ANALYSIS]
Use when the user asks for customer risk analysis, collection reliability,
customer scoring, overdue debtors or a payment-risk ranking.

WHAT IT DOES
Computes a 0–100 reliability score per customer (by running the skill code)
and returns a table already sorted and labelled by risk level.

PARAMETERS (hybrid; the code reads them from the sandbox)
Slash text is parsed deterministically first (`parse_skill_arguments` +
date enrich). `param_schema` enables a light LLM only when keys stay unresolved.
- meses: analysis window in calendar months (default 24).
- min_deuda: minimum outstanding debt in € (default 0).
- top: customer cap, highest debt first (default 30).

HOW TO PRESENT THE RESULT
- Show the table exactly as the code returns it (keep row and score colours).
- Summarise in 2–3 sentences: blocked/problematic customers and where debt
  concentrates.
- If there are no rows, say so clearly; do not invent customers or figures.

METHODOLOGY (informative; the code is authoritative)
Score 0–100 weighting six criteria: payment ratio, DSO, temporal payment
spread, paid volume, recency and due-date compliance. Labels: Premium /
Reliable / At risk / Problematic / Blocked.
