# Propuesta de la entrega E2′ (base 3.1.879)

- **Rama:** `14.0-pns-ai-3879` · contexto `odoo-dev 14 lab_pns_ai_3879`, BD `lab_pns_ai_3879_14`
- **Fecha:** 27/10/2026
- **Plan:** [plan de corrección sobre 3.1.879](plan_correccion_pns_ai_3879.md), ficha de E2′
- **Datos:** [comparación con 3.1.879](../specs/comparacion_pns_ai_3-1-879.md) (§1.3, §2.1, §2.2, §3, §4.3,
  §5.6, §6.1 y §10.1); [diagnóstico de PNS-70](pns70_diagnostico_3879.md)
- **Registro de parches:** [parches_pns_ai.md](parches_pns_ai.md). Línea base de E1′: 260 tests, 18 F y 32 E.
- **HEAD de partida de E2′:** `c639fa8` («[DOC] Staging E1′: repetición de R8 (27/10/2026), no
  concluyente por el proveedor; E1′ cerrada y R8 pasa a E3′»).
- **Estado:** **implementada (27/10/2026)**: parches, tests, neutralización y documentación; pruebas
  manuales del laboratorio pendientes ([lab_e2_3879.md](lab_e2_3879.md)). Ver «Implementación» al final.
  - Registro anterior de este campo: propuesta final, todas las decisiones cerradas (27/10/2026, tercera
    ronda); P-20 ejecutada, PNS-20 confirmado; pendiente: implementar.
  - Registro anterior: decisiones de Sergio del 27/10/2026 tomadas; quedaban las nuevas
    decisiones y P-20 iba antes que cualquier parche.

Rutas de `pns_ai_mcp` salvo indicación; líneas de la copia de trabajo (3.1.879 con E1′). Las comprobaciones
de este documento son de solo lectura: código, core de Odoo 14 de referencia y `SELECT` dentro de
`BEGIN TRANSACTION READ ONLY … ROLLBACK` sobre `lab_pns_ai_3879_14`.

> **Actualización (27/10/2026, tras las decisiones):** Sergio ha cambiado el contexto a `lab_pns_ai_3879`
> (BD `lab_pns_ai_3879_14`, imagen `odoo-dev:14-lab_pns_ai_3879`, `third_party` en
> `14.0-pns-ai-3879`), comprobado con `odoo-dev 14 estado`. La nota siguiente queda como registro.
>
> **Entorno, 27/10/2026:** el contexto activo de `odoo-dev 14` es **`lab_pns_ai`** (BD `lab_pns_ai_14`,
> imagen `odoo-dev:14-lab_pns_ai`), no `lab_pns_ai_3879`. Para las consultas no ha hecho falta cambiarlo
> (el contenedor de la BD es el mismo). Antes de implementar y de lanzar tests, hay que ejecutar
> `odoo-dev 14 arrancar` desde el repo del laboratorio de 3879. Lo decide Sergio.

## 1. Ficha por ficha

### PNS-37 — la papelera del diario borra como superusuario (Alta, propuesta)

- **Fallo:**
  - **(a) Filas editables.** `ai.change.journal` solo sobrescribe `unlink` (`models/ai_change_journal.py:635-638`).
    `create` y `write` siguen el ACL `1,1,1,0` de AI Administrator y de Ajustes
    (`security/ir.model.access.csv:42-43`), sin reglas de registro. Los campos `readonly=True` solo
    cierran la interfaz, no el ORM. Un AI Administrator sin Ajustes reescribe por `call_kw` una fila antigua
    con `op='unlink'`, `state='applied'`, `reversible=True`, `model_name` y `after_json` =
    `{"ids": [...], "meta": {"quarantine": true}}`. El cron `_cron_empty_journal_trash` (`:612-633`) la
    selecciona (`_quarantined`, `:541-549`) y `_empty_rows` (`:551-575`) borra esos ids con `unlink()`.
  - **(b) Borrado que solo exige escritura.** El paso `unlink` de un plan, en un modelo con `active`, hace
    `recs.write({'active': False})` (`controllers/safe_plan.py:938-953`) sin comprobar el permiso de
    borrado. Pasados los días de retención, el cron lo borra como superusuario.
- **Quién:** (a) AI Administrator sin Ajustes; (b) cualquiera que confirme un plan (AI Writer) sobre un
  modelo archivable en el que tenga escritura y no borrado.
- **Comprobaciones previas (27/10/2026):**
  - **Cómo corre el cron.** `data/journal_trash_cron.xml:4-14` no tiene `user_id` y es `noupdate="1"`.
    - Laboratorio: cron 13, `user_id` 1, activo, `numbercall` -1; última ejecución el 26/10 a las 15:11.
    - Staging: también `user_id` 1 ([staging_e1_3879.md](staging_e1_3879.md), C.2).
    - En Odoo 14, uid 1 activa `su` (`odoo/api.py:450-451`): el cron se salta ACL y reglas.
  - **Retención:** `pns_ai_mcp.journal_trash_days` = 30 en el laboratorio.
  - **Qué es editable:** todo, por ORM, para AI Administrator y Ajustes. `create_date` no se puede
    escribir: Odoo 14 descarta `LOG_ACCESS_COLUMNS` en `write` y `create` (`odoo/models.py:3602, 3835`).
    Por tanto, una fila nueva y falsa espera los 30 días; una fila antigua reescrita sirve al momento.
  - **Reglas de acceso del borrado:** ninguna `ir.rule` sobre `ai.change.journal` (consulta en el
    laboratorio). El paso de plan corre con el usuario humano (`execute_safe_plan`,
    `controllers/safe_plan.py:785-792`), así que un `check_access_rule('unlink')` allí es efectivo.
  - **Escrituras legítimas del diario** (Grep en los tres módulos):
    - en `sudo`: `record_executed_step` (`controllers/safe_plan.py:978` y `models/safe_operation.py:1611`) y el
      `create` del deshacer en `action_revert` (`ai_change_journal.py:503`);
    - `_record_failed_plan` (`:375-441`), en un cursor propio como `SUPERUSER_ID`;
    - **sin `sudo`, como quien pulsa:** `self.write` de `action_revert` (`:498-502`) y `row.write` de
      `_empty_rows` (`:570-573`), que llaman `action_empty_trash` / `action_empty_one` (`:577-610`) y
      `res.config.settings.action_empty_journal_trash` (`models/res_config_settings.py:383-388`).
  - Filas del laboratorio: 2 (`op='action'`, `failed`, de la prueba 2b), ninguna en papelera.
  - `model_can_archive`, `snapshot_records` y `record_executed_step` son públicos, pero por RPC no hacen
    daño: los dos últimos necesitan objetos que no llegan por JSON.
- **Cambio mínimo (parche 17):**
  - **(a)** En `models/ai_change_journal.py`, sobrescribir `create` (`@api.model_create_multi`) y `write`:
    `AccessError` si no es `self.env.su`. Es el mismo criterio que el parche 13 aplica a `ai.safe.operation`.
    - Las dos escrituras que hoy corren como quien pulsa pasan a `sudo()`: `self.sudo().write(...)` en
      `action_revert` y `row.sudo().write(...)` en `_empty_rows`.
    - Antes ya se comprueba `_ensure_journal_manager`; el borrado de `_empty_rows` sigue con los
      permisos de quien pulsa.
  - **(b)** En `controllers/safe_plan.py`, paso `unlink` (`:938-953`), antes de archivar:
    `recs.check_access_rights('unlink')` y `recs.check_access_rule('unlink')`.
  - El cron no se toca: sigue como superusuario, que hace falta para borrar en cualquier modelo. Con (a)
    y (b) solo vacía filas escritas por el sistema y registros que el usuario podía borrar al archivarlos.
  - Sin tocar el ACL (`ir.model.access.csv` no admite el marcador).
- **Qué se degrada:** el AI Administrator sin Ajustes ya no corrige a mano una fila del diario (no hay
  botón que lo haga). Un plan de borrado sobre un registro que el usuario no puede borrar falla, en vez
  de archivarlo.
- **Test (Seges):** `pns_ai_mcp/tests/test_seges_change_journal.py` (`TransactionCase`):
  - `test_ai_admin_write_refused` y `test_ai_admin_create_refused`: AI Administrator sin Ajustes, sobre
    una fila creada en `sudo` en el test;
  - `test_revert_and_empty_still_work_for_ai_admin` (control): el AI Administrator revierte y vacía una
    fila legítima;
  - `test_plan_unlink_requires_unlink_right`: grupo de prueba con escritura y sin borrado en
    `res.partner.category` (tiene `active`), `execute_safe_plan` con ese usuario. Se espera
    `AccessError`, la categoría sigue activa y no hay fila del diario;
  - **la fila del parche toca la fila de una ejecución fallida**, porque el `create` cerrado también le
    afecta. Por eso hay un test de no regresión, `TestSegesFailedPlanRow.test_failed_plan_row_survives_rollback`
    (`TransactionCase`, **sin `enter_test_mode` ni `HttpCase`**):
    - llama a `_record_failed_plan` desde un entorno sin `su`;
    - hace `rollback` del cursor del test;
    - comprueba, desde un `registry.cursor()` nuevo, que la fila `failed` existe;
    - la borra en un cursor propio como superusuario en `finally`.
    - El usuario es `base.user_admin` (ya guardado en la BD), como en el test de PNS-07.
  - `test_failed_execute_journals_outside_rollback` (fabricante) sigue aceptado como desfasado, sin
    tocarlo (plan, E0′).
- **Neutralización:** quitar el `create`/`write` sobrescritos y las dos comprobaciones de `safe_plan.py`.
  - Deben fallar los dos de rechazo y `test_plan_unlink_requires_unlink_right`.
  - El de control y el de la fila fallida pasan con y sin parche: son de no regresión.
- **Decisiones:** 1 y 2.

### PNS-19 — modelos de credenciales alcanzables sin pasar por `env[...]` (Alta)

- **Fallo:** el sandbox solo cierra la puerta `env[...]` / `env.get(...)` (`controllers/context_builder.py:83-99`,
  con `RELAXAICODE_CREDENTIAL_MODELS` en `controllers/validators_base.py:187-209` y
  `catalogue_inspect_error` en `:436-448`). Los recordsets que devuelve el ORM son los reales.
- **Comprobaciones previas (27/10/2026):**
  - **El acceso literal a atributos no pasa por el control de ejecución.** `guarded_getattr`
    (`context_builder.py:131-183`) sustituye solo al `getattr` del sandbox (`:431-434`). `x.provider_id.api_key`
    lo ve el AST, que no conoce `provider_id` ni `api_key`.
  - **Relaciones hacia los modelos cerrados desde modelos abiertos** (`ir_model_fields` del laboratorio):

    | Modelo abierto | Campo | Modelo cerrado | ¿Lo cierra el sandbox? |
    |---|---|---|---|
    | `ai.log` | `provider_id` | `ai.provider` | No |
    | `ai.provider.usage.wizard` | `provider_id` | `ai.provider` | No |
    | `ai.context`, `ai.skill` | `agent_ids` | `ai.agent` | Sí (catálogos) |
    | `res.users` | `api_key_ids`, `totp_trusted_device_ids` | `res.users.apikeys` | No, pero la clave no es campo del ORM (solo nombre y fechas) |

  - **Caminos que una lista de modelos no cierra (requieren prueba):**
    - `env.ref('<xmlid>')`: `GuardedSandboxEnv.__getattr__` (`:104-117`) deja pasar `ref`. Hay XML ID de
      `ai.agent` (`pns_ai_mcp.ai_agent_admin`, `ai_agent_mcp`, `pns_ai_chatboo.ai_agent_chatboo`) y de
      `ir.config_parameter` (7, de `base`, `mail`, `digest`, `sale`…).
    - `new()` no está bloqueado: `env['ai.log'].new({'provider_id': N}).provider_id` da el proveedor N sin
      buscar en `ai.log`.
    - Campos `Reference` del core con todos los modelos en la selección: `mail.template.preview.resource_ref`
      y `sms.template.preview.resource_ref`. `Reference.convert_to_cache` solo valida que el modelo esté
      en la selección (`odoo/fields.py:2452-2466`). Con `new({'resource_ref': 'ai.provider,N'})` se
      llegaría a cualquier modelo cerrado.
    - `ai.api.server` se alcanza igual desde `ai.openapi.spec.generate.wizard.server_id`
      (`wizard/openapi_spec_generate_wizard.py:23`) y `ai.api.server.key.server_id`
      (`models/api_server_key.py:35`), que no están en la lista. El AST bloquea `.auth_token` literal,
      pero no está comprobado que bloquee `read(['auth_token'])` ni `read()` sin campos.
  - **Datos para P-19 en el laboratorio:** 69 de 149 filas de `ai_log` con `provider_id` y 4 proveedores
    con `api_key`.
  - **Quién:** AI Administrator (el campo `api_key` exige `group_ai_admin`, `models/ai_provider.py:194-199`).
    Un usuario sin ese grupo recibe `AccessError` del propio campo.
  - **Alcance:** la Caja A (`get_readonly_env`, `controllers/controller_helpers.py:184-252`) la usan
    `relaxaicode` por `/mcp` y el motor (`utils/engine_tool_run.py:28-30`). El código de las skills corre
    fuera de ella, con el entorno de la petición (`utils/skill_runtime.py:3017`): las escriben
    administradores y no forman parte de PNS-19.
- **No encaja con el plan:** el plan sitúa el cambio en `validators_base.py`, `context_builder.py` y
  `ai_log.py`, es decir, en ampliar la lista. Con `new()` y los campos `Reference`, la lista no basta: cualquier
  modelo nuevo con una relación reabre el hueco. Hay dos opciones (decisión 3):
  - **Opción A, la del fabricante:** añadir `ai.log`, `ai.provider.usage.wizard`,
    `ai.openapi.spec.generate.wizard` y `ai.api.server.key` a la lista, y en `GuardedSandboxEnv` envolver
    `ref` para rechazar un registro de un modelo cerrado.
    - Archivos: `validators_base.py` y `context_builder.py`.
    - Riesgo: bloquea `ai.log` entero en el sandbox, que hoy sirve para preguntar por el consumo. No cierra
      `new()` con campos `Reference`.
  - **Opción B, control en el modelo (recomendada):**
    - `get_readonly_env` marca el cursor de la Caja A (`cr._seges_box_a = True`).
    - `ai.provider`, `ai.api.server`, `ai.mcp.user` e `ir.config_parameter` sobrescriben `_read`: si el
      cursor lleva la marca y el entorno no es `su`, `AccessError`.
    - Cubre relaciones, `env.ref`, `new()`, `Reference`, `read()`, `mapped()` y `search_read()`, porque
      todos acaban en `_read`.
    - El motor lee en `sudo` (`_api_key_for_inference`, `ai_provider.py:201-209`;
      `context_builder.py:458`), así que no le afecta. `ai.log` sigue disponible (sin `.provider_id.*`).
    - Archivos: `controllers/controller_helpers.py` (marca), `models/ai_provider.py`,
      `models/external_server.py`, `models/mcp_user.py` y un `_inherit` de `ir.config_parameter`
      (archivo nuevo en `models/`).
    - Comprobación previa a implementar: que ningún código que corra en la Caja A lea esos cuatro modelos
      sin `sudo` (helpers del sandbox, `utils/sandbox_helpers.py:53-90`, y los que llama `build_safe_context`).
- **Cambio mínimo (parche 18):** el de la opción elegida. Con B, también la entrada `ref` de A, por defensa
  en profundidad, si Sergio lo pide.
- **Qué se degrada (B):** en el sandbox no se puede leer ningún campo de proveedores, servidores
  externos, usuarios MCP ni parámetros del sistema, ni por relación. Lo que hoy da la puerta ya era así.
- **Test (Seges):** `pns_ai_mcp/tests/test_seges_sandbox_credentials.py`:
  - `TransactionCase` con la marca puesta en el cursor del test (`addCleanup` la quita) y un AI
    Administrator creado en el test: `ai.log…provider_id.api_key`, `env.ref` de un agente →
    `provider_ids.provider_id.api_key`, `new()` sobre `mail.template.preview` y `read()` de
    `ai.api.server` desde el asistente OpenAPI → `AccessError`;
  - control: lo mismo en `sudo` lee, y sin marca lee;
  - un caso por la Caja A real (`get_readonly_env` + `build_safe_context`, como
    `test_seges_chatboo_export.py`), con `base.user_admin`. Se le da `group_ai_admin` en un cursor propio
    confirmado y se le quita en `finally`; la BD de tests es nueva en cada ejecución.
- **Neutralización:** quitar la marca del cursor (o el `_read` de `ai.provider`). Deben fallar los casos de
  rechazo y seguir pasando los de control.
- **Decisiones:** 3 y 4.

### PNS-17 — la cabecera personalizada de autenticación sigue a otro host (Alta)

- **Fallo:** al cambiar de host en una redirección, `request_public_http` quita solo las cabeceras de
  `_AUTH_HEADER_NAMES` (`utils/fetch_url_safe.py:98-110, 156-159`). El driver pone la clave en la cabecera
  `auth_header_name` del servidor con `auth_type` `api_key` o `custom_header` (`lib/api/drivers/base.py:47-50`),
  por ejemplo `apikey` u `Ocp-Apim-Subscription-Key`, y esa cabecera viaja al host nuevo.
- **Comprobaciones previas (27/10/2026):**
  - Llamadores de `request_public_http`:
    - el driver OpenAPI, para la especificación (`lib/api/drivers/openapi_driver.py:92-101`, con
      `build_auth_headers`) y para cada operación (`:386-413`);
    - el generador de especificaciones (`services/openapi_spec_generator.py:614-624`), sin
      autenticación.
  - Cabeceras que ponen esos llamadores, además de la de autenticación: `Accept`, `User-Agent` y
    `Content-Type`.
  - Otros detalles en el salto: los `params` de la consulta y el cuerpo (`data`) se reenvían al host
    nuevo salvo en 303 (`:160-162`). No son la clave, pero son datos de la llamada (observación, fuera
    de PNS-17).
  - **Segunda salida con el mismo defecto, no citada en el plan:** el cliente MCP por HTTP
    (`utils/mcp_client.py:75-111`). Pone la misma cabecera personalizada (`:86-91`) y hace
    `requests.Session().post` con las redirecciones por defecto. `requests` solo quita `Authorization` al
    cambiar de host, así que la cabecera personalizada viaja. Además, no valida que el host del salto sea
    público.
- **Cambio mínimo (parche 19):**
  - En `utils/fetch_url_safe.py`, `_strip_auth_headers` pasa a conservar solo una lista de cabeceras
    permitidas al cambiar de host: `accept`, `accept-language`, `content-type` y `user-agent`.
  - Cierra cualquier nombre de cabecera, también los futuros, y deja `_AUTH_HEADER_NAMES` sin uso.
  - La alternativa es pasar el nombre de `auth_header_name` desde el driver, que obliga a tocar los dos
    llamadores y no cubre otras cabeceras.
  - Para `mcp_client.py`, ver la decisión 5.
- **Qué se degrada:** una API que redirige a otro host y espera allí una cabecera propia no estándar deja
  de recibirla. Es lo que se busca.
- **Test (Seges):** `pns_ai_mcp/tests/test_seges_fetch_redirect.py` (`TransactionCase`, sin red):
  - `requests.request` sustituido con `unittest.mock`: primer salto 302 a otro host público y segundo 200;
  - `non_public_host_error` sustituido para que los dos hosts pasen por públicos;
  - comprobación de que el segundo salto no lleva `apikey` ni `Ocp-Apim-Subscription-Key`, y sí
    `User-Agent`;
  - control: en el mismo host, la cabecera se conserva.
  - Si entra `mcp_client.py`: `test_mcp_client_no_redirect`, con `Session.post` sustituido.
- **Neutralización:** volver al filtro por `_AUTH_HEADER_NAMES`. Falla el caso de la cabecera personalizada.
- **P-17 en el staging** (servidor que redirija y registre cabeceras): no hay uno preparado. Propongo
  validar con el test y con una prueba manual en el laboratorio contra un servidor HTTP local de dos
  puertos. El host «público» se simula en el test; en la prueba manual, `non_public_host_error` lo
  rechazaría. Ver la decisión 6.
- **Decisiones:** 5 y 6.

### PNS-82 — el `unlink` de la sesión borra adjuntos de otros creadores (parche 11 adaptado; Alta, resto Baja)

- **Fallo:** `chatboo.session.unlink` (`pns_ai_chatboo/models/chatboo_session.py:1943-2020`) borra en
  `sudo` todos los adjuntos con `res_model='chatboo.session'` de esas sesiones (`:1987-1995`), sean de quien
  sean, antes de que `super().unlink()` compruebe el acceso. El cron `_cleanup_old_sessions` (`:2023-2048`,
  llamado desde `chatboo_async_request.py:1586`) hace `old_sessions.unlink()` en `sudo` (`:2046`).
- **Comprobaciones previas (27/10/2026):**
  - Sobre una sesión ajena, el `AccessError` de `super().unlink()` deshace la transacción (sin efecto,
    prueba 5 de E2). Sobre una propia, borra adjuntos de otros creadores que cuelguen de ella. Hoy solo
    pasa con datos anteriores a la corrección o con flujos futuros.
  - **`_cleanup_old_sessions` no necesita cambio:** pasa por el mismo `unlink`, así que el filtro de
    creador del parche le aplica (es lo que cubre `test_cron_unlink_sudo_keeps_foreign`).
  - **Criterio de enganche.** `_claim_turn_file_chips` (`:465-503`) solo engancha si
    `not att.res_model and not att.res_id and att.create_uid == self.user_id` (`:496`), con el dueño de la
    sesión, no el usuario real.
    - El parche 11 engancha si falta cualquiera de los dos campos, con `create_uid` igual al usuario
      real y la sesión suya (rama `14.0-pns-ai-correcciones`, `chatboo_session.py:419-450`).
    - La diferencia real está en los adjuntos **propios** con `res_model` informado y `res_id = 0`: el
      parche 11 los engancha y el fabricante no.
    - Los casos ajenos los rechazan los dos: (a) a (c) de `test_claim_filters_in_python`.
  - **¿Quién crea adjuntos con `res_model` y `res_id = 0`?** En los tres módulos, nadie.
    `write_export_attachment` lo admite (`pns_base/utils/portable_io.py:345-364`), pero ninguna de sus 14
    llamadas pasa `res_model` (Grep).
  - **Recuento en `lab_pns_ai_3879_14`** (consulta de §5.2; adjuntos sin `res_field`):

    | Caso | Adjuntos | Detalle |
    |---|---|---|
    | a) los dos vacíos (los engancha el fabricante) | 9 | 5 de `__system__` (xml, scss) y 4 de `admin` (2 CSV, 1 PDF y 1 SVG del 23/10: los huérfanos de PNS-98) |
    | b) `res_model` informado y `res_id` 0 o NULL | 14 | Todos `ir.ui.view`, de `__system__`: bundles de estáticos (9 JS y 5 CSS) |
    | b) citados en mensajes de alguna sesión | 0 | — |
    | d) enganchados | 7 | — |

    En el laboratorio, ningún adjunto del caso b) es del chat ni lo engancharía ninguno de los dos
    criterios (el creador sería `__system__`).
- **Opciones para el caso b)** (decisión 7):
  - **Criterio del fabricante (recomendado):** solo se enganchan los huérfanos con los dos campos
    vacíos.
    - No hay ningún productor del caso b) en los módulos y en el laboratorio no hay ninguno del chat.
    - Es la superficie más pequeña: un adjunto propio que ya apunta a un modelo (subido en un formulario
      sin guardar, un borrador del compositor de correo) no se mueve a la sesión, y por eso no se borra al
      borrar la sesión.
    - El test (d) se invierte: el adjunto con `res_model` y `res_id = 0` no se engancha.
    - Sin cambio de código en `_claim_turn_file_chips`.
  - **Criterio del parche 11:** engancha también el caso b) si el creador es el dueño.
    - Cambio de una condición en `:496`.
    - Recupera adjuntos propios que alguien creara así. No se conoce ningún flujo que lo haga.
    - Si algún día existe, el adjunto pasaría a borrarse con la sesión.
  - Si el recuento del staging (§5.2) da adjuntos del caso b) citados en sesiones, se revisa la
    recomendación antes de implementar.
- **Cambio mínimo (parche 11 adaptado):** en `unlink`, antes del borrado en `sudo`:
  - `self.check_access_rights('unlink')` y `self.check_access_rule('unlink')` (el superusuario y el cron
    pasan);
  - de los adjuntos colgados, solo se borran los del dueño de cada sesión o sin `create_uid`; el resto se
    desengancha (`res_model` y `res_id` a `False`), como en el parche 11 original (`chatboo_session.py:1344-1352`
    de la rama anterior).
  - Marcadores con `Seges: parche 11 (PNS-82, seguridad)` y la nota «adaptado a 3.1.879» en el registro.
- **Qué se degrada:** al borrar una sesión, un adjunto ajeno que colgara de ella queda huérfano de su
  creador en vez de borrarse.
- **Test (Seges):** en `pns_ai_chatboo/tests/test_seges_chatboo_access.py`, sobre `SegesChatbooCase`
  (aquí no hay cursor propio):
  - se portan `test_unlink_own_session_keeps_foreign` y `test_cron_unlink_sudo_keeps_foreign`;
  - se completa el caso (d) de `test_claim_filters_in_python` según la decisión 7;
  - se actualiza la cabecera del archivo, que hoy los lista como pendientes de E2′.
- **Neutralización:** quitar el filtro de creador y las dos comprobaciones de `unlink`. Deben fallar los
  dos tests de `unlink`.
- **Decisión:** 7.

### PNS-70 — Chart.js 4 en `window.Chart` (decisión A del 23/10/2026)

- **Fallo:** al abrir el chat, `chatboo_heavy_libs.js:12-33` carga `chart.umd.min.js` (Chart.js 4.4.8) y
  sustituye en `window.Chart` a la 2.9.3 de Odoo. Odoo no la recarga y pinta con la API 4 y opciones de la 2
  ([diagnóstico](pns70_diagnostico_3879.md), §4).
- **Comprobaciones previas (27/10/2026):**
  - **Condición 1, ningún otro JS espera `window.Chart` en versión 4.** Grep de `\bChart\b`,
    `window.Chart`, `globalThis.Chart`, `typeof Chart`, `new Chart(` y `chart.umd` en los `.js`, `.xml`,
    `.html` y `.py` de `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo`:
    - `chatboo_heavy_libs.js:16` (URL) y `:29` (`var chart = window.Chart;`): el único lector;
    - `chatboo_charts.js:36-47, 1636-1640`: usa su copia `ChartLib`, recibida por `bindEngines`, no la
      global;
    - el resto son textos o comentarios (`chatboo_charts.js:59, 869, 1199, 2218`;
      `chatboo_export.js:2112`; `chatboo_component_v2.js:515, 3661`).
    - **Se cumple:** nada más pasa a `PnsChatbooChart`.
  - **Condición 2, un solo token. No encaja con el código real.** La librería asigna `window.Chart` **dos
    veces** (comprobado con `grep -ob`, md5 `45f5b4f17f83d6d21847ec6e14f91674`, 206 553 caracteres):

    | Desplazamiento | Texto | Qué hace |
    |---|---|---|
    | 584 | `(t="undefined"!=typeof globalThis?globalThis:t\|\|self).Chart=e()` | Cabecera UMD: el token del plan |
    | 206 491 | `"undefined"!=typeof window&&(window.Chart=An)` | Dentro de la fábrica (el `index.umd` de Chart.js 4): se ejecuta antes que la cabecera |
    | 206 450 | `An.Chart=An` | Propiedad de la propia clase (`Chart.Chart`): no toca la global |

    - Con solo el token del plan, la fábrica sigue dejando la 4 en `window.Chart` y PNS-70 no se corrige.
    - El diagnóstico (§1) decía «la asignación es única en el archivo»: es incorrecto.
  - **Caché del navegador.** Odoo 14 sirve `/static` con `max-age` de una semana (`STATIC_CACHE`,
    `odoo/http.py:69, 1367`).
    - `chatboo_heavy_libs.js` va en el bundle, con hash nuevo en cada cambio, pero `chart.umd.min.js` se
      pide por su URL fija.
    - Tras el despliegue, un navegador con la librería antigua en caché tendría el bundle nuevo, que lee
      `window.PnsChatbooChart` (sin definir), y la librería vieja, que sigue pisando `window.Chart`.
    - Resultado: gráficos del chat sin Chart.js y Odoo igual de roto hasta que caduque la caché.
    - P-70 se hace «con recarga sin caché» y no lo vería.
  - **Criterio de P-70:** sigue valiendo. La 4 también tiene `Chart.helpers` (desplazamiento 206 177),
    pero solo ella tiene `Chart.version` (`static version="4.4.8"`, desplazamiento 98 778).
- **Cambio propuesto (parche 20; decisión 8):**
  - `pns_ai_chatboo/static/src/js/chart.umd.min.js`:
    - **dos** tokens: `.Chart=e()` → `.PnsChatbooChart=e()` y `window.Chart=An` → `window.PnsChatbooChart=An`;
    - el marcador en un comentario aparte, en la cabecera:
      `/* Seges: parche 20 (PNS-70, compatibilidad). Dos tokens: .PnsChatbooChart=e() y window.PnsChatbooChart=An. Ver docs/pendiente/parches_pns_ai.md */`.
    - `An.Chart=An` no se toca.
  - `pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js`, con marcador `// Seges: parche 20 …`:
    - `:29`: `var chart = window.PnsChatbooChart;`;
    - `:16`: la URL pasa a `'/pns_ai_chatboo/static/src/js/chart.umd.min.js?seges=20'`. Así el navegador no
      reutiliza la copia en caché, y `loadJS` la trata como una URL distinta
      (`addons/web/static/src/js/core/ajax.js:182-213`).
  - **`grep` de comprobación** (queda en el registro):
    ```sh
    grep -o 'PnsChatbooChart=e()\|window\.PnsChatbooChart=An\|\.Chart=e()\|window\.Chart=An' \
      pns_ai_chatboo/static/src/js/chart.umd.min.js | sort | uniq -c
    # esperado: 1 .PnsChatbooChart=e()  y  1 window.PnsChatbooChart=An; ninguno de los antiguos
    grep -rn "window\.Chart\b\|chart\.umd\.min\.js" pns_base pns_ai_mcp pns_ai_chatboo --include=*.js --include=*.xml | grep -v "chart.umd.min.js:"
    # esperado: solo chatboo_heavy_libs.js:16 (con ?seges=20)
    ```
- **Qué se degrada:** nada. El chat ya usaba su copia; `window.Chart` deja de cambiar al abrir el chat.
- **Test:** sin test Python (es JS de carga diferida y no hay tests JS en el módulo). Validación con P-70
  ([diagnóstico](pns70_diagnostico_3879.md), §4): los casos 1 a 4 con recarga sin caché, y un caso 5 que
  propongo añadir:
  - con la caché normal, en un navegador que haya abierto el chat antes del parche, F5 y abrir el chat;
  - se espera `PnsChatbooChart.version` = `4.4.8` y `window.Chart` sin `version`.
- **Neutralización:** con la librería original y la línea 29 antigua, el caso 1 de P-70 vuelve a dar
  `Chart.version` = `4.4.8` y los errores `xAxes`/`yAxes`. Es manual, en el navegador, por Sergio.
- **Decisión:** 8.

### PNS-20 — «Revisar» ejecuta la importación real (Alta, REQUIERE PRUEBA)

- **Estado de P-20:** **sin ejecutar.** No figura en la [fase 3](fase3_lab_pns_ai_3879.md) (P-8a/b, P-6,
  P-70 y P-9a/b/e/f) ni en la [verificación](verificacion_seguridad_pns_ai.md). Según el plan, el parche
  queda condicionado a esa prueba.
- **Lo que dice el código** (`pns_base/models/operation_report_wizard.py:305-323`):
  - `action_preview` abre un `SAVEPOINT` en SQL directo;
  - llama a `action_import` y lee los contadores;
  - hace `ROLLBACK TO SAVEPOINT` y `invalidate_cache()` (`:290-291`).
- **Por qué podría fallar:**
  - En Odoo 14, `invalidate_cache()` sin argumentos llama a `env.cache.invalidate()`
    (`odoo/models.py:5780-5782`), que no vacía `env.all.towrite`. Eso solo lo hace `env.clear()`
    (`odoo/api.py:628-635`).
  - `cr.savepoint()` de Odoo sí vuelca antes y limpia al deshacer (`odoo/sql_db.py:113-134`).
  - Una escritura sobre un registro existente que siga pendiente al deshacer se volcaría al final de la
    petición. Ocurre si nada la ha volcado antes: un `search` sobre esos campos, un `flush`…
  - Hay 15 asistentes con `action_import` que heredan de `pns.operation.report.wizard`
    (`pns_ai_mcp/wizard/`). En sus archivos no hay cursores propios ni `commit` (Grep); los `utils` que
    llaman no se han revisado.
- **Qué falta para decidir:** ejecutar P-20 en el laboratorio de 3879 (comparación §6.1):
  1. `odoo-dev 14 arrancar` desde el repo del laboratorio de 3879 (hoy el contexto es `lab_pns_ai`; lo
     decide Sergio).
  2. Como AI Administrator, exportar usuarios MCP y proveedores. Cambiar en el JSON un campo de un
     registro existente (por ejemplo, el nombre o la URL del proveedor; nunca la clave).
  3. Importar con «Sobrescribir» marcado, pulsar **Revisar** y cerrar sin Confirmar.
  4. `SELECT` del campo en `ai_mcp_user` / `ai_provider`, y de `write_date`.
  - **Esperado si está bien:** sin cambios. Si cambia, PNS-20 queda confirmado.
- **Parche si P-20 lo confirma (parche 21):** en `action_preview`, `self.env['base'].flush()` antes del
  `SAVEPOINT` y antes del `ROLLBACK TO SAVEPOINT`, y `self.env.clear()` en lugar de `invalidate_cache()`
  (mismo efecto que `cr.savepoint()`).
  - No cubre lo que la importación confirme en cursores propios o envíe fuera.
  - Test: `pns_base` no tiene `tests/`, así que el test iría en `pns_ai_mcp/tests/test_seges_import_preview.py`
    con el asistente de usuarios MCP. Se comprobaría desde un cursor nuevo tras terminar la llamada
    (`TransactionCase` sin modo test), porque el defecto se ve al volcar al final de la petición.
- **Decisión:** 9.

## 2. Lo que no encaja con el plan

| Punto del plan | Código real | Dónde se trata |
|---|---|---|
| PNS-70: «el cambio en la librería es exactamente un token» | Hay dos asignaciones a `window.Chart` (cabecera UMD y fábrica) | Decisión 8 |
| PNS-70: validación con recarga sin caché | `/static` se sirve con una semana de caché; hace falta cambiar la URL | Decisión 8 y caso 5 de P-70 |
| PNS-19: cambio en la lista del sandbox (`validators_base.py`, `context_builder.py`, `ai_log.py`) | `new()`, `env.ref` y los campos `Reference` del core llegan a los modelos cerrados sin pasar por `env[...]` | Decisión 3 |
| PNS-17: `fetch_url_safe.py` y `auth_header_name` | El cliente MCP por HTTP (`utils/mcp_client.py`) tiene el mismo defecto, con `requests` | Decisión 5 |
| PNS-82: `unlink` y `_cleanup_old_sessions` | `_cleanup_old_sessions` no necesita cambio: pasa por `unlink` | — |
| Contexto `lab_pns_ai_3879` | El contexto activo es `lab_pns_ai` | Antes de implementar (cabecera) |

## 3. Numeración y commits

> **Sustituida** por la tabla de «Propuesta final» (tercera ronda, al final), que añade el parche 22
> (PNS-100). Esta queda como registro.

| Commit | Parche | Contenido |
|---|---|---|
| 1 | 11 (adaptado, PNS-82) | `unlink` de la sesión (y el criterio de la decisión 7) |
| 2 | 17 (PNS-37) | Diario solo para el sistema; borrado de un plan con permiso de borrado |
| 3 | 18 (PNS-19) | Modelos de credenciales en la Caja A (opción de la decisión 3) |
| 4 | 19 (PNS-17) | Cabeceras permitidas al cambiar de host (y `mcp_client.py` según la decisión 5) |
| 5 | 20 (PNS-70) | Chart.js 4 como `PnsChatbooChart` |
| 6 | 21 (PNS-20) | Solo si P-20 lo confirma |
| 7 | — | Tests de E2′ |
| 8 | — | [DOC] registro, plan y verificación |

Marcadores: `# Seges: parche N (PNS-XX, <tipo>). Ver docs/pendiente/parches_pns_ai.md`, de tipo `seguridad`
salvo el 20 (`compatibilidad`).

## 4. Validación prevista

- **Laboratorio**, tras `arrancar` en el contexto de 3879:
  - `py_compile` con Python 3.7.3 y lint con `--base` del último commit de E1′;
  - `odoo-dev 14 tests pns_base,pns_ai_mcp,pns_ai_chatboo` contra la línea base de E1′ (260 · 18 F · 32 E);
  - neutralización de cada parche, como en E1′;
  - reinicio del contexto antes de cualquier prueba por RPC ([registro](parches_pns_ai.md), «Regla para las
    entregas siguientes»);
  - P-19 (casos de §1), P-37 y P-37b, P-70 (casos 1 a 5) y P-20.
- **Staging `pns_demo`:** las consultas de §5 antes de subir; P-37, P-37b, P-19, P-82 (prueba 4 bis de E2),
  P-70 en el navegador de Sergio, y no regresión del chat (descargas, gráficos, borrar una sesión),
  de Autorizaciones y de Revertir / Vaciar papelera.

## 5. Consultas para el staging (Sergio)

Solo lectura. Se ejecutan con `docker exec -i odoo14_pns_db psql -U odoo -d pns_demo` y la consulta por la
entrada estándar.

### 5.1 PNS-37: filas en papelera y quién las escribió

Antes de subir el parche 17, comprobar que ninguna fila en papelera se ha reescrito a mano: `write_uid` debe
ser el del creador o el superusuario, y `write_date` igual o muy cercano a `create_date`. Conviene
repetirla en LIYBEN antes del despliegue final (contenedor `odoo14_db`).

```sql
BEGIN TRANSACTION READ ONLY;
SELECT c.id, c.user_id, c.active, c.numbercall, c.nextcall, c.lastcall
  FROM ir_cron c JOIN ir_model_data d ON d.model = 'ir.cron' AND d.res_id = c.id
 WHERE d.module = 'pns_ai_mcp' AND d.name = 'ir_cron_ai_journal_trash';
SELECT value AS journal_trash_days FROM ir_config_parameter WHERE key = 'pns_ai_mcp.journal_trash_days';
SELECT j.id, j.op, j.state, j.reversible, j.model_name, j.record_ids_display,
       j.create_uid, j.write_uid, j.create_date, j.write_date
  FROM ai_change_journal j
 WHERE j.op = 'unlink' AND position('"quarantine": true' IN coalesce(j.after_json, '')) > 0
 ORDER BY j.id;
ROLLBACK;
```

### 5.2 PNS-82: adjuntos con `res_model` informado y `res_id = 0` (decisión 7)

La misma consulta que se ejecutó en `lab_pns_ai_3879_14` (resultado en §1, PNS-82). Copia en el scratchpad
de esta sesión: `/tmp/claude-1000/-home-soporte-GitHub-third-party/f8567f28-7e4a-4aa7-a68a-a447a36436da/scratchpad/pns82_res_id0.sql`.

```sql
BEGIN TRANSACTION READ ONLY;
-- 1. Recuento por criterio (solo adjuntos sin res_field: los de campo no se enganchan).
SELECT CASE
         WHEN res_model IS NOT NULL AND res_model <> '' AND coalesce(res_id, 0) = 0 THEN 'b) res_model informado, res_id 0 o NULL'
         WHEN (res_model IS NULL OR res_model = '') AND coalesce(res_id, 0) = 0 THEN 'a) los dos vacíos'
         WHEN (res_model IS NULL OR res_model = '') AND coalesce(res_id, 0) <> 0 THEN 'c) res_id sin res_model'
         ELSE 'd) enganchado' END AS caso,
       count(*) AS adjuntos,
       count(*) FILTER (WHERE description = 'pns_base:export') AS marca_export
  FROM ir_attachment
 WHERE res_field IS NULL
 GROUP BY 1 ORDER BY 1;
-- 2. Detalle del caso b): por modelo, creador y tipo.
SELECT a.res_model, u.login AS creador, a.mimetype, count(*) AS adjuntos,
       min(a.create_date)::date AS primero, max(a.create_date)::date AS ultimo
  FROM ir_attachment a LEFT JOIN res_users u ON u.id = a.create_uid
 WHERE a.res_field IS NULL AND a.res_model IS NOT NULL AND a.res_model <> ''
   AND coalesce(a.res_id, 0) = 0
 GROUP BY 1, 2, 3 ORDER BY 4 DESC, 1;
-- 3. Del caso b), los que alguna sesión de Chatboo cita en sus mensajes (chips de descarga).
SELECT a.id, a.res_model, a.name, u.login AS creador, a.create_date::date
  FROM ir_attachment a LEFT JOIN res_users u ON u.id = a.create_uid
 WHERE a.res_field IS NULL AND a.res_model IS NOT NULL AND a.res_model <> ''
   AND coalesce(a.res_id, 0) = 0
   AND EXISTS (SELECT 1 FROM chatboo_session s
                WHERE s.messages LIKE '%/' || a.id || '"%'
                   OR s.messages LIKE '%"attachment_id": ' || a.id || '%')
 ORDER BY a.id;
ROLLBACK;
```

Lectura: si la consulta 3 sale vacía y la 2 solo muestra modelos ajenos al chat (como los bundles
`ir.ui.view` del laboratorio), se mantiene la recomendación (criterio del fabricante).

**Resultado en el staging `pns_demo` (Sergio, 27/10/2026):**

| Caso | Adjuntos | `marca_export` |
|---|---|---|
| a) los dos vacíos | 200 | 0 |
| b) `res_model` informado, `res_id` 0 o NULL | 14: todos `ir.ui.view`, creados por `__system__` (9 `application/javascript` y 5 `text/css`, del 15/10 al 26/10/2026) | 0 |
| d) enganchados | 13 | 0 |
| Consulta 3 (caso b) citado en sesiones) | 0 filas | — |

Coincide con el laboratorio: los únicos casos con `res_id = 0` son bundles de estáticos del sistema.
Queda el criterio del fabricante (decisión 7). **La auditoría previa de adjuntos de LIYBEN, al final del
plan, repite esta consulta** (contenedor `odoo14_db`).

## Decisiones planteadas (27/10/2026, primera versión)

1. **PNS-37, alcance:** ¿se aplican las dos partes, (a) diario solo para el sistema y (b) permiso de
   borrado en el paso `unlink`? Recomendación: las dos. Ninguna basta sola.
2. **PNS-37, test de la fila fallida:** ¿se incluye `test_failed_plan_row_survives_rollback` (cursor
   propio, sin `enter_test_mode`) aunque sea de no regresión y no falle al neutralizar? Recomendación: sí,
   porque el `create` cerrado toca esa fila.
3. **PNS-19, enfoque:** (A) ampliar la lista y filtrar `env.ref`, como el fabricante, o (B) control en el
   modelo con la marca en el cursor de la Caja A. Recomendación: **B**: la lista no cierra `new()` ni los
   campos `Reference`.
4. **PNS-19, modelos con el control (si B):** ¿`ai.provider`, `ai.api.server`, `ai.mcp.user` e
   `ir.config_parameter`? Recomendación: los cuatro, con la comprobación previa de que nada de la Caja A
   los lee sin `sudo`. Si se prefiere no heredar un modelo del core, sin `ir.config_parameter`; entonces
   quedan abiertos sus XML ID y `Reference`.
5. **PNS-17, `utils/mcp_client.py`:** ¿entra en el parche 19 (`allow_redirects=False` en `Session.post`)
   o va a la hoja de E4′? Recomendación: entra. Es la misma fuga, y un servidor MCP no debería redirigir
   un POST. Si alguno lo hace, fallará con un error claro.
6. **PNS-17, P-17:** ¿basta el test con `requests` sustituido más una prueba manual en el laboratorio, o
   se monta un servidor de prueba con redirección para el staging? Recomendación: test y laboratorio; el
   staging no tiene un servidor OpenAPI de prueba.
7. **PNS-82, adjuntos con `res_model` y `res_id = 0`:** criterio del fabricante (no se enganchan) o del
   parche 11 (se enganchan si son del dueño). Recomendación: **el del fabricante**, condicionada al
   resultado de §5.2 en el staging. En el laboratorio, 14 casos, todos bundles de estáticos de
   `__system__`, y ninguno citado en el chat.
8. **PNS-70, cambio en la librería:** el plan pedía un token y hacen falta **dos** (`.Chart=e()` y
   `window.Chart=An`), más `?seges=20` en la URL de `chatboo_heavy_libs.js` por la caché de una semana.
   ¿Se aprueba así? Recomendación: sí. Es lo mínimo que deja `window.Chart` intacta; la alternativa sin
   tocar la librería (opción B del diagnóstico) tiene la carrera descrita allí.
9. **PNS-20:** ¿se ejecuta P-20 en el laboratorio de 3879 dentro de E2′ (requiere `arrancar`) y, si lo
   confirma, se aplica el parche 21? Recomendación: sí. Si no lo confirma, se registra como verificado y
   no hay parche.
10. **Contexto del laboratorio:** ¿ejecutas `odoo-dev 14 arrancar` desde el repo de `lab_pns_ai_3879`
    antes de implementar? Hoy está activo `lab_pns_ai`, y no instalo ni lanzo tests en otro contexto.

## Decisiones de Sergio (27/10/2026)

1. **PNS-37:** se aplican las dos partes: diario solo para el sistema y permiso de borrado en el paso
   `unlink` del plan.
   - Antes de implementar, inventario de todos los puntos que crean o escriben en `ai_change_journal`
     (ejecución correcta, fallida e intento rechazado) y cómo quedan con el `create` cerrado.
   - Un test de no regresión por cada uno.
2. **PNS-37:** sí al test de la fila de la ejecución fallida, con cursor propio y sin `enter_test_mode`.
3. **PNS-19: opción B**, el control en el modelo dentro de la Caja A. Hay que concretar:
   - en qué método engancha;
   - que no dependa de `su` ni de `sudo`;
   - que la marca del cursor se ponga y se quite en un `try`/`finally`.
   - Tests negativos por vía: `env[...]`, `env.ref`, `new()`, campo `Reference`
     (`mail.template.preview.resource_ref`), `sudo()`, `read_group`, `display_name` y campos related.
   - Un test positivo: fuera de la Caja A, el flujo normal de Chatboo sigue leyendo `ai.provider`.
4. **PNS-19:** lista de modelos a partir de un inventario de credenciales en `lab_pns_ai_3879_14`:
   - como mínimo `ai.provider`, `ai.api.server` y `ai.mcp.user`;
   - valorar `ir.mail_server` y `fetchmail.server`;
   - para `ir.config_parameter`, lista permitida o bloqueada (como mínimo `database.secret`), sin romper
     lecturas legítimas como `web.base.url`.
5. **PNS-17:** `mcp_client.py` entra en el parche 19 con `allow_redirects=False`; si el servidor redirige,
   error claro. Antes de subir a LIYBEN hay que comprobar que sus URLs MCP son las finales (anotar en la
   propuesta y en el plan).
6. **PNS-17:** validación con un test con `requests` simulado más una prueba manual en el laboratorio; sin
   servidor de prueba en el staging.
7. **PNS-82:** criterio del fabricante (solo adjuntos con `res_model` y `res_id` vacíos), confirmado por el
   laboratorio y el staging (§5.2). La auditoría previa de adjuntos de LIYBEN repite la consulta.
8. **PNS-70:** dos tokens (cabecera y `window.Chart=An`), cada uno con su marcador y el `grep`.
   `?seges=20` solo si la librería se carga por URL fija. Se corrige el diagnóstico (asignación única).
9. **PNS-20:** P-20 se ejecuta dentro de E2′ antes de implementar. El parche 21 solo si confirma el fallo;
   si no, se registra el resultado y PNS-20 se cierra sin parche.

## Comprobaciones tras las decisiones (27/10/2026)

Solo lectura: código, core de Odoo 14 de referencia y `SELECT` en `lab_pns_ai_3879_14` dentro de
`BEGIN TRANSACTION READ ONLY … ROLLBACK`.

### PNS-37 (decisiones 1 y 2): quién crea o escribe en `ai_change_journal`

Grep de `ai.change.journal`, `record_executed_step`, `_record_failed_plan` y `_record_change_journal` en
los tres módulos, sin tests ni migraciones (las migraciones van por SQL y no pasan por el ORM).

| # | Vía | Dónde | Operación y entorno hoy | Con el parche 17 | Test de no regresión |
|---|---|---|---|---|---|
| 1 | **Ejecución correcta**: cada paso de un plan | `controllers/safe_plan.py:860, 875, 899, 916, 937, 963` → `_record_change_journal` (`:974-980`) → `record_executed_step` (`models/ai_change_journal.py:242-372`, `self.create`, `:348`) | `create` con `env['ai.change.journal'].sudo()`: `su` | Sin cambio | `test_applied_row_as_ai_writer`: `execute_safe_plan` con un AI Writer (sin `su`), `create` y `write` de un contacto; dos filas `applied` |
| 2 | **Ejecución correcta tras recargar el registro** (`module.update`) | `models/safe_operation.py:1599-1613`, `_heal_module_update_after_registry_reset` | `record_executed_step` en un cursor propio con `SUPERUSER_ID`: `su` | Sin cambio | `test_heal_shape_creates_row`: misma llamada que `:1611` (`Environment(cr, SUPERUSER_ID, ctx)` y `record_executed_step`) en el cursor del test. La recarga real del registro no se reproduce en un test |
| 3 | **Ejecución fallida** | `models/safe_operation.py:1516-1518` (`except` de `execute_plan_now`) → `_record_failed_plan` (`ai_change_journal.py:375-441`) | `create` en un cursor propio con `SUPERUSER_ID` y `sudo()` (`:393-395`), `commit` (`:440`): `su` | Sin cambio | `test_failed_plan_row_survives_rollback` (decisión 2): cursor propio, sin `enter_test_mode` ni `HttpCase`; lectura desde un `registry.cursor()` nuevo; limpieza en `finally` |
| 4 | **Intento rechazado** dentro del plan: `PermissionError` o `UserError` de `execute_safe_plan` (permisos, cúspide, parche 12, y la nueva comprobación de borrado) | El mismo `except` de `:1484-1523`, porque `execute_safe_plan` va dentro del `try` (`:1433-1465`) | Fila `failed` por `_record_failed_plan`. Son las 2 filas `action` del laboratorio (prueba 2b de E1′) | Sin cambio | `test_rejected_plan_journals_failed_row`: el plan de borrado rechazado por (b), y después `_record_failed_plan(steps, str(exc), env=exec_env)`, como `:1516`. En cursor propio y sin `safe_operation_id` en el contexto (ver nota) |
| 5 | **Intento rechazado antes de ejecutar** (token, `check_identity`, cancelación) | Rutas de verificación y `action_confirm_and_execute` | No escriben en el diario (`test_cancelled_safe_plan_does_not_journal` del fabricante) | Sin cambio | El del fabricante |
| 6 | **Revertir** | `action_revert` (`ai_change_journal.py:443-534`) | `self.write` como quien pulsa (`:498-502`); `create` del deshacer en `sudo` (`:503`) | El `write` pasa a `self.sudo().write(...)` | `test_revert_still_works_for_ai_admin` |
| 7 | **Vaciar papelera a mano** | `action_empty_trash`, `action_empty_one` (`:577-610`) y `res.config.settings.action_empty_journal_trash` (`models/res_config_settings.py:383-388`) → `_empty_rows` | `row.write` como quien pulsa (`:570-573`) | `row.sudo().write(...)` (el borrado sigue con los permisos de quien pulsa) | `test_empty_one_and_settings_still_work_for_ai_admin` |
| 8 | **Cron de la papelera** | `_cron_empty_journal_trash` (`:612-633`) → `_empty_rows` | Como uid 1: `su` | Sin cambio | `test_cron_empties_old_row`: fila legítima con `create_date` antigua (puesta por SQL en la transacción del test) y cron con un entorno `SUPERUSER_ID` |
| 9 | **Campo related almacenado** `verification_id` (`:77-80`) | Recálculo del ORM | Se guarda con `_write`, no con `write` | Sin cambio | `test_related_verification_id_recompute`: cambiar `verification_id` de la operación en `sudo` y `flush`, sin `AccessError` |
| 10 | `ondelete` de `safe_operation_id` y `view_id` (`set null`) | Clave foránea de la BD | Sin ORM | Sin cambio | — |
| 11 | `origin` de Chatboo (`pns_ai_chatboo/models/ai_log_door.py:27-33`) | `ondelete` de la selección | `_keep_rows` no hace nada | Sin cambio | — |
| 12 | **Por RPC** (`call_kw`) | ACL `1,1,1,0` | AI Administrator y Ajustes crean y escriben | `AccessError` | Los negativos de §1 (`test_ai_admin_write_refused`, `test_ai_admin_create_refused`) |

- **Nota sobre las filas 3 y 4:** `_record_failed_plan` escribe en un cursor propio. Si el contexto trae
  `ai_journal_safe_operation_id` de una operación sin confirmar en la BD, la clave foránea falla y el error
  se queda en el log (`safe_operation.py:1519-1522`). Por eso los tests no ponen ese id, salvo que creen la
  operación en un cursor confirmado y la borren en `finally`.
  - No se usa `execute_plan_now` entero: hace `cr.commit()` del cursor del llamador (`:1439`) y rompería el
    aislamiento del test.
- **Resultado:** solo cambian las vías 6 y 7 (dos `sudo()`), además de `create` y `write`. Ninguna vía
  legítima deja de funcionar.

### PNS-19 (decisión 3): diseño del control

> **Sustituido** por «PNS-19: rediseño por campos» (segunda ronda, más abajo): el modelo no se cierra
> entero. Lo de aquí queda como registro; siguen valiendo la marca con `try`/`finally` y los embudos.

- **Dónde engancha.** En `models.AbstractModel` con `_inherit = 'base'` (archivo nuevo
  `pns_ai_mcp/models/box_a_guard.py`), sobrescribiendo los tres embudos de lectura de Odoo 14:

  | Método (`odoo/models.py`) | Qué pasa por él |
  |---|---|
  | `_read` (`:3087`) | `read()` (`:3034`), el acceso a un campo (`__get__` → `_fetch_field`, `:3063-3085`), `mapped`, `search_read`, `export_data`, `name_get` y `display_name`, y los campos related |
  | `_read_group_raw` (`:2286`) | `read_group` (`:2230-2265`), que lee por SQL sin pasar por `_read` |
  | `_search` (`:4527`) | `search`, `search_count`, `name_search`, los x2many y los dominios con camino (`provider_id.api_key`). Evita usar la búsqueda como oráculo de la clave |

  - Para un modelo cerrado: si el cursor lleva la marca, `AccessError` antes de llamar a `super()`.
  - Para cualquier otro modelo, sale enseguida tras comprobar `self._name`.
  - **¿Por qué `base` y no cada modelo?** `pns_ai_mcp` depende solo de `web` y `pns_base` (→ `mail`). Con
    `_inherit = 'base'` y la lista por nombre de modelo se cierran también `fetchmail.server` e
    `iap.account` sin tocar `depends`. Si el módulo no está instalado, el nombre simplemente no aparece.
- **Independiente de `su` y de `sudo`.** La condición es solo «cursor marcado y modelo cerrado».
  - No usa `check_access_rights` (con `su` no comprueba nada) ni `self.env.su`.
  - Cubre los related: en Odoo 14 se calculan como superusuario por defecto (`compute_sudo` ←
    `related_sudo=True`, `odoo/fields.py:349`).
  - También cubre los métodos públicos que lean en `sudo` dentro de la Caja A.
- **Caché de `ir.config_parameter`:** `_get_param` usa `ormcache` por `(uid, su, key)`
  (`odoo/addons/base/models/ir_config_parameter.py:70-74`). Un valor ya cacheado no pasa por `_read`. Por
  eso `get_param` también se sobrescribe en `ir.config_parameter` (heredable: es de `base`): en la Caja A,
  una clave bloqueada da `AccessError` antes de la caché.
- **La marca, con `try`/`finally`.** La Caja A se abre en un solo sitio: `tools_relaxaicode.py:183`
  (`controller._get_readonly_env()`). Es el único llamador de `get_readonly_env`; el motor de Chatboo
  llega por la misma función (`utils/engine_tool_run.py:28-30`).
  - El `try` exterior empieza en `:116` (con `ro_cr = None` en `:115`) y su `finally` cierra el cursor en
    `:282-293`.
  - Propuesta: justo después de `:183`, `ro_cr._seges_box_a = True`; en el `finally`, antes del
    `rollback`, `ro_cr._seges_box_a = False` dentro de su propio `try`.
  - Así la marca se quita en todos los caminos de salida, también por excepción, y solo vive en el objeto
    cursor de la Caja A, que se cierra a continuación. Ningún otro cursor la lleva.
  - Desde el sandbox no se puede tocar: `cr` y los nombres con `_` están bloqueados.
  - `get_readonly_env` no se cambia.
- **Lo que corre con la marca** (de `:183` al `finally`): `build_safe_context`, que lee `web.base.url` en
  `sudo` (`context_builder.py:455-460`); el código del sandbox; y la serialización del resultado
  (`_result_of`, `_link_and_picture_rows`, `_present_result`, `_success_response`).
  - Comprobación previa a implementar (f): que nada de eso lea un modelo cerrado. Se hará con la batería
    completa de tests y con el log; si aparece algo, se para y se consulta.
- **Tests** (`pns_ai_mcp/tests/test_seges_sandbox_credentials.py`, `TransactionCase`, marca puesta en el
  cursor del test con `addCleanup` que la quita, AI Administrator creado en el test). Uno negativo por vía:

  | Test | Vía |
  |---|---|
  | `test_gate_env_getitem` | `env['ai.provider']` (la puerta del fabricante sigue) |
  | `test_env_ref_agent_provider_key` | `env.ref('pns_ai_mcp.ai_agent_admin').provider_ids.provider_id.api_key` |
  | `test_new_many2one` | `env['ai.log'].new({'provider_id': N}).provider_id.api_key` |
  | `test_reference_field` | `env['mail.template.preview'].new({'resource_ref': 'ai.provider,N'}).resource_ref.api_key` |
  | `test_sudo_does_not_lift` | `env['ai.log'].sudo().search([...]).provider_id.api_key` (el `sudo` lo pone el test, no el sandbox) |
  | `test_read_group` | `rec.provider_id.read_group([], ['api_key'], ['api_key'])` y `env['ai.log'].read_group(..., ['provider_id'])` (nombre del proveedor) |
  | `test_display_name` | `env['ai.log'].search([...], limit=1).provider_id.display_name` |
  | `test_related_field` | `env['ai.openapi.spec.generate.wizard'].new({'server_id': X}).base_url` (related `server_id.base_url`, el único que sale hacia un modelo cerrado según el inventario) |
  | `test_search_oracle` | `env['ai.log'].search_count([('provider_id.api_key', '=like', 'a%')])` |
  | `test_mail_server_from_message` | `mail.message.mail_server_id.smtp_pass` (con Ajustes) |
  | `test_icp_blocked_key` y `test_icp_cached_get_param` | `database.secret` por `Reference` y por `get_param` con la caché ya caliente |
  | `test_icp_allowed_key` (control) | `web.base.url` con `get_param` en `sudo` sigue leyéndose |

  - **Positivo, fuera de la Caja A:** `test_outside_box_a_chatboo_reads_provider`. Sin marca, como usuario
    de chat: `ai.execution.engine.get_providers_for_agent` con el agente de Chatboo
    (`models/ai_execution_engine.py:203`) y `_driver_for_provider` (`:349`), que lee la clave con
    `_api_key_for_inference` (`:390`). Se espera la clave.
  - **Marca:** `test_marker_cleared_after_box_a`. Llama a la herramienta `relaxaicode` real con un código
    que lanza una excepción y con uno correcto, y comprueba que el cursor ya no lleva la marca en los dos
    casos.
  - Además, un caso por la Caja A real con `base.user_admin`, como estaba en §1.
- **Neutralización:** quitar el `True` de la marca. Fallan todos los negativos; pasan el positivo y el
  control de `web.base.url`.

### PNS-19 (decisión 4): inventario de credenciales y lista propuesta

`ir_model_fields` de `lab_pns_ai_3879_14`: campos `char`, `text`, `binary` y `html` con nombre de credencial
(consulta en el scratchpad: `/tmp/claude-1000/-home-soporte-GitHub-third-party/f8567f28-7e4a-4aa7-a68a-a447a36436da/scratchpad/pns19_inventario.sql`).
Módulos instalados relevantes: `mail`, `fetchmail`, `auth_signup`, `auth_totp`, `payment` e `iap` (sin
`auth_oauth`, `google_account` ni `microsoft_account`).

| Modelo | Campo secreto | Quién lo lee hoy (ACL / `groups`) | Se llega desde | Propuesta |
|---|---|---|---|---|
| `ai.provider` | `api_key` | `group_ai_admin` (campo) | `ai.log`, `ai.provider.model`, `ai.agent.provider`, `ai.provider.usage.wizard`, `ai.artifact.bundle.export.wizard` | **Cerrar** (mínimo) |
| `ai.api.server` | `auth_token`; además `config_json` y `env_vars` | `group_ai_admin` (campos) | `ai.context`, `ai.api.server.key`, `ai.openapi.spec.generate.wizard` (y su related `base_url`), `ai.artifact.bundle.export.wizard` | **Cerrar** (mínimo) |
| `ai.mcp.user` | `mcp_api_key_hash` | ACL del modelo | `ai.api.key.wizard`, `ai.key.pin.ask`, `ai.artifact.bundle.export.wizard` | **Cerrar** (mínimo) |
| `ai.api.server.key` | `token` (clave de cada usuario para un servidor) | ACL del modelo | — (es hijo de `ai.api.server`) | **Cerrar**: no está en ninguna lista y guarda tokens |
| `ai.key.pin.ask` | `supplied_key` (clave en claro durante el canje) | — | — | **Cerrar** |
| `ai.key.pin.desk` | `token` | — | — | **Cerrar** |
| `ai.api.key.wizard` | `generated_key`, `manual_key` | — | — | **Cerrar** |
| `ir.mail_server` | `smtp_pass` | `base.group_system` (ACL) | **`mail.message.mail_server_id`**, `mail.template`, `mail.compose.message` (almacenados) | **Cerrar**: un administrador con Ajustes llega a la contraseña SMTP desde cualquier mensaje |
| `fetchmail.server` | `password` | `base.group_system` (ACL) | `mail.mail.fetchmail_server_id` | **Cerrar** |
| `iap.account` | `account_token` | **`base.group_user`** (`iap/security/ir.model.access.csv:3`, `1,0,1,0`), sin `groups` | puerta abierta: no está en la lista | **Cerrar**: cualquier interno lo lee hoy, también fuera del sandbox (observación para E4′) |
| `res.users` | `totp_secret`, `password` | `totp_secret` con `groups=NO_ACCESS`; `password` calculado y vacío | — | No hace falta |
| `res.users.apikeys` | — (la clave no es un campo del ORM) | — | `res.users.api_key_ids` | No hace falta |
| `ai.safe.operation` | `confirm_token_hash` | `read` sobrescrito (`safe_operation.py:2000`) | — | Fuera (PNS-54, ya tratado) |
| Tokens de portal (`access_token` de `account.move`, `sale.order`, `ir.attachment`; `signup_token`) | — | Quien lee el registro | — | Fuera: dan acceso a lo que el usuario ya ve. Observación para E4′ |
| Asistentes de pago (`*.onboarding.wizard`: `stripe_secret_key`, `paypal_pdt_token`) | — | Transitorios del administrador | — | Fuera: no guardan datos entre peticiones |

**Lista propuesta (decisión nueva 1):** `ai.provider`, `ai.api.server`, `ai.api.server.key`, `ai.mcp.user`,
`ai.key.pin.ask`, `ai.key.pin.desk`, `ai.api.key.wizard`, `ir.mail_server`, `fetchmail.server`,
`iap.account`, y `ir.config_parameter` con su regla propia.

**`ir.config_parameter`: lista bloqueada (decisión nueva 2).** Claves del laboratorio (23): `database.secret`
(36 caracteres), `database.uuid`, `database.create_date`, `web.base.url`, `mail.*`, `auth_signup.*`,
`base.*`, `digest.*`, `sale.*` y `pns_ai*.*`. Ninguna `pns_*` lleva secretos.
- **Por qué bloqueada y no permitida:** con la marca solo corren el código del motor y el del sandbox. El
  motor lee claves en `sudo` (`web.base.url`, `context_builder.py:455-460`, y los parámetros `pns_ai_mcp.*`
  que use la serialización). Una lista permitida obliga a inventariar todas esas lecturas y rompe en
  silencio la próxima que se añada. Una bloqueada solo tiene que conocer los secretos.
- **Regla:** se bloquea si la clave es `database.secret` o contiene `secret`, `password`, `passwd`, `token`,
  `api_key`, `apikey` o `private` (sin distinguir mayúsculas). Así entran también los
  parámetros de OAuth o de terceros que se instalen después. `web.base.url` y el resto siguen legibles.
- **Dónde:** en `_read`, las filas con clave bloqueada (la clave se lee por SQL, para no recursar); en
  `_search` y `_read_group_raw`, cualquier dominio o agrupación que use el campo `value`; y en `get_param`
  (caché).
- `database.uuid` no es un secreto (identificador de la BD) y queda legible.

**Observación nueva (fuera de PNS-19, propuesta para E4′):** con `ir.mail_server` y `mail.mail` abiertos en
la Caja A, `mail.message.mail_server_id.send_email(...)` o `env['mail.mail'].search(...).send()` envían
correo por SMTP sin escribir en la BD (el `READ ONLY` solo frena el `write` posterior). Es del tipo de
PNS-07: `send`, `send_email` y `connect` no están en `RELAXAICODE_SIDE_EFFECT_METHODS`. Con `ir.mail_server`
cerrado, `send_email` y `connect` fallan al leer el servidor. `mail.mail.send()` con el SMTP de `odoo.conf`
(sin `ir.mail_server`) seguiría enviando.

### PNS-17 (decisión 5)

- En `utils/mcp_client.py:103-108`, `self._session.post(..., allow_redirects=False)`. Si la respuesta es una
  redirección (`resp.is_redirect`), `MCPClientError`: «MCP server '%s' answered with a redirect to %s. Set
  the final URL in the server.». `raise_for_status()` no lo detecta, porque un 3xx no es un error.
- Es la única llamada HTTP del cliente (`:103`).
- Test: `test_mcp_client_redirect_refused` (`Session.post` simulado con un 302).
- **Antes de subir a LIYBEN:** comprobar que las URLs de sus servidores MCP (`ai_api_server` con
  transporte HTTP) son las finales, sin redirección (por ejemplo, `curl -sI` de cada una o `SELECT` de
  las URLs y prueba de conexión desde la ficha).
  - **No encaja con los límites de esta tarea:** la decisión pide anotarlo también en el
    [plan](plan_correccion_pns_ai_3879.md), pero en esta tarea solo se pueden tocar la propuesta y el
    diagnóstico de PNS-70. Queda anotado aquí; falta pasarlo al plan, §3, punto 1 (decisión nueva 4).

### PNS-70 (decisión 8): cómo se carga la librería

- `chart.umd.min.js` **no va en ningún bundle**:
  - `pns_ai_chatboo/views/assets.xml:4-33` solo incluye `chatboo_heavy_libs.js` (`:20`) y los JS propios;
  - en `.py`, `.xml` y `.html` de los tres módulos no hay otro `<script src>` con esa ruta.
- Se carga por **URL fija** con `ajax.loadJS`, desde la lista `VENDOR` (`chatboo_heavy_libs.js:12-18`).
- Por tanto, **se añade `?seges=20`** y el caso 5 de P-70 con la caché normal.
- Marcadores: uno por token, en comentarios aparte en la cabecera de `chart.umd.min.js` (la librería
  minificada no admite un comentario junto al token sin romper el `grep` de una línea), cada uno con el
  desplazamiento que localiza el `grep -ob`. Más los dos `// Seges: parche 20 …` de `chatboo_heavy_libs.js`
  (`:16` y `:29`).
- El `grep` de comprobación es el de §1, PNS-70.
- Diagnóstico corregido con bloques fechados, sin reescribir el registro del 23/10:
  [pns70_diagnostico_3879.md](pns70_diagnostico_3879.md), §1 (corrección), §4 («Tras las decisiones del
  27/10/2026») y caso 5 de P-70.

### PNS-20 (decisión 9)

- Orden: P-20 en `lab_pns_ai_3879` antes de implementar ningún parche de E2′ (pasos en §1, PNS-20).
- Si confirma el fallo, parche 21; si no, se registra el resultado en la
  [verificación](verificacion_seguridad_pns_ai.md) y en el plan, y PNS-20 se cierra sin parche.
- P-20 la ejecuta Sergio en la interfaz: importar con «Revisar» es una escritura en la BD del laboratorio,
  aunque se deshaga. Yo preparo los `SELECT` de antes y después.

### Decisiones nuevas para Sergio

1. **PNS-19, lista de modelos cerrados:** ¿se aprueba la de arriba (11 modelos, con `ai.api.server.key`,
   los tres del PIN y la clave, `ir.mail_server`, `fetchmail.server` e `iap.account`)? Recomendación: sí.
2. **PNS-19, `ir.config_parameter`:** ¿lista bloqueada (`database.secret` más el patrón de nombres) en vez
   de permitida? Recomendación: bloqueada, por lo razonado arriba.
3. **PNS-19, dónde engancha:** ¿se acepta `_inherit = 'base'` (un control para todos los modelos, filtrado
   por nombre) para cerrar `fetchmail.server` e `iap.account` sin tocar `depends`? La alternativa es heredar
   solo los modelos de `base` y de `pns_*`, y dejar esos dos en la puerta `env[...]`, que no cierra
   `mail.mail.fetchmail_server_id`. Recomendación: `base`.
4. **PNS-17, anotación en el plan:** ¿la paso al plan (§3, LIYBEN) al implementar, o ahora en una tarea
   aparte? Esta tarea no permite tocarlo.
5. **Observaciones para la hoja de E4′:** `iap.account.account_token` legible por cualquier interno,
   envío de correo desde la Caja A (`send`, `send_email`), los tokens de portal, y el reenvío de `params` y
   `data` en las redirecciones de `request_public_http`. ¿Se añaden a la hoja de E4′? Recomendación: sí,
   sin ampliar E2′.
6. **P-20:** ¿la ejecutas tú en la interfaz del laboratorio con los `SELECT` que prepare? Importar con
   «Revisar» escribe en la BD, aunque sea para deshacerlo, y no lo hago sin que me lo pidas.

## Decisiones de Sergio (27/10/2026, segunda ronda)

1. **PNS-19, lista:** se aprueban los 11 modelos y la regla de `ir.config_parameter`, pero **sin cerrar el
   modelo entero**.
   - `read()` y `search_read()` sin campos devuelven los many2one como `(id, nombre)` con `name_get` del
     modelo relacionado, y la serialización corre con la marca.
   - Solo se permiten los campos de identificación (`id`, `display_name` y el `_rec_name` real de cada
     modelo). Cualquier otro campo da `AccessError`.
   - La precarga de `_fetch_field` no debe traer campos no permitidos. Se rechaza solo cuando se pide uno
     expresamente: acceso al campo, `read()` con ese campo, `search_read`, `read_group` o un dominio sobre él.
   - Tests de no regresión con la marca: `env['ai.log'].search([...], limit=1).read()` y `search_read()` sin
     campos, `env['mail.message'].search_read([...])` sin campos y `provider_id.display_name`, que deben
     funcionar.
   - Comprobar si `_present_result` y `_link_and_picture_rows` leen campos de modelos cerrados más allá del
     nombre. Los negativos siguen, adaptados: se rechaza el campo secreto, no el nombre.
2. **`ir.config_parameter`:** lista bloqueada, como se propuso.
3. **`_inherit = 'base'`:** aceptado. Orden de la condición: primero la marca del cursor (salida inmediata
   fuera de la Caja A) y después el nombre del modelo.
4. **PNS-17:** la anotación de las URLs MCP de LIYBEN pasa al plan (§3) al implementar, en el commit [DOC]
   final.
5. **E4′:** se añaden los tokens de portal y el reenvío de `params` y `data` en las redirecciones de
   `request_public_http`.
   - `iap.account`: observación del core de Odoo (ACL estándar), sin parche; en la Caja A lo cubre PNS-19.
   - El envío de correo desde la Caja A no va todavía a E4′: hay que comprobar si un usuario de chat sin AI
     Administrator llega a `mail.mail.send()`, `mail.mail._send()`, `ir.mail_server.send_email()` o
     `connect()` en la Caja A. Si es así, se propone PNS, gravedad y parche mínimo.
6. **P-20:** la ejecuta Sergio en la interfaz. Se preparan antes los `SELECT`, el campo que se cambia, los
   pasos y dónde guardar el JSON (fuera del repo; se borra al terminar).

## Segunda ronda: preparación de P-20, rediseño de PNS-19 y correo (27/10/2026)

Solo lectura: código, core de Odoo 14 de referencia y `SELECT` en `lab_pns_ai_3879_14`.

### P-20: pasos y consultas (decisión 6)

**Qué se prueba.** En `action_preview` (`pns_base/models/operation_report_wizard.py:305-323`), la
importación escribe y después se hace `ROLLBACK TO SAVEPOINT` + `invalidate_cache()`. Si alguna escritura
sigue pendiente en el ORM (`towrite`), se vuelca al terminar la petición de «Review», aunque no se pulse
Confirmar.
- **Usuarios MCP** (`wizard/import_users_wizard.py:93-98`): `existing.sudo().write(vals)` tras buscar por
  `user_id`.
- **Proveedores** (`wizard/import_servers_wizard.py:65-105`): `existing.write(vals)` tras buscar por `name`.
- Las dos son el caso de la ficha (registro existente, «Replace existing» marcado por defecto).

**Registros y campos elegidos** (consulta de antes, 27/10/2026):

| Archivo | Registro | Campo que se cambia en el JSON | Valor actual | Valor nuevo | Por qué este |
|---|---|---|---|---|---|
| Proveedores | `ai_provider` id 3, `name` = `OVH` | `temperature` | `0.7` | `0.42` | Campo simple y almacenado. No es de `_SPEECH_GATE_KEYS` (`models/ai_provider.py:609`), así que no lanza la sonda de audio por red. `fit_audio` es falso en los cuatro. OVH no es el proveedor del chat |
| Usuarios MCP | `ai_mcp_user` id 1, `login` = `demo` | `last_mcp_client_label` | vacío | `P-20 preview` | `Char` almacenado sin `compute` ni `inverse`: `import_vals_from_dict` lo importa (`pns_base/utils/portable_io.py:159-208`). No toca grupos ni claves |

**No cambiar nada más del JSON.** En los usuarios MCP, los indicadores con `inverse`
(`is_ai_writer`… `models/mcp_user.py:144-181`) escriben grupos de `res.users` si vienen en el archivo. La
exportación no los incluye (son calculados sin almacenar), pero conviene comprobarlo antes de importar.

> **Corrección (27/10/2026, tras P-20):** la exportación **sí los incluye**. El JSON de usuarios MCP de
> P-20 traía `is_mcp_manager`, `is_ai_writer`, `is_ai_external_url`, `is_ai_external_api` e
> `is_ai_conversational`. Al tener `inverse`, `export_record_dict` no los salta, e `import_vals_from_dict`
> los importa (`pns_base/utils/portable_io.py:183`). Más `is_ai_admin`, que no es campo y queda como aviso.
> En P-20 los valores coincidían con los actuales y `res.users` de `demo` no se tocó (`write_date`
> 2026-10-22, sin grupos de `pns_ai_mcp`). Ver el caso de grupos en el test del parche 21.

**Dónde va el JSON:** en `~/p20_lab/`, fuera del repo. Se borra al terminar: lo borro yo cuando me digas
que has acabado (`rm -r ~/p20_lab` y el original en la carpeta de descargas).

**Consulta (antes, después de «Review» y después de cerrar).** Kit sin comando `psql` (`odoo-dev 14
ayuda`), así que se lanza contra el contenedor de la BD. Copia en
`/tmp/claude-1000/-home-soporte-GitHub-third-party/f8567f28-7e4a-4aa7-a68a-a447a36436da/scratchpad/p20_select.sql`.

```sh
docker exec -i odoo-dev-14-db-1 psql -U odoo -d lab_pns_ai_3879_14 < /tmp/claude-1000/-home-soporte-GitHub-third-party/f8567f28-7e4a-4aa7-a68a-a447a36436da/scratchpad/p20_select.sql
```

```sql
BEGIN TRANSACTION READ ONLY;
-- P-20 (PNS-20): estado de los dos registros de la prueba. Ejecutar antes y después.
SELECT 'ai_provider' AS tabla, p.id, p.name, p.temperature, p.fit_audio, p.active,
       p.write_uid, p.write_date
  FROM ai_provider p
 ORDER BY p.id;
SELECT 'ai_mcp_user' AS tabla, u.id, u.login, u.last_mcp_client_label,
       u.write_uid, u.write_date
  FROM ai_mcp_user u
 ORDER BY u.id;
-- Asistentes de importación usados y adjuntos de exportación de la prueba.
SELECT 'wizards' AS tabla,
       (SELECT count(*) FROM ai_import_users_wizard) AS import_users,
       (SELECT count(*) FROM ai_import_servers_wizard) AS import_servers;
SELECT 'export' AS tabla, a.id, a.name, a.create_date
  FROM ir_attachment a
 WHERE a.description = 'pns_base:export'
 ORDER BY a.id DESC LIMIT 5;
ROLLBACK;
```

**Resultado de «antes» (27/10/2026, ejecutada por mí):**
- `ai_provider` 3 (OVH): `temperature` 0.7, `write_uid` 2, `write_date` 2026-10-23 09:38:41.880593.
- `ai_mcp_user` 1 (demo): `last_mcp_client_label` vacío, `write_uid` 2, `write_date` 2026-10-23
  07:28:35.52422.
- 0 asistentes de importación y 0 adjuntos de exportación.

**Pasos en la interfaz** (http://localhost:8169, BD `lab_pns_ai_3879_14`, como `admin`, que es AI
Administrator; el fallo no depende de los permisos):

*Caso A, proveedores:*
1. En la lista de proveedores de IA, abrir **Providers Tools** → **Export JSON**. En la pregunta de
   secretos, exportar **sin secretos** (así el archivo no lleva `api_key` y la importación no la toca).
2. `mkdir ~/p20_lab` y mover allí el `.json` descargado.
3. Editar el archivo:
   - dejar solo el objeto con `"name": "OVH"` (la lista con un elemento);
   - cambiar `"temperature": 0.7` por `0.42`;
   - comprobar que no hay ninguna clave `api_key`.
4. **Providers Tools** → **Import JSON**, subir el archivo, dejar «Replace existing» marcado y pulsar
   **Review**.
5. Con la pantalla «Review this import» abierta («Will replace: OVH»), **sin pulsar Confirmar**, lanzar la
   consulta (**después 1**).
6. Cerrar la ventana (Cancelar o la X), sin Confirmar, y lanzar la consulta otra vez (**después 2**).

*Caso B, usuarios MCP:* lo mismo desde la lista de usuarios MCP, con **Users Tools** → **Export JSON**:
- sin secretos (sin `mcp_api_key_hash`);
- dejar solo el objeto con `"login": "demo"`;
- cambiar `"last_mcp_client_label": ""` por `"P-20 preview"`;
- **Users Tools** → **Import JSON** → **Review**, y las dos consultas.
- La búsqueda de `ai.mcp.user` crea filas para los usuarios internos que no tengan
  (`_maybe_ensure_all_users`, `models/mcp_user.py:560-587`): si aparece alguna fila nueva, es eso, no PNS-20.

**Cómo leer el resultado:**

| Después 1 y 2 | Conclusión |
|---|---|
| `temperature` = 0.7, etiqueta vacía, `write_date` sin cambios | PNS-20 **no se confirma** en estos dos asistentes: se registra y se cierra sin parche (decisión 9) |
| `temperature` = 0.42 o etiqueta = `P-20 preview` (y `write_date` nuevo) | PNS-20 **confirmado**: «Review» aplica parte de la importación. Parche 21 |
| Cambia solo en uno de los dos | Confirmado para ese asistente. El parche 21 es común (`action_preview`), así que se aplica igual |

- Es normal que los asistentes (`ai_import_*_wizard`) y los adjuntos de exportación cuenten 1 o 2: son de
  la prueba. Los transitorios los limpia Odoo y los adjuntos marcados, el cron de `pns_base` a las 24 h.
- **Si se confirma, para volver al estado anterior:**
  - OVH: `temperature` a 0.7 desde su ficha.
  - `demo`: el campo es de solo lectura en la ficha. Otra importación con `""` y Confirmar lo devuelve,
    o se deja `P-20 preview`, que no tiene efecto. Lo decides tú.

### PNS-19: rediseño por campos (decisiones 1 y 3)

**`_rec_name` real de los 11 modelos** (código de la rama y core de Odoo 14; regla por defecto en
`odoo/models.py:2830-2836`: `_rec_name` explícito, si no `name`, si no ninguno → nombre «`modelo,id`»):

| Modelo | `_rec_name` | `name_get` | Campos permitidos en la Caja A |
|---|---|---|---|
| `ai.provider` | `name` (`models/ai_provider.py:154`) | El de Odoo (el `name_get` de `:79` es de `ai.provider.model`) | `id`, `display_name`, `name` |
| `ai.api.server` | `name` (`models/external_server.py:81`) | El de Odoo | `id`, `display_name`, `name` |
| `ai.api.server.key` | `user_id` (`models/api_server_key.py:33`) | El de Odoo: nombre del usuario | `id`, `display_name`, `user_id` |
| `ai.mcp.user` | `user_id` (`models/mcp_user.py:73`) | Propio (`:524-532`): `user_id.name` | `id`, `display_name`, `user_id` |
| `ai.key.pin.ask` | ninguno: no hay `name` (`models/key_pin_desk.py:165-175`) | `ai.key.pin.ask,ID` | `id`, `display_name` |
| `ai.key.pin.desk` | **`token`** (`models/key_pin_desk.py:27`): **el propio secreto** | Devolvería el token | Solo `id` (decisión nueva 1) |
| `ai.api.key.wizard` | ninguno: no hay `name` (`models/mcp_api_key_wizard.py:20-66`) | `ai.api.key.wizard,ID` | `id`, `display_name` |
| `ir.mail_server` | `name` («Description», `odoo/addons/base/models/ir_mail_server.py:86`) | El de Odoo | `id`, `display_name`, `name` |
| `fetchmail.server` | `name` (`addons/fetchmail/models/fetchmail.py:37`) | El de Odoo | `id`, `display_name`, `name` |
| `iap.account` | `service_name` (`addons/iap/models/iap_account.py:18`) | El de Odoo | `id`, `display_name`, `service_name` |
| `ir.config_parameter` | `key` (`odoo/addons/base/models/ir_config_parameter.py:33`) | El de Odoo | `id`, `display_name`, `key`; `value` solo si la clave no está bloqueada |

**Embudos y regla** (en `models/box_a_guard.py`, `_inherit = 'base'`). En cada método, primero
`getattr(self.env.cr, '_seges_box_a', False)` (fuera de la Caja A, `super()` de inmediato), después
`self._name in BOX_A_FIELD_ALLOW` (dict `modelo → campos permitidos`). Nada depende de `su`:

| Método (`odoo/models.py`) | Con la marca, en un modelo cerrado |
|---|---|
| `_fetch_field(field)` (`:3063-3085`) | Si `field.name` no está permitido → `AccessError`. Si lo está, se llama a `_read` solo con los permitidos (la precarga no trae `api_key`, `smtp_pass`…). Es el acceso a un campo (`rec.x`, `rec['x']`, `mapped`, `export_data`, related con `compute_sudo`) |
| `read(fields=None)` (`:3006-3034`) | **Sin campos** → se leen solo los permitidos: devuelve `id`, `display_name` y el nombre, sin error (decisión nueva 2). **Con campos** → si alguno no está permitido, `AccessError`. `search_read` pasa por aquí |
| `_read(fields)` (`:3087`) | Red de seguridad: si llega un campo no permitido por otra vía interna, `AccessError` antes del SQL (no aborta la transacción) |
| `_read_group_raw(domain, fields, groupby…)` (`:2286`) | `AccessError` si un campo de `fields` o de `groupby` no está permitido. El dominio pasa por `_search`. Un `read_group` de `ai.log` agrupado por `provider_id` sigue funcionando: el nombre del grupo sale de `name_get` → `name`, permitido |
| `_search(args…)` (`:4527`) | `AccessError` si una hoja del dominio usa un campo no permitido. Cubre los caminos desde otro modelo (`('provider_id.api_key', '=like', 'a%')` en `ai.log`): Odoo 14 resuelve la parte del modelo relacionado con `comodel._search`. Se comprobará que ningún many2one hacia un modelo cerrado use `auto_join`, que haría un JOIN sin pasar por ahí |
| `ir.config_parameter.get_param(key)` | `AccessError` si la clave está bloqueada, antes de la caché `ormcache` de `_get_param` |

- **`ir.config_parameter` en `_fetch_field` / `read` / `_read`:** `value` se permite si ninguna fila del
  recordset tiene la clave bloqueada (claves leídas por SQL, sin recursión). En `_search` y `_read_group_raw`,
  `value` no se permite nunca en la Caja A (sería un oráculo). `get_param` busca solo por `key`, así que
  `web.base.url` (`context_builder.py:455-460`) y `mail.bounce.alias` / `mail.catchall.domain` (los lee
  `send_email` en `sudo`) siguen funcionando.
- **Por qué `read()` sin campos de un modelo relacionado ya funciona:** `env['ai.log'].read()` convierte
  `provider_id` con `Many2one.convert_to_read` → `value.sudo().display_name` → `name_get` → `name`, que está
  permitido. `mail.message.search_read()` igual con `mail_server_id` → `ir.mail_server.name`.

**¿Qué lee la serialización con la marca?** (`controllers/relaxaicode_outcome.py:41-221`,
`relaxaicode_models.py`, `relaxaicode_rows.py`):

| Función | Qué lee de los registros del resultado | Con el rediseño |
|---|---|---|
| `_build_label_to_record_index` (`relaxaicode_models.py:420-450`) | `display_name`, `name` y `rec[_rec_name]` de los recordsets del espacio del sandbox | Permitidos. Para `ai.key.pin.desk` (`_rec_name` = `token`) el `try/except` lo salta |
| `_backfill_missing_record_ids` (`:515-545`) | `Model.search([(rec_name, '=', texto)])` sobre el modelo del código | `env[...]` de la puerta: un modelo cerrado no llega aquí. Si llegara, `_rec_name` está permitido |
| `_score_record_fit` (`:153-224`) | `display_name`, `name` y **hasta 50 campos almacenados** (`rec[fname]`, `:204-207`) | Los no permitidos dan `AccessError` dentro del `try/except: continue` (`:206`). Puntúa un poco peor, sin fallo y sin fuga (el valor no sale del servidor) |
| `_picture_target` y `walk` (`relaxaicode_rows.py:69-118`) | Campos de imagen (`image_*`) y many2one del registro, un salto más | `ai.provider`… no tienen imagen; los many2one no permitidos dan `AccessError` dentro de `try/except` (`:106-109`, `_record_has_image` `:62-66`) |
| `_present_result` (`relaxaicode_outcome.py:224-…`) | Datos ya serializados y `res.lang` (`render_context_from_env`) | Sin lecturas de modelos cerrados |

Conclusión: más allá del nombre, solo leen otros campos `_score_record_fit` y `walk`, y los dos toleran el
error. La comprobación (f) se hace igualmente con la batería completa y el log.

**Tests** (`pns_ai_mcp/tests/test_seges_sandbox_credentials.py`; marca en el cursor del test con
`addCleanup`). Los negativos esperan `AccessError` **por el campo secreto**:

| Test | Vía | Esperado |
|---|---|---|
| `test_gate_env_getitem` | `env['ai.provider']` en el sandbox | `KeyError` de la puerta (sin cambios) |
| `test_env_ref_agent_provider_key` | `env.ref('pns_ai_mcp.ai_agent_admin').provider_ids.provider_id.api_key` | `AccessError`; `.provider_id.name` funciona |
| `test_new_many2one` | `env['ai.log'].new({'provider_id': N}).provider_id.api_key` | `AccessError` |
| `test_reference_field` | `env['mail.template.preview'].new({'resource_ref': 'ai.provider,N'}).resource_ref.api_key` | `AccessError` |
| `test_sudo_does_not_lift` | `….sudo().provider_id.api_key` (el `sudo` lo pone el test) | `AccessError` |
| `test_read_group` | `provider.read_group([], ['api_key'], ['api_key'])` | `AccessError`; `env['ai.log'].read_group([], ['provider_id'], ['provider_id'])` funciona |
| `test_display_name` | `log.provider_id.display_name` | **Funciona** (no regresión) |
| `test_related_field` | `env['ai.openapi.spec.generate.wizard'].new({'server_id': X}).base_url` (related `server_id.base_url`) | `AccessError` (`base_url` no es el nombre) |
| `test_search_oracle` | `env['ai.log'].search_count([('provider_id.api_key', '=like', 'a%')])` | `AccessError` |
| `test_prefetch_no_secret` | `log.provider_id.name` y después comprobar que `api_key` no está en la caché del entorno | Sin `api_key` en caché |
| `test_mail_server_secret` | `mail.message…mail_server_id.smtp_pass` (con Ajustes) | `AccessError`; `.name` funciona |
| `test_icp_blocked_key`, `test_icp_cached_get_param` | `database.secret` por `Reference` (`.value`) y por `get_param` con la caché caliente | `AccessError` |
| `test_icp_value_search_refused` | `rec.search_count([('key', '=', 'database.secret'), ('value', '=like', 'a%')])` | `AccessError` |
| **No regresión (deben funcionar):** `test_log_read_no_fields`, `test_log_search_read_no_fields`, `test_message_search_read_no_fields`, `test_provider_read_no_fields` | `env['ai.log'].search([...], limit=1).read()`; `env['ai.log'].search_read([...], limit=1)`; `env['mail.message'].search_read([('mail_server_id', '!=', False)], limit=1)` (dato creado en el test); `provider.read()` | Sin error. `provider_id` / `mail_server_id` como `(id, nombre)`; `provider.read()` devuelve solo `id`, `display_name` y `name` |
| `test_icp_allowed_key` | `get_param('web.base.url')` en `sudo` | Funciona |
| `test_outside_box_a_chatboo_reads_provider` | Sin marca: `get_providers_for_agent` y `_driver_for_provider` (`models/ai_execution_engine.py:203, 349, 390`) | Lee la clave |
| `test_marker_cleared_after_box_a` | Herramienta real con código que falla y con código correcto | Sin marca en el cursor después |

**Neutralización:** con la marca a `False`, fallan todos los negativos y siguen pasando los de no regresión.

### Correo desde la Caja A (decisión 5)

**¿Llega un usuario de chat sin AI Administrator? Sí, a `ir.mail_server.send_email()` y `connect()`.**
- **Quién entra en la Caja A:** el motor de Chatboo ejecuta `relaxaicode` con `DummyController`
  (`utils/engine_tool_run.py:16-44`). Para operaciones de lectura no exige ningún grupo; solo la escritura
  pide AI Writer (`:36-44`).
  - Al chat entra quien tiene el grupo conversacional y una clave MCP
    (`pns_ai_chatboo/utils/chatboo_access.py:7-31`). No hace falta AI Administrator ni Ajustes.
  - El código lo escribe el modelo: una instrucción inyectada en un adjunto o en un registro puede
    dictarlo.
- **`ir.mail_server.send_email(message, smtp_server=…, smtp_port=…)`** (`odoo/addons/base/models/ir_mail_server.py:426-514`):
  - es `@api.model` y no comprueba ACL;
  - con `smtp_server` informado, `connect` (`:175-249`) no lee ningún `ir.mail_server` (`:194-218`) y abre
    SMTP al host y puerto que diga quien llama (`:232-234`);
  - solo lee en `sudo` `mail.bounce.alias` / `mail.catchall.domain` para el remitente;
  - el mensaje se arma con `build_email`, también público y sin escrituras;
  - **nada escribe en la BD**, así que el `READ ONLY` de la Caja A no lo frena;
  - `env['ir.mail_server']` no está en la puerta del sandbox, y ni `send_email` ni `connect` están en
    `RELAXAICODE_SIDE_EFFECT_METHODS` (`controllers/validators_base.py:233-…`).
- **`ir.mail_server.connect(host, port, …)`** solo: abre una conexión TCP/SMTP a cualquier host y puerto,
  también internos. Es un SSRF fuera de la política de URL de `fetch_url`.
- **Con PNS-19 no basta:** el rediseño cierra los campos de `ir.mail_server`, y con `smtp_server`
  explícito no se lee ninguno. Sin `smtp_server`, el servidor por defecto sí se lee (`:197-208`) y PNS-19
  lo frena, salvo que no haya `ir.mail_server` y se use el SMTP de `odoo.conf` (`:210-214`), que tampoco
  lee ningún campo.
- **`mail.mail.send()`** (`addons/mail/models/mail_mail.py:243`): no lo alcanza un usuario sin Ajustes,
  porque el ACL de `mail.mail` es `0,0,0,0` salvo para `base.group_system`
  (`addons/mail/security/ir.model.access.csv:5-8`) y `_send` lee el correo con el entorno de quien llama.
  Un administrador con Ajustes sí: reenvía correos ya existentes (ver su contenido no le da nada nuevo,
  pero los manda fuera). `process_email_queue` (`:112`), igual.
- **`mail.mail._send()`:** privado, ya lo bloquea `blocked_private_attr`.
- **En los tests no se ve:** en modo test `send_email` no envía (`:491-494`) y `connect` no conecta
  (`:189-191`). El test tiene que comprobar el rechazo del sandbox, no el envío.

**Propuesta:**
- **PNS-100** (nuevo): «La Caja A permite enviar correo y abrir SMTP a cualquier host
  (`ir.mail_server.send_email` / `connect`)».
- **Gravedad: Alta.** Exfiltración de cualquier dato que el usuario de chat pueda leer hacia un servidor
  del atacante, y conexión a hosts internos, sin escrituras ni confirmación. Requiere una inyección de
  prompt, como PNS-07.
- **Parche mínimo (parche 22, tipo `seguridad`):** añadir a `RELAXAICODE_SIDE_EFFECT_METHODS`
  (`controllers/validators_base.py`), en un bloque propio con su marcador, `send_email`, `connect`,
  `send`, `process_email_queue`, `test_smtp_connection` y `fetch_mail`.
  - `_send` ya está cubierto por el bloqueo de `_`; `build_email` se deja, porque solo arma el mensaje.
  - La lista la usan el AST y `guarded_getattr`, como en el parche 15.
- **Colisiones de nombre** (bloquea `x.send(...)` y `x.connect(...)` de cualquier objeto): en el sandbox no
  debería haber envíos ni conexiones. Se revisarán como en el parche 15 (core, OCA, este repo y
  `vertical-instaladores`) antes de implementar.
- **Test:** en `test_seges_chatboo_export.py` o un `test_seges_sandbox_mail.py` nuevo:
  - el AST marca `env['ir.mail_server'].send_email(m, smtp_server='x')` y `connect('x', 25)`;
  - `guarded_getattr` rechaza los nombres compuestos;
  - código real en la Caja A como usuario de chat (sin AI Administrator), rechazado.
  - Neutralización: quitar el bloque; fallan los tres.
- Si entra en E2′, va después del parche 21 (PNS-20) en la numeración y los commits. Si no, a E4′.

### Decisiones nuevas para Sergio (segunda ronda)

1. **`ai.key.pin.desk`:** su `_rec_name` es `token`, el propio secreto. ¿Se permite solo `id`, de modo que
   también su `display_name` dé `AccessError`? Recomendación: sí. Nada apunta a ese modelo con un many2one,
   así que no afecta a `read()` de otros modelos.
2. **`read()` sin campos sobre un modelo cerrado** (`provider.read()`): ¿devuelve solo los campos
   permitidos, sin error, o da `AccessError`? Recomendación: solo los permitidos. Es coherente con la
   precarga y con «rechazar solo lo pedido expresamente». Con campos explícitos no permitidos, error.
3. **PNS-100 (correo desde la Caja A):** ¿entra en E2′ como parche 22, con la lista de seis nombres?
   Recomendación: sí. Es Alta, el cambio es una lista y comparte mecanismo y tests con el parche 15.
4. **P-20, usuario `demo`:** si la prueba confirma el fallo, ¿devuelvo la etiqueta con otra importación
   confirmada o la dejamos como `P-20 preview`? Lo decides tú al ver el resultado.

## Resultado de P-20 (Sergio, 27/10/2026, `lab_pns_ai_3879_14`, horas en UTC)

Sergio no pulsó Confirmar en ninguna de las dos rondas ni editó la ficha de OVH durante la prueba.

| Caso | Exportación | `temperature` / etiqueta | `write_date` | Después 1 y 2 |
|---|---|---|---|---|
| A. Proveedores (`ai_provider` 3, OVH) | adjunto 459, 10:42:01 | **0.7** (sin cambios) | 2026-10-23 09:38:41 → **2026-10-27 10:45:29.815183** | Iguales |
| B. Usuarios MCP (`ai_mcp_user` 1, `demo`) | adjunto 461, 10:47:41 | vacío → **`P-20 preview`** | 2026-10-23 07:28:35 → **2026-10-27 10:50:09.279496** | Iguales |

- **PNS-20 CONFIRMADO:** en B, «Review» persiste la importación; en A, el valor se deshace, pero queda un
  `UPDATE` del registro después del `ROLLBACK TO SAVEPOINT`. Se aplica el parche 21.
- Asistentes de la prueba: 1 `ai_import_servers_wizard` y 1 `ai_import_users_wizard`.
- `res.users` de `demo` sin cambios (consulta del 27/10/2026: `write_date` 2026-10-22 15:12:29, sin
  grupos de `pns_ai_mcp`).
- **Restos aceptados en el laboratorio** (decisión de Sergio): la etiqueta `P-20 preview` de `demo`, el
  `write_date` de OVH y los adjuntos de exportación 459 y 461. La `temperature` no cambió y no se restaura.
- **Limpieza:** `~/p20_lab` borrado (los dos JSON y las salidas de las consultas, transcritas arriba). En
  `~/Descargas` no había copias de los JSON de P-20: solo `20261022_pns_ai_plantilla_proveedores.json` y
  `userPolicy.json`, que no son de la prueba y no se tocan.
- Se registra también en la [verificación](verificacion_seguridad_pns_ai.md) en el commit [DOC] de E2′.

## Decisiones de Sergio (27/10/2026, tercera ronda)

1. **`ai.key.pin.desk`:** solo `id` permitido; `display_name` también da error.
2. **`read()` sin campos sobre un modelo cerrado:** devuelve solo los campos permitidos, sin error. Da error
   si se piden expresamente campos no permitidos.
3. **PNS-100:** entra en E2′ como parche 22, gravedad Alta.
   - Antes de cerrar la lista, barrido de solo lectura de los métodos públicos de los modelos instalados en
     `lab_pns_ai_3879_14` que salgan a la red o tengan efectos fuera de la BD.
   - Lista completa para `RELAXAICODE_SIDE_EFFECT_METHODS`, con un test negativo para `send_email` y
     `connect` y otro por cada vía nueva relevante.
4. **Parche 21:**
   - explicar por qué los dos asistentes se comportan distinto;
   - comprobar que `flush()` antes del `ROLLBACK TO SAVEPOINT` y `env.clear()` cubren los dos casos;
   - un test que cubra los dos: el valor no cambia (usuarios MCP) y no hay `UPDATE` posterior (proveedores);
   - revisar los otros 13 asistentes con `action_import` (cursores propios o envíos fuera).
5. **Restos de P-20** aceptados; borrar `~/p20_lab` y los JSON de `~/Descargas` (hecho, arriba).

## Tercera ronda: comprobaciones (27/10/2026)

Solo lectura: código, core de Odoo 14 de referencia y `SELECT` en `lab_pns_ai_3879_14`.

### Parche 21: por qué los dos asistentes se comportan distinto

En Odoo 14, `write()` no escribe en la BD: deja los valores en la caché y en `env.all.towrite`. Se
vuelcan en el siguiente `flush`, que también lanza `_read`: «if a read() follows a write(), we must flush
updates» (`odoo/models.py:3101-3103`). Ese `flush(fnames, records)` vuelca **todo** lo pendiente del modelo
si alguno de los campos pedidos está pendiente (`:5502-5535`). Sin `flush`, lo pendiente se escribe al final
de la petición. `invalidate_cache()` vacía la caché, pero no `towrite` ni `tocompute`
(`odoo/models.py:5780-5782`). Eso solo lo hace `env.clear()` (`odoo/api.py:628-635`).

- **Usuarios MCP: escritura pendiente que nadie vuelca dentro del `SAVEPOINT`.**
  - `existing.sudo().write(vals)` (`wizard/import_users_wizard.py:98`) deja `last_mcp_client_label` en
    `towrite`.
  - Con un solo registro en el archivo, nada vuelve a leer campos de `ai.mcp.user` antes del `ROLLBACK TO
    SAVEPOINT`. `_apply_operation_result` escribe en el asistente, otro modelo.
  - El `ROLLBACK` no tiene nada que deshacer en `ai_mcp_user`, e `invalidate_cache()` deja `towrite`
    intacto.
  - Al terminar la petición de «Review», Odoo vuelca: `UPDATE ai_mcp_user SET last_mcp_client_label =
    'P-20 preview', write_date = …`. **Fallo completo.**
- **Proveedores: la escritura del valor se vuelca y se deshace, pero queda otra pendiente.**
  - `existing.write(vals)` (`wizard/import_servers_wizard.py:105`) deja `temperature` en `towrite`.
  - Después, `target_server.available_model_ids` (`:119`) lee un one2many que no está en caché:
    `_fetch_field` precarga los campos de `ai.provider` y `_read` lanza `flush`.
  - El `UPDATE` de `temperature` se ejecuta **dentro** del `SAVEPOINT`, y el `ROLLBACK TO SAVEPOINT` lo
    deshace: por eso sigue en 0.7.
  - A continuación, `target_server.model_id = match[0].id` (`:127`, mismo modelo 131) es otro `write`: Odoo 14
    no omite los valores iguales. Deja `model_id` en `towrite` y marca para recálculo `model_name`
    (related almacenado de `model_id.name`, `models/ai_provider.py:212-215`).
  - Nada lo vuelca antes del `ROLLBACK`. Al final de la petición, `UPDATE ai_provider SET model_id = 131, …,
    write_date = …`: el mismo valor, pero con `write_date` nuevo.
  - **Fallo parcial:** hoy solo cambia `write_date`. Con un `selected_model` distinto en el JSON, cambiaría
    el modelo del proveedor.
  - La hipótesis del «recálculo pendiente» se queda corta. Lo que queda es sobre todo una **escritura
    pendiente** (`model_id`), con el recálculo de `model_name` encima. Ningún otro campo de `ai.provider` es
    calculado y almacenado (consulta de `ir_model_fields`: 0 con `depends`; el único related almacenado es
    `model_name`).

**¿Cubren los dos casos `flush()` antes del `ROLLBACK TO SAVEPOINT` y `env.clear()`?** Sí:
- `self.env['base'].flush()` sin campos hace `recompute()` de todo y vuelca todo `towrite`
  (`odoo/models.py:5495-5500`). Usuarios: el `UPDATE` de la etiqueta. Proveedores: el de `model_id` y el
  recálculo de `model_name`. Todo se ejecuta dentro del `SAVEPOINT`.
- El `ROLLBACK TO SAVEPOINT` deshace esos `UPDATE`.
- `env.clear()` vacía caché, `tocompute` y `towrite` (`odoo/api.py:632-635`): no queda nada para el final
  de la petición.
- Además, **`cr.precommit.clear()`** tras el `ROLLBACK`, como `cr.savepoint()` (`odoo/sql_db.py:122-128`).
  El seguimiento de `mail.thread` deja trabajo en `precommit`, que se ejecutaría al confirmar con datos
  deshechos.
  - Proveedores y usuarios MCP no heredan `mail.thread`, pero el parche es común a los 15 asistentes.
- `flush()` también **antes** del `SAVEPOINT`, para que lo pendiente de antes de la vista previa no se
  deshaga con ella.
- Después, `_apply_import_preview(**snap)` escribe en el asistente como hoy.

**Parche 21 (definitivo):** en `pns_base/models/operation_report_wizard.py`, `action_preview`
(`:305-323`):
- `self.env['base'].flush()` antes de `SAVEPOINT`;
- en los dos caminos (correcto y excepción), `self.env['base'].flush()` antes de `ROLLBACK TO SAVEPOINT`;
  en el de excepción, dentro de un `try` (el `flush` puede fallar por lo mismo que la importación);
- tras el `ROLLBACK`, `self.env.cr.precommit.clear()` y `self.env.clear()`. Sustituye a
  `_invalidate_after_preview_rollback`: el método se mantiene, por si alguien lo hereda, y pasa a llamar a
  `env.clear()`.
- Marcador `# Seges: parche 21 (PNS-20, seguridad)`.

**Test del parche 21:** `pns_ai_mcp/tests/test_seges_import_preview.py` (`TransactionCase`). `pns_base` no
tiene `tests/`.
- Simula el final de la petición con `self.env['base'].flush()` después de `action_preview()`.
- Como `now()` es constante dentro de la transacción del test, `write_date` no sirve para detectar un
  `UPDATE`. Se usa `ctid` (`SELECT ctid FROM … WHERE id = …`): cada `UPDATE` crea una versión nueva de la
  fila, y un `ROLLBACK TO SAVEPOINT` deja la original.
- Tests:
  - `test_users_preview_keeps_value` (caso B): JSON con otra `last_mcp_client_label`. Tras `action_preview` y
    `flush`, la etiqueta sigue igual y `ctid` no cambia.
  - `test_providers_preview_no_update` (caso A): proveedor con `model_id` y JSON con otra `temperature` y el
    mismo `selected_model`. Tras `action_preview` y `flush`, `temperature` igual y **`ctid` sin cambios**
    (sin `UPDATE` posterior).
  - `test_users_preview_keeps_groups`: JSON con `is_ai_writer: true` para un usuario sin AI Writer. Tras la
    vista previa, el usuario sigue sin el grupo.
  - `test_import_still_applies` (control): `action_import` aplica el cambio.
- **Neutralización:** fallan los dos primeros. El de usuarios, por el valor (`'P-20 preview' != ''`). El de
  proveedores, por `ctid`, aunque el valor coincida, como en P-20.
- El de grupos queda como no regresión si con el código actual no falla (la escritura del many2many puede
  ir directa a la tabla de relación y deshacerse con el `ROLLBACK`). Se anota lo que dé.

### Parche 21: los otros 13 asistentes con `action_import`

Grafo de llamadas aproximado (AST, por nombre de función, 5 niveles) desde cada `action_import`, buscando
cursores propios, `commit`, red, escritura en disco y recarga del registro. Después, revisión a mano de las
rutas de importación (`ai_context_disk.py`, `ai_skill.py`, `ai_agent.py`, `utils/artifact_bundle.py`,
`utils/config_backup.py`, `models/external_server.py`). Script en el scratchpad:
`/tmp/claude-1000/-home-soporte-GitHub-third-party/f8567f28-7e4a-4aa7-a68a-a447a36436da/scratchpad/import_effects.py`.

| Asistente | Resultado | ¿Lo cubre el parche 21? |
|---|---|---|
| `bundle_import_wizard` | `import_agent_zip` → `_sync_composition_and_cache` → `ai.agent.get_content` → **`_persist_cache_isolated`**: cursor propio con `commit` (`models/ai_agent.py:1389-1403`). Guarda la caché del prompt del agente con lo importado | **No.** La vista previa deja confirmada la caché con contenido deshecho. Además, ese cursor hace `UPDATE ai_agent` sobre una fila que la transacción de la vista previa puede tener bloqueada: espera hasta el `lock_timeout` (requiere prueba). Propuesta: hoja de E4′ (que `get_content` no persista en una vista previa, por ejemplo con `pns_import_preview` en el contexto) |
| `config_backup_wizard` | Su `action_preview` es propio, con `dry_run=True` (`wizard/config_backup_wizard.py:108-118`) | No usa el `action_preview` común: ni lo necesita ni le afecta |
| `skill_tools_wizard`, `mcp_context_tools_wizard` | `action_import` solo abre otro asistente (`:43-45`, `:47-49`) | Sin efecto: «Review» no escribe nada |
| `context_import_wizard`, `skill_import_wizard`, `agent_skill_import_wizard`, `agent_context_import_wizard` | Leen ZIP y archivos de fábrica del disco (`open(..., 'r')`, `ai_context_disk.py:453, 583`; `ai_skill.py:2016-2373`). Sin escritura en disco, cursor propio ni red | Sí |
| `import_agents_wizard`, `import_external_servers_wizard`, `import_whitelist_wizard`, `artifact_bundle_import_wizard` | Solo ORM. En `external_server.py` no hay red en `create`/`write` (el descubrimiento va por botones) | Sí |

### PNS-100: barrido de métodos con efectos fuera de la BD (decisión 3)

**Método.** Análisis AST, de solo lectura, del código de los **47 módulos instalados** en
`lab_pns_ai_3879_14` (consulta de `ir_module_module`, en el core de referencia y en este repo):
- métodos públicos de clases de modelo cuyo cuerpo, o el de un método privado del mismo módulo al que
  llaman (un salto), contiene `smtplib`, `requests`, `urllib`, `socket`, `imaplib`/`poplib`, `iap_jsonrpc`
  y `jsonrpc`, `subprocess`, `registry.cursor()`/`commit()`, o ejecución de acciones y crons;
- revisión a mano de cada coincidencia en el core;
- lista de módulos: `account`, `account_edi`, `auth_*`, `base`, `bus`, `digest`, `fetchmail`, `iap`,
  `iap_mail`, `mail`, `partner_autocomplete`, `payment`, `portal`, `sale`, `sms`, `snailmail`,
  `web_editor`, `pns_*` y otros;
- script y salida en el scratchpad: `sweep_side_effects.py` y `sweep.txt`
  (`/tmp/claude-1000/-home-soporte-GitHub-third-party/f8567f28-7e4a-4aa7-a68a-a447a36436da/scratchpad/`).

**Clasificación:**
- **(A)** Efecto real en la Caja A: sale a la red, o ejecuta código, sin escribir antes en la BD, así que el
  `READ ONLY` no lo frena.
- **(B)** Necesita escribir antes en la BD (crear un `mail.mail`, un `mail.message`…): hoy lo frena el
  `READ ONLY`. Solo se añade si es una vía estándar de envío (defensa en profundidad).
- **(C)** Cursor propio con `commit`: el mismo patrón que el parche 15.

| Nombre | Modelo (módulo) | Qué hace | Quién llega | Tipo | ¿A la lista? |
|---|---|---|---|---|---|
| `send_email` | `ir.mail_server` (base) | SMTP a cualquier host con `smtp_server`, sin ACL (`ir_mail_server.py:426-514`) | **Cualquier usuario de chat** | A | **Sí** |
| `connect` | `ir.mail_server` (base); también `fetchmail.server` | TCP/SMTP a cualquier host y puerto (`:175-249`) | **Cualquier usuario de chat** | A | **Sí** |
| `test_smtp_connection` | `ir.mail_server` (base) | Conecta con el servidor guardado (`:114`) | Ajustes (ACL) | A | Sí |
| `load_remote_url` | `ir.qweb.field.image` (web_editor) | **`requests.get(url)` a cualquier URL**, con redirecciones, sin control de host (`addons/web_editor/models/ir_qweb.py:461-470`). Modelo abstracto: `env[...]` no pide ACL | **Cualquier usuario de chat** | A | **Sí** (SSRF y fuga por la URL) |
| `send` | `mail.mail` (mail), `sms.sms` (sms) | SMTP / IAP de correos y SMS ya existentes; envía antes de escribir el estado (`mail_mail.py:243-283`; `sms_sms.py:47, 95`) | Ajustes (`mail.mail` `0,0,0,0` salvo `group_system`) | A | Sí |
| `process_email_queue` | `mail.mail` (mail) | Envía la cola (`mail_mail.py:112`) | Ajustes | A | Sí |
| `fetch_mail`, `button_confirm_login` | `fetchmail.server` (fetchmail) | IMAP/POP con las credenciales guardadas; `fetch_mail` con cursor propio (`fetchmail.py:137, 170`) | Ajustes | A, C | Sí |
| `get_credits` | `iap.account` (iap) | JSON-RPC a IAP con el token de la cuenta (`iap_account.py:139`) | Interno (ACL `base.group_user`) | A | Sí |
| `autocomplete`, `enrich_company`, `read_by_vat`, `start_sync` | `res.partner`, `res.partner.autocomplete.sync` (partner_autocomplete) | JSON-RPC a IAP con el texto que se pase y gasto de créditos (`res_partner.py:85-146`; `res_partner_autocomplete_sync.py:17`) | Interno | A | Sí |
| `send_letter`, `snailmail_print` | `mail.message`, `snailmail.letter` (snailmail) | Correo postal por IAP con coste, cursor propio (`snailmail_letter.py:328, 406`) | Interno con la carta | A, C | Sí |
| `update_notification` | `publisher_warranty.contract` (mail) | Envía a Odoo S.A. datos y logs del sistema (`addons/mail/models/update.py:69-82`) | Interno | A | Sí |
| `install_from_urls` | `ir.module.module` (base) | Descarga e instala módulos desde URLs, cursor propio (`ir_module.py:769`) | Ajustes | A, C | Sí |
| `action_process_edi_web_services` | `account.move` (account_edi) | Servicios web EDI con `commit` (`account_move.py:436`; `account_edi_document.py:251`) | Facturación | A, C | Sí |
| `get_usd_fx` | `ai.fx.source` (pns_ai_mcp) | HTTP a las fuentes de tipos de cambio (`models/ai_fx_source.py:73-87`); el motor y Chatboo lo llaman por Python, no desde el sandbox | Interno | A | Sí (M16 sigue en E4′) |
| `run` | `ir.actions.server` (base) | **Ejecuta la acción de servidor**, cuyo código no pasa por el AST del sandbox (puede llamar a `send_email`) (`ir_actions.py:585-…`) | Según `groups_id` de la acción | A (trampolín) | **Sí** |
| `method_direct_trigger` | `ir.cron` (base) | Ejecuta el cron **como su `user_id`** (a menudo superusuario), `ir_cron.py:81-86` | Escritura en `ir.cron` (Ajustes) | A (trampolín) | **Sí** |
| `execute_callback` | `payment.transaction` (payment) | Llama al método guardado en la transacción (`payment_acquirer.py:1113`) | Interno con la transacción | A (trampolín) | Sí |
| `upgrade_module` | `base.module.upgrade` (base) | Recarga el registro con `commit` (`base_module_upgrade.py:53`) | Ajustes | C | Sí |
| `action_start_automatic_process`, `parent_migration_process_cb` | `base.partner.merge.automatic.wizard` (base) | Fusión de contactos con `commit` (`base_partner_merge.py:538, 562`) | Ajustes / contactos | C | Sí |
| `send_mail` | `mail.template`, `mail.compose.message` (mail) | Crea `mail.mail` y envía | Interno | B | Sí (vía estándar de envío) |
| `message_process`, `message_route` | `mail.thread` (mail) | Procesa un correo entrante armado con `build_email`; puede generar un rebote (`mail_thread.py:668-680, 854, 1099`) | Interno | B | Sí (el rebote es un envío) |
| `update` | `bus.presence` (bus) | Presencia en cursor propio (`bus_presence.py:36`) | Interno | C | **No**: bloquearía `dict.update` en todo el sandbox. Efecto menor (marca de presencia) |
| `onchange_email` | `res.partner` (base) | Petición a Gravatar con el MD5 del correo (`res_partner.py:372, 870`) | Interno | A | **No**: host fijo y solo un hash. Observación para E4′ |
| `action_send` (digest), `execute_command` (mail.channel), `resend_mail_action`, `add_followers`, `action_resend` (sms) | — | Escriben en la BD antes de enviar | — | B | No (el `READ ONLY` los frena y no son la vía estándar) |
| `action_quotation_send`, `action_buy_credits`, `get_credits_url`, `get_account_url`, `get_config_account_url` | — | Solo devuelven una acción o una URL | — | — | No (falsos positivos del barrido) |
| `button_immediate_install` / `_upgrade` / `_uninstall`, y los del parche 15 (`get_content`, `log_*`, `test_connection`, `collect`, `page_html`, `paint_canvas`…) | — | — | — | — | Ya están en la lista |

**Lista definitiva del parche 22**, 28 nombres en un bloque nuevo de `RELAXAICODE_SIDE_EFFECT_METHODS`
(`controllers/validators_base.py`), con su marcador:

```
send_email, connect, test_smtp_connection, load_remote_url, send, process_email_queue,
fetch_mail, button_confirm_login, get_credits, autocomplete, enrich_company, read_by_vat,
start_sync, send_letter, snailmail_print, update_notification, install_from_urls,
action_process_edi_web_services, get_usd_fx, run, method_direct_trigger, execute_callback,
upgrade_module, action_start_automatic_process, parent_migration_process_cb, send_mail,
message_process, message_route
```

(`_send` y los demás privados ya los cubre el bloqueo de `_`.)

- **Colisiones de nombre:** la lista bloquea por nombre en cualquier objeto (AST y `guarded_getattr`).
  - Antes de implementar, búsqueda de `def <nombre>(` en el core, OCA, este repo y `vertical-instaladores`,
    con el mismo criterio que el parche 15 (aceptar si la coincidencia escribe o conecta; sacar si es una
    lectura sin alternativa).
  - Ya descartado: `update`. `run` y `send` son genéricos, pero en el código del sandbox no hay usos
    legítimos (no tiene módulos con `run`); se confirmará con las skills y contextos de fábrica.
  - Grep del 27/10/2026: ninguno de estos nombres aparece en `ai/`, `data/` de `pns_ai_mcp` ni de
    `pns_ai_chatboo`.
- **Gravedad de PNS-100: Alta.**
  - Cualquier usuario de chat, mediante una inyección de prompt, saca datos por SMTP (`send_email`,
    `connect`) o por HTTP (`load_remote_url`) hacia un host suyo, o llega a hosts internos, sin escribir
    en la BD ni pasar por la política de URL.
  - Con un administrador, además, se ejecutan crons y acciones de servidor (`run`, `method_direct_trigger`).
- **Tests** (`pns_ai_mcp/tests/test_seges_sandbox_side_effects.py`):
  - `test_names_in_denylist` y `test_ast_flags_literal_call`: los 28 nombres (`x.<nombre>(...)` marcado por
    el AST) y nombres compuestos rechazados por `guarded_getattr`.
  - **`test_box_a_send_email_refused`** y **`test_box_a_connect_refused`** (los pedidos): código real en la
    Caja A como usuario de chat sin AI Administrator. `env['ir.mail_server'].send_email(env['ir.mail_server'].build_email(...), smtp_server='seges.invalid')`
    y `env['ir.mail_server'].connect('seges.invalid', 2525)` se rechazan antes de ejecutarse.
    - En modo test, `send_email` y `connect` no envían (`ir_mail_server.py:189-191, 491-494`): el test
      comprueba el rechazo del sandbox. Además se sustituye `smtplib.SMTP` con `unittest.mock` y se
      comprueba que no se llama.
  - **Uno por vía nueva:**
    - `test_box_a_load_remote_url_refused` (HTTP, con `requests.get` sustituido y sin llamar);
    - `test_box_a_server_action_run_refused` (trampolín: una `ir.actions.server` de código creada en el
      test);
    - `test_box_a_cron_trigger_refused` (`method_direct_trigger`, como administrador);
    - `test_box_a_mail_queue_refused` (`mail.mail.send` / `process_email_queue`, como administrador);
    - `test_box_a_iap_refused` (`res.partner.read_by_vat` e `iap.account.get_credits`, con `iap_jsonrpc`
      sustituido);
    - `test_box_a_module_from_urls_refused` (`install_from_urls`).
  - **Neutralización:** quitar el bloque; fallan todos los negativos.

## Propuesta final (27/10/2026)

### Decisiones cerradas

| Tema | Decisión |
|---|---|
| PNS-37 | Diario solo para el sistema (`create`/`write` con `su`) y permiso de borrado en el paso `unlink`. Inventario de 12 vías con test de no regresión; test de la fila fallida con cursor propio y sin `enter_test_mode` |
| PNS-19 | Control por campos en la Caja A: `_inherit = 'base'`, primero la marca del cursor y después el modelo, independiente de `su`. 11 modelos con sus campos permitidos (`ai.key.pin.desk`: solo `id`). `read()` sin campos devuelve los permitidos. `ir.config_parameter` con lista bloqueada. Marca con `try`/`finally` en `tools_relaxaicode.py` |
| PNS-17 | Cabeceras permitidas al cambiar de host en `request_public_http`; `mcp_client.py` con `allow_redirects=False` y error claro. Test con `requests` simulado y prueba manual en el laboratorio; sin servidor en el staging |
| PNS-82 | Parche 11 adaptado (`unlink` de la sesión); criterio del fabricante para enganchar (solo los dos campos vacíos), confirmado en el laboratorio y en el staging |
| PNS-70 | Dos tokens con marcador y `grep`; `?seges=20` (carga por URL fija); caso 5 de P-70 |
| PNS-20 | Confirmado por P-20; parche 21 con `flush` + `precommit.clear()` + `env.clear()` |
| PNS-100 | Parche 22, Alta, 28 nombres |

### Parches y commits de E2′ (definitivo)

HEAD de partida: `c639fa8`. Un commit por parche, uno de tests y uno de documentación (reglas de N11).

| Commit | Parche | PNS / tipo | Archivos |
|---|---|---|---|
| 1 | **11** (adaptado) | PNS-82, seguridad | `pns_ai_chatboo/models/chatboo_session.py` (`unlink`) |
| 2 | **17** | PNS-37, seguridad | `pns_ai_mcp/models/ai_change_journal.py` (`create`, `write`, dos `sudo()`); `pns_ai_mcp/controllers/safe_plan.py` (paso `unlink`) |
| 3 | **18** | PNS-19, seguridad | `pns_ai_mcp/models/box_a_guard.py` (nuevo, `_inherit = 'base'` y `ir.config_parameter.get_param`), `pns_ai_mcp/models/__init__.py`, `pns_ai_mcp/controllers/tools_relaxaicode.py` (marca con `try`/`finally`) |
| 4 | **19** | PNS-17, seguridad | `pns_ai_mcp/utils/fetch_url_safe.py` (`_strip_auth_headers`); `pns_ai_mcp/utils/mcp_client.py` (`_http_post`) |
| 5 | **20** | PNS-70, compatibilidad | `pns_ai_chatboo/static/src/js/chart.umd.min.js` (2 tokens y marcadores en la cabecera); `pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js` (`:16` y `:29`) |
| 6 | **21** | PNS-20, seguridad | `pns_base/models/operation_report_wizard.py` (`action_preview`, `_invalidate_after_preview_rollback`) |
| 7 | **22** | PNS-100, seguridad | `pns_ai_mcp/controllers/validators_base.py` (bloque de 28 nombres) |
| 8 | — | Tests de E2′ | `pns_ai_mcp/tests/test_seges_change_journal.py`, `test_seges_sandbox_credentials.py`, `test_seges_fetch_redirect.py`, `test_seges_import_preview.py`, `test_seges_sandbox_side_effects.py`; `pns_ai_chatboo/tests/test_seges_chatboo_access.py` (dos tests de `unlink` y caso (d)) y su cabecera |
| 9 | — | [DOC] | `parches_pns_ai.md` (entradas 11 adaptado y 17 a 22, índice, `grep` de PNS-70, línea base de E2′); `plan_correccion_pns_ai_3879.md` (estado de E2′; §3: URLs MCP de LIYBEN y auditoría de adjuntos; hoja de E4′); `verificacion_seguridad_pns_ai.md` (P-20 y validaciones de E2′); `seguimiento_informe_pns_ai.md` (PNS-100 nuevo; PNS-19, 17, 82, 37, 70 y 20) |

**Hoja de E4′, entradas nuevas** (en el commit 9):
- tokens de portal (`access_token`, `signup_token`);
- reenvío de `params` y `data` en las redirecciones de `request_public_http`;
- caché del agente confirmada en la vista previa de `bundle_import_wizard` (`_persist_cache_isolated`, y
  posible espera por bloqueo);
- `onchange_email` y Gravatar;
- `bus.presence.update` en cursor propio.
- `iap.account` queda como observación del core (ACL estándar), sin parche.

### Orden de trabajo y validación

1. **Comprobaciones previas a implementar** (solo lectura; si alguna cambia el diseño, se para y se
   consulta):
   - (f) de PNS-19: qué lee la Caja A;
   - `auto_join` en los many2one hacia modelos cerrados;
   - colisiones de nombre de los 28 del parche 22;
   - inventario de PNS-07 reafirmado.
2. **Parches 11 y 17 a 22, uno por commit**, y los tests de E2′. Después, `py_compile` con Python 3.7.3 y
   `odoo_lint.py --revisar --base c639fa8`.
3. **Laboratorio** (`lab_pns_ai_3879`):
   - `odoo-dev 14 tests pns_base,pns_ai_mcp,pns_ai_chatboo` contra la línea base de E1′ (260 · 18 F · 32 E);
   - neutralización de cada parche;
   - reinicio del contexto antes de cualquier prueba por RPC;
   - P-19, P-37 y P-37b, P-70 (casos 1 a 5), la prueba manual de P-17 y P-20 repetida con el parche (sin
     cambios en `write_date` ni en el valor).
4. **Staging `pns_demo`:**
   - consultas de §5.1 antes de subir;
   - P-37, P-37b, P-19, P-82 (prueba 4 bis de E2), P-70 en el navegador de Sergio, P-20;
   - no regresión del chat (descargas, gráficos, borrar una sesión), de Autorizaciones, de Revertir y
     Vaciar papelera, y de las importaciones con «Review» y Confirmar.
5. **Antes de LIYBEN** (plan, §3): URLs MCP finales (PNS-17), auditoría de adjuntos con la consulta de §5.2
   y consulta de §5.1.

**Plan de prueba para el VPS de pruebas (staging `pns_demo`):** módulos a actualizar, `pns_base`,
`pns_ai_mcp` y `pns_ai_chatboo` (`-u`). Casos, en la interfaz:
- Chatboo: pedir un gráfico tras abrir Ventas → Análisis, y volver a la vista gráfico;
- descargar un Excel desde el chat y borrar una sesión con adjuntos;
- en Autorizaciones, confirmar un plan; en el diario, Revertir y Vaciar papelera;
- importar un JSON de proveedores con «Review» y cerrar sin Confirmar (sin cambios), y luego con Confirmar
  (cambios);
- con un usuario de chat, pedir algo normal (lectura de datos) para comprobar que la Caja A sigue
  respondiendo.

## Implementación (27/10/2026)

- **Comprobaciones previas** (punto 1 de «Orden de trabajo», más dos pedidas por Sergio: `precommit` en
  «Review» y firmas de las sobrescrituras en `base`): resultado en [parches_pns_ai.md](parches_pns_ai.md),
  «Parches de la rama 14.0-pns-ai-3879 (E2′)», «Comprobaciones previas a implementar».
- **Cambio de diseño por la (f):** `page_url` y `page_edit` (helpers del lienzo en el sandbox) piden el
  diseño con el entorno de la caja A y leen `ai.provider`. **Decisión de Sergio (27/10/2026): ventana en
  `_ask_design`**, con cinco condiciones:
  1. el gestor de contexto (`_box_a_trusted`) es privado, está fuera de `build_safe_context` y de los
     helpers, y un test comprueba que el código de la caja A no lo alcanza;
  2. dentro de la ventana solo entran datos simples (`str`);
  3. la marca se restaura en `finally`, con un test en el que el driver falla;
  4. de la ventana solo sale el diseño (`content` y `error`), sin datos del proveedor;
  5. se registra como excepción del parche 18, con la nota para E3′ (al corregir M1, M2 y F1, revisar si la
     ventana sigue haciendo falta o si la llamada puede salir de la caja A).
- **Resultado:** parches 11 adaptado y 17 a 22 aplicados, 59 tests nuevos en verde, la línea base de E1′
  sin cambios (319 · 18 F · 32 E), y neutralización conforme. Detalle en el registro.
- **Pendiente:** reiniciar el contexto y las pruebas manuales ([lab_e2_3879.md](lab_e2_3879.md)); después,
  el staging (§5 de este documento y «Orden de trabajo», punto 4).

## Revisión del parche 18 y PNS-101 (27/10/2026)

- **Rechazo:** la revisión de `odoo-reviewer` rechaza el parche 18 y aprueba el resto con observaciones
  menores. Tres vías siguen llegando al secreto, todas reproducidas con sus scripts:
  1. `read_group` con alias: `['display_name:max(value)']` lee `value` con el nombre de un campo permitido;
  2. ids que no son enteros: `browse(7.0)` llega a la fila de `database.secret` y el filtro de claves la
     ignoraba;
  3. caché: en Odoo 14 es una por hilo; lo que el motor lee con su cursor, la caja A lo recibe sin pasar por
     `_fetch_field`.
- **Comprobación pedida por Sergio** (solo lectura de código): ¿llega el sandbox a `env.cache` o a
  `env.all`? Sí: `GuardedSandboxEnv.__getattr__` da cualquier atributo público y ni el AST ni
  `guarded_getattr` bloquean esos nombres. Se paró y se consultó.
- **Reproducción** (decisión 1 de Sergio; caja A real como `base.user_admin`, shell de
  `lab_pns_ai_3879_14`, con rollback, sin imprimir secretos; scripts `p101_repro.py` y
  `p101_repro_c2.py` en `/tmp/claude-1000/-home-soporte-GitHub-third-party/5b6a0dd0-041a-4357-ae79-6549a6ce09ac/scratchpad/`):
  - a) `env.cache` y `env.all` alcanzables, también con `x = env; x.all` y `getattr(env, 'al' + 'l')`;
  - b) `env.cache.get(p, p._fields['value'])` devuelve `database.secret` si el motor lo leyó antes;
  - c) `env.all`: dos entornos de la caja A (uid 2, uno con `su=True`, `READ ONLY` activo) y el del cursor
    principal (uid 2, `su=False`, `READ ONLY` desactivado), desde el que se lee `database.secret`;
  - d) `env.all.towrite`, `tocompute`, `protected` y `envs`, alcanzables (no se escribió en ellos).
  - Gravedad propuesta: **Crítica** (la decide Sergio). Pasa a PNS-101 en el
    [seguimiento](seguimiento_informe_pns_ai.md).
- **Decisiones de Sergio (27/10/2026):**
  1. reproducción de solo lectura antes de seguir (hecha, arriba);
  2. opción A como parche nuevo 23 (PNS-101), con commit y tests propios: inventario de atributos antes de
     fijar la lista de `GuardedSandboxEnv`; `cache`, `all`, `envs`, `towrite`, `tocompute` y `protected`
     bloqueados como atributo (nunca como nombre) en el AST y en `guarded_getattr`;
  3. revisar si alguna función que el sandbox puede llamar lee credenciales con el entorno principal
     mientras dura la caja A;
  4. `registry.clear_caches()` en `_invalidate_after_preview_rollback` (los dos caminos);
  5. después, los cierres del parche 18 y el resto de la revisión.
- **Decisión 3, resultado** (solo lectura de código): los helpers de `build_safe_context`
  (`field_selection`, `search_by_affinity`…) y los de módulos (`collect_sandbox_helpers`, solo
  `chatboo.session`) usan el entorno de la caja A, no el principal. La única que lee credenciales es la
  llamada de diseño del lienzo (`page_url`, `page_edit` → `_ask_design` → `llm_completion_for_agent`), ya
  dentro de la ventana, que ahora vacía la caché al cerrarse. Los cursores propios que abren
  `_store_design`, `_store_title` y `ai.log._create_log_entry` escriben `chatboo.session` y `ai.log`, sin
  leer credenciales. No hay ninguna otra que tratar.
- **Inventario de atributos del `env`** (decisión 2): en la entrada del parche 23 del
  [registro](parches_pns_ai.md). Resultado: el código del sandbox usa `user`, `company`, `companies`,
  `context`, `lang`, `uid` y `ref`; el motor recibe el mismo envoltorio después de la ejecución y usa
  además `cr` y `registry`, que el código del sandbox no puede nombrar.
- **Resultado:** parche 18 corregido (tres cierres), cambio en el 21, parche 23 nuevo; 341 tests, 18 F y
  32 E (los mismos por nombre), 22 tests nuevos en verde; neutralización conforme, cada cierre por separado.
  Scripts del revisor: rechazo en todos los casos salvo el C de `p18_check.py`, que pone la marca con
  `setattr` sin pasar por `tool_relaxaicode` (por la herramienta real, rechazo). Detalle en el
  [registro](parches_pns_ai.md), «Revisión de E2′ (27/10/2026)».

### Parches y commits de E2′ (actualizado tras la revisión)

Sustituye a la tabla de «Parches y commits de E2′ (definitivo)». El 23 va antes del commit de tests.

| Commit | Parche | PNS / tipo | Archivos |
|---|---|---|---|
| 1 | **11** (adaptado) | PNS-82, seguridad | `pns_ai_chatboo/models/chatboo_session.py` (`unlink`; solo esas líneas) |
| 2 | **17** | PNS-37, seguridad | `pns_ai_mcp/models/ai_change_journal.py`; `pns_ai_mcp/controllers/safe_plan.py` |
| 3 | **18** | PNS-19, seguridad | `pns_ai_mcp/models/box_a_guard.py` (nuevo), `pns_ai_mcp/models/__init__.py`, `pns_ai_mcp/controllers/tools_relaxaicode.py` (marca e import de `_box_a_clear_cache`), `pns_ai_chatboo/models/chatboo_session.py` (ventana: import, `_ask_design` y `_ask_design_raw`; solo esas líneas) |
| 4 | **19** | PNS-17, seguridad | `pns_ai_mcp/utils/fetch_url_safe.py`; `pns_ai_mcp/utils/mcp_client.py` |
| 5 | **20** | PNS-70, compatibilidad | `pns_ai_chatboo/static/src/js/chart.umd.min.js`; `pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js` |
| 6 | **21** | PNS-20, seguridad | `pns_base/models/operation_report_wizard.py` |
| 7 | **22** | PNS-100, seguridad | `pns_ai_mcp/controllers/validators_base.py` (bloque de 28 nombres; solo esas líneas) |
| 8 | **23** | PNS-101, seguridad | `pns_ai_mcp/controllers/validators_base.py` (`RELAXAICODE_ENV_STATE_*`; solo esas líneas), `pns_ai_mcp/controllers/validators.py`, `pns_ai_mcp/controllers/context_builder.py` |
| 9 | — | Tests de E2′ | `pns_ai_mcp/tests/__init__.py`, `test_seges_change_journal.py`, `test_seges_sandbox_credentials.py`, `test_seges_fetch_redirect.py`, `test_seges_import_preview.py`, `test_seges_sandbox_side_effects.py`, `test_seges_sandbox_env.py` (nuevo, 23); `pns_ai_chatboo/tests/__init__.py`, `test_seges_chatboo_access.py`, `test_seges_canvas_box_a.py`, `test_seges_skill_env.py` (nuevo, 23) |
| 10 | — | [DOC] | `parches_pns_ai.md`, `plan_correccion_pns_ai_3879.md`, `verificacion_seguridad_pns_ai.md`, `seguimiento_informe_pns_ai.md` (PNS-100 y PNS-101 nuevos), `e2_propuesta_3879.md`, `lab_e2_3879.md` (`pns70_diagnostico_3879.md` ya va en `88ba581`) |

`chatboo_session.py` lleva los parches 11 y 18, y `validators_base.py` los parches 22 y 23: en GitHub
Desktop se separan seleccionando las líneas de cada marcador.


## Segundo rechazo de E2′ (28/10/2026): C1/V1/V2 y C2

`odoo-reviewer` **rechaza** E2′ por fugas del sandbox que **no introduce** E2′ (están en 3.1.782 y en
LIYBEN). Confirmadas por la herramienta real: **C1** (`.format` con la plantilla en variable llega a
`odoo.tools.config` → `admin_passwd`/`db_password`), **C2** (`user`/`company` con `su=True` saltan ACL y
record rules); por lectura, **V1** (`string.Formatter` por import) y **V2** (`type()` de un `attrgetter`),
que devuelven el objeto Python real (→ `__globals__` → `__builtins__` → `__import__`).

### Fase 1 — inventario de puntos de resolución de nombres en runtime

| Punto | Dónde | ¿Filtro común antes? | Caso que colaba |
|---|---|---|---|
| `guarded_getattr` (builtin `getattr`) | `context_builder.py` | Sí | — |
| `attrgetter`/`methodcaller` → `_check_attr_path` | `context_builder.py` | Sí (vía `guarded_getattr`) | — |
| `SafeModuleFacade._module_facade_rejects` | `context_builder.py` | Parcial (sin `DANGEROUS_FORMAT_NAMES`) | V1 (`from string import Formatter`) |
| `str.format`/`format_map`, plantilla no literal | no había formateador propio | No | C1 y variantes (`f=t.format`, `getattr(t,'format')`, `methodcaller`) |
| `type(x)` 1 arg, clases crudas | builtins/globales | — (objeto real) | V2 (solo por un canal dunder: `format`/literal) |
| `env.user`/`env.company` | `api.py` fuerza `su=True` | — | C2 |

### Enfoque de raíz (decisión de Sergio, Crítica)

Impedir resolver los nombres peligrosos **por ninguna vía**, en el punto de resolución: predicado único
`sandbox_forbidden_name` (dunder + privado + PRIVILEGE + ENV_STATE + ORM + SIDE_EFFECT + DANGEROUS_ATTR +
DANGEROUS_FORMAT + `format`/`format_map`) en `guarded_getattr`, `_check_attr_path` y
`_module_facade_rejects`; **formateador propio** (`relaxaicode_format_guard.py`) que reescribe en el AST el
acceso a `.format`/`.format_map` a `_sandbox_str_attr` y resuelve los campos por `guarded_getattr` (cubre
plantilla literal y en variable); `Markup` rechazado. C2: `user`/`company`/`companies` sin su
(`_identity_no_su`). El AST con el filtro ampliado es defensa adicional.

### Parches y commits de E2′ (tras el segundo rechazo)

> **Superada (28/10/2026)** por «Commits de E2′: regla de tres commits (28/10/2026)», al final de este
> documento.

Todo C1/V1/V2 amplía el **parche 23** (PNS-101 ampliado); C2 es el **parche 24** (PNS-102 nuevo). Tres
commits:

| Commit | Contenido | Archivos |
|---|---|---|
| A — parche 23 ampliado (código) | formateador y predicado único, A1/S1 | `controllers/relaxaicode_format_guard.py` (nuevo), `controllers/validators_base.py` (`sandbox_forbidden_name`, `RELAXAICODE_STR_FORMAT_NAMES`, `_is_dunder`), `controllers/context_builder.py` (predicado en `guarded_getattr`/`_module_facade_rejects`; A1/S1; `_identity_no_su` lo comparte C2), `controllers/validators.py` (filtro de campos literal), `controllers/tools_relaxaicode.py` (compila con `compile_sandbox_code`, inyecta `_sandbox_str_attr`) |
| B — parche 24 (código) | `user`/`company`/`companies` sin su | `controllers/context_builder.py` (`_identity_no_su` y su uso en `GuardedSandboxEnv` y `build_safe_context`) |
| C — tests y docs | tests nuevos y documentación | `tests/__init__.py`, `tests/test_seges_format_guard.py`, `tests/test_seges_identity_su.py`; `parches_pns_ai.md`, `seguimiento_informe_pns_ai.md`, `plan_correccion_pns_ai_3879.md`, `pns_ai_decisiones.md`, `e2_propuesta_3879.md`, `lab_e2_3879.md` |

`context_builder.py` recibe cambios en A y B; en GitHub Desktop se separan por líneas (el helper
`_identity_no_su` y su uso van en B). **LIYBEN: claves MCP revocadas el 27/10/2026; regenerarlas tras el
despliegue.**

## Commits de E2′: regla de tres commits (28/10/2026)

Regla decidida por Sergio el 27/10/2026: **commit 1 = código, commit 2 = tests, commit 3 = documentación**,
por carpetas completas. Sustituye a todas las tablas de commits anteriores de este documento («definitivo»,
«actualizado tras la revisión» y «tras el segundo rechazo»). HEAD de partida: `c639fa8` (más `88ba581`,
[DOC], ya subido). Ningún archivo mezcla código y tests, así que **no hay que separar líneas** en GitHub
Desktop: cada archivo va entero a un único commit (también `context_builder.py`, `validators_base.py` y
`chatboo_session.py`, que llevan varios parches). Los marcadores `# Seges: parche N (PNS-XX, <tipo>)` del
código se mantienen y son los que relacionan cada línea con su parche.

| Commit | Contenido | Carpetas (completas) | Archivos |
|---|---|---|---|
| 1 — código | Parches 11 (adaptado), 17, 18, 19, 20, 21, 22, 23 (ampliado, con A1/S1, el blindaje de nombres internos y la segunda vuelta de 28/10: fachadas de `operator` como funciones y helper único `run_sandbox_code`, que toca `skill_runtime.py`) y 24 | `pns_ai_mcp/controllers/`, `pns_ai_mcp/models/`, `pns_ai_mcp/utils/`, `pns_ai_chatboo/models/`, `pns_ai_chatboo/static/src/js/`, `pns_base/models/` | `context_builder.py`, `relaxaicode_format_guard.py` (nuevo), `safe_plan.py`, `tools_relaxaicode.py`, `validators.py`, `validators_base.py`; `models/__init__.py`, `ai_change_journal.py`, `box_a_guard.py` (nuevo); `fetch_url_safe.py`, `mcp_client.py`, `skill_runtime.py`; `chatboo_session.py`; `chart.umd.min.js`, `chatboo_heavy_libs.js`; `operation_report_wizard.py` |
| 2 — tests | Tests de Seges de E2′ | `pns_ai_mcp/tests/`, `pns_ai_chatboo/tests/` | `pns_ai_mcp/tests/`: `__init__.py`, `test_seges_change_journal.py`, `test_seges_facade_class.py` (nuevo), `test_seges_fetch_redirect.py`, `test_seges_format_guard.py`, `test_seges_identity_su.py`, `test_seges_import_preview.py`, `test_seges_sandbox_credentials.py`, `test_seges_sandbox_env.py`, `test_seges_sandbox_side_effects.py` (todos nuevos salvo `__init__.py`); `pns_ai_chatboo/tests/`: `__init__.py`, `test_seges_chatboo_access.py`, `test_seges_canvas_box_a.py` (nuevo), `test_seges_skill_env.py` (nuevo) |
| 3 — [DOC] | Documentación de E2′ | `docs/pendiente/` | `e2_propuesta_3879.md`, `lab_e2_3879.md` (nuevo), `parches_pns_ai.md`, `plan_correccion_pns_ai_3879.md`, `pns_ai_decisiones.md`, `seguimiento_informe_pns_ai.md`, `verificacion_seguridad_pns_ai.md` |

Títulos propuestos, en el estilo de E1′:

1. `[FIX] pns_ai_mcp, pns_ai_chatboo, pns_base: E2′, parches 11 y 17 a 24 (PNS-82, 37, 19, 17, 70, 20, 100, 101, 102)`
2. `[ADD] pns_ai_mcp, pns_ai_chatboo: tests de Seges de E2′`
3. `[DOC] E2′: parches 11 y 17 a 24, revisiones y validación en laboratorio`

Antes de cada commit, comprobar en GitHub Desktop que la lista de archivos marcados coincide con esta
tabla (37 archivos en total: 16 de código, 14 de tests y 7 de documentación). Respecto a la versión de
35 (primera vuelta del parche 23 ampliado), la segunda vuelta (28/10/2026) añade `pns_ai_mcp/utils/skill_runtime.py`
al commit de código y `pns_ai_mcp/tests/test_seges_facade_class.py` al de tests.

**LIYBEN:** claves MCP revocadas el 27/10/2026; regenerarlas tras el despliegue.
