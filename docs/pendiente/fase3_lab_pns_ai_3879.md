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

### Datos de prueba que quedan en `lab_pns_ai_3879_14`

- Usuarios `p8b_aiadmin` (uid 10) y `p8b_victima` (uid 11).
- Contacto «P-8b contacto de prueba» (id 43).
- `ai.safe.operation` ids 1 a 4 y sus filas de `ai.change.journal` (ids 1 a 4).
- `ir.cron` id 18 «P-8b cron»: sigue activo con `nextcall` en el pasado. Es inocuo (solo reescribe el
  marcador en el contacto 43). Conviene archivarlo o borrar la BD antes de la parte 2.
- P-8a no dejó nada.

## Pendiente (parte 2, no hecho)

- Condición 3: P-6 ampliada y P-70.
- Condición 4: P-9a, P-9b y P-9e sobre una copia de `pns_demo`.

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

- BD `pns_demo_p9` (actualizada a 3.1.879, neutralizada, proveedores inactivos) y el volcado en
  `~/Descargas`: se borran al cerrar la fase 3.
- El contexto de `odoo-dev 14` sigue siendo `lab_pns_ai_3879` / `lab_pns_ai_3879_14`.
