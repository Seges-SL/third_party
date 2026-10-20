# Spec: correcciones_pns_ai_entrega2 (Odoo 14.0)

- **Entrega:** E2 del [plan de corrección](../pendiente/plan_correccion_pns_ai.md) · **Parches:** 11 y 12
- **Rama:** `14.0-pns-ai-correcciones` · **Fecha:** 20/10/2026 · **Estado:** pendiente de aprobación
  de Sergio
- **Módulos afectados:** `pns_ai_chatboo` 2.1.453 (parche 11) y `pns_ai_mcp` 3.1.782 (parche 11, lista
  del sandbox, y parche 12). Apache-2.0, base propia de Seges por N12. `pns_base` no cambia.
- **Decisiones de las que parte:** D4, D8, D33, N11 y N12 ([decisiones](../pendiente/pns_ai_decisiones.md))
- **Versión:** Odoo 14.0 (`CLAUDE.md` del repo). Imagen de pruebas `odoo-dev:14-lab_pns_ai`
  (Python 3.7.3)
- **Código de referencia consultado:** `/opt/odoo-src/14.0/odoo` (core: `ir_attachment.py`,
  `ir_http.py`, `res_users.py`, `api.py`, `base_groups.xml`) y `/opt/odoo-src/14.0/vertical-instaladores`.
  Del módulo, solo los archivos locales del repo (no `/opt/odoo-src/14.0/third_party`).
- **Modelo:** [spec E1](correcciones_pns_ai_entrega1.md) (formato, criterios, marcadores, tests y
  ajustes del staging).

## 1. Objetivo y reglas de negocio

### 1.1 Objetivo

| PNS | Qué se corrige | Estado hoy | Prueba que lo demuestra |
|---|---|---|---|
| PNS-82 (parche 11) | `chatboo.session.claim_turn_file_chips` (y `apply_`/`stage_`/`consume_*_chips`) engancha en `sudo` a una sesión cualquier adjunto sin `res_model` o sin `res_id`, sea de quien sea; después `/pns_ai_mcp/session_file` y `/web/content` lo sirven y el borrado de la sesión lo borra | VULNERABLE | Fase 3b-1, grupo b (`verificacion_seguridad_pns_ai.md:774-777`) |
| PNS-01 / PNS-02, resto (parche 12) | `user.add_group` / `user.remove_group` solo exigen `group_ai_admin`; `_apply_user_add_group` / `_apply_user_remove_group` resuelven y escriben en `sudo`. Un AI Administrator sin Ajustes se da `base.group_system` (o se lo quita a un administrador) con un plan que él mismo confirma | PARCIAL (no probado a propósito, informe 2 §5) | Seguimiento PNS-01/02; staging de esta entrega |

### 1.2 Reglas

1. **R1 (PNS-82):** ningún usuario (interno sin relación ni portal) puede enganchar a una sesión, por
   ninguna vía, un adjunto que no haya creado él; ni descargarlo después por
   `/pns_ai_mcp/session_file` o `/web/content`. Tras el intento la BD no cambia.
2. **R2 (PNS-82):** el dueño de la sesión sigue viendo y descargando sus descargas del chat (Excel,
   PDF, Word, SVG, ficheros adjuntados, binarios de `fetch_url`/`api_call` del turno).
3. **R3 (PNS-82):** borrar una sesión solo borra los adjuntos que pertenecen de verdad a ella (creados
   por su dueño). Un adjunto ajeno que cuelgue de ella (enganchado antes del parche) vuelve a ser
   huérfano de su creador y no se borra.
4. **R4 (PNS-01/02):** dar o quitar un grupo nativo con `user.add_group` / `user.remove_group` exige
   `base.group_system` **además** de `group_ai_admin`, comprobado sobre el usuario real que propone y
   que ejecuta (el que confirma), antes de cualquier `sudo()`. La comprobación no depende de los datos
   XML ni de los registros de `ai.trusted.action`, y no se pierde con `-u`.
5. **R5:** `view.*` y `field.set_required` / `op=field_required` no cambian (diseño aceptable según el
   seguimiento y el informe 2, §3.2).
6. **R6 (límites de N11):** cambio mínimo; Python 3.7.3; sin dependencias nuevas; sin tocar `version`,
   `depends`, `external_dependencies`, `i18n`, `LICENSE`, `NOTICE` ni `ir.model.access.csv`; no se tocan
   los parches 1 a 10; marcador `# Seges: parche N (PNS-XX, seguridad). Ver docs/pendiente/parches_pns_ai.md`
   junto a cada cambio.

   Esta entrega añade **un** mensaje nuevo visible (parche 12), en inglés y con `_()`, sin traducción
   (no se toca `i18n`; ver la duda D-6).

## 2. Soluciones existentes evaluadas (OCA / core / repo común) y conclusión

### 2.1 Qué hace el core de Odoo 14 con los adjuntos huérfanos

`ir.attachment.check` (`/opt/odoo-src/14.0/odoo/odoo/addons/base/models/ir_attachment.py:418-459`):

- Fuera de `sudo`, un adjunto **sin `res_id`** (huérfano, con o sin `res_model`) solo lo lee o
  escribe su creador o un administrador de Ajustes (`:434`: `not res_id and create_uid != self.env.uid`
  → `AccessError`).
- Si tiene `res_model` y `res_id`, se exige permiso sobre el registro (`:436-459`). Si el registro ya
  no existe, **no se comprueba nada** (`:444-454`: `browse(res_ids).exists()` vacío): cualquier interno
  con ACL de lectura del modelo lo lee. Es relevante para el borrado en cascada (§5.3).
- `sudo()` (`env.su`) se salta todo (`:420`).

`/web/content` (`ir_http.py:298-338`) lee el adjunto como el usuario: `AccessError` → 403.
`/pns_ai_mcp/session_file` (`pns_ai_mcp/controllers/session_file.py:20-32`, `_may_read`) entrega al
creador, a un administrador de Ajustes o a quien pueda leer el registro del que cuelga.

**Consecuencia:** el criterio del core para un huérfano es «es de quien lo creó». El fallo de
`claim_turn_file_chips` es saltarse ese criterio con `sudo()`. La corrección natural es aplicarlo
explícitamente (comparar `create_uid` con el usuario real) antes de escribir en `sudo`.

### 2.2 Qué hace el core con «usuario real» y `sudo`

- En Odoo 14 `sudo()` conserva el `uid` (`env.su = True`). `self.env.uid` y `self.env.user` siguen
  siendo el usuario real dentro de `sudo`.
- `env.is_system()` devuelve `True` en `sudo` (`api.py:538-541`: `self.su or …`): **no sirve** para
  comprobar el grupo del usuario real. Se usa `self.env.user.has_group('base.group_system')`
  (`res_users.py:813-837`, consulta `res_groups_users_rel` con el `uid`), como el fabricante en PNS-09
  (`pns_ai_mcp/models/external_server.py:566-584`, `_check_may_set_stdio_command`:
  `user._is_superuser() or user.has_group('base.group_system')` y `UserError`).
- `base.user_root` (uid 1) es miembro de `base.group_system` (`base_groups.xml:14-18`).

### 2.3 Otras soluciones

- **OCA / core / repo común:** no aplican. Es la corrección del código de un tercero (N11). No hay en
  OCA 14 nada que «cierre» métodos de otro módulo; un `_inherit` desde un módulo nuevo duplicaría la
  lógica y dejaría el método original público. Se descarta, como en E1.
- **Corrección del informe 2, §2.2** (orden de preferencia): 1) privado; 2) si debe seguir público,
  grupo/propiedad antes del `sudo()`; 3) no confiar en el ACL ni en efectos laterales; 4) test
  negativo por método.
- **§3.2 del informe 2 para PNS-01/02:** «exigir también `base.group_system`, comprobado sobre el
  usuario real, como ya hace la versión nueva para los servidores `stdio`». Se sigue literalmente.

**Conclusión:**
- **A (PNS-82):** opción 1 (privado) para los cuatro métodos del flujo de chips **y además** filtro por
  usuario real antes del `sudo()` en `_claim_turn_file_chips`, porque el privado solo no basta (el
  búfer `staged_assistant_files` lo escribe el dueño por ORM y lo consume el worker; ver §5.1.3). Más
  filtro en el borrado en cascada.
- **B (PNS-01/02):** comprobación en Python dentro de `ai.system.action`, en los cuatro métodos
  `_preview_*`/`_apply_*` de grupos de usuario. No en el XML (§5.4).

## 3. Manifest (depends, orden de data, licencia, autor)

**Sin cambios** en ningún `__manifest__.py` (ni `version`, ni `depends`, ni `external_dependencies`,
ni `data`). Licencia de los módulos: Apache-2.0 (Patanegra Soft).

Los cambios son solo de Python: no hay campos, vistas ni datos nuevos o modificados. **No hace falta
`-u`**: basta con reiniciar el servidor (§9.3). La carpeta nueva `pns_ai_chatboo/tests/` la descubre
Odoo sola (`odoo.modules.module.get_test_modules`); no hace falta importarla desde el `__init__.py`
del módulo.

## 4. Modelos y campos (tabla: modelo | herencia | campo | tipo | parámetros | propósito)

No hay campos nuevos ni cambios de herencia.

| Modelo | Herencia | Campo | Tipo | Parámetros | Propósito |
|---|---|---|---|---|---|
| — | — | — | — | — | Sin campos nuevos |

Cambios de métodos:

| Modelo | Herencia | Antes | Después | Decorador | PNS / parche |
|---|---|---|---|---|---|
| `chatboo.session` | `_name` (propio) | `claim_turn_file_chips(chips)` | `_claim_turn_file_chips(chips)` + filtro dueño/creador | (de registro) | PNS-82 / 11 |
| `chatboo.session` | `_name` | `apply_assistant_download_chips(chips)` | `_apply_assistant_download_chips(chips)` | (de registro) | PNS-82 / 11 |
| `chatboo.session` | `_name` | `stage_assistant_download_chips(chips)` | `_stage_assistant_download_chips(chips)` | (de registro) | PNS-82 / 11 (D-1) |
| `chatboo.session` | `_name` | `consume_staged_assistant_download_chips()` | `_consume_staged_assistant_download_chips()` | (de registro) | PNS-82 / 11 (D-1) |
| `chatboo.session` | `_name` | `unlink()` | igual nombre: comprueba acceso antes del `sudo` y solo borra adjuntos del dueño | (CRUD) | PNS-82 / 11 |
| `ai.system.action` | `_name` (propio) | — | **nuevo** `_check_may_change_user_groups()` | — | PNS-01/02 / 12 |
| `ai.system.action` | `_name` | `_preview_user_add_group`, `_apply_user_add_group`, `_preview_user_remove_group`, `_apply_user_remove_group` | igual nombre: llaman primero a `_check_may_change_user_groups()` | `@api.model` | PNS-01/02 / 12 |

Comprobado que ningún nombre nuevo choca con `BaseModel` ni con métodos del core 14 (Grep de
`_claim_turn_file_chips`, `_apply_assistant_download_chips`, `_stage_assistant_download_chips`,
`_consume_staged_assistant_download_chips` y `_check_may_change_user_groups` en
`/opt/odoo-src/14.0/odoo`: 0 coincidencias).

## 5. Métodos (firma, comportamiento, llamada a super, decoradores)

### 5.1 A) PNS-82 — Inventario y diseño

#### 5.1.1 Inventario de llamadores (A)

Búsqueda (Grep) de los nombres en todo `third_party` (Python, JS, XML, datos, `ai/`), en los JS de
Chatboo (`rpc`/`_rpc`/`fetch` con `method:` o `route:`), en las rutas de controlador y en
`/opt/odoo-src/14.0/vertical-instaladores`.

Resultados generales:
- **JS:** ningún `rpc`/`_rpc` con `method:` sobre `chatboo.session`. Todo el cliente de Chatboo usa
  **rutas** (`/chatboo/...`, `chatboo_component_v2.js`, `chatboo_export.js`, `chatboo_systray.js`);
  los únicos `method:` son `'POST'` de `fetch` (`chatboo_component_v2.js:2132`, `:2572`) y el
  `'call'` del sobre JSON-RPC (`:2135`).
- **XML:** ningún botón, acción de servidor ni cron con estos nombres. El cron de Chatboo llama a
  `model.cron_maintenance()` (`pns_ai_chatboo/data/chatboo_async_cron.xml:11`).
- **Otros módulos de `third_party`** (`auto_database_backup`, `ir_attachment_s3`, `ir_attachment_url`,
  `iwesabe_dynamic_product_code`, `login_user_detail`, `odoo_whatsapp_integration`, `server_info`,
  `whatsapp_mail_messaging`): 0 coincidencias. `ir_attachment_url`/`ir_attachment_s3` no sobrescriben
  `ir.attachment.check`.
- **`pns_ai_mcp`:** solo `merge_download_chips_into_session` (`utils/session_download.py:773-775`), que
  es un no-op, llamado desde `controllers/safe_plan.py:917`. No llama a los métodos de Chatboo.
- **vertical-instaladores (14.0):** 0 coincidencias.
- **Tests:** ninguno (Chatboo no tiene tests).

| Método | Llamador (archivo:línea) | Contexto | Usuario con que se ejecuta | ¿RPC desde el navegador? |
|---|---|---|---|---|
| `claim_turn_file_chips` | `pns_ai_chatboo/models/chatboo_session.py:362` | Dentro de `stage_assistant_download_chips` | El del env del llamador (ver `apply_`) | No |
| ″ | `chatboo_session.py:406` | Dentro de `apply_assistant_download_chips` | Ídem | No |
| ″ | `chatboo_session.py:491` | `fulfill_client_export` (Word/PDF/HTML que monta el navegador), tras `persist_turn_file` | Usuario real de la ruta `/chatboo/sessions/fulfill_export` (`controllers/chatboo.py:301-323`, comprueba dueño en `:313`), sin `sudo`. JS: `chatboo_export.js:3671-3672` | **La ruta sí** (JSON, `auth='user'`); el método, no |
| ″ | `pns_ai_chatboo/models/chatboo_async_request.py:1586` | `_persist_turn_files` (ficheros adjuntados con el clip) ← `_save_to_session:1684` | uid del job = dueño de la sesión (el `create` fija `user_id = env.uid` y exige sesión propia, `:203-216`; el hilo abre `Environment(cr, uid, …)`, `:281`; `_finalize` reabre con el mismo uid, `:913-924`). Sin `sudo` | No |
| ″ | `chatboo_async_request.py:1738` | `_save_to_session`: chips de `done_meta['assistant_files']` (motor, `agent_engine.py:4847-4854`), del búfer (`:1702`), huérfanos de la sesión (`:1703`) y SVG en línea (`:1723`) | Ídem. También desde `request_cancel` (`:2014`, `_save_to_session(msg, {}, error=None)`), que llama el dueño (`:1999`) por la ruta `/chatboo/async/cancel` **o por RPC directo** (método público) | No (pero ver hallazgo H-2) |
| ″ | **RPC directo** `/web/dataset/call_kw`, `/jsonrpc`, `/xmlrpc` | El método no lee la sesión: la regla por `user_id` **no se aplica**. Funciona sobre cualquier id de sesión | Cualquier interno **y portal** | Solo como ataque (fase 3b-1) |
| `apply_assistant_download_chips` | `chatboo_session.py:517` | `fulfill_client_export`, si no había chip pendiente que sustituir | Usuario real de la ruta | No |
| `stage_assistant_download_chips` | `chatboo_session.py:413` | `apply_`, si el último mensaje no es del asistente | Ídem | No |
| `consume_staged_assistant_download_chips` | `chatboo_async_request.py:1702` | `_save_to_session` (lee el búfer con SQL y lo vacía) | uid del job (dueño) | No |
| `unlink` (sesión) | `pns_ai_chatboo/controllers/chatboo.py:407` | Ruta `/chatboo/sessions/delete` (comprueba dueño `:405`); JS `chatboo_component_v2.js:1456-1457` | Usuario real, sin `sudo` | **La ruta sí** |
| ″ | `controllers/chatboo.py:427` | Ruta `/chatboo/sessions/bulk_delete` (comprueba dueño `:423-425`); JS `chatboo_component_v2.js:1524-1525` | Ídem | **La ruta sí** |
| ″ | `chatboo_session.py:1380` | `_cleanup_old_sessions` ← `chatboo_async_request.cron_maintenance:2200` ← cron | `sudo()` (`:1372`) | No (pero `cron_maintenance` es público: H-4) |
| ″ | RPC directo `unlink` | ORM estándar: regla por `user_id` en `super().unlink()` | Interno (portal sin ACL) | No (control) |

#### 5.1.2 Cómo se generan hoy los adjuntos de descarga del chat

| Origen | Quién lo crea | `res_model` / `res_id` al crearlo | `create_uid` | Cuándo se «reclama» |
|---|---|---|---|---|
| Descargas del motor: exportaciones Excel/CSV/etc. pedidas en el turno (`AgentEngine._attach_requested_file_export`, `agent_engine.py:4927-4956`) | `persist_turn_file` → `persist_turn_file_detail` (`pns_ai_mcp/utils/session_download.py:403-481`): `ir.attachment` en `sudo` en un cursor propio con commit (`_run_on_committed_cursor`, `:373-400`, mismo `uid`) | **Ninguno** (huérfano) | Usuario del turno (env del worker) | Al guardar el turno: `_save_to_session` → `claim` (`chatboo_async_request.py:1738`), con los chips de `done_meta['assistant_files']` |
| Binarios de `fetch_url`/`api_call` de un plan (`safe_plan.py:1402-1492`) | Ídem (`persist_chatboo_session_file_detail`), con el env de quien ejecuta el plan | Ninguno | Quien ejecuta el plan (en el turno, el usuario; auto-confirmado, `with_user(user_id)`, `safe_plan.py:2256`) | Si el plan corre en el turno, entra en `export_chips` del motor (`agent_engine.py:2972-2991`) y se reclama en `:1738`. Si lo confirma otro usuario fuera del turno, **no se reclama nunca** (`merge_download_chips_into_session` es un no-op) |
| PDF/Word/HTML montados en el navegador | `fulfill_client_export` → `persist_turn_file` | Ninguno | Usuario de la ruta | Inmediatamente (`chatboo_session.py:491`); si no había chip pendiente, `apply_` → `stage_` (búfer) |
| Ficheros adjuntados con el clip | `_persist_turn_files` → `persist_turn_file` | Ninguno | uid del job | Inmediatamente (`chatboo_async_request.py:1586`) |
| SVG en línea de la respuesta | `persist_inline_svgs_from_html` (`pns_ai_mcp/utils/svg_download.py:447-461`) → `persist_chatboo_session_file` | Ninguno | uid del job | `:1735-1738` |
| Imágenes pegadas o adjuntadas | `_persist_turn_images` (`chatboo_async_request.py:992-1040`), **sin `sudo`** | `chatboo.session` / sesión del job | uid del job | No pasan por `claim` (ya nacen colgadas) |
| **Copias de configuración** (PNS-20/D8) y otras exportaciones de `pns_ai_mcp` | `write_export_attachment`/`write_json_attachment` (`pns_base/utils/portable_io.py:342-369`), con `EXPORT_MARK`, purga a 24 h | **Ninguno** (o `res_model` con `res_id=0` si se pasa) | Quien exporta (AI Administrator / administrador). Llamadores: `res_config_settings.py:212`, `ai_provider.py:1135`, `mcp_user.py:720`, `external_server.py:1425`, `ai_agent.py:1464`, `safe_operation.py:2030`, `url_whitelist.py:296`, `ai_log.py:1013`, `ai_skill.py:1639`, `ai_context.py:2837`, `utils/artifact_bundle.py:284` | Nunca (no son del chat). **Son el blanco más grave de PNS-82** |

Además, cualquier huérfano de otros módulos (por ejemplo, adjuntos de un asistente con
`res_model` y `res_id=0`) cumple hoy la condición de `claim` (`:436-437`: solo se salta los que tienen
**los dos**).

**Criterio para distinguir los legítimos de los ajenos** (se evaluaron tres):

| Criterio | ¿Cubre todos los legítimos? | ¿Cierra los ajenos? | Conclusión |
|---|---|---|---|
| a) Solo los chips del búfer de la sesión (`stage_*`) | **No**: el búfer solo lo alimenta `fulfill_client_export` → `apply_` → `stage_`. Los chips del motor (`assistant_files`), los ficheros del clip y los SVG no pasan por él | **No**: el dueño escribe `staged_assistant_files` por ORM (`write` en su sesión, campo de texto sin protección) y el worker lo consume | Descartado |
| b) Ventana temporal (creados desde `started_at` del turno) | Sí, en el turno | No: un huérfano ajeno reciente (una copia de configuración recién exportada) entra en la ventana | Descartado como criterio único |
| c) **Creados por el propio usuario real** (`create_uid == self.env.uid`) **y** sesión del usuario real (`session.user_id == self.env.uid`) | **Sí**: todos los orígenes de la tabla crean el adjunto con el uid del dueño (el worker, la ruta y el motor corren con su uid) | **Sí**: un huérfano solo es «de» quien lo creó, que es exactamente el criterio del core (`ir_attachment.py:434`) | **Elegido** |

#### 5.1.3 Por qué el privado solo no basta (hallazgos del inventario)

- **H-1 — La regla de sesión no protege `claim`.** El método no lee ningún campo de la sesión
  (`self._name`, `self.id`), así que la regla por `user_id` no se aplica: por RPC funciona con el id
  de **cualquier** sesión, y también para un usuario de **portal** (sin ACL sobre `chatboo.session`,
  pero `call_kw` no la comprueba). El portal no puede descargar después (el core exige usuario interno,
  `ir_attachment.py:423`, y `_may_read` no le da la sesión), pero sí puede mover huérfanos ajenos a
  cualquier sesión, que luego los borra en cascada. El seguimiento decía «sobre una sesión propia (la
  regla por `user_id` lo exige)»: no es así.
- **H-2 — Vía sin método público: búfer + `request_cancel`.** Cualquier interno, sin acceso a Chatboo
  ni clave MCP, puede: (1) `write` en su sesión `{'staged_assistant_files': '[{"attachment_id": <id
  ajeno>}]'}`; (2) `create` de un `chatboo.async.request` pendiente en su sesión (ACL `1,1,1,0`,
  `ir.model.access.csv:3`); (3) `request_cancel()` por RPC (público, `chatboo_async_request.py:1992`).
  `request_cancel` llama a `_save_to_session` (`:2014`), que consume el búfer (`:1702`) y llama a
  `claim` (`:1738`). Privatizar los cuatro métodos **no** cierra esta vía; el filtro de `create_uid`
  sí. Lo mismo vale para cualquier chip que el motor deje en `assistant_files`.
- **H-3 — Sin RPC legítimo.** Ningún llamador legítimo usa los cuatro métodos por RPC: privatizarlos
  no rompe nada del navegador.

#### 5.1.4 Corrección (parche 11)

1. **Privados** `_claim_turn_file_chips`, `_apply_assistant_download_chips`,
   `_stage_assistant_download_chips` y `_consume_staged_assistant_download_chips` (D-1 para los dos
   últimos). Se actualizan sus 8 llamadores (§5.5).
2. **Filtro en `_claim_turn_file_chips`, antes del `sudo()` de escritura:**
   - si la sesión no es del usuario real (`self.sudo().user_id.id != self.env.uid`), no hace nada;
   - un adjunto solo se engancha si `att.create_uid.id == self.env.uid`.
   Se mantiene el `sudo()` de lectura/escritura del adjunto (el worker puede correr con un env sin
   permisos de escritura sobre el adjunto en otros contextos) y la condición original
   (`res_model and res_id` → no tocar). `self.env.uid` es el usuario real también dentro de `sudo`
   (§2.2). Sin mensajes nuevos: los ajenos se ignoran en silencio, como hoy los que ya tienen dueño.
3. **Borrado en cascada (`unlink`):**
   - comprobar `check_access_rights('unlink')` y `check_access_rule('unlink')` **antes** de los
     borrados en `sudo` (hoy el `sudo` va antes y solo lo deshace el rollback de la transacción;
     PNS-55). En `sudo` (cron) las dos comprobaciones no hacen nada;
   - de los adjuntos que cuelgan de las sesiones, se borran solo los creados por el dueño de la
     sesión (o sin `create_uid`). Los demás se **desenganchan** (`res_model = False`, `res_id = False`):
     vuelven a ser huérfanos de su creador, que los sigue leyendo (core `:434`), y no quedan colgando de
     una sesión borrada, donde el core los dejaría leer a cualquier interno (`:444-454`, §2.1).
4. **Copias de configuración (PNS-20/D8):** quedan cubiertas por el filtro (su `create_uid` es quien
   exporta). No se tocan sus llamadores. Solo el propio exportador podría engancharlas a **su** sesión,
   lo que no da acceso a nadie más.

`recover_orphan_download_chips` y `fulfill_client_export` no se tocan (D-3).

### 5.2 Sandbox de relaxaicode (A)

`chatboo.session` es alcanzable desde la caja A (`GuardedSandboxEnv` solo cierra `ai.api.server`,
`ai.context` y `ai.skill`; `validators.py:1064`). Los cuatro métodos escriben en el mismo cursor, que en
la caja A es `READ ONLY`, así que hoy fallarían; aun así, con el criterio de E1 (§5.3 de la spec E1),
los nombres que pasan a privados se añaden a `RELAXAICODE_SIDE_EFFECT_METHODS`: bloquea la llamada
literal, `getattr` con cadena estática, `attrgetter`/`methodcaller` y `guarded_getattr` en ejecución.
El hueco del alias (`f = m._claim_turn_file_chips; f()`) sigue para E3, como en E1 (D-2 de E1).

Observación para E3 (no se cambia): `fulfill_client_export` es público, alcanzable desde la caja A, y
`persist_turn_file` crea el adjunto en un **cursor propio con commit**, fuera del rollback.

Para B no hay métodos renombrados: no cambia la lista.

### 5.3 B) PNS-01/02 — Inventario

| Método | Llamador (archivo:línea) | Contexto | Usuario con que se ejecuta | ¿RPC desde el navegador? |
|---|---|---|---|---|
| `_apply_user_add_group` / `_apply_user_remove_group` | `pns_ai_mcp/models/ai_trusted_action.py:129` (`_apply` → `_resolve_method('apply_method')`, `:93-110`) | Nombre tomado del registro `ai.trusted.action` (`data/trusted_actions_system.xml:83`, `:93`) | El env de quien llama a `_apply` | No: privados (`AccessError`; `test_system_action.py:429-438`) |
| `ai.trusted.action._apply` | `controllers/safe_plan.py:845` | `execute_safe_plan`, paso `op='action'` | Env del humano (docstring `:770-772`); grupo comprobado en `_apply` (`ai_trusted_action.py:125-128`) | No |
| `execute_safe_plan` | `models/safe_operation.py:1395` | `execute_plan_now` (`exec_env = self.env`, `:1346`) | El del registro de la operación | No |
| `execute_plan_now` | `controllers/safe_plan.py:2256` | Auto-confirmación en la propuesta (`with_user(user_id)`). **No aplica a `op=action`**: `_all_steps_auto_confirmable` devuelve `False` (`:430-432`) | — | No |
| ″ | `controllers/safe_plan.py:2421` | `safe_plan_status` (herramienta MCP) | Usuario de la clave MCP | No |
| ″ | `models/safe_operation.py:878` | `_execute_plan_with_timeouts`, `uid = confirmed_uid = self.env.uid` de `resolve_execute` (`:727`) | **Quien ejecuta/confirma**. Viene de `/pns_ai_mcp/verification/execute` (`controllers/verification_ui.py:61`, solo el dueño; el registro va en `sudo` pero el uid es el real) o del botón `action_confirm_and_execute` (`safe_operation.py:1711-1749`, dueño o AI Administrator, `_can_resolve` `:308-315`) | La ruta y el botón (`call_button`) sí; el método, no |
| ″ | `models/safe_operation.py:999` | `_retry_confirmed_not_executed` (cron) | `confirmed_by_uid` → `user_id` → `SUPERUSER_ID` (`:988-992`) | No |
| `_preview_user_add_group` / `_preview_user_remove_group` | `ai_trusted_action.py:115` (`_preview`) ← `controllers/safe_plan.py:253` (`validate_safe_plan`, captura `UserError` → «Step N: …») y `:678` (`describe_safe_plan`, captura `Exception`) | Propuesta | Quien propone | No |
| Tests del fabricante | `tests/test_system_action.py:301-316` (superusuario), `:444-456` (interno: `PermissionError` antes de llegar) | — | — | — |
| `pns_base.utils.compat.user_add_group` / `user_remove_group` | `ai_system_action.py:721`, `:751`; `models/mcp_user.py:240`, `:246` (inverse de los flags de grupos **de IA** de `ai.mcp.user`, grupos fijos); reexportados en `pns_ai_mcp/utils/compat.py:17-18`; `setUp` de varios tests | Utilidad genérica | — | **No se tocan** (no son el punto de control; ver §5.4) |
| Otros módulos de `third_party` y vertical-instaladores | — | 0 coincidencias de `user.add_group`, `_apply_user_*` o `ai.trusted.action` | — | — |
| Prompt | `pns_ai_mcp/ai/contexts/core/system_prompt.xml:144`; `controllers/safe_plan.py:1939-1940` | Instrucciones al LLM («Authorization is the Confirm toast plus AI Administrator») | — | No se cambian (D-7) |

### 5.4 B) Dónde poner la comprobación de `base.group_system`

| Lugar | ¿Se pierde con `-u`? | ¿Lo puede deshacer un AI Administrator? | Conclusión |
|---|---|---|---|
| Dato XML (`group_ids` de `trusted_action_user_*` en `data/trusted_actions_system.xml`) | El archivo **no** es `noupdate` (no lleva `noupdate`; `__manifest__.py:133`): `-u` lo recarga. `eval="[(4, ref(...))]"` **añade** sin quitar | **Sí**: `ai.trusted.action` es `1,1,1,1` para `group_ai_admin` (`security/ir.model.access.csv:73`) | **Inservible**: además, `group_ids` significa «**al menos uno**» (`user_has_required_groups`, `ai_trusted_action.py:131-143`). Añadir `base.group_system` **relajaría** la condición (AI Admin **o** Ajustes) |
| `ai.trusted.action._apply` por `code` | No | **Sí**: el AI Administrator puede crear otro registro con otro `code`, `model_id = ai.system.action` y `apply_method = '_apply_user_add_group'`, o vaciar `group_ids` | Descartado |
| **`ai.system.action._preview_*`/`_apply_*` de grupos de usuario** (Python) | No (es código) | No: está en el método que hace el `sudo` | **Elegido** |
| `pns_base/utils/compat.py` | No | No | Descartado: utilidad genérica usada también por `mcp_user.py` para grupos de IA; y no conoce el usuario real |

**Comprobación:** método nuevo `_check_may_change_user_groups()` en `ai.system.action`, con el patrón del
fabricante en PNS-09:

```python
user = self.env.user
if user._is_superuser() or user.has_group('base.group_system'):
    return
raise UserError(_('Only a Settings administrator can add or remove user groups.'))
```

- Se llama al principio de `_preview_user_add_group`, `_apply_user_add_group`,
  `_preview_user_remove_group` y `_apply_user_remove_group`, **antes** de `_resolve_user`/`_resolve_group`
  (que leen en `sudo`).
- **En el preview:** `validate_safe_plan` lo llama al proponer y convierte el `UserError` en «Step N:
  Only a Settings administrator…» (`safe_plan.py:248-257`): no se crea la tarjeta (D-5). Además deja de
  revelar en `sudo` el nombre del usuario y del grupo a quien no puede cambiarlos.
- **En el apply:** cubre la ejecución, que corre con el usuario que confirma (§5.3), aunque la propuesta
  la hiciera otro (por ejemplo, un administrador de Ajustes propone y un AI Administrator sin Ajustes
  confirma desde Autorizaciones). El `UserError` en `execute_safe_plan` hace fallar el plan y cancela
  la autorización (`execute_plan_now`, docstring `:1279-1284`).
- `UserError` y no `AccessError`: es el tipo del patrón PNS-09 y el único que `validate_safe_plan`
  convierte en mensaje de propuesta.
- **Superusuario** (`_is_superuser()`): mantiene el test del fabricante `test_user_group_preview`
  (`self.env` de `TransactionCase` es el uid 1) y el último recurso `SUPERUSER_ID` del cron. `user_root`
  ya es de `base.group_system`.

**`view.*` y `field.set_required` (no se cambian, R5):**
- `view.set_field_readonly`/`invisible`/`domain`/`reset_field_modifiers` van por `op='action'` →
  `ai.trusted.action._apply` (exige `group_ai_admin`) → `_apply_view_modifier`
  (`ai_system_action.py:208-304`), que crea vistas heredadas en `sudo` con una `arch` cerrada
  (`build_modifier_arch`) y `ai.view.policy`.
- `field.set_required` y `view.set_field_required` como `op='action'` se rechazan al proponer
  (`is_required_atom`, `safe_plan.py:227-231` y `:840-843`); el camino real es `op='field_required'`,
  que `validate_safe_plan` solo deja a un AI Administrator (`:219-223`) y `execute_safe_plan` ejecuta
  llamando directamente a `_apply_field_set_required`/`_apply_view_set_field_required` (`:811-835`),
  **sin** pasar por `ai.trusted.action._apply`. En la ejecución solo se exige AI Writer
  (`controller_helpers.py:22-24`, `:102`); como el dueño no puede alterar los pasos guardados (PNS-03
  corregido), el control de la propuesta basta. Observación, sin cambio.
- Un test de no regresión confirma que un AI Administrator sin Ajustes sigue aplicando `view.*` (§9.2).

**Hallazgo H-5 (fuera de alcance):** como el AI Administrator tiene CRUD sobre `ai.trusted.action`, el
«vocabulario cerrado» de acciones de confianza no es cerrado para él: puede registrar una acción que
llame a cualquier método por nombre de cualquier modelo (`_resolve_method` usa `getattr` sin lista
de permitidos), con `group_ids` vacío. El ACL y las reglas del modelo destino siguen siendo la última
barrera para los métodos sin `sudo`; el riesgo está en los métodos `@api.model` que trabajan en `sudo`.
El parche 12 lo cierra para los grupos de usuario (la comprobación está en el método), pero no en
general. Propuesta en D-4.

### 5.5 Diffs por archivo

Las líneas son las del archivo actual de la rama (con los parches 1 a 10), antes de aplicar nada. Cada
marcador añade una línea y desplaza las siguientes. Indentación exacta a la del archivo. Sin cambios
de estilo. **Regla de marcadores:** un marcador junto a cada línea cambiada; una línea cambiada dentro
de un método corto, a cinco líneas o menos del marcador del `def`, se considera cubierta por él (como en
E1).

#### Parche 11 — PNS-82 (`pns_ai_chatboo` y lista del sandbox)

`pns_ai_chatboo/models/chatboo_session.py`
```diff
@@ -357 @@
-    def stage_assistant_download_chips(self, chips):
+    # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    def _stage_assistant_download_chips(self, chips):
@@ -362 @@
-        self.claim_turn_file_chips(chips)
+        self._claim_turn_file_chips(chips)
@@ -374 @@
-    def consume_staged_assistant_download_chips(self):
+    # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    def _consume_staged_assistant_download_chips(self):
@@ -401 @@
-    def apply_assistant_download_chips(self, chips):
+    # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    def _apply_assistant_download_chips(self, chips):
@@ -406 @@
-        self.claim_turn_file_chips(chips)
+        self._claim_turn_file_chips(chips)
@@ -413 @@
-            self.stage_assistant_download_chips(chips)
+            # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
+            self._stage_assistant_download_chips(chips)
@@ -415,4 @@
-    def claim_turn_file_chips(self, chips):
+    # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    def _claim_turn_file_chips(self, chips):
         """Hang engine-created attachments on this session."""
         self.ensure_one()
+        # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        uid = self.env.uid
+        if self.sudo().user_id.id != uid:
+            return
         Attachment = self.env['ir.attachment'].sudo()
@@ -436,3 @@
             if att.res_model and att.res_id:
                 continue
+            # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
+            if att.create_uid.id != uid:
+                continue
             att.write({
@@ -491 @@
-        self.claim_turn_file_chips([chip])
+        # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        self._claim_turn_file_chips([chip])
@@ -517 @@
-            self.apply_assistant_download_chips([chip])
+            # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
+            self._apply_assistant_download_chips([chip])
@@ -1294 @@
+        # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        self.check_access_rights('unlink')
+        self.check_access_rule('unlink')
         if self.ids:
@@ -1331,2 @@
                 if atts:
-                    atts.unlink()
+                    # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
+                    owner = {s.id: s.user_id.id for s in self.sudo()}
+                    own = atts.filtered(
+                        lambda a: a.create_uid.id in (False, owner.get(a.res_id)))
+                    (atts - own).write({'res_model': False, 'res_id': False})
+                    own.unlink()
```
Notas:
- `uid` se define antes del bucle y se reutiliza en el filtro (línea `:437` del original).
- `owner.get(a.res_id)` es `False` si la sesión no tiene `user_id` (usuario borrado, `ondelete='set
  null'`): entonces solo se borran los adjuntos sin `create_uid` y el resto se desengancha.
- El desenganche y el borrado siguen dentro del `try/except` existente (`:1326-1337`): un fallo solo
  deja el aviso actual y no impide borrar la sesión.
- No se cambia el docstring de `unlink` ni el tratamiento de los jobs ni el `lock_timeout` (parche 6
  no toca este archivo).

`pns_ai_chatboo/models/chatboo_async_request.py`
```diff
@@ -1586 @@
-                    self.session_id.claim_turn_file_chips([chip])
+                    # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
+                    self.session_id._claim_turn_file_chips([chip])
@@ -1702 @@
-            _staged = session.consume_staged_assistant_download_chips()
+            # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
+            _staged = session._consume_staged_assistant_download_chips()
@@ -1738 @@
-                session.claim_turn_file_chips(_assistant_files)
+                # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
+                session._claim_turn_file_chips(_assistant_files)
```
(Las líneas del parche 6, `:697-698`, `:714-715` y `:839-866`, no se tocan.)

`pns_ai_mcp/controllers/validators.py` (`RELAXAICODE_SIDE_EFFECT_METHODS`, tras `:202`)
```diff
     # Seges: parche 10 (PNS-83, seguridad). Ver docs/pendiente/parches_pns_ai.md
     '_redeem_key_pin', '_release_all', '_note_failure', '_is_blocked',
+    # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    '_claim_turn_file_chips', '_apply_assistant_download_chips',
+    '_stage_assistant_download_chips', '_consume_staged_assistant_download_chips',
 })
```

#### Parche 12 — PNS-01/02 (`pns_ai_mcp/models/ai_system_action.py`)

```diff
@@ -706,3 @@
         return ''
 
+    # Seges: parche 12 (PNS-01/02, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    def _check_may_change_user_groups(self):
+        """Native groups are Settings business: AI Administrator alone is not
+        enough. Checked on the real user before any sudo(), like stdio servers."""
+        user = self.env.user
+        if user._is_superuser() or user.has_group('base.group_system'):
+            return
+        raise UserError(_(
+            'Only a Settings administrator can add or remove user groups.'
+        ))
+
     @api.model
@@ -709,2 @@
     def _preview_user_add_group(self, user_id=None, group=None, **_kw):
+        # Seges: parche 12 (PNS-01/02, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        self._check_may_change_user_groups()
         user = self._resolve_user(user_id)
@@ -718,2 @@
     def _apply_user_add_group(self, user_id=None, group=None, **_kw):
+        # Seges: parche 12 (PNS-01/02, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        self._check_may_change_user_groups()
         user = self._resolve_user(user_id)
@@ -738,2 @@
     def _preview_user_remove_group(self, user_id=None, group=None, **_kw):
+        # Seges: parche 12 (PNS-01/02, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        self._check_may_change_user_groups()
         user = self._resolve_user(user_id)
@@ -748,2 @@
     def _apply_user_remove_group(self, user_id=None, group=None, **_kw):
+        # Seges: parche 12 (PNS-01/02, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        self._check_may_change_user_groups()
         user = self._resolve_user(user_id)
```
`UserError` y `_` ya están importados (`:12-13`). No se tocan `data/trusted_actions_system.xml`,
`models/ai_trusted_action.py` ni `pns_base/utils/compat.py`.

#### Comprobaciones del programador (las repite el revisor)

```sh
# Ningún llamador con los nombres públicos antiguos (fuera de tests):
grep -rnE "(\.|def )(claim_turn_file_chips|apply_assistant_download_chips|stage_assistant_download_chips|consume_staged_assistant_download_chips)\b" \
  pns_base pns_ai_mcp pns_ai_chatboo --include=*.py --include=*.js --include=*.xml | grep -v "/tests/"
# Esperado: vacío.

grep -rn "_check_may_change_user_groups" pns_ai_mcp --include=*.py | grep -v "/tests/"
# Esperado: 5 líneas (def + 4 llamadas).

grep -rn "Seges: parche 1[12] (PNS-" pns_ai_mcp pns_ai_chatboo
# Esperado: 20 líneas = parche 11: 15 (chatboo_session.py 11, chatboo_async_request.py 3,
# validators.py 1) + parche 12: 5 (ai_system_action.py).
```
Tras E2, `grep -rn "Seges: parche [0-9]* (PNS-" pns_ai_mcp` pasa de 30 a 36 líneas, y en
`pns_ai_chatboo` da 14 (el parche 6 usa otro formato y no entra).

## 6. Vistas (XML ID heredado verificado | xpath | cambio)

**Sin cambios.** Verificado que ninguna vista, acción ni cron de los tres `pns_*` llama por nombre a
los métodos renombrados (§5.1.1). Los botones relacionados con B (`action_confirm_and_execute`,
`safe_operation.py:1711`) no cambian.

| XML ID heredado verificado | xpath | Cambio |
|---|---|---|
| — | — | Ninguno |

## 7. Seguridad (grupos, access CSV, record rules)

- **Grupos:** sin cambios. B exige `base.group_system` (core) además de `pns_ai_mcp.group_ai_admin`, en
  Python.
- **`ir.model.access.csv`:** sin cambios en los dos módulos. Referencias:
  - `chatboo.session`: `base.group_user` `1,1,1,1` (`pns_ai_chatboo/security/ir.model.access.csv:2`);
  - `chatboo.async.request`: `base.group_user` `1,1,1,0` (`:3`; resto de PNS-55, no se toca aquí);
  - `ai.trusted.action`: lectura interna (`pns_ai_mcp/security/ir.model.access.csv:4`) y CRUD de AI
    Administrator (`:73`, H-5);
  - `ai.system.action`: AI Administrator (`:74`).
- **Record rules:** sin cambios (`pns_ai_chatboo/security/security.xml:9-29`, por `user_id`).
- **Comprobación en Python:** es el contenido de los parches (filtro de dueño y creador antes del
  `sudo()` en A; `base.group_system` sobre el usuario real en B).

## 8. Datos (secuencias, crons, datos por defecto)

Sin secuencias, crons ni datos nuevos o modificados. `data/trusted_actions_system.xml` **no** cambia
(§5.4). El cron de Chatboo (`cron_maintenance`) sigue igual; su borrado de sesiones viejas pasa por el
`unlink` corregido (en `sudo`).

## 9. Tests previstos

Reglas comunes (las de E1, §9.1, y la línea base):
- Cabecera Apache-2.0 con «Copyright (C) 2026 Seges», **sin** línea `# -*- coding: utf-8 -*-` (nota de
  implementación de E1) y con el marcador de tests en la tercera línea.
- Etiquetas `@tagged('post_install', '-at_install', '<módulo>', 'seges_e2')`. Clases `HttpCase` o
  `TransactionCase` (llevan `standard`; no se repite PNS-50).
- **Sin** patrones desfasados de la línea base: ninguna skill con `code_body`; nada que dependa de
  `group_ai_conversational`, `/mcp`, `ai.provider` ni del agente `pns_ai_chatboo`; ningún
  `request_safe_plan` de `field_required` (cursor propio de `ai.safe.choice`); ningún
  `execute_plan_now`/`confirm_by_user` (hacen `commit` del cursor del test); ningún `unlink` como
  superusuario para probar protecciones (siempre `with_user`); no se escribe `create_date`; sin red.
- Python 3.7: sin walrus, sin `list[...]` evaluados, sin f-strings con `=`.
- Errores esperados por HTTP dentro de `mute_logger('odoo.http')`.

### 9.1 A) `pns_ai_chatboo/tests/` (carpeta nueva)

**`pns_ai_chatboo/tests/__init__.py`** (contenido propuesto):
```python
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 11 (tests de la entrega E2). Ver docs/pendiente/parches_pns_ai.md
from . import test_seges_chatboo_access
```

**`pns_ai_chatboo/tests/test_seges_chatboo_access.py`**, cabecera:
```python
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 11 (tests de la entrega E2). Ver docs/pendiente/parches_pns_ai.md
"""Parche 11 (PNS-82): los adjuntos del chat solo se enganchan a la sesión de su
creador; los métodos del flujo de chips dejan de ser públicos; el borrado de una
sesión no se lleva adjuntos ajenos."""
```
Importaciones previstas: `base64`, `json`, `os`, `re`; `odoo.fields`, `odoo.modules.module.get_module_path`,
`odoo.tests.HttpCase`, `TransactionCase`, `tagged`, `odoo.tests.common.new_test_user`,
`odoo.tools.mute_logger`; `odoo.addons.pns_ai_mcp.utils.session_download.persist_turn_file`;
`odoo.addons.pns_ai_mcp.controllers.validators.RELAXAICODE_SIDE_EFFECT_METHODS`;
`odoo.addons.pns_ai_mcp.controllers.context_builder.guarded_getattr`.

Constantes:
```python
RENAMED = (
    ('claim_turn_file_chips', '_claim_turn_file_chips'),
    ('apply_assistant_download_chips', '_apply_assistant_download_chips'),
    ('stage_assistant_download_chips', '_stage_assistant_download_chips'),
    ('consume_staged_assistant_download_chips', '_consume_staged_assistant_download_chips'),
)
BODY_A = b'seges-e2-a-body'
```

**`setUp` común** (mixin `_SegesChatbooData`, como superusuario `self.env`):
- **A:** `new_test_user(self.env, login='seges_e2_a', groups='base.group_user', password='seges_e2_a')`.
- **B:** ídem `seges_e2_b`. **P:** `seges_e2_portal`, `base.group_portal`.
- **Sesiones:** `cs_a = env['chatboo.session'].with_user(A).create({'name': 'Seges E2 A'})`; ídem `cs_b`.
- **Adjuntos de A:**
  - `att_a`: descarga huérfana creada **como A** (`env['ir.attachment'].with_user(A).create({'name':
    'seges-e2-a.xlsx', 'datas': base64.b64encode(BODY_A), 'mimetype': 'application/octet-stream'})`):
    `create_uid = A`, sin `res_model`;
  - `att_a_rm0`: huérfano de A con `res_model='res.partner'`, `res_id=0` (la combinación de
    `write_export_attachment`);
  - `att_cfg`: copia de configuración simulada, creada por un usuario `seges_e2_admin`
    (`base.group_user,base.group_system,pns_ai_mcp.group_ai_admin`) con
    `pns_base.utils.portable_io.write_json_attachment(env_admin, 'seges-e2-config.json', {'k': 'secret'})`
    (huérfano con `EXPORT_MARK`).
- Utilidades `_rpc(login, model, method, args, kwargs=None)` y `_assert_refused(res, private)` iguales
  que en E1 (`pns_ai_mcp/tests/test_seges_rpc_access.py:103-126`); `_get(login, url)` =
  `authenticate` + `url_open(url)`; `_atts()` = `flush` + `SELECT id, res_model, res_id, create_uid FROM
  ir_attachment WHERE id IN %s ORDER BY id` con los ids de prueba.

#### Clase 1 — `TestSegesChatbooRpc(_SegesChatbooData, HttpCase)`: negativos por JSON-RPC real

| Test | Llamadas | Esperado |
|---|---|---|
| `test_control_session_ok` | B y P: `res.users.context_get` | Responde (`result`): la sesión y la ruta funcionan |
| `test_claim_refused_rpc` | B y P: `chatboo.session.claim_turn_file_chips([cs_b.id], [{'attachment_id': att_a.id}])`, la variante con `{'url': '/pns_ai_mcp/session_file/%d/x.xlsx' % att_a.id}` y con `/web/content/%d`; las mismas con `_claim_turn_file_chips`; las mismas sobre `[cs_a.id]` y con `att_a_rm0` y `att_cfg` | Público → `builtins.AttributeError`; privado → `odoo.exceptions.AccessError`. `_atts()` idéntico antes y después |
| `test_flow_methods_refused_rpc` | B y P: `apply_assistant_download_chips`, `stage_assistant_download_chips` (con los mismos chips) y `consume_staged_assistant_download_chips` sobre `[cs_b.id]`, públicos y privados | Rechazadas igual. `staged_assistant_files` de `cs_b` sin cambios; `_atts()` idéntico |
| `test_foreign_download_denied` | B: `GET /pns_ai_mcp/session_file/<att_a>`, `GET /web/content/<att_a>`; ídem `att_cfg`. Control A: `GET /pns_ai_mcp/session_file/<att_a>` | B: `404` en `session_file` y distinto de `200` en `/web/content` (403), sin `BODY_A` en el cuerpo. A: `200` y cuerpo `BODY_A` |
| `test_staged_buffer_does_not_hijack` (H-2, por RPC real) | B por RPC: `write([cs_b.id], {'staged_assistant_files': json.dumps([{'attachment_id': att_a.id}, {'url': '/pns_ai_mcp/session_file/%d' % att_cfg.id}])})` → `True`; `chatboo.async.request.create({'session_id': cs_b.id, 'prompt': 'seges e2'})`; `request_cancel([job_id])` → `True` | `_atts()`: `att_a` y `att_cfg` sin `res_model`/`res_id`. B: `GET /pns_ai_mcp/session_file/<att_a>` y `<att_cfg>` → 404. **Falla sin el parche** (hoy los engancha a `cs_b` y responde 200). Es la vía que el privado solo no cierra |
| `test_unlink_own_session_keeps_foreign` (R3) | Setup en `sudo`: simular un enganche anterior al parche (`att_a.sudo().write({'res_model': 'chatboo.session', 'res_id': cs_b.id})`) y un adjunto propio de B colgado de su sesión (`env['ir.attachment'].with_user(B).create({..., 'res_model': 'chatboo.session', 'res_id': cs_b.id})`). B por RPC: `chatboo.session.unlink([cs_b.id])` | El de B, borrado. `att_a` existe, `res_model` vacío, `res_id` 0/vacío, `create_uid = A`. A: `GET /pns_ai_mcp/session_file/<att_a>` → 200; B → 404. **Falla sin el parche** (hoy borra `att_a`) |
| `test_unlink_foreign_session_refused` | Imagen de A colgada de `cs_a` (creada como A). B por RPC: `unlink([cs_a.id])` | `AccessError`; `cs_a` y su adjunto siguen. Documenta la comprobación previa al `sudo` (hoy también pasa, por el rollback) |

#### Clase 2 — `TestSegesChatbooFlows(_SegesChatbooData, HttpCase)`: positivos (R2)

`HttpCase` a propósito: en modo de pruebas `registry.cursor()` devuelve el cursor de pruebas, así que
`persist_turn_file` (`_run_on_committed_cursor`, cursor propio con commit) trabaja en la transacción del
test y ve los usuarios creados en él.

| Test | Qué hace | Esperado |
|---|---|---|
| `test_own_download_claimed_and_served` | `chip = persist_turn_file(env_a, cs_a.id, b'seges-e2-own', 'seges-e2.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')` con `env_a = self.env(user=A)`; `cs_a.with_user(A)._claim_turn_file_chips([chip])` | Adjunto con `create_uid = A`, `res_model = 'chatboo.session'`, `res_id = cs_a.id`. A: `GET chip['url']` → 200 y cuerpo; `GET /web/content/<id>` → 200. B: los dos ≠ 200 |
| `test_claim_filters_in_python` | (a) `cs_b.with_user(B)._claim_turn_file_chips([{'attachment_id': att_a.id}])`; (b) lo mismo con `.sudo()` (`cs_b.with_user(B).sudo()`); (c) `env['chatboo.session'].with_user(B).browse(cs_a.id)._claim_turn_file_chips([<adjunto huérfano de B>])`; (d) control: `cs_a.with_user(A)._claim_turn_file_chips([{'attachment_id': att_a.id}, {'url': '/web/content/%d' % att_a_rm0.id}])` | (a), (b) y (c): nada cambia (el `sudo` no levanta el filtro; no se engancha a una sesión ajena). (d): los dos de A quedan en `cs_a` |
| `test_fulfill_client_export_claims_own` | `cs_a.with_user(A).fulfill_client_export('seges-e2.pdf', 'application/pdf', base64.b64encode(b'%PDF-1.4 seges'), kind='pdf')`; después `cs_a.with_user(A)._consume_staged_assistant_download_chips()` | Devuelve el chip; adjunto colgado de `cs_a` con `create_uid = A`; el consumo devuelve ese chip y deja `staged_assistant_files` vacío. Cubre `chatboo_session.py:491`, `:517`, `:413`, `:362` y el consumo |
| `test_save_to_session_claims_only_own` | `job = env['chatboo.async.request'].with_user(A).create({'session_id': cs_a.id, 'prompt': 'seges e2', 'files': json.dumps([{'name': 'seges-e2.csv', 'mimetype': 'text/csv', 'data': 'data:text/csv;base64,' + base64.b64encode(b'a;b').decode()}])})`; `chip_own = persist_turn_file(env_a, …)`; `job._save_to_session('ok', {'assistant_files': [chip_own, {'attachment_id': att_cfg.id, 'url': '/pns_ai_mcp/session_file/%d' % att_cfg.id}]}, error=None)` | El CSV del clip (`:1586`) y `chip_own` (`:1738`) quedan en `cs_a`; `att_cfg` sigue huérfano. El último mensaje del asistente lleva los chips en `files`. Camino real del worker, sin LLM |
| `test_cron_unlink_sudo_keeps_foreign` | Sesiones `cs_a` y `cs_b`, cada una con un adjunto propio colgado (creado por su dueño); a `cs_b` se le cuelga además en `sudo` `att_cfg` (creador distinto). `(cs_a + cs_b).sudo().unlink()` en una sola llamada, como `_cleanup_old_sessions` | Los dos propios, borrados. `att_cfg` sigue existiendo, con `res_model` y `res_id` vacíos y `create_uid` intacto |
| `test_public_names_gone` | `hasattr(type(env['chatboo.session']), nombre)` para los 4 antiguos y los 4 nuevos | Antiguos `False`, nuevos `True` |
| `test_no_caller_uses_public_names` | Recorre los `.py`, `.js` y `.xml` de `pns_ai_chatboo` y `pns_ai_mcp` (sin `tests/`; `get_module_path`) con la expresión del §5.5 | Ninguna coincidencia. Guarda contra un llamador olvidado |

#### Clase 3 — `TestSegesChatbooSandbox(TransactionCase)`

| Test | Esperado |
|---|---|
| `test_names_in_denylist` | Los 4 nombres nuevos están en `RELAXAICODE_SIDE_EFFECT_METHODS` y `guarded_getattr(object(), nombre)` lanza `AttributeError` |

Total previsto: **15 tests** en `pns_ai_chatboo` (línea base: 0).

### 9.2 B) `pns_ai_mcp/tests/test_seges_user_groups.py` (archivo nuevo; D-8)

Registro en `pns_ai_mcp/tests/__init__.py` (al final):
```diff
 # Seges: parches 7 a 10 (tests de la entrega E1). Ver docs/pendiente/parches_pns_ai.md
 from . import test_seges_rpc_access
+# Seges: parche 12 (tests de la entrega E2). Ver docs/pendiente/parches_pns_ai.md
+from . import test_seges_user_groups
```

Cabecera:
```python
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 12 (tests de la entrega E2). Ver docs/pendiente/parches_pns_ai.md
"""Parche 12 (PNS-01/02): dar o quitar grupos nativos con un plan exige
base.group_system además de AI Administrator, sobre el usuario real."""
```

**Clase `TestSegesUserGroupActions(TransactionCase)`**, `@tagged('post_install', '-at_install',
'pns_ai_mcp', 'seges_e2')`. `setUp` (superusuario):
- **ADM** (AI Administrator sin Ajustes): `groups='base.group_user,pns_ai_mcp.group_ai_admin'` (implica
  AI Writer, que exige cualquier `op=action`, `controller_helpers.py:102`).
- **SYS** (AI Administrator con Ajustes): `'base.group_user,base.group_system,pns_ai_mcp.group_ai_admin'`.
- **T** (objetivo): `'base.group_user'`. **TS** (objetivo administrador): `'base.group_user,base.group_system'`.
- `env_adm = api.Environment(self.cr, ADM.id, {})`, ídem `env_sys` (como `test_system_action.py:323`).
- `_step(code, user, group)` = `{'op': 'action', 'action_code': code, 'args': {'user_id': user.id, 'group': group}}`.

| Test | Qué hace | Esperado |
|---|---|---|
| `test_propose_rejected_without_settings` | `validate_safe_plan([_step('user.add_group', ADM, 'base.group_system')], env_adm)` y lo mismo con `user.remove_group` sobre TS | `(False, err)` con `'Only a Settings administrator'` en `err` |
| `test_confirmed_add_group_rejected_without_settings` | `execute_safe_plan(env_adm, [_step('user.add_group', ADM, 'base.group_system')])` (lo que ejecuta un plan confirmado por ADM, `safe_operation.py:1395`) | `UserError`; `ADM.has_group('base.group_system')` sigue `False` |
| `test_confirmed_remove_group_rejected_without_settings` | `execute_safe_plan(env_adm, [_step('user.remove_group', TS, 'base.group_system')])` | `UserError`; TS sigue con `base.group_system` |
| `test_registry_edit_does_not_lift_check` | ADM (tiene CRUD, H-5) vacía los grupos de la acción: `env_adm['ai.trusted.action']._get('user.add_group').write({'group_ids': [(5, 0, 0)]})`; después `._apply(user_id=ADM.id, group='base.group_system')` | `UserError`: la comprobación no depende del registro (ni de `-u`) |
| `test_direct_methods_rejected_without_settings` | `env_adm['ai.system.action']._preview_user_add_group(...)`, `_apply_user_add_group(...)`, `_preview_user_remove_group(...)`, `_apply_user_remove_group(...)`; y lo mismo con `env_adm['ai.system.action'].sudo()` | `UserError` en los ocho (en `sudo` también: se comprueba el usuario real) |
| `test_settings_admin_adds_and_removes` (positivo) | `validate_safe_plan([...add T base.group_system...], env_sys)` → `ok`; `execute_safe_plan(env_sys, [add])`; después `execute_safe_plan(env_sys, [remove])` | `ok is True`; T gana y después pierde `base.group_system`; los dos devuelven una fila `{'op': 'action', 'result': {'ok': True, …}}` |
| `test_view_actions_unchanged_for_ai_admin` (no regresión de R5) | Vista de formulario de `res.partner` con `comment` (creada como en `test_system_action.py:21-33`); `env_adm['ai.trusted.action']._get('view.set_field_readonly')._apply(model='res.partner', field='comment', readonly=True, view_ids=[view.id])` | `result['ok']` y una vista heredada nueva: ADM sin Ajustes sigue usando `view.*` |

Total previsto: **7 tests**. Los tests negativos **fallan sin el parche 12** (hoy el plan da el grupo).
Si `execute_safe_plan` del positivo tropezara con algo ambiental del diario de cambios
(`_record_change_journal`, mismo cursor), el programador lo sustituye por `trusted._apply` con `env_sys`
y lo anota en «Notas de implementación».

#### Criterio de aceptación local

- `odoo-dev 14 tests pns_ai_mcp` (contexto `lab_pns_ai`): **205 tests**, los 7 nuevos en verde y el
  resto igual que tras E1: 148 + 7 = 155 pasados, 5 saltados, 14 fallidos y 31 errores, **con los
  mismos nombres**. En particular, siguen igual `test_system_action.test_user_group_preview`
  (superusuario) y `test_internal_user_cannot_reach_system_action_through_trusted_action`.
- `odoo-dev 14 tests pns_ai_chatboo`: **15 tests**, todos en verde (línea base 0).
- `python3 ~/.claude/hooks/odoo_lint.py --revisar --base 14.0-pns-ai-3`: sin incidencias nuevas. No
  se corrigen avisos previos del fabricante.
- `py_compile` con Python 3.7.3 (imagen `odoo-dev:14-lab_pns_ai`) de los 4 archivos de producto y los 4
  de tests.
- Los `grep` del §5.5 con el resultado esperado.

### 9.2 bis Entradas en `docs/pendiente/parches_pns_ai.md` (las escribe el programador)

Una por parche, con el formato de los parches 7 a 10 (fecha, estado, PNS, «Qué falla sin él»,
«Cambio», «Qué se degrada», «Cómo comprobar si el fabricante ya lo ha corregido» y «Comprobaciones
realizadas»). Texto propuesto para el **índice** (filas nuevas tras la 10):

```markdown
| 11 | PNS-82 | seguridad | `pns_ai_chatboo/models/chatboo_session.py`, `pns_ai_chatboo/models/chatboo_async_request.py`, `pns_ai_mcp/controllers/validators.py` | E2 | (ver `git log`) | Pendiente |
| 12 | PNS-01, PNS-02 | seguridad | `pns_ai_mcp/models/ai_system_action.py` | E2 | (ver `git log`) | Pendiente |
```

Texto propuesto para la fila E2 del [plan](../pendiente/plan_correccion_pns_ai.md), columna «Estado»:
`Spec en revisión (docs/specs/correcciones_pns_ai_entrega2.md)`; tras validar: `Hecha: validada en
staging el <fecha> (commit <hash>)`. En el seguimiento, columna «Rama Seges» de PNS-82, PNS-01 y
PNS-02: `CORREGIDO con el parche 11 (E2)` / `CORREGIDO con el parche 12 (E2)` cuando se valide.

### 9.3 Plan de prueba en staging (`pns_demo`)

**Supuesto** (el encargo se corta en este punto): se sigue el modelo de E1 (§9.3 y «Ajustes en la
ejecución del staging»). La no regresión con Gemini incluye, además de las descargas y el borrado de
una sesión propia, un plan de grupos confirmado por un usuario con AI Administrator y
`base.group_system` (debe funcionar) y el mismo intento por un AI Administrator sin `base.group_system`
(debe rechazarse); más la limpieza y el registro de resultados. Se añaden pruebas por script sin LLM
para la vía del búfer (H-2) y el borrado en cascada.

**Despliegue** (plan de staging, §2.2, punto 4, como E1):
1. `git archive` del commit de Sergio. Huella SHA-256 en el equipo y en el VPS, y `diff -rq` con el
   despliegue anterior (`2bb4f51`): solo deben aparecer `pns_ai_chatboo/models/chatboo_session.py`,
   `pns_ai_chatboo/models/chatboo_async_request.py`, `pns_ai_chatboo/tests/` (2 archivos nuevos),
   `pns_ai_mcp/controllers/validators.py`, `pns_ai_mcp/models/ai_system_action.py`,
   `pns_ai_mcp/tests/__init__.py` y `pns_ai_mcp/tests/test_seges_user_groups.py`. Marcadores: 20 líneas
   `Seges: parche 1[12] (PNS-`.
2. Copia previa en `/opt/odoo/pns_staging/addons_antes_E2`. `rsync` y reinicio de `odoo14_pns`. **Sin
   `-u`** (no hay campos, vistas ni datos).
3. Log del arranque sin tracebacks.

**Auditoría previa (solo lectura)** — enganches anteriores al parche:
```sql
SELECT a.id, a.name, a.create_uid, s.user_id, a.res_id
  FROM ir_attachment a
  JOIN chatboo_session s ON a.res_model = 'chatboo.session' AND a.res_id = s.id
 WHERE a.create_uid IS DISTINCT FROM s.user_id;
```
Esperado: 0 filas (si hay alguna, se anota y no se toca; el `unlink` corregido la desengancharía). La
misma consulta se propone para LIYBEN antes del despliegue final.

**Preparación** (por RPC como `admin`, con `preparar_e2.py`, solo biblioteca estándar; contraseñas
con `getpass`, no se guardan ni se anotan; autorización de Sergio para crear y borrar usuarios, D-9):
- **A2** (`e2_interno_a`): interno sin IA; crea por RPC un huérfano `ir.attachment` (`e2-a2.txt`) →
  id **X**.
- **B** (`e2_interno_b`): interno sin IA. Crea por RPC su `chatboo.session` → **CS_B**.
- **P** (`e2_portal`): portal temporal (como D-5 de E1).
- **E2ADM** (`e2_aiadmin`): interno + `group_ai_admin` + `group_ai_conversational`, **sin**
  `base.group_system`, con clave MCP (la genera `admin` en la interfaz; se usa y no se anota).
- **T** (`e2_objetivo`): interno + `base.group_partner_manager` (grupo inocuo para las pruebas de
  quitar y poner).
- **admin:** temporalmente `group_ai_conversational` y clave MCP (como en E1, R2), para proponer planes
  por `/mcp` y por el chat.
- **Y:** `admin` exporta una copia de configuración **sin secretos** desde Ajustes (huérfano con
  `EXPORT_MARK`, `create_uid = admin`). Id por `SELECT`.
- **Línea base con `SELECT`:** `id, res_model, res_id, create_uid` de X e Y;
  `res_groups_users_rel` de E2ADM y T; `count(*)` de `ai_safe_operation`.

**Pruebas de seguridad por script** (`pruebas_e2_rpc.py` y `pruebas_e2_mcp.py`):

| # | Prueba | Quién | Llamadas | Resultado esperado |
|---|---|---|---|---|
| 1 | **PNS-82, RPC directo** (3b-1) | B y P | `chatboo.session.claim_turn_file_chips([CS_B], [{'attachment_id': X}])` y `[{'url': '/pns_ai_mcp/session_file/<Y>'}]`; `_claim_turn_file_chips`; `apply_`/`stage_`/`consume_` (públicos y privados) | Público → `AttributeError`; privado → `AccessError`. X e Y sin cambios. **CORREGIDO** |
| 2 | **PNS-82, búfer + `request_cancel`** (H-2) | B | `write([CS_B], {'staged_assistant_files': '[{"attachment_id": X}, {"attachment_id": Y}]'})`; `chatboo.async.request.create({'session_id': CS_B, 'prompt': 'e2'})`; `request_cancel([job])` | `True` en las tres; X e Y siguen huérfanos. **CORREGIDO** |
| 3 | **PNS-82, descarga** | B | `GET /pns_ai_mcp/session_file/<X>` y `<Y>`; `GET /web/content/<X>` y `<Y>` | 404 / 403 (nunca 200). Control: A2 `GET /pns_ai_mcp/session_file/<X>` → 200 |
| 4 | **Borrado en cascada** (R3) | admin y B | `admin` simula un enganche anterior: `ir.attachment.write([X], {'res_model': 'chatboo.session', 'res_id': CS_B})`. B crea un adjunto propio colgado de CS_B (**Z**) y borra CS_B: `chatboo.session.unlink([CS_B])` | Z borrado. X existe, `res_model` vacío, `create_uid = A2`. A2 descarga X (200); B no (404) |
| 5 | **Sesión ajena** | B | `chatboo.session.unlink([<sesión de U1>])` | `AccessError`; la sesión y sus adjuntos siguen (`SELECT`) |
| 6 | **PNS-01, propuesta** | E2ADM, por `/mcp` | `tools/call` `safe_plan_request` con `[{'op': 'action', 'action_code': 'user.add_group', 'args': {'user_id': <E2ADM>, 'group': 'base.group_system'}}]` | `success: false`, error «Step 1: Only a Settings administrator can add or remove user groups.». Sin fila nueva en `ai_safe_operation`; E2ADM sin `base.group_system`. **CORREGIDO** |
| 7 | **PNS-01, plan confirmado** | `admin` propone, E2ADM confirma | `admin` por `/mcp`: el mismo plan para E2ADM → `verification_id` pendiente. E2ADM por RPC: `ai.safe.operation.action_confirm_and_execute([<op>])` (puede resolver las de otros, `_can_resolve`) | Error con el mensaje nuevo; la operación no queda `executed` (cancelada); E2ADM sin `base.group_system`. **CORREGIDO** (la comprobación está en la ejecución, sobre quien confirma) |
| 8 | **PNS-02, quitar** | E2ADM | Como 6, con `user.remove_group` de T y `base.group_partner_manager`; y como 7 (lo propone `admin`, confirma E2ADM) | Rechazado en los dos; T conserva el grupo. **CORREGIDO** |
| 9 | **`view.*` sin cambios** (R5) | E2ADM, por `/mcp` | `safe_plan_request` con `view.set_field_readonly` sobre un campo de una vista de formulario de `res.partner`; después cancelarla (`action_cancel` por RPC) | Se crea la tarjeta pendiente (la propuesta pasa); cancelada sin aplicar |
| — | Control | B y P | `res.users.context_get` | Responde |

**No regresión con Gemini:**

| # | Caso | Quién | Pasos | Resultado esperado |
|---|---|---|---|---|
| R1 | Descarga Excel del motor (`:1738`) | U1 | Turno: «Exporta a Excel los 5 primeros contactos» | Chip en la respuesta; descarga 200 con el contenido. `SELECT`: el adjunto tiene `create_uid = U1`, `res_model = 'chatboo.session'` y `res_id` = sesión de U1 |
| R2 | PDF montado en el navegador (`fulfill_export`, `:491`/`:517`) | U1 | «Ahora en PDF» (o el botón de exportar a PDF del chat) | El chip pendiente se sustituye; descarga 200; mismo `SELECT` |
| R3 | Fichero adjuntado con el clip (`:1586`) | U1 | Adjuntar un CSV pequeño y preguntar por él | Chip clicable en la burbuja del usuario; descarga 200 |
| R4 | Recarga | U1 | F5 / History → abrir la sesión | Los chips de R1-R3 siguen y descargan |
| R5 | Borrar una sesión propia | U1 | History → borrar la sesión de R1-R4 | Sin error; `SELECT count(*) FROM ir_attachment WHERE res_model = 'chatboo.session' AND res_id = <sesión>` → 0 |
| R6 | Plan de grupos con Ajustes | `admin` (AI Administrator + `base.group_system`) | En el chat: «Quita al usuario e2_objetivo el grupo Crear contactos» → Confirmar; después «Añádeselo de nuevo» → Confirmar | Los dos se aplican; `res_groups_users_rel` de T sin y con el grupo |
| R7 | Plan de grupos sin Ajustes | E2ADM | En el chat: «Añádeme el grupo Ajustes» | Sin tarjeta; el chat informa del rechazo («Only a Settings administrator…»). E2ADM sin `base.group_system` |
| R8 | Log | — | `grep -E "claim_turn_file_chips\|download_chips\|AttributeError\|Only a Settings administrator\|no se pudieron borrar los adjuntos"` sobre el log del intervalo | Solo los rechazos provocados en 1-8 y R7 |

**Limpieza** (`preparar_e2.py --limpiar` y la interfaz):
- borrar A2, B, P, E2ADM y T, con sus sesiones, jobs y adjuntos (X, Z); borrar Y (o dejar que lo purgue
  la retención de 24 h);
- retirar a `admin` `group_ai_conversational` y revocar su clave MCP; revocar la de E2ADM (se borra con
  el usuario);
- borrar las operaciones de prueba de `ai_safe_operation` (las de 6-9 y R6-R7) y comprobar con `SELECT`
  contra la línea base;
- borrar en la interfaz las sesiones de U1 que queden de las pruebas.

Resultado en la verificación: apartado nuevo «Staging — entrega E2», con la misma estructura que el
de E1. Si la ejecución obliga a desviarse, se añade aquí un apartado «Ajustes en la ejecución del
staging».

**LIYBEN:** no se despliega al cerrar E2 (decisión del 20/10/2026): recibe todas las correcciones al
terminar el plan, **sin `-u`**. Antes, la auditoría de solo lectura de este apartado.

## 10. Riesgos y preguntas abiertas

### 10.1 Qué se degrada (por parche)

- **Parche 11:**
  - Un adjunto creado por un usuario distinto del dueño de la sesión ya no se engancha a ella. En los
    flujos actuales no pasa: el worker, la ruta y el motor crean con el uid del dueño. Los binarios de
    un plan que confirma otro usuario fuera del turno ya no se enganchaban (no-op de
    `merge_download_chips_into_session`).
  - Al borrar una sesión, los adjuntos ajenos (enganchados antes del parche) se desenganchan en vez
    de borrarse: quedan en el filestore como huérfanos de su creador. Las descargas del chat no llevan
    `EXPORT_MARK` y no las purga nadie (observación ya registrada en PNS-21).
  - Sesiones sin `user_id` (usuario borrado) que borre el cron: los adjuntos con `create_uid` se
    desenganchan en lugar de borrarse (blobs que quedan; caso raro).
  - Clientes externos que llamen por RPC a los cuatro métodos: no se conoce ninguno (D-6 de E1: sin
    peticiones a `/xmlrpc` ni `/jsonrpc` en LIYBEN).
  - En el sandbox, cuatro nombres más en la lista negra (son nombres propios de Chatboo, sin colisión).
- **Parche 12:**
  - Un AI Administrator sin Ajustes ya no puede dar ni quitar **ningún** grupo por un plan, tampoco los
    de IA (AI Writer, etc.). Para los grupos de IA tiene los indicadores de `ai.mcp.user`
    (`mcp_user.py:230-318`), que no cambian.
  - En LIYBEN no cambia nada: los dos AI Administrators ya tienen `base.group_system` (D4).
  - Mensaje nuevo en inglés sin traducir.
  - El prompt sigue diciendo «Authorization is the Confirm toast plus AI Administrator»
    (`system_prompt.xml:144`): el LLM propondrá el plan a un AI Administrator sin Ajustes y recibirá el
    rechazo al proponer (D-7).

### 10.2 Riesgos de regresión

| Riesgo | Efecto | Mitigación |
|---|---|---|
| Un llamador sin actualizar (`chatboo_session.py:362/406/413/491/517`, `chatboo_async_request.py:1586/1702/1738`) | `AttributeError`. En `:1586` y `:1738` está dentro de `_save_to_session`, que `_finalize` envuelve en `try/except` (`:923-948`): **el turno se guardaría sin la respuesta en la sesión**, con solo un `exception` en el log. En `fulfill_client_export` falla la exportación a PDF/Word | `test_no_caller_uses_public_names`, `test_fulfill_client_export_claims_own`, `test_save_to_session_claims_only_own`; `grep` del §5.5; R1-R3 |
| El filtro de `create_uid` deja fuera un origen legítimo no detectado (un adjunto del turno creado con otro uid) | El chip se ve pero la descarga da 404 al dueño | Inventario §5.1.2; R1-R4 cubren los cuatro orígenes con `claim`; R8 |
| `check_access_rule('unlink')` al principio de `unlink` | Si alguien borra sesiones fuera de `sudo` y sin permiso, falla antes (antes fallaba en `super().unlink()` igualmente) | Sin cambio de comportamiento para el dueño ni para el cron (`sudo`); `test_unlink_*`; R5 |
| Desenganche de adjuntos en `unlink` falla | Se registra el aviso existente y la sesión se borra; el adjunto queda colgando (como hoy si falla el borrado) | Dentro del `try/except` original |
| El `UserError` del preview afecta a otras pantallas | `describe_safe_plan` lo captura (`safe_plan.py:677-680`) y solo se llama al proponer | Test `test_propose_rejected_without_settings`; prueba 6 y R7 |
| Superusuario o cron | Pasan por `_is_superuser()` / `user_root` en `base.group_system` | `test_user_group_preview` del fabricante sigue en verde |
| Commit por parche | `validators.py` (pns_ai_mcp) va en el parche 11 junto a Chatboo | Un solo bloque; selección de líneas en GitHub Desktop, como D-7 de E1 |

### 10.3 Cómo comprobar si el fabricante ya lo ha corregido (vigilancia, N12)

En la carpeta de la versión nueva, fuera del repo. Prueba definitiva: pasar
`pns_ai_chatboo/tests/test_seges_chatboo_access.py` y `pns_ai_mcp/tests/test_seges_user_groups.py`
contra esa versión (adaptando los nombres si los renombra): si los negativos pasan sin los parches de
Seges, está corregido.

- **Parche 11 (PNS-82):**
  ```sh
  grep -nE "def _?(claim_turn_file_chips|apply_assistant_download_chips|stage_assistant_download_chips|consume_staged_assistant_download_chips)\b" pns_ai_chatboo/models/chatboo_session.py
  grep -n "create_uid\|check_access_rule" pns_ai_chatboo/models/chatboo_session.py
  ```
  Corregido si `claim` (público o privado) compara el `create_uid` del adjunto con el usuario real y
  comprueba que la sesión es suya **antes** de escribir en `sudo` (o escribe sin `sudo`, dejando que
  `ir.attachment.check` lo impida), **y** el `unlink` no borra en `sudo` adjuntos de otros creadores.
  **No basta** con que los métodos sean privados: queda la vía del búfer y `request_cancel` (H-2).
- **Parche 12 (PNS-01/02):**
  ```sh
  grep -nE "group_system|_is_system|is_system\(\)" pns_ai_mcp/models/ai_system_action.py pns_ai_mcp/models/ai_trusted_action.py
  grep -n "group_system" pns_ai_mcp/data/trusted_actions_system.xml
  ```
  Corregido si `_apply_user_add_group`/`_apply_user_remove_group` (o `_resolve_user`) comprueban
  `base.group_system` sobre `self.env.user` antes del `sudo()`. **No vale:** añadir `base.group_system`
  a `group_ids` en el XML (significa «al menos uno» y el AI Administrator puede editar el registro), ni
  `self.env.is_system()` (es `True` en `sudo`).

### 10.4 Dudas y decisiones para Sergio

- **D-1 — Privatizar también `stage_` y `consume_`:**
  - **Recomendado: sí.** Mismo flujo, solo llamadores Python del módulo; dos renombrados y dos
    llamadores más. Cierra su uso por RPC (hoy `consume_` lee con SQL el búfer de cualquier sesión
    antes de fallar la escritura).
  - **Alternativa:** solo `claim_` y `apply_` (los que cita el informe). El filtro protege igual.
- **D-2 — Borrado en cascada:**
  - **Recomendado:** comprobar acceso antes del `sudo` y desenganchar los ajenos (§5.1.4, punto 3).
  - **Alternativas:** a) dejar los ajenos colgando de la sesión borrada (el core los deja leer a
    cualquier interno, §2.1: peor); b) borrarlos igualmente (es el daño de PNS-82).
- **D-3 — Restos del mismo flujo fuera de PNS-82** (no se tocan en E2):
  - `recover_orphan_download_chips(messages=…)`: lista en `sudo` nombres y tamaños de adjuntos de una
    sesión ajena (resto de PNS-55, fuga menor);
  - `fulfill_client_export`: público; desde la caja A crea adjuntos con un cursor propio con commit;
  - `chatboo.async.request.cron_maintenance` (H-4): público, cualquier interno lo lanza por RPC
    (reclamación de jobs y purga de sesiones viejas en `sudo`, con commit). Efecto: adelantar la purga.
  - **Propuesta:** registrarlos como resto de PNS-55/PNS-07 y del patrón común, y llevarlos a E4 (los
    dos primeros y el tercero) y E3 (el segundo, por el sandbox).
- **D-4 — Hallazgo H-5: registro `ai.trusted.action` editable por AI Administrator.**
  - **Propuesta:** numerarlo como **PNS-97** (gravedad propuesta: Media; requiere AI Administrator),
    registrarlo en el seguimiento y decidir la entrega. Corrección posible, sin tocar el CSV: en
    `create`/`write`/`unlink` de `ai.trusted.action`, exigir `base.group_system` fuera de `sudo` (los
    datos XML se cargan como superusuario). Encaja en E4 o en una entrega «Después».
  - Mientras tanto, el parche 12 ya cubre el caso grave (grupos de usuario) porque la comprobación vive
    en el método.
- **D-5 — Comprobar también en el preview** (rechazo al proponer, sin tarjeta):
  - **Recomendado: sí** (mejor experiencia: no hay tarjeta que rebote; no revela nombres en `sudo`).
  - **Alternativa:** solo en el apply (la tarjeta se crea y falla al confirmar).
- **D-6 — Mensaje nuevo sin traducción:** «Only a Settings administrator can add or remove user
  groups.» saldrá en inglés porque no se toca `i18n` (N11). ¿Se acepta?
- **D-7 — Prompt del sistema:** `system_prompt.xml:144` y `safe_plan.py:1939-1940` siguen diciendo que
  basta AI Administrator. **Recomendado:** no tocarlos en E2 (cambio mínimo; el rechazo es claro) y
  anotarlo para la fase funcional.
- **D-8 — Ubicación del test de B:** **recomendado** archivo nuevo `test_seges_user_groups.py` (el de
  E1 lleva el marcador «parches 7 a 10» y su commit ya está hecho). **Alternativa:** clase nueva en
  `test_seges_rpc_access.py`, cambiando su cabecera.
- **D-9 — Usuarios temporales en `pns_demo`:** ¿se autoriza crear A2, B, P, E2ADM (AI Administrator
  **sin** Ajustes, con clave MCP) y T, y dar temporalmente a `admin` el grupo conversacional y una clave
  MCP? Todo se borra o revoca en la limpieza.
- **D-10 — Requisito `base.group_system` frente a `base.group_erp_manager`:** el core exige «Access
  Rights» (`group_erp_manager`) para cambiar grupos por la interfaz; el informe pide `base.group_system`
  (que lo implica). **Recomendado:** `base.group_system`, como el informe y PNS-09.
- **D-11 — Un parche para dos PNS:** el parche 12 cubre el resto común de PNS-01 y PNS-02 (misma
  causa, mismo archivo). La regla dice «un parche por PNS»; se propone una excepción documentada, con el
  marcador `(PNS-01/02, seguridad)`. Si se prefiere, se parte en 12 (add) y 12 bis (remove), con más
  ruido y sin ventaja.
- **Efecto en decisiones** (cuando E2 se valide en staging): D33 puede desbloquearse (queda D46); D8:
  se puede levantar la restricción «no exportar copias con secretos mientras siga PNS-82»; D4: para BD
  de clientes, AI Administrator deja de equivaler a administrador de Odoo en lo que respecta a grupos
  nativos (siguen PNS-84, PNS-86 y H-5).

## 11. Árbol de archivos (si es nuevo: con readme/, README.rst y static/description/)

Módulos existentes: no se crea `readme/`, `README.rst` ni `static/description/`.

```
pns_ai_chatboo/
├── models/
│   ├── chatboo_session.py            (parche 11: líneas 357, 362, 374, 401, 406, 413, 415-418,
│   │                                  436-437, 491, 517, 1294, 1331-1332)
│   └── chatboo_async_request.py      (parche 11: líneas 1586, 1702, 1738)
└── tests/                            (NUEVA)
    ├── __init__.py                   (NUEVO)
    └── test_seges_chatboo_access.py  (NUEVO, 15 tests)
pns_ai_mcp/
├── controllers/
│   └── validators.py                 (parche 11: RELAXAICODE_SIDE_EFFECT_METHODS)
├── models/
│   └── ai_system_action.py           (parche 12: método nuevo tras la línea 706; líneas 709, 718,
│                                      738, 748)
└── tests/
    ├── __init__.py                   (registro del test nuevo)
    └── test_seges_user_groups.py     (NUEVO, 7 tests)
docs/pendiente/parches_pns_ai.md      (entradas de los parches 11 y 12: programador)
```

Sin cambios en `__manifest__.py`, `security/`, vistas, datos (`data/trusted_actions_system.xml`
incluido), `i18n/`, `LICENSE`, `NOTICE`, `pns_base` ni en los parches 1 a 10.

## Notas de implementación

Fecha: 20/10/2026. Respuestas de Sergio a §10.4: D-1 sí; D-2 sí; D-3 no se tocan en E2; D-4 sin
cambios de código (H-5 será PNS-97, en E4); D-5 sí; D-6 se acepta el mensaje en inglés; D-7 no se toca
el prompt; D-8 archivo nuevo; D-9 sin código; D-10 `base.group_system`; D-11 un solo parche 12.

- **A1 (filtro de `_claim_turn_file_chips` y cron):** se repasaron todos los caminos que llegan a
  `_save_to_session` y a `_claim_turn_file_chips` con un uid distinto del dueño de la sesión.
  Ninguno existe, así que se aplica el filtro de la spec tal cual (`self.sudo().user_id.id != uid` y
  `att.create_uid.id != uid`, sin la excepción del superusuario):
  - `chatboo.async.request.cron_maintenance` → `_reclaim_stuck` llama a `_save_to_session(...,
    reclaim=True)` con el env del cron, pero con `reclaim=True` la función se salta todo el bloque
    `if not reclaim:` (`chatboo_async_request.py`), que es donde están `_persist_turn_files`,
    `_consume_staged_assistant_download_chips` y `_claim_turn_file_chips`. El resto del cron
    (`_gc_old`, `_gc_stale_query_data`, `_cleanup_old_sessions`) solo borra y no reclama adjuntos.
  - `_finalize` (también la rama `_record_crash`) y el hilo del worker reabren el entorno con el uid del
    job, y el `create` del job fija `user_id = env.uid` fuera de `sudo`.
  - `request_cancel` devuelve `False` si `self.user_id.id != self.env.uid`, así que un superusuario no
    puede cancelar el job de otro y llegar a `_save_to_session`.
  - No hay más llamadores de `_save_to_session`, `_persist_turn_files` ni `fulfill_client_export`
    en `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo`. No hace falta test de ese camino.
- **A2:** crear un `chatboo.async.request` no arranca el hilo ni llama a ningún proveedor: `create` solo
  inserta; el hilo se lanza en `_spawn()`, que llama el controlador (en modo de pruebas ejecutaría
  `_process()` en línea, pero ningún test lo invoca). No hizo falta `unittest.mock`.
- **A3:** no se han escrito scripts del staging.
- **Paso 1:** el grep de llamadores sobre todo `third_party` (`.py`, `.js`, `.xml`, `.csv`, `.json`) dio
  exactamente las 8 llamadas y las 4 definiciones del §5.1.1. Sin llamadores nuevos.
- **Positivo de `execute_safe_plan`:** `test_settings_admin_adds_and_removes` funciona con
  `execute_safe_plan(env_sys, ...)` sin necesidad de sustituirlo por `trusted._apply`.
- **Tests de chatboo, ajustes respecto al §9.1:**
  - `test_claim_refused_rpc` hace una llamada por usuario, sesión y nombre con una lista que contiene
    los nueve chips (3 adjuntos × 3 formatos) en lugar de una llamada por combinación, para limitar el
    número de peticiones HTTP; la cobertura es la misma. El mixin reutiliza la sesión HTTP mientras no
    cambie el usuario.
  - `test_claim_filters_in_python` usa para el caso (c) un huérfano propio de B (`att_b`, creado en el
    `setUp`).
  - Se ha comprobado a mano que, con los dos filtros de `_claim_turn_file_chips` y el de `unlink`
    neutralizados temporalmente, fallan 4 de los 14 tests iniciales; después se restauró el código.
  - Tras la revisión se añadió `test_cron_unlink_sudo_keeps_foreign` (borrado de dos sesiones a la vez
    en `sudo`, como el cron `_cleanup_old_sessions`): el total pasa de 14 a 15 tests, todos en verde.
  - Lint: f-strings en lugar de `%` y `# pylint: disable=too-many-instance-attributes` en el mixin de
    datos, porque son archivos nuevos y el hook cuenta como nuevas todas sus incidencias.
- **Entorno:** `odoo-dev 14 estado` indica `REPO=/home/soporte/GitHub/lab_pns_ai` con `third_party` como
  repo compartido (copia de trabajo `/home/soporte/GitHub/third_party`, rama `14.0-pns-ai-correcciones`);
  no hubo aviso de carpeta fuera del contexto.
