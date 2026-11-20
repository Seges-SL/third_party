ly_y0() (
  set -u
  umask 077
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  oculta() { sed -E 's/((password|passwd|secret|token|api_key|apikey)[^=: ]*[=: ]+)[^ "]+/\1***/Ig'; }
  [ -n "${VPS_PORT:-}" ] && [ -n "${VPS_DEST:-}" ] || { echo "Faltan VPS_PORT y VPS_DEST: lánzalas con la línea read de antes"; exit 1; }
  D=~/pns_ai_3973/liyben
  OCA=~/odoo-dev/14.0/oca
  KIT=~/GitHub/claude-odoo-kit/entorno/Dockerfile.14
  [ -d "$D" ] || { echo "No existe $D"; exit 1; }
  O="$D/y0-$(date +%Y%m%d-%H%M%S).txt"
  DV="$D/Dockerfile.vps"
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== Y0 (solo lectura en el VPS; en el equipo escribe solo $O y $DV): $(date '+%F %T')"
  echo "== 1. Repos del addons_path de LIYBEN en el VPS (git sin escribir)"
  R=$(ssh -T -p "$VPS_PORT" "$VPS_DEST" 'bash -s' 2>&1 <<'REMOTO'
AP=$(docker exec odoo14_server cat /etc/odoo/odoo.conf | sed -n 's/^[[:space:]]*addons_path[[:space:]]*=[[:space:]]*//p' | head -1)
echo "AP|$AP"
IFS=, read -r -a ENTRADAS <<< "$AP"
for e in "${ENTRADAS[@]}"; do
  e=$(echo "$e" | tr -d ' ')
  case "$e" in
    /usr/lib/python3/dist-packages/odoo/addons|/mnt/core-addons|/mnt/extra-addons/custom|/mnt/extra-addons/custom/third_party) continue ;;
    /mnt/extra-addons/*) h="/opt/odoo/addons/${e#/mnt/extra-addons/}" ;;
    *) echo "RARO|$e"; continue ;;
  esac
  g() { git --no-optional-locks -c safe.directory="$h" -C "$h" "$@"; }
  if [ ! -d "$h" ]; then echo "REPO|${e#/mnt/extra-addons/}|-|-|-|nodir"
  elif g rev-parse --git-dir >/dev/null 2>&1; then
    echo "REPO|${e#/mnt/extra-addons/}|$(g rev-parse --abbrev-ref HEAD)|$(g rev-parse HEAD)|$(g status --porcelain 2>/dev/null | wc -l)|git"
  else echo "REPO|${e#/mnt/extra-addons/}|-|-|-|nogit"; fi
done
if [ -r /opt/odoo/Dockerfile ]; then echo "DF|$(sha256sum /opt/odoo/Dockerfile | cut -d' ' -f1)|$(wc -l < /opt/odoo/Dockerfile)"; else echo "DF|no|0"; fi
echo "FIN|"
REMOTO
)
  chk "respuesta completa del VPS" "$(printf '%s\n' "$R" | grep -c '^FIN|')" 1
  [ "$F" = 0 ] || { printf '%s\n' "$R" | head -20; echo "== Y0: $F FALLO(S). No sigas: pega la salida."; exit 1; }
  printf '%s\n' "$R" | grep '^RARO|' | sed 's/^RARO|/INFO    entrada del addons_path sin tratar: /'
  NREPO=$(printf '%s\n' "$R" | grep -c '^REPO|' || true)
  echo "repos en el VPS (sin el core ni third_party): $NREPO"
  IG=0; DI=0; FA=0
  while IFS='|' read -r _ rel vrama vhead vsucio vtipo; do
    case "$rel" in
      OCA/*) l="$OCA/${rel#OCA/}" ;;
      custom/*) l="$HOME/GitHub/${rel#custom/}" ;;
      *) l="" ;;
    esac
    if [ "$vtipo" != git ]; then echo "INFO    $rel en el VPS: $vtipo (no se compara)"; continue; fi
    [ "$vsucio" = 0 ] || echo "INFO    $rel en el VPS con $vsucio cambio(s) sin commit"
    if [ -z "$l" ] || ! git -C "$l" rev-parse --git-dir >/dev/null 2>&1; then
      echo "FALLO   $rel: no está en el equipo (${l:-sin ruta}); sus módulos saldrían SIN CÓDIGO"; F=$((F + 1)); FA=$((FA + 1)); continue
    fi
    lrama=$(git -C "$l" rev-parse --abbrev-ref HEAD); lhead=$(git -C "$l" rev-parse HEAD)
    case "$rel" in custom/*)
      case "$lrama" in 14.0*) ;; *) echo "FALLO   $rel: tu copia está en la rama $lrama (el kit solo la monta en una rama 14.0*)"; F=$((F + 1)) ;; esac
      ls=$(git -C "$l" status --porcelain | wc -l | tr -d ' ')
      [ "$ls" = 0 ] || { echo "FALLO   $rel: tu copia tiene $ls cambio(s) sin commit (el kit monta la copia de trabajo)"; F=$((F + 1)); }
    esac
    if [ "$lhead" = "$vhead" ]; then IG=$((IG + 1))
    else
      DI=$((DI + 1))
      if ! git -C "$l" cat-file -e "$vhead^{commit}" 2>/dev/null; then rel2="el commit del VPS no está en el equipo"
      elif git -C "$l" merge-base --is-ancestor "$vhead" "$lhead"; then rel2="el equipo va por delante ($(git -C "$l" rev-list --count "$vhead..$lhead") commits)"
      elif git -C "$l" merge-base --is-ancestor "$lhead" "$vhead"; then rel2="el equipo va por detrás ($(git -C "$l" rev-list --count "$lhead..$vhead") commits)"
      else rel2="divergen"; fi
      echo "INFO    $rel: VPS ${vhead:0:7} ($vrama), equipo ${lhead:0:7} ($lrama): $rel2"
    fi
  done < <(printf '%s\n' "$R" | grep '^REPO|')
  echo "resumen: iguales $IG, distintos $DI, que faltan en el equipo $FA"
  EXTRA=$(cd "$OCA" 2>/dev/null && for d in */; do r=${d%/}; printf '%s\n' "$R" | grep -q "^REPO|OCA/$r|" || echo "$r"; done | tr '\n' ' ')
  echo "OCA del equipo que el VPS no usa (se montan, sin efecto si no están instalados): ${EXTRA:-ninguno}"

  echo "== 2. Dockerfile del VPS frente al del kit"
  DFL=$(printf '%s\n' "$R" | grep '^DF|' | head -1)
  if [ "$(echo "$DFL" | cut -d'|' -f2)" = no ]; then
    echo "INFO    /opt/odoo/Dockerfile no existe o no se puede leer en el VPS"
  else
    ssh -T -p "$VPS_PORT" "$VPS_DEST" 'cat /opt/odoo/Dockerfile' > "$DV" 2>/dev/null
    chk "copia local del Dockerfile del VPS (huella igual a la del VPS)" "$(sha256sum "$DV" | cut -d' ' -f1)" "$(echo "$DFL" | cut -d'|' -f2)"
    [ -r "$KIT" ] || { echo "FALLO   no se lee $KIT"; F=$((F + 1)); }
    if [ -r "$KIT" ]; then
      chk "Dockerfile del VPS = Dockerfile.14 del kit" "$(cmp -s "$DV" "$KIT" && echo igual || echo distinto)" igual info
      cmp -s "$DV" "$KIT" || { echo "-- diferencias (VPS = +, kit = -; posibles secretos ocultos)"; diff -u "$KIT" "$DV" | sed 1,2d | grep -E '^[-+]' | oculta | head -60 | sed 's/^/   /'; }
    fi
  fi
  if [ "$F" = 0 ]; then echo "== Y0: TODO OK"; else echo "== Y0: $F FALLO(S). No sigas: pega la salida."; fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ly_y0
