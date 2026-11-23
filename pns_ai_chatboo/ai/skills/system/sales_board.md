---
skill: sales-board
name: Sales board
description: Movable cards over the last 12 months of sales — key figures, quoted and confirmed by month and by salesperson, top customers, largest open quotations and, with CRM, the pipeline by stage.
agent_codes: pns_ai_chatboo
version: 1.0
args_policy: none
sequence: 46
active: true
context_codes:
---
[SALES-BOARD]
Use with /sales-board, or when the user asks for a sales board or a sales
overview in cards.

WHAT IT SHOWS
Cards built by the code, in the chat (no page, no Design call). Each card
can be dragged by its header, minimized, maximized or closed; Restore puts
the layout back. The layout is kept per browser.

- Key figures: confirmed sales and orders, quoted amount and quotations,
  customers with orders.
- Quoted and confirmed by month (wide card, chart).
- Quoted and confirmed by salesperson (chart).
- Top customers and largest open quotations (tables; each row opens its record).
- Pipeline by stage (chart), only when CRM is installed.

Quoted = draft or sent quotations. Confirmed = confirmed sales orders.
Active company, untaxed, last 12 months. A card with no rows is left out.

HOW TO PRESENT THE RESULT
- Show the cards as the code returns them. Do not invent figures or cards.
