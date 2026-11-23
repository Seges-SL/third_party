---
skill: pipeline
name: Sales pipeline
description: Live CRM pipeline page: funnel by stage, weighted forecast by close month, salesperson leaderboard, win rate and stalled deals.
agent_codes: pns_ai_chatboo
version: 1.1
param_schema: {"team": {"type": "string", "desc": "Sales team name or part of it. Empty = every team."}, "salesperson": {"type": "string", "desc": "Salesperson name or part of it. Empty = everyone."}, "stalled_days": {"type": "integer", "desc": "Days without a stage change before a deal counts as stalled.", "default": 21}}
arg_hint: team=… salesperson=… stalled_days=21
args_policy: default
sequence: 50
active: true
context_codes:
---
[PIPELINE]
Use when the user asks for the sales pipeline, the CRM funnel, the sales
forecast, open opportunities, win rate or deals that are stuck (/pipeline).

WHAT IT DOES
Reads the open CRM opportunities of the active company (the asking user's
access) and opens one page: key figures, funnel by stage, weighted forecast
by expected close month, pipeline by salesperson and stalled deals. Outside
Chatboo the same figures come back as tables.

PARAMETERS (sandbox; may be None)
- team: sales team name or part of it. Empty = every team.
- salesperson: salesperson name or part of it. Empty = everyone.
- stalled_days: days without a stage change before a deal is stalled
  (default 21).

HOW TO PRESENT THE RESULT
- The page is the answer. Do not repeat its figures in prose.
- If the result says no team or salesperson matches, say so; do not guess.

METHODOLOGY (informative; the code is authoritative)
- Open = opportunity, active, not in a won stage, probability below 100.
- Weighted = expected revenue × probability.
- Win rate (12 months) = won / (won + lost) by closing date. Lost = archived
  with probability 0.
- Stalled = last stage change (or last edit) older than stalled_days.
