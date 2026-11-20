ly_y0r() (
  set -u
  umask 077
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  # completo | reparable (la única frontera es el commit del VPS y la historia de detrás está entera) | otra | incompleta
  clase() {
    [ "$(git -C "$1" rev-parse --is-shallow-repository)" = true ] || { echo completo; return; }
    [ "$(cat "$(git -C "$1" rev-parse --absolute-git-dir)/shallow")" = "$2" ] || { echo otra; return; }
    for p in $(git -C "$1" cat-file -p "$2^{commit}" | sed -n 's/^parent //p'); do
      git -C "$1" rev-list "$p" >/dev/null 2>&1 || { echo incompleta; return; }
    done
    echo reparable
  }
  MODO=${1:-comprobar}
  case "$MODO" in comprobar|REPARAR) ;; *) echo "Uso: ly_y0r [comprobar|REPARAR] (sin argumento: comprobar, que no escribe)"; exit 1 ;; esac
  D=~/pns_ai_3973/liyben
  [ -d "$D" ] || { echo "No existe $D"; exit 1; }
  O="$D/y0r-$MODO-$(date +%Y%m%d-%H%M%S).txt"
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== Y0r ($MODO): clones de Y0c antes o después de RESTAURAR y marca superficial que deja FIJAR. $(date '+%F %T')"
  echo "== 1. Lista y salidas de Y0c"
  FX=$(grep -l '^== Y0c: TODO OK (FIJAR)\.' "$D"/y0c-FIJAR-*.txt 2>/dev/null)
  chk "salidas de FIJAR con TODO OK" "$(printf '%s' "$FX" | grep -c .)" 1
  HF=$(sed -n 's/^fijados: \([0-9]*\); lista para RESTAURAR: .*(SHA-256 \([0-9a-f]\{16\}\))$/\1 \2/p' $FX /dev/null | head -1)
  NRS=$(ls -1 "$D"/fijados-restaurado-*.tsv 2>/dev/null | wc -l | tr -d ' ')
  if [ -e "$D/fijados.tsv" ]; then
    FASE=antes; LISTA="$D/fijados.tsv"
    chk "ninguna lista ya restaurada" "$NRS" 0
  else
    FASE=despues; LISTA=$(ls -1 "$D"/fijados-restaurado-*.tsv 2>/dev/null | tail -1)
    chk "una lista restaurada (no hay fijados.tsv)" "$NRS" 1
    chk "salidas de RESTAURAR con TODO OK" "$(grep -l '^== Y0c: TODO OK (todos restaurados' "$D"/y0c-RESTAURAR-*.txt 2>/dev/null | wc -l | tr -d ' ')" 1
  fi
  [ -n "${LISTA:-}" ] && [ -f "$LISTA" ] || { echo "FALLO   no hay lista de fijados"; echo "== Y0r: FALLO. No se ha tocado nada."; exit 1; }
  echo "fase: $FASE RESTAURAR; lista: $LISTA"
  chk "lista: repos y SHA-256 = los de la salida de FIJAR" "$(wc -l < "$LISTA" | tr -d ' ') $(sha256sum "$LISTA" | cut -c1-16)" "$HF"
  [ "$MODO" = comprobar ] || chk "REPARAR solo después de RESTAURAR" "$FASE" despues

  echo "== 2. Contenedores de odoo-dev-14"
  chk "docker responde" "$(docker ps -q >/dev/null 2>&1 && echo si || echo no)" si
  SV=$(docker ps --filter label=com.docker.compose.project=odoo-dev-14 --format '{{.Label "com.docker.compose.service"}}' 2>/dev/null | sort | tr '\n' ' ' | sed 's/ $//')
  echo "en marcha: ${SV:-ninguno}"
  chk "nada de odoo-dev-14 en marcha salvo PostgreSQL (db)" "$(printf '%s\n' $SV | grep -cvx -e db -e '')" 0
  [ "$MODO" = comprobar ] || [ "$F" = 0 ] || { echo "== Y0r: $F FALLO(S). No se ha tocado nada."; exit 1; }

  echo "== 3. Clones de la lista"
  NC=0; NR=0; NO=0; NI=0; REP=""; OTR=""; AREP=""
  while IFS='|' read -r l rama antes vps; do
    [ -n "$l" ] || continue
    n=${l#"$HOME"/}
    git -C "$l" rev-parse --git-dir >/dev/null 2>&1 || { echo "FALLO   $n: no es un repo git"; F=$((F + 1)); continue; }
    F0=$F
    ahora=$(git -C "$l" rev-parse HEAD); rl=$(git -C "$l" rev-parse --abbrev-ref HEAD)
    su=$(git -C "$l" status --porcelain | wc -l | tr -d ' ')
    if [ "$FASE" = antes ]; then
      ref=$(git -C "$l" rev-parse -q --verify "refs/heads/$rama" || echo -)
      chk "$n: suelto en ${vps:0:7} (VPS), limpio; $rama sigue en ${antes:0:7}" "$ahora $rl $su $ref" "$vps HEAD 0 $antes"
    else
      chk "$n: en $rama ${antes:0:7} y limpio" "$ahora $rl $su" "$antes $rama 0"
    fi
    c=$(clase "$l" "$vps")
    case "$c" in
      completo) NC=$((NC + 1)) ;;
      reparable) NR=$((NR + 1)); REP="$REP $n" ;;
      otra) NO=$((NO + 1)); OTR="$OTR $n(otra frontera)" ;;
      incompleta) NI=$((NI + 1)); OTR="$OTR $n(historia incompleta)" ;;
    esac
    [ "$c" != reparable ] || [ "$F" != "$F0" ] || AREP="$AREP$l|$rama
"
  done < "$LISTA"
  echo "-- marca superficial (antes de este modo): completos $NC; con la marca de FIJAR y reparables sin red $NR; superficiales por otra causa $NO; con historia incompleta $NI"
  [ -z "$REP" ] || echo "   reparables:$REP"
  [ -z "$OTR" ] || echo "   no se tocan:$OTR"
  if [ "$MODO" = REPARAR ]; then
    echo "== 4. Quitar la marca superficial de FIJAR"
    [ "$F" = 0 ] || { echo "== Y0r: $F FALLO(S). No se ha tocado nada."; exit 1; }
    while IFS='|' read -r l rama; do
      [ -n "$l" ] || continue
      n=${l#"$HOME"/}
      SF="$(git -C "$l" rev-parse --absolute-git-dir)/shallow"
      B="$D/shallow_bak/$(echo "$n" | tr '/' '_')"
      mkdir -p "$D/shallow_bak"
      if [ -e "$B" ]; then echo "FALLO   $n: ya existe la copia $B; no se toca"; F=$((F + 1)); continue; fi
      cp -p -- "$SF" "$B"
      echo "-- [ALTERA $n] quita la marca superficial de FIJAR (copia: $B)"
      rm -- "$SF"
      if [ "$(git -C "$l" rev-parse --is-shallow-repository)" = false ] && git -C "$l" rev-list HEAD >/dev/null 2>&1; then
        echo "OK      $n: completo ($(git -C "$l" rev-list --count HEAD) commits en $rama)"
      else
        cp -p -- "$B" "$SF"; echo "FALLO   $n: la historia no queda entera; marca repuesta desde la copia"; F=$((F + 1))
      fi
    done <<< "$AREP"
  fi
  if [ "$F" = 0 ]; then echo "== Y0r: TODO OK ($MODO, fase $FASE RESTAURAR)"; else echo "== Y0r: $F FALLO(S). Pega la salida."; fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ly_y0r "$@"
