# Análisis pns_ai_mcp (Odoo 14) — Bloque 6: ejecución de código (relaxaicode, sandbox y skills)

Repositorio `third_party` (Odoo **14.0**, rama `14.0-analisis-pns-ai`). Código de terceros:
solo análisis, no se modifica ni se diseña nada. Núcleo/OCA de referencia en
`/opt/odoo-src/14.0/`. Etiquetas: **HECHO** (archivo:línea verificada), **INFERENCIA**
(deducción del código) y **PENDIENTE** (a confirmar con `odoo-dev 14`).

Piezas analizadas (todas leídas enteras salvo lo indicado en la tabla de cobertura):
`controllers/tools_relaxaicode.py`, `controllers/context_builder.py`,
`controllers/validators.py`, `models/ai_execution_engine.py`,
`utils/skill_runtime.py`, `utils/sandbox_helpers.py`, `utils/skill_live_code.py`,
`utils/skill_files.py`, `utils/skill_errors.py`, `utils/untrusted_html_contract.py`,
`utils/relaxaicode_recipe.py` (parcial, ver tabla), `utils/relaxaicode_render.py` (no leído
entero, 2607 líneas — ver §7 y cobertura), `wizard/skill_capture_wizard.py`,
`wizard/skill_import_wizard.py`, `wizard/agent_skill_import_wizard.py`,
`models/ai_skill.py` (apartados relevantes), `models/ai_system_action.py`,
`models/ai_trusted_action.py`, `models/mcp_safe_operation.py` (apartados de cursores),
`controllers/controller_helpers.py` (caja A). Contraste: `tests/test_relaxaicode_*.py`.

---

## 1. Qué es relaxaicode

- **HECHO** (`controllers/tools_relaxaicode.py:1504-1562`): `relaxaicode` es una herramienta
  MCP (`@mcp_tool(name='relaxaicode', is_write=True)`) que **ejecuta Python** dentro del
  proceso de Odoo con acceso al ORM vía la global `env`. El lenguaje es **Python nativo**
  (no un DSL): se compila con `compile(..., 'exec')` y se ejecuta con `exec()`.
- **Quién escribe el código**: lo escribe el **LLM** (el modelo del proveedor configurado).
  El contrato del prompt de sistema le dice que asigne el resultado a `result`
  (`ai/contexts/core/system_prompt.xml:81-82`). También lo escribe:
  - un **skill** (su `code_body`, Python relaxaicode guardado en `ai.skill.code_body`,
    [CONOC] §1 `models/ai_context.py` tabla, campo línea 125; ejecutado por
    `utils/skill_runtime.py:656-659`);
  - indirectamente el **usuario**, al capturar una ejecución exitosa como skill
    (`wizard/skill_capture_wizard.py`, §6).
- **Desde dónde se lanza** (HECHO): (a) como **herramienta MCP** invocada por el LLM desde
  el orquestador (`utils/agent_engine.py:3378` `get_tool_function('relaxaicode')`); (b) como
  **code_body de un skill** disparado por un **slash command** en Chatboo
  (`utils/agent_engine.py:1210,1276,1359-1376`); (c) implícitamente, cualquier turno de chat
  que el modelo decida resolver con la tool. No hay endpoint HTTP directo que el usuario
  llame con código a mano: siempre pasa por el LLM o por el runtime de skills.

---

## 2. Cómo se ejecuta

- **exec del builtin, NO safe_eval del core** (HECHO, `tools_relaxaicode.py:1999` `compile`,
  `:2095` `exec(byte_code, safe_context, safe_context)`). No se usa
  `odoo.tools.safe_eval`. La contención se construye a mano: validación AST previa
  (§3) + `__builtins__` recortado + `env` endurecido (§4). En skills el patrón es idéntico
  (`skill_runtime.py:656-659`, `exec(compile(code,'<skill:..>','exec'), ctx, ctx)`).
- **Mismo proceso de Odoo** (HECHO): no hay subproceso, contenedor ni aislamiento de SO. El
  código corre en el worker HTTP/SSE de Odoo con el intérprete y el `env` del servidor.
- **Límites de tiempo/memoria** (HECHO, comentario `tools_relaxaicode.py:26-32`): el módulo
  NO impone límites de CPU/memoria durante el `exec`; **delega** en los límites del worker
  de Odoo (`limit_time_real` / `limit_time_cpu` / `limit_memory_hard`, ver
  `docs/seguridad_dos_cajas.md`). **INFERENCIA**: si esos límites no están configurados en el
  despliegue, un bucle del LLM puede consumir CPU/memoria sin tope del módulo.
- **Tope de tamaño de SALIDA** (HECHO, `:31-32`, `:57-84`, `:2264-2281`):
  `RELAXAICODE_MAX_RESULT_ROWS = 50000` filas en `data`/`groups` y
  `RELAXAICODE_MAX_TEXT_CHARS = 2_000_000` (~2 MB) en `formatted_text`/`text`/`html`; si se
  supera devuelve error `ResultTooLarge` reintentable. Comprobación O(1) (solo `len`), no
  serializa toda la estructura.
- **Caja A — cursor READ ONLY** (HECHO, `tools_relaxaicode.py:1935-1942`,
  `controller_helpers.py:184-252`): la lectura corre sobre un cursor aislado marcado
  `SET TRANSACTION READ ONLY`; `cr.commit` se neutraliza (monkey-patch a no-op,
  `controller_helpers.py:234-251`); en `finally` se hace `rollback()` + `close()`
  (`tools_relaxaicode.py:2826-2837`). Si no se puede marcar READ ONLY, **falla cerrado**
  (UserError, `controller_helpers.py:218-224`). Desactiva tracking/mail para evitar
  escrituras colaterales (`:225-231`).

---

## 3. Validación AST (`controllers/validators.py`)

Entrada única: `validate_relaxaicode_source_ast(code)` (`:1597`), que devuelve
`(is_valid, error, requires_write)`. Antes hay reescrituras "de reparación suave"
(`repair_locals_dir_checks`, `repair_unsafe_sort_keys`, `repair_cr_dbname`,
`repair_registry_models`, `repair_percent_format_strings`) y un segundo intento
`_attempt_syntax_repair` (`tools_relaxaicode.py:861-1275`, reparaciones regex del JSON del LLM).

### 3.1 Imports (HECHO)
- **Peligrosos bloqueados** `RELAXAICODE_DANGEROUS_MODULES` (`:77-84`): `odoo`, `os`, `sys`,
  `pathlib`, `shutil`, `tempfile`, `socket`, `urllib`, `http`, `requests`, `ftplib`,
  `subprocess`, `multiprocessing`, `pickle`, `marshal`, `ctypes`, `importlib`, `builtins`,
  `__builtin__`, `__builtins__`.
- **Red/FS** `RELAXAICODE_NETWORK_IMPORT_MODULES` (`:66-69`): mensaje único hacia
  `propose_safe_operations op=fetch_url`.
- **Permitidos** `RELAXAICODE_SAFE_MODULES` (`:85-94`): `datetime, date, time, collections,
  itertools, functools, math, statistics, decimal, json, base64, hashlib, re, string,
  operator, csv, io, copy, uuid, random, calendar, textwrap, unicodedata, platform, zoneinfo`.
- **Excepción `urllib.parse`** (HECHO, `:1711-1712` AST + `context_builder.py:160-169`
  runtime): solo `from urllib.parse import <nombre>` (funciones de texto); `import urllib.parse`
  prohibido (ligaría `urllib` → `urllib.request`). Validado por `tests/test_relaxaicode_imports.py`.
- Validación en AST (`:1679-1726`) y refuerzo en runtime con `guarded_import`
  (`context_builder.py:146-181`): doble capa, misma lista.

### 3.2 Nombres y builtins prohibidos (HECHO)
- `dangerous_functions` (`:1660-1663`): `open, eval, exec, compile, __import__, input,
  raw_input, file` — tanto como `Name` (`:1733-1746`) como método `.attr` (`:1749-1754`).
- `dangerous_vars` (`:1670-1672`): `locals, globals, vars, dir` (Load → rechazado, `:1871-1880`).
- Métodos de cursor/transacción (`:1757-1766`): `execute, executemany, commit, rollback,
  savepoint, dictfetchall, dictfetchone`.
- `type(name, bases, dict)` de 3 args (crear clases dinámicas) bloqueado (`:1778-1782`);
  `class` prohibida (`:1949-1953`); `return` solo dentro de `def` (`:1787-1795`).
- **`__builtins__` recortado** (`context_builder.py:239-251`): lista blanca de ~55 builtins;
  `setattr`/`delattr` eliminados a propósito (evitar escritura ORM encubierta, `:246-247`);
  `getattr` sustituido por `guarded_getattr` (`:265`); `__import__` por `guarded_import`.

### 3.3 Cobertura por vector típico de escape (contraste con `test_relaxaicode_sandbox_escapes_e2e.py`)

| Vector | ¿Bloqueado? | Dónde (archivo:línea) | Payload en el test e2e |
|---|---|---|---|
| Dunders `__class__`/`__subclasses__`/`__bases__`/`__mro__`/`__globals__` (literal) | **Sí** (AST) | `validators.py:113-131` `DANGEROUS_ATTR_NAMES`; attr `:1850-1856` | `().__class__.__bases__[0].__subclasses__()`, `{}.__class__.__mro__` (`:35-36`) |
| Dunder con nombre dinámico `getattr(x,'__cla'+'ss__')` | **Sí** (runtime) | `context_builder.py:111-143` `guarded_getattr` (dunder genérico + denylist) | `getattr((), '__cla'+'ss__')`, `getattr(getattr((),n1),n2)` (`:45-46`) |
| `getattr` literal con dunder/attr peligroso | **Sí** (AST) | `validators.py:1899-1917` (2º arg string) | — |
| `str.format` / `format_map` con dunder `{0.__class__}` | **Sí** (AST plantilla) | `validators.py:1926-1938` | `'{0.__class__}'.format(())` (`:37`) |
| `string.Formatter().get_field/vformat` | **Sí** (nombre) + módulo recortado | AST `DANGEROUS_FORMAT_NAMES` `:136-139,1860-1866`; runtime `context_builder.py:232-236` (`string` sin `Formatter`/`Template`) | `string.Formatter().get_field(...)` (`:38`) |
| Frames / tracebacks `f_back`,`f_globals`,`tb_frame`,`gi_frame`,`cr_frame` | **Sí** | `validators.py:125-128` (denylist) + `guarded_getattr` | `e.__traceback__` (`:43`); `getattr((lambda:0),'f_'+'globals')` (`:47`) |
| Generadores/corrutinas (`gi_frame`/`gi_code`/`cr_frame`/`ag_frame`) | **Sí** (attrs en denylist) | `validators.py:128` | No hay payload específico en el test (INFERENCIA: cubierto por la denylist, no probado) |
| Acceso a builtins reales `__builtins__` | **Sí** | AST `:1885-1891`; `__builtins__` recortado | — |
| `import os` / `__import__('os')` | **Sí** | AST `:1684-1699,1769-1773`; `guarded_import` | `import os`, `__import__('os').getcwd()` (`:39-40`) |
| `class X` / `type('X',(),{})` | **Sí** | AST `:1778-1782,1949-1953` | `class X(object): pass`, `type('X',(),{})` (`:41-42`) |
| `cr`/`_cr`/`registry`/`pool` | **Sí** | `validators.py:113-131` (`cr,_cr,pool,registry,_registry`) + `guarded_getattr` | — (ver §4 el agujero via métodos de negocio) |
| Mutadores ORM ofuscados `getattr(rec,'write')`, `attrgetter('write')` | **Marca requires_write / AttributeError** | AST `_detect_requires_write_from_ast` `:966-976`; runtime `guarded_getattr` `:130-134` | `WRITE_BYPASS_PAYLOADS` (`:60-64`), test `test_obfuscated_orm_write_rejected` (`:173-205`) |

**Observaciones (INFERENCIA/HECHO):**
- `type(value).__name__` se permite explícitamente como etiqueta string
  (`validators.py:663-671,1854-1855`); el resto de `obj.__name__` se bloquea.
- La e2e **no** prueba generadores/corrutinas ni (lo más importante, §4) getattr sobre
  **métodos de negocio que abren cursores nuevos** (`resolve_execute`, `cleanup_*`,
  `execute_plan_now`): el corpus solo cubre `write` ofuscado. Es un hueco de cobertura.

### 3.4 Lambdas / sort keys (HECHO)
`_SAFE_LAMBDA_MSG` (`:1077-1089`); solo se permiten lambdas/keys "accesores"
(`_is_safe_accessor_expr` `:1100-1123`: sin yield/raise, solo calls a builtins seguros
`_SAFE_LAMBDA_CALL_NAMES` `:992-995`, métodos seguros `_SAFE_LAMBDA_METHODS` `:996-1001`,
`operator.itemgetter/attrgetter`, o defs del propio script). Las keys inseguras se reescriben
a decorate-sort (`repair_unsafe_sort_keys` `:1438-1594`).

### 3.5 Detección de escritura (`_detect_requires_write_from_ast`, `:913-989`) (HECHO)
Marca `requires_write=True` ante: `create/write/unlink` (`:926`), `.copy()` salvo
`copy.copy`/`copy.deepcopy` (`:951-954`), asignación por atributo `rec.campo = x` (`:984-988`),
`AugAssign` sobre atributo (`:978-982`), `getattr/attrgetter('write'...)` (`:966-976`), y una
lista de **métodos de negocio con efecto secundario** `side_effect_methods` (`:928-944`):
`confirm_by_user, cancel_by_user, execute_plan_now, resolve_confirm_and_execute,
resolve_confirm, resolve_execute, action_confirm_and_execute, action_execute_plan,
action_cancel, cleanup_expired, cleanup_stuck_state, create_verification,
button_immediate_install/upgrade/uninstall`. Si `requires_write` → la tool **rechaza**
(no ejecuta, `tools_relaxaicode.py:1907-1922`): relaxaicode es SOLO LECTURA; las escrituras
van por la Caja B.

---

## 4. Qué objetos recibe el código y con qué usuario

`build_safe_context` (`context_builder.py:184-551`) inyecta (HECHO):
- **`env`**: envuelto en `GuardedSandboxEnv` (`:56-108`), sobre el **cursor READ ONLY (caja A)**
  para lecturas (`tools_relaxaicode.py:1936-1942`). El wrapper bloquea `env['ai.api.server']`
  y `env['ai.context']` (catálogos, `:72-89`) y propaga el bloqueo a `env.sudo()['...']`,
  `with_context`, etc. (`:65-67,93-102`).
- Objetos: `user`, `company`, locale (`user_lang`, `pk_*`), `today`/`now` en huso del usuario
  (`:339-397`), `dbname`, módulos seguros, excepciones, helpers (`format_amount`,
  `field_selection`, `get_safe_plan_steps`, etc.). `previous_result`/`raw_data` (`:501-509`).
- **Usuario**: el del turno (`controller._get_env_for_operation('read')`, `:268`); en skills el
  `env` del motor de chat (usuario humano, `skill_runtime.py:650-652`). **No** es SUPERUSER por
  defecto: corre con los permisos del usuario del chat. **`sudo()` sí está disponible** en el
  sandbox (`_ast_is_env_root` lo permite, `validators.py:828-837`); eleva permisos de lectura.
- **¿Puede escribir en la BD?** (HECHO/INFERENCIA):
  1. Por diseño **no**: READ ONLY + AST que marca escrituras → rechazo (§3.5). Las escrituras
     van por la Caja B (`propose_safe_operations`).
  2. `env.cr`/`registry`/`pool` están bloqueados (no hay SQL crudo).
  3. **Agujero (ver pregunta 9 / §riesgos)**: métodos de negocio que **abren cursores nuevos**
     (`registry.cursor()`, no READ ONLY) invocados con **getattr dinámico** evaden tanto el
     detector de escritura como `guarded_getattr`.
- **¿Archivos/red/procesos?** (HECHO): no. `open`/`os`/`subprocess`/`socket`/`requests`
  bloqueados en AST y `guarded_import`. La red externa solo por Caja B `fetch_url`/`api_call`.

### Pregunta 9 (abierta en el bloque 5): ¿puede el sandbox llamar a
`ai.system.action.apply_*`, `ai.trusted.action.apply` o abrir cursores nuevos (`resolve_*`)?

Respuesta (HECHO + INFERENCIA; PENDIENTE confirmar con `odoo-dev 14`):

- **Los modelos son accesibles**: `ai.system.action` y `ai.trusted.action` **no** están en la
  lista de catálogos prohibidos (`RELAXAICODE_FORBIDDEN_CATALOGUE_MODELS` solo lista
  `ai.api.server` y `ai.context`, `validators.py:146-149`). `env['ai.system.action']` y
  `env['ai.safe.operation']` se obtienen sin problema.
- **`ai.system.action.apply_*` y `ai.trusted.action.apply`** (HECHO): **no** figuran en
  `side_effect_methods` del detector de escritura (`validators.py:928-944`), así que una
  llamada literal **no** se marca `requires_write` y la tool **sí ejecutaría**. Pero estos
  métodos escriben sobre `self.env.cr` = el **cursor READ ONLY de la caja A**
  (p. ej. `apply_user_add_group`→`user_add_group`, `ai_system_action.py:716-719`;
  `apply.apply_method`, `ai_trusted_action.py:117-122`). **INFERENCIA**: el `SET TRANSACTION
  READ ONLY` aborta el write → fallo controlado, **no persiste**. `apply_module_update`
  (`:630-668`) llama a `button_immediate_*`, que en core hace `SELECT ... FOR UPDATE NOWAIT`
  + `cr.commit()` (`/opt/odoo-src/14.0/odoo/addons/base/models/ir_module.py:550-573`): el
  FOR UPDATE sobre transacción READ ONLY falla, y además `button_immediate_*` sí está en
  `side_effect_methods` (bloqueado si se llama literal). `ai.trusted.action` además guarda
  modelo+método **libres** editables por cualquier admin IA ([CAJA_B] §3.5), así que el
  "vocabulario cerrado" es ampliable.
- **`resolve_*` / `execute_plan_now` / `cleanup_*`** (HECHO del detector + INFERENCIA del
  agujero): estos métodos **sí** abren **cursores nuevos no-READ-ONLY** con
  `registry.cursor()` (`mcp_safe_operation.py:603,828,949,1134,1189,1471` y
  `_claim_execute` hace `cr.commit()` `:1171`). **Están** en `side_effect_methods`
  (`validators.py:928-944`), de modo que una **llamada literal** `op.resolve_execute()` se
  marca `requires_write` y **se rechaza** antes de ejecutar (`tools_relaxaicode.py:1907-1922`).
  **PERO** el detector de escritura por `getattr`/`attrgetter` solo cubre los 4 mutadores ORM
  (`RELAXAICODE_ORM_WRITE_ATTRS = create/write/unlink/copy`, `validators.py:166-168,966-976`),
  y `guarded_getattr` tampoco lista estos nombres de negocio (solo denylist de dunders/frames,
  ORM mutators y catálogo, `context_builder.py:124-143`). **INFERENCIA (riesgo alto)**:
  `getattr(env['ai.safe.operation'].browse(id), 'resolve_execute')()` —o `cleanup_stuck_state`,
  `execute_plan_now`, `_retry_confirmed_not_executed`— **no** se marca `requires_write`, **no**
  lo bloquea `guarded_getattr`, y al ejecutarse abre un cursor nuevo que **sí** puede
  **persistir** (su propio `commit`), saltándose la garantía READ ONLY de la caja A. Requiere
  que exista una `ai.safe.operation` en estado `confirmed` (para `resolve_execute`), condición
  que no siempre se da, pero `cleanup_*`/`_retry_*` son `@api.model` y actúan sobre la cola
  existente. **El test e2e NO cubre este vector** (solo `getattr→write`, `:60-64`).
  **PENDIENTE**: reproducir en `odoo-dev 14` si `getattr(op,'resolve_execute')()` o
  `getattr(env['ai.safe.operation'],'cleanup_stuck_state')()` ejecutan y persisten.

---

## 5. `ai.execution.engine`: resolución rol → bundle → proveedor

(HECHO, `models/ai_execution_engine.py`) Modelo **abstracto** `ai.execution.engine`
(`:108-109`). Flujo:
1. `chat_completion(agent_code, messages, tools, ...)` (`:533-600`) resuelve el código de
   agente con `resolve_inference_agent_code` (`ai_agent_consumer.py:36-51`: rol explícito o
   clave de feature `FEATURE_AGENT_CODES`).
2. `get_providers_for_agent` (`:149-223`): (1) `provider_id` explícito de UI → ese;
   (2) failovers explícitos del agente (`ai.agent.provider` ordenados por prioridad, `:177-179`,
   leídos con `sudo()` porque son infraestructura, `:145`); (3) si hay un único proveedor →
   ese; (4) si hay varios sin asignar → auto-crea la cadena de failover (`:204-221`);
   (5) ninguno → `RedirectWarning`/`UserError`.
3. `_driver_for_provider` (`:225-274`): instancia el driver (`lib/llm/drivers.get_llm_driver`
   por `protocol`), resuelve modelo/endpoint y la **API key** vía
   `provider._api_key_for_inference()` (`ai_provider.py:109-117`, `self.sudo().api_key`); lo
   envuelve en `_LoggedProviderDriver` (`:23-51`) que registra cada `chat_completion` en
   `ai.log`. **No** reenvía `X-Mcp-Token` (las tools corren in-process, `:257-260`).
4. Failover: itera proveedores, registra `log_provider_failover` (`:562-597`). Excepción:
   desbordamiento de contexto (`_is_context_overflow`, `:64-70`) aborta **sin** failover
   (`:581-593`). `resolve_provider` (`:602-606`) devuelve el primero de la cadena.

No hay un concepto literal de "bundle" en este modelo; el "bundle" (contextos always-on del
agente) vive en `ai.agent`/`ai.context` ([CONOC] §7). Aquí la cadena es rol(agente) →
proveedor(es) → driver LLM.

---

## 6. Skills: runtime, live code, creación/activación, ZIP

- **Runtime** (HECHO, `utils/skill_runtime.py`): `bootstrap_skill_code_body` (`:587-691`)
  parsea argumentos del slash (`parse_skill_arguments` `:488-584`), enriquece fechas
  (`enrich_params_with_dates`), construye el **mismo** `build_safe_context` (caja segura,
  **sin** la caja A READ ONLY: usa `_get_env_for_operation('read')` directo, `:626-627,650-652`)
  y ejecuta el `code_body` con `exec`. El contrato exige que `result` sea dict; si trae
  `formatted_text` + `__return_direct__`/`__stop_after_direct__`, se marca
  `__fmt_type__='author_html'` (confianza de plataforma, `:662-668`). `try_skill_fast_path`
  (`:917-1059`) ejecuta el ciclo determinista multi-ronda sin LLM: presentación directa,
  `propose_steps` auto-confirmables (fetch_url whitelist / api_call trusted) o toast Confirm.
- **Nota caja A/caja segura** (INFERENCIA, importante): el `code_body` de skill se ejecuta en
  `bootstrap_skill_code_body` **sin** el cursor READ ONLY (a diferencia de la tool
  `relaxaicode`, §2). La contención de escritura del skill descansa en la validación AST al
  **guardar** (`_check_code_body_contract`, abajo), no en un cursor READ ONLY en ejecución.
  **PENDIENTE** confirmar si un `code_body` que pase el AST pero llame getattr a métodos de
  negocio escribiría (mismo agujero §4) ejecutándose por slash.
- **Live code** (HECHO): `utils/skill_live_code.py` **no** es ejecución en vivo; es el candado
  AST `code_has_frozen_result_rows` (`:40-66`) que **rechaza al guardar** un `code_body` que
  parezca una captura congelada (asigna `data`/`rows`/`rows_src` a ≥3 dicts literales sin
  construirlos en un bucle `for`+`append/extend`). Obliga a consultar en vivo.
- **Cómo se invocan** (HECHO): por slash command resuelto en `agent_engine.py:1210-1276`;
  si el skill tiene `code_body` se intenta fast-path server-side; si es painter-free, los
  datos tabulares se entregan al LLM. Help (`?`) siempre determinista.
- **Quién puede crear/activar** (HECHO, `security/ir.model.access.csv`):
  - `ai.skill`: lectura para `base.group_user` (`:16`, `1,0,0,0`); **escritura total para
    `group_ai_writer`** (`:20`, `1,1,1,1`).
  - `pns_ai_mcp.skill.capture.wizard`: `group_ai_writer` `1,1,1,1` (`:24`).
  - Importadores ZIP (`skill.import.wizard`, `agent.skill.import.wizard`): `group_ai_admin`
    `1,1,1,1` (`:26,31`).
  - Por tanto **un Writer** (no solo admin) puede crear y activar skills.
- **Writer vía `skill.capture.wizard` con `from_chatboo`** (HECHO, riesgo):
  `wizard/skill_capture_wizard.py` crea un skill a partir de un log de ejecución relaxaicode
  exitosa (`source_log_id`, `:20-26`; `code_body = log.code_to_execute`, `:123`).
  `action_create_draft` (`:148-213`) normalmente crea el skill **inactivo** (`active=False`,
  revisión del admin), **salvo** cuando `from_chatboo` es True: entonces
  **`'active': bool(self.from_chatboo)` = True** (`:190`), es decir el skill queda **activo y
  usable (`/code`) sin revisión del administrador**. `from_chatboo` lo pone el contexto
  `capture_from_chatboo`/`default_from_chatboo` (`:67-90`), ligado al comando `/create-skill`
  de Chatboo (`:71`, `utils/skill_help.py:195-203`). El `code_body` capturado pasa por el
  constraint AST al crearse (ver abajo), pero la **activación sin revisión humana** amplía la
  superficie: cualquier Writer puede cristalizar y activar código ejecutable desde el chat.
- **Qué pasa al importar de un ZIP** (HECHO, `models/ai_skill.py:1129-1218`):
  `import_skills_zip` exige **AI admin** (`ensure_ai_admin`, `:1136`), lee `manifest.json` +
  ficheros de contenido/código del ZIP, y hace `create`/`write` de los skills con
  `active = entry.get('active', True)` (`:1200`) — es decir, **un ZIP puede traer skills ya
  activos**. El `code_body` importado dispara el constraint `_check_code_body_contract`
  (`ai_skill.py:363-433`): valida AST con `validate_relaxaicode_source_ast` (bloqueante,
  `:395-400`), el contrato publicado (`skill_contract_violations`), el candado de filas
  congeladas (`:401-406`) y un smoke-run best-effort. **INFERENCIA**: el ZIP es dato no
  confiable; la única barrera del código es el AST (que, como vimos en §4, no cubre getattr a
  métodos de negocio). **PENDIENTE**: confirmar que `import_agent_skills_zip` aplica el mismo
  constraint (va por `create`/`write` de `ai.skill`, luego sí).

---

## 7. Render HTML de resultados y `untrusted_html_contract`

- **Contrato HTML no confiable** (HECHO, `utils/untrusted_html_contract.py`): el sandbox
  **no** puede inventar `formatted_text` user-facing. La confianza es **solo** por
  `__fmt_type__` ∈ `{server_side_python, author_html, local_json, local_raw}`
  (`:12-17`). `reject_untrusted_formatted_text` (`:20-60`) elimina cualquier `formatted_text`
  del sandbox libre sin `__fmt_type__` de confianza, lo degrada a
  `__untrusted_html_preview__` (recortado a 4000) y fuerza turno del LLM. Se aplica en
  `tools_relaxaicode.py:2287` (antes del render) y `:2635-2638` (tras el render, con
  `after_server_render=True` para no borrar lo que puso el servidor).
- **Render server-side** (HECHO parcial): `relaxaicode_render.maybe_attach_formatted_text`
  (`tools_relaxaicode.py:2466-2503`) construye la tabla HTML a partir de las filas y estampa
  `__fmt_type__='server_side_python'` (el renderer de confianza, comentario `:35-44`). Las
  imágenes base64 se convierten a URLs `/web/image/<model>/<id>/<campo>`
  (`_postprocess_images` `:273-311`) y los binarios que viajan al LLM se sustituyen por
  placeholder (`_sanitize_binary_for_llm` `:124-142`) para no desbordar contexto.
- **¿Se sanea antes del navegador?** INFERENCIA/PENDIENTE: el módulo distingue HTML de
  **confianza** (servidor / skill author_html) de HTML **del LLM libre** (rechazado), pero
  `relaxaicode_render.py` (2607 líneas) **no se leyó entero** (ver cobertura). El HTML de
  `author_html` (skills) y el del servidor se consideran confiables y **no** se observa un
  paso de saneado tipo `bleach`/`html_sanitize` del core en lo leído. El skill author_html lo
  escribe el autor del skill (Writer/admin), de modo que un skill malicioso podría inyectar
  HTML/JS en Chatboo. **PENDIENTE**: revisar en `relaxaicode_render.py` si hay
  `tools.html_sanitize` antes de emitir al cliente, y auditar el JS de Chatboo
  (`static/src/js/`), fuera del alcance de este bloque.

---

## 8. `sudo()`, compatibilidad Odoo 14 / Python 3.7.3 y riesgos

- **`sudo()`** (HECHO): en el **sandbox** está permitido (`validators.py:828-837`
  `_ast_is_env_root` acepta `env.sudo()...`), y el wrapper `GuardedSandboxEnv` lo re-envuelve
  para que `env.sudo()['ai.context']` siga bloqueado (`context_builder.py:93-102`). Eleva
  permisos de **lectura** sobre un cursor READ ONLY. En la **infraestructura** (engine, skills,
  logs) hay `sudo()` justificado: `_api_key_for_inference` (`ai_provider.py:117`),
  `get_failovers` (`ai_execution_engine.py:145`), `ai.log` (`:288,377,426`), apply_* de
  `ai_system_action.py` (`.sudo()` en `ir.ui.view`/`ir.module.module`/`res.users`/`res.groups`),
  `sandbox_helpers.collect_sandbox_helpers` (`:68-70`).
- **Compatibilidad Python 3.7.3 / zoneinfo** — ver §9.
- **Compatibilidad Odoo 14** (HECHO): el código usa patrones válidos en 14 (AST con
  `ast.Str`/`ast.Num` para <3.8, `ast.Constant` para 3.8+, p. ej. `validators.py:1819-1822`,
  `:2057`). `ast.unparse` (`validators.py:290,426,579,1591`) **solo existe en Python 3.9+**:
  en la imagen de Odoo 14 con Python 3.7.3 lanzaría `AttributeError`, pero está envuelto en
  `try/except Exception` que devuelve el código original (p. ej. `:289-293`), de modo que las
  **reparaciones** basadas en `ast.unparse` (`repair_unsafe_sort_keys`, `repair_registry_models`,
  `repair_percent_format_strings`, `_rewrite_dir_calls`) serían **no-ops silenciosos** en 3.7.
  La validación principal (`validate_relaxaicode_source_ast`) no depende de `unparse`, así que
  la seguridad no se degrada; sí se pierden las auto-reparaciones. **PENDIENTE** confirmar la
  versión real de Python de la imagen del cliente (encargo dice 3.7.3; CLAUDE.md del repo solo
  fija Odoo 14).
- **Riesgos destacados** (resumen, detalle en §3-7 y §9):
  1. **getattr a métodos de negocio que abren cursores nuevos** evade el detector de escritura
     y `guarded_getattr` → posible escritura persistente saltándose la caja A READ ONLY
     (§4, pregunta 9). INFERENCIA/riesgo alto, no cubierto por tests.
  2. **`skill.capture.wizard` con `from_chatboo` activa el skill sin revisión** del admin
     (§6); Writer puede crear/activar skills.
  3. **ZIP de skills puede traer `active=True`** (§6); solo el AST protege el `code_body`.
  4. **HTML de confianza (author_html / server) sin saneado observado** → posible XSS vía
     skill malicioso (§7, PENDIENTE).
  5. **Sin límites de tiempo/memoria propios**: depende de `limit_*` del worker (§2).
  6. **Auto-reparaciones AST inertes en Python 3.7** (`ast.unparse`) (§8).
  7. **`zoneinfo` anunciado pero inexistente en 3.7**, sin fallback (§9).

---

## 9. ZoneInfo / `zoneinfo` en Python 3.7.3

- **Qué dice el prompt** (HECHO): `ai/contexts/core/system_prompt.xml:70`
  `<variable name="ZoneInfo" type="type">Pre-loaded zoneinfo.ZoneInfo</variable>` y `:84`
  incluye `zoneinfo` en la lista de módulos importables.
- **Cómo lo "precarga" el sandbox** (HECHO, `context_builder.py:221-224`):
  `try: from zoneinfo import ZoneInfo as _ZoneInfo / except Exception: _ZoneInfo = None`.
  Solo si no es None se añade al contexto (`:438-439` `if _ZoneInfo is not None:
  safe_context['ZoneInfo'] = _ZoneInfo`).
- **En Python 3.7.3** (HECHO): el módulo `zoneinfo` de la stdlib **no existe** (es 3.9+). Por
  tanto `_ZoneInfo = None` y **`ZoneInfo` NO se inyecta** en el sandbox → el código del LLM
  que use `ZoneInfo(...)` recibe **`NameError: name 'ZoneInfo' is not defined`**
  (manejado como error reintentable, `tools_relaxaicode.py:2744-2778`).
- **`import zoneinfo`** (HECHO): aunque `zoneinfo` está en `RELAXAICODE_SAFE_MODULES`
  (`validators.py:94`) y el AST lo acepta, en runtime `guarded_import` hace
  `__import__('zoneinfo')` (`context_builder.py:178-179`) → **`ModuleNotFoundError`** en 3.7,
  devuelto como error de ejecución reintentable.
- **¿Alternativa (backports.zoneinfo / pytz)?** (HECHO): **No hay fallback**. El `except` deja
  `_ZoneInfo = None` sin intentar `backports.zoneinfo` ni `pytz`. `pytz` no está en la lista
  blanca de imports, así que el LLM tampoco puede recurrir a él. Para huso horario el contrato
  ofrece `now`/`today`/`user_tz` ya en huso del usuario (`system_prompt.xml:68-71`,
  `context_builder.py:339-397`), que es la vía soportada.
- **Consecuencia** (INFERENCIA): el prompt induce al LLM a usar `ZoneInfo`/`zoneinfo`; en la
  imagen de Odoo 14 (Python 3.7.3) eso **siempre falla** con NameError/ModuleNotFoundError,
  gastando rondas ReAct hasta que el modelo use `now`/`user_tz`. Es una **incompatibilidad de
  contenido del prompt con el entorno**, no un fallo de seguridad. Coincide con lo apuntado en
  [CONOC] §7.1 (`analisis_pns_ai_mcp_2_conocimiento.md:601-603,731-732`).

### Contraste imports permitidos: prompt vs validador (HECHO)
- **Prompt** (`system_prompt.xml:84`): `datetime, json, operator, math, re, collections,
  itertools, functools, statistics, decimal, csv, copy, uuid, random, calendar, textwrap,
  unicodedata, base64, hashlib, string, io, zoneinfo` + `from urllib.parse import ...`.
- **Validador** `RELAXAICODE_SAFE_MODULES` (`validators.py:85-94`): lo mismo **más** `date`,
  `time` y `platform` (no citados en el prompt), y también `zoneinfo`.
- Diferencias: el validador es **más permisivo** (`time`, `platform`, `date`); el prompt es
  no exhaustivo ("and other safe modules"). Ambos comparten el problema `zoneinfo`. Ninguna
  diferencia abre un vector nuevo (todos de cálculo puro), pero `platform` expone datos del
  SO del contenedor (versión de Python/OS) a la lectura — menor, INFERENCIA.

---

## Resumen del bloque

`relaxaicode` ejecuta **Python del LLM** con `exec()` (no safe_eval) en el **mismo proceso**
de Odoo, sobre la "**caja A**": cursor aislado `SET TRANSACTION READ ONLY` con `commit`
neutralizado y `rollback` final. La contención se apoya en tres capas: (1) validación **AST**
(`validators.py`) que bloquea imports peligrosos, builtins (`open/eval/exec/dir/...`), dunders,
frames, cursor/registry, `class`, `return` a nivel módulo y lambdas no accesoras, y marca las
escrituras; (2) `__builtins__` recortado con `guarded_getattr`/`guarded_import`; (3) cursor
READ ONLY. Las escrituras legítimas van por la **Caja B**. Los tests e2e
(`test_relaxaicode_sandbox_escapes_e2e.py`) confirman que los escapes clásicos (dunders,
`type()`, format-string, getattr dinámico a dunder/write, bypass de API) fallan controlados.

**Hallazgo principal (pregunta 9):** los modelos `ai.system.action` / `ai.trusted.action` /
`ai.safe.operation` **son accesibles** desde el sandbox. `apply_*`/`apply` escriben sobre el
cursor READ ONLY → abortan (contenido). Pero los métodos `resolve_*`/`execute_plan_now`/
`cleanup_*` abren **cursores nuevos no-READ-ONLY** (`registry.cursor()`); aunque la llamada
**literal** se bloquea (están en `side_effect_methods`), llamarlos por **`getattr` dinámico**
evade el detector de escritura (solo cubre create/write/unlink/copy) y `guarded_getattr` →
**posible escritura persistente saltándose la caja A** (INFERENCIA, no cubierto por los tests;
PENDIENTE reproducir). También: `skill.capture.wizard` con `from_chatboo` **activa** el skill
sin revisión del admin; el **ZIP** de skills puede importar `active=True` (solo el AST protege
el code_body); no hay saneado HTML observado para `author_html`/servidor; `zoneinfo`/`ZoneInfo`
se anuncian en el prompt pero **no existen en Python 3.7.3** y no hay fallback; varias
auto-reparaciones AST (`ast.unparse`) son no-ops en 3.7.

**Complemento 6b (crítico):** (a) **un Writer puede escalar privilegios con un skill**: el
`code_body` de un skill se ejecuta sin cursor READ ONLY y **nadie** usa el `requires_write` del
AST en la ruta de skills (`ai_skill.py:395` lo descarta como `_requires_write`); la llamada
`env['ai.system.action'].apply_user_add_group(user.id, <id de base.group_system>)` pasa el
AST, y el propio **smoke-run del constraint al guardar** (`ai_skill.py:407-415`) la ejecuta en
la transacción del guardado → el cambio persiste sin que nadie invoque el skill (HECHO de flujo;
persistencia INFERENCIA; PENDIENTE reproducir). Lo mismo vale para un `.sudo().write()` literal.
(b) **Saneado HTML**: no hay `html_sanitize` ni DOMPurify en ningún punto; `formatted_text`
(`author_html`) se devuelve **tal cual** (`relaxaicode_render.py:2237-2238,2594-2595`). El
renderer de tablas escapa casi todo, pero la celda base64 (`:897`) inserta el valor **sin
escapar** (XSS almacenado posible desde un campo de texto de un registro) y los `href` de
mapa/coordenadas no filtran el esquema (`javascript:`). (c) `relaxaicode_recipe` reescribe el
código **antes** de validar y la validación ve el código final (sin reescrituras posteriores);
los skills no pasan por estas recetas. `ast.unparse`/`ast.get_source_segment` no existen en
3.7 → recetas inertes o excepción.

## Tabla de cobertura

| Archivo | Líneas | Leído entero |
|---|---|---|
| `controllers/tools_relaxaicode.py` | 2837 | Sí |
| `controllers/validators.py` | 2613 | Sí |
| `controllers/context_builder.py` | 552 | Sí |
| `controllers/controller_helpers.py` | (get_readonly_env 184-252) | Parcial (solo caja A) |
| `models/ai_execution_engine.py` | 607 | Sí |
| `utils/skill_runtime.py` | 1059 | Sí |
| `utils/sandbox_helpers.py` | 90 | Sí |
| `utils/skill_live_code.py` | 66 | Sí |
| `utils/skill_files.py` | 71 | Sí |
| `utils/skill_errors.py` | 97 | Sí |
| `utils/untrusted_html_contract.py` | 60 | Sí |
| `utils/relaxaicode_recipe.py` | 542 | Sí (complemento 6b) |
| `utils/relaxaicode_render.py` | 2608 | Sí (complemento 6b, en dos lecturas: 1-1478 y 1478-2608) |
| `utils/skill_dates.py` | 160 | Sí (complemento 6b) |
| `utils/skill_help.py` | 303 | Parcial (create-skill builtin) |
| `utils/skill_code_prefix.py` | 263 | Sí (complemento 6b) |
| `utils/skill_engine_contract.py` | 213 | Sí (complemento 6b) |
| `models/ai_skill.py` (6b) | (355-433 constraint, 498-532 create/write) | Parcial |
| `models/ai_system_action.py` (6b) | (1-60, 117-119, 668-764) | Parcial |
| `controllers/tools_relaxaicode.py` (6b) | (25-55, 1070-1120, 1465-1501, 1660-1794) | Parcial (orden recetas/validación) |
| `pns_base/utils/compat.py` (6b) | (113-123 user_add_group) | Parcial |
| `pns_ai_chatboo/static/src/js/*` (6b) | — | No (solo Grep de `sanitize`/`DOMPurify`/`innerHTML`) |
| `wizard/skill_capture_wizard.py` | 214 | Sí |
| `wizard/skill_import_wizard.py` | 46 | Sí |
| `wizard/agent_skill_import_wizard.py` | 56 | Sí |
| `models/ai_skill.py` | (363-433, 1129-1218) | Parcial (constraint + import ZIP) |
| `models/ai_system_action.py` | (540-764) | Parcial (apply_* + module.update) |
| `models/ai_trusted_action.py` | (90-137) | Parcial (apply/_resolve_method) |
| `models/mcp_safe_operation.py` | (575-1306) | Parcial (resolve_* / cursores) |
| `tests/test_relaxaicode_sandbox_escapes_e2e.py` | 206 | Sí (contraste) |
| `tests/test_relaxaicode_imports.py` | 66 | Sí (contraste) |
| `tests/test_relaxaicode_model_stamp.py` / `_render_locale.py` / `test_friendly_skill_error.py` | — | No (solo contraste de nombre) |

Tras el complemento 6b, los cinco archivos pendientes del bloque están leídos enteros. Queda
fuera del bloque: el JS de Chatboo (`pns_ai_chatboo/static/src/js/`), ruta exacta de inserción
del HTML en el DOM.

## Preguntas abiertas

1. **(Crítica, pregunta 9)** ¿Ejecuta y **persiste** en `odoo-dev 14` un
   `getattr(env['ai.safe.operation'].browse(id), 'resolve_execute')()` (o `cleanup_stuck_state`,
   `execute_plan_now`, `_retry_confirmed_not_executed`) lanzado desde relaxaicode, abriendo un
   cursor nuevo no-READ-ONLY y saltándose la caja A? Si es así, ¿debería la denylist de
   `_detect_requires_write_from_ast` (vía getattr) y/o `guarded_getattr` incluir los
   `side_effect_methods`?
2. ¿Escribe realmente un `code_body` de **skill** (ejecutado por slash, sin caja A READ ONLY,
   `skill_runtime.py:650-652`) que use el mismo patrón getattr→método de negocio? La única
   barrera es el AST al guardar.
3. ¿El HTML `author_html` (skills) y `server_side_python` se **sanean** (`html_sanitize`) antes
   de llegar a Chatboo, o un skill/autor puede inyectar `<script>`? (requiere leer
   `relaxaicode_render.py` y el JS de Chatboo).
4. ¿Cuál es la **versión exacta de Python** de la imagen del cliente? Si es 3.7.3: `zoneinfo`
   nunca funciona y las auto-reparaciones con `ast.unparse` son no-ops. ¿Procede corregir el
   `system_prompt.xml` para no anunciar `ZoneInfo`/`zoneinfo`?
5. ¿Es aceptable que `skill.capture.wizard` con `from_chatboo` **active** el skill sin revisión
   del admin (`wizard/skill_capture_wizard.py:190`), y que un **Writer** pueda crear/activar
   skills (`ir.model.access.csv:20,24`)? ¿Debería forzarse `active=False` y revisión?
6. ¿Deben imponerse límites de **CPU/memoria** propios del módulo, o se confía en
   `limit_time_real`/`limit_time_cpu`/`limit_memory_hard` del worker del VPS? Confirmar que el
   despliegue los fija.
7. ¿Importar un **ZIP** de skills con `active=True` (`ai_skill.py:1200`) es el comportamiento
   deseado, dado que el ZIP es dato no confiable y solo el AST valida el `code_body`?
8. El módulo `platform` está en la whitelist del validador pero no en el prompt
   (`validators.py:92` vs `system_prompt.xml:84`): ¿es intencional exponer datos del SO del
   contenedor al código del LLM?

---

## Complemento 6b

Alcance: `utils/relaxaicode_render.py` (2608 líneas), `utils/relaxaicode_recipe.py` (542),
`utils/skill_engine_contract.py` (213), `utils/skill_dates.py` (160),
`utils/skill_code_prefix.py` (263), leídos enteros. Para el punto 4 se han leído fragmentos de
`validators.py`, `context_builder.py`, `skill_runtime.py`, `agent_engine.py`, `ai_skill.py`,
`ai_system_action.py` y `pns_base/utils/compat.py` (líneas citadas). Código de terceros: solo
análisis, sin propuesta de código.

### 6b.1 Saneado HTML (valores de registros y `author_html`)

**Conclusión:** no existe ningún saneado de tipo `html_sanitize` (core:
`/opt/odoo-src/14.0/odoo/tools/mail.py`, función `html_sanitize`) ni `bleach`/DOMPurify en la
ruta. El módulo confía en dos cosas: (a) escapar con `html.escape` cada valor que el renderer
de tablas pinta y (b) la "marca de confianza" `__fmt_type__`.
- HECHO: Grep de `html_sanitize|sanitize=` en `pns_ai_mcp/**/*.py` solo encuentra campos
  `fields.Html(sanitize=False)` (`ai_log.py:207`, `ai_provider.py:101`,
  `external_server.py:195,282,288,294`, `wizard/context_stats_wizard.py:33`); ninguna llamada a
  `html_sanitize`.
- HECHO: Grep de `DOMPurify|sanitize` en `pns_ai_chatboo/static/src/js/chatboo_*.js` solo
  encuentra `sanitizeWordClone` (exportación a Word, `chatboo_export.js:3055`). El HTML se
  inserta con `innerHTML` (p. ej. `chatboo_formatters.js:553,671,746`,
  `chatboo_component_v2.js:1836,1867,4478`). PENDIENTE: seguir la ruta exacta
  `formatted_text` → DOM en el JS (fuera de este bloque).

**`formatted_text` / `author_html` (skills)** — pasa sin tocar:
- HECHO: `render_result_html` devuelve `result['formatted_text']` tal cual si existe
  (`relaxaicode_render.py:2237-2238`); igual `render_for_direct_return` (`:2594-2595`);
  `maybe_attach_formatted_text` antepone las tarjetas al HTML existente sin procesarlo
  (`:2513-2518`).
- HECHO: el skill obtiene la marca de confianza automáticamente: `formatted_text` +
  `__return_direct__`/`__stop_after_direct__` → `__fmt_type__='author_html'`
  (`skill_runtime.py:664-668`); `_stamp_author_html` (`:748-753`) la pone a cualquier
  presentación con `formatted_text` (`:768,773,873,883`).
- HECHO: el único filtro (`untrusted_html_contract.py:20-60`) se aplica a la tool
  `relaxaicode` (sandbox libre del LLM), no al HTML del skill, que ya llega marcado.
- INFERENCIA: el autor de un skill (un **Writer**, ver §6) puede emitir HTML/JS arbitrario que
  se pinta en el chat de **cualquier usuario** que invoque el skill → XSS almacenado por diseño.

**Renderer de tablas (`server_side_python`)** — puntos donde se construye HTML:

| Punto (relaxaicode_render.py) | Qué inserta | ¿Escapa? |
|---|---|---|
| `_record_form_url` `:564-571` | modelo e id del enlace a ficha | Sí (`model` con `html.escape`, id `%d`) |
| `_name_cell_link_html` `:574-583` | texto del enlace | Sí |
| `_render_map_thumb_cell` `:612-658` | `alt`, `badge`, `title`, `png`/`src`, `href` | Sí (todo con `html.escape`), **pero `href` sin filtro de esquema** (`:649,657`): un `javascript:` pasaría |
| `_render_coords_cell` `:661-711` | texto, `data-copy-text`, `href` | Sí, **`href` sin filtro de esquema** (`:672,692`) |
| `_render_cell` números/fechas `:869-891` | valor formateado | Sí |
| `_render_cell` base64 `:892-897` | `clean` (valor de la celda) dentro de `src="data:image/...;base64,%s"` | **NO**. Basta que un valor de texto mida >64 caracteres y empiece por `iVBORw`, `/9j/`, `R0lGOD` o `UklGR` (`:101`) para que se inserte crudo: una comilla en el valor rompe el atributo. **INFERENCIA (riesgo alto):** un usuario con escritura sobre cualquier campo de texto que acabe en una tabla del chat (nombre de contacto, referencia…) puede plantar XSS almacenado que se ejecuta al verlo otro usuario |
| `_render_cell` imagen por URL `:898-917` | `href`/`src` | Sí; solo acepta `/web/image/`, `http…` o `/…` |
| `_render_cell` texto `:918-921` | valor | Sí |
| `_render_table` `:951-1033` | `caption` | No escapa (`:957`, f-string), pero ningún llamante pasa `caption` (`:1623,1853,1903`) → hoy inerte (HECHO) |
| idem | `section_title` | No escapa en `:968`, pero el llamante lo pasa ya escapado (`:1906`) (HECHO) |
| idem | cabeceras (claves) `:977`, `_row_class`/`_row_color` `:986-988`, clases `:1002`, `data-tip` `:1015` | Sí |
| idem | `_color_<col>` / `_style_<col>` `:1004-1011` | Escapa comillas (no hay ruptura de atributo), pero el CSS es libre → INFERENCIA: inyección CSS (superposiciones, `url(...)`) posible desde el código |
| `_table_block_open` `:1191-1213` | JSON del dataset en atributo | Sí |
| `_map_banner_card_html` `:1258-1309` | `href`, `label` | Sí; el `href` viene de `map_url`/`pins_url` que exige `http…` o `/…` (`:1413-1419`) o de la celda `__map_thumb__` (sin filtro de esquema, `:1380`) |
| `_title_html` `:1442-1450`, `_block_title_html` `:1463-1481` | título | No escapan, pero los llamantes pasan texto ya escapado (`:1616`, `:1875-1877`) (HECHO) |
| `_markdownish_to_html` `:1484-1543` | pie (`footer`) | Sí (escapa y luego aplica `**`) |
| `_result_notices_html` `:1546-1581` | avisos | Sí |
| `grouped_dashboard_html` `:1728-1865` | id, título, tarjetas | Sí (`:1757,1769,1813,1816`) |
| `_link_banner_card_html` / `_safe_card_href` `:2310-2388` | tarjetas `link` | Sí, y **sí** filtra esquema (solo http/https o ruta relativa, rechaza `//`, comillas y `<>`) |
| `render_svg_cards_html` `:2471-2505` | JSON de la tarjeta | Sí |
| `wrap_bare_images_clickable` `:2561-2587` | `href` a partir del `src` | Sí; `_image_link_href` solo http o `/` (`:2550-2558`) |

Resumen 6b.1: los valores de registros **se escapan** salvo en la celda base64 (`:897`); los
`href` de celdas de mapa/coordenadas no filtran el esquema (dependen del código del LLM/skill,
no de valores de registros directamente); el `formatted_text` de skills (`author_html`) **no se
sanea en ningún sitio** (HECHO en Python; PENDIENTE en el JS).

### 6b.2 `relaxaicode_recipe`: reescrituras previas a validar/ejecutar

Funciones (HECHO, todas en `relaxaicode_recipe.py`):
1. `module_level_data_literal_error` (`:112-135`): rechaza asignaciones de nivel módulo con
   colecciones literales de más de 8 elementos (`_MAX_MODULE_LITERAL_ELTS`, `:11`).
2. `strip_module_level_data_literals` (`:138-180`): elimina esas asignaciones y recupera su
   valor con `_try_eval_data_node` (`:22-109`): `ast.literal_eval` y un plegado limitado de
   `+ - * / // %`, signo y `round()` sobre números; nada ejecutable. Regenera el código con
   `ast.unparse` (`:177`).
3. `bind_stripped_names_from_prior` (`:183-203`): antepone `nombre = json.loads(<repr del JSON
   recuperado>)` o `nombre = (previous_result.get('data') ...) or raw_data or []`. Solo
   identificadores válidos (`:193`); el JSON va como literal `repr` → no inyecta código.
4. `strip_self_recursive_shadow_defs` (`:324-356`) y `self_recursive_def_error` (`:359-374`):
   quitan/rechazan `def f(...): return f(...)` que sombrean una `def` real.
5. `ensure_module_result_call` (`:377-457`): si no hay `result =` a nivel módulo, añade
   `result = <última def con docstring o última def>(args)`; los argumentos son nombres del
   propio módulo, `str(today)` para fechas obligatorias simples o la expresión
   `previous_result/raw_data`. No inventa rangos de fechas (`:234-248`).
6. `ensure_date_param_coercion` (`:479-531`): inserta en la `def` raíz, por texto y con la
   sangría de la primera sentencia, un bloque `if isinstance(x, str) ...: x =
   date.fromisoformat(x[:10])` por cada parámetro de fecha. Usa `ast.get_source_segment`
   (`:507`).
7. `inject_map_pins_origin_from_distance` (`:534-541`): no-op.

¿Puede alguna introducir algo que el validador no vea?
- HECHO: en la tool, todas se aplican **antes** de `validate_relaxaicode_source_ast`:
  literales en `_strip_module_literals_or_reject` (`tools_relaxaicode.py:1465-1501`, llamada en
  `:1609,1648`), recetas 4-6 en `:1680-1706`, y además en `_attempt_syntax_repair`
  (`:1082-1119`), cuyo resultado se **revalida** (`:1788`). Tras la validación (`:1767/1790`) no
  hay más asignaciones a `code` (Grep de `code = ` / `code, ` en el archivo). El validador ve
  el código final.
- INFERENCIA: lo que insertan las recetas son identificadores tomados del propio AST,
  literales `repr` de JSON y llamadas a `json.loads`, `date.fromisoformat`, `str(today)`: nada
  que el validador prohíba ni que amplíe capacidades. No se aprecia vector de inyección.
- HECHO: los **skills no pasan por estas recetas**: `bootstrap_skill_code_body` compila y
  ejecuta el `code_body` tal cual (`skill_runtime.py:656-659`), sin validar el AST en
  ejecución (solo al guardar, ver 6b.4).
- HECHO (compatibilidad Python): `ast.unparse` (`:177,351`) es de Python 3.9+; en 3.7/3.8 cae
  en el `except` y devuelve el código original sin cambios → en
  `_strip_module_literals_or_reject` no hay nombres eliminados y el literal grande se
  **rechaza** siempre (`tools_relaxaicode.py:1484-1501`); `strip_self_recursive_shadow_defs` es
  no-op y `self_recursive_def_error` rechaza. `ast.get_source_segment` (`:507`) es de 3.8+: en
  3.7 lanza `AttributeError` **no capturado** dentro de la función; en `_attempt_syntax_repair`
  hay `try` (`tools_relaxaicode.py:1101`), pero en `:1706` no hay `try` local (PENDIENTE:
  comprobar si un manejador externo lo captura; si no, una `def` con parámetro de fecha haría
  fallar la tool en Python 3.7).

### 6b.3 Contrato de skills y resto de archivos

**`skill_engine_contract.py`** (HECHO):
- Claves de front-matter admitidas (`SKILL_FRONT_MATTER_KEYS`, `:22-41`) y capacidades
  `requires:` admitidas (`SKILL_ENGINE_CAPABILITIES`, `:44-60`).
- Los `__dunder__` de resultado **no** son una lista blanca escrita: son todos los
  `'__x__'` entrecomillados que aparecen en `utils/*.py` y `controllers/*.py`
  (`published_result_dunders`, `:133-142`), excluyendo los archivos de `_SKIP_ENGINE_FILES`
  (`:96-101`) y nombres del intérprete (`_NOT_RESULT_PROTOCOL`, `:64-93`). Se calcula al
  importar (`SKILL_RESULT_DUNDERS`, `:145`) y en cada llamada (`:178,189`).
- `skill_contract_violations` (`:198-212`) devuelve claves/capacidades/dunders no publicados.
- INFERENCIA: es un contrato de **interfaz**, no de seguridad: no mira llamadas a métodos ni
  escrituras. Como `__fmt_type__`, `__return_direct__`, etc. están citados en el motor, un
  skill puede emitirlos libremente.

**`skill_dates.py`** (HECHO): resolución determinista de días (`hoy`, `ayer`, `mañana`, ISO,
días de la semana con `este/próximo/next`, `:108-149`) y detección de ayuda (`is_help_like`,
`:64-87`; `skill_args_are_help`, `:90-105`). Funciones puras, regex con `re.escape`; sin
riesgo apreciable.

**`skill_code_prefix.py`** (HECHO): prefijos del código de catálogo (`custom_`) y del comando
slash (`custom-`) leídos de `ir.config_parameter` con `sudo()` (`:153-166`, lectura de
configuración, justificado); normalización, unicidad (`uniquify_catalog_code`, `:140-150`),
comandos reservados (`reserved_slash_commands`, `:169-189`) y retirada de "gemelos" sin
prefijo (`leftover_twin_action` devuelve `'unlink'`, `:249-262`). Sin implicaciones de
seguridad.

**`relaxaicode_render.py`, resto** (HECHO): detección de tablas (`is_tabulable`, `:158-188`),
locale desde `res.lang` (`render_context_from_env`, `:247-314`), formateo numérico/fecha,
selección de la columna enlazada a la ficha (`_select_name_link_keys`, `:476-511`), tintado por
terciles/cebra (`:1926-2227`), dashboard y tablas agrupadas, tarjetas SVG/link. Python puro;
la única consulta ORM es la de `res.lang` (`:261-267`).

### 6b.4 Pregunta 4: ¿puede el `code_body` de un skill de un Writer llamar a `apply_user_add_group` y persistir?

**Respuesta: sí, salvo prueba en contra; y además se ejecuta ya al guardar el skill.**
(HECHO de flujo estático; persistencia INFERENCIA fuerte; PENDIENTE reproducir en
`odoo-dev 14`.)

Cadena:
1. **El Writer puede crear el skill con `code_body`**: ACL `1,1,1,1` para `group_ai_writer`
   (§6, `ir.model.access.csv:20`); `create` no revisa el código (`ai_skill.py:500-512`);
   `write` solo impide a no-admins tocar `is_system` y `owner_id` (`:514-526`). (HECHO)
2. **El AST no lo bloquea**:
   - `env['ai.system.action']` no es catálogo prohibido (`validators.py:146-149`; §4). (HECHO)
   - `apply_user_add_group` no está en `side_effect_methods` (`validators.py:928-944`) ni en
     `RELAXAICODE_EXTERNAL_API_METHODS` (`:170-176`) ni en `DANGEROUS_ATTR_NAMES`
     (`:113-131`). (HECHO)
   - **Aunque lo estuviera, daría igual en skills**: `validate_relaxaicode_source_ast` devuelve
     `(True, None, requires_write)` — marcar escritura no invalida (`validators.py:1992-2004`) —
     y el constraint **descarta** ese valor (`ok, err, _requires_write = ...`,
     `ai_skill.py:395`). El único consumidor de `requires_write` es la tool relaxaicode
     (`tools_relaxaicode.py:1767,1907`). Por tanto ni siquiera un `.sudo().write(...)` literal
     se bloquea en un skill. (HECHO)
3. **El contrato publicado no lo bloquea**: `skill_contract_violations` solo mira front-matter,
   `requires` y dunders (`skill_engine_contract.py:198-212`). (HECHO)
4. **El smoke-run lo ejecuta al guardar**: con el registry listo,
   `_check_code_body_contract` llama a `bootstrap_skill_code_body(self.env, code,
   arguments='')` (`ai_skill.py:407-415`) con el `env` del Writer, en la **misma transacción**
   del `create`/`write`, sin savepoint ni cursor READ ONLY. Solo lanza `ValidationError` si
   `result` no es dict o trae dunders no publicados (`:420-433`). Si el código asigna
   `result = {...}`, el guardado termina bien y la transacción se confirma. (HECHO de flujo;
   INFERENCIA: el cambio de grupo queda confirmado con el guardado, aunque el skill nunca se
   active ni se invoque.)
5. **En ejecución tampoco hay barrera**: `bootstrap_skill_code_body` ejecuta con `exec` sobre
   `build_safe_context(_Ctrl(env), 'read')`, donde `_get_env_for_operation` devuelve el mismo
   `env` (`skill_runtime.py:622-627,650-659`); por slash ese `env` es el del motor de chat
   (`agent_engine.py:1359-1363`, `AgentEngine(self.env)` en `ai_agent.py:385`). Grep de
   `READ ONLY` en el módulo: solo en la ruta de la caja A (`controller_helpers.py:193-251`,
   `tools_relaxaicode.py`), nunca en skills. `GuardedSandboxEnv` solo bloquea los catálogos
   (`context_builder.py:56-108`) y `guarded_getattr` solo actúa en `getattr()` dinámico
   (`:111-143`), no en la llamada por atributo `obj.metodo()`. (HECHO)
6. **El método escribe con privilegios de superusuario**: `ai.system.action` es
   `AbstractModel` (`ai_system_action.py:117-118`, sin control de ACL de modelo para llamar a
   sus métodos), `apply_user_add_group` es `@api.model` (`:715-733`) y resuelve usuario y grupo
   con `sudo()` (`_resolve_user` `:672-680`, `_resolve_group` `:682-696`); `user_add_group`
   hace `user.write({groups_id: [(4, gid)]})` sobre ese registro `sudo`
   (`pns_base/utils/compat.py:113-116`). No comprueba que quien llama sea admin. (HECHO)

Consecuencia (INFERENCIA, riesgo crítico): un AI Writer puede guardar un skill cuyo
`code_body` sea, en esencia, "añadir a `user.id` el grupo `base.group_system` y devolver un
dict", y obtener **Ajustes de Odoo** (y por extensión `group_ai_admin` u otros) en el mismo
guardado. Lo mismo con `apply_user_remove_group` (quitar grupos a un admin) o
`apply_view_*`/`apply_field_set_required` (`ai_system_action.py:347-500`), que también usan
`sudo()`. Si el skill se activa, cualquier usuario que lo invoque ejecuta el código con **sus**
permisos (`agent_engine.py:1359`), lo que además permite a un Writer actuar con los derechos de
un administrador que lo invoque. Contraste con §4: en la tool relaxaicode el mismo `apply_*`
abortaría por el cursor READ ONLY; en skills esa protección no existe.

Matiz (INFERENCIA): `apply_module_update` (`ai_system_action.py:630-668`) llama a
`button_immediate_*`, que hace `cr.commit()` en el core
(`/opt/odoo-src/14.0/odoo/addons/base/models/ir_module.py:550-573`); en un skill también se
ejecutaría (el `side_effect_methods` que la incluye no se aplica a skills).

PENDIENTE (prueba en `odoo-dev 14`, sin cargar datos de producción): con un usuario solo
Writer, crear un skill con `code_body` que llame a `apply_user_add_group(user.id, <id de
base.group_system>)` y asigne `result = {'data': []}`; comprobar tras guardar si el usuario
tiene `base.group_system`.

### 6b.5 Preguntas abiertas nuevas

9. **(Crítica)** Confirmar en `odoo-dev 14` la escalada de 6b.4. Si se confirma: ¿se acepta que
   un Writer pueda guardar `code_body` ejecutable, o debe limitarse a `group_ai_admin`? ¿Debe
   el smoke-run del constraint ejecutarse sin cursor READ ONLY?
10. **(Alta)** XSS almacenado por la celda base64 (`relaxaicode_render.py:897`) y HTML libre de
    skills (`author_html`): ¿se acepta sin saneado? Confirmar en el JS de Chatboo cómo se
    inserta `formatted_text`.
11. Python de la imagen: si es 3.7, `ensure_date_param_coercion` usa
    `ast.get_source_segment` (3.8+) sin `try` local en `tools_relaxaicode.py:1706`: ¿hace
    fallar la tool con `def` que tienen parámetros de fecha?
