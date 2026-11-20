# Análisis pns_ai_mcp — Bloque 8: presentación, exportaciones, cliente web y tests (Odoo 14.0)

> Análisis de código de terceros (Patanegra Soft, Apache-2.0). **No se diseña ni se propone
> código.** Rama `14.0-analisis-pns-ai`, copia de trabajo `./pns_ai_mcp/`. Core de referencia:
> `/opt/odoo-src/14.0/odoo/` (el paquete Python está en `/opt/odoo-src/14.0/odoo/odoo/`).
>
> Clasificación: **HECHO** (archivo:línea), **INFERENCIA** (deducido del código, no ejecutado),
> **PENDIENTE** (comprobar con `odoo-dev 14`). Rutas sin prefijo = `pns_ai_mcp/`.
> Referencias: [MAPA]=`analisis_pns_ai_mcp_1_mapa.md`, [CONOC]=`..._2_conocimiento.md`,
> [SECR]=`..._3_conexiones_secretos.md`, [MCP]=`..._4_servidor_mcp.md`, [CAJAB]=`..._5_caja_b.md`,
> [CODE]=`..._6_ejecucion_codigo.md`, [LLM]=`..._7_motor_llm.md`, [BASE]=`analisis_pns_base.md`.

---

## 0. Piezas del bloque y quién las llama

- Las utilidades `utils/*` de este bloque **no tienen modelos ni vistas**: son funciones puras que
  el motor (`utils/agent_engine.py`, [LLM]) y el sandbox (`controllers/tools_relaxaicode.py`,
  [CODE]) llaman para dar forma a la respuesta del LLM antes de guardarla en la sesión de Chatboo
  (`pns_ai_chatboo`, fuera de alcance salvo donde se cita).
- Llamadas (HECHO, Grep): `agent_engine.py:1952` (anti-eco), `:2468` (record_cite),
  `:2944` (report_outline_guard), `:2987-2990` (delivery_gate + linkify), `:3167-3184`
  (primary_artifact + basket), `:3343-3352`, `:3520`, `:3682-3880` (delivery_gate), `:4381-4413`
  (exportaciones); `tools_relaxaicode.py:815` (record_cite), `:2160` (field_selection);
  `context_builder.py:488,513` (field_selection y delivery_gate expuestos al sandbox);
  `safe_plan.py:736-742` (chips de descarga), `:889` (ack records), `:1065-1144` (descargas
  binarias); `relaxaicode_render.py:280,1113,1146,1160` (presentation_mode);
  `pns_ai_chatboo/models/chatboo_async_request.py:360` (presentation_mode) y `:1384-1391`
  (SVG); `pns_ai_chatboo/controllers/chatboo.py:302` (icono Excel);
  `pns_ai_chatboo/models/chatboo_session.py:401,437` (aviso por bus).

---

## 1. Utilidades de presentación

| Utilidad | Qué hace con la respuesta del LLM | ¿Modifica BD? | Evidencia |
|---|---|---|---|
| `presentation_mode.py` (363 l.) | Decide el **diseño tabla/gráfico** (`show-table`, `show-chart`, `table`, `dashboard`), el motor de gráficos (`echarts`/`chartjs`) y eje Y simple/doble. Detecta la intención por palabras (es/en) del mensaje del **usuario**, no del LLM. Prioridad: resultado > sesión > ICP. | Sí: `apply_sticky_show_mode` escribe `presentation_show_mode` en `chatboo.session` | HECHO `:63-120` (vocabulario), `:250-273`, `:276-291`, `:301-320` (write `:318`); lee la sesión con `sudo` `:347` y la id desde el contexto o `request.chatboo_options` `:330-354`; ICP `pns_ai_chatboo.*` con `sudo` `:203-221` |
| `primary_artifact.py` (258 l.) | "Artefacto principal del turno": el primer resultado completo (filas, mapa, gráfico o HTML ≥ 20 caracteres de texto) queda **fijado en la posición 0** de la cesta; los siguientes lo mejoran in situ (UPGRADE, si el código reutiliza `previous_result`/`raw_data` o repite título) o se añaden como secundarios (MINOR); las sondas (PROBE) se ignoran. | No | HECHO `:111-152`, `:176-191`, `:226-258`; detecta la reutilización con AST `:34-52` |
| `turn_presentation_basket.py` (243 l.) | **Cesta del turno**: acumula N resultados presentables de herramientas en una sola burbuja; si hay más de uno, los fusiona en `{'tables': [...]}` y **re-renderiza el HTML en el servidor** con `relaxaicode_render` (descarta el `formatted_text` del sobre fusionado). | No | HECHO `:53-85` (elegibilidad, confía en `__fmt_type__` `server_side_python`/`author_html`/`local_json`/`local_raw` `:81-84`), `:154-192`, `:195-243` (`work.pop('formatted_text')` `:223`, render `:230-243`) |
| `record_cite.py` (141 l.) | Tarjeta de cita al pie: de las referencias `(model,id)` del turno deja **un único documento cabecera**; una `X.line` sube a su cabecera `X` (busca el many2one al padre); si hay varias sin rol → nada ("sin mural"). | No (lee con `browse`, sin `sudo`) | HECHO `:13-39`, `:49-65`, `:68-90`, `:119-141` |
| `record_delivery_gate.py` (255 l.) | **Candado de entrega**: si hubo filas tabulables en el turno y el cierre del LLM es corto (≤ 280 caracteres) y no contiene tabla ni enlace `/web#id=`, el motor **reinyecta** el listado (1a). El reinyectado de turnos anteriores (1b) está desactivado (`return False`). Además extrae filas de pasos de Safe Plan para `previous_result`. | No | HECHO `:25-31`, `:34-38`, `:53-72`, `:75-91`, `:104-132`, `:135-194` |
| `record_linkify.py` (112 l.) | **Auto-enlace**: en la prosa del LLM envuelve la primera aparición de cada nombre de registro ya resuelto en el turno como Markdown `[nombre](/web#id=N&model=M&view_type=form)`. No inventa ids; opt-out `links_off`. | No | HECHO `:30-31`, `:50-112` |
| `report_outline_guard.py` (170 l.) | Modo informe: si la skill declara `report_outline`/`closing_required`, **añade los encabezados que falten** con el texto fijo `_Pendiente de narrativa; cifras en las tablas anteriores._` y el cierre; recupera la narrativa de una ronda anterior del mismo turno si el cierre la sustituyó. | No | HECHO `:71-99`, `:116-170` (texto fijo `:161-163`, stub `:12`) |
| `response_anti_echo.py` (159 l.) | **Anti-eco**: calcula la huella SHA-256 del atributo `data-chatboo-dataset` de cada bloque `o_chatboo_table_block` y **borra de la respuesta** las tablas ya mostradas en mensajes anteriores (salvo que este turno las regenerase). Analiza HTML con regex y conteo de `<div>`. | No | HECHO `:20-28`, `:30-66`, `:69-97`, `:115-143` |
| `verification_ack_records.py` (91 l.) | Tras confirmar un Safe Plan sin nueva llamada al LLM, construye la tarjeta de documento con los ids creados/escritos/copiados (cabeceras vía `record_cite`). Nombre recortado a 120. | No | HECHO `:46-74`, `:77-91`; carga `record_cite` por ruta si falla el import relativo `:12-27` |
| `svg_download.py` (479 l.) | **Extrae los SVG "dibujo"** (≥ 400 caracteres, máx. 5 por turno, no decorativos) de la respuesta (SVG crudo, bloques de código, `<pre><code>`, escapado), los **sanea por regex**, los guarda como adjunto de la sesión y los **quita de la burbuja**, sustituyéndolos por un chip. Nombra el archivo a partir del mensaje del usuario. | Sí (vía `session_download`) | HECHO `:50-51`, `:230-254` (saneado), `:334-411`, `:430-451`, `:454-479` |
| `field_selection.py` (100 l.) | Helper precargado en el sandbox: devuelve `[(valor, etiqueta)]` de un campo Selection usando `_description_selection(env)` (existe en 14: core `odoo/fields.py:2390`) o `fields_get`; da una pista reintentable si el código del LLM iteró un `selection` invocable. | No | HECHO `:42-87`, `:90-100` |
| `controllers/formatters.py` (865 l.) | Serializadores: XLSX con estilo (openpyxl), PDF tabular con miniaturas y gráfico (reportlab); además HTML/CSV/XML "clásicos". | No | ver §2 |

Observaciones transversales:
- HECHO: todas son agnósticas de dominio por diseño (los comentarios lo repiten), pero contienen
  vocabulario fijo es/en para detectar intención (`presentation_mode.py:63-120`,
  `svg_download.py:62-82`) y textos fijos en español (`report_outline_guard.py:12,162`).
- INFERENCIA: varias utilidades **reescriben la salida del LLM** (añaden encabezados, enlaces,
  reinyectan tablas o las quitan). Lo que ve el usuario no es literalmente lo que generó el modelo;
  el `ai.log` guarda lo enviado/recibido ([SECR] §7), no necesariamente la burbuja final.
- INFERENCIA (rendimiento): `artifact_export._load_formatters()` vuelve a **ejecutar el archivo
  `controllers/formatters.py` en cada llamada** (`spec_from_file_location` + `exec_module`, sin
  caché, `artifact_export.py:1898-1918`), y `_word_cell_html` la invoca **por cada celda** de una
  exportación Word (`:1291-1293`); igual `_slug_stem`/`export_filename` con `svg_download.py`
  (`:887-922`). Exportaciones Word grandes serán lentas.

---

## 2. Exportaciones

### 2.1 Disparador y flujo

1. HECHO: el motor llama a `_attach_requested_file_export` cuando el **mensaje del usuario**
   nombra un formato (`pdf`, `xlsx/excel/xls`, `txt`, `md/markdown`, `html`, `word/doc/docx`) —
   detección por tokens, no por verbos (`artifact_export.py:50-63`, `:184-251`;
   `agent_engine.py:4370-4420`). PowerPoint/ODT/RTF/ODS se rechazan (`:54-58`, `:118-126`).
2. HECHO: con sesión de Chatboo (`client_fulfill=True`, `agent_engine.py:4403`) **PDF, Word y
   HTML no se generan en el servidor**: se crea un chip "pendiente" y el **cliente Chatboo** monta
   el archivo (tabla + gráfico pintado) (`artifact_export.py:31`, `:1084-1095`). Excel y Markdown
   (y txt) sí se serializan en el servidor (`:1096-1119`).
3. HECHO: los bytes se guardan con `persist_chatboo_session_file` y el chip se añade al último
   mensaje del asistente o se "escenifica" si el turno sigue en curso
   (`session_download.py:434-546`, `:878-918`).

### 2.2 Qué datos incluye cada formato

| Formato | Generador | Contenido | Evidencia |
|---|---|---|---|
| XLSX | `serialize_xlsx_sheets` → `formatters.format_excel_workbook` (openpyxl) → openpyxl propio → OOXML con `zipfile` | Filas "públicas" (claves que no empiezan por `_`) del resultado del turno, etiquetas `__column_labels__`, título `__title__`, leyenda `__sheet_caption__`; máx. 32 hojas, 20 000 filas, 256 columnas | HECHO `artifact_export.py:599-625`, `:1343-1415`, `:1513-1548`; `formatters.py:306-449` |
| PDF (sin Chatboo) | `formatters.format_data_as_pdf` (reportlab) | Mismas filas; **celdas imagen** (data-URI, base64 o `/web/image/<modelo>/<id>/<campo>`) se convierten en miniatura leyendo el registro con el `env` recibido; gráfico de barras/líneas si hay 3-24 categorías y series numéricas de escala similar | HECHO `formatters.py:537-597` (lectura `env[model].browse(id)[campo]` `:546-550`), `:720-864`; `artifact_export.py:787-856`, `:1593-1633` |
| Word (.doc = HTML de Office) | `_as_word_html` | Tabla con miniaturas o, con `__rich_doc__`, **el HTML del turno** quitando solo `<script>` y nodos de clases de gráfico | HECHO `artifact_export.py:1209-1340` |
| HTML | `_as_html` | Tabla escapada con `html.escape` | HECHO `:1187-1206` |
| Markdown / TXT | `_as_markdown`, `_as_tsv` | Tabla; tabuladores/saltos convertidos a espacio | HECHO `:1161-1184`, `:1889-1895` |
| SVG | `persist_inline_svgs_from_html` | El dibujo saneado | HECHO `svg_download.py:454-479` |
| Binarios de APIs | `safe_plan.py:1065-1144` | Archivo descargado por `fetch_url`/`api_call` (Caja B) | HECHO; ver [CAJAB] §6 |
| Icono Excel de la burbuja | `icon_xlsx_payload` | Matriz enviada por el cliente; se devuelve en base64, **no se guarda** | HECHO `artifact_export.py:1451-1460`; llamado desde `pns_ai_chatboo/controllers/chatboo.py:302` |

- INFERENCIA: el `env` de las exportaciones es el del motor (`self.env` en `agent_engine.py:4402`);
  si es el del usuario, la lectura de imágenes `/web/image/...` respeta sus permisos; si el motor
  corriera con otro usuario, podría incrustar imágenes que el usuario no ve. PENDIENTE confirmar el
  usuario del `env` del motor ([LLM] §8).
- INFERENCIA (riesgo medio): **inyección de fórmulas en Excel**. openpyxl trata como fórmula
  cualquier cadena que empiece por `=`. Las celdas de texto se escriben como `str(value)`
  (`formatters.py:424-425`; `artifact_export.py:1579-1584` vía `_excel_value` `:1654-1662`), así que
  un dato de Odoo como `=HYPERLINK(...)` se exportará como fórmula. Solo el respaldo OOXML con
  `inlineStr` (`:1746-1761`) es inmune. PENDIENTE probar con un contacto llamado `=1+1`.
- HECHO (código muerto): `format_data_as_html_table`/`_csv`/`_xml` (`formatters.py:25-290`)
  **no escapan** título, etiquetas ni valores, pero solo los envuelven métodos de
  `controllers/main.py:200-218` que nadie llama (Grep sin otras llamadas). Sin efecto hoy.

### 2.3 Dónde se guardan, a quién llegan y cuándo se borran

| Aspecto | Comportamiento | Evidencia |
|---|---|---|
| Almacén | `ir.attachment` creado con **`sudo()`**, `res_model='chatboo.session'`, `res_id=<sesión>`; filestore | HECHO `session_download.py:504-511` |
| Transacción | Se crea en un **cursor aparte con `commit` inmediato** (el adjunto persiste aunque el turno falle después) | HECHO `session_download.py:404-431`, `:525-526`; también el "stage" `:889-905` |
| Límite | 15 MB por archivo (ICP `pns_ai_chatboo.download_max_bytes`, 0 = sin límite) | HECHO `:24-25`, `:39-46`, `:444-457` |
| URL del chip | `/web/content/<id>/<nombre>?download=true&access_token=…`; SVG: `/pns_ai_mcp/session_file/<id>?access_token=…` | HECHO `:95-114`; token con `generate_access_token` del core (`odoo/addons/base/models/ir_attachment.py:631-640`) |
| Quién puede abrirlo | **Cualquiera que tenga la URL**, incluso sin sesión: con token válido el core lee el registro con `sudo` | HECHO core `odoo/addons/base/models/ir_http.py:298-322` (`consteq` y `record_sudo` `:313-315`); `session_file.py:18-56` (`auth='public'`, ver [MCP] §9) |
| Token hacia el LLM | En descargas binarias de Caja B, el metadato "para el LLM" incluye el chip con la **URL con `access_token`** | HECHO `session_download.py:549-569`, usado como `body` del paso (`safe_plan.py:1088,1138-1144`). INFERENCIA: ese `body` vuelve al proveedor LLM en el contexto ([LLM] §4) → la URL pública del archivo sale de Odoo. PENDIENTE confirmar |
| Aviso al cliente | `bus.bus`: en 14 no existe `_sendone`; usa `sendone((db,'res.partner',partner_id), json.dumps(payload))` al **socio del dueño de la sesión**; el mensaje solo lleva `type`, `action='message_received'`, `session_id` (sin datos del archivo); el cliente Chatboo parsea la cadena | HECHO `session_download.py:825-855`; core `addons/bus/models/bus.py:53-79` (sin `_sendone`), `:47-50` (GC de notificaciones a los 100 s); `pns_ai_chatboo/static/src/js/chatboo_component_v2.js:785-801` |
| Borrado | Al borrar la sesión: `chatboo.session.unlink` borra sus adjuntos (y el core también, `odoo/models.py:3492-3499`). La retención (`pns_ai_chatboo.history_retention_days`, 30 por defecto) **solo se ejecuta al crear una sesión nueva** y solo para las sesiones **del usuario que la crea** | HECHO `pns_ai_chatboo/models/chatboo_session.py:978`, `:981-1058`, `:1060-1079` |
| Sin sesión | Si no hay sesión de Chatboo, no se guarda nada (`no_session`) | HECHO `session_download.py:437-439` |

INFERENCIA: un usuario que deja de usar Chatboo conserva indefinidamente sus exportaciones (con
datos de negocio) en el filestore, accesibles por URL con token. No hay cron de purga de adjuntos
de sesión en este módulo (los crons de [MAPA] §7 no tocan `ir.attachment`).

---

## 3. Cliente web (JS `_v14`)

Se cargan **en todas las páginas del backend** vía `views/assets.xml:12-42` (hereda
`web.assets_backend`); la clave `assets` del manifest se ignora en 14 ([MAPA] §10.2).
`static/src/xml/mcp_field_widgets.xml` son plantillas OWL 2 para 17+ y no se cargan en 14 (HECHO
`:2`, sin clave `qweb` en `__manifest__.py`).

### 3.1 Widgets de campo

| Widget (registro) | Archivo | Qué hace | Dónde se usa | Riesgo |
|---|---|---|---|---|
| `mcp_api_key_display` | `mcp_api_key_widget_v14.js` (75 l.) | Muestra la clave en claro y botón copiar con `navigator.clipboard` | `views/mcp_api_key_wizard_views.xml:39` | Texto con `text:` (sin XSS). INFERENCIA: `navigator.clipboard` no existe fuera de HTTPS/localhost → el botón lanza `TypeError` (no hay `catch` síncrono, `:41`). PENDIENTE en el VPS si va por HTTP |
| `pns_html_readonly` | `pns_html_readonly_widget_v14.js` (19 l.) | `this.$el.html(this.value)` **sin sanear** | `context_stats_wizard_views.xml:16` (`stats_html`), `bundle_cache_rebuild_wizard_views.xml:9` y `json_export_wizard_views.xml:9` (`result_html`) | Ver §5 |
| `mcp_iso_datetime` | `mcp_iso_datetime_widget_v14.js` (47 l.) | Fecha en ISO UTC monoespaciada | (Grep: no se usa en vistas del módulo) | Ninguno |
| `mcp_json_compressed` | `mcp_json_compressed_widget_v14.js` (393 l.) | JSON en una línea; al pulsar hace `read` del campo original (`prompt_data`, `result_data`…) y lo muestra con `.text()`; copiar con `execCommand('copy')` | `mcp_log_views.xml:32,77,78` | Sin XSS (`.text()` `:274`). Lectura por ORM con ACL del usuario (`:231-235`, `:304-308`) |
| `context_window_combo` | `context_window_combo_v14.js` (86 l.) | `<select>` de tamaños de ventana de contexto | `ai_provider_views.xml:48` | Ninguno |

### 3.2 Los 9 `ListController.include`

Todos sobrescriben `renderButtons`, llaman primero a `_super` y **salen sin hacer nada si
`this.modelName` no es el suyo**; para su modelo añaden un botón "Tools" que abre un asistente con
`do_action(<XML ID>)`. Las acciones existen (Grep en `wizard/*_views.xml`, línea entre paréntesis).

| # | Archivo | Modelo | Acción abierta | Extra |
|---|---|---|---|---|
| 1 | `safe_operation_tree_v14.js:10-37` | `ai.safe.operation` | `action_safe_operation_tools_wizard` (`safe_operation_tools_wizard_views.xml:27`) | — |
| 2 | `ai_agent_tree_v14.js:11-38` | `ai.agent` | `action_agent_tools_wizard` (`ai_agent_tools_wizard_views.xml:24`) | — |
| 3 | `external_server_tree_v14.js:10-37` | `ai.api.server` | `action_external_server_tools_wizard` (`:24`) | — |
| 4 | `ai_provider_tree_v14.js:10-37` | `ai.provider` | `action_provider_tools_wizard` (`:24`) | — |
| 5 | `mcp_user_tree_v14.js:12-59` | `ai.mcp.user` | `action_user_tools_wizard` (`:24`) | Define `_onToggleBoolean` (recarga al cambiar `is_mcp_manager`): **ese método no existe en el `ListController` de 14** ni lo dispara ningún evento (Grep en `web/static/src/js` sin resultados) → código muerto (HECHO) |
| 6 | `mcp_context_tree_v14.js:13-42` | `ai.context` | `action_mcp_context_tools_wizard` (`:33`) | `console.log` de depuración en cada render (`:26`) |
| 7 | `mcp_skill_tree_v14.js:12-39` | `ai.skill` | `action_ai_skill_tools_wizard` (`skill_tools_wizard_views.xml:31`) | — |
| 8 | `mcp_log_tree_v14.js:8-108` | `ai.log` | `action_log_tools_wizard` (`:24`) y `action_mcp_logs_delete_menu_window` (`mcp_log_views.xml:8`) | Inserta la leyenda de colores en el panel de control llamando por RPC a `ai.log.render_flow_legend('grid')` (`:93-102`); HTML estático del servidor (`models/ai_log.py:435-477`) |
| 9 | `whitelist_tree_v14.js:10-37` | `ai.url.whitelist` | `action_whitelist_tools_wizard` (`:24`) | — |

¿Afectan a listas no PNS? HECHO: no cambian nada visible; el `renderButtons` del core
(`web/static/src/js/views/list/list_controller.js:158-179`) se ejecuta igual y después se
comprueba el modelo. Coste: nueve envoltorios encadenados en cada lista (también en los diálogos
de búsqueda que usan `ListController`). INFERENCIA: despreciable.

### 3.3 `ActionManager.include` (`mcp_log_tree_v14.js:111-187`)

- Intercepta `_executeClientAction` para **todas** las acciones cliente y, si la acción es
  `display_notification` con `params.next.tag === 'reload'` (de **cualquier módulo**), programa
  temporizadores para cerrar el último diálogo y recargar los controladores de `ai.log`.
- HECHO (core 14): `display_notification` es una función que devuelve `next`, y el core ya ejecuta
  `doAction(next)` (`web/static/src/js/core/misc.js:190-201`;
  `chrome/action_manager.js:419-433`); `reload` recarga la página entera.
- HECHO: el código usa `self._dialogs` y `self._controllers`, que **no existen** en el
  ActionManager de 14 (allí son `currentDialogController` y `controllers`,
  `action_manager.js:59-61,452`); y `getCurrentController()` devuelve el descriptor
  (`{widget, …}`, `:205-208`) que no tiene `modelName`. **Todo el bloque es inerte en 14**: solo
  añade dos `setTimeout` vacíos a esas notificaciones. No rompe acciones ajenas.

### 3.4 Otros parches globales

| Parche | Alcance | Efecto | Evidencia |
|---|---|---|---|
| `FormRenderer.include` (`mcp_log_form_v14.js:10-112`) | **Todos los formularios** | Tras cada render busca `.o_field_text_copy_btn`; si existe, enlaza "copiar al portapapeles" (`execCommand('copy')`). Solo actúa en formularios con ese botón (`mcp_log_views.xml:173-206` y asistente de importación de usuarios) | HECHO; `_render` del core es `async` (`views/abstract_renderer.js:140-143`), el `then` se aplica. Coste: un `find` por render |
| `ai_agent_origin_filter_v14.js` (355 l.) | **Toda la página** | 1) `document.addEventListener('click', …, true)` en fase de captura (`:303-346`); solo intercepta clics en botones `.o_pns_origin_filter` o en la cabecera `composition_origin` dentro de un formulario con `.o_pns_origin_filter_bar` (`ai_agent_views.xml:77,117`). 2) `MutationObserver` sobre `document.documentElement` con `subtree:true` (`:348-352`) que, 50 ms después de **cualquier** cambio del DOM, recorre todos los `.o_form_view`. 3) Guarda filtros/orden en `sessionStorage` | HECHO. INFERENCIA: sin efecto funcional fuera del agente, pero coste constante en todo el backend; reordena filas de la x2many **solo en el DOM** (no en el servidor) |
| CSS `mcp_context.css:114-116` | Todos los formularios | `.o_form_view .o_field_x2many { overflow-anchor: none; }` cambia el anclaje de scroll en **todas** las x2many | HECHO; INFERENCIA impacto visual mínimo |
| CSS restante | Ámbito propio | Clases `o_mcp_*`, `o_pns_*`; `mcp_context_list.css` apunta a 17+/19 (inerte en 14); `field[name="content"] textarea` no casa con nada en el DOM | HECHO (5 archivos leídos) |

### 3.5 Rutas del servidor que llama el JS de este módulo

Solo RPC estándar (`/web/dataset/call_kw`): `ai.log.render_flow_legend` (`@api.model`, sin datos de
usuario, `models/ai_log.py:447-477`) y `read` del registro mostrado (`mcp_json_compressed`). No
llama rutas propias (`/mcp`, `/pns_ai_mcp/*` las usa el JS de Chatboo, [MCP] §9). El resto son
`do_action` de XML IDs.

---

## 4. Librerías incluidas

| Archivo | Librería | Versión | ¿La usa este módulo? | Notas |
|---|---|---|---|---|
| `static/src/js/showdown.js` | Showdown (Markdown → HTML) | 2.1.0 (21-04-2022) — HECHO `:1` | No (Grep); la usa `pns_ai_chatboo` | Showdown **no sanea**: deja pasar HTML crudo (INFERENCIA por la documentación de la librería) |
| `static/src/js/showdown.min.js` | Showdown minificado | 2.1.0 — HECHO (cabecera) | No se carga (no está en `assets.xml`) | Archivo sobrante |
| `static/src/js/jspdf.umd.min.js` | jsPDF | 2.5.1 — HECHO (`version="2.5.1"`) | No; la usa Chatboo | Afectada por CVE-2025-29907 (<3.0.1) y CVE-2025-57810 (<3.0.2), DoS con `addImage` |
| `static/src/js/xlsx.full.min.js` | SheetJS Community | 0.18.5 — HECHO (`.version="0.18.5"`) | No; la usa Chatboo | Afectada por CVE-2023-30533 (contaminación de prototipo al **leer** archivos, <0.19.3) y CVE-2024-22363 (ReDoS, <0.20.2) |

- HECHO: `pns_ai_chatboo/views/assets.xml:13-18` carga **otra copia** de showdown 2.1.0, jsPDF
  y SheetJS en el mismo bundle → las tres librerías van **dos veces** en `web.assets_backend`.
  INFERENCIA: más peso de descarga en cada carga del backend; la segunda definición de
  `window.showdown`/`jspdf`/`XLSX` sustituye a la primera (misma versión en showdown; PENDIENTE
  comparar versiones de jsPDF/SheetJS de Chatboo).
- INFERENCIA: las CVE de jsPDF/SheetJS solo son explotables si el cliente procesa imágenes o
  archivos controlados por terceros; aquí generan archivos a partir de datos del chat. Riesgo bajo,
  pero son versiones desactualizadas incluidas a mano (sin gestor de dependencias).

---

## 5. HTML y Markdown generados por el LLM: ¿se sanean? (XSS)

Conclusión: **no hay saneado de la respuesta del LLM antes de pintarla**, ni en este bloque ni en
la ruta de Chatboo. Ya establecido en [CODE] §6b.1 (no hay `html_sanitize`, `bleach` ni DOMPurify);
este bloque lo confirma para la prosa Markdown y añade los puntos propios.

| Vía | ¿Saneo? | Evidencia | Riesgo |
|---|---|---|---|
| Prosa Markdown del LLM → Chatboo | **No**. `formatMarkdown` pasa el texto por Showdown sin filtro y devuelve el HTML; se inserta con `innerHTML` ([CODE] §6b.1: `chatboo_formatters.js:553,671,746`) | HECHO `pns_ai_chatboo/static/src/js/chatboo_formatters.js:283-314`; solo el respaldo sin Showdown escapa (`:320-321`) | **Alto (INFERENCIA)**: si el LLM devuelve `<img src=x onerror=…>` o un enlace `javascript:` —p. ej. por *prompt injection* desde un dato de Odoo leído en el turno ([LLM] §6)— se ejecuta en la sesión del usuario |
| `formatted_text` / `author_html` (skills) | No | [CODE] §6b.1 | Alto (ya documentado) |
| Celda base64 y `href` de mapas en tablas del servidor | Parcial | [CODE] §6b.1 (`relaxaicode_render.py:897`, `:649,657,672,692`) | Alto (ya documentado). La cesta re-renderiza con ese mismo renderer (`turn_presentation_basket.py:209-243`) |
| `record_linkify` | No escapa la etiqueta ni el modelo | HECHO `record_linkify.py:30-31,92` | Bajo: solo reutiliza texto que ya estaba en la prosa y refs del servidor; no añade un vector nuevo |
| `report_outline_guard` | No | HECHO `:148-168` (inserta encabezados/cierre de la skill tal cual) | Igual que `author_html`: contenido del autor de la skill |
| SVG extraídos (`sanitize_svg`) | **Lista negra por regex**: quita `<script>`, `<foreignObject>`, atributos `on*` y `href="javascript:"` entre comillas | HECHO `svg_download.py:41-48`, `:230-254` | Medio-bajo. INFERENCIA: eludible (p. ej. `href` con entidades `&#106;avascript:`, `<animate>/<set>` sobre `href`). Mitigado al abrirlo por `/pns_ai_mcp/session_file`, que responde `image/svg+xml` → el core añade `Content-Security-Policy: default-src 'none'` (`odoo/http.py:1461-1474`) y `nosniff` (`session_file.py:50-55`). **No mitigado** para los SVG que **se quedan en la burbuja** (< 400 caracteres, decorativos o más de 5 por turno, `svg_download.py:275-281,350-361`), que llegan al `innerHTML` de Chatboo |
| Widget `pns_html_readonly` | No (`$el.html`) | HECHO `pns_html_readonly_widget_v14.js:11-13`; campos `Html(sanitize=False)`: `context_stats_wizard.py:33`, `pns_base/models/operation_report_wizard.py:36` | Bajo-medio: `stats_html` interpola **sin escapar** el nombre del agente, códigos de contexto y el texto de error (`context_stats_wizard.py:120-123,246,309-313,349-355`); quien pueda nombrar un agente/contexto podría inyectar HTML que ve otro administrador. `result_html` ya analizado en [BASE] §4 obs. 2 |
| Exportación HTML / tarjeta de archivo | Sí (`html.escape`) | HECHO `artifact_export.py:985-1008,1187-1206` | Ninguno |
| Exportación Word con `__rich_doc__` | Solo quita `<script>` | HECHO `artifact_export.py:1220,1274-1278` | Bajo (se abre en Word, no en el navegador) |
| Leyenda de `ai.log`, JSON comprimido, API key, fecha ISO | HTML estático o `.text()` | HECHO (ver §3) | Ninguno |

---

## 6. Tests

### 6.1 Inventario

Etiquetas: todas las clases Odoo usan `@tagged('post_install', '-at_install', 'pns_ai_mcp')`; la
de intrusión añade `pns_intrusion`. Helpers en `tests/_helpers.py` (240 l.).

| Archivo (líneas) | Clase / tipo | Bloque | Qué cubre | ¿Se ejecuta en 14? |
|---|---|---|---|---|
| `test_bundle_locale.py` (245) | `TransactionCase` | 2 | Resolución de locale y deduplicación de contextos, contextos `core` transversales, códigos de agentes en importación, `@module` pull, estadísticas de composición, contextos de nómina (se salta si no están) | Sí |
| `test_agent_context_inheritance.py` (57) | `TransactionCase` | 2 | Contextos efectivos propios por agente (sin herencia) | Sí |
| `test_knowledge_ownership.py` (157) | `TransactionCase` | 2 | Contexto privado no entra en el prompt de otro, escritor no edita contextos de módulo, visibilidad de skills, escritor no exporta/importa | **Se salta** si no existe `base.user_demo` (`:29-31`) — PENDIENTE: ¿la BD de `odoo-dev 14 tests` tiene datos demo? |
| `test_context_unlink.py` (106) | `TransactionCase` | 2 | No se borran contextos `core` ni de fábrica; sí los propios y restos | Igual: se salta sin `user_demo` (`:24-26`) |
| `test_required_context_pin.py` (59) | `TransactionCase` | 2 | `required_context_codes` sobreviven a limpiar la lista | Sí |
| `test_identity_pack_isolation.py` (73) | `TransactionCase` | 2 | Packs `self_*` ajenos excluidos | Sí |
| `test_factory_defaults_keep.py` (93) | `TransactionCase` | 2 | Restaurar valores de fábrica conserva enlaces extra; la semilla no nombra módulos ajenos | Sí |
| `test_knowledge_composition.py` (258) | `TransactionCase` | 2 | Tokens de origen (`native/imported/pinned/extra`), orden, filtros `link_show_*` | Sí (algunos se saltan sin Chatboo) |
| `test_context_type_tokens.py` (21) | `TransactionCase` | 2 | Etiquetas de `context_type` | Sí |
| `test_mcp_agent.py` (156) | `TransactionCase` | 2/3/7 | Resolución de agentes endpoint/inferencia, borrado prohibido de agentes de módulo, acciones de ajustes, proveedores sin rol admin, **la API key del proveedor no es legible por un usuario normal** | Sí. PENDIENTE: requiere el agente Chatboo y al menos un `ai.provider` (falla con `assertTrue`, no se salta, `:119-122,141`) |
| `test_mcp_http.py` (137) | `HttpCase` | 4 | `initialize`, `tools/call system://info`, `server/discover` y `tools/list` sin estado | Sí. **Hace `commit` real** (ver 6.3) |
| `test_relaxaicode_imports.py` (65) | `TransactionCase` | 6 | Validación AST de imports de red y `guarded_import` | Sí |
| `test_relaxaicode_sandbox_escapes_e2e.py` (205) | `TransactionCase` | 6 | 18 cargas de fuga del sandbox y escrituras ofuscadas | **Se salta** si el nombre de la BD no contiene `test`/`prueba` y no está `PNS_ALLOW_INTRUSION_TESTS=1` (`_helpers.py:46-67`). PENDIENTE: nombre de la BD de tests de `odoo-dev` |
| `test_relaxaicode_render_locale.py` (294) | `TransactionCase` | 6/8 | Separadores por idioma, varias tablas, enlaces de nombre | Sí (se salta si falta `es_ES`) |
| `test_relaxaicode_model_stamp.py` (231) | `TransactionCase` | 6 | Asignación de `__model` a filas | INFERENCIA: **error** (no salto) en `test_stamp_both_sibling_lists_with_env` si `product` no está instalado (`self.env['product.product']` `:74` → `KeyError`; `product` no está en `depends`); `test_related_models_from_product_id` espera `product.product` desde `sale.order.line` (`:63-71`). PENDIENTE |
| `test_friendly_skill_error.py` (53) | `TransactionCase` | 6 | Mensajes de error de skills | Sí |
| `test_safe_plan_atomicity.py` (188) | `TransactionCase` con cursores propios | 5 | `executed` no se marca si falla el commit final; cancelación sin repetición | Sí. **Commits reales** con limpieza manual |
| `test_system_action.py` (447) | `TransactionCase` | 5 | Acciones de sistema (vistas heredadas `required`, módulos, grupos), validación de Safe Plan por grupo | Sí. Limpieza con commits reales (`:429-447`) |
| `test_chatboo_pending_cards.py` (79) | `TransactionCase` | 5 | Tarjetas pendientes por usuario, expiradas | Sí |
| `test_change_journal_menu.py` (42) | `TransactionCase` | 1/5 | Menú "Changes" oculto a escritores | Sí |
| `test_presentation_mode.py` (34) | **`unittest.TestCase`** | 8 | `normalize_show_mode`, pista "gráfico", atributo `data-chatboo-show-mode` | **No**: importado (`__init__.py:21`) pero sin `test_tags`; el cargador de 14 lo descarta (`odoo/tests/loader.py:79-86`, `odoo/tests/common.py:2658-2660`) |
| `test_change_journal.py` (131) | `TransactionCase` | 3/5 | Diario de cambios: secuencia, reversión, no registra planes cancelados, registra fallos fuera del rollback | **No**: no está en `tests/__init__.py` |
| `test_session_download.py` (94) | **`unittest.TestCase`** | 8 | Funciones puras de descargas | **No**: ni importado ni etiquetado |

`tests/__pycache__/*.cpython-312.pyc`: restos de una ejecución con Python 3.12 (HECHO, nombres);
no afectan. Los tests citan una suite de host (`unit_tests/`, `./t.sh`, `smoke_mcp_http.sh`) que
**no viaja en el repositorio** (HECHO, Glob vacío).

### 6.2 Cobertura por bloque (qué queda sin cubrir)

| Bloque | Cubierto | Sin cubrir (relevante para riesgos ya documentados) |
|---|---|---|
| 2 Conocimiento | Bien: composición, locale, propiedad (si hay `user_demo`), fábrica, bloqueo de borrado | Sincronización en cada arranque (`_register_hook`, [CONOC] §5), import/export ZIP, reconstrucción de caché, `skip_hardcoded_restrictions` ([CONOC] §4) |
| 3 Conexiones y secretos | Solo que un usuario normal no lee `api_key` del proveedor (`test_mcp_agent.py:136-156`); diario de cambios **no se ejecuta** | Servidores externos y credenciales por usuario, lista blanca, cachés, copias de configuración, logs y su purga, coste/consumo |
| 4 Servidor MCP | Camino feliz de 4 métodos JSON-RPC con clave válida | Rechazo sin clave o con clave inválida, `cors='*'`/`csrf=False`, SSE, `session_file` (token, otros adjuntos), rutas `verification_ui`/`choice_ui` ([MCP] §3-§9) |
| 5 Caja B | Atomicidad, acciones de sistema, permisos por grupo para `field_required`, tarjetas | PIN, cron `cleanup_expired`, `fetch_url`/`api_call` y descargas binarias, vías de salto de la Caja B ([CAJAB] §3) |
| 6 Ejecución de código | Imports de red, fugas del sandbox (**solo en BD "test"**), render y locale, `__model` | XSS de celda base64/`href` y `author_html` ([CODE] §6b.1), smoke-run de skills al guardar ([CODE] §6), `untrusted_html_contract`, recetas en 3.7 |
| 7 Motor LLM | Solo resolución de agentes/proveedores | Bucle ReAct, drivers HTTP, timeouts/failover, datos enviados al proveedor, *prompt injection* ([LLM] §1-§6) |
| 8 Presentación/exportación/JS | Nada efectivo (los dos tests son `unittest.TestCase` y no corren) | Todas las utilidades de §1, exportaciones y saneado SVG, inyección de fórmulas, todo el JS (no hay tests QUnit/tour) |

### 6.3 Tests con efectos fuera del rollback

- HECHO: `setup_http_mcp_fixtures` en 14 escribe el **hash de una API key MCP predecible**
  (`pns-http-test-<nombre_bd>`) en el `ai.mcp.user` del **administrador** y hace `env.cr.commit()`
  sobre el cursor del test (`_helpers.py:143-162`, `:173-201`). En 14 no hay protección contra
  `commit` en tests (core `odoo/tests/common.py` sin bloqueo; Grep). INFERENCIA: en la BD
  efímera de `odoo-dev 14 tests` no importa; **si alguien ejecuta los tests sobre una copia de
  producción en el VPS, el admin queda con una clave MCP conocida y activa**.
- HECHO: `test_safe_plan_atomicity` y la limpieza de `test_system_action` hacen commits reales y
  borran lo que crean (`test_safe_plan_atomicity.py:59,62-67`; `test_system_action.py:429-447`).
  Un fallo a mitad puede dejar contactos `pns-atomicity-*` u operaciones de prueba.

---

## 7. Compatibilidad con Odoo 14 y Python 3.7.3

### 7.1 Python 3.7.3

- HECHO: sin sintaxis posterior a 3.7 en los archivos del bloque. `from __future__ import
  annotations` (≥ 3.7) en `primary_artifact.py:12`, `record_*.py`, `report_outline_guard.py:10`,
  `response_anti_echo.py:13`, `turn_presentation_basket.py:9`, `svg_download.py:9`,
  `verification_ack_records.py:9`, `artifact_export.py:10`, `field_selection.py:10`,
  `session_file.py:5`. La anotación `set | None` (`response_anti_echo.py:119`) solo es válida
  gracias a ese import (no se evalúa).
- HECHO: `ET.indent` (3.9) está protegido con `try/except AttributeError` (`formatters.py:283-287`).
- HECHO: dependencias Python `openpyxl` y `reportlab` declaradas
  (`__manifest__.py:33`); si faltan, XLSX cae al OOXML propio (`artifact_export.py:1404-1414`)
  y PDF lanza excepción (`formatters.py:861-862`). PENDIENTE `odoo-dev 14 paridad` en el VPS.

### 7.2 Odoo 14 (cliente web legacy)

| Punto | Estado | Evidencia |
|---|---|---|
| `odoo.define`, `AbstractField`, `field_registry`, `ListController`, `FormRenderer`, `ActionManager` | Correctos para el cliente legacy de 14 | core `web/static/src/js/...` citado en §3 |
| ES6 (`const`, destructuring, comas finales en llamadas) | Funciona en navegadores actuales; Odoo 14 no transpila | `mcp_context_tree_v14.js:10-11`, `ai_agent_origin_filter_v14.js:82-84` |
| `ListController._onToggleBoolean` | No existe en 14 → código muerto | §3.2 |
| `ActionManager._dialogs/_controllers` | No existen en 14 → bloque inerte | §3.3 |
| `bus.bus._sendone` | No existe en 14; usa `sendone` legacy correctamente | §2.3 |
| `fields.Field._description_selection(env)`, `generate_access_token`, `new_test_user`, `set_csp` | Existen en 14 | `odoo/fields.py:2390`; `ir_attachment.py:631`; `tests/common.py:106`; `http.py:1461` |
| Tests `unittest.TestCase` | No se ejecutan en 14 | §6.1 |
| `mcp_field_widgets.xml`, `mcp_context_list.css` | Pensados para 17+; inertes en 14 | §3 |

### 7.3 Riesgos del bloque (de mayor a menor)

1. **XSS por la prosa Markdown del LLM** (Showdown sin saneo + `innerHTML`), alcanzable por
   *prompt injection* desde datos de Odoo (INFERENCIA, §5).
2. **Archivos exportados accesibles por URL pública con token**, guardados con `sudo` y commit
   inmediato, sin purga salvo borrado de la sesión o retención disparada al crear otra sesión; en
   descargas de Caja B la URL con token se devuelve al LLM (HECHO/INFERENCIA, §2.3).
3. **Inyección de fórmulas** en XLSX generados con openpyxl (INFERENCIA, §2.2).
4. **Tests que dejan una API key conocida** si se ejecutan sobre una BD real (HECHO, §6.3).
5. Cobertura de tests casi nula para los riesgos de seguridad documentados en los bloques 4-7 y
   nula para el bloque 8; tests de intrusión que se saltan según el nombre de la BD (§6).
6. Librerías JS desactualizadas con CVE conocidas y **cargadas dos veces** (§4).
7. Saneado SVG por lista negra; mitigado por CSP solo fuera de la burbuja (§5).
8. HTML sin escapar en `stats_html` (nombres de agentes/contextos) (§5).
9. Coste global del JS: `MutationObserver` de todo el documento, oyente de clics en captura,
   `FormRenderer` en todos los formularios; rendimiento de exportación Word (recarga de módulos por
   celda) (§1, §3.4).

---

## Resumen del bloque

- Las 11 utilidades de presentación **reescriben la salida del LLM** antes de guardarla: fijan el
  primer artefacto del turno, fusionan varios resultados (re-render en servidor), reinyectan
  tablas olvidadas, quitan tablas repetidas, añaden enlaces `/web#id=` y encabezados de informe,
  extraen SVG a archivos. Son funciones puras; solo `presentation_mode` (show mode de la sesión) y
  `svg_download`/`session_download` (adjuntos) tocan la BD.
- **XSS**: no hay saneado de la respuesta del LLM. La prosa Markdown pasa por Showdown 2.1.0 sin
  filtro y se inserta con `innerHTML` en Chatboo (`chatboo_formatters.js:283-314`); se suma a lo ya
  documentado en [CODE] §6b.1. El saneado de SVG es por regex y solo lo protege la CSP del core
  cuando se abre por `/pns_ai_mcp/session_file`. `pns_html_readonly` pinta `Html(sanitize=False)`
  con valores sin escapar (`context_stats_wizard.py`).
- **Exportaciones**: filas públicas del turno → XLSX/MD/TXT en servidor (PDF/Word/HTML los monta
  el cliente Chatboo). `ir.attachment` de `chatboo.session` (`sudo`, commit inmediato, 15 MB),
  descargable por URL con `access_token` **sin sesión**; solo se borra con la sesión (retención de
  30 días disparada al crear otra sesión). Bus: solo id de sesión al dueño. Riesgos: fórmulas en
  Excel (openpyxl) y URL con token devuelta al LLM en descargas de Caja B.
- **JS**: 5 widgets; 9 `ListController.include` sin efecto en listas no PNS; `ActionManager.include`
  sobre todas las `display_notification` con `next=reload`, **inerte en 14**; `FormRenderer.include`
  en todos los formularios; oyente global de clics y `MutationObserver` de todo el DOM (filtro de
  origen). Código muerto: `_onToggleBoolean`. Solo RPC estándar (`render_flow_legend`, `read`).
- **Librerías**: showdown 2.1.0, jsPDF 2.5.1 (CVE-2025-29907, CVE-2025-57810), SheetJS 0.18.5
  (CVE-2023-30533, CVE-2024-22363); este módulo no las usa y Chatboo vuelve a cargarlas.
- **Tests**: 23 archivos; 21 importados. **No se ejecutan**: `test_change_journal` y
  `test_session_download` (no importados) y `test_presentation_mode` (importado pero
  `unittest.TestCase` sin etiquetas, descartado por el cargador de 14). Se saltan según el entorno:
  propiedad y borrado de contextos (sin `user_demo`), intrusión del sandbox (BD sin "test" en el
  nombre). Posibles errores: `test_relaxaicode_model_stamp` sin `product`, `test_mcp_agent` sin
  proveedor. `test_mcp_http` hace commit de una API key MCP predecible para el admin.
- **Cobertura**: buena en conocimiento (bloque 2); mínima en servidor MCP, Caja B y sandbox (solo
  caminos felices y algunos permisos); nula en motor LLM (7) y presentación (8); ningún test de
  XSS, autenticación negativa, PIN, `session_file` ni JS.
- **Compatibilidad**: Python 3.7.3 sin problemas en estos archivos; cliente legacy de 14 correcto
  salvo los dos fragmentos inertes; plantillas OWL y CSS de 17+ sin efecto.

## Tabla de cobertura

| Archivo | Líneas | Leído entero |
|---|---|---|
| `utils/presentation_mode.py` | 363 | sí |
| `utils/primary_artifact.py` | 258 | sí |
| `utils/record_cite.py` | 141 | sí |
| `utils/record_delivery_gate.py` | 255 | sí |
| `utils/record_linkify.py` | 112 | sí |
| `utils/report_outline_guard.py` | 170 | sí |
| `utils/response_anti_echo.py` | 159 | sí |
| `utils/turn_presentation_basket.py` | 243 | sí |
| `utils/svg_download.py` | 479 | sí |
| `utils/verification_ack_records.py` | 91 | sí |
| `utils/artifact_export.py` | 1918 | sí (2 tramos) |
| `utils/session_download.py` | 918 | sí |
| `utils/field_selection.py` | 100 | sí |
| `controllers/formatters.py` | 865 | sí |
| `static/src/js/*_v14.js` (16 archivos) | 19-393 | sí, todos |
| `static/src/js/showdown.js`, `showdown.min.js`, `jspdf.umd.min.js`, `xlsx.full.min.js` | — | **no** (por instrucción: solo cabecera/versión) |
| `static/src/css/*.css` (5 archivos) | 16-316 | sí, todos |
| `static/src/xml/mcp_field_widgets.xml` | 53 | sí |
| `views/assets.xml`, `__manifest__.py` | 46 / 135 | sí |
| `tests/*.py` (24 archivos incl. `__init__` y `_helpers`) | 21-447 | sí, todos |
| `tests/__pycache__/*.pyc` | — | no (binarios) |
| Apoyo: `controllers/session_file.py` | 56 | sí |
| Apoyo: `wizard/context_stats_wizard.py` | — | parcial (`:91-370`) |
| Apoyo: `wizard/bundle_cache_rebuild_wizard.py`, `context_stats_wizard_views.xml` | 40 / 34 | sí |
| Apoyo: `agent_engine.py`, `ai_log.py`, `chatboo_session.py`, `chatboo_formatters.js` | — | parcial (líneas citadas) |

## Preguntas abiertas

1. ¿La BD que crea `odoo-dev 14 tests` tiene datos demo (`base.user_demo`) y un nombre con
   "test"? Si no, `test_knowledge_ownership`, `test_context_unlink` y el test de intrusión del
   sandbox se saltan siempre. PENDIENTE: `odoo-dev 14 tests pns_ai_mcp` y revisar los "skipped".
2. ¿Fallan `test_relaxaicode_model_stamp` (sin `product`/`sale`) y `test_mcp_agent` (sin
   `ai.provider` ni agente Chatboo) en una BD con solo `pns_ai_mcp`? PENDIENTE en `odoo-dev`.
3. ¿Se van a ejecutar alguna vez los tests sobre una copia de producción en el VPS? Si es así,
   `test_mcp_http` dejará al administrador con una API key MCP conocida y activa.
4. ¿Se aceptan como riesgo los archivos exportados accesibles por URL con token sin autenticar y
   sin caducidad, o se requiere una política de retención/purga para los adjuntos de
   `chatboo.session`?
5. ¿El `body` de las descargas binarias de Caja B (con la URL y su `access_token`) se envía al
   proveedor LLM? PENDIENTE: trazar en `agent_engine.py` qué parte de `safe_plan_steps` entra en
   el prompt ([LLM] §4).
6. ¿Con qué usuario corre el `env` del motor al exportar (lectura de imágenes `/web/image/...` en
   PDF/Word)? ¿El del usuario del chat o uno técnico? ([LLM] §8).
7. ¿Se confirma la inyección de fórmulas en XLSX? PENDIENTE: exportar a Excel un listado con un
   contacto llamado `=1+1` y abrirlo.
8. ¿Se confirma el XSS por Markdown? PENDIENTE (solo en local): pedir al chat que repita
   literalmente `<img src=x onerror=console.log(1)>` y ver si se ejecuta en la burbuja.
9. ¿Qué versiones de jsPDF y SheetJS incluye `pns_ai_chatboo` y cuál prevalece al cargarse ambas
   copias? ¿Hay intención de actualizar estas librerías?
10. ¿El VPS sirve Odoo por HTTPS? Si no, el botón copiar del widget de API key (`navigator.clipboard`)
    fallará.
11. ¿Las reglas de acceso de `chatboo.session` impiden que un usuario lea adjuntos de sesiones
    ajenas por `/web/content/<id>` **sin** token? (Fuera de este módulo; PENDIENTE al analizar
    `pns_ai_chatboo`.)

Fuentes externas (versiones afectadas de las CVE):
[CVE-2025-57810 (osv.dev)](https://osv.dev/vulnerability/CVE-2025-57810),
[CVE-2025-29907 (Mend)](https://mend.io/vulnerability-database/CVE-2025-29907),
[CVE-2023-30533 (cvefeed)](https://cvefeed.io/vuln/detail/CVE-2023-30533),
[CVE-2024-22363 (cvefeed)](https://cvefeed.io/vuln/detail/CVE-2024-22363).
