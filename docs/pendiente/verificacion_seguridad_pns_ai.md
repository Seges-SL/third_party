# Verificación de seguridad controlada — pns_ai_mcp

**Fecha:** 2026-10-08
**Entorno:** local, Docker del kit (`odoo-dev`). Odoo 14.0.
**Rama analizada:** `third_party` @ `14.0-analisis-pns-ai` (copia de trabajo montada).
**Alcance:** solo lectura del repo salvo este informe. Sin claves de IA. Sin llamadas a
servicios externos. Solo datos de demostración.

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
