---
code: sale_order_duplicate_workflow
tipo: domain
description: How to duplicate a sale order and change its lines in two separate steps. Includes how to get the URL of the new order.
version: 1.2
---

# Duplicate a sale order and change its lines

## MANDATORY flow (two separate steps)

NEVER try to duplicate and change lines in a single safe_plan_request chained with $ref.
The ID of the duplicated order is NOT available until the user confirms step 1.

### Step 1 — Duplicate the order
```
op: copy
model: sale.order
id: <original_order_id>
overrides: {}   # no overrides; lines are copied as they are
```
Tell the user to confirm in Odoo to duplicate the order.
Wait for the confirmation. Call safe_plan_status() to get the ID of the new order.

### Step 2 — Change the line quantity
Once you have the ID of the new order (result of step 1):
1. Run relaxaicode to get the line IDs of the new order:
   ```python
   order = env['sale.order'].browse(<new_id>)
   result = [{'line_id': l.id, 'product': l.name, 'qty': l.product_uom_qty} for l in order.order_line]
   ```
2. Propose the write on that line:
   ```
   op: write
   model: sale.order.line
   ids: [<line_id>]
   values: {product_uom_qty: <new_quantity>}
   ```

## URL of the new order

To build the link to the new order, get the host base URL
(do not assume ``ir.config_parameter`` ``web.base.url`` is filled — it can
return 'Unknown').
Build: `<base_url>/web#model=sale.order&id=<new_id>&view_type=form`

## Common mistakes to avoid
- Do NOT chain copy + write in a single safe_plan_request with $ref: the $ref of an op=copy does not resolve the IDs of the child lines.
- Do NOT assume the base URL is in ir.config_parameter.
- Do NOT try to change lines of the ORIGINAL order: always work on the duplicate.
