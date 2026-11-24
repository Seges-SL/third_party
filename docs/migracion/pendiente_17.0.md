# Pendiente de migración a 17.0

Notas para migrar a la 17 a los clientes que vienen de la 14, encontradas mientras se trabaja en otras ramas.

## Vistas de los clientes con `attrs` que heredan de `pns_*`

- **Fecha:** 24/11/2026.
- **Origen:** rama `17.0-pns-ai`, `docs/pendiente/fase1_pns_ai_17_3996.md`, etapa F1.1 (caso 3, sección 3).
- **Qué:** el parche de vistas de `pns_base` convierte `attrs` solo en las vistas con xml_id `pns*` o con una pista
  en el nombre o el modelo (`'pns'`, `'inherit.mcp'`, `'ai.'`, `'mcp.'`, `'relaxaicode'`):
  - no convierte las vistas sin xml_id que crearon los clientes en la 14 heredando de una `pns_*`, si no tienen
    pistas;
  - no convierte los `arch_prev` con `attrs` que vienen de la 14 (los usa «Restablecer» en modo `soft`);
  - efecto: la 17 rechaza `attrs` en el arch combinado de una vista, que incluye sus herederas, así que al
    actualizar una `pns_*` en el `-u` de la migración, o al restablecer una vista, puede fallar con «Since 17.0,
    the "attrs" and "states" attributes are no longer used».
- **Estado:** inferido por lectura, no probado.
  - [L] `pns_base/models/ir_ui_view_patch.py`: `_record_is_pns` (`:82-91`) y `_view_vals_look_pns` (`:94-96`)
    deciden la conversión en `_load_records` (`:321-325`) y `create` (`:338-339`); `write` mira solo las pistas
    (`:348-352`) y `_compute_arch`, el xml_id o las pistas (`:372-377`).
  - Core 17 (`17.0-20260908`): rechazo de `//*[@attrs]` en el arch combinado
    (`odoo/addons/base/models/ir_ui_view.py:392-394`, comprobado en el contenedor); `reset_arch('soft')` escribe
    `arch_prev` en `arch_db` (`:297-298`, referencia `/opt/odoo-src/17.0/odoo`).
- **Qué hacer al migrar:** antes del `-u`, buscar en la BD del cliente las vistas con `attrs` en `arch_db` o en
  `arch_prev` que no sean `pns*` y hereden de una `pns_*`, y convertirlas o revisarlas a mano.
- **Módulos:** `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo`.
