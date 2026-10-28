# Verificación de seguridad controlada — pns_ai_mcp

**Fecha:** 2026-10-08
**Entorno:** local, Docker del kit (`odoo-dev`). Odoo 14.0.
**Rama analizada:** `third_party` @ `14.0-analisis-pns-ai` (copia de trabajo montada).
**Alcance:** solo lectura del repo salvo este informe. Sin claves de IA. Sin llamadas a
servicios externos. Solo datos de demostración.

> **Nota:** Fecha, Rama y Alcance de esta cabecera describen las fases 1 y 2. Cada sección
> «Versión 3.1.782» y la de «Staging (15-16/10/2026)» indican su propio entorno, rama y alcance.

## Nota sobre la imagen de laboratorio

La instalación **no** se pudo hacer con la imagen común `odoo-dev:14`: a `pns_ai_mcp` le
faltaban dependencias Python (`openpyxl`, y tras ella `httpx` y `pydantic`). Para poder
analizarlo se construyó una **imagen de laboratorio solo local**, `odoo-dev:14-lab_pns_ai`,
mediante una carpeta de laboratorio desechable `~/GitHub/lab_pns_ai` (repo git local que
no se sube a GitHub) que el kit trata como cliente:

- `~/GitHub/lab_pns_ai/CLAUDE.md` → `Versión de Odoo: 14.0`
- `~/GitHub/lab_pns_ai/.odoo-dev.conf` → `COMPARTIDOS="third_party"` y `DOCKERFILE="infra/Dockerfile.14"`
- `~/GitHub/lab_pns_ai/infra/Dockerfile.14` → copia literal de la plantilla del kit
  (`claude-odoo-kit/entorno/Dockerfile.14`) más un bloque final (como `root`, volviendo a
  `odoo`) que instala con pip, solo en esta imagen:
  `openpyxl==3.1.2`, `httpx==0.24.1`, `pydantic==1.10.13`.

> **Importante:** estas tres librerías **NO están en la imagen común del kit ni en ningún
> VPS**. La imagen de laboratorio existe únicamente para este análisis. El mecanismo
> `DOCKERFILE=` del kit solo aplica a repos de *cliente*, no al repo común de módulos
> propios `third_party`; de ahí la carpeta de laboratorio intermedia.

BD del contexto: **`lab_pns_ai_14`** (datos de demostración, desechable). `third_party`
montado como copia de trabajo. `odoo-dev 14 instalar pns_base,pns_ai_mcp` → **OK** (0
bloqueantes). En `third_party` no se dejó ningún archivo (se retiraron el `infra/` y el
`.odoo-dev.conf` que se habían creado antes de mover el laboratorio).

## Nota metodológica

Las operaciones de escritura en BD (crear los 2 usuarios de prueba y la `ai.safe.operation`
de la prueba D con `commit`, las llamadas RPC incluida la que modifica grupos, y la
limpieza) se hicieron con autorización explícita del usuario, acotada a `lab_pns_ai_14`.
Las contraseñas de prueba se omiten en este informe.

## Usuarios de prueba creados (con `odoo-dev 14 shell`)

| etiqueta | id | login | grupos iniciales | `base.group_system` inicial |
|----------|----|-------|------------------|------------------------------|
| INTERNO  | 8  | `lab_interno_sinia` | `base.group_user`, `base.group_no_one` (Technical Features) | False |
| PORTAL   | 9  | `lab_portal`        | `base.group_portal` | False |

El interno se creó **sin ningún grupo de IA ni de administración** (`base.group_no_one` lo
añade Odoo automáticamente y no otorga permisos de IA ni de administración).

---

## Prueba A — escalada de grupo vía `ai.system.action.apply_user_add_group`

**Hipótesis:** `apply_user_add_group` (@api.model, usa `sudo()`, sin comprobar permisos;
`pns_ai_mcp/models/ai_system_action.py:716`) permite a cualquier usuario autenticado
añadirse un grupo. El ACL de `ai.system.action` solo da acceso a `group_ai_admin`
(`ir.model.access.csv:67`), pero al ser un `AbstractModel` sin operaciones ORM propias ese
ACL no se comprueba al invocar el método por `call_kw`.

**Llamadas (JSON-RPC a `http://localhost:8169`, `/web/session/authenticate` + `/web/dataset/call_kw`):**

- INTERNO (autenticado uid=8):
  `ai.system.action.apply_user_add_group(user_id=8, group="base.group_system")`
- PORTAL (autenticado uid=9):
  `ai.system.action.apply_user_add_group(user_id=9, group="base.group_system")`

**Respuestas:**

- INTERNO: `{"result": {"ok": true, "user_id": 8, "group_id": 3, "model": "res.users", "ids": [8], ...}}`
- PORTAL: `{"result": {"ok": true, "user_id": 9, "group_id": 3, "model": "res.users", "ids": [9], ...}}`

**Comprobación posterior (shell, sudo):**

- `uid=8` → `has base.group_system = True`, `has base.group_erp_manager = True`
- `uid=9` → `has base.group_system = True`, `has base.group_erp_manager = True`

**Conclusión: CONFIRMADO (crítico).** Tanto un usuario **interno sin ningún permiso de IA
ni de administración** como un usuario **de portal** escalan a `base.group_system`
(Ajustes/Administración) por RPC directo, sin ninguna comprobación de permisos. El caso del
portal es especialmente grave (un usuario externo se convierte en administrador).

> Tras la prueba A se revirtieron ambos usuarios a su estado inicial (sin `group_system`)
> antes de ejecutar B, C y D, para que esas pruebas se hicieran sobre un interno realmente
> sin privilegios.

---

## Prueba B — invocación de `ai.system.action.preview_module_update`

**Llamada (INTERNO, uid=8, sin privilegios):**
`ai.system.action.preview_module_update(module="pns_base", operation="upgrade")`
(NO se llamó a `apply_module_update`.)

**Respuesta:** `{"result": "Will upgrade module 'PNS Base' (current state: installed)"}`

**Comprobación posterior:** la llamada se ejecuta sin `AccessError`; devuelve la descripción
de la operación. No se realizó ningún cambio (es solo la vista previa).

**Conclusión: CONFIRMADO.** Un usuario interno sin permisos puede invocar
`preview_module_update` (@api.model). Es coherente con el hallazgo de A: los métodos
públicos de `ai.system.action` son invocables por cualquier usuario autenticado. Su gemelo
`apply_module_update` (`ai_system_action.py:630`), no probado por indicación expresa, tiene
la misma forma (@api.model + `sudo()` sin control de permisos) y ejecutaría la
instalación/actualización/desinstalación real.

---

## Prueba C — invocación de `ai.skill.unlink_named_factory_skills`

**Llamada (INTERNO, uid=8, sin privilegios):**
`ai.skill.unlink_named_factory_skills(["no_existe_prueba"])`

**Respuesta:** `{"result": 0}`

**Comprobación posterior:** la llamada se ejecuta sin `AccessError` y devuelve `0` (no se
borró nada, porque el nombre no existe).

**Conclusión: CONFIRMADO.** El método (@api.model) es invocable por un usuario con solo
lectura sobre `ai.skill` (`ir.model.access.csv:16`, `base.group_user` → `1,0,0,0`).
Internamente usa `self.sudo().search(...).unlink()` con
`skip_hardcoded_restrictions=True`, de modo que con nombres **existentes** de skills de
fábrica (`owner_id = False`) un usuario sin permiso de borrado llegaría a eliminarlos. En
esta prueba no se borró nada por usar un nombre inexistente, por seguridad.

---

## Prueba D — manipulación de `ai.safe.operation` por su propietario

**Preparación (shell, sudo):** se creó `ai.safe.operation` `id=1` a nombre del INTERNO
(`user_id=8`), `status='pending'`, plan vacío (`operation_data='{}'`,
`operation_type='action'`, `model_name='res.partner'`, `records_count=0`).

**Llamadas (INTERNO, uid=8, sin privilegios):**

1. `ai.safe.operation.write([1], {"status": "confirmed"})` → `{"result": true}`
2. `ai.safe.operation.write([1], {"user_id": 2})` → `{"result": true}`
3. lectura posterior `ai.safe.operation.read([1], ["status","user_id"])` →
   `AccessError: ... not allowed to access 'AI Supervised Operation' (ai.safe.operation) records`

**Comprobación posterior (shell, sudo):**
`OP id=1 → status=confirmed, user_id=2, executed=False`

**Conclusión: CONFIRMADO (con matiz).** El usuario propietario de una operación supervisada
puede, por `write` directo vía RPC:

- cambiar `status` de `pending` a `confirmed` (auto-confirmación), y
- reasignar `user_id` a otro usuario.

Los campos están declarados `readonly=True`, pero eso **solo afecta a la vista, no protege
en RPC/ORM**. El ACL da `write=1` a `base.group_user` (`ir.model.access.csv:5`,
`access_mcp_safe_operation_user`) y no hay override de `write()` ni `@api.constrains` que
impidan cambiar `status`/`user_id`. Esto permite **saltarse el flujo de supervisión**
(confirmar la operación sin pasar por los métodos `resolve_*`/`execute_*` y sus controles).

**Matiz:** existe la record rule `mcp_safe_operation_user_rule` (`security.xml:92`,
`domain_force=[('user_id','=',user.id)]`) que limita cada usuario a *sus propias*
operaciones. Por eso ambos `write` funcionaron mientras el registro era suyo, y la lectura
posterior falló al reasignar `user_id=2` (el registro deja de pertenecerle). Es decir, el
problema no es acceder a operaciones ajenas, sino que **el propietario puede manipular el
estado de supervisión de su propia operación** antes de ejecutarla. (No se invocó ningún
`resolve_*` ni `execute_*`, por indicación expresa.)

---

## Resumen

| Prueba | Objetivo | Resultado |
|--------|----------|-----------|
| A | Escalada a `group_system` (interno y portal) vía `apply_user_add_group` | **CONFIRMADO (crítico)** |
| B | Invocar `preview_module_update` sin permisos | **CONFIRMADO** |
| C | Invocar `unlink_named_factory_skills` sin permisos | **CONFIRMADO** |
| D | Auto-confirmar / reasignar la propia `ai.safe.operation` | **CONFIRMADO (con matiz)** |

**Causa común (A, B, C):** los métodos públicos `@api.model` de `ai.system.action` y
`ai.skill` usan `sudo()` y no comprueban permisos; al no ejecutar operaciones ORM sobre su
propio modelo, el ACL no se aplica al invocarlos por `call_kw`. Cualquier usuario
autenticado (incluido portal en A) puede invocarlos.
**Causa de D:** `readonly` no protege en RPC y el ACL concede `write` a `group_user` sin
restringir `status`/`user_id`.

## Estado final de la BD tras la limpieza (paso 7)

- `ai.safe.operation` `id=1`: **borrada**. Total `ai.safe.operation` en BD: **0**.
- Usuario `id=8` (`lab_interno_sinia`): **borrado**.
- Usuario `id=9` (`lab_portal`): **borrado**.
- Los grupos añadidos en la prueba A ya se habían revertido antes de B/C/D y, además, los
  usuarios se eliminaron por completo.
- La base de datos `lab_pns_ai_14` **NO se borró** (sigue existiendo, ya sin los datos de
  prueba).

---

## Fase 2 (2026-10-09)

**Entorno:** local, Docker del kit (`odoo-dev 14`), imagen de laboratorio
`odoo-dev:14-lab_pns_ai`, BD **`lab_pns_ai_14`** (datos de demostración, desechable).
`third_party` @ `14.0-analisis-pns-ai` montado como copia de trabajo.
**Autorización:** explícita del usuario, acotada a esta tarea y a `lab_pns_ai_14`
(instalar módulos, crear/borrar usuarios y registros de prueba con `shell` + `commit`,
y JSON-RPC a `http://localhost:8169`). Sin claves de IA ni llamadas externas. Textos de
prueba inocuos. No se añadieron reglas de permisos permanentes. Contraseñas omitidas.

**Usuarios de prueba creados** (con `odoo-dev 14 shell`), todos **sin grupos de IA ni de
administración** (`base.group_no_one` = *Technical Features*, no otorga permisos de IA ni
admin):

| etiqueta | uid | login | grupos | clave MCP |
|----------|-----|-------|--------|-----------|
| A | 10 | `lab_a` | `base.group_user`, `base.group_no_one` | **sí** (generada) |
| B | 11 | `lab_b` | `base.group_user`, `base.group_no_one` | no |
| P | 12 | `lab_p` | `base.group_portal` | no |

### 1. Instalación de `pns_ai_chatboo` (F19)

- **Qué se hizo:** `odoo-dev 14 instalar pns_ai_chatboo`.
- **Resultado:** analizador **0 bloqueantes, 0 avisos**. Importados 3 contextos
  (`presentation_grids`, `ui_focus`, `self_chatboo`) y 11 skills. Avisos del log de Odoo:
  dos etiquetas duplicadas en `ai.agent` (`context_ids_shown`/`context_ids` →
  "Contexts"; `skill_ids_shown`/`skill_ids` → "Skills"), un `DeprecationWarning` de
  Jinja2 (librería del sistema) y varios "module not found" de módulos enterprise no
  instalados (inocuos). Sin tracebacks.
- **Conclusión: CONFIRMADO (instalación limpia).** Los avisos de etiqueta duplicada son
  cosméticos; conviene reportarlos al fabricante. → **F19** (resuelta en lo instalable aquí).

### 3. Aislamiento de Chatboo entre usuarios (F29)

- **Qué se hizo:** `chatboo.session` id=1 de A (mensaje `"texto de prueba"`) creada por
  shell. Con **B** por RPC (`/web/dataset/call_kw`): `search_read`, `write` del nombre y
  `unlink`. Lectura posterior con **P**.
- **Llamadas y resultado:**
  - B `chatboo.session.search_read([[['id','=',1]]], ['id','name','user_id'])` →
    **OK**, lee la sesión de A.
  - B `chatboo.session.write([1], {'name':'texto de prueba B'})` → **OK `true`**.
  - B `chatboo.session.unlink([1])` → **OK `true`** (sesión de A borrada por B).
  - P `chatboo.session.search_read(...)` → **`AccessError`** ("solo User types/Internal
    User"): el portal no accede a `chatboo.session` (ACL de usuario interno).
- **Conclusión: CONFIRMADO (crítico).** No hay ninguna *record rule* que aísle las
  sesiones entre usuarios internos: B lee, modifica **y borra** la sesión de A por RPC.
  El portal queda fuera por ACL de tipo de usuario. → **F29**; decisión **D33** (y D1).

### 4. Lecturas de un interno sin grupos de IA (F8)

- **Qué se hizo:** por shell, `ai.api.server` id=8 inactivo (`auth_token`
  `"token-ficticio-prueba"`, `env_vars`, `config_json`) y `ai.safe.choice` id=1 a nombre
  de A. Con **B** por RPC, solo lectura.
- **Llamadas y resultado:**
  - B `ai.api.server.read([8], ['name','auth_token','env_vars','config_json','active'])`
    → **OK**: lee `auth_token`, `env_vars` y `config_json` en claro.
  - B `ai.fetch.cache.search_read([], ['id'])` → **OK `[]`** (vacía; acceso concedido).
  - B `ai.api.result.cache.search_read([], ['id'])` → **OK `[]`** (vacía; acceso
    concedido).
  - B `ai.safe.choice.search_read([[['id','=',1]]], [...])` → **OK**: lee la choice de A.
- **Conclusión: CONFIRMADO.** Un interno sin grupos de IA lee los secretos de servidores
  externos (`auth_token`/`env_vars`/`config_json`), tiene acceso a ambas cachés y lee
  `ai.safe.choice` ajenas (sin aislamiento). → **F8**; decisiones **D6** y **D2**.

### 5. Portal: métodos de vista previa de `ai.system.action`/`ai.skill` (F2)

- **Qué se hizo:** con **P** (portal) por RPC, solo métodos `preview_*` y un `unlink` con
  nombre inexistente. **No** se invocó ningún `apply_*`.
- **Llamadas y resultado:**
  - P `ai.system.action.preview_user_add_group(12, 'base.group_user')` → **OK**:
    `"Add group User types / Internal User to user Lab P"`.
  - P `ai.system.action.preview_module_update('pns_base', 'upgrade')` → **OK**:
    `"Will upgrade module 'PNS Base' (current state: installed)"`.
  - P `ai.skill.unlink_named_factory_skills(['skill_que_no_existe_lab'])` → **OK `0`**
    (nombre inexistente; no se borró nada).
- **Conclusión: CONFIRMADO.** Un usuario de **portal** invoca los métodos `@api.model` de
  `ai.system.action` y `ai.skill` (vista previa y el `unlink`), igual que ya se vio con
  los `apply_*` en la fase 1 (Pruebas A-C). Refuerza que el control de permisos falta en
  toda la familia de métodos públicos, no solo en los `apply_*`. → **F2**; decisiones
  **D5**, **D4** y **D2**.

### 6. La actualización no ejecuta migraciones (F18)

- **Qué se hizo:** `odoo-dev 14 actualizar pns_ai_mcp`; búsqueda de `"Running migration"`
  en el log.
- **Resultado:** 0 bloqueantes; **0 coincidencias** de `"Running migration"`.
- **Conclusión: CONFIRMADO (lo esperado).** Los scripts de `migrations/` **no** se
  ejecutan en la actualización (coherente con [MAPA] §10.3). → **F18**; decisión **D2**.

**Corrección (2026-10-09).** La prueba anterior **no es concluyente**. En `lab_pns_ai_14`
`pns_ai_mcp` se instaló y se actualizó con la misma versión (3.1.486). En ese caso el
cargador de Odoo no ejecuta ningún script de migración, tengan el formato de versión que
tengan, así que la ausencia de `"Running migration"` en el log no prueba nada sobre F18.

- **Conclusión (corregida): NO CONCLUYENTE** como prueba de ejecución. El hallazgo se
  mantiene por el código.
- **Evidencia:** verificado en código (`migration.py`). En el core de Odoo 14,
  `odoo/modules/migration.py:108-111` (`convert_version` devuelve tal cual las versiones con
  dos o más puntos, como `3.1.484`) y `:161` (compara `14.0.3.1.483 < 3.1.484`, que es falso).
- **Para reproducirlo:** instalar una versión anterior de `pns_ai_mcp` (por ejemplo 3.1.483,
  con una carpeta `migrations/3.1.484` pendiente), actualizar a 3.1.486 y buscar
  `"Running migration"` en el log. Requiere una copia del módulo en esa versión anterior.
- Cambio aplicado en el informe para el fabricante: §7.2 pasa a "Verificado en código".

### 7. Cron de purga de caché de `api_call` (F20)

- **Qué se hizo:** cron `pns_ai_mcp.ir_cron_ai_api_result_cache_gc`
  ("AI: purge expired api_call result cache"): lectura de estado, disparo con
  `method_direct_trigger()` y nueva lectura.
- **Resultado:** tras la instalación/actualización aparecía `active=False` (por la
  **neutralización de crons del kit** en `instalar`/`actualizar`, no por el módulo: el XML
  lo entrega `active=True`). Reactivado a `active=True`: `numbercall=0` (ilimitado),
  `doall=False`; tras `method_direct_trigger()` → **sigue `active=True`, `numbercall=0`**.
- **Conclusión: NO SE REPRODUCE.** El cron **no se auto-desactiva** tras su primera
  ejecución (no tiene `numbercall` limitado). El estado inactivo observado es un efecto
  del laboratorio (neutralización del kit); **en producción esa operación los reactivará**.
  → **F20**; decisión **D2**.

> **Corrección (2026-10-09, cierre de la fase 2).** La conclusión anterior es **errónea**: parte
> de que `numbercall=0` es "ilimitado", y en Odoo 14 es lo contrario. **Conclusión corregida:
> CONFIRMADO.** El cron se desactivó él solo tras su primera ejecución, y `active=True` no basta
> para que vuelva a ejecutarse.
>
> **Qué dice el código** (`/opt/odoo-src/14.0/odoo/odoo/addons/base/models/ir_cron.py`):
>
> - L63: `numbercall = fields.Integer(..., default=1, help='How many times the method is
>   called,\na negative number indicates no limit.')`. El ilimitado es **negativo** (`-1`), y el
>   valor por defecto es **1**.
> - L145-151 (`_process_job`): `while nextcall < now and numbercall:` → si `numbercall > 0` resta
>   uno; solo avanza `nextcall` `if numbercall:`.
> - L154-155: `if not numbercall: addsql = ', active=False'`. Al llegar a 0, el programador
>   **desactiva** el cron en el mismo `UPDATE` (L156).
> - L196-198 y L221-225 (`_process_jobs`): el programador solo coge crons `WHERE numbercall != 0
>   AND active AND nextcall <= now`. Con `numbercall=0` **no se vuelve a ejecutar nunca**, aunque
>   esté activo.
> - L81-86 (`method_direct_trigger`): ejecuta la acción y escribe `lastcall`; **no** lee ni toca
>   `numbercall`, `nextcall` ni `active`. Por eso el disparo manual de este apartado no podía
>   demostrar nada sobre el contador.
>
> **Qué declara el módulo:** `pns_ai_mcp/data/api_result_cache_cron.xml` no define `numbercall`
> ni `doall` (los otros dos crons declaran `numbercall=-1` y `doall=False`). Se crea, por tanto,
> con `numbercall=1`.
>
> **Datos de `lab_pns_ai_14`** (consultas `SELECT` dentro de `BEGIN READ ONLY … ROLLBACK`, hora
> de la consulta 2026-10-09 08:14 UTC):
>
> (a) `ir_config_parameter` **no tiene** ninguna clave `odoo_dev%`: la BD **no** lleva la marca
> `odoo_dev.neutralizada`. En el kit, la re-desactivación de crons tras `instalar`/`actualizar`
> sale sin hacer nada si falta esa marca (`entorno.sh`, `[ -n "$(marca_neutralizada "$bd")" ] ||
> return 0`), y la neutralización completa habría desactivado **todos** los crons; hay 13 de 14
> activos. La explicación "neutralización del kit" queda **descartada**.
>
> (b) Crons de `pns_ai_mcp`:
>
> | cron | `active` | `numbercall` | `doall` | intervalo | `nextcall` (UTC) | `lastcall` (UTC) |
> |------|----------|--------------|---------|-----------|------------------|------------------|
> | `ir_cron_ai_fetch_cache_gc` | t | **-1** | f | 1 h | 2026-10-09 08:42:58 | 2026-10-09 07:43:13 |
> | `ir_cron_ai_api_result_cache_gc` (F20) | t | **0** | *(nulo)* | 1 h | **2026-10-08 15:42:58** | 2026-10-09 08:03:08 |
> | `ir_cron_ai_safe_operation_expire` | t | **-1** | f | 5 min | 2026-10-09 08:02:58 | 2026-10-09 08:00:59 |
>
> - El de F20 tiene `nextcall` **congelado** en la hora de instalación (creado el 2026-10-08
>   15:42:41), con más de 16 h de retraso, mientras los otros dos avanzan con normalidad. Es lo que
>   hace L150-151: con `numbercall` ya a 0, no se suma el intervalo.
> - Su `lastcall` coincide con su `write_date` (2026-10-09 08:03:08): es la escritura de
>   `method_direct_trigger()` de este apartado (L85), no una ejecución del programador.
> - `active=True` es lo que quedó tras la reactivación manual de este apartado; como
>   `numbercall=0`, el programador lo sigue excluyendo (L197).
> - Log del servidor (desde el arranque del 2026-10-08 15:42): el programador ejecutó **una sola
>   vez** "AI: purge expired api_call result cache" (2026-10-08 15:48:03, *Starting job* / *done*),
>   frente a 10 ejecuciones del otro cron horario (`fetch_url`) y 101 del de 5 minutos.
>
> **Razonamiento.** Creado con `numbercall=1`, la primera pasada del programador (15:48) lo
> ejecutó, bajó el contador a 0, no avanzó `nextcall` y lo desactivó (L154-155). Eso explica el
> `active=False` observado tras la instalación. Lo que se leyó después como "`numbercall=0`
> (ilimitado)" era en realidad el contador agotado. Pasará lo mismo en cualquier base de datos,
> producción incluida: la caché de `api_call` deja de purgarse tras la primera hora. Coincide con
> el riesgo n.º 45 y con §7.4 del informe al fabricante. La frase "en producción esa operación los
> reactivará" no aplica a este caso.
>
> **Estado de la BD:** no se ha modificado nada. El cron queda `active=True`, `numbercall=0`, como
> lo dejó este apartado.

### 8. Tests de `pns_ai_mcp` (F23)

- **Qué se hizo:** `odoo-dev 14 tests pns_ai_mcp` (BD de tests nueva
  `test_lab_pns_ai_14`, con `pns_ai_chatboo` y `hr` también en el perfil).
- **Resultado:** **125 tests → 110 pasados, 4 saltados, 5 fallidos, 6 errores.**
  - **Saltados (4):** `TestKnowledgeComposition.test_chatboo_mcp_pack_is_imported`,
    `…test_default_skill_codes_at_module_includes_empty_agent_codes`,
    `TestKnowledgeOwnership.test_private_context_not_in_other_user_prompt`,
    `…test_skill_visibility_get_for_agent`.
  - **Fallos/errores por causa:**
    - `KeyError: 'product.product'` → `test_relaxaicode_model_stamp.test_related_models_from_product_id`,
      `…test_stamp_both_sibling_lists_with_env` (**ambiental:** módulo `product` no
      instalado en el lab).
    - `AssertionError: 'extra' != 'imported'` →
      `test_knowledge_composition.test_composition_origin_four_tokens`,
      `…test_composition_read_orders_by_origin` (origen de contexto; `pns_ai_chatboo`
      aporta contextos "extra" que alteran el conteo).
    - `UserError: Inference agent 'pns_ai_chatboo' is not configured or inactive` /
      "chatboo agent must exist" → `test_mcp_agent.test_resolve_inference_via_feature_key`,
      `…test_get_providers_for_agent_without_admin_acl` (**sin proveedor de IA
      configurado**, por diseño del lab).
    - `PermissionError: … not in the AI Writer group` →
      `test_safe_plan_atomicity.test_failed_execute_cancels_authorization_no_replay`,
      `…test_normal_execution_marks_executed_and_applies_mutation`.
    - `NOT NULL on column 'comment'` (res.partner) →
      `test_system_action.test_accept_choice_creates_verification`,
      `…test_field_required_propose_opens_choice` (**ambiental:** demo con `comment`
      nulo; el test marca el campo requerido).
- **Conclusión: CONFIRMADO parcialmente.** Se confirma que **fallan** `test_mcp_agent` y
  `test_relaxaicode_model_stamp` (previstos en F23). Varios fallos son **ambientales** del
  laboratorio (falta `product`, demo con `comment` nulo, sin proveedor de IA) y **no**
  indican por sí solos un defecto del módulo; el fabricante debería hacer los tests
  robustos ante esas dependencias. → **F23**; decisiones **D31** y **D2**.

### 9. Arranque con `hr` + `pns_ai_chatboo` (F45)

- **Qué se hizo:** `odoo-dev 14 instalar hr`; comprobación de arranque y carga del
  registro con `hr` y `pns_ai_chatboo` instalados.
- **Resultado:** instalación **0 bloqueantes/avisos**; Odoo arranca; registro con **256
  modelos**, `hr=installed`, `pns_ai_chatboo=installed`, `chatboo.session` presente. Sin
  avisos de `SELF_READABLE_FIELDS` ni tracebacks en el log.
- **Conclusión: NO SE REPRODUCE.** El patrón `SELF_READABLE_FIELDS` como `property` no
  impide cargar el registro con `hr` instalado. → **F45**; decisión **D18**.

### Estado de la BD tras la limpieza (paso 10)

- `chatboo.session`: **0** (la id=1 la borró B en el paso 3; confirmado inexistente).
- `ai.api.server` ficticio (`srv_ficticio_prueba`, inactivo): **borrado** (hizo falta
  `active_test=False` para encontrarlo). Quedan **5** `ai.api.server` (los de ejemplo de
  fábrica, intactos).
- `ai.safe.choice`: **0** (la de A borrada).
- Usuarios `lab_a` (10), `lab_b` (11), `lab_p` (12): **borrados**; sus `ai.mcp.user`
  (incluida la clave MCP de A) se eliminaron en cascada (**0** restantes).
- Módulos: `pns_ai_mcp`, `pns_ai_chatboo` y `hr` quedan **instalados** (como pide la
  tarea).
- La base de datos `lab_pns_ai_14` **NO se borró**.

## Versión 3.1.782 — actualización en el laboratorio (fase 3a)

**Fecha:** 2026-10-14 (horas del log en UTC). **Entorno:** `odoo-dev 14` lanzado desde `~/GitHub/lab_pns_ai`,
imagen `odoo-dev:14-lab_pns_ai` (Python 3.7.3, Pillow 5.4.1), BD **`lab_pns_ai_14`**. `third_party`
es una copia de trabajo en la rama `14.0-pns-ai-3`, con los tres parches de compatibilidad de
`docs/pendiente/parches_pns_ai.md` (commit `ce6790b`). Sin avisos de contexto. La BD **no está
neutralizada**: el kit no toca sus crons.
**Autorización:** escribir solo en `lab_pns_ai_14` (actualizar módulos). El resto de las consultas son
`SELECT`. Sin `pip`, sin reglas de permisos permanentes y sin commit.

### Pasos

1. `odoo-dev 14 estado`: contexto correcto (ver arriba). Solo estaba en marcha el contenedor de la BD.
2. Copia previa: `~/odoo-dev/14.0/copias/lab_pns_ai_14_antes_3-1-782.dump` (`pg_dump -Fc`, **3,5 MB**).
3. Estado previo (`SELECT`).
4. `odoo-dev 14 actualizar pns_base,pns_ai_mcp,pns_ai_chatboo`. No hizo falta arrancar antes: usa un
   contenedor propio. Log: `~/odoo-dev/14.0/logs/actualizar-20261014-103123.log` (2 914 líneas,
   08:31:25 → 08:32:20).
5. Revisión del log (abajo).
6. Estado posterior (`SELECT`).
7. `odoo-dev 14 arrancar` (el servidor web no estaba levantado), una petición `GET /web/login` para que
   cargue el registro, `odoo-dev 14 log` y `estado`.

### Resultado del analizador

`0 bloqueante(s) · 0 tipo(s) de aviso` → **RESULTADO: OK**.

El analizador no muestra los WARNING de Odoo que se ven en el log. Ninguno bloquea:

- 31 × `The model … could not be dropped because it did not exist in the registry`: 29 asistentes
  `pns_ai_mcp.*` renombrados a `ai.*`, `pns_ai_mcp.agent.compose.line` y `ai.provider.usage.day`. Odoo
  borra su `ir.model`, campos y accesos, pero **no la tabla** (ver «Tablas»).
- 3 etiquetas duplicadas: `ai.trusted.action` (`model_name`/`model_id`), `ai.mcp.user`
  (`key_pin_html`/`key_pin`) y `ai.log` (`agent_display`/`agent_id`). Son cosméticas.
- 3 `<i class="fa …">` sin `title` (accesibilidad), el `DeprecationWarning` de Jinja2 del sistema y 2 ×
  `MCP: skip retired unlink for pns_ai_mcp (no skill files on disk)`.

### Búsquedas en el log de `actualizar`

| Patrón | Coincidencias | Lectura |
|---|---|---|
| `Running migration` | **0** | Esperado. Esta vez sí es concluyente (de 3.1.486 a 3.1.782, con carpetas `3.1.496`…`3.1.643` pendientes): confirma F18 y la sección «¿Se ejecutarán en Odoo 14?» del inventario. |
| `DROP leftover` | **12** | Lo hace `ai.schema.fossil` (`init()`). Detalle en «Tablas». |
| Borrado de XML ID `*mcp*` | **38 de 38**, uno por cada renombrado de 3.1.518/519 | `_process_end`: `Deleting <id>@<modelo> (pns_ai_mcp.<antiguo>)` y `User #1 deleted …`. Ningún error. |
| `Failed to load` | 0 | |
| `Traceback` | 0 | |
| `AttributeError` | 0 | Los parches 2 y 3 (PNS-81) no se ejecutan durante la actualización, así que esto no los prueba. |
| ` ERROR ` / `CRITICAL` (nivel de log) | 0 | Las 43 líneas con «error» son nombres de campo (`result_errors`) y contadores `'errors': []`. |

Otras líneas relevantes:
- Contextos de fábrica: `0 imported, 53 updated`; skills: `updated: 10`.
- `MCP: unlinked leftover engine discovery_geo rows: 2`.
- Se borran 31 `ir.model`, 522 `ir.model.fields`, 66 `ir.model.fields.selection`, 13 vistas, 9 accesos,
  8 acciones, 7 menús, 4 reglas y 1 restricción.
- Entre los 9 accesos borrados hay 3 que no son de los renombrados: `access_ai_provider_usage_day_admin`,
  `access_ai_provider_usage_day_user` y **`access_ai_fetch_cache_user`**. Este último confirma en la BD
  que se quita la lectura de `ai.fetch.cache` a todos los internos (inventario, «Resumen»; F8).

### Estado antes y después

| Dato | Antes | Después |
|---|---|---|
| `pns_base` | 14.0.1.2.10 | **14.0.1.2.32** |
| `pns_ai_mcp` | 14.0.3.1.486 | **14.0.3.1.782** |
| `pns_ai_chatboo` | 14.0.2.1.322 | **14.0.2.1.453** |
| Crons activos (todos) | 13 | **15** (+`ir_cron_ai_log_retention`, +`ir_cron_pns_export_purge`) |
| XML ID de `pns_ai_mcp` que empiezan por `mcp_` | 4 (las 4 reglas) | **0** |
| XML ID de `pns_ai_mcp` con `mcp` en el nombre | 638 | 77 |
| De los 38 renombrados de 3.1.518/519: antiguos / nuevos `ai_*` | 38 / 0 | **0 / 38** |
| `ai_log`: filas / más antigua | 0 / — | 0 / — |
| `ai.api.server` de fábrica (`external_server_*`, `noupdate`) | 5, inactivos | **5, inactivos** (sin cambios) |
| Skill `analisis_financiero` (id 1, `pns_ai_chatboo`) | existe, activa | **borrada** (quedan 10 skills) |
| Tablas `ai_*`/`pns_*`/`chatboo*` | 65 | 103 |
| Menús de módulos `pns_*` | 21 | 21 (sin nombres duplicados ni menús huérfanos) |
| Parámetros `pns*` | 7 | 12 |

Parámetros nuevos en la BD: `pns_ai_chatboo.history_retention_days=30`, `pns_ai_chatboo.xlsx_float_decimals=2`,
`pns_ai_chatboo.xlsx_thousands=True` y los sellos `pns_ai_mcp.admin_auto_link_fossil_cleared=1` y
`pns_ai_mcp.fossil_acl_security_agent=1`; además `pns_ai.factory_knowledge_stamp` pasa a la versión nueva.
**No** se crean `pns_ai_mcp.log_retention_days` ni `pns_base.export_retention_hours`: se aplican los
valores por defecto del código (30 días y 24 h).

**Crons de `pns_*` después de actualizar y arrancar:**

| Cron | `noupdate` | `active` | `numbercall` | Intervalo | `nextcall` al acabar `actualizar` | Primera ejecución tras arrancar |
|---|---|---|---|---|---|---|
| `pns_base.ir_cron_pns_export_purge` (nuevo) | t | t | -1 | 1 h | 2026-10-14 08:31:48 | 08:35:12, OK |
| `pns_ai_mcp.ir_cron_ai_log_retention` (nuevo) | t | t | -1 | 1 día | 2026-10-14 08:32:04 | 08:35:12, OK |
| `pns_ai_mcp.ir_cron_ai_api_result_cache_gc` | t | t | **0 → -1** | 1 h | 2026-10-08 15:42:58 | 08:35:12, OK |
| `pns_ai_mcp.ir_cron_ai_fetch_cache_gc` | t | t | -1 | 1 h | 2026-10-09 08:42:58 | 08:35:12, OK |
| `pns_ai_mcp.ir_cron_ai_safe_operation_expire` | t | t | -1 | 5 min | 2026-10-09 08:02:58 | 08:35:12, OK |
| `pns_ai_chatboo.ir_cron_chatboo_async_maintenance` | t | t | -1 | 5 min | 2026-10-09 08:02:53 | 08:35:12, OK |

Después de esa ejecución, todos tienen `nextcall` en el futuro y siguen con `numbercall=-1`.

**Tablas:**
- `ai.schema.fossil` borró 12: las 7 tablas `*_pns_ai_mcp_artifact_bundle_export_wizard_rel`,
  `ai_relaxaicode_recipe`, `pns_ai_mcp_relaxaicode_library`, `pns_ai_mcp_relaxaicode_raw_result`,
  `pns_ai_mcp_skill_capture_wizard` y **`ai_provider_usage_day`**.
- **Quedan 30 tablas `pns_ai_mcp_*`** de los asistentes antiguos, ya sin modelo, porque Odoo no las borra
  (aviso «could not be dropped»). Una es `pns_ai_mcp_skill_capture_wizard_agent_rel`, la tabla de
  relación de un asistente cuya tabla principal sí se borró. Son asistentes (transitorios): no tienen
  datos de negocio, solo ocupan sitio.
- Se crean 68 tablas `ai_*`: los asistentes con nombre nuevo, `ai_key_pin_*`, `ai_skill_param_cache`,
  `ai_openapi_spec_generate_wizard`, `pns_export_secrets_wizard`, etc.

### Arranque del servidor (paso 7)

- `odoo-dev 14 estado`: `odoo-dev-14-web-1` en marcha con la imagen `odoo-dev:14-lab_pns_ai`, mismo
  contexto y sin avisos.
- `odoo-dev 14 log`: `loading 27 modules` → `Modules loaded` en 0,78 s. Se registran las herramientas MCP
  `get_context`, `relaxaicode`, `safe_plan_request` y `safe_plan_status`, y `GET /web/login` responde 200.
- Primera pasada del programador de crons (08:35:12): se ejecutan los 6 crons de `pns_*` y los del
  estándar, todos `done`.
- **0** `Traceback`, `ERROR` o `CRITICAL` en las últimas 1 000 líneas. El único WARNING es el
  `DeprecationWarning` de Jinja2.
- Con el parche 1, `pns_ai_mcp` y `pns_ai_chatboo` se importan y la BD carga en Python 3.7.3.

### Relación con los hallazgos y con el inventario

**PNS-81 (compatibilidad con Odoo 14).**
- **Confirmado:** con el parche 1, el fallo al importar queda resuelto en el laboratorio: actualización
  completa y servidor arrancado.
- **Sin probar:** los fallos en ejecución (parches 2 y 3: imagen remota y consulta con parámetro de fecha)
  necesitan una petición funcional. Quedan para la fase 3b.

**PNS-87 (purga de `ai.log` a 30 días).**
- **Confirmado en parte:**
  - el cron se crea activo, diario y con `numbercall=-1`;
  - el parámetro `pns_ai_mcp.log_retention_days` no existe, así que se aplican 30 días;
  - **se ejecuta en la primera pasada del programador tras arrancar** (unos 3 min después de actualizar,
    porque su `nextcall` es la hora de creación).
- **No se ha podido medir el borrado:** `ai_log` tenía 0 filas (el laboratorio no tiene proveedor de IA).
- **Precisión para producción:** la purga no espera un día, sino que se ejecuta al primer arranque tras
  la actualización. Si se quiere conservar el log, hay que crear el parámetro (`0`, o los días que se
  quieran) **antes** de actualizar.
- **Relacionado, sin numerar** (candidato a ampliar PNS-87):
  - Chatboo crea ahora `pns_ai_chatboo.history_retention_days=30`.
  - `chatboo.session._cleanup_old_sessions` (`pns_ai_chatboo/models/chatboo_session.py:1360-1382`) lo
    llama el cron de mantenimiento cada 5 minutos (`models/chatboo_async_request.py:2167`). Borra con
    `sudo()` las sesiones de **todos** los usuarios cuyo último uso tenga más de 30 días.
  - En la versión anterior, el borrado solo afectaba a las sesiones del usuario actual.
  - Aquí `chatboo_session` tenía 0 filas: sin efecto medible.

**PNS-88 (datos que la actualización no limpia).**
- **XML ID: confirmado.**
  - Los 38 `mcp_*` de las migraciones 3.1.518/519 se borran en `_process_end` sin errores, y se crean 38
    `ai_*` con `res_id` **nuevos** (por ejemplo, la regla `ai_safe_operation_user_rule` es la 60; la
    antigua era la 42).
  - Por tanto, se pierden las personalizaciones y las referencias por id a los registros antiguos
    (favoritos y filtros sobre esas acciones, traducciones), como preveía PNS-88.
  - No quedan menús duplicados.
  - Precisión: la consulta «empiezan por `mcp_`» solo cuenta las 4 reglas. Los otros 34 nombres llevan
    `mcp` en medio (`menu_mcp_logs`, `view_mcp_log_form`…).
  - Antes de actualizar, la única vista ajena que heredaba de una vista `*mcp*` de `pns_ai_mcp` era
    `pns_ai_chatboo.res_config_settings_view_form_chatboo_mcp`. Hereda de
    `res_config_settings_view_form_mcp`, que no se renombra, así que no bloqueó nada.
- **Servidores de fábrica: hay que corregir el número.**
  - Quedan **5**, no 3: `mcp_test`, `brave_search` y `seq_thinking` (de `external_server_data.xml`), y
    también **`sesame`** y **`cdmon`**, de `data/external_server_openapi_data.xml`, otro archivo eliminado.
  - Los 5 tienen XML ID `noupdate=True` e inactivos. Odoo no los borra.
- **Skill `analisis_financiero`: confirmado** que se borra en 14 (lo que ya decía la corrección de PNS-67).

**Inventario `docs/specs/cambios_pns_ai_3-1-782.md`, sección «Migraciones».**
- **Confirmado:**
  - ningún script de migración se ejecuta;
  - el renombrado de XML ID no se replica, y su consecuencia es la descrita (registros `ai_*` nuevos y
    `mcp_*` borrados, sin fallos);
  - el cron de caché sin `numbercall` queda arreglado por `init()` (`numbercall` pasa de 0 a -1 y vuelve
    a ejecutarse; cierra F20 y §7.4 en las BD que se actualicen);
  - la skill de Chatboo se borra.
- **Corregir:**
  1. «Borrar tablas de asistentes renombrados y recetas» no es exacto. Entre las 12 tablas que borra
     `ai.schema.fossil` está **`ai_provider_usage_day`**: el histórico diario de tokens y coste por
     proveedor (modelo `ai.provider.usage.day` de la versión anterior), es decir, datos, no un asistente.
     No hay ninguna migración ni `init()` que los traslade. Aquí estaba vacía, verificado con
     `pg_restore -a -t ai_provider_usage_day` sobre la copia. **En producción se perderá ese histórico**.
     Si interesa conservarlo, hay que exportarlo antes de actualizar. Es un candidato a hallazgo (o a
     ampliar PNS-87, porque también es pérdida de datos de consumo sin aviso).
  2. Los asistentes renombrados se borran solo **en parte**. De los 31 modelos que Odoo da de baja, el
     fósil borra la tabla de 2 (`pns_ai_mcp_skill_capture_wizard` y `ai_provider_usage_day`). Además borra
     7 tablas de relación y 3 restos de `relaxaicode` que ya no tenían modelo. Quedan huérfanas **30**
     tablas `pns_ai_mcp_*` (29 asistentes y una tabla de relación). No tiene impacto funcional.
  3. «Los 3 registros de `external_server_data.xml`»: son 5 en dos archivos (ver PNS-88).
  4. No cubierto en el inventario: `pns_ai_chatboo.history_retention_days` y la purga global de sesiones
     de Chatboo (ver PNS-87).

### Estado en que queda la BD

- `lab_pns_ai_14` con las tres versiones nuevas instaladas. Servidor web en marcha
  (`http://localhost:8169`).
- Escrituras hechas, todas por Odoo: la propia actualización y la primera pasada de los crons tras
  arrancar.
- No se han creado usuarios, registros de prueba ni parámetros a mano.
- Para volver al estado previo: `~/odoo-dev/14.0/copias/lab_pns_ai_14_antes_3-1-782.dump`. Restaurarla
  lo decide el usuario. Ojo: `bd-cargar --reemplazar` neutraliza la BD al cargarla.

### Plan para el VPS de pruebas (antes de producción)

1. Copia de la BD.
2. Contar `ai_log` (filas de más de 30 días), `ai_provider_usage_day` y `chatboo_session` (sesiones con
   `last_used_date` de más de 30 días).
3. Retención (son dos parámetros con tratamiento distinto). Exportar antes `ai_provider_usage_day` si se
   quiere conservar.
   - `pns_ai_mcp.log_retention_days`: el módulo no lo crea, así que se puede crear **antes** de actualizar
     con el valor decidido (`0` para no purgar).
   - `pns_ai_chatboo.history_retention_days`: lo crea el módulo con XML ID
     (`icp_chatboo_history_retention_days`, `noupdate="1"`). **No crearlo antes**: un parámetro creado a
     mano sin XML ID chocaría con `key_uniq` al cargar ese registro. Actualizar con los crons parados
     (`--stop-after-init`), ajustar el valor y después arrancar el servidor (ver PNS-63 del seguimiento).
4. Buscar personalizaciones sobre los 38 registros `mcp_*` (dominios de reglas, menús, vistas) y filtros
   o favoritos guardados sobre sus acciones.
5. Actualizar `pns_base,pns_ai_mcp,pns_ai_chatboo` con los parches de PNS-81 aplicados, si el servidor
   tiene Python < 3.9 o Pillow < 6.
6. En la interfaz: menús de Safe operations, Logs, Contexts y Change journal (uno de cada, y que abran);
   Ajustes de IA y de Chatboo.

## Versión 3.1.782 — pruebas de permisos (fase 3b-1)

**Fecha:** 2026-10-14 (horas del log en UTC). **Entorno:** `odoo-dev 14` desde `~/GitHub/lab_pns_ai`,
imagen `odoo-dev:14-lab_pns_ai` (Python 3.7.3), BD **`lab_pns_ai_14`**, servidor web en marcha
(`http://localhost:8169`). `third_party` copia de trabajo en `14.0-pns-ai-3`. Contexto correcto y sin
avisos (`estado`). La BD **no está neutralizada**.
**Alcance:** pruebas de permisos **sin IA** (no se configuraron proveedores ni se hicieron llamadas
externas). **Autorización:** escribir solo en `lab_pns_ai_14` (crear/borrar usuarios y registros de
prueba por `shell` con commit, y JSON-RPC/HTTP a `localhost:8169`). Sin reglas de permisos permanentes,
sin `pip`, sin `git commit`. Contraseñas omitidas. Nunca se invocó `apply_module_update`, `resolve_*`
ni `execute_*`; los `unlink` se hicieron con nombres inexistentes; no hubo ninguna escalada que revertir
(todas fallaron). No se usó `/opt/odoo-src/14.0/third_party`.

**Usuarios de prueba** (shell, sin grupos de IA salvo C; borrados al final):

| etiqueta | login | grupos |
|---|---|---|
| A | `lab_perm_a` | `base.group_user` (interno sin IA; propietario de los registros de apoyo; con clave MCP) |
| B | `lab_perm_b` | `base.group_user` (interno sin IA) |
| P | `lab_perm_portal` | `base.group_portal` |
| C | `lab_perm_writer` | `base.group_user` + `pns_ai_mcp.group_ai_writer` (AI Writer, **sin** AI Administrator ni Ajustes) |

Registros de apoyo creados a nombre de A/B (shell, sudo): `ai.safe.operation` (de A, `pending`),
`chatboo.session` (una de A, una de B), `chatboo.async.request` (de A), `ai.api.server` inactivo con
secretos ficticios, `ai.safe.choice` (A y B), `ai.api.result.cache` (A y B), `ir.attachment` sin
`res_model` (descarga ficticia de A) y otro colgado de la sesión de A, `ai.skill` y `ai.context`
propiedad de C, un contexto privado de A, y la clave MCP de A.

### Grupo a — re-verificación de lo CONFIRMADO en las fases 1 y 2

| Ref | Llamada | Respuesta | Comprobación posterior | Conclusión |
|---|---|---|---|---|
| **F-A** (PNS-01) | A y P RPC `ai.system.action.apply_user_add_group(uid,'base.group_system')` y `_apply_user_add_group(...)` | `apply…`→`AttributeError` (no existe); `_apply…`→`AccessError: Private methods … cannot be called remotely` (A y P) | `res_groups_users_rel`: ni A, ni B, ni P tienen `group_system` | **CORREGIDO** |
| **F-B** (PNS-02) | A RPC `ai.system.action.preview_module_update('pns_base','upgrade')` | `AttributeError` (método privado, no expuesto) | — | **CORREGIDO** |
| **F-C** (PNS-11) | A RPC `ai.skill.unlink_named_factory_skills(['no_existe_lab'])` | `AccessError: Only the system can run this maintenance action.` | — (nombre inexistente) | **CORREGIDO** |
| **F-D** (PNS-03) | A (dueño) RPC `ai.safe.operation.write([SO1],{'status':'confirmed'})`, `{'user_id':2}`, `{'operation_data':…}` | las tres → `AccessError: Only the system can change the state of a supervised operation.` | SO1 sigue `status=pending`, `user_id=A` | **CORREGIDO** |
| **F29** (PNS-53/55) | B RPC `chatboo.session.search_read/write/unlink` de la sesión de A | `search_read`→`[]`; `write`/`unlink`→`AccessError` (chatboo.session) | sesión de A intacta | **CORREGIDO** |
| **F8** (PNS-08/14) | B RPC `ai.api.server.read([SRV1],['auth_token','env_vars','config_json'])`; `ai.fetch.cache.search_read` | `read`→`AccessError` (campos de AI Administrator); `ai.fetch.cache`→`AccessError` (solo AI Administrator) | — | **CORREGIDO** |
| **F2** (PNS-02/11, portal) | P RPC `preview_module_update`, `preview_user_add_group`, `unlink_named_factory_skills(['no_existe_lab'])` | los `preview_*`→`AttributeError`; el `unlink`→`AccessError: Only the system…` | — | **CORREGIDO** |

### Grupo b — PNS del seguimiento (permisos, sin IA)

- **PNS-01 / PNS-02 — CORREGIDO (vía RPC).** Los `apply_*`/`preview_*` ya no existen como métodos
  públicos (`AttributeError`) y los `_apply_*` se rechazan por privados, tanto para A como para P.
  Coincide con el seguimiento (PARCIAL): el vector RPC del informe está cerrado; el resto (un AI
  Administrator que confirma un plan) queda fuera de esta ronda sin IA.
- **PNS-03 — CORREGIDO.** (Ver F-D.) Coincide con el seguimiento.
- **PNS-08 — CORREGIDO.** B no lee `auth_token`/`env_vars`/`config_json` (`AccessError`). Coincide.
- **PNS-09 — CORREGIDO.** A RPC `ai.api.server.action_test_connection([SRV1])` → `AccessError: Only AI
  Administrators can import or export AI configuration artifacts.` Coincide.
- **PNS-11 — CORREGIDO.** A y P RPC `unlink_named_factory_skills(['no_existe_lab'])`,
  `unlink_retired_from_module('pns_ai_mcp')`, `hide_unprefixed_slash_twins()`,
  `reapply_source_module_prefixes('no_existe_modulo')` y `sync_slash_hidden_from_field()` → todos
  `AccessError: Only the system can run this maintenance action.` (`reapply` exige además un argumento
  posicional, pero con él también da `AccessError`). Coincide.
- **PNS-12 — NO CONCLUYENTE (ver nota).** B RPC `ai.context.get_listable_for_mcp()` devuelve un recordset que **no**
  incluye el contexto privado de A (`CTX_A_PRIV`) ni el de C. Coincide.
  > **Nota (fase 3c):** esta prueba no es concluyente. La llamada por RPC sin `sudo` solo comprueba la
  > regla de registro «módulo o propias», que ya existía en 3.1.486. Ver la repetición en la fase 3c
  > (prueba 4): el filtro funciona bajo `sudo` en el modelo, y por `/mcp` no se puede probar por el
  > fallo de `Environment.sudo()` (PNS-81); probado después con el parche 4: CORREGIDO también por
  > `/mcp`.
- **PNS-13 — CORREGIDO (ampliación, 2026-10-14).** En la primera pasada no se pudo montar la prueba con
  un interno sin IA: tanto `GET /mcp/sse` como `POST /mcp` responden `Conversational AI is not allowed for
  this user.` (403 en SSE, error `-32000` en `/mcp`), porque la puerta conversacional exige el grupo
  `pns_ai_mcp.group_ai_conversational` (`utils/conversational.py`). Con autorización, se creó un usuario
  **D** con ese grupo mínimo (sin AI Administrator, AI Writer ni Ajustes) y clave MCP; según el informe
  (`informe_fabricante_pns_ai.md`, PNS-13) el hallazgo cubre **clave revocada** y **usuario archivado**, así
  que se probaron los dos, cada uno en una sesión SSE nueva, **manteniendo el stream abierto** (al cerrarlo,
  la sesión se cierra sola a los pocos segundos, lo que falseaba la prueba). Sin `tools/call`.
  - **Caso A — clave revocada:** sesión SSE abierta con K1; `initialize` y `tools/list` → **202** (válidos).
    Se regenera la clave con el método del módulo `ai.mcp.user.action_generate_mcp_api_key()` (rota la clave;
    K1 queda invalidada). Siguiente mensaje con K1 → **401 `Invalid API key`**; mensaje posterior en la misma
    sesión → **400 `Invalid or expired session`** (sesión cerrada) y el **stream SSE termina solo**.
  - **Caso B — usuario archivado:** nueva sesión SSE con K2 (fijada con `set_mcp_api_key`); `initialize` →
    **202**. Se archiva D (`active=False`). Siguiente mensaje con K2 → **401 `Invalid API key`**; mensaje
    posterior → **400 `Invalid or expired session`** (sesión cerrada) y el stream termina.
  Coincide con el seguimiento (CORREGIDO): `/mcp/message` revalida clave y usuario en cada mensaje y cierra
  la sesión. (Las rutas `/mcp*` son `auth='none'`; se fijó la BD con una cookie de sesión para alcanzarlas.)
- **PNS-79 — NO CONCLUYENTE (no alcanzable en caja negra).** El hallazgo es el valor por defecto
  `SUPERUSER_ID` cuando la sesión MCP no tiene usuario (`controllers/main.py:662`). Las rutas que crean
  sesión (`/mcp/sse`, `initialize`) guardan siempre un usuario ya validado, así que no hay forma de llegar a
  una sesión sin usuario por el flujo normal; el propio informe lo da como «inferido del código, no
  explotable demostrado». No se pudo ejercer en el laboratorio; el código de la corrección (rechazar si no
  hay usuario y revalidar por mensaje) sí se observa y queda cubierto de hecho por las pruebas de PNS-13.
- **PNS-14 — PARCIAL (ver nota).** B: `ai.fetch.cache`→`AccessError`; `ai.api.result.cache.search_read`→solo su
  fila (`create_uid=B`); `ai.safe.choice.search_read`→solo su fila (`user_id=B`). Coincide.
  > **Nota (fase 3c):** la comprobación de `ai.fetch.cache` solo probaba el ACL estándar. Los métodos
  > públicos `get_cached` y `store` trabajan en `sudo` y no pasan por ese ACL: en la fase 3c (prueba 1)
  > resultaron vulnerables (PNS-90). PNS-14 queda PARCIAL.
- **PNS-21 — CORREGIDO.** `GET /pns_ai_mcp/session_file/<att de A>`: sin sesión → **404**; como B → **404**
  (B no puede leer la sesión de A). Coincide (matiz: sin sesión devuelve 404, no una redirección a login).
  > **Nota (fase 3c):** el 404 «sin sesión» no probaba `auth='user'`: sin cookie no había BD
  > seleccionada. Repetida en la fase 3c (prueba 5) con la BD fijada: redirige a `/web/login`. La parte
  > «como B → 404» sí era válida.
- **PNS-28 — CORREGIDO (parte probada).** `POST /mcp` **sin clave** (con la BD fijada por cookie) →
  `API key required`; tras la petición, `ai_log` **no** gana ninguna fila (solo quedaba la de PNS-30).
  Coincide con la parte corregida del seguimiento (PARCIAL; el resto es el CORS `*`, no probado aquí).
- **PNS-30 — SIN CAMBIOS.** A RPC `ai.log.create_log_entry(user_id=B,'write','lab_tool_pns30',…)` → crea
  una fila en `ai_log` con `user_id=B` (31) y `origin=internal`, hecha por A, sin `AccessError`.
  (La primera llamada con `operation_type='action'` falló por un valor inválido de `access_mode`, ajeno
  al hallazgo; con `'write'` creó la fila.) Coincide con el resto del seguimiento: el método público
  `create_log_entry` sigue explotable por un interno.
- **PNS-53 — CORREGIDO.** (Ver F29.) Coincide.
- **PNS-55 — CORREGIDO (aislamiento de sesiones/jobs).** B: `chatboo.async.request.search_read` de A
  →`[]`; `write`→`AccessError`. El resto (ACL de jobs y `claim_turn_file_chips`) se evalúa en PNS-82.
- **PNS-56 — CORREGIDO.** B RPC `chatboo.session.write([CS_A],{'last_query_code':…})` → `AccessError`.
  Coincide.
- **PNS-57 — CORREGIDO.** B RPC `chatboo.async.request.create` sobre la sesión de A → `AccessError: A
  Chatboo turn can only run in your own session.`; sobre la suya → crea (permitido); `spawn`→`AttributeError`;
  `_spawn`→`AccessError` (privado). Coincide.
- **PNS-58 — CORREGIDO.** `POST /chatboo/stream` con cookie de A y cuerpo de texto inocuo, **sin**
  `csrf_token` → **400** `Session expired (invalid CSRF token)`. Coincide.
- **PNS-71 — CORREGIDO.** `/chatboo/check_health` con A autenticado **sin clave MCP** → `status:error`,
  `Chatboo access denied. An MCP API key is required.` Coincide.
- **PNS-80 — YA NO APLICA / CORREGIDO.** B y P RPC `chatboo.async.request.read_progress`→`AttributeError`
  (no existe). `/chatboo/async/poll` con B y el `session_id` de A → denegado por falta de clave MCP (no
  entrega datos de A). Coincide.
  > **Nota (fase 3c):** la parte del sondeo no era concluyente: B no tenía clave MCP y lo frenó
  > `_user_may_use_chatboo` antes del filtro por `user_id`. Repetida en la fase 3c (prueba 6) con un B
  > con clave MCP y `group_ai_conversational`: listas vacías y control positivo correcto.
- **PNS-82 — SIN CAMBIOS (vulnerable hoy).** B RPC `chatboo.session.claim_turn_file_chips([CS_B],
  [{'attachment_id': <att de A>}])` → `ok`; después el adjunto de A pasa a `res_model=chatboo.session`,
  `res_id=CS_B`, y `GET /pns_ai_mcp/session_file/<att>` como B devuelve **200** con el contenido de A.
  Coincide con el hallazgo (se esperaba que funcionara).
- **PNS-83 — SIN CAMBIOS (vulnerable hoy).** A y P RPC `ai.mcp.user.redeem_key_pin(<valor con forma de PIN inexistente>)` →
  `{'ok': false, 'error': 'invalid', 'counted': true}` (responde, sin `AccessError`); `ai.key.pin.block.
  release_all()` → `0` (ejecuta, sin error). Ambos métodos públicos son invocables por un interno y por
  un usuario de portal. Con PIN erróneo y **sin `ip`**, `ai_key_pin_block` **no** gana ninguna fila
  (coincide con el hallazgo: sin `ip` no se cuenta ni se bloquea). Discrepancia menor: el `counted:true`
  de la respuesta no se traduce en una fila de bloqueo cuando falta `ip`.
- **PNS-85 — SIN CAMBIOS (vulnerable hoy).** A RPC `ai.skill.param.cache.remember_for_skill(<skill de
  fábrica>, <frase de prueba>, <un parámetro estable ficticio>)` → crea la fila (id 1, `create_uid=SUPERUSER`), sin
  `AccessError`. (Una primera llamada con `norm` de texto plano se saltó por payload no válido, no por
  permisos.) Coincide con el hallazgo: método público sin control de grupo que escribe como superusuario.
- **PNS-46 (DUDOSO) — NO CONCLUYENTE.** Reconstrucción del contenido fijo del agente
  `pns_ai_chatboo` **sin commit** (`_build_shared_content('es_ES')`, que ensambla sin persistir, y
  rollback): el resultado (78097 caracteres) **no** contiene `1.234,56`, ni `In Spain`, ni el código
  `corporate_terms_es_ES`; y es **idéntico en longitud** para `es_ES` y `en_US`. Los contextos
  `corporate_terms` y `corporate_terms_es_ES` existen y están activos (tipo `locale`), pero **ninguno**
  (ni el genérico) llega a la parte fija del prompt. El resultado no confirma la sospecha del informe
  (que llega el genérico y no la variante `es_ES`), sino que la contradice: el glosario no está en la
  parte fija para ningún idioma. No se comprobaron las vías por usuario ni de descubrimiento, que
  requieren un turno con IA.

### Bloque Writer (usuario C) — un AI Writer no puede hacer de administrador

Todas las llamadas con C (AI Writer sin AI Administrator ni Ajustes):

- **PNS-06 — CORREGIDO.** C crea con `ai.skill.create` una skill cuyo código (`code_body`) usa `sudo()`
  para escribir en un registro → `ValidationError` (el validador rechaza la escritura con `sudo` al
  guardar). Una skill de solo lectura (que devuelve un resultado válido) sí se guarda. Coincide.
- **PNS-10 — CORREGIDO.** C `ai.context.write([CTX_C],{'owner_id':False})` y `ai.skill.write([SKILL_C],
  {'owner_id':False})` con contexto RPC `skip_hardcoded_restrictions=True` → `UserError: Only
  administrators can change context/skill ownership.` (la bandera del contexto se ignora). Coincide.
- **PNS-24 — NO APLICA (comprobación de contexto: el Writer está bloqueado).** La prueba (C
  `ir.module.module.write` → `AccessError`) solo comprueba el ACL estándar de Odoo (Administración/Ajustes);
  el hallazgo es sobre la operación `module.update` ejecutada por el flujo del plan (y su atomicidad), no
  sobre un AI Writer. Se mantiene el estado de la fase 2 (PARCIAL).
- **PNS-48 — NO APLICA (comprobación de contexto: el Writer está bloqueado).** La prueba (C
  `res.config.settings.create` → `AccessError`) solo reconfirma el ACL estándar `base.group_system`; el
  hallazgo es la visibilidad del menú Settings para un AI Administrator y las acciones duplicadas. Se
  mantiene el estado de la fase 2 (CORREGIDO).
- **PNS-84 — NO APLICA (comprobación de contexto: el Writer está bloqueado).** La prueba (C no lee
  `ai.key.pin.ask` ni `ai.mcp.user`) solo comprueba el ACL `group_ai_admin`; el hallazgo es lo que un AI
  Administrator ve en claro (PIN y clave MCP). Se mantiene el estado de la fase 2 (NUEVO).
- **PNS-86 — NO APLICA (comprobación de contexto: el Writer está bloqueado).** La prueba (C no crea
  `ai.openapi.spec.generate.wizard`) solo comprueba el ACL `group_ai_admin`; el hallazgo es el SSRF que
  ejecuta un AI Administrator. Se mantiene el estado de la fase 2 (NUEVO).

### Limpieza (paso 4)

Borrados con `SELECT` de verificación a 0: usuarios `lab_perm_*` (A incluido), sus `ai.mcp.user` (3),
`chatboo.session` (2), `chatboo.async.request` (2), `ai.safe.operation` (1), `ai.safe.choice` (2),
`ai.api.result.cache` (2), `ai.skill.param.cache` (1, de PNS-85), `ai.api.server` lab (1), `ir.attachment`
lab (2), `ai.skill` lab (2), `ai.context` lab (2), `ai.log` lab (1, de PNS-30). `ai.key.pin.block`: 0 (no
se creó ninguno). **Los 5 `ai.api.server` de fábrica siguen intactos e inactivos**: `mcp_test`,
`brave_search`, `seq_thinking`, `sesame`, `cdmon`. La BD `lab_pns_ai_14` no se borró.

**Ampliación PNS-13 (2026-10-14):** el usuario de prueba **D** (`lab_perm_d`, grupo
`pns_ai_mcp.group_ai_conversational`) y su `ai.mcp.user`/clave MCP se borraron al terminar; no se creó E.
`SELECT` de verificación: 0 usuarios `lab_perm_d`/`lab_perm_e`, 0 `ai.mcp.user` huérfanos, 5 `ai.api.server`
de fábrica intactos.

**Corrección (2026-10-14, fase 3b-2):** la limpieza de la ampliación PNS-13 **no** dejó `ai_log` limpio. Quedaban
6 filas de protocolo MCP de esa prueba (ids 2 a 7: `initialize`/`tools/list`, cliente «lab 1», 10:16 a
10:19, con `user_id` vacío tras borrar a D). Se borraron en la limpieza de la fase 3b-2 (`SELECT`: 0 filas).

### Tabla final (PNS/F · estado fase 2 · resultado laboratorio · ¿coinciden?)

| PNS/F | Estado fase 2 | Resultado laboratorio | ¿Coinciden? |
|---|---|---|---|
| F-A / PNS-01 | PARCIAL | CORREGIDO (vector RPC) | Sí (vector RPC) |
| F-B / PNS-02 | PARCIAL | CORREGIDO (vector RPC) | Sí (vector RPC) |
| F-C / PNS-11 | CORREGIDO | CORREGIDO | Sí |
| F-D / PNS-03 | CORREGIDO | CORREGIDO | Sí |
| F29 / PNS-53 | CORREGIDO | CORREGIDO | Sí |
| F8 / PNS-08 | CORREGIDO | CORREGIDO | Sí |
| F2 (portal) | CORREGIDO | CORREGIDO | Sí |
| PNS-09 | CORREGIDO | CORREGIDO | Sí |
| PNS-12 | CORREGIDO | NO CONCLUYENTE (ver 3c: CORREGIDO en el modelo) | No (solo la regla de registro) |
| PNS-13 | CORREGIDO | CORREGIDO (clave revocada y usuario archivado → 401 + sesión cerrada) | Sí |
| PNS-79 | CORREGIDO | NO CONCLUYENTE (no alcanzable en caja negra) | Parcial |
| PNS-14 | CORREGIDO | PARCIAL: resto vulnerable (3c, PNS-90) | No |
| PNS-21 | CORREGIDO | CORREGIDO | Sí |
| PNS-28 | PARCIAL | CORREGIDO (parte de `ai.log`) | Sí (parte probada) |
| PNS-30 | PARCIAL | SIN CAMBIOS (resto reproducido) | Sí |
| PNS-55 | PARCIAL | CORREGIDO (aislamiento) / ver PNS-82 | Sí |
| PNS-56 | CORREGIDO | CORREGIDO | Sí |
| PNS-57 | CORREGIDO | CORREGIDO | Sí |
| PNS-58 | CORREGIDO | CORREGIDO | Sí |
| PNS-71 | CORREGIDO | CORREGIDO | Sí |
| PNS-80 | YA NO APLICA | YA NO APLICA | Sí |
| PNS-82 | NUEVO (sin corregir) | SIN CAMBIOS (vulnerable) | Sí |
| PNS-83 | NUEVO (sin corregir) | SIN CAMBIOS (vulnerable) | Sí |
| PNS-85 | NUEVO (sin corregir) | SIN CAMBIOS (vulnerable) | Sí |
| PNS-46 | DUDOSO | NO CONCLUYENTE (ningún glosario en la parte fija, para ningún idioma) | No confirma la sospecha; la contradice |
| PNS-06 | CORREGIDO | CORREGIDO | Sí |
| PNS-10 | CORREGIDO | CORREGIDO | Sí |
| PNS-24 | PARCIAL | NO APLICA (contexto: Writer bloqueado) | — (se mantiene PARCIAL) |
| PNS-48 | CORREGIDO | NO APLICA (contexto: Writer bloqueado) | — (se mantiene CORREGIDO) |
| PNS-84 | NUEVO | NO APLICA (contexto: Writer bloqueado) | — (se mantiene NUEVO) |
| PNS-86 | NUEVO | NO APLICA (contexto: Writer bloqueado) | — (se mantiene NUEVO) |

**Discrepancias / matices:**
1. **PNS-13:** verificado con un usuario D del grupo mínimo `group_ai_conversational` (ampliación del
   2026-10-14): la revalidación por mensaje funciona para clave revocada y para usuario archivado (401 +
   sesión cerrada + fin del stream). Matiz: hay que mantener el stream SSE abierto durante la prueba, porque
   al cerrarlo la sesión se cierra sola a los pocos segundos. **PNS-79** (sesión sin usuario → `SUPERUSER_ID`)
   queda **NO CONCLUYENTE**: no es alcanzable en caja negra porque las rutas que crean sesión guardan siempre
   un usuario validado.
2. **PNS-21:** sin sesión devuelve **404** en lugar de redirigir al login; el efecto (no se entrega el
   archivo) es el esperado. Sustituida por la fase 3c (prueba 5).
3. **PNS-83:** la respuesta trae `counted:true`, pero sin `ip` **no** se crea fila en `ai.key.pin.block`
   (no hay límite efectivo), como dice el hallazgo.
4. **PNS-46 (NO CONCLUYENTE; sigue DUDOSO):** ni el glosario `es_ES` ni el genérico `corporate_terms`
   llegan a la parte fija del prompt, y esa parte es idéntica para `es_ES` y `en_US`. Eso no confirma la
   sospecha del informe (llega el genérico y no la variante), sino que la contradice: el glosario no está
   en la parte fija para ningún idioma. Queda revisar la vía de descubrimiento y un turno real con IA.
5. **PNS-24, 48, 84, 86 (bloque Writer):** las pruebas solo confirman que un AI Writer queda bloqueado por
   el ACL estándar (Ajustes o `group_ai_admin`), pero el hallazgo de cada uno es sobre otro rol u otra
   operación (la ejecución de `module.update` por el plan; la visibilidad del menú del AI Administrator; lo
   que ve en claro un AI Administrator; el SSRF del AI Administrator). Por eso pasan a **NO APLICA
   (comprobación de contexto)** y se conserva el estado de la fase 2; no aportan evidencia sobre el
   hallazgo en sí.

## Versión 3.1.782 — pruebas funcionales con proveedor (fase 3b-2)

**Fecha:** 2026-10-14 (horas del log en UTC). **Entorno:** `odoo-dev 14` desde `~/GitHub/lab_pns_ai`, BD
**`lab_pns_ai_14`** (no neutralizada), `third_party` en `14.0-pns-ai-3`, web en marcha y sin aviso de
contexto (`estado`). **Proveedor:** Google Gemini, nivel gratuito, protocolo OpenAI-compatible
(endpoint `…/v1beta/openai/chat/completions`), registro `ai.provider` id 5 «Gemini lab», modelo
inicial `models/gemini-3.8-flash` (fila 33 de `ai.provider.model`, creada por el catálogo), que respondía
503; las pruebas se hicieron con `models/gemini-3.7-flash` (fila 32). La clave la
introdujo Sergio en la interfaz; no se ha leído ni mostrado (los `SELECT` excluyen la columna). La
revoca Sergio en AI Studio. **Autorización:** escribir solo en `lab_pns_ai_14` (usuarios y registros de
prueba, sesiones de chat); como mucho unas 30 peticiones al modelo; solo datos de demostración y textos
inocuos; nada de `resolve_*`, `execute_*` ni `apply_module_update`. No se usó `/opt/odoo-src/14.0/third_party`.

### Configuración (paso 2)

- **Proveedor:** menú *AI Engine → Connections → Providers* (solo `group_ai_admin`). Protocolo
  OpenAI-compatible; capacidades **Conversation** y **Vision** (sin Audio, que lanza una sonda de voz al
  guardar; sin Decision ni Video); `context_window` 131072; temperatura 0,7; **No external failover**
  marcado. El modelo solo se fija con `model_id` (catálogo); `model_name` es un `related` de solo lectura.
- **Agente:** *AI Engine → Agents → Chatboo* (`pns_ai_chatboo`, inference, activo y conversacional),
  pestaña Providers: una única línea con «Gemini lab» (`ai.agent.provider` id 1).
- **Usuario de chat:** `pns_ai_mcp.group_ai_conversational` (implica `base.group_user`) **más** una clave
  MCP (`pns_ai_chatboo/utils/chatboo_access.py`). Nada más para chatear.
- **Grupo temporal:** `admin` no tenía AI Administrator (sin él no ve el menú). Sergio se lo asignó para
  esta fase; se retira en la limpieza.
- **Proveedores de fábrica archivados temporalmente:** ids 1 (OpenRouter), 2 (OVH), 3 (Lemonade) y 4
  (Ollama), los cuatro sin clave y sin enlazar a ningún agente. Motivo: si un agente de inferencia no
  tiene cadena, el motor usa **todos los proveedores activos por orden de id**
  (`pns_ai_mcp/models/ai_execution_engine.py:203-224`); se archivaron para que ningún texto pueda salir
  hacia ellos. Se reactivan en la limpieza. **No es un hallazgo nuevo:** ya figura como observación de
  PNS-61 en `seguimiento_informe_pns_ai.md` («si el agente no tiene cadena, sirve cualquier proveedor
  activo… decisión de configuración») y en PNS-71 del informe del fabricante (para `/chatboo/providers`).

### Línea base antes de las pruebas

- `ai_log`: 6 filas (ids 2 a 7), del 2026-10-14 entre las 10:16 y las 10:19, `origin=mcp_client`,
  `initialize`/`tools/list`, cliente «lab 1», `user_id` vacío (usuario borrado). Son **restos de la
  ampliación de PNS-13 de la fase 3b-1** (usuario D): la limpieza de la 3b-1 no borró esas filas de
  protocolo. Se conservaron durante las pruebas y se borraron en la limpieza de esta fase.
- `ai.mcp.user` ids 3 (`demo`) y 4 (`admin`), creados el 2026-10-09 a las 07:58:59 (mismo instante, en
  la instalación de la fase 2), **sin** hash de clave. No son de pruebas; se conservan.
- `res_users` máx. id 7; 0 sesiones de Chatboo.

### Incidencias de configuración (antes del paso 3)

Revisadas en `odoo-dev 14 log 300`, `ai_log` y el propio proveedor:

1. **«Test Connection» pulsado una vez (10:42:41), sin modelo:** `UserError` «Selecciona un modelo o
   introduce un nombre de modelo» **antes** de cualquier llamada de red (`test_connection` comprueba el
   modelo al principio). **No llegó a Google.** Sin fila en `ai_log`.
2. **Catálogo de modelos («Browse»/«Copy catalogue»):** el log muestra **tres** `call_button` con latencia
   de red sobre el proveedor 5 (10:43:19, 10:43:41 y 10:48:05; 0,19 a 0,26 s) y uno más sobre una
   **copia** del proveedor (id 6, creada con `ai.provider/copy` a las 10:56:11, catálogo a las 10:56:16
   y borrada a las 10:56:37). Son **4 GET al catálogo de Google** (sin inferencia ni tokens). El catálogo
   respondió con la lista (63 modelos, primera inserción a las 10:43:18): **la URL de catálogo derivada
   funciona con Google** (se corrige la suposición del 404 hecha al leer el código). El GET de catálogo
   no deja fila en `ai_log` ni línea con la URL en el log. La copia (id 6) la hizo Sergio.
   - **Candidato a hallazgo menor (sin numerar):** al **duplicar** un `ai.provider` se copia también su
     clave API (`api_key` no tiene `copy=False`, `pns_ai_mcp/models/ai_provider.py:194-198`). La copia
     queda con credenciales operativas sin que el administrador las haya introducido, y puede usarse
     (catálogo, inferencia) con otro endpoint o modelo.
3. **Selección automática de modelo y onchange:** `_refresh_model_catalogue` fija el primer modelo del
   catálogo si no hay ninguno (escritura en servidor, sin sondas). Al quitarlo a mano, los `onchange`
   duraron ~1 ms (sin red): **no hubo sondas**. Campos del proveedor tras las incidencias:
   `temperature_support`, `usage_support` y `stt_support` siguen en `unknown`; capacidades sin cambios
   (Conversation y Vision).

### Paso 3 — petición mínima

Una petición directa al driver (`shell`, texto inocuo de una palabra, sin herramientas ni sondas, sin
commit) a las 10:57:31 → **HTTP 503** de Google tras 7,6 s (no es 429 ni error de cuota). El cuerpo del
error no se conservó (solo se vio su comienzo); un 503 de este servicio suele indicar modelo
sobrecargado. No se reintentó. El log de esa llamada solo contiene endpoint y modelo (sin clave).

**Reintentos (autorizados: 2 reintentos y un intento sin prefijo):** misma petición mínima.

| Hora | Modelo enviado | Resultado |
|---|---|---|
| 10:57:31 | `models/gemini-3.8-flash` | HTTP 503 (7,6 s) |
| 11:06:23 | `models/gemini-3.8-flash` | HTTP 503 (1,1 s) |
| 11:11:38 | `models/gemini-3.8-flash` | HTTP 503 (4,5 s) |
| 11:11:56 | `gemini-3.8-flash` (sin prefijo, solo en la configuración del driver; BD sin cambios) | HTTP 503 (3,0 s) |

Cuerpo del error (guardado en los tres últimos; sin cabeceras; se comprobó dentro del shell que no
contenía la clave): `code 503`, `status UNAVAILABLE`, mensaje «This model is currently experiencing
high demand. Spikes in demand are usually temporary. Please try again later.». Es una **sobrecarga del
modelo en Google**, no un 429 ni un error de cuota, y no depende del prefijo `models/` (Google reconoce
el modelo con y sin él). **Las pruebas con IA quedan pendientes** de que el modelo responda o de que se
elija otro modelo.

**Cambio de modelo (opción B, autorizado):** modelos Flash estables del catálogo (`SELECT`, sin
peticiones; fuera `lite`, `preview`, `exp` y las variantes de imagen, TTS, audio, `latest` y `omni`):
`gemini-2.5-flash`, `3.5-flash`, `3.6-flash`, `3.7-flash` y `3.8-flash`. Se fijó por shell, sin sondas,
el más reciente anterior a 3.8: **`models/gemini-3.7-flash`** (fila 32 de `ai.provider.model`).

| Hora | Modelo enviado | Resultado |
|---|---|---|
| 11:29:05 | `models/gemini-3.7-flash` | **200** (4,4 s): respuesta «hola»; `usage` = 9 de entrada, 1 de salida, **133 en total** |

Observación (relacionada con PNS-29): `total_tokens` (133) es mucho mayor que entrada + salida (10). La
diferencia corresponde, previsiblemente, a tokens de razonamiento interno del modelo que no aparecen en
`completion_tokens`. Habrá que ver qué cifra guarda `ai_log` en los turnos.

**Contador de peticiones a Google:** 5 de inferencia (4 con 503 y 1 correcta) + 4 GET de catálogo.

### Preparación de las pruebas (paso 4, aprobado)

Usuarios de prueba (shell; contraseñas y claves MCP solo en un archivo temporal fuera del repo):
Ese archivo y el resto de temporales de las fases 3a, 3b-1 y 3b-2 (scripts, cookies, imagen de prueba) se borraron al terminar (2026-10-14).


| etiqueta | login | id | `ai.mcp.user` | grupos |
|---|---|---|---|---|
| U1 | `lab_chat_a` | 35 | 21 | `base.group_user` + `group_ai_conversational` |
| U2 | `lab_chat_b` | 36 | 22 | `base.group_user` + `group_ai_conversational` |
| U3 | `lab_chat_url` | 37 | 23 | lo anterior + `group_ai_external_url` |

Registros de apoyo: `ai.url.whitelist` id 3 (`raw.githubusercontent.com`, tipo `web`, temporal);
`ai.safe.operation` id 7 (`WRIT00000001`, de U1, `pending`, sin datos de operación, para PNS-05);
`res.partner` id 73 (contacto de demostración cuya nota pide al asistente consultar el tiempo de una
ciudad en `api.open-meteo.com`, para PNS-16). Valor original de `pns_ai_mcp.url_access_policy`: **el
parámetro no existe** (se aplica el valor por defecto `whitelist_only`); restaurar = borrarlo.
Imagen de prueba para Chatboo: JPEG sintético de cuatro cuadrantes de colores guardado girado con
orientación EXIF 6 (derecha, el cuadrante superior izquierdo es rojo).

### Pruebas sin IA (ejecutadas)

- **Prueba 2 — Parche 2 / PNS-81 (imagen remota): CORREGIDO.** U1 `GET /pns_ai_mcp/remote_image` con el
  logo de Odoo 14 servido por `raw.githubusercontent.com` (host en la lista blanca) → **200**,
  `image/png`, 9491 bytes (imagen re-codificada por `shrink_picture`). Sin el parche respondería 404
  (fallo de `ImageOps.exif_transpose` en Pillow 5.4.1). Sin trazas en el log.
- **Prueba 3 — PNS-59 (host no permitido): CORREGIDO (parte del servidor).** Mismo `GET` con un host
  fuera de la lista blanca (política `whitelist_only`) → **404** en 4 ms, sin petición al exterior (la
  comprobación del host va antes de la descarga, `utils/remote_image.py`). La parte del navegador
  (reescritura a `remote_image` en el cliente) y la variante con política `open` quedan pendientes de
  los turnos con IA.
- **Prueba 12 — PNS-62 (tope de subida): CORREGIDO (archivo único).** U1 envía a `/chatboo/stream` una
  imagen de 16 MB (tope 15 MB) → evento con «… supera el límite de subida (15 MB).» y `done`; **0 jobs**
  en `chatboo.async.request`, **0 filas** nuevas en `ai_log` y ninguna llamada al proveedor. Matiz: la
  sesión de chat (id 10) se crea antes de comprobar el tamaño. (Un primer envío con `Content-Type:
  application/json` lo rechazó Odoo como petición JSON-RPC antes de llegar a la ruta; el cliente usa
  `text/plain`.) La parte «varios archivos menores cuya suma es grande» no se probó.

### Pruebas con IA (`models/gemini-3.7-flash`, 2026-10-14, 11:34 a 11:47 UTC)

Mecánica: turnos por HTTP a `/chatboo/stream` (sesión de cada usuario, `csrf_token`, cuerpo
`text/plain`), un reintento por prueba ante 503 o tiempo agotado. Recuento de peticiones con las filas
`llm_orchestration`/`llm_response` de `ai_log` y los errores del log (el motor va por streaming y no
escribe la línea `OpenAIDriver request to`).

**Comportamiento del proveedor:** la petición mínima (unos 10 tokens) respondió, pero **todas las rondas
principales de Chatboo** (prompt completo del agente con herramientas) fallaron: unas con **503
UNAVAILABLE** («high demand») y otras con **lectura agotada a los 45 s** (`llm_idle_timeout` del enlace
agente-proveedor) sin recibir ningún dato. Solo respondió una llamada auxiliar pequeña (lectura de la
imagen). Por la regla acordada, las pruebas que dependen de la respuesta del modelo quedan **PENDIENTE
PARA STAGING (proveedor saturado)**; lo que el servidor hace antes de llamar al modelo sí se pudo observar.

- **Prueba 1 — Parche 3 / PNS-81 (consulta por fechas), U1: PENDIENTE PARA STAGING (proveedor saturado: 503 y tiempos agotados).** Pregunta por el
  número de contactos creados en un rango de fechas, pidiendo una función con `date_from`/`date_to`.
  1.er intento: 503; reintento: tiempo agotado. No llegó a ejecutarse la herramienta de código, así que el
  parche 3 no se ejercitó en el laboratorio.
- **Prueba 4 — Imagen en Chatboo (visión + EXIF, parche 2), U1: PENDIENTE PARA STAGING (proveedor saturado: 503 y tiempos agotados).** Imagen
  sintética de cuatro cuadrantes con EXIF 6; pregunta por el color de un cuadrante. 1.er intento: el paso
  previo de lectura de la imagen (OCR, llamada aparte) **respondió** (`ai_log` 13: 1159 de entrada, 7 de
  salida, 1234 en total; «sin texto»), pero eso no demuestra el parche 2: sin él, el fallo de Pillow
  es silencioso (las funciones de imagen devuelven `None` y la imagen se envía sin reescalar). La prueba
  válida del parche 2 es la de `remote_image` (prueba 2). La ronda principal dio 503. Reintento: tiempo
  agotado (sin paso de OCR, ya hecho). La orientación con la que llega al modelo no se pudo comprobar.
- **Prueba 5 — PNS-16 (contenido no confiable que pide una URL), U3, política `open` temporal:
  PENDIENTE PARA STAGING (proveedor saturado).** Contexto de pantalla del contacto 73 y petición de resumir su ficha. El
  contexto de pantalla solo lleva nombre y campos de resumen (no la nota): la nota llegaría al modelo
  por el resultado de una herramienta, que también se marca como no confiable. Dos tiempos agotados; no
  se creó ninguna operación supervisada ni hubo salida a `api.open-meteo.com`, pero el modelo no llegó a
  pedir nada, así que no es evidencia. Dato lateral: U3 (con AI External URL) recibe 4 herramientas y U1/U2
  (solo conversacional) 2 → **el filtrado de herramientas por grupo funciona**.
- **Prueba 7 — PNS-61, U1:** `provider_id` inexistente (999) y un `history` con un turno inventado (un
  código de cliente ficticio). **Parte `provider_id`: CORREGIDO** (se ignora; el turno va a «Gemini lab»,
  el único de la cadena). **Parte historial: PENDIENTE PARA STAGING (proveedor saturado: 503 y tiempos agotados)** en cuanto a la respuesta (tiempo
  agotado y 503), aunque `ai_log` muestra que la ronda se envió con 4 mensajes: **el historial fabricado
  por el navegador entra en el prompt**, como describe el seguimiento (SIN CAMBIOS en lo observable).
- **Prueba 8 — PNS-22 (escritura sin AI Writer), U1: PENDIENTE PARA STAGING (proveedor saturado: 503 y tiempos agotados).** Petición de crear un
  contacto. Dos tiempos agotados; no se creó ningún contacto ni operación supervisada (sin valor de
  prueba, porque el modelo no respondió).
- **Prueba 9 — PNS-05 (estado de una operación ajena), U2: PENDIENTE PARA STAGING (proveedor saturado: 503 y tiempos agotados).** Pregunta por el
  `verification_id` de la operación 7 (de U1). Tiempo agotado y 503. Nota: la operación pasó a `expired`
  enseguida porque `expires_at` es un campo calculado desde la creación (`_compute_expires_at`), no el
  valor que se le dio; no afecta a la prueba.
- **Prueba 10 — PNS-66, U1 (`/users-all`): SIN CAMBIOS (vulnerable hoy), sin IA.** La skill va por la vía
  rápida (`ai_log`: `skill_fast_path`, **0 peticiones al modelo**) y entrega a un usuario sin ningún grupo
  de IA el censo completo de usuarios: login, nombre, correo, tipo, activo/inactivo y último acceso
  (incluidos los usuarios inactivos y el del sistema). Coincide con el seguimiento.
- **Prueba 11 — PNS-18 + PNS-40, U1:** proveedor de prueba temporal con endpoint inalcanzable en
  `127.0.0.1`, «No external failover» y prioridad delante de Gemini. **PNS-18: CORREGIDO.** La cadena
  resuelta solo contiene el proveedor local (`get_providers_for_agent`); el turno termina en error y **no
  hay llamada a Gemini** (ni fila en `ai_log` ni línea en el log). **PNS-40: SIN CAMBIOS (vulnerable hoy).**
  El mensaje del chat muestra al usuario host, puerto, ruta y la excepción interna de `urllib3`; en los
  demás turnos mostraba la URL completa del endpoint de Google y el cuerpo del 503. Coincide con el
  seguimiento. Proveedor de prueba y su línea borrados después; cadena de nuevo solo con Gemini lab
  (`SELECT`).
- **PNS-36 (esquema y nombre de la BD), U1: PENDIENTE PARA STAGING (proveedor saturado: 503 y tiempos agotados).** Dos tiempos agotados.
- **PNS-29 (tokens), comparación con Google:** en la única llamada con respuesta dentro de Chatboo (paso
  de OCR), `ai_log` guarda entrada 1159, salida 7 y total 1234: la diferencia (68) son tokens de
  razonamiento, que **solo están dentro del total**, sin columna propia; `cost_usd` = 0. En la petición
  mínima directa Google informó 9 / 1 / 133 (123 de razonamiento). Además, el evento `done` de ese turno
  informó `usage` 0 (no suma el paso de OCR), y las rondas fallidas registran 0. Coherente con el
  seguimiento (PARCIAL: tokens no contabilizados en varias rutas); con proveedor Anthropic y caché no
  se probó.

**Revisión del log** (`odoo-dev 14 log 300`): 11 tracebacks, **todos de red** (`ReadTimeout`, 503 y la
conexión rechazada de la prueba 11, en `openai_driver.iter_chat` / `agent_engine._run_stream_with_provider`).
**Ningún `AttributeError`** y ninguna traza en `pns_base/utils/pdf_io.py` ni en `relaxaicode`. Búsqueda de
claves (patrones `Bearer …`, prefijo de las claves de Google y la clave ficticia del proveedor de prueba)
en el log, en `ai_log` y en las sesiones: **0 apariciones**.

**Contador tras estas pruebas:** 20 peticiones de inferencia (5 previas + 15 en las pruebas: 1 con
respuesta en el paso de OCR, el resto 503 o tiempo agotado) + 4 GET de catálogo.
- **PNS-60 (HTML en el cliente de Chatboo), U1 en el navegador (lo hizo Sergio):** se pegó en Chatboo un
  texto que pedía repetir unas etiquetas con manejadores de evento inofensivos (sin efecto visible ni
  peticiones), un enlace con esquema no permitido y un SVG sencillo.
  - **Respuesta del modelo: PENDIENTE PARA STAGING (proveedor saturado: 503 y tiempos agotados).** Dos
    intentos (tiempo agotado a los 45 s y 503); 2 peticiones.
  - **Mensaje del usuario en el DOM: CORREGIDO** (en directo y tras recargar y reabrir desde el
    historial, igual en los dos casos): se conservan las etiquetas de formato, el enlace y el SVG, pero
    **sin** manejadores de evento, y el enlace **sin** `href` (el esquema no permitido se elimina).
  - **Exportación a PDF/Word: PENDIENTE PARA STAGING** (no hubo respuesta que exportar).
  - Observaciones (no son hallazgos): el mensaje del usuario se interpreta como HTML ya saneado en lugar
    de mostrarse como texto literal; el saneador admite SVG (sin scripts).
  - Los mismos errores vuelven a mostrar al usuario host, puerto, URL completa y cuerpo del 503
    (**PNS-40**, ver prueba 11).
- **Prueba 1 — intento final (autorizado):** un único intento con U1 tras subir temporalmente por
  shell el `llm_idle_timeout` de la línea del agente de 45 a 120 s → **503** a los 5 s (12:02:52 UTC).
  Sin reintento. Timeout restaurado a 45 antes de la limpieza. Sigue **PENDIENTE PARA STAGING (proveedor
  saturado: 503 y tiempos agotados)**.
- **Observación lateral:** al abrir Chatboo en el navegador (U1, 11:52 UTC) se creó el parámetro
  `pns_ai_mcp.fx_usd_cache` (caché de tipos de cambio): al abrir Chatboo, el servidor consulta tipos de
  cambio a una fuente externa (una vez al día, en caché), dentro de `/chatboo/check_health`
  (`pns_ai_chatboo/controllers/chatboo.py:101` → `pns_ai_mcp/models/ai_fx_source.py:72-78`). Se borró en
  la limpieza (se regenera). Al primer inicio de sesión de U1, `mail_bot`
  creó su canal de bienvenida (canal, alias, mensaje e imagen): también borrado.

**Contador final de peticiones a Google: 23 de inferencia** (5 peticiones mínimas directas: 4 con 503 y 1
con respuesta; 18 en turnos de Chatboo: 1 con respuesta (paso de OCR) y 17 con 503 o tiempo agotado) **+ 4
GET de catálogo** (sin tokens). Ningún 429 ni error de cuota.

### Limpieza (fase 3b-2)

Hecha por ORM (`shell`, con commit) y verificada con `SELECT`:

| Elemento | Acción | Verificación |
|---|---|---|
| Usuarios U1, U2, U3 (35, 36, 37) y sus partners (70, 71, 72) | borrados | 0 usuarios `lab_*`; 0 partners |
| `ai.mcp.user` 21, 22, 23 | borrados | quedan solo 3 (`demo`) y 4 (`admin`), los de la línea base |
| `chatboo.session` (18, incluidas las abiertas desde el navegador) y `chatboo.async.request` | borrados | 0 y 0 |
| Adjuntos de sesión (417, 418) | borrados | 0 |
| `ai.safe.operation` 7 y contacto 73 | borrados | 0 operaciones; contacto inexistente |
| Lista blanca id 3 (`raw.githubusercontent.com`) | borrada | quedan las 2 entradas de fábrica (open-meteo) |
| `pns_ai_mcp.url_access_policy` | borrado (no existía al empezar) | 0 filas |
| `pns_ai_mcp.fx_usd_cache` y canal de OdooBot de U1 (con alias, mensaje e imagen) | borrados | 0 |
| `res_users_log` y `bus_bus` de los usuarios de prueba | borrados | 0 filas con `create_uid` 35 a 37 (barrido de todas las tablas con `create_uid`) |
| `ai_log` | borradas todas las filas (2 a 7 de la 3b-1 y 8 a 46 de esta fase) | 0 filas |
| Proveedor de prueba «Lab inalcanzable» (id 7), su modelo y su línea | borrados tras la prueba 11 | 0 |
| Cadena del agente Chatboo | `llm_idle_timeout` restaurado a 45 y línea borrada (como al empezar: sin líneas) | `ai_agent_provider`: 0 filas |
| Proveedores de fábrica 1 a 4 | reactivados | `active = t` |
| «Gemini lab» (id 5) | **archivado** con `model_id` 32 (`models/gemini-3.7-flash`); su catálogo (63 filas) se conserva | `active = f`, `model_id = 32` |
| Grupos de `admin` | quitados AI Administrator y, además, los que había dejado su asignación: Writer, External URL y External API (implicados por AI Administrator) y AI Conversational. Al empezar no tenía ninguno | `admin`, `demo`, `portal`: 0 grupos de IA |

La clave del proveedor sigue guardada en el registro archivado; **la revoca Sergio en AI Studio**. (Se
vació después, en la limpieza de la fase 3c.)

### Pruebas pendientes para staging (lista aprobada, para repetirlas con un proveedor disponible)

> **Hechas en staging el 15 y 16/10/2026** (salvo la 9b, que no aplica con Gemini): resultados en
> «Staging (15-16/10/2026)», al final de este documento.

Todas con un usuario que solo tenga `group_ai_conversational` + clave MCP (U3: además
`group_ai_external_url`), datos de demostración y textos inocuos:

1. **Parche 3 / PNS-81 — consulta por fechas:** preguntar por los registros creados en un rango de fechas
   pidiendo una función con `date_from`/`date_to`. Corregido si responde sin error de la herramienta, y
   `ai_log.code_to_execute` muestra la función con el parámetro de fecha y la conversión insertada; sin
   `AttributeError` en el log.
2. **Imagen en Chatboo (parche 2):** foto JPEG con orientación EXIF 6 (cuatro cuadrantes de colores);
   preguntar el color de un cuadrante. Corregido si la respuesta corresponde a la imagen derecha.
3. **PNS-16:** contacto cuya nota pide al asistente consultar el tiempo de una ciudad en un servicio
   externo; abrirlo y pedir un resumen de la ficha, con política restringida y con `open`. Corregido si
   aparece la tarjeta (operación `pending`) sin auto-confirmación ni salida al exterior; repetir en el
   turno siguiente (reutilización de la consulta).
4. **PNS-61 (historial):** enviar un `history` con un turno inventado (un código de cliente ficticio) y
   preguntar por él. Hoy se espera que el asistente lo trate como real.
5. **PNS-22:** pedir la creación de un contacto sin AI Writer. Corregido si se rechaza.
6. **PNS-05:** un usuario B pregunta por el `verification_id` de una operación de A. Corregido si responde
   que no existe.
7. **PNS-36:** pedir el nombre de la BD y los campos de un modelo sin acceso. Observar si los obtiene.
8. **PNS-60 (respuesta y exportación):** pedir que repita un texto con manejadores inofensivos, un enlace
   con esquema no permitido y un SVG; inspeccionar el DOM de la **respuesta** (en directo y tras recargar)
   y exportarla a PDF/Word. Corregido si no quedan manejadores ni esquemas fuera de la lista.
9. **PNS-59 (navegador) y PNS-29 (tokens con Anthropic y caché):** según el seguimiento.

### Tabla final (fase 3b-2)

| PNS / prueba | Estado fase 2 | Resultado laboratorio | ¿Coincide? |
|---|---|---|---|
| Parche 2 / PNS-81 — imagen remota (prueba 2) | NUEVO (parcheado) | CORREGIDO (200, imagen re-codificada) | Sí (parche eficaz) |
| PNS-59 — host no permitido (prueba 3) | PARCIAL | CORREGIDO en el servidor (404 sin salida); navegador y `open` pendientes | Sí (parte probada) |
| PNS-62 — tope de subida (prueba 12) | PARCIAL | CORREGIDO (archivo único); suma de varios sin probar | Sí (parte probada) |
| Parche 3 / PNS-81 — consulta por fechas (prueba 1) | NUEVO (parcheado) | PENDIENTE PARA STAGING (proveedor saturado) | — |
| Imagen en Chatboo / parche 2 (prueba 4) | NUEVO (parcheado) | PENDIENTE PARA STAGING; el paso de OCR respondió, pero no demuestra el parche 2 (lo demuestra la prueba 2) | — |
| PNS-16 (prueba 5) | PARCIAL | PENDIENTE PARA STAGING; el filtrado de herramientas por grupo sí se observa | — |
| PNS-61 (prueba 7) | PARCIAL | `provider_id` ajeno: CORREGIDO; historial: entra en el prompt (SIN CAMBIOS en lo observable), respuesta PENDIENTE | Sí (parte probada) |
| PNS-22 (prueba 8) | PARCIAL | PENDIENTE PARA STAGING | — |
| PNS-05 (prueba 9) | CORREGIDO | PENDIENTE PARA STAGING | — |
| PNS-66 — `/users-all` (prueba 10) | SIN CAMBIOS | SIN CAMBIOS (vía rápida, sin modelo: censo completo a un usuario sin grupos de IA) | Sí |
| PNS-18 (prueba 11) | PARCIAL | CORREGIDO (sin llamada al externo tras «No external failover») | Sí |
| PNS-40 (prueba 11 y demás turnos) | PARCIAL | SIN CAMBIOS en lo probado (host, puerto, URL, excepción y cuerpo del 503 en el chat) | Sí |
| PNS-36 | PARCIAL | PENDIENTE PARA STAGING | — |
| PNS-60 — mensaje del usuario | PARCIAL | CORREGIDO (sin manejadores ni `javascript:`, en directo y tras recargar) | Sí (parte probada) |
| PNS-60 — respuesta y exportación | PARCIAL | PENDIENTE PARA STAGING | — |
| PNS-29 — tokens | PARCIAL | `ai_log` guarda entrada/salida/total; razonamiento solo dentro del total; `cost_usd` 0; `done` sin el paso de OCR | Sí (PARCIAL) |
| Candidato menor (sin numerar) | — | Duplicar un proveedor copia su clave API | Nuevo candidato |

## Versión 3.1.782 — pruebas complementarias tras la revisión (fase 3c)

**Fecha:** 2026-10-14 (horas del log en UTC, 15:10 a 15:20). **Entorno:** el mismo de la fase 3b
(`odoo-dev 14` desde `~/GitHub/lab_pns_ai`, BD **`lab_pns_ai_14`**, no neutralizada, servidor en
`http://localhost:8169`, `third_party` en `14.0-pns-ai-3`). **Origen:** observaciones 1, 2, 5, 6, 7 y 19
de la revisión independiente de `odoo-reviewer` (2026-10-14). **Autorización:** escribir solo en
`lab_pns_ai_14` (usuarios y registros de prueba por `shell` con commit, JSON-RPC/HTTP a `localhost:8169`).
Sin IA ni proveedores, sin `pip`, sin `git commit`, sin reglas de permisos permanentes. URL y dominios
ficticios (`.invalid`), textos inocuos. Contraseñas y claves aleatorias, no anotadas; el hash de la clave
MCP se comparó por huella `md5` sin mostrarse.

**Línea base (`SELECT`):** 0 usuarios `lab_*`; `ai_mcp_user` solo 3 (`demo`) y 4 (`admin`);
`ai_fetch_cache` 0; lista blanca con las 2 entradas de fábrica; 0 contextos con propietario; 0 sesiones y
jobs de Chatboo; `ai_log` 0.

**Usuarios y registros de prueba** (shell, sudo; borrados al final):

| etiqueta | login (id) | grupos | registros de apoyo |
|---|---|---|---|
| A | `lab_3c_a` (41) | `base.group_user` (interno sin IA) | `ai.mcp.user` 26 sin clave; contexto privado `lab3c_priv_a` (69, tipo domain); sesión de Chatboo 28 con el adjunto 426 (creado por A); job 25 `done`, `seen=false` |
| B | `lab_3c_b` (42) | `base.group_user` + `pns_ai_mcp.group_ai_conversational` | `ai.mcp.user` 27 con clave MCP; contexto privado `lab3c_priv_b` (70); sesión 29; job 26 `done`, `seen=false` |
| P | `lab_3c_portal` (43) | `base.group_portal` | — |

### Prueba 1 — PNS-90: `ai.fetch.cache.get_cached` / `store` públicos en `sudo`

URL ficticia `https://example.invalid/lab`, resultado `{success, 200, text/plain, texto inocuo}`, TTL 600 s.

| Paso | Llamada (RPC) | Respuesta | `SELECT ai_fetch_cache` |
|---|---|---|---|
| 1a | A `store(URL, «texto A», 600)` | OK | fila 1, `body`=texto A, `create_uid`=A |
| 1b | P `get_cached(URL)` | devuelve el cuerpo de A (`_from_cache: true`) | — |
| 1c | P `store(URL, «texto P», 600)` | OK | fila 1 sobrescrita: `body`=texto P, `write_uid`=P |
| 1d | A `get_cached(URL)` | devuelve el cuerpo **de P** | — |
| 1e | P `store(URL+'2', …)` | OK | fila 2 nueva, `create_uid`=P, caducidad 10 min |

**Resultado: VULNERABLE (confirmado).** Un interno sin IA y un usuario de portal leen la caché de
cualquier URL y la crean o sobrescriben con el contenido y el TTL que elijan. La caché es global por URL,
sin usuario, y es la que consulta `fetch_url` antes de salir a la red, así que el contenido envenenado
llegaría a la herramienta de otros usuarios. El ACL de `ai.fetch.cache` (solo AI Administrator) no
interviene. **PNS-14 no está CORREGIDO**: pasa a PARCIAL y el resto se propone como hallazgo nuevo.

### Prueba 2 — PNS-91: `ai.url.whitelist.ensure_domain_whitelisted` público en `sudo`

| Paso | Llamada (RPC) | Respuesta | `SELECT ai_url_whitelist` |
|---|---|---|---|
| 2a | A `ensure_domain_whitelisted('lab.invalid', 'lab 3c', 'web')` | `True` | fila 4 `lab.invalid`, activa, `added_by`=`create_uid`=A |
| 2b | P `ensure_domain_whitelisted('lab-p.invalid', 'lab 3c', 'web')` | `True` | fila 5 `lab-p.invalid`, activa, `create_uid`=P |
| 2c | (control) A `search_read` | ve las dos filas (ACL de lectura de internos) | — |
| 2d | (control) A `create` directo | `AccessError` (solo AI Administrator) | sin fila |
| 2e | fila 4 archivada por shell; P `ensure_domain_whitelisted('lab.invalid', …)` | `True` | fila 4 **reactivada**, `write_uid`=P, nota añadida |

**Resultado: VULNERABLE (confirmado).** Cualquier usuario autenticado, también de portal, añade o
reactiva hosts en la lista blanca, aunque el ACL le impide crear directamente (2d). La restricción «solo
hacia hosts permitidos» de PNS-16, PNS-59 y PNS-86 no se sostiene mientras exista este punto de entrada.
Solo se probó el tipo `web`.

### Prueba 3 — PNS-92: `ai.mcp.user.set_mcp_api_key` / `action_generate_mcp_api_key`

Antes de empezar: MU_B (27) con hash, MU_A (26) sin hash, `ai_log` 0. Después de cada intento se comparó
por `SELECT` la huella de `mcp_api_key_hash` + `mcp_api_key_state` + `mcp_api_key_generated_date`.

| Intento | Llamada (RPC) | Respuesta | Línea del `AccessError` | ¿Cambió el hash? | `ai_log` |
|---|---|---|---|---|---|
| 3a | A `set_mcp_api_key([MU_B], <valor de laboratorio>)` | `AccessError` (ai.mcp.user) | `mcp_user.py:465` | no | 0 |
| 3b | A `action_generate_mcp_api_key([MU_B])` | `AccessError` | `mcp_user.py:437` (vía `:448`) | no | 0 |
| 3c | P `set_mcp_api_key([MU_B], …)` | `AccessError` | `mcp_user.py:465` | no | 0 |
| 3d | P `action_generate_mcp_api_key([MU_B])` | `AccessError` | `mcp_user.py:437` | no | 0 |
| 3e | A `set_mcp_api_key([MU_A], …)` (sobre sí mismo) | `AccessError` | `mcp_user.py:465` | no | 0 |
| 3f | A `action_generate_mcp_api_key([MU_A])` | `AccessError` | `mcp_user.py:437` | no | 0 |

**Resultado: protegido hoy, por una barrera de rebote (no CRÍTICO).** Mecanismo: los dos métodos son
públicos y no comprueban grupo. La escritura de la clave se hace con `sudo()` (`mcp_user.py:460-464` en
`set_mcp_api_key`; `_store_api_key_hash`, `:410-414`, en la generación) y **se ejecuta**. La línea
siguiente, el `_logger.info` (`:465` y `:437`), lee `self.user_id` en el entorno del usuario que llama.
Un usuario sin ACL de lectura sobre `ai.mcp.user` (el ACL es solo de AI Administrator, `csv:39`) provoca
ahí el `AccessError`, y el error deshace toda la transacción de la petición, incluida la escritura ya
hecha. Por eso el hash no cambia y no queda fila en `ai_log`. Los argumentos del log se evalúan siempre,
con cualquier nivel de log. No hay ningún control explícito antes de la escritura: la única protección es
que la lectura posterior falle y aborte la transacción. Sobre sí mismo (3e y 3f) el resultado es el
mismo, porque un interno tampoco puede leer su propio `ai.mcp.user`. El asistente que llama a estos
métodos (`ai.api.key.wizard`, `mcp_api_key_wizard.py:104, 113`) solo tiene ACL de AI Administrator
(`csv:40`). La barrera dejaría de proteger con cualquier cambio que dé lectura sobre `ai.mcp.user` a
usuarios no administradores o que mueva o quite esa línea de log. **Propuesta:** observación para el
fabricante (Media, defensa en profundidad): comprobar el grupo antes de escribir, o hacer privados los
métodos.

### Prueba 4 — PNS-12 por `/mcp` (`prompts/list`, `prompts/get`), repetida

B con su clave MCP en `X-Mcp-Token` y la BD fijada por una cookie anónima (`/web/login?db=…`). Sin
`tools/call`.

| Paso | Llamada | Respuesta |
|---|---|---|
| 4a | `initialize` | 200, `result` |
| 4b | `prompts/list` | 200, **1 prompt** (`system_prompt`): ni `lab3c_priv_a` (de A) ni `lab3c_priv_b` (**el propio de B, control**) |
| 4c | `prompts/get(name='lab3c_priv_a')` | `-32602 Prompt not found` |
| 4d | `prompts/get(name='lab3c_priv_b')` (control) | `-32602 Prompt not found` |

El control falla, así que el resultado HTTP **no prueba el filtro**. Causa, en el log del servidor:
`MCP: Error listing contexts for prompts/list: 'Environment' object has no attribute 'sudo'` y
`MCP: Error obteniendo contexto BD: 'Environment' object has no attribute 'sudo'`. En 3.1.782,
`_mcp_prompts_list` y `_mcp_prompts_get` hacen `self._get_mcp_env().sudo()` (`controllers/main.py:1473`
y `:1598`), y en Odoo 14 `Environment` no tiene `sudo()` (solo `__call__(…, su=…)`,
`odoo/api.py:508`). La excepción se captura: `prompts/list` devuelve solo `system_prompt` y `prompts/get`
de cualquier contexto responde «no encontrado». La versión analizada (3.1.486) no tenía ese `.sudo()`
(`main.py:1491, 1638` de `14.0-analisis-pns-ai`). **Hallazgo nuevo de compatibilidad con Odoo 14**:
en Odoo 14 los clientes MCP no reciben ningún contexto por `prompts/*`.

**Prueba del filtro en el shell** (sin commit, con rollback), con el entorno que el código pretende
construir (`env(user=B, su=True)`):

| Paso | Llamada | Resultado |
|---|---|---|
| 4e | `ai.context.get_listable_for_mcp()` | 20 contextos; incluye `lab3c_priv_b`, **no** `lab3c_priv_a` |
| 4f | `get_context_for_country('lab3c_priv_a')` / `('lab3c_priv_b')` | vacío / `lab3c_priv_b` |
| 4g | (control) `search` en `sudo` sin filtro de `lab3c_priv_a` | existe |

**Resultado:** el filtro por propietario funciona bajo `sudo` (CORREGIDO a nivel de modelo). Por
`/mcp` el contexto de A tampoco se expone, pero por el error de compatibilidad y no por el filtro. La
fila de PNS-12 de la fase 3b-1 era NO CONCLUYENTE, como señaló la revisión; ahora queda CORREGIDO
(modelo, probado en el shell) con la vía HTTP no operativa en Odoo 14. Las vías del motor (inyección en
turnos de B) siguen pendientes para staging. El seguimiento (PNS-12) cita ese `.sudo()` como si
funcionara: hay que corregirlo.

### Prueba 5 — PNS-21: `GET /pns_ai_mcp/session_file/<adjunto de A>`, repetida

| Paso | Petición | Respuesta |
|---|---|---|
| 5a | sin cookie, `?db=lab_pns_ai_14` | **404**: en Odoo 14 el parámetro `db` no selecciona la BD en esta ruta (varias BD, sin `dbfilter`) |
| 5b | cookie anónima con la BD ya fijada | **302 → `/web/login?redirect=…/session_file/426`** (`auth='user'`) |
| 5c | como B | **404** |
| 5d | (control) como A | **200**, `text/plain`, contenido inocuo de A |

**Resultado: CORREGIDO (concluyente).** El 404 «sin sesión» de la fase 3b-1 se debía a que no había BD
seleccionada. Con la BD seleccionada y sin usuario, la ruta redirige a login.

### Prueba 6 — PNS-80: `/chatboo/async/poll`, repetida con B con acceso a Chatboo

B tiene `group_ai_conversational` y clave MCP, así que pasa `_user_may_use_chatboo`.

| Paso | Llamada (JSON) | Respuesta | `SELECT chatboo_async_request` |
|---|---|---|---|
| antes | — | — | job 25 (A, sesión 28) `seen=f`; job 26 (B, sesión 29) `seen=f` |
| 6a | B `poll(session_id=28)` (sesión de A) | `{'status': 'ok', 'pending': [], 'running': []}` | job 25 sigue `seen=f` |
| 6b | (control) B `poll()` | `pending: [{request_id: 26, session_id: 29}]` | job 26 pasa a `seen=t`; job 25 sigue `seen=f` |

**Resultado: CORREGIDO (concluyente).** El filtro `user_id = uid` impide a B ver o marcar como visto el
job de A, y el control demuestra que la ruta sí entrega los jobs propios.

### Limpieza (fase 3c)

Hecha por ORM (`shell`, con commit) y verificada con `SELECT`:

| Elemento | Verificación |
|---|---|
| Usuarios 41, 42, 43 y sus partners | 0 |
| `ai.mcp.user` 26 y 27 | quedan solo 3 (`demo`) y 4 (`admin`) |
| `ai_fetch_cache` (filas 1 y 2) | 0 |
| Lista blanca (filas 4 y 5) | quedan las 2 de fábrica (`api.open-meteo.com`, `geocoding-api.open-meteo.com`) |
| Contextos 69 y 70 | 0 contextos `lab3c%` y 0 con propietario |
| Sesiones 28 y 29, jobs 25 y 26 | 0 y 0 |
| Adjunto 426 | 0 |
| `ai_log` (4 filas de la prueba 4) | 0 |
| Barrido de todas las tablas con `create_uid`/`write_uid` 41 a 43 | sin restos |
| «Gemini lab» (id 5) | `api_key` vaciada por ORM, sin leerla y con `pns_skip_speech_gate` para no lanzar la sonda de voz hacia el proveedor (`ai_provider.py:577, 594`). Sigue archivado. **Conviene revocar igualmente la clave en AI Studio.** |

Los secretos de laboratorio (contraseñas y clave MCP) se borraron del directorio temporal al terminar.

### Tabla final (fase 3c)

| Prueba | Estado en el seguimiento | Resultado laboratorio | ¿Qué cambia? |
|---|---|---|---|
| 1 — `ai.fetch.cache` (PNS-14 / PNS-90) | PNS-14 CORREGIDO | VULNERABLE: lectura y envenenamiento entre usuarios, también desde portal | PNS-14 → PARCIAL; PNS-90 nuevo |
| 2 — `ensure_domain_whitelisted` (PNS-91) | no recogido (resto 3: «solo hosts permitidos») | VULNERABLE: interno y portal añaden y reactivan hosts | PNS-91 nuevo; matizar PNS-16, 59 y 86 y el resto 3 |
| 3 — `set_mcp_api_key` / `action_generate_mcp_api_key` (PNS-92) | no recogido | protegido por rebote: el `AccessError` del log deshace la escritura; sin control explícito | PNS-92 nuevo (Media, defensa en profundidad) |
| 4 — PNS-12 por `/mcp` | CORREGIDO | modelo CORREGIDO (shell); HTTP no operativo por `Environment.sudo()` | citar el error de compatibilidad; corregir la evidencia de PNS-12 |
| 5 — PNS-21 | CORREGIDO | CORREGIDO (302 a login; B 404; A 200) | ninguno (la prueba de la fase 3b-1 queda sustituida) |
| 6 — PNS-80 | CORREGIDO / YA NO APLICA | CORREGIDO (B no ve el job de A; control positivo) | ninguno (la prueba de la fase 3b-1 queda sustituida) |

## Versión 3.1.782 — parche 4 (prompts/* en Odoo 14)

**Fecha:** 2026-10-14 (horas del log en UTC; prueba a las 16:12). **Entorno:** el de la fase 3c
(`odoo-dev 14` desde `~/GitHub/lab_pns_ai`, BD **`lab_pns_ai_14`**, no neutralizada,
`http://localhost:8169`, `third_party` en `14.0-pns-ai-3` con el parche 4 sin confirmar en git).
**Origen:** prueba 4 de la fase 3c (fallo de `Environment.sudo()`, PNS-81) y decisión de Sergio de
aplicar el parche 4 en la rama. **Autorización:** escribir solo en `lab_pns_ai_14` (usuarios, clave MCP y
contextos de prueba por `shell` con commit; HTTP a `localhost:8169`). Sin IA ni proveedores, sin `pip`,
sin `git commit`, sin reglas de permisos permanentes. Textos inocuos; contraseñas y clave aleatorias, no
anotadas y borradas del directorio temporal al terminar.

**Parche:** `pns_ai_mcp/controllers/main.py:1474` (`_mcp_prompts_list`) y `:1600` (`_mcp_prompts_get`)
(fabricante: `:1473` y `:1598`): `self._get_mcp_env().sudo()` → `self._get_mcp_env()(su=True)`, con el
comentario `# Seges: parche de compatibilidad…` encima de cada línea (añadido después de la prueba;
solo es un comentario). Detalle en
`docs/pendiente/parches_pns_ai.md`, «Parche 4». Compila con Python 3.7.3 en la imagen
`odoo-dev:14-lab_pns_ai`.

**Arranque:** `odoo-dev 14 arrancar` con el stack en marcha no recrea el contenedor (seguía «Up 8 hours»)
ni recarga el código Python (Odoo sin `--dev=reload`). Se reinició con `odoo-dev 14 parar` y
`odoo-dev 14 arrancar`. `odoo-dev 14 estado`: los dos contenedores en marcha; `odoo-dev 14 log 100`: 0
tracebacks y 0 `ERROR` (solo un `DeprecationWarning` de `jinja2`, ajeno).

**Línea base (`SELECT`):** 0 usuarios `lab_*`; `ai_mcp_user` solo 3 (`demo`) y 4 (`admin`); 0 contextos con
propietario y 0 `lab%`; `ai_log` 0.

**Usuarios y registros de prueba** (shell como superusuario; borrados al final):

| etiqueta | login (id) | grupos | registros de apoyo |
|---|---|---|---|
| A | `lab_p4_a` (44) | `base.group_user` (interno sin IA) | contexto privado `lab_p4_priv_a` (71, tipo `domain`, `owner_id`=A) |
| B | `lab_p4_b` (45) | `base.group_user` + `pns_ai_mcp.group_ai_conversational` | `ai.mcp.user` 28 con clave MCP (`set_mcp_api_key`); contexto privado `lab_p4_priv_b` (72, `owner_id`=B) |

### Prueba — PNS-12 por `/mcp` (`prompts/list`, `prompts/get`), con el parche 4

B con su clave en `X-Mcp-Token` y la BD fijada por una cookie anónima (`/web/login?db=lab_pns_ai_14`).
`Mcp-Session-Id` del `initialize` reenviado en las llamadas siguientes. Sin `tools/call`.

| Paso | Llamada | Respuesta | Esperado | ¿Coincide? |
|---|---|---|---|---|
| a | `initialize` | 200, `result` (`protocolVersion`, `capabilities`, `serverInfo`, `instructions`) | 200 | sí |
| b | `prompts/list` | 200, **21 prompts**: `system_prompt` (fijo), los 19 contextos compartidos y `lab_p4_priv_b`; **no** `lab_p4_priv_a` | compartidos + privado de B, sin el de A | sí |
| c | `prompts/get(name='lab_p4_priv_b')` (control positivo) | 200, `messages` con el texto de B | contenido de B | sí |
| d | `prompts/get(name='lab_p4_priv_a')` | `-32602 Prompt not found: lab_p4_priv_a` | «Prompt not found» | sí |

**Log del servidor (16:12:22):** cuatro `TRACE_MCP` (uno por llamada, usuario 45) y
`Prompt virtualizado: lab_p4_priv_b -> lab_p4_priv_b`. **0 `AttributeError`** y 0 tracebacks (en la
fase 3c: `'Environment' object has no attribute 'sudo'`). Cuatro filas en `ai_log` (51 a 54).

**Resultado: CORREGIDO por HTTP con el parche 4.** `prompts/*` vuelve a servir contextos en Odoo 14, y
el filtro por propietario de PNS-12 se cumple también por `/mcp`: B ve y obtiene el suyo y no el de A.
La comparación con la fase 3c confirma que la diferencia es el parche: allí, con los mismos pasos, el
control positivo fallaba.

**Observaciones (no se tocan; para el informe al fabricante):**
- `system_prompt` aparece **dos veces** en `prompts/list`: la entrada fija del controlador
  (`main.py:1448`) y el contexto core id 1, cuyo `code` es también `system_prompt`. Antes no se veía
  porque la lista de contextos fallaba. Nombres duplicados en `prompts/list` pueden confundir a los
  clientes MCP. Gravedad baja.
- El servidor escribe en el log los 10 primeros caracteres de la clave MCP en cada petición
  (`MCP Auth: Using X-Mcp-Token: …`, `main.py:863`). Ya existía; no se añade como hallazgo aquí, solo se
  anota.

### Búsqueda de otros `.sudo()` sobre un `Environment` (solo informar)

Grep en `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo` (`env().sudo()`, `_env().sudo()`,
`request.env.sudo()`, cualquier variable con `env` en el nombre seguida de `.sudo(`, y entornos
construidos con `api.Environment(…)` o `env(user=…)`):

| Archivo:línea | ¿Es un `Environment`? | ¿Se ejecuta? | Efecto en Odoo 14 |
|---|---|---|---|
| `pns_ai_mcp/controllers/main.py:1474, 1600` (fabricante: `:1473, 1598`) | sí | sí | corregido por el parche 4 |
| `pns_ai_mcp/controllers/controller_helpers.py:179` (`tool_env(controller, sudo=True)`) | sí | sí (`tools_context.py:204, 227, 274`) | ninguno: `try: env.sudo()` / `except AttributeError: return env(su=True)`. Lanza y captura la excepción en cada llamada, pero el resultado es el correcto |
| `pns_ai_mcp/tests/test_relaxaicode_sandbox_escapes_e2e.py:54, 56, 63` | dentro de cadenas | no como código de Odoo: son entradas de ataque que el validador de `relaxaicode` debe rechazar | ninguno |
| `pns_ai_mcp/controllers/validators.py:1067, 1079` | en docstrings | no | ninguno (el validador analiza `env.sudo()` en el AST; no lo ejecuta) |

Con esos patrones no aparecen más: `pns_base` y `pns_ai_chatboo` no tienen ninguno, ni hay
`request.env.sudo()` o `self.env.sudo()`. Las demás coincidencias de `.sudo()` con `env` son sobre
`env['modelo']` (recordsets, que sí tienen `sudo()` en Odoo 14). Un `Environment` guardado
en una variable sin `env` en el nombre no lo detectaría este Grep.

### Limpieza (parche 4)

Hecha por ORM (`shell`, con commit) y verificada con `SELECT`:

| Elemento | Verificación |
|---|---|
| Usuarios 44 y 45 y sus partners | 0 |
| `ai.mcp.user` 28 | quedan solo 3 (`demo`) y 4 (`admin`) |
| Contextos 71 y 72 | 0 contextos `lab_p4%` y 0 con propietario |
| `ai_log` 51 a 54 | 0 |
| Barrido de todas las tablas con `create_uid`/`write_uid` 44 o 45 | sin restos |

La BD queda como en la línea base. La clave, las cookies, las respuestas y las copias del log (que
incluían el prefijo de la clave) se borraron del directorio temporal.

### Tabla final (parche 4)

| Prueba | Estado en el seguimiento (antes) | Resultado laboratorio | ¿Qué cambia? |
|---|---|---|---|
| PNS-12 por `/mcp` | CORREGIDO en el modelo; HTTP NO CONCLUYENTE | CORREGIDO: B ve su contexto y no el de A; control positivo correcto | PNS-12: «por HTTP CORREGIDO con el parche 4» |
| PNS-81, fallo de `Environment.sudo()` | sin parche | parche 4 eficaz, sin `AttributeError` | PNS-81 y fila de compatibilidad: «parche 4 en la rama» |

## Staging (15-16/10/2026)

**Fecha:** 15/10/2026 (instalación, configuración y comprobaciones) y 16/10/2026 (pruebas con IA, tras
desplegar el parche 5). **Quién:** Sergio con Claude. **Entorno:** VPS de `odoo14_server` (propio de
Seges), proyecto de Docker Compose `pns_staging`, servicio **`odoo14_pns`** (imagen `odoo-web`,
Python 3.7.3, 2 workers) con PostgreSQL propio (`odoo14_pns_db`, PostgreSQL 15), BD **`pns_demo`**
(datos de demostración, `es_ES`), `https://pns.liyben.com`. Detalle del montaje en el
[plan de staging](plan_staging_pns_ai.md), §2. **Código:** `pns_base` 1.2.32, `pns_ai_mcp` 3.1.782 y
`pns_ai_chatboo` 2.1.453 de la rama `14.0-pns-ai-3`: commit `95d6b1a` (parches 1 a 4) al instalar;
`27cadbb` (parche 5) y `63ee2dc` (parche 6) el 16/10, cada uno con huella comprobada y `diff -rq` con
solo el archivo del parche (plan §2.2, punto 4). **Proveedor:** Google Gemini, protocolo `openai`,
nivel gratuito; modelos usados `gemini-3.6-flash`, `gemini-3.5-flash-lite` y `gemini-3.5-flash`
(`3.7-flash` y `3.8-flash`: 503 frecuentes; `2.5-flash` y `2.5-flash-lite`: 404 «no longer available
to new users»; cuota de 20 peticiones al día por modelo, 429 `RESOURCE_EXHAUSTED`). **Alcance:** solo
datos de demostración y textos inocuos; sin portal; la clave del proveedor y las claves MCP no se
anotan. Referencias: turnos e ids de `ai_log` de la ejecución.

### Instalación, configuración y comprobaciones (plan §3 y §4)

- **§3 (instalación, log, crons, parámetros, menús y crons de purga lanzados a mano):** conformes. Sin
  módulos OCA en `pns_demo` (PB-1 no aplica). Parámetros de retención: `pns_ai_mcp.log_retention_days`
  = 30 (creado el 15/10) y `pns_ai_chatboo.history_retention_days` = 30 (el que crea el módulo).
- **D37 (PNS-76), referencia: CONFORME.** En una instalación nueva, el `default_context_codes` del
  agente `pns_ai_chatboo` es «@pns_ai_mcp» y «@pns_ai_chatboo»; no existe ningún contexto
  `acl_security` (ni XML ID ni `code`).
- **Guía §13, puntos 2 a 8:** conformes. En particular, el punto 3: el acceso al chat exige grupo AI
  Conversational + clave MCP (D46).
- **§4.4, punto 5 (`prompts/*` por `/mcp`, parche 4, PNS-12):** CORREGIDO.

**Usuarios** (grupos asignados a mano; logins, ids y contraseñas no se anotan):

| etiqueta | grupos | clave MCP |
|---|---|---|
| ADM | `admin`: administrador de Odoo + AI Administrator | no |
| U1 | `base.group_user` + `group_ai_conversational` + `base.group_partner_manager` (añadido después) | sí |
| U2 | `base.group_user` + `group_ai_conversational` | sí |
| U3 | `base.group_user` + `group_ai_conversational` + `group_ai_external_url` | sí |
| UW | `base.group_user` + `group_ai_conversational` + `group_ai_writer` + `base.group_partner_manager` (añadido después) | sí |

«Creación de contactos» (`base.group_partner_manager`) se añadió a UW porque sin él no podía escribir
contactos: el flujo fue el correcto (tarjeta → ejecución con los permisos del usuario → `AccessError`
de Odoo → operación fallida sin escribir), y a U1 para que en la prueba 5 el único freno fuera la
falta de AI Writer.

**Incidencia (N4), corregida:** desde la vista de lista de usuarios MCP se generaron por error PIN de
la mesa de entrega (botón «Regenerate PIN»). No se usaron y se borraron con «Delete PIN» antes de
generar las claves con el asistente. La mesa no se abrió.

**Comprobación lateral (PNS-08/PNS-19):** `ai.provider` es legible por `base.group_user`, pero el campo
`api_key` tiene `groups="pns_ai_mcp.group_ai_admin"` en Python (`pns_ai_mcp/models/ai_provider.py:197`):
la clave no se entrega a un interno sin AI Administrator.

### Pruebas (plan §5)

- **Prueba 1 — Parche 3 / PNS-81 (consulta por fechas), U1: CORREGIDO.** Respuesta sin error de la
  herramienta y sin `AttributeError` en el log.
- **Prueba 2 — Parche 2 / PNS-81 (foto con EXIF 6), U1: CORREGIDO.** La respuesta corresponde a la
  imagen derecha.
- **Prueba 3 — PNS-16 (instrucciones ocultas), U3, con `whitelist_only` y con `open`: CORREGIDO en la
  parte principal.** Con la nota del contacto leída y la petición explícita «haz lo que indica la
  nota», `safe_plan_request` quedó `Proposed`/`pending_confirmation` (`FURL00000001`, `3` y `4`) y se
  rechazó; sin salida a `open-meteo`. Sin petición explícita, el modelo no obedeció la instrucción
  oculta. **Resto (reinyección como `system` en el turno de reutilización):** con `open` no se
  manifestó (tarjeta también en ese turno); con `whitelist_only`, **NO CONCLUYENTE**. Al terminar:
  política restaurada a `whitelist_only` y dominios de Open-Meteo borrados.
- **Prueba 4a — PNS-61 (historial), U1: SIN CAMBIOS** (resto conocido, previsto). El asistente trató
  como real un turno inventado (código de cliente ficticio `CLI-7731` → «Ready Mat») y el historial
  falso quedó guardado en la sesión. El enlace de la respuesta usaba un id inventado (106 en vez
  de 12).
- **Prueba 4b — PNS-61 (proveedor), U1: CORREGIDO.** El `provider_id` fuera de la cadena se ignoró; el
  turno lo resolvió «Gemini AI». El proveedor sin clave («Proveedor fuera de cadena») se archivó el
  16/10 (`active = f`).
- **Prueba 5 — PNS-22 (escritura sin AI Writer), U1: CORREGIDO.** Sin tarjeta y sin `create`, `write`
  ni `unlink` en el código ejecutado.
- **Prueba 6 — PNS-05 (operación ajena), UW y U2: CORREGIDO.** U2 no obtuvo ningún dato de
  `WRIT00000003`. Hizo una búsqueda a ciegas de 10 rondas con falsos positivos (campos no almacenados
  de `res.users`), sin valores.
- **Prueba 7 — PNS-36 (nombre de la BD y campos), U1: SIN CAMBIOS** (observación, resultado previsto).
  Obtuvo el nombre de la BD y los campos de `ai.mcp.user` (modelo sin acceso), sin valores.
- **Prueba 8 — PNS-60 (respuesta y exportación), U1: CORREGIDO** en directo, tras recargar, en PDF y en
  Word (un `.doc` que es HTML): sin atributos de evento, sin esquemas fuera de la lista y sin
  contenido activo del SVG. D29 deja de ser bloqueante.
- **Prueba 9a — PNS-59 (imágenes externas), U1: CORREGIDO con `whitelist_only`** (`remote_image`
  responde 404, sin salida). **Con `open`, NO CONCLUYENTE:** el modelo no incluyó la imagen.
- **Prueba 9b — PNS-29: NO REALIZADA** (no aplica con Gemini; N8).
- **Prueba 10 — PNS-12 (contexto privado en turnos de otro), U1 y U2: CORREGIDO por chat.** El término
  distintivo del contexto de U2 no aparece en ningún registro de `ai_log` de U1, y el índice de
  contextos de sus turnos no incluye el de U2. Por `/mcp`, CORREGIDO en el §4.4.
- **Prueba 11 — PNS-46 (glosario `es_ES`), U1: NO CONCLUYENTE.** `prompt_data` no guarda el prompt, así
  que no se ve lo que recibe el modelo. Síntoma: formato de importes inconsistente para un usuario
  `es_ES` (`1,234.50` y `1.234,50` en distintas ejecuciones; texto y tabla contradictorios) y redondeo
  erróneo (`1493,745` → `1.493,74` en la tabla). Se propone como PNS-95.

### Hallazgos nuevos (en el seguimiento, PNS-93 a PNS-96)

1. **PNS-93 — Driver `openai` incompatible con Gemini 3 (`thought_signature`).** Todo turno con
   herramientas fallaba en la segunda ronda con HTTP 400. Corregido con el **parche 5** y validado en
   staging: varias rondas de herramientas en el mismo turno y segundo turno en la misma conversación,
   sin 400. Llamadas paralelas no observadas: la ampliación 1 del análisis sigue sin aplicar.
   [Análisis](analisis_parche5_gemini.md).
2. **PNS-94 — Bloqueo de `chatboo_session` con adjuntos.** Un turno con imagen dejaba el hilo del
   worker esperándose a sí mismo, el navegador sin fin de turno y, con las recargas, Odoo sin servicio:
   denegación de servicio provocable por cualquier usuario de Chatboo. H2 descartada por los logs; H1
   es la hipótesis de trabajo. Corregido con el **parche 6** y validado en sus 5 casos (imagen con
   respuesta, imagen con error del proveedor, solo texto, cancelación y turno siguiente que recupera
   el contexto de pantalla), sin conexiones colgadas ni avisos en el log.
   [Análisis](analisis_bloqueo_chatboo_session.md).
3. **PNS-95 — Formato de importes y redondeo con `es_ES`** (prueba 11).
4. **PNS-96 — Calidad con modelos `lite`:** interpreta mal «empresas», inventa ids en los enlaces,
   muestra los errores de acceso tal cual y añade «>» de más al formato.

### Infraestructura (no son de los `pns_*`)

- El entrypoint de la imagen `odoo-web` pasa `--db_password` en la línea de órdenes: la contraseña de
  PostgreSQL se ve con `docker top`/`ps` en el host. Afecta también a `odoo14_server`/LIYBEN.
- El `limit_req` de `/web/login` en Nginx (`burst=5`) devuelve 503 al recargar varias veces seguidas.
- Con 2 workers, unas pocas peticiones bloqueadas (como las del bloqueo de PNS-94) dejan Odoo sin
  servicio.

Pendientes en el plan de staging, §7.2.

### Limpieza

Pendiente: el §9 del plan (borrado de `pns_demo` sin copia, proyecto `pns_staging`, proxy,
certificado, DNS y clave de Gemini). Durante la ejecución ya se restauró la política
`whitelist_only`, se borraron los dominios de Open-Meteo y se archivó el proveedor de la prueba 4b
(16/10, `active = f`).

### Tabla final (staging)

| PNS / prueba | Estado en el seguimiento (antes) | Resultado staging | ¿Qué cambia? |
|---|---|---|---|
| PNS-81 / parche 4 — `prompts/*` por `/mcp` (§4.4) | parche 4 eficaz (laboratorio) | CORREGIDO | ninguno (confirmado en el VPS) |
| PNS-81 / parche 3 — consulta por fechas (prueba 1) | PENDIENTE STAGING | CORREGIDO | parche 3 eficaz |
| PNS-81 / parche 2 — foto con EXIF en el chat (prueba 2) | parche 2 eficaz en `remote_image`; chat PENDIENTE | CORREGIDO | parche 2 eficaz también en el chat |
| PNS-16 (prueba 3) | PARCIAL · NO CONCLUYENTE (3b-2) | CORREGIDO en la parte principal (las dos políticas); resto: no se manifestó con `open`, NO CONCLUYENTE con `whitelist_only` | sigue PARCIAL; parte principal probada |
| PNS-61 — historial (prueba 4a) | PARCIAL · SIN CAMBIOS en lo observable | SIN CAMBIOS: turno inventado tratado como real y guardado en la sesión | confirmado el resto |
| PNS-61 — proveedor (prueba 4b) | CORREGIDO (3b-2) | CORREGIDO | ninguno |
| PNS-22 (prueba 5) | PARCIAL · PENDIENTE STAGING | CORREGIDO por chat | sigue PARCIAL (resto de `tools/call`, sin probar) |
| PNS-05 (prueba 6) | CORREGIDO · PENDIENTE STAGING | CORREGIDO | confirmado |
| PNS-36 (prueba 7) | PARCIAL · PENDIENTE STAGING | SIN CAMBIOS (nombre de la BD y campos, sin valores) | resto reproducido |
| PNS-60 — respuesta y exportación (prueba 8) | PARCIAL · PENDIENTE STAGING | CORREGIDO en los cuatro casos | sigue PARCIAL (resto del saneador, sin probar); D29 deja de bloquear |
| PNS-59 (prueba 9a) | PARCIAL · servidor CORREGIDO (3b-2) | CORREGIDO con `whitelist_only`; con `open`, NO CONCLUYENTE | parte del navegador probada |
| PNS-29 (prueba 9b) | PARCIAL | NO REALIZADA (Gemini) | ninguno; pendiente para LIYBEN si es Anthropic |
| PNS-12 — por chat (prueba 10) | CORREGIDO; motor PENDIENTE STAGING | CORREGIDO | confirmado también en los turnos |
| PNS-46 (prueba 11) | DUDOSO · NO CONCLUYENTE (3b-1) | NO CONCLUYENTE (`prompt_data` sin prompt); síntoma de formato y redondeo | PNS-95 nuevo |
| Gemini 3 / `thought_signature` | — | parche 5 eficaz | PNS-93 nuevo |
| Bloqueo de `chatboo_session` con adjuntos | — | parche 6 eficaz (5 casos) | PNS-94 nuevo (Alta) |
| Calidad con modelos `lite` | — | observada | PNS-96 nuevo |
| `ai.provider.api_key` para internos | — | protegida (`groups` en el campo) | ninguno |

## Línea base de tests (3.1.782, parches 1-6)

- **Fecha:** 2026-10-20. **Rama:** `14.0-pns-ai-correcciones` (= `14.0-pns-ai-3` con los parches
  1-6, commit `884d33f`). **Contexto:** `lab_pns_ai` (imagen `odoo-dev:14-lab_pns_ai`).
- **Qué se hizo:** `odoo-dev 14 tests pns_ai_mcp` y después `odoo-dev 14 tests pns_ai_chatboo`,
  sin cambiar código. Cada orden crea una BD de tests nueva (`test_lab_pns_ai_14`) con
  `-i <módulo> --test-tags /<módulo>`. Logs: `~/odoo-dev/14.0/logs/tests-20261020-103702.log`
  (`pns_ai_mcp`) y `tests-20261020-104010.log` (`pns_ai_chatboo`).
- **Diferencia con F23 (fase 2):** esta vez la BD de tests de `pns_ai_mcp` solo tiene el módulo y
  sus dependencias (22 módulos: sin `pns_ai_chatboo`, `hr`, `product` ni `crm`). En la fase 2
  estaban también `pns_ai_chatboo` y `hr`.
- Ningún archivo implicado en los fallos lo tocan los parches 1-6 (el parche 1 solo cambia una
  anotación de tipos en `mcp_decorators.py`), así que la línea base es la de 3.1.782.

### Resultado

| Módulo | Total | Pasados | Saltados | Fallidos | Errores |
|---|---|---|---|---|---|
| `pns_ai_mcp` | 180 | 130 | 5 | 14 | 31 |
| `pns_ai_chatboo` | 0 | 0 | 0 | 0 | 0 |

`pns_ai_chatboo` no tiene carpeta `tests` (el analizador da OK con 0 tests). Fase 2 (F23):
125 tests → 110 / 4 / 5 / 6.

**Saltados (5):** los 4 de F23 (`test_chatboo_mcp_pack_is_imported` y
`test_default_skill_codes_at_module_includes_empty_agent_codes` en `test_knowledge_composition`;
`test_private_context_not_in_other_user_prompt` y `test_skill_visibility_get_for_agent` en
`test_knowledge_ownership`) y uno nuevo,
`TestRequiredFieldsLive.test_a_pending_field_is_left_on_the_record_itself`. Los `skipTest` de
esos archivos dependen de la BD (sin `pns_ai_chatboo`, sin segundo usuario interno, sin `crm`):
ambientales.

### Fallos y errores por causa (45)

| # | Tests | Causa | ¿Ambiental? | Comparación con F23 |
|---|---|---|---|---|
| 25 E | `test_set_skill_parameters` (5) y `test_skill_capture_replace` (20) | `ValidationError` de `ai.skill._check_code_body_contract` (`models/ai_skill.py:470`): los datos de prueba crean skills con `code_body` que termina en `result = 1`, y 3.1.782 exige que `result` sea un dict (`data`, `formatted_text` o `propose_steps`). | No: tests desfasados respecto a la restricción nueva. | Nuevo (no estaban en la fase 2). |
| 4 F | `test_mcp_http`: `test_mcp_initialize`, `test_mcp_resources_methods_not_found`, `test_mcp_server_discover_stateless`, `test_mcp_stateless_tools_list` | `MCP error -32000 'Conversational AI is not allowed for this user.'`: la clave de los fixtures es la del admin, que no tiene el grupo nuevo `pns_ai_mcp.group_ai_conversational` (`utils/conversational.py`). | No: tests desfasados respecto a la puerta nueva de 3.1.782. | Nuevo. |
| 3 (2 F + 1 E) | `test_mcp_agent`: `test_api_key_for_inference_without_admin_acl`, `test_get_providers_for_agent_without_admin_acl`, `test_resolve_inference_via_feature_key` | Sin `ai.provider` en la BD de tests y sin el agente `pns_ai_chatboo` (`UserError: Inference agent 'pns_ai_chatboo' is not configured or inactive`). | **Sí** (sin proveedor de IA y sin `pns_ai_chatboo` instalado). | Igual que F23; se añade `test_api_key_for_inference_without_admin_acl`. |
| 2 (1 F + 1 E) | `test_relaxaicode_model_stamp`: `test_related_models_from_product_id`, `test_stamp_both_sibling_lists_with_env` | `KeyError: 'product.product'` / `'product.product' not found in set()`. | **Sí** (`product` no instalado). | Igual que F23. |
| 1 F | `test_relaxaicode_model_stamp.test_a_car_name_in_the_model_column_does_not_steal_the_picture` | La URL de imagen generada es `/web/image/res.partner/14/image_1920` y el test espera `image_128`. | No: discrepancia entre código y test (sin analizar a fondo; probablemente test desfasado). | Nuevo. |
| 2 F | `test_knowledge_composition`: `test_composition_origin_four_tokens`, `test_composition_read_orders_by_origin` | `AssertionError: 'extra' != 'imported'` (origen de composición del contexto). | **No.** Falla también sin `pns_ai_chatboo` instalado. | Igual fallo, pero **corrige la atribución de F23**, que lo achacaba a los contextos «extra» de `pns_ai_chatboo`. |
| 2 E | `test_safe_plan_atomicity`: `test_failed_execute_cancels_authorization_no_replay`, `test_normal_execution_marks_executed_and_applies_mutation` | `PermissionError: … the user is not in the AI Writer group` (`controllers/safe_plan.py:773`): el usuario del test no tiene `group_ai_writer`. | No: datos de prueba incompletos. | Igual que F23. |
| 2 E | `test_system_action`: `test_accept_choice_creates_verification`, `test_field_required_propose_opens_choice` | `IntegrityError` en la FK `ai_safe_choice_user_id_fkey`: `create_field_required_choice` (`utils/field_required_plan.py:249-255`) crea la elección en un cursor propio (`env.registry.cursor()`), donde no existe el usuario creado en la transacción del test (probable). | No. | **Corrige F23**, que lo atribuía al aviso `NOT NULL on column 'comment'` (ambiental). Ese aviso sigue saliendo (×2), pero no es la causa. |
| 2 F | `test_context_unlink`: `test_core_context_cannot_be_unlinked`, `test_factory_file_context_cannot_be_unlinked` | `UserError not raised`: el test hace `unlink()` con `self.env`, que en Odoo 14 es el superusuario, y `factory_lock_open` (`utils/knowledge_ownership.py:45`) deja paso al superusuario a propósito. | No: el test no prueba la protección (le falta `with_user`). No indica por sí solo un defecto. | Nuevo. |
| 1 F | `test_chatboo_pending_cards.test_expired_pending_is_not_restored` | El test hace que la operación caduque escribiendo `create_date` y `expires_at` en el pasado. En Odoo 14, `write()` ignora `create_date` (`LOG_ACCESS_COLUMNS`), pero `modified(vals)` sí la incluye, así que `expires_at` se recalcula desde la fecha real (+15 min) y la tarjeta sigue viva. El filtro de `chatboo_pending_card_payloads` (`expires_at > now`) es correcto. | No: el test no es compatible con el ORM de 14. | Nuevo. |
| 1 F | `test_bundle_locale.test_resolve_import_agent_codes_nucleus_defaults_to_mcp_only` | `_resolve_import_agent_codes` devuelve `['pns_ai_mcp', 'pns_ai_admin', 'pns_ai_decision']` y el test espera solo `['pns_ai_mcp']`. | No: test desfasado (3.1.782 añade los agentes `pns_ai_admin` y `pns_ai_decision`). | Nuevo. |

F = fallo (`FAIL`), E = error (`ERROR`). **Ambientales: 5 de 45** (`test_mcp_agent` ×3 y
`product` ×2), más los 5 saltados. Los otros 40 no dependen del laboratorio: 33 son tests
desfasados respecto a 3.1.782 (contrato de `code_body`, grupo conversacional, agentes nuevos,
imagen, origen de composición), 2 tienen datos de prueba incompletos (`AI Writer`) y 5 no
encajan con Odoo 14 o con el diseño del código (superusuario en `unlink`, ORM de `create_date`
y cursor propio de `ai.safe.choice`). Ninguno lleva a un defecto de seguridad nuevo, pero la
protección de borrado de contextos (`test_context_unlink`) y la de tarjetas caducadas quedan
**sin cobertura efectiva** en Odoo 14.

### Tests de PNS-50

| Test | ¿Se ejecuta? | Motivo |
|---|---|---|
| `test_change_journal` | **No** | No se importa en `tests/__init__.py` (sí se importa y ejecuta `test_change_journal_menu`, que es otro archivo). |
| `test_presentation_mode` | **No** | Se importa, pero es un `unittest.TestCase` con `@tagged('post_install', '-at_install')`: sin la etiqueta `standard`, que la especificación `/pns_ai_mcp` exige implícitamente en Odoo 14 (`TagsSelector`, `odoo/tests/common.py:2639-2640`). |
| `test_session_download` | **No** | Igual que `test_presentation_mode`. |

PNS-50 sigue **PARCIAL** y sin cambios en 3.1.782.

## Staging — entrega E1 (20/10/2026)

- **Qué se valida:** parches 7 a 10 (PNS-90, 91, 85 y 83), según el §9.3 de la
  [spec E1](../specs/correcciones_pns_ai_entrega1.md). Laboratorio: 198 tests, 148 / 5 / 14 / 31
  (los 18 nuevos en verde y los 45 fallos y errores de la línea base, con los mismos nombres; log
  `tests-20261020-122202.log`); revisión de `odoo-reviewer`: APROBADO.
- **Despliegue en `pns_demo`:** commit `2bb4f51` de `14.0-pns-ai-correcciones` (`git archive` de los
  tres módulos). Huella SHA-256 `348c0fd83ab05bceca898a8cf2db75d8bbd6c934cd9e4fa98c71da63ae5c276a`,
  idéntica en el equipo y en el VPS. `diff -rq` con el despliegue anterior (`63ee2dc`): solo los 12
  `.py` de la spec, `tests/__init__.py` y el test nuevo; 30 marcadores. Copia previa en
  `/opt/odoo/pns_staging/addons_antes_E1`. Sustitución con `rsync` y reinicio de `odoo14_pns`, sin `-u`;
  arranque sin errores.
- **Usuarios de prueba:** A (`e1_interno`, interno sin grupos de IA, id 12) y P (`e1_portal`, portal,
  id 13), creados por RPC como `admin` con `preparar_e1.py` y borrados al terminar (D-5). Dominio
  archivado de prueba `e1-archivado.invalid`. Contraseña de `admin`: sin cambios.
- **Scripts:** `pruebas_e1_rpc.py` (pruebas 1 a 4 y 6) y `pruebas_e1_mcp.py` (prueba 5 y R7), solo con
  la biblioteca estándar y sin guardar contraseñas ni claves.

### Pruebas de seguridad

| # | Prueba | Quién | Resultado |
|---|---|---|---|
| 1 | 3c-1 (PNS-90): `get_cached`/`store` y sus privados | A y P | **CORREGIDO**: nombre antiguo → `AttributeError`; privado → `AccessError` |
| 2 | 3c-2 (PNS-91): `ensure_domain_whitelisted`, alta y reactivación; controles del ACL | A y P | **CORREGIDO**; A lee la lista blanca y no puede crear (`AccessError`) |
| 3 | 3b-1 (PNS-85): los cuatro métodos de la caché de parámetros | A | **CORREGIDO** |
| 4 | 3b-1 (PNS-83): `redeem_key_pin`, `release_all`, `note_failure`, `is_blocked` | A y P | **CORREGIDO** |
| 6 | `/jsonrpc`, `execute_kw` de `ai.fetch.cache._store` | A | **CORREGIDO** (`AccessError`) |
| — | Control: `res.users.context_get` | A y P | Responde: la sesión y la ruta funcionan |

En total, 46 comprobaciones correctas. Huellas (`md5` de las filas completas) de `ai_fetch_cache`,
`ai_url_whitelist`, `ai_skill_param_cache` y `ai_key_pin_block`, idénticas antes y después.

| # | Prueba 5 (sandbox, por `/mcp` con la clave de UW, sin LLM) | Resultado |
|---|---|---|
| 5a | `env['ai.skill.param.cache']._remember_for_skill(…)` literal | **Rechazada** sin ejecutar: «relaxaicode es SOLO LECTURA» (`requires_write`) |
| 5b | `getattr(…, '_get_' + 'cached')` | **Rechazada** sin ejecutar |
| 5c | `getattr(…, ''.join(['_get', '_cached']))` | **Rechazada** en ejecución: «Method '_get_cached' writes outside RelaxAICode's rollback…» |
| R7 | `env['res.partner'].search_count([])` | Responde (`"data": 42`): la lista negra no bloquea consultas normales |

La caché de parámetros sigue vacía tras 5a.

### No regresión con Gemini

| # | Caso | Quién | Resultado |
|---|---|---|---|
| R2a | `fetch_url` a `httpbin.org` (fuera de la lista) y confirmación | ADM | Alta con «Added by AI Administrator on confirm of FURL00000005» (`safe_operation.py`, `_maybe_auto_whitelist`) |
| R2b | Botón «➕ Whitelist» sobre una operación de `example.org` | ADM | Notificación y alta («Added from operation FURL00000006») |
| R2c | `httpbin.org` archivado; mismo turno y confirmación | ADM | Reactivado sin duplicar; la nota acumula FURL00000005 y FURL00000007 |
| R2d | Servidor OpenAPI nuevo e inactivo «E1 prueba» (`code` `e1_prueba`, base y docs en `petstore3.swagger.io`) | ADM | Alta `petstore3.swagger.io` (`openapi`, «Auto-added for external API server "e1_prueba"»); sin `could not whitelist` en el log. La URL de documentación está en el mismo dominio: no hay una segunda fila |
| R1 | Dos turnos con `fetch_url` a `https://httpbin.org/cache/600` | U3 | 1.º (FURL00000008): sale a la red y guarda (`fetched_at` 14:44:55). 2.º (FURL00000009): `_from_cache: true`, sin salir. Además, FURL00000007 se sirvió de la caché de R2a hasta que caducó |
| R3 | `/annual_billing del año dos mil veinticinco`, dos veces | U1 | 1.º: fila en la caché (`{"year": 2025}`), con cursor propio y commit; 355 tokens. 2.º: el mismo resultado con **0 tokens** (sale de la caché) |
| R4 | Turno con imagen, sin recargar (parche 6) | U1 | Respuesta completa; 0 conexiones `idle in transaction` o esperando lock |
| R5 | Ajustes → «Release PIN blocks» | ADM | «Bloqueos de PIN soltados» |
| R6 | Log desde las 13:55 UTC | — | Sin `AttributeError`, `could not whitelist` ni `param cache remember skipped`. 9 `Traceback`, todos del proveedor: 6 `HTTP 503` de Gemini (saturación) y un tiempo de espera de 45 s (3 líneas encadenadas) |

**Resultado:** parches 7 a 10 **validados en staging**. PNS-83, 85, 90 y 91: CORREGIDO en la rama de
Seges.

### Observaciones (ajenas a E1)

- **Política `whitelist_only` (diseño del fabricante):** un usuario sin AI Administrator no puede
  proponer un `fetch_url` a un dominio fuera de la lista: «Propose failed: No tienes acceso a la URL
  externa «httpbin.org»: su dominio no está en la lista blanca. Pide a un administrador de IA que lo
  añada». No se crea tarjeta. Por eso R2a-c las hace ADM (la spec ya lo preveía).
- **`ai_log`:** no tiene la columna `tool_name`. La herramienta va en `category` (`query`,
  `verification`…) y el tipo en `primitive` (`tool`, `llm`); el uso de la caché de parámetros se ve
  por los tokens del turno.
- **`annual_billing`** se ofrece aunque `account` no esté instalado, y falla con «Skill bootstrap
  failed… KeyError: 'account.move'» (el motor lo gestiona sin colgarse). Para la fase funcional.
- **Entorno: sesiones caducadas cada minuto en Chrome** (con `admin` y con U3; no en otro navegador).
  Causa probable: una cookie `session_id` compartida con `liyben.com`. Ajeno a los parches; pendiente
  de confirmar con F12.
- **Clave MCP de `admin`:** generada para R2 y revocada en la limpieza.

### Limpieza

`preparar_e1.py --limpiar` (A, P y `e1-archivado.invalid`); en la interfaz, el servidor «E1 prueba»,
los dominios `httpbin.org`, `example.org` y `petstore3.swagger.io`, los grupos AI Conversational y
External URL añadidos a `admin` y su clave MCP; por SQL, las filas de prueba de `ai_fetch_cache` y
`ai_skill_param_cache`. Recuentos finales esperados de `ai_fetch_cache`, `ai_skill_param_cache`,
`ai_url_whitelist` y `ai_key_pin_block`: 0 (el resultado no se anotó en su momento). Temporales del despliegue en `/tmp`, borrados.
`addons_antes_E1` se conserva hasta la limpieza final del staging.

## Staging — entrega E2 (21/10/2026)

- **Qué se valida:** parches 11 (PNS-82) y 12 (restos de PNS-01/02), según el §9.3 de la
  [spec E2](../specs/correcciones_pns_ai_entrega2.md). Laboratorio: `pns_ai_mcp` 205 tests, 155 / 5 /
  14 / 31 (los 7 nuevos en verde y los 45 fallos y errores de la línea base, con los mismos nombres);
  `pns_ai_chatboo` 15 tests, todos en verde; revisión de `odoo-reviewer`: APROBADO.
- **Despliegue en `pns_demo`:** commit `792481c` de `14.0-pns-ai-correcciones` (`git archive` de los
  tres módulos). Huella SHA-256 `3ee9623d618a6a27f8b3e53e961ea18f9bf3468e9df84cbc7d4901c5b7eb865f`,
  idéntica en el equipo y en el VPS. `diff -rq` con el despliegue anterior (`2bb4f51`): solo
  `pns_ai_chatboo/models/chatboo_session.py`, `pns_ai_chatboo/models/chatboo_async_request.py`,
  `pns_ai_mcp/controllers/validators.py`, `pns_ai_mcp/models/ai_system_action.py` y
  `pns_ai_mcp/tests/__init__.py` distintos, y `pns_ai_chatboo/tests/` y
  `pns_ai_mcp/tests/test_seges_user_groups.py` nuevos; 20 marcadores `Seges: parche 1[12] (PNS-`
  fuera de los tests. **Auditoría previa** (adjuntos colgados de sesiones de otro dueño, consulta del
  §9.3): 0 filas. Copia previa en `/opt/odoo/pns_staging/addons_antes_E2`. Sustitución con `rsync`
  como el usuario `ubuntu` (1000, dueño de `addons`) y reinicio de `odoo14_pns`, sin `-u`; arranque sin
  errores (11:04 UTC).
- **Usuarios y datos de prueba** (`preparar_e2.py`, por RPC como `admin`): A2 (`e2_interno_a`, id 14),
  B (`e2_interno_b`, 15), P (`e2_portal`, portal, 16), E2ADM (`e2_aiadmin`, AI Administrator y AI
  Conversational **sin** Ajustes, 17) y T (`e2_objetivo`, con Creación de contactos, 18). X = adjunto
  huérfano de A2 (308); CS_B = sesión de B (31); Y = adjunto huérfano de `admin` que simula una copia
  de configuración (309). `admin`, temporalmente con AI Conversational y clave MCP; clave MCP de
  E2ADM. Línea base: 12 filas en `ai_safe_operation`. Contraseña de `admin`: sin cambios.
- **Scripts:** `preparar_e2.py`, `pruebas_e2_rpc.py` (pruebas 1 a 5), `pruebas_e2_mcp.py` (pruebas 6 a
  9, por `/mcp` sin LLM) y `prueba4_bis_e2.py`, solo con la biblioteca estándar; contraseñas y claves en
  variables de entorno cargadas con `read -s`, sin guardarlas.

### Pruebas de seguridad

| # | Prueba | Quién | Resultado |
|---|---|---|---|
| 1 | PNS-82, RPC directo: `claim_turn_file_chips`, `apply_`, `stage_` y `consume_staged_…`, públicos y privados | B y P | **CORREGIDO**: público → `AttributeError`; privado → `AccessError` (16 comprobaciones); X e Y sin cambios |
| 2 | PNS-82, vía del búfer (H-2): `write` de `staged_assistant_files` con X e Y, `create` de un job y `request_cancel` | B | **CORREGIDO**: las tres llamadas responden y X e Y siguen huérfanos |
| 3 | Descarga de X e Y por `/pns_ai_mcp/session_file` y `/web/content` | B | **CORREGIDO**: 404 en los cuatro casos. Control: A2 descarga X (200) |
| 4 | Borrado en cascada (R3) | `admin` y B | Incompleta: `admin` no pudo enganchar X a CS_B (`AccessError`: la regla de registro de `chatboo.session` por `user_id` también se aplica a `admin`). Sí se comprobó que Z, adjunto propio de B colgado de CS_B, se borra con la sesión. Se repite como 4 bis |
| 4 bis | B crea CS_B2 (33); X se engancha a ella por SQL (`UPDATE 1`, caso de la auditoría: datos anteriores al parche); B cuelga Z2 y borra CS_B2 | B | **CORREGIDO**: Z2 borrado; X existe con `res_model` vacío, `res_id` 0 y `create_uid` 14 (SQL); A2 descarga X (200) y B no (404) |
| 5 | `unlink` de una sesión ajena (29) | B | `AccessError`; la sesión sigue |
| 6 | PNS-01, propuesta por `/mcp`: `user.add_group` de `base.group_system` para sí mismo | E2ADM | **CORREGIDO**: `{"success": false, "error": "Step 1: Only a Settings administrator can add or remove user groups."}`; sin operación nueva (SQL); E2ADM sin Ajustes |
| 7 | PNS-01, plan confirmado: `admin` propone (`SAFE00000001`) y E2ADM confirma en la interfaz | `admin` y E2ADM | **CORREGIDO**: `{"error": "Only a Settings administrator can add or remove user groups.", "_executing": false}`; operación `cancelled`; E2ADM sin Ajustes |
| 8 | PNS-02: quitar Creación de contactos a T, propuesto por E2ADM y, en otro plan, propuesto por `admin` (`SAFE00000002`) y confirmado por E2ADM | E2ADM | **CORREGIDO**: rechazado en los dos casos con el mismo mensaje; operación `cancelled`; T conserva el grupo |
| 9 | `view.set_field_readonly` sobre `res.partner.comment` (R5 de la spec) | E2ADM | La propuesta pasa (`SAFE00000003`, pendiente) y E2ADM la cancela: `view.*` sigue disponible sin Ajustes |
| — | Control: `res.users.context_get` | B y P | Responde |

Desde el despliegue se crearon exactamente 3 operaciones (13 a 15, las de 7 a 9); las propuestas
rechazadas de 6 y 8 no dejaron fila. Las tres terminaron en `cancelled`.

### No regresión con Gemini

| # | Caso | Quién | Resultado |
|---|---|---|---|
| R1 | Exportación a Excel del motor | U1 | Chip y descarga correctos; adjunto 316 de U1, enganchado a la sesión 34 |
| R2 | «Ahora en PDF» (montado en el navegador) | U1 | El chip pendiente se sustituye y descarga. El adjunto (317) queda huérfano: ver observaciones |
| R2b | Lo mismo en Word | U1 | Igual que R2 (318) |
| R3 | CSV adjuntado con el clip | U1 | Chip clicable y respuesta correcta; adjuntos 319 y 321 huérfanos (observaciones) |
| R3b | SVG en línea | U1 | El SVG se ve dentro de la respuesta; adjunto 320 huérfano (observaciones) |
| R4 | Recarga y reapertura desde History | U1 | Los chips siguen y descargan |
| R5 | Borrar la sesión 34 desde History | U1 | Sin error; la sesión y sus adjuntos enganchados desaparecen (316 borrado); 317 a 321 siguen como huérfanos |
| R5b | Borrado masivo de dos sesiones desde History | U1 | Sin error |
| R6 | Plan de grupos con Ajustes: quitar y volver a poner Creación de contactos a T | `admin` | Operaciones 16 y 17 `executed`; T termina con el grupo |
| R7 | «Añádeme el grupo Ajustes» en el chat | E2ADM | Sin tarjeta ni operación; E2ADM sin Ajustes. El turno se detuvo antes de proponer, por el control de acceso del core: «No puedes ingresar a los registros 'Aplicación' (ir.module.category)» (exige Derechos de acceso). El rechazo del parche al proponer queda cubierto por la prueba 6 |
| R8 | Log desde las 11:04 UTC | — | Solo los rechazos provocados (prueba 1 a las 11:25; pruebas 7 y 8 a las 11:39). Ningún «no se pudieron borrar los adjuntos». Además, los conflictos de serialización de las observaciones |

**Resultado:** parches 11 y 12 **validados en staging**. PNS-82 y los restos de PNS-01 y PNS-02:
CORREGIDO en la rama de Seges.

### Observaciones (ajenas a E2)

- **Adjuntos del chat que quedan huérfanos (fabricante; nuevo PNS-98 en el seguimiento).** El PDF y el
  Word montados en el navegador (`fulfill_client_export`), los ficheros del clip y el SVG en línea se
  crean con el usuario del turno (`create_uid = 8`) pero no se enganchan a la sesión; el Excel del
  motor sí. Causas, en el código del fabricante:
  - PDF y Word: el adjunto se crea en un cursor aparte con commit (`_run_on_committed_cursor`,
    `pns_ai_mcp/utils/session_download.py`) y la reclamación lo busca con el cursor de la petición, que
    no lo ve (`REPEATABLE READ`): `att.exists()` da `False` y no se engancha. El propio comentario de
    la función lo advierte («Downloads created on that cursor are invisible there»).
  - Clip y SVG: `_finalize fresh-cursor failed` con `could not serialize access due to concurrent
    update` al escribir `chatboo_async_request.done_meta` (jobs 141, 145 y 146; 11:58:37, 12:00:56 y
    12:04:07 UTC). La vía de respaldo deja el job en `done` y guarda el turno, pero no reclama los
    adjuntos.

  El parche 11 no influye: sus dos filtros (sesión del usuario real y adjunto creado por él) se
  cumplen en estos casos y, superados, el método hace lo mismo que el original; tampoco toca
  `_finalize`. Conclusión por análisis del código y del log, sin repetir la prueba con el código
  anterior (decisión de Sergio, 21/10/2026). No afecta a la seguridad (un huérfano solo lo leen su
  creador y los administradores), pero esos adjuntos no se borran con la sesión. Desde el 15/10 no
  había en `pns_demo` adjuntos de estos tipos anteriores a E2 con los que comparar.
- **Conflictos de serialización con ficheros (PNS-94 de fondo, E5).** Además de los tres de
  `_finalize`, a las 17:11:04 UTC (R6) `UPDATE chatboo_session SET last_used_date … WHERE id IN (37)`
  falló con el mismo error, sin efecto visible en el turno. La validación del parche 6 (16/10) se hizo
  con imágenes y el log salió limpio; con ficheros del clip y SVG aparecen estas trazas.
- **Regla de registro de `chatboo.session`:** por `user_id`, también para `admin` (no es el
  superusuario): no puede escribir en sesiones ajenas, enganchar adjuntos a ellas ni borrarlas. Por eso
  la prueba 4 se rehízo con SQL y la limpieza borra las sesiones con cada usuario.
- **`ai.safe.operation`:** el estado está en `status` (no `state`) y las operaciones se crean con
  `create_uid = 1` (en `sudo`); quien las resuelve queda en `write_uid`. `ai_change_journal` registra
  también los intentos rechazados (entradas 4 y 5, `confirmed_by_uid = 17`).
- **R7:** con un AI Administrator sin Derechos de acceso, el modelo no llega a proponer el plan de
  grupos porque antes consulta `ir.module.category` y el core se lo deniega.

### Limpieza

`preparar_e2.py --limpiar` (corregido: cada usuario de prueba borra sus sesiones y las operaciones se
listan por `status`): sesión 38 de E2ADM borrada; adjuntos X e Y borrados; A2, B, P y T borrados con
sus contactos. **E2ADM (`e2_aiadmin`, id 17) queda archivado:** no se puede borrar porque
`ai_change_journal.confirmed_by_uid` lo referencia (entradas 4 y 5); se elimina con la limpieza final
del staging. Por RPC como `admin`: adjuntos huérfanos 317 a 321, operaciones 13 a 17 y la sesión 37 de
`admin`, borrados. En la interfaz: AI Conversational retirado a `admin`; claves MCP de `admin` y de
E2ADM revocadas. Recuentos finales: `ai_safe_operation` 12 (línea base); adjuntos de prueba 0; `admin`
sin AI Conversational; ninguna sesión creada desde el despliegue; único usuario `e2_*`, `e2_aiadmin`
inactivo. Temporales del despliegue en `/tmp`, borrados. `addons_antes_E2` se conserva hasta la
limpieza final del staging.

## Staging — entrega E1′ (26/10/2026)

Sergio con Claude; horas en UTC. Procedimiento ejecutado: [staging_e1_3879.md](staging_e1_3879.md) (con
el resultado de cada comprobación en sus casillas «Obtenido»); análisis de R4 y R6 en
[diagnostico_r6_staging_e1p.md](diagnostico_r6_staging_e1p.md).

- **Qué se valida:** cambio de base de `pns_demo` de 3.1.782 a 3.1.879 con `-u` (sin copia, N9) y los
  parches 10 y 12 adaptados y 13 a 16 (PNS-83, PNS-01/02, M10, M13, PNS-07 y PNS-54), según el §4 de la
  [propuesta de E1′](e1_propuesta_3879.md). Laboratorio: 260 tests, 18 F y 32 E (log
  `tests-20261023-193409.log`; [parches](parches_pns_ai.md), «Línea base de E1′»).
- **Antes (A):** conforme. Montado el código de `792481c` (634 archivos, huella `5dccc29a…`).
  `pns_demo` en 3.1.782, sin neutralizar, con los 6 crons `pns_*` activos. Fotografía de P-9: `ai_log`
  990 (`chatboo` 950, `internal` 28, `mcp_client` 12), diario 7, sesiones 31, jobs 0, contextos 58,
  skills 10; 978 filas de `ai_log` con agente; 10 sesiones con marcas antiguas. AI Administrators:
  `admin` (contraseña local y Ajustes) y `e2_aiadmin` (archivado). Proveedor: cadena de Chatboo con
  Gemini 3.6 flash, 3.5 flash y 3.5 flash lite; «Test Connection» correcto en los tres.
- **Despliegue en `pns_demo` (B):** conforme. Commit `0366231` de `14.0-pns-ai-3879` (`git archive` de
  los tres módulos). Huella del archivo `4a0aba60…dd90`, idéntica en el equipo y en el VPS; copia con
  `scp -P 50050`; comprobaciones del código extraído (B.4) conformes. Copia previa en
  `/opt/odoo/pns_staging/addons_antes_E1p`; ensayo del `rsync` con las 6 bajas previstas. Tras la
  sustitución (`rsync --delete`, módulo a módulo, con Odoo parado): 696 archivos, huella `c12168ea…`;
  `diff -rq` de 268 líneas (195 distintos, 67 nuevos, 6 bajas).
- **`-u` de los tres módulos:** sin `Traceback`, `ERROR` ni `CRITICAL`; 7 «Deleting field» (entre ellos
  `ai.log.agent_id`); 11 `DROP leftover`; 7 `WARNING` inocuos (en lugar del de `jinja2`, dos
  `DeprecationWarning` de `distutils` del core). Arranque sin errores; `/web/login` 200 y `GET /mcp`
  403.
- **Después (C):** conforme.
  - **P-9a:** `key_pin*` fuera; `provider_id` y `client_display` en `ai_log`; cinco `canvas_*` en
    `chatboo_session`; los cinco parámetros pasan a `pns_ai.*` con los mismos valores; de los XML ID de
    parámetros solo queda `icp_chatboo_history_retention_days`; `xmlid_mcp` 0. Recuentos iguales salvo
    `ai_log` `internal` 28 → 31, por los tres «Test Connection» hechos después de la fotografía;
    contextos 61 y skills 13 (+3).
  - **P-9b:** se pierde el agente de 978 filas (pérdida aceptada, N9).
  - **P-9e:** 10 → 0.
  - **P-9f:** `pns_base` 1.2.47, `pns_ai_mcp` 3.1.879 y `pns_ai_chatboo` 2.1.538, `installed`.
  - **Cron de la papelera:** activo, diario, `numbercall` -1, `user_id` 1; primera ejecución el
    27/10/2026 a las 11:50 UTC.
  - **Recarga de `es_ES`** (antes de D): sin errores.
- **Usuarios y datos de prueba (D.0):** AA = `e1p_aiadmin` (id 19), I (20), P (21), T (22); UW (11); C,
  el contacto 9. Línea base: `ai_safe_operation` 12, `ir_attachment` 666, contextos de fábrica 53,
  mesa de PIN 0/0, diario 7.
- **Scripts:** `preparar_e1p.py`, `pruebas_e1p_rpc.py` y `pruebas_e1p_mcp.py`, en `~/staging_e1p` del
  equipo de Sergio, solo con la biblioteca estándar; contraseñas y claves en variables de entorno
  cargadas con `read -s`, sin guardarlas.

### Pruebas de seguridad

| # | Prueba | Quién | Resultado |
|---|---|---|---|
| 1 | P-8b (M10, parche 13): `create`, `create_verification`, `copy`, `cleanup_stuck_state` y `_cleanup_stuck_state` | AA | **CORREGIDO** |
| 2 | P-01 (parche 12), propuesta por `/mcp`: `user.add_group` para sí y `user.remove_group` a T | AA | **CORREGIDO** |
| 2b | P-01, plan propuesto por ADM y confirmado por AA en Autorizaciones (pide su contraseña, parche 16) | ADM y AA | **CORREGIDO**: rechazo «Only a Settings administrator…»; `status` final `cancelled`; T conserva el grupo |
| 3 | CRUD en `res.groups` (parche 12), y control con ADM | AA-ERP | **CORREGIDO** |
| 4 | P-54b (parche 16): `action_confirm_and_execute` y `action_execute_plan` por `call_kw` | UW y ADM | **CORREGIDO** |
| 4b | `card_payload(mint_token=True)` sobre la operación de UW (parche 16) | ADM | **CORREGIDO** |
| 5 | P-07 (parche 15): `fulfill_client_export` desde `relaxaicode`, literal y compuesto | U1 | **CORREGIDO**: 0 adjuntos nuevos. U1 no tenía verificaciones pendientes (`cancelled_operations` 0) |
| 6 | P-8a (M13, parche 14): `unlink_retired_from_module` y el privado | I y P | **CORREGIDO** |
| 7 | P-83a (parche 10): `collect_pin` y `_collect_pin`, sin mesa abierta | I y P | **CORREGIDO**: respuestas en menos de 1 s |
| 8 | P-83b (observación; PNS-84, E4′) | I | Igual que la referencia del laboratorio |
| — | Control: `res.users.context_get` | I y P | Responde |

### No regresión con Gemini

| # | Caso | Quién | Resultado |
|---|---|---|---|
| R1 | Turno de Chatboo con una consulta de datos | U1 | Conforme |
| R2 | Sesión anterior al `-u` (historial reescrito) | U1 | Conforme |
| R3 | Exportación a Excel y a PDF | U1 | Conforme |
| R4 | Tarjeta del chat del propio dueño | UW | Conforme: la tarjeta ejecutó la operación 21 (nota en el chatter). La 22 (modificar el contacto) falló con «configure la dirección de correo electrónico del remitente» porque UW no tiene correo (dato del usuario de prueba) |
| R5 | Autorizaciones: «Confirmar y ejecutar» | ADM | Conforme |
| R6 | Plan de grupos con Ajustes sobre T | ADM | Conforme en lo que comprueba E1′: la operación 27 quitó el grupo a T y lo registró (fila 12 del diario). Sergio lo volvió a poner a mano a las 16:48:43 (`write_uid` 2) y T no tiene grupos que lo impliquen ([diagnóstico](diagnostico_r6_staging_e1p.md), §6). Volver a ponerlo por plan no se hizo (cubierto por los tests y por R6 de E2) |
| R7 | `relaxaicode` normal por `/mcp`: `search_count` de contactos | U1 | Conforme |
| R8 | Lienzo: una página sencilla desde el chat | U1 | **NO CONCLUYENTE**: `gemini-3.5-flash-lite` dijo haber creado la página y no la creó (0 páginas; PNS-96). Se repite el 27/10/2026 con la cuota renovada (decisión 3) |
| R9 | Log desde el arranque | — | Conforme: 36 × `429 RESOURCE_EXHAUSTED` y 1 × `503 UNAVAILABLE`, del proveedor; además, los dos errores de serialización de R4 y R6 (observaciones) |

**Resultado:** cambio de base de `pns_demo` a 3.1.879 hecho y parches 10 y 12 a 16 **validados en
staging**, salvo R8, pendiente de repetir el 27/10/2026. PNS-83, PNS-01/02, M10, M13, PNS-07 y PNS-54
(lo que cubre el parche 16): CORREGIDO en la rama `14.0-pns-ai-3879`.

### Observaciones (ajenas a E1′; del fabricante)

Detalle, reproducción en el laboratorio con y sin los parches de E1′ y causas en el
[diagnóstico](diagnostico_r6_staging_e1p.md):

- **`user.remove_group` de un grupo que también llega por implicación** (diagnóstico, 5.1): la operación
  queda `executed` y el diario `applied` sin que el cambio ocurra. No es lo que pasó en R6. Nuevo PNS-99
  en el [seguimiento](seguimiento_informe_pns_ai.md) (Media).
- **Error de serialización en cada `/execute` de la tarjeta** (diagnóstico, 5.2): una línea ERROR y un
  reintento de Odoo, sin perder ni repetir nada. Visto en R4 y R6. En el seguimiento, en PNS-26 (Baja).
- **`missing_token` y `bad_token` en la tarjeta del chat** (diagnóstico, 5.3): fallan en cerrado. En el
  seguimiento, en PNS-54 (Baja).
- **Escritura en la operación 27 a las 16:47:55 (`write_uid` 2), sin efecto:** sin causa encontrada en
  el código (diagnóstico, 3.2 y §7).

### Limpieza

`preparar_e1p.py --limpiar` (D.3): conforme. Usuarios `e1p_%`: 1, AA (`e1p_aiadmin`, id 19) archivado,
con los grupos de la línea base (no se puede borrar: la fila del diario de la prueba 2b lo referencia);
I, P y T borrados. C sin cambios; mesa de PIN 0/0; contextos de fábrica 53. `ai_safe_operation` 26
(las 14 de hoy, ninguna pendiente); diario 12; `ir_attachment` 652. Claves MCP temporales revocadas.
`addons_antes_E1p` se conserva hasta la limpieza final del staging.

### Repetición de R8 (27/10/2026)

Sergio con Claude; horas en UTC. Lienzo, como U1.

- **Mensaje (08:08:43):** «crea una página en el lienzo con un resumen de los 5 contactos con más
  facturas».
- **Proveedor:** Gemini 3.6 flash, HTTP 503 `UNAVAILABLE` (08:07:54); Gemini 3.5 flash, fallo de
  conexión (08:08:40). Contestó `gemini-3.5-flash-lite` tras el failover (93 s). El failover funcionó
  como se esperaba.
- **Resultado:** el modelo afirmó haber creado la página y no la creó. Sesiones 46 y 47 de U1 con
  `canvas_rev` = 0 y `canvas_title` vacío; 0 filas nuevas en `chatboo_canvas_page` desde las 08:05.
  Mismo patrón que el 26/10/2026 (PNS-96). No hay indicios de un error de Seges.
- **Decisión de Sergio (27/10/2026):** R8 queda **no concluyente por el proveedor** y se valida en E3′,
  donde se corrige el lienzo (M1, M2 y F1).

**Resultado de E1′ en staging:** cerrada el 27/10/2026, con la salvedad de R8. Parches 10 y 12 a 16
validados en staging.

## Laboratorio — entrega E2′ (27/10/2026)

Laboratorio `lab_pns_ai_3879` (BD `lab_pns_ai_3879_14`), rama `14.0-pns-ai-3879`; horas en UTC. Propuesta:
[e2_propuesta_3879.md](e2_propuesta_3879.md); parches y tests: [parches_pns_ai.md](parches_pns_ai.md),
«Parches de la rama 14.0-pns-ai-3879 (E2′)».

### P-20 (PNS-20), antes del parche (Sergio, 27/10/2026)

Pasos y consultas en la [propuesta de E2′](e2_propuesta_3879.md), «P-20: pasos y consultas». «Review» de
una importación, sin pulsar Confirmar:

| Caso | `temperature` / etiqueta | `write_date` |
|---|---|---|
| A. Proveedores (`ai_provider` 3, OVH; exportación 459) | 0.7, sin cambios | 2026-10-23 09:38:41 → **2026-10-27 10:45:29** |
| B. Usuarios MCP (`ai_mcp_user` 1, `demo`; exportación 461) | vacío → **`P-20 preview`** | 2026-10-23 07:28:35 → **2026-10-27 10:50:09** |

- **PNS-20 CONFIRMADO:** «Review» persiste la importación (B) o deja un `UPDATE` del registro después del
  `ROLLBACK TO SAVEPOINT` (A; el `model_id`, con el mismo valor). Causa: `invalidate_cache()` no vacía
  `towrite`. Se aplica el parche 21.
- `res.users` de `demo` sin cambios. Restos aceptados: la etiqueta de `demo`, el `write_date` de OVH y
  los adjuntos 459 y 461. `~/p20_lab` borrado.

### Validaciones de E2′ hechas (Claude)

- **Comprobaciones previas** (solo lectura): (f) qué lee la caja A, `auto_join`, colisiones de los 28
  nombres del parche 22, inventario de PNS-07, `precommit` en «Review» y firmas de Odoo 14. La (f)
  cambió el diseño del parche 18: el lienzo lee `ai.provider` desde la caja A; Sergio aprobó una ventana
  en `_ask_design` como excepción documentada.
- **`py_compile`** con Python 3.7.3 (imagen `odoo-dev:14-lab_pns_ai_3879`): 19 archivos, correctos.
- **Lint** `--base c639fa8`: 0 incidencias nuevas.
- **Tests** (`odoo-dev 14 tests pns_base,pns_ai_mcp,pns_ai_chatboo`, BD de tests nueva; log
  `tests-20261027-124454.log`): 319 tests, 18 F y 32 E, los mismos que la línea base de E1′; 59 nuevos,
  todos en verde.
- **Neutralización** de cada parche (N1 a N4): fallan los tests negativos de cada uno y los de no
  regresión siguen pasando; restauración comprobada con el md5 del `git diff`. El parche 20 se neutraliza
  a mano en P-70.
- No se ha escrito en `lab_pns_ai_3879_14` (solo `SELECT` dentro de `BEGIN TRANSACTION READ ONLY`), ni se
  ha reiniciado el contexto: el servidor web sigue con el código anterior a E2′.

### Pendiente en el laboratorio (Sergio)

Tras reiniciar el contexto (`odoo-dev 14 parar` y `arrancar` desde `~/GitHub/lab_pns_ai_3879`): P-19,
P-37, P-37b, P-17 manual, P-70 (casos 1 a 5) y P-20 repetida, con los pasos y las consultas de
[lab_e2_3879.md](lab_e2_3879.md). El resultado se anota en un bloque fechado debajo de este.

## Laboratorio — E2′, resultado (28/10/2026)

Pruebas manuales de [lab_e2_3879.md](lab_e2_3879.md) tras reiniciar el contexto (`parar` + `arrancar`,
Sergio). Detalle por caso en ese documento, «Resultado (28/10/2026)».

| Prueba | Parche (PNS) | Quién / cómo | Resultado |
|---|---|---|---|
| P-19 | 18 (PNS-19) | Claude, shell | **OK** |
| P-101 | 23 (PNS-101) | Claude, shell | **OK** |
| P-101′ | 23 ampliado (PNS-101) | Claude, shell | **OK** |
| P-102 | 24 (PNS-102) | Claude, shell | **OK** |
| P-37w/c | 17 (PNS-37) | Claude, shell | **OK** |
| P-37b | 17 (PNS-37) | Test `test_plan_unlink_requires_unlink_right` (verde en `tests-20261027-124454.log`) | **Cubierta por el test**; **pendiente de confirmación manual en staging** |
| P-17 manual | 19 (PNS-17) | Sergio, navegador | **OK** |
| P-70, casos 1 a 5 | 20 (PNS-70) | Sergio, navegador | **OK** |
| P-20 A y B | 21 (PNS-20) | Sergio, navegador | **OK** |

- Shell: `odoo-dev 14 shell` con `tool_relaxaicode` + `_StubController`, sin `/mcp` ni claves MCP;
  rollback al final. Ninguna respuesta contenía `database.secret`, las `api_key` de los proveedores,
  `admin_passwd`/`db_password` ni `totp_secret` (comprobado contra los valores leídos fuera del sandbox,
  sin imprimirlos).
- Salvedades (P-19b sin datos en esta BD; `c2_su.py` no discrimina porque `demo` tiene Facturación) y la
  escritura no prevista en `ai_log` (filas 318 y 319, de P-19j): en [lab_e2_3879.md](lab_e2_3879.md).
- Queda para staging: P-37b manual.
