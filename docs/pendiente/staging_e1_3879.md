# Subida de E1′ al staging `pns_demo` (cambio de base a 3.1.879)

- **Rama:** `14.0-pns-ai-3879` · **Commit a desplegar:** `0366231` (salvo que Sergio indique otro HEAD;
  entonces hay que recalcular las huellas del §B.1 y del §B.4) · **Preparado:** 26/10/2026 ·
  **Estado:** preparado, sin ejecutar.
- **Origen:** ficha de E1′ y §1 (validación, punto 2) del
  [plan de corrección sobre 3.1.879](plan_correccion_pns_ai_3879.md); plan de prueba del §4 de la
  [propuesta de E1′](e1_propuesta_3879.md); pérdidas de P-9 en la
  [comparación](../specs/comparacion_pns_ai_3-1-879.md), §9.2, §9.5 y §9.6.
- **Procedimiento de referencia:** [plan de staging](plan_staging_pns_ai.md), §2.2 (punto 4) y §7.1; registros
  «Staging — entrega E1» y «Staging — entrega E2» de la
  [verificación](verificacion_seguridad_pns_ai.md).
- **Condiciones del staging que siguen vigentes:** las del plan de staging, §1 (datos de demostración,
  sin mesa de PIN, `whitelist_only`). Sin copia de `pns_demo` (N9; aprobado para esta subida el
  23/10/2026).
- **Sin secretos en este documento:** ni contraseñas, ni claves, ni el contenido de `.env`. Las claves de
  los proveedores solo las introduce Sergio, en la interfaz.

**Convenciones de los comandos.** **[LECTURA]**: solo lee. **[ALTERA]**: cambia algo; va precedido de
un aviso de qué cambia. Las consultas SQL van con `psql` dentro del contenedor de PostgreSQL y, si son
de lectura, dentro de `BEGIN TRANSACTION READ ONLY … ROLLBACK`. Contenedores: `odoo14_pns_db` para
`pns_demo` y `odoo14_db` para LIYBEN. Lo que no está confirmado en los documentos se marca
**«Sin confirmar»** y se dice cómo comprobarlo.

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

**`git archive` de los tres módulos a `/opt/odoo/pns_staging/addons`**, el mismo de todas las subidas a
`pns_demo` (instalación del 15/10, parches 5 y 6 del 16/10, E1 del 20/10 y E2 del 21/10):

- El plan de staging (§2.2, puntos 1 y 4, y §7.1) y los registros de E1 y E2 de la verificación lo dicen
  expresamente: `git archive` desde el equipo de Sergio, huella SHA-256 comparada en el VPS, `diff -rq`
  con el despliegue anterior, copia previa en `addons_antes_EN` y sustitución con `rsync` como el usuario
  `ubuntu` (1000, dueño de `addons`).
- **Comprobado el 26/10/2026 en el equipo, sin tocar la copia de trabajo:**
  `git archive --format=tar.gz <commit> pns_base pns_ai_mcp pns_ai_chatboo` (sin prefijo) reproduce las
  huellas anotadas de E1 (`2bb4f51` → `348c0fd8…`) y de E2 (`792481c` → `3ee9623d…`). Es la orden exacta
  que se usó.
- **El clon de `third_party` (instalación en LIYBEN, §3.2: git como UID 101, refspec explícito, checkout
  sin `--track`) es el método de LIYBEN** (`odoo14_server`, `/opt/odoo/addons/custom/third_party`). No
  sirve para `pns_demo`, que no monta ningún clon.
- **Incoherencia documental:** la spec de E1 (`docs/specs/correcciones_pns_ai_entrega1.md`, §9.3, punto
  1) decía «Clon del VPS en el commit de Sergio», pero lo ejecutado y registrado fue `git archive`
  (verificación, «Staging — entrega E1»). Manda lo registrado. La comprobación A.3 confirma en el VPS
  que lo montado coincide con el archivo de `792481c`.

**Diferencia con E1 y E2:**
- **`-u` de los tres módulos.** E1 y E2 solo cambiaban Python y bastaba con reiniciar. Aquí cambia la
  versión y el esquema (U5, U6, U9, U12, U16, U17 de la comparación).
- **`rsync` con `--delete`, módulo a módulo.** De `792481c` a `0366231` desaparecen 6 archivos (§B.5). En
  E1 y E2 no desaparecía ninguno y los registros no dicen si se usó `--delete`.
- **Odoo se para antes de sustituir el código.** En E1 y E2 se sustituía en caliente y después se
  reiniciaba.

---

## A. Comprobaciones previas (solo lectura)

Desde el VPS, con el usuario `ubuntu` salvo que se indique otro. `ubuntu` usa `docker` sin `sudo`
(comprobado por Sergio en el VPS el 26/10/2026).

### A.1 Contenedores y usuario de PostgreSQL

**[LECTURA]** Comprueba los nombres de los contenedores y el usuario de PostgreSQL (solo imprime la
variable del usuario, nunca la contraseña):

```bash
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}' | grep -E 'odoo14_pns|odoo14_db|odoo14_server'
docker exec odoo14_pns_db printenv POSTGRES_USER
docker exec odoo14_db printenv POSTGRES_USER
```

Esperado: `odoo14_pns` (imagen `odoo-web`) y `odoo14_pns_db` (`postgres:15-alpine`) en marcha; los dos
`POSTGRES_USER` = `odoo` (comprobado por Sergio en el VPS el 26/10/2026, en `odoo14_pns_db` y en
`odoo14_db`). Si saliera otro, alguien ha cambiado los contenedores: parar y averiguarlo antes de
seguir.

### A.2 Cómo está montado el código

**[LECTURA]** Montajes de `odoo14_pns` (no muestra variables de entorno), carpetas del proyecto,
propietario y espacio libre:

```bash
docker inspect odoo14_pns --format '{{range .Mounts}}{{.Type}}  {{.Source}} -> {{.Destination}}  rw={{.RW}}{{"\n"}}{{end}}'
cd /opt/odoo/pns_staging && ls -la && ls -la addons
stat -c '%U %u %a %n' addons addons/*
df -h /opt/odoo /tmp
```

Esperado (plan de staging, §2; montajes comprobados por Sergio en el VPS el 26/10/2026):

| Origen en el host | Destino en `odoo14_pns` | Modo |
|---|---|---|
| `/opt/odoo/pns_staging/addons` | `/mnt/extra-addons/pns` | `ro` |
| `/opt/odoo/pns_staging/config` | `/etc/odoo` | `ro` |
| `/opt/odoo/odoo-core/odoo` y `/opt/odoo/odoo-core/addons` (código de Odoo) | los que muestre `docker inspect` | `ro` |
| volumen `pns_staging_odoo-data` | `/var/lib/odoo` | `rw` |

Dentro de `addons`, solo `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo`, de `ubuntu` (1000);
`addons_antes_E1` y `addons_antes_E2` presentes (se conservan hasta la limpieza final); unos 100 MB
libres como mínimo.

**[LECTURA]** Ajustes de `odoo.conf` que importan aquí, sin `admin_passwd`. El archivo está en el host,
en `/opt/odoo/pns_staging/config/odoo.conf` (montado como `/etc/odoo/odoo.conf`):

```bash
grep -E '^[[:space:]]*(addons_path|dbfilter|logfile|data_dir|workers|max_cron_threads)[[:space:]]*=' /opt/odoo/pns_staging/config/odoo.conf
```

Esperado:
- comprobado por Sergio el 26/10/2026:
  `addons_path = /usr/lib/python3/dist-packages/odoo/addons,/mnt/core-addons,/mnt/extra-addons/pns`,
  `data_dir = /var/lib/odoo` y **ninguna línea `logfile`**: el log del `-u` y del arranque sale por la
  salida estándar (B.7 y B.8);
- según el plan de staging (§2.3): `dbfilter = ^pns_demo$`, `workers = 2`, `max_cron_threads = 1`.

### A.3 Qué código hay montado (huella)

Con `git archive` no hay commit en el VPS: se compara una huella del árbol (SHA-256 de cada archivo, en
orden fijo). Calculada el 26/10/2026 en el equipo sobre los archivos de cada commit:

| Commit | Archivos | Huella del árbol |
|---|---|---|
| `792481c` (E2, lo que debería estar montado) | 634 | `5dccc29a5481cad8337441140c6380b3bc458941051e61f6c1db76aa00de3033` |
| `0366231` (E1′, lo que se va a montar) | 696 | `c12168eac19014c6ab51135cac239e8a8f0d85b2423d4b9f7a09ee1d2a2b6160` |

**[LECTURA]**

```bash
cd /opt/odoo/pns_staging/addons
find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l
find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum
```

Esperado: 634 y `5dccc29a…`. **Si no coincide, parar:** alguien ha cambiado el código desde E2, y el
`diff -rq` de B.6 y la vuelta atrás (E) ya no partirían de lo que se cree.

### A.4 Estado de `pns_demo`: módulos, neutralización, crons y actividad

**[LECTURA]**

```bash
docker exec -i odoo14_pns_db psql -U odoo -d pns_demo -v ON_ERROR_STOP=1 <<'SQL'
BEGIN TRANSACTION READ ONLY;
-- Versiones y módulos de autenticación (para parche 16)
SELECT name, state, latest_version FROM ir_module_module
 WHERE name LIKE 'pns_%' OR name IN ('auth_oauth', 'auth_ldap', 'auth_totp') ORDER BY name;
-- Marca de neutralización del kit (no debería existir: pns_demo no es una copia cargada con el kit)
SELECT key, value FROM ir_config_parameter WHERE key LIKE 'odoo_dev.%';
-- Crons de los pns_*
SELECT d.module || '.' || d.name AS xml_id, c.active, c.numbercall, c.interval_number,
       c.interval_type, c.nextcall, c.user_id
  FROM ir_cron c JOIN ir_model_data d ON d.model = 'ir.cron' AND d.res_id = c.id
 WHERE d.module LIKE 'pns_%' ORDER BY 1;
SELECT count(*) FILTER (WHERE active) AS crons_activos, count(*) AS crons FROM ir_cron;
SELECT id, name, active FROM ir_mail_server ORDER BY id;
-- Actividad en curso (antes de parar)
SELECT pid, state, xact_start, wait_event_type, left(query, 80) AS query
  FROM pg_stat_activity WHERE datname = 'pns_demo' AND state <> 'idle' ORDER BY xact_start;
ROLLBACK;
SQL
```

Esperado:
- `pns_base` 14.0.1.2.32, `pns_ai_mcp` 14.0.3.1.782 y `pns_ai_chatboo` 14.0.2.1.453, `installed` (los
  parches no cambian `version`). `auth_oauth` y `auth_ldap` no instalados (si lo estuvieran, ver A.6).
- Sin filas `odoo_dev.%`: el staging **no está neutralizado** y no lo estará tras el `-u`; los crons se
  quedan como estén.
- Seis crons de `pns_*`, activos, `numbercall` -1 (como en LIYBEN, instalación §3.4). Todavía sin
  `pns_ai_mcp.ir_cron_ai_journal_trash` (llega con el `-u`, U12).
- Ninguna transacción de `pns_demo` en curso, o solo `idle`.

### A.5 Fotografía de P-9 antes del `-u` (P-9a, P-9b y P-9e)

Las consultas de la comparación (§9.5), como en la fase 3 (`fase3_lab_pns_ai_3879.md`, parte 3), pero
sobre `pns_demo` real. **[LECTURA]** La salida se guarda en `/tmp` del VPS para compararla después (no
contiene secretos: solo nombres de columna, claves de parámetros, cinco valores de presentación y
recuentos):

```bash
docker exec -i odoo14_pns_db psql -U odoo -d pns_demo -v ON_ERROR_STOP=1 <<'SQL' | tee /tmp/pns_p9_antes_E1p.txt
BEGIN TRANSACTION READ ONLY;
-- P-9a: columnas de las cuatro tablas
SELECT table_name, count(*) AS columnas FROM information_schema.columns
 WHERE table_schema = 'public'
   AND table_name IN ('ai_log', 'ai_mcp_user', 'chatboo_session', 'chatboo_async_request')
 GROUP BY table_name ORDER BY table_name;
SELECT table_name, column_name FROM information_schema.columns
 WHERE table_schema = 'public'
   AND ((table_name = 'ai_mcp_user' AND column_name LIKE 'key_pin%')
     OR (table_name = 'ai_log' AND column_name IN ('agent_id', 'provider_id', 'client_display'))
     OR (table_name = 'chatboo_session' AND column_name LIKE 'canvas_%'))
 ORDER BY 1, 2;
-- P-9a: parámetros (nombres) y valores de los cinco que se renombran (U6)
SELECT key FROM ir_config_parameter WHERE key LIKE 'pns_ai%' ORDER BY key;
SELECT key, value FROM ir_config_parameter
 WHERE key ~ '^pns_ai(_chatboo)?\.(chart_engine|default_show_?mode|xlsx_float_decimals|xlsx_thousands|download_max_bytes)$'
 ORDER BY key;
SELECT module, name FROM ir_model_data
 WHERE model = 'ir.config_parameter' AND module LIKE 'pns_ai%' ORDER BY 1, 2;
SELECT count(*) AS xmlid_mcp FROM ir_model_data WHERE module = 'pns_ai_mcp' AND name LIKE 'mcp\_%';
-- P-9a: recuentos por origin y totales
SELECT 'ai_log' AS tabla, origin, count(*) FROM ai_log GROUP BY origin
UNION ALL
SELECT 'ai_change_journal', origin, count(*) FROM ai_change_journal GROUP BY origin
 ORDER BY 1, 2;
SELECT (SELECT count(*) FROM ai_log) AS ai_log, (SELECT count(*) FROM ai_change_journal) AS diario,
       (SELECT count(*) FROM chatboo_session) AS sesiones,
       (SELECT count(*) FROM chatboo_async_request) AS jobs,
       (SELECT count(*) FROM ai_context) AS contextos, (SELECT count(*) FROM ai_skill) AS skills;
-- P-9b: filas con agente (la columna desaparece con el -u, U9)
SELECT count(*) AS ai_log_con_agente FROM ai_log WHERE agent_id IS NOT NULL;
-- P-9e: sesiones con marcas antiguas (U16)
SELECT count(*) AS sesiones_marcas_antiguas FROM chatboo_session
 WHERE messages LIKE '%o_chatboo_%' OR messages LIKE '%data-chatboo-%';
ROLLBACK;
SQL
```

Referencia (la copia `pns_demo_p9` del 22/10, comparación §9.6): `ai_mcp_user` con las tres `key_pin*`;
`chatboo_async_request` 25 columnas; `ai_log` por `origin` `chatboo` 950, `internal` 25, `mcp_client`
12; 978 filas con agente; 10 sesiones con marcas antiguas. **Lo que cuenta no es la referencia, sino
que antes y después coincidan** (C.1); `pns_demo` ha podido cambiar desde el 22/10 (purga de `ai_log`,
turnos nuevos).

**Pérdida aceptada (plan de corrección §1; N9):** el agente de esas filas de `ai_log` (U9). No se guarda
aparte.

### A.6 AI Administrators y contraseña local (parche 16)

`check_identity` valida la contraseña local (`_check_credentials`): quien entre sin ella (OAuth, LDAP) no
podría confirmar en Autorizaciones. **[LECTURA]** Solo devuelve si hay contraseña, no el hash:

```bash
docker exec -i odoo14_pns_db psql -U odoo -d pns_demo -v ON_ERROR_STOP=1 <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT u.id, u.login, u.active, u.share,
       (u.password IS NOT NULL AND u.password <> '') AS contrasena_local,
       EXISTS (SELECT 1 FROM res_groups_users_rel r2
                 JOIN ir_model_data d2 ON d2.model = 'res.groups' AND d2.res_id = r2.gid
                WHERE r2.uid = u.id AND d2.module = 'base' AND d2.name = 'group_system') AS ajustes
  FROM res_users u
  JOIN res_groups_users_rel r ON r.uid = u.id
  JOIN ir_model_data d ON d.model = 'res.groups' AND d.res_id = r.gid
                      AND d.module = 'pns_ai_mcp' AND d.name = 'group_ai_admin'
 ORDER BY u.id;
ROLLBACK;
SQL
```

Esperado en `pns_demo`: `admin` (ADM, id 2) activo, con contraseña local y Ajustes; `e2_aiadmin` (id 17)
inactivo (archivado en la limpieza de E2). Si A.4 mostró `auth_oauth` instalado, ejecutar además
`SELECT id, login FROM res_users WHERE oauth_uid IS NOT NULL;` en un bloque igual (la columna solo
existe con ese módulo).

**LIYBEN:** hecho el 26/10/2026 (consulta de solo lectura en `odoo14_db`): `fran.odoo@seges.es` y
`sguerrero@liyben.com` activos y con contraseña local. Pendiente: que ambos confirmen que la conocen
([parches](parches_pns_ai.md), parche 16).

### A.7 Proveedor del staging

**[LECTURA]** Proveedores y cadena del agente, sin leer `api_key`:

```bash
docker exec -i odoo14_pns_db psql -U odoo -d pns_demo -v ON_ERROR_STOP=1 <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT id, name, active, protocol, model_name, endpoint FROM ai_provider ORDER BY id;
SELECT a.code AS agente, ap.priority, ap.active, p.name AS proveedor, p.active AS proveedor_activo
  FROM ai_agent_provider ap
  JOIN ai_agent a ON a.id = ap.agent_id
  JOIN ai_provider p ON p.id = ap.provider_id
 ORDER BY a.code, ap.priority, ap.id;
ROLLBACK;
SQL
```

Después, en la interfaz y **solo Sergio** (AI Engine → Providers):
1. **Gemini:** «Test Connection» correcto y cuota disponible en la consola de Google AI Studio. El nivel
   gratuito da 20 peticiones al día por modelo (plan de staging §7.2): las pruebas de D con LLM son
   pocas, pero conviene hacerlas el mismo día que se comprueba la cuota.
2. **Si Gemini no tiene cuota:** OVH con **Qwen3.5-397B-A17B** como auxiliar (decisión del 23/10/2026,
   [decisiones](pns_ai_decisiones.md), bloque de N12; **no** Qwen3.5-9B, que inventa datos). Referencia
   del laboratorio (`fase3_lab_pns_ai_3879.md`): protocolo `openai`, endpoint
   `https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions`, Conversation + Vision; se añade a
   la cadena de Chatboo **después** de Gemini. La clave la pega Sergio.
3. Anotar qué proveedor queda operativo: ______________________

---

## B. Despliegue y `-u`

Orden: preparar el archivo (B.1-B.4, sin tocar `pns_demo`), copia del código actual (B.5), parar Odoo
(B.6), sustituir el código (B.6), `-u` (B.7), revisar el log y arrancar (B.8).

### B.1 En el equipo de Sergio: archivo del commit

**[LECTURA del repo]** No cambia la copia de trabajo (`git archive` lee el commit). Crea un archivo en
`/tmp` del equipo:

```bash
cd ~/GitHub/third_party
git cat-file -t 0366231
git archive --format=tar.gz -o /tmp/pns_addons_0366231.tar.gz 0366231 pns_base pns_ai_mcp pns_ai_chatboo
sha256sum /tmp/pns_addons_0366231.tar.gz
```

Esperado: `commit` y `4a0aba606cc022997e9c224abe66b4c6c0ec2808470baaacc5f3536740cddd90` (calculada el
26/10/2026 con git 2.43.0, la misma orden que reproduce las huellas de E1 y E2). Si se despliega otro
commit, se sustituye en las tres órdenes y la huella será otra: se anota la que salga.

### B.2 Copia al VPS

Método de E1′: `scp` desde el equipo de Sergio a `/tmp/` del VPS (cómo se copió en E1 y E2 no consta:
ver F). `<destino_ssh>` es lo mismo que Sergio usa para entrar por `ssh`: el alias de `~/.ssh/config`
o `ubuntu@<IP>`.

**[LECTURA]** En el equipo de Sergio, para localizar el alias:

```bash
grep -iE '^\s*(Host|HostName|User)\s' ~/.ssh/config
```

**[ALTERA solo `/tmp` del VPS]** Copia del archivo:

```bash
scp /tmp/pns_addons_0366231.tar.gz <destino_ssh>:/tmp/
```

La comprobación de que llega íntegro es la huella de B.3.

### B.3 En el VPS: huella y extracción en una carpeta temporal

**[LECTURA]** Huella del archivo recibido (debe ser la de B.1):

```bash
sha256sum /tmp/pns_addons_0366231.tar.gz
```

**[ALTERA solo `/tmp`]** Crea `/tmp/pns_addons_E1p` (borra la carpeta si existía) y extrae allí:

```bash
rm -rf /tmp/pns_addons_E1p && mkdir /tmp/pns_addons_E1p && tar -xzf /tmp/pns_addons_0366231.tar.gz -C /tmp/pns_addons_E1p
```

### B.4 Comprobaciones del código extraído (plan de staging §2.2, puntos 2 y 3)

**[LECTURA]**

```bash
cd /tmp/pns_addons_E1p
grep -n "'version'" pns_base/__manifest__.py pns_ai_mcp/__manifest__.py pns_ai_chatboo/__manifest__.py
grep -rn "Seges: parche" pns_base pns_ai_mcp pns_ai_chatboo --include=*.py | grep -v '/tests/' | wc -l
grep -rn "Seges: parche de compatibilidad" pns_base pns_ai_mcp pns_ai_chatboo | wc -l
grep -nE "def _?collect_pin\b" pns_ai_mcp/models/key_pin_desk.py
grep -nE "group_system" pns_ai_mcp/models/ai_system_action.py pns_ai_mcp/utils/privilege_cusp.py | wc -l
grep -nE "def create\b|def _?cleanup_stuck_state\b" pns_ai_mcp/models/safe_operation.py
grep -nE "def _?unlink_retired_from_module\b" pns_ai_mcp/models/ai_context_disk.py
grep -c "fulfill_client_export" pns_ai_mcp/controllers/validators_base.py
grep -nE "check_identity|def action_confirm_and_execute|mint_token and" pns_ai_mcp/models/safe_operation.py
find pns_base pns_ai_mcp pns_ai_chatboo -type f | wc -l
find pns_base pns_ai_mcp pns_ai_chatboo -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum
```

Esperado (comprobado en el equipo el 26/10/2026 sobre el archivo de `0366231`):

| Comprobación | Esperado |
|---|---|
| Versiones | `1.2.47`, `3.1.879`, `2.1.538` |
| Marcadores «Seges: parche» fuera de tests | 20 (parches 10 y 12 a 16; [parches](parches_pns_ai.md), E1′) |
| «Seges: parche de compatibilidad» | 0 (parches 1 a 9 retirados en esta rama) |
| Parche 10 | `def _collect_pin(self, pin):` |
| Parche 12 | 2 líneas |
| Parche 13 | `def create(self, vals_list):` y `def _cleanup_stuck_state(…)` |
| Parche 14 | `def _unlink_retired_from_module(…)` |
| Parche 15 | 1 |
| Parche 16 | el `import` de `check_identity`, `@check_identity` sobre `action_confirm_and_execute` y `if mint_token and self.user_id == self.env.user:` |
| Archivos / huella del árbol | 696 / `c12168ea…6160` (A.3) |

Si algo no coincide, **no seguir**.

### B.5 Copia del código actual

**[ALTERA]** Crea `/opt/odoo/pns_staging/addons_antes_E1p` con el código de `792481c`, para la vuelta atrás
del código (E). Antes, comprobar que no existe:

```bash
cd /opt/odoo/pns_staging && test ! -e addons_antes_E1p && cp -a addons addons_antes_E1p && ls -d addons_antes_*
```

### B.6 Parar Odoo y sustituir el código

**[ALTERA]** Para el servicio `web` (contenedor `odoo14_pns`) del proyecto `pns_staging`. `pns_demo` deja
de responder en `https://pns.liyben.com` hasta B.8. PostgreSQL (`odoo14_pns_db`) sigue en marcha:

```bash
cd /opt/odoo/pns_staging && docker compose stop web && docker compose ps
```

**[LECTURA]** Ensayo del `rsync` (no cambia nada). Debe listar exactamente estas 6 bajas:

```bash
for m in pns_base pns_ai_mcp pns_ai_chatboo; do rsync -ani --delete /tmp/pns_addons_E1p/$m/ /opt/odoo/pns_staging/addons/$m/ | grep '^\*deleting'; done
```

```
*deleting   data/chatboo_icp_data.xml                    (pns_ai_chatboo, U19)
*deleting   static/src/js/showdown.js                    (pns_ai_chatboo)
*deleting   controllers/moe_controller.py                (pns_ai_mcp)
*deleting   lib/llm/drivers/ollama_driver.py             (pns_ai_mcp)
*deleting   tests/test_chatboo_pending_cards.py          (pns_ai_mcp)
*deleting   views/mcp_field_widgets.xml                  (pns_ai_mcp)
```

**[ALTERA]** Sustitución, módulo a módulo, como `ubuntu` y sin `sudo` (como E2). El `--delete` solo
actúa dentro de cada módulo:

```bash
for m in pns_base pns_ai_mcp pns_ai_chatboo; do rsync -a --delete /tmp/pns_addons_E1p/$m/ /opt/odoo/pns_staging/addons/$m/; done
```

**[LECTURA]** Verificación (huella como en A.3; `diff -rq` con la copia):

```bash
cd /opt/odoo/pns_staging/addons
find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l
find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum
cd /opt/odoo/pns_staging && LC_ALL=C diff -rq addons_antes_E1p addons > /tmp/pns_diff_E1p.txt; wc -l < /tmp/pns_diff_E1p.txt
grep -c '^Files ' /tmp/pns_diff_E1p.txt; grep -c '^Only in addons/' /tmp/pns_diff_E1p.txt; grep '^Only in addons_antes_E1p' /tmp/pns_diff_E1p.txt
```

Esperado: 696 archivos y huella `c12168ea…6160`; `diff -rq`: 268 líneas = 195 archivos distintos, 67
entradas solo en `addons` (archivos y carpetas nuevos de 3.1.879 y de los tests de Seges) y las 6 bajas
de arriba (calculado en el equipo entre `792481c` y `0366231`). A diferencia de E1 y E2, aquí el `diff`
es grande porque cambia la base; la comprobación fuerte es la huella.

### B.7 `-u` de los tres módulos

Desde `/opt/odoo/pns_staging`, con `docker compose run --rm` (plan de staging, §7.1: `run` pasa por el
entrypoint, que añade la conexión a PostgreSQL; `exec` no). `-T` porque la salida va a un archivo.

**[ALTERA `pns_demo`, sin copia (N9)]** Actualiza la base de datos a 3.1.879: borra `ai_log.agent_id` y
las columnas `key_pin*`, renombra cinco parámetros, reescribe el historial de Chatboo, crea el cron de
la papelera (activo) y resiembra contextos y skills de fábrica (comparación §9.2, U5 a U21). **No se
puede deshacer** (ver E):

```bash
cd /opt/odoo/pns_staging && docker compose run --rm -T web odoo -u pns_base,pns_ai_mcp,pns_ai_chatboo -d pns_demo --stop-after-init 2>&1 | tee /tmp/pns_u_E1p.log
```

`odoo.conf` no tiene `logfile` (A.2): todo el log del `-u` queda en `/tmp/pns_u_E1p.log`.

### B.8 Revisar el log y arrancar

**[LECTURA]**

```bash
L=/tmp/pns_u_E1p.log
grep -cE 'Traceback|ERROR|CRITICAL' $L
grep 'Deleting field' $L
grep -c 'DROP leftover' $L
grep -E 'No module named|module .* not (found|installable)' $L
grep 'WARNING' $L | sed 's/.* WARNING [^ ]* //' | sort | uniq -c
grep -E 'Modules loaded|Registry loaded' $L | tail -2
```

Esperado (fase 3, `pns_demo_p9`, 22/10):
- **0** `Traceback`, `ERROR` y `CRITICAL`; ningún módulo que no se importe.
- **7 «Deleting field»**, entre ellos **`Deleting field ai.log.agent_id`** (U9); los demás:
  `ai.mcp.user.key_pin`, `key_pin_used`, `key_pin_killed` (U5), `ai.skill.capture.wizard.from_chatboo`
  (U17 bis), `ai.log.agent_display` y `ai.mcp.user.key_pin_html` (calculados).
- **11** `DROP leftover` (`DROP TABLE IF EXISTS` de tablas que no existen).
- Unos 6 `WARNING`: `jinja2`, etiquetas repetidas y, dos veces, `skip retired unlink for pns_ai_mcp`.

**Si hay `Traceback`, `ERROR` o `CRITICAL`: no arrancar** y decidir con el apartado E.

**[ALTERA]** Arranca `odoo14_pns` con el código nuevo:

```bash
cd /opt/odoo/pns_staging && docker compose start web && docker compose ps
```

**[LECTURA]** Tras uno o dos minutos (sin `logfile`, el log del servidor está en `docker compose logs`):

```bash
cd /opt/odoo/pns_staging && docker compose logs --since 10m web 2>&1 | grep -cE 'Traceback|ERROR|CRITICAL'
curl -sS -o /dev/null -w '%{http_code}\n' https://pns.liyben.com/web/login
curl -sS -o /dev/null -w '%{http_code}\n' https://pns.liyben.com/mcp
```

Esperado: 0; `200`; `403` (`GET /mcp` rechazado por Nginx, plan §2.3).

**[ALTERA solo `/tmp`]** Borrar los temporales del despliegue en el VPS
(`/tmp/pns_addons_0366231.tar.gz`, `/tmp/pns_addons_E1p`); el log y las fotografías de P-9 se conservan
hasta anotar los resultados.

---

## C. Comprobaciones posteriores

### C.1 P-9a, P-9b y P-9e después

**[LECTURA]** El mismo bloque de A.5 **sin la consulta de P-9b** (la de `agent_id` daría error y
`ON_ERROR_STOP` cortaría el resto), con la salida en `/tmp/pns_p9_despues_E1p.txt`:

```bash
docker exec -i odoo14_pns_db psql -U odoo -d pns_demo -v ON_ERROR_STOP=1 <<'SQL' | tee /tmp/pns_p9_despues_E1p.txt
BEGIN TRANSACTION READ ONLY;
-- P-9a: columnas de las cuatro tablas
SELECT table_name, count(*) AS columnas FROM information_schema.columns
 WHERE table_schema = 'public'
   AND table_name IN ('ai_log', 'ai_mcp_user', 'chatboo_session', 'chatboo_async_request')
 GROUP BY table_name ORDER BY table_name;
SELECT table_name, column_name FROM information_schema.columns
 WHERE table_schema = 'public'
   AND ((table_name = 'ai_mcp_user' AND column_name LIKE 'key_pin%')
     OR (table_name = 'ai_log' AND column_name IN ('agent_id', 'provider_id', 'client_display'))
     OR (table_name = 'chatboo_session' AND column_name LIKE 'canvas_%'))
 ORDER BY 1, 2;
-- P-9a: parámetros (nombres) y valores de los cinco que se renombran (U6)
SELECT key FROM ir_config_parameter WHERE key LIKE 'pns_ai%' ORDER BY key;
SELECT key, value FROM ir_config_parameter
 WHERE key ~ '^pns_ai(_chatboo)?\.(chart_engine|default_show_?mode|xlsx_float_decimals|xlsx_thousands|download_max_bytes)$'
 ORDER BY key;
SELECT module, name FROM ir_model_data
 WHERE model = 'ir.config_parameter' AND module LIKE 'pns_ai%' ORDER BY 1, 2;
SELECT count(*) AS xmlid_mcp FROM ir_model_data WHERE module = 'pns_ai_mcp' AND name LIKE 'mcp\_%';
-- P-9a: recuentos por origin y totales
SELECT 'ai_log' AS tabla, origin, count(*) FROM ai_log GROUP BY origin
UNION ALL
SELECT 'ai_change_journal', origin, count(*) FROM ai_change_journal GROUP BY origin
 ORDER BY 1, 2;
SELECT (SELECT count(*) FROM ai_log) AS ai_log, (SELECT count(*) FROM ai_change_journal) AS diario,
       (SELECT count(*) FROM chatboo_session) AS sesiones,
       (SELECT count(*) FROM chatboo_async_request) AS jobs,
       (SELECT count(*) FROM ai_context) AS contextos, (SELECT count(*) FROM ai_skill) AS skills;
-- P-9e: sesiones con marcas antiguas (U16)
SELECT count(*) AS sesiones_marcas_antiguas FROM chatboo_session
 WHERE messages LIKE '%o_chatboo_%' OR messages LIKE '%data-chatboo-%';
ROLLBACK;
SQL
```

**[LECTURA]** Comparación (además de las diferencias esperadas de abajo, sale el bloque de P-9b, que
solo está en la fotografía de antes):

```bash
diff /tmp/pns_p9_antes_E1p.txt /tmp/pns_p9_despues_E1p.txt
```

Esperado (comparación §9.6):
- `ai_mcp_user` sin `key_pin*` (U5); `chatboo_async_request` con las mismas columnas (U17); `ai_log`
  sin `agent_id` y con `provider_id` y `client_display` (U13); `chatboo_session` con las cinco
  `canvas_*` nuevas (U17).
- Los cinco parámetros pasan a `pns_ai.*` **con el mismo valor**; nuevos `pns_ai_admin`,
  `pns_ai_chatboo` y `<agente>.fossil_acl_security_agent` (U7); de los XML ID de parámetros solo queda
  `icp_chatboo_history_retention_days` (U19).
- `xmlid_mcp` = 0 (U3).
- **Mismos recuentos por `origin`** en `ai_log` y en el diario, y mismos totales de `ai_log`, diario,
  sesiones y jobs. Crecen `ai_context` (+3) y `ai_skill` (+3) (U15).
- **P-9b:** la columna `agent_id` ya no aparece en la consulta de columnas (U9).
- **P-9e:** `sesiones_marcas_antiguas` = 0 (U16).

| Comprobación | Esperado | Obtenido |
|---|---|---|
| P-9a | Como arriba | [ ] ____ |
| P-9b | `agent_id` fuera; se pierde el agente de ___ filas (A.5) | [ ] ____ |
| P-9e | ___ (A.5) → 0 | [ ] ____ |

### C.2 P-9f y cron de la papelera (U12)

**[LECTURA]**

```bash
docker exec -i odoo14_pns_db psql -U odoo -d pns_demo -v ON_ERROR_STOP=1 <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT name, state, latest_version FROM ir_module_module WHERE name LIKE 'pns_%' ORDER BY name;
SELECT d.module || '.' || d.name AS xml_id, c.active, c.numbercall, c.interval_number,
       c.interval_type, c.nextcall, c.user_id
  FROM ir_cron c JOIN ir_model_data d ON d.model = 'ir.cron' AND d.res_id = c.id
 WHERE d.module LIKE 'pns_%' ORDER BY 1;
SELECT key, value FROM ir_config_parameter WHERE key LIKE 'odoo_dev.%';
ROLLBACK;
SQL
```

| Comprobación | Esperado | Obtenido |
|---|---|---|
| P-9f | `pns_base` 14.0.1.2.47, `pns_ai_mcp` 14.0.3.1.879, `pns_ai_chatboo` 14.0.2.1.538, `installed`. (`odoo-dev paridad` no existe en el VPS: lo cubre B.8, sin módulos que no se importen) | [ ] ____ |
| Cron de la papelera | `pns_ai_mcp.ir_cron_ai_journal_trash` **activo**, diario, `numbercall` -1; anotar `user_id` (sin `user_id` en el XML: corre con el usuario por defecto, PNS-37, E2′) | [ ] ____ |
| Resto de crons | Los seis de A.4, sin cambios | [ ] ____ |
| Neutralización | Ninguna fila `odoo_dev.%` (el staging no se neutraliza; el cron nuevo se queda activo, como quedará en LIYBEN) | [ ] ____ |

### C.3 Recargar `es_ES` (obligatorio, antes de D)

Decisión de Sergio (26/10/2026): se recarga `es_ES` después del `-u` y **antes de las pruebas de D**,
igual que se hará en LIYBEN al final (plan de corrección §3), para que R2 y el resto de D prueben lo
mismo que verá LIYBEN. Odoo 14 no reescribe en el `-u` las traducciones ya cargadas (U21).

**[ALTERA `pns_demo`]** Vuelve a cargar las traducciones al español de **todos los módulos instalados**
(no solo los `pns_*`) y **sobrescribe los términos existentes**: el asistente lleva marcado
«Sobrescribir términos existentes» por defecto (Odoo 14, `base.language.install`; la casilla solo se ve
en modo desarrollador), así que cualquier traducción retocada a mano en `pns_demo` vuelve a la oficial
del módulo (no consta ninguna). No toca datos de negocio ni el código. Solo Sergio, en la interfaz,
como `admin` (etiquetas en inglés, las del código de Odoo 14; en español pueden variar):

1. Ajustes → Traducciones → Idiomas.
2. En la fila de `es_ES` («Spanish / Español»), botón «Activate / Update» (icono de recarga) y, en el
   asistente «Load a Translation», «Add».
3. Esperar a que el asistente diga que el idioma se ha instalado (no cerrar la pestaña antes) y
   comprobar en el log que no hay errores:

```bash
cd /opt/odoo/pns_staging && docker compose logs --since 15m web 2>&1 | grep -cE 'Traceback|ERROR|CRITICAL'
```

| Comprobación | Esperado | Obtenido |
|---|---|---|
| Recarga de `es_ES` | El asistente termina («… has been successfully installed»); 0 errores en el log | [ ] ____ |

---

## D. Pruebas de seguridad y de no regresión de E1′

En el orden del §4 de la [propuesta](e1_propuesta_3879.md). Las definiciones completas de cada prueba
están en la [comparación](../specs/comparacion_pns_ai_3-1-879.md) (§3, §4.3 y §8.7) y en
[parches](parches_pns_ai.md); aquí, quién, qué se hace y qué se espera.

### D.0 Preparación

**Antes de empezar D, C.3 (recarga de `es_ES`) tiene que estar hecho.**

**[ALTERA `pns_demo`]** Usuarios y datos de prueba. Crearlos y borrarlos lo autoriza Sergio, como en E1
(D-5) y E2 (D-9). Como entonces, por RPC como `admin` con scripts de solo biblioteca estándar y
contraseñas con `read -s` o `getpass`, sin guardarlas. Los scripts no van en este documento.

**Cómo se gestionaron los scripts en E1 y E2.** Los registros de la verificación los nombran, pero no
dicen dónde estaban ni desde dónde se lanzaron; lo que sigue sale de los propios archivos (comprobado
el 26/10/2026 en el equipo de Sergio):
- **Dónde:** en el equipo de Sergio, fuera de cualquier repo y sin subirse al VPS. E1
  (`preparar_e1.py`, `pruebas_e1_rpc.py`, `pruebas_e1_mcp.py`) en `~/Descargas`; E2 (`preparar_e2.py`,
  `pruebas_e2_rpc.py`, `pruebas_e2_mcp.py`, `prueba4_bis_e2.py`) en `~/staging_e2`, junto con
  `e2_estado.json` (solo ids de los datos de prueba, sin secretos), que `preparar_e2.py` escribe en la
  carpeta actual y leen los demás.
- **Quién y desde dónde:** Sergio, desde su equipo, contra `https://pns.liyben.com` (URL por defecto
  de los scripts): JSON-RPC (`/web/session/authenticate`, `/web/dataset/call_kw`, `/jsonrpc`) y `/mcp`
  por HTTPS. Contraseñas y claves MCP en variables de entorno (`E1_*`, `E2_*`) cargadas con `read -s`.
  Las claves MCP las generaba Sergio en la interfaz. Lo que necesitaba SQL lo hacía Sergio con `psql`
  en el VPS: `prueba4_bis_e2.py` se para y espera a que Sergio enganche el adjunto X por SQL.

**Propuesta para E1′ (los scripts se escriben aparte, cuando Sergio lo pida):** lo mismo que en E2.
- Carpeta `~/staging_e1p` en el equipo de Sergio, fuera del repo; nada se copia al VPS.
- `preparar_e1p.py` (crea AA o desarchiva `e2_aiadmin`, I, P y T; `--limpiar` según D.3) y
  `e1p_estado.json` con los ids; `pruebas_e1p_rpc.py` (D.1: 1, 4, 4b, 6, 7, 8 y control);
  `pruebas_e1p_mcp.py` (D.1: 2, 2b, 3 y 5, y R7). Se parte de los de E1 y E2 con las adaptaciones de
  la comparación (§4.2, «Scripts de staging»).
- Variables `E1P_URL` (por defecto `https://pns.liyben.com`), `E1P_DB`, `E1P_ADM_LOGIN`,
  `E1P_ADM_PASS`, `E1P_PASS` y `E1P_KEY_*`, con `read -s`; biblioteca estándar.
- Los ejecuta Sergio desde su equipo. La línea base y las comprobaciones de tablas, con `psql` en el VPS
  y en solo lectura. La confirmación de 2b pide ahora la contraseña de AA (parche 16): se hace en
  Autorizaciones o el script la pide con `getpass`; se decide al escribirlo.

| Etiqueta | Usuario | Grupos | Para |
|---|---|---|---|
| ADM | `admin` (id 2) | Ajustes + AI Administrator | Control y no regresión |
| U1, UW | los del staging | Chat (UW con AI Writer) | P-07, P-54b, no regresión |
| AA | `e1p_aiadmin` (nuevo) o `e2_aiadmin` desarchivado | Interno + AI Administrator + AI Conversational, **sin** Ajustes; con clave MCP | P-8b, P-01 |
| AA-ERP | AA con «Permisos de acceso» (`base.group_erp_manager`) temporal | Lo mismo + Permisos de acceso | CRUD en `res.groups` |
| I | `e1p_interno` (nuevo) | Interno sin grupos de IA | P-8a, P-83a/b |
| P | `e1p_portal` (nuevo, temporal) | Portal | P-8a, P-83a |
| T | `e1p_objetivo` (nuevo) | Interno + `base.group_partner_manager` | P-01 (quitar) |
| C | contacto de demostración | — | P-8b, P-54b |

Línea base con `SELECT` (solo lectura) antes de las pruebas: `count(*)` de `ai_safe_operation`,
`ir_attachment` y `ai_context WHERE source_module = 'pns_ai_mcp' AND owner_id IS NULL`;
`res_groups_users_rel` de AA y T; `write_uid` y `write_date` de C; recuentos de `ai_key_pin_ask` y
`ai_key_pin_desk`. **Sin mesa de PIN** (N4): no se abre ninguna.

### D.1 Pruebas de seguridad

| # | Prueba (parche) | Quién | Qué se hace | Esperado | Obtenido |
|---|---|---|---|---|---|
| 1 | **P-8b** (M10, parche 13) | AA | Por `call_kw`: `create` de `ai.safe.operation` ya `confirmed` a nombre de ADM con un plan sobre C; `create_verification` con otro `user_id`; `copy` de una operación existente; `cleanup_stuck_state` y `_cleanup_stuck_state` | `create`, `create_verification` y `copy`: `AccessError` «Only the system can create a supervised operation.». `cleanup_stuck_state`: `AttributeError` (ya no existe); `_cleanup_stuck_state`: `AccessError` (privado). `ai_safe_operation` y C sin cambios | [ ] ____ |
| 2 | **P-01** (parche 12) | AA | Por `/mcp`: plan `user.add_group` de `base.group_partner_manager` para sí y `user.remove_group` del mismo grupo a T | Rechazo al proponer: «Only a Settings administrator can add or remove user groups.»; sin operación nueva; grupos de AA y T sin cambios | [ ] ____ |
| 2b | P-01, plan confirmado (como la prueba 7 de E2) | ADM propone, AA confirma en Autorizaciones | ADM propone quitar el grupo a T; AA confirma (ahora pide su contraseña, parche 16) | Rechazo en la ejecución con el mismo mensaje; T conserva el grupo; anotar `status` final (en E2, `cancelled`) | [ ] ____ |
| 3 | **CRUD en `res.groups`** (parche 12) | AA-ERP | Plan con un paso CRUD `write` sobre `users` de `base.group_partner_manager` | Rechazo al proponer con el mismo mensaje; sin operación; el grupo sin cambios. **Control:** ADM propone lo mismo y pasa (cancelarla después) | [ ] ____ |
| 4 | **P-54b** (parche 16) | UW (dueño) y ADM | UW, con una operación suya `pending` (plan sobre C desde el chat), llama por `call_kw` a `action_confirm_and_execute` y a `action_execute_plan`; ADM, lo mismo sobre la de UW | Devuelven la acción del asistente `res.users.identitycheck` y **no ejecutan**: la operación sigue `pending` y C sin cambios | [ ] ____ |
| 4b | `card_payload` (parche 16, b) | ADM | `card_payload(mint_token=True)` sobre la operación de UW | Sin `confirm_token` en la respuesta (solo el dueño lo recibe) | [ ] ____ |
| 5 | **P-07** (parche 15) | U1 | Por `/mcp`, herramienta `relaxaicode`, sin LLM: código que llama a `fulfill_client_export` sobre su sesión, con el nombre literal y con el nombre compuesto | Literal: rechazado sin ejecutar («relaxaicode es SOLO LECTURA»). Compuesto: rechazado en ejecución. **Ningún adjunto nuevo** de U1 (`SELECT` de `ir_attachment` por `create_date` y `create_uid`) | [ ] ____ |
| 6 | **P-8a** (M13, parche 14) | I y P | Por `call_kw`, el nombre antiguo `unlink_retired_from_module` y el privado | Antiguo: `AttributeError`; privado: `AccessError`. Recuento de contextos de fábrica de `pns_ai_mcp` sin cambios | [ ] ____ |
| 7 | **P-83a** (parche 10) | I y P | Por `call_kw` y por `/jsonrpc`: `collect_pin` y `_collect_pin`, **sin mesa abierta** (N4: el caso con mesa no se hace en el staging) | Antiguo: `AttributeError`; privado: `AccessError`; respuesta inmediata (sin la espera de 20 s) | [ ] ____ |
| 8 | **P-83b** (observación; no lo corrige E1′: PNS-84 en E4′) | I | Por RPC: `touch`, `supply`, `collect`, `close`, `notify_changed`, `any_open` | Anotar cuáles responden. Ningún cambio en las tablas de la mesa de PIN | [ ] ____ |
| — | Control | I, P | `res.users.context_get` | Responde | [ ] ____ |

### D.2 No regresión (con el proveedor de A.7)

| # | Caso | Quién | Esperado | Obtenido |
|---|---|---|---|---|
| R1 | Turno de Chatboo con una consulta de datos | U1 | Respuesta correcta; tabla con formato | [ ] ____ |
| R2 | Abrir una sesión anterior al `-u` (historial reescrito, U16; parte visual de P-9e) | U1 | Tablas, fichas, ordenación y gráfico como antes; sin errores en la consola | [ ] ____ |
| R3 | Exportación a Excel (motor) y a PDF desde el navegador (`fulfill_client_export` por la vía normal) | U1 | Las dos descargan (el parche 15 solo la cierra en el sandbox). El PDF puede quedar huérfano: PNS-98, conocido | [ ] ____ |
| R4 | Tarjeta del chat del propio dueño: plan de escritura sobre C, confirmar y ejecutar | UW | Se ejecuta (el dueño sigue recibiendo token; parche 16, b) | [ ] ____ |
| R5 | Autorizaciones: «Confirmar y ejecutar» de una operación pendiente | ADM | Pide la contraseña una vez; ejecuta; una segunda confirmación en menos de 10 minutos no la pide | [ ] ____ |
| R6 | Plan de grupos con Ajustes: quitar y volver a poner `base.group_partner_manager` a T (R6 de E2) | ADM | Las dos operaciones `executed`; T termina con el grupo | [ ] ____ |
| R7 | `relaxaicode` normal por `/mcp`: `search_count` de contactos (R7 de E1) | U1 | Responde con el número | [ ] ____ |
| R8 | Lienzo: una página sencilla desde el chat (el parche 15 deja sus funciones como funciones) | U1 | La página se crea y se ve | [ ] ____ |
| R9 | Log desde el arranque (B.8) | — | Sin `Traceback` salvo los del proveedor (429/503); los rechazos provocados en D.1, a su hora | [ ] ____ |

### D.3 Limpieza de las pruebas

**[ALTERA]** Como en E2: cada usuario de prueba borra sus sesiones; se borran I, P, T y sus contactos;
AA se archiva si `ai_change_journal.confirmed_by_uid` lo referencia; se retiran «Permisos de acceso» de
AA y las claves MCP temporales; operaciones de prueba borradas o canceladas. Recuentos finales frente a
la línea base de D.0. Resultado en la [verificación](verificacion_seguridad_pns_ai.md), en un bloque
nuevo «Staging — entrega E1′».

---

## E. Vuelta atrás (descrita, no lista para pegar)

Operaciones que cambian el VPS: las decide y hace quien administra el VPS.

1. **Antes del `-u` (fallo en B.3 a B.6).** `pns_demo` no ha cambiado. Se devuelve el código de
   `792481c` desde `addons_antes_E1p` con el mismo método (`rsync` con `--delete`, módulo a módulo,
   desde la copia hacia `addons`), se comprueba la huella de A.3 (634, `5dccc29a…`) y se arranca `web`.
2. **Después del `-u`.** **No hay copia de `pns_demo`** (N9). El `-u` cambia la base de datos de forma
   irreversible: borra `ai_log.agent_id` y las `key_pin*` (U9, U5), renombra parámetros (U6) y reescribe
   el historial de Chatboo (U16) (comparación §9.4, «Vuelta atrás»). Volver el código a `792481c`, sin
   `-u` o con él, deja código 3.1.782 sobre un esquema 3.1.879: **no está validado** y no se recomienda.
   Opciones, por orden de preferencia:
   - **Corregir hacia delante:** un commit nuevo en `14.0-pns-ai-3879`, desplegado con este mismo
     método (B.1 a B.8, con `addons_antes_…` del código que haya montado).
   - **Recrear `pns_demo` desde cero** con 3.1.879 si quedara inservible, como la instalación del plan
     de staging (§3 y §4: datos de demostración, proveedor, usuarios y claves). Es coherente con N9: solo
     tiene datos de demostración.
3. **`addons_antes_E1p`** se conserva hasta la limpieza final del staging (plan de staging, §9, punto
   4), como `addons_antes_E1` y `addons_antes_E2`.

---

## F. Lo que no está documentado

| Dato | Dónde se comprueba |
|---|---|
| Cómo se copió el archivo de `git archive` al VPS en E1 y E2 | No consta. En E1′ se copia con `scp` desde el equipo de Sergio a `/tmp/` del VPS (B.2) |
| Opciones de `rsync` de E1 y E2 (si llevaban `--delete`) | No consta; aquí hace falta `--delete` (§0) |
| Cuántas filas de `ai_log` tienen agente hoy en `pns_demo` (la cifra de 978 es de la copia del 22/10) | A.5 |
| Cuota disponible de Gemini el día de la subida | A.7 (consola de Google AI Studio) |
