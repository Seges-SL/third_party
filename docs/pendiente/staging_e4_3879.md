# Subida de E4′ al staging `pns_demo` (parches 30 a 34)

- **Rama:** `14.0-pns-ai-3879` · **Base (montada ahora):** `522ce6e` (E3′ y parche 29) · **Commit a
  desplegar:** `8d218ea`, el último que toca los módulos. Los posteriores (`3384567` y `a06d393`) solo son
  [DOC]: dan el mismo árbol, pero otra huella del `.tar.gz` (B.1) · **Preparado:** 06/11/2026 · **Estado:**
  ejecutado el 09/11/2026 (montado ahora: `8d218ea`); resultado en G.
- **Qué se sube:** E4′.a (parches 30 a 33, en `pns_ai_mcp`) y E4′.b con su ampliación E4′.b2 y E4′.b3
  (parche 34 con la opción A y el formato F1, en `pns_ai_chatboo`). Registro en [parches](parches_pns_ai.md),
  «Parches de la rama 14.0-pns-ai-3879 (E4′.a)», «(E4′.b)» y «(E4′.b2 y E4′.b3)».
- **Origen:** [propuesta de E4′](e4_propuesta_3879.md) (aprobada el 05/11/2026; «Resultado de E4′.a»,
  «Resultado de E4′.b», «Resultado de E4′.b2 y E4′.b3» y «Resultado de E4′.h») y el
  [plan](plan_correccion_pns_ai_3879.md), apartado E4′ (los dos bloques de validaciones del parche 34) y §3
  punto 1, «Antes del despliegue (E4′.a)». Validación en el laboratorio: parche 34 en
  [parches](parches_pns_ai.md), «Validación en el laboratorio» de E4′.b2 y E4′.b3 (sesiones 21 a 24); parches
  30 a 33 con el script [`scripts_e4/pruebas_e4p.py`](scripts_e4/pruebas_e4p.py): la versión final, el
  09/11/2026 (16/16 OK); el 06/11/2026 (16/16 OK), con una versión anterior al filtro de contraseñas.
- **Procedimiento de referencia:** [subida de E3′](staging_e3_3879.md) (mismo método, mismos contenedores, el
  túnel SSH de su apartado G) y [subida de E2′](staging_e2_3879.md) para los usuarios de prueba y la limpieza.
- **Limpieza del staging: al terminar todos los cambios, no por entrega** (como en E3′). En esta subida solo
  se deshace lo que falsearía las pruebas siguientes (F).
- **LIYBEN recibe todo de una vez, al final** (plan, §1 punto 3 y §3). Las comprobaciones previas de A.4 y
  A.5 de este documento se repiten allí (plan, §3.1, «Antes del despliegue (E4′.a)»).
- **Condiciones del staging que siguen vigentes:** las del plan de staging, §1. `pns_demo` **no está
  neutralizado** (los crons corren). Sin copia de `pns_demo` (N9).
- **Sin secretos en este documento:** ni contraseñas, ni claves, ni el contenido de `.env`.

**Convenciones de los comandos.** Las de E2′ y E3′: **[LECTURA]** solo lee; **[ALTERA]** cambia algo y va
precedido de un aviso. SQL con `psql` en `odoo14_pns_db`, BD `pns_demo`, usuario `odoo`, con la función `e4sql`
(A.0), que abre la sesión **en solo lectura**, y siempre con heredoc `<<'SQL'`. Lo no confirmado se marca
**«Sin confirmar»**. Además:
- Las consultas que vienen del plan (A y B de P1, V5 y V6) van **tal cual**. Las nuevas de este documento
  (comprobaciones previas de A.4, cron, grupos, pasos por `model` y `op`, variante con expresión regular,
  jobs del botón Canvas y huella de los mensajes) se validaron en solo lectura contra `lab_pns_ai_3879_14` el
  06/11/2026; las de `ai_safe_operation`, con un JSON de prueba, porque allí la tabla está vacía.
- Los valores esperados de B.4 se calcularon el 06/11/2026 **sin git**: sobre la copia de trabajo (módulos
  iguales a `8d218ea`) y sobre el archivo de `522ce6e` que quedaba en `/tmp` del equipo (huella
  `34b1b023…f3d0`, la de B.1 de E3′). Se confirman en B.4 con el archivo de `git archive`.
- Variable del VPS para las consultas de una sesión: `SESION` (no `E4P_SESSION`: el script de E4′ no usa
  sesiones). Se asigna directamente (`SESION=58`), sin `read`.

## Índice

0. Método de despliegue
A. Comprobaciones previas (solo lectura)
B. Despliegue y `-u`
C. Usuarios de prueba y comprobaciones posteriores
D. Pruebas
E. Vuelta atrás (descrita)
F. Limpieza
G. Resultado de la subida

---

## 0. Método de despliegue

El de E3′ (§0): `git archive` de los tres módulos desde el equipo de Sergio, `scp` a `/tmp` del VPS, huella
comparada en el VPS, copia previa en `addons_antes_E4p`, parada de `web`, `rsync --delete` módulo a módulo
como `ubuntu`, `-u` y arranque.

**Diferencias con E3′** (calculadas el 06/11/2026 con `diff -rq` entre el archivo de `522ce6e` y los módulos
de la copia de trabajo, sin git):
- **Cambian `pns_ai_mcp` y `pns_ai_chatboo`.** 11 archivos, todos `.py`: 10 distintos
  (`pns_ai_mcp/models/ai_execution_engine.py`, `ai_provider.py`, `ai_trusted_action.py`,
  `pns_ai_mcp/wizard/ai_provider_usage_wizard.py`, `pns_ai_mcp/tests/__init__.py`,
  `test_seges_format_guard.py`, `test_seges_user_groups.py`, `pns_ai_chatboo/models/chatboo_async_request.py`,
  `chatboo_canvas.py` y `pns_ai_chatboo/tests/test_seges_chatboo_canvas.py`) y 1 nuevo
  (`pns_ai_mcp/tests/test_seges_e4p.py`). **Ninguna baja.** `pns_base` no cambia.
- **Sin cambio de versión ni de esquema.** Manifiestos en `1.2.47`, `3.1.879` y `2.1.538`. No cambian vistas,
  datos, CSV, JS ni `i18n`, y el diff no añade ni quita ningún campo (`fields.`).
- **Una sola actualización: `-u pns_ai_mcp`** (decisión de E4′.h). Lo que cambia es Python y se carga al
  arrancar; el `-u` recarga además los datos de `pns_ai_mcp`, entre ellos los 9 registros de
  `data/trusted_actions_system.xml` (`noupdate` falso), que se reescriben en `su`: es la prueba real de que
  el parche 32 no bloquea la carga de datos (lo que en los tests hace `test_factory_data_reload`).
  **Matiz:** en Odoo 14, `button_upgrade` añade los módulos instalados que dependen del que se actualiza
  (`odoo/addons/base/models/ir_module.py:636-669`), y `pns_ai_chatboo` depende de `pns_ai_mcp`
  (`__manifest__.py:24`). Así que **el `-u` también actualiza `pns_ai_chatboo`** aunque no se nombre: recarga
  sus datos sin cambios (la regla del parche 28 sigue en `t f f t`). No hay que lanzar nada más. Que no haya
  otro módulo instalado que dependa de `pns_ai_mcp` se comprueba en A.4 a.
- **La vuelta atrás del código es viable** (E): solo cambia Python.
- **Nuevo en esta subida:** las operaciones supervisadas con pasos sobre `ai.trusted.action` antes del
  despliegue (A.4), los grupos de los usuarios de prueba (A.5), el script de E4′ por el túnel SSH (D.1) y
  las validaciones del parche 34 a mano y por SQL (D.2 y D.3).

---

## A. Comprobaciones previas (solo lectura)

En el VPS, con el usuario `ubuntu`, salvo donde se diga.

### A.0 Función de consulta

**[LECTURA]**

```bash
e4sql() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_pns_db psql -U odoo -d pns_demo -v ON_ERROR_STOP=1 -v sesion="${SESION:-0}"; }
e4sql <<'SQL'
SHOW default_transaction_read_only;
SHOW TimeZone;
SQL
```

Esperado: `on` y `UTC` (como en E3′).

### A.1 Contenedores y usuario de PostgreSQL

**[LECTURA]** Como en E3′ (A.1):

```bash
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}' | grep -E 'odoo14_pns|odoo14_db|odoo14_server'
docker exec odoo14_pns_db printenv POSTGRES_USER
```

Esperado: `odoo14_pns` y `odoo14_pns_db` en marcha; `POSTGRES_USER` = `odoo`.

**[LECTURA]** Puerto publicado de Odoo (destino del túnel de D.1), para confirmarlo antes de D.1:

```bash
docker port odoo14_pns
```

Esperado: una línea hacia `8169` (`<puerto del contenedor>/tcp -> <dirección>:8169`), que se anota. Si no sale, el
túnel de D.1 no tiene destino: parar y decidir con Sergio. La orden del `ssh` de D.1 sigue **«Sin
confirmar»**.

### A.2 Montajes, copias y disco

**[LECTURA]**

```bash
docker inspect odoo14_pns --format '{{range .Mounts}}{{.Type}}  {{.Source}} -> {{.Destination}}  rw={{.RW}}{{"\n"}}{{end}}'
cd /opt/odoo/pns_staging && ls -la && ls -la addons
du -sh addons
df -h /opt/odoo /tmp
```

Esperado: los montajes de E3′ (G, A.2), sin cambios. Copias `addons_antes_E1`, `addons_antes_E2`,
`addons_antes_E1p`, `addons_antes_E2p` y `addons_antes_E3p`, y **todavía no** `addons_antes_E4p`. Disco: en E3′
estaba al **87 %** (9,6 GB libres). La copia de B.5 ocupa lo que dé `du -sh addons` (en el equipo, los tres
módulos suman unos 12 MB): no es un problema de espacio, pero se anota el porcentaje. **Si el disco pasa
del 95 %, parar** y decidir con Sergio qué restos de la limpieza final se adelantan.

### A.3 Qué código hay montado (huella)

| Commit | Archivos | Huella del árbol |
|---|---|---|
| `522ce6e` (E3′, lo que debería estar montado) | 710 | `6ac645fcfffa3d6a5707d2e3eb7e98518f5d4f1039dc8a32c91782769f6e44e5` |
| `8d218ea` (E4′, lo que se va a montar) | 711 | `e37be4488f2b086a38ff8e6f04baf2f5464a880efd5d241b442909d10fcd1844` (calculada sin git sobre la copia de trabajo; se confirma en B.4) |

**[LECTURA]**

```bash
cd /opt/odoo/pns_staging/addons
find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l
find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum
```

Esperado: 710 y `6ac645fc…44e5`. **Si no coincide, parar:** alguien ha cambiado el código desde E3′.

### A.4 Estado de `pns_demo` y operaciones supervisadas sobre `ai.trusted.action` (parche 32)

**Por qué.** Con el parche 32, un paso CRUD sobre `ai.trusted.action` solo se aplica si quien lo propuso
**y** quien lo confirma tienen Ajustes. Una operación que ya esté pendiente o confirmada sin ejecutar, con un
paso así y propuesta por un AI Administrator sin Ajustes, fallará al ejecutarse después del `-u`. Los
caminos reales del reintento son `safe_plan_status` y `/verification/execute` (errata del plan del
05/11/2026: `_cleanup_stuck_state` no tiene llamador).

**A.4 a. Módulos, crons, acciones de confianza y actividad.** **[LECTURA]** El bloque de A.4 de E3′, con el
cron de `cleanup_expired` (el que caduca las operaciones pendientes) y las acciones de confianza:

```bash
e4sql <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT name, state, latest_version FROM ir_module_module WHERE name LIKE 'pns_%' ORDER BY name;
SELECT key, value FROM ir_config_parameter WHERE key LIKE 'odoo_dev.%';
SELECT d.module || '.' || d.name AS xml_id, c.active, c.numbercall, c.interval_number,
       c.interval_type, c.nextcall, c.user_id
  FROM ir_cron c JOIN ir_model_data d ON d.model = 'ir.cron' AND d.res_id = c.id
 WHERE d.module LIKE 'pns_%' ORDER BY 1;
-- Cron de cleanup_expired (pns_demo no está neutralizado: corre)
SELECT d.module || '.' || d.name AS xml_id, c.active, c.numbercall, c.interval_number, c.interval_type,
       c.lastcall, c.nextcall, c.user_id, s.code
  FROM ir_cron c
  JOIN ir_model_data d ON d.model = 'ir.cron' AND d.res_id = c.id
  JOIN ir_act_server s ON s.id = c.ir_actions_server_id
 WHERE d.module = 'pns_ai_mcp' AND d.name = 'ir_cron_ai_safe_operation_expire';
-- Acciones de confianza: las 9 de fábrica y ningún resto de pruebas
SELECT count(*) AS acciones, max(id) AS ultima,
       count(*) FILTER (WHERE code LIKE 'seges.e4p%') AS restos_e4p
  FROM ai_trusted_action;
SELECT pid, state, xact_start, wait_event_type, left(query, 80) AS query
  FROM pg_stat_activity WHERE datname = 'pns_demo' AND state <> 'idle' ORDER BY xact_start;
-- Módulos instalados que dependen, directa o indirectamente, de pns_ai_mcp (los que actualiza el -u de B.7)
WITH RECURSIVE dep(name) AS (
    SELECT m.name FROM ir_module_module m
      JOIN ir_module_module_dependency d ON d.module_id = m.id
     WHERE d.name = 'pns_ai_mcp'
    UNION
    SELECT m.name FROM ir_module_module m
      JOIN ir_module_module_dependency d ON d.module_id = m.id
      JOIN dep ON d.name = dep.name
)
SELECT m.name, m.state FROM ir_module_module m
 WHERE m.name IN (SELECT name FROM dep) AND m.state = 'installed' ORDER BY 1;
ROLLBACK;
SQL
```

Esperado: las versiones de E3′ (`1.2.47`, `3.1.879` y `2.1.538`, `installed`); sin filas `odoo_dev.%`; siete
crons de `pns_*`; el de `cleanup_expired`, `pns_ai_mcp.ir_cron_ai_safe_operation_expire`, activo, cada 5
minutos, `numbercall` -1, `user_id` 1 y `model.cleanup_expired()` (así en el laboratorio el 06/11/2026); 9
acciones de confianza y 0 restos `seges.e4p`; ninguna transacción en curso; en los módulos que dependen de
`pns_ai_mcp`, **solo `pns_ai_chatboo`** (así en el laboratorio el 09/11/2026). Se anotan `lastcall` y
`nextcall` del cron y el `max(id)` de las acciones. **Si sale otro módulo** que dependa de `pns_ai_mcp`, el
`-u` de B.7 también lo actualizaría: parar y decidir con Sergio.

**A.4 b. Dos comprobaciones antes de las consultas A y B.** **[LECTURA]**

```bash
e4sql <<'SQL'
BEGIN TRANSACTION READ ONLY;
-- 1) operation_data no vacío que no empieza por '{' (las consultas A y B harían ::jsonb y fallarían)
SELECT count(*) FILTER (WHERE coalesce(o.operation_data, '') <> '' AND o.operation_data NOT LIKE '{%') AS no_empieza_por_llave,
       count(*) AS operaciones
  FROM ai_safe_operation o;
-- 2) pasos por estado, model y op de todas las operaciones
SELECT o.status, coalesce(s.step ->> 'model', '(sin model)') AS model, coalesce(s.step ->> 'op', '(sin op)') AS op,
       count(*) AS pasos, count(DISTINCT o.id) AS operaciones
  FROM ai_safe_operation o
 CROSS JOIN LATERAL jsonb_array_elements(
         CASE WHEN o.operation_data LIKE '{%'
               AND jsonb_typeof(o.operation_data::jsonb -> 'plan_steps') = 'array'
              THEN o.operation_data::jsonb -> 'plan_steps' ELSE '[]'::jsonb END) s(step)
 GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;
SELECT status, count(*) FROM ai_safe_operation GROUP BY 1 ORDER BY 1;
ROLLBACK;
SQL
```

Esperado:
- **1):** `no_empieza_por_llave` = 0. `operaciones`: en E1′ quedaron 26 en total (plan, §4); se anota el
  número. **Si sale 1 o más,** no se lanzan A y B: se usa la variante con expresión regular (abajo).
- **2):** **pasos reales** (en `pns_demo` hubo planes en E1′ y E2′): filas con `model` y `op` (por ejemplo,
  `res.partner` / `write`) en estados terminales. Si sale vacía con `operaciones` > 0, la consulta no está
  leyendo los pasos (`plan_steps` con otra forma): **parar y revisar** antes de fiarse de A y B, que usan el
  mismo filtro. Es la comprobación de que el filtro funciona con datos reales (en el laboratorio la tabla
  estaba vacía).

**A.4 c. Consultas A y B** (las del plan, §3 punto 1, «Antes del despliegue (E4′.a)», tal cual).
**[LECTURA]**

```bash
e4sql <<'SQL'
BEGIN TRANSACTION READ ONLY;

-- Consulta A: lo que reintentaría _retry_confirmed_not_executed (status = 'confirmed' y no executed)
WITH sys AS (
    SELECT r.uid
      FROM res_groups_users_rel r
      JOIN ir_model_data d ON d.model = 'res.groups' AND d.res_id = r.gid
     WHERE d.module = 'base' AND d.name = 'group_system'
), ops AS (
    SELECT o.*
      FROM ai_safe_operation o
     WHERE o.status = 'confirmed'
       AND COALESCE(o.executed, false) = false
       AND o.operation_data LIKE '{%'
       AND jsonb_typeof(o.operation_data::jsonb -> 'plan_steps') = 'array'
       AND EXISTS (
           SELECT 1
             FROM jsonb_array_elements(o.operation_data::jsonb -> 'plan_steps') s(step)
            WHERE jsonb_typeof(s.step) = 'object'
              AND s.step ->> 'model' = 'ai.trusted.action'
              AND s.step ->> 'op' IN ('create', 'write', 'copy', 'unlink')
       )
)
SELECT o.id, o.status, o.executed,
       o.user_id, up.login AS propone_login,
       (o.user_id = 1 OR o.user_id IN (SELECT uid FROM sys)) AS propone_ajustes,
       o.confirmed_by_uid, uc.login AS confirma_login,
       COALESCE(o.confirmed_by_uid, o.user_id) AS uid_efectivo,
       (COALESCE(o.confirmed_by_uid, o.user_id) = 1
        OR COALESCE(o.confirmed_by_uid, o.user_id) IN (SELECT uid FROM sys)) AS confirma_ajustes,
       o.create_date, o.write_date, o.resolved_at, o.expires_at,
       o.expires_at < (now() AT TIME ZONE 'UTC') AS vencida
  FROM ops o
  JOIN res_users up ON up.id = o.user_id
  LEFT JOIN res_users uc ON uc.id = o.confirmed_by_uid
 ORDER BY o.id;

-- Consulta B: los demás estados no terminales (solo 'pending': se confirma y ejecuta por el toast,
-- Autorizaciones o auto-confirm; 'expired', 'cancelled' y 'executed' son terminales).
WITH sys AS (
    SELECT r.uid
      FROM res_groups_users_rel r
      JOIN ir_model_data d ON d.model = 'res.groups' AND d.res_id = r.gid
     WHERE d.module = 'base' AND d.name = 'group_system'
), ops AS (
    SELECT o.*
      FROM ai_safe_operation o
     WHERE o.status = 'pending'
       AND COALESCE(o.executed, false) = false
       AND o.operation_data LIKE '{%'
       AND jsonb_typeof(o.operation_data::jsonb -> 'plan_steps') = 'array'
       AND EXISTS (
           SELECT 1
             FROM jsonb_array_elements(o.operation_data::jsonb -> 'plan_steps') s(step)
            WHERE jsonb_typeof(s.step) = 'object'
              AND s.step ->> 'model' = 'ai.trusted.action'
              AND s.step ->> 'op' IN ('create', 'write', 'copy', 'unlink')
       )
)
SELECT o.id, o.status, o.executed,
       o.user_id, up.login AS propone_login,
       (o.user_id = 1 OR o.user_id IN (SELECT uid FROM sys)) AS propone_ajustes,
       o.confirmed_by_uid, uc.login AS confirma_login,
       (o.confirmed_by_uid IS NOT NULL
        AND (o.confirmed_by_uid = 1 OR o.confirmed_by_uid IN (SELECT uid FROM sys))) AS confirma_ajustes,
       o.create_date, o.expires_at,
       o.expires_at < (now() AT TIME ZONE 'UTC') AS vencida
  FROM ops o
  JOIN res_users up ON up.id = o.user_id
  LEFT JOIN res_users uc ON uc.id = o.confirmed_by_uid
 ORDER BY o.id;

ROLLBACK;
SQL
```

Esperado: **0 filas en A y en B** (en E1′ no quedó ninguna pendiente). Si sale alguna: se anotan id,
quién propone y quién confirma (con `propone_ajustes` y `confirma_ajustes`) y si está vencida. Una fila con
`propone_ajustes = f` fallará tras el `-u` (esperado por el parche 32); qué hacer con ella antes de seguir
(dejarla, cancelarla desde Autorizaciones) **lo decide Sergio**.

**Variante con expresión regular** (solo si 1) dio 1 o más; sustituye a A y B). **[LECTURA]** Encuentra el
modelo en cualquier clave `"model"` del texto, también fuera de `plan_steps`: lo que salga se revisa a mano.

```bash
e4sql <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT o.id, o.status, o.executed, o.user_id, o.confirmed_by_uid, o.create_date, o.expires_at
  FROM ai_safe_operation o
 WHERE o.status IN ('confirmed', 'pending')
   AND COALESCE(o.executed, false) = false
   AND o.operation_data ~ '"model"\s*:\s*"ai\.trusted\.action"'
 ORDER BY o.id;
ROLLBACK;
SQL
```

### A.5 Grupos de los usuarios de prueba

**[LECTURA]** Usuarios del script y de las pruebas: `admin` (id 2), `demo` (en E3′, id 6), `e1p_aiadmin` (id 19
en el staging, archivado desde E1′) y U1 (`u1`, id 8). No lee contraseñas, solo si hay una:

```bash
e4sql <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT u.id, u.login, u.active, u.share, p.lang,
       (u.password IS NOT NULL AND u.password <> '') AS contrasena_local,
       bool_or(d.module = 'base' AND d.name = 'group_user') AS interno,
       bool_or(d.module = 'base' AND d.name = 'group_system') AS ajustes,
       coalesce(string_agg(d.name, ', ' ORDER BY d.name) FILTER (WHERE d.module = 'pns_ai_mcp' AND d.name LIKE 'group_ai_%'), '') AS grupos_ia
  FROM res_users u
  JOIN res_partner p ON p.id = u.partner_id
  LEFT JOIN res_groups_users_rel r ON r.uid = u.id
  LEFT JOIN ir_model_data d ON d.model = 'res.groups' AND d.res_id = r.gid
 WHERE u.login IN ('admin', 'demo', 'e1p_aiadmin', 'u1') OR left(u.login, 4) = 'e4p_'
 GROUP BY u.id, p.lang ORDER BY u.id;
SELECT m.id, u.login, m.mcp_api_key_state, coalesce(m.mcp_api_key_hash, '') <> '' AS tiene_hash
  FROM ai_mcp_user m JOIN res_users u ON u.id = m.user_id
 WHERE u.login IN ('admin', 'e1p_aiadmin', 'u1') ORDER BY m.id;
ROLLBACK;
SQL
```

Esperado (lo que pide la precondición del script, D3: `demo` interno sin ninguno de los cinco grupos de IA;
`e1p_aiadmin` con `group_ai_admin` y sin `base.group_system`):

| Usuario | Esperado |
|---|---|
| `admin` (2) | activo, interno, Ajustes, los cinco grupos de IA, contraseña local; clave MCP `not_generated` y sin hash (revocada en E3′, D.3). `lang` = `es_ES` (decide qué columnas de V5 y V6 se miran: `_es` o `_en`) |
| `demo` (6) | **inactivo** (archivado en E3′), interno, sin Ajustes, `grupos_ia` vacío |
| `e1p_aiadmin` (19) | **inactivo**, interno, sin Ajustes, `group_ai_admin` (y los que implica) y `group_ai_conversational` (así se creó en E1′) |
| `u1` (8) | activo, interno, con `group_ai_conversational`; clave MCP `generated` (la usa para R8, D.4) |
| `e4p_*` | ninguno |

Si `demo` o `e1p_aiadmin` no encajan, C dice qué hacer. No se toca nada aquí.

### A.6 Proveedores y casilla «Design»

**[LECTURA]** La consulta de A.7 de E3′, sin leer `api_key`:

```bash
e4sql <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT id, name, model_name, active, fit_conversation, fit_design FROM ai_provider ORDER BY id;
SELECT a.code AS agente, ap.priority, ap.active, p.id AS proveedor_id, p.name AS proveedor, p.active AS proveedor_activo
  FROM ai_agent_provider ap
  JOIN ai_agent a ON a.id = ap.agent_id
  JOIN ai_provider p ON p.id = ap.provider_id
 ORDER BY a.code, ap.priority, ap.id;
ROLLBACK;
SQL
```

Esperado (E3′, G, A.7): Gemini 3.6 flash (1), «Proveedor fuera de cadena» (2, inactivo), Gemini 3.5 flash
(3) y Gemini 3.5 flash lite (4); «Design» en `t` en los tres Gemini (se dejó así para esta subida: plan, §4,
«Staging `pns_demo`, tras E3′»). **Se anotan los ids** con sus casillas: D.2 los usa para poner y quitar
«Design». P-33 del script toma el primer `ai.provider` activo por id (en E3′, el 1).

Cuota: **solo Sergio**, «Test Connection» de los Gemini y, si puede, la consola de Google AI Studio (F de
E1′). Esta subida tiene unos cinco turnos de chat con el modelo (T1, el segundo turno, F1 con texto y tabla,
V2 y R8); el botón Canvas no llama al modelo. **Hacer «Test Connection» antes de C:** escribe en el
proveedor y en `ai_log` (plan, apartado E4′, fila «Test Connection escribe en el proveedor»), y la consulta de
P-30 (D.1) mira las filas de `admin` desde 5 minutos antes de `rpc`.

---

## B. Despliegue y `-u`

El orden de E3′: archivo (B.1 a B.4, sin tocar `pns_demo`), copia (B.5), parar y sustituir (B.6), `-u` (B.7),
log y arranque (B.8).

### B.1 En el equipo de Sergio: archivo del commit

**[LECTURA del repo]** Lo ejecuta Sergio (el agente no usa git):

```bash
cd ~/GitHub/third_party
git cat-file -t 8d218ea
git log --oneline 8d218ea..HEAD -- pns_base pns_ai_mcp pns_ai_chatboo
git archive --format=tar.gz -o /tmp/pns_addons_8d218ea.tar.gz 8d218ea pns_base pns_ai_mcp pns_ai_chatboo
sha256sum /tmp/pns_addons_8d218ea.tar.gz
```

Esperado: `commit`; ninguna línea en el `git log` (ningún commit posterior toca los módulos); la huella del
`.tar.gz` **se anota** (no está calculada: el `.tar.gz` lleva el id del commit en la cabecera, y con
`a06d393` saldría otra aunque el árbol sea el mismo). La huella del árbol se comprueba en B.4.

### B.2 Copia al VPS

**[ALTERA solo `/tmp` del VPS]**

```bash
read -rp 'Puerto SSH del VPS: ' VPS_PORT; read -rp 'Usuario@host del VPS: ' VPS_DEST
scp -P "$VPS_PORT" /tmp/pns_addons_8d218ea.tar.gz "$VPS_DEST":/tmp/
```

### B.3 En el VPS: huella y extracción

**[LECTURA]** `sha256sum /tmp/pns_addons_8d218ea.tar.gz` (la de B.1).

**[ALTERA solo `/tmp`]**

```bash
rm -rf /tmp/pns_addons_E4p && mkdir /tmp/pns_addons_E4p && tar -xzf /tmp/pns_addons_8d218ea.tar.gz -C /tmp/pns_addons_E4p
```

### B.4 Comprobaciones del código extraído

**[LECTURA]**

```bash
cd /tmp/pns_addons_E4p
grep -n "'version'" pns_base/__manifest__.py pns_ai_mcp/__manifest__.py pns_ai_chatboo/__manifest__.py
grep -rn "Seges: parche" pns_base pns_ai_mcp pns_ai_chatboo --include=*.py --include=*.js --include=*.xml | grep -v '/tests/' | wc -l
for n in 30 31 32 33 34; do printf 'parche %s: ' $n; grep -rn "Seges: parche $n " pns_base pns_ai_mcp pns_ai_chatboo | grep -v '/tests/' | wc -l; done
grep -c 'def _check_log_user(' pns_ai_mcp/models/ai_execution_engine.py
grep -c 'Only the system can call chat_completion' pns_ai_mcp/models/ai_execution_engine.py
grep -c 'def _check_settings_admin(' pns_ai_mcp/models/ai_trusted_action.py
grep -c 'def month_usage(' pns_ai_mcp/models/ai_provider.py
grep -c "check_access_rights('create')" pns_ai_mcp/wizard/ai_provider_usage_wizard.py
grep -c 'def watch_no_page(' pns_ai_chatboo/models/chatboo_canvas.py
grep -c "'original_content': _content" pns_ai_chatboo/models/chatboo_async_request.py
grep -c '^import html' pns_ai_chatboo/models/chatboo_async_request.py
sha256sum pns_ai_chatboo/models/chatboo_async_request.py pns_ai_chatboo/models/chatboo_canvas.py
ls pns_ai_mcp/tests/test_seges_e4p.py
find pns_base pns_ai_mcp pns_ai_chatboo -type f | wc -l
find pns_base pns_ai_mcp pns_ai_chatboo -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum
```

Esperado (calculado el 06/11/2026 sobre la copia de trabajo; entre paréntesis, lo que da el archivo de
`522ce6e`, para ver que cada línea distingue el código nuevo):

| Comprobación | Esperado |
|---|---|
| Versiones | `1.2.47`, `3.1.879`, `2.1.538` (sin cambios) |
| Marcadores «Seges: parche» fuera de tests | 142 (113): los 113 de E1′ a E3′ y 29 de E4′ |
| Por parche (30 a 34) | 8, 1, 5, 3, 12 |
| Parche 30: `def _check_log_user(` | 1 (0) |
| Parche 31: mensaje de `chat_completion` | 1 (0) |
| Parche 32: `def _check_settings_admin(` | 1 (0) |
| Parche 33: `def month_usage(` / `check_access_rights('create')` | 0 / 1 (1 / 0) |
| Parche 34: `def watch_no_page(` / `'original_content': _content` / `import html` | 1 / 1 / 1 (0 / 0 / 0) |
| Huellas de los dos archivos del parche 34 | `c97e6a7b…` (`chatboo_async_request.py`) y `e470e7a7…` (`chatboo_canvas.py`), las del registro |
| Test nuevo | `test_seges_e4p.py` presente |
| Archivos / huella del árbol | 711 / `e37be448…1844` (A.3) |

Si algo no coincide, **no seguir**. Si solo difiere la huella del árbol y lo demás coincide, se anota y decide
Sergio (A.3 la calculó sin git).

### B.5 Copia del código actual

**[ALTERA]** Crea `/opt/odoo/pns_staging/addons_antes_E4p` con el código de `522ce6e`:

```bash
cd /opt/odoo/pns_staging && test ! -e addons_antes_E4p && cp -a addons addons_antes_E4p && ls -d addons_antes_*
df -h /opt/odoo
```

### B.6 Parar Odoo y sustituir el código

**[ALTERA]** Para `web` (`odoo14_pns`). `pns_demo` deja de responder hasta B.8:

```bash
cd /opt/odoo/pns_staging && docker compose stop web && docker compose ps
```

**[LECTURA]** Ensayo del `rsync`: **no debe listar ninguna baja** (0, «Diferencias con E3′»):

```bash
for m in pns_base pns_ai_mcp pns_ai_chatboo; do rsync -ani --delete /tmp/pns_addons_E4p/$m/ /opt/odoo/pns_staging/addons/$m/ | grep '^\*deleting'; done
```

**[ALTERA]** Sustitución, módulo a módulo, como `ubuntu` y sin `sudo`:

```bash
for m in pns_base pns_ai_mcp pns_ai_chatboo; do rsync -a --delete /tmp/pns_addons_E4p/$m/ /opt/odoo/pns_staging/addons/$m/; done
```

**[LECTURA]** Verificación:

```bash
cd /opt/odoo/pns_staging/addons
find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l
find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum
cd /opt/odoo/pns_staging && LC_ALL=C diff -rq addons_antes_E4p addons > /tmp/pns_diff_E4p.txt; wc -l < /tmp/pns_diff_E4p.txt
grep -c '^Files ' /tmp/pns_diff_E4p.txt; grep -c '^Only in addons/' /tmp/pns_diff_E4p.txt; grep -c '^Only in addons_antes_E4p' /tmp/pns_diff_E4p.txt
```

Esperado: 711 archivos y la huella de B.4. En el `diff -rq`, 11 líneas: 10 archivos distintos, 1 solo en
`addons` (`pns_ai_mcp/tests: test_seges_e4p.py`) y 0 solo en `addons_antes_E4p` (calculado el 06/11/2026
entre el archivo de `522ce6e` y la copia de trabajo). Si `diff -rq` lista también `__pycache__`, se descuentan.

### B.7 `-u` de `pns_ai_mcp`

**[ALTERA `pns_demo`, sin copia (N9)]** Recarga los XML de datos, la seguridad y las vistas de `pns_ai_mcp`
y, por la dependencia (0, «Matiz»), también los de `pns_ai_chatboo` (el único módulo instalado que depende de
`pns_ai_mcp`: se comprueba en A.4 a). No cambia el esquema. Un registro de
datos de estos módulos sin `noupdate` retocado a mano desde E3′ volvería al valor del módulo; no consta
ninguno. Las casillas «Design» son datos del usuario: el `-u` no las toca (se comprueba en C.3).

```bash
cd /opt/odoo/pns_staging && docker compose run --rm -T web odoo -u pns_ai_mcp -d pns_demo --stop-after-init 2>&1 | tee /tmp/pns_u_E4p.log
```

### B.8 Revisar el log y arrancar

**[LECTURA]**

```bash
L=/tmp/pns_u_E4p.log
grep -cE 'Traceback|ERROR|CRITICAL' $L
grep -c 'Deleting field' $L
grep -E 'No module named|module .* not (found|installable)' $L
grep -cE 'Only a Settings administrator can change trusted actions' $L
grep -E 'Loading module (pns_ai_mcp|pns_ai_chatboo) |Module (pns_ai_mcp|pns_ai_chatboo) loaded in' $L
for m in pns_ai_mcp pns_ai_chatboo; do printf '%s: ' $m; grep -c "loading $m/" $L; done
grep 'WARNING' $L | sed 's/.* WARNING [^ ]* //' | sort | uniq -c
grep -E 'Modules loaded\.|modules loaded in' $L | tail -2
```

Esperado: 0 `Traceback`, `ERROR` y `CRITICAL`; 0 «Deleting field»; ningún módulo que no se importe; **0
rechazos del parche 32** durante la carga de `trusted_actions_system.xml`; cuatro líneas de carga, en INFO:
`Loading module pns_ai_mcp (<i>/<n>)` y `Module pns_ai_mcp loaded in <s>s, <q> queries`, y las dos de
`pns_ai_chatboo` (en Odoo 14, `odoo/modules/loading.py:160-169` y `:295-301`: en INFO solo los módulos que se
actualizan; los demás, en DEBUG); una línea `loading <módulo>/<archivo>` por archivo de datos (`load_data`,
`loading.py:65`): **61** de `pns_ai_mcp` y **13** de `pns_ai_chatboo` (los de `data` de sus manifiestos; sin
`demo`); y al final `Modules loaded.` (`loading.py:562`) y `<n> modules loaded in …` (`loading.py:309`, nivel
RUNBOT, que se escribe como INFO). En Odoo 14 no hay ninguna línea «Registry loaded». Si no sale ninguna de
estas líneas, el log del staging va con un nivel por encima de INFO: se anota y se mira el log a mano.
`WARNING`: como referencia, los de E2′ y E3′ (etiquetas repetidas de `ai.log` «Client» y
`ai.trusted.action` «Model», `skip retired unlink for pns_ai_mcp` y dos `DeprecationWarning` de
`distutils`); se anotan los que salgan.

**Si hay `Traceback`, `ERROR` o `CRITICAL`: no arrancar** y decidir con el apartado E.

**[ALTERA]** Arranca `web`:

```bash
cd /opt/odoo/pns_staging && docker compose start web && docker compose ps
docker inspect -f '{{.State.StartedAt}}' odoo14_pns
```

Se anota `StartedAt` (el **reinicio**; lo usa la orden del log de D.4).

**[LECTURA]** Tras uno o dos minutos:

```bash
cd /opt/odoo/pns_staging && docker compose logs --since 10m web 2>&1 | grep -cE 'Traceback|ERROR|CRITICAL'
curl -sS -o /dev/null -w '%{http_code}\n' https://pns.liyben.com/web/login
curl -sS -o /dev/null -w '%{http_code}\n' https://pns.liyben.com/mcp
```

Esperado: 0; `200`; `403`.

**[ALTERA solo `/tmp`]** Borrar `/tmp/pns_addons_8d218ea.tar.gz` y `/tmp/pns_addons_E4p`. El log y el diff se
conservan hasta anotar los resultados.

---

## C. Usuarios de prueba y comprobaciones posteriores

### C.1 Módulos, crons y acciones de confianza

**[LECTURA]** El bloque de A.4 a (sin la consulta de actividad).

Esperado: igual que en A.4 a: versiones sin cambio; 7 crons, el de `cleanup_expired` como antes; **9
acciones de confianza, el mismo `max(id)`** (el `-u` las reescribe en su sitio, no las crea de nuevo) y 0
restos; ninguna fila `odoo_dev.%`.

### C.2 Usuarios de prueba (decisión 4 de E4′.h)

**[ALTERA `pns_demo`]** Los autoriza y hace Sergio, en la interfaz (Ajustes → Usuarios y compañías →
Usuarios; los archivados, con el filtro «Archivado»). Contraseñas **nuevas, solo para la prueba y de 8
caracteres o más**: el filtro del script solo tapa en su salida las de 8 o más (una corta taparía trozos de
otras palabras). Ninguna se escribe en este documento ni en G.

| Etiqueta | Usuario | Qué se hace | Para |
|---|---|---|---|
| ADM | `admin` (2) | Nada en sus grupos. **Clave MCP temporal** (desde su ficha de Usuarios MCP) para usar Chatboo, si A.5 la da en `not_generated` | `preparar`, `rpc` (P-30 como objetivo, P-33.5 y P-32.5), `limpiar`; Chatboo en D.2 y D.3 |
| DEMO | `demo` (6) | **Desarchivar** («Acción → Desarchivar») y «Acción → Cambiar contraseña». Queda como **interno sin grupos de IA** | `rpc`: P-30, P-31 y P-33.1 a P-33.4 |
| AA | `e1p_aiadmin` (19) | **Desarchivar** y «Cambiar contraseña», **si sus grupos de A.5 encajan** (interno, `group_ai_admin`, sin Ajustes). **Si no encajan:** no se le cambian los grupos; se crea `e4p_aiadmin` (nombre «Seges E4p AI admin», login sin `@`, «Usuario interno», AI Administrator, sin Ajustes) con contraseña nueva, y en D.1 se exporta `E4P_AIADMIN=e4p_aiadmin` | `rpc`: P-32.1 a P-32.4 |
| U1 | `u1` (8) | Nada | R8 (D.4) |

- `e1p_aiadmin` está archivado porque una fila del diario de la prueba 2b de E1′ lo referencia (plan, §4): no
  se borra, se vuelve a archivar en F.
- Si `demo` tuviera algún grupo de IA (A.5), **no se le quita**: se para y decide Sergio (la alternativa
  equivalente es un `e4p_interno` nuevo, interno sin IA, con `E4P_INTERNO=e4p_interno`).
- Con un login sin `@` no se envía invitación (E3′, D.0, paso 4).

**[LECTURA]** Después, la consulta de A.5. Esperado: `demo` y el AA, **activos**, con los mismos grupos que en
A.5 y contraseña local; la clave de `admin` en `generated`. Se anota qué usuarios se desarchivaron o crearon:
son los que F vuelve a archivar.

### C.3 Casillas «Design» tras el `-u`

**[LECTURA]** La consulta de A.6. Esperado: las mismas casillas que en A.6 (el `-u` no las toca).

---

## D. Pruebas

**Orden** (lo que crea filas de `ai_log` de `admin` va **después** de la consulta de P-30):
1. D.1: script por el túnel (`preparar`, `rpc`, consulta de P-30, `limpiar` dos veces).
2. D.2 y D.3, fase 1, **sin «Design» en ningún proveedor**: T1 con V5 y V6, el segundo turno, recargar, el
   botón Canvas (Paso 1), copiar y exportar; F1 con texto y tabla (D.3).
3. D.2, fase 2, **con «Design» en alguno**: V2 y V3.
4. **«Design» solo en Gemini 3.5 flash** (decisión 2 de E4′.h) y D.4 (R8 y log).
5. F (limpieza).

### D.1 Script de E4′ por el túnel SSH (parches 30 a 33)

**Script:** [`scripts_e4/pruebas_e4p.py`](scripts_e4/pruebas_e4p.py) (SHA-256
`76f781f6e462c52856fbafaeb0d33ac677169af27c8fc826322e724013fa9b03`, la de `a06d393`; esa versión se validó en
el laboratorio el 09/11/2026, 16/16 OK). Solo biblioteca estándar;
XML-RPC, sin claves MCP ni etiqueta de cliente MCP. Pide las contraseñas con `getpass`, una por usuario y
solo cuando hace falta, y no imprime secretos.
- **Variables:** `E4P_URL` y `E4P_DB`, obligatorias (sin valor por defecto: no apunta a ningún sitio si se
  olvidan); `E4P_STATE`, por defecto `~/staging_e4p/estado_e4p.json` (se deja así); `E4P_ADMIN` (`admin`),
  `E4P_INTERNO` (`demo`) y `E4P_AIADMIN` (`e1p_aiadmin`).
- **Estado ligado a URL y BD:** si el archivo de estado es de otro servidor o BD, para. Por eso `preparar`,
  `rpc` y `limpiar` van **siempre por la misma URL** (la del túnel).
- **503:** reintenta 3 veces cada 15 s; si sigue, para con código 2 y **se repite el paso**. El estado se
  guarda tras cada creación: **no hay que tocarlo**.
- **Salida:** 0 todo OK; 1 alguna comprobación FALLO; 2 parada (precondición, conexión, autenticación o
  estado). `rpc` deja además la tabla en `~/staging_e4p/resultado_e4p_<fecha>.txt`.
- **Escribe en `pns_demo`:** `preparar` crea la acción de confianza `seges.e4p` (archivada, solo para Ajustes,
  sobre `res.partner` con `fields_get`, que solo lee); `rpc` no debería crear nada (si P-32.2 o P-32.3 crean,
  guarda los ids en el estado); `limpiar` borra las `seges.e4p*` y los ids del estado.

**Túnel, en el equipo de Sergio** (el de E3′, G: puerto 8169 del VPS en el 18169 local, sin pasar por Nginx
ni su límite de `/xmlrpc`). La forma exacta de la orden no quedó escrita en E3′: **«Sin confirmar»**, la de
abajo es la habitual. **[LECTURA]** En una terminal aparte, que se deja abierta:

```bash
read -rp 'Puerto SSH del VPS: ' VPS_PORT; read -rp 'Usuario@host del VPS: ' VPS_DEST
ssh -p "$VPS_PORT" -N -L 18169:127.0.0.1:8169 "$VPS_DEST"
```

En otra terminal del equipo:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:18169/web/login
# esperado: 200
mkdir -p ~/staging_e4p && chmod 700 ~/staging_e4p
cp ~/GitHub/third_party/docs/pendiente/scripts_e4/pruebas_e4p.py ~/staging_e4p/
cd ~/staging_e4p && sha256sum pruebas_e4p.py
# esperado: 76f781f6…9b03
test ! -e ~/staging_e4p/estado_e4p.json && echo libre
export E4P_URL=http://localhost:18169 E4P_DB=pns_demo
# solo si C.2 creó e4p_aiadmin: export E4P_AIADMIN=e4p_aiadmin
```

**1. `preparar`.** **[ALTERA `pns_demo`]** Pide la contraseña de `admin`.

```bash
cd ~/staging_e4p && python3 pruebas_e4p.py preparar; echo "salida: $?"
```

Esperado: `seges.e4p creada (ai.trusted.action <id>), archivada y solo para Ajustes`, `Estado:
…/staging_e4p/estado_e4p.json` y `salida: 0`. El `<id>` es normalmente el `max(id)` de A.4 a + 1 (la
secuencia puede ir por delante: en el laboratorio, la 10 el 06/11 y la 11 el 09/11). Si ya existiera:
`seges.e4p ya existe (ai.trusted.action <id>): se reutiliza`.

**2. `rpc`.** **[ALTERA `pns_demo` solo si un parche no está]** Pide las contraseñas de `demo`, del AA y de
`admin`, en ese orden (la de `admin`, después de la precondición). **Antes:** nadie usa Chatboo ni «Test
Connection» como `admin` desde 5 minutos antes (la consulta de P-30 los contaría).

```bash
cd ~/staging_e4p && python3 pruebas_e4p.py rpc; echo "salida: $?"
```

Esperado: `Precondición (D3): demo es interno sin grupos de IA; e1p_aiadmin es AI Administrator sin
Ajustes`, `t0 (UTC): <fecha>` (se anota), la consulta de P-30, `ai.provider <id>`, la tabla, `16
comprobaciones: 16 OK, 0 FALLO`, `Tabla copiada en …` y `salida: 0`. La tabla esperada es la del
laboratorio (06/11/2026):

| Comprobación | Usuario | Esperado | Detalle esperado |
|---|---|---|---|
| P-30.1 | `demo` | AccessError (30) `log_role_without_provider` | `AccessError: Only the system can write AI History rows for another user.` |
| P-30.2 | `demo` | AccessError (30) `log_provider_llm_request` | el mismo |
| P-30.3 | `demo` | AccessError (30) `log_provider_llm_response` | el mismo |
| P-30.4 | `demo` | AccessError (30) `log_llm_inference` | el mismo |
| P-30.5 | `demo` | AccessError (30) `log_provider_inference` | el mismo |
| P-31 | `demo` | AccessError (31) | `AccessError: Only the system can call chat_completion.` (con un agente que no existe: sin el parche daría `UserError`) |
| P-33.1 | `demo` | AttributeError (no existe) | `AttributeError: type object 'ai.provider' has no attribute 'month_usage'` |
| P-33.2 | `demo` | AccessError (método privado) | `Private methods (such as _month_usage) cannot be called remotely.` (lo rechaza el core por ser privado: no distingue si el parche está; lo distingue P-33.1) |
| P-33.3 | `demo` | `default_get`: AccessError y sin cifras | `AccessError (ACL): You are not allowed to create 'Provider usage this month' (ai.provider.usage.wizard) records.` |
| P-33.4 | `demo` | `onchange`: AccessError y sin cifras | el mismo |
| P-33.5 | `admin` | `default_get`: ok y llegan las cifras | `llegan las claves: prompt_tokens, completion_tokens, total_tokens, cost_display` (sin valores) |
| P-32.1 | AA | AccessError (32) write del label | `AccessError: Only a Settings administrator can change trusted actions.` |
| P-32.2 | AA | AccessError (32) create de `seges.e4p.b` | el mismo |
| P-32.3 | AA | AccessError (32) copy | el mismo |
| P-32.4 | AA | AccessError (32) unlink | el mismo |
| P-32.5 | `admin` | sin cambios | `igual (write_date incluido)` |

Lecturas de un `FALLO`: «respondió sin error» o «se ejecutó (devolvió None)» (`cannot marshal None`) = ese
parche no está; «rechazado, pero no por el parche» = otro rechazo (se anota la línea); «creó/copió
ai.trusted.action N» = el parche 32 no está (el id queda en el estado y lo borra `limpiar`). Una parada en
la precondición (salida 2) dice qué grupo sobra o falta: volver a C.2.

**3. Consulta de P-30, en el VPS.** **[LECTURA]** Justo después de `rpc`. Se pega con `e4sql <<'SQL'` … `SQL`
**la consulta que imprimió el script** (está también en el archivo de resultado), con `t0` y el uid de
`admin` ya puestos. Su forma:

```sql
SELECT id, create_date, user_id, create_uid, endpoint, primitive,
       provider_id, total_tokens, cost_usd, left(result_summary, 60) AS resumen
  FROM ai_log
 WHERE endpoint = 'seges_e4p_staging'
    OR (user_id = 2 AND create_date >= '<t0 - 300 s>')
 ORDER BY id;
```

Esperado: **0 filas** (como en el laboratorio). Una fila con `user_id` 2 y `create_uid` de `demo` sería
P-30 roto; una con `create_uid` 2 sería actividad de `admin` en la ventana (se anota y se mira su `endpoint`).

**4. `limpiar`, dos veces.** **[ALTERA `pns_demo`]** Pide la contraseña de `admin` cada vez.

```bash
cd ~/staging_e4p && python3 pruebas_e4p.py limpiar; echo "salida: $?"
python3 pruebas_e4p.py limpiar; echo "salida: $?"
```

Esperado: la primera, `Acciones de confianza borradas: 1 [<id de preparar>]` y `Queda el archivo de estado:
…`; la segunda, `Acciones de confianza borradas: 0`; las dos con `salida: 0`. Después, **[LECTURA]** el bloque
de A.4 a: 9 acciones y 0 restos `seges.e4p`.

| Paso | Qué anotar | Obtenido |
|---|---|---|
| `preparar` | id de `seges.e4p`; salida | [x] `ai.trusted.action` 10; salida 0 |
| `rpc` | `t0`; id del proveedor; OK/FALLO (16); reintentos 503; salida; archivo de resultado | [x] t0 2026-11-09 10:03:19; proveedor 1; 16 OK / 0 FALLO; sin 503; salida 0; `resultado_e4p_20261109-110323.txt` |
| Consulta de P-30 | número de filas | [x] 0 filas |
| `limpiar` ×2 | borradas 1 y 0; salidas | [x] 1 [10] y 0; salidas 0 |

### D.2 Parche 34: aviso del lienzo (T1, V2, V3, V5, V6, botón Canvas, copiar y exportar)

**Quién:** ADM (`admin`, con la clave MCP temporal de C.2), en Chatboo, F12 abierto. Las respuestas del
modelo cambian de una vez a otra: se juzga por el SQL y por lo que se ve, no por lo que diga el chat.

**Consultas de esta parte.** **[LECTURA]** `SESION=<id>` se asigna antes de cada una.

*Sesiones de `admin`* (para sacar el id de cada conversación nueva):

```bash
e4sql <<'SQL'
SELECT id, create_date, canvas_open, canvas_rev, md5(messages) AS huella,
       jsonb_array_length(messages::jsonb) AS mensajes
  FROM chatboo_session WHERE user_id = 2 ORDER BY id DESC LIMIT 3;
SQL
```

*V5 y V6* (las del plan, apartado E4′, «Ajuste de las validaciones del parche 34», tal cual):

```bash
e4sql <<'SQL'
BEGIN TRANSACTION READ ONLY;
-- V5: último mensaje del asistente de la sesión :sesion
WITH ult AS (
  SELECT e.ord AS pos, e.msg
    FROM chatboo_session s,
         jsonb_array_elements(s.messages::jsonb) WITH ORDINALITY AS e(msg, ord)
   WHERE s.id = :sesion AND e.msg->>'role' = 'assistant'
   ORDER BY e.ord DESC LIMIT 1)
SELECT pos,
       position('No page was built. The reason is in the AI History.' IN coalesce(msg->>'content', '')) > 0 AS content_en,
       position('No se ha creado la página. El motivo está en el Historial IA.' IN coalesce(msg->>'content', '')) > 0 AS content_es,
       msg ? 'original_content' AS hay_original,
       coalesce(msg->>'original_content', '') = '' AS original_vacio,
       position('No page was built. The reason is in the AI History.' IN coalesce(msg->>'original_content', '')) > 0 AS original_en,
       position('No se ha creado la página. El motivo está en el Historial IA.' IN coalesce(msg->>'original_content', '')) > 0 AS original_es
  FROM ult;
-- V5 (complemento): canvas_rev y el último job de la sesión
SELECT s.id, s.canvas_rev, r.id AS job, r.state,
       position('No se ha creado la página. El motivo está en el Historial IA.' IN coalesce(r.response, '')) > 0 AS response_es,
       position('No page was built. The reason is in the AI History.' IN coalesce(r.response, '')) > 0 AS response_en
  FROM chatboo_session s
  LEFT JOIN LATERAL (SELECT * FROM chatboo_async_request WHERE session_id = s.id ORDER BY id DESC LIMIT 1) r ON true
 WHERE s.id = :sesion;
-- V6: historial que recibió el motor en cada job de la sesión
SELECT id, create_date, state,
       position('No page was built. The reason is in the AI History.' IN coalesce(history, '')) > 0 AS historia_en,
       position('No se ha creado la página. El motivo está en el Historial IA.' IN coalesce(history, '')) > 0 AS historia_es,
       position('No page was built. The reason is in the AI History.' IN coalesce(done_meta, '')) > 0 AS done_meta_en,
       position('No se ha creado la página. El motivo está en el Historial IA.' IN coalesce(done_meta, '')) > 0 AS done_meta_es
  FROM chatboo_async_request
 WHERE session_id = :sesion
 ORDER BY id;
ROLLBACK;
SQL
```

*Forma del aviso y jobs del botón Canvas* (nueva; validada en el laboratorio el 06/11/2026: en la sesión 23,
`historia_html` = t en el job 54; jobs 3 y 4 en `error`):

```bash
e4sql <<'SQL'
BEGIN TRANSACTION READ ONLY;
-- Cómo empieza y cómo acaba el último mensaje del asistente (F1: '</em></p>' si empieza por '<')
WITH ult AS (
  SELECT e.msg
    FROM chatboo_session s,
         jsonb_array_elements(s.messages::jsonb) WITH ORDINALITY AS e(msg, ord)
   WHERE s.id = :sesion AND e.msg->>'role' = 'assistant'
   ORDER BY e.ord DESC LIMIT 1)
SELECT left(ltrim(msg->>'content'), 1) = '<' AS empieza_por_menor,
       position('<table' IN coalesce(msg->>'content', '')) > 0 AS con_tabla,
       right(rtrim(msg->>'content'), 9) = '</em></p>' AS aviso_html,
       right(rtrim(msg->>'content'), 1) = '_' AS aviso_markdown,
       (msg->>'content') = (msg->>'original_content') AS content_igual_original
  FROM ult;
-- El aviso en el historial que guarda cada job, con su HTML
SELECT id, state,
       position('<p><em>No se ha creado la página. El motivo está en el Historial IA.</em></p>' IN coalesce(history, '')) > 0 AS historia_html
  FROM chatboo_async_request WHERE session_id = :sesion ORDER BY id;
-- Jobs del botón Canvas de la sesión
SELECT id, msg_index, state, left(error, 70) AS error, started_at, finished_at
  FROM chatboo_canvas_job WHERE session_id = :sesion ORDER BY id;
ROLLBACK;
SQL
```

*Motivo del rechazo en `ai_log`* (desde unos minutos antes del turno):

```bash
e4sql <<'SQL'
SELECT id, create_date, endpoint, left(regexp_replace(coalesce(result_summary, ''), '[[:space:]]+', ' ', 'g'), 120) AS resumen
  FROM ai_log
 WHERE user_id = 2 AND create_date > now() - interval '15 minutes'
   AND (result_summary ILIKE 'No page was built%' OR result_summary ILIKE 'Design %')
 ORDER BY id;
SQL
```

**Fase 1: sin «Design» en ningún proveedor activo.** **[ALTERA la configuración del staging]** Sergio
desmarca «Design» (AI Engine → Providers) en todos los proveedores activos, sin tocar «Conversación».
Comprobación: la consulta de A.6, ningún activo con `fit_design` = `t`.

| # | Prueba | Qué se hace | Esperado | Qué anotar | Obtenido |
|---|---|---|---|---|---|
| T1 | **Disparador** | Conversación nueva; exactamente: «Hazme una página con los cinco primeros contactos ordenados por nombre, solo con su id y su nombre. Una página nueva; no escribas la tabla en el chat.» Mirar la burbuja **mientras escribe** (D.3) y al terminar. Después, sesiones de `admin` (id → `SESION`), V5, forma del aviso y `ai_log` | No se crea página. En `ai_log`, una fila «No page was built…». La burbuja termina con «*No se ha creado la página. El motivo está en el Historial IA.*» en cursiva y en su propio párrafo, al cerrar el turno o tras recargar (no en vivo). V5: `content_es` = t, `hay_original` = t, `original_es` = t; complemento: `canvas_rev` 0, job `done`, `response_es` = t. Forma: si `empieza_por_menor` = t, `aviso_html` = t; si no, `aviso_markdown` = t; `content_igual_original` = t | id de sesión y de job; cuándo apareció el aviso; las columnas de V5 y de la forma; la fila de `ai_log` y su texto; modelo que contestó | [x] OK (sesión 59, job 200; aviso al cerrar el turno; V5 y forma como se esperaba; filas 1690/1691 y 1694/1695; Gemini 3.6 flash) |
| V5′ | **Copiar y exportar** (burbuja de T1, sin recargar) | Icono de copiar; PDF, DOCX y, si la burbuja lleva tabla, XLSX | Copiar: si hay tabla, **solo la tabla** (lee `clip_data`, del fabricante), sin aviso; sin tabla, se anota qué copia. PDF y DOCX **con el aviso en párrafo aparte**. XLSX con tabla, **sin** el aviso. Si el mensaje es de una sola tabla (`o_ai_table_block`), el PDF/DOCX **sin HTML crudo** | qué copia; aviso sí/no en cada archivo; HTML crudo sí/no | [x] OK (copiar sin aviso; PDF y `.doc` con aviso en párrafo aparte, sin HTML crudo; XLSX sin aviso) |
| V6 | **Segundo turno sin recargar** (misma sesión) | «Escribe aquí en el chat esa misma tabla.» Después, V6 y la forma del aviso | Job 2 con `historia_es` = t y `historia_html` = t (el aviso entra en el historial que guarda el job, con su HTML; D.3). El segundo turno no lleva aviso propio si no hay rechazo | ids de los dos jobs; `historia_es` y `historia_html` de cada uno; si el turno 2 tiene tabla | [x] OK (jobs 200 y 201; `historia_es` y `historia_html` t en el 201; turno 2 con tabla, sin aviso propio) |
| BC | **Botón Canvas (Paso 1)** | Huella (consulta de sesiones) antes; botón Canvas de la respuesta con tabla del turno 2; esperar a que acabe; jobs del botón Canvas; huella después | Job de `chatboo.canvas.job` en `error` con «No se ha creado la página. El motivo está en el Historial IA.» y `started_at` = `finished_at` (sin llamar al modelo). **En pantalla, ningún aviso explícito:** solo el borde rojo del botón y el motivo en el tooltip, sin toast ni diálogo (defecto del fabricante, al informe; plan, §3.2). La sesión, sin cambios (misma huella y mismos mensajes) | id del job; qué se ve (borde, tooltip, nada más); huella antes y después | [x] OK (job 1 en `error`, sin llamar al modelo; huella igual; borde rojo, sin tooltip) |
| R34 | **Recargar y cambiar de sesión** | Recargar el navegador (F5) y abrir la sesión; después, otra sesión y volver. V5 en cada momento | La burbuja de T1 sigue con el aviso, bien formado. V5 igual que en T1. La huella puede cambiar (el cliente reescribe `messages`), sin perder el aviso | V5 tras recargar y tras volver; huella | [x] OK (aviso conservado tras recargar y tras cambiar de sesión; huella `5670c960…`) |

**Fase 2: «Design» en alguno** (decisión 2 de E4′.h). **[ALTERA la configuración]** Sergio marca «Design» en
Gemini 3.6 flash y Gemini 3.5 flash (ids de A.6; como los proveedores 1 y 2 del laboratorio), no en `lite`.
Comprobación: la consulta de A.6.

| # | Prueba | Qué se hace | Esperado | Qué anotar | Obtenido |
|---|---|---|---|---|---|
| V2 | **Con «Design», sin aviso** | Conversación nueva con el mismo texto de T1. Sesiones, V5, V6 y `ai_log` (con «Qué modelo diseñó» de E3′, D.1, si hace falta) | Página creada (`canvas_rev` 1), la tarjeta se abre; **sin aviso** en la burbuja, en `messages` (`content_es` y `original_es` = f), en `response` ni en `done_meta`; `ai_log` con «Design laid out the page in … s» | id de sesión y job; `canvas_rev`; modelo que diseñó | [x] OK (sesión 60, job 202, `canvas_rev` 1; sin aviso; Gemini 3.6 flash diseñó) |
| V3 | **Botón Canvas sin «Design», con el chat abierto** | Con «Design» marcado, abrir la sesión de T1 (respuesta con tabla del turno 2). En **otra pestaña**, quitar «Design» de los dos, **sin recargar el chat**, y pulsar Canvas. Huella antes y después; jobs del botón Canvas | Job en `error` con el aviso, sin llamar al modelo; **sin aviso duplicado** en la burbuja; la sesión **sin cambios** (misma huella y mismos mensajes); en pantalla, lo mismo que en BC | id del job; huella antes y después; número de mensajes | [x] no concluyente (sin botón «Lienzo» en la sesión 59; en la 61, el modelo creó página) |

Al terminar V3 no queda «Design» en ningún proveedor: el estado final se pone en D.4.

### D.3 Lo que queda «Sin confirmar» del parche 34 y se mira en el staging

| # | Qué | Cómo se mira | Esperado / cómo se lee | Obtenido |
|---|---|---|---|---|
| F1-t | **Texto + tabla embebida.** El criterio de F1 («empieza por `<`») no detecta una respuesta que empieza por texto y lleva una tabla: usaría el markdown y la burbuja (que sí entra por la rama de HTML embebido) podría pintar el aviso con los `_` literales ([parches](parches_pns_ai.md), E4′.b2 y E4′.b3, «Frontera texto + tabla») | En la **fase 1** (sin «Design»), conversación nueva: «Escribe primero una frase que resuma lo que vas a hacer y después, aquí en el chat, una tabla con los cinco primeros contactos ordenados por nombre, con su id y su nombre. Después hazme una página nueva con esa tabla.» Forma del aviso y V5 | Si sale `empieza_por_menor` = f y `con_tabla` = t: es el caso; se anota `aviso_markdown` y **cómo se ve el aviso en la burbuja** (cursiva o con `_` literales) tras recargar. Si sale `empieza_por_menor` = t o `con_tabla` = f, **no concluyente** (el modelo no dio la forma buscada); se puede repetir una vez | [x] no concluyente (sesión 62: empieza por `<`; aviso en HTML, en cursiva) |
| Viv | **El aviso no se ve en vivo** durante el streaming (no es un token: lo añade el servidor al guardar) | En T1 (y en F1-t), mirar la burbuja mientras el modelo escribe y en el momento en que termina | Durante el streaming, sin aviso; aparece al cerrar el turno o al recargar. Se anota cuándo apareció | [x] OK (no se ve en vivo; aparece al cerrar el turno) |
| Hist | **`_strip_html` al compactar.** El motor compacta el historial leyendo `content` y le quita el HTML (`pns_ai_mcp/utils/history_compact.py:386-389`), así que el modelo recibe el aviso como texto | V6 y la forma del aviso del segundo turno (`historia_html`) | La columna `history` del job guarda el aviso **con su HTML** (`historia_html` = t). Lo que recibe el modelo después de compactar **no se ve por SQL**: en el laboratorio, ninguna fila de `ai_log` lleva el aviso (comprobado el 06/11/2026). Queda cubierto por lectura del código; se anota `historia_html` | [x] `historia_html` t (job 201) |

Hist y un F1-t no concluyente se anotan en G: no cuentan como fallo ni bloquean la subida.

### D.4 «Design» final y no regresión

**[ALTERA la configuración]** **«Design» solo en Gemini 3.5 flash** (decisión 2 de E4′.h; plan, §3.1,
«Casilla Design»: no en `lite` y al menos un proveedor con ella). Comprobación: la consulta de A.6, solo ese
proveedor con `fit_design` = `t`. Es el estado en que queda el staging.

| # | Caso | Quién | Esperado | Qué anotar | Obtenido |
|---|---|---|---|---|---|
| R8 | **Lienzo desde el chat**, con Gemini 3.5 flash. Conversación nueva: «Hazme una página con las ventas por mes de este año, con un gráfico de barras y una tabla». Consultas de R8 y «Qué modelo diseñó» de E3′ (D.1 y D.2) con el id de U1 | U1 | La tarjeta de la página en la burbuja y, al abrirla, el gráfico y la tabla; `canvas_open` = t y `canvas_rev` ≥ 1; en `ai_log`, «Design laid out the page in … s» y diseñó Gemini 3.5 flash; sin aviso. **Si falla por cuota (429) o 503 del proveedor: se anota y no bloquea** | sesión, filas de `ai_log`, modelo; si hubo 429/503 | [x] OK (sesión 63 de `u1`, `canvas_rev` 1; fila 1758, Gemini 3.5 flash; sin 429/503) |
| R-log | **Log desde el arranque** (B.8) | — | Por comprobación de `rpc` (D.1), como en el laboratorio el 09/11/2026: **P-33.1, un `ERROR` de `odoo.http` con su `Traceback`** a la hora de `rpc` (`AttributeError` … `month_usage`; el texto exacto depende de la revisión de Odoo 14); **P-30, P-31, P-32 y P-33.2: nada** (`AccessError` hereda de `UserError` y `dispatch_rpc` lo relanza sin escribirlo); **P-33.3 y P-33.4: dos líneas INFO** «Access Denied by ACLs for operation: create, uid: `<uid de demo>`, model: ai.provider.usage.wizard». Fuera de eso, solo errores del proveedor (429/503), si los hay, a su hora | líneas `ERROR` y `Traceback`, por tipo y hora | [x] P-33.1 a las 10:03:20 (esperado) y fallo de serialización de la sesión 59 a las 10:28:27 (observación) |

Orden de R-log **[LECTURA]**, con `StartedAt` de B.8 tal como sale:

```bash
cd /opt/odoo/pns_staging && docker compose logs --since '<StartedAt de B.8>' web 2>&1 | grep -E 'Traceback|ERROR|CRITICAL'
```

---

## E. Vuelta atrás (descrita, no lista para pegar)

Operaciones que cambian el VPS: las decide y hace quien administra el VPS.

1. **Antes del `-u` (fallo en B.3 a B.6).** `pns_demo` no ha cambiado. Se devuelve el código de `522ce6e` desde
   `addons_antes_E4p`, con `rsync --delete` módulo a módulo; se comprueba la huella de A.3 (710,
   `6ac645fc…44e5`) y se arranca `web`.
2. **Después del `-u`.** Solo cambió Python: sin esquema, versiones, vistas, datos ni seguridad nuevos. Volver
   el código como en el punto 1 y reiniciar `web` **es viable («Sin confirmar»: no ensayado)**. No hace falta
   otro `-u`: los datos de `pns_ai_mcp` y `pns_ai_chatboo` que recargó son los mismos en `522ce6e`. Lo escrito
   con el código nuevo se queda: mensajes de Chatboo con el aviso del parche 34 (texto, inofensivo) y, si
   `limpiar` no se hizo, la acción `seges.e4p` (se borra con `limpiar`; no tiene interfaz: F). Si hay dudas,
   se corrige hacia delante con un commit nuevo y el mismo procedimiento.
3. **`addons_antes_E4p`** se conserva hasta la limpieza final del staging, como las anteriores.

---

## F. Limpieza

**[ALTERA]** Mínima, como en E3′: se deshace lo que falsearía las pruebas siguientes o deja accesos abiertos.

- **`seges.e4p`:** borrada por `limpiar` (D.1, paso 4). Si no se pudo, se repite `limpiar` (se puede
  repetir); si sigue sin poder, **parar y decidir con Sergio**: `ai.trusted.action` no tiene interfaz (en el
  laboratorio, el 09/11/2026, ninguna acción de ventana, vista ni menú sobre el modelo).
- **Usuarios:** volver a **archivar `demo`** y **`e1p_aiadmin`** (o `e4p_aiadmin`, si se creó en C.2: se
  archiva; no se borra). Las contraseñas de prueba se quedan en usuarios archivados (no pueden entrar).
- **Clave MCP temporal de `admin`:** revocar (queda `not_generated` y sin hash, como tras E3′).
- **«Design»:** solo en Gemini 3.5 flash (D.4). Si se paró antes de D.4, ponerla así igualmente.
- **Sesiones y jobs de las pruebas:** se quedan (como las 49 a 57 de E3′) para la limpieza final; se anotan
  sus ids (sesiones de T1, F1-t y V2 de `admin` y la de R8 de U1; jobs de Chatboo y del botón Canvas).
- **Equipo de Sergio:** cerrar el túnel (Ctrl+C en su terminal) y `unset E4P_URL E4P_DB E4P_AIADMIN E4P_INTERNO`.
  `~/staging_e4p` (script, estado y resultado) se conserva hasta anotar G; el estado, tras el segundo
  `limpiar`, ya no tiene ids. `/tmp/pns_addons_8d218ea.tar.gz` se borra tras B.
- **`/tmp` del VPS:** `pns_u_E4p.log` y `pns_diff_E4p.txt`, después del [DOC] de esta subida.
- **Restos de E1′ a E3′ que siguen pendientes** (no se borran ahora; limpieza final):
  - VPS, `/opt/odoo/pns_staging`: `addons_antes_E1`, `addons_antes_E2`, `addons_antes_E1p`, `addons_antes_E2p`,
    `addons_antes_E3p` (y ahora `addons_antes_E4p`), `addons_27cadbb`, `addons_27cadbb_b` y `addons_95d6b1a`;
  - VPS, `/tmp`: `pns_addons_27cadbb.tar.gz`, `pns_addons_63ee2dc.tar.gz`, `pns_addons_95d6b1a.tar.gz`,
    `pns_p9_antes_E1p.txt`, `pns_p9_despues_E1p.txt` y `pns_liyben.snip` (**revisar antes de borrar**);
    se comprueban con `ls -la /tmp` y se anotan;
  - equipo, `/tmp` (visto con `ls` el 06/11/2026): `pns_addons_0366231`, `27cadbb`, `2bb4f51`, `522ce6e`,
    `63ee2dc` y `9a2970d` (`.tar.gz`);
  - `pns_demo`: sesiones 49 a 57, contactos archivados 59, 60 y 65, `e3p_portal` (26) archivado
    ([staging de E3′](staging_e3_3879.md), G, «Restos para la limpieza final»); de E2′, los de su G.

**[LECTURA]** Comprobación final:

```bash
e4sql <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT count(*) AS acciones, count(*) FILTER (WHERE code LIKE 'seges.e4p%') AS restos_e4p FROM ai_trusted_action;
SELECT u.id, u.login, u.active FROM res_users u
 WHERE u.login IN ('demo', 'e1p_aiadmin') OR left(u.login, 4) = 'e4p_' ORDER BY u.id;
SELECT m.id, u.login, m.mcp_api_key_state, coalesce(m.mcp_api_key_hash, '') <> '' AS tiene_hash
  FROM ai_mcp_user m JOIN res_users u ON u.id = m.user_id WHERE u.login = 'admin';
SELECT id, name, active, fit_design FROM ai_provider WHERE fit_design ORDER BY id;
ROLLBACK;
SQL
```

Esperado: 9 acciones y 0 restos; `demo`, `e1p_aiadmin` (y `e4p_aiadmin`, si existe) inactivos; clave de `admin`
en `not_generated` y sin hash; una sola fila de proveedor con «Design»: Gemini 3.5 flash. Resultado en la
[verificación](verificacion_seguridad_pns_ai.md), en un bloque nuevo «Staging — entrega E4′».

---

## G. Resultado de la subida (09/11/2026)

Sergio con Claude; horas en UTC. Commit `8d218ea` de `14.0-pns-ai-3879` (procedimiento en `b661446`).
Resultado por prueba en las columnas «Obtenido» de D.1 a D.4; resumen en la
[verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E4′ (09/11/2026)».

### A. Comprobaciones previas

- **A.0 a A.3:** `e4sql` en solo lectura (`on`) y `UTC`. `odoo14_pns` y `odoo14_pns_db` en marcha (los de
  LIYBEN, solo mirados); `POSTGRES_USER` = `odoo`. `docker port odoo14_pns`: `8069/tcp -> 127.0.0.1:8169` (y
  `8072/tcp -> 127.0.0.1:8172`). Montajes de E3′ sin cambios (`addons` en `/mnt/extra-addons/pns`,
  `rw=false`). Copias `addons_antes_E1`, `_E2`, `_E1p`, `_E2p` y `_E3p`, sin `addons_antes_E4p`; `addons`,
  12 MB; disco al 87 % (9,5 GB libres). Código montado: 710 archivos, `6ac645fc…44e5` (el de `522ce6e`).
- **A.4 (módulos, cron de `cleanup_expired`, acciones de confianza, dependientes; comprobaciones previas; A y
  B):** versiones `14.0.1.2.47`, `14.0.3.1.879` y `14.0.2.1.538`, `installed`; 0 filas `odoo_dev.%`; 7 crons
  de `pns_*`, activos, `user_id` 1; `ir_cron_ai_safe_operation_expire` activo, cada 5 minutos, `numbercall`
  -1, `model.cleanup_expired()`, `lastcall` 09:38:12 y `nextcall` 09:42:23; 9 acciones de confianza
  (`max(id)` 9) y 0 restos; ninguna transacción en curso; módulos instalados que dependen de `pns_ai_mcp`:
  **solo `pns_ai_chatboo`**. A.4 b: 0 `operation_data` que no empiecen por `{`; 29 operaciones
  (14 `cancelled`, 13 `executed`, 2 `expired`); pasos reales leídos (`res.partner`/`write`,
  `mail.message`/`create`, `res.partner.category`/`unlink`, `res.groups`/`write`, `action`, `fetch_url`),
  ninguno sobre `ai.trusted.action`. Consultas A y B: **0 filas**.
- **A.5 (grupos):** `admin` (2) activo, Ajustes, los cinco grupos de IA, `es_ES`, clave MCP `not_generated`
  sin hash; `demo` (6) inactivo, interno, sin Ajustes ni grupos de IA; `e1p_aiadmin` (19) inactivo, interno,
  sin Ajustes, `group_ai_admin` (y los que implica) y `group_ai_conversational`; `u1` (8) activo, con
  `group_ai_conversational` y clave MCP `generated`; ningún `e4p_*`. Precondición del script: se cumple.
- **A.6 (proveedores y «Design»):** 1 Gemini 3.6 flash, 2 «Proveedor fuera de cadena» (inactivo, «Design»
  vacío), 3 Gemini 3.5 flash y 4 Gemini 3.5 flash lite; «Design» en `t` en 1, 3 y 4. Cadena de
  `pns_ai_chatboo`: 1 → 3 → 4. «Test Connection» de los tres Gemini, hecho por Sergio hacia las 09:44, antes
  de C.

### B. Despliegue

- **B.1 (huella del `.tar.gz`):** `8d218ea` es `commit`; ningún commit posterior toca los módulos;
  `df42159a4ac5d048c32d9aa3206123a40ccbb8c805bea56b343ddc5b8cec0d5e`.
- **B.2 a B.4:** copiado al VPS con la misma huella. Código extraído: versiones sin cambios; 142 marcadores
  fuera de tests (8, 1, 5, 3 y 12 de los parches 30 a 34); las nueve comprobaciones de código como se esperaba
  (`def month_usage(` en 0); `chatboo_async_request.py` `c97e6a7b…` y `chatboo_canvas.py` `e470e7a7…`;
  `test_seges_e4p.py` presente; **711 archivos, `e37be448…1844`** (confirma la huella de A.3, calculada sin
  git).
- **B.5 y B.6:** `addons_antes_E4p` creada (huella `6ac645fc…44e5`; disco 87 %). `web` parado; ensayo del
  `rsync` sin bajas; `rsync` con salida 0; `addons`: 711 archivos, `e37be448…1844`; `diff -rq`: 11 líneas
  (10 archivos distintos, 1 nuevo, `test_seges_e4p.py`, y 0 solo en `addons_antes_E4p`).
- **B.7 y B.8 (`-u` de `pns_ai_mcp`; `WARNING`):** salida 0, de 09:49 a 09:50:05. 0 `Traceback`, `ERROR` y
  `CRITICAL`; 0 «Deleting field»; ningún módulo sin importar; **0 rechazos del parche 32** (las 9 acciones de
  fábrica se reescribieron a las 09:49:22). Carga: `Loading module pns_ai_mcp (28/48)`,
  `Module pns_ai_mcp loaded in 34.78s, 4636 queries`, `Loading module pns_ai_chatboo (34/48)` y
  `Module pns_ai_chatboo loaded in 2.74s, 584 queries` (el `-u` arrastra a `pns_ai_chatboo`, como se
  esperaba); 61 y 13 líneas `loading <módulo>/<archivo>`; `48 modules loaded in 38.22s, 5233 queries` y
  `Modules loaded.`. `WARNING`: los de E2′ y E3′ (2 «Client» de `ai.log`, 1 «Model» de `ai.trusted.action`,
  `skip retired unlink for pns_ai_mcp` y 2 `DeprecationWarning` de `distutils`), ninguno nuevo.
- **Arranque (reinicio):** `StartedAt` = `2026-11-09T09:51:24.370379362Z`. Log, 0 errores; `/web/login` 200;
  `/mcp` 403. `/tmp` del VPS: `.tar.gz` y extracción borrados.

### C. Usuarios y comprobaciones posteriores

- **C.1:** igual que A.4 a; 9 acciones (`max(id)` 9), 9 activas, 0 restos, última escritura 09:49:22 (la del
  `-u`).
- **C.2 (desarchivados o creados):** `demo` (6) y `e1p_aiadmin` (19) desarchivados a las 09:56:33, con
  contraseñas de prueba nuevas de 8 o más, sin cambiar sus grupos; clave MCP temporal de `admin` generada.
  Ningún `e4p_*`.
- **C.3:** «Design» como en A.6 (1, 3 y 4 en `t`).

### D. Pruebas

- **D.1 (script):** túnel `ssh -p … -N -L 18169:127.0.0.1:8169 …`, `/web/login` 200 por `localhost:18169`;
  script `76f781f6…9b03`. `preparar`: `ai.trusted.action` 10. `rpc`: t0 = 2026-11-09 10:03:19, **16/16 OK**,
  salida 0, `resultado_e4p_20261109-110323.txt`; P-33.1 con el texto «The method 'month_usage' does not exist
  on the model 'ai.provider'» (otro texto que en el laboratorio; el script lo clasifica bien). Las contraseñas
  de prueba de `demo` y `e1p_aiadmin` no aparecen en el resultado; la de `admin` (5 caracteres, por debajo del
  umbral del filtro) coincide con el texto de los logins (6 líneas, 2 como palabra entera): no es una fuga.
  Consulta de P-30: **0 filas** (última fila de `ai_log`, la 1680, del 04/11). `limpiar` ×2:
  `borradas: 1 [10]` y `0`, salidas 0; 9 acciones y 0 restos; estado sin ids.
- **D.2, fase 1 (T1, V5′, V6, BC, R34):** «Design» quitado de 1, 3 y 4. **T1** (sesión 59, job 200, Gemini
  3.6 flash, 11 s): sin página (`canvas_rev` 0); el modelo dice «He creado la página nueva…» y la burbuja
  termina con el aviso en cursiva y en su propio párrafo. V5: `content_es` y `original_es` en t; job `done`,
  `response_es` t. Forma: empieza por `<`, con tabla, `aviso_html` t, `content` = `original_content`.
  `ai_log`: dos intentos de diseño, filas 1690/1691 y 1694/1695 («Design failed after 0 s: No AI provider is
  configured for agent pns_ai_chatboo» y «No page was built: …»). **V5′:** copiar, solo la tabla (`id` y
  `name`), sin aviso; PDF, aviso en su propio párrafo, sin HTML crudo; «Word», un `.doc` (HTML), aviso en su
  `<p>`, sin HTML crudo; XLSX, la tabla sin aviso. **V6** (job 201): `historia_es` t e `historia_html` t;
  turno 2 con tabla y sin aviso propio. **BC:** job del botón Canvas 1, `error` con el aviso, `started_at` =
  `finished_at` (10:17:36); sesión sin cambios (huella `8eba1ad3…124a`, 4 mensajes, `canvas_rev` 0); en
  pantalla, el texto pasa a «Creación de página» y vuelve a «Lienzo» con el borde rojo, **sin tooltip**, sin
  toast ni mensaje. **R34:** tras F5 y tras cambiar de sesión, el mensaje de T1 conserva el aviso (`content` y
  `original_content`, HTML); huella nueva `5670c960…cfc8f` (la reescribe el cliente).
- **D.2, fase 2 (V2, V3):** «Design» en 1 y 3. **V2** (sesión 60, job 202): página creada (`canvas_rev` 1) y
  se abre; sin aviso en la burbuja, `messages`, `response`, `done_meta` ni historial; fila 1711, «Design laid
  out the page in 26 s», Gemini 3.6 flash. **V3: no concluyente.** La respuesta con tabla del turno 2 de la
  sesión 59 ya no tenía el botón «Lienzo» tras recargar; un turno nuevo en la sesión 59 (jobs 204 y 205)
  tampoco lo trajo (ver observaciones); en una conversación nueva (sesión 61) el modelo creó una página aunque
  se le pidió que no (`canvas_rev` 1), sin tabla ni botón. No se repite: lo esencial (job en error sin llamar
  al modelo, sesión sin cambios, sin aviso duplicado) lo cubre BC.
- **D.3 (F1-t, Viv, Hist):** **F1-t: no concluyente** (sesión 62, `canvas_rev` 0): el contenido empieza por
  `<` (la frase va en HTML) y lleva tabla; `aviso_html` t y el aviso se ve en cursiva. No se repite: con las
  herramientas de tablas el modelo responde en HTML desde la primera frase. **Viv:** el aviso no se ve durante
  el streaming; aparece al terminar el turno (T1 y F1-t). **Hist:** `historia_html` t en el job 201; lo que
  recibe el modelo tras compactar, por lectura del código.
- **D.4 (R8, R-log):** «Design» solo en Gemini 3.5 flash (3). **R8** (`u1`, sesión 63): página con el gráfico
  y la tabla, `canvas_rev` 1; fila 1758, «Design laid out the page in 37 s», **Gemini 3.5 flash**;
  conversación con Gemini 3.6 flash, 61 s; sin 429 ni 503. **R-log** desde el `StartedAt`: el `ERROR` de
  `odoo.http` de P-33.1 a las 10:03:20, con su `Traceback` (esperado); y, a las 10:28:27, dos `ERROR` («bad
  query: SELECT id FROM chatboo_session WHERE id = 59 FOR UPDATE SKIP LOCKED» y «Error loading session: could
  not serialize access due to concurrent update», de `pns_ai_chatboo.controllers.chatboo`; ver observaciones).
  Sin errores del proveedor.

### F. Limpieza

- `seges.e4p` borrada por `limpiar`; `demo` y `e1p_aiadmin` archivados otra vez (con sus contraseñas de
  prueba); clave MCP de `admin` revocada; «Design» solo en Gemini 3.5 flash. Túnel cerrado y variables
  quitadas en el equipo.
- Comprobación final: 9 acciones y 0 restos; `demo` y `e1p_aiadmin` inactivos, ningún `e4p_*`; clave de
  `admin` `not_generated` sin hash; una sola fila con «Design»: 3, Gemini 3.5 flash.

**Resultado:** **E4′ validada en staging (09/11/2026)**: parches 30 a 33 (script, 16/16 OK; P-30, 0 filas) y
34 (T1, V5, V5′, V6, BC, R34, V2, Viv, Hist), con el `-u` de `pns_ai_mcp` sin errores y la recarga de las
acciones de fábrica en `su`. V3 y F1-t, no concluyentes (no bloquean). R8 OK con Gemini 3.5 flash.

### Correcciones del procedimiento

Anotadas aquí; los pasos de A a F no se cambian.

- **D.1, túnel:** la orden `ssh -p "$VPS_PORT" -N -L 18169:127.0.0.1:8169 "$VPS_DEST"` funciona tal cual (deja
  de estar «Sin confirmar»).
- **A.6:** «Test Connection» no dejó filas en `ai_log` (la última seguía siendo la 1680, del 04/11): solo
  escribe en el proveedor.
- **D.1, comprobación del filtro:** solo tiene sentido con las contraseñas de 8 o más; una más corta (la de
  `admin`) coincide con trozos de los logins.
- **D.2, V3:** el botón «Lienzo» del turno 2 de la sesión de T1 no sigue tras recargar; se intentó con un
  turno nuevo y con una conversación nueva (ver arriba).
- **D.2, fase 1:** F1-t (D.3) va en la fase 1, sin «Design»; se hizo después de V2 y V3, con «Design» quitado
  otra vez.
- **D.4, R8:** la consulta de `ai_log` con «últimos 15 minutos» se quedó corta; se lanzó con hora fija.
- **P-33.1:** en el staging el texto es «The method 'month_usage' does not exist on the model 'ai.provider'»
  (en el laboratorio, «type object … has no attribute 'month_usage'»).

### Observaciones

- **Sesión 58** (10:09:37): primer intento de T1, antes de quitar «Design»; creó una página (fila 1684,
  «Design laid out the page in 41 s»).
- **El modelo afirma haber creado la página** cuando se rechaza (PNS-96): en T1 y en F1-t, el aviso del parche
  34 lo corrige en la burbuja.
- **Botón Canvas:** en el staging, ni siquiera el tooltip con el motivo (en el laboratorio sí lo había): solo
  el borde rojo. Defecto del fabricante; al informe (plan, §3 punto 2).
- **Exportación:** PDF y `.doc` ponen la prosa y el aviso antes de la tabla, y el aviso sin cursiva (un
  `<p>`); PDF, `.doc` y XLSX solo con la columna `Name` (copiar lleva `id` y `name`); la exportación «Word» es
  un `.doc` HTML, no `.docx`. Del fabricante.
- **Sesión 59, 10:27-10:28:** el job 204 acabó con «Se especificó una orden inválida» (el modelo pidió el
  orden `name ascii`); Sergio reenvió el texto (job 205). Al terminar el 205, la carga de la sesión por el
  cliente falló por la escritura concurrente del job (`FOR UPDATE SKIP LOCKED` con «could not serialize
  access…», 10:28:27; la sesión, `write_date` 10:28:27.058): la carga no reintenta. Probable causa de que no
  saliera el botón «Lienzo». Del fabricante; el parche 34 no intervino (sin rechazo de página en esos turnos).
- **Sesión 61:** el orquestador creó una página aunque se le pidió «No hagas ninguna página» (plan, apartado
  E4′, fila «El orquestador reinterpreta peticiones…»).
- **Contraseña de `admin` en `pns_demo`:** 5 caracteres, en un staging accesible desde Internet. No es de E4′;
  decide Sergio si se cambia (antes o en la limpieza final).

### Restos para la limpieza final (no se borran ahora)

- VPS, `/opt/odoo/pns_staging`: `addons_antes_E4p` (además de las anteriores); `/tmp`: `pns_u_E4p.log` y
  `pns_diff_E4p.txt` (se pueden borrar tras este [DOC]).
- `pns_demo`: sesiones 58 a 62 (`admin`) y 63 (`u1`), con sus páginas (58, 60, 61 y 63); jobs de Chatboo 199 a
  208; job del botón Canvas 1; filas de `ai_log` 1681 a 1760 (80, del 09/11); `demo` y `e1p_aiadmin`
  archivados con contraseñas de prueba.
- Equipo de Sergio: `~/staging_e4p` (script, estado y resultado; tras este [DOC]).
