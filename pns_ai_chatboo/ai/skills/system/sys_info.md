---
skill: sys-info
name: System information
description: Odoo version, series, database, server time, current user and company, user/company/module counts, and base URL.
agent_codes:
version: 1.4
args_policy: none
sequence: 20
active: true
context_codes:
---
[SYS-INFO]
Use when the user asks for system information, the Odoo version, server
status, server time or an environment summary.

WHAT IT DOES
Runs the skill code and returns a Property/Value table with read-only
system facts.

HOW TO PRESENT THE RESULT
- Show the table exactly as the code returns it.
- Optional: 1–2 summary sentences (version and current user/company).
- Do not invent values that are not in the table.
