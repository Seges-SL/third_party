ld_l2() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD L2"
  [ "$(cd "$(dirname "$0")" && pwd)" = "$LD" ] || { echo "Lánzala desde $LD: bash $LD/ld_l2.sh"; exit 1; }
  sudo -v || { echo "FALLO   sudo. No se ha seguido."; exit 1; }
  O=$(nueva "$LD/l2" .txt) || exit 1
  T=$(mktemp -d "$LD/l2_arbol.XXXXXX") || exit 1
  trap 'rm -rf -- "$T"' EXIT
  {
  echo "== $TANDA (VPS: trae la rama al clon y para el web): $(date -u '+%F %T') UTC"
  echo "== 1. Comprobaciones previas (solo lectura)"
  L0=$(ultima "$LD/l0-*.txt")
  chk "última L0 (${L0##*/}) con TODO OK" "$(marca "$L0" '== LD L0: TODO OK. Corte: pega la salida. Después L1 (interfaz) y L2, antes de una hora.')" 1
  chk "L0 de hace menos de una hora (si no, repite L0)" "$( [ -n "$L0" ] && [ $(( $(date +%s) - $(stat -c %Y "$L0") )) -lt 3600 ] && echo si || echo no)" si
  C=$(cat "$LD/commit.txt" 2>/dev/null)
  chk "huellas de $LD" "$(cd "$LD" && sha256sum -c --quiet huellas.txt 2>&1 | wc -l | tr -d ' ')" 0
  chk "web en marcha" "$(web)" 1
  chk "rama del clon" "$(g rev-parse --abbrev-ref HEAD 2>&1)" "$RAMA_ANTES"
  chk "HEAD del clon" "$(g rev-parse --short=7 HEAD 2>&1)" "$COMMIT_ANTES"
  chk "clon limpio (líneas de status)" "$(g status --porcelain 2>&1 | wc -l | tr -d ' ')" 0
  chk "la rama $RAMA no existe aún en el clon (local)" "$(g rev-parse -q --verify "refs/heads/$RAMA" >/dev/null && echo existe || echo no)" no
  corte "comprobaciones previas"

  echo "== 2. [ALTERA el clon: solo referencias] fetch de $RAMA como el UID 101, con refspec explícito (§3.2)"
  g101 fetch origin "+refs/heads/$RAMA:refs/remotes/origin/$RAMA" 2>&1 | sed 's/^/   /'
  chk "origin/$RAMA = commit del documento" "$(g rev-parse -q --verify "refs/remotes/origin/$RAMA" 2>&1)" "$C"
  chk "$COMMIT_ANTES es antecesor del commit" "$(g merge-base --is-ancestor "$COMMIT_ANTES" "$C" 2>/dev/null && echo si || echo no)" si
  chk "rama, HEAD y status del clon, sin cambios" "$(g rev-parse --abbrev-ref HEAD)|$(g rev-parse --short=7 HEAD)|$(g status --porcelain | wc -l | tr -d ' ')" "$RAMA_ANTES|$COMMIT_ANTES|0"
  chk "propietario de .git/ (archivos que no son del UID 101)" "$(find "$CLON/.git" ! -uid 101 2>/dev/null | wc -l | tr -d ' ')" 0
  g archive "$C" pns_base pns_ai_mcp pns_ai_chatboo | tar -x -C "$T" || echo "FALLO   git archive del commit"
  chk "árbol de los módulos del commit (archivos y huella)" "$(arbol "$T" | una)" "$ARBOL_RAMA"
  corte "fetch"

  echo "== 3. [ALTERA: corte del servicio] docker compose stop web, a las $(date -u +%T) UTC"
  ( cd "$COMPOSE" && docker compose stop web ) 2>&1 | sed 's/^/   /'
  chk "web parado" "$(web)" 0
  chk "odoo14_db en marcha" "$(docker ps --format '{{.Names}}' | grep -cx odoo14_db || true)" 1
  chk "liyben.com/web/login (502 o 503: Nginx sin Odoo)" "$(curl -sS -o /dev/null -w '%{http_code}' https://liyben.com/web/login 2>/dev/null | grep -cE '^50[234]$' || true)" 1 info
  fin "Corte: web PARADO. Sigue con L3 en el equipo."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_l2
