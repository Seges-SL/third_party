# Plan de portado de los parches de Seges a pns_ai 3.1.973

- **Fecha:** 10/11/2026 (propuesta y decisiones) · 11/11/2026 (fases 0 y 1; fase 2a).
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

## Fase 4 — Zonas que cambian: 27, 29 y 34 (en este orden)

- **27:**
  - escapar `<` en `json.dumps` (`chatboo_canvas.py:1097, 1426, 1439, 2046-2047`);
  - **CSP (decisión 6):** se mantiene la cabecera HTTP del fabricante y se añade la `<meta>` de Seges
    (`img-src data: blob:; connect-src 'none'; …`) en el diseño y en las dos descargas, para que gane la más
    estricta y quede cerrado `'self'`;
  - comprobar antes que el lienzo de 3.1.973 sigue pintando sin `'self'`, sobre todo `/sales-board` y las
    imágenes de la página. Si algo legítimo necesita `'self'`, se presenta a Sergio antes de decidir;
  - tests: `test_seges_chatboo_canvas` y P-9 parte A como test.
- **29:** muestra para Design (`:829-858`) y `place_rows_on_page` (`:2062-2105`).
- **34:** `log_no_page` (`:587-616`); `_process` y `_save_to_session` (`chatboo_async_request.py:149-162,
  1184-1410`), con la opción A y F1. P-13 en la interfaz.

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
2. Fase 3: P-22 y, si Sergio pasa a la opción A, P-20.
3. Fase 4: P-13.
4. Con toda la rama:
   - P-14, en una BD instalada con `~/pns_ai_3973/fase0/modulos_3879` y después actualizada;
   - P-2, con tres casos:
     - (a) `-u` desde 3.1.879 con el parche 35: corrige los dos crons;
     - (b) `-u` desde 3.1.879 con la base limpia y después a la rama con el 35: el script no se ejecuta y
       los crons siguen rotos; corrección a mano;
     - (c) instalación limpia (`lab_pns_ai_3973_14`): crons bien y el script no los toca.

     `lab_pns_ai_3973_14` solo cubre (c); (a) y (b) usan `~/pns_ai_3973/fase0/modulos_3879`;
   - P-11;
   - `_require_settings` (con y sin el 32);
   - reintento de la tarjeta (manual).
5. P-15: `-u` completo sobre una copia de `pns_demo` que carga Sergio.
6. P-21 de nuevo (solo lectura), justo antes del `-u` del staging.
7. Staging `pns_demo`.

## Tras el `-u` (staging y LIYBEN)

- **Rol Diseño:**
  - `use_fallback` desactivado;
  - el rol solo en `3.5-flash`: el `-u` se lo da a todos los proveedores con la casilla «Design», `lite`
    incluido;
  - comprobar que no aparece el botón Canvas en los demás.
- **Crons de NUEVO-2:** confirmar que el parche 35 los corrigió (`ir_cron.code`).
- **§6.2:** todos los AI Administrators ganan AI Conversational, y no se puede quitar. La ficha 26 se
  reproduce con un usuario que no sea AI Administrator.
- **Decisión 10:** antes de LIYBEN, consultar si sus AI Administrators tienen Ajustes (ahora también decide
  `_require_settings`).
