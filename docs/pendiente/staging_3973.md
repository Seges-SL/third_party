# Subida de la rama 3973 al staging `pns_demo` (de 3.1.879 a 3.1.973)

- **Rama:** `14.0-pns-ai-3973` · **Base (montada ahora):** `8d218ea` (E4′, rama `14.0-pns-ai-3879`) · **Commit a
  desplegar:** `5d0559b`, el último que toca los módulos. Los posteriores (`5ed7878`, HEAD el 18/11/2026) solo son
  [DOC] y dan el mismo árbol de módulos (comprobado en E0) · **Preparado:** 18/11/2026 (`2e7f784`) · **Estado:**
  ejecutado el 18/11/2026, de 16:11 a 17:12 UTC (montado ahora: `5d0559b`, `pns_demo` en 3.1.973), con dos tandas
  nuevas, T4b y F1; resultado en G.
- **Qué se sube:** el portado de los parches de Seges a 3.1.973 ([plan](plan_correccion_pns_ai_3973.md), fases 1 a 4,
  parches 35 a 39 y pruebas con toda la rama). Módulos: `pns_base` 14.0.1.2.69, `pns_ai_mcp` 14.0.3.1.973 y
  `pns_ai_chatboo` 14.0.2.1.587.
- **Origen:** [plan](plan_correccion_pns_ai_3973.md), puntos 5 (P-15), 6 (P-21) y 7 (staging), y «Tras el `-u`
  (staging y LIYBEN)». P-21: [comparación](../specs/comparacion_pns_ai_3-1-973.md), §7.3 y la fila P-21.
- **Procedimiento de referencia:** [subida de E4′](staging_e4_3879.md) (contenedores, función de SQL en solo lectura,
  túnel, «Obtenido» por fila) y [subida de E1′](staging_e1_3879.md) (`-u` de los tres módulos con cambio de esquema,
  recarga de `es_ES`).
- **Ensayo:** P-15 (18/11/2026) hizo el mismo `-u` sobre una copia de `pns_demo` de ese día, con el core del staging
  (`cc0060e`): todo como se esperaba. Los esperados de T4 y T6 salen de su salida real.
- **LIYBEN** no se toca aquí.
- **Condiciones del staging que siguen vigentes:** las del plan de staging, §1. `pns_demo` **no está neutralizado** (los
  crons corren). **Con copia de `pns_demo`** antes del `-u` (decisión a; en E1′ a E4′ no la hubo, N9).
- **Sin secretos en este documento:** ni contraseñas, ni claves, ni el contenido de `.env`.

**Decisiones de Sergio para esta subida (18/11/2026).** Propuestas por Claude y aprobadas por Sergio: b y f, al
ejecutarse E0 y la carga de `p15b_pns_demo_14`; a, c, d, e y g, a las 17:03.

| | Decisión | Aprobado |
|---|---|---|
| a | Copia de `pns_demo` antes del `-u` | Sí: `pg_dump -Fc` por SSH al equipo, sin filestore, con el web parado (T3) |
| b | Commit a desplegar | `5d0559b` |
| c | Recarga de `es_ES` tras el `-u` | Sí, como en E1′ (T7) |
| d | Comprobación del 39 | Cubierta por el laboratorio `cc0060e` (mismo core y código, 4/4, D48); en el staging, `iap_account` sin cambios (T6) |
| e | Anexo de PNS-26 | Una nota de `admin` en un contacto de demostración, desde el chat, confirmada en la ficha de Autorizaciones (T7) |
| f | Validar el SQL en el laboratorio | Hecho el 18/11/2026: `p15b_pns_demo_14` (copia de las 13:29, esquema 3.1.879) y `p15_pns_demo_14` |
| g | Nombre del documento | `staging_3973.md` |

## Índice

0. Método de despliegue y diferencias con E4′
1. Cómo se ejecuta (tandas)
2. Tandas, en orden: E0 (hecha) · E1 · P.0 y T0 · T1 · T2 · T3 · T4 · T4b (nueva) · T5 · T6 · T7 · T8
3. E. Vuelta atrás (descrita)
4. F. Limpieza (con F1, nueva)
5. G. Resultado de la subida

---

## 0. Método de despliegue y diferencias con E4′

El de E4′ (§0): `git archive` de los tres módulos desde el equipo de Sergio, `scp` a `/tmp` del VPS, huella comparada en
el VPS, copia previa del código (`addons_antes_3973`), parada de `web`, `rsync --delete` módulo a módulo como `ubuntu`,
`-u` y arranque.

**Diferencias con E4′:**
- **Cambia la base del fabricante** (3.1.879 → 3.1.973) y, con ella, la versión y el esquema de los tres módulos.
  `-u pns_base,pns_ai_mcp,pns_ai_chatboo` (D38), como en E1′. En P-15 solo se actualizaron esos tres: ningún otro
  módulo instalado depende de `pns_base` (se comprueba en T0).
- **El `rsync` borra mucho:** de `8d218ea` a `5d0559b`, 131 archivos dados de baja, 108 nuevos y 282 cambiados
  (`git diff --name-status`, E0); desaparecen 113 carpetas. El ensayo del `rsync` se comprueba contra la lista de E0.
- **El `-u` borra seis columnas de `ai_provider`** (`fit_audio`, `fit_conversation`, `fit_decision`, `fit_design`,
  `fit_video` y `fit_vision`). La casilla «Design» de E4′ pasa a ser el **rol Diseño** (`ai.provider.role`,
  `pns_ai_mcp/models/ai_provider_role.py:45`; registro `pns_ai_mcp.ai_provider_role_design`,
  `pns_ai_mcp/data/ai_provider_role_data.xml:48-57`; paso desde `fit_design` en `pns_ai_mcp/utils/schema_fossils.py:270-278`).
  `use_fallback` es del rol, no del proveedor (`ai_provider_role.py:85-91`). Por eso hay un SQL «antes» (`antes.sql`,
  con las `fit_*`) y otro «después» (`despues.sql`, con los roles).
- **El `-u` no se puede deshacer con el código:** borra columnas, skills y contextos de fábrica. La vuelta atrás después
  del `-u` es la copia de T3 o corregir hacia delante (E).
- **P-21 va dentro de T0**, justo antes del despliegue (plan, punto 6).

## 1. Cómo se ejecuta (tandas)

- Cada **tanda** es una función que se pega de una vez en la terminal indicada. Corre en un subshell (no deja `cd` ni
  `umask` en la terminal), guarda su salida con `tee` y comprueba sola el «Esperado»: cada línea sale como **`OK`**,
  **`INFO`** (difiere de lo esperado, pero no bloquea: se anota) o **`FALLO`** (bloquea). Al final,
  **`== <tanda>: TODO OK`** o **`== <tanda>: n FALLO(S). No sigas: pega la salida.`**
- Las comprobaciones que bloquean están antes de lo que escribe: si una falla, la tanda para sin escribir lo siguiente.
- **Sergio pega la salida y Claude la contrasta antes de la tanda siguiente.** Hay **cortes** obligatorios antes de T2
  (lo primero que escribe en el VPS) y después de T4, antes de T4b (lo primero que escribe tras el `-u`; T4b corre con el
  web parado y T5 lo arranca).
- **Dónde:** E1 y T3 en el **equipo de Sergio**; P.0, T0, T2 y T4 a T8 en el **VPS**, como `ubuntu`, en una sola
  sesión (si se abre otra, se vuelve a pegar P.0). T1 y la parte manual de T7, en la **interfaz** (ventana privada,
  F12 abierto).
- **Salidas:** en el VPS, `/tmp/pns_3973/` (permisos 700; solo recuentos, códigos, ids y nombres de proveedor); en el
  equipo, `~/pns_ai_3973/staging/`. No llevan secretos ni contenido de registros.
- **SQL:** los tres archivos de [staging_3973/](staging_3973/) (abajo), con `psql -X -q -At -F '|'` dentro de
  `odoo14_pns_db` y la sesión forzada a solo lectura (`default_transaction_read_only=on`, como `e4sql` de E4′). Cada
  archivo abre y cierra su transacción `BEGIN TRANSACTION READ ONLY … ROLLBACK`.
- **Prueba de las tandas (18/11/2026, entorno de Claude):** sintaxis (`bash -n`) y ejecución completa de cada una contra
  un PostgreSQL 16 con un esquema mínimo cargado con los valores de `p15b_pns_demo_14` y `p15_pns_demo_14`, y con
  `docker`, `rsync`, `ssh`, `scp` y `curl` simulados. Todas dan `TODO OK` con los valores esperados y cortan con
  `FALLO` en los casos negativos probados: skill archivada, operación pendiente, web en marcha, log del `-u` vacío o
  alterado (parche 35 con WARNING, 47 módulos), `retry 2/5` y copia demasiado pequeña. **Queda por validar en el VPS:**
  la salida real de `docker compose ps --status running --services`, el formato de las líneas `*deleting` de `rsync`
  con carpetas, la línea «HTTP service (werkzeug) running» con `workers = 2` y el `pg_dump` por SSH.
- **Validado en el VPS (18/11/2026):** los cuatro puntos anteriores, y también `odoo shell` con `workers = 2` (T4b). T4b
  y F1 se probaron igual en el entorno de Claude antes de entregarlas (abajo, en cada una).

### Archivos SQL

| Archivo | Para | SHA-256 | Validado (18/11/2026) |
|---|---|---|---|
| [`staging_3973/p21.sql`](staging_3973/p21.sql) | P-21, antes del `-u` | `476f3185280bc09fd8d824e9dbd745e24a9f386070c5601a5a30df866ab71e0e` | `p15b_pns_demo_14`: lo mismo que el 10/11 |
| [`staging_3973/antes.sql`](staging_3973/antes.sql) | estado antes del `-u` (esquema 3.1.879) | `a796856758f674403697888b07c701a69adc93c32cd8957ca1c7d7e4f65a2121` | `p15b_pns_demo_14`: igual que `p15_antes.txt` y `p15_antes_b.txt` |
| [`staging_3973/despues.sql`](staging_3973/despues.sql) | estado después (esquema 3.1.973, rol Diseño) | `7a82182ea823b75bc19a7896bb6b2cc6a7f981e6f63e7ca9c3772d0bdb2b1383` | `p15_pns_demo_14`: igual que `p15_despues.txt` |

Los escribió y validó un agente en el laboratorio `lab_pns_ai_cc0060e`, con el web parado. Las citas de código de
P-21 y del rol Diseño están en la cabecera de cada archivo. Dos matices de P-21: el riesgo de las archivadas
(`code_uniq`) vale también para los contextos (`pns_ai_mcp/models/ai_context.py:116-118`), y `p21.sql` detecta los
contextos que se borran por `rel_path`, mientras que el `-u` compara por `code` (`ai_context_disk.py:779`): en
`p15b_pns_demo_14` dan 0 de las dos maneras.

---

## 2. Tandas

### E0. Equipo: archivo del commit y esperados (hecha el 18/11/2026, 16:22)

**[LECTURA del repo; ALTERA solo `/tmp` del equipo y `~/pns_ai_3973/staging/`]** `git archive` de `5d0559b` y de
`8d218ea` (control del método), extracción en `/tmp/pns_3973_e0*`, recuentos y lista de bajas. Salida
`e0-20261118-162234.txt`. Resultado, que son los esperados de T0 y T2:

| Comprobación | Resultado |
|---|---|
| `5d0559b` | `commit`; ningún commit posterior toca los módulos |
| Control: `8d218ea` con el mismo método | 711 archivos, `e37be4488f2b086a38ff8e6f04baf2f5464a880efd5d241b442909d10fcd1844` (la de E4′): **CONTROL OK** |
| `.tar.gz` de `5d0559b` | `ca9c03158ebb4118fe019812ad7efe116ec98ed8122bf9f640f2fd2982044cae` (`/tmp/pns_addons_5d0559b.tar.gz`) |
| Versiones | `14.0.1.2.69`, `14.0.3.1.973`, `14.0.2.1.587` |
| Marcadores «Seges: parche» fuera de tests | 141 |
| Por parche | 11:2, 12:10, 15:1, 16:3, 17:5, 18:13, 19:3, 20:4, 21:6, 22:1, 24:4, 25:1, 26:2, 27:12, 28:3, 29:14, 32:5, 33:3, 34:11, 35:1, 36:2, 37:1, 38:28, 39:6 (sin los retirados 10, 13, 14, 23, 30 y 31) |
| Árbol de `5d0559b` | 688 archivos, `0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a` (= 711 − 131 + 108) |
| Bajas de archivos | 131; lista `~/pns_ai_3973/staging/bajas_8d218ea_5d0559b.txt`, `7590e5aa8748a2d3a260cfcef3736113f9cc6411da2ebcba83402f408aab93d8` |
| Carpetas que desaparecen | 113 |

### E1. Equipo: copia al VPS

**[ALTERA solo `/tmp` del VPS]** Comprueba en el equipo las huellas del `.tar.gz`, la lista de bajas y los tres `.sql`
(desde la copia de trabajo del repo), crea `/tmp/pns_3973` (700) en el VPS y copia los cinco archivos. Pide el puerto
y `usuario@host` del VPS (los de `ssh`).

```bash
s3_e1() (
  set -u
  umask 077
  D=~/pns_ai_3973/staging
  R=~/GitHub/third_party/docs/pendiente/staging_3973
  read -rp 'Puerto SSH del VPS: ' VPS_PORT
  read -rp 'Usuario@host del VPS: ' VPS_DEST
  O="$D/e1-$(date +%Y%m%d-%H%M%S).txt"
  {
  echo "== 1. Huellas en el equipo"
  F=0
  chk() { if [ "$(sha256sum "$1" | cut -d' ' -f1)" = "$2" ]; then echo "OK      $1"; else echo "FALLO   $1"; F=1; fi; }
  chk /tmp/pns_addons_5d0559b.tar.gz ca9c03158ebb4118fe019812ad7efe116ec98ed8122bf9f640f2fd2982044cae
  chk "$D/bajas_8d218ea_5d0559b.txt" 7590e5aa8748a2d3a260cfcef3736113f9cc6411da2ebcba83402f408aab93d8
  chk "$R/p21.sql" 476f3185280bc09fd8d824e9dbd745e24a9f386070c5601a5a30df866ab71e0e
  chk "$R/antes.sql" a796856758f674403697888b07c701a69adc93c32cd8957ca1c7d7e4f65a2121
  chk "$R/despues.sql" 7a82182ea823b75bc19a7896bb6b2cc6a7f981e6f63e7ca9c3772d0bdb2b1383
  [ "$F" = 0 ] || { echo "== E1: FALLO. No sigas."; exit 1; }
  echo "== 2. [ALTERA solo /tmp del VPS] Carpeta /tmp/pns_3973 y copia de los cinco archivos"
  ssh -p "$VPS_PORT" "$VPS_DEST" 'umask 077 && mkdir -p /tmp/pns_3973 && ls -ld /tmp/pns_3973' || { echo "== E1: FALLO en ssh"; exit 1; }
  if scp -P "$VPS_PORT" /tmp/pns_addons_5d0559b.tar.gz "$D/bajas_8d218ea_5d0559b.txt" \
       "$R/p21.sql" "$R/antes.sql" "$R/despues.sql" "$VPS_DEST":/tmp/pns_3973/; then
    echo "== E1: TODO OK"
  else
    echo "== E1: FALLO en scp"
  fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
s3_e1
```

Esperado: cinco `OK`, la línea de `ls -ld` (`drwx------ … /tmp/pns_3973`) y `== E1: TODO OK`.

### P.0 y T0. VPS: funciones, comprobaciones previas, P-21 y estado «antes» (solo lectura)

**P.0 [LECTURA]** Funciones de las tandas del VPS. Se pegan una vez por sesión. Solo definen funciones y la variable
`S3`; no ejecutan nada.

```bash
S3=/tmp/pns_3973
s3sql() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_pns_db \
    psql -U odoo -d pns_demo -X -q -At -F '|' -v ON_ERROR_STOP=1 "$@"; }
s3sec() { awk -v s="## $2" 'index($0, "## ") == 1 { p = (index($0, s) == 1); next } p' "$1"; }
s3una() { tr '\n' ' ' | sed 's/ $//'; }
s3chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; S3_FALLOS=$((S3_FALLOS + 1)); fi
}
s3fin() {
    if [ "$S3_FALLOS" = 0 ]; then echo "== $1: TODO OK"
    else echo "== $1: $S3_FALLOS FALLO(S). No sigas: pega la salida."; return 1; fi
}
s3arbol() {
    ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l ) | tr -d ' '
    ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 \
        | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1 )
}
echo "P.0 cargado: S3=$S3"
```

Esperado: `P.0 cargado: S3=/tmp/pns_3973`.

**T0 [LECTURA; ALTERA solo `/tmp/pns_3973`]** Huellas de lo copiado; sesión SQL en solo lectura; contenedores, puerto,
montajes, copias y disco; código montado; `odoo.conf`; módulos que actualiza el `-u`; actividad; **P-21**; estado
«antes» (`antes.txt`); y extracción del código nuevo en `/tmp/pns_3973/addons_5d0559b` con sus comprobaciones (como
B.4 de E4′). Para en el primer bloque con `FALLO`.

```bash
s3_t0() (
  set -u
  umask 077
  S3_FALLOS=0
  type s3chk >/dev/null 2>&1 && [ -n "${S3:-}" ] || { echo "Faltan las funciones de P.0: pégalas antes"; exit 1; }
  cd "$S3" || exit 1
  O="$S3/t0-$(date +%Y%m%d-%H%M%S).txt"
  {
  echo "== 1. Huellas de lo copiado desde el equipo"
  s3chk ".tar.gz de 5d0559b" "$(sha256sum pns_addons_5d0559b.tar.gz | cut -d' ' -f1)" ca9c03158ebb4118fe019812ad7efe116ec98ed8122bf9f640f2fd2982044cae
  s3chk "lista de bajas" "$(sha256sum bajas_8d218ea_5d0559b.txt | cut -d' ' -f1)" 7590e5aa8748a2d3a260cfcef3736113f9cc6411da2ebcba83402f408aab93d8
  s3chk "p21.sql" "$(sha256sum p21.sql | cut -d' ' -f1)" 476f3185280bc09fd8d824e9dbd745e24a9f386070c5601a5a30df866ab71e0e
  s3chk "antes.sql" "$(sha256sum antes.sql | cut -d' ' -f1)" a796856758f674403697888b07c701a69adc93c32cd8957ca1c7d7e4f65a2121
  s3chk "despues.sql" "$(sha256sum despues.sql | cut -d' ' -f1)" 7a82182ea823b75bc19a7896bb6b2cc6a7f981e6f63e7ca9c3772d0bdb2b1383
  [ "$S3_FALLOS" = 0 ] || { s3fin T0; exit 1; }

  echo "== 2. Sesión SQL"
  s3chk "solo lectura" "$(echo 'SHOW default_transaction_read_only;' | s3sql)" on
  s3chk "zona horaria" "$(echo 'SHOW TimeZone;' | s3sql)" UTC info

  echo "== 3. Contenedores"
  docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}' | grep -E 'odoo14_pns|odoo14_db|odoo14_server'
  s3chk "POSTGRES_USER" "$(docker exec odoo14_pns_db printenv POSTGRES_USER)" odoo
  docker port odoo14_pns

  echo "== 4. Montajes, copias y disco"
  docker inspect odoo14_pns --format '{{range .Mounts}}{{.Type}}  {{.Source}} -> {{.Destination}}  rw={{.RW}}{{"\n"}}{{end}}'
  ls -d /opt/odoo/pns_staging/addons_antes_*
  s3chk "addons_antes_3973 todavía no existe" "$(test -e /opt/odoo/pns_staging/addons_antes_3973 && echo existe || echo no)" no
  df -h /opt/odoo /tmp
  USO=$(df --output=pcent /opt/odoo | tail -1 | tr -dc '0-9')
  s3chk "disco por debajo del 95 %" "$([ "$USO" -lt 95 ] && echo si || echo "no ($USO %)")" si

  echo "== 5. Código montado (debe ser 8d218ea)"
  s3chk "archivos y huella montados" "$(s3arbol /opt/odoo/pns_staging/addons | s3una)" "711 e37be4488f2b086a38ff8e6f04baf2f5464a880efd5d241b442909d10fcd1844"

  echo "== 6. odoo.conf"
  grep -E '^[[:space:]]*(addons_path|dbfilter|logfile|data_dir|workers|max_cron_threads)[[:space:]]*=' /opt/odoo/pns_staging/config/odoo.conf

  echo "== 7. Módulos instalados que dependen de pns_base (los que actualiza el -u)"
  DEP=$(s3sql <<'SQL' | s3una
WITH RECURSIVE dep(name) AS (
    SELECT m.name FROM ir_module_module m
      JOIN ir_module_module_dependency d ON d.module_id = m.id
     WHERE d.name = 'pns_base'
    UNION
    SELECT m.name FROM ir_module_module m
      JOIN ir_module_module_dependency d ON d.module_id = m.id
      JOIN dep ON d.name = dep.name
)
SELECT m.name FROM ir_module_module m
 WHERE m.name IN (SELECT name FROM dep) AND m.state = 'installed' ORDER BY 1;
SQL
)
  s3chk "dependientes de pns_base" "$DEP" "pns_ai_chatboo pns_ai_mcp"

  echo "== 8. Actividad en pns_demo (informativo)"
  s3sql <<'SQL'
SELECT pid, state, xact_start, wait_event_type, left(query, 60)
  FROM pg_stat_activity WHERE datname = 'pns_demo' AND state <> 'idle' AND pid <> pg_backend_pid() ORDER BY xact_start;
SQL
  [ "$S3_FALLOS" = 0 ] || { s3fin T0; exit 1; }

  echo "== 9. P-21 (p21.sql, solo lectura)"
  s3sql < p21.sql > p21.txt || { echo "FALLO   psql de p21.sql"; exit 1; }
  cat p21.txt
  s3chk "P-21 contextos que reescribe" "$(s3sec p21.txt 'contextos que reescribe: resumen' | s3una)" "reescribe sin edición|12"
  s3chk "P-21 contextos que borra" "$(s3sec p21.txt 'contextos de fábrica sin archivo' | wc -l | tr -d ' ')" 0
  s3chk "P-21 skills que reescribe" "$(s3sec p21.txt 'skills que reescribe' | cut -d'|' -f1,4 | s3una)" \
      "billing|reescribe sin edición financial_health|reescribe sin edición forecast|reescribe sin edición"
  s3chk "P-21 skills retiradas" "$(s3sec p21.txt 'skills retiradas' | cut -d'|' -f1 | s3una)" \
      "annual_billing cash_forecast credit_facility customer_risk_analysis sys_info users_all users_logged"
  s3chk "P-21 skills que adoptar" "$(s3sec p21.txt 'skills nuevas que ya existen' | wc -l | tr -d ' ')" 0
  s3chk "P-21 archivadas (skills y contextos)" "$(s3sec p21.txt 'archivadas (' | wc -l | tr -d ' ')" 0
  [ "$S3_FALLOS" = 0 ] || { s3fin T0; exit 1; }

  echo "== 10. Estado antes del -u (antes.sql, solo lectura)"
  s3sql < antes.sql > antes.txt || { echo "FALLO   psql de antes.sql"; exit 1; }
  cat antes.txt
  s3chk "versiones" "$(s3sec antes.txt 'versiones' | s3una)" \
      "pns_ai_chatboo|14.0.2.1.538|installed pns_ai_mcp|14.0.3.1.879|installed pns_base|14.0.1.2.47|installed"
  s3chk "operaciones pending o confirmed sin ejecutar" "$(s3sec antes.txt 'ai_safe_operation pending' | wc -l | tr -d ' ')" 0
  s3chk "crons de NUEVO-2" "$(s3sec antes.txt 'crons de purga' | cut -d'|' -f1,2 | s3una)" \
      "ir_cron_ai_api_result_cache_gc|model.gc_expired() ir_cron_ai_fetch_cache_gc|model.gc_expired()" info
  s3chk "las 7 retiradas presentes" "$(s3sec antes.txt 'las 7 skills' | s3una)" 7 info
  s3chk "ai_skill" "$(s3sec antes.txt 'ai_skill por source_module' | s3una)" "pns_ai_chatboo|13" info
  s3chk "P-11 (AI Administrators|sin AI Conversational)" "$(s3sec antes.txt 'P-11' | s3una)" "3|0" info
  s3chk "diseños" "$(s3sec antes.txt 'diseños' | s3una)" "chatboo_session.canvas_design|12 chatboo_canvas_page.design|0" info
  s3chk "sesión con /web/image (id|user_id)" "$(s3sec antes.txt 'chatboo_session con /web/image' | s3una)" "51|2" info
  s3chk "iap, sms, partner_autocomplete" "$(s3sec antes.txt 'módulos iap' | grep -E '^(iap|sms|partner_autocomplete)\|' | cut -d'|' -f2 | s3una)" \
      "installed installed installed" info
  s3chk "acciones de confianza (n|max_id)" "$(s3sec antes.txt 'ai_trusted_action' | s3una)" "9|9" info
  s3chk "proveedores con fit_design" "$(s3sec antes.txt 'ai_provider (' | awk -F'|' '$8 == "t" { print $1 }' | s3una)" 3 info
  s3chk "iap_account (n|max_id)" "$(s3sec antes.txt 'iap_account' | s3una)" "1|1" info
  [ "$S3_FALLOS" = 0 ] || { s3fin T0; exit 1; }

  echo "== 11. Código nuevo, extraído en $S3/addons_5d0559b (solo /tmp)"
  ( umask 022 && rm -rf "$S3/addons_5d0559b" && mkdir "$S3/addons_5d0559b" \
      && tar -xzf "$S3/pns_addons_5d0559b.tar.gz" -C "$S3/addons_5d0559b" ) || { echo "FALLO   extracción"; exit 1; }
  cd "$S3/addons_5d0559b" || exit 1
  s3chk "versiones del código" "$(grep -h "'version'" pns_base/__manifest__.py pns_ai_mcp/__manifest__.py pns_ai_chatboo/__manifest__.py | tr -dc '0-9.\n' | s3una)" \
      "14.0.1.2.69 14.0.3.1.973 14.0.2.1.587"
  s3chk "marcadores fuera de tests" "$(grep -rn 'Seges: parche' pns_base pns_ai_mcp pns_ai_chatboo --include=*.py --include=*.js --include=*.xml | grep -v '/tests/' | wc -l | tr -d ' ')" 141
  s3chk "marcadores por parche" "$(grep -rhoE 'Seges: parche [0-9]+' pns_base pns_ai_mcp pns_ai_chatboo --include=*.py --include=*.js --include=*.xml --exclude-dir=tests | sort | uniq -c | sort -k4n | awk '{ print $4 ":" $1 }' | s3una)" \
      "11:2 12:10 15:1 16:3 17:5 18:13 19:3 20:4 21:6 22:1 24:4 25:1 26:2 27:12 28:3 29:14 32:5 33:3 34:11 35:1 36:2 37:1 38:28 39:6"
  s3chk "script del parche 35" "$(test -f pns_ai_mcp/migrations/14.0.3.1.973/post-migrate.py && echo si || echo no)" si
  s3chk "sin lectura para otros" "$(find pns_base pns_ai_mcp pns_ai_chatboo \( -type f ! -perm -o=r \) -o \( -type d ! -perm -o=rx \) | wc -l | tr -d ' ')" 0
  s3chk "archivos y huella del código nuevo" "$(s3arbol "$S3/addons_5d0559b" | s3una)" "688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
  s3fin T0
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
s3_t0
```

Esperado (`OK` salvo donde se dice):

| # | Comprobación | Esperado |
|---|---|---|
| 1 | Huellas | las cinco de E0 y de la tabla de archivos SQL |
| 2 | Sesión SQL | `on`; zona horaria `UTC` (`INFO` si no) |
| 3 | Contenedores | `odoo14_pns` y `odoo14_pns_db` en marcha; `POSTGRES_USER` = `odoo`; `8069/tcp -> 127.0.0.1:8169` |
| 4 | Montajes y disco | los de E4′ (G, A.0 a A.3); `addons_antes_E1` … `addons_antes_E4p`, sin `addons_antes_3973`; disco por debajo del 95 % (el 18/11, 86 %) |
| 5 | Código montado | 711, `e37be448…1844` (`8d218ea`). **Si no coincide, alguien ha cambiado el código desde E4′** |
| 6 | `odoo.conf` | los de E1′ (A.2): sin `logfile`, `workers = 2`, `max_cron_threads = 1` |
| 7 | Dependientes de `pns_base` | `pns_ai_chatboo pns_ai_mcp` |
| 8 | Actividad | ninguna transacción, o solo `idle` (informativo) |
| 9 | **P-21** | contextos que reescribe `reescribe sin edición|12`; contextos que borra 0; skills que reescribe `billing`, `financial_health` y `forecast`, sin edición; skills retiradas, las 7 (`annual_billing`, `cash_forecast`, `credit_facility`, `customer_risk_analysis`, `sys_info`, `users_all` y `users_logged`); que adoptar 0; archivadas 0. Es el resultado del 10/11/2026 (comparación, «Resultado de P-21»). **Un `FALLO` aquí (una edición, una archivada) lo decide Sergio antes de seguir** |
| 10 | Antes (`antes.txt`) | versiones `1.2.47`, `3.1.879`, `2.1.538` y 0 operaciones `pending` o `confirmed` sin ejecutar (bloquean). Informativos, con los valores de la copia de las 13:29: crons de NUEVO-2 con `model.gc_expired()`; 7 retiradas; 13 skills; P-11 `3|0`; diseños 12 y 0; sesión con `/web/image` `51|2`; `iap`, `sms` y `partner_autocomplete` instalados; acciones de confianza `9|9`; «Design» (`fit_design`) solo en el proveedor 3; `iap_account` `1|1` |
| 11 | Código nuevo | versiones `14.0.1.2.69 14.0.3.1.973 14.0.2.1.587`; 141 marcadores y su reparto (E0); el script del parche 35; 0 archivos sin lectura para otros (la extracción va con `umask 022`); 688, `0dc381e0…ba7a` |

Si pasa más de una hora entre T0 y T2, se repite T0: P-21 y el «antes» tienen que ser de justo antes del despliegue.

### T1. Interfaz: proveedores y el diseño con `/web/image` antes del `-u` (solo Sergio)

1. **Proveedores:** «Test Connection» de los Gemini (AI Engine → Providers; en E4′, los 1, 3 y 4) y, si se puede, la
   cuota en la consola de Google AI Studio (F de E1′). T7 tiene un turno de chat (el anexo de PNS-26). «Test Connection»
   escribe en el proveedor; va después de T0, que ya tomó el «antes».
2. **Diseño con `/web/image` (D55), antes del `-u`:** como `admin`, en Chatboo, abrir la sesión del punto 10 de T0 (el
   18/11, la 51, de `admin`; es de las sesiones 49 a 57 de E3′) y su página del lienzo, con F12 abierto. Se anota si se
   ven las imágenes y si la consola muestra «Refused to load the image» (`img-src`). **Sin confirmar:** cómo se llega a
   esa sesión en la lista de conversaciones; si no se localiza, se anota y se decide.

| Comprobación | Esperado | Obtenido |
|---|---|---|
| «Test Connection» y cuota | correcto en los Gemini de la cadena | proveedores 3 y 4, OK; **el 1 (Gemini 3.6 flash), `Read timed out` (240 s)** contra la API de Google. Sergio: fallo del proveedor, se sigue. Cuota: no comprobada (no se localizó la pantalla en AI Studio) |
| Sesión con `/web/image`, antes | se anota: imágenes sí/no; «Refused to load the image» sí/no | sesión 51, un registro, tarjeta con `[object Object]`, **sin imágenes**; consola sin «Refused to load the image» |

**Corte.** Sergio pega T0 y anota T1; Claude lo contrasta antes de T2.

### T2. VPS: copia del código, parada de `web` y sustitución

**[ALTERA]** Crea `/opt/odoo/pns_staging/addons_antes_3973` (el código de `8d218ea`, para la vuelta atrás), **para
`web`** (`pns_demo` deja de responder en `https://pns.liyben.com` hasta T5; PostgreSQL sigue en marcha), ensaya el
`rsync` y lo compara con la lista de bajas de E0, sustituye el código módulo a módulo como `ubuntu` y lo comprueba.
`pns_demo` no cambia en esta tanda.

```bash
s3_t2() (
  set -u
  umask 077
  S3_FALLOS=0
  type s3chk >/dev/null 2>&1 && [ -n "${S3:-}" ] || { echo "Faltan las funciones de P.0: pégalas antes"; exit 1; }
  O="$S3/t2-$(date +%Y%m%d-%H%M%S).txt"
  {
  cd /opt/odoo/pns_staging || exit 1
  echo "== 1. Comprobaciones previas"
  s3chk "código extraído (T0)" "$(s3arbol "$S3/addons_5d0559b" | s3una)" "688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
  s3chk "código montado" "$(s3arbol addons | s3una)" "711 e37be4488f2b086a38ff8e6f04baf2f5464a880efd5d241b442909d10fcd1844"
  s3chk "addons_antes_3973 todavía no existe" "$(test -e addons_antes_3973 && echo existe || echo no)" no
  [ "$S3_FALLOS" = 0 ] || { s3fin T2; echo "No se ha cambiado nada."; exit 1; }

  echo "== 2. [ALTERA] Copia del código actual en addons_antes_3973"
  cp -a addons addons_antes_3973 || { echo "FALLO   cp"; exit 1; }
  s3chk "copia addons_antes_3973" "$(s3arbol addons_antes_3973 | s3una)" "711 e37be4488f2b086a38ff8e6f04baf2f5464a880efd5d241b442909d10fcd1844"
  df -h /opt/odoo
  [ "$S3_FALLOS" = 0 ] || { s3fin T2; echo "pns_demo y el código montado no han cambiado."; exit 1; }

  echo "== 3. [ALTERA] Parar web (pns_demo deja de responder)"
  docker compose stop web
  docker compose ps
  s3chk "web parado" "$(docker compose ps --status running --services | grep -cx web)" 0
  [ "$S3_FALLOS" = 0 ] || { s3fin T2; exit 1; }

  echo "== 4. Ensayo del rsync (no cambia nada)"
  : > "$S3/rsync_ensayo.txt"
  for m in pns_base pns_ai_mcp pns_ai_chatboo; do
    rsync -ani --delete "$S3/addons_5d0559b/$m/" "addons/$m/" \
      | awk -v m="$m" '/^\*deleting/ { sub(/^\*deleting +/, ""); print m "/" $0 }' >> "$S3/rsync_ensayo.txt"
  done
  grep -v '/$' "$S3/rsync_ensayo.txt" | grep -v '__pycache__' | LC_ALL=C sort > "$S3/rsync_bajas_archivos.txt"
  LC_ALL=C sort "$S3/bajas_8d218ea_5d0559b.txt" > "$S3/bajas_ordenadas.txt"
  s3chk "bajas de archivos (número)" "$(wc -l < "$S3/rsync_bajas_archivos.txt" | tr -d ' ')" 131
  s3chk "bajas de archivos = lista de E0" "$(comm -3 "$S3/rsync_bajas_archivos.txt" "$S3/bajas_ordenadas.txt" | wc -l | tr -d ' ')" 0
  s3chk "bajas de carpetas" "$(grep -c '/$' "$S3/rsync_ensayo.txt")" 113 info
  s3chk "líneas de __pycache__" "$(grep -c '__pycache__' "$S3/rsync_ensayo.txt")" 0 info
  [ "$S3_FALLOS" = 0 ] || { s3fin T2; echo "El código montado no ha cambiado. Vuelta atrás: docker compose start web"; exit 1; }

  echo "== 5. [ALTERA] rsync --delete, módulo a módulo"
  RC=0
  for m in pns_base pns_ai_mcp pns_ai_chatboo; do
    rsync -a --delete "$S3/addons_5d0559b/$m/" "addons/$m/" || RC=$?
  done
  s3chk "salida de rsync" "$RC" 0

  echo "== 6. Verificación"
  s3chk "código montado = 5d0559b" "$(s3arbol addons | s3una)" "688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
  s3chk "sin lectura para otros" "$(find addons/pns_base addons/pns_ai_mcp addons/pns_ai_chatboo \( -type f ! -perm -o=r \) -o \( -type d ! -perm -o=rx \) | wc -l | tr -d ' ')" 0
  LC_ALL=C diff -rq addons_antes_3973 addons > "$S3/diff_3973.txt"
  echo "diff -rq: $(wc -l < "$S3/diff_3973.txt") líneas; distintos $(grep -c '^Files ' "$S3/diff_3973.txt"); solo en addons $(grep -c '^Only in addons/' "$S3/diff_3973.txt"); solo en addons_antes_3973 $(grep -c '^Only in addons_antes_3973' "$S3/diff_3973.txt")"
  s3chk "distintos en diff -rq" "$(grep -c '^Files ' "$S3/diff_3973.txt")" 282 info
  s3fin T2 || echo "Vuelta atrás del código: E.1 (pns_demo no ha cambiado)."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
s3_t2
```

Esperado:
- **1:** código extraído 688 / `0dc381e0…`; montado 711 / `e37be448…`; sin `addons_antes_3973`.
- **2:** copia con 711 / `e37be448…`.
- **3:** `web` parado.
- **4:** 131 bajas de archivos, exactamente las de la lista de E0 (bloquea); 113 carpetas (`INFO` si sale otro número:
  depende de cómo lista `rsync` las carpetas; se anota) y 0 líneas de `__pycache__`.
- **5 y 6:** `rsync` con salida 0; montado 688 / `0dc381e0…`; 0 sin lectura para otros. `diff -rq` informativo (282
  distintos).
- Si algo falla antes del punto 5, el código montado no ha cambiado: vuelta atrás, `docker compose start web` (E.1).

### T3. Equipo: copia de `pns_demo` (decisión a)

**[ALTERA el equipo y `/tmp/pns_3973` del VPS]** Con el web parado (lo comprueba), `pg_dump -Fc` de `pns_demo` por SSH
directo al equipo, sin escribir en el VPS y sin filestore (como D53 en P-15). Comprueba la salida, el tamaño (más de
1 MB; la copia de P-15 tenía 5 383 353 bytes) y la cabecera `PGDMP` del formato personalizado. Si todo va bien, deja en
el VPS la marca `/tmp/pns_3973/copia_ok`, que T4 exige. **Sin confirmar:** que la orden sea la misma de P-15 (no quedó
escrita en el traspaso); es la equivalente.

```bash
s3_t3() (
  set -u
  umask 077
  D=~/pns_ai_3973/staging
  read -rp 'Puerto SSH del VPS: ' VPS_PORT
  read -rp 'Usuario@host del VPS: ' VPS_DEST
  F="$D/pns_demo_antes_3973-$(date +%Y%m%d-%H%M).dump"
  O="$D/t3-$(date +%Y%m%d-%H%M%S).txt"
  {
  echo "== 1. Web del staging parado (T2)"
  W=$(ssh -p "$VPS_PORT" "$VPS_DEST" 'cd /opt/odoo/pns_staging && docker compose ps --status running --services' | grep -cx web)
  if [ "$W" = 0 ]; then echo "OK      web parado"; else echo "== T3: FALLO, el web está en marcha. No sigas."; exit 1; fi
  test ! -e "$F" || { echo "== T3: FALLO, ya existe $F"; exit 1; }
  echo "== 2. [ALTERA el equipo] pg_dump -Fc de pns_demo, sin filestore (D53), a $F"
  ssh -p "$VPS_PORT" "$VPS_DEST" 'docker exec odoo14_pns_db pg_dump -U odoo -Fc pns_demo' > "$F"
  RC=$?
  ls -l "$F"
  sha256sum "$F"
  T=$(stat -c %s "$F")
  M=$(head -c 5 "$F")
  if [ "$RC" = 0 ] && [ "$M" = PGDMP ] && [ "$T" -gt 1000000 ]; then
    echo "OK      copia ($T bytes, cabecera PGDMP)"
    echo "== 3. [ALTERA solo /tmp del VPS] Marca de copia hecha (la exige T4)"
    if ssh -p "$VPS_PORT" "$VPS_DEST" "umask 077 && echo '$(basename "$F") $T' > /tmp/pns_3973/copia_ok && cat /tmp/pns_3973/copia_ok"; then
      echo "== T3: TODO OK"
    else
      echo "== T3: FALLO al escribir la marca"
    fi
  else
    echo "== T3: FALLO en la copia (salida $RC, $T bytes, cabecera '$M'). No sigas."
  fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
s3_t3
```

Esperado: `OK web parado`, la huella de la copia (se anota en G), `OK copia (… bytes, cabecera PGDMP)`, la marca y
`== T3: TODO OK`. El archivo queda en 600 y se conserva hasta la limpieza final del staging.

### T4. VPS: `-u` de los tres módulos y su log

**[ALTERA `pns_demo`, con la copia de T3]** Actualiza la base de datos a 3.1.973: borra las seis `fit_*` de
`ai_provider` (y crea los roles), borra las 7 skills retiradas, reescribe 12 contextos y 3 skills de fábrica, crea las 4
skills nuevas, corre el post-migrate de 14.0.3.1.973 (parche 35) y recarga datos, vistas y seguridad de los tres
módulos. **No se puede deshacer con el código** (E). Antes comprueba: web parado, código de `5d0559b` montado y la marca
de T3. Tarda 1 a 2 minutos sin salida en pantalla (P-15: 72 s); el log queda en `/tmp/pns_3973/u-<fecha>.log` (sin
`logfile` en `odoo.conf`, todo va a la salida estándar).

```bash
s3_t4() (
  set -u
  umask 077
  S3_FALLOS=0
  type s3chk >/dev/null 2>&1 && [ -n "${S3:-}" ] || { echo "Faltan las funciones de P.0: pégalas antes"; exit 1; }
  O="$S3/t4-$(date +%Y%m%d-%H%M%S).txt"
  L="$S3/u-$(date +%Y%m%d-%H%M%S).log"
  {
  cd /opt/odoo/pns_staging || exit 1
  echo "== 1. Comprobaciones previas"
  s3chk "web parado" "$(docker compose ps --status running --services | grep -cx web)" 0
  s3chk "código montado = 5d0559b" "$(s3arbol addons | s3una)" "688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
  s3chk "copia de pns_demo hecha (T3)" "$(test -f "$S3/copia_ok" && echo si || echo no)" si
  [ "$S3_FALLOS" = 0 ] || { s3fin T4; echo "No se ha lanzado el -u."; exit 1; }

  echo "== 2. [ALTERA pns_demo] -u pns_base,pns_ai_mcp,pns_ai_chatboo, lanzado a las $(date +%H:%M:%S) (1 a 2 minutos, sin salida en pantalla)"
  docker compose run --rm -T web odoo -u pns_base,pns_ai_mcp,pns_ai_chatboo -d pns_demo --stop-after-init > "$L" 2>&1
  RC=$?
  echo "terminado a las $(date +%H:%M:%S); log: $L ($(wc -l < "$L" | tr -d ' ') líneas)"
  tail -3 "$L"

  echo "== 3. Log del -u"
  s3chk "salida del -u" "$RC" 0
  s3chk "Traceback, ERROR o CRITICAL" "$(grep -cE 'Traceback|ERROR|CRITICAL' "$L")" 0
  s3chk "módulos que no se importan" "$(grep -cE 'No module named|module .* not (found|installable)' "$L")" 0
  s3chk "Deleting field (los seis fit_* de ai.provider)" "$(grep -oE 'Deleting field [A-Za-z0-9_.]+' "$L" | sed 's/^Deleting field //' | LC_ALL=C sort | s3una)" \
      "ai.provider.fit_audio ai.provider.fit_conversation ai.provider.fit_decision ai.provider.fit_design ai.provider.fit_video ai.provider.fit_vision"
  s3chk "migraciones" "$(grep -oE 'module [a-z_]+: Running migration \[[^]]*\] [a-z-]+' "$L" | s3una)" \
      "module pns_ai_mcp: Running migration [14.0.3.1.973>] post-migrate"
  s3chk "parche 35, fixed" "$(grep -oE 'Seges patch 35: [A-Za-z0-9_.]+ fixed' "$L" | LC_ALL=C sort | s3una)" \
      "Seges patch 35: pns_ai_mcp.ir_cron_ai_api_result_cache_gc fixed Seges patch 35: pns_ai_mcp.ir_cron_ai_fetch_cache_gc fixed"
  s3chk "parche 35, WARNING" "$(grep 'Seges patch 35' "$L" | grep -c WARNING)" 0
  s3chk "módulos actualizados" "$(grep -oE 'Module [a-z0-9_]+ loaded in' "$L" | awk '{ print $2 }' | LC_ALL=C sort | s3una)" \
      "pns_ai_chatboo pns_ai_mcp pns_base"
  s3chk "módulos cargados" "$(grep -oE '[0-9]+ modules loaded in' "$L" | tail -1 | awk '{ print $1 }')" 48
  s3chk "DROP leftover" "$(grep -c 'DROP leftover' "$L")" 11 info
  echo "-- WARNING (los de librería, como jinja2 o distutils, son informativos)"
  grep ' WARNING ' "$L" | sed 's/.* WARNING [^ ]* //' | cut -c1-90 | sort | uniq -c
  s3chk "WARNING same label de ai.log" "$(grep -c 'Two fields (client_label, client_display) of ai.log' "$L")" 2 info
  s3chk "WARNING same label de ai.trusted.action" "$(grep -c 'Two fields (model_name, model_id) of ai.trusted.action' "$L")" 1 info
  s3chk "WARNING skip retired unlink" "$(grep -c 'skip retired unlink for pns_ai_mcp' "$L")" 2 info
  s3chk "otros WARNING de los pns_*" "$(grep ' WARNING ' "$L" | grep -E 'odoo\.addons\.pns_' | grep -v 'skip retired unlink' | wc -l | tr -d ' ')" 0
  s3fin T4 || echo "No arranques el web: decide con el apartado E."
  echo "Corte: pega esta salida antes de T5."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
s3_t4
```

Esperado (de la salida real de P-15, `actualizar-20261118-134056.log`):

| Comprobación | Esperado |
|---|---|
| Salida del `-u` | 0 |
| `Traceback`, `ERROR`, `CRITICAL` | 0 |
| Módulos que no se importan | 0 |
| «Deleting field» | exactamente los seis `ai.provider.fit_*` |
| Migraciones | una: `module pns_ai_mcp: Running migration [14.0.3.1.973>] post-migrate` |
| Parche 35 | «Seges patch 35: … fixed» de los dos crons; ningún WARNING del 35 |
| Módulos actualizados | `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo` («Module … loaded in»), y `48 modules loaded in` |
| «DROP leftover» | 11 (informativo) |
| WARNING | «same label» 2 de `ai.log` y 1 de `ai.trusted.action`, «skip retired unlink for pns_ai_mcp» 2 (informativos); ningún otro de `odoo.addons.pns_*` (bloquea). Los de librería (`jinja2` en el laboratorio, `distutils` en E4′) son informativos |

**Si hay `FALLO`: no se arranca** y se decide con E. **Corte** en cualquier caso: Sergio pega T4 y Claude lo contrasta
antes de T4b.

### T4b. VPS: recarga de `es_ES` y rol Diseño, con el web parado (nueva, 18/11/2026)

**[ALTERA `pns_demo`]** Añadida durante la subida (aprobada por Sergio a las 17:42 hora local, 16:42 UTC) y ejecutada
entre T4 y T5. **Sustituye los puntos 1 y 2 manuales de T7** (decisión c y «Tras el `-u`» del plan): en un solo `odoo shell`, recarga
`es_ES` con sobrescritura y pone `use_fallback` del rol Diseño a falso, con un `commit` explícito. Antes y después,
SQL de solo lectura (`/tmp/pns_3973/t4b.sql`, lo escribe la propia tanda): rol Diseño, sus proveedores, todos los roles,
`res_lang` y el número de `ir_translation` de `es_ES`. Exige el web parado y una salida de T4 con `TODO OK`.

Base en el core del staging (`cc0060e`):
- `--load-language` no sirve: `load_language` crea el asistente solo con `lang` (`odoo/tools/translate.py:1292-1301`) y
  `--i18n-overwrite` exige `-u` o una importación (`odoo/tools/config.py:387-388`).
- El asistente `base.language.install` tiene `overwrite` con `default=True`; `lang_install` activa el idioma y llama a
  `_update_translations(lang, overwrite)` sobre todos los módulos instalados
  (`odoo/addons/base/wizard/base_language_install.py:27-37`).
- `odoo shell` con la entrada sin tty ejecuta el texto con `env` de superusuario dentro del cursor y hace
  `cr.rollback()` al final (`odoo/cli/shell.py`): hace falta el `commit` explícito.
- `use_fallback` es un Boolean editable del rol (`pns_ai_mcp/models/ai_provider_role.py:72-78`); su `write` solo
  bloquea a quien no es superusuario en `_SHIPPED_FIELDS` (`:216`).

Bloque: 80 líneas, SHA-256 `81c8ac0699d3c98ff0b55511c017b83d4bfc4da9790f78a512f787fc8036c811`. Probado en el entorno de
Claude con `docker` y `odoo shell` simulados: `TODO OK`; `FALLO` con el web en marcha, sin la salida de T4 y con una
excepción antes del `commit`.

```bash
s3_t4b() (
  set -u
  umask 077
  S3_FALLOS=0
  type s3chk >/dev/null 2>&1 && [ -n "${S3:-}" ] || { echo "Faltan las funciones de P.0: pégalas antes"; exit 1; }
  O="$S3/t4b-$(date +%Y%m%d-%H%M%S).txt"
  L="$S3/t4b-shell-$(date +%Y%m%d-%H%M%S).log"
  Q="$S3/t4b.sql"
  cat > "$Q" <<'SQL'
BEGIN TRANSACTION READ ONLY;
\echo '## rol Diseño (xml_id|code|activo|use_fallback|alternativa)'
SELECT d.module || '.' || d.name, r.code, r.active, r.use_fallback, fb.code
  FROM ai_provider_role r
  LEFT JOIN ir_model_data d ON d.model = 'ai.provider.role' AND d.res_id = r.id
  LEFT JOIN ai_provider_role fb ON fb.id = r.fallback_id
 WHERE r.code = 'design';
\echo '## proveedores con el rol Diseño (provider_id|proveedor activo|use_fallback del rol)'
SELECT p.id, p.active, r.use_fallback
  FROM ai_provider_role r
  JOIN ai_provider_role_rel rr ON rr.role_id = r.id
  JOIN ai_provider p ON p.id = rr.provider_id
 WHERE r.code = 'design'
 ORDER BY p.id;
\echo '## roles (code|use_fallback)'
SELECT code, use_fallback FROM ai_provider_role ORDER BY code;
\echo '## res_lang es_ES (code|active)'
SELECT code, active FROM res_lang WHERE code = 'es_ES';
\echo '## ir_translation es_ES (n)'
SELECT count(*) FROM ir_translation WHERE lang = 'es_ES';
ROLLBACK;
SQL
  {
  cd /opt/odoo/pns_staging || exit 1
  echo "== 1. Comprobaciones previas"
  s3chk "web parado" "$(docker compose ps --status running --services | grep -cx web)" 0
  s3chk "T4 terminó con TODO OK" "$(cat "$S3"/t4-*.txt 2>/dev/null | grep -cx '== T4: TODO OK')" 1
  s3sql < "$Q" > "$S3/t4b_antes.txt" || { echo "FALLO   psql (antes)"; exit 1; }
  cat "$S3/t4b_antes.txt"
  s3chk "rol Diseño, antes" "$(s3sec "$S3/t4b_antes.txt" 'rol Diseño' | s3una)" "pns_ai_mcp.ai_provider_role_design|design|t|t|conversation"
  s3chk "proveedores con el rol Diseño, antes" "$(s3sec "$S3/t4b_antes.txt" 'proveedores con el rol' | s3una)" "3|t|t"
  s3chk "es_ES activo" "$(s3sec "$S3/t4b_antes.txt" 'res_lang es_ES' | s3una)" "es_ES|t"
  [ "$S3_FALLOS" = 0 ] || { s3fin T4b; echo "No se ha cambiado nada. No arranques: pega la salida."; exit 1; }

  echo "== 2. [ALTERA pns_demo] odoo shell: recarga de es_ES con sobrescritura y use_fallback del rol Diseño a falso (un solo commit), lanzado a las $(date +%H:%M:%S)"
  docker compose run --rm -T web odoo shell -d pns_demo > "$L" 2>&1 <<'PY'
role = env.ref('pns_ai_mcp.ai_provider_role_design')
print('T4B rol antes: use_fallback=%s' % role.use_fallback)
wiz = env['base.language.install'].create({'lang': 'es_ES', 'overwrite': True})
wiz.lang_install()
print('T4B es_ES: state=%s overwrite=%s' % (wiz.state, wiz.overwrite))
role.write({'use_fallback': False})
env.cr.commit()
print('T4B rol despues: use_fallback=%s' % role.use_fallback)
print('T4B COMMIT OK')
PY
  RC=$?
  echo "terminado a las $(date +%H:%M:%S); log: $L ($(wc -l < "$L" | tr -d ' ') líneas)"
  grep '^T4B ' "$L"
  s3chk "salida de odoo shell" "$RC" 0 info
  s3chk "commit hecho" "$(grep -cx 'T4B COMMIT OK' "$L")" 1
  s3chk "Traceback, ERROR o CRITICAL" "$(grep -cE 'Traceback|ERROR|CRITICAL' "$L")" 0
  s3chk "rol antes y después" "$(grep -E '^T4B rol (antes|despues):' "$L" | s3una)" "T4B rol antes: use_fallback=True T4B rol despues: use_fallback=False"
  s3chk "asistente de idioma" "$(grep -E '^T4B es_ES:' "$L")" "T4B es_ES: state=done overwrite=True"
  echo "-- WARNING (informativo)"
  grep ' WARNING ' "$L" | sed 's/.* WARNING [^ ]* //' | cut -c1-90 | sort | uniq -c
  echo "-- líneas con «translation» en el log (informativo): $(grep -ci 'translation' "$L")"

  echo "== 3. Después (solo lectura)"
  s3sql < "$Q" > "$S3/t4b_despues.txt" || { echo "FALLO   psql (después)"; exit 1; }
  cat "$S3/t4b_despues.txt"
  s3chk "rol Diseño sin alternativa" "$(s3sec "$S3/t4b_despues.txt" 'rol Diseño' | s3una)" "pns_ai_mcp.ai_provider_role_design|design|t|f|conversation"
  s3chk "rol Diseño solo en Gemini 3.5 flash" "$(s3sec "$S3/t4b_despues.txt" 'proveedores con el rol' | s3una)" "3|t|f"
  s3chk "los demás roles, iguales" "$(s3sec "$S3/t4b_despues.txt" 'roles (' | grep -v '^design|' | s3una)" "$(s3sec "$S3/t4b_antes.txt" 'roles (' | grep -v '^design|' | s3una)"
  s3chk "es_ES activo" "$(s3sec "$S3/t4b_despues.txt" 'res_lang es_ES' | s3una)" "es_ES|t"
  s3chk "ir_translation es_ES (antes → después)" "$(s3sec "$S3/t4b_despues.txt" 'ir_translation es_ES' | s3una)" "$(s3sec "$S3/t4b_antes.txt" 'ir_translation es_ES' | s3una)" info
  s3fin T4b || echo "No arranques el web: pega la salida."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
s3_t4b
```

Esperado:
- **1:** web parado; T4 con `TODO OK`; antes, rol Diseño `pns_ai_mcp.ai_provider_role_design|design|t|t|conversation`,
  sus proveedores `3|t|t` y `es_ES|t`. Si algo falla, no ha cambiado nada.
- **2:** `commit hecho`; 0 `Traceback`, `ERROR` y `CRITICAL`; `use_fallback` de `True` a `False`; el asistente con
  `state=done overwrite=True`. La salida de `odoo shell` es `INFO` si no es 0. Los WARNING son informativos.
- **3:** rol Diseño `…|design|t|f|conversation`, solo en el proveedor `3|t|f`; los demás roles, iguales; `es_ES|t`; el
  número de `ir_translation` de `es_ES` se anota (`INFO` si cambia).
- Si falla, no se arranca el web: Sergio pega la salida.

### T5. VPS: arranque

**[ALTERA]** Arranca `odoo14_pns` con el código nuevo, guarda `StartedAt` en `/tmp/pns_3973/started_at.txt` (lo usa
T8), espera a «HTTP service (werkzeug) running» (hasta 3 minutos) y comprueba el log y las dos URL.

```bash
s3_t5() (
  set -u
  umask 077
  S3_FALLOS=0
  type s3chk >/dev/null 2>&1 && [ -n "${S3:-}" ] || { echo "Faltan las funciones de P.0: pégalas antes"; exit 1; }
  O="$S3/t5-$(date +%Y%m%d-%H%M%S).txt"
  {
  cd /opt/odoo/pns_staging || exit 1
  echo "== 1. [ALTERA] Arrancar web"
  docker compose start web
  docker compose ps
  SA=$(docker inspect -f '{{.State.StartedAt}}' odoo14_pns)
  echo "$SA" > "$S3/started_at.txt"
  echo "StartedAt: $SA"
  echo "== 2. Esperando a «HTTP service (werkzeug) running» (hasta 3 minutos)"
  i=0
  until docker compose logs --since "$SA" web 2>&1 | grep -q 'HTTP service (werkzeug) running'; do
    i=$((i + 1)); [ "$i" -gt 36 ] && break; sleep 5
  done
  s3chk "servidor HTTP en marcha" "$([ "$i" -le 36 ] && echo si || echo no)" si info
  sleep 20
  echo "== 3. Log y respuesta"
  s3chk "Traceback, ERROR o CRITICAL desde el arranque" "$(docker compose logs --since "$SA" web 2>&1 | grep -cE 'Traceback|ERROR|CRITICAL')" 0
  s3chk "/web/login" "$(curl -sS -o /dev/null -w '%{http_code}' https://pns.liyben.com/web/login)" 200
  s3chk "/mcp por GET" "$(curl -sS -o /dev/null -w '%{http_code}' https://pns.liyben.com/mcp)" 403
  s3fin T5
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
s3_t5
```

Esperado: `StartedAt` (se anota); servidor en marcha (`INFO` si la línea no sale en 3 minutos: se mira el log a mano);
0 `Traceback`, `ERROR` y `CRITICAL`; `/web/login` 200; `GET /mcp` 403 (Nginx, plan de staging §2.3).

### T6. VPS: estado «después» (solo lectura)

**[LECTURA]** `despues.sql` a `despues.txt` y comparación automática con `antes.txt` de T0.

```bash
s3_t6() (
  set -u
  umask 077
  S3_FALLOS=0
  type s3chk >/dev/null 2>&1 && [ -n "${S3:-}" ] || { echo "Faltan las funciones de P.0: pégalas antes"; exit 1; }
  cd "$S3" || exit 1
  O="$S3/t6-$(date +%Y%m%d-%H%M%S).txt"
  {
  echo "== 1. Estado después del -u (despues.sql, solo lectura)"
  s3sql < despues.sql > despues.txt || { echo "FALLO   psql de despues.sql"; exit 1; }
  cat despues.txt
  echo "== 2. Comprobaciones"
  s3chk "versiones" "$(s3sec despues.txt 'versiones' | s3una)" \
      "pns_ai_chatboo|14.0.2.1.587|installed pns_ai_mcp|14.0.3.1.973|installed pns_base|14.0.1.2.69|installed"
  s3chk "crons de NUEVO-2 (parche 35)" "$(s3sec despues.txt 'crons de purga' | cut -d'|' -f1,2 | s3una)" \
      "ir_cron_ai_api_result_cache_gc|model._gc_expired() ir_cron_ai_fetch_cache_gc|model._gc_expired()"
  s3chk "crons de pns_* (activo y periodicidad), iguales" "$(s3sec despues.txt 'crons de pns_' | s3una)" "$(s3sec antes.txt 'crons de pns_' | s3una)" info
  s3chk "las 7 retiradas" "$(s3sec despues.txt 'las 7 skills' | s3una)" 0
  s3chk "skills de fábrica" "$(s3sec despues.txt 'ai_skill (' | awk -F'|' '$2 == "pns_ai_chatboo" { print $1 }' | s3una)" \
      "bill_draft billing customer_360 dashboard financial_health forecast pipeline sales_board top_sales users"
  s3chk "skills que no son de fábrica, iguales" "$(s3sec despues.txt 'ai_skill (' | awk -F'|' '$2 != "pns_ai_chatboo"' | s3una)" \
      "$(s3sec antes.txt 'ai_skill (' | awk -F'|' '$2 != "pns_ai_chatboo"' | s3una)"
  s3chk "P-11: sin AI Conversational" "$(s3sec despues.txt 'P-11' | cut -d'|' -f2)" 0
  s3chk "P-11: AI Administrators, iguales" "$(s3sec despues.txt 'P-11' | cut -d'|' -f1)" "$(s3sec antes.txt 'P-11' | cut -d'|' -f1)" info
  s3chk "diseños, iguales" "$(s3sec despues.txt 'diseños' | s3una)" "$(s3sec antes.txt 'diseños' | s3una)"
  s3chk "sesión con /web/image, igual" "$(s3sec despues.txt 'chatboo_session con /web/image' | s3una)" "$(s3sec antes.txt 'chatboo_session con /web/image' | s3una)" info
  s3chk "acciones de confianza, iguales" "$(s3sec despues.txt 'ai_trusted_action' | s3una)" "$(s3sec antes.txt 'ai_trusted_action' | s3una)"
  s3chk "iap_account, igual (parche 39)" "$(s3sec despues.txt 'iap_account' | s3una)" "$(s3sec antes.txt 'iap_account' | s3una)"
  s3chk "módulos iap y otros, iguales" "$(s3sec despues.txt 'módulos iap' | s3una)" "$(s3sec antes.txt 'módulos iap' | s3una)" info
  s3chk "operaciones por status, iguales" "$(s3sec despues.txt 'ai_safe_operation por status' | s3una)" "$(s3sec antes.txt 'ai_safe_operation por status' | s3una)" info
  s3chk "operaciones pending o confirmed sin ejecutar" "$(s3sec despues.txt 'ai_safe_operation pending' | wc -l | tr -d ' ')" 0
  s3chk "proveedores, iguales (id|activo|modelo|nombre)" "$(s3sec despues.txt 'ai_provider (' | s3una)" \
      "$(s3sec antes.txt 'ai_provider (' | awk -F'|' '{ print $1 "|" $2 "|" $9 "|" $10 }' | s3una)"
  s3chk "rol Diseño = proveedores con fit_design" "$(s3sec despues.txt 'proveedores con el rol' | cut -d'|' -f1 | s3una)" \
      "$(s3sec antes.txt 'ai_provider (' | awk -F'|' '$8 == "t" { print $1 }' | s3una)"
  s3chk "rol Diseño (xml_id|code|activo|use_fallback|alternativa), antes de T7" "$(s3sec despues.txt 'rol Diseño' | s3una)" \
      "pns_ai_mcp.ai_provider_role_design|design|t|t|conversation" info
  s3chk "roles por proveedor = fit_* de antes" \
      "$(s3sec despues.txt 'roles por proveedor' | awk -F'|' '{ k = split($3, a, ","); for (i = 1; i <= k; i++) if (a[i] != "") print $1 " " a[i] }' | LC_ALL=C sort | s3una)" \
      "$(s3sec antes.txt 'ai_provider (' | awk -F'|' '{ split("conversation audio vision video decision design", n, " "); for (i = 3; i <= 8; i++) if ($i == "t") print $1 " " n[i - 2] }' | LC_ALL=C sort | s3una)" info
  s3chk "ai_provider_fit_stash borrada" "$(s3sec despues.txt 'tabla ai_provider_fit_stash' | s3una)" f info
  s3chk "cadena de proveedores, igual" "$(s3sec despues.txt 'cadena ai_agent_provider' | s3una)" "$(s3sec antes.txt 'cadena ai_agent_provider' | s3una)" info
  s3fin T6
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
s3_t6
```

Esperado (`OK` salvo donde se dice):

| Comprobación | Esperado |
|---|---|
| Versiones | `14.0.1.2.69`, `14.0.3.1.973`, `14.0.2.1.587` |
| Crons de NUEVO-2 | `model._gc_expired()` en los dos (parche 35); los crons de `pns_*`, como antes (`INFO`) |
| Skills | 7 retiradas a 0; de fábrica, exactamente `bill_draft billing customer_360 dashboard financial_health forecast pipeline sales_board top_sales users` (13 → 10, como en P-15); las que no son de fábrica, iguales |
| P-11 | sin AI Conversational 0 (§6.2); AI Administrators, como antes (`INFO`) |
| Iguales a antes | diseños (12 y 0), acciones de confianza, `iap_account` (decisión d, parche 39) y proveedores (id, activo, modelo, nombre) |
| Operaciones | 0 `pending` o `confirmed` sin ejecutar; por status, como antes (`INFO`) |
| Rol Diseño | los proveedores con el rol = los que tenían `fit_design` (el 3, Gemini 3.5 flash); el rol con `use_fallback` activado y alternativa `conversation` (`INFO`: T7 lo cambia; desde T4b, que corre antes, sale `t|f|conversation` y ese `INFO` es el esperado); los roles de cada proveedor = sus `fit_*` de antes (`INFO`); `ai_provider_fit_stash` borrada (`INFO`); la cadena de proveedores, igual (`INFO`) |

### T7. Interfaz y VPS: recarga de `es_ES`, rol Diseño, diseño con `/web/image` y anexo de PNS-26

> **Desde el 18/11/2026, T4b sustituye los puntos 1 y 2** (recarga de `es_ES` y rol Diseño): se hacen automatizados
> entre T4 y T5, con el web parado, y no a mano aquí. Se conservan abajo como referencia de lo que hacen. Quedan los
> puntos 3 y 4, manuales, y `s3_t7`, que comprueba también lo de T4b.

**Manual, solo Sergio, en este orden:**

1. **(Sustituido por T4b.) [ALTERA `pns_demo`] Recarga de `es_ES`** (decisión c), como C.3 de E1′: Ajustes → Traducciones → Idiomas, fila de
   `es_ES`, «Activate / Update» y, en «Load a Translation», «Add». Sobrescribe los términos de todos los módulos
   instalados con los oficiales (no consta ninguno retocado a mano). Esperar a que termine. Los errores los cuenta T8.
2. **(Sustituido por T4b.) [ALTERA la configuración] Rol Diseño** («Tras el `-u`» del plan): desactivar `use_fallback` en el rol Diseño
   (`pns_ai_mcp.ai_provider_role_design`), sin tocar sus proveedores. Debe quedar solo en Gemini 3.5 flash (el 3), como
   salió del `-u`. Comprobar que el botón Canvas no aparece con los demás. **Sin confirmar:** el menú y la etiqueta del
   campo en la interfaz (`ai_provider_role.py:85-91`).
3. **Diseño con `/web/image` (D55), después del `-u`:** lo mismo que en T1. **Si se veían las imágenes antes y ahora
   no, se anota en G como cambio de comportamiento** (decisión A de D55: se mantiene la `<meta>` del parche 27).
4. **[ALTERA `pns_demo`] Anexo de PNS-26** (decisión e; plan, punto 7): como `admin`, conversación nueva en Chatboo:
   «Añade una nota interna al contacto «<contacto de demostración>» con el texto «Prueba anexo PNS-26 (3973)».» No se
   confirma en la tarjeta del chat: en **Autorizaciones**, abrir la ficha de la operación y pulsar **«Confirmar»**
   (encadena `/confirm` y `/execute`; pide la contraseña, parche 16). Se anota la hora y el número de «Confirmar»
   (normalmente 1). Si no hay cuota o el modelo no crea la operación, se para y decide Sergio.

**[LECTURA] Después, en el VPS:**

```bash
s3_t7() (
  set -u
  umask 077
  S3_FALLOS=0
  type s3chk >/dev/null 2>&1 && [ -n "${S3:-}" ] || { echo "Faltan las funciones de P.0: pégalas antes"; exit 1; }
  cd "$S3" || exit 1
  O="$S3/t7-$(date +%Y%m%d-%H%M%S).txt"
  {
  echo "== 1. Rol Diseño y últimas operaciones de admin (solo lectura)"
  s3sql > t7.txt <<'SQL' || { echo "FALLO   psql"; exit 1; }
BEGIN TRANSACTION READ ONLY;
\echo '## rol Diseño (xml_id|code|activo|use_fallback|alternativa)'
SELECT d.module || '.' || d.name, r.code, r.active, r.use_fallback, fb.code
  FROM ai_provider_role r
  LEFT JOIN ir_model_data d ON d.model = 'ai.provider.role' AND d.res_id = r.id
  LEFT JOIN ai_provider_role fb ON fb.id = r.fallback_id
 WHERE r.code = 'design';
\echo '## proveedores con el rol Diseño (provider_id|proveedor activo|use_fallback del rol)'
SELECT p.id, p.active, r.use_fallback
  FROM ai_provider_role r
  JOIN ai_provider_role_rel rr ON rr.role_id = r.id
  JOIN ai_provider p ON p.id = rr.provider_id
 WHERE r.code = 'design'
 ORDER BY p.id;
\echo '## últimas operaciones de admin (id|status|executed|confirmed_by_uid|create_date|write_date)'
SELECT id, status, executed, confirmed_by_uid, create_date, write_date
  FROM ai_safe_operation WHERE user_id = 2 ORDER BY id DESC LIMIT 3;
ROLLBACK;
SQL
  cat t7.txt
  echo "== 2. Comprobaciones"
  s3chk "rol Diseño sin alternativa" "$(s3sec t7.txt 'rol Diseño' | s3una)" "pns_ai_mcp.ai_provider_role_design|design|t|f|conversation"
  s3chk "rol Diseño solo en Gemini 3.5 flash" "$(s3sec t7.txt 'proveedores con el rol' | s3una)" "3|t|f"
  s3chk "operación del anexo de PNS-26 (la última de admin)" "$(s3sec t7.txt 'últimas operaciones' | head -1 | cut -d'|' -f2,3,4)" "executed|t|2"
  s3fin T7
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
s3_t7
```

Esperado: rol Diseño `…|design|t|f|conversation` y solo en el proveedor `3|t|f`; la última operación de `admin`,
`executed|t|2` (la del punto 4: se anota su id).

| # | Comprobación | Esperado | Obtenido |
|---|---|---|---|
| 1 | Recarga de `es_ES` | el asistente termina; sin errores (T8) | hecha en T4b (`state=done overwrite=True`, 0 errores) |
| 2 | Rol Diseño | solo Gemini 3.5 flash; `use_fallback` desactivado; sin botón Canvas con los demás | hecho en T4b; `s3_t7`: `…|design|t|f|conversation` y `3|t|f`. Botón Canvas con los demás: no comprobado a la vista |
| 3 | Sesión con `/web/image`, después | como antes; si no, cambio de comportamiento | igual que antes (T1): un registro, tarjeta con `[object Object]`, sin imágenes. **Sin cambio de comportamiento** (D55). Consola sin «Refused to load the image», como antes (confirmado por Sergio el 18/11/2026) |
| 4 | Anexo de PNS-26 | operación `executed`, confirmada por `admin`; la nota en el contacto | operación 36 `executed|t|2` (17:09:24); `mail.message` 205 en el contacto 29. Antes, la 35, cancelada (G, «Anexo de PNS-26») |

### T8. VPS: log del servidor desde el arranque

**[LECTURA; ALTERA solo `/tmp/pns_3973`]** Guarda el log desde `StartedAt` y cuenta lo del anexo de PNS-26. El
argumento es el número de «Confirmar» de T7 (por defecto, 1).

```bash
s3_t8() (
  set -u
  umask 077
  S3_FALLOS=0
  type s3chk >/dev/null 2>&1 && [ -n "${S3:-}" ] || { echo "Faltan las funciones de P.0: pégalas antes"; exit 1; }
  N="${1:-1}"
  cd /opt/odoo/pns_staging || exit 1
  SA=$(cat "$S3/started_at.txt") || exit 1
  LS="$S3/servidor-$(date +%Y%m%d-%H%M%S).log"
  O="$S3/t8-$(date +%Y%m%d-%H%M%S).txt"
  {
  echo "== 1. Log del servidor desde $SA ($N «Confirmar» del anexo de PNS-26)"
  docker compose logs --since "$SA" web > "$LS" 2>&1
  echo "$LS: $(wc -l < "$LS" | tr -d ' ') líneas"
  echo "-- bad query (solo orden y tabla)"
  grep -oE 'bad query: [A-Z]+( INTO| FROM)? "?[a-z_]+"?' "$LS" | sort | uniq -c
  echo "-- ERROR y CRITICAL por logger"
  grep -E ' (ERROR|CRITICAL) ' "$LS" | sed -E 's/.* (ERROR|CRITICAL) [^ ]* ([^ :]+):.*/\1 \2/' | sort | uniq -c
  echo "== 2. Comprobaciones"
  s3chk "bad query UPDATE ai_safe_operation" "$(grep -oE 'bad query: UPDATE "?ai_safe_operation"?' "$LS" | wc -l | tr -d ' ')" "$N" info
  s3chk "SERIALIZATION_FAILURE, retry 1/5" "$(grep -c 'SERIALIZATION_FAILURE, retry 1/5' "$LS")" "$N" info
  s3chk "retry 2/5 o más" "$(grep -cE 'SERIALIZATION_FAILURE, retry [2-5]/5' "$LS")" 0
  s3chk "maximum number of tries reached" "$(grep -c 'maximum number of tries reached' "$LS")" 0
  s3chk "Traceback (se miran los de arriba: solo proveedor 429/503)" "$(grep -c 'Traceback' "$LS")" 0 info
  s3fin T8
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
s3_t8 1
```

Esperado (plan, punto 7; propuesta de la fase 3, «Anexo de PNS-26»; D47 en el laboratorio): por cada «Confirmar», un
`ERROR` «bad query» `UPDATE "ai_safe_operation"` de `odoo.sql_db` y un `INFO` «SERIALIZATION_FAILURE, retry 1/5» de
`odoo.service.model`: **no son fallo** (`INFO` si el número no coincide). **Fallo:** «retry 2/5» o más, o «maximum
number of tries reached». Los demás `ERROR` y `Traceback` se miran en el listado por logger: solo se esperan los del
proveedor (429/503), si los hay.

---

## 3. E. Vuelta atrás (descrita, no lista para pegar)

**No se usó** (18/11/2026): todas las tandas terminaron con `TODO OK`.

Operaciones que cambian el VPS: las decide y hace quien administra el VPS.

1. **Antes del `-u` (fallo en T0 a T3, o en T4 antes de lanzarlo).** `pns_demo` no ha cambiado. Si el código ya se
   sustituyó (T2, punto 5), se devuelve desde `addons_antes_3973` con `rsync -a --delete`, módulo a módulo, y se
   comprueba con `s3arbol /opt/odoo/pns_staging/addons` (711, `e37be448…1844`). Después, `docker compose start web`.
2. **Después del `-u`.** Volver solo el código a `8d218ea` deja código 3.1.879 sobre un esquema 3.1.973 (sin las
   `fit_*`, sin las 7 skills retiradas): **no está validado y no se recomienda**. Opciones, por orden de preferencia:
   - **Corregir hacia delante:** un commit nuevo en `14.0-pns-ai-3973`, desplegado con este mismo procedimiento.
   - **Restaurar la copia de T3:** parar `web`; devolver el código de `addons_antes_3973` (punto 1); copiar el `.dump` al
     VPS; recrear `pns_demo` desde él (`dropdb`, `createdb` y `pg_restore` en `odoo14_pns_db`, con el usuario `odoo`);
     arrancar. **Sin confirmar:** no ensayado; el filestore no está en la copia (D53), y lo que el `-u` hubiera
     cambiado allí no se deshace.
3. **`addons_antes_3973`** se conserva hasta la limpieza final del staging, como las anteriores.

## 4. F. Limpieza

Mínima, como en E4′: no hay usuarios ni claves de prueba en esta subida.

- **Se quedan** (se anotan en G para la limpieza final): la operación y la nota del anexo de PNS-26; las sesiones de
  `admin` de T7; `addons_antes_3973`; la copia de T3 en el equipo (600).
- **`/tmp/pns_3973` del VPS:** `pns_addons_5d0559b.tar.gz` y `addons_5d0559b/` se borraron con **F1** (abajo), después
  de T6. Las salidas (`t0` a `t8`, `t4b*`, `f1`, `p21.txt`, `antes.txt`, `despues.txt`, `t7.txt`, `u-*.log`,
  `t4b-shell-*.log`, `servidor-*.log`, `diff_3973.txt`, `rsync_*.txt`, `bajas_*`, `started_at.txt`, `copia_ok`) y los
  `.sql` (los tres y `t4b.sql`), después del [DOC] del resultado. Antes se copian al equipo, porque G los cita por su
  nombre. **Hecho el 18/11/2026, tras el [DOC]:** copiado al equipo (L1 y L1b) y borrado (L2). Ver G, «Limpieza de
  `/tmp`».
- **Equipo:** `/tmp/pns_addons_5d0559b.tar.gz`, `/tmp/pns_addons_8d218ea_ctl.tar.gz`, `/tmp/pns_3973_e0` y
  `/tmp/pns_3973_e0_ctl` (E0), después del [DOC] del resultado. **Hecho el 18/11/2026** (L3).
- **Laboratorio:** `p15_pns_demo_14`, `p15b_pns_demo_14`, la copia de P-15 y el laboratorio `cc0060e` se conservan hasta
  la limpieza final del staging (traspaso de P-15).

### F1. VPS: borrado del código extraído (nueva, 18/11/2026)

**[BORRA solo en `/tmp/pns_3973`]** Ejecutada después de T6. Antes comprueba: T6 con `TODO OK`, el código montado
(688, `0dc381e0…ba7a`), `addons_antes_3973` (711, `e37be448…1844`, que se conserva) y que existen los dos que borra.
Después comprueba que ya no están y que el código montado sigue intacto, y lista lo que queda.

Bloque: 29 líneas, SHA-256 `6ae26c7be9a441f8b7a32e47c1c2bad30a56297cc5e33c32c62600b2d87553e9`. Probado en el entorno de
Claude: `TODO OK`; repetido, `FALLO` sin borrar nada.

```bash
s3_f1() (
  set -u
  umask 077
  S3_FALLOS=0
  type s3chk >/dev/null 2>&1 && [ -n "${S3:-}" ] || { echo "Faltan las funciones de P.0: pégalas antes"; exit 1; }
  cd "$S3" || exit 1
  O="$S3/f1-$(date +%Y%m%d-%H%M%S).txt"
  {
  echo "== 1. Comprobaciones previas"
  s3chk "T6 terminó con TODO OK" "$(cat t6-*.txt 2>/dev/null | grep -cx '== T6: TODO OK')" 1
  s3chk "código montado = 5d0559b" "$(s3arbol /opt/odoo/pns_staging/addons | s3una)" "688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
  s3chk "addons_antes_3973 = 8d218ea (se conserva)" "$(s3arbol /opt/odoo/pns_staging/addons_antes_3973 | s3una)" "711 e37be4488f2b086a38ff8e6f04baf2f5464a880efd5d241b442909d10fcd1844"
  s3chk "existe pns_addons_5d0559b.tar.gz" "$(test -f pns_addons_5d0559b.tar.gz && echo si || echo no)" si
  s3chk "existe addons_5d0559b/" "$(test -d addons_5d0559b && echo si || echo no)" si
  [ "$S3_FALLOS" = 0 ] || { s3fin F1; echo "No se ha borrado nada."; exit 1; }
  echo "== 2. [BORRA solo en $S3] pns_addons_5d0559b.tar.gz y addons_5d0559b/"
  rm -f -- "$S3/pns_addons_5d0559b.tar.gz"
  rm -rf -- "$S3/addons_5d0559b"
  echo "== 3. Verificación"
  s3chk "tar.gz borrado" "$(test -e pns_addons_5d0559b.tar.gz && echo existe || echo no)" no
  s3chk "addons_5d0559b borrado" "$(test -e addons_5d0559b && echo existe || echo no)" no
  s3chk "código montado intacto" "$(s3arbol /opt/odoo/pns_staging/addons | s3una)" "688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
  echo "-- lo que queda en $S3"
  ls -1 "$S3"
  s3fin F1
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
s3_f1
```

Esperado: cinco `OK` antes del borrado, tres después y `== F1: TODO OK`. Si algo falla en el punto 1, no se borra nada.

---

## 5. G. Resultado de la subida (18/11/2026)

Sergio con Claude. **Horas en UTC** (las del VPS; las locales son UTC + 1; los nombres de las salidas del equipo
llevan la hora local). Commit `5d0559b` de `14.0-pns-ai-3973`, con este documento en `2e7f784`. Todas las tandas se
ejecutaron tal cual, más **T4b** y **F1**, nuevas (arriba). Salidas del VPS en `/tmp/pns_3973/` (copiadas al equipo
antes de la limpieza); del equipo, en `~/pns_ai_3973/staging/`. Resultado: **la subida, hecha; ninguna tanda con
`FALLO` salvo la primera T7** (operación 35, abajo), repetida con `TODO OK`.

### Por tanda

| Tanda | Hora (UTC) | Resultado | Salida |
|---|---|---|---|
| E1 (equipo) | 16:11 | `TODO OK`: 5 huellas; `/tmp/pns_3973` en 700 | `e1-20261118-171159.txt` (equipo) |
| P.0 + T0 | 16:17 | `TODO OK`, **sin ningún `INFO`**: valores idénticos a los de la copia de las 13:29 | `t0-20261118-161728.txt`, `p21.txt`, `antes.txt` |
| T1 (interfaz) | ~16:20 a 16:33 | ver «Obtenido» de T1 y abajo | — |
| T2 | 16:42 | `TODO OK`. 131 bajas de archivos, las de la lista de E0; 113 carpetas (`OK`, no `INFO`); `diff -rq`: 282 distintos, 102 «solo en addons» y 97 «solo en addons_antes_3973» (una carpeta entera cuenta una línea). Web parado desde las 16:43 | `t2-20261118-164225.txt`, `rsync_*.txt`, `diff_3973.txt` |
| T3 (equipo) | 16:44 | `TODO OK`. `pns_demo_antes_3973-20261118-1744.dump`, 5 383 981 bytes, SHA-256 `ecde6453d7f782ee0d5046b1201a0301c58379cec6cb017f5277d092a04ef88b`, permisos 600 | `t3-20261118-174436.txt` (equipo) |
| T4 (`-u`) | 16:47:00 a 16:47:54 | `TODO OK`. Log de 308 líneas; «Deleting field» 6; post-migrate 1; parche 35 «fixed» 1 y 1; 48 módulos; «DROP leftover» 11; los WARNING esperados más 2 `py.warnings` de `ir_actions_report.py` (core, informativos) | `t4-20261118-164700.txt`, `u-20261118-164700.log` |
| **T4b (nueva)** | 16:51:36 a 16:51:48 | `TODO OK`. `es_ES` recargado con `overwrite=True`; rol Diseño, `use_fallback` a `f`; `ir_translation` de `es_ES` 19 627 → 19 640 (`INFO`). WARNING informativos: 9 de `pns_base.models.ir_translation` («language import drop duplicate code/model» y «removed N duplicate translation row(s)») y 2 `py.warnings` | `t4b-20261118-165135.txt`, `t4b-shell-20261118-165135.log`, `t4b_antes.txt`, `t4b_despues.txt` |
| T5 | 16:52 | `TODO OK`. **`StartedAt` `2026-11-18T16:52:46.088479983Z`**; «HTTP service (werkzeug) running» sale con `workers = 2`; `/web/login` 200 y `GET /mcp` 403. **Web parado de 16:43 a 16:52** | `t5-20261118-165245.txt` |
| T6 | 16:53 | `TODO OK`, con un `INFO` esperado: el rol Diseño ya en `f` por T4b. Skills 13 → 10 (`bill_draft billing customer_360 dashboard financial_health forecast pipeline sales_board top_sales users`); roles por proveedor = las `fit_*` de antes; `ai_log` (max) 1760 → 1762 | `t6-20261118-165357.txt`, `despues.txt` |
| T7 | 17:10 | `TODO OK`. La primera, a las 17:03, dio `FALLO` por la operación 35 (abajo) | `t7-20261118-171030.txt` (la válida); `t7-20261118-170340.txt` (diagnóstico) |
| T8 | 17:10 | `TODO OK`. «bad query» 0 y «retry 1/5» 0 (`INFO`: se esperaba 1); «retry 2/5» 0; «maximum» 0 | `t8-20261118-171037.txt`, `servidor-20261118-171037.log` (las válidas); `t8-20261118-170349.txt` (diagnóstico) |
| **F1 (nueva)** | 17:12 | `TODO OK`. Borrados `pns_addons_5d0559b.tar.gz` y `addons_5d0559b/` de `/tmp/pns_3973` | `f1-20261118-171241.txt` |

- **Validado en el VPS** todo lo que §1 dejaba por validar: la salida de `docker compose ps --status running
  --services`, el formato de `*deleting` con carpetas, «HTTP service (werkzeug) running» con `workers = 2` y el
  `pg_dump` por SSH. También `odoo shell` con `workers = 2` (T4b).
- **Notas de T0:**
  - `docker port` da además `8072/tcp -> 127.0.0.1:8172` (longpolling; T0 no lo comprueba);
  - montajes con `config` y `addons` en `rw=false` (no se compararon línea a línea con A.0 a A.3 de E4′);
  - el último `-u` antes de este fue el del 09/11/2026 a las 09:50:03 (P-21);
  - disco al 87 %.
- **P-21 (dentro de T0):** el mismo resultado que el 10/11/2026 (12 contextos y 3 skills que se reescriben sin edición,
  7 retiradas, 0 que adoptar, 0 archivadas).

### Interfaz (T1 y T7)

- **«Test Connection» (T1):** proveedores 3 y 4, OK; **el 1 (Gemini 3.6 flash) falla con `Read timed out` (240 s)**
  contra la API de Google. Sergio: fallo del proveedor, se sigue. **Cuota:** no comprobada.
- **Diseño con `/web/image` (D55), sesión 51:** antes (T1), un registro, tarjeta con `[object Object]`, **sin
  imágenes**; consola sin «Refused to load the image». Después (T7), **igual**: **sin cambio de comportamiento**, así
  que la decisión A de D55 no tiene nada que anotar. La consola, sin el aviso antes y después (confirmado por Sergio
  el 18/11/2026).
- **`es_ES` y rol Diseño (T7, puntos 1 y 2):** hechos en T4b. El botón Canvas con los demás proveedores no se miró a la
  vista; el SQL da el rol solo en el proveedor 3.

### Anexo de PNS-26: dos intentos

1. **Operación 35 (`WRIT00000011`): creada a las 16:57:59, cancelada a las 16:58:34.** Prompt de la decisión e sobre el
   contacto de demostración 14 (`base.res_partner_12`). El modelo (servido por el proveedor 4) propuso un `write` sobre
   `res.partner` con un `mail.message` dentro de `message_ids`. `admin` la confirmó y la ejecución falló con
   `KeyError: 14` en el core:
   - `pns_ai_mcp/controllers/safe_plan_execute.py:184` (`recs.write(vals)`) → `mail/models/mail_message.py:598`
     (`create`) → `mail_message.py:1195` (`_get_reply_to`): sin `model` en los valores, `records` es un `mail.thread`
     vacío y a `_notify_get_reply_to(...)[res_id]` le falta la clave 14;
   - resultado guardado: `{"error": "14", "_executing": false}`;
   - en esa cadena no hay código de Seges. Ningún `mail_message` creado desde el arranque (comprobado por SQL): no quedó
     nada a medias.
2. **Operación 36 (`CREA00000003`): creada a las 17:07:59, ejecutada a las 17:09:24.** Prompt: crear en el chatter del
   contacto una nota interna (`mail.message` nuevo, tipo `comment`, subtipo nota) con el texto «Prueba anexo PNS-26
   (3973)». El modelo eligió **otro contacto de demostración, el 29** (`base.res_partner_address_18`), y Sergio lo
   aceptó. Un «Confirmar», `executed|t|2`, `mail.message` **205** en el chatter del contacto 29.
   - **El 40001 no se reprodujo:** «bad query» `UPDATE ai_safe_operation` 0 y «retry 1/5» 0 (en D47 del laboratorio, 1
     y 1); «retry 2/5» y «maximum», 0. El documento lo trata como `INFO`. Por qué no salió esta vez: sin analizar
     (fuera del alcance de la subida).

### Log del servidor desde el arranque (T8)

- **6 ERROR y 6 Traceback:**
  - 4 de `engine_tool_loop`, todos `RuntimeError` en `openai_driver._raise_http` con **HTTP 503**, dos por turno (de
    los proveedores 1 y 3; en los dos turnos respondió el 4);
  - 2 de `safe_operation`: el `KeyError: 14` de la operación 35.
- **Orden de diagnóstico usada** (no es tanda; solo lectura): por cada ERROR, la hora, el nivel y el logger; por cada
  Traceback, archivo, línea y función, y el tipo de la excepción (su valor, solo si es numérico). No saca mensajes ni
  datos. Probada en el entorno de Claude con un log simulado. 8 líneas, SHA-256
  `cfd0cae121307a4fc3691f1d07b57e66bca2cd25dcfd4fcdebaba90c833664b0`.

```bash
( L=$(ls -t /tmp/pns_3973/servidor-*.log | head -1); echo "$L"
  awk '
{ sub(/^[^|]*\| /, "") }
/ (ERROR|CRITICAL) / { split($0, a, " "); print "## " a[2] " " a[4] " " a[6]; next }
/^Traceback/ { tb = 1; print "  Traceback"; next }
tb && /^  File "/ { l = $0; sub(/^  File "/, "", l); sub(/^.*\/(pns|odoo)\//, "", l); gsub(/"/, "", l); print "    " l; next }
tb && /^[A-Za-z_][A-Za-z0-9_.]*(:|$)/ { e = $0; m = e; sub(/:.*/, "", e); sub(/^[^:]*:? */, "", m); if (m ~ /^[0-9]+$/) e = e ": " m; print "  -> " e; tb = 0; next }
' "$L" )
```

### Lo que queda para la limpieza final del staging

**Limpieza final (20/11/2026, D69; J de [liyben_3973.md](liyben_3973.md)):** hecho lo de `pns_demo` (borrada entera,
sin copia, N9), lo del VPS (`/opt/odoo/pns_staging` borrada entera, con `addons_antes_3973`) y las salidas, que siguen
en el equipo. **Queda (K8), al cierre de la ficha 26:** la copia de T3 y `~/pns_ai_3973/staging/`, y lo del
laboratorio (`p15_pns_demo_14`, `p15b_pns_demo_14`, la copia de P-15 y el laboratorio `cc0060e`).

- **`pns_demo`:** operaciones 35 (cancelada) y 36 (ejecutada); `mail.message` 205 en el contacto 29; las sesiones de
  Chatboo de `admin` de los dos turnos: las de `user_id` 2 creadas desde `StartedAt` (16:52:46). Sus ids se sacan en la
  limpieza final.
- **VPS:** `/opt/odoo/pns_staging/addons_antes_3973` (`8d218ea`, 711, `e37be448…1844`).
- **Equipo:** la copia de T3 (600) y `~/pns_ai_3973/staging/`.
- **Laboratorio:** `p15_pns_demo_14`, `p15b_pns_demo_14`, la copia de P-15 y el laboratorio `cc0060e`.
- **Salidas del VPS:** desde la limpieza de `/tmp` (abajo), solo en el equipo, en
  `~/pns_ai_3973/staging/vps/pns_3973/` (32 archivos, 700/600). Se conservan con `~/pns_ai_3973/staging/`.

### Pendientes de decisión (de Sergio), abiertos

- **Informe al fabricante:** el plan que el validador acepta y el core no puede ejecutar (operación 35), anotado en el
  [seguimiento](seguimiento_informe_pns_ai.md) como observación sin ficha. Que el modelo eligiera otro contacto no va
  al informe (es conducta del modelo).
- Por qué el 40001 no salió en el staging: sin investigar.
- Proveedores 1 y 3 con 503 y tiempo agotado el 18/11 (lado de Google; cuota sin comprobar).
- Los WARNING de `pns_base.models.ir_translation` al recargar el idioma: se miran si salen otra vez en LIYBEN (no se
  sabe si salieron en E1′, que no guardó el log del asistente).

### Lecciones

- Antes de pegar en la sesión del VPS, mirar el prompt: P.0 y T0 se pegaron primero en el equipo y no hicieron nada (el
  `cd` de la tanda lo paró).
- Para recargar un idioma con sobrescritura: el asistente `base.language.install` desde `odoo shell`, con `commit`
  explícito. `--load-language` no admite `--i18n-overwrite` sin `-u`, y `load_language` ignora esa opción.
- Un plan de la IA puede pasar el validador y no ejecutarse en el core: revisar el plan en la ficha antes de
  «Confirmar» (tipo de operación, modelo y `res_id`; el `res_id` por SQL, con su xml_id).
- Un «esperado» de un fenómeno de concurrencia (el 40001) puede no darse: por eso va en `INFO`.
- Un «esperado» sobre el número de salidas de una tanda se saca de la lista real de archivos, no de lo que se
  recuerda de la ejecución: L1 esperaba una salida de T8 con `TODO OK` y había dos (limpieza de `/tmp`).
- Una tanda no pisa una salida que ya existe: dos ejecuciones en el mismo segundo darían el mismo nombre y `tee` la
  sobrescribiría (visto en la prueba de L1 en el entorno de Claude).

### Limpieza de `/tmp` (18/11/2026, tras el [DOC] del resultado)

Después de los commits del [DOC] (con push). Horas en UTC. Cuatro tandas, probadas en el entorno de Claude con `ssh`,
`git` y el VPS simulados (positivos y negativos de cada una). L1, L1b y L3, en el equipo; L2, en el VPS, con P.0.

| Tanda | Hora (UTC) | Resultado | Salida |
|---|---|---|---|
| L1 (equipo) | 17:38 | Comprobaciones previas `OK` (repo sin cambios, HEAD con push, commit del [DOC], copia sin hacer, `/tmp/pns_3973` en el VPS). **Copia hecha:** 32 archivos, las mismas huellas en los dos lados, sin lectura para otros. Termina con 1 `FALLO` **de la comprobación, no de la copia:** esperaba una salida de T8 con `TODO OK` y hay dos (la de diagnóstico, 170349, también terminó con `TODO OK`, porque en T8 el 40001 es `INFO`). No imprimió la huella | `l1-20261118-183843.txt`, `l1_lista_vps.txt`, `l1_lista_equipo.txt` |
| L1b (equipo, nueva) | 17:42 | `TODO OK`. La copia y el VPS, iguales que la lista de L1; la última línea de cada salida de tanda (solo `t7-20261118-170340.txt` con su `FALLO` de entonces); al menos un `TODO OK` por tanda, también en las válidas de T7 (171030) y T8 (171037). Huella de la lista: `ba2fd446c249e126875d007a5433b3a310c2dbd9406f473069328b6b45a5dcbf` | `l1b-20261118-184207.txt`, `l1b_lista_vps.txt`, `l1b_lista_equipo.txt` |
| L2 (VPS) | ~17:43 | `TODO OK`. Lista igual a la de L1; `/tmp/pns_3973` borrado; el código montado (688, `0dc381e0…ba7a`) y `addons_antes_3973` (711, `e37be448…1844`), intactos; disco al 87 % | solo en pantalla (borra la carpeta de las salidas) |
| L3 (equipo) | 17:43 | `TODO OK`. Exige L1b con `TODO OK`, la salida de E0 y el `.tar.gz` de E0 (`ca9c0315…`). Borrados los cuatro restos de E0 de `/tmp`; la copia de T3, intacta (600) | `l3-20261118-184345.txt` |

Todas las salidas, en `~/pns_ai_3973/staging/`. Los bloques, tal como se ejecutaron:

**L1** (42 líneas, SHA-256 `15da8d5d433cd7b3de80677a2c545b24116bb8461ca440bc57bd6460eda96398`). Su comprobación de las
salidas de tanda exige exactamente un `TODO OK` (`… 1`) y falla con T8; la corrige L1b. No se vuelve a usar tal cual.

```bash
s3_l1() (
  set -u
  umask 077
  D=~/pns_ai_3973/staging
  V="$D/vps"
  read -rp 'Puerto SSH del VPS: ' VPS_PORT
  read -rp 'Usuario@host del VPS: ' VPS_DEST
  O="$D/l1-$(date +%Y%m%d-%H%M%S).txt"
  test ! -e "$O" || { echo "Ya existe $O: espera un segundo y repite"; exit 1; }
  {
  F=0
  chk() { if [ "$2" = "$3" ]; then echo "OK      $1"; else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi; }
  echo "== 1. Comprobaciones previas (solo lectura)"
  G=~/GitHub/third_party
  chk "repo sin cambios pendientes" "$(git -C "$G" status --short | wc -l | tr -d ' ')" 0
  chk "HEAD con push" "$(git -C "$G" rev-parse HEAD)" "$(git -C "$G" rev-parse '@{u}')"
  chk "commit del [DOC] del resultado" "$(git -C "$G" log -8 --format=%s | grep -c 'resultado de la subida al staging de la 3973')" 1
  chk "la copia no existe todavía" "$(test -e "$V" && echo existe || echo no)" no
  chk "/tmp/pns_3973 en el VPS" "$(ssh -p "$VPS_PORT" "$VPS_DEST" 'test -d /tmp/pns_3973 && echo si || echo no')" si
  [ "$F" = 0 ] || { echo "== L1: $F FALLO(S). No se ha copiado nada."; exit 1; }
  echo "== 2. Lista con huellas en el VPS (solo lectura)"
  ssh -p "$VPS_PORT" "$VPS_DEST" 'cd /tmp/pns_3973 && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum' > "$D/l1_lista_vps.txt" \
    || { echo "== L1: FALLO al listar en el VPS"; exit 1; }
  echo "archivos en el VPS: $(wc -l < "$D/l1_lista_vps.txt" | tr -d ' ')"
  echo "== 3. [ALTERA el equipo] Copia de /tmp/pns_3973 a $V/pns_3973 (700/600)"
  mkdir "$V" || exit 1
  ssh -p "$VPS_PORT" "$VPS_DEST" 'tar -C /tmp -cf - pns_3973' | tar -C "$V" -xf - || { echo "== L1: FALLO en la copia"; exit 1; }
  echo "== 4. Verificación"
  ( cd "$V/pns_3973" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum ) > "$D/l1_lista_equipo.txt"
  chk "mismos archivos y huellas" "$(cmp -s "$D/l1_lista_vps.txt" "$D/l1_lista_equipo.txt" && echo si || echo no)" si
  chk "archivos (más de 0)" "$([ "$(wc -l < "$D/l1_lista_vps.txt")" -gt 0 ] && echo si || echo no)" si
  for t in t0:T0 t2:T2 t4:T4 t4b:T4b t5:T5 t6:T6 t7:T7 t8:T8 f1:F1; do
    chk "salida de ${t#*:} con TODO OK" "$(cat "$V/pns_3973/${t%%:*}"-*.txt 2>/dev/null | grep -cx "== ${t#*:}: TODO OK")" 1
  done
  chk "sin lectura para otros" "$(find "$V" -perm /o=rwx | wc -l | tr -d ' ')" 0
  H=$(sha256sum < "$D/l1_lista_vps.txt" | cut -d' ' -f1)
  if [ "$F" = 0 ]; then echo "== L1: TODO OK"; echo "Huella de la lista (argumento de s3_l2): $H"
  else echo "== L1: $F FALLO(S). No borres nada en el VPS: pega la salida."; fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
s3_l1
```

**L1b** (37 líneas, SHA-256 `5c834db06a213db0359247506dcf01f16af811be97014171bb4a546464b93111`). Solo lectura sobre la
copia de L1 y el VPS; exige al menos un `TODO OK` por tanda y el de las válidas de T7 y T8.

```bash
s3_l1b() (
  set -u
  umask 077
  D=~/pns_ai_3973/staging
  V="$D/vps/pns_3973"
  read -rp 'Puerto SSH del VPS: ' VPS_PORT
  read -rp 'Usuario@host del VPS: ' VPS_DEST
  O="$D/l1b-$(date +%Y%m%d-%H%M%S).txt"
  test ! -e "$O" || { echo "Ya existe $O: espera un segundo y repite"; exit 1; }
  {
  F=0
  chk() { if [ "$2" = "$3" ]; then echo "OK      $1"; else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi; }
  echo "== 1. Copia de L1 frente a su lista (solo lectura)"
  ( cd "$V" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum ) > "$D/l1b_lista_equipo.txt"
  chk "copia = lista del VPS de L1" "$(cmp -s "$D/l1_lista_vps.txt" "$D/l1b_lista_equipo.txt" && echo si || echo no)" si
  echo "== 2. El VPS no ha cambiado desde L1 (solo lectura)"
  ssh -p "$VPS_PORT" "$VPS_DEST" 'cd /tmp/pns_3973 && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum' > "$D/l1b_lista_vps.txt" \
    || { echo "== L1b: FALLO al listar en el VPS"; exit 1; }
  chk "lista del VPS = la de L1" "$(cmp -s "$D/l1_lista_vps.txt" "$D/l1b_lista_vps.txt" && echo si || echo no)" si
  echo "== 3. Salidas de las tandas (final de cada una)"
  for t in t0 t2 t4 t4b t5 t6 t7 t8 f1; do
    for f in "$V/$t"-*.txt; do printf '%-28s %s\n' "$(basename "$f")" "$(grep -E '^== [A-Za-z0-9]+: ' "$f" | tail -1)"; done
  done
  for t in t0:T0 t2:T2 t4:T4 t4b:T4b t5:T5 t6:T6 t7:T7 t8:T8 f1:F1; do
    n=$(cat "$V/${t%%:*}"-*.txt 2>/dev/null | grep -cx "== ${t#*:}: TODO OK")
    chk "${t#*:} con al menos un TODO OK" "$([ "$n" -ge 1 ] && echo si || echo "no ($n)")" si
  done
  chk "T7 válida (171030) con TODO OK" "$(grep -cx '== T7: TODO OK' "$V"/t7-20261118-171030.txt 2>/dev/null)" 1
  chk "T8 válida (171037) con TODO OK" "$(grep -cx '== T8: TODO OK' "$V"/t8-20261118-171037.txt 2>/dev/null)" 1
  chk "sin lectura para otros" "$(find "$D/vps" -perm /o=rwx | wc -l | tr -d ' ')" 0
  H=$(sha256sum < "$D/l1_lista_vps.txt" | cut -d' ' -f1)
  if [ "$F" = 0 ]; then echo "== L1b: TODO OK"; echo "Huella de la lista (argumento de s3_l2): $H"
  else echo "== L1b: $F FALLO(S). No borres nada en el VPS: pega la salida."; fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
s3_l1b
```

**L2** (22 líneas, SHA-256 `6d96438ce5cfb8e25abab6b6ad1a33cdf022548c769538305a0c1edeeb576c90`, con la huella de L1b en
la última línea). Exige las funciones de P.0 y la huella; borra solo si la lista coincide.

```bash
s3_l2() (
  set -u
  S3_FALLOS=0
  type s3chk >/dev/null 2>&1 && [ -n "${S3:-}" ] || { echo "Faltan las funciones de P.0: pégalas antes"; exit 1; }
  H="${1:-}"
  [ -n "$H" ] || { echo "Falta la huella que imprimió s3_l1"; exit 1; }
  echo "== 1. Comprobaciones previas (solo lectura)"
  s3chk "S3 es /tmp/pns_3973" "$S3" /tmp/pns_3973
  s3chk "lista = la copiada al equipo (L1)" "$(cd "$S3" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)" "$H"
  s3chk "código montado = 5d0559b" "$(s3arbol /opt/odoo/pns_staging/addons | s3una)" "688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
  s3chk "addons_antes_3973 = 8d218ea (se conserva)" "$(s3arbol /opt/odoo/pns_staging/addons_antes_3973 | s3una)" "711 e37be4488f2b086a38ff8e6f04baf2f5464a880efd5d241b442909d10fcd1844"
  [ "$S3_FALLOS" = 0 ] || { s3fin L2; echo "No se ha borrado nada."; exit 1; }
  echo "== 2. [BORRA] /tmp/pns_3973"
  rm -rf -- /tmp/pns_3973
  echo "== 3. Verificación"
  s3chk "/tmp/pns_3973 borrada" "$(test -e /tmp/pns_3973 && echo existe || echo no)" no
  s3chk "código montado intacto" "$(s3arbol /opt/odoo/pns_staging/addons | s3una)" "688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
  s3chk "addons_antes_3973 intacta" "$(s3arbol /opt/odoo/pns_staging/addons_antes_3973 | s3una)" "711 e37be4488f2b086a38ff8e6f04baf2f5464a880efd5d241b442909d10fcd1844"
  df -h /tmp | tail -1
  s3fin L2
)
s3_l2 ba2fd446c249e126875d007a5433b3a310c2dbd9406f473069328b6b45a5dcbf
```

**L3** (31 líneas, SHA-256 `475653f73a80965e4791d7ea7b21cc5d7e92d3dea7db35f121e6cb67b689af63`).

```bash
s3_l3() (
  set -u
  umask 077
  D=~/pns_ai_3973/staging
  O="$D/l3-$(date +%Y%m%d-%H%M%S).txt"
  test ! -e "$O" || { echo "Ya existe $O: espera un segundo y repite"; exit 1; }
  {
  F=0
  chk() { if [ "$2" = "$3" ]; then echo "OK      $1"; else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi; }
  echo "== 1. Comprobaciones previas (solo lectura)"
  chk "L1b terminó con TODO OK" "$(cat "$D"/l1b-*.txt 2>/dev/null | grep -cx '== L1b: TODO OK')" 1
  chk "E0 guardada" "$(ls "$D"/e0-*.txt 2>/dev/null | wc -l | tr -d ' ')" 1
  chk ".tar.gz de 5d0559b" "$(sha256sum /tmp/pns_addons_5d0559b.tar.gz 2>/dev/null | cut -d' ' -f1)" ca9c03158ebb4118fe019812ad7efe116ec98ed8122bf9f640f2fd2982044cae
  for p in /tmp/pns_addons_8d218ea_ctl.tar.gz /tmp/pns_3973_e0 /tmp/pns_3973_e0_ctl; do
    chk "existe $p" "$(test -e "$p" && echo si || echo no)" si
  done
  chk "la copia de T3 sigue (600)" "$(stat -c %a "$D"/pns_demo_antes_3973-20261118-1744.dump 2>/dev/null)" 600
  [ "$F" = 0 ] || { echo "== L3: $F FALLO(S). No se ha borrado nada."; exit 1; }
  echo "== 2. [BORRA solo en /tmp del equipo] los cuatro restos de E0"
  rm -f -- /tmp/pns_addons_5d0559b.tar.gz /tmp/pns_addons_8d218ea_ctl.tar.gz
  rm -rf -- /tmp/pns_3973_e0 /tmp/pns_3973_e0_ctl
  echo "== 3. Verificación"
  for p in /tmp/pns_addons_5d0559b.tar.gz /tmp/pns_addons_8d218ea_ctl.tar.gz /tmp/pns_3973_e0 /tmp/pns_3973_e0_ctl; do
    chk "borrado $p" "$(test -e "$p" && echo existe || echo no)" no
  done
  chk "la copia de T3 intacta" "$(stat -c %a "$D"/pns_demo_antes_3973-20261118-1744.dump)" 600
  if [ "$F" = 0 ]; then echo "== L3: TODO OK"; else echo "== L3: $F FALLO(S). Pega la salida."; fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
s3_l3
```
