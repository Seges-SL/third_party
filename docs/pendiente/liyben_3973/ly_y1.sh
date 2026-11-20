ly_y1() (
  set -u
  umask 077
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  [ -n "${VPS_PORT:-}" ] && [ -n "${VPS_DEST:-}" ] || { echo "Faltan VPS_PORT y VPS_DEST: lánzalas con la línea read de antes"; exit 1; }
  D=~/pns_ai_3973/liyben
  DB_LOCAL=odoo-dev-14-db-1
  [ -d "$D" ] || { echo "No existe $D"; exit 1; }
  M=$(date +%Y%m%d-%H%M%S)
  O="$D/y1-$M.txt"
  A="$D/LIYBEN-$M.dump"
  [ ! -e "$O" ] && [ ! -e "$A" ] && [ ! -e "$A.parcial" ] || { echo "Ya existe $O o $A: vuelve a lanzarla dentro de un segundo"; exit 1; }
  T=$(mktemp) || exit 1
  trap 'rm -f -- "$T"' EXIT
  {
  echo "== Y1 (copia de LIYBEN para el ensayo; ALTERA solo $D): $(date '+%F %T')"
  echo "== 1. Comprobaciones previas"
  chk "permisos de $D" "$(stat -c %a "$D")" 700
  chk "espacio libre en el equipo (al menos 2 GB)" "$( [ "$(df --output=avail -B1 "$D" | tail -1 | tr -d ' ')" -ge 2000000000 ] && echo si || echo no)" si
  chk "PostgreSQL local ($DB_LOCAL) en marcha" "$(docker ps --format '{{.Names}}' | grep -cx "$DB_LOCAL")" 1
  [ "$F" = 0 ] || { echo "== Y1: $F FALLO(S). No se ha copiado nada."; exit 1; }

  echo "== 2. [ALTERA solo $D] pg_dump -Fc de LIYBEN por SSH, sin filestore (D53), lanzado a las $(date +%H:%M:%S); en el VPS no se escribe nada"
  ssh -T -p "$VPS_PORT" "$VPS_DEST" "docker exec -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_db sh -c 'pg_dump -U \"\$POSTGRES_USER\" -Fc LIYBEN'" > "$A.parcial"
  RC=$?
  echo "terminado a las $(date +%H:%M:%S)"
  chk "salida de pg_dump por SSH" "$RC" 0
  B=$(stat -c %s "$A.parcial")
  echo "tamaño: $B bytes"
  chk "tamaño razonable (más de 30 MB; la del 16/10 tenía 48 MB)" "$( [ "$B" -gt 30000000 ] && echo si || echo no)" si
  if [ "$F" != 0 ]; then rm -f -- "$A.parcial"; echo "== Y1: $F FALLO(S). Copia incompleta borrada; no sigas: pega la salida."; exit 1; fi
  mv -- "$A.parcial" "$A"
  chk "permisos de la copia" "$(stat -c %a "$A")" 600
  echo "SHA-256: $(sha256sum "$A" | cut -d' ' -f1)"

  echo "== 3. Lectura de la copia con pg_restore -l (en $DB_LOCAL, solo lee la entrada)"
  docker exec -i "$DB_LOCAL" pg_restore -l < "$A" > "$T" 2>&1
  chk "pg_restore -l" "$?" 0
  chk "BD de origen" "$(sed -n 's/^;[[:space:]]*dbname: //p' "$T" | head -1)" LIYBEN
  echo "versión de origen: $(sed -n 's/^;[[:space:]]*Dumped from database version: //p' "$T" | head -1)"
  chk "datos de ai_provider en la copia" "$(grep -cE 'TABLE DATA public ai_provider ' "$T")" 1
  chk "datos de res_partner en la copia" "$(grep -cE 'TABLE DATA public res_partner ' "$T")" 1
  echo "entradas TABLE DATA: $(grep -c 'TABLE DATA' "$T")"
  if [ "$F" = 0 ]; then echo "== Y1: TODO OK (copia: $A)"; else echo "== Y1: $F FALLO(S). No sigas: pega la salida."; fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ly_y1
