---
code: sale_order_duplicate_workflow
tipo: domain
description: Procedimiento para duplicar un pedido de venta y modificar sus líneas en dos pasos separados. Incluye cómo obtener la URL del nuevo pedido.
version: 1.0
---

# Duplicar pedido de venta y modificar líneas

## Flujo OBLIGATORIO (dos pasos separados)

NUNCA intentes duplicar y modificar líneas en un solo propose_safe_operations encadenado con $ref.
El ID del pedido duplicado NO está disponible hasta que el usuario confirma el paso 1.

### Paso 1 — Duplicar el pedido
```
op: copy
model: sale.order
id: <id_pedido_original>
overrides: {}   # sin overrides; las líneas se copian tal cual
```
Informa al usuario: "Confirma en Odoo para duplicar el pedido."
Espera confirmación. Llama a get_safe_operation_status() para obtener el ID del nuevo pedido.

### Paso 2 — Modificar la cantidad de la línea
Una vez tengas el ID del nuevo pedido (resultado del paso 1):
1. Ejecuta relaxaicode para obtener los IDs de las líneas del nuevo pedido:
   ```python
   order = env['sale.order'].browse(<nuevo_id>)
   result = [{'line_id': l.id, 'product': l.name, 'qty': l.product_uom_qty} for l in order.order_line]
   ```
2. Propón la escritura sobre la línea concreta:
   ```
   op: write
   model: sale.order.line
   ids: [<line_id>]
   values: {product_uom_qty: <nueva_cantidad>}
   ```

## URL del nuevo pedido

Para construir el enlace al nuevo pedido, obtén la URL base del host
(no asumas que ``ir.config_parameter`` ``web.base.url`` está relleno — puede
devolver 'Unknown').
Construye: `<base_url>/web#model=sale.order&id=<nuevo_id>&view_type=form`

## Errores comunes a evitar
- NO encadenar copy + write en un solo propose_safe_operations con $ref: el $ref de un op=copy no resuelve el ID de las líneas hijas.
- NO asumir que la URL base está en ir.config_parameter.
- NO intentar modificar líneas del pedido ORIGINAL: siempre trabajar sobre el duplicado.
