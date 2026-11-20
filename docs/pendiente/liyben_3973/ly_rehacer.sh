ly_rehacer() (
  set -u
  umask 077
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  una() { tr '\n' ' ' | sed 's/ *$//'; }
  corte() { [ "$F" = 0 ] || { echo "== REHACER: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  MODO=${1:-comprobar}
  case "$MODO" in comprobar|REHACER) ;; *) echo "Uso: ly_rehacer [comprobar|REHACER] (sin argumento: comprobar, que no borra ni carga)"; exit 1 ;; esac
  web() { docker ps --format '{{.Names}}' | grep -cE '^odoo-dev-14-web' || true; }
  pg() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo-dev-14-db-1 psql -U odoo -d "$1" -X -q -At -F '|' 2>&1; }
  L=~/GitHub/lab_liyben_3973
  D=~/pns_ai_3973/liyben
  T="$D/tandas"
  LOGS=~/odoo-dev/14.0/logs
  BD=liyben_ens_14
  COPIA="$D/LIYBEN-20261119-124423.dump"
  H3=7a40c90a45f0ea6a061ae4de0c5e7586e81e358dddf362ad5c704c85a07f2e7a
  H5=d649a74d7a6e7833210f5a4b03df879abe25a4a0f8c8c7972083d52a6df5cb44
  HC=cb6ebff73e4d0e39030efbceccf5e2f2cf57474e8ea1b3484a2e4b4245418d30
  MK3='== Y3: TODO OK. Corte: pega la salida (y la paridad) antes de Y4.'
  MK5='== Y5: TODO OK. Corte: pega la salida antes de Y6.'
  M=$(date +%Y%m%d-%H%M%S)
  O="$D/rehacer-$MODO-$M.txt"
  [ -d "$D" ] || { echo "No existe $D"; exit 1; }
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  lista() { ls -1 "$D"/"$1"-*.txt 2>/dev/null | LC_ALL=C sort; }
  # lanza <tanda> <modo> <prefijo de su salida>: la ejecuta sin entrada y deja en Y su salida nueva (la única que no estaba)
  lanza() {
    local A N
    A=$(lista "$3")
    echo "-- bash $1 $2, lanzado a las $(date +%H:%M:%S) (su salida, con «| » delante)"
    bash "$T/$1" "$2" < /dev/null 2>&1 | sed 's/^/   | /'
    N=$(LC_ALL=C comm -13 <(printf '%s\n' "$A") <(lista "$3") | grep . || true)
    echo "-- terminado a las $(date +%H:%M:%S)"
    chk "$1 $2: una salida nueva ($3-*.txt)" "$(printf '%s\n' "$N" | grep -c . || true)" 1
    Y=$(printf '%s\n' "$N" | head -1); Y=${Y:-/dev/null}
    echo "   salida: $Y"
  }
  # tramos de las salidas de Y3 y Y5, para comparar con la primera pasada
  otros() { awk '/^INFO    otros «Deleting field»/ { f = 1; next } f && /^   / { print; next } { f = 0 }' "$1"; }
  drop() { grep '^INFO    «DROP leftover»' "$1" || true; }
  warn() { awk '/^-- WARNING agrupados/ { f = 1; next } /^INFO    conocidos/ { f = 0 } f' "$1"; }
  conoc() { grep '^INFO    conocidos' "$1" || true; }
  reac() { grep -i 'reactiv' "$(printf '%s' "$1" | sed 's#/y5-ACTUALIZAR-#/y5-actualizar-#')" 2>/dev/null || true; }
  par3() { awk '/^-- líneas de la salida sobre neutralización/ { f = 1; next } /^== 3\./ { f = 0 } f' "$1"; }
  # igual <etiqueta> <tramo> <salida de la primera pasada> <salida de ahora>
  igual() {
    if [ "$($2 "$3")" = "$($2 "$4")" ]; then echo "OK      $1: igual que la primera pasada"
    else echo "INFO    $1: distinto de la primera pasada (no bloquea; diff primera → ahora):"
      diff <($2 "$3") <($2 "$4") | grep '^[<>]' | cut -c1-160 | head -30 | sed 's/^/   /'; fi
  }
  {
  echo "== REHACER ($MODO): borrar $BD y rehacerla hasta antes de Y6 (Y3 CARGAR y Y5 ACTUALIZAR), con el web parado. $M"
  echo "== 1. Comprobaciones previas (solo lectura)"
  chk "ly_y3.sh (huella)" "$(sha256sum "$T/ly_y3.sh" 2>/dev/null | cut -d' ' -f1)" "$H3"
  chk "ly_y5.sh (huella)" "$(sha256sum "$T/ly_y5.sh" 2>/dev/null | cut -d' ' -f1)" "$H5"
  chk "web del kit parado" "$(web)" 0
  E=$(cd "$L" && odoo-dev 14 estado 2>&1)
  chk "contexto activo (BD|repo)" "$(printf '%s\n' "$E" | sed -n 's/^ *BD=//p' | head -1)|$(printf '%s\n' "$E" | sed -n 's/^ *REPO=//p' | head -1)" "lab_liyben_3973_14|$L"
  chk "PostgreSQL del kit en marcha" "$(docker ps --format '{{.Names}}' | grep -cx odoo-dev-14-db-1 || true)" 1
  chk "clones fijados (fijados.tsv, 23 repos)" "$(wc -l < "$D/fijados.tsv" 2>/dev/null | tr -d ' ')" 23
  chk "copia: existe, 600 y huella de Y1" "$(stat -c %a "$COPIA" 2>/dev/null) $(sha256sum "$COPIA" 2>/dev/null | cut -d' ' -f1)" "600 $HC"
  [ "$F" = 0 ] || echo "   (si el único FALLO es PostgreSQL: lanza «cd $L && odoo-dev 14 bd-lista», que no levanta el web, y repite)"
  corte "comprobaciones previas"
  chk "$BD existe" "$(pg postgres <<< "SELECT count(*) FROM pg_database WHERE datname = '$BD';")" 1
  chk "conexiones abiertas a $BD (el borrado fallaría)" "$(pg postgres <<< "SELECT count(*) FROM pg_stat_activity WHERE datname = '$BD';")" 0
  Q=$(pg "$BD" <<'SQL'
SELECT string_agg(name || '|' || state || '|' || latest_version, ' ' ORDER BY name) FROM ir_module_module WHERE name IN ('pns_base','pns_ai_mcp','pns_ai_chatboo');
SELECT string_agg(r.code, ',' ORDER BY r.code) FROM ai_provider_role_rel rr JOIN ai_provider_role r ON r.id = rr.role_id WHERE rr.provider_id = 1;
SQL
)
  chk "consultas sin error" "$(printf '%s\n' "$Q" | grep -ciE 'ERROR:|psql: error' || true)" 0
  chk "$BD como la dejó Y6 APLICAR: versiones de la rama" "$(printf '%s\n' "$Q" | sed -n 1p)" "pns_ai_chatboo|installed|14.0.2.1.587 pns_ai_mcp|installed|14.0.3.1.973 pns_base|installed|14.0.1.2.69"
  chk "$BD como la dejó Y6 APLICAR: roles del proveedor 1" "$(printf '%s\n' "$Q" | sed -n 2p)" "conversation,design,vision"
  R3=$(grep -lx -- "$MK3" "$D"/y3-CARGAR-*.txt 2>/dev/null || true)
  R=$(grep -lx -- "$MK5" "$D"/y5-ACTUALIZAR-*.txt 2>/dev/null || true)
  chk "primera pasada: una Y3 CARGAR con TODO OK" "$(printf '%s\n' "$R3" | grep -c . || true)" 1
  chk "primera pasada: una Y5 ACTUALIZAR con TODO OK" "$(printf '%s\n' "$R" | grep -c . || true)" 1
  R3=${R3:-/dev/null}; R=${R:-/dev/null}
  echo "   referencias: $(basename "$R3") y $(basename "$R")"
  chk "primera pasada: otros «Deleting field» (7)" "$(otros "$R" | grep -c . || true)" 7
  chk "primera pasada: «DROP leftover» (22)" "$(drop "$R" | sed 's/.*: //')" 22
  corte "comprobaciones previas"
  echo "-- control negativo de las dos tandas (sin escribir): cada una debe dar un solo FALLO, el esperado"
  lanza ly_y3.sh comprobar y3-comprobar
  chk "Y3 comprobar: el único FALLO es que $BD ya existe" "$(grep '^FALLO' "$Y" | una)" "FALLO   $BD no existe todavía (bd-lista): esperado [0], obtenido [1]"
  chk "Y3 comprobar: marcador final" "$(grep -cx '== Y3: 1 FALLO(S). No se ha cargado nada.' "$Y" || true)" 1
  lanza ly_y5.sh comprobar y5-comprobar
  chk "Y5 comprobar: el único FALLO son las versiones (ya 3.1.973)" "$(grep '^FALLO' "$Y" | una)" "FALLO   versiones en $BD (todavía 3.1.782): esperado [pns_ai_chatboo|installed|14.0.2.1.453 pns_ai_mcp|installed|14.0.3.1.782 pns_base|installed|14.0.1.2.32], obtenido [pns_ai_chatboo|installed|14.0.2.1.587 pns_ai_mcp|installed|14.0.3.1.973 pns_base|installed|14.0.1.2.69]"
  chk "Y5 comprobar: marcador final" "$(grep -cx '== Y5: 1 FALLO(S). No se ha actualizado nada.' "$Y" || true)" 1
  if [ "$MODO" = comprobar ] || [ "$F" != 0 ]; then
    if [ "$F" = 0 ]; then echo "== REHACER: TODO OK (comprobar: no se ha borrado ni cargado nada)"; else echo "== REHACER: $F FALLO(S). No se ha borrado nada."; fi
    exit 0
  fi

  echo "== 2. [BORRA la BD $BD y su filestore] odoo-dev 14 bd-borrar $BD, lanzado a las $(date +%H:%M:%S)"
  B=$( (cd "$L" && odoo-dev 14 bd-borrar "$BD") < /dev/null 2>&1 ); RC=$?
  echo "-- salida de bd-borrar (20 líneas como mucho)"
  printf '%s\n' "$B" | cut -c1-160 | head -20 | sed 's/^/   /'
  chk "salida de bd-borrar" "$RC" 0 info
  chk "$BD ya no existe" "$(pg postgres <<< "SELECT count(*) FROM pg_database WHERE datname = '$BD';")" 0
  chk "web del kit parado" "$(web)" 0
  corte "borrado"

  echo "== 3. [ALTERA: crea $BD] Y3 CARGAR (mismo .dump de Y1)"
  T0=$(date '+%Y-%m-%d %H:%M:%S')
  lanza ly_y3.sh CARGAR y3-CARGAR
  Y3=$Y
  chk "Y3 CARGAR: TODO OK" "$(grep -cx -- "$MK3" "$Y3" || true)" 1
  for f in carga paridad; do
    chk "log de $f de esta carga ($f-$BD.log, posterior a $T0)" "$( [ -n "$(find "$LOGS/$f-$BD.log" -newermt "$T0" 2>/dev/null)" ] && echo si || echo no)" si
  done
  corte "carga (Y3)"

  echo "== 4. [ALTERA $BD] Y5 ACTUALIZAR (-u de los tres pns_*)"
  lanza ly_y5.sh ACTUALIZAR y5-ACTUALIZAR
  Y5=$Y
  chk "Y5 ACTUALIZAR: TODO OK" "$(grep -cx -- "$MK5" "$Y5" || true)" 1
  corte "-u (Y5)"

  echo "== 5. Comparación con la primera pasada ($(basename "$R3"), $(basename "$R"))"
  chk "otros «Deleting field» iguales" "$(otros "$Y5" | una)" "$(otros "$R" | una)"
  chk "«DROP leftover» igual" "$(drop "$Y5")" "$(drop "$R")"
  igual "WARNING agrupados de Y5" warn "$R" "$Y5"
  igual "WARNING conocidos de Y5" conoc "$R" "$Y5"
  igual "crons reactivados por el -u (salida del kit)" reac "$R" "$Y5"
  igual "líneas de carga y paridad de Y3" par3 "$R3" "$Y3"
  if [ "$F" = 0 ]; then echo "== REHACER: TODO OK. Corte: pega la salida antes de Y6 v3."; else echo "== REHACER: $F FALLO(S). No sigas: pega la salida."; fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ly_rehacer "$@"
