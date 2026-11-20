ly_y3() (
  set -u
  umask 077
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  MODO=${1:-comprobar}
  case "$MODO" in comprobar|CARGAR) ;; *) echo "Uso: ly_y3 [comprobar|CARGAR] (sin argumento: comprobar, que no escribe)"; exit 1 ;; esac
  web() { docker ps --format '{{.Names}}' | grep -cE '^odoo-dev-14-web' || true; }
  pg() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo-dev-14-db-1 psql -U odoo -d "$1" -X -q -At -F '|' 2>&1; }
  L=~/GitHub/lab_liyben_3973
  D=~/pns_ai_3973/liyben
  LOGS=~/odoo-dev/14.0/logs
  BD=liyben_ens_14
  COPIA="$D/LIYBEN-20261119-124423.dump"
  M=$(date +%Y%m%d-%H%M%S)
  O="$D/y3-$MODO-$M.txt"
  S="$D/y3-bdcargar-$M.txt"
  [ -d "$D" ] || { echo "No existe $D"; exit 1; }
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== Y3 ($MODO): copia de LIYBEN como $BD en el contexto lab_liyben_3973, con el web parado. $M"
  echo "== 1. Comprobaciones previas (solo lectura)"
  chk "web del kit parado" "$(web)" 0
  E=$(cd "$L" && odoo-dev 14 estado 2>&1)
  chk "contexto activo (BD|repo)" "$(printf '%s\n' "$E" | sed -n 's/^ *BD=//p' | head -1)|$(printf '%s\n' "$E" | sed -n 's/^ *REPO=//p' | head -1)" "lab_liyben_3973_14|$L"
  A=$(ls -t "$D"/y2b-arrancar-*.txt 2>/dev/null | head -1)
  chk "huellas del core cc0060e en la construcción (Y2b), sin la traza «+ echo»: OK|DISTINTA" "$(grep 'huella odoo/' "$A" 2>/dev/null | grep -v '+ echo' | grep -c '(OK)$' || true)|$(grep 'huella odoo/' "$A" 2>/dev/null | grep -v '+ echo' | grep -c '(DISTINTA)$' || true)" "5|0"
  chk "copia: existe, 600 y huella de Y1" "$(stat -c %a "$COPIA" 2>/dev/null) $(sha256sum "$COPIA" 2>/dev/null | cut -d' ' -f1)" "600 cb6ebff73e4d0e39030efbceccf5e2f2cf57474e8ea1b3484a2e4b4245418d30"
  echo "-- odoo-dev 14 bd-lista (levanta solo el contenedor de PostgreSQL, sin web ni crons)"
  BL=$(cd "$L" && odoo-dev 14 bd-lista 2>&1)
  chk "$BD no existe todavía (bd-lista)" "$(printf '%s\n' "$BL" | grep -cx "$BD" || true)" 0
  chk "PostgreSQL del kit en marcha" "$(docker ps --format '{{.Names}}' | grep -cx odoo-dev-14-db-1)" 1
  chk "clones fijados (fijados.tsv, 23 repos)" "$(wc -l < "$D/fijados.tsv" 2>/dev/null | tr -d ' ')" 23
  chk "espacio libre en / (al menos 3 GB)" "$( [ "$(df --output=avail -B1 / | tail -1 | tr -d ' ')" -ge 3000000000 ] && echo si || echo no)" si
  if [ "$MODO" = comprobar ] || [ "$F" != 0 ]; then
    if [ "$F" = 0 ]; then echo "== Y3: TODO OK (comprobar: no se ha tocado nada)"; else echo "== Y3: $F FALLO(S). No se ha cargado nada."; fi
    exit 0
  fi

  echo "== 2. [ALTERA: crea la BD $BD y su filestore vacío] odoo-dev 14 bd-cargar, lanzado a las $(date +%H:%M:%S)"
  ( cd "$L" && odoo-dev 14 bd-cargar "$COPIA" --bd "$BD" ) > "$S" 2>&1 < /dev/null
  RC=$?
  echo "terminado a las $(date +%H:%M:%S); salida completa en $S ($(wc -l < "$S" | tr -d ' ') líneas)"
  chk "salida de bd-cargar" "$RC" 0 info
  echo "-- líneas de la salida sobre neutralización, carga y paridad"
  grep -iE 'neutraliz|carg|paridad|instalad|iguales|distint|sin c[oó]digo|no se importa|fallar|error' "$S" | cut -c1-160 | head -40 | sed 's/^/   /'

  echo "== 3. Después (solo lectura)"
  chk "web del kit parado (bd-cargar no lo levanta)" "$(web)" 0
  chk "$BD existe" "$(pg postgres <<< "SELECT count(*) FROM pg_database WHERE datname = '$BD';")" 1
  N=$(cd "$L" && odoo-dev 14 estado --bd "$BD" 2>&1 | grep -i 'neutraliz' | head -1)
  echo "estado --bd: $N"
  chk "$BD neutralizada por el kit" "$(printf '%s' "$N" | grep -qi 'NO neutralizada' && echo no || (printf '%s' "$N" | grep -qi 'neutralizada' && echo si || echo no))" si
  Q=$(pg "$BD" <<'SQL'
SELECT string_agg(name || '|' || latest_version, ' ' ORDER BY name) FROM ir_module_module WHERE name IN ('pns_base','pns_ai_mcp','pns_ai_chatboo') AND state = 'installed';
SELECT count(*) FROM ir_module_module WHERE state = 'installed';
SELECT count(*) FROM res_partner WHERE signup_token IS NOT NULL;
SELECT count(*) FROM ir_cron WHERE active;
SQL
)
  chk "versiones de pns_* en la copia (3.1.782)" "$(printf '%s\n' "$Q" | sed -n 1p)" "pns_ai_chatboo|14.0.2.1.453 pns_ai_mcp|14.0.3.1.782 pns_base|14.0.1.2.32"
  chk "módulos instalados (I0: 215)" "$(printf '%s\n' "$Q" | sed -n 2p)" 215
  chk "tokens de registro (I0: 8)" "$(printf '%s\n' "$Q" | sed -n 3p)" 8
  chk "crons activos tras neutralizar" "$(printf '%s\n' "$Q" | sed -n 4p)" 0 info
  for f in "$LOGS/carga-$BD.log" "$LOGS/paridad-$BD.log"; do
    if [ -e "$f" ]; then echo "-- $f ($(wc -l < "$f" | tr -d ' ') líneas; ERROR: $(grep -c 'ERROR' "$f" || true))"
    else echo "INFO    no existe $f (no bloquea)"; fi
  done
  [ -e "$LOGS/paridad-$BD.log" ] && { echo "-- paridad (primeras 60 líneas no vacías)"; grep -v '^[[:space:]]*$' "$LOGS/paridad-$BD.log" | head -60 | cut -c1-160 | sed 's/^/   /'; }
  if [ "$F" = 0 ]; then echo "== Y3: TODO OK. Corte: pega la salida (y la paridad) antes de Y4."; else echo "== Y3: $F FALLO(S). No sigas: pega la salida."; fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ly_y3 "$@"
