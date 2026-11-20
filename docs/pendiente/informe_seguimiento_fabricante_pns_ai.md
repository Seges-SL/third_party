# CONFIDENCIAL — Seguimiento del informe técnico de seguridad: pns_base 1.2.32, pns_ai_mcp 3.1.782 y pns_ai_chatboo 2.1.453 (Odoo 14.0)

| | |
|---|---|
| **Destinatario** | PATANEGRA Soft |
| **Módulos** | `pns_base` 1.2.32 · `pns_ai_mcp` 3.1.782 ("AI Engine") · `pns_ai_chatboo` 2.1.453 ("Chatboo") |
| **Plataforma** | Odoo 14.0 |
| **Informe anterior** | Informe técnico de seguridad del 2026-10-08 sobre `pns_base` 1.2.10, `pns_ai_mcp` 3.1.486 y `pns_ai_chatboo` 2.1.322 (PNS-01 a PNS-80) |
| **Fecha** | 2026-10-15 |
| **Entorno de análisis** | Entorno de pruebas con Odoo 14 (Python 3.7.3, Pillow 5.4.1), con bases de datos de pruebas. Algunas pruebas funcionales con un proveedor de IA externo no pudieron completarse por indisponibilidad del proveedor y se repetirán (§8). |
| **Método** | Revisión del código de las versiones nuevas frente a las del informe anterior, hallazgo por hallazgo, y comprobación en ejecución de los cambios más relevantes (control de acceso por RPC, actualización de una base de datos existente, compatibilidad con Odoo 14). Para comprobar los módulos en Odoo 14 se aplicaron en el entorno de pruebas las cuatro correcciones mínimas descritas en §3 (la primera, imprescindible para cargar los módulos). |
| **Referencias de código** | Todas las líneas citadas son las del código publicado de estas versiones. |

---

## Índice

1. Resumen
2. Prioridad 1: métodos públicos que trabajan en `sudo`
3. Compatibilidad con Odoo 14 (PNS-81)
4. Pérdida de datos al actualizar (PNS-87, PNS-88) y nota sobre PNS-63
5. Estado de PNS-01 a PNS-92
6. Hallazgos nuevos (PNS-81 a PNS-92)
7. Peticiones menores y observaciones
8. Pendiente de comprobar por nuestra parte

---

## 1. Resumen

1. Hemos revisado `pns_base` 1.2.32, `pns_ai_mcp` 3.1.782 y `pns_ai_chatboo` 2.1.453 frente a los 80
   hallazgos del informe anterior. Agradecemos el trabajo: la versión nueva corrige o reduce todos los
   hallazgos críticos y una parte importante de los altos, y añade tests negativos de seguridad.
2. Estado de los 80 hallazgos del informe anterior: **31 corregidos, 33 parciales, 13 sin cambios,
   2 ya no aplican y 1 dudoso**. Además, hemos encontrado **12 hallazgos nuevos** (PNS-81 a PNS-92):
   9 en código nuevo o modificado de esta versión y 3 (PNS-90 a PNS-92) en código que ya existía y que
   el informe anterior no citaba.

   | Gravedad | Corregido | Parcial | Sin cambios | Ya no aplica | Dudoso | Nuevo | Total |
   |---|---|---|---|---|---|---|---|
   | Crítica | 5 | 4 | 0 | 0 | 0 | 0 | 9 |
   | Alta | 13 | 11 | 1 | 1 | 0 | 4 | 30 |
   | Media | 4 | 12 | 9 | 0 | 0 | 5 | 30 |
   | Baja | 9 | 6 | 3 | 1 | 1 | 3 | 23 |
   | **Total** | **31** | **33** | **13** | **2** | **1** | **12** | **92** |

3. **Críticos del informe anterior.** Se han repetido en el entorno de pruebas las pruebas A-D del
   informe anterior, que cubren los hallazgos críticos y PNS-11 (Alta, corregido); las vías que
   reproducían están cerradas. Estado de los críticos:
   - **Corregidos:** la modificación del estado de una operación por su propietario (PNS-03), el
     `confirmed_uid` elegido por quien llama (PNS-04), la consulta de estado sin filtro de usuario
     (PNS-05), la ejecución de skills al guardar (PNS-06) y el XSS almacenado entre usuarios (PNS-53).
   - **Parciales, con el resto acotado:** la escalada a `base.group_system` por RPC (PNS-01) y los
     métodos `apply_*`/`preview_*` públicos (PNS-02). La vía RPC del informe anterior está cerrada, pero
     un AI Administrator sin permisos de Ajustes sigue pudiendo conceder o quitar grupos de Odoo con un
     plan que él mismo confirma (§2.7).
   - **Otros restos acotados:** PNS-07 (el sandbox no bloquea los métodos privados, §2.8) y PNS-54
     (confirmación sin token ligado a la interacción).
4. **Lo más urgente ahora** es el mismo patrón que causó PNS-01: métodos públicos (sin `_`) que
   trabajan en `sudo` o con un cursor de superusuario sin comprobar grupo ni propiedad. Aparece en cinco
   hallazgos nuevos explotables hoy (entrega de claves MCP por PIN, PNS-83; caché de `fetch_url`,
   PNS-90; apropiación de adjuntos ajenos en Chatboo, PNS-82; caché de parámetros de skills, PNS-85; y
   ampliación de la lista blanca de URL, PNS-91), tres de ellos de gravedad alta y comprobados en el
   entorno de pruebas, y en un sexto, PNS-92, hoy sin efecto. En varios de ellos basta un usuario de portal. La corrección es la misma que ya se aplicó a
   `ai.system.action` (§2).
5. **Compatibilidad con Odoo 14 (PNS-81).** Con Python 3.7 o 3.8, `pns_ai_mcp` no se importa por una
   anotación de tipos de Python 3.9, y una base de datos que tenga los módulos instalados deja de cargar
   al sustituir el código. Además, tres funciones fallan en ejecución (dos sin aviso). Las cuatro correcciones
   son de una o dos líneas (§3). Pedimos una fecha prevista de corrección.
6. **Actualización de bases de datos existentes.** La actualización purga sin aviso el registro de
   actividad de más de 30 días y borra la tabla del histórico diario de consumo por proveedor
   (PNS-87); además, en Odoo 14 no se ejecutan los renombrados de XML ID de `migrations/`, y se pierden
   las personalizaciones sobre esos registros (PNS-88). Al actualizar en el entorno de pruebas se
   observó que el cron de purga se ejecuta en la primera pasada, que la tabla del histórico se borra y
   que los registros renombrados se recrean con ids nuevos; el volumen de datos borrado no se pudo medir
   (las tablas estaban vacías) y se deduce del código (§4).
7. Recomendamos priorizar, por este orden: PNS-83, PNS-90, PNS-82, PNS-85 y PNS-91 con los restos de
   PNS-01/02 y PNS-07/19 (§2); PNS-81 (§3); PNS-87 y PNS-88 (§4). El resto de peticiones (§7) es de
   menor urgencia.

---

## 2. Prioridad 1: métodos públicos que trabajan en `sudo`

### 2.1 Patrón común y corrección propuesta

En Odoo 14, `call_kw` permite invocar por RPC cualquier método cuyo nombre no empiece por `_` a
cualquier usuario autenticado, también a uno de portal, sin comprobar el ACL del modelo: solo lo
comprueban los métodos ORM, y estos métodos trabajan en `sudo()` o con un cursor propio de
superusuario. Es la causa de PNS-01 y PNS-11 del informe anterior, que la versión 3.1.782 ha corregido
correctamente en `ai.system.action` y `ai.trusted.action` (métodos privados) y en `ai.skill`
(`_require_bootstrap()`).

El mismo patrón sigue presente en estos métodos:

| Hallazgo | Gravedad | Métodos | Quién puede llamarlos hoy |
|---|---|---|---|
| PNS-83 | Alta | `ai.mcp.user.redeem_key_pin`; `ai.key.pin.block.release_all`, `note_failure`, `is_blocked` | Cualquier usuario autenticado, incluido portal |
| PNS-90 | Alta | `ai.fetch.cache.get_cached`, `store` | Cualquier usuario autenticado, incluido portal |
| PNS-82 | Alta | `chatboo.session.claim_turn_file_chips` (y `apply_assistant_download_chips`) | Cualquier usuario interno |
| PNS-85 | Media | `ai.skill.param.cache.remember_for_skill`, `lookup_for_skill`; `ai.skill.remember_param_cache`, `lookup_param_cache` | Cualquier usuario autenticado (comprobado con un interno) |
| PNS-91 | Media | `ai.url.whitelist.ensure_domain_whitelisted` | Cualquier usuario autenticado, incluido portal |
| PNS-92 | Media | `ai.mcp.user.set_mcp_api_key`, `action_generate_mcp_api_key` | Hoy sin efecto por un motivo indirecto (§6) |
| PNS-30 (resto) | Media | `ai.log.create_log_entry` | Cualquier usuario autenticado |
| PNS-37 (resto) | Media | `ai.change.journal.record_failed_plan` | Cualquier usuario autenticado |

**Corrección propuesta**, en este orden de preferencia:

1. Hacer privados (`_metodo`) los métodos que solo llama el propio motor o el flujo de confirmación, como
   se hizo con `ai.system.action`. Es el caso de PNS-90, PNS-91, PNS-85, PNS-30, PNS-37 y, si no tiene
   llamador externo, de `redeem_key_pin` (PNS-83), que no tiene llamador en los tres módulos.
2. Si el método debe seguir siendo público, comprobar al principio, antes de cualquier `sudo()`, el grupo
   y la propiedad sobre el usuario real (`ensure_ai_admin`, o la regla de propietario), como ya hace la
   versión nueva en `action_test_connection` y `action_discover_tools` (PNS-09).
3. No confiar en el ACL del modelo ni en efectos laterales (PNS-92) como control de acceso de un método
   público.
4. Añadir un test negativo por método con un usuario interno sin grupos de IA y otro de portal, como los
   nuevos de `pns_ai_mcp/tests/test_system_action.py:429-456`.

Un resumen de cada hallazgo está a continuación; el detalle completo, en §6.

### 2.2 PNS-83 — Entrega de claves MCP por PIN sin grupo y sin límite efectivo de intentos

`redeem_key_pin` (`pns_ai_mcp/models/mcp_user.py:819-860`) es público, no comprueba grupo y devuelve la
clave MCP en claro del usuario dueño de un PIN válido si hay una mesa de entrega abierta. El contador de
fallos depende de un parámetro que elige quien llama (`models/key_pin_block.py:38-40, 48-50`), y los
métodos que gestionan los bloqueos también son públicos (`:36-73`). La clave obtenida puede ser la de
un AI Administrator. **Comprobado en el entorno de pruebas:** un usuario interno y uno de portal invocan
`redeem_key_pin` y `release_all` sin error de acceso, y un intento fallido sin `ip` no crea ni incrementa
ningún bloqueo (aunque la respuesta indica `counted: true`). La entrega de la clave con un PIN válido no
se probó; se deduce del código.

**Corrección:** proponemos hacer el método privado o comprobar el grupo; basar el contador de fallos en
la IP que determina el servidor, no en un argumento; hacer privados `release_all`, `note_failure` e
`is_blocked`, y marcar el PIN como usado al canjearlo.

### 2.3 PNS-90 — Caché de `fetch_url` legible y sobrescribible por cualquier usuario

`get_cached` y `store` (`pns_ai_mcp/models/fetch_cache.py:63-89, 91-123`) leen y escriben en `sudo` una
caché global por URL, sin usuario, que `fetch_url` consulta antes de salir a la red
(`controllers/safe_plan.py:1493-1503, 1619`). Cualquier usuario puede leer lo que otros consultaron y
fijar de antemano el contenido que recibirá la herramienta de otro usuario: es una vía de prompt
injection entre usuarios (PNS-16). El ACL nuevo del modelo (solo AI Administrator) no interviene.
**Comprobado en el entorno de pruebas.**

**Corrección:** `_get_cached` y `_store`.

### 2.4 PNS-82 — Apropiación de adjuntos ajenos en Chatboo

`claim_turn_file_chips` (`pns_ai_chatboo/models/chatboo_session.py:415-441`) reasigna en `sudo` a la
sesión del llamador cualquier `ir.attachment` al que le falte `res_model` o `res_id`, sin comprobar quién
lo creó ni que lo haya generado el motor. Después, `/pns_ai_mcp/session_file` y `/web/content` lo
entregan. Entre esos adjuntos están las descargas del chat de otros usuarios y las copias de
configuración de `pns_ai_mcp`, que pueden llevar secretos. **Comprobado en el entorno de pruebas.**

**Corrección:** proponemos reclamar solo adjuntos creados por el propio usuario y marcados como
generados por el motor para ese turno, y no reasignar nunca un adjunto que ya tenga `res_model`.

### 2.5 PNS-85 — Caché de parámetros de skills escribible por cualquier usuario

`remember_for_skill` (`pns_ai_mcp/models/ai_skill_param_cache.py:125-154`) crea filas con un cursor de
superusuario y commit, para cualquier skill, en una caché sin usuario que el motor aplica en los turnos
de todos. Un usuario sin permisos de escritura puede fijar los parámetros (fechas, filtros, empresa) con
que se ejecutará una skill cuando la use otro. **Comprobado en el entorno de pruebas** para
`remember_for_skill`: un interno sin grupos de IA crea una fila sobre una skill de fábrica, que queda
creada por el superusuario. Los otros puntos de entrada proceden del código.

**Corrección:** proponemos hacer privados los métodos en ambos modelos y, si la caché debe
compartirse, escribir en ella solo desde el motor tras una ejecución real.

### 2.6 PNS-91 — Ampliación de la lista blanca de URL sin control de grupo

`ensure_domain_whitelisted` (`pns_ai_mcp/models/url_whitelist.py:235-266`) crea o reactiva hosts en la
lista blanca en `sudo`. Con la política de URL restringida, eso deja sin efecto la restricción de
salida de `remote_image` y `fetch_url`, y debilita las correcciones de PNS-16, PNS-59 y PNS-86.
**Comprobado en el entorno de pruebas.**

**Corrección:** `_ensure_domain_whitelisted`, llamado solo desde el flujo de confirmación del plan.

### 2.7 Resto de PNS-01 y PNS-02: grupos de Odoo con solo AI Administrator

La vía RPC está cerrada (comprobado en el entorno de pruebas). Queda que las acciones de confianza
`user.add_group` y `user.remove_group` solo exigen `group_ai_admin`
(`pns_ai_mcp/data/trusted_actions_system.xml:84, 94`), y `_apply_user_add_group` / `_apply_user_remove_group`
resuelven usuario y grupo en `sudo` (`pns_ai_mcp/models/ai_system_action.py:674-697, 718, 748`). Un AI
Administrator que no sea administrador de Odoo puede, con un plan que él mismo confirma, darse
`base.group_system` o quitárselo a un administrador.

**Corrección:** exigir también `base.group_system`, comprobado sobre el usuario real, como ya hace la
versión nueva para los servidores `stdio` (`pns_ai_mcp/models/external_server.py:548, 567-587`).

### 2.8 Resto de PNS-07 y PNS-19: métodos privados alcanzables desde el sandbox

`guarded_getattr` aplica ya una lista de 15 métodos con efectos
(`pns_ai_mcp/controllers/context_builder.py:123-155`; `controllers/validators.py:178-194`) y el sandbox
ya no llega a `sudo`, al cursor ni al registro. Pero sigue siendo una lista negra y, según su propio
docstring, permite los métodos con `_`. Quedan alcanzables, entre otros:

- métodos con cursor propio y commit de `ai.safe.operation`: `_execute_plan_with_timeouts` (que recibe
  el uid ejecutor, `models/safe_operation.py:866-888`), `_retry_confirmed_not_executed` (`:974-1012`),
  `_claim_execute` (`:1136-1205`), `_release_execute_claim` (`:1207`), `_clear_stale_execute_claims`
  (`:1246-1260`) y `_heal_module_update_after_registry_reset` (`:1457-1556`);
- los públicos nuevos `redeem_key_pin` y `remember_for_skill` (PNS-83, PNS-85), que no están en la lista;
- `ai.provider._api_key_for_inference()`, que devuelve la clave del proveedor leída en `sudo`
  (`models/ai_provider.py:200-208`) (PNS-19).

Hay además cursores propios en `ai_log.py`, `ai_change_journal.py`, `ai_provider.py`, `ai_agent.py`,
`ai_context.py` y `ai_skill_param_cache.py` que no hemos revisado uno a uno.

**Corrección:** proponemos bloquear en el sandbox los métodos que empiezan por `_`, con una lista de
excepciones de solo lectura (como `_name` o `_fields`), y pasar a una lista de métodos permitidos en
lugar de una lista de prohibidos.

---

## 3. Compatibilidad con Odoo 14 (PNS-81)

Entorno de referencia: imagen oficial de Odoo 14 (Debian Buster), con Python 3.7.3 y Pillow 5.4.1
(Odoo 14 fija `Pillow==5.4.1` con Python ≤ 3.7 en su `requirements.txt:34`). Hemos analizado todos los
`.py` de los tres módulos en busca de sintaxis y API posteriores a Python 3.7 y de API de librerías no
disponibles en esa imagen. Resultado: **1 fallo al importar, 3 fallos en ejecución**; los demás usos
están protegidos (`try/except` o `getattr`) y solo degradan funciones secundarias.

| # | Archivo:línea | Qué falla | Efecto | Corrección mínima |
|---|---|---|---|---|
| 1 | `pns_ai_mcp/controllers/mcp_decorators.py:169` | Anotación de retorno `tuple[bool, Optional[str]]` (Python 3.9), evaluada al definir la función; el archivo no tiene `from __future__ import annotations`. | **Al importar:** `TypeError: 'type' object is not subscriptable`. No se importan `pns_ai_mcp` ni `pns_ai_chatboo`; una base de datos con los módulos instalados no carga. | `Tuple[bool, Optional[str]]` (el archivo ya importa de `typing`) o añadir `from __future__ import annotations`. |
| 2 | `pns_ai_mcp/utils/relaxaicode_recipe.py:507` | `ast.get_source_segment` (Python 3.8). | **En ejecución:** desde `controllers/tools_relaxaicode.py:1867`, sin protección, la herramienta devuelve error cuando el código define a nivel de módulo una función con un parámetro cuyo nombre contiene `date`, `day`, `fecha`, `when` o `dia` (`_DATE_PARAM_HINTS`, `:206-209`): el caso típico de las consultas por rango de fechas. | `getattr(ast, 'get_source_segment', None)` y, si no existe, usar `src`, la alternativa que la función ya prevé (`or src`). |
| 3 | `pns_base/utils/pdf_io.py:94` | `ImageOps.exif_transpose` (Pillow ≥ 6.0). | **En ejecución, sin aviso:** `_open_picture` lanza `AttributeError`, que las funciones de imagen capturan devolviendo `None`. `/pns_ai_mcp/remote_image` responde 404 a todas las imágenes y Chatboo reenvía al proveedor las imágenes previas sin reescalar (`pns_ai_chatboo/models/chatboo_async_request.py:1079-1094`). | Usar `ImageOps.exif_transpose` si existe; si no, devolver la imagen sin girar o girarla leyendo la orientación EXIF (etiqueta 0x0112). |
| 4 | `pns_ai_mcp/controllers/main.py:1473` (`_mcp_prompts_list`) y `:1598` (`_mcp_prompts_get`) | `self._get_mcp_env().sudo()`: en Odoo 14 `Environment` no tiene `sudo()` (solo `__call__(…, su=…)`). No es un problema de Python, sino de la API de Odoo 14. | **En ejecución, sin aviso:** el `AttributeError` se captura. `prompts/list` devuelve solo `system_prompt` y `prompts/get` de cualquier contexto responde «Prompt not found»: los clientes MCP no reciben ningún contexto. En 3.1.486 no ocurría (esas rutas no llamaban a `.sudo()`). | `self._get_mcp_env()(su=True)`, que conserva el uid del usuario de la clave y mantiene el filtro por propietario de PNS-12. |

**Comprobación.** Con las cuatro correcciones mínimas aplicadas en el entorno de pruebas: la
actualización termina y el servidor arranca (1); `remote_image` devuelve la imagen re-codificada (3); y
`prompts/list` y `prompts/get` sirven los contextos compartidos y el privado del usuario, no los de otros
usuarios, sin `AttributeError` en el log (4). La corrección 2 está pendiente de comprobar con un turno
real (§8). Sin las correcciones, los fallos 1 y 4 se han observado tal como se describen.

**Versiones afectadas.** Con Python 3.7 fallan los cuatro. Con Python 3.8 y Pillow 8.1.1 siguen fallando
el 1 y el 4.

**Degradaciones menores en Python 3.7 (no bloquean, para su valoración):**

- `pns_ai_mcp/controllers/validators.py:434, 784, 1423` comprueban `ast.Constant` sin `ast.Str`/`ast.Num`,
  que es como Python 3.7 representa los literales: la reparación de `%` no se aplica y un `key=` literal
  en `sorted` se rechaza. Las comprobaciones de seguridad del validador sí contemplan 3.7.
- `pns_ai_mcp/utils/relaxaicode_recipe.py:32, 79, 97, 99` comprueban `ast.Constant`: en 3.7 un `None`
  literal (`ast.NameConstant`) hace que no se recupere el dato extraído.
- `pns_ai_mcp/controllers/validators.py:2330-2337` (`detect_dangerous_operations`) no coincide en 3.7 y,
  en `:2335`, lanzaría `AttributeError` en cualquier asignación que no sea una llamada. Hoy la función se
  importa (`main.py:91`) pero no se llama; conviene borrarla o corregirla.
- `ast.unparse` (`validators.py:330, 466, 619, 1812`; `relaxaicode_recipe.py:177, 351`) y `ET.indent`
  (`controllers/formatters.py:284`) están protegidos: en 3.7 no se aplican las reparaciones automáticas y
  el XML sale sin sangría.

**Petición.** Necesitamos una versión compatible con Odoo 14 sobre Python 3.7. Mientras tanto mantenemos
las cuatro correcciones mínimas en nuestra copia del código, lo que nos obliga a revisarlas en cada
versión. **¿Pueden indicarnos una fecha prevista para la versión que corrija PNS-81?** Sugerimos
además añadir a su integración continua una carga de los módulos con la imagen oficial de Odoo 14
(Python 3.7, Pillow 5.4.1), que habría detectado los cuatro fallos.

---

## 4. Pérdida de datos al actualizar (PNS-87, PNS-88) y nota sobre PNS-63

Ambos se han comprobado actualizando una base de datos desde 3.1.486 en el entorno de pruebas. En
PNS-87 se observó que el cron de purga se ejecuta en la primera pasada del programador y que la tabla
`ai_provider_usage_day` se borra; las tablas estaban vacías, así que el volumen de datos que se pierde no
se pudo medir y se deduce del código.

### 4.1 PNS-87 — Purga del registro de actividad y borrado del histórico diario de consumo

- **Purga de `ai.log`.** La actualización crea activo el cron diario de retención
  (`pns_ai_mcp/data/ai_log_cron.xml`, `noupdate="1"`). Si no existe el parámetro
  `pns_ai_mcp.log_retention_days`, aplica 30 días (`models/ai_log.py:17-18, 892-912`), y su primera
  ejecución borra en `sudo`, en una sola transacción, todas las filas más antiguas: la auditoría y el
  historial de consumo y coste que usa `get_user_usage_summary`. En el entorno de pruebas la purga no
  esperó un día: se ejecutó en la primera pasada del programador, unos minutos después de actualizar. El
  parámetro no está en Ajustes y no hay aviso ni nota de actualización.
- **Borrado de `ai_provider_usage_day`.** `ai.schema.fossil.init()` (`models/ai_schema_fossil.py:25-35`)
  ejecuta en cada actualización `DROP TABLE IF EXISTS … CASCADE` de las tablas de `FOSSIL_TABLES`
  (`utils/schema_fossils.py:15-28`), entre ellas `ai_provider_usage_day` (`:27`). No es una tabla de
  asistente: es el histórico diario de tokens, coste y número de peticiones por proveedor (modelo
  `ai.provider.usage.day` de 3.1.486). No hay migración que lo traslade, así que se pierde en la primera
  actualización. En la misma función se borran columnas que el ORM ya no usa (`LEFTOVER_COLUMNS`,
  `:44-53`).
- **Valoración.** El informe anterior pedía retención (PNS-30); el defecto no es la purga, sino el valor
  por defecto en una actualización, la falta de aviso y la pérdida del histórico.
- **Recomendación:** proponemos, en actualizaciones, no purgar hasta que el administrador fije la
  retención (o exponerla en Ajustes con un valor por defecto que no borre); trasladar
  `ai_provider_usage_day` al modelo que lo sustituya antes de borrarla, o no borrarla, y documentar ambos
  cambios en las notas de versión.

### 4.2 PNS-88 — Renombrados de XML ID que no se ejecutan en Odoo 14

- Los renombrados `mcp_*` → `ai_*` de reglas, accesos, menús, acciones y vistas de
  `ai.safe.operation`, `ai.log`, `ai.context` y `ai.change.journal` (38 XML ID) solo están en
  `pns_ai_mcp/migrations/3.1.518/pre-migrate.py` y `3.1.519/pre-migrate.py`. En Odoo 14 esos scripts no
  se ejecutan (§7.2 del informe anterior: formato de versión de las carpetas).
- Al actualizar, Odoo crea los registros `ai_*` como nuevos y borra los `mcp_*` al final. En el entorno
  de pruebas se borraron los 38 sin errores y se crearon 38 con ids nuevos: se pierden las
  personalizaciones hechas sobre los antiguos (dominios de regla, menús, vistas, traducciones) y las
  referencias a sus ids (favoritos o filtros guardados sobre esas acciones).
- Quedan además en las bases de datos existentes los 5 servidores de fábrica que ya no están en los datos
  (`noupdate="1"`, inactivos): `external_server_mcp_test`, `external_server_brave_search` y
  `external_server_sequential_thinking` (`stdio` con `npx`), y `external_server_sesame` y
  `external_server_cdmon` (OpenAPI).
- **Recomendación:** proponemos hacer los renombrados en código que también se ejecute en Odoo 14 (por
  ejemplo, en `init()`) o corregir el formato de versión de las carpetas de `migrations/`, y retirar o
  documentar los servidores heredados.

### 4.3 Nota sobre PNS-63 (retención de sesiones de Chatboo)

La purga global de sesiones es la corrección que pedimos y está bien resuelta
(`pns_ai_chatboo/models/chatboo_session.py:1360-1381`, llamada desde el cron de mantenimiento cada
5 minutos, `models/chatboo_async_request.py:2167`). Pero, igual que en PNS-87, en la primera pasada del
cron tras actualizar borra todas las sesiones (y sus adjuntos) de más de 30 días, también las de
usuarios que no vuelven al chat. El parámetro `pns_ai_chatboo.history_retention_days` se crea con un
registro de datos `noupdate="1"` que no existía en `pns_ai_chatboo` 2.1.322
(`data/chatboo_icp_data.xml:8-11`). Según el
código (no lo hemos probado), si un administrador crea el parámetro a mano antes de actualizar, la carga
de ese registro chocaría con la restricción `key_uniq` de `ir.config_parameter`.

**Recomendación:** proponemos avisarlo en las notas de versión y crear el parámetro solo si no existe
(por código, en lugar de con un registro de datos), para que el administrador pueda fijar la retención
antes de actualizar.

---

## 5. Estado de PNS-01 a PNS-92

Estados: **Corregido** (el cambio cubre el hallazgo y sus puntos de entrada) · **Parcial** (cubre una
parte; queda un resto concreto) · **Sin cambios** · **Ya no aplica** (el código desapareció) ·
**Dudoso** (no se puede decidir sin una prueba adicional) · **Nuevo** (hallazgo que no estaba en el
informe anterior). Donde se indica «comprobado en entorno de pruebas», el resultado se ha verificado en
ejecución; en los demás, procede de la revisión del código.

| PNS | Gravedad | Estado | Situación |
|---|---|---|---|
| PNS-01 | Crítica | Parcial | Vía RPC cerrada: métodos privados (comprobado en entorno de pruebas). Queda que `user.add_group` solo exige AI Administrator (§2.7). |
| PNS-02 | Crítica | Parcial | Todos los `apply_*`/`preview_*` privados (comprobado en entorno de pruebas). Queda `user.remove_group` con solo AI Administrator (§2.7). |
| PNS-03 | Crítica | Corregido | `write` fuera de `sudo` rechazado; sin creación directa por RPC. Comprobado en entorno de pruebas. |
| PNS-04 | Crítica | Corregido | `confirmed_uid` ignorado; `_can_resolve()` en todas las transiciones. La variante privada que recibe uid es resto de PNS-07. |
| PNS-05 | Crítica | Corregido | `safe_plan_status` filtra siempre por usuario y ejecuta sin `sudo`. Pendiente de comprobar con un turno real (§8). |
| PNS-06 | Crítica | Corregido | Ejecución de prueba en savepoint revertido y rechazo del código de escritura (comprobado en entorno de pruebas el rechazo al guardar). Comparte el resto del sandbox de PNS-07. |
| PNS-07 | Crítica | Parcial | Lista de 15 métodos y bloqueo del cursor; quedan alcanzables los métodos privados con cursor propio (§2.8). |
| PNS-08 | Alta | Corregido | Campos secretos solo para AI Administrator y vaciados en la exportación. Comprobado en entorno de pruebas. |
| PNS-09 | Alta | Corregido | `stdio` solo para administrador de Ajustes; entorno mínimo y timeout; acciones con `ensure_ai_admin` (comprobado en entorno de pruebas `action_test_connection`). |
| PNS-10 | Alta | Corregido | La bandera solo vale en `sudo` o para el superusuario. Comprobado en entorno de pruebas. |
| PNS-11 | Alta | Corregido | `_require_bootstrap()` en los cinco métodos; `record_context_usage` privado. Comprobado en entorno de pruebas. |
| PNS-12 | Alta | Corregido | Filtro por propietario en el modelo (comprobado en entorno de pruebas). Por MCP solo se pudo comprobar con la corrección 4 de §3 aplicada. |
| PNS-13 | Alta | Corregido | Clave y usuario revalidados en cada mensaje; sesiones con caducidad. Comprobado en entorno de pruebas. |
| PNS-14 | Alta | Parcial | Reglas nuevas en `ai.api.result.cache` y `ai.safe.choice` (comprobado en entorno de pruebas). Queda `ai.fetch.cache` por métodos públicos (PNS-90). |
| PNS-15 | Alta | Corregido | Saneado o escape en todas las vías citadas. |
| PNS-16 | Alta | Parcial | Turno no confiable sin auto-confirmación. Quedan la reinyección con rol `system` en el turno siguiente y el alta de dominio con política `open`. Prueba no concluyente; pendiente (§8). |
| PNS-17 | Alta | Parcial | `fetch_url` protegido salto a salto y con tope. Quedan el generador OpenAPI (PNS-86) y las redirecciones del driver OpenAPI con cabeceras de autenticación y sin tope (`lib/api/drivers/openapi_driver.py:74-81, 387-394`). |
| PNS-18 | Alta | Parcial | Nuevo `no_external_failover` (comprobado en entorno de pruebas). Sin exclusión de modelos o campos ni anonimización. |
| PNS-19 | Alta | Parcial | `sudo` y el cursor bloqueados en el sandbox. Queda `ai.provider._api_key_for_inference()` alcanzable (§2.8). |
| PNS-20 | Alta | Parcial | Exportación sin secretos por defecto y purga de 24 h. Queda la importación que sobrescribe sin resumen previo; ver también §7.5. |
| PNS-21 | Alta | Corregido | `auth='user'` y URL sin token. Comprobado en entorno de pruebas. Ver PNS-82. |
| PNS-22 | Media | Parcial | Puerta `group_ai_writer` en el `DummyController`. `tools/call` sigue decidiendo por una lista de dos nombres no registrados y `is_write` no tiene efecto (`controllers/main.py:1295-1311, 1380-1383`). Pendiente (§8). |
| PNS-23 | Alta | Sin cambios | Las skills capturadas desde Chatboo y las importadas por ZIP quedan activas (§7.1). |
| PNS-24 | Alta | Parcial | Ejecución con el usuario real y veto de cascadas. `button_immediate_*` sigue haciendo commit dentro de un plan con otros pasos. |
| PNS-25 | Alta | Corregido | Sin failover tras ejecutar efectos; ejecución idempotente. |
| PNS-26 | Alta | Parcial | `rollback` en `/mcp` si falla la herramienta. Siguen los commits en `safe_operation.py` y no consta un rollback equivalente en el motor de Chatboo. |
| PNS-27 | Alta | Corregido | Fuera SheetJS y las copias duplicadas; jsPDF 4.2.1. Ver §7.4. |
| PNS-28 | Media | Parcial | Sin filas de `ai.log` para peticiones sin usuario (comprobado en entorno de pruebas). Siguen `cors='*'` y sin validación de `Origin`. |
| PNS-29 | Media | Parcial | El uso de las llamadas cortas se registra (comprobado en entorno de pruebas en parte). Sin topes de gasto; ver §7.8. |
| PNS-30 | Media | Parcial | `ondelete='set null'`, ACL sin escritura y retención. Queda `create_log_entry` público (§2.1); filas creables a nombre de otro, comprobado en entorno de pruebas. Ver PNS-87. |
| PNS-31 | Media | Sin cambios | Sigue el backport global de `_process_ondelete`; `set_values` reescribe la política de URL; más `include` globales del cliente web. Ver §7.9. |
| PNS-32 | Media | Parcial | Sin borrados en disco. La sincronización sigue sobrescribiendo contextos de fábrica editados y sin bloqueo entre workers. |
| PNS-33 | Media | Sin cambios | Ver §7.7. |
| PNS-34 | Media | Corregido | Clave aleatoria por clase y restaurada al desmontar. |
| PNS-35 | Media | Sin cambios | Las dos vías openpyxl escriben como fórmula las celdas que empiezan por `=`. |
| PNS-36 | Media | Parcial | Fuera `resources/*` y `system://info`. El sandbox sigue ofreciendo el nombre de la base de datos y `fields_get` sin permiso de lectura. Pendiente (§8). |
| PNS-37 | Media | Sin cambios | `intended_values` sin redactar y reversión parcial; además, `record_failed_plan` público (§2.1). |
| PNS-38 | Media | Sin cambios | El prompt de sistema sigue induciendo acciones de sistema y cita campos inexistentes en Odoo 14. |
| PNS-39 | Media | Parcial | 202 en `/mcp/message` y negociación de versión. Quedan 204 en notificaciones, 200 en errores de autenticación e `isError` siempre `False`. |
| PNS-40 | Media | Parcial | `temperature` omitible. Quedan `0` → `0,7`, `max_completion_tokens` y el endpoint en el mensaje de error (este último, comprobado en entorno de pruebas; los otros dos, en código). |
| PNS-41 | Media | Corregido | Sin reescritura de `website`; `iframe` con `sandbox` sin scripts. |
| PNS-42 | Media | Sin cambios | `_notifyInvalidFields` y el CSS de obligatorios siguen siendo globales. |
| PNS-43 | Baja | Parcial | Aviso en el asistente de idioma; el descarte sigue aplicándose a cualquier módulo y por otras vías solo deja un WARNING. |
| PNS-44 | Baja | Ya no aplica | Sin escrituras en `ir.module.module` durante la carga. |
| PNS-45 | Baja | Corregido | Cada fallo de carga de herramienta se registra con traza. |
| PNS-46 | Baja | Dudoso | Prueba no concluyente: el glosario no aparece en la parte fija del prompt para ningún idioma. Pendiente (§8). |
| PNS-47 | Baja | Corregido | El fallo de las fuentes de divisas se recuerda 15 minutos. |
| PNS-48 | Baja | Corregido | Menú Settings con `base.group_system`; sin acciones duplicadas. |
| PNS-49 | Baja | Parcial | Siguen `moe_controller.py`, `cleanup_stuck_state`, `web_read`, `search_fetch`, dos `include` sin efecto y el driver `ollama` no seleccionable. |
| PNS-50 | Baja | Parcial | Tests negativos nuevos. `test_change_journal.py` sigue sin importarse, y `test_presentation_mode` y `test_session_download` se descartan en Odoo 14 (sin etiqueta `standard`). |
| PNS-51 | Baja | Sin cambios | `platform` sigue permitido en el sandbox (§7.2). |
| PNS-52 | Baja | Corregido | Defaults con recordset vacío y selecciones validadas. |
| PNS-53 | Crítica | Corregido | Reglas por `user_id` y HTML saneado en el historial y el streaming. Comprobado en entorno de pruebas. |
| PNS-54 | Crítica | Parcial | La tarjeta solo actúa para el dueño. Siguen sin token ligado a la interacción `/verification/confirm` y `/verification/execute`, y `resolve_confirm_and_execute` y `confirm_by_user` son públicos para el dueño. |
| PNS-55 | Alta | Parcial | Aislamiento de sesiones y trabajos (comprobado en entorno de pruebas). Quedan el ACL de trabajos con `write`/`create`, `claim_turn_file_chips` (PNS-82) y `recover_orphan_download_chips`. |
| PNS-56 | Alta | Corregido | La vía entre usuarios depende de PNS-55, ya cerrada. Comprobado en entorno de pruebas. |
| PNS-57 | Alta | Corregido | `_spawn` privado; trabajos solo sobre sesión propia. Comprobado en entorno de pruebas. |
| PNS-58 | Alta | Corregido | `/chatboo/stream` con CSRF y sin `cors`. Comprobado en entorno de pruebas. |
| PNS-59 | Alta | Parcial | Las imágenes externas pasan por `remote_image` (comprobado en entorno de pruebas el 404 para un host no permitido). Con política `open` o lista blanca ampliable (PNS-91) el servidor sigue descargando. Pendiente (§8). |
| PNS-60 | Alta | Parcial | Saneador en todos los puntos de inserción (comprobado en entorno de pruebas para el mensaje del usuario). Quedan `escapeHtml` sin comillas, lista negra de etiquetas y showdown. Respuesta y exportación, pendientes (§8). |
| PNS-61 | Media | Parcial | Agente fijado por el servidor; `provider_id` fuera de la cadena ignorado (comprobado en entorno de pruebas). El historial sigue llegando del navegador (§7.3). |
| PNS-62 | Media | Parcial | Tope por archivo (comprobado en entorno de pruebas). Sin tope de número de archivos ni del cuerpo total. |
| PNS-63 | Media | Corregido | Purga global por cron. Ver la nota de actualización en §4.3. |
| PNS-64 | Media | Parcial | Se prefiere voz local; sin ella usa la remota y no hay ajuste para desactivarla. |
| PNS-65 | Media | Parcial | HTML saneado y servido con `nosniff`. Quedan `src` sin escapar en Word, todas las claves del dataset, `mimetype` del cliente y subidas automáticas. |
| PNS-66 | Media | Sin cambios | Skills de fábrica sin control de grupo (`users-all`, `users-logged`, `sys-info`, `forecast`). Comprobado en entorno de pruebas con `users-all`. |
| PNS-67 | Media | Corregido | `financial-health` y `customer-risk-analysis` corregidas; `analisis-financiero` retirada. |
| PNS-68 | Media | Sin cambios | Las migraciones `2.1.296` y `2.1.300` siguen borrando sin filtrar el dueño (en Odoo 14 no se ejecutan). |
| PNS-69 | Baja | Corregido | Listas de clase ampliadas en `__init__`. |
| PNS-70 | Media | Sin cambios | Sigue usando la global `window.Chart` con Chart.js 4.4.8 en todo el backend. |
| PNS-71 | Baja | Corregido | `check_health` con clave y sin datos de infraestructura; estados HTTP correctos. Comprobado en entorno de pruebas. |
| PNS-72 | Baja | Parcial | Fuera SheetJS y duplicados; siguen seis librerías en `web.assets_backend`. |
| PNS-73 | Baja | Sin cambios | Campo `static` de clase y capa con `z-index: 1050`. |
| PNS-74 | Baja | Parcial | `noopener` añadido; sigue el código muerto citado. |
| PNS-75 | Baja | Corregido | Celdas con `=`, `+`, `-`, `@` prefijadas como texto. |
| PNS-76 | Baja | Parcial | Caché de menús vaciada al generar la clave; la receta del agente sigue difiriendo entre bases actualizadas y nuevas. |
| PNS-77 | Baja | Sin cambios | `pns_ai_chatboo` sigue sin tests. |
| PNS-78 | Baja | Corregido | Etiquetas distintas. |
| PNS-79 | Baja | Corregido | Sin valor por defecto `SUPERUSER_ID`; usuario de la clave revalidada. Prueba no concluyente. |
| PNS-80 | Alta | Ya no aplica | `read_progress` desaparece y el sondeo filtra por usuario. Comprobado en entorno de pruebas. |
| PNS-81 | Alta | Nuevo | Incompatibilidades con Odoo 14 (§3). Comprobado en entorno de pruebas (salvo la corrección 2). |
| PNS-82 | Alta | Nuevo | Apropiación de adjuntos ajenos en Chatboo. Comprobado en entorno de pruebas. |
| PNS-83 | Alta | Nuevo | Entrega de claves MCP por PIN sin grupo ni límite de intentos. Comprobado en entorno de pruebas (acceso por RPC y contador; la entrega de la clave, en código). |
| PNS-84 | Media | Nuevo | PIN y clave MCP en claro en la base de datos y en el navegador. |
| PNS-85 | Media | Nuevo | Caché de parámetros de skills escribible por cualquier usuario. Comprobado en entorno de pruebas (`remember_for_skill`). |
| PNS-86 | Media | Nuevo | Generador OpenAPI sin control de hosts no públicos, redirecciones ni tamaño. |
| PNS-87 | Baja | Nuevo | Pérdida de datos de consumo al actualizar. Comprobado en entorno de pruebas que el cron de purga se ejecuta en la primera pasada y que la tabla del histórico diario se borra; el volumen borrado no se pudo medir (tablas vacías). |
| PNS-88 | Baja | Nuevo | Renombrados de XML ID `mcp_*` que no se ejecutan en Odoo 14: los 38 se borran y se recrean con ids nuevos. Quedan además servidores de fábrica heredados. Comprobado en entorno de pruebas. |
| PNS-89 | Baja | Nuevo | `/pns_ai_mcp/key_pin/stop` sin CSRF. |
| PNS-90 | Alta | Nuevo | Caché de `fetch_url` legible y sobrescribible por cualquier usuario. Comprobado en entorno de pruebas. |
| PNS-91 | Media | Nuevo | Lista blanca de URL ampliable por cualquier usuario. Comprobado en entorno de pruebas. |
| PNS-92 | Media | Nuevo | Clave MCP escrita en `sudo` sin control previo; protegido solo por un efecto lateral (comprobado en entorno de pruebas). |

---

## 6. Hallazgos nuevos (PNS-81 a PNS-92)

PNS-81 a PNS-89 están en código nuevo o modificado en esta versión. PNS-90 a PNS-92 están en código que
ya existía en 3.1.486 y que el informe anterior no citaba. Mismo criterio de gravedad que el informe
anterior.

### PNS-81 — Incompatibilidades con Odoo 14: el módulo no se importa y tres funciones fallan en ejecución

- **Gravedad:** Alta · **Estado:** Comprobado en entorno de pruebas (la corrección 2, pendiente) ·
  **Módulos:** pns_ai_mcp, pns_base
- **Ubicación y detalle:** §3.
- **Impacto:** en un servidor Odoo 14 con Python 3.7 (imagen oficial) o 3.8, sustituir el código deja la
  base de datos sin cargar, porque `pns_ai_mcp` está instalado y no se importa. Corregida la importación,
  fallan tres funciones en ejecución (dos sin aviso): consultas con parámetros de fecha, imágenes remotas
  y reescalado, y `prompts/*` por MCP.
- **Recomendación:** las cuatro correcciones mínimas de §3. Sugerimos además una carga de prueba con la
  imagen oficial de Odoo 14 en la integración continua.

### PNS-82 — `chatboo.session.claim_turn_file_chips` se apropia de adjuntos ajenos sin `res_model` o sin `res_id`

- **Gravedad:** Alta · **Estado:** Comprobado en entorno de pruebas · **Módulos:** pns_ai_chatboo,
  pns_ai_mcp (relacionado con PNS-21 y PNS-55)
- **Ubicación:** `pns_ai_chatboo/models/chatboo_session.py:415-441`; también desde el método público
  `apply_assistant_download_chips` (`:401-413`).
- **Comportamiento:**
  - El método es público. Sobre una sesión propia (la regla por `user_id` lo exige), toma ids de adjunto
    de la lista recibida o de la URL del chip.
  - Con `ir.attachment` en `sudo`, reasigna a esa sesión cualquier adjunto al que le falte `res_model` o
    `res_id`: solo se salta los que tienen los dos (`:436-437`). Entran también los adjuntos con
    `res_model` y `res_id=0`, combinación que admite `write_export_attachment`
    (`pns_base/utils/portable_io.py:342-361`). No comprueba quién lo creó ni que lo haya generado el
    motor.
  - Después, `_may_read` de `/pns_ai_mcp/session_file` lo entrega, porque el adjunto ya cuelga de una
    sesión que el llamador puede leer (`pns_ai_mcp/controllers/session_file.py:20-32`); por la misma razón
    lo sirve `/web/content`.
  - Al borrar su sesión, el usuario borra en `sudo` todos los adjuntos que cuelgan de ella
    (`chatboo_session.py:1326-1333`), también los reclamados.
- **Adjuntos expuestos:** las descargas del chat de otros usuarios y las copias de configuración de
  `pns_ai_mcp`, que se guardan sin `res_model` y, si se exportan con secretos, llevan claves y tokens
  durante su ventana de 24 h: Ajustes (`pns_ai_mcp/models/res_config_settings.py:212`), proveedores
  (`models/ai_provider.py:1135`), usuarios MCP (`models/mcp_user.py:720`) y servidores externos
  (`models/external_server.py:1423`). Los ids son secuenciales.
- **Impacto:** cualquier usuario interno (el ACL de `chatboo.session` es `base.group_user`) puede leer o
  borrar adjuntos de otros usuarios sin `res_model` o sin `res_id`, incluidas copias de configuración con
  secretos.
- **Recomendación:** proponemos reclamar solo adjuntos creados por el propio usuario y marcados por el
  motor como descarga de ese turno, no reasignar nunca un adjunto con `res_model` y añadir un test
  negativo con dos usuarios.

### PNS-83 — `ai.mcp.user.redeem_key_pin` entrega claves MCP por RPC sin grupo y sin límite efectivo de intentos

- **Gravedad:** Alta · **Estado:** Comprobado en entorno de pruebas (acceso por RPC de un interno y de un
  portal a `redeem_key_pin` y `release_all`; contador sin `ip`); la entrega de la clave, verificada en
  código · **Módulo:** pns_ai_mcp (relacionado con PNS-07, PNS-33 y PNS-84)
- **Ubicación:** `pns_ai_mcp/models/mcp_user.py:819-860`; `models/key_pin_block.py:36-73`;
  `models/key_pin_desk.py:171-192`; `static/src/js/key_pin_desk_v14.js:93-118`; `utils/key_pin.py:13`.
- **Comportamiento:**
  - `redeem_key_pin(raw, ip=None)` es `@api.model`, público y sin comprobación de grupo. No tiene llamador
    en los tres módulos. Busca el PIN en `sudo` y, si hay una mesa de entrega abierta, devuelve la clave
    MCP en claro del usuario dueño del PIN. La pestaña del administrador responde sola, sin intervención.
  - El contador de fallos depende del argumento `ip`, que por RPC elige quien llama; si va vacío, no se
    cuenta ni se bloquea (`key_pin_block.py:38-40, 48-50`), aunque la respuesta indique
    `counted: true`.
  - `ai.key.pin.block.release_all()` (`:68-73`), `note_failure(ip)` e `is_blocked(ip)` (`:36-66`) también
    son públicos y trabajan en `sudo`: cualquier usuario autenticado puede levantar todos los bloqueos,
    bloquear durante una hora la IP que quiera (`DEFAULT_PIN_BLOCK_HOURS = 1`), impidiendo el canje
    legítimo desde ella, o consultar si una IP está bloqueada.
  - El canje no marca el PIN como usado: sigue válido hasta que se llama a `consume_key_pin` o el
    administrador lo borra.
  - Cada canje con PIN correcto ocupa un worker hasta 20 s (`key_pin_desk.py:185-192`).
- **Impacto:** un usuario autenticado cualquiera, también de portal, puede probar PIN sin límite real. Con
  un PIN vigente (8 dígitos por defecto; configurable hasta 4) y una mesa abierta, obtiene la clave MCP
  de ese usuario, que puede ser un AI Administrator, y actúa por `/mcp` en su nombre. Es el patrón de
  PNS-01 aplicado a credenciales.
- **Recomendación:** §2.2.

### PNS-84 — PIN y clave MCP en claro en la base de datos y en el navegador

- **Gravedad:** Media · **Estado:** Verificado en código · **Módulo:** pns_ai_mcp (relacionado con PNS-33
  y PNS-83)
- **Ubicación:** `pns_ai_mcp/models/mcp_user.py:142`; `models/key_pin_desk.py:154-239`;
  `static/src/js/key_pin_desk_v14.js:38-48`.
- **Comportamiento:**
  - `ai.mcp.user.key_pin` guarda el PIN en claro (`Char`, indexado): lo ven todos los AI Administrator y
    queda en copias de seguridad y réplicas.
  - `ai.key.pin.ask.supplied_key` guarda la clave MCP en claro hasta que la recoge quien espera
    (`:209-212`). Si la respuesta llega después de los 20 s, nadie la recoge, y la fila solo se borra en
    el siguiente canje (`_drop_old`, `:164-169`, llamado solo desde `collect`): la clave puede quedarse en
    la tabla indefinidamente.
  - Cualquier AI Administrator puede leer `ai.key.pin.ask` (ACL `1,1,1,1`) y ver claves de otros usuarios
    mientras están en la tabla.
  - La pestaña de la mesa guarda en `sessionStorage` la lista completa de claves en claro. Cualquier XSS
    en el backend mientras está abierta las leería todas (relación con PNS-54 y PNS-60).
- **Impacto:** credenciales de acceso MCP en claro, fuera del hash que pedía PNS-33 y sin caducidad
  garantizada.
- **Recomendación:** proponemos guardar el PIN como hash; borrar `supplied_key` al vencer la espera (por
  ejemplo, en un cron) y restringir la lectura de `ai.key.pin.ask`, y no conservar la lista de claves en
  el navegador más allá de lo imprescindible.

### PNS-85 — Caché de parámetros de skills escribible por cualquier usuario autenticado

- **Gravedad:** Media · **Estado:** Comprobado en entorno de pruebas (`remember_for_skill`); el resto,
  verificado en código · **Módulo:** pns_ai_mcp (relacionado con PNS-07)
- **Ubicación:** `pns_ai_mcp/models/ai_skill_param_cache.py:125-154` (`remember_for_skill`) y `:91-107`
  (`lookup_for_skill`); `models/ai_skill.py:329-345`; `utils/agent_engine.py:785`.
- **Comportamiento:**
  - `remember_for_skill(skill_id, leftover, norm)` es `@api.model` público. Crea la fila con un cursor
    propio como `SUPERUSER_ID` y hace commit (`:143-148`). Acepta cualquier `skill_id`, también de skills
    que el llamador no puede leer, y no sobrescribe una fila existente: gana el primero que escribe.
  - Segundo punto de entrada público: `ai.skill.remember_param_cache(leftover, norm)`
    (`ai_skill.py:338-345`), que solo usa `self.id`.
  - La caché es global, sin usuario: `lookup_for_skill` busca en `sudo` por skill y frase normalizada, y
    el motor la aplica en los turnos de todos los usuarios. `lookup_for_skill` y
    `ai.skill.lookup_param_cache` (`ai_skill.py:329-336`) también son públicos.
  - El ACL no interviene. Por el commit propio, si el sandbox llega al modelo, la escritura sobrevive al
    rollback de la caja A: la lista de PNS-07 (`controllers/validators.py:178-194`) no incluye estos
    métodos.
- **Impacto:** un usuario sin permisos de escritura puede fijar de antemano los parámetros (fechas,
  filtros, empresa) con que se ejecutará una skill para una frase concreta cuando la use otro usuario, y
  leer los parámetros cacheados de cualquier skill. Los resultados salen alterados sin aviso. Es
  integridad, no escalada.
- **Recomendación:** §2.5.

### PNS-86 — Generador OpenAPI: descarga sin control de hosts no públicos, redirecciones ni tamaño

- **Gravedad:** Media · **Estado:** Verificado en código · **Módulo:** pns_ai_mcp (relacionado con
  PNS-17)
- **Ubicación:** `pns_ai_mcp/services/openapi_spec_generator.py:579-610` (`fetch_documentation`);
  `wizard/openapi_spec_generate_wizard.py:197-214`.
- **Comportamiento:**
  - Solo comprueba que el host inicial esté en la lista blanca `web`. Después hace `requests.get`, que
    sigue redirecciones a cualquier host, sin `non_public_host_error`.
  - Lee el cuerpo entero en memoria antes de truncarlo a `_MAX_DOC_CHARS` (`:19`, 120 000 caracteres).
  - El texto se guarda en `docs_text` del asistente, que ve el administrador, y se envía al proveedor LLM.
  - La lista blanca no rechaza IP ni nombres internos (`models/url_whitelist.py`, sin restricción), así
    que basta con añadir un host interno; además, cualquier usuario autenticado puede ampliarla (PNS-91).
- **Impacto:** un AI Administrator sin permisos de Ajustes puede leer servicios internos de la red del
  servidor y enviarlos al proveedor LLM. Gravedad Media y no Alta como PNS-17 porque el generador solo lo
  usa el AI Administrator.
- **Recomendación:** reutilizar el bucle salto a salto con `non_public_host_error` y la lectura con tope
  de `utils/fetch_url_safe.py`, como ya hace `fetch_url` (`controllers/safe_plan.py:1528-1585`).

### PNS-87 — Pérdida de datos de consumo al actualizar: purga de `ai.log` a 30 días y borrado de `ai_provider_usage_day`

- **Gravedad:** Baja · **Estado:** Comprobado en entorno de pruebas · **Módulo:** pns_ai_mcp
  (relacionado con PNS-30)
- **Ubicación:** `pns_ai_mcp/data/ai_log_cron.xml`; `models/ai_log.py:17-18, 892-912`;
  `utils/schema_fossils.py:15-28, 44-53`; `models/ai_schema_fossil.py:25-35`.
- **Detalle y recomendación:** §4.1. Columnas que también se borran: `ai_log.operation_code`,
  `ai_provider.cost_policy`, `ai_provider.is_on_premise`, `ai_context.is_shared`, `ai_skill.is_shared`,
  `ai_agent.auto_link_mcp_nucleus`, `ai_agent.link_show_native` y `ai_agent.link_show_pinned`.
- **Impacto:** pérdida de datos no avisada en instalaciones que usan el registro como auditoría o para
  repartir costes, y pérdida del histórico de consumo por proveedor. En bases con mucho volumen, el
  primer borrado puede ser largo.

### PNS-88 — Renombrados de XML ID `mcp_*` que no se ejecutan en Odoo 14 y servidores de fábrica heredados

- **Gravedad:** Baja · **Estado:** Comprobado en entorno de pruebas · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/migrations/3.1.518/pre-migrate.py` y `3.1.519/pre-migrate.py`;
  `data/external_server_data.xml` y `data/external_server_openapi_data.xml` de la versión anterior.
- **Detalle y recomendación:** §4.2.
- **Impacto:** bajo. En Odoo 14 los renombrados de `migrations/` no se ejecutan: al actualizar, los 38
  registros se borran y se recrean con ids nuevos, y se pierden las personalizaciones y las referencias
  a los antiguos. Los servidores de fábrica que ya no están en los datos quedan en la base de datos.

### PNS-89 — `/pns_ai_mcp/key_pin/stop` sin CSRF

- **Gravedad:** Baja · **Estado:** Verificado en código · **Módulo:** pns_ai_mcp (relacionado con PNS-83)
- **Ubicación:** `pns_ai_mcp/controllers/key_pin.py:35-54` (`type='http'`, `POST`, `csrf=False`).
- **Comportamiento:** el único efecto es cerrar la mesa cuyo token se envíe y avisar por el bus. El token
  se genera en el navegador con `Date.now()` y `Math.random()`, no con un generador criptográfico, y vive
  en el `sessionStorage` de la pestaña (`static/src/js/key_pin_desk_v14.js:20-30`); sin conocerlo no hay
  efecto.
- **Impacto:** mínimo hoy; es una excepción de CSRF innecesaria en una función sensible.
- **Recomendación:** si la ruta se usa con `sendBeacon` al cerrar la pestaña, proponemos enviar el
  `csrf_token` en el cuerpo y quitar `csrf=False`, y generar el token con `crypto.getRandomValues`.

### PNS-90 — Caché de `fetch_url` legible y sobrescribible por cualquier usuario autenticado

- **Gravedad:** Alta · **Estado:** Comprobado en entorno de pruebas · **Módulo:** pns_ai_mcp (resto de
  PNS-14; relacionado con PNS-16 y PNS-17)
- **Ubicación:** `pns_ai_mcp/models/fetch_cache.py:63-89` (`get_cached`) y `:91-123` (`store`);
  `controllers/safe_plan.py:1493-1503` (clave de caché), `:1619` (lectura) y `:1667, 1723` (escritura).
- **Comportamiento:**
  - `get_cached(url)` y `store(url, result, ttl_seconds)` son `@api.model` públicos. Buscan, crean y
    sobrescriben filas en `sudo`, sin comprobar grupo.
  - La caché es global: la clave es la URL (más el hash del cuerpo en `QUERY`), sin usuario.
  - `fetch_url` consulta esa caché antes de salir a la red; si hay una fila vigente, devuelve su cuerpo
    como resultado de la herramienta.
  - `store` acepta el contenido, el código de estado y el TTL que elija quien llama.
  - El ACL de `ai.fetch.cache` (solo AI Administrator desde esta versión) no interviene.
- **Impacto:** cualquier usuario autenticado, también de portal, puede leer el cuerpo cacheado de las
  URL que consultaron otros usuarios y fijar de antemano el contenido que recibirá la herramienta
  `fetch_url` de otro usuario para una URL, sin que la petición salga a la red. Ese contenido llega al
  modelo como resultado de la herramienta: prompt injection entre usuarios (PNS-16).
- **Recomendación:** §2.3.

### PNS-91 — `ai.url.whitelist.ensure_domain_whitelisted` amplía la lista blanca sin control de grupo

- **Gravedad:** Media · **Estado:** Comprobado en entorno de pruebas (tipo `web`) · **Módulo:**
  pns_ai_mcp (relacionado con PNS-16, PNS-59 y PNS-86)
- **Ubicación:** `pns_ai_mcp/models/url_whitelist.py:235-266`; tipos admitidos en `:54-56`.
- **Comportamiento:** `ensure_domain_whitelisted(hostname, notes, kind)` es `@api.model` público. Crea la
  fila con `sudo().create` o reactiva una archivada con `sudo().write`, sin comprobar grupo. Admite los
  tipos `web`, `mcp` y `openapi`. El ACL de internos es de solo lectura
  (`security/ir.model.access.csv:6`) y el `create` directo se rechaza, pero el método no pasa por él.
- **Impacto:** cualquier usuario autenticado, también de portal, puede añadir o reactivar hosts en la
  lista blanca. Con la política de URL restringida, eso abre la salida del servidor hacia esos hosts
  (`remote_image`, `fetch_url`).
- **Recomendación:** §2.6.

### PNS-92 — `set_mcp_api_key` y `action_generate_mcp_api_key` escriben la clave en `sudo` sin control previo

- **Gravedad:** Media (defensa en profundidad) · **Estado:** Comprobado en entorno de pruebas (hoy sin
  efecto) · **Módulo:** pns_ai_mcp (relacionado con PNS-33 y PNS-83)
- **Ubicación:** `pns_ai_mcp/models/mcp_user.py:450-466` (`set_mcp_api_key`), `:440-448`
  (`action_generate_mcp_api_key`) → `:419-437` (`_do_generate_mcp_api_key`) → `:406-417`
  (`_store_api_key_hash`).
- **Comportamiento:**
  - Los dos métodos son públicos y no comprueban grupo ni propiedad. Escriben el hash de la clave MCP con
    `sudo()` (`:460-464` y `:410-414`).
  - Hoy no tienen efecto para un usuario sin permisos por una razón indirecta: después de escribir, la
    línea de log (`:465` y `:437`) lee `self.user_id` en el entorno del usuario que llama. Sin lectura
    sobre `ai.mcp.user` (solo AI Administrator, `security/ir.model.access.csv:39`), esa lectura lanza
    `AccessError` y deshace toda la transacción, incluida la escritura ya hecha. En las comprobaciones
    con un usuario interno y uno de portal, el hash no cambió y el error salía de esa línea de log, no
    de un control previo.
  - El único llamador legítimo es el asistente `ai.api.key.wizard` (`models/mcp_api_key_wizard.py:104,
    113`), con ACL solo de AI Administrator.
- **Impacto:** hoy ninguno comprobado. Cualquier cambio que dé lectura sobre `ai.mcp.user` a usuarios no
  administradores, o que mueva o quite esa línea de log, dejaría a cualquier usuario autenticado fijar o
  regenerar la clave MCP de otro, incluido un administrador. Sería Crítica.
- **Recomendación:** comprobar `group_ai_admin` (o la propiedad, si se quiere autoservicio) antes de
  escribir, o hacer privados los métodos y llamarlos solo desde el asistente.

---

## 7. Peticiones menores y observaciones

Ninguna es urgente; las recogemos para que puedan incluirse en una próxima versión.

### 7.1 Skills activadas sin revisión (PNS-23)

La ejecución al guardar ya es de solo lectura (PNS-06). Queda que la captura desde Chatboo crea la skill
activa (`'active': bool(self.from_chatboo)`, `pns_ai_mcp/wizard/skill_capture_wizard.py:834`), con
`from_chatboo` tomado del contexto (`:196-197`), aunque el docstring de cabecera dice «DRAFT
(active=False)». La importación ZIP y desde ficheros mantiene `active` del fichero, `True` por defecto
(`pns_ai_mcp/models/ai_skill.py:1782, 1998-2013`). **Petición:** que ambas vías dejen la skill inactiva
hasta que la revise un administrador.

### 7.2 Módulo `platform` en el sandbox (PNS-51)

`platform` sigue en la lista de módulos permitidos (`pns_ai_mcp/controllers/validators.py:94`) y permite
leer datos del sistema operativo del servidor. **Petición:** quitarlo. El anuncio de `zoneinfo` en el
prompt que citaba el informe anterior ya está corregido.

### 7.3 Historial de la conversación enviado por el navegador (PNS-61)

El agente y el proveedor ya los fija el servidor. El `history` del cuerpo de `/chatboo/stream` sigue
llegando del navegador (`pns_ai_chatboo/controllers/chatboo.py:738`), se guarda en el trabajo
(`models/chatboo_async_request.py:242`) y es el historial que recibe el motor (`:418, 605`): el usuario
puede fabricar turnos previos o resultados de herramientas. **Petición:** que el servidor reconstruya el
historial a partir de la sesión guardada.

### 7.4 Showdown y el complemento de jsPDF (PNS-27, PNS-60)

jsPDF ya está en 4.2.1. Showdown 2.1.0 sigue incluido (`pns_ai_chatboo/static/src/js/showdown.js`):
no sanea por diseño, tiene una vulnerabilidad de denegación de servicio publicada (CVE-2024-1899) y
parece sin mantenimiento; hoy su salida pasa por el saneador nuevo. `jspdf.plugin.autotable.min.js` no lo
hemos revisado. **Petición:** sustituir showdown por un convertidor mantenido (seguido del saneador) e
indicar la versión de autotable.

### 7.5 `copy=False` en la clave del proveedor (PNS-20)

Duplicar un proveedor copia su clave API, porque el campo `api_key` no lleva `copy=False`
(`pns_ai_mcp/models/ai_provider.py:194-198`). Solo puede duplicar quien ya lee la clave, así que no hay
ganancia de privilegio, pero la clave se multiplica en registros que quizá no se revisen. Ya existía en
3.1.486. **Petición:** añadir `copy=False`.

### 7.6 `system_prompt` duplicado en `prompts/list`

Una vez corregido el fallo de `prompts/*` (PNS-81, corrección 4), `system_prompt` aparece dos veces en
`prompts/list`: la entrada fija del controlador (`pns_ai_mcp/controllers/main.py:1448`) y el contexto
core cuyo `code` es también `system_prompt`. Nombres duplicados pueden confundir a los clientes MCP.
Gravedad baja. **Petición:** omitir uno de los dos o darles nombres distintos.

### 7.7 Clave MCP en la URL y en el log (resto de PNS-33)

Sin cambios respecto al informe anterior: se sigue aceptando la clave como `?api_key=`
(`pns_ai_mcp/controllers/main.py:421, 716, 867`), lo que la deja en registros de proxies y del navegador,
y se registran sus 10 primeros caracteres a nivel INFO en cada petición (`:863, 869`). El hash sigue
siendo SHA-256 sin sal y sin caducidad (`utils/api_key.py:35-48`). **Propuesta:** aceptar la
clave solo en cabecera y no registrar ninguna parte de ella (o solo un identificador no derivado de la
clave).

### 7.8 Tokens de escritura en caché de Anthropic no contabilizados (resto de PNS-29)

`normalize_usage` recoge los tokens leídos de caché (`cached_tokens`, `cache_read_input_tokens`), pero
no `cache_creation_input_tokens` de Anthropic (`pns_ai_mcp/utils/llm_usage.py:94-99`). La escritura en
caché, que el proveedor factura, no se refleja en el consumo registrado. Sigue sin haber topes de gasto,
de tokens ni de turnos. **Propuesta:** sumar `cache_creation_input_tokens` al consumo y, si es posible,
ofrecer un tope de gasto configurable.

### 7.9 El parche de `Root.get_request` afecta a todas las bases de datos del proceso (observación sobre PNS-31)

El parche de `pns_ai_mcp/http_patch.py` está acotado a las rutas `/mcp`, pero no a la base de datos.
Sustituye `odoo.http.Root.get_request` al importar el módulo (`http_patch.py:22-35`, importado desde
`pns_ai_mcp/__init__.py:15`), con la única condición de la versión de Odoo
(`NEEDS_ROOT_GET_REQUEST_PATCH`, `pns_base/utils/compat.py:20`). Por tanto afecta a todas las bases de
datos que sirve el mismo proceso, tengan o no instalado `pns_ai_mcp`. Impacto práctico bajo: solo cambia
el tratamiento de las peticiones `POST` JSON a `/mcp` y `/mcp/*`. **Sugerimos** documentarlo o, si
es viable, aplicar el cambio solo cuando la base de datos de la petición tenga el módulo instalado.

### 7.10 PNS-92

Ver §6. Aunque hoy no tiene efecto, recomendamos corregirlo junto con los métodos de §2: la protección
actual depende de una línea de log.

---

## 8. Pendiente de comprobar por nuestra parte

Las siguientes comprobaciones necesitan turnos reales con un proveedor de IA y no pudieron completarse
por indisponibilidad del proveedor. Las haremos en un entorno de preproducción y les comunicaremos
cualquier resultado que cambie lo dicho en este informe.

| Comprobación | Hallazgo |
|---|---|
| Consulta por rango de fechas con una función con parámetros de fecha, en Python 3.7 | PNS-81 (corrección 2) |
| Foto con orientación EXIF adjunta en el chat: el modelo debe recibirla girada correctamente | PNS-81 (corrección 3) |
| Contenido de un registro que pide consultar una URL: sin auto-confirmación con las dos políticas de URL, también en el turno siguiente al reutilizar la consulta | PNS-16 |
| Historial de la conversación enviado por el navegador | PNS-61 |
| Operación de escritura pedida por un usuario sin AI Writer, por Chatboo y por MCP | PNS-22 |
| Estado de una operación de otro usuario consultado desde el chat | PNS-05 |
| Nombre de la base de datos y campos de un modelo sin permiso de lectura, pedidos desde el chat | PNS-36 |
| Saneado de la respuesta del asistente durante el streaming, tras recargar y en la exportación | PNS-60 |
| Imágenes externas en las respuestas, con la política restringida y con `open` | PNS-59 |
| Tokens registrados con Anthropic y caché de prompt, frente a la consola del proveedor | PNS-29 |
| Que el contenido del contexto privado de un usuario no llegue a los turnos de otro | PNS-12 |
| Presencia del glosario `es_ES` en lo que recibe el modelo | PNS-46 |
