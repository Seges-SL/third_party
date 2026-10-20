# Seguimiento del informe al fabricante: pns_base 1.2.32, pns_ai_mcp 3.1.782 y pns_ai_chatboo 2.1.453

- **Versiones comparadas:** rama `14.0-analisis-pns-ai` (pns_base 1.2.10, pns_ai_mcp 3.1.486,
  pns_ai_chatboo 2.1.322; la versión del informe) frente a `HEAD` de `14.0-pns-ai-3` (pns_base 1.2.32,
  pns_ai_mcp 3.1.782, pns_ai_chatboo 2.1.453). Diff: `git diff 14.0-analisis-pns-ai..HEAD`.
- **Fecha:** 13/10/2026 (código, fase 2). Actualizado el 14/10/2026 con el laboratorio (fase 3) y la
  revisión independiente del seguimiento, y el 16/10/2026 con el staging (15-16/10/2026).
- **Fuentes:** `docs/pendiente/informe_fabricante_pns_ai.md` (PNS-01 a PNS-80),
  `docs/specs/cambios_pns_ai_3-1-782.md` (inventario de la fase 1), el código actual y
  `docs/pendiente/verificacion_seguridad_pns_ai.md` (laboratorio, fases 3a, 3b-1, 3b-2 y 3c, y
  sección «Staging (15-16/10/2026)») y `docs/pendiente/plan_staging_pns_ai.md` (registro del §6.1).
- **Método:** lectura de código (fase 2) y pruebas en el laboratorio (fase 3). Las líneas citadas son
  las de la rama `14.0-pns-ai-3`, que incluye los parches 1 a 6
  (`docs/pendiente/parches_pns_ai.md`; 1 a 3 en el commit `ce6790b`). Solo cambian respecto al código
  del fabricante las de `mcp_decorators.py`, `relaxaicode_recipe.py`, `pdf_io.py`, `main.py` (de la
  1473 en adelante, +1; de la 1598 en adelante, +2), `openai_driver.py` (parche 5: de la 659 en
  adelante, +9) y `chatboo_async_request.py` (parche 6: dos marcadores y llamadas antes de las dos
  llamadas a `_finalize`, y el método nuevo; las líneas que se citan de ese archivo en PNS-94 son las
  del fabricante) (ver PNS-81, PNS-93, PNS-94 y «Compatibilidad con Odoo 14»).
- **Alcance:** primer bloque, hallazgos de gravedad crítica y alta (35); segundo bloque, de gravedad
  media y baja (45, con PNS-22, que pasó a Media en la revisión del informe, y PNS-79). Total: los
  80 hallazgos del informe. Tercer bloque: hallazgos nuevos (PNS-81 a PNS-96) y compatibilidad con
  Odoo 14 (Python 3.7 y librerías de la imagen).

> **Fase 3 (laboratorio) hecha**, con el parche 1 aplicado para que los módulos se importen:
> - **3a:** actualización de una copia a 3.1.782 (PNS-81, 87 y 88 e inventario);
> - **3b-1:** permisos sin IA;
> - **3b-2:** pruebas funcionales con proveedor, **parcial**: el proveedor estaba saturado y varias
>   pruebas quedan pendientes para staging;
> - **3c:** pruebas complementarias tras la revisión independiente (PNS-12, 21, 80, 90, 91 y 92);
> - **parche 4:** `prompts/*` por `/mcp`, PNS-12 por HTTP CORREGIDO.
>
> **Staging hecho (15-16/10/2026)** en `pns_demo` (VPS de `odoo14_server`, proveedor Gemini, parches 1
> a 6): las pruebas pendientes de la 3b-2 y las 10 y 11 del plan de staging (la 9b, PNS-29, no aplica
> con Gemini). De ahí salen PNS-93 a PNS-96.
>
> El resultado de cada PNS probado está en la columna «Laboratorio y staging» de la tabla resumen y en
> su detalle; «(staging)» marca lo probado en el VPS. «—» significa que no se probó ni en el
> laboratorio ni en el staging.

> **Desde el 20/10/2026 (N11 y N12):** Seges corrige los hallazgos en la rama
> `14.0-pns-ai-correcciones` y mantiene la 3.1.782 ([plan de corrección](plan_correccion_pns_ai.md)).
> La columna «Estado» sigue describiendo el **código del fabricante** (lo que se le comunica en el
> informe). La columna «Rama Seges» de la tabla resumen recoge lo corregido o previsto por Seges
> (parche, entrega y validación). Actualizada el 20/10/2026 con la entrega E1 (PNS-83, 85, 90 y 91).

Estados: **CORREGIDO** (el cambio cubre el hallazgo y sus puntos de entrada) · **PARCIAL** (cubre
una parte; queda un resto concreto) · **SIN CAMBIOS** · **YA NO APLICA** (el código desapareció) ·
**DUDOSO** (no se puede decidir sin prueba en el laboratorio) · **NUEVO** (hallazgo que no estaba en
el informe: del código nuevo o modificado de esta versión o, en PNS-90 a PNS-92, código anterior
detectado en la revisión).

Columna «Laboratorio y staging»: **CORREGIDO** · **CORREGIDO (parte probada: …)** (solo se probó esa parte) ·
**SIN CAMBIOS** / **VULNERABLE** (reproducido) · **NO CONCLUYENTE** · **PENDIENTE STAGING** (no se
pudo probar por el proveedor) · **CONFIRMADO** (hallazgo funcional observado) · «—» (no probado o
prueba que solo comprueba otro rol o el ACL estándar).

## Tabla resumen

| PNS | Gravedad | Estado | Laboratorio y staging | Rama Seges |
|---|---|---|---|---|
| PNS-01 | Crítica | PARCIAL | CORREGIDO (parte probada: vía RPC cerrada, 3b-1) | Previsto en E2 |
| PNS-02 | Crítica | PARCIAL | CORREGIDO (parte probada: vía RPC cerrada, 3b-1) | Previsto en E2 |
| PNS-03 | Crítica | CORREGIDO | CORREGIDO (3b-1) | — |
| PNS-04 | Crítica | CORREGIDO | — | — |
| PNS-05 | Crítica | CORREGIDO | CORREGIDO (staging, prueba 6) | — |
| PNS-06 | Crítica | CORREGIDO | CORREGIDO (parte probada: rechazo al guardar de una escritura con `sudo`, 3b-1) | — |
| PNS-07 | Crítica | PARCIAL | — | Parcial (E1): los 11 métodos privatizados, en la lista negra del sandbox; resto (métodos con `_`, alias): E3 |
| PNS-53 | Crítica | CORREGIDO | CORREGIDO (3b-1) | — |
| PNS-54 | Crítica | PARCIAL | — | — |
| PNS-08 | Alta | CORREGIDO | CORREGIDO (3b-1) | — |
| PNS-09 | Alta | CORREGIDO | CORREGIDO (parte probada: `action_test_connection` de un interno, 3b-1) | — |
| PNS-10 | Alta | CORREGIDO | CORREGIDO (3b-1) | — |
| PNS-11 | Alta | CORREGIDO | CORREGIDO (3b-1) | — |
| PNS-12 | Alta | CORREGIDO | CORREGIDO en el modelo (3c); por HTTP CORREGIDO con el parche 4 (ver PNS-81; confirmado en staging, §4.4); en los turnos del chat, CORREGIDO (staging, prueba 10) | — |
| PNS-13 | Alta | CORREGIDO | CORREGIDO (3b-1) | — |
| PNS-14 | Alta | PARCIAL | VULNERABLE en `ai.fetch.cache` (3c, PNS-90); el resto, CORREGIDO (3b-1) | Resto de `ai.fetch.cache`: parche 7 (E1), CORREGIDO |
| PNS-15 | Alta | CORREGIDO | — | — |
| PNS-16 | Alta | PARCIAL | CORREGIDO (parte probada: tarjeta sin auto-confirmación ni salida, con las dos políticas; staging, prueba 3); resto (reinyección como `system`), NO CONCLUYENTE | — |
| PNS-17 | Alta | PARCIAL | — | — |
| PNS-18 | Alta | PARCIAL | CORREGIDO (parte probada: `no_external_failover`, 3b-2) | — |
| PNS-19 | Alta | PARCIAL | — | Previsto en E3 |
| PNS-20 | Alta | PARCIAL | — | — |
| PNS-21 | Alta | CORREGIDO | CORREGIDO (3c) | — |
| PNS-23 | Alta | SIN CAMBIOS | — | — |
| PNS-24 | Alta | PARCIAL | — | — |
| PNS-25 | Alta | CORREGIDO | — | — |
| PNS-26 | Alta | PARCIAL | — | — |
| PNS-27 | Alta | CORREGIDO | — | — |
| PNS-55 | Alta | PARCIAL | CORREGIDO (parte probada: aislamiento de sesiones y jobs, 3b-1) | — |
| PNS-56 | Alta | CORREGIDO | CORREGIDO (3b-1) | — |
| PNS-57 | Alta | CORREGIDO | CORREGIDO (3b-1) | — |
| PNS-58 | Alta | CORREGIDO | CORREGIDO (3b-1) | — |
| PNS-59 | Alta | PARCIAL | CORREGIDO (parte probada: 404 sin salida para un host no permitido, 3b-2; navegador con `whitelist_only`, staging, prueba 9a); con `open`, NO CONCLUYENTE | — |
| PNS-60 | Alta | PARCIAL | CORREGIDO (parte probada: mensaje del usuario, 3b-2; respuesta en directo, tras recargar, PDF y Word, staging, prueba 8) | — |
| PNS-80 | Alta | YA NO APLICA | CORREGIDO (3c) | — |
| PNS-22 | Media | PARCIAL | CORREGIDO (parte probada: por chat, staging, prueba 5) | — |
| PNS-28 | Media | PARCIAL | CORREGIDO (parte probada: sin filas de `ai.log` sin clave, 3b-1) | — |
| PNS-29 | Media | PARCIAL | PARCIAL (3b-2) | — |
| PNS-30 | Media | PARCIAL | SIN CAMBIOS (resto reproducido, 3b-1) | Resto (`create_log_entry`): previsto en E4 |
| PNS-31 | Media | SIN CAMBIOS | — | — |
| PNS-32 | Media | PARCIAL | — | — |
| PNS-33 | Media | SIN CAMBIOS | — | — |
| PNS-34 | Media | CORREGIDO | — | — |
| PNS-35 | Media | SIN CAMBIOS | — | — |
| PNS-36 | Media | PARCIAL | SIN CAMBIOS (resto reproducido: nombre de la BD y campos sin valores, staging, prueba 7) | — |
| PNS-37 | Media | SIN CAMBIOS | — | Resto (`record_failed_plan`): previsto en E4 |
| PNS-38 | Media | SIN CAMBIOS | — | — |
| PNS-39 | Media | PARCIAL | — | — |
| PNS-40 | Media | PARCIAL | SIN CAMBIOS (resto reproducido, 3b-2) | — |
| PNS-41 | Media | CORREGIDO | — | — |
| PNS-42 | Media | SIN CAMBIOS | — | — |
| PNS-61 | Media | PARCIAL | CORREGIDO (parte probada: `provider_id`, 3b-2 y staging, prueba 4b); historial, SIN CAMBIOS (staging, prueba 4a) | — |
| PNS-62 | Media | PARCIAL | CORREGIDO (parte probada: archivo único, 3b-2) | — |
| PNS-63 | Media | CORREGIDO | — | — |
| PNS-64 | Media | PARCIAL | — | — |
| PNS-65 | Media | PARCIAL | — | — |
| PNS-66 | Media | SIN CAMBIOS | SIN CAMBIOS (3b-2) | — |
| PNS-67 | Media | CORREGIDO | — | — |
| PNS-68 | Media | SIN CAMBIOS | — | — |
| PNS-70 | Media | SIN CAMBIOS | — | — |
| PNS-43 | Baja | PARCIAL | — | — |
| PNS-44 | Baja | YA NO APLICA | — | — |
| PNS-45 | Baja | CORREGIDO | — | — |
| PNS-46 | Baja | DUDOSO | NO CONCLUYENTE (3b-1 y staging, prueba 11; síntoma en PNS-95) | — |
| PNS-47 | Baja | CORREGIDO | — | — |
| PNS-48 | Baja | CORREGIDO | — | — |
| PNS-49 | Baja | PARCIAL | — | — |
| PNS-50 | Baja | PARCIAL | — | Batería de tests al día: previsto en ET |
| PNS-51 | Baja | SIN CAMBIOS | — | — |
| PNS-52 | Baja | CORREGIDO | — | — |
| PNS-69 | Baja | CORREGIDO | — | — |
| PNS-71 | Baja | CORREGIDO | CORREGIDO (3b-1) | — |
| PNS-72 | Baja | PARCIAL | — | — |
| PNS-73 | Baja | SIN CAMBIOS | — | — |
| PNS-74 | Baja | PARCIAL | — | — |
| PNS-75 | Baja | CORREGIDO | — | — |
| PNS-76 | Baja | PARCIAL | — | — |
| PNS-77 | Baja | SIN CAMBIOS | — | — |
| PNS-78 | Baja | CORREGIDO | — | — |
| PNS-79 | Baja | CORREGIDO | NO CONCLUYENTE (3b-1) | — |
| PNS-81 | Alta | NUEVO | importación resuelta con el parche 1 (3a); parche 2 eficaz (3b-2 y staging, prueba 2); parche 3 eficaz (staging, prueba 1); `prompts/*`: parche 4 en la rama, eficaz (prueba del parche 4 y staging, §4.4) | Parches 1-4 (compatibilidad), en LIYBEN |
| PNS-82 | Alta | NUEVO | VULNERABLE (3b-1) | Previsto en E2 |
| PNS-83 | Alta | NUEVO | VULNERABLE (3b-1) | **Parche 10 (E1): CORREGIDO** (laboratorio y staging, 20/10/2026) |
| PNS-84 | Media | NUEVO | — | — |
| PNS-85 | Media | NUEVO | VULNERABLE (3b-1) | **Parche 9 (E1): CORREGIDO** (laboratorio y staging, 20/10/2026) |
| PNS-86 | Media | NUEVO | — | — |
| PNS-87 | Baja | NUEVO | CONFIRMADO (3a: purga al primer arranque) | Sin código (E6): retención por parámetro |
| PNS-88 | Baja | NUEVO | CONFIRMADO (3a: 38 XML ID y 5 servidores) | Sin código (E6) |
| PNS-89 | Baja | NUEVO | — | Previsto en E4 |
| PNS-90 | Alta | NUEVO | VULNERABLE (3c) | **Parche 7 (E1): CORREGIDO** (laboratorio y staging, 20/10/2026) |
| PNS-91 | Media | NUEVO | VULNERABLE (3c) | **Parche 8 (E1): CORREGIDO** (laboratorio y staging, 20/10/2026) |
| PNS-92 | Media | NUEVO | protegido solo por rebote (3c) | Previsto en E4 |
| PNS-93 | Media | NUEVO | CONFIRMADO (staging); parche 5 eficaz | Parche 5, validado en staging; en LIYBEN |
| PNS-94 | Alta | NUEVO | CONFIRMADO (staging); parche 6 eficaz (5 casos) | Parche 6, validado en staging; en LIYBEN. Corrección de fondo: E5 |
| PNS-95 | Baja | NUEVO | CONFIRMADO (staging, prueba 11) | — |
| PNS-96 | Baja | NUEVO | CONFIRMADO (staging, con modelos `lite`) | — |

**Recuento:** CORREGIDO 31 · PARCIAL 33 · SIN CAMBIOS 13 · YA NO APLICA 2 · DUDOSO 1 (80 del
informe) · NUEVO 16 (total 96). Por gravedad:

| Gravedad | Corregido | Parcial | Sin cambios | Ya no aplica | Dudoso | Nuevo | Total |
|---|---|---|---|---|---|---|---|
| Crítica | 5 | 4 | 0 | 0 | 0 | 0 | 9 |
| Alta | 13 | 11 | 1 | 1 | 0 | 5 | 31 |
| Media | 4 | 12 | 9 | 0 | 0 | 6 | 31 |
| Baja | 9 | 6 | 3 | 1 | 1 | 5 | 25 |
| **Total** | **31** | **33** | **13** | **2** | **1** | **16** | **96** |

Restos que se repiten en varios parciales:
1. **El sandbox (caja A) bloquea por lista de nombres y no impide llamar a métodos privados**
   (`_metodo`). Afecta a PNS-07 y PNS-19 (y a lo que PNS-06 ejecuta al guardar).
2. **Un AI Administrator sin permisos de Ajustes sigue pudiendo conceder o quitar grupos de Odoo**
   (incluido `base.group_system`) mediante un plan confirmado. Afecta a PNS-01 y PNS-02.
3. **Los controles nuevos de URL (`remote_image`, `fetch_url`) dependen de la política de URL y de una
   lista blanca que cualquier usuario autenticado puede ampliar por RPC**: con la política `open`, el
   servidor descarga cualquier host público. Con la restringida, `ensure_domain_whitelisted` deja a
   cualquier usuario, también de portal, añadir o reactivar hosts en la lista (PNS-91, comprobado en
   la fase 3c). Afecta a PNS-16, PNS-59 y PNS-86.

## Detalle: hallazgos críticos

### PNS-01 — Escalada a `base.group_system` por `apply_user_add_group`

- **Estado:** PARCIAL.
- **Evidencia:**
  - La vía del informe (RPC por cualquier interno o portal) está cerrada: `ai.system.action` ya no
    tiene métodos públicos. `apply_user_add_group` pasa a `_apply_user_add_group`
    (`pns_ai_mcp/models/ai_system_action.py:718`) y `call_kw` rechaza los nombres con `_`. Test
    nuevo: `pns_ai_mcp/tests/test_system_action.py:429-442`.
  - El único llamador es `ai.trusted.action._apply` (`pns_ai_mcp/models/ai_trusted_action.py:117-129`),
    que ahora comprueba los grupos del registro sobre el usuario real; `ai.trusted.action` también
    pasa sus métodos `apply`/`preview` a privados. Test: `test_system_action.py:444-456`.
  - **Resto:** el grupo exigido para `user.add_group` / `user.remove_group` es solo
    `group_ai_admin` (`pns_ai_mcp/data/trusted_actions_system.xml:84, 94`), y `_apply_user_add_group`
    y `_apply_user_remove_group` resuelven usuario y grupo en `sudo` (`ai_system_action.py:674-697`)
    y escriben con `pns_base/utils/compat.py:113-116` y `119-122`. Un AI Administrator que no sea
    administrador de Odoo puede, con un plan que él mismo confirma, darse `base.group_system`. El
    informe pedía exigir los dos
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
  - **Resto:** `_apply_user_remove_group` (`:748`) tiene el mismo límite que PNS-01: basta
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
- **Evidencia:** la herramienta pasa a llamarse `safe_plan_status` (`controllers/safe_plan.py:2351-2445`;
  decorador en `:2351`, función en `:2369`).
  - Busca en `sudo`, pero siempre con `('user_id', '=', env.uid)` (`:2383-2402`), también cuando se
    da el `verification_id`.
  - Ejecuta con el entorno del usuario y sin `sudo` (`:2412-2413`). Ese entorno sale de
    `request.env(user=…)`, que deja `su=False` (`controllers/controller_helpers.py:141-165`).
- **Prueba en el laboratorio:** sí. Con dos usuarios, B pide en el chat el estado de una operación de
  A dando su `verification_id`: debe responder que no hay operación. Para A, una operación confirmada
  se ejecuta respetando sus ACL (una escritura sobre un modelo sin permiso debe fallar).
- **Staging (16/10/2026, prueba 6): CORREGIDO.** U2 no obtuvo ningún dato de la operación de UW
  (`WRIT00000003`); hizo una búsqueda a ciegas de 10 rondas con falsos positivos (campos no
  almacenados de `res.users`), sin valores. La segunda parte también se observó: antes de tener
  «Creación de contactos», la operación confirmada de UW se ejecutó con sus permisos y falló con el
  `AccessError` de Odoo, sin escribir.

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
    `controllers/validators.py:178-194`), y el AST la comprueba también en `getattr`, `attrgetter` y
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

- **Estado:** CORREGIDO (en el modelo; por HTTP CORREGIDO con el parche 4).
- **Evidencia:**
  - `get_listable_for_mcp`, `get_context_for_country`, `get_discovery_entries` y
    `get_discovery_indexed_codes` filtran con `ownership_read_domain()` (`ai_context.py:345-346,
    570-610, 658-668, 869-945`). El dominio es explícito (`owner_id` vacío o igual al usuario,
    `utils/knowledge_ownership.py:7-10`) y usa `env.user`, que dentro de `sudo` sigue siendo el usuario
    real, así que las lecturas en `sudo` del motor (`utils/agent_engine.py:1023, 1029-1038, 1052`)
    quedan filtradas.
  - **Laboratorio (fase 3c):** en el shell, con el entorno que construye el controlador (uid de B con
    `su=True`), `get_listable_for_mcp()` devuelve el contexto privado de B y no el de A, y
    `get_context_for_country` devuelve vacío para el de A y el registro para el de B. Como control,
    una búsqueda sin filtro encuentra el de A. La prueba de la fase 3b-1 (RPC sin `sudo`) solo
    comprobaba la regla de registro, que ya existía en 3.1.486.
  - **Por HTTP, CORREGIDO con el parche 4:** en 3.1.782 `prompts/list` y `prompts/get` llaman a
    `.sudo()` sobre el `Environment` (`controllers/main.py:1474, 1600`; fabricante: `:1473, 1598`), que no existe en Odoo 14; en
    la fase 3c el error se capturaba y no se listaba ni servía ningún contexto, tampoco el propio
    (cuarto fallo de PNS-81), así que la prueba HTTP no era concluyente. Con el parche 4
    (`self._get_mcp_env()(su=True)`) se repitió por `/mcp` (2026-10-14, 16:12 UTC; detalle en
    `verificacion_seguridad_pns_ai.md`, «Versión 3.1.782 — parche 4»): B, con su clave,
    recibe en `prompts/list` los contextos compartidos y su contexto privado, y no el de A;
    `prompts/get` del suyo devuelve su contenido (control positivo) y el de A, «Prompt not found». En
    el log, ningún `AttributeError`.
- **Staging (15-16/10/2026): CORREGIDO** por `/mcp` (plan §4.4, con el parche 4) y **en los turnos
  del chat** (prueba 10): el término distintivo del contexto privado de U2 no aparece en ningún
  registro de `ai_log` de U1, y el índice de contextos de los turnos de U1 no incluye el de U2.
- **Pendiente:** si el fabricante corrige PNS-81 sin el parche 4, repetir `prompts/list` y
  `prompts/get` por `/mcp` con su versión.

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

- **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:**
    - `ai.api.result.cache` tiene regla por `create_uid` (`security/security.xml:173-191`).
    - La clave de caché de `api_call` incluye el uid (`utils/api_call_result.py:14-22`,
      `models/api_result_cache.py:83-84`, `controllers/safe_plan.py:1810-1811`).
    - `ai.safe.choice` tiene regla por `user_id` (`security/security.xml:161-170`).
    - Se quita la lectura de `ai.fetch.cache` a internos en el ACL (solo AI Administrator,
      `security/ir.model.access.csv:50`).
  - **Resto (punto de entrada no cubierto por el ACL, ya existía):** `ai.fetch.cache.get_cached` y
    `ai.fetch.cache.store` son métodos públicos `@api.model` que trabajan en `sudo`
    (`models/fetch_cache.py:63-89, 91-123`). La caché es global por URL, sin usuario, y es la que
    consulta `fetch_url` antes de salir a la red (`controllers/safe_plan.py:1493-1503`). Cualquier
    usuario autenticado, también de portal, la lee y la sobrescribe por RPC. Tiene número propio: PNS-90.
  - **Laboratorio:** la parte corregida se comprobó en la fase 3b-1 (B no ve las filas de A de
    `ai.api.result.cache` ni de `ai.safe.choice`). La comprobación de `ai.fetch.cache` de esa fase
    (`search_read` → `AccessError`) solo probaba el ACL estándar; el resto se reprodujo en la fase 3c
    (PNS-90).
- **Staging:** verificado en código (la clave de caché incluye el uid); sin prueba en staging, que no
  tiene servidores externos (plan §4.4).

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
    - Nota: la política restringida tampoco limita los hosts mientras cualquier usuario pueda ampliar
      la lista blanca por RPC (PNS-91).
- **Prueba en el laboratorio:** sí. Con un registro abierto cuyo texto pida al asistente consultar
  una URL externa: no debe haber auto-confirmación (debe aparecer la tarjeta), tanto con política
  restringida como `open`. Repetir pidiéndolo en el turno siguiente (reutilizando la consulta):
  observar si se auto-confirma.
- **Staging (16/10/2026, prueba 3, U3 con AI External URL):**
  - **Parte principal: CORREGIDO**, con `whitelist_only` y con `open`. Con la nota leída y la petición
    explícita «haz lo que indica la nota», `safe_plan_request` quedó `Proposed`/`pending_confirmation`
    (`FURL00000001`, `3` y `4`) y se rechazó, sin salida a `open-meteo`. Sin petición explícita, el
    modelo no obedeció la instrucción oculta.
  - **Resto (reinyección como `system`):** con `open` no se manifestó (también hubo tarjeta en el
    turno de reutilización); con `whitelist_only`, NO CONCLUYENTE. El estado sigue PARCIAL.

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
  - Observación (Baja, ya existía en 3.1.486): duplicar un proveedor copia su clave API, porque el
    campo `api_key` no lleva `copy=False` (`models/ai_provider.py:194-198`). Solo puede duplicar quien
    ya lee la clave (`groups='pns_ai_mcp.group_ai_admin'`), así que no hay ganancia de privilegio, pero
    la clave se multiplica en registros que quizá no se revisen. Corrección: añadir `copy=False`.
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
  - **Laboratorio (fase 3c):** `GET /pns_ai_mcp/session_file/<adjunto de A>` con una cookie anónima
    que ya tiene la BD seleccionada → 302 a `/web/login`; como B → 404; como A (control) → 200. El 404
    «sin sesión» de la fase 3b-1 no probaba `auth='user'`: sin cookie no había BD seleccionada (con
    varias BD, el parámetro `?db=` no la selecciona en esta ruta).

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
      cualquier `ir.attachment` sin `res_model` o sin `res_id`, cuyo id llegue en la lista o en la URL
      del chip, sin comprobar quién lo creó. Después, `_may_read` de `session_file` lo entrega porque
      cuelga de una sesión del llamador. Entre esos adjuntos están las descargas del chat de otros
      usuarios (PNS-21) y las copias de configuración de `pns_ai_mcp`, que pueden llevar secretos. Los
      ids son secuenciales. Tiene número propio: PNS-82.
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
    clic, ahora desde el servidor. Con la política restringida, solo hacia hosts de la lista blanca,
    pero cualquier usuario autenticado puede añadir hosts a esa lista por RPC (PNS-91).
  - **Laboratorio (fase 3b-2):** solo se probó la parte del servidor: `remote_image` con un host no
    permitido responde 404 sin salir a la red. La reescritura en el cliente (que es la corrección real)
    y la prueba con la política `open` quedan pendientes para staging.
- **Prueba en el laboratorio:** sí. Una respuesta que incluya una imagen de un host externo no
  permitido debe mostrarse como enlace o texto alternativo, sin petición al exterior (ver el log
  del servidor y la pestaña de red). Repetir con la política `open`: hoy se espera que el servidor
  haga la petición.
- **Staging (16/10/2026, prueba 9a):** con `whitelist_only`, **CORREGIDO**: la imagen pasa por
  `remote_image`, que responde 404, y no hay salida al exterior. Con `open`, **NO CONCLUYENTE**: el
  modelo no incluyó la imagen en la respuesta, así que el resto no se pudo observar.

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
- **Staging (16/10/2026, prueba 8): CORREGIDO** en la respuesta, en directo y tras recargar, y en la
  exportación a PDF y a Word (un `.doc` que es HTML): sin atributos de evento, sin esquemas fuera de
  la lista y sin contenido activo del SVG. El resto del código (`escapeHtml` sin comillas, lista
  negra, showdown) no se ha probado: el estado sigue PARCIAL. D29 deja de ser bloqueante.

### PNS-80 — `read_progress` devuelve el progreso y la respuesta de cualquier turno a cualquier usuario

- **Estado:** YA NO APLICA.
- **Evidencia:**
  - `read_progress` ya no existe en `pns_ai_chatboo` (ni en Python ni en JS).
  - El progreso se entrega en la propia respuesta de `/chatboo/stream`, que lee por SQL solo el job
    que acaba de crear en esa petición (`controllers/chatboo.py:818-860`).
  - El sondeo tras recargar (`/chatboo/async/poll`, `:467-524`) filtra por `user_id = uid`
    (`:487-494`), y los jobs tienen regla por dueño.
  - **Laboratorio:** `read_progress` no existe por RPC, ni para un interno ni para un portal (fase
    3b-1). Fase 3c: B, con clave MCP y `group_ai_conversational` (así que pasa
    `_user_may_use_chatboo`), sondea con el `session_id` de A y recibe listas vacías; el job terminado
    de A sigue sin marcar como visto. Como control, B sí recibe su propio job. La prueba de la fase
    3b-1 sobre el sondeo no era concluyente: B no tenía clave MCP y lo frenó el control de acceso
    antes del filtro.

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
- **Staging (16/10/2026, prueba 5): CORREGIDO por Chatboo.** U1 (con «Creación de contactos», para que
  el único freno fuera la falta de AI Writer) pidió crear un contacto: sin tarjeta y sin `create`,
  `write` ni `unlink` en el código ejecutado. Por `/mcp` no se probó; el resto de `tools/call` sigue.

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
  - Relacionado: la retención nueva está activa por defecto y purga al actualizar (PNS-87). El mismo
    defecto en el diario de cambios (`record_failed_plan`) está en PNS-37.
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
  - Observación (fase 5c, revisión de código): el parche de `http_patch.py` está acotado a las rutas
    `/mcp`, pero no a la base de datos. Sustituye `odoo.http.Root.get_request` al importar el módulo
    (`http_patch.py:22-35`, importado desde `__init__.py:15`), con la única condición de la versión
    de Odoo (`NEEDS_ROOT_GET_REQUEST_PATCH`, `pns_base/utils/compat.py:20`). Por tanto afecta a todas
    las bases de datos que sirve el mismo proceso, tengan o no instalado `pns_ai_mcp`. Impacto
    práctico bajo: solo cambia el tratamiento de las peticiones `POST` JSON a `/mcp` y `/mcp/*`.
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
- **Staging (16/10/2026, prueba 7): SIN CAMBIOS** (resto reproducido, como se preveía). U1 obtuvo el
  nombre de la BD y la lista de campos de `ai.mcp.user`, sobre el que no tiene acceso, sin valores.

### PNS-37 — Diario de cambios incompleto y valores sin redactar

- **Gravedad:** Media · **Estado:** SIN CAMBIOS.
- **Evidencia:**
  - `intended_values` se guarda sin redactar en los planes fallidos
    (`pns_ai_mcp/models/ai_change_journal.py:377`).
  - La reversión solo cubre `create`, `copy` y `write` (`:411-455`).
  - La redacción por nombre no cubre `env_vars` ni `config_json`
    (`utils/change_journal.py:30-38`, archivo sin cambios).
  - El diff del modelo solo renombra `correlation_id` → `turn`.
  - **Punto de entrada no citado en el informe (ya existía):** `ai.change.journal.record_failed_plan`
    (`models/ai_change_journal.py:342-400`) es `@api.model` público. Escribe con un cursor propio como
    `SUPERUSER_ID` (`:360-362`), que confirma al cerrarse, y toma `user_id` y `confirmed_by_uid` del
    contexto de la llamada (`:381-382`). Cualquier usuario autenticado puede crear por RPC entradas
    falsas del diario («plan fallido») a nombre de otro usuario, aunque el ACL del diario sea solo de
    AI Administrator y Ajustes (`security/ir.model.access.csv:42-43`). Es el mismo patrón que
    `create_log_entry` en `ai.log` (PNS-30). Corrección: hacerlo privado (`_record_failed_plan`).
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
- **Staging (16/10/2026, pruebas 4a y 4b):**
  - **Historial: SIN CAMBIOS.** El asistente trató como real un turno inventado (código de cliente
    ficticio `CLI-7731` → «Ready Mat») y **el historial falso quedó guardado en la sesión**. El enlace de la respuesta usaba un id inventado (106 en vez
    de 12; ver PNS-96).
  - **Proveedor: CORREGIDO.** Un `provider_id` fuera de la cadena se ignoró; el turno lo resolvió el
    de la cadena.

### PNS-62 — Adjuntos e imágenes sin límites de tamaño ni truncado

- **Gravedad:** Media · **Estado:** PARCIAL.
- **Evidencia:**
  - **Corregido:**
    - Tope por archivo e imagen en `/chatboo/stream`, 15 MB por defecto y configurable
      (`pns_ai_chatboo/controllers/chatboo.py:770-786`; `utils/chatboo_product_icp.py:22, 64-97`).
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
  - **Nota operativa (actualización):** esta purga global es la corrección, pero en la primera pasada
    del cron tras actualizar (cada 5 minutos) borra todas las sesiones de más de 30 días, también las
    de los usuarios que no vuelven al chat. El parámetro `pns_ai_chatboo.history_retention_days` se
    crea con el registro de datos `icp_chatboo_history_retention_days` (`data/chatboo_icp_data.xml:8-11`,
    `noupdate="1"`), que en `pns_ai_chatboo` 2.1.322 no existía. Conviene fijar la retención deseada antes de que se
    ejecute el cron. Según el código (no probado): si el parámetro se crea a mano antes de actualizar,
    sin XML ID, la carga de ese registro chocaría con la restricción `key_uniq` de
    `ir.config_parameter`. Hay que crearlo con su XML ID o ajustarlo justo después de actualizar con
    los crons parados.
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
- **Laboratorio (fase 3b-1): NO CONCLUYENTE.** Se reconstruyó sin commit la parte fija del agente de
  Chatboo para `es_ES` y para `en_US`: es idéntica en los dos idiomas, y no contiene ni el glosario
  `corporate_terms_es_ES` ni el genérico `corporate_terms`, aunque ambos existen y están activos. Eso
  no confirma la sospecha del informe (que llega el genérico y no la variante), sino que la contradice:
  el glosario no está en la parte fija para ningún idioma. O llega por otra vía (descubrimiento o
  contextos por usuario), o la composición de esa BD difiere de la de fábrica (ver PNS-76). Los tests
  del fabricante esperan `corporate_terms` como «importado» en el agente de Chatboo
  (`pns_ai_mcp/tests/test_knowledge_composition.py:209-222`).
- **Staging (16/10/2026, prueba 11): NO CONCLUYENTE.** `prompt_data` de `ai_log` no guarda el prompt
  de los turnos de Chatboo, así que no se puede ver si llega el glosario. Síntoma compatible con la
  sospecha: con un usuario `es_ES`, el formato de los importes cambia entre ejecuciones (`1,234.50` y
  `1.234,50`) y el texto y la tabla de una misma respuesta se contradicen. Se registra aparte como
  PNS-95, junto con un redondeo erróneo.
- **Pendiente:** revisar la vía de descubrimiento; para ver el prompt hace falta otra vía de registro
  (el bucle de herramientas registra la petición sin `prompt_data`, `agent_engine.py:3134-3146`; ver
  `analisis_parche5_gemini.md`, «Registro de actividad»).

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
- **Prueba en el laboratorio:** sí, pendiente (con el parche 1 el módulo ya se importa):
  `odoo-dev 14 tests pns_ai_mcp` y comprobar en el log si esas dos clases se ejecutan.

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
  - Observación (fase 3b-2, ya existía en 3.1.486): al abrir Chatboo se consultan tipos de cambio a una
    fuente externa. No lo hace el navegador, sino el servidor, dentro de `check_health`
    (`controllers/chatboo.py:101` → `pns_ai_mcp/models/ai_fx_source.py:72-78`, `urllib`), y el
    resultado se guarda una vez al día en `pns_ai_mcp.fx_usd_cache` (`:19, 93-100`). Queda cubierto por
    este hallazgo y por PNS-47 (espera sin red); no se numera aparte.
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

PNS-81 a PNS-89: solo código nuevo o modificado en `git diff 14.0-analisis-pns-ai..HEAD`. PNS-90 a
PNS-92: código que ya existía en 3.1.486 y que el informe no citaba; salieron en la revisión
independiente del seguimiento y se comprobaron en el laboratorio (fase 3c). PNS-93 a PNS-96: observados
en el staging (15-16/10/2026, `pns_demo`, proveedor Gemini; `verificacion_seguridad_pns_ai.md`,
«Staging (15-16/10/2026)»); la gravedad es una propuesta. Mismo criterio de
gravedad que el informe. Antes de numerar cada uno se ha comprobado con Grep que no figuraba en el
informe ni en este seguimiento; cuando era un resto ya citado, se indica la relación.

Patrón común en PNS-82, PNS-83, PNS-85, PNS-90, PNS-91 y PNS-92: es la misma causa que PNS-01. Son
métodos públicos (sin `_`) que trabajan en `sudo` o con un cursor de superusuario y no comprueban
grupo ni propiedad. En Odoo 14, `call_kw` los deja invocar a cualquier usuario autenticado, también a
uno de portal, aunque no tenga ACL sobre el modelo. En PNS-92 la escritura se deshace hoy por un
efecto lateral (ver su detalle). El mismo patrón aparece como punto de entrada adicional en PNS-30
(`create_log_entry`) y PNS-37 (`record_failed_plan`).

### PNS-81 — Incompatibilidades con Odoo 14: el módulo no se importa y tres funciones fallan en ejecución

- **Gravedad:** Alta · **Estado:** NUEVO. En la rama `14.0-pns-ai-3`, los cuatro fallos tienen
  parche local (parches 1 a 4, `docs/pendiente/parches_pns_ai.md`).
- **Descripción:** detalle completo en «Compatibilidad con Odoo 14». Líneas de la rama (con los
  parches); entre paréntesis, la línea del código del fabricante cuando cambia.
  - **Al importar** (parche 1): `pns_ai_mcp/controllers/mcp_decorators.py:171` (fabricante: `:169`).
    La anotación de retorno `tuple[bool, Optional[str]]` se evalúa al definir la función, y el
    archivo no tiene `from __future__ import annotations`. Con Python < 3.9 lanza `TypeError: 'type'
    object is not subscriptable`. No se importan ni `pns_ai_mcp` ni `pns_ai_chatboo`, que depende de
    él (comprobado con `paridad` en la fase 1).
  - **Al ejecutar, Python 3.7** (parche 3): `pns_ai_mcp/utils/relaxaicode_recipe.py:508` (fabricante:
    `:507`) llama a `ast.get_source_segment`, que existe desde 3.8. Ya estaba en el §7.3 del informe
    como «posiblemente no capturado». Ahora está confirmado: el camino principal de `tool_relaxaicode`
    lo llama sin protección (`controllers/tools_relaxaicode.py:1867`). El `except` general (`:2986`)
    convierte el `AttributeError` en un error de la herramienta. Falla cualquier código que defina, a
    nivel de módulo, una función con un parámetro cuyo nombre contenga `date`, `day`, `fecha`, `when` o
    `dia` (`_DATE_PARAM_HINTS`, `:206-209`; se compara por subcadena). Es el caso típico de las
    consultas por rango de fechas.
  - **Al ejecutar, Pillow 5.4.1** (parche 2): `pns_base/utils/pdf_io.py:95` (fabricante: `:94`; el
    parche añade la alternativa en `:100-111`) llama a `ImageOps.exif_transpose`, que existe desde
    Pillow 6.0. Odoo 14 fija `Pillow==5.4.1` con Python ≤ 3.7 (`requirements.txt:34` de la
    referencia). Todas las funciones de imagen capturan la excepción y devuelven `None` («no es una
    imagen»), así que el fallo es silencioso:
    - `/pns_ai_mcp/remote_image` responde 404 a todas las imágenes (`utils/remote_image.py:79-81`,
      `controllers/remote_image.py`);
    - Chatboo reenvía al proveedor las imágenes previas sin reescalar
      (`pns_ai_chatboo/models/chatboo_async_request.py:1079-1094`).
  - **Al ejecutar, Odoo 14** (parche 4): `_mcp_prompts_list` y `_mcp_prompts_get` llaman a `.sudo()`
    sobre el `Environment` (`pns_ai_mcp/controllers/main.py:1474, 1600`; fabricante: `:1473, 1598`). En Odoo 14 `Environment` no
    tiene ese método (solo `__call__(…, su=…)`, `odoo/api.py:508` de la referencia). El
    `AttributeError` se captura en silencio: `prompts/list` devuelve solo `system_prompt` y
    `prompts/get` de cualquier contexto responde «Prompt not found». Los clientes MCP externos no
    reciben ningún contexto por `prompts/*`. En 3.1.486 no pasaba: esas rutas usaban
    `self._get_mcp_env()` sin `.sudo()` (`main.py:1491, 1638` de `14.0-analisis-pns-ai`). El parche 4
    lo cambia por `self._get_mcp_env()(su=True)`, que en Odoo 14 conserva el uid del usuario de la
    clave y mantiene el filtro de PNS-12.
- **Impacto:** en un servidor Odoo 14 con Python 3.7 (la imagen oficial, Debian Buster) o 3.8,
  sustituir el código deja la base de datos sin cargar, porque `pns_ai_mcp` está instalado y no se
  importa. Corregida la importación, los demás fallos dejan funciones rotas sin aviso. Con Python 3.8
  y Pillow 8.1.1 quedan el fallo de importación y el de `prompts/*`.
- **Laboratorio:**
  - fase 3a: con el parche 1, la actualización termina y el servidor arranca;
  - fase 3b-2: con el parche 2, `remote_image` devuelve 200 con la imagen re-codificada;
  - el parche 3 (consulta con un parámetro de fecha) quedó pendiente para staging por el proveedor;
    en staging (16/10/2026, prueba 1), CORREGIDO: respuesta sin error de la herramienta y sin
    `AttributeError`;
  - staging (16/10/2026, prueba 2): con el parche 2, una foto con EXIF 6 adjunta en el chat llega
    derecha al modelo;
  - fase 3c: `prompts/list` y `prompts/get` por `/mcp` con un usuario con clave no devuelven ningún
    contexto, tampoco el propio, y el log registra el `AttributeError`;
  - parche 4 (2026-10-14, 16:12 UTC): la misma prueba por `/mcp` lista los contextos compartidos y el
    privado del usuario (no el de otro), `prompts/get` sirve el propio y rechaza el ajeno («Prompt not
    found»), y el log no registra ningún `AttributeError` (`verificacion_seguridad_pns_ai.md`,
    «Versión 3.1.782 — parche 4»).

### PNS-82 — `chatboo.session.claim_turn_file_chips` se apropia de adjuntos ajenos sin `res_model` o sin `res_id`

- **Gravedad:** Alta · **Estado:** NUEVO (relacionado con PNS-55 y PNS-21).
- **Ubicación:** `pns_ai_chatboo/models/chatboo_session.py:415-441`. También se llega desde el método
  público `apply_assistant_download_chips` (`:401-413`).
- **Comportamiento:**
  - El método es público. Sobre una sesión propia (la regla por `user_id` lo exige), toma ids de
    adjunto de la lista recibida o de la URL del chip.
  - Con `ir.attachment` en `sudo`, reasigna a esa sesión (`res_model`/`res_id`) cualquier adjunto al
    que le falte `res_model` o `res_id`: solo se salta los que tienen los dos (`:436-437`). Así entran
    también los adjuntos con `res_model` y `res_id=0`, una combinación que admite
    `write_export_attachment` (`pns_base/utils/portable_io.py:342-361`). No comprueba quién lo creó
    ni que lo haya generado el motor.
  - Después, `_may_read` de `/pns_ai_mcp/session_file` lo entrega, porque el adjunto ya cuelga de una
    sesión que el llamador puede leer (`pns_ai_mcp/controllers/session_file.py:20-32`). Por la misma
    razón, también lo sirve `/web/content`.
  - Además, al borrar su propia sesión, el usuario borra en `sudo` todos los adjuntos que cuelgan de
    ella (`chatboo_session.py:1326-1333`), también los reclamados.
- **Adjuntos expuestos:**
  - las descargas del chat de otros usuarios (PNS-21);
  - las copias de configuración de `pns_ai_mcp`, que se guardan sin `res_model` y, si se exportan con
    secretos, llevan claves y tokens durante su ventana de 24 h (PNS-20):
    - Ajustes (`pns_ai_mcp/models/res_config_settings.py:212`);
    - proveedores (`models/ai_provider.py:1135`);
    - usuarios MCP (`models/mcp_user.py:720`);
    - servidores externos (`models/external_server.py:1423`).
- **Impacto:** cualquier usuario interno (el ACL de `chatboo.session` es `base.group_user`) puede leer
  o borrar adjuntos de otros usuarios que no tengan `res_model` o `res_id`, incluidas copias de
  configuración con secretos. Los ids son secuenciales. Es la misma clase de fuga que PNS-21 (Alta).
- **Prueba en el laboratorio:** sí (permisos). A genera una descarga en el chat. B, sobre su propia
  sesión, llama por RPC a `claim_turn_file_chips` con el id de ese adjunto y después abre
  `/pns_ai_mcp/session_file/<id>`. Hoy se espera que B lo descargue; tras la corrección, el adjunto no
  debe cambiar de sesión. Comprobar también que el chat de A sigue sirviendo su descarga.

### PNS-83 — `ai.mcp.user.redeem_key_pin` entrega claves MCP por RPC sin grupo y sin límite efectivo de intentos

- **Gravedad:** Alta · **Estado:** NUEVO (relacionado con PNS-07, PNS-33 y PNS-84).
- **Rama Seges (20/10/2026):** **CORREGIDO con el parche 10 (E1)**: `redeem_key_pin`, `release_all`, `note_failure` e `is_blocked` pasan a privados; por RPC (interno, portal y `/jsonrpc`) se rechazan sin cambios en la BD (laboratorio y staging); el botón «Release PIN blocks» sigue funcionando. **Resto con el mismo patrón (decisión D-3 de la spec E1), previsto en E4:** `ai.mcp.user.consume_key_pin`; `ai.key.pin.desk.touch`, `close`, `any_open` y `notify_changed`; `ai.key.pin.ask.collect` y `supply` (públicos, en `sudo`); `ai.api.result.cache.get_cached`/`store` (públicos en `sudo`, aunque la clave incluye el uid); `ai.fetch.cache.gc_expired` y `ai.api.result.cache.gc_expired`.
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
  - `ai.key.pin.block.note_failure(ip)` e `is_blocked(ip)` (`:36-66`) también son `@api.model`
    públicos y trabajan en `sudo`. Con `note_failure`, cualquier usuario autenticado puede sumar fallos
    a la IP que quiera hasta bloquearla durante una hora (`DEFAULT_PIN_BLOCK_HOURS = 1`,
    `utils/key_pin.py:13`): impide el canje legítimo desde esa IP (denegación de servicio). Con
    `is_blocked` puede consultar si una IP está bloqueada.
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
- **Rama Seges (20/10/2026):** **CORREGIDO con el parche 9 (E1)**: los cuatro métodos pasan a privados y a la lista negra del sandbox; por RPC se rechazan (laboratorio y staging). En staging, la caché se guarda en el primer turno de una skill y el segundo la usa sin llamar al modelo (0 tokens). Queda abierto el alias en el sandbox (`f = m._metodo; f()`), que cierra E3.
- **Ubicación:** `pns_ai_mcp/models/ai_skill_param_cache.py:125-154` (`remember_for_skill`) y
  `:91-107` (`lookup_for_skill`); `models/ai_skill.py:329-345`; `utils/agent_engine.py:785`.
- **Comportamiento:**
  - `remember_for_skill(skill_id, leftover, norm)` es `@api.model` público. Crea la fila con un cursor
    propio como `SUPERUSER_ID` y hace commit (`:143-148`).
  - Acepta cualquier `skill_id`, también de skills que el llamador no puede leer, y no sobrescribe una
    fila existente: gana el primero que escribe.
  - Hay un segundo punto de entrada público: `ai.skill.remember_param_cache(leftover, norm)`
    (`ai_skill.py:338-345`), que solo usa `self.id` y delega en `remember_for_skill`. Se puede llamar
    sobre cualquier id de skill sin leerla.
  - La caché es global, sin usuario: `lookup_for_skill` busca en `sudo` por skill y frase normalizada,
    y el motor la aplica en los turnos de todos los usuarios. `lookup_for_skill` (y
    `ai.skill.lookup_param_cache`, `ai_skill.py:329-336`) también es público: cualquier usuario puede
    leer los parámetros cacheados de cualquier skill.
  - El ACL (lectura para internos, CRUD para AI Writer y AI Administrator) no interviene. Por el
    commit propio, si el sandbox llega al modelo, la escritura sobrevive al rollback de la caja A: el
    resto de PNS-07 (lista negra de 15 nombres, `validators.py:178-194`) no incluye estos métodos.
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
  - Nota: no solo el AI Administrator puede ampliar la lista blanca; cualquier usuario autenticado
    puede añadir o reactivar hosts por RPC (PNS-91). Para usar el generador sigue haciendo falta ser
    AI Administrator.
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

### PNS-87 — Pérdida de datos de consumo al actualizar: purga de `ai.log` a 30 días y borrado de `ai_provider_usage_day`

- **Gravedad:** Baja · **Estado:** NUEVO (relacionado con PNS-30).
- **Ubicación:** `pns_ai_mcp/data/ai_log_cron.xml` (`noupdate="1"`, activo, diario);
  `models/ai_log.py:17-18, 892-912`; `utils/schema_fossils.py:15-28, 44-53`;
  `models/ai_schema_fossil.py:25-35`.
- **Comportamiento:**
  - **Purga de `ai.log`:**
    - Al actualizar se crea el cron activo. Si no existe el parámetro `pns_ai_mcp.log_retention_days`,
      se aplican 30 días.
    - El parámetro no está en Ajustes; solo se cambia en Parámetros del sistema.
    - La primera ejecución borra en `sudo`, en una sola transacción, todas las filas de más de 30
      días: la auditoría y el historial de consumo y coste que usa `get_user_usage_summary`.
    - No hay aviso ni nota de actualización.
  - **Borrado de `ai_provider_usage_day`:**
    - `ai.schema.fossil.init()` ejecuta en cada `-u` un `DROP TABLE IF EXISTS … CASCADE` de las tablas
      de `FOSSIL_TABLES`. Entre ellas está `ai_provider_usage_day` (`schema_fossils.py:27`).
    - No es un asistente: es el histórico diario de tokens, coste y número de peticiones por
      proveedor (modelo `ai.provider.usage.day` de 3.1.486). No hay migración ni `init()` que lo
      traslade, así que se pierde en la primera actualización.
    - En la misma función se borran columnas que el ORM ya no usa (`LEFTOVER_COLUMNS`,
      `schema_fossils.py:44-53`): `ai_log.operation_code`, `ai_provider.cost_policy`,
      `ai_provider.is_on_premise`, `ai_context.is_shared`, `ai_skill.is_shared`,
      `ai_agent.auto_link_mcp_nucleus`, `ai_agent.link_show_native` y `ai_agent.link_show_pinned`.
- **Impacto:** pérdida de datos no avisada en instalaciones que guardan el log como auditoría o para
  repartir costes, y pérdida del histórico de consumo por proveedor. En bases con mucho volumen, el
  primer borrado puede ser largo. El informe pedía retención (PNS-30), así que el defecto es el valor
  por defecto y la falta de aviso, no la purga.
- **Laboratorio (fase 3a): CONFIRMADO.** El cron se crea activo con `numbercall=-1` y el parámetro no
  existe. La purga no espera un día: se ejecuta en la primera pasada del programador tras arrancar
  (unos 3 minutos después de actualizar). `ai_log` y `ai_provider_usage_day` estaban vacías en la
  copia, así que no se pudo medir el borrado.
- **Para producción:** antes de actualizar, crear el parámetro `pns_ai_mcp.log_retention_days` (`0`
  para no purgar, o los días que se quieran) y exportar `ai_provider_usage_day` si interesa conservar
  el histórico.

### PNS-88 — Renombrados de XML ID `mcp_*` que no se ejecutan en Odoo 14 y servidores de fábrica heredados

- **Gravedad:** Baja · **Estado:** NUEVO.
- **Ubicación:** `pns_ai_mcp/migrations/3.1.518/pre-migrate.py` y `3.1.519/pre-migrate.py` (38 XML ID);
  `data/external_server_data.xml` y `data/external_server_openapi_data.xml` de la versión anterior
  (eliminados).
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
  - Quedan 5 servidores de fábrica en las BD existentes, todos `noupdate="1"` e inactivos por defecto:
    - de `external_server_data.xml`, tres servidores `stdio` con `npx`: `external_server_mcp_test`,
      `external_server_brave_search` y `external_server_sequential_thinking` (código `seq_thinking`);
    - de `external_server_openapi_data.xml`, dos OpenAPI: `external_server_sesame` y
      `external_server_cdmon`.
- **Descartado:** la skill `analisis-financiero` sí se borra en 14 (ver la corrección en PNS-67).
- **Impacto:** bajo. En 14 los renombrados de `migrations/` no se ejecutan: al actualizar, los 38
  registros se borran y se recrean con ids nuevos, y se pierden las personalizaciones y las referencias
  a los antiguos. Los servidores de fábrica retirados quedan en la BD.
- **Laboratorio (fase 3a): CONFIRMADO.** Los 38 XML ID `mcp_*` se borran en `_process_end` sin
  errores, y se crean 38 `ai_*` con ids nuevos, así que se pierden las personalizaciones y las
  referencias por id a los registros antiguos. No quedan menús duplicados. Siguen los 5 servidores de
  fábrica, inactivos.

### PNS-89 — `/pns_ai_mcp/key_pin/stop` sin CSRF

- **Gravedad:** Baja · **Estado:** NUEVO (relacionado con PNS-83).
- **Ubicación:** `pns_ai_mcp/controllers/key_pin.py:35-54` (`type='http'`, `POST`, `csrf=False`).
- **Comportamiento:**
  - Una página de otro origen puede hacer que el navegador de un AI Administrator envíe el POST.
  - El único efecto es cerrar la mesa cuyo token se envíe y avisar por el bus. El token se genera en el
    navegador con `Date.now()` y `Math.random()` (`key_pin_desk_v14.js:28`), no con un generador
    criptográfico, y vive en el `sessionStorage` de la pestaña (`key_pin_desk_v14.js:20-30`); sin
    conocerlo no hay efecto.
  - Probablemente se usa con `sendBeacon` al cerrar la pestaña, que puede llevar el `csrf_token` en el
    cuerpo. Propuesta: quitar `csrf=False` y generar el token con `crypto.getRandomValues`.
- **Impacto:** mínimo hoy; es una excepción de CSRF innecesaria en una función sensible.
- **Prueba en el laboratorio:** no (revisión de código).

### PNS-90 — Caché de `fetch_url` legible y sobrescribible por cualquier usuario autenticado

- **Gravedad:** Alta · **Estado:** NUEVO (ya existía en 3.1.486; resto de PNS-14; relacionado con
  PNS-16 y PNS-17).
- **Rama Seges (20/10/2026):** **CORREGIDO con el parche 7 (E1)**: `get_cached` y `store` pasan a privados; un interno y un portal ya no leen ni escriben la caché por RPC (prueba 1 de 3c repetida en staging: CORREGIDO). `fetch_url` sigue cacheando y sirviendo desde la caché (staging, R1).
- **Ubicación:** `pns_ai_mcp/models/fetch_cache.py:63-89` (`get_cached`) y `:91-123` (`store`);
  `controllers/safe_plan.py:1493-1503` (clave de caché), `:1619` (lectura) y `:1667, 1723`
  (escritura).
- **Comportamiento:**
  - `get_cached(url)` y `store(url, result, ttl_seconds)` son `@api.model` públicos. Buscan, crean y
    sobrescriben filas en `sudo`, sin comprobar grupo.
  - La caché es global: la clave es la URL (más el hash del cuerpo en `QUERY`), sin usuario.
  - `fetch_url` consulta esa caché antes de salir a la red. Si hay una fila vigente, devuelve su
    cuerpo como resultado de la herramienta.
  - `store` acepta el contenido, el código de estado y el TTL que elija quien llama.
  - El ACL de `ai.fetch.cache` (solo AI Administrator desde esta versión) no interviene.
- **Impacto:** cualquier usuario autenticado, también de portal, puede:
  - leer el cuerpo cacheado de cualquier URL que haya consultado otro usuario;
  - fijar de antemano el contenido que recibirá la herramienta `fetch_url` de los demás usuarios para
    una URL, sin que la petición salga a la red. Ese contenido llega al modelo como resultado de la
    herramienta: es una vía de prompt injection entre usuarios (PNS-16).
- **Laboratorio (fase 3c): VULNERABLE.** Con una URL ficticia y contenido inocuo, un interno sin
  grupos de IA guarda una entrada; un usuario de portal la lee, la sobrescribe con su propio contenido,
  y después el interno recibe el contenido del portal. El portal también crea entradas nuevas con el
  TTL que elige.
- **Corrección propuesta:** hacer privados los dos métodos (`_get_cached`, `_store`), como se hizo con
  `ai.system.action` en PNS-01.

### PNS-91 — `ai.url.whitelist.ensure_domain_whitelisted` amplía la lista blanca sin control de grupo

- **Gravedad:** Media · **Estado:** NUEVO (ya existía en 3.1.486; relacionado con PNS-16, PNS-59 y
  PNS-86).
- **Rama Seges (20/10/2026):** **CORREGIDO con el parche 8 (E1)**: `ensure_domain_whitelisted` pasa a privado; un interno y un portal ya no añaden ni reactivan dominios (prueba 2 de 3c repetida en staging: CORREGIDO). Siguen funcionando el alta al confirmar un AI Administrator, el botón «➕ Whitelist», la reactivación y el alta de servidores externos (staging, R2).
- **Ubicación:** `pns_ai_mcp/models/url_whitelist.py:235-266`; tipos admitidos en `:54-56`.
- **Comportamiento:**
  - `ensure_domain_whitelisted(hostname, notes, kind)` es `@api.model` público. Crea la fila con
    `sudo().create` o reactiva una archivada con `sudo().write`, sin comprobar grupo.
  - Admite los tipos `web`, `mcp` y `openapi`.
  - El ACL de internos es de solo lectura (`security/ir.model.access.csv:6`), pero no interviene.
- **Impacto:** cualquier usuario autenticado, también de portal, puede añadir o reactivar hosts en la
  lista blanca. Con la política de URL restringida, eso abre la salida del servidor hacia esos hosts
  (`remote_image`, `fetch_url`) y deja sin efecto el resto 3 de «Restos que se repiten».
- **Laboratorio (fase 3c): VULNERABLE.** Un interno sin grupos de IA y un usuario de portal añaden
  cada uno un dominio ficticio (`.invalid`). El portal reactiva una entrada archivada. Como control,
  el `create` directo del interno da `AccessError`. Solo se probó el tipo `web`.
- **Corrección propuesta:** hacerlo privado (`_ensure_domain_whitelisted`) y dejar que lo llame solo el
  flujo de confirmación del plan.

### PNS-92 — `set_mcp_api_key` y `action_generate_mcp_api_key` escriben la clave en `sudo` sin control previo

- **Gravedad:** Media (defensa en profundidad) · **Estado:** NUEVO (ya existía en 3.1.486; relacionado
  con PNS-33 y PNS-83).
- **Ubicación:** `pns_ai_mcp/models/mcp_user.py:450-466` (`set_mcp_api_key`), `:440-448`
  (`action_generate_mcp_api_key`) → `:419-437` (`_do_generate_mcp_api_key`) → `:406-417`
  (`_store_api_key_hash`).
- **Comportamiento:**
  - Los dos métodos son públicos y no comprueban grupo ni propiedad. Escriben el hash de la clave MCP
    con `sudo()` (`:460-464` y `:410-414`).
  - Hoy no tienen efecto para un usuario sin permisos por una razón indirecta. Después de escribir,
    la línea de log (`:465` y `:437`) lee `self.user_id` en el entorno del usuario que llama. Sin ACL
    de lectura sobre `ai.mcp.user` (solo AI Administrator, `security/ir.model.access.csv:39`), esa
    lectura lanza `AccessError`, y el error deshace toda la transacción, incluida la escritura ya
    hecha. Los argumentos del log se evalúan con cualquier nivel de log.
  - El único llamador legítimo es el asistente `ai.api.key.wizard`
    (`models/mcp_api_key_wizard.py:104, 113`), con ACL solo de AI Administrator (`csv:40`).
- **Impacto:** hoy, ninguno comprobado. La protección depende de un efecto lateral: cualquier cambio
  que dé lectura sobre `ai.mcp.user` a usuarios no administradores, o que mueva o quite esa línea de
  log, dejaría a cualquier usuario autenticado fijar o regenerar la clave MCP de otro (incluido un
  administrador). Sería Crítica.
- **Laboratorio (fase 3c): protegido solo por rebote.** Seis intentos por RPC, sin éxito: un interno
  sin IA y un portal sobre el registro de otro usuario de prueba, y el interno sobre el suyo. En todos,
  el hash no cambia, no aparece ninguna fila en `ai_log` y el `AccessError` sale de la línea del log
  (`:465` o `:437`), no de un control previo.
- **Corrección propuesta:** comprobar `group_ai_admin` (o la propiedad, si se quiere autoservicio) antes
  de escribir, o hacer privados los métodos y llamarlos solo desde el asistente.

### PNS-93 — El driver `openai` pierde la `thought_signature` de Gemini 3 y todo turno con herramientas falla

- **Gravedad propuesta:** Media · **Estado:** NUEVO. En la rama `14.0-pns-ai-3`, con parche local
  (**parche 5**, `docs/pendiente/parches_pns_ai.md`), validado en staging.
- **Descripción:** con Gemini 3.x configurado con `protocol = openai`
  (`…/v1beta/openai/chat/completions`), Gemini envía en cada `tool_call` el campo
  `extra_content.google.thought_signature` y exige recibirlo de vuelta. `iter_chat` reconstruye cada
  `tool_call` solo con `id`, `type` y `function` y lo pierde
  (`pns_ai_mcp/lib/llm/drivers/openai_driver.py:645-657` del fabricante; mensaje final en
  `:661-664`). La siguiente ronda del bucle de herramientas recibe `HTTP 400 … Function call is
  missing a thought_signature in functionCall parts`. «Test Connection» funciona porque no envía
  herramientas (`models/ai_provider.py:995-997`). Análisis completo en
  `docs/pendiente/analisis_parche5_gemini.md`.
- **Impacto:** con Gemini 3 por el protocolo OpenAI, Chatboo no puede responder ninguna pregunta que
  necesite consultar datos. El 400 se convierte en `ProviderConnectionError` y dispara el failover;
  con un solo proveedor, el usuario ve el error. No es un problema de seguridad ni de Odoo 14.
- **Staging (16/10/2026):** sin el parche, todo turno con herramientas fallaba (15/10). Con el parche 5
  (commit `27cadbb`), varias rondas de herramientas en el mismo turno y un segundo turno en la misma
  conversación, sin 400, con `gemini-3.6-flash`, `3.5-flash-lite` y `3.5-flash`. No se observaron
  llamadas paralelas (la ampliación 1 del análisis, para llamadas sin `index`, sigue sin aplicar).
- **Corrección sugerida:** conservar `extra_content` de cualquier delta del `tool_call` (el parche 5
  es esa corrección mínima) y revisar las llamadas paralelas sin `index` y el fallback de llamadas
  escritas en texto (`agent_engine.py:3215-3240`).

### PNS-94 — Bloqueo de `chatboo_session` tras un turno con adjunto: denegación de servicio por cualquier usuario de Chatboo

- **Gravedad propuesta:** Alta · **Estado:** NUEVO. En la rama `14.0-pns-ai-3`, con parche local
  (**parche 6**, `docs/pendiente/parches_pns_ai.md`), validado en staging.
- **Descripción:** el turno se ejecuta en un hilo dentro del worker HTTP con un cursor propio (A) que
  mantiene la transacción abierta todo el turno (`pns_ai_chatboo/models/chatboo_async_request.py:252-303`,
  cursor en `:280`). Al terminar, `_finalize` abre en el mismo hilo otro cursor (B) y escribe la misma
  fila de `chatboo_session` (`:835-918`, cursor en `:885-887`; `input_history` en `:1723`). Si A tiene
  un lock sobre esa fila, B espera a A, y A no se cerrará nunca: su `rollback` está en el `finally`
  (`:724`), después de `_finalize`, en el mismo hilo. PostgreSQL no lo detecta como interbloqueo y
  ningún límite de Odoo afecta a un hilo de fondo. Hipótesis de trabajo sobre el origen del lock (H1):
  la escritura de `last_screen_context` por A después del commit de `:514` (`:556-562`), que con
  imagen llega a SQL por A; H2 (commit de `:514` fallido) descartada porque los logs no tienen «could
  not commit the session writes». Líneas del código del fabricante (antes del parche 6). Análisis
  completo en `docs/pendiente/analisis_bloqueo_chatboo_session.md`.
- **Impacto:** el job no llega a `done` y el navegador sigue esperando. Cada recarga ejecuta
  `update_last_used()` sobre la misma fila sin límite de espera (`pns_ai_chatboo/controllers/chatboo.py:286`)
  y ocupa un worker; con 2 workers bastan unas pocas para dejar Odoo sin servicio, y las conexiones
  quedan en PostgreSQL hasta reiniciar. Se reproduce siempre al adjuntar una imagen, también cuando
  el proveedor devuelve error. **Cualquier usuario de Chatboo** (grupo conversacional y clave MCP, sin
  privilegios) puede provocarlo, sin querer o a propósito.
- **Staging:** dos incidentes antes del parche (resueltos reiniciando). Con el parche 6 (commit
  `63ee2dc`, 16/10/2026), validado en sus 5 casos (imagen con respuesta, imagen con error del
  proveedor, solo texto, cancelación y turno siguiente que recupera el contexto de pantalla), sin
  conexiones colgadas ni avisos en el log.
- **Corrección sugerida** (análisis, §5.2): cerrar la transacción de A antes de `_finalize` (el
  parche 6) y, de fondo, que toda escritura en la sesión durante el turno vaya en cursores cortos; no
  tragarse un commit fallido; `lock_timeout` en las escrituras de la sesión; no ejecutar trabajo largo
  en hilos dentro de los workers; detección y cierre del job si `_finalize` no obtiene el lock.

### PNS-95 — Formato de importes inconsistente y redondeo erróneo con usuarios `es_ES`

- **Gravedad propuesta:** Baja · **Estado:** NUEVO (relacionado con PNS-46).
- **Descripción:** con un usuario `es_ES`, las respuestas con importes usan unas veces `1,234.50` y
  otras `1.234,50`, y en una misma respuesta el texto y la tabla se contradicen. Además, un importe de
  `1493,745` aparece como `1.493,74` en la tabla. Ubicación: sin localizar en el código. El formato lo
  produce el modelo y la parte fija del prompt no incluye el glosario `corporate_terms_es_ES`
  (PNS-46, laboratorio 3b-1: `pns_ai_mcp/models/ai_context.py:818-826`); el redondeo puede venir de la
  representación en coma flotante (`1493,745` no es exacto en binario), sin comprobar.
- **Impacto:** cifras ambiguas o incorrectas en respuestas financieras para usuarios españoles.
- **Staging (16/10/2026, prueba 11):** observado. Lo que recibe el modelo no se puede ver: `prompt_data`
  no guarda el prompt de los turnos de Chatboo.
- **Corrección sugerida:** formatear los importes en el servidor según el idioma del usuario (o
  incluir de forma fiable el glosario y el formato en el prompt) y redondear con `Decimal` o con la
  precisión de la moneda; guardar el prompt en `ai_log` para poder auditarlo.

### PNS-96 — Calidad de las respuestas con modelos `lite`

- **Gravedad propuesta:** Baja · **Estado:** NUEVO (observación de calidad; depende en parte del
  modelo).
- **Descripción:** con modelos `lite` (en staging, `gemini-3.5-flash-lite`), el asistente interpreta
  mal «empresas», inventa ids en los enlaces a registros (como el 106 en vez de 12 de la prueba 4a),
  muestra al usuario los errores de acceso tal cual (relacionado con PNS-40) y añade «>» de más
  al formato. Ubicación: sin localizar en el código.
- **Impacto:** enlaces que llevan a otro registro o a ninguno, y mensajes de error técnicos en el
  chat. Sin efecto de seguridad observado: los accesos se siguen comprobando en Odoo.
- **Staging (16/10/2026):** observado en varias pruebas con modelos `lite`.
- **Corrección sugerida:** construir los enlaces a partir de los ids devueltos por la herramienta (no
  del texto del modelo), traducir los errores de acceso a un mensaje para el usuario y documentar los
  modelos mínimos recomendados.

### Candidatos evaluados y descartados

- **Candidatos de la revisión independiente sin número propio:**
  - pérdida de `ai_provider_usage_day`: incluida en PNS-87;
  - purga global de sesiones de Chatboo: es la corrección de PNS-63 (ver su nota operativa);
  - duplicar un proveedor copia su clave: observación en PNS-20;
  - consulta de tipos de cambio al abrir Chatboo: la hace el servidor, una vez al día; cubierta por
    PNS-47 y PNS-72.

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
- Las líneas son las de la rama `14.0-pns-ai-3`, con los parches 1 a 4 (1 a 3 en `ce6790b`). Respecto
  al código del fabricante solo cambian `main.py` (de la 1473 en adelante, +1; de la 1598 en adelante,
  +2), `mcp_decorators.py` (de la línea 169 en adelante, +2),
  `relaxaicode_recipe.py` (la 507 pasa a 508-509 y, de la 508 en adelante, +2) y `pdf_io.py` (la 94
  pasa a 95 y, de la 98 en adelante, +17). La clasificación describe el código del fabricante; las
  filas parcheadas lo indican.
- El fallo de `Environment.sudo()` (cuarta fila de FALLA) no es de Python ni de librerías, sino de la
  API de Odoo 14. Se detectó en el laboratorio (fase 3c), no en el análisis AST.

Versiones en la imagen: **Python 3.7.3**, PyPDF2 1.26.0, openpyxl 3.1.2, requests 2.21.0 (urllib3
1.24.1), reportlab 3.5.13, Pillow 5.4.1, lxml 4.3.2, pdfminer 20181108. No están `pypdf`, `fitz`
(PyMuPDF) ni `pdftoppm`.

**Resumen:** FALLA AL IMPORTAR 1 · FALLA AL EJECUTAR 3 · SEGURO 22. Los cuatro fallos son PNS-81 y
los cuatro tienen parche en la rama (parches 1 a 4; el de `Environment.sudo()` es el parche 4).

### a) Python

| Archivo:línea | Uso | Clasificación | Efecto en Odoo 14 / motivo | Corrección mínima |
|---|---|---|---|---|
| `pns_ai_mcp/controllers/mcp_decorators.py:171` (fabricante: `:169`) | `-> tuple[bool, Optional[str]]` (3.9) | **FALLA AL IMPORTAR** (parche 1 en la rama) | Anotación de retorno evaluada al definir la función; sin `from __future__ import annotations`. No se importan `pns_ai_mcp` ni `pns_ai_chatboo`. | `Tuple[bool, Optional[str]]` (ya importa `typing`) o añadir `from __future__ import annotations`. |
| `pns_ai_mcp/utils/relaxaicode_recipe.py:508` (fabricante: `:507`) | `ast.get_source_segment` (3.8) | **FALLA AL EJECUTAR** (parche 3 en la rama) | Desde `tools_relaxaicode.py:1867`, sin protección: la herramienta devuelve error si el código define una función de nivel superior con un parámetro de fecha. Desde `:1252` está dentro de `try` (ver fila SEGURO). | `getattr(ast, 'get_source_segment', None)` y, si no existe, usar `src`, como ya hace con `or src`. |
| `pns_ai_mcp/controllers/main.py:1474, 1600` (fabricante: `:1473, 1598`) | `self._get_mcp_env().sudo()` (API de Odoo, no de Python) | **FALLA AL EJECUTAR** (parche 4 en la rama; eficaz: `prompts/list` y `prompts/get` sirven los contextos visibles y no los ajenos, sin `AttributeError`) | `Environment` no tiene `sudo()` en Odoo 14 (`odoo/api.py:508` de la referencia: solo `__call__(…, su=…)`). El `AttributeError` se captura: `prompts/list` solo devuelve `system_prompt` y `prompts/get` de cualquier contexto da «Prompt not found» (comprobado en la fase 3c). En 3.1.486 no había `.sudo()`. | `self._get_mcp_env()(su=True)`. |
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

Sin coincidencias: genéricos integrados fuera de esa línea, uniones `|` evaluadas, `typing` 3.8+
sin protección, `cached_property`, `functools.cache`, `@lru_cache` sin paréntesis,
`removeprefix`/`removesuffix`, `math.prod/isqrt/dist`, `importlib.metadata`, `shlex.join`,
`statistics.fmean`, `asyncio.to_thread`, `zip(strict=)`, `dict | dict`, f-string `{x=}`, `dataclass`
con `kw_only`/`slots` y walrus. Los 65 archivos con `from __future__ import annotations` exigen
Python ≥ 3.7. Con 3.6 no cargarían, pero 3.6 queda fuera del objetivo.

### b) Librerías

| Archivo:línea | Uso | Versión en la imagen | Clasificación | Efecto / alternativa |
|---|---|---|---|---|
| `pns_base/utils/pdf_io.py:95` (fabricante: `:94`) | `ImageOps.exif_transpose` (Pillow ≥ 6.0) | Pillow 5.4.1 (no existe, comprobado) | **FALLA AL EJECUTAR** (parche 2 en la rama, `:95-111`; eficaz en la fase 3b-2) | `_open_picture` lanza `AttributeError`. `as_picture`, `picture_size`, `shrink_picture`, `turn_picture` y `picture_pdf` lo capturan y devuelven `None`. Consecuencias: `remote_image` da 404 y Chatboo reenvía las imágenes sin reescalar (PNS-81). **Corrección:** `fn = getattr(ImageOps, 'exif_transpose', None); return (fn(image) if fn else image), kind`. Sin girar por EXIF, pero funciona. |
| `pns_base/utils/pdf_io.py:45-60` | `pypdf.PdfReader/PdfWriter` con caída a `PyPDF2.PdfFileReader/PdfFileWriter(strict=False)` | PyPDF2 1.26.0; `pypdf` ausente | SEGURO | `except ImportError` → PyPDF2. `PdfFileReader` acepta `strict` y tiene `.pages` (comprobado). |
| `pns_base/utils/pdf_io.py:63-79` | `add_page`/`addPage`, `rotate`/`rotateClockwise`, `get_object`/`getObject` | PyPDF2 1.26.0 | SEGURO | `getattr` con las dos variantes; en la imagen existen `addPage` y `rotateClockwise` (comprobado). |
| `pns_base/utils/pdf_io.py:254` (fabricante: `:237`) | `extract_text`/`extractText` | PyPDF2 1.26.0 | SEGURO | `getattr`; existe `extractText`. |
| `pns_base/utils/pdf_io.py:233` (fabricante: `:216`) | `pdfminer.high_level.extract_text` | pdfminer 20181108 (no existe, comprobado) | SEGURO | `except ImportError` → PyPDF2. Extrae peor el texto de algunos PDF. |
| `pns_base/utils/pdf_io.py:218, 385, 402` (fabricante: `:201, 368, 385`) | `fitz` (PyMuPDF), `pdftoppm` | ausentes | SEGURO | Opcionales (`except ImportError`, `shutil.which`). Sin ellos, los PDF escaneados no se convierten en imágenes para el modelo de visión. |

Sin problemas de API:
- **openpyxl 3.1.2:** solo `Workbook`, `load_workbook`, `styles` y `utils.get_column_letter`.
- **reportlab 3.5.13:** `platypus`, `graphics.charts`, `lib`; `Table(splitByRow=)` existe (comprobado).
- **requests 2.21.0 / urllib3 1.24.1:** `allow_redirects`, `is_redirect`, `iter_content`,
  `exceptions.SSLError/RequestException`. No usa `JSONDecodeError` de requests ni `Retry(allowed_methods=)`.
- **lxml:** sin uso directo en los tres módulos.
