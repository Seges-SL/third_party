ly_e0() (
  set -u
  umask 077
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  arbol() {
    ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l ) | tr -d ' '
    ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 \
        | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1 )
  }
  REPO=~/GitHub/third_party
  DEST=~/pns_ai_3973/liyben
  LIYBEN_HOY=578859b
  STAGING=5d0559b
  ARBOL_STAGING="688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
  CUAL=${1:-HEAD}
  [ -d "$DEST" ] || { echo "No existe $DEST"; exit 1; }
  O="$DEST/e0-$(date +%Y%m%d-%H%M%S).txt"
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  T=$(mktemp -d /tmp/ly_e0.XXXXXX) || exit 1
  trap 'rm -rf -- "$T"' EXIT
  {
  cd "$REPO" || exit 1
  echo "== E0 (equipo, solo lectura del repo; extracción temporal en $T, se borra al acabar): $(date '+%F %T')"
  echo "== 1. Repo y commits"
  chk "rama" "$(git rev-parse --abbrev-ref HEAD)" 14.0-pns-ai-3973
  chk "árbol de trabajo limpio" "$(git status --porcelain | wc -l | tr -d ' ')" 0
  chk "al día con su rama remota (delante|detrás)" "$(git rev-list --left-right --count 'HEAD...@{u}' 2>&1 | tr '\t' '|')" "0|0"
  C=$(git rev-parse -q --verify "$CUAL^{commit}") || { echo "FALLO   no existe el commit $CUAL"; exit 1; }
  echo "commit a comprobar: $(git log -1 --format='%h %s' "$C")"
  chk "existe $LIYBEN_HOY (LIYBEN hoy)" "$(git cat-file -t "$LIYBEN_HOY" 2>/dev/null)" commit
  chk "existe $STAGING (staging)" "$(git cat-file -t "$STAGING" 2>/dev/null)" commit
  chk "existe origin/14.0" "$(git rev-parse -q --verify origin/14.0 >/dev/null && echo si || echo no)" si
  echo "origin/14.0 (copia local de la remota): $(git log -1 --format='%h %ci' origin/14.0 2>/dev/null)"
  [ "$F" = 0 ] || { echo "== E0: $F FALLO(S). No sigas: pega la salida."; exit 1; }

  echo "== 2. Módulos del commit frente a $STAGING (lo validado en el staging)"
  chk "$STAGING es antecesor del commit" "$(git merge-base --is-ancestor "$STAGING" "$C" && echo si || echo no)" si
  chk "commits posteriores a $STAGING que tocan los módulos" "$(git rev-list --count "$STAGING..$C" -- pns_base pns_ai_mcp pns_ai_chatboo)" 0
  git archive "$C" pns_base pns_ai_mcp pns_ai_chatboo | tar -x -C "$T" || { echo "FALLO   git archive"; exit 1; }
  chk "árbol de los módulos (archivos y huella)" "$(arbol "$T" | tr '\n' ' ' | sed 's/ $//')" "$ARBOL_STAGING"
  chk "versiones" "$(for m in pns_base pns_ai_mcp pns_ai_chatboo; do grep -oE "'version': *'[^']+'" "$T/$m/__manifest__.py" | grep -oE "[0-9][0-9.]+"; done | tr '\n' ' ' | sed 's/ $//')" "14.0.1.2.69 14.0.3.1.973 14.0.2.1.587"

  echo "== 3. Lo que cambia fuera de pns_* y docs/ (el clon de LIYBEN tiene todo third_party)"
  for B in "$LIYBEN_HOY" origin/14.0; do
    L=$(git diff --name-only "$B" "$C" -- . ':(exclude)pns_base' ':(exclude)pns_ai_mcp' ':(exclude)pns_ai_chatboo' ':(exclude)docs')
    N=$(printf '%s' "$L" | grep -c . || true)
    echo "-- $B → commit: $N archivo(s)"
    [ "$N" = 0 ] || printf '%s\n' "$L" | sed 's/^/   /' | head -40
    M=""
    for d in $(printf '%s\n' "$L" | grep / | cut -d/ -f1 | sort -u); do
      if git cat-file -e "$B:$d/__manifest__.py" 2>/dev/null || git cat-file -e "$C:$d/__manifest__.py" 2>/dev/null; then M="$M $d"; fi
    done
    chk "módulos (no pns_*) que cambian de $B al commit" "${M# }" ""
  done

  echo "== 4. Relación con 14.0 (para el merge del punto 3; informativo)"
  chk "origin/14.0 es antecesor del commit" "$(git merge-base --is-ancestor origin/14.0 "$C" && echo si || echo no)" si info
  chk "commits de origin/14.0 que no están en el commit" "$(git rev-list --count "$C..origin/14.0")" 0 info
  chk "$LIYBEN_HOY es antecesor del commit" "$(git merge-base --is-ancestor "$LIYBEN_HOY" "$C" && echo si || echo no)" si info
  if [ "$F" = 0 ]; then echo "== E0: TODO OK"; else echo "== E0: $F FALLO(S). No sigas: pega la salida."; fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ly_e0
