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

## Propuesta del parche 29 en 3.1.973 (pendiente de aprobación)

- **Fecha:** 16/11/2026. **Rama:** `14.0-pns-ai-3973`, en `d9d4f82` según el encargo (HEAD no comprobado con git). Solo
  lectura: no se ha tocado código ni tests.
- **Líneas:** «actual» es el árbol en `d9d4f82` (con los parches 25, 26, 27 y 38 ya aplicados). «Tras el parche» es la
  simulación descrita abajo. Las líneas del plan (`:829-858`, `:2062-2105`) son de 3.1.973 limpia y no se usan.
- **Fuentes:** registro, «Parche 29» (rama 3879: cambio, revisiones, neutralización, medición y riesgos residuales);
  [e3_hallazgo_p8ea_3879.md](e3_hallazgo_p8ea_3879.md); diffs de la fase 0
  (`~/pns_ai_3973/fase0/diffs/pns_ai_chatboo+models+chatboo_canvas.py.diff` y `…chatboo_session.py.diff`); test de la
  3879 (`~/pns_ai_3973/fase0/tests_seges/pns_ai_chatboo/tests/test_seges_chatboo_canvas.py`); archivos completos de la
  3879 (`~/pns_ai_3973/fase0/modulos_3879/pns_ai_chatboo/models/`).

### Alcance aprobado (D6 a D10, encargo del 16/11/2026)

Se porta el 29 entero de la 3879:
- la regla de `textContent` en `_PAGE_RULES`, en un bloque propio con su marcador, detrás de la regla del 27 c;
- C1: la muestra de `sample_figures_for_design` pasa por `_script_safe` (ya existe por el 27);
- A (`_model_data_left`) y B (`_raw_value_left`);
- la envoltura `place_rows_on_page` sobre la del fabricante, renombrada `_place_rows_on_page` (D7);
- `html.escape(quote=True)` en la tabla de rescate y la forma `&quot;` en `_page_shows_rows` («q» en esta propuesta);
- D (edición sin filas, en `chatboo_session.py`), B1 con n1, y m1, m3 y m8.

El defecto de `keys` de R8 queda fuera (informe al fabricante), salvo que impida pasar un test del 29: no lo impide
(punto 2 f).

### Método

- **Simulación fuera del repo** (`/tmp/claude-1000/-home-soporte-GitHub-third-party/53b4aefb-12de-4815-8b20-092030ba9066/scratchpad/p29/simular.py`):
  copia los dos archivos de `d9d4f82`, comprueba 17 anclas (el texto exacto de cada línea donde cae un bloque) y pega cada
  bloque del 29 copiado **por rango de líneas** del archivo de la 3879, sin reescribirlo. Resultado en `…/p29/sim/`.
- **Resultado del diff frente a la 3879:** en `chatboo_canvas.py` solo quedan las diferencias ajenas al 29: el parche 34
  (importación de `ContextVar`, `_NO_PAGE_WATCH`, `watch_no_page`, `page_refused_in_job` y su parte de `log_no_page`), los dos
  marcadores del 25 que 3.1.973 ya no necesita (`open_page` y `edit_page`), el doble marcador del 27 en
  `_payload_for_const_data` y dos cambios del fabricante (sin `_figure_numbers`; `_page_template` leído con
  `ast.literal_eval`). En `chatboo_session.py` desaparecen todos los bloques del 29, y lo demás son cambios del fabricante y
  parches de otras fases.
- **Compila** con Python 3.12 (`py_compile`). Python 3.7.3 en la imagen y el lint `--revisar`, al implementar. La 3879 dio
  0 incidencias nuevas con el mismo texto (la f-string de `_rows_as_table` y la tupla de `_page_shows_rows` se eligieron por
  eso).
- **Comprobación en memoria** (`…/p29/comprobar.py`, con un `odoo` falso que solo da `_`): los casos puros de
  `place_rows_on_page` de los tests del 29 (A: 5 rescates y 2 diseños conservados; B: 6 rescates y el control `R&D Ltd`;
  `Seges "P29"` y el título hostil conservan el diseño; A y B no saltan con la página de rescate; C1). **20 de 20 BIEN.**
  Las partes de `chatboo_session.py` necesitan Odoo y se miden en la batería.

### 1. Bloques del 29 en los diffs de la fase 0 y dónde caen

**`pns_ai_chatboo/models/chatboo_canvas.py`** (9 marcadores, como en la 3879):

| # | Hunk del diff de la fase 0 | Parte | Actual (`d9d4f82`) | Tras el parche | Mezcla con otro parche y cómo se separa |
|---|---|---|---|---|---|
| C1 | `@@ -17,11 +17,42 @@` | B1 y n1 (`HTMLParser`) | detrás de `:19` (`import unicodedata`) | `:20-21` | El hunk trae también la importación de `ContextVar` (34) y los helpers del 27. Solo entran las dos líneas del 29; el 34 va en su parche y el 27 ya está (`:25-44`) |
| C2 | `@@ -42,6 +73,13 @@` | regla de `textContent` | entre `:69` (fin de la regla del 27 c, `:67-69`) y `:70` | `:72-75` | En la 3879 ya iba con marcador propio, detrás del 27 c. El 27 c no se toca: el 29 entra como bloque aparte justo detrás |
| C3 | `@@ -851,6 +946,9 @@` | C1 | entre `:907` (`dumped = str(sample)`) y `:908` (`note = (`) | `:914-916` | Ninguna: el 27 no cambia `sample_figures_for_design`. C1 solo usa `_script_safe` (27, `:33-38`) |
| C4 | `@@ -1045,8 +1146,10 @@` | q (`_cell_html`) | `:1103-1104` | `:1112-1116` | Ninguna |
| C5 | `@@ -1069,8 +1172,9 @@` | q (`_rows_as_table`, filas que no son diccionarios) | `:1127-1128` | `:1138-1141` | Ninguna |
| C6 | `@@ -1238,10 +1343,11 @@` | q (`_page_shows_rows` acepta `&quot;`) | `:1289-1292` | `:1301-1306` | Ninguna |
| C7 | `@@ -1523,6 +1631,187 @@` | A, B, B1 y n1, más m1, m3 y m8 | delante de `:1577` (`_visible_page_text`), detrás de `_const_data_value` (`:1561-1574`) | `:1590-1768` | Ninguna. Un solo marcador para el bloque, como en la 3879 |
| C8 | `@@ -2065,7 +2355,31 @@` | envoltura y renombrado (D7) | `:2122` (`def place_rows_on_page`) | envoltura `:2316-2336`; marcador `:2339`; `_place_rows_on_page` `:2340-2383` | Ninguna. El cuerpo del fabricante (`:2123-2170` hoy) no cambia |

Dentro de C7, por parte (líneas tras el parche):
- **A:** `_DATA_ASSIGN_RE` (`:1592`), `_DATA_NAME_RE` (`:1597`, con `\Z` de m1), `_server_data_values` (`:1602`) y
  `_model_data_left` (`:1617`);
- **B:** `_MARKUP_UNSAFE` (`:1599`), `_markup_values` (`:1642`, con m3 y el conjunto `seen` de m8) y `_raw_value_left`
  (`:1673`, con las dos formas JSON);
- **B1:** `_VOID_TAGS` (`:1694`), `_PageRowsText` (`:1700`) y `page_rows_texts` (`:1725`);
- **n1:** `_PageMarkupText` (`:1741`) y `page_markup_texts` (`:1757`).

Del diff del lienzo **no** son del 29: el 34 (cuatro hunks), el 27 (ya aplicado), el 26 (`open_page`) y los dos del 25.

**`pns_ai_chatboo/models/chatboo_session.py`** (5 marcadores, como en la 3879):

| # | Hunk del diff de la fase 0 | Parte | Actual (`d9d4f82`) | Tras el parche | Mezcla con otro parche y cómo se separa |
|---|---|---|---|---|---|
| S1 | `@@ -1064,11 +1070,17 @@` | importaciones de D, B, B1 y n1 | entre `:1098` (`sync_canvas_title_phrases,`) y `:1099` (`)`) | `:1099-1101` | El hunk trae el 25 (comprobación del dueño, ya en `:1091-1093`). Solo entran las tres líneas del 29 |
| S2 | `@@ -1078,6 +1090,27 @@` | D, B1 (rechazo previo) y n1 | entre `:1107` (`page = pictures_out(…)`) y `:1108` (`prompt = …`) | `:1111-1131` (n1 con marcador propio en `:1129`) | Ninguna |
| S3 | `@@ -1158,12 +1191,22 @@`, primera parte | D (`bind_rows`, `bind_title`) | `:1188-1193` | `:1212-1218` | Ninguna |
| S4 | mismo hunk, segunda parte | B1 tras pintar (`kept_texts`) | entre `:1193` (`), images)`) y `:1194` (`if err or not content:`) | `:1219-1227` | Ninguna |

Del diff de la sesión **no** son del 29: el 25 (renombrado a `_paint_canvas` y `AccessError`), el 18 (envoltura de
`_ask_design`, que en 3.1.973 va en otros archivos), el 11 y el 26.

### 2. Qué cambia en 3.1.973 frente a la 3879

El código del fabricante en las zonas del 29 es **idéntico** al de 3.1.879: entre 3.1.879 y 3.1.973, `chatboo_canvas.py`
solo cambia en cuatro hunks (los dos `paint_canvas` → `_paint_canvas`, el borrado de `_figure_numbers`, que no tenía
llamadores, y `ast.literal_eval` en la lectura de `_page_template`). Punto por punto:

**a) La muestra (`sample_figures_for_design`, `:883-914`).**
- Igual que en la 3879: por bloque, `{'title', 'keys', 'data': data[:3]}`, con `json.dumps(…, ensure_ascii=False,
  default=str)` y, si falla, `str(sample)`.
- **No** es la forma de `figures_for_design` (`:865-874`): esa vuelca los bloques tal cual (sin `keys` y con todas las
  filas).
- Comparten que son una lista de bloques con `data`. Por eso, si Design copia la muestra en `const DATA`,
  `_payload_for_const_data` (`:1471-1484`) la reconoce como forma de bloques y escribe `figures_for_design`, ya escapado por
  el 27 (`:1481`).
- C1 actúa sobre `dumped` después de las dos ramas, así que cubre también `str(sample)`. `figures_for_design` no se toca.

**b) Llamadores de `place_rows_on_page` en los tres módulos** (grep en `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo`, fuera
de los tests):

| Llamador | Línea actual | `captured` |
|---|---|---|
| `chatboo.session._page_html` (skill capturada, caso h) | `chatboo_session.py:942` | `True` |
| `chatboo.session._paint_canvas` (lienzo nuevo, edición y repetición) | `chatboo_session.py:1188` | `True` |

- La rama `captured=False` (`:2146`) no tiene llamadores en los tres módulos. Ningún test del 29 la usa.
- **El sandbox no la ve por su nombre.** `sandbox_helpers` (`chatboo_session.py:833-859`) solo da `page_url`, `page_edit` y
  `page_html`, que envuelven `_page_url`, `_page_edit` y `_page_html`. **Novedad de 3.1.973:** el fabricante hizo
  privados esos tres métodos; el nombre en el sandbox no cambia.
- **Las skills tampoco.** El código capturado llama a `page_html(` (`wrap_captured_page`, `chatboo_canvas.py:2087-2119`;
  `pns_ai_mcp/utils/skill_runtime_code_rewrite.py:628-633`; `pns_ai_mcp/models/ai_skill_authoring.py:420`), y de ahí a
  `_page_html`.
- Ninguno de los nombres nuevos del 29 (`_place_rows_on_page`, `_model_data_left`, `_raw_value_left`, `_markup_values`,
  `_server_data_values`, `page_rows_texts`, `page_markup_texts`, `_PageRowsText`, `_PageMarkupText`, `_VOID_TAGS`,
  `_DATA_ASSIGN_RE`, `_DATA_NAME_RE`, `_MARKUP_UNSAFE`, `HTMLParser`) existe hoy en los tres módulos: no hay colisiones.
- Las importaciones de `place_rows_on_page` están dentro de las funciones (`:928`, `:1097`), así que siempre toman la
  envoltura.
- **Los tests del fabricante no pasan por ella:** `test_chatboo_perimeter.py` escribe `canvas_design` directamente
  (`:176-179`).

**Conclusión: nada obliga a cambiar D7.** La envoltura sigue siendo el único punto por el que pasan las dos rutas.

**c) `_SCRIPT_INNER_RE` (`:1406-1408`):** sigue siendo `(<script\b[^>]*>)(.*?)(</script>)` con `IGNORECASE | DOTALL`,
no codicioso. La causa de P-8e a sigue (un `</script` dentro de DATA corta el script), y A lee el script como lo corta el
servidor.

**d) ¿A reconoce todas las formas en que 3.1.973 escribe DATA?** Sí:
- el servidor escribe DATA en dos sitios:
  - la página de rescate: `<script>const DATA=%s;</script>` (`:1165`);
  - la sustitución del JSON que sigue a `const DATA =` (`bind_const_data`, `:1527-1558`), que respeta los espacios de Design;
- el valor es `_flat_rows` (`:1464`), o `figures_for_design` en la forma de bloques (`:1471-1484`);
- otras matrices con las mismas columnas, incluido un `let DATA` (el control de `test_data_forms_bound_kept`), las cambia
  `bind_script_row_json` (`:1759`) por los datos de `_row_payloads`;
- los tres valores están en `_server_data_values`;
- el vigilante escribe `var ROWS=`, que no es DATA;
- el tema, la impresión y el prefijo CSP del 27 se añaden al servir, no se guardan: A no los ve;
- con el 27, DATA va con `\u003c`, pero `json.loads` devuelve el valor original, así que `val not in server` compara
  lo mismo que en la 3879.

Comprobado en memoria: 5 de 5 rescates y 2 de 2 diseños conservados.

**e) ¿Sobre qué texto se evalúa B?**
- En la envoltura, sobre la salida de `_place_rows_on_page`: antes de `swap_pictures` y sin el prefijo CSP, que no se guarda.
- En S4 (B1 tras pintar), sobre `content` ya con `swap_pictures`. Las imágenes son `data:` en base64, solo con su alfabeto
  (27 a′, `fullmatch`), y no llevan `<`, `>` ni `"`.

En ese texto, lo que escribe el servidor:
- **en los scripts** (DATA, TITLE, `ROWS` del vigilante y las otras matrices, todos con `_script_json`): `<` como
  `\u003c`, `>` como `\u003e`, `&` como `\u0026` y `"` como `\"`;
- **en las cabeceras** de la tabla (`<th>`, `:1117`), los títulos de bloque (`<h2>`, `:1139`) y el `<title>` del rescate
  (`:1151`): `html.escape` por defecto, que ya escapa `"`;
- **en las celdas:** `quote=False` hoy (`:1104`, `:1128`). Es lo que corrige q.

**Caso `Seges "P29"`:** se conserva el diseño:
- DATA lo lleva como `Seges \"P29\"`, que no contiene `Seges "P29"`;
- con q, la tabla escribe `&quot;`;
- el vigilante, `\"`.

Comprobado en memoria (`test_hostile_rows_design_kept`). Sin la parte de `_cell_html`, el mismo diseño va al rescate: es
N29q.

Las formas JSON de B solo se buscan para valores con `<` o `>` y conservan ese carácter en crudo. Con el 27, el servidor ya no
lo escribe nunca en crudo dentro de un script, así que no dan falsos positivos.

**f) R8 (`keys`):** igual.
- La muestra lleva `keys` (`:892-901`) y el DATA que escribe el servidor no (`_flat_rows`, `figures_for_design`).
- No impide ningún test del 29: `test_design_prompt_escaped` espera `keys` en la muestra (que es como está), y los demás
  comparan DATA con las filas.
- Queda fuera del parche, como dice el alcance.

**g) Otros cambios de 3.1.973 cerca, sin efecto en el 29:**
- `_page_template` se lee con `ast.literal_eval` (`:2077-2083`); el caso h sigue pasando por `_page_html` y por la envoltura;
- `_store_design` va dentro de `seges_side_env()` (parche 38, `chatboo_session.py:1010`), sin cambio en la revisión que
  ven los tests;
- `log_no_page` (`:640`) y `canvas_title` siguen igual. D los usa.

### 3. Código propuesto por bloque

Copiado byte a byte de la 3879 (el rango de líneas va entre paréntesis). Las barras invertidas de los regex y del docstring
de `_raw_value_left` van tal cual en el archivo de origen: comprobación con `grep -cF` al final de esta sección.

**C1** (3879 `:22-23`), detrás de `import unicodedata` (`:19`):

```python
# Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
from html.parser import HTMLParser
```

**C2** (3879 `:79-82`), en `_PAGE_RULES`, entre la regla del 27 c (`:67-69`) y `'Every tab, chip or card…'` (`:70`):

```python
    # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
    'Put every value from DATA and TITLE on the page with textContent (or '
    'createTextNode): they are plain text. Never insert them with innerHTML, '
    'outerHTML, insertAdjacentHTML or document.write. '
```

**C3, C1 del 29** (3879 `:949-951`), en `sample_figures_for_design`, entre `dumped = str(sample)` (`:907`) y `note = (`
(`:908`):

```python
    # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
    # Design may copy the sample into const DATA: it must not close the script.
    dumped = _script_safe(dumped)
```

**C4, q en `_cell_html`** (3879 `:1149-1153`). Sustituye a `:1103-1105`:

```python
    # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
    # Quotes escaped too: a raw " on the page is a value Design copied.
    return '<td>%s</td>' % html.escape(
        '' if value is None else str(value), quote=True,
    )
```

**C5, q en `_rows_as_table`** (3879 `:1175-1179`). Sustituye a `:1127-1130`:

```python
    # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
    cells = ''.join(
        f'<tr><td>{html.escape(str(row), quote=True)}</td></tr>'
        for row in rows
    )
```

**C6, q en `_page_shows_rows`** (3879 `:1346-1351`). Sustituye a `:1289-1293`:

```python
        # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
        if not any(
            found(form)
            for mark in own
            for form in (html.escape(mark, quote=False), html.escape(mark), mark)
        ):
```

**C7, A, B, B1 y n1** (3879 `:1634-1812`), delante de `def _visible_page_text` (`:1577`), con dos líneas en blanco detrás:

```python
# Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
# Every way a design hands DATA to its script. Only the server writes it.
_DATA_ASSIGN_RE = re.compile(
    r'(?:\b(?:const|let|var)\s+|\bwindow\s*\.\s*)DATA\s*=(?!=)\s*',
)
# ``window.DATA = DATA;`` passes a name on, not figures. Only when nothing
# follows the name: a line break before ``.concat([...])`` is not the end.
_DATA_NAME_RE = re.compile(r'[A-Za-z_$][\w$.]*\s*(?:[;,)]|\Z)')
# A row value with one of these, raw on the page, is markup Design copied.
_MARKUP_UNSAFE = ('<', '>', '"')


def _server_data_values(blocks):
    """What the server writes as DATA for ``blocks``, as plain JSON values."""
    values = [_flat_rows(blocks)]
    values.extend(data for _keys, data in _row_payloads(blocks))
    dumped, _note = figures_for_design(blocks)
    try:
        values.append(json.loads(dumped))
    except ValueError:
        _logger.debug('Chatboo canvas: figures are not JSON', exc_info=True)
    return [
        json.loads(json.dumps(value, ensure_ascii=False, default=str))
        for value in values
    ]


def _model_data_left(page, blocks):
    """True when the page assigns DATA figures the server did not write.

    Read inside each <script> as the server cuts it: a value that closes
    the script leaves JSON that does not parse.
    """
    text = page or ''
    server = _server_data_values(blocks)
    dec = json.JSONDecoder()
    seen = 0
    for match in _SCRIPT_INNER_RE.finditer(text):
        inner = match.group(2)
        for hit in _DATA_ASSIGN_RE.finditer(inner):
            seen += 1
            if _DATA_NAME_RE.match(inner, hit.end()):
                continue
            try:
                val, _end = dec.raw_decode(inner, hit.end())
            except ValueError:
                return True
            if val not in server:
                return True
    return len(_DATA_ASSIGN_RE.findall(text)) > seen


def _markup_values(blocks, title=''):
    """Row values, keys and titles that would be markup if left raw."""
    found = []
    seen = set()

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if not str(key).startswith('_'):
                    walk(str(key))
                # Private fields still go to Design's sample and to DATA.
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            text = value.strip()
            if (
                len(text) >= 3 and text not in seen
                and any(char in text for char in _MARKUP_UNSAFE)
            ):
                seen.add(text)
                found.append(text)

    walk(title or '')
    for block in blocks or []:
        walk(block.get('title') or '')
        walk(block.get('data') or [])
    return found


def _raw_value_left(page, blocks, title=''):
    """The first such value that sits raw in ``page``, or None.

    The server never writes one raw: scripts get ``\\u003c`` and ``\\"``,
    tables get ``&lt;`` and ``&quot;``.
    """
    text = page or ''
    for value in _markup_values(blocks, title):
        forms = [value]
        # Copied into a JS string, " becomes \": look for that form too. It
        # keeps < or > raw, which the server never writes, so no false hit.
        if '<' in value or '>' in value:
            forms.extend(
                json.dumps(value, ensure_ascii=ascii_only)[1:-1]
                for ascii_only in (False, True)
            )
        if any(form in text for form in forms):
            return value
    return None


_VOID_TAGS = frozenset((
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
    'meta', 'source', 'track', 'wbr',
))


class _PageRowsText(HTMLParser):
    """Text inside the server's ``#pns-page-rows`` tables, entities decoded."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.texts = []

    def handle_starttag(self, tag, attrs):
        if tag in _VOID_TAGS:
            return
        if self.depth:
            self.depth += 1
        elif dict(attrs).get('id') == 'pns-page-rows':
            self.depth = 1

    def handle_endtag(self, tag):
        if self.depth and tag not in _VOID_TAGS:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth and data.strip():
            self.texts.append(data)


def page_rows_texts(page):
    """The values of the tables the server wrote in ``#pns-page-rows``.

    Only to know what to look for: an empty list means there is nothing to
    check against, never that the page is safe.
    """
    try:
        parser = _PageRowsText()
        parser.feed(page or '')
        parser.close()
    except (AssertionError, NotImplementedError, ValueError):
        _logger.debug('Chatboo canvas: could not read the page rows', exc_info=True)
        return []
    return parser.texts


class _PageMarkupText(_PageRowsText):
    """Text of the whole page, outside scripts and styles, that holds < or >."""

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth and ('<' in data or '>' in data):
            self.texts.append(data)


def page_markup_texts(page):
    """Visible text of ``page`` with < or > once decoded: what an edit must
    not unescape. A change may have moved a value out of ``#pns-page-rows``.
    """
    try:
        parser = _PageMarkupText()
        parser.feed(page or '')
        parser.close()
    except (AssertionError, NotImplementedError, ValueError):
        _logger.debug('Chatboo canvas: could not read the page text', exc_info=True)
        return []
    return parser.texts
```

**C8, envoltura y renombrado** (3879 `:2358-2382`). Sustituye a la línea `:2122`. El docstring y el cuerpo del fabricante
siguen detrás sin cambios:

```python
# Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
def place_rows_on_page(design, rows, captured=False, title=''):
    """``_place_rows_on_page``, or the rescue page when that is not safe.

    The rescue page (escaped tables) replaces a design that still assigns
    DATA figures the server did not write, or that has a row value or the
    title with ``<``, ``>`` or ``"`` as raw text.
    """
    page = _place_rows_on_page(design, rows, captured=captured, title=title)
    blocks = _blocks_for_page(rows)
    if not blocks:
        return page
    name = (title or '').strip() or page_title(rows, blocks)
    if _model_data_left(page, blocks):
        reason = 'DATA the server did not write'
    elif _raw_value_left(page, blocks, name) is not None:
        reason = 'a raw row value'
    else:
        return page
    _logger.info('Chatboo canvas: the page kept %s; rescue page', reason)
    return _finish_rescue(_page_for_rows(blocks))


# Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
def _place_rows_on_page(design, rows, captured=False, title=''):
```

**S1, importaciones** (3879 `:1081-1083`), dentro del `from .chatboo_canvas import (…)` de `_paint_canvas`, entre `:1098` y
`:1099`:

```python
            # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
            _blocks_for_page, _const_data_value, _raw_value_left,
            _rows_from_const_data, page_markup_texts, page_rows_texts,
```

**S2, D, B1 y n1** (3879 `:1093-1113`), entre `:1107` y `:1108`:

```python
        # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
        # A change without rows keeps the open page's figures: the server
        # writes them again, so Design cannot change or unescape them.
        bind_rows, bind_title, kept_texts = rows, title, []
        if page and not _blocks_for_page(rows):
            bind_rows = _rows_from_const_data(_const_data_value(page))
            bind_title = title or self.canvas_title or ''
            if not _blocks_for_page(bind_rows):
                # No DATA to write again: check the change against the
                # values of the server's own tables, or do not change it.
                kept_texts = page_rows_texts(page)
                if not kept_texts:
                    return log_no_page(
                        self.env,
                        'the open page has no figures to keep; '
                        'change it with its rows',
                        session_id=self.id,
                    )
                # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
                # An earlier change may have moved a value out of the table.
                kept_texts += page_markup_texts(page)
```

**S3 y S4** (3879 `:1194-1209`). Sustituyen a `:1188-1193` (`rows` pasa a `bind_rows` y `title` a `bind_title`; detrás va
B1 tras pintar):

```python
            # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
            content = swap_pictures(place_rows_on_page(
                sync_canvas_title_phrases(raw, title),
                bind_rows,
                captured=True,
                title=bind_title,
            ), images)
            # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
            if kept_texts and _raw_value_left(
                content, [{'title': '', 'data': kept_texts}],
            ) is not None:
                return log_no_page(
                    self.env,
                    'the change left a value of the page as markup',
                    session_id=self.id,
                )
```

### 4. Tests

Archivo: `pns_ai_chatboo/tests/test_seges_chatboo_canvas.py`. Clase `TestSegesCanvasModelData` de la copia de la fase 0
(`:489-753`), **N = 15 tests**. Etiquetas, las de la 3879: `post_install`, `-at_install`, `pns_ai_chatboo`, `seges_e3p`.

Se portan también sus constantes y helpers (fase 0, `:458-486`, con su comentario): `P29_MARK`, `P29_QUOTE`, `P29_ROWS`, `P29_PLAIN`,
`P29_DATA`, `P29_SAMPLE_NOTE`, `_p29_design` y `_p29_copied_sample`. Van detrás de `TestSegesCanvasHeaders` (`:494-549`),
con el marcador `# Seges: parche 29 (P-8e a, seguridad)`. Todo lo demás que usan ya está en el archivo: `html`, `json`,
`mock`, `canvas`, `collect_sandbox_helpers`, `LLM`, `EVIL`, `EVIL_COMMENT`, `BREAKOUTS` y `_json_after`.

**`setUp`:** se porta tal cual (`collect_sandbox_helpers` con `user_a` y `ai_session_ref`, como `TestSegesCanvasPictures`,
que ya pasa en 3.1.973). **La adaptación del 27 (página en `su` con `owner_id`) no aplica.** Estos 15 tests no crean
`chatboo.canvas.page`: trabajan sobre `chatboo.session.canvas_design`. La sesión la crea `_SegesCanvasCase` con
`with_user`, y los tests que preparan una página abierta ya escriben en `su` (`self.session_a.sudo().write(…)`).

| Test | Cubre | Port |
|---|---|---|
| `test_sample_copied_evil_first` | A y B, repetición (`EVIL` delante) | Tal cual. Las dos llamadas dependen de `design_figures_centralized`, sin cambios en 3.1.973 |
| `test_sample_copied_comment_first` | ídem, `EVIL_COMMENT` delante | Tal cual |
| `test_sample_copied_retry_error` | repetición con `HTTP 503` | Tal cual |
| `test_data_not_written_by_server` (5 subtests) | A | Tal cual |
| `test_data_forms_bound_kept` (2 subtests) | control de A (`window.DATA = DATA;` y `let DATA` sustituido) | Tal cual |
| `test_raw_value_in_markup` (7 subtests) | B, con las formas JSON y el control `R&D Ltd` | Tal cual |
| `test_page_html_hostile_template` | caso h | Tal cual: `helpers['page_html']` sigue existiendo y ahora llama a `_page_html` |
| `test_edit_rebinds_rows` | D | Tal cual: `helpers['page_edit']` → `_page_edit` → `edit_page` → `_paint_canvas` |
| `test_edit_unescaped_data` | D con A (y la forma JSON de B) | Tal cual |
| `test_edit_raw_value_in_markup` | D con B | Tal cual |
| `test_edit_page_without_data` (6 subtests) | B1 y n1 | Tal cual |
| `test_design_prompt_escaped` | C1 | Tal cual: `P29_SAMPLE_NOTE` es el texto de `open_page` (`:976`) y la muestra sigue llevando `keys` (R8) |
| `test_normal_design_kept` | control | Tal cual |
| `test_hostile_rows_design_kept` | control de falsos positivos (`Seges "P29"`, `R&D`, `O'Brien`, `x > y`, título hostil) y q | Tal cual |
| `test_design_rule_text_content` | regla | Tal cual |

Ninguno «adaptado» ni «no aplica».

**Cabecera del archivo:** una línea nueva tras la del 27 (`:5`), con el mismo estilo:
`# Seges: fase 4 sobre 3.1.973, vuelven los casos del parche 29. Ver docs/pendiente/parches_pns_ai.md`. En el docstring del
módulo, una viñeta del parche 29 junto a la del 27. `tests/__init__.py` no cambia.

**Tests de otras clases que pasan por la envoltura** (sin cambios, deben seguir en verde):
- `TestSegesCanvasScriptJson.test_whole_page` (título `EVIL`, DATA sustituido: B no salta, porque TITLE va escapado);
- `TestSegesCanvasPictures.test_page_html_*` y `test_page_url_*` (filas sin `<`, `>` ni `"`).

### 5. Neutralizaciones

Método de la fase 4:
1. SHA-256 de referencia de los dos archivos ya parcheados, anotado antes de la primera;
2. copia, cambio comprobado con una coincidencia exacta y batería completa;
3. restauración y SHA-256 IGUAL tras cada una.

**SHA-256 de referencia:**

| Archivo | En `d9d4f82` (antes del parche) | Previsto con el parche (simulación) |
|---|---|---|
| `pns_ai_chatboo/models/chatboo_canvas.py` | `bb42701991968f2b11042fb1b69e4541045040be88bbe9bdd9d3230c0c3377d1` (el de referencia del 27) | `3f8daf37f21af0746c674d65a07bc63ccd36c73eeef48c154753ee61334f6afc` |
| `pns_ai_chatboo/models/chatboo_session.py` | `739c3b7fdfcc0b5a6007abf5e439ed505ac97852a0ba6a3228d52fe716778d5e` | `40e8c4f5d51a8cb86e4ccafbebb031aefa14ecdb292494da00637aa764d5714a` |

El previsto solo vale si el archivo implementado sale byte a byte como la simulación. La referencia de las
neutralizaciones es la que se anote tras implementar.

En la tabla, «registro» es la fila equivalente de la 3879 (punto 5 de la entrada del 29). Las líneas son «tras el parche».

| Id | Qué se retira | Debe caer (además de `test_paap_i7`) | F/E | Registro |
|---|---|---|---|---|
| N29r | la regla (`chatboo_canvas.py:72-75`) | `test_design_rule_text_content` | F | En la 3879 no se neutralizó («es un texto») |
| N29c1 | `dumped = _script_safe(dumped)` → `dumped = dumped` (`:916`) | `test_design_prompt_escaped` | F | N29c1 |
| N29A | `if _model_data_left(page, blocks):` → `if False:` (envoltura) | los 5 subtests de `test_data_not_written_by_server`. `test_edit_unescaped_data` **no** cae (lo detecta la forma JSON de B) | F | N29a |
| N29B | `elif _raw_value_left(page, blocks, name) is not None:` → `elif False:` (envoltura) | 6 subtests de `test_raw_value_in_markup` (el de `R&D Ltd` pasa) y `test_edit_raw_value_in_markup` | F | N29b |
| N29env | la envoltura no revisa: `blocks = _blocks_for_page(rows)` → `blocks = []` (devuelve lo del fabricante) | lo de N29A y N29B más `test_sample_copied_evil_first`, `test_sample_copied_comment_first`, `test_sample_copied_retry_error`, `test_page_html_hostile_template` y `test_edit_unescaped_data`: 11 subtests y 6 tests. `test_hostile_rows_design_kept` pasa (llama a A y B directamente) | F | N29ab |
| N29q | `_cell_html` vuelve a `quote=False` (`:1115`) | `test_hostile_rows_design_kept` y el subtest `R&D Ltd` de `test_raw_value_in_markup` | F | N29q |
| N29D | D entero: `if page and not _blocks_for_page(rows):` → `if False:` (`chatboo_session.py:1115`) | `test_edit_rebinds_rows`, `test_edit_unescaped_data`, `test_edit_raw_value_in_markup` y 3 subtests de `test_edit_page_without_data`: (2) hostil, (2) hostil con filas escalares y (3). **Previsto, además:** «dos pasos, hostil» (n1 está dentro de esa rama y su subtest es posterior a N29d) | F | N29d |
| N29B1 | `if not _blocks_for_page(bind_rows):` → `if False:` (`chatboo_session.py:1118`) | los 3 subtests de N29D. **Previsto, además:** «dos pasos, hostil», por el mismo motivo. El (2) inocente pasa | F | N29e |
| N29n1 | `kept_texts += page_markup_texts(page)` → `kept_texts += []` (`chatboo_session.py:1131`) | el subtest «dos pasos, hostil»; «dos pasos, inocente» pasa | F | N29f |
| N29m1 | `_DATA_NAME_RE` con `$` y `re.M` en lugar de `\Z` (`:1597`) | **ninguno** (ver abajo) | — | — |

Ninguna debería dar E. En la 3879, el recuento de E no cambió en ninguna. Si alguna da E, se documenta por nombre sin
cambiar el test. Los subtests se confirman, como en el 27, por el total del runner y por un grep de nombres.

**Lo que no tumbaría ningún test (medido en memoria sobre la simulación, `…/p29/variantes_q.py` y `variantes_m.py`):**
- **N29q, por partes.** La parte de `_cell_html` sí tumba los dos tests de arriba. Las otras dos **no tumban ninguno de los
  15**:
  - q2: `_rows_as_table` con `quote=False`;
  - q3: `_page_shows_rows` sin la forma `&quot;`.

  Test propuesto, **no añadido**: `test_quoted_values_in_server_table`, con dos subtests:
  - filas escalares con `"` (`['Seges "P29" uno', 'Seges P29 dos']`) sobre `_p29_design('var n = 1;')`: el diseño se
    conserva (cae con q2 y con q3);
  - filas con `"` en diccionarios sobre el mismo diseño: el diseño se conserva con la tabla del servidor en su hueco y
    `pns-page-rows-visible` (cae con q1 y con q3).
- **N29m1.** Ninguno de los 15 tiene un `window.DATA = DATA` seguido de un salto de línea y `.concat(…)`. Subtest propuesto,
  **no añadido**, en `test_data_not_written_by_server`:
  `P29_DATA + ' window.DATA = DATA' + chr(10) + '.concat([{"id": 9, "name": "x"}]);'` → rescate. Con m1 da rescate; sin m1
  conserva el diseño (comprobado en memoria). No cambia el número de tests.
- **m3 y m8** no se piden como neutralización. m3 (bajar a las claves `_…`) tampoco lo cubre ningún test: lo detectaría un
  valor `EVIL` en `_note` copiado en el HTML (comprobado en memoria). m8 (el conjunto `seen`) solo evita repetidos y no
  cambia ningún resultado.

### 6. Recuento previsto

- **Línea base** (tras el 27): 541 tests, 1 F (`TestSystemTrustedActions.test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin`),
  0 E y 6 saltados:
  - `test_backend_starts_without_errors`;
  - `test_a_pending_field_is_left_on_the_record_itself`;
  - `test_typed_readers_keep_secret_keys_out`;
  - `test_typed_setters_do_not_return_a_secret`;
  - `test_execute_success_no_serialization_failure`;
  - `test_execute_bus_notice_survives_retry`.
- **Previsto con el 29:** **556 tests (541 + 15)**, 1 F (el mismo), 0 E y los mismos 6 saltados.
- Con el test propuesto para q2/q3: 557. El subtest de m1 no cambia el número.
- Si alguno de los 15 falla, o cambia algún test que hoy pasa (en particular `test_whole_page` o los de
  `TestSegesCanvasPictures`), se informa por nombre antes de seguir.

### 7. Riesgos residuales de la 3879, en 3.1.973

| Riesgo (registro, «Parche 29») | En 3.1.973 con el parche |
|---|---|
| **`innerHTML` en el código del diseño** (también `outerHTML`, `insertAdjacentHTML` y `document.write`) | **Igual.** El servidor no puede garantizarlo leyendo el JavaScript. Lo reduce la regla C2. La contención es mayor que en la 3879: en el marco se aplican la cabecera del fabricante y la `<meta>` del 27, y en las descargas, la `<meta>`. El impacto sigue siendo la navegación del marco (ninguna de las dos políticas la limita) |
| **Comilla simple en atributos** (B no revisa `'`) | **Igual**, con la misma contención |
| **Páginas guardadas antes del parche** | **Igual en el mecanismo:** el 29 actúa al pintar y al guardar, no al servir. **Cambia el alcance:** se suman los diseños pintados con 3.1.973 sin el 29 (`lab_pns_ai_3973_14` desde el 11/11/2026: A7 contó 4 en `canvas_design` y 0 en `chatboo.canvas.page.design`). El fragmento de medición del registro no depende del 29 y sirve tal cual. Si la edición sin filas cae en el caso 2 de B1 (página sin DATA legible de filas), la protegen B1 y n1, como en la 6d′ del laboratorio de la 3879 |
| **o1** (n1 no cubre valores que una edición anterior dejó en un atributo, un comentario, un `<script>`, un `<style>` o codificados) | **Igual:** `_PageMarkupText` es el mismo y la imagen sigue con Python 3.7.3 |
| **o2** (falso positivo con `>` o `->` en crudo en el texto visible, en el caso 2 de B1) | **Igual:** solo afecta a la edición sin filas sobre páginas sin DATA legible de filas |
| m4, m5, m6, n2 y el valor inventado por el modelo | **Igual** |
| m7 (HTML del código del orquestador en `page_html`) | **Igual**, ahora en `_page_html` (`chatboo_session.py:916`). El sandbox lo sigue llamando `page_html` |

### Registro, plan y laboratorio (al implementar; ahora no se editan)

- **Registro:** entrada del 29 en «Parches de la rama 14.0-pns-ai-3973 (fase 4, 13/11/2026)», con:
  - los bloques y sus líneas;
  - el punto 2;
  - tests, batería, neutralizaciones y riesgos;
  - el índice de la rama (fila 29) pasa a «Aplicado».
- **Plan:** un bloque nuevo debajo de «Fase 4», 29, sin reescribir el fechado.
- **Laboratorio** (procedimiento fijo): 5a a 5c y 6c a 6e de [lab_p29_3879.md](lab_p29_3879.md), adaptados a 3.1.973, más la
  medición de las páginas guardadas sin el 29 en `lab_pns_ai_3973_14`. Automatización con Chrome según lo decidido el
  13/11/2026.

### Decisiones pendientes de Sergio (parche 29)

| Id | Decisión | Recomendación |
|---|---|---|
| D11 | Añadir `test_quoted_values_in_server_table` (2 subtests), para que q2 y q3 tengan un test que caiga | **Sí.** Sin él, dos de las tres líneas de q no tienen test, y q es lo que evita los rescates falsos con `"` |
| D12 | Añadir el subtest de m1 a `test_data_not_written_by_server` | **Sí.** Es una línea, y m1 fue un aviso de la revisión |
| D13 | Neutralizar también q2 y q3 por separado (N29q2, N29q3) si se aprueba D11 | **Sí**, con D11 |
| D14 | Medir antes del laboratorio, en solo lectura, los diseños guardados sin el 29 en `lab_pns_ai_3973_14`, con el fragmento del registro | **Sí:** fija la línea base del riesgo «páginas guardadas antes» en 3.1.973 |

### Decisiones de Sergio (16/11/2026, parche 29)

6. **D6:** se porta el 29 entero de la 3879 (regla de `textContent`, C1, A, B, envoltura, q, D con B1 y n1, m1, m3 y m8),
   no solo las dos funciones que citaba el plan.
7. **D7:** envoltura `place_rows_on_page` sobre la del fabricante, renombrada `_place_rows_on_page`. Se mantiene tras
   confirmar los llamadores (punto 2 de la propuesta).
8. **D8:** la regla del 29 va en un bloque propio con su marcador, detrás de la del 27 c en `_PAGE_RULES`.
9. **D9:** el defecto de `keys` de R8 queda fuera del 29 (informe al fabricante); no impide ningún test.
10. **D10:** laboratorio del 29 corto y automatizado, sin LLM, con `lab_cdp.py` y `lab_auto.sh`
    (`~/pns_ai_3973/fase4/lab/`). Cubre las sesiones 4 y 8, su descarga y la medición de DATA ilegible antes (D14) y
    después. Los casos con el modelo real (6c y 6d′ de [lab_p29_3879.md](lab_p29_3879.md)) van junto a P-13 del 34, que
    también necesita proveedor.
11. **D11 sí:** `test_quoted_values_in_server_table` (2 subtests).
12. **D12 sí:** subtest de m1 en `test_data_not_written_by_server`.
13. **D13 sí:** N29q2 y N29q3.
14. **D14 sí:** medición en solo lectura de `lab_pns_ai_3973_14` antes del laboratorio.

Además:
- confirmado que en los 15 tests no se aplica la adaptación de la página en `su`;
- compilación con Python 3.7.3 mediante `py_compile.compile`, con el `.pyc` en `/tmp` y la versión impresa (forma fija a
  partir de ahora; registro, «Parche 29 en 3.1.973»);
- conclusión (a) de la investigación sobre el parche 38 (ningún camino de producción provoca la escritura pisada ni la
  espera bloqueada) y adaptación de `test_edit_page_without_data` con `self.env['base'].flush()` y el comentario «solo vale
  en modo test».

## Implementación y resultados del parche 29 (16/11/2026)

- **Archivos de trabajo** (`~/pns_ai_3973/fase4/29/`):
  - `simulacion/`: copia de la simulación, con SHA-256 igual a la del scratchpad (15 archivos);
  - `d14_medicion.py` y `d14_resultado.txt`;
  - `sha256_antes.txt` y `sha256_parche.txt`;
  - `aplicar.py` y `tests_aplicar.py`;
  - `neutralizar.py`, `neutralizar.sh` y `neutralizaciones.txt`;
  - `chatboo_canvas.py.parche` y `chatboo_session.py.parche`.
- **D14 (antes del laboratorio):**
  - cómo conecta: `odoo-dev 14 shell` con el script por la entrada estándar. Es `dc run --rm web odoo shell -d <BD>`
    (`entorno.sh:503-507`): un contenedor de un solo uso que levanta solo `db` (`depends_on`), sin el servicio `web` ni
    crons. Guarda de BD y `rollback` al final;
  - resultado:

    | Modelo | Diseños | Con DATA ilegible |
    |---|---|---|
    | `chatboo.session.canvas_design` | 4 | 0 (sesiones: ninguna) |
    | `chatboo.canvas.page.design` | 0 | 0 |

- **Código:** los 12 bloques con sus 14 marcadores, aplicados con `aplicar.py` (las 17 anclas comprobadas y los bloques
  copiados por rango de líneas de la 3879). SHA-256 iguales a los previstos (`3f8daf37…` y `40e8c4f5…`). Escapes del 27
  intactos y ningún U+2028/U+2029 literal (comprobado con `chr(92)`). Lint: 0 incidencias nuevas.
- **Compilación con 3.7.3:** la forma `-m py_compile` falló con `OSError: [Errno 30] Read-only file system` al escribir el
  `.pyc`, no por el código. Con `py_compile.compile` y el `.pyc` en `/tmp`: «3.7.3 COMPILA 2» (modelos) y «3.7.3 COMPILA 1»
  (test), con código 0.
- **Tests:** `TestSegesCanvasModelData` con 16 tests: los 15 de la 3879, `test_quoted_values_in_server_table` (D11) y el
  subtest de m1 (D12). `test_edit_page_without_data`, adaptado (`flush()` tras las dos escrituras de la sesión, `:769-773` y
  `:802-806`).
  - `tests_aplicar.py` se paró una vez antes de escribir, por una comprobación mal planteada: exigía que no hubiera ningún
    U+2028 literal, y el 27 los lleva a propósito en sus casos. Se cambió por «el texto nuevo no añade ninguno».
- **Baterías:**

  | Log | Tests | F | E | Saltados | Traceback | bad query | seges_side_env | Secretos |
  |---|---|---|---|---|---|---|---|---|
  | `tests-20261116-095208.log` (sin adaptar) | 557 | 4 (`test_paap_i7` y 3 subtests de `test_edit_page_without_data`) | 0 | 6 | 61 | 1 | 1 | 0 |
  | `tests-20261116-100426.log` (con `flush()`) | 557 | 1 (`test_paap_i7`) | 0 | los 6 | 58 | 1 (`UPDATE "ai_safe_operation"`) | 1 | 0 |

  - Los 3 subtests de la primera fallaban por la escritura pendiente del test (parche 38): «(2) inocente», «dos pasos,
    hostil» y «dos pasos, inocente». Investigación en solo lectura y conclusión (a) en el registro, «Parche 29 en
    3.1.973».
  - Origen de los módulos: `addons paths` con `/mnt/compartidos/third_party`; 0 `pns_*` en `~/odoo-dev/14.0/oca/*`, en
    `/usr/lib/python3/dist-packages/odoo/addons` de la imagen y en `addons/14.0` del volumen `odoo-dev-14_web-data`
    (montado en solo lectura).
- **Neutralizaciones** (método de la fase 4, sobre el código con la adaptación; además de `test_paap_i7`; todas F, 0 E y
  SHA-256 IGUAL en los dos archivos):

  | Id | Qué se retira | Log | Runner | Caen | ¿Lo previsto? |
  |---|---|---|---|---|---|
  | N29r | la regla | `tests-20261116-100824.log` | 2 | `test_design_rule_text_content` | Sí |
  | N29c1 | C1 | `-101153` | 2 | `test_design_prompt_escaped` | Sí |
  | N29A | A en la envoltura | `-101526` | 7 | 6 subtests de `test_data_not_written_by_server` | Uno más: el de D12, que es un caso de A |
  | N29B | B en la envoltura | `-101852` | 8 | 6 subtests de `test_raw_value_in_markup` y `test_edit_raw_value_in_markup` | Sí |
  | N29env | la envoltura no revisa (`blocks = []`) | `-102208` | 19 | 12 subtests (6 de A con el de D12, 6 de B) y `test_sample_copied_evil_first`, `test_sample_copied_comment_first`, `test_sample_copied_retry_error`, `test_page_html_hostile_template`, `test_edit_unescaped_data` y `test_edit_raw_value_in_markup` | Sí, más el de D12 |
  | N29q | `_cell_html` con `quote=False` | `-102520` | 4 | `test_hostile_rows_design_kept`, el subtest `R&D Ltd` y `test_quoted_values_in_server_table` [filas con columnas] | Sí |
  | N29q2 | `_rows_as_table` con `quote=False` | `-102833` | 2 | `test_quoted_values_in_server_table` [filas escalares] | Sí |
  | N29q3 | `_page_shows_rows` sin `&quot;` | `-103148` | 4 | los 2 subtests de `test_quoted_values_in_server_table` y `test_edit_page_without_data` por su premisa (`:754-756`) | Uno más: sin `&quot;`, el diseño sin DATA cae a `_page_for_rows`, que escribe `const DATA` |
  | N29m1 | `_DATA_NAME_RE` con `$` y `re.M` | `-103502` | 2 | el subtest de D12 | Sí |
  | N29D | D entero | `-103815` | 8 | `test_edit_rebinds_rows`, `test_edit_unescaped_data`, `test_edit_raw_value_in_markup` y 4 subtests: (2) hostil, (2) hostil con filas escalares, (3) y «dos pasos, hostil» | Sí, con «dos pasos, hostil» |
  | N29B1 | B1 (`if False:`) | `-104127` | 5 | (2) hostil, (2) hostil con filas escalares, (3) y «dos pasos, hostil» | Sí, con «dos pasos, hostil» |
  | N29n1 | cierre de n1 | `-104439` | 2 | «dos pasos, hostil» | Sí |

  - Con el `flush()`, los subtests de rechazo de `test_edit_page_without_data` caen al retirar B1 (N29D y N29B1), no por la
    escritura pendiente. «(2) inocente» y «dos pasos, inocente» pasan en todas.
  - Los subtests salen en el log como `FAIL: Subtest <Clase>.<test> [etiqueta]` o `(clave=…)`. Se confirman con el total
    del runner y con un grep de nombres.
- **Laboratorio:** hecho (16/11/2026): automatizado y sin LLM (D10), sin incidencias en `canvas/4`, `canvas/8` y la
  descarga de la 8 (código 0; C solo con `?` y `lab_pns_ai_3973_14`); fila del 16/11/2026 en el «Registro de
  laboratorios» de [lab_procedimiento_3973.md](lab_procedimiento_3973.md). Los casos con el modelo real, con P-13 del 34.
  La autoprueba de `lab_cdp.py` pasó el 16/11/2026 (12 PASA, código 0).

## Parche 34 en 3.1.973 (16/11/2026)

- **Fecha:** 16/11/2026. **Rama:** `14.0-pns-ai-3973`, código en `05a05a5` (HEAD `c278827` solo añade documentación; no
  comprobado con git).
- **Fuente:** rama `14.0-pns-ai-3879`, rev. `3feb224a20175c16d2ace5ee5aa64418756747bc` (`/tmp/p34_codigo/seges3879/`, con
  `SHA256SUMS` comprobado): `pns_ai_chatboo/models/chatboo_canvas.py`, `pns_ai_chatboo/models/chatboo_async_request.py` y
  `pns_ai_chatboo/tests/test_seges_chatboo_canvas.py`. Registro, «Parche 34: aviso fijo del servidor cuando `log_no_page`
  rechaza en un turno (PNS-96)» y «Parches de la rama 14.0-pns-ai-3879 (E4′.b2 y E4′.b3)» (opción A y F1).

### Propuesta

- **Código del fabricante en las zonas del 34:** igual entre 3.1.879 y 3.1.973 salvo comentarios, docstrings, mensajes
  de log e imports. Comparado sin comentarios (`tokenize`), función a función:
  - `log_no_page`: igual;
  - `_process`: las diferencias de 3.1.973 (empresas de la pantalla en `get_fresh_query_data` y en la llamada al motor,
    `_prompt_runs_a_skill`, `turn_file_names`) quedan fuera de la apertura tras `_notify('thinking')` y del `finally`;
  - `_save_to_session`: las diferencias (`result_note` en el mensaje del usuario, `last_query_company_ids`) quedan fuera
    de la rama de éxito y de su diccionario.
- **Porte por anclajes:** los bloques del 34 se copian tal cual de la 3879 en 10 puntos, cada uno sobre un anclaje que
  aparece una sola vez en el archivo (paso 0 b, abajo). No cambia nada del código del fabricante que los rodea; solo se
  sustituyen `'content': acc or ''` y `'original_content': acc or ''` del diccionario de la rama de éxito.
- **Comprobaciones nuevas** (condiciones del plan del 16/11/2026, desde el parche 29):
  - invariante 2: que el 34 no escriba la fila de `chatboo.session` en el cursor del turno después del motor;
  - invariante 1: si la caja B puede escribir `canvas_*` y llamar a `page_edit` en la misma transacción.

### Decisiones de Sergio (16/11/2026, parche 34)

15. **D15:** porte literal del parche 34 de la 3879: opción A y F1, 12 marcadores, mismo texto y mismo msgid.
16. **D16:** la marca se abre tras `self._notify('thinking')` y el `reset` es la primera línea del `finally` del `try` del
    motor. El `return` temprano de la confirmación fallida (`chatboo_async_request.py:339` antes del parche) queda sin
    `reset`, como en la 3879.
17. **D17:** la lectura de `canvas_rev` al abrir la marca sigue sin `try`.
18. **D18:** se portan los 9 tests de `TestSegesNoPageNotice` tal cual.
19. **D19:** las invariantes 1 y 2 del parche 38 se anotan en el registro y no llevan código.

## Implementación y resultados del parche 34 (16/11/2026)

- **Paso 0 (solo lectura):**
  - fuente: `sha256sum -c` de `/tmp/p34_codigo/SHA256SUMS` correcto;
  - SHA-256 antes (copias en `/tmp/p34_antes/`):

    | Archivo | Antes | Con el parche |
    |---|---|---|
    | `pns_ai_chatboo/models/chatboo_canvas.py` | `3f8daf37f21af0746c674d65a07bc63ccd36c73eeef48c154753ee61334f6afc` | `78ee3ea46bc4749d119d5c252a1b5e61a0795ce9aebce9932c005ee742198a61` |
    | `pns_ai_chatboo/models/chatboo_async_request.py` | `112f0dc8377e0ad807d86f99e93fe204a7ee418e0198e36d8b90abe82a85f52c` | `f992a1bd4b8a510cb9d44e580f1b2c82e38252915087ee748c7759d84392e3d7` |
    | `pns_ai_chatboo/tests/test_seges_chatboo_canvas.py` | `903d611908a6ba1d7a220be50728bb0150c18cbbd3866df820be2d54d4097c03` | `4f65f4243994f3589ee0c092362aa7d9f3d156fcf753c3554a9a212eb63c564a` |

    «Con el parche» son los SHA-256 finales, tras el cierre (cita del comentario de F1 y cabecera del test). Los del
    paso 3 y de las seis primeras neutralizaciones eran `9696786f…` (`chatboo_async_request.py`) y `aa11275b…` (test);
    `chatboo_canvas.py` no cambia en el cierre.

  - los 10 anclajes (4 en `chatboo_canvas.py` y 6 en `chatboo_async_request.py`, con el diccionario de la rama de éxito),
    1 vez cada uno;
  - el msgid «No page was built. The reason is in the AI History.» está en `pns_ai_chatboo/i18n/es.po:2213` y lo usa
    `chatboo_canvas_job.py:133` y `:156`. No se toca `i18n`;
  - invariante 2 y caja B: resultado en el registro, «Parche 34 en 3.1.973».
- **Código (paso 1):** 10 bloques con 12 marcadores (5 en `chatboo_canvas.py` y 7 en `chatboo_async_request.py`). Cada
  bloque añadido es una subcadena literal del archivo de la 3879. Líneas tras el parche:
  - `chatboo_canvas.py`: import de `ContextVar` (`:20-21`), `_NO_PAGE_WATCH` (`:29-32`), `watch_no_page` (`:653-658`),
    `page_refused_in_job` (`:661-668`) y la anotación en `log_no_page` (`:679-688`). Son las mismas líneas que en la 3879;
  - `chatboo_async_request.py`: `import html` (`:12-13`), import de `_NO_PAGE_WATCH`, `page_refused_in_job` y
    `watch_no_page` (`:21-22`), apertura de la marca (`:167-169`), `reset` (`:539-540`), composición F1 (`:1361-1376`),
    `'content': _content` (`:1434`) y la opción A antes de `'original_content': _content` (`:1435-1438`). El `return`
    de D16 queda en `:346`.
  - `grep -rn "Seges: parche 34 (" pns_ai_mcp pns_ai_chatboo --include=*.py | grep -v /tests/` → 12.
  - Compila con Python 3.7.3: «3.7.3 COMPILA 3».
- **Tests (paso 2):** al final de `pns_ai_chatboo/tests/test_seges_chatboo_canvas.py`, el marcador, `NO_PAGE_ACC`,
  `NO_PAGE_NOTICE` y `TestSegesNoPageNotice(_SegesCanvasCase)` (etiqueta `seges_e4p`, 9 tests), copiados por rango de
  líneas (`:756-864` de la 3879). `_SegesCanvasCase` es igual en las dos ramas. Lint `--revisar --base 05a05a5`: 0
  incidencias nuevas.
- **Batería (paso 3):**

  | Log | Tests | F | E | Saltados | Traceback | bad query | seges_side_env | Secretos |
  |---|---|---|---|---|---|---|---|---|
  | `tests-20261116-100426.log` (línea base) | 557 | 1 (`test_paap_i7`) | 0 | 6 | 58 | 1 | 1 | 0 |
  | `tests-20261116-125048.log` (con el 34) | 566 | 1 (`test_paap_i7`) | 0 | los 6 | 58 | 1 (`UPDATE "ai_safe_operation"`) | 1 | 0 |
  | `tests-20261116-131620.log` (final, tras las neutralizaciones) | 566 | 1 (`test_paap_i7`) | 0 | los 6 | 58 | 1 | 1 | 0 |

  - los 9 de `TestSegesNoPageNotice`, en verde;
  - origen de los módulos: `addons paths` con `/mnt/compartidos/third_party`; 0 `pns_*` en `~/odoo-dev/14.0/oca`, en la
    imagen `odoo-dev:14-lab_pns_ai_3973` y en el volumen `odoo-dev-14_web-data` (montado en solo lectura). Contexto
    activo: el de `lab_pns_ai_3973`, el mismo de la línea base.
- **Neutralizaciones (paso 4):** una cada vez, batería completa, restauración con SHA-256 igual al del paso 3. Además de
  `test_paap_i7`; todas con 0 E y los 6 saltados:

  | Id | Qué se retira | Log | Runner | Caen | ¿Lo previsto? |
  |---|---|---|---|---|---|
  | N34m | `log_no_page` no anota (`pass` en lugar de `watch['refused'] = True`) | `tests-20261116-125537.log` | 5 | `test_notice_after_refusal`, `test_notice_unknown_session`, `test_notice_empty_answer` y `test_notice_html_answer` | Sí |
  | N34s | `_save_to_session` no añade el aviso (`if False and page_refused_in_job(…)`) | `-125902` | 5 | los mismos cuatro | Sí |
  | N34r | `page_refused_in_job` no compara `canvas_rev` | `-130220` | 2 | `test_no_notice_when_page_changed` | Sí |
  | N34j | `page_refused_in_job` no compara el job | `-130546` | 2 | `test_no_notice_other_job` | Sí |
  | N34o | `original_content` vuelve a `acc or ''` | `-130917` | 5 | los cuatro con aviso | Sí |
  | N34h | F1 fuerza siempre el markdown (`if False:`) | `-131244` | 2 | `test_notice_html_answer` | Sí |
  | N34x | la anotación no compara la sesión (`same = True` antes de `if same:`; cierre, S1) | `tests-20261116-155852.log` | 2 | `test_no_notice_other_session` | Sí |

  - `test_no_notice_without_refusal`, `test_no_notice_other_session` y `test_no_watch` pasan en las seis primeras;
    `test_no_notice_without_refusal` y `test_no_watch`, también en N34x. N34x se hizo sobre el código del cierre, con
    restauración al SHA-256 final;
  - Traceback: 62 con 4 F del 34 y 59 con 1, uno por cada test que cae; «bad query», «seges_side_env: » y secretos,
    iguales que en la línea base.
- **Revisión (paso 5):** APROBADO CON OBSERVACIONES: 0 críticos, 0 avisos y 3 sugerencias, que no reabren ninguna
  decisión ni llevan código:
  - **S1:** ningún test ejecuta `_process`: la apertura (`chatboo_async_request.py:167-169`) y el `reset` (`:539-540`)
    solo se validan en el laboratorio (P-13); sin ellos la batería seguiría en verde. Tampoco hay neutralización de la
    comparación de sesión de `log_no_page` (`chatboo_canvas.py:683-688`), que debería tumbar
    `test_no_notice_other_session` (no comprobado).
  - **S2 (junto a D16):** además del `return` de `:346`, una excepción no controlada de `_augment_prompt_with_files`
    (`:248-250`), `_recall_prior_images` (`:358`) o `_start_heartbeat` (`:364`) sale de `_process` antes del `try` del
    motor (`:397`) y sin `reset`. Inocuo: la marca va ligada al id del job, en producción el hilo es nuevo por job y en
    los tests cada uno hace su `reset`. No es un olvido.
  - **S3:** el comentario de F1 cita `chatboo_formatters.js:88-97` (texto literal de la 3879, D15); en 3.1.973
    `isLikelyHtml` está en `:90-99`, con la misma lógica. Además, el cliente de 3.1.973 parte el contenido con
    `splitHtmlAndMarkdownTail` (`chatboo_sse.js:361-393`, llamado desde `chatboo_formatters.js:1074`), así que el
    `<p><em>…</em></p>` tras «tabla + texto» puede caer en la cola tratada como markdown: comprobar en P-13 que se ve en
    cursiva y no como etiquetas.
  - Sin hallazgos en: Python 3.7.3, ciclos de import, `ContextVar` entre hilos (un hilo por job; `_cancel_pending` y el
    job de lienzo no ven la marca; `_reclaim_one` va por la rama `incomplete`), traducción e invariante 2.
- **Laboratorio:** pendiente. P-13 con proveedor real, 6c y 6d′ de [lab_p29_3879.md](lab_p29_3879.md) (D10) y, en
  pantalla, en vivo y al recargar, los casos a′, b′, c y d de «Pintado del aviso en el cliente», abajo.

### Decisiones de Sergio (16/11/2026, cierre del parche 34)

- **Observación de la invariante 1:** aceptada sin código. Es el mismo falso negativo que `test_no_notice_when_page_changed`.
- **S1:** se añade la neutralización N34x (la anotación de `log_no_page` no compara la sesión). La apertura y el `reset` en
  `_process` quedan para P-13 (D18: no se añaden tests).
- **S2:** sin cambio.
- **S3:** se corrige la cita del comentario de F1 a `chatboo_formatters.js:90-99` (solo el comentario,
  `chatboo_async_request.py:1369`). Se añade a la cabecera del test la línea «fase 4 sobre 3.1.973, vuelven los casos del
  parche 34», con la forma de la del 29.
- **Pintado del aviso en el cliente** (abajo): no se reabren D15 ni F1. Es lectura de código, sin confirmar, y no es una
  diferencia entre la 3879 y 3.1.973. Se comprueba en pantalla en el laboratorio del 34. Si se confirma, Sergio decide
  entonces entre aceptarlo, cambiar la forma del aviso en el servidor (parche propio) o parchear el cliente.

### Cierre del parche 34 (16/11/2026)

- **Cambios:** cita del comentario de F1 (`chatboo_async_request.py:1369`, `:88-97` → `:90-99`) y línea nueva en la
  cabecera de `test_seges_chatboo_canvas.py` (`:7`). «3.7.3 COMPILA 3»; lint `--revisar --base 05a05a5`: 0 incidencias
  nuevas; 12 marcadores fuera de `tests/`.
- **N34x:** 2 F (`test_paap_i7` y `test_no_notice_other_session`), 0 E, los 6 saltados; Traceback 59 (uno por el test
  que cae), «bad query» 1, «seges_side_env: » 1 y secretos 0. SHA-256 igual al restaurar.
- **Batería final:** `tests-20261116-160401.log`, 566 tests, 1 F (`test_paap_i7`), 0 E, los 6 saltados; Traceback 58, «bad query» 1
  (`UPDATE "ai_safe_operation"`), «seges_side_env: » 1 y secretos 0, iguales que en la línea base; los 9 del 34 en verde;
  módulos desde `/mnt/compartidos/third_party`.

### Pintado del aviso en el cliente (16/11/2026, lectura de código, sin confirmar)

Solo lectura de `pns_ai_chatboo/static/src/js/` de la rama y de `~/pns_fabricante/3.1.879/` (enlace
`_fabricante/`). No se ha ejecutado nada ni se ha visto en pantalla.

- **Dónde están las funciones:**

  | | 3.1.879 | Rama (= 3.1.973) |
  |---|---|---|
  | `isLikelyHtml` | `chatboo_formatters.js:88-97` | `chatboo_formatters.js:90-99` |
  | `splitHtmlAndMarkdownTail` | `chatboo_sse.js:361-393` | `chatboo_sse.js:361-393` |
  | quién llama a `splitHtmlAndMarkdownTail` | solo `_formatContent` (`chatboo_formatters.js:1072-1073`) | solo `_formatContent` (`chatboo_formatters.js:1074-1075`) |

  - `splitHtmlAndMarkdownTail` ya existía en 3.1.879. El código de pintado es el mismo en las dos versiones:
    `chatboo_markdown.js` es idéntico, y `chatboo_sse.js` y `chatboo_formatters.js` solo cambian en comentarios y en una
    cadena que ahora pasa por `_t`. El `chatboo_formatters.js` y el `chatboo_sse.js` de la rama tienen el mismo SHA-256
    que los de 3.1.973 limpia.
- **Ruta común:**
  - al recargar, el componente toma `original_content || content` y lo pasa por `_formatContent`
    (`chatboo_component_v2.js:1224-1226`);
  - en vivo, al cerrar el turno, el evento `done` trae `assistant_content` (`chatboo_async_request.py:731-738`), que pasa
    por la misma `_formatContent` (`chatboo_component_v2.js:3184-3185` y `:3287`);
  - después se sanea con `sanitizeHtml` (`chatboo_formatters.js:1185`), que conserva `P` y `EM`
    (`_ALLOWED_TAGS`, `:124-135`). Durante el streaming no hay aviso. El resultado es el mismo en vivo y al recargar.
- **Punto clave:**
  - `ChatbooMarkdown.toHtml` escapa todo `<` del texto (`inline`, `chatboo_markdown.js:130`);
  - el `_…_` solo se convierte en `<em>` en la ruta de markdown (`chatboo_markdown.js:112`);
  - `_formatContent` solo entra en esa ruta si el contenido tiene `#`, `` ` ``, `**`, `__`, una lista o una fila de tabla
    (`chatboo_formatters.js:1163-1170`). Un `_…_` suelto no la activa; si no entra, se escapa tal cual (`:1181`).
- **Casos:**

  | Caso | Recorrido | Conclusión |
  |---|---|---|
  | **a.** `<table>…</table>` + `<p><em>aviso</em></p>`, sin `</div>` antes de la prosa o con prosa sin marcas de markdown tras el `</div>` (los tests y T1 del staging) | `splitHtmlAndMarkdownTail` no parte (la cola no cumple `looksLikeMarkdownTail`, `chatboo_sse.js:113-122`); pasa `isLikelyHtml` (`chatboo_formatters.js:1082`) y va a `enhanceHtmlProse` | cursiva |
  | **a′.** Tabla del servidor en `<div>…</div>` + prosa con `##`, `**` o una lista + `<p><em>aviso</em></p>` (el patrón `` `...</div>## Analysis…` `` del fabricante, `chatboo_formatters.js:1071-1073`) | el split separa la cola (`:1074-1078`), con el `<p><em>`, y la pasa a `_formatMarkdown` → `toHtml`, que la escapa | etiquetas literales |
  | **b.** Texto con marcas de markdown + `\n\n_aviso_` | ruta de markdown (`:1174`) | cursiva |
  | **b′.** Texto llano + `\n\n_aviso_` (`NO_PAGE_ACC` de los tests, o «Se ha generado la página» de E3′) | sin marcas: `escapeHtml` (`:1181`) | guiones bajos literales |
  | **c.** Solo `_aviso_` (respuesta vacía) | como b′: ni el aviso ni su traducción tienen marcas | guiones bajos literales |
  | **d.** Texto + tabla incrustada + `\n\n_aviso_` (frontera de F1) | la regex de HTML incrustado (`:1146-1148`) lo manda a `enhanceHtmlProse`; con tabla no se vuelve a leer como markdown; no se ha seguido qué hace con el nodo de texto `_aviso_` | no se puede deducir del código (probablemente literal) |

- **Afecta igual a la 3879**, que tiene el mismo código de pintado.
- **Por qué no se vio en su staging** (`staging_e4_3879.md:1077-1080` y `:1096-1099`): solo salió la forma HTML (T1 y F1-t
  empezaban por `<` y la prosa no llevaba marcas de markdown). Ningún laboratorio ni staging ha visto en pantalla b′ ni c,
  y los tests del servidor comprueban el texto guardado, no cómo lo pinta el cliente.
- **Opciones, si el laboratorio lo confirma:**
  1. aceptarlo y documentarlo, sin código: el aviso se lee, con `_…_` o etiquetas a la vista en a′, b′ y c;
  2. cambiar la forma del aviso en el servidor (parche propio): reabre D15 y F1 y exige tests y neutralizaciones nuevos;
     la forma que funcione en las cuatro rutas está por diseñar y ver en pantalla;
  3. parchear el JS del cliente para que reconozca el aviso: toca código del fabricante que hoy no tiene parches.
- **Decisión:** después del laboratorio del 34 (Sergio, 16/11/2026).
- Confirmado en L1 y resuelto con D25: ver «Forma del aviso: línea llana (16/11/2026, D20 a D28)», abajo.

## Forma del aviso: línea llana (16/11/2026, D20 a D28)

### Laboratorio L1

- **Dónde:** [lab_procedimiento_3973.md](lab_procedimiento_3973.md), «Ampliación (16/11/2026): pintado del aviso» y filas
  del 16/11/2026 de las 16:13 y las 16:58 UTC del «Registro de laboratorios». Sin modelo, con el `formatContent` real
  del cliente.
- **Con F1 (16:13):** el aviso sale en cursiva en a y b, con `<p><em>` literales en a′ y con `_…_` literales en b′, c y
  d; 12/12 igual que lo previsto, código 0. Confirma la lectura de código de «Pintado del aviso en el cliente» y
  resuelve d (literal).
- **Con la línea llana (16:58):** 12/12 «línea llana», código 0.

### Decisiones de Sergio (16/11/2026, D20 a D28)

- **D20:** dos laboratorios: L1 sin modelo y L2 con turnos reales.
- **D21:** Chrome visible en L2.
- **D22:** «Design» lo cambia Sergio en la interfaz.
- **D23:** contacto hostil para 6c.
- **D24:** lienzo plantado para 6d′, que se borra al acabar.
- **D25:** el aviso pasa a ser una línea llana sin marcas en todos los casos: `acc`, dos saltos de línea y el aviso; con
  `acc` vacío, solo el aviso. Reabre D15 y F1.
- **D26:** se quita `import html` y su marcador.
- **D27:** cambian los esperados de `test_notice_after_refusal`, `test_notice_unknown_session`,
  `test_notice_empty_answer` y `test_notice_html_answer`.
- **D28:** neutralizaciones N34p (nueva), N34s y N34o. Desaparece N34h (ya no hay rama F1). No se repiten N34m, N34r,
  N34j ni N34x: `chatboo_canvas.py` y `page_refused_in_job` no cambian.

### Implementación

- **Código** (`pns_ai_chatboo/models/chatboo_async_request.py`):
  - rama de éxito de `_save_to_session` (`:1359-1371`): desde el comentario de F1 hasta `_content = f"_{_note}_"`, se
    sustituye por un comentario nuevo y `f"{acc}\n\n{_note}"` si `acc` tiene texto, o `_note` si no;
  - se quitan `import html` y su marcador (`:12-13` antes del cambio);
  - no cambian el marcador del bloque, `_content = acc or ''`, el msgid de `_note`, `_assistant_content = _content` ni la
    opción A (`content` y `original_content` con el mismo texto);
  - las citas de este archivo bajan 2 líneas: los marcadores quedan en `:19`, `:165`, `:537`, `:1359`, `:1429` y
    `:1430`, y el `return` temprano de D16 en `:344`.
- **Tests** (`pns_ai_chatboo/tests/test_seges_chatboo_canvas.py`, `TestSegesNoPageNotice`):
  - `test_notice_after_refusal` y `test_notice_unknown_session`: `NO_PAGE_ACC + '\n\n' + NO_PAGE_NOTICE`;
  - `test_notice_empty_answer`: `NO_PAGE_NOTICE`;
  - `test_notice_html_answer` (mismo `acc`): `acc + '\n\n' + NO_PAGE_NOTICE`, con `assertNotIn('<em>', …)` y
    `assertFalse(….endswith('_'))` en lugar de `assertNotIn('\n\n_', …)`, y el comentario de D25;
  - los otros 5 tests y el `import html` del test (lo usa `:797`) no cambian.
- **Comprobaciones:** 11 marcadores fuera de `tests/` (5 en `chatboo_canvas.py` y 6 en `chatboo_async_request.py`);
  «3.7.3 COMPILA 1» en cada archivo (forma fija del registro, «Parche 29 en 3.1.973»); lint `--revisar --base 7768d74`:
  0 incidencias nuevas.
- **SHA-256:**

  | Archivo | Antes | Después |
  |---|---|---|
  | `chatboo_async_request.py` | `f992a1bd…92e3d7` | `54b8a5c2f636455c070824db8f1d72341309cd46cc5cb289d8e7c3ff80a60ca4` |
  | `test_seges_chatboo_canvas.py` | `4f65f424…c63c564a` | `072c4d3470989dc7251593730b500add7254e9be4f4ccaa57b53fc9ec5b307c5` |
  | `chatboo_canvas.py` | `78ee3ea4…742198a61` | sin cambios |

### Batería

`tests-20261116-172418.log`: 566 tests, 1 F (`test_paap_i7`), 0 E y los mismos 6 saltados; Traceback 58, «bad query» 1
(`UPDATE "ai_safe_operation"`), «seges_side_env: » 1 y secretos 0, iguales que en la línea base
(`tests-20261116-160401.log`); los 9 de `TestSegesNoPageNotice` en verde; módulos desde `/mnt/compartidos/third_party`.

### Neutralizaciones

Una cada vez, con la batería completa y SHA-256 igual al del paso 3 al restaurar (`54b8a5c2…`).

| Id | Cambio | Log | Resultado | Traceback |
|---|---|---|---|---|
| N34p (nueva) | el aviso vuelve a markdown: `f"{acc}\n\n_{_note}_"` y `f"_{_note}_"` | `tests-20261116-172840.log` | 5 F: `test_paap_i7` y los 4 con aviso | 62 |
| N34s | `if False and page_refused_in_job(…)` | `tests-20261116-173222.log` | 5 F: los mismos | 62 |
| N34o | `'original_content'` vuelve a `acc or ''` | `tests-20261116-173603.log` | 5 F: los mismos | 62 |

Los 4 con aviso son `test_notice_after_refusal`, `test_notice_unknown_session`, `test_notice_empty_answer` y
`test_notice_html_answer`. En las tres: 0 E, los 6 saltados, «bad query» 1, «seges_side_env: » 1 y secretos 0; Traceback
62, uno por test que cae.

### Revisión (`odoo-reviewer`, 16/11/2026)

APROBADO CON OBSERVACIONES: 0 críticos, 2 avisos y 3 sugerencias.

- **Sin hallazgos en:**
  - inyección: el aviso sale de un msgid fijo, su traducción (`pns_ai_chatboo/i18n/es.po`) no lleva marcas y nada del
    usuario ni del modelo entra en él;
  - `html` no se usa en ningún otro punto del archivo;
  - opción A, invariante 2 y apertura y `reset` de la marca en `_process`;
  - otros lectores del contenido guardado (exportaciones PDF, DOCX y XLSX, copiar, `history_compact`,
    `get_model_history`, componente del chat): ninguno busca `_`, `<em>` ni el párrafo;
  - cobertura de los tests, neutralizaciones y Python 3.7.3.
- **Avisos (documentación):** la viñeta «Marcadores» del registro («Parche 34 en 3.1.973») y los textos de F1 en el
  registro y en esta propuesta. Resueltos con la viñeta corregida y con los bloques fechados del 16/11/2026, sin
  reescribir los anteriores.
- **Sugerencias:**
  - el comentario del código está en inglés y cita «laboratorio del 34»: se deja (texto decidido);
  - `assertFalse(….endswith('_'))` es redundante con la comparación exacta: se deja (documenta la intención);
  - repetir los casos en el laboratorio: previsto en L2.

### Riesgo aceptado y laboratorio

- **Riesgo aceptado:** tras una respuesta que se pinta como HTML (casos a y d), el aviso queda pegado al último texto,
  sin línea propia.
- **Laboratorio:** L1 hecho (16/11/2026). L2 pendiente: P-13 con proveedor real, 6c y 6d′ de
  [lab_p29_3879.md](lab_p29_3879.md); la apertura de la marca y el `reset` en `_process` (S1, sin test) se ven en P-13.
