# CONFIDENCIAL — Informe técnico de seguridad: pns_base 1.2.10, pns_ai_mcp 3.1.486 y pns_ai_chatboo 2.1.322 (Odoo 14.0)

> **Borrador.** Pendiente de revisión interna antes de su envío.

| | |
|---|---|
| **Destinatario** | PATANEGRA Soft |
| **Módulos** | `pns_base` 1.2.10 · `pns_ai_mcp` 3.1.486 ("AI Engine") · `pns_ai_chatboo` 2.1.322 ("Chatboo") |
| **Plataforma** | Odoo 14.0 |
| **Fecha** | 2026-10-08 (ampliado con `pns_ai_chatboo` y con una segunda ronda de reproducción el 2026-10-09) |
| **Entorno de análisis** | Odoo 14.0 oficial, Python 3.7, base de datos de pruebas con datos de demostración. Sin claves de proveedores de IA ni llamadas a servicios externos. |
| **Método** | `pns_base` y `pns_ai_mcp`: revisión estática completa del código y reproducción controlada (pruebas A-D) de los hallazgos más graves mediante JSON-RPC. `pns_ai_chatboo`: revisión estática completa del código propio. Segunda ronda de reproducción (2026-10-09), con el mismo método, sobre ambos módulos: instalación de `pns_ai_chatboo`, aislamiento de sesiones, lecturas de un interno sin grupos de IA, métodos de `ai.system.action`/`ai.skill` con portal, migraciones, cron, tests y arranque con `hr`. |

---

## 1. Resumen ejecutivo

1. Hemos revisado `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo` con vistas a su uso en Odoo 14.0. Agradecemos el trabajo de los módulos; este informe busca ayudar a corregir lo encontrado antes de usarlos con usuarios reales.
2. Se han reproducido cuatro problemas de control de acceso de `pns_ai_mcp` (pruebas A-D) en una base de datos de pruebas. Una segunda ronda ha reproducido además PNS-08, PNS-14 y PNS-55 (este último de `pns_ai_chatboo`), ha extendido al usuario de portal PNS-02 y PNS-11, y ha confirmado §7.2 (migraciones) y §7.4 (cron). PNS-69 no se reproduce en Odoo 14 con `hr` y se rebaja a Baja. El resto de hallazgos de `pns_ai_chatboo` procede de la revisión del código.
3. **A:** cualquier usuario autenticado, **incluido un usuario de portal**, se añade `base.group_system` con una sola llamada a `ai.system.action.apply_user_add_group`.
4. **B y C:** el mismo usuario sin permisos invoca `ai.system.action.preview_module_update` y `ai.skill.unlink_named_factory_skills`; la causa es la misma que en A. En la segunda ronda, un **usuario de portal** también invoca `preview_user_add_group`, `preview_module_update` y `unlink_named_factory_skills` (PNS-02, PNS-11).
5. **D:** el propietario de una `ai.safe.operation` puede cambiar por `write` su `status` a `confirmed` y su `user_id`, saltándose la supervisión humana.
6. La causa común de A-C son métodos públicos `@api.model` que trabajan con `sudo()` sin comprobar permisos: en un `AbstractModel` (o sin operación ORM sobre el propio modelo) el ACL no se evalúa al invocarlos por `call_kw`.
7. La revisión del código señala otros tres críticos en `pns_ai_mcp` que siguen el mismo patrón (métodos públicos que aceptan el uid ejecutor, ejecución en `sudo` disparada por el LLM y código de skills ejecutado al guardar sin solo lectura).
8. Entre los altos de `pns_ai_mcp` destacan: credenciales de servidores externos legibles por cualquier interno (reproducido: un interno sin grupos de IA lee `auth_token`, `env_vars` y `config_json`, ambas cachés y las `ai.safe.choice` de otro usuario; PNS-08, PNS-14), ausencia de saneado HTML (XSS), `fetch_url` sin protección SSRF y envío de datos al LLM sin controles de alcance.
9. En `pns_ai_chatboo`, las sesiones del chat no tienen reglas de registro: cualquier interno puede leer, modificar y borrar conversaciones ajenas (reproducido en la segunda ronda; un usuario de portal no accede) y dejar en ellas HTML que se ejecuta al abrirlas la víctima (PNS-53, PNS-55). Además, el cliente web inserta el HTML del asistente sin sanear (PNS-60) y cualquier XSS en el chat puede confirmar y ejecutar operaciones de la Caja B sin el usuario (PNS-54) o sacar datos sin clic mediante imágenes externas (PNS-59).
10. En Odoo 14 `pns_ai_mcp` no se instala con las dependencias declaradas sin añadir librerías que no usa; sus scripts de `migrations/` no se ejecutan por el formato de versión (reproducido al actualizar; probablemente lo mismo ocurre en `pns_ai_chatboo`), y el cron de purga de la caché de `api_call` se desactiva tras su primera ejecución (reproducido). La batería de tests de `pns_ai_mcp` da fallos, parte de ellos por depender de módulos o datos que no siempre existen (§6.1).
11. Total: **9 críticos, 26 altos, 24 medios y 19 bajos** (78 hallazgos; 25 de ellos de `pns_ai_chatboo`). Recomendamos priorizar PNS-01 a PNS-07 y PNS-53 a PNS-55, y confirmar la corrección con las pruebas del §3.

### 1.1 Tabla de hallazgos

Estado: **Reproducido** (comprobado ejecutando en el entorno de pruebas) · **Verificado en código**
(comportamiento leído en el código, sin ejecutar) · **Inferido del código** (deducción razonada
que conviene confirmar) · **No reproducido** (se intentó en el entorno de pruebas y no se produjo).
Los problemas de compatibilidad de §7 no llevan número; §7.2 y §7.4 están reproducidos.

| ID | Gravedad | Estado | Módulo | Título |
|---|---|---|---|---|
| PNS-01 | Crítica | Reproducido (A) | pns_ai_mcp | Escalada a `base.group_system` por `apply_user_add_group` (interno y portal) |
| PNS-02 | Crítica | Reproducido parcialmente (B; `preview_*` también con portal) | pns_ai_mcp | Resto de `apply_*` de `ai.system.action` sin control de permisos |
| PNS-03 | Crítica | Reproducido (D) | pns_ai_mcp | El propietario modifica `status` y `user_id` de su `ai.safe.operation` |
| PNS-04 | Crítica | Inferido del código | pns_ai_mcp | `resolve_*` / `confirm_by_user` públicos ejecutan con un `confirmed_uid` elegido por quien llama |
| PNS-05 | Crítica | Inferido del código | pns_ai_mcp | `get_safe_operation_status` busca sin filtrar por usuario y ejecuta en `sudo` |
| PNS-06 | Crítica | Verificado en código (flujo) | pns_ai_mcp | El `code_body` de una skill se ejecuta al guardarla, sin solo lectura |
| PNS-07 | Crítica | Inferido del código | pns_ai_mcp | `getattr` dinámico desde el sandbox a métodos que abren cursores con escritura |
| PNS-08 | Alta | Reproducido | pns_ai_mcp | Credenciales de `ai.api.server` legibles por cualquier usuario interno |
| PNS-09 | Alta | Verificado en código | pns_ai_mcp | Servidores MCP `stdio`: comando libre, entorno completo, sin timeout; métodos sin control de grupo |
| PNS-10 | Alta | Verificado en código | pns_ai_mcp | `skip_hardcoded_restrictions` aceptado desde el contexto RPC |
| PNS-11 | Alta | Reproducido (C; también con portal) | pns_ai_mcp | Métodos públicos de `ai.skill`/`ai.context` que borran o escriben en `sudo` |
| PNS-12 | Alta | Verificado en código | pns_ai_mcp | Contextos privados de otros usuarios expuestos (índice de dominios y prompts MCP) |
| PNS-13 | Alta | Inferido del código | pns_ai_mcp | `/mcp/message` no revalida clave ni usuario; sesiones sin caducidad |
| PNS-14 | Alta | Reproducido (lecturas); clave de caché verificada en código | pns_ai_mcp | Cachés legibles por todos, caché de `api_call` sin usuario, `ai.safe.choice` sin reglas |
| PNS-15 | Alta | Verificado en código | pns_ai_mcp, pns_base | HTML sin sanear (XSS) en varias vías |
| PNS-16 | Alta | Verificado en código | pns_ai_mcp | Prompt injection sin defensas combinada con auto-confirmación |
| PNS-17 | Alta | Verificado en código | pns_ai_mcp | `fetch_url` sin protección SSRF ni límite de tamaño |
| PNS-18 | Alta | Verificado en código | pns_ai_mcp | Datos hacia el proveedor LLM sin control por modelo, campo o empresa |
| PNS-19 | Alta | Inferido del código | pns_ai_mcp | Secretos accesibles desde el sandbox mediante `sudo()` |
| PNS-20 | Alta | Verificado en código | pns_ai_mcp, pns_base | Copias de configuración con secretos e importación que sobrescribe |
| PNS-21 | Alta | Verificado en código | pns_ai_mcp | Exportaciones del chat descargables sin sesión; URL con token hacia el LLM |
| PNS-22 | Alta | Verificado en código | pns_ai_mcp | La puerta `group_ai_writer` de `tools/call` no se aplica |
| PNS-23 | Alta | Verificado en código | pns_ai_mcp | Skills activadas sin revisión (captura desde el chat, importación ZIP) |
| PNS-24 | Alta | Verificado en código | pns_ai_mcp | `module.update`: `sudo`, commit y lista de vetos insuficiente |
| PNS-25 | Alta | Inferido del código | pns_ai_mcp | Failover tras ejecutar herramientas: posible doble ejecución |
| PNS-26 | Alta | Verificado en código | pns_ai_mcp | Commits fuera del flujo transaccional |
| PNS-27 | Alta | Verificado en código | pns_ai_mcp | jsPDF 2.5.1 y SheetJS 0.18.5 con CVE conocidas en todo el backend |
| PNS-28 | Media | Verificado en código | pns_ai_mcp | CORS `*`, sin validación de `Origin` y registro de peticiones no autenticadas |
| PNS-29 | Media | Verificado en código | pns_ai_mcp | Sin topes de gasto; tokens no contabilizados en varias rutas |
| PNS-30 | Media | Verificado en código | pns_ai_mcp | `ai.log`: sin retención, filas modificables, auditoría borrada en cascada |
| PNS-31 | Media | Verificado en código | pns_ai_mcp | Parches globales sobre Odoo fuera del ámbito PNS |
| PNS-32 | Media | Verificado en código | pns_ai_mcp | Sincronización de fábrica: sobrescribe ediciones y borra carpetas en disco |
| PNS-33 | Media | Verificado en código | pns_ai_mcp | Claves MCP: query string, prefijo en log, hash sin sal, sin caducidad |
| PNS-34 | Media | Verificado en código | pns_ai_mcp | Un test hace commit de una clave MCP predecible para el administrador |
| PNS-35 | Media | Inferido del código | pns_ai_mcp | Inyección de fórmulas en exportaciones XLSX |
| PNS-36 | Media | Verificado en código | pns_ai_mcp | Esquema de cualquier modelo y nombre de la BD expuestos por MCP |
| PNS-37 | Media | Verificado en código | pns_ai_mcp | Diario de cambios incompleto y valores sin redactar |
| PNS-38 | Media | Verificado en código | pns_ai_mcp | Conocimiento de fábrica que induce acciones de sistema y cita campos inexistentes en 14 |
| PNS-39 | Media | Verificado en código | pns_ai_mcp | Desviaciones de la especificación MCP |
| PNS-40 | Media | Verificado en código | pns_ai_mcp | Parámetros de protocolo LLM rechazados por modelos recientes; endpoint en el error |
| PNS-41 | Media | Verificado en código | pns_base | `website` de todos los módulos reescrito e `index.html` servido sin sanear |
| PNS-42 | Media | Verificado en código | pns_base | Cambio global del JS de validación y del CSS de obligatorios |
| PNS-43 | Baja | Verificado en código | pns_base | Descarte silencioso de traducciones duplicadas en cualquier carga |
| PNS-44 | Baja | Verificado en código | pns_base | Escrituras en `ir.module.module` durante la carga del registro |
| PNS-45 | Baja | Verificado en código | pns_ai_mcp | `ImportError` silenciado al registrar herramientas MCP |
| PNS-46 | Baja | Inferido del código | pns_ai_mcp | El glosario `es_ES` probablemente no llega a la parte fija del prompt |
| PNS-47 | Baja | Verificado en código | pns_ai_mcp | Sin red, cada `check_health` espera los timeouts de las fuentes FX |
| PNS-48 | Baja | Verificado en código | pns_ai_mcp | Menú Settings inaccesible para AI Administrator; acciones duplicadas |
| PNS-49 | Baja | Verificado en código | pns_ai_mcp | Código muerto |
| PNS-50 | Baja | Verificado en código | pns_ai_mcp | Tests no cargados o descartados; sin tests de seguridad negativa |
| PNS-51 | Baja | Verificado en código | pns_ai_mcp | Módulo `platform` permitido en el sandbox |
| PNS-52 | Baja | Verificado en código | pns_base | `settings_io`: defaults con `lambda self` y selecciones dinámicas sin validar |
| PNS-53 | Crítica | Verificado en código | pns_ai_chatboo | XSS almacenado entre usuarios a través de `chatboo.session.messages` |
| PNS-54 | Crítica | Verificado en código | pns_ai_chatboo, pns_ai_mcp | Cualquier XSS en el chat confirma y ejecuta operaciones de la Caja B sin el usuario |
| PNS-55 | Alta | Reproducido (`chatboo.session`); `chatboo.async.request`, verificado en código | pns_ai_chatboo | Sin aislamiento entre usuarios en `chatboo.session` y `chatboo.async.request` |
| PNS-56 | Alta | Inferido del código | pns_ai_chatboo | Inyección en el siguiente turno de otro usuario mediante el estado de su sesión |
| PNS-57 | Alta | Inferido del código | pns_ai_chatboo | Turnos lanzados por RPC sin clave MCP y sobre sesiones ajenas |
| PNS-58 | Alta | Inferido del código | pns_ai_chatboo | `/chatboo/stream` sin CSRF, con `cors='*'` y cuerpo `text/plain` |
| PNS-59 | Alta | Verificado en código | pns_ai_chatboo | Salida de datos sin clic mediante imágenes externas en las respuestas |
| PNS-60 | Alta | Verificado en código | pns_ai_chatboo, pns_ai_mcp | HTML del asistente insertado sin sanear en el cliente de Chatboo |
| PNS-61 | Media | Verificado en código | pns_ai_chatboo | Agente, proveedor e historial elegidos por el navegador |
| PNS-62 | Media | Verificado en código | pns_ai_chatboo | Adjuntos e imágenes sin límites de tamaño ni truncado |
| PNS-63 | Media | Verificado en código | pns_ai_chatboo | Retención de sesiones solo al volver a usar el chat |
| PNS-64 | Media | Verificado en código | pns_ai_chatboo | Lectura en voz alta con voces remotas |
| PNS-65 | Media | Verificado en código | pns_ai_chatboo | Exportaciones generadas en el navegador (HTML sin escapar, columnas ocultas, subida automática) |
| PNS-66 | Media | Verificado en código | pns_ai_chatboo, pns_ai_mcp | Skills de fábrica sin control de grupo |
| PNS-67 | Media | Verificado en código | pns_ai_chatboo | Errores funcionales en skills financieras |
| PNS-68 | Media | Verificado en código | pns_ai_chatboo | Migraciones que borran skills por código sin filtrar el dueño |
| PNS-69 | Baja (antes Media) | No reproducido en Odoo 14 con `hr` | pns_ai_chatboo | `SELF_READABLE_FIELDS` / `SELF_WRITEABLE_FIELDS` redefinidos como `property` |
| PNS-70 | Media | Inferido del código | pns_ai_chatboo | Choque de `window.Chart` con el Chart.js de Odoo 14 |
| PNS-71 | Baja | Verificado en código | pns_ai_chatboo | `check_health` y `/chatboo/providers` exponen infraestructura; errores con estado 200 |
| PNS-72 | Baja | Verificado en código | pns_ai_chatboo | 7 librerías JS cargadas para todos los internos |
| PNS-73 | Baja | Inferido del código | pns_ai_chatboo | Sintaxis sin transpilar y posibles conflictos con diálogos del core |
| PNS-74 | Baja | Verificado en código | pns_ai_chatboo | Código muerto o heredado en el cliente web |
| PNS-75 | Baja | Inferido del código | pns_ai_chatboo | Copia TSV al portapapeles sin neutralizar fórmulas |
| PNS-76 | Baja | Inferido del código | pns_ai_chatboo | Receta del agente distinta en bases actualizadas y nuevas; menú tras generar la clave |
| PNS-77 | Baja | Verificado en código | pns_ai_chatboo | Sin tests |
| PNS-78 | Baja | Reproducido | pns_ai_mcp | Dos pares de campos de `ai.agent` con la misma etiqueta (aviso al instalar) |

---

## 2. Usuarios y llamadas de las pruebas

Para las pruebas A-D se crearon dos usuarios en la base de datos de pruebas:

| Etiqueta | uid | Grupos | `base.group_system` |
|---|---|---|---|
| INTERNO | 8 | `base.group_user` (y `base.group_no_one`, añadido por Odoo); **ningún grupo de IA ni de administración** | No |
| PORTAL | 9 | `base.group_portal` | No |

Todas las llamadas usan JSON-RPC: autenticación con `/web/session/authenticate` y después
`/web/dataset/call_kw` con la cookie de sesión obtenida. Las contraseñas se omiten.

```json
POST /web/session/authenticate
{"jsonrpc": "2.0", "method": "call",
 "params": {"db": "<bd>", "login": "<login>", "password": "<omitida>"}}
```

---

## 3. Hallazgos críticos

### PNS-01 — Escalada a `base.group_system` por `ai.system.action.apply_user_add_group`

- **Gravedad:** Crítica · **Estado:** Reproducido (prueba A) · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/models/ai_system_action.py:117-118` (`AbstractModel`),
  `:716` (`apply_user_add_group`, `@api.model`), `:672-680` (`_resolve_user`, `sudo`),
  `:682-696` (`_resolve_group`, `sudo`); `pns_base/utils/compat.py:113-116` (`user_add_group`);
  `pns_ai_mcp/security/ir.model.access.csv:67` (ACL solo `group_ai_admin`).

**Descripción.** `apply_user_add_group` es un método público `@api.model` de un `AbstractModel`.
Resuelve usuario y grupo con `sudo()` y escribe `groups_id` sobre el registro `sudo` sin
comprobar quién llama. El ACL de `ai.system.action` (línea 67) no se evalúa porque el método no
realiza ninguna operación ORM sobre su propio modelo.

**Reproducción.**

```json
POST /web/dataset/call_kw   (sesión de INTERNO, uid=8)
{"jsonrpc": "2.0", "method": "call",
 "params": {"model": "ai.system.action", "method": "apply_user_add_group",
            "args": [], "kwargs": {"user_id": 8, "group": "base.group_system"}}}
```

```json
POST /web/dataset/call_kw   (sesión de PORTAL, uid=9)
{"jsonrpc": "2.0", "method": "call",
 "params": {"model": "ai.system.action", "method": "apply_user_add_group",
            "args": [], "kwargs": {"user_id": 9, "group": "base.group_system"}}}
```

**Resultado observado.** Ambas devuelven
`{"result": {"ok": true, "user_id": <8|9>, "group_id": 3, "model": "res.users", "ids": [<8|9>], ...}}`.
Comprobación posterior: ambos usuarios tienen `base.group_system` y `base.group_erp_manager`. Un
usuario de portal pasa a ser administrador de Odoo.

**Impacto.** Toma de control completa de la base de datos por cualquier usuario autenticado,
incluidos usuarios externos de portal. Ninguna configuración de grupos lo evita.

**Recomendación.** Los métodos `apply_*` (y `preview_*`) deberían comprobar explícitamente, al
inicio y antes de cualquier `sudo()`, que el usuario real de la petición es administrador de Odoo
(`base.group_system`) y AI Administrator, o bien no ser invocables por RPC (métodos privados con
`_`, llamados solo desde el flujo supervisado tras su propia verificación). Conviene no confiar
en el ACL de un `AbstractModel` como control de acceso. Un test negativo con un usuario interno
y otro de portal evitaría regresiones.

### PNS-02 — Resto de métodos `apply_*` de `ai.system.action` sin control de permisos

- **Gravedad:** Crítica · **Estado:** Reproducido parcialmente (prueba B: `preview_module_update`;
  en la segunda ronda, un usuario de portal invoca `preview_user_add_group` y
  `preview_module_update` sin `AccessError`); los `apply_*` distintos de PNS-01, verificados en
  código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/models/ai_system_action.py:606` (`preview_module_update`), `:630-668`
  (`apply_module_update`), `:746` (`apply_user_remove_group`), `:347`, `:381`, `:428`, `:450`,
  `:472`, `:497` (`apply_view_*`, `apply_field_set_required`).

**Descripción.** Todos los `apply_*` tienen la misma forma que PNS-01 (`@api.model` + `sudo()`
sin comprobación). `apply_module_update` instala, actualiza o **desinstala** módulos con
`button_immediate_*` (que hace `commit`).

**Reproducción (solo la vista previa; `apply_module_update` no se invocó deliberadamente).**

```json
POST /web/dataset/call_kw   (sesión de INTERNO, uid=8)
{"jsonrpc": "2.0", "method": "call",
 "params": {"model": "ai.system.action", "method": "preview_module_update",
            "args": [], "kwargs": {"module": "pns_base", "operation": "upgrade"}}}
```

**Resultado observado.** `{"result": "Will upgrade module 'PNS Base' (current state: installed)"}`,
sin `AccessError`.

**Impacto.** Cualquier usuario autenticado podría desinstalar módulos (con sus datos), quitar
grupos a administradores o alterar vistas y obligatoriedad de campos de cualquier modelo.

**Recomendación.** La misma que PNS-01, aplicada a todos los métodos públicos del modelo.

### PNS-03 — El propietario modifica `status` y `user_id` de su `ai.safe.operation`

- **Gravedad:** Crítica · **Estado:** Reproducido (prueba D) · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/models/mcp_safe_operation.py:123` (`user_id`), `:156` (`status`),
  `:225` (`operation_data`); `pns_ai_mcp/security/ir.model.access.csv:5` (`base.group_user`
  con `write=1`); `pns_ai_mcp/security/security.xml:92-96` (regla por `user_id`).

**Descripción.** Los campos de control están declarados `readonly=True`, lo que solo afecta a la
vista. El ACL concede escritura a `base.group_user` y no hay override de `write()` ni
`@api.constrains` que impidan cambiar `status`, `user_id` u `operation_data`.

**Reproducción.** Preparación: `ai.safe.operation` id=1 a nombre de INTERNO, `status='pending'`,
plan vacío.

```json
POST /web/dataset/call_kw   (sesión de INTERNO, uid=8)
{"jsonrpc": "2.0", "method": "call",
 "params": {"model": "ai.safe.operation", "method": "write",
            "args": [[1], {"status": "confirmed"}], "kwargs": {}}}
```

```json
{"jsonrpc": "2.0", "method": "call",
 "params": {"model": "ai.safe.operation", "method": "write",
            "args": [[1], {"user_id": 2}], "kwargs": {}}}
```

**Resultado observado.** Ambas devuelven `{"result": true}`. Estado final: `status=confirmed`,
`user_id=2`, `executed=False`. Una lectura posterior por INTERNO da `AccessError` (la regla de
registro ya no le deja verlo): el problema no es el acceso a operaciones ajenas, sino que el dueño
manipula el estado de supervisión de la suya.

**Impacto.** Se salta la confirmación humana. Encadenado con PNS-04 o PNS-05, el plan
auto-confirmado se ejecuta con otro usuario o como superusuario.

**Recomendación.** Impedir la escritura directa de los campos de control (`status`, `user_id`,
`operation_data`, `executed`, `result_info`, `expires_at`, `confirmed_by`) salvo desde los
métodos internos del flujo, por ejemplo con un override de `write` que solo los acepte bajo un
contexto interno que no pueda llegar por RPC, o quitando `write` del ACL de `base.group_user` y
operando siempre a través de métodos que validen la transición de estado.

### PNS-04 — `resolve_*` y `confirm_by_user` ejecutan con un `confirmed_uid` elegido por quien llama

- **Gravedad:** Crítica · **Estado:** Inferido del código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/models/mcp_safe_operation.py:527` (`confirm_by_user`), `:579`
  (`resolve_confirm`), `:706` (`resolve_execute`), `:805` (`resolve_confirm_and_execute`), `:831`
  (`api.Environment(cr2, uid, …)` en `_execute_plan_with_timeouts`). La comprobación de dueño solo
  existe en el controlador (`pns_ai_mcp/controllers/verification_ui.py:16-37`) y en los botones.

**Descripción.** Los cuatro métodos son públicos, aceptan `confirmed_uid` y no comprueban ni la
propiedad de la operación ni que ese uid sea el usuario de la sesión. El plan se ejecuta en un
entorno con ese uid; con `confirmed_uid=1` Odoo 14 activa el modo superusuario. Las comprobaciones
de permisos del plan se evalúan sobre el uid elegido.

**Impacto.** Un interno con una operación propia puede, combinando PNS-03 (escribir el plan y
`status`) y `resolve_execute(confirmed_uid=1)`, ejecutar como superusuario un plan arbitrario
(por ejemplo `user.add_group` con `base.group_system`).

**Recomendación.** Que estos métodos no acepten el uid como parámetro desde RPC: deberían usar
siempre `self.env.uid` de la petición y verificar que es el dueño (o un AI Administrator cuando el
flujo lo prevea). Si se necesita un uid distinto internamente, la variante debería ser privada.

### PNS-05 — `get_safe_operation_status` busca sin filtrar por usuario y ejecuta en `sudo`

- **Gravedad:** Crítica · **Estado:** Inferido del código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/controllers/safe_plan.py:1907` (`env['ai.safe.operation'].sudo()`),
  `:1909-1911` (búsqueda por `verification_id` sin filtro de usuario), `:1936-1942`
  (`execute_plan_now()` sobre el registro `sudo`); `pns_ai_mcp/models/mcp_safe_operation.py:1235`
  (`execute_plan_now`, conserva `su=True`).

**Descripción.** La herramienta del LLM que consulta el estado de una operación la busca como
superusuario, sin limitarla al usuario actual, y si está `confirmed` y sin ejecutar la ejecuta en
ese mismo entorno `sudo`: las escrituras del plan ignoran ACL y reglas. Los `verification_id` son
secuenciales y predecibles.

**Impacto.** Con PNS-03, cualquier usuario con acceso al chat ejecuta CRUD como superusuario
pidiendo al LLM que consulte el estado. Además puede leer el `result_info` de operaciones ajenas y
disparar su ejecución.

**Recomendación.** Buscar con el entorno del usuario (o filtrar por `user_id = env.uid`) y no
ejecutar nunca desde esta herramienta; si debe ejecutar, hacerlo con el entorno del usuario que
confirmó y tras validar la confirmación.

### PNS-06 — El `code_body` de una skill se ejecuta al guardarla, sin solo lectura

- **Gravedad:** Crítica · **Estado:** Verificado en código (flujo); la persistencia del efecto es
  inferida · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/models/ai_skill.py:395` (se descarta `requires_write`), `:407-415`
  (smoke-run con `bootstrap_skill_code_body(self.env, …)` en el constraint), `:500-526`
  (`create`/`write` no revisan el código); `pns_ai_mcp/controllers/validators.py:1992-2004`;
  `pns_ai_mcp/security/ir.model.access.csv:20` (`group_ai_writer` 1,1,1,1).

**Descripción.** Un AI Writer puede crear skills con código. El constraint de contrato ejecuta el
código al guardar, con el `env` del autor, en la misma transacción y sin cursor de solo lectura.
El validador AST marca `requires_write` pero en skills ese valor se descarta, de modo que ni un
`.sudo().write(...)` literal se bloquea. Una vez activa, quien invoque la skill la ejecuta con sus
propios permisos.

**Impacto.** Un Writer puede escalar privilegios (por ejemplo llamando a `apply_user_add_group`)
o escribir cualquier dato con solo guardar una skill; también puede hacer que un administrador
ejecute su código al invocarla.

**Recomendación.** Ejecutar el smoke-run en un cursor de solo lectura (o en un savepoint que se
revierta siempre) y rechazar en skills el código que el validador marque como de escritura, igual
que hace la herramienta relaxaicode con la Caja A.

### PNS-07 — `getattr` dinámico desde el sandbox a métodos que abren cursores con escritura

- **Gravedad:** Crítica · **Estado:** Inferido del código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/controllers/validators.py:166-168, 966-976` (el detector de
  `getattr` solo cubre `create/write/unlink/copy`), `:928-944` (`side_effect_methods`, solo para
  llamadas literales); `pns_ai_mcp/controllers/context_builder.py:124-143` (`guarded_getattr`);
  `pns_ai_mcp/models/mcp_safe_operation.py:603, 828, 949, 1134, 1189, 1471` (`registry.cursor()`
  propios) y `:1171` (`commit`).

**Descripción.** Una llamada literal a `resolve_execute`, `execute_plan_now` o `cleanup_*` desde
relaxaicode se rechaza, pero la misma llamada mediante `getattr(obj, 'resolve_execute')()` no la
detecta el AST ni la bloquea `guarded_getattr`. Esos métodos abren cursores nuevos sin solo
lectura y hacen `commit`.

**Impacto.** Código generado por el LLM (o inducido por prompt injection) puede persistir cambios
saltándose la garantía de solo lectura de la Caja A.

**Recomendación.** Bloquear en `guarded_getattr` todos los nombres de `side_effect_methods` (no solo
los mutadores ORM), o mejor, impedir que los métodos que abren cursores propios sean alcanzables
desde el sandbox.

---

## 4. Hallazgos de gravedad alta

### PNS-08 — Credenciales de `ai.api.server` legibles por cualquier usuario interno

- **Estado:** Reproducido (segunda ronda: un interno sin grupos de IA lee `auth_token`, `env_vars`
  y `config_json` en claro) · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/models/external_server.py:176-182` (`auth_token`, sin `groups`),
  `:209-213` (`env_vars`, sin `groups`), `config_json` con los mismos valores en claro;
  `pns_ai_mcp/security/ir.model.access.csv:7` (lectura para `base.group_user`) y `:8`
  (`ai.api.server.key` 1,1,1,1 para `base.group_user`).

**Descripción.** Los tokens y variables de entorno de los servidores externos se guardan en claro
y cualquier usuario interno puede leerlos por RPC. `config_json` los duplica.

**Impacto.** Robo de credenciales de servicios de terceros.

**Recomendación.** Restringir esos campos con `groups` (AI Administrator), no duplicarlos en
`config_json` y revisar el ACL de `ai.api.server.key` (que cada usuario solo vea las suyas
mediante una regla de registro).

### PNS-09 — Servidores MCP `stdio`: comando libre, entorno completo, sin timeout

- **Estado:** Verificado en código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/utils/mcp_client.py:134-165` (`Popen` con `os.environ` + `env_vars`),
  `:180` (`readline()` bloqueante), `:323-341` (`close()`);
  `pns_ai_mcp/lib/api/drivers/mcp_driver.py:31-39, 59-64, 72-78` (sin `try/finally`);
  `pns_ai_mcp/models/external_server.py:874` (`action_discover_tools`) y `:993`
  (`action_test_connection`), sin control de grupo.

**Descripción.** El comando es libre y hereda todo el entorno del proceso de Odoo (incluidas, en
contenedores, las credenciales de PostgreSQL). No hay timeout de lectura y el proceso hijo puede
quedar vivo si el handshake falla. Los métodos de prueba y descubrimiento son invocables por
cualquier interno, lo que lanza el comando configurado.

**Impacto.** AI Administrator equivale a ejecución de comandos en el sistema operativo; cualquier
interno puede provocar la ejecución del comando configurado y bloquear workers.

**Recomendación.** Limitar `stdio` a una lista de comandos permitidos o desactivarlo por defecto,
pasar al hijo un entorno mínimo, aplicar timeout de lectura y cerrar siempre el proceso, y exigir
grupo en `action_test_connection` / `action_discover_tools`.

### PNS-10 — `skip_hardcoded_restrictions` aceptado desde el contexto RPC

- **Estado:** Verificado en código (explotación inferida) · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/models/ai_context.py:1520`; `pns_ai_mcp/models/ai_skill.py:515, 535`.

**Descripción.** La guarda Python que impide a un no administrador cambiar `owner_id`,
`context_type` o `is_system` se salta si el contexto trae `skip_hardcoded_restrictions=True`, y
`call_kw` acepta el contexto que envía el cliente. En Odoo 14 `write` evalúa las reglas de registro
sobre el estado anterior, no sobre el resultado.

**Impacto.** Un AI Writer puede convertir su contexto o skill en global o `core` e inyectar
instrucciones de forma persistente en el prompt de todos los usuarios, incluidos los que confirman
operaciones.

**Recomendación.** No leer banderas de seguridad del contexto de la petición: usar una marca que no
pueda llegar por RPC (por ejemplo un atributo de instancia, o comprobar `self.env.su` en los
caminos internos de importación).

### PNS-11 — Métodos públicos de `ai.skill` / `ai.context` que borran o escriben en `sudo`

- **Estado:** Reproducido (prueba C, invocación; en la segunda ronda, también por un usuario de
  portal) · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/models/ai_skill.py:1599` (`unlink_named_factory_skills`), `:1551`
  (`unlink_retired_from_module`), `:848` (`hide_unprefixed_slash_twins`), `:751`
  (`reapply_source_module_prefixes`), `:486` (`sync_slash_hidden_from_field`);
  `pns_ai_mcp/models/ai_context.py:1399-1426` (`record_context_usage`, SQL directo);
  `pns_ai_mcp/security/ir.model.access.csv:16` (`ai.skill` solo lectura para `base.group_user`).

**Reproducción.**

```json
POST /web/dataset/call_kw   (sesión de INTERNO, uid=8)
{"jsonrpc": "2.0", "method": "call",
 "params": {"model": "ai.skill", "method": "unlink_named_factory_skills",
            "args": [["no_existe_prueba"]], "kwargs": {}}}
```

**Resultado observado.** `{"result": 0}` sin `AccessError`. No se borró nada porque se usó un
nombre inexistente a propósito; con nombres reales de skills de fábrica (`owner_id = False`) el
método las borraría con `sudo` y `skip_hardcoded_restrictions=True`.

**Impacto.** Un usuario con solo lectura borra o renombra skills de fábrica de cualquier módulo PNS
y altera contadores y fechas de contextos.

**Recomendación.** Hacer privados estos métodos (los llaman los hooks de sincronización) o exigir
superusuario / AI Administrator al inicio.

### PNS-12 — Contextos privados de otros usuarios expuestos

- **Estado:** Verificado en código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/utils/agent_engine.py:738, 743, 749-766` (índice de dominios leído con
  `sudo`); `pns_ai_mcp/models/ai_context.py:600-604, 667-670` (`get_listable_for_mcp`,
  `get_context_for_country` sin filtro de dueño); `pns_ai_mcp/controllers/main.py:1510-1521,
  1665-1719` (prompts MCP servidos como superusuario).

**Descripción.** El motor lee las filas `discovery` y sus cuerpos con `sudo`, y `prompts/list` /
`prompts/get` listan contextos sin aplicar la regla de propiedad.

**Impacto.** El contenido de un contexto privado se inyecta en turnos de otros usuarios y aparece
en el catálogo MCP de todos.

**Recomendación.** Aplicar en estas lecturas el mismo dominio de propiedad que la regla de registro
("sin dueño o propios") o hacerlas con el entorno del usuario.

### PNS-13 — `/mcp/message` no revalida clave ni usuario; sesiones sin caducidad

- **Estado:** Inferido del código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/controllers/main.py:653-663` (si la clave ya no existe o el usuario
  está archivado, continúa con `session.mcp_user_id`), `:986-994` (sesiones de `initialize`);
  `pns_ai_mcp/utils/session_store.py:193-209` (`cleanup_expired`, nunca llamado).

**Descripción.** POST `/mcp/message` solo compara la clave con la guardada en la sesión y no
comprueba que siga vigente ni que el usuario esté activo. Las sesiones no caducan.

**Impacto.** Una clave revocada o la de un usuario archivado sigue ejecutando herramientas con un
id de sesión antiguo hasta reiniciar Odoo; la cola de respuestas crece en memoria.

**Recomendación.** Revalidar clave y usuario activo en cada mensaje y llamar periódicamente a
`cleanup_expired`.

### PNS-14 — Cachés legibles por todos, caché de `api_call` sin usuario, `ai.safe.choice` sin reglas

- **Estado:** Reproducido en las lecturas (segunda ronda: un interno sin grupos de IA accede a
  ambas cachés y lee la `ai.safe.choice` de otro usuario); la clave de caché sin usuario y la
  modificación de elecciones ajenas, verificadas en código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/security/ir.model.access.csv:9, 10` (`ai.fetch.cache`,
  `ai.api.result.cache` lectura para `base.group_user`), `:69` (`ai.safe.choice` 1,1,1,1 para
  `base.group_user`, sin regla de registro); `pns_ai_mcp/utils/api_call_result.py:14-18` (clave
  `sha256(server + tool + argumentos)` sin usuario).

**Impacto.** Respuestas obtenidas con la credencial de un usuario se sirven a otro durante 10
minutos; cualquier interno lee cachés ajenas y altera elecciones de otros usuarios.

**Recomendación.** Incluir el usuario (o la credencial efectiva) en la clave de caché, restringir
la lectura de las cachés y añadir una regla de propiedad a `ai.safe.choice`.

### PNS-15 — HTML sin sanear (XSS)

- **Estado:** Verificado en código (Python); la explotación en el cliente web es inferida ·
  **Módulos:** pns_ai_mcp, pns_base
- **Ubicación:** `pns_ai_mcp/utils/relaxaicode_render.py:897` (celda base64 sin escapar) y
  `:649, 657, 672, 692` (`href` sin filtro de esquema); `author_html` de skills sin saneado;
  `pns_ai_mcp/static/src/js/showdown.js` (Markdown → HTML sin filtro, insertado con `innerHTML`
  por el chat); `pns_ai_mcp/static/src/js/pns_html_readonly_widget_v14.js:11-13` (`$el.html`);
  `pns_ai_mcp/wizard/context_stats_wizard.py:33, 120-123` (`Html(sanitize=False)` con
  interpolación sin escapar); `pns_base/models/operation_report_wizard.py:36`
  (`result_html` con `sanitize=False`; `pns.export.file.wizard` creable por cualquier interno).

**Descripción.** La salida del LLM y varios datos (celdas de tablas, nombres de agentes y
contextos, textos de skills) llegan al DOM sin saneado. No hay `html_sanitize`, `bleach` ni
DOMPurify en estas rutas.

**Impacto.** Un texto controlado por un tercero (un dato de Odoo leído en el turno, una respuesta
inducida por prompt injection) puede ejecutar JavaScript en la sesión de quien lee el chat, incluido
un administrador.

**Recomendación.** Sanear en el servidor (`html_sanitize`) todo HTML que no sea generado
íntegramente por la plataforma, escapar siempre los valores interpolados, filtrar esquemas de
`href` (solo `http`, `https`, `mailto`) y pasar el HTML de Showdown por un saneador antes de
insertarlo. Evitar `sanitize=False` en campos que pueda escribir un usuario.

### PNS-16 — Prompt injection sin defensas combinada con auto-confirmación

- **Estado:** Verificado en código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/utils/agent_engine.py:672-722, 2167-2174` (registro en pantalla
  inyectado en rol `system`); `pns_ai_mcp/models/url_whitelist.py:191-192` y
  `pns_ai_mcp/controllers/safe_plan.py:584-589` (política `open`: auto-confirma y añade el dominio);
  `pns_ai_mcp/controllers/safe_plan.py:362-367` (`api_call` auto-confirmado a servidores
  `trusted`).

**Descripción.** Texto no confiable (campos del registro abierto, resultados de herramientas,
descripciones de herramientas externas) llega al modelo sin delimitar, en parte con rol `system`.
El modelo ve todas las herramientas sin filtrar por usuario, y `fetch_url` (política `open`) y
`api_call` (servidores `trusted`) se ejecutan sin humano.

**Impacto.** Un dato malicioso en Odoo puede inducir peticiones externas sin confirmación, incluida
la exfiltración de datos del turno.

**Recomendación.** Enviar los datos de registros y resultados en roles `user`/`tool` y delimitados,
no en `system`; filtrar las herramientas visibles según los grupos del usuario; y no auto-confirmar
acciones con salida externa cuando el turno contiene datos no confiables.

### PNS-17 — `fetch_url` sin protección SSRF ni límite de tamaño

- **Estado:** Verificado en código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/controllers/safe_plan.py:1237-1244` (`allow_redirects=True`, solo se
  valida el host inicial), `:1248` (`resp.content` completo); `pns_ai_mcp/utils/fetch_url_safe.py:36-39`
  (solo esquema); drivers OpenAPI que dejan que la especificación remota elija el host y le envían
  la credencial.

**Impacto.** Acceso a direcciones internas (localhost, base de datos, metadatos de la nube) y
consumo de memoria del worker con respuestas grandes.

**Recomendación.** Resolver el nombre y rechazar direcciones privadas, de loopback y link-local,
validar cada salto de redirección, limitar el tamaño leído (`stream=True` con tope) y fijar el host
de OpenAPI en la configuración del servidor, no en la especificación.

### PNS-18 — Datos hacia el proveedor LLM sin control por modelo, campo o empresa

- **Estado:** Verificado en código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/controllers/tools_relaxaicode.py:31-32` (hasta 50 000 filas / ~2 MB por
  resultado); `pns_ai_mcp/utils/agent_engine.py:2167-2174` (registro en pantalla en cada turno);
  `pns_ai_mcp/utils/llm_usage.py:51-63` (`is_on_premise` solo afecta al coste mostrado).

**Descripción.** No existe lista de modelos o campos excluidos, filtro por empresa ni
anonimización. El failover a un proveedor externo envía los mismos datos.

**Impacto.** Dificulta el cumplimiento de protección de datos: no se puede garantizar qué sale de la
instalación.

**Recomendación.** Ofrecer una lista configurable de modelos y campos que nunca se envían, un tope
de filas hacia el LLM independiente del de la herramienta y una opción que impida el failover de un
proveedor local a uno externo.

### PNS-19 — Secretos accesibles desde el sandbox mediante `sudo()`

- **Estado:** Inferido del código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/controllers/context_builder.py:56-102` (el entorno guardado solo bloquea
  `ai.context` y `ai.api.server`).

**Descripción.** El sandbox permite `env.sudo()`. Código como
`env.sudo()['ai.provider'].search([]).mapped('api_key')` o la lectura de `database.secret`
devolvería el valor, que el motor envía al proveedor en el siguiente mensaje `tool`.

**Recomendación.** No exponer `sudo()` en el sandbox o bloquear explícitamente los modelos y
parámetros con secretos (`ai.provider`, `ir.config_parameter`, `ai.mcp.user`, `res.users.apikeys`).

### PNS-20 — Copias de configuración con secretos e importación que sobrescribe

- **Estado:** Verificado en código · **Módulos:** pns_ai_mcp, pns_base
- **Ubicación:** `pns_ai_mcp/utils/config_backup.py:125-126, 188-190` ("sin secretos" no vacía
  `config_json`), `:200-231` (hash MCP siempre incluido), `:287` (`replace_existing=True` fijo);
  `pns_ai_mcp/models/res_config_settings.py:172` (desde Ajustes, siempre con secretos);
  `pns_base/utils/settings_io.py:336` (`include_secrets=True` por defecto); adjuntos nunca borrados
  (`pns_base/utils/portable_io.py:273-287`).

**Impacto.** Claves en el filestore de forma indefinida; importar un fichero ajeno puede introducir
servidores `stdio` de confianza, proveedores con endpoint ajeno o la política de URL `open`.

**Recomendación.** Excluir secretos por defecto (también de `config_json`), borrar los adjuntos
tras la descarga y mostrar un resumen de cambios antes de aplicar una importación.

### PNS-21 — Exportaciones del chat descargables sin sesión; URL con token hacia el LLM

- **Estado:** Verificado en código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/utils/session_download.py:504-511` (adjunto creado con `sudo`),
  `:404-431, 525-526` (commit inmediato), `:549-569` (URL con `access_token` en el metadato para el
  LLM); `pns_ai_mcp/controllers/session_file.py:18-56` (`auth='public'`).

**Impacto.** Cualquiera con la URL descarga exportaciones con datos de negocio sin iniciar sesión,
y esa URL puede salir hacia el proveedor LLM.

**Recomendación.** Servir las descargas con `auth='user'` y comprobación de dueño, no incluir la URL
con token en el contexto del LLM y caducar o purgar los adjuntos.

### PNS-22 — La puerta `group_ai_writer` de `tools/call` no se aplica

- **Estado:** Verificado en código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/controllers/main.py:1322-1393, 1403-1412` (la comprobación solo cubre
  dos nombres no registrados; `is_write` no dispara nada); `pns_ai_mcp/utils/agent_engine.py:3381-3441`
  (`DummyController` del motor sin la puerta).

**Impacto.** `clean_system` (que borra) se puede ejecutar sin ser AI Writer.

**Recomendación.** Comprobar `group_ai_writer` en `tools/call` y en el `DummyController` para toda
herramienta con `is_write=True`.

### PNS-23 — Skills activadas sin revisión

- **Estado:** Verificado en código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/wizard/skill_capture_wizard.py:190` (`'active': bool(self.from_chatboo)`),
  `:67-90` (`from_chatboo` desde el contexto); `pns_ai_mcp/models/ai_skill.py:1129-1218`
  (importación ZIP deja `active=True`).

**Impacto.** Código nuevo queda disponible para todos sin revisión de un administrador; solo el AST
lo protege (ver PNS-06).

**Recomendación.** Crear siempre las skills capturadas o importadas como inactivas hasta su
aprobación por un AI Administrator.

### PNS-24 — `module.update`: `sudo`, commit y lista de vetos insuficiente

- **Estado:** Verificado en código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/models/ai_system_action.py:36-40` (solo veta desinstalar `base`, `web`,
  `pns_base`, `pns_ai_mcp`), `:568-668` (`ir.module.module` en `sudo`).

**Descripción.** El `sudo()` salta `assert_log_admin_access` del core, la operación hace commit y
recarga el registro (rompe la atomicidad del plan) y no veta `mail` ni `bus`, cuya desinstalación
arrastra a `pns_ai_mcp` y a casi todo lo demás. Se marca como irreversible.

**Recomendación.** No usar `sudo` para las operaciones de módulo (que el core compruebe al usuario
real), vetar las dependencias del propio módulo y avisar de las desinstalaciones en cascada.

### PNS-25 — Failover tras ejecutar herramientas: posible doble ejecución

- **Estado:** Inferido del código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/utils/agent_engine.py:1775-1782` (el siguiente proveedor repite el
  turno desde cero), `:1722-1819` (cascada).

**Impacto.** Operaciones auto-confirmadas (`fetch_url`, `api_call` de confianza) pueden ejecutarse
dos veces si el proveedor falla después de la primera ronda de herramientas.

**Recomendación.** No hacer failover tras haber ejecutado herramientas con efectos, o reanudar el
turno con los resultados ya obtenidos.

### PNS-26 — Commits fuera del flujo transaccional

- **Estado:** Verificado en código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/controllers/main.py:1436-1449` (toda excepción de herramienta se
  convierte en un resultado y la petición termina con commit); `pns_ai_mcp/models/mcp_safe_operation.py:1171,
  1337` (commits sobre el cursor del llamador); cursores auxiliares con commit en proveedores, logs y
  diario.

**Impacto.** Efectos parciales de una herramienta que falla quedan guardados.

**Recomendación.** Hacer rollback (o usar un savepoint) cuando una herramienta falla y evitar
`commit()` sobre el cursor de la petición.

### PNS-27 — jsPDF 2.5.1 y SheetJS 0.18.5 con CVE conocidas en todo el backend

- **Estado:** Verificado en código · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/static/src/js/jspdf.umd.min.js` (2.5.1: CVE-2025-29907,
  CVE-2025-57810), `pns_ai_mcp/static/src/js/xlsx.full.min.js` (0.18.5: CVE-2023-30533,
  CVE-2024-22363); cargadas en `web.assets_backend` por `pns_ai_mcp/views/assets.xml`.

**Descripción.** `pns_ai_mcp` no las usa; las usa `pns_ai_chatboo`, que además carga otra copia.

**Recomendación.** Actualizar a versiones corregidas y cargarlas solo en el módulo que las usa.

---

## 5. Hallazgos de gravedad media (defectos de código)

### PNS-28 — CORS `*`, sin validación de `Origin` y registro de peticiones no autenticadas
- **Ubicación:** `pns_ai_mcp/controllers/main.py:350, 517, 546, 562` (`Access-Control-Allow-Origin: *`),
  `:1015-1031` y `:134-198` (registro en `ai.log` antes de autenticar).
- **Descripción e impacto:** la especificación MCP exige validar `Origin` (protección frente a DNS
  rebinding). Cualquier web visitada por un usuario puede generar filas en `ai.log`.
- **Recomendación:** validar `Origin` contra una lista configurable y no registrar en base de datos
  las peticiones sin clave válida (o limitarlas).

### PNS-29 — Sin topes de gasto; tokens no contabilizados en varias rutas
- **Ubicación:** `pns_ai_mcp/utils/agent_engine.py:157-176` (respaldo no-stream descarta `usage`),
  `:179-239` (`llm_json_completion`).
- **Descripción e impacto:** no hay tope de gasto, tokens ni turnos; parte del consumo (incluida la
  caché de Anthropic) no se registra, por lo que el coste mostrado es inferior al real.
- **Recomendación:** contabilizar `usage` en todas las rutas y ofrecer topes configurables.

### PNS-30 — `ai.log`: sin retención, filas modificables, auditoría borrada en cascada
- **Ubicación:** `pns_ai_mcp/models/ai_log.py:51` (`ondelete='cascade'`), `:606-643` (hasta 100 000
  caracteres por campo); `pns_ai_mcp/security/ir.model.access.csv:35` (AI admin 1,1,1,1).
- **Descripción e impacto:** guarda prompts, respuestas, código y resultados sin retención automática;
  un AI Administrator puede modificar filas por RPC; borrar un usuario borra su auditoría.
- **Recomendación:** retención configurable con cron, quitar `write` del ACL y usar `ondelete='set null'`
  o `restrict`.

### PNS-31 — Parches globales sobre Odoo fuera del ámbito PNS
- **Ubicación:** `pns_ai_mcp/http_patch.py:9, 22-35` (`Root.get_request`);
  `pns_ai_mcp/models/ir_model_fields_selection.py:23-43` (backport global de `_process_ondelete`);
  `set_values` de `res.config.settings` (se ejecuta al guardar cualquier pantalla de Ajustes); 9
  `ListController.include`, `FormRenderer.include` (`pns_ai_mcp/static/src/js/mcp_log_form_v14.js:10-112`),
  oyente global de clics y `MutationObserver` de todo el DOM
  (`pns_ai_mcp/static/src/js/ai_agent_origin_filter_v14.js:303-352`).
- **Descripción e impacto:** cualquier defecto en estos parches afecta a módulos ajenos; el backport
  oculta valores de selección huérfanos de otros módulos; el observador del DOM tiene coste en todo el
  backend.
- **Recomendación:** acotar cada parche a las rutas, modelos o vistas PNS (por ejemplo, con
  comprobaciones de clase CSS o de modelo antes de actuar).

### PNS-32 — Sincronización de fábrica: sobrescribe ediciones y borra carpetas en disco
- **Ubicación:** `pns_ai_mcp/models/ai_context.py:415-431` (`_register_hook`), `:1646-1665`
  (`shutil.rmtree` de `ai/contexts/domain/self/` en cualquier addon instalado);
  `pns_ai_mcp/hooks.py:217-234`.
- **Descripción e impacto:** en cada cambio de sello sobrescribe y reactiva contextos editados por el
  administrador, borra carpetas del código desplegado y puede ejecutarse en paralelo en varios workers
  (transacciones abortadas).
- **Recomendación:** no borrar archivos del addons path, respetar las ediciones locales (marca de
  "modificado") y serializar la sincronización con un bloqueo.

### PNS-33 — Claves MCP: query string, prefijo en log, hash sin sal, sin caducidad
- **Ubicación:** `pns_ai_mcp/controllers/main.py:424-444, 716-722` (`?api_key=`), `:866, 872`
  (10 primeros caracteres en el log INFO); `pns_ai_mcp/utils/api_key.py:35-48` (SHA-256 sin sal).
- **Descripción e impacto:** la clave en la URL queda en logs del proxy, historial y `Referer`; el
  prefijo en el log facilita ataques; no hay caducidad.
- **Recomendación:** aceptar la clave solo por cabecera, no registrar ningún fragmento, usar un hash
  con sal (o HMAC con secreto del servidor) y añadir fecha de caducidad.

### PNS-34 — Un test hace commit de una clave MCP predecible para el administrador
- **Ubicación:** `pns_ai_mcp/tests/_helpers.py:143-162, 173-201` (`pns-http-test-<bd>` y
  `env.cr.commit()`); `pns_ai_mcp/tests/test_safe_plan_atomicity.py:59, 62-67`; `pns_ai_mcp/tests/test_system_action.py:429-447`.
- **Impacto:** ejecutar los tests sobre una copia de producción deja al administrador con una clave
  conocida y activa.
- **Recomendación:** generar claves aleatorias y no hacer commit en tests (usar el cursor de test o
  `registry.enter_test_mode`).

### PNS-35 — Inyección de fórmulas en exportaciones XLSX (Inferido del código)
- **Ubicación:** `pns_ai_mcp/controllers/formatters.py:424-425`; `pns_ai_mcp/utils/artifact_export.py:1579-1584,
  1654-1662`.
- **Descripción e impacto:** las celdas de texto se escriben con `str(value)`; un dato que empiece por
  `=` se exporta como fórmula (por ejemplo `=HYPERLINK(...)`).
- **Recomendación:** escapar los valores que empiecen por `=`, `+`, `-`, `@` o forzar tipo cadena.

### PNS-36 — Esquema de cualquier modelo y nombre de la BD expuestos por MCP
- **Ubicación:** `pns_ai_mcp/controllers/tools_system.py:160-281` (`fetch_native_mcp_resource`,
  `fields_get` sin permiso de lectura del modelo); `pns_ai_mcp/utils/system_info.py:87-107`
  (`system://info`).
- **Recomendación:** exigir permiso de lectura del modelo antes de `fields_get` y limitar
  `system://info` a administradores.

### PNS-37 — Diario de cambios incompleto y valores sin redactar
- **Ubicación:** `pns_ai_mcp/models/ai_change_journal.py:376-378` (`intended_values` sin redactar),
  `:411-494` (reversión); `pns_ai_mcp/utils/change_journal.py:30-38` (redacción por nombre; no cubre
  `env_vars` ni `config_json`).
- **Descripción e impacto:** no revierte `unlink`, módulos, grupos, campos redactados ni x2many
  vacíos; `field.set_required` sobre campos de módulo solo cambia la memoria del worker.
- **Recomendación:** documentar qué es reversible, ampliar la redacción y redactar también los planes
  fallidos.

### PNS-38 — Conocimiento de fábrica que induce acciones de sistema y cita campos inexistentes en 14
- **Ubicación:** `pns_ai_mcp/ai/contexts/` (contextos de fábrica).
- **Descripción e impacto:** el conocimiento empuja al modelo a proponer instalaciones, cambios de
  grupos y peticiones externas, y cita campos que no existen en Odoo 14.
- **Recomendación:** revisar el conocimiento por versión de Odoo y no sugerir acciones de sistema por
  defecto.

### PNS-39 — Desviaciones de la especificación MCP
- **Ubicación:** `pns_ai_mcp/controllers/main.py:981-984, 596-597` (204 en lugar de 202), GET `/mcp`
  con un evento suelto, 200 en errores de autenticación, sin `isError`.
- **Impacto:** clientes estrictos pueden fallar; sin selector de BD, con varias bases de datos y sin
  `dbfilter` `/mcp` devuelve 404 HTML.
- **Recomendación:** alinear códigos de estado y formato de errores con la especificación.

### PNS-40 — Parámetros de protocolo LLM rechazados; endpoint en el mensaje de error
- **Ubicación:** `pns_ai_mcp/utils/agent_engine.py:2029` (`temperature or 0.7`: 0 pasa a 0.7),
  `:204, 231` (`max_tokens`), `:2213-2229` (`image_url` también hacia Anthropic), `:2853-2864`
  (endpoint en el error, pese al comentario de `:4197`).
- **Impacto:** modelos recientes rechazan la petición y se activa el failover; el usuario final ve
  detalles de infraestructura.
- **Recomendación:** respetar `temperature = 0`, omitirla cuando el modelo no la admita, usar
  `max_completion_tokens` donde corresponda, el formato de imagen propio de Anthropic, y no mostrar
  endpoints al usuario.

### PNS-41 — `pns_base`: `website` de todos los módulos reescrito e `index.html` servido sin sanear
- **Ubicación:** `pns_base/models/ir_module_module.py:75-105` (`_pns_localize_websites` en cada
  arranque y en `update_list`); `pns_base/views/ir_module_views.xml:8-14` (iframe con la
  descripción).
- **Descripción e impacto:** afecta a todos los módulos con `index.html` (core, OCA y propios). El
  iframe sirve el HTML en el mismo origen y con la sesión del administrador, sin el saneado que
  aplica el core: un `index.html` con JavaScript se ejecutaría con sus privilegios.
- **Recomendación:** limitarlo a módulos PNS y servir la descripción saneada o en un iframe con
  `sandbox`.

### PNS-42 — `pns_base`: cambio global del JS de validación y del CSS de obligatorios
- **Ubicación:** `pns_base/static/src/js/pns_invalid_fields_dedupe.js:40-153`;
  `pns_base/static/src/css/pns_required_readonly.css:4-13`.
- **Descripción e impacto:** modifica el aviso de campos obligatorios en todos los formularios y
  listas de edición múltiple, dependiendo de métodos privados del cliente web que también
  sobrescriben módulos `web_*` habituales.
- **Recomendación:** activarlo solo en vistas PNS o hacerlo opcional.

---

## 6. Hallazgos de gravedad baja (defectos de código)

| ID | Ubicación | Descripción | Recomendación |
|---|---|---|---|
| PNS-43 | `pns_base/models/ir_translation.py:39-51` | Al cargar un idioma con sobrescritura, descarta en silencio (solo WARNING) filas duplicadas de cualquier módulo. | Limitarlo a módulos PNS o informar al usuario. |
| PNS-44 | `pns_base/models/ir_module_module.py:75-85, 81, 90` | Escribe en `ir.module.module` durante `_register_hook`; si falla a nivel PostgreSQL la transacción queda abortada (excepción capturada). `get_module_path(display_warning=True)` avisa en cada arranque por módulos sin código. | Hacerlo en `update_list` solo, con savepoint, y sin avisos. |
| PNS-45 | `pns_ai_mcp/controllers/__init__.py:13-22` | `try/except ImportError: pass` al importar las herramientas: si una falla, sus herramientas MCP desaparecen sin error. | Registrar el error en el log. |
| PNS-46 | Composición del prompt (`ai.agent`) | Inferido: el glosario `es_ES` probablemente no llega a la parte fija del prompt tras normalizar; una caché por agente e idioma que se recompila a menudo. | Revisar la normalización del idioma. |
| PNS-47 | Fuentes FX (`check_health`) | Sin salida a Internet, cada `check_health` espera los timeouts de las dos fuentes (hasta 8 s); el error no se cachea. | Cachear el fallo durante un tiempo. |
| PNS-48 | Menús y acciones | El menú Settings se muestra a AI Administrator, pero exige también `base.group_system`; acciones "Export/Import skills ZIP" duplicadas en el menú Acción. | Alinear `groups` del menú con el acceso real; quitar duplicados. |
| PNS-49 | Varios | Código muerto: `controllers/moe_controller.py`, `controllers/write_verification.py` (con tabla errónea), `cleanup_stuck_state`, tokens de confianza, `web_read`, `search_fetch`, `api_key_migration`, `ActionManager.include`, `_onToggleBoolean`, `showdown.min.js`, driver `ollama` no seleccionable. | Eliminarlo o documentarlo. |
| PNS-50 | `pns_ai_mcp/tests/` | `test_change_journal` y `test_session_download` no importados; `test_presentation_mode` (`unittest.TestCase` sin `@tagged`) lo descarta el cargador de 14; sin cobertura del motor LLM ni tests de seguridad negativa (XSS, autenticación, permisos). | Importar y adaptar los tests; añadir tests negativos para PNS-01 a PNS-07. |
| PNS-51 | `pns_ai_mcp/controllers/validators.py:92` | El módulo `platform` está permitido en el sandbox: datos del SO accesibles al código del LLM. | Quitarlo de la lista permitida. |
| PNS-52 | `pns_base/utils/settings_io.py:113-114, 188-198`; `pns_base/utils/portable_io.py:157-158` | `field_default` llama a `default(None)`: un default `lambda self: self.env…` lanzaría `AttributeError` (no capturado en `read_settings_icp`); las selecciones definidas por método no se validan. | Llamar al default con un recordset vacío y validar selecciones dinámicas. |
| PNS-78 | `pns_ai_mcp/models/ai_agent.py:138-176` | Reproducido: al instalar, Odoo avisa de que dos pares de campos de `ai.agent` tienen la misma etiqueta: `context_ids_shown` / `context_ids` ("Contexts") y `skill_ids_shown` / `skill_ids` ("Skills"). Cosmético, pero confunde en filtros, agrupaciones y exportaciones. | Dar etiquetas distintas a los campos calculados (por ejemplo "Contexts (shown)"). |

### 6.1 Resultado de la ejecución de los tests de `pns_ai_mcp` (relacionado con PNS-50)

Ejecutados en una base de datos de tests nueva, con `pns_ai_chatboo` y `hr` instalados y sin
proveedor de IA configurado: **125 tests, 110 pasan, 4 se saltan y 11 terminan en fallo o
error** (5 fallos y 6 errores). Los tests identificados en el registro, por causa:

| Tests afectados | Error | ¿Depende del entorno? |
|---|---|---|
| `test_relaxaicode_model_stamp`: `test_related_models_from_product_id`, `test_stamp_both_sibling_lists_with_env` | `KeyError: 'product.product'` | **Sí**: necesitan el módulo `product`, que `pns_ai_mcp` no declara como dependencia. El test debería saltarse si no está instalado. |
| `test_system_action`: `test_accept_choice_creates_verification`, `test_field_required_propose_opens_choice` | `NOT NULL` en la columna `comment` de `res.partner` | **Sí**: el test marca el campo como obligatorio sobre datos de demostración que lo tienen vacío. El test debería preparar sus propios registros. |
| `test_mcp_agent`: `test_resolve_inference_via_feature_key`, `test_get_providers_for_agent_without_admin_acl` | `UserError: Inference agent 'pns_ai_chatboo' is not configured or inactive` / "chatboo agent must exist" | **Sí**: dependen de que exista y esté configurado el agente de Chatboo con proveedor. El test debería crear su propio agente y proveedor de prueba. |
| `test_knowledge_composition`: `test_composition_origin_four_tokens`, `test_composition_read_orders_by_origin` | `AssertionError: 'extra' != 'imported'` | **En parte**: fallan con `pns_ai_chatboo` instalado, cuyos contextos alteran el resultado esperado. Es una combinación de módulos del propio fabricante, así que el test debería tolerarla. |
| `test_safe_plan_atomicity`: `test_failed_execute_cancels_authorization_no_replay`, `test_normal_execution_marks_executed_and_applies_mutation` | `PermissionError: … not in the AI Writer group` | **No**: el usuario del test no tiene el grupo que el código exige. Hay que revisar la preparación del test o el control de permisos. |

Además se saltan 4 tests de `TestKnowledgeComposition` y `TestKnowledgeOwnership`. Recomendamos que
la batería pase en una instalación mínima (solo las dependencias declaradas) y que cada test que
necesite otro módulo o un proveedor configurado lo compruebe y se salte con un motivo explícito.

---

## 7. Compatibilidad con Odoo 14

### 7.1 `external_dependencies` sin usar

`pns_ai_mcp/__manifest__.py:29-33` declara `openpyxl`, `reportlab`, `requests`, `httpx` y
`pydantic`. **`httpx` y `pydantic` no se importan en el código** (`httpx` solo aparece como nombre
prohibido en el sandbox; el "shim v1/v2" que menciona el comentario del manifest no existe). Como Odoo
comprueba `external_dependencies` antes de instalar, una instalación de Odoo 14 sin esas dos librerías
no puede instalar el módulo aunque no las necesite. `openpyxl` sí se usa (exportación XLSX) pero no
viene con Odoo 14.

**Recomendación:** quitar `httpx` y `pydantic` de `external_dependencies` y corregir el comentario.

### 7.2 Versión `3.1.x`: los scripts de migración no se ejecutan

`pns_ai_mcp` declara `'version': '3.1.486'` (`__manifest__.py:7`) y `pns_base` `'1.2.10'`. Odoo 14
antepone la serie y las convierte en `14.0.3.1.486` y `14.0.1.2.10`. En cambio, las carpetas de
`pns_ai_mcp/migrations/` (68 scripts: 65 `post-migrate.py` y 3 `pre-migrate.py`) se llaman `3.1.x`.
El gestor de migraciones de Odoo 14 (`odoo/modules/migration.py`, `convert_version`) solo antepone
la serie a versiones con menos de dos puntos, así que trata `3.1.484` como versión completa y compara
`14.0.3.1.483 < 3.1.484`, que es falso. Por tanto, según el código del cargador, **ningún script de
migración se ejecuta en 14** (incluida la migración de claves en claro) y las actualizaciones futuras
que dependan de una migración no se aplicarán.

**Estado: Reproducido.** Al actualizar `pns_ai_mcp` en el entorno de pruebas, el registro de Odoo no
muestra la ejecución de ningún script de migración.

**Recomendación:** publicar para 14 con versión `14.0.x.y.z` y carpetas de migración con ese mismo
formato (o con la versión completa `14.0.3.1.x`).

### 7.3 APIs de Python 3.8+ / 3.9+

Odoo 14 funciona con Python 3.6-3.8 y es habitual en 3.7. No hay sintaxis incompatible, pero sí APIs
de la biblioteca estándar:

| API | Versión | Ubicación | Efecto en 3.7 |
|---|---|---|---|
| `ast.unparse` | 3.9 | `pns_ai_mcp/controllers/validators.py:290, 426, 579` | Cae en `except`: las reparaciones automáticas de código no se aplican y los literales grandes se rechazan siempre. |
| `ast.get_source_segment` | 3.8 | `pns_ai_mcp/utils/relaxaicode_recipe.py:507` (llamado desde `controllers/tools_relaxaicode.py:1706`) | `AttributeError` posiblemente no capturado cuando el código del LLM define una función con parámetro de fecha. |
| `zoneinfo` / `ZoneInfo` | 3.9 | `pns_ai_mcp/ai/contexts/core/system_prompt.xml:70, 84` | El prompt de sistema lo anuncia como precargado y permitido, pero no existe: el código generado con zonas horarias falla. |
| `get_type_hints(..., include_extras=True)` | 3.9 | `pns_ai_mcp/controllers/mcp_decorators.py:103` | `TypeError` latente si una herramienta declara parámetros explícitos (hoy ninguna entra en esa rama). |

Además, `from __future__ import annotations` en `pns_base/utils/portable_io.py:18` y
`pns_base/utils/settings_io.py:17` exige Python 3.7 (con 3.6 `pns_base` no carga) y no se usa en esos
archivos; el comentario del manifest de `pns_ai_mcp` indica 3.6 como mínimo.

**Recomendación:** usar alternativas compatibles con 3.7 (o declarar el mínimo real), y que el prompt
de sistema solo anuncie lo disponible en la versión de Python en ejecución.

### 7.4 Cron sin `numbercall`

`pns_ai_mcp/data/api_result_cache_cron.xml:5-13` ("AI: purge expired api_call result cache") no
define `numbercall` ni `doall`, a diferencia de los otros dos crons
(`data/fetch_cache_cron.xml:13`, `data/safe_operation_cron.xml:13`, con `numbercall=-1`). En Odoo 14
el valor por defecto de `numbercall` es 1, así que el cron se desactiva tras su primera ejecución y la
caché de `api_call` deja de purgarse.

**Estado: Reproducido.** En el entorno de pruebas, el programador ejecutó el cron una sola vez, en la
primera hora tras la instalación. Después quedó con `numbercall=0` y `nextcall` sin avanzar, mientras
los otros dos crons seguían ejecutándose. Reactivarlo (`active=True`) no basta: el programador solo
toma los crons con `numbercall != 0`. Una vez corregido el XML, como el archivo de datos es
`noupdate="1"`, las bases de datos ya instaladas también necesitarán que una migración corrija
`numbercall` en el registro existente.

**Recomendación:** añadir `<field name="numbercall">-1</field>` y `<field name="doall" eval="False"/>`.

---

## 8. Hallazgos de pns_ai_chatboo 2.1.322

`pns_ai_chatboo` ("Chatboo") es el chat de IA del backend: cada turno lo resuelve `pns_ai_mcp`
(agente `pns_ai_chatboo`) en un hilo con cursor propio, y el cliente web recibe la respuesta por
SSE. Se ha revisado entero el código propio del módulo (Python, XML, JS y CSS); de las librerías
de terceros solo se han leído cabecera y versión. En la segunda ronda se ha reproducido PNS-55
(para `chatboo.session`) y se ha comprobado que PNS-69 no se produce con `hr`; para el resto, el
estado indica si el comportamiento se ha leído en el código o se deduce de él. La instalación de
`pns_ai_chatboo` es limpia salvo el aviso de PNS-78.
Rutas relativas a `pns_ai_chatboo/` salvo que se indique otro módulo; los archivos JS están en
`static/src/js/`.

### 8.1 Hallazgos críticos

### PNS-53 — XSS almacenado entre usuarios a través de `chatboo.session.messages`

- **Estado:** Verificado en código (permisos y punto de inserción); la escritura en sesiones
  ajenas en la que se apoya está reproducida (PNS-55) · **Módulo:** pns_ai_chatboo
- **Ubicación:** `security/ir.model.access.csv:2` (`chatboo.session` para `base.group_user` con
  1,1,1,1, sin `ir.rule`); `chatboo_component_v2.js:1052-1089` (carga del historial) y `:5564`
  (`t-raw="msg.content"`).

**Descripción.** No hay reglas de registro sobre `chatboo.session`, así que cualquier usuario
interno puede escribir por `call_kw` el campo `messages` de la sesión de otro usuario, incluido un
administrador. Al abrir Chatboo, el cliente formatea los mensajes del asistente con
`formatContent` sin sanear y pinta los del usuario tal cual cuando contienen ciertas etiquetas;
ambos acaban en `t-raw`. El origen no es el LLM: basta el ORM.

**Impacto.** Ejecución de JavaScript en la sesión de la víctima al abrir el chat. Con una víctima
administradora, el atacante actúa como administrador de Odoo (y, ver PNS-54, confirma
operaciones supervisadas).

**Recomendación.** Añadir reglas de registro que limiten `chatboo.session` y
`chatboo.async.request` a su dueño (PNS-55) y sanear todo HTML que se pinte en el chat (PNS-60).

### PNS-54 — Cualquier XSS en el chat confirma y ejecuta operaciones de la Caja B sin el usuario

- **Estado:** Verificado en código (cliente); la ausencia de controles adicionales dentro de
  `resolve_confirm` es inferida · **Módulos:** pns_ai_chatboo, pns_ai_mcp
- **Ubicación:** `chatboo_component_v2.js:2149-2169` (espera de 5 s solo en el botón y solo para
  `danger_level == 'high'`), `:2181-2234` (llamadas a confirmar y ejecutar);
  `pns_ai_mcp/controllers/verification_ui.py:16-64` (rutas `auth='user'`, sin comprobación de
  tiempo en `:39-54`; un administrador MCP actúa sobre operaciones ajenas en `:29-31`).

**Descripción.** La única barrera entre una propuesta de escritura y su ejecución es la tarjeta
del navegador. Las rutas `/pns_ai_mcp/verification/pending`, `/confirm` y `/execute` solo exigen
sesión y ser dueño (o `group_ai_admin`), por lo que un script que se ejecute en la página puede
listar, confirmar y ejecutar operaciones sin interacción. El XSS puede venir de PNS-53, PNS-60 o
PNS-15, también disparado por *prompt injection* sin clic.

**Impacto.** Salto del control humano de escrituras; con la sesión de un administrador MCP, sobre
operaciones de otros usuarios.

**Recomendación.** Además de eliminar las vías de XSS, exigir en servidor una confirmación que un
script de la página no pueda producir (por ejemplo un token de un solo uso ligado a la interacción
o reautenticación para riesgo alto) y aplicar en servidor la espera para operaciones `high`.

### 8.2 Hallazgos de gravedad alta

### PNS-55 — Sin aislamiento entre usuarios en `chatboo.session` y `chatboo.async.request`

- **Estado:** Reproducido para `chatboo.session` (segunda ronda: un interno sin grupos de IA lee,
  modifica y borra por RPC la sesión de otro; un usuario de portal recibe `AccessError`);
  `chatboo.async.request`, adjuntos y `read_progress`, verificados en código · **Módulo:**
  pns_ai_chatboo
- **Ubicación:** `security/ir.model.access.csv:2-3` (sin `ir.rule` en el módulo);
  `models/chatboo_session.py:458, 467` (método público que busca adjuntos y crea tokens con
  `sudo` sin comprobar dueño), `:1003-1033` (`unlink` que borra en `sudo` jobs y adjuntos);
  `models/chatboo_async_request.py:1603-1626` (`read_progress` lee cualquier job por SQL).

**Descripción.** El acceso a Chatboo (la clave MCP) se comprueba en las rutas del controlador,
pero no en el ORM. Por RPC, cualquier interno, con o sin clave, lee, modifica y borra las sesiones
de otros (mensajes, filas de la última consulta, código, contexto de pantalla), sus adjuntos y
`access_token`, y los jobs con imágenes y ficheros en base64.

**Impacto.** Fuga de conversaciones y datos de negocio entre todos los usuarios internos; base de
PNS-53, PNS-56 y PNS-57.

**Recomendación.** Reglas de registro por `user_id` para ambos modelos, ACL de jobs solo de
lectura para el usuario (el servidor los crea), y comprobación de dueño en los métodos públicos
que trabajan con `sudo`.

### PNS-56 — Inyección en el siguiente turno de otro usuario mediante el estado de su sesión

- **Estado:** Inferido del código · **Módulo:** pns_ai_chatboo
- **Ubicación:** `models/chatboo_async_request.py:336-352, 493-505`.

**Descripción.** El turno reutiliza `last_query_code`, `last_query_data`, `active_skill_code` /
`active_skill_params` y `messages` de la sesión: el código como pista para el LLM y las filas como
`previous_result` en el sandbox. Por PNS-55, otro usuario puede escribirlos.

**Impacto.** Instrucciones y datos falsos que el LLM procesa con el `env` de la víctima.

**Recomendación.** Corregir PNS-55 y tratar estos campos como datos no confiables (no
reinyectarlos como instrucciones).

### PNS-57 — Turnos lanzados por RPC sin clave MCP y sobre sesiones ajenas

- **Estado:** Inferido del código · **Módulo:** pns_ai_chatboo
- **Ubicación:** `models/chatboo_async_request.py:230-253` (`spawn()` público que ejecuta el motor
  con el `uid` del registro); ACL de creación en `security/ir.model.access.csv:3`.

**Descripción.** Un interno puede crear un `chatboo.async.request` con `session_id` y `user_id`
ajenos (campos editables) y llamar a `spawn()`. El turno consume proveedor sin pasar por la
comprobación de la clave y `_save_to_session` lo escribe en la sesión de la víctima.

**Impacto.** Coste no autorizado y contenido arbitrario en conversaciones de otros.

**Recomendación.** Hacer `spawn()` privado (o comprobar dueño y clave), no permitir `create` desde
el cliente y fijar `user_id` al usuario actual.

### PNS-58 — `/chatboo/stream` sin CSRF, con `cors='*'` y cuerpo `text/plain`

- **Estado:** Inferido del código · **Módulo:** pns_ai_chatboo
- **Ubicación:** `controllers/chatboo.py:654-835` (`type='http'`, `csrf=False`, `cors='*'`),
  `:670` (`json.loads` del cuerpo sin exigir `Content-Type: application/json`).

**Descripción.** Una petición simple entre orígenes (sin *preflight*) es válida. La cookie de
sesión de Odoo 14 no lleva `SameSite`, así que los navegadores que no aplican `Lax` por defecto la
enviarían desde una web de terceros.

**Impacto.** Una web externa puede lanzar turnos en nombre del usuario conectado (coste,
herramientas de lectura, propuestas de escritura). Combinado con PNS-16, el texto del turno lo
elige el atacante.

**Recomendación.** Activar la protección CSRF (o exigir `application/json` y un token propio),
quitar `cors='*'` y validar `Origin`.

### PNS-59 — Salida de datos sin clic mediante imágenes externas en las respuestas

- **Estado:** Verificado en código · **Módulo:** pns_ai_chatboo
- **Ubicación:** `chatboo_formatters.js:283-340` (Markdown → HTML sin filtro), `:547-582`
  (`_wrapStandaloneImages`, sin filtro de dominio ni de esquema); `chatboo_component_v2.js:2461-2466`
  (reformateo en cada token).

**Descripción.** Las imágenes de dominios externos que aparezcan en la respuesta (en Markdown o
HTML) se cargan al asignar el HTML en los formateadores, en cada token del streaming y en cada
recarga. No hay filtro de dominios en el cliente ni CSP en `/web`, y la lista blanca de
`fetch_url` solo controla las peticiones del servidor.

**Impacto.** Una *prompt injection* puede hacer que el LLM incluya una imagen cuya URL lleve datos
de la pantalla o de la consulta: salen hacia un tercero sin clic y sin pasar por la Caja B.

**Recomendación.** Permitir solo imágenes del propio origen (o `data:`/`blob:` generados por la
plataforma) al sanear, y documentar una CSP `img-src` recomendada para `/web`.

### PNS-60 — HTML del asistente insertado sin sanear en el cliente de Chatboo

- **Estado:** Verificado en código; la explotación de cada vía es inferida · **Módulos:**
  pns_ai_chatboo, pns_ai_mcp
- **Ubicación:**
  - `chatboo_formatters.js:778-896` (`formatContent`: deja pasar tal cual cualquier texto que
    empiece por `<` o contenga una etiqueta de bloque, y convierte el resto con Showdown sin
    saneador); `chatboo_component_v2.js:5564, 5683` (`t-raw`); `chatboo_formatters.js:553, 671`
    (`innerHTML` antes del `t-raw`, sobre nodos del documento).
  - `chatboo_formatters.js:663-749` (`enhanceHtmlProse`: toma `textContent`, que deshace el escape
    del servidor, y lo vuelve a convertir en HTML).
  - `pns_ai_mcp/controllers/safe_plan.py:790-861` (`user_ack_message` con `title` y `name` sin
    escapar) pintado por `chatboo_component_v2.js:2592-2631`.
  - `chatboo_formatters.js:100-104` (`_escapeHtml` no escapa comillas) usado en atributos en
    `chatboo_component_v2.js:3310, 5171`; `modelLabel` sin escapar en `:5074, 5202`; mensajes de
    error concatenados en `:1559, 1569, 1974, 2770, 3006, 3128`.
  - `chatboo_charts.js:2167, 2210, 2261-2262` (nombre de serie y clave de columna en la tabla de
    estadísticas por `innerHTML`).
  - `chatboo_export.js:2429-2505` (Markdown crudo del LLM convertido con Showdown y asignado a
    `innerHTML` al exportar, también en las exportaciones automáticas).

**Descripción.** El cliente de Chatboo no tiene ningún saneador (no hay DOMPurify ni equivalente;
solo una limpieza parcial para Word). Confía en el escape del servidor, que no se aplica a la
prosa del LLM, a `author_html` de skills ni a varios campos, y en varios puntos deshace ese escape.
Showdown no sanea por diseño, y la versión incluida (2.1.0) tiene además un fallo publicado de
escape de comillas en las URL de enlaces e imágenes sin versión corregida. El HTML se asigna con
`innerHTML` antes de pintarse, por lo que se procesa también durante el streaming, en cada
recarga, al leerlo en voz alta y al exportarlo.

**Impacto.** Confirma y amplía PNS-15: un texto que el LLM repita o un valor de un registro de
Odoo puede ejecutar JavaScript en la sesión de quien lee el chat; con PNS-54, saltar la Caja B.

**Recomendación.** Sanear en un único punto, justo antes de insertar, todo el HTML que llega al
DOM (lista blanca de etiquetas y atributos, sin manejadores de eventos, esquemas de URL limitados a
`http`, `https`, `mailto` y rutas propias); no deshacer el escape del servidor en
`enhanceHtmlProse`; escapar comillas en valores de atributo y escapar `title`, `name`, etiquetas de
modelo, mensajes de error, nombres de serie y claves de columna; sustituir Showdown por un
convertidor mantenido.

### 8.3 Hallazgos de gravedad media (defectos de código)

### PNS-61 — Agente, proveedor e historial elegidos por el navegador
- **Ubicación:** `controllers/chatboo.py:704` (cualquier agente activo) y lectura de
  `provider_id` (aceptado para cualquier proveedor existente en
  `pns_ai_mcp/models/ai_execution_engine.py:171-174`); `controllers/chatboo.py:311-345`
  (`/chatboo/sessions/save` guarda `backend_history`, `meta` y `records` enviados por el cliente);
  `chatboo_component_v2.js:2861-2875` (`history` enviado desde el navegador).
- **Descripción e impacto:** un usuario con clave puede usar cualquier proveedor dado de alta
  (también uno externo cuando el chat está configurado con uno local) y fabricar turnos previos o
  resultados de herramientas que el motor acepta como historial.
- **Recomendación:** restringir agente y proveedor a la cadena configurada del agente Chatboo y
  reconstruir el historial en el servidor a partir de la sesión.

### PNS-62 — Adjuntos e imágenes sin límites de tamaño ni truncado
- **Ubicación:** `models/chatboo_async_request.py:937-938, 1196-1199` (texto completo de los
  adjuntos, todas las hojas de Excel), `:769-837` (`_persist_turn_images`, crea adjuntos sin
  aplicar `pns_ai_chatboo.download_max_bytes`); cuerpo de `/chatboo/stream` sin tope.
- **Descripción e impacto:** coste de proveedor y memoria sin límite; las imágenes anteriores se
  reenvían en cada turno; los documentos subidos son además una vía de *prompt injection*
  indirecta.
- **Recomendación:** topes de tamaño y de texto extraído, aplicados también a las imágenes del
  turno y al cuerpo de la petición.

### PNS-63 — Retención de sesiones solo al volver a usar el chat
- **Ubicación:** `models/chatboo_session.py:1060-1079` (`_cleanup_old_sessions` solo para el
  usuario actual); `models/chatboo_async_request.py:49, 1812-1821` (jobs con base64 72 h).
- **Descripción e impacto:** las sesiones de usuarios que no vuelven a abrir Chatboo (inactivos,
  archivados o sin clave) y sus adjuntos con `access_token` no caducan nunca. Inferido: al borrar
  un usuario, la cascada SQL borra sus sesiones sin ejecutar el `unlink` del ORM y deja adjuntos
  huérfanos.
- **Recomendación:** cron de retención para todas las sesiones y borrado de adjuntos por ORM.

### PNS-64 — Lectura en voz alta con voces remotas
- **Ubicación:** `chatboo_tts.js:57-78` (`pickVoice` no comprueba `voice.localService`).
- **Descripción e impacto:** en navegadores que ofrecen voces en la nube, el texto de la respuesta
  (hasta 12 000 caracteres, con datos de negocio) puede enviarse a un servicio de voz de terceros
  (envío inferido).
- **Recomendación:** preferir o exigir voces locales y permitir al administrador desactivar la
  función.

### PNS-65 — Exportaciones generadas en el navegador
- **Ubicación:** `chatboo_export.js:3123, 3209-3214, 2250-2251` (`src` de imágenes sin escapar en
  Word y en el HTML subido), `:3055-3082, 3684-3686` (Word con el HTML de la burbuja; la limpieza
  solo quita `script`), `:2211-2259` (columnas del *dataset* no visibles);
  `controllers/chatboo.py:271-293` (`/chatboo/sessions/fulfill_export` acepta `mimetype` del
  cliente); `chatboo_component_v2.js:5308-5328` (subida automática de documentos pendientes).
- **Descripción e impacto:** documentos con HTML inyectable y recursos remotos que se cargan al
  abrirlos (en Windows, rutas UNC); columnas que el usuario no veía; subida sin acción del usuario.
- **Recomendación:** escapar atributos, sanear el HTML exportado, exportar solo columnas visibles,
  fijar el `mimetype` en el servidor y subir los documentos solo a petición.

### PNS-66 — Skills de fábrica sin control de grupo
- **Ubicación:** `ai/skills/system/` (`users-all`, `users-logged`, `sys-info`, `forecast`);
  `pns_ai_mcp/models/ai_skill.py:645-673` (`list_for_agent` sin filtro de grupo).
- **Descripción e impacto:** cualquier usuario con clave obtiene el censo de usuarios (incluidos
  archivados y su último acceso), quién está conectado, y nombre de base de datos, URL y versiones;
  `forecast` envía la ciudad de la compañía a un servicio externo.
- **Recomendación:** permitir declarar grupos requeridos por skill y aplicarlos al listar y al
  ejecutar.

### PNS-67 — Errores funcionales en skills financieras
- **Ubicación:** skill `financial-health` (`.py:552-566` frente a `:765`); `customer_risk_analysis.py:72-76`;
  `bal_prefix` de `analisis-financiero` (`.py:461-485`).
- **Descripción e impacto:** `financial-health` busca claves (`Indicator`) distintas de las que
  genera (`Metric`) y siempre concluye "sin acción urgente". `customer-risk-analysis` toma como
  fecha de cobro la de la propia factura (DSO cercano a cero) y hace una consulta por factura. Las
  financieras recorren todos los apuntes publicados 7 veces sin filtro de fecha ni de compañía.
  Información de negocio errónea presentada como análisis y consultas muy lentas en bases grandes.
- **Recomendación:** corregir las claves y la fecha de cobro (conciliaciones), agrupar consultas y
  filtrar por compañía y periodo.

### PNS-68 — Migraciones que borran skills por código sin filtrar el dueño
- **Ubicación:** `migrations/2.1.296/post-migrate.py:26-34` y `migrations/2.1.300/`.
- **Descripción e impacto:** borran las skills `flota` y `payroll` por código; también borrarían
  skills de usuario con ese código.
- **Recomendación:** filtrar por skills de fábrica (`owner_id` vacío y módulo de origen).

### PNS-70 — Choque de `window.Chart` con el Chart.js de Odoo 14 (Inferido del código; mecanismo verificado)
- **Ubicación:** `chatboo_charts.js:1197-1279, 1603-1622`; carga de Chart.js 4.4.8 en
  `views/assets.xml`.
- **Descripción e impacto:** Odoo 14 carga bajo demanda su Chart.js en la vista gráfico y en el
  tablero contable y sobrescribe `window.Chart`; desde ese momento los gráficos del chat usan una
  API distinta y se pintan mal hasta recargar.
- **Recomendación:** usar una referencia local a la librería (no la global) o un empaquetado que no
  dependa de `window.Chart`.

### 8.4 Hallazgos de gravedad baja (defectos de código)

| ID | Ubicación | Descripción | Recomendación |
|---|---|---|---|
| PNS-71 | `controllers/chatboo.py:66-148, 609-650, 945-950` | `/chatboo/check_health` devuelve proveedor (host y modelo) y `str(e)` a internos sin clave; `/chatboo/providers` lista con `sudo` todos los proveedores si el agente no tiene cadena; `_json_response` ignora `status` y responde 200 en los errores. | Exigir la clave, no devolver detalles de infraestructura ni excepciones y respetar el código de estado. |
| PNS-72 | `views/assets.xml:4-34`; `chatboo_systray.js:32` | 7 librerías (3 duplicadas con `pns_ai_mcp` y SheetJS sin uso) en `web.assets_backend` para todos los internos; cada carga del cliente llama a `check_health`. | Cargar las librerías bajo demanda al abrir el chat, sin duplicados, y cachear el estado. |
| PNS-73 | Bundle JS; `chatboo_systray.js:405` | Inferido: sintaxis ES2022 sin transpilar en un bundle compartido; uso de `setup()` y funciones flecha en `t-on` por verificar con OWL 1; capa con `z-index: 1050` y ocultación del panel de control que puede chocar con diálogos del core. | Transpilar al nivel soportado por Odoo 14 y revisar el apilamiento con los modales. |
| PNS-74 | `chatboo_component_v2.js:3002, 4988-5007, 5169`; `chatboo_systray.js:130-131` | Código muerto o heredado: `chatboo_floating_transfer_history`, `_saveRawForTemplate`, rama `result.error` que nunca se activa, "#undefined" en el modal de contexto, manejador `o_chatboo_dismiss_btn` con `window.open` sin `noopener`, `mail_service` inexistente en 14, `chatboo_has_access` sin lectura. | Eliminarlo; añadir `noopener` donde se abran ventanas. |
| PNS-75 | `chatboo_export.js:704-706, 2786-2796` | Inferido: la copia en TSV al portapapeles no neutraliza celdas que empiezan por `=`, `+`, `-` o `@`, que se evalúan al pegar en una hoja de cálculo. | Prefijar esas celdas como texto. |
| PNS-76 | Migraciones 2.1.217 / 2.1.237 frente a `data/ai_agent_data.xml`; `models/ir_ui_menu.py` | Inferido: el agente queda con `acl_security` en `default_context_codes` en bases actualizadas y sin él en instalaciones nuevas; el menú Chatboo puede no aparecer tras generar la clave hasta recargar (caché de `load_menus`). | Igualar la receta en datos y migraciones; invalidar la caché de menús al generar la clave. |
| PNS-69 | `models/res_users.py:30-36` | **Rebajado de Media a Baja: no reproducido en Odoo 14 con `hr`.** `SELF_READABLE_FIELDS` / `SELF_WRITEABLE_FIELDS` se redefinen como `property`, mientras que en Odoo 14 son listas de clase que otros módulos concatenan a nivel de clase (por ejemplo `hr`). Con `hr` y `pns_ai_chatboo` instalados, Odoo arranca y carga el registro sin errores ni avisos, porque `mail` (del que dependen ambos) vuelve a asignar las listas antes. El `TypeError` solo aparecería con otro orden de carga. | Extender las listas de clase como hace el core (en `__init__` del modelo, como `mail` y `hr`). |
| PNS-77 | — | El módulo no tiene tests. | Añadir tests, en especial negativos de aislamiento entre usuarios (PNS-53, PNS-55, PNS-57) y de saneado (PNS-60). |

### 8.5 Compatibilidad con Odoo 14

- **Formato de versión.** `__manifest__.py:6` declara `2.1.322` y las carpetas de `migrations/`
  se llaman `2.1.x`. Por el mismo motivo descrito en §7.2 (inferido; no comprobado para este
  módulo), es probable que esos scripts no se ejecuten en Odoo 14. Recomendamos el mismo cambio.
- **Dependencias Python.** No añade librerías obligatorias: usa `openpyxl` (ya exigida por
  `pns_ai_mcp`); `xlrd` es opcional para `.xls`.

### 8.6 Efecto de pns_ai_chatboo sobre hallazgos anteriores

| Hallazgo | Efecto |
|---|---|
| PNS-03, PNS-04 | Se agravan: además del `write` por RPC, un XSS en el chat confirma y ejecuta operaciones (PNS-54). |
| PNS-11 | Se agrava: `unlink_named_factory_skills` afecta a las 11 skills de fábrica de Chatboo. |
| PNS-15 | Se confirma en el código del cliente y se amplía (PNS-60). |
| PNS-16, PNS-17 | Se agravan: lo que el LLM repite llega al DOM, y la lista blanca de `fetch_url` no cubre las imágenes que pide el navegador (PNS-59). |
| PNS-21 | Se agrava: los adjuntos con token viven mientras viva la sesión, que puede no caducar nunca (PNS-63), y hay documentos que se suben solos (PNS-65). |
| PNS-27 | Se matiza: Chatboo carga otra copia de las mismas versiones de showdown, jsPDF y SheetJS; usa jsPDF con datos de la respuesta (aplican CVE-2025-29907 y CVE-2025-57810), no usa SheetJS. Showdown 2.1.0 tiene además una vulnerabilidad de denegación de servicio (CVE-2024-1899) y el fallo de escape de PNS-60. |
| PNS-35 | Se mitiga en la ruta del chat: el XLSX de exportación lo genera el servidor con celdas `inlineStr` escapadas, que no se evalúan como fórmulas. |
