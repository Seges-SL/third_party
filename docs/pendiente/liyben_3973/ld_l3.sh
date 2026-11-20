ld_l3() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD L3"
  DB_LOCAL=odoo-dev-14-db-1
  [ -n "${VPS_PORT:-}" ] && [ -n "${VPS_DEST:-}" ] || { echo "Faltan VPS_PORT y VPS_DEST: lánzalas con la línea read de antes"; exit 1; }
  vps() { ssh -T -p "$VPS_PORT" "$VPS_DEST" "$@"; }
  O=$(nueva "$DE/l3" .txt) || exit 1
  M=$(date +%Y%m%d-%H%M%S)
  A="$DE/LIYBEN-antes-$M.dump"
  B="$DE/LIYBEN-filestore-antes-$M.tar"
  [ ! -e "$A" ] && [ ! -e "$B" ] && [ ! -e "$A.parcial" ] && [ ! -e "$B.parcial" ] || { echo "Ya existe la copia: vuelve a lanzarla dentro de un segundo"; exit 1; }
  T=$(mktemp) || exit 1
  trap 'rm -f -- "$T"' EXIT
  {
  echo "== $TANDA (equipo: copia de LIYBEN, BD y filestore, por SSH; D57). En el VPS solo escribe la marca $LD/copia_ok: $(date '+%F %T')"
  echo "== 1. Comprobaciones previas"
  chk "permisos de $DE" "$(stat -c %a "$DE")" 700
  chk "espacio libre en el equipo (al menos 3 GB)" "$( [ "$(df --output=avail -B1 "$DE" | tail -1 | tr -d ' ')" -ge 3000000000 ] && echo si || echo no)" si
  chk "PostgreSQL local ($DB_LOCAL) en marcha, para pg_restore -l (si no: odoo-dev 14 bd-lista)" "$(docker ps --format '{{.Names}}' | grep -cx "$DB_LOCAL" || true)" 1
  R=$(vps "cd $COMPOSE && docker compose ps --status running --services | grep -cx web; grep -cx '== LD L2: TODO OK. Corte: web PARADO. Sigue con L3 en el equipo.' \$(ls -t $LD/l2-*.txt | head -1); test -e $LD/copia_ok && echo hay || echo no; find $FS -type f | wc -l; du -sb $FS | cut -f1" 2>&1)
  chk "en el VPS: web parado | última L2 con TODO OK | sin marca anterior" "$(printf '%s\n' "$R" | sed -n 1,3p | una)" "0 1 no"
  NFS=$(printf '%s\n' "$R" | sed -n 4p); BFS=$(printf '%s\n' "$R" | sed -n 5p)
  echo "filestore en el VPS: $NFS archivos, $BFS bytes"
  corte "comprobaciones previas"

  echo "== 2. [ALTERA solo $DE] pg_dump -Fc de LIYBEN por SSH, lanzado a las $(date +%H:%M:%S)"
  vps "docker exec -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_db sh -c 'pg_dump -U \"\$POSTGRES_USER\" -Fc LIYBEN'" > "$A.parcial"
  RC=$?
  chk "salida de pg_dump por SSH" "$RC" 0
  S=$(stat -c %s "$A.parcial"); echo "tamaño: $S bytes (ensayo, Y1: 49 307 121)"
  chk "tamaño razonable (más de 30 MB)" "$( [ "$S" -gt 30000000 ] && echo si || echo no)" si
  if [ "$F" != 0 ]; then rm -f -- "$A.parcial"; echo "== $TANDA: $F FALLO(S). Copia incompleta borrada; no sigas: pega la salida."; exit 1; fi
  mv -- "$A.parcial" "$A"
  docker exec -i "$DB_LOCAL" pg_restore -l < "$A" > "$T" 2>&1
  chk "pg_restore -l" "$?" 0
  chk "BD de origen" "$(sed -n 's/^;[[:space:]]*dbname: //p' "$T" | head -1)" LIYBEN
  chk "datos de ai_provider y res_partner en la copia" "$(grep -cE 'TABLE DATA public (ai_provider|res_partner) ' "$T")" 2
  echo "entradas TABLE DATA: $(grep -c 'TABLE DATA' "$T") (ensayo: 832)"

  echo "== 3. [ALTERA solo $DE] filestore por SSH (tar sin comprimir), lanzado a las $(date +%H:%M:%S)"
  vps "tar -C $(dirname "$FS") -cf - LIYBEN" > "$B.parcial"
  RC=$?
  chk "salida de tar por SSH" "$RC" 0
  NT=$(tar -tf "$B.parcial" 2>/dev/null | grep -vc '/$' || true)
  chk "archivos en la copia = en el VPS" "$NT" "$NFS"
  echo "tamaño: $(stat -c %s "$B.parcial") bytes"
  if [ "$F" != 0 ]; then rm -f -- "$B.parcial"; echo "== $TANDA: $F FALLO(S). Copia del filestore borrada; no sigas: pega la salida."; exit 1; fi
  mv -- "$B.parcial" "$B"
  chk "permisos de las dos copias" "$(stat -c %a "$A") $(stat -c %a "$B")" "600 600"
  HA=$(sha256sum "$A" | cut -d' ' -f1); HB=$(sha256sum "$B" | cut -d' ' -f1)
  echo "SHA-256: ${A##*/} $HA"
  echo "SHA-256: ${B##*/} $HB"
  corte "copias"

  echo "== 4. [ALTERA el VPS: solo $LD/copia_ok] marca de copia hecha"
  vps "umask 077; printf '%s\n' '${A##*/} $HA' '${B##*/} $HB $NFS' > $LD/copia_ok"
  chk "marca escrita en el VPS (líneas)" "$(vps "wc -l < $LD/copia_ok" 2>&1)" 2
  fin "Sigue con L4 en el VPS."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_l3
