# Análisis: pns_ai_mcp — Bloque 1: mapa y configuración (Odoo 14.0, rama 14.0-analisis-pns-ai)

> Documento de análisis, **no** es una especificación de diseño ni propone código.
> `pns_ai_mcp` es código de terceros (PATANEGRA Soft, Apache 2.0) y no se modifica.
>
> - Fuente: copia de trabajo `/home/soporte/GitHub/third_party/pns_ai_mcp/`. No se ha consultado
>   `/opt/odoo-src/14.0/third_party`.
> - Referencia del core: `/opt/odoo-src/14.0/odoo/` (prefijo `core:` en las citas, relativo a esa
>   ruta). Las rutas sin prefijo son relativas a `pns_ai_mcp/`.
> - Lo que ya explica `docs/specs/analisis_pns_base.md` (en adelante **[BASE]**) no se repite: se
>   cita su apartado.
> - Notación: **HECHO** (archivo:línea verificado), **INFERENCIA** (deducción no ejecutada),
>   **PENDIENTE** (se comprobará con `odoo-dev 14`).
> - Alcance del bloque 1: `__manifest__.py`, `__init__.py`, `hooks.py`, `http_patch.py`,
>   `constants.py`, `security/`, `data/`, `views/`, `wizard/`, `models/res_config_settings.py`,
>   `models/ir_ui_menu.py`, `models/ir_model_fields_selection.py`, `models/mcp_log_delete_menu.py`
>   y un índice de `migrations/`. Del resto del módulo solo hay inventario (§2) y, cuando hizo falta
>   para entender un archivo del bloque, comprobaciones puntuales que se citan con su línea.

---

## 1. Manifest (`__manifest__.py`)

### 1.1 Claves

| Clave | Valor | Línea | Observación |
|---|---|---|---|
| `name` | `AI Engine` | 6 | Nombre visible en Aplicaciones (inglés). |
| `version` | `3.1.486` | 7 | No sigue `14.0.x.y.z`. Odoo lo convierte en `14.0.3.1.486` (core: `odoo/modules/module.py:366,441-445`). Consecuencia grave sobre `migrations/` en §12.3. |
| `category` | `Patanegra AI` | 8 | Categoría de módulo nueva (Odoo la crea al vuelo). Distinta de la categoría de grupos `module_category_ai` (§4.1). |
| `summary` / `description` | inglés | 9-24 | Describe el protocolo PAAP, "two-box model" (proponer → autorizar → ejecutar) y servidor MCP. |
| `author` / `website` | `PATANEGRA Soft` / `/pns_ai_mcp/static/description/index.html` | 25-26 | URL relativa; `pns_base` la reescribe de todas formas ([BASE] §2.1). |
| `license` | `Other OSI approved licence` | 27 | Archivo `LICENSE` Apache 2.0. |
| `depends` | `['base', 'web', 'mail', 'bus', 'pns_base']` | 28 | `mail`: `mail.channel`, `mail.message`, subtipos `mail.mt_comment/mt_note` (`models/mcp_safe_operation.py:1962-2049`); `bus`: `bus.bus` (`utils/session_download.py:841`). |
| `external_dependencies.python` | `openpyxl, reportlab, requests, httpx, pydantic` | 29-34 | Ver §1.2. |
| `assets` | 5 CSS + 3 librerías JS + 16 JS `_v14` + 1 XML | 35-68 | **Clave ignorada en Odoo 14** (HECHO: no hay ninguna referencia a `'assets'` en `core: odoo/modules/`). En 14 los assets se cargan con `views/assets.xml` (§5.4). |
| `data` | 57 archivos | 69-126 | Orden en §1.3. |
| `qweb` | no existe | 127 | Comentario: "qweb key removed in Odoo 17+". En 14 `static/src/xml/mcp_field_widgets.xml` **no se carga**; no afecta porque los JS `_v14` no usan plantillas QWeb (HECHO: ningún `template:`/`qweb.render` en `static/src/js/*_v14.js`; el propio XML dice "OWL 2 templates … (Odoo 17+)", línea 2). |
| `installable` / `application` / `auto_install` | `True` / `True` / `False` | 128-130 | Aparece como aplicación ("AI Engine") en el menú principal. |
| `post_init_hook` / `uninstall_hook` | `post_init_hook` / `uninstall_hook` | 132-133 | §3.1. No hay `pre_init_hook`. |

### 1.2 Dependencias externas: dónde se usan

| Librería | Uso en el código (HECHO) | Observación |
|---|---|---|
| `requests` | `models/ai_provider.py:28`; `lib/llm/drivers/openai_driver.py:6`; `lib/llm/drivers/anthropic_driver.py:6`; `lib/api/drivers/openapi_driver.py:28`; `utils/mcp_client.py:10`; `controllers/safe_plan.py:1197` | Viene con Odoo 14 (requirements del core). |
| `openpyxl` | `controllers/formatters.py:309,337-338`; `utils/artifact_export.py:1552-1553` (importaciones locales dentro de funciones) | Exportación a XLSX. |
| `reportlab` | `controllers/formatters.py:602-603,618,637-641,729-733` (locales) | PDF/gráficos. Viene con Odoo 14. |
| `httpx` | **Ninguna importación.** Solo aparece como nombre prohibido en el sandbox (`controllers/validators.py:67`) y en comentarios (`lib/llm/utils/timeouts.py:11`, `utils/agent_engine.py:2636`). | Declarada pero no usada. |
| `pydantic` | **Ninguna importación** (el comentario del manifest, línea 32, habla de un "shim v1/v2" que no existe en el código). | Declarada pero no usada. |

HECHO (core: `odoo/addons/base/models/ir_module.py:336-347`, `odoo/modules/module.py:469-474`): Odoo 14
comprueba **todas** las librerías de `external_dependencies` al instalar o actualizar y aborta con
"Unable to install module … external dependency is not met". Por tanto, **si la imagen no trae
`httpx` y `pydantic`, el módulo no se instala**, aunque no los use. PENDIENTE: `odoo-dev 14 paridad`
o instalación de prueba para ver si la imagen local los trae.

### 1.3 `data` en orden (líneas 70-125)

1. `views/assets.xml` (70)
2. `security/security_groups.xml` (71), `security/security.xml` (72), `security/ir.model.access.csv` (73)
3. Vistas de modelos: `views/mcp_api_key_wizard_views.xml`, `views/mcp_user_views.xml` (define la raíz y las carpetas de menú), `views/mcp_safe_operation_views.xml` (74-76)
4. 27 vistas de asistentes `wizard/*_views.xml` (77-103)
5. `views/ai_context_views.xml`, `ai_domain_index_views.xml`, `mcp_change_journal_views.xml`, `mcp_log_views.xml`, `mcp_log_delete_menu_views.xml`, `ai_provider_views.xml`, `ai_agent_views.xml`, `url_whitelist_views.xml`, `ai_fx_source_views.xml`, `ai_skill_views.xml`, `ai_operator_menus.xml`, `external_server_views.xml`, `res_config_settings_views.xml` (104-116)
6. `data/ai_agent_data.xml` (117), `views/ai_menus.xml` (118)
7. `data/mcp_data.xml`, `external_server_data.xml`, `fx_source_data.xml`, `fetch_cache_cron.xml`, `api_result_cache_cron.xml`, `safe_operation_cron.xml`, `trusted_actions_system.xml` (119-125)

Fuera del manifest, cargados solo por `post_init_hook` (§3.1): `data/ai_provider_data.xml`,
`data/external_server_openapi_data.xml`, `data/url_whitelist_data.xml`,
`data/instance_defaults_data.xml` (`hooks.py:60-65`).

Fuera de todo: `views/mcp_field_widgets.xml` está **vacío** (0 bytes) y no figura en el manifest
(HECHO).

Orden correcto respecto a dependencias de XML ID: las carpetas de menú `menu_ai_security`,
`menu_ai_knowledge`, `menu_ai_connections` se definen en `views/mcp_user_views.xml:141-155`, antes
que todos los menús hijos; `views/ai_menus.xml` va después de las acciones que referencia.

---

## 2. Inventario del módulo (para repartir los bloques 2-4)

Tamaños: no se han contado líneas; cuando se conoce un mínimo por una cita se indica "≥ N líneas".

### 2.1 `models/` (26 archivos)

| Archivo | Modelo / clase | Propósito deducido |
|---|---|---|
| `__init__.py` | — | Importa los 25 módulos de modelos (líneas 6-31). |
| `mcp_user.py` | `ai.mcp.user` (Model) | Usuario MCP: hash SHA-256 de la API key por usuario, flags de grupos IA, último cliente MCP. |
| `mcp_api_key_wizard.py` | `pns_ai_mcp.api_key_wizard` (Transient) | Generar/importar/borrar la API key (leído entero, ver §8). |
| `ai_log.py` | `ai.log` | Registro de auditoría: una fila por operación IA/MCP. |
| `ai_change_journal.py` | `ai.change.journal` | Diario permanente de mutaciones ERP aplicadas vía Safe Plan, con reversión. |
| `mcp_log_delete_menu.py` | `pns_ai_mcp.log_delete_menu` (Transient) | Asistente de borrado de logs (bloque 1, §8). |
| `ai_context.py` | `ai.context` (≥ 3211 líneas) | Contextos de conocimiento (prompts) por agente; importación desde `ai/contexts`, ZIP, estadísticas; `_register_hook` y `_auto_init` (§3.4). |
| `ai_trusted_action.py` | `ai.trusted.action` | Registro declarativo de acciones de confianza del Safe Plan (`op='action'`). |
| `ai_view_policy.py` | `ai.view.policy` | Qué vistas heredadas ha creado una acción de sistema de la IA. |
| `ai_system_action.py` | `ai.system.action` (Abstract) | Preview/apply de acciones de sistema (vistas, campos obligatorios, módulos, grupos de usuario). |
| `ai_safe_choice.py` | `ai.safe.choice` | Lista de selección previa a la confirmación del Safe Plan (Chatboo). |
| `mcp_safe_operation.py` | `ai.safe.operation` (≥ 2223 líneas) | Núcleo "Caja B": operaciones supervisadas propuestas por la IA, confirmación, ejecución, PIN. |
| `ai_provider.py` | `ai.provider`, `ai.provider.model` | Proveedores LLM (endpoint, API key, modelo, protocolo), prueba de conexión, export/import. Contiene `cr.commit()` (línea 589). |
| `ai_provider_usage_day.py` | `ai.provider.usage.day` | Consumo diario de tokens/coste por proveedor. |
| `ai_fx_source.py` | `ai.fx.source` | Fuentes HTTP de tipos de cambio USD para mostrar costes. |
| `ai_agent.py` | `ai.agent`, `ai.agent.provider` (≥ 1519 líneas) | Agente (endpoint o inferencia), composición de contextos/skills, caché del prompt, cadena de proveedores con prioridad. |
| `ai_agent_consumer.py` | `_inherit ai.agent` | Restricciones de borrado y códigos de agentes de funcionalidad. |
| `res_config_settings.py` | `_inherit res.config.settings` | Ajustes (bloque 1, §6). |
| `ai_skill.py` | `ai.skill` (≥ 1767 líneas) | Skills (procedimiento + código `code_body` ejecutable "relaxaicode"), import/export ZIP. |
| `ai_execution_engine.py` | `ai.execution.engine` (Abstract) | Motor de ejecución PAAP: resuelve rol → bundle → proveedor. |
| `url_whitelist.py` | `ai.url.whitelist` | Lista blanca de dominios para `fetch_url`. |
| `fetch_cache.py` | `ai.fetch.cache` | Caché de resultados `fetch_url` inmutables. |
| `api_result_cache.py` | `ai.api.result.cache` | Caché efímera de respuestas completas de `api_call`. |
| `external_server.py` | `ai.api.server` (≥ 1182 líneas) | Servidores API externos (MCP SSE/stdio u OpenAPI), descubrimiento de herramientas, credenciales. |
| `api_server_key.py` | `ai.api.server.key` | Credencial saliente por usuario y servidor. |
| `ir_ui_menu.py` | `_inherit ir.ui.menu` | Visibilidad de menús (bloque 1, §3.3). |
| `ir_model_fields_selection.py` | `_inherit ir.model.fields.selection` | Backport de Odoo 15 (bloque 1, §3.3). |

### 2.2 `controllers/` (21 archivos)

| Archivo | Propósito deducido |
|---|---|
| `__init__.py` | Importa `main`, `verification_ui`, `choice_ui`, `session_file`; las herramientas (`tools_*`, `safe_plan`) dentro de `try/except ImportError: pass` (líneas 13-22): **si alguna falla al importar, sus herramientas MCP desaparecen sin error**. |
| `main.py` (≥ 1339 líneas) | Controlador HTTP MCP: 14 rutas `/mcp`, `/mcp/sse`, `/mcp/message`, `/mcp/<agent_code>…`, todas `auth='none'`, `csrf=False`, `cors='*'` (líneas 287-803). |
| `mcp_decorators.py` | Registro automático de herramientas MCP con validación de esquema (único archivo tocado por el commit "adapt to Python 3.7/3.8", [BASE] §12.1). |
| `verification_ui.py` | Rutas JSON `auth='user'`: `/pns_ai_mcp/verification/confirm|execute|cancel|pending` (líneas 39-108). |
| `choice_ui.py` | Rutas JSON `auth='user'`: `/pns_ai_mcp/choice/accept|cancel` (17-27). |
| `session_file.py` | Ruta `/pns_ai_mcp/session_file/<id>` con `auth='public'` (18-21): sirve SVG de sesión. |
| `safe_plan.py` (≥ 1380 líneas) | Declaración de operaciones supervisadas (Caja B): CRUD, `fetch_url`, `api_call`, acciones. |
| `write_verification.py` | Verificación de escrituras peligrosas (PIN). |
| `safe_operation.py` | Shim: `from .write_verification import *`. |
| `tools_system.py` | Herramientas MCP de mantenimiento del sistema. |
| `tools_relaxaicode.py` (≥ 922 líneas) | Herramientas MCP de ejecución de código "relaxaicode". |
| `context_builder.py` | Contexto de ejecución "seguro" para relaxaicode. |
| `validators.py` | Validación AST del código relaxaicode (lista de imports prohibidos). |
| `tools_context.py` | Herramienta MCP de consulta de contextos / bundle de descubrimiento. |
| `tools_context_analytics.py` | Herramientas de análisis de uso de contextos. |
| `tools_i18n_audit.py` | Auditoría de paridad de traducciones en tiempo de ejecución. |
| `tools_memory.py` | `tool_search_memory`; importado por `main.py:73`. |
| `formatters.py` (≥ 733 líneas) | Formateo de datos: XLSX (openpyxl) y PDF (reportlab). |
| `controller_helpers.py` | Ayudas del controlador; comprueba grupos IA (15-17). |
| `utils.py` | Utilidades y clases comunes del servidor MCP. |
| `moe_controller.py` | Controlador vacío (`pass`, línea 12) y **no importado** desde `__init__.py`: código muerto. |

### 2.3 `utils/` (73 archivos)

| Archivo | Propósito (docstring) |
|---|---|
| `__init__.py` | Paquete. |
| `agent_engine.py` (≥ 2771 líneas) | Motor agéntico nativo: bucle ReAct, llamadas a herramientas, streaming. |
| `agent_identity.py` | Nombre visible y proveedor del agente. |
| `agent_stream_text.py` | Helpers puros de texto en streaming. |
| `ai_agent_registry.py` | Códigos fijos de agentes (MCP, Chatboo…). |
| `ai_paths.py` | Resolución de rutas de la carpeta `ai/`. |
| `api_call_result.py` | Formato y paginación de respuestas `api_call`. |
| `api_key.py` | Hash de API keys. |
| `api_key_migration.py` | Migración única de API key en claro → hash. |
| `artifact_bundle.py` | Export/import parcial de artefactos IA (ZIP); llama a `ensure_ai_admin` (62, 188). |
| `artifact_export.py` (≥ 1553 líneas) | Exportación determinista de tablas a archivo (XLSX…). |
| `change_journal.py` | Contrato JSON de `ai.change.journal`. |
| `compat.py` | Fachada de `pns_base.utils.compat` + `grant_mcp_manager_to_odoo_admins` (sin llamadas en todo el módulo) + `load_odoo14_assets_if_needed` (leído entero). |
| `config_backup.py` | Copia completa de la configuración `ai.*` (export/import). |
| `context_code_scan.py` | Escaneo de códigos en `ai/contexts`. |
| `context_roles.py` | Tipos de contexto (`core/domain/locale/discovery`). |
| `context_utils.py` | Utilidades de contexto. |
| `copy_code.py` | Códigos únicos `_copy` al duplicar. |
| `direct_return_policy.py` | Cuándo la salida de una herramienta llega tal cual a Chatboo. |
| `display_currency.py` | Moneda de presentación (≈50 ISO); ICP `pns_ai_mcp.display_currency` (7). |
| `domain_index.py` | Índice de dominios (routing por texto); ICP `pns_ai_mcp.domain_index_inject` (29), `icp_flag_enabled` (128-132). |
| `error_ux.py` | Limpieza de errores para Chatboo. |
| `fetch_url_safe.py` | Política de métodos HTTP para `fetch_url`. |
| `field_required_plan.py` | Safe Plan `field_required`. |
| `field_selection.py` | Etiquetas de Selection. |
| `formatting_mode_policy.py` | Ejes de presentación (painter, footmode, showmode). |
| `fx_rates.py` | Tipos de cambio USD. |
| `history_compact.py` | Compactación del historial de conversación. |
| `import_export_guard.py` | `ensure_ai_admin` (leído entero, §4.6). |
| `knowledge_ownership.py` | Propiedad y visibilidad de contextos/skills de usuario. |
| `knowledge_stamp.py` | Sello de módulos que traen `ai/`. |
| `llm_usage.py` | Normalización de `usage` del LLM. |
| `mcp_client.py` | Cliente MCP mínimo; **lanza procesos con `subprocess.Popen`** para servidores stdio (155-159). |
| `mcp_correlation.py`, `mcp_identity.py`, `mcp_logging.py`, `mcp_protocol.py`, `mcp_resources.py`, `mcp_tool_payload.py` | Protocolo MCP: correlación, identidad, logging, versión, recursos, sobre de herramientas. |
| `mcp_ui.py` | Capa UI sobre `pns_base` (leído entero; abre `pns_ai_mcp.json_export_wizard`). |
| `model_name_suggest.py` | Sugerencias de modelo ante `KeyError`. |
| `module_update_heal.py` | Ayuda tras `button_immediate_*` (instalar/actualizar módulos). |
| `orm_domain.py` | Helpers de dominios ORM. |
| `portable_io.py` | Reexporta `pns_base.utils.portable_io` ([BASE] §2.6). |
| `presentation_mode.py`, `primary_artifact.py`, `record_cite.py`, `record_delivery_gate.py`, `record_linkify.py`, `report_outline_guard.py`, `response_anti_echo.py`, `turn_presentation_basket.py`, `svg_download.py`, `verification_ack_records.py` | Presentación de respuestas en Chatboo. |
| `relaxaicode_recipe.py`, `relaxaicode_render.py` | Sandbox relaxaicode: literales y render HTML de resultados. |
| `sandbox_helpers.py` | Helpers del sandbox desde el registro de Odoo. |
| `session_download.py` | Descargas de sesión (adjuntos + `bus.bus`). |
| `session_store.py` | Almacén de sesiones del transporte SSE. |
| `skill_code_prefix.py` | Prefijos de skills; ICP y defaults (15-18). |
| `skill_dates.py`, `skill_engine_contract.py`, `skill_errors.py`, `skill_files.py`, `skill_help.py`, `skill_live_code.py`, `skill_runtime.py` | Runtime de skills. |
| `system_info.py` | Snapshot `system://info`. |
| `untrusted_html_contract.py` | Rechazo de HTML no confiable del sandbox. |
| `user_time.py` | Zona horaria del usuario. |
| `view_policy_arch.py` | Arch de vistas heredadas creadas por la IA. |

### 2.4 `lib/` (19 archivos)

| Archivo | Propósito |
|---|---|
| `lib/api/__init__.py`, `lib/api/drivers/__init__.py` | Capa de API externas; registra drivers `mcp` y `openapi`. |
| `lib/api/drivers/base.py`, `registry.py` | Driver abstracto y registro por `api_type`. |
| `lib/api/drivers/mcp_driver.py` | Driver para servidores MCP externos. |
| `lib/api/drivers/openapi_driver.py` | Driver OpenAPI/Swagger (`requests`). |
| `lib/api/tools_prompt_block.py` | Catálogo de herramientas externas inyectado en el prompt. |
| `lib/api/validate_tool_args.py` | Validación de argumentos contra `inputSchema`. |
| `lib/llm/__init__.py` | Vacío. |
| `lib/llm/drivers/__init__.py`, `registry.py`, `base.py` | SPI de drivers LLM; registra `openai`, `anthropic`, `ollama`. |
| `lib/llm/drivers/openai_driver.py`, `anthropic_driver.py`, `ollama_driver.py` | Clientes HTTP de LLM (`requests`). |
| `lib/llm/utils/__init__.py`, `tool_utils.py`, `mcp_utils.py`, `timeouts.py` | Tool calls, detección de carga MCP, token de usuario en la petición, timeouts. |

### 2.5 `ai/` (conocimiento de fábrica, 63 archivos)

| Archivo(s) | Contenido |
|---|---|
| `ai/contexts/core/system_prompt.xml` | Prompt de sistema núcleo. |
| `ai/contexts/discovery/discovery_<x>.json` y `discovery_<x>_es_ES.json` (30 archivos) | Reglas de enrutado por dominio para `<x>` = `account`, `accounting_imbalances`, `api_cdmon`, `api_sesame`, `business_documents`, `cost_accounting`, `fetch_url_recipe`, `filters`, `geo`, `geography`, `hr_contracts`, `hr_payroll`, `invoice_concepts`, `partners`, `trial_balance`. |
| `ai/contexts/domain/account.xml`, `accounting_imbalances.xml`, `business_documents.xml`, `cost_accounting.xml`, `dates.xml`, `filters.xml`, `geography.xml`, `invoice_concepts.xml`, `partners.xml` | Conocimiento de dominio (contabilidad, documentos, fechas, filtros, geografía, conceptos de factura, contactos). |
| `ai/contexts/domain/email.md`, `sale_order_duplicate_workflow.md` | Guías en Markdown. |
| `ai/contexts/domain/fetch_url_recipe/fetch_url_recipe.xml` | Receta de `fetch_url`. |
| `ai/contexts/domain/hr_contracts/hr_contracts.xml` | Contratos RR. HH. |
| `ai/contexts/domain/hr_payroll/hr_payroll.xml`, `hr_payroll_accounting_present.xml`, `hr_payroll_{de_DE,en_US,es_AR,es_ES,es_MX,fr_FR,it_IT,pt_BR}.xml` | Nóminas por país (10 archivos). |
| `ai/contexts/domain/self_mcp/self_mcp.xml` | Contexto obligatorio del agente MCP (`required_context_codes`, `data/ai_agent_data.xml:16`). |
| `ai/contexts/domain/trial_balance/trial_balance.xml`, `trial_balance_es_ES.xml` | Balance de sumas y saldos. |
| `ai/contexts/locale/corporate_terms/corporate_terms.xml`, `corporate_terms_es_ES.xml` | Terminología corporativa. |
| `ai/skills/custom/.gitkeep` | **No hay skills de fábrica** (HECHO: único archivo en `ai/skills/`). |

### 2.6 `static/src/` (26 archivos)

| Archivo | Propósito |
|---|---|
| `css/mcp_log_tree.css`, `mcp_context.css`, `mcp_context_list.css`, `mcp_rtl.css`, `pns_list.css` | Estilos de listas PNS; selectores acotados a clases propias (`.o_pns_list`, `.o_mcp_log_tree`…), salvo `.o_field_html .mcp-stats-table` y `.o_field_text_copy_*` (HECHO, búsqueda de selectores). |
| `js/showdown.js` | Librería Markdown → HTML (vendor), cargada en todo el backend. |
| `js/showdown.min.js` | Versión minificada **no cargada**. |
| `js/jspdf.umd.min.js`, `js/xlsx.full.min.js` | Librerías vendor PDF y XLSX, cargadas en todo el backend. |
| `js/mcp_api_key_widget_v14.js` | Widget `mcp_api_key_display` (71). |
| `js/pns_html_readonly_widget_v14.js` | Widget `pns_html_readonly` (16). |
| `js/mcp_iso_datetime_widget_v14.js` | Widget `mcp_iso_datetime` (46). |
| `js/mcp_json_compressed_widget_v14.js` | Widget `mcp_json_compressed` (389). |
| `js/context_window_combo_v14.js` | Widget `context_window_combo` (83). |
| `js/mcp_log_form_v14.js` | `FormRenderer.include` (10). |
| `js/ai_agent_origin_filter_v14.js` | Filtros por origen en el formulario de agente. |
| `js/ai_agent_tree_v14.js`, `ai_provider_tree_v14.js`, `mcp_user_tree_v14.js`, `mcp_context_tree_v14.js`, `mcp_skill_tree_v14.js`, `mcp_log_tree_v14.js`, `whitelist_tree_v14.js`, `external_server_tree_v14.js`, `safe_operation_tree_v14.js` | Botón "Operaciones" en las listas mediante **`ListController.include`** (9 parches del prototipo global) y `ActionManager.include` (`mcp_log_tree_v14.js:111`). |
| `xml/mcp_field_widgets.xml` | Plantillas OWL 2 para Odoo 17+; no se cargan en 14. |

### 2.7 `tests/` (25 archivos)

| Archivo | Clase / propósito |
|---|---|
| `__init__.py` | Importa 21 módulos de test. **No importa** `test_change_journal.py` ni `test_session_download.py`: esos no se ejecutan. |
| `_helpers.py` | Helpers compartidos (O14 + O19). |
| `test_agent_context_inheritance.py` | `TestAgentEffectiveContexts`. |
| `test_bundle_locale.py` | `TestAgentLocale`. |
| `test_change_journal.py` | Diario de cambios y reversión (no importado). |
| `test_change_journal_menu.py` | Menú "Changes" oculto a escritores. |
| `test_chatboo_pending_cards.py` | Tarjetas pendientes de Chatboo. |
| `test_context_type_tokens.py`, `test_context_unlink.py` | Tokens de tipo y borrado de contextos. |
| `test_factory_defaults_keep.py`, `test_identity_pack_isolation.py`, `test_knowledge_composition.py`, `test_knowledge_ownership.py`, `test_required_context_pin.py` | Composición y propiedad del conocimiento. |
| `test_friendly_skill_error.py` | Mapeo de errores de skills. |
| `test_mcp_agent.py` | Agente MCP. |
| `test_mcp_http.py` | `HttpCase` del endpoint MCP. |
| `test_presentation_mode.py`, `test_session_download.py` | `unittest.TestCase` puros (sin `@tagged`). |
| `test_relaxaicode_imports.py`, `test_relaxaicode_model_stamp.py`, `test_relaxaicode_render_locale.py`, `test_relaxaicode_sandbox_escapes_e2e.py` (etiqueta `pns_intrusion`) | Sandbox relaxaicode, incluido intento de escapes. |
| `test_safe_plan_atomicity.py` | `executed=True` solo tras commit correcto. |
| `test_system_action.py` | Acciones de sistema de confianza. |

### 2.8 Propuesta de reparto para los bloques 2-4

| Bloque | Contenido sugerido |
|---|---|
| 2 — Datos, conocimiento y secretos | `models/` de catálogo (`ai_context`, `ai_skill`, `ai_agent`, `ai_agent_consumer`, `ai_provider`, `ai_provider_usage_day`, `ai_fx_source`, `mcp_user`, `mcp_api_key_wizard`, `external_server`, `api_server_key`, `url_whitelist`, `fetch_cache`, `api_result_cache`, `ai_log`, `ai_change_journal`) + `utils/` de import/export y propiedad (`config_backup`, `artifact_bundle`, `knowledge_*`, `api_key*`, `portable_io`, `context_*`, `domain_index`, `skill_code_prefix`, `display_currency`, `fx_rates`). |
| 3 — Superficie HTTP/MCP y ejecución | `controllers/` completos, `http_patch` en ejecución, `models/mcp_safe_operation.py`, `ai_trusted_action`, `ai_system_action`, `ai_view_policy`, `ai_safe_choice`, `ai_execution_engine`, `lib/`, `utils/mcp_*`, `fetch_url_safe`, `relaxaicode_*`, `sandbox_helpers`, `module_update_heal`, `field_required_plan`, `view_policy_arch`, `session_*`. |
| 4 — Motor de agente, presentación y cliente | `utils/agent_engine.py` y utilidades de presentación, `static/src/`, contenido de `ai/`, `tests/` (ejecución). |

---

## 3. Hooks, `http_patch.py` y modelos core heredados del bloque

### 3.1 `hooks.py`

**`post_init_hook(*args)`** (27-42). Acepta la firma de Odoo 14 `(cr, registry)` y la de 17+ `(env,)`
según `version_info` (34-38); en 14 crea `api.Environment(cr, SUPERUSER_ID, {})`.
1. `sync_factory_knowledge(env, 'post_init')` (157-194): con `skip_hardcoded_restrictions=True`
   llama a `ai.context._import_all_from_module(replace_existing=True, module_name='pns_ai_mcp')` y
   a `ai.skill.import_from_module('pns_ai_mcp', scopes=('system',))`; luego
   `_sync_agent_caches` (245-256: `_sync_composition_and_cache()` de **todos** los `ai.agent`) y
   `_write_factory_stamp` (237-242: ICP `pns_ai.factory_knowledge_stamp`, línea 24). Cada paso
   captura excepciones y solo registra WARNING.
2. `_load_first_install_data(env)` (45-96): carga con `convert_file(..., mode='init', noupdate=True,
   kind='data', pathname=…)` (firma de 14 verificada: core `odoo/tools/convert.py:722`) los cuatro
   XML de §1.3 que no están en el manifest; después `ai.api.server._link_orphan_api_discovery()`.

Observaciones:
- HECHO: la misma importación de contextos y skills se ejecuta **dos veces** en la instalación:
  primero desde `data/mcp_data.xml:6-10` (durante la carga de datos) y después desde el hook.
- INFERENCIA: las excepciones se capturan sin `savepoint` (`hooks.py:83-89,129-133,149-153,177-191`);
  si el fallo es de PostgreSQL, la transacción queda abortada y la instalación fallará más adelante
  con un error que no apunta a la causa.

**`uninstall_hook(cr, registry)`** (99-102, firma de 14): borra los `ai.context` y `ai.skill` con
`source_module='pns_ai_mcp'` y sin `owner_id` (105-154). No borra: parámetros `pns_ai_mcp.*` y
`pns_ai.factory_knowledge_stamp`, adjuntos de exportación, secuencias creadas en tiempo de ejecución
(`pns_ai_mcp.safe_op.<verbo>`, `pns_ai_mcp.safe_choice`, ver §7.3). INFERENCIA: Odoo borra los
modelos y sus tablas, pero esos ICP y secuencias quedan huérfanos.

**`maybe_sync_factory_knowledge`** (217-234) se llama desde `ai.context._register_hook`
(`models/ai_context.py:415-431`, fuera del bloque, comprobado): **en cada carga del registro**
(arranque de cada worker, core [BASE] §2.1 sobre `_register_hook`) calcula el sello recorriendo
**todos** los módulos instalados (`hooks.py:206-214`, `get_module_path` + existencia de `ai/`) y, si
cambió la versión de cualquier módulo que traiga `ai/`, vuelve a sincronizar el conocimiento de
fábrica (escrituras en BD durante el arranque). INFERENCIA: con varios workers arrancando a la vez
tras una actualización pueden sincronizar en paralelo; y, como en `pns_base`, cada módulo huérfano
genera "module not found" en el log en cada arranque ([BASE] §12.2).

### 3.2 `http_patch.py`

- HECHO (9, 22-35): si `NEEDS_ROOT_GET_REQUEST_PATCH` (True en 14, [BASE] §2.6) sustituye
  **`odoo.http.Root.get_request`** al importar el módulo. Para peticiones **POST** con mimetype
  `application/json` o `application/json-rpc` y ruta `/mcp` o que empiece por `/mcp/` (14-19),
  devuelve `HttpRequest` en lugar de `JsonRequest`; el resto sigue al original.
- Core 14 (HECHO, core `odoo/http.py:1413-1418`): `get_request` decide `JsonRequest` solo por el
  mimetype. Sin el parche, un POST JSON a una ruta `type='http'` (todas las `/mcp…` lo son,
  `controllers/main.py:287-803`) daría error de tipo de petición.
- Efecto sobre módulos que no son PNS:
  - INFERENCIA: el parche es **de proceso**: una vez importado en un worker afecta a todas las
    bases de datos servidas por ese proceso, tenga o no instalado `pns_ai_mcp`.
  - Solo cambia el comportamiento de POST JSON a `/mcp` y `/mcp/*`. Cualquier otro módulo (core,
    OCA, Seges) que tuviera rutas JSON bajo `/mcp/…` dejaría de funcionar como JSON-RPC.
    HECHO: ni el core 14 ni los repos OCA/compartidos de `/opt/odoo-src/14.0` (excluida la copia
    `third_party`) declaran rutas que empiecen por `/mcp` (búsqueda de `route('/mcp`). Falta
    revisar los módulos propios del cliente.
  - Las rutas `/mcp` tienen `csrf=False`, `auth='none'`, `cors='*'` (análisis en bloque 3).

### 3.3 Modelos core heredados en este bloque

**`ir.ui.menu` — `models/ir_ui_menu.py`**
- Sobrescribe `_visible_menu_ids(self, debug=False)` (49-60) llamando primero a `super()` (firma
  igual que el core: `core: odoo/addons/base/models/ir_ui_menu.py:78-116`, decorado con
  `ormcache` por grupos del usuario).
- Si el usuario **no** es `group_ai_admin`, quita `menu_mcp_change_journal`; si **sí** lo es,
  quita los menús de operador `menu_mcp_contexts_writer`, `menu_ai_skill_writer`,
  `menu_mcp_safe_operation`, `menu_mcp_logs` (14-26).
- Efecto global: se ejecuta para **todos** los usuarios en cada carga de menús; solo elimina
  menús PNS. Coste: un `has_group` y hasta 5 `env.ref` por llamada, fuera del `ormcache` del core
  (INFERENCIA: despreciable).

**`ir.model.fields.selection` — `models/ir_model_fields_selection.py`**
- `_process_ondelete` (23-37): antes de llamar al core, descarta las selecciones cuyo modelo ya no
  está en el registro (el core haría `self.env[model]` y lanzaría `KeyError`, HECHO core
  `odoo/addons/base/models/ir_model.py:1427-1428`).
- `_get_records` (39-43): devuelve un recordset vacío de `ir.model` si el modelo no existe (en el
  core `ir_model.py:1461-1469` también haría `self.env[...]`).
- Efecto global: aplica a **todas** las actualizaciones de **todos** los módulos. Evita un fallo
  conocido de 14 (corregido en 15) pero también oculta valores de selección huérfanos de otros
  módulos, que dejan de dar error (solo un INFO, línea 30).

**`res.config.settings`** — §6. Efecto global relevante: su `set_values` se ejecuta cada vez que un
administrador guarda **cualquier** pantalla de Ajustes (todas comparten el modelo).

### 3.4 Otros efectos de arranque fuera del bloque, detectados de paso

- `ai.context._auto_init` (`models/ai_context.py:1222-1228`) vuelve a cargar `views/assets.xml`
  con `convert_file` (`utils/compat.py:48-71`) en Odoo ≤ 14. Redundante con el manifest (línea 70).
  INFERENCIA: inocuo; solo ocurre al instalar/actualizar.

### 3.5 `__init__.py` y `constants.py`

- `__init__.py` (11-15): importa `models`, los hooks, `wizard`, `controllers` y `http_patch`.
- `constants.py`: textos en español (8-14) usados en mensajes HTML de `mcp_safe_operation.py:22,1923-1947`
  y `PIN_EXPIRY_MINUTES = 15` (17), usado en `mcp_safe_operation.py:250,472` y
  `controllers/write_verification.py:278-280`.

---

## 4. Seguridad

### 4.1 Categoría y grupos — `security/security_groups.xml` (`noupdate="0"`)

| XML ID | Nombre | `implied_ids` | Línea |
|---|---|---|---|
| `module_category_ai` (`ir.module.category`) | Artificial Intelligence | — | 10-14 |
| `group_ai_writer` | AI Writer | `base.group_user` | 16-21 |
| `group_ai_external_url` | AI External URL | `base.group_user` | 23-28 |
| `group_ai_external_api` | AI External API | `base.group_user` | 32-37 |
| `group_ai_admin` | AI Administrator | `group_ai_writer`, `group_ai_external_url`, `group_ai_external_api` | 39-44 |

Jerarquía: `AI Administrator ⇒ {Writer, External URL, External API} ⇒ Usuario interno`. No hay
grupo "usuario IA": según `security/security.xml:7-8`, cualquier usuario interno activo con API key
tiene acceso de lectura vía MCP.

HECHO: **ningún grupo IA se asigna automáticamente**. `grant_mcp_manager_to_odoo_admins`
(`utils/compat.py:25-45`) no se llama desde ningún archivo del módulo, ni hooks ni migraciones. El
administrador de Odoo no ve el menú "AI Engine" hasta que se le asigne un grupo IA.

INFERENCIA: como Writer/External URL/External API no forman una cadena lineal, en 14 la ficha del
usuario los mostrará como casillas independientes dentro de "Artificial Intelligence" (PENDIENTE).

### 4.2 `security/ir.model.access.csv`, línea a línea

Leyenda: R/W/C/D = leer/escribir/crear/borrar. **No hay ninguna línea sin `group_id`** (HECHO).

| L. | id | Modelo | Grupo | R | W | C | D | Observación |
|---|---|---|---|---|---|---|---|---|
| 2 | access_mcp_log_user | ai.log | base.group_user | 1 | 0 | 0 | 0 | Regla: solo los suyos. |
| 3 | access_mcp_context_user | ai.context | base.group_user | 1 | 0 | 0 | 0 | Regla: sin dueño o propios. |
| 4 | access_ai_trusted_action_user | ai.trusted.action | base.group_user | 1 | 0 | 0 | 0 | Sin regla. |
| 5 | access_mcp_safe_operation_user | ai.safe.operation | base.group_user | 1 | **1** | 0 | 0 | Regla: propios, **con escritura**. Ver §4.5 riesgo 3. |
| 6 | access_url_whitelist_user | ai.url.whitelist | base.group_user | 1 | 0 | 0 | 0 | Sin regla. |
| 7 | access_external_server_user | ai.api.server | base.group_user | 1 | 0 | 0 | 0 | Sin regla. **Lectura de `auth_token`, `env_vars`, `config_json`** (§4.5 riesgo 1). |
| 8 | access_api_server_key_user | ai.api.server.key | base.group_user | 1 | 1 | 1 | 1 | Regla: solo las propias. |
| 9 | access_ai_fetch_cache_user | ai.fetch.cache | base.group_user | 1 | 0 | 0 | 0 | Sin regla (§4.5 riesgo 2). |
| 10 | access_ai_api_result_cache_user | ai.api.result.cache | base.group_user | 1 | 0 | 0 | 0 | Sin regla (§4.5 riesgo 2). |
| 11 | access_ai_provider_user | ai.provider | base.group_user | 1 | 0 | 0 | 0 | `api_key` protegido con `groups=group_ai_admin` (`models/ai_provider.py:103-107`). |
| 12 | access_ai_provider_model_user | ai.provider.model | base.group_user | 1 | 0 | 0 | 0 | |
| 13 | access_ai_provider_usage_day_user | ai.provider.usage.day | base.group_user | 1 | 0 | 0 | 0 | Consumo y coste visibles para todos. |
| 14 | access_ai_fx_source_user | ai.fx.source | base.group_user | 1 | 0 | 0 | 0 | |
| 15 | access_ai_context_agent_user | ai.agent | base.group_user | 1 | 0 | 0 | 0 | Incluye el prompt en caché (`cached_content`). |
| 16 | access_ai_skill_user | ai.skill | base.group_user | 1 | 0 | 0 | 0 | Regla: sin dueño o propias. |
| 17 | access_pns_ai_mcp_context_stats_wizard | pns_ai_mcp.context_stats_wizard | base.group_user | 1 | 1 | 1 | 1 | Transitorio; `stats_html` sin sanear. |
| 18 | access_mcp_context_tools_wizard_admin | pns_ai_mcp.context.tools.wizard | group_ai_admin | 1 | 1 | 1 | 1 | |
| 19 | access_mcp_context_writer | ai.context | group_ai_writer | 1 | 1 | 1 | 1 | Limitado por reglas. |
| 20 | access_ai_skill_writer | ai.skill | group_ai_writer | 1 | 1 | 1 | 1 | Limitado por reglas. |
| 21 | access_ai_context_agent_compose_wizard_writer | pns_ai_mcp.agent.compose.wizard | group_ai_writer | 1 | 1 | 1 | 1 | Escribe en `ai.agent`, que el Writer no puede escribir (INFERENCIA: AccessError). |
| 22 | access_ai_context_agent_compose_line_writer | pns_ai_mcp.agent.compose.line | group_ai_writer | 1 | 1 | 1 | 1 | |
| 23 | access_ai_context_agent_cache_rebuild_wizard_writer | pns_ai_mcp.agent.cache.rebuild.wizard | group_ai_writer | 1 | 1 | 1 | 1 | |
| 24 | access_ai_skill_capture_wizard_writer | pns_ai_mcp.skill.capture.wizard | group_ai_writer | 1 | 1 | 1 | 1 | Crea skills con código ejecutable (§8). |
| 25 | access_pns_ai_mcp_skill_tools_wizard_admin | pns_ai_mcp.skill.tools.wizard | group_ai_admin | 1 | 1 | 1 | 1 | |
| 26 | access_pns_ai_mcp_skill_import_wizard_admin | pns_ai_mcp.skill.import.wizard | group_ai_admin | 1 | 1 | 1 | 1 | |
| 27 | access_pns_ai_mcp_context_import_wizard_admin | pns_ai_mcp.context_import_wizard | group_ai_admin | 1 | 1 | 1 | 1 | |
| 28 | access_pns_ai_mcp_json_export_wizard_admin | pns_ai_mcp.json_export_wizard | group_ai_admin | 1 | 1 | 1 | 1 | Un Writer que exporte no podrá abrir el resultado salvo `sudo` interno (PENDIENTE). |
| 29 | access_pns_ai_mcp_agent_tools_wizard_admin | pns_ai_mcp.agent.tools.wizard | group_ai_admin | 1 | 1 | 1 | 1 | |
| 30 | access_pns_ai_mcp_agent_context_import_wizard_admin | pns_ai_mcp.agent.context.import.wizard | group_ai_admin | 1 | 1 | 1 | 1 | |
| 31 | access_pns_ai_mcp_agent_skill_import_wizard_admin | pns_ai_mcp.agent.skill.import.wizard | group_ai_admin | 1 | 1 | 1 | 1 | |
| 32 | access_pns_ai_mcp_agent_import_wizard_admin | pns_ai_mcp.agent.import.wizard | group_ai_admin | 1 | 1 | 1 | 1 | |
| 33 | access_mcp_user_admin | ai.mcp.user | group_ai_admin | 1 | 1 | 1 | 1 | Ningún otro grupo accede. |
| 34 | access_mcp_api_key_wizard_admin | pns_ai_mcp.api_key_wizard | group_ai_admin | 1 | 1 | 1 | 1 | |
| 35 | access_mcp_log_admin | ai.log | group_ai_admin | 1 | 1 | 1 | 1 | |
| 36 | access_ai_change_journal_admin | ai.change.journal | group_ai_admin | 1 | 1 | 1 | 0 | |
| 37 | access_ai_change_journal_system | ai.change.journal | base.group_system | 1 | 1 | 1 | 0 | Administrador de Odoo sin grupo IA también accede. |
| 38 | access_mcp_log_delete_menu_admin | pns_ai_mcp.log_delete_menu | group_ai_admin | 1 | 1 | 1 | 1 | |
| 39 | access_mcp_log_delete_menu_system | pns_ai_mcp.log_delete_menu | base.group_system | 1 | 1 | 1 | 1 | |
| 40 | access_mcp_safe_operation_admin | ai.safe.operation | group_ai_admin | 1 | 1 | 1 | 1 | |
| 41 | access_url_whitelist_admin | ai.url.whitelist | group_ai_admin | 1 | 1 | 1 | 1 | |
| 42 | access_external_server_admin | ai.api.server | group_ai_admin | 1 | 1 | 1 | 1 | |
| 43 | access_api_server_key_admin | ai.api.server.key | group_ai_admin | 1 | 1 | 1 | 1 | |
| 44 | access_ai_fetch_cache_admin | ai.fetch.cache | group_ai_admin | 1 | 1 | 1 | 1 | |
| 45 | access_ai_api_result_cache_admin | ai.api.result.cache | group_ai_admin | 1 | 1 | 1 | 1 | |
| 46 | access_ai_provider_admin | ai.provider | group_ai_admin | 1 | 1 | 1 | 1 | |
| 47 | access_ai_provider_model_admin | ai.provider.model | group_ai_admin | 1 | 1 | 1 | 1 | |
| 48 | access_ai_provider_usage_day_admin | ai.provider.usage.day | group_ai_admin | 1 | 1 | 1 | 1 | |
| 49 | access_ai_fx_source_admin | ai.fx.source | group_ai_admin | 1 | 1 | 1 | 1 | |
| 50 | access_ai_provider_tools_wizard_admin | pns_ai_mcp.provider.tools.wizard | group_ai_admin | 1 | 1 | 1 | 1 | |
| 51 | access_ai_agent_provider_admin | ai.agent.provider | group_ai_admin | 1 | 1 | 1 | 1 | Solo admin: los demás usuarios no pueden leer la cadena de proveedores (PENDIENTE si el motor la lee con `sudo`). |
| 52 | access_ai_context_agent_admin | ai.agent | group_ai_admin | 1 | 1 | 1 | 1 | |
| 53-57 | access_import_{servers,users,whitelist,external_servers,agents}_wizard_admin | asistentes de importación JSON | group_ai_admin | 1 | 1 | 1 | 1 | |
| 58-61 | access_{mcp_user,whitelist,external_server,mcp_log}_tools_wizard_admin | asistentes "Tools" | group_ai_admin | 1 | 1 | 1 | 1 | |
| 62 | access_safe_operation_tools_wizard_user | pns_ai_mcp.safe.operation.tools.wizard | base.group_user | 1 | 1 | 1 | 1 | |
| 63 | access_config_backup_wizard_admin | pns_ai_mcp.config_backup_wizard | group_ai_admin | 1 | 1 | 1 | 1 | |
| 64-65 | access_artifact_bundle_{export,import}_wizard_admin | asistentes de bundle | group_ai_admin | 1 | 1 | 1 | 1 | |
| 66 | access_ai_trusted_action_admin | ai.trusted.action | group_ai_admin | 1 | 1 | 1 | 1 | |
| 67 | access_ai_system_action_admin | ai.system.action (abstracto) | group_ai_admin | 1 | 1 | 1 | 1 | |
| 68 | access_ai_view_policy_admin | ai.view.policy | group_ai_admin | 1 | 1 | 1 | 1 | |
| 69 | access_ai_safe_choice_user | ai.safe.choice | base.group_user | 1 | 1 | 1 | 1 | **Sin record rule**: cualquier usuario interno lee/modifica/borra las elecciones de todos (§4.5 riesgo 3). |

Cobertura: todos los modelos de `models/` y `wizard/` tienen al menos una línea (HECHO, contraste de
los `_name` de `models/` y `wizard/` con el CSV). No hay reglas multicompañía ni campos
`company_id` en los modelos del bloque (PENDIENTE para los del bloque 2).

### 4.3 Record rules — `security/security.xml` (`noupdate="0"`)

| XML ID | Modelo | Grupo | Dominio | R/W/C/D | Líneas |
|---|---|---|---|---|---|
| `ai_context_user_read_rule` | ai.context | base.group_user | `['|', ('owner_id','=',False), ('owner_id','=',user.id)]` | 1/0/0/0 | 24-33 |
| `ai_context_writer_read_rule` | ai.context | group_ai_writer | igual | 1/0/0/0 | 36-45 |
| `ai_context_writer_write_rule` | ai.context | group_ai_writer | `[('owner_id','=',user.id), ('context_type','!=','core')]` | 0/1/1/1 | 46-55 |
| `ai_context_admin_rule` | ai.context | group_ai_admin | `[(1,'=',1)]` | 1/1/1/1 | 56-65 |
| `mcp_log_user_rule` | ai.log | base.group_user | `[('user_id','=',user.id)]` | 1/0/0/0 | 68-77 |
| `mcp_log_admin_rule` | ai.log | group_ai_admin | `[(1,'=',1)]` | 1/0/0/1 | 80-89 |
| `mcp_safe_operation_user_rule` | ai.safe.operation | base.group_user | `[('user_id','=',user.id)]` | 1/1/0/0 | 92-101 |
| `mcp_safe_operation_admin_rule` | ai.safe.operation | group_ai_admin | `[(1,'=',1)]` | 1/1/1/1 | 104-113 |
| `ai_skill_user_read_rule` | ai.skill | base.group_user | sin dueño o propias | 1/0/0/0 | 116-125 |
| `ai_skill_writer_read_rule` | ai.skill | group_ai_writer | igual | 1/0/0/0 | 128-137 |
| `ai_skill_writer_write_rule` | ai.skill | group_ai_writer | `[('owner_id','=',user.id), ('is_system','=',False)]` | 0/1/1/1 | 138-147 |
| `ai_skill_admin_rule` | ai.skill | group_ai_admin | `[(1,'=',1)]` | 1/1/1/1 | 148-157 |
| `api_server_key_own_rule` | ai.api.server.key | base.group_user | `[('user_id','=',user.id)]` | 1/1/1/1 | 160-169 |
| `api_server_key_admin_rule` | ai.api.server.key | group_ai_admin | `[(1,'=',1)]` | 1/1/1/1 | 170-179 |

Semántica en 14: las reglas de grupo se combinan con OR entre los grupos del usuario; si para un modo
(p. ej. escritura) no aplica ninguna regla, ese modo no queda restringido por reglas. Por eso, en
`ai.log`, el administrador IA puede escribir/crear (ACL 1,1,1,1) aunque su regla solo marque
lectura y borrado (INFERENCIA, consistente con el core).

Sin reglas: `ai.api.server`, `ai.url.whitelist`, `ai.fetch.cache`, `ai.api.result.cache`,
`ai.provider*`, `ai.agent`, `ai.safe.choice`, `ai.change.journal`, `ai.trusted.action`,
`ai.mcp.user`, `ai.fx.source`, `ai.view.policy`.

Secuencia `sequence_safe_operation` (`security.xml:184-191`): ver §7.3 (no se usa).

### 4.4 Acciones de servidor sin `groups_id`

`views/ai_menus.xml`, `views/mcp_user_views.xml:91-106`, `views/ai_agent_views.xml:174-208` y
`views/ai_skill_views.xml:139-174` declaran 32 `ir.actions.server`; solo dos tienen `groups_id`
(`ai_skill_views.xml:152,162`). HECHO (core `odoo/addons/base/models/ir_actions.py:608-620`): en 14,
una acción de servidor sin grupos solo la puede ejecutar quien tenga **permiso de escritura** sobre
el modelo; esto limita la mayoría al administrador IA, pero:
- los Writer pueden ejecutar las de `ai.context` y `ai.skill` (exportar/importar ZIP, restaurar
  desde módulo, recargar skills desde archivos); los métodos llamados comprueban
  `ensure_ai_admin` (§4.6);
- cualquier usuario interno puede ejecutar la de `ai.safe.operation` (`action_server_export_safe_operations`,
  `ai_menus.xml:213-219`), que llama a un método con `ensure_ai_admin`
  (`models/mcp_safe_operation.py:2223`).

### 4.5 Riesgos de seguridad detectados en el bloque

1. **Secretos de servidores externos legibles por todos los usuarios internos.** HECHO: ACL de
   lectura para `base.group_user` (CSV línea 7) y campos `auth_token` (`models/external_server.py:176-182`),
   `env_vars` (209-213) y `config_json` (236-242) sin `groups=`. La vista los muestra con
   `password="True"` (`views/external_server_views.xml:100`), que no es una barrera: por RPC
   (`read`) se obtienen en claro. Contraste: `ai.provider.api_key` sí tiene `groups`.
2. **Cachés de resultados visibles para todos.** HECHO: `ai.fetch.cache` y `ai.api.result.cache`
   legibles por cualquier usuario interno y sin record rules (CSV 9-10). INFERENCIA: guardan
   respuestas completas de `api_call`/`fetch_url` (p. ej. datos de RR. HH. de Sesame si se activa)
   pedidas por otros usuarios. Confirmar contenido en bloque 2.
3. **Escritura directa sobre las autorizaciones propias y sobre elecciones ajenas.** HECHO: un
   usuario interno puede escribir sus `ai.safe.operation` (ACL 1,1,0,0 + regla con
   `perm_write`), y leer/escribir/borrar **cualquier** `ai.safe.choice` (CSV 69, sin regla).
   INFERENCIA: si `write()` no protege campos como `status`, `executed` o el plan, un usuario podría
   alterar por RPC una propuesta después de generada o marcarla como confirmada, saltándose la
   "Caja B". PENDIENTE de bloque 3 (`mcp_safe_operation.py`, `write_verification.py`).
4. **Contexto `skip_hardcoded_restrictions` controlable por el cliente.** HECHO:
   `utils/import_export_guard.py:9-10` deja pasar a cualquiera si el contexto trae esa clave; lo
   mismo `ai.skill.write/unlink` (`models/ai_skill.py:515,535`), `ai.context.write/unlink`
   (`models/ai_context.py:1520,1635`) y `knowledge_ownership.py:51`. En Odoo el contexto de una
   llamada RPC lo decide el navegador. INFERENCIA: las record rules siguen aplicando (el ORM no las
   omite por contexto), así que el impacto real es saltarse las comprobaciones que solo están en
   Python (exportaciones "solo administradores", protección de registros de sistema que las reglas
   no cubren). Se analiza en bloque 2.
5. **El grupo AI Administrator equivale en la práctica a un administrador técnico.** HECHO:
   acciones de confianza `module.update` (instalar/actualizar/desinstalar módulos) y
   `user.add_group` / `user.remove_group` ("Add native security group to user"), todas con
   `group_ai_admin` (`data/trusted_actions_system.xml:67-95`); servidores MCP `stdio` con
   `command`/`command_args`/`env_vars` configurables (`views/external_server_views.xml:112-120`) que
   se ejecutan con `subprocess.Popen` (`utils/mcp_client.py:155-159`); importación de API keys de
   cualquier usuario (§8). INFERENCIA: un AI Administrator que no sea administrador de Odoo puede
   escalar a administrador de Odoo (añadirse `base.group_system`) y ejecutar comandos del sistema
   operativo como el usuario de Odoo. Verificar límites en bloque 3.
6. **API key generada guardada en claro en la tabla del asistente.** HECHO:
   `models/mcp_api_key_wizard.py:116` escribe `generated_key` en el registro transitorio.
   INFERENCIA: permanece en `pns_ai_mcp_api_key_wizard` hasta la limpieza de transitorios (en 14,
   por defecto, registros de más de 1 hora). Cualquier administrador IA puede leerla mientras tanto.
7. **HTML sin sanear** en asistentes accesibles a todos: `stats_html` (`wizard/context_stats_wizard.py:33`)
   con códigos de contexto insertados sin escapar (349-356); `result_html` heredado ([BASE] §4,
   observación 2). Riesgo bajo (códigos los crean Writers/administradores).

### 4.6 Usos de `sudo()` en los archivos del bloque

| Archivo:línea | Qué hace | Comentario justificativo |
|---|---|---|
| `hooks.py:206` | Busca `ir.module.module` instalados | No (entorno ya superusuario). |
| `hooks.py:223,240` | Lee/escribe ICP del sello | No. |
| `models/res_config_settings.py:105` | `env.ref(xmlid).sudo().read()` de acciones | No; inocuo (solo definiciones de acción). |
| `models/res_config_settings.py:150` | Busca el agente de módulo por código | No. |
| `models/res_config_settings.py:230,250,322` | Lee/escribe ICP | No; normal en ajustes. |
| `models/res_config_settings.py:275` | Lee todos los `ai.skill` para validar prefijos | No. |
| `models/res_config_settings.py:292` | Reconstruye caché de todos los agentes | No. |
| `wizard/import_users_wizard.py:93,99,111,120,127` | Escribe/crea `ai.mcp.user` (incluido el hash de API key) | No; el administrador IA ya tiene ACL completa, así que el `sudo` es redundante. |
| `wizard/context_stats_wizard.py:80` | `get_discovery_indexed_codes` como superusuario | No; accesible a cualquier usuario interno (ACL línea 17). |
| `wizard/mcp_log_tools_wizard.py:17` | Lee la acción de borrado | No; inocuo. |
| `models/mcp_api_key_wizard.py:86` (fuera del bloque) | Borra la API key | No. |

`http_patch.py`, `models/ir_ui_menu.py`, `models/ir_model_fields_selection.py`,
`models/mcp_log_delete_menu.py` y el resto de `wizard/` no usan `sudo()`.

---

## 5. Menús, acciones y vistas

### 5.1 Árbol de menús

| Menú (XML ID) | Secuencia | Grupos | Abre | Definido en |
|---|---|---|---|---|
| **AI Engine** (`menu_mcp_main`) | 10 | admin, writer, external_url, external_api | Carpeta raíz (icono `static/description/icon.png`) | `views/mcp_user_views.xml:131-135` |
| ├ Agents (`menu_ai_agent`) | 10 | admin | `action_ai_agent` → `ai.agent` lista/form | `views/ai_menus.xml:14-19` |
| ├ Knowledge (`menu_ai_knowledge`) | 20 | admin, writer | Carpeta | `mcp_user_views.xml:146-150` |
| │ ├ Domain Discovery (`menu_ai_domain_discovery`) | 7 | admin | `action_ai_domain_discovery` → `ai.context` tipo `discovery` (sin crear/editar) | `views/ai_domain_index_views.xml:66-71` |
| │ ├ Contexts (`menu_mcp_contexts`) | 10 | admin | `action_mcp_contexts` → `ai.context` (`active_test=False`, filtro "mi idioma") | `views/ai_context_views.xml:199-204` |
| │ ├ Skills (`menu_ai_skill`) | 20 | admin | `action_ai_skill` → `ai.skill` | `ai_menus.xml:21-26` |
| │ ├ My Contexts (`menu_mcp_contexts_writer`) | 40 | writer (oculto a admin por §3.3) | `action_mcp_contexts_writer` → `ai.context` propios, por defecto tipo `domain` | `views/ai_operator_menus.xml:7-12` |
| │ └ My Skills (`menu_ai_skill_writer`) | 50 | writer (oculto a admin) | `action_ai_skill_writer` → `ai.skill` propias | `ai_operator_menus.xml:14-19` |
| ├ Connections (`menu_ai_connections`) | 30 | admin | Carpeta | `mcp_user_views.xml:141-145` |
| │ ├ Providers (`menu_ai_provider`) | 5 | admin | `action_ai_provider` → `ai.provider` | `ai_menus.xml:6-11` |
| │ ├ External Servers (`menu_external_server`) | 10 | admin | `action_external_server` → `ai.api.server` (filtro activos) | `views/external_server_views.xml:276-281` |
| │ └ Whitelist (`menu_url_whitelist`) | 20 | admin | `action_url_whitelist` → `ai.url.whitelist` | `views/url_whitelist_views.xml:79-84` |
| ├ Security (`menu_ai_security`) | 40 | admin, writer, external_url, external_api | Carpeta | `mcp_user_views.xml:151-155` |
| │ ├ Users (`menu_mcp_users`) | 5 | admin | Acción de servidor `action_server_open_mcp_users` → crea filas `ai.mcp.user` para todos los usuarios internos activos y abre `action_mcp_users` | `mcp_user_views.xml:100-106,158-163`; `models/mcp_user.py:335-349,493-502` |
| │ ├ Authorizations (`menu_mcp_safe_operation_admin`) | 10 | admin | `action_mcp_safe_operation_admin` → todas las `ai.safe.operation` | `views/mcp_safe_operation_views.xml:136-153` |
| │ ├ My Authorizations (`menu_mcp_safe_operation`) | 20 | writer, external_url, external_api (oculto a admin) | `action_mcp_safe_operation` (las propias, por record rule) | `mcp_safe_operation_views.xml:118-134` |
| │ ├ Changes (`menu_mcp_change_journal`) | 25 | admin (forzado con `(6,0,…)` en cada `-u`) | `action_mcp_change_journal` → `ai.change.journal` | `views/mcp_change_journal_views.xml:131-152` |
| │ ├ My Activity (`menu_mcp_logs`) | 30 | writer, external_url, external_api (oculto a admin) | `action_mcp_logs` → `ai.log` (los suyos por regla) | `views/mcp_log_views.xml:283-288` |
| │ └ Activity (`menu_mcp_logs_admin`) | 40 | admin | `action_mcp_logs_technical` → `ai.log` | `mcp_log_views.xml:290-295` |
| └ Settings (`menu_mcp_settings`) | 50 | admin | `action_mcp_configuration` → `res.config.settings` inline, `module=pns_ai_mcp` | `views/res_config_settings_views.xml:260-274` |

Notas:
- HECHO: el menú Settings es visible para `group_ai_admin`, pero `res.config.settings` solo es
  accesible a `base.group_system` (core `odoo/addons/base/security/ir.model.access.csv:110`), y el
  bloque de ajustes tiene `groups="pns_ai_mcp.group_ai_admin"` (`res_config_settings_views.xml:11`).
  **Solo quien tenga ambos grupos puede configurar el módulo.** INFERENCIA: un AI Administrator sin
  Ajustes recibe un error de acceso al abrir "Settings" (PENDIENTE).
- Un usuario interno sin grupo IA no ve ningún menú, pero conserva el acceso por RPC de §4.2.

### 5.2 Acciones sin menú (botones, asistentes, enlaces)

- Ajustes: `action_module_endpoint_agents`, `action_module_inference_agents` (`res_config_settings_views.xml:244-258`).
- `action_ai_fx_source` (`views/ai_fx_source_views.xml:45-55`): solo desde Ajustes.
- `action_mcp_api_key_wizard` (`views/mcp_api_key_wizard_views.xml:10-16`).
- `action_mcp_logs_delete_menu_window` (`mcp_log_views.xml:8-14`): botón de cabecera de lista
  (soportado en 14: core `addons/web/static/src/js/views/list/list_view.js:53,112`).
- Acciones de asistentes `wizard/*_views.xml` (§8).
- Acciones de servidor enlazadas (`binding_model_id`) que aparecen en el menú "Acción":
  `ai.context` lista (6, `ai_menus.xml:112-159`), `ai.skill` lista (3 en `ai_menus.xml:222-247`
  y 3 en `ai_skill_views.xml:147-174`; "Export selected skills to ZIP" e "Import skills from ZIP"
  quedan **duplicados** con nombres iguales, INFERENCIA), `ai.agent` formulario (4,
  `ai_agent_views.xml:174-208`), `ai.mcp.user` formulario ("Import existing API key",
  `mcp_user_views.xml:91-98`). El resto se declaran con `binding_model_id=False` y se invocan desde
  los botones JS de las listas (bloque 4).

### 5.3 Vistas (resumen; ninguna hereda vistas del core salvo la de Ajustes)

| Archivo | Vistas | Observaciones de 14 |
|---|---|---|
| `mcp_user_views.xml` | lista/form `ai.mcp.user` | Botones generar/regenerar/borrar key con `attrs`. |
| `mcp_safe_operation_views.xml` | búsqueda/lista/form `ai.safe.operation` | Confirmar/cancelar desde lista y form; "Whitelist" solo admin. |
| `ai_context_views.xml` | lista/búsqueda/form `ai.context` | Registros `core` de solo lectura por `attrs`. |
| `ai_domain_index_views.xml` | lista/búsqueda de descubrimiento | |
| `mcp_change_journal_views.xml` | búsqueda/lista/form `ai.change.journal` | Botón "Revert" con confirmación. |
| `mcp_log_views.xml` | 2 listas, form, búsqueda `ai.log` | `widget="badge"` existe en 14 (core `addons/web/static/src/js/fields/field_registry_owl.js:24`); filtros con `datetime.datetime.now().replace(...)` (265-266, PENDIENTE que py.js lo evalúe). |
| `ai_provider_views.xml` | form/lista/búsqueda `ai.provider` | `api_key` con `password="True"`. |
| `ai_agent_views.xml` | lista/form `ai.agent` | Enlaces `<a data-token>` gestionados por JS. |
| `external_server_views.xml` | lista/form/búsqueda `ai.api.server` | `widget="ace"` con `mode: javascript` en campos de solo lectura (176, 184, 201) pese al comentario de que 14 solo trae modos python/xml (139-142): PENDIENTE. |
| `url_whitelist_views.xml`, `ai_fx_source_views.xml`, `ai_skill_views.xml`, `mcp_log_delete_menu_views.xml`, `mcp_api_key_wizard_views.xml` | CRUD simples / asistentes | |
| `res_config_settings_views.xml` | Hereda **`base.res_config_settings_view_form`**, xpath `//div[hasclass('settings')]`, `position="inside"` | XML ID y nodo verificados: core `odoo/addons/base/views/res_config_settings_views.xml:4,24`. Estructura `app_settings_block` / `o_setting_box` de 14. |

### 5.4 Assets — `views/assets.xml`

Plantilla `pns_ai_mcp.assets_backend` heredando `web.assets_backend` (12-42): 5 CSS, 3 librerías
vendor (`showdown.js`, `jspdf.umd.min.js`, `xlsx.full.min.js`) y 16 JS `_v14`. Se cargan para todos
los usuarios internos en todas las pantallas. INFERENCIA: las librerías vendor (sobre todo
`xlsx.full.min.js`) aumentan el peso del backend para todos y definen globales (`showdown`, `jspdf`,
`XLSX`) que podrían chocar con otros módulos que traigan las mismas; los 9 `ListController.include`
modifican el prototipo de todas las listas (análisis en bloque 4).

---

## 6. Ajustes (`models/res_config_settings.py` + `views/res_config_settings_views.xml`)

Quién los ve: usuarios con `base.group_system` **y** `group_ai_admin` (§5.1). Ruta: Ajustes →
pestaña "AI Engine", o AI Engine → Settings.

### 6.1 Campos

| Campo | Tipo | `config_parameter` | Valor por defecto | Sembrado al instalar | Líneas |
|---|---|---|---|---|---|
| `display_currency` | Selection (~50 ISO, `utils/display_currency.py:10`) | `pns_ai_mcp.display_currency` | `USD` | No | 33-43 |
| `domain_index_inject` | Boolean | `pns_ai_mcp.domain_index_inject` | `True` | Sí, `'True'` (`_seed_install_icp`, 317-321) | 45-55 |
| `url_access_policy` | Selection `whitelist_only` / `open` | `pns_ai_mcp.url_access_policy` | `whitelist_only` | No (se usa el valor por defecto de `get_param`, 231-233) | 57-69 |
| `skill_code_prefix` | Char | `pns_ai_mcp.skill_code_prefix` | `custom_` (`utils/skill_code_prefix.py:17`) | Sí | 71-81 |
| `skill_command_prefix` | Char | `pns_ai_mcp.skill_command_prefix` | `custom-` (`skill_code_prefix.py:18`) | Sí | 82-91 |

Ningún campo tiene `groups=`; la visibilidad la da el atributo `groups` del bloque.

### 6.2 Botones (todos `type="object"`)

| Botón | Método | Qué hace | Comprobación |
|---|---|---|---|
| Configuration (agente MCP) | `action_open_module_agent` (145-157) | Abre el formulario del agente `pns_ai_mcp` (búsqueda con `sudo`). | — |
| Browse all external / internal agents | `action_open_module_{endpoint,inference}_agents` (139-143) | Lista de agentes de módulo por tipo. | — |
| Manage quote sources | `action_open_fx_sources` (163-165) | `ai.fx.source`. | — |
| Manage URL Whitelist | `action_open_url_whitelist` (159-161) | `ai.url.whitelist`. | — |
| Export configuration | `action_export_ai_config` (167-194) | `config_backup.export_config(include_secrets=True)` → adjunto JSON → asistente de descarga. **Siempre con secretos.** | `ensure_ai_admin` (171) |
| Import configuration | `action_import_ai_config` (196-208) | Abre `pns_ai_mcp.config_backup_wizard`. | `ensure_ai_admin` |
| Export / Import artifact bundle | `action_export_artifact_bundle` / `action_import_artifact_bundle` (210-226) | Abre asistentes de bundle parcial. | `ensure_ai_admin` |

### 6.3 `get_values` / `set_values`

- `get_values` (228-246) sustituye los valores leídos por el core por los suyos normalizados.
- `set_values` (248-284): llama primero a `super()` (que ya escribe los cinco ICP, core
  `odoo/addons/base/models/res_config.py:585-599`) y después los reescribe. Observaciones:
  - INFERENCIA (por core `ir_config_parameter.py:86-97`: `set_param(key, False)` **borra** la
    clave): al desmarcar `domain_index_inject`, `super()` borra la clave, la lectura posterior
    (255-257) devuelve el valor por defecto `'True'` y se reconstruyen las cachés; al volver a
    marcarla, `super()` ya escribió `'True'`, la comparación no ve cambio y **no** se reconstruyen
    las cachés. Además, mientras esté desmarcado, **cada** guardado de cualquier pantalla de Ajustes
    reconstruiría las cachés de todos los agentes (264, 286-305). PENDIENTE.
  - HECHO (271-282): si el prefijo coincide con un comando existente lanza `UserError`. Como
    `set_values` se ejecuta al guardar **cualquier** ajuste, INFERENCIA: un conflicto de prefijos
    impediría guardar ajustes de otros módulos hasta corregirlo.
- `_seed_install_icp` (307-327): solo crea las tres claves si no existen; llamado desde
  `data/instance_defaults_data.xml:6` vía `post_init_hook`.

---

## 7. Datos que crea al instalar

### 7.1 Parámetros del sistema (`ir.config_parameter`)

| Clave | Valor | Origen |
|---|---|---|
| `pns_ai_mcp.skill_code_prefix` | `custom_` | `_seed_install_icp` |
| `pns_ai_mcp.skill_command_prefix` | `custom-` | ídem |
| `pns_ai_mcp.domain_index_inject` | `True` | ídem |
| `pns_ai.factory_knowledge_stamp` | sello de módulos con `ai/` | `hooks.py:24,237-242` |

Otras claves que el código lee o escribe más adelante (fuera del bloque, solo localizadas):
`pns_ai_mcp.display_currency`, `pns_ai_mcp.url_access_policy`, `pns_ai_mcp.skills_slash_hidden`
(`models/ai_skill.py:53`), `pns_ai_mcp.fx_usd_cache` (`models/ai_fx_source.py:18`),
`pns_ai_mcp.dataset_cache_max_bytes` (`utils/agent_engine.py:32`).

### 7.2 Crons

| XML ID | Modelo / código | Frecuencia | Activo | `numbercall` | Archivo |
|---|---|---|---|---|---|
| `ir_cron_ai_fetch_cache_gc` | `ai.fetch.cache` → `model.gc_expired()` | 1 hora | Sí | -1 | `data/fetch_cache_cron.xml:6-16` |
| `ir_cron_ai_api_result_cache_gc` | `ai.api.result.cache` → `model.gc_expired()` | 1 hora | Sí | **no se indica** | `data/api_result_cache_cron.xml:5-13` |
| `ir_cron_ai_safe_operation_expire` | `ai.safe.operation` → `model.cleanup_expired()` | 5 minutos | Sí | -1 | `data/safe_operation_cron.xml:6-16` |

HECHO (core `odoo/addons/base/models/ir_cron.py:63,145-155`): en 14 `numbercall` vale **1** por
defecto y el cron se desactiva cuando llega a 0. **La purga de la caché de `api_call` se ejecuta una
sola vez y se desactiva**, y la tabla `ai_api_result_cache` crecerá sin límite. Los tres archivos son
`noupdate="1"`. Ningún archivo Python del módulo toca `numbercall` (HECHO, búsqueda).

### 7.3 Secuencias

- `sequence_safe_operation` (código `pns_ai_mcp.safe_operation`, prefijo `VERIF-`, relleno 8,
  `security/security.xml:184-191`). HECHO: **ningún código la usa**; el modelo crea al vuelo, con
  `sudo`, una secuencia por verbo `pns_ai_mcp.safe_op.<verbo>` (`models/mcp_safe_operation.py:375-418`)
  y `pns_ai_mcp.safe_choice` (`models/ai_safe_choice.py:36-49`). Todas sin compañía.

### 7.4 Registros por defecto

Cargados en cada instalación **y actualización** (manifest):
- `ai.agent` `ai_agent_mcp`: "MCP Server", código `pns_ai_mcp`, tipo `endpoint`, origen `module`,
  `default_context_codes=@pns_ai_mcp`, `required_context_codes=self_mcp` (`data/ai_agent_data.xml:8-21`,
  `noupdate="1"`).
- Funciones de `data/mcp_data.xml:5-11` (`noupdate="0"`, se ejecutan en cada `-u`): importar
  contextos de `ai/contexts` con reemplazo, importar skills "system" (no hay archivos: 0 skills),
  enlazar descubrimiento de API huérfano.
- `ai.api.server` (`data/external_server_data.xml`, `noupdate="1"`, todos **inactivos**, tipo
  `stdio`, comando `npx -y @modelcontextprotocol/...`): `external_server_mcp_test` (15-35),
  `external_server_brave_search` con `BRAVE_API_KEY: YOUR_API_KEY_HERE` (43-68),
  `external_server_sequential_thinking` (76-95). Requieren Node.js/npx en el servidor y descargan
  paquetes de npm al activarse (INFERENCIA por `npx -y`).
- `ai.fx.source` (`data/fx_source_data.xml`, `noupdate="1"`, **activos**):
  `https://open.er-api.com/v6/latest/USD` y `https://api.frankfurter.app/latest?from=USD`.
  INFERENCIA: Odoo hará peticiones salientes a esos servicios para convertir costes (bloque 2).
- `ai.trusted.action` (`data/trusted_actions_system.xml`, **sin** `noupdate`: se reescriben en cada
  `-u`), todas con modelo `ai.system.action` y grupo `group_ai_admin`: `field.set_required`,
  `view.set_field_required`, `view.set_field_readonly`, `view.set_field_invisible`,
  `view.set_field_domain`, `view.reset_field_modifiers` (peligro medio) y `module.update`,
  `user.add_group`, `user.remove_group` (peligro alto).

Cargados solo en la primera instalación (`post_init_hook`, `noupdate=True`):
- `ai.provider` (`data/ai_provider_data.xml`), sin API keys: OpenRouter
  (`https://openrouter.ai/api/v1/chat/completions`, modelo `x-ai/grok-4.5`), OVH (endpoint
  `oai.endpoints.kepler.ai.cloud.ovh.net`, modelo `Qwen3.6-27B`), Lemonade
  (`http://localhost:13305/...`, on-premise) y Ollama (`http://localhost:11434/...`, on-premise).
  Dos `ai.provider.model`. No se enlazan a ningún agente.
- `ai.api.server` OpenAPI (`data/external_server_openapi_data.xml`): `sesame` (Sesame HR, spec
  pública) y `cdmon` (spec manual), ambos inactivos, `trusted=False`, `auth_type=bearer` sin token.
  `_load_factory_spec_json(..., 'cdmon.json')`: el archivo `data/openapi/cdmon.json` **no existe**
  (HECHO, glob), así que no hace nada (`models/external_server.py:751-776`).
- `ai.url.whitelist`: `api.open-meteo.com` y `geocoding-api.open-meteo.com`, activos
  (`data/url_whitelist_data.xml:7-19`).
- ICP de §7.1.

Además: contextos `ai.context` desde `ai/contexts` (número PENDIENTE), `ir.module.category`, 4
grupos, 14 reglas, plantilla de assets.

---

## 8. Asistentes (`wizard/` y transitorios del bloque)

Todos los de importación heredan `pns.operation.report.wizard` ([BASE] §2.4) y muestran el
resultado con vistas propias de `wizard/operation_result_views.xml`. Los "Tools" heredan el mixin
vacío `pns.export_import.tools.wizard.mixin` (`wizard/tools_wizard_mixin.py:9-11`).
`wizard/operation_result.py` solo contiene funciones de mapeo, no modelos.

| Modelo | Archivo | Quién puede (ACL) | Se lanza desde | Qué hace / qué modifica o exporta |
|---|---|---|---|---|
| `pns_ai_mcp.config_backup_wizard` | `config_backup_wizard.py` | admin | Ajustes → Import configuration | Sube JSON/ZIP y llama a `config_backup.import_config`: restaura **toda** la configuración (proveedores, agentes, contextos, skills, servidores, lista blanca, hashes de API key por login, ajustes ICP). Empareja por clave de negocio; no borra (vista 15-17). `ensure_ai_admin` (45). |
| (exportación) | `models/res_config_settings.py:167-194` | admin + Ajustes | Ajustes → Export configuration | JSON con **secretos en claro** (`include_secrets=True`, 172; aviso en la vista 172-174). Adjunto `ir.attachment` sin `res_model` que no se borra ([BASE] §4 obs. 3). |
| `pns_ai_mcp.artifact_bundle.export.wizard` | `artifact_bundle_export_wizard.py` | admin | Ajustes | ZIP parcial con skills, contextos, proveedores, agentes, servidores, usuarios MCP, lista blanca; `include_secrets` y `include_settings` **desactivados** por defecto (20-29). `ensure_ai_admin` dentro de `utils/artifact_bundle.py:62`. |
| `pns_ai_mcp.artifact_bundle.import.wizard` | `artifact_bundle_import_wizard.py` | admin | Ajustes | Importa el ZIP; `replace_existing=True` por defecto (30-35): **sobrescribe** por clave de negocio. `ensure_ai_admin` en `artifact_bundle.py:188`. |
| `pns_ai_mcp.import_servers_wizard` (proveedores) | `import_servers_wizard.py` | admin | `ai.provider.action_import_providers` (lista/Tools) | Crea/actualiza `ai.provider` por nombre, incluida `api_key` (70-78), modelos (106-119, **borra y recrea** los modelos disponibles), cadena de agentes con `savepoint` por asignación (144-194) y días de uso. |
| `pns_ai_mcp.import_agents_wizard` | `import_agents_wizard.py` | admin | `ai.agent.action_import_agents` | Crea/actualiza `ai.agent` por código; con reemplazo **borra** su cadena de proveedores y la recrea (72-96). |
| `pns_ai_mcp.import_users_wizard` | `import_users_wizard.py` | admin | `ai.mcp.user.action_import_users` | Por login, crea/actualiza `ai.mcp.user` con `sudo`, **incluido el hash de API key** (`mcp_api_key_hash`; acepta claves en claro antiguas, vista 10-12). INFERENCIA: permite fijar la credencial MCP de cualquier usuario, también del administrador. Qué otros campos aplica (`_import_vals_from_json_row`, p. ej. flags de grupos) → bloque 2. |
| `pns_ai_mcp.import_whitelist_wizard` | `import_whitelist_wizard.py` | admin | `ai.url.whitelist.action_import_whitelist` | Crea/actualiza dominios (`active`, `notes`, vigencias). |
| `pns_ai_mcp.import_external_servers_wizard` | `import_external_servers_wizard.py` | admin | `ai.api.server.action_import_external_servers` | Aplica **cualquier** campo escribible de `ai.api.server` presente en el JSON (91-104), incluidos `command`, `command_args`, `env_vars`, `trusted`, tokens. INFERENCIA: importar un JSON ajeno puede dejar configurado un comando del sistema que se ejecutará al probar o descubrir el servidor. |
| `pns_ai_mcp.context_import_wizard` | `context_import_wizard.py` | admin | Acción "Import contexts from ZIP" en lista de contextos | Importa `.txt/.md/.xml/.zip`; con reemplazo actualiza por código + ruta. Sin límite de tamaño ni de número de miembros del ZIP (INFERENCIA: riesgo de ZIP bomba, bajo por ser solo admin). |
| `pns_ai_mcp.agent.import.wizard` | `bundle_import_wizard.py` | admin | Desde agente (PENDIENTE: ningún botón en la vista; método en `ai.agent`/JS) | Importa "context pack" a un agente; `replace_composition=True` por defecto: **sustituye** la composición del agente. |
| `pns_ai_mcp.agent.context.import.wizard` / `.agent.skill.import.wizard` | `agent_context_import_wizard.py`, `agent_skill_import_wizard.py` | admin | Menú Acción del formulario de agente | Importan contextos/skills de ZIP y los asignan al agente. |
| `pns_ai_mcp.skill.import.wizard` | `skill_import_wizard.py` | admin | Acción "Import skills from ZIP" | Importa skills (incluye `code_body` ejecutable). |
| `pns_ai_mcp.skill.capture.wizard` | `skill_capture_wizard.py` | **writer** | Chatboo `/create-skill` (INFERENCIA) | Crea un `ai.skill` con el código ejecutado en un log; queda **activo** si `from_chatboo` (190), un campo `readonly` solo en la interfaz que puede llegar por contexto `default_from_chatboo` (84-85) o por RPC. INFERENCIA: un Writer puede publicar código ejecutable activo; su alcance depende del sandbox (bloque 3). |
| `pns_ai_mcp.agent.compose.wizard` + `.agent.compose.line` | `bundle_compose_wizard.py` | writer | PENDIENTE (ningún botón en vistas del bloque) | Añade/quita contextos de un agente y reconstruye la caché. INFERENCIA: un Writer no puede escribir `ai.agent` (CSV 15, 52) y obtendrá error. |
| `pns_ai_mcp.agent.cache.rebuild.wizard` | `bundle_cache_rebuild_wizard.py` | writer | Botón "Rebuild cache" del agente | Muestra informe HTML de la reconstrucción. |
| `pns_ai_mcp.context_stats_wizard` | `context_stats_wizard.py` | **todos los internos** | Acción "MCP context statistics" / botón Statistics del agente | Estadísticas de tamaño del bundle del agente MCP (solo lectura). |
| `pns_ai_mcp.context.tools.wizard` | `mcp_context_tools_wizard.py` | admin | Botón de la lista (JS) | Estadísticas, restaurar desde módulo (sobrescribe contextos de fábrica, `replace_existing=True` por defecto), exportar e importar ZIP. |
| `pns_ai_mcp.skill.tools.wizard` | `skill_tools_wizard.py` | admin | Botón de la lista (JS) | Recargar skills desde archivos, exportar/importar ZIP. |
| `pns_ai_mcp.{agent,provider,user,whitelist,external_server}.tools.wizard` | `*_tools_wizard.py` | admin | Botón "Operaciones" de cada lista (JS) | Exportar JSON (con secretos según el modelo, bloque 2) / abrir el asistente de importación. |
| `pns_ai_mcp.log.tools.wizard` | `mcp_log_tools_wizard.py` | admin | Lista de Activity (JS) | Exportar logs a JSON; abrir el borrado. |
| `pns_ai_mcp.safe.operation.tools.wizard` | `safe_operation_tools_wizard.py` | todos los internos | Lista de autorizaciones (JS) | Refrescar caducidad; exportar (botón solo admin + `ensure_ai_admin`). |
| `pns_ai_mcp.json_export_wizard` | `json_export_wizard.py` | admin | Resultado de cualquier exportación | Hereda `pns.export.file.wizard` ([BASE] §2.5): botón de descarga del adjunto. |
| `pns_ai_mcp.log_delete_menu` | `models/mcp_log_delete_menu.py` | admin y `base.group_system` | Cabecera de la lista Activity / Log Tools | Borra todos los `ai.log` o deja los N más recientes (10…100 000), vía `ai.log._delete_oldest_logs`; comprueba grupos en Python (57-61). |
| `pns_ai_mcp.api_key_wizard` | `models/mcp_api_key_wizard.py` | admin | Botones del usuario MCP / "Import existing API key" | Genera (muestra una vez, guarda hash; ver §4.5 riesgo 6), importa una clave elegida o un hash (`set_mcp_api_key`, `models/mcp_user.py:403-417`) o la borra. |

Resumen de copias con secretos:
- Siempre con secretos: Ajustes → Export configuration.
- Con secretos si se marca: bundle parcial.
- INFERENCIA (bloque 2): exportación JSON de proveedores incluye `api_key` para el administrador
  (`export_record_dict` vuelca los Char, [BASE] §2.6; `models/ai_provider.py:596-652`); la de
  servidores externos incluiría `auth_token`/`env_vars`; la de usuarios MCP incluye hashes.
- Ningún adjunto exportado se borra automáticamente.

---

## 9. Configuración necesaria, en orden

1. **Imagen/servidor**: Python con `openpyxl`, `reportlab`, `requests`, **`httpx` y `pydantic`**
   (§1.2, sin ellos no instala). Node.js/npx solo si se usarán servidores MCP `stdio`. Salida a
   Internet hacia los proveedores LLM y fuentes de cambio (§7.4).
2. **Instalar** `pns_base` y `pns_ai_mcp` (Aplicaciones → "AI Engine").
3. **Asignar grupos** (Ajustes → Usuarios y compañías → Usuarios → usuario → sección "Artificial
   Intelligence"): al menos un usuario con **AI Administrator** que además sea **Administración /
   Ajustes**; Writer / External URL / External API para los usuarios que deban proponer
   escrituras, consultar URLs o llamar APIs externas. Ningún grupo se asigna solo (§4.1).
4. **Proveedores** (AI Engine → Connections → Providers): en el proveedor elegido, poner `API Key`,
   "Fetch Models", elegir modelo y "Test Connection". Los cuatro proveedores sembrados no tienen
   clave (§7.4).
5. **Agentes** (AI Engine → Agents): el agente "MCP Server" ya existe (endpoint, sin proveedor).
   Los agentes de inferencia los aportan otros módulos (p. ej. Chatboo); a esos hay que asignarles
   proveedores en la pestaña "Providers" (`views/ai_agent_views.xml:140-153`).
6. **Usuarios MCP y claves** (AI Engine → Security → Users): abrir la lista crea las filas; en cada
   usuario que vaya a usar un cliente MCP externo, "Generate API Key" y copiarla en ese momento.
7. **Ajustes** (Ajustes → AI Engine, o AI Engine → Settings): política de URL (`whitelist_only` por
   defecto) y lista blanca; moneda de presentación y fuentes de cambio; "Turn-scoped domain packs";
   prefijos de skills (`custom_` / `custom-`).
8. **Opcional**: servidores externos (AI Engine → Connections → External Servers): pegar token,
   activar, "Discover Tools"; decidir `trusted` (si se activa, `api_call` se ejecuta sin
   confirmación, `models/external_server.py:221-235`).
9. **Revisar crons** (Ajustes → Técnico → Automatización → Acciones planificadas): tras la primera
   ejecución, "AI: purge expired api_call result cache" quedará inactivo (§7.2).
10. **Cliente MCP externo**: URL `https://<odoo>/mcp` (o `/mcp/<agent_code>`) con la API key del
    usuario; detalles de cabeceras y de selección de base de datos con `auth='none'` en bloque 3.

---

## 10. Compatibilidad con Odoo 14 y Python 3.7.3 (archivos del bloque)

### 10.1 Python
- HECHO: no hay construcciones posteriores a 3.7 en los archivos del bloque (f-strings con formato
  anidado en `context_stats_wizard.py:172-181` y `{**dict}` en
  `artifact_bundle_export_wizard.py:82-87` son válidos desde 3.6). Búsqueda en todo el módulo de
  `:=`, `removeprefix/removesuffix`, `match`, `functools.cache`, `Literal`, `TypedDict`: solo
  aparecen dentro de expresiones regulares (`controllers/tools_relaxaicode.py:906,922`).
- HECHO: muchos `utils/` usan `from __future__ import annotations` (p. ej. `fx_rates.py:5`,
  `artifact_bundle.py:10`): requieren Python ≥ 3.7, como `pns_base` ([BASE] §12.1). La imagen local
  usa 3.7.3 ([BASE] §12.1); falta confirmar el VPS.

### 10.2 Odoo 14
| Punto | Estado |
|---|---|
| Clave `assets` del manifest | Ignorada en 14 (HECHO); sustituida por `views/assets.xml`. |
| Plantillas QWeb de cliente | No se cargan (sin clave `qweb`); no se necesitan en 14 (HECHO). |
| Firmas de hooks `(cr, registry)` | Correctas (`hooks.py:27-38,99`). |
| `convert_file` | Firma de 14 respetada (core `odoo/tools/convert.py:722`). |
| Herencia de Ajustes | XML ID y xpath válidos (core `base/views/res_config_settings_views.xml:4,24`). |
| `_visible_menu_ids`, `_process_ondelete`, `_get_records`, `Root.get_request` | Existen con la firma usada (core citado en §3). |
| Botón en cabecera de lista, `widget="badge"`, `sample="1"`, `default_order` | Soportados en 14 (core citado en §5.3). |
| `widget="ace"` modo `javascript` | PENDIENTE (los estáticos de `web/static/lib` no están en la referencia). |
| Crons `numbercall`/`doall` | Existen en 14; falta `numbercall` en un cron (§7.2). |
| `res.config.settings` con Selection/Boolean/Char `config_parameter` | Soportado (core `res_config.py:477-480,585-599`). |

### 10.3 `migrations/`: probablemente **no se ejecutan nunca en Odoo 14**

HECHO (core `odoo/modules/migration.py:108-111,144-161`):
- `convert_version` considera "con versión de servidor" cualquier carpeta con dos o más puntos, así
  que `3.1.47`…`3.1.484` se comparan tal cual.
- La versión instalada y la del manifest se guardan adaptadas a `14.0.3.1.x` (core
  `module.py:366,441-445`, `loading.py:277-279`).
- La condición `installed < '3.1.47' <= current` compara `14.0.…` con `3.1.…`; como 14 > 3, es
  siempre falsa.

INFERENCIA fuerte: con el manifest en `3.1.486`, **ningún script de `migrations/` se ejecutará en
Odoo 14** al actualizar el módulo. Hoy no importa (el módulo entra en esta rama directamente en
3.1.486), pero cualquier actualización futura del proveedor que dependa de una migración (renombrar
columnas, purgar datos) no se aplicará. `hooks.py:13-14` dice explícitamente que esas tareas viven en
`migrations/`. PENDIENTE: confirmarlo con un `-u` y buscar "Running migration" en el log.

### 10.4 Índice de `migrations/` (78 scripts; solo cabecera leída)

| Versión | Script | Qué hace |
|---|---|---|
| 3.1.47 | post | Recarga traducciones del módulo con sobrescritura. |
| 3.1.102 | post | No-op. |
| 3.1.105-3.1.111 | post (7) | Reimporta el contexto `geo` (cambios de mapas/pines) y reconstruye cachés (105). |
| 3.1.113, 3.1.114 | post | Reimporta skills desde archivos (`sesame-geo`). |
| 3.1.115, 3.1.117 | post | Reimporta skills y el contexto `geo`. |
| 3.1.116 | post | `DELETE` de filas miss/error en `ai_geo_place` y refresca `geo`. |
| 3.1.118, 3.1.119 | post | Refresca contextos `geo` / `presentation_grids`. |
| 3.1.135, 3.1.142 | post | Enriquece/regenera minimapas de `ai.geo.route`. |
| 3.1.136 | pre | Renombra tablas `ai.geo.cache→ai.geo.place` y `ai.geo.distance.cache→ai.geo.route`; purga selecciones huérfanas. |
| 3.1.140 | post | Fuerza etiquetas de menús/acciones (EN/ES). |
| 3.1.145 | post | Borra el menú `menu_ai_entities`. |
| 3.1.146 | post | Renombra menú Geography → Geo. |
| 3.1.149 | post | Elimina menús, acciones y modelos geo (movidos a `pns_geo`). |
| 3.1.239 | post | Códigos de skill a snake_case. |
| 3.1.281 | post | Contextos por defecto del agente MCP (`@pns_ai_mcp`, `acl_security`). |
| 3.1.285, 3.1.289 | post | Activa `domain_index_inject` y reconstruye cachés. |
| 3.1.290 | post | No-op. |
| 3.1.291 | post | `cost_policy` → `is_on_premise` en proveedores. |
| 3.1.293 | post | Borra ICP `domain_index_shadow`; asegura `domain_index_inject`. |
| 3.1.294, 3.1.295 | post | Reconstruye cachés de agentes MCP/Chatboo/ACL. |
| 3.1.297 | post | Siembra ICP de skills ocultas en slash. |
| 3.1.299 | post | Índice de dominios pasa a contextos `discover`; reimporta. |
| 3.1.325 | pre | Renombra `max_agent_turns→max_agent_rounds` y `llm_turn_timeout→llm_round_timeout`. |
| 3.1.362, 3.1.363 | post | Borra contextos de fábrica en otros idiomas (solo EN + es_ES). |
| 3.1.365 | pre | Renombra tokens/columnas `translation→locale`, `discover→discovery`. |
| 3.1.368, 3.1.370 | post | Fija etiquetas de `context_type`; 370 borra columnas sobrantes con `ALTER TABLE … DROP COLUMN` formateado con `%` (sin parámetros). |
| 3.1.371, 3.1.379-3.1.381 | post | Purga/reescribe restos `disc_*`. |
| 3.1.376 | post | Rellena semillas de fábrica vacías de agentes. |
| 3.1.402, 3.1.403 | post | Refresca `system_prompt`. |
| 3.1.404 | post | Fija `self_mcp` en el agente endpoint. |
| 3.1.405-3.1.407, 3.1.410 | post | Retira contextos `self` y packs de identidad ajenos. |
| 3.1.408 | post | **Borra archivos** sobrantes en la ruta del addon instalado. |
| 3.1.424, 3.1.425 | post | Filtros de origen del agente (`link_show_*`). |
| 3.1.431, 3.1.433, 3.1.434 | post | Limpia traducciones de etiquetas de origen. |
| 3.1.448, 3.1.450, 3.1.451 | post | Borra filas de descubrimiento/skills cuyo archivo ya no existe o con idioma distinto de es_ES. |
| 3.1.449, 3.1.454 | post | Archiva/borra skills "slash" duplicadas sin prefijo. |
| 3.1.463, 3.1.465 | post | Renombra códigos de contexto (`commercial_documents→business_documents`, quita `domain_knowledge_`). |
| 3.1.476, 3.1.483, 3.1.484 | post | Fuerza `group_ai_admin` en el menú "Changes". |

---

## 11. Riesgos, dudas y lo que no se puede saber sin ejecutar

### 11.1 Riesgos (de mayor a menor)

1. **Secretos expuestos a cualquier usuario interno**: tokens y variables de entorno de servidores
   externos legibles por RPC (§4.5-1); cachés de resultados de otros usuarios (§4.5-2).
2. **AI Administrator ≈ administrador de Odoo + acceso al sistema operativo** (§4.5-5).
3. **Posible manipulación de autorizaciones** por escritura directa de `ai.safe.operation` y acceso
   total a `ai.safe.choice` (§4.5-3).
4. **Exportación de configuración siempre con secretos**, en adjuntos que no se borran (§8).
5. **Bypass de comprobaciones por contexto** `skip_hardcoded_restrictions` (§4.5-4).
6. **Efectos fuera de PNS**: parche de proceso de `Root.get_request` (§3.2), backport global de
   `_process_ondelete` (§3.3), `set_values` en todos los guardados de Ajustes (§6.3), escaneo de
   todos los módulos en cada arranque (§3.1), 3 librerías JS y 10 parches de prototipo del cliente
   web en todo el backend (§5.4), 3 crons nuevos (uno cada 5 minutos). Se suman a los de `pns_base`
   ([BASE] §13).
7. **Instalación bloqueada** si faltan `httpx`/`pydantic` (§1.2).
8. **Migraciones que no se ejecutan** en 14 (§10.3).
9. **Cron de caché de `api_call` que se apaga tras una ejecución** (§7.2).
10. **Herramientas MCP que pueden desaparecer en silencio** por el `except ImportError: pass`
    (§2.2).
11. API key generada en claro en tabla transitoria (§4.5-6); HTML sin sanear (§4.5-7).

### 11.2 Pendiente de comprobar con `odoo-dev 14`

- `odoo-dev 14 paridad` / instalación: ¿la imagen trae `httpx` y `pydantic`?
- Instalación limpia de `pns_ai_mcp`: log de `post_init_hook` (contextos importados, avisos),
  validación de todas las vistas (incluidas las `ace` en modo `javascript` y los filtros con
  `datetime`), número de `ai.context` creados.
- `-u pns_ai_mcp`: confirmar que no aparece "Running migration" (§10.3).
- Cron de `api_result_cache` inactivo tras su primera ejecución.
- Usuario con solo `group_ai_admin` (sin Ajustes) abriendo AI Engine → Settings.
- Usuario interno sin grupos IA: `read` por RPC de `ai.api.server` (`auth_token`, `env_vars`),
  `ai.fetch.cache`, `ai.api.result.cache`, `ai.safe.choice`; `write` de su `ai.safe.operation`.
- Guardar Ajustes de otro módulo con `domain_index_inject` desmarcado y con un prefijo de skill en
  conflicto.
- Ficha de usuario: cómo se presentan los grupos de "Artificial Intelligence".
- Ejecución de los tests del módulo (`odoo-dev 14 tests pns_ai_mcp`).

---

## 12. Tabla de cobertura

| Archivo / grupo | Lectura |
|---|---|
| `__manifest__.py`, `__init__.py`, `hooks.py`, `http_patch.py`, `constants.py` | Entero |
| `security/security_groups.xml`, `security/security.xml`, `security/ir.model.access.csv` | Entero |
| `data/` (12 archivos) | Entero |
| `views/` (19 archivos, incluido `mcp_field_widgets.xml` vacío) | Entero |
| `wizard/` (30 `.py` + 27 `_views.xml`) | Entero |
| `models/res_config_settings.py`, `ir_ui_menu.py`, `ir_model_fields_selection.py`, `mcp_log_delete_menu.py` | Entero |
| `models/mcp_api_key_wizard.py`, `utils/mcp_ui.py`, `utils/compat.py`, `utils/import_export_guard.py` (fuera del bloque) | Entero |
| `controllers/__init__.py`, `moe_controller.py`, `safe_operation.py`, `lib/llm/__init__.py`, `lib/llm/utils/__init__.py`, `lib/llm/drivers/__init__.py`, `lib/api/drivers/__init__.py`, `tests/__init__.py`, `static/src/xml/mcp_field_widgets.xml` (inventario) | Entero |
| `migrations/` (78 scripts) | Parcial a propósito: solo cabecera/docstring (índice pedido) |
| Resto de `models/`, `controllers/`, `utils/`, `lib/`, `tests/` | Parcial: cabecera, clases y líneas concretas citadas (inventario) |
| `static/src/js`, `static/src/css` | Parcial: búsqueda de registros, `include` y selectores |
| `ai/` | No (solo nombres de archivo) |
| `i18n/`, `static/description/`, `LICENSE` | No |

---

## Preguntas abiertas

1. ¿La imagen Docker local y la del VPS del cliente tienen `httpx` y `pydantic`? Si no, ¿se añaden
   a la imagen (Dockerfile del cliente) aunque el módulo no los importe, o se pide al fabricante que
   los quite de `external_dependencies`?
2. ¿Qué usuarios tendrán **AI Administrator**? Dado que permite instalar/desinstalar módulos, añadir
   grupos nativos a usuarios y ejecutar comandos `stdio` en el servidor, ¿se restringe a quienes ya
   son administradores de Odoo?
3. ¿Se acepta que cualquier usuario interno pueda leer por RPC los tokens (`auth_token`,
   `env_vars`) de los servidores externos y las cachés de respuestas de otros usuarios? ¿Se
   activarán servidores con datos sensibles (Sesame RR. HH.)?
4. ¿Se usarán las copias de configuración? Siempre incluyen secretos y sus adjuntos no se borran:
   ¿quién puede generarlas y cómo se custodian?
5. ¿Se utilizarán servidores MCP `stdio` (requieren Node/npx en el servidor y descargan paquetes de
   npm)? Si no, ¿se dejan inactivos los tres de ejemplo?
6. ¿Es aceptable el parche de proceso de `Root.get_request` sobre `/mcp` y el backport global de
   `_process_ondelete` para el resto de módulos del cliente? ¿Hay algún módulo que use rutas bajo
   `/mcp`?
7. ¿Se informa al fabricante de: migraciones que no se ejecutan en 14 (versión `3.1.x`), cron sin
   `numbercall`, ACL de `ai.safe.choice` y de cachés, `auth_token` sin `groups`, bypass por contexto
   `skip_hardcoded_restrictions`, y comportamiento de `set_values` con `domain_index_inject`?
8. ¿Las fuentes de tipos de cambio (`open.er-api.com`, `frankfurter.app`) y las llamadas a
   proveedores LLM externos son aceptables desde el punto de vista de protección de datos del
   cliente? ¿Se usará algún proveedor on-premise (Ollama/Lemonade)?
9. ¿Qué proveedor y modelo LLM se configurará realmente, y con qué clave? (Los sembrados no tienen
   ninguna.)
10. ¿Quién debe poder abrir AI Engine → Settings? Hoy exige a la vez Ajustes y AI Administrator.
