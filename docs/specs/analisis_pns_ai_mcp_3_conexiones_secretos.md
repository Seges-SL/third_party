# Análisis pns_ai_mcp — Bloque 3: conexiones y secretos (Odoo 14)

Rama `14.0-analisis-pns-ai`. Código de terceros (Patanegra Soft, Apache-2.0): **no se modifica ni se
diseña código**. Copia analizada: `/home/soporte/GitHub/third_party/pns_ai_mcp/` (no la de
`/opt/odoo-src/14.0/third_party`). Core verificado en `/opt/odoo-src/14.0/odoo/`.

Convenciones: **HECHO** (archivo:línea), **INFERENCIA** (deducción razonada, no comprobada en
ejecución), **PENDIENTE** (comprobar con `odoo-dev 14`). Rutas relativas a `pns_ai_mcp/` salvo que
se indique otra cosa.

Referencias a bloques previos (no se repiten aquí):
- Bloque 1 (`analisis_pns_ai_mcp_1_mapa.md`): tabla ACL completa (§ líneas 405-460), §4.5 riesgo 1
  (`auth_token` legible por usuarios internos), §4.5-4 / punto 954 (bypass
  `skip_hardcoded_restrictions`), §7.2 crons (`numbercall` ausente en la purga de `api_call`).
- Bloque 2 (`analisis_pns_ai_mcp_2_conocimiento.md`): §1.3 `ai.agent.provider` (campos y `create`),
  §4 propiedad/visibilidad y `skip_hardcoded_restrictions`.

---

## 1. Modelos: campos, métodos, overrides y `super`

### 1.1 `ai.provider.model` (`models/ai_provider.py:32-38`)
HECHO: `name` Char requerido, `provider_id` Many2one `ai.provider` `ondelete='cascade'`. Sin métodos.

### 1.2 `ai.provider` (`models/ai_provider.py:40-717`)
Campos (HECHO):

| Campo | Tipo | Parámetros | Línea |
|---|---|---|---|
| `name` | Char | required | 78 |
| `alias` | Char | etiqueta del selector de Chatboo | 79-84 |
| `protocol` | Selection | `openai`, `anthropic`; default `openai` | 85-91 |
| `endpoint` | Char | URL POST exacta; solo `strip()` al guardar | 92-97 |
| `endpoint_setup_guide` | Html compute, `sanitize=False` | plantilla por protocolo | 98-102, 301-319 |
| `api_key` | Char | **`groups="pns_ai_mcp.group_ai_admin"`**, en claro | 103-107 |
| `model_name` | Char related `model_id.name`, store | | 120-123 |
| `model_id` | Many2one `ai.provider.model` | dominio por proveedor | 124 |
| `available_model_ids` | One2many | | 125 |
| `temperature` | Float | default 0.7; constraint 0-2 | 128-136, 321-325 |
| `temperature_support`, `usage_support` | Selection unknown/yes/no | readonly, copy=False | 137-166 |
| `is_on_premise` | Boolean | coste 0 si el gateway no lo informa | 167-176 |
| `footmode`, `painter` | Selection | presentación Chatboo | 178-216 |
| `context_window` | Integer | default 32768 | 218-233 |
| `context_window_display`, `context_window_tokens` | Char compute | | 235-247, 267-289 |
| `usage_day_ids` | One2many `ai.provider.usage.day` | copy=False | 249-256 |
| `agent_provider_ids` | One2many `ai.agent.provider` | | 258-265 |
| `agent_ids` | Many2many compute | | 290-299 |

HECHO: no hay `active` ni `company_id` (configuración global, sin multicompañía).

Métodos (HECHO):
- `_api_key_for_inference` (109-117): devuelve `self.sudo().api_key`; privado (no RPC).
- `create` (`model_create_multi`, 327-332) y `write` (334-337): normalizan `endpoint`; llaman a
  `super` y devuelven su resultado.
- `_sanitize_endpoint` (339-342), `_derive_models_url` (344-371; helper no usado por
  `action_fetch_models`, que usa `driver.models_url`).
- `action_fetch_models` (373-442), `_onchange_model_id` (444-448), `_onchange_reset_temperature_support`
  (450-454), `_probe_temperature_support` (456-488), `test_connection` (490-571),
  `_mark_usage_support_yes` (573-594): ver §2.
- `action_export_providers` (596-652), `action_export_selected` (654-705),
  `action_import_providers` (707-717): ver §10.
- `safe_error_message` (21-25) fuerza ASCII en mensajes de error (se pierden tildes). HECHO.
- Duplicados inocuos: `_logger` definido dos veces (19, 30) e `import requests` tras la función (28).

### 1.3 `ai.provider.usage.day` (`models/ai_provider_usage_day.py`)
HECHO: `provider_id` (requerido, cascade, 20-27), `date` (28), `prompt_tokens`, `completion_tokens`,
`total_tokens`, `cost` (digits 16,8), `request_count` (29-33); `unique(provider_id, date)` (35-41).
Métodos: `increment_for_turn` (43-112, SQL directo en cursor propio; §9), `import_missing_days`
(114-147, solo crea fechas que faltan, `sudo`), `to_export_rows` (149-161). Sin overrides CRUD.

### 1.4 `ai.fx.source` (`models/ai_fx_source.py`)
HECHO: `name`, `url` (requerido; constraint `http(s)://`, 46-53), `sequence`, `active`, `fail_count`,
`last_success`, `last_fail`, `last_error` (28-44). Métodos `_mark_success`/`_mark_fail` (55-68,
`sudo().write`), `_fetch_rates` (70-81, `urllib.request`, timeout 4 s), `get_usd_fx` (83-154),
`_rates_from_odoo_currency` (156-187), `convert_usd` (189-192). Caché en ICP
`pns_ai_mcp.fx_usd_cache` (18). Ver §9.

### 1.5 `ai.mcp.user` (`models/mcp_user.py`)
Campos (HECHO): `user_id` (requerido, cascade, 76-82), `name`/`email`/`login` related store (85-104),
`mcp_api_key_hash` (111-118, readonly, index), `mcp_api_key_state` (120-129),
`mcp_api_key_generated_date` (131-135), banderas compute+inverse `is_mcp_manager`, `is_ai_writer`,
`is_ai_external_url`, `is_ai_external_api` (138-167, 206-285: añaden/quitan el usuario del grupo),
`last_mcp_client_label`/`_ip`/`_seen` (169-185).

Overrides (HECHO):
- `create` (297-320): impide duplicados por usuario y **descarta en silencio claves que no son
  campos**; llama a `super` con la lista filtrada.
- `write` (322-332): mismo filtrado; `super`.
- `_search` (518-522), `search` (537-540), `search_read` (542-545), `web_search_read` (529-535):
  llaman a `_maybe_ensure_all_users` y a `super`. `search_fetch` (524-527) **no existe en 14**
  (core: solo `_search` en `odoo/models.py:4527`; `web_search_read` en
  `odoo/addons/web/models/models.py:48`): código muerto e inocuo.
- `name_get` (482-490).
- INFERENCIA: con contexto `ensure_all_users`, `search` → `_search` ejecuta
  `ensure_all_users_have_record` dos veces y este hace un `search` por usuario (N+1, 348-352).

Métodos de clave: `_store_api_key_hash` (359-370), `_do_generate_mcp_api_key` (372-391),
`action_generate_mcp_api_key` (393-401), `set_mcp_api_key` (403-419), `generate_mcp_api_key` /
`clear_mcp_api_key` / `action_import_mcp_api_key` (421-480, abren el asistente). Ver §4.

### 1.6 `ai.api.server` (`models/external_server.py`)
Campos (HECHO): identidad `name`, `code` (único, 338-340), `active` (88-102); `api_type` mcp/openapi
(105-116); `server_type` sse/stdio (119-128); `url` (131-134); OpenAPI `spec_url`, `spec_manual`,
`base_url`, `spec_json` (137-169); autenticación `auth_type` none/api_key/bearer/custom_header
(170-175), **`auth_token`** (176-182, sin `groups`), `auth_header_name` (183-191),
`auth_call_preview` Html (192-197, no muestra el valor, 360-382); stdio **`command`**,
**`command_args`**, **`env_vars`** (200-213, sin `groups`); `timeout` (216-220); **`trusted`**
(221-233); **`config_json`** (236-242, sin `groups`); descubrimiento `tools_json`, `resources_json`,
`prompts_json`, `last_discovery`, contadores y HTML (245-296); `usage_guide` (299-307),
`detection_context_ids` (308-317), `notes`, `added_by` (318-324); `key_ids` One2many
`ai.api.server.key` (327-336).

Overrides (HECHO):
- `copy` (342-351): genera `code` libre; `super().copy(default)`.
- `create` (516-531): si llega `config_json`, rellena **solo los campos vacíos** con lo parseado;
  `super`; después `_sync_json_from_fields` y `_ensure_server_whitelisted`.
- `write` (533-559): `super` primero; si cambia `config_json` reescribe **todos** los campos
  parseados (incluido `auth_token`) con contexto `_syncing_json`; si cambian campos, regenera
  `config_json`; si cambian URL/activo, añade dominios a la lista blanca; si cambian
  `code`/`active`, sincroniza contextos de detección (561-586, `sudo` +
  `skip_hardcoded_restrictions`).

Resto de métodos: `_fields_to_json` / `_json_to_fields` (456-514), detección híbrida con LLM
(588-717), `_server_hostnames` (730-748), `_load_factory_spec_json` (750-788),
`_link_orphan_api_discovery` (790-821), `_ensure_server_whitelisted` (823-847), `_get_driver`
(851-855), `_resolve_auth_token` (857-872), `action_discover_tools` (874-922),
`_openapi_spec_dict` / `_auth_vals_from_openapi_catalog` / `action_discover_auth` (924-991),
`action_test_connection` (993-1007), `get_tools_list`, `get_tools_prompt_block`,
`get_active_servers_summary` (1009-1080, `sudo`), exportación/importación (1087-1186).

### 1.7 `ai.api.server.key` (`models/api_server_key.py`)
HECHO: `server_id` (requerido, cascade), `user_id` (default usuario actual), **`token`** (Char
requerido, en claro, sin `groups`), `active`, `notes`; `UNIQUE(server_id, user_id)` (37-69). Sin
métodos.

### 1.8 `ai.url.whitelist` (`models/url_whitelist.py`)
HECHO: `domain`, `kind` web/mcp/openapi, `active`, `valid_from`, `valid_until`, `notes`, `added_by`;
`UNIQUE(domain, kind)` (47-101). Métodos de consulta todos con `sudo` (103-270) y
exportación/importación (274-321). Ver §6.

### 1.9 `ai.fetch.cache` y `ai.api.result.cache`
HECHO: ver §6 (campos en `models/fetch_cache.py:32-52` y `models/api_result_cache.py:29-49`).

### 1.10 `ai.log` (`models/ai_log.py`)
HECHO: ver §7. Override: `display_name` almacenado (285-289) con `_rec_name='display_name'` (42).
PENDIENTE: comportamiento en 14 de redefinir `display_name` como compute almacenado.

### 1.11 `ai.change.journal` (`models/ai_change_journal.py`)
HECHO: ver §8. Override `unlink` (496-499): solo el superusuario borra; **no llama a `super` para el
resto** (lanza `UserError`).

---

## 2. Proveedores LLM

### 2.1 Protocolos y drivers
- HECHO: `protocol` admite `openai` y `anthropic` (`ai_provider.py:85-88`). El registro de drivers
  incluye además `ollama` (`lib/llm/drivers/__init__.py:9-11`), no seleccionable en el formulario.
- INFERENCIA (drivers no leídos, son de otro bloque): `auth_headers` envía `Authorization: Bearer`
  (OpenAI) o `x-api-key` (Anthropic).

### 2.2 "Fetch Models" (`action_fetch_models`, 373-442)
HECHO: `GET` a `driver.models_url(endpoint)` con la clave del proveedor, timeout 10 s; espera
`{"data":[{"id":…}]}`; crea los modelos nuevos, **borra los que ya no aparecen** (418-421) y si no
hay modelo seleccionado elige el primero. Si el modelo seleccionado desaparece, `model_id` queda
vacío por el `unlink` (INFERENCIA: `ondelete` por defecto `set null` en Many2one).
Errores: el cuerpo remoto completo va al `UserError` (`Remote Error %s: %s`, 399-401).
INFERENCIA: algunos gateways repiten parte de la clave en el mensaje de error; llegaría al navegador.
HECHO: la lectura `self.api_key` (380) está fuera del `try`; un usuario sin `group_ai_admin` que
llamara por RPC recibiría `AccessError` (core 14 `_fetch_field` → `check_field_access_rights`,
`odoo/models.py:3063-3067`).

### 2.3 "Test Connection" (`test_connection`, 490-571)
HECHO: envía un chat real ("Just say 'ok'…") con `temperature 0`; si no hay clave usa
`"dummy-key-for-local"` (505). Registra en `ai.log` el prompt y la **respuesta completa**
(527-541). Lanza la sonda de temperatura (solo Anthropic, 456-488) y clasifica si la respuesta trae
`usage` (553-560). Error: `_logger.error(..., exc_info=True)` y `UserError` ASCII (567-571).
Coste: cada prueba consume tokens y no se suma a `usage_day` (INFERENCIA: el contador lo alimenta
`agent_engine.py:4217`, no este método).
HECHO: `_onchange_model_id` (444-448) hace una petición de red al cambiar el modelo en el formulario
(solo Anthropic, timeout 8 s).

### 2.4 Cadena de proveedores por agente
HECHO (`models/ai_execution_engine.py`):
1. `provider_id` explícito desde la interfaz (171-174): **cualquier proveedor existente**, sin
   comprobar que pertenezca a la cadena del agente ni el grupo del usuario.
2. Enlaces `ai.agent.provider` activos ordenados por `(priority, id)` leídos con `sudo` (133-147,
   177-179).
3. Si no hay enlaces, todos los proveedores (`search([], order='id')`) con creación automática de
   enlaces (181-…).
4. `chat_completion` (533-…) prueba en orden; en cada salto registra `provider_failover` en
   `ai.log` con los 500 primeros caracteres del error (276-320, 562-566); un desbordamiento de
   contexto aborta sin failover (581-…).
5. La clave se lee con `_api_key_for_inference()` (265; también `utils/agent_engine.py:195, 2027`).
Campos del enlace: bloque 2 §1.3.

### 2.5 El `cr.commit()` de `ai_provider.py`
HECHO: `_mark_usage_support_yes` (573-594) abre **otro cursor** (`self.env.registry.cursor()`),
pone `lock_timeout = 2s`, hace `UPDATE ai_provider SET usage_support='yes'` por SQL y `cr.commit()`
(589). Es el commit de ese cursor auxiliar, no del de la petición. Se llama desde
`utils/agent_engine.py:4224`.

Por qué está (HECHO, comentario 574 y `ai_provider_usage_day.py:47-51`): el turno de Chatboo
mantiene una transacción REPEATABLE READ larga; escribir el proveedor en ella provocaba errores de
serialización (40001) que se mostraban como "MCP engine error".

Riesgos:
- HECHO: salta el ORM (sin `write_uid`, sin invalidar la caché del entorno actual, sin
  constraints ni seguimiento); el entorno de la petición sigue viendo `unknown` hasta la siguiente
  transacción.
- HECHO: el cambio queda confirmado aunque la transacción principal se deshaga (intencionado).
- INFERENCIA: si la transacción principal ya tiene bloqueada la fila (p. ej. escribió el
  proveedor antes), el UPDATE espera 2 s y falla en silencio (`_logger.debug`, 590-594); no hay
  interbloqueo indefinido gracias al `lock_timeout`.
- INFERENCIA: consume una conexión adicional del pool por llamada (solo mientras el valor sea
  `unknown`).
- HECHO: en tests, `registry.cursor()` devuelve `TestCursor` solo si el registro está en modo test
  (`odoo/modules/registry.py:698-706`); en `TransactionCase` normal es un cursor real que confirma
  fuera de la transacción del test. PENDIENTE: comprobar con `odoo-dev 14 tests`.
- El mismo patrón está en `ai_provider_usage_day.increment_for_turn` (89-111),
  `ai_log.create_log_entry` (573-664) y `ai_change_journal.record_failed_plan` (360-408).

---

## 3. Mapa de secretos

Leyenda RPC: "interno" = cualquier usuario con `base.group_user`. Exportar = botones JSON del propio
modelo, copia completa (`config_backup`) o bundle (`artifact_bundle`).

| # | Secreto | Dónde se guarda | Cifrado / hash | `groups` / ACL / regla | Quién lo lee por RPC | Exportaciones | Logs / errores / navegador |
|---|---|---|---|---|---|---|---|
| 1 | `ai.provider.api_key` | columna `ai_provider.api_key` (`ai_provider.py:103-107`) | **En claro** | `groups=group_ai_admin`; ACL lectura interno (CSV 11) | Solo AI admin (HECHO, core `models.py:3018,3067`). El motor lo lee con `sudo` (117) | Export propio: **siempre incluido**, sin opción (`ai_provider.py:611,666`). Copia completa desde Ajustes: **siempre con secretos** (`res_config_settings.py:172`). Bundle: solo si `include_secrets` (`config_backup.py:125-126, 361-362`) | Widget `password` (`views/ai_provider_views.xml:37`): el valor viaja al navegador del admin. No se escribe en `ai.log` (prompt de prueba sin clave, 533). Journal: redactado por nombre (`utils/change_journal.py:30-33`) |
| 2 | `ai.api.server.auth_token` | `ai_api_server.auth_token` (176-182) | **En claro** | **Sin `groups`**; ACL lectura interno (CSV 7) | **Cualquier usuario interno** (bloque 1 §4.5-1) | Export propio: **siempre** (`external_server.py:1087-1090`). Copia/bundle: vaciado si no hay secretos (`config_backup.py:188-189, 401-402`) | `password` en formulario (`external_server_views.xml:100`). Duplicado en claro en `config_json` (fila 3). Journal: redactado ("token") |
| 3 | `ai.api.server.config_json` | `ai_api_server.config_json` (236-242) | **En claro**; contiene `auth.token` (462-466) y `env` (481-482) | Sin `groups`; ACL lectura interno | Cualquier usuario interno | **No se vacía con `include_secrets=False`** (`config_backup.py:187-191, 400-404`): el token y las variables salen igualmente | Widget `ace` sin ocultar (`external_server_views.xml:149`). Journal: **no redactado** (nombre no coincide) |
| 4 | `ai.api.server.env_vars` | `ai_api_server.env_vars` (209-213) | En claro (JSON) | Sin `groups`; ACL lectura interno | Cualquier usuario interno | Vaciado sin secretos (`config_backup.py:190, 403`) | Se pasa al proceso hijo (`utils/mcp_client.py:145-151`). Texto plano en formulario (118-119). Journal: **no redactado** |
| 5 | `ai.api.server.command_args` | `ai_api_server.command_args` (204-208) | En claro | Sin `groups`; ACL lectura interno | Cualquier usuario interno | Siempre (no se considera secreto) | El comando completo aparece en el error de arranque (`utils/mcp_client.py:163-165`) → `UserError` al navegador (`external_server.py:886-887, 998-999`). INFERENCIA: si los argumentos llevan claves, se filtran |
| 6 | `ai.api.server.key.token` | `ai_api_server_key.token` (`api_server_key.py:53-58`) | **En claro** | Sin `groups`; ACL CRUD interno (CSV 8) con regla "solo las propias" (`security.xml:160-169`); admin todas (170-179) | Cada usuario las suyas; AI admin todas | No se exporta (One2many omitido, `pns_base/utils/portable_io.py:101`) | `password` en la pestaña del servidor (`external_server_views.xml:133`). Se resuelve con `sudo` (`external_server.py:865-871`). Ver fuga por caché (§6.3) |
| 7 | `ai.mcp.user.mcp_api_key_hash` | `ai_mcp_user.mcp_api_key_hash` (`mcp_user.py:111-118`) | SHA-256 **sin sal** (`utils/api_key.py:35-48`) | ACL solo AI admin (CSV 33) | AI admin | **Siempre**, aunque `include_secrets=False` (`config_backup.py:200-231, 413-441`); export propio vía `export_record_dict` (`mcp_user.py:600-605`) | Invisible en la vista (`mcp_user_views.xml:54`). Un hash exportado no permite autenticarse sin la clave original (INFERENCIA) |
| 8 | Clave MCP en claro recién generada / importada | `pns_ai_mcp_api_key_wizard.generated_key` y `manual_key` (`mcp_api_key_wizard.py:33-38, 61-64, 116`) | **En claro** en tabla transitoria | ACL solo AI admin (CSV 34) | AI admin, hasta el vaciado de transitorios (`transient_age_limit`, core `models.py:385, 6522-6524`; 1 h por defecto, INFERENCIA) | No | Se muestra una vez en el asistente |
| 9 | Clave MCP en tránsito | Cabeceras o **query `?api_key=`** (`controllers/main.py:443, 870`) | — | — | — | — | Prefijo de 10 caracteres en log INFO (`main.py:866, 872`). INFERENCIA: con `?api_key=` la URL completa queda en el log de acceso de werkzeug/proxy. HECHO: la sesión SSE conserva la clave en claro en memoria (`main.py:669`, `session.api_key`) |
| 10 | Copias exportadas | `ir.attachment` sin `res_model` (`pns_base/utils/portable_io.py:273-295`) | En claro (JSON/ZIP) | Core 14: adjuntos sin registro solo los lee su creador o sistema (`ir_attachment.py:434`) | Creador y administradores del sistema | — | HECHO (grep): ni `pns_base` ni `pns_ai_mcp` borran estos adjuntos; quedan en el filestore indefinidamente |
| 11 | Datos en `ai.log` | `prompt_data`, `result_data`, `user_prompt`, `code_to_execute` (`ai_log.py:214-255`) | En claro | Regla: cada usuario los suyos; admin todos (`security.xml:68-89`) | Usuario (propios), AI admin (todos) | Export de logs solo campos resumen (`ai_log.py:716-720`) | `execute_safe_plan` guarda pasos y resultados completos sin redactar (`mcp_safe_operation.py:1586-1591`): valores escritos (p. ej. un token) y cuerpos de `fetch_url`/`api_call` |
| 12 | Datos en `ai.change.journal` | `before_json`, `after_json` (`ai_change_journal.py:113-114`) | En claro, redacción por nombre de campo | ACL admin y sistema 1,1,1,0 (CSV 36-37) | AI admin y sistema | No | `intended_values` de planes fallidos **sin redactar** (`ai_change_journal.py:376-378`) |
| 13 | Cachés | `ai.fetch.cache.url/body`, `ai.api.result.cache.arguments_json/body` | En claro | ACL **lectura interno** (CSV 9-10), sin reglas | **Cualquier usuario interno** | No | Ver §6 |

---

## 4. API keys MCP (entrada a `/mcp`)

- **Generación** (HECHO, `mcp_user.py:385-391`): 32 caracteres `[A-Za-z0-9]` con `secrets.choice`
  (≈190 bits). Se guarda solo el hash (`_store_api_key_hash`, 359-370) y se devuelve la clave en
  claro una vez al asistente (`mcp_api_key_wizard.py:113-125`), que la guarda en
  `generated_key` (fila 8 del §3).
- **Hash** (HECHO, `utils/api_key.py:35-48`): `sha256(clave.strip())` hexadecimal, **sin sal ni
  pepper**. Justificación del fabricante (15-25): búsqueda indexada O(1) y portabilidad. Con 190
  bits de entropía es un esquema aceptado para tokens aleatorios (INFERENCIA). Una clave elegida a
  mano (`set_mcp_api_key`, 403-419) puede ser débil y entonces el hash sin sal sí es atacable
  (INFERENCIA).
- **Trampa de `normalize_to_hash`** (HECHO, `api_key.py:51-75`): cualquier valor de 64 caracteres
  hexadecimales se toma como hash ya calculado. Si un admin pega como clave un token hexadecimal de
  64 caracteres (p. ej. `openssl rand -hex 32`), se guarda tal cual y **la clave nunca validará**.
- **Comparación** (HECHO, `controllers/main.py:466-468, 893-895`): `search` por igualdad del hash en
  SQL (índice). No es comparación en tiempo constante, pero se compara el hash, no la clave;
  INFERENCIA: no explotable por tiempo en la práctica.
- **Validación adicional** (HECHO): usuario Odoo activo (`main.py:469, 901-905`).
- **Caducidad**: no existe (HECHO: solo `mcp_api_key_generated_date`, sin fecha de expiración ni
  "último uso"). Una clave por usuario.
- **Revocación** (HECHO): asistente "eliminar" pone el hash a `False`
  (`mcp_api_key_wizard.py:84-96`); también desactivar el usuario. PENDIENTE: si una sesión SSE ya
  abierta se corta al revocar (la sesión guarda la clave y vuelve a hashearla en `main.py:669`).
- **Migración de claves en claro**: `utils/api_key_migration.py:20-69` hashea la columna antigua
  `mcp_api_key` y la borra, pero **no se llama desde ningún sitio** (HECHO: grep solo encuentra la
  definición). Las claves en claro de exportaciones antiguas se hashean al importar
  (`mcp_user.py:572-583`; `config_backup.py:616-619`).
- **Quién gestiona**: ACL de `ai.mcp.user` y del asistente solo AI admin (CSV 33-34). Los métodos
  públicos `action_generate_mcp_api_key` y `set_mcp_api_key` no comprueban grupo y escriben con
  `sudo`; los protege la ACL de lectura del modelo (INFERENCIA).

---

## 5. Servidores externos

### 5.1 Tipos
HECHO: `api_type` `mcp` (transporte `sse` = HTTP JSON-RPC, o `stdio` = proceso local) y `openapi`
(spec remota o pegada, `spec_manual`) (`external_server.py:105-169`).

### 5.2 Credencial
HECHO: `_resolve_auth_token` (857-872): primero la clave activa del usuario en
`ai.api.server.key` (búsqueda con `sudo`), si no `auth_token` del servidor, si no ninguna. La
colocación de la cabecera la decide el servidor (`lib/api/drivers/base.py:25-42`,
`utils/mcp_client.py:71-88`). Excepciones:
- HECHO: `discover` y `test_connection` usan siempre el token del servidor
  (`mcp_driver.py:32, 60` sin `auth_token`; `openapi_driver.py:72-79`).
- HECHO: la descarga de la spec OpenAPI en tiempo de llamada (`openapi_driver.py:325` →
  `_fetch_spec`) también usa el token por defecto, no el del usuario.

### 5.3 `trusted`
HECHO (221-233): si está activo, los pasos `api_call` a ese servidor se ejecutan sin la
confirmación del Safe Plan. Viaja en exportaciones e importaciones (comentario 1083-1085;
`config_backup.py:182-192`). INFERENCIA: importar un fichero con un servidor `stdio` + `trusted`
deja un comando que la IA puede lanzar sin confirmación humana.

### 5.4 Qué se ejecuta al probar o descubrir
HECHO (`utils/mcp_client.py`):
- `stdio`: `subprocess.Popen([command] + args, stdin/stdout/stderr=PIPE, env=os.environ +
  env_vars)` (134-165). Sin `shell=True` (no hay inyección de shell), pero el comando es **libre**:
  quien edite el servidor ejecuta lo que quiera como el usuario del sistema de Odoo.
- **Entorno heredado completo** (150-151): el hijo recibe todas las variables del proceso Odoo.
  INFERENCIA: en Docker suelen incluir credenciales de PostgreSQL (`HOST`, `USER`, `PASSWORD`).
- **Sin timeout en stdio**: `readline()` bloqueante (180); `timeout` del servidor solo se aplica a
  HTTP (63, 102). Un servidor que no responde bloquea el worker hasta el `limit_time_real` de Odoo
  (INFERENCIA).
- **`stderr` en PIPE sin leer** hasta el fallo (186): si el hijo escribe mucho en stderr, se llena
  el buffer y se bloquea (INFERENCIA).
- **Procesos que quedan vivos**: `close()` (323-341) termina el proceso, pero los drivers lo llaman
  solo en el camino feliz, sin `try/finally` (`lib/api/drivers/mcp_driver.py:31-39, 59-64, 72-78`).
  Si el handshake o `tools/list` fallan, el proceso queda vivo (bloqueado leyendo stdin) hasta que
  muera el worker. HECHO del código; PENDIENTE reproducir.
- Cada `test_connection`, `discover` y cada `api_call` lanza un proceso nuevo (handshake completo).
- `sse`: `requests.post` con timeout `server.timeout` (90-116).
- OpenAPI: `requests.get` de la spec y `requests.request` de la operación con timeout
  `(5, timeout)` (`openapi_driver.py:72-80, 369-376`).

### 5.5 Quién puede lanzarlo
HECHO: `action_test_connection` (993-1007) y `action_discover_tools` (874-922) no comprueban grupo;
la ACL da lectura del modelo a todo usuario interno (CSV 7) y el menú es solo admin
(`external_server_views.xml:281`). INFERENCIA: un usuario interno puede llamar por RPC a
`action_test_connection` y **provocar la ejecución del comando stdio configurado** (no elegirlo) o
peticiones salientes; en `action_discover_tools` el `Popen` ocurre antes del `write` que fallaría
por ACL. PENDIENTE: confirmar con `odoo-dev 14`.

### 5.6 Sincronización `config_json`
HECHO: al escribir `config_json` se sobrescriben campos, incluido `auth_token` (533-540); al crear,
solo se rellenan los vacíos (519-524). Un `config_json` sin bloque `auth` pone `auth_type='none'`
(512-513) pero **no borra** `auth_token`.

---

## 6. Lista blanca y cachés

### 6.1 Lista blanca (`ai.url.whitelist`)
HECHO:
- Coincidencia exacta o subdominio, por `kind` (`url_whitelist.py:117-144`); ventana temporal
  `valid_from`/`valid_until`; recorre todas las filas en Python (O(n)).
- Política ICP `pns_ai_mcp.url_access_policy`: `whitelist_only` (defecto) u `open`
  (146-156). Con `open` cualquier dominio se añade automáticamente (`_fetch_url_access_status`,
  170-195).
- Los servidores externos añaden sus dominios al crearse/activarse con el `kind` de su `api_type`
  (`external_server.py:823-847`); los `stdio` no tienen dominio.
- `ai.fx.source` **no** está sujeta a la lista blanca (`ai_fx_source.py:31-32`).
- HECHO: `fetch_url` sigue redirecciones (`controllers/safe_plan.py:1237-1243`, `allow_redirects=True`)
  y la lista blanca solo comprueba el host inicial. No hay bloqueo de IP privadas/loopback/metadatos
  (grep sin resultados de `ipaddress`/`169.254`). INFERENCIA: SSRF posible a través de un dominio
  permitido que redirija, y directo con la política `open`.
- HECHO (bug de importación): `_import_whitelist` busca por `domain` sin `kind`
  (`config_backup.py:596`); con el mismo dominio en dos `kind` actualiza una fila cualquiera y puede
  violar `UNIQUE(domain, kind)`.

### 6.2 `ai.fetch.cache` (`models/fetch_cache.py`)
HECHO:
- Guarda `url` (con query string), `url_hash` (SHA-256 de la clave), `status_code`,
  `content_type`, `body` (cuerpo de texto **truncado a 10 240 caracteres**, `safe_plan.py:1285`),
  `truncated`, `fetched_at`, `expires_at` (32-48). Las respuestas binarias no se guardan
  (`safe_plan.py:1279-1283`).
- TTL decidido por el origen (`Cache-Control`/`Expires`), máximo 7 días
  (`safe_plan.py:1011-1044`).
- Clave: URL exacta, más hash del cuerpo para `QUERY` (`safe_plan.py:1152-1162`). **No incluye el
  método**: `HEAD`/`OPTIONS` y `GET` comparten entrada (un `GET` puede recibir el resumen de
  cabeceras guardado por un `HEAD`). HECHO del código; PENDIENTE reproducir.
- El docstring habla de un `cache_ttl` en `ai.url.whitelist` (23-25) que **no existe**: documentación
  obsoleta.
- Lectura/escritura con `sudo` (74, 117-121); compartida entre usuarios.

### 6.3 `ai.api.result.cache` (`models/api_result_cache.py`)
HECHO:
- Guarda **la respuesta completa** sin truncar (`body`), `body_size`, `server_code`, `tool_name`,
  `arguments_json` (29-45). TTL fijo 600 s (`utils/api_call_result.py:11`).
- Clave = `sha256(server + tool + argumentos)` **sin usuario** (`api_call_result.py:14-18`). En
  `_execute_api_call` se consulta la caché **antes** de resolver la credencial del usuario
  (`safe_plan.py:1415-1426`). INFERENCIA (grave): durante 10 minutos, otro usuario que haga la
  misma llamada recibe la respuesta obtenida con la clave personal del primero, aunque su propia
  clave no le diera acceso a esos datos.

### 6.4 Quién las lee y purga
- HECHO: ACL de lectura para todo usuario interno (CSV 9-10) sin reglas → cualquier usuario puede
  leer por RPC las URLs, cuerpos y argumentos de todos.
- HECHO: lecturas ignoran filas caducadas (`fetch_cache.py:74-77`, `api_result_cache.py:60-63`),
  pero siguen en BD hasta la purga.
- Crons: bloque 1 §7.2. `ir_cron_ai_fetch_cache_gc` cada hora; `ir_cron_ai_api_result_cache_gc`
  **sin `numbercall`** (en 14 vale 1 por defecto) → tras la primera ejecución deja de purgar y las
  respuestas completas se acumulan, legibles por RPC.

---

## 7. Logs (`ai.log`)

HECHO (`models/ai_log.py`):
- Por fila: usuario, origen (chatboo/mcp_client/internal), IP, cliente, fecha, acceso
  (read/write), primitiva, endpoint (herramienta, recurso, prompt), modelo LLM, hilo
  (`correlation_id`, `step_seq`, `operation_code`), flujo calculado, **`prompt_data`**
  (argumentos/mensajes en JSON), **`result_data`** (resultado), `result_summary`,
  `additional_info`, **`user_prompt`** (texto original del usuario), **`code_to_execute`** (Python
  de relaxaicode), tamaños y tokens (44-289).
- Contenido real (HECHO por llamadas): mensajes enviados al LLM en la prueba de conexión
  (`ai_provider.py:533-534`), respuestas LLM (`ai_execution_engine.py:440-461`), errores de
  failover (306-313), planes Safe Plan completos con resultados (`mcp_safe_operation.py:1586-1591`),
  resultados de herramientas MCP (`controllers/main.py`, múltiples `result_data=result`).
  INFERENCIA: incluye datos de clientes leídos por las herramientas y cuerpos de `fetch_url` /
  `api_call`.
- Tamaño: `prompt_data`, `result_data`, `user_prompt`, `code_to_execute` hasta 100 000 caracteres
  cada uno; `result_summary` y `additional_info` 5 000 (606-643).
- Escritura: cursor propio como SUPERUSER con commit inmediato (573-664); se omite solo con
  `TestCursor` (569-570). Dos líneas INFO "TRACE_MCP" por entrada (572, 660).
- Retención: **ninguna automática** (sin cron). Borrado manual con asistente
  (`mcp_log_delete_menu.py:66-68` → `_delete_oldest_logs`, 672-712) para AI admin o sistema
  (CSV 38-39). `user_id` con `ondelete='cascade'` (51): borrar un usuario borra su auditoría.
- Quién los ve: cada usuario interno los suyos (regla `security.xml:68-77`), AI admin todos
  (80-89). HECHO: la ACL del admin es 1,1,1,1 (CSV 35) y ninguna regla restringe la escritura → un
  AI admin puede **modificar** filas por RPC (los `readonly` son solo de interfaz); integridad de
  auditoría no garantizada. INFERENCIA: un AI admin ve datos de negocio que su propio rol quizá no
  le permitiría leer.
- Exportación: solo campos resumen (716-755).

---

## 8. Change journal (`ai.change.journal`)

HECHO (`models/ai_change_journal.py` y `utils/change_journal.py`):
- **Qué registra**: una fila por paso mutante aplicado del Safe Plan (`create`, `write`, `copy`,
  `unlink`, `action`, `field_required`), en la misma transacción (`record_executed_step`, 215-340),
  con quién lo pidió, quién confirmó, origen, autorización, modelo, IDs, tipo
  (`view_modifier`, `field_meta`, `acl`, `module`, `report`, `trusted_action`, `generic`;
  `change_journal.py:20-52`), instantáneas antes/después en JSON y si es reversible.
- **Planes fallidos**: fila `failed` en cursor propio con commit (342-409), incluye el error (2000
  caracteres) y `intended_values` **sin redactar**.
- **Redacción**: claves que contienen `password`, `api_key`, `secret`, `token`, `private_key`,
  `otp`, `smtp_pass`, `oauth` → `'***'` (`change_journal.py:30-38, 80-90`). No cubre `env_vars`,
  `config_json` ni otros nombres.
- **Instantánea**: excluye binarios/imágenes, computados no almacenados y `password`
  (`ai_change_journal.py:23, 201-213`).
- **Revertir** (`action_revert`, 411-494): exige superusuario, `group_ai_admin` o
  `base.group_system` (34-41); solo filas `applied`, reversibles, que no sean ya una reversión y cuyos
  datos actuales coincidan con el "después" (147-185). `create`/`copy` → `unlink` de lo creado;
  `write` → reescribe los valores "antes" excepto los `'***'`. Se ejecuta **con los permisos del
  usuario**, sin `sudo`. Crea una fila `revert` no reversible.
- **No se puede revertir**: `unlink`, `field_required`, `action` sin "undo" declarado, planes
  fallidos, reversiones, campos redactados, cambios posteriores sobre los mismos campos
  (`change_journal.py:121-143`).
- HECHO (core 14 `odoo/fields.py:3062-3070`): una lista de IDs vacía `[]` no se convierte en
  `(6,0,[])`; revertir un Many2many/One2many que estaba vacío **no lo vacía**. Para One2many,
  `(6,0,ids)` puede desvincular o borrar líneas (INFERENCIA).
- Permisos: ACL admin y sistema 1,1,1,0 (CSV 36-37): pueden crear y **modificar** filas por RPC
  (incluido `before_json`) y después revertir; no es escalada porque `revert` usa sus propios
  permisos. Borrado solo superusuario (496-499). `user_id`/`confirmed_by_uid` con
  `ondelete='restrict'`: impide borrar usuarios con historial.
- INFERENCIA: `can_revert` se calcula en la lista (`mcp_change_journal_views.xml:57`) con un `read`
  por fila (N+1) y puede lanzar `AccessError` si el admin no tiene lectura del modelo registrado.
  PENDIENTE.

---

## 9. Consumo y coste

- **`usage_day`** (HECHO): por proveedor y día, suma tokens de prompt/respuesta/total, coste
  informado por el proveedor (en USD, sin convertir) y número de turnos (`request_count` +1 por
  llamada a `increment_for_turn`). Se llama desde `utils/agent_engine.py:4217`. SQL directo en
  cursor propio con commit (`ai_provider_usage_day.py:62-111`). Si no hay tokens ni coste, no
  cuenta (55-56). La prueba de conexión no suma (INFERENCIA, §2.3).
- **Tope**: **no existe**. HECHO por grep (`budget|quota|daily_limit|max_cost|cost_limit|spend`): no
  hay límite de gasto, tokens o peticiones por usuario o proveedor; solo se contabiliza. Además
  `provider_id` elegido en la interfaz se acepta sin restricciones (`ai_execution_engine.py:171-174`).
- **Fuentes FX** (HECHO):
  - Por defecto `https://open.er-api.com/v6/latest/USD` y
    `https://api.frankfurter.app/latest?from=USD` (`data/fx_source_data.xml:3-14`, activas,
    `noupdate`).
  - Se piden en `get_usd_fx` (`ai_fx_source.py:83-154`), llamado desde
    `pns_ai_chatboo/controllers/chatboo.py:87, 923-925` (ruta `/chatboo/check_health`, `auth='user'`,
    66) vía `pns_ai_chatboo/utils/fx_rates.py:19`.
  - Caché diaria en ICP `pns_ai_mcp.fx_usd_cache` (93-102, 150-153). **Si todas fallan no se cachea
    el error** (129-142): cada `check_health` vuelve a intentar todas las fuentes (4 s de timeout
    cada una) y escribe `fail_count`/`last_error` con `sudo` en la transacción de la petición.
    INFERENCIA: sin salida a Internet, cada carga de la interfaz espera hasta 8 s.
  - PENDIENTE: frecuencia real de `check_health` (probablemente al cargar el cliente web de cada
    usuario interno, incluidos los que no tienen clave MCP: `has_api_key` se calcula, pero `fx` se
    pide igualmente, `chatboo.py:85-87`).
  - Respaldo: tasas de `res.currency` (`_rates_from_odoo_currency`, 156-187; `_convert` existe en
    14, `res_currency.py:187`).
- **Moneda de visualización**: ICP `pns_ai_mcp.display_currency`, 50 códigos ISO
  (`utils/display_currency.py`); `convert_usd_amount` solo presenta, no persiste
  (`utils/fx_rates.py:32-63`).

---

## 10. Copias de configuración

### 10.1 `config_backup` (copia completa)
HECHO (`utils/config_backup.py`):
- **Incluye**: proveedores con modelos, modelo elegido y uso diario (120-131); agentes con contextos,
  skills y cadena de proveedores (134-157); contextos no `core` (160-167); skills no de sistema
  (170-179); servidores externos (todos los campos escalares, 182-192); lista blanca (195-197);
  usuarios MCP con clave generada: login, nombre, estado, banderas de grupo y **hash** (200-231);
  ajustes ICP del módulo (248-260).
- **Sin secretos** (`include_secrets=False`): se quita `api_key` del proveedor y se vacían
  `auth_token` y `env_vars` de servidores (125-126, 188-190). **No** se vacía `config_json`
  (fuga, §3 fila 3). El hash MCP se incluye siempre. Los tokens por usuario (`ai.api.server.key`)
  nunca se incluyen.
- **Desde Ajustes siempre con secretos** (`res_config_settings.py:172`); requiere crear
  `res.config.settings` (core: solo `base.group_system`,
  `odoo/addons/base/security/ir.model.access.csv:110`) y `ensure_ai_admin`.
- **Importación** (`import_config`, 267-301; asistente `wizard/config_backup_wizard.py:42-88`, ACL
  solo admin CSV 63): todo con `sudo`, `replace_existing=True` fijo (287): actualiza por clave de
  negocio (proveedor `name`, contexto/skill/servidor/agente `code`, lista blanca `domain`, usuario
  `login`). Sobrescribe:
  - proveedores: todos los campos presentes (si el fichero no trae `api_key`, se conserva) (444-493);
  - servidores: todos los campos presentes; si el fichero sin secretos trae `auth_token=''`, **borra
    el token del destino**, salvo que `config_json` lo vuelva a poner (556-578 + §5.6);
  - agentes: campos escalares y **reconstrucción completa de la cadena de proveedores** (borra y
    recrea enlaces, 724-747); contextos y skills de agentes/skills con `(6,0,ids)` (712, 721, 768,
    772);
  - usuarios MCP: solo hash, estado y fecha (633-653); no toca grupos;
  - ajustes ICP vía `pns_base` (779-806), incluida la política de URL (`open` abre la salida).
  - No borra registros que no estén en el fichero.
- Riesgo (INFERENCIA): importar un fichero ajeno permite introducir servidores `stdio` con comando
  arbitrario y `trusted=True`, proveedores con endpoint ajeno (exfiltración de prompts) y la
  política `open`.

### 10.2 `artifact_bundle` (copia parcial)
HECHO (`utils/artifact_bundle.py`): ZIP con secciones opcionales (`skills.zip`, `contexts.zip`,
`providers.json`, `agents.json`, `mcp_servers.json`, `mcp_users.json`, `url_whitelists.json`,
`settings.json`) y `bundle_manifest.json` con la base de datos de origen (47-183).
`include_secrets` y `include_settings` desactivados por defecto
(`wizard/artifact_bundle_export_wizard.py:20-29`). Importación con `import_partial` y
`replace_existing` elegible (186-275; `config_backup.py:304-353`). Mismas reglas de sobrescritura
que §10.1. Ambos extremos llaman a `ensure_ai_admin` (62, 188).

### 10.3 Exportaciones por modelo
HECHO: `ai.provider` (incluye `api_key` siempre), `ai.api.server` (todos los campos siempre),
`ai.mcp.user` (hash), `ai.url.whitelist`, `ai.log` (resumen). Todas protegidas por
`ensure_ai_admin`, que se salta con el contexto `skip_hardcoded_restrictions`
(`utils/import_export_guard.py:9-10`; bloque 1 §4.5-4, bloque 2 §4). INFERENCIA: para
`ai.api.server` el bypass no añade exposición (ya es legible por RPC); para `ai.provider` la
lectura de `api_key` sigue bloqueada por `groups` y la excepción se traga
(`ai_provider.py:610-613`), saliendo solo el nombre.

---

## 11. `sudo()`, compatibilidad y riesgos

### 11.1 Usos de `sudo()` y superusuario en el bloque
| Archivo:línea | Uso | Valoración |
|---|---|---|
| `ai_provider.py:117` | leer `api_key` para inferir | Justificado (documentado) |
| `ai_provider_usage_day.py:63, 119` | SQL con `SUPERUSER_ID`; importación | Justificado |
| `ai_fx_source.py:56, 64, 92, 105, 163` | marcar fuentes, ICP, buscar fuentes y monedas | Justificado; escribe en la transacción de cualquier usuario |
| `mcp_user.py:197, 203, 291, 363, 413, 496` | cliente MCP, estado de clave, guardar hash, leer acción | 363/413 sin comprobar grupo (protegido por ACL) |
| `mcp_api_key_wizard.py:86` | borrar hash | ACL admin |
| `url_whitelist.py:110, 132, 149, 245, 250, 266` | consultas y alta automática | `ensure_domain_whitelisted` es `@api.model` público: INFERENCIA, cualquier usuario interno podría llamarlo por RPC y **añadir dominios a la lista blanca** (no comprueba grupo). PENDIENTE |
| `external_server.py:567, 651, 787, 799, 865, 1046, 1068` | contextos de detección, spec, credencial del usuario, catálogo | Justificado salvo 567/651 con `skip_hardcoded_restrictions` |
| `fetch_cache.py:74, 117, 121, 131`; `api_result_cache.py:60, 89, 93, 104` | caché compartida | Ver §6.3 (fuga entre usuarios) |
| `ai_log.py:575, 682-700` | registro y borrado | Justificado |
| `ai_change_journal.py:361-362, 458` | planes fallidos y fila de reversión | Justificado |
| `config_backup.py` (todas las funciones de export/import) y `artifact_bundle.py:63-69, 189-190` | copias | Dependen de `ensure_ai_admin` |
| `display_currency.py:79` | leer ICP | Inocuo |

### 11.2 Compatibilidad Odoo 14 y Python 3.7.3
- HECHO: `from __future__ import annotations` en `ai_fx_source.py:5`, `utils/display_currency.py:5`,
  `utils/fx_rates.py:5`, `utils/change_journal.py:10`, `utils/artifact_bundle.py:10`: válido desde
  3.7. f-strings (3.6), `secrets` (3.6), `raise … from` correctos. No se ha visto `:=`, `dict | dict`
  ni genéricos `list[str]` en los archivos del bloque.
- HECHO: `search_fetch` no existe en 14 (código muerto); `web_search_read` sí (módulo `web`).
- HECHO: acción `display_notification` con `next` soportada en 14
  (`web/static/src/js/core/misc.js:190-200`); el mensaje pasa por `sprintf`, un `%` en el texto
  podría romperlo (INFERENCIA).
- HECHO: `res.currency._convert` existe en 14 (`res_currency.py:187`).
- HECHO: `api_key_migration.py` no se invoca (código muerto).
- PENDIENTE: `display_name` almacenado en `ai.log` en 14; ejecución de tests con los cursores
  propios (§2.5).

### 11.3 Riesgos (orden de gravedad)
1. Tokens de servidores externos (`auth_token`, `env_vars`, `config_json`) legibles por cualquier
   usuario interno por RPC (`external_server.py:176-242`, CSV 7). Ya señalado en bloque 1 §4.5-1;
   aquí se añade `config_json` y `env_vars`.
2. Caché de `api_call` sin usuario en la clave: respuestas obtenidas con la clave personal de un
   usuario servidas a otros 10 minutos (`api_call_result.py:14-18`, `safe_plan.py:1415-1426`), y
   legibles por RPC por todos (CSV 10); con el cron sin `numbercall`, se acumulan.
3. `include_secrets=False` no vacía `config_json` (`config_backup.py:187-191, 400-404`).
4. Servidores `stdio`: comando libre, entorno completo de Odoo heredado, sin timeout de lectura,
   procesos huérfanos si falla el handshake (`mcp_client.py:134-195`, `mcp_driver.py:31-78`);
   lanzables por RPC por usuarios internos vía `action_test_connection` (INFERENCIA, PENDIENTE).
5. Clave MCP por query string (`main.py:443, 870`) y prefijo en logs (866, 872).
6. Logs y journal con datos sensibles sin redactar (planes completos, `intended_values`), sin
   retención automática y modificables por AI admin.
7. Lista blanca: redirecciones no revalidadas y sin bloqueo de IP internas (SSRF).
8. Sin tope de gasto; selección libre de proveedor desde la interfaz.
9. Copias exportadas con secretos en `ir.attachment` sin borrado.
10. Importación de copias: puede introducir comandos, endpoints y política `open`; bug de
    lista blanca por `kind`.

---

## Resumen del bloque

- Tres clases de credencial: `ai.provider.api_key` (salida a LLM, en claro, `groups` admin),
  `ai.api.server.auth_token`/`env_vars`/`config_json` y `ai.api.server.key.token` (salida a APIs
  externas, en claro) y la clave MCP de entrada (solo SHA-256 sin sal).
- La clave del proveedor está bien protegida por `groups`; las de servidores externos no: cualquier
  usuario interno las lee por RPC, incluidas las duplicadas en `config_json`.
- Las claves MCP: 32 caracteres aleatorios, hash determinista indexado, sin caducidad, una por
  usuario, revocables borrando el hash; la clave en claro queda en la tabla transitoria del
  asistente hasta el vaciado; se aceptan por query string y su prefijo va al log.
- La migración de claves en claro existe pero no se ejecuta nunca.
- Proveedores: protocolos `openai` y `anthropic` (driver `ollama` registrado pero no
  seleccionable); "Fetch Models" borra modelos que desaparecen; "Test Connection" hace un chat real
  y lo registra entero en `ai.log`.
- Cadena de proveedores: elegido en interfaz (sin restricción) → enlaces por prioridad → todos los
  proveedores; failover registrado en `ai.log`.
- El `cr.commit()` de `ai_provider.py:589` es de un cursor auxiliar para evitar errores de
  serialización del turno largo; salta el ORM y confirma aunque la petición falle; mismo patrón en
  uso diario, logs y journal.
- Servidores externos MCP stdio/SSE y OpenAPI; credencial del usuario antes que la del servidor
  (pero descubrir y probar usan siempre la del servidor); `trusted` omite la confirmación.
- Stdio ejecuta un comando libre con el entorno completo de Odoo, sin timeout de lectura y sin
  `finally` para matar el proceso; los métodos de prueba no comprueban grupo.
- Lista blanca tipada con ventana temporal; política `open` añade dominios solos; no revalida
  redirecciones ni bloquea IP internas.
- Caché de `fetch_url`: cuerpo truncado a 10 KB, TTL del origen hasta 7 días, clave sin método.
- Caché de `api_call`: respuesta completa, 10 min, clave sin usuario → fuga entre usuarios;
  ambas cachés legibles por todos; la purga de `api_call` se apaga tras la primera ejecución.
- `ai.log`: prompts, respuestas, argumentos, código y resultados hasta 100 KB por campo; sin
  retención automática; cada usuario ve los suyos, el AI admin todos y puede modificarlos.
- Journal: instantáneas redactadas por nombre de campo; reversión solo de create/copy/write por
  admin/sistema con sus permisos; no revierte unlink, acciones sin undo, campos redactados ni
  x2many vacíos.
- Consumo: tokens, coste del proveedor y turnos por día; **ningún tope**. FX: dos APIs públicas,
  caché diaria; si fallan, se reintenta en cada `check_health`.
- Copias: la completa desde Ajustes siempre lleva secretos; "sin secretos" deja `config_json`; los
  hashes MCP siempre viajan; la importación sobrescribe por clave de negocio, reconstruye cadenas de
  failover y puede cambiar la política de URL.
- Compatibilidad con 14 y Python 3.7 correcta en lo leído; código muerto (`search_fetch`,
  migración de claves).

## Tabla de cobertura

| Archivo | Líneas | Leído entero |
|---|---|---|
| `models/ai_provider.py` | 718 | Sí |
| `models/ai_provider_usage_day.py` | 161 | Sí |
| `models/ai_fx_source.py` | 192 | Sí |
| `models/mcp_user.py` | 682 | Sí |
| `models/external_server.py` | 1186 | Sí |
| `models/api_server_key.py` | 69 | Sí |
| `models/url_whitelist.py` | 321 | Sí |
| `models/fetch_cache.py` | 136 | Sí |
| `models/api_result_cache.py` | 109 | Sí |
| `models/ai_log.py` | 755 | Sí |
| `models/ai_change_journal.py` | 499 | Sí |
| `utils/config_backup.py` | 806 | Sí |
| `utils/artifact_bundle.py` | 286 | Sí |
| `utils/api_key.py` | 75 | Sí |
| `utils/api_key_migration.py` | 69 | Sí |
| `utils/display_currency.py` | 84 | Sí |
| `utils/fx_rates.py` | 63 | Sí |
| `utils/change_journal.py` | 167 | Sí |
| Apoyo: `security/ir.model.access.csv` (69), `security/security.xml` (194), `utils/mcp_client.py` (341), `lib/api/drivers/mcp_driver.py` (93), `utils/import_export_guard.py` (17), `utils/portable_io.py` (8), `models/mcp_api_key_wizard.py` (126), `wizard/config_backup_wizard.py` (88), `views/external_server_views.xml` (282) | — | Sí |
| Apoyo parcial: `lib/api/drivers/openapi_driver.py` (60-89, 150-405), `lib/api/drivers/base.py` (20-49), `controllers/safe_plan.py` (1005-1044, 1152-1162, 1200-1479), `controllers/main.py` (440-499, 850-919), `models/ai_execution_engine.py` (133-189, 250-329, 415-464, 520-589), `models/mcp_safe_operation.py` (1575-1599), `wizard/artifact_bundle_export_wizard.py` (1-40), `pns_base/utils/portable_io.py` (20-319), `pns_ai_chatboo/controllers/chatboo.py` (60-89, 905-934), `data/fx_source_data.xml` (entero) | — | No (solo lo citado) |

Archivos del bloque no leídos enteros: ninguno.

## Preguntas abiertas

1. ¿Se acepta que cualquier usuario interno lea por RPC `auth_token`, `env_vars` y `config_json` de
   `ai.api.server` (ampliación de la pregunta 3 del bloque 1)?
2. ¿Se usan servidores con credenciales por usuario? Si es así, la caché de `api_call` sin usuario en
   la clave sirve datos de un usuario a otro durante 10 minutos: ¿se informa al fabricante como
   fallo de seguridad?
3. ¿Se va a usar el transporte `stdio` en algún cliente? Si no, ¿se documenta como prohibido
   (comando libre, entorno completo heredado, procesos huérfanos)?
4. PENDIENTE de `odoo-dev 14`: ¿un usuario interno sin grupos IA puede ejecutar por RPC
   `ai.api.server.action_test_connection` / `action_discover_tools` y
   `ai.url.whitelist.ensure_domain_whitelisted`?
5. ¿Se acepta que la copia completa desde Ajustes lleve siempre los secretos y que "sin secretos"
   no vacíe `config_json`? ¿Quién custodia los adjuntos de exportación, que no se borran?
6. ¿Hace falta un tope de gasto o, al menos, restringir la elección libre de proveedor desde la
   interfaz?
7. ¿Qué retención se quiere para `ai.log` (contiene prompts, respuestas y datos de negocio) y
   para las cachés? ¿Es aceptable que el AI admin pueda modificar filas de log?
8. ¿Hay salida a Internet desde el servidor? Sin ella, cada `check_health` espera los timeouts de
   las dos fuentes FX (hasta 8 s): ¿se desactivan las fuentes en esos clientes?
9. ¿Se informa al fabricante de: clave MCP por query string y prefijo en logs, migración de claves
   no invocada, clave de caché de `fetch_url` sin método, importación de lista blanca sin `kind`,
   reversión de x2many vacíos y docstring de `cache_ttl` obsoleto?
10. PENDIENTE de `odoo-dev 14`: comportamiento de `display_name` almacenado en `ai.log`,
    `can_revert` en la lista del journal con modelos sin permiso de lectura, y cursores propios
    (`registry.cursor()` + commit) dentro de los tests.
