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
