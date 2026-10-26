# Diagnóstico de R6 (y R4) en el staging de E1′

- **Fecha:** 26/10/2026 (horas en UTC).
- **Código:** rama `14.0-pns-ai-3879`, 3.1.879 con los parches 10 y 12 a 16 (commit `0366231`; el árbol
  no tiene cambios respecto a `947db7e`).
- **Fuentes:**
  - log del staging `~/staging_e1p/diag/pns_r4_r6_E1p.log` (8758 líneas, de 16:30 a 16:50);
  - lectura del código de los tres módulos y del core 14 de referencia;
  - reproducción en `lab_pns_ai_3879_14` (contexto `odoo-dev 14` `lab_pns_ai_3879`), con y sin los
    seis parches de E1′.
- **Comprobaciones en la BD del staging:** las del apartado 6 las hizo Sergio en `pns_demo` el
  26/10/2026 (solo lectura).

## 1. Resumen

1. **R6 no se reproduce como fallo del código.** En el laboratorio, `user.remove_group` confirmado
   desde la tarjeta quita el grupo de verdad: 4 de 4 veces, con y sin parches. En el staging, el log
   muestra que la escritura sobre T se confirmó a las 16:47:22. Después hay una **escritura manual
   sobre T desde el navegador, a las 16:48:43** (`/web/dataset/call_kw/res.users/write`), que hizo
   Sergio: es la causa de que T vuelva a tener el grupo (confirmado en el staging, apartado 6).
2. **Sí existe el caso «ejecutada y con el diario `applied` sin que el cambio exista»**, pero por otra
   vía: con `user.remove_group`, cuando el usuario también recibe el grupo por implicación de otro que
   conserva. Odoo 14 lo vuelve a añadir en el mismo `write`. La operación queda `executed` con
   `result.ok = true` y el diario `applied`. Reproducido con y sin parches: **es del fabricante.**
   Propuesta: **nuevo, gravedad Media** (apartado 5.1).
3. **El error de serialización no es concurrencia: sale en cada `/execute` de la tarjeta.** El cursor
   de la petición escribe en la fila de la operación después de que otro cursor la haya actualizado y
   confirmado. Odoo reintenta la petición, el segundo intento ve la operación ejecutada y responde
   bien. No se pierde nada. Es del fabricante, gravedad **Baja**, de la familia de PNS-26
   (apartado 5.2).
4. **`missing_token` y `bad_token` vienen de la compuerta del token, no de la ejecución.** Una tarjeta
   recién propuesta en el chat llega sin token. Además, cualquier `/pending` (por ejemplo, el del
   systray) rota el token sin actualizar la tarjeta. Las dos cosas son del fabricante, fallan en
   cerrado y su gravedad es **Baja** (apartado 5.3). En la franja de R6, el log no muestra ningún
   `/confirm` rechazado para la operación 27 (ver 3.2).

## 2. Flujo de la tarjeta del chat para el dueño (lectura del código)

### 2.1 Peticiones, en orden

| # | Origen | Petición | Qué hace | Escribe en la fila de `ai_safe_operation` | Cursor |
|---|---|---|---|---|---|
| 0 | Motor del chat (job de Chatboo) | evento SSE `verification` | `_mint_card_token` busca la operación y acuña un token (`pns_ai_mcp/utils/engine_tool_run.py:538-555, 586-593`) | Sí, si la encuentra (hash y fecha) | El del job (`pns_ai_chatboo/models/chatboo_async_request.py:359, 384`) |
| 1 | `_restorePendingVerifications` (`pns_ai_chatboo/static/src/js/chatboo_component_v2.js:2096-2111`) y `_refreshAuthCue` del systray (`pns_ai_chatboo/static/src/js/chatboo_systray.js:263-268`) | `POST /pns_ai_mcp/verification/pending` | `pending_card_payloads()` → `card_payload(mint_token=True)` → `_mint_confirm_token` (`pns_ai_mcp/controllers/verification_ui.py:142-146`; `pns_ai_mcp/models/safe_operation.py:2053-2066, 2020-2051, 553-565`) | **Sí, en cada llamada** (rota el token) | El de la petición |
| 2 | Botón Confirmar (`chatboo_component_v2.js:2264-2275`) | `POST /pns_ai_mcp/verification/confirm` `{verification_id, confirm_token}` | Compuerta del token (`verification_ui.py:37-50, 52-76`) y, si pasa, `_resolve_confirm` (`safe_operation.py:656-789`) | Sí: `status=confirmed`, `confirmed_by_uid`, `resolved_at` | Propio, `cr1` (`safe_operation.py:685`, commit en `:747`) |
| 3 | Si `/confirm` va bien (`chatboo_component_v2.js:2307-2330`) | `POST /pns_ai_mcp/verification/execute` `{verification_id, confirm_token}` | Compuerta (sin espera) → `_resolve_execute` (`safe_operation.py:791-911`) → `_execute_plan_with_timeouts` (`:948-1016`) → `execute_plan_now` (`:1344-1528`) | a) claim `result_info`, cursor propio con commit (`:1216-1285`); b) `executed/status/result_info`, en `cr2` (`:1474-1483`) | `cr2` (`:955`, commit en `:970`) |
| 3′ | Misma petición, al volver | — | `_consume_confirm_token` si `executed` (`verification_ui.py:95-96`; `safe_operation.py:587-593`) | Sí: `confirm_token_hash=NULL`, `confirm_token_at=NULL` | **El de la petición** |

### 2.2 Dónde se aplica cada cosa

- **El cambio del plan, el diario y `status=executed` van en la misma transacción, la de `cr2`:**
  - `execute_plan_now` hace commit para renovar la instantánea (`safe_operation.py:1439`) y ejecuta
    `execute_safe_plan` (`:1465`; `pns_ai_mcp/controllers/safe_plan.py:785-873`).
  - Un paso `action` llama a `ai.trusted.action._apply` (`pns_ai_mcp/models/ai_trusted_action.py:117-129`,
    con el `env` de `cr2`) y después a `_record_change_journal` (`safe_plan.py:871-873, 974-981`). Este
    crea la fila del diario en el mismo `env`, siempre con `state='applied'`
    (`pns_ai_mcp/models/ai_change_journal.py:348-367`).
  - Después, el `UPDATE … executed = true, status = 'executed'` en crudo (`safe_operation.py:1474-1481`)
    y el commit (`:1483`).
  - En el laboratorio, la fila del diario y el `write_date` del usuario tienen la misma marca de tiempo
    (por ejemplo, 17:14:32.282988): es la misma transacción.
- **`user.remove_group`:** `_apply_user_remove_group` (`pns_ai_mcp/models/ai_system_action.py:778-798`)
  → `user_remove_group` (`pns_base/utils/compat.py:119-122`). Este solo escribe `(3, gid)` si el grupo
  está en `groups_id`, y devuelve `ok: True` sin comprobar el resultado.
- **Diferencia con un paso CRUD (R4):** ninguna en cursores ni en transacción.
  - `create`, `write` y `action` siguen el mismo camino: misma transacción y mismo `UPDATE`.
  - Lo único que cambia es la llamada intermedia (`Model.create`/`write` en `safe_plan.py:889-918`
    frente a `action._apply`).

### 2.3 De dónde sale `missing_token`

- `verification_ui.py:44`: hay hash y la petición no trae token.
- `verification_ui.py:48-49`: no hay hash y la operación sigue `pending`.
- `bad_token` (`:44`): el token no coincide con el último acuñado.
- Las tres respuestas se devuelven **antes** de tocar la operación. En el JS solo se pintan como
  «Error: …» si las devuelve `/confirm` (`chatboo_component_v2.js:2281-2296`). Lo que devuelva
  `/execute` nunca se pinta como error.

## 3. Lo que muestra el log del staging

### 3.1 R4 (UW, `CREA00000001`, operación 21)

| Hora | PID | Evento |
|---|---|---|
| 16:34:42,240 | 18 | `/confirm` con 4 consultas: rechazado por la compuerta. El log no guarda la respuesta. |
| 16:34:42,789 | 18 | `GET /web`: recarga de la página. Después, `/pending` (acuña el token). |
| 16:34:51,305-448 | 18 | `/confirm` aceptado: «confirmada (uid=11) — sin execute». |
| 16:34:51,621-821 | 19 | `/execute`: `execute_plan_now` start → plan done, committing → finished. |
| 16:34:51,852 | 19 | `bad query: UPDATE "ai_safe_operation" SET "confirm_token_at"=NULL,"confirm_token_hash"=NULL,"write_uid"=11 …` → `SERIALIZATION_FAILURE, retry 1/5`. |
| 16:34:52,739 | 18 | Otro `/confirm` con 4 consultas, durante el reintento. No se sabe qué respondió. |
| 16:34:52,747 | 19 | `/execute` 200 (110 consultas, 1,02 s): el reintento terminó bien. |

### 3.2 R6 (ADM, `SAFE00000007`, operación 27)

| Hora | PID | Evento |
|---|---|---|
| 16:46:13, 16:46:16, 16:46:59 | 18/19 | `/confirm` con 3 consultas: rechazados por la compuerta. Son **anteriores a la operación 27**, que crea el job 172 (termina a las 16:47:03 con un evento `verification`). |
| 16:46:59 | 19 | Empieza el job 173, con una transacción anterior a la eliminación. |
| 16:47:22,079-156 | 18 | `/confirm` de la 27 aceptado (18 consultas). Es el **único** `/confirm` de la franja después de las 16:47:03. |
| 16:47:22,248-502 | 18 | `/execute`: plan done, committing → finished. |
| 16:47:22,521 | 18 | El mismo `bad query` (`write_uid=2`, `WHERE id IN (27)`) → `retry 1/5 in 0.6190 sec`. |
| 16:47:23,156 | 18 | `/execute` 200 (107 consultas). Antes, «At least one model cache has been invalidated», propio de un `write` en `groups_id`. |
| 16:47:42,102 | 19 | La interfaz pide la imagen de T con `unique=26102026174722`: el `write_date` de T es 16:47:22 UTC (17:47:22 en Madrid). **La escritura sobre T se confirmó.** |
| 16:47:55,759 | 19 | El job 173 llama a `safe_plan_request`: es la propuesta 28. Su transacción es de antes de las 16:47:22, así que todavía ve el grupo. |
| 16:48:03 | 19 | `/cancel` de `SAFE00000008`. |
| **16:48:43,672** | 18 | **`POST /web/dataset/call_kw/res.users/write`** (69 consultas), seguido de `res.users/read` y de la imagen de T con `unique=26102026174843`. Alguien guardó la ficha de T desde el navegador. |
| 16:49:53, 16:50:18, 16:50:28 | — | Jobs 176 a 178: nuevas propuestas (29 a 31). Son posteriores a 16:48:43. |

**Lectura:**
- La operación 27 se aplicó. El grupo vuelve con una escritura manual a las 16:48:43, que no pasa
  por el diario.
- La propuesta 28 sale de una lectura con la instantánea antigua del job 173. Las 29 a 31 ven el
  grupo porque ya estaba de nuevo.
- El «Error: missing_token» que se vio no puede ser de la confirmación de la 27, que fue aceptada.
  Encaja con alguna de las tarjetas de 16:46 (apartado 5.3).

**No explicado:** el `write_date` de la operación 27 es 16:47:55 y la escritura la hizo ADM (uid 2,
apartado 6, consulta 2), pero ningún código que haya encontrado escribe en una operación ya ejecutada:
- `refresh_expiry_statuses` y `_align_executed_status` (`safe_operation.py:1910-1965`) solo tocan
  `pending`/`confirmed`;
- `_replace_pending_plan` (`safe_plan.py:2051-2106`) no se llama desde la herramienta.

Coincide con la propuesta 28 del job 173. Sigue sin causa en el código y sin efecto: no cambia el
estado ni el resultado (apartado 6, consulta 2).

## 4. Reproducción en el laboratorio

### 4.1 Método

- **Reinicio:** `odoo-dev 14 parar` y `odoo-dev 14 arrancar` desde `~/GitHub/lab_pns_ai_3879` antes de
  cada ronda contra el servidor web (regla de E1′), también tras neutralizar y tras restaurar.
- **Datos:** creados con `odoo-dev 14 shell` y borrados al final (4.5):
  - usuarios de prueba T (`diag_r6_t`, interno con `base.group_partner_manager` directo) y T2
    (`diag_r6_t2`, interno con `sales_team.group_sale_salesman_all_leads`, que implica
    `group_sale_salesman`);
  - contacto «Diag R4 contacto».
- **Operaciones:** creadas como admin (uid 2) con `request_safe_plan`, la misma función que usa la
  herramienta `safe_plan_request` (cursor propio con commit, `safe_plan.py:2194-2223`):
  - `r6_remove_group`: `action` `user.remove_group` sobre T;
  - `r4_note`: `create` de `mail.message` (nota en el chatter del contacto);
  - `write_partner`: `write` de `comment` en el contacto;
  - `implied_group`: `action` `user.remove_group` de `group_sale_salesman` sobre T2.
- **Confirmación:** por HTTP, con sesión de admin y las mismas peticiones que el JS:
  - `/pending` para obtener el token de la tarjeta;
  - 5,5 s de espera si la tarjeta es `high`;
  - `/confirm` y `/execute` con ese token.
  - En la variante concurrente, un segundo `/confirm` 0,15 s después de lanzar `/execute`, como en R4
    a las 16:34:52.
- **Comprobación:** SQL de solo lectura del estado, la fila del diario, `res_groups_users_rel`, el
  contacto y la nota.

### 4.2 Con los parches de E1′ (rondas `parcheado` y `conc`)

| Caso | Respuesta de `/confirm` | Respuesta de `/execute` | Operación | Diario | Efecto real |
|---|---|---|---|---|---|
| R6, grupo directo | `confirmed`, `needs_execute` | `executed`, `idempotent: true` | `executed`, hash vacío | `action` `applied` | **T sin el grupo** |
| R4, nota | igual | igual | `executed` | `create` `applied` | Nota creada |
| `write` en el contacto | igual | igual | `executed` | `write` `applied` | `comment` escrito |
| Grupo implicado | igual | igual | `executed`, `result.ok: true` | `action` `applied` | **T2 sigue con el grupo** |
| Variante concurrente (los 4) | igual | igual; el segundo `/confirm`: `executed`, `idempotent: true` | igual | igual | Igual que arriba |

- En las 8 llamadas a `/execute`, el log del servidor tiene el mismo `bad query … could not serialize
  access due to concurrent update` sobre `confirm_token_*`, seguido de `SERIALIZATION_FAILURE, retry
  1/5`.
- El `idempotent: true` de la respuesta es la huella del reintento: el segundo intento entra por la
  rama de «ya ejecutada» (`safe_operation.py:820-840`).

### 4.3 Origen de `missing_token` y `bad_token`

- **Montaje:** el cursor del shell hace de cursor del job, con su transacción ya empezada. Se crea la
  operación con `request_safe_plan` y se llama a `ToolRunMixin._mint_card_token` con ese `env`, como
  hace el motor.

| Prueba | Resultado |
|---|---|
| ¿El cursor del job ve la operación recién creada? | **No.** `_mint_card_token` devuelve `''` y el evento sale sin token. |
| `/confirm` con la tarjeta sin token | `missing_token` (hay hash, pero la petición no trae token). |
| `/pending` y, con el token nuevo, `/confirm` + `/execute` | Bien (`confirmed` → `executed`). |
| Tarjeta con el token A, otro `/pending` (systray) y `/confirm` con A | `bad_token`. |

### 4.4 Con los seis parches neutralizados (rondas `neutro`, `neutroconc` y `tokneutro`)

- **Neutralización (como la del 23/10, sin git):**
  - copia de los 7 archivos parcheados en el scratchpad con su sha256;
  - en su lugar, las versiones de `_fabricante/3.1.879/`: `validators_base.py`, `ai_context_disk.py`,
    `ai_system_action.py`, `key_pin_desk.py`, `mcp_user.py`, `safe_operation.py` y
    `privilege_cusp.py`, con 0 marcadores;
  - reinicio del contexto.
- **Resultado: idéntico a 4.2 y 4.3.** El grupo directo se quita; el implicado se queda con la
  operación `executed` y el diario `applied`; la serialización sale en cada `/execute`;
  `missing_token` y `bad_token` igual.
- **Restauración:**
  - copia de vuelta de los 7 archivos: `sha256sum -c` correcto en los 7;
  - `grep -c "Seges: parche"`: 27 marcadores en 13 archivos, igual que antes;
  - `git status --short` vacío;
  - reinicio del contexto con el código parcheado.

### 4.5 Estado del laboratorio

- **Recuentos** (`res_users`, `res_partner`, `res_groups_users_rel`, `ai_safe_operation`,
  `ai_change_journal`, `mail_message`, `ai_log`, `ir_attachment`, `res_users_log`, `bus_bus` y crons
  activos): **iguales antes y después**, también los `max(id)`. Por ejemplo, `ai_safe_operation` 0 → 0,
  `ai_change_journal` 2 → 2 y `res_users` 8 → 8.
- **Borrado:**
  - por ORM: los 2 usuarios y los 3 contactos de prueba, con sus avatares y mensajes;
  - por SQL, acotado a los ids posteriores al recuento inicial: 20 operaciones, 19 filas del diario,
    19 de `ai_log`, 28 de `res_users_log` y 39 de `bus_bus` (había 0).
- **Residuos:**
  - las secuencias de PostgreSQL de ids y de `verification_id` (`pns_ai_mcp.safe_op.*`) han avanzado;
  - el log del servidor web de estas rondas se perdió al recrear el contenedor; los extractos están
    arriba.

## 5. Conclusiones

### 5.1 Operación `executed` y diario `applied` sin el cambio: `user.remove_group` con grupos implicados (nuevo)

- **Se confirma** que puede pasar, aunque no es lo que ocurrió en R6 (ver 1.1 y 3.2).
- **Causa exacta:**
  - `user_remove_group` (`pns_base/utils/compat.py:119-122`) escribe `(3, gid)`.
  - El `write` de `res.users` en Odoo 14 (`UsersImplied.write`,
    `/opt/odoo-src/14.0/odoo/odoo/addons/base/models/res_users.py:1091-1109`) añade después los
    `trans_implied_ids` de los grupos que quedan. Si alguno implica `gid`, vuelve en la misma
    escritura.
  - `_apply_user_remove_group` (`ai_system_action.py:778-798`) devuelve `ok: True` sin comprobarlo.
  - `record_executed_step` registra siempre `state='applied'` (`ai_change_journal.py:348-367`).
  - Variante: si el grupo no está en `groups_id`, `user_remove_group` no escribe nada y el resultado
    es el mismo.
- **Alcance:**
  - **Tipo:** solo `user.remove_group`. `user.add_group` siempre tiene efecto. En los pasos CRUD, el
    diario refleja lo que hace el ORM.
  - **Vías:** todas las que terminan en `execute_safe_plan`, porque está en `_apply`:
    - la tarjeta del chat (`/confirm` + `/execute`);
    - Autorizaciones (`action_confirm_and_execute`);
    - `safe_plan_status`;
    - el reintento del cron (`_retry_confirmed_not_executed`).
- **Fabricante o parche:** fabricante. Con los parches neutralizados el resultado es el mismo. El
  parche 12 solo añade la comprobación de Ajustes antes de escribir.
- **Gravedad propuesta: Media.**
  - Una retirada de permisos pedida y confirmada no ocurre, y el diario y la respuesta dicen lo
    contrario: auditoría falsa.
  - No concede privilegios, y la ficha del usuario sigue mostrando el grupo.
- **PNS:** no corresponde a ninguno de los citados:
  - PNS-24 es `module.update`;
  - PNS-26, commits fuera del flujo;
  - PNS-94, bloqueo de `chatboo_session`.
  - Se relaciona con PNS-37 (diario incompleto) y con PNS-01/02 (grupos nativos), pero es distinto.
  - **Propuesta: hallazgo nuevo** (siguiente número libre en el seguimiento: PNS-99).
  - **Registrado como PNS-99** en el [seguimiento](seguimiento_informe_pns_ai.md) (decisión de Sergio
    del 26/10/2026).

### 5.2 Error de serialización en cada `/execute` de la tarjeta

- **Causa:**
  - `/execute` lee la operación con el cursor de la petición (`verification_ui.py:24`), que fija su
    instantánea `REPEATABLE READ` (`/opt/odoo-src/14.0/odoo/odoo/sql_db.py:420`).
  - Después, el claim y `cr2` actualizan esa fila y hacen commit (`safe_operation.py:1243-1280, 1483`).
  - Al volver, `_consume_confirm_token` (`verification_ui.py:96`) escribe la misma fila con la
    instantánea antigua. El volcado al final de la petición (`/opt/odoo-src/14.0/odoo/odoo/http.py:362-366`)
    da 40001.
  - `service_model.check` reintenta (`/opt/odoo-src/14.0/odoo/odoo/service/model.py:22-23, 97-105`). El
    segundo intento entra por la rama de «ya ejecutada» y el consumo del token pasa.
- **Alcance:**
  - toda confirmación por la tarjeta del chat, de cualquier tipo de operación: determinista, sin
    necesidad de otro cliente;
  - no afecta a Autorizaciones (`action_confirm_and_execute`), que no consume el token por esta ruta.
- **Efecto:**
  - una línea ERROR en el log por cada confirmación;
  - un reintento con espera aleatoria (hasta 1 s en el primero);
  - no hay pérdida ni duplicado: el plan no se repite, por el claim y la rama idempotente.
- **Fabricante o parche:** fabricante (igual sin parches).
- **Gravedad propuesta: Baja.**
- **PNS:** misma familia que PNS-26 (escrituras en el cursor del llamador mezcladas con cursores
  propios que hacen commit). **Propuesta:** añadirlo al «resto» de PNS-26 en lugar de abrir otro.
  **Añadido a PNS-26** en el [seguimiento](seguimiento_informe_pns_ai.md).

### 5.3 `missing_token` / `bad_token` en la tarjeta del chat

- **Causa 1 (`missing_token`):**
  - `_mint_card_token` se ejecuta en el cursor del job (`engine_tool_run.py:538-555`).
  - La operación se crea en otro cursor, con commit (`safe_plan.py:2194-2223`), cuando la transacción
    del job ya empezó. El job no la ve y el evento sale sin token.
  - El primer Confirmar falla hasta que un `/pending` repinta la tarjeta con token
    (`chatboo_component_v2.js:2170-2178`).
- **Causa 2 (`bad_token`):** cualquier `/pending` rota el token (`safe_operation.py:2053-2066`, con
  `mint_token=True` por defecto, llamado sin argumentos en `verification_ui.py:145`), también el del
  systray (`chatboo_systray.js:263-268`), que no actualiza la tarjeta.
- **Alcance:** tarjetas del chat (Chatboo). Fallan en cerrado: nunca ejecutan sin token.
- **Fabricante o parche:** fabricante.
  - El parche 16 solo limita el acuñado al dueño (`safe_operation.py:2047-2049`), y en estas pruebas
    el que llama siempre es el dueño.
  - Con los parches neutralizados, el resultado es el mismo.
- **Gravedad propuesta: Baja** (usabilidad: obliga a repetir y confunde, como en R4 y R6).
- **PNS:** relacionado con PNS-54 (token de la tarjeta), pero no es lo que corrige el parche 16.
  **Propuesta:** hallazgo nuevo de gravedad Baja, o anexo a PNS-54. **Añadido como anexo a PNS-54**
  en el [seguimiento](seguimiento_informe_pns_ai.md) (decisión de Sergio del 26/10/2026).

### 5.4 Observación: propuestas con datos antiguos

- El job 173 propone a las 16:47:55 quitar un grupo que ya no estaba, porque su transacción empezó
  antes del cambio. Es el mismo mecanismo que en 5.3: una transacción larga del job en `REPEATABLE
  READ`.
- No hace daño (el humano cancela), pero explica la propuesta 28.
- No se propone como hallazgo.

## 6. Comprobaciones en el staging (hechas el 26/10/2026)

```sql
BEGIN READ ONLY;
-- 1. ¿Quién escribió T por última vez? Se espera write_date ≈ 16:48:43 (la escritura manual).
SELECT id, login, write_uid, write_date FROM res_users WHERE id = 22;
-- 2. Operación 27: write_uid de la escritura de las 16:47:55 (apartado 3.2, «no explicado»).
SELECT id, verification_id, status, executed, write_uid, write_date, resolved_at
  FROM ai_safe_operation WHERE id = 27;
-- 3. ¿Algún grupo de T implica Contact Creation (transitivamente)? Se esperan 0 filas.
WITH RECURSIVE imp(gid, hid) AS (
    SELECT gid, hid FROM res_groups_implied_rel
    UNION SELECT i.gid, r.hid FROM imp i JOIN res_groups_implied_rel r ON r.gid = i.hid)
SELECT i.gid FROM imp i
  JOIN res_groups_users_rel u ON u.gid = i.gid AND u.uid = 22
 WHERE i.hid = (SELECT res_id FROM ir_model_data WHERE module = 'base' AND name = 'group_partner_manager');
ROLLBACK;
```

Y preguntar a quien hizo R6 qué hizo a las 16:48:43 en la ficha de T (17:48:43 en Madrid).

- **Si la consulta 1 da 16:48:43 y la 3 da 0 filas:** queda cerrado que R6 fue una escritura manual,
  no un fallo.
- **Si la 3 devuelve filas:** R6 es el caso de 5.1.

**Resultado** (Sergio, 26/10/2026, en `pns_demo`, solo lectura):

| Consulta | Resultado |
|---|---|
| 1 | T (id 22): `write_uid` 2, `write_date` 16:48:43 UTC |
| 2 | Operación 27: `write_uid` 2, `write_date` 16:47:55 UTC |
| 3 | 0 filas |

- Sergio confirma que fue él quien guardó la ficha de T a las 17:48:43 (Madrid).
- **La escritura de las 16:48:43 queda confirmada:** la hizo Sergio (`write_uid` 2, consulta 1). El
  log no guarda el usuario ni los valores enviados; la secuencia de peticiones, el `write_date` de T y
  la confirmación de Sergio sí lo cierran.
- **Conclusión:** R6 fue la escritura manual, no un fallo del código.

## 7. Lo que no se ha podido reproducir o determinar

- **La escritura de las 16:47:55 en la operación 27:** la hizo ADM (uid 2, consulta 2); sigue sin
  causa en el código y sin efecto.
- **Las respuestas de los `/confirm` rechazados del staging:** el log no las guarda; solo el número de
  consultas.
- **El evento SSE sin token, de extremo a extremo con un LLM real:** no se ha reproducido para no usar
  proveedores. Se reprodujo la misma llamada (`_mint_card_token`) en un cursor con la transacción ya
  empezada.
- **El reparto en procesos:** el laboratorio corre en modo hilos (werkzeug) y el staging en prefork. No
  influye en 5.2, que ocurre dentro de una sola petición.
- **Las pruebas se hicieron con `admin`,** con la contraseña de demo del laboratorio; no la apunto aquí.
