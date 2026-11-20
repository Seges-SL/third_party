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
