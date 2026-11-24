# Fase 2 de `pns_ai` en la 17: port de los parches y correcciones de la fase 1

- **Fecha:** 24/11/2026 (tandas preparadas).
- **Rama y partida:** `17.0-pns-ai`, HEAD `3aac623` (igual a `origin/17.0-pns-ai`), sin cambios locales. Módulos:
  `pns_base` 17.0.1.2.92, `pns_ai_mcp` 17.0.3.1.996 y `pns_ai_chatboo` 17.0.2.1.597 (R17), sin ningún parche.
- **Qué es la fase 2** (`docs/pendiente/plan_pns_ai_17.md`, «Plan», punto 3): «portar y aplicar los parches en esta
  rama, con sus tests».
- **Este documento:** alcance (sección 1), método (sección 2), tandas (sección 3) y estado (sección 4). El registro de
  cada tanda se añade debajo, en una sección por tanda, al hacerla.
- **Documentos de partida:** clasificación `docs/pendiente/clasificacion_parches_pns_ai_17_3996.md` (924 líneas,
  `5cb17965…ad129fe`; secciones 3, 4, 7 y 11) y fase 1 `docs/pendiente/fase1_pns_ai_17_3996.md` (1210 líneas,
  `ab4f1877…be524c`; secciones 7 y 8). Precedente: el port a 3.1.973 de la 14 (`14.0:docs/pendiente/`,
  `plan_correccion_pns_ai_3973.md` y `parches_pns_ai.md`).
- **Decisiones de Sergio (24/11/2026):**
  - **114.** Rama: se sigue en `17.0-pns-ai`, sin rama nueva. A `17.0` se llega al final de la fase 3, con PR y merge
    commit (plan, L3-4).
  - **115.** Versión de los manifiestos: no se tocan `version`, `depends`, `external_dependencies` ni `i18n`, y no se
    añade `migrations/` (como en la 14). F1-4 queda fuera, como inventario (cierra la decisión 112).
  - **116.** Tanda T0 nueva, antes de T1, solo de tests y documentos, sin código. Lleva: la infraestructura de tests de
    Seges en los módulos (`seges_common.py`, `common.py` y el bloque de Seges en `tests/__init__.py`), los tests de no
    regresión de los parches retirados (10, 13, 14, 23, 30 y 31), E0′ y el anexo de PNS-26 (como en la 14), el
    registro de parches (decisión 119) y la regla de terceros en `CLAUDE.md` (decisión 121). Se espera todo en verde;
    si algo falla, es un hallazgo y se para. En T0 se mide la línea base de las baterías.
  - **117.** Tests del laboratorio: se copian a los módulos, no se mueven; `seges_pruebas_3996` no cambia en la fase 2.
    A los módulos va el test que prueba cada parche o corrección (el `[HYPOTHESIS]`, como test normal) y los `[CHECK]`
    que protegen lo que se toca. El detalle, en la fase 1 de cada tanda.
  - **118.** Commits: tres por tanda (`[FIX]` código, `[ADD]` tests, `[DOC]` registro), como en la 14. T0, solo
    `[ADD]` y `[DOC]`.
  - **119.** Registro de parches en la 17: `docs/pendiente/parches_pns_ai.md`, corto (índice con número, id, tanda,
    estado y commit; para el detalle, remite a `14.0:docs/pendiente/parches_pns_ai.md`). Se crea en T0. Los
    marcadores, como en la 14.
  - **120.** Numeración: las correcciones de la fase 1, incluidas las tres sin número (SSE sin escapar, creador en
    `session_file`, `str(e)`), reciben número de parche desde el 40 al portarse, uno por corrección y en el orden de
    las tandas, con su F1-n como id. La numeración es común con la 14. Si el id choca con el «F1» del 27, la fase 1 de
    la tanda propone cómo distinguirlo.
  - **121.** `CLAUDE.md` de la rama: la regla de terceros de la 14, adaptada a la 17, en T0. En la fase 1 de T0 se
    comprueba antes si ese `CLAUDE.md` lo genera la plantilla del kit (`configurar_repo.py`); si lo genera, se para.
  - **122.** Los casos que necesitan un proveedor real (L2 del 34; 6c y 6d′ del 29) van a la lista del staging
    (fase 3). Cómo quedan en los tests del módulo se decide en la fase 1 de T5b.
  - **123.** E3 (alias de los parches 15 y 22) se estudia en la fase 1 de T4, con intención de cerrarlo.
  - **124.** Consta en este documento, sin reescribir la clasificación, que el 26 y el 28 sí tienen tests en la 14
    (`TestSegesCanvasPictures` y `TestSegesSharedPage`, en `test_seges_chatboo_canvas.py`); solo el 20 no tiene test.
  - **125.** Ninguna línea del documento pasa de 120 caracteres, tampoco las de las tablas. En la tabla, «N archivos»
    o nombres cortos; la lista completa, debajo de la tabla (como la sección 8 de la fase 1).
  - **126.** `CLAUDE.md`: lo genera el kit (`configurar_repo.py`); se añade a mano la regla de terceros, como en `14.0`
    (`9288d5a`), opción (a). En este repo no se usa `configurar_repo.py --force`. La opción (c), un sitio en la
    plantilla del kit para reglas propias del repo, queda como pendiente del kit, aparte.
  - **127.** `seges_common.py` y `common.py`, enteros en T0.
  - **128.** Cabeceras de los tests: las líneas históricas de la 14 sin cambios, más una línea de la 17
    (`# Seges: adaptado a la 17 (fase 2, T0): …` en los que cambian), que dice que los documentos que citan las
    líneas históricas están en `14.0`.
  - **129.** Anexo de PNS-26: se adaptan `_bus_notices` (formato del bus de la 17, `{"type", "payload"}`) y el texto
    de los `skip`.
  - **130.** Sin neutralización en T0: el código del fabricante que prueban los tests es el de `14.0` y cada archivo
    tiene su control positivo.
  - **131.** Columna «Commit» de los retirados en el registro de parches: «—»; el hash del `[ADD]` de T0, en la
    sección 5.
  - **132.** Cada `assertRaises` espera una sola excepción, la que da R17, establecida leyendo R17 y el core (si es
    `AccessError`, `assertRaises(AccessError)`, que en la 17 vacía la caché antes). En T0, `AttributeError` en los
    tres casos en Python de `test_seges_e4p.py`.
  - **133.** El FAIL del anexo de PNS-26 en la primera ejecución es un error de adaptación, no un hallazgo
    (`res.partner.comment` es Html en la 17): la comprobación `applied` compara por subcadena con un valor único.
  - **134.** La línea de la 17 va en las cabeceras de los 13 archivos de tests, también en los copiados sin cambios
    de código.
  - **135.** Tras corregir los fallos de adaptación, se vuelve a ejecutar la batería de los tres módulos y se sigue
    con el laboratorio, el lint y la comprobación del entorno, con las mismas reglas.
  - **136.** Se silencian solo las trazas que los tests provocan a propósito, para que la línea base vuelva a
    «RESULTADO: OK»: `mute_logger('odoo.http')` en `_SegesE4pRpcBase._rpc` y `mute_logger('odoo.sql_db')` solo en
    el primer intento del anexo de PNS-26. Nada más amplio.
  - **137.** El `I001` de los dos `tests/__init__.py` se deja: ordenarlo movería líneas del fabricante.
  - **138.** `test_execute_retry_is_idempotent` comprueba él mismo la carrera:
    `assertEqual(codes, [errorcodes.SERIALIZATION_FAILURE], …)`, como `PRECONDITION` (el `mute_logger` de la 136 ya
    no la deja ver en el log).
  - **139.** El asunto del commit `d7c872c` se deja como está, sin amend ni push forzado (como el cuerpo de
    `67bb15b` en su día). Su asunto real es «[ADD] pns_ai: tests de Seges de no regresión en la 17 (T0) y la
    descripción vacía.», con texto pegado por error; el acordado era «[ADD] pns_ai: tests de Seges de no regresión
    en la 17 (T0)».

## 1. Alcance

- **Parches que se portan (21):** 11, 12, 15 a 22, 24 a 29, 32 a 34, 36 y 39. No se portan el 35, el 37 ni el 38 (no
  aplican; clasificación, secciones 6 y 11).
- **Adaptaciones ya decididas:** el 18 como O1 ampliado con B2 y sin B (decisión 29 de la clasificación); el 20, el 21
  y el 36, «cambiado» (clasificación, sección 11, puntos 2 a 4); las listas del 22 y del 39, las del punto 7 (con
  `res.users.check` y los llamadores de la localización india).
- **Correcciones de la fase 1** (su sección 8): caso 24 (con el 18), F1-2 (con el 33), F1-6 (con el SSE sin escapar
  y el creador en `session_file`), F1-7 (con el `str(e)` del Chatboo), F1-8 y F1-9 a F1-12 (juntas, decisión 113).
- **Menores** (decisión 111): solo si el port toca su archivo. F1-4 queda fuera (decisión 115).
- **No regresión:** los tests de la 14 de los parches retirados (10, 13, 14, 23, 30 y 31), E0′ y el anexo de PNS-26,
  en T0 (decisión 116).
- **Pendiente para el port, con su tanda:** las aperturas de cursor del punto 5 localizadas y no leídas (T1), la caja
  A con uid 1 (decisión 48, T3) y el alias de los parches 15 y 22 (E3, T4; decisión 123).
- **Fuera de esta fase:** el staging (fase 3 del plan) y su lista de comprobaciones a mano (fase 1, sección 7), a la
  que se suman los casos con proveedor real (decisión 122).

## 2. Método

- **Cada tanda, en dos fases:**
  - fase 1, solo lectura: lo que falta por leer de la tanda, la adaptación de cada parche a la 17 y los tests, con
    `git apply --check` de los diffs de la 14; se presenta a Sergio y se para;
  - fase 2, tras su aprobación: los cambios en la copia de trabajo, que monta el laboratorio `lab_pns_ai_3996`;
    `odoo-dev 17 actualizar`, baterías, neutralizaciones y lint desde el laboratorio; después, el registro en este
    documento y en `docs/pendiente/parches_pns_ai.md`. Los commits y el push los hace Sergio.
- **Código:** el diff de la 14 de cada parche (sección 3) con `git apply`; lo que no entra, a mano. En un mismo
  archivo, primero el parche y después la corrección (fase 1, sección 8). Cambio mínimo, sin dependencias nuevas.
- **Marcador** junto a cada cambio, como en la 14 (decisión 119):
  `# Seges: parche N (<id>, <tipo>). Ver docs/pendiente/parches_pns_ai.md`. Las correcciones de la fase 1 llevan su
  número desde el 40 y su F1-n como id (decisión 120).
- **Manifiestos:** no se tocan `version`, `depends`, `external_dependencies` ni `i18n`, y no se añade `migrations/`
  (decisión 115).
- **Tests:**
  - los de Seges, en el módulo del parche (`tests/test_seges_*.py`, con el bloque de Seges en `tests/__init__.py`),
    adaptados de los de la 14 (clasificación, sección 7) y de los de aceptación del laboratorio;
  - los del laboratorio se copian, no se mueven: el `[HYPOTHESIS]` de cada parche o corrección, como test normal, y
    los `[CHECK]` que protegen lo que se toca (decisión 117). `seges_pruebas_3996` no cambia: sus 56 tests miden el
    avance;
  - baterías desde el laboratorio: `odoo-dev 17 tests pns_base,pns_ai_mcp,pns_ai_chatboo` y
    `odoo-dev 17 tests seges_pruebas_3996`. Referencias:
    - tres módulos sin parches: `0 failed, 0 error(s) of 249 tests`, 3 omitidos por el entorno (log
      `tests-20261123-141538.log` del laboratorio, 23/11/2026; clasificación, sección 10). La línea base con los
      tests de T0 se mide en T0 (decisión 116);
    - `seges_pruebas_3996`: `17 failed, 0 error(s) of 56 tests` (fase 1, cabecera);
  - desde T1, `test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin` queda en F por diseño (parche 12), como en la 14;
  - cada parche se neutraliza una vez en el laboratorio: sus tests dan F y el SHA-256 vuelve a ser el mismo al
    restaurar (como en la 14);
  - lint: `python3 ~/.claude/hooks/odoo_lint.py --revisar <modulo>/`.
- **Commits por tanda** (decisión 118): `[FIX]` código, `[ADD]` tests y `[DOC]` registro; T0, solo `[ADD]` y `[DOC]`.
  Patrón de la 14 (`ef05eaa`, `bc699e7`, `4542d3a`), con la tanda entre paréntesis.

## 3. Tandas

| Tanda | Parches y correcciones | Archivos | `git apply --check` (3aac623) | Lab. tras ella |
|---|---|---|---|---|
| T0 | tests de no regresión, registro y `CLAUDE.md` | 13 de tests y 2 documentos | sin código | 17 F de 56 |
| T1 | 12, 32, 16, 17, 19, 33 y F1-2 | 10 (`pns_ai_mcp`) | limpio; el 17, +6 | 16 F |
| T2 | 21 y 36 | `operation_report_wizard.py` | falla (4 de 4): a mano | 9 F |
| T3 | 24, 18 (O1 ampliado, B2 y P-22) y caso 24 | 8 (2 nuevos) | limpio; el 18 se reescribe | 4 F |
| T4 | 15, 22 y 39 (listas del punto 7) | 2 | limpio tras T3 | 4 F |
| T5a | 11, 25, 26 y 28 | 4 | limpio; sesión, +4 y +120 | 4 F |
| T5b | 27, 29 y 34 | 3 | limpio en cadena; el 34, `-C1` | 4 F |
| T6 | 20 | 2 (JS) | un archivo falla: a mano | 3 F |
| T7 | F1-6, SSE sin escapar y creador en `session_file` | 2 | sin diff de la 14 | 2 F |
| T8 | F1-7 y `str(e)` del Chatboo | 2 | sin diff de la 14 | 2 F |
| T9 | F1-8 | 1 (JS) | sin diff de la 14 | 2 F |
| T10 | F1-9, F1-10, F1-11 y F1-12, con sus menores | 10 u 11 | sin diff de la 14 | 0 F |

- **Archivos de cada tanda** (R17):
  - **T0:** `pns_ai_mcp/tests/`: `__init__.py`, `seges_common.py`, `test_seges_rpc_access.py`,
    `test_seges_safe_operation.py`, `test_seges_e4p.py` (casos del 30 y del 31), `test_seges_facade_class.py`,
    `test_seges_format_guard.py`, `test_seges_sandbox_env.py` y `test_seges_verify_execute_40001.py`;
    `pns_ai_chatboo/tests/`: `__init__.py`, `common.py`, `test_seges_skill_env.py` y `test_seges_chatboo_smoke.py`;
    `docs/pendiente/parches_pns_ai.md` (nuevo) y `CLAUDE.md`.
  - **T1:** `pns_ai_mcp/`: `models/ai_system_action.py`, `utils/privilege_cusp.py`, `models/ai_trusted_action.py`,
    `models/safe_operation.py`, `models/ai_change_journal.py`, `controllers/safe_plan_execute.py`,
    `utils/fetch_url_safe.py`, `utils/mcp_client.py`, `models/ai_provider.py` (33 y F1-2) y
    `wizard/ai_provider_usage_wizard.py`.
  - **T2:** `pns_base/models/operation_report_wizard.py`.
  - **T3:** `pns_ai_mcp/`: `controllers/context_builder.py`, `models/__init__.py`, `models/seges_box_a_read.py` y
    `utils/seges_box_a_cache.py` (nuevos), `utils/sandbox_helpers.py`, `models/key_pin_desk.py`,
    `models/mcp_api_key_wizard.py` y `models/sandbox_secret_read.py` (caso 24). No toca `controller_helpers.py`.
  - **T4:** `pns_ai_mcp/controllers/validators_base.py` y `controllers/context_builder.py`.
  - **T5a:** `pns_ai_chatboo/`: `models/chatboo_session.py`, `models/chatboo_canvas.py`,
    `models/chatboo_canvas_page.py` y `security/security.xml`.
  - **T5b:** `pns_ai_chatboo/models/`: `chatboo_canvas.py`, `chatboo_session.py` y `chatboo_async_request.py`.
  - **T6:** `pns_ai_chatboo/static/src/js/`: `chatboo_heavy_libs.js` y `chart.umd.min.js`.
  - **T7:** `pns_ai_mcp/controllers/main.py` y `controllers/session_file.py`.
  - **T8:** `pns_ai_chatboo/controllers/chatboo.py` y, si la corrección va en el método,
    `pns_ai_mcp/models/ai_execution_engine.py`.
  - **T9:** `pns_ai_mcp/static/src/js/safe_operation_action_buttons.js`.
  - **T10:** `pns_ai_chatboo/static/src/js/`: `chatboo_formatters.js`, `chatboo_app.js`, `chatboo_choice_list.js`,
    `chatboo_svg_cards.js`, `chatboo_charts.js`, `chatboo_row_marks.js` y `chatboo_turn.js`;
    `pns_ai_chatboo/models/chatboo_session.py`, `pns_ai_mcp/utils/record_marks.py`,
    `pns_ai_mcp/controllers/safe_plan_describe.py` y, si el diseño toca `held`, `pns_ai_mcp/models/safe_operation.py`.
- **Diffs de la 14** (rama `14.0`):
  - T1: `ef05eaa` (cada archivo, de un solo parche);
  - T2: `ef05eaa` (21) y `51e422c` (36);
  - T3: `5ce3365` (24) y `f922f76` (18), sin los dos trozos de `controller_helpers.py` (B y el 37) ni la función B
    de `seges_box_a_cache.py` (`_seges_forget_secret_columns`);
  - T4: `8d1c9b2` (15 y 22, en un mismo trozo de `validators_base.py`) y `631b924` (39);
  - T5a: `8d1c9b2` (el 11, el 25 y el 26 en trozos distintos de `chatboo_session.py`);
  - T5b: `52660ab` (27), `34606ab` (29), `272ebb5` y `617b9b3` (34);
  - T6: `ef05eaa`.
- **`git apply --check -v` sobre `3aac623`** (por la entrada estándar, encadenando los diffs de un mismo archivo):
  - limpios sin desplazamiento: 12, 16, 19, 24, 28, 32, 33, `chart.umd.min.js` y `safe_plan_execute.py`;
  - con desplazamiento: el 17 en `ai_change_journal.py` (+6); el 11, el 25 y el 26 en `chatboo_session.py` (+4 y
    +120); el 27 (−1); el 29 en la sesión (−2 tras el 11, el 25 y el 26); el 18 en `context_builder.py` (0 tras el 24);
  - cadenas limpias: canvas 26 → 27 → 29 → 34, `validators_base.py` 15/22 → 39 y `context_builder.py` 24 → 18 → 39;
    fallan fuera de orden (el 29 y el 34 sin el 27; el 39 sin el 18);
  - el 34 en `chatboo_async_request.py` choca solo en el contexto del `import html` (que el propio `617b9b3` quita);
    con `-C1`, la cadena entra (+4, −4 y −51);
  - fallan por la 17: `chatboo_heavy_libs.js` (20) y `operation_report_wizard.py` (21 y 36).
- **Orden:** T0 deja la base de tests sin tocar código; T1 fija el método con lo que entra limpio; T2 y T3 son lo más
  delicado y van pronto; T4 va tras T3 por `context_builder.py`; T5a y T5b, antes de T10 (decisión 113); las
  correcciones F1-n, tras los parches.

### Detalle

- **T0 (decisión 116):**
  - Tests de la 14 que entran (`14.0`), en su módulo:
    - `pns_ai_mcp`: `seges_common.py` (`_StubController`); `test_seges_rpc_access.py` (`TestSegesRpcAccess`,
      `TestSegesInternalFlows` y `TestSegesSandboxDenylist`; parches 7 a 10, 13 y 14, más un control de sesión);
      `test_seges_safe_operation.py` (`TestSegesSafeOperationCreate`; 13); `test_seges_e4p.py`, solo lo del 30 y
      el 31 (sus casos de `TestSegesE4pRpc`, `TestSegesE4pLogRows` y `TestSegesE4pChatCompletion`; lo del 32 y el
      33 entra en T1); `test_seges_facade_class.py` (`TestSegesFacadeClass` y `TestSegesSkillFormat`; 23);
      `test_seges_format_guard.py` (`TestSegesFormatGuard`; 23, con `test_pns36_cr_dbname`, el test de PNS-36 sin
      parche que cubría el 23); `test_seges_sandbox_env.py` (`TestSegesSandboxEnv`; 23: el 18 solo se cita en su
      docstring); `test_seges_verify_execute_40001.py` (`TestSegesVerifyExecute40001`; anexo de PNS-26, con dos
      casos con `skip` en la 14);
    - `pns_ai_chatboo`: `common.py` (`SegesChatbooCase`); `test_seges_skill_env.py` (`TestSegesSkillEnv`; 23) y
      `test_seges_chatboo_smoke.py` (`TestSegesChatbooSmoke`; E0′).
  - Reparto comprobado caso a caso en `14.0` (24/11/2026), con el marcador de la cabecera y el docstring del archivo
    o de la clase y, en `test_seges_rpc_access.py`, el nombre del caso (modelo y método que prueba): ningún caso es de
    un parche que se porta. El plan de la 3973 (L150) cita `test_seges_rpc_access.py` en la fila del 15 porque se
    adaptó en la fase 2b, pero no tiene casos del 15.
  - Parches 7 a 9 (PNS-90, PNS-91 y PNS-85: caché de `fetch_url`, alta de dominios y caché de parámetros de skills,
    pasados a privados): retirados en 3.1.879 porque los cubrió el fabricante (cabecera de `test_seges_rpc_access.py`
    e índice de `14.0:docs/pendiente/parches_pns_ai.md`). La clasificación no los trata (su sección 5 solo recoge los
    retirados del índice de 3.1.973); en R17 siguen privados los nombres que prueba el archivo (`git grep`:
    `fetch_cache.py:71` y `:99`, `url_whitelist.py:241`, `ai_skill_param_cache.py:95` y `:129`, `ai_skill.py:351` y
    `:360`), y la fase 1 de T0 lo confirma.
  - Fase 1: comprobar si el `CLAUDE.md` de la rama lo genera la plantilla del kit (`configurar_repo.py`; decisión
    121, si lo genera se para); los cambios de API de la 17 en esos tests (`flush`, `invalidate_cache`, `name_get`,
    `fields_view_get`…) y que los nombres privados del fabricante sigan en R17; el contenido del registro (decisión
    119) y de la regla de terceros.
  - Laboratorio: 17 F de 56, sin cambios. Baterías: todo en verde (salvo los `skip`); un fallo es un hallazgo y se
    para. Se mide la línea base.
  - Commits: «[ADD] pns_ai: tests de Seges de no regresión en la 17 (T0)» y «[DOC] pns_ai 17: registro de parches,
    regla de terceros y tanda T0 (fase 2)».
- **T1:**
  - Fase 1: las 14 aperturas de cursor del punto 5 (6 en `safe_operation.py`), `check_identity` y `has_group` en el
    contenedor, y `_compute_display_name` (F1-2).
  - Tests de la 14: `test_seges_user_groups.py` (12 y 32), `test_seges_e4p.py` (`TestSegesE4pTrustedAction`,
    `TestSegesE4pUsage` y los casos del 33 de `TestSegesE4pRpc`), `test_seges_verification.py` (16),
    `test_seges_change_journal.py` (17) y `test_seges_fetch_redirect.py` (19). Del laboratorio, el de F1-2
    (`TestDisplayName17`).
  - Riesgo: bajo (el 12 cambia permisos; el 16 pide la contraseña).
  - Commit: «[FIX] pns_ai_mcp: parches 12, 32, 16, 17, 19 y 33 portados a 17.0.3.1.996 y F1-2 (T1)».
- **T2:**
  - Fase 1: `_invalidate_after_preview_rollback` (`:295`), el `SAVEPOINT` (`:315`) y su `ROLLBACK` (`:324`),
    `Cache.invalidate` e `invalidate_all` en el contenedor, el ormcache de `has_group` y `registry.clear_cache()`;
    `_inject_screen_arch` y `postprocess_and_fields` con `sudo`. Se confirma el módulo de los tests: el código está en
    `pns_base` y la clasificación lleva los tests a `pns_ai_mcp`.
  - Tests: `TestImportReview` y `TestReviewViews` del laboratorio (sus orígenes de la 14,
    `test_seges_import_preview.py` y `test_seges_review_views.py`); opcional, un caso de `config_backup_wizard` (36).
  - Riesgo: alto. Volcar solo dentro del savepoint desharía también lo pendiente del llamador: se vuelca antes del
    `SAVEPOINT` y otra vez dentro, y después se invalida sin volcar.
  - Commit: «[FIX] pns_base: parches 21 y 36 adaptados a la 17 (PNS-20, PNS-103) (T2)».
- **T3:**
  - Fase 1: `Field.__get__` con el valor en caché, el cálculo de los no guardados, `check_field_access_rights`,
    quién abre la caja A con uid 1 (decisión 48) y los campos de P-22 con el `display_name` de la 17.
  - Tests: los 9 del laboratorio (`TestBoxACacheAtOpening`, `TestBoxASecretReadInside` y `TestBoxAComputedSecret`,
    con `_CursorSpy` en `seges_common.py`); de la 14, `test_seges_identity_su.py` (24), `test_seges_box_a_vias.py` y
    `test_seges_sandbox_credentials.py` según la clasificación (sección 11, punto 1); caso nuevo con uid 1.
  - Riesgo: el mayor. B2 invalida con `Cache.invalidate`, que tira lo pendiente: solo en la caché de la caja A, nunca
    en la del llamador (un `[GUARD]` lo comprueba). El enganche de `Field.__get__` está en el camino caliente: sale
    enseguida fuera de la caja A.
  - Commit: «[FIX] pns_ai_mcp: parches 24 y 18 (O1 ampliado y B2, con P-22 y el caso 24) portados a la 17 (PNS-102,
    PNS-19) (T3)».
- **T4:**
  - Fase 1: E3, con intención de cerrarlo (decisión 123); los 3 llamadores de la localización india; `iap_jsonrpc`
    en modo test.
  - Tests de la 14: `test_seges_sandbox_side_effects.py` (adaptado, con los casos nuevos del punto 7) y
    `pns_ai_chatboo/tests/test_seges_chatboo_export.py` (15).
  - Riesgo: medio (bloquear de más por un nombre común; de ahí la tabla por modelo).
  - Commit: «[FIX] pns_ai_mcp: parches 15, 22 y 39 portados a 17.0.3.1.996 con las listas de la 17 (T4)».
- **T5a:**
  - Fase 1: lo nuevo de R17 en `chatboo_session.py`; la regla del 28 (`noupdate="0"`: el `-u` la aplica).
  - Tests de la 14: `test_seges_chatboo_access.py` (11) y, de `test_seges_chatboo_canvas.py`,
    `TestSegesPaintCanvas` (25), `TestSegesCanvasPictures` (26) y `TestSegesSharedPage` (28). La sección 7 de la
    clasificación dice que el 26 y el 28 no tienen test propio: sí lo tienen, y solo el 20 no lo tiene (decisión 124).
  - Riesgo: bajo.
  - Commit: «[FIX] pns_ai_chatboo: parches 11, 25, 26 y 28 portados a 17.0.2.1.597 (T5a)».
- **T5b:**
  - Fase 1: la CSP en la 17 (decisión 6 de la 14), el punto 6 del 29 (sus tests, en `HttpCase` y con `flush()`) y
    `_process` del 34. Cómo quedan en los tests los casos con proveedor real (decisión 122).
  - Tests de la 14: `TestSegesCanvasHeaders` (27), `TestSegesCanvasModelData` (29) y `TestSegesNoPageNotice` (34).
  - Casos con proveedor real (L2 del 34; 6c y 6d′ del 29): a la lista del staging (decisión 122).
  - Riesgo: medio.
  - Commit: «[FIX] pns_ai_chatboo: parches 27, 29 y 34 portados a 17.0.2.1.597 (T5b)».
- **T6:**
  - Fase 1: `bindEngines` (`chatboo_charts.js:40-47`) y la opción A de la 14 (Chart.js propio del chat).
  - Tests: los 2 de `TestChatbooChartCollision` del laboratorio, a `pns_ai_chatboo` (Chrome). Sin test en la 14.
  - Riesgo: medio (librería minificada).
  - Commit: «[FIX] pns_ai_chatboo: parche 20 adaptado a la 17 (PNS-70) (T6)».
- **T7:** tests: `TestRoutes17.test_mcp_single_allow_origin` y los `[CHECK]` de CORS que proteja (pueden cambiar con
  F1-6); nuevos para el SSE con un `agent_code` hostil y para el creador en `session_file`.
- **T8:** tests nuevos: `/chatboo/providers` con un agente sin cadena y los errores de las rutas sin `str(e)`.
- **T9:** sin test automático: la reproducción va al staging (fase 1, sección 7, punto 1).
- **T10:** fase 1: el diseño (`id`, `class` y `data-*` del contenido del asistente; `held`). Tests:
  `TestSanitizer17.test_t2b_no_chat_controls` y `TestMarks17.test_t3_marks_checked_on_save`, vigilando los
  `[CHECK]` T1 y T2a. Al terminar, el laboratorio da `0 failed … of 56`.

## 4. Estado

| Tanda | Estado |
|---|---|
| T0 | hecha (24/11/2026): 0 F y 0 E de 330 tests, 5 omitidos; laboratorio, 17 F de 56; `CLAUDE.md`, con la regla |
| T1 | pendiente (la siguiente) |
| T2 a T10 | pendientes |

## 5. T0: tests de no regresión, registro y `CLAUDE.md`

- **Fecha:** 24/11/2026. Partida: HEAD `b093519` («[DOC] pns_ai 17: tandas del port (fase 2)»), sin cambios
  locales.
- **Fase 1** (solo lectura, 24/11/2026). Las citas del core son del contenedor del laboratorio
  (`/usr/lib/python3/dist-packages/odoo`, Odoo 17.0-20260908), no de `/opt/odoo-src/17.0`:
  - `CLAUDE.md`: lo genera el kit (`configurar_repo.py:299`, plantilla `plantilla-repo/CLAUDE.md.tpl`; entero y
    solo si no existe, salvo `--force`, `:144-149`), sin sitio para reglas propias del repo. Por la decisión 121,
    se paró ese punto; se resolvió con la decisión 126.
  - Código del fabricante que prueban los tests (22 archivos): igual en R17 que en `14.0` salvo los parches de
    Seges (15 a 18, 22, 37, 38 y 39) y `ai_log.py` (cambios de 3.1.996; la firma de `_create_log_entry`, que los
    tests simulan, es igual). Los nombres privados de los parches 7 a 10, 13, 14, 30 y 31 siguen en R17.
  - En la 17 no existen `BaseModel.flush()`, `invalidate_cache()`, `sql_db.flush_env` ni `Transaction.towrite`;
    `get_module_resource` es un alias obsoleto que avisa.
- **Archivos (13 de tests, nuevos salvo los dos `__init__.py`):**
  - `pns_ai_mcp/tests/`: `__init__.py` (bloque de Seges al final), `seges_common.py`, `test_seges_rpc_access.py`,
    `test_seges_safe_operation.py`, `test_seges_e4p.py` (sin `TestSegesE4pTrustedAction`, `TestSegesE4pUsage` ni
    los 3 casos del 33 de `TestSegesE4pRpc`, que entran en T1), `test_seges_facade_class.py`,
    `test_seges_format_guard.py`, `test_seges_sandbox_env.py` y `test_seges_verify_execute_40001.py`;
  - `pns_ai_chatboo/tests/`: `__init__.py`, `common.py`, `test_seges_skill_env.py` y `test_seges_chatboo_smoke.py`.
- **Cambios respecto a `14.0`** (los 13 llevan en la cabecera las líneas de la 14 sin cambios y la línea de la 17,
  decisiones 128 y 134):
  - copiados sin cambios de código: `seges_common.py`, `test_seges_safe_operation.py`,
    `test_seges_facade_class.py`, `test_seges_format_guard.py` y `test_seges_chatboo_smoke.py`;
  - `test_seges_rpc_access.py`: `self.env.flush_all()` en L127 y L155 (`odoo/api.py:735`);
    `invalidate_recordset()` en L374 (`odoo/models.py:6747`); el comentario de `result` cita `odoo/http.py:2253`
    (L145);
  - `test_seges_e4p.py`: solo los casos del 30 y del 31; sin los imports `api`, `convert_file`,
    `execute_safe_plan` ni `AccessError`; `flush_all()` (L80); `mute_logger('odoo.http')` en `_rpc` (L91,
    decisión 136); `assertRaises(AttributeError)` en L224, L233 y L276 (decisión 132: el modelo solo tiene `_log_*`,
    `models/ai_execution_engine.py:425-781`, y `_chat_completion`, `:872`; el `:38` es del envoltorio del driver;
    `odoo/models.py` no tiene `__getattr__`);
  - `test_seges_sandbox_env.py`: solo el docstring (L26-30: `env.all` es la `Transaction` del cursor,
    `odoo/api.py:532`; el fabricante la rechaza, `controllers/context_builder.py:169-173`);
  - `test_seges_verify_execute_40001.py`:
    - `cache.get_dirty_fields()` en lugar de `towrite` (L113, `odoo/api.py:1260`) y `flush_all()` (L144, L154 y
      L222);
    - `applied` por subcadena (L250, decisión 133; `res_partner.py:239`, Html en la 17 y Text en la 14);
    - `_bus_notices` con `{"type", "payload"}` (L297, decisión 129; `bus/models/bus.py:111-120`;
      `safe_operation.py:1753` y `:1768-1769`);
    - `cr.flush()` (L349, `odoo/service/model.py:155`, `odoo/sql_db.py:134`) y `env_p.reset()` (L369,
      `model.py:160-161`; `api.py:501` y `:886`);
    - `mute_logger('odoo.sql_db')` solo en el primer intento (L374, decisión 136);
    - `assertEqual(codes, [errorcodes.SERIALIZATION_FAILURE], …)` en `test_execute_retry_is_idempotent` (L434-437,
      decisión 138);
    - citas del core de la 17 y de R17 en el docstring y los comentarios, y el texto de los `skip` (L410 y L473);
  - `common.py`: `flush_all()` (L57) y el docstring (`odoo/tests/common.py:1934`);
  - `test_seges_skill_env.py`: `file_path` (L27, `odoo/tools/misc.py:158`; `odoo/modules/module.py:220-240`).
- **Primera ejecución** (log `tests-20261124-165129.log`): `1 failed, 3 error(s) of 330 tests`, cuatro fallos de
  adaptación, ninguno del fabricante:
  - 3 ERROR en `test_seges_e4p.py` (`test_foreign_user_leaves_no_row`, `test_external_user_leaves_no_row` y
    `test_direct_call_refused`): en la 17, `assertRaises` no admite una tupla de excepciones
    (`odoo/tests/common.py:445-456`, `TypeError: issubclass() arg 1 must be a class`). Corrección: la decisión 132;
  - 1 FAIL en `test_execute_retry_is_idempotent`, con el mensaje `PRECONDITION`: la comprobación `applied`
    comparaba `comment` por igualdad y en la 17 es Html. Corrección: la decisión 133. Con ella, el reintento
    idempotente sí se evaluó y pasa (primer intento con 40001; el plan no se vuelve a ejecutar).
- **Segunda ejecución** (log `tests-20261124-165725.log`): `0 failed, 0 error(s) of 330 tests`, pero el resumen de
  `analizar_log.py` daba «RESULTADO: FALLO» por 26 líneas `ERROR` que los tests provocan a propósito: 25
  `odoo.http` de los 4 casos RPC de `TestSegesE4pRpc` y 1 `odoo.sql_db: bad query` del 40001 del anexo. Se
  resolvió con la decisión 136, y la 138 hace que el caso compruebe la carrera que el log ya no enseña.
- **Baterías** (desde el laboratorio):
  - tres módulos (log `tests-20261124-171048.log`): `0 failed, 0 error(s) of 330 tests`, «RESULTADO: OK», sin
    líneas `ERROR`. Omitidos (5): `crm not installed`, los 2 de «typed parameter readers/setters arrive in Odoo
    20» y los 2 del anexo de PNS-26 (sin parche, decisión del 13/11/2026);
  - `seges_pruebas_3996` (log `tests-20261124-170030.log`): `17 failed, 0 error(s) of 56 tests`, los mismos 17
    casos que en `tests-20261124-131215.log`.
- **Por archivo:**

| Archivo | Casos | Verdes | `skip` |
|---|---|---|---|
| `test_seges_rpc_access.py` | 22 | 22 | 0 |
| `test_seges_safe_operation.py` | 4 | 4 | 0 |
| `test_seges_e4p.py` | 9 | 9 | 0 |
| `test_seges_facade_class.py` | 9 | 9 | 0 |
| `test_seges_format_guard.py` | 19 | 19 | 0 |
| `test_seges_sandbox_env.py` | 12 | 12 | 0 |
| `test_seges_verify_execute_40001.py` | 3 | 1 | 2 |
| `test_seges_skill_env.py` | 1 | 1 | 0 |
| `test_seges_chatboo_smoke.py` | 2 | 2 | 0 |
| **Total T0** | **81** | **79** | **2** |

- **Línea base para T1:** `0 failed, 0 error(s) of 330 tests`, 5 omitidos. Desde T1,
  `test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin` queda en F por diseño (parche 12).
- **Lint** (`python3 ~/.claude/hooks/odoo_lint.py --revisar <modulo>/`): 0 incidencias nuevas en `pns_ai_mcp/` y
  `pns_ai_chatboo/`. Preexistentes, del fabricante: en cada `tests/__init__.py`, `UP009` (L1, `# -*- coding:
  utf-8 -*-`) e `I001` (L6, bloque de imports sin ordenar, que abarca el bloque de Seges; se deja, decisión 137).
- **Entorno:** la BD del laboratorio no se toca (los tests usan una BD nueva que se borra). Comprobado antes y
  después: `odoo-dev 17 estado` igual (BD `lab_pns_ai_3996_17`, `CONF_HASH=c5c7138b608673bb`, mismo servidor
  web), `bd-lista` sin `test_…` y el mismo sha256 de los `.py` de `seges_pruebas_3996` (`b5e46c60…`).
- **Registro:** `docs/pendiente/parches_pns_ai.md` (nuevo, 92 líneas): índice de los parches 7 a 39, tests sin
  parche y hueco desde el 40.
- **`CLAUDE.md`:** la regla de terceros, a mano (12 líneas, tras «En módulos existentes…»; decisión 126).
- **Commits** (los hace Sergio):
  - `[ADD]`: `d7c872c`. Errata (decisión 139): su asunto real es «[ADD] pns_ai: tests de Seges de no regresión
    en la 17 (T0) y la descripción vacía.»; el acordado era «[ADD] pns_ai: tests de Seges de no regresión en la
    17 (T0)»;
  - `[DOC]`: el de este registro, «[DOC] pns_ai 17: registro de parches, regla de terceros y tanda T0 (fase 2)».
- **Para las tandas siguientes:** en la 17, `assertRaises` no admite tuplas (`odoo/tests/common.py:445-456`); en
  los tests de la 14 de T1 a T6 no hay más (solo estaban en las partes de T0 del e4p). En T1, vigilar
  `test_seges_verification.py:78` (`assertFalse` sobre `comment`, que es Html en la 17). No hay comparaciones de
  igualdad con campos que pasan de Text a Html.
