# Fase 1 de `pns_ai` en la 17: código que solo se activa en la 15 o superior

- **Fecha:** 24/11/2026.
- **Rama y partida:** `17.0-pns-ai`, HEAD `a8713b1` (igual a `origin/17.0-pns-ai`), sin cambios locales. Módulos:
  `pns_base` 17.0.1.2.92, `pns_ai_mcp` 17.0.3.1.996 y `pns_ai_chatboo` 17.0.2.1.597 (R17).
- **Qué es la fase 1** (`docs/pendiente/plan_pns_ai_17.md`, L71-72): «analizar el código que solo se activa en la 15 o
  superior y que en la 14 no se revisó (`ir_ui_view_patch.py`, assets, rutas JSON, cliente de Chatboo), con el
  criterio de los PNS». La lista sale de la 14 (`docs/specs/analisis_pns_base.md` de `14.0`: §2.3, §10 y punto 9,
  «lógica muerta en 14 (`ir_ui_view_patch.py` completo)»).
- **Este documento:** mide el alcance (solo lectura) y propone las etapas. No hay ningún test escrito ni ejecutado.
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
- **Marcas:**
  - **[L]:** leído (el cuerpo del código o del documento).
  - **[Loc]:** localizado por búsqueda, sin leer el cuerpo.
  - **[C]:** comprobado en el contenedor de `odoo-dev:17-lab_pns_ai_3996` (core `17.0-20260908`,
    `/usr/lib/python3/dist-packages/odoo`) en una única ejecución, sin red ni volúmenes: búsqueda en las fuentes o
    `hasattr` tras importar `odoo` sin BD. Prueba que algo existe y dónde, no cómo se comporta.
  - **(ref.):** cita de `/opt/odoo-src/17.0/odoo` (`6a0efa7`), solo para lo que esa ejecución no capturó.
  - **probado:** ejecutado en el laboratorio. En esta fase solo hay pruebas indirectas (sección 1).
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
- **Puede quedar fuera:**
  - código de la 15 o superior sin condición y con un nombre que no está en la lista (por ejemplo, una firma que
    cambia de sentido sin cambiar de nombre);
  - el comportamiento en la 17 de las 59 rutas: solo están contadas;
  - el JS: solo está medido, no revisado;
  - el core 14 no está en las referencias: «no existe en la 14» se apoya en los comentarios del fabricante y en
    `analisis_pns_base.md`, no en una comprobación.
- **Cobertura (localizada por nombre en los tests; no se ejecutó nada):**
  - **directa, casi ninguna:**
    - tests del fabricante: `_get_env_for_operation` (`test_sandbox_live_handles.py`,
      `test_relaxaicode_sandbox_escapes_e2e.py`) y el `Content-Type: application/json` (`tests/_helpers.py`,
      `test_session_download.py`, `test_chatboo_perimeter.py`);
    - laboratorio: `test_review_views.py` (el `get_view` del asistente, parches 21 y 36) y `test_side_cursors.py`
      (`test_is_running`);
  - **indirecta (probado, sección 10 de la clasificación):**
    - la instalación de los tres módulos ejecuta la conversión de las 250 `attrs`, `post_init_hook` y `convert_file`;
    - `TestWebClientStarts.test_backend_starts_without_errors` (`pns_base`, en verde) carga el bundle completo,
      `pns_web_paths.js` incluido, sin errores de consola;
  - **sin cobertura:** casos 4, 5, 9, 11, 20 a 23 y 25 de la sección 3, y la desinstalación;
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
  (`chatboo_app.js:25-40`, `chatboo_systray.js:114`).
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
  - Clase: correcto según la instalación; pendiente la revisión con el criterio de los PNS (expresión regular no
    voraz `\{.*?\}`, escapado, lo que se deja sin convertir con un ERROR).
  - Cobertura: instalación (probado indirecto). Parche: ninguno; lo usan los parches 21 y 36 (`_inject_screen_arch`).
- **Caso 4. `write` por pistas:** `ir_ui_view_patch.py:348` [L].
  - Rama: convierte si el nombre o el modelo de la vista contienen una pista (`'pns'`, `'inherit.mcp'`, `'ai.'`,
    `'mcp.'`, `'relaxaicode'`), sin mirar el xml_id.
  - Clase: sin saber (falsos positivos de las pistas en vistas ajenas). Cobertura: ninguna. Parche: ninguno.
- **Caso 5. `_compute_arch`:** `ir_ui_view_patch.py:355-378` [L].
  - Rama: convierte el arch del archivo (`--dev=xml` o lectura de `arch_fs`).
  - Core: `odoo/addons/base/models/ir_ui_view.py:220` [C], cuerpo sin leer.
  - Clase: se resuelve leyendo el core. Cobertura: ninguna. Parche: ninguno.
- **Caso 6. `Base.get_view` sin condición:** `ir_ui_view_patch.py:507-519` [L].
  - Rama: añade la clase `o_pns_view` a las vistas `pns_*`; en cada `get_view` de cualquier modelo hace `browse` y lee
    `view.xml_id`, fuera de la caché de vistas.
  - Core: `odoo/addons/base/models/ir_ui_view.py:2635` [C]; devuelve una copia, `dict(self._get_view_cache(…))`
    (`:2660`, ref.).
  - Clase: correcto; revisión con el criterio de los PNS: coste por llamada. Cobertura: ninguna. Parche: ninguno.
- **Caso 7. `read_sums`:** `pns_ai_mcp/utils/compat.py:33` [L].
  - Rama: `_read_group(domain, [], ['<campo>:sum'])`. Core: `odoo/models.py:1857` [C].
  - Clase: correcto. Quién lo llama: sin buscar. Cobertura: ninguna. Parche: ninguno.
- **Caso 8. `invalidate_recordset`:** `pns_base/utils/compat.py:39`, `:81` [L].
  - Core: `BaseModel.invalidate_recordset` existe; `invalidate_cache`, no [C].
  - Clase: correcto. Cobertura: indirecta (muchos usos). Parche: ninguno.
- **Caso 9. `/mcp` sin `http_patch`:** `pns_base/utils/compat.py:28` → `pns_ai_mcp/http_patch.py:26` [L].
  - Rama: no hay parche; el POST con `Content-Type: application/json` a `/mcp` (rutas `type='http'`) lo despacha el
    core.
  - Core: `odoo/http.py:2098-2102` (`HttpDispatcher`, `is_compatible_with`), `:2162-2171` (`JsonRPCDispatcher`) [C,
    cuerpos sin leer].
  - Clase: sin saber (área de las rutas JSON). Cobertura: los tests del fabricante que envían `application/json`
    (`tests/_helpers.py:372`), sin comprobar qué ruta tocan. Parche: ninguno.
- **Caso 10. Assets de la 14:** `pns_ai_mcp/utils/compat.py:66` [L].
  - Rama: vuelve sin hacer nada; los assets entran por el manifiesto. Clase: correcto. Parche: ninguno.
- **Caso 11. `'list'` en una acción de Ajustes:** `pns_ai_mcp/models/res_config_settings.py:158-159`, usado en
  `:196` [L].
  - Rama: en la 17 devuelve `'list'` para `view_mode` (`'list,form'`) y para `views`.
  - Core: `VIEW_TYPES` (`odoo/addons/base/models/ir_actions.py:346-347`, ref.) solo tiene `'tree'`, pero solo valida
    los registros guardados de `ir.actions.act_window.view`; esta acción es un `dict` que va directo al cliente web,
    así que no prueba que `'list'` falle. En sentido contrario, `get_views` convierte `'list'` en `'tree'` antes de
    llamar a `get_view` (`odoo/addons/base/models/ir_ui_view.py:2475-2476`: `:2475` [C], comprobado en el contenedor
    en el punto 7 de la sección 11 de la clasificación; la conversión de `:2476`, ref.), lo que indica que el cliente
    17.0 trabaja con `'list'`.
  - Contradice `pns_base/utils/version_gates.py:16` (`TREE_TO_LIST_FROM = 18`) y el comentario de
    `ir_ui_view_patch.py:107` («Odoo 17 still uses view_mode 'tree'») [L].
  - Clase: sin saber (falta leer `action_service` y `view_service` de la 17.0). Cobertura: ninguna. Parche: ninguno.
    Hallazgo F1-1.
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
  - Core: `Cursor.rollback` llama a `self.clear()` (`odoo/sql_db.py:490-492`, ref.), que llama a
    `self.transaction.clear()` (`:140-143`, ref.); `Transaction.clear` sin localizar ni leer.
  - Clase: correcto si `Transaction.clear` invalida la caché (falta leerlo). Cobertura: ninguna. Parche: ninguno.
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
- **Caso 20. Avisos por el bus (servidor):** `pns_ai_chatboo/models/chatboo_session.py:523`,
  `models/chatboo_canvas_page.py:119`, `models/chatboo_async_request.py:1625`, `pns_ai_mcp/models/key_pin_desk.py:72`
  y `models/safe_operation.py:1753` [L].
  - Rama: `bus.bus._sendone(partner, tipo, payload)`.
  - Core: `addons/bus/models/bus.py:111` [C]; el cliente se suscribe al partner de la sesión
    (`addons/bus/models/ir_websocket.py:75-76`, ref.).
  - Clase: correcto en el servidor; la recepción, en el caso 23. Cobertura: ninguna.
  - Parche: 11, 25, 26, 29 y 38 (`chatboo_session.py`); 28 (`chatboo_canvas_page.py`); 34
    (`chatboo_async_request.py`); 18 y 38 (`key_pin_desk.py`); 16 y 38 (`safe_operation.py`).
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
- **Caso 23. Avisos por el bus (cliente):** `pns_ai_chatboo/static/src/js/chatboo_app.js:25-40` y
  `chatboo_systray.js:114` [L].
  - Rama: interpretan la notificación de la 17 (lista o `{type, payload}`).
  - Core: `bus_service` de la 17, no comprobado.
  - Clase: sin saber. Cobertura: ninguna. Parche: ninguno.
- **Caso 24. Ganchos «Odoo 17+» del guardián:** `pns_ai_mcp/models/sandbox_secret_read.py:100-113` [L].
  - Core: `_has_field_access` y `_check_field_access` no existen en la 17 [C]; protege el gancho de la 14
    (`:116-126`).
  - Clase: distinto. Ya registrado: clasificación, sección 11, punto 1, «Al margen» (decisión 48), junto con la caja
    A con uid 1, que da `su` (localizado, no probado; decisión 48). Parche: 18.
- **Caso 25. `name_get` (lo inverso, decisión 61):** `pns_ai_mcp/models/ai_provider.py:80` (de `ai.provider.model`,
  `:26-27`) y `models/mcp_user.py:536` (de `ai.mcp.user`, `_rec_name = 'user_id'`, `:71-73`) [L].
  - Rama: etiquetas «título (nombre)» y «nombre del usuario» / «No user»; ningún `_compute_display_name` en esos
    modelos [Loc].
  - Core: `name_get` obsoleto desde la 17.0 (`odoo/models.py:1694`, ref.); `display_name` se calcula con
    `_compute_display_name` (`:1678`, ref., cuerpo sin leer).
  - Clase: probablemente muerto en la 17; se resuelve leyendo `odoo/models.py:1678`. Cobertura: ninguna.
  - Parche: 33 (`ai_provider.py`). Hallazgo F1-2.

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
  - Falta: la revisión por riesgo (etapa F1.5).
- **Rutas:**
  - 59 `@http.route`: 34 en `pns_ai_chatboo/controllers/chatboo.py` y 25 en `pns_ai_mcp` (`main.py` 14,
    `verification_ui.py` 4, `key_pin.py` 3, `choice_ui.py` 2, `remote_image.py` 1, `session_file.py` 1).
  - Ocurrencias de `type=`: 34 `JSON_ROUTE_TYPE` (`'json'` en la 17) y 27 `'http'`. 14 `csrf=False`, todas en
    `pns_ai_mcp/controllers/main.py`.
  - Sin `http_patch` en la 17 (caso 9).
  - Falta: el inventario de las 59 (`auth=`, `type=`, `csrf=`, `methods=` y quién las alcanza), empezando por las 14
    `csrf=False` de `main.py` (etapa F1.2).
- **Cliente del Chatboo:**
  - Incluido en las 12.888 líneas de `pns_ai_chatboo`: de sus 28 assets, 16 son idénticos a 3.1.973; de sus 19 JS,
    6 son módulos `@odoo-module` y el resto, scripts sin esa marca (varios se declaran «shared owl1 / owl2»).
  - Enganche con el servidor: casos 20, 22 y 23.
  - Falta: la recepción por el bus (etapa F1.3) y la revisión por riesgo (etapa F1.5).
- **`ir_ui_view_patch.py`:**
  - 519 líneas [L]. En la 17 están activos `_load_records`, `create`, `write`, `_compute_arch`, `_auto_convert_attrs`
    (paso 1) y `Base.get_view` (casos 3 a 6). Están muertos `<tree>`→`<list>`, `column_invisible`, el xpath de
    Ajustes de la 19 y la normalización de `view_mode` (7 condiciones, sección 2).
  - Falta: la revisión con el criterio de los PNS de los casos 3 a 6 (etapa F1.1).

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
- **F1-1. `'list'` en una acción de la 17** (caso 11) [L]:
  - El hallazgo es la contradicción interna: `pns_ai_mcp/models/res_config_settings.py:159` devuelve `'list'` con
    `ODOO_VERSION >= 17`, frente al umbral 18 de `pns_base/utils/version_gates.py:16` y al comentario de
    `pns_base/models/ir_ui_view_patch.py:107` [L]. Afecta a `_action_open_module_agents` (`:196-202`).
  - El efecto, sin confirmar: el cliente 17.0 trabaja con `'list'` (`get_views`, caso 11), así que puede no fallar
    (etapa F1.4).
- **F1-2. `name_get` sin efecto en la 17** (caso 25) [L; core ref.]:
  - `ai.provider.model` y `ai.mcp.user` perderían sus etiquetas. Sin confirmar: falta leer `odoo/models.py:1678`
    (etapa F1.4). La corrección, en el port (decisión 61).
- **F1-3. `@web/core/user` sin uso y comentario falso** (caso 22), menor [L; core C]:
  - `pns_web_paths.js:44-62` define un módulo que nadie importa; la L11 dice que la 17 trata como módulo todo
    `static/src`, y la 17.0 solo trata así lo que lleva `@odoo-module`. Confirmado por lectura; sin efecto conocido.
- **F1-4. `mcp_context_list.css` repetido**, menor [L]:
  - Aparece dos veces en `assets` de `pns_ai_mcp/__manifest__.py` (web.assets_backend). Sin efecto conocido.

## 6. Etapas

Cada etapa tiene su fase 1 (lectura y propuesta) y su fase 2 (escritura); los tests se ejecutan antes en el
laboratorio (decisión 64). Los tests van como idea; no hay ninguno escrito.

- **F1.1. `ir_ui_view_patch.py` (casos 3 a 6):**
  - Leer: `ir_ui_view_patch.py` con el criterio de los PNS; en el core, `_compute_arch` (`ir_ui_view.py:220`), la
    validación de `attrs` (`:394`) y `get_view` (`:2635`).
  - Test (`test_view_patch_17`): el convertidor con valores difíciles (`}`, `<`, `&`, comillas); ninguna vista `pns_*`
    con `attrs=` en `arch_db`; un `write` sobre una vista ajena cuyo modelo contiene `ai.` no se toca; `get_view` de
    un modelo ajeno sin `o_pns_view`.
  - Necesita: la BD del laboratorio con los tres módulos.
- **F1.2. Rutas JSON y `/mcp` (caso 9 y las 59 rutas):**
  - Leer: `odoo/http.py:2038-2214` (despacho, compatibilidad, CSRF); el inventario de las 59 rutas, empezando por las
    14 `csrf=False` de `main.py`.
  - Test: `HttpCase` con un POST `application/json` a `/mcp` sin clave, que debe dar un error MCP, no un 400 ni un
    error de CSRF; y una ruta `json` que falla, con el formato de error esperado.
  - Necesita: `HttpCase` en el laboratorio.
- **F1.3. Bus del Chatboo (casos 20 y 23):**
  - Leer: el `bus_service` de la 17.0 y los dos lectores del cliente.
  - Test de navegador: `notify_files_updated` en el servidor y el cliente recibe `pns_chatboo_sync`.
  - Necesita: Chrome en la imagen del laboratorio (ya está, sección 10 de la clasificación).
- **F1.4. Lecturas sueltas (casos 5, 11, 15 y 25):**
  - Leer: `ir_ui_view.py:220` (caso 5); `action_service` y `view_service` de la 17.0 (caso 11); `Transaction.clear`
    (caso 15); `odoo/models.py:1678` (caso 25).
  - Test solo si la lectura no basta: abrir la acción de Ajustes en el navegador (caso 11); `display_name` de
    `ai.provider.model` y `ai.mcp.user` con etiqueta `[HYPOTHESIS]` (caso 25).
- **F1.5. JS por riesgo (decisión 60):**
  - Inventario con `git grep` de los puntos peligrosos en los 80 assets y en las librerías bajo demanda; revisión a
    mano de lo que salga, empezando por lo que pinta HTML (`chatboo_formatters.js`, `chatboo_markdown.js`,
    `sanitizeHtml`) y lo que llama al servidor (`key_pin_desk.js`, con su `csrf_token`).
  - Resultado: lo revisado, lo que queda sin revisar y los hallazgos `F1-n`.

## 7. Lo que va al port

- **Caso 24** (parche 18, decisión 48): los ganchos «Odoo 17+» no existen y la caja A con uid 1 da `su` (localizado,
  no probado; decisión 48).
- **Casos 11 y 25** (F1-1 y F1-2): correcciones nuevas, si se confirman en F1.4.
- **Caso 3:** todos los parches que tocan XML de vistas pasan por el convertidor; lo que salga de F1.1 vale para
  ellos.
- **F1-3 y F1-4 (menores):** solo se corrigen si el port toca esos archivos (convención del código heredado); si no,
  quedan como inventario.
