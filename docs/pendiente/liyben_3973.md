# Despliegue de la rama 3973 en LIYBEN (de 3.1.782 a 3.1.973)

- **Rama:** `14.0-pns-ai-3973`. **Montado antes del despliegue:** `578859b` (rama `14.0-pns-ai-3`, 3.1.782; [instalación](instalacion_liyben_pns_ai.md),
  §3.2). **Commit a desplegar:** el HEAD de la rama en el commit de este documento (D58). E0 comprueba que de `c6ec077`
  a él solo cambia `docs/` y que el árbol de los módulos es el de `5d0559b` (688 archivos, `0dc381e0…ba7a`). El hash
  completo queda en `commit.txt` (E0) y se anota en G. **Preparado:** 20/11/2026. **Estado:** ejecutado el
  20/11/2026, con el commit `3df4307` (G).
- **Qué se despliega:** el portado de los parches de Seges a 3.1.973 ([plan](plan_correccion_pns_ai_3973.md), fases 1 a
  4, parches 35 a 39 y pruebas con toda la rama), ya subido al staging ([staging_3973.md](staging_3973.md)). Módulos:
  `pns_base` 14.0.1.2.32 → 14.0.1.2.69, `pns_ai_mcp` 14.0.3.1.782 → 14.0.3.1.973 y `pns_ai_chatboo` 14.0.2.1.453 →
  14.0.2.1.587.
- **Origen:** [plan](plan_correccion_pns_ai_3973.md), «Tras el `-u` (staging y LIYBEN)», con D50 y D56 a D67 (abajo);
  [instalación](instalacion_liyben_pns_ai.md), §6.2 (fila «Despliegue de las correcciones»).
- **Referencias:** [staging_3973.md](staging_3973.md) (método, T4b y la forma de las tandas) e
  [instalación](instalacion_liyben_pns_ai.md) §3 (copia previa, git como el UID 101 con refspec explícito y `checkout -b`
  sin `--track`) y §7 (vuelta atrás de la instalación).
- **Ensayo:** el `-u`, la recarga de `es_ES` y el rol Diseño se ensayaron el 19/11/2026 sobre una copia de LIYBEN de ese
  día (`liyben_ens_14`), con la imagen del VPS, el core `cc0060e` y los OCA y repos propios en los commits del VPS. Los
  «Esperado» de L0 a L6 salen de ese ensayo (Y4 a Y7, Anexo A), con D50 aplicado (tokens 0, no 8).
- **Condiciones de LIYBEN:** producción, con datos reales y **sin neutralizar** (los crons corren). Un solo
  `docker compose` en `/opt/odoo` (servicios `web`, `odoo14_server`, y `db`, `odoo14_db`); solo la BD LIYBEN (D9);
  `logfile` en `odoo.conf` (el log está en `/opt/odoo/logs/odoo-server.log`); clon de `third_party` del UID 101
  (`messagebus`) con refspec solo de `14.0`. **El servicio se corta** de L2 a L5 (en el ensayo, el `-u` tardó 67-72 s).
  **Con copia completa** (BD y filestore) antes del `-u` (D57).
- **Sin secretos en este documento:** ni contraseñas, ni claves, ni el contenido de `.env`. Las salidas solo llevan
  recuentos, códigos, ids y nombres de proveedor.

**Decisiones de este despliegue.** Propuestas por Claude y aprobadas por Sergio (D50, 19/11 por la mañana; D56 a D64,
19/11 a mediodía; D65 a D67 y D66 revisada, 19/11 por la tarde; las del documento, 19/11 a las 16:14). Pasan al plan
(«Tras el `-u`») y a la instalación (§6.2) en el [DOC] de este documento.

| | Decisión |
|---|---|
| D50 | Los **8 tokens de registro** de LIYBEN se vacían por SQL justo antes del `-u` (`d50_vaciar VACIAR`, en L4), solo con el perfil exacto (8 tokens, 5 filas) y ningún token vigente o sin caducidad de un interno. Ensayado en LIYBEN con `ROLLBACK` el 19/11 (y otra vez en L0). Detalle en el plan, «D50 hecho» |
| D56 | **Ensayo** del `-u` sobre una copia de LIYBEN antes de escribir este documento, con el web parado de principio a fin: laboratorio `~/GitHub/lab_liyben_3973`, Dockerfile del VPS más el bloque del core `cc0060e`, OCA y `vertical-instaladores` fijados en los commits del VPS (restaurados al acabar). Hecho (Anexo A) |
| D57 | **Copia completa antes del `-u`:** BD y filestore, por SSH al equipo, con el web parado. Orden: parar el web → copia → `d50_vaciar VACIAR` → `checkout` → `-u` (L2, L3 y L4) |
| D58 | **Commit a desplegar:** el HEAD de la rama en el commit de este documento, con compuerta de árbol 688 / `0dc381e0…`. Concreción (19/11, 16:14): HEAD = `origin/14.0-pns-ai-3973`; de `c6ec077` a HEAD solo cambia `docs/`; el hash, en `commit.txt` (E0) y en G |
| D59 | **Comprobaciones heredadas** del plan de la 3879 (§3, «Al terminar») y de A.4 a A.6 de E3′/E4′, en L0 (I0), de solo lectura. Bloquean: operaciones pendientes o confirmadas sin ejecutar con pasos sobre `ai.trusted.action`. INFO: decisión 10, servidores MCP (PNS-17), PNS-82, PNS-37 y A.6 |
| D60 | **Claves MCP** (revocadas el 27/10): no se regeneran en el despliegue (Nginx da 404 en `/mcp`, D20); si hacen falta, en el uso real |
| D61 | **Ficha 26** de la §6.2 (usuario sin AI Administrator): al uso real. En el despliegue, solo el SQL de AI Conversational de los AI Administrators (L0 y L6) |
| D62 | **Rol Diseño** al proveedor **1** (`models/gemini-3.5-flash`, hoy inactivo) y `use_fallback` desactivado. Mientras el 1 esté inactivo, nadie diseña (no cae a Qwen 9B) |
| D63 | Nombre: `docs/pendiente/liyben_3973.md`; SQL y tandas en `docs/pendiente/liyben_3973/` |
| D64 | **Los 3 AI Administrators se quedan:** ids 2, 6 y 7. El 2 no tiene AI Conversational y lo gana fijo en el `-u` (§6.2): se anota en G |
| D65 | **«Antes» de LIYBEN** con P-21 adaptado a 3.1.782 (Y4): A, lista de `ai/` de `578859b` al commit = la del fabricante de 3.1.782 a 3.1.973 (A 15, D 12, M 19, `f413c755…d4`; en E0); B, esquema y correspondencia exacta de los 56 contextos y las 10 skills con los archivos de 3.1.782; C, «antes» y P-21; D, contraste con I0 (B, C y D en L0). Una edición de fábrica es FALLO |
| D66 (revisada) | **Recarga de `es_ES`: B′.** En una sola transacción: guardar las filas `es_ES` de fuera de los `pns_*`, `_update_translations('es_ES', True)` de los tres `pns_*` y restaurar por `id` las que cambiaron (y reinsertar las borradas). Los `pns_*` reciben sus 196 traducciones cambiadas y nada de fuera cambia. Historia: primera elección B, revisada el 19/11 tras la medida de Y6 v3 (B reescribía 13 textos y 36 orígenes `code` de otros módulos) |
| D67 | **Rol Diseño (D62) con un solo `write`** del proveedor 1: quitar Decisión y añadir Diseño (`role_ids: [(3, decisión), (4, diseño)]`), y `use_fallback` de Diseño a falso. El `-u` da Decisión al proveedor 1 (`openai`, `fit_decision = t`) y en 3.1.973 solo `systemone` la admite: sin quitarla, el `write` da `ValidationError` |

Decisiones del documento (19/11/2026, 16:14; las recomendaciones de Claude): **L0 frente al ensayo** bloquea lo
estructural; lo que cambia con el uso (diario, Chatboo, `ai_log`, traducciones, servidores API), INFO; L2 exige una L0
de menos de una hora. **Filestore en L3:** `tar` por SSH al equipo, sin escribir en el VPS, con `.parcial` y recuento de
archivos. **L7 sin turno de Chatboo con IA** (al uso real, como D61). **Salidas:** VPS `/tmp/liyben_3973` (700); equipo
`~/pns_ai_3973/liyben/despliegue/`. Las tandas del ensayo entran en el repo tal cual (Anexo B); las del despliegue son
nuevas (`ld_*`).

## Índice

0. Método y diferencias con el staging
1. Cómo se ejecuta
2. Tandas, en orden: E0 · E1 · L.0 y L0 · L1 (interfaz) · corte · L2 · L3 · corte · L4 · corte · L4b (comprobar, corte,
   APLICAR_BP) · corte · L5 · L6 · L7 (interfaz) · L8
3. E. Vuelta atrás (descrita)
4. F. Limpieza (F0, F1 y F2)
5. G. Resultado (vacío)
- Anexo A. Ensayo
- Anexo B. Tandas del ensayo en el repo

---

## 0. Método y diferencias con el staging

El de la instalación (§3.2): el código llega por git al clon de `third_party` del VPS, **como el UID 101**, con `fetch`
de refspec explícito y `checkout -b` sin `--track`; después, `-u` de los tres módulos con el web parado y arranque. La
rama `14.0-pns-ai-3` se queda en `578859b` (vuelta atrás) y `14.0` no se toca.

**Diferencias con el staging ([staging_3973.md](staging_3973.md)):**
- **Git en vez de `git archive` + `rsync`:** LIYBEN tiene un clon de todo `third_party` (§3.2), no una carpeta de
  módulos. De `578859b` al commit, fuera de los `pns_*` y `docs/` solo cambia `CLAUDE.md` (E0).
- **Otra base del fabricante:** se sube desde 3.1.782 (el staging venía de 3.1.879). El `-u` borra las **5** `fit_*` de
  3.1.782 (no existía `fit_design`) y **7 campos más**, todos documentados y sin pérdida que importe (Y5, Anexo A); lleva
  una migración (`14.0.3.1.973`), el parche 35 corrige los dos crons de NUEVO-2 y crea un cron nuevo,
  `pns_ai_mcp.ir_cron_ai_journal_trash`, **activo** (LIYBEN no está neutralizada).
- **P-21 con las listas de 3.1.782** (D65): 13 contextos y 3 skills reescritos sin edición, 3 contextos nuevos, 6
  skills retiradas. El `-u` escribe los 56 contextos y las 10 skills (no solo los de P-21): las ediciones de fábrica solo
  se detectan **antes** del `-u` (L0).
- **Recarga de `es_ES` B′** (D66 revisada) en vez de la recarga completa del staging (T4b): en LIYBEN, la recarga de los
  `pns_*` con sobrescritura reescribía términos `code` de otros módulos.
- **Rol Diseño en el proveedor 1, quitándole Decisión** (D62, D67), no en el que ya lo tenía.
- **D50:** se vacían los 8 tokens de registro en L4, justo antes del `checkout` y del `-u`.
- **Copia completa** (BD y filestore; D57); en el staging, solo la BD.
- **Las tandas del VPS no se pegan:** E1 las copia desde el commit, con sus huellas, y se lanzan con `bash` (§1).
- **Log:** con `logfile` en `odoo.conf`, nada de Odoo sale por la salida estándar del contenedor. Cada tanda guarda la
  posición del log antes y corta desde ahí (FALLO si el log rota).
- **El `-u` no se puede deshacer con el código:** borra columnas, skills y contextos de fábrica. Después del `-u`, la
  vuelta atrás es corregir hacia delante o restaurar la copia de L3 (E).

## 1. Cómo se ejecuta

- **Tandas en archivos.** Todas están en [`liyben_3973/`](liyben_3973/) del commit; el texto completo de cada una va en
  su apartado, con sus líneas y su SHA-256. Cada una corre en un subshell, guarda su salida con `tee` y comprueba sola
  el «Esperado»: cada línea sale como **`OK`**, **`INFO`** (difiere, pero no bloquea: se anota) o **`FALLO`**
  (bloquea). Termina siempre con **`== LD <tanda>: TODO OK. <siguiente paso>`** o **`== LD <tanda>: n FALLO(S) …`**:
  una salida sin esa línea final no está terminada.
- **Compuertas:** cada tanda comprueba antes de escribir lo que necesita (la anterior con `TODO OK`, el web en el estado
  esperado, el clon, el commit, las huellas) y para con `FALLO` sin escribir nada. Las que escriben comprueban también
  que no se han ejecutado ya.
- **Sergio pega la salida y Claude la contrasta antes de la tanda siguiente.** Cortes obligatorios: tras L0 y L1 (antes
  de lo primero que escribe en el VPS), tras L3 (antes del `-u`), tras L4 (antes de L4b), entre L4b comprobar y
  APLICAR_BP, y tras APLICAR_BP (antes de arrancar el web).
- **Equipo de Sergio** (E0, E1, L3, F0 y F1), desde el repo, en una terminal donde antes se ha lanzado (solo para las
  que usan SSH: E1, L3 y F1):

  ```bash
  read -rp 'Puerto SSH del VPS: ' VPS_PORT; read -rp 'Usuario@host del VPS: ' VPS_DEST; export VPS_PORT VPS_DEST
  ```

  y cada tanda con `bash ~/GitHub/third_party/docs/pendiente/liyben_3973/ld_<x>.sh`.
- **VPS** (L0, L2, L4, L4b, L5, L6, L8 y F2): en **una sesión SSH interactiva** como `ubuntu` (`sudo` pide la contraseña
  en L0, L2 y L4; git como el UID 101 va después con `sudo -n -u messagebus env HOME=/tmp git …`). Cada tanda con
  `bash /tmp/liyben_3973/ld_<x>.sh`; las tandas comprueban que se lanzan desde ahí.
- **Interfaz** (L1 y L7): solo Sergio, ventana privada, F12 abierto.
- **Salidas:** en el VPS, `/tmp/liyben_3973/` (700): las tandas, `commit.txt`, `huellas.txt` y las salidas (`l0-*`,
  `l0_antes-*`, `l0_i0-*`, `l2-*`, `copia_ok`, `l4-*`, `u-*.log`, `l4_t0.txt`, `l4b-*`, `l5-*`, `l5_offset.txt`,
  `l5_started_at.txt`, `l6-*`, `l6_despues-*`, `l8-*`, `servidor-*.log`). En el equipo, `~/pns_ai_3973/liyben/despliegue/`
  (700): `e0-*`, `commit.txt`, `e1-*`, `huellas_vps.txt`, `l3-*`, las dos copias de L3 (600) y, tras F1, `vps/`.
- **Horas:** las del VPS, en UTC; las del equipo, locales (UTC + 1).

### Archivos que van al VPS

E1 los copia desde `git archive` del commit, comprueba sus huellas contra la lista que lleva dentro y deja en el VPS
`huellas.txt`, que L0, L2, L4 y L4b vuelven a comprobar. Las piezas SQL y Python son las del ensayo, extraídas por
líneas sin cambios (Anexo A): el despliegue corre lo mismo que se validó.

| Archivo | Líneas | SHA-256 | Lo usa |
|---|---|---|---|
| [`ld_comun.sh`](liyben_3973/ld_comun.sh) | 41 | `7886e6c4cbbd08412b67eff196a7c6ae36a58e17d5126ecf8620ede02157511d` | funciones comunes (rutas, constantes, `chk`/`corte`/`fin`, `lysql` en solo lectura, `g`/`g101`, `arbol`, `web`) |
| [`ld_l0.sh`](liyben_3973/ld_l0.sh) | 128 | `ccd64ae7c568759ff8e6f9bafb5ff09287f73a39d4bae03bebd81e7614e3abe2` | L0 |
| [`ld_l2.sh`](liyben_3973/ld_l2.sh) | 45 | `dc6d69e02814f80033035bf2a7a8e2795deed25723c48569c3296b5b2f7a7387` | L2 |
| [`ld_l4.sh`](liyben_3973/ld_l4.sh) | 107 | `35716b0a7c0e9fff3bce59fdff714ba6c76dc081542b1e41a7677a156c42baa8` | L4 |
| [`ld_l4b.sh`](liyben_3973/ld_l4b.sh) | 169 | `2c5a0a06f717ddf1a2297d6931c27c4696dd4df366a8bc87de519f89158f3cfe` | L4b |
| [`ld_l5.sh`](liyben_3973/ld_l5.sh) | 43 | `516ada0765906e7510b31d9640e0fd3b24dea59a23b06d918b22c28974fe7295` | L5 |
| [`ld_l6.sh`](liyben_3973/ld_l6.sh) | 99 | `832597e672eb8eec325f1b98b7f8ded1cb473ff6a5438be7eb71f54691c803e4` | L6 |
| [`ld_l8.sh`](liyben_3973/ld_l8.sh) | 34 | `9625216112d3954dcd893c299d385083e495f594801389052cf516638e76357c` | L8 |
| [`ld_f2.sh`](liyben_3973/ld_f2.sh) | 20 | `5b8e59578bc6038d5c545f9bbffb4831132df5ca7ad15d6418f03591ae3560cf` | F2 |
| [`l0_b.sql`](liyben_3973/l0_b.sql) | 171 | `85394c9767b647cefc977c1be57af555a0a5b7c6f0dbb16ddcacfd373eb3cf21` | L0, B (= Y4 B) |
| [`l0_antes.sql`](liyben_3973/l0_antes.sql) | 259 | `26d8194e3cbf43607420c60a312ac91a443e86741f7f33dc3b210c609b3e514c` | L0, C y P-21 (= Y4 C) |
| [`l4b_estado.sql`](liyben_3973/l4b_estado.sql) | 37 | `8b4ee8af026ee5c0117394f54858b9665c2abc5518d6ff11e4046cb2d7ee9c5b` | L4b, estado (= Y6 v3) |
| [`l4b_foto.sql`](liyben_3973/l4b_foto.sql) | 2 | `d8102a5de47136b1d4e26360e0415fb831995afaa471dfd7fb4c7113effb533f` | L4b, foto de las traducciones (= Y6 v3) |
| [`l4b.py`](liyben_3973/l4b.py) | 143 | `b7827d7dc172b9ea4caba42061a8276a72777ed61354bbfc293b3a55ed970c98` | L4b, script del `odoo shell` (= Y6 v3) |
| [`l6_despues.sql`](liyben_3973/l6_despues.sql) | 143 | `d58c9f7188422273f4ea1e88aaee88441b474cc6425a4a2dd1a63d5d23110fc0` | L6 (= Y7) |
| [`d50_vaciar.sh`](liyben_3973/d50_vaciar.sh) | 102 | `301a0dd070bc980455d75e4e701bf85f0e9d8036b319b94c5099587cc55a3797` | L0 (ensayo) y L4 (VACIAR); D50 |
| [`ly_i0.sh`](liyben_3973/ly_i0.sh) | 224 | `4e5939f65f3f414c7070b2d7d612b49d8e120a27f418b81e43f7175a8042284d` | L0 (I0, del ensayo) |

En el equipo (no van al VPS): [`ld_e0.sh`](liyben_3973/ld_e0.sh) (47 líneas, `da4a9f92…`), [`ld_e1.sh`](liyben_3973/ld_e1.sh) (60 líneas, `9b7aa1bd…`), [`ld_l3.sh`](liyben_3973/ld_l3.sh) (64 líneas, `5d845e5f…`), [`ld_f0.sh`](liyben_3973/ld_f0.sh) (35 líneas, `10568763…`), [`ld_f1.sh`](liyben_3973/ld_f1.sh) (30 líneas, `52f228d8…`); texto y huella completa en su apartado.

Las funciones comunes, que cargan todas las tandas con «.» (no se lanza sola):

Archivo [`liyben_3973/ld_comun.sh`](liyben_3973/ld_comun.sh): 41 líneas, SHA-256 `7886e6c4cbbd08412b67eff196a7c6ae36a58e17d5126ecf8620ede02157511d`.

```bash
# Funciones comunes de las tandas del despliegue en LIYBEN (ld_*.sh). No se lanza: lo cargan las tandas con «.».
# Rutas del VPS (I0, 19/11/2026) y del equipo de Sergio.
LD=/tmp/liyben_3973
DE=~/pns_ai_3973/liyben/despliegue
COMPOSE=/opt/odoo
CLON=/opt/odoo/addons/custom/third_party
LOGF=/opt/odoo/logs/odoo-server.log
FS=/opt/odoo/odoo-web-data/.local/share/Odoo/filestore/LIYBEN
RAMA_ANTES=14.0-pns-ai-3
COMMIT_ANTES=578859b
RAMA=14.0-pns-ai-3973
ARBOL_RAMA="688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
VERS_RAMA="pns_ai_chatboo|installed|14.0.2.1.587 pns_ai_mcp|installed|14.0.3.1.973 pns_base|installed|14.0.1.2.69"
F=0
chk() {
  if [ "$2" = "$3" ]; then echo "OK      $1"
  elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
  else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
}
una() { tr '\n' ' ' | sed 's/ *$//'; }
sec() { printf '%s\n' "$1" | awk -v s="## $2" '/^## /{p = ($0 == s); next} p'; }
corte() { [ "$F" = 0 ] || { echo "== $TANDA: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
fin() { if [ "$F" = 0 ]; then echo "== $TANDA: TODO OK.${1:+ $1}"; else echo "== $TANDA: $F FALLO(S). No sigas: pega la salida."; fi; }
# PostgreSQL de LIYBEN en el VPS, sesión forzada a solo lectura (como I0)
lysql() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_db \
    sh -c 'psql -U "$POSTGRES_USER" -d LIYBEN -X -q -At -F "|"' 2>&1; }
# git del clon sin escribir (como ubuntu) y git que escribe (como el UID 101, §3.2 de la instalación)
g() { git --no-optional-locks -c safe.directory="$CLON" -C "$CLON" "$@"; }
g101() { sudo -n -u messagebus env HOME=/tmp git -c safe.directory="$CLON" -C "$CLON" "$@"; }
# archivos y huella de los tres pns_* de una carpeta (como E0 y T0 del staging)
arbol() {
  ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l ) | tr -d ' '
  ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 \
      | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1 )
}
web() { ( cd "$COMPOSE" && docker compose ps --status running --services 2>/dev/null | grep -cx web || true ); }
# última salida de una tanda (por nombre) y si termina con su marca
ultima() { ls -t $1 2>/dev/null | head -1; }
marca() { if [ -n "$1" ] && [ -f "$1" ]; then grep -cx -- "$2" "$1" || true; else echo 0; fi; }
# nombre de salida nuevo, sin pisar ninguno
nueva() { local o="$1-$(date +%Y%m%d-%H%M%S)$2"; [ ! -e "$o" ] || { echo "Ya existe $o: vuelve a lanzarla dentro de un segundo" >&2; return 1; }; printf '%s' "$o"; }
```

### Prueba de las tandas (19/11/2026, entorno de Claude)

- **Montaje:** repo de prueba con historia real (commit «antes» con el `ai/` de `_fabricante/3.1.782`, que reproduce la
  lista `f413c755…d4` y «solo `CLAUDE.md`»; árbol actual, 688 / `0dc381e0…`), remoto `bare`, copia del equipo y clon del
  «VPS» del UID 101 con refspec solo de `14.0`. Simulados: `ssh`, `scp`, `docker` (`ps`, `compose ps/stop/start/run -u/run
  shell`, `exec psql/pg_dump/pg_restore`), `sudo`, `id`, `curl`, `odoo-dev` y `ly_i0.sh`; las respuestas SQL y del shell,
  sacadas de las salidas del ensayo (`y4_antes`, `y7_despues`, Y6 v3), con crons activos y tokens 0. En la copia probada,
  las constantes de hash se cambiaron por las del repo de prueba (`COMMIT_ANTES`, `BASE_DOC`, `STAGING`).
- **Positivo:** E0 → E1 → L0 → L2 → L3 → L4 → L4b comprobar → APLICAR_BP → L5 → L6 → L8 → F1 → F2, todas con `TODO OK`;
  F0 comprobar y BORRAR.
- **Negativos (FALLO y nada cambiado):** E0 con el árbol sucio y con un cambio fuera de `docs/`; E1 con la carpeta ya
  creada y con un archivo alterado; L0 con un archivo alterado en el VPS, I0 en FALLO, la rama remota movida y otro
  perfil de tokens; L2 con una L0 de más de una hora y con el clon sucio; L3 con el web en marcha y sin SSH; L4 sin copia,
  con la compuerta de D50 fallando, con el `-u` con error (FALLO; el estado lo decide E) y repetida; L4b APLICAR_BP sin
  comprobar, con otra medida (sin commit) y repetida, y comprobar con el web en marcha; L5 sin APLICAR_BP y con ERROR en
  el arranque (FALLO con el web ya en marcha); L6 con tokens; F2 con otra huella.
- **Queda por validar en el VPS:** `ly_i0.sh` lanzada con `bash` desde `/tmp/liyben_3973` (el 19/11 se usó por
  `ssh … 'bash -s' <`); `sudo -n` como `messagebus` tras `sudo -v`; que `ubuntu` lea `odoo-server.log` y todo el
  filestore (L0 lo comprueba antes del corte); `docker compose run … odoo shell` con `logfile` (la salida del script por
  la salida estándar, los registros al log); el `ls-remote` y el `fetch` con las credenciales del clon; `curl` con el web
  parado (INFO).

---

## 2. Tandas

### E0. Equipo: commit a desplegar y módulos (solo lectura)

**[LECTURA del repo; ALTERA solo `/tmp` del equipo, que borra al acabar, y `~/pns_ai_3973/liyben/despliegue/`]** Antes,
en GitHub Desktop, «Fetch origin». Comprueba la rama, el árbol limpio y al día con la remota (D58), que de `c6ec077` al
commit solo cambia `docs/` y que `578859b` es antecesor; extrae los tres módulos del commit y comprueba el árbol (688 /
`0dc381e0…`), las versiones, la lista de `ai/` de `578859b` al commit (Y4 A: A 15, D 12, M 19, `f413c755…d4`) y que
fuera de `pns_*` y `docs/` solo cambia `CLAUDE.md`; y que las tandas del commit son las de la copia de trabajo. Guarda el
hash en `commit.txt`.

```bash
bash ~/GitHub/third_party/docs/pendiente/liyben_3973/ld_e0.sh
```

Esperado: todo `OK` y `== LD E0: TODO OK. Sigue con E1.`

Archivo [`liyben_3973/ld_e0.sh`](liyben_3973/ld_e0.sh): 47 líneas, SHA-256 `da4a9f9204ac9ada043ba835b69487a6e2af82899a0a8b461a09cf1e9be40066`.

```bash
ld_e0() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD E0"
  REPO=~/GitHub/third_party
  BASE_DOC=c6ec077
  STAGING=5d0559b
  mkdir -p "$DE" && chmod 700 "$DE" || exit 1
  O=$(nueva "$DE/e0" .txt) || exit 1
  T=$(mktemp -d /tmp/ld_e0.XXXXXX) || exit 1
  trap 'rm -rf -- "$T"' EXIT
  {
  cd "$REPO" || exit 1
  echo "== $TANDA (equipo, solo lectura del repo; extracción temporal en $T, se borra al acabar): $(date '+%F %T')"
  echo "== 1. Repo y commit que se despliega (D58: HEAD de la rama en el commit del documento)"
  chk "rama" "$(git rev-parse --abbrev-ref HEAD)" "$RAMA"
  chk "árbol de trabajo limpio" "$(git status --porcelain | wc -l | tr -d ' ')" 0
  echo "copia local de la remota (haz «Fetch origin» en GitHub Desktop antes): $(git log -1 --format='%h %ci' '@{u}' 2>&1)"
  chk "al día con su rama remota (delante|detrás)" "$(git rev-list --left-right --count 'HEAD...@{u}' 2>&1 | tr '\t' '|')" "0|0"
  C=$(git rev-parse HEAD)
  echo "commit a desplegar: $(git log -1 --format='%H %s' "$C")"
  chk "$BASE_DOC es antecesor del commit" "$(git merge-base --is-ancestor "$BASE_DOC" "$C" && echo si || echo no)" si
  chk "archivos fuera de docs/ que cambian de $BASE_DOC al commit" "$(git diff --name-only "$BASE_DOC" "$C" -- . ':(exclude)docs' | una)" ""
  chk "$COMMIT_ANTES (montado en LIYBEN) es antecesor del commit" "$(git merge-base --is-ancestor "$COMMIT_ANTES" "$C" && echo si || echo no)" si
  corte "repo"

  echo "== 2. Módulos del commit (= $STAGING, lo validado en el staging y en el ensayo)"
  chk "commits posteriores a $STAGING que tocan los módulos" "$(git rev-list --count "$STAGING..$C" -- pns_base pns_ai_mcp pns_ai_chatboo)" 0
  git archive "$C" pns_base pns_ai_mcp pns_ai_chatboo | tar -x -C "$T" || { echo "FALLO   git archive"; F=$((F + 1)); corte "git archive"; }
  chk "árbol de los módulos (archivos y huella)" "$(arbol "$T" | una)" "$ARBOL_RAMA"
  chk "versiones" "$(for m in pns_base pns_ai_mcp pns_ai_chatboo; do grep -oE "'version': *'[^']+'" "$T/$m/__manifest__.py" | grep -oE "[0-9][0-9.]+"; done | una)" "14.0.1.2.69 14.0.3.1.973 14.0.2.1.587"
  DF=$(git diff --no-renames --name-status "$COMMIT_ANTES" "$C" -- pns_ai_mcp/ai pns_ai_chatboo/ai | LC_ALL=C sort)
  chk "cambios en ai/ de $COMMIT_ANTES al commit, por tipo (Y4 A)" "$(printf '%s\n' "$DF" | cut -f1 | LC_ALL=C sort | uniq -c | awk '{printf "%s %s ", $2, $1}' | sed 's/ $//')" "A 15 D 12 M 19"
  chk "huella de esa lista (= la del fabricante de 3.1.782 a 3.1.973)" "$(printf '%s\n' "$DF" | sha256sum | cut -d' ' -f1)" f413c755fcfaf6e0ed7b1f51feb7a62b621323173496d3218f6b43715d8438d4
  chk "archivos fuera de pns_* y docs/ que cambian de $COMMIT_ANTES al commit (el clon de LIYBEN tiene todo third_party)" "$(git diff --name-only "$COMMIT_ANTES" "$C" -- . ':(exclude)pns_base' ':(exclude)pns_ai_mcp' ':(exclude)pns_ai_chatboo' ':(exclude)docs' | una)" "CLAUDE.md"
  corte "módulos"

  echo "== 3. Tandas del despliegue en el commit (docs/pendiente/liyben_3973/)"
  chk "tandas del commit = las de la copia de trabajo" "$(git diff --name-only "$C" -- docs/pendiente/liyben_3973 | wc -l | tr -d ' ')" 0
  printf '%s\n' "$C" > "$DE/commit.txt"
  echo "guardado: $DE/commit.txt ($C)"
  fin "Sigue con E1."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_e0
```

### E1. Equipo: copia de las tandas al VPS

**[ALTERA el VPS: solo crea `/tmp/liyben_3973`]** Exige la última E0 con `TODO OK`, su commit = HEAD y el árbol
limpio; saca con `git archive` las tandas del commit y comprueba las huellas de los 17 archivos que van al VPS (§1)
contra la lista que lleva dentro; crea `/tmp/liyben_3973` (700; **falla si ya existe**) y copia por `scp` los 17,
`commit.txt` y `huellas.txt`; comprueba en el VPS las huellas, los permisos y el número de archivos.

```bash
bash ~/GitHub/third_party/docs/pendiente/liyben_3973/ld_e1.sh
```

Esperado: todo `OK` (en el VPS, `HUELLAS_OK 700 19`), la huella de la lista copiada y
`== LD E1: TODO OK. Sigue con L0 en el VPS.`

Archivo [`liyben_3973/ld_e1.sh`](liyben_3973/ld_e1.sh): 60 líneas, SHA-256 `9b7aa1bd80dc6d18160b41858a4673b0c1a96c7e5bfb8bb2fa235d6ab1c61363`.

```bash
ld_e1() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD E1"
  REPO=~/GitHub/third_party
  # Archivos que van al VPS y su SHA-256 (los del commit del documento)
  ESPERADAS='7886e6c4cbbd08412b67eff196a7c6ae36a58e17d5126ecf8620ede02157511d  ld_comun.sh
ccd64ae7c568759ff8e6f9bafb5ff09287f73a39d4bae03bebd81e7614e3abe2  ld_l0.sh
dc6d69e02814f80033035bf2a7a8e2795deed25723c48569c3296b5b2f7a7387  ld_l2.sh
35716b0a7c0e9fff3bce59fdff714ba6c76dc081542b1e41a7677a156c42baa8  ld_l4.sh
2c5a0a06f717ddf1a2297d6931c27c4696dd4df366a8bc87de519f89158f3cfe  ld_l4b.sh
516ada0765906e7510b31d9640e0fd3b24dea59a23b06d918b22c28974fe7295  ld_l5.sh
832597e672eb8eec325f1b98b7f8ded1cb473ff6a5438be7eb71f54691c803e4  ld_l6.sh
9625216112d3954dcd893c299d385083e495f594801389052cf516638e76357c  ld_l8.sh
5b8e59578bc6038d5c545f9bbffb4831132df5ca7ad15d6418f03591ae3560cf  ld_f2.sh
85394c9767b647cefc977c1be57af555a0a5b7c6f0dbb16ddcacfd373eb3cf21  l0_b.sql
26d8194e3cbf43607420c60a312ac91a443e86741f7f33dc3b210c609b3e514c  l0_antes.sql
8b4ee8af026ee5c0117394f54858b9665c2abc5518d6ff11e4046cb2d7ee9c5b  l4b_estado.sql
d8102a5de47136b1d4e26360e0415fb831995afaa471dfd7fb4c7113effb533f  l4b_foto.sql
b7827d7dc172b9ea4caba42061a8276a72777ed61354bbfc293b3a55ed970c98  l4b.py
d58c9f7188422273f4ea1e88aaee88441b474cc6425a4a2dd1a63d5d23110fc0  l6_despues.sql
301a0dd070bc980455d75e4e701bf85f0e9d8036b319b94c5099587cc55a3797  d50_vaciar.sh
4e5939f65f3f414c7070b2d7d612b49d8e120a27f418b81e43f7175a8042284d  ly_i0.sh'
  [ -n "${VPS_PORT:-}" ] && [ -n "${VPS_DEST:-}" ] || { echo "Faltan VPS_PORT y VPS_DEST: lánzalas con la línea read de antes"; exit 1; }
  O=$(nueva "$DE/e1" .txt) || exit 1
  T=$(mktemp -d /tmp/ld_e1.XXXXXX) || exit 1
  trap 'rm -rf -- "$T"' EXIT
  {
  echo "== $TANDA (equipo: copia de las tandas al VPS, en $LD; en el VPS solo crea esa carpeta): $(date '+%F %T')"
  echo "== 1. Comprobaciones previas"
  E0=$(ultima "$DE/e0-*.txt")
  chk "última E0 (${E0##*/}) con TODO OK" "$(marca "$E0" '== LD E0: TODO OK. Sigue con E1.')" 1
  C=$(git -C "$REPO" rev-parse HEAD)
  chk "commit de E0 = HEAD del repo" "$(cat "$DE/commit.txt" 2>/dev/null)" "$C"
  chk "árbol de trabajo limpio" "$(git -C "$REPO" status --porcelain | wc -l | tr -d ' ')" 0
  corte "comprobaciones previas"
  git -C "$REPO" archive "$C" docs/pendiente/liyben_3973 | tar -x -C "$T" || { echo "FALLO   git archive"; F=$((F + 1)); corte "git archive"; }
  S="$T/docs/pendiente/liyben_3973"
  LISTA=$(printf '%s\n' "$ESPERADAS" | awk '{print $2}')
  H=$( cd "$S" && for f in $LISTA; do sha256sum "$f" 2>&1; done )
  chk "huellas de los $(printf '%s\n' "$LISTA" | wc -l | tr -d ' ') archivos del commit = las del documento" "$H" "$ESPERADAS"
  [ "$F" = 0 ] || printf '%s\n' "$H" | sed 's/^/   /'
  corte "huellas"
  cp "$DE/commit.txt" "$S/commit.txt"
  ( cd "$S" && sha256sum $LISTA commit.txt ) > "$T/huellas.txt"

  echo "== 2. [ALTERA el VPS: crea $LD] Copia por scp"
  ssh -T -p "$VPS_PORT" "$VPS_DEST" "test ! -e $LD && mkdir -m 700 $LD" || { echo "FALLO   $LD ya existe en el VPS o no se pudo crear: no se ha copiado nada"; F=$((F + 1)); corte "carpeta en el VPS"; }
  ( cd "$S" && scp -q -P "$VPS_PORT" $LISTA commit.txt "$T/huellas.txt" "$VPS_DEST:$LD/" )
  chk "scp" "$?" 0
  R=$(ssh -T -p "$VPS_PORT" "$VPS_DEST" "cd $LD && chmod 600 * && sha256sum -c --quiet huellas.txt && echo HUELLAS_OK; stat -c %a $LD; ls -1 | wc -l")
  chk "en el VPS: huellas, permisos de $LD y archivos" "$(printf '%s\n' "$R" | una)" "HUELLAS_OK 700 $(( $(printf '%s\n' "$LISTA" | wc -l) + 2 ))"
  echo "huella de la lista copiada: $(sha256sum "$T/huellas.txt" | cut -d' ' -f1)"
  cp "$T/huellas.txt" "$DE/huellas_vps.txt"
  fin "Sigue con L0 en el VPS."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_e1
```

### L.0 y L0. VPS: sesión y comprobaciones previas, I0, B, C, P-21 y D50 en ensayo (solo lectura)

**L.0.** Abrir la sesión SSH interactiva en el VPS como `ubuntu` (§1). Las tandas se lanzan con su ruta completa; nada
que pegar más que la orden.

**L0 [LECTURA; escribe solo en `/tmp/liyben_3973`]** No cambia LIYBEN ni el clon. Con el web **en marcha**:
1. huellas de `/tmp/liyben_3973` y commit;
2. I0 (`ly_i0.sh` del ensayo, D59), que debe dar `TODO OK`;
3. lo que necesitan L2 a L5: UID 101, `sudo -n`, `ls-remote` de la rama = commit, log y filestore legibles entero y 2 GB
   libres;
4. B (`l0_b.sql`): esquema de 3.1.782 (79 columnas, 5 `fit_*`, sin tablas de 3.1.973) y correspondencia exacta de los 56
   contextos y las 10 skills con sus archivos (0 con dueño);
5. C (`l0_antes.sql`): el «antes» completo (lo usa L6), contra I0: versiones de 3.1.782, 215 instalados, ningún
   dependiente, AI Administrators 2, 6 y 7 (el 2 sin AI Conversational), proveedores 1 inactivo y 2 activo, los 6 crons
   de `pns_*` activos, NUEVO-2 con `model.gc_expired()`, 0 operaciones no terminales, 10 skills y 56 contextos sin
   xml_id, `es_ES` activo, 8 tokens e `iap_account` 1; y P-21: 13 contextos reescritos sin edición, 3 nuevos, 0
   retirados; skills `billing`, `financial_health` y `forecast` reescritas sin edición, las 6 retiradas, 0 adoptadas, 0
   archivadas;
6. D50 en ensayo (`d50_vaciar ensayo`, termina en `ROLLBACK`).

Lo que cambia con el uso (último `-u`, servidores API, diario, Chatboo, `ai_log`, traducciones) sale como INFO si
difiere de I0.

```bash
bash /tmp/liyben_3973/ld_l0.sh
```

Esperado: `OK` en todo lo que bloquea; INFO fijas: el origen del clon (esquema y host), si es superficial, el tamaño del
log y del filestore y la nota de «solo uso»; `== LD L0: TODO OK. Corte: pega la salida. Después L1 (interfaz) y L2,
antes de una hora.` Salidas: `l0-*.txt`, `l0_antes-*.txt` (el «antes», con su huella) y `l0_i0-*.txt`.

Archivo [`liyben_3973/ld_l0.sh`](liyben_3973/ld_l0.sh): 128 líneas, SHA-256 `ccd64ae7c568759ff8e6f9bafb5ff09287f73a39d4bae03bebd81e7614e3abe2`.

```bash
ld_l0() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD L0"
  sb() { sec "$RB" "$1"; }
  sc() { sec "$RC" "$1"; }
  ver() { echo "-- $2"; sc "$1" | sed 's/^/   /'; }
  [ "$(cd "$(dirname "$0")" && pwd)" = "$LD" ] || { echo "Lánzala desde $LD: bash $LD/ld_l0.sh"; exit 1; }
  sudo -v || { echo "FALLO   sudo (hace falta para git como el UID 101). No se ha seguido."; exit 1; }
  O=$(nueva "$LD/l0" .txt) || exit 1
  A=$(nueva "$LD/l0_antes" .txt) || exit 1
  I=$(nueva "$LD/l0_i0" .txt) || exit 1
  {
  echo "== $TANDA (VPS, solo lectura: no escribe en LIYBEN, ni en el clon, ni fuera de $LD): $(date -u '+%F %T') UTC"
  echo "== 1. Tandas y commit"
  chk "huellas de $LD (las que copió E1)" "$(cd "$LD" && sha256sum -c --quiet huellas.txt 2>&1 | wc -l | tr -d ' ')" 0
  C=$(cat "$LD/commit.txt" 2>/dev/null)
  chk "commit a desplegar (40 caracteres hexadecimales)" "$(printf '%s' "$C" | grep -cxE '[0-9a-f]{40}' || true)" 1
  echo "commit: $C"
  corte "tandas"

  echo "== 2. I0 (ly_i0.sh del ensayo, solo lectura; salida completa en $I)"
  bash "$LD/ly_i0.sh" > "$I" 2>&1
  chk "I0 terminó con TODO OK" "$(marca "$I" '== I0: TODO OK')" 1
  grep -E '^(FALLO|INFO) ' "$I" | sed 's/^/   /'
  grep -E '^(tamaño de LIYBEN|módulos instalados|traducciones es_ES|filestore|iap_account)' "$I" | sed 's/^/   /'
  grep -A2 '^== 6\.' "$I" | tail -1 | sed 's/^/   disco: /'
  echo "-- caso b de PNS-82 por modelo y creador (decisión 7; I0 del 19/11: 67/18/2/1)"
  grep -A6 '^-- caso b por modelo' "$I" | grep '^   ' | head -6
  corte "I0"

  echo "== 3. Lo que necesitan L2 a L5"
  chk "web en marcha (se para en L2)" "$(web)" 1
  chk "usuario messagebus = UID 101" "$(id -u messagebus 2>&1)" 101
  chk "propietario del clon" "$(stat -c %u "$CLON")" 101
  chk "sudo sin pedir otra vez la contraseña (sudo -n)" "$(sudo -n true 2>&1 && echo si || echo no)" si
  echo "INFO    origen del clon (esquema y host, sin usuario ni credenciales): $(g remote get-url origin 2>&1 | sed -E 's#^([a-z+]+://)([^@/]*@)?([^/:]+).*#\1\3#; s#^[^@/]+@([^:]+):.*#ssh \1#')"
  echo "INFO    clon superficial: $(g rev-parse --is-shallow-repository 2>&1)"
  RL=$(g101 ls-remote origin "refs/heads/$RAMA" 2>&1)
  chk "ls-remote de $RAMA como el UID 101 (la rama remota está en el commit)" "$(printf '%s\n' "$RL" | cut -f1 | head -1)" "$C"
  [ "$(printf '%s\n' "$RL" | cut -f1 | head -1)" = "$C" ] || printf '%s\n' "$RL" | head -3 | cut -c1-120 | sed 's/^/   /'
  chk "log del servidor legible ($LOGF)" "$(test -r "$LOGF" && echo si || echo no)" si
  echo "INFO    tamaño del log: $(stat -c %s "$LOGF" 2>&1) bytes"
  chk "filestore legible entero (archivos sin lectura | carpetas sin entrada)" "$(find "$FS" -type f ! -readable 2>/dev/null | wc -l | tr -d ' ')|$(find "$FS" -type d ! -executable 2>/dev/null | wc -l | tr -d ' ')" "0|0"
  echo "INFO    filestore: $(find "$FS" -type f 2>/dev/null | wc -l | tr -d ' ') archivos, $(du -sb "$FS" 2>/dev/null | cut -f1) bytes"
  chk "espacio libre en el VPS (al menos 2 GB; L3 no escribe aquí)" "$( [ "$(df --output=avail -B1 / | tail -1 | tr -d ' ')" -ge 2000000000 ] && echo si || echo no)" si
  corte "lo que necesitan L2 a L5"

  echo "== 4. B: esquema de LIYBEN y correspondencia con los archivos de 3.1.782 (l0_b.sql = Y4 B)"
  RB=$(lysql < "$LD/l0_b.sql")
  chk "consultas sin error" "$(printf '%s\n' "$RB" | grep -ciE "ERROR:|psql: error" || true)" 0
  printf '%s\n' "$RB" | grep 'ERROR:' | head -5 | sed 's/^/   /'
  chk "marcador final de la salida SQL" "$(printf '%s\n' "$RB" | grep -cx '## fin' || true)" 1
  chk "columnas que usa Y4 (en la lista|presentes)" "$(sb columnas | awk -F'|' '{n++; if ($2 == "t") p++} END {printf "%d|%d\n", n, p}')" "79|79"
  chk "columnas que faltan" "$(sb columnas | awk -F'|' '$2 != "t" {print $1}' | una)" ""
  chk "columnas fit_* de ai_provider (3.1.782: 5, sin fit_design)" "$(sb 'columnas fit')" "fit_audio fit_conversation fit_decision fit_video fit_vision"
  chk "ai_provider existe | tablas de 3.1.973 ya presentes (ai_provider_role, chatboo_canvas_page)" "$(sb tablas)" "t|0"
  cuenta() { sb "$1" | awk -F'|' '{if ($2 != "") f++; if ($1 == "fila sin archivo") s++; if ($1 == "archivo sin fila") a++; if ($6 == "t") d++; if ($1 == "ok") o++} END {printf "%d|%d|%d|%d|%d\n", f, s, a, d, o}'; }
  raros() { sb "$1" | awk -F'|' '$1 != "ok" || $6 == "t"' | head -20 | sed 's/^/   /'; }
  chk "contextos frente a los 56 archivos (filas|sin archivo|archivos sin fila|con dueño|emparejados)" "$(cuenta 'contextos archivos')" "56|0|0|0|56"
  [ -z "$(raros 'contextos archivos')" ] || { echo "-- contextos no emparejados o con dueño (caso|id|code|source_module|rel_path|con dueño; 20 como mucho)"; raros 'contextos archivos'; }
  chk "skills frente a los 10 archivos (filas|sin archivo|archivos sin fila|con dueño|emparejadas)" "$(cuenta 'skills archivos')" "10|0|0|0|10"
  [ -z "$(raros 'skills archivos')" ] || { echo "-- skills no emparejadas o con dueño (caso|id|code|source_module|rel_path|con dueño; 20 como mucho)"; raros 'skills archivos'; }
  corte "B (esquema y correspondencia)"

  echo "== 5. C: «antes» (l0_antes.sql = Y4 C; salida SQL completa en $A, para L6)"
  RC=$(lysql < "$LD/l0_antes.sql")
  printf '%s\n' "$RC" > "$A"
  echo "guardado: $A ($(wc -l < "$A" | tr -d ' ') líneas, SHA-256 $(sha256sum "$A" | cut -d' ' -f1))"
  chk "consultas sin error" "$(printf '%s\n' "$RC" | grep -ciE "ERROR:|psql: error" || true)" 0
  printf '%s\n' "$RC" | grep 'ERROR:' | head -5 | sed 's/^/   /'
  chk "marcador final de la salida SQL" "$(printf '%s\n' "$RC" | grep -cx '## fin' || true)" 1
  chk "versiones (nombre|estado|versión), = I0" "$(sc versiones | una)" "pns_ai_chatboo|installed|14.0.2.1.453 pns_ai_mcp|installed|14.0.3.1.782 pns_base|installed|14.0.1.2.32"
  chk "módulos a medio instalar o actualizar" "$(sc 'estados a medias')" 0
  chk "módulos instalados, = I0" "$(sc instalados)" 215
  chk "dependientes de los pns_*" "$(sc dependientes | una)" ""
  chk "fecha del último -u de pns_ai_mcp y pns_ai_chatboo (write_date, UTC: $(sc 'ultimo -u'))" "$(sc 'ultimo -u' | cut -c1-10)" 2026-10-16 info
  chk "AI Administrators (id|activo|Ajustes|contraseña local|AI Conversational), = I0" "$(sc 'ai admins' | una)" "2|t|t|t|f 6|t|t|t|t 7|t|t|t|t"
  chk "P-11 (AI Administrators|sin AI Conversational): el 2 lo ganará en el -u (D64)" "$(sc p11)" "3|1"
  chk "proveedores (id|activo|protocolo|modelo|conv|audio|visión|vídeo|decisión|sin failover externo), = I0" "$(sc proveedores | una)" "1|f|openai|models/gemini-3.5-flash|t|f|t|f|t|t 2|t|openai|Qwen3.5-9B|t|f|t|f|f|f"
  ver cadena "cadena ai_agent_provider, sin api_key (id|agente|prioridad|activo|skip_sync_fallback|provider_id|proveedor activo); para L6"
  chk "crons de pns_* (xml_id|activo|intervalo|numbercall): los 6 de I0, activos" "$(sc crons | una)" "pns_ai_chatboo.ir_cron_chatboo_async_maintenance|t|5 minutes|-1 pns_ai_mcp.ir_cron_ai_api_result_cache_gc|t|1 hours|-1 pns_ai_mcp.ir_cron_ai_fetch_cache_gc|t|1 hours|-1 pns_ai_mcp.ir_cron_ai_log_retention|t|1 days|-1 pns_ai_mcp.ir_cron_ai_safe_operation_expire|t|5 minutes|-1 pns_base.ir_cron_pns_export_purge|t|1 hours|-1"
  echo "INFO    crons activos en LIYBEN (todos los módulos; L6 espera uno más): $(sc 'crons activos')"
  chk "crons de NUEVO-2 antes del -u (el parche 35 los corregirá), = I0" "$(sc 'crons nuevo2' | una)" "ir_cron_ai_api_result_cache_gc|model.gc_expired() ir_cron_ai_fetch_cache_gc|model.gc_expired()"
  chk "parámetros (clave|valor), = I0" "$(sc parametros | una)" "pns_ai_chatboo.history_retention_days|30 pns_ai_mcp.log_retention_days|30 pns_ai_mcp.url_access_policy|whitelist_only"
  chk "operaciones pending o confirmed sin ejecutar, = I0" "$(sc 'operaciones no terminales' | una)" ""
  chk "operaciones no terminales con pasos sobre ai.trusted.action (parche 32)" "$(sc 'operaciones trusted')" 0
  ver 'operaciones por status' "ai_safe_operation por status (status|n); para L6"
  ver trusted "ai_trusted_action (n|max_id); para L6"
  chk "servidores ai.api.server (PNS-17), = I0" "$(sc 'servidores api')" 0 info
  chk "diario (filas|unlink en papelera|reescritas por otro), = I0" "$(sc diario)" "2|0|0" info
  chk "Chatboo (sesiones|id máximo|primera, mes|usuarios), = I0" "$(sc chatboo)" "1|1|2026-10|1" info
  chk "ai_log (filas|con agent_id|max_id), = I0" "$(sc ai_log)" "0|0|0" info
  chk "skills (code|activa|sistema|con xml_id), = I0" "$(sc skills | una)" "annual_billing|t|t|f billing|t|t|f credit_facility|t|t|f customer_risk_analysis|t|t|f dashboard|t|t|f financial_health|t|t|f forecast|t|t|f sys_info|t|t|f users_all|t|t|f users_logged|t|t|f"
  ver 'skills detalle' "skills (id|code|command|source_module|rel_path|activa|write_uid); para L6"
  chk "contextos (total|activos|con xml_id), = I0" "$(sc contextos)" "56|56|0"
  chk "contextos por módulo (source_module|n|activos)" "$(sc 'contextos por modulo' | una)" "pns_ai_chatboo|3|3 pns_ai_mcp|53|53"
  ver 'modulos iap' "módulos crm, iap, partner_autocomplete y sms (name|state); para L6"
  chk "es_ES activo, = I0" "$(sc idioma)" "es_ES|t"
  chk "traducciones es_ES, = I0" "$(sc 'traducciones es_ES')" 45482 info
  chk "tokens de registro (los 8 de D50; los vacía L4), = I0" "$(sc tokens)" 8
  chk "iap_account (filas), = I0" "$(sc iap)" 1

  echo "== 5b. P-21 de LIYBEN (qué hará el -u de 3.1.973 con los contextos y skills de fábrica)"
  ver 'p21 contextos reescribe' "contextos que reescribe (módulo:rel_path|estado|id|write_uid)"
  echo "-- contextos que reescribe: resumen (n estado)"; sc 'p21 contextos reescribe' | cut -d'|' -f2 | LC_ALL=C sort | uniq -c | sed 's/^ */   /'
  chk "contextos que reescribe sin edición (con o sin uso posterior al último -u)" "$(sc 'p21 contextos reescribe' | cut -d'|' -f2 | grep -cE '^reescribe sin edición( \(solo uso\))?$' || true)" 13
  echo "INFO    «solo uso»: write_date posterior al último -u pero igual a last_used y write_uid 1 (el UPDATE del contador de uso, ai_context.py:1224-1231 de 3.1.782); no es una edición (no bloquea)"
  chk "contextos nuevos (code|estado)" "$(sc 'p21 contextos nuevos' | una)" "discovery_page_tab|falta: lo crea discovery_page_tab_es_ES|falta: lo crea page_tab|falta: lo crea"
  chk "contextos de fábrica sin archivo en 3.1.973 (los borraría)" "$(sc 'p21 contextos retirados' | una)" ""
  ver 'p21 skills reescribe' "skills que reescribe (code|estado|id|write_uid)"
  chk "skills que reescribe (code|estado)" "$(sc 'p21 skills reescribe' | cut -d'|' -f1,2 | una)" "billing|reescribe sin edición financial_health|reescribe sin edición forecast|reescribe sin edición"
  ver 'p21 skills retiradas' "skills retiradas: las borra (code|id|activa|write_uid)"
  chk "skills retiradas (code)" "$(sc 'p21 skills retiradas' | cut -d'|' -f1 | una)" "annual_billing credit_facility customer_risk_analysis sys_info users_all users_logged"
  chk "skills nuevas que ya existen (se adoptarían o chocarían)" "$(sc 'p21 skills nuevas que ya existen' | una)" ""
  chk "contextos y skills archivados" "$(sc 'p21 archivadas' | una)" ""
  corte "C y P-21"

  echo "== 6. D50 en ensayo (d50_vaciar.sh; termina en ROLLBACK)"
  R=$( . "$LD/d50_vaciar.sh" && d50_vaciar ensayo 2>&1 )
  printf '%s\n' "$R" | sed 's/^/   /'
  chk "D50 ensayo con TODO OK" "$(printf '%s\n' "$R" | grep -cx '== D50 (ensayo): TODO OK (ensayo: LIYBEN sin cambios)' || true)" 1
  fin "Corte: pega la salida. Después L1 (interfaz) y L2, antes de una hora."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_l0
```

### L1. Interfaz: antes del corte (solo Sergio)

1. **Avisar** a los usuarios de LIYBEN del corte (de L2 a L5).
2. **Chatboo:** como uno de los AI Administrators, abrir la sesión de Chatboo que hay (la 1, de 10/2026) y anotar si se
   abre y cómo se ve (base de L7).
3. **Sin «Test Connection»** ni turnos de IA: escriben en LIYBEN después del «antes» y L7 no los repite (decisión 4 del
   documento).

| Comprobación | Esperado | Obtenido |
|---|---|---|
| Aviso del corte | hecho | |
| Sesión antigua de Chatboo, antes | se anota: se abre sí/no, cómo se ve | |

**Corte.** Sergio pega L0 y anota L1; Claude lo contrasta antes de L2. L2 tiene que empezar antes de una hora desde L0.

### L2. VPS: la rama en el clon y parada del web

**[ALTERA el clon: solo referencias; ALTERA: corte del servicio]** Exige una L0 con `TODO OK` de menos de una hora, las
huellas, el web en marcha y el clon en `14.0-pns-ai-3` / `578859b`, limpio y sin la rama nueva. `fetch` de la rama con
refspec explícito como el UID 101 (§3.2); comprueba `origin/14.0-pns-ai-3973` = commit, `578859b` antecesor, el clon sin
cambios, `.git/` del UID 101 y el árbol de los módulos del commit (688 / `0dc381e0…`). Después, `docker compose stop
web`.

```bash
bash /tmp/liyben_3973/ld_l2.sh
```

Esperado: todo `OK`; `liyben.com/web/login` con 502, 503 o 504 (INFO si no); `== LD L2: TODO OK. Corte: web PARADO.
Sigue con L3 en el equipo.`

Archivo [`liyben_3973/ld_l2.sh`](liyben_3973/ld_l2.sh): 45 líneas, SHA-256 `dc6d69e02814f80033035bf2a7a8e2795deed25723c48569c3296b5b2f7a7387`.

```bash
ld_l2() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD L2"
  [ "$(cd "$(dirname "$0")" && pwd)" = "$LD" ] || { echo "Lánzala desde $LD: bash $LD/ld_l2.sh"; exit 1; }
  sudo -v || { echo "FALLO   sudo. No se ha seguido."; exit 1; }
  O=$(nueva "$LD/l2" .txt) || exit 1
  T=$(mktemp -d "$LD/l2_arbol.XXXXXX") || exit 1
  trap 'rm -rf -- "$T"' EXIT
  {
  echo "== $TANDA (VPS: trae la rama al clon y para el web): $(date -u '+%F %T') UTC"
  echo "== 1. Comprobaciones previas (solo lectura)"
  L0=$(ultima "$LD/l0-*.txt")
  chk "última L0 (${L0##*/}) con TODO OK" "$(marca "$L0" '== LD L0: TODO OK. Corte: pega la salida. Después L1 (interfaz) y L2, antes de una hora.')" 1
  chk "L0 de hace menos de una hora (si no, repite L0)" "$( [ -n "$L0" ] && [ $(( $(date +%s) - $(stat -c %Y "$L0") )) -lt 3600 ] && echo si || echo no)" si
  C=$(cat "$LD/commit.txt" 2>/dev/null)
  chk "huellas de $LD" "$(cd "$LD" && sha256sum -c --quiet huellas.txt 2>&1 | wc -l | tr -d ' ')" 0
  chk "web en marcha" "$(web)" 1
  chk "rama del clon" "$(g rev-parse --abbrev-ref HEAD 2>&1)" "$RAMA_ANTES"
  chk "HEAD del clon" "$(g rev-parse --short=7 HEAD 2>&1)" "$COMMIT_ANTES"
  chk "clon limpio (líneas de status)" "$(g status --porcelain 2>&1 | wc -l | tr -d ' ')" 0
  chk "la rama $RAMA no existe aún en el clon (local)" "$(g rev-parse -q --verify "refs/heads/$RAMA" >/dev/null && echo existe || echo no)" no
  corte "comprobaciones previas"

  echo "== 2. [ALTERA el clon: solo referencias] fetch de $RAMA como el UID 101, con refspec explícito (§3.2)"
  g101 fetch origin "+refs/heads/$RAMA:refs/remotes/origin/$RAMA" 2>&1 | sed 's/^/   /'
  chk "origin/$RAMA = commit del documento" "$(g rev-parse -q --verify "refs/remotes/origin/$RAMA" 2>&1)" "$C"
  chk "$COMMIT_ANTES es antecesor del commit" "$(g merge-base --is-ancestor "$COMMIT_ANTES" "$C" 2>/dev/null && echo si || echo no)" si
  chk "rama, HEAD y status del clon, sin cambios" "$(g rev-parse --abbrev-ref HEAD)|$(g rev-parse --short=7 HEAD)|$(g status --porcelain | wc -l | tr -d ' ')" "$RAMA_ANTES|$COMMIT_ANTES|0"
  chk "propietario de .git/ (archivos que no son del UID 101)" "$(find "$CLON/.git" ! -uid 101 2>/dev/null | wc -l | tr -d ' ')" 0
  g archive "$C" pns_base pns_ai_mcp pns_ai_chatboo | tar -x -C "$T" || echo "FALLO   git archive del commit"
  chk "árbol de los módulos del commit (archivos y huella)" "$(arbol "$T" | una)" "$ARBOL_RAMA"
  corte "fetch"

  echo "== 3. [ALTERA: corte del servicio] docker compose stop web, a las $(date -u +%T) UTC"
  ( cd "$COMPOSE" && docker compose stop web ) 2>&1 | sed 's/^/   /'
  chk "web parado" "$(web)" 0
  chk "odoo14_db en marcha" "$(docker ps --format '{{.Names}}' | grep -cx odoo14_db || true)" 1
  chk "liyben.com/web/login (502 o 503: Nginx sin Odoo)" "$(curl -sS -o /dev/null -w '%{http_code}' https://liyben.com/web/login 2>/dev/null | grep -cE '^50[234]$' || true)" 1 info
  fin "Corte: web PARADO. Sigue con L3 en el equipo."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_l2
```

### L3. Equipo: copia de LIYBEN, BD y filestore (D57)

**[ALTERA solo `~/pns_ai_3973/liyben/despliegue/`; en el VPS, solo la marca `copia_ok`]** Exige permisos 700, 3 GB
libres y el PostgreSQL del kit en marcha (para `pg_restore -l`; si no, `odoo-dev 14 bd-lista`); en el VPS, el web
parado, la última L2 con `TODO OK` y ninguna marca anterior. `pg_dump -Fc` por SSH con la sesión en solo lectura, a
`.parcial` (más de 30 MB, `pg_restore -l` correcto, BD de origen LIYBEN); el filestore con `tar` por SSH, a `.parcial`,
con el mismo número de archivos que en el VPS. Las dos copias en 600, con su SHA-256; la marca `copia_ok` en el VPS con
sus nombres y huellas.

```bash
bash ~/GitHub/third_party/docs/pendiente/liyben_3973/ld_l3.sh
```

Esperado: todo `OK`; el tamaño del `.dump` cerca de los 49 307 121 bytes de Y1 y 832 entradas `TABLE DATA` (INFO);
`== LD L3: TODO OK. Sigue con L4 en el VPS.`

**Corte.** Sergio pega L2 y L3; Claude lo contrasta antes de L4.

Archivo [`liyben_3973/ld_l3.sh`](liyben_3973/ld_l3.sh): 64 líneas, SHA-256 `5d845e5f44502f305273e6f98656b6f77ef6201a5198d93c54f0ab9c8f18d274`.

```bash
ld_l3() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD L3"
  DB_LOCAL=odoo-dev-14-db-1
  [ -n "${VPS_PORT:-}" ] && [ -n "${VPS_DEST:-}" ] || { echo "Faltan VPS_PORT y VPS_DEST: lánzalas con la línea read de antes"; exit 1; }
  vps() { ssh -T -p "$VPS_PORT" "$VPS_DEST" "$@"; }
  O=$(nueva "$DE/l3" .txt) || exit 1
  M=$(date +%Y%m%d-%H%M%S)
  A="$DE/LIYBEN-antes-$M.dump"
  B="$DE/LIYBEN-filestore-antes-$M.tar"
  [ ! -e "$A" ] && [ ! -e "$B" ] && [ ! -e "$A.parcial" ] && [ ! -e "$B.parcial" ] || { echo "Ya existe la copia: vuelve a lanzarla dentro de un segundo"; exit 1; }
  T=$(mktemp) || exit 1
  trap 'rm -f -- "$T"' EXIT
  {
  echo "== $TANDA (equipo: copia de LIYBEN, BD y filestore, por SSH; D57). En el VPS solo escribe la marca $LD/copia_ok: $(date '+%F %T')"
  echo "== 1. Comprobaciones previas"
  chk "permisos de $DE" "$(stat -c %a "$DE")" 700
  chk "espacio libre en el equipo (al menos 3 GB)" "$( [ "$(df --output=avail -B1 "$DE" | tail -1 | tr -d ' ')" -ge 3000000000 ] && echo si || echo no)" si
  chk "PostgreSQL local ($DB_LOCAL) en marcha, para pg_restore -l (si no: odoo-dev 14 bd-lista)" "$(docker ps --format '{{.Names}}' | grep -cx "$DB_LOCAL" || true)" 1
  R=$(vps "cd $COMPOSE && docker compose ps --status running --services | grep -cx web; grep -cx '== LD L2: TODO OK. Corte: web PARADO. Sigue con L3 en el equipo.' \$(ls -t $LD/l2-*.txt | head -1); test -e $LD/copia_ok && echo hay || echo no; find $FS -type f | wc -l; du -sb $FS | cut -f1" 2>&1)
  chk "en el VPS: web parado | última L2 con TODO OK | sin marca anterior" "$(printf '%s\n' "$R" | sed -n 1,3p | una)" "0 1 no"
  NFS=$(printf '%s\n' "$R" | sed -n 4p); BFS=$(printf '%s\n' "$R" | sed -n 5p)
  echo "filestore en el VPS: $NFS archivos, $BFS bytes"
  corte "comprobaciones previas"

  echo "== 2. [ALTERA solo $DE] pg_dump -Fc de LIYBEN por SSH, lanzado a las $(date +%H:%M:%S)"
  vps "docker exec -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_db sh -c 'pg_dump -U \"\$POSTGRES_USER\" -Fc LIYBEN'" > "$A.parcial"
  RC=$?
  chk "salida de pg_dump por SSH" "$RC" 0
  S=$(stat -c %s "$A.parcial"); echo "tamaño: $S bytes (ensayo, Y1: 49 307 121)"
  chk "tamaño razonable (más de 30 MB)" "$( [ "$S" -gt 30000000 ] && echo si || echo no)" si
  if [ "$F" != 0 ]; then rm -f -- "$A.parcial"; echo "== $TANDA: $F FALLO(S). Copia incompleta borrada; no sigas: pega la salida."; exit 1; fi
  mv -- "$A.parcial" "$A"
  docker exec -i "$DB_LOCAL" pg_restore -l < "$A" > "$T" 2>&1
  chk "pg_restore -l" "$?" 0
  chk "BD de origen" "$(sed -n 's/^;[[:space:]]*dbname: //p' "$T" | head -1)" LIYBEN
  chk "datos de ai_provider y res_partner en la copia" "$(grep -cE 'TABLE DATA public (ai_provider|res_partner) ' "$T")" 2
  echo "entradas TABLE DATA: $(grep -c 'TABLE DATA' "$T") (ensayo: 832)"

  echo "== 3. [ALTERA solo $DE] filestore por SSH (tar sin comprimir), lanzado a las $(date +%H:%M:%S)"
  vps "tar -C $(dirname "$FS") -cf - LIYBEN" > "$B.parcial"
  RC=$?
  chk "salida de tar por SSH" "$RC" 0
  NT=$(tar -tf "$B.parcial" 2>/dev/null | grep -vc '/$' || true)
  chk "archivos en la copia = en el VPS" "$NT" "$NFS"
  echo "tamaño: $(stat -c %s "$B.parcial") bytes"
  if [ "$F" != 0 ]; then rm -f -- "$B.parcial"; echo "== $TANDA: $F FALLO(S). Copia del filestore borrada; no sigas: pega la salida."; exit 1; fi
  mv -- "$B.parcial" "$B"
  chk "permisos de las dos copias" "$(stat -c %a "$A") $(stat -c %a "$B")" "600 600"
  HA=$(sha256sum "$A" | cut -d' ' -f1); HB=$(sha256sum "$B" | cut -d' ' -f1)
  echo "SHA-256: ${A##*/} $HA"
  echo "SHA-256: ${B##*/} $HB"
  corte "copias"

  echo "== 4. [ALTERA el VPS: solo $LD/copia_ok] marca de copia hecha"
  vps "umask 077; printf '%s\n' '${A##*/} $HA' '${B##*/} $HB $NFS' > $LD/copia_ok"
  chk "marca escrita en el VPS (líneas)" "$(vps "wc -l < $LD/copia_ok" 2>&1)" 2
  fin "Sigue con L4 en el VPS."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_l3
```

### L4. VPS: D50, `checkout` y `-u`

**[ALTERA LIYBEN y el clon]** Con el web parado. Compuertas: huellas; última L2 con `TODO OK`; marca de L3 posterior a
L2; ninguna L4 anterior que pasara del punto 2; web parado y `odoo14_db` en marcha; clon en `14.0-pns-ai-3` /
`578859b`, limpio; `origin/14.0-pns-ai-3973` = commit; versiones de 3.1.782. Después, en orden y con un corte tras cada
paso:
1. **D50:** `d50_vaciar VACIAR` (los 8 tokens; `COMMIT`). Si su compuerta falla, no vacía nada y decide Sergio.
2. **`checkout -b 14.0-pns-ai-3973 <commit>`** sin `--track`, como el UID 101; rama, HEAD y status; árbol de los `pns_*`
   montados (688 / `0dc381e0…`), del UID 101; versiones de los manifiestos; `14.0-pns-ai-3` sigue en `578859b`.
3. **`-u`** con `docker compose run --rm -T web odoo -u pns_base,pns_ai_mcp,pns_ai_chatboo -d LIYBEN --stop-after-init`;
   el log se corta de `odoo-server.log` desde la posición previa (`u-*.log`); la hora de inicio, en `l4_t0.txt` (L6).
4. **Log contra Y5:** Traceback, ERROR y CRITICAL 0; ningún módulo sin importar; «Deleting field» de las 5 `fit_*` y de
   los 7 campos del ensayo, exactos; la migración `14.0.3.1.973`; parche 35 `fixed` 2 y sin WARNING; 3 módulos
   actualizados y 215 cargados; ningún otro WARNING de los `pns_*`. INFO: «DROP leftover» (ensayo: 22) y los WARNING
   conocidos («same label» de `ai.log` 3 y de `ai.trusted.action` 2; «skip retired unlink» 2).
5. **Después, corto:** versiones de la rama, 0 a medias, 215 instalados, NUEVO-2 con `model._gc_expired()`, 0 `fit_*`,
   `ai_provider_role` y `chatboo_canvas_page` presentes, **tokens 0** y el web parado.

```bash
bash /tmp/liyben_3973/ld_l4.sh
```

Esperado: todo `OK`; el `-u` en 1 a 2 minutos sin salida (ensayo: 67-72 s; log de 389 líneas); `== LD L4: TODO OK.
Corte: web PARADO. Pega la salida antes de L4b. No arranques el web.` Si falla tras el punto 2, el estado lo decide E.

Archivo [`liyben_3973/ld_l4.sh`](liyben_3973/ld_l4.sh): 107 líneas, SHA-256 `35716b0a7c0e9fff3bce59fdff714ba6c76dc081542b1e41a7677a156c42baa8`.

```bash
ld_l4() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD L4"
  [ "$(cd "$(dirname "$0")" && pwd)" = "$LD" ] || { echo "Lánzala desde $LD: bash $LD/ld_l4.sh"; exit 1; }
  sudo -v || { echo "FALLO   sudo. No se ha seguido."; exit 1; }
  O=$(nueva "$LD/l4" .txt) || exit 1
  M=${O##*/l4-}; M=${M%.txt}
  US="$LD/u-salida-$M.log"
  LG="$LD/u-$M.log"
  {
  echo "== $TANDA (VPS: D50, checkout de la rama y -u de los tres pns_* en LIYBEN, con el web parado): $(date -u '+%F %T') UTC"
  echo "== 1. Comprobaciones previas (solo lectura)"
  C=$(cat "$LD/commit.txt" 2>/dev/null)
  chk "huellas de $LD" "$(cd "$LD" && sha256sum -c --quiet huellas.txt 2>&1 | wc -l | tr -d ' ')" 0
  L2=$(ultima "$LD/l2-*.txt")
  chk "última L2 (${L2##*/}) con TODO OK" "$(marca "$L2" '== LD L2: TODO OK. Corte: web PARADO. Sigue con L3 en el equipo.')" 1
  chk "marca de copia de L3 (2 líneas, posterior a L2)" "$(wc -l < "$LD/copia_ok" 2>/dev/null | tr -d ' ')|$( [ "$LD/copia_ok" -nt "$L2" ] && echo posterior || echo anterior)" "2|posterior"
  sed 's/^/   /' "$LD/copia_ok" 2>/dev/null
  chk "ningún L4 anterior que pasara del punto 2" "$(grep -l '^== 2\. \[ALTERA LIYBEN\] D50' "$LD"/l4-*.txt 2>/dev/null | grep -v "^$O\$" | grep -c . || true)" 0
  chk "web parado" "$(web)" 0
  chk "odoo14_db en marcha" "$(docker ps --format '{{.Names}}' | grep -cx odoo14_db || true)" 1
  chk "rama|HEAD|status del clon" "$(g rev-parse --abbrev-ref HEAD)|$(g rev-parse --short=7 HEAD)|$(g status --porcelain | wc -l | tr -d ' ')" "$RAMA_ANTES|$COMMIT_ANTES|0"
  chk "origin/$RAMA = commit del documento" "$(g rev-parse -q --verify "refs/remotes/origin/$RAMA" 2>&1)" "$C"
  chk "versiones en LIYBEN (las de antes)" "$(lysql <<< "SELECT string_agg(name || '|' || state || '|' || latest_version, ' ' ORDER BY name) FROM ir_module_module WHERE name IN ('pns_base','pns_ai_mcp','pns_ai_chatboo');")" "pns_ai_chatboo|installed|14.0.2.1.453 pns_ai_mcp|installed|14.0.3.1.782 pns_base|installed|14.0.1.2.32"
  chk "log del servidor legible" "$(test -r "$LOGF" && echo si || echo no)" si
  corte "comprobaciones previas"

  echo "== 2. [ALTERA LIYBEN] D50: d50_vaciar VACIAR (vacía los 8 tokens de registro; COMMIT)"
  R=$( . "$LD/d50_vaciar.sh" && d50_vaciar VACIAR 2>&1 )
  printf '%s\n' "$R" | sed 's/^/   /'
  chk "D50 VACIAR con TODO OK" "$(printf '%s\n' "$R" | grep -cx '== D50 (VACIAR): TODO OK' || true)" 1
  corte "D50 (si la compuerta falló, no se vació nada: decide Sergio)"

  echo "== 3. [ALTERA el clon] checkout -b $RAMA <commit> sin --track, como el UID 101 (§3.2)"
  g101 checkout -q -b "$RAMA" "$C" 2>&1 | sed 's/^/   /'
  chk "rama|HEAD|status del clon" "$(g rev-parse --abbrev-ref HEAD)|$(g rev-parse HEAD)|$(g status --porcelain | wc -l | tr -d ' ')" "$RAMA|$C|0"
  chk "árbol de los pns_* montados (archivos y huella; D58)" "$(arbol "$CLON" | una)" "$ARBOL_RAMA"
  chk "archivos de los pns_* que no son del UID 101" "$(find "$CLON/pns_base" "$CLON/pns_ai_mcp" "$CLON/pns_ai_chatboo" ! -uid 101 | wc -l | tr -d ' ')" 0
  chk "versiones de los manifiestos" "$(for m in pns_base pns_ai_mcp pns_ai_chatboo; do grep -oE "'version': *'[^']+'" "$CLON/$m/__manifest__.py" | grep -oE "[0-9][0-9.]+"; done | una)" "14.0.1.2.69 14.0.3.1.973 14.0.2.1.587"
  chk "rama $RAMA_ANTES sigue en $COMMIT_ANTES (vuelta atrás)" "$(g rev-parse --short=7 "refs/heads/$RAMA_ANTES")" "$COMMIT_ANTES"
  corte "checkout (vuelta atrás: E, punto 1)"

  OFF=$(stat -c %s "$LOGF")
  T0U=$(date -u '+%Y-%m-%d %H:%M:%S')
  printf '%s\n' "$T0U" > "$LD/l4_t0.txt"
  echo "== 4. [ALTERA LIYBEN] -u pns_base,pns_ai_mcp,pns_ai_chatboo, lanzado a las $T0U UTC (1 a 2 minutos sin salida; ensayo: 67-72 s). Log desde el byte $OFF de $LOGF"
  ( cd "$COMPOSE" && docker compose run --rm -T web odoo -u pns_base,pns_ai_mcp,pns_ai_chatboo -d LIYBEN --stop-after-init ) > "$US" 2>&1 < /dev/null
  RC=$?
  echo "terminado a las $(date -u +%T) UTC"
  chk "salida del -u" "$RC" 0
  chk "salida estándar del contenedor (con logfile, vacía o solo avisos de compose)" "$(grep -cE 'Traceback|ERROR|CRITICAL' "$US" || true)" 0
  [ ! -s "$US" ] || { echo "-- salida estándar ($(wc -l < "$US" | tr -d ' ') líneas; 10 como mucho)"; head -10 "$US" | cut -c1-160 | sed 's/^/   /'; }
  N1=$(stat -c %s "$LOGF")
  chk "el log no se ha rotado durante el -u" "$( [ "$N1" -ge "$OFF" ] && echo si || echo no)" si
  tail -c +"$((OFF + 1))" "$LOGF" > "$LG"
  chk "log del -u con contenido" "$( [ -s "$LG" ] && echo si || echo no)" si
  echo "log del -u: $LG ($(wc -l < "$LG" | tr -d ' ') líneas; ensayo: 389)"
  corte "lanzamiento"

  echo "== 5. Log del -u (contra Y5 del ensayo)"
  chk "Traceback, ERROR o CRITICAL" "$(grep -cE 'Traceback|ERROR|CRITICAL' "$LG" || true)" 0
  echo "-- nivel y logger (WARNING/ERROR/CRITICAL), sin el mensaje"
  grep -oE ' (WARNING|ERROR|CRITICAL) [^ ]+ [^ ]+:' "$LG" | sort | uniq -c | sed 's/^/   /'
  chk "módulos que no se importan" "$(grep -cE 'No module named|module .* not (found|installable)' "$LG" || true)" 0
  DEL=$(grep -oE 'Deleting field [A-Za-z0-9_.]+' "$LG" | sed 's/^Deleting field //' | LC_ALL=C sort)
  chk "Deleting field de ai.provider (las 5 fit_* de 3.1.782, sin fit_design)" "$(printf '%s\n' "$DEL" | grep '^ai\.provider\.' | una)" "ai.provider.fit_audio ai.provider.fit_conversation ai.provider.fit_decision ai.provider.fit_video ai.provider.fit_vision"
  chk "otros «Deleting field» (los 7 del ensayo, Y5: documentados, sin pérdida que importe)" "$(printf '%s\n' "$DEL" | grep -v '^ai\.provider\.' | una)" "ai.log.agent_display ai.log.agent_id ai.mcp.user.key_pin ai.mcp.user.key_pin_html ai.mcp.user.key_pin_killed ai.mcp.user.key_pin_used ai.skill.capture.wizard.from_chatboo"
  chk "migraciones" "$(grep -oE 'module [a-z_]+: Running migration \[[^]]*\] [a-z-]+' "$LG" | una)" "module pns_ai_mcp: Running migration [14.0.3.1.973>] post-migrate"
  chk "parche 35, fixed" "$(grep -oE 'Seges patch 35: [A-Za-z0-9_.]+ fixed' "$LG" | LC_ALL=C sort | una)" "Seges patch 35: pns_ai_mcp.ir_cron_ai_api_result_cache_gc fixed Seges patch 35: pns_ai_mcp.ir_cron_ai_fetch_cache_gc fixed"
  chk "parche 35, WARNING" "$(grep 'Seges patch 35' "$LG" | grep -c WARNING || true)" 0
  chk "módulos actualizados («Module … loaded in»)" "$(grep -oE 'Module [a-z0-9_]+ loaded in' "$LG" | awk '{ print $2 }' | LC_ALL=C sort | una)" "pns_ai_chatboo pns_ai_mcp pns_base"
  chk "módulos cargados (I0: 215)" "$(grep -oE '[0-9]+ modules loaded in' "$LG" | tail -1 | awk '{ print $1 }')" 215
  echo "INFO    «DROP leftover» (ensayo, Y5: 22): $(grep -c 'DROP leftover' "$LG" || true)"
  echo "-- WARNING agrupados (mensaje recortado a 90 caracteres)"
  grep ' WARNING ' "$LG" | sed 's/.* WARNING [^ ]* //' | cut -c1-90 | sort | uniq -c | sed 's/^/   /'
  echo "INFO    conocidos: «same label» de ai.log $(grep -c 'Two fields (client_label, client_display) of ai.log' "$LG" || true) (ensayo: 3), de ai.trusted.action $(grep -c 'Two fields (model_name, model_id) of ai.trusted.action' "$LG" || true) (ensayo: 2); «skip retired unlink for pns_ai_mcp» $(grep -c 'skip retired unlink for pns_ai_mcp' "$LG" || true) (ensayo: 2)"
  chk "otros WARNING de los pns_*" "$(grep ' WARNING ' "$LG" | grep -E 'odoo\.addons\.pns_' | grep -v 'skip retired unlink' | wc -l | tr -d ' ')" 0
  grep ' WARNING ' "$LG" | grep -E 'odoo\.addons\.pns_' | grep -v 'skip retired unlink' | sed 's/.* WARNING [^ ]* //' | cut -c1-120 | sort | uniq -c | sed 's/^/   /'


  echo "== 6. Después (solo lectura; el «después» completo es L6)"
  Q=$(lysql <<'SQL'
SELECT string_agg(name || '|' || state || '|' || latest_version, ' ' ORDER BY name) FROM ir_module_module WHERE name IN ('pns_base','pns_ai_mcp','pns_ai_chatboo');
SELECT count(*) FROM ir_module_module WHERE state IN ('to upgrade','to install','to remove');
SELECT count(*) FROM ir_module_module WHERE state = 'installed';
SELECT string_agg(d.name || '|' || s.code, ' ' ORDER BY d.name) FROM ir_model_data d JOIN ir_cron c ON c.id = d.res_id JOIN ir_act_server s ON s.id = c.ir_actions_server_id WHERE d.module = 'pns_ai_mcp' AND d.model = 'ir.cron' AND d.name IN ('ir_cron_ai_fetch_cache_gc', 'ir_cron_ai_api_result_cache_gc');
SELECT count(*) FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'ai_provider' AND column_name LIKE 'fit\_%';
SELECT (to_regclass('public.ai_provider_role') IS NOT NULL) || '|' || (to_regclass('public.chatboo_canvas_page') IS NOT NULL);
SELECT count(*) FROM res_partner WHERE signup_token IS NOT NULL;
SQL
)
  chk "consultas sin error" "$(printf '%s\n' "$Q" | grep -ciE 'ERROR:|psql: error' || true)" 0
  chk "versiones de la rama" "$(printf '%s\n' "$Q" | sed -n 1p)" "$VERS_RAMA"
  chk "módulos a medio instalar o actualizar" "$(printf '%s\n' "$Q" | sed -n 2p)" 0
  chk "módulos instalados (I0: 215)" "$(printf '%s\n' "$Q" | sed -n 3p)" 215
  chk "crons de NUEVO-2 corregidos por el parche 35" "$(printf '%s\n' "$Q" | sed -n 4p)" "ir_cron_ai_api_result_cache_gc|model._gc_expired() ir_cron_ai_fetch_cache_gc|model._gc_expired()"
  chk "columnas fit_* en ai_provider" "$(printf '%s\n' "$Q" | sed -n 5p)" 0
  chk "tablas de 3.1.973 (ai_provider_role|chatboo_canvas_page)" "$(printf '%s\n' "$Q" | sed -n 6p)" "true|true"
  chk "tokens de registro (D50)" "$(printf '%s\n' "$Q" | sed -n 7p)" 0
  chk "web parado" "$(web)" 0
  fin "Corte: web PARADO. Pega la salida antes de L4b. No arranques el web."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_l4
```

### L4b. VPS: recarga B′ de `es_ES` y rol Diseño (D66 revisada, D67), con el web parado

**[comprobar: LECTURA, termina en `rollback`; APLICAR_BP: ALTERA LIYBEN]** Es Y6 v3 del ensayo con `docker compose run
--rm -T web odoo shell -d LIYBEN` y el `psql` del VPS. `l4b.py`, `l4b_estado.sql` y `l4b_foto.sql` son los del ensayo
sin cambios (sus marcas siguen siendo «Y6 …»). Compuertas: huellas, web parado, última L4 con `TODO OK`, ningún
APLICAR_BP con commit y versiones de la rama; en APLICAR_BP, además, un comprobar con `TODO OK` posterior a L4. Estado de
antes por SQL (rol Diseño con alternativa, nadie con Diseño, el 1 con Decisión) y foto de las traducciones `es_ES` desde
otra sesión.
- **`comprobar`:** en el shell, B, B′ y C (rol) medidos por el módulo y el tipo de antes y deshechos con `rollback`;
  después, foto externa igual a la de antes.
- **`APLICAR_BP`:** B′ y D67 en un solo `commit`, con la compuerta «medida = la del último comprobar» dentro de la
  transacción; después, desde otra sesión, medida externa = la del shell, fuera de los `pns_*` igual, rol Diseño sin
  alternativa y solo en el 1, Decisión sin titulares.

```bash
bash /tmp/liyben_3973/ld_l4b.sh
```

Esperado (comprobar): todo `OK`; B con 36 solo origen y 13 texto cambiado fuera de los `pns_*` y 196 cambiadas en los
`pns_*` (INFO si difiere); B′ sin ningún cambio fuera, restauradas = 49; los tres `rollback`; traducciones antes 45 966
y 41 467 fuera de los `pns_*` (INFO si difiere); WARNING de `pns_base.models.ir_translation` (ensayo: 9 por recarga);
`== LD L4b: TODO OK. Corte (comprobar: rollback, nada escrito). Pega la salida antes de APLICAR_BP.`

**Corte.** Claude contrasta la medida antes de APLICAR_BP.

```bash
bash /tmp/liyben_3973/ld_l4b.sh APLICAR_BP
```

Esperado (APLICAR_BP): todo `OK`; `Y6 COMMIT OK`; rol Diseño `pns_ai_mcp.ai_provider_role_design|design|t|f|conversation`,
con Diseño `1|f|f`, Decisión sin titulares, roles `1|f|models/gemini-3.5-flash|conversation,vision,design` y
`2|t|Qwen3.5-9B|conversation,vision`; `== LD L4b: TODO OK. Corte (APLICAR_BP). Pega la salida antes de L5. No arranques
el web todavía.` En el ensayo, el total de `es_ES` no cambió (45 966) y los `pns_*` pasaron de 538/3810/151 a
549/3811/139.

Archivo [`liyben_3973/ld_l4b.sh`](liyben_3973/ld_l4b.sh): 169 líneas, SHA-256 `2c5a0a06f717ddf1a2297d6931c27c4696dd4df366a8bc87de519f89158f3cfe`.

```bash
ld_l4b() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD L4b"
  MODO=${1:-comprobar}
  case "$MODO" in
    comprobar) OP=- ;;
    APLICAR_BP) OP=BP ;;
    *) echo "Uso: bash $LD/ld_l4b.sh [comprobar|APLICAR_BP] (sin argumento: comprobar, que termina en rollback)"; exit 1 ;;
  esac
  [ "$(cd "$(dirname "$0")" && pwd)" = "$LD" ] || { echo "Lánzala desde $LD: bash $LD/ld_l4b.sh $MODO"; exit 1; }
  BD=LIYBEN
  NT_E=45966
  NF_E=41467
  FINC="Corte (comprobar: rollback, nada escrito). Pega la salida antes de APLICAR_BP."
  FINA="Corte (APLICAR_BP). Pega la salida antes de L5. No arranques el web todavía."
  O=$(nueva "$LD/l4b-$MODO" .txt) || exit 1
  M=${O##*/l4b-$MODO-}; M=${M%.txt}
  SL="$LD/l4b-shell-$MODO-$M.log"
  SLOG="$LD/l4b-log-$MODO-$M.log"
  FA="$LD/l4b_foto_antes-$MODO-$M.txt"
  FD="$LD/l4b_foto_despues-$MODO-$M.txt"
  DA="$LD/l4b_antes-$MODO-$M.txt"
  DD="$LD/l4b_despues-$MODO-$M.txt"
  medida_ext() { awk -F'|' -v etq="$1" '
    function tipo(t) { return (t == "code" || t == "model" || t == "model_terms") ? t : "otro" }
    function pns(m) { return substr(m, 1, 4) == "pns_" }
    NR == FNR { a[$1] = $0; at[$1] = $2; am[$1] = $3; av[$1] = $7; next }
    { d[$1] = $0; dt[$1] = $2; dm[$1] = $3; dv[$1] = $7 }
    END {
      split("code model model_terms otro", T, " ")
      for (i in a) {
        t = tipo(at[i])
        if (pns(am[i])) { k = !(i in d) ? 3 : (d[i] == a[i] ? 1 : 2); pn[t, k]++ }
        else { k = !(i in d) ? 4 : (dv[i] != av[i] ? 3 : (d[i] != a[i] ? 2 : 1)); fu[t, k]++ }
      }
      for (i in d) if (!(i in a)) { t = tipo(dt[i]); if (pns(dm[i])) nu[t, 1]++; else nu[t, 2]++ }
      for (j = 1; j <= 4; j++) { t = T[j]; printf "Y6 MEDIDA %s fuera %s igual=%d origen=%d texto=%d borradas=%d\n", etq, t, fu[t,1], fu[t,2], fu[t,3], fu[t,4]
        so += fu[t,2]; st += fu[t,3]; sb += fu[t,4] }
      for (j = 1; j <= 4; j++) { t = T[j]; printf "Y6 MEDIDA %s pns %s igual=%d cambiadas=%d borradas=%d\n", etq, t, pn[t,1], pn[t,2], pn[t,3]
        pc += pn[t,2]; pb += pn[t,3] }
      for (j = 1; j <= 4; j++) { t = T[j]; printf "Y6 MEDIDA %s nuevas %s pns=%d fuera=%d\n", etq, t, nu[t,1], nu[t,2]
        np += nu[t,1]; nf += nu[t,2] }
      printf "Y6 TOTAL %s fuera_origen=%d fuera_texto=%d fuera_borradas=%d nuevas_fuera=%d pns_cambiadas=%d pns_borradas=%d nuevas_pns=%d\n", etq, so, st, sb, nf, pc, pb, np
    }' "$2" "$3"; }
  cero() { echo "Y6 TOTAL $1 fuera_origen=0 fuera_texto=0 fuera_borradas=0 nuevas_fuera=0 pns_cambiadas=0 pns_borradas=0 nuevas_pns=0"; }
  {
  echo "== $TANDA ($MODO): recarga B′ de es_ES de los tres pns_* (D66 revisada) y rol Diseño en el proveedor 1 sin alternativa, quitándole Decisión (D67), sobre LIYBEN con el web parado (Y6 v3 del ensayo; script l4b.py = el del ensayo). $(date -u '+%F %T') UTC"
  echo "== 1. Comprobaciones previas (solo lectura)"
  chk "huellas de $LD" "$(cd "$LD" && sha256sum -c --quiet huellas.txt 2>&1 | wc -l | tr -d ' ')" 0
  chk "web parado" "$(web)" 0
  L4=$(ultima "$LD/l4-*.txt")
  chk "última L4 (${L4##*/}) con TODO OK" "$(marca "$L4" '== LD L4: TODO OK. Corte: web PARADO. Pega la salida antes de L4b. No arranques el web.')" 1
  chk "ningún L4b APLICAR_BP con commit" "$(grep -lx 'Y6 COMMIT OK' "$LD"/l4b-shell-APLICAR_BP-*.log 2>/dev/null | grep -c . || true)" 0
  if [ "$OP" = BP ]; then
    C=$(ultima "$LD/l4b-comprobar-*.txt")
    chk "último L4b comprobar (${C##*/}) con TODO OK y posterior a L4" "$(marca "$C" "== $TANDA: TODO OK. $FINC")|$( [ -n "$C" ] && [ "$C" -nt "$L4" ] && echo posterior || echo anterior)" "1|posterior"
  fi
  chk "versiones en LIYBEN (las de la rama, tras L4)" "$(lysql <<< "SELECT string_agg(name || '|' || state || '|' || latest_version, ' ' ORDER BY name) FROM ir_module_module WHERE name IN ('pns_base','pns_ai_mcp','pns_ai_chatboo');")" "$VERS_RAMA"
  chk "log del servidor legible" "$(test -r "$LOGF" && echo si || echo no)" si
  corte "compuertas"
  RA=$(lysql < "$LD/l4b_estado.sql")
  printf '%s\n' "$RA" > "$DA"
  chk "consultas sin error (antes)" "$(printf '%s\n' "$RA" | grep -ciE 'ERROR:|psql: error' || true)" 0
  chk "marcador final (antes)" "$(printf '%s\n' "$RA" | grep -cx '## fin' || true)" 1
  chk "rol Diseño, antes (xml_id|code|activo|use_fallback|alternativa)" "$(sec "$RA" 'rol Diseño' | una)" "pns_ai_mcp.ai_provider_role_design|design|t|t|conversation"
  chk "proveedores con el rol Diseño, antes (nadie: 3.1.782 no tenía fit_design)" "$(sec "$RA" 'con Diseño' | una)" ""
  chk "proveedores con el rol Decisión, antes (id|activo|protocolo): el 1, que su protocolo no admite" "$(sec "$RA" 'con Decisión' | una)" "1|f|openai"
  chk "roles por proveedor, antes (id|activo|modelo|roles), de las fit_* de I0" "$(sec "$RA" 'roles por proveedor' | una)" "1|f|models/gemini-3.5-flash|conversation,vision,decision 2|t|Qwen3.5-9B|conversation,vision"
  chk "es_ES activo" "$(sec "$RA" es_ES)" "es_ES|t"
  NT=$(sec "$RA" traducciones | cut -d'|' -f1)
  NF=$(sec "$RA" 'traducciones fuera de pns' | cut -d'|' -f1)
  chk "traducciones es_ES antes (ensayo: $NT_E)" "$NT" "$NT_E" info
  chk "traducciones es_ES fuera de los pns_* antes (ensayo: $NF_E)" "$NF" "$NF_E" info
  echo "INFO    traducciones es_ES antes (n|huella): $(sec "$RA" traducciones); fuera de pns_*: $(sec "$RA" 'traducciones fuera de pns'); de los pns_*: $(sec "$RA" 'traducciones pns' | una)"
  lysql < "$LD/l4b_foto.sql" > "$FA"
  chk "foto de antes (filas sin error = traducciones es_ES)" "$(grep -cvE 'ERROR:|psql: error' "$FA" || true)|$(grep -cE 'ERROR:|psql: error' "$FA" || true)" "$NT|0"
  corte "estado antes"

  case "$OP" in
    -) echo "== 2. Ensayo en odoo shell, sin commit: B, B′ y C (rol), cada uno medido y deshecho con rollback. Lanzado a las $(date -u +%T) UTC" ;;
    BP) echo "== 2. [ALTERA LIYBEN] odoo shell: recarga B′ (B y restauración por id de las filas de fuera de los pns_*) y rol Diseño (D67), un solo commit. Lanzado a las $(date -u +%T) UTC" ;;
  esac
  ESP=""
  [ "$OP" = BP ] && ESP=$(grep "^   Y6 MEDIDA BP \|^   Y6 TOTAL BP " "$C" | sed 's/^   //' | LC_ALL=C sort -u)
  OFF=$(stat -c %s "$LOGF")
  { printf 'BD = "%s"\nOP = "%s"\nESPERADA = """%s"""\n' "$BD" "$OP" "$ESP"; cat "$LD/l4b.py"; } \
    | ( cd "$COMPOSE" && docker compose run --rm -T web odoo shell -d "$BD" ) > "$SL" 2>&1
  RC=$?
  N1=$(stat -c %s "$LOGF")
  tail -c +"$((OFF + 1))" "$LOGF" > "$SLOG"
  echo "terminado a las $(date -u +%T) UTC; salida del shell: $SL ($(wc -l < "$SL" | tr -d ' ') líneas); log: $SLOG ($(wc -l < "$SLOG" | tr -d ' ') líneas)"
  grep '^Y6 bd=\|^Y6 FOTO\|^Y6 TOTAL\|^Y6 BP \|^Y6 MEDIDA = \|^Y6 ROL\|^Y6 ROLLBACK\|^Y6 FIN\|^Y6 COMMIT' "$SL" | sed 's/^/   /'
  chk "salida del shell" "$RC" 0 info
  chk "el log no se ha rotado durante el shell" "$( [ "$N1" -ge "$OFF" ] && echo si || echo no)" si
  chk "shell en $BD y como superusuario" "$(grep -cx "Y6 bd=$BD su=True op=$OP" "$SL" || true)" 1
  chk "foto del shell = foto externa de antes (filas)" "$(sed -n 's/^Y6 FOTO n=//p' "$SL")" "$NT"
  chk "Traceback, ERROR o CRITICAL (salida del shell | log)" "$(grep -cE 'Traceback|ERROR|CRITICAL' "$SL" || true)|$(grep -cE 'Traceback|ERROR|CRITICAL' "$SLOG" || true)" "0|0"
  [ "$(cat "$SL" "$SLOG" | grep -c 'Traceback' || true)" = 0 ] || echo "   tipo de la excepción: $(cat "$SL" "$SLOG" | grep -oE '^[A-Za-z_.]*(Error|Exception)' | sort -u | una)"
  chk "roles en el shell (titulares de Diseño y Decisión, use_fallback y roles del proveedor 1, antes → después)" "$(grep -E '^Y6 ROL (antes|despues):' "$SL" | una)" "Y6 ROL antes: diseno=[] decision=[1] use_fallback=True roles_p1=conversation,vision,decision Y6 ROL despues: diseno=[1] decision=[] use_fallback=False roles_p1=conversation,vision,design"
  echo "-- WARNING del log por logger (sin el mensaje, que lleva textos de traducciones)"
  grep -oE ' WARNING [^ ]+ [^ ]+:' "$SLOG" | sort | uniq -c | sed 's/^/   /'
  echo "INFO    WARNING de pns_base.models.ir_translation: «drop duplicate» $(grep -c 'language import drop duplicate' "$SLOG" || true), «removed … duplicate» $(grep -c 'duplicate translation row' "$SLOG" || true) (ensayo: 9 por recarga)"
  for e in B BP; do
    if grep -q "^Y6 TOTAL $e " "$SL"; then
      echo "-- medida de $e por el módulo y el tipo de antes (fuera: igual / solo origen / texto cambiado / borradas; pns: igual / cambiadas / borradas; nuevas: en pns_* / fuera)"
      grep "^Y6 MEDIDA $e \|^Y6 TOTAL $e " "$SL" | sed 's/^/   /'
    fi
  done
  if [ "$OP" = - ]; then
    chk "B: borradas fuera de los pns_* (el core no borra al importar)" "$(grep -oE '^Y6 TOTAL B .*fuera_borradas=[0-9]+' "$SL" | sed 's/.*fuera_borradas=//')" 0
    chk "B (ensayo: 36 solo origen y 13 texto fuera de los pns_*; 196 cambiadas en los pns_*)" "$(grep -oE '^Y6 TOTAL B fuera_origen=[0-9]+ fuera_texto=[0-9]+' "$SL")|$(grep -oE '^Y6 TOTAL B .*pns_cambiadas=[0-9]+' "$SL" | sed 's/.*pns_cambiadas=//')" "Y6 TOTAL B fuera_origen=36 fuera_texto=13|196" info
    chk "B′: fuera de los pns_* sin ningún cambio" "$(grep -oE '^Y6 TOTAL BP fuera_origen=[0-9]+ fuera_texto=[0-9]+ fuera_borradas=[0-9]+ nuevas_fuera=[0-9]+' "$SL")" "Y6 TOTAL BP fuera_origen=0 fuera_texto=0 fuera_borradas=0 nuevas_fuera=0"
    chk "B′: restauradas por id = las que B cambia fuera de los pns_*" "$(sed -n 's/^Y6 BP guardadas=[0-9]* restauradas=\([0-9]*\) reinsertadas=\([0-9]*\)$/\1|\2/p' "$SL")" "$(grep -oE '^Y6 TOTAL B fuera_origen=[0-9]+ fuera_texto=[0-9]+' "$SL" | awk -F'[= ]' '{ print $5 + $7 "|0" }')"
    chk "B′: guardadas = traducciones fuera de los pns_* antes" "$(sed -n 's/^Y6 BP guardadas=\([0-9]*\) .*/\1/p' "$SL")" "$NF"
    for e in B BP C; do chk "rollback tras $e, en el mismo cursor" "$(grep -cx "Y6 ROLLBACK $e: igual=True" "$SL" || true)" 1; done
    chk "el shell terminó (rollback)" "$(grep -cx 'Y6 FIN comprobar (rollback)' "$SL" || true)" 1
  else
    chk "medida de BP igual a la del último comprobar (${C##*/})" "$(grep "^Y6 MEDIDA BP \|^Y6 TOTAL BP " "$SL" | LC_ALL=C sort -u | una)|$(grep -cx 'Y6 MEDIDA = la del comprobar: True' "$SL" || true)" "$(printf '%s\n' "$ESP" | una)|1"
    chk "B′: fuera de los pns_* sin ningún cambio" "$(grep -oE '^Y6 TOTAL BP fuera_origen=[0-9]+ fuera_texto=[0-9]+ fuera_borradas=[0-9]+ nuevas_fuera=[0-9]+' "$SL")" "Y6 TOTAL BP fuera_origen=0 fuera_texto=0 fuera_borradas=0 nuevas_fuera=0"
    chk "commit hecho" "$(grep -cx 'Y6 COMMIT OK' "$SL" || true)" 1
  fi

  echo "== 3. Después, desde otra sesión de solo lectura"
  chk "web parado (odoo shell va en un contenedor aparte)" "$(web)" 0
  RD=$(lysql < "$LD/l4b_estado.sql")
  printf '%s\n' "$RD" > "$DD"
  chk "consultas sin error (después)" "$(printf '%s\n' "$RD" | grep -ciE 'ERROR:|psql: error' || true)" 0
  chk "marcador final (después)" "$(printf '%s\n' "$RD" | grep -cx '## fin' || true)" 1
  chk "los demás roles, iguales (code|activo|use_fallback)" "$(sec "$RD" roles | grep -v '^design|' | una)" "$(sec "$RA" roles | grep -v '^design|' | una)"
  chk "es_ES activo" "$(sec "$RD" es_ES)" "es_ES|t"
  lysql < "$LD/l4b_foto.sql" > "$FD"
  chk "foto de después sin error" "$(grep -cE 'ERROR:|psql: error' "$FD" || true)" 0
  case "$OP" in -) ET=C ;; *) ET=$OP ;; esac
  MX=$(medida_ext "$ET" "$FA" "$FD")
  echo "-- medida externa (fotos de antes y después desde otra sesión, clasificadas por el módulo y el tipo de antes)"
  printf '%s\n' "$MX" | grep "^Y6 TOTAL " | sed 's/^/   /'
  if [ "$OP" = - ]; then
    chk "foto externa: después = antes (todo deshecho)" "$(cmp -s "$FA" "$FD" && echo igual || echo distinta)" igual
    chk "medida externa: nada cambiado" "$(printf '%s\n' "$MX" | grep '^Y6 TOTAL ')" "$(cero C)"
    chk "rol Diseño, sin cambios" "$(sec "$RD" 'rol Diseño' | una)" "$(sec "$RA" 'rol Diseño' | una)"
    chk "proveedores con el rol Diseño, sin cambios" "$(sec "$RD" 'con Diseño' | una)" ""
    chk "proveedores con el rol Decisión, sin cambios" "$(sec "$RD" 'con Decisión' | una)" "$(sec "$RA" 'con Decisión' | una)"
    chk "roles por proveedor, sin cambios" "$(sec "$RD" 'roles por proveedor' | una)" "$(sec "$RA" 'roles por proveedor' | una)"
    chk "traducciones es_ES, sin cambios (n|huella)" "$(sec "$RD" traducciones)" "$(sec "$RA" traducciones)"
    fin "$FINC"
  else
    if [ "$OP" = C ]; then
      chk "medida externa: traducciones sin ningún cambio (C)" "$(printf '%s\n' "$MX" | grep '^Y6 TOTAL ')" "$(cero C)"
    else
      chk "medida externa = medida del shell (las 13 líneas de $OP)" "$(printf '%s\n' "$MX" | LC_ALL=C sort | una)" "$(grep "^Y6 MEDIDA $OP \|^Y6 TOTAL $OP " "$SL" | LC_ALL=C sort | una)"
    fi
    if [ "$OP" = B ]; then
      echo "INFO    traducciones fuera de los pns_* (n|huella, por el módulo de después): antes $(sec "$RA" 'traducciones fuera de pns'), después $(sec "$RD" 'traducciones fuera de pns') (con B cambian: es lo elegido)"
    else
      chk "traducciones fuera de los pns_*, iguales (n|huella)" "$(sec "$RD" 'traducciones fuera de pns')" "$(sec "$RA" 'traducciones fuera de pns')"
    fi
    chk "rol Diseño sin alternativa (xml_id|code|activo|use_fallback|alternativa)" "$(sec "$RD" 'rol Diseño' | una)" "pns_ai_mcp.ai_provider_role_design|design|t|f|conversation"
    chk "rol Diseño solo en el proveedor 1, inactivo (D62: mientras siga inactivo, nadie diseña)" "$(sec "$RD" 'con Diseño' | una)" "1|f|f"
    chk "rol Decisión sin titulares (el protocolo openai no lo admite; nadie = «no»)" "$(sec "$RD" 'con Decisión' | una)" ""
    chk "roles por proveedor (id|activo|modelo|roles)" "$(sec "$RD" 'roles por proveedor' | una)" "1|f|models/gemini-3.5-flash|conversation,vision,design 2|t|Qwen3.5-9B|conversation,vision"
    echo "INFO    traducciones es_ES (n|huella): antes $(sec "$RA" traducciones), después $(sec "$RD" traducciones); de los pns_*: antes $(sec "$RA" 'traducciones pns' | una), después $(sec "$RD" 'traducciones pns' | una)"
    fin "$FINA"
  fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_l4b "$@"
```

### L5. VPS: arranque

**[ALTERA: fin del corte]** Exige el último L4b APLICAR_BP con `TODO OK`, el web parado y el clon en la rama y el commit.
Guarda la posición del log, `docker compose start web` y espera hasta 3 minutos a «HTTP service (werkzeug) running»;
después, 20 s más.

```bash
bash /tmp/liyben_3973/ld_l5.sh
```

Esperado: todo `OK`; Traceback, ERROR o CRITICAL 0 desde el arranque; `liyben.com/web/login` 200 y `/mcp` 404 (D20);
`== LD L5: TODO OK. Web EN MARCHA. Sigue con L6.`

Archivo [`liyben_3973/ld_l5.sh`](liyben_3973/ld_l5.sh): 43 líneas, SHA-256 `516ada0765906e7510b31d9640e0fd3b24dea59a23b06d918b22c28974fe7295`.

```bash
ld_l5() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD L5"
  [ "$(cd "$(dirname "$0")" && pwd)" = "$LD" ] || { echo "Lánzala desde $LD: bash $LD/ld_l5.sh"; exit 1; }
  O=$(nueva "$LD/l5" .txt) || exit 1
  {
  echo "== $TANDA (VPS: arranque del web con la rama): $(date -u '+%F %T') UTC"
  echo "== 1. Comprobaciones previas (solo lectura)"
  B=$(ultima "$LD/l4b-APLICAR_BP-*.txt")
  chk "último L4b APLICAR_BP (${B##*/}) con TODO OK" "$(marca "$B" '== LD L4b: TODO OK. Corte (APLICAR_BP). Pega la salida antes de L5. No arranques el web todavía.')" 1
  chk "web parado" "$(web)" 0
  chk "rama y HEAD del clon" "$(g rev-parse --abbrev-ref HEAD)|$(g rev-parse HEAD)" "$RAMA|$(cat "$LD/commit.txt")"
  corte "comprobaciones previas"

  OFF=$(stat -c %s "$LOGF")
  printf '%s\n' "$OFF" > "$LD/l5_offset.txt"
  echo "== 2. [ALTERA: fin del corte] docker compose start web (log desde el byte $OFF)"
  ( cd "$COMPOSE" && docker compose start web ) 2>&1 | sed 's/^/   /'
  SA=$(docker inspect -f '{{.State.StartedAt}}' odoo14_server 2>&1)
  printf '%s\n' "$SA" > "$LD/l5_started_at.txt"
  echo "StartedAt: $SA"
  chk "web en marcha" "$(web)" 1
  echo "== 3. Esperando a «HTTP service (werkzeug) running» en el log (hasta 3 minutos)"
  i=0
  until tail -c +"$((OFF + 1))" "$LOGF" | grep -q 'HTTP service (werkzeug) running'; do
    i=$((i + 1)); [ "$i" -gt 36 ] && break; sleep 5
  done
  chk "servidor HTTP en marcha" "$( [ "$i" -le 36 ] && echo si || echo no)" si info
  sleep 20
  echo "== 4. Log y respuesta"
  S=$(tail -c +"$((OFF + 1))" "$LOGF")
  chk "Traceback, ERROR o CRITICAL desde el arranque" "$(printf '%s\n' "$S" | grep -cE 'Traceback|ERROR|CRITICAL' || true)" 0
  echo "-- nivel y logger (WARNING/ERROR/CRITICAL), sin el mensaje"
  printf '%s\n' "$S" | grep -oE ' (WARNING|ERROR|CRITICAL) [^ ]+ [^ ]+:' | sort | uniq -c | sed 's/^/   /'
  chk "liyben.com/web/login" "$(curl -sS -o /dev/null -w '%{http_code}' https://liyben.com/web/login 2>&1)" 200
  chk "GET liyben.com/mcp (Nginx, D20)" "$(curl -sS -o /dev/null -w '%{http_code}' https://liyben.com/mcp 2>&1)" 404
  fin "Web EN MARCHA. Sigue con L6."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_l5
```

### L6. VPS: «después» por SQL (solo lectura)

**[LECTURA]** Es Y7 del ensayo (`l6_despues.sql`) contra el «antes» de L0 y el «después» de L4b. Exige L5 y L0 con
`TODO OK`, ambos «antes» y «después» completos y la hora de inicio del `-u`.

```bash
bash /tmp/liyben_3973/ld_l6.sh
```

Esperado: versiones de la rama, 215, ningún dependiente; AI Administrators 2, 6 y 7 con AI Conversational (P-11 `3|0`,
D64); proveedores = antes sin las `fit_*`; roles como en L4b; cadena de proveedores = antes; **crons de `pns_*`: los 6
de antes y `pns_ai_mcp.ir_cron_ai_journal_trash`, todos activos** (activos en total, uno más que en L0; el único creado
en el `-u`); NUEVO-2 con `model._gc_expired()`; parámetros = antes (`journal_trash_days` no existe, INFO); 0
operaciones no terminales; skills `bill_draft billing customer_360 dashboard financial_health forecast pipeline
sales_board top_sales users`, 10 activas; contextos 59 (`pns_ai_chatboo` 6, `pns_ai_mcp` 53), los 3 nuevos creados en el
`-u`, los 56 de antes presentes; contextos escritos en el `-u` 13|43 (INFO); 0 archivados; traducciones = después de
L4b; **tokens 0**; `iap_account` = antes. INFO si difieren con el uso: operaciones, `ai_trusted_action`, diario, Chatboo,
`ai_log`. `== LD L6: TODO OK. Sigue con L7 (interfaz) y L8.`

Archivo [`liyben_3973/ld_l6.sh`](liyben_3973/ld_l6.sh): 99 líneas, SHA-256 `832597e672eb8eec325f1b98b7f8ded1cb473ff6a5438be7eb71f54691c803e4`.

```bash
ld_l6() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD L6"
  sd() { sec "$RD" "$1"; }
  sa() { sec "$RA" "$1"; }
  ver() { echo "-- $2"; sd "$1" | sed 's/^/   /'; }
  igual() { chk "$2, = antes (L0)" "$(sd "$1" | una)" "$(sa "$1" | una)" ${3:-}; }
  [ "$(cd "$(dirname "$0")" && pwd)" = "$LD" ] || { echo "Lánzala desde $LD: bash $LD/ld_l6.sh"; exit 1; }
  O=$(nueva "$LD/l6" .txt) || exit 1
  A=$(nueva "$LD/l6_despues" .txt) || exit 1
  {
  echo "== $TANDA (VPS: «después» por SQL, contra el «antes» de L0 y el «después» de L4b; solo lectura): $(date -u '+%F %T') UTC"
  echo "== 1. Comprobaciones previas"
  L5=$(ultima "$LD/l5-*.txt")
  chk "última L5 (${L5##*/}) con TODO OK" "$(marca "$L5" '== LD L5: TODO OK. Web EN MARCHA. Sigue con L6.')" 1
  L0=$(ultima "$LD/l0-*.txt")
  chk "última L0 (${L0##*/}) con TODO OK" "$(marca "$L0" '== LD L0: TODO OK. Corte: pega la salida. Después L1 (interfaz) y L2, antes de una hora.')" 1
  AN=$(sed -n 's/^guardado: \(.*l0_antes-[0-9-]*\.txt\) (.*/\1/p' "$L0" | head -1)
  chk "«antes» de esa L0 completo (${AN##*/})" "$(grep -cx '## fin' "$AN" 2>/dev/null || true)" 1
  B=$(ultima "$LD/l4b-APLICAR_BP-*.txt")
  DB=$(printf '%s' "$B" | sed 's#/l4b-APLICAR_BP-#/l4b_despues-APLICAR_BP-#')
  chk "«después» del L4b APLICAR_BP (${DB##*/}) completo" "$(grep -cx '## fin' "$DB" 2>/dev/null || true)" 1
  T0U=$(cat "$LD/l4_t0.txt" 2>/dev/null)
  chk "inicio del -u de L4 (UTC)" "$(printf '%s' "$T0U" | grep -cxE '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}' || true)" 1
  echo "   inicio del -u: $T0U UTC"
  corte "comprobaciones previas"
  RA=$(cat "$AN")

  echo "== 2. «Después» (l6_despues.sql = Y7; salida SQL completa en $A)"
  RD=$( { printf "\\\\set t0 '%s'\n" "$T0U"; cat "$LD/l6_despues.sql"; } | lysql )
  printf '%s\n' "$RD" > "$A"
  echo "guardado: $A ($(wc -l < "$A" | tr -d ' ') líneas, SHA-256 $(sha256sum "$A" | cut -d' ' -f1))"
  chk "consultas sin error" "$(printf '%s\n' "$RD" | grep -ciE 'ERROR:|psql: error' || true)" 0
  printf '%s\n' "$RD" | grep -iE 'ERROR:|psql: error' | head -5 | cut -c1-160 | sed 's/^/   /'
  chk "marcador final de la salida SQL" "$(printf '%s\n' "$RD" | grep -cx '## fin' || true)" 1
  corte "consultas"

  echo "== 3. Módulos, AI Administrators y proveedores"
  chk "versiones (nombre|estado|versión): las de la rama" "$(sd versiones | una)" "pns_ai_chatboo|installed|14.0.2.1.587 pns_ai_mcp|installed|14.0.3.1.973 pns_base|installed|14.0.1.2.69"
  chk "módulos a medio instalar o actualizar" "$(sd 'estados a medias')" 0
  chk "módulos instalados, = I0" "$(sd instalados)" 215
  igual dependientes "dependientes de los pns_* (ninguno)"
  chk "AI Administrators (id|activo|Ajustes|contraseña local|AI Conversational): el 2 lo ganó en el -u (D64)" "$(sd 'ai admins' | una)" "2|t|t|t|t 6|t|t|t|t 7|t|t|t|t"
  chk "P-11 (AI Administrators|sin AI Conversational)" "$(sd p11)" "3|0"
  chk "proveedores (id|activo|protocolo|modelo|sin failover externo), = antes sin las fit_*" "$(sd proveedores | una)" "$(sa proveedores | awk -F'|' '{ print $1 "|" $2 "|" $3 "|" $4 "|" $10 }' | una)"
  chk "roles por proveedor (id|activo|modelo|roles): Decisión fuera del 1 y Diseño dentro (D67)" "$(sd 'roles por proveedor' | una)" "1|f|models/gemini-3.5-flash|conversation,vision,design 2|t|Qwen3.5-9B|conversation,vision"
  chk "rol Diseño sin alternativa (xml_id|code|activo|use_fallback|alternativa)" "$(sd 'rol Diseño' | una)" "pns_ai_mcp.ai_provider_role_design|design|t|f|conversation"
  chk "rol Diseño solo en el proveedor 1, inactivo (D62)" "$(sd 'con Diseño' | una)" "1|f|f"
  chk "rol Decisión sin titulares" "$(sd 'con Decisión' | una)" ""
  ver roles "roles (code|activo|use_fallback|alternativa)"
  igual cadena "cadena de proveedores (id|agente|prioridad|activo|skip_sync_fallback|provider_id|proveedor activo)"

  echo "== 4. Crons"
  chk "crons de pns_* (xml_id|activo|intervalo|numbercall): los 6 de antes y el nuevo de la papelera del diario, todos activos" "$(sd crons | una)" "pns_ai_chatboo.ir_cron_chatboo_async_maintenance|t|5 minutes|-1 pns_ai_mcp.ir_cron_ai_api_result_cache_gc|t|1 hours|-1 pns_ai_mcp.ir_cron_ai_fetch_cache_gc|t|1 hours|-1 pns_ai_mcp.ir_cron_ai_journal_trash|t|1 days|-1 pns_ai_mcp.ir_cron_ai_log_retention|t|1 days|-1 pns_ai_mcp.ir_cron_ai_safe_operation_expire|t|5 minutes|-1 pns_base.ir_cron_pns_export_purge|t|1 hours|-1"
  chk "crons activos (todos los módulos) = los de L0 más el nuevo" "$(sd 'crons activos')" "$(( $(sa 'crons activos') + 1 ))"
  chk "crons creados en el -u (journal_trash_cron.xml, active=True)" "$(sd 'crons creados en el -u' | una)" "pns_ai_mcp.ir_cron_ai_journal_trash"
  chk "crons de NUEVO-2 corregidos por el parche 35" "$(sd 'crons nuevo2' | una)" "ir_cron_ai_api_result_cache_gc|model._gc_expired() ir_cron_ai_fetch_cache_gc|model._gc_expired()"

  echo "== 5. Parámetros, operaciones, diario, Chatboo y registro"
  igual parametros "parámetros (clave|valor)"
  chk "parámetro pns_ai_mcp.journal_trash_days (clave|valor)" "$(sd 'parametro papelera' | una)" "" info
  chk "operaciones pending o confirmed sin ejecutar" "$(sd 'operaciones no terminales' | una)" ""
  chk "operaciones no terminales con pasos sobre ai.trusted.action" "$(sd 'operaciones trusted')" 0
  igual 'operaciones por status' "ai_safe_operation por status (status|n)" info
  igual trusted "ai_trusted_action (n|max_id)" info
  chk "servidores ai.api.server (PNS-17)" "$(sd 'servidores api')" 0
  igual diario "diario (filas|unlink en papelera|reescritas por otro)" info
  igual chatboo "Chatboo (sesiones|id máximo|primera, mes|usuarios)" info
  chk "ai_log (filas|max_id; sin agent_id desde el -u)" "$(sd ai_log)" "0|0" info

  echo "== 6. Skills y contextos (P-21)"
  chk "skills (code): 6 retiradas y 6 nuevas, como en el staging" "$(sd skills | cut -d'|' -f1 | una)" "bill_draft billing customer_360 dashboard financial_health forecast pipeline sales_board top_sales users"
  chk "skills activas" "$(sd skills | awk -F'|' '$2 == "t"' | grep -c . || true)" 10
  ver skills "skills (code|activa|sistema|con xml_id)"
  ver 'skills detalle' "skills (id|code|command|source_module|rel_path|activa|write_uid|escrita en el -u)"
  chk "skills que P-21 reescribe (billing, financial_health, forecast) con write_date del -u" "$(sd 'skills reescritas' | una)" "billing financial_health forecast" info
  chk "contextos (total|activos)" "$(sd contextos | cut -d'|' -f1,2)" "59|59"
  echo "INFO    contextos con xml_id: $(sd contextos | cut -d'|' -f3) (antes: $(sa contextos | cut -d'|' -f3))"
  chk "contextos por módulo (source_module|n|activos)" "$(sd 'contextos por modulo' | una)" "pns_ai_chatboo|6|6 pns_ai_mcp|53|53"
  chk "contextos nuevos (code|módulo|rel_path|activo|creado en el -u)" "$(sd 'contextos nuevos' | una)" "discovery_page_tab|pns_ai_chatboo|contexts/discovery/discovery_page_tab.json|t|t discovery_page_tab_es_ES|pns_ai_chatboo|contexts/discovery/discovery_page_tab_es_ES.json|t|t page_tab|pns_ai_chatboo|contexts/domain/page_tab/page_tab.xml|t|t"
  chk "contextos creados antes del -u (los 56 de antes: ninguno retirado)" "$(sd 'contextos de antes')" 56
  chk "contextos escritos en el -u (de los 13 que P-21 reescribe|de los otros 43: el -u escribe los 56; ensayo, Y7)" "$(sd 'contextos reescritos')" "13|43" info
  chk "contextos y skills archivados" "$(sd archivadas | una)" ""

  echo "== 7. Idioma, traducciones, tokens e IAP"
  igual 'modulos iap' "módulos crm, iap, partner_autocomplete y sms (name|state)"
  chk "es_ES activo" "$(sd idioma)" "es_ES|t"
  chk "traducciones es_ES, = después de L4b (la recarga B′ no añade)" "$(sd 'traducciones es_ES')" "$(sec "$(cat "$DB")" traducciones | cut -d'|' -f1)"
  chk "traducciones fuera de los pns_* (n|huella), = después de L4b" "$(sd 'traducciones fuera de pns')" "$(sec "$(cat "$DB")" 'traducciones fuera de pns')"
  chk "traducciones de los pns_* (módulo|n), = después de L4b" "$(sd 'traducciones pns' | una)" "$(sec "$(cat "$DB")" 'traducciones pns' | una)"
  chk "tokens de registro (D50: vaciados en L4)" "$(sd tokens)" 0
  igual iap "iap_account (filas)"
  fin "Sigue con L7 (interfaz) y L8."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_l6
```

### L7. Interfaz (solo Sergio)

Sin turno de Chatboo con IA (decisión 4 del documento; al uso real, como D61).

| Comprobación | Esperado | Obtenido |
|---|---|---|
| Entrada en `liyben.com` | correcta | |
| Sesión antigua de Chatboo (la de L1) | se abre; se anota cómo se ve frente a L1 | |
| Botón Canvas | no aparece (Diseño solo en el proveedor 1, inactivo: nadie diseña, D62) | |
| AI Engine › roles | Diseño sin alternativa y solo en el proveedor 1; Decisión sin proveedores | |
| Consola (F12) | sin errores de los `pns_*` | |

### L8. VPS: log del servidor desde el arranque (solo lectura)

**[LECTURA]** Corta el log desde la posición de L5 (`servidor-*.log`), agrupa WARNING, ERROR y CRITICAL por logger y saca
las trazas sin datos (archivo, línea, función y tipo). Lanzarla después de L7, para que recoja sus peticiones.

```bash
bash /tmp/liyben_3973/ld_l8.sh
```

Esperado: ERROR o CRITICAL 0 y Traceback 0 (INFO: se contrastan uno a uno); las peticiones a `/chatboo` de L7;
`== LD L8: TODO OK. Sigue con F1 (equipo).`

Archivo [`liyben_3973/ld_l8.sh`](liyben_3973/ld_l8.sh): 34 líneas, SHA-256 `9625216112d3954dcd893c299d385083e495f594801389052cf516638e76357c`.

```bash
ld_l8() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD L8"
  [ "$(cd "$(dirname "$0")" && pwd)" = "$LD" ] || { echo "Lánzala desde $LD: bash $LD/ld_l8.sh"; exit 1; }
  O=$(nueva "$LD/l8" .txt) || exit 1
  M=${O##*/l8-}; M=${M%.txt}
  S="$LD/servidor-$M.log"
  {
  echo "== $TANDA (VPS: log del servidor desde el arranque de L5; solo lectura): $(date -u '+%F %T') UTC"
  OFF=$(cat "$LD/l5_offset.txt" 2>/dev/null)
  chk "posición del log de L5" "$(printf '%s' "$OFF" | grep -cxE '[0-9]+' || true)" 1
  chk "el log no se ha rotado desde L5" "$( [ "$(stat -c %s "$LOGF")" -ge "${OFF:-0}" ] && echo si || echo no)" si
  corte "comprobaciones previas"
  tail -c +"$((OFF + 1))" "$LOGF" > "$S"
  echo "log desde el arranque (StartedAt $(cat "$LD/l5_started_at.txt" 2>/dev/null)): $S ($(wc -l < "$S" | tr -d ' ') líneas)"
  echo "-- nivel y logger (WARNING/ERROR/CRITICAL), sin el mensaje"
  grep -oE ' (WARNING|ERROR|CRITICAL) [^ ]+ [^ ]+:' "$S" | sort | uniq -c | sed 's/^/   /'
  chk "ERROR o CRITICAL" "$(grep -cE ' (ERROR|CRITICAL) ' "$S" || true)" 0 info
  chk "Traceback" "$(grep -c '^Traceback' "$S" || true)" 0 info
  echo "-- trazas sin datos (por cada ERROR: hora, nivel y logger; por cada Traceback: archivo/línea/función y tipo)"
  awk '
/ (ERROR|CRITICAL) / { split($0, a, " "); print "   ## " a[2] " " a[4] " " a[6]; next }
/^Traceback/ { tb = 1; print "     Traceback"; next }
tb && /^  File "/ { l = $0; sub(/^  File "/, "", l); sub(/^.*\/(pns|odoo)\//, "", l); gsub(/"/, "", l); print "       " l; next }
tb && /^[A-Za-z_][A-Za-z0-9_.]*(:|$)/ { e = $0; m = e; sub(/:.*/, "", e); sub(/^[^:]*:? */, "", m); if (m ~ /^[0-9]+$/) e = e ": " m; print "     -> " e; tb = 0; next }
' "$S"
  echo "INFO    peticiones a /chatboo desde el arranque: $(grep -c '/chatboo' "$S" || true); a /mcp: $(grep -c ' /mcp' "$S" || true)"
  fin "Sigue con F1 (equipo)."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_l8
```

---

## 3. E. Vuelta atrás (descrita, no lista para pegar)

Operaciones que cambian el VPS: las decide y hace quien administra el VPS.

1. **Antes del `-u` (FALLO en L0 a L3, o en L4 antes del punto 4).** LIYBEN no ha cambiado, salvo los tokens si L4 pasó
   del punto 2 (D50: vaciados a propósito; no se reponen). Si el `checkout` ya se hizo, volver con
   `sudo -n -u messagebus env HOME=/tmp git -c safe.directory=/opt/odoo/addons/custom/third_party -C /opt/odoo/addons/custom/third_party checkout 14.0-pns-ai-3`
   (la rama sigue en `578859b`, L4 lo comprueba) y comprobar el árbol de los `pns_*` (630 / `4863c946…`, I0). La rama
   `14.0-pns-ai-3973` del clon puede quedarse. Después, `docker compose start web` en `/opt/odoo`.
2. **Después del `-u`.** Volver solo el código a `578859b` deja código 3.1.782 sobre un esquema 3.1.973 (sin las
   `fit_*`, sin las 6 skills retiradas): **no está validado y no se recomienda**. Por orden de preferencia:
   - **Corregir hacia delante:** un commit nuevo en `14.0-pns-ai-3973`, desplegado con este mismo procedimiento (o, si
     es solo de datos, una tanda con comprobar y aplicar).
   - **Restaurar la copia de L3:** parar el web; devolver el código (punto 1); copiar al VPS el `.dump` y el `.tar` de
     L3, con su SHA-256 de la marca `copia_ok`; recrear LIYBEN desde el `.dump` (`dropdb`, `createdb` y `pg_restore` en
     `odoo14_db`, con el usuario de la BD) y devolver el filestore desde el `.tar`; arrancar. **Sin confirmar:** no
     ensayado. Lo que hubiera pasado en LIYBEN entre L3 y la restauración se pierde (con el web parado de L2 a L5, solo
     L4 y L4b).
3. **Fallo en L4b APLICAR_BP antes del commit:** el shell no escribe nada (`rollback`). Con el commit hecho y una
   comprobación de después en FALLO: se decide entre corregir hacia delante y restaurar.
4. **Fallo en L5 con el web ya en marcha** (ERROR en el arranque): se decide con el log de L8 entre parar el web y seguir
   hacia delante.
5. **Las copias de LIYBEN anteriores** (`/opt/odoo/backups`, 15 y 16/10) no se tocan.

## 4. F. Limpieza

- **Se quedan** (se anotan en G para la limpieza final): la rama `14.0-pns-ai-3` del clon (hasta el merge, punto 3 del
  orden); las dos copias de L3 en el equipo (600); `~/pns_ai_3973/liyben/` y `~/pns_ai_3973/liyben/despliegue/`; el
  laboratorio `~/GitHub/lab_liyben_3973` y su imagen `odoo-dev:14-lab_liyben_3973`.
- **F0** (equipo; tras el commit de este documento, antes del despliegue): borra la copia del ensayo `liyben_ens_14`.
- **F1** (equipo; tras L8): copia `/tmp/liyben_3973` del VPS al equipo (G cita las salidas por su nombre).
- **F2** (VPS; tras F1): borra `/tmp/liyben_3973`, con la huella de la lista que da F1.

### F0. Equipo: borrado de `liyben_ens_14`

**[comprobar: LECTURA; BORRAR: BORRA `liyben_ens_14` y su filestore]** Exige el web del kit parado, su PostgreSQL en
marcha, la carpeta del laboratorio, que exista la BD, sin conexiones abiertas (`pg_stat_activity`), y este documento en
HEAD del repo.

```bash
bash ~/GitHub/third_party/docs/pendiente/liyben_3973/ld_f0.sh
bash ~/GitHub/third_party/docs/pendiente/liyben_3973/ld_f0.sh BORRAR
```

Esperado: comprobar con `== LD F0: TODO OK. Corte: si todo es OK, lanza bash ld_f0.sh BORRAR.`; BORRAR con la salida de
`bd-borrar`, `OK      liyben_ens_14 ya no existe` y `== LD F0: TODO OK.`

Archivo [`liyben_3973/ld_f0.sh`](liyben_3973/ld_f0.sh): 35 líneas, SHA-256 `105687639d53bc568c173d0d7f1c8749249ad3956f3a273a2a44509c55fc0c66`.

```bash
ld_f0() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD F0"
  BD=liyben_ens_14
  L=~/GitHub/lab_liyben_3973
  MODO=${1:-comprobar}
  case "$MODO" in comprobar|BORRAR) ;; *) echo "Uso: bash ld_f0.sh [comprobar|BORRAR]"; exit 1 ;; esac
  pg() { docker exec -i odoo-dev-14-db-1 psql -U odoo -d postgres -X -q -At 2>&1; }
  mkdir -p "$DE" && chmod 700 "$DE" || exit 1
  O=$(nueva "$DE/f0-$MODO" .txt) || exit 1
  {
  echo "== $TANDA ($MODO; equipo: borrado de la copia del ensayo $BD, tras el commit del documento): $(date '+%F %T')"
  echo "== 1. Comprobaciones previas (solo lectura)"
  chk "web del kit parado" "$(docker ps --format '{{.Names}}' | grep -cE '^odoo-dev-14-web' || true)" 0
  chk "PostgreSQL del kit en marcha (si no: cd $L && odoo-dev 14 bd-lista)" "$(docker ps --format '{{.Names}}' | grep -cx odoo-dev-14-db-1 || true)" 1
  chk "carpeta del laboratorio $L" "$(test -d "$L" && echo si || echo no)" si
  corte "comprobaciones previas"
  chk "$BD existe" "$(pg <<< "SELECT count(*) FROM pg_database WHERE datname = '$BD';")" 1
  chk "conexiones abiertas a $BD (pg_stat_activity)" "$(pg <<< "SELECT count(*) FROM pg_stat_activity WHERE datname = '$BD';")" 0
  chk "el documento está en el repo (docs/pendiente/liyben_3973.md en HEAD)" "$(git -C ~/GitHub/third_party cat-file -e HEAD:docs/pendiente/liyben_3973.md 2>/dev/null && echo si || echo no)" si
  corte "compuertas"
  if [ "$MODO" = BORRAR ]; then
    echo "== 2. [BORRA $BD y su filestore] odoo-dev 14 bd-borrar $BD (en la terminal no pregunta)"
    ( cd "$L" && odoo-dev 14 bd-borrar "$BD" ) < /dev/null 2>&1 | sed 's/^/   /'
    chk "$BD ya no existe" "$(pg <<< "SELECT count(*) FROM pg_database WHERE datname = '$BD';")" 0
    fin
  else
    fin "Corte: si todo es OK, lanza bash ld_f0.sh BORRAR."
  fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_f0 "$@"
```

### F1. Equipo: copia de las salidas del VPS

**[ALTERA solo `~/pns_ai_3973/liyben/despliegue/vps`]** Exige que `vps/` no exista y la última L8 con `TODO OK`. Copia
por `scp` todos los archivos de `/tmp/liyben_3973`, comprueba que las huellas son las del VPS y que no tienen permisos
para otros, y da la huella de la lista para F2.

```bash
bash ~/GitHub/third_party/docs/pendiente/liyben_3973/ld_f1.sh
```

Esperado: todo `OK` y `== LD F1: TODO OK. Sigue con F2 en el VPS: bash /tmp/liyben_3973/ld_f2.sh <huella>`.

Archivo [`liyben_3973/ld_f1.sh`](liyben_3973/ld_f1.sh): 30 líneas, SHA-256 `52f228d83cf4cccd2c02509816f7f42e19285245f7a1b60b5a17993ecd7d0a5b`.

```bash
ld_f1() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD F1"
  [ -n "${VPS_PORT:-}" ] && [ -n "${VPS_DEST:-}" ] || { echo "Faltan VPS_PORT y VPS_DEST: lánzalas con la línea read de antes"; exit 1; }
  vps() { ssh -T -p "$VPS_PORT" "$VPS_DEST" "$@"; }
  V="$DE/vps"
  O=$(nueva "$DE/f1" .txt) || exit 1
  {
  echo "== $TANDA (equipo: copia de las salidas de $LD del VPS a $V; en el VPS no escribe nada): $(date '+%F %T')"
  echo "== 1. Comprobaciones previas"
  chk "$V no existe aún" "$(test -e "$V" && echo existe || echo no)" no
  chk "en el VPS: última L8 con TODO OK" "$(vps "grep -cx '== LD L8: TODO OK. Sigue con F1 (equipo).' \$(ls -t $LD/l8-*.txt | head -1)" 2>&1)" 1
  corte "comprobaciones previas"
  R=$(vps "cd $LD && find . -maxdepth 1 -type f -printf '%f\n' | LC_ALL=C sort | xargs -d '\n' sha256sum" 2>&1)
  echo "archivos en el VPS: $(printf '%s\n' "$R" | grep -c . || true)"
  echo "== 2. [ALTERA solo $V] scp"
  mkdir -m 700 "$V" || exit 1
  scp -q -P "$VPS_PORT" "$VPS_DEST:$LD/*" "$V/"
  chk "scp" "$?" 0
  chk "huellas de la copia = las del VPS" "$(cd "$V" && find . -maxdepth 1 -type f -printf '%f\n' | LC_ALL=C sort | xargs -d '\n' sha256sum)" "$R"
  chk "archivos de la copia sin permisos para otros" "$(find "$V" -type f -perm /077 | wc -l | tr -d ' ')" 0
  HL=$(printf '%s\n' "$R" | sha256sum | cut -d' ' -f1)
  echo "huella de la lista (para F2): $HL"
  fin "Sigue con F2 en el VPS: bash $LD/ld_f2.sh $HL"
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_f1
```

### F2. VPS: borrado de `/tmp/liyben_3973`

**[BORRA `/tmp/liyben_3973`]** Exige la huella de la lista igual a la de F1 (si algo cambió desde F1, no borra) y el web
en marcha. Después comprueba que el código montado sigue intacto (rama y árbol).

```bash
bash /tmp/liyben_3973/ld_f2.sh <huella de F1>
```

Esperado: todo `OK`, la línea del disco y `== LD F2: TODO OK.`

Archivo [`liyben_3973/ld_f2.sh`](liyben_3973/ld_f2.sh): 20 líneas, SHA-256 `5b8e59578bc6038d5c545f9bbffb4831132df5ca7ad15d6418f03591ae3560cf`.

```bash
ld_f2() (
  set -u
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD F2"
  HL=${1:-}
  [ "$(cd "$(dirname "$0")" && pwd)" = "$LD" ] || { echo "Lánzala desde $LD: bash $LD/ld_f2.sh <huella de F1>"; exit 1; }
  printf '%s' "$HL" | grep -qxE '[0-9a-f]{64}' || { echo "Uso: bash $LD/ld_f2.sh <huella de la lista que da F1>"; exit 1; }
  echo "== $TANDA (VPS: borra $LD, ya copiada al equipo por F1): $(date -u '+%F %T') UTC"
  echo "== 1. Comprobaciones previas"
  chk "huella de la lista de $LD = la de F1" "$(cd "$LD" && find . -maxdepth 1 -type f -printf '%f\n' | LC_ALL=C sort | xargs -d '\n' sha256sum | sha256sum | cut -d' ' -f1)" "$HL"
  chk "web en marcha" "$(web)" 1
  corte "comprobaciones previas"
  echo "== 2. [BORRA $LD]"
  rm -rf -- "$LD"
  chk "$LD borrada" "$(test -e "$LD" && echo existe || echo no)" no
  chk "código montado intacto (rama y árbol)" "$(g rev-parse --abbrev-ref HEAD)|$(arbol "$CLON" | una)" "$RAMA|$ARBOL_RAMA"
  df -h / | tail -1 | sed 's/^/   disco: /'
  fin
)
ld_f2 "$@"
```

---

## 5. G. Resultado del despliegue

**Ejecutado el 20/11/2026, de 11:29 a 12:07 hora local** (Sergio; contraste de Claude tras cada tanda). **Commit
desplegado:** `3df4307129a44719a27dd30c12dd479ab0335a6b` (`commit.txt` de E0), rama `14.0-pns-ai-3973`. LIYBEN queda en
`pns_base` 14.0.1.2.69, `pns_ai_mcp` 14.0.3.1.973 y `pns_ai_chatboo` 14.0.2.1.587, con el web en marcha desde las
10:55:21 UTC. **Corte real del servicio:** de la parada de L2 (10:42:25 UTC) al «HTTP service (werkzeug) running» de L5
(10:55:23 UTC): **12 min 58 s**. Todas las tandas terminaron con `TODO OK`, sin ningún `FALLO`.

Horas del VPS en UTC; las del equipo (E0, E1, L3, F1), locales (UTC + 1). Salidas del VPS, copiadas por F1 a
`~/pns_ai_3973/liyben/despliegue/vps/`; las del equipo, en `~/pns_ai_3973/liyben/despliegue/` (no van al repo).

| Tanda | Hora | Salida | Resultado |
|---|---|---|---|
| F0 | 11:10 y 11:12 (antes de la ventana) | `f0-comprobar-20261120-111002.txt`, `f0-BORRAR-20261120-111202.txt` | `liyben_ens_14` y su filestore borrados (la copia del ensayo solo se podría rehacer desde el `.dump` de Y1) |
| E0 | 11:29:58 | `e0-20261120-112958.txt` | `TODO OK`: rama, árbol limpio y al día con la remota (`3df4307`, 11:03:34); de `c6ec077` al commit solo `docs/`; árbol 688 / `0dc381e0…`, versiones y lista de `ai/` (Y4 A); fuera de `pns_*` y `docs/`, solo `CLAUDE.md` |
| E1 | 11:31:32 | `e1-20261120-113132.txt` | `TODO OK`: 17 huellas del commit = las del documento; `/tmp/liyben_3973` creada (700) con 19 archivos; `huellas.txt` `49eec712297ca9224de76719d897a43bbf67720a9bc9c5cc565633e2834b64e3` (recalculada por Claude: igual) |
| L0 | 10:33:13 | `l0-20261120-103313.txt`, `l0_i0-…`, `l0_antes-…` | `TODO OK`. I0 `TODO OK` (276 MB, 215 módulos, 45 482 traducciones, disco 9,4 GB libres, caso b de PNS-82 67/18/2/1); `ls-remote` como el UID 101 en el commit; filestore legible entero (3028 archivos, 564 727 024 bytes); B: 79/79, 5 `fit_*`, 56 + 10 emparejados, 0 con dueño; C = I0 (35 crons activos en total; último `-u` 16/10 18:00:52); P-21 exacto (13 + 3 + 0; 3 skills reescritas, 6 retiradas); D50 en ensayo con `ROLLBACK`. «Antes»: 127 líneas, `2a8622e98b2032f2ffe5f324494a2f243e52f6d3ea2fd8a3e4b7f1b2f1128809`. Un INFO de Chatboo (abajo) |
| L1 | — | — | Aviso del corte: no hizo falta, nadie usaba LIYBEN (Sergio). Sesión antigua de Chatboo: **no aplica** (borrada el 19/11, abajo; decisión A de Sergio, 11:48 local) |
| L2 | 10:42:22 | `l2-20261120-104222.txt` | `TODO OK`: `fetch` como el UID 101 (`[new branch] 14.0-pns-ai-3973`), remota = commit, clon sin cambios; **web parado a las 10:42:25**; `liyben.com/web/login` 50x |
| L3 | 11:43:31 | `l3-20261120-114331.txt` | `TODO OK`. `LIYBEN-antes-20261120-114331.dump`: 49 300 282 bytes, 832 `TABLE DATA`, `88610a70e58612356b785f6d471623d1d3dde45ff35616147137258ef06f3c34`. `LIYBEN-filestore-antes-20261120-114331.tar`: 567 234 560 bytes, 3028 archivos (= VPS), `85d529082c308bd21c0ca7b317f66b6be2f9bdefc97c018df4ece08817bdadbc`. Las dos en 600; marca `copia_ok` en el VPS |
| L4 | 10:46:54 | `l4-20261120-104654.txt`, `u-20261120-104654.log`, `u-salida-…`, `l4_t0.txt` | `TODO OK`. D50 `VACIAR` (10:46:55): perfil exacto, 8 vaciados, `COMMIT`, 0 después. `checkout -b` sin `--track` como el UID 101: árbol 688 / `0dc381e0…`; `14.0-pns-ai-3` sigue en `578859b`. **`-u` de 10:46:56 a 10:48:26 (90 s)**, log de 382 líneas: 0 Traceback/ERROR/CRITICAL; las 5 `fit_*` y los 7 campos de Y5; la migración; parche 35 `fixed` 2; 3 actualizados y 215 cargados; «DROP leftover» 22; WARNING conocidos 3/2/2; los demás WARNING, de módulos de LIYBEN y `vertical-instaladores` (21 `decimal_precision`, 8 `odoo.models`, 8 `ir_model`, 3 `odoo.fields`, 2 `py.warnings`), como en Y5. Después: tokens 0 |
| L4b comprobar | 10:50:38 | `l4b-comprobar-20261120-105038.txt` y su shell, log, estados y fotos | `TODO OK`, nada escrito. B: fuera de los `pns_*` 36 solo origen y 13 texto (`code`), 196 cambiadas en los `pns_*` (95/46/55); B′: 0 fuera, 49 restauradas; C: Diseño al 1 y Decisión fuera; tres `rollback`; foto externa igual. 9 WARNING de `pns_base.models.ir_translation` por recarga. INFO de traducciones (abajo) |
| L4b APLICAR_BP | 10:52:38 | `l4b-APLICAR_BP-20261120-105238.txt` y su shell, log, estados y fotos | `TODO OK`. `Y6 MEDIDA = la del comprobar: True` y `Y6 COMMIT OK`; desde otra sesión, medida = la del shell y fuera de los `pns_*` igual (`41470|28b8cb9e413f14a483e5a4c8b096d598`); `es_ES` 45 969 filas, `e762d7c47785be1bf89ca6f1f1b4cbf9` → `a360d9eb568ab464593f6d471e6c122d`; `pns_*` 538/3810/151 → 549/3811/139; Diseño `1|f|f` sin alternativa, Decisión sin titulares, roles `1|f|…|conversation,vision,design` y `2|t|Qwen3.5-9B|conversation,vision` |
| L5 | 10:55:21 | `l5-20261120-105521.txt`, `l5_offset.txt`, `l5_started_at.txt` | `TODO OK`: `StartedAt` 10:55:21.62, «HTTP service» 10:55:23; 0 Traceback/ERROR/CRITICAL (4 WARNING de `py.warnings`); `/web/login` 200 y `/mcp` 404 (D20) |
| L6 | 10:56:46 | `l6-20261120-105646.txt`, `l6_despues-…` | `TODO OK`, sin INFO: versiones, 215, AI Administrators 2, 6 y 7 con AI Conversational (P-11 `3|0`; el 2 lo ganó en el `-u`, D64); 7 roles; crons de `pns_*` 7 activos, 36 en total, el único creado en el `-u` `pns_ai_mcp.ir_cron_ai_journal_trash`; NUEVO-2 con `model._gc_expired()`; skills 10; contextos 59 (13/43 escritos en el `-u`); traducciones = después de L4b; tokens 0. «Después»: 132 líneas (= Y7), `b673205e4426f0ec84c6cb2acc15af06dfa1d9d27fa904f5dc86fb6b96700967` |
| L7 | 12:04 local | — | Ver la tabla de abajo |
| L8 | 11:05:00 | `l8-20261120-110500.txt`, `servidor-20261120-110500.log` | `TODO OK`: 492 líneas desde el arranque, 0 ERROR/CRITICAL y 0 Traceback; WARNING 84 `decimal_precision`, 32 `odoo.models`, 4 `py.warnings` (21 y 8 por cada carga del registro); 0 peticiones a `/chatboo` y a `/mcp` |
| F1 | 12:05:46 | `f1-20261120-120546.txt` | `TODO OK`: 49 archivos de `/tmp/liyben_3973` en `vps/`, huellas iguales, sin permisos para otros; huella de la lista `8a677881cc3e26c79cac4f5528e73fac9965fd60065920d49343e5346a718a5c` |
| F2 | 11:07:26 | (por pantalla) | `TODO OK`: `/tmp/liyben_3973` borrada; código montado intacto (rama y árbol); disco 9,4 GB libres (87 %) |

**L1 y L7 (interfaz, Sergio):**

| Comprobación | Esperado | Obtenido |
|---|---|---|
| L1: aviso del corte | hecho | No hizo falta: nadie usaba LIYBEN |
| L1: sesión antigua de Chatboo, antes | se anota | **No aplica:** la sesión 1 ya no existe (abajo) |
| L7: entrada en `liyben.com` | correcta | Correcta |
| L7: sesión antigua de Chatboo | se abre | **No aplica** (decisión A: no se abre Chatboo, para no crear una sesión después del «antes») |
| L7: botón Canvas | no aparece | **Cubierto por L6:** el botón está dentro del panel de Chatboo y sale de `canvas_available` (`pns_ai_chatboo/static/src/js/chatboo_component_v2.js:1707`, `:3823-3824`; `pns_ai_chatboo/controllers/chatboo.py:73-96`); con Diseño solo en el proveedor 1, inactivo, nadie diseña (D62). Se mira en el uso real |
| L7: AI Engine › roles | Diseño sin alternativa y solo en el 1; Decisión sin proveedores | Correcto |
| L7: consola (F12) | sin errores de los `pns_*` | Sin errores |

**INFO y diferencias con el ensayo (ninguna bloquea):**
- **Chatboo 0 sesiones en L0** (I0 del 19/11: `1|1|2026-10|1`). La borró la retención de 30 días de 3.1.782: el cron
  `pns_ai_chatboo.ir_cron_chatboo_async_maintenance` llama a `_cleanup_old_sessions()`
  (`_fabricante/3.1.782/pns_ai_chatboo/models/chatboo_async_request.py:2144-2167`,
  `models/chatboo_session.py:1360-1382`), que borra las sesiones con `last_used_date` de hace más de
  `history_retention_days` (30). En `odoo-server.log`, línea 22735: «2026-11-19 14:21:17,391 … Cleaning 1 Chatboo
  session(s) older than 30 days», posterior a la copia de Y1 (por eso el ensayo aún la tenía). Por eso L1.2 y la fila
  de L7 no aplican (y, con la decisión A, L8 no tiene peticiones a `/chatboo`).
- **`-u` de 90 s y log de 382 líneas** (ensayo: 67-72 s y 389). Los 90 s incluyen crear el contenedor `run`; todos los
  recuentos del log son los de Y5. No se ha mirado de dónde salen las 7 líneas de menos.
- **3 traducciones `es_ES` más que en el ensayo, todas fuera de los `pns_*`** (tras el `-u`: 45 969 y 41 470, frente a
  45 966 y 41 467; antes del `-u`, 45 482 en los dos). El `-u` real añadió 487 filas y el del ensayo 484. Dentro de los
  `pns_*`, igual que el ensayo. B′ guarda y restaura las filas de fuera tal como estaban (`guardadas=41470`,
  restauradas 49 = el ensayo) y APLICAR_BP exige la medida del comprobar de hoy: las 3 quedan intactas. Sin
  identificar (se puede, en solo lectura, comparando por tipo y módulo `vps/l4b_foto_antes-comprobar-20261120-105038.txt`
  con la `y6_foto_antes` de Y6 v3).
- **WARNING de L8 por cuadruplicado:** 84 = 4 × 21 y 32 = 4 × 8, uno por cada carga del registro de LIYBEN tras el
  arranque; son los mismos del `-u`.
- **Validado en el VPS lo que el documento dejaba pendiente (§1):** `ly_i0.sh` con `bash` desde `/tmp/liyben_3973`;
  `sudo -n` como `messagebus` tras `sudo -v`; lectura del log y de todo el filestore como `ubuntu`;
  `docker compose run … odoo shell` con `logfile` (salida del script por la salida estándar, registros al log); el
  `ls-remote` y el `fetch` con las credenciales del clon; `curl` con el web parado (50x, `OK`).

**Lo que queda para la limpieza final (punto 4 del orden) y para el uso real (punto 2):**
- **VPS:** la rama `14.0-pns-ai-3` del clon, en `578859b` (vuelta atrás hasta el merge, punto 3); `14.0` del clon en
  `f63d5a1`, frente a `origin/14.0` `59bd6af` del equipo (se mira en el merge); `/opt/odoo/backups` (15 y 16/10), no se
  toca. En `/tmp` no queda nada del despliegue (F2).
- **Equipo:** `~/pns_ai_3973/liyben/despliegue/` (700): salidas de E0, E1, L3, F0 y F1, `commit.txt`,
  `huellas_vps.txt`, `vps/` (49 archivos) y las dos copias de L3 (600, unos 616 MB). **Las copias de L3 se conservan al
  menos hasta terminar el uso real** (son la vuelta atrás, E). `~/pns_ai_3973/liyben/` (ensayo: `.dump` de Y1, tandas y
  salidas); el laboratorio `~/GitHub/lab_liyben_3973` y la imagen `odoo-dev:14-lab_liyben_3973`; el contexto activo de
  `odoo-dev 14` sigue siendo `lab_liyben_3973`.
- **Al uso real:** Chatboo y el botón Canvas en la interfaz (L1.2 y L7 no aplicaron); la ficha 26 (D61); las claves MCP,
  si hacen falta (D60); el proveedor 1 sigue inactivo, así que nadie tiene Diseño en activo (D62); opcional, identificar
  las 3 traducciones de más.

**Fila de la §6.2 de la [instalación](instalacion_liyben_pns_ai.md):** «Despliegue de las correcciones», hecho el
20/11/2026 con el commit `3df4307` (este apartado).

---

## Anexo A. Ensayo (19/11/2026, equipo de Sergio, hora local salvo I0 y D50)

Sobre `liyben_ens_14`, copia de LIYBEN de ese día (`LIYBEN-20261119-124423.dump`, 49 307 121 bytes,
`cb6ebff7…8d30`), neutralizada y sin filestore (D53), con el web parado de principio a fin. Salidas en
`~/pns_ai_3973/liyben/` (no van al repo).

| Tanda | Resultado |
|---|---|
| D50 (09:18-09:24 UTC) | Perfil de LIYBEN: 8 tokens (5 filas de perfil). `d50_vaciar ensayo` en LIYBEN con `TODO OK` y `ROLLBACK`. Core y laboratorio en el plan («D50 hecho») |
| I0 (VPS, 10:40 UTC) | Inventario de solo lectura (`ly_i0.sh`): es la base de L0. Versiones 1.2.32 / 3.1.782 / 2.1.453, 215 instalados, 3 AI Administrators, proveedor 1 inactivo y 2 activo, 6 crons activos, 56 contextos y 10 skills sin xml_id, 45 482 traducciones `es_ES`, 8 tokens, disco al 87 % |
| E0 (11:39) | `c6ec077` = árbol de `5d0559b` (688 / `0dc381e0…`); de `578859b` al commit, fuera de `pns_*` y `docs/` solo `CLAUDE.md` |
| Y0, Y0b | Repos del VPS frente al equipo: clones superficiales; 22 OCA del VPS más antiguos; `vertical-instaladores` en `7c05906`; Dockerfile del VPS distinto del del kit |
| Y0c FIJAR (12:57) | 23 clones de `~/odoo-dev/14.0` en los commits del VPS |
| Y1 | Copia `pg_dump -Fc` por SSH (la de arriba), 832 `TABLE DATA`; en el VPS no se escribió nada |
| Y2a, Y2b (12:59-13:08) | Laboratorio `lab_liyben_3973` con `infra/Dockerfile.14` (= `Dockerfile.14.lab_liyben` del Anexo B); `arrancar` con la C limpia y `parar` |
| Y3 CARGAR (13:15) | `liyben_ens_14` cargada y neutralizada; paridad 215 / 212 iguales / 3 distintos (`pns_*`) / 0 sin código |
| Y4 (13:57) | «Antes» (D65) con `TODO OK`: A (lista de `ai/`), B (56 + 10 emparejados, 0 con dueño), C = I0 (crons a `f` por la neutralización) y P-21. `y4_antes-20261119-135706.txt`, `ab7571b7…c0958c`. Es el origen de `l0_b.sql` (`ly_y4.sh:58-228`) y `l0_antes.sql` (`ly_y4.sh:248-506`) |
| Y5 ACTUALIZAR (14:11-14:13) | `-u` en 72 s, log de 389 líneas, 0 Traceback/ERROR/CRITICAL; las 5 `fit_*` y los 7 campos más; 1 migración; parche 35 `fixed` 2; 3 actualizados, 215 cargados; «DROP leftover» 22; el kit reactivó 1 cron y lo volvió a desactivar |
| Y6 v1 y v2 (14:27-14:45) | v1: `ValidationError` al dar Diseño al 1 con Decisión (→ D67). v2: APLICAR con 1 FALLO: 49 filas de otros módulos pasaron a los `pns_*` (medida por el módulo de después, errónea). La copia se rehízo |
| REHACER (15:01-15:04) | `bd-borrar`, Y3 CARGAR y Y5 ACTUALIZAR otra vez: igual que la primera pasada |
| Y6 v3 comprobar (15:36) | B: fuera de los `pns_*`, 36 solo origen y 13 texto cambiado; `pns_*` 196 cambiadas. B′: 0 fuera (49 restauradas). C: 0. `rollback` comprobado → D66 revisada (B′) |
| Y6 v3 APLICAR_BP (15:39) | `TODO OK`: medida = la del comprobar; fuera de los `pns_*` igual; total 45 966; rol Diseño `1|f|f`, Decisión sin titulares. Es el origen de `l4b_estado.sql` (`ly_y6.sh:39-75`), `l4b_foto.sql` (`:80-81`) y `l4b.py` (`:155-297`) |
| Y7 (15:49) | «Después» con `TODO OK`: versiones, 215, AI Conversational en 2, 6 y 7; crons: el único creado en el `-u` es `pns_ai_mcp.ir_cron_ai_journal_trash`; skills 10 (6 retiradas, 6 nuevas); contextos 59; tokens 8 (sin D50). `y7_despues-20261119-154926.txt`, `1f312c26…6198`. Es el origen de `l6_despues.sql` (`ly_y7.sh:60-202`) |
| RESTAURAR (16:01-16:03) | `ly_y0r.sh` comprobar, `ly_y0c.sh RESTAURAR` y `ly_y0r.sh` comprobar: los 23 clones de vuelta en `14.0`, con `TODO OK`. Clones de profundidad 1 antes y después: la marca superficial no se repara |

**Piezas del ensayo en el despliegue, sin cambios** (comprobado el 20/11/2026: cada archivo es igual, byte a byte, a
esas líneas de la tanda del ensayo):

| Archivo del despliegue | Líneas de la tanda del ensayo | SHA-256 |
|---|---|---|
| `l0_b.sql` | `ly_y4.sh:58-228` | `85394c9767b647cefc977c1be57af555a0a5b7c6f0dbb16ddcacfd373eb3cf21` |
| `l0_antes.sql` | `ly_y4.sh:248-506` | `26d8194e3cbf43607420c60a312ac91a443e86741f7f33dc3b210c609b3e514c` |
| `l4b_estado.sql` | `ly_y6.sh:39-75` | `8b4ee8af026ee5c0117394f54858b9665c2abc5518d6ff11e4046cb2d7ee9c5b` |
| `l4b_foto.sql` | `ly_y6.sh:80-81` | `d8102a5de47136b1d4e26360e0415fb831995afaa471dfd7fb4c7113effb533f` |
| `l4b.py` | `ly_y6.sh:155-297` | `b7827d7dc172b9ea4caba42061a8276a72777ed61354bbfc293b3a55ed970c98` |
| `l6_despues.sql` | `ly_y7.sh:60-202` | `d58c9f7188422273f4ea1e88aaee88441b474cc6425a4a2dd1a63d5d23110fc0` |

`liyben_ens_14` se conserva, solo para consultas SQL de solo lectura, hasta el commit de este documento (F0). Borrada
el 20/11/2026 (F0, G).

## Anexo B. Tandas del ensayo en el repo

Entran tal cual, como registro de lo que se ejecutó; **no forman parte del despliegue** salvo `ly_i0.sh` (L0). Necesitan
el equipo de Sergio con el kit y, las que van por SSH, `VPS_PORT` y `VPS_DEST` (§1).

| Archivo | Líneas | SHA-256 | Qué hace |
|---|---|---|---|
| [`ly_e0.sh`](liyben_3973/ly_e0.sh) | 69 | `815ee437376227280b8b548fa7ad64a19eccc4b2265ce5b2ef10eac516803cd1` | E0 del ensayo: árbol de módulos y lo que cambia fuera de `pns_*` |
| [`ly_i0.sh`](liyben_3973/ly_i0.sh) | 224 | `4e5939f65f3f414c7070b2d7d612b49d8e120a27f418b81e43f7175a8042284d` | I0: inventario de solo lectura del VPS (base de L0) |
| [`ly_y0.sh`](liyben_3973/ly_y0.sh) | 97 | `302f85928e5d785b7bb92975153881f7ec81fc6e631116b1a6033d22cfe7c415` | Y0: repos del `addons_path` del VPS frente al equipo y Dockerfile |
| [`ly_y0b.sh`](liyben_3973/ly_y0b.sh) | 35 | `a5cbbde50814f44cf97f38db5b6936a45b3bf3b47a871e7d4de08a8f8c27437c` | Y0b: clones superficiales y `__pycache__` |
| [`ly_y0c.sh`](liyben_3973/ly_y0c.sh) | 115 | `afaf1152f1e8a8d496acfb46cec669b254609da2d40c601015a815a8045282df` | Y0c: `comprobar` / `FIJAR` / `RESTAURAR` de los clones de `~/odoo-dev/14.0` |
| [`ly_y0r.sh`](liyben_3973/ly_y0r.sh) | 104 | `8676be87d7a5cf4911a8d90921f0d14ccf31b882af1c92222d5275e13714096e` | `comprobar` antes y después de RESTAURAR (y `REPARAR`, no usado) |
| [`ly_y1.sh`](liyben_3973/ly_y1.sh) | 53 | `d0556daab661ccf8bf92d95375e8820bc344a93d168db66b712f869211d68439` | Y1: copia `pg_dump -Fc` por SSH |
| [`ly_y2a.sh`](liyben_3973/ly_y2a.sh) | 49 | `a19d4364ae63b478a68eba6a0263d96652cc82d4da635003c9a6afea7f303bf1` | Y2a: carpeta del laboratorio |
| [`ly_y2b.sh`](liyben_3973/ly_y2b.sh) | 93 | `cab60234aa6aa91ff5705836c86e8ce1ba6a2700b2d2ec8e5ab09ededd50b5a2` | Y2b: `arrancar` con el procedimiento fijo |
| [`ly_y3.sh`](liyben_3973/ly_y3.sh) | 78 | `7a40c90a45f0ea6a061ae4de0c5e7586e81e358dddf362ad5c704c85a07f2e7a` | Y3: `comprobar` / `CARGAR` de `liyben_ens_14` |
| [`ly_y4.sh`](liyben_3973/ly_y4.sh) | 563 | `0f12c99481062687546843944e9c81696044046a52bea8faa1961e3e00d6a8d3` | Y4: «antes» (A git, B esquema y correspondencia, C antes y P-21) |
| [`ly_y5.sh`](liyben_3973/ly_y5.sh) | 116 | `d649a74d7a6e7833210f5a4b03df879abe25a4a0f8c8c7972083d52a6df5cb44` | Y5: `comprobar` / `ACTUALIZAR` (`-u`) |
| [`ly_y6.sh`](liyben_3973/ly_y6.sh) | 378 | `73315a5f9dd772786c05b7d1a1b9e67fda19a595c0d69b889c92a2878666ae30` | Y6 v3: `comprobar` / `APLICAR_B`, `APLICAR_BP`, `APLICAR_C` |
| [`ly_y7.sh`](liyben_3973/ly_y7.sh) | 272 | `a3b767b70bb82d034825916616fa9d410af128fd63276a321e94a5cc3ebc47cd` | Y7: «después» por SQL |
| [`ly_rehacer.sh`](liyben_3973/ly_rehacer.sh) | 137 | `0d1ac78cde6f65b5bdd455b956b98d0348b8e0b505bd95f44d39fb0e300dd5eb` | `comprobar` / `REHACER` de la copia hasta antes de Y6 |
| [`Dockerfile.14.lab_liyben`](liyben_3973/Dockerfile.14.lab_liyben) | 95 | `7961c769ef8f7627e771723ad5d028ff7b12d4cd009c65fc330396a42412cd50` | `infra/Dockerfile.14` del laboratorio (Y2a): el del VPS más el bloque del core `cc0060e` |

**Notas:**
- `ly_y6.sh` es la v3 (la ejecutada). Las versiones anteriores no entran: v1 (227 líneas,
  `ec7cbbca447d2d6e65c3d79536e1f842a5fd12e4d71d0fe056bc8c04ad1ae76a`, sin quitar Decisión) y v2 (250 líneas,
  `c164ee59270a627854fb319cb7fc617167713671a70007bdfd3f2e791a3e5a89`, medida por el módulo de después).
- `ly_y4.sh`: la línea INFO de «solo uso» sale siempre, aunque no haya casos (también en L0); y, como `ly_y5.sh`, su
  «consultas sin error» busca `ERROR:` y no `psql: error` (lo cubren el marcador final y los valores; corregido en
  `ly_y6.sh` y en las `ld_*`).
- `ly_y3.sh` y `ly_y5.sh` terminan con código 0 aunque fallen (`exit` dentro de `{ … } | tee`): quien las encadene mira
  la línea final (lo hace `ly_rehacer.sh`).
- `ly_y0c.sh`: su `comprobar` es el previo a FIJAR (necesita SSH y no lee la lista); RESTAURAR no tiene ensayo y
  comprueba cada repo después del `checkout`. Con `ly_y0r.sh` antes y después queda cubierto.
- `ly_i0.sh` se lanzó el 19/11 desde el equipo con `ssh … 'bash -s' <`; en L0 se lanza en el VPS con `bash`.
- Las tres `d50_*.sh` ya estaban en el repo (`4c2509c`) y no cambian.
