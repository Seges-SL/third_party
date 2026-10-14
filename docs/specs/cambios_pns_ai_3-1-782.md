# Cambios de la versión nueva de los módulos `pns_*` (pns_ai_mcp 3.1.782)

Fase 1 (inventario, solo lectura) · 13/10/2026 · Diff `14.0-analisis-pns-ai..HEAD` (rama `14.0-pns-ai-3`).
Convenciones: **HECHO** (visto en código o en una herramienta), **INFERENCIA** (deducido; requiere prueba en el laboratorio).
Las líneas citadas son de la versión nueva salvo que se indique lo contrario.

## Resumen

- 459 archivos de los tres módulos cambiados (97 nuevos, 39 eliminados, 6 renombrados, 317 modificados; +32 000 / −21 000 líneas). El grueso está en `pns_ai_mcp` (341 archivos).
- **Bloqueante para el laboratorio: `pns_ai_mcp` y `pns_ai_chatboo` NO SE IMPORTAN** con la imagen `odoo-dev:14-lab_pns_ai` (Python 3.7.3). Causa: `pns_ai_mcp/controllers/mcp_decorators.py:169` cambia `Tuple[...]` por `tuple[...]` en una anotación que se evalúa al importar (requiere Python ≥ 3.9). Es la única incompatibilidad de sintaxis encontrada (análisis AST con gramática 3.7).
- Versiones siguen sin el formato `14.0.x.y.z` → **los scripts de `migrations/` siguen sin ejecutarse en 14** (21 scripts nuevos en `pns_ai_mcp`, 2 en `pns_ai_chatboo`). El fabricante lo reconoce y replica parte de esa lógica en `init()` (modelo `ai.schema.fossil`, `ai_agent.init`, `api_result_cache.init`); los renombrados de XML ID (pre-migrate 3.1.518/3.1.519) no se replican.
- Dependencias: `httpx` y `pydantic` salen de `external_dependencies` (ya no se importan); `mail` y `bus` pasan a llegar por `pns_base` (que ahora depende de `web` y `mail`).
- Seguridad, cambios de calado: reglas nuevas (`ai.safe.choice`, `ai.api.result.cache`, `chatboo.session`, `chatboo.async.request`); `session_file` pasa de `auth='public'` a `auth='user'`; `/chatboo/stream` recupera CSRF y pierde `cors='*'`; el log deja de ser editable por el administrador de IA; se quita la lectura de `ai.fetch.cache` a todos los internos.
- Funcionalidad nueva sensible: **PIN temporal para entregar la clave MCP a una app** (`ai.key.pin.*`, rutas `/pns_ai_mcp/key_pin/*`), con la clave en claro en un campo de BD durante unos segundos y un método público sin comprobación de grupo; **descarga de imágenes remotas por el servidor** (`/pns_ai_mcp/remote_image`); generador de especificaciones OpenAPI que descarga documentación; exportación con pregunta explícita por los secretos.
- Afecta a casi todos los hallazgos del informe: 78 de 80 tienen algún archivo citado modificado; PNS-68 solo indirectamente (su migración no cambia) y PNS-77 (Chatboo sin tests) sin cambios.

## Versiones

| Módulo | Anterior | Nueva | Adaptada por Odoo 14 |
|---|---|---|---|
| `pns_base` | 1.2.10 | 1.2.32 | `14.0.1.2.32` |
| `pns_ai_mcp` | 3.1.486 | 3.1.782 | `14.0.3.1.782` |
| `pns_ai_chatboo` | 2.1.322 | 2.1.453 | `14.0.2.1.453` |

Ninguno adopta `14.0.x.y.z`. Los tres manifiestos añaden el comentario «Odoo reads this file with ast.literal_eval». Licencia sin cambios (Apache-2.0, `Other OSI approved licence`).

## Dependencias y librerías

### `depends`

| Módulo | Anterior | Nueva | Cambio |
|---|---|---|---|
| `pns_base` | `base`, `web` | `web`, `mail` | **+`mail`** (arrastra `bus`). Necesario por el cron nuevo (`activity_user_type`, `data/export_purge_cron.xml`). |
| `pns_ai_mcp` | `base`, `web`, `mail`, `bus`, `pns_base` | `web`, `pns_base` | −`base`, −`mail`, −`bus` como directas; siguen llegando por `pns_base` → `mail` → `bus`. Usa `bus.bus` en `models/key_pin_desk.py:71`: dependencia transitiva, válida. |
| `pns_ai_chatboo` | `web`, `mail`, `bus`, `pns_base`, `pns_ai_mcp` | `web`, `bus`, `pns_base`, `pns_ai_mcp` | −`mail` (llega por `pns_base`). |

### `external_dependencies` (Python)

| Módulo | Anterior | Nueva |
|---|---|---|
| `pns_base` | — | — |
| `pns_ai_mcp` | `openpyxl`, `reportlab`, `requests`, `httpx`, `pydantic` | `openpyxl`, `reportlab`, `requests` (**−`httpx`, −`pydantic`**) |
| `pns_ai_chatboo` | `openpyxl` | `openpyxl` |

HECHO: ningún archivo de los tres módulos importa ya `httpx` ni `pydantic` (Grep). Las dos librerías que el laboratorio añadió en `infra/Dockerfile.14` por exigencia del manifiesto dejan de ser necesarias (no estorban).

### Librerías usadas y no declaradas (todas opcionales o ya en la imagen)

- `pns_base/utils/pdf_io.py` (nuevo): `PIL` (Pillow) y `PyPDF2` (vienen con Odoo 14); `pypdf` con caída a `PyPDF2` (`:45-50`, `:55-60`); `fitz` (PyMuPDF) opcional con `except ImportError` (`:200-203`, `:367-370`, `:417-421`); `pdftoppm` (poppler-utils) opcional por `shutil.which` (`:422`).
- `pns_ai_chatboo/models/chatboo_async_request.py`: `xlrd` (ya se usaba).
- `zoneinfo` (Python ≥ 3.9) en `pns_ai_mcp/utils/user_time.py:18`, `controllers/context_builder.py:359`, `pns_ai_chatboo/utils/chatboo_display_time.py:70`: con alternativa a `pytz`/`dateutil`; ya existía.

### Compatibilidad con Python 3.7 (imagen del laboratorio y de Odoo 14 oficial)

- **`pns_ai_mcp/controllers/mcp_decorators.py:169`**: `-> tuple[bool, Optional[str]]` en un archivo sin `from __future__ import annotations`. En la versión anterior era `Tuple[...]`. Rompe la importación de `pns_ai_mcp` y, por dependencia, de `pns_ai_chatboo` (ver Paridad). HECHO.
- `from __future__ import annotations` (Python ≥ 3.7): 65 archivos (50 en la versión anterior). Compatible con 3.7.
- Sin otra sintaxis posterior a 3.7 (AST con `feature_version=(3,7)` sobre todos los `.py`). HECHO.

### Librerías JS

- `pns_ai_mcp` deja de cargar en `web.assets_backend` `showdown.js`, `jspdf.umd.min.js` y `xlsx.full.min.js` (eliminados; también `showdown.min.js`). `pns_ai_chatboo` conserva sus propias copias de showdown y jsPDF (`views/assets.xml:17-20`) y elimina su `xlsx.full.min.js`. Ninguna referencia queda colgando (Grep).
- JS nuevos en `pns_base`: `pns_image_viewer.js`, `pns_layer.js`. En `pns_ai_mcp`: `ai_usage_chip_v14.js`, `skill_capture_wizard_v14.js`, `openapi_spec_generate_wizard_v14.js`, `external_server_usage_v14.js`, `mcp_log_usage_summary_v14.js`, `model_picker_dialog_v14.js`, `key_pin_desk_v14.js`. En `pns_ai_chatboo`: `chatboo_pdf_viewer.js`, `chatboo_row_marks.js`.

## Archivos por módulo

### `pns_base` (35 archivos; +1 686 / −338)

- **Nuevos (14):** `NOTICE`, `static/description/NOTICE`, `data/export_purge_cron.xml`, `models/base_language_install.py`, `models/export_secrets_wizard.py`, `models/ir_attachment.py`, `models/ir_groups_patch.py`, `static/src/css/pns_image_viewer.css`, `static/src/js/pns_image_viewer.js`, `static/src/js/pns_layer.js`, `utils/pdf_io.py`, `utils/thread_env.py`, `utils/version_gates.py`, `views/export_secrets_wizard_views.xml`.
- **Eliminados (2):** `utils/paths.py`, `i18n/ar_001.po`.
- **Modificados (19):** manifest, `__init__.py`, `i18n/es.po`, `models/` (6: `__init__`, `export_file_wizard`, `ir_module_module`, `ir_translation`, `ir_ui_view_patch`, `operation_report_wizard`), `security/ir.model.access.csv`, `static/` (3), `utils/` (5: `__init__`, `compat`, `portable_io`, `settings_io`, `ui_feedback`), `views/assets.xml`.

### `pns_ai_mcp` (341 archivos; +24 243 / −17 377)

- **Nuevos (72**, de ellos 21 scripts de migración y 2 `NOTICE`):
  - Controladores: `controllers/key_pin.py`, `controllers/remote_image.py`.
  - Modelos: `ai_schema_fossil.py`, `ai_skill_param_cache.py`, `ai_skill_param_line.py`, `key_pin_block.py`, `key_pin_desk.py`, `secret_native_export.py`.
  - Drivers LLM: `lib/llm/drivers/openrouter_driver.py`, `lib/llm/drivers/systemone_driver.py`. Servicio: `services/openapi_spec_generator.py`.
  - Asistentes: `wizard/ai_provider_catalogue_copy.py` (+vista), `wizard/openapi_spec_generate_wizard.py` (+vista).
  - Datos: `data/ai_agent_conversational.xml`, `data/ai_log_cron.xml`.
  - Utilidades (20): `ack_record_card`, `conversational`, `db_error_text`, `decision_choice`, `inference_audit`, `key_pin`, `model_catalogue`, `name_affinity`, `provider_fit`, `record_label`, `record_marks`, `remote_image`, `required_fields`, `schema_fossils`, `skill_trigger_match`, `slash_domain_codes`, `spoken_fields`, `turn_record_models`, `usage_display`.
  - Tests (5): `test_flow_legend`, `test_required_fields_live`, `test_server_identity_detection`, `test_set_skill_parameters`, `test_skill_capture_replace`.
  - Estáticos: 7 JS y 1 CSS (ver Dependencias).
- **Eliminados (32**, de ellos 9 scripts de migración):
  - Controladores (herramientas MCP retiradas): `tools_context_analytics.py`, `tools_i18n_audit.py`, `tools_memory.py`, `tools_system.py`, `write_verification.py`.
  - Modelo `models/ai_provider_usage_day.py` (modelo `ai.provider.usage.day`).
  - Datos: `data/ai_provider_data.xml` y `data/external_server_openapi_data.xml` (no estaban en el manifiesto anterior), `data/external_server_data.xml` (sí estaba). Entre los dos archivos de servidores había 5 registros `noupdate="1"`: 3 en `external_server_data.xml` y 2 en `external_server_openapi_data.xml` (ver «Migraciones», correcciones tras el laboratorio, punto 3).
  - Contextos de descubrimiento: `ai/contexts/discovery/discovery_{api_cdmon,api_sesame,geo}{,_es_ES}.json`.
  - Utilidades: `api_key_migration.py`, `mcp_resources.py`, `system_info.py`.
  - JS: `showdown.js`, `showdown.min.js`, `jspdf.umd.min.js`, `xlsx.full.min.js`. `i18n/ar_001.po`.
- **Renombrados (6):** `models/mcp_safe_operation.py` → `models/safe_operation.py`; `views/mcp_change_journal_views.xml` → `views/ai_change_journal_views.xml`; `views/mcp_log_views.xml` → `views/ai_log_views.xml`; `views/mcp_safe_operation_views.xml` → `views/safe_operation_views.xml`; `wizard/safe_operation_tools_wizard{,_views}.*` → `wizard/safe_tools_wizard{,_views}.*`.
- **Modificados (231)** por carpeta: `wizard/` 54, `utils/` 47, `tests/` 24, `models/` 21, `static/` 21, `controllers/` 15, `lib/` 13, `views/` 13, `ai/` 11, `data/` 4, `security/` 3, raíz 3, `i18n/` 2.
- **Modelos renombrados (31 transitorios)**: todos los `pns_ai_mcp.*` pasan a `ai.*` (por ejemplo `pns_ai_mcp.skill.capture.wizard` → `ai.skill.capture.wizard`, `pns_ai_mcp.safe.operation.tools.wizard` → `ai.safe.tools.wizard`). Sus ACL se reescriben con el mismo XML ID y el nuevo `model_id`.
- **Modelos nuevos:** persistentes `ai.key.pin.desk`, `ai.key.pin.ask`, `ai.key.pin.block`, `ai.skill.param.cache`, `ai.skill.param.line`; transitorios `ai.skill.capture.param.line`, `ai.provider.catalogue.copy`, `ai.openapi.spec.generate.wizard`; abstracto `ai.schema.fossil`. **Quitado:** `ai.provider.usage.day`.

### `pns_ai_chatboo` (83 archivos; +6 006 / −3 420)

- **Nuevos (11):** `NOTICE`, `static/description/NOTICE`, `data/ai_agent_conversational.xml`, `security/security.xml`, `static/src/css/chatboo_pdf_viewer.css`, `static/src/css/chatboo_row_marks.css`, `static/src/js/chatboo_pdf_viewer.js`, `static/src/js/chatboo_row_marks.js`, `utils/turn_documents.py`, `migrations/2.1.336/post-migrate.py`, `migrations/2.1.343/post-migrate.py`.
- **Eliminados (5):** `ai/skills/system/analisis_financiero.{md,py}`, `static/src/js/xlsx.full.min.js`, `i18n/ar.po`, `migrations/2.1.241/post-migrate.py`.
- **Modificados (67):** `ai/` 23, `static/` 19, `models/` 8, `utils/` 6, `data/` 3, `views/` 3, `controllers/` 2, raíz 2, `i18n/` 1.
- Sin modelos nuevos ni quitados. Sigue sin `tests/`.

## Cambios con impacto

### Modelos y campos nuevos en modelos existentes

| Modelo (archivo) | Campos añadidos | Campos quitados |
|---|---|---|
| `ai.mcp.user` (`models/mcp_user.py:142-148`) | `key_pin` (Char, indexado, **el PIN en claro**), `key_pin_used`, `key_pin_killed`, `key_pin_html`, `is_ai_conversational` | — |
| `ai.provider` (`models/ai_provider.py`) | 30 campos de capacidades y precio (`apt_*`, `fit_*`, `price_*_label`, `compose`, `maker`, `no_external_failover`, `active`…) | `agent_ids`, `agent_provider_ids`, `is_on_premise`, `painter`, `usage_day_ids` |
| `ai.log` (`models/ai_log.py`) | `agent_id`, `cost_usd`, `turn`, `turn_step`, campos de presentación | `correlation_id`, `step_seq`, `operation_code` |
| `ai.change.journal` | `turn`, `turn_step` | `correlation_id`, `step_seq` |
| `ai.safe.operation` (renombrado de archivo) | `turn` | `correlation_id` |
| `ai.skill` | `compose`, `param_cache_ids`, `param_line_ids` | `painter` |
| `ai.agent` | `is_agent_conversational`, `link_show_inserted`, `link_show_own` | `link_show_native`, `link_show_pinned` |
| `ai.api.server` / servidor externo (`models/external_server.py`) | `docs_url`, `openapi_gen_prompt` | — |
| `chatboo.session` | `attached_documents`, `last_domain_codes`, `marked_refs`, `pending_param_skill_id` | `llm_formatting_mode` |
| `ai.agent` (chatboo), `res.config.settings` (chatboo) | `chatboo_upload_max_mb`, `chatboo_download_max_mb`, `chatboo_history_retention_days` (+ formato XLSX en ajustes) | — |
| `res.users` (chatboo) | `chatboo_show_series_stats` | — |

Los renombres de columnas (`correlation_id` → `turn`, `step_seq` → `turn_step`, `painter` → `compose`) y el borrado de columnas obsoletas los hace `ai.schema.fossil.init()` en cada actualización (ver Migraciones).

### `ir.model.access.csv`

`pns_ai_mcp/security/ir.model.access.csv` (HECHO, diff):
- **Quitada** `access_ai_fetch_cache_user` (`ai.fetch.cache`, `base.group_user`, lectura): los internos ya no leen la caché de `fetch_url`.
- **`access_ai_log_admin`** pasa de `1,1,1,1` a `1,0,0,1`: el administrador de IA ya no puede escribir ni crear registros de log, solo leerlos y borrarlos.
- Nuevas: `ai.agent.provider` lectura para `base.group_user`; `ai.skill.param.cache` y `ai.skill.param.line` (lectura internos; CRUD writer y admin); `ai.skill.capture.param.line` (writer); `ai.provider.catalogue.copy`, `ai.openapi.spec.generate.wizard`, `ai.schema.fossil`, `ai.key.pin.block`, `ai.key.pin.desk`, `ai.key.pin.ask` (solo `group_ai_admin`).
- Quitadas las de `ai.provider.usage.day`. Las de los 31 asistentes renombrados se reescriben con el mismo grupo y permisos. `safe_operation_tools_wizard_user` sigue en `base.group_user` con `1,1,1,1` (ahora `ai.safe.tools.wizard`).
- Todas las líneas nuevas tienen `group_id`.

`pns_base/security/ir.model.access.csv:` nueva `access_pns_export_secrets_wizard` (`pns.export.secrets.wizard`, `base.group_user`, `1,1,1,1`). El asistente guarda `res_model`, `res_ids` y `method` (campos `readonly` solo en la vista) y ejecuta `records.<method>(include_secrets)` si el método empieza por `_pns_export_` (`models/export_secrets_wizard.py:46-55`). Los siete métodos `_pns_export_*` existentes comprueban `ensure_ai_admin` (`mcp_user.py:706-713`, `res_config_settings.py:204-206`, `external_server.py:1406-1413`, `ai_provider.py:1105-1113`). El control descansa en cada método, no en el asistente.

`pns_ai_chatboo`: sin cambios en el CSV.

### Record rules y grupos

- `pns_ai_mcp/security/security.xml` (`noupdate="0"`):
  - `:161` `ai_safe_choice_user_rule`: cada interno solo ve y modifica sus filas de `ai.safe.choice`.
  - `:173` `ai_api_result_cache_user_rule` (`create_uid = user`) y `:183` `ai_api_result_cache_admin_rule` (admin, todo).
  - `:69`, `:81`, `:93`, `:105`: reglas de `ai.log` y `ai.safe.operation` con XML ID nuevo (`mcp_*` → `ai_*`), mismo dominio.
- `pns_ai_chatboo/security/security.xml` (nuevo, `noupdate="0"`):
  - `:9` `chatboo_session_user_rule`: `chatboo.session` restringida a `user_id = user` (CRUD).
  - `:20` `chatboo_async_request_user_rule`: lectura y escritura de las propias; sin creación ni borrado por regla. Comentario `:4`: el proceso que recoge trabajos bloqueados usa `sudo()` y no pasa por estas reglas.
- `pns_ai_mcp/security/security_groups.xml:39`: **grupo nuevo `group_ai_conversational`** («diálogo abierto»; no lo implica el administrador de IA), con `implied_ids` `base.group_user`. Se asigna desde `ai.mcp.user.is_ai_conversational` (`models/mcp_user.py:310-318`).
- `pns_base/models/ir_groups_patch.py` (nuevo): reescritura de `res.groups` en carga solo para Odoo 19 (`category_id` → `privilege_id`); en 14 no cambia los valores. INFERENCIA por el código de `version_gates`.

### Rutas HTTP

| Ruta | Antes | Ahora | Archivo |
|---|---|---|---|
| `/pns_ai_mcp/session_file/<id>` (+ variante con `<filename>`) | `auth='public'` | **`auth='user'`**; lee el adjunto con `sudo()` y filtra con `_may_read` | `controllers/session_file.py:37-44` |
| `/chatboo/stream` | `auth='user'`, `csrf=False`, `cors='*'` | `auth='user'`, **CSRF por defecto** (el cliente envía `csrf_token` por query, `chatboo_component_v2.js:2564-2566`), sin `cors` | `pns_ai_chatboo/controllers/chatboo.py:717` |
| `/chatboo/edit-skill` (nueva) | — | `auth='user'`, JSON; comprueba `_user_may_use_chatboo` | `pns_ai_chatboo/controllers/chatboo.py:641` |
| `/pns_ai_mcp/key_pin/desk` (nueva) | — | `auth='user'`, JSON; solo admin de IA o superusuario (`_admin`, `:12-16`) | `controllers/key_pin.py:21` |
| `/pns_ai_mcp/key_pin/supply` (nueva) | — | `auth='user'`, JSON; ídem | `controllers/key_pin.py:28` |
| `/pns_ai_mcp/key_pin/stop` (nueva) | — | `auth='user'`, `POST`, **`csrf=False`**; ídem; cierra una «mesa» por token | `controllers/key_pin.py:35-54` |
| `/pns_ai_mcp/remote_image` (nueva) | — | `auth='user'`, `GET`; el servidor descarga una imagen externa | `controllers/remote_image.py:24` |

No hay otras rutas añadidas ni quitadas (comparación automática de los 43 → 48 decoradores `@http.route`). Los controladores eliminados (`tools_*.py`, `write_verification.py`) no declaraban rutas: eran herramientas MCP.

### PIN temporal de clave (funcionalidad nueva, `pns_ai_mcp`)

Comportamiento (HECHO salvo indicación):
- El administrador de IA genera un PIN numérico (8 dígitos por defecto, 4-12; `utils/key_pin.py:11-16`) para un usuario MCP; se guarda **en claro** en `ai.mcp.user.key_pin` (`models/mcp_user.py:142`, `:800-817`, `secrets.choice`).
- Una pestaña del administrador abierta en la lista de usuarios actúa de «mesa» (`ai.key.pin.desk`, caducidad 45 s) y mantiene en el navegador la lista de claves en claro.
- `ai.mcp.user.redeem_key_pin(raw, ip)` (`models/mcp_user.py:819-860`) busca el PIN, crea un `ai.key.pin.ask` y espera hasta 20 s (`models/key_pin_desk.py:171-192`, bucle con `time.sleep(0.4)` y cursores nuevos) a que la pestaña devuelva la clave por `/key_pin/supply`. La clave se comprueba contra el hash (`:231`) y se guarda **en claro en `ai.key.pin.ask.supplied_key`** (`:161`, `:238`) hasta que la recoge el que espera, que borra la fila (`:209-212`); filas de más de 2 minutos se borran (`:165-169`).
- Contador de fallos por IP (`ai.key.pin.block`, 100 intentos y 1 h por defecto; `models/key_pin_block.py:36-66`). **Si `ip` llega vacía, ni se bloquea ni se cuenta** (`:38-40`, `:49-51`).
- `redeem_key_pin` es un método público `@api.model` **sin comprobación de grupo** y no tiene llamador en estos tres módulos (INFERENCIA: lo usa otra app o módulo del fabricante). En Odoo 14 cualquier usuario autenticado puede invocar por RPC un método público de un modelo aunque no tenga ACL sobre él; dentro todo va en `sudo()`. Requiere comprobación en la fase 2/3.
- `touch()` devuelve a la pestaña el email y el login de todas las peticiones pendientes (`models/key_pin_desk.py:111-122`); el bus notifica a todos los administradores de IA (`:50-58`).
- Parámetros nuevos: `pns_ai_mcp.key_pin_length`, `.key_pin_attempts`, `.key_pin_block_hours` (ajustes, `models/res_config_settings.py`); el botón de ajustes libera todos los bloqueos (`:349`).

### Uso de `sudo()`

Recuento de `.sudo(` en Python: `pns_base` 4 → 9, `pns_ai_mcp` 237 → 298, `pns_ai_chatboo` 20 → 26 (109 líneas añadidas con `sudo()` en el diff). Puntos nuevos relevantes:
- `pns_ai_mcp/models/key_pin_desk.py` (todas las operaciones, más cursores con `SUPERUSER_ID` en `:176-177`, `:201-202`).
- `pns_ai_mcp/models/mcp_user.py:830-851` (`redeem_key_pin`).
- `pns_ai_mcp/controllers/session_file.py:43` (lectura del adjunto antes del filtro `_may_read`).
- `pns_ai_mcp/services/openapi_spec_generator.py:588` (lista blanca).
- `pns_base/models/ir_attachment.py:25,35` (cron de purga).
- `pns_ai_mcp/models/ai_agent.py:238-275` (sellos de fábrica en `init`).
El detalle por hallazgo corresponde a la fase 2.

### Crons

| Cron | Archivo | Comportamiento |
|---|---|---|
| `ir_cron_pns_export_purge` (nuevo) | `pns_base/data/export_purge_cron.xml` (`noupdate="1"`, cada hora, `numbercall=-1`) | Borra adjuntos marcados como exportación (`description = EXPORT_MARK`) con más de `pns_base.export_retention_hours` (24 h; 0 = no borrar). `pns_base/models/ir_attachment.py:22-43`. |
| `ir_cron_ai_log_retention` (nuevo) | `pns_ai_mcp/data/ai_log_cron.xml` (`noupdate="1"`, diario, `numbercall=-1`) | Purga `ai.log` con más de `pns_ai_mcp.log_retention_days` (30 días; 0 = no purgar). |
| `ir_cron_ai_api_result_cache_gc` (corregido) | `pns_ai_mcp/data/api_result_cache_cron.xml:13` | Añade `numbercall=-1` y `doall=False`. Como el archivo es `noupdate`, `ai.api.result.cache.init()` reactiva el registro existente por SQL en cada actualización (`models/api_result_cache.py:51-80`). |

### Parámetros del sistema

- Nuevos: `pns_base.export_retention_hours`, `pns_ai_mcp.log_retention_days`, `pns_ai_mcp.key_pin_length`, `pns_ai_mcp.key_pin_attempts`, `pns_ai_mcp.key_pin_block_hours`, `pns_ai_chatboo.upload_max_bytes`, `pns_ai_chatboo.xlsx_float_decimals`, `pns_ai_chatboo.xlsx_thousands`; sellos de un solo uso `pns_ai_mcp.admin_auto_link_fossil_cleared`, `pns_ai_mcp.fossil_acl_security_agent`.
- Retirados del código: `pns_ai_mcp.ai_agent_mcp`, `pns_ai_chatboo.ai_agent_chatboo`, `pns_ai_mcp.external_server_cdmon`, `chatboo.action`.

### Servicios externos

- **`/pns_ai_mcp/remote_image`** (`utils/remote_image.py:24-68`): el servidor descarga la imagen; cada salto (máx. 3 redirecciones) exige http(s), host permitido por `ai.url.whitelist.may_show_remote_image` (entrada `web` o **política abierta**, `models/url_whitelist.py:168-176`) y host público (`non_public_host_error`); 8 MB máx.; se re-codifica como JPEG/PNG de 1024 px máx. con cabeceras `nosniff` y `CSP default-src 'none'`. Lo puede pedir cualquier interno.
- **Generador OpenAPI** (`services/openapi_spec_generator.py:579-610`, asistente solo admin): exige que el host de la documentación esté en la lista blanca `web`, pero `requests.get` sigue redirecciones por defecto y no aplica `non_public_host_error`. HECHO en código; impacto a valorar en fase 2.
- Drivers LLM nuevos: `openrouter_driver.py` y `systemone_driver.py` (protocolo «elección cerrada», `urllib.request.urlopen`, `:96`). `promote_decision_provider` convierte proveedores `protocol='decision'` en `systemone` (`utils/schema_fossils.py:150-194`).
- Datos de fábrica retirados: proveedores y servidores externos preconfigurados (cdmon, Sesame, OVH Kepler, OpenRouter, Brave). En BD existentes, los 5 servidores de fábrica (`mcp_test`, `brave_search` y `sequential_thinking` de `external_server_data.xml`; `sesame` y `cdmon` de `external_server_openapi_data.xml`) eran `noupdate="1"`: **Odoo no los borra** al desaparecer los archivos (`_process_end` solo borra XML ID sin `noupdate`; confirmado en la fase 3a, ver «Migraciones»).
- Herramientas MCP retiradas: `tools_system` (información del sistema), `tools_memory`, `tools_i18n_audit`, `tools_context_analytics`.

### Almacenamiento de claves y exportaciones

- `_pns_secret_fields` declarados: `ai.api.server.key.token` (`models/api_server_key.py:31`), servidor externo `auth_token`, `env_vars`, `config_json` (`models/external_server.py:83`), `ai.mcp.user.mcp_api_key_hash` (`models/mcp_user.py:77`), `ai.provider.api_key` (`models/ai_provider.py:155`).
- `models/secret_native_export.py` (nuevo): sobrescribe `base.export_data` para vaciar las columnas que acaban en un campo secreto, también a través de relaciones (`:28-42`). Afecta a la exportación estándar de **todos** los modelos (coste: recorre las rutas exportadas).
- Exportaciones portables: preguntan si incluir secretos (`pns.export.secrets.wizard`); los archivos generados se borran a las 24 h (cron de `pns_base`).
- `utils/api_key_migration.py` (migración de claves en claro) eliminado.
- Caché de `api_call`: la clave incluye ahora el usuario (`models/api_result_cache.py:83-84`, `uid=self.env.uid`).
- PIN de clave: ver apartado propio (PIN y clave en claro en campos de BD).

### Otros cambios con efecto en datos

- `pns_base/models/ir_module_module.py`: deja de reescribir el `website` de todos los módulos; solo incrusta el índice local cuando el manifiesto del propio módulo apunta a él, en un marco con `sandbox`. En BD donde la versión anterior ya reescribió `website`, el valor vuelve al del manifiesto al actualizar la lista de aplicaciones (INFERENCIA).
- `pns_ai_mcp/models/ai_agent.py:215-275` (`init`, en cada `-u`): desactiva enlaces automáticos de proveedores en el agente AI Admin (una vez), sincroniza `is_agent_conversational` con la semilla y quita `acl_security` del agente `pns_ai_mcp` (una vez).
- `pns_ai_mcp/models/ai_log.py`: cron de retención (30 días) → **se borrarán logs antiguos** en la primera ejecución tras actualizar.

## Migraciones

### Carpetas

| Módulo | Anterior | Nueva | Añadidas | Quitadas |
|---|---|---|---|---|
| `pns_base` | — | — | — | — |
| `pns_ai_mcp` | 68 scripts (`3.1.47`…`3.1.484`) | 80 carpetas (`3.1.47`…`3.1.643`) | 21 scripts en 18 carpetas: `3.1.496-499`, `.517`, `.518` (pre y post), `.519` (pre), `.533`, `.546`, `.547`, `.548` (pre), `.553` (pre), `.554`, `.555` (pre y post), `.597`, `.606`, `.636` (pre), `.642`, `.643` | 9: `3.1.135`, `.142`, `.239`, `.376`, `.379`, `.380`, `.381`, `.448`, `.451` |
| `pns_ai_chatboo` | 33 carpetas (`2.1.33`…`2.1.301`) | 33 carpetas | `2.1.336`, `2.1.343` | `2.1.241` |

Contenido de las nuevas (docstring): refresco del `system_prompt` de fábrica (496-499, 533); renombrado de XML ID `mcp_*` → `ai_*` de reglas, accesos, menús, acciones y vistas de `ai.safe.operation`, `ai.log`, `ai.context`, `ai.change.journal` (518 pre, 519 pre); borrado de tablas de asistentes renombrados (517, 518, 547, 548, 553, 554, 555); filas de detección de servidores (546); `openapi_gen_prompt` por defecto (597, 606); renombrado de columnas `correlation_id`/`step_seq` (636 pre); borrado de columnas obsoletas (642, 643). Chatboo: refresco de paquetes de host (336) y borrado de la skill retirada `analisis-financiero` (343, filtra por skills de fábrica sin dueño vía `unlink_named_factory_skills`, `pns_ai_mcp/models/ai_skill.py:2184-2212`).

### ¿Se ejecutarán en Odoo 14?

**No.** HECHO por el código del core (`odoo/modules/migration.py:108-111,145-161`, `odoo/modules/module.py:441-445`):
- La versión instalada y la del manifiesto se guardan como `14.0.3.1.x` / `14.0.2.1.x`.
- Una carpeta con dos puntos (`3.1.636`) se considera «con serie» y se compara tal cual: `14.0.3.1.486 < 3.1.636` es falso. Ningún script `3.1.*` ni `2.1.*` entra.
- Solo se ejecutarían carpetas `0.0.0` o con un único punto; no hay ninguna.

El fabricante lo reconoce explícitamente (`pns_ai_mcp/utils/schema_fossils.py:6-10`, `models/ai_agent.py:216`, `migrations/3.1.606/post-migrate.py`) y replica una parte en `init()` (se ejecuta en cada `-u`):

| Tarea de migración | ¿Replicada en 14? | Dónde |
|---|---|---|
| Borrar tablas de asistentes renombrados y recetas (517-518, 547-548, 553-555) | Sí, en parte (ver «Correcciones tras el laboratorio», 1 y 2) | `models/ai_schema_fossil.py:25-31` (`DROP TABLE IF EXISTS … CASCADE` de 12 tablas fijas; protege `ai_safe_choice` y `ai_change_journal`). Entre ellas está `ai_provider_usage_day`, que son datos. |
| `painter` → `compose` | Sí | `utils/schema_fossils.py:65-89` |
| `correlation_id`/`step_seq` → `turn`/`turn_step` (636) | Sí | `utils/schema_fossils.py:135-141` |
| Columnas obsoletas (642, 643) | Sí | `utils/schema_fossils.py:44-53,197-200` |
| Proveedor `decision` → `systemone` | Sí | `utils/schema_fossils.py:150-194` |
| Cron de caché sin `numbercall` | Sí | `models/api_result_cache.py:51-80` |
| `openapi_gen_prompt` (597, 606) | Sí, según el docstring de 606 (`ai.api.server.init()`) | no verificado |
| **Renombrado de XML ID `mcp_*` → `ai_*` (518 pre, 519 pre)** | **No** (Grep sin resultados fuera de `migrations/`) | — |
| Refresco de `system_prompt` (496-499, 533) | No como migración; INFERENCIA: lo cubre la sincronización de fábrica | — |
| Chatboo 2.1.336 / 2.1.343 | No (no hay equivalente fuera de `migrations/`) | — |

Consecuencia esperada de los XML ID sin renombrar (INFERENCIA, verificar en la fase 3): al actualizar se crean registros nuevos `ai_*` (reglas, accesos, menús, acciones, vistas) y, al final, `_process_end` borra los `mcp_*` que ya no están en los datos (están en bloques `noupdate="0"`). El resultado debería ser equivalente, salvo que el borrado falle (por ejemplo, una vista heredada de otro módulo que apunte a una vista `mcp_*`) o haya personalizaciones sobre esos registros, que se perderían. La skill retirada `analisis_financiero` de Chatboo probablemente queda en BD actualizadas.

En la fase 3, buscar en el log de `actualizar`: `Running migration` (esperado: 0), `pns_ai_mcp: DROP leftover` y errores de `_process_end` / `unlink` de XML ID `mcp_*`.

### Correcciones tras el laboratorio (fase 3a, 2026-10-14)

Resultado completo en `docs/pendiente/verificacion_seguridad_pns_ai.md`, sección «Versión 3.1.782 —
actualización en el laboratorio (fase 3a)». Se confirma lo anterior: no se ejecuta ningún script de
migración, el renombrado de XML ID no se replica (se crean 38 `ai_*` nuevos y se borran los 38 `mcp_*`
sin errores), el cron de caché recupera `numbercall` y la skill `analisis-financiero` se borra (no
queda, contra lo que se infería arriba). Hay que corregir cuatro puntos:

1. **`ai_provider_usage_day` son datos, no un asistente.** Entre las 12 tablas que borra
   `ai.schema.fossil` está el histórico diario de tokens, coste y peticiones por proveedor (modelo
   `ai.provider.usage.day` de 3.1.486; `utils/schema_fossils.py:27`). Ninguna migración ni `init()` lo
   traslada, así que **se pierde en la primera actualización**. Si interesa conservarlo, hay que
   exportarlo antes. Recogido en PNS-87 del seguimiento.
2. **Los asistentes renombrados se borran solo en parte.** De los 31 modelos que Odoo da de baja, el
   fósil borra la tabla de 2 (`pns_ai_mcp_skill_capture_wizard` y `ai_provider_usage_day`), además de 7
   tablas de relación y 3 restos de `relaxaicode` sin modelo. Quedan **30 tablas huérfanas**
   `pns_ai_mcp_*` (29 de asistentes y una de relación), sin impacto funcional.
3. **Servidores de fábrica: son 5 en dos archivos**, no «los 3 de `external_server_data.xml`»:
   `external_server_mcp_test`, `external_server_brave_search` y `external_server_sequential_thinking`
   (de `data/external_server_data.xml`), y `external_server_sesame` y `external_server_cdmon` (de
   `data/external_server_openapi_data.xml`). Ambos archivos desaparecen en la versión nueva; los 5
   registros son `noupdate="1"`, siguen inactivos y Odoo no los borra (PNS-88).
4. **No estaba inventariada la retención de Chatboo.** `pns_ai_chatboo` crea el parámetro
   `pns_ai_chatboo.history_retention_days` (30 días; registro `icp_chatboo_history_retention_days` de
   `data/chatboo_icp_data.xml`, `noupdate="1"`, nuevo en esta versión). El cron de mantenimiento, cada 5
   minutos, llama a `chatboo.session._cleanup_old_sessions`
   (`pns_ai_chatboo/models/chatboo_session.py:1360-1382`), que borra en `sudo` las sesiones de **todos**
   los usuarios con más días que la retención. Antes solo se purgaban las del usuario que volvía al chat.
   Es la corrección de PNS-63; ver allí la nota operativa para la actualización.

## Paridad

Comando: `odoo-dev 14 paridad pns_base,pns_ai_mcp,pns_ai_chatboo` desde `~/GitHub/lab_pns_ai` (solo lectura; 13/10/2026). Imagen `odoo-dev:14-lab_pns_ai`, BD `lab_pns_ai_14`, `third_party` montado como compartido.

```
módulos instalados: 27 · versión igual: 24 · versión distinta: 3 · sin código: 0 · no se importan: 2
NO SE IMPORTA  pns_ai_chatboo: TypeError: 'type' object is not subscriptable
NO SE IMPORTA  pns_ai_mcp: TypeError: 'type' object is not subscriptable
VERSIÓN        pns_ai_chatboo: BD 14.0.2.1.322 · código 14.0.2.1.453
VERSIÓN        pns_ai_mcp: BD 14.0.3.1.486 · código 14.0.3.1.782
VERSIÓN        pns_base: BD 14.0.1.2.10 · código 14.0.1.2.32
RESULTADO: el entorno NO puede cargar esta BD tal cual.
ya instalados en la BD: pns_base, pns_ai_mcp, pns_ai_chatboo → no hay nada por instalar; para aplicar cambios, 'actualizar'.
```

Interpretación:
- **No se importan** `pns_ai_mcp` ni `pns_ai_chatboo` (este último porque importa el primero). Causa (HECHO): `pns_ai_mcp/controllers/mcp_decorators.py:169`, anotación `tuple[bool, Optional[str]]` evaluada al importar con Python 3.7.3 (la imagen oficial de Odoo 14 usa Debian Buster y Python 3.7). **No se arregla con librerías ni con el Dockerfile**: es un error del código del fabricante. Hasta que lo corrija, ni el laboratorio ni ningún cliente con Odoo 14 sobre Python < 3.9 puede actualizar estos módulos, y tras sustituir el código Odoo no cargaría la BD (`pns_ai_mcp` instalado y sin importar).
- **Librerías**: ninguna librería nueva falta en la imagen; `httpx` y `pydantic` sobran pero no estorban.
- **Sin código**: ninguno.
- **Versiones distintas** BD/código: las tres, lo esperado antes de `actualizar`.
- La comprobación se detiene en el primer error de importación, así que pueden existir errores posteriores en tiempo de importación que este informe no detecta (el análisis AST no encontró más incompatibilidades de sintaxis).

## PNS afectados

Archivos citados en el informe que cambian en esta versión (M = modificado, D = eliminado, R = renombrado, A = nuevo relacionado). Solo identificación; el estado de cada hallazgo es de la fase 2.

| PNS | Archivos tocados |
|---|---|
| PNS-01 | `pns_ai_mcp/models/ai_system_action.py` (M), `security/ir.model.access.csv` (M), `pns_base/utils/compat.py` (M) |
| PNS-02 | `models/ai_system_action.py` (M) |
| PNS-03 | `models/mcp_safe_operation.py` (R → `models/safe_operation.py`), `security/security.xml` (M), `security/ir.model.access.csv` (M) |
| PNS-04 | `controllers/verification_ui.py` (M), `models/safe_operation.py` (R) |
| PNS-05 | `controllers/safe_plan.py` (M), `models/safe_operation.py` (R) |
| PNS-06 | `controllers/validators.py` (M), `models/ai_skill.py` (M), `security/ir.model.access.csv` (M) |
| PNS-07 | `controllers/context_builder.py` (M), `controllers/validators.py` (M), `models/safe_operation.py` (R) |
| PNS-08 | `models/external_server.py` (M), `security/ir.model.access.csv` (M) |
| PNS-09 | `lib/api/drivers/mcp_driver.py` (M), `models/external_server.py` (M), `utils/mcp_client.py` (M) |
| PNS-10 | `models/ai_context.py` (M), `models/ai_skill.py` (M) |
| PNS-11 | `models/ai_context.py` (M), `models/ai_skill.py` (M), `security/ir.model.access.csv` (M) |
| PNS-12 | `controllers/main.py` (M), `models/ai_context.py` (M), `utils/agent_engine.py` (M) |
| PNS-13 | `controllers/main.py` (M), `utils/session_store.py` (M) |
| PNS-14 | `security/ir.model.access.csv` (M), `security/security.xml` (M, reglas nuevas), `utils/api_call_result.py` (M), `models/api_result_cache.py` (M) |
| PNS-15 | `static/src/js/pns_html_readonly_widget_v14.js` (M), `static/src/js/showdown.js` (D), `utils/relaxaicode_render.py` (M), `wizard/context_stats_wizard.py` (M), `pns_base/models/operation_report_wizard.py` (M) |
| PNS-16 | `controllers/safe_plan.py` (M), `models/url_whitelist.py` (M), `utils/agent_engine.py` (M) |
| PNS-17 | `controllers/safe_plan.py` (M), `utils/fetch_url_safe.py` (M) |
| PNS-18 | `controllers/tools_relaxaicode.py` (M), `utils/agent_engine.py` (M), `utils/llm_usage.py` (M) |
| PNS-19 | `controllers/context_builder.py` (M) |
| PNS-20 | `models/res_config_settings.py` (M), `utils/config_backup.py` (M), `pns_base/utils/portable_io.py` (M), `pns_base/utils/settings_io.py` (M) |
| PNS-21 | `controllers/session_file.py` (M, `auth` cambia), `utils/session_download.py` (M) |
| PNS-22 | `controllers/main.py` (M), `controllers/tools_system.py` (D), `utils/agent_engine.py` (M) |
| PNS-23 | `models/ai_skill.py` (M), `wizard/skill_capture_wizard.py` (M) |
| PNS-24 | `models/ai_system_action.py` (M) |
| PNS-25 | `utils/agent_engine.py` (M) |
| PNS-26 | `controllers/main.py` (M), `models/safe_operation.py` (R) |
| PNS-27 | `static/src/js/jspdf.umd.min.js` (D), `static/src/js/xlsx.full.min.js` (D), `views/assets.xml` / manifest (M) |
| PNS-28 | `controllers/main.py` (M) |
| PNS-29 | `utils/agent_engine.py` (M) |
| PNS-30 | `models/ai_log.py` (M), `security/ir.model.access.csv` (M) |
| PNS-31 | `static/src/js/ai_agent_origin_filter_v14.js` (M), `static/src/js/mcp_log_form_v14.js` (M); `http_patch.py` y `models/ir_model_fields_selection.py` sin cambios |
| PNS-32 | `hooks.py` (M), `models/ai_context.py` (M) |
| PNS-33 | `controllers/main.py` (M); `utils/api_key.py` sin cambios; PIN de clave nuevo (A) relacionado |
| PNS-34 | `tests/_helpers.py` (M), `tests/test_safe_plan_atomicity.py` (M), `tests/test_system_action.py` (M) |
| PNS-35 | `controllers/formatters.py` (M), `utils/artifact_export.py` (M) |
| PNS-36 | `controllers/tools_system.py` (D), `utils/system_info.py` (D) |
| PNS-37 | `models/ai_change_journal.py` (M); `utils/change_journal.py` sin cambios |
| PNS-38 | `ai/contexts/core/system_prompt.xml` (M), `ai/contexts/discovery/*` (D) |
| PNS-39 | `controllers/main.py` (M) |
| PNS-40 | `utils/agent_engine.py` (M) |
| PNS-41 | `pns_base/models/ir_module_module.py` (M), `pns_base/static/src/js/pns_module_index.js` (M) |
| PNS-42 | Manifest, `ai/contexts/core/system_prompt.xml`, `controllers/__init__.py`, `controllers/main.py`, `controllers/mcp_decorators.py`, `controllers/validators.py`, `data/api_result_cache_cron.xml`, `models/ai_agent.py`; `pns_base/models/ir_module_module.py`, `ir_translation.py`, `static/src/js/pns_invalid_fields_dedupe.js`, `utils/portable_io.py`, `utils/settings_io.py` (todos M) |
| PNS-43 | `pns_base/models/ir_translation.py` (M) |
| PNS-44 | `pns_base/models/ir_module_module.py` (M) |
| PNS-45 | `controllers/__init__.py` (M) |
| PNS-46 | `models/ai_agent.py` (M) |
| PNS-47 | `models/ai_fx_source.py` (M) |
| PNS-48 | `views/ai_menus.xml` (M) |
| PNS-49 | `controllers/write_verification.py` (D), `utils/api_key_migration.py` (D), `static/src/js/showdown.min.js` (D), `controllers/moe_controller.py` (M) |
| PNS-50 | `tests/__init__.py` (M), 5 tests nuevos (A) |
| PNS-51 | `controllers/validators.py` (M) |
| PNS-52 | `pns_base/utils/settings_io.py` (M), `pns_base/utils/portable_io.py` (M) |
| PNS-53 | `pns_ai_chatboo/static/src/js/chatboo_component_v2.js` (M), `pns_ai_chatboo/security/security.xml` (A) |
| PNS-54 | `controllers/verification_ui.py` (M) |
| PNS-55 | `pns_ai_chatboo/models/chatboo_async_request.py` (M), `models/chatboo_session.py` (M), `security/security.xml` (A) |
| PNS-56 | `pns_ai_chatboo/models/chatboo_async_request.py` (M) |
| PNS-57 | `pns_ai_chatboo/models/chatboo_async_request.py` (M), `security/security.xml` (A) |
| PNS-58 | `pns_ai_chatboo/controllers/chatboo.py` (M, CSRF y `cors`), `static/src/js/chatboo_component_v2.js` (M) |
| PNS-59 | `pns_ai_chatboo/static/src/js/chatboo_component_v2.js` (M), `chatboo_formatters.js` (M); `pns_ai_mcp/controllers/remote_image.py` (A) relacionado |
| PNS-60 | `pns_ai_mcp/controllers/safe_plan.py` (M) |
| PNS-61 | `pns_ai_chatboo/controllers/chatboo.py` (M), `pns_ai_mcp/models/ai_execution_engine.py` (M) |
| PNS-62 | `pns_ai_chatboo/models/chatboo_async_request.py` (M) |
| PNS-63 | `pns_ai_chatboo/models/chatboo_async_request.py` (M), `models/chatboo_session.py` (M) |
| PNS-64 | `pns_ai_chatboo/static/src/js/chatboo_tts.js` (M) |
| PNS-65 | `pns_ai_chatboo/controllers/chatboo.py` (M) |
| PNS-66 | `pns_ai_mcp/models/ai_skill.py` (M) |
| PNS-67 | `pns_ai_chatboo/ai/skills/system/customer_risk_analysis.py` (M), `analisis_financiero.{md,py}` (D) |
| PNS-68 | `migrations/2.1.296/post-migrate.py` sin cambios; `migrations/2.1.343` (A) y `pns_ai_mcp/models/ai_skill.py` (`unlink_named_factory_skills`) relacionados |
| PNS-69 | `pns_ai_chatboo/models/res_users.py` (M) |
| PNS-70 | `pns_ai_chatboo/controllers/chatboo.py`, `data/ai_agent_data.xml`, `models/res_users.py`, `views/assets.xml`, `static/src/js/chatboo_charts.js` (M) |
| PNS-71 | `pns_ai_chatboo/controllers/chatboo.py` (M) |
| PNS-72 | `pns_ai_chatboo/views/assets.xml` (M), `static/src/js/xlsx.full.min.js` (D) |
| PNS-73 | `pns_ai_chatboo/static/src/js/chatboo_systray.js` (M) |
| PNS-74 | `pns_ai_chatboo/static/src/js/chatboo_component_v2.js` (M), `chatboo_systray.js` (M) |
| PNS-75 | `pns_ai_chatboo/static/src/js/chatboo_export.js` (M) |
| PNS-76 | `pns_ai_chatboo/data/ai_agent_data.xml` (M); `models/ir_ui_menu.py` sin cambios; `pns_ai_mcp/models/ai_agent.py` (`_drop_acl_security_factory_fossil`) relacionado |
| PNS-77 | Sin cambios (Chatboo sigue sin `tests/`) |
| PNS-78 | `pns_ai_mcp/models/ai_agent.py` (M) |
| PNS-79 | `pns_ai_mcp/controllers/main.py` (M) |
| PNS-80 | `pns_ai_chatboo/models/chatboo_async_request.py` (M) |
| Informe §7.2 (migraciones) | `utils/schema_fossils.py` (A), `models/ai_schema_fossil.py` (A), `models/ai_agent.py` (M) |
| Informe §7.4 (cron sin `numbercall`) | `data/api_result_cache_cron.xml` (M), `models/api_result_cache.py` (M) |

Candidatos a hallazgo nuevo para la fase 2c (solo señalados aquí): importación rota en Python 3.7 (`mcp_decorators.py:169`); `redeem_key_pin` público sin grupo y sin contador si no hay IP; clave y PIN en claro en campos de BD; `/key_pin/stop` sin CSRF; XML ID renombrados sin migración en 14; descarga de documentación OpenAPI sin control de redirecciones ni de hosts no públicos; `export_data` sobrescrito para todos los modelos; purga de logs a 30 días activa por defecto.
