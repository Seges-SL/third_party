ly_y2b() (
  set -u
  umask 077
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  web() { docker ps --format '{{.Names}}' | grep -cE '^odoo-dev-14-web' || true; }
  L=~/GitHub/lab_liyben_3973
  D=~/pns_ai_3973/liyben
  LOGS=~/odoo-dev/14.0/logs
  BD=lab_liyben_3973_14
  M=$(date +%Y%m%d-%H%M%S)
  O="$D/y2b-$M.txt"
  A="$D/y2b-arrancar-$M.txt"
  SL="$LOGS/servidor-$M.log"
  [ -d "$D" ] && [ -d "$LOGS" ] || { echo "No existe $D o $LOGS"; exit 1; }
  [ ! -e "$O" ] && [ ! -e "$SL" ] || { echo "Ya existe $O o $SL: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  ARR=0; HECHO=0
  al_acabar() {
    [ "$ARR" = 1 ] && [ "$HECHO" = 0 ] || return 0
    echo "== Corte: la tanda no terminó. Guardo el log y paro el servidor (procedimiento fijo)"
    [ -e "$SL" ] || odoo-dev 14 log all > "$SL" 2>&1
    echo "log: $SL ($(wc -l < "$SL" | tr -d ' ') líneas)"
    ( cd "$L" && odoo-dev 14 parar > /dev/null 2>&1 )
    echo "web en marcha tras parar: $(web)"
    echo "== Y2b: CORTADA. No sigas: pega la salida."
  }
  trap al_acabar EXIT
  trap 'exit 130' INT TERM
  echo "== Y2b (arrancar del laboratorio $L, con construcción de la imagen): $M"
  echo "== 1. Comprobaciones previas"
  chk "web del kit parado" "$(web)" 0
  chk "huellas de Y2a (CLAUDE.md, .odoo-dev.conf, Dockerfile)" "$(cd "$L" 2>/dev/null && sha256sum CLAUDE.md .odoo-dev.conf infra/Dockerfile.14 | cut -c1-16 | tr '\n' ' ' | sed 's/ $//')" "a445fd79f9efdde3 52852470998ce7d2 7961c769ef8f7627"
  chk "clones fijados (fijados.tsv, 23 repos)" "$(wc -l < "$D/fijados.tsv" 2>/dev/null | tr -d ' ')" 23
  chk "third_party: rama y cambios sin commit" "$(git -C ~/GitHub/third_party rev-parse --abbrev-ref HEAD) $(git -C ~/GitHub/third_party status --porcelain | wc -l | tr -d ' ')" "14.0-pns-ai-3973 0"
  chk "LIYBEN: rama, commit y cambios sin commit" "$(git -C ~/GitHub/LIYBEN rev-parse --abbrev-ref HEAD) $(git -C ~/GitHub/LIYBEN rev-parse --short=7 HEAD) $(git -C ~/GitHub/LIYBEN status --porcelain | wc -l | tr -d ' ')" "14.0 ff34570 0"
  chk "tu vertical-instaladores fuera de 14.0* (el kit monta la publicada)" "$(case "$(git -C ~/GitHub/vertical-instaladores rev-parse --abbrev-ref HEAD)" in 14.0*) echo no ;; *) echo si ;; esac)" si
  chk "vertical-instaladores publicada, fijada en el commit del VPS" "$(git -C ~/odoo-dev/14.0/vertical-instaladores rev-parse --short=7 HEAD)" 7c05906
  [ "$F" = 0 ] || { echo "== Y2b: $F FALLO(S). No se ha arrancado nada."; exit 1; }
  read -rp "¿Ninguna pestaña de localhost:8169 abierta en ningún navegador? [s/N] " RESP < /dev/tty
  chk "sin pestañas de localhost:8169" "$RESP" s
  [ "$F" = 0 ] || { echo "== Y2b: no se ha arrancado nada. Cierra las pestañas y repite."; exit 1; }

  echo "== 2. [ALTERA] odoo-dev 14 arrancar desde $L (construye odoo-dev:14-lab_liyben_3973 la primera vez; puede tardar), lanzado a las $(date +%H:%M:%S)"
  ARR=1
  ( cd "$L" && odoo-dev 14 arrancar ) > "$A" 2>&1 < /dev/null
  RC=$?
  echo "terminado a las $(date +%H:%M:%S); salida completa en $A ($(wc -l < "$A" | tr -d ' ') líneas); últimas:"
  tail -12 "$A" | cut -c1-160 | sed 's/^/   /'
  chk "salida de arrancar" "$RC" 0
  [ "$F" = 0 ] || exit 1

  echo "== 3. Espera a «HTTP service (werkzeug) running» (hasta 5 minutos)"
  n=0; i=0
  while [ "$i" -lt 60 ]; do
    n=$(odoo-dev 14 log all 2>/dev/null | grep -c 'HTTP service (werkzeug) running' || true)
    [ "$n" -ge 1 ] && break
    sleep 5; i=$((i + 1))
  done
  chk "servidor en marcha (HTTP service running)" "$( [ "$n" -ge 1 ] && echo si || echo no)" si
  [ "$F" = 0 ] || exit 1
  odoo-dev 14 log all > "$SL" 2>&1
  echo "log guardado: $SL ($(wc -l < "$SL" | tr -d ' ') líneas)"

  echo "== 4. Comprobación C sobre el log guardado"
  ODOO=$(sed 's/^[^|]*| //' "$SL" | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9:,]+ [0-9]+ [A-Z]+ ')
  chk "líneas de Odoo en el log" "$( [ -n "$ODOO" ] && echo si || echo no)" si
  BDS=$(printf '%s\n' "$ODOO" | awk '{print $5}' | sort -u | tr '\n' ' ' | sed 's/ $//')
  echo "BD con líneas: $BDS"
  chk "BD con líneas fuera de «?» y $BD" "$(printf '%s\n' "$ODOO" | awk -v b="$BD" '$5 != "?" && $5 != b {print $5}' | sort -u | tr '\n' ' ' | sed 's/ $//')" ""
  chk "BD con «Starting job» (crons)" "$(printf '%s\n' "$ODOO" | grep 'Starting job' | awk '{print $5}' | sort -u | tr '\n' ' ' | sed 's/ $//')" ""
  echo "Traceback: $(grep -c 'Traceback' "$SL" || true) · ERROR: $(printf '%s\n' "$ODOO" | awk '$4 == "ERROR"' | grep -c . || true) · CRITICAL: $(printf '%s\n' "$ODOO" | awk '$4 == "CRITICAL"' | grep -c . || true) (informativo)"

  echo "== 5. [ALTERA] odoo-dev 14 parar"
  ( cd "$L" && odoo-dev 14 parar ) > /dev/null 2>&1
  chk "web del kit parado" "$(web)" 0

  echo "== 6. Contexto nuevo (odoo-dev 14 estado, solo lectura)"
  E=$(cd "$L" && odoo-dev 14 estado 2>&1)
  chk "BD del contexto" "$(printf '%s\n' "$E" | sed -n 's/^ *BD=//p' | head -1)" "$BD"
  chk "repo del contexto" "$(printf '%s\n' "$E" | sed -n 's/^ *REPO=//p' | head -1)" "$L"
  chk "imagen del contexto" "$(printf '%s\n' "$E" | sed -n 's/^ *IMAGEN=//p' | head -1)" "odoo-dev:14-lab_liyben_3973"
  printf '%s\n' "$E" | grep -E '^ *(compartidos|third_party|vertical-instaladores|LIYBEN|OCA|imagen)' | sed 's/^ */   /'
  HECHO=1
  if [ "$F" = 0 ]; then echo "== Y2b: TODO OK. Corte: pega la salida antes de cargar la copia (Y3)."; else echo "== Y2b: $F FALLO(S). No sigas: pega la salida."; fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ly_y2b
