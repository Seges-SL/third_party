# Fase 3, parte 1 — laboratorio de pns_ai 3.1.879

- **Fecha:** 2026-10-22. **Rama:** `14.0-pns-ai-3879` (commit `5940e52`: `pns_base` 1.2.47,
  `pns_ai_mcp` 3.1.879, `pns_ai_chatboo` 2.1.538, sin cambios de Seges).
- **Contexto `odoo-dev 14`:** `lab_pns_ai_3879` (imagen `odoo-dev:14-lab_pns_ai_3879`, Dockerfile
  `infra/Dockerfile.14`), BD `lab_pns_ai_3879_14`, creada vacía con el paso 2. No se ha escrito en
  ninguna otra BD.
- **Referencias:** decisión N12 (`pns_ai_decisiones.md`), hoja `n12_decision_3879.md` §5, línea base de
  tests en `verificacion_seguridad_pns_ai.md` y fichas M10/M13 de
  `docs/specs/comparacion_pns_ai_3-1-879.md` §8.7.
- **Alcance:** condiciones 1 y 2 de §5, más P-8a y P-8b. Las condiciones 3 (P-6 ampliada, P-70) y 4
  (P-9a/b/e sobre `pns_demo`) quedan para la parte 2.

## Resumen

| Condición / prueba | Resultado |
|---|---|
| Condición 1 (paridad sin módulos que no se importan) | **CUMPLE** |
| Condición 2 (tests de `pns_ai_mcp` sin regresiones graves) | **CUMPLE** (ver matices en el paso 3) |
| P-8a (M13) | **Confirmado**: interno sin IA y portal borran los 53 contextos de fábrica |
| P-8b (M10) | **Confirmado**: el AI Administrator ejecuta planes como otro usuario; el caso `ir.cron` llega a ejecutar código como el admin |

## Paso 1 — Estado y paridad

| Comando | Resultado | Condición 1 |
|---|---|---|
| `odoo-dev 14 estado` | Contexto `lab_pns_ai_3879`, third_party montado desde la copia de trabajo (rama `14.0-pns-ai-3879`), BD aún no creada, contenedores activos. Sin avisos de contexto. | — |
| `odoo-dev 14 paridad pns_base,pns_ai_mcp,pns_ai_chatboo` | 3 por instalar, 9 dependencias comprobadas · sin código: 0 · **no se importan: 0** · librerías que faltan: 0. «Se pueden instalar». | **CUMPLE** |

No hace falta ninguna línea nueva en `infra/Dockerfile.14`.

## Paso 2 — Instalación

| Comando | Resultado |
|---|---|
| `odoo-dev 14 instalar pns_ai_chatboo` | **OK**: 0 bloqueantes, 0 tipos de aviso según el analizador. 23 módulos cargados en 63 s. Log: `~/odoo-dev/14.0/logs/instalar-20261022-164538.log`. |

- «Deleting field»: **0**. Tracebacks: **0**. Líneas ERROR/CRITICAL: **0**.
- 7 líneas WARNING, todas informativas: `DeprecationWarning` de `jinja2` (`collections`), etiquetas
  repetidas (`ai.log`: `client_label`/`client_display`; `ai.trusted.action`: `model_name`/`model_id`) y,
  ×3, `MCP: skip retired unlink for pns_ai_mcp (no skill files on disk)`.
- BD nueva: no está neutralizada (no viene de `bd-cargar`) y la instalación no ha desactivado crons ni
  servidores de correo.

## Paso 3 — Tests de `pns_ai_mcp`

| Comando | Total | Fallidos | Errores | Saltados | Línea base 3.1.782 (parches 1-6) |
|---|---|---|---|---|---|
| `odoo-dev 14 tests pns_ai_mcp` | 202 | 17 | 35 | 4 | 180 · 14 F · 31 E · 5 saltados |

Log: `~/odoo-dev/14.0/logs/tests-20261022-164729.log`.

**`pns_ai_chatboo`:** no trae carpeta `tests`, igual que en 3.1.782. No se ejecuta: no hay nada que
comparar.

### Comparación con la línea base

De los 52 fallos y errores, **42 son los mismos tests y por las mismas causas** que en la línea base
(contrato de `code_body`, grupo conversacional, sin proveedor ni `pns_ai_chatboo`, sin `product`,
imagen, origen de composición, `AI Writer` en `test_safe_plan_atomicity`, cursor propio en
`test_system_action`, superusuario en `test_context_unlink`, agentes nuevos en `test_bundle_locale`).

**Desaparecen (3):**

| Test | Motivo |
|---|---|
| `TestMcpAgent.test_resolve_inference_via_feature_key` | Ahora pasa. |
| `TestSkillCaptureReplace.test_wizard_create_rejects_unread_schema_keys` | El fabricante lo ha quitado. |
| `TestChatbooPendingCards.test_expired_pending_is_not_restored` | Renombrado: el archivo pasa a `test_pending_cards.py` (ver abajo). |

**Nuevos frente a la línea base (10):**

| Test | F/E | Causa (una línea) | ¿Grave? |
|---|---|---|---|
| `TestPendingCards.test_expired_pending_is_not_restored` | F | Es el test renombrado de `test_chatboo_pending_cards`; mismo fallo de la línea base (`create_date` que el ORM de 14 ignora). | No (ya estaba) |
| `TestChangeJournal.test_create_write_sequence_and_revert` | E | `test_change_journal` ya se importa (en 3.1.782 no se ejecutaba, PNS-50) y ejecuta el plan con `SUPERUSER_ID`, que no está en `AI Writer` → `PermissionError`. | No: datos de prueba |
| `TestChangeJournal.test_unlink_archives_then_revert_and_empty_trash` | E | Igual que el anterior. | No: datos de prueba |
| `TestChangeJournal.test_failed_execute_journals_outside_rollback` | F | No encuentra la fila `failed` del diario. Sin analizar a fondo; probablemente la misma falta de `AI Writer` o el cursor propio del test. | No (a confirmar) |
| `TestPaapCore.test_paap_i1_a_proposal_changes_nothing_and_hands_out_no_credential` | E | Archivo nuevo. `IntegrityError` en la FK `ai_safe_operation_user_id_fkey`: la operación se escribe en un cursor propio que no ve al usuario creado en la transacción del test (mismo patrón que `test_system_action` en la línea base). | No: incompatible con el test transaccional |
| `TestSkillCaptureReplace.test_skill_form_adding_lines_lifts_none` | E | `ValidationError` de `_check_code_body_contract` (`presentation_no_html`): test desfasado frente al contrato de `code_body`, misma familia que los 25 E de la línea base. | No |
| `TestSkillCaptureReplace.test_wizard_injects_unread_schema_keys` | E | Contrato de `code_body` (`result` int): misma familia. | No |
| `TestSkillCaptureReplace.test_wizard_lines_lift_none_policy` | E | Contrato de `code_body` (`result` int): misma familia. | No |
| `TestFlowLegend.test_legend_chips_include_svg_icons` | F | `9 != 8`: la leyenda tiene un chip más y el test no se ha actualizado (en 3.1.782 pasaba). | No: test desfasado |
| `TestMcpHttp.test_mcp_notification_accepted` | F | `Conversational AI is not allowed for this user`: la clave del fixture no tiene el grupo conversacional, misma familia que los 4 F de la línea base. | No |

**Condición 2: CUMPLE.** Ningún fallo nuevo indica un defecto funcional o de seguridad: son tests
desfasados, datos de prueba incompletos o tests incompatibles con los cursores propios en Odoo 14. Dos
matices:

- `test_change_journal` y `test_paap_core` (el diario y la papelera, PNS-37, y PAAP) **no tienen
  cobertura efectiva** en Odoo 14 mientras no se corrijan sus datos de prueba.
- Las protecciones sin cobertura de la línea base (`test_context_unlink`, tarjetas caducadas) siguen
  igual.

## Paso 4 — Permisos (§8.7)

Ejecutado con `odoo-dev 14 shell` sobre `lab_pns_ai_3879_14`, llamando a los métodos como lo haría un
RPC (`check_method_name` + `odoo.api.call_kw` con el entorno del usuario de prueba).

### P-8a (M13) — `ai.context.unlink_retired_from_module`

Se hizo dentro de un `SAVEPOINT` que se deshizo después: no queda nada en la BD.

| Usuario de prueba | Grupos de IA | Llamada | Contextos de fábrica de `pns_ai_mcp` (antes → después) | Esperado si está bien |
|---|---|---|---|---|
| Interno (`base.group_user`) | Ninguno | **Aceptada**, devuelve 53 | 53 → **0** | `AccessError`, 53 → 53 |
| Portal (`base.group_portal`) | Ninguno | **Aceptada**, devuelve 53 | 53 → **0** | `AccessError`, 53 → 53 |

Tras deshacer: 53. **M13 confirmado** en 3.1.879, también desde portal: se borran todos los
contextos de fábrica con `rel_path` (todos los 53 los tienen).

### P-8b (M10) — `create` de `ai.safe.operation` + `cleanup_stuck_state`

Usuario atacante: «P-8b AI Administrator» (uid 10; `base.group_user` + `group_ai_admin`, sin
`base.group_system` ni `base.group_erp_manager`). Estas pruebas **sí se confirmaron** en la BD del
laboratorio: `cleanup_stuck_state` ejecuta en cursores propios que solo ven datos confirmados.

| Caso | Identidad suplantada | `create` de la operación | `cleanup_stuck_state` | Efecto en la BD |
|---|---|---|---|---|
| 1. `write` en un contacto (ficha literal) | uid 2 (admin) | **Aceptado** | **Aceptado**; el plan se ejecuta como uid 2 | Rechazado en la ejecución: en esta BD vacía el admin no está en `AI Writer`. Operación `cancelled`, contacto sin cambios. |
| 1 bis. `write` en un contacto | Víctima de prueba (uid 11: `base.group_system` + `AI Writer` + creación de contactos) | **Aceptado** | **Aceptado** (`executed: 1`) | Contacto con `comment = 'P-8b'` y **`write_uid = 11`**; fila del diario con `create_uid = 11`. Operación `executed`. |
| 2. `create` de `ir.cron` (`res.partner`, `state='code'`, código inocuo que escribe un marcador en el contacto, `user_id` = 2, `nextcall` pasado) | Víctima de prueba (uid 11) | **Aceptado** | **Aceptado** (`executed: 1`) | Se crea el `ir.cron` (`create_uid = 11`, `user_id = 2`, activo). La cúspide no lo frena. Al dispararlo, el contacto queda con el marcador y **`write_uid = 2`**: el código corre como el admin. |

- En el intento 1 bis anterior, la víctima no tenía «Contact Creation» y el plan falló con
  `AccessError`, ya **con la identidad de la víctima**. Se le añadió `base.group_partner_manager` y se
  repitió.
- El servidor del laboratorio no ejecutó el cron en 150 s (no procesa crons en esta BD). Se disparó con
  `method_direct_trigger` desde el shell, que ejecuta la acción con `cron.user_id`, igual que el
  planificador.
- No se probó el plan que se añade `base.group_system`, porque §8.7 lo pide solo «en la rama»
  (3.1.782 con el parche 12).

**M10 confirmado** en 3.1.879:

- Un AI Administrator sin Ajustes crea una operación ya confirmada a nombre de otro usuario y la hace
  ejecutar con `cleanup_stuck_state`.
- El límite real es lo que pueda hacer el usuario suplantado: necesita `AI Writer` para los pasos CRUD.
- La cúspide no cubre `ir.cron`, así que se llega a ejecutar código como el usuario que se ponga en el
  cron (aquí, el admin).

### Datos de prueba de P-8b (ya no existen)

Al terminar la parte 1 quedaron en `lab_pns_ai_3879_14` los usuarios `p8b_aiadmin` (uid 10) y
`p8b_victima` (uid 11), el contacto «P-8b contacto de prueba» (id 43), las `ai.safe.operation` 1 a 4
con sus filas de `ai.change.journal` y el `ir.cron` 18 «P-8b cron» (activo, inocuo). P-8a no dejó nada.

La BD se recreó antes de la parte 2 y esos datos ya no están. Comprobado el 23/10/2026 con SQL de solo
lectura (`BEGIN READ ONLY` … `ROLLBACK`) en `lab_pns_ai_3879_14`:

| Consulta | Filas |
|---|---|
| `res_users` con `login LIKE 'p8b\_%'` | 0 |
| `res_partner` «P-8b contacto de prueba» | 0 |
| `ir_cron` «P-8b cron» | 0 |
| `ai_safe_operation` / `ai_change_journal` (todas) | 0 / 0 |

## Pendiente (parte 2, no hecho)

- Condición 3: P-6 ampliada y P-70. **Hecho: ver «Parte 2» (abajo).**
- Condición 4: P-9a, P-9b y P-9e sobre una copia de `pns_demo`. **Hecho: ver «Parte 3».**

## Parte 2 — P-6 ampliada y P-70 (condición 3) y comprobación visual de P-9e

- **Fecha:** 2026-10-23 (horas en UTC). **Contexto `odoo-dev 14`:** `lab_pns_ai_3879`, BD
  `lab_pns_ai_3879_14` (recreada, con `pns_ai_chatboo` y `sale_management`), third_party en la rama
  `14.0-pns-ai-3879` (3.1.879 sin cambios de Seges). Sin avisos de contexto.
- **Escrito:** en `lab_pns_ai_3879_14`, solo lo que hizo Sergio en la interfaz (proveedores, cadena,
  grupos y turnos de Chatboo). En `pns_demo_p9`, solo `odoo-dev 14 bd-claves admin` y
  `bd-claves u1,u3` (autorizados por Sergio). No se ha leído ni escrito ninguna clave: las
  consultas a `ai_provider` solo miran si `api_key` está vacía.
- **Comprobaciones tras cada caso** (solo lectura): log del contenedor desde el inicio del caso
  («_finalize fresh-cursor failed», «could not serialize access», WARNING/ERROR);
  `pg_stat_activity` de la BD con `state LIKE 'idle in transaction%' OR wait_event_type = 'Lock'`;
  `chatboo_async_request` (estado, `session_saved` en `done_meta`, prompt presente en
  `chatboo_session.messages`); `ir_attachment` nuevos (`id, res_model, res_id`); `ai_log` para saber
  qué proveedor respondió.

### Resumen

| Prueba | Resultado | Condición 3 |
|---|---|---|
| P-6 ampliada: bloqueo de sesión (PNS-94) | En los 11 casos ejercitados (23 jobs): **ningún bloqueo**. Todos los jobs en `done` con `session_saved: true` y el turno en la sesión, `pg_stat_activity` siempre limpio y 0 «_finalize fresh-cursor failed» | **CUMPLE** |
| P-6 ampliada: log sin «could not serialize access» | **1 en Chatboo**: `update_last_used` al cargar la sesión justo después de que un turno la confirmara (caso c). Es el punto 4 previsto en la ficha PNS-94 (§5.6). Hay otro en la configuración de un proveedor, que no es de Chatboo | **NO CUMPLE** el criterio literal (residuo previsto; sin bloqueo) |
| P-6 ampliada: adjuntos (PNS-98) | Clip (2 CSV), SVG y PDF con `res_model`/`res_id` vacíos; imágenes enlazadas a `chatboo.session` | Lo esperado (PNS-98 sigue) |
| P-70 (PNS-70) | Tras abrir Chatboo, `window.Chart` pasa de 2.x (Odoo) a 4.4.8. Ventas → Análisis: se dibuja, con errores «Invalid scale configuration for scale: xAxes/yAxes». Tablero de Facturación: **los gráficos no cargan bien** | **NO CUMPLE** |
| P-9e, comprobación visual | Sesiones 5, 16 y 27 de `pns_demo_p9`: tablas con formato, fichas, ordenación y gráfico donde hay columnas numéricas; sin errores en la consola | **CUMPLE** (condición 4) |
| **Condición 3** | Falla P-70, y el log de P-6 tiene un «could not serialize access» de Chatboo | **NO CUMPLE** tal como está redactada |

Según §5 de `n12_decision_3879.md`, si falla una condición se vuelve a b). La decisión es de Sergio
(tomada el 23/10/2026: la condición 3 no cumple por P-70, se acepta como excepción y b′ sigue; ver
«Valoración de las condiciones», al final). Para valorarlo:

- **P-70** ya figuraba como PARCIAL en §5.6 («el choque de Chart.js cambia de sentido»). Ahora está
  confirmado, también en el tablero de Facturación. El origen está en un solo sitio: Chatboo carga
  `chart.umd.min.js` 4.4.8 en `window.Chart` al abrir el chat
  (`pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js:12-33`), aunque el motor configurado es
  `echarts`.
- **El «could not serialize»** es el residuo 4 de PNS-94 («El conflicto de `last_used_date` visto
  en R6 puede seguir en el log»). Una de dos cargas simultáneas de la sesión devolvió `status: error`
  y la otra la cargó bien. No queda nada colgado.

### Configuración (paso 1)

Hecha por Sergio en la interfaz y comprobada por SQL:

| Elemento | Estado |
|---|---|
| Proveedor 1 «Gemini 3.6 flash» | Activo, `openai`, endpoint de Gemini compatible con OpenAI, `models/gemini-3.6-flash`, Conversation + Vision, con clave |
| Proveedor 2 «Gemini 3.5 flash» | Igual con `models/gemini-3.5-flash` (también con Vision) |
| Proveedor 3 «OVH» (añadido en el caso b) | `openai`, `https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions`, primero `Qwen3.5-9B` y luego `Qwen3.5-397B-A17B`, Conversation + Vision |
| Proveedor 4 «Gemini 3.5 flash lite» (añadido en el caso c) | `models/gemini-3.5-flash-lite`, Conversation + Vision |
| Cadena del agente Chatboo (id 3) | Al final: 3.6 → 3.5 → 3.5 flash lite → OVH, todas activas |
| Grupos del admin (uid 2) | AI Administrator y AI Conversational (más Writer, External URL y External API) |

El primer «hecho» no llegó al servidor: no hubo ninguna petición en el log ni proveedores en ninguna
BD. Se repitió en `localhost:8169` / `lab_pns_ai_3879_14`.

### P-6 ampliada (paso 2)

Línea base: adjuntos > 410, jobs > 0, sesiones > 0. Columnas: «Log» = «fresh-cursor failed» /
«could not serialize access» desde el inicio del caso; «PG» = filas con `idle in transaction` o
`wait_event_type = 'Lock'`.

#### Caso 1 — Turno con imagen, proveedor que responde

| Qué se hizo | Comprobaciones | Resultado |
|---|---|---|
| Contactos (lista), sesión nueva 1, PNG de 199,7 KB, «¿Qué ves en esta imagen?» (07:31-07:32) | Job 1 `done` en 26 s, `session_saved: true`, turno en la sesión. Log 0 / 0. PG 0. Adjunto 411 → `chatboo.session` / 1. El indicador de espera desaparece sin recargar. Gemini 3.6 devolvió primero un HTTP 503 y el motor hizo *failover*; la respuesta final es de `gemini-3.6-flash` | **CUMPLE** |

#### Caso 5 — Turno siguiente al de la imagen

| Qué se hizo | Comprobaciones | Resultado |
|---|---|---|
| Misma sesión 1, desde Ventas → Presupuestos (lista), solo texto: «¿En qué pantalla estoy ahora y cuántos registros hay?» (07:35) | Job 2 `done` en 3 s, `session_saved: true`, turno en la sesión. Log 0 / 0. PG 0. Sin adjuntos. Respuesta: lista de `sale.order`, 20 registros (correcto: `count(*)` = 20). `last_screen_context` pasa de `res.partner` a `sale.order`. El del turno con imagen también se había guardado (en 3.1.782 con el parche 6 se podía perder) | **CUMPLE** |

#### Caso 2 — Turno con imagen y error del proveedor

| Qué se hizo | Comprobaciones | Resultado |
|---|---|---|
| Endpoint de los dos proveedores Gemini con una `X` al final (HTTP 404), PNG, «¿Qué ves?», sesión 1 (07:39). Endpoints restaurados a las 07:40 | Job 3 `done` en 2 s, `session_saved: true`, turno y error en la sesión. Mensaje: «Fallaron todos los proveedores del agente pns_ai_chatboo». Log 0 / 0. Solo los ERROR/WARNING esperados (404 ×2, *failover* y «scanned PDF transcription failed», que es el intento previo de transcribir la imagen, `chatboo_async_request.py:922`). PG 0. Adjunto 412 → `chatboo.session` / 1 | **CUMPLE** |
| **Repetición con 429 real** (escenario original del bloqueo de staging): caso b, primer intento, 6 turnos (jobs 8-13, sesión nueva 3, 08:09-08:10) con HTTP 429 `RESOURCE_EXHAUSTED` (cuota gratuita de 20 peticiones al día por modelo) en los dos proveedores | Los 6 jobs `done` en 1-2 s, `session_saved: true`, turno en la sesión. Log 0 / 0. PG 0. Fallo por cuota del proveedor: no cuenta como fallo de la prueba, pero confirma el arreglo con un 429 de verdad | **CUMPLE** |

#### Caso 3 — Turno de solo texto

| Qué se hizo | Comprobaciones | Resultado |
|---|---|---|
| Ficha de Deco Addict, sesión nueva 2, «Resúmeme este contacto.» (07:41) | Job 4 `done` en 12 s, `session_saved: true`, turno en la sesión. Log 0 / 0. PG 0. Sin adjuntos. Respuesta correcta (3 facturas publicadas, base 590 000,00, comprobado por SQL) | **CUMPLE** |

#### Caso 4 — Cancelación de un turno en curso

| Qué se hizo | Comprobaciones | Resultado |
|---|---|---|
| PNG y una petición larga, sesión 2 (08:01-08:03). Primer intento: terminó antes de poder cancelar. Segundo: «detener» a los pocos segundos | Job 5 `done` (32 s, terminado). Job 6 `done` (23 s) con `cancel_requested = true`, respuesta «⏹ Generación cancelada.», `session_saved: true`, en la sesión. Log 0 / 0, sin WARNING. PG 0. Adjuntos 413 y 414 → `chatboo.session` / 2 | **CUMPLE** |

#### Caso (a) — Dos CSV por el clip

| Qué se hizo | Comprobaciones | Resultado |
|---|---|---|
| `ventas_t1.csv` y `ventas_t2.csv` en el mismo turno, «Une estos dos CSV…», sesión 2 (08:06) | Job 7 `done` en 9 s, `session_saved: true`, turno en la sesión. Tabla correcta (Mesa 27 / 12 150; Silla 71 / 8 520). Log 0 / 0 (solo «Large result JSON», informativo). PG 0. **Adjuntos 415 y 416 (`text/csv`) con `res_model` y `res_id` vacíos → PNS-98** | **CUMPLE** (PNS-98 anotado) |

#### Caso (b) — Respuesta con SVG en línea

| Qué se hizo | Comprobaciones | Resultado |
|---|---|---|
| Primer intento: ver el caso 2 (429 en todos los proveedores) | — | No cuenta (cuota) |
| Segundo intento con OVH (`Qwen3.5-9B`) en la cadena, sesión 3 (08:57-08:59) | Job 14 `done` en 2 min 13 s, `session_saved: true`, turno en la sesión. *Failover* 429 → 429 → OVH, 2 rondas. Log 0 / 0. PG 0. **Adjunto 417 (`image/svg+xml`, 2 135 bytes) con `res_model` y `res_id` vacíos → PNS-98**; los mensajes no lo citan. En el chat no se vio el dibujo: Qwen devolvió el SVG como código. La ruta de guardado del SVG sí se ejecutó (se creó el adjunto) | **CUMPLE** (PNS-98 anotado; el dibujo no se vio por el modelo) |

#### Caso (c) — Exportar a PDF desde el chat (`fulfill_client_export`)

| Qué se hizo | Comprobaciones | Resultado |
|---|---|---|
| Primer intento con OVH `Qwen3.5-9B`, sesión 2 (09:02) | Job 15 `done` en 22 s, `session_saved: true`. Qwen respondió con un bloque Python con **datos inventados** (Producto A/B/C) y sin documento PDF: no se llamó a `fulfill_export`. Log 0 «fresh-cursor». PG 0 | No ejercitado (modelo) |
| Segundo intento: respondió Gemini 3.5 flash lite, sesión 2 (09:09-09:10). Ficha de PDF → «Preparar y descargar» | Job 16 `done` en 6 s, `session_saved: true`, turno en la sesión. `POST /chatboo/sessions/fulfill_export` 200 (09:10:04). **Adjunto 418 (`application/pdf`) con `res_model` y `res_id` vacíos → PNS-98.** PG 0. Log: 0 «fresh-cursor», **1 «could not serialize access due to concurrent update»** (09:10:06, abajo) | **NO CUMPLE** (criterio del log; sin bloqueo) |

El «could not serialize» de las 09:10:06:

- **Qué:** `SELECT id FROM chatboo_session WHERE id = 2 FOR UPDATE SKIP LOCKED` en `update_last_used`
  (`pns_ai_chatboo/models/chatboo_session.py:746-754`), desde `/chatboo/sessions/load`.
- **Efecto:** el controlador lo registra como «Error loading session» y devuelve `status: error`
  (`pns_ai_chatboo/controllers/chatboo.py:297-320`).
- **Cuándo:** hubo dos `load` a la vez (09:10:06,073 y ,076), 20 ms después del commit del turno en
  la sesión (`write_date` 09:10:06,053). La otra carga fue bien y no quedó ninguna conexión colgada.
- **Encaje:** es el punto 4 de la ficha PNS-94 de §5.6 (en REPEATABLE READ, `SKIP LOCKED` no evita
  el 40001 si la fila ha cambiado después de la instantánea).

El PDF descargado tiene dos defectos. No afectan a la condición 3:

- **Datos inventados.** Salen los de Qwen del turno anterior (Producto A/B/C), que el modelo tomó
  del historial de la sesión 2.
- **HTML como texto.** Antes de la tabla, el PDF muestra como texto el HTML del bloque de tabla, con
  los `_` de `o_ai_*` perdidos (`oaitableblock`, `oaidatatable`). En `messages`, el turno empieza
  por `<div class="o_ai_table_block" …>` seguido de la prosa. En el chat se ve bien. Es un fallo del
  exportador a PDF del lado del cliente (`chatboo_export.js`), a registrar.

#### Caso (d) — Recargar con un turno en marcha

| Qué se hizo | Comprobaciones | Resultado |
|---|---|---|
| Primer intento con flash lite, sesión 2 (09:40-09:41) | Jobs 17 (6 s) y 18 (8 s) `done`, `session_saved: true`. La recarga (`GET /web`, 09:41:30) llegó 1 s **después** del fin del job 18 | No ejercitado (turno demasiado corto) |
| Segundo intento: petición de un informe de 3 000 palabras, F5 a los 2 s, sesión 2 (09:45) | Job 19 empieza a las 09:45:27; **F5 a las 09:45:29, con el turno en marcha**; termina a las 09:45:37 (10 s), `done`, `session_saved: true`, en la sesión. Cargas de la sesión a las 09:45:39-40 y, tras una segunda recarga, a las 09:45:57, con el turno completo. Log 0 / 0. PG 0. Sergio: el F5 corta la vista, el turno termina antes de volver a entrar y al entrar ya está la respuesta | **CUMPLE** |

#### Adjuntos nuevos

| id | `res_model` | `res_id` | Tipo | Origen | |
|---|---|---|---|---|---|
| 411 | `chatboo.session` | 1 | `image/png` | Caso 1 | Bien |
| 412 | `chatboo.session` | 1 | `image/png` | Caso 2 | Bien |
| 413 | `chatboo.session` | 2 | `image/png` | Caso 4 (job 5) | Bien |
| 414 | `chatboo.session` | 2 | `image/png` | Caso 4 (job 6) | Bien |
| 415 | — | — | `text/csv` | Caso (a) | **PNS-98** |
| 416 | — | — | `text/csv` | Caso (a) | **PNS-98** |
| 417 | — | — | `image/svg+xml` | Caso (b) | **PNS-98** |
| 418 | — | — | `application/pdf` | Caso (c) | **PNS-98** |

#### Otras observaciones

- **«could not serialize access due to concurrent delete» (09:07:38), fuera de Chatboo:**
  - Salió en el `UPDATE ai_provider SET usage_support …` de «Test Connection» de un proveedor
    provisional «Gemini 3.7 flash» (id 5).
  - La prueba tardó 145 s (la sonda de voz dio *ReadTimeout* de 15 s) y, mientras tanto, se borró
    el proveedor. Odoo reintentó y acabó en «El registro no existe».
  - Es configuración, sin relación con PNS-94.
- **«+ Nuevo»:** en los casos 4, (a) y (d) los turnos fueron a la sesión 2 porque no se pulsó (no
  llegó ningún `/chatboo/sessions/create`). No afecta a los resultados.
- **Proveedores:**
  - Gemini dio HTTP 503 en el caso 1 y agotó la cuota gratuita (429) desde las 08:09.
  - `Qwen3.5-9B` de OVH no sigue el formato ni las herramientas de Chatboo e inventa datos. Para
    las pruebas siguientes se recomienda `Qwen3.5-397B-A17B` (catálogo público de OVH AI Endpoints:
    Vision + Reasoning, 262k).
  - Selector de proveedor del chat: los jobs 1 a 16 empezaron por el proveedor 1 y recorrieron la
    cadena. Los jobs 17 a 19 se hicieron con Gemini 3.5 flash lite elegido (`provider_id = 4`, sin
    *failover* en `ai_log`).

### P-70 (paso 3)

Para saber qué Chart.js estaba activo se usó en la consola:
`typeof Chart === 'undefined' ? 'sin Chart' : (Chart.version || (Chart.defaults && Chart.defaults.global ? '2.x (Odoo)' : '¿?'))`.
El de Odoo 14 es la v2.9.3 (`web/static/lib/Chart/Chart.js`), sin `Chart.version`.

| Paso | `window.Chart` | Lo que se ve | Consola |
|---|---|---|---|
| Ventas → Informes → Ventas, vista gráfico, F5 con el chat cerrado; cambio de tipo | `2.x (Odoo)` | Bien | — |
| Abrir Chatboo y pedir un gráfico de barras de ventas por cliente | `4.4.8` | El gráfico de Chatboo, bien | — |
| Volver a la vista gráfico sin F5 y cambiar barras → líneas → circular | `4.4.8` | Se dibujan | **«Invalid scale configuration for scale: xAxes»** y **«… yAxes»** (`chart.umd.min.js:19:85494`), en cada cambio |
| Facturación → Tablero (acción 335; el admin no tiene `account.group_account_readonly`, que es lo que da el menú) con F5 y el chat cerrado | `2.x (Odoo)` | Bien | — |
| Abrir y cerrar Chatboo | `4.4.8` | — | — |
| Volver al tablero sin F5 | `4.4.8` | **Los gráficos de los diarios no cargan bien** | Los mismos errores `xAxes`/`yAxes` (y un 404 de `chart.umd.js.map`, solo de las herramientas de desarrollo) |

**NO CUMPLE.** Se confirma PNS-70 tal como lo describe §5.6:

- Chatboo carga Chart.js 4.4.8 en `window.Chart` al abrir el chat
  (`chatboo_heavy_libs.js:12-33`, en `VENDOR` aunque el motor sea `echarts`).
- `ajax.loadJS` de Odoo no vuelve a cargar su Chart.js 2.
- Las vistas gráfico y el tablero de diarios pintan con la API v4 y opciones v2 (`scales.xAxes/yAxes`).
- Con F5 vuelve la 2.x hasta que se abre otra vez el chat.

### Comprobación visual de P-9e (paso 4)

- **Acceso:** `odoo-dev 14 bd-claves admin --bd pns_demo_p9` y, como las sesiones son de otros
  usuarios y `/chatboo/sessions/load` solo deja abrirlas a su dueño, `bd-claves u1,u3 --bd
  pns_demo_p9` (los dos con autorización de Sergio). Se entró desde el selector de bases de datos en
  una ventana privada. Proveedores desactivados: no se lanzó ningún turno.
- **Sesiones:** 5 y 27 son de `u1` (uid 8) y 16 de `u3` (uid 10).

| Sesión | Tablas (formato) | Fichas | Ordenar por columna | Cambio a gráfico | Consola |
|---|---|---|---|---|---|
| 5 | Con formato | Bien | Bien | Se dibuja y se vuelve a los datos | Sin errores |
| 27 | Con formato | Bien | Bien | Sin botón «Gráfico» | Sin errores |
| 16 | Con formato | Bien | — (las tablas tienen una sola fila) | Sin botón «Gráfico» | Sin errores |

El botón «Gráfico» sale donde hay datos numéricos. Análisis de los `data-ai-dataset` de cada sesión:

- **Sesión 5:** es la única con una tabla con una columna numérica (`pais` / `total_empresas`).
- **Sesión 27:** dos tablas de texto (1 y 40 filas).
- **Sesión 16:** tablas de una fila y 7 columnas de texto.

La ausencia del botón en 27 y 16 es lo esperado y no indica ninguna pérdida.

**CUMPLE.** El historial reescrito por el `-u` (marcas `o_ai_*` / `data-ai-*`) se pinta y funciona
con el cliente de 3.1.879. Queda sin hacer la parte de §9.5 que abre la sesión con el cliente
3.1.782 sobre la BD actualizada (fuera del encargo).

### Queda en el entorno (parte 2)

- **`lab_pns_ai_3879_14`:**
  - Proveedores 1 a 4 activos, con las claves de Sergio, y la cadena de Chatboo.
  - Sesiones 1 a 3, jobs 1 a 19 y adjuntos 411 a 418 (415 a 418 sueltos, PNS-98).
  - Conviene quitar las claves o borrar la BD al acabar.
- **`pns_demo_p9`:** contraseña `prueba` y sin 2FA para `admin`, `u1` y `u3`. Borrada el 23/10/2026
  (ver «Queda en el entorno» de la parte 3).
- **Scratchpad de la sesión:** CSV de prueba y script de comprobación (temporales).

## Parte 3 — Pruebas de actualización P-9a, P-9b, P-9e y P-9f (condición 4)

- **Fecha:** 2026-10-22. **Contexto `odoo-dev 14`:** `lab_pns_ai_3879`, sin cambios (BD del contexto:
  `lab_pns_ai_3879_14`, que no se ha tocado). **Código:** 3.1.879 (rama `14.0-pns-ai-3879`).
- **BD de la prueba:** `pns_demo_p9`, copia del staging `pns_demo` (3.1.782 con los parches 1 a 12),
  volcado `~/Descargas/pns_demo_p9_20261022.dump` (`pg_dump -Fc`). Excepción puntual a N9 autorizada
  por Sergio; la BD y el volcado se borran al cerrar la fase 3. Sin filestore (el volcado no lo trae).
- **Solo se ha escrito en `pns_demo_p9`:** la carga y neutralización del kit, `UPDATE ai_provider SET
  active = false` y el `-u`. No se han leído las columnas `api_key` de `ai_provider` ni ninguna columna
  de clave o hash de `ai_mcp_user` (solo los nombres de columna, en P-9a).
- Consultas y resultados completos (solo lectura, `BEGIN READ ONLY`): en el scratchpad de la sesión
  (`p9_consultas.sql`, `p9_antes.txt`, `p9_despues.txt`, `p9_foto*.txt`). Las tablas de abajo recogen
  lo que importa.

### Resumen

| Prueba | Resultado frente a §9.5 | Condición 4 |
|---|---|---|
| P-9a | Lo esperado: `key_pin*` fuera, `chatboo_async_request` intacta, cinco parámetros `pns_ai.*` sin XML ID y con el mismo valor, ningún `mcp_*` y los mismos recuentos por `origin` | **CUMPLE** |
| P-9b | **La columna `ai_log.agent_id` desaparece** (`column "agent_id" does not exist`); se pierde el agente de 978 de 987 filas. Tiene razón nuestra comparación (U9), no la auditoría del fabricante | **CUMPLE** (pérdida prevista en §9, U9) |
| P-9e | 10 → 0 sesiones con marcas antiguas; las 17 marcas presentes pasan a `o_ai_*` / `data-ai-*`; en las sesiones 5, 16 y 27 la longitud baja exactamente 5 por marca y, deshecho el renombrado, el contenido es idéntico byte a byte | **CUMPLE** (sin comprobación visual) |
| P-9f | `latest_version` 14.0.1.2.47 / 14.0.3.1.879 / 14.0.2.1.538; paridad completa | **CUMPLE** |
| **Condición 4** | Las pérdidas son las de §9 (U5, U6, U9, U15, U16, U17 bis) y nada más | **CUMPLE** |

### Paso 1 — Carga

| Comando | Resultado |
|---|---|
| `odoo-dev 14 ayuda` | `bd-cargar <archivo> [--bd NOMBRE]` acepta `.dump`; en el script, `*.dump` va a `pg_restore --no-owner --no-acl` (`entorno.sh:687`). El volcado empieza por `PGDMP` (formato `-Fc`). `--bd` solo cambia la BD de ese comando (`bd_contexto`, `entorno.sh:153-159`), no el estado del contexto. |
| `odoo-dev 14 bd-cargar ~/Descargas/pns_demo_p9_20261022.dump --bd pns_demo_p9` | Cargada, log de `pg_restore` vacío (sin errores). **Neutralizada:** `odoo_dev.neutralizada` = 2026-10-22 17:36:41; crons activos: 0. |
| Paridad que lanza `bd-cargar` | BD: 23 instalados · 20 iguales · **3 versión distinta** (lo esperado): `pns_base` 14.0.1.2.32 → 14.0.1.2.47, `pns_ai_mcp` 14.0.3.1.782 → 14.0.3.1.879, `pns_ai_chatboo` 14.0.2.1.453 → 14.0.2.1.538 · sin código 0 · no se importan 0. |
| | **Fallo del kit (no de la copia):** la misma salida dice «SIN CÓDIGO …pns_demo_p9_20261022.dump» y «la instalación FALLARÁ». `cmd_paridad` toma `ARGS[0]`, que en `bd-cargar` es la ruta del volcado, como lista de módulos. No afecta a la prueba. |
| `UPDATE ai_provider SET active = false` | 2 filas (estaba activo «Gemini AI»). Después: 0 activos de 2. |

### Paso 2 y 4 — P-9a (esquema, parámetros, XML ID y `origin`)

| Consulta | Antes | Después | Esperado (§9.5) | |
|---|---|---|---|---|
| Columnas de `ai_mcp_user` | Con `key_pin`, `key_pin_used`, `key_pin_killed` | Sin ellas | `key_pin*` fuera (U5) | Sí |
| Columnas de `chatboo_async_request` | 25 | Las mismas 25 | Intactas (U17) | Sí |
| Columnas de `ai_log` | 34, con `agent_id` | Sin `agent_id`; nuevas `provider_id` (U13) y `client_display` | Ver P-9b | Sí |
| Columnas de `chatboo_session` | 23 | + `canvas_design`, `canvas_open`, `canvas_rev`, `canvas_title`, `canvas_turn` | Nuevas (U17) | Sí |
| Parámetros `pns_ai%` | 23; `pns_ai_chatboo.chart_engine`, `default_show_mode`, `download_max_bytes`, `xlsx_float_decimals`, `xlsx_thousands` | 26; esos cinco como `pns_ai.*`, **con el mismo valor** (`echarts`, `show-table`, `15728640`, `2`, `True`). Nuevos: `pns_ai_admin`, `pns_ai_chatboo` y `pns_ai_decision.fossil_acl_security_agent` | Cinco renombrados (U6); una marca por agente (U7) | Sí |
| XML ID de `ir.config_parameter` | 6 (`icp_chatboo_*`) | 1: `icp_chatboo_history_retention_days` | Los cinco sin XML ID; queda el de retención (U19) | Sí |
| XML ID `mcp_*` de `pns_ai_mcp` | 0 | 0 | Ninguno (U3) | Sí |
| `ai_log` por `origin` | `chatboo` 950 · `internal` 25 · `mcp_client` 12 | Igual | Mismos recuentos (U10) | Sí |
| `ai_change_journal` por `origin` | `chatboo` 5 · `mcp_client` 2 | Igual | Mismos recuentos (U10) | Sí |
| Valor de selección `chatboo` | — | En `ai.log` y `ai.change.journal`, con XML ID `pns_ai_chatboo.selection__…__origin__chatboo` | Pasa a Chatboo (U10) | Sí |
| Totales | `ai_log` 987 · diario 7 · sesiones 30 · `chatboo_async_request` 19 | Igual | — | Sí |

**Foto ampliada** (todas las tablas `ai_*`, `chatboo_*` y `pns_*`: columnas y número de filas;
`ir_model_data` de `pns_*`; adjuntos):
- **Columnas quitadas:** solo `ai_log.agent_id`, las tres `key_pin*` y `ai_skill_capture_wizard.from_chatboo`
  (transitorio, pasa a `from_chat`; U17 bis).
- **Filas:** ninguna tabla pierde filas. Crecen `ai_context` 58 → 61 (`page_tab`, `discovery_page_tab`,
  `discovery_page_tab_es_ES`), `ai_skill` 10 → 13 (`cash_forecast`, `customer_360`, `pipeline`, activas),
  `ai_skill_param_line` 10 → 15 y las relaciones de agente (U15). Tablas nuevas vacías: lienzo (U17),
  `ai_provider_usage_wizard` (U14) y `ai_skill_required_group_rel`.
- **Resiembra (U15, D38):** el `-u` reescribe (`write_date`) 56 de los 58 contextos previos, 7 de las 10
  skills previas y los 4 agentes. Es lo previsto en §9; aquí no se puede saber si alguna tenía texto
  editado a mano.
- **Agente `pns_ai_decision`:** sigue, activo (U11).
- **Adjuntos** de `chatboo.session` y sueltos (10 y 1): sin cambios.
- **Crons:** uno nuevo, `pns_ai_mcp.ir_cron_ai_journal_trash` (U12). El kit avisó de que el `-u` lo había
  activado y lo desactivó (copia neutralizada). **En producción quedará activo.**

### Paso 3 — `-u`

| Comando | Resultado |
|---|---|
| `odoo-dev 14 actualizar pns_base,pns_ai_mcp,pns_ai_chatboo --bd pns_demo_p9` | **OK**: 0 bloqueantes y 0 tipos de aviso según el analizador. 23 módulos en 49,7 s. Log: `~/odoo-dev/14.0/logs/actualizar-20261022-173831.log`. |

- **Tracebacks:** 0. **ERROR/CRITICAL:** 0. **WARNING:** 6, los mismos tipos que en la instalación de la
  parte 1 (`jinja2`, etiquetas repetidas y, ×2, `skip retired unlink for pns_ai_mcp`).
- **«Deleting field»: 7.**

  | Campo | ¿Tenía columna? | En §9 |
  |---|---|---|
  | `ai.log.agent_id` | Sí: **se borra con sus datos** | U9 |
  | `ai.mcp.user.key_pin`, `key_pin_used`, `key_pin_killed` | Sí (ya tiradas por `drop_leftover_columns`) | U5 |
  | `ai.skill.capture.wizard.from_chatboo` | Transitorio | U17 bis |
  | `ai.log.agent_display`, `ai.mcp.user.key_pin_html` | No (no estaban en `information_schema` antes) | Calculados que acompañan a U9/U5; sin datos |

- **`agent_id`:** solo las líneas del borrado del campo (`Deleting 2583@ir.model.fields
  (pns_ai_mcp.field_ai_log__agent_id)` y su «Deleting field»).
- **`DROP`:** 11 líneas «`pns_ai_mcp: DROP leftover …`» (`ai_schema_fossil.py:29-33`). El log sale siempre,
  porque es un `DROP TABLE IF EXISTS`: ninguna de las 11 tablas existía antes (foto ampliada). Ningún
  otro `DROP` en el log.
- Al final, el core borra dos `ir.model.data` más (ids 9161 y 9187). Según la foto, el único cambio que
  encaja es el valor de selección `chatboo` de `origin`, que ahora tiene XML ID de `pns_ai_chatboo`.
  Esto se deduce, no se ha comprobado: los nombres no se guardaron antes. Sin efecto en filas (los
  recuentos por `origin` no cambian).

### P-9b — `ai_log.agent_id`

| | Antes | Después | Esperado |
|---|---|---|---|
| `SELECT count(*) FROM ai_log WHERE agent_id IS NOT NULL` | **978** (de 987) | `ERROR: column "agent_id" does not exist` | Auditoría: sigue. Comparación §9.2 U9: el core la borra |
| Log | — | `Deleting field ai.log.agent_id` | — |

**La columna desaparece.** La auditoría del fabricante («el `-u` ya no tira … `ai_log.agent_id`») es
falsa. Nuestra comparación (U9) es correcta: quitar el campo de `LEFTOVER_COLUMNS` no basta, porque el
core borra el campo y su columna al terminar el `-u`. Se pierde el agente de las 978 filas. Es una
pérdida prevista en §9: **CUMPLE** la condición 4. Para LIYBEN y producción, hay que guardar antes esa
columna si se quiere conservar.

### P-9e — Reescritura del historial de Chatboo

| Consulta | Antes | Después | Esperado |
|---|---|---|---|
| Consulta literal de §9.5 (`LIKE '%o_chatboo_%' OR LIKE '%data-chatboo-%'`) | 10 | **0** | 0 |
| Consulta exacta (patrón de `markup_rename.py`) | 10 | **0** | 0 |
| Inventario de marcas (todas las sesiones) | 17 marcas antiguas: `data-chatboo-` `chart-engine` 36, `dataset` 36, `show-mode` 36, `sort-col` 154, `sort` 1160; `o_chatboo_` `block_title` 32, `data_table` 36, `ficha` 4, `ficha_table` 4, `ficha_title` 4, `grouped_result` 2, `namelink` 320, `num` 4, `result_title` 2, `table_block` 36, `th_sort` 154, `titled_block` 4 | Las mismas 17, con los mismos recuentos, como `data-ai-*` / `o_ai_*`; ninguna antigua | Ninguna de `ENGINE_MARKUP`/`ENGINE_CLASSES` |
| `data-chatboo-showmode=` (variante de un día) | 0 | 0 | — |

Los gráficos no se guardan como HTML: se dibujan en el cliente a partir de `data-*-chart-engine`,
`dataset` y `show-mode` de cada bloque de tabla. No hay `o_chatboo_chart_host` en ninguna sesión.

**Tres sesiones con tablas** (la 5 tiene además fichas y un resultado agrupado). Cada marca renombrada
acorta 5 caracteres (`chatboo` → `ai`). «MD5 deshecho» = MD5 del texto después de devolver `data-ai-` →
`data-chatboo-` y `o_ai_` → `o_chatboo_`.

| Sesión | Marcas antes (attr + clase) | Longitud antes | Esperada (−5 × marcas) | Longitud después | Marcas nuevas después | MD5 antes | MD5 deshecho después |
|---|---|---|---|---|---|---|---|
| 5 | 346 + 128 | 75 473 | 73 103 | **73 103** | 346 + 128 | `24770b14…` | `24770b14…` (igual) |
| 16 | 114 + 72 | 302 771 | 301 841 | **301 841** | 114 + 72 | `672a6355…` | `672a6355…` (igual) |
| 27 | 254 + 106 | 137 054 | 135 254 | **135 254** | 254 + 106 | `2686bccc…` | `2686bccc…` (igual) |

La longitud cambia exactamente lo que explica el renombrado, y deshecho este el texto es idéntico byte a
byte: el `-u` no toca nada más del historial. `canvas_design` es nueva (U17); las columnas
`canvas_build_*` no existían (U16).

**Marcas nuevas en el código de 3.1.879** (Grep en `pns_ai_chatboo/static` y `pns_ai_mcp/static`;
`data-ai-*` también como `dataset.ai…`):

| Marca | CSS | JS |
|---|---|---|
| `data-ai-chart-engine`, `data-ai-dataset`, `data-ai-sort-col`, `data-ai-sort` | — | Sí |
| `data-ai-show-mode` | Sí | Sí |
| `o_ai_block_title`, `o_ai_data_table`, `o_ai_ficha_title`, `o_ai_namelink`, `o_ai_num`, `o_ai_result_title`, `o_ai_table_block`, `o_ai_th_sort` | Sí | Sí |
| `o_ai_ficha`, `o_ai_ficha_table`, `o_ai_grouped_result`, `o_ai_titled_block` | Sí | — |

- **Ninguna marca nueva queda sin usar.**
- Siguen en el JS tres nombres con el prefijo antiguo: `data-chatboo-chart-engine-active`
  (`chatboo_charts.js:2012`) y `data-chatboo-sort-bound` (`:2876, 2898`). Son atributos de estado que
  se ponen al pintar, no están en `ENGINE_MARKUP` y no aparecen en ningún `messages` guardado. No
  afectan.

**Comprobación visual: no hecha.** El servidor del kit tiene `list_db = True` sin `dbfilter`
(`entorno.sh:381`), así que podría abrir `pns_demo_p9` desde el selector sin cambiar el contexto. Pero
entrar exige la contraseña de un usuario de la copia: ponerla con `bd-claves` modifica la BD y lo decide
Sergio. Además, la sesión no tenía herramientas de navegador. Tampoco se ha hecho la parte de §9.5 que
abre la sesión con el cliente 3.1.782 sobre la BD actualizada (fuera del encargo).

### P-9f — Versiones y paridad

| Consulta | Antes | Después | Esperado |
|---|---|---|---|
| `latest_version` `pns_base` | 14.0.1.2.32 | **14.0.1.2.47** | 14.0.1.2.47 |
| `latest_version` `pns_ai_mcp` | 14.0.3.1.782 | **14.0.3.1.879** | — |
| `latest_version` `pns_ai_chatboo` | 14.0.2.1.453 | **14.0.2.1.538** | — |
| `odoo-dev 14 paridad --bd pns_demo_p9` | 3 «versión distinta» | 23 iguales · 0 distintas · 0 sin código · **0 no se importan** · «paridad completa» | Sin módulos que no se importan |
| `odoo-dev 14 paridad pns_base,pns_ai_mcp,pns_ai_chatboo --bd pns_demo_p9` | — | Igual; «no hay nada por instalar» | — |

### Para producción (LIYBEN) y el staging

- Antes del `-u`, guardar la copia y, si interesa, `ai_log.id, agent_id`: el `-u` borra la columna.
- Tras el `-u` quedará **activo** el cron nuevo `pns_ai_mcp.ir_cron_ai_journal_trash` (aquí lo desactivó
  la neutralización).
- El historial de Chatboo queda reescrito y la vuelta atrás solo es posible con la copia.

### Queda en el entorno

- **Limpieza (23/10/2026):** Sergio borró la BD `pns_demo_p9` (actualizada a 3.1.879, neutralizada,
  proveedores inactivos, con las contraseñas de prueba de la parte 2) y el volcado
  `~/Descargas/pns_demo_p9_20261022.dump`. Comprobado con `odoo-dev 14 bd-lista`: `pns_demo_p9` ya no
  aparece (quedan `lab_pns_ai_14`, `lab_pns_ai_3879_14`, `lumisol_v14_14`, `novocuadro_14` y
  `third_party_14`). Se cierra así la excepción a N9.
- El contexto de `odoo-dev 14` sigue siendo `lab_pns_ai_3879` / `lab_pns_ai_3879_14`.

## Valoración de las condiciones (23/10/2026)

Condiciones de `n12_decision_3879.md` §5. Valoración y decisión de Sergio.

| Condición | Pruebas | Resultado |
|---|---|---|
| 1. Paridad sin módulos que no se importan | Parte 1, paso 1 | **CUMPLE** |
| 2. Tests del fabricante de `pns_ai_mcp` sin regresiones graves | Parte 1, paso 3 | **CUMPLE** |
| 3. P-6 ampliada (sin bloqueos de sesión) y P-70 (gráficos de Odoo intactos con Chatboo abierto) | Parte 2 | **NO CUMPLE** por P-70; aceptada como excepción (abajo) |
| 4. P-9a, P-9b y P-9e sobre una copia de `pns_demo`: las pérdidas son las de §9 | Parte 3 y parte 2, paso 4 | **CUMPLE** |

**Condición 3, NO CUMPLE por P-70:**

- **P-6 cumple:** ningún bloqueo de sesión. El «could not serialize» al cargar dos veces la sesión es
  el residuo previsto de PNS-94 (punto 4 de la ficha de §5.6).
- **P-70 falla en 3.1.879:** tras abrir el chat, errores xAxes/yAxes en la vista gráfico y el tablero
  de Facturación no carga bien (parte 2, paso 3). Es una regresión visible.
- **En 3.1.782 no se observa** (Sergio, staging `pns_demo`, 3.1.782 con los parches 1 a 12,
  23/10/2026, consola del navegador):
  - Con F5 en Contactos y el chat cerrado, `window.Chart` ya es la 4.4.8: la carga el bundle
    `web.assets_backend` de Chatboo (`pns_ai_chatboo/views/assets.xml:22` en
    `14.0-pns-ai-correcciones`).
  - Tras abrir Ventas → Análisis (vista gráfico) y el tablero de Facturación, `window.Chart` sigue
    siendo la 4.4.8: Odoo no recarga su 2.x.
  - Aun así, la vista gráfico (también al cambiar de tipo) y el tablero se pintan bien, sin errores
    en la consola.
- **Sin explicar** por qué falla en 3.1.879 y no en 3.1.782. Tampoco casa con el análisis estático de
  §5.6 de la comparación (carga diferida de la 2.x de Odoo con `ajax.loadJS`). Se investiga al
  preparar el parche de PNS-70.

**Decisión (Sergio, 23/10/2026, reconfirmada):**

- **b′ sigue adelante como excepción** a la regla de §5 de `n12_decision_3879.md` («si alguna falla,
  volver a b)»): cambio de base único a 3.1.879 y congelación posterior. P-70 se acepta porque el
  origen es único (Chatboo carga Chart.js 4 en `window.Chart`) y la corrección es localizada.
- **PNS-70 pasa a Alta** y se corrige en la rama nueva sin pisar `window.Chart`. La condición 3 se
  cierra al repetir P-70 en el laboratorio con ese parche.
- **LIYBEN no se parchea ahora:** espera al cambio de base. Según el staging, sus gráficos de Odoo no
  están afectados. Se comunicará al jefe junto con la hoja de N12.
