# Propuesta de la fase 4 sobre 3.1.973 (parche 27)

- **Fecha:** 13/11/2026. **Rama:** `14.0-pns-ai-3973`. **Laboratorio:** `lab_pns_ai_3973` (BD `lab_pns_ai_3973_14`).
- **Base:** `pns_base` 14.0.1.2.69 · `pns_ai_mcp` 14.0.3.1.973 · `pns_ai_chatboo` 14.0.2.1.587, con los parches de las
  fases 2 y 3.
- **Plan:** [plan_correccion_pns_ai_3973.md](plan_correccion_pns_ai_3973.md), decisión 6, «Fase 4» y «Planificación
  hasta el staging».
- **Registro:** [parches_pns_ai.md](parches_pns_ai.md), «Parche 27: el lienzo no deja salir datos (F1)» y «Revisión de
  E3′ (29/10/2026): B1 del parche 27 b y nueva versión» (rama 3879).
- **Laboratorio:** [lab_procedimiento_3973.md](lab_procedimiento_3973.md).
- **Comparación con 3.1.973:** [comparacion_pns_ai_3-1-973.md](../specs/comparacion_pns_ai_3-1-973.md), §3.7 y §9 (P-9).
- **Estado:** parche 27 implementado y validado (13/11/2026). Comprobación previa hecha y decidida; propuesta aprobada
  con las decisiones D1 a D5 (abajo, «Decisiones de Sergio»); resultados en «Implementación y resultados del parche 27
  (13/11/2026)».

Las líneas son del árbol actual (rama en `b30d834`), salvo que se diga otra cosa. «3879» es la rama
`14.0-pns-ai-3879`. «Diff de la fase 0» es `~/pns_ai_3973/fase0/diffs/pns_ai_chatboo+models+chatboo_canvas.py.diff`.

## Comprobación previa de la CSP (13/11/2026)

Objetivo (plan, fase 4): comprobar, antes de proponer el 27, que el lienzo de 3.1.973 sigue pintando sin `'self'`
cuando se añade la `<meta>` de Seges a la cabecera HTTP del fabricante (decisión 6).

### A1. Dónde se escribe JSON dentro de un `<script>` del lienzo

En `pns_ai_chatboo/models/chatboo_canvas.py`, la única diferencia frente a 3.1.973 limpia es la línea del parche 26 en
`:910`, que desplaza +1 todo lo que viene después.

| 3.1.973 | Actual | Función | Destino | ¿Entra en el 27? |
|---|---|---|---|---|
| 1097 | 1098 | `_page_for_rows` | `<script>const DATA=%s;</script>` (`:1110`) | Sí |
| 1425 | 1426 | `_payload_for_const_data`, rama de bloques (`return dumped` de `figures_for_design`) | `const DATA` | Sí (el plan no la citaba) |
| 1426 | 1427 | `_payload_for_const_data`, filas planas | `const DATA` | Sí |
| 1439 | 1440 | `bind_const_title` | `const TITLE` | Sí |
| 1733 | 1734 | `bind_script_row_json` | otras matrices dentro de cada `<script>` (`_SCRIPT_INNER_RE.sub`, `:1745`) | Sí (el plan no la citaba; la 3879 sí la cubría) |
| 2194 | 2195 | `_spare_rows_watch` | `var ROWS=%s` del vigilante | Sí (el fabricante solo cambia `</`) |
| 2046-2047 | 2047-2048 | `wrap_captured_page` | **código Python** del sandbox (`_page_template = …`), no HTML | No |

Fuera del marco: `_share_panel` (`:404-405`) escribe JSON en atributos de la página exterior, con
`html.escape(quote=True)`. No aplica.

### A4. Política resultante

En el marco del diseño (`srcdoc`) se aplican las dos: la cabecera de la página exterior, que el marco hereda, y la
`<meta>`. En las descargas solo se aplica la `<meta>`, porque las rutas no envían CSP. En la página exterior solo se
aplica la cabecera.

| Directiva | Fabricante (`chatboo.py:1175-1180`) | `<meta>` de Seges | Efectiva en el marco | Efectiva en las descargas |
|---|---|---|---|---|
| `default-src` | `'none'` | `'none'` | `'none'` | `'none'` (antes, ninguna) |
| `script-src` / `style-src` | `'unsafe-inline'` | `'unsafe-inline'` | `'unsafe-inline'` | `'unsafe-inline'` |
| `img-src` | `'self' data: blob:` | `data: blob:` | `data: blob:` (sin `'self'`) | `data: blob:` |
| `font-src` | `data:` | `data:` | `data:` | `data:` |
| `connect-src` | `'self'` | `'none'` | `'none'` (sin `'self'`) | `'none'` |
| `form-action` / `base-uri` | `'none'` | `'none'` | `'none'` | `'none'` |
| `frame-src` / `object-src` | `'none'` (por `default-src`) | `'none'` | `'none'` | `'none'` |
| `worker-src` | sin URL permitida (por `script-src`) | `'none'` | cerrado | `'none'` |
| `frame-ancestors` | `'self'` | — (una `<meta>` la ignora) | solo en la página exterior | — |

Lo que pierde la resultante frente al fabricante:
- en el marco, solo `'self'` en `img-src` y en `connect-src`;
- en las descargas, todo lo que no va en línea ni es `data:` o `blob:`.

### A5. Qué carga el HTML del lienzo

- **Página exterior** (carcasa de `/chatboo/canvas/<id>` y `/chatboo/page/<id>`): estilos, scripts y `onclick` en
  línea; `fetch` a `/chatboo/share/people` y POST de compartir; el marco `srcdoc`; el enlace de descarga. Todo lo
  permite la cabecera, y la `<meta>` no llega aquí.
- **Marco y descargas, lo que pone el código:** `_THEME_START`, `_THEME_BRIDGE`, `_HIDDEN_HIDES` (`:242-256`),
  `_PRINT_BRIDGE`, los botones de la descarga, la página de rescate y el vigilante (`:2186-2213`). Todo va en línea y
  sin URL.
- **Imágenes de las filas:** `pictures_as_tokens` (`:713-740`) cambia cada imagen reconocida por `pns-img:N`.
  `swap_pictures` (`:743-749`) la cambia de nuevo por `data:image/…`, o por `''` si el token no existe. `_cell_html`
  (`:1048`) solo pone `<img src>` a un token completo. El código **nunca** mete una URL del servidor en el marco.
- **Prompt de Design** (`:25-82`): prohíbe `fetch` y las API (`:44`); las imágenes van solo por token; el logo de la
  empresa no se le ofrece (solo `Company: <nombre>`, `:915-917`).
- **`/sales-board`:** es una skill del chat (`ai/skills/system/sales_board.py` y `.md`). Las tarjetas se pintan en el
  chat con ECharts, sin página ni Design, y no piden datos después de cargar. El botón Canvas se monta en todo
  `.o_ai_table_block[data-ai-dataset]` (`chatboo_charts.js:3229-3240`; `canvasTitleOf` lee `.o_ai_dashboard_title`,
  `:2957`), así que previsiblemente también está en esas tarjetas. Las filas son textos e importes, sin imágenes. Los
  gráficos los pinta Design en línea, y una librería de un CDN o del estático de Odoo ya la bloquea el `script-src` del
  fabricante.
- **Filas en el estado (3)**, es decir, bloqueadas solo por la `<meta>`):
  - en el marco, un `<img>`, `url(` o `fetch` que **la IA** escriba hacia el propio Odoo. No es legítimo: P-9 midió que
    esas peticiones salen sin sesión y que CORS no deja leer la respuesta. Una URL de imagen que no se reconoce y queda
    como texto en `DATA` (ver «Observación nueva») está en este caso si Design la pone en un `src`;
  - en las descargas, cualquier recurso externo. Es la degradación ya aceptada en el parche 27 de la 3879.
- **Filas en el estado (4):** ninguna.

### A6. Conclusión de la lectura

- Nada legítimo depende de `'self'`.
- Lo que el fabricante ya bloquea por su cuenta (librerías de un CDN o del estático de Odoo en el marco) lleva al
  informe al fabricante: un diseño con una librería externa sale sin gráficos en el lienzo y con gráficos en la descarga.
- Las descargas sin CSP ya estaban en el informe (P-9).

### A7. Diseños guardados en `lab_pns_ai_3973_14`

- Script, fuera del repo: `~/pns_ai_3973/fase4/csp/a7_recuentos.py`. Lo ejecutó `odoo-dev 14 shell` por entrada
  estándar, con el contexto `lab_pns_ai_3973` y el servidor web parado. Es de solo lectura y termina con `rollback`.
- Cuenta diseños, no apariciones. No se imprimen contenidos ni ID.
- Resultado:
  - **`chatboo.session.canvas_design`, 4 diseños:** 0 en todos los patrones de ruta del servidor (`src`/`href`/`url(`
    con `/`, `//`, `/web/image`, `/web/content`, `/web/binary`, `/web/static`, `/pns_ai_`, `localhost`/`127.0.0.1`), de
    petición (`fetch(`, `XMLHttpRequest`, `sendBeacon`, `EventSource`/`WebSocket`), de `http(s)` fuera de `w3.org` y de
    `<script src=`. Más de 0 solo en `data:image/` (2) y `pns-img:` (2).
  - **`chatboo.canvas.page.design`:** 0 diseños.
- Lectura:
  - `data:image/` son las imágenes incrustadas, que las dos políticas permiten;
  - `pns-img:` cuenta también el texto sin número. En ningún caso es una carga del propio Odoo: un
    `src="pns-img:N"` lo bloquean las dos políticas;
  - la muestra es pequeña.

### Decisiones de Sergio (13/11/2026)

1. **Sin paso B.** La `<meta>` no rompe nada legítimo: lo confirman el código, el prompt de Design, P-9 y A7 (4
   diseños, ninguna carga del propio Odoo). El parche 27 sigue como en el plan.
2. **A7 se repite**, en solo lectura, sobre la copia de `pns_demo` de P-15.
3. **La observación nueva** (abajo) va al informe al fabricante, sin parche.

**Sobre la propuesta del parche 27 (13/11/2026):**

4. **D1 sí:** se porta 27 a′. Resto conocido, para el registro: un `data:` con espacios o saltos de línea dentro del
   base64 deja de reconocerse y queda como texto. Lo que genera `_base64_picture` no los lleva.
5. **D2 sí:** regla del prompt con el texto de la propuesta, detrás de `'Do not fetch and do not call APIs. '` en
   `_PAGE_RULES`.
6. **D3 sí:** no se porta 27 d (`X-Frame-Options`). Confirmado: `chatboo.py:1171` y `:1277` usan `_page_headers`.
7. **D4 sí:** P-9 parte A como `TestSegesCanvasHeaders` en `test_seges_chatboo_canvas.py`, etiqueta `seges_e3p`, sin
   la parte RPC → compartir.
8. **D5 sí:** laboratorio corto tras implementar.

### Observación nueva para el informe al fabricante

Está separada de «Canvas sin imágenes», que ya está localizada en el traspaso de la fase 2c: el botón Canvas no lleva
imágenes a Design (`_chart_dataset_rows`, `relaxaicode_render_table.py:326-336`).

- **URL de imagen que no se reconoce:** un valor de imagen de las filas en un formato que `_WEB_IMAGE_RE`
  (`chatboo_canvas.py:654`) no reconoce sigue como URL en la muestra a Design y en `DATA` (`pictures_as_tokens`,
  `:729-737`). Ejemplos: `/web/image/<id>`, `/web/image?model=…`, `/web/content/…` o una URL absoluta.
- **Efecto:** si Design la pone en un `<img>`, el marco la pide sin sesión. Sale la imagen rota o la de por defecto,
  aunque el usuario tenga acceso.
- **Desde cuándo:** pasa ya en 3.1.973, con la cabecera del fabricante sola.

## Propuesta del parche 27 en 3.1.973 (pendiente de aprobación)

Archivos:
- `pns_ai_chatboo/models/chatboo_canvas.py` (código);
- `pns_ai_chatboo/tests/test_seges_chatboo_canvas.py` (tests).

`controllers/chatboo.py` no se toca.

### 27 a) Escape de lo que entra en un `<script>`

Se portan de la 3879 los dos helpers, tal cual (diff de la fase 0, líneas 21-40). Van detrás de `_logger`
(`chatboo_canvas.py:23`):

```python
# Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md
# Inside a <script> the HTML parser ends the block at </script> and reads
# <!-- as a comment: a row must not do either. Line separators break old JS.
_SCRIPT_UNSAFE = (
    ('<', '\\u003c'), ('>', '\\u003e'), ('&', '\\u0026'),
    ('\u2028', '\\u2028'), ('\u2029', '\\u2029'),
)


def _script_safe(text):
    """JSON text that can sit inside a <script>. Exact: JSON keeps those
    characters only inside strings, where the escape means the same."""
    for char, escaped in _SCRIPT_UNSAFE:
        text = text.replace(char, escaped)
    return text


def _script_json(value):
    """``value`` as JSON for a <script>: the one way figures go in."""
    return _script_safe(json.dumps(value, ensure_ascii=False, default=str))
```

- **Por qué es exacto:** en JSON, `<`, `>`, `&`, U+2028 y U+2029 solo aparecen dentro de cadenas, donde `\uXXXX`
  significa lo mismo. `json.loads` y el `JSON` del navegador devuelven el valor original.
- **Puntos donde se aplica:**

  | Línea | Hoy | Con el parche |
  |---|---|---|
  | 1098 | `json.dumps(_flat_rows(blocks), ensure_ascii=False, default=str)` | `_script_json(_flat_rows(blocks))` |
  | 1426 | `return dumped` | `return _script_safe(dumped)` (`figures_for_design` no se toca: si su `json.dumps` falla, devuelve `str(blocks)`, que sigue sin ser JSON, pero ya no cierra el `<script>`) |
  | 1427 | `return json.dumps(_flat_rows(blocks), …)` | `return _script_json(_flat_rows(blocks))` |
  | 1440 | `dumped = json.dumps(title, ensure_ascii=False)` | `dumped = _script_json(title)` |
  | 1734 | `chunks.append(json.dumps(best, …))` | `chunks.append(_script_json(best))` |
  | 2195 | `json.dumps(rows, ensure_ascii=False).replace('</', '<\\/')` | `_script_json(rows)` |

- **Por qué no basta el `.replace('</', '<\\/')` del fabricante en 2195:**
  - solo cubre el cierre `</script>`;
  - dentro de un `<script>`, la secuencia `<!--` seguida de `<script` pasa el tokenizador de HTML5 al estado *script data
    double escaped*. En ese estado, el siguiente `</script>` **no cierra** el bloque. El resto del vigilante y lo que
    venga detrás quedan dentro del script, y la página se rompe o cambia de estructura según lo que escriba la fila;
  - `<!--<script` no contiene `</`, así que el `replace` no lo toca. `_script_safe` sí: cambia `<` por `\u003c`;
  - es el caso `EVIL_COMMENT` de los tests.
- **Por qué 2047-2048 no entra:** `wrap_captured_page` escribe **código Python** (`_page_template = "<json>"`,
  `_page_title = "<json>"`), que se ejecuta en el sandbox. El HTML de `_page_template` no llega así al navegador: pasa
  por `page_html`, que vuelve a escribir `DATA` y `TITLE` con los puntos de arriba. Escapar ahí no protege nada y
  cambiaría el texto del código guardado.

### 27 a′) Imágenes `data:` solo en base64

- **Problema:** `_picture_of` (`:706-707`) acepta cualquier valor que empiece por `data:image/`. `swap_pictures` lo
  vuelve a meter **sin escapar** donde Design escribió el token, también dentro de `const DATA` o de un `<img src="…">`.
  Un valor `data:image/png;base64,x</script><script>…` salta el escape de 27 a.
- **Cambio de la 3879:** `return value if _DATA_URI_RE.fullmatch(value) else ''`. `_DATA_URI_RE` ya existe en 3.1.973
  (`:752`), sin anclas; `fullmatch` lo ancla.
- Si el valor no es una imagen, sigue como texto y lo serializa `_script_json`.
- El plan no lo citaba: **decisión pendiente D1**.

### 27 b) CSP en `<meta>` al servir (decisión 6)

Se porta tal cual de la 3879 (diff de la fase 0, líneas 64-83). Va justo antes de `_before_body_end` (`:430`):

```python
# Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md
# Added when the page is served, never stored: pages saved before get it too.
_CSP_META = (
    '<meta http-equiv="Content-Security-Policy" content="'
    "default-src 'none'; script-src 'unsafe-inline'; "
    "style-src 'unsafe-inline'; img-src data: blob:; font-src data:; "
    "connect-src 'none'; form-action 'none'; base-uri 'none'; "
    "frame-src 'none'; object-src 'none'; worker-src 'none'"
    '">'
)
# Our own doctype comes first, so the page is in standards mode; the two
# metas right after it open an implied <html> and <head> and are its first
# children. The design follows untouched: its doctype is ignored, and its
# <html> and <head> merge into ours. Nothing of it runs before the policy.
_CSP_PREFIX = '<!DOCTYPE html><meta charset="utf-8">' + _CSP_META


def _with_csp(design):
    """The design served behind our doctype and CSP, from byte 0."""
    return _CSP_PREFIX + (design or '')
```

Se aplica en dos sitios, como **último paso**:

- **`canvas_page`** (`:512-516`), al documento del `srcdoc`, antes del escape de atributo. Sirve a
  `/chatboo/canvas/<id>` y a `/chatboo/page/<id>`:
  ```python
  srcdoc = html.escape(
      _with_csp(_before_body_end(
          _with_theme(design), _HIDDEN_HIDES + _PRINT_BRIDGE,
      ))
      if (design or '').strip() else '',
      quote=True,
  )
  ```
- **`downloadable_page`** (`:463`), a las dos descargas (`/chatboo/canvas/<id>/download` y `/chatboo/page/<id>/download`):
  ```python
  return _with_csp(
      _before_body_end(_with_theme(design), _HIDDEN_HIDES + buttons),
  )
  ```

**Orden dentro del `<head>`.** Se comprueba por construcción. `_with_csp` envuelve el resultado completo, así que
`_CSP_PREFIX` ocupa los bytes 0 en adelante de lo servido. Todo lo que añade el servidor va **detrás** de la `<meta>`:
- `_THEME_START`, delante de cada `<script>` del diseño (`_with_theme`, `:242-247`);
- `_THEME_BRIDGE`, `_HIDDEN_HIDES` y `_PRINT_BRIDGE`, antes del `</body>` del diseño (`_before_body_end`);
- los botones de la descarga;
- el vigilante (`_spare_rows_watch`), que ya va dentro del diseño guardado.

Delante de la `<meta>` solo van el doctype y la `<meta charset>`, que no cargan ni ejecutan nada. Según HTML5 (registro,
«Revisión de E3′», «Por qué funciona»):
1. el doctype propio pone el documento en modo estándar;
2. la `<meta charset>` abre `<html>` y `<head>` implícitos, y la CSP es el **segundo hijo** de `<head>`;
3. lo que viene del diseño se lee con la política ya en vigor. Su doctype se ignora, sus `<html>` y `<head>` se fusionan
   con los nuestros, y un BOM o cualquier texto cierra el `<head>` con la CSP ya dentro.

**Diseño sin `<head>`** (o sin `<html>`, sin `<body>` o con basura delante): no cambia nada. El `<head>` lo abre el
prefijo, no el diseño. Lo cubren los 14 casos de `B1_DESIGNS` y, fuera de los tests, los 78 casos de html5lib de la 3879
(`docs/pendiente/scripts_e3/csp_prefijo.py` y `csp_adversario.py`).

**La página exterior no lleva `<meta>`.** Sus scripts de compartir necesitan `connect-src 'self'`, que da la cabecera
del fabricante.

### Cabeceras HTTP del fabricante: no se tocan (decisión 6)

- `_PAGE_CSP` (`chatboo.py:1175-1180`) y `_page_headers` (`:1182-1187`) siguen como están. Los usan `/chatboo/canvas/<id>`
  (`:1171`) y `/chatboo/page/<id>` (`:1277`).
- Las dos descargas siguen enviando solo `Content-Type`, `Content-Disposition` y `nosniff` (`:1291-1300`, `:1319-1328`).
  Su CSP es la `<meta>`.
- **27 d de la 3879 (`X-Frame-Options: SAMEORIGIN`):** no se porta. `frame-ancestors 'self'` en la cabecera del
  fabricante cubre lo mismo en los navegadores actuales. **Decisión pendiente D3.**

### 27 c) Regla del prompt de Design

- **Texto de la 3879:** detrás de `'Do not fetch and do not call APIs. '` (`:44`): `'Do not load external libraries,
  fonts, stylesheets or images: the page cannot reach the network. Draw charts with inline SVG or <canvas>. '`.
- **Alcance:** llega a `DESIGN_SYSTEM` y a `EDIT_SYSTEM`.
- **Por qué:** sin la regla, Design puede seguir pidiendo librerías de un CDN, que la cabecera del fabricante ya bloquea
  en el marco. La página sale sin gráficos.
- En la 3879 compartía bloque con la regla del 29. Aquí entra sola, y la del 29 se añade en su fase con su marcador.
- **Decisión pendiente D2.**

### Riesgos aceptados en la 3879, en 3.1.973

| Riesgo (parche 27 y revisiones de E3′) | En 3.1.973 con el parche |
|---|---|
| Autonavegación del marco (`location`, `<meta http-equiv="refresh">`, enlace sin `target`) | **Igual.** Ni la cabecera ni la `<meta>` la limitan, y el documento nuevo no hereda la política |
| WebRTC (STUN/TURN) y DNS (`dns-prefetch`, `preconnect`) | **Igual** |
| Imágenes `http(s)` externas de las filas, que dejan de verse | **Cambia:** en el marco ya las bloquea el fabricante (`img-src` sin hosts externos). El parche solo las quita de las **descargas** |
| m4: el 404 de la carcasa sin `X-Frame-Options` | **Cambia de forma:** sin el 27 d, el 404 de `request.not_found()` va sin la cabecera CSP del fabricante (sin `frame-ancestors`), igual que antes iba sin `X-Frame-Options`. Sigue sin llevar nada del diseño |
| Diseño sin doctype: pasa de modo quirks a estándar | **Igual** (es por el prefijo) |
| m-a: `downloadable_page('   ')` sin prefijo | **Igual** (`:439-440`). Las cuatro rutas dan 404 con el diseño vacío |
| m-b: el test comprueba el prefijo literal, no el árbol HTML5 | **Igual** |
| Vía de la sesión (D5: HTML escrito por RPC en `canvas_design` y compartido) | **Mejora:** sigue abierta (no es del 27), pero su alcance queda limitado por las dos políticas en el marco y por la `<meta>` en las descargas, que en 3.1.973 no tenían CSP |
| Peticiones al propio Odoo desde el marco (nuevo en 3.1.973: `'self'` del fabricante) | **Desaparece:** `img-src` y `connect-src` quedan sin `'self'` |

### Marcadores

`# Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md`, uno por bloque:
1. `_SCRIPT_UNSAFE`, `_script_safe` y `_script_json`, detrás de `:23`;
2. la regla c, en `_PAGE_RULES`, detrás de `:44` (si se aprueba D2);
3. `_CSP_META`, `_CSP_PREFIX` y `_with_csp`, delante de `_before_body_end` (`:430`);
4. el `return` de `downloadable_page` (`:463`);
5. el `srcdoc` de `canvas_page` (`:512`);
6. `_picture_of` (`:706-707`), si se aprueba D1;
7. a 12. cada punto del escape: `:1098`, `:1426`, `:1427`, `:1440`, `:1734` y `:2195`.

En el test se cambia la segunda línea de cabecera (la de la fase 2b) para decir que los casos del 27 vuelven en la
fase 4. `tests/__init__.py` no cambia: el archivo ya se importa.

### Tests

Archivo: `pns_ai_chatboo/tests/test_seges_chatboo_canvas.py`. Las clases de la 3879 vienen de
`~/pns_ai_3973/fase0/tests_seges/pns_ai_chatboo/tests/test_seges_chatboo_canvas.py`. Etiquetas `post_install`,
`-at_install`, `pns_ai_chatboo`, `seges_e3p`, como en la 3879.

Se portan los imports (`html`, `json`, `re` y `chatboo_canvas as canvas`), las constantes `EVIL`, `EVIL_COMMENT` y
`BREAKOUTS`, `_json_after`, `B1_DESIGNS` y `_assert_csp_served`.

**`TestSegesCanvasScriptJson` (8):**

| Test | Cubre | Port |
|---|---|---|
| `test_const_data` | 1427 | Tal cual |
| `test_const_data_blocks_shape` | 1426 | Tal cual |
| `test_const_title` | 1440 | Tal cual |
| `test_other_arrays` | 1734 | Tal cual: `const ROWS` no es `const DATA`, así que `bind_script_row_json` pasa de `bind_const_data` al camino de `_row_payloads` (`:1711-1745`) y comparte con los bloques dos columnas (`name`, `amount`) |
| `test_rescue_page` | 1098 | Tal cual |
| `test_rows_watch` | 2195 | Tal cual. Con el `replace` del fabricante falla por `<!--<script` (`BREAKOUTS`), que es justo lo que muestra que no basta |
| `test_whole_page` | `place_rows_on_page` completo con título | Tal cual. **Riesgo:** en 3.1.973 `place_rows_on_page` es la del fabricante (el envoltorio del 29 aún no está). Si falla por un valor en crudo fuera de `DATA`/`TITLE` (lo que cubre el 29), no se cambia el test: se documenta por nombre y se vuelve a medir tras el 29 |
| `test_picture_only_base64_data_uri` | 27 a′ | Tal cual si se aprueba D1; si no, no se porta |

**`TestSegesCanvasShell` (8):**

| Test | Port |
|---|---|
| `test_stored_design_has_no_csp` | Tal cual |
| `test_canvas_shell`, `test_page_shell` | **Adaptados:** fuera `X-Frame-Options == 'SAMEORIGIN'` (D3). En su lugar, `Content-Security-Policy` de la respuesta igual al literal del fabricante: fija la decisión 6. `_assert_csp_served` sobre el `srcdoc`, sin cambios |
| `test_canvas_download`, `test_page_download` | **Adaptados:** además, que la respuesta **no** lleva cabecera `Content-Security-Policy` (la CSP de la descarga es la `<meta>`) |
| `test_csp_prefix_cases` (14 subtests) | Tal cual |
| `test_csp_policy` | Tal cual |
| `test_design_rule` | Tal cual si se aprueba D2; si no, no se porta |

`setUp` adaptado como en la fase 2b: en 3.1.973 la página solo se crea en `su`, así que
`self.env['chatboo.canvas.page'].sudo().create({..., 'owner_id': self.chat.id})`, con el marcador «adaptado a 3.1.973».

**P-9 parte A como test de Seges.** Clase nueva `TestSegesCanvasHeaders` en el mismo archivo, etiqueta `seges_e3p`.
Viene de `~/GitHub/lab_pns_ai_973/seges_pruebas_973/tests/test_p9_csp_cabeceras.py`, leído y no copiado:

| Test | Comprueba |
|---|---|
| `test_p9_shell_headers` | `/chatboo/canvas/<id>` (dueño) y `/chatboo/page/<id>` (lector interno, añadido en `user_ids` en `su`): 200; CSP igual al literal `PAGE_CSP` del fabricante; `nosniff` |
| `test_p9_srcdoc_escape` | El marcador inofensivo `"></iframe><b id=p9>` no cierra el marco en las dos rutas: un `<iframe` y un `</iframe>`; el marcador escapado sí y en crudo no |
| `test_p9_downloads` | Las dos descargas: 200; adjunto; `nosniff`; sin cabecera CSP; lo servido empieza por `_CSP_PREFIX` |

Qué se adapta del original:
- registraba sí/no en el log; aquí son `assert`;
- usa `SegesChatbooCase` (`_chat_user`, `_get`) en lugar de `create_test_user` y su copia de `_chatboo_access`;
- la página compartida se crea en `su` con `owner_id`;
- **no se porta** `test_rpc_y_compartir`: la vía D5 sigue abierta y no es del 27, y un test que la diera por buena
  fijaría el defecto. El control de alta fuera de `su` ya está en `TestSegesSharedPage`.

**Recuento previsto** (línea base: 522 tests, 1 F `test_paap_i7`, 0 E y 6 saltados):
- con D1 y D2 aprobadas: **541 tests (522 + 8 + 8 + 3), 1 F (`test_paap_i7`), 0 E y 6 saltados**;
- sin D1 o sin D2, uno menos por cada una.

Si `test_whole_page` falla por el motivo de arriba, se informa por nombre antes de seguir.

### Neutralizaciones previstas

Mismo método que en las fases anteriores:
1. SHA-256 de referencia de `chatboo_canvas.py` tal como quede tras implementar, anotado antes de la primera;
2. copia, cambio y batería;
3. restauración y SHA-256 **IGUAL** a la referencia tras cada una.

| Id | Qué se retira | Resultado esperado |
|---|---|---|
| N27a1 | 1098: `json.dumps` del fabricante | F `test_rescue_page` |
| N27a2 | 1426: `return dumped` sin `_script_safe` | F `test_const_data_blocks_shape` |
| N27a3 | 1427: `json.dumps` del fabricante | F `test_const_data` (y previsiblemente `test_whole_page`) |
| N27a4 | 1440: `json.dumps(title, …)` | F `test_const_title` (y previsiblemente `test_whole_page`) |
| N27a5 | 1734: `json.dumps(best, …)` | F `test_other_arrays` |
| N27a6 | 2195: vuelve el `.replace('</', '<\\/')` del fabricante | F `test_rows_watch` (por `<!--<script`) |
| N27b1 | `canvas_page` sin `_with_csp` | F `test_canvas_shell`, `test_page_shell` y los 14 subtests de `test_csp_prefix_cases` |
| N27b2 | `downloadable_page` sin `_with_csp` | F `test_canvas_download`, `test_page_download`, `test_p9_downloads` y los 14 subtests de `test_csp_prefix_cases` |
| N27a′ | `_picture_of` sin `fullmatch` (si D1) | F `test_picture_only_base64_data_uri` |
| N27c | Sin la regla del prompt (si D2) | F `test_design_rule` |

`test_csp_prefix_cases` comprueba las dos funciones en cada subtest: en N27b1 y en N27b2 caen los 14 subtests. Una
neutralización que dé E en lugar de F se documenta por nombre, sin cambiar el test.

### Registro y plan (al implementar; ahora no se editan)

- **Registro** (`parches_pns_ai.md`), sección nueva «Parches de la rama 14.0-pns-ai-3973 (fase 4)», entrada del 27:
  - qué se porta (a, a′, b, c) y qué no (d);
  - los seis puntos del escape y por qué sale 2047-2048;
  - el orden del prefijo;
  - las cabeceras del fabricante intactas;
  - la tabla de riesgos de arriba;
  - tests, resultado de la batería, neutralizaciones y estado.

  Además, la observación nueva de las URL de imagen, en el apartado del informe al fabricante.
- **Plan:** sin reescribir las entradas fechadas, un bloque nuevo debajo:
  - en «Fase 4», 27: «comprobación previa hecha (13/11/2026, sin paso B; propuesta_fase4_3973.md)» y las líneas
    corregidas (1426 y 1734 añadidas, 2195 añadida, 2047-2048 fuera);
  - en «Pruebas posteriores», punto 5 (P-15): «A7 en solo lectura sobre la copia de `pns_demo`».

### Laboratorio después de implementar

Es corto y sigue el procedimiento fijo: «Antes de arrancar», «Arranque», C tras la entrada y «Al acabar».
- **Qué se mira:**
  1. `/chatboo/canvas/<id>` de un lienzo con imágenes: pinta, se ven las imágenes, cambian el tema y la impresión;
  2. Compartir, desde la página exterior: funciona, porque no lleva `<meta>`;
  3. la descarga abierta desde el disco: pinta, se ven las imágenes y el botón de imprimir funciona.
- **Consola:** ningún «Refused to …» de `img-src` ni de `connect-src`. Si sale alguno, se anota la directiva y la ruta,
  con `<id>`.
- **Sin LLM:** sobre un diseño ya guardado.

### Decisiones pendientes de Sergio

| Id | Decisión | Recomendación |
|---|---|---|
| D1 | Portar 27 a′ (`_picture_of` con `_DATA_URI_RE.fullmatch`) | **Sí.** Sin él, una imagen `data:` con `</script>` salta el escape de 27 a por `swap_pictures`. Es una línea y el regex ya es del fabricante |
| D2 | Portar 27 c (regla del prompt sin recursos externos) | **Sí.** El fabricante ya bloquea las librerías externas en el marco, y sin la regla Design las sigue pidiendo y la página sale sin gráficos |
| D3 | No portar 27 d (`X-Frame-Options`) | **No portarlo.** `frame-ancestors 'self'` del fabricante lo cubre, y la decisión 6 mantiene su cabecera. Los tests pasan a comprobar la CSP literal del fabricante |
| D4 | P-9 parte A como clase nueva en `test_seges_chatboo_canvas.py`, etiqueta `seges_e3p`, sin la parte RPC → compartir | **Sí** (motivos arriba) |
| D5 | Laboratorio corto tras implementar | **Sí:** el prefijo cambia lo servido en las cuatro rutas, y solo el navegador confirma que se pinta igual |

## Implementación y resultados del parche 27 (13/11/2026)

- **Código** (`pns_ai_chatboo/models/chatboo_canvas.py`): 27 a (seis puntos), a′, b (`canvas_page` y
  `downloadable_page`) y c, con los 12 marcadores de la propuesta. `controllers/chatboo.py` no cambia. Lint: 0
  incidencias nuevas. Compila con Python 3.7.3 en `odoo-dev:14`.
- **SHA-256 de `chatboo_canvas.py`:**
  - antes de tocarlo: `d5178aea9f05f2f9fe6dfab1b56354f8f071b0e41dea04fb6707325a82d54c5a`
    (`~/pns_ai_3973/fase4/27/sha256_antes.txt`);
  - de referencia, con el parche: `bb42701991968f2b11042fb1b69e4541045040be88bbe9bdd9d3230c0c3377d1`
    (`~/pns_ai_3973/fase4/27/sha256_parche.txt`).
- **Tests** (`pns_ai_chatboo/tests/test_seges_chatboo_canvas.py`): `TestSegesCanvasScriptJson` (8),
  `TestSegesCanvasShell` (8) y `TestSegesCanvasHeaders` (3), con las adaptaciones de la propuesta y el alta de la página
  en `su`. Las dos clases de la 3879 y sus constantes se copiaron del archivo de la fase 0 con un script, para conservar
  tal cual los U+2028 literales de sus casos.
- **Batería** (`tests-20261113-190554.log`, línea base `tests-20261113-182647.log`):
  - **541 tests** (+19), **1 F** (`TestSystemTrustedActions.test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin`),
    **0 E** y los mismos **6 saltados**, por nombre;
  - `bad query` 1 (`UPDATE "ai_safe_operation"`), «seges_side_env: » 1, Traceback 58 y secretos 0: iguales que en la
    línea base;
  - origen de los módulos: `addons paths` con `/mnt/compartidos/third_party`; 0 `pns_*` en `~/odoo-dev/14.0/oca/*`, en
    `/usr/lib/python3/dist-packages/odoo/addons` de la imagen y en `addons/14.0` del volumen `odoo-dev-14_web-data`
    (montado en solo lectura);
  - `test_whole_page` pasa sin el parche 29.
- **Neutralizaciones** (método de la 2a: cambio comprobado con una coincidencia exacta, batería completa, restauración
  y SHA-256; scripts y salida en `~/pns_ai_3973/fase4/27/`):

  | Id | Qué se retira | Esperado | Obtenido (F además de `test_paap_i7`) | E | SHA-256 |
  |---|---|---|---|---|---|
  | N27a1 | 1098 | `test_rescue_page` | `test_rescue_page` | 0 | IGUAL |
  | N27a2 | 1426 | `test_const_data_blocks_shape` | `test_const_data_blocks_shape` | 0 | IGUAL |
  | N27a3 | 1427 | `test_const_data` (y previsiblemente `test_whole_page`) | `test_const_data`, `test_whole_page` | 0 | IGUAL |
  | N27a4 | 1440 | `test_const_title` (y previsiblemente `test_whole_page`) | `test_const_title`, `test_whole_page` | 0 | IGUAL |
  | N27a5 | 1734 | `test_other_arrays` | `test_other_arrays` | 0 | IGUAL |
  | N27a6 | 2195 (vuelve el `replace` del fabricante) | `test_rows_watch` | `test_rows_watch`, `test_whole_page` | 0 | IGUAL |
  | N27b1 | `_with_csp` en `canvas_page` | `test_canvas_shell`, `test_page_shell` y 14 subtests | ídem; runner: 17 failed (1 + 2 + 14) | 0 | IGUAL |
  | N27b2 | `_with_csp` en `downloadable_page` | `test_canvas_download`, `test_page_download`, `test_p9_downloads` y 14 subtests | ídem; runner: 19 failed (1 + 2 + 14 + 2) | 0 | IGUAL |
  | N27a′ | `fullmatch` en `_picture_of` | `test_picture_only_base64_data_uri` | ídem | 0 | IGUAL |
  | N27c | regla del prompt | `test_design_rule` | ídem | 0 | IGUAL |

  Diferencias con lo esperado:
  - **N27a6 tumba también `test_whole_page`:** `place_rows_on_page` con `captured=True` incluye el vigilante;
  - **subtests:** el patrón de nombres del traspaso no saca las líneas de los subtests. Se confirman por el total del
    runner y por un grep de nombres (`test_csp_prefix_cases` 29 veces en las dos pasadas, que son 1 + 14 × 2;
    `test_p9_downloads` 1 en N27b1, donde pasa, y 5 en N27b2, que son 1 + 2 × 2).
- **Laboratorio D5** (13/11/2026): correcto. Ver la fila del 13/11/2026 en el «Registro de laboratorios» de
  [lab_procedimiento_3973.md](lab_procedimiento_3973.md). Sesión 8 como `seges_int@example.com`, Compartir con
  `seges_aiadm`; la página compartida queda en la BD del laboratorio.
- **Nota de la herramienta de escritura:** al escribir archivos, un `\uXXXX` con una sola barra se convertía en el
  carácter. Se perdieron así, en la primera versión de esta propuesta, los escapes de U+2028/U+2029 del bloque de
  `_SCRIPT_UNSAFE` y un escape de `<`; se corrigieron. El código se escribió con scripts que construyen la barra con
  `chr(92)`. Comprobado en `chatboo_canvas.py`: ningún U+2028/U+2029 literal (`grep -P`); los dos pares van como escape,
  en la línea 30; y los escapes con doble barra de `<`, `>` y `&` están intactos (1 de cada uno).
- **Automatización del laboratorio:** queda para los laboratorios del 29 y del 34 (Chrome con
  `--remote-debugging-pipe` y Python estándar, sin WebSocket ni instalaciones; decisión de Sergio, 13/11/2026). En el
  equipo hay Chrome, pero no Node ni `websocket-client`.
