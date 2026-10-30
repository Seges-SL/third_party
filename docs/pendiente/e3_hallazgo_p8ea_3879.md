# Hallazgo de P-8e a (E3′, parche 27 a): `const DATA` del modelo sin escapar

- **Rama:** `14.0-pns-ai-3879`, HEAD `58885ce` cuando se analizó.
- **Fecha:** 30/10/2026.
- **Origen:** prueba P-8e a del laboratorio ([lab_e3_3879.md](lab_e3_3879.md), apartado 7), sobre el
  parche 27 a (F1) del [registro de parches](parches_pns_ai.md).
- **Estado:** parche 29 **aprobado** el 30/10/2026 (tres revisiones de `odoo-reviewer`; ajustes en el
  apartado 7). Registro, tests y neutralización: [parches_pns_ai.md](parches_pns_ai.md), «Parche 29».
  Pendiente del commit y del laboratorio ([lab_p29_3879.md](lab_p29_3879.md)); después, reanudar P-8e a.

## 1. Qué falló y cómo reproducirlo

**Esperado (lab_e3_3879.md, 7):** ninguna alerta «P-8e»; los nombres maliciosos se ven como texto, y en
`canvas_design` aparecen escapados (`</script>…`).

**Obtenido:** en `canvas_design`, `const DATA` lleva los dos nombres **sin escapar**, y lo servido
también (`/chatboo/canvas/11/download`). Copias: `~/lab_e3p/p8ea_sesion11.html` (BD) y
`~/lab_e3p/p8ea_servida.html` (servida). La alerta no salió, pero por casualidad (apartado 3.1).

Datos del laboratorio (BD `lab_pns_ai_3879_14`):

- Contactos **71** «`Seges E3 </script><script>alert("P-8e")</script>`» y **72**
  «`Seges E3 <!--<script>`». Las filas reales del filtro son 72, 71, 70 y 68.
- Sesión `chatboo_session` **11** (admin), `canvas_rev` 6.
- `ai_log` del turno (`turn` = `D8JH`):

| id | Qué |
|---|---|
| 492 | `tool_calls: relaxaicode` (el código llama a `page_url`) |
| 494 | Design, dentro de `page_url`: HTTP 429 (cuota) |
| 495 | «No page was built: HTTP 429…» (`log_no_page`) |
| 496 | relaxaicode: «Execution successful. Result: {'data': [...]}» |
| 497 | Design, desde la página que había quedado pendiente: «laid out the page in 28 s (12071 chars)» |
| 498 | Failover del orquestador (Gemini 3.6 flash → 3.5 flash) |
| 499 | Repetición de Design (el diseño «mezcla cifras»): HTTP 503 |

Reproducción:

1. Crear los contactos 71 y 72 como en lab_e3_3879.md, apartado 3.
2. Como `admin`, en Chatboo: «Haz una página con los contactos cuyo nombre empieza por "Seges E3", con su
   nombre y su id».
3. Basta con que Design **copie en `const DATA` la muestra** que recibe en el prompt, con el contacto 71 dentro.
   La cuota agotada del 429 no hace falta: solo explica por qué esta vez la página salió del camino de la
   página pendiente.
4. Comprobar con la consulta de lab_e3_3879.md, apartado 7 (`cierra_script = t`).

Pruebas de que el DATA guardado es **texto del modelo**, no del servidor:

- lleva `"keys": ["id", "nombre"]`, que es el formato de la muestra (`sample_figures_for_design`), no el
  de la sustitución (`_flat_rows` o `figures_for_design`);
- trae una fila inventada, `{"id": 69, "nombre": "Seges E3 Contacto 4"}`: el contacto 69 no existe. La
  muestra lleva 3 filas, y la nota dice «Show all 4 rows»;
- la tabla de rescate (`#pns-page-rows`, escapada y visible, con `pns-page-rows-visible` y sin
  `pns-page-rows-watch`) sí lleva las filas reales: 72, 71, 70 y 68.

## 2. Análisis

### 2.1 Camino, desde el resultado de relaxaicode hasta la escritura de `canvas_design`

1. `sandbox_helpers` → `_claim_page_turn` anota una página pendiente,
   `note_page_waiting(self.env, fulfill)` (`chatboo_session.py:824`, `846`, `860-866`).
2. El código llama a `page_url` → `open_page` → `_paint_canvas` → 429 → `log_no_page` devuelve `''`.
   `waiting` sigue activo.
3. Se ejecuta relaxaicode (`pns_ai_mcp/utils/engine_tool_run.py:184`). Luego
   `turn._payload = unwrap_tool_payload(result)` (196) y `_tool_loop_fulfill_page` (199, 383-393).
4. `fulfill_waiting_page` (`pns_ai_mcp/utils/result_page.py:167`): `blocks_on_payload` (53, 77-80)
   arma un bloque titulado con la `summary` («Se encontraron 4 contactos.»); después, `fn(env, blocks)` (186).
5. `fulfill` → `open_page(..., new=True)` (`chatboo_canvas.py:938`):
   - `sample_figures_for_design` (`905`, `972`) hace `json.dumps` **sin escapar**, así que los nombres
     hostiles van tal cual al prompt de Design;
   - después llama a `session._paint_canvas` (980).
6. `_paint_canvas` (`chatboo_session.py:1055`):
   - `_ask_design(DESIGN_SYSTEM, …)` (1120) es la línea 497 del log;
   - `design_figures_centralized` (1135) da False, porque DATA no se puede leer (2.2);
   - se repite la petición (1154), que es la 499, la del 503;
   - y se **queda el primer documento** («kept the layout», 1161-1166).
7. `place_rows_on_page(..., captured=True)` (`chatboo_session.py:1170` → `chatboo_canvas.py:2129`):
   - `bind_const_title` (2149) sustituye TITLE;
   - `bind_script_row_json` (2150) → `bind_const_data` (1775) **no sustituye nada**;
   - `clear_script_row_json` (2152) tampoco;
   - `_fill_page_rows_slot` + `_finish_rescue` (2166) dejan la tabla escapada visible.
8. `_store_design` (`chatboo_session.py:1185`) → `session.write(values)` (1009) guarda la revisión 6.

### 2.2 Causa

`_SCRIPT_INNER_RE` (`chatboo_canvas.py:1416`) es `(<script\b[^>]*>)(.*?)(</script>)`, no codicioso. El DATA
del modelo lleva `</script>` dentro de una cadena JSON (el contacto 71), y el regex da el script por
terminado ahí. `raw_decode` falla («Unterminated string») y el bucle hace `continue` (1552):
`replaced = 0`.

Reproducido en memoria sobre la copia guardada:

```
script 7340 len 273 tiene DATA: True | final: '…{"id": 71, "nombre": "Seges E3 '
  raw_decode FALLA: Unterminated string starting at: line 3 column 214
```

`_object_arrays_in` tampoco encuentra ningún array completo, así que `clear_script_row_json` no vacía
nada. `_const_data_value` (1570) falla igual: `_design_label_leaks` devuelve None, el diseño no pasa la
comprobación de centralización y se repite la petición. Si el servidor hubiera sustituido, habría entrado
la rama de bloques de `_payload_for_const_data` (1481-1491), que escapa con `_script_safe` y no lleva
`"keys"`.

**Origen:** las reglas permiten a Design «keep that sample» (`chatboo_canvas.py:52`, `911`), y la muestra
va con los valores reales sin escapar (905). El modelo la copia, y justo el valor que rompe el `<script>`
es el que impide que el servidor la sustituya.

### 2.3 Casos en que `const DATA` escrito por el modelo queda sin sustituir

| # | Caso | Dónde |
|---|---|---|
| a | DATA contiene `</script` (este caso): el regex corta el script | `chatboo_canvas.py:1416`, `1552` |
| b | DATA no es JSON estricto: claves sin comillas, comillas simples, comas finales, comentarios, `Object.freeze([...])`, `JSON.parse('…')`, spread… | `1552` (`continue`) |
| c | No coincide con `\bconst\s+DATA\s*=`: `let`/`var DATA`, `window.DATA =`, desestructuración | `1467` |
| d | Las filas no son diccionarios o solo tienen claves `_…`: `_row_payloads` vacío y salida temprana | `1538-1539` |
| e | Los datos no están en un `<script>`: en un atributo `data-*`, en un `<template>`, en un manejador `on…` | todo el binding mira solo `<script>` |
| f | DATA sí se sustituye, pero el modelo dejó otra copia (`const SAMPLE = […]`, cadenas sueltas): con `replaced > 0` se sale sin tocar el resto | `1776` |
| g | **Edición sin filas**: `edit_page` → `_paint_canvas(instruction, new_page=False)` sin `rows` → `place_rows_on_page` sale en `if not blocks: return design`. El documento reescrito se guarda tal cual, y el modelo puede «desescapar» los `<` de la página actual | `1005`, `2142-2143` |
| h | Arrastre: una skill capturada con un `canvas_design` así lo lleva como plantilla (`wrap_captured_page` → `page_html` → el mismo fallo a) en cada ejecución | `2094-2114`, `chatboo_session.py:927` |

### 2.4 Otros `json.dumps` revisados

- `chatboo_canvas.py:429-430` (`data-people`, `data-text`): pasan por `html.escape(quote=True)`. Correcto.
- `chatboo_canvas.py:871` (`figures_for_design`): su único uso es 1490, con `_script_safe`. Correcto.
  Su pareja, 905, no escapa (es el origen descrito en 2.2).
- `chatboo_canvas.py:2113-2114`: generan código Python; un literal de `json.dumps` con cadenas es una
  cadena Python válida. No hay inyección, pero se propaga el diseño (caso h).
- `controllers/chatboo.py:1122` (`application/json`) y `1130` (SSE: `json.dumps` escapa los saltos de
  línea): no son HTML. Correcto. No se ha revisado cómo pinta los SSE el cliente.
- `chatboo_session.py:1140-1160`: las etiquetas reales (`leaks`) van al prompt de la repetición y al
  `_logger.info`. No es HTML: es un vector menor (instrucciones al modelo, ruido en el log). Lo relevante es
  **1161-1166**: si la repetición falla, se guarda el primer documento; no se cierra ante el fallo.

### 2.5 Por qué no lo detectaron los tests

`TestSegesCanvasScriptJson` (`tests/test_seges_chatboo_canvas.py:235-287`) parte siempre de una plantilla
con un DATA inocente (`[{"name": "a", "amount": 0}]`), y el simulador de Design devuelve siempre `DESIGN`
(42-48), también inocente. Los tests prueban que **lo que escribe el servidor** sale escapado cuando
consigue sustituir. No hay ningún caso:

- en que Design devuelva la muestra copiada con `EVIL` dentro de `const DATA`;
- con `replaced == 0`, ni de guardar el diseño tras una repetición fallida;
- de edición sin filas;
- sobre la muestra enviada a Design (905).

### 2.6 Resumen

| Punto | Archivo:línea | ¿Escapa? | Gravedad |
|---|---|---|---|
| DATA del modelo no sustituido (`</script` corta el regex) | `chatboo_canvas.py:1416`, `1552` | **No** | **Alta** (un dato externo navega o reescribe el marco, 3.2) |
| Muestra a Design con valores en crudo (origen) | `chatboo_canvas.py:905`, `52`, `911` | **No** (va al prompt) | Alta (es la causa) |
| Se guarda el diseño tras una repetición fallida | `chatboo_session.py:1161-1166` | **No** (no se cierra ante el fallo) | Alta |
| Edición sin filas: no se vuelven a meter las filas | `chatboo_canvas.py:1005`, `2142-2143` | **No** | Media-alta |
| Sustitución parcial (`replaced > 0` deja otras copias) | `chatboo_canvas.py:1776` | **No** | Media |
| Skill capturada propaga el diseño contaminado | `chatboo_canvas.py:2094-2114` | Python: sí; HTML: **no** | Media |
| Etiquetas reales en el prompt de repetición y en el log | `chatboo_session.py:1140-1152` | No aplica (no es HTML) | Baja |
| `data-people` / `data-text` | `chatboo_canvas.py:429-430` | Sí | — |
| `figures_for_design` | `chatboo_canvas.py:871` → `1490` | Sí | — |
| `_json_response` | `controllers/chatboo.py:1122` | No aplica (JSON) | — |
| `_sse_event` | `controllers/chatboo.py:1130` | No aplica (SSE) | — |
| Tests sin la ruta del modelo hostil | `tests/test_seges_chatboo_canvas.py:42-48`, `235-287` | — | Hueco de cobertura |

## 3. Correcciones al primer análisis (30/10/2026)

### 3.1 Por qué no salió la alerta

En DATA, el contacto **72** (`<!--<script>`) va **delante** del 71. En el contenido de un `<script>`, la
secuencia `<!--` seguida de `<script>` lleva al analizador HTML al estado de **escape doble**. En ese
estado, el `</script>` del contacto 71 no cierra el bloque, sino que solo sale del escape doble. Por eso
el `<script>alert("P-8e")</script>` siguiente no llega a ser un script propio, y la alerta no salta. **Con
el contacto 71 solo, sí saltaría.**

Que no saliera la alerta no es, por tanto, una señal de que el parche funcione. P-8e a debe juzgarse por el
`canvas_design` (la consulta de lab_e3_3879.md, apartado 7), no por la alerta. Además, el regex del
servidor (2.2) y el navegador no ven el mismo final del script.

Para confirmar cómo lo interpreta un navegador, sin analizar el HTML hostil con expresiones regulares:

- `html5lib` en un venv fuera de la imagen: parsear `p8ea_sesion11.html` y listar los `<script>` con su
  texto, primero con 71 y 72 juntos y después con 71 solo;
- o `chromium --headless --dump-dom` sobre la descarga.

### 3.2 Impacto: navegación del marco con disparador externo (gravedad alta)

El script inyectado se ejecuta en el iframe `sandbox="allow-scripts allow-modals"`, con origen opaco y la
CSP del parche 27 b (`connect-src 'none'`, `form-action 'none'`…). No llega a la sesión de Odoo ni puede
hacer peticiones, pero sí puede reescribir la página y **navegar el marco a una página externa**
(`location = …`, `<meta http-equiv="refresh">`). La CSP no lo limita y el documento nuevo ya no lleva la
`<meta>`.

Ese era un riesgo aceptado del parche 27 (e, «autonavegación del marco»), con el modelo de Design como
único disparador. Con este fallo **pasa a tener un disparador externo: quien pueda poner nombre a un
registro** que acabe en una página (contactos, productos…) puede navegar el marco de otro usuario, dentro
de la carcasa de Odoo. Alcanza a las páginas compartidas y a la descarga (`downloadable_page`).
**Gravedad: alta.**

## 4. Opciones de corrección

| Opción | Qué hace | Impacto |
|---|---|---|
| **A. Cerrar ante el fallo** | En `place_rows_on_page` con `captured=True`: si hay bloques, el diseño menciona `const DATA` y `bound == 0`, se descarta el documento del modelo y se usa `_page_for_rows(blocks)` (rescate, ya escapado y probado). Lo mismo en `chatboo_session.py:1161-1166` cuando la repetición falla y DATA no se puede leer | Cierra a, b y c. Se pierde el diseño en esos casos, que ya eran páginas defectuosas. Cambio pequeño |
| **B. Comprobar los valores hostiles conocidos** | Antes de guardar, para cada celda de texto con `<`, `>` o `&` y para el título: si aparece **literal** en el documento, se rechaza y se va al rescate | Defensa en profundidad para a, e, f y g. Solo detecta lo inseguro conocido; no prueba que el resto sea seguro. Coste lineal |
| **C. No dar valores reales que copiar** | **C1:** pasar la muestra de `sample_figures_for_design` (905) por `_script_safe`: si el modelo la copia tal cual, ya va escapada. **C2:** valores ficticios del mismo tipo y la instrucción «write `const DATA = [];`» | C1: mínimo y sin cambio de comportamiento para Design, pero el modelo puede desescapar (por eso va con A y B). C2: ataca el origen y mejora la privacidad, pero Design pierde formatos y longitudes reales, y hay que retocar `chatboo_canvas.py:52` y `911` sin romper `test_design_rule` |
| **D. Edición sin filas** | Volver a meter las filas de la página abierta (las del DATA guardado por el servidor) tras `_paint_canvas` en `chatboo_canvas.py:1005`, o como mínimo aplicar B con esos valores | Cierra g |
| E. Repetición fallida | Incluido en A: rescate en lugar de «kept the layout» cuando DATA no se puede leer | Complementa a A |
| F. Tokenizador HTML en lugar del regex | Localizar los scripts con un tokenizador | **No sirve:** si el texto ya rompió el `<script>`, el navegador también lo ve roto, y no recupera nada. Además, añadiría una dependencia |

**Qué hacer cuando el diseño trae su propio DATA:** el servidor sobrescribe siempre. Si no puede (no es
JSON, está truncado o la clave no coincide), ese diseño no es válido: va al rescate (A). El caso h queda
cubierto por A y B, porque `page_html` usa el mismo `place_rows_on_page`.

## 5. Decisiones de Sergio (30/10/2026)

1. **Parche 29 = A + B + C + D**, con C en la **variante C1**: la muestra de `sample_figures_for_design`
   pasa por `_script_safe`. Se registra en [parches_pns_ai.md](parches_pns_ai.md) con el marcador
   `# Seges: parche 29 (…)`. Debe cumplir las condiciones del repo: cambio mínimo, Python 3.7.3, sin
   dependencias nuevas y sin tocar `version`, `depends`, `external_dependencies` ni `i18n`.
2. **Riesgo residual de `innerHTML` en el código del diseño: aceptado y documentado.**
   - Aunque `const DATA` quede bien escapado, `_script_json` solo protege al analizador HTML: el `<script>`
     no se cierra. No protege lo que el JavaScript del diseño hace después con los valores.
   - Si el diseño pinta una fila con `innerHTML`, `insertAdjacentHTML`, `outerHTML` o `document.write`, un
     nombre como `<img src=x onerror=…>` se ejecuta en el marco, con el mismo impacto que 3.2.
   - El servidor no puede garantizarlo: leer el JavaScript del diseño para concluirlo no es fiable. La
     contención son el sandbox y la CSP actuales.
   - En el diseño de la sesión 11, los tres `innerHTML` solo vacían contenedores (`innerHTML = ''`) y las
     celdas usan `textContent`, pero depende de cada respuesta del modelo.
   - Se reduce con una **regla nueva en `_PAGE_RULES`**: insertar los datos con `textContent`, nunca con
     `innerHTML`. Hoy no la piden ni `_PAGE_RULES`, ni `DESIGN_SYSTEM`, ni `EDIT_SYSTEM`; el código propio
     de la carcasa sí usa `textContent` (`chatboo_canvas.py:340-370`).
3. **Tests previstos:**
   - un simulador de Design que devuelve la muestra copiada con `EVIL` y `EVIL_COMMENT` dentro de
     `const DATA`, **en los dos órdenes**;
   - DATA que no es JSON (caso b);
   - edición sin filas (caso g);
   - el prompt de Design no lleva `</script` en crudo (C1).

## 6. Estado (30/10/2026)

- **Parche 29:** pendiente de implementar.
- **Laboratorio de E3′** ([lab_e3_3879.md](lab_e3_3879.md)): en pausa en **P-8e a**.
  - Las pruebas http y 8b se ejecutaron aparte.
  - Queda pendiente la limpieza.
  - Al reanudar tras el parche 29, P-8e a se juzga por la consulta del `canvas_design`, no por la alerta
    (3.1).
- **Pruebas previstas del laboratorio del parche 29** (decisión de Sergio del 30/10/2026):
  - **a) Variante con el contacto 71 solo**, sin el 72 delante (3.1):
    - antes del parche, para comprobar que la alerta «P-8e» salta;
    - después del parche, para comprobar que no salta y que la consulta de lab_e3_3879.md, apartado 7, da
      `cierra_script = f`.
  - **b) Usuario portal (disparador externo, 3.2):**
    - comprobar si el usuario portal puede poner un nombre hostil a su propio contacto desde «Mi cuenta»;
    - si puede, comprobar si ese nombre llega a una página del lienzo de `admin`.

## 7. Ajustes al plan del parche 29 e implementación (30/10/2026)

Plan de la fase 1 aprobado por Sergio el 30/10/2026, con estos ajustes:

1. **A cubre también `let DATA`, `var DATA` y `window.DATA`.** Si hay bloques y el diseño asigna DATA de
   cualquiera de esas formas sin que el servidor la haya sustituido, se usa la página de rescate. Queda
   fuera una asignación que solo pasa un nombre (`window.DATA = DATA;`): no lleva cifras.
2. **B cambia de alcance.** Salta con los valores que, tras `strip`, tienen 3 caracteres o más y contienen
   `<`, `>` o `"`; no salta con `&` solo ni con `'`.
   - `&` solo no es un vector y daría rescates por casualidad (`R&D`, `AT&T`).
   - `"` sí lo es (inyección de un atributo con un manejador en línea).
   - `'` queda como riesgo residual documentado, junto al de `innerHTML`.
   - **Ampliación (30/10/2026, tras la neutralización N29a):** para los valores con `<` o `>`, B busca
     también su forma de cadena JSON (`json.dumps(v)[1:-1]`, con `ensure_ascii=False` y `True`). Así detecta
     un valor copiado en una cadena JS fuera de DATA (`const SAMPLE = […]`), donde `"` aparece como `\"`.
   - **Corrección a la premisa:** el servidor no escribía `"` siempre escapada. En DATA va como `\"`, pero
     las celdas de la tabla de rescate usaban `html.escape(..., quote=False)` (`_cell_html` y
     `_rows_as_table`). Para que B no salte con su propia tabla, esas dos llamadas pasan a `quote=True`, y
     `_page_shows_rows` acepta también esa forma. El texto se ve igual.
3. **`Page title:` y `Company:` siguen en crudo en el prompt de Design.** C1 solo escapa la muestra; B
   frena la copia en crudo del título.
4. **Fragmento de solo lectura** para medir las páginas ya guardadas con DATA ilegible (laboratorio,
   staging y LIYBEN): en [parches_pns_ai.md](parches_pns_ai.md), «Parche 29».

**Implementación (30/10/2026):** A y B están en una envoltura de `place_rows_on_page`, por la que pasan
`_paint_canvas` y `page_html`. Por eso la repetición fallida de `chatboo_session.py:1161-1166` y la skill
capturada (caso h) quedan cubiertas sin tocar esos puntos. C1 está en `sample_figures_for_design`. D: la
edición sin filas vuelve a meter las de la página abierta. La regla de `textContent` está en
`_PAGE_RULES`. Detalle, tests, neutralización y riesgos residuales: [parches_pns_ai.md](parches_pns_ai.md),
«Parche 29».

| Caso de 2.3 | Tras el parche 29 |
|---|---|
| a (`</script` en DATA) | Rescate (A, y B si el valor es de las filas) |
| b (DATA que no es JSON) | Rescate (A) |
| c (`let`/`var`/`window.DATA`) | Rescate si el servidor no la sustituyó (A) |
| d (filas que no son diccionarios) | Rescate si el diseño trae su DATA (A: el servidor no la puede sustituir) |
| e (datos fuera de `<script>`) | Rescate si un valor de las filas o el título está en crudo (B) |
| f (otra copia, además de DATA) | Rescate si es otra asignación de DATA (A) o si lleva un valor de las filas en crudo o como cadena JSON (B) |
| g (edición sin filas) | Con DATA legible de filas en la página abierta: se vuelven a meter (D), y después A y B. Sin él, pero con la tabla del servidor: B con los valores de esa tabla; si alguno queda en crudo, la edición se rechaza y la página anterior se queda. Sin DATA ni tabla: la edición sin filas se rechaza (B1 de la revisión). Sin DATA, B compara también el texto visible de la página abierta con `<` o `>`, por si una edición anterior sacó un valor de la tabla (n1 de la segunda revisión) |
| h (skill capturada) | `page_html` pasa por A y B |

**Tras la revisión del parche 29 (30/10/2026):** `odoo-reviewer` lo rechazó por un bloqueante, **B1**. Una
página abierta sin `const DATA` legible de filas dejaba la edición sin filas sin protección. Esa página
puede salir con el parche puesto (diseño que no escribe DATA y se conserva tras la repetición, o filas que
no son diccionarios). Decisión de Sergio: la opción a con cierre (fila g de la tabla). Avisos y
observaciones (m1 a m8) y su tratamiento: [parches_pns_ai.md](parches_pns_ai.md), «Parche 29».

**Tras la segunda revisión del parche 29 (30/10/2026):** APROBADO CON OBSERVACIONES. Decisión de Sergio sobre
**n1** (una edición anterior puede sacar un valor de la tabla de la que depende B1): opción b, cierre
aplicado (fila g). **n2** (`html.parser` en Python 3.7.3 frente a 3.12) queda como observación sin
consecuencias. Detalle: [parches_pns_ai.md](parches_pns_ai.md), «Parche 29».
