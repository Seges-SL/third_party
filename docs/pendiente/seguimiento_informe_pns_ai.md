# Seguimiento del informe al fabricante: pns_base 1.2.32, pns_ai_mcp 3.1.782 y pns_ai_chatboo 2.1.453

- **Versiones comparadas:** rama `14.0-analisis-pns-ai` (pns_base 1.2.10, pns_ai_mcp 3.1.486,
  pns_ai_chatboo 2.1.322; la versión del informe) frente a `HEAD` de `14.0-pns-ai-3` (pns_base 1.2.32,
  pns_ai_mcp 3.1.782, pns_ai_chatboo 2.1.453). Diff: `git diff 14.0-analisis-pns-ai..HEAD`.
- **Fecha:** 13/10/2026.
- **Fuentes:** `docs/pendiente/informe_fabricante_pns_ai.md` (PNS-01 a PNS-80),
  `docs/specs/cambios_pns_ai_3-1-782.md` (inventario de la fase 1) y el código actual.
- **Método:** solo lectura de código. Las líneas citadas son de la versión nueva salvo que se diga
  lo contrario. No se ha ejecutado nada en el laboratorio.
- **Alcance:** primer bloque, hallazgos de gravedad crítica y alta (35); segundo bloque, de gravedad
  media y baja (45, con PNS-22, que pasó a Media en la revisión del informe, y PNS-79). Total: los
  80 hallazgos del informe. Tercer bloque: hallazgos nuevos del código nuevo o modificado
  (PNS-81 a PNS-89) y compatibilidad con Odoo 14 (Python 3.7 y librerías de la imagen).

> **Fase 3 bloqueada:** pns_ai_mcp y pns_ai_chatboo no se importan con Python 3.7, ver
> cambios_pns_ai_3-1-782.md (`pns_ai_mcp/controllers/mcp_decorators.py:169`, anotación
> `tuple[...]` evaluada al importar). Todas las pruebas de laboratorio de este documento quedan
> pendientes hasta que el fabricante lo corrija. Con esa línea corregida, los módulos se importarían,
> pero quedan dos fallos en ejecución (PNS-81 y sección «Compatibilidad con Odoo 14»).

Estados: **CORREGIDO** (el cambio cubre el hallazgo y sus puntos de entrada) · **PARCIAL** (cubre
una parte; queda un resto concreto) · **SIN CAMBIOS** · **YA NO APLICA** (el código desapareció) ·
**DUDOSO** (no se puede decidir sin prueba en el laboratorio) · **NUEVO** (hallazgo del código nuevo o
modificado de esta versión; no estaba en el informe).

## Tabla resumen

| PNS | Gravedad | Estado |
|---|---|---|
| PNS-01 | Crítica | PARCIAL |
| PNS-02 | Crítica | PARCIAL |
| PNS-03 | Crítica | CORREGIDO |
| PNS-04 | Crítica | CORREGIDO |
| PNS-05 | Crítica | CORREGIDO |
| PNS-06 | Crítica | CORREGIDO |
| PNS-07 | Crítica | PARCIAL |
| PNS-53 | Crítica | CORREGIDO |
| PNS-54 | Crítica | PARCIAL |
| PNS-08 | Alta | CORREGIDO |
| PNS-09 | Alta | CORREGIDO |
| PNS-10 | Alta | CORREGIDO |
| PNS-11 | Alta | CORREGIDO |
| PNS-12 | Alta | CORREGIDO |
| PNS-13 | Alta | CORREGIDO |
| PNS-14 | Alta | CORREGIDO |
| PNS-15 | Alta | CORREGIDO |
| PNS-16 | Alta | PARCIAL |
| PNS-17 | Alta | PARCIAL |
| PNS-18 | Alta | PARCIAL |
| PNS-19 | Alta | PARCIAL |
| PNS-20 | Alta | PARCIAL |
| PNS-21 | Alta | CORREGIDO |
| PNS-23 | Alta | SIN CAMBIOS |
| PNS-24 | Alta | PARCIAL |
| PNS-25 | Alta | CORREGIDO |
| PNS-26 | Alta | PARCIAL |
| PNS-27 | Alta | CORREGIDO |
| PNS-55 | Alta | PARCIAL |
| PNS-56 | Alta | CORREGIDO |
| PNS-57 | Alta | CORREGIDO |
| PNS-58 | Alta | CORREGIDO |
| PNS-59 | Alta | PARCIAL |
| PNS-60 | Alta | PARCIAL |
| PNS-80 | Alta | YA NO APLICA |
| PNS-22 | Media | PARCIAL |
| PNS-28 | Media | PARCIAL |
| PNS-29 | Media | PARCIAL |
| PNS-30 | Media | PARCIAL |
| PNS-31 | Media | SIN CAMBIOS |
| PNS-32 | Media | PARCIAL |
| PNS-33 | Media | SIN CAMBIOS |
| PNS-34 | Media | CORREGIDO |
| PNS-35 | Media | SIN CAMBIOS |
| PNS-36 | Media | PARCIAL |
| PNS-37 | Media | SIN CAMBIOS |
| PNS-38 | Media | SIN CAMBIOS |
| PNS-39 | Media | PARCIAL |
| PNS-40 | Media | PARCIAL |
| PNS-41 | Media | CORREGIDO |
| PNS-42 | Media | SIN CAMBIOS |
| PNS-61 | Media | PARCIAL |
| PNS-62 | Media | PARCIAL |
| PNS-63 | Media | CORREGIDO |
| PNS-64 | Media | PARCIAL |
| PNS-65 | Media | PARCIAL |
| PNS-66 | Media | SIN CAMBIOS |
| PNS-67 | Media | CORREGIDO |
| PNS-68 | Media | SIN CAMBIOS |
| PNS-70 | Media | SIN CAMBIOS |
| PNS-43 | Baja | PARCIAL |
| PNS-44 | Baja | YA NO APLICA |
| PNS-45 | Baja | CORREGIDO |
| PNS-46 | Baja | DUDOSO |
| PNS-47 | Baja | CORREGIDO |
| PNS-48 | Baja | CORREGIDO |
| PNS-49 | Baja | PARCIAL |
| PNS-50 | Baja | PARCIAL |
| PNS-51 | Baja | SIN CAMBIOS |
| PNS-52 | Baja | CORREGIDO |
| PNS-69 | Baja | CORREGIDO |
| PNS-71 | Baja | CORREGIDO |
| PNS-72 | Baja | PARCIAL |
| PNS-73 | Baja | SIN CAMBIOS |
| PNS-74 | Baja | PARCIAL |
| PNS-75 | Baja | CORREGIDO |
| PNS-76 | Baja | PARCIAL |
| PNS-77 | Baja | SIN CAMBIOS |
| PNS-78 | Baja | CORREGIDO |
| PNS-79 | Baja | CORREGIDO |
| PNS-81 | Alta | NUEVO |
| PNS-82 | Alta | NUEVO |
| PNS-83 | Alta | NUEVO |
| PNS-84 | Media | NUEVO |
| PNS-85 | Media | NUEVO |
| PNS-86 | Media | NUEVO |
| PNS-87 | Baja | NUEVO |
| PNS-88 | Baja | NUEVO |
| PNS-89 | Baja | NUEVO |

**Recuento:** CORREGIDO 32 · PARCIAL 32 · SIN CAMBIOS 13 · YA NO APLICA 2 · DUDOSO 1 (80 del
informe) · NUEVO 9 (total 89). Por gravedad:

| Gravedad | Corregido | Parcial | Sin cambios | Ya no aplica | Dudoso | Nuevo | Total |
|---|---|---|---|---|---|---|---|
| Crítica | 5 | 4 | 0 | 0 | 0 | 0 | 9 |
| Alta | 14 | 10 | 1 | 1 | 0 | 3 | 29 |
| Media | 4 | 12 | 9 | 0 | 0 | 3 | 28 |
| Baja | 9 | 6 | 3 | 1 | 1 | 3 | 23 |
| **Total** | **32** | **32** | **13** | **2** | **1** | **9** | **89** |

Restos que se repiten en varios parciales:
1. **El sandbox (caja A) bloquea por lista de nombres y no impide llamar a métodos privados**
   (`_metodo`). Afecta a PNS-07 y PNS-19 (y a lo que PNS-06 ejecuta al guardar).
2. **Un AI Administrator sin permisos de Ajustes sigue pudiendo conceder o quitar grupos de Odoo**
   (incluido `base.group_system`) mediante un plan confirmado. Afecta a PNS-01 y PNS-02.
3. **Los controles nuevos de URL (`remote_image`, `fetch_url`) dependen de la política de URL**: con
   la política `open`, el servidor descarga cualquier host público. Afecta a PNS-16 y PNS-59.

## Detalle: hallazgos críticos

### PNS-01 — Escalada a `base.group_system` por `apply_user_add_group`

- **Estado:** PARCIAL.
- **Evidencia:**
  - La vía del informe (RPC por cualquier interno o portal) está cerrada: `ai.system.action` ya no
    tiene métodos públicos. `apply_user_add_group` pasa a `_apply_user_add_group`
    (`pns_ai_mcp/models/ai_system_action.py:716`) y `call_kw` rechaza los nombres con `_`. Test
    nuevo: `pns_ai_mcp/tests/test_system_action.py:429-442`.
  - El único llamador es `ai.trusted.action._apply` (`pns_ai_mcp/models/ai_trusted_action.py:117-129`),
    que ahora comprueba los grupos del registro sobre el usuario real; `ai.trusted.action` también
    pasa sus métodos `apply`/`preview` a privados. Test: `test_system_action.py:444-456`.
  - **Resto:** el grupo exigido para `user.add_group` / `user.remove_group` es solo
    `group_ai_admin` (`pns_ai_mcp/data/trusted_actions_system.xml:84`), y `_apply_user_add_group`
    resuelve usuario y grupo en `sudo` (`ai_system_action.py:674-697`) y escribe con
    `pns_base/utils/compat.py:113-116`. Un AI Administrator que no sea administrador de Odoo puede,
    con un plan que él mismo confirma, darse `base.group_system`. El informe pedía exigir los dos
    grupos. El fabricante sí lo aplica ya en otro sitio (servidores `stdio`, ver PNS-09), lo que
    indica que no considera equivalentes a ambos administradores.
- **Prueba en el laboratorio:** sí.
  - Un interno y un usuario de portal llaman por RPC a `apply_user_add_group` y a
    `_apply_user_add_group`: deben recibir error de método inexistente o privado, sin cambio de grupos.
  - Un AI Administrator sin `base.group_system` pide en Chatboo añadirse un grupo de Ajustes y
    confirma la tarjeta: hoy se espera que funcione (resto abierto). Tras la corrección, debe
    rechazarse.

### PNS-02 — Resto de `apply_*` de `ai.system.action` sin control de permisos

- **Estado:** PARCIAL.
- **Evidencia:**
  - Todos los `apply_*` y `preview_*` son privados (`ai_system_action.py:334-480`, `:605`, `:631`,
    `:708-765`); ya no hay ningún método público en el modelo. Los `preview` se llaman desde
    `pns_ai_mcp/controllers/safe_plan.py:678-700` y los `apply` desde `safe_plan.py:822-843`, siempre a
    través de `ai.trusted.action._apply` con comprobación de grupo.
  - `module.update` se ejecuta ahora con el usuario real (`ai_system_action.py:639`,
    `with_user(self.env.uid)`), así que el core exige administrador de Odoo (detalle en PNS-24).
  - **Resto:** `_apply_user_remove_group` (`:747`) tiene el mismo límite que PNS-01: basta
    `group_ai_admin` para quitar grupos de Ajustes a un administrador de Odoo. Las acciones de vista
    y obligatoriedad (`view.*`, `field.set_required`) también se quedan en `group_ai_admin` con
    `sudo`, lo que parece una decisión de diseño aceptable.
- **Prueba en el laboratorio:** sí.
  - Interno y portal: `preview_module_update` y `preview_user_add_group` por RPC deben fallar (antes
    respondían).
  - AI Administrator sin Ajustes: proponer y confirmar un `module.update` debe fallar con error de
    acceso del core.
  - AI Administrator sin Ajustes: proponer y confirmar `user.remove_group` sobre un administrador de
    Odoo. Hoy se espera que funcione (resto abierto).

### PNS-03 — El propietario modifica `status` y `user_id` de su `ai.safe.operation`

- **Estado:** CORREGIDO.
- **Evidencia:**
  - `write` sobrescrito: cualquier escritura fuera de `sudo` lanza `AccessError`
    (`pns_ai_mcp/models/safe_operation.py:503-511`). Cubre todos los campos de control.
  - El ACL de internos pasa a `1,1,0,0`: sin creación directa por RPC
    (`pns_ai_mcp/security/ir.model.access.csv:5`). La regla por `user_id` se mantiene
    (`security/security.xml:93-101`).
  - Las transiciones legítimas escriben en `sudo` después de `_can_resolve()`: `confirm_by_user`
    (`:513-547`), `cancel_by_user` (`:1119-1134`) y `resolve_*`. `ai.safe.tools.wizard` (CRUD para
    internos) solo refresca y exporta (`wizard/safe_tools_wizard.py:13-16`).
- **Prueba en el laboratorio:** sí. Un interno, sobre su propia operación pendiente, intenta escribir
  `status`, `user_id` u `operation_data` por RPC: debe recibir `AccessError`. Confirmar desde la
  tarjeta debe seguir funcionando.

### PNS-04 — `resolve_*` y `confirm_by_user` ejecutan con un `confirmed_uid` elegido por quien llama

- **Estado:** CORREGIDO.
- **Evidencia:**
  - `confirm_by_user` (`safe_operation.py:513-526`), `resolve_confirm` (`:574-594`) y
    `resolve_execute` (`:709-727`) comprueban `_can_resolve()` (dueño o AI Administrator,
    `:308-316`) e ignoran el parámetro: `confirmed_uid = self.env.uid`.
    `resolve_confirm_and_execute` (`:831-863`) delega en ambos.
  - El controlador de la tarjeta ya no deja actuar al AI Administrator sobre operaciones ajenas
    (`controllers/verification_ui.py:16-35`).
  - La variante que sí recibe un uid, `_execute_plan_with_timeouts(op_id, uid, …)` (`:866`), es
    privada y no se puede llamar por RPC. Sí parece alcanzable desde el sandbox: ese resto se trata
    en PNS-07.
- **Prueba en el laboratorio:** sí. Un interno llama por RPC a `resolve_execute` con un
  `confirmed_uid` de administrador sobre su operación: la ejecución debe registrar como confirmador al
  propio interno (`confirmed_by_uid`), no al administrador. Sobre una operación ajena: `AccessError`.

### PNS-05 — `get_safe_operation_status` busca sin filtrar por usuario y ejecuta en `sudo`

- **Estado:** CORREGIDO.
- **Evidencia:** la herramienta pasa a llamarse `safe_plan_status` (`controllers/safe_plan.py:2351-2445`).
  - Busca en `sudo`, pero siempre con `('user_id', '=', env.uid)` (`:2383-2402`), también cuando se
    da el `verification_id`.
  - Ejecuta con el entorno del usuario y sin `sudo` (`:2412-2413`). Ese entorno sale de
    `request.env(user=…)`, que deja `su=False` (`controllers/controller_helpers.py:141-165`).
- **Prueba en el laboratorio:** sí. Con dos usuarios, B pide en el chat el estado de una operación de
  A dando su `verification_id`: debe responder que no hay operación. Para A, una operación confirmada
  se ejecuta respetando sus ACL (una escritura sobre un modelo sin permiso debe fallar).

### PNS-06 — El `code_body` de una skill se ejecuta al guardarla, sin solo lectura

- **Estado:** CORREGIDO (con el resto común del sandbox, ver PNS-07).
- **Evidencia:**
  - El smoke-run va dentro de un savepoint que siempre se revierte (`_run_and_undo`,
    `pns_ai_mcp/models/ai_skill.py:476-490`, usado en `:441-458`).
  - `skill_code_refusal` (`pns_ai_mcp/utils/skill_runtime.py`, función homónima) rechaza el código que
    el validador marca como de escritura. Se aplica al guardar (`ai_skill.py:426-428`) y en cada
    ejecución, así que también cubre filas guardadas antes del cambio.
  - El validador común bloquea `sudo`, `with_user`, `with_env` y `env`
    (`controllers/validators.py:201-203`). Todos los puntos de entrada (formulario, captura,
    importación) pasan por el constraint `_check_code_body_contract` (`ai_skill.py:391`).
  - Queda fuera del alcance del savepoint lo que abra su propio cursor y haga commit: es el resto
    descrito en PNS-07.
- **Prueba en el laboratorio:** sí. Un AI Writer guarda una skill cuyo código escribe en un registro
  (literal y con `sudo`): debe rechazarse al guardar. Una skill de solo lectura debe guardarse y
  ejecutarse. Tras guardarla, ningún dato debe haber cambiado.

### PNS-07 — `getattr` dinámico desde el sandbox a métodos que abren cursores con escritura

- **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:** `guarded_getattr` aplica ya la lista de métodos con efectos
    `RELAXAICODE_SIDE_EFFECT_METHODS` (`controllers/context_builder.py:123-155`;
    `controllers/validators.py:178-196`), y el AST la comprueba también en `getattr`, `attrgetter` y
    `methodcaller` (`validators.py:1160-1195`). El sandbox ya no llega al cursor ni al registro
    (`cr`, `_cr`, `pool`, `registry` en `validators.py:132`).
  - **Resto:** sigue siendo una lista negra de 15 nombres públicos, y el sandbox no bloquea los
    métodos de un guion bajo: el docstring de `guarded_getattr` dice expresamente que los permite.
    Quedan fuera de la lista métodos que abren cursores propios con commit:
    - `_execute_plan_with_timeouts(op_id, uid, …)` (`models/safe_operation.py:866-888`), que además
      **recibe el uid**;
    - `_retry_confirmed_not_executed` (`:974-1012`), `_claim_execute` (`:1136-1205`),
      `_release_execute_claim` (`:1207`), `_clear_stale_execute_claims` (`:1246-1260`) y
      `_heal_module_update_after_registry_reset` (`:1457-1556`);
    - el método público nuevo `ai.mcp.user.redeem_key_pin` (`models/mcp_user.py:820`), con cursores de
      superusuario en `models/key_pin_desk.py:176-177, 201-202` (ver PNS-83);
    - el método público nuevo `ai.skill.param.cache.remember_for_skill`
      (`models/ai_skill_param_cache.py:125-154`), que hace commit con un cursor de superusuario (ver
      PNS-85).

    También hay cursores propios en `ai_log.py`, `ai_change_journal.py`, `ai_provider.py`,
    `ai_agent.py`, `ai_context.py` y `ai_skill_param_cache.py` sin revisar uno a uno.
- **Prueba en el laboratorio:** sí, y es la más importante del bloque. Con un usuario con acceso al
  chat, comprobar si el código de relaxaicode puede invocar un método privado de un modelo
  (`env['ai.safe.operation']._…`). Si puede, lo que haya escrito un método con cursor propio debe
  verse persistido tras el turno, aunque la caja A es de solo lectura. Basta con observar si el
  sandbox permite o no la llamada; no hace falta un plan real.

### PNS-53 — XSS almacenado entre usuarios a través de `chatboo.session.messages`

- **Estado:** CORREGIDO.
- **Evidencia:**
  - Hay reglas de registro nuevas: `chatboo.session` queda limitada a `user_id = user` para todas las
    operaciones (`pns_ai_chatboo/security/security.xml:9-18`, cargado en el manifest `:32`). Ningún
    otro usuario puede escribir los mensajes de una sesión ajena.
  - El historial se pinta con `t-raw="_safeHtml(msg.content)"` y la vista previa del streaming con
    `t-raw="_safeHtml(state.streamingPreview)"` (`static/src/js/chatboo_component_v2.js:5909, 6034`).
    Ambos pasan por `sanitizeHtml` (`chatboo_component_v2.js:5249`;
    `static/src/js/chatboo_formatters.js:271-320`). Calidad del saneador: ver PNS-60.
- **Prueba en el laboratorio:** sí. Un interno intenta escribir `messages` en la sesión de otro por
  RPC: debe recibir `AccessError`. En su propia sesión, un mensaje con un manejador de evento o un
  enlace `javascript:` debe pintarse sin ellos (inspeccionar el DOM).

### PNS-54 — Cualquier XSS en el chat confirma y ejecuta operaciones de la Caja B sin el usuario

- **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:** en las rutas de la tarjeta, el AI Administrator ya no actúa sobre operaciones
    ajenas; solo el dueño (`pns_ai_mcp/controllers/verification_ui.py:16-35`). Las vías de XSS
    conocidas se reducen mucho (PNS-53, PNS-60, PNS-15).
  - **Resto:**
    - `/verification/confirm` y `/verification/execute` (`verification_ui.py:37-62`) siguen
      exigiendo solo sesión y propiedad. No hay token de un solo uso ligado a la interacción, ni
      reautenticación, ni espera en servidor para `danger_level = 'high'`.
    - Los métodos de modelo `resolve_confirm_and_execute` y `confirm_by_user` siguen siendo públicos
      por RPC para el dueño, así que un script en la página puede confirmar y ejecutar sin pasar por
      la tarjeta.
- **Prueba en el laboratorio:** sí, de comportamiento y sin cargas: con una operación `high`
  pendiente, comprobar si el servidor acepta `confirm` y `execute` en cuanto se crea la operación
  (sin espera) y sin ningún dato que solo produzca el clic en la tarjeta. Hoy se espera que sí.

## Detalle: hallazgos de gravedad alta

### PNS-08 — Credenciales de `ai.api.server` legibles por cualquier usuario interno

- **Estado:** CORREGIDO.
- **Evidencia:**
  - `auth_token`, `env_vars` y `config_json` llevan ya `groups='pns_ai_mcp.group_ai_admin'`
    (`pns_ai_mcp/models/external_server.py:193-195, 227-229, 255-257`; añadidos en este diff) y se
    declaran secretos (`:83`).
  - `ai.api.server.key` mantiene la regla por `user_id` (`security/security.xml:195-209`).
  - El sandbox bloquea esos nombres (`controllers/validators.py:158-169`). La exportación estándar
    vacía los campos secretos (`models/secret_native_export.py`).
- **Prueba en el laboratorio:** sí. Un interno sin grupos de IA lee `ai.api.server` por RPC
  (`read` y `search_read` con esos campos): debe recibir `AccessError` en los campos o no verlos.
  Exportar desde la lista estándar debe dejar vacías esas columnas.

### PNS-09 — Servidores MCP `stdio`: comando libre, entorno completo, sin timeout

- **Estado:** CORREGIDO.
- **Evidencia:**
  - Solo un administrador de Ajustes (o el superusuario) puede crear un servidor `stdio` o cambiar
    `command`, `command_args` o `env_vars`. Se comprueba sobre el usuario real, también en
    importaciones en `sudo` y al escribir vía `config_json`
    (`pns_ai_mcp/models/external_server.py:548, 567-587`).
  - El hijo recibe un entorno mínimo (`utils/mcp_client.py:15, 157`), la lectura tiene timeout
    (`:189-203`, `selectors`), `stderr` va a un fichero temporal y se cierra con
    terminate/kill (`:366-381`). El driver cierra en `finally` (`lib/api/drivers/mcp_driver.py:32-40,
    51-66, 75-81`).
  - `action_discover_tools` y `action_test_connection` exigen `ensure_ai_admin`
    (`external_server.py:1147, 1260`).
  - No hay lista de comandos permitidos; el fabricante optó por restringir quién configura, que es
    una alternativa razonable.
- **Prueba en el laboratorio:** sí. Un AI Administrator sin Ajustes intenta crear o editar un servidor
  `stdio` (formulario e importación): debe fallar. Un interno llama por RPC a `action_test_connection`:
  `AccessError`. Con un servidor `stdio` que no responde, la prueba de conexión debe terminar por
  timeout sin dejar procesos vivos.

### PNS-10 — `skip_hardcoded_restrictions` aceptado desde el contexto RPC

- **Estado:** CORREGIDO.
- **Evidencia:**
  - La bandera solo vale dentro de `sudo()` o para el superusuario (`factory_lock_open`,
    `pns_ai_mcp/utils/knowledge_ownership.py:38-49`). `call_kw` no puede producir ninguno de los dos.
  - La usan `write`/`unlink` de `ai.skill` (`models/ai_skill.py:775-812`) y de `ai.context`
    (`models/ai_context.py:1326-1350, 1446-1457`). Un no administrador sigue sin poder cambiar
    `owner_id`, `is_system` ni `context_type='core'`.
- **Prueba en el laboratorio:** sí. Un AI Writer escribe `owner_id=False` (o `context_type='core'`)
  en su contexto o skill enviando `skip_hardcoded_restrictions=True` en el contexto RPC: debe recibir
  `UserError`/`AccessError`.

### PNS-11 — Métodos públicos de `ai.skill` / `ai.context` que borran o escriben en `sudo`

- **Estado:** CORREGIDO.
- **Evidencia:**
  - `unlink_named_factory_skills` (`ai_skill.py:2184`), `unlink_retired_from_module` (`:2136`),
    `hide_unprefixed_slash_twins` (`:1432`), `reapply_source_module_prefixes` (`:1322`) y
    `sync_slash_hidden_from_field` (`:547`) llaman al principio a `_require_bootstrap()`
    (`:1419-1429`), que exige `env.su` o superusuario.
  - `record_context_usage` pasa a ser privado (`ai_context.py:1213`).
  - Las importaciones públicas de `ai.context` exigen `ensure_ai_admin` (`:1166`, `:1654`, `:2445`,
    `:2615`, `:2662`, `:2739`).
  - Test: `tests/test_system_action.py:439-442`.
- **Prueba en el laboratorio:** sí. Un interno y un usuario de portal repiten la llamada del informe
  (`unlink_named_factory_skills`): debe recibir `AccessError`. Lo mismo con los otros cuatro métodos.

### PNS-12 — Contextos privados de otros usuarios expuestos

- **Estado:** CORREGIDO.
- **Evidencia:**
  - `get_listable_for_mcp`, `get_context_for_country`, `get_discovery_entries` y
    `get_discovery_indexed_codes` filtran con `ownership_read_domain()` (`ai_context.py:345-346,
    570-610, 658-668, 869-945`).
  - El dominio usa `env.user`, que en Odoo 14 sigue siendo el usuario real dentro de `sudo`, así que
    las lecturas en `sudo` del motor (`utils/agent_engine.py:1023, 1029-1038, 1052`) y de
    `prompts/get` (`controllers/main.py`, `_mcp_prompts_get`, `env = self._get_mcp_env().sudo()`)
    quedan filtradas.
- **Prueba en el laboratorio:** sí. Con dos usuarios, A crea un contexto privado de dominio. B no
  debe verlo en `prompts/list` / `prompts/get` del MCP, y su contenido no debe inyectarse en los
  turnos de B que activen ese dominio.

### PNS-13 — `/mcp/message` no revalida clave ni usuario; sesiones sin caducidad

- **Estado:** CORREGIDO.
- **Evidencia:**
  - En cada POST se busca otra vez la clave por hash y se exige usuario activo, igual al de la sesión
    y sin la denegación conversacional; si falla, se cierra la sesión
    (`pns_ai_mcp/controllers/main.py:650-665`).
  - La variante por agente delega en el mismo método (`:284-286`).
  - `cleanup_expired` (1 h sin actividad) se llama al crear cada sesión
    (`utils/session_store.py:127, 198-213`).
- **Prueba en el laboratorio:** sí. Con una sesión SSE abierta, revocar la clave o archivar al
  usuario: el siguiente mensaje debe devolver 401 y la sesión debe cerrarse.

### PNS-14 — Cachés legibles por todos, caché de `api_call` sin usuario, `ai.safe.choice` sin reglas

- **Estado:** CORREGIDO.
- **Evidencia:**
  - Se quita la lectura de `ai.fetch.cache` a internos (solo admin, `security/ir.model.access.csv:50`).
  - `ai.api.result.cache` tiene regla por `create_uid` (`security/security.xml:173-191`).
  - La clave de caché incluye el uid (`utils/api_call_result.py:14-22`,
    `models/api_result_cache.py:83-84`, `controllers/safe_plan.py:1810-1811`).
  - `ai.safe.choice` tiene regla por `user_id` (`security/security.xml:161-170`).
  - Observación: la clave de `ai.fetch.cache` sigue sin usuario (URL, método y cuerpo), pero solo la
    lee el administrador y `fetch_url` no lleva credenciales del usuario.
- **Prueba en el laboratorio:** sí. Un interno sin grupos no lee `ai.fetch.cache`; solo ve sus filas
  de `ai.api.result.cache` y `ai.safe.choice`. La misma `api_call` hecha por A y luego por B en menos
  de 10 minutos no debe servir a B la respuesta de A.

### PNS-15 — HTML sin sanear (XSS)

- **Estado:** CORREGIDO.
- **Evidencia, punto por punto:**
  - Celdas e imágenes base64 escapadas (`pns_ai_mcp/utils/relaxaicode_render.py:1010-1036`). Enlaces
    de mapa con `_safe_card_href` (`:733`) y URL de registro construida con id entero y modelo
    escapado (`:679-702`).
  - Showdown se elimina de `pns_ai_mcp`.
  - `pns_html_readonly_widget_v14.js:13-40`: limpieza en un `<template>` inerte (sin `script`,
    `iframe`, `on*`, ni esquemas `javascript:`/`vbscript:`/`data:` salvo `data:image`).
  - `context_stats_wizard.py`: el campo pasa a calculado (no escribible) y escapa título y valores
    (`:6, 37-38, 289-291`).
  - `pns_base/models/operation_report_wizard.py:38-51`: `html_sanitize` en `create`/`write` fuera de
    `sudo`.
  - La prosa del LLM y el `author_html` de skills no se sanean en el servidor, pero el cliente de
    Chatboo los sanea en el único punto de inserción (ver PNS-60).
- **Prueba en el laboratorio:** sí. Crear por RPC un `pns.export.file.wizard` con HTML activo en
  `result_html` y abrirlo con otro usuario: el HTML debe llegar saneado. Mostrar en el chat un
  registro cuyo nombre contenga etiquetas: deben verse como texto.

### PNS-16 — Prompt injection sin defensas combinada con auto-confirmación

- **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:**
    - El registro en pantalla va como mensaje `user` delimitado y marcado como datos
      (`pns_ai_mcp/utils/agent_engine.py:2766-2777`).
    - El turno se marca como no confiable si trae datos de pantalla o tras el resultado de
      cualquier herramienta (`:2337-2339`, `:3958-3973`). En ese caso no se auto-confirma
      `fetch_url` ni un `api_call` que no sea de solo lectura (`controllers/safe_plan.py:394-431`).
    - Las herramientas se filtran por grupos del usuario (`controllers/mcp_decorators.py:345-348`,
      `utils/agent_engine.py:1345-1360`).
  - **Resto:**
    - El código y las filas de la consulta del turno anterior se reinyectan con rol `system`
      (`agent_engine.py:2712-2760`, `[DATOS REUTILIZABLES]` y `[CONSULTA REUTILIZABLE]`). La marca
      de no confiable se reinicia en cada turno, así que un contenido inducido en un turno vuelve con
      autoridad de sistema en el siguiente.
    - Con la política de URL `open`, al confirmar se sigue añadiendo el dominio a la lista blanca
      (`safe_plan.py:749-754`).
- **Prueba en el laboratorio:** sí. Con un registro abierto cuyo texto pida al asistente consultar
  una URL externa: no debe haber auto-confirmación (debe aparecer la tarjeta), tanto con política
  restringida como `open`. Repetir pidiéndolo en el turno siguiente (reutilizando la consulta):
  observar si se auto-confirma.

### PNS-17 — `fetch_url` sin protección SSRF ni límite de tamaño

- **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:**
    - `non_public_host_error` resuelve el nombre y rechaza cualquier dirección no global
      (`pns_ai_mcp/utils/fetch_url_safe.py:26-44`).
    - Las redirecciones se siguen salto a salto, cada uno validado (esquema, host público y
      política de URL; máximo 5), y el cuerpo se lee con `stream=True` hasta 20 MB
      (`controllers/safe_plan.py:1528-1585`; `fetch_url_safe.py:22-23`).
    - OpenAPI ya no deja que la especificación elija otro host: o `base_url` configurado o el mismo
      host de la especificación (`lib/api/drivers/openapi_driver.py:270-291`).
    - El nuevo `/pns_ai_mcp/remote_image` aplica las mismas comprobaciones (inventario,
      `utils/remote_image.py:24-68`).
  - **Resto (puntos de entrada):**
    - El generador OpenAPI nuevo (`services/openapi_spec_generator.py:579-610`, solo administrador)
      usa `requests.get`, que sigue redirecciones sin `non_public_host_error`. Tiene número propio:
      PNS-86.
    - El driver OpenAPI sigue redirecciones con las cabeceras de autenticación propias y sin límite
      de tamaño (`openapi_driver.py:74-81, 387-394`).
    - Entre la comprobación DNS y la conexión hay una segunda resolución, que no protege frente a
      DNS rebinding (menor).
- **Prueba en el laboratorio:** sí. `fetch_url` a `localhost`, a la IP de la base de datos y a una URL
  pública que redirige a una IP privada: todas rechazadas. Una descarga de más de 20 MB: rechazada.
  Con el asistente de OpenAPI (como administrador), una URL de documentación que redirige a un host
  interno: hoy se espera que la siga.

### PNS-18 — Datos hacia el proveedor LLM sin control por modelo, campo o empresa

- **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:** nuevo campo `no_external_failover` en `ai.provider`
    (`pns_ai_mcp/models/ai_provider.py:359-364`), aplicado en la cadena de proveedores
    (`models/ai_execution_engine.py:189, 243-254`).
  - **Sin cambios:**
    - No hay lista de modelos o campos excluidos ni anonimización.
    - No hay tope de filas hacia el LLM distinto del de la herramienta:
      `RELAXAICODE_MAX_RESULT_ROWS = 50000` (`controllers/tools_relaxaicode.py:31`).
- **Prueba en el laboratorio:** sí (funcional). Con un proveedor local marcado `No external failover`
  seguido de uno externo, forzar el fallo del local: el turno debe terminar en error sin llamar al
  externo (comprobar en `ai.log`).

### PNS-19 — Secretos accesibles desde el sandbox mediante `sudo()`

- **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:**
    - `GuardedSandboxEnv` y el validador bloquean `sudo`, `with_user`, `with_env`, `env`, `_env` y
      `env(user=…, su=…)` (`pns_ai_mcp/controllers/context_builder.py:62-110`;
      `controllers/validators.py:201-209`).
    - También bloquean el acceso al cursor (`cr`, `_cr`, `pool`, `registry`, `validators.py:132`)
      y los campos secretos de `ai.api.server` (`:158-169`).
  - **Resto:**
    - Los métodos privados no están bloqueados (ver PNS-07), y
      `ai.provider._api_key_for_inference()` devuelve la clave del proveedor leída en `sudo`
      (`models/ai_provider.py:200-208`). No está en ninguna lista negra.
    - Además, no se bloquean por modelo los secretos que el propio usuario puede leer
      (`ir.config_parameter` para un administrador), que el motor reenviaría al proveedor.
- **Prueba en el laboratorio:** sí, sin redactar el código. Con un usuario de chat sin grupos de IA,
  comprobar si el sandbox permite invocar un método privado de `ai.provider`. El resultado esperado
  tras la corrección es un error del sandbox; si devuelve un valor, el resto está confirmado.

### PNS-20 — Copias de configuración con secretos e importación que sobrescribe

- **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:**
    - Exportación sin secretos por defecto (`pns_ai_mcp/utils/config_backup.py:93-117`), con
      `config_json` tratado como secreto (`models/external_server.py:83`) y el hash MCP solo con
      secretos (`config_backup.py:366-370`).
    - Desde Ajustes se pregunta (`pns.export.secrets.wizard`; `models/res_config_settings.py:204-207`).
    - `settings_io` pasa a `include_secrets=False` (`pns_base/utils/settings_io.py:366`).
    - Los adjuntos de exportación se marcan y se purgan a las 24 h (`pns_base/utils/portable_io.py:345-360`,
      `pns_base/models/ir_attachment.py:22-43`).
    - Importar un servidor `stdio` exige administrador de Ajustes (PNS-09).
  - **Resto:**
    - La importación sigue sobrescribiendo por defecto (`wizard/config_backup_wizard.py:41-46`,
      `replace_existing` por defecto `True`).
    - No hay resumen de cambios antes de aplicar (`:48-63` importa directamente). Un fichero ajeno
      puede seguir cambiando proveedores, endpoints o la política de URL `open`.
- **Prueba en el laboratorio:** sí. Exportar sin marcar secretos y revisar que el JSON no contiene
  claves, tokens, `config_json` con credenciales ni hashes. El adjunto debe desaparecer tras el cron
  (o comprobar su marca). Importar una copia que cambie la política de URL: hoy se aplica sin
  confirmación previa.

### PNS-21 — Exportaciones del chat descargables sin sesión; URL con token hacia el LLM

- **Estado:** CORREGIDO.
- **Evidencia:**
  - `/pns_ai_mcp/session_file/…` pasa a `auth='user'` y solo entrega el adjunto al creador, a un
    administrador de Ajustes o a quien pueda leer el registro al que cuelga
    (`pns_ai_mcp/controllers/session_file.py:20-44`). Responde con `nosniff`, y los SVG se sanean.
  - La URL ya no lleva `access_token` (`utils/session_download.py:99-106`).
  - El adjunto se crea con el uid del usuario (`:373-393, 449-454`), así que la comprobación de
    creador funciona.
  - Observación: estos adjuntos no llevan `EXPORT_MARK` y no entran en la purga de 24 h. Además, ver
    en PNS-55 el método nuevo que permite engancharlos a otra sesión.
- **Prueba en el laboratorio:** sí. Abrir la URL de una descarga del chat sin sesión (debe pedir
  login) y con otro usuario interno (debe dar 404).

### PNS-23 — Skills activadas sin revisión

- **Estado:** SIN CAMBIOS.
- **Evidencia:**
  - La captura sigue creando la skill activa si viene de Chatboo (`'active': bool(self.from_chatboo)`,
    `pns_ai_mcp/wizard/skill_capture_wizard.py:834`), y `from_chatboo` se sigue tomando del contexto
    (`:196-197`). El docstring de cabecera dice «DRAFT (active=False)», pero no es lo que hace.
  - La importación ZIP y desde ficheros mantiene `active` del fichero, `True` por defecto
    (`models/ai_skill.py:1782, 1998-2013`).
  - Los atenuantes ya existían en la versión analizada: la propiedad del autor (`apply_create_ownership`,
    `:756`), la regla «módulo o propias» (`security/security.xml:117-125`) y `ensure_ai_admin` en las
    importaciones.
- **Prueba en el laboratorio:** sí (funcional). Capturar una skill desde Chatboo como AI Writer:
  observar si queda activa y quién la ve en el menú `/` (otro usuario, un administrador).

### PNS-24 — `module.update`: `sudo`, commit y lista de vetos insuficiente

- **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:**
    - La operación se ejecuta con el usuario real, sin `sudo`, y el core vuelve a exigir
      administrador de Odoo (`pns_ai_mcp/models/ai_system_action.py:637-641`).
    - Se rechaza cualquier desinstalación cuya cascada arrastre a `pns_ai_mcp`, lo que cubre `mail`,
      `bus` y `pns_base` (`_uninstall_cascade`, `:588-603`). La vista previa enumera la cascada
      (`:605-629`).
  - **Resto:**
    - `button_immediate_*` sigue haciendo commit y recargando el registro. El fabricante lo
      gestiona con timeouts y una «curación» posterior (`models/safe_operation.py:1370-1378`,
      `utils/module_update_heal.py`), pero no impide combinar `module.update` con otros pasos en el
      mismo plan: la atomicidad no se garantiza en ese caso.
- **Prueba en el laboratorio:** sí. AI Administrator sin Ajustes: `module.update` debe fallar.
  Administrador: desinstalar `mail` debe rechazarse con el mensaje de cascada. Un plan con un paso
  de escritura y un `module.update` que falle después: comprobar si la escritura queda guardada.

### PNS-25 — Failover tras ejecutar herramientas: posible doble ejecución

- **Estado:** CORREGIDO.
- **Evidencia:**
  - Si un plan se auto-confirma y ejecuta en el turno, se marca `_turn_effects_done`
    (`pns_ai_mcp/utils/agent_engine.py:4325-4327`). Si después falla el proveedor, el turno termina
    con un aviso y no pasa al siguiente (`:2389-2395`).
  - La ejecución manual es idempotente por `executed` y por el claim atómico
    (`models/safe_operation.py:1136-1205`).
- **Prueba en el laboratorio:** opcional (difícil de provocar). Con dos proveedores y el primero
  forzado a fallar tras una `fetch_url` auto-confirmada: la URL debe pedirse una sola vez (ver
  `ai.log`).

### PNS-26 — Commits fuera del flujo transaccional

- **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:** si una herramienta MCP lanza excepción, se hace `rollback` del cursor de la
    petición antes del commit final (`pns_ai_mcp/controllers/main.py:1410-1420`).
  - **Resto:**
    - Siguen los `commit()` sobre el cursor del llamador en `safe_operation.py`
      (`resolve_confirm_and_execute` `:850, 859`; `execute_plan_now` `:1366, 1410`;
      `_clear_stale_execute_claims` `:1260`), ahora documentados como intencionados.
    - El total de `.commit()` en `models`, `controllers`, `utils` y `lib` de `pns_ai_mcp` es el
      mismo que en la versión analizada (30).
    - No consta un rollback equivalente en la ruta del motor de Chatboo (`AgentEngine`) cuando
      falla una herramienta.
- **Prueba en el laboratorio:** sí. Una herramienta que escribe y luego falla, llamada por `/mcp` y
  por Chatboo: comprobar en ambos casos que no queda nada escrito.

### PNS-27 — jsPDF 2.5.1 y SheetJS 0.18.5 con CVE conocidas en todo el backend

- **Estado:** CORREGIDO.
- **Evidencia:**
  - Se eliminan `pns_ai_mcp/static/src/js/jspdf.umd.min.js`, `pns_ai_mcp/static/src/js/xlsx.full.min.js`
    y `pns_ai_chatboo/static/src/js/xlsx.full.min.js`.
  - Queda una sola copia de jsPDF, versión 4.2.1 (cabecera de
    `pns_ai_chatboo/static/src/js/jspdf.umd.min.js`), posterior a las versiones que corrigen las dos
    CVE citadas. No he revisado avisos publicados para 4.2.1.
  - Solo la carga Chatboo, que la usa (`pns_ai_chatboo/views/assets.xml:19-20`), aunque sigue en
    `web.assets_backend` (Chatboo está en todo el backend).
  - `jspdf.plugin.autotable.min.js` no se ha revisado.
- **Prueba en el laboratorio:** sí (funcional). Exportar a PDF y a XLSX desde Chatboo: ambas deben
  seguir funcionando con las librerías nuevas.

### PNS-55 — Sin aislamiento entre usuarios en `chatboo.session` y `chatboo.async.request`

- **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:**
    - Reglas por `user_id` en ambos modelos (`pns_ai_chatboo/security/security.xml:9-29`).
    - En los jobs, `create` fija `user_id` y exige una sesión propia, y `write` no deja cambiar
      `session_id` ni `user_id` fuera de `sudo` (`models/chatboo_async_request.py:200-224`).
    - `read_progress` desaparece (PNS-80).
    - `sandbox_helpers` comprueba al dueño (`models/chatboo_session.py:748-749`), y
      `prepare_skill_capture_action` / `prepare_skill_edit_action` también (`:1071, 1229`).
    - `unlink` borra jobs y adjuntos en `sudo` antes de `super().unlink()`, pero sobre una sesión
      ajena la regla hace fallar la transacción entera.
  - **Resto:**
    - El ACL de jobs sigue con `write` y `create` para el usuario
      (`security/ir.model.access.csv:3`, `1,1,1,0`; el informe pedía solo lectura).
    - **Punto de entrada nuevo:** `chatboo.session.claim_turn_file_chips` (público, nuevo en esta
      versión, `models/chatboo_session.py:415-441`). Sobre la sesión propia, engancha en `sudo`
      cualquier `ir.attachment` sin `res_model`, cuyo id llegue en la lista o en la URL del chip,
      sin comprobar quién lo creó. Después, `_may_read` de `session_file` lo entrega porque cuelga de
      una sesión del llamador. Los adjuntos sin `res_model` incluyen las descargas del chat de otros
      usuarios (PNS-21) y las exportaciones de `pns_base` sin modelo (que pueden llevar secretos,
      `pns_base/utils/portable_io.py:345-360`). Los ids son secuenciales. Tiene número propio: PNS-82.
    - `recover_orphan_download_chips(messages=…)` (`:521-552`) lista en `sudo` nombres y tamaños de
      adjuntos de una sesión dada sin leerla si se le pasan los mensajes (fuga menor; la descarga sí
      se deniega).
- **Prueba en el laboratorio:** sí.
  - Un interno lee, escribe y borra por RPC la sesión y los jobs de otro: `AccessError`.
  - Para `claim_turn_file_chips`: A genera una descarga en el chat; B, sobre su propia sesión, llama
    al método con el id del adjunto de A y luego intenta descargarlo. Tras la corrección debe
    fallar; hoy se espera que funcione.

### PNS-56 — Inyección en el siguiente turno de otro usuario mediante el estado de su sesión

- **Estado:** CORREGIDO (la vía entre usuarios).
- **Evidencia:**
  - La vía del hallazgo dependía de PNS-55. Con la regla por `user_id`
    (`pns_ai_chatboo/security/security.xml:9-18`), nadie más que el dueño escribe `last_query_code`,
    `last_query_data`, `active_skill_*` ni `messages`. Las escrituras del servidor se hacen en
    `sudo` sobre la sesión del job.
  - Lo que se reinyecta sigue tratándose como instrucción de sistema (`[CONSULTA REUTILIZABLE]`,
    `pns_ai_mcp/utils/agent_engine.py:2712-2760`), pero eso ya es el resto de PNS-16, no una vía
    entre usuarios.
- **Prueba en el laboratorio:** sí. B intenta escribir `last_query_code` en la sesión de A por RPC:
  `AccessError`.

### PNS-57 — Turnos lanzados por RPC sin clave MCP y sobre sesiones ajenas

- **Estado:** CORREGIDO.
- **Evidencia:**
  - `spawn` pasa a `_spawn` (privado, `pns_ai_chatboo/models/chatboo_async_request.py:252`). Solo lo
    llama `/chatboo/stream` (`controllers/chatboo.py:818-825`) después de
    `_user_may_use_chatboo`.
  - `create` fija `user_id` y exige sesión propia, y `write` bloquea los campos de dueño (`:200-224`).
  - El reclaim y el cron solo cierran jobs atascados; no los ejecutan (`:2009-2090, 2144-2160`).
- **Prueba en el laboratorio:** sí. Un interno sin clave MCP crea un job por RPC sobre la sesión de
  otro (`AccessError`) y sobre la suya, e intenta lanzarlo (`spawn`/`_spawn`): no debe ejecutarse
  ningún turno ni consumirse proveedor.

### PNS-58 — `/chatboo/stream` sin CSRF, con `cors='*'` y cuerpo `text/plain`

- **Estado:** CORREGIDO.
- **Evidencia:** la ruta pasa a `type='http', auth='user', methods=['POST']`, con CSRF por defecto y
  sin `cors` (`pns_ai_chatboo/controllers/chatboo.py:717`). El cliente envía `csrf_token`
  (inventario, `chatboo_component_v2.js:2564-2566`). Una petición entre orígenes sin token la
  rechaza Odoo, sea cual sea el `Content-Type`.
- **Prueba en el laboratorio:** sí. Un POST a `/chatboo/stream` con la cookie de sesión y sin
  `csrf_token` debe rechazarse (400/403). Desde el chat debe seguir funcionando.

### PNS-59 — Salida de datos sin clic mediante imágenes externas en las respuestas

- **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:** el saneador del cliente quita `src`, `href` no de enlace y `url()` de CSS que no
    sean del propio origen (`pns_ai_chatboo/static/src/js/chatboo_formatters.js:156-221`). Las
    imágenes de otro origen se reescriben a `/pns_ai_mcp/remote_image?url=…` (`:222-260`), así que el
    navegador ya no contacta con terceros.
  - **Resto:** el servidor descarga esa URL si el host está en la lista blanca con entrada `web` o si
    la política de URL es `open` (`pns_ai_mcp/models/url_whitelist.py:168-176`, inventario). Con la
    política `open`, una imagen inducida por prompt injection con datos en la URL sigue saliendo sin
    clic, ahora desde el servidor. Con la política restringida, solo hacia hosts permitidos.
- **Prueba en el laboratorio:** sí. Una respuesta que incluya una imagen de un host externo no
  permitido debe mostrarse como enlace o texto alternativo, sin petición al exterior (ver el log
  del servidor y la pestaña de red). Repetir con la política `open`: hoy se espera que el servidor
  haga la petición.

### PNS-60 — HTML del asistente insertado sin sanear en el cliente de Chatboo

- **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:**
    - Hay un saneador (`sanitizeHtml`, `chatboo_formatters.js:111-320`): análisis en un documento
      inerte; fuera `script`, `style`, `iframe`, `form`, `math`, animaciones SVG, etc.; fuera
      atributos `on*`, `srcdoc`, `srcset`, `action`…; enlaces solo `http`, `https`, `mailto`, `tel` y
      `blob` propio.
    - Se aplica al final de `formatContent` (`:1141-1147`), es decir, después de Showdown y de
      `enhanceHtmlProse`, así que deshacer el escape ya no reabre el HTML.
    - También se aplica en los dos `t-raw` (`chatboo_component_v2.js:5909, 6034`) y en todas las
      asignaciones `innerHTML` de `chatboo_export.js` (`:78, 724, 806, 1466, 2179, 2340, 2484, 2833,
      3087`).
    - La tabla de estadísticas escapa el nombre de serie (`chatboo_charts.js:2315`).
    - El acuse de verificación se guarda como mensaje y se pinta por el `t-raw` saneado.
  - **Resto:**
    - `escapeHtml` sigue sin escapar comillas (`chatboo_formatters.js:105-109`) y se usa en
      atributos (`chatboo_component_v2.js:3464`, `data-slash-code`). El informe lo citaba
      expresamente.
    - El saneador es una lista negra de etiquetas, no una lista blanca.
    - Showdown 2.1.0 sigue incluido (`pns_ai_chatboo/static/src/js/showdown.js`), aunque su salida
      pasa ahora por el saneador.
- **Prueba en el laboratorio:** sí. Pedir al asistente que repita texto con etiquetas activas
  (manejadores de evento, enlaces con esquemas no permitidos, SVG): inspeccionar el DOM del mensaje
  durante el streaming, tras recargar y en la exportación a PDF/Word. No deben aparecer manejadores
  ni esquemas fuera de la lista.

### PNS-80 — `read_progress` devuelve el progreso y la respuesta de cualquier turno a cualquier usuario

- **Estado:** YA NO APLICA.
- **Evidencia:**
  - `read_progress` ya no existe en `pns_ai_chatboo` (ni en Python ni en JS).
  - El progreso se entrega en la propia respuesta de `/chatboo/stream`, que lee por SQL solo el job
    que acaba de crear en esa petición (`controllers/chatboo.py:818-860`).
  - El sondeo tras recargar (`/chatboo/async/poll`, `:467-524`) filtra por `user_id = uid`, y los
    jobs tienen regla por dueño.
- **Prueba en el laboratorio:** sí (rápida). Interno y portal llaman por RPC a
  `chatboo.async.request.read_progress`: debe fallar por método inexistente. `/chatboo/async/poll`
  con el `session_id` de otro usuario debe devolver listas vacías.

## Medios y bajos

Mismo criterio que los bloques anteriores. La gravedad va en la línea de estado; PNS-22 es Media
(revisión del informe) y PNS-69, Baja. Ninguno de estos restos coincide con los tres «Restos que se
repiten»: cuando un resto toca el sandbox o la Caja B, se indica en el propio hallazgo.

### PNS-22 — `is_write` no se aplica de forma centralizada; falta la puerta en el `DummyController`

- **Gravedad:** Media · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:** el `DummyController` del motor comprueba ahora `group_ai_writer` en
    `_get_env_for_operation('write')` (`pns_ai_mcp/utils/agent_engine.py:3838-3866`). La
    herramienta del informe (`clean_system`) desaparece con `controllers/tools_system.py`.
  - **Resto:** `tools/call` sigue decidiendo la puerta por una lista de dos nombres que no son
    herramientas registradas (`controllers/main.py:1295-1311`). La marca `is_write` solo se lee
    después de la puerta (`:1380-1383`) y no tiene efecto. Hoy la única herramienta con
    `is_write=True` es `relaxaicode` (`controllers/tools_relaxaicode.py:1671`), que decide dentro;
    una herramienta de escritura futura dependerá otra vez de pedir el entorno correcto.
- **Prueba en el laboratorio:** sí. Un usuario de chat sin AI Writer pide una operación de
  escritura por Chatboo y por `/mcp`: debe rechazarse en ambos casos.

### PNS-28 — CORS `*`, sin validación de `Origin` y registro de peticiones no autenticadas

- **Gravedad:** Media · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:** `_log_mcp_operation` ya no guarda en `ai.log` las peticiones sin usuario MCP
    (`pns_ai_mcp/controllers/main.py:107-114`). Las otras escrituras en `ai.log` del controlador
    pasan por ese método.
  - **Resto:** todas las rutas `/mcp*` siguen con `cors='*'` y cabecera
    `Access-Control-Allow-Origin: *` (`main.py:240-295, 487, 599, 693, 800`), y no hay validación de
    `Origin`.
- **Prueba en el laboratorio:** sí. Un POST a `/mcp` sin clave no debe crear filas en `ai.log`. Un
  POST con `Origin` ajeno y clave válida: hoy se espera que se atienda.

### PNS-29 — Sin topes de gasto; tokens no contabilizados en varias rutas

- **Gravedad:** Media · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:** desaparece el respaldo síncrono que descartaba `usage`. Las llamadas cortas
    devuelven y registran `usage` (`llm_json_completion_result`,
    `pns_ai_mcp/utils/agent_engine.py:92-153`, con `inference_audit`), y el uso lateral del turno
    se suma al total (`:579-596`, `:1516-1536`). `normalize_usage` recoge los tokens leídos de caché
    (`utils/llm_usage.py:83-112`).
  - **Resto:**
    - No hay tope de gasto, de tokens ni de turnos (sin parámetros ni campos para ello).
    - `normalize_usage` no recoge `cache_creation_input_tokens` de Anthropic (`llm_usage.py:94-99`),
      así que la escritura en caché sigue sin contarse.
- **Prueba en el laboratorio:** sí (funcional). Un turno con proveedor Anthropic y caché de prompt:
  comparar los tokens de `ai.log` con los de la consola del proveedor.

### PNS-30 — `ai.log`: sin retención, filas modificables, auditoría borrada en cascada

- **Gravedad:** Media · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:**
    - `user_id` pasa a `ondelete='set null'` (`pns_ai_mcp/models/ai_log.py:49-55`).
    - ACL de AI Administrator `1,0,0,1` (`security/ir.model.access.csv:41`).
    - Cron diario de retención, 30 días por defecto (`data/ai_log_cron.xml`;
      `models/ai_log.py:893-912`).
  - **Resto (punto de entrada no citado en el informe, ya existía):** `create_log_entry` sigue
    siendo un método público `@api.model` (`ai_log.py:668-669`) que crea la fila con un cursor
    propio como `SUPERUSER_ID` (`:706-708`) y con el `user_id` que recibe. Cualquier usuario que
    pueda llamar por RPC puede añadir filas de auditoría a nombre de otro. Quitar `create` del ACL
    no lo cubre.
  - Observación: el tope de 100 000 caracteres por campo sigue (`:739`).
  - Relacionado: la retención nueva está activa por defecto y purga al actualizar (PNS-87).
- **Prueba en el laboratorio:** sí. Un interno sin grupos de IA llama por RPC a
  `ai.log.create_log_entry` con el `user_id` de otro usuario: tras la corrección debe fallar; hoy se
  espera que cree la fila. Un AI Administrator intenta `write` sobre una fila: `AccessError`.

### PNS-31 — Parches globales sobre Odoo fuera del ámbito PNS

- **Gravedad:** Media · **Estado:** SIN CAMBIOS.
- **Evidencia:**
  - `http_patch.py` y `models/ir_model_fields_selection.py` no cambian. El primero ya estaba acotado
    a las rutas `/mcp` (`http_patch.py:13-35`); el backport de `_process_ondelete` sigue siendo
    global (`ir_model_fields_selection.py:23-43`).
  - `set_values` de Ajustes reescribe la política de URL en cada guardado
    (`models/res_config_settings.py:297-303`).
  - Los `include` del cliente web en `pns_ai_mcp` pasan de 11 a 19. Hay uno nuevo sobre
    `WebClient` que arranca el sondeo del bus para todo usuario del backend
    (`static/src/js/key_pin_desk_v14.js:349-364`). Siguen el oyente global de clics y el
    `MutationObserver` de todo el documento (`ai_agent_origin_filter_v14.js:330, 375-379`), y se
    añaden dos oyentes globales más (`key_pin_desk_v14.js:285, 301`).
- **Prueba en el laboratorio:** no (revisión de código).

### PNS-32 — Sincronización de fábrica: sobrescribe ediciones y borra carpetas en disco

- **Gravedad:** Media · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:** ya no hay `shutil.rmtree` ni otro borrado de archivos en el módulo. El retiro
    de los contextos `self` solo toca registros de base de datos
    (`pns_ai_mcp/models/ai_context.py:1490-1540`).
  - **Resto:**
    - La sincronización sigue en `_register_hook` (`ai_context.py:413-429`) y sigue importando con
      `replace_existing=True` (`hooks.py:183-219`). Solo respeta las filas con dueño; un contexto de
      fábrica editado por el administrador se sobrescribe al cambiar el sello.
    - No hay bloqueo entre workers (`maybe_sync_factory_knowledge`, `hooks.py:243-260`).
- **Prueba en el laboratorio:** sí. Editar un contexto de fábrica, actualizar el módulo y comprobar
  si la edición se pierde. Revisar que no desaparece ninguna carpeta del addons path.

### PNS-33 — Claves MCP: query string, prefijo en log, hash sin sal, sin caducidad

- **Gravedad:** Media · **Estado:** SIN CAMBIOS.
- **Evidencia:**
  - Sigue aceptándose `?api_key=` (`pns_ai_mcp/controllers/main.py:421, 716, 867`).
  - Se registran los 10 primeros caracteres a nivel INFO (`:863, 869`).
  - SHA-256 sin sal (`utils/api_key.py:35-48`, archivo sin cambios) y sin campo de caducidad.
  - Relacionado: el PIN de entrega guarda el PIN y la clave en claro en la base de datos (PNS-84).
- **Prueba en el laboratorio:** no (revisión de código).

### PNS-34 — Un test hace commit de una clave MCP predecible para el administrador

- **Gravedad:** Media · **Estado:** CORREGIDO.
- **Evidencia:**
  - La clave es aleatoria por clase (`secrets.token_urlsafe(24)`,
    `pns_ai_mcp/tests/_helpers.py:200-202`).
  - El desmontaje devuelve al administrador la clave que tenía (`:225-241`).
  - Los demás `commit()` de tests limpian lo que crean (`test_safe_plan_atomicity.py:62-67`,
    `test_system_action.py:458-476`).
  - Observación: si la ejecución se corta entre montaje y desmontaje, el administrador se queda con
    una clave aleatoria (no conocida).
- **Prueba en el laboratorio:** sí. Tras `odoo-dev 14 tests pns_ai_mcp` (BD de tests nueva),
  comprobar que el hash de la clave del administrador es el mismo que antes.

### PNS-35 — Inyección de fórmulas en exportaciones XLSX

- **Gravedad:** Media · **Estado:** SIN CAMBIOS.
- **Evidencia:**
  - Las dos vías openpyxl siguen escribiendo el texto tal cual:
    - `str(value)` (`pns_ai_mcp/controllers/formatters.py:452`);
    - `_excel_value` → `_xlsx_plain_text`, que solo quita caracteres de control
      (`utils/artifact_export.py:2152, 2228-2236, 2307-2313`).

    openpyxl trata como fórmula cualquier cadena que empiece por `=`.
  - Novedad: fórmulas deliberadas a partir de plantillas aritméticas validadas
    (`artifact_export.py:520-576`), que no amplían el problema.
  - La exportación XLSX del chat (`inlineStr`) sigue sin evaluarse como fórmula.
- **Prueba en el laboratorio:** sí. Un registro cuyo nombre empiece por `=`, exportado por una
  descarga XLSX de skill o `relaxaicode`: abrir el archivo y ver si la celda es fórmula.

### PNS-36 — Esquema de cualquier modelo y nombre de la BD expuestos por MCP

- **Gravedad:** Media · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:** desaparecen `resources/list` y `resources/read`, `fetch_native_mcp_resource`
    (`controllers/tools_system.py`) y `system://info` (`utils/system_info.py`). El controlador ya
    solo atiende `server/discover`, `initialize`, `tools/*` y `prompts/*`
    (`pns_ai_mcp/controllers/main.py:1122-1139`).
  - **Resto (otro punto de entrada):** el sandbox de `relaxaicode`, que usa cualquier usuario del
    chat o de MCP, precarga el nombre de la BD como `dbname`, `db_name` y `database`
    (`controllers/context_builder.py:436-438, 550-552`; ya estaba en la versión analizada).
    Ningún validador bloquea `fields_get` sobre un modelo sin permiso de lectura.
- **Prueba en el laboratorio:** sí. Un usuario de chat sin grupos de IA pide el nombre de la base de
  datos y los campos de un modelo al que no tiene acceso: observar si los obtiene.

### PNS-37 — Diario de cambios incompleto y valores sin redactar

- **Gravedad:** Media · **Estado:** SIN CAMBIOS.
- **Evidencia:**
  - `intended_values` se guarda sin redactar en los planes fallidos
    (`pns_ai_mcp/models/ai_change_journal.py:377`).
  - La reversión solo cubre `create`, `copy` y `write` (`:411-455`).
  - La redacción por nombre no cubre `env_vars` ni `config_json`
    (`utils/change_journal.py:30-38`, archivo sin cambios).
  - El diff del modelo solo renombra `correlation_id` → `turn`.
- **Prueba en el laboratorio:** no (revisión de código).

### PNS-38 — Conocimiento de fábrica que induce acciones de sistema y cita campos inexistentes en 14

- **Gravedad:** Media · **Estado:** SIN CAMBIOS.
- **Evidencia:**
  - El prompt de sistema sigue explicando cómo proponer `module.update` y cambios de grupos nativos
    (`pns_ai_mcp/ai/contexts/core/system_prompt.xml:142-144`) y anima a usar `fetch_url` (`:21-26`).
  - Siguen los campos inexistentes en 14: `pns_delivery_status` (`ai/contexts/domain/email.md:4-87`)
    y `calendar.event.customer_id` (`ai/contexts/domain/partners.xml:38`).
  - Se retiran los contextos de descubrimiento de cdmon, Sesame y geo, que no eran el objeto del
    hallazgo.
- **Prueba en el laboratorio:** no (revisión de contenido).

### PNS-39 — Desviaciones de la especificación MCP

- **Gravedad:** Media · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:**
    - `/mcp/message` responde 202 (`pns_ai_mcp/controllers/main.py:689`).
    - Se negocia la versión de protocolo y se envuelve el resultado según la era
      (`main.py:960-977`; `utils/mcp_protocol.py:132`).
  - **Resto:**
    - Las notificaciones a `/mcp` siguen con 204 (`main.py:586, 984`).
    - Los errores de autenticación salen con 200 (`_mcp_json_http_response` sin `status`,
      `:1031-1039`).
    - `isError` solo aparece como `False` (`controllers/tools_relaxaicode.py:1535, 1568`).
- **Prueba en el laboratorio:** sí (funcional). Un cliente MCP estricto: inicializar, enviar una
  notificación y una clave errónea, y anotar códigos de estado.

### PNS-40 — Parámetros de protocolo LLM rechazados; endpoint en el mensaje de error

- **Gravedad:** Media · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:**
    - Se puede omitir `temperature` por proveedor (`send_temperature` según
      `temperature_support`, `pns_ai_mcp/utils/agent_engine.py:2642-2644`).
    - El driver de Anthropic reintenta sin ella si el modelo la rechaza
      (`lib/llm/drivers/anthropic_driver.py:191-200`).
    - Las imágenes se convierten al bloque propio de Anthropic (`anthropic_driver.py:288-303`).
  - **Resto:**
    - `temperature = 0` sigue pasando a 0,7 (`agent_engine.py:2625`).
    - No se usa `max_completion_tokens` en el driver OpenAI (`openai_driver.py:590-592`).
    - El error al usuario sigue incluyendo el endpoint (`agent_engine.py:3289-3299`) y se muestra el
      fallo de cada proveedor (`:2412-2418`).
- **Prueba en el laboratorio:** sí. Con un proveedor de endpoint inalcanzable, el mensaje del chat
  no debe mostrar la URL; hoy se espera que la muestre.

### PNS-41 — `pns_base`: `website` de todos los módulos reescrito e `index.html` servido sin sanear

- **Gravedad:** Media · **Estado:** CORREGIDO.
- **Evidencia:**
  - Ya no se reescribe `website` ni hay escrituras en carga. El índice local solo se incrusta si el
    manifiesto del propio módulo apunta a él (`pns_base/models/ir_module_module.py:1-33`).
  - El `iframe` lleva `sandbox` sin `allow-scripts` (`static/src/js/pns_module_index.js:23-28`), así
    que un `index.html` con JavaScript no se ejecuta.
  - Observación (inventario, inferencia): en BD donde la versión anterior reescribió `website`, el
    valor vuelve al del manifiesto al actualizar la lista de aplicaciones.
- **Prueba en el laboratorio:** sí. Ficha de un módulo OCA: su `website` debe ser el del manifiesto
  y verse la descripción estándar. Ficha de un módulo PNS: índice incrustado sin scripts (consola).

### PNS-42 — `pns_base`: cambio global del JS de validación y del CSS de obligatorios

- **Gravedad:** Media · **Estado:** SIN CAMBIOS.
- **Evidencia:**
  - Se quita el `ListController.include`, pero el `BasicController.include` sigue sustituyendo
    `_notifyInvalidFields` en todos los formularios y listas
    (`pns_base/static/src/js/pns_invalid_fields_dedupe.js:44-96`).
  - El CSS de obligatorios sigue siendo global (`static/src/css/pns_required_readonly.css:4-13`).
  - No hay opción para desactivarlo.
- **Prueba en el laboratorio:** no (revisión de código).

### PNS-61 — Agente, proveedor e historial elegidos por el navegador

- **Gravedad:** Media · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:**
    - El agente lo fija el servidor (`resolve_inference_agent_code(None, consumer_key='chatboo')`,
      `pns_ai_chatboo/controllers/chatboo.py:790-792`).
    - El `provider_id` del cliente solo estrecha la cadena del agente; uno fuera de ella se ignora
      (`pns_ai_mcp/models/ai_execution_engine.py:184-240`).
    - `/chatboo/sessions/save` ya no guarda `backend_history`, `meta` ni `records`
      (`chatboo.py:343-377`).
  - **Resto:** el `history` del cuerpo de `/chatboo/stream` sigue llegando del navegador
    (`chatboo.py:738`). Se guarda en el job (`models/chatboo_async_request.py:242`) y es el
    historial que recibe el motor (`:418, 605`). El usuario puede fabricar turnos previos o
    resultados de herramientas.
  - Observación: si el agente no tiene cadena, sirve cualquier proveedor activo
    (`ai_execution_engine.py:210-226`), que es una decisión de configuración.
- **Prueba en el laboratorio:** sí. Enviar a `/chatboo/stream` un `provider_id` fuera de la cadena:
  debe ignorarse. Enviar un `history` con un turno inventado: hoy se espera que el asistente lo
  trate como real.

### PNS-62 — Adjuntos e imágenes sin límites de tamaño ni truncado

- **Gravedad:** Media · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:**
    - Tope por archivo e imagen en `/chatboo/stream`, 15 MB por defecto y configurable
      (`pns_ai_chatboo/controllers/chatboo.py:768-786`; `utils/chatboo_product_icp.py:22, 64-97`).
    - Los documentos se leen a trozos de 8 000 caracteres bajo demanda, con un máximo conservado
      (`utils/turn_documents.py:19-21, 55-65, 108`).
    - Las imágenes previas se reenvían acotadas y reescaladas
      (`models/chatboo_async_request.py:1028-1050`).
  - **Resto:**
    - No hay tope de número de archivos ni del cuerpo total.
    - Con el parámetro a 0 no hay límite.
    - Los documentos subidos siguen siendo una vía de prompt injection indirecta (es el resto de
      PNS-16).
- **Prueba en el laboratorio:** sí. Subir un archivo mayor que el tope: mensaje de límite sin
  llamar al proveedor. Subir varios archivos menores que el tope cuya suma sea grande: hoy se
  aceptan.

### PNS-63 — Retención de sesiones solo al volver a usar el chat

- **Gravedad:** Media · **Estado:** CORREGIDO.
- **Evidencia:**
  - `_cleanup_old_sessions` borra por ORM las sesiones de todos los usuarios con más días que la
    retención (30 por defecto) (`pns_ai_chatboo/models/chatboo_session.py:1360-1381`;
    `utils/chatboo_product_icp.py:20`).
  - Lo llama el cron de mantenimiento cada 5 minutos (`models/chatboo_async_request.py:2167`;
    `data/chatboo_async_cron.xml`).
  - `user_id` pasa a `ondelete='set null'` (`chatboo_session.py:52-58`), así que borrar un usuario
    ya no borra sus sesiones por SQL. Quedan para el cron, cuyo `unlink` borra los adjuntos
    (`:1280-1332`).
- **Prueba en el laboratorio:** sí. Con la retención a 1 día, una sesión con adjunto y
  `last_used_date` antigua de un usuario que no vuelve: tras el cron deben desaparecer la sesión y
  el adjunto.

### PNS-64 — Lectura en voz alta con voces remotas

- **Gravedad:** Media · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:** `pickVoice` prefiere una voz local del idioma
    (`pns_ai_chatboo/static/src/js/chatboo_tts.js:59-87`).
  - **Resto:**
    - Si no hay voz local, usa la remota (`:76-79`).
    - No hay ajuste para que el administrador desactive la función.
- **Prueba en el laboratorio:** sí (navegador con voces en la nube, por ejemplo Chrome o Edge sin
  voces locales del idioma): observar si la lectura usa una voz remota.

### PNS-65 — Exportaciones generadas en el navegador

- **Gravedad:** Media · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:**
    - El HTML de Word y del documento subido pasa por `sanitizeHtml`
      (`pns_ai_chatboo/static/src/js/chatboo_export.js:78, 806, 3087`).
    - El archivo se sirve como adjunto con `nosniff` (`pns_ai_mcp/controllers/session_file.py:64-73`),
      así que el `mimetype` del cliente ya no lo abre como página.
  - **Resto:**
    - `src` de imágenes concatenado sin escapar en Word (`chatboo_export.js:3150, 3235`).
    - Se exportan todas las claves del dataset salvo las que empiezan por `_`
      (`:2197-2232`).
    - `/chatboo/sessions/fulfill_export` guarda el `mimetype` que envía el cliente
      (`controllers/chatboo.py:301-322` → `models/chatboo_session.py:471-490`).
    - Los documentos pendientes se suben solos al pintar el mensaje
      (`chatboo_component_v2.js:5625-5648`).
- **Prueba en el laboratorio:** sí. Exportar a Word una respuesta con imagen y abrir el `.doc`:
  ver si carga recursos externos. Comparar las columnas del XLSX o Word con las visibles en el chat.

### PNS-66 — Skills de fábrica sin control de grupo

- **Gravedad:** Media · **Estado:** SIN CAMBIOS.
- **Evidencia:**
  - `list_for_agent` solo filtra por `active` y `show_in_slash`
    (`pns_ai_mcp/models/ai_skill.py:897-929`), y `ai.skill` no tiene campo de grupos.
  - Siguen `users-all` (archivados y último acceso,
    `pns_ai_chatboo/ai/skills/system/users_all.py:6, 14`), `users-logged` y `sys-info` (base de
    datos, URL y versiones, `sys_info.py:8-21`). `forecast` sigue pidiendo datos externos por ciudad
    (`forecast.py:7, 77`).
- **Prueba en el laboratorio:** sí. Un usuario de chat sin grupos de IA ejecuta `/users-all` y
  `/sys-info`: hoy se espera que obtenga el censo y los datos del sistema.

### PNS-67 — Errores funcionales en skills financieras

- **Gravedad:** Media · **Estado:** CORREGIDO.
- **Evidencia:**
  - `financial-health` acepta `Metric`/`Métrica` además de `Indicator`
    (`pns_ai_chatboo/ai/skills/system/financial_health.py:344-345`) y filtra por fecha y compañía
    (`:222-280, 394`).
  - `customer-risk-analysis` toma la fecha de cobro de la contrapartida conciliada, nunca de la
    propia línea, con una sola lectura de apuntes conciliados (`customer_risk_analysis.py:30-34,
    77-83`).
  - `analisis-financiero` se elimina.
  - Observación (corrige la del inventario): además de la migración `2.1.343`, que en 14 no se
    ejecuta, la semilla `pns_ai_chatboo/data/chatboo_skill_data.xml:9-10` (cargada en cada `-u`, con
    superusuario) llama a `unlink_named_factory_skills` con `analisis_financiero` y
    `analisis-financiero`. En 14 la skill retirada sí se borra al actualizar, salvo que tenga dueño.
- **Prueba en el laboratorio:** sí (funcional). Ejecutar `financial-health` y
  `customer-risk-analysis` con datos de una copia: conclusiones coherentes y DSO distinto de cero en
  clientes que pagan tarde. Comprobar si `analisis-financiero` sigue en la lista.

### PNS-68 — Migraciones que borran skills por código sin filtrar el dueño

- **Gravedad:** Media · **Estado:** SIN CAMBIOS.
- **Evidencia:**
  - `migrations/2.1.296/post-migrate.py:20-35` y `migrations/2.1.300/post-migrate.py:26-36` no
    cambian: siguen borrando por `code`, `command` o `rel_path` sin filtrar el dueño.
  - La migración nueva `2.1.343` sí filtra, porque usa `unlink_named_factory_skills`
    (`pns_ai_mcp/models/ai_skill.py:2184-2212`).
  - En Odoo 14 ninguna de ellas se ejecuta (§7.2 del informe e inventario).
- **Prueba en el laboratorio:** no (no se ejecutan en 14).

### PNS-70 — Choque de `window.Chart` con el Chart.js de Odoo 14

- **Gravedad:** Media · **Estado:** SIN CAMBIOS.
- **Evidencia:**
  - Se sigue eligiendo el motor y creando el gráfico con la global
    (`typeof global.Chart`, `new global.Chart(...)`,
    `pns_ai_chatboo/static/src/js/chatboo_charts.js:1617-1636, 1983`).
  - Se carga Chart.js 4.4.8 en `web.assets_backend` (`views/assets.xml:22`).
- **Prueba en el laboratorio:** sí. Abrir una vista gráfico de Odoo y después pedir un gráfico en el
  chat sin recargar: observar si se pinta mal o da error en la consola.

### PNS-43 — Descarte silencioso de traducciones duplicadas en cualquier carga

- **Gravedad:** Baja · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:** el asistente de cargar idioma avisa con una notificación de cuántas filas se
    descartaron (`pns_base/models/base_language_install.py:12-31`;
    `models/ir_translation.py:111`).
  - **Resto:**
    - El descarte sigue aplicándose a cualquier módulo.
    - Por otras vías con sobrescritura (`base.update.translations`, `-u` con `--i18n-overwrite`)
      solo queda el WARNING del log.
- **Prueba en el laboratorio:** opcional. Recargar `es_ES` con sobrescritura desde Ajustes: si hay
  duplicados, debe aparecer el aviso.

### PNS-44 — Escrituras en `ir.module.module` durante la carga del registro

- **Gravedad:** Baja · **Estado:** YA NO APLICA.
- **Evidencia:** `pns_base/models/ir_module_module.py` queda en un campo calculado sin escrituras.
  No hay `_register_hook` ni llamadas a `get_module_resource`/`get_module_path` en `pns_base`.
- **Prueba en el laboratorio:** sí (rápida). En el log de arranque no deben aparecer avisos de
  `get_module_path` causados por `pns_base`.

### PNS-45 — `ImportError` silenciado al registrar herramientas MCP

- **Gravedad:** Baja · **Estado:** CORREGIDO.
- **Evidencia:** `_load_tool` registra la excepción con traza por cada herramienta que no carga, sin
  impedir las demás (`pns_ai_mcp/controllers/__init__.py:17-31`).
- **Prueba en el laboratorio:** no.

### PNS-46 — El glosario `es_ES` probablemente no llega a la parte fija del prompt

- **Gravedad:** Baja · **Estado:** DUDOSO.
- **Evidencia:**
  - La composición carga las variantes de idioma (`assemble_context_parts` →
    `_lazy_load_locale_variants`, `pns_ai_mcp/models/ai_context.py:818-826`). Ese mecanismo ya
    existía en la versión analizada, así que el código no permite decidir si la inferencia del
    informe era correcta.
  - `normalize_context_ids` sigue colapsando a la variante genérica (`:977-1005`).
  - Sigue habiendo una sola caché por agente con un solo `cache_locale`
    (`models/ai_agent.py:203, 1182-1197`).
- **Prueba en el laboratorio:** sí. Con un usuario `es_ES`, reconstruir la caché del agente de
  Chatboo y buscar en `cached_content` el formato `1.234,56` y los términos españoles de
  `corporate_terms_es_ES`.

### PNS-47 — Sin red, cada `check_health` espera los timeouts de las fuentes FX

- **Gravedad:** Baja · **Estado:** CORREGIDO.
- **Evidencia:**
  - El fallo se guarda 15 minutos con `retry_after` (`pns_ai_mcp/models/ai_fx_source.py:22,
    100-104, 136-153`).
  - Antes de dar el fallo se prueba `res.currency` (`:124-131`).
- **Prueba en el laboratorio:** opcional. Sin salida a Internet, dos aperturas seguidas del chat:
  solo la primera debe esperar.

### PNS-48 — Menú Settings inaccesible para AI Administrator; acciones duplicadas

- **Gravedad:** Baja · **Estado:** CORREGIDO.
- **Evidencia:**
  - El menú Settings pasa a `base.group_system`
    (`pns_ai_mcp/views/res_config_settings_views.xml:335-340`).
  - En el menú Acción de `ai.skill` quedan cuatro acciones distintas (`views/ai_menus.xml:222`;
    `views/ai_skill_views.xml:167-190`); las otras definiciones tienen `binding_model_id` vacío.
- **Prueba en el laboratorio:** sí (rápida). AI Administrator sin Ajustes: no ve Settings. Lista de
  skills: sin acciones repetidas.

### PNS-49 — Código muerto

- **Gravedad:** Baja · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:** se eliminan `controllers/write_verification.py`, `utils/api_key_migration.py` y
    `showdown.min.js`.
  - **Resto:** siguen sin uso o sin efecto en 14:
    - `controllers/moe_controller.py` (no se importa);
    - `cleanup_stuck_state` (`models/safe_operation.py`);
    - `web_read` (`models/ai_agent.py`);
    - `search_fetch` (`models/mcp_user.py`);
    - `ActionManager.include` (`static/src/js/mcp_log_tree_v14.js`);
    - `_onToggleBoolean` (`static/src/js/mcp_user_tree_v14.js`);
    - el driver `ollama`, registrado (`lib/llm/drivers/registry.py:19`) pero no seleccionable en
      `ai.provider.protocol`.
- **Prueba en el laboratorio:** no.

### PNS-50 — Tests no cargados o descartados; sin tests de seguridad negativa

- **Gravedad:** Baja · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:**
    - Hay tests negativos nuevos: métodos privados de `ai.system.action` y `ai.trusted.action`
      (`pns_ai_mcp/tests/test_system_action.py:429-456`) y escapes del sandbox
      (`test_relaxaicode_sandbox_escapes_e2e.py`).
    - `test_session_download` pasa a importarse.
  - **Resto:**
    - `test_change_journal.py` sigue sin importarse (`tests/__init__.py`).
    - `test_presentation_mode` y `test_session_download` siguen siendo `unittest.TestCase`
      (`test_presentation_mode.py:19-20`, `test_session_download.py:20-21`). Su `@tagged` no
      incluye `standard`, y Odoo 14 filtra por defecto con `+standard`
      (`odoo/tools/config.py:596` de la referencia), así que se descartan.
    - No hay cobertura del motor LLM.
- **Prueba en el laboratorio:** sí, cuando se pueda importar el módulo: `odoo-dev 14 tests
  pns_ai_mcp` y comprobar en el log si esas dos clases se ejecutan.

### PNS-51 — Módulo `platform` permitido en el sandbox

- **Gravedad:** Baja · **Estado:** SIN CAMBIOS.
- **Evidencia:** `platform` sigue en la lista de módulos permitidos
  (`pns_ai_mcp/controllers/validators.py:94`).
- **Prueba en el laboratorio:** opcional. Pedir en el chat la versión del sistema operativo del
  servidor: hoy se espera que la obtenga.

### PNS-52 — `settings_io`: defaults con `lambda self` y selecciones dinámicas sin validar

- **Gravedad:** Baja · **Estado:** CORREGIDO.
- **Evidencia:**
  - `field_default` llama al default con un recordset vacío y, si falla, devuelve el vacío del tipo
    (`pns_base/utils/settings_io.py:113-133`).
  - Las selecciones definidas por método se resuelven y validan; si no se pueden leer, el valor se
    rechaza (`pns_base/utils/portable_io.py:133-158`).
- **Prueba en el laboratorio:** no.

### PNS-69 — `SELF_READABLE_FIELDS` / `SELF_WRITEABLE_FIELDS` redefinidos como `property`

- **Gravedad:** Baja · **Estado:** CORREGIDO.
- **Evidencia:** se amplían las listas de clase en `__init__`, como hacen `mail` y `hr`
  (`pns_ai_chatboo/models/res_users.py:44-57`).
- **Prueba en el laboratorio:** sí (rápida). Con `hr` instalado, un usuario cambia sus preferencias
  de Chatboo y su propia ficha sin error.

### PNS-71 — `check_health` y `/chatboo/providers` exponen infraestructura; errores con estado 200

- **Gravedad:** Baja · **Estado:** CORREGIDO.
- **Evidencia:**
  - `check_health` exige la clave (`pns_ai_chatboo/controllers/chatboo.py:85-86`). Devuelve el alias
    o el nombre del proveedor, no el host (`_picker_label`, `:1005-1013`), y un mensaje genérico en
    los errores (`:150-160`).
  - `/chatboo/providers` solo ofrece la cadena del agente, sin la búsqueda en `sudo` de todos los
    proveedores (`:670-712`).
  - `_json_response` respeta el `status` (`:1046-1053`).
  - Observación: `_fx_payload` devuelve `str(exc)` si falla el cálculo de divisas (`:1024-1029`).
- **Prueba en el laboratorio:** sí (rápida). Un interno sin clave llama a `/chatboo/check_health`:
  acceso denegado. Una petición inválida a `/chatboo/stream` debe responder 400.

### PNS-72 — 7 librerías JS cargadas para todos los internos

- **Gravedad:** Baja · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:** sale SheetJS y desaparecen los duplicados con `pns_ai_mcp` (PNS-27).
  - **Resto:**
    - Siguen seis librerías de terceros en `web.assets_backend` para todo interno: showdown, jsPDF,
      autotable, html2canvas, Chart.js y ECharts (`pns_ai_chatboo/views/assets.xml:17-23`).
    - Cada carga del cliente sigue llamando a `check_health` (`static/src/js/chatboo_systray.js:45`).
- **Prueba en el laboratorio:** no.

### PNS-73 — Sintaxis sin transpilar y posibles conflictos con diálogos del core

- **Gravedad:** Baja · **Estado:** SIN CAMBIOS.
- **Evidencia:**
  - Sigue el campo `static` de clase (`pns_ai_chatboo/static/src/js/chatboo_component_v2.js:183`) y
    `setup()` en el componente OWL (`:193`).
  - Sigue la capa con `z-index: 1050` (`chatboo_systray.js:432`; `css/chatboo_floating.css:1251`).
  - No hay `?.` ni `??` en los archivos propios.
- **Prueba en el laboratorio:** sí (funcional). Con Chatboo abierto, abrir un diálogo del core (por
  ejemplo, un asistente): debe quedar por encima.

### PNS-74 — Código muerto o heredado en el cliente web

- **Gravedad:** Baja · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:** `window.open` lleva `noopener` (`pns_ai_chatboo/static/src/js/chatboo_systray.js:143`;
    `chatboo_component_v2.js:615`), y no queda el «#undefined» del modal de contexto.
  - **Resto:**
    - `chatboo_floating_transfer_history` (`chatboo_component_v2.js:724-739`);
    - `_saveRawForTemplate` (`:5224`);
    - la rama `result.error` (`:3161`);
    - `mail_service`, que no existe en 14 (`chatboo_systray.js:202`);
    - `chatboo_has_access`, que se escribe y no se lee (`:50-61`).
- **Prueba en el laboratorio:** no.

### PNS-75 — Copia TSV al portapapeles sin neutralizar fórmulas

- **Gravedad:** Baja · **Estado:** CORREGIDO.
- **Evidencia:**
  - `clipCellText` antepone `'` a las celdas que empiezan por `=`, `+`, `-` o `@` y no son números
    (`pns_ai_chatboo/static/src/js/chatboo_export.js:2787-2808`).
  - La copia del mensaje usa ese TSV (`:706`).
  - La alternativa sin datos estructurados copia texto plano, sin tabuladores (`:2176-2187`).
- **Prueba en el laboratorio:** opcional. Copiar una tabla con un nombre que empiece por `=` y
  pegarla en una hoja de cálculo: debe quedar como texto.

### PNS-76 — Receta del agente distinta en bases actualizadas y nuevas; menú tras generar la clave

- **Gravedad:** Baja · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:** al escribir el hash de la clave se vacía la caché de menús
    (`pns_ai_mcp/models/mcp_user.py:370-378`).
  - **Resto:** las migraciones `2.1.217`/`2.1.237` siguen añadiendo `acl_security` al agente
    `pns_ai_chatboo` (`migrations/2.1.237/post-migrate.py:12, 21`), y los datos no lo llevan
    (`data/ai_agent_data.xml:16-17`). La limpieza nueva `_drop_acl_security_factory_fossil` solo
    actúa sobre el agente `pns_ai_mcp` (`pns_ai_mcp/models/ai_agent.py:251-274`). En 14 esas
    migraciones no se ejecutan, así que la diferencia solo afecta a BD que las hayan ejecutado en
    otra versión.
- **Prueba en el laboratorio:** sí. Generar la clave de un usuario sin recargar: el menú Chatboo
  debe aparecer en la siguiente navegación. En una copia de producción, revisar
  `default_context_codes` del agente `pns_ai_chatboo`.

### PNS-77 — Sin tests

- **Gravedad:** Baja · **Estado:** SIN CAMBIOS.
- **Evidencia:** `pns_ai_chatboo` sigue sin carpeta `tests/`. Las reglas nuevas de aislamiento
  (PNS-53, PNS-55) no tienen tests propios.
- **Prueba en el laboratorio:** no.

### PNS-78 — Dos pares de campos de `ai.agent` con la misma etiqueta

- **Gravedad:** Baja · **Estado:** CORREGIDO.
- **Evidencia:** `context_ids_shown` y `skill_ids_shown` pasan a «Contexts on the form» y «Skills on
  the form» (`pns_ai_mcp/models/ai_agent.py:161-175`).
- **Prueba en el laboratorio:** sí (rápida). Actualizar el módulo: no debe aparecer el aviso de
  etiquetas duplicadas.

### PNS-79 — `/mcp/message` usa `SUPERUSER_ID` si la sesión no tiene usuario

- **Gravedad:** Baja · **Estado:** CORREGIDO.
- **Evidencia:**
  - Ya no hay valor por defecto. El usuario sale de la clave revalidada en cada mensaje, y la
    petición se rechaza con 401 si no coincide con el de la sesión
    (`pns_ai_mcp/controllers/main.py:650-665`). Una sesión sin usuario no coincide nunca.
  - La variante por agente delega en el mismo método (`:284-286`).
- **Prueba en el laboratorio:** sí, junto con PNS-13: con una sesión SSE abierta, revocar la clave;
  el siguiente mensaje debe dar 401.

## Hallazgos nuevos

Solo código nuevo o modificado en `git diff 14.0-analisis-pns-ai..HEAD`. Mismo criterio de gravedad
que el informe. Antes de numerar cada uno se ha comprobado con Grep que no figuraba en el informe ni
en este seguimiento; cuando era un resto ya citado, se indica la relación.

Patrón común en PNS-82, PNS-83 y PNS-85: es la misma causa que PNS-01 en código nuevo. Son métodos
públicos (sin `_`) que trabajan en `sudo` o con un cursor de superusuario y no comprueban grupo ni
propiedad. En Odoo 14, `call_kw` los deja invocar a cualquier usuario autenticado, también a uno de
portal, aunque no tenga ACL sobre el modelo.

### PNS-81 — Incompatibilidades con Odoo 14: el módulo no se importa y dos funciones fallan en ejecución

- **Gravedad:** Alta · **Estado:** NUEVO.
- **Descripción:** detalle completo en «Compatibilidad con Odoo 14».
  - **Al importar:** `pns_ai_mcp/controllers/mcp_decorators.py:169`. La anotación de retorno
    `tuple[bool, Optional[str]]` se evalúa al definir la función, y el archivo no tiene
    `from __future__ import annotations`. Con Python < 3.9 lanza `TypeError: 'type' object is not
    subscriptable`. No se importan ni `pns_ai_mcp` ni `pns_ai_chatboo`, que depende de él (comprobado
    con `paridad` en la fase 1).
  - **Al ejecutar, Python 3.7:** `pns_ai_mcp/utils/relaxaicode_recipe.py:507` llama a
    `ast.get_source_segment`, que existe desde 3.8. Ya estaba en el §7.3 del informe como «posiblemente
    no capturado». Ahora está confirmado: el camino principal de `tool_relaxaicode` lo llama sin
    protección (`controllers/tools_relaxaicode.py:1867`). El `except` general (`:2986`) convierte el
    `AttributeError` en un error de la herramienta. Falla cualquier código que defina, a nivel de
    módulo, una función con un parámetro cuyo nombre contenga `date`, `day`, `fecha`, `when` o `dia`
    (`_DATE_PARAM_HINTS`, `:206-209`; se compara por subcadena). Es el caso típico de las consultas por
    rango de fechas.
  - **Al ejecutar, Pillow 5.4.1:** `pns_base/utils/pdf_io.py:94` llama a `ImageOps.exif_transpose`,
    que existe desde Pillow 6.0. Odoo 14 fija `Pillow==5.4.1` con Python ≤ 3.7
    (`requirements.txt:34` de la referencia). Todas las funciones de imagen capturan la excepción y
    devuelven `None` («no es una imagen»), así que el fallo es silencioso:
    - `/pns_ai_mcp/remote_image` responde 404 a todas las imágenes (`utils/remote_image.py:79-81`,
      `controllers/remote_image.py`);
    - Chatboo reenvía al proveedor las imágenes previas sin reescalar
      (`pns_ai_chatboo/models/chatboo_async_request.py:1079-1094`).
- **Impacto:** en un servidor Odoo 14 con Python 3.7 (la imagen oficial, Debian Buster) o 3.8,
  sustituir el código deja la base de datos sin cargar, porque `pns_ai_mcp` está instalado y no se
  importa. Corregida la importación, los otros dos fallos dejan funciones rotas sin aviso. Con Python
  3.8 y Pillow 8.1.1 solo queda el fallo de importación.
- **Prueba en el laboratorio:** sí (funcional), cuando el fabricante corrija la importación:
  - `odoo-dev 14 paridad pns_base,pns_ai_mcp,pns_ai_chatboo` sin errores de importación;
  - una consulta del chat que defina una función con un parámetro `date_from`;
  - una respuesta con una imagen externa permitida, que debe mostrarse.

### PNS-82 — `chatboo.session.claim_turn_file_chips` se apropia de adjuntos ajenos sin `res_model`

- **Gravedad:** Alta · **Estado:** NUEVO (relacionado con PNS-55 y PNS-21).
- **Ubicación:** `pns_ai_chatboo/models/chatboo_session.py:415-441`. También se llega desde el método
  público `apply_assistant_download_chips` (`:401-413`).
- **Comportamiento:**
  - El método es público. Sobre una sesión propia (la regla por `user_id` lo exige), toma ids de
    adjunto de la lista recibida o de la URL del chip.
  - Con `ir.attachment` en `sudo`, reasigna a esa sesión (`res_model`/`res_id`) cualquier adjunto que
    no tenga `res_model`. No comprueba quién lo creó ni que lo haya generado el motor.
  - Después, `_may_read` de `/pns_ai_mcp/session_file` lo entrega, porque el adjunto ya cuelga de una
    sesión que el llamador puede leer (`pns_ai_mcp/controllers/session_file.py:20-32`).
  - Además, al borrar su propia sesión, el usuario borra en `sudo` todos los adjuntos que cuelgan de
    ella (`chatboo_session.py:1326-1333`), también los reclamados.
- **Impacto:** cualquier usuario interno (el ACL de `chatboo.session` es `base.group_user`) puede leer
  o borrar adjuntos de otros usuarios que no tengan `res_model`. Entre ellos están las descargas del
  chat de otros usuarios y las exportaciones portables de `pns_base`, que pueden llevar secretos si
  se exportaron con ellos. Los ids son secuenciales. Es la misma clase de fuga que PNS-21 (Alta).
- **Prueba en el laboratorio:** sí (permisos). A genera una descarga en el chat. B, sobre su propia
  sesión, llama por RPC a `claim_turn_file_chips` con el id de ese adjunto y después abre
  `/pns_ai_mcp/session_file/<id>`. Hoy se espera que B lo descargue; tras la corrección, el adjunto no
  debe cambiar de sesión. Comprobar también que el chat de A sigue sirviendo su descarga.

### PNS-83 — `ai.mcp.user.redeem_key_pin` entrega claves MCP por RPC sin grupo y sin límite efectivo de intentos

- **Gravedad:** Alta · **Estado:** NUEVO (relacionado con PNS-07, PNS-33 y PNS-84).
- **Ubicación:** `pns_ai_mcp/models/mcp_user.py:819-860`; `models/key_pin_block.py:36-73`;
  `models/key_pin_desk.py:171-192`; `static/src/js/key_pin_desk_v14.js:93-118`.
- **Comportamiento:**
  - `redeem_key_pin(raw, ip=None)` es `@api.model`, público, sin comprobación de grupo. No tiene
    llamador en los tres módulos. Busca el PIN en `sudo` y, si hay una mesa abierta, devuelve la clave
    MCP en claro del usuario dueño del PIN.
  - La pestaña del administrador responde sola: si tiene la clave en su lista, la envía a
    `/key_pin/supply` sin intervención del administrador.
  - El contador de fallos depende del `ip` que pasa quien llama. Vacío, no se cuenta ni se bloquea
    (`key_pin_block.py:38-40, 48-50`). Por RPC lo elige el propio llamador, así que puede no enviarlo
    o cambiarlo en cada intento.
  - `ai.key.pin.block.release_all()` (`:68-73`) también es `@api.model` público y en `sudo`. Cualquier
    usuario autenticado puede levantar todos los bloqueos.
  - El canje no marca el PIN como usado. El PIN sigue válido hasta que se llama a `consume_key_pin` o
    el administrador lo borra.
  - Cada canje con PIN correcto ocupa un worker hasta 20 s (`key_pin_desk.py:185-192`).
- **Impacto:** un usuario autenticado cualquiera, también de portal, puede probar PIN sin límite real.
  Con un PIN vivo (8 dígitos por defecto; se puede bajar a 4) y una mesa abierta, obtiene la clave MCP
  de ese usuario, que puede ser un AI Administrator, y actúa por `/mcp` en su nombre. Es el mismo
  patrón de PNS-01, sobre credenciales.
- **Prueba en el laboratorio:** sí (permisos y funcionamiento, sin redactar el procedimiento):
  - un interno sin grupos de IA y un usuario de portal llaman por RPC a `redeem_key_pin` con un valor
    con forma de PIN y a `ai.key.pin.block.release_all`. Tras la corrección deben recibir
    `AccessError`; hoy se espera que respondan;
  - con un PIN erróneo y sin `ip`, comprobar que no se crea ni se incrementa ninguna fila en
    `ai.key.pin.block`.

### PNS-84 — PIN y clave MCP en claro en la base de datos y en el navegador

- **Gravedad:** Media · **Estado:** NUEVO (relacionado con PNS-33 y PNS-83).
- **Ubicación:** `pns_ai_mcp/models/mcp_user.py:142`; `models/key_pin_desk.py:154-239`;
  `static/src/js/key_pin_desk_v14.js:38-48`.
- **Comportamiento:**
  - `ai.mcp.user.key_pin` guarda el PIN en claro (`Char`, indexado). Lo ven todos los AI Administrator
    y queda en copias de seguridad y réplicas.
  - `ai.key.pin.ask.supplied_key` guarda la clave MCP en claro hasta que la recoge quien espera
    (`:209-212`). Si la respuesta llega después de los 20 s, nadie la recoge. La fila solo se borra en
    el siguiente canje (`_drop_old`, `:164-169`, que solo se llama desde `collect`), así que la clave
    puede quedarse en la tabla indefinidamente.
  - Cualquier AI Administrator puede leer `ai.key.pin.ask` (ACL `1,1,1,1`) y ver claves de otros
    usuarios mientras están en la tabla.
  - La pestaña de la mesa guarda en `sessionStorage` la lista completa de claves en claro (`vault`).
    Cualquier XSS en el backend mientras está abierta las leería todas (relación con PNS-54 y PNS-60).
- **Impacto:** credenciales de acceso MCP en claro fuera del hash que exige PNS-33. Además, quedan sin
  caducidad garantizada.
- **Prueba en el laboratorio:** sí (funcional). Con una mesa abierta, provocar un canje cuya respuesta
  llegue tras el tiempo de espera (por ejemplo, cerrando y reabriendo la pestaña). Después, consultar
  por `SELECT` si `ai_key_pin_ask` conserva filas con `supplied_key`.

### PNS-85 — Caché de parámetros de skills escribible por cualquier usuario autenticado

- **Gravedad:** Media · **Estado:** NUEVO (relacionado con PNS-07).
- **Ubicación:** `pns_ai_mcp/models/ai_skill_param_cache.py:125-154` (`remember_for_skill`) y
  `:91-108` (`lookup_for_skill`); `models/ai_skill.py:329-345`; `utils/agent_engine.py:785`.
- **Comportamiento:**
  - `remember_for_skill(skill_id, leftover, norm)` es `@api.model` público. Crea la fila con un cursor
    propio como `SUPERUSER_ID` y hace commit (`:143-148`).
  - Acepta cualquier `skill_id`, también de skills que el llamador no puede leer, y no sobrescribe una
    fila existente: gana el primero que escribe.
  - La caché es global, sin usuario: `lookup_for_skill` busca en `sudo` por skill y frase normalizada,
    y el motor la aplica en los turnos de todos los usuarios.
  - El ACL (lectura para internos, CRUD para AI Writer y AI Administrator) no interviene. Por el
    commit propio, si el sandbox llega al modelo, la escritura sobrevive al rollback de la caja A: el
    resto de PNS-07 (lista negra de 15 nombres, `validators.py:178-194`) no incluye este método.
- **Impacto:** un usuario sin permisos de escritura puede fijar de antemano los parámetros con que se
  ejecutará una skill para una frase concreta (fechas, filtros, empresa) cuando la use otro usuario.
  Los resultados salen alterados sin aviso. Es integridad, no escalada.
- **Prueba en el laboratorio:** sí (permisos). Un interno sin grupos de IA llama por RPC a
  `ai.skill.param.cache.remember_for_skill` sobre una skill de fábrica. Tras la corrección: `AccessError`.
  Hoy se espera que cree la fila (comprobar como administrador). Además, comprobar si relaxaicode puede
  invocar el método.

### PNS-86 — Generador OpenAPI: descarga sin control de hosts no públicos, redirecciones ni tamaño

- **Gravedad:** Media · **Estado:** NUEVO (relacionado con PNS-17).
- **Ubicación:** `pns_ai_mcp/services/openapi_spec_generator.py:579-610` (`fetch_documentation`);
  `wizard/openapi_spec_generate_wizard.py:197-214`.
- **Comportamiento:**
  - Solo comprueba que el host inicial esté en la lista blanca `web`. Después hace `requests.get`, que
    sigue redirecciones a cualquier host, sin `non_public_host_error`.
  - Lee el cuerpo entero en memoria antes de truncarlo a `_MAX_DOC_CHARS` (`:19`, 120 000 caracteres).
  - El texto se guarda en `docs_text` del asistente, que ve el administrador, y se envía al proveedor
    LLM.
  - La lista blanca no rechaza IP ni nombres internos (`models/url_whitelist.py`, sin constraint), y el
    AI Administrator la gestiona (ACL `1,1,1,1`). Ni siquiera hace falta una redirección: basta con
    añadir un host interno.
- **Por qué número propio:**
  - es un punto de entrada nuevo en esta versión, no un resto de lo que corrigió el fabricante;
  - devuelve el contenido a quien lo pide (SSRF con lectura), mientras que `fetch_url` sí aplica la
    protección completa (`safe_plan.py:1528-1585`);
  - la corrección es local: reutilizar el bucle salto a salto con `non_public_host_error` y la lectura
    con tope de `fetch_url_safe.py`.

  La gravedad es Media y no Alta como PNS-17 porque solo lo usa el AI Administrator, que el informe
  trata como rol distinto del administrador de Odoo (PNS-01).
- **Impacto:** un AI Administrator sin permisos de Ajustes puede leer servicios internos de la red del
  servidor (paneles, metadatos de la nube) y enviarlos al proveedor LLM.
- **Prueba en el laboratorio:** sí (permisos y funcionamiento). Como AI Administrator, generar con una
  URL de documentación de un host permitido que redirija a `localhost`: hoy se espera que la siga.
  Tras la corrección debe rechazarse con el mismo mensaje que `fetch_url`.

### PNS-87 — Purga de `ai.log` a 30 días activa por defecto tras actualizar

- **Gravedad:** Baja · **Estado:** NUEVO (relacionado con PNS-30).
- **Ubicación:** `pns_ai_mcp/data/ai_log_cron.xml` (`noupdate="1"`, activo, diario);
  `models/ai_log.py:17-18, 892-912`.
- **Comportamiento:**
  - Al actualizar se crea el cron activo. Si no existe el parámetro `pns_ai_mcp.log_retention_days`, se
    aplican 30 días.
  - El parámetro no está en Ajustes; solo se cambia en Parámetros del sistema.
  - La primera ejecución borra en `sudo`, en una sola transacción, todas las filas de más de 30 días:
    la auditoría y el historial de consumo y coste que usa `get_user_usage_summary`.
  - No hay aviso ni nota de actualización.
- **Impacto:** pérdida de datos no avisada en instalaciones que guardan el log como auditoría o para
  repartir costes. En bases con mucho volumen, el primer borrado puede ser largo. El informe pedía
  retención (PNS-30), así que el defecto es el valor por defecto y la falta de aviso, no la purga.
- **Prueba en el laboratorio:** sí (funcional), con una copia: tras `actualizar`, comprobar que el cron
  está activo y que el parámetro no existe. Contar por `SELECT` las filas de `ai_log` con más de 30
  días antes de que se ejecute. Para producción: fijar el parámetro antes de actualizar.

### PNS-88 — Datos que la actualización en Odoo 14 no limpia: XML ID `mcp_*` y servidores de fábrica

- **Gravedad:** Baja · **Estado:** NUEVO.
- **Ubicación:** `pns_ai_mcp/migrations/3.1.518/pre-migrate.py` y `3.1.519/pre-migrate.py` (38 XML ID);
  `data/external_server_data.xml` de la versión anterior (eliminado).
- **Comportamiento:**
  - Los renombrados `mcp_*` → `ai_*` de reglas, accesos, menús, acciones y vistas de
    `ai.safe.operation`, `ai.log`, `ai.context` y `ai.change.journal` solo están en migraciones, que en
    14 no se ejecutan, y no se replican en `init()`.
  - Al actualizar, Odoo crea registros `ai_*` nuevos. Al final, `_process_end` borra los `mcp_*`
    (bloques `noupdate="0"`). Se pierden las personalizaciones hechas sobre los antiguos (dominios de
    regla, menús, vistas, traducciones) y las referencias a sus ids (favoritos o filtros guardados
    sobre esas acciones).
  - No hay vistas heredadas de ellos en `third_party` ni en `vertical-instaladores` (Grep), así que el
    borrado no debería fallar en nuestros repos.
  - Los 3 servidores de `external_server_data.xml` eran `noupdate="1"`: quedan en las BD existentes.
    Están inactivos por defecto; uno es `stdio` con `npx`.
- **Descartado:** la skill `analisis-financiero` sí se borra en 14 (ver la corrección en PNS-67).
- **Impacto:** bajo; limpieza y posible pérdida de personalizaciones al actualizar.
- **Prueba en el laboratorio:** sí (funcional), en la actualización:
  - en el log, las líneas de `_process_end` sobre XML ID `mcp_*`;
  - después, `SELECT name FROM ir_model_data WHERE module = 'pns_ai_mcp' AND name LIKE '%mcp%'` para
    ver qué queda;
  - menús de Safe operations, Logs y Contexts sin duplicar;
  - si quedan los servidores `mcp_test`, `brave_search` y `sequential_thinking`.

### PNS-89 — `/pns_ai_mcp/key_pin/stop` sin CSRF

- **Gravedad:** Baja · **Estado:** NUEVO (relacionado con PNS-83).
- **Ubicación:** `pns_ai_mcp/controllers/key_pin.py:35-54` (`type='http'`, `POST`, `csrf=False`).
- **Comportamiento:**
  - Una página de otro origen puede hacer que el navegador de un AI Administrator envíe el POST.
  - El único efecto es cerrar la mesa cuyo token se envíe y avisar por el bus. El token es aleatorio y
    vive en el `sessionStorage` de la pestaña (`key_pin_desk_v14.js:20-30`), así que sin conocerlo no
    hay efecto.
  - Probablemente se usa con `sendBeacon` al cerrar la pestaña, que puede llevar el `csrf_token` en el
    cuerpo.
- **Impacto:** mínimo hoy; es una excepción de CSRF innecesaria en una función sensible.
- **Prueba en el laboratorio:** no (revisión de código).

### Candidatos evaluados y descartados

- **`base.export_data` sobrescrito para todos los modelos** (`pns_ai_mcp/models/secret_native_export.py:28-42`):
  - **Efecto:** después de la exportación estándar, vacía las columnas cuya ruta acaba en un campo de
    `_pns_secret_fields` (hoy solo en 4 modelos de `pns_ai_mcp`). La firma es la de Odoo 14
    (`odoo/models.py:956`).
  - **Coste:** recorre las rutas exportadas (columnas × profundidad) en cada exportación y solo
    reescribe filas si hay alguna columna secreta. Es despreciable.
  - **Efecto lateral:** otro módulo que use `export_data` por código recibe vacíos en esas columnas,
    que es lo que se busca.
  - No es un hallazgo.
- **Skill `analisis_financiero` retirada:** se borra en cada `-u` por la semilla XML (ver PNS-67).
- **`ai.execution.engine.choose`** (`models/ai_execution_engine.py:266-285`, público):
  - cualquier usuario autenticado puede lanzar por RPC una pregunta de elección cerrada a la cadena de
    decisión con la clave de la empresa;
  - el resultado no se puede serializar y la llamada acaba en error, pero el coste ya se ha producido;
  - impacto marginal (protocolo de respuesta cerrada); se cita como observación de PNS-29.

## Compatibilidad con Odoo 14

Objetivo: Odoo 14 con Python 3.7 y las librerías de la imagen oficial (la del laboratorio,
`odoo-dev:14-lab_pns_ai`).

**Método:**
- Análisis AST de todos los `.py` de los tres módulos (script en el scratchpad de la sesión): genéricos
  integrados, uniones `|`, `typing` 3.8+, stdlib 3.8+, `dataclass` y `zip(strict=)`, walrus y f-string
  `{x=}`, con la clasificación pedida. Se completa con Grep de otras API (`ast.get_source_segment`,
  `datetime.UTC`, `missing_ok=`, `ET.indent`, `include_extras`, `math.comb`, `itertools.pairwise`…).
- Comprobación con `python3 -c` en la imagen (`docker run --rm --entrypoint python3`, sin Odoo ni BD)
  de la forma del AST de 3.7 y de los atributos de las librerías usadas.

Versiones en la imagen: **Python 3.7.3**, PyPDF2 1.26.0, openpyxl 3.1.2, requests 2.21.0 (urllib3
1.24.1), reportlab 3.5.13, Pillow 5.4.1, lxml 4.3.2, pdfminer 20181108. No están `pypdf`, `fitz`
(PyMuPDF) ni `pdftoppm`.

**Resumen:** FALLA AL IMPORTAR 1 · FALLA AL EJECUTAR 2 · SEGURO 22. Los tres fallos son PNS-81.

### a) Python

| Archivo:línea | Uso | Clasificación | Efecto en Odoo 14 / motivo | Corrección mínima |
|---|---|---|---|---|
| `pns_ai_mcp/controllers/mcp_decorators.py:169` | `-> tuple[bool, Optional[str]]` (3.9) | **FALLA AL IMPORTAR** | Anotación de retorno evaluada al definir la función; sin `from __future__ import annotations`. No se importan `pns_ai_mcp` ni `pns_ai_chatboo`. | `Tuple[bool, Optional[str]]` (ya importa `typing`) o añadir `from __future__ import annotations`. |
| `pns_ai_mcp/utils/relaxaicode_recipe.py:507` | `ast.get_source_segment` (3.8) | **FALLA AL EJECUTAR** | Desde `tools_relaxaicode.py:1867`, sin protección: la herramienta devuelve error si el código define una función de nivel superior con un parámetro de fecha. Desde `:1252` está dentro de `try` (ver fila SEGURO). | `getattr(ast, 'get_source_segment', None)` y, si no existe, usar `src`, como ya hace con `or src`. |
| `pns_ai_mcp/controllers/tools_relaxaicode.py:1252` | misma llamada | SEGURO | `try/except Exception` (`:1238-1257`): solo se pierde la coerción de fechas. | — |
| `pns_ai_mcp/controllers/mcp_decorators.py:13` | `typing.get_origin`, `get_args` (3.8) | SEGURO | `try/except ImportError` con alternativa propia. | — |
| `pns_ai_mcp/controllers/mcp_decorators.py:103` | `get_type_hints(..., include_extras=True)` (3.9) | SEGURO | Dentro de `try/except Exception` (`:90-160`): esquema vacío. Ninguna herramienta entra en esa rama (sin cambios desde §7.3). | — |
| `pns_ai_mcp/controllers/context_builder.py:359` | `zoneinfo` (3.9) | SEGURO | `try/except` con alternativa `dateutil.tz`. Corrige el punto de §7.3 del informe (el prompt prometía `ZoneInfo`). | — |
| `pns_ai_mcp/utils/user_time.py:18` | `zoneinfo` | SEGURO | `try/except` con alternativa `pytz`. | — |
| `pns_ai_chatboo/utils/chatboo_display_time.py:70` | `zoneinfo` | SEGURO | `try/except` con alternativa `pytz`. | — |
| `pns_ai_mcp/controllers/validators.py:330, 466, 619, 1812` (4 filas) | `ast.unparse` (3.9) | SEGURO | `try/except Exception`: devuelve el código sin reparar. Las reparaciones automáticas no se aplican en 3.7 (igual que §7.3). | — |
| `pns_ai_mcp/utils/relaxaicode_recipe.py:177, 351` (2 filas) | `ast.unparse` | SEGURO | `try/except`: devuelve el código original sin quitar literales ni definiciones duplicadas. | — |
| `pns_ai_mcp/utils/response_anti_echo.py:119` | unión `X \| Y` en anotación | SEGURO | Archivo con `from __future__ import annotations`. | — |
| `pns_ai_mcp/controllers/formatters.py:284` | `ET.indent` (3.9) | SEGURO | `try/except AttributeError`: XML sin sangría. | — |
| `pns_ai_mcp/controllers/validators.py:434, 784, 1423` | `isinstance(..., ast.Constant)` sin `ast.Str`/`ast.Num` | SEGURO (degrada) | En 3.7 los literales son `Str`/`Num`/`NameConstant` (comprobado en la imagen). No falla. La reparación de `%` no se aplica y un `key=` literal en `sorted` se rechaza. Las comprobaciones de seguridad del validador sí contemplan 3.7 (`:1084-1085` con `Index`, `:1139-1142`, `:2092-2095`, `:2182-2185`, `:2207-2210`). | Aceptar también `ast.Str`/`ast.Num`. |
| `pns_ai_mcp/controllers/validators.py:2330-2337, 2356-2358, 2545-2547` | `.slice` como `Constant`/`Str` | SEGURO (sin uso) | En 3.7 el índice es `ast.Index(Str)` y no coincide, pero está dentro de `detect_dangerous_operations`, que solo se importa (`main.py:91`) y no se llama. Además, `:2335` (`elif` al nivel de `if isinstance(node.value, ast.Call)`) lanzaría `AttributeError` en cualquier asignación que no sea una llamada. | Borrar la función o corregirla si se vuelve a usar. |
| `pns_ai_mcp/utils/relaxaicode_recipe.py:32, 79, 97, 99` | `ast.Constant` | SEGURO (degrada) | `literal_eval` va antes. En 3.7, un `None` literal (`NameConstant`) hace que no se recupere el dato extraído. | Aceptar `ast.NameConstant`. |

Sin coincidencias: genéricos integrados fuera de la línea 169, uniones `|` evaluadas, `typing` 3.8+
sin protección, `cached_property`, `functools.cache`, `@lru_cache` sin paréntesis,
`removeprefix`/`removesuffix`, `math.prod/isqrt/dist`, `importlib.metadata`, `shlex.join`,
`statistics.fmean`, `asyncio.to_thread`, `zip(strict=)`, `dict | dict`, f-string `{x=}`, `dataclass`
con `kw_only`/`slots` y walrus. Los 65 archivos con `from __future__ import annotations` exigen
Python ≥ 3.7. Con 3.6 no cargarían, pero 3.6 queda fuera del objetivo.

### b) Librerías

| Archivo:línea | Uso | Versión en la imagen | Clasificación | Efecto / alternativa |
|---|---|---|---|---|
| `pns_base/utils/pdf_io.py:94` | `ImageOps.exif_transpose` (Pillow ≥ 6.0) | Pillow 5.4.1 (no existe, comprobado) | **FALLA AL EJECUTAR** | `_open_picture` lanza `AttributeError`. `as_picture`, `picture_size`, `shrink_picture`, `turn_picture` y `picture_pdf` lo capturan y devuelven `None`. Consecuencias: `remote_image` da 404 y Chatboo reenvía las imágenes sin reescalar (PNS-81). **Corrección:** `fn = getattr(ImageOps, 'exif_transpose', None); return (fn(image) if fn else image), kind`. Sin girar por EXIF, pero funciona. |
| `pns_base/utils/pdf_io.py:45-60` | `pypdf.PdfReader/PdfWriter` con caída a `PyPDF2.PdfFileReader/PdfFileWriter(strict=False)` | PyPDF2 1.26.0; `pypdf` ausente | SEGURO | `except ImportError` → PyPDF2. `PdfFileReader` acepta `strict` y tiene `.pages` (comprobado). |
| `pns_base/utils/pdf_io.py:63-79` | `add_page`/`addPage`, `rotate`/`rotateClockwise`, `get_object`/`getObject` | PyPDF2 1.26.0 | SEGURO | `getattr` con las dos variantes; en la imagen existen `addPage` y `rotateClockwise` (comprobado). |
| `pns_base/utils/pdf_io.py:237` | `extract_text`/`extractText` | PyPDF2 1.26.0 | SEGURO | `getattr`; existe `extractText`. |
| `pns_base/utils/pdf_io.py:215` | `pdfminer.high_level.extract_text` | pdfminer 20181108 (no existe, comprobado) | SEGURO | `except ImportError` → PyPDF2. Extrae peor el texto de algunos PDF. |
| `pns_base/utils/pdf_io.py:201, 368, 385` | `fitz` (PyMuPDF), `pdftoppm` | ausentes | SEGURO | Opcionales (`except ImportError`, `shutil.which`). Sin ellos, los PDF escaneados no se convierten en imágenes para el modelo de visión. |

Sin problemas de API:
- **openpyxl 3.1.2:** solo `Workbook`, `load_workbook`, `styles` y `utils.get_column_letter`.
- **reportlab 3.5.13:** `platypus`, `graphics.charts`, `lib`; `Table(splitByRow=)` existe (comprobado).
- **requests 2.21.0 / urllib3 1.24.1:** `allow_redirects`, `is_redirect`, `iter_content`,
  `exceptions.SSLError/RequestException`. No usa `JSONDecodeError` de requests ni `Retry(allowed_methods=)`.
- **lxml:** sin uso directo en los tres módulos.
