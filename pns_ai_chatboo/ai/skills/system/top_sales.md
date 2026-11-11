---
skill: top-sales
name: Top sales
description: Asks step by step what to rank (customers, products or salespeople) and how many months back, then charts the top 10 by untaxed sales.
agent_codes: pns_ai_chatboo
version: 1.0
arg_hint: 2 6
args_policy: default
sequence: 40
active: true
context_codes:
---
[TOP-SALES]
Use with /top-sales.

HOW IT TALKS
The code asks one question per turn and keeps what it already knows in
`__skill_state__`. The user answers with a number, without the slash; the
engine hands the state back with that reply. `/top-sales 2 6` answers both
questions at once.

HOW TO PRESENT THE RESULT
- Questions and the final chart come from the code. Do not ask your own
  questions and do not invent figures.
