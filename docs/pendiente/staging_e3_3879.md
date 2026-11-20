# Subida de E3′ y del parche 29 al staging `pns_demo` (parches 25 a 29)

- **Rama:** `14.0-pns-ai-3879` · **Base (montada ahora):** `9a2970d` (E2′) · **Commit a desplegar:**
  `522ce6e`, el último que toca los módulos (`git log --oneline 9a2970d..HEAD -- pns_base pns_ai_mcp
  pns_ai_chatboo`: `60271e6`, `c64a556`, `a3762ec` y `522ce6e`). Los commits posteriores, `bdb9dda` y
  `047ff89`, solo son [DOC]: dan el mismo árbol y la misma huella del árbol, pero otra huella del
  `.tar.gz` (B.1) · **Preparado:** 03/11/2026 · **Estado:** ejecutado el 03 y 04/11/2026 con `522ce6e`;
  resultado en «Resultado de la subida (03 y 04/11/2026)», al final. Pasos previos de D.0 hechos el
  03/11/2026.
- **Qué se sube:** parches 25 (M1), 26 (M2), 27 (F1), 28 (D1) y 29 (P-8e a), todos en `pns_ai_chatboo`.
  Registro en [parches](parches_pns_ai.md), «Parches de la rama 14.0-pns-ai-3879 (E3′)» y «Parche 29».
- **Origen:** «Propuesta final (29/10/2026)» de la [propuesta de E3′](e3_propuesta_3879.md) y
  [hallazgo de P-8e a](e3_hallazgo_p8ea_3879.md). Validación en el laboratorio:
  [lab_e3_3879.md](lab_e3_3879.md), «Resultado (30/10/2026)», y [lab_p29_3879.md](lab_p29_3879.md),
  «Resultado (03/11/2026)».
- **Procedimiento de referencia:** [subida de E2′](staging_e2_3879.md) (mismo método, mismos contenedores) y
  [subida de E1′](staging_e1_3879.md) donde E2′ no tiene equivalente (proveedores y R8).
- **Limpieza del staging: al terminar todos los cambios, no por entrega.** La limpieza del §9 del plan de
  staging (borrar `pns_demo` sin copia, el proyecto `pns_staging`, las copias `addons_antes_*`, el proxy y la
  clave de Gemini) se hace una sola vez, al cerrar la última entrega. En esta subida solo se deshace lo que
  falsearía las pruebas siguientes (D.3).
- **LIYBEN recibe todo de una vez, al final** (plan de corrección, §1 punto 3 y §3), no esta entrega por
  separado. Recordatorios para entonces:
  - Sus claves MCP están **revocadas desde el 27/10/2026** (PNS-101 y PNS-102): **se vuelven a generar
    después del despliegue final** y se comprueba que los clientes conectan (plan de corrección, §3.1).
  - **URLs MCP finales (PNS-17, parche 19):** el cliente MCP por HTTP ya no sigue redirecciones; antes de
    actualizar, comprobar que las URLs de los servidores MCP de LIYBEN son las finales (plan de
    corrección, §3.1).
  - **AI Administrators con contraseña local (parche 16):** comprobado el 26/10/2026 (E1′, A.6); se repite
    antes del despliegue final.
  - La medición de A.6 (`DATA` ilegible y lectores de portal) se repite en LIYBEN, en `odoo14_db`.
- **Condiciones del staging que siguen vigentes:** las del plan de staging, §1 (datos de demostración, sin
  mesa de PIN, `whitelist_only`). Sin copia de `pns_demo` (N9).
- **Sin secretos en este documento:** ni contraseñas, ni claves, ni el contenido de `.env`.

**Convenciones de los comandos.** Las de E2′: **[LECTURA]** solo lee; **[ALTERA]** cambia algo y va
precedido de un aviso. SQL con `psql` en `odoo14_pns_db`, base de datos `pns_demo`, usuario `odoo`. Lo no
confirmado se marca **«Sin confirmar»**. Además, en este documento:
- Las consultas de D son **las de [lab_e3_3879.md](lab_e3_3879.md) y [lab_p29_3879.md](lab_p29_3879.md)
  tal cual** (validadas contra la BD el 03/11/2026). Solo cambian el contenedor, la BD, los ids y los
  marcadores que hay que rellenar (`<…>`). Las que no vienen del laboratorio (dueños de los ilegibles,
  A.8, «Qué modelo diseñó», línea base de D.0 y comprobación final de D.3) se validaron en solo lectura
  contra `lab_pns_ai_3879_14` el 03/11/2026, y así se indica junto a cada una.
- Se lanzan con la función `e3sql` del VPS (A.0), que abre la sesión de PostgreSQL **en solo lectura**
  (`default_transaction_read_only`), y siempre con heredoc `<<'SQL'` (nunca `<<< "…"`: con comillas
  dobles, Bash expande `!` y rompe las consultas con `<!--`).
- Las consultas con barra invertida la generan con `chr(92)`: la herramienta de escritura del agente
  decodifica las secuencias de escape Unicode al escribir.

## Índice

0. Método de despliegue
A. Comprobaciones previas (solo lectura)
B. Despliegue y `-u`
C. Comprobaciones posteriores
D. Pruebas de seguridad y de no regresión
E. Vuelta atrás (descrita)
F. Lo que no está documentado
G. Resultado de la subida

---

## 0. Método de despliegue

El de E2′ (§0): `git archive` de los tres módulos desde el equipo de Sergio, `scp` a `/tmp` del VPS, huella
comparada en el VPS, copia previa en `addons_antes_E3p`, parada de `web`, `rsync --delete` módulo a módulo
como `ubuntu` y `-u`.

**Diferencias con E2′** (comprobado el 03/11/2026 con `git diff --stat` y `--name-status 9a2970d..522ce6e`):
- **Solo cambia `pns_ai_chatboo`.** 7 archivos: 6 distintos (`controllers/chatboo.py`,
  `models/chatboo_canvas.py`, `models/chatboo_canvas_page.py`, `models/chatboo_session.py`,
  `security/security.xml` y `tests/__init__.py`) y 1 nuevo (`tests/test_seges_chatboo_canvas.py`).
  **Ninguna baja.** `pns_base` y `pns_ai_mcp` no cambian.
- **Sin cambio de versión ni de esquema.** Los tres manifiestos siguen en `1.2.47`, `3.1.879` y `2.1.538`.
  No cambian manifiestos, vistas, datos, CSV, JS ni `i18n`. El diff no añade ni quita ningún campo
  (`fields.`); lo único nuevo en los modelos es un constraint de Python (`@api.constrains('user_ids')`,
  `_check_user_ids_internal`, parche 28), que se carga al arrancar.
- **`-u` solo de `pns_ai_chatboo`.** Criterio de Sergio de E2′: un módulo entra en el `-u` si cambia algo que
  el `-u` carga. En `pns_ai_chatboo` cambia `security/security.xml` (cargado por el manifiesto): la regla
  `chatboo_canvas_page_admin_rule` (parche 28) pasa `perm_write` y `perm_create` a `False`. Está en
  `<data noupdate="0">` (`security.xml:7`), así que **solo se aplica con el `-u`**: un reinicio dejaría la
  regla con los cuatro permisos. `pns_base` y `pns_ai_mcp` quedan fuera porque no cambian.
- **Sin fotografía de P-9 ni recarga de `es_ES`:** no hay pérdidas de esquema ni traducciones nuevas (C.3).
- **La vuelta atrás del código es viable** (E), con un matiz: la regla vuelve con un `-u` del código
  anterior.
- **Nuevo en esta subida:** la medición de lienzos y páginas guardados con `DATA` ilegible y de lectores de
  portal, antes del despliegue (A.6) y después de las pruebas (D.2b).

---

## A. Comprobaciones previas (solo lectura)

Desde el VPS, con el usuario `ubuntu`.

### A.0 Función de consulta

**[LECTURA]** En la terminal del VPS. La sesión de PostgreSQL se abre en solo lectura: un `INSERT` o un
`UPDATE` pegado por error falla.

```bash
e3sql() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_pns_db psql -U odoo -d pns_demo -v ON_ERROR_STOP=1 -v sesion="${E3P_SESSION:-0}"; }
e3sql <<'SQL'
SHOW default_transaction_read_only;
SHOW TimeZone;
SQL
```

Esperado: `on` y `UTC`. La zona horaria es **«Sin confirmar»** en `odoo14_pns_db`: la consulta de `ai_log` de
D usa `now() - interval '15 minutes'` contra `create_date` (UTC); si no es `UTC`, se revisa con
`'<reinicio>'` (D.1, fila 6c).

### A.1 Contenedores y usuario de PostgreSQL

**[LECTURA]** Como en E2′ (A.1):

```bash
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}' | grep -E 'odoo14_pns|odoo14_db|odoo14_server'
docker exec odoo14_pns_db printenv POSTGRES_USER
```

Esperado: `odoo14_pns` y `odoo14_pns_db` en marcha; `POSTGRES_USER` = `odoo`.

### A.2 Cómo está montado el código

**[LECTURA]** Como en E2′ (A.2):

```bash
docker inspect odoo14_pns --format '{{range .Mounts}}{{.Type}}  {{.Source}} -> {{.Destination}}  rw={{.RW}}{{"\n"}}{{end}}'
cd /opt/odoo/pns_staging && ls -la && ls -la addons
df -h /opt/odoo /tmp
```

Esperado: los montajes de E2′, sin cambios. En `addons`, los tres módulos, de `ubuntu`. Deben estar
`addons_antes_E1`, `addons_antes_E2`, `addons_antes_E1p` y `addons_antes_E2p`, y **todavía no**
`addons_antes_E3p`.

### A.3 Qué código hay montado (huella)

Calculada el 03/11/2026 en el equipo (git 2.43.0) sobre los archivos de cada commit. Con el mismo método,
`9a2970d` reproduce las huellas de E2′ (A.3 y B.1):

| Commit | Archivos | Huella del árbol |
|---|---|---|
| `9a2970d` (E2′, lo que debería estar montado) | 709 | `7a6c7144880aab3680db5d47d22bf041e91697d02879aaef69c02610fe00bb9f` |
| `522ce6e` (E3′ y parche 29, lo que se va a montar) | 710 | `6ac645fcfffa3d6a5707d2e3eb7e98518f5d4f1039dc8a32c91782769f6e44e5` |

**[LECTURA]**

```bash
cd /opt/odoo/pns_staging/addons
find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l
find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum
```

Esperado: 709 y `7a6c7144…bb9f`. **Si no coincide, parar:** alguien ha cambiado el código desde E2′.

### A.4 Estado de `pns_demo`: módulos, crons y actividad

**[LECTURA]** El bloque de E2′ (A.4), sin cambios:

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

Esperado (como en C.2 de E2′):
- `pns_base` 14.0.1.2.47, `pns_ai_mcp` 14.0.3.1.879 y `pns_ai_chatboo` 14.0.2.1.538, `installed`.
- Sin filas `odoo_dev.%`.
- Siete crons de `pns_*`; `pns_ai_mcp.ir_cron_ai_journal_trash` activo, diario, `numbercall` -1 y `user_id` 1.
- Ninguna transacción en curso.

### A.5 Regla del AI Administrator antes del `-u`

**[LECTURA]** La consulta de [lab_e3_3879.md](lab_e3_3879.md), 0.1, tal cual:

```bash
e3sql <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT r.name, r.perm_read, r.perm_write, r.perm_create, r.perm_unlink
  FROM ir_rule r JOIN ir_model_data d ON d.res_id = r.id AND d.model = 'ir.rule'
 WHERE d.module = 'pns_ai_chatboo' AND d.name = 'chatboo_canvas_page_admin_rule';
-- antes del -u: t, t, t, t; después (C.1): t, f, f, t
ROLLBACK;
SQL
```

Esperado **antes** del `-u`: `t t t t` (lo que carga `security.xml` en `9a2970d`). Después del `-u`, `t f f t`
(C.1).

### A.6 Lienzos y páginas guardados con `DATA` ilegible y lectores de portal (antes)

**Qué mide.** [`medir_data_ilegible.py`](scripts_e3/medir_data_ilegible.py) cuenta los lienzos
(`chatboo_session.canvas_design`) y las páginas compartidas (`chatboo_canvas_page.design`) con un `DATA`
que el servidor no puede leer: la misma comprobación que el parche 29. Lo leí el 03/11/2026 (SHA-256
`05af0d60…f16e`, igual en el repo y en `~/lab_e3p`): **es de solo lectura** (lee la entrada estándar y
escribe en la salida estándar, sin abrir archivos ni conexiones; solo usa `json`, `re` y `sys`) y **no
imprime contenido de los lienzos**: por modelo, el número de diseños, el de ilegibles y sus ids.

**Cómo se lee lo que salga «antes».** Es **riesgo residual real**: lienzos y páginas de usuarios guardados
antes del parche, con un `DATA` del modelo que pudo cortar el `<script>`. **El parche no los corrige:**
actúa al pintar y al guardar, no sobre lo ya guardado (el prefijo CSP del parche 27 b sí se aplica al
servirlos). Se anotan los ids y sus dueños, sin contenido; qué hacer con ellos lo decide Sergio.

**Dónde se ejecuta.** Que haya `python3` en el host del VPS es **«Sin confirmar»**:

```bash
python3 --version
```

- **Opción A (hay `python3` en el host).** **[ALTERA solo `/tmp` del VPS]** Desde el equipo de Sergio, con
  `VPS_PORT` y `VPS_DEST` como en B.2:
  ```bash
  read -rp 'Puerto SSH del VPS: ' VPS_PORT; read -rp 'Usuario@host del VPS: ' VPS_DEST
  scp -P "$VPS_PORT" ~/GitHub/third_party/docs/pendiente/scripts_e3/medir_data_ilegible.py "$VPS_DEST":/tmp/
  ```
  En el VPS, **[LECTURA]**: `sha256sum /tmp/medir_data_ilegible.py` (esperado `05af0d60…f16e`) y la función
  `e3medir` de [lab_p29_3879.md](lab_p29_3879.md), 0.1, con el contenedor, la BD y la ruta del VPS:
  ```bash
  e3medir() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_pns_db psql -U odoo -d pns_demo -At -c "SELECT row_to_json(t) FROM (SELECT 'chatboo.session' AS m, id, canvas_design AS d FROM chatboo_session WHERE canvas_design IS NOT NULL UNION ALL SELECT 'chatboo.canvas.page', id, design FROM chatboo_canvas_page WHERE design IS NOT NULL) t;" | python3 -I /tmp/medir_data_ilegible.py; }
  e3medir | tee /tmp/pns_e3p_medir_antes.txt
  ```
- **Opción B (sin `python3` en el host).** **[LECTURA]** Desde el equipo de Sergio, la salida de `psql`
  viaja por `ssh` hasta el script, sin copiar nada al VPS ni guardar los diseños en ningún lado (pasan por
  la tubería y el script solo imprime ids):
  ```bash
  cd ~/staging_e3p
  read -rp 'Puerto SSH del VPS: ' VPS_PORT; read -rp 'Usuario@host del VPS: ' VPS_DEST
  ssh -p "$VPS_PORT" "$VPS_DEST" "docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_pns_db psql -U odoo -d pns_demo -At" <<'SQL' | python3 -I ~/staging_e3p/medir_data_ilegible.py | tee ~/staging_e3p/medir_antes.txt
  SELECT row_to_json(t) FROM (SELECT 'chatboo.session' AS m, id, canvas_design AS d FROM chatboo_session WHERE canvas_design IS NOT NULL UNION ALL SELECT 'chatboo.canvas.page', id, design FROM chatboo_canvas_page WHERE design IS NOT NULL) t;
  SQL
  ```
  `~/staging_e3p/medir_data_ilegible.py` es la copia de D.0 (misma huella).

**Dueños de los ilegibles, sin contenido** (validada en el laboratorio el 03/11/2026 con las sesiones 12 y
14; la de páginas, con una lista vacía, porque allí no queda ninguna). **[LECTURA]** Con los ids que haya
dado `e3medir` (si no hay ninguno, no se lanza):

```bash
e3sql <<'SQL'
SELECT s.id AS sesion, s.user_id, u.login, u.share, s.canvas_rev, s.write_date
  FROM chatboo_session s JOIN res_users u ON u.id = s.user_id
 WHERE s.id = ANY ('{<ids de chatboo.session>}'::int[]) ORDER BY s.id;
SELECT p.id AS pagina, p.owner_id, u.login, p.write_date,
       (SELECT count(*) FROM chatboo_canvas_page_user_rel r WHERE r.page_id = p.id) AS lectores
  FROM chatboo_canvas_page p JOIN res_users u ON u.id = p.owner_id
 WHERE p.id = ANY ('{<ids de chatboo.canvas.page>}'::int[]) ORDER BY p.id;
SQL
```

**Lectores de portal guardados (m3).** **[LECTURA]** La consulta de [lab_e3_3879.md](lab_e3_3879.md), 8b,
tal cual:

```bash
e3sql <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT count(*) AS lectores_portal
  FROM chatboo_canvas_page_user_rel r JOIN res_users u ON u.id = r.user_id
 WHERE u.share;
-- esperado en el laboratorio: 0. En el staging y en LIYBEN: anotar el número; si no es 0, decide Sergio
ROLLBACK;
SQL
```

| Medición (antes) | Obtenido |
|---|---|
| `python3` en el host / opción usada | [x] `python3` 3.12.3 en el host; opción A, script `05af0d60…f16e` en `/tmp` |
| `chatboo.session`: con diseño / ilegibles (ids) | [x] 0 / 0 (`/tmp/pns_e3p_medir_antes.txt`) |
| `chatboo.canvas.page`: con diseño / ilegibles (ids) | [x] 0 / 0 |
| Dueños de los ilegibles (login, `write_date`) | [x] No aplica: 0 ilegibles, sin riesgo residual; 6d′ no aplica |
| Lectores de portal guardados (m3) | [x] 0 |

**Si sale una sesión ilegible cuyo dueño Sergio pueda usar** (por ejemplo, de `admin` o de U1), se anota:
es la candidata de 6d′ (D.1).

### A.7 Proveedores del staging

**[LECTURA]** La consulta de [lab_e3_3879.md](lab_e3_3879.md), 0.2, y la de la cadena de E1′ (A.7), sin leer
`api_key`:

```bash
e3sql <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT id, name, model_name, active, fit_conversation, fit_design FROM ai_provider ORDER BY id;
SELECT a.code AS agente, ap.priority, ap.active, p.name AS proveedor, p.active AS proveedor_activo
  FROM ai_agent_provider ap
  JOIN ai_agent a ON a.id = ap.agent_id
  JOIN ai_provider p ON p.id = ap.provider_id
 ORDER BY a.code, ap.priority, ap.id;
ROLLBACK;
SQL
```

Esperado: la cadena de Chatboo con Gemini 3.6 flash, 3.5 flash y 3.5 flash lite, como en E2′ (G, A.7). Los
ids de los tres en `pns_demo` y su casilla «Design» son **«Sin confirmar»**: se anotan para D.0.

Después, en la interfaz y **solo Sergio**: «Test Connection» de los tres **y cuota en la consola de Google
AI Studio** (F de E1′: «Test Connection» no basta). El nivel gratuito da 20 peticiones al día por modelo
(plan de staging §7.2) y esta subida tiene unos 13 turnos de chat con diseño (R8, comprobación visual,
P-8d, 5a a 5c, 6b, 6c, 6d′ y 6e), cada uno con varias llamadas: conviene hacer D el mismo día que se
comprueba la cuota.

### A.8 Datos para las pruebas de D

**[LECTURA]** Usuarios que usan el script y las pruebas (consulta validada en el laboratorio el
03/11/2026, sin U1; no lee contraseñas, solo si hay una). `<login de U1>` es el login del usuario de chat
del staging (R8):

```bash
e3sql <<'SQL'
BEGIN TRANSACTION READ ONLY;
-- Logins que pide pruebas_e3p_lab.py (admin y demo con contraseña; portal solo se lee), U1 y restos de E3′
SELECT u.id, u.login, u.active, u.share,
       (u.password IS NOT NULL AND u.password <> '') AS contrasena_local
  FROM res_users u
 WHERE u.login IN ('admin', 'demo', 'portal', '<login de U1>') OR left(u.login, 4) = 'e3p_'
 ORDER BY u.id;
-- Grupos de IA de admin (Chatboo exige AI Conversational y clave MCP propia)
SELECT d.name AS grupo
  FROM res_groups_users_rel r
  JOIN ir_model_data d ON d.model = 'res.groups' AND d.res_id = r.gid AND d.module = 'pns_ai_mcp'
 WHERE r.uid = 2 ORDER BY 1;
SELECT m.id, u.login, m.mcp_api_key_state
  FROM ai_mcp_user m JOIN res_users u ON u.id = m.user_id
 WHERE u.login IN ('admin', 'demo', '<login de U1>') ORDER BY m.id;
-- Restos de pruebas anteriores con el prefijo de E3′ (esperado: 0, 0, 0)
SELECT 'pagina' AS que, count(*) FROM chatboo_canvas_page WHERE name LIKE 'Seges E3%'
UNION ALL SELECT 'contacto', count(*) FROM res_partner WHERE name LIKE 'Seges E3%'
UNION ALL SELECT 'compañía', count(*) FROM res_company WHERE name LIKE 'Seges E3%';
ROLLBACK;
SQL
```

Esperado: `admin` (id 2) activo, interno y con contraseña local; si tiene `group_ai_conversational` y en qué
estado está su clave MCP (en E2′ quedó en `not_generated`). U1 activo e interno, con clave MCP
`generated` (la usa para el chat en R8); **se anota su id** (consulta de R8). Si `demo` o `portal` **no
existen** en `pns_demo`, se crean temporales con ese login (D.0, decisión de Sergio del 03/11/2026).

En el laboratorio (03/11/2026): `admin` 2, `demo` 6 y `portal` 7, los tres con contraseña local; `admin`
con los cinco grupos de IA; restos «Seges E3»: 0 páginas, 2 contactos (el 68, activo, y el 74, archivado;
la consulta cuenta también los archivados) y 0 compañías.

---

## B. Despliegue y `-u`

El orden de E2′: archivo (B.1 a B.4, sin tocar `pns_demo`), copia (B.5), parar y sustituir (B.6), `-u`
(B.7), log y arranque (B.8).

### B.1 En el equipo de Sergio: archivo del commit

**[LECTURA del repo]**

```bash
cd ~/GitHub/third_party
git cat-file -t 522ce6e
git archive --format=tar.gz -o /tmp/pns_addons_522ce6e.tar.gz 522ce6e pns_base pns_ai_mcp pns_ai_chatboo
sha256sum /tmp/pns_addons_522ce6e.tar.gz
```

Esperado: `commit` y `34b1b023d1c2d3944dcfdfe46c832ab0c5a897a1b49c9695161192ff76d8f3d0`, calculada el
03/11/2026 con git 2.43.0. Si se despliega otro commit, se sustituye en las tres órdenes. Con `047ff89`
(HEAD, solo [DOC] después de `522ce6e`) sale `66239eb8283e14ddb52c2791b75313b0cba56025526f7ff0196882369606135e`:
el `.tar.gz` lleva el id del commit en su cabecera, y la huella del árbol (B.4) es la misma. Con el mismo
método, `9a2970d` da `0dd550a3…6fd6`, la de E2′.

### B.2 Copia al VPS

**[ALTERA solo `/tmp` del VPS]** Como en E2′ (B.2):

```bash
read -rp 'Puerto SSH del VPS: ' VPS_PORT; read -rp 'Usuario@host del VPS: ' VPS_DEST
scp -P "$VPS_PORT" /tmp/pns_addons_522ce6e.tar.gz "$VPS_DEST":/tmp/
```

### B.3 En el VPS: huella y extracción

**[LECTURA]** `sha256sum /tmp/pns_addons_522ce6e.tar.gz` (la de B.1).

**[ALTERA solo `/tmp`]**

```bash
rm -rf /tmp/pns_addons_E3p && mkdir /tmp/pns_addons_E3p && tar -xzf /tmp/pns_addons_522ce6e.tar.gz -C /tmp/pns_addons_E3p
```

### B.4 Comprobaciones del código extraído

**[LECTURA]**

```bash
cd /tmp/pns_addons_E3p
grep -n "'version'" pns_base/__manifest__.py pns_ai_mcp/__manifest__.py pns_ai_chatboo/__manifest__.py
grep -rn "Seges: parche" pns_base pns_ai_mcp pns_ai_chatboo --include=*.py --include=*.js --include=*.xml | grep -v '/tests/' | wc -l
for n in 25 26 27 28 29; do printf 'parche %s: ' $n; grep -rn "Seges: parche $n " pns_base pns_ai_mcp pns_ai_chatboo | grep -v '/tests/' | wc -l; done
grep -c 'def _paint_canvas(' pns_ai_chatboo/models/chatboo_session.py
grep -c 'def paint_canvas(' pns_ai_chatboo/models/chatboo_session.py
grep -rc 'pictures_as_tokens(.*env(su=False)' pns_ai_chatboo/models | grep -v ':0$'
grep -c '^_CSP_PREFIX = ' pns_ai_chatboo/models/chatboo_canvas.py
grep -c "('X-Frame-Options', 'SAMEORIGIN')" pns_ai_chatboo/controllers/chatboo.py
grep -c 'def _check_user_ids_internal(' pns_ai_chatboo/models/chatboo_canvas_page.py
grep -A10 'id="chatboo_canvas_page_admin_rule"' pns_ai_chatboo/security/security.xml | grep -E 'perm_(write|create)'
grep -c '_model_data_left(' pns_ai_chatboo/models/chatboo_canvas.py
ls pns_ai_chatboo/tests/test_seges_chatboo_canvas.py
find pns_base pns_ai_mcp pns_ai_chatboo -type f | wc -l
find pns_base pns_ai_mcp pns_ai_chatboo -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum
```

Esperado (comprobado en el equipo el 03/11/2026 sobre el archivo de `522ce6e`; entre paréntesis, lo que da
`9a2970d`, para ver que cada línea distingue el código nuevo):

| Comprobación | Esperado |
|---|---|
| Versiones | `1.2.47`, `3.1.879`, `2.1.538` (sin cambios) |
| Marcadores «Seges: parche» fuera de tests (`.py`, `.js` y `.xml`) | 113: los 75 de E1′ y E2′ (con `.xml` siguen siendo 75 en `9a2970d`) y 38 de E3′ y del parche 29 |
| Por parche (25 a 29) | 5, 2, 13, 4, 14 (uno de los 4 del 28, en `security.xml`) |
| Parche 25: `def _paint_canvas(` / `def paint_canvas(` | 1 / 0 (antes 0 / 1) |
| Parche 26: `pictures_as_tokens(…env(su=False)` | `chatboo_session.py:1` y `chatboo_canvas.py:1` (antes, ninguna línea) |
| Parche 27: `_CSP_PREFIX = ` / `X-Frame-Options` | 1 / 2 (antes 0 / 0) |
| Parche 28: `def _check_user_ids_internal(` / regla | 1; `perm_write` y `perm_create` con `eval="False"` (antes 0; `True`) |
| Parche 29: `_model_data_left(` | 2: la definición y su llamada en `place_rows_on_page` (antes 0; `place_rows_on_page` ya existía y no distingue) |
| Test nuevo | `test_seges_chatboo_canvas.py` presente |
| Archivos / huella del árbol | 710 / `6ac645fc…44e5` (A.3) |

Si algo no coincide, **no seguir**.

### B.5 Copia del código actual

**[ALTERA]** Crea `/opt/odoo/pns_staging/addons_antes_E3p` con el código de `9a2970d`:

```bash
cd /opt/odoo/pns_staging && test ! -e addons_antes_E3p && cp -a addons addons_antes_E3p && ls -d addons_antes_*
```

### B.6 Parar Odoo y sustituir el código

**[ALTERA]** Para `web` (`odoo14_pns`). `pns_demo` deja de responder hasta B.8:

```bash
cd /opt/odoo/pns_staging && docker compose stop web && docker compose ps
```

**[LECTURA]** Ensayo del `rsync`. Como en E2′, **no debe listar ninguna baja** (el diff de `9a2970d` a
`522ce6e` no borra archivos; simulado en el equipo el 03/11/2026, sin bajas):

```bash
for m in pns_base pns_ai_mcp pns_ai_chatboo; do rsync -ani --delete /tmp/pns_addons_E3p/$m/ /opt/odoo/pns_staging/addons/$m/ | grep '^\*deleting'; done
```

**[ALTERA]** Sustitución, módulo a módulo, como `ubuntu` y sin `sudo`:

```bash
for m in pns_base pns_ai_mcp pns_ai_chatboo; do rsync -a --delete /tmp/pns_addons_E3p/$m/ /opt/odoo/pns_staging/addons/$m/; done
```

**[LECTURA]** Verificación:

```bash
cd /opt/odoo/pns_staging/addons
find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l
find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum
cd /opt/odoo/pns_staging && LC_ALL=C diff -rq addons_antes_E3p addons > /tmp/pns_diff_E3p.txt; wc -l < /tmp/pns_diff_E3p.txt
grep -c '^Files ' /tmp/pns_diff_E3p.txt; grep -c '^Only in addons/' /tmp/pns_diff_E3p.txt; grep -c '^Only in addons_antes_E3p' /tmp/pns_diff_E3p.txt
```

Esperado: 710 archivos y huella `6ac645fc…44e5`. En el `diff -rq`, 7 líneas: 6 archivos distintos, 1 solo en
`addons` y 0 solo en `addons_antes_E3p` (los de 0, «Diferencias con E2′»; simulado en el equipo el
03/11/2026 entre los árboles de `9a2970d` y `522ce6e`).

### B.7 `-u` de `pns_ai_chatboo`

**[ALTERA `pns_demo`, sin copia (N9)]** Vuelve a cargar los XML de datos, la seguridad y las vistas de
`pns_ai_chatboo`. Lo único que cambia respecto al `-u` de E2′ es la regla `chatboo_canvas_page_admin_rule`
(`perm_write` y `perm_create` a `False`). No cambia el esquema. Un registro de datos de `pns_ai_chatboo` sin
`noupdate` que se hubiera retocado a mano desde E2′ volvería al valor del módulo, y no consta ninguno. Las
casillas «Design» de los proveedores (D.0) son de `pns_ai_mcp` y datos del usuario: el `-u` no las toca.

```bash
cd /opt/odoo/pns_staging && docker compose run --rm -T web odoo -u pns_ai_chatboo -d pns_demo --stop-after-init 2>&1 | tee /tmp/pns_u_E3p.log
```

### B.8 Revisar el log y arrancar

**[LECTURA]**

```bash
L=/tmp/pns_u_E3p.log
grep -cE 'Traceback|ERROR|CRITICAL' $L
grep -c 'Deleting field' $L
grep -E 'No module named|module .* not (found|installable)' $L
grep 'WARNING' $L | sed 's/.* WARNING [^ ]* //' | sort | uniq -c
grep -E 'Modules loaded|Registry loaded' $L | tail -2
```

Esperado: 0 `Traceback`, `ERROR` y `CRITICAL`; **0 «Deleting field»** (el diff no añade ni quita campos);
ningún módulo que no se importe. Los `WARNING`, **«Sin confirmar»**: el laboratorio hizo
`actualizar pns_ai_chatboo` (RESULTADO OK) pero no anotó sus avisos. Como referencia, los del `-u` de E2′
(G, B.7 y B.8): etiquetas repetidas (`ai.log` «Client» ×2, `ai.trusted.action` «Model»), `skip retired
unlink for pns_ai_mcp` y dos `DeprecationWarning` de `distutils`. Con `-u` solo de `pns_ai_chatboo`,
alguno de los de `pns_ai_mcp` puede no salir. Se anotan los que salgan.

**Si hay `Traceback`, `ERROR` o `CRITICAL`: no arrancar** y decidir con el apartado E.

**[ALTERA]** Arranca `web`:

```bash
cd /opt/odoo/pns_staging && docker compose start web && docker compose ps
```

**[LECTURA]** Hora del arranque (UTC): es el **reinicio** que usan las consultas de D (en el laboratorio,
apartado 4 de [lab_p29_3879.md](lab_p29_3879.md)). Se anota con la forma `2026-11-04 10:57:35`:

```bash
docker inspect -f '{{.State.StartedAt}}' odoo14_pns
```

**[LECTURA]** Tras uno o dos minutos:

```bash
cd /opt/odoo/pns_staging && docker compose logs --since 10m web 2>&1 | grep -cE 'Traceback|ERROR|CRITICAL'
curl -sS -o /dev/null -w '%{http_code}\n' https://pns.liyben.com/web/login
curl -sS -o /dev/null -w '%{http_code}\n' https://pns.liyben.com/mcp
```

Esperado: 0; `200`; `403`.

**[ALTERA solo `/tmp`]** Borrar `/tmp/pns_addons_522ce6e.tar.gz` y `/tmp/pns_addons_E3p`. El log, el diff y
`/tmp/pns_e3p_medir_antes.txt` se conservan hasta anotar los resultados.

---

## C. Comprobaciones posteriores

### C.1 Regla del AI Administrator

**[LECTURA]** La consulta de A.5.

| Comprobación | Esperado | Obtenido |
|---|---|---|
| `chatboo_canvas_page_admin_rule` (`perm_read`, `perm_write`, `perm_create`, `perm_unlink`) | `t f f t`, como en 0.1 de [lab_e3_3879.md](lab_e3_3879.md) | [x] OK: `t f f t` |

### C.2 Módulos y crons

**[LECTURA]** El bloque de A.4, sin la consulta de actividad.

| Comprobación | Esperado | Obtenido |
|---|---|---|
| Versiones | Las de A.4, `installed` (sin cambio de versión) | [x] Igual que A.4: `1.2.47`, `3.1.879` y `2.1.538` |
| Cron de la papelera | `pns_ai_mcp.ir_cron_ai_journal_trash` activo, diario, `numbercall` -1, `user_id` 1 | [x] Igual que A.4 |
| Resto de crons | Los seis de A.4, sin cambios | [x] Igual que A.4 (7 crons `pns_*` en total) |
| Neutralización | Ninguna fila `odoo_dev.%` | [x] Igual que A.4: ninguna |

### C.3 Recargar `es_ES`

No aplica: E3′ y el parche 29 no tocan `i18n` (regla de los parches; comprobado en el diff) y `es_ES` ya se
recargó tras E1′.

---

## D. Pruebas de seguridad y de no regresión de E3′ y del parche 29

**Decisiones de Sergio (03/11/2026):**
- **Sin pruebas «antes del parche»:** el fallo ya quedó demostrado en el laboratorio
  ([lab_p29_3879.md](lab_p29_3879.md), apartados 2 y 3). Sí se hacen las mediciones «antes» (A.6).
- **Usuario de portal nuevo y temporal** (PT) para 5c (P-8e a con un disparador externo), con la ciudad
  con comilla simple, como en el laboratorio, aunque un contacto nuevo no tenga facturas.
- **6d′ solo si A.6 encuentra un lienzo con `DATA` ilegible** en una sesión que Sergio pueda usar con su
  dueño; si no, «no aplica» (cubierto por [lab_p29_3879.md](lab_p29_3879.md), 6d′, y por
  `test_edit_page_without_data`).
- **«Design» en los tres proveedores Gemini** (3.6 flash, 3.5 flash y 3.5 flash lite), por si alguno no tiene
  cuota. Es una **excepción a la decisión 6** de la [propuesta de E3′](e3_propuesta_3879.md) («R8 con un
  modelo de diseño que no sea `lite`»). Por eso, en R8 y en las pruebas que pinten, se anota con `ai_log`
  qué modelo diseñó la página. **Si R8 la diseña `lite` y no se crea, R8 queda no concluyente por el
  proveedor (PNS-96)**, como en E1′.
- **Cuota de Gemini:** en la consola de Google AI Studio, no solo con «Test Connection» (A.7).
- **`demo` y `portal`:** si no existen en `pns_demo`, se crean temporales con ese login (D.0) y se archivan
  en D.3.
- **R8 la hace U1**, como en E1′ (no regresión de un usuario de chat normal), y sigue haciendo de 6a en su
  sesión. **`E3P_SESSION` es la sesión de ADM de la primera página de la comprobación visual (R-vis)**: la
  usan P-8c y el paso `http`. 6b va al final, sobre esa sesión de ADM.

**Orden de ejecución** (el de [lab_e3_3879.md](lab_e3_3879.md): el script necesita una sesión de `admin` con
lienzo):
1. D.0 completo (pasos previos, usuarios, casillas, PT con su ciudad).
2. R8 con U1 (D.2) y la comprobación visual con ADM (R-vis, D.2), cuya primera página da `E3P_SESSION`.
3. `preparar` del script (D.0).
4. D.1 en orden: P-8c y P-8h (paso `rpc`), P-8d, P-8e a (5a, 5b, 5c), 6c, 6e, P-8e b y `X-Frame-Options`
   (paso `http`), 6b y 6d′.
5. Log (D.2, R-log), medición después (D.2b) y limpieza (D.3).

### D.0 Preparación

**[ALTERA `pns_demo`]** Datos, usuarios y claves temporales. Los autoriza y crea Sergio, como en E1′ y E2′.

| Etiqueta | Usuario | Para |
|---|---|---|
| ADM | `admin` (id 2), Ajustes + AI Administrator, con AI Conversational y **clave MCP temporal** para usar Chatboo (A.8) | Comprobación visual (`E3P_SESSION`), P-8c, P-8h, P-8d, P-8e a, 6b a 6e, P-8e b |
| U1 | el usuario de chat del staging (`<login de U1>`, id de A.8), con su clave MCP | R8 (y 6a) |
| DEMO | `demo`, interno, con su contraseña (el paso `rpc` la pide). **Si no existe en `pns_demo`:** se crea temporal con login `demo` (abajo, paso 3) | P-8c1, P-8c2 y P-8h5 a P-8h11 |
| PORTAL | `portal`: el script **solo lee su id** para P-8h3, sin entrar con él. **Si no existe en `pns_demo`:** se crea temporal con login `portal` (abajo, paso 3) | P-8h3 |
| PT | usuario de portal **nuevo y temporal**, login `e3p_portal`, nombre «Seges E3 portal» | 5c |

**Requisitos previos (bloquean la subida, no la redacción).** Como en E2′ (D.0), no se empieza A ni se
toca el staging hasta tenerlos hechos:

| # | Paso previo | Por qué bloquea | Validación | Hecho |
|---|---|---|---|---|
| 1 | **[ALTERA la BD del laboratorio `lab_pns_ai_3879_14`]** Ejecutar en el laboratorio el **nuevo orden de `preparar` y después `limpiar`** con el script del repo. Nunca se ha ejecutado entero: el 30/10/2026 `preparar` falló (quitaba la compañía a `admin` antes de crear el contacto oculto) y se completó a mano. **Ojo:** `~/lab_e3p/pruebas_e3p_lab.py` todavía es la versión anterior (SHA-256 `3c807309…cadaca`, con el orden antiguo en `preparar`; `limpiar` igual): hay que copiar el del repo (`c433305c…32e2`, con `limpiar` corregido el 03/11/2026). Antes, apartar el estado del 30/10 (paso 2), para que `limpiar` no intente borrar las páginas 9, 12 y 14 que ya no existen | Es la versión de `preparar` que se va a usar en el staging y no se ha probado nunca | Con el contexto del laboratorio arrancado (lo hace Sergio): `cp ~/GitHub/third_party/docs/pendiente/scripts_e3/pruebas_e3p_lab.py ~/lab_e3p/ && cd ~/lab_e3p && sha256sum pruebas_e3p_lab.py && python3 pruebas_e3p_lab.py preparar`. Esperado: `compañía ok <id>`, `admin sin la compañía ok`, `contactos ok ok ok`, las dos rutas de imagen, `P-8e a: contactos [<a>, <b>]` y `Comprobación: admin no ve el oculto -> ('ok', 0)`. Después, `python3 pruebas_e3p_lab.py limpiar`. Esperado: sin línea `páginas` (no hay páginas en el estado nuevo), `admin con la compañía ok`, `contactos ('ok', True)` (al repetirlo sobre el estado del 03/11, con los contactos 76 a 79 ya borrados: `contactos ya borrados`), `propiedades ok N` (N ≥ 1; en el laboratorio, al menos la 82), `acción temporal ('ok', True)`, `admin sin la compañía ok`, `compañía ('ok', True)` y `Queda el archivo de estado: …`. Las propiedades se borran antes que la compañía porque `res.company.create` le crea una `property_product_pricelist` sin `res_id`, que al borrar la compañía queda con `company_id` NULL y choca con `ir_property_unique_index` si ya hay otra igual (o queda huérfana); como `admin` no tiene `perm_unlink` en `ir.property`, lo hace una acción de servidor temporal ([lab_e3_3879.md](lab_e3_3879.md), apartado 9). La huérfana 81 del laboratorio (del borrado de la compañía 3) no la toca: es un resto que decide Sergio. Por último, la consulta de [lab_p29_3879.md](lab_p29_3879.md), apartado 8 (con `e3sql` del laboratorio). **Esperado: 0 / 2 / 0**, o **0 / 1 / 0** si Sergio ya archivó el 68: `res.company.create` crea un contacto «Seges E3 otra» con la compañía y Odoo no lo borra con ella, así que este `preparar` deja otro igual que el 68, que también se archiva a mano | [x] 03/11/2026. `preparar` OK (compañía 4, contactos 76 a 79). El primer `limpiar` falló en la compañía por `ir_property_unique_index` (chocaba con la propiedad huérfana 81 que dejó el borrado de la compañía 3) y se corrigió el script (`c433305c…32e2`). Repetido: `contactos ya borrados`, `propiedades ok 1` (la 82), `acción temporal ('ok', True)` y compañía borrada. Sergio borró la huérfana 81 con `odoo-dev 14 shell` (comprobando antes campo, compañía y `res_id`). Ciclo completo sin huérfana previa: compañía 5, contactos 81 a 84, `admin no ve el oculto -> ('ok', 0)`; `limpiar` sin errores, `propiedades ok 1` (la 83). Después: 0 páginas, 0 compañías, 0 acciones «Seges E3%», `admin` con 1 compañía y ninguna propiedad de tarifa sin `res_id`. Los «Seges E3 otra» 68, 75 y 80, archivados a mano por Sergio: 0 contactos «Seges E3%» activos |
| 2 | **Archivo de estado del script.** `pruebas_e3p_lab.py` guarda y lee los ids en una ruta fija, `~/lab_e3p/estado_e3p.json`, **aunque se ejecute desde otra carpeta**. Hoy tiene los ids del laboratorio (compañía 3; contactos 70 a 73; páginas 9, 12 y 14). Sin cambiar el script: antes del paso 1, `mv ~/lab_e3p/estado_e3p.json ~/lab_e3p/estado_e3p_lab_3010.json`; tras el paso 1, `mv ~/lab_e3p/estado_e3p.json ~/lab_e3p/estado_e3p_lab_paso1.json`; y en el staging, al terminar D.3, `mv ~/lab_e3p/estado_e3p.json ~/staging_e3p/estado_e3p_staging.json` | Con un estado viejo, `limpiar` borraría en `pns_demo` las páginas y contactos con los ids del laboratorio (el AI Administrator puede borrar cualquier página) y `preparar` solo sobrescribe parte de las claves | `test ! -e ~/lab_e3p/estado_e3p.json && echo libre` antes del `preparar` del staging. La alternativa con cambio de código (una variable `E3P_STATE`) la decide Sergio; no se propone para esta subida | [x] 03/11/2026: el estado del 30/10, en `~/lab_e3p/estado_e3p_lab_3010.json`; el del paso 1, en `~/lab_e3p/estado_e3p_lab_paso1.json`; ruta libre |

**Script de pruebas** ([`scripts_e3/pruebas_e3p_lab.py`](scripts_e3/pruebas_e3p_lab.py), leído el
03/11/2026; `limpiar` corregido el mismo día: borra las propiedades de la compañía de prueba y se puede repetir):
- **Variables:** `E3P_URL` (por defecto `http://localhost:8169`), `E3P_DB` (por defecto
  `lab_pns_ai_3879_14`) y `E3P_SESSION` (sesión de `admin` para P-8c y la carcasa). **Apunta por defecto al
  laboratorio:** en el staging, siempre `E3P_URL=https://pns.liyben.com` y `E3P_DB=pns_demo`. Las admite sin
  cambios (las lee de `os.environ`).
- **Contraseñas:** las pide con `getpass` (las de `admin`, `demo` y, en `http`, otra vez la de `admin`), no
  por variables. No hay claves MCP: el script usa XML-RPC y `/web/session/authenticate`.
- **Qué imprime:** estados, ids, la última línea de cada error (hasta 220 caracteres), el `repr` de lo
  devuelto (hasta 120: `True`, ids, o nombre y dueño de su propia página de prueba en P-8h7), la cabecera
  `X-Frame-Options` y si lo servido empieza por el prefijo CSP. **No lee proveedores, parámetros ni claves y
  no imprime nada que pueda ser un secreto en el staging.** La URL sí sale (`Abrir en el navegador: …`).
- **Logins fijos:** `admin`, `demo` y `portal` (A.8). **Archivo de estado fijo** (paso previo 2).
- **Escribe en `pns_demo`:** `preparar` crea la compañía «Seges E3 otra», cuatro contactos «Seges E3 …» y
  cambia las compañías de `admin` (se la añade y se la quita); `rpc` crea páginas «Seges E3 P-8h …» y una
  de `demo` compartida con `admin`; `http` crea la página «Seges E3 P-8e b»; `limpiar` lo borra (y, para borrar las `ir.property` de la
  compañía, crea, ejecuta y borra una acción de servidor «Seges E3 limpiar propiedades»). Si
  `preparar` se corta, `admin` puede quedarse con la compañía: lo comprueba D.3.

**Carpeta de trabajo en el equipo de Sergio:** `~/staging_e3p`, fuera del repo. Nada se copia al VPS salvo,
con la opción A de A.6, `medir_data_ilegible.py` a `/tmp`.

```sh
mkdir -p ~/staging_e3p
cp ~/GitHub/third_party/docs/pendiente/scripts_e3/pruebas_e3p_lab.py ~/GitHub/third_party/docs/pendiente/scripts_e3/medir_data_ilegible.py ~/staging_e3p/
cd ~/staging_e3p && sha256sum pruebas_e3p_lab.py medir_data_ilegible.py
# esperado: c433305c…32e2 y 05af0d60…f16e
test ! -e ~/lab_e3p/estado_e3p.json && echo libre
export E3P_URL=https://pns.liyben.com E3P_DB=pns_demo
# E3P_SESSION, después de R-vis (D.2): export E3P_SESSION=<id de la sesión de ADM de la primera página>
# Al terminar D.3:
#   unset E3P_URL E3P_DB E3P_SESSION
```

`E3P_SESSION` se asigna directamente, sin `read` (con órdenes pegadas detrás, `read` toma la línea pegada
como respuesta; [lab_p29_3879.md](lab_p29_3879.md), 0.1). Lo mismo en el VPS, para `e3sql`.

**Pasos en la interfaz (Sergio):**

1. **«Design» en los tres Gemini** (AI Engine → Providers), sin quitar «Conversación». Después, la consulta
   de A.7: los tres con `fit_conversation` y `fit_design` en `t`. Se anota qué tenían antes (A.7).
2. **ADM:** AI Conversational (desde la ficha del usuario, no con la casilla de Usuarios MCP: fallo de E2′) y
   clave MCP temporal para Chatboo, si A.8 no los muestra ya.
3. **`demo` y `portal`, solo si A.8 no los muestra** (decisión de Sergio del 03/11/2026). Desde la interfaz
   (Ajustes → Usuarios y compañías → Usuarios → Crear):
   - `demo`: nombre «E3p demo» (sin el prefijo «Seges E3», para no entrar en la página de 5b), login `demo`, «Tipo de usuario» Usuario interno, sin grupos de IA;
     guardar y «Acción → Cambiar contraseña» con una contraseña nueva solo para la prueba (la pide el paso
     `rpc`). Basta con el grupo de usuario interno: `chatboo.canvas.page` da acceso a `base.group_user`
     (`ir.model.access.csv`, línea 4).
   - `portal`: nombre «E3p portal rpc», login `portal`, «Tipo de usuario» Portal; sin contraseña (el
     script solo lee su id).
   - Con un login sin `@` no se envía invitación (paso 4). Se anota cuáles se han creado: son los que D.3
     archiva. Si ya existían, no se tocan (salvo, si hiciera falta, la contraseña de `demo`, que es un
     cambio de datos que decide Sergio).
4. **PT, usuario de portal temporal.** Desde la interfaz (Ajustes → Usuarios y compañías → Usuarios →
   Crear): nombre «Seges E3 portal», login `e3p_portal` (**sin `@`**), «Tipo de usuario» Portal; guardar;
   «Acción → Cambiar contraseña» con una contraseña nueva solo para la prueba. Con un login que no es un
   correo, Odoo no rellena el correo y `auth_signup` no envía la invitación (`res_users.py` de
   `auth_signup`, `create`: solo invita a usuarios con correo; comprobado en el código de 14.0, no en el
   staging).
5. **PT entra en el portal y edita su ficha.** En una **ventana privada**, entrar como `e3p_portal`, ir a «Mi
   cuenta» y guardar con la ciudad:
   ```
   Seges E3 portal </script><script>alert('P-portal')</script>
   ```
   El formulario de Odoo 14 exige nombre, teléfono, correo, calle, ciudad y país
   (`MANDATORY_BILLING_FIELDS`, `portal/controllers/portal.py:138`), y un contacto nuevo no los tiene: se
   rellenan con valores de prueba (por ejemplo, correo `e3p_portal@example.com`, teléfono `000`, calle
   «Seges E3», país España). Comprobación **[LECTURA]** (la de [lab_p29_3879.md](lab_p29_3879.md),
   apartado 3, con el login de PT):
   ```bash
   e3sql <<'SQL'
   SELECT u.id AS usuario, p.id AS contacto, p.name, p.city, p.write_uid
     FROM res_users u JOIN res_partner p ON p.id = u.partner_id WHERE u.login = 'e3p_portal';
   SQL
   ```
   Esperado: la ciudad guardada tal cual y `write_uid` = el id de PT (lo escribió él, no `admin`). Se anotan
   el usuario y el contacto de PT (`<id del contacto del portal>` en 5c).

**Línea base** (después de D.0 y antes de R8), **[LECTURA]** (validada en el laboratorio el 03/11/2026):

```bash
e3sql <<'SQL'
SELECT 'sesiones' AS que, count(*) FROM chatboo_session
UNION ALL SELECT 'paginas', count(*) FROM chatboo_canvas_page
UNION ALL SELECT 'ai_log', count(*) FROM ai_log
UNION ALL SELECT 'companias_de_admin', count(*) FROM res_company_users_rel WHERE user_id = 2;
SQL
```

`companias_de_admin` es el «antes» de D.3 (`preparar` y `limpiar` añaden y quitan una compañía a `admin`).

### D.1 Pruebas de seguridad

`<reinicio>` es la hora de B.8. Las consultas que filtran por `user_id = 2` miran las sesiones de `admin`.
**Consulta C** (de [lab_p29_3879.md](lab_p29_3879.md), 0.1, tal cual; se cambia `E3P_SESSION` delante para
otra sesión):

```bash
e3sql <<'SQL'
SELECT id, canvas_rev,
       position('</script><script>alert' IN canvas_design) > 0 AS cierra_script,
       position('<!--<script>' IN canvas_design) > 0 AS comentario,
       position(chr(92) || 'u003c/script' || chr(92) || 'u003e' || chr(92) || 'u003cscript' || chr(92) || 'u003ealert' IN canvas_design) > 0 AS escapado,
       position(chr(92) || 'u003c!--' || chr(92) || 'u003cscript' || chr(92) || 'u003e' IN canvas_design) > 0 AS comentario_escapado,
       position('pns-page-rows-visible' IN canvas_design) > 0 AS rescate,
       position('th{background:#eef1f7}' IN canvas_design) > 0 AS pagina_rescate
  FROM chatboo_session WHERE id = :sesion;
SQL
```

**Consulta de `ai_log`** (de [lab_p29_3879.md](lab_p29_3879.md), apartado 6, tal cual). **Ventana de 15
minutos:** se lanza justo después de cada prueba; para revisar después, se cambia
`now() - interval '15 minutes'` por `'<reinicio>'` (o por la hora de la prueba, en UTC):

```bash
e3sql <<'SQL'
SELECT id, create_date,
       left(regexp_replace(coalesce(user_prompt, ''), '[[:space:]]+', ' ', 'g'), 50) AS peticion,
       left(regexp_replace(coalesce(result_summary, ''), '[[:space:]]+', ' ', 'g'), 140) AS resumen,
       position('</script><script>alert' IN coalesce(result_data, '') || coalesce(result_summary, '')) > 0 AS crudo
  FROM ai_log
 WHERE create_date > now() - interval '15 minutes'
   AND ((result_summary ILIKE 'Design %')
        OR (result_summary ILIKE 'No page was built%')
        OR (user_prompt ILIKE '%Lay out the tables of one chat answer as a page%'))
 ORDER BY id;
SQL
```

**Qué modelo diseñó** (validada en el laboratorio el 03/11/2026 con las filas 666, 669, 718 y 738:
`provider_id` y `model_name` salen rellenos, «Gemini 3.5 flash lite» y `models/gemini-3.5-flash-lite`). En las
filas del camino del fulfill (666 y 669) `result_summary` es la respuesta de Design, así que `resumen`
muestra los 60 primeros caracteres del HTML (el doctype y el `<html>`), no un texto «Design …». Con los ids
de la consulta anterior:

```bash
e3sql <<'SQL'
SELECT l.id, l.create_date, p.name AS proveedor, l.model_name,
       left(regexp_replace(coalesce(l.result_summary, ''), '[[:space:]]+', ' ', 'g'), 60) AS resumen
  FROM ai_log l LEFT JOIN ai_provider p ON p.id = l.provider_id
 WHERE l.id = ANY ('{<ids de ai_log>}'::int[]) ORDER BY l.id;
SQL
```

**Avisos para todas las ediciones (de [lab_p29_3879.md](lab_p29_3879.md)):**
- El chat puede afirmar un cambio que el servidor ha rechazado («He actualizado el color de fondo…»). **Se
  juzga por `canvas_rev`, `canvas_design` (consulta C) y `ai_log`, no por la alerta ni por lo que dice el
  chat.**
- Con peticiones cortas («pon el fondo azul») el orquestador puede reinterpretarlas como una página nueva.
  Por eso 6b y 6d′ usan el mensaje acotado: «Cambia solo el color de fondo de esta página a azul, sin
  volver a consultar datos ni cambiar nada más».
- Un 503 o un 429 del proveedor: repetir unos minutos después.

| # | Prueba (parche) | Quién | Qué se hace | Esperado | Obtenido |
|---|---|---|---|---|---|
| 1 | **P-8c** (parche 25) | ADM y DEMO, script, paso `rpc` (`cd ~/staging_e3p && python3 pruebas_e3p_lab.py rpc`, con `E3P_SESSION` de R-vis, la sesión de ADM) | Casos P-8c1 a P-8c4 de [lab_e3_3879.md](lab_e3_3879.md), §4 | P-8c1 y P-8c3: `AttributeError` (el método no existe); P-8c2: «Private methods (such as _paint_canvas) cannot be called remotely.»; P-8c4: `canvas_rev` igual antes y después | [x] OK (por el túnel, G): P-8c1 y P-8c3, «method 'paint_canvas' does not exist»; P-8c2, «Private methods…»; P-8c4, `canvas_rev` 1 antes y después (sesión 50) |
| 2 | **P-8h** (parche 28), RPC | ADM y DEMO, mismo paso `rpc` | Casos P-8h1 a P-8h11 de [lab_e3_3879.md](lab_e3_3879.md), §5 | Los de esa tabla: P-8h2 y P-8h6, «Only the system can change the owner of a shared page.»; P-8h3, «A page can only be shared with internal users.»; P-8h8 a P-8h10, `AccessError`; el resto, `ok`. El script imprime una página de `admin` y otra de `demo` compartida con `admin` | [x] OK, 11/11: P-8h2 y P-8h6, «Only the system can change the owner…»; P-8h3, «…internal users.»; P-8h8 a P-8h10, denegados; el resto, `ok`. Página 1 (de `admin`) y página 4 (de `demo`, compartida con `admin`) |
| 2b | **P-8h** (parche 28), interfaz | ADM, navegador | AI › Security › Shared pages, como en [lab_e3_3879.md](lab_e3_3879.md), §5: en la página de `demo`, «Open page», «Stop sharing» y cambiar el título; en la de `admin`, «Stop sharing». Después, la consulta de §5 (abajo) | Página de `demo`: abre la carcasa; «Stop sharing» y guardar el título dan acceso denegado (el formulario **parece** editable: decisión 4). Página de `admin`: «Stop sharing» funciona. En la consulta, ningún `owner_id` cambiado y ningún lector con el id de `portal` (A.8) | [x] OK: la página 4 abre, y «Stop sharing» y cambiar el título se deniegan; en la página 1, «Stop sharing» funciona. Consulta: la 1 sin lectores, la 4 con dueño 6 y lector 2; ningún lector 7 |
| 3 | **P-8d** (parche 26) | ADM, Chatboo, **conversación nueva** (no la de `E3P_SESSION`: el paso `http` la usa con su diseño real) | Con los ids que imprimió `preparar` (o la consulta de §6 de [lab_e3_3879.md](lab_e3_3879.md)): «Llama a page_url con estas filas, exactamente así, sin buscar nada: [{"nombre": "Seges E3 foto", "foto": "/web/image/res.partner/&lt;id oculto&gt;/image_128"}]». Después, la consulta de §6 con `E3P_SESSION` = esa sesión. **Control:** lo mismo con el id del visible | Oculto: `canvas_rev` sube y `con_imagen` = `f` (la ruta queda como texto). Visible: `con_imagen` = `t` y la foto se ve. Si el modelo no llama a `page_url` con esas filas, no concluyente (lo cubren `test_page_url_hidden_picture` y `test_page_html_hidden_picture`) | [x] OK. Oculto (03/11): sesión 51, `canvas_rev` 1, `con_imagen` f y `con_ruta` t (la tarjeta de `lite` muestra «[object Object]»). Visible: la sesión 52 (03/11) no fue concluyente (los tres Gemini fallaron por cuota); repetido el 04/11 en la sesión 53: `canvas_rev` 1, `con_imagen` t y `con_ruta` f, tarjeta y foto correctas; Gemini 3.6 flash (fila 1636, 41 s) |
| 4 | **P-8e a** (parches 27 a y 29), 5a, 5b y 5c | ADM, Chatboo, F12 abierto, **tres conversaciones nuevas** | 5a: «Haz una página con el contacto cuyo id es &lt;id del primer contacto de `P-8e a: contactos`&gt;, con su id y su nombre» (el que lleva `</script>`; en el laboratorio, el 71). 5b: «Haz una página con los contactos cuyo nombre empieza por "Seges E3", con su nombre y su id» (los dos hostiles). 5c: «Haz una página con el contacto cuyo id es &lt;id del contacto del portal&gt;, con su id, su nombre y su ciudad» (PT, D.0). Después, la consulta de abajo | En ninguna salta una alerta. En las tres: `cierra_script = f` y `comentario = f`; `escapado = t` cuando el valor hostil está en la página; `comentario_escapado = t` en 5b. Las tres combinaciones de `rescate` / `pagina_rescate` (`t t`, `t f`, `f f`) son correctas ([lab_p29_3879.md](lab_p29_3879.md), apartado 5). Se anota qué modelo diseñó cada una | [x] OK, sin alerta ni avisos en ninguna (04/11). Columnas: `cierra_script`, `comentario`, `escapado`, `comentario_escapado`; `rescate`, `pagina_rescate`. **5a** (contacto 63, sesión 54): f f t f; f f; 3.6 flash (fila 1642, 25 s). **5b** (sesión 55): f f t t; f f; 3.6 flash (fila 1648, 48 s); se ven 59, 60, 62, 63 y 64, no el 61 (oculto). **5c** (contacto 59 de PT, sesión 56): f f t f; f f; diseñó 3.5 flash (fila 1655, 84 s) tras un failover de 3.6 flash (fila 1654; HTTP 503 según el log de Odoo a las 11:12:23, `ai_log` no guarda el detalle). El `crudo` = t de las filas «Execution successful» (1643, 1649 y 1656) es el resultado de la herramienta de datos, no lo guardado; en las filas de Design, `crudo` f |
| 5 | **6c** (parche 29, camino del fulfill) | ADM, en la conversación de 5b | «rehaz la tabla como tarjetas»; después, consulta C (`E3P_SESSION` = la de 5b) y la de `ai_log` (columna `crudo`) | `canvas_rev` sube y `cierra_script = f`; `pagina_rescate` puede ser `t` si Design copió los valores. `crudo = t` en una fila de Design con la página guardada con `cierra_script = f`: Design copió el valor y el parche 29 lo frenó | [x] Conforme: sesión 55, `canvas_rev` 2; f f t t; f f. Design 1661 («changed the page», 30 s) y 1662 («laid out the page again», 35 s), las dos con `crudo` f: Design no copió los valores en crudo, así que el freno del parche 29 no se vio actuar en este camino (cubierto en [lab_p29_3879.md](lab_p29_3879.md), 6c). 3.6 flash; la página, como tarjetas, sin avisos |
| 6 | **6d′** (parche 29, caso 2 de B1) | ADM, solo si A.6 dio una sesión candidata **y su dueño puede usarla** | Mensaje acotado sobre esa sesión (como dueño); antes, `e3medir` (solo lectura) para confirmar que sigue ilegible. Después, consulta C y `ai_log` | **Se rechaza:** `canvas_rev` no cambia y `ai_log` dice `No page was built: the change left a value of the page as markup`. Otros desenlaces correctos, los de [lab_p29_3879.md](lab_p29_3879.md), 6d. **Si A.6 no dio candidata: «no aplica»** (cubierto por el laboratorio, 6d′, y por `test_edit_page_without_data`) | [x] No aplica: A.6 sin ilegibles |
| 7 | **6e** (parche 27 a) | ADM | Crear en Contactos `Seges E3 "P29"` (con comillas dobles) y pedir en una conversación nueva una página con ese contacto por id; consulta C | El nombre se ve igual, con sus comillas, en el diseño o en el rescate; `cierra_script = f` | [x] OK: contacto 65, sesión 57, `canvas_rev` 1, `cierra_script` f, `rescate` / `pagina_rescate` f f; el nombre se ve con sus comillas. 3.6 flash (fila 1671, 110 s). En la fila 1668, «AST Validation Error: [PROHIBITED:DIR]»: el código del modelo usó `dir()`, el validador lo rechazó y se corrigió en la segunda ronda |
| 8 | **P-8e b y `X-Frame-Options`** (parches 27 b y d) | ADM, script, paso `http` (`python3 pruebas_e3p_lab.py http`, con `E3P_SESSION` de R-vis), y navegador | Rutas y pasos de [lab_e3_3879.md](lab_e3_3879.md), §8, con `https://pns.liyben.com`. Cabeceras a mano (opcional): el `curl` de §8 con la URL del staging y la cookie con `read -rsp` y `unset` | `/chatboo/canvas/<E3P_SESSION>` y `/chatboo/page/<id>`: HTTP 200, `X-Frame-Options: SAMEORIGIN`, prefijo CSP `True`. Las dos descargas: HTTP 200, `X-Frame-Options: None`, prefijo CSP `True`. En el navegador: «script en linea: ok», imagen externa rota, avisos «Refused to load…» y «Refused to connect…», peticiones a `example.com` bloqueadas por CSP; la página de `E3P_SESSION` (R-vis), sin esos avisos | [x] OK (P-8e b conforme), con una desviación sin efecto en la seguridad. Página 5 (`page_net` 5 en el estado). `/chatboo/canvas/50`, `/chatboo/page/5`, `/chatboo/page/5/download` y `/chatboo/canvas/50/download`: HTTP 200, prefijo CSP `True` y `X-Frame-Options: SAMEORIGIN` en las cuatro. **Desviación:** en las descargas, `X-Frame-Options: SAMEORIGIN` lo pone Nginx por la URL pública (`pns_liyben_com.conf` l. 11). Que Odoo no la pone en las descargas se comprueba en el código de `522ce6e` (solo en `chatboo_canvas`, `chatboo.py` l. 1157, y `chatboo_shared_page`, l. 1250); por el túnel, solo que Odoo no la pone en `/mcp` (405 sin `X-Frame-Options`, frente a 403 con ella por la URL pública). Navegador (Firefox): «script en linea: ok», imagen externa rota; en la consola, «La configuración de la página bloqueó…» en `style-src-elem` ×2 (`example.com/seges-e3.css` y `seges-e3-font.css`), `img-src` (`seges-e3.png`) y `connect-src` ×2, y «Uncaught (in promise) TypeError: NetworkError» (consecuencia del bloqueo); además, 2 avisos de mapeo de fuente de `about:srcdoc` de las herramientas de Firefox (irrelevantes). La página de la sesión 50, sin esos avisos |
| 9 | **6b** (parche 29, caso 1 de B1) | ADM, en la sesión `E3P_SESSION` (R-vis), **al final** (después del paso `http`) | Mensaje acotado; consulta C y `ai_log` | `canvas_rev` sube; las cifras no cambian; `pagina_rescate = f` (`rescate` puede ser `t`) | [x] OK: sesión 50, `canvas_rev` 1 → 2; `pagina_rescate` f y el resto f; mismas cifras (2 registros, total 907500; Deco Addict 590000 y Azure Interior 317500); fondo azul. 3.6 flash: Design 1677 («changed the page in 10 s»; respuesta de Design de 104 caracteres, según `ai_log`) y 1678 («laid out the page again», 40 s). `relaxaicode` (fila 1676) llamado aunque el mensaje pedía no consultar datos; ninguna «No page was built» |

**Consulta de P-8e a** (de [lab_p29_3879.md](lab_p29_3879.md), apartado 5, tal cual; `<reinicio>` con la
forma `2026-11-04 10:57:35`). Saca las sesiones de `admin` con lienzo creadas después del reinicio:

```bash
e3sql <<'SQL'
SELECT id, canvas_rev, create_date,
       position('</script><script>alert' IN canvas_design) > 0 AS cierra_script,
       position('<!--<script>' IN canvas_design) > 0 AS comentario,
       position(chr(92) || 'u003c/script' || chr(92) || 'u003e' || chr(92) || 'u003cscript' || chr(92) || 'u003ealert' IN canvas_design) > 0 AS escapado,
       position(chr(92) || 'u003c!--' || chr(92) || 'u003cscript' || chr(92) || 'u003e' IN canvas_design) > 0 AS comentario_escapado,
       position('pns-page-rows-visible' IN canvas_design) > 0 AS rescate,
       position('th{background:#eef1f7}' IN canvas_design) > 0 AS pagina_rescate
  FROM chatboo_session
 WHERE user_id = 2 AND create_date > '<reinicio>' AND canvas_design IS NOT NULL
 ORDER BY id;
SQL
```

**Consulta de P-8d** (de [lab_e3_3879.md](lab_e3_3879.md), §6, tal cual):

```bash
e3sql <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT id, name, company_id FROM res_partner WHERE name LIKE 'Seges E3 foto%' ORDER BY id;
-- el oculto es el que tiene company_id (la compañía «Seges E3 otra»)
ROLLBACK;
SQL
E3P_SESSION=<id de la sesión de P-8d> e3sql <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT id, canvas_rev, position('data:image' IN canvas_design) > 0 AS con_imagen,
       position('/web/image/res.partner/' IN canvas_design) > 0 AS con_ruta
  FROM chatboo_session WHERE id = :sesion;
-- esperado tras el oculto: canvas_rev sube, con_imagen = f (la ruta se queda como texto)
ROLLBACK;
SQL
```

**Consulta de P-8h** (de [lab_e3_3879.md](lab_e3_3879.md), §5; solo cambia el comentario: el lector
prohibido es el id de `portal` de A.8, no el 7 del laboratorio):

```bash
e3sql <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT p.id, p.name, p.owner_id, array_agg(r.user_id ORDER BY r.user_id) AS lectores
  FROM chatboo_canvas_page p LEFT JOIN chatboo_canvas_page_user_rel r ON r.page_id = p.id
 WHERE p.name LIKE 'Seges E3%' GROUP BY p.id ORDER BY p.id;
-- esperado: ningún owner_id cambiado; ningún lector con el id de portal de A.8
ROLLBACK;
SQL
```

**No se repiten aquí:** las pruebas «antes del parche» (decisión de Sergio) y el caso 3 de B1 (página sin
tabla ni `DATA`), que no se puede provocar desde el chat (`test_edit_page_without_data`).

### D.2 No regresión (con los proveedores de A.7)

| # | Caso | Quién | Esperado | Obtenido |
|---|---|---|---|---|
| R8 | **Lienzo desde el chat** (cierra la R8 que E1′ dejó para E3′). Conversación nueva: «Hazme una página con las ventas por mes de este año, con un gráfico de barras y una tabla». Consultas de [lab_e3_3879.md](lab_e3_3879.md), §1 (abajo, con el id de U1), y «Qué modelo diseñó». **Hace también de 6a**, para ahorrar cuota: consulta C sobre esa sesión, con `E3P_SESSION=<id de la sesión de R8> e3sql` solo para esa orden (la sesión de R8 **no** es `E3P_SESSION`) | U1 | La burbuja trae la tarjeta de la página y al abrirla se ven el gráfico y la tabla; la sesión con `canvas_open = t` y `canvas_rev >= 1`; en `ai_log`, «Design laid out the page in … s» y ninguna «No page was built: the design call broke: AccessError». Como 6a: `pagina_rescate = f` (`rescate` puede ser `t`). **Se anota el modelo.** Si la diseña `lite` y no se crea: no concluyente por el proveedor (PNS-96) | [x] OK (03/11): sesión 49 de U1, `canvas_open` t (consulta del 04/11) y `canvas_rev` 1; `ai_log` 1591, «Design laid out the page in 9 s»; diseñó `lite` y la página se creó (correcta en R-vis). Como 6a: todo f (`rescate` y `pagina_rescate` incluidos). Cierra la R8 de E1′ |
| R-vis | **Comprobación visual con la CSP** ([lab_e3_3879.md](lab_e3_3879.md), §2): una o dos páginas, cada una en una conversación nueva («página con los clientes y su facturación», «página con las facturas pendientes por cliente»), al menos una con gráfico. **La sesión de la primera es `E3P_SESSION`** (se saca con la consulta de R8 con `user_id = 2`), en el VPS y en `~/staging_e3p`. La página de R8 la revisa U1 con los mismos puntos | ADM, navegador | Se ven completas; tema e «Imprimir / PDF» funcionan; consola sin avisos de CSP de la propia página (si sale alguno, anotar el host); «Descargar HTML» se ve igual, empieza por el prefijo CSP y `document.compatMode` da `"CSS1Compat"`. Si una página se ve distinta (de quirks a estándar), anotarlo: coste aceptado del parche 27 b | [x] OK: una página, la de ADM en la sesión 50 (`E3P_SESSION`), diseñada por `lite` (fila 1605). Páginas de las sesiones 49 (U1) y 50 correctas: tema, «Imprimir / PDF», consola sin avisos de CSP y descarga en `CSS1Compat` |
| R-desc | **Descargas del lienzo:** «Descargar HTML» del lienzo (`/chatboo/canvas/<id>/download`) y de una página compartida (`/chatboo/page/<id>/download`) | ADM | Las dos descargan y abren en local con la CSP (complementa la fila 8 de D.1). La del lienzo se nombra con la sesión, no con la página (observación del laboratorio, ya conocida) | [x] OK: descargas del lienzo 50 y de la página 1, abiertas en local, correctas |
| R-log | **Log desde el arranque** (B.8), con la orden de abajo | — | Solo errores del proveedor (429/503) y los rechazos provocados en D.1 (`rpc`: P-8c y P-8h), a su hora. Qué rechazos de RPC deja Odoo en el log como `ERROR` es **«Sin confirmar»**: se anotan con su hora y se cotejan con las pruebas | [x] OK, desde 2026-11-03T16:27:50Z: 26 líneas `ERROR` y 16 `Traceback`, de tres tipos: 429 de Gemini (03/11, 16:34 a 17:16), 503 de Gemini (03/11 17:16 y 04/11 11:12:23) y «The method 'paint_canvas' does not exist» ×2 (03/11 17:07:40, P-8c1 y P-8c3). Ninguno inesperado. **Resuelve el «Sin confirmar»:** Odoo solo registra como `ERROR` el método inexistente; P-8c2 y los rechazos de P-8h no salen como `ERROR`. Las URLs del log no llevan la clave |

**Orden de R-log** **[LECTURA]**, con la hora de `docker inspect` de B.8 tal como sale (formato RFC 3339):

```bash
cd /opt/odoo/pns_staging && docker compose logs --since '<StartedAt de B.8>' web 2>&1 | grep -E 'Traceback|ERROR|CRITICAL'
```

**Consulta de R8** (de [lab_e3_3879.md](lab_e3_3879.md), §1; solo cambia el usuario: el id de U1 de A.8.
Con `user_id = 2` da la sesión de ADM de R-vis, `E3P_SESSION`):

```bash
e3sql <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT id, user_id, canvas_open, canvas_rev, length(canvas_design) AS largo
  FROM chatboo_session WHERE user_id = <id de U1 de A.8> ORDER BY id DESC LIMIT 3;
-- esperado: la sesión del turno con canvas_open = t y canvas_rev >= 1
SELECT id, create_date, result_summary FROM ai_log
 WHERE result_summary ILIKE 'Design %' OR result_summary ILIKE 'No page was built%'
 ORDER BY id DESC LIMIT 5;
-- esperado: «Design laid out the page in … s»; ninguna «No page was built: the design call broke: AccessError»
ROLLBACK;
SQL
```

### D.2b Medición después de las pruebas

**[LECTURA]** Lo mismo que A.6 (`e3medir` con la opción que se usó, la consulta de dueños y m3), guardando en
`/tmp/pns_e3p_medir_despues.txt` o `~/staging_e3p/medir_despues.txt`.

| Medición (después) | Esperado | Obtenido |
|---|---|---|
| `chatboo.session`: ilegibles | Los de A.6 (salvo si 6d′ sustituyó alguno por otra página) y **ninguna** de las sesiones creadas después del reinicio | [x] OK: 8 con diseño, 0 ilegibles (`/tmp/pns_e3p_medir_despues.txt`). Los 8 lienzos los crearon las pruebas (sesiones 49, 50, 51 y 53 a 57) |
| `chatboo.canvas.page`: ilegibles | Los de A.6 | [x] OK: 3 con diseño (páginas 1, 4 y 5, de las pruebas), 0 ilegibles |
| Lectores de portal guardados (m3) | El número de A.6 (el parche no limpia los guardados; impide guardar nuevos) | [x] OK: 0, como en A.6 |

### D.3 Limpieza de las pruebas

**[ALTERA]** Mínima, porque la limpieza general es al final de todos los cambios. Lo que se deshace es lo que
falsearía las pruebas siguientes (sobre todo los valores hostiles):
- **Datos de `preparar`:** `cd ~/staging_e3p && python3 pruebas_e3p_lab.py limpiar`. Esperado: `páginas
  ('ok', True)`, `admin con la compañía ok`, `contactos ('ok', True)`, `propiedades ok N` (N ≥ 1),
  `acción temporal ('ok', True)`, `admin sin la compañía ok` y `compañía ('ok', True)` (o el error que
  diga qué la usa). Las `ir.property` de la compañía se borran antes que ella: si no, el borrado deja
  huérfana la propiedad de la tarifa que Odoo le creó (o choca con `ir_property_unique_index` si ya hay
  una huérfana igual; [lab_e3_3879.md](lab_e3_3879.md), apartado 9). Si se repite, `ya borradas` o
  `ya borrados` en lo que no quede, y `compañía ya borrada` si ya no existe.
  **Después de `limpiar`, archivar a mano** (como ADM, en Contactos) el contacto «Seges E3 otra» que
  `res.company.create` crea con la compañía: `limpiar` no lo borra ni Odoo lo borra con ella (en el
  laboratorio, el 03/11/2026, quedaron así el 68, el 75 y el 80). Sin archivarlo, la comprobación final da
  1 contacto en vez de 0. Y el archivo de estado, a `~/staging_e3p` (D.0, paso previo 2).
- **PT:** como ADM, en Contactos, **vaciar la ciudad** de su contacto (es un valor hostil), archivar el
  usuario `e3p_portal` y archivar su contacto.
- **6e:** archivar el contacto `Seges E3 "P29"`.
- **`demo` y `portal` temporales** (solo los que se crearon en D.0, paso 3): archivar el usuario y su
  contacto. Los que ya existían en `pns_demo` no se tocan.
- **Claves:** revocar la clave MCP temporal de ADM. Si se le añadió AI Conversational para la prueba, se
  deja anotado (se quita en la limpieza general o cuando Sergio decida).
- **Se quedan:** las sesiones de chat de las pruebas (las de después del reinicio, con los valores hostiles
  escapados), las páginas reales de R8 y de la comprobación visual, y las casillas «Design» de los tres
  Gemini (configuración del staging; la de `lite` es la excepción de esta subida, se revisa en E4′).

**[LECTURA]** Comprobación final (la de [lab_p29_3879.md](lab_p29_3879.md), apartado 8, tal cual, y otra para
PT, los temporales `demo` y `portal`, la compañía de `admin` y la clave; las dos, validadas en el laboratorio
el 03/11/2026):

```bash
e3sql <<'SQL'
SELECT 'pagina' AS que, count(*) FROM chatboo_canvas_page WHERE name LIKE 'Seges E3%'
UNION ALL SELECT 'contacto', count(*) FROM res_partner WHERE name LIKE 'Seges E3%' AND active
UNION ALL SELECT 'compañía', count(*) FROM res_company WHERE name LIKE 'Seges E3%';
SQL
e3sql <<'SQL'
SELECT u.id, u.login, u.active, p.active AS contacto_activo, coalesce(p.city, '') = '' AS ciudad_vacia
  FROM res_users u JOIN res_partner p ON p.id = u.partner_id
 WHERE left(u.login, 4) = 'e3p_' OR u.login IN ('demo', 'portal') ORDER BY u.id;
SELECT count(*) AS companias_de_admin FROM res_company_users_rel WHERE user_id = 2;
SELECT m.id, u.login, m.mcp_api_key_state, coalesce(m.mcp_api_key_hash, '') <> '' AS tiene_hash
  FROM ai_mcp_user m JOIN res_users u ON u.id = m.user_id WHERE u.login = 'admin';
SQL
```

Esperado: **0 / 0 / 0** (con los archivados hechos); PT archivado, con el contacto archivado y la ciudad
vacía; `demo` y `portal` archivados si se crearon en D.0 e iguales que en A.8 si ya existían; `admin` con las mismas compañías que antes de `preparar` (se anota el número antes, en D.0); la clave
de `admin` en `not_generated` y sin hash. Resultado en la [verificación](verificacion_seguridad_pns_ai.md), en
un bloque nuevo «Staging — entrega E3′».

---

## E. Vuelta atrás (descrita, no lista para pegar)

Operaciones que cambian el VPS: las decide y hace quien administra el VPS.

1. **Antes del `-u` (fallo en B.3 a B.6).** `pns_demo` no ha cambiado. Se devuelve el código de `9a2970d`
   desde `addons_antes_E3p`, con `rsync --delete` módulo a módulo. Se comprueba la huella de A.3 (709,
   `7a6c7144…`) y se arranca `web`.
2. **Después del `-u`.** El `-u` de E3′ no cambia el esquema: ni campos ni versiones. Volver el código a
   `9a2970d` como en el punto 1 **es viable («Sin confirmar»: no ensayado)**, con un matiz: lo que el `-u`
   cambió en `security.xml` (la regla `chatboo_canvas_page_admin_rule` en `t f f t`) **no vuelve con el
   código**; vuelve con un **`-u` de `pns_ai_chatboo` con el código anterior**, que recarga la regla con los
   cuatro permisos (`noupdate="0"`). Sin ese `-u`, el código de E2′ funcionaría con la regla nueva (el AI
   Administrator no podría escribir páginas ajenas), que es más restrictiva. Lo escrito con el código nuevo
   (sesiones y páginas) se queda. Si hay dudas, se corrige hacia delante con un commit nuevo y el mismo
   procedimiento.
3. **`addons_antes_E3p`** se conserva hasta la limpieza final del staging, como las anteriores.

---

## F. Lo que no está documentado

| Dato | Dónde se comprueba |
|---|---|
| `python3` en el host del VPS | A.6 (`python3 --version`); si no hay, opción B |
| `WARNING` del `-u` de `pns_ai_chatboo` | Sin referencia: el laboratorio no anotó los suyos. Se anotan los de B.8 |
| Zona horaria de `odoo14_pns_db` (ventana de 15 minutos) | A.0 (`SHOW TimeZone`) |
| `demo` y `portal` en `pns_demo` (logins fijos del script) | A.8. **Decidido por Sergio (03/11/2026):** si falta alguno, se crea temporal con ese login (D.0, paso 3) y se archiva en D.3 |
| Contraseña de `demo` en `pns_demo` | Sergio. Si `demo` ya existe y hay que ponerle una, es un cambio de datos (D.0) |
| Login e id de U1 (R8) | A.8 (`<login de U1>`) |
| AI Conversational y clave MCP de `admin` para Chatboo | A.8 |
| Ids de los Gemini en `pns_demo` y su casilla «Design» antes de D.0 | A.7 |
| Cuota de Gemini el día de la subida | Consola de Google AI Studio, no solo «Test Connection» (F de E1′) |
| Rechazos de RPC que Odoo deja como `ERROR` en el log | D.2, R-log |
| Envío de invitación al crear PT | D.0, paso 3 (comprobado en el código de 14.0, no en el staging) |
| Pasos previos 1 y 2 de D.0 | Hechos el 03/11/2026 (D.0, columna «Hecho») |
| E4′ | **No entra en esta subida.** Observaciones del laboratorio de E3′ para E4′ o el informe: el chat afirma cambios que no hizo, la muestra de Design con `keys`, tres llamadas a Design por edición, la casilla «Design» en `lite` |

---

## G. Resultado de la subida (03 y 04/11/2026)

Sergio con Claude; horas en UTC. Commit `522ce6e` de `14.0-pns-ai-3879`. A a C y la mayor parte de D, el
03/11/2026; el resto de D y la limpieza, el 04/11/2026. Resultado por prueba en las columnas «Obtenido» de
A.6, C.1, C.2, D.1, D.2 y D.2b; resumen en la [verificación](verificacion_seguridad_pns_ai.md), «Staging —
entrega E3′ (03 y 04/11/2026)».

### A. Comprobaciones previas

- **A.0 a A.5:** como se esperaba, sin cambios respecto al traspaso.
  - A.0: `on` y `UTC`.
  - A.1: `odoo14_pns` y `odoo14_pns_db` en marcha; `POSTGRES_USER` `odoo`.
  - A.2: montajes como en E2′, más el volumen anónimo `/mnt/extra-addons` (`rw=true`) de la imagen oficial,
    que no es un cambio. Copias `addons_antes_E1`, `addons_antes_E2`, `addons_antes_E1p` y
    `addons_antes_E2p`, sin `addons_antes_E3p`. Restos `addons_27cadbb`, `addons_27cadbb_b` y
    `addons_95d6b1a`. Disco al 87 % (9,6 GB libres).
  - A.3: 709 archivos, huella `7a6c7144…bb9f`.
  - A.4: `1.2.47`, `3.1.879` y `2.1.538`; sin `odoo_dev.%`; 7 crons; ninguna transacción en curso.
  - A.5: `t t t t`.
- **A.6 (medición antes):** `python3` 3.12.3 en el host (opción A), script `05af0d60…f16e` en `/tmp`.
  `chatboo.session` 0 con diseño y 0 ilegibles; `chatboo.canvas.page` 0 con diseño y 0 ilegibles
  (`/tmp/pns_e3p_medir_antes.txt`): sin riesgo residual, 6d′ no aplica. m3: 0.
- **A.7:** cadena de Chatboo con Gemini 3.6 flash (1), 3.5 flash (3) y 3.5 flash lite (4). «Design» ya
  estaba en `t` en los tres: el paso 1 de D.0 no hizo falta. Proveedor 2, «Proveedor fuera de cadena»,
  inactivo. «Test Connection» de 3.5 flash: 429.
- **A.8:** U1 = `u1` (id 8, clave `generated`); `admin` con los cinco grupos de IA y clave `not_generated`.
  `demo` (6) y `portal` (7) existían, pero **archivados**: caso no previsto. Decisión de Sergio: desarchivarlos,
  poner a `demo` una contraseña nueva y volver a archivarlos al terminar. Restos «Seges E3»: 0 / 0 / 0.
  Decisión de Sergio: seguir sin comprobar la cuota en la consola de Google AI Studio.

### Antes de B

- **Pasos previos 1 y 2 de D.0:** hechos el 03/11/2026 en el laboratorio (D.0, columna «Hecho»).
- **Commits en los módulos después de `522ce6e`:** 0 (comprobado el 04/11/2026, paso 0).

### B. Despliegue

- **B.1:** huella del archivo `34b1b023…f3d0`.
- **B.2 a B.4:** huella igual en el VPS. 113 marcadores (por parche, 5, 2, 13, 4 y 14); las comprobaciones de
  los cinco parches, conformes; 710 archivos, huella `6ac645fc…44e5`.
- **B.5:** copia en `addons_antes_E3p`, con huella `7a6c7144…`.
- **B.6:** el ensayo no listó bajas. Tras la sustitución, 710 archivos y huella `6ac645fc…`; `diff -rq` de 7
  líneas (6 distintos + 1 nuevo + 0 bajas), todo de `pns_ai_chatboo`.
- **B.7 y B.8 (`-u` de `pns_ai_chatboo`):** 0 errores y 0 «Deleting field». 3 `WARNING` conocidos: la
  etiqueta «Client» de `ai.log` y los dos de `distutils`.
- **Arranque (reinicio):** 2026-11-03 16:27:50 (`StartedAt` 2026-11-03T16:27:50.349009205Z). Log con 0
  errores; `/web/login` 200 y `/mcp` 403.

### C. Comprobaciones posteriores

C.1: `t f f t`. C.2: igual que A.4. C.3: no aplica.

### D. Pruebas

- **D.0 (03/11):** `demo` y `portal` desarchivados; `demo` con contraseña nueva; clave MCP temporal de
  `admin`. PT: usuario `e3p_portal` 26, contacto 59, ciudad hostil con comilla simple guardada, `write_uid`
  26. Línea base: 39 sesiones, 0 páginas, 1576 filas de `ai_log` y `admin` con 1 compañía.
- **`preparar`:** compañía 2, oculto 61, «admin sin la compañía ok», visible 62. Al crear los contactos
  hostiles, Nginx devolvió **503** (`limit_req zone=odoo_login`, 5 r/min con ráfaga 5, en `/xmlrpc` y
  `/web/login`). El script no captura `ProtocolError` y no guardó el estado. Los hostiles 63
  (`</script>…`) y 64 (`<!--<script>`) se crearon a mano en la interfaz y el estado se escribió a mano;
  «admin no ve el oculto», comprobado en la interfaz; el contacto de la compañía es el 60. **Desde entonces,
  `preparar`, `rpc` y `limpiar` se hicieron por un túnel SSH al puerto 8169 del VPS (18169 en local)**, sin
  tocar Nginx ni el script.
- **D.2, R8 (+6a) y R-vis (03/11):** R8, sesión 49 de U1, diseñó `lite` (fila 1591), conforme; 6a todo f.
  R-vis: sesión 50 de `admin` = `E3P_SESSION`, diseñó `lite` (fila 1605); páginas 49 y 50 correctas.
- **D.1 (03/11):** P-8c y P-8h por el túnel, OK (P-8h, 11/11 por RPC y conforme en la interfaz). P-8d
  oculto (sesión 51), OK. P-8d visible (sesión 52), no concluyente: fallaron los tres Gemini por cuota (3.6
  flash con el límite diario gratuito de 20, «retry in 15h» a las 17:01; 3.5 flash, 429; `lite` falló hacia
  las 17:16).
- **Noche del 03/11:** Sergio volvió a archivar `demo` y `portal`.
- **Paso 0 (04/11):** `StartedAt` sin cambios (sin reinicio). Datos íntegros: contactos 59 a 64, compañía 2,
  páginas 1 y 4, sesiones 49 a 52, claves de `admin` y `u1` en `generated`, `admin` con 1 compañía. Último
  `ai_log`, 1632. 0 commits en los módulos después de `522ce6e`. Script del repo y del equipo con
  `c433305c…32e2`; estado con `page_admin` 1 y `page_demo_ui` 4; túnel, 200. **Cuota:** comprobada por el
  uso: 3.6 flash respondió desde la primera prueba (fila 1634); un 503 momentáneo a las 11:12:23 (failover a
  3.5 flash, fila 1654); la consola de AI Studio no se anotó.
- **D.1 (04/11):** todas conformes.
  - P-8d visible: sesión 53, `con_imagen` t; 3.6 flash (fila 1636).
  - P-8e a: 5a (sesión 54), 5b (sesión 55) y 5c (sesión 56), sin alerta ni avisos y con `cierra_script` y
    `comentario` f en las tres; 5c lo diseñó 3.5 flash tras el failover.
  - 6c: sesión 55, `canvas_rev` 2; conforme. Design no copió los valores en crudo, así que el freno del
    parche 29 no se vio actuar en este camino (cubierto en [lab_p29_3879.md](lab_p29_3879.md), 6c).
  - 6d′: no aplica (A.6 sin ilegibles).
  - 6e: contacto 65, sesión 57; conforme.
  - Paso `http`: página 5. HTTP 200, prefijo CSP y `X-Frame-Options: SAMEORIGIN` en las cuatro rutas; en
    las descargas la pone Nginx por la URL pública (D.1, fila 8). P-8e b, conforme en Firefox.
  - 6b: sesión 50, `canvas_rev` 2, mismas cifras y fondo azul; conforme.
- **D.2 (04/11):** R-desc y R-log conformes. R-log resuelve el «Sin confirmar»: solo el método inexistente
  (P-8c1 y P-8c3) sale como `ERROR`.
- **D.2b:** script `05af0d60…f16e`; `chatboo.session` 8 con diseño y 0 ilegibles; `chatboo.canvas.page` 3
  con diseño y 0 ilegibles; lectores de portal 0 (`/tmp/pns_e3p_medir_despues.txt`).
- **D.3 (limpieza, 04/11):**
  - `limpiar` por el túnel: páginas `('ok', True)`, `admin con la compañía ok`, contactos `('ok', True)`,
    `propiedades ok 1`, acción temporal `('ok', True)`, `admin sin la compañía ok` y compañía `('ok', True)`.
  - A mano: archivados el contacto 60, el usuario 26, el contacto 59 y el contacto 65. La ciudad de 59: en
    el primer guardado se sustituyó por «Madrid» (ya sin el valor hostil) y después se vació. Clave MCP de
    `admin` revocada. `demo` y `portal`, archivados desde la noche del 03/11. Estado movido a
    `~/staging_e3p/estado_e3p_staging.json`.
  - Comprobación final: 0 / 0 / 0; `demo` y `portal` inactivos con el contacto activo (como en A.8);
    `e3p_portal` inactivo, con el contacto inactivo y la ciudad vacía; `admin` con 1 compañía; clave de
    `admin` en `not_generated` y sin hash; se conservan las 9 sesiones de prueba (49 a 57).

**Resultado:** E3′ y el parche 29 **validados en el staging `pns_demo`** (parches 25 a 29). R8 de E1′,
cerrada. Desviaciones sin efecto en la seguridad: el `X-Frame-Options` que Nginx añade a las descargas por
la URL pública, y la ciudad de PT corregida en D.3.

### Correcciones del procedimiento

Anotadas aquí; los pasos de A a D no se han cambiado.

- **Límite de Nginx en `/xmlrpc`** (5 r/min, ráfaga 5): `preparar`, `rpc` y `limpiar`, por el túnel SSH
  (18169 en local).
- **`demo` y `portal` archivados:** el documento solo preveía «existen» o «no existen».
- **«Design» ya activa en los tres Gemini** (el paso 1 de D.0 no hizo falta).
- **`E3P_SESSION` también en el VPS:** lo dice D.0, pero no estaba en el paso 0 del traspaso.
- **Confusión de terminales:** las consultas, en el VPS; el script y el `scp`, en el equipo.
- **Cuota:** con el nivel gratuito, unos 13 turnos de diseño no caben en un día si antes se ha usado el
  laboratorio.
- **`X-Frame-Options` en las descargas:** lo añade Nginx en la URL pública; lo que pone Odoo se ve por el
  túnel o en el código.
- **Textos de Firefox:** muestra la CSP como «La configuración de la página bloqueó…» (el documento usa los
  textos de Chrome).
- **D.3, PT:** comprobar `ciudad_vacia`; los contactos archivados se editan con el filtro «Archivado».
- **No repetir el paso `http` para comparar:** crea otra página y sobrescribe `page_net` en el estado.

### Observaciones para E4′

Anotadas también en el [plan de corrección](plan_correccion_pns_ai_3879.md), «E4′ (hoja de Medios y
Bajos)»:

- Toda la tarde del 03/11 diseñó `lite`; el 04/11, 3.6 flash (y 3.5 flash en 5c).
- La tarjeta de `lite` pinta la ruta de P-8d como «[object Object]».
- `pruebas_e3p_lab.py` no resiste un 503: termina sin guardar el estado (valorar capturar
  `xmlrpc.client.ProtocolError` y guardar tras cada creación).
- Dos llamadas a Design por edición (6c y 6b: «changed» y después «laid out again»).
- El chat llama a `relaxaicode` aunque se le pida no consultar datos (6b).
- `ai_log` no guarda el detalle del error del proveedor en el failover (fila 1654); solo está en el log de
  Odoo.
- El validador AST rechaza `dir()` (fila 1668): funciona como debe; se anota por el tiempo extra.
- La casilla «Design» en `lite` (excepción de esta subida).

### Restos para la limpieza final (no se borran ahora)

- **`pns_demo`:** sesiones 49 a 57; contactos archivados 59, 60 y 65; usuario `e3p_portal` (26) archivado;
  casillas «Design» de los tres Gemini.
- **`/opt/odoo/pns_staging`:** `addons_antes_E1`, `addons_antes_E2`, `addons_antes_E1p`, `addons_antes_E2p`
  y `addons_antes_E3p`, y `addons_27cadbb`, `addons_27cadbb_b` y `addons_95d6b1a`. Disco al 87 %.
- **`/tmp` del VPS:** `pns_u_E3p.log`, `pns_diff_E3p.txt`, `pns_e3p_medir_antes.txt`,
  `pns_e3p_medir_despues.txt` y `medir_data_ilegible.py` (se borran después de este [DOC]).
- **`/tmp` del VPS, comprobado con `ls` el 04/11/2026 (no se borran ahora):** siguen los de E1/E1′ y E2′
  anotados en [staging_e2_3879.md](staging_e2_3879.md), «Restos para la limpieza final». Por su nombre:
  `pns_addons_27cadbb.tar.gz`, `pns_addons_63ee2dc.tar.gz` y `pns_addons_95d6b1a.tar.gz` (plan de staging,
  §9, punto 4), `pns_p9_antes_E1p.txt` y `pns_p9_despues_E1p.txt`. `pns_liyben.snip`: no consta qué es;
  **revisar antes de borrar**. Los cinco de E3′ (`pns_u_E3p.log`, `pns_diff_E3p.txt`,
  `pns_e3p_medir_antes.txt`, `pns_e3p_medir_despues.txt` y `medir_data_ilegible.py`) se borraron el
  04/11/2026 a las 16:07 UTC, después del commit `fcbeebd` (`rm -v`; comprobado con `ls`).
