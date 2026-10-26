# Plan de corrección de los módulos pns_ai sobre la base 3.1.879

- **Rama de trabajo:** `14.0-pns-ai-3879`, base `5940e52` (la 3.1.879 del fabricante, sin cambios)
- **Fecha de aprobación:** 23/10/2026 (Sergio).
- **Origen:** [decisiones](pns_ai_decisiones.md) N12, opción **b′** (cambiar una vez de base a 3.1.879), y
  la [hoja de decisión](n12_decision_3879.md).
- **Datos de cada hallazgo:** [comparación con 3.1.879](../specs/comparacion_pns_ai_3-1-879.md); cada
  ficha cita su sección.
- **Registro de los cambios en el código:** [parches_pns_ai.md](parches_pns_ai.md).
- **Plan anterior:** [plan_correccion_pns_ai.md](plan_correccion_pns_ai.md) (base 3.1.782), referencia
  de la rama `14.0-pns-ai-correcciones`.
- **Estado del plan:** aprobado (23/10/2026); E0′ terminada el 23/10/2026: parte A (tests) validada en
  laboratorio y diagnóstico de PNS-70 hecho ([pns70_diagnostico_3879.md](pns70_diagnostico_3879.md)).
  Rama `14.0-pns-ai-3879` publicada el 23/10/2026 (desde `dafb316`). Siguiente: E1′.
  E1′ validada en laboratorio el 23/10/2026 (parches 10 y 12 adaptados y 13 a 16); siguiente: subida al
  staging `pns_demo` con el cambio de base.

## 1. Cómo se trabaja

**Reglas (las de N11):**
- Un commit por parche y otro por los tests de cada entrega.
- Marcador `Seges: parche N` junto a cada cambio.
- Entrada de cada parche en [parches_pns_ai.md](parches_pns_ai.md).
- Test negativo de Seges para cada parche.
- Sin tocar `version`, `depends` ni `external_dependencies`.

**Criterio:** lo Crítico y lo Alto se corrige; lo Medio y lo Bajo, caso a caso (E4′).

**Numeración de los parches:**
- **1 a 9:** se retiran en esta rama; los cubre el fabricante.
- **10, 11 y 12:** conservan su número, con la nota «adaptado a 3.1.879».
- **13 en adelante:** los parches nuevos, en el orden en que se apliquen.

**Validación de cada entrega:**
1. **Laboratorio:** contexto `odoo-dev 14 lab_pns_ai_3879`, BD `lab_pns_ai_3879_14`.
2. **Staging `pns_demo`.** La primera subida (E1′) incluye el cambio de base de `pns_demo` de 3.1.782 a
   3.1.879 con `-u`, sin copia (N9; aprobado el 23/10/2026). Las pérdidas son las de P-9 (comparación
   §9.5 y §9.6).
3. **LIYBEN:** se actualiza de una vez al final (§3).

## 2. Entregas

| Entrega | Contenido | Parches | Estado |
|---|---|---|---|
| **E0′** (previa) | `test_seges_*` adaptados; esqueleto de tests de Chatboo; datos de prueba de `test_change_journal` y `test_paap_core`; línea base nueva; diagnóstico de PNS-70 (solo lectura) | — | Parte A (tests): validada en laboratorio (23/10/2026). Diagnóstico de PNS-70: hecho (23/10/2026) |
| **E1′** | Críticos y Altos baratos: M10 con el parche 12 adaptado, PNS-54, PNS-07, M13, `collect_pin` (PNS-83) | 10 y 12 adaptados; 13 (M10), 14 (M13), 15 (PNS-07) y 16 (PNS-54) | Validada en laboratorio (23/10/2026) |
| **E2′** | Resto de Altos: papelera del diario (PNS-37), PNS-19, PNS-17, PNS-82, PNS-70; PNS-20 si P-20 lo confirma | 11 adaptado; nuevos | Pendiente |
| **E3′** | Lienzo: M1, M2 y F1 | Nuevos | Pendiente |
| **E4′** | Hoja de Medios y Bajos (corregir o aceptar); después, lo elegido | Nuevos, si se corrige algo | Pendiente |

Rutas de las fichas: las de la comparación (salvo indicación, de `pns_ai_mcp`; línea de 3.1.879).

### E0′ (previa)

- **Adaptar los `test_seges_*` desde `14.0-pns-ai-correcciones`:** solo lo que pasa sin parches.
  - Origen: comparación §4.1 (y §10.1, «Tests de E1 y E2»).
  - Qué falla: la importación de `RELAXAICODE_SIDE_EFFECT_METHODS` de `controllers/validators` está rota
    (ahora en `controllers/validators_base.py:233`, sin los nombres privados). El detalle por test,
    en §4.1.
  - `pns_ai_mcp/tests/test_seges_rpc_access.py`, completo (18 tests, parches 7 a 10), con 6 adaptaciones:
    - la lista negra pasa a `blocked_private_attr` (`validators_base.py:164`);
    - el AST rechaza el nombre privado (`PRIVATE_ATTR`, `validators.py:303-304, 362-367`);
    - con la política `open` ya no se da de alta el dominio (`safe_plan.py:775-777`);
    - el código se lee en `SkillsMixin._normalize_skill_params` (`utils/engine_skills.py:71`);
    - `_redeem_key_pin` responde `no_desk` sin mesa abierta (`mcp_user.py:764-765`).
    - Las pruebas del parche 10 son las de su alcance en 3.1.782; el canje por `collect_pin` va en E1′.
  - `pns_ai_chatboo/tests/test_seges_chatboo_access.py`: 12 de los 15 tests (parche 11).
    - Los jobs se crean en `sudo`: la ACL es `1,0,0,0`.
    - `test_claim_filters_in_python` queda sin el adjunto con `res_id = 0`.
    - Van a E1′: `test_seges_user_groups.py` y `test_fulfill_client_export_claims_own`. Van a E2′: los
      dos tests de `unlink` y el caso de `res_id = 0`.
- **Tests propios de Chatboo:** en esta entrega, solo el esqueleto; se amplían en cada entrega.
  - Origen: comparación §5.6, «PNS-50 y PNS-77» (Chatboo sin tests en el paquete).
  - Archivo y método:
    - `pns_ai_chatboo/tests/common.py`, clase `SegesChatbooCase(HttpCase)`: usuario con acceso
      (grupo conversacional y clave MCP, `utils/chatboo_access.py:7-30`) y llamadas JSON-RPC;
    - `pns_ai_chatboo/tests/test_seges_chatboo_smoke.py`, `TestSegesChatbooSmoke.test_open_session`
      (`/chatboo/sessions/create` y `/load`, `controllers/chatboo.py:270-320`) y
      `test_no_access_without_key`.
  - Ampliación: un archivo `test_seges_chatboo_<tema>.py` por entrega sobre `SegesChatbooCase`
    (E1′, PNS-07; E2′, parche 11; E3′, lienzo).
- **Datos de prueba de `test_change_journal` y `test_paap_core`.**
  - Origen: fase 3, parte 1, paso 3 ([fase3_lab_pns_ai_3879.md](fase3_lab_pns_ai_3879.md), tabla
    «Nuevos frente a la línea base»), y comparación §5.5, fila PNS-50 y PNS-77.
  - Archivos y método:
    - `pns_ai_mcp/tests/test_change_journal.py`: `_exec` da `AI Writer` al usuario 1 en la transacción
      del test;
    - `pns_ai_mcp/tests/test_paap_core.py`: `setUp` pone el registro en modo test, para que el cursor
      propio de `request_safe_plan` vea al usuario.
  - Marcador sin número ni PNS: `Seges: parche de tests E0′ (datos de prueba)`. Registro en
    [parches_pns_ai.md](parches_pns_ai.md), «Cambios en tests del fabricante».
  - Queda en F, sin tocar y pendiente de decisión de Sergio,
    `test_failed_execute_journals_outside_rollback`: no se arregla con datos de prueba (texto de error
    antiguo y lectura con una transacción anterior al commit).
- **Línea base nueva** con los tests de Seges. Referencia: 202 tests, 17 F y 35 E (fase 3, parte 1).
  - **Resultado (23/10/2026):**
    - `pns_ai_mcp`: 220 tests, 17 F, 32 E y 3 saltados;
    - `pns_ai_chatboo`: 14 tests, 0 F y 0 E;
    - `pns_base`: sin tests.
  - Detalle test a test en [parches_pns_ai.md](parches_pns_ai.md), «Línea base de E0′ sobre 3.1.879».
- **Diagnóstico de PNS-70**, de solo lectura y sin parche en esta entrega: por qué falla en 3.1.879 y no
  en 3.1.782, con los estáticos reales del contenedor.
  - Origen: comparación §5.6, «PNS-70».
  - Archivos: `pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js:12-33` (3.1.879, carga de Chart.js
    4.4.8 al abrir el chat); `pns_ai_chatboo/views/assets.xml:22` (3.1.782, en `web.assets_backend`).
- **Al terminar E0′, Sergio publica la rama.**

### E1′ (Críticos y Altos baratos)

- **Propuesta y decisiones (23/10/2026):** [e1_propuesta_3879.md](e1_propuesta_3879.md).
- **Resultado (23/10/2026): validada en laboratorio.**
  - Parches 10 y 12 adaptados, y 13 (M10), 14 (M13), 15 (PNS-07) y 16 (PNS-54).
  - Tests: 260, 18 F y 32 E. El F nuevo es `test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin`,
    aceptado por diseño.
  - Detalle, inventario de PNS-07 y neutralización en [parches_pns_ai.md](parches_pns_ai.md),
    «Parches de la rama 14.0-pns-ai-3879 (E1′)».
  - PNS-54 (c), la tarjeta del chat del propio dueño: riesgo aceptado ligado a D29.
- **Subida al staging `pns_demo` (preparada el 26/10/2026, sin ejecutar):**
  [staging_e1_3879.md](staging_e1_3879.md). Comprobaciones previas, despliegue con `git archive` y `-u`,
  P-9, pruebas de seguridad y de no regresión, y vuelta atrás.
- **M10, junto con el parche 12 adaptado.**
  - Origen: comparación §8.7 «M10» (Crítica), §1.2 (parche 12), §2.1 (PNS-01, resto) y §10.1.
  - Archivo y método (M10): `models/safe_operation.py`: `create` de `ai.safe.operation` (no
    sobrescrito), `cleanup_stuck_state` (`:1006-1039`), `_retry_confirmed_not_executed`
    (`:1041-1080`) y `execute_plan_now` (`:1409-1468`).
  - Archivo y método (parche 12): `models/ai_system_action.py`, `_resolve_group_below_cusp`
    (`:700-708`) al proponer y al ejecutar (`:719-775`); vía CRUD en `controllers/safe_plan.py:270-271,
    881-940` (`crud_cusp_error`, §10.1).
  - Criterio de Seges: solo `base.group_system` da o quita cualquier grupo mediante un plan, también
    por la vía CRUD. El control no puede fiarse de `self.env.user` en un plan lanzado por
    `cleanup_stuck_state`.
- **PNS-54.**
  - Origen: comparación §3 «PNS-54» (Crítica) y §1.3.
  - Archivo y método: `models/safe_operation.py`: `card_payload(mint_token=True)` (`:2003-2032`),
    `pending_card_payloads` (`:2034-2048`), `action_confirm_and_execute` y su alias
    `action_execute_plan` (`:1765-1831`); ruta `/pns_ai_mcp/verification/pending` en
    `controllers/verification_ui.py:142-146`.
- **PNS-07.**
  - Origen: comparación §3 «PNS-07» (Crítica) y §1.3.
  - Archivo y método: `pns_ai_chatboo/models/chatboo_session.py`, `fulfill_client_export`
    (`:541-564`), que llega a `persist_turn_file` (`utils/session_download.py:365-392`, cursor propio
    con commit); `sandbox_helpers` (`chatboo_session.py:818`).
  - Tests: se porta aquí `test_fulfill_client_export_claims_own` (de `test_seges_chatboo_access.py`
    de `14.0-pns-ai-correcciones`), en `pns_ai_chatboo/tests/test_seges_chatboo_export.py`.
  - **Los tests de PNS-07 no deben usar `enter_test_mode` ni `HttpCase`** (que lo activa): tienen que
    ejercitar el cursor propio con commit, que es el defecto. Con el registro en modo test, ese cursor
    comparte la transacción del test y el fallo no se ve.
- **Tests del parche 12 adaptado:** `pns_ai_mcp/tests/test_seges_user_groups.py` (de
  `14.0-pns-ai-correcciones`), reescrito con un grupo no cúspide (comparación §4.1 y P-01).
- **M13.**
  - Origen: comparación §8.7 «M13» (Alta).
  - Archivo y método: `models/ai_context_disk.py:757-796`, `ai.context.unlink_retired_from_module`.
- **`collect_pin`, PNS-83** (parche 10 adaptado: renombrar a `_collect_pin`).
  - Origen: comparación §3 «PNS-83» (Alta), §1.2 y §10.1.
  - Archivo y método: `models/key_pin_desk.py:193-201`, `ai.key.pin.ask.collect_pin`; único llamador,
    `models/mcp_user.py:766`.

### E2′ (resto de Altos)

- **Papelera del diario, PNS-37:** cron como superusuario sobre filas editables; borrado que solo exige
  escritura.
  - Origen: comparación §6.1 «PNS-37 (parte)» (Alta, propuesta) y §1.3.
  - Archivo y método: `models/ai_change_journal.py`, `_cron_empty_journal_trash` (`:612-633`) y la
    selección de filas en papelera (`:541-575`); `data/journal_trash_cron.xml:5-15` (sin `user_id`);
    `security/ir.model.access.csv:42-43`; paso `unlink` de un plan en `controllers/safe_plan.py:938-953`.
  - Tests: si el parche de la papelera afecta a la fila del diario de una ejecución fallida
    (`_record_failed_plan`), un test de Seges cubrirá que esa fila sobrevive al rollback, con un cursor
    propio y sin `enter_test_mode`. El test del fabricante `test_failed_execute_journals_outside_rollback`
    se acepta como desfasado (entre los 17 F de la línea base de E0′) y no se rediseña.
- **PNS-19.**
  - Origen: comparación §3 «PNS-19» (Alta) y §1.3.
  - Archivo y método: control de modelos de credenciales en `controllers/validators_base.py:187-209,
    405-415` y `controllers/context_builder.py:83-117` (`GuardedSandboxEnv.__getattr__`, `env.ref`);
    relación `ai.log.provider_id` en `models/ai_log.py:172-179`.
- **PNS-17.**
  - Origen: comparación §3 «PNS-17» (Alta) y §1.3.
  - Archivo y método: `utils/fetch_url_safe.py:98-110, 156-159` (`_AUTH_HEADER_NAMES`,
    `request_public_http`); `auth_header_name` en `lib/api/drivers/base.py:47-50`.
- **PNS-82** (parche 11 adaptado: el `unlink` de la sesión).
  - Origen: comparación §3 «PNS-82» (Alta; resto Baja), §1.2 y §10.1.
  - Archivo y método: `pns_ai_chatboo/models/chatboo_session.py`, `unlink` (`:1989-1995`) y
    `_cleanup_old_sessions` (`:2023`).
  - Tests, de `test_seges_chatboo_access.py` de `14.0-pns-ai-correcciones` (no portados en E0′):
    - `test_unlink_own_session_keeps_foreign` y `test_cron_unlink_sudo_keeps_foreign`, que fallan con
      3.1.879 por la diferencia real;
    - en `test_claim_filters_in_python`, el adjunto con `res_model` y `res_id = 0`, que el fabricante
      no engancha (exige los dos vacíos, `chatboo_session.py:495`). Hay que decidir si se mantiene el
      criterio del parche 11.
- **PNS-70:** parche sin pisar `window.Chart` y repetición de P-70, que cierra la condición 3 de la
  [hoja de N12](n12_decision_3879.md).
  - Origen: comparación §5.6 «PNS-70» (Alta) y §1.3.
  - Archivo y método: `pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js:24-33`.
  - Diagnóstico (E0′, parte B): [pns70_diagnostico_3879.md](pns70_diagnostico_3879.md). Mecanismo
    comprobado en ejecución el 23/10/2026: Chart 4, cargado al abrir el chat, sustituye en `window.Chart`
    a la 2.x de Odoo.
  - **Decisión de Sergio (23/10/2026): opción A.** Chart 4 bajo un nombre propio, `PnsChatbooChart`:
    `pns_ai_chatboo/static/src/js/chart.umd.min.js` (cabecera UMD) y `chatboo_heavy_libs.js:28-33`.
    Condiciones:
    1. Antes de aplicarla, comprobar que ningún otro JS de `pns_*` usa `window.Chart` esperando la
       versión 4; si lo hay, pasa también a `PnsChatbooChart`.
    2. El cambio en la librería es exactamente un token (`.Chart=e()` → `.PnsChatbooChart=e()`), con
       marcador, y el `grep` que lo localiza queda en [parches_pns_ai.md](parches_pns_ai.md).
  - Validación con P-70 (casos en el diagnóstico, §4):
    - Odoo: `window.Chart` sigue siendo la 2.x (`Chart.helpers` presente, sin `Chart.version`);
    - chat: `PnsChatbooChart.version` = `4.4.8`.
- **PNS-20**, solo si P-20 lo confirma.
  - Origen: comparación §6.1 «PNS-20 (parte)» (Alta, REQUIERE PRUEBA) y §1.3.
  - Archivo y método: `pns_base/models/operation_report_wizard.py`, `action_preview` (`:305-323`;
    `SAVEPOINT` en `:290-291`).

### E3′ (lienzo)

- **M1:** dueño en `paint_canvas`.
  - Origen: comparación §8.7 «M1» (Media) y §8.2.
  - Archivo y método: `pns_ai_chatboo/models/chatboo_session.py`, `paint_canvas` (`:1049-1184`), que
    guarda con `_store_design` (`:974-1017`).
- **M2:** `page_html` lee imágenes en `sudo`.
  - Origen: comparación §8.7 «M2» (Media) y §8.2.
  - Archivo y método: `pns_ai_chatboo/models/chatboo_session.py`, `page_html` (`:897-943`);
    `pns_ai_chatboo/models/chatboo_canvas.py`, sesión en `sudo` en `_session_of_this_turn` (`:639`) y
    lectura de imágenes en `pictures_as_tokens` (`:677-697`).
- **F1:** CSP y escape de `</` en `DATA`.
  - Origen: comparación §8.7 «F1» (Media) y §8.4.
  - Archivo: `pns_ai_chatboo/models/chatboo_canvas.py` (carcasa `:500-573`; filas en el `<script>`
    `:1097-1109, 1423-1434`).
  - Método: a determinar en la entrega.

### E4′ (hoja de Medios y Bajos)

Hoja con una propuesta de corregir o aceptar para cada uno. Decide Sergio con la hoja y después se
corrige lo elegido.

| Ficha | Origen (comparación) | Archivo y método |
|---|---|---|
| M11 | §8.7 «M11», §8.2 | `models/ai_execution_engine.py:402-758`, envoltorios `log_*` (`log_llm_inference`, `log_provider_*`, `log_role_without_provider`) |
| M12 | §8.7 «M12», §8.2 | `models/ai_execution_engine.py:849-923`, `chat_completion` |
| PNS-97 | §3 «PNS-97», §2.3 | `models/ai_trusted_action.py:28-143` (`_resolve_method`, `:93-110`); `security/ir.model.access.csv:74` |
| PNS-98 | §3 «PNS-98», §2.3 | `utils/session_download.py:365-392` (`persist_turn_file`); `pns_ai_chatboo/models/chatboo_session.py:559-564` (`fulfill_client_export`) y `:490-492` (`_claim_turn_file_chips`); vía de respaldo de `_finalize` en `pns_ai_chatboo/models/chatboo_async_request.py:697-715` |
| PNS-61 | §3 «PNS-61» | `pns_ai_chatboo/models/chatboo_session.py:219-239` (`get_model_history`); `pns_ai_chatboo/controllers/chatboo.py:422-455` (`/chatboo/sessions/save`) |
| PNS-36 | §3 «PNS-36» | `controllers/validators.py:385-402` (campos de `.format`); `controllers/context_builder.py:104-117` (`GuardedSandboxEnv.__getattr__`) |
| PNS-84 | §3 «PNS-84» | `models/key_pin_desk.py`, `touch` (`:111-124`) y `_drop_old` (`:177-182`); `security/ir.model.access.csv:81` |
| PNS-29 | §6.1 «PNS-29 (parte)» | `models/ai_provider.py:1016-1047` (`month_usage`); filtro de cuota en `models/ai_execution_engine.py:252-254` |
| PNS-18 | §6.1 «PNS-18» | `models/ai_execution_engine.py:252-263, 305-316` (`_without_external_after_local`) |
| PNS-26 (resto) | §5.6 «PNS-26 (resto)» | `utils/engine_tool_run.py:323-357` (`SAVEPOINT` por herramienta) y `:256-260, 306-321` |
| PNS-88 | §5.6 «PNS-88» | `utils/schema_fossils.py:69-97` (`XMLID_RENAMES`) |
| F4 | §8.7 «F4», §8.4 | `pns_ai_chatboo/static/src/js/chatboo_export.js`; método: a determinar en la entrega |
| D1 (ficha de la comparación) en el lienzo | §8.7 «D1», §8.3 | `pns_ai_chatboo/models/chatboo_canvas_page.py:25-176` (`write` de `owner_id`); regla del AI Administrator en `pns_ai_chatboo/security/security.xml:43-76` |
| M5 | §8.7 «M5 y M16», §8.2 | `pns_ai_chatboo/models/chatboo_async_request.py:1559-1586`, `cron_maintenance` |
| M16 | §8.7 «M5 y M16», §8.2 | `models/ai_fx_source.py:86-166`, `get_usd_fx` |

## 3. Al terminar

1. **LIYBEN:**
   - copia completa previa;
   - `-u` de los tres módulos;
   - `ai_log.agent_id` se pierde (decidido);
   - después: cron de la papelera activo, retención de 30 días, recargar idiomas y abrir sesiones
     antiguas de Chatboo.
2. **Informe al fabricante:** M10, M13, `collect_pin`, PNS-54, PNS-07, PNS-97, PNS-98, PNS-70, F4, la
   nota falsa sobre `agent_id` (comparación §9.3) y, como observación, la numeración de `pns_base`
   1.2.47 (§9.1). Sin rutas locales, kit, laboratorio, clientes ni personas.
3. **Limpieza:** staging `pns_demo`, `lab_pns_ai` / `lab_pns_ai_14` y `_fabricante/`.

## 4. Estado del entorno

- **`lab_pns_ai_3879_14`:** conserva las claves de los 4 proveedores y la clave MCP de admin, para las
  pruebas (decisión de Sergio del 23/10/2026).
- **LIYBEN:** usuarios externos archivados el 23/10/2026.

## 5. Seguimiento por parche

Estados (N11): aplicado → validado en laboratorio → validado en staging → en LIYBEN.

| N.º | Ficha | Entrega | Estado |
|---|---|---|---|
| 10 | PNS-83 (`collect_pin`) | E1′ | Adaptado a 3.1.879; validado en laboratorio (23/10/2026) |
| 11 | PNS-82 (`unlink` de la sesión) | E2′ | Adaptado a 3.1.879; pendiente |
| 12 | PNS-01 y PNS-02 (criterio de grupos), con M10 | E1′ | Adaptado a 3.1.879; validado en laboratorio (23/10/2026) |
| 13 | M10 (`create` de `ai.safe.operation`; `_cleanup_stuck_state`) | E1′ | Validado en laboratorio (23/10/2026) |
| 14 | M13 (`_unlink_retired_from_module`) | E1′ | Validado en laboratorio (23/10/2026) |
| 15 | PNS-07 (métodos con cursor propio en la lista del sandbox) | E1′ | Validado en laboratorio (23/10/2026) |
| 16 | PNS-54 (`check_identity`; token solo para el dueño) | E1′ | Validado en laboratorio (23/10/2026) |
| — | Parche de tests E0′ (datos de prueba de `test_change_journal` y `test_paap_core`) | E0′ | Validado en laboratorio (23/10/2026) |
