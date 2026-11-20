# Análisis pns_ai_chatboo (Odoo 14) — Bloque C1: servidor y skills de fábrica

Rama `14.0-analisis-pns-ai`. Copia analizada: `/home/soporte/GitHub/third_party/pns_ai_chatboo/`
(versión de manifest `2.1.322`). Código de terceros (PATANEGRA Soft): **no se modifica ni se
propone código**. Core de referencia: `/opt/odoo-src/14.0/`.

Convención: **HECHO** (archivo:línea), **INFERENCIA** (deducción razonada), **PENDIENTE**
(comprobar en laboratorio con `odoo-dev 14`). Rutas relativas a `pns_ai_chatboo/` salvo que se
indique otra cosa.

Documentos previos citados (no repetidos):
- [CONS] `docs/specs/analisis_pns_ai_mcp.md` (consolidado).
- [CONOC] `analisis_pns_ai_mcp_2_conocimiento.md`, [SECR] `_3_conexiones_secretos.md`,
  [CODE] `_6_ejecucion_codigo.md`, [LLM] `_7_motor_llm.md`, [BASE] `analisis_pns_base.md`.
- [VERIF] `docs/pendiente/verificacion_seguridad_pns_ai.md`.

---

## 1. Manifest, dependencias, hooks y assets

### 1.1 Manifest (`__manifest__.py`)
| Clave | Valor | Observación |
|---|---|---|
| `version` | `2.1.322` (:6) | HECHO. No sigue `14.0.x.y.z`; las carpetas `migrations/2.1.*` dependen de este esquema. |
| `license` | `'Other OSI approved licence'` (:22) con `LICENSE` Apache-2.0 | HECHO. |
| `depends` | `web, mail, bus, pns_base, pns_ai_mcp` (:26) | Ver 1.2. |
| `external_dependencies` | `python: ['openpyxl']` (:29-31) | Ver 1.3. |
| `data` | CSV → `ai_agent_data` → `chatboo_context_data` → `chatboo_skill_data` → `chatboo_icp_data` → `chatboo_async_cron` → vista de ajustes → assets → menús (:32-42) | HECHO. Orden correcto (seguridad, datos, vistas, menús). |
| `qweb` | `static/src/xml/chatboo_systray.xml` (:43-45) | HECHO (existe). Es del bloque cliente. |
| `application` | `True` (:47) | HECHO. |
| `uninstall_hook` | `uninstall_hook` (:49) | Ver 1.4. |

No hay carpeta `tests/` (HECHO: solo existen `i18n/ar.po` e `i18n/es.po` fuera del código).

### 1.2 Por qué depende de cada módulo
- **`pns_ai_mcp`** (HECHO, dependencia estructural; Chatboo es un cliente del motor):
  - Modelos heredados o usados: `ai.agent` (`models/ai_agent.py:21-22`), `ai.skill`
    (`models/ai_skill.py:13-14`), `pns_ai_mcp.skill.capture.wizard`
    (`models/skill_capture_wizard.py:8-9`), `ai.context` (`data/chatboo_context_data.xml:5`),
    `ai.mcp.user` (carnet, `utils/chatboo_access.py:15-21`), `ai.log`
    (`models/chatboo_session.py:207-215,722-728,751-756`), `ai.safe.operation` (`:810`),
    `ai.provider`, `ai.execution.engine` (`controllers/chatboo.py:619-627,708,941`),
    `pns_ai_mcp.relaxaicode_raw_result` (`controllers/chatboo.py:412`), `ai.fx.source`
    (`utils/fx_rates.py:19`).
  - Motor: `AgentEngine.run_stream` (`models/chatboo_async_request.py:483-505`;
    firma en `pns_ai_mcp/utils/agent_engine.py:1051`).
  - Utilidades: `session_download` (persistir adjuntos y URLs con token), `presentation_mode`,
    `formatting_mode_policy`, `history_compact`, `svg_download`, `mcp_correlation`,
    `artifact_export`, `display_currency`, `field_required_plan`, `skill_code_prefix`,
    `skill_live_code`, `user_time` (imports en `models/chatboo_async_request.py:360,401,
    1232,1278,1362,1383`, `models/chatboo_session.py:399,470,658,909`,
    `controllers/chatboo.py:301,531,684,916`, `utils/screen_context.py:169`,
    `utils/chatboo_display_time.py:64`).
  - Grupos: `pns_ai_mcp.group_ai_writer` (`models/chatboo_session.py:879`),
    `pns_ai_mcp.group_ai_admin` (`controllers/chatboo.py:74,407`).
  - Vista padre de ajustes `pns_ai_mcp.res_config_settings_view_form_mcp`
    (`views/res_config_settings_mcp_agents_views.xml:7`; verificada en
    `pns_ai_mcp/views/res_config_settings_views.xml:3`, botón objetivo en `:48`).
  - Hook de desinstalación `pns_ai_mcp.hooks.uninstall_factory_knowledge_for_module`
    (`hooks.py:21-24`).
- **`pns_base`**: solo `utils/compat.py:11-19` (reexporta `JSON_ROUTE_TYPE`, etc.). HECHO
  ([BASE] §10, línea 321).
- **`bus`**: notificaciones `bus.bus` (`models/chatboo_async_request.py:1867-1879`,
  `models/ai_skill.py:36-48`) y la skill `users-logged` (`bus.presence`). HECHO.
- **`web`**: assets backend (`views/assets.xml:4`). HECHO.
- **`mail`**: INFERENCIA: no se usa directamente en el Python del bloque (no hay `mail.thread`
  ni campos de `mail`); probablemente para el systray o JS (bloque cliente). PENDIENTE (C2).
  Ver además 11.2 (`SELF_READABLE_FIELDS`): `mail` es el que hace que el override funcione.

### 1.3 `external_dependencies` y librerías realmente usadas
| Librería | Declarada | Dónde se usa | Si falta |
|---|---|---|---|
| `openpyxl` | Sí (:29-31) | `models/chatboo_async_request.py:1009` (`_xlsx_to_text`, `:1001-1038`), llamado desde `_extract_file_text` `:1127-1144` al adjuntar `.xlsx/.xlsm` con el clip | Odoo **no instala** el módulo (HECHO, [CONS] §3.1). En ejecución el código degrada a `[Excel …: openpyxl no está instalado…]` (`:1010-1014,1135-1136`). |
| `xlrd` | No | `:1044` (`_xls_to_text`, `.xls` antiguos) | Degrada con mensaje (`:1149-1153`). INFERENCIA: Odoo 14 lo trae en sus requisitos; PENDIENTE versión en la imagen. |
| `PIL` (Pillow) | No (core) | `:907` (reescalado de imágenes previas) | Fallback sin reescalar (`:923-934`). |
| `ocr.service` (`pns_ocr`) | No (opcional) | `:1109-1124` (PDF) | Mensaje "OCR no instalado" (`:1110`). |

### 1.4 Hooks
- `uninstall_hook` (`hooks.py:17-28`): con `SUPERUSER_ID` llama a
  `uninstall_factory_knowledge_for_module(env, 'pns_ai_chatboo')` para borrar los contextos y
  skills de fábrica de este módulo (conserva los de usuario). Excepciones silenciadas con
  `warning`. HECHO.
- No hay `pre_init_hook` ni `post_init_hook`. La siembra se hace con `<function>` en `data/`
  (§9). HECHO.
- INFERENCIA: al desinstalar, Odoo borra las tablas `chatboo_session` y `chatboo_async_request`,
  pero los `ir.attachment` con `res_model='chatboo.session'` no tienen FK y el core no los
  borra: quedarían huérfanos con su `access_token` (descargables por URL, [CONS] riesgo 21).
  PENDIENTE.

### 1.5 Assets (`views/assets.xml:4-34`)
Plantilla heredada `web.assets_backend` (forma correcta en 14). Carga 3 CSS, el protocolo SSE,
librerías de terceros (showdown, jsPDF + autotable, html2canvas, SheetJS, Chart.js, ECharts; no
abiertas por regla) y los JS propios (`chatboo_component_v2.js`, `chatboo_systray.js`, …).
HECHO: todos los archivos referenciados existen. El análisis del JS es del bloque cliente (C2).

---

## 2. Modelos

### 2.1 `chatboo.session` (nuevo; `models/chatboo_session.py:34-1079`)
`_order = 'last_used_date desc, create_date desc'` (:38). Sin `company_id`.

| Campo | Tipo | Parámetros | Propósito (línea) |
|---|---|---|---|
| `name` | Char | required, default `"Session <fecha>"` | Nombre; se autorrenombra con el primer prompt (41-46; controlador 324-335) |
| `user_id` | M2o `res.users` | required, default usuario, `ondelete='cascade'`, index | Dueño (47-55) |
| `messages` | Text | — | JSON con TODO el historial visible (56-59) |
| `input_history` | Text | — | JSON de prompts (flechas ↑/↓), máx. 50 (60-63, 567) |
| `conversation_id` | Char | — | Id libre que manda el cliente (64-67) |
| `last_used_date` | Datetime | default now | Base de la retención (68-72) |
| `last_screen_context` | Text | — | Última pantalla bajo el overlay (73-76) |
| `last_query_code` | Text | — | Código relaxaicode de la última consulta; se reinyecta como pista (77-85) |
| `last_query_data` | Text | — | **Filas** del último dataset (cache Nivel 2) (86-95) |
| `last_query_data_date` | Datetime | — | Marca para TTL (96-100) |
| `active_skill_code` / `active_skill_params` | Char / Text | — | Skill "pegajosa" y sus parámetros (101-115) |
| `staged_assistant_files` | Text | — | Buffer temporal de chips de descarga (116-120) |
| `presentation_show_mode` | Char | default de ajustes | show-table / show-chart (121-136) |
| `llm_formatting_mode` | Selection | default False | Obsoleto, se conserva por esquema (137-147) |

Métodos (todos HECHO):
| Método | Líneas | Comportamiento |
|---|---|---|
| `format_display_datetime` (`@api.model`) | 149-153 | Hora "de pared" en tz de usuario/compañía (`utils/chatboo_display_time.py`). |
| `get_messages` / `get_messages_for_chat` | 157-176 | Deserializa; `_for_chat` completa `user_prompt` desde `ai.log` del **usuario actual** (`_annotate_turn_user_prompts` 195-239). |
| `_merge_attachment_chips` / `_merge_meta` | 260-331 | Evita que un `save` del cliente borre chips, métricas, `clip_data`, `backend_history`… (`_PRESERVED_ASSISTANT_KEYS` 243-258); limpia base64/HTML de burbujas de usuario. |
| `stage_/consume_/apply_assistant_download_chips` | 333-387 | Buffer de chips; `consume` lee con SQL crudo parametrizado (354-357). |
| `fulfill_client_export(filename, mimetype, datas, kind)` | 389-440 | Persiste el Word/PDF/HTML que monta el navegador (`persist_chatboo_session_file`) y sustituye el chip pendiente. |
| `recover_orphan_download_chips` | 442-487 | Busca adjuntos de la sesión con **`sudo()`** (458), **genera `access_token`** si falta (459-467) y devuelve URLs con token. |
| `append_local_ack(text)` | 489-517 | Añade nota local (sin LLM). |
| `set_messages` / `set_input_history` | 519-571 | Serializa quitando `\x00`; `set_messages` fusiona con lo previo; historial recortado a 50. |
| `update_last_used` | 573-575 | — |
| `_query_data_ttl_hours`, `get_fresh_query_data`, `_gc_stale_query_data` | 579-622 | TTL (ICP `pns_ai_chatboo.query_data_ttl_hours`, def. 12 h) y purga por cron. |
| `get_user_sessions(limit=50)` (`@api.model`) | 624-630 | Limpia antiguas del usuario y lista las suyas. |
| Captura de skills: `_slugify_skill_code`, `_looks_like_probe_code`, `_code_has_hardcoded_rows`, `_pick_capture_code`, `_score_relaxaicode_log`, `_find_best_capture_log`, `_normalize_turn_id`, `_find_best_capture_log_for_turn`, `compose_capture_code`, `_fetch_steps_for_turn`, `_last_user_prompt_text`, `_default_capture_procedure`, `prepare_skill_capture_action` | 634-974 | `/create-skill`: exige dueño (877-878) y `group_ai_writer` (879-882); busca el `ai.log` del turno **del usuario** (749-768); envuelve el "painter" con los pasos de *fetch* auto-confirmables del turno (`utils/skill_capture_compose.py`, solo `api_call`/`fetch_url`/`mcp_call`, `:21,60-77`); `_fetch_steps_for_turn` lee `ai.safe.operation`/`ai.log` con `sudo` **filtrando por `user_id`** (806-833). Abre el asistente de MCP con `default_from_chatboo=True` (945-958) ⇒ la skill queda **activa sin revisión** ([CODE] §6, línea 281-291). |
| `create` (`@api.model_create_multi`) | 976-979 | Llama a `_cleanup_old_sessions()` y a `super()`. |
| `unlink` | 981-1058 | `SET LOCAL lock_timeout='3s'`; borra con **`sudo`** los `chatboo.async.request` (1003-1007) y los `ir.attachment` de las sesiones (1028-1033); `super().unlink()`. |
| `_cleanup_old_sessions` (`@api.model`) | 1060-1079 | Borra las sesiones **del usuario actual** con `last_used_date` < hoy − `pns_ai_chatboo.history_retention_days` (def. 30; ≤0 desactiva). |

### 2.2 `chatboo.async.request` (nuevo; `models/chatboo_async_request.py:129-1879`)
| Campo | Tipo | Propósito (línea) |
|---|---|---|
| `session_id` | M2o `chatboo.session`, required, cascade, index | 136-139 |
| `user_id` | M2o `res.users`, required, index, default usuario (sin `ondelete` explícito) | 140-143 |
| `prompt` | Text required | 144 |
| `history` | Text (JSON del **navegador**) | 145 |
| `agent_code` / `provider_id` | Char / Integer (del navegador) | 146-147 |
| `screen_context` | Text JSON | 149 |
| `images` / `image_names` / `files` | Text JSON (data URLs **base64**) | 155-166 |
| `state` | Selection pending/running/done/error | 168-176 |
| `partial`, `struct_events`, `done_meta`, `response`, `error` | Text | 178-185 |
| `seen`, `cancel_requested` | Boolean index | 187-191 |
| `started_at`, `finished_at` | Datetime | 193-194 |

Métodos (HECHO): `enqueue` (198-221, `@api.model`, crea con `user_id=self.env.uid`); `spawn`
(223-274, hilo daemon con `uid` y contexto del request; en tests en línea); `_record_crash`
(276-309); `_process` (313-602, §5); `_start_heartbeat`/`_stop_heartbeat` (604-646);
`_flush_progress` (648-663, SQL crudo); `_finalize` (665-759); `_split_data_url`,
`_persist_turn_images` (769-837); `_recall_prior_images`, `_downscale_image_to_data_url`
(856-934); extracción de ficheros `_decode_text_bytes`, `_peek_ooxml_kind`, `_is_ole_cfb`,
`_format_excel_sheets`, `_xlsx_to_text`, `_xls_to_text`, `_docx_to_text`, `_extract_file_text`,
`_augment_prompt_with_files` (940-1222); `_persist_turn_files` (1224-1265);
`_llm_history_for_session` (1267-1296); `_save_to_session` (1298-1599); `read_progress`
(1603-1626, `@api.model`, **SQL crudo por `request_id` sin comprobar dueño**); `mark_seen`
(1628-1637); `request_cancel` (1639-1671, comprueba dueño 1646); `_is_cancel_requested`;
`_reclaim_stuck` (1688-1811); `_gc_old` (1812-1821); `cron_maintenance` (1823-1846); `_notify`
(1850-1879).

### 2.3 Modelos heredados
| Modelo | Archivo | Campos | Métodos y `super` (HECHO) |
|---|---|---|---|
| `ai.agent` | `models/ai_agent.py` | `chatboo_show_systray`, `chatboo_dataset_cache_max_mb`, `chatboo_query_data_ttl_hours`: computados no almacenados con inverso que escribe ICP (24-47) | `_compute_chatboo_product_settings` (`@api.depends('code')`, 49-60); 3 inversos (62-78) solo para el agente `pns_ai_chatboo`; `_module_factory_seed` (80-87, `super()` si no es Chatboo); `_host_identity_registry` (89-93, `super()` + identidad de `utils/chatboo_authorship.py:44-54`). |
| `ai.skill` | `models/ai_skill.py` | — | `create` (`model_create_multi`, 119-128), `write` (130-138), `unlink` (140-153): llaman a `super()` y avisan por bus `skills_changed`; con `chatboo_confirm_op` añaden nota local a la sesión **propia** (`_chatboo_confirm_session` 50-61 comprueba dueño). `action_delete_owned`/`action_rename_owned` (100-117) ponen contexto y llaman a `super()`. |
| `res.users` | `models/res_users.py` | `chatboo_card_width_ratio` Float (24-28) | `SELF_READABLE_FIELDS`/`SELF_WRITEABLE_FIELDS` como `@property` (30-36, ver 11.2); `chatboo_set_own_card_width_ratio` (`@api.model`, 42-48): `sudo().write` **solo** sobre `self.env.user`. |
| `res.config.settings` | `models/res_config_settings.py` | `chatboo_show_systray`, `chatboo_dataset_cache_max_mb` (def. 8), `chatboo_query_data_ttl_hours` (def. 12), `chatboo_chart_engine` (echarts/chartjs), `chatboo_default_show_mode` (17-64) | `get_values` (66-76) y `set_values` (78-87) con `super()`; leen/escriben ICP vía `utils/chatboo_product_icp.py:45-106` (con `sudo`). |
| `pns_ai_mcp.skill.capture.wizard` | `models/skill_capture_wizard.py` | `chatboo_session_id` Integer readonly (11) | `_onchange_source_log_id` (27-31, `super()` + re-envoltorio); `action_create_draft` (33-43, `super()` con `chatboo_confirm_op='created'`). |
| `ir.ui.menu` | `models/ir_ui_menu.py` | — | `_visible_menu_ids` (27-37, `super()`; oculta `menu_chatboo_root` sin carnet). |

---

## 3. Seguridad

### 3.1 `security/ir.model.access.csv` línea a línea
| Línea | Modelo | Grupo | R W C U | Valoración |
|---|---|---|---|---|
| 2 | `chatboo.session` | `base.group_user` | 1 1 1 1 | HECHO. Con grupo, pero **sin record rules** (3.2): todo usuario interno tiene CRUD sobre **todas** las sesiones. |
| 3 | `chatboo.async.request` | `base.group_user` | 1 1 1 0 | HECHO. Lectura, escritura y creación sobre **todos** los jobs de todos los usuarios. |

No hay líneas sin `group_id`. El wizard heredado y `res.config.settings` usan los ACL de sus
módulos. HECHO.

### 3.2 Record rules y grupos
- **No existe ninguna `ir.rule`** para `chatboo.session` ni `chatboo.async.request` (HECHO: Grep de
  `model_chatboo` en el repo solo devuelve el CSV y el cron; `security/` solo tiene el CSV).
- El módulo **no define grupos** (HECHO). El acceso a Chatboo es el "carnet": tener
  `ai.mcp.user.mcp_api_key_hash` no vacío (`utils/chatboo_access.py:7-23`, usa `sudo`,
  `pns_ai_mcp/models/mcp_user.py:288-294`). Se comprueba en **las rutas del controlador** y para
  ocultar el menú; **no** protege el ORM.
- Odoo 14 permite llamar por RPC (`/web/dataset/call_kw`) a cualquier método que no empiece por
  `_` (HECHO: `/opt/odoo-src/14.0/odoo/odoo/models.py:113-119`).

**¿Puede un usuario leer sesiones, mensajes o adjuntos de otro?**
1. **Sesiones y mensajes: sí** (HECHO por ACL sin reglas). Por RPC, cualquier usuario interno
   (con o sin carnet) puede `search_read` de `chatboo.session` de otros: `messages`,
   `input_history`, `last_query_data` (filas de datos de negocio), `last_query_code`,
   `last_screen_context`. También **escribir** y **borrar** (el `unlink` arrastra con `sudo` los
   adjuntos y jobs, 1003-1033). PENDIENTE: reproducir con dos usuarios internos.
2. **Adjuntos: sí** (HECHO por core + INFERENCIA). `ir.attachment.check` delega en
   `check_access_rights/rule` del registro `res_model/res_id`
   (`/opt/odoo-src/14.0/odoo/odoo/addons/base/models/ir_attachment.py:443-459`); como cualquier
   interno puede leer cualquier `chatboo.session`, puede leer sus adjuntos (imágenes, ficheros,
   exportaciones) y su `access_token` (campo con `groups="base.group_user"`, `:385`). Además
   `recover_orphan_download_chips` (público) genera tokens con `sudo` y devuelve URLs
   descargables sin sesión ([CONS] riesgo 21). PENDIENTE (incluido en F28 de [CONS]).
3. **Jobs: sí** (HECHO por ACL). Cualquier interno lee `prompt`, `history`, `images` y `files`
   en **base64**, `response` de otros durante las 72 h que viven (§6); `read_progress(id)` lee
   cualquier job por SQL sin comprobar dueño (1603-1626).
4. **Escritura cruzada** (HECHO por ACL; impacto INFERENCIA): un interno puede escribir en la
   sesión de otro `last_query_code`, `last_query_data`, `active_skill_code/params` o `messages`.
   En el siguiente turno de la víctima el código se reinyecta como pista al LLM y las filas como
   `previous_result` en el sandbox (`models/chatboo_async_request.py:336-352,493-505`): inyección
   de instrucciones y de datos falsos. Si el cliente pinta HTML de `messages` sin sanear, sería
   XSS almacenado entre usuarios: PENDIENTE (bloque C2).
5. **Turnos en nombre de otra sesión** (INFERENCIA fuerte): con ACL de creación, un interno puede
   crear un `chatboo.async.request` con `session_id` ajeno (y `user_id` ajeno, campo editable) y
   llamar al método público `spawn()`: el motor corre con **su** `uid` (230-253), consume
   proveedor, salta el carnet y `_save_to_session` escribe el turno en la sesión de la víctima;
   `_notify` avisa a la víctima. PENDIENTE.

### 3.3 Usos de `sudo()` (HECHO)
| Lugar | Para qué | Valoración |
|---|---|---|
| `utils/chatboo_access.py:15` | Leer carnet `ai.mcp.user` | Justificado (solo booleano). |
| `utils/chatboo_product_icp.py:47,87`, `chatboo_session.py:582,1064`, `controllers/chatboo.py:79` | Leer/escribir ICP | Escritura solo desde ajustes o inversos de `ai.agent` (quien pueda escribir el agente). |
| `models/res_users.py:47` | Escribir el ancho de tarjeta propio | Acotado a `self.env.user`. |
| `models/chatboo_session.py:458,467` | Buscar adjuntos de la sesión y crear token | Sin comprobar dueño en el método (público). |
| `models/chatboo_session.py:810,822` | Leer `ai.safe.operation`/`ai.log` | Filtrado por `user_id = env.user`. |
| `models/chatboo_session.py:1003,1028` | Borrar jobs y adjuntos en `unlink` | Lo dispara cualquier interno sobre cualquier sesión (3.2). |
| `models/chatboo_async_request.py:466` | Guardar `last_screen_context` | — |
| `controllers/chatboo.py:450-452` | `_reclaim_stuck(minutes=1)` de **todos** los usuarios al hacer *poll* | Cierra jobs ajenos y escribe en sus sesiones con entorno `sudo`; INFERENCIA: la marca horaria usa la tz del superusuario. |
| `controllers/chatboo.py:638,642` | Lista de proveedores si el agente no tiene cadena | Expone nombre/protocolo/modelo/host de **todos** los proveedores. |
| `pns_ai_mcp/utils/session_download.py:471,505,382` | Crear el adjunto y su token | `uid` conservado (`:418-422`): en 14 `sudo()` no cambia `env.user`, así que `_check_contents` fuerza `text/plain` a HTML/SVG para no administradores (`ir_attachment.py:331-340`). |

---

## 4. Rutas de `controllers/chatboo.py`

`JSON_ROUTE_TYPE` = `'json'` en 14 ([BASE] §10). Para `type='json'` Odoo 14 no valida CSRF
(solo `type='http'`, `/opt/odoo-src/14.0/odoo/odoo/http.py:779-785`), pero exige
`Content-Type: application/json`, que obliga a *preflight* entre orígenes. Todas las rutas son
`auth='user'`. "Carnet" = `_user_may_use_chatboo()` (30-31). Usuario: el de la sesión salvo
indicación.

| Ruta (línea) | Carnet | Entrada del navegador | Validación / devuelve | Señal |
|---|---|---|---|---|
| `/chatboo/check_health` (66-148) | **No** (solo afecta a `show_systray`) | — | Proveedor activo (alias o `host → modelo`), `can_save_raw`, FX, moneda, diagnóstico de agente | Expone host/modelo del proveedor a internos **sin** carnet; `str(e)` al cliente. |
| `/chatboo/prefs` (150-164) | Sí | `card_width_ratio` | Escribe solo el propio usuario | OK. |
| `/chatboo/test_connection` (166-192) | Sí | — | `provider.test_connection()` del primer proveedor del agente | INFERENCIA: chat real de pago y `ai.log` ([CONS] paso 3) por cualquier usuario con carnet. |
| `/chatboo/sessions/list` (196-217) | Sí | — | Sesiones propias (`get_user_sessions`) | OK. |
| `/chatboo/sessions/create` (219-244) | Sí | `name` | Crea con `user_id` propio | OK. |
| `/chatboo/sessions/load` (246-269) | Sí | `session_id` | Comprueba dueño (254-255); mensajes, historial, `conversation_id` | OK. |
| `/chatboo/sessions/fulfill_export` (271-293) | Sí | `session_id`, `filename`, `mimetype`, `datas` (base64), `kind` ∈ doc/pdf/html | Comprueba dueño (283-284); persiste adjunto (límite 15 MB, §9) | `mimetype` libre (ver 3.3). |
| `/chatboo/export/xlsx` (295-309) | Sí | `sections`, `filename` | Construye XLSX con `artifact_export.icon_xlsx_payload` | No persiste. |
| `/chatboo/sessions/save` (311-345) | Sí | `session_id`, `messages`, `input_history`, `conversation_id` | Comprueba dueño (321-322); sobrescribe historial (con fusión) | El cliente puede fabricar turnos en su propia sesión. |
| `/chatboo/sessions/rename` (347-363) | Sí | `session_id`, `new_name` | Comprueba dueño | OK. |
| `/chatboo/sessions/delete` (365-379) | Sí | `session_id` | Comprueba dueño; `unlink` (borra jobs y adjuntos) | OK. |
| `/chatboo/sessions/bulk_delete` (381-399) | Sí | `session_ids` (lista) | Comprueba dueño de cada una (391-393) | OK. |
| `/chatboo/save_raw_for_template` (401-419) | Sí | `query`, `result_json` | Exige `group_ai_admin` (407); crea `relaxaicode_raw_result` | OK. |
| `/chatboo/dismiss_messages` (421-433) | Sí | — | `mark_seen` de jobs propios | OK. |
| `/chatboo/async/poll` (435-492) | Sí | `session_id` | Reclaim `sudo` global (449-454); jobs propios terminados y en curso (filtra `user_id`) | `session_id` no se valida, pero el dominio filtra por usuario. |
| `/chatboo/async/cancel` (494-518) | Sí | `request_id`, `session_id` | Comprueba dueño (504-505, 508) | OK. |
| `/chatboo/skills/list` (520-544) | Sí | `agent_code` (kwargs) | `resolve_inference_agent_code` + `list_for_agent` | Acepta **cualquier agente activo** (`pns_ai_mcp/models/ai_agent_consumer.py:36-51`). |
| `/chatboo/create-skill` (546-571) | Sí | `session_id`, `skill_code`, `turn_id` | Dueño (557-558) + Writer (modelo) | Skill activa sin revisión ([CODE] §6). |
| `/chatboo/delete-skill` (573-587) | Sí | `skill_code`, `session_id` | `action_delete_owned` (MCP valida dueño/Writer) | `session_id` validado en `_chatboo_skill_ctx` (42-51). |
| `/chatboo/rename-skill` (589-605) | Sí | `old_code`, `new_code`, `session_id` | `action_rename_owned` | Igual. |
| `/chatboo/providers` (609-650) | Sí | — | Cadena de failover del agente; si no hay, **todos** con `sudo` | Información de infraestructura. |
| **`/chatboo/stream`** (654-835) `type='http'`, `methods=['POST']`, **`csrf=False`, `cors='*'`** | Sí (664) | Cuerpo JSON crudo: `session_id`, `message`, `history`, `agent_code`, **`provider_id`**, `screen_context`, `images`, `image_names`, `files` | Sesión: si no es del usuario **crea una nueva** (693-699, correcto); agente: cualquiera activo (704); proveedor: **cualquiera existente**, sin comprobar cadena ni grupo (`pns_ai_mcp/models/ai_execution_engine.py:171-174`, [SECR] §2.4); `history` sin contrastar ([LLM] §3.2). Devuelve SSE (`meta`, `status`…, `replace`, `done`). | Ver 4.1. |

Utilidades: `_json_response` (945-950) **ignora `status`** (los 400/403/500 salen como 200;
HECHO). `_sse_event` (952-954) serializa con `json.dumps`.

### 4.1 `/chatboo/stream` sin CSRF (INFERENCIA, PENDIENTE)
- El cuerpo se lee con `json.loads(request.httprequest.data)` (670) sin exigir
  `Content-Type: application/json`. Una petición "simple" entre orígenes (`text/plain`, sin
  *preflight*) es válida.
- La cookie `session_id` de Odoo 14 se emite sin atributo `SameSite`
  (`/opt/odoo-src/14.0/odoo/odoo/http.py:1455-1456`). Navegadores que aplican `Lax` por defecto
  (Chrome/Edge) no la enviarían en un POST entre sitios; otros (Firefox, Safari) sí podrían.
- Consecuencia posible: una web de terceros lanza turnos en nombre del usuario conectado
  (coste, herramientas de lectura, propuestas de escritura que aún requieren confirmación). No
  puede **leer** la respuesta (`cors='*'` no vale con credenciales).
- `cors='*'` con `methods=['POST']`: INFERENCIA, el *preflight* `OPTIONS` no llega a la ruta
  (405), así que solo funcionan las peticiones simples. PENDIENTE probar con `curl`/navegador.

---

## 5. Flujo de un mensaje en el servidor

```
Navegador ──POST /chatboo/stream──▶ chat_stream (controllers/chatboo.py:654)
  1. carnet (664) · parse JSON (670-681) · start_new_turn (683-687, pns_ai_mcp/utils/mcp_correlation.py:16)
  2. sesión propia o nueva (691-699)
  3. resolve_inference_agent_code + get_providers_for_agent (704-729) → si no hay proveedor: SSE con aviso
  4. enqueue (732-737) → chatboo.async.request(state=pending) ; cr.commit() (738) ; spawn() (739)
  5. generate_stream (747-825): SELECT del job cada 0,3 s, reemite struct_events/replace/done,
     keepalive 15 s, tope 600 s; al terminar marca seen (810-816)
        │
        ▼  hilo daemon "chatboo-async-<id>" (chatboo_async_request.py:239-274), cursor propio, uid del usuario
  _process (313-602)
   a. state=running + commit + bus 'thinking' (320-322)
   b. lee de la sesión last_query_code, get_fresh_query_data, active_skill_* (336-352)
   c. apply_sticky_show_mode (355-372, pns_ai_mcp/utils/presentation_mode.py:301)
   d. history/images del job (379-388); texto de ficheros añadido al mensaje (394, sin truncar)
   e. apply_turn_axis / resolve_remote_formatting_override (401-427, formatting_mode_policy.py:160)
   f. recall de hasta 3 imágenes previas reescaladas a 768 px (439, 842-896)
   g. latido cada 10 s (445, 604-633)
   h. screen_context → enrich_screen_context (utils/screen_context.py:99-161) + guarda last_screen_context con sudo (453-480)
   i. AgentEngine(env con chatboo_session_id…).run_stream(...) (482-505; agent_engine.py:1051)
      eventos: token/replace/done/error/status…; meta-eventos active_skill, query_code, query_data (506-556)
      flush a BD cada 0,3 s por SQL (547-556, 648-663); cancelación cooperativa (506, 551, 558-565)
   j. _finalize (665-759) en cursor NUEVO: estado final, _save_to_session (1298-1599), commit,
      bus 'async_done' o 'error' (743); último recurso SQL crudo (750-757)
   k. rollback del cursor del hilo (598-602)
```
- `_save_to_session` (HECHO): añade el turno de usuario (con chips de imágenes/ficheros ya
  persistidos como `ir.attachment` de la sesión, 1341-1355), consume chips "staged" y huérfanos,
  persiste SVG inline como ficheros (`svg_download.persist_inline_svgs_from_html`, 1380-1404),
  actualiza `input_history` (1411-1421), añade el mensaje del asistente con métricas, fuentes,
  `records`, `backend_history` y `clip_data` (1455-1536), y guarda `last_query_code`,
  `last_query_data` (+fecha) y la skill activa (1542-1585).
- Bus (HECHO): en 14 no existe `bus.bus._sendone` (core solo `sendone(channel, message)`,
  `/opt/odoo-src/14.0/odoo/addons/bus/models/bus.py:78-79`); el código cae al canal
  `(db, 'res.partner', partner_id)` con el mensaje **como cadena JSON** (1874-1877).
  INFERENCIA: el cliente 14 debe hacer `JSON.parse`; PENDIENTE (C2).
- Cron (HECHO, `data/chatboo_async_cron.xml:7-17`): cada 5 min `cron_maintenance` (1823-1846) =
  `_reclaim_stuck` (jobs pending/running sin latido > 3 min; guarda lo generado como respuesta
  incompleta, `FOR UPDATE SKIP LOCKED` + savepoint, 1688-1811) + commit + `_gc_old` (borra jobs
  done/error con más de 72 h) + `_gc_stale_query_data`. El cron se ejecuta con el usuario que lo
  creó al instalar (`ir_cron.py:55`, INFERENCIA: OdooBot/superusuario).
- Workers: el *tail* ocupa un worker HTTP hasta 10 min y, en prefork, `limit_time_real` puede
  matar el proceso con el hilo del motor dentro ([LLM] §7, líneas 358-378; [CONS] riesgo 35).

---

## 6. Retención

| Dato | Dónde | Cuánto tiempo | Cómo se borra (HECHO salvo indicación) |
|---|---|---|---|
| Mensajes completos (texto, HTML/markdown, `sources`, `records`, `clip_data` con **filas**, `backend_history`, `user_prompt`, métricas) | `chatboo.session.messages` | Hasta borrar la sesión | Manual (rutas delete/bulk_delete) o `_cleanup_old_sessions` |
| Historial de prompts | `input_history` | Últimos 50 (567) | Con la sesión |
| `last_screen_context` (acción, modelo, id, vista, hash de URL) | sesión | Se sobrescribe cada turno | Con la sesión |
| `last_query_code` | sesión | Indefinido | Con la sesión |
| `last_query_data` (filas) | sesión | TTL 12 h (ICP `pns_ai_chatboo.query_data_ttl_hours`; 0 = nunca) | Cron cada 5 min (`_gc_stale_query_data`, 604-622); tamaño máx. 8 MB (ICP `pns_ai_mcp.dataset_cache_max_bytes`, [LLM] §7) |
| Imágenes, ficheros, exportaciones, SVG | `ir.attachment` (`res_model='chatboo.session'`) con `access_token` | Hasta borrar la sesión | `unlink` de la sesión (1027-1038) |
| Jobs (prompt, `history`, imágenes y ficheros **base64**, respuesta, eventos) | `chatboo.async.request` | 72 h tras terminar (`GC_HOURS`, :49) | Cron `_gc_old` (1812-1821); también al borrar la sesión |
| Logs del motor | `ai.log` (pns_ai_mcp) | Política de MCP | [CONS] D13 |

Política de sesiones (HECHO, `chatboo_session.py:1060-1079`): parámetro
`pns_ai_chatboo.history_retention_days` (por defecto **30**; no está en los ajustes ni en
`data/`, solo en Parámetros del sistema). Cuenta desde `last_used_date`, que se refresca al
cargar la sesión (256). **Solo se ejecuta para el usuario actual** al crear una sesión o listar
las suyas. INFERENCIA: las sesiones (y sus adjuntos con token) de usuarios que no vuelven a abrir
Chatboo, archivados o sin carnet **no caducan nunca**; no hay cron de retención. Si se borra el
usuario, `ondelete='cascade'` borra sus sesiones, pero el `unlink` de ORM no se ejecuta (cascada
SQL) ⇒ sus adjuntos quedarían huérfanos (INFERENCIA, PENDIENTE).

---

## 7. Skills de fábrica (`ai/skills/system`)

Siembra: `data/chatboo_skill_data.xml:7-10` → `ai.skill.import_from_module('pns_ai_chatboo')`
con `replace_existing=True` en cada instalación/`-u` (`pns_ai_mcp/models/ai_skill.py:1629-1647`)
y borra `flota`/`payroll` (`unlink_named_factory_skills`, `:1599-1626`). Inclusión en el agente:
`default_skill_codes = @pns_ai_chatboo` (`data/ai_agent_data.xml:21`); las de `agent_codes`
vacío entran en cualquier agente que tire de `@pns_ai_chatboo` (`ai_skill.py:1665-1668`).

**Quién puede invocarlas** (HECHO): cualquier usuario con carnet ve la lista
(`list_for_agent`, `ai_skill.py:645-673`, sin filtro de grupo). El `code_body` se ejecuta con el
`env` del usuario del chat, sin cursor READ ONLY ([CODE] §6 y §6b.4): las lecturas respetan sus
ACL y reglas (si no tiene Contabilidad, las financieras fallan con `AccessError`), y **no** usan
`sudo` salvo `sys-info` para `web.base.url`.

**Ejecución al guardar** ([CODE] §6b.4): el *smoke-run* de `_check_code_body_contract` no se
ejecuta en instalación/actualización (`ai_skill.py:407-409`, `registry.ready` falso) pero **sí**
cuando un admin/Writer edita o recarga una skill desde la interfaz: se ejecuta con su `env` y en
la misma transacción. Ninguna skill de fábrica escribe en BD (HECHO por lectura del código), así
que el riesgo es de rendimiento (ver `customer-risk-analysis` y las financieras).

| Skill (`.md`/`.py`) | Qué hace | Modelos que lee | Escribe | Devuelve | Observaciones |
|---|---|---|---|---|---|
| `users-all` (`users_all.*`) | Censo de **todos** los usuarios, incluidos archivados, por login (`.py:5`) | `res.users` (`active_test=False`) | No | `data`: Login, Nombre, Email, Tipo (Interno/Portal), Activo, Último acceso (`login_date`) (7-14) | `agent_codes` vacío. Lo que ya puede leer un interno, pero agregado para cualquiera con carnet. |
| `users-logged` | Usuarios con presencia online/away; si no hay, 20 últimos accesos (`.py:6-33`) | `bus.presence`, `res.users` | No | `data`: Usuario, Login, Estado, Última señal | `bus.presence` lectura `base.group_user` (`/opt/odoo-src/14.0/odoo/addons/bus/security/ir.model.access.csv:3`). Campos verificados (`bus_presence.py:30-33`). |
| `sys-info` | Versión, serie, BD, hora del servidor, tz, idioma, usuario, compañía, nº compañías/usuarios/módulos, `web.base.url` (`.py:4-21`) | `res.company`, `res.users`, `ir.module.module`, ICP (`sudo`) | No | `data` Propiedad/Valor | Revela nombre de BD y URL base. |
| `customer-risk-analysis` | Score 0-100 por cliente (6 criterios) (`.py:30-227`) | `account.move` (posted, out_invoice/out_refund), `account.move.line` | No | `data`: Cliente, NIF, F.Pend., Deuda €, F.Pagadas, Ratio %, DSO, Dispersión %, Score, Fiabilidad + colores | `agent_codes` vacío. **N+1**: un `search` de `account.move.line` por factura pagada (72-76). INFERENCIA (error funcional): la línea buscada es la de cobro **de la propia factura** (`move_id = inv.id`), cuya `date` es la fecha contable de la factura, no la del pago ⇒ DSO ≈ 0 y "a tiempo" casi siempre. Detección 14/17 por excepción (40-45). |
| `analisis-financiero` | Informe narrativo (painter-free): KPIs, liquidez, deudas, cobros, ratios, pólizas (`.py`) | `account.move`, `account.move.line`, `account.journal` | No | `tables` (9+), `footer`, `report_outline`, `closing_required`, `company` | `bal_prefix` (461-485) recorre **todas** las líneas contables publicadas, 7 veces, sin filtro de fecha ni de compañía (PGC español: 57, 430, 400…). INFERENCIA: muy lento en BD grandes y mezcla compañías permitidas en el contexto. |
| `financial-health` | Gemelo en inglés del anterior | Igual | No | Igual | Mismo coste. **HECHO (error)**: los KPIs usan la clave `Metric`/`Value` (552-566) pero el cierre busca `Indicator`/`Indicador` (765), así que `_overdue`/`_drawn` nunca se detectan y `closing_required` siempre dice "no urgent action". |
| `credit-facility` | Dispuesto a fin de mes en diarios de póliza (`P*`, "póliza", "credit facility"…) (`.py:235-378`) | `account.journal`, `account.move.line` | No | `groups` (bloques de 5 meses, show-chart), `footer`, `summary` | `args_policy: ask`. Heurística de nombres (160-170). |
| `billing` | Facturación (base imponible) por mes de `out_invoice` publicadas (`.py:120-167`) | `account.move` | No | `data` Month/Amount/Invoices, `show_mode=show-chart` | — |
| `annual-billing` | Facturación por semana ISO con barras `█` en HTML (`.py:36-186`) | `account.move` | No | `formatted_text` (HTML de autor) | Usa `start_date`, `end_date`, `year`, `anio`, `arguments`, `lugar`, `fecha` **sin** `try/except NameError` (10-13): depende de que el sandbox los inyecte (PENDIENTE). Interpola `start_date`/`end_date` del usuario (recortados a 10 caracteres) en HTML de confianza (100, 66): INFERENCIA, inyección HTML de bajo alcance. |
| `dashboard` | 9 tarjetas: equipo (o diario), top clientes y tendencia para mes, trimestre y año (`.py:45-138`) | `account.move` (`team_id` lo aporta `sale`, `/opt/odoo-src/14.0/odoo/addons/sale/models/account_invoice.py:15`) | No | `groups`, `show_mode=dashboard` | Detecta `team_id` con `fields_get` (116). |
| `forecast` | Previsión Open-Meteo en 3 rondas (`propose_steps` `fetch_url`) (`.py:383-500`) | `res.company` (ciudad/provincia) | No | `data`/`groups` + `footer`, o `formatted_text` de error | Sale a Internet: envía la ciudad de la compañía o las indicadas a `open-meteo.com` (lista blanca sembrada por MCP, `pns_ai_mcp/data/url_whitelist_data.xml:8,15`). Los nombres de ciudad del usuario se interpolan en `formatted_text` (407-409, 473-474): INFERENCIA, HTML sin escapar. |

Común a todas: fecha del **servidor** (`date.today()`), no la del usuario (HECHO, p. ej.
`customer_risk_analysis.py:25`; coincide con [LLM] §3.1). `operator`, `format_amount`,
`company`, `env` los aporta el sandbox ([CODE] §4).

---

## 8. Contextos de fábrica (`ai/contexts/domain`)

Importados en cada `-u` con `ai.context._import_all_from_module(True, 'pns_ai_chatboo')`
(`data/chatboo_context_data.xml:5`, `noupdate="0"`). INFERENCIA: `replace_existing=True`
sobrescribe en cada actualización lo que un administrador haya editado, aunque `self_chatboo`
dice "Administrators may edit this context" (`self_chatboo.xml:76`). PENDIENTE.
Los tres son **obligatorios** en el agente (`data/ai_agent_data.xml:18-20`,
`models/ai_agent.py:80-87`).

| Contexto | Archivo | Qué enseña al LLM (HECHO) |
|---|---|---|
| `self_chatboo` (v2.2, `agent_codes=pns_ai_chatboo`, `is_fallback`) | `self_chatboo/self_chatboo.xml` | Identidad "Chatboo"; actúa **dentro de los permisos del usuario** (21-23); ámbito Odoo; peticiones fuera de ámbito: responder igualmente con una protesta irónica (42-56); tono y respuestas a "¿quién eres/quién te creó?" usando los bloques de host (`utils/chatboo_authorship.py:26-41`); no consultar `system://info`. |
| `ui_focus` (v1.1) | `ui_focus/ui_focus.xml` | Con `[Active screen]`, las referencias implícitas ("esto", "cámbialo") apuntan al registro de pantalla; lectura con relaxaicode/MCP, escritura **solo** con `propose_safe_operations` (22-25); usar el recuento "List scope". El bloque lo genera `utils/screen_context.py` con el `env` del usuario (`browse().exists()`, `search_count` con el dominio que manda el navegador, 132-155, 199-222). |
| `presentation_grids` (v1.35) | `presentation_grids/presentation_grids.xml` | Contrato de presentación: filas estructuradas y claves `_row_color`, `_color_*`, `_style_*`, `_title_*`; ejes painter/footmode/showmode; exportaciones (PDF, Excel, Word, txt, Markdown, HTML) sin crear `ir.attachment` ni Caja B (91-93); paleta pastel; gráficos ECharts/Chart.js; mapas con `pns_geo`; formato de fecha/hora; tablas anchas para histogramas. |

---

## 9. Ajustes, parámetros y crons

| Parámetro (ICP) | Origen | Valor por defecto | Uso |
|---|---|---|---|
| `pns_ai_chatboo.download_max_bytes` | `data/chatboo_icp_data.xml:4-7` (noupdate) | 15728640 (15 MB) | Tope por adjunto persistido (`pns_ai_mcp/utils/session_download.py:24,39-46,444-457`). INFERENCIA: no aplica a `_persist_turn_images` (Attachment.create directo, 820-826) ni al cuerpo de `/chatboo/stream`. |
| `pns_ai_chatboo.chart_engine` | `chatboo_icp_data.xml:8-11` + ajustes | `echarts` | Motor de gráficos. |
| `pns_ai_chatboo.default_show_mode` | `chatboo_icp_data.xml:12-15` + ajustes | `show-table` | Modo inicial de sesión (legado `default_showmode`). |
| `pns_ai_chatboo.show_systray` | ajustes / `ai.agent` | `True` | Lanzador en la barra (solo con carnet, `controllers/chatboo.py:85-86`). |
| `pns_ai_mcp.dataset_cache_max_bytes` | ajustes (MB × 1 MiB) | 8 MB | Tope de cache de filas (parámetro de MCP que escribe Chatboo, `utils/chatboo_product_icp.py:7,90-93`). |
| `pns_ai_chatboo.query_data_ttl_hours` | ajustes | 12 | TTL de `last_query_data`. |
| `pns_ai_chatboo.history_retention_days` | **solo** Parámetros del sistema | 30 | Retención de sesiones (§6). |

- Vista de ajustes (`views/res_config_settings_mcp_agents_views.xml:4-73`): inserta tras el botón
  `action_open_module_inference_agents` del formulario de MCP un bloque "Chatboo" con
  *Interface* (systray), *Conversation memory* (MB y horas), *Data presentation* (motor y modo) y
  botón "Configuration" → `action_open_module_agent` con `agent_code='pns_ai_chatboo'`
  (`pns_ai_mcp/models/res_config_settings.py:145`). HECHO.
- Los mismos tres valores de producto aparecen como campos computados en el formulario del
  agente (`models/ai_agent.py:24-78`).
- Crons: solo "Chatboo: async queue maintenance" (5 min, activo, `numbercall=-1`,
  `doall=False`; `data/chatboo_async_cron.xml`). HECHO.
- Agente sembrado `ai_agent_chatboo` (`data/ai_agent_data.xml`, **noupdate**): `code
  pns_ai_chatboo`, `agent_type inference`, `default_context_codes @pns_ai_mcp\n@pns_ai_chatboo`.
  HECHO. Las migraciones 2.1.217/2.1.237 escriben `…\nacl_security` en `default_context_codes`
  (`migrations/2.1.217/post-migrate.py:15`, `2.1.237:12`), distinto del XML: INFERENCIA, una BD
  migrada y una instalada desde cero quedan con recetas diferentes. PENDIENTE.

---

## 10. Configuración necesaria, en orden

Rutas de menú en inglés (traducciones no verificadas). Requisito previo: la configuración de
MCP de [CONS] §2, pasos 0-6.

| # | Paso | Ruta / lugar | Detalle |
|---|---|---|---|
| 0 | Imagen | Dockerfile del cliente | `openpyxl` (obligatorio, bloquea la instalación); `xlrd` opcional para `.xls`; Pillow (core). |
| 1 | Instalar | Apps → "Chatboo" | Siembra agente, contextos, skills, ICP y cron. |
| 2 | Proveedor del agente | AI Engine → Agents → Chatboo → pestaña Providers | Sin cadena y con más de un proveedor, `/chatboo/stream` responde "No AI provider is configured" (713-729). |
| 3 | Carnet por usuario | AI Engine → Security → Users → (usuario) → "Generate API Key" | Sin hash no aparece el menú (`models/ir_ui_menu.py:27-37`) y todas las rutas (salvo `check_health`) responden "access denied". INFERENCIA: `load_menus` está en caché por usuario (`/opt/odoo-src/14.0/odoo/odoo/addons/base/models/ir_ui_menu.py:221-222`); puede hacer falta recargar/limpiar caché tras generar la clave. PENDIENTE. |
| 4 | Grupos | Ajustes → Usuarios → (usuario) → "Artificial Intelligence" | AI Writer para `/create-skill`, `/delete-skill`, `/rename-skill`; AI Administrator para "guardar resultado en bruto". Contabilidad para las skills financieras; `sale` para `team_id` en `/dashboard`. |
| 5 | Ajustes de Chatboo | Ajustes → AI Engine → bloque "Chatboo" | Systray, límite MB, TTL, motor de gráficos, modo inicial; "Configuration" abre el agente. |
| 6 | Parámetros | Ajustes → Técnico → Parámetros → Parámetros del sistema | `pns_ai_chatboo.history_retention_days` (30) y `pns_ai_chatboo.download_max_bytes` (15 MB). |
| 7 | Cron | Ajustes → Técnico → Automatización → Acciones planificadas | Comprobar "Chatboo: async queue maintenance" activo. |
| 8 | Red | Lista blanca de MCP | `open-meteo.com` para `/forecast` (ya sembrada). |
| 9 | Servidor | `odoo.conf` y proxy | Con prefork, `limit_time_real` ≥ 600 o el *tail* y el hilo mueren ([LLM] §7); proxy sin *buffering* (la ruta envía `X-Accel-Buffering: no`, 837-842) y `proxy_read_timeout` alto; HTTPS. |

---

## 11. Compatibilidad con Odoo 14 / Python 3.7.3 y riesgos

### 11.1 Python 3.7.3 (HECHO salvo indicación)
- `from __future__ import annotations` (`utils/chatboo_display_time.py:10`, `fx_rates.py:5`,
  `skill_capture_compose.py:12`): válido desde 3.7.
- `zoneinfo` (3.9) solo como alternativa tras MCP y antes de `pytz` (`chatboo_display_time.py:62-78`).
- `contextlib.nullcontext` (3.7) solo en la rama sin `Environment.manage` (17+), `:59-64`.
- f-strings, `{**r}`, `max(default=)`, `re.fullmatch`, `isoformat(timespec=)`: 3.6+.
- No se ha visto `:=`, `match`, `dict | dict` ni genéricos `list[str]` en el bloque.

### 11.2 Odoo 14
| Punto | Estado |
|---|---|
| `api.Environment.manage()` en hilos | Se usa (HECHO, `chatboo_async_request.py:52-64,249,293,715`). |
| `odoo.registry(db)` | Existe en 14 (`:67-78`). |
| `invalidate_recordset` (17) | Cae a `invalidate_cache(fnames, ids)` (HECHO, `chatboo_session.py:367-373`, `chatboo_async_request.py:1318-1326`). |
| `bus._sendone` (16+) | No existe en 14; cae a `sendone` con cadena JSON (5). PENDIENTE que el cliente lo parsee. |
| Assets por plantilla y `qweb` en manifest | Correcto para 14. |
| Campos de contabilidad (`move_type`, `payment_state`, `invoice_date_due`, `default_account_id`, `user_type_id`) | Existen en 14 (`account/models/account_move.py:157,238`). |
| `SELF_READABLE_FIELDS`/`SELF_WRITEABLE_FIELDS` como `@property` (`models/res_users.py:30-36`) | En 14 son **listas de clase** (`base/models/res_users.py:268-270`) y varios módulos las leen a nivel de clase (`hr/models/res_users.py:139`: `pool[self._name].SELF_READABLE_FIELDS + …`). INFERENCIA: funciona solo porque `mail` (dependencia) las reasigna como lista en la clase final antes (`mail/models/res_users.py:69-73`); con otro orden, `property + list` daría `TypeError` al cargar el registro. Frágil; PENDIENTE probar con `hr` instalado. |
| `_visible_menu_ids` | El método base está en `ormcache` por grupos (`ir_ui_menu.py:79`); el override no se cachea, pero `load_menus` sí por usuario (10, paso 3). |
| `ir.cron` `numbercall`/`doall` | Existen en 14 (XML del cron). |

### 11.3 Riesgos (de mayor a menor; ver también Resumen)
1. **Aislamiento entre usuarios inexistente en el ORM** (3.2): lectura/escritura/borrado de
   sesiones, mensajes, datasets, adjuntos y jobs ajenos por RPC. HECHO (ACL) / PENDIENTE prueba.
2. **Inyección cruzada** en el siguiente turno de otro usuario vía `last_query_code`,
   `last_query_data`, `active_skill_*`, `messages` (3.2.4). INFERENCIA.
3. **Turnos lanzados por RPC** (`create` + `spawn`) saltando el carnet y escribiendo en sesiones
   ajenas (3.2.5). INFERENCIA.
4. **`/chatboo/stream` sin CSRF** con lectura de cuerpo crudo (4.1). PENDIENTE.
5. **Proveedor y agente elegidos por el navegador** sin restricción; `history` fabricable.
   HECHO.
6. **Coste y DoS**: texto de adjuntos sin truncar (todas las hojas Excel, 937-938, 1196-1199),
   imágenes sin tope de tamaño, *recall* de imágenes cada turno, un worker por stream hasta
   10 min. HECHO / INFERENCIA. También vector de *prompt injection* indirecta (documentos
   subidos).
7. **Retención sin cron**: sesiones de usuarios inactivos y sus adjuntos con token públicos sin
   caducidad; jobs con base64 72 h. HECHO / INFERENCIA.
8. **Skills de fábrica para cualquiera con carnet**, con datos agregados de usuarios y sistema;
   `ai.skill.unlink_named_factory_skills` invocable por cualquier interno ya CONFIRMADO en
   [VERIF] C ([CONS] riesgo 11): con Chatboo instalado afecta a sus 11 skills de fábrica.
9. **Errores funcionales** en skills: `financial-health` (cierre siempre "sin urgencia"),
   `customer-risk-analysis` (DSO/puntualidad mal calculados, N+1), financieras con recorrido
   completo de apuntes ×7.
10. **Migraciones** 2.1.296/2.1.300 borran skills `flota`/`payroll` sin filtrar `owner_id`
    (`migrations/2.1.296/post-migrate.py:26-34`): borrarían también skills de usuario con ese
    código. HECHO.
11. `check_health` expone el proveedor a internos sin carnet; `_json_response` devuelve 200 en
    errores. HECHO.

### 11.4 Índice de `migrations/` (una línea por script; todos `post-migrate.py` con `SUPERUSER_ID`)
| Versión | Qué hace |
|---|---|
| 2.1.33 | Reimporta contextos de Chatboo y reconstruye la caché del agente. |
| 2.1.38 | Reimporta `self`, `self_es_ES`, `self_en_US` (creador PATANEGRA) y sincroniza caché. |
| 2.1.92 | `import_from_files` de todas las skills y fija `skill_ids` del agente a las por defecto. |
| 2.1.112, .113, .129, .130, .131, .132, .146 | Resiembra de skills de fábrica desde disco (`import_from_files`, todas las de todos los módulos). |
| 2.1.133 | Igual (parámetros de periodo y bloques de meses en skills financieras). |
| 2.1.134 | Igual (ayuda `?` determinista en skills financieras). |
| 2.1.135 | Igual (narrativa de los informes financieros). |
| 2.1.136 | Igual (esqueleto fijo del informe; ayuda nunca por LLM). |
| 2.1.163 | `auto_link_mcp_nucleus=True` en el agente y `sync_factory_knowledge` de MCP. |
| 2.1.177 | Resiembra de skills tras renombrar archivos a snake_case. |
| 2.1.217 | SQL: recetas `@pns_ai_mcp\n@pns_ai_chatboo\nacl_security` y `@pns_ai_chatboo`, quita `auto_link`; `source_module='pns_ai_chatboo'` en 5 contextos; reimporta y resetea contextos del agente. |
| 2.1.232 | Borra los contextos clonados `self_es_ES`/`self_en_US`. |
| 2.1.234 | Fija `required_context_codes` = `self`, `presentation_grids`, `ui_focus` (+ existentes). |
| 2.1.237 | Igual que 2.1.234 y rellena recetas vacías (con `acl_security`). |
| 2.1.241 | `_fill_empty_factory_seeds` del agente. |
| 2.1.263, 2.1.264 | Reimporta `self*` (texto de ámbito/saludo) y sincroniza caché. |
| 2.1.265 | Renombra el contexto `self` → `self_chatboo` y reescribe el pin. |
| 2.1.266 | Quita `self`/`self_*` ajenos de **todos** los agentes, borra la fila `self` y su xmlid, reimporta `self_chatboo`, sincroniza Chatboo y MCP. |
| 2.1.267 | Retira restos `self`, `self_es_ES`, `self_en_US`, `self_retired`. |
| 2.1.268 | Reimporta `self_chatboo` y retira `self` genérico. |
| 2.1.269 | Purga archivos fuente retirados de `self` y la fila genérica. |
| 2.1.271 | Reescribe el pin `self` → `self_chatboo` (vía `_unlink_foreign_identity_packs`). |
| 2.1.296 | Borra skills `flota`/`payroll` (por código, comando o ruta; sin filtrar dueño). |
| 2.1.300 | Igual que 2.1.296 + `import_from_module('pns_ai_chatboo')`. |
| 2.1.301 | `import_from_module` + `unlink_named_factory_skills(['flota','payroll'])`. |

---

## Resumen del bloque

1. Chatboo es el cliente de chat de `pns_ai_mcp`: guarda la conversación (`chatboo.session`) y
   ejecuta cada turno en un hilo con cursor propio (`chatboo.async.request`), delegando todo el
   razonamiento en `AgentEngine.run_stream`. El navegador solo hace *tail* SSE del job.
2. Depende de `pns_ai_mcp` para modelos (`ai.agent`, `ai.skill`, `ai.context`, `ai.mcp.user`,
   `ai.log`, proveedores), motor, utilidades de descargas/presentación, grupos y la vista de
   ajustes; de `pns_base` solo para `compat`. `openpyxl` (declarado) se usa al adjuntar Excel.
3. Acceso: "carnet" = hash de API key MCP; se aplica en rutas y menú, **no** en el ORM.
4. **Hallazgo principal**: ACL `base.group_user` con CRUD en sesiones y RWC en jobs, **sin record
   rules**. Cualquier interno puede, por RPC, leer, modificar y borrar conversaciones, datasets,
   adjuntos (y sus tokens) y jobs (con imágenes y ficheros en base64) de otros usuarios.
5. Consecuencias derivadas: inyección de código/datos en el siguiente turno de otro usuario;
   creación de jobs y `spawn()` por RPC saltando el carnet; `read_progress` sin dueño.
6. `/chatboo/stream`: `csrf=False`, `cors='*'`, cuerpo crudo ⇒ posible CSRF con peticiones
   simples (cookie sin `SameSite` en 14). `provider_id` y `agent_code` del navegador se aceptan
   sin restricción; `history` fabricable.
7. Las rutas JSON comprueban dueño de la sesión correctamente; `check_health` no exige carnet;
   `/chatboo/providers` puede listar todos los proveedores con `sudo`.
8. Retención: sesiones 30 días desde el último uso pero solo al volver a usar Chatboo; sin cron;
   adjuntos con token mientras viva la sesión; jobs 72 h; datasets 12 h.
9. 11 skills de fábrica, solo lectura, con el `env` del usuario; invocables por cualquiera con
   carnet. `users-all`, `users-logged` y `sys-info` agregan datos de usuarios y sistema;
   `forecast` sale a Open-Meteo con la ciudad de la empresa.
10. Errores funcionales: `financial-health` nunca detecta urgencias; `customer-risk-analysis`
    calcula DSO con la fecha de la factura y hace N+1; las financieras recorren todos los
    apuntes 7 veces sin filtro de compañía.
11. Tres contextos obligatorios (identidad, foco de pantalla, presentación) que se reimportan
    con sobrescritura en cada `-u`.
12. Compatibilidad 14 / 3.7.3 correcta en general; puntos frágiles: `SELF_*_FIELDS` como
    `property` (funciona gracias a `mail`), bus con cadena JSON, `limit_time_real` en prefork.
13. Sin tests propios. 32 migraciones, casi todas de resiembra de conocimiento; dos borran
    skills por nombre sin filtrar dueño.

## Tabla de cobertura

| Archivo | Lectura |
|---|---|
| `__manifest__.py`, `__init__.py`, `hooks.py` | Entero |
| `security/ir.model.access.csv` | Entero |
| `data/ai_agent_data.xml`, `chatboo_context_data.xml`, `chatboo_skill_data.xml`, `chatboo_icp_data.xml`, `chatboo_async_cron.xml` | Entero |
| `views/chatboo_menus.xml`, `assets.xml`, `res_config_settings_mcp_agents_views.xml` | Entero |
| `models/__init__.py`, `chatboo_session.py` (1079), `ai_agent.py`, `ai_skill.py`, `res_users.py`, `res_config_settings.py`, `skill_capture_wizard.py`, `ir_ui_menu.py` | Entero |
| `models/chatboo_async_request.py` (1880) | Entero (en dos lecturas: 1-1355 y 1356-1880) |
| `controllers/__init__.py`, `controllers/chatboo.py` (955) | Entero |
| `utils/__init__.py`, `chatboo_access.py`, `chatboo_authorship.py`, `chatboo_display_time.py`, `chatboo_product_icp.py`, `compat.py`, `fx_rates.py`, `screen_context.py`, `skill_capture_compose.py`, `turn_deliverable.py` | Entero |
| `ai/contexts/domain/*/*.xml` (3) | Entero |
| `ai/skills/system/*.md` y `*.py` (11 + 11) | Entero |
| `migrations/` 2.1.33, .38, .92, .112, .113, .129, .163, .217, .232, .234, .237, .241, .263-.269, .271, .296, .300, .301 | Entero |
| `migrations/` 2.1.130, .131, .132, .133, .134, .135, .136, .146, .177 | **No enteros**: Grep de docstring y llamada (`import_from_files(replace_existing=True)`); 23 líneas con el mismo patrón que 2.1.129 |
| `static/` (JS, CSS, XML), `i18n/`, `LICENSE`, `static/description/` | Fuera del bloque (C2). Librerías de terceros no abiertas por regla |
| Externos consultados parcialmente | `pns_ai_mcp/utils/session_download.py` (25-54, 404-546), `models/ai_execution_engine.py` (140-199, 602-606), `models/ai_agent_consumer.py` (entero), `models/ai_skill.py` (363-433, 645-673, 1590-1733), `models/mcp_user.py` (Grep), core 14 citado en cada punto |

## Preguntas abiertas

1. ¿Se acepta que cualquier usuario interno lea y modifique por RPC las sesiones, adjuntos y
   jobs de otros (sin record rules)? Prueba: dos usuarios internos, `search_read` y `write` sobre
   `chatboo.session` y `chatboo.async.request` ajenos, y descarga de un adjunto ajeno.
2. ¿Puede un interno sin carnet crear un job con `session_id` ajeno y ejecutar `spawn()` por
   `call_kw`? ¿Se escribe el turno en la sesión de la víctima y se factura?
3. ¿El cliente (C2) pinta como HTML el contenido de `messages`? Si sí, la escritura cruzada es XSS
   almacenado.
4. ¿Es explotable el CSRF de `/chatboo/stream` con `fetch(..., {mode:'no-cors', credentials:'include', body: JSON en text/plain})` desde otro origen en Firefox/Safari? ¿Responde 405 al *preflight*?
5. ¿Se debe restringir `provider_id` y `agent_code` del navegador a la cadena del agente Chatboo?
   (Decisión del fabricante; [SECR] §2.4.)
6. ¿Qué retención se quiere para sesiones de usuarios inactivos o archivados, sus adjuntos con
   token y los jobs con base64? ¿Hace falta un cron de retención? (Enlaza con [CONS] D13.)
7. ¿Quedan adjuntos huérfanos al borrar un usuario (cascada SQL) o al desinstalar el módulo?
8. ¿El mensaje del bus en 14 (cadena JSON) lo interpreta bien el cliente?
9. Con `workers>0` y `limit_time_real=120`, ¿un turno de más de 120 s mata el hilo y el *reclaim*
   lo recupera como "respuesta incompleta"?
10. ¿Carga el registro con `hr` instalado junto a Chatboo (`SELF_READABLE_FIELDS` como
    `property`)?
11. ¿Tras generar la API key aparece el menú Chatboo sin reiniciar (caché de `load_menus`)?
12. ¿Inyecta el sandbox `start_date`, `end_date`, `year`, `anio`, `lugar`, `fecha` siempre? Si
    no, `/annual-billing` falla con `NameError`.
13. ¿Se quiere limitar por grupo quién puede ejecutar `users-all`, `users-logged` y `sys-info`?
14. ¿Es intencionado que las BD migradas lleven `acl_security` en `default_context_codes` y las
    nuevas no?
15. ¿Deben conservarse los cambios de un administrador en los contextos y skills de fábrica, o es
    aceptable que cada `-u` los sobrescriba?
16. Rendimiento: tiempo de `/analisis-financiero` y `/customer-risk-analysis` con una copia de
    producción (decisión del usuario cargarla).
