# Plan de portado de los parches de Seges a pns_ai 3.1.973

- **Fecha:** 10/11/2026 (propuesta y decisiones) · 11/11/2026 (fases 0 y 1; fases 2a y 2b) · 12/11/2026 (fase 3a) · 13/11/2026 (planificación hasta el staging).
- **Decisión:** camino B de la [comparación con 3.1.973](../specs/comparacion_pns_ai_3-1-973.md), §8: pasar a
  3.1.973 entera y volver a portar los parches de Seges ([decisiones](pns_ai_decisiones.md), N15; Sergio,
  10/11/2026).
- **Rama:** `14.0-pns-ai-3973`, creada por Sergio con GitHub Desktop desde `14.0-pns-ai-3879` en `3feb224`.
- **Base nueva:** `pns_base` 14.0.1.2.69 · `pns_ai_mcp` 14.0.3.1.973 · `pns_ai_chatboo` 14.0.2.1.587
  (`_fabricante/3.1.973/ORIGEN.txt`).
- **Reglas:** las del CLAUDE.md del repo para módulos de terceros (registro, marcador, test y neutralización)
  y las del [registro de parches](parches_pns_ai.md). Los parches portados conservan su número. Commits:
  tres por fase (código, tests y documentación), salvo el de la base limpia. Los hace Sergio.
- **Aprobación:** fase a fase, por Sergio.
- **Entornos:**
  - Laboratorio nuevo `lab_pns_ai_3973` (BD `lab_pns_ai_3973_14`), que monta la copia de trabajo de
    `third_party`. Se crea en la fase 1; al arrancarlo sustituye al contexto activo de `lab_pns_ai_973`, cuya
    BD y carpeta no se tocan (aceptado por Sergio, 11/11/2026).
  - `lab_pns_ai_973` queda como referencia de 3.1.973 sin cambios.
  - `lab_pns_ai_3879` monta la misma copia de trabajo (`COMPARTIDOS="third_party"`): mientras el repo esté
    en `14.0-pns-ai-3973`, **no se arranca, ni se reinicia, ni se actualiza** (cargaría 3.1.973).
    - Su BD `lab_pns_ai_3879_14` **no es fiable** desde el 12/11/2026 y no se vuelve a usar como referencia
      (decisión de Sergio, 13/11/2026; ver «Planificación hasta el staging»).
  - **`_fabricante/`, trasladado (11/11/2026, hecho):** las versiones del fabricante están en
    `/home/soporte/pns_fabricante`; en el repo queda el enlace `_fabricante` → esa carpeta, excluido con una
    regla en `.git/info/exclude`. La opción del kit para esto no se aplicó. `_fabricante/` no se modifica.

## Decisiones de Sergio (10/11/2026)

1. **Rama:** `14.0-pns-ai-3973`, desde `14.0-pns-ai-3879` en `3feb224`.
2. **Laboratorio:** nuevo, `lab_pns_ai_3973` (BD `lab_pns_ai_3973_14`), que monta la copia de trabajo.
   `lab_pns_ai_973` queda como referencia; `lab_pns_ai_3879` no se reinicia ni se actualiza mientras el repo
   esté en la rama nueva.
3. **Parche 18, opción B:** vaciar solo las columnas secretas al abrir la caja A, en `open_readonly_env`, con
   el mismo criterio que `secret_column` del fabricante. P-22 se ejecuta justo después (fase 3), con el
   criterio fijado antes: ver la fase 3.

   **Parche 18 (12/11/2026):** la opción B sola no basta (V1 a V4 confirmadas). Se aplica O1: en la caja A y sin su,
   se rechaza la lectura de una columna con `_pns_hidden_column` verdadero o, salvo `id`, de un modelo sin permiso de
   lectura, venga de la caché o de un cálculo, en `_read_attr`, `__getitem__` y `mapped` de `base`, más el cuarto
   enganche sobre objetos `Field` (`mapped`, `compute_value`). B (vaciado al abrir) y B2 (tras cada helper) quedan como
   defensa.
4. **Crons de NUEVO-2, opción (b):** script `migrations/14.0.3.1.973/post-migrate.py` como parche de Seges,
   el **35** (número asignado por Sergio el 11/11/2026). Ver «Parche 35: crons de NUEVO-2».
5. **Tests del parche 23:** se quitan unos y se adaptan otros. Ver la fase 3.
6. **CSP del parche 27:** se mantiene la cabecera HTTP del fabricante y se añade la `<meta>` de Seges. Ver la
   fase 4.

## Datos de partida (fase 0, 10/11/2026)

- La rama `14.0-pns-ai-3879` es exactamente 3.1.879 más lo de Seges: `diff -rq` frente a
  `_fabricante/3.1.879` da 49 diferencias, todas asignadas:

  | Tipo | N.º | Detalle |
  |---|---|---|
  | Archivos con parches | 29 | 117 bloques, todos con su parche (parches 10 a 34) |
  | Archivos propios | 2 | `box_a_guard.py` (18) y `relaxaicode_format_guard.py` (23 ampliado) |
  | Tests de Seges | 15 + 1 | 14 `test_seges_*` de `pns_ai_mcp`, la carpeta `pns_ai_chatboo/tests` y los imports de `pns_ai_mcp/tests/__init__.py` |
  | E0′ | 2 | `test_change_journal.py` y `test_paap_core.py` |

- **Copias de trabajo, fuera del repo:** `~/pns_ai_3973/fase0/`.
  - `diffs/`: un `.diff` por archivo, `diff -u _fabricante/3.1.879/<archivo> <archivo>`, con `/` → `+` en
    el nombre.
  - `bloques_parches_final.tsv`, `resumen_por_parche.tsv` y `asignacion_49.tsv`: bloque → parche.
  - `tests_seges/` y `propios/`: los tests de Seges, `common.py`, los dos `tests/__init__.py`,
    `box_a_guard.py` y `relaxaicode_format_guard.py`.
  - `modulos_3879/`: los tres módulos de la rama 3879, para instalar 3.1.879 en P-2 y P-14.
  - `sha256_copias.tsv`: 736 archivos. Comprobados de nuevo en el destino el 11/11/2026: todos coinciden.
- **Bloques que mezclan parches** (hay que separarlos a mano al portar). Son 8 bloques de código, en 5
  archivos (en la propuesta del 10/11/2026 se contaron por error como «siete»):

  | Archivo | Bloque | Parches |
  |---|---|---|
  | `pns_ai_mcp/controllers/validators_base.py` | 1 | 15 y 22 |
  | `pns_ai_mcp/controllers/context_builder.py` | 5 | 24 y 23 |
  | `pns_ai_mcp/controllers/context_builder.py` | 6 | 23 y 24 |
  | `pns_ai_mcp/controllers/tools_relaxaicode.py` | 1 | 18 y 23 |
  | `pns_ai_chatboo/models/chatboo_session.py` | 1 | 25 y 18 |
  | `pns_ai_chatboo/models/chatboo_session.py` | 4 | 25 y 29 |
  | `pns_ai_chatboo/models/chatboo_canvas.py` | 1 | 34, 29 y 27 |
  | `pns_ai_chatboo/models/chatboo_canvas.py` | 2 | 27 y 29 (cada frase del prompt con su marcador) |

  `pns_ai_mcp/tests/__init__.py` (bloque 1) junta además los imports de las entregas E0′, E1′, E2′ y E4′.
- **Marcador que falta en la rama 3879:** en `pns_ai_mcp/utils/skill_runtime.py`, el import de
  `run_sandbox_code` (parche 23 ampliado) no lleva marcador; lo lleva el bloque siguiente. Desaparece con el
  parche 23, que se retira.
- **Archivos parcheados que 3.1.973 no cambia:** `ai_change_journal.py`, `privilege_cusp.py`,
  `ai_provider_usage_wizard.py`, `chart.umd.min.js` y `chatboo_heavy_libs.js`.
- **Permisos:** los archivos de `_fabricante/3.1.973` están en `600` (como en el zip); al copiarlos, `644`
  y `755` para las carpetas.
- El fabricante ya marca el cursor de la caja A en `open_readonly_env` (`SANDBOX_CURSOR_FLAG`,
  `controllers/controller_helpers.py:193`).

## Fase 1 — Rama, 3.1.973 limpia, documentación y línea base

1. **1a (11/11/2026, hecho):**
   - `fase0` copiada a `~/pns_ai_3973/fase0` y sha256 comprobados (736 de 736).
   - `lab_pns_ai_3879`, parado. El Odoo 14 activo era el de `lab_pns_ai_973`: sin `--dev` y sin montar
     `third_party`.
2. **1b (11/11/2026, hecho):**
   - `pns_*` igual que `modulos_3879`;
   - los tres módulos, sustituidos por los de `_fabricante/3.1.973`, sin `ORIGEN.txt` ni `__pycache__`, con
     `chmod -R u=rwX,go=rX`;
   - `diff -rq` vacío (657 archivos); ninguno sin lectura para otros;
   - fuera de las tres carpetas, sin cambios (sha256 de 2483 archivos en `~/pns_ai_3973/fase1/`).
   - Commit de Sergio: «[IMP] pns_ai: base 3.1.973 del fabricante, sin cambios».
3. **1c:** este plan, el registro de parches («Cambio de base a 3.1.973»), la decisión N15 y la frase de la
   base en el CLAUDE.md del repo. Commit de Sergio: «[DOC] pns_ai: plan y registro del cambio de base a
   3.1.973».
4. **1d (11/11/2026, hecho):**
   - `lab_pns_ai_3973` según el MANUAL (6.7); los comandos se presentan a Sergio antes de ejecutarlos;
   - `paridad` e instalación limpia de `pns_ai_chatboo` (log `instalar-20261111-110830.log`);
   - tests de los tres módulos: es la **línea base del fabricante en 3.1.973** (F y E por nombre;
     `test_web_client` necesita Chrome). Sin el parche 12, `test_paap_i7_…` debería pasar.
   - **Resultado** (log `tests-20261111-111101.log`): **246 tests, 0 F, 0 E y 4 saltados**
     (`TestWebClientStarts.test_backend_starts_without_errors`, sin Chrome;
     `TestRequiredFieldsLive.test_a_pending_field_is_left_on_the_record_itself`; y
     `TestSandboxSecretRead.test_typed_readers_keep_secret_keys_out` y
     `test_typed_setters_do_not_return_a_secret`). `test_paap_i7_…` pasa.
   - **Falso «FALLO» del analizador:** el resumen de `odoo-dev` marca «FALLO» por la línea
     `ERROR … ai_change_journal: AI change journal: snapshot read failed on res.partner`, que es un log
     esperado de `TestOneCompanyLive.test_plan_cannot_touch_the_other_company` (la regla multicompañía
     niega la lectura y el diario lo anota), no un test fallido. Manda la línea del runner
     (`0 failed, 0 error(s) of 246 tests`). Se repetirá en cada batería: no cuenta como F ni E.

## Fase 2 — Parches que aplican igual o con desplazamientos

Método:
- el `.diff` de la fase 0 con `patch --dry-run`; lo que no entra, a mano;
- después, lint, tests y neutralización.

**Fase 2a (aprobada por Sergio el 11/11/2026):** parches 21, 20, 17, 33, **12, 32** y 16, en ese orden. El
12 va antes que el 32 porque `_check_settings_admin` (32) importa `settings_admin_error` (12): sin el 12,
cualquier `create` de `ai.trusted.action`, también la carga de datos al instalar, daría `ImportError`. En la
neutralización del 12 fallan también, como es esperado, los negativos del 32 que dependen de
`settings_admin_error`. Tests: los de Seges de estos parches, más `test_seges_safe_operation` como no
regresión del 13 (M10 del fabricante, regex con su mensaje). En `test_seges_e4p`, los casos del 30 y del 31
se adaptan a los nombres privados: `test_log_own_rpc_allowed` pasa a negativo (`AttributeError`: el
fabricante cierra también la escritura a nombre propio por RPC) y los controles en Python
(`test_own_row_written`, `test_sudo_call_works`) llaman al método privado equivalente.

| Parche | Archivos en 3.1.973 | Ajuste | Test |
|---|---|---|---|
| 21 | `pns_base/models/operation_report_wizard.py` | Ninguno | `test_seges_import_preview` |
| 20 | `chart.umd.min.js`, `chatboo_heavy_libs.js` | Copiar los de la rama | Manual: gráfico en el chat |
| 17 | `ai_change_journal.py`; `controllers/safe_plan_execute.py:221-226` | Paso `unlink` en su archivo nuevo | `test_seges_change_journal` |
| 33 | wizard; `ai_provider.py:1096, 1132` | Desplazado | `test_seges_e4p` (33) |
| 32 | `ai_trusted_action.py` | Helper sobre el bloque SQL cambiado (`:77-85`) | `test_seges_e4p` (32), `test_seges_user_groups` |
| 12 | `ai_system_action.py:728-786`; `privilege_cusp.py` | Con el plan como solicitante (`with_user`): gana el más estricto | `test_seges_user_groups`; `test_paap_i7…` vuelve a F por diseño; P-5 con el 12 |
| 16 | `safe_operation.py:1796, 2034-2063` | Desplazado | `test_seges_verification`, `test_seges_safe_operation` |
| 15 | `validators_base.py:230-266` | Solo los 9 nombres que siguen públicos | `test_seges_rpc_access`, `test_seges_chatboo_export` (corregir `test_fulfill_client_export_claims_own`), `test_seges_chatboo_access` |
| 22 | `validators_base.py:257-265` | Los 21 nombres que faltan | `test_seges_sandbox_side_effects` |
| 19 | `fetch_url_safe.py:122-135`; `mcp_client.py` | Junto a la comprobación del par (`:47-68`) | `test_seges_fetch_redirect`; P-7 |
| 11 | `chatboo_session.py:1976-2033` | `write` nuevo encima | `test_seges_chatboo_access` |
| 26 | `chatboo_session.py:937`; `chatboo_canvas.py:910` | `sudo` → `env(su=False)` | `test_seges_chatboo_canvas` |
| 25 | `chatboo_canvas.py:924, 948` | Solo la comprobación de dueño (`_paint_canvas` ya es privado) | `test_seges_chatboo_canvas` |
| 28 | `chatboo_canvas_page.py:71-94`; `security.xml:67-76` | Sin la parte de `owner_id` (la cierra el fabricante) | `test_seges_chatboo_canvas` |

**Fase 2b (aprobada por Sergio el 11/11/2026, con condiciones; hecha el 11/11/2026):** parches 15, 22, 19, 11, 26, 25
y 28. Detalle en el [registro](parches_pns_ai.md), «Parches de la rama 14.0-pns-ai-3973 (fase 2b)».
- Correcciones a la tabla anterior (no se reescribe):
  - el 22 lleva **22** nombres, no 21 (el fabricante tiene 6 de los 28);
  - el 25 va en `chatboo_session.py`, `_paint_canvas` (`:1085-1087`): los llamadores de `chatboo_canvas.py` ya
    usan el nombre privado.
- Tests: los de Seges de estos parches, `test_seges_chatboo_smoke` (E0′, sin parche) y el caso (b) de P-5 en
  `test_seges_user_groups`. Adaptados a 3.1.973: `test_seges_rpc_access` (imports de `safe_plan_http` y
  `safe_plan_execute`), `test_seges_chatboo_export` (16 nombres ya privados) y `TestSegesSharedPage` (alta solo en
  `su`; `test_same_owner_refused_too`). De `test_seges_chatboo_canvas`, solo los casos de 25, 26 y 28.
- Resultado (log `tests-20261111-135129.log`): **382 tests, 1 F (`test_paap_i7`, por diseño), 0 E y 4 saltados**;
  76 nuevos frente a la 2a. 10 neutralizaciones, todas con el resultado previsto y SHA-256 igual al restaurar.
  P-7, hecha (N19f y N19m).
- **Segundo falso «FALLO» del analizador**, junto al de `TestOneCompanyLive` (1d): el
  `ERROR odoo.sql_db … ir_attachment_create_uid_fkey` de `test_fulfill_client_export_claims_own`. El test pasa por
  la vía de respaldo del fabricante (`_run_on_committed_cursor`). La línea ya salía en todas las baterías de la
  rama 3879 que lo ejecutan. Detalle en el registro. No cuenta como F ni E.
- Camino del job del botón Canvas (25): queda como prueba manual, sin test nuevo (Sergio, 11/11/2026).

## Fase 2c — Parche 36 (decisión de Sergio, 11/11/2026)

- **Problema** (defecto del fabricante, visto en las pruebas manuales de la fase 2): «Review this import» no abre
  para un AI Administrator sin Ajustes. `_inject_import_preview_arch` y `_inject_operation_result_arch`
  (`pns_base/models/operation_report_wizard.py:369-379`) leen la vista sin `sudo`, e `ir.ui.view` solo lo lee
  `group_system`. Afecta a la importación de proveedores y de usuarios MCP. Detalle en el
  [registro](parches_pns_ai.md), «Pruebas manuales de la fase 2 en `lab_pns_ai_3973` (11/11/2026)».
- **Cuándo:** después de las pruebas manuales de la fase 2 (hechas) y antes de la fase 3.
- **Propuesta** (cambio, test y neutralización): aparte, pendiente de aprobación de Sergio.
- **Aprobada y aplicada (11/11/2026)**, como PNS-103, tipo `funcional`:
  - `.sudo()` sobre las dos vistas (`operation_report_wizard.py:373` y `:380`, marcadores en `:370` y `:379`);
  - tests: `pns_ai_mcp/tests/test_seges_review_views.py` (6, etiqueta `seges_e2p`);
  - batería de los tres módulos: 388 tests, 1 F (`test_paap_i7`), 0 E y 4 saltados;
  - N36p y N36r: 8 E cada una, SHA-256 igual al restaurar;
  - alta de PNS-103 en el seguimiento.

  Afecta a 17 asistentes (no 16; ver el registro, parche 36). La rama 3879 y `pns_demo` tienen el mismo defecto,
  sin parche. Queda la prueba manual: [guía de la fase 2c](lab_fase2c_3973.md).
- **Validado en el laboratorio (12/11/2026):**
  - manual con `seges_aiadm`;
  - por RPC (`load_views`, el camino del navegador) con `seges_access` y `seges_aiadm`, más el negativo con
    `seges_int@example.com`: 32 OK y 0 FALLO.

  Por el camino salió un defecto del fabricante que solo se ve por RPC: `fields_view_get` sin `@api.model` en
  `pns.operation.report.wizard`. No se corrige. Detalle en el [registro](parches_pns_ai.md), «Prueba en el
  laboratorio del parche 36 (12/11/2026)». Fase 2c cerrada.

## Fase 3 — Parches 24 y 18; tests del 23

- `_StubController` pasa a un archivo común de tests (p. ej. `pns_ai_mcp/tests/seges_common.py`): los cinco
  tests que lo importan dejan de depender del test del 18.
- **Parche 24:**
  - `_identity_no_su` tal cual;
  - una rama en `GuardedSandboxEnv.__getattr__` antes de `context_builder.py:138-139`;
  - los globales de `:659-660`;
  - test: `test_seges_identity_su`.
- **Parche 18, opción B (decisión 3):**
  - Al abrir la caja A, en `open_readonly_env`, se invalidan en la caché del hilo solo las columnas secretas,
    con el mismo criterio que `secret_column` del fabricante. No toda la caché, para no perder escrituras
    pendientes del llamador.
  - Test: `test_box_a_engine_cache_before_run` adaptado.
  - Los casos de `test_seges_sandbox_credentials` se reescriben al criterio del fabricante.
  - `test_seges_canvas_box_a` y la ventana de `_ask_design` desaparecen.
- **P-22, justo después**, con este criterio fijado antes de ejecutarla:
  - listar los campos de los 11 modelos que `box_a_guard` cerraba y que el guardián del fabricante deja leer
    en la caja A;
  - marcar cuáles son una credencial o permiten actuar como otro usuario.

  Si sale alguno, se presenta a Sergio, que decide si se pasa a la opción A (con P-20).
- **Tests del parche 23 (decisión 5):**
  - se quitan `test_markup_rejected_unit`, los 11 de `TestSegesEngineNames` y `test_type_itemgetter_class`;
  - los restos (`itemgetter` nativo, `Markup` con campos simples) se anotan en el registro como restos
    conocidos, sin más;
  - los 9 negativos de `test_seges_sandbox_env` pasan a comprobar que se rechaza y que no sale el secreto;
  - `test_allowed_attrs` y `test_engine_attrs_on_wrapper` se invierten al criterio del fabricante.

**Fase 3a (decisiones de Sergio del 12/11/2026; hecha el 12/11/2026):**
- Propuesta, decisiones y condiciones: [propuesta_fase3_3973.md](propuesta_fase3_3973.md). La fase 3 se parte en 3a
  (archivo común, parche 24 y tests del 23) y 3b (parche 18 con B y B2, `test_seges_sandbox_credentials` y P-22).
- Hecho: `pns_ai_mcp/tests/seges_common.py`, parche 24 y los tests de la 3a. Detalle en el
  [registro](parches_pns_ai.md), «Parches de la rama 14.0-pns-ai-3973 (fase 3a)».
- Resultado (log `tests-20261112-112537.log`): **434 tests, 1 F (`test_paap_i7`, por diseño), 0 E y 4 saltados**.
  N24a, N24b y N24c, todas F y con SHA-256 igual al restaurar.
- Correcciones a la propuesta del 12/11/2026: `test_seges_sandbox_env` tiene 12 tests (no 13) y el recuento es 434
  tras la 3a (no 435) y 470 tras la 3b (no 468/469).
- **Antes de la 3b:** el inventario de la decisión 2 encontró cinco vías posibles (V1 a V5, sin comprobar en
  ejecución): cálculos que leen una credencial en `sudo` durante la ejecución y la dejan en la caché del hilo. Se
  presentan a Sergio con las opciones O1 a O3 antes de decidir la 3b.

**Fase 3b (decisiones de Sergio del 12/11/2026; hecha el 12/11/2026):**
- Propuesta, confirmación de V1 a V4, decisiones y resultados: [propuesta_fase3_3973.md](propuesta_fase3_3973.md), desde
  «Confirmación de V1 a V4» hasta «Implementación de la 3b (12/11/2026)». Registro: «Parches de la rama
  14.0-pns-ai-3973 (fase 3b)».
- Hecho:
  - **parche 18** con O1 (decisión 3 revisada), B y B2. El cuarto enganche quedó en lista cerrada: en el sandbox, de
    un objeto `Field` se rechaza cualquier atributo invocable salvo `get_description`;
  - **parche 37** (PNS-104, Baja): `flush` del llamador antes de abrir la caja A;
  - tests: `test_seges_box_a_vias.py` (37), `test_seges_sandbox_credentials.py` (33) y `test_seges_box_a_flush.py`
    (4).
- Resultado: **505 tests tras el 18 (2 F) y 508 tras el 37 (1 F, `test_paap_i7`), 0 E y 4 saltados** (logs
  `tests-20261112-144029.log` y `tests-20261112-152957.log`). Neutralizaciones N18a a N18h y N-flush: todas F y con
  SHA-256 igual al restaurar.
- Pendiente: la prueba en `lab_pns_ai_3973` y P-22, con sus scripts presentados antes. Fuera de la 3b: PNS-105,
  `iap.account.get` (P2), los `new()` del llamador y el laboratorio con el core de LIYBEN.

**Fase 3b, laboratorio y P-22 (12/11/2026, hechos):**
- **Laboratorio:** reinicio sin `-u`, `p18_lab.py` (V3 rechazado; lecturas normales OK; `ai_log` 61 → 61) y dos turnos
  de Chatboo como `seges_int@example.com`, sin errores. La página `/chatboo/canvas/8` la comprobó Sergio.
- **P-22:** credenciales en claro en `ai.key.pin.ask` (`pin`, `supplied_key`) y `ai.api.key.wizard` (`generated_key`,
  `manual_key`), y el `display_name` del desk, que es su token. El fabricante cierra esos modelos en su puerta, pero un
  `Reference` la salta.
  - Decisión de Sergio: opción 3(b) como ampliación del parche 18 (`_pns_secret_fields`, con el desk).
  - Se acepta que esos campos salgan vacíos en las exportaciones nativa y portable.
- **Resultado:** 510 tests, 1 F (`test_paap_i7`), 0 E y 4 saltados (log `tests-20261112-165632.log`); N18p con F en los
  5 subtests.
- Detalle en la [propuesta](propuesta_fase3_3973.md), «Laboratorio de la 3b», «P-22» e «Implementación de P-22», y en
  el [registro](parches_pns_ai.md), «Parche 18 ampliado por P-22».
- **Fuera de la 3b, pendiente de decidir:**
  - limitar el servidor del laboratorio (sin `dbfilter` ni `db_name`, ejecuta los crons de todas las BD);
  - la fiabilidad de `lab_pns_ai_3879_14`, sobre la que corrieron dos crons de `pns_*` con código de 3.1.973 el
    12/11/2026.
  - **Decidido el 13/11/2026:** procedimiento fijo del laboratorio, sin limitar el servidor, y `lab_pns_ai_3879_14`
    no fiable. Ver «Planificación hasta el staging», punto 2.

## Planificación hasta el staging (decisiones de Sergio, 13/11/2026)

Orden:
1. **Cierre del parche 38 (PNS-105):** hecho el 13/11/2026 (parche, laboratorio con la salvedad de la apertura 24
   aceptada, y seguimiento). Detalle en la [propuesta](propuesta_fase3_3973.md),
   «Implementación del parche 38 (13/11/2026)»
   y «Laboratorio del parche 38 (13/11/2026)», y en el [registro](parches_pns_ai.md), «Parche 38 (PNS-105, datos)».
2. **Procedimiento del laboratorio:** el servidor de Odoo 14 del kit arranca sin `dbfilter` ni `db_name` y ejecuta los
   crons de toda BD cuyo registro se cargue. No se limita el servidor ni se cambia el kit: la mitigación del laboratorio
   del parche 38 pasa a ser el **procedimiento fijo** de todo laboratorio de esta rama. Procedimiento:
   [lab_procedimiento_3973.md](lab_procedimiento_3973.md).
   - **`lab_pns_ai_3879_14` no es fiable:** el 12/11/2026 corrieron sobre ella dos crons de `pns_*` con código de
     3.1.973. No se vuelve a usar como referencia. P-2 (a) y (b) y P-14 se hacen en BD nuevas instaladas con
     `~/pns_ai_3973/fase0/modulos_3879`, nunca sobre ella.
3. **Fase 4** (abajo).
4. **Pruebas con toda la rama** («Pruebas posteriores», punto 4), con la **versión del core del staging** comprobada en
   el código montado y no con `dpkg`, como en LIYBEN (propuesta, «Datos de LIYBEN»). **`iap.account.get` (P2) se
   decide antes** de estas pruebas (propuesta, «Hallazgos de P1 a P3»).
5. **Staging** de la rama (`pns_demo`). **Hecho el 18/11/2026** («Pruebas posteriores», punto 7).

**Laboratorio con el core de LIYBEN** (`DOCKERFILE` propio): antes de LIYBEN. Ya se aplazó así el 12/11/2026 (propuesta,
«Decisiones de Sergio sobre V1 a V5 y la 3b», punto 5).

## Fase 4 — Zonas que cambian: 27, 29 y 34 (en este orden)

- **27:**
  - escapar `<` en `json.dumps` (`chatboo_canvas.py:1097, 1426, 1439, 2046-2047`);
  - **CSP (decisión 6):** se mantiene la cabecera HTTP del fabricante y se añade la `<meta>` de Seges
    (`img-src data: blob:; connect-src 'none'; …`) en el diseño y en las dos descargas, para que gane la más
    estricta y quede cerrado `'self'`;
  - comprobar antes que el lienzo de 3.1.973 sigue pintando sin `'self'`, sobre todo `/sales-board` y las
    imágenes de la página. Si algo legítimo necesita `'self'`, se presenta a Sergio antes de decidir;
  - tests: `test_seges_chatboo_canvas` y P-9 parte A como test.
  - **Hecho (13/11/2026):**
    - comprobación previa hecha, sin paso B (decisión de Sergio);
    - puntos corregidos del escape: 1098, 1426, 1427, 1440, 1734 y 2195 (árbol anterior al parche). Sale 2047-2048
      (`wrap_captured_page`, que genera Python, no HTML);
    - parche implementado (a, a′, b y c; sin d) y validado: batería de 541 tests, 1 F (`test_paap_i7`), 0 E y 6
      saltados; 10 neutralizaciones con SHA-256 igual; laboratorio D5 correcto;
    - detalle en [propuesta_fase4_3973.md](propuesta_fase4_3973.md).
- **29:** muestra para Design (`:829-858`) y `place_rows_on_page` (`:2062-2105`).
  - **Hecho (16/11/2026):**
    - propuesta y decisiones D6 a D14 en [propuesta_fase4_3973.md](propuesta_fase4_3973.md). Se porta el 29 entero, con
      12 bloques y 14 marcadores. Las líneas de arriba son de 3.1.973 limpia; las del árbol están en la propuesta;
    - batería: 557 tests, 1 F (`test_paap_i7`), 0 E y 6 saltados; 12 neutralizaciones con SHA-256 igual;
    - D14: 0 diseños con DATA ilegible en `lab_pns_ai_3973_14`;
    - `test_edit_page_without_data`, adaptado por el parche 38 (solo vale en modo test);
    - laboratorio hecho (16/11/2026): automatizado y sin LLM (D10), sin incidencias (fila del 16/11/2026 en el
      «Registro de laboratorios» de [lab_procedimiento_3973.md](lab_procedimiento_3973.md)); los casos con el modelo
      real, con P-13 del 34.
- **34:** `log_no_page` (`:587-616`); `_process` y `_save_to_session` (`chatboo_async_request.py:149-162,
  1184-1410`), con la opción A y F1. P-13 en la interfaz.
  - **Condiciones nuevas (16/11/2026):**
    - la propuesta del 34 comprueba que el 34 no escriba la fila de `chatboo.session` en el cursor del turno después del
      motor (invariante 2 del registro, «Parche 29 en 3.1.973»);
    - por comprobar (revisión de `odoo-reviewer`, 16/11/2026): si la caja B puede escribir `canvas_*` y llamar a
      `page_edit` en la misma transacción (única forma teórica de romper la invariante 1 dentro de un turno; afectaría a
      la disponibilidad, no a la seguridad del 29);
    - su laboratorio incluye 6c y 6d′ del 29 (casos con el modelo real; [lab_p29_3879.md](lab_p29_3879.md)), junto a P-13,
      porque los dos necesitan proveedor (D10).
  - **Hecho el código (16/11/2026):**
    - decisiones D15 a D19 y resultados en [propuesta_fase4_3973.md](propuesta_fase4_3973.md); registro, «Parche 34 en
      3.1.973». Porte literal de la 3879 con la opción A y F1: 10 bloques y 12 marcadores;
    - citas recalculadas sobre `05a05a5`: `log_no_page` en `chatboo_canvas.py:646` antes del parche (`:671` tras él);
      `chatboo_async_request.py` antes del parche es igual al de 3.1.973 limpia (mismo SHA-256 `112f0dc8…` que
      `~/pns_fabricante/3.1.973/`; `_process` en `:149` y `_save_to_session` en `:1184`, como arriba);
    - batería: 566 tests, 1 F (`test_paap_i7`), 0 E y 6 saltados; 6 neutralizaciones con SHA-256 igual;
    - invariante 2: se cumple; invariante 1 (caja B): no posible. La observación (un plan que suba `canvas_rev` en el
      turno suprime el aviso) queda aceptada sin código (Sergio, 16/11/2026; registro, «Parche 34 en 3.1.973»);
    - cierre (16/11/2026): cita del comentario de F1 corregida, línea de la fase 4 en la cabecera del test y
      neutralización N34x (S1);
    - laboratorio pendiente:
      - P-13 con proveedor real;
      - 6c y 6d′ de [lab_p29_3879.md](lab_p29_3879.md);
      - en pantalla, en vivo y al recargar, los casos a′, b′, c y d del pintado del aviso en el cliente (lectura de
        código, sin confirmar; [propuesta_fase4_3973.md](propuesta_fase4_3973.md), «Pintado del aviso en el cliente»).
        Si se confirma, Sergio decide entre aceptarlo, cambiar la forma del aviso en el servidor o parchear el cliente.

**Tras el laboratorio L1 del 34 (16/11/2026, decisiones D20 a D28):**

- **34, forma del aviso cambiada (D25):**
  - L1 confirmó, con el `formatContent` real del cliente, las marcas literales de F1 (`<p><em>` en a′; `_…_` en b′, c y
    d). Fila del 16/11/2026 de las 16:13 UTC en el «Registro de laboratorios» de
    [lab_procedimiento_3973.md](lab_procedimiento_3973.md).
  - El aviso pasa a ser una línea llana sin marcas: `acc`, dos saltos de línea y el aviso; con `acc` vacío, solo el
    aviso. Reabre D15 y F1. Se quita `import html` (D26): quedan 11 marcadores.
  - Tests (D27): cambian los esperados de los 4 tests con aviso. Batería `tests-20261116-172418.log`: 566 tests, 1 F
    (`test_paap_i7`), 0 E y 6 saltados, igual que la línea base. Neutralizaciones N34p (nueva), N34s y N34o (D28): 5 F
    cada una, SHA-256 igual al restaurar.
  - Revisión de `odoo-reviewer`: APROBADO CON OBSERVACIONES (0 críticos; los 2 avisos, de documentación, resueltos).
  - Riesgo aceptado: tras una respuesta que se pinta como HTML (casos a y d), el aviso queda pegado al último texto.
  - Detalle en [propuesta_fase4_3973.md](propuesta_fase4_3973.md), «Forma del aviso: línea llana (16/11/2026, D20 a
    D28)», y en el registro, «Parche 34 en 3.1.973».
- **Laboratorio del 34:**
  - L1 (sin modelo): hecho (16/11/2026); con la línea llana, 12/12 «línea llana», código 0 (fila de las 16:58 UTC);
  - L2 (turnos reales, D20 y D21): pendiente: P-13 con proveedor real, 6c (contacto hostil, D23) y 6d′ (lienzo plantado y
    borrado al acabar, D24) de [lab_p29_3879.md](lab_p29_3879.md), con «Design» cambiado por Sergio en la interfaz
    (D22), y la apertura de la marca y el `reset` en `_process`.

**Tras el laboratorio L2 del 34 (17/11/2026, decisiones D29 a D33):**

- **34: laboratorio hecho.** L2 con turnos reales (~14:05-14:12 UTC, `servidor-20261117-151159.log`, modelo
  `gemini-3.5-flash-lite` por D32): los seis pasos validados (T1 y T1b a mano, D33; V2, 5b′, 6c y 6d′ OK), y con V2, la
  apertura de la marca y el `reset` en `_process` (S1). D14 después: 6 con diseño y 0 ilegibles; limpieza hecha.
  Resultados en el registro, «Parche 34 en 3.1.973», «Laboratorio L2 (17/11/2026)»; fila y los cuatro intentos no válidos
  en el «Registro de laboratorios» de [lab_procedimiento_3973.md](lab_procedimiento_3973.md).
- **Lo siguiente:** parche 35 (sección siguiente).
- **Pendiente menor:** el clasificador de `lab_cdp.py` (`MOTIVOS_FIJOS`) no reconoce «No AI provider is configured…», y
  `rechazo()` de T1 busca «no design provider» (errata en el registro). Hay que corregirlo antes de reutilizar el
  escenario p34.

## Parche 35: crons de NUEVO-2 (decisión 4)

- `pns_ai_mcp/migrations/14.0.3.1.973/post-migrate.py`, como parche de Seges (registro, marcador, test y
  neutralización). Los parches siguen sin tocar `version`; este es la única excepción a «sin `migrations/`
  propios» (CLAUDE.md del repo).
- **Condiciones:**
  - solo los dos crons, buscados por XML ID (`pns_ai_mcp.ir_cron_ai_fetch_cache_gc` y
    `pns_ai_mcp.ir_cron_ai_api_result_cache_gc`);
  - solo sustituye el texto exacto `model.gc_expired()` por `model._gc_expired()`;
  - idempotente;
  - si el código del cron no es el esperado, no lo toca y lo deja en el log.
- Se ejecuta en el `-u` desde 3.1.879 (`pns_demo`) y desde 3.1.782 (LIYBEN). Lo comprueba P-2.
- NUEVO-2 solo afecta a las BD **actualizadas** a 3.1.973 desde 3.1.879 o 3.1.782: los crons son
  `noupdate` y conservan `model.gc_expired()`.
- **Una BD actualizada a 3.1.973 sin el parche** (por ejemplo, actualizada con la base limpia del primer
  commit desde 3.1.879) no lo ejecuta: Odoo solo corre `migrations/14.0.3.1.973/` en un `-u` que cruce
  esa versión. Se corrige a mano (`model._gc_expired()` en los dos crons). P-2 cubre este caso (b).
- **En una instalación limpia de 3.1.973** los crons nacen con `model._gc_expired()` y ya están bien: el
  script no tiene nada que hacer (y tampoco se ejecuta, porque no hay `-u` que cruce la versión).

### Parche 35: código y tests hechos (17/11/2026)

- **Hecho:** script, 9 tests, batería y cinco neutralizaciones sobre `7c68ae8`, con las decisiones D34 a D38 de
  Sergio (17/11/2026). Detalle en el [registro](parches_pns_ai.md), «Parches de la rama 14.0-pns-ai-3973 (parche 35,
  17/11/2026)».
- **D38:** el `-u` de P-2 y del staging nombra los tres módulos: `-u pns_base,pns_ai_mcp,pns_ai_chatboo`.
- **Qué mirar en P-2:**
  - **(a)** `-u` desde 3.1.879 con el 35: en el log, «module pns_ai_mcp: Running migration [14.0.3.1.973>]
    post-migrate» y dos «Seges patch 35: … fixed (gc_expired -> _gc_expired)», una por cron; ningún WARNING del 35
    («not found» ni «unexpected code»);
  - **(b)** `-u` desde 3.1.879 con la base limpia y después a la rama con el 35: ninguna de las dos (el script no se
    ejecuta); los crons siguen con `model.gc_expired()` y se corrigen a mano;
  - **(c)** instalación limpia: ninguna de las dos; los crons nacen con `model._gc_expired()`.
- **Comprobación de `ir_cron.code`**, en los tres casos y en el staging, solo de lectura:

  ```sql
  SELECT d.name, s.code
    FROM ir_model_data d
    JOIN ir_cron c ON c.id = d.res_id
    JOIN ir_act_server s ON s.id = c.ir_actions_server_id
   WHERE d.module = 'pns_ai_mcp' AND d.model = 'ir.cron'
     AND d.name IN ('ir_cron_ai_fetch_cache_gc', 'ir_cron_ai_api_result_cache_gc');
  ```

  Esperado: `model._gc_expired()` en las dos filas, salvo en (b) antes de la corrección a mano.

## Parches retirados: 10, 13, 14, 23, 30 y 31

- **Registro:** estado «Retirado en 3.1.973 (cubierto por el fabricante)», en el índice de la rama
  `14.0-pns-ai-3973`. Las entradas antiguas no se reescriben.
- **Tests:** se conservan como no regresión de la corrección del fabricante. Los casos que esperan
  `AccessError` aceptan también el error de nombre privado (salvo los del 23, decisión 5).

## Tests

- `pns_ai_chatboo/tests/__init__.py` y `pns_ai_mcp/tests/__init__.py`: el del fabricante, con el bloque de
  Seges debajo y sus marcadores.
- E0′ sobra (el fabricante lo corrige con otros nombres); queda retirado en el registro.
- Cada fase se mide como «línea base del fabricante + tests de Seges», con F y E por nombre.
- **Regla (11/11/2026):** en cada entrega de tests se confirma que los tres módulos se cargan desde
  `/mnt/compartidos/third_party/pns_*`: `addons paths` del log de tests, y ningún `pns_*` en las demás rutas
  del contenedor (`/usr/lib/python3/dist-packages/odoo/addons`, `/var/lib/odoo/addons/14.0`, `/mnt/oca/*`).

## Pruebas posteriores (en `lab_pns_ai_3973` salvo indicación)

1. Fase 2, al terminar 2a y 2b (juntas): P-5 con el 12, P-7 y las comprobaciones manuales de la 2a
   (registro de parches, «Pendiente de la fase 2a»; P-70 caso 1 del parche 20 incluido).
   **Hechas el 11/11/2026:** registro de parches, «Pruebas manuales de la fase 2 en `lab_pns_ai_3973`
   (11/11/2026)», y guía [lab_fase2_3973.md](lab_fase2_3973.md). Sin positivo del 26 desde la interfaz; de ellas
   sale la fase 2c (parche 36).
2. Fase 3: P-22 y, si Sergio pasa a la opción A, P-20.
3. Fase 4: P-13.
4. Con toda la rama:
   - **Antes:** decisión sobre `iap.account.get` (P2) y comprobación de la versión del core del staging (ver
     «Planificación hasta el staging», punto 4);
     - **P2 decidido y hecho (17/11/2026):** opción B (D40), **parche 39** (PNS-107, Baja): `iap.account.get` bloqueado
       en la caja A por modelo y nombre, literal y dinámico, y sus 8 llamadores públicos por nombre (D40b), también como alias sin llamada en sus modelos (D40d); el campo
       calculado de `partner_autocomplete` y `crm.lead.iap_enrich`, restos conocidos (D40c). Tests, batería y
       neutralizaciones N39, N39b y N39c en el
       [registro](parches_pns_ai.md), «Parches de la rama 14.0-pns-ai-3973 (parche 39, 17/11/2026)». Sin cambios en
       P-2;
     - **Core del staging, comprobado (17/11/2026, solo lectura en el VPS):** `odoo14_pns` monta en `ro`
       `/opt/odoo/odoo-core/odoo` en `/usr/lib/python3/dist-packages/odoo` y `/opt/odoo/odoo-core/addons` en
       `/mnt/core-addons`. Commit `cc0060e889603eb2e47fa44a8a22a70d7d784185` (22/10/2024), sin cambios locales: el
       mismo que LIYBEN y que la referencia `/opt/odoo-src/14.0`. SHA-256 (16) dentro del contenedor iguales a la tabla
       de LIYBEN (propuesta de la fase 3, «Datos de LIYBEN»): `fields.py` `f915e7114ceb705d`, `models.py`
       `aae6b5a0c3027136`, `auth_totp/models/res_users.py` `a8bb617ffd88f3b8`, `auth_signup/models/res_partner.py`
       `c848abd85790cadd`; `iap/models/iap_account.py` `010ed431f82f5666`, igual en la imagen `odoo-dev:14` y en la
       referencia (las citas del parche 39 valen para el staging y LIYBEN). `iap` solo carga de `/mnt/core-addons`.
       El core de la imagen del laboratorio no es `cc0060e` (variante de `totp_secret`): el laboratorio con el core
       de LIYBEN cubriría también el staging (decisión pendiente, tras el bloque 4 de las pruebas con toda la rama).
       Observación sin acción: volumen anónimo en `/mnt/extra-addons` (`rw`, el `VOLUME` de la imagen), fuera del
       `addons_path` (solo usa `/mnt/extra-addons/pns`, `ro`);
   - P-14, en una BD instalada con `~/pns_ai_3973/fase0/modulos_3879` y después actualizada;
   - P-2, con tres casos:
     - (a) `-u` desde 3.1.879 con el parche 35: corrige los dos crons;
     - (b) `-u` desde 3.1.879 con la base limpia y después a la rama con el 35: el script no se ejecuta y
       los crons siguen rotos; corrección a mano;
     - (c) instalación limpia (`lab_pns_ai_3973_14`): crons bien y el script no los toca.

     `lab_pns_ai_3973_14` solo cubre (c); (a) y (b) usan `~/pns_ai_3973/fase0/modulos_3879`.

     **P-2 se hace en el laboratorio, no en el VPS.** La corrección a mano solo es del caso (b) y de su BD de
     laboratorio (`lab_p2b_879_14`). En el staging (`pns_demo`, desde 3.1.879) y en LIYBEN (desde 3.1.782), el `-u`
     cruza 3.1.973 y los dos crons los corrige el parche 35 («Tras el `-u` (staging y LIYBEN)», abajo).
     Orden de la corrección a mano (decisión de Sergio del 17/11/2026; contexto `lab_pns_ai_3973`, web parado; muestra
     el code y pide «s/N»; escribe con `commit` exactamente `model._gc_expired()` por `cron.write`, como
     `migrations/14.0.3.1.973/post-migrate.py:18-19` y `:35-42`, y solo donde el code es `model.gc_expired()`):

     ```bash
     bash ~/pns_ai_3973/fase4/lab/rama_corregir_p2b.sh --bd lab_p2b_879_14
     ```
   - P-11;
   - `_require_settings` (con y sin el 32);
   - reintento de la tarjeta (con CDP desde el 17/11/2026: D47, abajo).
   - **Guía:** [lab_3973/guia_rama.md](lab_3973/guia_rama.md), con los bloques 0, 3, 1, 2 y 4, «Al acabar» y la
     limpieza final.

   **Preparación de las pruebas con toda la rama (17/11/2026; decisiones D41 a D47 de Sergio).** Scripts y guía
   preparados, sin ejecutar ningún laboratorio. Están en [lab_3973/](lab_3973/), con sus SHA-256 en la guía.
   - **D41 (carpetas):** `COMPARTIDOS=""` y `DOCKERFILE="infra/Dockerfile.14"` (copia del de `lab_pns_ai_3973`,
     `cfc58aed…c348`). 3.1.879 sale de `~/pns_ai_3973/fase0/modulos_3879` (711 archivos, SHA-256 contra
     `sha256_copias.tsv`). La base limpia 3.1.973 es el `git archive` del commit de la 1b (`33ca68c`, «base 3.1.973 del
     fabricante»): solo `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo`, 657 archivos, permisos 644/755. Todo `-u` a la rama
     se lanza desde `lab_pns_ai_3973` con `--bd` y `-u pns_base,pns_ai_mcp,pns_ai_chatboo` (D38).
     Respuesta al paso 0 (17/11/2026): 3.1.879 se instala en las dos BD desde `lab_pns_ai_879`, y el primer `-u` del
     caso (b), a la base limpia, desde `lab_pns_ai_973f`. La guía comprueba el contexto, en solo lectura, antes de cada
     `-u`; cada `-u` va con el web parado y su `actualizar-*.log` (línea «==> actualizar en `<bd>` (log: …)») es el
     `--log` de `rama_comprobar.sh`.
   - **D42 (BD y carpetas):** `lab_p2a_879_14` (bloque 1) y `lab_p2b_879_14` (bloque 2); carpetas
     `~/GitHub/lab_pns_ai_879` y `~/GitHub/lab_pns_ai_973f` (`git init` y `CLAUDE.md` con «Versión de Odoo: 14.0»,
     MANUAL 6.7), creadas por `rama_carpetas.sh`. Se aceptan los datos de demostración (el kit no pasa
     `--without-demo`).
     Versiones esperadas antes del `-u` (`rama_plantar.sh`): `pns_base` `14.0.1.2.47`, `pns_ai_mcp` `14.0.3.1.879` y
     `pns_ai_chatboo` `14.0.2.1.538`. Salen de `modulos_3879/pns_base/__manifest__.py:8`,
     `pns_ai_mcp/__manifest__.py:8` y `pns_ai_chatboo/__manifest__.py:7` (`1.2.47`, `3.1.879` y `2.1.538`; Odoo antepone
     `14.0.`).
   - **D43 (siguiente pasada de P-2):** `method_direct_trigger()` de los dos crons (escribe) y `ValueError` de
     `safe_eval` en la salida, esperado 0 (`rama_crons.sh`).
     **Control negativo** (revisión del 17/11/2026; bloque 2, entre los puntos 8 y 9 de la guía): `rama_crons.sh --bd
     lab_p2b_879_14` antes de la corrección a mano. Esperado: código 1, «RAMA CRONS sin error 0 de 2», `ValueError` 2 o
     más (`safe_eval` envuelve el `AttributeError` en `ValueError`, `odoo/tools/safe_eval.py:346-347` de la imagen) y
     nada escrito. Dos motivos: `method_direct_trigger` solo escribe `lastcall` después de `run()`
     (`odoo/addons/base/models/ir_cron.py:83-84`), y cada cron va en su `savepoint`, que deshace lo que hubiera hecho la
     acción.
   - **D44:** `lab_auto.sh` y `lab_cdp.py` aceptan `--lab <carpeta>` y `--bd <bd>`; por defecto, `lab_pns_ai_3973` y
     `lab_pns_ai_3973_14`. La C espera la BD indicada. `prueba_lab_auto.sh`: 49 PASA (antes 32).
   - **D45 (P-11, tests por lectura):** ningún test de Seges crea un AI Administrator y espera que no tenga AI
     Conversational. Las dos únicas menciones a `group_ai_conversational` en los tests de Seges dan ese grupo a usuarios
     que no son AI Administrator (`pns_ai_mcp/tests/test_seges_sandbox_credentials.py:323` y
     `test_seges_review_views.py:46`). Ningún test de Seges cambia de resultado por la implicación de §6.2. La línea base
     (580 tests, 1 F en `test_paap_i7`) ya se midió con ella.
   - **D46 (`_require_settings`):** `rama_require_settings.sh` (con `--sin-32` para la pasada con N32, SHA-256 antes y
     después). Sin commit y con cada caso en un savepoint deshecho. No pasa por `_resolve_execute`, que hace commit
     (`safe_operation.py:948` y `:957`): ejecuta como el servidor (`:1441-1445` y `:1477-1486`) con `execute_safe_plan`.
     Por lectura: la propuesta de `field_required` de un AI Administrator sin Ajustes ya la rechaza la validación
     (`safe_plan_validate.py:198-202`). El script lo informa y crea la operación igualmente, para probar la barrera al
     ejecutar.
     Revisión del 17/11/2026: `execute_safe_plan` no captura errores (los lanza) y, si va bien, devuelve la lista
     `results` (`safe_plan_execute.py:60-242`). «ok» exige el valor de éxito (`ok` en el dict de la fila, `:122-133` y
     `:146-148`) y el efecto, mirado dentro del savepoint:
     - vista: `comment` readonly en la arquitectura de la vista de prueba;
     - campo: `required` del campo en el registro (`ai_system_action.py:410-412`). En un campo de módulo,
       `ir.model.fields` no se persiste (`ir_model.py:924-927` de la imagen; nota en `ai_system_action.py:408`).

     Un error devuelto se clasifica como la excepción.
   - **D47 (reintento de la tarjeta):** `tarjeta_plantar.sh` (solo la operación, de `seges_int`, sin sesión: la tarjeta
     la pinta el panel con las operaciones pendientes, `chatboo_systray.js:409-411` →
     `chatboo_component_v2.js:2162-2188`), escenario `lab_auto.sh … --escenario tarjeta` y `tarjeta_borrar.sh`.
     El escenario comprueba antes, por SQL, que la operación sigue pendiente y sin caducar
     (`pns_ai_mcp/constants.py:7`, 15 min). Si no, para sin pulsar nada. Se lanza antes de 15 min desde el plantado.
     - **Clic forzado** (decisión de Sergio del 17/11/2026): el botón «Confirmar» de una tarjeta `high` está
       deshabilitado 5 s desde que se pinta (`chatboo_component_v2.js:2373-2393`). El escenario solo quita `disabled`
       al botón y lanza el clic sobre él. Una persona no puede seguir ese camino.
     - **Esperado** (corregido tras el paso 0): rechazo `too_soon`; ningún `/verification/pending` sin `peek` tras el
       clic; confirmación sola unos 5,5 s después del rechazo y con el mismo token (`chatboo_component_v2.js:2275-2281`);
       la operación ejecutada (SQL de solo lectura).
       En el log, el ERROR «bad query» sobre `ai_safe_operation` y «SERIALIZATION_FAILURE, retry 1/5» (anexo de PNS-26)
       no son fallo; «retry 2/5» o «maximum number of tries reached», sí.
     - **Matiz de lectura:** tras cada respuesta de `/confirm`, la bandeja pide `/verification/pending` con `peek: true`
       (`chatboo_component_v2.js:2426` → `:3410-3419` → `chatboo_systray.js:67-73` y `:262-268`). No genera token. El
       escenario la cuenta como informativa; solo es fallo una petición sin `peek`.
   - **Parche 39 en el laboratorio (bloque 3):** `p39_lab.sh` (sin commit; antes, SQL de que `sms` e `iap` están
     instalados). Llama a la herramienta `relaxaicode` real como `seges_int`, con `tool_relaxaicode`
     (`tools_relaxaicode.py:104-107`) y `_StubController` (`tests/seges_common.py:15-43`). Casos:
     `iap.account.get('seges_lab39')`, `get_credits_url('seges_lab39')`, `f = get_config_account_url` y `f()`, y
     `sms.resend.new({}).action_buy_credits()`: los cuatro con `"isError": true` o la respuesta de
     `_read_only_response()` (`relaxaicode_prepare.py:400-416`, `requires_write`; `tools_relaxaicode.py:159-172`).
     Control: `result = {'a': {'k': 1}.get('k'), 'n': env['iap.account'].search_count([])}`, sin error. Antes y
     después, `count(*)` y `max(id)` de `iap_account` desde un cursor aparte, de solo lectura, sin cambios.
     Revisión del 17/11/2026: el script distingue por qué se rechaza, sin imprimir el texto.
     - **Bloqueado por el 39:** `isError` con el marcador «Method '<nombre>' writes outside RelaxAICode's rollback» de
       `_seges_check_model_method` (`context_builder.py:309-327`, llamado desde `_read_attr`, `:330-334`; devuelto como
       «Error executing code: …», `relaxaicode_failures.py:194-199`). Es lo previsto para `get` y para
       `f = get_config_account_url; f()`.
     - **`requires_write`:** el AST ve una llamada cuyo nombre está en la lista global (`validators_checks.py:464-484`;
       nombres del 39 en `validators_base.py:304-314`). Es lo previsto para `get_credits_url` y `action_buy_credits`.
     - **Otro error, o una clase distinta de la prevista:** FALLO.
     - **Una excepción de la herramienta:** no es un rechazo. El resultado es NO CONCLUYENTE (código 8).
   - **Caminos reales hacia `too_soon`** (pregunta de Sergio, solo por lectura; no van en el escenario, se decide
     después):
     - **Con la tarjeta pintada por `/verification/pending`, no hay ninguno.** El servidor cuenta los 5 s desde
       `confirm_token_at` (`safe_operation.py:564-596`) y la tarjeta los cuenta desde que se pinta, después de recibir
       el token. El botón se habilita 5 s después del pintado (`chatboo_component_v2.js:2373-2393`). Además,
       `fields.Datetime.now()` quita los microsegundos (`odoo/fields.py:1868-1874` de la imagen), lo que hace la espera
       del servidor más corta, no más larga.
     - **Tras `bad_token` o `missing_token`:** `_retryRefusedCard` pide un token nuevo (`:2284`) y espera 5,5 s antes de
       confirmar (`:2276`, `:2302`). No llega a `too_soon`. Si el segundo intento también falla, vuelve a habilitar el
       botón sin token nuevo (`:2266-2271`).
     - **Dos operaciones:** el reintento de una pasa `held` con todas las tarjetas pintadas menos ella (`:2190-2200`),
       así que no cambia el token de las otras.
     - **Dos pestañas:** la otra pestaña genera un token nuevo para la operación (su `held` no la incluye). La pestaña
       con el token antiguo recibe `bad_token`, no `too_soon`. La tarjeta nueva de la otra pestaña empieza con su
       propia cuenta atrás.
     - **Camino real posible: tarjeta pintada sin token.** La tarjeta del SSE va sin token si `_mint_card_token` no lo
       genera (`engine_tool_run.py:541-563`: la operación aún no se ve en su cursor, otro usuario o un error; también en
       `agent_engine.py:1769-1778`). Una tarjeta sin token no entra en `held` (`chatboo_component_v2.js:2190-2200`). Si
       el panel se vuelve a abrir (`chatboo_systray.js:409-411`), la restauración genera un token y se lo pone a la
       tarjeta ya pintada sin volver a deshabilitar el botón (`chatboo_component_v2.js:2311-2316`). Un clic en los 5 s
       siguientes da `too_soon`.
     - **Carrera posible:** una restauración en vuelo mientras llega la tarjeta del SSE. Su `held` se calculó antes del
       pintado y renueva el token de esa tarjeta, con la cuenta atrás ya en marcha (`:2311-2316`). El margen es el
       retraso entre el pintado del SSE y la respuesta de `/verification/pending`.

   **Resultados de las pruebas con toda la rama (18/11/2026).** Ejecutadas con la
   [guía](lab_3973/guia_rama.md), en el orden 0, 3, 1, 2 y 4. Todos los bloques, OK. Línea base sin cambios: 580 tests, 1 F
   (`test_paap_i7`), 0 E, 6 saltados y 6 subtests saltados. Los logs se citan solo por su nombre. Cada `arrancar` tiene
   su fila en el registro de laboratorios del [procedimiento](lab_procedimiento_3973.md).
   - **Bloque 0 (preparación): OK.** Copia y 12 SHA-256, OK; `prueba_lab_auto.sh`, 49 PASA; web parado; no existían
     `lab_p2a_879_14` ni `lab_p2b_879_14`. `rama_carpetas.sh`: 5 de 5 líneas esperadas (`modulos_3879` 711; 1b
     `33ca68c`, 657; `SHA256SUMS.txt` `e37be448…1844` y `4c5b1cd2…6c53`; `Dockerfile.14` `cfc58aed…c348`). Los
     permisos de las carpetas, en la incidencia b).
   - **Bloque 3 (`lab_pns_ai_3973_14`): OK.**
     - `-u` a la rama: OK, 0 bloqueantes, 0 avisos (`actualizar-20261118-092113.log`);
     - P-2 (c): todo OK. 206 líneas de la BD y 0 de otras; migración 0; Seges patch 35: líneas 0, WARNING 0;
       versiones `14.0.2.1.587`, `14.0.3.1.973` y `14.0.1.2.69`; `model._gc_expired()` en los dos crons; P-11: 4 AI
       Administrators, 0 sin AI Conversational;
     - D43: OK, 2 de 2, `ValueError` 0 (`rama_crons-lab_pns_ai_3973_14-20261118-092314.log`);
     - parche 39: «P39 VEREDICTO OK». Los 4 casos, 4/4 con su clase: `get` y `f()` «bloqueado por el 39»;
       `get_credits_url` y `action_buy_credits`, `requires_write`. Control OK; `iap_account` 0/0, sin cambios.
       **Queda validado en laboratorio** el marcador del 39 en el texto de `isError`.
   - **Bloque 1 (`lab_p2a_879_14`): OK.**
     - instalación de 3.1.879: OK (`instalar-20261118-093241.log`);
     - foto y plantado: OK (`usuario=8 sesion=1 skill=3 cache=1`). La foto, con 4 de 7 skills retiradas con fila de
       fábrica (incidencia c);
     - `-u` a la rama: OK (`actualizar-20261118-094410.log`);
     - P-2 (a): todo OK. 290 líneas y 0 de otras; migración 1; «Seges patch 35: … fixed» 1 y 1; WARNING 0; versiones
       de la rama; `model._gc_expired()`; P-11: 1 AI Administrator, con AI Conversational, y `seges_p11_admin` también;
       P-14: 0 filas de fábrica, la caché borrada en cascada y la sesión presente con `active_skill_code`
       `cash_forecast`;
     - D43: OK (`rama_crons-lab_p2a_879_14-20261118-095755.log`).
   - **Bloque 2 (`lab_p2b_879_14`): OK.**
     - instalación: OK (`instalar-20261118-100001.log`); plantado: OK (`usuario=8 sesion=1 skill=3 cache=1`);
     - `-u` a la base limpia: OK, migración 0, «Seges patch 35» 0 (`actualizar-20261118-100519.log`);
     - `-u` a la rama: OK (`actualizar-20261118-100813.log`);
     - P-2 (b) antes de corregir: todo OK. 200 líneas; migración 0; «Seges patch 35» 0; los crons con
       `model.gc_expired()`;
     - control negativo de D43 (8b): FALLO, como se prevé. 0 de 2, `ValueError` 2, código 1
       (`rama_crons-lab_p2b_879_14-20261118-101232.log`);
     - corrección a mano: «CORREGIDOS 2»;
     - P-2 (b) tras corregir: todo OK, `model._gc_expired()` en los dos;
     - D43: OK (`rama_crons-lab_p2b_879_14-20261118-101447.log`).
   - **Bloque 4 (`lab_pns_ai_3973_14`): OK.**
     - D46 con el 32: 4/4 → OK. Vista: `comment` readonly, antes no y después sí; vistas heredadas 1. Campo:
       `required`, antes no y después sí;
     - D46 con N32: 4/4 → OK. N32 `4b74193c…bf91`; restaurado, IGUAL (`11d9877f…33d1`); git limpio;
     - **quedan validados en laboratorio** `comment` readonly en `modifiers` y el número de vistas heredadas (1);
     - D47: «Código final 0» (op=13). Primer `/confirm`, `too_soon`, a 0,06 s del pintado; segundo, éxito 5,51 s
       después, con el mismo token. `/pending` sin `peek` 0 y con `peek` 2 (informativo); `/execute` `executed`. SQL
       después: `executed`, confirmada por el usuario de la sesión, comentario escrito;
     - log de D47 (`servidor-20261118-103306.log`): «bad query» 1 (`UPDATE "ai_safe_operation"`), «retry 1/5» 1,
       «retry 2/5» o más 0, «maximum» 0, Traceback 0. Informativos: 1 WARNING `py.warnings` (`DeprecationWarning` de
       `jinja2/sandbox.py`, core) y 1 HTTP 404 de `/es/website/translations/…` en el login. Confirma el anexo de
       PNS-26 (punto 7);
     - borrado: operaciones 1, contactos 1, quedan 0.
   - **Incidencias y desviaciones, con su resolución:**
     - a) **primer `arrancar` de `lab_pns_ai_879` (09:25, hora local):** C NO CONCLUYENTE (código 7). El log se guardó a
       los 13 s y salió vacío; nadie entró. Se repitió esperando a «HTTP service (werkzeug) running»: C OK. Corregido
       en el «Al acabar corto» de la guía;
     - b) **paridad `FALLARÁ` («SIN CÓDIGO») en `lab_pns_ai_879`:** `rama_carpetas.sh` dejó en 700 la raíz de las dos
       carpetas, y sus metadatos en 700/600 (`infra/`, `infra/Dockerfile.14`, `CLAUDE.md`, `.odoo-dev.conf`,
       `SHA256SUMS.txt` y `ORIGEN.txt`). El usuario 101 del contenedor no podía entrar. Se corrigió a mano con
       `chmod 755` de las dos raíces, sin recursivo. Los `SHA256SUMS` no cambian. Corregido en `rama_carpetas.sh`;
     - c) **foto de los bloques 1 y 2:** 4 de 7 skills retiradas con fila de fábrica, no 7. Es causa de 3.1.879 del
       fabricante. `sys_info`, `users_all` y `users_logged` declaran `required_groups`, y el motor 14.0.3.1.879 no
       publica esa capacidad. `_raise_unpublished_capability` (`pns_ai_mcp/models/ai_skill.py:409` en 3.1.879) las
       rechaza en la importación, que solo lo deja en INFO («skills import_from_files: {'created': 10, … 'errors': […
       requests engine capability "required_groups" …]}», 3 errores en cada instalación). En una instalación nueva de
       3.1.879 esas tres no existen; P-2 (a) y (b) cubren la retirada de las 4 que sí. Decisión de Sergio: seguir con
       4 de 7. Para el staging, la comprobación del punto 7. **Informe al fabricante: pendiente de decisión de
       Sergio** (no se añade);
     - d) **D47:** `seges_int` (uid 12) no tenía escritura en `res.partner`. Sus grupos: `base.group_user`, ventas, AI
       Conversational y AI Writer, sin `base.group_partner_manager`. `tarjeta_plantar.sh` paró antes de plantar, sin
       escribir nada. Decisión de Sergio: añadir `base.group_partner_manager` solo durante D47 y quitarlo al acabar.
       La lista de grupos de antes y la de después, IGUALES. En la guía, «Requisito de D47».

   **Laboratorio con el core cc0060e (18/11/2026).** Se repite parte de las pruebas con toda la rama, ahora con el core
   del staging y de LIYBEN (`cc0060e`, punto 4, «Antes»). Las salidas están fuera del repo, en
   `~/pns_ai_3973/fase4/cc0060e/`: aquí se citan por su nombre y se resumen, sin datos. El `arrancar` tiene su fila
   en el registro de laboratorios del [procedimiento](lab_procedimiento_3973.md).
   - **Decisiones de Sergio (18/11/2026):**
     - **D48:** laboratorio con el core `cc0060e` antes del staging, con el alcance del paso 0: instalación limpia
       (P-2 c), batería, `p39_lab.sh` y `rama_require_settings.sh` con el 32. Quedan fuera D47 y P-2 (a) y (b), porque
       `migration.py`, `loading.py`, `iap`, el JS y las plantillas son iguales en los dos cores;
     - **D49:** el core va en un Dockerfile propio: carpeta `~/GitHub/lab_pns_ai_cc0060e`, imagen
       `odoo-dev:14-lab_pns_ai_cc0060e`, BD `lab_pns_ai_cc0060e_14`;
     - **D50:** los 7 tokens de registro de LIYBEN se vacían justo antes de su despliegue, no ahora. Antes hay que
       comprobar en `cc0060e` qué hace `signup_cancel` de `auth_signup` («Tras el `-u`», abajo);
     - **D51:** limpieza final de las pruebas con toda la rama: hecha (abajo);
     - **Conservación:** el laboratorio `cc0060e` (carpeta, imagen y BD) se conserva hasta la limpieza final del
       staging.
   - **Limpieza final de las pruebas con toda la rama (D51, ~11:28 hora local):** `bd-borrar` de `lab_p2a_879_14` y
     `lab_p2b_879_14`. Se borraron también las carpetas `lab_pns_ai_879` y `lab_pns_ai_973f` y sus dos imágenes. El
     `arrancar` final de la guía no se lanzó, porque el contexto ya era `lab_pns_ai_3973` y no cambió. `bd-borrar` no
     pregunta en la terminal; la confirmación es solo para los agentes (MANUAL del kit, 6.4). La guía está corregida
     («Limpieza final»).
   - **Paso 0, comparación de cores (`comprobar/resumen_0a_odoo-dev14.txt`):** se comparó la imagen `odoo-dev:14`
     (paquete 14.0.20231106) con `/opt/odoo-src/14.0/odoo` (`cc0060e`, sin cambios locales). Resultado: 9205 iguales,
     187 distintos, 581 solo en la imagen (`design-themes`) y 10 solo en la referencia. `odoo-dev:14-lab_pns_ai_3973`
     da lo mismo. Diferencias que importan a la rama:
     - `totp_secret` y `signup_token`, calculados por SQL;
     - `_allow_sudo_commands` y `uid_origin`;
     - `HTTPRequest` nueva en `http.py`;
     - `call_kw`;
     - reglas `ir.rule` multicompañía.

     **Excepción a la forma fija de `docker run`** (aprobada por Sergio el 18/11/2026): la comparación se ejecutó
     también con las imágenes locales `odoo-dev:14-lab_pns_ai_3973` y `odoo-dev:14-lab_pns_ai_cc0060e`, en solo
     lectura. Con la primera, en este paso 0; con la segunda, en la comprobación posterior de la imagen (abajo).
   - **Imagen (D49; `arrancar` a las 11:52 hora local, `arrancar_20261118-115229.txt`):** `infra/Dockerfile.14`
     descarga el tarball del commit `cc0060e`, sustituye con él todo el core del paquete y comprueba 5 huellas
     (`fields.py`, `models.py`, `auth_totp/models/res_users.py`, `auth_signup/models/res_partner.py` e
     `iap/models/iap_account.py`, las del staging y LIYBEN). Las 5, OK. El SHA-256 del tarball, `925cf1c3…9654`, es un
     dato y no una referencia, porque GitHub no garantiza que el tarball sea estable.
     - Comprobación posterior con `comparar_core.py`: iguales 9402, distintos 0, solo en la imagen 0, solo en la
       referencia 0.
     - SHA-256 de los archivos de la carpeta: `CLAUDE.md` `c3de247c…4f3d`, `.odoo-dev.conf` `9f87184c…00d9` e
       `infra/Dockerfile.14` `8800092a…e69a`.
     - «Al acabar corto» con `servidor-20261118-115434.log`: 6 líneas, nadie entró, sin Starting job, C código 0.
   - **Batería (`tests-20261118-120134.log`; salida `tests_20261118-120131.txt`):** 580 tests, 1 F
     (`TestSystemTrustedActions.test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin`), 0 E y los 6 saltados de siempre. En el log: Traceback 58,
     `seges_side_env` 1, secretos 0 y 1 «bad query» (`UPDATE "ai_safe_operation"`). **Igual a la línea base.**
     `test_seges_box_a_vias` pasa, así que V3, V4 y O1 del parche 18 quedan validados en la variante de `totp_secret`
     de LIYBEN. Los subtests saltados no se contaron (pendiente, abajo).
   - **Instalación y P-2 (c) (`instalar-20261118-121058.log`; salidas `i_lab_pns_ai_cc0060e_14.txt` y
     `p2c_lab_pns_ai_cc0060e_14.txt`):** `-i` OK, 0 bloqueantes y 0 avisos; el web no se reinició. P-2 (c), con una
     consulta de solo lectura, todo OK:
     - 596 líneas de la BD y 0 de otras; migración 0 y «Seges patch 35» 0. Estos recuentos del log de `instalar` salen
       de la salida de la tanda 4a, que no se guardó en `p2c_lab_pns_ai_cc0060e_14.txt`;
     - versiones `14.0.2.1.587`, `14.0.3.1.973` y `14.0.1.2.69`;
     - `iap` y `sms` instalados;
     - `model._gc_expired()` en los dos crons;
     - `P11|0|0|1`.

     `rama_comprobar.sh` no sirve para un `-i`: exige un `actualizar-*.log` y al menos un AI Administrator.
   - **Preparación (`prep_seges_int.txt`):** se creó `seges_int` con commit (id 8, solo `base.group_user`,
     `no_reset_password`).
   - **Copias de los scripts (`~/pns_ai_3973/fase4/lab/cc0060e/`):** de los originales solo cambian `LAB_NOMBRE` y `BD`,
     y los originales no se tocaron. `p39_lab.sh` `6d160f93…1656` y `rama_require_settings.sh` `eb7cbb3c…38f1`.
   - **Parche 39 (`p39_lab_pns_ai_cc0060e_14.txt`):** «P39 VEREDICTO OK»: 4/4 previstos con su clase, 0 excepciones,
     control OK, `iap_account` 0/0 sin cambios. El usuario no tiene AI Conversational, a diferencia del bloque 3.
   - **D46 con el 32 (`d46_lab_pns_ai_cc0060e_14.txt`):** 4/4, código 0. Las cuatro líneas coinciden con lo esperado en
     la guía (bloque 4, punto 2), incluida la propuesta «rechazada en la validación» de «sin Ajustes, campo»
     (`safe_plan_validate.py:198-202`; `rama_require_settings.sh`, comentario de cabecera y `propuesta`).
   - **Conclusión:** el core del staging y de LIYBEN (`cc0060e`) queda cubierto en el alcance de D48. La instalación
     limpia, la batería, el 39 y D46 con el 32 dan lo mismo que con el core de la imagen `odoo-dev:14`. Lo que queda
     fuera (D47 y P-2 a/b) no depende de lo que cambia entre los dos cores.
   - **Archivos de referencia en [lab_3973/](lab_3973/)**, con su SHA-256 en la tabla de la
     [guía](lab_3973/guia_rama.md):
     - `Dockerfile.14.cc0060e`: copia de `infra/Dockerfile.14` del laboratorio, para reconstruir la imagen;
     - `comparar_core.py`: compara, en solo lectura, el core de una imagen con la referencia.
   - **Pendientes:**
     - `--lab` en `p39_lab.sh` y `rama_require_settings.sh` si se reutilizan. Hoy llevan el laboratorio fijo, y las
       copias de `cc0060e` se adaptaron a mano;
     - contar los subtests saltados con el core `cc0060e` (no se contaron; en la línea base son 6);
     - D50: comprobar en `cc0060e` qué hace `signup_cancel` de `auth_signup` antes de vaciar los tokens de LIYBEN
       («Tras el `-u`», abajo). → Hecho el 19/11/2026 («Tras el `-u`», «D50 hecho»).
5. P-15: `-u` completo sobre una copia de `pns_demo` que carga Sergio.
   - **Añadido el 13/11/2026 (fase 4, parche 27):** A7 en solo lectura sobre la copia de `pns_demo`. Es el script
     `~/pns_ai_3973/fase4/csp/a7_recuentos.py`, que cuenta diseños por patrón, sin contenido ni ID (ver
     [propuesta_fase4_3973.md](propuesta_fase4_3973.md), A7). Su constante `BD` es `lab_pns_ai_3973_14`: para la
     copia hay que cambiarla, y el cambio se presenta antes.
   - **Decisiones de Sergio (18/11/2026, tarde).** Numeración a continuación de D51, confirmada por Sergio:
     - **D52:** P-15 en `lab_pns_ai_cc0060e` (core del staging, punto 4) con el web parado. Excepción al
       procedimiento fijo ([lab_procedimiento_3973.md](lab_procedimiento_3973.md)): no hay `arrancar` ni reinicios del
       web, así que no aplica la comprobación C. Si alguna vez se levantara el web con la copia, sería una decisión
       aparte: la neutralización no vacía las claves de los proveedores de IA;
     - **D53:** copia por `pg_dump`, sin filestore;
     - **D54:** `-u` de los tres módulos (D38). A7 solo después, con una comprobación por SQL de los diseños
       antes y después. Se añaden a P-15 `ai_skill` (las 7 retiradas) y P-11;
     - **D55:** diseño con `/web/image` (A7b, abajo): **opción A**, se mantiene la decisión 1 del 13/11/2026
       («sin paso B», [propuesta_fase4_3973.md](propuesta_fase4_3973.md), «Decisiones de Sergio (13/11/2026)»).
       - Motivo: la cabecera del fabricante permite `'self'` en `img-src` y la `<meta>` del 27 lo quita. Es el efecto
         buscado (propuesta de la fase 4, `:52` y `:314`). Es el único caso encontrado, y es un diseño de demostración
         anterior a 3.1.973.
       - Salvedad: en la 3879, el 27 ya tenía `img-src data: blob:`, pero «las de `/web/image` siguen, porque se
         incrustan en `data:`» ([parches_pns_ai.md](parches_pns_ai.md), «Parche 27: el lienzo no deja salir datos
         (F1)», e, de la 3879). No está comprobado si ese diseño muestra hoy sus imágenes en el staging: se comprueba a
         la vista allí (punto 7).
   - **P-15 hecho (18/11/2026).** Las salidas están fuera del repo, en `~/pns_ai_3973/fase4/cc0060e/p15/`: aquí se citan
     por su nombre y se resumen, sin datos. Son `t0-20261118-133146.txt`, `t1-20261118-133247.txt`,
     `t2-20261118-133339.txt`, `t3-20261118-133535.txt`, `t3b-20261118-133822.txt`, `t4-20261118-134055.txt`,
     `t5-20261118-134441.txt`, `t6-20261118-135128.txt` y `t7-20261118-135715.txt`, más `p15_antes.txt`,
     `p15_antes_b.txt` y `p15_despues.txt`. Log del `-u`: `actualizar-20261118-134056.log`. Fila en el registro de
     laboratorios del [procedimiento](lab_procedimiento_3973.md).
     - **Contexto y copia:** `lab_pns_ai_cc0060e` (core del staging) con el web parado de principio a fin (D52); BD
       `p15_pns_demo_14`. Copia de `pns_demo` del 18/11/2026 a las 13:29 (hora local), por `pg_dump -Fc` desde
       `odoo14_pns_db`, directa por SSH al portátil y sin filestore (D53): 5,4 MB. El archivo local tiene permisos 600
       y se borra en la limpieza final del staging.
     - **Carga:** `bd-cargar --bd`, neutralizada; log de carga vacío (0 errores). Paridad: 48 instalados, 45 iguales, 3
       con versión distinta (`pns_base` 1.2.47 → 1.2.69, `pns_ai_mcp` 3.1.879 → 3.1.973 y `pns_ai_chatboo` 2.1.538 →
       2.1.587) y 0 sin código. El «la instalación FALLARÁ» del final de `bd-cargar` es falso (pendientes, abajo).
     - **`-u pns_base,pns_ai_mcp,pns_ai_chatboo`** (el de E1, D38): analizador OK, 0 bloqueantes, 0 avisos, código 0,
       72 s. Log de 306 líneas: 0 Traceback, 0 «bad query» y ningún CRITICAL; «Running migration [14.0.3.1.973>]
       post-migrate» 1; versiones de la rama.
     - **WARNING del log (esperados):**
       - `py.warnings` de `jinja2`, 1 (librería de la imagen);
       - `ir_model` «Two fields … same label», 3 (`ai.log` ×2 y `ai.trusted.action` ×1): campos del fabricante,
         cosmético;
       - `ai_skill_disk` «MCP: skip retired unlink for pns_ai_mcp (no skill files on disk)», 2. Sale en todos los `-u`
         de noviembre (1 con un módulo, 2 con varios): comportamiento del fabricante.
     - **Parche 35 en una BD con historia:** «Seges patch 35: pns_ai_mcp.ir_cron_ai_api_result_cache_gc fixed» y
       «… ir_cron_ai_fetch_cache_gc fixed», 1 y 1; WARNING del 35, 0. Los dos crons pasan de `model.gc_expired()` a
       `model._gc_expired()`; inactivos por la neutralización antes y después.
     - **Skills retiradas:** las 7 (`annual_billing`, `cash_forecast`, `credit_facility`, `customer_risk_analysis`,
       `sys_info`, `users_all` y `users_logged`) estaban en `pns_demo` con fila de fábrica (`code`, `source_module`
       `pns_ai_chatboo` y `owner_id` vacío); tras el `-u`, 0. `ai_skill`: 13 antes y 10 después (las 6 no retiradas y,
       por la cuenta, 4 nuevas de 3.1.973; cuáles, no se sabe por esta copia). Cubre lo que el punto 7 («Skills sin
       importar en 3.1.879») decía que el laboratorio no podía cubrir.
     - **P-11** (consulta de `rama_comprobar.sh`): AI Administrators 3, sin AI Conversational 0. Solo después: el
       «antes» no se tomó.
     - **Diseños no vacíos, por SQL:** `chatboo_session.canvas_design` 12 y `chatboo_canvas_page.design` 0, iguales
       antes y después.
     - **A7** (solo después, D54; antes no, porque con el esquema de 3.1.879 y el código de 3.1.973 la lectura por ORM
       podía fallar): 12 y 0 diseños, iguales al SQL. 0 en todos los patrones de ruta del servidor como atributo
       (`src`/`href`/`url(` con `/`), `//`, `/web/content`, `/web/binary`, `/web/static`, `/pns_ai_`, `localhost`, de
       petición, de `http(s)` y de `<script src=`. Más de 0: `data:image/` 1, `pns-img:` 1 y `/web/image` 1.
     - **A7b** (diagnóstico de ese `/web/image`; contexto enmascarado, solo lectura; `t6-20261118-135128.txt`): 5
       apariciones en un solo diseño, anterior a 3.1.973, sin `data:image/` ni `pns-img:`. 4 están dentro de `<script>`:
       2 como datos embebidos (la ruta `/web/image/<modelo>/<id>/<campo>` como valor) y 2 en el código que decide si un
       valor es imagen (`startsWith("/web/image") || startsWith("http")`). La quinta es texto en una celda. Es decir: el
       diseño carga imágenes del propio Odoo por ruta relativa desde JavaScript. Decisión: D55 (arriba).
   - **Copias adaptadas de los scripts** (`~/pns_ai_3973/fase4/lab/cc0060e/`, fuera del repo):
     - `a7_recuentos.py`: solo cambia `BD = 'p15_pns_demo_14'`. SHA-256
       `836b5718adcf71f5327113b9744981adbd51c1a7eadf754680ac9b3eff24668b`. El original
       (`~/pns_ai_3973/fase4/csp/a7_recuentos.py`, `a8ab66c3f617665385d76655517d72b4de16fafeeca0235f865f8e8c37bdaa90`)
       no cambia;
     - `a7b_contexto.py` (nuevo, 47 líneas): solo lectura con `rollback` y contexto enmascarado. SHA-256
       `467129c3c547d1440411d47ab6acec37c188360a6297ee423d96e755bd02a519`.
   - **Pendientes:**
     - **(kit)** `bd-cargar` llama a `cmd_paridad` con el archivo como argumento, y la paridad lo trata como un módulo
       «por instalar»: por eso sale un falso «la instalación FALLARÁ» al final de `bd-cargar`. La primera parte de la
       paridad es la válida. Se analiza otro día en el kit, no aquí;
     - **conservación:** `p15_pns_demo_14` y la copia `.dump` se conservan hasta la limpieza final del staging, con el
       laboratorio `cc0060e`.
6. P-21 de nuevo (solo lectura), justo antes del `-u` del staging.
   - **Hecho el 18/11/2026** (16:17 UTC), dentro de T0 del [documento de subida](staging_3973.md), con
     `staging_3973/p21.sql`: el mismo resultado que el 10/11/2026 (12 contextos y 3 skills que se reescriben sin
     edición, 7 retiradas, 0 que adoptar, 0 archivadas).
7. Staging `pns_demo`.
   - **Hecho el 18/11/2026** (16:11 a 17:12 UTC): commit `5d0559b`, `-u pns_base,pns_ai_mcp,pns_ai_chatboo`, con el
     procedimiento de [staging_3973.md](staging_3973.md) (en `2e7f784`) y dos tandas nuevas, **T4b** (recarga de `es_ES`
     y rol Diseño con el web parado; sustituye los puntos 1 y 2 manuales de T7) y **F1** (borrado del código extraído en
     `/tmp`). Todas con `TODO OK`; la vuelta atrás no se usó. Resultado por tanda, salidas y lo que queda para la
     limpieza final: [staging_3973.md](staging_3973.md), apartado G. Copia previa de `pns_demo` (decisión a): T3,
     `ecde6453…f88b`. Web parado de 16:43 a 16:52 UTC. Lo previsto abajo, cómo quedó:
     - **parche 39** (decisión d): `iap_account` igual antes y después; la validación es la del laboratorio `cc0060e`;
     - **parche 35:** «fixed» 1 y 1 y 0 WARNING en el `-u`; `model._gc_expired()` en los dos crons (T6);
     - **skills:** las 7 retiradas a 0; 13 → 10, con las 4 nuevas de 3.1.973;
     - **P-11:** sin AI Conversational 0; AI Administrators como antes;
     - **diseño con `/web/image` (D55):** sesión 51, sin imágenes antes y después: **sin cambio de comportamiento**.
       Consola sin «Refused to load the image» antes y después (confirmado por Sergio, 18/11/2026);
     - **log del `-u`:** 0 Traceback, post-migrate 1, «Deleting field» 6, 48 módulos, «DROP leftover» 11. WARNING: los
       previstos y 2 `py.warnings` de `ir_actions_report.py` (core, informativos), en lugar del de `jinja2` de P-15;
     - **anexo de PNS-26:** la primera operación (35) falló en el core (`KeyError: 14`, plan no ejecutable) y se
       canceló; la segunda (36) se ejecutó con un «Confirmar». **El 40001 no se reprodujo** (0 y 0; en D47, 1 y 1): se
       queda en `INFO`, como preveía el documento;
     - **rol Diseño y `es_ES`:** hechos en T4b (abajo, «Tras el `-u`»).
   - **Pendientes de decisión, abiertos** (staging_3973.md, G):
     - el plan no ejecutable de la operación 35, anotado en el
       [seguimiento](seguimiento_informe_pns_ai.md) como observación sin ficha, candidata al informe al fabricante;
     - por qué el 40001 no salió en el staging: sin investigar;
     - proveedores 1 y 3 con 503 y tiempo agotado el 18/11 (lado de Google; cuota sin comprobar);
     - los WARNING de `pns_base.models.ir_translation` al recargar el idioma: se miran si salen otra vez en LIYBEN.
   - **Siguiente:** limpieza de `/tmp` del VPS y del equipo (copiando antes al equipo las salidas del VPS); después,
     LIYBEN (D50 antes de su despliegue) y el informe al fabricante (al final).
   - **Core `cc0060e`, cubierto en el laboratorio (18/11/2026):** ver el punto 4, «Laboratorio con el core cc0060e». El
     laboratorio (carpeta, imagen y BD) se conserva hasta la limpieza final del staging.
   - Anexo de PNS-26: un «Confirmar» correcto de la ficha (encadena `/confirm` y `/execute`). En el log, por cada
     uno, un ERROR «bad query» de `odoo.sql_db` sobre `ai_safe_operation` y un INFO «SERIALIZATION_FAILURE, retry 1/5»
     de `odoo.service.model`. No cuentan como fallo ([propuesta](propuesta_fase3_3973.md), «Anexo de PNS-26
     (serialización en `/execute`): confirmación en 3.1.973 (13/11/2026)», «Decisión de Sergio (13/11/2026)»).
     **Confirmado en el laboratorio en D47 (18/11/2026):** «bad query» 1 (`UPDATE "ai_safe_operation"`) y «retry 1/5»
     1, sin «retry 2/5» (`servidor-20261118-103306.log`; punto 4, resultados).
   - **Skills sin importar en 3.1.879 (añadido el 18/11/2026; punto 4, resultados, incidencia c):** comprobación en
     solo lectura de `ai_skill` para `sys_info`, `users_all` y `users_logged` (filas, `source_module` y `owner_id`),
     antes y después de la subida. En una instalación nueva de 3.1.879 no existen, porque piden `required_groups`;
     una BD con historia podría tenerlas, y su retirada no la cubre el laboratorio.
     Cubierto en P-15 sobre una copia de `pns_demo` (18/11/2026): las 7 retiradas tenían fila de fábrica y quedan en 0
     tras el `-u` (punto 5, D54).
   - **Añadido tras P-15 (18/11/2026; punto 5):**
     - **P-11** antes y después del `-u`, con la misma consulta de `rama_comprobar.sh`. Previsto después: sin AI
       Conversational 0;
     - **`ai_skill`:** lista de `code` con `source_module` y si `owner_id` está vacío, antes y después. Previsto: las 7
       retiradas, en 0; 13 → 10 si `pns_demo` sigue igual. P-15 ya cubrió la retirada en una BD con historia;
     - **diseño con `/web/image` (D55):** localizar su sesión con una consulta de solo lectura (solo el id de la
       `chatboo_session` cuyo `canvas_design` contiene `/web/image`) y abrirlo antes y después del `-u`. Anotar si se
       ven las imágenes y si la consola muestra «Refused to load the image» de `img-src`. Si se ven antes y no después,
       va en el documento de subida como cambio de comportamiento (decisión A, ya tomada);
     - **valores esperados del log del `-u`** (`docker compose run … | tee`): 0 Traceback; «post-migrate» de
       14.0.3.1.973, 1; «Seges patch 35: … fixed», 1 y 1; como WARNING esperados, los de P-15 (`jinja2` 1, «same label»
       3 y «skip retired unlink» 2). Duración en el laboratorio: 72 s (orientativa).

## Tras el `-u` (staging y LIYBEN)

**Staging, hecho el 18/11/2026** ([staging_3973.md](staging_3973.md), T4b y T6): rol Diseño con `use_fallback`
desactivado y solo en el proveedor 3 (SQL; el botón Canvas con los demás no se miró a la vista); crons de NUEVO-2 con
`model._gc_expired()`; P-11 sin AI Conversational 0; `es_ES` recargado. Lo que sigue queda para LIYBEN.

- **Rol Diseño (LIYBEN; sustituye a la del staging, que hablaba de `3.5-flash` y de la casilla «Design»):** en
  3.1.782 no existe `fit_design`, así que tras el `-u` nadie tiene el rol. D62: al proveedor 1
  (`models/gemini-3.5-flash`, inactivo) con `use_fallback` desactivado; D67: en el mismo `write`, quitarle Decisión,
  que el `-u` le da y su protocolo (`openai`) no admite. Botón Canvas: en L7 del
  [documento de despliegue](liyben_3973.md); el 20/11 quedó cubierto por L6 (no se abrió Chatboo, decisión A de Sergio)
  y se mira en el uso real. Detalle abajo, «Despliegue en LIYBEN».
- **Crons de NUEVO-2:** confirmar que el parche 35 los corrigió (`ir_cron.code`).
- **§6.2:** todos los AI Administrators ganan AI Conversational, y no se puede quitar. La ficha 26 se
  reproduce con un usuario que no sea AI Administrator. → **20/11/2026:** no aplica en LIYBEN (los tres internos activos
  son AI Administrators); se reproduce en el laboratorio antes del informe (abajo, «Uso real en LIYBEN hecho»).
- **Decisión 10:** antes de LIYBEN, consultar si sus AI Administrators tienen Ajustes (ahora también decide
  `_require_settings`).
- **D50 (Sergio, 18/11/2026; antes del despliegue en LIYBEN):** los 7 tokens de registro de LIYBEN se vacían justo
  antes de su despliegue. Antes de eso, comprobar en el core `cc0060e` qué hace `signup_cancel` de `auth_signup` (en
  `cc0060e`, `signup_token` se calcula por SQL; punto 4, «Laboratorio con el core cc0060e», paso 0).
  - **D50 hecho (19/11/2026; decisiones de Sergio: las recomendaciones de Claude).** Vaciado por SQL (A1), solo si el
    perfil es el esperado (B), probado antes en el laboratorio (C), los 8 tokens (E2 a) y compuerta con el perfil
    exacto y sin tokens vigentes de internos (E3). Tandas en [`liyben_3973/`](liyben_3973/) (se pegan como función;
    salidas en `~/pns_ai_3973/liyben/`, que no van al repo):

    | Archivo | Líneas | SHA-256 |
    |---|---|---|
    | `d50_core.sh` | 45 | `dff0219ca4102a210e314dc6cecd16b533309f1cf28576b4018b7543883943c9` |
    | `d50_lab.sh` | 85 | `436f041a00b055302f7628b28fc8362786f8bfa5d033d346c48464a4c6cf9bcb` |
    | `d50_vaciar.sh` | 102 | `301a0dd070bc980455d75e4e701bf85f0e9d8036b319b94c5099587cc55a3797` |

    - **Core** (`d50_core.sh`, solo lectura, 09:35 local, `d50-20261119-093520.txt`): referencia
      `/opt/odoo-src/14.0/odoo` en `cc0060e`, sin cambios locales; `auth_signup/models/res_partner.py` con SHA-256
      `c848abd85790cadd…`, el mismo que LIYBEN (tabla del 12/11 en
      [propuesta_fase3_3973.md](propuesta_fase3_3973.md)). `signup_cancel` (`:139-140`) es un `write` de
      `signup_token`, `signup_type` y `signup_expiration` a `False`. `signup_token` (`:27`) es calculado, con
      `inverse` `_inverse_token` (`:60-62`): `UPDATE res_partner SET signup_token = %s` con `None`. Las otras dos son
      columnas normales. En la BD, las tres quedan a `NULL`; por el ORM, además, `write_date`/`write_uid` y los
      `write` heredados. Sin token ni `signup_type`, `_get_signup_url_for_action` (`:78-87`) ya no pone el token en la
      URL, y a un contacto sin usuario no le da URL. Llaman a `signup_cancel`: `survey/controllers/main.py:146` y
      `auth_signup/models/res_users.py:251`.
    - **Laboratorio** (`d50_lab.sh`, `lab_pns_ai_cc0060e_14`, `shell --bd`, web parado, sin commit; 09:19:05 UTC,
      `d50lab-20261119-101905.txt`): en dos contactos de demostración sin usuario, `signup_prepare` (2 tokens
      distintos, tipo `signup`) y después `signup_cancel` en uno y el `UPDATE` de A1 en el otro. Los dos quedan
      igual: columnas `(False, None, None)` y ORM `(token, signup_valid, signup_url)` `(False, False, False)`. Huella
      de las columnas de signup antes y después del `rollback`, igual (`cf5237692fe1`). VEREDICTO OK.
    - **Perfil de LIYBEN** (solo lectura, 09:18:59 UTC; recuentos sin tokens, nombres ni ids): 8 tokens, todos de
      contactos activos; 0 contactos con tipo o caducidad sin token.

      | Usuarios del contacto | Tipo | Caducidad | n |
      |---|---|---|---|
      | portal, archivados | `signup` | sin caducidad | 3 |
      | externos sin portal, archivados | `signup` | sin caducidad | 2 |
      | externos sin portal, archivados | `reset` | sin caducidad | 1 |
      | sin usuario | `reset` | sin caducidad | 1 |
      | interno activo | `reset` | caducado (05/08/2025 13:42 UTC) | 1 |

      Los «7 tokens de registro vigentes sin caducidad» de la 3b son los 7 sin caducidad: los «6 de usuarios de
      portal archivados» son 3 de portal y 3 externos sin portal (los 18 archivados del 23/10 mezclaban los dos, ver
      [instalación en LIYBEN](instalacion_liyben_pns_ai.md), §6.2), y 2 de los 7 son de tipo `reset`. El octavo ya
      existía en la 3b (caducado desde el 05/08/2025) y no se contó por no estar vigente; está caducado, así que
      `signup_valid` es falso (`:42-43`) y `_signup_retrieve_partner` lo rechaza al comprobar la validez
      (`:169-172`).
    - **Ensayo en LIYBEN** (`d50_vaciar ensayo`, 09:24:18 UTC): TODO OK. Compuerta superada (8 tokens, el perfil de
      la tabla, 0 vigentes de internos), 8 filas vaciadas y 0 con token, tipo o caducidad dentro de la transacción,
      `ROLLBACK`, y 8 tokens después en otra sesión: LIYBEN sin cambios.
    - **En el despliegue, justo antes del `-u`:** `d50_vaciar VACIAR` (misma transacción, termina en `COMMIT`; esperado
      `TODO OK` y 0 tokens después). Si la compuerta falla (otro perfil o un token vigente de un interno), no se vacía
      nada y decide Sergio. Va al documento de despliegue en LIYBEN, insertado desde el archivo y con su huella.
      → En [liyben_3973.md](liyben_3973.md): L4 lo carga desde `/tmp/liyben_3973` (copiado por E1 con su huella) y
      L0 lo ensaya antes.

**Despliegue en LIYBEN hecho (20/11/2026):** commit `3df4307`, de 3.1.782 a 3.1.973, con corte del servicio de
10:42:25 a 10:55:23 UTC y todas las tandas con `TODO OK`. Resultado, INFO y lo que queda para la limpieza final y el
uso real, en G de [liyben_3973.md](liyben_3973.md).

**Uso real en LIYBEN hecho (20/11/2026; decisiones de Sergio: las recomendaciones de Claude).** Detalle en H de
[liyben_3973.md](liyben_3973.md), con las tandas `lu_*.sh` en [`liyben_3973/`](liyben_3973/).
- **Chatboo:** responde con el proveedor 2 (Qwen3.5-9B); sin botón Canvas, porque nadie con Diseño está activo (D62).
- **Cadena de Chatboo:** quitada en L7 y añadida de nuevo (fila 3, igual a la 2 salvo el id); sin efecto. Se queda.
- **D60:** las claves MCP no se regeneran; la generada durante U1 se borró. Los tres usuarios MCP, sin clave.
- **D61, ficha 26:** no aplica en LIYBEN. **Pendiente antes del informe (punto 5):** reproducirla en el laboratorio con
  `odoo-dev 14 shell` y `rollback`, con un usuario que no sea AI Administrator, marcando solo la casilla y la casilla
  junto con otra, y mirando el grupo antes del `rollback` (segunda ronda, decisión 5; fila 2.9 de
  [decisiones_pendientes_hallazgos_3879.md](decisiones_pendientes_hallazgos_3879.md)). Antes, decidir la BD: la copia
  del ensayo (`liyben_ens_14`) se borró en F0, y el core de LIYBEN (`cc0060e`) no es el del laboratorio estándar.
- **Las 3 traducciones de más:** la descripción en `es_ES` de `account_statement_import_online_wise` (OCA, no
  instalado), fuera de los `pns_*`; sin efecto; no se busca la causa.
- **Copias de L3:** se conservan hasta la limpieza final (punto 4).
- **Siguiente:** el merge (punto 3).

**Despliegue en LIYBEN (19 y 20/11/2026; decisiones de Sergio: las recomendaciones de Claude).** Documento:
[liyben_3973.md](liyben_3973.md), con sus tandas y el SQL en [`liyben_3973/`](liyben_3973/). Antes se hizo un ensayo
sobre una copia de LIYBEN (`liyben_ens_14`, Anexo A del documento), del que salen los «Esperado».

| | Decisión |
|---|---|
| D56 | **Ensayo** del `-u` sobre una copia de LIYBEN antes del documento, con el web parado de principio a fin. Laboratorio nuevo `~/GitHub/lab_liyben_3973` (no se toca `cc0060e`); Dockerfile = el del VPS exacto más el bloque del core `cc0060e`; en el ensayo, el `-u` y la recarga con el rol (D50 no: ya ensayado en LIYBEN); OCA y `vertical-instaladores` en los commits del VPS (clones fijados y restaurados al acabar). Hecho el 19/11 |
| D57 | **Copia completa antes del `-u`:** BD y filestore, por SSH al equipo, con el web parado. Orden: parar el web → copia → `d50_vaciar VACIAR` → `checkout` → `-u` |
| D58 | **Commit que se despliega:** el HEAD de la rama en el commit del documento, con compuerta de árbol de los módulos = `5d0559b` (688 / `0dc381e0…ba7a`). Concreción (19/11): HEAD = `origin/14.0-pns-ai-3973`, de `c6ec077` a HEAD solo cambia `docs/`; el hash, en `commit.txt` (E0) y en G |
| D59 | **Comprobaciones heredadas** (§3 «Al terminar» del plan de la 3879 y A.4 a A.6 de E3′/E4′), en L0, de solo lectura. Bloquean las operaciones pendientes o confirmadas sin ejecutar con pasos sobre `ai.trusted.action`; INFO: decisión 10, servidores MCP (PNS-17), PNS-82, PNS-37 y A.6 |
| D60 | **Claves MCP** (revocadas el 27/10): no se regeneran en el despliegue (Nginx da 404 en `/mcp`, D20); si hacen falta, en el uso real |
| D61 | **Ficha 26** (§6.2, usuario sin AI Administrator): al uso real. En el despliegue, solo el SQL de AI Conversational de los AI Administrators |
| D62 | **Rol Diseño** al proveedor 1 (`models/gemini-3.5-flash`, inactivo) y `use_fallback` desactivado. El rol dice «Nobody holding it: Conversation answers» (`pns_ai_mcp/data/ai_provider_role_data.xml:48-57`) y el motor solo usa titulares activos: mientras el 1 esté inactivo, nadie diseña (no cae a Qwen 9B) |
| D63 | Nombre: `docs/pendiente/liyben_3973.md`; SQL y tandas en `docs/pendiente/liyben_3973/` |
| D64 | **Los 3 AI Administrators se quedan** (ids 2, 6 y 7; D4 y D46 decían dos). El 2 no tiene AI Conversational y lo gana fijo en el `-u` (§6.2) |
| D65 | **«Antes» de LIYBEN con P-21 adaptado a 3.1.782:** A, lista de `ai/` de `578859b` al commit = la del fabricante de 3.1.782 a 3.1.973 (A 15, D 12, M 19, `f413c755…d4`); B, esquema por `information_schema` y correspondencia exacta de los 56 contextos y las 10 skills con los archivos de 3.1.782 por `source_module` + `rel_path`; C, «antes» y P-21 con las listas de 3.1.782; D, contraste con I0. Una edición de fábrica es FALLO. Criterio de edición (el contador de uso de 3.1.782 pone `write_date`): contexto editado si `write_uid` ≠ 1, o `write_date` posterior al último `-u` y distinto de `last_used`; skill editada si `write_date` es posterior al último `-u` o `write_uid` ≠ 1 |
| D66 (revisada) | **Recarga de `es_ES`: B′.** En una sola transacción, guardar las filas `es_ES` de fuera de los `pns_*`, `_update_translations('es_ES', True)` de los tres `pns_*` y restaurar por `id` las que cambiaron (y reinsertar las borradas). Los `pns_*` reciben sus 196 traducciones cambiadas y nada de fuera cambia |
| D67 | **Rol Diseño con un solo `write`** del proveedor 1: `role_ids: [(3, decisión), (4, diseño)]` y `use_fallback` de Diseño a falso. El `-u` da Decisión al 1 (`fit_decision = t` en 3.1.782) y en 3.1.973 solo `systemone` la admite (`_check_roles_match_protocol`, `pns_ai_mcp/models/ai_provider.py:625-634`; `chooses`, `pns_ai_mcp/lib/llm/drivers/systemone_driver.py:17`): sin quitarla, el `write` da `ValidationError` |

Historia de D66: primera elección **B** (solo los tres `pns_*` con sobrescritura, en vez del asistente sobre los 215
módulos), revisada el 19/11 tras la medida de Y6 v3: B reescribía 13 textos y 36 orígenes `code` de otros módulos (en
Odoo 14 la traducción `code` se busca por el texto inglés, de cualquier módulo).

- **Ensayo (19/11, `liyben_ens_14`):** «antes» con P-21 (Y4): 13 contextos y 3 skills (`billing`, `financial_health`,
  `forecast`) reescritos sin edición, 3 contextos nuevos (`page_tab`, `discovery_page_tab`, `discovery_page_tab_es_ES`),
  6 skills retiradas (`annual_billing`, `credit_facility`, `customer_risk_analysis`, `sys_info`, `users_all`,
  `users_logged`), ninguna edición de fábrica. `-u` (Y5, dos veces): 67-72 s, 0 Traceback, las 5 `fit_*` y 7 campos
  más borrados (todos documentados: `ai.mcp.user.key_pin*`, PNS-84 y D60; `ai.log.agent_id`/`agent_display`, `ai_log`
  vacío; `ai.skill.capture.wizard.from_chatboo`, transitorio), 1 migración, parche 35 `fixed` 2, «DROP leftover» 22.
  Recarga B′ y rol (Y6 v3) con `TODO OK`; «después» (Y7) con `TODO OK`.
- **Cron nuevo:** `pns_ai_mcp.ir_cron_ai_journal_trash` (`pns_ai_mcp/data/journal_trash_cron.xml:5-15`,
  `noupdate="1"`, `active` verdadero, diario) es el único cron que crea el `-u`; en LIYBEN, sin neutralizar, queda
  **activo**, y los 6 de antes siguen activos. `pns_ai_mcp.journal_trash_days` no existe tras el `-u` (vale 30 por
  defecto).
- **El `-u` escribe los 56 contextos y las 10 skills** (`write_date` del `-u`), no solo los 13 y 3 de P-21: las
  ediciones de fábrica solo se detectan **antes** del `-u` (L0).
- **Roles tras el `-u`:** 7 (`conversation`, `audio`, `vision`, `video`, `decision`, `design`, `parser`); `parser` con
  alternativa `conversation`; todos salvo Diseño con `use_fallback` activado (tras L4b).
