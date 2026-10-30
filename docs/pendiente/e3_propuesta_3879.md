# Propuesta de la entrega E3′ (lienzo) — inventario previo

- **Rama:** `14.0-pns-ai-3879` · contexto `odoo-dev 14 lab_pns_ai_3879`, BD `lab_pns_ai_3879_14`
- **Fecha:** 29/10/2026
- **Plan:** [plan de corrección sobre 3.1.879](plan_correccion_pns_ai_3879.md), ficha de E3′ (M1, M2, F1 y,
  desde el 29/10/2026, D1)
- **Datos:** [comparación con 3.1.879](../specs/comparacion_pns_ai_3-1-879.md) §8.1, §8.2 (M1, M2, M3), §8.3
  (D1, D5), §8.4 (F1) y §8.7 (P-8c, P-8d, P-8e, P-8h); [registro de parches](parches_pns_ai.md): parche 15,
  parche 18 («Excepción documentada: la ventana del lienzo») y parche 22.
- **HEAD de partida:** `59f8980` («[DOC] E2′ en el staging pns_demo: subida y pruebas (29/10/2026)»).
- **Estado:** inventario de solo lectura, sin decisiones tomadas. Donde hay opciones se describen con su
  efecto, sin elegir y sin código. Decisiones: «Propuesta final (29/10/2026)», al final.

Las líneas son de la copia de trabajo (3.1.879 con E1′ y E2′), no de 3.1.879 sin parches. Las
comprobaciones son de solo lectura: código de los tres módulos, core de Odoo 14 de referencia
(`/opt/odoo-src/14.0`) y `SELECT` dentro de `BEGIN READ ONLY … ROLLBACK` sobre `lab_pns_ai_3879_14`. No se
ha leído ni impreso ningún secreto (ni `api_key` ni claves MCP).

Rutas abreviadas: `session.py` = `pns_ai_chatboo/models/chatboo_session.py`; `canvas.py` =
`pns_ai_chatboo/models/chatboo_canvas.py`; `page.py` = `pns_ai_chatboo/models/chatboo_canvas_page.py`;
`chatboo.py` = `pns_ai_chatboo/controllers/chatboo.py`.

## Hechos de base (para todos los puntos)

- **Los helpers del sandbox se publican en `sudo`.** `collect_sandbox_helpers`
  (`pns_ai_mcp/utils/sandbox_helpers.py:53-88`) hace `rec = rec.sudo()` antes de `rec.sandbox_helpers()`
  (`:68-70`). `sandbox_helpers` (`session.py:819-842`) envuelve `page_url`, `page_edit` y `page_html` con
  `getattr(self, nombre)`: los tres corren sobre un `chatboo.session` vacío **en `sudo`** y con el uid real
  (en Odoo 14 `sudo()` no cambia el uid). Se llaman desde `build_safe_context`
  (`pns_ai_mcp/controllers/context_builder.py:866-871`) con el entorno de la caja A.
- **Entorno de la caja A.** `get_readonly_env` (`pns_ai_mcp/controllers/controller_helpers.py:184-250`):
  cursor nuevo, `SET TRANSACTION READ ONLY`, `commit` neutralizado y el mismo uid que el entorno del motor
  (`:224`). El contexto se copia de forma superficial (`{**base_env.context, …}`): los objetos mutables del
  contexto, como `page_request`, son **los mismos** que ve el motor. El parche 18 marca ese cursor
  (`pns_ai_mcp/controllers/tools_relaxaicode.py:186-188`) y lo desmarca en el `finally` (`:289-291`).
- **Sesión del turno.** `_session_of_this_turn` (`canvas.py:619-649`) toma el id de
  `resolve_session_ref` (`pns_ai_mcp/utils/session_download.py:547-563`: `ai_session_ref` del contexto o de
  la petición HTTP), lee la sesión **en `sudo`** (`:639`) y exige `session.user_id == env.uid`, salvo si el
  uid es `SUPERUSER_ID` (1), que pasa con cualquier sesión (`:644`).
- **Escritura del lienzo.** `_store_design` (`session.py:976-1019`) y `_store_title` (`:1021-1049`) escriben
  en un cursor propio como `SUPERUSER_ID` y confirman. Sin comprobación propia del dueño: confían en quien
  las llama.

## I1. `paint_canvas` (M1): llamadores, uid y entorno

**Definición:** `session.py:1051-1186`. Con `new_page=True` no lee ningún campo de `self` antes de
`_store_design` (solo `self.canvas_design` cuando `new_page` es falso, `:1079`); `_ask_design`
(`:1189-1200`), `_canvas_build_cancelled` (`:1293-1297`) y `canvas_public_url(rev=…)` (`:966-970`) solo usan
`self.id` y el contexto.

**Llamadores (Grep de `paint_canvas` en los tres módulos, incluidos `static/`, vistas y datos):**

| # | Llamador | Cómo llega a `paint_canvas` | uid | Entorno de `self` | Cursor |
|---|---|---|---|---|---|
| a | RPC `/web/dataset/call_kw` | Directo: `_call_kw_multi` hace `browse(ids)` sin comprobar acceso (`/opt/odoo-src/14.0/odoo/odoo/api.py:386-392`) | El del llamador | Usuario, sin `su`, sobre **cualquier** id | Petición |
| b | `page_url` desde el sandbox | `page_url` (`session.py:876-897`) → `open_page` (`canvas.py:884-930`) → `_session_of_this_turn` → `session.paint_canvas(…)` (`canvas.py:924`) | El del turno | Sesión propia **en `sudo`** | Caja A (marcada, `READ ONLY`); la llamada de diseño, dentro de la ventana del parche 18 |
| c | `page_edit` desde el sandbox | `page_edit` (`session.py:947-964`) → `edit_page` (`canvas.py:938-955`): con filas, como (b); sin filas, `session.paint_canvas(instruction, new_page=False)` (`canvas.py:948`) | El del turno | Sesión propia en `sudo` | Caja A, como (b) |
| d | Botón Canvas | `POST /chatboo/canvas/build` (`chatboo.py:346-361`; acceso a Chatboo y `_own_session`, `:88-95`) → `chatboo.canvas.job._start` (`chatboo_canvas_job.py:36-71`) → hilo de `_spawn` (`chatboo_job.py:176-228`, `api.Environment(cr, uid, context)` con el uid de la petición, `:187, 207`) → `_process` (`chatboo_canvas_job.py:101-131`) → `open_page(env['chatboo.session'] con ai_session_ref, …)` → (b) | El que pulsó | Sesión propia en `sudo` (vía `_session_of_this_turn`) | Cursor propio del hilo, sin marca |
| e | Página «en espera» | `page_url` sin filas, o `_claim_page_turn` (`session.py:844-865`) cuando la frase activa `page_tab`, guardan un `fulfill` con `note_page_waiting` (`pns_ai_mcp/utils/result_page.py:101-109`). El motor lo ejecuta en `fulfill_waiting_page` (`result_page.py:167-200`) desde `_tool_loop_fulfill_page` (`pns_ai_mcp/utils/engine_tool_run.py:383-406`) y desde `_offer_page_card` (`pns_ai_mcp/utils/engine_presentation.py:215-228`). El `fulfill` llama a `open_page(env['chatboo.session'], …)` con el `env` **del motor** → (b) | El del turno | Sesión propia en `sudo` | Cursor del motor (trabajador del chat), sin marca |

- **JS:** ningún archivo de `static/` llama a `paint_canvas`, ni por `_rpc` ni por `call_kw`; el cliente del
  chat solo usa las rutas JSON de `/chatboo/canvas/*` (`static/src/js/chatboo_charts.js:3005, 3070, 3128,
  3142`). `page_html` no llama a `paint_canvas`.
- **Sandbox:** `paint_canvas` está en `RELAXAICODE_SIDE_EFFECT_METHODS`
  (`pns_ai_mcp/controllers/validators_base.py:264`, bloque del parche 15). Lo bloquean el AST
  (`validators_checks.py:476-484`, cualquier llamada `x.paint_canvas(...)`) y `guarded_getattr`
  (`context_builder.py:220-224`). Además, el código del sandbox no tiene ningún `chatboo.session` a mano: los
  helpers son funciones sueltas. La única vía abierta es la (a), RPC.
- **Portal:** la comparación habla de internos (ACL de `chatboo.session` solo para `base.group_user`,
  `security/ir.model.access.csv:2`). No se ha comprobado si un portal llega hasta `_store_design`: depende
  de si la cadena de diseño (`llm_completion_for_agent`, `pns_ai_mcp/utils/agent_engine.py:315`) lee
  `ai.agent`/`ai.provider` con los permisos del llamador.

**¿Rompería cada llamador una comprobación «la sesión es del usuario real (`self.env.uid`), leída en
`sudo`, o `AccessError`»?**

| Llamador | Efecto |
|---|---|
| (a) RPC | Es lo que se busca: con una sesión ajena, `AccessError` y sin escritura (P-8c). Con la propia, sigue funcionando (y gastando inferencia; ver «Hacerlo privado»). |
| (b), (c) sandbox | No rompe: `_session_of_this_turn` ya ha comprobado el dueño con el mismo uid. |
| (d) botón Canvas | No rompe: el uid del hilo es el de quien pulsó y la ruta ya exige sesión propia. |
| (e) página en espera | No rompe: mismo uid del turno. |
| uid 1 (`SUPERUSER_ID`) | `_session_of_this_turn` admite cualquier sesión con uid 1; una comprobación estricta en `paint_canvas` la rechazaría. Solo afecta si un turno o un job corre como `__system__` (no es el caso de Chatboo, que usa el uid del usuario: `chatboo_async_request.py:658`). Hay que decidir si la excepción se copia. |

**¿Y hacerlo privado (`_paint_canvas`)?**
- Cierra la vía (a) entera: Odoo 14 rechaza por RPC los nombres con `_`
  (`check_method_name`, `/opt/odoo-src/14.0/odoo/addons/web/controllers/main.py:1361` y
  `odoo/service/model.py:174`). También para el dueño (hoy puede pedir diseños por RPC sin pasar por el
  acceso de Chatboo ni por la clave MCP).
- Llamadores que cambian: solo `canvas.py:924` y `:948` (Python, mismo módulo). Ningún JS, vista ni dato.
- En el sandbox ya está bloqueado; con `_` lo bloquearía además `PRIVATE_ATTR`. El nombre de la lista del
  parche 15 (`validators_base.py:264`) y el de `test_seges_chatboo_export.py:40` (`test_names_in_denylist`,
  `test_ast_flags_literal_call`) quedarían sin objeto: habría que decidir si se mantienen como defensa o se
  cambian por el nombre nuevo.
- Las dos medidas no se excluyen: privado cierra el RPC; la comprobación del dueño protege a cualquier
  llamador interno futuro.

## I2. `page_html` (M2): flujo en `sudo` e imágenes

**Flujo confirmado** (`session.py:899-945`):
1. `self` es un `chatboo.session` vacío: en `sudo` desde el sandbox (hechos de base) o del usuario por RPC
   (con `ai_session_ref` en el contexto).
2. `session = _session_of_this_turn(self)` (`:917`) → sesión propia **en `sudo`** (`canvas.py:639`).
3. `pictures_as_tokens(session.env, blocks)` (`:921`) → `session.env` es `su=True` **en las dos vías**.
4. `_picture_of` (`canvas.py:700-710`) → `_web_image_picture` (`canvas.py:677-697`): para cada valor
   `/web/image/<modelo>/<id>/<campo>`, `env[modelo].search([('id', '=', id)])` y `record[campo]` en ese
   entorno, sin ACL, reglas ni grupos de campo, si el base64 empieza como una imagen
   (`_base64_picture`, `:667-674`).
5. Guarda con `_store_design` (superusuario, cursor propio) y devuelve la URL.

**Qué entorno pasan `page_url` y `page_edit` a `pictures_as_tokens`:** `open_page` usa `sessions.env`
(`canvas.py:910`), y `sessions` es el `self` del helper.

| Vía | `sessions.env` | Imágenes |
|---|---|---|
| `page_url`/`page_edit` con filas desde el **sandbox** | **`sudo`** (helper publicado en `sudo`) | **En `sudo`, como `page_html`** |
| `page_url`/`page_edit` por **RPC** | Usuario | Con ACL y reglas |
| Botón Canvas (d) y página en espera (e) | Usuario (`env['chatboo.session']` sin `sudo`) | Con ACL y reglas |
| `page_edit` sin filas | — | No lee imágenes nuevas: `pictures_out` solo cambia por fichas las que ya hay en la página (`canvas.py:755-780`) |

**Corrección a la comparación:** la fila M3 de §8.2 dice que `page_url`/`page_edit` «incrustan imágenes con
el entorno del usuario» y que el fallo es «solo de `page_html`». Eso es cierto por RPC, pero **no desde el
sandbox**, que es la vía de uso normal: allí los tres helpers leen las imágenes en `sudo`. M2 alcanza
también a `page_url` y `page_edit` (con filas).

**Si `page_html` (y `open_page`) usaran el entorno del usuario sin `su`:**
- **Fuera de la caja A (RPC, botón, página en espera):** las imágenes salen con ACL, reglas y grupos de
  campo. Un registro que el usuario no puede leer da `AccessError` en `search` o al leer el campo;
  `_web_image_picture` lo captura (`:691-693`) y la celda se queda sin imagen. Los campos binarios con
  `attachment=True` se leen bien: Odoo 14 consulta `ir.attachment` internamente tras la comprobación del
  registro.
- **Dentro de la caja A (sandbox, cursor marcado):**
  - lo mismo que fuera, y además el guarda del parche 18 rechaza cualquier campo que no sea de
    identificación en los 11 modelos de credenciales (ninguno tiene imágenes que el lienzo use);
  - la transacción `READ ONLY` no molesta: leer imágenes no escribe;
  - la escritura del lienzo sigue fuera (`_store_design`), sin cambio;
  - la comprobación del dueño no cambia: `_session_of_this_turn` puede seguir leyendo la sesión en `sudo`;
    lo que cambia es solo el entorno con el que se leen las imágenes.
- **Efecto funcional:** las skills de fábrica que usan `page_html` (`cash_forecast.py:421`,
  `customer_360.py:590`, `pipeline.py:554`) y la regla del system prompt
  (`pns_ai_mcp/ai/contexts/core/system_prompt.xml:118-121`) apuntan a imágenes de registros que el usuario ya
  ve: no se espera regresión. Desaparecen solo las imágenes que hoy salen gracias al `sudo`.
- **Opciones de alcance** (sin elegir):
  1. solo `page_html` (lo que dice la ficha M2);
  2. `page_html` y `open_page` (cubre también `page_url`/`page_edit` desde el sandbox), que es el alcance
     real del fallo.

## I3. F1: documento, `DATA`, recursos externos y vías de salida

### (a) Dónde se monta y dónde se sirve

- **Montaje:** `paint_canvas` y `page_html` → `place_rows_on_page(…, captured=True)` (`canvas.py:2068-2111`):
  `bind_const_title` y `bind_script_row_json`/`bind_const_data` escriben las filas y el título dentro de los
  `<script>` del diseño → `swap_pictures` (`:743-752`) → `_store_design` (`chatboo.session.canvas_design`).
  Compartir copia ese HTML en `chatboo.canvas.page.design` (`chatboo.py:1188-1196`).
- **Carcasa** (`canvas_page`, `canvas.py:500-573`): página nuestra con los botones (imprimir, descargar,
  compartir) y un `<iframe id="pns-frame" sandbox="allow-scripts allow-modals" srcdoc="…">` (`:568-570`). El
  marco se carga **por `srcdoc`**, no por URL: el diseño (con `_with_theme`, `_HIDDEN_HIDES` y
  `_PRINT_BRIDGE`) va escapado con `html.escape(…, quote=True)` en el atributo (`:512-516`). Scripts propios
  de la carcasa: `_SHARE_SCRIPT` (`:296`, hace `fetch` a `/chatboo/share/people` y `POST` a la ruta de
  compartir), `_THEME_SCRIPT` (`:163`) y un `onclick` en línea en el botón de imprimir (`:529-533`). La
  carcasa no escucha `message`; los dos oyentes están dentro del marco y miran `e.source === window.parent`
  (`:131, 152`).
- **Rutas y cabeceras:**

| Ruta | Archivo:línea | Qué sirve | Cabeceras propias |
|---|---|---|---|
| `GET /chatboo/canvas/<session_id>` | `chatboo.py:1133-1155` | Carcasa con `srcdoc` (lienzo de la sesión propia) | Solo `Content-Type: text/html; charset=utf-8` |
| `GET /chatboo/page/<page_id>` (compartida) | `chatboo.py:1220-1244` | Misma carcasa con `srcdoc` (página legible por las reglas) | Solo `Content-Type` |
| `GET /chatboo/canvas/<id>/download` | `chatboo.py:1270-1295` | `downloadable_page(design)` (`canvas.py:437-476`): el diseño con botones propios, **sin marco ni `sandbox`** | `Content-Type`, `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff` |
| `GET /chatboo/page/<id>/download` | `chatboo.py:1246-1268` | Igual | Igual |

  Ni Odoo 14 ni los módulos añaden `Content-Security-Policy` ni `X-Frame-Options` a estas respuestas (Grep:
  la única CSP de los módulos es `pns_ai_mcp/controllers/remote_image.py:38`; en el core, `X-Frame-Options`
  solo en `web/controllers/main.py:902, 966`). Observación: sin `X-Frame-Options`, otra web puede enmarcar
  la carcasa (botón Compartir con su CSRF); es la autenticación de Odoo la que lo limita.
- **Herencia de CSP en `srcdoc`:** según la especificación HTML, un documento `srcdoc` hereda la política
  (contenedor de políticas) de su padre, también con `sandbox`. Una CSP en la cabecera de la carcasa se
  aplicaría al marco; tendría que admitir los scripts en línea de la carcasa y del diseño, y el `fetch` de
  `_SHARE_SCRIPT`. Cómo resuelve `'self'` cada navegador en un `srcdoc` de origen opaco **está por verificar
  en navegador**: no se ha probado.

### (b) Serialización de filas y otros valores dentro de `<script>`

| Punto | Archivo:línea | Qué escribe | Escape de `</` |
|---|---|---|---|
| Página de rescate | `_page_for_rows`, `canvas.py:1089-1112` (`:1097`, `:1109`) | `<script>const DATA=…;</script>` con `json.dumps(_flat_rows(blocks))` | **No** |
| `const DATA` del diseño | `bind_const_data`, `canvas.py:1476-1503`, con `_payload_for_const_data` (`:1423-1434`): `figures_for_design` (`:811-819`) o `json.dumps(_flat_rows(…))` (`:1434`) | Las filas de la ejecución | **No** |
| Otras matrices con las mismas columnas | `bind_script_row_json`, `canvas.py:1708-1750` (`:1741`) | `json.dumps(best)` | **No** |
| `const TITLE` | `bind_const_title`, `canvas.py:1440-1473` (`:1447`) | `json.dumps(title)` (el título viene de las filas, de la petición del botón o del modelo) | **No** |
| Vigilante de filas | `_spare_rows_watch`, `canvas.py:2191-2215` (`:2200`) | `json.dumps(rows).replace('</', '<\\/')` | **Sí** (el patrón del fabricante) |
| Panel de compartir | `_share_panel`, `canvas.py:387-428` (`:404-405`) | `json.dumps` en atributos `data-*`, escapado con `attr` | No aplica (atributo, no `<script>`) |
| Captura de skill | `canvas.py:2052-2053` | `json.dumps` dentro de código Python de la skill | No aplica (no es HTML) |

- `json.dumps` con `ensure_ascii=False` no escapa `<`, `>` ni `&`. Un valor con `</script><script>…` cierra
  el bloque en el analizador HTML y ejecuta lo que sigue dentro del marco (P-8e, a).
- El escape del fabricante (`</` → `<\/`) cierra `</script>`. No cubre la secuencia `<!--` seguida de
  `<script` dentro de un script (estado «doble escapado» del analizador), que puede romper el bloque de
  otra forma. Escapar `<` como `\u003c` cubre los dos casos y sigue siendo JSON válido. Es una opción, sin
  elegir.

### (c) Recursos externos

- **Prompt de diseño** (`_PAGE_RULES`, `canvas.py:24-86`; `DESIGN_SYSTEM` y `EDIT_SYSTEM`, `:87-113`): la
  única regla de red es «Do not fetch and do not call APIs» (`:43`). **No dice nada** de librerías, fuentes,
  CDN, hojas de estilo ni imágenes externas: ni las permite ni las prohíbe. Un diseño con Chart.js de un
  CDN o Google Fonts cumple el prompt.
- **Filas con imágenes externas:** el system prompt pide poner una imagen `http(s)` como URL desnuda en la
  celda (`system_prompt.xml:120`). `_picture_of` no las convierte (solo `data:`, `/web/image` y base64), así
  que llegan a `DATA` y el marco las carga directamente del host externo. Es un uso legítimo: una CSP con
  `img-src` cerrado lo rompería, salvo lista de hosts o paso por `/pns_ai_mcp/remote_image` (que exige
  sesión de Odoo, `remote_image.py:24`, y el marco no la tiene).
- **`lab_pns_ai_3879_14` (29/10/2026):** `chatboo_session` tiene 6 filas y **ninguna con `canvas_design`**;
  `chatboo_canvas_page` tiene **0 filas**. El recuento de `src=`/`href=` con `http(s)` externo, agrupado por
  host, sale **vacío**; también 0 en `url()` externo, `@import`, `fetch`/`XMLHttpRequest`/`sendBeacon`/
  `WebSocket`, `<form>` y navegación. El laboratorio no tiene muestra: la muestra útil está en el staging
  `pns_demo` (y en LIYBEN), donde la consulta la decide Sergio. Consulta usada (solo recuentos, sin
  contenido):

  ```sql
  BEGIN READ ONLY;
  WITH docs AS (
    SELECT 'chatboo_session' AS tabla, id, canvas_design AS d FROM chatboo_session
     WHERE coalesce(canvas_design, '') <> ''
    UNION ALL
    SELECT 'chatboo_canvas_page', id, design FROM chatboo_canvas_page WHERE coalesce(design, '') <> ''
  ), hits AS (
    SELECT tabla, id, lower(m[2]) AS atributo, lower(m[3]) AS host
      FROM docs, regexp_matches(d, '(^|[\s<"''])(src|href)\s*=\s*["'']?https?://([^/"''\s>:?#]+)', 'gi') AS m
  )
  SELECT tabla, host, atributo, count(*) AS apariciones, count(DISTINCT id) AS documentos
    FROM hits GROUP BY 1, 2, 3 ORDER BY 1, 5 DESC, 4 DESC;
  ROLLBACK;
  ```

### (d) Vías de salida con `sandbox="allow-scripts allow-modals"` que una CSP en `<meta>` no cubre

Lo que el `sandbox` ya cierra (sin `allow-forms`, `allow-popups`, `allow-top-navigation`,
`allow-same-origin` ni `allow-downloads`): envío de formularios, `window.open` y enlaces `target=_blank`,
navegar la pestaña de arriba, la sesión y las cookies de Odoo, y las descargas.

Lo que queda y una CSP en `<meta>` (dentro del documento) **no** cubre:
1. **Autonavegación del marco:** `location = 'https://host/?d=…'`, `<meta http-equiv="refresh">` o un clic
   en un enlace sin `target`. Ninguna directiva CSP implantada la limita (`navigate-to` no existe en los
   navegadores) y ninguna opción de `sandbox` la impide. El documento nuevo ya no tiene la CSP del anterior.
2. **WebRTC:** `RTCPeerConnection` con un servidor STUN/TURN propio saca datos en la negociación ICE; no
   hay directiva CSP implantada que lo cierre.
3. **DNS:** `<link rel="dns-prefetch">` y `preconnect` resuelven nombres sin que la CSP los frene en todos
   los navegadores (fuga por la consulta DNS).
4. **Lo que se ejecuta antes del `<meta>`:** una `<meta>` solo vale desde donde aparece. Si la pone el
   servidor, tiene que ir la primera en `<head>`; si la escribe el modelo, no sirve. Una CSP en `<meta>` no
   admite `report-uri`, `frame-ancestors` ni `sandbox`.
5. **Modales (`allow-modals`):** `prompt()`/`confirm()` permiten pedir datos al usuario con aspecto de
   diálogo del navegador («formularios falsos», punto 3 de F1). La CSP no los regula; lo que se escriba solo
   sale por las vías 1 a 3.
6. **El HTML descargado** se abre sin `sandbox` en local (`file://`): ahí solo vale una `<meta>` que viaje
   con el archivo; una cabecera de la carcasa no le llega.

Lo que una CSP (en `<meta>` o heredada de la cabecera) **sí** cierra: `fetch`, `XMLHttpRequest`,
`sendBeacon`, `WebSocket` y `EventSource` (`connect-src`), imágenes y fondos CSS (`img-src`), scripts,
estilos y fuentes externas (`script-src`, `style-src`, `font-src`), marcos y `object` anidados
(`frame-src`, `object-src`) y workers (`worker-src`).

**Opciones para F1** (sin elegir; se pueden combinar):
- **CSP en `<meta>`** insertada por el servidor como primer elemento de `<head>` del diseño: viaja con el
  `srcdoc` y con la descarga.
- **CSP en la cabecera de la carcasa**, heredada por el `srcdoc` (por verificar en navegador): no la puede
  quitar el diseño, pero obliga a ajustar los scripts de la carcasa.
- **Grado de cierre de red:** cerrar todo (rompe CDN, fuentes e imágenes externas) o una lista de hosts
  (por ejemplo la de PNS-59). Hay que decidir qué hacer con las librerías de CDN; cambiar el prompt para
  prohibirlas es otra opción.
- **Escape en `DATA` y `TITLE`:** `</` → `<\/` (el del fabricante) o `<` → `\u003c`, en los cuatro puntos de
  la tabla (b).
- **Autonavegación del marco** (vía 1): solo se puede detectar desde la carcasa (por ejemplo, contar los
  `load` del marco y vaciarlo); no se puede impedir. Queda como riesgo aceptado u opción aparte.
- **Descarga** (punto 4 de F1): con o sin CSP en `<meta>` dentro del archivo.

## I4. D1: páginas compartidas

- **Modelo** (`page.py:25-176`): `chatboo.canvas.page`, `mail.thread`; `owner_id` requerido, por defecto el
  usuario, `ondelete='cascade'` (`:37-44`); `user_ids` con `domain=[('share', '=', False)]` (`:45-52`), que
  **solo** aplica en la interfaz; `design` y `name` editables.
- **ACL:** `base.group_user` `1,1,1,1` (`security/ir.model.access.csv:4`).
- **Reglas** (`security/security.xml:43-76`), de grupo, que Odoo 14 combina con «o»:
  - lectura: dueño o lector nombrado (`:44-53`);
  - escritura, alta y borrado: dueño (`:56-65`);
  - **AI Administrator:** `[(1, '=', 1)]` con los cuatro permisos (`:67-76`): lee, cambia, crea y borra
    **todas** las páginas.
- **`write` y el cambio de `owner_id`:** `write` (`page.py:76-84`) no limita campos. En Odoo 14 la regla
  se comprueba **antes** de escribir (`/opt/odoo-src/14.0/odoo/odoo/models.py:3593-3595`) y no después: el
  dueño puede poner `owner_id` = otro usuario (P-8h). Detalle que no recoge la comparación: si en el mismo
  `write` cambia `owner_id` y añade lectores, `_tell_new_readers` corre **después** de escribir y el aviso
  dice «<nuevo dueño> shared a page with you» (`_inbox_note`, `:132-139`); el autor del mensaje sigue siendo
  quien escribe (`message_notify` calcula el autor del usuario actual). El alta, en cambio, sí se comprueba
  después de crear: un usuario normal no crea páginas a nombre de otro, pero sí puede pasárselas después.
- **Qué hace hoy el AI Administrator por su regla:**
  - **Menú** «Shared pages» bajo AI › Security (`views/chatboo_canvas_page_views.xml:75-79`; el padre
    `pns_ai_mcp.menu_ai_security` es visible para AI Administrator, AI Writer y los grupos de URL y API
    externas, `pns_ai_mcp/views/mcp_user_views.xml:162-166`). Lista y formulario (`:6-47`) con todas las
    páginas, sus dueños y lectores; botones «Open page» y «Stop sharing»; borrado desde la lista (no tiene
    `delete="0"`); en el formulario puede cambiar `user_ids` (y, por tanto, avisar a quien quiera);
    `owner_id` es de solo lectura **en la vista**, no en el ORM.
  - **Rutas:** abre `/chatboo/page/<id>` y su descarga de cualquier página (`_readable_page`,
    `chatboo.py:1212-1218`), con los datos incrustados de su dueño aunque él no pueda leer esos
    registros. `/chatboo/page/<id>/people` exige además ser el dueño (`:1205`).
  - **Por RPC:** cambia `design` o `name` de una página ajena (los lectores ven el HTML nuevo en la URL de
    Odoo), cambia `owner_id` o crea páginas a nombre de cualquiera.
  - **Crons:** ninguno toca `chatboo.canvas.page` (Grep en `data/` y modelos). La limpieza de sesiones no
    borra páginas; solo las borra el `cascade` al borrar al usuario dueño.
- **`message_notify` al compartir** (`_notify_inbox`, `page.py:121-130`, desde `create` y `write`):
  - avisa a los socios de los usuarios **añadidos** a `user_ids`, menos el dueño (`:86-95`), y les manda un
    aviso por el bus (`:96-119`);
  - por la ruta de compartir solo entran internos (`people_named` filtra `share`, `:151-157`); **por ORM**
    entra cualquier `res.users`, también de portal (el `domain` del campo no se aplica en el servidor). Un
    portal no puede leer la página (sin ACL), pero recibe la notificación, por correo si su preferencia es
    esa (`message_notify`, `/opt/odoo-src/14.0/odoo/addons/mail/models/mail_thread.py:2022-2060`);
  - el contenido es fijo salvo el asunto (`name`, texto libre del dueño) y el nombre del dueño; el cuerpo es
    `Markup` con los valores escapados;
  - lo pueden disparar el dueño de cada página y el AI Administrator sobre cualquiera.
- **Opciones** (sin elegir):
  - `owner_id` no modificable salvo por el sistema (o por el AI Administrator);
  - regla del AI Administrator: mantenerla (decisión de diseño del fabricante), dejarla en solo lectura o
    limitarla a borrar;
  - `user_ids`: solo usuarios internos también por ORM (como la ruta), lo que corta los avisos a portal.

## I5. La ventana del parche 18: ¿puede salir de la caja A la llamada de diseño?

**Cómo funciona hoy la página «en espera»:**
- `page_url` sin filas llama a `open_page`, que no encuentra material y guarda con `note_page_waiting`
  (`canvas.py:894-907`) un `fulfill(env, later)` que vuelve a llamar a `open_page(env['chatboo.session'], …)`.
- El `dict` `page_request` lo planta el motor en su contexto (`pns_ai_mcp/utils/agent_engine.py:896-899`) y
  la caja A lo comparte por referencia (hechos de base).
- Cuando la herramienta devuelve, el motor, ya fuera de la caja A y con su cursor sin marca, llama a
  `fulfill_waiting_page(self.env, payload)` (`engine_tool_run.py:383-406`): si el resultado no trae URL y sí
  filas (`blocks_on_payload`), ejecuta el `fulfill` con esas filas, pone `payload['page_url']` y reenvuelve el
  resultado de la herramienta (`rewrap_tool_payload`, `:400-401`), así que el modelo ve la URL.
- El contexto `page_tab` ya lo describe al modelo: «A call with no rows does not lay the page out (the server
  waits and uses the rows when they exist)» (`pns_ai_chatboo/ai/contexts/domain/page_tab/page_tab.xml:22-23`).

**`page_url` con filas, aplazada como la página en espera:**
- **Qué devolvería al código del sandbox:** una cadena vacía (como hoy sin filas). No hay URL «provisional»
  posible sin tocar el motor: si el resultado ya trae `page_url`, `fulfill_waiting_page` no hace nada
  (`result_page.py:169-172`).
- **Qué vería el usuario:** lo mismo que hoy en el patrón del contexto (`'page_url': page_url(rows, …)` dentro
  del resultado, `page_tab.xml:27-31`, y el patrón de «soft fail», `:75-82`): el motor rellena la URL y la
  tarjeta sale igual. El diseño tarda lo mismo, pero fuera de la caja A, que deja de estar abierta (cursor
  `READ ONLY`) durante los minutos del diseño.
- **Diferencias:**
  - las filas del lienzo serían las del **resultado** (`blocks_on_payload`), no las que el código pasó a
    `page_url`, salvo que el `fulfill` guarde las suyas (son datos planos);
  - si el resultado no lleva filas (solo `page_url`), hoy no se rellenaría: `fulfill_waiting_page` sale sin
    filas (`:174-176`);
  - el código no puede usar la URL dentro del propio resultado (por ejemplo, en el texto);
  - con las filas leídas en el entorno del motor, las imágenes se leen con el usuario, sin `sudo` (cierra
    también M2 para `page_url`, ver I2);
  - solo funciona donde el motor ejecuta `fulfill_waiting_page` (turnos de Chatboo). Por `/mcp` no hay
    sesión de Chatboo y hoy ya devuelve `''`. Los slash de skills usan `page_html`, que no llama al
    diseño; **no se ha comprobado** que el camino de los slash ejecute `fulfill_waiting_page`.
- **`page_edit` sin filas** (el caso habitual de un cambio, `page_tab.xml:39-57`): **no es viable sin tocar
  el motor.** No hay filas que esperar: `fulfill_waiting_page` exige `blocks` en el resultado
  (`result_page.py:174-176`) y el resultado de un cambio solo trae `summary` y `page_url`. Aplazarlo
  obliga a cambiar el contrato de `fulfill_waiting_page` en `pns_ai_mcp` (ejecutar el `fulfill` sin filas).
  Es un cambio acotado, pero en el motor, no en el lienzo.
- **¿Se podría eliminar `_box_a_trusted`?** Solo si **ningún** camino llama al diseño con el cursor marcado:
  `page_url` con filas y `page_edit` con y sin filas. Si se aplazan los tres, la ventana deja de hacer
  falta: se elimina `_box_a_trusted` (`pns_ai_mcp/models/box_a_guard.py:66-83`), su importación
  (`session.py:17`) y la envoltura `_ask_design` vuelve a ser el cuerpo del fabricante (`_ask_design_raw`,
  `:1202`). Si queda alguno, la ventana sigue haciendo falta para ese.
- **Tests de `pns_ai_chatboo/tests/test_seges_canvas_box_a.py` que cambiarían:** los 6 prueban la ventana
  (`test_design_call_reads_provider_in_box_a`, `test_only_design_leaves_the_window`,
  `test_window_takes_plain_strings`, `test_mark_restored_when_design_fails`,
  `test_guard_still_closed_after_window`, `test_cache_closed_after_window_prefetch`). Sin ventana, sobran o
  se sustituyen por tests de lo contrario: con la marca puesta, `page_url`/`page_edit` no llaman al driver,
  devuelven `''` y dejan el `fulfill`; fuera de la caja A, el `fulfill` llama al diseño. Los de
  `test_seges_sandbox_credentials.py` no dependen de la ventana.
- **Resumen:** `page_url` con filas puede salir de la caja A con el mecanismo actual, con las diferencias
  dichas; `page_edit` sin filas, no, sin tocar `fulfill_waiting_page`. Quitar la ventana del todo exige ese
  cambio en el motor.

## I6. R8: proveedores de diseño en el laboratorio

`SELECT` en `lab_pns_ai_3879_14` (29/10/2026; sin `api_key`):

| id | Nombre | Protocolo | Modelo | Activo | Conversación | Visión | Decisión | **Diseño** |
|---|---|---|---|---|---|---|---|---|
| 1 | Gemini 3.6 flash | openai | `models/gemini-3.6-flash` | Sí | Sí | Sí | No | **No** |
| 2 | Gemini 3.5 flash | openai | `models/gemini-3.5-flash` | Sí | Sí | Sí | No | **No** |
| 3 | OVH | openai | `Qwen3.5-397B-A17B` | Sí | Sí | Sí | No | **No** |
| 4 | Gemini 3.5 flash lite | openai | `models/gemini-3.5-flash-lite` | Sí | Sí | Sí | No | **No** |

(Audio y vídeo, «No» en los cuatro; «Sin failover externo», «No» en los cuatro.)

Cadena del agente `pns_ai_chatboo` (`ai_agent_provider`, agente 3): prioridad 0, Gemini 3.6 flash (1);
prioridad 1, Gemini 3.5 flash (2); prioridad 2, Gemini 3.5 flash lite (4). Todas las filas activas. OVH no
está en la cadena de Chatboo.

- **Hoy no hay ningún proveedor con la casilla de diseño en el laboratorio:** `canvas_available` da falso y
  ninguna página se puede crear (`paint_canvas` acaba en «no design provider» en `ai.log`). R8 en el
  laboratorio exige primero marcar «Design» en un proveedor de la cadena.
- **Modelos de diseño que no son `lite` disponibles:** Gemini 3.6 flash y Gemini 3.5 flash (en la cadena), y
  OVH (fuera de la cadena: habría que añadirlo).
- La casilla excluye al proveedor del resto de necesidades si es la única marcada (`provider_fits`,
  `pns_ai_mcp/utils/provider_fit.py:14-25`): marcar solo «Design» en uno de la cadena le quita la
  conversación. Marcar «Design» además de «Conversación» lo deja para las dos cosas.
- Si solo hay un proveedor de diseño y falla (503, como el 27/10/2026), no hay failover de diseño a otro:
  para no repetir el no concluyente de E1′, conviene que haya dos con la casilla y ninguno `lite`, o
  aceptar que un fallo del proveedor deja R8 sin resultado.
- **Staging:** no consultado desde aquí. La configuración de diseño de `pns_demo` (qué proveedor tenía la
  casilla el 26 y 27/10/2026) hay que mirarla allí con el mismo `SELECT` antes de repetir R8.

## Decisiones para Sergio

1. **M1:** comprobación del dueño en `paint_canvas`, hacerlo privado o las dos cosas; y si se copia la
   excepción de uid 1 de `_session_of_this_turn`. Si se hace privado, qué hacer con `paint_canvas` en la
   lista del parche 15 y en su test.
2. **M2:** alcance: solo `page_html` (ficha original) o también `open_page` (`page_url`/`page_edit` desde el
   sandbox, que hoy también leen imágenes en `sudo`). Anotar la corrección a la fila M3 de la comparación.
3. **F1:**
   - dónde va la CSP (`<meta>` insertada por el servidor, cabecera de la carcasa heredada por el `srcdoc`, o
     las dos);
   - cuánto se cierra la red: todo, o lista de hosts; qué hacer con librerías, fuentes y CDN (prompt y CSP)
     y con las imágenes externas de las filas;
   - qué escape en `DATA`/`TITLE` (`<\/` o `<`);
   - autonavegación del marco, WebRTC y DNS: riesgo aceptado o medida aparte en la carcasa;
   - la descarga: con o sin CSP dentro del archivo;
   - si se repite la consulta de hosts en `pns_demo` (y en LIYBEN) para ver qué usan hoy los diseños.
4. **D1:** `owner_id` fijo; qué permisos deja la regla del AI Administrator; `user_ids` solo internos también
   por ORM.
5. **Ventana del parche 18:** mantenerla; sacar solo `page_url` con filas fuera de la caja A (la ventana
   sigue para `page_edit`); o cambiar también `fulfill_waiting_page` en el motor para `page_edit` y quitar
   `_box_a_trusted` (con el cambio de los 6 tests).
6. **R8:** qué proveedor no `lite` se marca como de diseño en el laboratorio (y en el staging), si con o sin
   «Conversación», y si se marca un segundo para tener failover de diseño. Es un cambio de datos en las dos
   BD: lo decide y lo hace Sergio.

## Propuesta final (29/10/2026)

Decisiones de Sergio del 29/10/2026, aprobadas. Regla N11 en todos los parches: cambio mínimo, Python
3.7.3, sin tocar `version`, `depends`, `external_dependencies`, `i18n`, `LICENSE` ni `NOTICE`; marcador
`# Seges: parche N (<ficha>, seguridad)` junto a cada cambio; un test negativo de Seges por parche.

1. **M1 → parche 25.** `paint_canvas` pasa a privado (`_paint_canvas`) y además comprueba el dueño dentro:
   `ensure_one`; la sesión, leída en `sudo`, es de `self.env.uid`, o `AccessError` sin escribir. **Sin** la
   excepción de uid 1. La lista del parche 15 (`validators_base.py:264`) y sus tests no se tocan.
2. **M2 → parche 26.** `page_html` y `open_page` leen las imágenes con el entorno del usuario sin `su`
   (`session.env(su=False)` / `sessions.env(su=False)`) al llamar a `pictures_as_tokens`.
   `_session_of_this_turn` no se toca. Alcance: el de I2, opción 2.
3. **F1 → parche 27.**
   - a) Una función única que serializa valores para meterlos dentro de `<script>`: JSON con `<`, `>`, `&`,
     U+2028 y U+2029 escapados como `\u003c`, `\u003e`, `\u0026`, `\u2028` y `\u2029`. Se usa en los cinco
     puntos de la tabla I3 (b): página de rescate, `const DATA`, otras matrices, `const TITLE` y el vigilante
     (`:2200`).
   - b) CSP en `<meta http-equiv="Content-Security-Policy">`, insertada por el servidor **al servir** (no al
     guardar), como primer elemento de `<head>` del documento del diseño (se crea si no existe). Va en el
     `srcdoc` de la carcasa (`canvas_page`: `/chatboo/canvas/<id>` y `/chatboo/page/<id>`) y en
     `downloadable_page` (las dos descargas). Política: `default-src 'none'; script-src 'unsafe-inline';
     style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; form-action 'none';
     base-uri 'none'; frame-src 'none'; object-src 'none'; worker-src 'none'`.
   - c) Regla nueva en `_PAGE_RULES`, en inglés: sin librerías, fuentes, hojas de estilo ni imágenes
     externas; los gráficos, con SVG en línea o `<canvas>`.
   - d) Cabecera `X-Frame-Options: SAMEORIGIN` en `GET /chatboo/canvas/<session_id>` y
     `GET /chatboo/page/<page_id>`.
   - e) Riesgo aceptado, documentado en la entrada: autonavegación del marco, WebRTC y DNS (I3 d, vías 1 a
     3); las imágenes `http(s)` externas de las filas dejan de verse en el lienzo.
4. **D1 → parche 28.** `owner_id` de `chatboo.canvas.page` no se puede cambiar fuera de `sudo` (nadie,
   tampoco el AI Administrator); `user_ids` solo admite usuarios internos, también por ORM (constraint); la
   regla del AI Administrator (`security.xml:67-76`) pasa a leer y borrar, sin escribir ni crear.
5. **Ventana del parche 18: se mantiene.** Motivos (I5): sacar solo `page_url` no la elimina, porque
   `page_edit` la necesita, y cambia el comportamiento; quitarla exige cambiar `fulfill_waiting_page` en
   `pns_ai_mcp` y sustituir 6 tests; está acotada y validada en staging; con el parche 26 no da más acceso.
6. **R8:** con un modelo de diseño que no sea `lite`: Gemini 3.6 flash y 3.5 flash, con «Design» y
   «Conversación». Las casillas las marca Sergio.

### Comprobaciones previas (paso 0, 29/10/2026) y decisiones añadidas

- **Proveedores:** en `lab_pns_ai_3879_14`, `fit_design` = falso en los cuatro, y los cuatro tienen
  conversación. Ningún `lite` tiene diseño. Decisión de Sergio: se sigue con la implementación, y marcar
  «Design» en los dos es el paso previo de las pruebas manuales ([lab_e3_3879.md](lab_e3_3879.md)).
- **Regla del AI Administrator:** `<data noupdate="0">` (`security.xml:7`) y `ir_model_data.noupdate` = falso
  en las 6 reglas de `pns_ai_chatboo`: el `-u` la cambia en las BD existentes.
- **Enmarcado:** nada enmarca la carcasa. El chat abre las páginas con `window.open(…, '_blank', 'noopener')`
  (`static/src/js/chatboo_charts.js:3055`, `chatboo_systray.js:226`) y la lista «Shared pages», con
  `act_url` en una pestaña nueva (`chatboo_canvas_page.py:170-176`). El único `<iframe>` del JS es el visor
  de PDF (`chatboo_pdf_viewer.js:109`).
- **`paint_canvas` por su nombre:** solo `canvas.py:924` y `:948`, la lista del parche 15
  (`validators_base.py:264`) y su test (`test_seges_chatboo_export.py:40`). Ningún test del fabricante, JS,
  vista, dato ni el repo del laboratorio.
- **Regla nueva del AI Administrator sobre páginas ajenas:** «Stop sharing» (`action_unshare`, un `write`)
  da `AccessError`; el formulario deja cambiar en pantalla `name` y `user_ids`, pero al guardar da
  `AccessError`; «Open page», la descarga y el borrado desde la lista siguen funcionando. No se cambian las
  vistas.
- **Imágenes que no son `data:`:** las de las filas pasan a `data:` base64 (`pictures_as_tokens` y
  `swap_pictures`). Quedan fuera las URL `http(s)` de las celdas (riesgo aceptado, 3 e), los `/web/image/…`
  que no se pueden leer (se quedan como texto en `DATA`) y lo que el diseño escriba por su cuenta (un logo
  por `/web/image`, un CDN). El laboratorio no tiene diseños guardados: la comprobación visual queda para
  las pruebas manuales.
- **Línea base:** los registros no tienen la batería completa después del parche 23 ampliado y el 24. Se
  ejecutó antes de cambiar nada (log `tests-20261029-160733.log`): **386 tests, 18 F y 32 E**
  (`pns_ai_mcp` 358, `pns_ai_chatboo` 28); ninguno de los 50 es de Seges.
- **Dos puntos de F1 que no insertan JSON puro** (decisiones de Sergio del 29/10/2026):
  - `figures_for_design` (rama de bloques de `const DATA`, `_payload_for_const_data`): si `json.dumps`
    falla, devuelve `str(blocks)`. **Decisión:** se escapa su texto con el mismo paso de escape de la
    función única; `figures_for_design` no se toca. En JSON el escape textual es exacto (esos caracteres
    solo aparecen dentro de cadenas). En el repr no sale JSON, igual que hoy, pero ya no puede cerrar el
    `<script>`.
  - `swap_pictures` (punto nuevo, fuera de la tabla I3 b): vuelve a meter el valor de la imagen sin
    escapar, en `DATA` y en `<img src>`, y `_picture_of` aceptaba cualquier valor que empezara por
    `data:image/`. **Decisión:** dentro del parche 27, un valor `data:image/` solo cuenta como imagen si es
    exactamente `data:image/<tipo>;base64,<base64>` (`_DATA_URI_RE`); si no, queda como texto y lo
    serializa la función única.

### Revisión (29/10/2026): B1 y decisión de Sergio

- `odoo-reviewer` rechazó la primera versión del parche 27 b (**B1**): `_with_csp` buscaba el `<head>` del
  diseño con expresiones regulares que no siguen HTML5, y con comentarios raros, BOM, espacios que no son
  de HTML, etiquetas con guion, atributos con `>` o `<?xml …?>` la CSP llegaba tarde, acababa en `<body>` o
  la descarga pasaba a modo quirks.
- **Decisión de Sergio:** no se analiza el diseño. Al servir, como último paso, se antepone en el byte 0
  el prefijo fijo `<!DOCTYPE html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" …>` y
  después el documento tal cual, en el `srcdoc` de la carcasa (antes del escape de atributo) y en las dos
  descargas, también para los diseños guardados antes. Coste aceptado: un diseño sin doctype pasa de modo
  quirks a estándar. Con ese prefijo, la CSP es el **segundo** hijo de `<head>` (detrás de la de
  `charset`) y va antes que cualquier cosa del diseño.
- m1 (tests con el prefijo exacto y los casos de B1), m2 (mensaje en `test_foreign_session_refused`), m3
  (lectores de portal guardados: observación y `SELECT` en el laboratorio, el staging y LIYBEN) y m4 (404
  sin `X-Frame-Options`, aceptada).
- Detalle, comprobación con html5lib y neutralización: [registro](parches_pns_ai.md), «Revisión de E3′
  (29/10/2026)».

- **Errata (30/10/2026):** restituidas las secuencias de escape perdidas al escribir (puntos sobre `_script_safe` y el escape de `<`).
