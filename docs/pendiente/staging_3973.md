# Subida de la rama 3973 al staging `pns_demo` (de 3.1.879 a 3.1.973)

- **Rama:** `14.0-pns-ai-3973` · **Base (montada ahora):** `8d218ea` (E4′, rama `14.0-pns-ai-3879`) · **Commit a
  desplegar:** `5d0559b`, el último que toca los módulos. Los posteriores (`5ed7878`, HEAD el 18/11/2026) solo son
  [DOC] y dan el mismo árbol de módulos (comprobado en E0) · **Preparado:** 18/11/2026 · **Estado:** preparado, sin
  ejecutar.
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
2. Tandas, en orden: E0 (hecha) · E1 · P.0 y T0 · T1 · T2 · T3 · T4 · T5 · T6 · T7 · T8
3. E. Vuelta atrás (descrita)
4. F. Limpieza
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
  (lo primero que escribe en el VPS) y antes de T5 (arrancar con el código nuevo).
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
| «Test Connection» y cuota | correcto en los Gemini de la cadena | [ ] |
| Sesión con `/web/image`, antes | se anota: imágenes sí/no; «Refused to load the image» sí/no | [ ] |

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
antes de T5.

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
| Rol Diseño | los proveedores con el rol = los que tenían `fit_design` (el 3, Gemini 3.5 flash); el rol con `use_fallback` activado y alternativa `conversation` (`INFO`: T7 lo cambia); los roles de cada proveedor = sus `fit_*` de antes (`INFO`); `ai_provider_fit_stash` borrada (`INFO`); la cadena de proveedores, igual (`INFO`) |

### T7. Interfaz y VPS: recarga de `es_ES`, rol Diseño, diseño con `/web/image` y anexo de PNS-26

**Manual, solo Sergio, en este orden:**

1. **[ALTERA `pns_demo`] Recarga de `es_ES`** (decisión c), como C.3 de E1′: Ajustes → Traducciones → Idiomas, fila de
   `es_ES`, «Activate / Update» y, en «Load a Translation», «Add». Sobrescribe los términos de todos los módulos
   instalados con los oficiales (no consta ninguno retocado a mano). Esperar a que termine. Los errores los cuenta T8.
2. **[ALTERA la configuración] Rol Diseño** («Tras el `-u`» del plan): desactivar `use_fallback` en el rol Diseño
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
| 1 | Recarga de `es_ES` | el asistente termina; sin errores (T8) | [ ] |
| 2 | Rol Diseño | solo Gemini 3.5 flash; `use_fallback` desactivado; sin botón Canvas con los demás | [ ] |
| 3 | Sesión con `/web/image`, después | como antes; si no, cambio de comportamiento | [ ] |
| 4 | Anexo de PNS-26 | operación `executed`, confirmada por `admin`; la nota en el contacto | [ ] |

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
- **`/tmp/pns_3973` del VPS:** `pns_addons_5d0559b.tar.gz` y `addons_5d0559b/` se pueden borrar después de T6; las
  salidas (`t0` a `t8`, `p21.txt`, `antes.txt`, `despues.txt`, `t7.txt`, `u-*.log`, `servidor-*.log`, `diff_3973.txt`,
  `rsync_*.txt`) y los `.sql`, después del [DOC] del resultado.
- **Equipo:** `/tmp/pns_addons_5d0559b.tar.gz`, `/tmp/pns_addons_8d218ea_ctl.tar.gz`, `/tmp/pns_3973_e0` y
  `/tmp/pns_3973_e0_ctl` (E0), después del [DOC] del resultado.
- **Laboratorio:** `p15_pns_demo_14`, `p15b_pns_demo_14`, la copia de P-15 y el laboratorio `cc0060e` se conservan hasta
  la limpieza final del staging (traspaso de P-15).

---

## 5. G. Resultado de la subida

Sin ejecutar. Se rellena con las salidas de cada tanda (por su nombre, sin datos), los «Obtenido» de T1 y T7, las
huellas de T3 y los ids que quedan para la limpieza final.
