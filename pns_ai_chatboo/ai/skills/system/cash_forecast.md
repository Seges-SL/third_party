---
skill: cash-forecast
name: Cash forecast
description: Week-by-week cash forecast page from open customer and supplier items by due date: inflows, outflows, running balance, lowest point and the biggest receipts and payments ahead.
agent_codes: pns_ai_chatboo
version: 1.1
param_schema: {"weeks": {"type": "integer", "desc": "Weeks ahead to forecast (1-26).", "default": 12}}
arg_hint: weeks=12
args_policy: default
sequence: 51
active: true
context_codes:
---
[CASH-FORECAST]
Use when the user asks for a cash forecast, treasury forecast, cash flow
ahead, expected receipts and payments, or when the bank balance runs low
(/cash-forecast).

WHAT IT DOES
Starts from today's bank and cash balance and adds the open receivable and
payable items of the active company by due date, week by week. Opens one
page: key figures, inflows and outflows per week with the running balance
and its lowest point, the biggest receipts and payments ahead, and the
weekly table. Outside Chatboo the same figures come back as tables.

PARAMETERS (sandbox; may be None)
- weeks: weeks ahead (default 12, at most 26).

HOW TO PRESENT THE RESULT
- The page is the answer. Do not repeat its figures in prose.
- Overdue items are their own first column: they are what would come in or
  go out if they were settled now. Do not move them into a week.

METHODOLOGY (informative; the code is authoritative)
- Cash today = balance of bank and cash accounts (posted entries).
- Inflows = open residual of receivable items; outflows = open residual of
  payable items; bucketed by due date (weeks start on Monday).
- Items due after the horizon go to «Later» and stay out of the curve.
