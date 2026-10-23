# PNS-70 en 3.1.879: diagnóstico (E0′, parte B)

- **Fecha:** 23/10/2026. **Rama:** `14.0-pns-ai-3879` (3.1.879); la 3.1.782 se lee con
  `git show 14.0-pns-ai-correcciones:<ruta>`.
- **Alcance:** solo lectura. Código, core de Odoo 14 de referencia (`/opt/odoo-src/14.0`), bundles
  servidos por el laboratorio (`SELECT` en `ir_attachment` y `grep` en el filestore del contenedor
  `odoo-dev-14-web-1`). No se ha arrancado ningún contexto ni cambiado código, BD o contenedores.
- **Origen:** [plan](plan_correccion_pns_ai_3879.md), E0′ y ficha de PNS-70 (E2′);
  [comparación](../specs/comparacion_pns_ai_3-1-879.md) §5.6 «PNS-70»;
  [hoja de N12](n12_decision_3879.md) §5; [fase 3](fase3_lab_pns_ai_3879.md), parte 2, «P-70 (paso 3)».
- **Comprobación manual en el navegador (Sergio, 23/10/2026):** en `lab_pns_ai_3879` (3.1.879), con
  recarga sin caché (§4, «Comprobado en ejecución»). No se ha repetido en 3.1.782.
- **Cómo se identifica cada versión en la consola:** la 2.x de Odoo no expone `Chart.version`; se
  reconoce por `Chart.helpers`. La 4.4.8 tiene `Chart.version`.
- **Decisión (Sergio, 23/10/2026):** opción A para E2′, con dos condiciones (§4, «Decisión»).

## 1. Cómo se carga Chart.js en cada versión

`pns_ai_chatboo/static/src/js/chart.umd.min.js` es el mismo archivo en las dos versiones: Chart.js
4.4.8, UMD. Sin cargador AMD ni CommonJS, el UMD hace `globalThis.Chart = …`: la asignación es única en
el archivo.

| | 3.1.782 (`14.0-pns-ai-correcciones`) | 3.1.879 (esta rama) |
|---|---|---|
| Dónde | Dentro de `web.assets_backend` (`pns_ai_chatboo/views/assets.xml:22`), junto con jsPDF, autotable, html2canvas, ECharts y showdown (`:17-23`) | Fuera del bundle. `chatboo_heavy_libs.js:12-33` lo carga con `ajax.loadJS` al abrir el chat (`chatboo_systray.js:383`, `_showOverlay`), en `VENDOR` aunque el motor sea ECharts |
| Cuándo | Al cargar la página (F5), una vez | La primera vez que se abre el chat en esa página |
| Orden frente a los estáticos de `web` | El bundle de `web` no trae Chart.js. Chart 4 ocupa `window.Chart` antes de que Odoo cargue su 2.x | Depende de lo que haga el usuario. Si antes se ha abierto una vista gráfico, Chart 4 llega **después** de la 2.x de Odoo |
| Cómo lo usa el chat | `global.Chart` al pintar (`chatboo_charts.js:1625-1629, 1983` de 3.1.782) | Su copia, `ChartLib`, recibida en `bindEngines(window.Chart, window.echarts)` tras cargar (`chatboo_heavy_libs.js:28-33`; `chatboo_charts.js:36-47, 1636-1640, 2006`) |
| Otros JS de `pns_*` | Ninguno (`git grep` en `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo`) | Ninguno además de `chatboo_heavy_libs.js` y `chatboo_charts.js` |

## 2. El core de Odoo 14

- **Carga:** Odoo trae Chart.js **2.9.3** (`web/static/lib/Chart/Chart.js` en el contenedor). Esa 2.x
  no expone `Chart.version`; se identifica por `Chart.helpers`. La carga de forma diferida con `jsLibs` →
  `ajax.loadLibs` → `ajax.loadJS`:
  - vista gráfico, `addons/web/static/src/js/views/graph/graph_view.js:25-27`;
  - tablero de diarios de Facturación (`JournalDashboardGraph`),
    `addons/web/static/src/js/fields/basic_fields.js:3065-3068`.
  - La única inclusión directa (`web/views/webclient_templates.xml:637`) es de `web.tests_assets`, no
    del backend.
- **`loadJS` no comprueba `window.Chart`, solo la URL** (`addons/web/static/src/js/core/ajax.js:182-213`):
  - si ya la pidió antes, devuelve la misma promesa resuelta y no vuelve a ejecutar el script;
  - si hay en el DOM un `<script src>` con esa URL, la da por cargada.
- **Uso:** el renderer y el widget del tablero usan la global en el momento de pintar:
  `new Chart(ctx, …)` en `graph_renderer.js:841, 896, 961` y `basic_fields.js:3130`.
  - Usan opciones de la API 2: `scales: {xAxes: [...], yAxes: [...]}` (`graph_renderer.js:466, 482`;
    `basic_fields.js:3154-3155, 3196`).
  - No tocan `Chart.defaults` ni plugins.
- **Por qué salen los errores:** desde Chart.js 3, `scales` es un objeto indexado por id de eje. Con
  `xAxes`/`yAxes` como arrays, Chart 4 escribe `Invalid scale configuration for scale: xAxes` (y `yAxes`)
  en la consola, descarta esas escalas y pinta con las de por defecto. Es lo que se vio en P-70: «se
  dibuja, con errores» en la vista gráfico, y los gráficos de los diarios no cargan bien.

## 3. Estáticos servidos en el laboratorio

| BD (servidor del contexto `lab_pns_ai_3879`) | Adjunto `web.assets_backend.js` | Contenido |
|---|---|---|
| `lab_pns_ai_3879_14` (3.1.879) | `/web/content/405-e0dbf9c/web.assets_backend.js`, 23/10/2026 07:23 | Sin Chart 4 (0 apariciones de `Invalid scale configuration`); `chatboo_heavy_libs.js` dentro; Chart 2 no va en el bundle (solo la URL dentro de `graph_view` y `basic_fields`) |
| `lab_pns_ai_14` (3.1.782 instalada) | `/web/content/450-c5fc102/web.assets_backend.js`, 23/10/2026 16:21 | **Híbrido:** `chart.umd.min.js` dentro del bundle (la vista `assets.xml` guardada en la BD es la de 3.1.782), con `(this, …)` a nivel global; pero el contenido de los JS es el de la copia de trabajo actual (3.1.879): aparece `require('pns_ai_chatboo.heavy_libs')` |

- En ningún bundle (`web.assets_common*` y `web.assets_backend*`) hay un `define` AMD global ni
  `module`/`exports` globales: `define.amd` solo aparece en las comprobaciones de las propias librerías
  UMD. Por tanto, Chart 2 y Chart 4 escriben los dos en `window.Chart`, y **gana el último que se
  ejecuta**.
- **Cuidado:** `lab_pns_ai_14` abierta con el contexto actual mezcla el XML de 3.1.782 con el JS de
  3.1.879. **No sirve como laboratorio de 3.1.782** hasta que se arranque su contexto (`lab_pns_ai`).
  Una comprobación manual hecha así no vale para comparar.

## 4. Conclusión

### Comprobado en el código y en los estáticos

1. En 3.1.879, Chart 4 entra en `window.Chart` al abrir el chat (`ajax.loadJS`), sin restaurar lo que
   hubiera antes.
2. Odoo carga su Chart 2 una sola vez por página y por URL, y pinta con lo que haya en `window.Chart` en
   ese momento.
3. Con la secuencia **vista gráfico (o tablero) → abrir el chat → volver**, Odoo pinta con Chart 4 y
   opciones de Chart 2: de ahí los errores `xAxes`/`yAxes`.
4. Si el chat se abre **antes** que cualquier vista gráfico, Odoo carga después su 2.x, que gana en
   `window.Chart`, y sus gráficos salen bien. El chat no se ve afectado: ya tiene su copia en `ChartLib`.
   Esta secuencia no se ha probado en el navegador.

### Comprobado en ejecución (Sergio, 23/10/2026)

En `lab_pns_ai_3879` (3.1.879), con recarga sin caché:

| Paso | `window.Chart` | Consola |
|---|---|---|
| Gráfico de Odoo pintado, antes de abrir el chat | 2.x: sin `Chart.version`, con `Chart.helpers` | — |
| Abrir Chatboo, volver al gráfico y cambiar de tipo | `Chart.version` = `4.4.8` | «Invalid scale configuration for scale: xAxes» y «… yAxes», desde `chart.umd.min.js` |

**El mecanismo de 3.1.879 queda COMPROBADO:** Chart 4, cargado al abrir el chat, sustituye en
`window.Chart` a la 2.x que Odoo ya había cargado. Odoo no la recarga y pinta con la API 4 y opciones de
la 2.

### 3.1.782

- **Según el código:** Chart 4 está en `window.Chart` desde el F5 (dentro de `web.assets_backend`). La
  primera vista gráfico o el tablero cargan la 2.x con `loadJS`, que pasa a ser la última en ejecutarse:
  - Odoo pinta bien;
  - lo que se rompe tras abrir una vista gráfico son **los gráficos del chat**, que pintaban con
    `global.Chart` (`chatboo_charts.js:1625-1629, 1983` de 3.1.782), ya en la 2.x.
  - Es coherente con D43 ([decisiones](pns_ai_decisiones.md)): «tras abrir una de ellas, los gráficos
    del chat se pintan mal hasta recargar la página (las vistas de Odoo no se rompen)».
- **Staging `pns_demo` (23/10/2026, [comparación](../specs/comparacion_pns_ai_3-1-879.md) §5.6):
  resultado coincidente (gráficos de Odoo correctos), medida sin explicar; no bloquea.**
  - Después de abrir Ventas → Análisis y el tablero se midió `window.Chart` = 4.4.8. Según el código
    debería ser la 2.x.
  - No se investiga más: el parche garantiza que `window.Chart` sea siempre la de Odoo, sea cual sea el
    orden.

### Opciones de parche (sin pisar `window.Chart`)

| Opción | Archivo | Qué cambia | Riesgo |
|---|---|---|---|
| **A. Chart 4 bajo un nombre propio** | `pns_ai_chatboo/static/src/js/chart.umd.min.js` (cabecera UMD, una sola aparición de `.Chart=e()`) y `chatboo_heavy_libs.js:28-33` | El UMD asigna `globalThis.PnsChatbooChart` en lugar de `globalThis.Chart`; `loadHeavyLibs` pasa `window.PnsChatbooChart` a `bindEngines`. `window.Chart` nunca se toca | Bajo y determinista, sin carreras. Es un cambio de un token en una librería minificada del fabricante: se registra con marcador en un comentario aparte en la cabecera, y una versión nueva del fabricante lo deshace (se vigila con `grep`). Ningún otro JS de `pns_*` usa `window.Chart` |
| B. Guardar y restaurar `window.Chart` | `chatboo_heavy_libs.js:24-33` | Antes de `loadJS(chart.umd)`, guardar `window.Chart`. Después, entregar la 4 a `bindEngines` y restaurar el valor anterior (o borrar la global si no había ninguna) | Medio. Hay una ventana entre la ejecución del script y el `.then` en la que `window.Chart` es la 4. Si Odoo carga su 2.x a la vez (vista gráfico abriéndose mientras se abre el chat), la restauración puede devolver un valor viejo y borrar la 2.x. Poco probable, no imposible. Sin tocar la librería |
| C. Cargar Chart 4 solo si el motor es Chart.js | `chatboo_heavy_libs.js:12-33` y el motor configurado (`chatboo_charts.js:5, 19`) | Sacar Chart 4 de `VENDOR` cuando el motor sea ECharts | No corrige nada si el motor es Chart.js (el predeterminado, `chatboo_charts.js:5`). Solo reduce la exposición; como complemento de A o B |

**Recomendación: opción A.** Es la única que elimina el choque en cualquier orden y sin carreras, con un
cambio mínimo y sin dependencias nuevas. La C puede sumarse más adelante (E4′) por rendimiento, no por
PNS-70.

### Decisión (Sergio, 23/10/2026)

**Opción A para E2′**, con dos condiciones:

1. **Antes de aplicarla,** comprobar que ningún otro JS de `pns_*` usa `window.Chart` (o la global
   `Chart`) esperando la versión 4. Si lo hay, pasa también a `PnsChatbooChart`.
   - En este diagnóstico no hay ninguno, aparte de `chatboo_heavy_libs.js`
     (§1, `grep` en `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo`).
   - Se repite al aplicar el parche, por si cambia algo.
2. **El cambio en la librería es exactamente un token** (`.Chart=e()` → `.PnsChatbooChart=e()` en
   `chart.umd.min.js`), con su marcador en un comentario aparte. En
   [parches_pns_ai.md](parches_pns_ai.md) queda el `grep` que lo localiza.

### Validación con P-70

En el laboratorio `lab_pns_ai_3879`, con recarga sin caché.

**Criterios:**
- **Odoo:** `window.Chart` sigue siendo la 2.x (`Chart.helpers` presente, sin `Chart.version`), sin
  errores `xAxes`/`yAxes` en la consola.
- **Chat:** `PnsChatbooChart.version` = `4.4.8`, y sus gráficos se pintan.

**Casos:**
1. Ventas → Análisis (vista gráfico) → abrir Chatboo y pedir un gráfico → volver sin F5 y cambiar
   barras → líneas → circular.
2. Lo mismo con el tablero de Facturación.
3. Orden inverso: F5 → abrir el chat → vista gráfico y tablero; y abrir el chat otra vez.
4. Sesión antigua con gráfico (como P-9e, sesión 5): el gráfico del chat se pinta.

## 5. Pendiente

- Aplicar la opción A en E2′, con las dos condiciones de la decisión, y repetir P-70: cierra la
  condición 3 de N12.
- Antes de usar `lab_pns_ai_14` como laboratorio de 3.1.782, arrancar su contexto (`lab_pns_ai`):
  abierta con el contexto actual mezcla versiones (§3).
