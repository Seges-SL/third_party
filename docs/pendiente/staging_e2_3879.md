# Subida de E2′ al staging `pns_demo` (parches 11 adaptado y 17 a 24)

- **Rama:** `14.0-pns-ai-3879` · **Base:** `c639fa8` (código de los módulos igual al de `0366231`, lo montado
  en E1′) · **Commit a desplegar:** `9a2970d`, el último que toca los módulos. Cualquier commit posterior
  que solo sea [DOC] (como `4a6b432`) da el mismo árbol y la misma huella del árbol, pero otra huella del
  `.tar.gz` (B.1) · **Preparado:** 28/10/2026 · **Estado:** preparado, sin ejecutar. **Bloqueado** hasta
  cumplir los dos pasos previos de código de D.0 (scripts de P-19 y de la 4 bis, validados contra el
  laboratorio).
- **Qué se sube:** parches 11 (adaptado) y 17 a 24: PNS-82, PNS-37, PNS-19, PNS-17, PNS-70, PNS-20,
  PNS-100, PNS-101 (ampliado) y PNS-102. Lista de archivos en la [propuesta de E2′](e2_propuesta_3879.md),
  «Commits de E2′: regla de tres commits (28/10/2026)»; registro en [parches](parches_pns_ai.md),
  «Parches de la rama 14.0-pns-ai-3879 (E2′)».
- **Origen:** §4, §5 y «Propuesta final» («Orden de trabajo y validación», punto 4) de la
  [propuesta de E2′](e2_propuesta_3879.md); validación en el laboratorio:
  [lab_e2_3879.md](lab_e2_3879.md), «Resultado (28/10/2026)», y [verificación](verificacion_seguridad_pns_ai.md),
  «Laboratorio — E2′, resultado (28/10/2026)».
- **Procedimiento de referencia:** [subida de E1′](staging_e1_3879.md) (mismo método, mismos contenedores),
  [plan de staging](plan_staging_pns_ai.md), §2.2 y §7.1.
- **Limpieza del staging: al terminar todos los cambios, no por entrega.** La limpieza del §9 del plan de
  staging (borrar `pns_demo` sin copia, el proyecto `pns_staging`, las copias `addons_antes_*`, el proxy y la
  clave de Gemini) se hace una sola vez, al cerrar la última entrega. En esta subida solo se deshace lo que
  falsearía las pruebas siguientes (D.3).
- **LIYBEN recibe todo de una vez, al final** (plan de corrección, §1 punto 3 y §3), no esta entrega por
  separado. Sus claves MCP están **revocadas desde el 27/10/2026** (PNS-101 y PNS-102): **se vuelven a
  generar después del despliegue final** y se comprueba que los clientes conectan (plan de corrección,
  §3.1).
- **Condiciones del staging que siguen vigentes:** las del plan de staging, §1 (datos de demostración, sin
  mesa de PIN, `whitelist_only`). Sin copia de `pns_demo` (N9).
- **Sin secretos en este documento:** ni contraseñas, ni claves, ni el contenido de `.env`.

**Convenciones de los comandos.** Las de E1′: **[LECTURA]** solo lee; **[ALTERA]** cambia algo y va
precedido de un aviso. SQL con `psql` en `odoo14_pns_db`, base de datos `pns_demo`, y las de lectura dentro
de `BEGIN TRANSACTION READ ONLY … ROLLBACK`. Lo no confirmado se marca **«Sin confirmar»**.

## Índice

0. Método de despliegue
A. Comprobaciones previas (solo lectura)
B. Despliegue y `-u`
C. Comprobaciones posteriores
D. Pruebas de seguridad y de no regresión
E. Vuelta atrás (descrita)
F. Lo que no está documentado

---

## 0. Método de despliegue

El de E1′ (§0): `git archive` de los tres módulos desde el equipo de Sergio, `scp` a `/tmp` del VPS, huella
comparada en el VPS, copia previa en `addons_antes_E2p`, parada de `web`, `rsync` módulo a módulo como
`ubuntu` y `-u`.

**Diferencia con E1′:**
- **Sin cambio de versión ni de esquema.** Los tres manifiestos siguen en `1.2.47`, `3.1.879` y `2.1.538`:
  los parches no tocan `version` (comprobado el 28/10/2026 con `git show` en `0366231` y en `9a2970d`). De
  `0366231` a `9a2970d` cambian 17 archivos y hay 13 nuevos. Todos son Python, salvo dos JS estáticos de
  `pns_ai_chatboo`. No hay XML, datos, CSV, `i18n` ni manifiestos, y no se borra ningún archivo.
- **`-u` de `pns_ai_mcp` y `pns_ai_chatboo`, sin `pns_base`.** Criterio de Sergio: `pns_base` solo entra si
  cambia de versión, y no cambia. Su único cambio es Python (parche 21, `models/operation_report_wizard.py`),
  que se carga al arrancar. El modelo nuevo `box_a_guard.py` solo hereda `base` e `ir.config_parameter`,
  sin campos. El JS del parche 20 va en el bundle de estáticos, que Odoo regenera solo al cambiar el
  archivo. Por eso **no se espera ningún «Deleting field»** (B.8). En E2 (21/10) bastó con reiniciar.
- **Sin fotografía de P-9 ni recarga de `es_ES`:** no hay pérdidas de esquema ni traducciones nuevas
  (A.5 y C.3).
- **La vuelta atrás del código es viable** (E): sin cambio de esquema, volver a `0366231` no deja código
  viejo sobre un esquema nuevo.

---

## A. Comprobaciones previas (solo lectura)

Desde el VPS, con el usuario `ubuntu`.

### A.1 Contenedores y usuario de PostgreSQL

**[LECTURA]** Como en E1′ (A.1):

```bash
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}' | grep -E 'odoo14_pns|odoo14_db|odoo14_server'
docker exec odoo14_pns_db printenv POSTGRES_USER
```

Esperado: `odoo14_pns` y `odoo14_pns_db` en marcha; `POSTGRES_USER` = `odoo`.

### A.2 Cómo está montado el código

**[LECTURA]** Como en E1′ (A.2):

```bash
docker inspect odoo14_pns --format '{{range .Mounts}}{{.Type}}  {{.Source}} -> {{.Destination}}  rw={{.RW}}{{"\n"}}{{end}}'
cd /opt/odoo/pns_staging && ls -la && ls -la addons
df -h /opt/odoo /tmp
```

Esperado: los montajes de E1′ (A.2), sin cambios. En `addons`, los tres módulos, de `ubuntu`. Deben estar
`addons_antes_E1`, `addons_antes_E2` y `addons_antes_E1p`, y **todavía no** `addons_antes_E2p`.

### A.3 Qué código hay montado (huella)

Calculada el 28/10/2026 en el equipo sobre los archivos de cada commit. Con el mismo método, `0366231`
reproduce las huellas de E1′:

| Commit | Archivos | Huella del árbol |
|---|---|---|
| `0366231` (E1′, lo que debería estar montado) | 696 | `c12168eac19014c6ab51135cac239e8a8f0d85b2423d4b9f7a09ee1d2a2b6160` |
| `9a2970d` (E2′, lo que se va a montar) | 709 | `7a6c7144880aab3680db5d47d22bf041e91697d02879aaef69c02610fe00bb9f` |

**[LECTURA]**

```bash
cd /opt/odoo/pns_staging/addons
find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l
find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum
```

Esperado: 696 y `c12168ea…6160`. **Si no coincide, parar:** alguien ha cambiado el código desde E1′.

### A.4 Estado de `pns_demo`: módulos, crons y actividad

**[LECTURA]**

```bash
docker exec -i odoo14_pns_db psql -U odoo -d pns_demo -v ON_ERROR_STOP=1 <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT name, state, latest_version FROM ir_module_module WHERE name LIKE 'pns_%' ORDER BY name;
SELECT key, value FROM ir_config_parameter WHERE key LIKE 'odoo_dev.%';
SELECT d.module || '.' || d.name AS xml_id, c.active, c.numbercall, c.interval_number,
       c.interval_type, c.nextcall, c.user_id
  FROM ir_cron c JOIN ir_model_data d ON d.model = 'ir.cron' AND d.res_id = c.id
 WHERE d.module LIKE 'pns_%' ORDER BY 1;
SELECT pid, state, xact_start, wait_event_type, left(query, 80) AS query
  FROM pg_stat_activity WHERE datname = 'pns_demo' AND state <> 'idle' ORDER BY xact_start;
ROLLBACK;
SQL
```

Esperado:
- `pns_base` 14.0.1.2.47, `pns_ai_mcp` 14.0.3.1.879 y `pns_ai_chatboo` 14.0.2.1.538, `installed`.
- Sin filas `odoo_dev.%`.
- Siete crons de `pns_*`: los seis de E1′ y `pns_ai_mcp.ir_cron_ai_journal_trash`. El de la papelera
  activo, diario, `numbercall` -1 y `user_id` 1 (C.2 de E1′).
- Ninguna transacción en curso.

### A.5 PNS-37: filas en papelera del diario y quién las escribió (§5.1 de la propuesta)

Antes de subir el parche 17, comprobar que ninguna fila en papelera se ha reescrito a mano: `write_uid`
debe ser el del creador o el superusuario, y `write_date` igual o muy cercano a `create_date`. Es la
consulta de la [propuesta](e2_propuesta_3879.md), §5.1, para el contenedor y la BD del staging. En LIYBEN
se repite antes del despliegue final, en `odoo14_db` (plan de corrección, §3).

**[LECTURA]**

```bash
docker exec -i odoo14_pns_db psql -U odoo -d pns_demo -v ON_ERROR_STOP=1 <<'SQL' | tee /tmp/pns_e2p_diario_antes.txt
BEGIN TRANSACTION READ ONLY;
SELECT c.id, c.user_id, c.active, c.numbercall, c.nextcall, c.lastcall
  FROM ir_cron c JOIN ir_model_data d ON d.model = 'ir.cron' AND d.res_id = c.id
 WHERE d.module = 'pns_ai_mcp' AND d.name = 'ir_cron_ai_journal_trash';
SELECT value AS journal_trash_days FROM ir_config_parameter WHERE key = 'pns_ai_mcp.journal_trash_days';
SELECT j.id, j.op, j.state, j.reversible, j.model_name, j.record_ids_display,
       j.create_uid, j.write_uid, j.create_date, j.write_date
  FROM ai_change_journal j
 WHERE j.op = 'unlink' AND position('"quarantine": true' IN coalesce(j.after_json, '')) > 0
 ORDER BY j.id;
SELECT id, op, state, model_name, write_uid, write_date FROM ai_change_journal ORDER BY id;
ROLLBACK;
SQL
```

La última consulta, el diario entero, no está en §5.1. Sirve de «antes» para P-37 (D.1).

Lectura: si alguna fila en papelera tiene un `write_uid` que no es el creador ni el 1, o un `write_date`
lejano de `create_date`, **no subir** y revisarla antes. Con el parche 17, esa fila ya no se podría
corregir desde Odoo.

### A.6 PNS-82: adjuntos con `res_model` informado y `res_id = 0` (§5.2 de la propuesta)

Ya se ejecutó en `pns_demo` el 27/10/2026, con este resultado: 14 adjuntos del caso b), todos bundles
`ir.ui.view` de `__system__`, y 0 citados en sesiones ([propuesta](e2_propuesta_3879.md), §5.2). Se repite
para comprobar que no ha cambiado.

**[LECTURA]**

```bash
docker exec -i odoo14_pns_db psql -U odoo -d pns_demo -v ON_ERROR_STOP=1 <<'SQL'
BEGIN TRANSACTION READ ONLY;
-- 1. Recuento por criterio (solo adjuntos sin res_field: los de campo no se enganchan).
SELECT CASE
         WHEN res_model IS NOT NULL AND res_model <> '' AND coalesce(res_id, 0) = 0 THEN 'b) res_model informado, res_id 0 o NULL'
         WHEN (res_model IS NULL OR res_model = '') AND coalesce(res_id, 0) = 0 THEN 'a) los dos vacíos'
         WHEN (res_model IS NULL OR res_model = '') AND coalesce(res_id, 0) <> 0 THEN 'c) res_id sin res_model'
         ELSE 'd) enganchado' END AS caso,
       count(*) AS adjuntos,
       count(*) FILTER (WHERE description = 'pns_base:export') AS marca_export
  FROM ir_attachment
 WHERE res_field IS NULL
 GROUP BY 1 ORDER BY 1;
-- 2. Detalle del caso b): por modelo, creador y tipo.
SELECT a.res_model, u.login AS creador, a.mimetype, count(*) AS adjuntos,
       min(a.create_date)::date AS primero, max(a.create_date)::date AS ultimo
  FROM ir_attachment a LEFT JOIN res_users u ON u.id = a.create_uid
 WHERE a.res_field IS NULL AND a.res_model IS NOT NULL AND a.res_model <> ''
   AND coalesce(a.res_id, 0) = 0
 GROUP BY 1, 2, 3 ORDER BY 4 DESC, 1;
-- 3. Del caso b), los que alguna sesión de Chatboo cita en sus mensajes (chips de descarga).
SELECT a.id, a.res_model, a.name, u.login AS creador, a.create_date::date
  FROM ir_attachment a LEFT JOIN res_users u ON u.id = a.create_uid
 WHERE a.res_field IS NULL AND a.res_model IS NOT NULL AND a.res_model <> ''
   AND coalesce(a.res_id, 0) = 0
   AND EXISTS (SELECT 1 FROM chatboo_session s
                WHERE s.messages LIKE '%/' || a.id || '"%'
                   OR s.messages LIKE '%"attachment_id": ' || a.id || '%')
 ORDER BY a.id;
ROLLBACK;
SQL
```

Lectura: si la consulta 3 sale vacía y la 2 solo muestra modelos ajenos al chat, como en la referencia del
27/10, se mantiene el criterio del fabricante (decisión 7). Si salen adjuntos del caso b) citados en
sesiones, **no subir** y revisar el criterio.

### A.7 Proveedor del staging

Las consultas y los pasos de A.7 de E1′, sin cambios. Solo Sergio, en la interfaz: «Test Connection» de la
cadena de Chatboo **y cuota en la consola de Google AI Studio** (F de E1′: «Test Connection» no basta). La
necesitan los turnos del chat de D.2 y los gráficos de P-70.

### A.8 Datos para las pruebas de D

**[LECTURA]** Ids que necesitan los scripts y los pasos de D. No lee `value` ni `api_key`:

```bash
docker exec -i odoo14_pns_db psql -U odoo -d pns_demo -v ON_ERROR_STOP=1 <<'SQL'
BEGIN TRANSACTION READ ONLY;
-- P-19: id de database.secret (E2P_SECRET_ID) y datos de partida
SELECT id FROM ir_config_parameter WHERE key = 'database.secret';
SELECT count(*) AS logs_con_proveedor FROM ai_log WHERE provider_id IS NOT NULL;
-- P-19b: proveedores del agente pns_ai_mcp.ai_agent_admin (en el laboratorio, 0: el caso no prueba nada)
SELECT count(*) AS proveedores_agente_admin FROM ai_agent_provider ap
  JOIN ir_model_data d ON d.model = 'ai.agent' AND d.res_id = ap.agent_id
 WHERE d.module = 'pns_ai_mcp' AND d.name = 'ai_agent_admin';
-- P-70: id de la acción del tablero de Facturación (en el laboratorio, 335)
SELECT res_id AS accion_tablero FROM ir_model_data
 WHERE module = 'account' AND name = 'open_account_journal_dashboard_kanban';
-- P-20: proveedores y usuarios MCP (elegir los registros de D.1)
SELECT id, name, active, temperature, write_uid, write_date FROM ai_provider ORDER BY id;
SELECT m.id, u.login, m.last_mcp_client_label, m.write_uid, m.write_date
  FROM ai_mcp_user m JOIN res_users u ON u.id = m.user_id ORDER BY m.id;
-- P-37b: permisos actuales del usuario de prueba sobre res.partner.category (sustituir <login>)
SELECT g.name AS grupo, a.perm_read, a.perm_write, a.perm_create, a.perm_unlink
  FROM ir_model_access a
  JOIN ir_model m ON m.id = a.model_id AND m.model = 'res.partner.category'
  LEFT JOIN res_groups g ON g.id = a.group_id
 WHERE a.active AND (a.group_id IS NULL OR a.group_id IN (
         SELECT r.gid FROM res_groups_users_rel r JOIN res_users u ON u.id = r.uid
          WHERE u.login = '<login>'))
 ORDER BY 1;
ROLLBACK;
SQL
```

Para P-37b, el usuario de prueba **no puede tener ya `perm_unlink`** sobre `res.partner.category` por otro
grupo: con `base.group_partner_manager`, por ejemplo, la prueba no discriminaría. Si lo tiene, se usa otro
usuario con AI Writer o se crea uno temporal (D.0).

---

## B. Despliegue y `-u`

El orden de E1′: archivo (B.1 a B.4, sin tocar `pns_demo`), copia (B.5), parar y sustituir (B.6), `-u`
(B.7), log y arranque (B.8).

### B.1 En el equipo de Sergio: archivo del commit

**[LECTURA del repo]**

```bash
cd ~/GitHub/third_party
git cat-file -t 9a2970d
git archive --format=tar.gz -o /tmp/pns_addons_9a2970d.tar.gz 9a2970d pns_base pns_ai_mcp pns_ai_chatboo
sha256sum /tmp/pns_addons_9a2970d.tar.gz
```

Esperado: `commit` y `0dd550a384fbe4d2fd8708f753da4d200b94e0d2d74544d01fa39f3b0af16fd6`, calculada el
28/10/2026 con git 2.43.0. Si se despliega otro commit, se sustituye en las tres órdenes. Con
`4a6b432` sale `56dc5876a095b84114bf2d2a459d6dded717bd9a338f00bcbecadbcefc2fbe7d`. La huella del árbol
(B.4) es la misma mientras no haya commits de código posteriores.

### B.2 Copia al VPS

**[ALTERA solo `/tmp` del VPS]** Como en E1′ (B.2):

```bash
scp -P <puerto> /tmp/pns_addons_9a2970d.tar.gz <usuario>@<host>:/tmp/
```

### B.3 En el VPS: huella y extracción

**[LECTURA]** `sha256sum /tmp/pns_addons_9a2970d.tar.gz` (la de B.1).

**[ALTERA solo `/tmp`]**

```bash
rm -rf /tmp/pns_addons_E2p && mkdir /tmp/pns_addons_E2p && tar -xzf /tmp/pns_addons_9a2970d.tar.gz -C /tmp/pns_addons_E2p
```

### B.4 Comprobaciones del código extraído

**[LECTURA]**

```bash
cd /tmp/pns_addons_E2p
grep -n "'version'" pns_base/__manifest__.py pns_ai_mcp/__manifest__.py pns_ai_chatboo/__manifest__.py
grep -rn "Seges: parche" pns_base pns_ai_mcp pns_ai_chatboo --include=*.py --include=*.js | grep -v '/tests/' | wc -l
for n in 11 17 18 19 20 21 22 23 24; do printf 'parche %s: ' $n; grep -rn "Seges: parche $n " pns_base pns_ai_mcp pns_ai_chatboo | grep -v '/tests/' | wc -l; done
grep -c 'seges=20' pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js
ls pns_ai_mcp/models/box_a_guard.py pns_ai_mcp/controllers/relaxaicode_format_guard.py
find pns_base pns_ai_mcp pns_ai_chatboo -type f | wc -l
find pns_base pns_ai_mcp pns_ai_chatboo -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum
```

Esperado (comprobado en el equipo el 28/10/2026 sobre el archivo de `9a2970d`):

| Comprobación | Esperado |
|---|---|
| Versiones | `1.2.47`, `3.1.879`, `2.1.538` (sin cambios) |
| Marcadores «Seges: parche» fuera de tests (`.py` y `.js`) | 75: los 20 de E1′ (parches 10 y 12 a 16) y 55 de E2′ |
| Por parche (11, 17 a 24) | 2, 5, 7, 3, 4, 6, 1, 23, 4 |
| `seges=20` en `chatboo_heavy_libs.js` | 1 |
| Archivos nuevos de código | `box_a_guard.py` y `relaxaicode_format_guard.py` presentes |
| Archivos / huella del árbol | 709 / `7a6c7144…bb9f` (A.3) |

Si algo no coincide, **no seguir**.

### B.5 Copia del código actual

**[ALTERA]** Crea `/opt/odoo/pns_staging/addons_antes_E2p` con el código de `0366231`:

```bash
cd /opt/odoo/pns_staging && test ! -e addons_antes_E2p && cp -a addons addons_antes_E2p && ls -d addons_antes_*
```

### B.6 Parar Odoo y sustituir el código

**[ALTERA]** Para `web` (`odoo14_pns`). `pns_demo` deja de responder hasta B.8:

```bash
cd /opt/odoo/pns_staging && docker compose stop web && docker compose ps
```

**[LECTURA]** Ensayo del `rsync`. A diferencia de E1′, **no debe listar ninguna baja**:

```bash
for m in pns_base pns_ai_mcp pns_ai_chatboo; do rsync -ani --delete /tmp/pns_addons_E2p/$m/ /opt/odoo/pns_staging/addons/$m/ | grep '^\*deleting'; done
```

**[ALTERA]** Sustitución, módulo a módulo, como `ubuntu` y sin `sudo`:

```bash
for m in pns_base pns_ai_mcp pns_ai_chatboo; do rsync -a --delete /tmp/pns_addons_E2p/$m/ /opt/odoo/pns_staging/addons/$m/; done
```

**[LECTURA]** Verificación:

```bash
cd /opt/odoo/pns_staging/addons
find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l
find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum
cd /opt/odoo/pns_staging && LC_ALL=C diff -rq addons_antes_E2p addons > /tmp/pns_diff_E2p.txt; wc -l < /tmp/pns_diff_E2p.txt
grep -c '^Files ' /tmp/pns_diff_E2p.txt; grep -c '^Only in addons/' /tmp/pns_diff_E2p.txt; grep -c '^Only in addons_antes_E2p' /tmp/pns_diff_E2p.txt
```

Esperado: 709 archivos y huella `7a6c7144…bb9f`. En el `diff -rq`, 30 líneas: 17 archivos distintos, 13
solo en `addons` y 0 solo en `addons_antes_E2p`. Lo calculé en el equipo entre `0366231` y `9a2970d`:
- **los 13 nuevos:** `box_a_guard.py`, `relaxaicode_format_guard.py` y 11 tests de Seges;
- **los 17 distintos:** los archivos de código de la regla de tres commits, salvo los dos nuevos, más los
  `__init__.py` y `test_seges_chatboo_access.py` de los tests.

### B.7 `-u` de `pns_ai_mcp` y `pns_ai_chatboo`

**[ALTERA `pns_demo`, sin copia (N9)]** Vuelve a cargar los XML de datos y las vistas de los dos módulos,
que son los mismos que cargó el `-u` de E1′. No cambia el esquema: ningún campo nuevo ni borrado. Un
registro de datos sin `noupdate` que se hubiera retocado a mano desde E1′ volvería al valor del módulo,
y no consta ninguno.

```bash
cd /opt/odoo/pns_staging && docker compose run --rm -T web odoo -u pns_ai_mcp,pns_ai_chatboo -d pns_demo --stop-after-init 2>&1 | tee /tmp/pns_u_E2p.log
```

### B.8 Revisar el log y arrancar

**[LECTURA]**

```bash
L=/tmp/pns_u_E2p.log
grep -cE 'Traceback|ERROR|CRITICAL' $L
grep -c 'Deleting field' $L
grep -E 'No module named|module .* not (found|installable)' $L
grep 'WARNING' $L | sed 's/.* WARNING [^ ]* //' | sort | uniq -c
grep -E 'Modules loaded|Registry loaded' $L | tail -2
```

Esperado: 0 `Traceback`, `ERROR` y `CRITICAL`; **0 «Deleting field»**; ningún módulo que no se importe.
Los `WARNING`, **sin confirmar**: el laboratorio no hizo `-u` con E2′, porque el guion lo daba por
opcional. Como referencia, los de E1′: `jinja2`, etiquetas repetidas y `skip retired unlink for
pns_ai_mcp`. Se anotan los que salgan.

**Si hay `Traceback`, `ERROR` o `CRITICAL`: no arrancar** y decidir con el apartado E.

**[ALTERA]** Arranca `web`:

```bash
cd /opt/odoo/pns_staging && docker compose start web && docker compose ps
```

**[LECTURA]** Tras uno o dos minutos:

```bash
cd /opt/odoo/pns_staging && docker compose logs --since 10m web 2>&1 | grep -cE 'Traceback|ERROR|CRITICAL'
curl -sS -o /dev/null -w '%{http_code}\n' https://pns.liyben.com/web/login
curl -sS -o /dev/null -w '%{http_code}\n' https://pns.liyben.com/mcp
```

Esperado: 0; `200`; `403`.

**[ALTERA solo `/tmp`]** Borrar `/tmp/pns_addons_9a2970d.tar.gz` y `/tmp/pns_addons_E2p`. El log y
`/tmp/pns_e2p_diario_antes.txt` se conservan hasta anotar los resultados.

---

## C. Comprobaciones posteriores

### C.1 P-9a, P-9b y P-9e

No aplica: E2′ no cambia el esquema ni el historial de Chatboo (A.5 de E1′ medía las pérdidas del cambio de
base).

### C.2 Módulos y crons

**[LECTURA]** El bloque de A.4, sin la consulta de actividad.

| Comprobación | Esperado | Obtenido |
|---|---|---|
| Versiones | Las de A.4, `installed` | [ ] |
| Cron de la papelera | `pns_ai_mcp.ir_cron_ai_journal_trash` activo, diario, `numbercall` -1, `user_id` 1. Con el parche 17 el diario solo lo escribe el sistema, y el cron corre como superusuario | [ ] |
| Resto de crons | Los seis de A.4, sin cambios | [ ] |
| Neutralización | Ninguna fila `odoo_dev.%` | [ ] |

### C.3 Recargar `es_ES`

No aplica: E2′ no toca `i18n` (regla de los parches) y `es_ES` ya se recargó tras E1′.

---

## D. Pruebas de seguridad y de no regresión de E2′

En el orden de la [propuesta](e2_propuesta_3879.md), «Orden de trabajo y validación», punto 4. Aquí
figuran quién, qué se hace y qué se espera; los pasos detallados se remiten a
[lab_e2_3879.md](lab_e2_3879.md) cuando ya están escritos.

### D.0 Preparación

**[ALTERA `pns_demo`]** Datos y claves temporales. Los autoriza y crea Sergio, como en E1′.

| Etiqueta | Usuario | Para |
|---|---|---|
| ADM | `admin` (id 2), Ajustes + AI Administrator, con **clave MCP temporal** | P-19, P-101, P-37 y no regresión |
| U1 | el del staging (chat) | No regresión del chat y P-82 (B) |
| UW | el del staging (chat + AI Writer), con contraseña local | P-37b (si A.8 lo permite), Autorizaciones |
| A2 y B | dos usuarios internos de prueba (los de la prueba 4 bis de E2; borrados en su limpieza) | P-82 |

**Requisitos bloqueantes: dos pasos previos de código.** **No se empieza A ni se toca el staging** hasta
que los dos estén hechos y validados contra el laboratorio (`lab_pns_ai_3879`). Precedente: los scripts de
E1′ se prepararon y validaron contra el laboratorio el 26/10/2026, antes de la subida ([subida de
E1′](staging_e1_3879.md), D.0). Son scripts del equipo de Sergio, fuera del repo, y no código de los
módulos.

| # | Paso previo | Por qué bloquea | Validación en el laboratorio | Hecho |
|---|---|---|---|---|
| 1 | **Adaptar `pruebas_e2p_lab.py`** para que, si un caso de P-19 **no** se rechaza, no imprima la respuesta: solo un marcador de «no rechazado» y el tipo del resultado, **nunca el contenido ni la clave**. Los casos rechazados siguen mostrando el mensaje de rechazo, y los controles (r1, r2, P-101r) su respuesta | Tal como está, un caso no rechazado imprime los 200 primeros caracteres de la respuesta. En el staging podría ser la clave real de Gemini | Ejecutarlo contra `lab_pns_ai_3879_14` y comprobar dos cosas: que P-19, P-101 y P-37 dan lo mismo que el 28/10 ([lab](lab_e2_3879.md), «Resultado (28/10/2026)»), y que un caso forzado a no rechazarse (por ejemplo, el control r1 tratado como si fuera de secreto) sale solo con el marcador y el tipo | [ ] |
| 2 | **Adaptar los scripts de la 4 bis (P-82)**, `preparar_e2.py` y `prueba4_bis_e2.py` (`~/staging_e2`), para que no choquen con `e2_aiadmin` (id 17, archivado en `pns_demo`): que creen solo A2, B y el adjunto X (sin `e2_aiadmin`), o que usen logins nuevos. También tienen que funcionar sobre 3.1.879 | `preparar_e2.py` vuelve a crear `e2_aiadmin` y el login único chocaría. Además, la comparación anota cambios de 3.1.879 en esas vías (§4.2, «Scripts de staging») | Prueba 4 bis completa en `lab_pns_ai_3879_14`: Z2 borrado; X desenganchado y de A2; A2 descarga X (200) y B no (404). Después, limpieza de los usuarios y del adjunto de prueba en el laboratorio | [ ] |

**Scripts** (equipo de Sergio, fuera del repo, carpeta `~/staging_e2p`; nada se copia al VPS), una vez
cumplidos los dos pasos:
- **`pruebas_e2p_lab.py` adaptado** (paso 1): P-19, P-101, P-37w/c y la propuesta de P-37b. Variables:
  `E2P_URL=https://pns.liyben.com`, `E2P_DB=pns_demo`, `E2P_ADM_PASS`, `E2P_KEY_ADM` y `E2P_SECRET_ID`
  (A.8). Para P-37b, además, `E2P_KEY_DEMO` (la clave de UW) y `E2P_P37B_CAT`. Todas con `read -s`.
  - **P-37w** escribe sobre la fila `[1]` del diario. Con el parche da `AccessError` y no cambia nada. Sin
    el parche la alteraría; el «antes» de A.5 permite verlo.
- **Scripts de la 4 bis adaptados** (paso 2): P-82.

**Línea base** (después de crear los datos y antes de las pruebas), con `SELECT` de solo lectura:
`count(*)` de `ai_safe_operation`, `ai_change_journal` e `ir_attachment`, y el diario entero (A.5).

### D.1 Pruebas de seguridad

| # | Prueba (parche) | Quién | Qué se hace | Esperado | Obtenido |
|---|---|---|---|---|---|
| 1 | **P-37w/c** (parche 17) | ADM, `pruebas_e2p_lab.py` | `write` y `create` en `ai.change.journal` por `call_kw` ([lab](lab_e2_3879.md), §2) | `AccessError` «Only the system can write the AI change journal.» en los dos; el diario igual que en A.5 | [ ] |
| 2 | **P-37b** (parche 17), **primera vez de forma manual** (en el laboratorio solo la cubrió `test_plan_unlink_requires_unlink_right`) | ADM prepara; UW propone y confirma | Preparación de [lab](lab_e2_3879.md) §3, con UW en lugar de `demo`: etiqueta «Seges P-37b»; grupo «Seges P-37b» con leer y escribir sobre `res.partner.category`, sin crear ni eliminar; UW en el grupo. Propuesta con el script (`E2P_KEY_DEMO` = clave de UW) o, sin script, UW en Chatboo: «borra la etiqueta de contacto Seges P-37b». Después, UW en AI Engine → Security → My Authorizations → la operación → confirmar (pide la contraseña) | Error en la ejecución por falta de permiso de borrado; la etiqueta sigue `active`; en el diario, ninguna fila `unlink` `applied` y una `failed` del intento. Consultas de [lab](lab_e2_3879.md) §3 en `odoo14_pns_db` / `pns_demo` | [ ] |
| 3 | **P-19** (parche 18) | ADM, `pruebas_e2p_lab.py` | Casos a a j, r1 y r2 ([lab](lab_e2_3879.md), §1) | a a j: rechazo «Field api_key of ai.provider…» o «Field value of ir.config_parameter… cannot be read from the RelaxAICode sandbox.»; r1 y r2 responden. Si A.8 da 0 proveedores en el agente admin, la b devuelve `[]` y no prueba nada (como en el laboratorio) | [ ] |
| 3b | **P-101** (parche 23), en el mismo script | ADM | Casos a a e y r ([lab](lab_e2_3879.md), §1b) | a a e: rechazo «it is the ORM's own state»; r responde | [ ] |
| 4 | **P-82** (parche 11 adaptado), prueba 4 bis de E2 | B; Sergio por SQL | Como la 4 bis de E2 ([verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E2»): B crea una sesión; **[ALTERA]** Sergio engancha a ella por SQL el adjunto X de A2 (`UPDATE 1`); B cuelga un adjunto propio Z2 y borra la sesión desde History | Z2 borrado; X existe con `res_model` vacío, `res_id` 0 y `create_uid` de A2; A2 descarga X (200) y B no (404) | [ ] |
| 5 | **P-70** (parche 20), casos 1 a 5 | ADM, navegador de Sergio | Pasos de [lab](lab_e2_3879.md) §5 y la comprobación de consola de cada paso; el tablero de Facturación por URL con el id de A.8 (`/web#action=<id>`). Casos 1 a 4 con recarga sin caché; caso 5 con caché normal en un navegador que abrió el chat antes de E2′ | `[undefined, true, "4.4.8"]` (antes de abrir el chat, el tercero `undefined`); sin errores `xAxes`/`yAxes`; el gráfico del chat se pinta; en el caso 5, `chart.umd.min.js?seges=20` en la pestaña Red | [ ] |
| 6 | **P-20** (parche 21), casos A y B | ADM, navegador de Sergio | Pasos de la [propuesta](e2_propuesta_3879.md), «P-20: pasos y consultas», con los registros del staging (A.8). Caso A: un proveedor que no sea el primero de la cadena de Chatboo, `temperature` → un valor nuevo que se distinga (por ejemplo, 0.43). Caso B: el usuario MCP de U1, `last_mcp_client_label` → `P-20b staging`. «Review» sin Confirmar y cerrar; consulta antes, después de «Review» y después de cerrar (la de [lab](lab_e2_3879.md) §6, con los ids del staging). JSON en una carpeta temporal fuera del repo, que se borra al acabar | Valor y `write_date` iguales a los de «antes» en los dos casos | [ ] |
| — | No se repiten aquí | — | **P-17:** sin servidor de pruebas en el staging (propuesta final); la cubren la prueba manual del laboratorio y `test_seges_fetch_redirect.py`. **P-101′ y P-102:** validadas con la herramienta real en el laboratorio y cubiertas por `test_seges_format_guard.py` y `test_seges_identity_su.py` | — | — |

**P-20 B:** cualquier conexión por `/mcp` reescribe `last_mcp_client_label` con el `clientInfo` del cliente.
En el laboratorio, el 28/10, se vio `seges-e2p-viab 1`. U1 no debe conectar por MCP entre el «antes» y el
«después».

### D.2 No regresión (con el proveedor de A.7)

| # | Caso | Quién | Esperado | Obtenido |
|---|---|---|---|---|
| R1 | Turno de Chatboo con una consulta de datos (la caja A sigue respondiendo con el control por campos del parche 18 y el formateador del 23) | U1 | Respuesta correcta; tabla con formato | [ ] |
| R2 | **Descargas:** Excel del motor y PDF montado en el navegador | U1 | Las dos descargan. El PDF puede quedar huérfano (PNS-98, conocido) | [ ] |
| R3 | **Gráficos:** gráfico en el chat y cambio a gráfico de una tabla del historial | U1 | Se pintan; sin errores en la consola (complementa P-70) | [ ] |
| R4 | **Borrar una sesión con adjuntos** desde History (R5 de E2) | U1 | Sin error; desaparecen la sesión y sus adjuntos enganchados; los huérfanos siguen | [ ] |
| R5 | **Autorizaciones:** «Confirmar y ejecutar» de una operación pendiente (R5 de E1′) | ADM | Pide la contraseña una vez y ejecuta | [ ] |
| R6 | **Diario, Revertir:** ADM borra por plan confirmado un registro de prueba (por ejemplo, una etiqueta «Seges E2p diario»); en AI Engine → Security → Applied changes, la fila `unlink` → «Revert» | ADM | La fila se crea con el borrado en papelera (la escribe el sistema: parche 17, sin `AccessError`); «Revert» devuelve el registro; la fila pasa a `reverted` y aparece otra `applied` con `origin` `revert` y `reverts_id` = la original (`ai_change_journal.py`, `action_revert`) | [ ] |
| R7 | **Diario, Vaciar papelera:** otro borrado igual y «Empty trash» (o «Delete permanently» en la fila) | ADM | El registro se borra definitivamente, sin `AccessError`; anotar el estado final de la fila | [ ] |
| R8 | **Importaciones con «Review» y con Confirmar** | ADM | «Review» y cerrar: sin cambios (es P-20). Después, con Confirmar: el cambio se aplica. Devolver el valor original (otra importación o la ficha) | [ ] |
| R9 | `relaxaicode` normal por `/mcp`: `search_count` de contactos (R7 de E1′) | ADM | Responde con el número | [ ] |
| R10 | Log desde el arranque (B.8) | — | Sin `Traceback` salvo los del proveedor (429/503); los rechazos provocados en D.1, a su hora | [ ] |

### D.3 Limpieza de las pruebas

**[ALTERA]** Mínima, porque la limpieza general es al final de todos los cambios. Se revocan las claves MCP
temporales: la de ADM y, si se generó, la de UW. Se quitan a UW el grupo «Seges P-37b» y se archivan el
grupo y la etiqueta. Se borran o archivan los usuarios de P-82 (A2 y B) y sus sesiones, cada una por su
dueño, como en E2. Si P-20 hubiera cambiado algo, se devuelve el valor original. La fila `failed` de
P-37b y las de R6 y R7 se quedan en el diario, porque no se pueden borrar desde Odoo. Resultado en la
[verificación](verificacion_seguridad_pns_ai.md), en un bloque nuevo «Staging — entrega E2′».

---

## E. Vuelta atrás (descrita, no lista para pegar)

Operaciones que cambian el VPS: las decide y hace quien administra el VPS.

1. **Antes del `-u` (fallo en B.3 a B.6).** `pns_demo` no ha cambiado. Se devuelve el código de `0366231`
   desde `addons_antes_E2p`, con `rsync --delete` módulo a módulo. Se comprueba la huella de A.3 (696,
   `c12168ea…`) y se arranca `web`.
2. **Después del `-u`.** A diferencia de E1′, el `-u` de E2′ no cambia el esquema: ni campos ni versiones.
   Volver el código a `0366231` como en el punto 1 y reiniciar debería dejar el staging como tras E1′.
   **Sin confirmar** (no ensayado). El riesgo es bajo porque los datos que cargó el `-u` son los mismos
   de E1′. Lo escrito con el código nuevo (filas del diario, adjuntos desenganchados por el parche 11) se
   queda. Si hay dudas, se corrige hacia delante con un commit nuevo y el mismo procedimiento.
3. **`addons_antes_E2p`** se conserva hasta la limpieza final del staging, como las anteriores.

---

## F. Lo que no está documentado

| Dato | Dónde se comprueba |
|---|---|
| `WARNING` del `-u` de E2′ | Sin referencia: el laboratorio no hizo `-u` con E2′. Se anotan los de B.8 |
| Scripts de E2′ para el staging | Requisito bloqueante de D.0 (pasos previos 1 y 2): adaptar `pruebas_e2p_lab.py` para que no imprima la respuesta de un caso de P-19 no rechazado, y los scripts de la 4 bis por el choque con `e2_aiadmin`. Los dos, validados contra el laboratorio antes de tocar el staging |
| Usuario para P-37b sin permiso de borrado de etiquetas por otro grupo | A.8 (consulta de permisos con el login elegido) |
| Proveedores del agente admin en `pns_demo` (P-19b) | A.8 |
| Id de la acción del tablero de Facturación en `pns_demo` (P-70) | A.8 (en el laboratorio era 335) |
| Cuota de Gemini el día de la subida | Consola de Google AI Studio, no solo «Test Connection» (F de E1′) |
| E3′ y E4′ | **No entran en esta subida.** E3′ (lienzo: M1, M2 y F1; R8 y la revisión de la ventana de `_ask_design` del parche 18) y E4′ (hoja de Medios y Bajos) se suben con su propio documento cuando estén validadas en el laboratorio. Por eso no hay prueba del lienzo en D |
