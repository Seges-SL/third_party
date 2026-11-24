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
- **Decisiones de Sergio en T1 (24/11/2026):**
  - **140.** `test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin` (`test_system_action.py:543-547`): opción (b). El
    cambio va dentro del parche 12, con su marcador: `assertFalse(ok)` y
    `assertIn('Only a Settings administrator', err or '')`, en el `[FIX]`. En la 14 sigue la decisión del
    23/10/2026 (F por diseño); esto es solo para la 17.
  - **141.** Neutralizaciones: una por parche (N12, N32, N16, N17, N19, N33 y N40), con la batería de `pns_ai_mcp`,
    la copia previa en el scratchpad y el sha256 comprobado al restaurar. Con la 140, N12 deja también en F
    `test_paap_i7`.
  - **142.** F1-2: al módulo, solo el `[HYPOTHESIS]` (`test_seges_display_name.py`, etiqueta `seges_t1`). El parche
    40 repite la etiqueta en `_compute_display_name` y no llama a `name_get` (el del core lee `display_name`:
    recursión). El `name_get` del fabricante no se toca. Las líneas nuevas no pasan de 110 caracteres.
  - **143.** `onchange` del e4p: `fields_spec` como `{}` (formato de la 17) y el comentario corregido.
  - **144.** Errata del 19: su diff está en `8d1c9b2`, no en `ef05eaa`. Consta como nota en la sección 6; la sección
    3 no se reescribe.
  - **145.** Estado en el registro tras T1: «Validado en el laboratorio», con el hash del `[FIX]`.
  - **146.** Lint: I001 y C0415 en `ai_trusted_action.py` se aceptan como en la 14
    (`14.0:docs/pendiente/parches_pns_ai.md:3082`, parche 32, «Lint», 05/11/2026; recogidos en `:3177` y `:3763`).
  - **147.** `test_seges_change_journal.py:284`: savepoint propio (`sp = self.env.cr.savepoint()` antes y
    `sp.close(rollback=True)` en lugar de `self.env.cr.rollback()`), con comentario y cita.
  - **148.** Marcador del 40: id «F1-2», sin prefijo; en «Marcadores» del registro, una frase sobre `F1` (27 y 29) y
    `F1-n`.
  - **149.** Se autoriza `odoo-dev 17 actualizar pns_ai_mcp` en la BD del laboratorio (`lab_pns_ai_3996_17`), que
    queda con el código de T1.
  - **150.** El plan de prueba para el staging va en un apartado «Para el staging» de la sección 6. La fase 3 reunirá
    la lista de la fase 1 (su sección 7) y las de cada tanda; el documento de la fase 1 no se toca.
  - **151.** El 40 forma la etiqueta con f-string, porque el hook de lint del kit bloquea el `%` (UP031 y C0209) en
    las líneas nuevas; la etiqueta es la misma.
  - **152.** Las 2 líneas ERROR de N16 son efecto esperado de la neutralización (sin `check_identity`, el plan llega
    a ejecutarse); se anotan en la tabla de neutralizaciones.
- **Decisiones de Sergio en T2 (24/11/2026):**
  - **153.** Parche 21 con la semántica de `_FlushingSavepoint` del core: `cr.flush()` antes del `SAVEPOINT`;
    `env.flush_all()` dentro, tras `action_import()`; `cr.clear()` y `registry.clear_cache()` tras el `ROLLBACK`; sin
    volcado en el `except` ni `contextlib`. Sustituye al punto 3 de la sección 11 de la clasificación (su orientación
    para el port) y resuelve las dudas del `precommit` y del camino de excepción.
  - **154.** La falta de `_postprocess_access_rights` en `_inject_screen_arch` es una observación de R17, fuera de T2.
  - **155.** Lectura ORM en `test_providers_review_writes_nothing`, `[GUARD]`
    `test_caller_pending_write_survives_review` y neutralizaciones N21a, N21b y N21c, como excepción a la 141 por ser
    el riesgo alto.
  - **156.** `test_admin_gets_config_backup_screens`, en un caso aparte.
  - **157.** `odoo-dev 17 actualizar pns_base` en el laboratorio (`lab_pns_ai_3996_17`), como en la 149.
  - **158.** Nombres: archivo, clase y etiqueta de la 14 y nombres de los casos del laboratorio.
  - **159.** Las 3 líneas de 89 a 91 caracteres copiadas del laboratorio se quedan tal cual (el lint no las marca).

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
  - desde T1, `test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin` espera el rechazo del parche 12, con un cambio
    dentro del propio parche (decisión 140), y la batería sigue en verde; en la 14 queda en F por diseño;
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
| T1 | hecha (24/11/2026): 0 F y 0 E de 378 tests, 5 omitidos; laboratorio, 16 F de 56 |
| T2 | hecha (24/11/2026): 0 F y 0 E de 390 tests, 5 omitidos; laboratorio, 9 F de 56 |
| T3 | pendiente (la siguiente) |
| T4 a T10 | pendientes |

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

## 6. T1: parches 12, 32, 16, 17, 19 y 33, y el 40 (F1-2)

- **Fecha:** 24/11/2026. Partida: HEAD `146df1b` («[DOC] pns_ai 17: registro de parches, regla de terceros y tanda
  T0 (fase 2)»), sin cambios locales.
- **Fase 1** (solo lectura, 24/11/2026). Las citas del core son del contenedor del laboratorio
  (`/usr/lib/python3/dist-packages/odoo`, Odoo 17.0-20260908); las marcadas «ref.», de `/opt/odoo-src/17.0`:
  - los 10 archivos de R17 de T1 son idénticos a la base 3.1.973 de la 14 (`33ca68c`), salvo
    `ai_change_journal.py:222-227` (el `AccessError` del snapshot pasa a `warning`; de ahí el +6 del 17). Los
    parches dan el mismo código que en la 14; lo que cambia es el core;
  - `check_identity` (`odoo/addons/base/models/res_users.py:139-176`), como en la 14: exige HTTP, recuerda la
    contraseña 10 minutos y, si no, devuelve el asistente `res.users.identitycheck`; `run_check` (`:2023-2031`)
    vuelve a llamar al método y la contraseña se valida con `_check_credentials` (`:2015-2021`);
  - `has_group`: `ormcache('self._uid', 'group_ext_id')` y SQL (`res_users.py:1088-1113`), con la caché vaciada al
    escribir grupos (`:748-758` y `:1511-1522`); el `many2many` se escribe al momento (`odoo/fields.py:4906`, ref.);
  - `AccessError` sigue heredando de `UserError` (`odoo/exceptions.py:18` y `:74`); `check_access_rights` y
    `check_access_rule`, en `odoo/models.py:4139` y `:4150`; el primer `onchange` llama a `default_get`
    (`odoo/addons/web/models/models.py:970-978`), así que el 33 cubre también esa vía; `requests` 2.25.1
    (`Response.is_redirect`; `Session.post` admite `allow_redirects`);
  - las 14 aperturas de cursor del punto 5 (clasificación, sección 11) se han leído: cada una abre su cursor con su
    `Environment` y su `Transaction`, y su `commit` solo vuelca esa transacción (`odoo/sql_db.py:134-138`,
    `:176-181` y `:479-488`). Ninguna vuelca ni invalida al llamador por su cuenta y ninguna exige nada en T1.
    Por `safe_operation.py:966` y `:1085` pasan el 12, el 32 y el 17 con las claves `ai_journal_*` que pone
    `execute_plan_now` (`:1470-1479`); `key_pin_desk.py:198` y `:222` vuelven a leerse en T3 (caso 24);
  - en la 17, `TransactionCase` hace cada test en un savepoint (`odoo/tests/common.py:904-906`): el
    `self.env.cr.rollback()` de `test_seges_change_journal.py:284` lo destruiría (decisión 147).
- **Errata (decisión 144):** el diff del 19 está en `8d1c9b2` (fase 2b de la 14), no en `ef05eaa` como dice la
  sección 3. Con `8d1c9b2` entra limpio.
- **Archivos:**
  - código (`[FIX]`, 11): `pns_ai_mcp/`: `controllers/safe_plan_execute.py`, `models/ai_change_journal.py`,
    `models/ai_provider.py`, `models/ai_system_action.py`, `models/ai_trusted_action.py`, `models/safe_operation.py`,
    `utils/fetch_url_safe.py`, `utils/mcp_client.py`, `utils/privilege_cusp.py`,
    `wizard/ai_provider_usage_wizard.py` y `tests/test_system_action.py` (decisión 140);
  - tests (`[ADD]`, 7): `pns_ai_mcp/tests/`: `__init__.py` (bloque de Seges de T1), `test_seges_e4p.py` y, nuevos,
    `test_seges_user_groups.py`, `test_seges_verification.py`, `test_seges_change_journal.py`,
    `test_seges_fetch_redirect.py` y `test_seges_display_name.py`.
- **Cambios respecto a `14.0` en el código** (`git apply -v`, en el orden 12, 32, 16, 17, 19 y 33; 31 marcadores):
  - 12, 32, 16, 19 y 33: el diff de la 14 tal cual (`ef05eaa`; el 19, de `8d1c9b2`), limpio;
  - 17: el diff de `ef05eaa`; en `ai_change_journal.py`, los tres trozos con un desplazamiento de +6;
  - 40 (F1-2), a mano en `ai_provider.py`: `_compute_display_name` con `@api.depends('title', 'name')`
    (`odoo/models.py:1660-1695`) antes del `name_get` del fabricante, que no se toca; repite la etiqueta y no
    llama a `name_get` (decisión 142), con f-string (decisión 151);
  - `test_system_action.py:547-550`: `test_paap_i7` espera el rechazo del 12, con su marcador (decisión 140).
- **Cambios respecto a `14.0` en los tests** (los 7 llevan en la cabecera las líneas de la 14 sin cambios y la línea
  de la 17, decisiones 128 y 134):
  - copiados sin cambios de código: `test_seges_user_groups.py` y `test_seges_fetch_redirect.py`;
  - `test_seges_verification.py`: `flush_all()` (`odoo/api.py:735`) e `invalidate_recordset()` ×4
    (`odoo/models.py:6747`); la L78 (`assertFalse` sobre `comment`, Html) no cambia: vacío es `False` y escrito
    sería `'<p>…</p>'`;
  - `test_seges_change_journal.py`: `invalidate_recordset()` ×7, `invalidate_model()` ×1 (`odoo/models.py:6732`) y
    `flush_all()` ×2; en `test_failed_plan_row_survives_rollback`, un savepoint propio en lugar de
    `cr.rollback()` (decisión 147; `odoo/sql_db.py:84-112` y `:153-162`);
  - `test_seges_e4p.py`: las partes del 32 y el 33 (`TestSegesE4pTrustedAction`, `TestSegesE4pUsage` y los 3 casos
    del 33 de `TestSegesE4pRpc`) con sus imports y constantes; `invalidate_recordset()` ×3 e `invalidate_model()`
    ×1; `_xmlid_to_res_id` ×2 (`odoo/addons/base/models/ir_model.py:2228`); `convert_file(self.env, …)`
    (`odoo/tools/convert.py:674`); `onchange` con `fields_spec` `{}` y el comentario de la 17 (decisión 143;
    `odoo/addons/web/models/models.py:933` y `:970-978`); el docstring de T0 actualizado;
  - `test_seges_display_name.py` (nuevo): el `[HYPOTHESIS]` de `TestDisplayName17` del laboratorio, como test
    normal (decisión 142);
  - `tests/__init__.py`: el bloque de Seges de T1, debajo del de T0.
- **`odoo-dev 17 actualizar pns_ai_mcp`** (decisión 149; log `actualizar-20261124-174412.log`): «RESULTADO: OK», 0
  bloqueantes. `trusted_actions_system.xml` se recarga sin error (el 32 no rompe el `-u`). 5 WARNING del
  fabricante, ya conocidos (`instalar-20261123-132159.log` y la línea base): etiquetas repetidas en `ai.log` y
  `ai.trusted.action`, y «skip retired unlink». El servidor web se reinicia.
- **Baterías** (desde el laboratorio):
  - tres módulos (log `tests-20261124-174508.log`): `0 failed, 0 error(s) of 378 tests`, «RESULTADO: OK», sin
    líneas `ERROR`. Omitidos (5), los de T0;
  - `seges_pruebas_3996` (log `tests-20261124-174709.log`): `16 failed, 0 error(s) of 56 tests`. Frente a
    `tests-20261124-170030.log`, solo deja de fallar `TestDisplayName17.test_provider_model_label_from_name_get`.
- **Por archivo:**

| Archivo | Parche | Casos de T1 | Verdes |
|---|---|---|---|
| `test_seges_user_groups.py` | 12 | 12 | 12 |
| `test_seges_e4p.py` (28 en el archivo) | 32 y 33 | 19 | 19 |
| `test_seges_verification.py` | 16 | 2 | 2 |
| `test_seges_change_journal.py` | 17 | 11 | 11 |
| `test_seges_fetch_redirect.py` | 19 | 3 | 3 |
| `test_seges_display_name.py` | 40 | 1 | 1 |
| `test_system_action.py` (`test_paap_i7`, del fabricante) | 12 | cambiado | 1 |
| **Total T1** | | **48 nuevos** | **48** |

- **Neutralizaciones** (decisión 141): una por parche, con la batería de `pns_ai_mcp` (356 tests), la copia previa
  en el scratchpad y el sha256 comprobado al restaurar. Todas dan las F esperadas y todas las restauraciones, el
  mismo sha256. Después, los 11 archivos del `[FIX]` tienen el sha256 del final del paso de código.

| N | Qué se revierte | Log | F |
|---|---|---|---|
| N12 | `settings_admin_error` devuelve `None` | `tests-20261124-174925.log` | 12, con `test_paap_i7` (detalle debajo) |
| N32 | `_check_settings_admin` sin efecto | `tests-20261124-175107.log` | 13: los 8 negativos, con subtests |
| N16 | `safe_operation.py` de HEAD | `tests-20261124-175246.log` | 2: los de `verification` (decisión 152) |
| N17 | diario y `safe_plan_execute.py` de HEAD | `tests-20261124-175421.log` | 4 |
| N19 | `fetch_url_safe.py` y `mcp_client.py` de HEAD | `tests-20261124-175555.log` | 2 |
| N33 | alias `month_usage` y el asistente de HEAD | `tests-20261124-175727.log` | 6 en 5 tests (detalle debajo) |
| N40 | sin `_compute_display_name` | `tests-20261124-175908.log` | 1 |

  - N16 (decisión 152): 2 líneas `ERROR` de `safe_operation` («MCP: Error executing plan …» y «execute_plan_now …
    failed: You are not allowed to …»). Sin `check_identity`, la llamada por RPC llega a ejecutar el plan, que
    falla; con el parche no aparecen.
  - Detalle de N12: `test_propose_rejected_without_settings`, `test_propose_rejected_with_access_rights`,
    `test_confirmed_add_group_rejected_without_settings`, `test_confirmed_remove_group_rejected_without_settings`,
    `test_registry_edit_does_not_lift_check`, `test_direct_methods_rejected_without_settings`,
    `test_context_identities_checked`, `test_view_actions_unchanged_for_ai_admin`,
    `test_crud_res_groups_refused_without_settings`, `test_plan_confirmed_for_ai_admin_refused`,
    `test_sudo_in_plan_context_refused` y `test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin`.
  - Detalle de N17: `test_ai_admin_write_refused`, `test_ai_admin_create_refused`,
    `test_plan_unlink_requires_unlink_right` y `test_rejected_plan_journals_failed_row`. N19:
    `test_custom_auth_header_dropped_on_other_host` y `test_mcp_client_redirect_refused`. N33:
    `test_month_usage_rpc_refused` (interno y portal), `test_usage_wizard_default_get_rpc_refused` y
    `test_usage_wizard_onchange_rpc_refused` (interno), `test_month_usage_public_name_gone` y
    `test_default_get_refused_for_internal`.
- **Línea base para T2:** `0 failed, 0 error(s) of 378 tests`, 5 omitidos, «RESULTADO: OK»; laboratorio,
  `16 failed, 0 error(s) of 56 tests`. La línea base para T1 de la sección 5 («queda en F por diseño») la sustituye
  la decisión 140.
- **Lint** (`python3 ~/.claude/hooks/odoo_lint.py --revisar pns_ai_mcp/`): 2 incidencias nuevas, las de la decisión
  146 en `ai_trusted_action.py` (I001 en la L24 y C0415 en la L94), aceptadas como en la 14
  (`14.0:docs/pendiente/parches_pns_ai.md:3082`); 0 en los tests nuevos; 552 preexistentes, del fabricante.
- **Entorno:** comprobado antes y después. `odoo-dev 17 estado` igual (BD `lab_pns_ai_3996_17`,
  `CONF_HASH=c5c7138b608673bb`), `bd-lista` sin `test_…` y el mismo sha256 de los `.py` de `seges_pruebas_3996`
  (`b5e46c60…`). La BD del laboratorio queda con el código de T1 (decisión 149).
- **Registro:** en `docs/pendiente/parches_pns_ai.md`, las filas 12, 16, 17, 19, 32 y 33, «Validado en el
  laboratorio» con `f70c3c0` (decisión 145; la del 12 cita la 140); la fila del 40 (F1-2) en las correcciones de
  la fase 1, y la frase de «Marcadores» sobre `F1` y `F1-n` (decisión 148).
- **Commits** (los hace Sergio): `[FIX]` `f70c3c0` («[FIX] pns_ai_mcp: parches 12, 32, 16, 17, 19 y 33 portados a
  17.0.3.1.996 y F1-2 (T1)»); `[ADD]` `dfcf7e0` («[ADD] pns_ai_mcp: tests de Seges de los parches 12, 32, 16, 17,
  19 y 33 y de F1-2 en la 17 (T1)»); `[DOC]`, el de este registro.
- **Para el staging** (decisión 150; se actualiza `pns_ai_mcp`):
  - 16: en Autorizaciones, Confirmar pide la contraseña (una vez cada 10 minutos). Antes, comprobar que los AI
    Administrators tienen contraseña local; los usuarios sin ella (OAuth o LDAP) no pasan `check_identity`
    (`_check_credentials`);
  - 12: un AI Administrator sin Ajustes no da ni quita grupos con un plan, tampoco con «Permisos de acceso»;
  - 32: un AI Administrator sin Ajustes no crea, cambia ni borra acciones de confianza;
  - 33: «This month» del proveedor, solo para el AI Administrator;
  - 19: un servidor MCP cuya URL redirige da el error «… answered with a redirect …»; revisar antes que las URLs
    MCP configuradas son las finales;
  - 17: revertir una fila del diario y vaciar la papelera siguen funcionando para el AI Administrator;
  - 40: el modelo del proveedor se muestra como «Título (slug)» en el formulario.
- **Para las tandas siguientes:**
  - el hook de lint del kit bloquea el formato con `%` (UP031 y C0209) en las líneas escritas a mano: usar f-string
    (decisión 151). Lo que entra con `git apply` no pasa por el hook;
  - en la 17, `TransactionCase` trabaja en un savepoint por test: nada de `cr.rollback()` ni `cr.commit()` sobre el
    cursor del test. En los tests de la 14 de T3 a T5b (`test_seges_identity_su.py`, `test_seges_box_a_vias.py`,
    `test_seges_sandbox_credentials.py`, `test_seges_sandbox_side_effects.py` y los tres del Chatboo) no hay
    ningún `rollback` del cursor del test;
  - siguen haciendo falta en los tests de la 14: `invalidate_cache` → `invalidate_recordset`/`invalidate_model`,
    `flush()` → `flush_all()`, `xmlid_to_res_id` → `_xmlid_to_res_id`, `convert_file(env, …)` y la firma de
    `onchange` de la 17;
  - la batería de `pns_ai_mcp` sola tiene 356 tests tras T1: es la referencia para las neutralizaciones de las
    tandas de `pns_ai_mcp`;
  - en el contenedor, `docker run --rm -i` (sin `-i`, el heredoc no llega) y Python fuera del directorio de
    `odoo` o con `-I` (si no, `import logging` carga `odoo/logging.py`).

## 7. T2: parches 21 y 36

- **Fecha:** 24/11/2026. Partida: HEAD `22f3d85` («[DOC] pns_ai 17: registro de la tanda T1 (parches 12, 32, 16,
  17, 19, 33 y 40) (fase 2)»), sin cambios locales.
- **Fase 1** (solo lectura, 24/11/2026). Las citas del core son del contenedor del laboratorio
  (`/usr/lib/python3/dist-packages/odoo`, Odoo 17.0-20260908); las de `pns_base`, de R17 (`operation_report_wizard.py`
  de `22f3d85`):
  - `git apply --check` falla en los 4 trozos, también uno a uno: el 21 en `:4` (R17 ya no importa `ast` ni
    `json`), `:288` (`invalidate_cache()` es `self.env.invalidate_all()`, `:295`) y `:308` (`pns_import_preview` es
    `form_view_ref`, `:317`); el 36 en `:367` (las dos funciones `_inject_*` son ahora `_inject_screen_arch`,
    `:329-342`, con `postprocess_and_fields`, y `fields_view_get` es `get_view`, `:354-365`);
  - 21 en R17: sin volcado antes del `SAVEPOINT` (`:315`); tras el `ROLLBACK TO SAVEPOINT` (`:324`),
    `invalidate_all()` vuelca lo que la importación dejó pendiente (`odoo/api.py:719-728` y `:735-739`) y queda;
    `Cache.invalidate()` sin argumentos solo vacía `_data`, no `_dirty` (`api.py:1306-1307`), e `invalidate_all` no
    toca `tocompute`; `Cursor.clear()` vacía la caché con `_dirty`, `tocompute` y el `precommit`
    (`odoo/sql_db.py:140-144`, `api.py:881-884` y `:1321-1325`);
  - el core: `Cursor.flush()` es `transaction.flush()` más `precommit.run()` (`sql_db.py:134-138`, `api.py:870-879`);
    `_FlushingSavepoint` hace `cr.flush()` al abrir y `cr.clear()` en el `rollback` (`sql_db.py:101-108`). `Cursor` y
    `TestCursor` no redefinen `flush` ni `clear` (`BaseCursor`, `:121`);
  - `has_group`: `_has_group` con `ormcache('self._uid', 'group_ext_id')` (`odoo/addons/base/models/res_users.py:1098`);
    el `ROLLBACK` no lo deshace. `registry.clear_cache()` vacía `default` y `templates.cached_values`
    (`odoo/modules/registry.py:50-55` y `:716-724`) y lo avisa a los demás workers al final de la petición
    (`:858-885`); `ormcache.clear` está obsoleto y vacía más (`odoo/tools/cache.py:111-114`). Es el mismo coste que
    escribir grupos (`res_users.py:758`);
  - 36: `ir.ui.view` solo lo lee `base.group_system` (`odoo/addons/base/security/ir.model.access.csv:34-35`); `env.ref`
    no comprueba permisos (`browse` y `exists`) y el `AccessError` sale en `src.arch` (`:333`). El core lee la vista en
    `sudo` (`odoo/addons/base/models/ir_ui_view.py:2534`), la procesa con `postprocess_and_fields` en `sudo` en
    `_get_view_cache` (`:2596-2632`) y después `get_view` aplica `check_access_rights('read')` y
    `_postprocess_access_rights` con el usuario (`:2635-2666`). `get_view` de R17 solo llama a `_inject_screen_arch`
    con las dos pantallas fijas (`:356`) y ya comprobó la lectura del asistente con el usuario (`:358`);
  - comprobaciones previas de la parte 1 (paso 0): `_invalidate_after_preview_rollback` solo se llama desde
    `action_preview` (`:322` y `:326`) y nadie la redefine; en los dos caminos, tras el `ROLLBACK` van el `RELEASE`, la
    invalidación y, después, `raise` (relanza) o `_apply_import_preview` (sus escrituras en el asistente,
    `_store_operation_result`, `:225`, van siempre después); `_preview_snapshot` (`:275-292`) solo lee y devuelve
    datos simples; en los `action_import` de los 17 asistentes y en lo de `pns_*` que importan solo aparecen el
    `with env.cr.savepoint()` de `pns_ai_mcp/utils/config_backup.py:676` y el cursor propio de
    `pns_ai_mcp/models/ai_agent.py:1405` (`openapi_spec_generate_wizard.py:242` y `progress_job.py` no heredan el
    mixin);
  - módulo de los tests: `pns_ai_mcp`. `pns_base` solo depende de `web` y `mail`, y los tests necesitan los asistentes
    de `pns_ai_mcp`, `ai.mcp.user`, `ai.provider` y `group_ai_admin`; como en la 14 y en la clasificación.
- **Archivos:**
  - código (`[FIX]`, 1): `pns_base/models/operation_report_wizard.py` (387 líneas, `2b5c71f7…a17a4`);
  - tests (`[ADD]`, 3): `pns_ai_mcp/tests/`: `__init__.py` (bloque de Seges de T2; 60 líneas, `e4ee77bb…6808`) y,
    nuevos, `test_seges_import_preview.py` (258, `62a9ae32…0074`) y `test_seges_review_views.py` (245,
    `1a5178a9…d788`).
- **Cambios respecto a `14.0` en el código** (a mano; 5 marcadores; líneas nuevas de 88 caracteres como máximo, sin
  `%`):
  - 21: la 14 volcaba antes y dentro del `SAVEPOINT` (también en el `except`, con `contextlib.suppress`) y, tras el
    `ROLLBACK`, hacía `cr.precommit.clear()`, `env.clear()` y `registry.clear_caches()`. En la 17, la decisión 153:
    `cr.flush()` antes del `SAVEPOINT` (`:323-327`), `env.flush_all()` tras `action_import()` (`:331-335`) y, en
    `_invalidate_after_preview_rollback` (`:294-303`), `cr.clear()` y `registry.clear_cache()`;
  - 36: `src = self.env.ref(xmlid).sudo()` en `_inject_screen_arch` (`:350-354`), que cubre las dos pantallas (en la
    14 eran dos `.sudo()`, uno por función).
- **Cambios respecto a `14.0` en los tests** (los dos llevan en la cabecera las líneas de la 14 sin cambios y la línea
  de la 17, decisiones 128 y 134; nombres, decisión 158):
  - `test_seges_import_preview.py` (`TestSegesImportPreview`, `seges_e2p`): los 4 casos de `TestImportReview` del
    laboratorio (los de la 14 adaptados a la 17: SQL con `ctid` y valor, y `has_group` visto durante la vista
    previa); la lectura ORM sin invalidar en `test_providers_review_writes_nothing` y el `[GUARD]`
    `test_caller_pending_write_survives_review` (decisión 155: el campo, en `get_dirty_fields()` y no en el SQL antes;
    en el SQL justo tras «Review», tras `flush_all()` y por el ORM). Sin `invalidate_cache`, `env['base'].flush()`
    ni `cr.rollback()`;
  - `test_seges_review_views.py` (`TestSegesReviewViews`, `seges_e2p`): los 6 casos de `TestReviewViews` del
    laboratorio (`get_view` con `form_view_ref` en lugar de `fields_view_get` con `pns_import_preview` y
    `pns_operation_result`; `invalidate_recordset()`) y `test_admin_gets_config_backup_screens` (decisión 156);
  - los docstrings citan las líneas del archivo final; 3 líneas copiadas del laboratorio miden de 89 a 91
    caracteres (decisión 159);
  - `tests/__init__.py`: el bloque de Seges de T2, debajo del de T1.
- **`odoo-dev 17 actualizar pns_base`** (decisión 157; log `actualizar-20261124-215349.log`): «RESULTADO: OK», 0
  bloqueantes y 0 `ERROR`. Arrastra a `pns_ai_mcp` y `pns_ai_chatboo`; los 5 WARNING del fabricante de T1. El
  servidor web se reinicia.
- **Baterías** (desde el laboratorio):
  - tres módulos (log `tests-20261124-215513.log`): `0 failed, 0 error(s) of 390 tests`, «RESULTADO: OK», sin
    líneas `ERROR`. Omitidos (5), los de T0;
  - `seges_pruebas_3996` (log `tests-20261124-215843.log`): `9 failed, 0 error(s) of 56 tests`. Frente a
    `tests-20261124-174709.log`, pasan a verde los 7 `[HYPOTHESIS]` de los puntos 3 y 4 de la clasificación y no
    hay rojos nuevos: `TestImportReview` (`test_users_review_writes_nothing`, `test_providers_review_writes_nothing`
    y `test_users_review_keeps_groups`) y `TestReviewViews` (`test_admin_gets_review_screen`,
    `test_admin_gets_result_screen`, `test_admin_users_review_and_result` y `test_admin_servers_review_and_result`).
- **Por archivo:**

| Archivo | Parche | Casos de T2 | Verdes |
|---|---|---|---|
| `test_seges_import_preview.py` | 21 | 5 | 5 |
| `test_seges_review_views.py` | 36 | 7 | 7 |
| **Total T2** | | **12 nuevos** | **12** |

- **Neutralizaciones** (decisiones 141 y 155): con la batería de `pns_ai_mcp` (368 tests), la copia previa en el
  scratchpad y el sha256 comprobado al restaurar; las F previstas, escritas antes de ejecutar cada una. Todas dan las
  F previstas y todas las restauraciones, el sha256 del archivo final (`2b5c71f7…a17a4`). Las líneas `ERROR` de cada
  log son solo las de sus F y la del resumen.

| N | Qué se quita | F previstas | F obtenidas | Log |
|---|---|---|---|---|
| N21 | los cambios del 21 (el 36 se queda) | 3 | 3 (detalle debajo) | `tests-20261124-220205.log` |
| N21a | el `cr.flush()` previo | 1 | 1: `test_caller_pending_write_survives_review` | `tests-20261124-220530.log` |
| N21b | el `cr.clear()` | 1 | 1: `test_providers_review_writes_nothing` (ORM) | `tests-20261124-220832.log` |
| N21c | el `registry.clear_cache()` | 1 | 1: `test_users_review_keeps_groups` | `tests-20261124-221155.log` |
| N36 | el `.sudo()` | 5 | 5 (detalle debajo) | `tests-20261124-221517.log` |

  - N21: `test_users_review_writes_nothing` (`ctid` y etiqueta cambiados), `test_providers_review_writes_nothing`
    (la lectura ORM da 0.42) y `test_users_review_keeps_groups` (`has_group` en `True`). N21a: justo tras «Review»,
    el SQL da `None` (lo del llamador se volcó dentro del savepoint y se perdió). N21b: la caché se queda con 0.42.
  - N36: `test_admin_gets_review_screen`, `test_admin_gets_result_screen`, `test_admin_users_review_and_result`,
    `test_admin_servers_review_and_result` y `test_admin_gets_config_backup_screens`; F, no E (el `AccessError` se
    recoge en la lista de problemas).
- **Línea base para T3:** tres módulos, `0 failed, 0 error(s) of 390 tests`, 5 omitidos, «RESULTADO: OK»
  (`tests-20261124-215513.log`); `seges_pruebas_3996`, `9 failed, 0 error(s) of 56 tests`
  (`tests-20261124-215843.log`). La batería de `pns_ai_mcp` sola tiene 368 tests.
- **Lint** (`python3 ~/.claude/hooks/odoo_lint.py --revisar <modulo>/`): 0 incidencias nuevas en `pns_base/`
  (`operation_report_wizard.py`, 24 preexistentes, del fabricante) y en `pns_ai_mcp/` (los dos tests nuevos, sin
  preexistentes; `tests/__init__.py`, las 2 preexistentes: `UP009` e `I001`, decisión 137).
- **Entorno:** comprobado antes y después. `odoo-dev 17 estado` igual (BD `lab_pns_ai_3996_17`,
  `CONF_HASH=c5c7138b608673bb`), `bd-lista` sin `test_…` y el mismo sha256 de los `.py` de `seges_pruebas_3996`
  (`b5e46c60…`). La BD del laboratorio queda con el código de T2 (decisión 157).
- **Registro:** en `docs/pendiente/parches_pns_ai.md`, las filas 21 y 36, «Validado en el laboratorio» con
  `b391159`.
- **Commits** (los hace Sergio): `[FIX]` `b391159` («[FIX] pns_base: parches 21 y 36 adaptados a la 17 (PNS-20,
  PNS-103) (T2)»); `[ADD]` `0e41cab` («[ADD] pns_ai_mcp: tests de Seges de los parches 21 y 36 en la 17 (T2)»);
  `[DOC]`, el de este registro.
- **Para el staging** (decisión 150; se actualiza `pns_base`):
  - 21: como AI Administrator, pulsar «Review» en los usuarios MCP (etiqueta y AI Writer) y en los proveedores
    (temperatura). Nada cambia, el usuario no gana el grupo (menús, sin volver a entrar) y «Apply» sí aplica. Una
    importación que falle en «Review» muestra el error y no deja nada escrito. En el log aparece un INFO «Caches
    invalidated… ['default']» en cada «Review»: es esperado;
  - 36: un AI Administrator sin Ajustes, con y sin «Permisos de acceso», abre las pantallas de revisión y de
    resultado en los dos asistentes, en la copia de configuración y en otro asistente cualquiera (por ejemplo, la
    importación de skills). Un usuario sin AI Administrator sigue rechazado.
- **Para las tandas siguientes:**
  - observación de R17 (decisión 154): `_inject_screen_arch` no aplica `_postprocess_access_rights` por usuario
    (el core lo hace en `get_view`, `ir_ui_view.py:2635-2666`). No lo amplía el `sudo` y hoy no tiene efecto: las
    pantallas no tienen `groups=` ni los campos del mixin, y solo quedarían sin marcar `create`, `edit` y `delete` del
    formulario;
  - el `postcommit` de la vista previa no se vacía, igual que en el core (`cr.clear()` no lo toca); como mucho, un
    aviso del bus sin efecto;
  - `pns_ai_mcp/models/ai_agent.py:1405`, `_persist_cache_isolated`: cursor propio con `commit`; solo localizado, y
    no se llega a él directamente desde ningún `action_import`;
  - el savepoint anidado de `pns_ai_mcp/utils/config_backup.py:676` (`_FlushingSavepoint`) es compatible con la 153:
    vuelca y limpia solo lo de la vista previa, porque lo del llamador ya está volcado.
