ly_y0c() (
  set -u
  umask 077
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  MODO=${1:-comprobar}
  case "$MODO" in comprobar|FIJAR|RESTAURAR) ;; *) echo "Uso: ly_y0c [comprobar|FIJAR|RESTAURAR] (sin argumento: comprobar, que no escribe)"; exit 1 ;; esac
  D=~/pns_ai_3973/liyben
  V=~/odoo-dev/14.0
  LISTA="$D/fijados.tsv"
  [ -d "$D" ] || { echo "No existe $D"; exit 1; }
  O="$D/y0c-$MODO-$(date +%Y%m%d-%H%M%S).txt"
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== Y0c ($MODO): clones de ~/odoo-dev/14.0 en los commits del VPS para el ensayo (decisión N). $(date '+%F %T')"

  if [ "$MODO" = RESTAURAR ]; then
    echo "== 1. Comprobaciones previas"
    chk "existe la lista de fijados" "$(test -f "$LISTA" && echo si || echo no)" si
    [ "$F" = 0 ] || { echo "== Y0c: $F FALLO(S). No se ha tocado nada."; exit 1; }
    echo "lista: $LISTA ($(wc -l < "$LISTA" | tr -d ' ') repos; SHA-256 $(sha256sum "$LISTA" | cut -c1-16))"
    while IFS='|' read -r l rama antes vps; do
      ahora=$(git -C "$l" rev-parse HEAD 2>/dev/null)
      if [ "$ahora" = "$antes" ] && [ "$(git -C "$l" rev-parse --abbrev-ref HEAD)" = "$rama" ]; then echo "OK      $l ya estaba en $rama ${antes:0:7}"; continue; fi
      if [ "$ahora" != "$vps" ]; then echo "FALLO   $l: está en ${ahora:0:7}, ni en el commit fijado ni en el de antes; no se toca"; F=$((F + 1)); continue; fi
      if [ "$(git -C "$l" status --porcelain | wc -l | tr -d ' ')" != 0 ]; then echo "FALLO   $l: tiene cambios sin commit; no se toca"; F=$((F + 1)); continue; fi
      echo "-- [ALTERA $l] checkout de $rama"
      git -C "$l" checkout -q "$rama" 2>&1 | sed 's/^/   /'
      chk "$l en $rama ${antes:0:7}" "$(git -C "$l" rev-parse --abbrev-ref HEAD) $(git -C "$l" rev-parse HEAD)" "$rama $antes"
    done < "$LISTA"
    if [ "$F" = 0 ]; then
      mv -- "$LISTA" "$D/fijados-restaurado-$(date +%Y%m%d-%H%M%S).tsv"
      echo "== Y0c: TODO OK (todos restaurados; la lista se ha renombrado)"
    else echo "== Y0c: $F FALLO(S). La lista se conserva: pega la salida."; fi
    exit 0
  fi

  [ -n "${VPS_PORT:-}" ] && [ -n "${VPS_DEST:-}" ] || { echo "Faltan VPS_PORT y VPS_DEST: lánzalas con la línea read de antes"; exit 1; }
  echo "== 1. Commits del VPS (solo lectura)"
  R=$(ssh -T -p "$VPS_PORT" "$VPS_DEST" 'bash -s' 2>&1 <<'REMOTO'
AP=$(docker exec odoo14_server cat /etc/odoo/odoo.conf | sed -n 's/^[[:space:]]*addons_path[[:space:]]*=[[:space:]]*//p' | head -1)
IFS=, read -r -a ENTRADAS <<< "$AP"
for e in "${ENTRADAS[@]}"; do
  e=$(echo "$e" | tr -d ' ')
  case "$e" in
    /mnt/extra-addons/OCA/*|/mnt/extra-addons/custom/LIYBEN|/mnt/extra-addons/custom/vertical-instaladores) h="/opt/odoo/addons/${e#/mnt/extra-addons/}" ;;
    *) continue ;;
  esac
  echo "REPO|${e#/mnt/extra-addons/}|$(git --no-optional-locks -c safe.directory="$h" -C "$h" rev-parse HEAD 2>/dev/null || echo -)"
done
echo "FIN|"
REMOTO
)
  chk "respuesta completa del VPS" "$(printf '%s\n' "$R" | grep -c '^FIN|')" 1
  [ "$F" = 0 ] || { printf '%s\n' "$R" | head -20; echo "== Y0c: $F FALLO(S). No se ha tocado nada."; exit 1; }
  echo "repos: $(printf '%s\n' "$R" | grep -c '^REPO|')"

  echo "== 2. Clones del equipo"
  P=""
  while IFS='|' read -r _ rel vps; do
    case "$rel" in
      OCA/*) l="$V/oca/${rel#OCA/}" ;;
      custom/vertical-instaladores)
        case "$(git -C ~/GitHub/vertical-instaladores rev-parse --abbrev-ref HEAD 2>/dev/null)" in
          14.0*) echo "FALLO   tu copia de ~/GitHub/vertical-instaladores está en una rama 14.0*: el kit la montaría y esta tanda no toca tus repos"; F=$((F + 1)); continue ;;
        esac
        l="$V/vertical-instaladores" ;;
      custom/LIYBEN)
        chk "custom/LIYBEN: tu copia = VPS (no se toca)" "$(git -C ~/GitHub/LIYBEN rev-parse HEAD 2>/dev/null) $(git -C ~/GitHub/LIYBEN status --porcelain 2>/dev/null | wc -l | tr -d ' ')" "$vps 0"
        continue ;;
    esac
    [ "$vps" != - ] || { echo "INFO    $rel: el VPS no da su commit; se queda como está"; continue; }
    git -C "$l" rev-parse --git-dir >/dev/null 2>&1 || { echo "FALLO   $rel: no existe $l"; F=$((F + 1)); continue; }
    ahora=$(git -C "$l" rev-parse HEAD)
    [ "$ahora" != "$vps" ] || continue
    rama=$(git -C "$l" rev-parse --abbrev-ref HEAD)
    [ "$rama" != HEAD ] || { echo "FALLO   $rel: $l no está en una rama (¿ya fijado sin lista?)"; F=$((F + 1)); continue; }
    [ "$(git -C "$l" status --porcelain | wc -l | tr -d ' ')" = 0 ] || { echo "FALLO   $rel: $l tiene cambios sin commit"; F=$((F + 1)); continue; }
    echo "a fijar: $rel  $rama ${ahora:0:7} -> ${vps:0:7}"
    P="$P$l|$rama|$ahora|$vps
"
  done < <(printf '%s\n' "$R" | grep '^REPO|')
  N=$(printf '%s' "$P" | grep -c . || true)
  echo "repos a fijar: $N"
  if [ "$MODO" = comprobar ]; then
    if [ "$F" = 0 ]; then echo "== Y0c: TODO OK (comprobar: no se ha tocado nada)"; else echo "== Y0c: $F FALLO(S). No sigas: pega la salida."; fi
    exit 0
  fi

  chk "no hay una lista de fijados anterior" "$(test -e "$LISTA" && echo existe || echo no)" no
  [ "$F" = 0 ] || { echo "== Y0c: $F FALLO(S). No se ha tocado nada (si hay lista, primero RESTAURAR)."; exit 1; }
  echo "== 3. [ALTERA los clones de $V] fetch del commit del VPS y checkout --detach"
  [ "$F" = 0 ] || { echo "== Y0c: $F FALLO(S). No se ha tocado nada (si hay lista, primero RESTAURAR)."; exit 1; }
  : > "$LISTA"
  FIJ=0
  while IFS='|' read -r l rama antes vps; do
    [ -n "$l" ] || continue
    if ! git -C "$l" fetch -q --depth 1 origin "$vps" 2>/dev/null; then
      echo "INFO    $l: no se pudo traer ${vps:0:7} de su remoto; se queda en $rama ${antes:0:7}"; continue
    fi
    echo "$l|$rama|$antes|$vps" >> "$LISTA"
    git -C "$l" checkout -q --detach "$vps" 2>&1 | sed 's/^/   /'
    chk "$l en ${vps:0:7}" "$(git -C "$l" rev-parse HEAD)" "$vps"
    FIJ=$((FIJ + 1))
  done <<< "$P"
  echo "fijados: $FIJ; lista para RESTAURAR: $LISTA (SHA-256 $(sha256sum "$LISTA" | cut -c1-16))"
  if [ "$F" = 0 ]; then echo "== Y0c: TODO OK (FIJAR). No ejecutes 'odoo-dev 14 actualizar-codigo' hasta RESTAURAR."; else echo "== Y0c: $F FALLO(S). Pega la salida; RESTAURAR deshace lo fijado."; fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ly_y0c "$@"
