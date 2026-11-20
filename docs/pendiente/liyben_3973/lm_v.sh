lm_v() (
  # Merge (punto 3), VPS: vuelve el clon de third_party de 14.0-pns-ai-3973 (3df4307) a 14.0 en el merge commit, con un
  # solo cambio de árbol (update-ref con valor previo y checkout, como el UID 101). Sin parar el web ni -u: los pns_*
  # del merge son los montados (688 / 0dc381e0…); solo cambia docs/. Modos: comprobar (solo lectura) y APLICAR.
  # Se lanza en la sesión SSH interactiva: bash /tmp/liyben_merge/lm_v.sh comprobar|APLICAR
  set -u
  umask 077
  TANDA="LM V ${1:-}"
  LM=/tmp/liyben_merge
  COMPOSE=/opt/odoo
  CLON=/opt/odoo/addons/custom/third_party
  LOGF=/opt/odoo/logs/odoo-server.log
  RAMA_ANTES=14.0-pns-ai-3973
  COMMIT_ANTES=3df4307129a44719a27dd30c12dd479ab0335a6b
  C14_ANTES=f63d5a1
  C3=578859b
  P1_CORTO=59bd6af
  P2_CORTO=2b2f5e7
  ARBOL_RAMA="688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  una() { tr '\n' ' ' | sed 's/ *$//'; }
  corte() { [ "$F" = 0 ] || { echo "== $TANDA: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  fin() { if [ "$F" = 0 ]; then echo "== $TANDA: TODO OK.${1:+ $1}"; else echo "== $TANDA: $F FALLO(S). No sigas: pega la salida."; fi; }
  g() { git --no-optional-locks -c safe.directory="$CLON" -C "$CLON" "$@"; }
  g101() { sudo -n -u messagebus env HOME=/tmp git -c safe.directory="$CLON" -C "$CLON" "$@"; }
  arbol() {
    ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l ) | tr -d ' '
    ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 \
        | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1 )
  }
  web() { ( cd "$COMPOSE" && docker compose ps --status running --services 2>/dev/null | grep -cx web || true ); }
  corto() { printf '%.7s' "$1"; }
  MODO=${1:-}
  case "$MODO" in comprobar|APLICAR) ;; *) echo "Uso: bash $LM/lm_v.sh comprobar|APLICAR"; exit 1 ;; esac
  [ "$(cd "$(dirname "$0")" && pwd)" = "$LM" ] || { echo "Lánzala desde $LM: bash $LM/lm_v.sh $MODO"; exit 1; }
  sudo -v || { echo "FALLO   sudo. No se ha seguido."; exit 1; }
  O="$LM/lm_v-$MODO-$(date -u +%Y%m%d-%H%M%S).txt"
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  T=$(mktemp -d "$LM/arbol.XXXXXX") || exit 1
  trap 'rm -rf -- "$T"' EXIT
  {
  echo "== $TANDA (VPS: clon de third_party a 14.0 en el merge commit; $MODO): $(date -u '+%F %T') UTC"
  echo "== 1. Comprobaciones previas (solo lectura)"
  read -r M P1 P2 REST < "$LM/merge.txt" 2>/dev/null || true
  chk "merge.txt: tres hashes (merge, padre 1, padre 2)" "$(printf '%s %s %s\n' "${M:-}" "${P1:-}" "${P2:-}" | grep -cxE '[0-9a-f]{40} [0-9a-f]{40} [0-9a-f]{40}' || true)" 1
  corte "merge.txt"
  chk "padres del merge en merge.txt (14.0 de antes | la rama)" "$(corto "$P1")|$(corto "$P2")" "$P1_CORTO|$P2_CORTO"
  echo "   merge commit: $M"
  if [ "$MODO" = APLICAR ]; then
    UC=$(ls -t "$LM"/lm_v-comprobar-*.txt 2>/dev/null | head -1)
    chk "último comprobar (${UC##*/}) con TODO OK" "$( [ -n "$UC" ] && grep -cx "== LM V comprobar: TODO OK. Corte: pega la salida. Después, APLICAR antes de una hora." "$UC" || echo 0)" 1
    chk "comprobar de hace menos de una hora (si no, repítelo)" "$( [ -n "$UC" ] && [ $(( $(date +%s) - $(stat -c %Y "$UC") )) -lt 3600 ] && echo si || echo no)" si
  fi
  chk "web en marcha" "$(web)" 1
  chk "rama del clon" "$(g rev-parse --abbrev-ref HEAD 2>&1)" "$RAMA_ANTES"
  chk "HEAD del clon (el commit desplegado)" "$(g rev-parse HEAD 2>&1)" "$COMMIT_ANTES"
  chk "clon limpio (líneas de status)" "$(g status --porcelain 2>&1 | wc -l | tr -d ' ')" 0
  chk "stash vacío" "$(g stash list 2>&1 | wc -l | tr -d ' ')" 0
  chk "14.0 del clon (local)" "$(corto "$(g rev-parse -q --verify refs/heads/14.0 2>&1)")" "$C14_ANTES"
  O14=$(corto "$(g rev-parse -q --verify refs/remotes/origin/14.0 2>&1)")
  if [ "$O14" = "$(corto "$M")" ]; then echo "INFO    origin/14.0 del clon ya en el merge (un APLICAR anterior hizo el fetch y paró antes de escribir)"
  else chk "origin/14.0 del clon" "$O14" "$C14_ANTES"; fi
  chk "upstream de 14.0" "$(g rev-parse --abbrev-ref '14.0@{u}' 2>&1)" origin/14.0
  chk "refspec del clon (solo 14.0)" "$(g config --get-all remote.origin.fetch 2>&1 | una)" "+refs/heads/14.0:refs/remotes/origin/14.0"
  chk "clon superficial" "$(g rev-parse --is-shallow-repository 2>&1)" true
  SH0=$(sha256sum "$CLON/.git/shallow" 2>&1 | cut -d' ' -f1)
  chk ".git/shallow legible" "$(printf '%s' "$SH0" | grep -cxE '[0-9a-f]{64}' || true)" 1
  echo "   huella de .git/shallow: $SH0"
  chk "propietario de .git/ (archivos que no son del UID 101)" "$(find "$CLON/.git" ! -uid 101 2>/dev/null | wc -l | tr -d ' ')" 0
  N101=$(find "$CLON" -path "$CLON/.git" -prune -o ! -uid 101 -print 2>/dev/null | wc -l | tr -d ' ')
  echo "   archivos del árbol de trabajo que no son del UID 101 (sin .git): $N101 (después se exige el mismo número)"
  chk "árbol de los módulos montados (archivos y huella)" "$(arbol "$CLON" | una)" "$ARBOL_RAMA"
  chk "remota, como el UID 101 (ls-remote: 14.0 | la rama)" "$(g101 ls-remote origin refs/heads/14.0 "refs/heads/$RAMA_ANTES" 2>&1 | awk '{print $1}' | una)" "$M $P2"
  corte "comprobaciones previas"
  [ "$MODO" = comprobar ] && { fin "Corte: pega la salida. Después, APLICAR antes de una hora."; exit 0; }

  OFF=$(stat -c %s "$LOGF" 2>&1)
  chk "posición del log antes de cambiar nada" "$(printf '%s' "$OFF" | grep -cxE '[0-9]+' || true)" 1
  corte "log"
  echo "   log desde el byte $OFF"

  echo "== 2. [ALTERA el clon: solo referencias] fetch de 14.0 como el UID 101 (refspec del clon, sin --depth)"
  g101 fetch origin 2>&1 | sed 's/^/   /'
  chk "origin/14.0 del clon = merge" "$(g rev-parse -q --verify refs/remotes/origin/14.0 2>&1)" "$M"
  chk "padres del merge en el clon" "$(g rev-list --parents -n 1 "$M" 2>&1)" "$M $P1 $P2"
  chk "$COMMIT_ANTES (montado) es antecesor del merge" "$(g merge-base --is-ancestor "$COMMIT_ANTES" "$M" 2>/dev/null && echo si || echo no)" si
  chk "14.0 del clon ($C14_ANTES) es antecesor del merge" "$(g merge-base --is-ancestor refs/heads/14.0 "$M" 2>/dev/null && echo si || echo no)" si
  chk "archivos fuera de docs/ que cambian del montado al merge" "$(g diff --name-only "$COMMIT_ANTES" "$M" -- . ':(exclude)docs' 2>&1 | una)" ""
  echo "   archivos de docs/ que cambian: $(g diff --name-only "$COMMIT_ANTES" "$M" -- docs 2>&1 | wc -l | tr -d ' ')"
  g archive "$M" pns_base pns_ai_mcp pns_ai_chatboo | tar -x -C "$T" || echo "FALLO   git archive del merge"
  chk "árbol de los módulos del merge (archivos y huella)" "$(arbol "$T" | una)" "$ARBOL_RAMA"
  chk ".git/shallow sin cambios tras el fetch" "$(sha256sum "$CLON/.git/shallow" 2>&1 | cut -d' ' -f1)" "$SH0"
  chk "rama, HEAD y status del clon, sin cambios" "$(g rev-parse --abbrev-ref HEAD)|$(g rev-parse HEAD)|$(g status --porcelain | wc -l | tr -d ' ')" "$RAMA_ANTES|$COMMIT_ANTES|0"
  chk "propietario de .git/ tras el fetch" "$(find "$CLON/.git" ! -uid 101 2>/dev/null | wc -l | tr -d ' ')" 0
  corte "fetch"

  echo "== 3. [ALTERA el clon] 14.0 al merge (update-ref con valor previo) y checkout de 14.0, como el UID 101, a las $(date -u +%T) UTC"
  V14=$(g rev-parse refs/heads/14.0)
  g101 update-ref -m "lm_v: 14.0 al merge (punto 3)" refs/heads/14.0 "$M" "$V14" 2>&1 | sed 's/^/   /'
  chk "14.0 del clon = merge" "$(g rev-parse -q --verify refs/heads/14.0 2>&1)" "$M"
  corte "update-ref"
  g101 checkout 14.0 2>&1 | sed 's/^/   /'
  echo "== 4. Después (solo lectura)"
  chk "rama y HEAD del clon" "$(g rev-parse --abbrev-ref HEAD 2>&1)|$(g rev-parse HEAD 2>&1)" "14.0|$M"
  chk "clon limpio (líneas de status)" "$(g status --porcelain 2>&1 | wc -l | tr -d ' ')" 0
  chk "14.0 frente a origin/14.0 (delante|detrás)" "$(g rev-list --left-right --count '14.0...origin/14.0' 2>&1 | tr '\t' '|')" "0|0"
  chk "árbol de los módulos montados (archivos y huella)" "$(arbol "$CLON" | una)" "$ARBOL_RAMA"
  chk ".git/shallow sin cambios" "$(sha256sum "$CLON/.git/shallow" 2>&1 | cut -d' ' -f1)" "$SH0"
  chk "propietario de .git/ (archivos que no son del UID 101)" "$(find "$CLON/.git" ! -uid 101 2>/dev/null | wc -l | tr -d ' ')" 0
  chk "archivos del árbol de trabajo que no son del UID 101 (sin .git): los mismos que antes" "$(find "$CLON" -path "$CLON/.git" -prune -o ! -uid 101 -print 2>/dev/null | wc -l | tr -d ' ')" "$N101"
  chk "ramas que se quedan hasta la limpieza final (M5)" "$(corto "$(g rev-parse -q --verify "refs/heads/$RAMA_ANTES")")|$(corto "$(g rev-parse -q --verify refs/heads/14.0-pns-ai-3)")" "$(corto "$COMMIT_ANTES")|$C3"
  chk "web en marcha (no se ha parado)" "$(web)" 1
  S=$(stat -c %s "$LOGF")
  chk "el log no se ha rotado" "$( [ "$S" -ge "$OFF" ] && echo no || echo si)" no
  X() { tail -c +"$((OFF + 1))" "$LOGF"; }
  echo "   log desde el byte $OFF: $(X | wc -l | tr -d ' ') líneas"
  chk "ERROR o CRITICAL en el log desde el principio de la tanda" "$(X | grep -cE ' (ERROR|CRITICAL) ' || true)" 0
  chk "Traceback en el log desde el principio de la tanda" "$(X | grep -c '^Traceback' || true)" 0
  chk "liyben.com/web/login" "$(curl -sS -o /dev/null -w '%{http_code}' https://liyben.com/web/login 2>&1)" 200
  chk "GET liyben.com/mcp (Nginx, D20)" "$(curl -sS -o /dev/null -w '%{http_code}' https://liyben.com/mcp 2>&1)" 404
  fin "Clon en 14.0 (merge). Pega la salida. Después, U0 v4 en el equipo."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
lm_v "$@"
