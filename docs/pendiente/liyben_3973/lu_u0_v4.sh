lu_u0() (
  # U0 del uso real en LIYBEN: estado de partida, de solo lectura, desde el equipo por SSH (en el VPS no escribe nada).
  # Compara sección a sección el SQL de L6 (l6_despues.sql, el mismo del despliegue) con el «después» de L6 y resume el
  # log del servidor desde el arranque de L5. Escribe solo en ~/pns_ai_3973/liyben/uso/ (700).
  set -u
  umask 077
  TANDA="LU U0"
  REPO=~/GitHub/third_party
  SQL="$REPO/docs/pendiente/liyben_3973/l6_despues.sql"
  SQL_SHA=d58c9f7188422273f4ea1e88aaee88441b474cc6425a4a2dd1a63d5d23110fc0
  V=~/pns_ai_3973/liyben/despliegue/vps
  DEP=~/pns_ai_3973/liyben/despliegue
  REF_SHA=b673205e4426f0ec84c6cb2acc15af06dfa1d9d27fa904f5dc86fb6b96700967
  U=~/pns_ai_3973/liyben/uso
  CLON=/opt/odoo/addons/custom/third_party
  # v4 (merge, punto 3): el clon en 14.0, en el merge commit que guardó lm_e.sh despues (primer hash de merge.txt).
  MERGE_TXT=~/pns_ai_3973/liyben/merge/merge.txt
  COMMIT=$(cut -d' ' -f1 "$MERGE_TXT" 2>/dev/null)
  RAMA=14.0
  L8_LINEAS=492
  VOLATILES="operaciones por status|trusted|diario|chatboo|ai_log"
  # Ajustes aprobados por Sergio sobre el «después» de L6 (sección|valor esperado ahora), uno por línea.
  # cadena: la fila 2 se quitó en L7 (11:04:38 UTC) y se volvió a crear como la 3 (11:32:16 UTC, usuario 6); opción A, 12:36.
  AJUSTES="cadena|3|pns_ai_chatboo|0|t|f|2|t"
  # Usuarios MCP (id|user_id|estado|tiene hash): la clave generada en U1 (11:45:14 UTC) se borró a las 11:55:13 (opción b, D60).
  MCP_ESPERADO="1|2|not_generated|f 2|7|not_generated|f 3|6|not_generated|f"
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  una() { tr '\n' ' ' | sed 's/ *$//'; }
  sec() { printf '%s\n' "$1" | awk -v s="## $2" '/^## /{p = ($0 == s); next} p'; }
  secs() { printf '%s\n' "$1" | sed -n 's/^## //p'; }
  corte() { [ "$F" = 0 ] || { echo "== $TANDA: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  fin() { if [ "$F" = 0 ]; then echo "== $TANDA: TODO OK.${1:+ $1}"; else echo "== $TANDA: $F FALLO(S). No sigas: pega la salida."; fi; }
  [ -n "${VPS_PORT:-}" ] && [ -n "${VPS_DEST:-}" ] || { echo "Faltan VPS_PORT y VPS_DEST: lánzalas con la línea read de antes"; exit 1; }
  vps() { ssh -T -p "$VPS_PORT" "$VPS_DEST" "$@"; }
  mkdir -p -m 700 "$U" || exit 1
  M=$(date +%Y%m%d-%H%M%S)
  O="$U/u0-$M.txt"; A="$U/u0_estado-$M.txt"
  [ ! -e "$O" ] && [ ! -e "$A" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== $TANDA (equipo → VPS por SSH: estado de LIYBEN antes del uso real; solo lectura): $(date '+%F %T')"
  echo "== 1. Comprobaciones previas (equipo)"
  chk "l6_despues.sql del repo (SHA-256)" "$(sha256sum "$SQL" 2>/dev/null | cut -d' ' -f1)" "$SQL_SHA"
  REF=$(ls "$V"/l6_despues-*.txt 2>/dev/null)
  chk "un solo «después» de L6 en vps/" "$(printf '%s' "$REF" | grep -c . || true)" 1
  chk "«después» de L6 (${REF##*/}, SHA-256)" "$(sha256sum "$REF" 2>/dev/null | cut -d' ' -f1)" "$REF_SHA"
  T0U=$(cat "$V/l4_t0.txt" 2>/dev/null)
  chk "inicio del -u de L4 (vps/l4_t0.txt)" "$(printf '%s' "$T0U" | grep -cxE '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}' || true)" 1
  OFF=$(cat "$V/l5_offset.txt" 2>/dev/null)
  chk "posición del log de L5 (vps/l5_offset.txt)" "$(printf '%s' "$OFF" | grep -cxE '[0-9]+' || true)" 1
  echo "   inicio del -u: $T0U UTC; log desde el byte $OFF"
  chk "merge commit de merge.txt (v4)" "$(printf '%s' "$COMMIT" | grep -cxE '[0-9a-f]{40}' || true)" 1
  for C in "LIYBEN-antes-20261120-114331.dump|49300282" "LIYBEN-filestore-antes-20261120-114331.tar|567234560"; do
    N=${C%|*}
    chk "copia de L3 $N (tamaño|permisos): la vuelta atrás E sigue" "$(stat -c '%s|%a' "$DEP/$N" 2>&1)" "${C#*|}|600"
  done
  corte "comprobaciones previas"

  echo "== 2. VPS: web, código montado y log desde el arranque de L5 (solo lectura; sin mensajes del log)"
  R=$(vps "bash -s -- $OFF $CLON" <<'REMOTO' 2>&1
set -u
OFF=$1; CLON=$2; L=/opt/odoo/logs/odoo-server.log
echo "web|$(cd /opt/odoo && docker compose ps --status running --services 2>/dev/null | grep -cx web || true)"
echo "head|$(git --no-optional-locks -c safe.directory="$CLON" -C "$CLON" rev-parse --abbrev-ref HEAD 2>&1)|$(git --no-optional-locks -c safe.directory="$CLON" -C "$CLON" rev-parse HEAD 2>&1)"
echo "limpio|$(git --no-optional-locks -c safe.directory="$CLON" -C "$CLON" status --porcelain 2>&1 | wc -l)"
S=$(stat -c %s "$L"); echo "rotado|$( [ "$S" -ge "$OFF" ] && echo no || echo si)"
[ "$S" -ge "$OFF" ] || { echo "fin|1"; exit 0; }
X() { tail -c +"$((OFF + 1))" "$L"; }
echo "lineas|$(X | wc -l)"
echo "ultima|$(X | grep -oE '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}' | tail -1)"
echo "err|$(X | grep -cE ' (ERROR|CRITICAL) ' || true)"
echo "tb|$(X | grep -c '^Traceback' || true)"
echo "chatboo|$(X | grep -c '/chatboo' || true)"
echo "mcp|$(X | grep -c ' /mcp' || true)"
echo "callbutton|$(X | grep -c '"POST /web/dataset/call_button' || true)"
X | awk '/MCP: API key (generated|deleted|forced\/imported) for user/ { t = $2; sub(/,.*/, "", t); match($0, /MCP: API key [a-z\/]+/); a = substr($0, RSTART + 13, RLENGTH - 13); id = $0; sub(/.*\(ID: /, "", id); sub(/\).*/, "", id); print "k|" $1 " " t "|" a "|" id }'
X | grep -oE ' (WARNING|ERROR|CRITICAL) [^ ]+ [^ ]+:' | sort | uniq -c | sed 's/^/w|/'
X | awk '
/ (ERROR|CRITICAL) / { split($0, a, " "); print "t|   ## " a[2] " " a[4] " " a[6]; next }
/^Traceback/ { tb = 1; print "t|     Traceback"; next }
tb && /^  File "/ { l = $0; sub(/^  File "/, "", l); sub(/^.*\/(pns|odoo)\//, "", l); gsub(/"/, "", l); print "t|       " l; next }
tb && /^[A-Za-z_][A-Za-z0-9_.]*(:|$)/ { e = $0; m = e; sub(/:.*/, "", e); sub(/^[^:]*:? */, "", m); if (m ~ /^[0-9]+$/) e = e ": " m; print "t|     -> " e; tb = 0; next }
'
echo "fin|1"
REMOTO
)
  k() { printf '%s\n' "$R" | sed -n "s/^$1|//p" | head -1; }
  chk "respuesta completa del VPS" "$(k fin)" 1
  corte "SSH"
  chk "web en marcha" "$(k web)" 1
  chk "rama y HEAD del clon (14.0 en el merge; los pns_* = el desplegado)" "$(k head)" "$RAMA|$COMMIT"
  chk "código montado sin cambios (git status --porcelain)" "$(k limpio)" 0
  chk "el log no se ha rotado desde L5" "$(k rotado)" no
  corte "web y código"
  LN=$(k lineas)
  echo "   log desde el arranque: $LN líneas (L8: $L8_LINEAS; nuevas desde L8: $((LN - L8_LINEAS))); última hora: $(k ultima) UTC"
  chk "ERROR o CRITICAL desde el arranque" "$(k err)" 0 info
  chk "Traceback desde el arranque" "$(k tb)" 0 info
  printf '%s\n' "$R" | sed -n 's/^t|//p'
  chk "peticiones a /chatboo desde el arranque (nadie lo ha usado)" "$(k chatboo)" 0 info
  chk "peticiones a /mcp desde el arranque" "$(k mcp)" 0 info
  echo "INFO    botones (call_button) desde el arranque: $(k callbutton)"
  echo "-- acciones sobre claves MCP desde el arranque (fecha hora UTC|acción|ID de usuario); esperado: generated y deleted del 6 (U1)"
  printf '%s\n' "$R" | sed -n 's/^k|/   /p'
  echo "-- nivel y logger (WARNING/ERROR/CRITICAL), sin el mensaje (en L8: 84 decimal_precision, 32 odoo.models, 4 py.warnings)"
  printf '%s\n' "$R" | sed -n 's/^w|/   /p'

  echo "== 3. LIYBEN por SQL (l6_despues.sql, sesión de solo lectura; salida completa en $A)"
  RD=$( { printf "\\\\set t0 '%s'\n" "$T0U"; cat "$SQL"; } | vps "docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_db sh -c 'psql -U \"\$POSTGRES_USER\" -d LIYBEN -X -q -At -F \"|\"'" 2>&1)
  printf '%s\n' "$RD" > "$A"
  echo "guardado: $A ($(wc -l < "$A" | tr -d ' ') líneas, SHA-256 $(sha256sum "$A" | cut -d' ' -f1))"
  chk "consultas sin error" "$(printf '%s\n' "$RD" | grep -ciE 'ERROR:|psql: error' || true)" 0
  printf '%s\n' "$RD" | grep -iE 'ERROR:|psql: error' | head -5 | cut -c1-160 | sed 's/^/   /'
  chk "marcador final de la salida SQL" "$(printf '%s\n' "$RD" | grep -cx '## fin' || true)" 1
  corte "consultas"
  RA=$(cat "$REF")
  chk "secciones = las del «después» de L6" "$(secs "$RD" | una)" "$(secs "$RA" | una)"
  corte "secciones"

  echo "== 4. Comparación con el «después» de L6 (10:56:46 UTC): estructura (FALLO si cambia) y uso (INFO)"
  CMP=$(secs "$RA" | while IFS= read -r S; do
    [ "$S" = fin ] && continue
    AJ=$(printf '%s\n' "$AJUSTES" | awk -F'|' -v s="$S" '$1 == s { sub(/^[^|]*\|/, ""); print }')
    if [ -n "$AJ" ]; then
      chk "$S, = L6 con el ajuste aprobado" "$(sec "$RD" "$S" | una)" "$AJ"
    elif printf '%s\n' "$S" | grep -qxE "$VOLATILES"; then
      chk "$S, = L6 (uso)" "$(sec "$RD" "$S" | una)" "$(sec "$RA" "$S" | una)" info
    else
      chk "$S, = L6" "$(sec "$RD" "$S" | una)" "$(sec "$RA" "$S" | una)"
    fi
  done)
  printf '%s\n' "$CMP"
  F=$((F + $(printf '%s\n' "$CMP" | grep -c '^FALLO' || true)))
  echo "   secciones comparadas: $(secs "$RA" | grep -vcx fin); con ajuste aprobado: $(printf '%s\n' "$AJUSTES" | grep -c . || true)"
  echo "-- cadena completa, para H (id|agente|proveedor|prioridad|activa|idle s|ronda s|skip_sync_fallback|create_uid|creada UTC)"
  RC=$(vps "docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_db sh -c 'psql -U \"\$POSTGRES_USER\" -d LIYBEN -X -q -At -F \"|\"'" 2>&1 <<'SQLC'
SELECT ap.id, a.code, ap.provider_id, ap.priority, ap.active, ap.llm_idle_timeout, ap.llm_round_timeout,
       ap.skip_sync_fallback, ap.create_uid, to_char(ap.create_date, 'YYYY-MM-DD HH24:MI:SS')
  FROM ai_agent_provider ap LEFT JOIN ai_agent a ON a.id = ap.agent_id ORDER BY a.code, ap.priority, ap.id;
SQLC
)
  printf '%s\n' "$RC" | sed 's/^/   /'
  chk "cadena completa sin error" "$(printf '%s\n' "$RC" | grep -ciE 'ERROR:|psql: error' || true)" 0
  RM=$(vps "docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_db sh -c 'psql -U \"\$POSTGRES_USER\" -d LIYBEN -X -q -At -F \"|\"'" 2>&1 <<'SQLM'
SELECT id, user_id, coalesce(mcp_api_key_state, '-'), coalesce(mcp_api_key_hash, '') <> '' FROM ai_mcp_user ORDER BY id;
SQLM
)
  chk "usuarios MCP (id|user_id|estado|tiene hash): ninguna clave (D60)" "$(printf '%s\n' "$RM" | tr '\n' ' ' | sed 's/ *$//')" "$MCP_ESPERADO"

  echo "== 5. Respuesta pública (equipo)"
  chk "liyben.com/web/login" "$(curl -sS -o /dev/null -w '%{http_code}' https://liyben.com/web/login 2>&1)" 200
  chk "GET liyben.com/mcp (Nginx, D20)" "$(curl -sS -o /dev/null -w '%{http_code}' https://liyben.com/mcp 2>&1)" 404
  fin "Pega la salida antes del siguiente paso de interfaz."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
lu_u0
