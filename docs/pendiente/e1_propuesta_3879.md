# Propuesta de la entrega E1′ (base 3.1.879)

- **Rama:** `14.0-pns-ai-3879` · contexto `odoo-dev 14 lab_pns_ai_3879`
- **Fecha:** 23/10/2026
- **Plan:** [plan de corrección sobre 3.1.879](plan_correccion_pns_ai_3879.md), ficha de E1′
- **Datos:** [comparación con 3.1.879](../specs/comparacion_pns_ai_3-1-879.md) (§1.2, §1.3, §2.1, §2.2,
  §3, §4, §8.7, §9.5, §9.6 y §10.1)
- **Registro de parches:** [parches_pns_ai.md](parches_pns_ai.md)
- **Estado:** aprobada con condiciones el 23/10/2026 (ver «Decisiones de Sergio»).

Rutas de `pns_ai_mcp` salvo indicación; líneas de 3.1.879.

## 1. Ficha por ficha

### M10 — ejecutar un plan con la identidad de otro usuario (Crítica)

- **Fallo:** `ai.safe.operation` no sobrescribe `create`; `write` sí está cerrado a `sudo`
  (`models/safe_operation.py:532-537`). El AI Administrator tiene `create`
  (`security/ir.model.access.csv:46`; regla `ai_safe_operation_admin_rule`, `security/security.xml:105-114`)
  y da de alta una operación ya `confirmed` con `confirmed_by_uid`, `user_id` y `operation_data` a su
  elección. `cleanup_stuck_state` (`:1005-1039`) es público, sin grupo y sin llamador en el código (ni
  cron); llama a `_retry_confirmed_not_executed`, que abre un cursor con el uid de `confirmed_by_uid` (o
  `user_id`, `:1056-1064`) y ejecuta y confirma el plan. Segunda vía no citada en la comparación:
  `create_verification` (`:460-526`), público por RPC, acepta un `user_id` cualquiera.
- **Quién:** AI Administrator sin Ajustes (interno y portal no tienen `create`).
- **Cambio mínimo:** sobrescribir `create` con el criterio de `write` (`AccessError` si no `env.su`). El
  alta legítima ya corre como superusuario (`request_safe_plan`, `controllers/safe_plan.py:2198-2222`);
  los tests del fabricante crean con `self.env` / `SUPERUSER_ID` (`su` en Odoo 14). Cierra también
  `create_verification` por RPC, `copy()` e importación. El último recurso `SUPERUSER_ID` de `_retry` es
  inalcanzable (`user_id` es `required`, `ondelete='cascade'`).
- **Test:** `pns_ai_mcp/tests/test_seges_safe_operation.py` (`TransactionCase`, sin cursor propio):
  `test_rpc_create_confirmed_refused`, `test_create_verification_for_other_refused`, `test_copy_refused`,
  `test_system_create_still_works` (control).

### Parche 12 adaptado — solo `base.group_system` da o quita grupos con un plan

- **Fallo:** `_resolve_group_below_cusp` (`models/ai_system_action.py:700-708`), al proponer y al aplicar
  (`:719-775`), solo prohíbe la cúspide. Vía CRUD: `crud_cusp_error` (`utils/privilege_cusp.py:100-137`)
  rechaza los campos de grupos de `res.users` para cualquier grupo, pero en `res.groups` solo frena la
  cúspide: `write` de `users` o `implied_ids` en un grupo normal pasa (requiere escritura en
  `res.groups`, es decir `base.group_erp_manager` sin Ajustes, o la suplantación de M10).
- **Cambio mínimo:** (1) `_check_may_change_user_groups()` del parche 12 al principio de los cuatro
  `_preview_*` / `_apply_*`, antes de `_resolve_group_below_cusp` (la cúspide del fabricante se queda);
  (2) en `crud_cusp_error`, para `res.groups`, mensaje de Seges si `env.user` no es superusuario ni
  tiene `base.group_system` (cubre propuesta, `safe_plan.py:270-273`, y ejecución, `:881-953`, con el
  mismo `PermissionError`).
- **Test:** `pns_ai_mcp/tests/test_seges_user_groups.py` reescrito con `base.group_partner_manager`;
  nuevos `test_settings_admin_refused_on_cusp`, `test_crud_res_groups_refused_without_settings`,
  `test_crud_res_groups_settings_ok`, `test_context_identities_checked`.

### PNS-54 — el token de la tarjeta no frena a un script en la página (Crítica)

- **Fallo:** resto 1, `card_payload(mint_token=True)` (`models/safe_operation.py:2003-2032`) público y sin
  comprobar quién llama; `/pns_ai_mcp/verification/pending` (`controllers/verification_ui.py:142-146`)
  entrega tokens nuevos a la sesión del dueño. Resto 2, `action_confirm_and_execute` /
  `action_execute_plan` (`:1765-1831`) confirman y ejecutan sin token ni espera (dueño o AI Administrator).
- **Quién:** un script inyectado en la página del dueño (o de un AI Administrator).
- **Cambio mínimo:** (a) `action_confirm_and_execute` con `check_identity` de Odoo 14
  (`odoo/addons/base/models/res_users.py:97-132`, contraseña recordada 10 min); (b) `card_payload` solo
  genera token si `self.user_id == self.env.user`; (c) opcional: identidad reciente en
  `/verification/confirm` para `high`.
- **Test:** `pns_ai_mcp/tests/test_seges_verification.py` (`HttpCase`):
  `test_confirm_and_execute_requires_identity`, `test_card_payload_mint_only_owner`.

### PNS-07 — métodos públicos con cursor propio y commit (Crítica)

- **Fallo:** `chatboo.session.fulfill_client_export` (`pns_ai_chatboo/models/chatboo_session.py:541`) →
  `persist_turn_file` → `_run_on_committed_cursor` (`utils/session_download.py:365-392`); el nombre no
  está en `RELAXAICODE_SIDE_EFFECT_METHODS` (`controllers/validators_base.py:233-256`).
- **Quién:** el modelo (inyección de prompt en la Caja A); una skill en su ejecución de prueba.
- **Cambio mínimo:** el nombre a la lista, con marcador.
- **Test:** `pns_ai_chatboo/tests/test_seges_chatboo_export.py` (`TransactionCase`, sin `enter_test_mode`
  ni `HttpCase`), con usuario ya guardado en la BD (si se crea en la transacción del test, el cursor
  propio no lo ve, `_run_on_committed_cursor` cae al entorno del llamador y el defecto se esconde);
  control con llamada directa y comprobación desde un `registry.cursor()` nuevo; limpieza en `finally`.
  Se porta `test_fulfill_client_export_claims_own`.

### M13 — cualquier usuario borra los contextos de fábrica (Alta)

- **Fallo:** `ai.context.unlink_retired_from_module` (`models/ai_context_disk.py:757-796`), `@api.model`,
  sin comprobación, en `sudo` con `skip_hardcoded_restrictions`.
- **Quién:** cualquier autenticado, también portal (P-8a).
- **Cambio mínimo:** renombrar a `_unlink_retired_from_module` (único llamador `:745`, dentro de la
  importación, que exige AI Administrator, `:122`).
- **Test:** `test_seges_rpc_access.py`: entrada en `RENAMED`; `test_unlink_retired_refused` (interno y
  portal, `call_kw` y `/jsonrpc`; recuento sin cambios).

### `collect_pin` — PNS-83, parche 10 adaptado (Alta)

- **Fallo:** `ai.key.pin.ask.collect_pin` (`models/key_pin_desk.py:193-201`) público; `_collect` con cursor
  de superusuario y espera de 20 s (`:21`, `:203-220`).
- **Quién:** cualquier autenticado, también portal (denegación de servicio; clave en claro con el PIN).
- **Cambio mínimo:** renombrar a `_collect_pin`; único llamador `models/mcp_user.py:766`.
- **Test:** `test_seges_rpc_access.py`: entrada en `RENAMED`, `test_collect_pin_refused` (con
  `ASK_WAIT_SECONDS` sustituido), y ampliación de `test_redeem_key_pin_python` (mesa simulada,
  `_collect_pin` → `False`: el intento cuenta).

## 2. Diseño conjunto de M10 y el parche 12

Actor efectivo = la identidad del entorno con el que corre el plan (`self.env.user` en `_apply_*`):

| Vía | Quién la dispara | Identidad del plan |
|---|---|---|
| Tarjeta `/verification/execute` | Dueño | Dueño |
| Autorizaciones (`action_confirm_and_execute`) | Dueño o AI Administrator | Quien confirma |
| Confirmación automática al proponer (`safe_plan.py:2287-2305`) | Quien propone | Quien propone |
| `safe_plan_status` (`:2434-2470`) | Dueño | Dueño |
| `execute_plan_now` por RPC | Dueño o AI Administrator | Quien llama |
| `cleanup_stuck_state` → `_retry` | Quien vea la fila | `confirmed_by_uid`, no quien llama |

Solo la última ejecuta con otra identidad; es fiable cuando `confirmed_by_uid` solo lo escribe quien
confirma de verdad (parche de M10).

- **Vía del plan:** `base.group_system` al proponer (`_preview_*`, quien propone) y al aplicar
  (`_apply_*`, quien ejecuta); además, si vienen en el contexto, `ai_journal_user_id` y
  `ai_journal_confirmed_by_uid` (los pone `execute_plan_now` desde la fila, `:1440-1447`). Solo añaden
  rechazos.
- **Vía CRUD:** en `crud_cusp_error`, con el mismo `env.user`.
- **M10 como parche 13 propio:** otra causa y otro archivo; M10 va más allá de los grupos (P-8b); la
  vigilancia del fabricante es distinta; se revierten por separado. Ninguno basta solo.

## 3. Numeración y commits

| Commit | Parche | Contenido |
|---|---|---|
| 1 | 10 (adaptado, PNS-83) | `collect_pin` → `_collect_pin` |
| 2 | 12 (adaptado, PNS-01/02) | Criterio de Seges, plan y CRUD |
| 3 | 13 (M10) | `create` de `ai.safe.operation` solo para el sistema |
| 4 | 14 (M13) | `_unlink_retired_from_module` |
| 5 | 15 (PNS-07) | Lista del sandbox |
| 6 | 16 (PNS-54) | `check_identity` y token solo para el dueño |
| 7 | — | Tests de E1′ |
| 8 | — | [DOC] registro y plan |

## 4. Validación prevista

- Laboratorio: tests con la línea base de E0′, neutralización de cada parche, lint y `py_compile`.
- Staging `pns_demo`: cambio de base 3.1.782 → 3.1.879 con `-u` (pérdidas de P-9), pruebas P-8b, P-01,
  CRUD en `res.groups`, P-54b, P-07, P-8a, P-83a/b y no regresión del chat y de Autorizaciones.

## Decisiones de Sergio (23/10/2026)

- **Criterio de grupos:** el de Seges, con la cúspide del fabricante dentro.
- **`test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin`:** se acepta como F por diseño (línea base:
  18 F). No se toca; se documenta en [parches_pns_ai.md](parches_pns_ai.md).
- **PNS-54:** se aplican (a) y (b). (c) no se aplica: riesgo aceptado ligado a D29 (requiere antes un XSS
  en la página del dueño); se registra en la ficha de PNS-54 y en D29.
- **Marcadores de M10 y M13:** `Seges: parche N (M10, seguridad)`; la convención pasa a «PNS-XX o el id de
  la comparación».
- **`cleanup_stuck_state`:** pasa a privado (`_cleanup_stuck_state`) dentro del parche 13, si no tiene
  llamadores en JS ni XML.
- **Vía CRUD en `res.groups`:** incluida.
- **Condiciones previas a implementar:** comprobaciones de solo lectura (a) a (e); si alguna cambia el
  diseño, se para y se consulta.

## Resultado de las comprobaciones previas (23/10/2026)

Ninguna cambia el diseño. Detalle en [parches_pns_ai.md](parches_pns_ai.md), «Parches de la rama
14.0-pns-ai-3879 (E1′)».

- **(a)** `create_verification` crea con `self.create` (`models/safe_operation.py:507`), no con
  `sudo()`. El `create` cerrado del parche 13 la cierra también por RPC.
- **(b)** Solo dos sitios crean `ai.safe.operation`, y los dos corren con `su`:
  - `request_safe_plan` (`controllers/safe_plan.py:2198-2222`, `SUPERUSER_ID`);
  - `record_direct_operation` (`controllers/safe_operation.py:240-264`,
    `request.env(user=SUPERUSER_ID)`, sin llamadores).
  - En Odoo 14, uid 1 activa `su` (`odoo/api.py:450-451`).
  - Ningún JS, XML de datos ni migración crea operaciones.
- **(c)** En `static/`, `views/` y `data/` de los tres módulos:
  - `collect_pin`, `cleanup_stuck_state` y `action_execute_plan`: nada;
  - `unlink_retired_from_module`: solo un comentario de `pns_ai_chatboo/data/chatboo_skill_data.xml:6`,
    que habla del método de `ai.skill`;
  - `action_confirm_and_execute`: los dos botones de `views/safe_operation_views.xml:40, 71`.
  - Por tanto, `cleanup_stuck_state` pasa a privado dentro del parche 13.
- **(d)** Inventario de PNS-07: 28 métodos públicos llegan a un cursor propio y van a la lista.
  - La Caja A ya bloquea `cr.commit()` y es `READ ONLY` (`controllers/controller_helpers.py:184-250`).
    Solo se escapa lo que abre un cursor nuevo.
  - Las funciones del lienzo siguen funcionando, porque el sandbox las llama como funciones sueltas.
  - Exclusiones con su motivo, en el registro.
- **(e)** `action_execute_plan` llama a `self.action_confirm_and_execute()`, que pasa por
  `check_identity`. No se toca, y el test lo cubre.

**Ajustes de implementación respecto a §1:**
- **Parche 12, orden de las comprobaciones:** la de Seges va después de `_resolve_group_below_cusp`,
  no antes. Así la cúspide da primero el mensaje del fabricante y `test_paap_i7` solo falla en su
  última comprobación, la aceptada. Sigue yendo antes de la escritura en `sudo`.
- **Parche 12, una sola función:** la comprobación vive en `utils/privilege_cusp.py`
  (`settings_admin_error`), que comparten la acción de confianza y la vía CRUD.
