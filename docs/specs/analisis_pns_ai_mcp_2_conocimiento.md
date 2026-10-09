# Análisis: pns_ai_mcp — Bloque 2: conocimiento (contextos, skills y agentes) (Odoo 14.0, rama 14.0-analisis-pns-ai)

Documento de análisis, **no de diseño**: no se propone código. `pns_ai_mcp` es de terceros
(Patanegra Soft, Apache-2.0) y no se modifica. Se analiza la copia de trabajo
`/home/soporte/GitHub/third_party/pns_ai_mcp/`.

Etiquetas: **HECHO** (con `archivo:línea`), **INFERENCIA** (deducción del código, no ejecutada),
**PENDIENTE** (se comprobará con `odoo-dev 14`).

Referencias cruzadas (no se repiten aquí):
- **[MAPA]** = `docs/specs/analisis_pns_ai_mcp_1_mapa.md` (§3.1 hooks, §4.2 ACL, §4.3 record rules,
  §4.5 riesgos, §10 compatibilidad).
- **[BASE]** = `docs/specs/analisis_pns_base.md`.
- Core 14 = `/opt/odoo-src/14.0/odoo/`.

Archivos del bloque (todos leídos enteros, ver tabla de cobertura): `models/ai_context.py` (3483 l.),
`models/ai_skill.py` (1838), `models/ai_agent.py` (1633), `models/ai_agent_consumer.py` (82),
`utils/context_roles.py`, `context_utils.py`, `context_code_scan.py`, `knowledge_ownership.py`,
`knowledge_stamp.py`, `domain_index.py`, `copy_code.py`, `ai_paths.py` y los 59 archivos de `ai/`.
Para entender los flujos se han consultado puntualmente (sin leerlos enteros) `hooks.py:157-257`,
`utils/import_export_guard.py:7-17`, `utils/agent_engine.py:631-866`, `controllers/main.py:1570-1614`,
`utils/agent_identity.py:154-181`, `security/security.xml` y `data/ai_agent_data.xml`.

---

## 1. Modelos

### 1.1 `ai.context` — `models/ai_context.py` (modelo nuevo, `_name`)

Atributos: `_name='ai.context'` (108), `_rec_name='code'` (110), `_order='code'` (111),
`_sql_constraints` `code_uniq unique(code)` (113-115). Sin `company_id`: el catálogo es **común a
todas las compañías** (HECHO).

| Campo | Tipo | Parámetros relevantes | Línea |
|---|---|---|---|
| `code` | Char | `required=True` | 117 |
| `description` | Text | — | 126 |
| `author`, `version` | Char | se rellenan desde metadatos del archivo | 131, 136 |
| `date_modified` | Date | — | 141 |
| `content` | Text | `required=True`; texto que se inyecta al LLM | 146 |
| `active` | Boolean | `default=True` | 152 |
| `agent_ids` | Many2many `ai.agent` | tabla `ai_agent_context_rel` (inversa de `ai.agent.context_ids`) | 160 |
| `context_type` | Selection | `context_roles.TYPE_SELECTION` (core/domain/locale/discovery), `default='domain'`, `required` | 175 |
| `discovery_target_kind` | Selection | domain/api_server/url_whitelist, `default='domain'`, `required` | 188 |
| `discovery_target` | Char | `index=True` | 201 |
| `api_server_id` | Many2one `ai.api.server` | `ondelete='cascade'`, `index` | 208 |
| `discovery_triggers` | Text | JSON o una por línea | 217 |
| `discovery_priority` | Integer | `default=0` | 222 |
| `discovery_soft_depends` | Char | CSV | 227 |
| `locale` | Char | `index`; explícito, no se deduce del código | 236 |
| `base_code` | Char | `compute='_compute_base_code'`, `store=True`, `index` | 245 |
| `source_module` | Char | `readonly=True`, `index` (readonly solo de vista) | 293 |
| `composition_origin` | Selection | `compute`, `search`, no almacenado | 301 |
| `link_visible` | Boolean | `compute`, `search` | 316 |
| `composition_locked` | Boolean | `compute` | 320 |
| `owner_id` | Many2one `res.users` | `index`, `ondelete='set null'`; vacío = conocimiento de módulo | 326 |
| `content_size_bytes`, `content_size_without_metadata`, `metadata_overhead_bytes` | Integer | `compute='_compute_content_sizes'`, `store=False` | 459-478 |
| `rel_path` | Char | ruta portable `contexts/...` | 1201 |
| `usage_count` | Integer | `default=0`, `readonly` | 1209 |
| `last_used` | Datetime | `readonly` | 1216 |

Ningún campo tiene `groups=` (HECHO). `content` es legible por todo usuario interno dentro de la
regla "sin dueño o propios" ([MAPA] §4.3).

**Métodos** (todos `@api.model` salvo que se indique; los que no empiezan por `_` se pueden llamar
por RPC, core `odoo/models.py:116-119`):

| Grupo | Métodos (línea) | Comentario |
|---|---|---|
| Compute/search | `_compute_base_code` (254), `_compute_composition_link` (264, `@api.depends_context('composition_agent_id','active_id','active_model')`), `_search_composition_origin` (282), `_search_link_visible` (287), `_compute_content_sizes` (480) | `base_code` = `code` sin el sufijo `_<locale>` si coincide con `locale`. |
| Overrides ORM | `fields_get` (333, llama a super), `create` (354, `@api.model_create_multi`, super), `write` (1513, super), `unlink` (1629, super), `read` (1749, super sin cambios), `_search` (1438, super), `toggle_active` (1741, **no** llama a super), `_register_hook` (415, super primero), `_auto_init` (1222, super primero) | Ver §4 para `write`/`unlink`. `_search` reescribe hojas `name`→`code` y el filtro "Mi idioma". `toggle_active` ignora los `core`. |
| Constraints | `_check_code_snake_case` (1481), `_check_code_unique` (1498, redundante con el SQL, `search` en bucle) | |
| Ownership | `ownership_read_domain` (346), `filter_visible_for_user` (350), `_apply_detection_defaults` (365) | `_apply_detection_defaults` busca `ai.api.server` con `sudo` por código (391). |
| Composición | `get_context_for_country` (567), `_normalize_user_locale` (648), `get_listable_for_mcp` (654), `_virtual_map_from_contexts` (683), `_lazy_load_locale_variants` (703), `_pick_resolved_variant` (742), `_resolve_parts_from_virtual_map` (756), `assemble_context_parts` (826), `build_language_directive` (1034), `_injectable_active_contexts` (1053), `_domain_index_inject_enabled` (1064), `split_contexts_by_domain_index` (1075), `build_bundle_payload` (1100), `get_monolithic_content` (1117), `get_canonical_contexts_for_agent` (954), `normalize_context_ids` (984), `family_context_ids` (1015, de registro) | §3. |
| Discovery | `_discovery_parse_triggers` (839), `_discovery_core_codes` (855), `_active_api_server_codes` (868, `sudo`), `get_discovery_entries` (877), `get_discovery_indexed_codes` (948) | §3.3. |
| Estadísticas | `get_composition_stats` (779), `get_bundle_payload_size` (1112), `get_stats_by_ids` (1130), `get_global_stats` (1301, de registro), `get_formatting_conventions` (507), `get_base_context_name` (1175) | `get_formatting_conventions` mete `user_locale` sin escapar en una regex (533): con un `lang` manipulado por RPC solo provoca `re.error` (INFERENCIA, impacto nulo). |
| Uso | `record_context_usage` (1399) | **SQL directo en cursor propio con `commit`** (1409-1421); actualiza `usage_count`, `last_used` **y `write_date`**. Sin comprobación de permisos (§4.3, §3.4). |
| Importación de fábrica | `_import_all_from_module` (1989), `_import_contexts_from_dir` (2305), `_module_ships_context_code` (1976), `_resolve_import_agent_codes` (2116), `_explicit_agent_codes_from_metadata` (2099), `_pull_agent_codes_for_context` (2148), `_link_context_after_import` (2164), `_link_context_to_import_agents` (2183), `default_context_codes_for_agent` (2197), `_discovery_vals_from_metadata` (2295), `_infer_explicit_locale` (3167), `_backfill_explicit_locale` (3199), `_extract_metadata_from_content` (3217), `_extract_description_from_content` (3470), `normalize_code` (1870), `generate_code_from_name` (1906), `_get_module_path` (1756), `_get_context_source_paths` (1768, `sudo` sobre `ir.module.module`), `_factory_discovery_stems_on_disk` (433), `_factory_source_file_exists` (1570), `_is_shipped_factory_locked` (1609, `sudo`), `_invalidate_agent_caches_after_import` (1924, **SQL directo** `UPDATE ai_agent ... FOR UPDATE SKIP LOCKED` en savepoint), `import_system_from_files` (1858), `_import_system_from_files_internal` (2542), `_import_from_files_internal` (2554), `import_custom_bootstrap` (3102) | §5. |
| Limpieza de "identidad" | `_purge_retired_self_source_files` (1646), `_retire_generic_self_row` (1679) | **Borra carpetas del disco** (`shutil.rmtree` de `ai/contexts/domain/self/` en cualquier addon instalado, 1658-1665). |
| Export/import ZIP | `action_export_selected_zip` (1344), `_build_export_content` (1810), `_zip_path_for_record` (2568), `_export_content_for_record` (2593), `_build_export_manifest` (2620), `import_context_file` (2646), `_tally_import_result` (2750), `_read_zip_manifest` (2764), `_resolve_import_code` (2774), `import_contexts_from_zip_buffer` (2784), `import_contexts_zip` (2816), `import_agent_contexts_zip` (2863), `import_agent_zip` (2940), `_build_contexts_zip_bytes` (3005), `_export_records_to_zip` (3028), `export_all_to_zip` (3050), `action_export_selected` (3056), `export_agent_contexts_to_zip` (3067), `action_export_selected_to_zip` (3076), `export_agent_to_zip` (3090), informes HTML (1230, 2874), asistentes (1470, 1475, 2917, 2921, 2925) | Todos con `ensure_ai_admin` salvo los privados. |
| Acción | `action_restore_from_module` (1256) | Comprueba `has_group('pns_ai_mcp.group_ai_admin')` **explícitamente** (1266), no saltable por contexto. |

Defectos de código detectados (HECHO, sin efecto en la instalación estándar):
- `import_custom_bootstrap` (3121-3126): el `try:` está fuera del bucle `for filename in files`, así
  que solo procesa el **último** archivo de cada carpeta, tenga o no la extensión filtrada. No se
  ejecuta en la práctica: `pns_ai_mcp` no trae `ai/contexts/custom/`.
- La exportación ZIP escribe las filas `discovery` como `.json` (2570-2571), pero la importación ZIP
  solo acepta `.txt`, `.md` y `.xml` (2795): las filas de discovery **no vuelven** al importar.
- `import_context_file` (2728-2742) y `import_skills_zip` (`ai_skill.py:1191-1220`) crean sin
  `source_module` ni `is_system`; `apply_create_ownership` (`utils/knowledge_ownership.py:28-40`)
  asigna entonces `owner_id` = usuario que importa (un AI Administrator es Writer por implicación,
  [MAPA] §4.1). INFERENCIA: lo importado por ZIP queda **privado del administrador que importa** (solo
  entra en su "User knowledge" y solo él lo ve). PENDIENTE.

### 1.2 `ai.skill` — `models/ai_skill.py` (modelo nuevo)

`_name='ai.skill'` (93), `_order='sequence, code'` (95), `code_uniq unique(code)` (253-255). Sin
`company_id`.

| Campo | Tipo | Parámetros | Línea |
|---|---|---|---|
| `name` | Char | `required`, `translate` | 97 |
| `code` | Char | `required`; snake_case (constraint 345) | 98 |
| `command` | Char | kebab-case; vacío = `code` | 104 |
| `sequence` | Integer | `default=10` | 109 |
| `description` | Char | `required`, `translate` | 110 |
| `content` | Text | `required`; Markdown de orquestación | 116 |
| `code_body` | Text | Python "relaxaicode" ejecutable (bloque 6) | 125 |
| `agent_ids` | Many2many `ai.agent` | tabla `ai_agent_skill_rel`; vacío = skill global | 133 |
| `context_ids` | Many2many `ai.context` | tabla `ai_skill_context_rel` | 142 |
| `version` | Char | — | 151 |
| `param_schema` | Text | JSON | 152 |
| `arg_hint` | Char | — | 160 |
| `args_policy` | Selection | default/ask/none, `default='default'` | 167 |
| `painter` | Selection | painter-local/painter-free, `default=False` | 179 |
| `triggers` | Char | obsoleto | 192 |
| `active` | Boolean | `default=True` | 198 |
| `show_in_slash` | Boolean | `default=True`; espejo de la ICP `pns_ai_mcp.skills_slash_hidden` (53) | 199 |
| `is_system` | Boolean | `default=False` | 207 |
| `source_module` | Char | `readonly`, `index` | 213 |
| `composition_origin`, `link_visible` | Selection/Boolean | `compute`, `search` | 221, 236 |
| `rel_path` | Char | — | 240 |
| `owner_id` | Many2one `res.users` | `index`, `ondelete='set null'` | 246 |

Sin `groups=` en ningún campo: `code_body` lo lee cualquier usuario interno en los skills visibles
(HECHO).

**Métodos**:
- Overrides: `fields_get` (282, super), `create` (500, `@api.model_create_multi`, super; aplica
  propiedad y la ICP de ocultos), `write` (514, super; §4), `unlink` (534, super; §4). No sobrescribe
  `copy`, `_register_hook` ni `_auto_init`.
- Constraints: `_check_code` (319-354: sin prefijo `skill.`, comando sin colisiones, formatos) y
  **`_check_code_body_contract` (363-433)**: al guardar `code_body`/`content` valida el AST con
  `controllers/validators.validate_relaxaicode_source_ast`, el contrato publicado y, si
  `registry.ready`, **ejecuta el código** (`bootstrap_skill_code_body`, 412-415) con argumentos vacíos
  como el usuario que guarda. El detalle de la ejecución es del bloque 6.
- Exposición: `invoke_code` (314), `mcp_prompt_name` (551), `get_for_agent` (556),
  `get_by_prompt_name` (570), `_resolve_context_text` (584), `build_prompt_payload` (607),
  `list_for_agent` (644), `_arg_hint_text` (940), `_substitute_arguments` (961),
  `build_invocation_payload` (978).
- Autoría desde Chatboo: `user_can_author_skills` (675), `_require_skill_author` (679),
  `_find_by_invoke_token` (686), `_owned_mutable_skill` (702), `allocate_instance_identity` (717),
  `action_delete_owned` (892), `action_rename_owned` (899).
- ICP de ocultos: `_slash_hidden_codes` (435), `_set_slash_hidden_codes` (448),
  `_sync_slash_hidden_icp` (456), `_apply_slash_hidden_from_icp` (469), `sync_slash_hidden_from_field`
  (486, `sudo`, público).
- Sincronización de fábrica: `_get_module_path` (1231), `_skill_parse_md` (1243),
  `_get_skill_source_paths` (1261, `sudo`), `import_from_files` (1299), `_skill_disk_index_for_module`
  (1509), `_skill_rel_paths_for_module` (1545), `unlink_retired_from_module` (1551),
  `unlink_named_factory_skills` (1598), `import_from_module` (1628), `_after_factory_skill_import`
  (1649), `default_skill_codes_for_agent` (1661), `reapply_source_module_prefixes` (751),
  `_factory_skill_rel_paths_on_disk` (834), `hide_unprefixed_slash_twins` (848),
  `reload_from_server` (1761).
- ZIP: 996-1226 (todos con `ensure_ai_admin`), informes 1735, 1792.

HECHO: `pns_ai_mcp` **no trae skills**: `ai/skills/` solo contiene `custom/.gitkeep`. La sincronización
de fábrica (`hooks.py:182-184`, alcance `('system',)`) no encuentra archivos y
`unlink_retired_from_module` registra un WARNING "no skill files on disk" en cada sincronización
(`ai_skill.py:1567-1572`). Los skills vienen de otros módulos (p. ej. Chatboo).

### 1.3 `ai.agent` — `models/ai_agent.py` + `models/ai_agent_consumer.py`

`_name='ai.agent'` (61), `_order='sequence, name'` (63), `code_uniq` (212-214). Sin `company_id`.

| Campo | Tipo | Parámetros | Línea |
|---|---|---|---|
| `name` | Char | `required`, `translate` | 65 |
| `code` | Char | `required` | 66 |
| `agent_type` | Selection | inference/endpoint, `default='inference'`, `required` | 70 |
| `sequence`, `description`, `active` | Integer/Text/Boolean | `active` default True | 79-81 |
| `origin` | Selection | module/user, `default='user'`, `required`, `readonly` | 82 |
| `module_name` | Char | `readonly` | 92 |
| `provider_ids` | One2many `ai.agent.provider` | — | 98 |
| `max_agent_rounds` | Integer | `default=10` | 104 |
| `default_context_codes`, `required_context_codes`, `default_skill_codes` | Text | listas CSV/`@módulo` | 114, 123, 131 |
| `context_ids` | Many2many `ai.context` | `ai_agent_context_rel`, dominio sin core/discovery | 138 |
| `skill_ids` | Many2many `ai.skill` | `ai_agent_skill_rel` | 151 |
| `context_ids_shown`, `skill_ids_shown` | Many2many | `compute` + `inverse`, no almacenados | 162, 170 |
| `link_show_native/imported/pinned/extra` | Boolean | `default=True`, `copy=False` | 177-200 |
| `cached_content` | Text | `readonly`, `copy=False` (prompt compilado) | 203 |
| `cache_locale`, `cache_updated`, `cache_context_signature` | Char/Datetime/Char | `readonly`, `copy=False` | 204-210 |

Ningún campo con `groups=`: `cached_content` lo lee cualquier usuario interno ([MAPA] §4.2 l.15).

**Overrides**: `create` (218-236, **`@api.model`**, no `model_create_multi`; acepta dict o lista;
llama a super), `write` (238-271, super), `unlink` (285-295, super; impide borrar `origin='module'`),
`read` (791, super + reordena M2M), `fields_get` (841, super), `web_read` (795-799: **no existe en
Odoo 14**, HECHO: no hay `def web_read` en el core 14; código muerto). Herencia en
`ai_agent_consumer.py`: `unlink` (23-33, super; exige que no tenga proveedores ni contextos).
No sobrescribe `copy`, `_register_hook` ni `_auto_init`.

`_check_agent_create` (273-283): fuera de `install_mode` solo admite `origin='module'`. Ambas
condiciones las controla quien llama (el contexto y los `vals` llegan del RPC; `install_mode` lo pone
el core al cargar XML, `odoo/models.py:4183`). INFERENCIA: no es una barrera de seguridad, pero el ACL
de creación de `ai.agent` es solo de AI Administrator ([MAPA] §4.2 l.52), que es quien decide.

Resto de métodos: composición y caché (301-445, 1142-1355; §3), tokens y recetas (447-551,
690-707), origen de enlaces (553-839), acciones de selección/restauración (888-1138), identidad
(1182-1315), estadísticas/exportación (1357-1487). En `ai_agent_consumer.py`:
`resolve_inference_agent_code` (35), `get_mcp_bare_agent_code` (53), `resolve_mcp_agent_code` (58),
`action_open_form` (71).

`ai.agent.provider` (`ai_agent.py:1489-1633`): `agent_id`/`provider_id` Many2one `required`,
`ondelete='cascade'`; `priority`, `ordinal` (compute), `active`, `llm_idle_timeout` (45),
`llm_round_timeout` (120), `skip_sync_fallback`; `create` idempotente (`model_create_multi`, super por
fila, 1586-1625); `unique(agent_id, provider_id)`. El uso de proveedores es de otro bloque.

### 1.4 Utilidades del bloque

| Archivo | Contenido | Notas |
|---|---|---|
| `utils/context_roles.py` | Fuente única de roles: `INJECTABLE_TYPES=(core,domain,locale)` (35), `MCP_LISTABLE_TYPES=(core,domain)` (40), `AGENT_LINK_EXCLUDED_TYPES=(core,discovery)` (44), `canonical_type` (57), `canonical_discovery_code` (78) | `from __future__ import annotations` (19): válido en 3.7. |
| `utils/context_utils.py` | `strip_xml_metadata` (12-45): quita `<?xml?>`, `<metadata>`, la raíz `<context>` y líneas en blanco; `resolve_placeholders` (48-91): `{locale}`, `{lang}`, `{user_lang}`, `{odoo_version}`, `{odoo_series}` | `except:` desnudos (76, 88). |
| `utils/context_code_scan.py` | Lee códigos de los archivos de `ai/contexts` (`read(8000)`) y decide si un módulo "sigue siendo dueño" de un código (`factory_row_blocks_incoming`, 80-90) | Sin Odoo. |
| `utils/knowledge_ownership.py` | Dominios de lectura (7-10), filtro en Python (19-25), propiedad en `create` (28-40), guarda de escritura (43-67) | §4. |
| `utils/knowledge_stamp.py` | `module_has_ai_knowledge` (8-14), `format_factory_knowledge_stamp` (17-20) | §5. |
| `utils/domain_index.py` | Puntuación de disparadores y formato de cabeceras/catálogo (§3.3); ICP `pns_ai_mcp.domain_index_inject` (29); `build_detection_triggers_prompt` (327-362) | Anotaciones `re.Pattern`, `typing` con `from __future__` (16): válido en 3.7. |
| `utils/copy_code.py` | `next_copy_code` (7-19): `<base>_copy`, `<base>_copy2`… | No lo usa ningún archivo del bloque (se usa al duplicar servidores). |
| `utils/ai_paths.py` | `module_kind_dir` (22-37): solo `<módulo>/ai/<kind>`; sin ruta antigua | |

---

## 2. Qué es un contexto, una skill y un agente

### 2.1 Contexto (`ai.context`)

Un fragmento de conocimiento o instrucciones que se pega en el prompt. El tipo (`context_type`) es
el **papel en la composición** (`utils/context_roles.py:11-18`, HECHO):

| Tipo | Se inyecta | Se enlaza a agentes | Se lista por MCP | Origen típico |
|---|---|---|---|---|
| `core` | Siempre, en **todos** los agentes (`ai_agent.py:306-313`) | No | Sí | `ai/contexts/core/` o `system/` |
| `domain` | Si está en `context_ids` del agente (fijo) o si lo activa el índice de dominios (por turno) | Sí | Sí | `ai/contexts/domain/` |
| `locale` | Igual que `domain`; adaptación lingüística (glosario, formatos) | Sí | **No** | `ai/contexts/locale/` |
| `discovery` | **Nunca** (no es texto: es una fila de enrutado) | No | No | `ai/contexts/discovery/*.json` |

- Variantes por idioma: misma `base_code`, distinto `locale`. Al componer se elige una por
  `base_code`: la del idioma del usuario, si no la neutra, si no `en_US` (solo `locale`), si no la
  única (`ai_context.py:742-754`). `locale` sale de los metadatos (`<locale_code>`, `locale:`), del
  sufijo del código o, para `locale`, de un atributo interno; `is_fallback=true` fuerza neutro
  (3167-3197).
- `discovery`: `discovery_target_kind` = `domain` (cargar un paquete), `api_server` (pista para usar
  `api_call` con un servidor externo) o `url_whitelist` (fase 2, sin uso). Los de `api_server` se
  crean también desde `ai.api.server` (`_apply_detection_defaults`, 365-413; `_refresh_detection_identity`,
  1546-1568).

### 2.2 Skill (`ai.skill`)

Procedimiento seleccionable (`/comando` en Chatboo o prompt MCP `skill.<comando>`): `content` (prosa)
+ `code_body` opcional (Python) + contextos referenciados (`build_prompt_payload`, 607-639).

- **Dónde vive `code_body`**: como texto en la columna `code_body` de `ai_skill` (125). En los módulos
  viene de un `.py` junto al `.md` (`import_from_files`, 1364-1370) o del ZIP (`code/<code>.py`,
  1162-1168). Al servir la skill se pega **literalmente en el prompt** dentro de un bloque
  ```` ```python ```` (615-632), así que el LLM ve todo el código.
- **Quién la crea**: ACL de escritura/creación solo para `group_ai_writer` y `group_ai_admin`
  ([MAPA] §4.2 l.16, 20). Regla del Writer: solo propias y no de sistema
  (`security/security.xml:138-147`). Al crear, un Writer recibe `owner_id` automáticamente
  (`knowledge_ownership.py:37-39`); si los `vals` traen `is_system` o `source_module`, no se asigna
  dueño y la regla de creación (`owner_id = user`) lo rechaza (INFERENCIA, PENDIENTE). El asistente
  de captura (`pns_ai_mcp.skill.capture.wizard`, Writer) y Chatboo (`_require_skill_author`, 679)
  son las vías de interfaz.
- **Quién la activa**: `active` y `show_in_slash` los cambia quien pueda escribir el registro (Writer
  las suyas, administrador todas). `show_in_slash=False` se guarda además en la ICP
  `pns_ai_mcp.skills_slash_hidden` para que sobreviva a la resincronización (456-467, 1488-1501).
  Visibilidad en tiempo de ejecución: `agent_ids` vacío = global; con agentes, solo esos
  (`get_for_agent`, 556-568), siempre filtrando "sin dueño o mía".
- La **ejecución** de `code_body` (sandbox, `bootstrap_skill_code_body`, validación AST) es el
  bloque 6. Aquí solo consta que **guardar** un skill ya lo ejecuta una vez (§1.2).

### 2.3 Agente (`ai.agent`)

- `endpoint` (MCP): el LLM está en el cliente (Cursor, Claude Desktop). El agente solo sirve el
  prompt compilado, los contextos, las herramientas y las skills.
- `inference` (Chatboo, OCR…): el LLM se llama desde Odoo con la cadena de proveedores
  (`provider_ids`, `max_agent_rounds`).
- Agentes de módulo: `origin='module'`, `module_name`; no se pueden borrar (285-295) ni crear desde
  la interfaz (273-283). `pns_ai_mcp` crea uno: `ai_agent_mcp`, código `pns_ai_mcp`, tipo
  `endpoint`, `default_context_codes='@pns_ai_mcp'`, `required_context_codes='self_mcp'`
  (`data/ai_agent_data.xml:8-21`, `noupdate="1"`). El código del agente es "el nombre del módulo"
  (68) y el agente de `/mcp` sin ruta es `MCP_BARE_AGENT_CODE` (`ai_agent_consumer.py:53-56`).
- Composición de fábrica ("doble cable"): **push** = el archivo declara `agent_codes` o, si no, se
  enlaza a los agentes del mismo módulo (`_resolve_import_agent_codes`, 2116-2146; `pns_ai_mcp`
  siempre al agente `pns_ai_mcp`, 2143-2145); **pull** = el agente pide códigos o `@módulo` en
  `default_context_codes` (`wants_context_code`, 511-530). `required_context_codes` se vuelve a
  enlazar tras cada `write`/`create` (`_restore_required_context_links`, 485-505).

---

## 3. Cómo se compone el prompt de un agente

### 3.1 Orden del texto (HECHO)

`ai.agent.get_content(user_locale, force_rebuild, active_user)` (1142-1180):

1. **Parte compartida** (cacheable), `_build_shared_content` (412-428):
   - Contextos = `context_ids` activos del agente (sin paquetes de identidad de otro agente,
     862-876) **∪ todos los `core` activos** (335-338), **sin** los que tienen dueño (339), y **sin**
     los códigos del índice de dominios si la inyección está activa (340-346).
   - Cabecera `Agent=<code> | Locale=<locale> | Contexts=<n>` (422-424).
   - Cuerpos sin metadatos (`strip_xml_metadata`), uno por `base_code`, en orden
     **core → locale → domain** y alfabético dentro de cada tipo (`ai_context.py:756-777`).
   - `---` + **directiva de idioma** ("MANDATORY LANGUAGE RULE: You MUST always respond in
     <idioma>…", `ai_context.py:1034-1051`).
2. **Parte del usuario** (nunca se cachea), `_build_user_owned_content` (430-443): contextos del
   agente con `owner_id` = usuario actual, bajo `## User knowledge`.
3. **Identidad**, `_apply_resolved_identity` (1313-1315 → `utils/agent_identity.py:154-181`): antepone
   un bloque de nombre de producto y otro de autor, resueltos en cascada: registro Python del
   módulo → metadatos `product_name`/`vendor` del paquete `self_*` propio → `ai.agent.name` /
   `ir.module.module.author` (1277-1311).
4. **Cola del índice de dominios** (fuera de `get_content`):
   - MCP `prompts/get system_prompt`: `get_for_agent` + `enrich_with_domain_index(query)`
     (`controllers/main.py:1578-1598`). Con `arguments.query` añade los cuerpos de los paquetes que
     casen; sin ella, un catálogo compacto de códigos y disparadores (`domain_index.py:244-274`).
   - Chatboo: `AgentEngine.get_system_prompt` (`utils/agent_engine.py:631-723`) añade al final
     "datos de ejecución": fecha del servidor, dominios de la lista blanca, catálogo de herramientas
     externas, bloque de pantalla y los paquetes casados.

Observación (HECHO): el docstring dice que la directiva de idioma va "LAST" (`ai_context.py:1042`),
pero en el texto final queda **antes** de "User knowledge" y de la cola del índice.

### 3.2 Contextos por defecto, obligatorios e idioma

- Por defecto: el agente MCP tira de `@pns_ai_mcp` = todos los no-core/no-discovery de este módulo
  (accounting, partners, dates, email, `self_mcp`, `corporate_terms*`, …). `core` no se lista nunca
  (114-121); se inyecta igual.
- Obligatorio: `self_mcp` (identidad). Si existe en el catálogo, no se puede quitar
  (`_restore_required_context_links`); "Defaults" falla si falta (`_assert_required_contexts_present`,
  851-860).
- Idioma: `user_locale` explícito, si no `context['lang']`, si no `en_US` (301-304). En MCP lo da el
  usuario de la API key (`controllers/main.py:1570-1572`); en el `_register_hook` el entorno no tiene
  `lang`, así que la caché se construye en `en_US` (INFERENCIA).
- **INFERENCIA importante (PENDIENTE)**: `_sync_composition_and_cache` (1346-1355), que se ejecuta en
  cada sincronización de fábrica (`hooks.py:245-256`), deja en `context_ids` **un solo registro por
  `base_code`, el neutro** (`normalize_context_ids`, `ai_context.py:984-1013`). Y
  `assemble_context_parts` solo elige variantes **entre los registros que recibe** (683-701). Resultado
  probable: un usuario `es_ES` recibe en la parte fija `corporate_terms` en inglés (formato
  `1,234.56`, "Customer" en vez de "Cliente") y nunca `corporate_terms_es_ES`. Los paquetes del índice
  (p. ej. `hr_payroll`) no tienen este problema porque se resuelven con `get_context_for_country`
  (`agent_engine.py:745-766`). Comprobar con `odoo-dev 14 shell`: `context_ids` del agente
  `pns_ai_mcp` y si `cached_content` en `es_ES` contiene "1.234,56".

### 3.3 Índice de dominios (discovery) y su inyección

- Interruptor único: ICP `pns_ai_mcp.domain_index_inject`, por defecto activo
  (`domain_index.py:29`, `ai_agent.py:348-355`).
- Entradas: filas `discovery` activas, una por `base_code`; si hay variante del idioma del usuario se
  **unen** sus disparadores con los genéricos (`ai_context.py:877-946`, `domain_index.py:308-324`).
  Se descartan objetivos `core` y servidores API inexistentes o inactivos (`domain_index.py:61-105`).
- Efecto en la caché: los códigos objetivo y sus `soft_depends` salen de la parte fija
  (`indexed_codes_from_entries`, 108-125; también por `base_code`, así que `hr_payroll_es_ES` sale con
  `hr_payroll`). Con los JSON de este módulo quedan **fuera de la caché**: `account`,
  `accounting_imbalances`, `business_documents`, `cost_accounting`, `fetch_url_recipe`, `filters`,
  `geo`, `geography`, `hr_contracts`, `hr_payroll` (+ variantes), `hr_payroll_accounting_present`,
  `invoice_concepts`, `partners`, `trial_balance` (+ `_es_ES`). Quedan **siempre**: `system_prompt`,
  `self_mcp`, `dates`, `email`, `sale_order_duplicate_workflow`, `corporate_terms` (INFERENCIA a
  partir de los JSON).
- Coincidencia (`match_domains`, `domain_index.py:166-210`): texto en minúsculas y sin acentos;
  disparador de una palabra = palabra completa, de varias = subcadena; puntuación = nº de palabras del
  disparador; orden por (puntuación, prioridad); máximo 2 paquetes (`DEFAULT_MAX_PACKS`, 26) más sus
  `soft_depends`; servicios API hasta 4 sin gastar ese cupo.
- Inyección (`agent_engine.py:768-854`): cabecera `[DOMAIN_PACKS codes=… elapsed_ms=…]` + cuerpos;
  para servicios, `[EXTERNAL_SERVICE codes=…]` "use propose api_call with server code …"
  (`domain_index.py:223-241`). Cada turno con mensaje registra en `ai.log` los primeros 480
  caracteres del mensaje del usuario (`agent_engine.py:823-839`).
- `discovery_geo` apunta a `geo`, que **no existe en `pns_ai_mcp/ai/`** (HECHO, inventario de §7);
  sin otro módulo que lo traiga, el turno queda en `inject_miss`.

### 3.4 Caché (`cached_content`) y cuándo se reconstruye

- Clave: `cache_locale` == idioma pedido **y** `cache_context_signature` == firma actual; la firma es
  `id:write_date` de cada contexto de la parte compartida, ordenados por código (878-884).
- Se reconstruye (HECHO):
  - con `force_rebuild=True` (escritura ORM con `sudo`, 1163-1169): "Defaults" (931), "Restaurar
    desde módulo" (971), `_sync_composition_and_cache` (1354, llamado por la sincronización de
    fábrica y por `import_agent_zip`, `ai_context.py:2993`), `action_rebuild_cache` (1384-1387),
    Ajustes (`res_config_settings.py:300`) y migraciones;
  - si no coincide la clave: se compila y se guarda en **otro cursor con `commit`** por SQL directo
    (`_persist_cache_isolated`, 1317-1336);
  - tras cualquier importación de contextos, `_invalidate_agent_caches_after_import` pone a NULL la
    caché de todos los agentes (SQL directo, `ai_context.py:1938-1974`).
- Consecuencias (INFERENCIA, PENDIENTE de medir):
  - Una sola caché por agente y **un solo idioma**: usuarios de idiomas distintos se la van pisando
    y cada cambio de idioma recompila y escribe.
  - `record_context_usage` actualiza `write_date` (`ai_context.py:1416`) cada vez que se consulta un
    contexto por `prompts/get`/`get_context` (`controllers/main.py:1684, 2029`,
    `controllers/tools_context.py:313`): si el contexto consultado está en la parte compartida, la
    firma cambia y la siguiente petición recompila.
  - `_persist_cache_isolated` no fija `lock_timeout`: si la transacción en curso ya tiene bloqueada
    la fila de `ai_agent` (p. ej. tras un `write` del agente) y después se llama a `get_content` sin
    `force_rebuild`, el segundo cursor esperaría a la propia transacción (autobloqueo sin detección
    por PostgreSQL). No se ha visto un camino concreto que lo dispare. PENDIENTE.
  - Cualquier usuario interno puede forzar recompilación por RPC (`action_rebuild_cache`,
    `get_content(force_rebuild=True)`): lectura sobre `ai.agent` basta y la escritura va con `sudo`.

---

## 4. Propiedad, visibilidad y `skip_hardcoded_restrictions`

### 4.1 Reglas de propiedad (HECHO)

- `owner_id` vacío = conocimiento de módulo/importación, visible para todos los usuarios internos;
  con dueño = privado del dueño (reglas en [MAPA] §4.3; filtro equivalente en Python
  `filter_visible_records`, `knowledge_ownership.py:19-25`).
- `is_system` (skills) y `context_type='core'` (contextos) marcan registros de fábrica protegidos.
- Escritura del Writer: solo registros propios no-core/no-sistema (reglas `*_writer_write_rule`);
  además, en Python, `assert_writer_can_write_records` (`knowledge_ownership.py:43-67`) y los
  `write`/`unlink` de cada modelo.
- `unlink` de contextos: además bloquea `core` y filas de fábrica cuyo archivo siga en disco
  (`_is_shipped_factory_locked`, `ai_context.py:1609-1627`).

### 4.2 Puntos donde se comprueba el contexto

| Dónde | Qué se salta con la clave |
|---|---|
| `utils/import_export_guard.py:9-10` (`ensure_ai_admin`) | Toda la comprobación "solo AI Administrator" de importar/exportar/restaurar (todas las llamadas de §1.1-1.3 que la usan) |
| `utils/knowledge_ownership.py:51` | La guarda "solo tus registros" en Python |
| `models/ai_context.py:1520` (`write`) | La guarda anterior, "core es solo lectura para Writers" (1523), "solo administradores cambian el dueño" (1527) y "los core no se modifican" para todos, incluidos administradores (1531-1537) |
| `models/ai_context.py:1635` (`unlink`) | La guarda de dueño y el bloqueo de core/archivo de fábrica en disco |
| `models/ai_skill.py:515` (`write`) | La guarda de dueño, "sistema es solo lectura para Writers" (518) y "solo administradores cambian el dueño" (522) |
| `models/ai_skill.py:535` (`unlink`) | La guarda de dueño y "los de sistema no se borran" |

El propio módulo lo pone en: `hooks.py:116,137,170,183`; `ai_context.py:1274,1567,1696,2506,3211`;
`ai_agent.py:969,1013`; `ai_skill.py:821,861,1328,1575,1611`; `wizard/mcp_context_tools_wizard.py:30`;
`models/external_server.py:569,653,801` y migraciones.

### 4.3 ¿Puede llegar desde el navegador? ¿Qué permite realmente?

- **Sí puede llegar** (HECHO, core 14): `call_kw` aplica tal cual el `context` que envía el cliente
  (`odoo/api.py:369-392`). Solo se bloquean por RPC los métodos que empiezan por `_`
  (`odoo/models.py:116-119`); `write`, `unlink` y todos los métodos públicos citados se pueden
  llamar con `{'skip_hardcoded_restrictions': True}`.
- **Lo que el ORM sigue aplicando**: ACL y record rules. Pero en Odoo 14 `write` comprueba las reglas
  **antes** de escribir y no vuelve a comprobarlas después (`odoo/models.py:3593-3595`; la única
  comprobación posterior es la de `create`, 4073). Por tanto la regla del Writer
  (`owner_id = user` y no core / no sistema) se cumple sobre el registro **antes** del cambio, no
  sobre el resultado.

Escenarios (INFERENCIA, con el código y las reglas citados; **PENDIENTE de reproducir con
`odoo-dev 14`** con un usuario Writer y llamadas RPC):

1. **Writer → conocimiento global en el prompt de todos.** El Writer crea un contexto (queda suyo),
   lo enlaza a un agente escribiendo `agent_ids` del propio contexto (la regla solo mira el
   contexto) y después hace `write({'owner_id': False})` o `write({'context_type': 'core'})` con la
   clave. La regla previa se cumple (era suyo y no core) y la guarda Python se salta. Resultado:
   - `owner_id=False` + enlazado → entra en la parte compartida del agente para **todos** los
     usuarios;
   - `context_type='core'` → entra en el prompt de **todos los agentes** (`_system_contexts`,
     `ai_agent.py:306-313`);
   - en ambos casos el Writer pierde el control del registro (ya no es suyo) y solo un administrador
     lo ve en la lista como "de fábrica".
   Es inyección persistente de instrucciones al LLM de otros usuarios, incluidos administradores que
   confirman operaciones (bloque 3).
2. **Writer → skill global.** Igual con `ai.skill`: `write({'owner_id': False})` con la clave
   convierte su skill (con `code_body`) en visible para todos; `is_system=True` además la hace
   imborrable para Writers.
3. **Usuario interno sin grupo IA** con la clave: pasa `ensure_ai_admin`, pero las escrituras fallan
   por ACL (`ai.context`/`ai.skill` 1,0,0,0). Efectos que sí ocurren porque no pasan por el ORM o
   usan `sudo` (ver 4.4): `import_system_from_files` → `_import_all_from_module` captura las
   `AccessError` archivo por archivo (`ai_context.py:2523-2526`) y llega a
   `_purge_retired_self_source_files` (borrado de carpetas en disco, si existen) y a
   `_invalidate_agent_caches_after_import` (SQL directo que vacía la caché de todos los agentes).
   Exportar todo a ZIP le devuelve lo que ya podía leer.

### 4.4 Métodos públicos sin `ensure_ai_admin` que escriben con `sudo` o SQL directo

No necesitan la clave (HECHO en el código; alcance real PENDIENTE):

| Método | Línea | Efecto | Quién lo puede llamar (INFERENCIA) |
|---|---|---|---|
| `ai.skill.unlink_named_factory_skills(names)` | `ai_skill.py:1598-1626` | **Borra con `sudo`** las skills sin dueño cuyo código, comando o ruta coincidan | Cualquier usuario con sesión (incluso portal: `call_kw` no comprueba ACL del modelo y el método usa `sudo`) |
| `ai.skill.unlink_retired_from_module(module)` | 1551-1596 | Borra con `sudo` skills de fábrica cuyo `.md` ya no está en disco | Idem |
| `ai.skill.hide_unprefixed_slash_twins()` | 848-890 | Borra con `sudo` skills "gemelas" sin prefijo (también de usuarios) si hay prefijo de comando configurado | Idem |
| `ai.skill.reapply_source_module_prefixes(...)` | 751-832 | Renombra con `sudo` códigos/comandos de las skills de un módulo | Idem |
| `ai.skill.sync_slash_hidden_from_field()` | 486-498 | Escribe la ICP de ocultos con `sudo` | Idem |
| `ai.context.record_context_usage(code)` | `ai_context.py:1399-1426` | SQL directo: contadores y `write_date` de cualquier contexto por código | Idem |
| `ai.agent.get_content(force_rebuild=True)`, `action_rebuild_cache` | `ai_agent.py:1142-1171, 1384` | Reescribe la caché con `sudo` | Usuarios internos (necesita leer `ai.agent`) |

Además, **fuga entre usuarios por el índice de dominios** (INFERENCIA, PENDIENTE): el motor lee las
filas `discovery` y los cuerpos con `sudo` (`agent_engine.py:738,743,749-766`), ignorando la regla
"sin dueño o propios". Un Writer puede crear, sin ninguna clave, un contexto propio y una fila
`discovery` propia (la regla de creación solo prohíbe `core`) cuyo disparador sea una palabra común
("factura"): el cuerpo de su contexto **privado** se inyectaría en el turno de cualquier otro usuario
que la escriba, y su código y disparadores aparecerían en el catálogo MCP de todos
(`format_index_catalog`).

---

## 5. Sincronización del conocimiento de fábrica en cada arranque

Flujo completo del hook en [MAPA] §3.1; aquí, qué escribe y cuándo.

- **Cuándo** (HECHO): `ai.context._register_hook` (415-431) → `maybe_sync_factory_knowledge`
  (`hooks.py:217-234`). En 14, `_register_hook` se llama al terminar `load_modules`
  (`odoo/modules/loading.py:566-574`), que se ejecuta en `Registry.new` (`odoo/modules/registry.py:72-89`):
  al cargar el registro en **cada proceso** (cada worker al primer acceso a la BD) y en cada recarga
  por señal (`check_signaling`, 605-622). El cursor de `load_modules` hace `commit` al salir.
- **Coste fijo en cada carga**: recorre todos los módulos `installed` y mira en disco si tienen
  `ai/contexts` o `ai/skills` (`hooks.py:197-214`, `knowledge_stamp.py:8-14`) para calcular el sello
  `nombre:versión|…`; lo compara con la ICP `pns_ai.factory_knowledge_stamp`.
- **Sincroniza** si el sello cambió o la ICP está vacía: tras `-u` de **cualquier** módulo que traiga
  `ai/` (el sello los incluye a todos), al restaurar una copia sin esa ICP, o si se instala en disco
  un módulo con `ai/` nuevo. Solo sincroniza el conocimiento **de `pns_ai_mcp`**
  (`module_name='pns_ai_mcp'`, `hooks.py:169-184`).
- **Qué escribe** (HECHO):
  1. `ai.context`: crea o **sobrescribe** cada contexto de fábrica sin dueño (`content`,
     `description`, `context_type`, `rel_path`, `source_module`, `locale` y **`active`**, que vuelve a
     `True` salvo que el archivo diga otra cosa; `ai_context.py:2424-2435, 2505-2507`). Los que tienen
     dueño se saltan (2465-2472). No borra nunca (2528-2532).
  2. Vuelve a enlazar los contextos a los agentes (push + pull, 2508-2510): **reañade los que un
     administrador hubiera quitado** del agente.
  3. Borra del disco `ai/contexts/domain/self/` de cualquier addon instalado si existe (1646-1677) y
     borra/archiva filas `self*` retiradas (1679-1739).
  4. Vacía la caché de todos los agentes (SQL, 1924-1974).
  5. Skills de `pns_ai_mcp`: ninguna (§1.2); `import_from_files` escribiría también `agent_ids`
     `(6, 0, …)` y `active` desde el archivo (`ai_skill.py:1417-1437`).
  6. `_sync_agent_caches`: normaliza `context_ids` (un registro por `base_code`) y recompila con
     `force_rebuild` todos los agentes (`hooks.py:245-256`).
  7. Escribe el sello aunque los pasos anteriores hayan fallado (`hooks.py:192-193`).
- **Consecuencia funcional** (INFERENCIA): las ediciones de un administrador sobre contextos de
  fábrica (sin dueño) y los contextos archivados de `pns_ai_mcp` **se pierden** en la siguiente
  actualización de cualquier módulo con `ai/`. Para conservar un cambio hay que hacer una copia con
  otro código (o que tenga dueño).
- **Varios workers** (INFERENCIA, PENDIENTE): el bloqueo de `Registry.new` es por proceso, y la
  comprobación del sello no es atómica. En el caso normal (`-u` por línea de comandos) la sincronización
  ocurre en el proceso que actualiza y escribe el sello; los workers que recargan después lo ven igual
  y no hacen nada. Si el sello no coincide al arrancar varios workers a la vez, todos sincronizan en
  paralelo con `REPEATABLE READ`: el segundo choca en las mismas filas (`could not serialize access`),
  la excepción se captura sin `savepoint` (`hooks.py:177-191`) y la transacción de carga del registro
  queda abortada; esa petición falla y el worker lo reintenta en la siguiente. La invalidación de
  cachés sí usa `savepoint` y `SKIP LOCKED` (1938-1955).
- En la instalación la importación se hace dos veces (datos XML y `post_init_hook`, [MAPA] §3.1); el
  `_register_hook` del final ya ve el sello escrito y no repite (INFERENCIA, orden de
  `loading.py`: `post_init` por módulo antes del paso 8).

---

## 6. ¿Datos de la base de datos en contextos y prompt?

- **Contextos de fábrica**: solo texto fijo (reglas, modelos, campos, fragmentos de código de
  ejemplo con fechas ficticias como `2026-05-01`). No contienen clientes, empleados ni importes
  reales (HECHO, §7).
- **Lo que se añade desde la BD** (HECHO):
  - cabecera con código del agente, idioma y número de contextos (`ai_agent.py:422-424`);
  - identidad: `ai.agent.name`, `module_name`, `ir.module.module.author` (1264-1311);
  - "User knowledge": texto libre que hayan escrito los usuarios (puede contener cualquier dato);
  - catálogo del índice: códigos y disparadores de todas las filas `discovery` (también de otros
    usuarios, §4.4);
  - skills: `content`, `code_body`, contextos referenciados y los `ARGUMENTS` que teclea el usuario
    (`ai_skill.py:978-991`);
  - Chatboo (fuera del bloque): fecha, dominios de la lista blanca, catálogo de herramientas
    externas y **bloque de pantalla** (`agent_engine.py:672-722`). PENDIENTE (bloque del motor/Chatboo):
    qué datos del registro abierto lleva `screen_context_block`.
- **Datos de negocio que sí acaban en la conversación** (INFERENCIA): los contextos enseñan al LLM a
  consultar nóminas por empleado con DNI, bruto, IRPF y neto (`hr_payroll_es_ES.xml`,
  `hr_payroll_accounting_present.xml:72-86`), riesgo de cobro por cliente con NIF
  (`invoice_concepts.xml:41-50`), correos por dirección (`email.md:24-42`). Esos resultados viajan al
  proveedor LLM (externo en Chatboo o al cliente MCP). Es el flujo previsto, pero relevante para RGPD
  (bloques 4-6).
- `resolve_placeholders` (`context_utils.py:48-91`) solo sustituye idioma y versión de Odoo.

---

## 7. Contenido de `ai/`

### 7.1 `ai/contexts/core/system_prompt.xml` (entero, 136 líneas, `core`, v3.92)

Es el "protocolo" que reciben **todos** los agentes. Bloques:
- `core_directive` (11-26): actuar con herramientas sin excusas; preguntas de identidad en prosa;
  recursos fijos con `fetch_native_mcp_resource`; consultas con `relaxaicode` (sandbox "de solo
  lectura"); **escrituras con `propose_safe_operations`** (estado `pending_confirmation`, no decir que
  está hecho); `api_call` solo con servidores y herramientas del catálogo; paquetes con `get_context`
  (`contexts_index_core` y luego el código); **"You CAN access the internet via
  propose_safe_operations with op=fetch_url… Do NOT say 'I cannot access the internet'… Just call the
  tool"** (20); datos externos solo por `fetch_url` (21); no inventar datos internos (22); revisar
  antes la lista blanca (24); agrupar varias peticiones externas en una llamada porque "they
  auto-confirm and execute together" (25).
- `response_formatting` (28-47): concisión (<150 palabras), prosa frente a tablas, filas
  estructuradas, rankings, informes, `return_mode`, no repetir respuestas anteriores, idioma.
- `skills_protocol` (49-54): cómo listar skills, estructura procedimiento/código, contrato de autoría
  (forma de `result`, `param_schema`, `args_policy`, prefijos) y de contextos.
- `execution_environment` (56-77): variables del sandbox (`env`, `user`, `company`, `now`, `today`,
  **`ZoneInfo`**…).
- `coding_constraints` (79-112): reglas AST (sin `eval/exec`, sin `dir/locals`, sin
  `env.registry`, sin dunders), imports permitidos (incluye **`zoneinfo`**), forma de datos, nombres
  de campo, selecciones, autocorrección, filtros de glosario, cobertura de resultados.
- `odoo_images_in_html` (113-117) y `odoo_record_links` (118-120): URL `/web/image/...` y enlaces
  `/web#id=…&model=…`.
- `relational_writes` (121-134): tuplas x2many para `propose_safe_operations`; `op=field_required`;
  acciones de sistema `view.set_field_readonly/invisible/domain`, `view.reset_field_modifiers`,
  **`module.update` (install/upgrade/uninstall)**, **`user.add_group`/`user.remove_group`**; "Do NOT
  refuse with 'ask your administrator'. Authorization is the Confirm toast plus AI Administrator"
  (133).

**Instrucciones de acción** (HECHO): sí, muchas. Enseña a proponer escrituras de cualquier modelo,
peticiones HTTP externas (GET/HEAD/OPTIONS/QUERY), llamadas a APIs registradas, instalar/desinstalar
módulos y cambiar grupos de usuarios, y le pide expresamente no rechazarlas. La barrera real es la
confirmación y los grupos (bloque 3). Referencias a contextos que **no** trae `pns_ai_mcp`:
`presentation_grids`, `geo` (HECHO, inventario de `ai/`).

Compatibilidad: anuncia `ZoneInfo` precargado y `zoneinfo` importable (70, 84). En Python 3.7.3
`zoneinfo` no existe (3.9+); el sandbox lo omite si falla la importación
(`controllers/context_builder.py:222-224, 438-439`). INFERENCIA: el LLM generará código con `ZoneInfo`
que fallará con `NameError` y tendrá que reintentar.

### 7.2 `ai/contexts/domain/self_mcp/self_mcp.xml` (entero, 37 líneas, `domain`, v1.2)

Identidad del endpoint MCP: `agent_codes=pns_ai_mcp` (exclusivo), `is_fallback=true` (neutro). Dice
que el LLM está en el cliente, que sirve contextos, herramientas y skills "dentro de los permisos del
usuario", que no se presente como Chatboo, y cómo responder a "¿quién eres / quién te hizo / qué
puedes hacer?" usando los bloques de nombre y autor que antepone el servidor. No contiene acciones.
Es el `required_context_codes` del agente.

### 7.3 Resto de contextos (un párrafo por archivo; todos leídos enteros)

- **`domain/account.xml`** — `account.move` con `move_type` (14+) frente a `account.invoice` (≤13);
  convención de colores en compras por proveedor. Solo lectura. Campos verificados en el core 14
  (`account/models/account_move.py:157`).
- **`domain/accounting_imbalances.xml`** — sin bloque `<metadata>` (código por nombre de archivo).
  Asientos descuadrados y comprobación de un periodo con ejemplos de código. Los ejemplos terminan con
  la línea suelta `result` (43, 65), que `system_prompt.xml:81` prohíbe. Solo lectura.
- **`domain/business_documents.xml`** — presupuestos/pedidos/facturas/albaranes: **cómo crear y
  modificar** documentos (una cabecera, líneas con comando 0, escribir sobre el último documento
  confirmado, descuento global en `sale.order.line.discount`, precio en `price_unit`). Contiene
  instrucciones de escritura (vía propuesta).
- **`domain/cost_accounting.xml`** — `account.analytic.line` agrupado por `account_id.group_id`
  (`account.analytic.group` existe en 14: `analytic/models/analytic_account.py:35-36`); ingresos/gastos
  por signo. Solo lectura.
- **`domain/dates.xml`** — filtrar años con campos Date/Datetime, no con identificadores; años
  literales. Solo lectura.
- **`domain/email.md`** — `mail.mail` (enviados/recibidos por dirección) frente a `mail.message`
  con `pns_delivery_status`. HECHO: ese campo no existe en el core 14 ni en ningún `.py` de este repo;
  sin el módulo que lo añada, las consultas fallarán. Usa `date.today()`, contra la regla de
  `system_prompt.xml:84`. Solo lectura de correos (datos personales).
- **`domain/fetch_url_recipe/fetch_url_recipe.xml`** — cómo pedir datos externos con
  `propose_safe_operations op=fetch_url` (no `urllib`); ejemplo con
  `https://api.exchangerate.host/latest?...` (50); "Whitelisted domains auto-confirm; other domains
  wait for a human click" (62). Instrucciones de acceso a URLs.
- **`domain/filters.xml`** — `ir.filters`: "actualizar antes de crear" y cómo buscar la acción para
  favoritos. Instrucciones de escritura (vía propuesta).
- **`domain/geography.xml`** — país/provincia/ciudad, niveles administrativos (una comunidad no es
  `res.country.state`), búsqueda exacta, informar de datos ausentes. Solo lectura.
- **`domain/hr_contracts/hr_contracts.xml`** — contratos laborales: primero `hr.employee`, `hr.contract`
  solo si está instalado, nunca `contract.contract` (OCA). Solo lectura (datos de RR. HH.).
- **`domain/hr_payroll/hr_payroll.xml`** — cascada genérica de nóminas: contabilidad →
  `hr.payslip` → "sin datos". Solo lectura.
- **`domain/hr_payroll/hr_payroll_accounting_present.xml`** — cruza los totales contables por empresa
  con `hr.employee` por nombre y monta filas con DNI y foto. Contradicciones con `system_prompt.xml`:
  prohíbe `def` (42, cuando el protocolo los permite, 82) y pone `image_128` como booleano (77,
  cuando el protocolo lo prohíbe, 115). Solo lectura (datos sensibles).
- **`domain/hr_payroll/hr_payroll_es_ES.xml`** — España: bruto 640 (debe), IRPF 4751 y SS
  trabajador 476 (haber) por empresa; neto = bruto − IRPF − SS; respaldo `hr.payslip`
  (`hr_payroll` Enterprise/OCA, no core). Solo lectura.
- **`domain/hr_payroll/hr_payroll_en_US.xml`** — EE. UU.: cuentas 5100-5300 (debe). Solo lectura.
- **`domain/hr_payroll/hr_payroll_de_DE.xml`** — Alemania: cuenta 4100 (debe). Solo lectura.
- **`domain/hr_payroll/hr_payroll_es_AR.xml`** — Argentina: cuenta 411 (haber). Solo lectura.
- **`domain/hr_payroll/hr_payroll_es_MX.xml`** — México: cuenta 5100 (debe). Solo lectura.
- **`domain/hr_payroll/hr_payroll_fr_FR.xml`** — Francia: cuenta 421 (haber). Solo lectura.
- **`domain/hr_payroll/hr_payroll_it_IT.xml`** — Italia: cuenta 2120 (haber). Solo lectura.
- **`domain/hr_payroll/hr_payroll_pt_BR.xml`** — Brasil: cuentas 311 / 3.1.1 (haber). Solo lectura.
- **`domain/invoice_concepts.xml`** — correspondencias de facturas (base, total, impuestos,
  impagadas con `payment_state`, existe en 14: `account_move.py:238`), agrupación por cliente, análisis
  de riesgo (≥3 pagadas y ≥70 %), columnas fijas en español con NIF, periodos naturales. Solo lectura.
- **`domain/partners.xml`** — "cliente" = empresa con factura de venta publicada (nunca
  `customer_rank`), proveedores por `supplier_rank`, dirección con `contact_address`. Un patrón usa
  `calendar.event.customer_id`, que **no existe en el core 14** (HECHO: no aparece en
  `odoo/addons/calendar`); y `from datetime import datetime` + `datetime.now()` contra la regla de
  `now`/`today`. Solo lectura.
- **`domain/sale_order_duplicate_workflow.md`** — duplicar un pedido (`op: copy`) y luego modificar
  una línea (`op: write` sobre `sale.order.line`) en dos propuestas separadas; cómo construir la URL
  del pedido. Instrucciones de escritura (vía propuesta).
- **`domain/trial_balance/trial_balance.xml`** — balance de sumas y saldos por cuenta o por prefijo
  con 5 columnas fijas; neutro (`is_fallback`). Solo lectura.
- **`domain/trial_balance/trial_balance_es_ES.xml`** — igual con columnas en español (`codigo`,
  `cuenta`, `debe`, `haber`, `saldo`). Solo lectura.
- **`locale/corporate_terms/corporate_terms.xml`** — glosario inglés (neutro por `is_fallback`):
  formatos (`1,234.56`, CSV con coma, `MM/DD/YYYY`) y correspondencia término → modelo/contexto;
  menciona `acl_security` y `pns_acl_manager` (no incluidos). Usado también por
  `get_formatting_conventions`. Sin acciones.
- **`locale/corporate_terms/corporate_terms_es_ES.xml`** — glosario español (`1.234,56 €`, CSV con
  `;`, `DD/MM/YYYY`). Sin acciones. Ver §3.2 (probablemente no llega a la parte fija).
- **`discovery/*.json` (30 archivos)** — filas de enrutado, sin texto para el LLM, todas
  `source_module=pns_ai_mcp`, en pares neutro + `es_ES` (disparadores en inglés técnico y en
  español): `account` (70), `accounting_imbalances` (71), `business_documents` (74, `soft_depends`
  `partners`), `cost_accounting` (74), `fetch_url_recipe` (68), `filters` (65), `geo` (75, objetivo
  inexistente aquí), `geography` (73), `hr_contracts` (77), `hr_payroll` (80, `soft_depends`
  `hr_payroll_accounting_present`), `invoice_concepts` (78, `soft_depends` `partners`,
  `business_documents`), `partners` (72), `trial_balance` (76) y dos de tipo **`api_server`**:
  `cdmon` (dominios/DNS) y `sesame` (fichajes de RR. HH.), que solo actúan si existe un
  `ai.api.server` activo con ese código y entonces piden al LLM usar `api_call`.
- **`ai/skills/custom/.gitkeep`** — vacío.

---

## 8. `sudo()`, compatibilidad y riesgos

### 8.1 Usos de `sudo()` en los archivos del bloque (ninguno con comentario que lo justifique)

| Archivo:línea | Qué hace | Valoración |
|---|---|---|
| `ai_context.py:391` | Busca `ai.api.server` por código al crear una fila discovery | Lectura acotada; aceptable |
| `ai_context.py:874` | Códigos de servidores activos | Lectura; aceptable |
| `ai_context.py:1068`, `ai_agent.py:351`, `ai_skill.py:438,450` | ICP del índice y de ocultos | Normal |
| `ai_context.py:1621, 1784`; `ai_skill.py:1276` | `ir.module.module` | Inocuo |
| `ai_context.py:1961` | Todos los agentes para invalidar caché local | Inocuo |
| `ai_agent.py:368` | Códigos indexados (ver todas las filas discovery) | **Ignora la propiedad** (§4.4) |
| `ai_agent.py:1164` | Escribe la caché | Permite a cualquier usuario interno forzar escrituras |
| `ai_skill.py:489` | Siembra la ICP de ocultos | Público sin guarda; impacto bajo |
| `ai_skill.py:775, 859, 1573, 1609` | Renombra/borra skills de fábrica (y gemelas) | **Públicos sin guarda** (§4.4) |
| (fuera) `agent_engine.py:738, 743, 749` | Entradas discovery y cuerpos inyectados | **Ignora la propiedad** (§4.4) |

### 8.2 Odoo 14

- Correcto para 14 (HECHO): `@api.model_create_multi`, `@api.depends_context` (existe desde 13),
  `fields_get(allfields, attributes)`, `_register_hook`/`_auto_init` llamando a super, tuplas x2many,
  `ir.module.module.latest_version`. `_search(self, domain, *args, **kwargs)` es compatible con la
  firma de 14.
- `web_read` (`ai_agent.py:795-799`): no existe en 14; nunca se llama (código muerto).
- `ai.agent.create` con `@api.model` y manejo manual de listas (218-236): funciona en 14 (el core no
  avisa, HECHO: sin aviso de "create in batch" en `odoo/models.py`).
- `_auto_init` de `ai.context` recarga `views/assets.xml` ([MAPA] §3.4).
- `agent_engine.py:653` llama a `get_for_agent(agent_code, agent_code=…, user_locale=…)`, que daría
  `TypeError` (argumento duplicado); rama inalcanzable porque `resolve_inference_agent_code` ya exige
  que el agente exista. Fuera del bloque, anotado de paso.

### 8.3 Python 3.7.3

HECHO (búsqueda de sintaxis 3.8+ en los archivos del bloque y `hooks.py`): sin `:=`, sin
`dict | dict`, sin `removeprefix`, sin genéricos `list[...]` evaluados, sin `match`. Los
`from __future__ import annotations` (`context_roles.py:19`, `domain_index.py:16`) son válidos desde
3.7. **Compatible.** La única incompatibilidad es de contenido: `system_prompt.xml` anuncia `zoneinfo`
(§7.1).

### 8.4 Riesgos (de mayor a menor)

1. **Escalada de Writer a "conocimiento global"** mediante `skip_hardcoded_restrictions` por RPC:
   contexto propio → `owner_id=False` o `core`; skill propia → `owner_id=False`/`is_system`. Inyecta
   instrucciones en el prompt de todos los usuarios y agentes (§4.3). INFERENCIA fuerte, PENDIENTE.
2. **Borrado de skills de fábrica por cualquier usuario autenticado** con
   `unlink_named_factory_skills` / `unlink_retired_from_module` / `hide_unprefixed_slash_twins`
   (`sudo`, sin guarda) (§4.4). PENDIENTE (incluido portal).
3. **Fuga de contextos privados entre usuarios** por el índice de dominios leído con `sudo` (§4.4).
   PENDIENTE.
4. **Pérdida de configuración en cada actualización**: la sincronización de fábrica sobrescribe y
   reactiva contextos sin dueño y reenlaza los quitados (§5).
5. **Glosario/idiomas**: probablemente el glosario español no llega a la parte fija tras normalizar
   (§3.2).
6. **Prompt que empuja a actuar**: el protocolo pide no rechazar instalar módulos o cambiar grupos y
   proponer peticiones externas sin dudar; las de dominios en lista blanca se confirman solas (§7.1;
   barrera real en bloque 3).
7. **Caché**: una por agente y un idioma; `record_context_usage` y cualquier usuario pueden
   invalidarla o reescribirla (§3.4); posible autobloqueo de `_persist_cache_isolated`.
8. **Arranque**: cálculo de sello en disco en cada carga del registro; sincronización paralela con
   varios workers si el sello no coincide; borrado de carpetas de addons en disco (§5).
9. **Contenido con errores**: campos que no existen en 14 (`pns_delivery_status`,
   `calendar.event.customer_id`), objetivo `geo` ausente, contradicciones con el propio protocolo,
   `zoneinfo` en 3.7 (§7).
10. Datos personales (nóminas, DNI, correos) que el conocimiento enseña a extraer y que salen al LLM
    (§6).

---

## Resumen del bloque

**Qué es.** `ai.context` guarda conocimiento en texto (tipos `core` siempre inyectado, `domain`,
`locale` y `discovery` = filas de enrutado); `ai.skill` guarda procedimientos con Python
(`code_body` en BD, se pega entero en el prompt y se ejecuta una vez al guardar); `ai.agent` compone
el prompt (endpoint MCP o inferencia) y lo cachea en `cached_content`.

**Prompt.** Identidad + cabecera + core/locale/domain sin metadatos + directiva de idioma +
"User knowledge" del usuario + cola del índice de dominios (paquetes que casan con el mensaje, máx.
2 + dependencias, o catálogo). El agente MCP tira de `@pns_ai_mcp` y exige `self_mcp`. Caché única
por agente e idioma; se invalida por `write_date` de los contextos (que `record_context_usage` toca
en cada consulta), por importaciones y por acciones "Restaurar/Defaults".

**Datos.** Los contextos de fábrica son texto fijo, sin datos de clientes ni importes; enseñan a
consultar nóminas, DNI, NIF y correos, que sí viajan al LLM.

**Arranque.** Cada carga del registro calcula un sello de versiones; si cambia (tras `-u` de
cualquier módulo con `ai/`), resincroniza: sobrescribe y reactiva contextos de fábrica sin dueño,
reenlaza los quitados, borra carpetas `ai/contexts/domain/self/` en disco, vacía y recompila cachés.
Con varios workers y sello desfasado puede sincronizar en paralelo y abortar transacciones.

**Riesgos principales.**
1. `skip_hardcoded_restrictions` llega por RPC: un Writer puede convertir su contexto o skill en
   global o `core` (las reglas de 14 se comprueban antes del `write`). Inyección persistente en el
   prompt de todos.
2. Métodos públicos con `sudo` y sin guarda permiten a cualquier usuario autenticado borrar skills de
   fábrica.
3. El índice de dominios lee con `sudo`: contextos privados de un Writer pueden inyectarse en turnos
   de otros.
4. Ediciones del administrador sobre contextos de fábrica se pierden en cada actualización.
5. Probable: el glosario `es_ES` no llega a la parte fija; una sola caché por idioma.
6. El protocolo empuja a proponer instalaciones, cambios de grupos y peticiones externas.
7. Contenido con campos inexistentes en 14 y `zoneinfo` (no existe en Python 3.7.3).

**Compatibilidad.** Python 3.7.3: compatible. Odoo 14: compatible; `web_read` es código muerto.

**Configuración relevante.** ICP `pns_ai_mcp.domain_index_inject` (activo por defecto),
`pns_ai_mcp.skills_slash_hidden`, `pns_ai.factory_knowledge_stamp`; agente `ai_agent_mcp`
(`noupdate`); grupos Writer/Admin ([MAPA] §4.1); servidores `cdmon`/`sesame` activan sus filas
`api_server`. Para conservar cambios en contextos de fábrica: copiarlos con otro código.

---

## Tabla de cobertura

| Archivo | Líneas | Lectura |
|---|---|---|
| `models/ai_context.py` | 3483 | Entero (3 tramos) |
| `models/ai_skill.py` | 1838 | Entero (2 tramos) |
| `models/ai_agent.py` | 1633 | Entero (2 tramos) |
| `models/ai_agent_consumer.py` | 82 | Entero |
| `utils/context_roles.py` | 88 | Entero |
| `utils/context_utils.py` | 91 | Entero |
| `utils/context_code_scan.py` | 90 | Entero |
| `utils/knowledge_ownership.py` | 67 | Entero |
| `utils/knowledge_stamp.py` | 20 | Entero |
| `utils/domain_index.py` | 362 | Entero |
| `utils/copy_code.py` | 19 | Entero |
| `utils/ai_paths.py` | 37 | Entero |
| `ai/contexts/core/system_prompt.xml` | 136 | Entero (análisis completo) |
| `ai/contexts/domain/self_mcp/self_mcp.xml` | 37 | Entero (análisis completo) |
| `ai/contexts/domain/` (`.xml` y `.md`, 11) y subcarpetas `fetch_url_recipe`, `hr_contracts`, `hr_payroll` (10), `trial_balance` (2) | 30-129 c/u | Enteros (un párrafo cada uno) |
| `ai/contexts/locale/corporate_terms/*.xml` (2) | 73, 63 | Enteros (un párrafo cada uno) |
| `ai/contexts/discovery/*.json` (30) | 12-28 c/u | Enteros (párrafo conjunto) |
| `ai/skills/custom/.gitkeep` | 0 | Vacío |
| Consultados parcialmente (fuera del bloque) | — | `hooks.py:1-257`, `utils/import_export_guard.py:7-17`, `utils/agent_engine.py:630-866`, `controllers/main.py:1570-1614`, `utils/agent_identity.py:154-181`, `utils/compat.py:48-71`, `security/security.xml`, `data/ai_agent_data.xml` |

No quedan archivos del bloque sin leer.

---

## Preguntas abiertas

1. ¿Qué usuarios tendrán `AI Writer` en producción? Con el riesgo 1, un Writer equivale en la
   práctica a poder escribir en el prompt de todos.
2. ¿Se han editado a mano contextos de fábrica (sin dueño) en la base de datos del cliente? Se
   perderán en la próxima actualización de cualquier módulo con `ai/`.
3. ¿Qué otros módulos `pns_*` con `ai/` se instalarán (Chatboo, geo, ACL, `presentation_grids`)? Los
   necesita el conocimiento de este módulo (`geo`, `presentation_grids`, `acl_security`,
   `pns_delivery_status`).
4. ¿Qué idioma tienen los usuarios? Si conviven `es_ES` y otros, la caché única se recompilará a
   menudo; y hay que confirmar si el glosario español llega al prompt (§3.2).
5. ¿Se van a dar de alta los servidores `cdmon` o `sesame`? Activan pistas `api_call` y, en Sesame,
   datos de fichajes de empleados.
6. ¿Cuántos workers tiene el servidor del cliente y se arrancan a la vez tras actualizar? (§5,
   sincronización en paralelo).
7. ¿Está montada la carpeta de addons en solo lectura? Si no, la sincronización puede borrar
   carpetas `ai/contexts/domain/self/` de los addons.
8. PENDIENTE de comprobar con `odoo-dev 14` (lista para la etapa de pruebas): (a) escenarios 1 y 2 de
   §4.3 con un Writer por RPC; (b) llamada a `ai.skill.unlink_named_factory_skills` con un usuario
   interno sin grupo IA y con un usuario portal; (c) fuga por discovery de §4.4; (d) `context_ids`
   del agente `pns_ai_mcp` tras la sincronización y `cached_content` en `es_ES`; (e) que lo importado
   por ZIP queda con `owner_id` del administrador; (f) qué escribe `_register_hook` en el log al
   arrancar con el sello igual y distinto.
