# Comparación con la versión 3.1.973 del fabricante (pns_ai, Odoo 14)

- **Fecha:** 09/11/2026.
- **Origen:** `_fabricante/3.1.973/`, descargado de GitHub (rama 14.0) el 09/11/2026 (`ORIGEN.txt`):
  - `pns_base` 1.2.69, commit `3f76f5854e1ba8bb42ac81854a14b8cc73fa078d`;
  - `pns_ai_mcp` 3.1.973, commit `2450983049e475fab78eb19215dd005bd40491c9`;
  - `pns_ai_chatboo` 2.1.587, commit `0c2e6e36ec4db8adfa2c26f6977b08cfe2aaf019`.
- **Base comparada:** `_fabricante/3.1.879/` (1.2.47 / 3.1.879 / 2.1.538) y la copia de trabajo de la rama
  `14.0-pns-ai-3879` (3.1.879 + parches de Seges 10 a 34; módulos de `8d218ea`, validados en el staging el
  09/11/2026).
- **Alcance:** primera pasada: §2 (inventario), §3.1 a §3.4 (filas Críticas y Altas del
  [inventario de hallazgos](estado_hallazgos_3879.md)) y §4 (parches 10 a 34). Segunda pasada (09/11/2026):
  §3.5 a §3.7 (Medias, Bajas y sin gravedad; CSP, `__pns_sandbox_attr__` y los 9 nombres de PNS-07), NUEVO-3 y
  NUEVO-4 en §3.4, §5 a §9 y §1 definitivo, con el contexto de Seges que dio Sergio el 09/11/2026 (§5).
- **Verificación independiente:** odoo-reviewer, partes 1 a 3 (09/11/2026); correcciones aplicadas el
  09/11/2026.
- **Método:** el de la [comparación con 3.1.879](comparacion_pns_ai_3-1-879.md): se trabaja por hallazgo, no
  por diff. Para cada fila, el `grep` de «Cómo comprobar si el fabricante ya lo ha corregido» del
  [registro](../pendiente/parches_pns_ai.md) (ejecutado con Grep contra `_fabricante/3.1.973`) y la lectura
  del código. Solo análisis estático (Read, Grep, Glob, y los `diff -rq` / `diff -ruN` ya generados); sin
  ejecutar Python ni Odoo. Lo que depende de la ejecución se marca **REQUIERE PRUEBA** (§9).
  No se usa como fuente el informe del fabricante (`_fabricante/doc/`).
- **Rutas:** salvo indicación, relativas a `_fabricante/3.1.973/`. «(copia)» = módulos de la copia de trabajo
  (`/home/soporte/GitHub/third_party/pns_*`). «3.1.879:» = `_fabricante/3.1.879/`. Core:
  `/opt/odoo-src/14.0/odoo/`.
- **Veredictos de §3 (sobre 3.1.973):** **CORREGIDO** (el código cierra el hallazgo) · **PARCIAL** (queda un
  resto concreto) · **SIN CAMBIO** (el hallazgo sigue igual que en 3.1.879) · **EMPEORA** · **NO APLICA**
  (el código del hallazgo ya no existe, o es de entorno o procedimiento). Si la corrección del fabricante
  difiere de la de Seges, se dice en qué (más amplia, más estrecha, otro criterio).
- **Gravedad:** la del inventario; para los hallazgos nuevos, propuesta con el criterio de la comparación
  anterior. Este documento no recomienda: da datos para decidir.

## 1. Resumen

**§3, todas las filas con estado CS, AC, AI, PSD o SE (89 filas; veredicto en 3.1.973):**

| Gravedad | CORREGIDO | PARCIAL | SIN CAMBIO | EMPEORA | NO APLICA | Total |
|---|---|---|---|---|---|---|
| Crítica | 2 | 3 | 2 | 0 | 0 | 7 |
| Alta | 3 | 2 | 7 | 0 | 0 | 12 |
| Media | 4 | 3 | 7 | 0 | 0 | 14 |
| Baja | 2 | 3 | 8 | 0 | 0 | 13 |
| Sin gravedad | 2 | 1 | 30 | 0 | 10 | 43 |
| **Total** | **13** | **12** | **54** | **0** | **10** | **89** |

Detalle de las Críticas y Altas en la tabla siguiente; del resto, en §3.6.

**§3.1, Críticas y Altas (19 filas):**

| Gravedad | CORREGIDO | PARCIAL | SIN CAMBIO | EMPEORA | NO APLICA | Total |
|---|---|---|---|---|---|---|
| Crítica | 2 (M10, PNS-101) | 3 (PNS-01, PNS-02, PNS-07) | 2 (PNS-54, PNS-102) | 0 | 0 | 7 |
| Alta | 3 (PNS-81 resto, PNS-83, M13) | 2 (PNS-19, PNS-100) | 7 (PNS-17, 18, 20, 23, 26, 70, 82) | 0 | 0 | 12 |
| **Total** | **5** | **5** | **9** | **0** | **0** | **19** |

**§3.2, CF782 Críticas y Altas (20 filas), dos veredictos:**

| Veredicto | Copia de trabajo | 3.1.973 |
|---|---|---|
| Sigue CORREGIDO | 19 | 19 (en 4 la corrección es más amplia que en 3.1.879: PNS-06, 08, 09, 14) |
| NO APLICA (el código ya no existe) | 1 (PNS-80) | 1 (PNS-80) |
| Regresión | 0 | 0 |

**§3.3, filas CF Críticas y Altas cuyo código toca 3.1.973:** 9 revisadas, **0 regresiones**.

**Hallazgos NUEVOS (§3.4 y §7.2): 5.**

| Id | Grav. (propuesta) | Afecta a | En una línea |
|---|---|---|---|
| NUEVO-1 | Alta | 3.1.973 sin el parche 18 | La guarda de columnas secretas no cubre valores ya en la caché del hilo (mecanismo confirmado en ejecución, P-1; por lectura, no se alcanza en los caminos revisados de un turno real) |
| NUEVO-2 | Baja | `-u` de 3.1.879 a 3.1.973 | Dos crons `noupdate` quedan llamando a un método que ya no existe |
| NUEVO-3 | Alta (AI Administrator) | Copia de trabajo; corregido en 3.1.973 | Un AI Administrator sin Ajustes fija la clave MCP de un administrador de Ajustes |
| NUEVO-4 | Alta (cualquier interno) | Copia de trabajo (`pns_base`); corregido en 1.2.69 | El asistente de exportación borra en `sudo` cualquier adjunto; basta crearlo: lo borra la limpieza de transitorios, como superusuario |
| NUEVO-5 | Baja | 3.1.973 | Sin rol Diseño, diseñan los proveedores con rol Conversación o sin rol de la cadena del agente de Chatboo, o, si no tiene cadena, todos los proveedores activos con el rol Conversación o sin rol (alternativa activa por defecto). Confirmado en ejecución y en interfaz (P-10) |

**Parches 10 a 34 (§4), ¿siguen haciendo falta con 3.1.973?**

| Resultado | N.º | Parches |
|---|---|---|
| Sí | 12 | 11, 16, 17, 19, 20, 21, 24, 26, 29, 32, 33, 34 |
| En parte | 7 | 12, 15, 18, 22, 25, 27, 28 |
| No (el fabricante lo corrige) | 6 | 10, 13, 14, 23, 30, 31 |

Esfuerzo de llevarlos a 3.1.973 (mantener lo que siga haciendo falta, o retirar y adaptar sus tests):
**bajo 20**, **medio 4** (23, 27, 29, 34), **alto 1** (18).

**Choques con decisiones (§6):** reintento automático de la tarjeta (sin choque con el código del
parche 16; cambia el sentido de la espera de 5 s, D29); AI Administrator implica AI Conversational (se
propaga en el `-u`; afecta a la reproducción de la ficha 26, a usuarios de prueba y a LIYBEN); plan como
solicitante frente al parche 12 (criterios distintos, compatibles); `_require_settings` y la decisión 10;
tests de E0′ (sobran con 3.1.973); roles frente a la decisión 6 (`fit_design` desaparece; Diseño cae en
Conversación salvo que se
desactive la alternativa; archivar el rol no sirve; medido en P-10); multicompañía (ningún parche choca por lectura; el 26 cambia de efecto).

**Camino C, candidatos claros (§8.1):** NUEVO-4, NUEVO-3, PNS-81 resto, comprobación del par contra el
*rebinding*, asistente «¿incluir secretos?», `command_args` y `ensure_ai_admin`, ACL de `ai.safe.choice`,
reglas de `ai.skill.param.cache` y `write` de la sesión de Chatboo.

**Migración a 17.0 (§8.2):** 24 de los 25 parches tocan Python o XML común a las series del fabricante; el 20
(JS `owl1`) y el 18 (ORM de 14) habría que rehacerlos.

**Límites:** no se han revisado las filas CF782 Medias y Bajas (13) ni las filas solo CF cuyo código no toca
3.1.973. Lo que depende de la ejecución o de los datos, en §9 (21 pruebas).

## 2. Inventario

### 2.1 Tamaño del cambio por módulo

Fuente: `diff -rq` y `diff -ruN` de `_fabricante/3.1.879` frente a `_fabricante/3.1.973` (sin `__pycache__`).

| Módulo | Archivos con cambios | + líneas | − líneas | Nuevos | Borrados | Lo más grande |
|---|---|---|---|---|---|---|
| `pns_base` | 27 | 1 064 | 222 | 13 (`CHANGELOG.md`, `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, `models/progress_job.py`, `security/progress_job_rules.xml`, `static/src/{js,css,xml}/pns_progress_dialog*`, `tests/` (2), `banner_store.png`) | 0 | `models/progress_job.py` (+248), `i18n/es.po` (+144 −7) |
| `pns_ai_mcp` | 350 | 21 861 | 20 339 | 52 (de código: 33 `.py`, 3 `.js`, 4 `.xml`, 2 `.json` de voz y 6 ejemplos de proveedor; además 4 documentos y 3 imágenes) | 82 (80 scripts de `migrations/`, `static/src/xml/mcp_field_widgets.xml`) | `utils/skill_runtime.py` (+197 −2952), `relaxaicode_render.py` (+75 −2705), `artifact_export.py` (+80 −2572), `controllers/safe_plan.py` (+85 −1967), `models/ai_skill.py` (+38 −1769) |
| `pns_ai_chatboo` | 107 | 4 032 | 5 571 | 17 (4 skills nuevas en 8 archivos, `utils/form_draft.py`, `static/src/js/chatboo_open_o14.js` y `_o15.js`, `tests/` (3), 4 documentos, 3 imágenes) | 47 (33 scripts de `migrations/`, 7 skills en 14 archivos) | `ai/skills/system/financial_health.py` (+158 −899), `chatboo_component_v2.js` (+392 −249), `forecast.py` (+158 −419), `chatboo_async_request.py` (+312 −245) |

Una parte grande del volumen es traducción de comentarios y docstrings del español al inglés (p. ej.
`pns_base/models/ir_ui_view_patch.py`, `chatboo_session.py`, `chatboo_formatters.js`), y `i18n/es.po` y
`static/description/index.html` en los tres módulos.

### 2.2 Repartos de archivos (código movido, no borrado)

En los cinco archivos más grandes de `pns_ai_mcp`, lo que desaparece pasa a módulos nuevos. El archivo
original queda como fachada que reexporta. Comprobado con Grep en los casos que tocan parches o hallazgos.

| Archivo de 3.1.879 | Pasa a (3.1.973) | Comprobación |
|---|---|---|
| `utils/skill_runtime.py` (−2952) | `skill_runtime_code_rewrite.py` (+737), `_param_schema.py` (+682), `_bind_args.py` (+624), `_read_values.py` (+530), `_help_prompts.py` (+391) | `bootstrap_skill_code_body` y `skill_code_refusal` siguen en `skill_runtime.py` |
| `utils/relaxaicode_render.py` (−2705) | `relaxaicode_render_base.py`, `_table.py`, `_geo.py`, `_columns.py`, `_tint.py`, `_cards.py`, `_groups.py`, `_page.py` | Filtro de esquema `http(s)` en `relaxaicode_render_base.py:257` (antes `:244`); `_link_*` en `_cards.py:18-45` |
| `utils/artifact_export.py` (−2572) | `artifact_export_formats.py`, `_excel_formulas.py`, `_xlsx_writer.py`, `_request.py`, `_table.py`, `_pdf_chart.py`, `_loader.py` | PNS-35 (Media): segunda pasada |
| `controllers/safe_plan.py` (−1967) | `safe_plan_validate.py`, `safe_plan_describe.py`, `safe_plan_execute.py`, `safe_plan_ack.py`, `safe_plan_http.py` | `safe_plan.py:36-57` reexporta `validate_safe_plan`, `execute_safe_plan`, etc. El paso `unlink` del parche 17 está ahora en `safe_plan_execute.py:213-238`; `crud_cusp_error`, en `safe_plan_validate.py:245` y `safe_plan_execute.py:156-216` |
| `models/ai_skill.py` (−1769) | `ai_skill_disk.py`, `ai_skill_slash.py`, `ai_skill_authoring.py`, `ai_skill_zip.py` | Métodos de PNS-11 en `ai_skill_disk.py:377-431` y `ai_skill_slash.py:281-372` |
| `controllers/formatters.py` (−294), `controllers/safe_operation.py` (−260) | `artifact_export_*`, `safe_plan_*` | Sin parches de Seges en ellos |

En `pns_ai_chatboo`, las skills se sustituyen: salen `annual_billing`, `cash_forecast`, `credit_facility`,
`customer_risk_analysis`, `sys_info`, `users_all` y `users_logged`; entran `bill_draft`, `sales_board`,
`top_sales` y `users`. Lo que hace el `-u` con las filas de las retiradas, en la segunda pasada (§7).

### 2.3 Archivos nuevos y borrados, agrupados

- **`pns_base`:** modelo nuevo `pns.progress.job` (trabajo en hilo con diálogo de progreso; regla en
  `security/progress_job_rules.xml`, línea nueva en el CSV) y su JS/CSS/plantilla; `tests/test_web_client.py`
  (necesita Chrome; sin él Odoo lo salta); documentos y banner.
- **`pns_ai_mcp`, superficie nueva:** `models/ai_provider_role.py` (roles de proveedor con datos en
  `data/ai_provider_role_data.xml`, vistas y dos asistentes de importación y herramientas),
  `models/sandbox_secret_read.py` y `utils/sandbox_secrets.py` (columnas secretas cerradas en la caja A),
  `utils/one_company.py` (multicompañía), `utils/ai_disclosure.py` (marca «generado por IA» en ficheros),
  `utils/spoken_words.py` y `data/spoken/*.json`, `static/examples/providers/*.json` (5, sin claves),
  `static/src/js/key_pin_desk_boot_o14.js`, `mcp_log_reload_o14.js`, `ai_provider_role_tree_v14.js`.
- **`pns_ai_mcp`, tests:** nuevos `_offline.py`, `test_key_of_settings_admin.py`, `test_one_company_live.py`,
  `test_sandbox_live_handles.py`, `test_sandbox_secret_read.py`, `test_skill_box_a.py`; 21 cambiados.
- **`pns_ai_mcp`, borrados:** los 80 scripts de `migrations/` (§2.6) y `static/src/xml/mcp_field_widgets.xml`
  (plantillas OWL 2 de Odoo 17; en 14 no se usaban).
- **`pns_ai_chatboo`:** `utils/form_draft.py` (borrador de formulario para `/bill-draft`),
  `chatboo_open_o14.js` y `_o15.js`, y `tests/` (`__init__.py`, `test_chatboo_perimeter.py`,
  `test_chat_agent_composition.py`). Borrados: los 33 scripts de `migrations/` y las 7 skills citadas.
- **Archivos de Seges sin equivalente en el fabricante:** `pns_ai_mcp/models/box_a_guard.py` (parche 18),
  `pns_ai_mcp/controllers/relaxaicode_format_guard.py` (parche 23 ampliado), los 14 `test_seges_*.py` de
  `pns_ai_mcp/tests/` y la carpeta `pns_ai_chatboo/tests/` entera (6 `test_seges_*.py`, `common.py`,
  `__init__.py`). **Choque:** 3.1.973 trae su propio `pns_ai_chatboo/tests/__init__.py` (y `pns_base/tests/`).

### 2.4 Manifiestos

| Clave | `pns_base` 3.1.879 → 3.1.973 | `pns_ai_mcp` 3.1.879 → 3.1.973 | `pns_ai_chatboo` 3.1.879 → 3.1.973 |
|---|---|---|---|
| `version` | `1.2.47` → `14.0.1.2.69` (`__manifest__.py:8`) | `3.1.879` → `14.0.3.1.973` (`:8`) | `2.1.538` → `14.0.2.1.587` (`:7`) |
| `name` / `category` | sin cambio / `Technical` | `AI Engine` → `PNS AI Engine`; `Patanegra AI` → `Extra Tools` | `Chatboo` → `Chatboo — AI Chat Assistant`; → `Productivity` |
| `website` | `/pns_base/static/description/index.html` → `https://github.com/patanegra-soft/pns_base` | → `https://www.patanegra.com/ai-engine.html` | → `https://www.patanegra.com/chatboo.html` |
| `images` | nuevo `static/description/banner_store.png` | nuevo, ídem | nuevo, ídem |
| `license` | `Other OSI approved licence` (sin cambio) | ídem; añade el comentario «Apache License 2.0 — see LICENSE file» (`:29`) | ídem (sin cambio) |
| `depends` | `['web', 'mail']` (sin cambio) | `['web', 'pns_base']` (sin cambio) | `['web', 'bus', 'mail', 'pns_base', 'pns_ai_mcp']` (sin cambio) |
| `external_dependencies` | — | `openpyxl`, `reportlab`, `requests` (sin cambio) | `openpyxl` (sin cambio) |
| `data` | + `security/progress_job_rules.xml` (`:59`) | + `data/ai_provider_role_data.xml` (`:42`), `wizard/ai_provider_role_tools_wizard_views.xml`, `wizard/import_provider_roles_wizard_views.xml`, `views/ai_provider_role_views.xml` | sin cambio |
| `assets` | — | **se quita** la clave (`3.1.879: __manifest__.py:35-73`); en Odoo 14 se ignoraba. Los JS se cargan con `views/assets.xml`, que añade tres `<script>` | — |
| `qweb` | + `static/src/xml/pns_progress_dialog.xml` (`:67-69`) | — | `static/src/xml/chatboo_systray.xml` (sin cambio) |
| hooks | — | `post_init_hook`, `uninstall_hook` (sin cambio; `hooks.py` idéntico) | `uninstall_hook` (sin cambio) |

- La copia de trabajo conserva los números de 3.1.879 (`pns_base/__manifest__.py:8` `1.2.47`,
  `pns_ai_mcp/__manifest__.py:8` `3.1.879`, `pns_ai_chatboo/__manifest__.py:7` `2.1.538`, (copia)): los
  parches no tocan `version`.
- Los tres `version` nuevos ya llevan la serie: Odoo 14 no la antepone (`odoo/modules/module.py:441-445`). Los
  tres quedan por encima de los instalados (14.0.1.2.47, 14.0.3.1.879, 14.0.2.1.538): Aplicaciones los ofrece
  como actualización.
- **Numeración de `pns_base`:** el CHANGELOG etiqueta las publicaciones como
  `owl1-1.2.69_owl2-1.2.83_…`; `owl1` es la pila de Odoo 14 y 15. La 1.2.69 es, según esa etiqueta, la de
  Odoo 14: la duda de la comparación anterior (1.2.47 con número de Odoo 19, comp §9.1) no se repite con esta
  numeración.

### 2.5 `LICENSE`, `NOTICE` y documentos nuevos

- **`LICENSE` no es nuevo:** existe en los tres módulos de 3.1.879 y de 3.1.973 y es **idéntico** (el
  `diff -rq` no lo lista). Es la Apache License 2.0 (`pns_ai_mcp/LICENSE:1-3`).
- **Con el manifiesto:** `license` sigue siendo `Other OSI approved licence`, la etiqueta que Odoo 14 admite
  para licencias OSI fuera de su lista; el comentario de los tres manifiestos remite a `LICENSE` (Apache 2.0).
  No hay contradicción entre los dos. Con la base Apache-2.0 que mantiene Seges (CLAUDE.md del repo): misma
  licencia; sin choque.
- **`NOTICE` (raíz y `static/description/`) cambia en los tres:** se quita la dirección postal y, en
  `pns_base`, se añade un apartado «Third-party» (hoja de estilos de Font Awesome 4.7.0, MIT, solo en la
  pila de Odoo 20). Incorporar 3.1.973 trae estos `NOTICE`; la regla del repo («no se tocan `LICENSE` ni
  `NOTICE`») se refiere a cambios de Seges.
- **Documentos nuevos** en los tres módulos: `CHANGELOG.md`, `README.md`, `SECURITY.md` (avisos de
  seguridad por canal privado: «Security → Report a vulnerability» en GitHub o la web del fabricante; sin
  pruebas de concepto en público) y `CONTRIBUTING.md` (el repositorio se genera desde el árbol interno en cada
  publicación; las *pull requests* están desactivadas; se puede bifurcar el código, Apache-2.0).

### 2.6 `migrations/`

| Módulo | 3.1.879 | 3.1.973 | Copia de trabajo |
|---|---|---|---|
| `pns_base` | sin carpeta | sin carpeta | sin carpeta |
| `pns_ai_mcp` | 80 scripts en 78 carpetas, de `3.1.47` a `3.1.643` | **sin carpeta** | igual que 3.1.879 |
| `pns_ai_chatboo` | 33 scripts, de `2.1.33` a `2.1.343` | **sin carpeta** | igual que 3.1.879 |

- **¿Ejecutaría Odoo 14 alguno en un `-u` desde 3.1.879?** No, ni con 3.1.879 ni con 3.1.973.
  `convert_version` toma una carpeta con dos o más puntos como versión completa
  (`odoo/modules/migration.py:108-111`) y solo corre las de la franja (instalada, nueva] (`:144-146, 161`):
  (14.0.3.1.879, 14.0.3.1.973] y (14.0.2.1.538, 14.0.2.1.587]. `3.1.643` y `2.1.343` quedan por debajo.
  Quitar la carpeta no cambia nada en el `-u` desde 3.1.879 (ni en LIYBEN ni en `pns_demo`).
- **Ninguna carpeta `3.x` ni `2.x` del fabricante puede ejecutarse en Odoo 14:** con dos puntos se toma como
  versión completa y queda siempre por debajo de la instalada (`14.0.…`). El fabricante lo reconoce para
  las `3.1.*` (`utils/schema_fossils.py:6-10, 50, 70-71`); para las `2.1.*` de Chatboo vale el mismo cálculo.
- Lo que el `-u` cambia en datos va en `init()` y `_register_hook`. Los que ya existían siguen iguales; lo
  nuevo es `stash_fit_columns` (`utils/schema_fossils.py:290-313`, llamado desde
  `models/ai_schema_fossil.py:39`), el `_register_hook` de `ai.provider.role`
  (`models/ai_provider_role.py:261-270`) y el de `sandbox_secret_read` (`models/sandbox_secret_read.py:58-63,
  133-136`; solo cambia la precarga, no toca datos). Análisis completo en la segunda pasada (§7). Adelanto
  de un efecto del `-u` con datos `noupdate`: NUEVO-2 (§3.4).

### 2.7 CHANGELOG entre 3.1.879 y 3.1.973 (resumen propio)

Los tres CHANGELOG empiezan en la «primera publicación» (`pns_ai_mcp` 3.1.905, `pns_ai_chatboo` 2.1.542,
`pns_base` 1.2.53, 02-03/11/2026). **Las versiones intermedias desde las de 3.1.879 (3.1.880-3.1.904,
2.1.539-2.1.541 y 1.2.48-1.2.52) no tienen entrada.** Lo que dicen, agrupado:

- **Seguridad (según el fabricante):** acciones del sistema no invocables por RPC; los planes supervisados
  se ejecutan como quien los pidió y en sus compañías; registros por usuario privados; secretos de servidores
  externos solo para el AI Administrator y fuera de las exportaciones; `fetch_url` bloquea redes internas
  aunque cambie el DNS; el sandbox no envía correo ni ejecuta acciones; `/mcp` no da detalles sin autenticar y
  rechaza sesiones de otros usuarios (3.1.905). El sandbox no llega a la conexión ni al cursor por ninguna vía
  y solo expone una lista corta de atributos del `env`; el código de las skills corre en la caja A, con
  cursor de solo lectura propio y columnas secretas cerradas (3.1.924). Un AI Administrator sin Ajustes no
  puede poner la clave de un administrador de Ajustes (3.1.972). En `pns_base`, la pregunta «¿incluir
  secretos?» solo ejecuta la exportación que la abrió (1.2.68) y el asistente de exportación solo borra el
  fichero de quien lo hizo (1.2.53).
- **Funciones nuevas:** facturas de proveedor desde un documento adjunto (con impuestos combinados,
  retenciones, otra moneda, tiques y comprobantes de tarjeta), `/bill-draft` y `/sales-board`; roles de
  proveedor con alternativa (Conversación, Visión, Diseño, Parser, Decisión…); multicompañía según el selector
  de compañías; marca «generado por IA» (AI Act, art. 50) en Excel, PDF, HTML y Word; ejemplos de proveedores;
  pegar imágenes con Ctrl+V; la tarjeta de confirmación reintenta sola una vez si el servidor la rechaza por
  token antiguo o «demasiado pronto» (2.1.585).
- **Cambios de comportamiento:** AI Administrator implica ahora AI Conversational (3.1.972;
  `security/security_groups.xml:50`); la caché de `api_call` confirma la fila en cuanto se escribe (3.1.932);
  copias de configuración sin versión de esquema (3.1.917).
- **Producto y tienda:** nombres, categorías, `website`, banners, README en inglés y español, siete series
  (14.0 a 20.0, con una pila Owl 3 para Odoo 20).
- **Tests:** sin datos de demo, sin red en Odoo 14 y sin `commit` en cursor aparte durante un test (3.1.913).

## 3. Hallazgos Críticos y Altos

### 3.1 Filas con estado CS, AC, AI, PSD o SE

«Copia» = cómo lo deja la copia de trabajo (estado del inventario). «Seges frente a fabricante» solo cuando
la corrección difiere.

| Id | Grav. | Estado (inventario) | Veredicto en 3.1.973 | 3.1.973 (archivo:línea) | Seges frente a fabricante |
|---|---|---|---|---|---|
| PNS-01 | Crítica | CS (p12); CF (cúspide) | **PARCIAL** | Cúspide igual (`models/ai_system_action.py:710-718`; `utils/privilege_cusp.py` idéntico). **Nuevo:** el plan corre como quien lo pidió (`models/safe_operation.py:1435-1440`) y el alta de grupo se escribe sin `su` con ese usuario (`ai_system_action.py:738-742`, `user.with_user(self.env.uid)`); en Odoo 14 escribir `groups_id` exige `base.group_erp_manager` (`odoo/addons/base/security/ir.model.access.csv:71`). Por CRUD, `res.groups` igual (`:54`; `safe_plan_execute.py:157-184`) | **Otro criterio, más estrecho:** el fabricante exige al solicitante el permiso de Odoo («Permisos de acceso»); Seges exige Ajustes a quien ejecuta, a quien propone y a quien confirma (`privilege_cusp.py:105-164` (copia)). Medido en P-5 (§9): sin «Permisos de acceso» el plan falla con el error de escritura en `res.users` y no da el grupo; con él, lo da; corre con el uid del solicitante, sin `su` |
| PNS-02 | Crítica | CS (p12); CF (cúspide) | **PARCIAL** | Quitar grupo: mismo cambio (`ai_system_action.py:768-772`) | Igual que PNS-01. El test del fabricante `test_paap_i7_…` (`tests/test_system_action.py:543-547`) sigue esperando que un AI Administrator sin Ajustes proponga un grupo normal: con el parche 12 sigue fallando por diseño |
| PNS-07 | Crítica | CS (p15); CF (privados); AI | **PARCIAL** | `fulfill_client_export` pasa a `_fulfill_client_export` (`pns_ai_chatboo/models/chatboo_session.py:546`); `page_url`, `page_html`, `page_edit`, `paint_canvas` (`:888-1066`), los seis `log_*` y `chat_completion` (`models/ai_execution_engine.py:425-872`), `author_param_*` y `rewrite_code_for_params` (`models/ai_skill_authoring.py:215-341`) y `collect` (`models/key_pin_desk.py:195`), privados; `test_connection`, `get_content` y `get_for_agent`, en la lista (`controllers/validators_base.py:254-256`). **Siguen públicos y fuera de la lista** 9 de los 28 del parche 15: `mark_seen` (`chatboo_async_request.py:1535`), `sandbox_helpers` (`chatboo_session.py:831`), `action_suggest_detection` (`models/external_server.py:880`), `action_author_params`, `action_author_help`, `action_adapt_code` (`wizard/skill_capture_wizard.py:636-688`), `action_generate_openapi`, `action_generate`, `action_log_generation_usage` (`wizard/openapi_spec_generate_wizard.py:178-302`) | **Más estrecha** (19 de 28 cerrados). Parte de los 9 los frena la puerta de catálogos (modelos cerrados enteros, `validators_base.py:189-206`): detalle en la segunda pasada |
| PNS-54 | Crítica | CS (p16); AC (D29); AI | **SIN CAMBIO** | `action_confirm_and_execute` sin `check_identity` (`models/safe_operation.py:1796-1835`); `card_payload` genera token a quien puede leer la operación (`:2034-2063`). Nuevo `held` en `pending_card_payloads` (`:2065-2087`): no rota el token de las tarjetas que la pantalla ya pinta. En el cliente, la tarjeta reintenta sola una vez tras un rechazo `too_soon` / `bad_token` / `missing_token` (`chatboo_component_v2.js`, `_retryRefusedCard`); la espera de 5 s sigue en servidor | — |
| M10 | Crítica | CS (p13 con p12); AI | **CORREGIDO** | `create` solo en `su` (`models/safe_operation.py:545-551`, mismo texto que el parche 13); `_cleanup_stuck_state` privado (`:1030-1031`); el plan corre como el `user_id` de la operación (`:1435-1440`) | Mismo criterio que el parche 13. La parte del parche 12 (el AI Administrator se da Ajustes) queda como en PNS-01 |
| PNS-101 | Crítica | CS (p23 ampliado); AI; SE (recuento) | **CORREGIDO** (P-6, §9) | `GuardedSandboxEnv` con lista blanca (`user`, `company`, `companies`, `context`, `lang`, `uid`, `ref`, `with_context`, `with_company`; `controllers/context_builder.py:71-157`); cursores, conexiones, `Environment`, `Environments`, `Cache` y `Registry` rechazados por clase, se llegue por donde se llegue (`:159-199, 247-261`); toda lectura de atributo reescrita en el AST a `__pns_sandbox_attr__` (`:350-381`); `str.format` / `format_map` con formateador propio (`:290-347`). Relaxaicode y skills compilan igual (`tools_relaxaicode.py:190`; `utils/skill_runtime.py:258`) | **Otro criterio, más amplio:** lista blanca y bloqueo por clase del objeto, frente a la lista de nombres de estado del ORM y el formateador de Seges. Tests de Seges del parche 23 pasados contra 3.1.973 (P-6, §9): los negativos se rechazan, sin el secreto ni nombres internos (fallan solo por el texto del error); fallan `test_allowed_attrs` y `test_engine_attrs_on_wrapper` (criterio del fabricante más restrictivo) y `test_type_itemgetter_class` (`itemgetter` nativo); restos sin vía de ataque conocida |
| PNS-102 | Crítica | CS (p24); AI; SE (recuento) | **SIN CAMBIO** | `env.user`, `env.company` y `env.companies` del sandbox salen del ORM (`context_builder.py:95-97, 138-139`) y los globales `user` / `company` son `env.user` / `env.company` (`:659-660, 765-766`): en Odoo 14 `env.user` es `su` (`odoo/api.py:544-548`). **Alcance:** en la caja A de 3.1.973 solo `user`, y lo que cuelga de él, sigue como superusuario; `company` y `companies` no, porque la caja A fija `allowed_company_ids` (`utils/one_company.py:66-79`; `controllers/controller_helpers.py:188, 211-217`) y entonces Odoo los saca del entorno sin `su` (`odoo/api.py:571-577, 601-607`). Excepción: si el usuario no tiene ninguna compañía activa (y el contexto de origen no trae `allowed_company_ids`), `company` vuelve a ser `user.company_id` (y `companies`, `user.company_ids`), como superusuario (`odoo/api.py:578, 618`). **Agravante en 3.1.973:** la protección nueva de columnas secretas no actúa en lecturas `su` (`models/sandbox_secret_read.py:65-66`), así que por el `user` en `su` y sus relaciones no se aplica | — |
| PNS-17 | Alta | CS (p19); CF (parcial) | **SIN CAMBIO** (el resto principal) | Al cambiar de host solo se quitan las cabeceras de `_AUTH_HEADER_NAMES` (`utils/fetch_url_safe.py:122-134`); el cliente MCP sigue las redirecciones de `requests` (`utils/mcp_client.py:103-108`). **Mejora:** comprobación del par que contesta, contra el DNS *rebinding* (`fetch_url_safe.py:47-68, 176-179`; también `utils/remote_image.py:44-46`) | — |
| PNS-18 | Alta | AC (D10); PSD | **SIN CAMBIO** | «Sin failover externo» se aplica después de roles y topes, y con la red de «todos los proveedores activos» si la cadena no cubre el rol (`models/ai_execution_engine.py:256-287`). **Nuevo:** si nadie tiene el rol, se pide su alternativa (Parser → Conversación), que amplía los candidatos fuera de la cadena (`:271-286`) | — |
| PNS-19 | Alta | CS (p18); CF (parcial) | **PARCIAL** | **Criterio nuevo:** en el cursor de la caja A, cualquier columna «secreta» (por nombre, `_pns_secret_fields`, ajuste guardado en un parámetro secreto o `related` que acaba en una) da `AccessError` al leerla, buscar, ordenar o agrupar (`models/sandbox_secret_read.py:55-127`; `utils/sandbox_secrets.py:21-79`); `ir.config_parameter.value` por clave (`sandbox_secret_read.py:130-167`). `ai.provider` e `ir.config_parameter` salen de la lista de modelos cerrados (`validators_base.py:189-206`). **Restos:** no cubre lecturas `su` (`:65-66`; ver PNS-102) ni valores que ya estén en la caché del hilo (NUEVO-1) | **Otro criterio:** el fabricante cierra columnas por nombre en todos los modelos (más amplio en modelos, más estrecho en campos); Seges deja leer solo los campos de identificación de 11 modelos, también en `sudo`, y vacía la caché al abrir la caja A (`models/box_a_guard.py` (copia)). Las skills corren ahora en la caja A (`utils/skill_runtime.py:248-264`) sin la marca de Seges (§4, parche 18) |
| PNS-20 | Alta | CS (p21); CF (resto) | **SIN CAMBIO** | `pns_base/models/operation_report_wizard.py`: solo cambia un comentario (`:47`); `action_preview` igual | — |
| PNS-23 | Alta | SE | **SIN CAMBIO** (la causa) | Skills capturadas desde el chat, activas (`wizard/skill_capture_wizard.py:840`); importadas por ZIP, activas por defecto (`models/ai_skill_zip.py:239`); `skill_skip_body_check` sigue (`models/ai_skill.py:450`). Skills nuevas sin `required_groups`: `bill_draft`, `sales_board`, `top_sales`; `users` lo lleva (`pns_ai_chatboo/ai/skills/system/users.md:7`). **Acota el efecto:** el código de las skills corre en la caja A (`skill_runtime.py:248-264`) | — |
| PNS-26 | Alta | PSD (al informe) | **SIN CAMBIO** | `commit()` sobre el cursor del llamador en `execute_plan_now` (`models/safe_operation.py:943, 952, 1455`); recuento de `.commit()` en `models`, `controllers`, `utils` y `lib`: 30 → 31 (el nuevo, `utils/engine_tool_run.py:556`, en cursor propio y con comprobación de dueño) | — |
| PNS-70 | Alta | CS (p20); AI | **SIN CAMBIO** | `chart.umd.min.js` y `chatboo_heavy_libs.js` idénticos a 3.1.879; `window.Chart` en `pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js:29` | — |
| PNS-81 (resto) | Alta | CF (p1-p4); SE (resto) | **CORREGIDO** | `_static_str` usa `ast.literal_eval` y trata `Index` de 3.7 (`pns_ai_chatboo/utils/skill_capture_compose.py:319-327`). Grep de construcciones 3.8+ en los `.py` nuevos: sin coincidencias fuera de `try` o de comentarios | — |
| PNS-82 | Alta | CS (p11); CF (reclamación) | **SIN CAMBIO** (`unlink`) | `unlink` borra en `sudo` todos los adjuntos de la sesión (`pns_ai_chatboo/models/chatboo_session.py:1976-2033`, búsqueda en `:2023-2028`). Reclamación, igual (`:501`). Nuevo `write`: la sesión no cambia de dueño fuera de `su` (`:1968-1974`) | — |
| PNS-83 | Alta | CS (p10); AI | **CORREGIDO** | `_collect_pin` privado (`models/key_pin_desk.py:184-192`); su llamador, después del bloqueo por IP y de `any_open` (`models/mcp_user.py:802-806`). Además pasan a privados `_touch`, `_close` y `_supply` (`key_pin_desk.py:91, 127, 245`); `any_open` y `notify_changed` siguen públicos (`:42, 138`) | Mismo criterio que el parche 10, **más amplio** (cubre `close`, que el inventario dejaba en «A confirmar») |
| PNS-100 | Alta | CS (p22); AI | **PARCIAL** | La lista añade `send_email`, `build_email`, `send`, `send_mail`, `process_email_queue`, `run` y `method_direct_trigger` (`controllers/validators_base.py:257-265`). Faltan 21 de los 28 del parche 22 (`connect`, `test_smtp_connection`, `load_remote_url`, `fetch_mail`, `get_credits`, `read_by_vat`, `install_from_urls`, `get_usd_fx`, `execute_callback`, `upgrade_module`, `message_process`, `message_route`…) | **Más estrecha** (7 de 28, más `build_email`, que Seges no tiene) |
| M13 | Alta | CS (p14); AI | **CORREGIDO** | `_unlink_retired_from_module` privado (`models/ai_context_disk.py:751`); su llamador (`:738`) | Mismo criterio que el parche 14 |

**Entorno y procedimiento** (contraseña de `admin` de `pns_demo`, escritura sin causa en la operación 27):
**NO APLICA**; no son de código ni tienen gravedad Crítica o Alta en el inventario.

### 3.2 CF782 (corregidas en 3.1.782 y no revisadas en 3.1.879): las 5 Críticas y las 15 Altas

Dos veredictos: en la copia de trabajo (que en estos puntos es 3.1.879 sin parches) y en 3.1.973.
Comprobado con Grep y lectura del punto de control que cita el
[informe del 08/10](../pendiente/informe_fabricante_pns_ai.md) o el
[seguimiento](../pendiente/seguimiento_informe_pns_ai.md); no es una relectura completa de cada flujo.

| Id | Grav. | Punto de control | Copia de trabajo | 3.1.973 |
|---|---|---|---|---|
| PNS-03 | Crítica | `write` de `ai.safe.operation` solo en `su` | **CORREGIDO** (`pns_ai_mcp/models/safe_operation.py:546-549` (copia)) | **CORREGIDO** (`models/safe_operation.py:553-558`) |
| PNS-04 | Crítica | `confirm_by_user` y `resolve_*` privados | **CORREGIDO** (`safe_operation.py:595, 656, 791, 913` (copia)) | **CORREGIDO** (`:602, 667, 802, 924`); `cancel_by_user` público con `_can_resolve` (`:1207-1213`) |
| PNS-05 | Crítica | `safe_plan_status` solo ve las del usuario y no ejecuta en `sudo` | **CORREGIDO** (`controllers/safe_plan.py:2436-2445` (copia)) | **CORREGIDO** (`controllers/safe_plan.py:551-588`) |
| PNS-06 | Crítica | El `code_body` no escribe al guardar | **CORREGIDO**: AST que rechaza escrituras al guardar y al ejecutar (`utils/skill_runtime.py:2922-2941` (copia)) y ejecución de prueba en un *savepoint* que se deshace (`models/ai_skill.py:417-491` (copia)); la prueba corre sobre el cursor del llamador | **CORREGIDO, más amplio**: misma comprobación (`models/ai_skill.py:402-456`) y el código corre en una caja A propia, de solo lectura (`utils/skill_runtime.py:248-264`) |
| PNS-53 | Crítica | Regla de dueño en `chatboo.session` y saneado | **CORREGIDO** (`pns_ai_chatboo/security/security.xml:9-18` (copia)) | **CORREGIDO** (`pns_ai_chatboo/security/security.xml:9-18`; saneador sin cambios, `chatboo_formatters.js`; Grep de `innerHTML`/`t-raw` añadidos en el diff: ninguno) |
| PNS-08 | Alta | `auth_token`, `env_vars`, `config_json` con `groups` | **CORREGIDO** | **CORREGIDO, más amplio**: también `command_args` (`models/external_server.py:223-226`; `_pns_secret_fields`, `:84`) |
| PNS-09 | Alta | `stdio`: entorno mínimo, *timeout*, botones con grupo | **CORREGIDO** | **CORREGIDO, más amplio**: `utils/mcp_client.py:157, 190-203`; `ensure_ai_admin` en `action_test_connection` y `action_discover_tools` (`external_server.py:1127, 1240`) y ahora también en `action_suggest_detection` (`:882`) |
| PNS-10 | Alta | `skip_hardcoded_restrictions` solo cuenta en `sudo` | **CORREGIDO** (`utils/knowledge_ownership.py:48` (copia)) | **CORREGIDO** (archivo idéntico, `:41-49`) |
| PNS-11 | Alta | Métodos de `ai.skill`/`ai.context` con `_require_bootstrap` o privados | **CORREGIDO** (`models/ai_skill.py:581, 1403, 1510, 2228, 2274` (copia)) | **CORREGIDO** (`models/ai_skill_disk.py:385, 431`; `ai_skill_slash.py:291, 372`; `_record_context_usage`, `ai_context.py:532`); `sync_slash_hidden_from_field` ya no existe |
| PNS-12 | Alta | Lecturas de contextos con el dominio de propiedad | **CORREGIDO** | **CORREGIDO** (`models/ai_context_composition.py:114, 153, 182`, `ownership_read_domain()`) |
| PNS-13 | Alta | `/mcp/message` revalida clave y usuario | **CORREGIDO** (`controllers/main.py:692` (copia)) | **CORREGIDO** (`controllers/main.py:695-709`; `utils/session_store.py:127, 203`) |
| PNS-14 | Alta | `ai.api.result.cache` con `uid` en la clave y regla; `ai.safe.choice` con regla | **CORREGIDO** | **CORREGIDO, más amplio**: `ai.safe.choice` pasa a solo lectura para internos (`security/ir.model.access.csv:81`); clave con `uid` (`models/api_result_cache.py:91`); reglas (`security/security.xml:195-220`) |
| PNS-15 | Alta | Escape y filtro de esquema en el render | **CORREGIDO** | **CORREGIDO** (código repartido: `utils/relaxaicode_render_base.py:257`; 78 escapes en los 8 archivos frente a 71 en el original). Lectura completa: segunda pasada |
| PNS-21 | Alta | Descargas con `auth='user'` y dueño | **CORREGIDO** (`controllers/session_file.py:22, 40` (copia)) | **CORREGIDO** (`controllers/session_file.py:23, 44`) |
| PNS-25 | Alta | Sin failover tras efectos (`_turn_effects_done`) | **CORREGIDO** (`utils/agent_engine.py:1094`; `engine_tool_run.py:605` (copia)) | **CORREGIDO** (`utils/agent_engine.py:1123`; `engine_tool_run.py:613`) |
| PNS-27 | Alta | jsPDF/SheetJS | **CORREGIDO** (según seg) | **CORREGIDO** (`jspdf.umd.min.js` idéntico; sin SheetJS en `pns_ai_mcp`) |
| PNS-56 | Alta | Estado de la sesión ajena no escribible | **CORREGIDO** (regla de dueño) | **CORREGIDO** (regla igual; además la sesión no cambia de dueño, `chatboo_session.py:1968-1974`; datos reutilizados solo si son de las mismas compañías, `:120, 786-800`) |
| PNS-57 | Alta | `spawn` privado; jobs sin alta por RPC | **CORREGIDO** (`models/chatboo_job.py:176` (copia)) | **CORREGIDO** (`models/chatboo_job.py:175`; `security/ir.model.access.csv:3`, `1,0,0,0`) |
| PNS-58 | Alta | `/chatboo/stream` con CSRF y sin `cors='*'` | **CORREGIDO** (`controllers/chatboo.py:778` (copia)) | **CORREGIDO** (`controllers/chatboo.py:799`) |
| PNS-80 | Alta | `read_progress` | **NO APLICA** (no existe) | **NO APLICA** (no existe; el progreso va por `async_poll`, con acceso a Chatboo, `controllers/chatboo.py:537-544`) |

### 3.3 Filas CF Críticas o Altas cuyo código toca 3.1.973 (¿siguen corregidas?)

Las que además son CS (PNS-01, 02, 07, 17, 19, 20, 82) están en §3.1.

| Id | Grav. | Qué toca 3.1.973 | ¿Sigue corregido? |
|---|---|---|---|
| PNS-14 / PNS-90 | Alta | `models/fetch_cache.py` (+11 −4) | Sí: `_get_cached`, `_store` privados (`:71, 99`); `gc_expired` pasa además a `_gc_expired` (`:135`; ver NUEVO-2) |
| PNS-16 | Alta | `utils/engine_turn_messages.py` (+55 −50), `models/url_whitelist.py` (+10 −4) | Sí: `[REUSABLE DATA]` / `[REUSABLE QUERY]` con rol `user` y turno no fiable (`engine_turn_messages.py:280-334`); `url_whitelist.py`, solo la restricción SQL |
| PNS-24 | Alta | `models/ai_system_action.py` (+14 −3) | Sí: `module.update` sin cambios; nuevo `_require_settings` (Ajustes) en las acciones de vistas y campos (`:120-125, 218, 388, 505`) |
| PNS-55 | Alta | `security/security.xml` (Chatboo), `chatboo_session.py` | Sí: reglas de sesión y job iguales; la de `chatboo.canvas.job` deja de dar escritura (`security.xml:32-41`), sin efecto práctico: su ACL ya era de solo lectura (`security/ir.model.access.csv:5`, igual en 3.1.879); `recover_orphan_download_chips` con dueño (`chatboo_session.py:603`) |
| PNS-59 | Alta | `utils/remote_image.py` (+4 −1) | Sí, y mejora: comprobación del par contra el *rebinding* (`:44-46`) |
| PNS-60 | Alta | `chatboo_formatters.js` (+12 −10), `chatboo_component_v2.js` (+392 −249) | Sí: el saneador no cambia (solo textos traducidos con `escapeHtml`); en el diff no se añade ningún `innerHTML`, `t-raw` ni `.html(` |
| PNS-81 (p1-p4) | Alta | Archivos nuevos `.py` | Sí: Grep de walrus, `removeprefix`, `functools.cache`, `zip(strict=)`, `match`/`case`, genéricos en anotaciones: solo comentarios, código con `try` (`ast.unparse`) o con `getattr` (`get_source_segment`, `utils/relaxaicode_recipe.py:515`). **Dato:** en Python 3.7 no hay `ast.unparse`, así que las reparaciones que lo usan nunca se aplican (devuelven el código sin cambios, p. ej. `controllers/validators_repair.py:105-109`; `utils/relaxaicode_recipe.py:190-194`); y `ast.Constant` no se usa en comprobaciones (no hay `isinstance(…, ast.Constant)` y la lista de literales admite `Str`, `controllers/validators_base.py:296-298`): solo construye nodos. Seis de esos usos están en reparaciones que terminan en `ast.unparse` y en 3.7 no se aplican (`validators_repair.py:218, 276, 286`; `validators_sort.py:276, 356, 371`). El séptimo es la reescritura de atributos del sandbox (`context_builder.py:362`), que pasa por `compile` (`:380`). Python 3.7 admite esos nodos al compilar, pero no se ha comprobado en ejecución. P-18 |
| PNS-94 | Alta | `chatboo_async_request.py` (+312 −245), `chatboo_job.py` (+64 −65) | Sí por código: `rollback` antes de `_finalize` (`chatboo_async_request.py:542, 590`); latido en hilo aparte (`chatboo_job.py:24-35, 275-313`) |

**Regresiones detectadas: ninguna.**

### 3.4 Hallazgos NUEVOS

| Id | Grav. (propuesta) | Afecta a | Qué pasa | Dónde | Estado |
|---|---|---|---|---|---|
| **NUEVO-1** | Alta (como PNS-19) | 3.1.973 sin el parche 18 | La protección de columnas secretas se aplica al leer de la base de datos, no a lo que ya está en la caché. En Odoo 14 un campo en caché se devuelve sin comprobar permisos (`odoo/fields.py:993-996`), y la caché es una por hilo para todos los cursores. El motor lee la clave del proveedor en `sudo` en el mismo hilo antes de las herramientas, y la caja A no vacía la caché al abrirse. El fabricante solo quita la precarga de esas columnas, y sus tests vacían la caché antes de cada lectura. El único vaciado propio, `_forget_values`, solo afecta a `ir.config_parameter.value` tras un `get_param` en `sudo` sobre el cursor de la caja A, no al abrirla. **Lo hace más difícil:** cualquier `commit` o `rollback` del hilo vacía la caché compartida, si hay un entorno sobre ese cursor (`odoo/sql_db.py:65-86`, llamados en `:449-462`; `odoo/api.py:628-635`), así que la clave solo sigue en caché si no hay ninguno entre la lectura del motor y la caja A; P-1 debe reproducir ese caso. Core que lo sostiene: la caché es la de `Environments`, compartida por todos los entornos y cursores del hilo (`odoo/api.py:449-477, 765-769`), y un campo en caché se devuelve sin comprobar permisos (`odoo/fields.py:993-996`) | `models/sandbox_secret_read.py:15-16, 50-52, 58-63, 161-163`; `controllers/controller_helpers.py:179-238`; `tests/test_sandbox_secret_read.py:39-44` | **Mecanismo confirmado en ejecución (P-1, 10/11/2026):** con la clave en la caché del hilo, la caja A la devuelve; con la caché vacía, la guarda la deniega. En un turno real, por lectura, no se alcanza en los caminos revisados (Chatboo, `/mcp` y varias herramientas en una respuesta): un `commit` con entorno vacía la caché antes de la caja A. Detalle y lo no revisado, en el resultado de P-1 (§9). En la copia lo cubre el parche 18: la caché se vacía al abrir la caja A (`_box_a_clear_cache`, `models/box_a_guard.py:48-63`, llamado desde `controllers/tools_relaxaicode.py:190` (copia)), con `test_box_a_engine_cache_before_run` |
| **NUEVO-2** | Baja (actualización) | 3.1.973, `-u` desde 3.1.879 | Los crons de purga de `ai.fetch.cache` y `ai.api.result.cache` están en datos `noupdate="1"` y su código pasa de `model.gc_expired()` a `model._gc_expired()`; el método público desaparece. En una BD actualizada el registro del cron no se reescribe y falla en cada pasada (las cachés dejan de purgarse). El `init()` de `api_result_cache` no es nuevo (ya estaba, idéntico, en 3.1.879: `api_result_cache.py:51-53`), solo corrige `numbercall` y solo toca el cron de `api_result_cache` | `data/fetch_cache_cron.xml:2, 10`; `data/api_result_cache_cron.xml:2, 10`; `models/fetch_cache.py:135`; `models/api_result_cache.py:58-87, 146` | **REQUIERE PRUEBA** (P-2 en §9) |
| **NUEVO-3** | Alta (requiere AI Administrator) | **Copia de trabajo** (3.1.879); corregido en 3.1.973 | Un AI Administrator sin Ajustes puede generar, fijar o importar la clave MCP de un usuario que tiene Ajustes: `_ensure_key_admin` solo mira el grupo de IA. Con esa clave actúa por `/mcp` con la identidad y los permisos de ese administrador. No figura en el inventario; el fabricante lo cierra en 3.1.972 (CHANGELOG) | Copia: `pns_ai_mcp/models/mcp_user.py:737-742` (copia); importación, `wizard/import_users_wizard.py:111-133` (copia). Otros dos caminos de la copia: `create`/`write` por RPC de `mcp_api_key_hash`, sin comprobación (`models/mcp_user.py:347-364` (copia)), y la importación de configuración, que escribe el hash en `sudo` (`utils/config_backup.py:610-640` (copia)). 3.1.973: `models/mcp_user.py:740-781` (`_may_set_key_of`, `_drop_key_unless_allowed`); cierra esos dos caminos en `create` y `write` fuera de `su` (`mcp_user.py:346-354, 370-372`) y en la importación de configuración (`utils/config_backup.py:735`); test `tests/test_key_of_settings_admin.py` | Por lectura. Prueba de confirmación P-3 (§9) |

| **NUEVO-4** | Alta (cualquier usuario interno) | **Copia de trabajo** (`pns_base` 1.2.47); corregido en 1.2.69 | `pns.export.file.wizard.unlink` borra en `sudo` el adjunto que apunte `attachment_id`; el asistente es creable y editable por cualquier interno (ACL `1,1,1,1`) y un many2one se puede apuntar a cualquier id. Resultado: borrado de adjuntos ajenos (de cualquier modelo) sin permiso sobre ellos. No hace falta llamar a `unlink`: basta crear el asistente apuntando al adjunto; la limpieza automática de transitorios lo borra como superusuario (`odoo/models.py:6548`) y, con él, el adjunto, sin que el borrado quede a nombre de quien lo creó. No figura en el inventario; el CHANGELOG de `pns_base` lo da por corregido en la 1.2.53 | Copia: `pns_base/models/export_file_wizard.py:17-21` (copia); `pns_base/security/ir.model.access.csv:2` (copia). 1.2.69: `pns_base/models/export_file_wizard.py:19-27` (solo adjuntos con la marca de exportación y del propio usuario) | Por lectura. Prueba de confirmación P-4 (§9) |

Los NUEVO-5 en adelante, de la superficie nueva y del `-u`, están en §7. Endurecimiento sin hallazgo en la
copia: el asistente «¿incluir secretos?» de `pns_base` (1.2.68) ya no deja reescribir modelo, ids ni método
(`pns_base/models/export_secrets_wizard.py:11-13, 51-54`); en la copia los métodos `_pns_export_*` que
podría alcanzar exigen AI Administrator (`ensure_ai_admin`, p. ej.
`pns_ai_mcp/models/ai_provider.py:1221-1229` (copia)).

### 3.5 Filas Medias, Bajas y sin gravedad con estado CS, AC, AI, PSD o SE (segunda pasada)

70 filas: 14 Medias, 13 Bajas y 43 sin gravedad (las filas que solo tienen CF no entran, salvo las que toca
3.1.973 y se citan al final). Los anexos de PNS-54 (`missing_token`/`bad_token`, Baja) y de PNS-26
(serialización en `/execute`, Baja) van con su fila.

**Medias (14)**

| Id | Estado (inventario) | Veredicto en 3.1.973 | 3.1.973 (archivo:línea) y diferencia con Seges |
|---|---|---|---|
| PNS-28 (salvedad) | CF; SE | **SIN CAMBIO** | El `OPTIONS` lo contesta el core de Odoo 14; no depende del módulo |
| PNS-29 | CS (p33); CF; AC; AI | **SIN CAMBIO** | `month_usage` público (`models/ai_provider.py:1096`), usado por `spend_cap_reached` (`:1132`); el asistente da las cifras sin comprobar la ACL (`wizard/ai_provider_usage_wizard.py:37`). Restos 1 y 2 (aceptados): sin cambio aparente |
| PNS-30 | CF; CS (p30); AI | **CORREGIDO** | Los `log_*` pasan a privados (`models/ai_execution_engine.py:425-781`). Otro criterio que el parche 30: cierra el RPC por nombre, no comprueba el `user_id` (sus llamadores pasan `user_id or self.env.user.id`, `:445, 490, 606, 662, 753`) |
| PNS-33 (parte §7) | CF; SE | **SIN CAMBIO** | `set_mcp_api_key` sigue aceptando una clave elegida o un hash ya calculado (`models/mcp_user.py:456-470`). Nuevo: no deja fijar la clave de un administrador de Ajustes a quien no lo es (`:740-766`; NUEVO-3) |
| PNS-36 | CS (p23 ampliado) | **CORREGIDO** (P-6, §9) | Formateador propio de `str.format` y bloqueo de cursores por clase (`controllers/context_builder.py:159-199, 290-347`); el nombre de la BD no se publica (`:671-672`). Otro criterio que el parche 23; el test de Seges con `{0.cr.dbname}` (`test_pns36_cr_dbname`) pasa contra 3.1.973 (P-6, §9) |
| PNS-37 | CS (p17); CF | **SIN CAMBIO** | `ai_change_journal.py` idéntico (sin `create`/`write` propios); el paso `unlink` archiva con permiso de escritura (`controllers/safe_plan_execute.py:221-226`). Ahora con los permisos del solicitante, no de quien confirma |
| PNS-61 | PSD | **SIN CAMBIO** | Solo cambian comentarios en `get_model_history` y en `/chatboo/sessions/save` (`controllers/chatboo.py:431`) |
| PNS-84 | CS (p10, parte); AC; AI | **PARCIAL** (mejora) | `_touch`, `_close` y `_supply`, privados (`models/key_pin_desk.py:91, 127, 245`). Siguen el PIN y la clave en `ai.key.pin.ask`, que el AI Administrator lee (`security/ir.model.access.csv:85`), y `_touch` sigue dando los PIN pendientes a la mesa (`key_pin_desk.py:111-124`) |
| PNS-97 | CS (p32); AI | **PARCIAL** | `ai.trusted.action` sigue sin `create`/`write`/`unlink` propios y con ACL `1,1,1,1` del AI Administrator (`csv:78`). Lo que cambia: las acciones de vistas y campos exigen Ajustes al usuario real (`_require_settings`, `models/ai_system_action.py:120-125, 218, 388, 505`), y el plan corre como quien lo pidió (`safe_operation.py:1435-1440`), así que el caso del administrador de Ajustes que confirma el plan de otro ya no da sus permisos |
| PNS-99 | SE | **SIN CAMBIO** (REQUIERE PRUEBA) | `user_remove_group` solo quita grupos directos (`pns_base/utils/compat.py:142-145`) y `_apply_user_remove_group` devuelve `ok` igual (`ai_system_action.py:768-786`) |
| M1 | CS (p25) | **CORREGIDO** (más estrecho) | `_paint_canvas` privado (`pns_ai_chatboo/models/chatboo_session.py:1066`): cierra el RPC. No comprueba el dueño dentro; sus llamadores pasan por `_session_of_this_turn` (`chatboo_canvas.py:619`, `924`, `948`) |
| M2 | CS (p26) | **SIN CAMBIO** | `pictures_as_tokens(session.env, …)` y `(sessions.env, …)`, los dos en `sudo` (`chatboo_session.py:937`; `chatboo_canvas.py:910`) |
| M11 | CS (p30); AI | **CORREGIDO** | Igual que PNS-30. Queda cerrado también lo que Seges aceptó (filas a su propio nombre por RPC) |
| F1 | CS (p27, p29); AC | **PARCIAL** | CSP nueva del fabricante en la carcasa (§3.7). Siguen sin escapar los datos dentro de `<script>` (`chatboo_canvas.py:1097, 1426, 1439, 2046-2047`) y la muestra para Design (`:829-858`); la página guardada no se comprueba (`:2062-2105`); las descargas, sin CSP |

**Bajas (13)**

| Id | Estado | Veredicto en 3.1.973 | 3.1.973 (archivo:línea) y diferencia con Seges |
|---|---|---|---|
| PNS-96 (aviso) | CF (enlaces); CS (p34); PSD | **SIN CAMBIO** | `log_no_page` sigue devolviendo `''` sin aviso al turno (`chatboo_canvas.py:587-616`); el aviso solo existe en el botón Canvas (`chatboo_canvas_job.py:133, 156`) |
| M12 | CS (p31); AI | **CORREGIDO** | `_chat_completion` privado (`ai_execution_engine.py:872`) |
| D1 | CS (p28) | **PARCIAL** | `create` solo en `su` y `design`/`owner_id` solo en `su` (`chatboo_canvas_page.py:71-94`): más amplio que el parche 28 en `owner_id`. Sin comprobación de lectores internos en el servidor (`:52`, solo `domain`); la regla del AI Administrator sigue con escritura y alta (`security/security.xml:67-76`) |
| M16 | CS (p22, caja A); AC; AI | **SIN CAMBIO** | `get_usd_fx` público (`models/ai_fx_source.py:87`) y fuera de la lista del sandbox del fabricante (`validators_base.py:230-266`) |
| PNS-50 | CF (parcial); AC | **PARCIAL** (mejora) | Tests nuevos en los tres módulos (§2.3); siguen sin venir los `unit_tests/` citados |
| PNS-77 | CF (parcial); AC | **PARCIAL** (mejora) | Chatboo trae `tests/` (`test_chatboo_perimeter.py`, `test_chat_agent_composition.py`) |
| Hoja 21 | AC; AI | **CORREGIDO** con el criterio del fabricante | El orden por una columna secreta da `AccessError` (`models/sandbox_secret_read.py:74-91`). Si se mantiene el parche 18, en su guardián sigue abierto |
| PNS-98 | AI | **SIN CAMBIO** | `persist_turn_file` en cursor propio con `commit` (`utils/session_download.py:365-392, 474`); solo cambia `datas` por `raw` |
| F4 | AI | **SIN CAMBIO** | `chatboo_export.js` solo añade la marca de IA y traduce avisos |
| PNS-88 | PSD | **SIN CAMBIO** | `XMLID_RENAMES` igual (`utils/schema_fossils.py:73-101`) |
| M5 | PSD | **SIN CAMBIO** | `cron_maintenance` público (`chatboo_async_request.py:1621`) |
| Hoja 17 | PSD | **SIN CAMBIO** | `request_public_http` reenvía `params` y `data` igual; solo añade la comprobación del par (`fetch_url_safe.py:176-179`) |
| PNS-51 | SE | **SIN CAMBIO** | `platform` sigue en los módulos del sandbox (`controllers/validators_base.py:95`) |

**Sin gravedad (43)**

| Id | Estado | Veredicto en 3.1.973 | Comprobación |
|---|---|---|---|
| M3 | CF; CS (p26) | **PARCIAL** | `page_url` y `page_edit` privados (`chatboo_session.py:888-959`); la lectura de imágenes en `sudo` sigue (M2) |
| Hoja 38 (`iap.account.account_token`) | AC | **CORREGIDO** con el criterio del fabricante | El nombre lleva `token`: columna secreta en la caja A (`utils/sandbox_secrets.py:21-44`) |
| Numeración de `pns_base` | AI | **CORREGIDO** (dato) | `14.0.1.2.69`, etiqueta `owl1` (§2.4) |
| U9 | AC; AI | **NO APLICA** a un `-u` desde 3.1.879 | La columna ya la borró el `-u` a 3.1.879; `LEFTOVER_COLUMNS` no la toca (`schema_fossils.py:51-52`). Desde 3.1.782 (LIYBEN) pasaría igual que con 3.1.879 |
| Hoja 29 (casilla «Design» de `lite`) | AC | **NO APLICA** tal cual | La casilla pasa a rol (§6.6) |
| Hoja 33 («[object Object]») | AC | **NO APLICA** | Es efecto del parche 26 |
| Hojas 24 y 34 (scripts de pruebas) | CS | **NO APLICA** | Scripts de Seges |
| Hojas 32 y 35 (comportamiento del modelo) | PSD | **NO APLICA** | Sin código |
| Compatibilidad sin número (§7.1 a §7.4, §8.5) | SE | **NO APLICA** | La queja de §7.2 y §8.5 (migraciones `3.1.x` que no corren en 14) desaparece con la carpeta (§2.6); §7.1 y §7.4 ya estaban cerradas |
| Escritura en la operación 27; contraseña de `admin` | SE | **NO APLICA** | Entorno o procedimiento |
| Resto (30 filas) | — | **SIN CAMBIO** | Tabla siguiente |

**Bloque «SIN CAMBIO (código no tocado o sin cambio funcional)»**, con la comprobación:

| Filas | Comprobación |
|---|---|
| Valores hostiles de portal en la página | Mismo código que F1 / P-8e a: sin escape en `<script>` (`chatboo_canvas.py:1097, 1426`) |
| U6, U16 | `utils/engine_params.py` y `utils/markup_rename.py` idénticos (no salen en el `diff -rq`) |
| U15 | Mismo mecanismo de resiembra (`data/chatboo_skill_data.xml:10-11`, `import_from_module`); las skills que cambian, en §7.3 |
| U11 (agente «Decision» huérfano) | `data/ai_agent_data.xml` cambia 4 líneas y `promote_decision_provider` solo trata proveedores (`schema_fossils.py:215-264`) |
| `unit_tests/` no entregados | Siguen sin venir |
| Hoja 22 (`customer_360._iso`) | Skill idéntica; `ensure_module_result_call` en `utils/relaxaicode_recipe.py:389` |
| Hoja 26 (casilla AI Conversational) | Causa sin localizar, sin cambio en `_inverse_ai_group_flag`; contexto nuevo en §6.2 |
| Hoja 27 (`keys` en la muestra) | `sample_figures_for_design` sigue con `keys` (`chatboo_canvas.py:838-847`) |
| Botón Canvas sin aviso; nota «incomplete response»; copiar y XLSX; exportación del staging | `chatboo_canvas_job.py:133, 156` y `chatboo_async_request.py:1319-1337` iguales; `chatboo_export.js` solo añade la marca de IA |
| Carga de la sesión sin reintento | Sin cambio localizado (REQUIERE PRUEBA, §9) |
| Hojas 16, 19 y 20 | Código del core |
| Hoja 18 (caché del agente en «Review») | `operation_report_wizard.py` igual; `get_content` sigue con su cursor propio (`models/ai_agent.py:1213`) |
| Hoja 23 («Test Connection» escribe) | `ai_provider.test_connection` (`models/ai_provider.py:1192`) |
| Hoja 25 (estado de la clave MCP) | La autenticación sigue buscando por hash y usuario activo (`controllers/main.py:697-701`) |
| Hoja 28 (nombre de la descarga) | `download_filename(session.canvas_title, …)` (`controllers/chatboo.py:1324`) |
| Hoja 31 (tres llamadas a Design) | `_paint_canvas` con las mismas llamadas (`chatboo_session.py:1103, 1124, 1128, 1162`) |
| Hojas 36 y 37 | Sin cambio localizado en el registro del failover ni en el rechazo de `dir()` |
| obs. 6 | Adjuntos de `session_download` sin la marca de exportación (`session_download.py:474`) |
| obs. 7 | `_fx_payload` sigue devolviendo `str(exc)` (`controllers/chatboo.py:1116-1121`) |
| obs. 13 | Sin cambio localizado (los tests ya no confirman en cursor aparte, CHANGELOG 3.1.913) |
| Petición de §5 (prompt en `ai.log`) | Sin cambio localizado |
| Cancelación de todas las verificaciones; `log_no_page` en `ai_log` desde la caja A | Sin cambio localizado; `log_no_page` igual (`chatboo_canvas.py:587-616`) |

**Filas solo CF tocadas por 3.1.973:** PNS-35 sigue (prefijo `'` en
`utils/artifact_export_table.py:285` y `controllers/formatters.py:73`); PNS-41: los tres `website` apuntan
fuera y `pns_base/models/ir_module_module.py` (idéntico) solo incrusta el `index.html` cuando `website`
apunta a él, así que la ficha de Aplicaciones deja de mostrarlo (REQUIERE PRUEBA, §9, P-17).

### 3.6 Recuento de §3.5

| Gravedad | CORREGIDO | PARCIAL | SIN CAMBIO | EMPEORA | NO APLICA | Total |
|---|---|---|---|---|---|---|
| Media | 4 (PNS-30, 36, M1, M11) | 3 (PNS-84, 97, F1) | 7 (PNS-28, 29, 33, 37, 61, 99, M2) | 0 | 0 | 14 |
| Baja | 2 (M12, hoja 21) | 3 (D1, PNS-50, 77) | 8 (PNS-96, M16, 98, F4, 88, M5, hoja 17, PNS-51) | 0 | 0 | 13 |
| Sin gravedad | 2 (hoja 38, numeración) | 1 (M3) | 30 | 0 | 10 | 43 |
| **Total** | **8** | **7** | **45** | **0** | **10** | **70** |

### 3.7 Tres comprobaciones pedidas

**CSP del lienzo: fabricante frente al parche 27**

| Punto | 3.1.973 | Parche 27 (copia) |
|---|---|---|
| Dónde | Cabecera HTTP de la carcasa (`/chatboo/canvas/<id>` y `/chatboo/page/<id>`, `controllers/chatboo.py:1171, 1277`); el diseño va en un `<iframe sandbox="allow-scripts allow-modals" srcdoc>` (`chatboo_canvas.py:568`), que hereda la política | `<meta>` como primer elemento del `<head>` del diseño, al servir (`_with_csp`), en la carcasa **y en las dos descargas** |
| Política | `default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' data: blob:; font-src data:; connect-src 'self'; form-action 'none'; base-uri 'none'; frame-ancestors 'self'` (`:1175-1180`) | `… img-src data: blob:; connect-src 'none'; form-action 'none'; base-uri 'none'; frame-src 'none'; object-src 'none'; worker-src 'none'` |
| Diferencias | Permite imágenes y conexiones al propio origen. Medido en P-9 (§9, Chrome): para el marco `srcdoc`, «propio» es el Odoo que sirve la carcasa; las imágenes del propio Odoo (`/web/binary/company_logo`, relativa y absoluta) cargan y **llegan sin sesión** (log de Odoo: BD «?»; la BD del log sale de la sesión de la petición antes de mirar la autenticación de la ruta, `odoo/http.py:204, 215-216`, también con `auth='none'`, `addons/web/controllers/main.py:1605-1609`, así que con la cookie de una sesión iniciada saldría `lab_pns_ai_973_14`); del fetch solo consta que sale (el GET simple llega, 200; el POST JSON se queda en el preflight, OPTIONS 400) y que CORS no deja leer la respuesta; lo externo, bloqueado. No limita `frame-src`, `object-src` ni `worker-src` (caen en `default-src 'none'`, así que quedan cerrados igual) | Cierra también el propio origen |
| Enmarcado | `frame-ancestors 'self'` en la cabecera | `X-Frame-Options: SAMEORIGIN` |
| Descargas | **Sin CSP** (`controllers/chatboo.py:1291-1300, 1319-1328`; solo `nosniff`). Medido en P-9: abiertas como `file://`, nada para lo externo: el navegador lo intenta y solo falla por DNS (`ERR_NAME_NOT_RESOLVED`) | Con la misma `<meta>` |
| Datos en `<script>` | Sin escape de `<` | Escapados (`_script_json`) |

**Vía de la sesión (D5 de la comparación con 3.1.879), sin id nuevo.** El dueño escribe cualquier HTML en
`canvas_design` de su sesión por RPC y lo comparte; la página llega al otro usuario y se ejecuta en su
navegador, dentro del marco (P-9, §9). En 3.1.973 el fabricante cierra la vía por la página (fuera de `su`, ni
`create` ni `write` de `design` u `owner_id`: `_SYSTEM_FIELDS`, `models/chatboo_canvas_page.py:71-86`) pero
no por la sesión: la
ruta de compartir crea la página en `sudo` con `session.canvas_design` (`controllers/chatboo.py:1228`). En la
rama están abiertas las dos: `chatboo.session` no tiene `write` propio y `chatboo.canvas.page` solo protege
`owner_id` (parche 28, `models/chatboo_canvas_page.py:77-93` (copia)); la ruta de compartir hace
`pages.create(values)` (`controllers/chatboo.py:1200` (copia)). Su alcance lo limita la CSP del marco, no la
descarga: en 3.1.973 las descargas no llevan CSP; con el parche 27, sí.

**¿Puede el código del sandbox ligar `__pns_sandbox_attr__`?** No. `compile_sandbox` rechaza cualquier
código que contenga ese texto, también dentro de una cadena (`controllers/context_builder.py:375-376`),
antes de compilar; la reescritura solo genera lecturas (`:353-365`). Sin `globals`, `vars`, `exec` ni
`setattr` entre los builtins (`:621-633`), el nombre no se puede formar ni ligar por otra vía. Criterio más
amplio que el del parche 23 ampliado para `_sandbox_str_attr` (allí se rechazaba ligarlo, no mencionarlo).

**Los 9 nombres de PNS-07 que siguen públicos y fuera de la lista**

La puerta de catálogos solo actúa en `env[...]` y `env.get` (`context_builder.py:102-118`;
`validators_base.py:416-428`): cierra `ai.api.server`, `ai.context`, `ai.skill`, `ai.trusted.action` y los
modelos de credenciales (`:189-206`). Un registro al que se llega por una relación no pasa por ella.

| Nombre | Modelo | ¿Lo frena la puerta? | Situación |
|---|---|---|---|
| `mark_seen` | `chatboo.async.request` | No | Alcanzable sobre los jobs propios (regla de dueño); escribe en cursor propio |
| `sandbox_helpers` | `chatboo.session` | No | Alcanzable; devuelve los mismos helpers del lienzo que el sandbox ya recibe |
| `action_suggest_detection` | `ai.api.server` | Sí en `env[...]`; **no** por relación (`ai.api.server.key.server_id`, `models/api_server_key.py:36`) | Alcanzable en turnos de un AI Administrator (`ensure_ai_admin`, `external_server.py:882`): llamada al proveedor y escritura. Medido en P-8 (§9): por relación, el AI Administrator pasa `ensure_ai_admin` y llega a la llamada al LLM; el interno se para en `ensure_ai_admin`; por `env[...]` lo para la puerta |
| `action_author_params`, `action_author_help`, `action_adapt_code` | `ai.skill.capture.wizard` (Chatboo lo hereda) | Sí (modelo de credenciales) | Frenados; transitorio, sin relación localizada que lleve a él |
| `action_generate_openapi`, `action_generate`, `action_log_generation_usage` | `ai.openapi.spec.generate.wizard` | No | Transitorio: solo filas ya creadas por la interfaz (el AST no deja crearlas). Medido en P-8 (§9): un AI Administrator llega sobre sus filas y sobre las de otro AI Administrator (Odoo 14 no limita los transitorios por `create_uid`; ACL solo de `group_ai_admin`): `action_generate_openapi` llega al LLM, `action_generate` a `requests` y `action_log_generation_usage` al intento de escritura en `ai_log`; al interno lo para la ACL del modelo |

## 4. Parches de Seges 10 a 34

«Sigue haciendo falta»: sí / no / en parte. «Código en la zona»: aplica igual / con ajustes (líneas
desplazadas, contexto cambiado o código movido) / reescribir. Esfuerzo de mantenerlo o, si ya no hace falta,
de retirarlo y adaptar sus tests.

| Parche | PNS / id | Copia (archivo:línea) | 3.1.973 (archivo:línea) | ¿Hace falta? | Código en la zona | Esfuerzo |
|---|---|---|---|---|---|---|
| 10 | PNS-83 | `models/key_pin_desk.py:193-195`; `models/mcp_user.py:766-767` | `key_pin_desk.py:184-192`; `mcp_user.py:802-806` | **No** (mismo criterio y más amplio) | — (retirar) | bajo |
| 11 | PNS-82 | `pns_ai_chatboo/models/chatboo_session.py:2014, 2055` | `chatboo_session.py:1976-2033` (sin cambio funcional; `write` nuevo encima, `:1968-1974`) | **Sí** | con ajustes | bajo |
| 12 | PNS-01/02 | `models/ai_system_action.py:16-17, 713-719, 736-782`; `utils/privilege_cusp.py:101-164` | `ai_system_action.py:728-786` (`with_user`); `privilege_cusp.py` idéntico; CRUD en `safe_plan_validate.py:245` y `safe_plan_execute.py:156-216` | **En parte** (otro criterio, §3.1) | con ajustes | bajo |
| 13 | M10 | `models/safe_operation.py:531-533, 1019-1021` | `safe_operation.py:545-551, 1030-1031` | **No** (mismo criterio) | — (retirar) | bajo |
| 14 | M13 | `models/ai_context_disk.py:745, 758` | `ai_context_disk.py:738, 751` | **No** (mismo criterio) | — (retirar) | bajo |
| 15 | PNS-07 | `controllers/validators_base.py:255-285` | `validators_base.py:230-266` | **En parte** (9 nombres, §3.1) | con ajustes (16 nombres ya son privados y 3 están en la lista) | bajo |
| 16 | PNS-54 | `models/safe_operation.py:13-14, 1780-1782, 2047` | `safe_operation.py:1796, 2034-2063` | **Sí** | con ajustes (desplazado) | bajo |
| 17 | PNS-37 | `models/ai_change_journal.py` (4); `controllers/safe_plan.py:950-952` | `ai_change_journal.py` idéntico; el paso `unlink`, en `controllers/safe_plan_execute.py:221-226` | **Sí** | `ai_change_journal.py` aplica igual; el paso `unlink`, con ajustes (código idéntico, en otro archivo) | bajo |
| 18 | PNS-19 | `models/box_a_guard.py` (nuevo); `models/__init__.py:44`; `controllers/tools_relaxaicode.py:8, 188-190, 295-296`; `pns_ai_chatboo/models/chatboo_session.py:18, 1229` | `tools_relaxaicode.py:177-183, 272-279`; caja A común en `controller_helpers.py:179-238`, usada también por las skills (`utils/skill_runtime.py:250`); criterio propio en `models/sandbox_secret_read.py`; `_ask_design` en `chatboo_session.py:1203` | **En parte** (criterios distintos y restos de §3.1 y NUEVO-1) | **reescribir**: la marca tendría que ir en `open_readonly_env` (`controller_helpers.py:179-238`), porque las skills llegan a ella sin pasar por `tools_relaxaicode` (`utils/skill_runtime.py:250`); el desmarcado y `_box_a_clear_cache`, en los dos `finally` (`tools_relaxaicode.py:271`; `utils/skill_runtime.py:260-264`). Con ello, las skills de fábrica pasarían a correr bajo `box_a_guard` (P-20). Convivencia con `sandbox_secret_read.py`, que hereda los mismos `base` e `ir.config_parameter` | alto |
| 19 | PNS-17 | `utils/fetch_url_safe.py:104-119`; `utils/mcp_client.py:103-117` | `fetch_url_safe.py:122-135` (y comprobación nueva en `:47-68, 176-179`); `mcp_client.py:103-108` sin cambios | **Sí** | `fetch_url_safe.py` con ajustes (+24 líneas antes); `mcp_client.py` aplica igual | bajo |
| 20 | PNS-70 | `pns_ai_chatboo/static/src/js/chart.umd.min.js:1-2`; `chatboo_heavy_libs.js:16, 31` | Los dos archivos, idénticos a 3.1.879 | **Sí** | aplica igual | bajo |
| 21 | PNS-20 | `pns_base/models/operation_report_wizard.py:7, 293, 298, 320, 326, 332` | Solo un comentario cambiado (`:47`) | **Sí** | aplica igual | bajo |
| 22 | PNS-100 | `controllers/validators_base.py:286-316` | `validators_base.py:257-265` | **En parte** (21 nombres) | con ajustes (7 nombres ya en la lista) | bajo |
| 23 | PNS-101 | `controllers/context_builder.py` (11), `validators.py` (5), `validators_base.py` (3), `tools_relaxaicode.py` (2), `relaxaicode_format_guard.py` (1, de Seges), `utils/skill_runtime.py` (1) | `context_builder.py:71-381` reescrito (§3.1) | **No** según el código (otro criterio, más amplio); REQUIERE PRUEBA con los tests de Seges. Quedan restos sin vía de ataque conocida: `operator.itemgetter` se da nativo (la fachada solo sustituye `attrgetter` y `methodcaller`, `context_builder.py:468-471`); un `Markup` admite campos simples en `format` (`:327-339`); `with_context`/`with_company` siguen envueltos (`:131-137`). El `env` del sandbox no expone `is_admin`, `is_system` ni `su` (`:95-97, 138-145`) | — (retirar); mantenerlo sería reescribir | medio (portar y adaptar los tests) |
| 24 | PNS-102 | `controllers/context_builder.py:76-88, 117-121, 160-163, 551-555` | `context_builder.py:95-97, 138-139, 659-660, 765-766` | **Sí** | con ajustes: copiar `_identity_no_su` tal cual (`context_builder.py:76-89` (copia)); una rama en `GuardedSandboxEnv.__getattr__` antes de `context_builder.py:138-139`; cambiar los globales de `:659-660`. `test_seges_identity_su.py` sigue sirviendo (importa `_StubController` de `test_seges_sandbox_credentials.py`: sin el parche 18 no carga, §4.1) | bajo |
| 25 | M1 | `chatboo_session.py:14, 1054, 1073`; `chatboo_canvas.py:1023, 1048` | `_paint_canvas` ya privado (`chatboo_session.py:1066`), sin comprobación de dueño; llamadores `chatboo_canvas.py:924, 948` | **En parte** (falta la comprobación de dueño) | con ajustes | bajo |
| 26 | M2 | `chatboo_session.py:924`; `chatboo_canvas.py:1008` | `pictures_as_tokens(session.env, …)` (`chatboo_session.py:937`) y `(sessions.env, …)` (`chatboo_canvas.py:910`), los dos en `sudo` | **Sí** | con ajustes (desplazado) | bajo |
| 27 | F1 | `chatboo_canvas.py` (11); `controllers/chatboo.py:1153, 1246` | CSP del fabricante en cabecera HTTP y `frame-ancestors 'self'` (`controllers/chatboo.py:1171-1187, 1277`); `json.dumps` sin escapar `<` (`chatboo_canvas.py:1097, 1426, 1439, 2046-2047`) | **En parte** (a y a′ siguen; b y d, con otro criterio del fabricante) | con ajustes en el modelo; reescribir la parte de las rutas | medio |
| 28 | D1 | `chatboo_canvas_page.py:19, 69, 87`; `security/security.xml:67` | `create` y `write` de `design` y `owner_id` solo en `su` (`chatboo_canvas_page.py:71-94`); sin comprobación de `user_ids` internos; regla del AI Administrator igual (`security.xml:67-76`) | **En parte** (`owner_id` lo cierra el fabricante, más amplio) | con ajustes | bajo |
| 29 | P-8e a | `chatboo_canvas.py` (9); `chatboo_session.py` (5) | Muestra sin escapar (`chatboo_canvas.py:829-858`); `place_rows_on_page` sin comprobación de DATA (`:2062-2105`) | **Sí** | con ajustes (zonas con cambios del fabricante: `_page_*`, `_paint_canvas`) | medio |
| 30 | M11 | `models/ai_execution_engine.py:9, 160, 424, 464, 570, 630, 712, 790` | Los seis `log_*`, privados (`:425, 462, 565, 621, 687, 781`) | **No** (otro criterio: privados). 3.1.973 cubre todos los puntos de entrada (RPC, portal y caja A); solo queda sin cubrir la comprobación interna en Python, sin atacante ni llamador afectado | — (retirar) | bajo |
| 31 | M12 | `ai_execution_engine.py:895` | `_chat_completion` (`:872`) | **No** (privado). Como en el 30: cubre RPC, portal y caja A; solo queda sin cubrir la comprobación interna en Python, sin atacante ni llamador afectado | — (retirar) | bajo |
| 32 | PNS-97 | `models/ai_trusted_action.py:23, 83, 98, 104, 109` | Sin `create`/`write`/`unlink` (`ai_trusted_action.py`; el diff solo cambia la restricción SQL, `:77-85`); ACL del AI Administrator `1,1,1,1` (`security/ir.model.access.csv:78`) | **Sí** | con ajustes (bloque cambiado justo encima del helper) | bajo |
| 33 | PNS-29 | `models/ai_provider.py:1016, 1053`; `wizard/ai_provider_usage_wizard.py:37` | `month_usage` público (`ai_provider.py:1096, 1132`); asistente sin `check_access_rights` (`ai_provider_usage_wizard.py:37`) | **Sí** | con ajustes (desplazado) | bajo |
| 34 | PNS-96 | `chatboo_canvas.py:20, 29, 653, 661, 679`; `chatboo_async_request.py:12, 20, 143, 503, 1301, 1374, 1375` | `log_no_page` sin aviso (`chatboo_canvas.py:587-616`); `_process` y `_save_to_session` cambiados (`chatboo_async_request.py:149-162, 1184-1410`) | **Sí** | con ajustes | medio |

### 4.1 Tests de Seges afectados

Tests que tocan código movido, renombrado o reescrito en 3.1.973 (sin ejecutar; por lectura de sus imports y
de los nombres que usan):

| Archivo (copia) | Parches | Qué cambia en 3.1.973 |
|---|---|---|
| `pns_ai_mcp/tests/test_seges_rpc_access.py` | 10, 13, 14, 15 | Nombres públicos que el fabricante ya privatiza: los negativos siguen dando error; revisar los casos que esperan `AccessError` y ahora darán `AttributeError` |
| `pns_ai_mcp/tests/test_seges_e4p.py` | 30, 31, 32, 33 | `log_*` y `chat_completion` privados: `call_kw` dará `AttributeError` en vez de `AccessError`; usa `controllers.safe_plan.execute_safe_plan`, reexportado (`safe_plan.py:50-52`) |
| `pns_ai_mcp/tests/test_seges_user_groups.py` | 12, 32 | Importa `execute_safe_plan` y `validate_safe_plan` (reexportados); alta y baja de grupo con `with_user` y plan como solicitante |
| `pns_ai_mcp/tests/test_seges_change_journal.py` | 17 | Paso `unlink` movido a `safe_plan_execute.py` |
| `pns_ai_mcp/tests/test_seges_sandbox_env.py`, `test_seges_identity_su.py`, `test_seges_format_guard.py`, `test_seges_facade_class.py`; `pns_ai_chatboo/tests/test_seges_skill_env.py` | 23, 24 | `context_builder.py` reescrito; `relaxaicode_format_guard.py` no existe en el fabricante; `bootstrap_skill_code_body` corre ahora en la caja A. Los cinco importan `_StubController` de `test_seges_sandbox_credentials.py`, que depende de `box_a_guard` (parche 18): sin el 18 no cargan |
| `pns_ai_mcp/tests/test_seges_sandbox_credentials.py`, `pns_ai_chatboo/tests/test_seges_canvas_box_a.py` | 18 | Caja A común (`open_readonly_env`) y guarda propia del fabricante; `_ask_design` cambiado |
| `pns_ai_mcp/tests/test_seges_sandbox_side_effects.py` | 22 | Lista del fabricante con 7 de los 28 nombres |
| `pns_ai_chatboo/tests/test_seges_chatboo_export.py` | 15 | `test_fulfill_client_export_claims_own` llama al nombre público, que ya no existe (`_fulfill_client_export`) |
| `pns_ai_chatboo/tests/test_seges_chatboo_canvas.py` | 25, 26, 27, 28, 29, 34 | `page_*` y `paint_canvas` privados (los helpers los envuelven, `chatboo_session.py:831-846`); CSP del fabricante en las rutas |
| `pns_ai_chatboo/tests/test_seges_chatboo_access.py` | 11, 15 | `unlink` de la sesión, con `write` nuevo delante |
| `pns_ai_mcp/tests/test_seges_fetch_redirect.py` | 19 | Comprobación del par nueva en el bucle de `request_public_http` (con `requests` sustituido debería devolver `''`: REQUIERE PRUEBA) |
| `pns_ai_mcp/tests/test_seges_verification.py`, `test_seges_safe_operation.py`, `test_seges_import_preview.py` | 16, 13, 21 | Sin cambios en su código salvo desplazamientos |
| `pns_ai_chatboo/tests/__init__.py` | — | Choque con el `__init__.py` nuevo del fabricante (`pns_ai_chatboo/tests/__init__.py`) |

**Tests del fabricante ligados a decisiones de Seges:**
`test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin` sigue esperando el criterio del fabricante
(`tests/test_system_action.py:543-547`; con el parche 12, F por diseño).
Los dos cambios de datos de prueba de E0′ los resuelve el fabricante con otros nombres (el `grep` del registro
no los encuentra): `test_paap_core.py` crea un usuario con `group_ai_writer` (`:27-31`) y propone dentro de
`one_cursor(self)` (`:39`); `test_change_journal.py` da los grupos del plan al superusuario en `_exec`
(`grant_groups`, `:28-34`) y rehace el test del plan fallido con un usuario creado en cursor propio
(`:156-190`). Detalle en §6.5.

## 5. Lo nuevo y su valor

Contexto de Seges (Sergio, 09/11/2026): LIYBEN y otros clientes usan multicompañía, en 14.0 y después en
17.0; interesan en principio todas las funciones nuevas; los proveedores están por decidir (la
configuración actual, «Design» solo en Gemini 3.5 flash, es provisional); hay migración prevista a 17.0.
Aquí se valoran riesgo, arrastre y coste, no el interés. «Suelto» = se puede traer a 3.1.879 como parche de
Seges sin traer media versión.

| # | Bloque | Qué hace | Archivos (3.1.973) | Riesgo | Dependencias | ¿Suelto a 3.1.879? |
|---|---|---|---|---|---|---|
| 5.1 | Facturas de proveedor desde un adjunto y `/bill-draft` | El chat propone, con un plan que se confirma, el contacto y la factura borrador (líneas por tipo de impuesto, cuenta del historial, duplicados); `/bill-draft` abre el formulario de factura con proveedor y fecha, sin guardar | Conocimiento: `pns_ai_mcp/ai/contexts/domain/business_documents.xml` (+123), `discovery_business_documents*.json`, `invoice_concepts.xml`; skill `pns_ai_chatboo/ai/skills/system/bill_draft.{md,py}`; `utils/form_draft.py`; ruta `/chatboo/open-form` (`controllers/chatboo.py:732-747`); tarjeta de formulario en `chatboo_component_v2.js`, `chatboo_svg_cards.js` y `relaxaicode_render_cards.py` | Escrituras solo por plan confirmado (caja B); el formulario solo lleva valores por defecto de campos visibles y editables (`form_draft.py:92-153`). Un escaneo o una foto se envía al proveedor con rol Visión (coste y datos de la factura hacia ese proveedor, D10) | `account` instalado (`bill_draft.py:140`); rol Visión (5.3); caja B | **No del todo:** el conocimiento y la skill son datos, pero la tarjeta de formulario arrastra ruta, utilidad, JS del componente (+392 −249) y render; la lectura de escaneos, los roles. Arrastre **medio-alto** |
| 5.2 | Skills nuevas y reescritas | `/sales-board` (tarjetas movibles con cifras, gráficos y tablas), `top_sales`, `users` (sustituye a `users_all` y `users_logged`, con `required_groups`); `financial_health` y `forecast` reescritas; salen 7 skills (§7.3) | `pns_ai_chatboo/ai/skills/system/*`; `chatboo_svg_cards.js` (+22 −1) | Corren en la caja A en 3.1.973; `sales_board` y `top_sales` sin `required_groups` (lectura con los permisos del usuario) | Runtime de skills de 3.1.973 (caja A propia) y tarjetas | Las skills son archivos: **con ajustes** (REQUIERE PRUEBA en 3.1.879, cuyo runtime es otro). Arrastre **bajo-medio** |
| 5.3 | Roles de proveedor con alternativa | Sustituye las casillas `fit_*` por el modelo `ai.provider.role` (Conversación, Audio, Visión, Vídeo, Decisión, Diseño, Parser); Diseño y Parser caen en Conversación si nadie los tiene; exportar e importar roles | `models/ai_provider_role.py`; `data/ai_provider_role_data.xml`; `views/ai_provider_role_views.xml`; dos asistentes; `models/ai_provider.py:225-260`; `utils/provider_fit.py`; `models/ai_execution_engine.py:203-300`; `utils/schema_fossils.py:267-342` | Cambia quién diseña por defecto (§6.6); el AI Administrator puede archivar roles y apagar alternativas (`security/ir.model.access.csv:55`, `1,1,0,0`); `-u` con transformación de datos (§7.3) | Motor, vistas, importación/exportación, Chatboo (`canvas_available`) | **No:** sustituye campos, motor y datos. Arrastre **alto**. Con proveedores sin decidir, es la pieza que permite especialistas por rol |
| 5.4 | Multicompañía | La IA trabaja en las compañías marcadas en el selector (la activa primero) o, sin pantalla, en la compañía por defecto del usuario; el plan se ejecuta en las compañías en que se pidió; los datos reutilizados solo valen para las mismas compañías | `utils/one_company.py`; caja A `controllers/controller_helpers.py:187-188`; `controllers/safe_plan.py:322-325`; `models/safe_operation.py:1433-1440`; `pns_ai_chatboo/models/chatboo_async_request.py:69, 103-138, 392-395`; `controllers/chatboo.py:79, 914`; `chatboo_session.py:120, 786-800`; JS | Solo cuentan las compañías del propio usuario (`one_company.py:48-63`). **En la copia** no se fija `allowed_company_ids`: en Odoo 14, sin esa clave, `env.companies` son todas las del usuario (`odoo/api.py:601-618`), que es lo que usan las reglas multicompañía (`odoo/addons/base/models/ir_rule.py:57`), y `env.company` es su compañía por defecto (`odoo/api.py:571-578`); así que la IA lee todas y crea en la de por defecto, salvo los planes confirmados desde Autorizaciones, que usan la compañía activa de quien confirma (`addons/web/static/src/js/chrome/abstract_web_client.js:141`, core; `models/safe_operation.py:815` (copia)) | Caja A, caja B, Chatboo y cliente | `one_company.py` es autónomo (79 líneas), pero el cableado toca la caja A, `safe_plan`, `safe_operation` (zona de los parches 13 y 16) y `chatboo_async_request` (zona del parche 34). Arrastre **medio-alto** |
| 5.5 | `pns.progress.job` | Trabajo largo en un hilo, con diálogo de progreso | `pns_base/models/progress_job.py`; `security/progress_job_rules.xml`; JS, CSS y plantilla | Bajo: regla «solo los míos», ACL de lectura; el hilo corre como el usuario, en cursor propio con `commit` (`:138-172`) | Ninguna; **sin llamadores** en los tres módulos | **Sí** (solo `pns_base`). Valor hoy: ninguno salvo que lo use otro módulo |
| 5.6 | Marca «generado por IA» (AI Act, art. 50) | Propiedades de documento en Excel, PDF, HTML y Word; el contenido no cambia | `utils/ai_disclosure.py`; `artifact_export_formats.py`, `artifact_export_xlsx_writer.py`, `controllers/formatters.py`; `chatboo_export.js` (`markAiPdf`) | Bajo | `artifact_export` repartido | **Con ajustes:** poca lógica, pero en `artifact_export.py` (repartido en 3.1.973) y `chatboo_export.js`. Arrastre **bajo-medio** |
| 5.7 | Pegar imágenes con Ctrl+V | La imagen pegada va con la pregunta, como un adjunto | `chatboo_component_v2.js:3736-3740, 4004-4023, 6237` | Bajo; los topes de adjuntos del servidor siguen (PNS-62) | Componente del chat | **Con ajustes** (JS). Arrastre **bajo-medio** |
| 5.8 | Seguridad del CHANGELOG sin hallazgo nuestro previo | Código de skills en caja A propia (PNS-06, más amplio); columnas secretas cerradas en la caja A (PNS-19, otro criterio); clave MCP de un administrador de Ajustes (NUEVO-3); borrado de adjuntos por el asistente de exportación (NUEVO-4); asistente «¿incluir secretos?» blindado; comprobación del par contra el DNS *rebinding* (`fetch_url_safe.py:47-68`, `remote_image.py:44-46`); `command_args` con grupo y `ensure_ai_admin` en `action_suggest_detection`; `ai.safe.choice` de solo lectura; reglas de `ai.skill.param.cache`; la sesión de Chatboo no cambia de dueño; escape de expresiones en la conversión de `attrs` (solo 17+, `pns_base/models/ir_ui_view_patch.py:274-277`) | Los citados | Bajo en todos; la caja A de skills interactúa con los parches 18 y 23 | — | **Sí y bajos:** NUEVO-3, NUEVO-4, *rebinding*, `command_args`, `ensure_ai_admin`, ACL de `ai.safe.choice`, `write` de la sesión, reglas de `ai.skill.param.cache`. **Medio:** skills en caja A (`open_readonly_env` y `bootstrap_skill_code_body`) |
| 5.9 | Otros | Ejemplos de proveedores sin claves (`static/examples/providers/*.json`, se cargan con «Importar configuración»); palabras habladas (`utils/spoken_words.py`, `data/spoken/*.json`); permisos de IA en la exportación e importación de usuarios (`utils/config_backup.py:712-753`); AI Administrator implica AI Conversational (§6.2); tests nuevos | — | Bajo | — | Ejemplos y voz: sí; el resto va con su bloque |

## 6. Choques con decisiones

### 6.1 Reintento automático de la tarjeta frente al parche 16 y D29

- **Qué hace 3.1.973:** tras un Confirmar rechazado por `too_soon`, `bad_token` o `missing_token`, la tarjeta
  pide un token nuevo a `/pns_ai_mcp/verification/pending` (solo operaciones propias, `held` para no rotar las
  demás) y confirma una vez más sola, tras 5,5 s si es `high` (`chatboo_component_v2.js`, `_retryRefusedCard`;
  `controllers/verification_ui.py:142-152`).
- **Por dónde confirma:** el reintento confirma por `/pns_ai_mcp/verification/confirm`
  (`controllers/verification_ui.py:52-76`), que no pasa por `@check_identity`. Es coherente con D29: la
  contraseña solo se pide en Autorizaciones.
- **Frente al parche 16:** no choca con su código. El parche pide contraseña en Autorizaciones
  (`action_confirm_and_execute`) y solo deja generar token al dueño (`card_payload`); la ruta `pending` ya
  filtra por dueño (`safe_operation.py:2076-2081`). El reintento usa la ruta de la tarjeta, no el botón.
- **Frente a D29 (opción c no aplicada, riesgo aceptado porque exige antes un XSS):** el reintento no da a un
  script nada que no tuviera (la espera y el token siguen en el servidor). Lo que cambia es el significado del
  clic: un Confirmar pulsado antes de los 5 s acaba confirmando sin un segundo clic. La espera deja de ser
  «la persona espera 5 s» y pasa a ser «la confirmación llega 5 s después del clic».

### 6.2 «AI Administrator implica AI Conversational» frente a la ficha 26 y a los usuarios

- `security/security_groups.xml:50`. En el `-u`, Odoo 14 añade el grupo implicado a **todos** los usuarios
  del grupo (`odoo/addons/base/models/res_users.py:1049-1075`): todo AI Administrator pasa a tener AI
  Conversational.
- **Ficha 26** (la casilla no cambia el grupo): para un AI Administrator la casilla queda siempre marcada y
  desmarcarla no quita el grupo (lo da la implicación). La reproducción acordada (decisión 5) tendría que
  hacerse con un usuario que no sea AI Administrator para no confundir las dos cosas.
- **Pruebas y entornos:** los usuarios de prueba con AI Administrator (`e1p_aiadmin`, `admin` en el
  laboratorio y `pns_demo`) ganan acceso conversacional; los dos AI Administrators de LIYBEN, también. Revisar
  los tests de Seges que esperan un AI Administrator sin acceso conversacional (§9, P-11).

### 6.3 Plan ejecutado como quien lo pidió frente al parche 12

- 3.1.973 ejecuta el plan con el `user_id` de la operación y en sus compañías
  (`safe_operation.py:1435-1440`) y escribe los grupos sin `su` (`ai_system_action.py:738-742, 768-772`):
  exige al solicitante el permiso de Odoo «Permisos de acceso» (`base.group_erp_manager`) y nada a quien
  confirma.
- El parche 12 exige Ajustes al usuario del entorno, a quien propone y a quien confirma
  (`privilege_cusp.py:105-164` (copia)). Combinados no se contradicen: el resultado es el más estricto de
  los dos, porque Ajustes (`base.group_system`) implica «Permisos de acceso» (`base.group_erp_manager`;
  `odoo/addons/base/security/base_groups.xml:14-16`). El test del fabricante `test_paap_i7_…` sigue
  fallando por diseño.
- Efecto en el parche 32: el caso del «confused deputy» (el plan corría con los permisos de quien confirma)
  ya no se da en 3.1.973; su comprobación de proponente y confirmador sigue siendo válida.
- **Confirmado en ejecución (P-5, §9):** el plan corre con el uid del solicitante, sin `su`; sin «Permisos de
  acceso» falla con el error de escritura en `res.users` y no da el grupo; con él, lo da. Para confirmar el
  plan de otro, quien confirma tiene que ser AI Administrator (`_can_resolve`, `safe_operation.py:343-350`);
  en P-5, Ajustes + AI Administrator.

### 6.4 `ai.trusted.action` y `_require_settings` frente al parche 32 y la decisión 10

- 3.1.973 mantiene el CRUD del AI Administrator sobre `ai.trusted.action` (`csv:78`, sin `create`, `write`
  ni `unlink` propios) y `_resolve_method` sigue llamando por nombre a cualquier método, también privado
  (`ai_trusted_action.py:98-115`): el parche 32 sigue haciendo falta.
- Nuevo `_require_settings`: aplicar acciones de vistas y campos exige Ajustes al usuario real
  (`ai_system_action.py:120-125, 218, 388, 505`). Solo protege tres métodos `_apply_*`
  (`_apply_view_modifier`, `_apply_field_set_required` y `_apply_view_reset_field_modifiers`; los cuatro
  `_apply_view_set_field_*` pasan por el primero, `:355, 437, 459, 481`); `_apply_module_update` y los de
  grupos no lo llaman. **Decisión 10** (consultar antes de LIYBEN si sus AI
  Administrators tienen Ajustes): con 3.1.973 la misma consulta decide también si pueden aplicar esas
  acciones por un plan, con o sin el parche 32.

### 6.5 Tests de E0′ (datos de prueba)

El fabricante corrige los dos casos con otros nombres (§4.1): `test_paap_core.py:27-39` (usuario con AI
Writer y `one_cursor`) y `test_change_journal.py:28-34, 156-190` (grupos del plan para el superusuario; el
test del plan fallido, rehecho). Con 3.1.973, los cambios de E0′ y su marcador sobran, y la línea base de
tests del fabricante (18 F con el parche 12) hay que medirla de nuevo.

### 6.6 Roles de proveedor frente a la casilla «Design» y la decisión 6

- **`fit_design` ya no existe** como campo. En el `-u`, `init()` guarda las casillas marcadas en una tabla
  temporal y borra las columnas (`schema_fossils.py:270-313`); al cargar el registro las pasa al rol con el
  mismo código (`:316-342`; `ai_provider_role.py:261-270`). Un proveedor con «Design» marcado sale con el
  rol Diseño. No hay script de migración: el paso de casillas a roles lo hacen `init()` y `_register_hook`.
- **Cambio de comportamiento:** el rol Diseño tiene como alternativa Conversación y la alternativa está
  activa por defecto (`data/ai_provider_role_data.xml:48-55`; `ai_provider_role.py:85-91`). Si ningún
  proveedor tiene Diseño, o los que lo tienen están archivados o sin cuota, diseña la cadena de
  Conversación (`ai_execution_engine.py:256-287`), que en LIYBEN empieza por `lite`. En 3.1.879, sin casilla
  no había página.
- **Qué es «la cadena de Conversación»:** los proveedores de la cadena del agente `pns_ai_chatboo` con el
  rol Conversación o sin ningún rol (`pns_ai_chatboo/models/chatboo_session.py:987-989`;
  `utils/provider_fit.py:23-25`); si ese agente no tiene cadena, diseñan todos los proveedores activos con el rol Conversación o sin rol
  (`models/ai_execution_engine.py:236-238`).
- **Cómo se expresa la decisión 6 con roles:** Diseño solo en `3.5-flash` y «Use the fallback» desactivado
  en el rol Diseño (campo `use_fallback`, editable por el AI Administrator). Así, fuera de `3.5-flash` no
  diseña nadie ni aparece el botón Canvas (P-10, §9: C1b, C3, C6 y C8b). Sin desactivarlo, la regla «nunca
  en `lite`» no se cumple si `3.5-flash` está archivado o sin cuota (C7, C8). Si `3.5-flash` falla en la
  llamada no hay failover a `lite`, con o sin alternativa (C9, C9b): el failover solo recorre los
  proveedores con el rol.
- **La cadena del agente no limita Diseño:** con la cadena [lite], flash diseña aunque no esté en ella
  (C1): la cadena no cubre Diseño y se busca entre los proveedores activos con el rol
  (`models/ai_execution_engine.py:264-270`).
- **Archivar el rol Diseño no sirve:** el motor sigue leyendo su alternativa (`Role._by_code` busca con
  `active_test=False`, `models/ai_provider_role.py:203-208`), así que con ella activa diseña `lite` (C4) y,
  sin ella, nadie (C5). Además, el proveedor pierde el rol (Odoo 14 quita los archivados del many2many) y
  entra en la cadena de Conversación como proveedor sin rol (si el agente no tiene cadena o el proveedor
  está en ella).
- `canvas_available` pasa a ser verdadero si alguien cubre Diseño **o su alternativa**
  (`chatboo_session.py:1285-1293`): el botón Canvas aparece aunque no haya proveedor de diseño. NUEVO-5
  (§7.2).

### 6.7 Multicompañía frente a los parches que filtran por usuario o dueño

| Parche | Filtro | ¿Choca con varias compañías? |
|---|---|---|
| 12 | Grupos del usuario (Ajustes) | No: los grupos no dependen de la compañía |
| 16 | `user_id` de la operación | No |
| 18 | Campos por modelo, en el cursor de la caja A | No por lectura; en 3.1.973 la caja A lleva `allowed_company_ids` (`controller_helpers.py:187-188`): las lecturas de identificación siguen la regla multicompañía del modelo. Medido en P-12 (§9): la caja A lee solo en las compañías marcadas en la pantalla (sin pantalla, la de por defecto; una ajena se ignora) |
| 25 | Dueño de la sesión | No |
| 26 | Lee las imágenes sin `su` | Con 3.1.973, las imágenes de registros de compañías no marcadas en la pantalla dejan de verse (regla multicompañía); en la copia se ven las de todas las compañías del usuario. Medido en P-12 (§9): 3.1.973 tal cual muestra las de A, B y C (C no es del usuario); con el parche 26 simulado y pantalla A, solo A; con A y B, A y B |
| 28 | Dueño y lectores internos | No |
| 32 | Ajustes | No |
| 33 | ACL del asistente | No; `ai.provider` no tiene compañía |
| 34 | Job y sesión | No |

Ninguno queda incompleto por leer el código; las pruebas con dos compañías están en §9 (P-12).

### 6.8 Otros choques encontrados

- **N12 (b′, base 3.1.879):** el camino B la sustituye; el C la mantiene (§8).
- **Decisión 2 de la segunda ronda (opcionales: orden por campo secreto, no):** 3.1.973 lo cierra en su
  guardián (`sandbox_secret_read.py:74-91`); si se porta el parche 18, en el suyo sigue abierto.
- **D10 (PNS-18 aceptado):** la alternativa de rol amplía los candidatos fuera de la cadena (§3.1); el texto
  de la aceptación («la garantía de la casilla exige no tener externos activos») sigue valiendo.
- **Parche 34 con la opción A y F1:** depende de cómo pinta el cliente `original_content`; el componente
  cambia en 3.1.973 (+392 −249). REQUIERE PRUEBA (P-13).
- **Regla del repo sobre `NOTICE`:** traer 3.1.973 cambia los `NOTICE` del fabricante (§2.5); no es un
  cambio de Seges.
- **Decisión del 23/10 (no pedir el commit de `pns_base`):** deja de hacer falta con la numeración nueva
  (§2.4).

## 7. Seguridad y datos

**Método.** Grep de `@http.route` en los dos árboles; modelos nuevos con su ACL y reglas; métodos públicos
nuevos con `sudo`, cursor propio o `commit()`; `data/` (crons, `noupdate`); `init()`, `_register_hook` y
`schema_fossils`. Sin BD: lo que depende de los datos va a §9.

### 7.1 Superficie nueva

| Elemento | Dónde (3.1.973) | Control | Gravedad propuesta |
|---|---|---|---|
| Ruta `/chatboo/open-form` (única ruta nueva) | `pns_ai_chatboo/controllers/chatboo.py:732-747` | `auth='user'`, acceso a Chatboo; no escribe: devuelve una acción de ventana y valores por defecto de campos visibles y editables, comprobando lectura de many2one y alta del modelo (`utils/form_draft.py:30-153`) | Baja (la acción la elige el cliente entre las `ir.actions.act_window` existentes) |
| Modelo `ai.provider.role` y relación `role_ids` | `models/ai_provider_role.py`; `csv:12, 55` | Lectura para internos; el AI Administrator escribe colores, `active` y `use_fallback`; alta y baja solo en `su` (`:210-230`); `chip_html` sin sanear pero con `html_escape` y colores validados (`:34-41, 170-192`) | Baja (cambia quién recibe cada turno: §6.6) |
| Asistentes de roles | `wizard/import_provider_roles_wizard.py:29-31`; `wizard/ai_provider_role_tools_wizard.py`; `csv:58, 64` | `ensure_ai_admin`; escritura en `sudo` (`utils/config_backup.py:624`) | Baja |
| Acción «Duplicate» de proveedores (lista) | `views/ai_menus.xml:84-92`; `models/ai_provider.py:1167-1179` | `ensure_ai_admin`; `copy()` con los permisos del usuario | Baja |
| Modelo `pns.progress.job` | `pns_base/models/progress_job.py`; `security/progress_job_rules.xml` | Regla de dueño, ACL de lectura; `_launch` privado; hilo con cursor propio y `commit` como el usuario | Baja (sin llamadores) |
| Guardián de columnas secretas | `models/sandbox_secret_read.py` (herencia de `base` e `ir.config_parameter`) | Solo en el cursor de la caja A y sin `su`; además quita la precarga de esas columnas en **todos** los modelos (`:58-63`) | Restos: NUEVO-1 y PNS-102 |
| Importación de usuarios con permisos de IA | `utils/config_backup.py:712-753`; `models/mcp_user.py:609-649` | AI Administrator; mapeo dinámico de campos de `ai.mcp.user` en `sudo`, incluido `is_mcp_manager` (alias `is_ai_admin`): da AI Administrator a un usuario existente; la clave de un administrador de Ajustes se descarta (`:769-781`) | Baja (lo mismo que puede hacer en el formulario) |
| Caché de `api_call` confirmada al escribir | `models/api_result_cache.py:107-140` (CHANGELOG 3.1.932) | Privado; cursor propio con `commit` | Baja |
| Token de la tarjeta en cursor propio | `utils/engine_tool_run.py:544-557` | Comprueba el dueño antes de generar | Baja |
| Multicompañía | `utils/one_company.py:48-79` | Solo compañías activas del usuario | Baja |
| Servicios externos | Rol Visión para escaneos de facturas (5.1); ejemplos de proveedores sin claves | Configuración del AI Administrator | Datos hacia el proveedor (D10) |
| Crons, parámetros y claves | Ningún cron ni parámetro nuevo; cambia el código de dos crons (NUEVO-2); `use_fallback` es un campo, no un parámetro | — | — |

### 7.2 Hallazgos NUEVOS de esta sección

| Id | Grav. (propuesta) | Afecta a | Qué pasa | Dónde | Estado |
|---|---|---|---|---|---|
| **NUEVO-5** | Baja (comportamiento) | 3.1.973 | Con el rol Diseño vacío, archivado o sin cuota, el lienzo diseña con la cadena de Conversación, porque la alternativa viene activa en los datos: los proveedores de la cadena del agente `pns_ai_chatboo` con el rol Conversación o sin ningún rol (`chatboo_session.py:987-989`; `utils/provider_fit.py:23-25`) o, si ese agente no tiene cadena, todos los proveedores activos con el rol Conversación o sin rol (`models/ai_execution_engine.py:236-238`). No hay script de migración: el paso de casillas a roles lo hacen `init()` y `_register_hook` (§6.6). En una BD donde ningún proveedor tenía la casilla «Design» (p. ej. LIYBEN, donde es nueva desde 3.1.879), tras el `-u` aparece el botón Canvas y diseña el proveedor de conversación. El CHANGELOG anuncia los roles con alternativa, no este efecto | `data/ai_provider_role_data.xml:48-55`; `models/ai_execution_engine.py:271-286`; `pns_ai_chatboo/models/chatboo_session.py:1285-1293` | **Confirmado en ejecución (P-10, §9):** sin proveedor con Diseño o con el rol archivado, el botón aparece y diseña `lite` (tests; en la interfaz con Gemini, el caso sin rol, C2); con la alternativa desactivada, ni botón ni página |

### 7.3 Qué hace un `-u` desde 3.1.879 sobre una BD con datos

En orden aproximado de la carga de Odoo 14 (`odoo/modules/loading.py`):

1. **Versiones:** 14.0.1.2.69, 14.0.3.1.973 y 14.0.2.1.587, mayores que las instaladas; ningún script
   de `migrations/` (§2.6).
2. **`init()` de `ai.schema.fossil`** (`models/ai_schema_fossil.py:28-41`): borra tablas sobrantes,
   renombra XML ID antiguos, promueve columnas, convierte proveedores `decision`, **guarda las casillas
   `fit_*` en `ai_provider_fit_stash` y borra sus columnas** (`schema_fossils.py:290-313`), borra columnas
   sobrantes y renombra parámetros (`engine_params.py` idéntico: sin renombrados nuevos frente a 3.1.879).
3. **Tablas y columnas nuevas:** `ai_provider_role`, `ai_provider_role_rel`, `pns_progress_job`, los dos
   asistentes de roles, `chatboo_async_request.screen_company_ids`, `chatboo_async_request.result_note`
   (Boolean guardado, `pns_ai_chatboo/models/chatboo_async_request.py:61`) y
   `chatboo_session.last_query_company_ids`.
4. **Datos y seguridad:** roles sembrados (`noupdate="0"`: nombre, ayuda, orden y alternativa se
   reescriben en cada `-u`; los colores propios se conservan, `ai_provider_role.py:1-13`), con sus ACL,
   vistas y menú (`security/ir.model.access.csv:12, 55, 58, 64`; `views/ai_provider_role_views.xml`);
   `ai.safe.choice` pasa a solo lectura para internos; reglas nuevas de `ai.skill.param.cache`; la regla de
   `chatboo.canvas.job` deja de dar escritura (sin efecto práctico: su ACL ya era de solo lectura,
   `pns_ai_chatboo/security/ir.model.access.csv:5`); `pns.export.secrets.wizard` pierde el permiso de alta
   (`pns_base/security/ir.model.access.csv:3`, `1,1,0,1`); acción nueva «Duplicate» de proveedores
   (`views/ai_menus.xml:85-92`); **AI Administrator implica AI Conversational y Odoo lo propaga a los AI
   Administrators existentes** (§6.2); regla de `pns.progress.job`; tres JS nuevos en `views/assets.xml`.
5. **Skills de Chatboo:** `import_from_module('pns_ai_chatboo')` (`data/chatboo_skill_data.xml:10-11`)
   crea `bill_draft`, `sales_board`, `top_sales` y `users`, actualiza `financial_health`, `forecast` y
   `billing`, y **borra las filas de fábrica** de `annual_billing`, `cash_forecast`, `credit_facility`,
   `customer_risk_analysis`, `sys_info`, `users_all` y `users_logged`. Las skills no tienen XML ID: se
   borran las filas con `source_module='pns_ai_chatboo'` y `owner_id` vacío cuyo archivo ya no está en
   disco (`_unlink_retired_from_module`, `ai_skill_disk.py:403-418`); las de los usuarios llevan `owner_id`
   y se conservan. **Riesgo:** una skill de fábrica editada sin ponerle dueño se borra, con sus cambios. El
   mecanismo ya estaba en 3.1.879 (`ai_skill.py:2220-2261`). Su caché de parámetros se borra en cascada
   (`ai_skill_param_cache.py:37-41`): P-14 queda resuelta en esa parte. Para `bill_draft`, `sales_board`,
   `top_sales` y `users`: si ya existe una skill con ese código, el `-u` la salta si tiene dueño; si no lo
   tiene, la adopta y la reescribe, salvo que sea de otro módulo (`ai_skill_disk.py:262-303`).
6. **Contextos de fábrica:** `<function _import_all_from_module>` en `noupdate="0"` (`data/mcp_data.xml:5-7`;
   `pns_ai_chatboo/data/chatboo_context_data.xml:4-5`; código en `models/ai_context_disk.py:186-201`)
   reescribe en cada `-u` los contextos sin dueño (los de los usuarios, con `owner_id`, se saltan) y borra
   los de fábrica cuyo archivo ya no está. Archivos de contexto que cambian entre 3.1.879 y 3.1.973 (por
   comparación de archivos, 12): en `pns_ai_mcp/ai/contexts/` (8), `core/system_prompt.xml`,
   `domain/business_documents.xml`, `domain/invoice_concepts.xml`, `domain/email.md`,
   `domain/geography.xml`, `domain/sale_order_duplicate_workflow.md`,
   `discovery/discovery_business_documents.json` y `discovery/discovery_business_documents_es_ES.json`;
   en `pns_ai_chatboo/ai/contexts/` (4), `domain/ui_focus/ui_focus.xml`,
   `domain/presentation_grids/presentation_grids.xml`, `discovery/discovery_page_tab.json` y
   `discovery/discovery_page_tab_es_ES.json`.
   Un contexto de fábrica editado sin dueño pierde sus cambios. P-21.
7. **Fin de la carga (`_register_hook`):** las casillas guardadas pasan a roles
   (`schema_fossils.py:316-342`); si un rol aún no existe, esperan a la siguiente carga. El `_register_hook`
   de los roles trabaja dentro de un *savepoint* y borra la tabla del stash cuando queda vacía
   (`ai_provider_role.py:261-270`; `schema_fossils.py:339-341`). En `pns_demo`, si siguen los tres Gemini
   con «Design» (staging de E3′), los tres salen con el rol Diseño, `lite` incluido (§6.6).
8. **Crons:** NUEVO-2 (los dos de purga quedan con `model.gc_expired()`).
9. **Carpetas de tests:** sin efecto en la BD; la `tests/__init__.py` del fabricante en Chatboo choca con
   la de Seges al combinar (§2.3).
10. **LIYBEN** parte de 3.1.782 (`docs/pendiente/instalacion_liyben_pns_ai.md:30-32`): a lo anterior se
    suma lo del `-u` de 3.1.782 a 3.1.879 (comp §9.2, U1 a U21, incluido U9).

### 7.4 Resumen: qué queda abierto en cada lado

- Corregido por el fabricante y retirable: parches 10, 13, 14, 23 (P-6, §9: negativos rechazados; restos sin vía de ataque conocida), 30 y 31.
- Abierto en 3.1.973 sin parche de Seges: PNS-54, PNS-102, PNS-82 (`unlink`), PNS-17 (cabeceras), PNS-97,
  PNS-100 (21 nombres), PNS-07 (9 nombres), M2, F1 (escape y descargas; descargas sin CSP, medido en P-9),
  PNS-29 resto 3, NUEVO-1, NUEVO-2, NUEVO-5 (confirmado, P-10).
- Abierto en los dos lados: la vía de la sesión de D5 (HTML escrito por RPC en `canvas_design` y compartido;
  §3.7, P-9).
- Abierto en la copia y corregido en 3.1.973: NUEVO-3, NUEVO-4, PNS-81 resto, el *rebinding* de `fetch_url`,
  el código de skills fuera de la caja A, la multicompañía. En la copia, sin `allowed_company_ids`, la IA
  lee en todas las compañías del usuario (`odoo/api.py:601-618`; `odoo/addons/base/models/ir_rule.py:57`) y
  crea en la de por defecto (`odoo/api.py:571-578`), salvo los planes confirmados desde Autorizaciones, que
  usan la compañía activa de quien confirma (`addons/web/static/src/js/chrome/abstract_web_client.js:141`,
  core; `models/safe_operation.py:815` (copia)); §5.4.

## 8. Datos para decidir: A, B, C

Sin recomendación. Esfuerzos con la escala de §4 (bajo, medio, alto); «tests» = archivos `test_seges_*`.

| | **A.** Quedarse en 3.1.879 con los parches 10-34 | **B.** Pasar a 3.1.973 entera y volver a portar | **C.** Quedarse y traer cambios concretos como parches |
|---|---|---|---|
| Esfuerzo en parches | Ninguno (25 vigentes, validados en `pns_demo` el 09/11/2026) | Portar 19 (los 12 «sí» y los 7 «en parte»): 15 bajos, 3 medios (27, 29, 34), 1 alto (18). Retirar 6 (10, 13, 14, 23, 30, 31) | Uno nuevo por cada cambio traído, con registro, marcador, test y neutralización (CLAUDE.md del repo) |
| Esfuerzo en tests | Ninguno | 20 archivos de tests de Seges que ejecutar; 7 tocan código reescrito (filas de §4.1 cuyo cambio es una reescritura, no un movimiento, un cambio de nombre ni un desplazamiento): los 5 de `context_builder.py` (`test_seges_sandbox_env.py`, `test_seges_identity_su.py`, `test_seges_format_guard.py`, `test_seges_facade_class.py` y `pns_ai_chatboo/tests/test_seges_skill_env.py`) y los 2 de la caja A común (`test_seges_sandbox_credentials.py` y `pns_ai_chatboo/tests/test_seges_canvas_box_a.py`); en parte, uno más (`test_seges_chatboo_canvas.py`, por la CSP del fabricante en las rutas del 27). Línea base del fabricante nueva (§6.5) | Un test por parche nuevo |
| Otros trabajos | — | NUEVO-2 (datos de dos crons), NUEVO-5 (configurar `use_fallback` del rol Diseño), revisar §6.2; ciclo de laboratorio y staging como E1′ a E4′, con scripts de pruebas nuevos | Laboratorio y staging de lo traído |
| Riesgo | El conocido | Diff de +27 000 / −26 000 líneas; transformación de datos en el `-u` (§7.3); comportamientos nuevos (plan como solicitante, multicompañía, alternativa de Diseño, AI Administrator con acceso conversacional); código nuevo sin compilar con Python 3.7.3 (§9, P-18) | Bajo por pieza; la copia se aleja del fabricante en cada pieza |
| Hallazgos que quedan abiertos | Los del inventario sin cerrar, más NUEVO-3 y NUEVO-4 (Altas; NUEVO-4 no necesita `unlink`: basta crear el asistente, y la limpieza de transitorios borra el adjunto como superusuario), PNS-81 resto, *rebinding*, código de skills fuera de la caja A, alcance multicompañía | Los de 3.1.973 que Seges no parchee (§7.4), más NUEVO-1 si no se porta el 18, NUEVO-2 y NUEVO-5 | Los de A menos lo traído |
| Funciones nuevas | Ninguna | Todas (§5) | Solo las sueltas (§5, última columna): Ctrl+V, marca de IA, `pns.progress.job`, ejemplos de proveedores; no la multicompañía completa, los roles ni las facturas de proveedor sin arrastre |
| `-u` de `pns_demo` | Ninguno nuevo | §7.3 desde 3.1.879 | El de las piezas (CSV y reglas, si las hay) |
| `-u` de LIYBEN | El previsto (3.1.782 → 3.1.879 con parches, plan §3.1) | De 3.1.782 a 3.1.973: comp §9.2 (U1 a U21) más §7.3; o en dos pasos | Como A |
| Informe al fabricante | Lista actual (plan §3.2); se pueden señalar como ya corregidos en 3.1.973 NUEVO-3, NUEVO-4 y lo de §7.4 | Se rehace sobre 3.1.973: pasan a «corregido» M10, M13, PNS-83, M11, M12, PNS-30, PNS-81 resto, PNS-101 (con prueba); entran NUEVO-1, NUEVO-2, NUEVO-5 y los restos de PNS-07 (9 nombres), PNS-100 (21), PNS-19 (`su` y caché), F1 (escape y descargas), PNS-102 | Como A, indicando qué se ha tomado del fabricante |

### 8.1 Candidatos del camino C

| Cambio | Archivos (3.1.973) | Cierra | Tamaño | Notas |
|---|---|---|---|---|
| Borrado de adjuntos del asistente de exportación | `pns_base/models/export_file_wizard.py:8-27` | NUEVO-4 | ~8 líneas | Usa `EXPORT_MARK` de `pns_base/utils/portable_io.py` |
| Clave MCP de un administrador de Ajustes | `models/mcp_user.py:740-781`; `utils/config_backup.py:734-738` | NUEVO-3 | ~40 líneas | Más su test (`tests/test_key_of_settings_admin.py`) |
| `_static_str` en Python 3.7 | `pns_ai_chatboo/utils/skill_capture_compose.py:319-327` | PNS-81 resto | ~8 líneas | — |
| Par que contesta (*rebinding*) | `utils/fetch_url_safe.py:47-68, 176-179`; `utils/remote_image.py:16, 44-46` | Resto menor de PNS-17 y PNS-59 | ~30 líneas | En la zona del parche 19 |
| Asistente «¿incluir secretos?» | `pns_base/models/export_secrets_wizard.py`; CSV (`1,1,0,1`) | Endurecimiento | ~12 líneas | El CSV no admite marcador (como el parche 17) |
| `command_args` con grupo; `ensure_ai_admin` en `action_suggest_detection` | `models/external_server.py:84, 225, 882` | Endurecimiento (PNS-08/09) | 3 líneas | — |
| `ai.safe.choice` de solo lectura; reglas de `ai.skill.param.cache`; la sesión no cambia de dueño | `security/ir.model.access.csv:81`; `security/security.xml` (+32); `chatboo_session.py:1968-1974` | Endurecimiento (PNS-14, PNS-55) | CSV, XML y ~6 líneas | — |
| Código de skills en una caja A propia | `utils/skill_runtime.py:248-264`; `controllers/controller_helpers.py:179-238` | Resto de PNS-06 | Medio | Interactúa con las marcas de los parches 18 y 23 |
| Marca «generado por IA» | `utils/ai_disclosure.py` y sus llamadas | — (cumplimiento) | Medio (archivos repartidos) | — |
| Ctrl+V de imágenes | `chatboo_component_v2.js` | — | Medio (JS) | — |
| Multicompañía | `utils/one_company.py` y cableado (§5.4) | Alcance de compañía | Alto | Toca las zonas de los parches 13, 16 y 34 |

### 8.2 Efecto en la migración a Odoo 17.0

- El fabricante publica la misma base para las series 14.0 a 20.0, con una rama plana por serie. El Python es
  común (decide por `ODOO_VERSION`, p. ej. `models/ai_trusted_action.py:77-85`); el JS va por pila: `owl1` (14
  y 15), `owl2` (16 a 19), `owl3` (20) (CHANGELOG de `pns_base`, 1.2.68).
- **Parches de Seges sobre código común a las series:** 24 de 25 tocan Python o XML de los módulos (10 a 19 y
  21 a 34). **El 20** (Chart.js) es JS de la pila `owl1`: en 17.0 hay que rehacerlo sobre `owl2`. **El 18**
  usa puntos internos del ORM de Odoo 14 (`_read`, `_read_group_raw`, `_fetch_field`, caché por hilo): en 17
  no sirve tal cual; el guardián del fabricante ya trae los ganchos de 17+ (`sandbox_secret_read.py:96-109`).
  **El 16** usa `check_identity`, que existe en 17
  (`/opt/odoo-src/17.0/odoo/odoo/addons/base/models/res_users.py:139`). **El 24** depende de que `env.user`
  sea `su`; en 17, por comprobar en las referencias.
- **A y C:** al migrar habrá que tomar la rama 17.0 de una versión del fabricante y portar los parches; en la
  práctica, el trabajo de B más las diferencias de 17. El arreglo de `ir_ui_view_patch.py` (escape de
  expresiones al convertir `attrs`, `pns_base` 1.2.68) solo actúa en 17+ y no está en la copia.
- **B:** los parches quedarían ya portados al Python que el fabricante comparte con 17.0; en la migración
  quedarían el 20 (JS), el 18 (ORM) y los cambios de datos de la propia migración de Odoo (skill
  `odoo-migracion`).

### 8.3 Cómo repetir esta comparación en la siguiente versión

1. `diff -rq`, `diff -ruN` y recuento de líneas por módulo (sin `__pycache__`), como en esta pasada.
2. **CHANGELOG:** anotar los huecos (aquí, 3.1.880-3.1.904, 2.1.539-2.1.541 y 1.2.48-1.2.52 sin entrada) y
   leer las entradas de seguridad contra el inventario.
3. **Repartos:** Grep de los nombres de función de los parches en todo el árbol nuevo antes de dar nada por
   borrado (§2.2).
4. **Greps del registro** («Cómo comprobar…» de cada parche) contra el árbol nuevo, con estos ajustes:
   - parches 15 y 22: comparar la lista `RELAXAICODE_SIDE_EFFECT_METHODS` nombre a nombre y buscar los nombres
     que falten como `def _<nombre>(` (privatizados);
   - parche 23: `grep -n "_ALLOWED_ENV_ATTRS\|is_db_handle\|compile_sandbox" controllers/context_builder.py`;
   - parche 24: `grep -n "env.user\|env.company\|_ALLOWED_ENV_ATTRS" controllers/context_builder.py`;
   - tests de E0′:
     `grep -n "grant_groups\|one_cursor\|group_ai_writer" tests/test_change_journal.py tests/test_paap_core.py`;
   - NUEVO-1:
     `grep -n "invalidate\|clear_cache\|_box_a_clear" controllers/controller_helpers.py models/sandbox_secret_read.py`;
   - NUEVO-2: `grep -rn "model\.\w*(" */data/*.xml` frente a los `def` de esos modelos, solo en datos
     `noupdate="1"`;
   - NUEVO-3: `grep -n "_may_set_key_of\|def _ensure_key_admin" models/mcp_user.py`;
   - NUEVO-4: `grep -n "def unlink" -A6 pns_base/models/export_file_wizard.py`;
   - NUEVO-5: `grep -n "fallback_id\|use_fallback" data/ai_provider_role_data.xml models/ai_provider_role.py`.
5. **Inventario** (`docs/specs/estado_hallazgos_3879.md`) como lista de comprobación, fila a fila, y este
   documento como plantilla de veredictos.
6. Manifiestos (`version`, `license`, `depends`, `data`, `assets`/`qweb`), `migrations/`, `init()`,
   `_register_hook` y datos `noupdate`.
7. Python 3.7: los greps de §3.3 (PNS-81) y, en el laboratorio, `py_compile` con 3.7.3 y
   `odoo-dev 14 paridad`.

## 9. REQUIERE PRUEBA

Todas en el laboratorio (`odoo-dev 14`), sobre BD de laboratorio; lo que necesita datos de un cliente, sobre
una copia que carga Sergio. «Lab 973» = una BD instalada con 3.1.973; «lab copia» = la copia de trabajo.

| # | Qué resuelve | Prueba mínima | Qué se mira |
|---|---|---|---|
| P-1 | NUEVO-1 | Lab 973 sin el parche 18, AI Administrator, test de Seges `test_box_a_engine_cache_before_run` adaptado (el motor lee la clave en el mismo hilo y después la caja A pide la columna) | Si la lectura da `AccessError` o devuelve el valor (sin registrar el valor: solo si hubo error) |
| P-2 | NUEVO-2 | BD de laboratorio con 3.1.879 → `-u` a 3.1.973 | `SELECT code FROM ir_cron` de los dos crons y el log tras su siguiente pasada |
| P-3 | NUEVO-3 | Lab copia: un AI Administrator sin Ajustes llama a `set_mcp_api_key` sobre el usuario MCP de un administrador de Ajustes (adaptando `tests/test_key_of_settings_admin.py`) | Si la clave cambia en la copia; en lab 973, `AccessError` |
| P-4 | NUEVO-4 | Lab copia: un usuario interno crea el asistente de exportación apuntando a un adjunto de prueba ajeno y lo borra | Si el adjunto de prueba sigue existiendo |
| P-5 | PNS-01/02 con `with_user` | Lab 973: plan `user.add_group` de un grupo normal propuesto por un AI Administrator (a) sin «Permisos de acceso», (b) con él; confirmado por un administrador de Ajustes; y lo mismo con el parche 12 portado | Si el grupo se da en cada caso y qué error sale |
| P-6 | PNS-101, PNS-102, PNS-36 y el parche 23 | Lab 973 sin los parches 23 y 24: `test_seges_sandbox_env.py`, `test_seges_identity_su.py`, `test_seges_format_guard.py`, `test_seges_facade_class.py` y el test de `{0.cr.dbname}` (los que no dependen de `relaxaicode_format_guard.py`) | Qué tests pasan con el criterio del fabricante. Por lectura, lo que no quedaría cubierto: `test_seges_sandbox_env.py` (fallan `test_allowed_attrs` y `test_engine_attrs_on_wrapper`; nueve negativos siguen rechazados, pero fallarían por el texto del error); `test_seges_identity_su.py` (no se importa: es del parche 24); `test_seges_format_guard.py` (no se importa; sin cubrir `test_markup_rejected_unit` y los 11 de `TestSegesEngineNames`); `test_seges_facade_class.py` (sin cubrir `test_type_itemgetter_class`) |
| P-7 | Parche 19 en 3.1.973 | Lab 973 con el parche 19 portado: `test_seges_fetch_redirect.py` | Si la comprobación del par devuelve `''` con `requests` sustituido y los tres tests pasan |
| P-8 | PNS-07, 9 nombres | Lab 973, relaxaicode con driver simulado, como AI Administrator y como interno: `action_suggest_detection` por relación y los métodos del asistente OpenAPI sobre una fila propia | Si se llega a llamar al método (con el método sustituido en la clase) |
| P-9 | CSP del lienzo (§3.7) | Lab 973: página con un diseño que intente cargar una imagen y hacer una petición al propio Odoo; abrir la descarga desde disco | Qué bloquea el navegador en el marco y en la descarga (consola) |
| P-10 | §6.6 y NUEVO-5 | Lab 973 tras `-u` desde 3.1.879: proveedores con y sin «Design»; rol Diseño vacío, archivado y con `use_fallback` desactivado | Qué proveedor diseña (`ai.log`) y si aparece el botón Canvas |
| P-11 | §6.2 | Lab 973 tras `-u`: grupos de los AI Administrators; tests de Seges que usan AI Administrators | Si ganan AI Conversational y qué tests cambian de resultado |
| P-12 | Multicompañía | Lab con dos compañías y un usuario en las dos: turno con una marcada; plan confirmado desde la otra; página con imágenes de las dos (parche 26) | Compañía de lo leído y de lo escrito; imágenes visibles |
| P-13 | Parche 34 (opción A y F1) en 3.1.973 | Lab 973 con el parche portado: rechazo del lienzo en un turno con tabla | El aviso en la burbuja tras recargar y en `original_content` |
| P-14 | Skills retiradas | Lab con 3.1.879, sesión con `cash_forecast` activa y caché de parámetros → `-u` | Estado de la sesión (las filas de `ai.skill.param.cache` se borran en cascada: resuelto por lectura, §7.3) |
| P-15 | `-u` completo | Copia de `pns_demo` (la carga Sergio) → `-u` a 3.1.973 | Log; `ai_provider_role_rel` frente a las casillas antiguas; tabla `ai_provider_fit_stash` borrada; grupos de AI Administrators; skills |
| P-16 | PNS-99 | Lab 973: plan `user.remove_group` de un grupo que el usuario tiene por implicación | Estado de la operación y del diario |
| P-17 | PNS-41 | Lab 973: ficha de Aplicaciones de los tres módulos | Si se ve la descripción del módulo o la estándar |
| P-18 | Python 3.7.3 | `py_compile` de los `.py` de 3.1.973 con la imagen de laboratorio y `odoo-dev 14 paridad`; además, un test del sandbox con Python 3.7 (reparaciones con `ast.unparse` y compilación del sandbox, `context_builder.py:362`, §3.3 PNS-81) | Errores de sintaxis o librerías; si las reparaciones se aplican y si el código del sandbox compila y se ejecuta |
| P-19 | Carga de la sesión sin reintento | Lab 973, el caso de la sesión 59 del staging de E4′ | Si sigue el fallo de serialización |
| P-20 | Parche 18 portado a `open_readonly_env` (§4) | Lab 973 con el 18 portado: ejecutar las skills de fábrica de `pns_ai_chatboo` (todas las de `ai/skills/system/`) como un usuario interno | Qué skills fallan bajo `box_a_guard` (lecturas de campos que no son de identificación en los 11 modelos que guarda) |
| P-21 | Contextos y skills de fábrica en el `-u` (§7.3) | Copia de la BD (`pns_demo` o la que cargue Sergio), antes del `-u`, solo lectura | Contextos (`ai.context`) y skills (`ai.skill`) sin `owner_id` de `pns_ai_mcp` y `pns_ai_chatboo` cuyo código o archivo esté entre los cambiados o retirados, y si alguno se editó a mano (fecha de escritura posterior a la del último `-u`): se reescribirían o se borrarían |

**Resultado de P-3 y P-4 (10/11/2026): NUEVO-3 y NUEVO-4 confirmados en ejecución en nuestra rama.** Lab copia:
rama `14.0-pns-ai-3879` (módulos de `8d218ea`), contexto `odoo-dev 14` `lab_pns_ai_3879`, BD
`lab_pns_ai_3879_14`; módulos cargados desde la copia de trabajo (`/mnt/compartidos/third_party/pns_*`).
`odoo-dev 14 shell` con usuarios creados en la misma transacción, cada caso en un savepoint deshecho y
`rollback` final. Sin claves ni hashes en la salida.

- P-3 (un AI Administrator sin Ajustes frente a la fila MCP de un administrador de Ajustes; control: la de un
  empleado, cambia): el hash **cambia, sin excepción**, por las seis vías: `set_mcp_api_key`,
  `action_generate_mcp_api_key`, `write` del hash, `create` con el hash, asistente de importación de usuarios
  MCP y `config_backup._import_users` (0 errores, 0 avisos).
- P-4 (un interno frente a un adjunto de otro usuario que no puede leer; control: su `unlink` directo da
  `AccessError` y el adjunto sigue): crear el asistente apuntando al adjunto y borrarlo → **adjunto borrado**;
  crear el asistente y borrarlo como lo hace la limpieza de transitorios (`sudo().browse(ids).unlink()`,
  `odoo/models.py:6548`) → **adjunto borrado**; solo crearlo → el adjunto sigue.
- Restos: ninguno en la BD (usuarios, contactos, filas MCP, adjuntos y asistentes de prueba a 0; `ai_log` sin
  filas nuevas). Fuera de la transacción: huecos en las secuencias y el JSON subido al asistente de
  importación de P-3 en el filestore (login de prueba y clave de prueba sin uso), marcado para la limpieza del
  filestore.

**Resultado de P-21 (10/11/2026): en `pns_demo` no hay ediciones manuales que perder.** Consulta de solo
lectura (`BEGIN TRANSACTION READ ONLY` … `ROLLBACK`), validada antes en `lab_pns_ai_3879_14` y lanzada por
Sergio en el staging, BD `pns_demo`. Fecha del último `-u`: la mayor `ir_module_module.write_date` de
`pns_ai_mcp` y `pns_ai_chatboo`, 09/11/2026 09:50 (E4′).

- Reescribe: los 12 contextos de los archivos de §7.3 y las 3 skills `billing`, `financial_health` y
  `forecast`. Todos activos, sin dueño, `write_uid` 1 y ninguno escrito después del último `-u`.
- Borra: las 7 skills retiradas (`annual_billing`, `cash_forecast`, `credit_facility`,
  `customer_risk_analysis`, `sys_info`, `users_all` y `users_logged`) existen, activas y sin dueño.
- Adopta (`bill_draft`, `sales_board`, `top_sales`, `users`): ninguna fila. Ninguna skill archivada.
- Riesgo (por lectura): al buscar la fila que reescribe o adopta, 3.1.973 no ve las skills archivadas
  (búsqueda sin `active_test=False`, `models/ai_skill_disk.py:262-271`), así que intentaría crearla de nuevo
  y el alta chocaría con `code_uniq` (`models/ai_skill.py:272-274`). En `pns_demo` no se da (ninguna
  archivada). Queda por probar en P-15.

**Resultado de P-18 (10/11/2026): 3.1.973 compila y el sandbox se ejecuta con Python 3.7.3; las 6
reparaciones con `ast.unparse` no se aplican.** Laboratorio nuevo `lab_pns_ai_973` (contexto `odoo-dev 14`,
BD `lab_pns_ai_973_14`, imagen con el mismo Dockerfile que `lab_pns_ai_3879`), sin repos compartidos
montados: los tres módulos son una copia de `_fabricante/3.1.973` sin cambios de contenido (`diff -rq`
vacío; solo se dio permiso de lectura, porque el zip los deja en `600`) y se cargan solo desde ahí
(addons_path, línea `addons paths` del log de Odoo y `get_module_path`). `paridad`: se pueden instalar.
Instalación limpia de `pns_ai_chatboo`: OK, sin avisos. Tests en el módulo aparte `seges_pruebas_973`
(`odoo-dev 14 tests`, BD de tests nueva): 6 tests, 0 fallos.

- `sys.version`: `3.7.3 (default, Mar 23 2024, 16:12:05) [GCC 8.3.0]`, la esperada.
- `compile()` de los 372 `.py` de los tres módulos: 0 errores. Junto con la importación (`paridad` e
  instalación) cubre la sintaxis y lo que se importa al cargar; no cubre las APIs de Python 3.8+ en código
  que no se ejecuta, que es lo que cubre el grep de §3.3 (PNS-81).
- `compile_sandbox` (`context_builder.py:368`): compila y redirige las lecturas de atributos. relaxaicode
  completo (`tool_relaxaicode`, stub del test e2e del fabricante): pasa por `compile_sandbox` y se ejecuta;
  el código legítimo y el del ORM devuelven datos y una fuga por `__class__` da un error controlado.
- Las 6 reparaciones con `ast.unparse` (`validators_repair.py:106, 244, 397`, `validators_sort.py:548`,
  `relaxaicode_recipe.py:192, 363`) no se aplican: devuelven el código sin cambios y no rompen nada; 4
  escriben un `WARNING` con traceback y las 2 de `relaxaicode_recipe.py` fallan sin rastro (por lectura,
  con esos datos llegan a `ast.unparse`). En un turno, el código que habría que reparar se rechaza con un
  error que pide reescribirlo (con `%` literal, error al ejecutar con una pista): más vueltas con el
  modelo, sin efecto en la seguridad. **Igual en nuestra rama**: los mismos 6 usos están en 3.1.879 y en
  `pns_ai_mcp` de `14.0-pns-ai-3879`.

**Resultado de P-6, C2 y P-1 (10/11/2026).** Laboratorio `lab_pns_ai_973` (el de P-18), módulo de tests
`seges_pruebas_973` (`odoo-dev 14 tests`, BD de tests nueva que el kit borra). Copias de los tests de Seges
de `14.0-pns-ai-3879` con el stub de `test_seges_sandbox_credentials.py:271-299` (sin nada del parche 18);
cada diferencia con el original, en el README del módulo. La caja A es siempre la real: `registry.cursor()`
da un cursor nuevo porque `TransactionCase` no activa el modo test (`odoo/tests/common.py:1403`, solo en
`HttpCase`), así que solo ve datos confirmados; los usuarios y el proveedor de C2 y P-1 van como datos XML
del módulo. En la salida solo se registró sí/no (nunca claves ni secretos).

- **P-6** (51 tests ejecutados; no ejecutables: `test_identity_helper_not_su`, `test_markup_rejected_unit` y
  los 11 de `TestSegesEngineNames`, porque usan código de los parches 23 ampliado y 24). Coincide con la
  predicción de la fila P-6:
  - `test_seges_sandbox_env.py`: fallan `test_allowed_attrs` (el `env` no expone `is_admin`) y
    `test_engine_attrs_on_wrapper` (no expone `cr`), criterio del fabricante más restrictivo. Los nueve
    negativos se rechazan sin que salga el secreto ni nombres internos y fallan solo por el texto del error.
  - `test_seges_format_guard.py`: los 19 que no dependen de `relaxaicode_format_guard.py` pasan, incluido
    `test_pns36_cr_dbname`.
  - `test_seges_facade_class.py`: solo falla `test_type_itemgetter_class` (`itemgetter` nativo, que solo
    resuelve subíndices).
  - `test_seges_identity_su.py`: la predicción decía «no se importa», pero se ejecutan cuatro de cinco.
    `test_wrapper_user_not_su` y `test_wrapper_company_not_su` fallan (`user` y `company` llevan `su`):
    **PNS-102 sigue abierto**. `test_positive_reads_own_user_company` pasa con el usuario confirmado.
    Aclaración (10/11/2026, tras P-12): `test_wrapper_company_not_su` construye `GuardedSandboxEnv` sobre el
    entorno del test, sin `allowed_company_ids` (`test_seges_identity_su.py:48-51`), y no pasa por la caja A:
    sin esa clave, Odoo 14 da `user.company_id`, que viene de `env.user` en `su` (`odoo/api.py:578`). En la caja
    A real, `one_company_context` fija `allowed_company_ids` (`controllers/controller_helpers.py:186`; medido en
    P-12) y `company` sale sin `su` (`odoo/api.py:577`), como dice §3.1. El dato que vale es
    `test_wrapper_user_not_su`: `env.user` siempre en `su` (`odoo/api.py:548`).
- **C2** (`test_c2_no_access_field_via_user`, usuario interno confirmado): la lectura de `totp_secret` del
  administrador a través de `user` se hace sin error (la respuesta llega a `'leido'`). Confirma C2 en
  3.1.973. El test no devuelve el valor.
- **P-1** (AI Administrator sin Ajustes; el motor lee la clave por `_api_key_for_inference`,
  `models/ai_provider.py:202-210`):

  | Caso | Clave en caché al abrir la caja A | `ERROR (` | Texto de la guarda de 3.1.973 | Aparece la clave |
  |---|---|---|---|---|
  | Copia de `test_box_a_engine_cache_before_run` (fila sin confirmar, por relación) | sí | no | no | sí |
  | Proveedor confirmado, caché caliente, por relación | sí | no | no | sí |
  | Proveedor confirmado, caché caliente, por `browse` | sí | no | no | sí |
  | Control: caché vacía, por relación | no | no | sí | no |
  | Control: caché vacía, por `browse` | no | no | sí | no |

  **Mecanismo de NUEVO-1 confirmado:** con la clave en la caché del hilo la guarda no actúa. El rechazo de la
  guarda no lleva `ERROR (` porque relaxaicode presenta los `AccessError` como mensaje para el usuario
  (`controllers/relaxaicode_failures.py:55-76`).
- **Condición de caché caliente.** §3.4 es correcta: `Cursor.commit` llama a `flush_env(self)` (con
  `clear=True` por defecto), que ejecuta `env.clear()`, y `Cursor.rollback` llama a `clear_env(self)`, que
  también ejecuta `env.clear()`. `Environment.clear` invalida la caché, que es la del hilo
  (`odoo/sql_db.py:65-87, 449-468`; `odoo/api.py:472, 628-635, 904-907`). Basta un entorno sobre el cursor
  que hace `commit`, sea cual sea ese cursor. En los tests no hay `commit` intermedio:
  `_create_log_entry` no escribe con `test_is_running` (`models/ai_log.py:716`). La caché caliente reproduce
  un turno sin escritura de log entre la lectura de la clave y la caja A.
- **El `commit` de `_create_log_entry` en cada ronda.** `ai.log._create_log_entry` abre un cursor con
  entorno (`models/ai_log.py:720-722`) y hace `commit` (`:847`). El motor lo llama antes de cada llamada al
  LLM (`_log_provider_llm_request`, `utils/engine_tool_loop.py:488-495`) y tras cada respuesta
  (`_tool_loop_log_response`), y lee la clave una vez al montar el turno (`utils/engine_tool_loop.py:172` →
  `utils/engine_turn_messages.py:156`). En un turno de Chatboo, la clave ya no está en caché al abrir la caja
  A. Entre medias no hay `commit` ni `rollback` del cursor del turno: el `commit` de Chatboo es anterior
  (`pns_ai_chatboo/models/chatboo_async_request.py:161`), los otros son posteriores (`:329, 542, 590`) y cada
  herramienta va en un `SAVEPOINT` lanzado con `cr.execute` (`utils/engine_tool_run.py:324-357`).
- **Otros caminos, por lectura:**
  - `/mcp` (relaxaicode o skill llamada por un cliente MCP): **no alcanzable** en lo revisado. Cada petición
    empieza con la caché vacía (`odoo/service/wsgi_server.py:87`, `odoo/api.py:431-440`). La autenticación
    busca `ai.mcp.user` por `mcp_api_key_hash` sin cargarlo en caché (`controllers/main.py:695-698,
    845-847`; las columnas secretas no se precargan, `models/sandbox_secret_read.py:58-63`). Los
    `get_param` son de claves no secretas (`controllers/main.py:314-315, 350`). La vía de skills no lee
    secretos antes de la caja A (`utils/skill_runtime.py:171-250`). En `tools/call` solo hay `rollback` si
    la herramienta falla (`controllers/main.py:1378`).
  - Varias herramientas en una respuesta, una con LLM por dentro: **no alcanzable** en lo revisado.
    - Parámetros híbridos de una skill (rol Parser): lee la clave en `llm_json_completion_result`
      (`utils/agent_engine.py:107-140`) y escribe `_mcp_log('skill_param_hybrid')` antes de ejecutar la skill
      (`utils/engine_skills.py:214, 267`).
    - Cada herramienta registra su ejecución con `commit` (`controller._log_mcp_operation` →
      `utils/engine_tool_run.py:46-70` → `utils/agent_engine.py:723`; relaxaicode,
      `controllers/relaxaicode_replies.py:86-102`).
    - En el failover, la ronda siguiente registra la petición antes de llamar
      (`utils/engine_tool_loop.py:488-495`).
    - Design corre en el hilo de un trabajo de Canvas, con su propia caché
      (`pns_ai_chatboo/models/chatboo_canvas_job.py:67-69` → `chatboo_job.py:193-224`, hilo con
      `Environment.manage()` propio).
    - Visión es la elección del proveedor del turno (`utils/agent_engine.py:1034`).
- **No revisado:**
  - Si `_create_log_entry` falla antes del `commit` (el error se traga, `models/ai_log.py:853-856`), la caché
    no se vacía.
  - Métodos que llaman a un LLM y que el propio código de la caja A puede alcanzar (relacionado con P-8;
    p. ej. `models/external_server.py:800`).
  - La caché `ormcache` de `ir.config_parameter.get_param`, que es otra caché.
  - Otros canales (voz, Secretary) y columnas secretas distintas de la clave del proveedor leídas en `sudo`
    durante un turno.

**Resultado de P-5, P-8 y P-12 (10/11/2026).** Laboratorio `lab_pns_ai_973` (el de P-18), módulo de tests
`seges_pruebas_973` (`odoo-dev 14 tests`, BD de tests nueva que el kit borra). Caja A siempre la real
(`tool_relaxaicode` con el stub de P-6, cursor propio `READ ONLY`), con usuarios, compañías, servidores,
claves y lista blanca como datos XML del módulo (solo existen en la BD de tests). Para el plan (P-5 y la
escritura de P-12) y las imágenes de P-12, `_test_cursor_view` del fabricante (`pns_ai_mcp/tests/_helpers.py:46-77`,
como en `test_one_company_live.py:72-91`): lo que pide `registry.cursor()` corre en la transacción del test.
Sin LLM ni red: las llamadas al LLM, `requests` y la resolución de nombres de `fetch_url_safe` se sustituyen
por registradores que cortan. Cada diferencia con el original, en el README del módulo. Logs:
`tests-20261110-131241.log` (P-5, P-8 primera parte, P-12), `tests-20261110-133023.log` (complemento de
P-8) y `tests-20261110-135653.log` (P-8, `action_suggest_detection` real); batería completa: 92 tests, los
32 F y 1 E de antes, ninguno de estas pruebas. En la salida solo sí/no (nunca claves ni tokens).
Verificación de `odoo-reviewer` (solo lectura) de las seis partes (P-5, P-8 primera parte, complemento de
P-8, P-12 lectura, escritura e imágenes): «mide lo que dice: sí» en las seis, con los límites que se indican.

- **P-5** (plan `user.add_group` de un grupo normal, sin el parche 12; propuesta por `request_safe_plan`,
  confirmación con `action_confirm_and_execute`). El confirmador tiene que ser **Ajustes + AI
  Administrator**, no solo Ajustes como decía la fila: para confirmar el plan de otro hay que ser AI
  Administrator (`_can_resolve`, `safe_operation.py:343-350`).

  | Proponente (AI Administrator) | uid al ejecutar | `su` | Grupo dado | Error | Operación | Diario |
  |---|---|---|---|---|---|---|
  | (a) sin «Permisos de acceso» | el del proponente | no | no | `UserError` con el error de escritura en `res.users` («Administration/Access Rights») | `cancelled` | `user.add_group` `failed` |
  | (b) con «Permisos de acceso» | el del proponente | no | sí | — | `executed` | `user.add_group` `applied` |

  Origen del error de (a): `check_access_rights('write')` de `res.users` (`odoo/addons/base/security/ir.model.access.csv:71`)
  al escribir los grupos (`ai_system_action.py:741` → `pns_base/utils/compat.py:139`);
  `action_confirm_and_execute` lo presenta como `UserError` («Error confirming the operation: …»). Se predijo
  `AccessError` y sale `UserError`: mismo origen. Límites: no se ejercitan la barrera de grupos de la
  herramienta `safe_plan_request` ni el auto-confirmado (no aplica a `danger=high`).
- **P-8** (4 de los 9 nombres de §3.7, caja A real, como AI Administrator y como interno).

  | Nombre y camino | AI Administrator | Interno |
  |---|---|---|
  | `action_suggest_detection` por relación (`ai.api.server.key.server_id`), método real | pasa `ensure_ai_admin` y llega a la llamada al LLM | se para en `ensure_ai_admin` («Only AI Administrators…»); no llega al LLM |
  | `action_suggest_detection` por `env['ai.api.server']` | lo para la puerta de catálogos (`[PROHIBITED:API_CATALOGUE]`) | ídem |
  | `action_generate_openapi`, método real | llega a la llamada al LLM | `AccessError` de la ACL del modelo; no llega al LLM, a `requests` ni a `ai_log` |
  | `action_generate`, método real | llega a `requests` (descarga de la documentación) | ídem |
  | `action_log_generation_usage`, método real | llega al intento de escritura en `ai_log` | ídem |

  Los tres del asistente OpenAPI, un AI Administrator llega igual sobre su fila y sobre la de otro AI
  Administrator: Odoo 14 no limita los transitorios por `create_uid` y el modelo solo tiene la ACL de
  `group_ai_admin`. Las escrituras en la fila no se guardan (caja A de solo lectura); ninguno intenta escribir
  en el servidor. Con los métodos sustituidos (primera parte), el interno también «llega» a los del asistente:
  solo indica que el sandbox no filtra el nombre; con el método real lo para la ACL. Límites: «llega al LLM» es
  llegar a la llamada con los permisos de ese usuario, cortada por un registrador; no se ejercitan las
  comprobaciones posteriores (agente activo, límite de gasto, modelo del proveedor); la resolución de nombres
  es ficticia (con `seges.invalid` real, `action_generate` se pararía en «Cannot resolve»); `ai_log` solo
  intento (en tests `_create_log_entry` no escribe, `models/ai_log.py:716`); el servidor OpenAPI, su entrada
  de lista blanca de tipo openapi y la de tipo web para `seges.invalid` se crearon solo en la BD de tests. Sin
  probar: `mark_seen`, `sandbox_helpers` y los tres de `ai.skill.capture.wizard` (siguen por lectura, §3.7).
- **P-12** (usuario AI Administrator en A y B, A por defecto; C no es suya; la pantalla llega como en un turno:
  `chatboo_async_request.py:392-395` → `one_company_context`).
  - Lectura (caja A real):

    | Pantalla | `allowed_company_ids` en la caja A | Ve |
    |---|---|---|
    | B | B | B |
    | ninguna | A | A |
    | A y B | A, B | A, B |
    | C (ajena) | A | A |

  - Escritura: propuesta con la pantalla en B (guardada por `safe_plan.py:322-325`) y confirmada por el mismo
    usuario con el selector en A. El plan corre en B (`env.company` = B, `allowed_company_ids` = B, sin `su`).
    Escribir en el contacto de B entra; en el de A, `UserError` por la regla multicompañía y operación
    `cancelled`. La compañía de un registro creado no se mide con `res.partner` (sin compañía por defecto en
    14): la medida es `env.company` = B.
  - Imágenes (`page_html` y `page_url`; las dos dan lo mismo):

    | Versión | Pantalla | A | B | C (ajena) |
    |---|---|---|---|---|
    | 3.1.973 tal cual | A | sí | sí | sí |
    | 3.1.973 + parche 26 (simulado) | A | sí | no | no |
    | 3.1.973 tal cual | A y B | sí | sí | sí |
    | 3.1.973 + parche 26 (simulado) | A y B | sí | sí | no |

    3.1.973 tal cual muestra la imagen de C, que no es del usuario: M2 abierto. El parche 26 se simula con una
    sustitución de `pictures_as_tokens` que reproduce `chatboo_session.py:924` y `chatboo_canvas.py:1008` de la
    rama (`env(su=False)`) en los dos puntos donde 3.1.973 la usa. `_store_design` guarda la página en un cursor
    propio (`chatboo_session.py:1007-1022`): las llamadas van en el cursor compartido (segunda ejecución; en la
    primera la página no se guardaba y la comprobación no medía).

**Resultado de P-10 y P-9 (10/11/2026): NUEVO-5 confirmado en ejecución y en interfaz; la decisión 6 se
expresa con Diseño solo en `flash` y la alternativa desactivada; la CSP del marco bloquea lo externo y deja
salir peticiones al propio Odoo (las imágenes llegan sin sesión; el fetch, sin poder leer la respuesta); las
descargas, sin CSP.** Laboratorio `lab_pns_ai_973` (el de P-18), BD
`lab_pns_ai_973_14`, módulo de tests `seges_pruebas_973` (`odoo-dev 14 tests`, BD de tests nueva que el kit
borra). En los tests, proveedores inventados (clave inventada, endpoint `.invalid`): P10-lite (rol
Conversación) y P10-flash (solo Diseño); los demás proveedores y la cadena de `pns_ai_chatboo` se archivan
durante el test; sin LLM ni red (el driver, `get_llm_driver`, se sustituye por un registrador; el motor y su
failover son los reales). Logs: `tests-20261110-153355.log` (P-10 parte A y P-9 parte A; 108 tests) y
`tests-20261110-172655.log` (P-10 parte B automatizada); batería completa: **115 tests, los mismos 32 F y 1 E
de antes (por nombre)**, ninguno de estas pruebas; las líneas de la parte A salen idénticas en las dos
ejecuciones. En la salida solo nombres de proveedor y sí/no. Diferencias con el original, en el README del
módulo.

- **P-10, parte A** (`tests/test_p10_roles_diseno.py`): lista completa y en orden de
  `get_providers_for_agent('pns_ai_chatboo', need='design')` y `canvas_available()` como `base.user_admin`
  sin `su`, con dos cadenas («sin cadena» y «cadena [lite]»); failover con
  `llm_completion_for_agent(..., need='design')`, flash lanzando un error. Dónde se lee el rol:
  `Role._by_code` busca con `active_test=False` (`models/ai_provider_role.py:203-208`) y el motor lee
  `use_fallback` de ese registro (`ai_execution_engine.py:273-275`): un rol archivado sigue dando su
  alternativa. Quién tiene el rol sale de `role_ids` (`ai_provider.py:242-245`), y Odoo 14 quita los
  archivados al acceder al many2many (`odoo/fields.py:2965-2970`).
- **P-10, parte B automatizada** (`tests/test_p10_interfaz.py`, `HttpCase`, cadena [lite], usuario con
  acceso a Chatboo): botón por `/chatboo/check_health`, la petición que hace la pantalla al cargar Chatboo
  (`static/src/js/chatboo_component_v2.js:1689-1691`; el botón depende de `canvas_available`, `:1707` →
  `_applyCanvas`, `:3824-3829`); diseño por `/chatboo/canvas/build`, la ruta del botón
  (`static/src/js/chatboo_charts.js:3070-3076`), con una tabla de dos filas. En modo test el trabajo se
  ejecuta dentro de la petición (`models/chatboo_job.py:189-191`). El motivo se anota envolviendo
  `log_no_page`, porque en modo test `ai.log` no se escribe (`pns_ai_mcp/models/ai_log.py:716-717`).

  | Caso | Diseño, sin cadena | Diseño, cadena [lite] | Botón (A / B) | `/chatboo/canvas/build` (B): pedido a · página |
  |---|---|---|---|---|
  | C1 flash con Diseño, alternativa sí | [P10-flash] | [P10-flash] | sí / sí | [P10-flash] · sí |
  | C1b ídem, alternativa no | [P10-flash] | [P10-flash] | sí / — | — |
  | C2 nadie con Diseño, alternativa sí | [P10-lite, P10-flash] | [P10-lite] | sí / sí | [P10-lite] · sí |
  | C3 ídem, alternativa no | [] | [] | no / no | [] · no |
  | C4 rol archivado, alternativa sí | [P10-lite, P10-flash] | [P10-lite] | sí / sí | [P10-lite] · sí |
  | C5 rol archivado, alternativa no | [] | [] | no / no | [] · no |
  | C6 flash archivado, alternativa no | [] | [] | no / no | [] · no |
  | C7 flash archivado, alternativa sí | [P10-lite] | [P10-lite] | sí / — | — |
  | C8 flash sin cuota, alternativa sí | [P10-lite] | [P10-lite] | sí / — | — |
  | C8b flash sin cuota, alternativa no | `UserError` «No AI provider has available quota this month.» | ídem | no / — | — |
  | C9 flash falla, alternativa no | intentos [P10-flash], no responde nadie | ídem | — / sí | [P10-flash] · no |
  | C9b flash falla, alternativa sí | intentos [P10-flash], no responde nadie | ídem | — | — |

  - Sin failover a lite cuando flash falla (C9, C9b): el bucle solo recorre la lista de Diseño, y
    `use_fallback` solo actúa si nadie tiene el rol, no si quien lo tiene falla. Mensaje de la ruta en C9:
    «No page was built. The reason is in the AI History.»; el motivo que se deja para `ai.log` es el error
    del proveedor.
  - Cadena de Conversación: «sin cadena», en C2 a C5 es [P10-lite, P10-flash] (flash, al perder su único rol,
    cuenta como proveedor sin rol, `utils/provider_fit.py:23-25`); en el resto, [P10-lite]. Con cadena
    [lite], siempre [P10-lite]. En C4 y C5 la relación de flash con Diseño sigue en la BD, pero el rol
    archivado no cuenta.
  - Paso de casillas a roles (`TestP10Casillas`): **sintético; -u real pendiente de P-15 (fase C)**. Se
    añaden `fit_design` y `fit_conversation` a `ai_provider` en la transacción del test y se llama a
    `stash_fit_columns` y `promote_fit_columns` (`utils/schema_fossils.py:290-342`): columnas `fit_*` tras
    `init`, 0; filas guardadas, 5; Diseño → [design], Conversación → [conversation], ambas →
    [conversation, design], ninguna → []; un proveedor archivado con la casilla también recibe [design]; la
    tabla temporal se borra.
  - Recarga de los datos de roles (`TestP10Actualizar`: `data/ai_provider_role_data.xml` con `convert_file`
    en modo `update`, no el -u completo): `use_fallback` desactivado y el rol archivado **se conservan**; la
    alternativa no cambia.
- **P-10 manual de Sergio** (interfaz, proveedor real Gemini):
  - C1, sin cadena: botón sí, página sí, diseña `gemini-3.6-flash`; sin línea de rol en el log.
  - C2, con cadena [P10-lite]: botón sí, página sí (tras dos HTTP 503 «high demand» de Google), diseña
    `gemini-3.5-flash-lite`; log: «AI: no provider holds role "design" for agent "pns_ai_chatboo"; asking
    "conversation"». **NUEVO-5 confirmado en interfaz.**
- En el laboratorio, el proveedor «flash» usó `gemini-3.6-flash`; la decisión 6 se refiere a `3.5-flash`.
  En la prueba cuentan los roles, no el modelo.
- **Matices de P-10 (no cambian la decisión 6):**
  - La ruta del lienzo acepta la petición aunque la pantalla no muestre el botón (C3, C5, C6) y termina sin
    página: no diseña nadie.
  - El motivo registrado en esos casos, «No AI provider is configured for agent pns_ai_chatboo», es
    engañoso: el agente tiene proveedor; lo que falta es quien cubra Diseño.
  - La fila de `ai.log` de un diseño fallido no guarda proveedor ni modelo (por lectura:
    `models/chatboo_canvas.py:602-613`).
- **P-9, parte A** (`tests/test_p9_csp_cabeceras.py`, `HttpCase`; usuarios de prueba `ann`, con acceso a
  Chatboo, y `bob`, interno):

  | Qué | Resultado |
  |---|---|
  | `/chatboo/canvas/<id>` y `/chatboo/page/<id>` | 200; CSP igual a la del fabricante: sí; `X-Frame-Options`: no; `nosniff`: sí |
  | Escape de un marcador inofensivo (`"></iframe><b id=p9>`, sin script) | 1 marco abierto y 1 cerrado; sin escapar: no; escapado: sí (las dos rutas) |
  | Las dos descargas | 200; CSP: no; `nosniff`: sí; adjunto: sí; diseño tal cual: sí |
  | Control: crear `chatboo.canvas.page` por `call_kw` | no (`AccessError`) |
  | `write` de `canvas_design` en la sesión propia por `call_kw` | aceptado: sí; guardado: sí |
  | Compartir después por el panel (POST con CSRF) | página creada: sí; con el diseño escrito por RPC: sí; `bob` lector: sí; aviso a `bob`: sí |
  | `bob` abre la página | 200; CSP: sí; el diseño va en la respuesta (en el `srcdoc`): sí |

- **P-9, parte B de Sergio** (Chrome; sonda escrita por RPC en `canvas_design` de su sesión, sin LLM; página 2
  compartida con un usuario interno; descargas abiertas como `file://`):

  | Dónde | Externo (img y fetch) | Imágenes del propio Odoo | fetch al propio Odoo |
  |---|---|---|---|
  | Marco del lienzo (`/chatboo/canvas/2`, dueño) | bloqueado por la CSP (`connect-src`, `img-src`) | cargan, llegan sin sesión (log de Odoo: BD «?» frente a `lab_pns_ai_973_14` en las peticiones con sesión) | la CSP los deja salir; el GET simple llega (200) y CORS impide leer; el POST JSON se queda en el preflight (OPTIONS 400) |
  | Página compartida (`/chatboo/page/2`, otro usuario) | igual | cargan | igual |
  | Descargas (`file://`) | sin CSP: `ERR_NAME_NOT_RESOLVED`, «No hay problemas» | cargan | CORS (origen `null`) |
  | Control: `/chatboo/canvas/2` como otro usuario | 404 | | |

  - El HTML escrito por RPC en la sesión propia llega al otro usuario por Compartir y se ejecuta en su
    navegador, dentro del marco (vía D5 de la comparación con 3.1.879; §3.7).
  - Límite: solo Chrome; Firefox no probado.
