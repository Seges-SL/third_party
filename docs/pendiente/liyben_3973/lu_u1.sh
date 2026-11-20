lu_u1() (
  # U1 del uso real en LIYBEN, después de la interfaz: log del servidor desde el inicio de U1 y recuentos de Chatboo.
  # Solo lectura, desde el equipo por SSH (en el VPS no escribe nada). Escribe solo en ~/pns_ai_3973/liyben/uso/.
  # Antes de la interfaz: date -u '+%F %T' > ~/pns_ai_3973/liyben/uso/u1_inicio.txt
  set -u
  umask 077
  TANDA="LU U1"
  U=~/pns_ai_3973/liyben/uso
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  sec() { printf '%s\n' "$1" | awk -v s="## $2" '/^## /{p = ($0 == s); next} p'; }
  k() { printf '%s\n' "$R" | sed -n "s/^$1|//p" | head -1; }
  corte() { [ "$F" = 0 ] || { echo "== $TANDA: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  fin() { if [ "$F" = 0 ]; then echo "== $TANDA: TODO OK.${1:+ $1}"; else echo "== $TANDA: $F FALLO(S). No sigas: pega la salida."; fi; }
  [ -n "${VPS_PORT:-}" ] && [ -n "${VPS_DEST:-}" ] || { echo "Faltan VPS_PORT y VPS_DEST: lánzalas con la línea read de antes"; exit 1; }
  vps() { ssh -T -p "$VPS_PORT" "$VPS_DEST" "$@"; }
  M=$(date +%Y%m%d-%H%M%S)
  O="$U/u1-$M.txt"; A="$U/u1_estado-$M.txt"
  [ -d "$U" ] && [ ! -e "$O" ] || { echo "Falta $U o ya existe $O"; exit 1; }
  {
  echo "== $TANDA (equipo → VPS por SSH: log y Chatboo desde el inicio de U1; solo lectura): $(date '+%F %T')"
  echo "== 1. Comprobaciones previas (equipo)"
  U0=$(ls -t "$U"/u0-*.txt 2>/dev/null | head -1)
  chk "última U0 (${U0##*/}) con TODO OK" "$(grep -cx '== LU U0: TODO OK. Pega la salida antes de U1 (interfaz).' "$U0" 2>/dev/null || true)" 1
  INI=$(cat "$U/u1_inicio.txt" 2>/dev/null)
  chk "inicio de U1 (u1_inicio.txt, UTC)" "$(printf '%s' "$INI" | grep -cxE '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}' || true)" 1
  chk "inicio de U1 posterior a la última U0" "$( [ "$(date -u -d "$INI" +%s 2>/dev/null || echo 0)" -ge "$(date -u -r "$U0" +%s)" ] && echo si || echo no)" si
  echo "   inicio de U1: $INI UTC"
  corte "comprobaciones previas"

  echo "== 2. VPS: log desde el inicio de U1 (rutas sin parámetros ni IP; sin mensajes salvo los del motor que se cuentan)"
  R=$(vps "bash -s -- '$INI'" <<'REMOTO' 2>&1
set -u
INI=$1; L=/opt/odoo/logs/odoo-server.log
X() { awk -v s="$INI" '/^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}/ { p = (substr($0, 1, 19) >= s) } p' "$L"; }
echo "lineas|$(X | wc -l)"
echo "ultima|$(X | grep -oE '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}' | tail -1)"
echo "err|$(X | grep -cE ' (ERROR|CRITICAL) ' || true)"
echo "tb|$(X | grep -c '^Traceback' || true)"
echo "design|$(X | grep -c 'AI: no provider holds role "design" for agent "pns_ai_chatboo"' || true)"
echo "nochain|$(X | grep -c 'system provider(s) for agent "pns_ai_chatboo" (no chain)' || true)"
echo "asking|$(X | grep -c '; asking "' || true)"
echo "serial|$(X | grep -c 'SERIALIZATION_FAILURE' || true)"
X | awk '/ werkzeug: / && match($0, /"(GET|POST) [^ "?]+[^"]*" [0-9]+/) {
  s = substr($0, RSTART + 1, RLENGTH - 1); n = split(s, a, " "); sub(/\?.*/, "", a[2])
  if (a[2] ~ /^\/chatboo/ || a[2] ~ /^\/web\/dataset\/call_kw\/(ai\.|chatboo)/) c[a[2] " " a[n]]++
} END { for (x in c) print "r|" c[x] " " x }'
X | grep -oE ' (WARNING|ERROR|CRITICAL) [^ ]+ [^ ]+:' | sort | uniq -c | sed 's/^/w|/'
X | awk '
/ (ERROR|CRITICAL) / { split($0, a, " "); print "t|   ## " a[2] " " a[4] " " a[6]; next }
/^Traceback/ { tb = 1; print "t|     Traceback"; next }
tb && /^  File "/ { l = $0; sub(/^  File "/, "", l); sub(/^.*\/(pns|odoo)\//, "", l); gsub(/"/, "", l); print "t|       " l; next }
tb && /^[A-Za-z_][A-Za-z0-9_.]*(:|$)/ { e = $0; sub(/:.*/, "", e); print "t|     -> " e; tb = 0; next }
'
echo "fin|1"
REMOTO
)
  chk "respuesta completa del VPS" "$(k fin)" 1
  corte "SSH"
  echo "   log desde el inicio de U1: $(k lineas) líneas; última hora: $(k ultima) UTC"
  chk "ERROR o CRITICAL" "$(k err)" 0
  chk "Traceback" "$(k tb)" 0
  printf '%s\n' "$R" | sed -n 's/^t|//p'
  chk "«no provider holds role design» para Chatboo (botón Canvas oculto, D62): al menos 1" "$( [ "$(k design)" -ge 1 ] 2>/dev/null && echo si || echo no)" si
  echo "   veces: $(k design)"
  chk "Chatboo sin cadena (usaría todos los proveedores activos)" "$(k nochain)" 0
  chk "roles que piden su alternativa (Diseño no tiene)" "$(k asking)" 0 info
  chk "SERIALIZATION_FAILURE" "$(k serial)" 0 info
  echo "-- peticiones a /chatboo y a ai.*/chatboo.* (n ruta código)"
  printf '%s\n' "$R" | sed -n 's/^r|//p' | sort -k2 | sed 's/^/   /'
  chk "peticiones a /chatboo/canvas/* (sin botón no debe haber)" "$(printf '%s\n' "$R" | sed -n 's/^r|//p' | grep -c ' /chatboo/canvas/' || true)" 0
  chk "respuestas 4xx/5xx en esas rutas" "$(printf '%s\n' "$R" | sed -n 's/^r|//p' | awk '$NF >= 400' | grep -c . || true)" 0
  echo "-- nivel y logger (WARNING/ERROR/CRITICAL), sin el mensaje"
  printf '%s\n' "$R" | sed -n 's/^w|/   /p'

  echo "== 3. LIYBEN por SQL (sesión de solo lectura; salida completa en $A)"
  RD=$(vps "docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_db sh -c 'psql -U \"\$POSTGRES_USER\" -d LIYBEN -X -q -At -F \"|\"'" 2>&1 <<SQL
\\set ini '$INI'
\\echo '## sesiones'
SELECT count(*), count(*) FILTER (WHERE create_date >= :'ini'::timestamp), coalesce(string_agg(DISTINCT user_id::text, ',') FILTER (WHERE create_date >= :'ini'::timestamp), '-') FROM chatboo_session;
\\echo '## peticiones async'
SELECT count(*), count(*) FILTER (WHERE create_date >= :'ini'::timestamp) FROM chatboo_async_request;
\\echo '## canvas'
SELECT (SELECT count(*) FROM chatboo_canvas_job WHERE create_date >= :'ini'::timestamp), (SELECT count(*) FROM chatboo_canvas_page WHERE create_date >= :'ini'::timestamp);
\\echo '## ai_log'
SELECT count(*), count(*) FILTER (WHERE create_date >= :'ini'::timestamp) FROM ai_log;
\\echo '## escrituras de configuración'
SELECT 'ai_agent', count(*) FROM ai_agent WHERE write_date >= :'ini'::timestamp
UNION ALL SELECT 'ai_agent_provider', count(*) FROM ai_agent_provider WHERE write_date >= :'ini'::timestamp OR create_date >= :'ini'::timestamp
UNION ALL SELECT 'ai_provider', count(*) FROM ai_provider WHERE write_date >= :'ini'::timestamp
UNION ALL SELECT 'ai_provider_role', count(*) FROM ai_provider_role WHERE write_date >= :'ini'::timestamp
UNION ALL SELECT 'ai_skill', count(*) FROM ai_skill WHERE write_date >= :'ini'::timestamp OR create_date >= :'ini'::timestamp
UNION ALL SELECT 'ai_context', count(*) FROM ai_context WHERE write_date >= :'ini'::timestamp OR create_date >= :'ini'::timestamp;
\\echo '## fin'
SQL
)
  printf '%s\n' "$RD" > "$A"
  echo "guardado: $A ($(wc -l < "$A" | tr -d ' ') líneas)"
  FQ=$F
  chk "consultas sin error" "$(printf '%s\n' "$RD" | grep -ciE 'ERROR:|psql: error' || true)" 0
  printf '%s\n' "$RD" | grep -iE 'ERROR:|psql: error' | head -5 | cut -c1-160 | sed 's/^/   /'
  chk "marcador final de la salida SQL" "$(printf '%s\n' "$RD" | grep -cx '## fin' || true)" 1
  [ "$F" = "$FQ" ] || { echo "== $TANDA: $F FALLO(S); las consultas fallaron. No se ha seguido: pega la salida."; exit 1; }
  S=$(sec "$RD" sesiones)
  chk "sesiones de Chatboo nuevas desde U1 (n|usuarios): 1 del usuario 6" "$(printf '%s' "$S" | cut -d'|' -f2,3)" "1|6" info
  echo "   sesiones en total: $(printf '%s' "$S" | cut -d'|' -f1)"
  echo "INFO    peticiones async (total|desde U1): $(sec "$RD" 'peticiones async')"
  chk "trabajos y páginas de Canvas desde U1 (job|page)" "$(sec "$RD" canvas)" "0|0"
  echo "INFO    ai_log (total|desde U1): $(sec "$RD" ai_log)"
  chk "escrituras de configuración desde U1 (agentes, cadena, proveedores, roles, skills, contextos): ninguna" \
      "$(sec "$RD" 'escrituras de configuración' | tr '\n' ' ' | sed 's/ *$//')" \
      "ai_agent|0 ai_agent_provider|0 ai_provider|0 ai_provider_role|0 ai_skill|0 ai_context|0"
  fin "Pega la salida. Después, U0 otra vez (la estructura no debe cambiar)."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
lu_u1
