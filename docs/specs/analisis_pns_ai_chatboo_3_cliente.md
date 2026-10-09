# Análisis pns_ai_chatboo — Bloque C3: resto del cliente web (Odoo 14)

- Rama: `14.0-analisis-pns-ai`. Versión de Odoo: 14.0 (`CLAUDE.md` del repo).
- Alcance: `pns_ai_chatboo/static/src/js/` salvo `chatboo_component_v2.js`, `chatboo_formatters.js`,
  `chatboo_sse.js` y librerías; `static/src/xml/`; `static/src/css/`. Código de terceros: solo se
  describe, no se diseña ni se propone código.
- Convención: **HECHO** (archivo:línea), **INFERENCIA** (deducción razonada, sin prueba en
  ejecución), **PENDIENTE** (requiere comprobación en ejecución o información externa).
- Documentos relacionados: [COMP] = `analisis_pns_ai_chatboo_2_componente.md`,
  [SRV] = `analisis_pns_ai_chatboo_1_servidor.md`. Rutas sin prefijo = `pns_ai_chatboo/static/src/`.

## 1. Carga y mapa de archivos

### 1.1 Cómo se cargan (HECHO)

- Todo va en `web.assets_backend` mediante plantilla heredada (`pns_ai_chatboo/views/assets.xml:4-34`),
  en este orden: 3 CSS (6-8), `chatboo_sse.js`, `chatboo_screen_context.js`,
  `chatboo_choice_list.js` (10-12), librerías `showdown`, `jspdf`, `jspdf.plugin.autotable`,
  `html2canvas`, `xlsx.full`, `chart.umd`, `echarts` (14-20), después `chatboo_dashboard.js`,
  `chatboo_card_width.js`, `chatboo_charts.js`, `chatboo_svg_cards.js`, `chatboo_tts.js`,
  `chatboo_formatters.js`, `chatboo_export.js`, `chatboo_context_stats.js`, el componente y
  `chatboo_systray.js` (21-32).
- La plantilla QWeb de cliente se declara en la clave `qweb` del manifest
  (`pns_ai_chatboo/__manifest__.py:43-45`), patrón correcto en Odoo 14.
- Consecuencia: **todo el JS y CSS se descarga en el backend de cualquier usuario interno**, tenga
  o no acceso a Chatboo (incluidas ~7 librerías grandes). Solo el icono del systray depende de
  `/chatboo/check_health` (HECHO `chatboo_systray.js:28,32-50`).

### 1.2 Tabla por archivo

| Archivo | Qué hace | Dónde se engancha | Rutas de servidor / salidas de red |
|---|---|---|---|
| `js/chatboo_export.js` (`odoo.define('pns_ai_chatboo.export')`, 1) | Copiar al portapapeles, descargar PDF, Excel y Word de una respuesta; generar y subir documentos "pendientes" de la sesión | `require` desde el componente (`chatboo_component_v2.js:8`, envoltorios `:5308-5396`) | `/chatboo/export/xlsx` (2989-2995); `/chatboo/sessions/fulfill_export` (3643-3652); carga de imágenes de celdas por URL (`loadImgDataUrl` 1532-1552) |
| `js/chatboo_charts.js` (IIFE, global `ChatbooCharts` 2500-2520) | Lee el JSON `data-chatboo-dataset` de las tablas y monta barra de herramientas + gráfico Chart.js o ECharts + tabla de estadísticas | `ChatbooDashboard.hydrateContent` (dashboard.js:837-845) y el componente; listener global de clic en `document` (2523-2581) | Ninguna |
| `js/chatboo_dashboard.js` (global `ChatbooDashboard` 847-851) | Tarjetas de panel movibles/minimizables/maximizables; persiste el orden en `localStorage` | `hydrateContent` llamado por el componente | Ninguna (solo `localStorage` `chatboo_dash_v1_<id>`, 9-40) |
| `js/chatboo_systray.js` (`odoo.define`, 1) | Icono en la barra superior; crea el *overlay* persistente y monta el componente; insignias y avisos | `SystrayMenu.Items.push` (508) | `/chatboo/check_health` (32-35), `/pns_ai_mcp/verification/pending` (243-246), `/chatboo/dismiss_messages` (125), `mail_service`/`/mail/init_messaging` (190-195), `window.open(href)` (130-131) |
| `js/chatboo_svg_cards.js` (global `ChatbooSvgCards` 377-380) | Convierte `data-chatboo-card` (JSON) en SVG de reloj/dato o en banner de enlace | `hydrateContent` (dashboard.js:842-844) | Enlaces externos `target=_blank` (264-265); abre SVG como `blob:` (291-316) |
| `js/chatboo_tts.js` (global `window.__chatbooTts` 364-402) | Lectura en voz alta con Web Speech API | Componente | Ninguna de Odoo; **posible envío a servicios de voz del navegador** (§5.2) |
| `js/chatboo_context_stats.js` (global `ChatbooContextStats` 264-279) | Utilidades del modal de ocupación de contexto (barras, *sparkline* SVG, localizar burbuja) | Componente | Ninguna |
| `js/chatboo_choice_list.js` (global `ChatbooChoiceList` 141) | Tarjeta flotante con casillas para elegir vistas antes de la confirmación de la Caja B | Evento SSE `choice` del componente ([COMP]) | `/pns_ai_mcp/choice/accept` (94-97), `/pns_ai_mcp/choice/cancel` (120) vía `api.callJson` |
| `js/chatboo_screen_context.js` (global `ChatbooScreenContext` 145-149) | Captura qué pantalla de Odoo hay debajo del *overlay* | Componente (envío en `/chatboo/stream`, [COMP] §4) | Ninguna directa |
| `js/chatboo_card_width.js` (global `ChatbooCardWidth` 106-116) | Calcula el ancho de las tarjetas de resultado (variable CSS `--o-chatboo-card-width`) | Componente | Ninguna (el comentario 3 dice que la persistencia es por RPC, pero este archivo no la hace) |
| `xml/chatboo_systray.xml` | Plantilla `pns_ai_chatboo.chatboo_systray_item`: `<li>` oculto con icono e insignia | `template` del widget (systray.js:16) | Imagen `/pns_ai_chatboo/static/description/icon.png` (7) |
| `css/chatboo_floating.css` | Tokens `:root`, burbujas, tablas, código, toolbar de gráficos, banners, prompt, modal de sesiones | Bundle backend | — |
| `css/chatboo_dashboard.css` | Rejilla del panel, tarjetas, ancho de tarjetas de gráfico | Bundle backend | — |
| `css/chatboo_systray.css` | Vacío (solo comentario, 1-3) | Bundle backend | — |

## 2. Exportaciones en el navegador (`chatboo_export.js`)

### 2.1 Formatos y flujo (HECHO)

| Acción | Función | Cómo se genera | Origen de los datos |
|---|---|---|---|
| Copiar texto | `copyToClipboard` (671-745), modo `content` | TSV de `clip_data` (704-706, `clipDataToTsv` 2786-2796) o texto plano del HTML de la burbuja (708-710, `htmlToPlainExportText` 2178-2189) | `msg.clip_data`, `msg.formatted_html`/`msg.content`, `original_content` |
| Copiar Markdown | ídem, modo `markdown` (684-701) | `clipDataToMarkdown` (2771-2784) o `htmlToMarkdown` (68-149) | ídem |
| PDF | `downloadAsPDF` (1648-1715) | Preferente: informe estructurado con jsPDF + AutoTable (`buildDocument('pdf')` 3568-3590 → `generateReportPDF` 1839-2074): título, fecha, prosa como texto, tablas, gráficos como PNG, estadísticas. Si no hay tablas/gráficos/prosa: captura con html2canvas del clon de la burbuja (`generateWysiwygPDF` 891-935). Último recurso: PDF de texto (`generateTextPDF` 2084-2113) | Tablas: `data-chatboo-dataset` o `<table>` del HTML (`sectionsFromRenderedHtml` 2828-2868), o `clip_data` (2820-2826); gráficos: PNG de los canvas pintados o pintados fuera de pantalla (3292-3319) |
| Excel | `downloadAsExcel` (2963-3022) | **El navegador no genera el XLSX**: envía `sections` (matriz de texto/números) a `/chatboo/export/xlsx` y descarga el base64 devuelto (2989-3002) | Igual que PDF, sin imágenes (2972); si no hay tablas, intenta interpretar el texto como JSON/CSV/líneas (`plainTextToSections` 2886-2944) |
| Word | `downloadAsWord` (3667-3725) | HTML con espacios de nombres de Office guardado como `.doc` con tipo `application/msword` (`wrapWordHtml` 3044-3053, `buildDocument('doc')` 3543-3555) | Tablas, prosa y gráficos como en PDF; si no hay tablas ni prosa y la burbuja "parece documento", **el HTML clonado de la burbuja** (3684-3686) |
| Documentos pendientes de sesión | `fulfillPendingSessionDocuments` (3607-3665) | Para cada chip `pending` de tipo doc/pdf/html construye el documento (`buildDocument`) y lo **sube** en base64 a `/chatboo/sessions/fulfill_export` | Igual que PDF/Word, sin `richHtml` (3627-3638) |

- La subida de documentos pendientes **no requiere clic**: el componente la lanza a los 120 ms de
  pintar un mensaje con chips `pending` (HECHO `chatboo_component_v2.js:5308-5328`). El servidor
  guarda un adjunto de hasta 15 MB con `mimetype` elegido por el cliente ([SRV] fila
  `fulfill_export`).
- `xlsx.full.min.js` (SheetJS) **no se usa** en el código de Chatboo: no hay ninguna referencia a
  `XLSX.` en `chatboo_*.js` (HECHO, Grep). El Excel lo construye el servidor.

### 2.2 Qué datos incluye (HECHO salvo indicación)

- Columnas: **todas las claves del JSON del *dataset***, salvo las que empiezan por `_` y `__model`
  (`datasetRowsToAoa` 2211-2259). **Incluye `id`**, que el gráfico sí omite (`SKIP_KEYS`,
  charts.js:25). INFERENCIA: si el servidor pone en `data-chatboo-dataset` más columnas de las que
  pinta en la tabla, la exportación incluye datos que el usuario no ve en el chat.
- Valores objeto se serializan con `JSON.stringify` (2242-2243).
- Celdas que "parecen imagen" (empiezan por `data:image/`, contienen `/web/image/` en cualquier
  posición o empiezan por firma base64 PNG/JPEG/GIF/WebP; `cellLooksLikeImage` 1241-1252) se
  convierten en miniaturas; las que no son `data:` se descargan con `new Image()` y
  `crossOrigin='anonymous'` (`loadImgDataUrl` 1532-1552). INFERENCIA: un valor como
  `https://externo/web/image/x` hace que el navegador pida esa URL externa al exportar.
- PDF y Word añaden una tabla de estadísticas (n, mín., máx., media, mediana, desviación, suma)
  calculada en el navegador (3406-3520).
- Nombre del archivo: del título del `clip_data`, del primer fichero adjunto o del texto de la
  pregunta del usuario normalizado a ASCII (`generateFilename` 512-546, `contentFilename` 436-479).

### 2.3 Tratamiento del contenido

**Excel (fórmulas).** El navegador manda texto y números (`sectionsForServer` 2870-2884). El
servidor escribe cada texto como celda `t="inlineStr"` escapada con `html.escape`
(HECHO `pns_ai_mcp/utils/artifact_export.py:1742-1761`); los `int`/`float` como número. Una celda
de cadena en línea **no se evalúa como fórmula**, aunque empiece por `=`. Conclusión: sin
inyección de fórmulas en el XLSX descargado (HECHO del formato; comprobación al abrir con Excel/
LibreOffice PENDIENTE). Matiz: la **copia TSV** al portapapeles (704-706, 2786-2796) sí puede
pegarse en una hoja y allí `=…`, `+…`, `-…`, `@…` se interpretan como fórmula (INFERENCIA,
comportamiento estándar de las hojas de cálculo).

**PDF.** El informe estructurado escribe **solo texto** con `doc.text` y `autoTable` (prosa extraída
con `textContent`, 2499-2585; celdas con `pdfCellText` 940-945); no hay HTML ni JavaScript de PDF
(no se usa `addJS` ni AcroForm: Grep sin resultados). Las imágenes se insertan con `addImage`
(1172, 1824, 2011, 2034). La vía html2canvas rasteriza el clon de la burbuja (incluye todo su HTML
visible), con `useCORS: true` y `allowTaint: true` (914-921): las imágenes externas del contenido se
vuelven a pedir (INFERENCIA).

**Word (`.doc` HTML).**
- Tablas, títulos y prosa se escapan con `escapeWordText` (`&`, `<`, `>`; 3039-3042): sin inyección
  por texto (HECHO 3111-3125, 2149-2170, 3193).
- **Sin escapar**: el `src` de las imágenes de celdas (`'<td><img src="' + img + '"'`, 3123) y de
  los gráficos/figuras (3209-3214). `img` procede de `_pdfImg`, que puede ser **la cadena tal cual
  del *dataset*** cuando empieza por `data:` (2250-2251) o el `src` literal de un `<img>` de la
  burbuja si empieza por `data:` (`imgElementToDataUrl` 1258-1261). Una comilla doble en ese valor
  rompe el atributo e inserta HTML arbitrario en el documento (HECHO del código; explotación
  INFERENCIA). También no se escapan `"` en `escapeWordText`, pero solo se usa en contenido de
  elementos, no en atributos (HECHO).
- **Inserta HTML del turno**: si no hay tablas ni prosa y la burbuja tiene más de 80 caracteres,
  imágenes o encabezados (`bubbleLooksLikeRichDoc` 3084-3103), el cuerpo del Word es
  `host.innerHTML` del clon (3684-3686). `sanitizeWordClone` (3055-3082) **solo** quita `script`,
  barras de herramientas, `.o_chatboo_noexport`, gráficos y *tooltips*; conserva atributos `on*`,
  `style`, `iframe`, `object`, enlaces y `src` remotos. INFERENCIA: Word no ejecuta JavaScript, pero
  sí intenta cargar recursos remotos al abrir el documento (imágenes externas o rutas UNC
  `\\servidor\…` en Windows: fuga de credenciales NTLM / baliza de apertura).
- El documento HTML de "pendientes" (`kind='html'`, `buildHtmlDocument` 3526-3531) usa las mismas
  piezas (sin `richHtml`), así que hereda el problema del `src` sin escapar. Ese HTML se sube al
  servidor (3643-3652). En Odoo 14, un adjunto con tipo `*ht*`/`*xml*` se fuerza a `text/plain`
  si el usuario no es administrador del sistema (HECHO
  `/opt/odoo-src/14.0/odoo/odoo/addons/base/models/ir_attachment.py:331-340`); para un usuario con
  `base.group_system` se conserva `text/html` (INFERENCIA: depende de si el servidor crea el adjunto
  con ese usuario; PENDIENTE contrastar con `controllers/chatboo.py:271-293`). El chip se abre con
  `download=true` salvo SVG (`sessionFileHref` 554-577), lo que reduce el riesgo de que el HTML se
  renderice en el origen de Odoo (INFERENCIA).

**Sumideros `innerHTML` en elementos desconectados.** Casi todas las conversiones crean un `div`
con `document.createElement` y le asignan HTML: 72, 493, 538, 726, 731, 808, 1468, 2181, 2362, 2505,
2834, 3060 (HECHO). Un `<img onerror=…>` asignado así **se ejecuta** aunque el `div` no esté en la
página (INFERENCIA, comportamiento estándar de los navegadores). El HTML de la burbuja ya se pintó
con `t-raw` en el chat ([COMP] X3), por lo que en la mayoría de casos no añade superficie nueva;
la excepción es `markdownToProseBlocks` (2429-2491): convierte con **showdown** el Markdown crudo
del LLM (`original_content`) y lo vuelca en `innerHTML` (2445 → 2505), con la CVE de showdown de
§6 (comillas en URL de enlaces/imágenes). Se ejecuta en cada PDF/Word/pendiente, incluso de forma
automática (pendientes, §2.1).

## 3. Gráficos y panel

### 3.1 Origen de los datos (HECHO)

- Única fuente: atributo `data-chatboo-dataset` (JSON) de `.o_chatboo_table_block`
  (`hydrateRoot` charts.js:2276-2334; `JSON.parse` 2296). No se leen celdas del DOM (comentario 5).
  Ese HTML lo genera el servidor o el formateador ([COMP]); los valores proceden de registros
  consultados por el motor y las **claves** de columna de lo que devuelva la herramienta o el LLM
  (INFERENCIA: alias de columnas elegidos por el modelo).
- Atributos de control leídos del bloque: `data-chatboo-chart-engine` (1603-1623; también la
  global `window.CHATBOO_CHART_ENGINE`), `data-chatboo-show-mode` (1625-1640),
  `data-chatboo-dual-axis` (389-405, 442-455), `data-chatboo-no-charts` (1642-1655).
- Etiquetas = valores de la columna categoría convertidos con `String()` (491-494); series = valores
  numéricos parseados (`parseNumber` 117-151); nombres de serie/eje = clave con `_` → espacio
  (`humanizeKey` 153-158).
- Panel (`chatboo_dashboard.js`): reordena y oculta tarjetas que ya vienen en el HTML; el título del
  botón de restaurar usa `textContent` (358); los iconos son SVG fijos (141-180). Estado solo en
  `localStorage` (9-40, 413-417). No llama al servidor.

### 3.2 ¿Opciones de gráfico con HTML o funciones construidas con texto? (HECHO)

- **No** hay `formatter` construido con cadenas: los únicos *formatters* son la función fija
  `formatTick` (1142-1151) en `axisLabel.formatter` y `tooltip.valueFormatter` de ECharts
  (1425, 1446, 1489, 1497, 1559) y en `ticks.callback` de Chart.js (1216-1218, 1233-1235). No hay
  `tooltip.formatter`, `rich` ni `eval/new Function` en el archivo.
- Chart.js dibuja en `canvas` (sin HTML). ECharts pinta ejes/leyendas en `canvas`; el *tooltip*
  por defecto es HTML pero los *formatters* integrados escapan (convención citada por la propia
  advertencia de Apache, ver §6). Tipos usados: `bar`, `line`, `pie`, `radar` (1381-1601); **no**
  `lines`, que es la serie afectada por CVE-2026-45249 (HECHO por lectura de los `type:` 1157,
  1244, 1402, 1459, 1508).
- **Sumidero real en este archivo**: la tabla de estadísticas. `statsTableHtml` (2185-2218)
  concatena `model[i].name` (= clave de la serie, es decir, nombre de columna del *dataset*) **sin
  escapar** (2210) y `mountSeriesStats` lo inserta con `wrap.innerHTML` en la burbuja (2261-2273).
  Una clave de columna con HTML (`<img src=x onerror=…>`) se ejecuta en el navegador del usuario
  (INFERENCIA de explotación; depende de si el servidor deja pasar claves arbitrarias). Las etiquetas
  `_t(...)` también se concatenan sin escapar (2201, 2206), pero son literales fijos.
- `_t` de este archivo busca `global.odoo._t` (2116-2121), que **no existe en Odoo 14** (Grep
  `odoo._t =` en `/opt/odoo-src/14.0/odoo/addons/web/static/src` sin resultados): los textos
  "Statistics", "Min"… salen siempre en inglés en el chat (HECHO por ausencia).

## 4. `screen_context` en el navegador (`chatboo_screen_context.js`)

- **Qué recoge (HECHO)**: `url_hash` completo (`location.hash`, 54), `action{action_id, name,
  res_model, view_type, res_id, active_ids, domain, menu_id}` (55-64 o 92-103) y `captured_at`
  (114). No lee valores de campos de la pantalla; el servidor enriquece después con
  `display_name`, partner, importes ([SRV] y `analisis_pns_ai_mcp_7_motor_llm.md` §9).
- **En Odoo 14** el componente no recibe `env.services.action` (el `env` legacy de 14 solo añade
  `blockUI/unblockUI`, HECHO `/opt/odoo-src/14.0/odoo/addons/web/static/src/js/env.js:13`), así que
  se usa `fromHash` (110-113): `name` y `domain` van a `null`, `active_ids` es `[res_id]` o vacío
  (INFERENCIA coincidente con [COMP] §4). En una lista con selección múltiple **no** se envían los
  ids seleccionados.
- `url_hash` se envía crudo: incluye cualquier parámetro del *hash* (p. ej. `cids` de compañías,
  `active_id`), lo que también se guarda en `chatboo.session.last_screen_context` ([SRV]).
- La captura se refresca al mostrar el *overlay* y se borra al ocultarlo
  (`chatboo_systray.js:316-345, 362-385`).
- `parseActiveIds` (28-47) sustituye `'` por `"` y hace `JSON.parse`: solo produce enteros; no hay
  riesgo de ejecución (HECHO).

## 5. Systray, TTS y resto

### 5.1 Systray (`chatboo_systray.js`)

- **Arranque** (26-52): el `<li>` empieza oculto; llama a `/chatboo/check_health` en **cada carga del
  cliente web de cada usuario interno** y solo muestra el icono si `show_systray !== false`. En error
  se queda oculto (*fail-closed*). Guarda `chatboo_has_access` en `localStorage` (38, 43, 49), pero
  **nunca lo lee** (HECHO, Grep): código muerto.
- **Al activarse** (58-134): escucha el bus (`bus_service.onNotification`, 67; API válida en 14,
  HECHO `/opt/odoo-src/14.0/odoo/addons/bus/static/src/js/services/bus_service.js:95-97`), los
  eventos internos `chatboo_response_ready` y `chatboo_auth_cue`, y consulta
  `/pns_ai_mcp/verification/pending` (243-246) para la insignia de "esperando confirmación".
- **Manejador global** `$(document).on('click.chatboo_systray', '.o_chatboo_dismiss_btn', …)`
  (94-133): cierra ventanas de chat de Discuss, llama a `/chatboo/dismiss_messages` y, si no está en
  Chatboo, hace `window.open(href del <a>, '_blank')` sin `noopener` (130-131). Ni la clase
  `o_chatboo_dismiss_btn` ni la ruta `/chatboo/dismiss_notification` existen en el repositorio
  (HECHO, Grep): es **código heredado sin uso**; cualquier mensaje de Discuss que contenga un enlace
  con esa clase lo activaría (INFERENCIA; el saneador de Odoo conserva `class`).
- `_onAsyncDone` (178-200) llama a `this.call('mail_service', 'getMessaging')`: **ese servicio no
  existe en Odoo 14** (Grep sin resultados en `addons/mail/static/src`); `_onCallService` hace
  `service[method]` con `service` indefinido (HECHO
  `/opt/odoo-src/14.0/odoo/addons/web/static/src/js/chrome/abstract_web_client.js:362-363`) y el
  `TypeError` lo captura el `try` (197-199). Efecto: el contador de Discuss no se refresca; sin
  rotura (INFERENCIA).
- **Overlay** (390-505): `div#o_chatboo_persistent_overlay` fijo bajo la barra de navegación, `z-index:
  1050`, añadido a `document.body` una sola vez y nunca destruido; el componente se monta ahí y se
  expone como `window.__chatboo_component` (482). Añade un *listener* de captura en la barra de
  navegación que oculta el overlay en cualquier clic (412-430), que no se retira nunca.
- Insignias con `innerHTML` de literales fijos (289-295, 310): sin riesgo.
- Notificaciones: `displayNotification` / `do_notify` existen en 14 (HECHO
  `/opt/odoo-src/14.0/odoo/addons/web/static/src/js/core/service_mixins.js:248,255`).
- Salidas fuera de Odoo: ninguna, salvo el `window.open` heredado.

### 5.2 TTS (`chatboo_tts.js`)

- Usa `window.speechSynthesis` / `SpeechSynthesisUtterance` del navegador (24-28, 293-313). No llama
  a Odoo ni a ningún servicio propio. Preferencia en `localStorage` `chatboo.tts.enabled` (16, 30-42).
- Lee hasta 12 000 caracteres (20, 84-93) del HTML de la respuesta (`formatted_html`, `htmlSrc` o
  `content`, 123-128) o, con TTS activo, **desde el punto donde se haga clic** en el chat, hasta la
  siguiente pregunta del usuario (315-333, 207-237), incluido el texto del campo de prompt (182-205).
- **Elección de voz** (`pickVoice` 57-78): primera voz cuyo idioma coincide; si no, la
  predeterminada; si no, la primera. **No mira `voice.localService`** (HECHO). INFERENCIA: en
  Chrome las voces "Google …" y en Edge las "Microsoft … Online (Natural)" son remotas; si el
  navegador elige una de ellas, el texto de la respuesta (datos de negocio) se envía a
  Google/Microsoft. PENDIENTE: comprobar qué voces devuelve `getVoices()` en los navegadores de los
  usuarios.
- `extractFullText` (113-121) asigna el HTML a un `div` desconectado (mismo patrón de §2.3).

### 5.3 Resto

- **`chatboo_svg_cards.js`**: todo el texto de las tarjetas pasa por `escapeXml` (10-16, 136-138,
  181-186, 250-253); `hourAng/minAng` son números (134-135). Enlaces: `safeHref` (204-223) solo admite
  `http(s)://`, dominios desnudos (les antepone `https://`) y rutas que empiezan por `/` sin `//`;
  rechaza espacios y comillas. Matiz: `/\externo.com` pasa el filtro y los navegadores lo tratan como
  `//externo.com` (INFERENCIA; el banner ya admite cualquier `https://`, así que el impacto es nulo).
  `openSvg` abre un `blob:` (mismo origen que Odoo) con contenido escapado: sin riesgo. Defecto:
  `window.open(url, '_blank', 'noopener')` devuelve siempre `null` con `noopener`, por lo que además
  se lanza la descarga (297-312) (INFERENCIA por la especificación de `window.open`).
- **`chatboo_choice_list.js`**: todo con `textContent` (25, 30, 45-47, 100, 111); tarjeta fija con
  `z-index: 20000` en `document.body` (21, 138). Envía `choice_id` y `selected_ids` (enteros) a
  `/pns_ai_mcp/choice/accept|cancel`.
- **`chatboo_context_stats.js`**: escapa los títulos del SVG (`esc` 14-20, 221); los anchos y colores
  son numéricos o de una lista fija (140-164); `findTurnBubble` limpia el código de turno (227-229)
  pero mete `messageIndex` sin limpiar en un selector (241) (solo puede provocar una excepción de
  selector). Sin red.
- **`chatboo_card_width.js`**: solo cálculo y `style.setProperty` (60-69). Sin red.
- **`chatboo_charts.js`**: *listener* global de clic en `document` en fase de captura
  (2523-2581), limitado a `.o_chatboo_cell_copy` dentro de contenedores de Chatboo; copia
  `data-copy-text` al portapapeles.

## 6. Librerías incluidas

| Librería (archivo) | Versión (HECHO, cabecera) | CVE conocidas que aplican | ¿Se usa en Chatboo? |
|---|---|---|---|
| showdown (`showdown.js:1`) | 2.1.0 | **CVE-2026-104477** (XSS: no escapa `"` en URL de enlaces/imágenes; afecta hasta 2.1.0, sin versión corregida publicada); **CVE-2024-1899** (DoS en el subparser de anclas, ≤ 2.1.0). Proyecto sin mantenimiento (INFERENCIA). | Sí: formateador (fuera del bloque) y `chatboo_export.js:363-372, 2437-2445` |
| jsPDF (`jspdf.umd.min.js:4`) | 2.5.1 (2022-01-28) | **CVE-2025-29907** y **CVE-2025-57810** (DoS por datos de imagen en `addImage`/`html`; corregidas en 3.0.1/3.0.2): aplican porque se llama a `addImage` con datos que pueden venir del *dataset*. CVE-2026-31938 (inyección HTML con `output()` hacia ventana nueva), CVE-2026-25940/24737 (AcroForm), CVE-2026-25755 (`addJS`): **no aplican** (solo se usa `output('blob')` y `save`, sin AcroForm ni `addJS`; HECHO 1860, 2067, 2070, 879). | Sí |
| jsPDF-AutoTable (`jspdf.plugin.autotable.min.js:3`) | 3.8.4 | Ninguna encontrada (PENDIENTE confirmar en GHSA). | Sí |
| html2canvas (`html2canvas.min.js:2`) | 1.4.1 (2022) | Ninguna conocida. | Sí (PDF de último recurso) |
| SheetJS xlsx (`xlsx.full.min.js`, `.version="0.18.5"`) | 0.18.5 | **CVE-2023-30533** (contaminación de prototipo al **leer** ficheros; corregida 0.19.3) y **CVE-2024-22363** (ReDoS; corregida 0.20.2). La versión de npm está abandonada. En Chatboo **no aplican en la práctica** porque no se usa la librería. | **No** (HECHO, Grep `XLSX.`) |
| Chart.js (`chart.umd.min.js:3`) | 4.4.8 | Ninguna (la única histórica, CVE-2020-7746, afecta a < 2.9.4). | Sí |
| Apache ECharts (`echarts.min.js:45`, `t.version="5.6.0"`; zrender 5.6.1) | 5.6.0 | **CVE-2026-45249** (XSS en el *tooltip* de la serie `lines`; corregida en 6.1.0): **no aplica**, Chatboo no usa `lines` (§3.2). | Sí |

**Comparación con `pns_ai_mcp`** (HECHO `pns_ai_mcp/views/assets.xml:20-22`): MCP carga
`showdown.js` (2.1.0), `jspdf.umd.min.js` (2.5.1, cabecera idéntica) y `xlsx.full.min.js` (0.18.5)
desde sus propias rutas; no carga AutoTable, html2canvas, Chart.js ni ECharts. Ambas plantillas
heredan `web.assets_backend`; Odoo aplica las vistas heredadas `ORDER BY priority, id`
(HECHO `/opt/odoo-src/14.0/odoo/odoo/addons/base/models/ir_ui_view.py:604`). Como MCP se instala
antes (Chatboo depende de él, `__manifest__.py:26`), su vista tiene id menor y sus scripts van antes
en el *bundle*; las copias de Chatboo se ejecutan después y **sobrescriben las globales**
(`showdown`, `window.jspdf`, `XLSX`): prevalecen las de Chatboo (INFERENCIA). Al ser las mismas
versiones no cambia el comportamiento; la identidad byte a byte es PENDIENTE. Efecto colateral: las
tres librerías se descargan **dos veces** en cada carga del backend. MCP, además, recarga su
`assets.xml` desde `_auto_init` (`pns_ai_mcp/models/ai_context.py:1222-1226`,
`pns_ai_mcp/utils/compat.py:60-71`), mismo XML ID, sin efecto en el orden (INFERENCIA).

Fuentes de CVE: ver el apartado "Fuentes" al final.

## 7. Cambios globales en el cliente web y compatibilidad con Odoo 14

### 7.1 Cambios globales (HECHO)

- Globales de `window`: `ChatbooCharts`, `ChatbooDashboard`, `ChatbooSvgCards`, `ChatbooCardWidth`,
  `ChatbooContextStats`, `ChatbooChoiceList`, `ChatbooScreenContext`, `__chatbooTts`,
  `__chatbooCellCopyBound`, `__chatboo_component` y las de las librerías (`showdown`, `jspdf`,
  `html2canvas`, `XLSX`, `Chart`, `echarts`).
- **Colisión de `window.Chart`**. Odoo 14 no mete Chart.js en `web.assets_backend` (solo en
  `web.tests_assets`, HECHO `/opt/odoo-src/14.0/odoo/addons/web/views/webclient_templates.xml:613,637`):
  lo carga **bajo demanda** con `jsLibs: ['/web/static/lib/Chart/Chart.js']` la vista *graph*
  (HECHO `web/static/src/js/views/graph/graph_view.js:25-27`), el gráfico del tablero contable
  (`web/static/src/js/fields/basic_fields.js:3067`), `web_kanban_gauge`, `website` y `survey`.
  `loadJS` solo evita recargar **la misma URL** (HECHO `web/static/src/js/core/ajax.js:182-194`),
  así que no detecta el `Chart` 4.x de Chatboo (que viene dentro del *bundle*). Secuencia
  (INFERENCIA): al iniciar, `window.Chart` = 4.4.8 (Chatboo); al abrir por primera vez una vista
  gráfico o el tablero contable, Odoo carga su Chart.js 2.x y **sobrescribe** `window.Chart`; desde
  ese momento, hasta recargar la página, `chatboo_charts.js` instancia Chart.js 2.x con
  configuración de la 4.x (`scales.x/y`, `plugins.legend`, tipo por *dataset*; 1197-1279), con
  gráficos mal pintados o errores. Las vistas de Odoo no se rompen (reciben su 2.x). Afecta al motor
  por defecto: sin atributo de motor se elige Chart.js si `typeof Chart === 'function'` (1603-1622).
  La versión exacta de Chart.js del core no se puede ver (las referencias no incluyen
  `static/lib`): PENDIENTE.
- *Listeners* globales: clic en `document` (charts.js:2528-2579, captura), clic delegado jQuery en
  `document` (systray.js:94), captura en la barra de navegación (systray.js:413-429),
  `window.resize` por gráfico ECharts (charts.js:1851-1854, retirado en `destroyChart` 1101-1108).
- DOM añadido a `body`: overlay (z-index 1050), tarjeta de elección (z-index 20000), host de captura
  PDF fuera de pantalla (export.js:780-829, se elimina) y host de gráfico fuera de pantalla
  (3262-3289, se elimina).
- `localStorage`: `chatboo_has_access`, `chatboo_unread`, `chatboo.tts.enabled`,
  `chatboo_dash_v1_<id>`.

### 7.2 Compatibilidad con Odoo 14

| Punto | Estado |
|---|---|
| Assets por plantilla heredada y `qweb` en manifest | Correcto (HECHO, §1.1) |
| Widget legacy de systray, `SystrayMenu.Items.push`, `_rpc`, `bus_service.onNotification`, `displayNotification` | Correcto en 14 (HECHO, §5.1) |
| `mail_service` | No existe en 14; error capturado (HECHO, §5.1) |
| `env.services.action` | No existe en 14; se usa el *hash* (HECHO, §4) |
| `global.odoo._t` | No existe en 14; textos de estadísticas sin traducir (HECHO, §3.2) |
| Clases Bootstrap 5 (`form-select form-select-sm` charts.js:1948; `fw-bold` systray.js:289) | Odoo 14 usa Bootstrap 4 (INFERENCIA): el selector del gráfico sale sin estilo y `fw-bold` no aplica. Cosmético. |
| CSS `:has()` (floating.css:107,110; dashboard.css:353), `field-sizing` (floating.css:902), `inset`, `min()/clamp()` | Requieren navegadores recientes (Firefox ≥ 121 para `:has`); en otros, degradación visual (INFERENCIA). |
| Clase `o_mail_systray_item` en la plantilla | Existe en 14 (HECHO `/opt/odoo-src/14.0/odoo/addons/mail/static/src/scss/systray.scss`); toma el estilo de los iconos de Discuss. |

### 7.3 CSS que afecta a pantallas que no son del chat (HECHO)

- `:root` define 18 variables `--chatboo-*` (floating.css:4-23): prefijadas, sin colisión.
- Todos los demás selectores empiezan por `.o_chatboo_*` o `#o_chatboo_*`; no se tocan clases de
  Odoo fuera de esos contenedores. Excepción menor: `.o_chatboo_slash .badge.badge-secondary`
  (1052-1056) y `.dropdown-item` dentro de `.o_chatboo_slash` (998-1034), acotados al menú de Chatboo.
- `.o_chatboo_container` con `!important` (1075-1079) y `.o_chatboo_floating_window` con
  `z-index: 1050` (1086-1099): solo en pantallas de Chatboo.
- Efecto indirecto: el overlay (`z-index: 1050`, systray.js:405) iguala el `z-index` de los modales
  de Bootstrap 4; un diálogo de Odoo abierto desde el chat (p. ej. `doAction` con `target: new`)
  queda por encima solo por estar después en el DOM (INFERENCIA; PENDIENTE probar).

## 8. Riesgos

| # | Riesgo | Base | Gravedad estimada |
|---|---|---|---|
| R1 | XSS por **clave de columna** del *dataset* en la tabla de estadísticas (`statsTableHtml` → `innerHTML`) | HECHO charts.js:2210, 2261-2262; explotación INFERENCIA | Media-alta (se pinta en el chat del usuario, en su sesión de Odoo) |
| R2 | showdown 2.1.0 con XSS conocida (CVE-2026-104477) aplicado al Markdown crudo del LLM en exportaciones, que además se lanzan solas para chips pendientes | HECHO export.js:2437-2445, 2505; component:5308-5328 | Media |
| R3 | `src` de imágenes sin escapar en Word/HTML exportado (inyección de HTML en el documento; el HTML se sube al servidor como adjunto) | HECHO export.js:3123, 3209-3214, 2250-2251 | Media-baja |
| R4 | Word con el HTML de la burbuja tal cual (recursos remotos, UNC/NTLM al abrir en Windows) | HECHO 3684-3686, 3055-3082; impacto INFERENCIA | Media-baja |
| R5 | TTS puede usar voces remotas (Google/Microsoft) y enviar fuera el texto de las respuestas | HECHO tts.js:57-78; envío INFERENCIA | Media (protección de datos) |
| R6 | Exportación incluye columnas del *dataset* no visibles (`id` y otras) | HECHO export.js:2211-2259; alcance INFERENCIA | Baja-media |
| R7 | Peticiones a URLs externas al exportar (`/web/image/` en cualquier posición, `useCORS`) | HECHO export.js:1248, 1532-1552, 914-921 | Baja |
| R8 | Librerías con CVE (jsPDF 2.5.1 DoS en `addImage`; showdown) y SheetJS 0.18.5 cargado sin uso, duplicado con MCP | HECHO §6 | Baja-media |
| R9 | Todo el JS/CSS (≈ 7 librerías) se carga a todos los internos y cada carga llama a `check_health` | HECHO assets.xml; systray.js:32 | Rendimiento |
| R10 | Choque de `window.Chart`: tras abrir una vista gráfico o el tablero contable, Odoo carga su Chart.js 2.x encima del 4.x de Chatboo y los gráficos del chat se pintan con la API equivocada hasta recargar | HECHO de los mecanismos (§7.1); efecto INFERENCIA | Media (funcional; las vistas de Odoo no se rompen) |
| R11 | Código heredado: `.o_chatboo_dismiss_btn` + `window.open` sin `noopener`, `chatboo_has_access` sin lectura, `mail_service` inexistente | HECHO §5.1 | Baja |
| R12 | TSV copiado al portapapeles con celdas `=…` se evalúa al pegar en una hoja | INFERENCIA | Baja |

## Resumen del bloque

1. 10 archivos JS, 1 XML y 3 CSS leídos enteros; las 7 librerías solo por cabecera/versión.
2. Todo se carga en `web.assets_backend` para cualquier interno; el icono depende de
   `/chatboo/check_health`, que se llama en cada carga del cliente.
3. Exportaciones: PDF (jsPDF+AutoTable, texto puro; html2canvas como último recurso), Word (HTML
   `.doc`), Excel (lo construye el servidor con celdas `inlineStr`: sin inyección de fórmulas).
4. Los documentos "pendientes" se generan en el navegador y se **suben solos** a
   `/chatboo/sessions/fulfill_export`.
5. Word inserta el HTML de la burbuja si no hay tablas ni prosa, con un saneado mínimo; el `src` de
   imágenes va sin escapar en Word y en el HTML subido.
6. Las exportaciones usan muchos `innerHTML` en `div` desconectados; uno de ellos procesa con
   showdown 2.1.0 (CVE-2026-104477) el Markdown crudo del LLM.
7. Gráficos: datos solo de `data-chatboo-dataset`; sin *formatters* construidos con texto; Chart.js
   en canvas, ECharts sin serie `lines` (CVE-2026-45249 no aplica).
8. Sumidero propio: la tabla de estadísticas inserta la clave de columna sin escapar
   (`charts.js:2210`).
9. Panel: solo `localStorage`, sin red, con `textContent`.
10. `screen_context` en 14: hash de la URL (acción, modelo, id, vista, menú) + `url_hash` completo;
    `name` y `domain` nulos; no envía selección múltiple.
11. Systray: overlay persistente en `body` (z-index 1050), *listeners* globales, código heredado
    (`o_chatboo_dismiss_btn`, `mail_service` inexistente en 14, `chatboo_has_access` sin uso).
12. TTS: Web Speech API sin filtrar voces locales; posible envío de respuestas a Google/Microsoft.
13. SVG cards, choice list, context stats y card width: escapado correcto o `textContent`; sin red
    salvo las rutas de la Caja B.
14. Librerías: showdown 2.1.0, jsPDF 2.5.1, AutoTable 3.8.4, html2canvas 1.4.1, SheetJS 0.18.5
    (sin uso), Chart.js 4.4.8, ECharts 5.6.0.
15. MCP carga showdown, jsPDF y SheetJS en las mismas versiones; prevalecen las copias de Chatboo
    por orden de herencia (INFERENCIA) y se descargan dos veces.
16. CSS acotado a clases `o_chatboo_*`; solo variables `:root` globales.
17. Compatibilidad 14: correcta en lo esencial; detalles de Bootstrap 5 y `:has()` cosméticos.
18. Riesgo a confirmar con prioridad: al abrir una vista gráfico o el tablero contable, Odoo 14
    carga su Chart.js 2.x encima del 4.x de Chatboo y los gráficos del chat quedan rotos hasta
    recargar (R10).

## Tabla de cobertura

| Archivo | Líneas | Lectura |
|---|---|---|
| `js/chatboo_export.js` | 3751 | Entero (3 tramos: 1-1589, 1590-2689, 2690-3751) |
| `js/chatboo_charts.js` | 2583 | Entero (2 tramos: 1-1699, 1700-2583) |
| `js/chatboo_dashboard.js` | 853 | Entero |
| `js/chatboo_systray.js` | 513 | Entero |
| `js/chatboo_svg_cards.js` | 382 | Entero |
| `js/chatboo_tts.js` | 404 | Entero |
| `js/chatboo_context_stats.js` | 281 | Entero |
| `js/chatboo_choice_list.js` | 143 | Entero |
| `js/chatboo_screen_context.js` | 151 | Entero |
| `js/chatboo_card_width.js` | 118 | Entero |
| `xml/chatboo_systray.xml` | 14 | Entero |
| `css/chatboo_floating.css` | 1350 | Entero |
| `css/chatboo_dashboard.css` | 360 | Entero |
| `css/chatboo_systray.css` | 4 | Entero |
| `showdown.js`, `jspdf.umd.min.js`, `jspdf.plugin.autotable.min.js`, `html2canvas.min.js`, `xlsx.full.min.js`, `chart.umd.min.js`, `echarts.min.js` | — | **No leídos enteros** (por instrucción): solo cabecera o búsqueda de la cadena de versión |
| Consultados fuera del bloque (parcial) | — | `views/assets.xml` (entero), `__manifest__.py` (Grep), `chatboo_component_v2.js:5295-5334` y Grep de `exportUtils`, `pns_ai_mcp/views/assets.xml` (entero), `pns_ai_mcp/utils/artifact_export.py:1451-1510, 1733-1777`, cabeceras de las librerías de `pns_ai_mcp` |

## Preguntas abiertas

1. ¿Puede el servidor o el LLM fijar libremente las **claves de columna** de `data-chatboo-dataset`
   (alias SQL, etiquetas inventadas)? Determina si R1 es explotable.
2. ¿El *dataset* incluye columnas que la tabla no muestra (además de `id`)? Si es así, ¿es aceptable
   que el PDF/Word/Excel las incluya?
3. Confirmar R10 en local: abrir Chatboo, pedir un gráfico, abrir una vista *graph* (o el tablero
   de Contabilidad) y volver a pedir un gráfico en el chat sin recargar. ¿Se pinta bien?
4. ¿Qué navegadores usan los usuarios y qué voces devuelve `speechSynthesis.getVoices()`? ¿Se
   acepta que el texto de las respuestas pueda salir hacia servicios de voz de Google/Microsoft?
5. El adjunto creado por `/chatboo/sessions/fulfill_export`, ¿se crea con el usuario o con `sudo`
   y con qué `mimetype` final para usuarios administradores? (riesgo de HTML servido como
   `text/html`).
6. ¿Es aceptable la subida automática de documentos pendientes sin acción del usuario?
7. ¿Se quiere mantener cargadas en todo el backend las 7 librerías (y las 3 duplicadas de MCP),
   incluida SheetJS 0.18.5 que Chatboo no usa?
8. ¿Hay plan del proveedor para actualizar showdown (sin versión corregida publicada) y jsPDF
   (≥ 3.0.2 para las DoS de `addImage`)?
9. ¿Las copias de `showdown.js`, `jspdf.umd.min.js` y `xlsx.full.min.js` de Chatboo y MCP son
   idénticas byte a byte? (comprobar con `sha256sum`).
10. El código heredado (`o_chatboo_dismiss_btn`, `/chatboo/dismiss_notification`,
    `chatboo_has_access`, `mail_service`), ¿lo retira el proveedor o se documenta como inocuo?

## Fuentes

- jsPDF CVE-2025-29907: <https://advisories.gitlab.com/npm/jspdf/CVE-2025-29907/>
- jsPDF CVE-2025-57810: <https://advisories.gitlab.com/npm/jspdf/CVE-2025-57810/>
- jsPDF CVE-2026-31938 (GHSA-wfv2-pwc8-crg5): <https://osv.dev/vulnerability/GHSA-wfv2-pwc8-crg5>
- jsPDF CVE-2026-25940: <https://db.gcve.eu/vuln/CVE-2026-25940>
- jsPDF CVE-2026-25755: <https://db.gcve.eu/vuln/CVE-2026-25755>
- jsPDF CVE-2026-24737: <https://advisories.gitlab.com/npm/jspdf/CVE-2026-24737/>
- SheetJS CVE-2023-30533: <https://advisories.gitlab.com/pkg/npm/xlsx/CVE-2023-30533/>
- SheetJS CVE-2024-22363: <https://cdn.sheetjs.com/advisories/CVE-2024-22363>
- Apache ECharts (CVE-2026-45249): <https://security.apache.org/projects/echarts/>
- showdown CVE-2026-104477: <https://www.vulncheck.com/advisories/showdown-through-2.1.0-xss-via-unescaped-quote-in-href-and-src-attributes>
- showdown CVE-2024-1899: <https://nvd.nist.gov/vuln/detail/CVE-2024-1899>
- Chart.js CVE-2020-7746: <https://nvd.nist.gov/vuln/detail/CVE-2020-7746>
- html2canvas (sin vulnerabilidades conocidas): <https://depscope.dev/pkg/npm/html2canvas>
