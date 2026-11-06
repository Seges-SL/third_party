# Propuesta de las entregas E4′.a y E4′.b (parches 30 a 34)

- **Rama:** `14.0-pns-ai-3879` · contexto `odoo-dev 14 lab_pns_ai_3879`, BD `lab_pns_ai_3879_14`
- **Fecha:** 04/11/2026 · **revisión:** 05/11/2026
- **HEAD de partida:** `ca707a9` («[DOC] E4′.0: hoja de Medios y Bajos sobre 3.1.879…»), copia de trabajo
  limpia. El código es el de `87bbd70` (`ca707a9` solo cambia documentación).
- **Origen:** [hoja de E4′](e4_hoja_3879.md), fichas 1 (M11), 2 (M12), 3 (PNS-97), 6 (PNS-36), 8 (PNS-29,
  resto 3) y 30 (el chat afirma cambios que no hizo), con las decisiones de Sergio del 04/11/2026 (primera
  y segunda ronda), que no se reabren; [plan sobre 3.1.879](plan_correccion_pns_ai_3879.md), apartado
  E4′; [registro de parches](parches_pns_ai.md) (N11, marcadores, formato de las entradas).
- **Estado:** propuesta aprobada por Sergio (05/11/2026) tras dos revisiones de odoo-reviewer; E4′.a y
  E4′.b implementadas (ver «Resultado de E4′.a» y «Resultado de E4′.b»); pendiente, E4′.h.
- **Alcance de las comprobaciones:** código de los tres módulos, `vertical-instaladores` y el repo del
  laboratorio; core de Odoo 14 de referencia (`/opt/odoo-src/14.0`); en el laboratorio, un script de
  `odoo-dev 14 shell` de solo lectura con `env.cr.rollback()` al final (sin motor, lienzo, skills,
  `relaxaicode` ni `log_*`; sin RPC contra el servidor web y sin tests). **[E]** = comprobado en
  ejecución; **[L]** = por lectura.

Rutas abreviadas: `engine.py` = `pns_ai_mcp/models/ai_execution_engine.py`; `trusted.py` =
`pns_ai_mcp/models/ai_trusted_action.py`; `provider.py` = `pns_ai_mcp/models/ai_provider.py`;
`usage_wizard.py` = `pns_ai_mcp/wizard/ai_provider_usage_wizard.py`; `canvas.py` =
`pns_ai_chatboo/models/chatboo_canvas.py`; `async.py` = `pns_ai_chatboo/models/chatboo_async_request.py`;
`session.py` = `pns_ai_chatboo/models/chatboo_session.py`.

## Hechos de base

- **Python 3.7.3** en la imagen del laboratorio [E]. Nada de lo propuesto usa sintaxis posterior.
- **RPC a un `AbstractModel`:** `/web/dataset/call_kw` solo pasa `check_method_name` y llama a
  `call_kw(request.env[model], …)` (`/opt/odoo-src/14.0/odoo/addons/web/controllers/main.py:1360-1362`);
  XML-RPC igual (`odoo/service/model.py:171-174`). Ninguno comprueba la ACL del modelo [L]. Los seis
  `log_*` y `chat_completion` no tienen decorador (`_api` = `None` [E]), así que van por
  `_call_kw_multi`, que hace `browse(ids)` y llama al método (`odoo/api.py:386-392`) [L]; `ai.execution.engine`
  es `AbstractModel` [E].
- **uid 1 implica `su`** en Odoo 14 (`odoo/api.py:450-451`) [L]; `Environment(cr, 1, {})` da `su=True` e
  `is_system()=True` [E]. `env.is_system()` = `su` o `base.group_system` (`odoo/api.py:538-541`) [L].
- **`_create_log_entry` no escribe con un `TestCursor`** (`pns_ai_mcp/models/ai_log.py:715-719`): con
  `--test-enable` y el cursor del entorno de tipo `TestCursor`, devuelve `None` [L]. En un `HttpCase` el
  registro está en modo test y las peticiones HTTP usan un `TestCursor`: **por RPC en un `HttpCase` no
  se escribe ninguna fila de `ai.log`, con o sin parche**. Fuera de modo test (`TransactionCase`), abre
  `registry.cursor()` y confirma (`:722`). Esto cambia el diseño del test del parche 30 que daba la hoja
  (ver «Ajustes»).
- **Usuarios del laboratorio** [E]: `base.user_admin` (id 2, interno, Ajustes y AI Administrator),
  `base.user_demo` (id 6, interno, sin Ajustes ni AI Administrator), `base.public_user` (id 4, `share`,
  archivado).

## Parche 30 (M11): los `log_*` públicos solo escriben a nombre del usuario actual e interno

### 1. Comprobaciones previas (paso 0)

**Llamadores de los seis envoltorios** (Grep en los tres módulos, `static/`, vistas, datos,
`vertical-instaladores` y el repo del laboratorio) [L]:

| Llamador | Método | `user_id` | Entorno |
|---|---|---|---|
| `engine.py:42` (`_LoggedProviderDriver.chat_completion`) | `log_provider_inference` | no lo pasa | El del motor; solo lo crea `chat_completion` (`engine.py:891`), que con el parche 31 corre en `su` |
| `engine.py:698` (`log_llm_inference`, modo `pair`) | `log_provider_inference` | reenvía el recibido | El mismo |
| `engine.py:773` y `:815` (`log_provider_inference`) | `log_provider_llm_request` / `_response` | reenvía el recibido | El mismo |
| `engine.py:887` (`chat_completion`) | `log_provider_failover` | no lo pasa | El de `chat_completion` (`su` con el 31) |
| `utils/agent_engine.py:249` | `log_role_without_provider` | no lo pasa | `env['ai.execution.engine']` del llamador |
| `utils/agent_engine.py:274` | `log_provider_failover` | no lo pasa | El mismo |
| `utils/agent_engine.py:1047` | `log_provider_failover` | `self._turn_uid` | `self.env` del motor |
| `utils/engine_tool_loop.py:491` y `:669` | `log_provider_llm_request` / `_response` | `self._turn_uid` | `self.env` del motor |
| `utils/inference_audit.py:100` (`flush`) | `log_llm_inference` | `self.user_id` del audit, o `env.user.id` | El `env` del propio audit |
| `wizard/openapi_spec_generate_wizard.py:185` | `log_llm_inference` | `self.env.uid` | El del asistente |
| `pns_ai_chatboo/models/chatboo_session.py:1300` (`_log_design_step`) | `log_llm_inference` | no lo pasa | `self.env` de la sesión |

- `self._turn_uid` es `env.uid` del entorno con el que se crea el motor (`agent_engine.py:552`) o
  `self.env.uid` al empezar el turno (`:571`); `self.env` solo cambia de **contexto** (`:546`, `:617`,
  `:899`, `:905`, `:1231`, `:1357`; `engine_presentation.py:205`, `engine_tool_run.py:205`), nunca de
  usuario. `engine_tool_run.py:18` es `DummyController`, que no llama a los `log_*` [L].
- **`inference_audit`:** todos sus usos pasan `user_id=self.env.uid` o `env.uid` con el mismo `env`
  (`external_server.py:811-815`, `ai_skill.py:1145-1149`, `:1213-1217`, `:1292-1296`,
  `spoken_fields.py:237-241`, `openapi_spec_generate_wizard.py:157-162`) o no lo pasan
  (`chatboo_session.py:1252`) [L].
- **JS y XML:** ningún archivo de `static/`, vistas ni datos nombra los seis métodos [L]. Solo los nombran la
  lista del parche 15 (`controllers/validators_base.py:268-273`) y su test
  (`pns_ai_chatboo/tests/test_seges_chatboo_export.py:41-43`).
- **Rutas `auth='none'`/`public`:** solo las de `/mcp` (`controllers/main.py:235-750`), que autentican con
  la clave MCP antes de crear el entorno; las claves solo existen para `share=False`
  (`models/mcp_user.py:384`, hoja, ficha 1) [L]. Ninguna ruta pública llega al motor con el usuario público.
- **Hilos de Chatboo:** corren con el uid de la petición (`chatboo_job.py:187`, `:207`) [L].
- **Vector real por RPC** [L]: `log_role_without_provider`, `log_provider_llm_request`,
  `log_provider_llm_response`, `log_llm_inference` (con `provider=False`) y `log_provider_inference` escriben
  con argumentos JSON. **`log_provider_failover` no:** necesita registros (`failed_provider.name`,
  `engine.py:453-455`, fuera del `try`), y por RPC solo llegan enteros o `False` → `AttributeError` antes de
  escribir. Se incluye igual en el parche por coherencia (su llamador interno sí pasa registros).
- **RPC a `AbstractModel`:** ver «Hechos de base» ([E] `_abstract=True`, `_api=None`).

**Firmas de Odoo 14 que se sobrescriben:** ninguna (métodos del fabricante; el helper es nuevo).

### 2. Cambio propuesto (esbozo, líneas de HEAD)

```diff
--- pns_ai_mcp/models/ai_execution_engine.py
@@ :9
+# Seges: parche 30 (M11, seguridad). Ver docs/pendiente/parches_pns_ai.md
-from odoo.exceptions import RedirectWarning, UserError
+from odoo.exceptions import AccessError, RedirectWarning, UserError
@@ tras :157 (fin de _bind_log_identity)
+    # Seges: parche 30 (M11, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    def _check_log_user(self, user_id=None):
+        """The public log_* write AI History rows on their own cursor. Outside
+        the system, only an internal user, and only for himself."""
+        if self.env.su:
+            return
+        if not self.env.user.has_group('base.group_user'):
+            raise AccessError(_('Only internal users can write AI History rows.'))
+        if user_id and user_id != self.env.uid:
+            raise AccessError(_(
+                'Only the system can write AI History rows for another user.'))
@@ :411 (log_role_without_provider), :449 (log_provider_failover), :553 (log_provider_llm_request),
@@ :611 (log_provider_llm_response), :691 (log_llm_inference): antes de «if 'ai.log' not in self.env:»
+        # Seges: parche 30 (M11, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        self._check_log_user(user_id)
@@ :767 (log_provider_inference): antes de «n_msgs = len(messages or [])»
+        # Seges: parche 30 (M11, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        self._check_log_user(user_id)
```

- **Por qué antes de `if 'ai.log' not in self.env`:** así el rechazo no depende de que `ai.log` exista y
  ocurre antes de `_resolve_log_threading` (que toca la petición y el contador del turno).
- **`user_id` falso** (`None`, `False`, `0`) se trata como «no viene», igual que hace el fabricante
  (`user_id or self.env.user.id`). Un `user_id` que no sea exactamente `self.env.uid` (también `"2"` por
  JSON) se rechaza.
- **Mensajes nuevos, en inglés y sin traducir (D-6):** «Only internal users can write AI History rows.» y
  «Only the system can write AI History rows for another user.».
- **Marcadores:** 8 (import, con línea propia; helper y seis llamadas). El import de `AccessError` lo usa
  también el parche 31, que va en el mismo commit.

### 3. Qué se degrada

- Ningún interno puede crear filas del Historial IA a nombre de otro por RPC ni desde Python fuera de
  `su`; un usuario externo, ninguna.
- Sigue abierto, **aceptado** (hoja, ficha 1): un interno crea filas a su propio nombre (tokens y coste
  inventados) por RPC. Sin `provider_id` no altera el tope; en LIYBEN no hay tope (D12).
- Un código futuro que llame a un `log_*` con el `user_id` de otro sin `su` dará `AccessError` (los `log_*`
  internos llaman dentro de `try`, salvo `log_provider_inference` desde el driver, que lo propagaría).
  Hoy no hay ninguno (tabla del paso 0).

### 4. Cómo comprobar si el fabricante ya lo ha corregido

```sh
grep -n "def log_\|def _log_\|user_id != self.env.uid\|user_id or self.env.user.id" pns_ai_mcp/models/ai_execution_engine.py
```

Corregido si los `log_*` pasan a privados o si comprueban el usuario antes de escribir (ya no aparece
`user_id or self.env.user.id` sin comprobación previa).

### 5. Tests

Archivo nuevo `pns_ai_mcp/tests/test_seges_e4p.py` (registrado en `tests/__init__.py` con su marcador). El
arnés RPC se copia de `test_seges_rpc_access.py` (`_rpc` y la comprobación del error, `:120-145`) en una
base propia del archivo: **no se importa `TestSegesRpcAccess`**, porque Odoo ejecutaría sus tests otra vez.

- **`TestSegesE4pRpc(HttpCase)`**, interno y portal de prueba con contraseña (como `:81-91`):
  - `test_log_foreign_user_refused`: para los dos usuarios y los seis métodos, con `user_id` = admin
    (`log_llm_inference`: `[[], False, {'total_tokens': 1}]`, `{'endpoint': 'seges_e4p_m11', 'user_id':
    self.env.ref('base.user_admin').id}`, sin fijar el id 2;
    los demás con argumentos JSON equivalentes) → `odoo.exceptions.AccessError`. Con el parche
    neutralizado, los cinco que escriben responden sin error y `log_provider_failover` da
    `AttributeError` (no es explotable por RPC: ver paso 0).
  - `test_log_portal_refused`: el portal sin `user_id` → `AccessError`.
  - `test_log_own_rpc_allowed` (control de lo aceptado): el interno sin `user_id` → sin `error`.
  - **No se cuentan filas aquí:** en un `HttpCase` `_create_log_entry` no escribe nunca (hechos de base).
- **`TestSegesE4pLogRows(TransactionCase)`**, sin `enter_test_mode` (como
  `test_seges_chatboo_export.py:67-84`), con usuarios **ya guardados en la BD** (uno creado en la transacción
  del test no existe para el cursor propio y el `INSERT` fallaría por la clave ajena, escondiendo el
  defecto):
  - `test_foreign_user_leaves_no_row`: `env['ai.execution.engine'].with_user(base.user_admin)`
    (`with_user` quita `su`) → `log_llm_inference(False, {'total_tokens': 1}, endpoint=E, user_id=SUPERUSER_ID)`
    → `AccessError`; 0 filas con `endpoint = E`.
  - `test_external_user_leaves_no_row`: `with_user(base.public_user)` sin `user_id` → `AccessError`; 0 filas.
  - `test_own_row_written` (control): `with_user(base.user_admin)` sin `user_id` → 1 fila con `user_id` =
    `self.env.ref('base.user_admin').id`.
  - **Conteo:** `with self.env.registry.cursor() as cr: cr.execute('SELECT count(*) FROM ai_log WHERE endpoint = %s', (E,))`.
    `E` = `'seges_e4p_m11'` (fijo, propio de este test).
  - **Limpieza:** `_purge` en `setUp` (restos de una ejecución interrumpida) y en `addCleanup`: cursor nuevo,
    `api.Environment(cr, SUPERUSER_ID, {})['ai.log'].search([('endpoint', '=', E)]).unlink()` y
    `cr.commit()` con `# pylint: disable=invalid-commit`, como `test_seges_chatboo_export.py:79-84`. `ai.log`
    no sobrescribe `unlink` ni lo referencia ningún modelo [L]. Con el parche neutralizado, la fila del
    negativo queda confirmada y la borra esa misma limpieza.

### 6. Neutralización prevista

| Ejecución | Qué se retira | Deben fallar |
|---|---|---|
| N30u | La comparación de `user_id` en `_check_log_user` | `test_log_foreign_user_refused` (el interno), `test_foreign_user_leaves_no_row` (`1 != 0`) |
| N30i | El criterio «interno» | `test_log_portal_refused`, `test_external_user_leaves_no_row` |

Pasan en ambas: `test_log_own_rpc_allowed` y `test_own_row_written`. En N30i, `test_log_foreign_user_refused`
pasa también con el portal: su `user_id` (admin) no es el suyo y lo sigue rechazando la comparación de
`user_id`.

## Parche 31 (M12): `chat_completion` solo en `su`

### 1. Comprobaciones previas (paso 0)

- **Llamadores** [L]: solo `pns_ai_chatboo/models/chatboo_async_request.py:918`, ya con `sudo()`; el
  docstring del motor (`engine.py:103`) lo cita como punto de entrada. Ningún JS, vista, dato, test del
  fabricante, `vertical-instaladores` ni repo del laboratorio. Lo nombran la lista del parche 15
  (`validators_base.py:267`) y `test_seges_chatboo_export.py:41`.
- **El driver con registro solo lo crea `chat_completion`** (`_driver_for_provider` solo se llama en
  `engine.py:891`) [L]: con el parche, `_LoggedProviderDriver` y el `log_provider_failover` de `:887`
  corren en `su` y el parche 30 no les afecta.
- **RPC:** ver «Hechos de base».
- **Firmas de Odoo 14:** ninguna.

### 2. Cambio propuesto (esbozo)

```diff
--- pns_ai_mcp/models/ai_execution_engine.py
@@ :870 (primera línea del cuerpo de chat_completion, tras el docstring)
+        # Seges: parche 31 (M12, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        if not self.env.su:
+            raise AccessError(_('Only the system can call chat_completion.'))
         agent_code = self.env['ai.agent'].resolve_inference_agent_code(agent_code)
```

- Mensaje nuevo, sin traducir: «Only the system can call chat_completion.».
- El nombre no cambia (decisión 1 de la segunda ronda). **Marcadores:** 1.

### 3. Qué se degrada

Nadie usa por RPC ni desde Python sin `sudo()` la inferencia directa con la clave de la empresa. Un módulo
de terceros que llame a `chat_completion` sin `sudo()` tendrá que añadirlo (hoy no hay ninguno).

### 4. Cómo comprobar si el fabricante ya lo ha corregido

```sh
grep -n "def chat_completion\|def _chat_completion\|self.env.su" pns_ai_mcp/models/ai_execution_engine.py
```

Corregido si `chat_completion` pasa a privado o exige `su` (o un grupo) antes de resolver el proveedor.

### 5. Tests (`test_seges_e4p.py`)

- `TestSegesE4pRpc.test_chat_completion_rpc_refused`: `_driver_for_provider` y `get_providers_for_agent`
  simulados con `patch.object(type(self.env['ai.execution.engine']), …)` (el servidor del `HttpCase` corre en el
  mismo proceso); un proveedor creado en `sudo` en el test. RPC `chat_completion` con
  `[[], 'pns_ai_mcp', [{'role': 'user', 'content': 'x'}]]` como interno y portal → `AccessError`; el driver
  simulado, sin llamar. **Agente:** `pns_ai_mcp` (`data/ai_agent_data.xml:8-10`, en el manifest, `__manifest__.py:125`; los
  tests corren en una BD nueva); el
  agente `chat` no existe en el laboratorio y `resolve_inference_agent_code` daría `UserError`
  (`models/ai_agent_consumer.py:57-61`) antes de llegar al driver, con lo que la neutralización no
  discriminaría. Con el parche neutralizado el interno recibe la respuesta simulada; el portal ya
  falla sin el parche (no lee `ai.agent`), así que solo discrimina el interno.
- `TestSegesE4pChatCompletion(TransactionCase)`:
  - `test_direct_call_refused`: desde Python, `with_user(<interno de prueba>)` → `AccessError`, driver sin llamar.
  - `test_sudo_call_works` (control): `sudo().chat_completion('pns_ai_mcp', […])` devuelve la respuesta
    simulada.
  - No se escriben filas: el driver simulado no es el `_LoggedProviderDriver`.

### 6. Neutralización prevista

| Ejecución | Qué se retira | Deben fallar |
|---|---|---|
| N31 | La comprobación de `su` | `test_chat_completion_rpc_refused` (el interno), `test_direct_call_refused` |

Pasa: `test_sudo_call_works`.

## Parche 32 (PNS-97): `create`, `write` y `unlink` de `ai.trusted.action` exigen `base.group_system` fuera de `su`

### 1. Comprobaciones previas (paso 0)

- **Quién escribe el modelo** (Grep de `ai.trusted.action`, `ai_trusted_action` y
  `model_ai_trusted_action` en `.py`, `.xml`, `.js` y `.csv` de los tres módulos, `vertical-instaladores` y el
  repo del laboratorio) [L]: solo `data/trusted_actions_system.xml` (9 registros, `:7-95`). El resto son
  lecturas (`_get` en `controllers/safe_plan.py:236`, `:395`, `:681`, `:863`), el bloqueo del sandbox
  (`validators_base.py:148-152`, `:548`; `utils/error_ux.py`), el prompt (`system_prompt.xml:25`) y la ACL
  (`security/ir.model.access.csv:4` y `:74`). Ningún JS, vista ni menú. `hooks.py` no carga este archivo
  (`:63-66`: solo `url_whitelist_data.xml` e `instance_defaults_data.xml`).
- **Laboratorio** [E]: 9 filas en `ai_trusted_action` (las 9 activas) y 9 en `ir_model_data`, todas del
  módulo `pns_ai_mcp` y con `noupdate` falso: en cada `-u` se vuelven a escribir.
- **La carga de datos corre en `su`** [L] (`odoo/` = `/opt/odoo-src/14.0/odoo/odoo`):
  - `convert_file` → `xml_import` con `Environment(cr, SUPERUSER_ID, {})` (`odoo/tools/convert.py:701`; CSV,
    `:770`); cada `<record>` va por `_load_records` → `_load_records_create` (`create`) o
    `_load_records_write` (`write`) (`odoo/models.py:4166-4172`). Un registro con `xmlid` cuyo registro se
    borró se vuelve a crear por el mismo camino.
  - **Borrado de registros obsoletos:** `ir.model.data._process_end` (`odoo/addons/base/models/ir_model.py:2254-2310`;
    `_process_end_unlink_record`, `:2250-2251`, hace `record.unlink()`), llamado desde
    `load_modules` con `env = api.Environment(cr, SUPERUSER_ID, {})` (`odoo/modules/loading.py:490` y `:505`).
  - **Desinstalación:** `module_uninstall` → `ir.model.data._module_data_uninstall`
    (`ir_model.py:2101-2112`, exige `is_system()`), desde `load_modules` con `SUPERUSER_ID`
    (`loading.py:516-527`). `model_id` con `ondelete='cascade'` (`trusted.py:58-61`) lo resuelve la clave
    ajena de PostgreSQL, sin ORM.
- **La copia:** `copy()` llama a `create` (`odoo/models.py:4714`) [L], así que la cubre la sobrescritura de
  `create`. El paso `copy` del Safe Plan (`controllers/safe_plan.py:917-937`) también. Archivar o
  desarchivar es `write`.
- **Vía del plan** [L]: `execute_safe_plan` (`safe_plan.py:785-…`) ejecuta los pasos con el `env` de quien
  confirma, sin `sudo` (`:792`); los pasos `create`, `write`, `copy` y `unlink` (`:878-945`) solo pasan
  `_meta_crud_block_error` (`:122-135`, `ir.ui.view` e `ir.model.fields`) y `crud_cusp_error`
  (`utils/privilege_cusp.py:124-164`, solo `res.users` y `res.groups`). Nada frena hoy un paso sobre
  `ai.trusted.action`. Las excepciones salen tal cual del ejecutor (`AccessError`).
- **Firmas de Odoo 14 que se sobrescriben:** `create(self, vals_list)` con `@api.model_create_multi`,
  `write(self, vals)` y `unlink(self)` (`odoo/models.py`). Idioma de Seges: parches 13 y 17
  (`safe_operation.py:531-540`, `ai_change_journal.py:637-649`).
- **Tests que lo tocan** [L]:
  - `test_system_action.py:452` y `:486` y `test_seges_user_groups.py:143`: solo `_get` y `_apply`.
  - **`test_seges_user_groups.py:77-81`, `test_registry_edit_does_not_lift_check`, hace
    `action.write({'group_ids': [(5, 0, 0)]})` como AI Administrator sin Ajustes.** Con el parche 32 da
    `AccessError` y el test pasa a **E**. La hoja decía que los tests solo usan `_get` y `_apply`: no es
    así. Decidido (tercera ronda): ese `write` pasa a `sudo()` con el marcador del parche 32. Su entorno
    (`env_adm`, `:45`) tiene el contexto vacío, así que el criterio combinado (abajo) lo deja pasar.
- **«Confused deputy»** (revisión de odoo-reviewer): un AI Administrator sin Ajustes propone un plan con un
  paso sobre `ai.trusted.action` y lo confirma un administrador con Ajustes, que puede resolver operaciones
  ajenas (`_can_resolve`, `safe_operation.py:336-343`). El plan corre con el `env` de quien confirma
  (`_resolve_execute`, `:798` y `:809`; `_execute_plan_with_timeouts`, `:958-960`): `is_system()` sería
  verdadero y el paso pasaría. `settings_admin_error` sola tampoco sirve: con `sudo()`, `env.user` sigue siendo
  el usuario sin Ajustes y rechazaría también los `sudo()` legítimos. De ahí el criterio combinado (D1).
- **a) `settings_admin_error`** [L]: `pns_ai_mcp/utils/privilege_cusp.py:106-121` (parche 12). Evalúa
  `env.user` **y**, si vienen en el contexto, los usuarios de `ai_journal_user_id` (quien propuso) y
  `ai_journal_confirmed_by_uid` (quien confirmó) (`:113-117`); devuelve el error si alguno no es
  superusuario ni tiene `base.group_system` (`:118-120`). Las claves solo pueden añadir un rechazo, nunca
  quitarlo. **Se cumple:** mira a quien propone, no solo a `self.env.user`. Ya la usan
  `crud_cusp_error` (`:143`, `:164`) y `_check_may_change_user_groups` (`ai_system_action.py:719`).
- **b) Dónde se ponen las claves** [L]: solo en `execute_plan_now` (`safe_operation.py:1454-1464`), justo
  antes de `execute_safe_plan(exec_env, steps)` (`:1465`): `ai_journal_user_id = self.user_id.id`
  (`user_id`, `required=True`, `:131-134`) y `ai_journal_confirmed_by_uid = confirmed_by_uid` o el uid que
  ejecuta. Todos los caminos que ejecutan los pasos de una operación pasan por ahí:
  - `action_confirm_and_execute` (`:1782`) y `action_execute_plan` (`:1846-1848`, la llama) →
    `_resolve_confirm_and_execute` (`:913`) → `_resolve_execute` (`:791`) → `_execute_plan_with_timeouts`
    → `execute_plan_now` (`:960`);
  - `_cleanup_stuck_state` (`:1019-1054`, parche 13) → `_retry_confirmed_not_executed` → `execute_plan_now`
    (`:1082`), con `Environment(cr, uid, {})`: el contexto vacío lo rellena `execute_plan_now`;
  - auto-confirmación en `propose` (`controllers/safe_plan.py:2308`) y `safe_plan_status` (`:2473`), también
    por `execute_plan_now`.
  - El parche 13 (`safe_operation.py:531-551`) hace que solo el sistema cree o cambie operaciones: el
    `user_id` (quien propone) no se puede falsificar por RPC.
  - **Única llamada directa a `execute_safe_plan`** fuera de `execute_plan_now`: el atajo de skills
    (`utils/skill_runtime.py:3405`), sin las claves; solo corre planes autoconfirmables (`:3377`), y un paso
    CRUD nunca lo es (`controllers/safe_plan.py:403-414`): ningún paso sobre `ai.trusted.action` llega por ahí.
  - **Se cumple.** Las recargas de datos (también un `module.update` dentro de un plan) usan
    `Environment(cr, SUPERUSER_ID, {})` (`odoo/tools/convert.py:701`): sin las claves, no les afecta.

### 2. Cambio propuesto (esbozo)

```diff
--- pns_ai_mcp/models/ai_trusted_action.py
@@ :23-24
+# Seges: parche 32 (PNS-97, seguridad). Ver docs/pendiente/parches_pns_ai.md
-from odoo import api, fields, models
-from odoo.exceptions import ValidationError
+from odoo import _, api, fields, models
+from odoo.exceptions import AccessError, ValidationError
@@ tras :80 (fin de _sql_constraints)
+    # Seges: parche 32 (PNS-97, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    def _check_settings_admin(self):
+        """A trusted action names a method that runs as whoever confirms the
+        plan: only Settings (or the system, as when loading data) defines it.
+        Inside a supervised plan, who proposed and confirmed it count too,
+        even in sudo()."""
+        from ..utils.privilege_cusp import settings_admin_error
+        ctx = self.env.context
+        in_plan = (ctx.get('ai_journal_user_id')
+                   or ctx.get('ai_journal_confirmed_by_uid'))
+        if not self.env.is_system() or (
+                in_plan and settings_admin_error(self.env)):
+            raise AccessError(_(
+                'Only a Settings administrator can change trusted actions.'))
+
+    # Seges: parche 32 (PNS-97, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    @api.model_create_multi
+    def create(self, vals_list):
+        self._check_settings_admin()
+        return super().create(vals_list)
+
+    # Seges: parche 32 (PNS-97, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    def write(self, vals):
+        self._check_settings_admin()
+        return super().write(vals)
+
+    # Seges: parche 32 (PNS-97, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    def unlink(self):
+        self._check_settings_admin()
+        return super().unlink()
```

- `is_system()` es `su` o Ajustes (hechos de base): la carga de datos, el `-u`, `_process_end` y la
  desinstalación pasan (contexto vacío, sin las claves); el AI Administrator sin Ajustes, no.
- **Criterio combinado (D1, «confused deputy»):** se rechaza si `not is_system()` o si el contexto trae
  `ai_journal_user_id` / `ai_journal_confirmed_by_uid` (está corriendo el plan de una operación supervisada,
  `execute_plan_now`) y `settings_admin_error(self.env)` da error, es decir, si quien ejecuta, quien propuso
  o quien confirmó no tiene Ajustes. Un plan propuesto por un AI Administrator sin Ajustes y confirmado por
  un administrador de Ajustes se rechaza, también si el paso llegara a escribir en `sudo()`. Fuera de un
  plan, `sudo()` sigue pasando (paso 0, b).
- **Import de `settings_admin_error` dentro del método**, como hace el fabricante con el mismo módulo
  (`ai_system_action.py:704`): queda cubierto por el marcador del helper y no añade otra línea de import
  con marcador.
- `write` comprueba aunque `vals` venga vacío (no hay escritores legítimos fuera de `su`; difiere del
  parche 17, que deja pasar `vals` vacío, pero aquí no hay ningún flujo que lo necesite).
- Sin tocar `ir.model.access.csv` (N11). Mensaje nuevo sin traducir: «Only a Settings administrator can
  change trusted actions.». **Marcadores:** 5 (imports, con línea propia; helper; `create`, `write` y
  `unlink`).

### 3. Qué se degrada

- El AI Administrator sin Ajustes ya no crea, cambia, copia, archiva ni borra acciones de confianza (por RPC
  ni con un plan). Sigue leyéndolas y ejecutándolas con `_apply` según sus `group_ids`.
- Un plan sobre `ai.trusted.action` solo se aplica si quien lo propuso **y** quien lo confirma tienen
  Ajustes: un administrador de Ajustes ya no puede confirmar el de un AI Administrator sin Ajustes (tendrá
  que proponerlo él o hacerlo a mano en Ajustes). Dentro de ese plan, ni `sudo()` lo salta.
- Un módulo de terceros que contribuya acciones por XML sigue funcionando (carga en `su`); uno que las cree
  en tiempo de ejecución fuera de `su` tendría que usar `sudo()` (hoy no hay ninguno; el docstring del
  fabricante cita `pns_acl_manager`, que no está en estos repos).
- En LIYBEN, si los dos AI Administrators no tienen Ajustes, no pueden tocar el registro (decisión 10:
  se consulta antes del despliegue).

### 4. Cómo comprobar si el fabricante ya lo ha corregido

```sh
grep -n "def create\|def write\|def unlink\|group_system\|is_system" pns_ai_mcp/models/ai_trusted_action.py; grep -n "trusted_action" pns_ai_mcp/security/ir.model.access.csv
```

Corregido si el modelo restringe las escrituras a Ajustes o al sistema (en Python o con una ACL de
`group_ai_admin` sin escritura, alta ni borrado).

### 5. Tests (`test_seges_e4p.py`, `TestSegesE4pTrustedAction(TransactionCase)`)

Usuarios con `new_test_user` como en `test_seges_user_groups.py:28-47`: AI Administrator sin Ajustes
(`base.group_user,pns_ai_mcp.group_ai_admin`, que implica AI Writer: `security/security_groups.xml:50`) y
AI Administrator con Ajustes, con sus entornos `env_adm` y `env_sys` (contexto vacío, como en `:45-46`).

- Negativos (AI Administrator sin Ajustes), `AccessError` y sin cambios:
  - `test_ai_admin_cannot_create` (acción nueva `seges.e4p` sobre `res.partner`; no existe tras el rechazo);
  - `test_ai_admin_cannot_write`: `apply_method`, `group_ids` (`[(5, 0, 0)]`), `label`, `danger` y `active`,
    uno por uno sobre `user.add_group`; los valores siguen como en el XML;
  - `test_ai_admin_cannot_unlink` y `test_ai_admin_cannot_copy`;
  - **vía del plan:** `test_plan_create_step_refused` (`execute_safe_plan(env_adm, [{'op': 'create', 'model':
    'ai.trusted.action', 'values': {…}}])` → `AccessError`; `search_count` del código nuevo = 0) y
    `test_plan_write_step_refused` (paso `write` que vacía `group_ids` de `view.set_field_readonly`).
- Negativos del «confused deputy» (D2). El contexto se pone como lo pone `execute_plan_now`
  (`safe_operation.py:1454-1464`), sin crear la operación: `action_confirm_and_execute` abre un cursor propio
  (`_execute_plan_with_timeouts`, `:955`) y no cabe en un `TransactionCase`. `PLAN_CTX` =
  `{'ai_journal_user_id': <AI Administrator sin Ajustes>, 'ai_journal_confirmed_by_uid': <administrador de
  Ajustes>}`:
  - `test_plan_confirmed_for_ai_admin_refused`: `execute_safe_plan(env_sys(context=PLAN_CTX), [paso write
    que vacía group_ids de view.set_field_readonly])` → `AccessError`; `group_ids` sin cambios. Es el caso
    que deja pasar `is_system()` solo;
  - `test_sudo_in_plan_context_refused`: `env_sys['ai.trusted.action'].with_context(**PLAN_CTX).sudo()`,
    `write` del mismo campo → `AccessError`; sin cambios.
- Controles:
  - `test_settings_admin_can_edit` (crear, cambiar y borrar con Ajustes, sin contexto de plan);
  - `test_sudo_can_edit`;
  - `test_factory_data_reload`: `convert_file(self.cr, 'pns_ai_mcp', 'data/trusted_actions_system.xml', {},
    'update', False, 'data')` (como un `-u`) sin error y los 9 `xmlid` siguen apuntando a sus registros;
  - **`test_plan_settings_admin_allowed` (test nuevo):** el mismo paso `write` con
    `ai_journal_user_id` y `ai_journal_confirmed_by_uid` del administrador de Ajustes → se aplica.
    No basta `test_settings_admin_can_edit`: no lleva el contexto de plan y no ejercita la segunda condición,
    así que no mostraría que el criterio combinado no bloquea un plan legítimo.
- `execute_safe_plan` en estos tests escribe el diario en el mismo cursor (`record_executed_step`); el único
  cursor propio del diario está en `_record_failed_plan` (`ai_change_journal.py:375-392`), que solo llama
  `execute_plan_now`. Sin cursores propios: todo se deshace con la transacción del test.
- **Cambio en un test existente** (aprobado en la tercera ronda): en `test_registry_edit_does_not_lift_check`,
  `action.sudo().write(…)` con el marcador `# Seges: parche 32 (PNS-97, seguridad)…`. Sigue probando lo que
  probaba (el criterio del parche 12 no depende del registro); que el AI Administrator no puede vaciar
  `group_ids` lo prueba ahora `test_ai_admin_cannot_write`.

### 6. Neutralización prevista

| Ejecución | Qué se retira | Deben fallar |
|---|---|---|
| N32 | `_check_settings_admin` no comprueba nada | `test_ai_admin_cannot_create`, `test_ai_admin_cannot_write`, `test_ai_admin_cannot_unlink`, `test_ai_admin_cannot_copy`, `test_plan_create_step_refused`, `test_plan_write_step_refused`, `test_plan_confirmed_for_ai_admin_refused`, `test_sudo_in_plan_context_refused` |
| N32j | La segunda condición (claves del plan con `settings_admin_error`); queda solo `is_system()` | `test_plan_confirmed_for_ai_admin_refused`, `test_sudo_in_plan_context_refused` |

Pasan en ambas: los cuatro controles y `test_registry_edit_does_not_lift_check` (en `sudo`, contexto vacío).
En N32j, los seis negativos del AI Administrator sin Ajustes siguen pasando (los rechaza `is_system()`).

## Parche 33 (PNS-29, resto 3): `_month_usage` privado y `default_get` del asistente con la ACL

### 1. Comprobaciones previas (paso 0)

- **Llamadores de `month_usage`** (Grep en los tres módulos, `static/`, vistas, datos, tests,
  `vertical-instaladores` y el repo del laboratorio) [L]: `provider.py:1053` (`spend_cap_reached`) y
  `usage_wizard.py:37` (`default_get`). Nada más. `spend_cap_reached` lo usan `provider.py:1061`
  (`assert_spend_cap`) y `engine.py:321` (`_without_capped`); sigue público y devuelve un booleano.
- **Asistente:** lo abre `action_open_usage` (`provider.py:1067-1076`, botón «This month» del formulario,
  `views/ai_provider_views.xml:11`) con `default_provider_id`. ACL: solo AI Administrator
  (`security/ir.model.access.csv:56`); `ai.provider` es legible por internos (`:10`).
- **Firma de Odoo 14 que se sobrescribe:** `default_get(self, fields_list)` con `@api.model`
  (`odoo/models.py:1280`, sin comprobación de ACL). La sobrescritura ya existe (`usage_wizard.py:25-65`); el
  parche añade una línea. `check_access_rights(operation, raise_exception=True)` lanza `AccessError` con el
  mensaje del core (traducido por Odoo).
- **Laboratorio:** reproducido por la hoja ([E], ficha 8 y «Revisión de la hoja»): `month_usage()` y
  `default_get` como `demo` devuelven las cifras; `check_access_rights('create')` como `demo` lanza
  `AccessError`. No se repite.
- **Otras vías de las cifras:** en Odoo 14 la primera llamada a `onchange` del asistente (sin
  `field_name`, `first_call`: `odoo/models.py:6051` y `:6076`) **sí llama a `default_get`** con los campos
  que faltan (`:6192-6195`) [L]; `demo` obtiene las cifras por ahí [E] (revisión de odoo-reviewer,
  04/11/2026). El parche lo cubre: el rechazo está en `default_get`, y lo prueba
  `test_usage_wizard_onchange_rpc_refused`. `create`/`read` del asistente exigen la ACL; ningún campo
  calculado de `ai.provider` usa `month_usage` [L].

### 2. Cambio propuesto (esbozo)

```diff
--- pns_ai_mcp/models/ai_provider.py
@@ :1016
-    def month_usage(self):
+    # Seges: parche 33 (PNS-29, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    def _month_usage(self):
@@ :1053
+        # Seges: parche 33 (PNS-29, seguridad). Ver docs/pendiente/parches_pns_ai.md
         return spend_cap_hit(
-            self.month_usage(),
+            self._month_usage(),
--- pns_ai_mcp/wizard/ai_provider_usage_wizard.py
@@ :37 (tras los dos imports locales de :34-35)
+        # Seges: parche 33 (PNS-29, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        self.check_access_rights('create')
-        usage = provider.month_usage()
+        usage = provider._month_usage()
```

- El marcador de `:1053` va encima de `return spend_cap_hit(` (la llamada ocupa varias líneas). En el
  asistente, el marcador y `check_access_rights('create')` van justo encima de `usage = provider._month_usage()`,
  que queda cubierta por ese marcador. **Marcadores:** 3.
- Sin mensajes nuevos (el de `check_access_rights` es del core). Sin tocar el CSV.

### 3. Qué se degrada

- Ningún interno sin AI Administrator obtiene por RPC los tokens y el coste del mes (ni con `month_usage` ni
  con `default_get` u `onchange` del asistente). El AI Administrator los sigue viendo en «This month».
- `default_get` del asistente sin `default_provider_id` no cambia (no lee cifras).
- Restos 1 y 2 de PNS-29, aceptados (D12, D10).

### 4. Cómo comprobar si el fabricante ya lo ha corregido

```sh
grep -n "def month_usage\|def _month_usage" pns_ai_mcp/models/ai_provider.py; grep -n "check_access_rights\|month_usage" pns_ai_mcp/wizard/ai_provider_usage_wizard.py
```

Corregido si `month_usage` deja de ser público (o comprueba el grupo) y el asistente no da cifras a quien no
tiene su ACL.

### 5. Tests (`test_seges_e4p.py`)

- `TestSegesE4pRpc` (proveedor creado en `sudo` en `setUp`):
  - `test_month_usage_rpc_refused`: interno y portal, `month_usage` → `AttributeError` (no existe) y
    `_month_usage` → `AccessError` (privado), sobre `[[provider.id]]`;
  - `test_usage_wizard_default_get_rpc_refused`: interno y portal, `default_get` de
    `ai.provider.usage.wizard` con `['total_tokens', 'cost_display']` y `context: {'default_provider_id': id}` →
    `AccessError`; la respuesta no trae `total_tokens`;
  - `test_usage_wizard_onchange_rpc_refused`: interno y portal, `onchange` de `ai.provider.usage.wizard` con
    `[[], {}, [], {'provider_id': '', 'total_tokens': '', 'cost_display': ''}]` (primera llamada) y
    `context: {'default_provider_id': id}` → `AccessError`; la respuesta no trae `value` con `total_tokens`.
  - **El portal no discrimina** en estos tres: sin el parche ya recibe `AccessError` por la ACL (no lee
    `ai.provider` ni el asistente), así que no muestra que el parche haga nada. Se mantiene como control de
    que el parche no le abre nada; lo que discrimina es el interno.
- `TestSegesE4pUsage(TransactionCase)`:
  - `test_month_usage_public_name_gone`: `hasattr(type(env['ai.provider']), 'month_usage')` falso y
    `_month_usage` presente;
  - `test_default_get_refused_for_internal`: interno de prueba, `with_context(default_provider_id=…)`
    `.default_get([...])` → `AccessError`;
  - `test_default_get_ai_admin_sees_figures` (control): AI Administrator → `provider_id`, `period_label` y
    `total_tokens` en el resultado;
  - `test_spend_cap_still_works` (control): `spend_cap_reached()` como interno devuelve un booleano.
- Sin cursores propios (`_month_usage` solo lee).

### 6. Neutralización prevista

| Ejecución | Qué se retira | Deben fallar |
|---|---|---|
| N33n | Vuelve el nombre público `month_usage` (y sus dos llamadores) | `test_month_usage_rpc_refused` (el público responde), `test_month_usage_public_name_gone` |
| N33w | Sin `check_access_rights('create')` en `default_get` | `test_usage_wizard_default_get_rpc_refused`, `test_usage_wizard_onchange_rpc_refused`, `test_default_get_refused_for_internal` (en los dos RPC, el interno; el portal sigue rechazado por la ACL) |

Pasan: `test_default_get_ai_admin_sees_figures` y `test_spend_cap_still_works`.

## Test de PNS-36 (`{0.cr.dbname}`), sin parche

- **Paso 0** [L]: la hoja lo comprobó en el laboratorio [E] (ficha 6): literal → `[PROHIBITED:FORMAT] … 'cr'`;
  en variable → lo rechaza el formateador (`AttributeError … 'cr' is not allowed`); igual con `registry`.
- **Test:** `pns_ai_mcp/tests/test_seges_format_guard.py`, `TestSegesFormatGuard.test_pns36_cr_dbname`, con
  el arnés de la clase (`_refused`, herramienta real `tool_relaxaicode` como `base.user_admin`, `:51-65`):
  - `"result = {'data': [{'v': '{0.cr.dbname}'.format(env)}]}\n"` (literal);
  - `"t = '{0.cr.dbname}'\nresult = {'data': [{'v': t.format(env)}]}\n"` (en variable);
  - lo mismo con `'{0.registry.db_name}'`;
  - en los cuatro, además, `assertFalse(self.env.cr.dbname in text, 'filtra')`.
- Cabecera del archivo: una línea de marcador nueva, `# Seges: tests de la entrega E4′ (PNS-36). Ver docs/pendiente/parches_pns_ai.md`.
- **Neutralización:** no es de un parche nuevo. Con el formateador del parche 23 ampliado neutralizado
  (NEU de E2′), debe fallar solo el caso en variable (el literal lo sigue rechazando el AST). Se comprueba
  en la misma tanda de neutralización de E4′.a (N23f).

## Parche 34 (fila 30): aviso fijo del servidor cuando `log_no_page` rechaza en un turno

### 1. Comprobaciones previas (paso 0)

**El `msgid`** [L, E]: `pns_ai_chatboo/i18n/es.po:2177`, exacto:
`msgid "No page was built. The reason is in the AI History."` →
`msgstr "No se ha creado la página. El motivo está en el Historial IA."` (`:2178`). Lo usa
`pns_ai_chatboo/models/chatboo_canvas_job.py:133` (`_process`, cuando `open_page` devuelve `''`) y `:156`
(`_on_crash`). En el laboratorio, `ir.translation._get_source(None, ('code',), 'es_ES', msgid)` devuelve la
traducción [E]. Odoo 14 busca las traducciones de código **sin filtrar por archivo**
(`odoo/tools/translate.py:484`, `_get_source(None, ('code',), lang, source)`) [L]: usarlo desde `async.py`
sale traducido sin tocar `i18n`.

**Llamadores de `log_no_page`** (`canvas.py:646`, función de módulo) [L]:

| Llamador | `session_id` |
|---|---|
| `_session_of_this_turn` (`canvas.py:696`, `:700`, `:704`) | No (sin sesión) · sí · sí |
| `edit_page` (`canvas.py:1009`) | Sí |
| `page_url` (`session.py:894`, excepción) | No |
| `page_html` (`session.py:918`; `:932`; `:943`, excepción) | No · sí · no |
| `page_edit` (`session.py:962`, excepción) | No |
| `_paint_canvas` (`session.py:1105`, `:1146`, `:1150`, `:1205`, `:1211`, `:1223`) | Según la línea; los de `:1146` en adelante, sí |

**Dónde se llama fuera de un job de Chatboo y qué pasa con la marca** [L]:

| Vía | Hilo | ¿Hay `_save_to_session` después? | Efecto de la marca |
|---|---|---|---|
| Turno de Chatboo (sandbox: `page_url`/`page_edit`/`page_html`; página en espera, `fulfill_waiting_page`) | El del job `chatboo.async.request` (`chatboo_job.py:194-227`); el sandbox y el diseño corren en ese mismo hilo (no hay ningún `Thread` ni ejecutor en `pns_ai_mcp`; el diseño ya suma su uso al turno por un `ContextVar`, `session.py:1272` → `llm_usage.note_turn_side_usage`) | Sí, en `_finalize` (`async.py:666`), en el mismo hilo | Se usa |
| Botón Canvas (`chatboo.canvas.job._process`, `chatboo_canvas_job.py:101-131`) | Su propio hilo de job | No (cierra con `_close`) y ya muestra su aviso (`:133`) | Ninguno: en ese hilo no hay marca abierta y la anotación no hace nada |
| Caja A desde `/mcp` (sin Chatboo) | El de la petición HTTP | No | Ninguno (sin marca abierta) |
| RPC o Python directo (`page_url` por RPC, tests) | El de la petición | No | Ninguno |
| `_cancel_pending` (`async.py:1488-1508`) | El de quien cancela (petición o cron) | **Sí**, rama de éxito (`_save_to_session(msg, {}, error=None)`, `:1499`) | Ninguno si la marca va ligada al job (ver diseño) |
| `_reclaim_one` (cron, `async.py:1510-1557`) | El del cron | Sí, pero rama `incomplete` | No aplica |

- En **modo test**, `_spawn` ejecuta `_process` en línea, en el hilo del test (`chatboo_job.py:190-192`).
- **`threading.local` o `contextvars`** (Python 3.7.3): los dos existen. Un hilo nuevo empieza con el
  contexto **vacío** (en 3.7 `threading.Thread` no copia el contexto): comprobado [E] (valor puesto en el
  hilo principal; en un hilo nuevo, `None`). Dentro de un hilo, los dos se comportan igual (los
  generadores del motor corren en el contexto de quien los itera). **Se elige `contextvars`**: es el patrón
  del fabricante para el estado por turno (`pns_ai_mcp/utils/llm_usage.py:11-33`, `_turn_side_usage`;
  `utils/inference_audit.py:17-23`) y `set` devuelve un token para deshacerlo en los tests. Lo que
  importa en los dos casos es no fiarse de lo que quede en un hilo reutilizado (el worker de prefork
  atiende peticiones seguidas en el mismo hilo): por eso la marca lleva el **id del job** y solo la lee
  `_save_to_session` del mismo job.
- **`canvas_rev`** (`session.py:86`, `Integer`) [E: tipo]. `_store_design` lo sube y confirma en un cursor
  propio (`session.py:999-1003`). `_finalize` llama a `_save_to_session` sobre el job leído en un cursor
  **nuevo** (`async.py:656-666`): lee el valor confirmado, sin caché vieja. En `_process`, la lectura va
  tras el `commit` de `:137`.
- **Precedente del fabricante:** la nota de respuesta incompleta (`async.py:1259-1281`): la nota va en
  `content` y **no** en `original_content` (`acc` limpio). `original_content` es lo que copian y exportan el
  cliente y lo que reenvía como historial (`chatboo_component_v2.js:1289`, `chatboo_export.js:493`, `:693`).
  `_assistant_content` se devuelve en los chips (`:1468-1469`) y `_finalize` lo escribe en `response` y
  `partial` y en `done_meta` (`:668-687`), con lo que el cliente actualiza la burbuja en vivo (mismo camino
  que los SVG, `:1231-1232`).
  - _Errata (06/11/2026):_ `original_content` **no** es «lo que reenvía como historial»: el historial lo
    monta el servidor (`get_model_history`) desde `content`.
- **`_save_to_session` sin cursor propio** en esta prueba [L]: `get_messages`, `set_messages`,
  `get_input_history`, `set_input_history`, `update_last_used`, `_consume_staged_assistant_download_chips`,
  `recover_orphan_download_chips` y `_claim_turn_file_chips` escriben o leen en el cursor del llamador;
  `_persist_turn_images`/`_files` no hacen nada sin imágenes ni ficheros, y `persist_inline_svgs_from_html`
  no guarda nada sin `<svg>`.
- **Archivos compartidos:** `canvas.py` lo tocan los parches 25, 26, 27 y 29, ninguno en `log_no_page`; el
  import nuevo va antes del marcador del parche 29 (`:20`), sin tocar ese marcador ni su import (`:21`);
  `async.py`, ningún parche de esta rama (el 6 está retirado).
- **c) `try`/`finally` en `_process`** [L]: `async.py:125` (`_process`). El cuerpo del motor va en un `try`
  (`:357`) con `except` (`:486-494`) y `finally` (`:495-508`: para el latido y, fuera de modo test, hace
  `rollback`). La marca se abre en `:138`, antes de ese `try`, así que el token existe en el `finally`.
  **Se cumple:** cabe `_NO_PAGE_WATCH.reset(token)` en una línea (más su marcador) al principio del
  `finally`. `_finalize` (y con él `_save_to_session`) corre dentro del `try` (`:478`, `:494`): el `reset`
  llega después de leer la marca.
- **d) Import circular** [L]: `canvas.py` solo importa, a nivel de módulo, la biblioteca estándar y
  `odoo._` (`:14-23`); en ningún punto importa `chatboo_async_request` (los imports diferidos que tiene son de
  `pns_ai_mcp`: `:655`, `:686-687`, `:960`, `:1017`, `:1027`, `:1043`). `models/__init__.py` carga
  `chatboo_canvas` (`:7`) antes que `chatboo_async_request` (`:10`). **Se cumple:** los imports de
  `chatboo_canvas` pueden ir arriba de `async.py` sin import circular.
- **Firmas de Odoo 14:** ninguna (métodos del fabricante).

### 2. Cambio propuesto (esbozo)

```diff
--- pns_ai_chatboo/models/chatboo_canvas.py
@@ :19-21 (importaciones de la biblioteca estándar, antes del marcador del parche 29)
 import unicodedata
+# Seges: parche 34 (PNS-96, funcional). Ver docs/pendiente/parches_pns_ai.md
+from contextvars import ContextVar
 # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
 from html.parser import HTMLParser
@@ tras :25 (_logger)
+# Seges: parche 34 (PNS-96, funcional). Ver docs/pendiente/parches_pns_ai.md
+# The Chatboo job whose turn is running in this thread, and whether a page
+# was refused in it. Only that job's _save_to_session reads it.
+_NO_PAGE_WATCH = ContextVar('pns_chatboo_no_page', default=None)
@@ antes de :646 (def log_no_page)
+# Seges: parche 34 (PNS-96, funcional). Ver docs/pendiente/parches_pns_ai.md
+def watch_no_page(job_id, session_id, rev):
+    """Open the watch for one Chatboo turn. Returns the token for ``reset``."""
+    return _NO_PAGE_WATCH.set({
+        'job': job_id, 'session': session_id, 'rev': rev or 0, 'refused': False,
+    })
+
+
+# Seges: parche 34 (PNS-96, funcional). Ver docs/pendiente/parches_pns_ai.md
+def page_refused_in_job(job_id, session_id, rev):
+    """True when this job's turn refused a page and the page did not change."""
+    watch = _NO_PAGE_WATCH.get()
+    return bool(
+        watch and watch['job'] == job_id and watch['session'] == session_id
+        and watch['refused'] and (rev or 0) == watch['rev']
+    )
+
+
 def log_no_page(env, reason, session_id=False):
@@ :653 (tras _logger.info('Chatboo canvas: %s', reason))
+    # Seges: parche 34 (PNS-96, funcional). Ver docs/pendiente/parches_pns_ai.md
+    watch = _NO_PAGE_WATCH.get()
+    if watch:
+        # The turn must go on: a session_id that is not an id does not count.
+        try:
+            same = not session_id or int(session_id) == watch['session']
+        except (TypeError, ValueError):
+            same = False
+        if same:
+            watch['refused'] = True
--- pns_ai_chatboo/models/chatboo_async_request.py
@@ :18 (importaciones relativas)
+# Seges: parche 34 (PNS-96, funcional). Ver docs/pendiente/parches_pns_ai.md
+from .chatboo_canvas import _NO_PAGE_WATCH, page_refused_in_job, watch_no_page
 from .chatboo_job import _env_manage, _get_registry, _is_test_mode
@@ :138 (tras self._notify('thinking'))
+        # Seges: parche 34 (PNS-96, funcional). Ver docs/pendiente/parches_pns_ai.md
+        no_page_token = watch_no_page(
+            self.id, self.session_id.id, self.session_id.canvas_rev)
@@ :495 (primera línea del finally del try de :357)
         finally:
+            # Seges: parche 34 (PNS-96, funcional). Ver docs/pendiente/parches_pns_ai.md
+            _NO_PAGE_WATCH.reset(no_page_token)
             # Parar el latido pase lo que pase (éxito o error).
@@ :1291 (rama de éxito, primera línea tras «else:»)
+            # Seges: parche 34 (PNS-96, funcional). Ver docs/pendiente/parches_pns_ai.md
+            _content = acc or ''
+            if page_refused_in_job(self.id, session.id, session.canvas_rev):
+                _note = _('No page was built. The reason is in the AI History.')
+                _content = (f"{acc}\n\n_{_note}_" if (acc or '').strip()
+                            else f"_{_note}_")
+                _assistant_content = _content
@@ :1349
-                'content': acc or '',
+                'content': _content,  # Seges: parche 34 (PNS-96, funcional). Ver docs/pendiente/parches_pns_ai.md
```

- **Marca sin sesión conocida:** la anotación de `log_no_page` sin `session_id` (excepciones de
  `page_url`/`page_html`/`page_edit`, «this turn carries no Chatboo session») cuenta para la sesión del job:
  la marca solo existe dentro de un job de Chatboo, que tiene una sola sesión. Con un `session_id`
  distinto del del job, no cuenta.
- **Imports arriba de `async.py`** (no dentro de los métodos): sin import circular (paso 0, d). El
  aviso se compone con f-strings (Python 3.7.3 las admite).
- **`int(session_id)` dentro de `try`** (D3): `log_no_page` es el camino blando («answer '' so the turn goes
  on») y no puede fallar por un `session_id` raro; si no es un id, la anotación no cuenta.
- **`reset` en el `finally` de `_process`** (D3; se cumple c): el token de `watch_no_page` se deshace al
  terminar el turno, con éxito o con error. Es higiene, no seguridad: la marca va ligada al id del job, que no
  se repite (las secuencias de PostgreSQL no se deshacen), así que una marca que quedara en un hilo
  reutilizado no la leería otro job. Entre `:138` y el `try` de `:357` hay una salida que no pasa por ese
  `finally`: si falla el `commit` de las escrituras de la sesión, `_finalize` con error y `return`
  (`:294-306`, solo fuera de modo test); también una excepción no capturada en ese tramo. Ahí no hay
  `reset`, con el mismo efecto nulo (la rama de error no lee la marca). Los tests deshacen la suya con
  su token.
- **`original_content` sigue siendo `acc`**, como en la nota de respuesta incompleta (precedente): decidido
  en la tercera ronda (el aviso del servidor solo va en `content`).
- **Identificador del marcador:** `PNS-96`, tipo `funcional` (decidido en la tercera ronda).
- Sin mensajes nuevos: reutiliza el `msgid` existente. **Marcadores:** 10 (5 en `canvas.py`: import,
  `_NO_PAGE_WATCH`, `watch_no_page`, `page_refused_in_job` y la anotación de `log_no_page`; 5 en `async.py`:
  import, apertura en `:138`, `reset` en el `finally`, rama de éxito en `:1291` y `content` en `:1349`).

### 3. Qué se degrada

- **Límites, ya en la hoja:** no corrige lo que escribe el modelo (le añade debajo una corrección
  determinista); no cubre los turnos en que el modelo afirma un cambio sin llamar a la herramienta; el texto
  no es exacto cuando lo rechazado es una edición («No se ha creado la página»); la vía de respaldo por SQL
  de `_finalize` (`async.py:703-714`) no lleva el aviso.
- **Nuevos de esta propuesta:**
  - si en el mismo turno se crea una página y después se rechaza una edición, `canvas_rev` ha cambiado y no
    sale aviso;
  - si el modelo ya explica bien el rechazo, el aviso sale igual (redundante, no contradictorio);
  - el aviso no entra en el `original_content` que guarda el servidor: tras recargar la sesión no se copia,
    no se exporta y el modelo no lo ve en el turno siguiente. **Matiz, en la burbuja en vivo:** el cliente
    toma `assistant_content` como `result.content` (`chatboo_component_v2.js:3033-3035`) y de ahí su
    `originalContent` (`:3124`). Hasta recargar, copiar o exportar desde esa burbuja **sí** incluye el aviso,
    y si el cliente guarda la sesión (`_messagesForPersist`, `:1284-1298`, que manda `original_content` o
    `content`) puede quedar guardado con él. No reabre la decisión (el servidor solo lo pone en `content`);
    se comprueba en el staging (abajo);
  - **turno vacío:** si el modelo no escribe nada, `_finalize` convierte el turno en error (`async.py:614-628`,
    salvo que haya un entregable, `done_meta_has_deliverable`) y la rama de error de `_save_to_session` no
    lleva aviso: el usuario ve el error genérico («The model returned no content…»), no el aviso. El aviso con
    respuesta vacía solo sale cuando hay entregable.
- **Comprobación en el staging (VPS, E4′.h):** provocar un rechazo de página en un turno de Chatboo; en la
  burbuja en vivo, copiar y exportar (anotar si llevan el aviso); recargar la sesión y repetir (sin aviso);
  leer `chatboo.session.get_messages()` del último mensaje del asistente antes y después de recargar y anotar
  si `original_content` lleva el aviso (lo habría guardado `_messagesForPersist`).

### 4. Cómo comprobar si el fabricante ya lo ha corregido

```sh
grep -n "No page was built" pns_ai_chatboo/models/chatboo_async_request.py pns_ai_chatboo/models/chatboo_session.py; grep -n "def log_no_page" -A14 pns_ai_chatboo/models/chatboo_canvas.py
```

Corregido si el servidor deja en la respuesta del turno (o en la burbuja) un aviso cuando el lienzo rechaza,
o si `log_no_page` devuelve algo que el turno muestre al usuario.

### 5. Tests (`pns_ai_chatboo/tests/test_seges_chatboo_canvas.py`, clase nueva `TestSegesNoPageNotice(_SegesCanvasCase)`)

`HttpCase` con el registro en modo test: lo que `log_no_page` escriba en `ai.log` va por un `TestCursor`
sobre la transacción del test y se deshace con ella; no hay filas que contar ni limpiar. El job se crea
como en el controlador: `env['chatboo.async.request'].with_user(self.user_a)._enqueue(self.session_a.id,
'seges e4p')` (`async.py:94-117`, en `sudo` por la ACL). Cada test abre la marca con `watch_no_page(job.id,
session.id, session.canvas_rev)`, como `_process`, y la deshace con `addCleanup(_NO_PAGE_WATCH.reset, token)`.
`ACC = 'He actualizado el color de fondo.'`; `NOTICE` = el `msgid` en inglés (el entorno del test no lleva
`lang`).

- `test_notice_after_refusal`: `log_no_page(env_a, 'seges e4p', session.id)` y
  `job.with_user(user_a)._save_to_session(ACC, {}, error=None)` → el último mensaje del asistente es
  `ACC + '\n\n_' + NOTICE + '_'`, `original_content == ACC` y el resultado trae `assistant_content` con el aviso.
  - _Errata (06/11/2026):_ con la opción A, `original_content == content` (no `== ACC`); y, cuando `acc`
    es HTML, el aviso se anexa como `<p><em>…</em></p>` (F1).
- `test_notice_unknown_session`: `log_no_page(env_a, 'seges e4p')` sin `session_id` → con aviso.
- `test_notice_empty_answer`: `acc = ''` → contenido `'_' + NOTICE + '_'`. Llama a `_save_to_session`
  directamente con `error=None`: en un turno real sin entregable, `_finalize` lo habría convertido antes en
  error (`async.py:614-628`) y la rama de error no lleva aviso (ver «Qué se degrada»).
- Controles, sin aviso y sin `assistant_content`:
  - `test_no_notice_without_refusal` (marca abierta, sin `log_no_page`);
  - `test_no_notice_when_page_changed` (marca, `log_no_page` y después `session.sudo().write({'canvas_rev': rev + 1})`);
  - `test_no_notice_other_job` (marca del job 1, `_save_to_session` del job 2 de la misma sesión, como un
    `_cancel_pending`);
  - `test_no_notice_other_session` (`log_no_page` con el id de `session_b`);
  - `test_no_watch` (sin marca: `token = _NO_PAGE_WATCH.set(None)` y `addCleanup(_NO_PAGE_WATCH.reset,
    token)`, para no depender de lo que haya dejado otro test en el hilo; `log_no_page` no falla y
    `_save_to_session` no añade nada; es lo que pasa en el botón Canvas y por RPC).

### 6. Neutralización prevista

| Ejecución | Qué se retira | Deben fallar |
|---|---|---|
| N34m | `log_no_page` no anota | `test_notice_after_refusal`, `test_notice_unknown_session`, `test_notice_empty_answer` |
| N34s | `_save_to_session` no añade el aviso | los mismos tres |
| N34r | `page_refused_in_job` no compara `canvas_rev` | `test_no_notice_when_page_changed` |
| N34j | `page_refused_in_job` no compara el job | `test_no_notice_other_job` |

Pasan en todas: `test_no_notice_without_refusal`, `test_no_notice_other_session` (salvo si se retira también
la comparación de sesión, que no se neutraliza aparte) y `test_no_watch`.

## Ajustes a la hoja que salen del paso 0 (sin cambiar sus decisiones)

1. **Test del parche 30:** la hoja pedía «error y 0 filas `seges_m11` contadas desde un cursor nuevo» con el
   arnés RPC. En un `HttpCase` `_create_log_entry` no escribe nunca (`ai_log.py:718`), así que contar filas
   ahí no discrimina. Se separa: RPC para el error (`HttpCase`) y `TransactionCase` sin modo test, con
   usuarios guardados, para las filas.
2. **`log_provider_failover` no es explotable por RPC** (necesita registros): el parche lo cubre igual.
3. **Parche 34, marca ligada al job:** la hoja hablaba de una marca por hilo con el `session_id`.
   `_cancel_pending` también llega a la rama de éxito de `_save_to_session`, desde otro hilo o desde un
   hilo reutilizado: la marca lleva además el id del job.

## Orden de implementación y commits

Tres commits por entrega (código, tests y documentación), como desde E2′ (decidido en la tercera ronda; la
regla N11 del registro se corrige en el commit 3). No hago commits: los sube Sergio.

| # | Commit | Archivos |
|---|---|---|
| 1 | `[FIX] pns_ai_mcp: parches 30 a 33 (E4′.a)` | `pns_ai_mcp/models/ai_execution_engine.py` (parche 30: import de `AccessError`, helper y seis llamadas; parche 31: `chat_completion`), `pns_ai_mcp/models/ai_trusted_action.py` (32), `pns_ai_mcp/models/ai_provider.py` y `pns_ai_mcp/wizard/ai_provider_usage_wizard.py` (33) |
| 2 | `[TEST] pns_ai_mcp: tests de E4′.a` | `pns_ai_mcp/tests/test_seges_e4p.py` (nuevo), `pns_ai_mcp/tests/__init__.py`, `pns_ai_mcp/tests/test_seges_format_guard.py` (PNS-36), `pns_ai_mcp/tests/test_seges_user_groups.py` (`sudo()` aprobado en la tercera ronda) |
| 3 | `[DOC] E4′.a` | `docs/pendiente/parches_pns_ai.md` (índice, entradas 30 a 33, línea base, neutralización), `docs/specs/comparacion_pns_ai_3-1-879.md` (cierre de PNS-36), `docs/pendiente/plan_correccion_pns_ai_3879.md` (estado, seguimiento), esta propuesta. **Erratas, todas en este commit:** (a) plan §5: filas 25 a 29 «validado en staging (04/11/2026)»; fila 15, R8 en staging con lite (excepción a la decisión 6); (b) plan §4: entrada «Staging pns_demo, tras E3′» y las filas 758 a 761 de `ai_log` del laboratorio (se conservan); (c) plan §1 y regla N11 del registro: tres commits por entrega desde E2′; (d) registro, «Cambios en tests del fabricante»: `test_failed_execute_journals_outside_rollback` aceptado como desfasado (no «pendiente de decisión»); (e) plan §3.2: añadir el defecto de `keys` y `customer_360._iso` como defecto de `ensure_module_result_call`; (f) cabecera del registro: añadir el staging del 04/11/2026; (g) `customer_360._iso` («`_iso` recibe una fecha como str»): `parches_pns_ai.md:1611-1613` y `:1710`, y `plan_correccion_pns_ai_3879.md:375` |
| 4 | `[FIX] pns_ai_chatboo: parche 34 (PNS-96)` | `pns_ai_chatboo/models/chatboo_canvas.py`, `pns_ai_chatboo/models/chatboo_async_request.py` |
| 5 | `[TEST] pns_ai_chatboo: tests de E4′.b` | `pns_ai_chatboo/tests/test_seges_chatboo_canvas.py` (y la línea de marcador de E4′ en `pns_ai_chatboo/tests/__init__.py`, si se registra) |
| 6 | `[DOC] E4′.b` | `docs/pendiente/parches_pns_ai.md` (entrada 34, «Qué se degrada» del parche 26 con «[object Object]», decisión 7), `docs/pendiente/plan_correccion_pns_ai_3879.md` |

Después: E4′.h (script de pruebas de E4′, sin tocar los de E2′ ni E3′, con la comprobación del parche 34 en el
staging) → una sola subida al staging.

- **Comprobaciones de cada entrega**, como en E3′: `py_compile` con Python 3.7.3 en la imagen
  `odoo-dev:14-lab_pns_ai_3879`; `python3 ~/.claude/hooks/odoo_lint.py --revisar --base ca707a9 pns_ai_mcp/ pns_ai_chatboo/`;
  batería completa (`odoo-dev 14 tests pns_ai_mcp,pns_ai_chatboo`); neutralización con copia, cambio,
  batería, restauración y SHA-256 de cada archivo.
- **Línea base de referencia:** **435 tests, 18 F y 32 E** (log `tests-20261030-173803.log`); ninguno de los
  50 es de Seges. Se repite antes de cambiar nada. Los 50 que fallan, los mismos por nombre.
- **Tests nuevos de E4′.a: 29**, todos en verde:
  - parche 30: 6 (`TestSegesE4pRpc`: `test_log_foreign_user_refused`, `test_log_portal_refused`,
    `test_log_own_rpc_allowed`; `TestSegesE4pLogRows`: `test_foreign_user_leaves_no_row`,
    `test_external_user_leaves_no_row`, `test_own_row_written`);
  - parche 31: 3 (`test_chat_completion_rpc_refused`; `TestSegesE4pChatCompletion`: `test_direct_call_refused`,
    `test_sudo_call_works`);
  - parche 32: 12 (8 negativos: `test_ai_admin_cannot_create`, `_write`, `_unlink`, `_copy`,
    `test_plan_create_step_refused`, `test_plan_write_step_refused`, `test_plan_confirmed_for_ai_admin_refused`,
    `test_sudo_in_plan_context_refused`; 4 controles: `test_settings_admin_can_edit`, `test_sudo_can_edit`,
    `test_factory_data_reload`, `test_plan_settings_admin_allowed`);
  - parche 33: 7 (`TestSegesE4pRpc`: `test_month_usage_rpc_refused`, `test_usage_wizard_default_get_rpc_refused`,
    `test_usage_wizard_onchange_rpc_refused`; `TestSegesE4pUsage`: `test_month_usage_public_name_gone`,
    `test_default_get_refused_for_internal`, `test_default_get_ai_admin_sees_figures`,
    `test_spend_cap_still_works`);
  - PNS-36: 1 (`test_pns36_cr_dbname`).
  - Además, `test_registry_edit_does_not_lift_check` (existente, modificado; no cuenta como nuevo) sigue en
    verde. Total esperado si la línea base se repite igual: **464 tests, 18 F y 32 E**.
- **Tests nuevos de E4′.b: 8** (3 con aviso: `test_notice_after_refusal`, `test_notice_unknown_session`,
  `test_notice_empty_answer`; 5 controles: `test_no_notice_without_refusal`, `test_no_notice_when_page_changed`,
  `test_no_notice_other_job`, `test_no_notice_other_session`, `test_no_watch`). Total esperado: **472 tests,
  18 F y 32 E**.
- **Marcadores esperados:** `grep -rn "Seges: parche 3[0-4] (" pns_ai_mcp pns_ai_chatboo --include=*.py | grep -v /tests/`:
  **27 líneas**:
  - parche 30: 8 (import, helper y seis llamadas, en `ai_execution_engine.py`);
  - parche 31: 1 (`chat_completion`);
  - parche 32: 5 (imports, helper, `create`, `write` y `unlink`, en `ai_trusted_action.py`);
  - parche 33: 3 (`_month_usage` y `spend_cap_reached` en `ai_provider.py`; `default_get` en el asistente);
  - parche 34: 10 (5 en `chatboo_canvas.py`: import, `_NO_PAGE_WATCH`, `watch_no_page`, `page_refused_in_job`,
    anotación de `log_no_page`; 5 en `chatboo_async_request.py`: import, apertura en `_process`, `reset` en el
    `finally`, rama de éxito y `content`).
  - Por entrega: E4′.a, 17 (`grep … "Seges: parche 3[0-3] ("`); E4′.b, 10 (`"Seges: parche 34 ("`).

## Decisiones de Sergio (tercera y cuarta ronda)

**Tercera ronda (04/11/2026), aprobadas:**

1. `test_registry_edit_does_not_lift_check`: el `write` pasa a `sudo()` con el marcador del parche 32.
2. Ajustes del paso 0: test del parche 30 partido en RPC y `TransactionCase`; marca del parche 34 ligada al
   job.
3. Parche 34: el aviso del servidor solo en `content` (no en `original_content`).
4. Parche 34: marcador «PNS-96, funcional».
5. Tres commits por entrega en E4′.a y E4′.b.

**Cuarta ronda (05/11/2026):**

- **D1.** Criterio combinado del parche 32: aprobado, condicionado a las comprobaciones a) y b) del paso 0.
  Las dos se cumplen (parche 32, paso 0): se aplica.
- **D2.** Tests nuevos de los hallazgos 2 y 3: los cuatro (`test_usage_wizard_onchange_rpc_refused`,
  `test_plan_confirmed_for_ai_admin_refused`, `test_sudo_in_plan_context_refused` y el control nuevo
  `test_plan_settings_admin_allowed`), con N32j y N33w ampliada.
- **D3.** Sugerencias: `try`/`except` en la anotación de `log_no_page`; `test_no_watch` con
  `_NO_PAGE_WATCH.set(None)` y `reset`; `self.env.ref('base.user_admin').id` en los tests del parche 30;
  `reset` en el `finally` de `_process`, aplicado porque se cumple c). N34ses: no.

## Decisiones pendientes

Ninguna. Las cuatro comprobaciones del paso 0 se cumplen (a y b, en el parche 32; c y d, en el parche 34),
así que no queda nada «Pendiente de decisión de Sergio».

## Resultado de E4′.a (05/11/2026)

- **Implementada como se propuso:** parches 30 a 33, el test de PNS-36 y el cambio a `sudo()` en
  `test_registry_edit_does_not_lift_check`. Entradas, neutralización y revisión en el
  [registro](parches_pns_ai.md), «Parches de la rama 14.0-pns-ai-3879 (E4′.a)».
- **Tests:** línea base repetida, 435 · 18 F · 32 E · 3 saltados (`tests-20261105-095615.log`), igual por
  nombre que `tests-20261030-173803.log`. Con E4′.a, **464 · 18 F · 32 E · 3 saltados**
  (`tests-20261105-101526.log`; tras las sugerencias del revisor, `tests-20261105-111902.log`): los mismos 50
  fallos, ninguno de Seges, y los 29 nuevos en verde, como se esperaba.
- **Comprobaciones:** `py_compile` con Python 3.7.3, correcto; 17 marcadores fuera de tests, como se
  esperaba. Lint: 0 avisos nuevos, salvo I001 y C0415 en `ai_trusted_action.py`, **aceptados por Sergio**.
- **Neutralización:** N30u, N30i, N31, N32, N32j, N33n, N33w y N23f, una cada vez, con restauración
  comprobada por SHA-256; fallan los tests previstos y los controles pasan en todas. Batería final
  restaurada: `tests-20261105-105904.log`, 464 · 18 F · 32 E · 3 saltados. En N23f falla además
  `TestSegesSkillFormat.test_skill_format_blocked`, que se añade a la lista de NEU-A.
- **Revisión (`odoo-reviewer`):** **APROBADA**. Sugerencias de tests aplicadas; la del docstring, no.
  Observaciones, en el registro.
- **Pendiente:** E4′.b (parche 34) y E4′.h; después, una sola subida al staging.

## Resultado de E4′.b (05/11/2026)

- **Implementada como se propuso:** parche 34. Entrada, neutralización y revisión en el
  [registro](parches_pns_ai.md), «Parches de la rama 14.0-pns-ai-3879 (E4′.b)».
- **Tests:** línea base, 464 · 18 F · 32 E · 3 saltados (`tests-20261105-111902.log`, mismo código que
  `039a5e5`). Con E4′.b, **472 · 18 F · 32 E · 3 saltados** (`tests-20261105-115245.log`): los mismos 50
  fallos por nombre, ninguno de Seges, y los 8 nuevos de `TestSegesNoPageNotice` en verde, como se esperaba.
- **Comprobaciones:** `py_compile` con Python 3.7.3, correcto; lint con `--base 039a5e5`, 0 avisos nuevos;
  10 marcadores fuera de tests, como se esperaba.
- **Neutralización:** N34m y N34s (21 F · 32 E: los tres tests con aviso), N34r y N34j (19 F · 32 E:
  `test_no_notice_when_page_changed` y `test_no_notice_other_job`), una cada vez, con restauración
  comprobada por SHA-256; los tres controles pasan en todas. Batería final restaurada:
  `tests-20261105-122437.log`, 472 · 18 F · 32 E · 3 saltados, con los mismos 50 fallos por nombre y
  ninguno nuevo.
- **Revisión (`odoo-reviewer`):** **APROBADA**, sin bloqueantes ni menores. Sugerencia **aceptada por Sergio
  sin cambio:** la lectura de `canvas_rev` en la apertura de la marca va sin `try` (si fallara, el turno
  acabaría en «crashed»; arreglo previsto si se viera: `try` con `rev = 0`). Las demás observaciones (alcance
  de los tests, efecto en `response`/`partial`/`done_meta` y el aviso en la burbuja en vivo), en el registro;
  no reabren la decisión 3 de la tercera ronda.
- **Pendiente:** E4′.h (script de pruebas de E4′, con las validaciones del parche 34 del
  [plan](plan_correccion_pns_ai_3879.md), apartado E4′); después, una sola subida al staging.

## Resultado de E4′.b2 y E4′.b3 (opción A y F1, 05-06/11/2026)

Ampliación del parche 34 sobre la copia de trabajo de E4′.b (HEAD `421a838`). El registro completo (cambio,
tests, neutralización con N34o y N34h, laboratorio e informe) está en el
[registro](parches_pns_ai.md), «Parches de la rama 14.0-pns-ai-3879 (E4′.b2 y E4′.b3)»; aquí quedan las
decisiones que **sustituyen o corrigen** lo escrito más arriba en esta propuesta.

- **Decisión 3 de la tercera ronda, sustituida (opción A, Sergio 05/11/2026):** donde esta propuesta dice que
  «el aviso del servidor solo va en `content`, no en `original_content`» (apartado «Decisiones de Sergio»,
  punto 3; apartado «Cambio propuesto», viñeta «`original_content` sigue siendo `acc`»; esbozo del diff, línea
  `'content': _content` sin tocar `original_content`), **con aviso `original_content` lleva ahora el mismo
  texto que `content`**; sin aviso, el valor de hoy (`acc or ''`). El esbozo del diff queda desfasado en ese
  punto: el código pone `'original_content': _content`. Descartadas C, D y E.
- **Formato del aviso (F1, Sergio 06/11/2026):** cuando el contenido es HTML
  (`(acc or '').lstrip().startswith('<')`), el aviso se anexa como `'<p><em>' + html.escape(_note) +
  '</em></p>'` en vez de en markdown (se añade `import html`, stdlib); si no, el markdown del esbozo.
  Descartadas F5 y F4.
- **Imprecisión del apartado «Qué se degrada», corregida:** la frase «el aviso no entra en el
  `original_content` que guarda el servidor: tras recargar la sesión no se copia, no se exporta y el modelo no
  lo ve en el turno siguiente» es **inexacta**. (a) El modelo **ya veía** el aviso el turno siguiente, incluso
  antes de la opción A, porque el motor compacta el historial leyendo `content`, no `original_content`
  (`pns_ai_mcp/utils/history_compact.py:386-389`, desde `engine_turn_messages.py:207-208`). (b) Con la opción
  A el aviso **sí** se ve en la burbuja tras recargar y entra en el PDF/DOCX; **copiar no lo lleva** (lee
  `clip_data`, del fabricante) y el **XLSX con tabla tampoco**.
- **Precedente del fabricante (nota «incomplete response»), al informe:** esa nota
  (`chatboo_async_request.py:1266-1287`, `'original_content': acc or ''` en `:1282`) **tampoco se ve en la
  burbuja** por el mismo mecanismo (`_loadSession` usa `original_content || content`); la opción A **no** la
  toca. Candidata al informe al fabricante, junto con el HTML crudo en PDF/DOCX y el error invisible del botón
  Canvas (ver el registro y el [plan](plan_correccion_pns_ai_3879.md), §3.2).
- **Recuentos:** los marcadores del parche 34 pasan de **10** (esbozo y E4′.b) a **11** (opción A) y **12**
  (F1); el grep de los parches 30-34 fuera de tests, de **27** a **28** (opción A) y **29** (F1). La clase
  `TestSegesNoPageNotice` pasa de **8 a 9** tests (nuevo `test_notice_html_answer`). Batería final (F1):
  `tests-20261106-162710.log`, **473 · 18 F · 32 E · 3 saltados**, mismos 50 fallos por nombre.
- **Revisión:** opción A (05/11/2026) y F1 (06/11/2026), **APROBADAS** por `odoo-reviewer`, sin bloqueantes.
- **Pendiente:** E4′.h (incluye el Paso 1, el error invisible del botón Canvas); después, una sola subida al
  staging.
