# Subida de E2′ al staging `pns_demo` (parches 11 adaptado y 17 a 24)

- **Rama:** `14.0-pns-ai-3879` · **Base:** `c639fa8` (código de los módulos igual al de `0366231`, lo montado
  en E1′) · **Commit a desplegar:** `9a2970d`, el último que toca los módulos. Cualquier commit posterior
  que solo sea [DOC] (como `4a6b432`) da el mismo árbol y la misma huella del árbol, pero otra huella del
  `.tar.gz` (B.1) · **Preparado:** 28/10/2026 · **Estado:** ejecutado el 29/10/2026 con `9a2970d`;
  resultado en «Resultado de la subida (29/10/2026)», al final. Los pasos marcados «(corregido el
  29/10/2026)» recogen lo que hubo que cambiar durante la subida.
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
G. Resultado de la subida (29/10/2026)

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
-- P-37b: usuarios con AI Writer y si ya pueden borrar etiquetas de contacto (res.partner.category)
SELECT u.id, u.login, u.active, u.share,
       EXISTS (SELECT 1 FROM ir_model_access a
                 JOIN ir_model m ON m.id = a.model_id AND m.model = 'res.partner.category'
                WHERE a.active AND a.perm_unlink
                  AND (a.group_id IS NULL OR a.group_id IN (
                         SELECT r.gid FROM res_groups_users_rel r WHERE r.uid = u.id))
       ) AS puede_borrar_etiquetas
  FROM res_users u
  JOIN res_groups_users_rel w ON w.uid = u.id
  JOIN ir_model_data d ON d.model = 'res.groups' AND d.res_id = w.gid
 WHERE d.module = 'pns_ai_mcp' AND d.name = 'group_ai_writer'
 ORDER BY u.id;
ROLLBACK;
SQL
```

Para P-37b, el usuario de prueba **no puede tener ya `perm_unlink`** sobre `res.partner.category` por otro
grupo: con `base.group_partner_manager`, por ejemplo, la prueba no discriminaría. Se elige uno interno
(`share` falso) y activo con `puede_borrar_etiquetas` falso; si no hay ninguno, se crea uno temporal (D.0).
**(corregido el 29/10/2026:** la consulta anterior pedía sustituir un `'<login>'` a mano; esta lista
directamente los candidatos. En `pns_demo`, `admin` y UW ya podían borrar etiquetas y se usó un usuario
temporal.**)**

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
read -rp 'Puerto SSH del VPS: ' VPS_PORT; read -rp 'Usuario@host del VPS: ' VPS_DEST
scp -P "$VPS_PORT" /tmp/pns_addons_9a2970d.tar.gz "$VPS_DEST":/tmp/
```

**(corregido el 29/10/2026:** los marcadores `<puerto>` y `<usuario>@<host>` se sustituyen por dos
variables que se piden al pegar, para no editar la orden.**)**

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
| Versiones | Las de A.4, `installed` | [x] Igual que A.4 |
| Cron de la papelera | `pns_ai_mcp.ir_cron_ai_journal_trash` activo, diario, `numbercall` -1, `user_id` 1. Con el parche 17 el diario solo lo escribe el sistema, y el cron corre como superusuario | [x] Igual que A.4 |
| Resto de crons | Los seis de A.4, sin cambios | [x] Igual que A.4; los de 5 minutos se ejecutaron a las 11:08 UTC con el código nuevo |
| Neutralización | Ninguna fila `odoo_dev.%` | [x] Ninguna |

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
| W | usuario **temporal** interno (en la subida, `e2p_writer`), con AI Writer y AI Conversational, contraseña local y clave MCP propia, sin permiso de borrado de etiquetas | P-37b |
| A2 y B | `e2p_interno_a` y `e2p_interno_b`: internos sin más grupos, creados y borrados por [`prueba4_bis_e2p.py`](scripts_e2/prueba4_bis_e2p.py) (`--preparar` y `--limpiar`) | P-82 |

**(corregido el 29/10/2026:** UW ya no es necesario: P-37b la hace W y R5 (Autorizaciones), ADM. Donde
D.1 (fila 2) dice UW, léase W.**)** Preparación de W:
- Usuario interno con **AI Writer y AI Conversational**: `/mcp` exige AI Conversational porque el agente
  del usuario es conversacional; sin ese grupo, el script responde «Esta clave no ve la herramienta
  safe_plan_request». Contraseña local y clave MCP propia (Usuarios MCP).
- Los grupos se añaden **desde la ficha del usuario o desde la del grupo**. En la subida, marcar la casilla
  AI Conversational en Usuarios MCP y guardar no dejó el grupo puesto: fallo de la casilla (observación
  para E4′ en el plan de corrección).
- Después, la consulta de P-37b de A.8: W debe salir con `puede_borrar_etiquetas` falso. Los grupos que la
  plantilla de usuario añade por defecto pueden cambiar de una BD a otra.

**Requisitos previos: dos pasos de código (cumplidos el 29/10/2026).** No se empezaba A ni se tocaba el
staging hasta que los dos estuvieran hechos y validados contra el laboratorio (`lab_pns_ai_3879`); los
dos lo están y D.0 ya no bloquea la subida. Precedente: los scripts de E1′ se prepararon y validaron
contra el laboratorio el 26/10/2026, antes de la subida ([subida de E1′](staging_e1_3879.md), D.0). Son
scripts del equipo de Sergio y no código de los módulos, y los dos están en el repo:
[scripts_e2/pruebas_e2p_lab.py](scripts_e2/pruebas_e2p_lab.py) (P-19, P-101 y P-37) y
[scripts_e2/prueba4_bis_e2p.py](scripts_e2/prueba4_bis_e2p.py) (P-82).

| # | Paso previo | Por qué bloquea | Validación en el laboratorio | Hecho |
|---|---|---|---|---|
| 1 | **Adaptar `pruebas_e2p_lab.py`** para que, si un caso de P-19 **no** se rechaza, no imprima la respuesta: solo un marcador de «no rechazado» y el tipo del resultado, **nunca el contenido ni la clave**. Los casos rechazados siguen mostrando el mensaje de rechazo, y los controles (r1, r2, P-101r) su respuesta | Tal como está, un caso no rechazado imprime los 200 primeros caracteres de la respuesta. En el staging podría ser la clave real de Gemini | Ejecutarlo contra `lab_pns_ai_3879_14` y comprobar dos cosas: que P-19, P-101 y P-37 dan lo mismo que el 28/10 ([lab](lab_e2_3879.md), «Resultado (28/10/2026)»), y que un caso forzado a no rechazarse (por ejemplo, el control r1 tratado como si fuera de secreto) sale solo con el marcador y el tipo | [x] 29/10/2026: validado en `lab_pns_ai_3879_14`, sin diferencias con el 28/10 y con el forzado solo en r1; guardado en [scripts_e2/pruebas_e2p_lab.py](scripts_e2/pruebas_e2p_lab.py) ([lab](lab_e2_3879.md), «Validación del script, paso 1 de D.0 (29/10/2026)») |
| 2 | **Adaptar los scripts de la 4 bis (P-82)**, `preparar_e2.py` y `prueba4_bis_e2.py` (`~/staging_e2`), para que no choquen con `e2_aiadmin` (id 17, archivado en `pns_demo`): que creen solo A2, B y el adjunto X (sin `e2_aiadmin`), o que usen logins nuevos. También tienen que funcionar sobre 3.1.879 | `preparar_e2.py` vuelve a crear `e2_aiadmin` y el login único chocaría. Además, la comparación anota cambios de 3.1.879 en esas vías (§4.2, «Scripts de staging») | Prueba 4 bis completa en `lab_pns_ai_3879_14`: Z2 borrado; X desenganchado y de A2; A2 descarga X (200) y B no (404). Después, limpieza de los usuarios y del adjunto de prueba en el laboratorio | [x] 29/10/2026: script nuevo [scripts_e2/prueba4_bis_e2p.py](scripts_e2/prueba4_bis_e2p.py), con logins `e2p_interno_a` y `e2p_interno_b` y sin tocar `e2_aiadmin`; prueba completa en `lab_pns_ai_3879_14` TODO OK y limpieza sin restos ([lab](lab_e2_3879.md), «Validación del script de la 4 bis, paso 2 de D.0 (29/10/2026)»). Sustituye a `preparar_e2.py` y `prueba4_bis_e2.py`; los de `~/staging_e2` quedan como registro de E2, sin cambios |

**Scripts** (equipo de Sergio, se ejecutan desde la carpeta `~/staging_e2p`; nada se copia al VPS). Los
dos tienen por defecto el laboratorio: en el staging, siempre con `E2P_URL` y `E2P_DB` del staging:
- **`pruebas_e2p_lab.py` adaptado** (paso 1), en
  [scripts_e2/pruebas_e2p_lab.py](scripts_e2/pruebas_e2p_lab.py); se copia a `~/staging_e2p`: P-19,
  P-101, P-37w/c y la propuesta de P-37b. Variables: `E2P_URL=https://pns.liyben.com`, `E2P_DB=pns_demo`,
  `E2P_ADM_PASS`, `E2P_KEY_ADM` y `E2P_SECRET_ID` (A.8). Para P-37b, además, `E2P_KEY_DEMO` (la clave de
  W) y `E2P_P37B_CAT`. Las claves, con `read -rsp` (ni en el historial ni en pantalla), y todas se borran
  al acabar. **(corregido el 29/10/2026:** el `mkdir -p` va antes del primer `cp`; antes solo estaba en el
  bloque de `prueba4_bis_e2p.py`.**)**
  ```sh
  mkdir -p ~/staging_e2p
  cp ~/GitHub/third_party/docs/pendiente/scripts_e2/pruebas_e2p_lab.py ~/staging_e2p/
  cd ~/staging_e2p
  read -rsp 'Contraseña de admin: ' E2P_ADM_PASS; echo
  read -rsp 'Clave MCP de ADM: ' E2P_KEY_ADM; echo
  read -rp 'Id de database.secret (A.8): ' E2P_SECRET_ID
  export E2P_URL=https://pns.liyben.com E2P_DB=pns_demo E2P_ADM_PASS E2P_KEY_ADM E2P_SECRET_ID
  # Para P-37b, antes de ejecutar:
  #   read -rsp 'Clave MCP de W: ' E2P_KEY_DEMO; echo
  #   read -rp 'Id de la etiqueta Seges P-37b: ' E2P_P37B_CAT
  #   export E2P_KEY_DEMO E2P_P37B_CAT
  python3 pruebas_e2p_lab.py
  unset E2P_URL E2P_DB E2P_ADM_PASS E2P_KEY_ADM E2P_SECRET_ID E2P_KEY_DEMO E2P_P37B_CAT
  ```
  Sin `E2P_FORZAR_NO_RECHAZO` (solo sirve para validar el script en el laboratorio).
  - **P-37w** escribe sobre la fila `[1]` del diario. Con el parche da `AccessError` y no cambia nada. Sin
    el parche la alteraría; el «antes» de A.5 permite verlo.
- **`prueba4_bis_e2p.py`** (paso 2), en [scripts_e2/prueba4_bis_e2p.py](scripts_e2/prueba4_bis_e2p.py):
  P-82 (D.1, fila 4). Escribe `e2p_estado.json` (solo ids, sin secretos) en la carpeta actual, así que
  se ejecuta desde `~/staging_e2p` y no desde el repo. `E2P_PSQL` se deja sin definir: el script usa por
  defecto `docker exec -i odoo14_pns_db sh -c 'psql -U "$POSTGRES_USER" -d pns_demo'`, el del VPS, y lo
  imprime en la pausa con el `UPDATE` que hay que lanzar allí. Las contraseñas, con `read -rsp`:
  ```sh
  cp ~/GitHub/third_party/docs/pendiente/scripts_e2/prueba4_bis_e2p.py ~/staging_e2p/
  cd ~/staging_e2p
  read -rsp 'Contraseña de admin: ' E2P_ADM_PASS; echo
  read -rsp 'Contraseña común de A2 y B (nueva, solo para la prueba): ' E2P_TEST_PASS; echo
  export E2P_URL=https://pns.liyben.com E2P_DB=pns_demo E2P_ADM_PASS E2P_TEST_PASS
  python3 prueba4_bis_e2p.py --preparar   # [ALTERA] crea A2, B y el adjunto X de A2
  python3 prueba4_bis_e2p.py              # la prueba; en la pausa, el UPDATE que imprime, en el VPS
  python3 prueba4_bis_e2p.py --limpiar    # [ALTERA] D.3
  unset E2P_URL E2P_DB E2P_ADM_PASS E2P_TEST_PASS
  ```
  `--preparar` aborta sin tocar nada si `e2p_interno_a` o `e2p_interno_b` ya existen como portal o con
  Ajustes, administración, AI Administrator o AI Conversational. Si la prueba se corta (por ejemplo, en la
  pausa o por un fallo), `--limpiar` recoge lo que haya quedado: sesiones, X, Z2 y los dos usuarios.

**Línea base** (después de crear los datos y antes de las pruebas), con `SELECT` de solo lectura:
`count(*)` de `ai_safe_operation`, `ai_change_journal` e `ir_attachment`, y el diario entero (A.5).

### D.1 Pruebas de seguridad

| # | Prueba (parche) | Quién | Qué se hace | Esperado | Obtenido |
|---|---|---|---|---|---|
| 1 | **P-37w/c** (parche 17) | ADM, [`pruebas_e2p_lab.py`](scripts_e2/pruebas_e2p_lab.py) (ejecución de D.0) | `write` y `create` en `ai.change.journal` por `call_kw` ([lab](lab_e2_3879.md), §2) | `AccessError` «Only the system can write the AI change journal.» en los dos; el diario igual que en A.5 | [x] OK: diario intacto (la fila 1 conserva su `write_date` del 16/10) |
| 2 | **P-37b** (parche 17), **primera vez de forma manual** (en el laboratorio solo la cubrió `test_plan_unlink_requires_unlink_right`) | ADM prepara; UW propone y confirma | Preparación de [lab](lab_e2_3879.md) §3, con UW en lugar de `demo`: etiqueta «Seges P-37b»; grupo «Seges P-37b» con leer y escribir sobre `res.partner.category`, sin crear ni eliminar; UW en el grupo. Propuesta con el [script](scripts_e2/pruebas_e2p_lab.py) (`E2P_KEY_DEMO` = clave de UW, con `read -rsp` como en D.0) o, sin script, UW en Chatboo: «borra la etiqueta de contacto Seges P-37b». Después, UW en AI Engine → Security → My Authorizations → la operación → confirmar (pide la contraseña) | Error en la ejecución por falta de permiso de borrado; la etiqueta sigue `active`; en el diario, ninguna fila `unlink` `applied` y una `failed` del intento. Consultas de [lab](lab_e2_3879.md) §3 en `odoo14_pns_db` / `pns_demo` | [x] OK, con W = `e2p_writer` (id 23): propuesta `UNLK00000001`; al confirmar, error «No puedes borrar… res.partner.category» (solo Contact Creation); la etiqueta 8 sigue activa; diario: fila 13 `unlink` `failed` (`create_uid` 1); `ai_safe_operation` 32 `cancelled`. Las dos primeras ejecuciones del script fallaron porque W no tenía AI Conversational (D.0) |
| 3 | **P-19** (parche 18) | ADM, [`pruebas_e2p_lab.py`](scripts_e2/pruebas_e2p_lab.py) (ejecución de D.0) | Casos a a j, r1 y r2 ([lab](lab_e2_3879.md), §1) | a a j: rechazo «Field api_key of ai.provider…» o «Field value of ir.config_parameter… cannot be read from the RelaxAICode sandbox.»; r1 y r2 responden. Si A.8 da 0 proveedores en el agente admin, la b devuelve `[]` y no prueba nada (como en el laboratorio). **Cómo leer el marcador:** «NO RECHAZADO (… vacío)» en la b = no prueba nada (sin proveedores en el agente admin), igual que en el laboratorio; cualquier «NO RECHAZADO (… no vacío)» = **parar la prueba y escalarlo**, sin abrir el contenido ni repetirla | [x] OK; la b, «NO RECHAZADO (… vacío)» (0 proveedores en el agente admin, ya conocido) |
| 3b | **P-101** (parche 23), en el mismo script | ADM | Casos a a e y r ([lab](lab_e2_3879.md), §1b) | a a e: rechazo «it is the ORM's own state»; r responde | [x] OK |
| 4 | **P-82** (parche 11 adaptado), prueba 4 bis de E2 | A2 y B (`e2p_interno_a`, `e2p_interno_b`); Sergio por SQL | Con [`scripts_e2/prueba4_bis_e2p.py`](scripts_e2/prueba4_bis_e2p.py) (`--preparar`, la prueba, `--limpiar`; ejecución en D.0, desde `~/staging_e2p`, con `E2P_URL` y `E2P_DB` del staging). Como la 4 bis de E2 ([verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E2»): B crea su sesión CS_B2; **[ALTERA]** Sergio engancha a ella por SQL el adjunto X de A2 (`UPDATE 1`); B cuelga un adjunto propio Z2 y borra la sesión con `unlink`, el método al que llama el borrado de History (`/chatboo/sessions/delete` → `session.unlink()`). **Por qué no desde History:** esa ruta exige acceso a Chatboo (grupo AI Conversational + clave MCP propia) y no se quiere crear ni revocar una clave para B en `pns_demo`; la lógica del parche 11 está en `unlink()` y es la misma; el controlador de History se ejercita en la no regresión del chat con U1 (D.2, R4) | X con `res_model` vacío, `res_id` 0 y `create_uid` de A2; Z2 borrado; CS_B2 borrada; A2 descarga X (200) y B recibe 404 exacto. El script termina con «RESULTADO: TODO OK» | [x] TODO OK: A2 24, B 25, X 915, CS_B2 48, Z2 916; X (False, 0, 24); A2 200, B 404; `--limpiar` borró los dos usuarios (no hizo falta archivarlos) |
| 5 | **P-70** (parche 20), casos 1 a 5 | ADM, navegador de Sergio | Pasos de [lab](lab_e2_3879.md) §5 y la comprobación de consola de cada paso; el tablero de Facturación por URL con el id de A.8 (`/web#action=<id>`). **El caso 5, primero**, con caché normal en el navegador habitual (el que abrió el chat antes de E2′); **después los casos 1 a 4, en una ventana privada**. **(corregido el 29/10/2026:** antes decía casos 1 a 4 con recarga sin caché y caso 5 después; hechos en ese orden en el mismo navegador, los casos 1 a 4 renuevan la caché y el caso 5 ya no prueba nada.**)** | `[undefined, true, "4.4.8"]` (antes de abrir el chat, el tercero `undefined`); sin errores `xAxes`/`yAxes`; el gráfico del chat se pinta; en el caso 5, `chart.umd.min.js?seges=20` en la pestaña Red | [x] OK casos 1 a 5: el 5 primero, en el navegador habitual con caché, con `?seges=20`; los 1 a 4 en ventana privada; sesión antigua 39 |
| 6 | **P-20** (parche 21), casos A y B | ADM, navegador de Sergio | Pasos de la [propuesta](e2_propuesta_3879.md), «P-20: pasos y consultas», con los registros del staging (A.8). Caso A: un proveedor que no sea el primero de la cadena de Chatboo, `temperature` → un valor nuevo que se distinga (por ejemplo, 0.43). Caso B: el usuario MCP de U1, `last_mcp_client_label` → `P-20b staging`. «Review» sin Confirmar y cerrar; consulta antes, después de «Review» y después de cerrar (la de [lab](lab_e2_3879.md) §6, con los ids del staging). JSON en una carpeta temporal fuera del repo, que se borra al acabar | Valor y `write_date` iguales a los de «antes» en los dos casos | [x] OK A (proveedor 3, `temperature` 0.7 → 0.43) y B (usuario MCP 2, de U1, etiqueta → «P-20b staging»), con «Will replace» en «Review»: valor y `write_date` sin cambios después de «Review» y después de cerrar; el `res.users` de U1 sin cambios |
| — | No se repiten aquí | — | **P-17:** sin servidor de pruebas en el staging (propuesta final); la cubren la prueba manual del laboratorio y `test_seges_fetch_redirect.py`. **P-101′ y P-102:** validadas con la herramienta real en el laboratorio y cubiertas por `test_seges_format_guard.py` y `test_seges_identity_su.py` | — | — |

**P-20 B:** cualquier conexión por `/mcp` reescribe `last_mcp_client_label` con el `clientInfo` del cliente.
En el laboratorio, el 28/10, se vio `seges-e2p-viab 1`. U1 no debe conectar por MCP entre el «antes» y el
«después».

### D.2 No regresión (con el proveedor de A.7)

| # | Caso | Quién | Esperado | Obtenido |
|---|---|---|---|---|
| R1 | Turno de Chatboo con una consulta de datos (la caja A sigue respondiendo con el control por campos del parche 18 y el formateador del 23) | U1 | Respuesta correcta; tabla con formato | [x] Validada por Sergio, sin consultas de comprobación |
| R2 | **Descargas:** Excel del motor y PDF montado en el navegador | U1 | Las dos descargan. El PDF puede quedar huérfano (PNS-98, conocido) | [x] Validada por Sergio, sin consultas de comprobación |
| R3 | **Gráficos:** gráfico en el chat y cambio a gráfico de una tabla del historial | U1 | Se pintan; sin errores en la consola (complementa P-70) | [x] Validada por Sergio, sin consultas de comprobación |
| R4 | **Borrar una sesión con adjuntos** desde History (R5 de E2) | U1 | Sin error; desaparecen la sesión y sus adjuntos enganchados; los huérfanos siguen | [x] Validada por Sergio, sin consultas de comprobación |
| R5 | **Autorizaciones:** «Confirmar y ejecutar» de una operación pendiente (R5 de E1′) | ADM | Pide la contraseña una vez y ejecuta | [x] OK |
| R6 | **Diario, Revertir:** ADM borra por plan confirmado un registro de prueba (por ejemplo, una etiqueta «Seges E2p diario»); en AI Engine → Security → Applied changes, la fila `unlink` → «Revert» | ADM | La fila se crea con el borrado en papelera (la escribe el sistema: parche 17, sin `AccessError`); «Revert» devuelve el registro; la fila pasa a `reverted` y aparece otra `applied` con `origin` `revert` y `reverts_id` = la original (`ai_change_journal.py`, `action_revert`) | [x] OK: fila 14 `unlink` → `reverted`; fila 15 con `origin` `revert` y `reverts_id` 14; la etiqueta 9 vuelve. `create_uid` 2 (el `sudo` conserva el uid) |
| R7 | **Diario, Vaciar papelera:** otro borrado igual y «Empty trash» (o «Delete permanently» en la fila) | ADM | El registro se borra definitivamente, sin `AccessError`; anotar el estado final de la fila | [x] OK: la fila 16 queda en `applied` (`create_uid` 2) y la etiqueta 10 se borró definitivamente |
| R8 | **Importaciones con «Review» y con Confirmar** | ADM | «Review» y cerrar: sin cambios (es P-20). Después, con Confirmar: el cambio se aplica. Devolver el valor original (otra importación o la ficha) | [x] OK: 0.43 confirmado y devuelto a 0.7 (12:37 UTC) |
| R9 | `relaxaicode` normal por `/mcp`: `search_count` de contactos (R7 de E1′) | ADM | Responde con el número | [x] Cubierta por los controles P-19 r1/r2 y P-101 r del script (`relaxaicode` normal por `/mcp` como ADM) |
| R10 | Log desde el arranque (B.8) | — | Sin `Traceback` salvo los del proveedor (429/503); los rechazos provocados en D.1, a su hora | [x] 8 líneas, todas esperadas: un 503 de Gemini (12:13 UTC) y los dos `ERROR` de P-37b, cada uno con dos `Traceback` encadenados |

### D.3 Limpieza de las pruebas

**[ALTERA]** Mínima, porque la limpieza general es al final de todos los cambios:
- Se revocan las claves MCP temporales: la de ADM y la de W (el usuario de P-37b).
- Se archiva W: la fila `failed` de P-37b lo referencia y no se borra.
- Se archivan las etiquetas «Seges P-37b» y la de R6 (la que «Revert» devolvió).
- Se borra el grupo «Seges P-37b»: en Odoo 14 los grupos no se pueden archivar.
- Los usuarios de P-82 se quitan con `prueba4_bis_e2p.py --limpiar` (ejecución de D.0): cada usuario
  borra sus sesiones; se borran X y Z2 y los dos usuarios con su contacto; si la FK del diario impide
  borrar un usuario, queda archivado (se anota).
- Si P-20 hubiera cambiado algo, se devuelve el valor original.
- La fila `failed` de P-37b y las de R6 y R7 se quedan en el diario, porque no se pueden borrar desde Odoo.

**(corregido el 29/10/2026:** se añaden la clave y el archivado de W, la etiqueta de R6 y el borrado del
grupo, que antes decía «archivar»; la consulta final lista los logins `e2p_` en vez de contarlos y
comprueba las claves revocadas.**)**

**[LECTURA]** Comprobación final, en el VPS. La última consulta dice si hay hash, **sin leerlo**:

```sh
docker exec -i odoo14_pns_db psql -U odoo -d pns_demo -v ON_ERROR_STOP=1 <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT id, login, active FROM res_users WHERE login LIKE 'e2p\_%' ORDER BY id;
SELECT count(*) AS adjuntos_e2p FROM ir_attachment WHERE name LIKE 'e2p-%';
SELECT count(*) AS sesiones_e2p
  FROM chatboo_session s JOIN res_users u ON u.id = s.user_id
 WHERE u.login LIKE 'e2p\_%';
SELECT m.id, u.login, m.mcp_api_key_state,
       coalesce(m.mcp_api_key_hash, '') <> '' AS tiene_hash
  FROM ai_mcp_user m JOIN res_users u ON u.id = m.user_id
 WHERE u.login = 'admin' OR u.login LIKE 'e2p\_%'
 ORDER BY m.id;
ROLLBACK;
SQL
```

Esperado: solo W, archivado (`active` falso); 0 adjuntos y 0 sesiones; las claves de `admin` y W en
`not_generated` y `tiene_hash` falso. Si `--limpiar` archivó algún usuario de P-82, sale en la primera
consulta y se anota.
Resultado en la [verificación](verificacion_seguridad_pns_ai.md), en un bloque nuevo «Staging — entrega
E2′».

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
| Scripts de E2′ para el staging | Pasos previos 1 y 2 de D.0, hechos el 29/10/2026; D.0 ya no bloquea la subida. Paso 1: [scripts_e2/pruebas_e2p_lab.py](scripts_e2/pruebas_e2p_lab.py) ([lab](lab_e2_3879.md), «Validación del script, paso 1 de D.0 (29/10/2026)»). Paso 2: [scripts_e2/prueba4_bis_e2p.py](scripts_e2/prueba4_bis_e2p.py), sin `e2_aiadmin` ([lab](lab_e2_3879.md), «Validación del script de la 4 bis, paso 2 de D.0 (29/10/2026)»). Los dos, validados contra el laboratorio |
| Usuario para P-37b sin permiso de borrado de etiquetas por otro grupo | A.8 (consulta de permisos con el login elegido) |
| Proveedores del agente admin en `pns_demo` (P-19b) | A.8 |
| Id de la acción del tablero de Facturación en `pns_demo` (P-70) | A.8 (en el laboratorio era 335) |
| Cuota de Gemini el día de la subida | Consola de Google AI Studio, no solo «Test Connection» (F de E1′) |
| E3′ y E4′ | **No entran en esta subida.** E3′ (lienzo: M1, M2 y F1; R8 y la revisión de la ventana de `_ask_design` del parche 18) y E4′ (hoja de Medios y Bajos) se suben con su propio documento cuando estén validadas en el laboratorio. Por eso no hay prueba del lienzo en D |

---

## G. Resultado de la subida (29/10/2026)

Sergio con Claude; horas en UTC. Commit `9a2970d` de `14.0-pns-ai-3879`. Resultado por prueba en las
columnas «Obtenido» de C.2, D.1 y D.2; resumen en la [verificación](verificacion_seguridad_pns_ai.md),
«Staging — entrega E2′ (29/10/2026)».

### A. Comprobaciones previas

- **A.1 a A.4:** como se esperaba. Montaje de `addons` de solo lectura; 0 `__pycache__` y 0 archivos de
  otro usuario; 696 archivos, huella `c12168ea…6160`; 7 crons `pns_*`.
- **A.5:** 0 filas en papelera; `pns_ai_mcp.journal_trash_days` sin definir; diario de 12 filas
  (guardado en `/tmp/pns_e2p_diario_antes.txt` del VPS).
- **A.6:** a) 200; b) 14 (9 JS y 5 CSS de `ir.ui.view`, de `__system__`, el último del 26/10); d) 13.
  Consulta 3 vacía: se mantiene la decisión 7.
- **A.7:** cadena de Chatboo con Gemini 3.6 flash, 3.5 flash y 3.5 flash lite; «Test Connection» correcto
  y cuota disponible. El primer «Test Connection» de 3.6 flash dio HTTP 503 (10:50:35); al repetirlo salió
  bien.
- **A.8:** `database.secret` id 1; 206 logs con proveedor; 0 proveedores en el agente admin (P-19b no
  prueba nada, como en el laboratorio); acción del tablero de Facturación 334. Para P-37b, `admin` y UW
  ya podían borrar etiquetas, así que se usó un usuario temporal (D.0).

### Antes de B

Se comprobó que el repo no tiene commits en los módulos después de `9a2970d`, y que el laboratorio carga
los módulos desde la raíz de `third_party` (las carpetas `_fabricante` van después en `addons_path`).

### B. Despliegue

- **B.4:** todo coincide: 75 marcadores; por parche 2, 5, 7, 3, 4, 6, 1, 23, 4; `seges=20` 1; 709
  archivos, huella `7a6c7144…bb9f`.
- **B.5:** copia en `addons_antes_E2p` con 696 archivos, huella `c12168ea…`.
- **B.6:** el ensayo no listó bajas. Tras la sustitución, 709 archivos, huella `7a6c7144…`; `diff -rq`
  de 30 líneas = 17 distintos + 13 nuevos + 0 bajas.
- **B.7 y B.8 (`-u`):** 0 `Traceback`, `ERROR` y `CRITICAL`; 0 «Deleting field». `WARNING`: etiquetas
  repetidas (`ai.log` «Client» ×2, `ai.trusted.action` «Model»), `skip retired unlink for pns_ai_mcp` y
  dos `DeprecationWarning` de `distutils` del núcleo (`ir_actions_report.py`). El aviso de `jinja2` de
  E1′ no apareció.
- **Arranque:** `web` arrancó a las 10:57:35. Los 3 errores de la primera revisión del log eran el 503
  de A.7, anterior a la parada. `/web/login` 200 y `/mcp` 403.

### C. Comprobaciones posteriores

C.2 igual que A.4; los crons de 5 minutos se ejecutaron a las 11:08 con el código nuevo.

### D. Pruebas

- **D.0:** scripts copiados a `~/staging_e2p`, con sha256 `4a247c5c…` y `47b63259…`. Etiqueta «Seges
  P-37b» id 8; grupo «Seges P-37b» id 43 (leer y escribir en `res.partner.category`); W = usuario
  temporal `e2p_writer`, id 23, con AI Writer. La plantilla por defecto le añadió Manage Product
  Variants, Quotation Templates, Tax display B2B y Technical Features, que no dan borrado de etiquetas.
  Usuario MCP 14. Línea base: 26 `ai_safe_operation`, 12 filas de diario, 657 adjuntos.
- **D.1 (seguridad):** todas OK.
  1. **P-37w/c:** OK; diario intacto (la fila 1 conserva su `write_date` del 16/10).
  2. **P-37b:** OK. Propuesta `UNLK00000001`; al confirmar como `e2p_writer`, error «No puedes borrar…
     res.partner.category» (solo Contact Creation); la etiqueta 8 sigue activa; diario: fila 13 `unlink`
     `failed` (`create_uid` 1); `ai_safe_operation` 32 `cancelled`. Las dos primeras ejecuciones del
     script dieron «Esta clave no ve la herramienta safe_plan_request»: `e2p_writer` no tenía AI
     Conversational (id 15), que `/mcp` exige porque su agente es conversacional. Se añadió desde la
     ficha del usuario (11:43); marcar la casilla en Usuarios MCP y guardar no lo dejó puesto (fallo de
     la casilla, observación para E4′).
  3. **P-19:** OK; la b salió «NO RECHAZADO (… vacío)», ya conocido. **P-101 (3b):** OK.
  4. **P-82:** TODO OK. A2 24, B 25, X 915, CS_B2 48, Z2 916; X (False, 0, 24); A2 200, B 404;
     `--limpiar` borró los dos usuarios (no hizo falta archivarlos).
  5. **P-70, casos 1 a 5:** OK. El caso 5 primero, en el navegador habitual con caché, con
     `?seges=20`; los casos 1 a 4 en ventana privada; sesión antigua 39.
  6. **P-20 A y B:** OK. A: proveedor 3, `temperature` 0.7 → 0.43. B: usuario MCP 2, de U1, etiqueta →
     «P-20b staging». «Will replace» en la pantalla de «Review»; valor y `write_date` sin cambios después
     de «Review» y después de cerrar; el `res.users` de U1 sin cambios.
- **D.2 (no regresión):** conforme.
  - R1 a R4: validadas por Sergio, sin consultas de comprobación. R5: OK.
  - R6: fila 14 `unlink` → `reverted`; fila 15 con `origin` `revert` y `reverts_id` 14; la etiqueta 9
    vuelve.
  - R7: la fila 16 queda en `applied` y la etiqueta 10 se borró definitivamente.
  - Las filas 14 a 16 tienen `create_uid` 2: el `sudo` conserva el uid.
  - R8: 0.43 confirmado y devuelto a 0.7 (12:37).
  - R9: cubierta por los controles P-19 r1/r2 y P-101 r del script (`relaxaicode` normal por `/mcp` como
    ADM).
  - R10: 8 líneas, todas esperadas: un 503 de Gemini (12:13) y los dos `ERROR` de P-37b, cada uno con dos
    `Traceback` encadenados.
- **D.3 (limpieza):** claves MCP de `admin` (usuario MCP 1) y de `e2p_writer` (14) revocadas
  (`not_generated`, sin hash); `e2p_writer` archivado; etiquetas 8 y 9 archivadas; grupo «Seges P-37b»
  borrado (en Odoo 14 los grupos no se pueden archivar); P-82: 0 adjuntos y 0 sesiones.

**Resultado:** E2′ desplegada en `pns_demo` y parches 11 (adaptado) y 17 a 24 **validados en staging**.
P-37b, que en el laboratorio solo cubría el test, queda confirmada a mano.

### Correcciones del procedimiento

Hechas en su sitio, con la nota «(corregido el 29/10/2026)»: B.2 (puerto y destino con `read -rp`), A.8
(consulta de P-37b sin `'<login>'`), D.0 (`mkdir -p` antes del primer `cp`; UW sustituido por el usuario
temporal W, con AI Writer y AI Conversational), D.1 fila 5 (orden de los casos de P-70) y D.3 (W, etiqueta
de R6, grupo y consulta final).

### Observaciones para E4′

Anotadas en el [plan de corrección](plan_correccion_pns_ai_3879.md), «E4′ (hoja de Medios y Bajos)»:
«Test Connection» escribe en `ai_provider`; `pruebas_e2p_lab.py` se identifica como `seges-e2p-lab` también
en el staging; la autenticación MCP no consulta `mcp_api_key_state`; y el fallo de la casilla AI
Conversational de Usuarios MCP (`is_ai_conversational`): Sergio confirma que la marcó y guardó la ficha y
el grupo no cambió; se puso desde la ficha del usuario. Candidata al informe al fabricante.

### Restos para la limpieza final (no se borran ahora)

- **`/tmp` del VPS, de E2′:** `pns_u_E2p.log`, `pns_diff_E2p.txt`, `pns_e2p_diario_antes.txt` y
  `pns_e2p_linea_base.txt`.
- **`/tmp` del VPS, de E1/E1′:** tres `.tar.gz`, `pns_diff_E1p.txt`, `pns_p9_*`, `pns_r4_r6_E1p.log`,
  `pns_u_E1p.log`, `pns_demo_init.log` y `pns_liyben.snip`. **Revisar antes de borrar.**
- **`/opt/odoo/pns_staging/addons_antes_E2p`:** vuelta atrás de E2′ (E, punto 3).
- **`~/staging_e2p` del equipo de Sergio:** las tres salidas del script y `e2p_estado.json`.
- **`~/Descargas`:** los dos JSON exportados de P-20, si siguen ahí.
