# Fase 1 de `pns_ai` en la 17: código que solo se activa en la 15 o superior

- **Fecha:** 24/11/2026.
- **Rama y partida:** `17.0-pns-ai`, HEAD `a8713b1` (igual a `origin/17.0-pns-ai`), sin cambios locales. Módulos:
  `pns_base` 17.0.1.2.92, `pns_ai_mcp` 17.0.3.1.996 y `pns_ai_chatboo` 17.0.2.1.597 (R17).
- **Qué es la fase 1** (`docs/pendiente/plan_pns_ai_17.md`, L71-72): «analizar el código que solo se activa en la 15 o
  superior y que en la 14 no se revisó (`ir_ui_view_patch.py`, assets, rutas JSON, cliente de Chatboo), con el
  criterio de los PNS». La lista sale de la 14 (`docs/specs/analisis_pns_base.md` de `14.0`: §2.3, §10 y punto 9,
  «lógica muerta en 14 (`ir_ui_view_patch.py` completo)»).
- **Este documento:** mide el alcance (solo lectura) y propone las etapas. Cada etapa lleva sus tests en el
  laboratorio (`seges_pruebas_3996`, con su copia en `docs/pendiente/lab_3996/`); el detalle, en la sección 6.
- **Decisiones de Sergio (24/11/2026):**
  - **60.** Alcance: el del plan, las cuatro áreas con el criterio de los PNS; el inventario de condiciones de versión
    es la base. El JS se revisa por riesgo, no entero: primero un inventario con `git grep` de los puntos peligrosos y
    después la revisión a mano de lo que salga, diciendo lo que queda sin revisar. Puntos peligrosos:
    - lo que mete HTML: `innerHTML`, `insertAdjacentHTML`, `markup(`, `t-raw`, `t-out` con `markup`;
    - lo que ejecuta código: `eval`, `new Function`, `setTimeout` con una cadena;
    - `postMessage` y los iframes;
    - `localStorage`, `sessionStorage` y `document.cookie`;
    - las URL absolutas y las librerías que se cargan bajo demanda;
    - las llamadas al servidor y su `csrf_token`.
  - **61.** Lo inverso (código de la 14 muerto en la 17: los dos `name_get`) entra en la fase 1 como lectura; la
    corrección, en el port. La rama de la 14 del guardián ya está registrada (decisión 48).
  - **62.** Numeración propia, `F1-n`, hasta el port, con búsqueda de antecedentes antes de numerar.
  - **63.** Este documento, enlazado desde el plan.
  - **64.** Los tests de la fase 1 se escriben en `seges_pruebas_3996` y en su copia de `docs/pendiente/lab_3996/`,
    por etapas, cada una con su fase 1 y su fase 2: primero se ejecutan en el laboratorio y después se escriben en el
    repo.
  - **65.** La marca `[C-ej]` (código de R17 ejecutado en el contenedor, sin Odoo ni BD) es propia; no equivale a
    «probado».
  - **66.** F1-5 se numera como menor, con la regla de F1-3 y F1-4 para el port.
  - **67.** Lo de la migración 14→17 va a `docs/migracion/`, como inferido (no probado).
  - **68.** El test 3 (b), en verde, describe lo que pasa: la pista pesa más que el xml_id.
  - **69.** `[HYPOTHESIS]` solo para un test que afirma el comportamiento seguro y sale en rojo mientras haya defecto;
    los tests de F1.1 son normales y se esperan en verde; los mensajes se comprueban con el texto literal de la capa
    que se prueba; el criterio de los PNS reconstruido de la 14 está en la sección 1.
  - **70.** La etiqueta `[CHECK]` (test que documenta lo que pasa, en verde) se acepta.
  - **71.** `tests/__init__.py` se queda con su patrón (solo la línea añadida, sin reordenar ni `noqa`).
  - **72.** El pendiente de migración va en `docs/migracion/pendiente_17.0.md` (regla `pendiente_<rama>.md`, con la
    rama de destino); es el primer archivo de la carpeta y su formato queda como convención.
  - **73.** F1-6 se numera ya como «sin confirmar» (como F1-1 y F1-2); lo confirma o lo descarta el test 4
    (`[HYPOTHESIS]`).
  - **74.** Los tres puntos iguales en la 14 (el mensaje sin escapar en el SSE, el creador que pasa siempre en
    `session_file` y el `str(e)` en las respuestas del Chatboo) van como observación para el port en la sección 7,
    sin número `F1-n`, con sus antecedentes de la 14.
  - **75.** El test 3 entra: con un método sin efectos ni red (`tools/list`), el permiso conversacional como
    `[SETUP]` y una clave creada en el test que nunca sale en el log ni en el informe.
  - **76.** Para los cuerpos idénticos a 3.1.973 vale la revisión de la 14. El alcance de F1.2 es lo que cambia en
    el core 17 más el cambio de `list_providers`.
  - **77.** El cambio de `list_providers` se numera como F1-7, regresión de PNS-71 (Baja).
  - **78.** F1-6 y F1-7 van al port como correcciones (no con la regla de los menores de F1-3 a F1-5). Con la
    corrección de F1-6, el test 4 pasa a verde.
  - **79.** El `str(e)` de las rutas del Chatboo distintas de `check_health`, el mensaje sin escapar del SSE y el
    creador en `session_file` van como observación para el port en la sección 7, con sus antecedentes.
  - **80.** Se amplía la definición de la marca [C]: «capturado del contenedor en una ejecución sin red: existencia y
    dónde, o el cuerpo del código del core leído allí; no es una ejecución de ese código (eso es [C-ej] o probado)».
  - **81.** Las citas de documentos de la 14 con «fabricante» en el nombre se quedan: son antecedentes internos. La
    decisión 74 se refiere a no escribir nada dirigido al fabricante.
  - **82.** F1-8 (Baja) va al port como corrección, como F1-6 y F1-7. Verificado en código, sin test de navegador.
    La reproducción manual (abrir Autorizaciones, ir a otro menú, empezar a editar un formulario, que otro usuario
    cree un plan y ver la recarga) va a la lista de comprobaciones del staging de la fase 3.
  - **83.** Sin test de navegador en F1.3. El caso 20 queda probado con los 6 tests del servidor; el caso 23,
    correcto por lectura ([C] para `handleMessage` y `subscribe` del core, [L] para los lectores), no probado.
  - **84.** El sexto emisor (`ai_skill.py:36-38`) entra en el caso 20. La nota del PIN en `bus_bus` va con PNS-84,
    sin número, con la frecuencia real del autovacuum citada. La clave que guarda `key_pin_desk.js` en el navegador
    se apunta para F1.5.
  - **85.** El `unsubscribe` muerto de `chatboo_app.js:469-474` es una observación con la regla de los menores.
  - **86.** F1-1 pasa a menor (regla de F1-3 y F1-4): la contradicción interna sigue, el efecto queda descartado.
    Sale de «correcciones nuevas» en la sección 7.
  - **87.** F1-2, Baja y cosmética, se da por confirmado si el test `[HYPOTHESIS]` sale en rojo. Corrección en el
    port: un `_compute_display_name` con `@api.depends('title', 'name')` en `ai.provider.model`; su `name_get` se
    deja (código multiversión); en `ai.mcp.user`, nada.
  - **88.** El `name_get()` directo de `utils/record_label.py:35`, observación sin número con la regla de los
    menores, diciendo que hasta corregir F1-2 `where_it_is` muestra «Título (slug)» y `display_name`, el slug.
  - **89.** La línea desfasada de la sección 4 («Falta: … casos 3 a 6 (etapa F1.1)») se corrige en el mismo commit.
  - **90.** Sin tests para los casos 11 y 15.
  - **91.** F1-9 se numera, Baja de forma provisional hasta la lectura de los `data-*`; también está en 3.1.973. Si se
    parchea en la 14, es una decisión aparte, fuera de esta fase.
  - **92.** La nota para PNS-84 (la lista de claves sobrevive al cierre de sesión) va sin número; su comprobación
    manual, a la lista del staging de la fase 3.
  - **93.** La imagen del laboratorio ya trae Chrome (sección 10 de la clasificación; `TestWebClientStarts`).
  - **94.** Para el JS, la decisión 76 exige una revisión con entradas hostiles; una lectura funcional no cuenta.
  - **95.** pdf.js 2.16.105 es del core: una línea en los límites (sección 1) como efecto fuera de los módulos, sin
    revisar.
  - **96.** Entran T1 y T2 (el saneador en el navegador); no entra un test de navegador de F1-9: se reproduce a mano
    en el staging de la fase 3, como F1-8.
  - **97.** Antes de la fase 2 de F1.5, una lectura de los `data-*` y de los eventos SSE.
  - **98.** F1-9, Media provisional; se confirma o se baja en el staging de la fase 3 (si el `position:fixed` no sale
    de la burbuja, baja a Baja).
  - **99.** F1-10, aparte y Baja, con la causa común con F1-9 anotada (el saneador deja pasar `id`, `class` y
    `data-*`, y el cliente no distingue el HTML del servidor del del modelo); corrección conjunta en el port, con su
    diseño allí.
  - **100.** Tests (decisión 69): T1 `[CHECK]` (lo que ya se cumple); T2a `[CHECK]` (idempotencia y nodo vivo); T2b
    `[HYPOTHESIS]` (la salida no contiene mandos del chat), en rojo hoy.
  - **101.** Antes de los tests, dos lecturas del servidor: el origen de las URL de `assistant_files` y `clip_data`,
    y el uso de las filas marcadas, parando si alguna da un riesgo.
  - **102.** La lista de comprobaciones del staging de la fase 3 es un bloque propio de la sección 7 (F1-8, F1-9 y la
    nota de PNS-84).
  - **103.** Lo que no tiene puntos peligrosos (la lógica de `chatboo_app.js`, `chatboo_export.js` y
    `chatboo_charts.js`, el tooltip de ECharts y el interior de las librerías) se declara sin revisar (decisión 60),
    y F1.5 se cierra así.
  - **104.** Las filas marcadas son F1-11, aparte y Media provisional. Causa común con F1-9 y F1-10 (decisión 99);
    corrección en el servidor, con su diseño en el port. También en 3.1.973. Su comprobación manual, al staging de la
    fase 3 (decisión 102).
  - **105.** Antes de los tests, dos lecturas: los planes de confianza que se confirman solos y qué muestra la tarjeta
    de un plan, parando si un plan de confianza puede escribir sobre el registro marcado sin tarjeta.
  - **106.** T3 `[HYPOTHESIS]` (`TransactionCase`, `test_marks_17.py`): una marca a un registro que el usuario no
    puede leer y otra a un id que no existe se descartan al guardarse. En rojo hoy.
  - **107.** El `sudo` de `_names_for` (`safe_plan_describe.py:82-91`, que llama `_step_targets`, `:190-198`) se
    numera aparte como F1-12, Baja; no va dentro de F1-11.
- **Marcas:**
  - **[L]:** leído (el cuerpo del código o del documento).
  - **[Loc]:** localizado por búsqueda, sin leer el cuerpo.
  - **[C]:** capturado del contenedor de `odoo-dev:17-lab_pns_ai_3996` (core `17.0-20260908`,
    `/usr/lib/python3/dist-packages/odoo`) en una ejecución sin red (decisión 80): existencia y dónde, o el cuerpo
    del código del core leído allí; no es una ejecución de ese código (eso es [C-ej] o probado).
  - **(ref.):** cita de `/opt/odoo-src/17.0/odoo` (`6a0efa7`), solo para lo que esa ejecución no capturó.
  - **[C-ej]:** código de R17 ejecutado en el contenedor, sin Odoo ni BD (decisión 65): el convertidor de
    `ir_ui_view_patch.py:20-301`, con el script por la entrada estándar. Muestra cómo se comporta ese código; no
    equivale a probado.
  - **probado:** ejecutado en el laboratorio: las pruebas indirectas (sección 1) y los tests de cada etapa
    (sección 6).
  - **Etiquetas de los tests del laboratorio** (decisión 70):
    - `[HYPOTHESIS]`: el test afirma el comportamiento seguro y sale en rojo mientras haya defecto;
    - `[CHECK]`: el test documenta lo que pasa y se espera en verde;
    - `[SETUP]`: falla una condición previa; no dice nada de la hipótesis.
  - Las rutas del core van como en el árbol de fuentes (`odoo/…`, `odoo/addons/base/…`, `addons/<módulo>/…`).

## 1. Método y límites

- **Búsqueda (R17, `git grep` en `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo`, sin `i18n/`, `lib/` ni `*.min.js`):**
  - condiciones de versión: `version_info`, `ODOO_VERSION`, los predicados `applies_*` de
    `pns_base/utils/version_gates.py`, `NEEDS_ROOT_GET_REQUEST_PATCH` y `_USE_INVALIDATE_RECORDSET`;
  - comprobaciones de existencia: `hasattr(`, `getattr(…, <por defecto>)` y `except ImportError`;
  - comentarios «Odoo 15…19+», «O15…O19+» y «v15…v19»;
  - sobrescrituras sin condición de una lista de unos 40 nombres de la API de la 15 a la 18 (`get_view`,
    `search_fetch`, `web_search_read`, `web_read`, `_has_field_access`, `_check_field_access`, `check_access`,
    `_compute_display_name`, `name_get`, `onchange`, `session_info`, `_sendone`…);
  - JS y XML: `server_version`, `version_info`, `odoo.define`, `odoo.loader`, `require(`, comentarios de versión;
  - las cuatro áreas, medidas: manifiestos (`assets`), comparación de cada asset con 3.1.973
    (`/home/soporte/pns_fabricante/3.1.973`), rutas (`@http.route`, `type=`, `csrf=False`) y XML con `attrs`.
- **Core:** una ejecución de Docker (marca [C]) para la existencia de cada API de la que depende un caso; lo que no
  capturó, en la referencia (ref.).
- **Criterio de los PNS** (el de la 14; no está escrito con ese nombre: `git grep -i "criterio de los PNS"` en
  `docs/` de `14.0` no da nada). Reconstruido para F1.1 y lo usan F1.2 a F1.5 (citas de `14.0`):
  - ficha: ubicación, descripción, reproducción, impacto y recomendación (`informe_fabricante_pns_ai.md:144-184`);
    estado: reproducido, verificado en código, inferido o no reproducido (`:32`);
  - gravedad (crítica, alta, media o baja; `:28`) según quién alcanza el código (portal, cualquier interno, un rol de
    IA o un administrador; `:181`) y qué permite (escalada, secretos, integridad de los datos, XSS o inyección;
    PNS-15, `:53`);
  - la puerta es la llamada por RPC, con el contexto y el `browse` de quien llama
    (`comparacion_pns_ai_3-1-879.md:1011-1015`); la gravedad es siempre una propuesta (`:1011`);
  - los efectos fuera de los módulos PNS son una categoría propia (tema 7, `pns_ai_decisiones.md:236`; riesgo 1 de
    `analisis_pns_base.md` §13); en ella se valora el coste de los parches globales (PB-2,
    `comparacion_pns_ai_3-1-879.md:805`).
- **Puede quedar fuera:**
  - código de la 15 o superior sin condición y con un nombre que no está en la lista (por ejemplo, una firma que
    cambia de sentido sin cambiar de nombre);
  - las 59 rutas ya no están solo contadas: están inventariadas en F1.2 (sección 4). Alcance de F1.2 (decisión 76):
    lo que cambia en el core 17 y `list_providers`. Los 59 decoradores son idénticos a los de 3.1.973 (comparados
    por AST: URL, función y argumentos) y los cuerpos también, salvo `list_providers` y el import de
    `content_disposition` de `chatboo.py` (comparación de los archivos de `controllers/` y de sus utilidades); esos
    cuerpos no se han vuelto a revisar en la 17: vale la revisión de la 14;
  - el JS: revisado por riesgo en F1.5 (decisión 60; sección 4). Queda sin revisar lo que no tiene puntos
    peligrosos (decisión 103): la lógica de `chatboo_app.js`, `chatboo_export.js` y `chatboo_charts.js`, el tooltip
    por defecto de ECharts (no hay `formatter` propio) y el interior de las librerías bajo demanda;
  - fuera de los módulos, sin revisar (decisión 95): el core trae pdf.js 2.16.105
    (`addons/web/static/lib/pdfjs/build/pdf.js`) [C], que `chatboo_pdf_viewer.js` usa para abrir PDF del mismo
    origen;
  - el core 14 no está en las referencias: «no existe en la 14» se apoya en los comentarios del fabricante y en
    `analisis_pns_base.md`, no en una comprobación.
- **Cobertura (localizada por nombre en los tests; no se ejecutó nada):**
  - **directa, casi ninguna:**
    - tests del fabricante: `_get_env_for_operation` (`test_sandbox_live_handles.py`,
      `test_relaxaicode_sandbox_escapes_e2e.py`) y el `Content-Type: application/json` (`tests/_helpers.py`,
      `test_session_download.py`, `test_chatboo_perimeter.py`);
    - laboratorio: `test_review_views.py` (el `get_view` del asistente, parches 21 y 36) y `test_side_cursors.py`
      (`test_is_running`);
    - laboratorio, F1.1: `test_view_patch_17.py` (casos 3 a 6, sección 6);
    - laboratorio, F1.2: `test_routes_17.py` (caso 9, F1-6, el error de una ruta `json`, `text/plain` y CSRF;
      sección 6);
    - laboratorio, F1.3: `test_bus_17.py` (caso 20: los 6 emisores, con el canal y el mensaje de `bus.bus`;
      sección 6);
    - laboratorio, F1.4: `test_display_name_17.py` (caso 25: el `display_name` de `ai.provider.model` y de
      `ai.mcp.user`; sección 6);
    - laboratorio, F1.5: `test_sanitizer_17.py` (`sanitizeHtml` del módulo en el navegador: T1, T2a y T2b; F1-9,
      F1-10 y F1-11 en el lado del cliente) y `test_marks_17.py` (T3: `remember_marks`, F1-11); sección 6;
  - **indirecta (probado, sección 10 de la clasificación):**
    - la instalación de los tres módulos ejecuta la conversión de las 250 `attrs`, `post_init_hook` y `convert_file`;
    - `TestWebClientStarts.test_backend_starts_without_errors` (`pns_base`, en verde) carga el bundle completo,
      `pns_web_paths.js` incluido, sin errores de consola;
  - **sin cobertura:** casos 11, 15 y 21 a 23 de la sección 3 (el 11 y el 15, correctos por lectura, decisión 90;
    el 23, correcto por lectura, decisión 83), y la
    desinstalación (los casos 4 y 5, desde F1.1);
  - `TestRequiredFieldsLive` (caso 17) está omitido en el laboratorio porque no hay `crm`.

## 2. Inventario de las condiciones de versión

- **Fachadas:** `pns_base/utils/compat.py:15` (`ODOO_VERSION = odoo.release.version_info[0]`) y
  `pns_base/utils/version_gates.py:15-19` (umbrales: `attrs` 17, `<tree>`→`<list>` 18, `privilege_id` 19,
  `ir.access` 20 y parámetros con tipo 20), reexportadas por `pns_ai_mcp/utils/compat.py:6-23` y
  `pns_ai_chatboo/utils/compat.py`. En JS, `pns_base/static/src/js/pns_web_paths.js` [L].
- **Recuentos (sin tests salvo donde se dice):**

| Tipo | pns_base | pns_ai_mcp | pns_ai_chatboo | Total |
|---|---|---|---|---|
| Condición de versión explícita | 25 | 22 | 2 | 49 (15 activas y 34 muertas en la 17) |
| Condición de versión en tests | 0 | 5 | 0 | 5 |
| `hasattr(` | 6 | 37 | 8 | 51 (63 con tests) |
| `getattr(…, <por defecto>)` | 32 | 263 | 32 | 327 |
| `except ImportError` (con tests) | 8 | 25 | 7 | 40; ninguno es de la serie de Odoo |
| Comentarios «Odoo 15…19+» (con tests) | 19 | 36 | 21 | 76 (73 sin tests) |
| Sobrescrituras de la lista de nombres | 3 | 12 | 1 | 16 |
| JS: comprobación de versión explícita | 0 | 0 | 0 | 0 |

- **De los `hasattr` y `getattr`, unos 33 son sobre API del core;** están en los casos de la sección 3.
- **Las 16 sobrescrituras:** 10 de API nueva o con otra semántica en la 17 (`get_view` ×2, `search_fetch`,
  `web_search_read` ×2, `web_read`, `_compute_display_name` ×2, `_has_field_access`, `_check_field_access`), 2
  `name_get` (API de la 14) y 4 que existen en las dos (`_compute_arch`, `_process_ondelete`, `session_info` ×2).
- **JS, comprobaciones de existencia:** `pns_web_paths.js` (3 módulos) y la forma de la notificación del bus
  (suscripción `chatboo_app.js:456-481`, interpretación `:25-64`; `chatboo_systray.js:47-59`; caso 23).
- **Criterio de descarte:**
  - `getattr(request, 'mcp_*')` y similares: atributos propios del fabricante;
  - `hasattr`/`getattr` sobre datos o registros propios (`invoke_code`, `isoformat`, `_ids`, `probe_stt`…) y sobre
    Python o `ast`;
  - `ImportError` de librerías opcionales (`openpyxl`, `reportlab`, `xlrd`) o marcados «unit tests … outside the Odoo
    package». Los de `pns_base/utils/pdf_io.py` (`pypdf`, `fitz`) dependen de la imagen, no de la serie (caso 21).
- **Condiciones de los tests (5):** `pns_ai_mcp/tests/_helpers.py:303`, `:372`; `tests/_offline.py:19`;
  `tests/test_sandbox_secret_read.py:107`, `:116` [Loc].
- **Las 15 activas en la 17** (la condición elige un camino distinto del de la 14):
  - `pns_base`: `utils/compat.py:28`, `:39`, `:81`; `models/ir_ui_view_patch.py:321`, `:338`, `:348`, `:366`, `:405`;
  - `pns_ai_mcp`: `hooks.py:37`, `:108`; `utils/compat.py:33`, `:66`; `http_patch.py:26`;
    `models/res_config_settings.py:159`;
  - `pns_ai_chatboo`: `hooks.py:20`.
- **Las 34 muertas en la 17** (se ejecuta la rama de la 14) [Loc salvo donde se dice]:
  - `pns_base` (17):
    - `utils/compat.py:18`, `:21`, `:31`, `:32`, `:35`, `:36`, `:51` (19 y 20) [L];
    - `models/ir_access_legacy.py:38` y `models/ir_config_parameter_compat.py:18` (20);
      `models/ir_groups_patch.py:48` (19);
    - `models/ir_ui_view_patch.py:111`, `:327`, `:340`, `:416`, `:463`, `:479` (18) y `:427` (19) [L];
  - `pns_ai_mcp` (16):
    - 14 `models.Constraint` (19; en la 17, `_sql_constraints`): `models/ai_agent.py:213`, `ai_context.py:111`,
      `ai_safe_choice.py:32`, `url_whitelist.py:96` [L]; `ai_agent.py:1700`, `ai_provider_role.py:154`,
      `ai_skill.py:278`, `ai_skill_param_cache.py:65`, `ai_trusted_action.py:77`, `ai_view_policy.py:37`,
      `api_result_cache.py:48`, `api_server_key.py:65`, `external_server.py:360`, `fetch_cache.py:51`;
    - `models/sandbox_secret_read.py:174` (20);
    - `controllers/session_file.py:29` (18; en la 17, `check_access_rights` y `check_access_rule`) [L];
  - `pns_ai_chatboo` (1): `utils/form_draft.py:32` (18; igual que el anterior) [L].

## 3. Casos activos en la 17

Clases: **correcto**; **distinto** (activo, pero depende de algo que no existe o es distinto en la 17); **muerto**
(nunca se cumple en la 17); **sin saber** (no se puede saber sin ejecutarlo). Parche relacionado: el mismo archivo en
la tabla de la sección 3 de la clasificación, no las mismas líneas. Los casos 19 y 25 son ramas de la 14 que se
ejecutan en la 17 (sus condiciones aparecen como muertas en la sección 2) y están aquí porque dependen de una API que
cambia.

- **Caso 1. Ganchos con `env`:** `pns_ai_mcp/hooks.py:37`, `:108` y `pns_ai_chatboo/hooks.py:20` [L].
  - Rama: `env = args[0]`. Core: `odoo/modules/loading.py:247` (`post_init_hook(env)`) [C]; `:565`
    (`uninstall_hook(env)`) (ref.).
  - Clase: correcto. Cobertura: instalación (probado indirecto); desinstalación, ninguna. Parche: ninguno.
- **Caso 2. Firma de `convert_file`:** `pns_ai_mcp/hooks.py:69-87` [L].
  - Core: `odoo/tools/convert.py:674`, `(env, module, filename, idref, mode, noupdate, kind, pathname)` [C].
  - Clase: correcto. Cobertura: instalación. Parche: ninguno.
- **Caso 3. Conversión de `attrs`:** `pns_base/models/ir_ui_view_patch.py:321` (`_load_records`), `:338` (`create`),
  `:405` (`_auto_convert_attrs`) [L].
  - Rama: convierte `attrs` en `invisible`/`readonly`/`required` en las vistas `pns_*`; `<tree>` se queda.
    Alcance: 250 `attrs=` en 19 XML (`pns_base` 31 en 4, `pns_ai_mcp` 219 en 15, `pns_ai_chatboo` 0).
  - Core: `odoo/addons/base/models/ir_ui_view.py:394` rechaza `attrs` «Since 17.0» [C].
  - Clase: **correcto** (F1.1, 24/11/2026; antes, correcto según la instalación y pendiente de revisar).
    - Algoritmo [L]: `attrs=(["'])(\{.*?\})\1` (`:410`) acaba en el primer `}` seguido de la misma comilla; lxml
      escribe los atributos entre `"` y la `"` del valor como `&quot;` (`odoo/tools/convert.py:141-144` [C]), así
      que un `}` del valor no la corta. Después, `html.unescape` (`:217`), `ast.literal_eval` (`:219`), el dominio
      en notación prefija (`:135-195`, valores con `%r`) y `html.escape(quote=True)` (`:236`).
    - Lo que no convierte: ERROR y el `attrs` se queda; el core rechaza todo `//*[@attrs]` del arch combinado
      (`odoo/addons/base/models/ir_ui_view.py:392-394` [C]), así que falla a la vista y la condición no se pierde en
      silencio. Las formas límite, en F1-5.
    - Alcance [L]: las vistas con xml_id `pns*` (también las `pns_*` que heredan del core) y, por las pistas de
      modelo o nombre (`:82-91`), las de terceros sobre modelos `ai.*`; una vista de un tercero sin pistas que
      hereda de una `pns_*` no se convierte. Ninguna vista `pns_*` está en un archivo `noupdate="1"`: en cada `-u`
      se recargan y se convierten (`odoo/tools/convert.py:366-378` [C]).
    - Las 250 `attrs` [C-ej]: 51 vistas; claves `invisible` 231, `readonly` 17 y `required` 5; solo `=` (190) y
      `!=` (96); 25 modificadores con varios términos (máximo, 6 hojas). Ninguna forma difícil: 0 no literales, 0
      valores con `{ } < > & '` o `"`, 0 atributos fijos repetidos, 0 en un texto, 0 `<attribute name="attrs">` y
      0 `states=`. Convertidas: 0 ERROR, 0 `attrs` que queden, y todas pasan `get_expression_field_names`. Las
      comparaciones con `True`/`False` son sobre Boolean, Char, Text, Many2one y Selection, ninguna numérica [L].
    - Probado: `test_converter_difficult_values` y `test_no_pns_view_keeps_attrs`, en verde (sección 6).
    - Sin saber: un Char o Text vaciado a `""` en el cliente (`= False` en la 14 frente a `not x` en la 17).
  - Cobertura: instalación (probado indirecto) y los dos tests. Parche: ninguno; lo usan los parches 21 y 36
    (`_inject_screen_arch`).
- **Caso 4. `write` por pistas:** `ir_ui_view_patch.py:348` [L].
  - Rama: convierte si el nombre o el modelo de la vista contienen una pista (`'pns'`, `'inherit.mcp'`, `'ai.'`,
    `'mcp.'`, `'relaxaicode'`), sin mirar el xml_id.
  - Clase: **correcto** (F1.1, 24/11/2026; antes, sin saber por los falsos positivos de las pistas en vistas ajenas).
    - Pistas: 0 de 1.264 `_name`, 0 de 6.620 vistas (`name` y `model`) y 0 módulos `pns*` de 642 en el contenedor
      [C]; 0 de 1.101 `_name`, 0 vistas y 0 módulos `pns*` en `oca/` y `vertical-instaladores/` (ref.).
    - Un falso positivo solo cambia archs con `attrs=` o `name="attrs"`, que la 17 rechaza: en el peor caso arregla
      una vista ajena inválida o reescribe un texto (F1-5). En `ir.ui.view` solo escribe `base.group_system`
      (`odoo/addons/base/security/ir.model.access.csv:35`; la `:34`, sin grupo, es `0,0,0,0`) [C], o código en
      `sudo`.
    - Probado: `test_write_hints`, en verde. Sin pista, el core rechaza `attrs` con su mensaje literal; con la pista
      `ai.` y un xml_id que no es `pns*`, se convierte (la pista pesa más que el xml_id; decisión 68); sin sintaxis
      antigua, el arch se guarda tal cual.
    - Sin saber: módulos de clientes que no están en las referencias.
  - Cobertura: `test_write_hints`. Parche: ninguno.
- **Caso 5. `_compute_arch`:** `ir_ui_view_patch.py:355-378` [L].
  - Rama: convierte el arch del archivo (`--dev=xml` o lectura de `arch_fs`).
  - Core: `odoo/addons/base/models/ir_ui_view.py:220` [C]; cuerpo leído en F1.1 (`:218-258` [C]).
  - Clase: **correcto** (F1.1, 24/11/2026; antes, se resolvía leyendo el core).
    - El core lee el archivo con `read_arch_from_file` en el contexto, o con `--dev=xml` y sin `arch_updated`
      (`:235-236`), si hay `arch_fs` y xml_id o `key` (`:237`); si no, `arch_db` (`:258`) [C]. El archivo conserva
      las `attrs`: sin el parche fallarían `--dev=xml`, «Restablecer al archivo» (`reset_arch('hard')`,
      `:299-301`) y el diff con el archivo (`:2239-2240`) (ref.).
    - Coste: en una lectura normal, las listas `pns_*` tienen `<tree`, así que mira el xml_id (una consulta por
      lote, `:331-337` [C], también para las vistas del core con `<tree`) y llama a un convertidor que no cambia
      nada. Solo cuando `_get_view_cache` no tiene la vista, que está en caché salvo con `--dev=xml`
      (`:2591-2596` [C]).
    - Probado: `test_arch_from_file_and_reset`, en verde.
  - Cobertura: `test_arch_from_file_and_reset`. Parche: ninguno.
- **Caso 6. `Base.get_view` sin condición:** `ir_ui_view_patch.py:507-519` [L].
  - Rama: añade la clase `o_pns_view` a las vistas `pns_*`; en cada `get_view` de cualquier modelo hace `browse` y lee
    `view.xml_id`, fuera de la caché de vistas.
  - Core: `odoo/addons/base/models/ir_ui_view.py:2635` [C]; devuelve una copia, `dict(self._get_view_cache(…))`
    (`:2660` [C], comprobado en F1.1).
  - Clase: **correcto**, revisado con el criterio de los PNS (F1.1, 24/11/2026; antes, correcto con el coste por
    llamada por revisar).
    - Core (`:2634-2664` [C]): `check_access_rights('read')`, la copia de `:2660` y, en cada llamada,
      la lectura y escritura del arch (`:2662-2664`).
    - Añade por llamada una consulta (`_compute_xml_id`: `ir.model.data.sudo().search_read`, `:334` [C]; el campo no
      se guarda) y, solo en las vistas `pns*`, otra lectura y escritura del arch. No toca la caché (cambia un `str`
      de la copia) ni usa `sudo()` (lo usa el core). Sin AccessError para quien no lee `ir.ui.view`: solo los campos
      guardados pasan por `_fetch_field` (`odoo/fields.py:1176-1184` [C]; el camino de los calculados, ref.).
    - `o_pns_view`, solo si el módulo del xml_id de la vista raíz empieza por `pns`: no hay ningún módulo así fuera
      de `third_party`, ni en el contenedor [C] ni en la referencia (ref.).
    - Probado: `test_get_view_class_and_cost`, en verde, con una diferencia de exactamente 1 consulta.
    - Sin saber: la caché de `get_views` en el cliente web, sin leer. Sin número: lo cubre PNS-42/PB-2 (sección 5).
  - Cobertura: `test_get_view_class_and_cost`. Parche: ninguno.
- **Caso 7. `read_sums`:** `pns_ai_mcp/utils/compat.py:33` [L].
  - Rama: `_read_group(domain, [], ['<campo>:sum'])`. Core: `odoo/models.py:1857` [C].
  - Clase: correcto. Quién lo llama: sin buscar. Cobertura: ninguna. Parche: ninguno.
- **Caso 8. `invalidate_recordset`:** `pns_base/utils/compat.py:39`, `:81` [L].
  - Core: `BaseModel.invalidate_recordset` existe; `invalidate_cache`, no [C].
  - Clase: correcto. Cobertura: indirecta (muchos usos). Parche: ninguno.
- **Caso 9. `/mcp` sin `http_patch`:** `pns_base/utils/compat.py:28` → `pns_ai_mcp/http_patch.py:26` [L].
  - Rama: no hay parche; el POST con `Content-Type: application/json` a `/mcp` (rutas `type='http'`) lo despacha el
    core.
  - Core [C; ejecución de F1.2, cuerpos leídos; `odoo/http.py` y `odoo/addons/base/models/ir_http.py` tienen el
    mismo sha256 que en `6a0efa7`]:
    - `_set_request_dispatcher` elige el dispatcher por el `type` de la ruta y da 400 si no es compatible
      (`odoo/http.py:1907-1918`). `HttpDispatcher.is_compatible_with` devuelve siempre `True` (`:2098-2103`);
      `JsonRPCDispatcher`, solo con `application/json` o `application/json-rpc` (`:2162-2172`);
    - el CSRF solo lo mira `HttpDispatcher`, con un método fuera de `CSRF_FREE_METHODS` y `csrf` distinto de
      `False` (`:2117-2127`). `/mcp` lleva `csrf=False` (`pns_ai_mcp/controllers/main.py:759`) y `auth='none'`, que
      deja `uid=None` aunque haya cookie (`odoo/addons/base/models/ir_http.py:142-144`);
    - con `cors='*'` el core añade `Access-Control-Allow-Origin` y contesta él los `OPTIONS` con 204, sin llegar al
      controlador (`odoo/http.py:2055-2067`).
  - Respuesta según la clave [L] (`main.py:760-1033`), con el `Origin` ausente o permitido (si no, 403, `:767-768`)
    y el agente `pns_ai_mcp` activo (si no, 404, `:769-775`). El `id` es el del cuerpo:

    | Clave | HTTP | Respuesta JSON-RPC |
    |---|---|---|
    | Ninguna | 401 | error `-32000`, «API key required» (`:828`, `:835`; el 401, `controllers/utils.py:62-68`) |
    | Incorrecta | 401 | error `-32000`, «Invalid API key» (`:851`) |
    | Correcta (usuario activo, permiso conversacional) | 200 | `result` del método (`:940`, `:974`) |

  - Clase: correcto, probado (F1.2, 24/11/2026; antes, sin saber): tests 1 a 3 de `test_routes_17.py` en verde
    (sección 6); el 1 devuelve el `id` del cuerpo, así que el cuerpo se lee. Cobertura: esos tres tests; los del
    fabricante envían `application/json` (`tests/_helpers.py:372`) sin comprobar la ruta. Parche: ninguno. Las
    cabeceras de la respuesta: F1-6 (sección 5).
- **Caso 10. Assets de la 14:** `pns_ai_mcp/utils/compat.py:66` [L].
  - Rama: vuelve sin hacer nada; los assets entran por el manifiesto. Clase: correcto. Parche: ninguno.
- **Caso 11. `'list'` en una acción de Ajustes:** `pns_ai_mcp/models/res_config_settings.py:158-159`, usado en
  `:196` [L].
  - Rama: en la 17 devuelve `'list'` para `view_mode` (`'list,form'`) y para `views`.
  - Quién la llama: los botones «Browse all» de `pns_ai_mcp/views/res_config_settings_views.xml:29` y `:51`, dentro
    de `<app … groups="pns_ai_mcp.group_ai_admin">` (`:10`), solo para `group_ai_admin`; abre `ai.agent` con
    `view_ai_agent_tree` y el formulario (`res_config_settings.py:189-202`) [L].
  - Core: `VIEW_TYPES` (`odoo/addons/base/models/ir_actions.py:346-347`, ref.) solo tiene `'tree'`, pero solo valida
    los registros guardados de `ir.actions.act_window.view`; esta acción es un `dict` que va directo al cliente web,
    así que no prueba que `'list'` falle. La cadena de conversiones (F1.4):
    - servidor: `call_button` pasa la acción por `clean_action` (`addons/web/controllers/dataset.py:27-31`, ref.),
      que llama a `fix_view_modes` (`addons/web/controllers/utils.py:28-31`, ref.); con `views` y sin `view_type`,
      cambia `'tree'` por `'list'` en `view_mode` y en `views` (`:127-140`, ref.); un `'list'` pasa igual;
    - cliente: `action_service.js:267` vuelve a cambiar `'tree'` por `'list'` [C]; `_executeActWindowAction` busca
      cada tipo en el registro de vistas, cuya clave es `list` (`:931-937`, ref.); `view_service.js:73-101` manda
      `views` tal cual a `get_views` [C] (`addons/web/static/src/…`);
    - `get_views` cambia `'list'` por `'tree'` antes de llamar a `get_view`
      (`odoo/addons/base/models/ir_ui_view.py:2474-2480`, la conversión en `:2476`) [C].
    - Con `'list'` o con `'tree'`, al cliente le llega `'list'` y al servidor `'tree'`: la acción abre igual.
  - Contradice `pns_base/utils/version_gates.py:16` (`TREE_TO_LIST_FROM = 18`) y el comentario de
    `ir_ui_view_patch.py:107` («Odoo 17 still uses view_mode 'tree'») [L].
  - Clase: **correcto** (F1.4, 24/11/2026; antes, sin saber). Cobertura: sin test (decisión 90); el test del
    módulo `pns_ai_mcp/tests/test_mcp_agent.py:107-115` acepta las dos formas (`'list'` o `'tree'`) [L].
    Parche: ninguno. Hallazgo F1-1, menor (decisión 86).
- **Caso 12. Hilos y registro:** `pns_base/utils/thread_env.py:15`, `:22`, `:32`;
  `pns_ai_chatboo/models/chatboo_job.py:47`, `:62`, `:104` [L].
  - Rama: sin `Environment.manage` usa `nullcontext`; usa `odoo.registry`; llama a `in_test_mode`.
  - Core: `api.Environment` sin `manage`; `odoo/__init__.py:97` (`registry`); `odoo/modules/registry.py:909` [C].
  - Clase: correcto. El comentario de `chatboo_job.py:58` («Odoo 17+/19 removed it», sobre `odoo.registry`) es
    falso para la 17, sin efecto. Cobertura: ninguna por nombre. Parche: ninguno.
- **Caso 13. Atributos del registro y de la versión:** `pns_ai_mcp/controllers/context_builder.py:666`
  (`release.series`), `models/ai_system_action.py:563` y `models/safe_operation.py:1602` (`_init_modules`),
  `utils/skill_runtime.py:691` (`ready`) [L].
  - Core: `odoo/release.py:17`; `odoo/modules/registry.py:133`, `:146` [C].
  - Clase: correcto. Cobertura: ninguna por nombre. Parche: 16 y 38 (`safe_operation.py`).
- **Caso 14. Caché y escrituras pendientes:** `pns_ai_mcp/models/sandbox_secret_read.py:55` (`invalidate_model`),
  `models/ai_log.py:724` y `models/safe_operation.py:1485` (`flush_all`), `utils/engine_tool_run.py:317`
  (`invalidate_all`) [L].
  - Core: `odoo/models.py:6732`; `odoo/api.py:735`, `:719` [C].
  - Clase: correcto. Cobertura: ninguna por nombre. Parche: 38 (`ai_log.py`, `engine_tool_run.py`), 16 y 38
    (`safe_operation.py`), 18 (el guardián).
- **Caso 15. Sin invalidar tras el `rollback()`:** `pns_ai_mcp/controllers/main.py:1378-1380` [L].
  - Rama: en la 17 existe `invalidate_all`, así que no invalida nada a mano.
  - Core: `Cursor.rollback` llama a `self.clear()` (`odoo/sql_db.py:490-492` [C]), que llama a
    `self.transaction.clear()` (`:140-143` [C]). `Transaction.clear` hace `self.cache.clear()` y
    `self.tocompute.clear()` (`odoo/api.py:881-884` [C]); `Cache.clear` vacía `_data`, `_dirty` y `_patches`
    (`api.py:1321-1325`, ref.). Tras el `rollback()` quedan vacíos la caché, las escrituras pendientes y los
    cálculos pendientes.
  - Después del `rollback()`, el controlador solo arma el diccionario de error y lo devuelve (`main.py:1382-1396`)
    [L]. Igual que en 3.1.973: el `rollback` es de PNS-26 (resto, 3.1.842; `comparacion_pns_ai_3-1-879.md:608` de
    `14.0`).
  - Clase: **correcto** (F1.4, 24/11/2026; antes, correcto si `Transaction.clear` invalida la caché). Cobertura:
    sin test (decisión 90). Parche: ninguno.
- **Caso 16. `request.jsonrequest`:** `pns_ai_mcp/controllers/controller_helpers.py:133` [L].
  - Rama: en la 17 `request` no tiene `jsonrequest` (solo `JsonRPCDispatcher`, `odoo/http.py:2205`) [C]; el error
    sale con `id` nulo.
  - Clase: correcto, igual que en la 14 (`/mcp` es una ruta `type='http'`). Cobertura: los dos tests del fabricante
    de `_get_env_for_operation`. Parche: 18 y 37.
- **Caso 17. Arch combinado:** `pns_ai_mcp/utils/field_required_plan.py:67` (`read_combined`), `:103`
  (`default_view`) [L].
  - Core: `odoo/addons/base/models/ir_ui_view.py:915`, `:575` [C].
  - Clase: correcto. Cobertura: `TestRequiredFieldsLive`, omitido sin `crm`. Parche: 38.
- **Caso 18. Lecturas de la web:** `pns_ai_mcp/models/safe_operation.py:2006` y `models/mcp_user.py:584`
  (`web_search_read`), `models/mcp_user.py:579` (`search_fetch`), `models/ai_agent.py:922` (`web_read`) [L].
  - Core: `addons/web/models/models.py:44-45` (`web_search_read` usa `search_fetch`, no `search_read`), `:77` y `:85`
    (`web_read` llama a `read`) [C]; `odoo/models.py:1644` (ref.).
  - Clase: correcto. Cobertura: ninguna por nombre. Parche: 16 y 38 (`safe_operation.py`).
- **Caso 19. Comprobación de acceso:** `pns_ai_chatboo/utils/form_draft.py:32` y
  `pns_ai_mcp/controllers/session_file.py:29` [L].
  - Rama: `check_access_rights` y `check_access_rule`. Core: `odoo/models.py:4139`, `:4150`; `check_access` no
    existe [C].
  - Clase: correcto. Cobertura: ninguna. Parche: ninguno.
- **Caso 20. Avisos por el bus (servidor):** 6 emisores (decisión 84): `pns_ai_chatboo/models/chatboo_session.py:523`,
  `models/chatboo_canvas_page.py:119`, `models/chatboo_async_request.py:1625`, `models/ai_skill.py:36-38`,
  `pns_ai_mcp/models/key_pin_desk.py:72` y `models/safe_operation.py:1753` [L].
  - Rama: `bus.bus._sendone(partner, tipo, payload)`; los fallbacks `sendone` de la 14 están muertos en la 17 [L].
    Cuerpos idénticos a 3.1.973 (decisión 76).
  - Core [C]:
    - `_sendone` (`addons/bus/models/bus.py:111-125`): el canal de un partner es `(bd, 'res.partner', id)`
      (`channel_with_db`, `:58-65`) y el mensaje, `{"type": tipo, "payload": payload}`;
    - la fila de `bus.bus` se crea con `sudo` en el `precommit` (`:131-133`) y el `NOTIFY` sale en el `postcommit`
      (`:135-160`): si la transacción se deshace, no sale nada;
    - el cliente se suscribe a `'broadcast'` y a su propio partner (`addons/bus/models/ir_websocket.py:65-77`);
    - los canales que pide el cliente deben ser cadenas (`:95-96`) y una cadena es `(bd, cadena)` (`bus.py:63-64`):
      un usuario no puede suscribirse al partner de otro. Ningún módulo PNS sobrescribe `_build_bus_channel_list` ni
      `ir.websocket` [Loc].
  - Emisores [L] (los disparadores, [Loc]; `sync` es `pns_chatboo_sync`):

    | Emisor | Tipo | Destinatario | Payload | Disparador |
    |---|---|---|---|---|
    | `notify_files_updated` | `sync` | dueño de la sesión | `message_received`, `session_id` | exportación |
    | `_tell_new_readers` | `sync` | lectores nuevos | `page_shared`, `page_id`, `title`, `owner`, `url` | compartir |
    | `_notify` | `sync` | dueño del trabajo | `action`, `session_id`, `request_id`, `is_error` | trabajo, cron |
    | `_chatboo_notify_skills_changed` | `sync` | usuario actual | `skills_changed`, `confirm`, `session_id` | skills |
    | `_broadcast` | `pns_key_pin*` (4) | AI Admins, mesas | `open`; `type`; `pin`, `email`, `login` | rutas del PIN |
    | `_notify_safe_plan_hosts` | `pns_safe_plan` | dueño, AI Admins | `verification_id`, `status`, `executed` | plan |

    - Ningún payload lleva texto del LLM ni datos de otros usuarios leídos con `sudo`; `verification_id` sale de una
      secuencia (`safe_operation.py:438-457`), no es secreto.
    - Van a un partner distinto del de quien los provoca, por diseño: la página compartida (el dueño la comparte;
      la suplantación del dueño ya es P-8h, `e3_propuesta_3879.md:286-293` de `14.0`), la mesa del PIN (solo AI
      Administrator, `controllers/key_pin.py:14-18`; PNS-84) y los planes (supervisión de los AI Administrators).
  - Clase: **correcto, probado** (F1.3, 24/11/2026; antes, correcto en el servidor): los 6 tests de
    `test_bus_17.py`, en verde (sección 6). La recepción, en el caso 23.
  - Parche: 11, 25, 26, 29 y 38 (`chatboo_session.py`); 28 (`chatboo_canvas_page.py`); 34
    (`chatboo_async_request.py`); 18 y 38 (`key_pin_desk.py`); 16 y 38 (`safe_operation.py`); ninguno en
    `ai_skill.py` (búsqueda en la clasificación).
- **Caso 21. PDF:** `pns_base/utils/pdf_io.py:45-57`, `:219`, `:386` [L].
  - Rama: `PyPDF2`; sin `fitz`, `pdfminer`. Imagen: `pypdf` no, `PyPDF2` 1.26.0, `fitz` no, `pdfminer` sí [C].
  - Clase: correcto (depende de la imagen, no de la serie). Cobertura: ninguna por nombre. Parche: ninguno.
- **Caso 22. Módulos web añadidos:** `pns_base/static/src/js/pns_web_paths.js:29-66` [L].
  - Rama: define `@web/core/network/rpc` y `@web/core/user`, que la 17.0 no trae;
    `@web/model/relational_model/record` ya existe.
  - Core: `addons/web/static/src/core/network/rpc.js` y `core/user.js` no existen;
    `core/network/rpc_service.js:47` `jsonrpc(url, params = {}, settings = {})` (`length` 1: sin `env`);
    `module_loader.js` con `factories` [C]; `odoo.loader` (`module_loader.js:201`, ref.).
  - Clase: correcto en lo que se usa (`chatboo_app.js` y `chatboo_systray.js` importan `rpc`). `@web/core/user` no lo
    importa nadie, y el comentario de la L11 es falso en la 17.0, que solo trata como módulo lo que lleva
    `@odoo-module` (`odoo/tools/js_transpiler.py:673`) [C]. Hallazgo F1-3.
  - Cobertura: `TestWebClientStarts` (probado indirecto: el bundle carga). Parche: ninguno.
- **Caso 23. Avisos por el bus (cliente):** `pns_ai_chatboo/static/src/js/chatboo_app.js` (suscripción
  `:456-481`; interpretación `:25-64`) y `chatboo_systray.js:47-59` [L].
  - Rama: en la 17 usan `bus_service.subscribe` (existe), así que la rama de `useBus(…, "notification")` queda
    muerta. Los demás lectores de esos tipos: `pns_ai_mcp/static/src/js/key_pin_desk.js:243-261` (los cuatro
    `pns_key_pin*`, una sola suscripción por la bandera `listening`) y `safe_operation_action_buttons.js:35-43`
    (`pns_safe_plan`; F1-8) [L].
  - Core [C] (`addons/bus/static/src/services/bus_service.js`; líneas de la referencia, que tiene las mismas 241
    líneas):
    - `handleMessage` recibe `[{id, message: {type, payload}}]` y llama a `notificationBus.trigger(type, payload)`
      (`:68-73`); el evento `"notification"` lleva la lista de `{type, payload}` (`:107`);
    - `subscribe(tipo, cb)` llama a `cb(payload)` (`:232`); no hay `unsubscribe`.
  - Forma: el callback recibe el `message` de Python tal cual; los analizadores solo quitan una capa `payload`
    cuando existe, y aquí no la hay. Cuadra con la 17 [L+C].
  - Qué hacen: recargar la sesión, invalidar la caché de skills, quitar la tarjeta del plan y, en el systray, el
    aviso de página compartida, con `title` y `owner` como texto (`t-out` escapa,
    `addons/web/static/src/core/notifications/notification.xml:7`, `:12`, [C]) y la URL solo si empieza por
    `/chatboo/page/` (`chatboo_systray.js:138-158`) [L]. No pintan HTML del payload.
  - Clase: **correcto** por lectura (decisión 83), no probado. Cobertura: ninguna. Parche: ninguno.
  - Relacionado: F1-8 (`safe_operation_action_buttons.js`) y la observación del `unsubscribe` muerto de
    `chatboo_app.js:469-474` (decisión 85), en la sección 5.
- **Caso 24. Ganchos «Odoo 17+» del guardián:** `pns_ai_mcp/models/sandbox_secret_read.py:100-113` [L].
  - Core: `_has_field_access` y `_check_field_access` no existen en la 17 [C]; protege el gancho de la 14
    (`:116-126`).
  - Clase: distinto. Ya registrado: clasificación, sección 11, punto 1, «Al margen» (decisión 48), junto con la caja
    A con uid 1, que da `su` (localizado, no probado; decisión 48). Parche: 18.
- **Caso 25. `name_get` (lo inverso, decisión 61):** `pns_ai_mcp/models/ai_provider.py:80` (de `ai.provider.model`,
  `:26-27`) y `models/mcp_user.py:536` (de `ai.mcp.user`, `_rec_name = 'user_id'`, `:71-73`) [L].
  - Rama: etiquetas «título (nombre)» y «nombre del usuario» / «No user»; ningún `_compute_display_name` en esos
    modelos [Loc].
  - Core (números del contenedor; sustituyen a `:1678` y `:1694` de la referencia) [C]:
    - `_compute_display_name` (`odoo/models.py:1660-1675`) convierte el `_rec_name` con `convert_to_display_name` y
      no llama a `name_get`; sin `_rec_name`, `"<modelo>,<id>"`;
    - `name_get` (`:1677-1695`) está obsoleto desde la 17.0: avisa (`DeprecationWarning`, `:1694`) y devuelve el
      `display_name`. En `odoo/models.py`, `fields.py`, `api.py`, `osv/`, `addons/web` (controladores y modelos) y
      `odoo/addons/base/models` nadie lo llama;
    - `Many2one.convert_to_display_name` devuelve el `display_name` del valor (`odoo/fields.py:3173-3174`), y
      `res_users.py` no redefine `_compute_display_name`.
  - Etiqueta en la 17:
    - `ai.provider.model` (sin `_rec_name`: `name`): el slug, en lugar de «título (nombre)». Se ve en el Many2one
      `model_id` del formulario del proveedor (`pns_ai_mcp/views/ai_provider_views.xml:32`) y en `placed_label`
      (`utils/record_label.py:51`), que usan `controllers/safe_plan_describe.py:141` y
      `utils/ack_record_card.py:52` [L]. La búsqueda no cambia: en la 14 y en la 17 busca en `name`;
    - `ai.mcp.user`: el nombre del usuario, como su `name_get`; «No user» no se alcanza (`user_id` es
      `required=True`, `mcp_user.py:79-82`) [L].
  - Probado (`test_display_name_17.py`, F1.4): el `[HYPOTHESIS]` de `ai.provider.model` (`name='lab-slug'`,
    `title='Lab Title'`) sale en rojo con `AssertionError: 'lab-slug' != 'Lab Title (lab-slug)'`; el de
    `ai.mcp.user` (`display_name` igual a `user.name`), en verde.
  - Clase: **distinto** en `ai.provider.model` (muestra el slug); sin cambio en `ai.mcp.user` (F1.4, 24/11/2026;
    antes, probablemente muerto en la 17). Cobertura: `test_display_name_17.py`.
  - Parche: 33 (`ai_provider.py`). Hallazgo F1-2, confirmado (decisión 87).

## 4. Las cuatro áreas, medidas

- **Assets:**
  - 81 entradas en los manifiestos (20, 33 y 28), 80 archivos únicos.
  - En 3.1.973 (`/home/soporte/pns_fabricante/3.1.973`, solo lectura) los tres `__manifest__.py` no tienen la clave
    `assets` y cargan `views/assets.xml` en `data` (`pns_base` `:60`, `pns_ai_mcp` `:38`, `pns_ai_chatboo` `:40`),
    una plantilla que hereda `web.assets_backend` [L]. Que Odoo 14 ignoraba la clave lo dice
    `docs/specs/comparacion_pns_ai_3-1-973.md:174` de `14.0` [L], sin comprobarlo en el core 14.
  - Frente a 3.1.973: 25 iguales, 14 distintos y 41 nuevos, unas 17.183 líneas distintas o nuevas (`pns_base` 676,
    `pns_ai_mcp` 3.619, `pns_ai_chatboo` 12.888).
  - Fuera del manifiesto, 9 archivos de `pns_ai_chatboo/static/src`: 7 librerías que se cargan bajo demanda
    (`chart.umd.min.js`, `echarts.min.js`, `html2canvas.min.js`, `jspdf*`) y 2 SVG (zona del parche 20).
  - Revisión por riesgo (F1.5, decisión 60) [L]: `git grep` en los JS y XML de `static/src` de los tres módulos, sin
    `lib/` ni `*.min.js`: 64 archivos (62 del manifiesto y `jspdf_umd_pre.js`/`_post.js`); frente a 3.1.973, 15
    iguales, 8 distintos y 41 nuevos. Triaje por el origen del dato: (a) del modelo, de otro usuario o de fuera;
    (b) del propio usuario o del servidor con escape; (c) constantes o `_t()`; (d) comentarios, lecturas, ramas
    muertas.

    | Punto peligroso | Total | (a) | (b) | (c) | (d) |
    |---|---|---|---|---|---|
    | HTML (`innerHTML`, `markup(`, `t-out`…) | 58 | 18 | 4 | 20 | 16 |
    | `eval`, `new Function`, temporizador con cadena | 0 | – | – | – | – |
    | `postMessage` y oyentes de `message` | 0 | – | – | – | – |
    | `iframe`, `sandbox`, `srcdoc` | 11 | 1 | 2 | – | 8 |
    | `localStorage`, `sessionStorage` (`indexedDB`, `document.cookie`: 0) | 26 | – | 24 | – | 2 |
    | Red (`fetch`, `window.open`, `.src`, `loadJS`) | 29 | 7 | 8 | 7 | 7 |
    | URL absolutas (57 cabeceras de licencia y 6 espacios de nombres SVG) | 63 | – | – | – | 63 |
    | Llamadas al servidor (`rpc`, `orm`, rutas JSON, `csrf_token`) | 63 | – | 63 | – | – |

    Ninguna (a) llega a `innerHTML` sin saneado ni escape, ni a `eval`. No hay URL externas ni librerías de la red.
  - Librerías bajo demanda: se cargan con `loadJS` desde `/pns_ai_chatboo/static/src/js/…`
    (`chatboo_heavy_libs.js:11-19`) [L]. Chart.js 4.4.8, ECharts 5.6.0 y html2canvas 1.4.1, con el mismo sha256 que
    en 3.1.973; jsPDF 4.2.1 y AutoTable 5.0.8, iguales salvo una primera línea `/** @odoo-module ignore */`;
    `jspdf_umd_pre.js` y `_post.js`, nuevos, solo guardan y restauran `define`, `module` y `exports`. No se han
    revisado por dentro (decisión 103).
  - Los 2 SVG (`chatboo_tts_volume_on/off.svg`): sin `<script>`, sin `on*` y sin referencias externas [L].
  - Qué consta revisado en la 14 con entradas hostiles (decisión 94; de `14.0`): el saneado de la respuesta y de la
    exportación (PNS-60, prueba 8 del staging, `plan_staging_pns_ai.md:530`; «sigue corregido con el código nuevo»
    en 3.1.973, `informe_fabricante_pns_ai_3973.md:221`, `comparacion_pns_ai_3-1-973.md:303`, `:331`). La lectura
    del pintado de `chatboo_markdown.js` (`parches_pns_ai.md:5521`) es funcional y no cuenta. Las versiones `_v14`
    de `key_pin_desk.js` (PNS-83, PNS-84, PNS-31) y de `pns_html_readonly_widget.js` (PNS-15), y
    `pns_module_index.js` (PNS-41), tienen antecedentes, no revisión de la versión de la 17. Por eso todo lo de la
    tabla se ha revisado aquí.
- **Rutas:**
  - 59 `@http.route`: 34 en `pns_ai_chatboo/controllers/chatboo.py` y 25 en `pns_ai_mcp` (`main.py` 14,
    `verification_ui.py` 4, `key_pin.py` 3, `choice_ui.py` 2, `remote_image.py` 1, `session_file.py` 1).
  - Ocurrencias de `type=`: 34 `JSON_ROUTE_TYPE` (`'json'` en la 17) y 27 `'http'`. 14 `csrf=False`, todas en
    `pns_ai_mcp/controllers/main.py`.
  - Sin `http_patch` en la 17 (caso 9). Las 27 ocurrencias de `'http'` son 25 rutas y dos comentarios
    (`main.py:763`, `http_patch.py:4`).
  - Inventario (F1.2) [L], por combinación de `auth`, `type` y `csrf`:
    - `none` · `http` · `csrf=False` · `cors='*'` · `save_session=False`: 14, todas `/mcp*` de `main.py`; las alcanza
      cualquiera desde internet. Protecciones: `Origin` (`main.py:308-318`; `utils/mcp_origin.py`) y clave por
      cabecera (hash en `ai.mcp.user`); sin clave no escriben nada (`main.py:116-123`). Los 6 `OPTIONS` los contesta
      el core (caso 9). Sin clave se distingue un agente que existe (401 o 405) de uno que no (404), como en la 14;
    - `user` · `http` · CSRF del core: 11. Aceptan POST 5: `key_pin.py:37` (administrador de IA),
      `chatboo.py:788` (`/chatboo/stream`), `:1192` (compartir el lienzo), `:1216` (lectores de una página) y
      `session_file.py:41` (sin `methods`). Solo GET 6: `remote_image.py:24` (lista blanca) y, en `chatboo.py`, el
      lienzo, `share/people`, la página compartida y las dos descargas (`attachment`);
    - `user` · `json`: 34 (`verification_ui.py` 4, `key_pin.py` 2, `choice_ui.py` 2, `chatboo.py` 26). Sin CSRF en
      el core; solo se llaman con `Content-Type` JSON (test 8), que entre orígenes exige preflight, y ninguna lleva
      `cors`. Comprobación propia: dueño (verificaciones y elecciones), administrador de IA (PIN) o acceso al
      Chatboo con sesión o trabajo propios. Escriben: las 4 de verificación (`pending` genera el token), las 2 de
      elección, `key_pin/supply` (recibe una clave) y, en `chatboo.py`, prefs, sesiones (también `load` y
      `async/poll`, que marcan uso o vistos), exportación, lienzo, trabajos y skills; `key_pin/desk` (`_touch`), sin
      leer [Loc];
    - `public`: 0. `user` con `csrf=False`: 0.
  - 58 reglas registradas: los decoradores interiores apilados de `main.py:261` y `:282` (`OPTIONS` de
    `/mcp/message` y `/mcp/<agent_code>/message`) se pierden (`odoo/http.py:792-806`, `:870-894`) [C], y
    `session_file` lleva dos URL. El preflight de esas dos URL lo contesta igualmente la regla POST, porque
    `ir.http` añade `OPTIONS` a todas las reglas (`odoo/addons/base/models/ir_http.py:262-267`, ref.; mismo
    sha256 que el contenedor).
  - Ninguna ruta es nueva frente a 3.1.973 (decisión 76, sección 1). Revisiones de la 14 que cubren los cuerpos
    (de `14.0`): `analisis_pns_ai_mcp_4_servidor_mcp.md` §2.1-2.4 (rutas MCP, preflight, decoradores apilados y
    elección de BD), `analisis_pns_ai_chatboo_1_servidor.md` §4, `comparacion_pns_ai_3-1-879.md` §8.1 (10 rutas
    del lienzo, el PIN y `fulfill_export`) y PNS-21, PNS-28, PNS-31, PNS-58, PNS-59, PNS-71 y PNS-89.
  - Hallazgos: F1-6 (cabeceras de `/mcp*`) y F1-7 (`list_providers`), en la sección 5.
- **Cliente del Chatboo:**
  - Incluido en las 12.888 líneas de `pns_ai_chatboo`: de sus 28 assets, 16 son idénticos a 3.1.973; de sus 19 JS,
    6 son módulos `@odoo-module` y el resto, scripts sin esa marca (varios se declaran «shared owl1 / owl2»).
  - Enganche con el servidor: casos 20, 22 y 23.
  - Hecha la recepción por el bus (etapa F1.3: casos 20 y 23; F1-8) y la revisión por riesgo (etapa F1.5).
  - Saneador (`sanitizeHtml`, `chatboo_formatters.js:112-366`; misma lógica que 3.1.973) [L; probado]: lista blanca
    de etiquetas y atributos en un documento inerte, en dos pasadas. Quita los atributos `on*`; en los enlaces deja
    `http`, `https`, `mailto`, `tel` y `blob:` del mismo origen; `src` solo local o `data:image`, y las imágenes
    externas pasan por `/pns_ai_mcp/remote_image`; en `style` quita `url()` externos y las funciones que cargan
    recursos; descarta `script`, `iframe`, `math`, `template`, `use`, `foreignObject` y `animate`; a `_blank` le
    añade `rel="noopener noreferrer"`. `escapeHtml` escapa las dos comillas y `ChatbooMarkdown` escapa todo `<`.
    Todo el contenido del asistente pasa por él (`chatboo_app.js:121`, `:2289`; los 9 `innerHTML` de la
    exportación). Deja pasar `id`, `class`, cualquier `data-*` y cualquier propiedad CSS sin `url()` (F1-9 a F1-11).
  - `data-*` y clases que el cliente lee del HTML del mensaje (lo que pueden disparar) [L]:
    - `id="pns_verif_<vid>"` con `data-confirm-token`: entra en `held` y la tarjeta real no se pinta (F1-9);
      `id="pns_choice_<id>"`, igual con la lista de elección (`chatboo_choice_list.js:17`);
    - `.o_ai_svg_card[data-ai-card]` de tipo `form`: con un clic, `/chatboo/open-form` con la acción, el modelo, el
      registro y los valores del JSON (F1-10); de tipo `link`, `clock` o `fact`: con `safeHref` y `escapeXml`;
    - `.o_ai_table_block[data-ai-dataset]`: gráficos y, con un clic, el lienzo de la sesión propia
      (`/chatboo/canvas/build`, `_own_session`); `data-msg-index` lo puede poner el propio mensaje (sesión propia);
    - `.o_ai_cell_copy[data-copy-text]`: copia el atributo, no el texto visible (F1-10);
    - `a.o_ai_namelink` en `table.o_ai_data_table`: al marcar la fila, el modelo y el id del enlace van con la
      siguiente orden (F1-11);
    - el diseño del tablero en `localStorage` (prefijo propio), el orden y la presentación: sin efecto fuera.
    - Ninguno llega a `location`, `eval` ni a una ruta elegida libremente.
  - Eventos SSE de `/chatboo/stream` [L]: `_sse_event` codifica con `json.dumps` (`chatboo.py:1132-1134`), así que el
    texto del modelo no puede fabricar una trama; los eventos estructurados los crea el motor en el servidor
    (`chatboo_async_request.py:459-476`). El cliente trata 7 (`chatboo_app.js:1606-1643`): `token` y `replace`
    (pintado saneado), `status` (`t-esc`), `meta` (ids de la sesión y del trabajo), `done` (metadatos; los
    archivos, con URL del servidor), `choice` y `verification` (tarjetas construidas con `textContent`). Los demás
    se ignoran.
- **`ir_ui_view_patch.py`:**
  - 519 líneas [L]. En la 17 están activos `_load_records`, `create`, `write`, `_compute_arch`, `_auto_convert_attrs`
    (paso 1) y `Base.get_view` (casos 3 a 6). Están muertos `<tree>`→`<list>`, `column_invisible`, el xpath de
    Ajustes de la 19 y la normalización de `view_mode` (7 condiciones, sección 2).
  - Hecha la revisión con el criterio de los PNS de los casos 3 a 6 (etapa F1.1; F1-5) (decisión 89).

## 5. Hallazgos F1

- **Antecedentes (decisión 62):** `git grep` en `docs/pendiente/` de `17.0-pns-ai` (`a8713b1`) y de `14.0`
  (`9cbb303`) de `name_get`, `view_mode`, `'list'`, `_primary_list_view_mode`, `pns_web_paths`, `@web/core/user`,
  `mcp_context_list`, `ai_provider.py`, `mcp_user.py` y `res_config_settings.py`:
  - ninguna coincidencia de `view_mode`, `'list'`, `_primary_list_view_mode`, `pns_web_paths`, `@web/core/user` ni
    `mcp_context_list` en ninguna de las dos ramas;
  - `name_get`: en `17.0-pns-ai`, solo `clasificacion_parches_pns_ai_17_3996.md:141` (ganchos de la caja A, otro
    tema). En `14.0`, `docs/pendiente/e2_propuesta_3879.md:950` ya sitúa el `name_get` de `ai_provider.py:79` en
    `ai.provider.model` (tabla de la caja A); no habla de su efecto. El resto, sobre el `name_get` del core;
  - `res_config_settings.py`: solo otras líneas y otros módulos.
  - No hay antecedente del síntoma de ninguno de los cuatro.
- **F1-1. `'list'` en una acción de la 17** (caso 11), menor (decisión 86) [L; core C y ref.]:
  - El hallazgo es la contradicción interna: `pns_ai_mcp/models/res_config_settings.py:159` devuelve `'list'` con
    `ODOO_VERSION >= 17`, frente al umbral 18 de `pns_base/utils/version_gates.py:16` y al comentario de
    `pns_base/models/ir_ui_view_patch.py:107` [L]. Afecta a `_action_open_module_agents` (`:196-202`).
  - Efecto descartado (F1.4): con `'list'` o con `'tree'`, al cliente le llega `'list'` y al servidor `'tree'`, y la
    acción abre igual (cadena de conversiones en el caso 11). Va con la regla de F1-3 y F1-4 (sección 7).
- **F1-2. `name_get` sin efecto en la 17** (caso 25), Baja, cosmética, confirmado (decisión 87) [L; core C; probado]:
  - `ai.provider.model` muestra el slug en lugar de «título (nombre)» (`ai_provider.py:80-87`): en el Many2one
    `model_id` del formulario del proveedor y en `placed_label` (caso 25). Lo ve quien lee el modelo
    (`base.group_user`, `pns_ai_mcp/security/ir.model.access.csv:11`) [L]. No permite nada más: solo cambia la etiqueta.
  - `ai.mcp.user`: su `name_get` está muerto, pero sin efecto (misma etiqueta; caso 25).
  - Probado: el `[HYPOTHESIS]` de `test_display_name_17.py` sale en rojo con
    `AssertionError: 'lab-slug' != 'Lab Title (lab-slug)'`; el test de `ai.mcp.user`, en verde.
  - La corrección, en el port (decisiones 61 y 87; sección 7).
- **F1-3. `@web/core/user` sin uso y comentario falso** (caso 22), menor [L; core C]:
  - `pns_web_paths.js:44-62` define un módulo que nadie importa; la L11 dice que la 17 trata como módulo todo
    `static/src`, y la 17.0 solo trata así lo que lleva `@odoo-module`. Confirmado por lectura; sin efecto conocido.
- **F1-4. `mcp_context_list.css` repetido**, menor [L]:
  - Aparece dos veces en `assets` de `pns_ai_mcp/__manifest__.py` (web.assets_backend). Sin efecto conocido.
- **F1-5. El convertidor de `attrs` trabaja sobre texto** (caso 3), menor [L; C-ej] (decisión 66):
  - `_auto_convert_attrs` (`pns_base/models/ir_ui_view_patch.py:409-413`) busca con expresiones regulares en el
    texto del arch, no en sus atributos XML. Con casos sintéticos [C-ej]:
    - reescribe `attrs="{…}"` también dentro de un texto (un `<p>`), sin aviso;
    - con un espacio inicial (`attrs=" {…}"`) no coincide ni da ERROR; después lo rechaza el core;
    - un atributo fijo y un `attrs` con la misma clave dan un atributo repetido y un arch que no se puede leer;
    - `<attribute name="attrs">{}</attribute>` se queda igual y lo rechaza el core. Y en la 14 un
      `<attribute name="attrs">` sustituía el diccionario entero; convertido, solo las claves que trae [L].
  - Quién lo alcanza: XML `pns_*` futuro, o un administrador que escribe vistas (`base.group_system`). Hoy, 0 casos
    en las 250 `attrs` (caso 3); todo, salvo lo del texto, acaba en un error visible al instalar.
  - Gravedad: Baja, sin seguridad: no hay inyección, porque solo `base.group_system` escribe vistas y el escape no
    deja salir del atributo.
  - Antecedentes: `git grep` en `docs/` de `14.0` (`9cbb303`) y de `17.0-pns-ai` (`ac624f9`) de `ir_ui_view_patch`,
    `_auto_convert_attrs`, `o_pns_view`, `fields_view_get` y «conversión de `attrs`». Solo aparece el arreglo del
    escape (`pns_base` 1.2.68; `comparacion_pns_ai_3-1-973.md:578` y `:864` de `14.0`), que es otro síntoma.
- **F1-6. `Access-Control-Allow-Origin` repetida en las respuestas de `/mcp*`** (caso 9), Baja, confirmado
  (decisión 73) [L; C; probado]:
  - El módulo pone la cabecera con el `Origin` de quien llama, o `*` sin `Origin` (`_mcp_cors_origin`,
    `pns_ai_mcp/controllers/main.py:327-331`; `_mcp_json_http_response`, `:333-340`, y las demás respuestas de
    `/mcp*`). El core añade la de `cors='*'` (`odoo/http.py:2055-2061`) [C] con `headers.extend`, que no sustituye
    (`_inject_future_response`, `:1804-1806`, ref.; mismo sha256 que el contenedor).
  - Probado: el test 4 de `test_routes_17.py` (`[HYPOTHESIS]`) sale en rojo con
    `Lists differ: ['https://allowed.lab-3996.test', '*'] != ['https://allowed.lab-3996.test']`.
  - Quién lo nota: un cliente MCP de navegador desde un origen permitido (`pns_ai_mcp.mcp_allowed_origins` o
    `web.base.url`). El navegador rechaza los dos valores y no deja leer la respuesta, aunque la petición ya se ha
    ejecutado. Los clientes de escritorio no envían `Origin` ni miran CORS.
  - Gravedad: Baja, sin seguridad: la respuesta queda más restringida y no hay `Access-Control-Allow-Credentials`.
  - Antecedentes: `git grep` en `docs/` de `14.0` (`9cbb303`) y de `17.0-pns-ai` (`81250fc`) de
    `_inject_future_response`, `headers.extend`, «dos cabeceras» y «dos valores»: nada del mismo síntoma. PNS-28
    (validar el `Origin`) y el preflight de la 14 (`analisis_pns_ai_mcp_4_servidor_mcp.md` §2.2, de `14.0`) son
    otros síntomas.
- **F1-7. `/chatboo/providers` vuelve a listar todos los proveedores activos** (decisión 77), Baja, regresión de
  PNS-71 [L]:
  - `list_providers` (`pns_ai_chatboo/controllers/chatboo.py:751-784`) llama a
    `get_providers_for_agent(agent_code, need='conversation')`. Si el agente no tiene cadena, ese método devuelve
    todos los proveedores activos, leídos con `sudo` (`pns_ai_mcp/models/ai_execution_engine.py:237-239`; igual en
    3.1.973). En 3.1.973 la ruta solo usaba los failovers del agente y, sin cadena, devolvía una lista vacía.
  - Devuelve por proveedor (`_serialize_provider`, `chatboo.py:1063-1080`, igual que en 3.1.973): id, nombre,
    protocolo, modelo, alias y etiqueta; el host solo si no hay alias ni nombre (`_provider_host`, `:1048-1061`).
    Sin claves ni endpoint.
  - Quién lo alcanza: los usuarios con acceso al Chatboo (grupo conversacional y clave MCP). Qué permite: ver la
    infraestructura de IA configurada (nombres, protocolos y modelos), lo que PNS-71 pedía no exponer.
  - Antecedente: PNS-71 (Baja, verificado en código; corregido en 3.1.782), «`/chatboo/providers` lista con
    `sudo` todos los proveedores si el agente no tiene cadena» (`informe_fabricante_pns_ai.md:109`, `:1230`;
    `informe_3973/estado_hallazgos_3973.md:135`, «no revisado en 3.1.973»; de `14.0`).
- **F1-8. `pns_safe_plan` recarga la página aunque ya no estés en Autorizaciones** (caso 23), Baja, verificado en
  código (decisión 82) [L; core C y ref.]:
  - `_bindSafePlanBus` (`pns_ai_mcp/static/src/js/safe_operation_action_buttons.js:35-43`) se suscribe a
    `pns_safe_plan` en cada `setup` de un `ListController` o `FormController` de `ai.safe.operation`, y el
    `bus_service` de la 17 no tiene `unsubscribe` (`bus_service.js:232`) [C]. El controlador viejo sigue cumpliendo
    `_isSafePlanView` (`:17-22`), así que cada aviso llama a `doAction({tag: 'reload'})` (`:24-33`) [L]: una recarga
    completa del cliente web estés donde estés, una vez por cada suscripción.
  - Quién lo alcanza: cualquier usuario cuyo agente proponga un plan, y el cron de caducidad. El aviso va al dueño
    y a todos los AI Administrators (caso 20); la recarga, a quien haya abierto Autorizaciones en esa pestaña.
  - Qué permite: un formulario a medias se guarda solo (`urgentSave`,
    `addons/web/static/src/views/form/form_controller.js:383-388`, ref.) o el navegador pregunta si quiere salir.
    Integridad de los datos (una edición a medias guardada), no seguridad.
  - Archivo nuevo en la 17: en 3.1.973 era `safe_operation_tree_v14.js`, sobre el bus antiguo (`on(…, this, …)`);
    que allí se quitara al destruir el widget es inferido, no comprobado (el core 14 no está en las referencias).
  - Reproducción manual (decisión 82): abrir Autorizaciones, ir a otro menú, empezar a editar un formulario, que
    otro usuario cree un plan y ver la recarga. Va al staging de la fase 3 (sección 7).
  - Antecedentes: `git grep` en `docs/` de `14.0` de `bus.bus`, `_sendone`, `pns_safe_plan`, `pns_key_pin`,
    `page_shared`, `bus_service`, `unsubscribe`, `_notify_safe_plan_hosts` y `key_pin_desk`: nada del mismo
    síntoma. Relacionado: PNS-31 (los oyentes globales de `key_pin_desk_v14.js`,
    `informe_fabricante_pns_ai_2.md:546-553` de `14.0`).
- **F1-9. El HTML del asistente puede ocultar la tarjeta de confirmación y ponerse encima**, Media provisional
  (decisión 98) [L; probado en parte]:
  - `sanitizeHtml` deja pasar `id`, `data-*` y `style` sin filtrar propiedades, salvo `url()` y las funciones que
    cargan recursos (`pns_ai_chatboo/static/src/js/chatboo_formatters.js:132-142`, `:195-212`).
  - `_showVerificationUI` busca la tarjeta por `id` (`chatboo_app.js:1969-1974`): si ya hay un elemento
    `pns_verif_<vid>`, no pinta la real y escribe el token en ese elemento. `_heldCardIds` (`:1864-1873`) manda al
    servidor como `held` los `pns_verif_*` con `data-confirm-token`, y el servidor no genera token para ellos
    (`pending_card_payloads`, `pns_ai_mcp/models/safe_operation.py`): al restaurar, la real tampoco se pinta. Igual con
    `pns_choice_` (`chatboo_choice_list.js:17`).
  - El modelo tiene el `verification_id`: `safe_plan_request` se lo devuelve
    (`pns_ai_mcp/controllers/safe_plan.py:502-517`) y es secuencial por verbo, del tipo `WRIT0042`
    (`safe_operation.py:438-456`).
  - Superposición, por lectura y sin probar: la tarjeta real va fija abajo a la derecha (`chatboo_app.js:1982`);
    `position:fixed`, `z-index`, `opacity` y `pointer-events` pasan el saneador, y ningún contenedor normal del
    mensaje tiene `transform` (CSS del módulo). Una capa del mensaje podría tapar el texto de la tarjeta real sin
    captar el clic, y el usuario confirmaría creyendo que cancela.
  - Quién lo alcanza: quien consiga meter texto en lo que lee el modelo (un registro, una página de `fetch_url`); lo
    ve el usuario de esa sesión. Qué permite: ocultar la confirmación (la operación sigue pendiente y se puede
    confirmar en Autorizaciones), suplantar la tarjeta y, con la superposición, una escritura con los permisos de la
    víctima por su propio clic. No ejecuta código ni da secretos.
  - Probado: T2b (`test_sanitizer_17.py`) en rojo; `[id^="pns_verif_"]` y `[id^="pns_choice_"]` quedan en la salida
    (sección 6). La ocultación y la superposición, a mano en el staging de la fase 3 (decisión 96).
  - Gravedad: Media provisional; baja a Baja si en el staging el `fixed` no sale de la burbuja (decisión 98).
  - Antecedentes: `git grep` en `docs/` de `14.0` y de `17.0-pns-ai` de `clobber`, `getElementById`, `pns_verif_`,
    `pns_choice_`, `position: fixed`, `pointer-events`, `clickjack`, `held`, `_heldCardIds` y `confirmToken`: nada
    del mismo síntoma; `held` solo se analizó por carreras y pestañas (`plan_correccion_pns_ai_3973.md:601-612`, de
    `14.0`). Relacionado: PNS-54. También en 3.1.973 (`chatboo_component_v2.js:2190-2200`, `:2311`; decisión 91).
- **F1-10. El HTML del asistente puede imitar los mandos del chat**, Baja (decisión 99) [L; probado en parte]:
  - El saneador deja `class` y `data-*`, y el cliente no distingue el HTML del servidor del del modelo. Con un clic:
    - `.o_ai_svg_card[data-ai-card]` de tipo `form` abre un formulario con la acción, el modelo, el registro y los
      valores que elija el modelo (`chatboo_svg_cards.js:323-350` → `chatboo_app.js:2836-2866`). El servidor usa los
      permisos del usuario, sin `sudo`; solo acepta `ir.actions.act_window`, pide `write` para editar y filtra los
      campos visibles y editables; nada se guarda sin «Guardar» (`pns_ai_chatboo/utils/form_draft.py`, igual que
      3.1.973);
    - `.o_ai_cell_copy` copia `data-copy-text`, no el texto visible (`chatboo_charts.js:3510-3535`).
  - Quién lo alcanza: como F1-9. Qué permite: ingeniería social (un formulario propuesto, otro texto en el
    portapapeles); sin escalada, sin secretos y sin escritura sin el «Guardar» del usuario.
  - Probado: T2b en rojo; `.o_ai_svg_card[data-ai-card]` y `.o_ai_cell_copy` quedan en la salida.
  - Antecedentes: `git grep` de `data-copy-text`, «portapapeles», `form_draft`, `open-form` y `kind=form`: nada
    igual. Relacionado: PNS-75 (copia TSV sin neutralizar fórmulas; `informe_fabricante_pns_ai.md:113`, `:1234`, de
    `14.0`). También en 3.1.973.
- **F1-11. Las filas marcadas dejan al modelo elegir el sujeto de la siguiente orden**, Media provisional
  (decisión 104) [L; probado]:
  - Al marcar una fila, el cliente toma el modelo y el id del enlace `a.o_ai_namelink` y la etiqueta de su texto
    (`chatboo_row_marks.js:25-41`) y los manda con la siguiente orden (`chatboo_turn.js:58-61`). El servidor los
    guarda (`pns_ai_chatboo/controllers/chatboo.py:836` → `remember_marks`, `chatboo_session.py:1450-1459`);
    `clean_marks` solo comprueba el tipo (`pns_ai_mcp/utils/record_marks.py:35-62`), no la existencia, el acceso ni
    la coincidencia con la fila visible. El trabajo añade al mensaje `MARKS_SENTENCE`, que pide usar esos ids como
    sujeto (`chatboo_async_request.py:284-291`; `record_marks.py:19-23`).
  - Qué permite: una fila que muestra un nombre y apunta a otro registro. Si el usuario la marca y da una orden, el
    motor recibe como sujeto el registro que eligió el modelo, y la etiqueta (80 caracteres) entra como texto del
    usuario.
  - Lo que lo limita [L]:
    - las lecturas van con los permisos del usuario;
    - ningún plan de confianza escribe en Odoo sin tarjeta: solo se confirman solos `fetch_url` a hosts de
      confianza y `api_call` a servidores `trusted` (`pns_ai_mcp/controllers/safe_plan_describe.py:15-56`; un paso
      CRUD da `False`, `:55`), que configuran los AI Administrators (`ir.model.access.csv:48-49`);
    - la tarjeta muestra el nombre real del modelo y el `display_name` real de los destinos, hasta 5 ids y 3 pasos
      (`safe_plan_describe.py:184-198`, `:335-367`); no el id. El título sí viene del modelo.
  - Quién lo alcanza: como F1-9, con el clic y la orden del usuario. Gravedad: Media provisional; con la tarjeta,
    el engaño necesita que el usuario no se fije o un destino con el mismo nombre; con F1-9, el plan se puede tapar.
  - Probado: T3 (`test_marks_17.py`) en rojo: `remember_marks` conserva la marca a un `ir.config_parameter` que el
    usuario no puede leer y la de un id que no existe; T2b: `a.o_ai_namelink` queda en la salida.
  - Antecedentes: `git grep` de `marks_sentence`, `record_marks`, `marked_refs`, `remember_marks`, `row_marks`,
    «filas marcadas» y `ChatbooRowMarks`: solo referencias funcionales (`analisis_bloqueo_chatboo_session.md:51`,
    `:198`; `cambios_pns_ai_3-1-782.md:116`; `manual_pns_ai_3973.md:377`; de `14.0`). `record_marks.py` y
    `chatboo_row_marks.js`, iguales en 3.1.973.
- **F1-12. La tarjeta de un plan muestra nombres de registros que el usuario no puede leer**, Baja (decisión 107)
  [L]:
  - `_names_for` lee el `display_name` con `sudo` (`pns_ai_mcp/controllers/safe_plan_describe.py:82-91`), y
    `describe_safe_plan` lo usa para los destinos de un paso (`_step_targets`, `:195`), el origen de una copia
    (`:217`) y los Many2one y x2many de los valores (`_describe_value`, `:124`, `:126`, `:142`). La descripción
    también vuelve al modelo en el resultado de `safe_plan_request` (`safe_plan.py:502-506`).
  - Quién lo alcanza: cualquier usuario del Chatboo cuyo modelo proponga un plan con ids que el usuario no puede leer.
    Qué permite: ver el nombre de esos registros, más allá del ACL y de las reglas; solo el nombre. La ejecución
    falla después con los permisos del usuario.
  - Antecedentes: en 3.1.486, `_names_for` «no se invoca desde `describe_safe_plan`… Sin fuga efectiva hoy»
    (`analisis_pns_ai_mcp_5_caja_b.md:191-192`, de `14.0`); en 3.1.973 ya se invoca. Otro punto: la D-5 de
    `correcciones_pns_ai_entrega2.md:898` («no revela nombres en `sudo`»). Misma familia que el core
    (`Many2one.convert_to_read` con `value.sudo().display_name`, `propuesta_fase3_3973.md:1737`).
    `safe_plan_describe.py` es idéntico a 3.1.973 (mismo sha256).
- **Causa común de F1-9, F1-10 y F1-11** (decisiones 99 y 104): el saneador deja pasar `id`, `class` y `data-*`, y el
  cliente no distingue el HTML que escribe el servidor (tablas, tarjetas de las skills) del que escribe el modelo; en
  F1-11, además, el servidor acepta lo que el cliente lee de ese HTML sin comprobarlo.
- **Observación, sin número: `unsubscribe` muerto en `chatboo_app.js`** (caso 23, decisión 85), menor [L; core C]:
  - `pns_ai_chatboo/static/src/js/chatboo_app.js:469-474` solo se da de baja si existe `busService.unsubscribe`,
    que la 17 no tiene (`bus_service.js:232`) [C]: las suscripciones de `:467-468` no se quitan.
  - Sin efecto: `ChatbooApp` se monta una sola vez (`chatMounted` no vuelve a `false`, `chatboo_overlay.js:94`,
    `:121-122`) [L]. Va con la regla de los menores (sección 7).
- **Observación, sin número: `name_get()` directo en `record_label.py`** (caso 25, decisión 88), menor [L; core C y
  ref.]:
  - `where_it_is` (`pns_ai_mcp/utils/record_label.py:35`) llama a `rec.with_context(show_address=True).name_get()`.
    En un modelo sin `name_get` propio entra en el del core: funciona (el `display_name` de `res.partner` respeta
    `show_address`, `odoo/addons/base/models/res_partner.py:893-897` [C]), pero avisa con un `DeprecationWarning`
    (`odoo/models.py:1694` [C]), que el log muestra una vez por proceso (`odoo/netsvc.py:190`, ref.).
  - En `ai.provider.model` llama a su `name_get` propio: hasta corregir F1-2, `where_it_is` recibe «Título (slug)»
    y `display_name`, el slug. Como solo usa las líneas siguientes a la primera (`:39`), aquí devuelve vacío [L].
  - Antecedentes: `git grep` en `docs/` de `14.0` y de `17.0-pns-ai` de `record_label`, `where_it_is` y
    `DeprecationWarning`: nada del mismo síntoma. Misma familia: el `DeprecationWarning` de `clear_cache`,
    observación del fabricante sin parche (`clasificacion_parches_pns_ai_17_3996.md:358-360`).
  - Va con la regla de los menores (sección 7).
- **Nota para PNS-84, sin número** (decisión 84) [L; core C]:
  - El aviso `pns_key_pin` lleva el PIN, el correo y el login (`pns_ai_mcp/models/key_pin_desk.py:147-154`), y la
    fila queda en `bus_bus` hasta la siguiente ejecución del autovacuum: `_gc_messages` lleva `@api.autovacuum` y
    borra las filas de más de 100 s (`addons/bus/models/bus.py:96-99`, `TIMEOUT` en `:26`), y el cron
    `base.autovacuum_job` corre una vez al día (`odoo/addons/base/data/ir_cron_data.xml:3-12`) [C]. Como máximo,
    un día y 100 s si el cron es puntual; más si se retrasa.
  - Solo se lee con `sudo` o con acceso a la BD: la ACL de `bus.bus` es `0,0,0,0` sin grupo [C].
  - El PIN y la clave en claro ya son PNS-84 (Media; Seges asume el riesgo; `informe_fabricante_pns_ai_3973.md:457-461`
    de `14.0`).
- **Nota para PNS-84, sin número: la lista de claves sobrevive al cierre de sesión** (decisiones 84 y 92) [L]:
  - `key_pin_desk.js` guarda en el `sessionStorage` de la pestaña, en claro, las claves por correo, los PIN y un
    token (`pns_ai_mcp/static/src/js/key_pin_desk.js:16-67`). Solo la borra «Clear» (`stopDesk`, `:331-339`);
    `pagehide` solo avisa al servidor (`:500-511`). Tras cerrar sesión, si otro AI Administrator entra en la misma
    pestaña, la mesa se abre con esa lista (`:596-597`). Igual en `key_pin_desk_v14.js:486-495` de 3.1.973.
  - La lee cualquier JS del mismo origen. La rama del JS que entrega una clave por correo o login, sin PIN, no tiene
    quien la active: el servidor solo crea peticiones con PIN (`pns_ai_mcp/models/mcp_user.py:806` → `_collect_pin`).
  - Ya es PNS-84 («no conservar la lista de claves en el navegador más allá de lo imprescindible»,
    `informe_seguimiento_fabricante_pns_ai.md:509-530` de `14.0`). Comprobación manual, al staging (sección 7).
- **Observaciones de F1.5, sin número** [L]:
  - `esc` de reserva sin comillas en `chatboo_app.js:2338-2341`: solo actúa si falta `ChatbooContextStats`, cuyo
    `esc` sí escapa `"` (`chatboo_context_stats.js:16-22`); acaba en un `title="…"` del modal de estadísticas
    (`chatboo_app.js:2443`) con la pregunta del propio usuario. Antecedente: X10 de
    `analisis_pns_ai_chatboo_2_componente.md:266` de `14.0` (otra función, ya corregida);
  - `localStorage` sin separar por usuario: `chatboo_provider_id` (`chatboo_app.js:743-786`), `chatboo_unread`
    (`chatboo_systray.js:39`, `:235`, `:248`; `chatboo_overlay.js:81`), `chatboo.tts.enabled` (`chatboo_tts.js:18`)
    y el diseño de los tableros (`chatboo_dashboard.js:17-45`) pasan al siguiente usuario del mismo navegador. Sin
    datos de negocio. Antecedente: inventariados, sin este punto (`analisis_pns_ai_chatboo_2_componente.md:69-73`
    de `14.0`);
  - X14 sigue: `t-att-href` sin filtro de esquema en los chips (`chatboo_app.xml:126`, `:174`, `:186`). Hoy solo le
    llegan datos de la sesión propia (PNS-53) o URL del servidor: `content_download_url` de un adjunto
    (`pns_ai_mcp/utils/session_download.py:447`) o `'#'` (`artifact_export.py:247`) (lectura de la decisión 101).
    Antecedente: X14 de `analisis_pns_ai_chatboo_2_componente.md:270` de `14.0`;
  - chips sin adjunto sin filtro: `_claim_turn_file_chips` (`pns_ai_chatboo/models/chatboo_session.py:470-502`)
    conserva sin tocar un chip cuya URL no apunta a un adjunto. Hoy solo son `'#'` o exportaciones pendientes; si
    otro emisor metiera una URL libre, llegaría al `t-att-href` sin filtro. Antecedente, otro síntoma: PNS-82, el
    filtro de dueño y creador de los adjuntos en ese método (`correcciones_pns_ai_entrega2.md:227`, de `14.0`); de
    la URL de un chip sin adjunto, nada.
- **Caso 6, sin número:** el coste de `Base.get_view` ya lo cubre PNS-42/PB-2, «parche global nuevo y menor» en el
  servidor (`comparacion_pns_ai_3-1-879.md:616` y `:805`; `estado_hallazgos_3879.md:352`; de `14.0`).

## 6. Etapas

Cada etapa tiene su fase 1 (lectura y propuesta) y su fase 2 (escritura); los tests se ejecutan antes en el
laboratorio (decisión 64). Las etapas tienen sus tests escritos y ejecutados en `seges_pruebas_3996`, con su copia
en `docs/pendiente/lab_3996/`; el detalle está en el «Hecha» de cada una.

- **F1.1. `ir_ui_view_patch.py` (casos 3 a 6):**
  - Leer: `ir_ui_view_patch.py` con el criterio de los PNS; en el core, `_compute_arch` (`ir_ui_view.py:220`), la
    validación de `attrs` (`:394`) y `get_view` (`:2635`).
  - Test (`test_view_patch_17`): el convertidor con valores difíciles (`}`, `<`, `&`, comillas); ninguna vista `pns_*`
    con `attrs=` en `arch_db`; un `write` sobre una vista ajena cuyo modelo contiene `ai.` no se toca; `get_view` de
    un modelo ajeno sin `o_pns_view`.
  - Necesita: la BD del laboratorio con los tres módulos.
  - **Hecha (24/11/2026):**
    - `seges_pruebas_3996/tests/test_view_patch_17.py`, clase `TestViewPatch17`: cinco tests `[CHECK]`, sin
      `[HYPOTHESIS]` (decisiones 68 y 69), en el laboratorio y en su copia de `docs/pendiente/lab_3996/` (mismo
      `sha256sum`). El test del `write` se ajustó a lo leído: una vista ajena con la pista `ai.` sí se convierte.
    - Los 5, en verde; el de `get_view` mide una diferencia de exactamente 1 consulta.
    - Laboratorio: `odoo-dev 17 tests seges_pruebas_3996` (BD temporal `test_lab_pns_ai_3996_17`, que no queda al
      terminar): `13 failed, 0 error(s) of 35 tests`; los 13 fallos son los de antes. Log
      `tests-20261124-110046.log`.
    - Resultado: casos 3 a 6 correctos (sección 3) y F1-5 (sección 5).
- **F1.2. Rutas JSON y `/mcp` (caso 9 y las 59 rutas):**
  - Leer: `odoo/http.py:2038-2214` (despacho, compatibilidad, CSRF); el inventario de las 59 rutas, empezando por las
    14 `csrf=False` de `main.py`.
  - Test: `HttpCase` con un POST `application/json` a `/mcp` sin clave, que debe dar un error MCP, no un 400 ni un
    error de CSRF; y una ruta `json` que falla, con el formato de error esperado.
  - Necesita: `HttpCase` en el laboratorio.
  - **Hecha (24/11/2026):**
    - `seges_pruebas_3996/tests/test_routes_17.py`, clase `TestRoutes17` (`HttpCase`), nueve tests, en el
      laboratorio y en su copia de `docs/pendiente/lab_3996/` (mismo `sha256sum`):
      1. POST JSON a `/mcp` sin clave: 401, «API key required» y el `id` del cuerpo;
      2. con una clave aleatoria: 401, «Invalid API key»;
      3. con una clave creada en el test para un usuario con el grupo conversacional, `tools/list` (sin red ni
         sesión SSE; decisión 75): 200 y una lista de herramientas;
      4. `[HYPOTHESIS]` (F1-6): una sola `Access-Control-Allow-Origin` con un `Origin` permitido;
      5. `Origin` ajeno: 403, «Origin not allowed»;
      6. `OPTIONS /mcp`: 204 del core, con su `Access-Control-Allow-Headers` fijo;
      7. ruta `json` que falla (`/chatboo/sessions/load` sin `session_id`): HTTP 200, código 200, «Odoo Server
         Error», `builtins.TypeError` y `debug`;
      8. POST `text/plain` a `/pns_ai_mcp/verification/pending`: 400 «Request inferred type is compatible with…»;
      9. POST sin `csrf_token` a `/pns_ai_mcp/key_pin/stop` y a `/chatboo/stream`: 400 «Session expired (invalid
         CSRF token)».
    - Ocho en verde y el 4 en rojo (F1-6 confirmado). Ningún test se corrigió tras la ejecución.
    - Laboratorio: `odoo-dev 17 tests seges_pruebas_3996` (BD temporal `test_lab_pns_ai_3996_17`, que no queda al
      terminar): `14 failed, 0 error(s) of 44 tests`; los 13 de antes y el test 4. Log `tests-20261124-112619.log`.
    - Resultado: caso 9 correcto, probado (sección 3); F1-6 confirmado y F1-7 (sección 5).
- **F1.3. Bus del Chatboo (casos 20 y 23):**
  - Leer: el `bus_service` de la 17.0 y los dos lectores del cliente.
  - Test: los 6 emisores del caso 20, con las filas de `bus.bus` (canal y mensaje) en la misma transacción. Sin test
    de navegador (decisión 83): necesitaría un commit real para el `NOTIFY`.
  - **Hecha (24/11/2026):**
    - `seges_pruebas_3996/tests/test_bus_17.py`, clase `TestBus17` (`TransactionCase`), seis tests `[CHECK]`, en el
      laboratorio y en su copia de `docs/pendiente/lab_3996/` (mismo `sha256sum`). Cada test ejecuta
      `cr.precommit.run()` (como `addons/mail/tests/common.py:1254`) y lee las filas creadas tras una marca,
      filtradas por canal y tipo:
      1. `notify_files_updated`: una fila al partner del dueño de la sesión, `message_received` y `session_id`;
      2. `_chatboo_notify_skills_changed` con el usuario U: una sola fila, la de U;
      3. página compartida: una fila al lector nuevo y ninguna al dueño; claves exactas y `url` relativa;
      4. `_notify('error')` de un trabajo: una fila al dueño con `is_error`;
      5. `_notify_safe_plan_hosts`: al dueño y a los AI Administrators, no a un tercero;
      6. `notify_changed` de la mesa del PIN: a los AI Administrators (y a quien llama), no a un tercero.
    - Los 6, en verde. Arreglo del propio test: el 5 salió `[SETUP]` en la primera ejecución porque no pasaba
      `expires_at` (NOT NULL en la tabla), que el módulo siempre pasa (`safe_operation.py:520-535`); no cambia lo
      que comprueba.
    - Laboratorio: `odoo-dev 17 tests seges_pruebas_3996` (BD temporal `test_lab_pns_ai_3996_17`, que no queda al
      terminar): `14 failed, 0 error(s) of 50 tests`; los 14 de antes. Log `tests-20261124-115249.log`.
    - Resultado: caso 20 correcto, probado; caso 23 correcto por lectura (sección 3); F1-8, la observación del
      `unsubscribe` y la nota para PNS-84 (sección 5).
- **F1.4. Lecturas sueltas (casos 5, 11, 15 y 25):**
  - Leer: `ir_ui_view.py:220` (caso 5); `action_service` y `view_service` de la 17.0 (caso 11); `Transaction.clear`
    (caso 15); `odoo/models.py:1678` (caso 25).
  - Test solo si la lectura no basta: abrir la acción de Ajustes en el navegador (caso 11); `display_name` de
    `ai.provider.model` y `ai.mcp.user` con etiqueta `[HYPOTHESIS]` (caso 25).
  - **Hecha (24/11/2026):**
    - Caso 5: ya se hizo en F1.1. Casos 11 y 15: por lectura, sin test (decisión 90); el core, en una ejecución sin
      red (marca [C]) y lo que no capturó, en la referencia (ref.).
    - Caso 25: `seges_pruebas_3996/tests/test_display_name_17.py`, clase `TestDisplayName17` (`TransactionCase`),
      dos tests, en el laboratorio y en su copia de `docs/pendiente/lab_3996/` (mismo `sha256sum`):
      1. `[HYPOTHESIS]` (F1-2): `ai.provider.model` con `name='lab-slug'` y `title='Lab Title'` tiene
         `display_name == 'Lab Title (lab-slug)'`. En rojo: `AssertionError: 'lab-slug' != 'Lab Title (lab-slug)'`;
      2. el `display_name` del `ai.mcp.user` de un usuario creado en el test es `user.name`. En verde.
    - Ningún test se corrigió tras la ejecución.
    - Laboratorio: `odoo-dev 17 tests seges_pruebas_3996` (BD temporal `test_lab_pns_ai_3996_17`, que no queda al
      terminar): `15 failed, 0 error(s) of 52 tests`; los 14 de antes y el test 1. Log `tests-20261124-121539.log`.
    - Resultado: casos 11 y 15 correctos (sección 3); caso 25 distinto en `ai.provider.model`; F1-1 menor, F1-2
      confirmado y la observación de `record_label.py` (sección 5).
- **F1.5. JS por riesgo (decisión 60):**
  - Inventario con `git grep` de los puntos peligrosos en los 80 assets y en las librerías bajo demanda; revisión a
    mano de lo que salga, empezando por lo que pinta HTML (`chatboo_formatters.js`, `chatboo_markdown.js`,
    `sanitizeHtml`) y lo que llama al servidor (`key_pin_desk.js`, con su `csrf_token`).
  - Apuntado (decisión 84): la clave que guarda `key_pin_desk.js` en el navegador (lista de claves y PIN; responde
    con ella a `pns_key_pin`, `:193-218`).
  - **Hecha (24/11/2026):**
    - Lecturas: el inventario y el triaje (sección 4); a fondo, el camino del modelo al DOM, la lista de claves, los
      iframes, las librerías y los SVG; después, los `data-*` y los eventos SSE (decisión 97), el origen de las URL
      de los chips y de `clip_data` y las filas marcadas (decisión 101), y los planes de confianza y la tarjeta de un
      plan (decisión 105).
    - `seges_pruebas_3996/tests/test_sanitizer_17.py`, clase `TestSanitizer17` (`HttpCase`), y
      `test_marks_17.py`, clase `TestMarks17` (`TransactionCase`), en el laboratorio y en su copia de
      `docs/pendiente/lab_3996/` (mismo `sha256sum`). Los tests del navegador abren `/web` como admin con
      `browser_js` (como `TestWebClientStarts`) y llaman al `sanitizeHtml` de
      `odoo.loader.modules.get("@pns_ai_chatboo/js/chatboo_formatters")`; un `[SETUP]` comprueba antes que el
      módulo está cargado, que tiene la función y que conserva un `<b>t</b>`. Entradas sintéticas mínimas:
      1. T1 `[CHECK]`, en verde: `on*` → `<b>t</b>`; `javascript:` → `<a>t</a>`; `javascript:` en `<svg><a>` →
         `<svg><a><text>t</text></a></svg>`; una imagen externa → un `<img>` con
         `src="/pns_ai_mcp/remote_image?url=…"` dentro de un enlace con `rel="noopener noreferrer"`; un `url()`
         externo en `style` → `<span>t</span>`; `<math>` y `<template>` → solo el `<p>t</p>` que los acompaña;
      2. T2a `[CHECK]`, en verde, con 10 entradas: sanear otra vez no cambia nada y, en un nodo vivo, no queda
         ningún `on*` ni un `href` fuera de `http`, `https`, `mailto`, `tel` o `blob:` del mismo origen;
      3. T2b `[HYPOTHESIS]` (F1-9, F1-10 y F1-11 en el cliente), en rojo; quedan los cinco mandos:
         `[HYPOTHESIS] chat controls in the output: [id^="pns_verif_"] kept: … | [id^="pns_choice_"] kept: … |`
         `.o_ai_svg_card[data-ai-card] kept: … | .o_ai_cell_copy kept: … | a.o_ai_namelink kept: …`;
      4. T3 `[HYPOTHESIS]` (F1-11), en rojo, con `remember_marks` como el usuario (el punto de `chatboo.py:836`):
         `kept [('ir.config_parameter', 20), ('res.partner', 100075), ('res.partner', 75)] (unreadable`
         `ir.config_parameter#20, missing res.partner#100075)`; esperado, solo el partner que el usuario lee.
    - Ajustes de diseño, antes de ejecutar (no cambian lo que se comprueba): `sanitizeHtml` guarda su salida en
      caché, así que T2a sanea `salida + "<!---->"` (clave nueva, pasada real; el comentario se quita y se espera
      exactamente la salida); la imagen externa queda fuera de T2a, porque en un nodo vivo pediría
      `/pns_ai_mcp/remote_image` (T1 ya la cubre). Ningún test se corrigió tras la ejecución.
    - Laboratorio: `odoo-dev 17 tests seges_pruebas_3996` (BD temporal `test_lab_pns_ai_3996_17`, que no queda al
      terminar): `17 failed, 0 error(s) of 56 tests`; los 15 de antes, T2b y T3. Log `tests-20261124-131215.log`.
    - Resultado: F1-9 a F1-12, la nota para PNS-84 de la lista de claves y las observaciones de F1.5 (sección 5); lo
      que queda sin revisar, en la sección 1 (decisión 103). Con F1.5 terminan las etapas de la fase 1.

## 7. Lo que va al port

- **Caso 24** (parche 18, decisión 48): los ganchos «Odoo 17+» no existen y la caja A con uid 1 da `su` (localizado,
  no probado; decisión 48).
- **F1-2 (decisión 87):** corrección: un `_compute_display_name` con `@api.depends('title', 'name')` en
  `ai.provider.model`; su `name_get` se deja (código multiversión); en `ai.mcp.user`, nada. Con la corrección, el
  `[HYPOTHESIS]` de `test_display_name_17.py` pasa a verde.
- **F1-1 (menor, decisión 86):** con la regla de F1-3 y F1-4: solo se corrige si el port toca ese archivo.
- **`name_get()` directo de `utils/record_label.py:35` (decisión 88):** observación con la regla de los menores (la
  de F1-3 y F1-4): solo se corrige si el port toca ese archivo.
- **Caso 3:** todos los parches que tocan XML de vistas pasan por el convertidor; lo que salga de F1.1 vale para
  ellos.
- **F1-3 y F1-4 (menores):** solo se corrigen si el port toca esos archivos (convención del código heredado); si no,
  quedan como inventario.
- **F1-5 (menor):** con la regla de F1-3 y F1-4; además, los parches que toquen XML de vistas evitan sus formas
  (`attrs` en un texto, espacio inicial, atributo fijo repetido y `<attribute name="attrs">`).
- **F1-6 y F1-7 (decisión 78):** correcciones, no con la regla de los menores:
  - F1-6: una sola `Access-Control-Allow-Origin` en las respuestas de `/mcp*` (la del módulo, que valida el
    `Origin`); con la corrección, el test 4 de `test_routes_17.py` pasa a verde;
  - F1-7: `/chatboo/providers` sin la lista de todos los proveedores activos cuando el agente no tiene cadena, como
    pedía PNS-71.
- **F1-8 (decisión 82):** corrección, como F1-6 y F1-7: que `safe_operation_action_buttons.js` no deje suscripciones
  de controladores ya cerrados (o que no recargue si su vista ya no está abierta). La reproducción manual (abrir
  Autorizaciones, ir a otro menú, empezar a editar un formulario, que otro usuario cree un plan y ver la recarga) va
  a la lista de comprobaciones del staging de la fase 3.
- **F1-9, F1-10 y F1-11 (decisiones 98, 99 y 104):** correcciones, con una causa común (sección 5): el saneador deja
  pasar `id`, `class` y `data-*`, y el cliente no distingue el HTML del servidor del del modelo. El diseño se hace en
  el port; como punto de partida:
  - F1-9 y F1-10, en el cliente: que el contenido del asistente no pueda llevar los `id`, las clases ni los `data-*`
    que el cliente toma por mandos (o que los del servidor vayan marcados de una forma que el modelo no pueda
    imitar), que la tarjeta y la lista de elección no se busquen por `id` en todo el documento y que `style` quede
    limitado en ese contenido (al menos `position`, `z-index` y `pointer-events`). Con la corrección, T2b de
    `test_sanitizer_17.py` pasa a verde;
  - F1-11, en el servidor: que `remember_marks` descarte las marcas a registros que no existen o que el usuario no
    puede leer y, si se puede, las que no están en el conjunto de datos del turno (como `narrow_rows`). Con la
    corrección, T3 de `test_marks_17.py` pasa a verde; en el cliente, lo de F1-10 para `a.o_ai_namelink`.
- **F1-12 (decisión 107):** corrección, Baja: que `_names_for` lea los nombres con los permisos del usuario, sin
  `sudo`, y muestre el id cuando no pueda leerlo.
- **F1-9 a F1-12 también están en 3.1.973** (decisión 91): parchearlos en la 14 es una decisión aparte, fuera de esta
  fase.
- **Observaciones de F1.5** (sección 5): con la regla de los menores (la de F1-3 y F1-4): solo se corrigen si el port
  toca esos archivos. Si la corrección de F1-10 toca las plantillas de los chips, el `href` de X14 y el de los chips
  sin adjunto pasan a llevar filtro de esquema.
- **`unsubscribe` muerto de `chatboo_app.js:469-474` (decisión 85):** observación con la regla de los menores (la
  de F1-3 y F1-4): solo se corrige si el port toca ese archivo.
- **Observaciones para el port (decisiones 74 y 79), sin número; iguales en 3.1.973:**
  - el SSE de `/mcp/sse` y `/mcp/<agent_code>/sse` mete el mensaje del agente, que lleva el código de la URL, en el
    JSON sin escapar (`pns_ai_mcp/controllers/main.py:532-536`). La respuesta solo la recibe quien hace la
    petición. Antecedentes: ninguno; `git grep` en `docs/` de `14.0` de `bind_err`, `_bind_mcp_agent`, escapes en
    SSE y `agent_code` con «escap» o «inyec» (el SSE del Chatboo, `e3_hallazgo_p8ea_3879.md:129`, es otro punto);
  - `session_file` deja pasar siempre al creador del adjunto, aunque ya no pueda leer el registro del que cuelga
    (`pns_ai_mcp/controllers/session_file.py:21-36`) [L]. El core solo se fía del creador si el adjunto no tiene
    `res_id`; si lo tiene, mira el acceso al registro (`ir.attachment.check`,
    `odoo/addons/base/models/ir_attachment.py:473-485`, ref.). Antecedentes relacionados, no del mismo síntoma:
    PNS-21 (descargas con `auth='user'` y dueño, corregido; `comparacion_pns_ai_3-1-973.md:312`) y
    PNS-82 (`_may_read` entrega los adjuntos reclamados; `informe_seguimiento_fabricante_pns_ai.md:451-465`);
  - las rutas del Chatboo distintas de `check_health` devuelven `str(e)` en sus errores: 23 casos en 19 rutas
    (`pns_ai_chatboo/controllers/chatboo.py:228-744`), 5 de ellos de `UserError` (`:669`, `:685`, `:703`, `:727`,
    `:744`). Antecedentes: PNS-71 solo cubre `check_health` (`informe_fabricante_pns_ai.md:1230`); relacionado,
    PNS-40 (el error del driver, `comparacion_pns_ai_3-1-879.md:450-452`); de `14.0`.
- **Lista de comprobaciones del staging de la fase 3** (decisión 102), a mano, con datos de prueba:
  1. F1-8: abrir Autorizaciones, ir a otro menú, empezar a editar un formulario, que otro usuario cree un plan y ver
     si la página se recarga;
  2. F1-9: con un mensaje del asistente que lleve un elemento con el `id` de la tarjeta de un plan pendiente, ver si
     la tarjeta real deja de pintarse (en directo y al recargar) y si el plan se puede confirmar desde
     Autorizaciones; con un elemento de posición fija, ver si sale de la burbuja y queda sobre la tarjeta real. Si no
     sale, F1-9 baja a Baja (decisión 98);
  3. F1-11: con una tabla del asistente cuya fila muestre un registro y enlace otro, marcar la fila, dar una orden de
     escritura y ver qué registro aparece en la tarjeta y cuál se escribiría;
  4. PNS-84, lista de claves: cargarla, cerrar sesión, entrar con otro AI Administrator en la misma pestaña y ver si
     aparece «This tab is holding keys» y la mesa se abre sola;
  5. PNS-84, aviso en `bus_bus`: tras canjear un PIN, ver con una consulta de solo lectura que la fila del aviso
     `pns_key_pin` sigue en `bus_bus` hasta el autovacuum (sección 5).
- **Migración 14→17:** las vistas sin xml_id de los clientes que heredan de `pns_*` y los `arch_prev` con `attrs`,
  en `docs/migracion/pendiente_17.0.md` (inferido, no probado).
