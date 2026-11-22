f26_ctx() (
  # Punto 5, ficha 26, paso 1: cambio del contexto activo de odoo-dev 14 de lab_pns_ai_3973 a lab_pns_ai_cc0060e
  # (core de LIYBEN), para la tanda f26_lab.sh. Procedimiento fijo del laboratorio, sin uso del laboratorio:
  # nadie entra en localhost:8169 (no abras ninguna pestaña).
  #   comprobar (solo lectura): contexto y web parado, laboratorio, imagen y BD, repo y árbol de los módulos.
  #   CAMBIAR   [ARRANCA el web de lab_pns_ai_cc0060e y lo PARA] exige el último comprobar con TODO OK:
  #             arrancar + «Al acabar corto» (espera a werkzeug, guarda el log, C con lab_cdp.py, parar) y
  #             comprueba el contexto nuevo. Da los datos de la fila del registro de laboratorios.
  # Uso: bash ~/Descargas/f26_ctx.sh comprobar | CAMBIAR
  set -u
  umask 077
  MODO=${1:-}
  TANDA="F26 CTX $MODO"
  DL=~/pns_ai_3973/informe
  LAB=lab_pns_ai_cc0060e
  CARPETA=~/GitHub/$LAB
  ANTES=~/GitHub/lab_pns_ai_3973
  BD=lab_pns_ai_cc0060e_14
  IMAGEN=odoo-dev:14-$LAB
  ESTADO=~/odoo-dev/14.0/estado
  LOGS=~/odoo-dev/14.0/logs
  CDP=~/pns_ai_3973/fase4/lab/lab_cdp.py
  WEB=odoo-dev-14-web-1
  REPO=~/GitHub/third_party
  RAMA=14.0-pns-ai-informe
  ARBOL="688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  corte() { [ "$F" = 0 ] || { echo "== $TANDA: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  fin() { if [ "$F" = 0 ]; then echo "== $TANDA: TODO OK.${1:+ $1}"; else echo "== $TANDA: $F FALLO(S). No sigas: pega la salida."; fi; }
  contexto() { sed -n 's/^REPO=//p' "$ESTADO" 2>/dev/null; }
  web() { docker ps --format '{{.Names}}' 2>/dev/null | grep -cx "$WEB" || true; }
  una() { tr '\n' ' ' | sed 's/ *$//'; }
  arbol() {
    ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l ) | tr -d ' '
    ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 \
        | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1 )
  }
  ultima() { ls -t "$DL"/f26_ctx-"$1"-*.txt 2>/dev/null | head -1; }
  marca() { if [ -n "$1" ] && [ -f "$1" ]; then grep -cx -- "$2" "$1" || true; else echo 0; fi; }
  FIN_C="Siguiente: bash ~/Descargas/f26_ctx.sh CAMBIAR (no abras localhost:8169)"
  case "$MODO" in comprobar|CAMBIAR) ;; *) echo "Uso: bash $0 comprobar | CAMBIAR"; exit 1 ;; esac
  mkdir -p "$DL" && chmod 700 "$DL" || exit 1
  O="$DL/f26_ctx-$MODO-$(date +%Y%m%d-%H%M%S).txt"
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== $TANDA (ficha 26, paso 1: contexto lab_pns_ai_3973 → $LAB): $(date '+%F %T')"
  if [ "$MODO" = CAMBIAR ]; then
    UC=$(ultima comprobar)
    chk "último comprobar (${UC##*/}) con TODO OK" "$(marca "$UC" "== F26 CTX comprobar: TODO OK. $FIN_C")" 1
  fi
  echo "== 1. odoo-dev 14 (solo lectura)"
  chk "contexto activo" "$(contexto)" "$ANTES"
  chk "web parado" "$(web)" 0
  chk "carpeta del laboratorio" "$( [ -d "$CARPETA" ] && [ -f "$CARPETA/.odoo-dev.conf" ] && echo si || echo no)" si
  chk "imagen $IMAGEN" "$(docker image ls -q "$IMAGEN" 2>/dev/null | wc -l | tr -d ' ')" 1
  chk "BD $BD en bd-lista" "$( (cd "$CARPETA" 2>/dev/null && odoo-dev 14 bd-lista 2>&1) | grep -cw -- "$BD" || true)" 1
  chk "lab_cdp.py" "$( [ -f "$CDP" ] && echo si || echo no)" si
  echo "== 2. Código montado (third_party)"
  chk "rama de third_party" "$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>&1)" "$RAMA"
  chk "third_party limpio" "$(git -C "$REPO" status --porcelain 2>&1 | wc -l | tr -d ' ')" 0
  chk "árbol de los módulos (archivos y huella)" "$(arbol "$REPO" | una)" "$ARBOL"
  corte "comprobaciones"
  if [ "$MODO" = comprobar ]; then fin "$FIN_C"; exit 0; fi
  echo "== [ARRANCA el web] odoo-dev 14 arrancar desde $CARPETA, a las $(date +%T)"
  ( cd "$CARPETA" && odoo-dev 14 arrancar ) > "$DL/arrancar-$(date +%Y%m%d-%H%M%S).txt" 2>&1
  A=$?
  chk "arrancar: código (salida en $DL/arrancar-*.txt)" "$A" 0
  chk "contexto activo tras arrancar" "$(contexto)" "$CARPETA"
  echo "== Al acabar corto: espera a «HTTP service (werkzeug) running» (máx. 2 min; sin espera si arrancar falló)"
  W=no
  [ "$A" = 0 ] && for i in $(seq 1 40); do
    (cd "$CARPETA" && odoo-dev 14 log 200 2>&1) | grep -q 'HTTP service (werkzeug) running' && { W=si; break; }
    sleep 3
  done
  chk "werkzeug en marcha" "$W" si
  LOG_LAB=$LOGS/servidor-$(date +%Y%m%d-%H%M%S).log
  (cd "$CARPETA" && odoo-dev 14 log all) > "$LOG_LAB" 2>&1
  echo "   log guardado: $LOG_LAB ($(wc -l < "$LOG_LAB" | tr -d ' ') líneas)"
  python3 -I "$CDP" c --lab "$LAB" --bd "$BD" < "$LOG_LAB" 2>&1 | sed 's/^/   /'
  C=${PIPESTATUS[0]}
  chk "C: código" "$C" 0
  ( cd "$CARPETA" && odoo-dev 14 parar ) 2>&1 | tail -3 | sed 's/^/   /'
  echo "== Después (solo lectura)"
  chk "contexto activo" "$(contexto)" "$CARPETA"
  chk "web parado" "$(web)" 0
  echo "   para el registro: primera línea $(grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}' "$LOG_LAB" | head -1) UTC,"\
       "última $(grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}' "$LOG_LAB" | tail -1) UTC;"\
       "Starting job: $(grep -c 'ir_cron: Starting job' "$LOG_LAB" || true)"
  fin "Contexto $LAB con el web parado. Pega la salida; después, f26_lab.sh leer."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
f26_ctx "$@"
