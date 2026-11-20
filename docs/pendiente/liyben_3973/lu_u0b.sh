lu_u0b() (
  # U0b del uso real en LIYBEN: por qué desaparece la cadena de proveedores de Chatboo entre L6 y U0. Solo lectura,
  # desde el equipo por SSH (en el VPS no escribe nada). Escribe solo en ~/pns_ai_3973/liyben/uso/.
  set -u
  umask 077
  TANDA="LU U0b"
  V=~/pns_ai_3973/liyben/despliegue/vps
  U=~/pns_ai_3973/liyben/uso
  L6T='2026-11-20 10:56:46'
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  sec() { printf '%s\n' "$1" | awk -v s="## $2" '/^## /{p = ($0 == s); next} p'; }
  ver() { echo "-- $2"; sec "$RD" "$1" | sed 's/^/   /'; }
  corte() { [ "$F" = 0 ] || { echo "== $TANDA: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  fin() { if [ "$F" = 0 ]; then echo "== $TANDA: TODO OK.${1:+ $1}"; else echo "== $TANDA: $F FALLO(S). No sigas: pega la salida."; fi; }
  [ -n "${VPS_PORT:-}" ] && [ -n "${VPS_DEST:-}" ] || { echo "Faltan VPS_PORT y VPS_DEST: lánzalas con la línea read de antes"; exit 1; }
  vps() { ssh -T -p "$VPS_PORT" "$VPS_DEST" "$@"; }
  M=$(date +%Y%m%d-%H%M%S)
  O="$U/u0b-$M.txt"; A="$U/u0b_estado-$M.txt"
  [ -d "$U" ] && [ ! -e "$O" ] || { echo "Falta $U (lanza antes U0) o ya existe $O"; exit 1; }
  {
  echo "== $TANDA (equipo → VPS por SSH: la cadena de Chatboo desde L6, $L6T UTC; solo lectura): $(date '+%F %T')"
  U0=$(ls -t "$U"/u0-*.txt 2>/dev/null | head -1)
  chk "última U0 (${U0##*/}) con el FALLO de la cadena" "$(grep -c '^FALLO   cadena, = L6' "$U0" 2>/dev/null || true)" 1
  OFF=$(cat "$V/l5_offset.txt" 2>/dev/null)
  chk "posición del log de L5" "$(printf '%s' "$OFF" | grep -cxE '[0-9]+' || true)" 1
  corte "comprobaciones previas"

  echo "== 1. LIYBEN por SQL (sesión de solo lectura; salida completa en $A)"
  RD=$(vps "docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_db sh -c 'psql -U \"\$POSTGRES_USER\" -d LIYBEN -X -q -At -F \"|\"'" 2>&1 <<SQL
\\set l6 '$L6T'
\\echo '## filas'
SELECT count(*) FROM ai_agent_provider;
\\echo '## secuencia'
SELECT last_value, is_called FROM ai_agent_provider_id_seq;
\\echo '## agentes'
SELECT a.id, a.code, a.active, coalesce(a.origin, ''), a.write_uid, (a.write_date >= :'l6'::timestamp),
       to_char(a.write_date, 'YYYY-MM-DD HH24:MI:SS')
  FROM ai_agent a ORDER BY a.id;
\\echo '## proveedores escritos desde L6'
SELECT id, write_uid, to_char(write_date, 'YYYY-MM-DD HH24:MI:SS') FROM ai_provider WHERE write_date >= :'l6'::timestamp ORDER BY id;
\\echo '## entradas desde L6'
SELECT user_id, count(*), to_char(min(create_date), 'HH24:MI:SS'), to_char(max(create_date), 'HH24:MI:SS')
  FROM res_users_log WHERE create_date >= :'l6'::timestamp GROUP BY 1 ORDER BY 1;
\\echo '## adjuntos desde L6'
SELECT coalesce(res_model, '-'), coalesce(mimetype, '-'), create_uid, count(*) FROM ir_attachment
 WHERE create_date >= :'l6'::timestamp GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;
\\echo '## asistentes desde L6'
SELECT 'ai.import.agents.wizard', count(*) FROM ai_import_agents_wizard WHERE create_date >= :'l6'::timestamp;
\\echo '## fin'
SQL
)
  printf '%s\n' "$RD" > "$A"
  echo "guardado: $A ($(wc -l < "$A" | tr -d ' ') líneas)"
  chk "marcador final de la salida SQL" "$(printf '%s\n' "$RD" | grep -cx '## fin' || true)" 1
  printf '%s\n' "$RD" | grep -iE 'ERROR:|psql: error' | head -5 | cut -c1-160 | sed 's/^/   /'
  ver filas "filas de ai_agent_provider (en L6: 1, la id 2)"
  ver secuencia "secuencia (last_value|is_called): si pasa de 2, se crearon filas después y también se borraron"
  ver agentes "agentes (id|code|activo|origin|write_uid|escrito desde L6|write_date UTC)"
  ver 'proveedores escritos desde L6' "proveedores escritos desde L6 (id|write_uid|write_date UTC)"
  ver 'entradas desde L6' "entradas en Odoo desde L6 (user_id|n|primera|última, UTC)"
  ver 'adjuntos desde L6' "adjuntos creados desde L6 (res_model|mimetype|create_uid|n)"
  ver 'asistentes desde L6' "asistente Import Agents desde L6 (los transitorios se purgan: 0 no descarta)"

  echo "== 2. Log desde el arranque de L5: peticiones a modelos ai.* (hora UTC, ruta sin parámetros, sin IP ni datos)"
  R=$(vps "bash -s -- $OFF" <<'REMOTO' 2>&1
set -u
OFF=$1; L=/opt/odoo/logs/odoo-server.log
[ "$(stat -c %s "$L")" -ge "$OFF" ] || { echo "rotado"; exit 0; }
tail -c +"$((OFF + 1))" "$L" | awk '/ werkzeug: / && match($0, /"(GET|POST) [^ "?]+/) {
  p = substr($0, RSTART + 1, RLENGTH - 1)
  if (p ~ /\/web\/(static|image|content|webclient\/(locale|qweb|translations))|\/longpolling\//) next
  t = $2; sub(/,.*/, "", t)
  if (p ~ /ai\.|ai_|chatboo|mcp|config_backup|backup/) print "a|" t " " p
  else n[p]++
} END { for (k in n) print "n|" n[k] " " k }'
echo "fin|1"
REMOTO
)
  chk "respuesta completa del VPS" "$(printf '%s\n' "$R" | grep -cx 'fin|1' || true)" 1
  echo "-- peticiones a ai.*, chatboo, mcp o copias (en orden)"
  printf '%s\n' "$R" | sed -n 's/^a|/   /p'
  echo "-- resto de peticiones (n ruta), las 25 más frecuentes"
  printf '%s\n' "$R" | sed -n 's/^n|//p' | sort -rn | head -25 | sed 's/^/   /'
  fin "Pega la salida."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
lu_u0b
