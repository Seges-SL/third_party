lm_e() (
  # Merge (punto 3), equipo. Modos:
  #   antes    (solo lectura) antes de abrir el PR: la rama se puede integrar en 14.0 sin conflictos (M2).
  #   despues  (solo lectura del repo) tras el merge del PR, «Fetch origin» y, en Desktop, 14.0 y «Pull»: el merge
  #            commit y sus padres; guarda merge.txt para el VPS.
  #   enviar   [ALTERA el VPS: crea /tmp/liyben_merge (700)] copia lm_v.sh y merge.txt y comprueba sus huellas.
  #   recoger  [ALTERA el VPS: borra /tmp/liyben_merge] trae sus salidas a $DM/vps/, compara huellas y la borra.
  # Se lanza con: bash ~/Descargas/lm_e.sh <modo> (enviar y recoger necesitan VPS_PORT y VPS_DEST exportados).
  set -u
  umask 077
  MODO=${1:-}
  TANDA="LM E ${MODO}"
  REPO=~/GitHub/third_party
  DM=~/pns_ai_3973/liyben/merge
  LM=/tmp/liyben_merge
  RAMA=14.0-pns-ai-3973
  P1_CORTO=59bd6af
  P2_CORTO=2b2f5e7
  N_RAMA=179
  COMMIT_DESPLEGADO=3df4307129a44719a27dd30c12dd479ab0335a6b
  C14_VPS=f63d5a1
  ARBOL_RAMA="688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
  LMV_SHA=139a5aaf83c9b184bd120a01ea681ddda1694bece5129c4d3a1eee0996bb03eb
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  una() { tr '\n' ' ' | sed 's/ *$//'; }
  corte() { [ "$F" = 0 ] || { echo "== $TANDA: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  fin() { if [ "$F" = 0 ]; then echo "== $TANDA: TODO OK.${1:+ $1}"; else echo "== $TANDA: $F FALLO(S). No sigas: pega la salida."; fi; }
  arbol() {
    ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l ) | tr -d ' '
    ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 \
        | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1 )
  }
  corto() { printf '%.7s' "$1"; }
  si() { "$@" 2>/dev/null && echo si || echo no; }
  ultima() { ls -t $1 2>/dev/null | head -1; }
  marca() { if [ -n "$1" ] && [ -f "$1" ]; then grep -cx -- "$2" "$1" || true; else echo 0; fi; }
  case "$MODO" in antes|despues|enviar|recoger) ;; *) echo "Uso: bash $0 antes|despues|enviar|recoger"; exit 1 ;; esac
  D=$(cd "$(dirname "$0")" && pwd)
  mkdir -p "$DM" && chmod 700 "$DM" || exit 1
  O="$DM/lm_e-$MODO-$(date +%Y%m%d-%H%M%S).txt"
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  T=$(mktemp -d /tmp/lm_e.XXXXXX) || exit 1
  trap 'rm -rf -- "$T"' EXIT
  if [ "$MODO" = enviar ] || [ "$MODO" = recoger ]; then
    [ -n "${VPS_PORT:-}" ] && [ -n "${VPS_DEST:-}" ] || { echo "Faltan VPS_PORT y VPS_DEST: lánzala tras la línea read de §1"; exit 1; }
  fi
  vps() { ssh -T -p "$VPS_PORT" "$VPS_DEST" "$@"; }
  {
  echo "== $TANDA (equipo: merge de $RAMA en 14.0, $MODO): $(date '+%F %T')"
  cd "$REPO" || { echo "FALLO   no existe $REPO"; exit 1; }
  case "$MODO" in
  antes)
    echo "== 1. Repo (haz «Fetch origin» en GitHub Desktop antes)"
    chk "rama actual" "$(git rev-parse --abbrev-ref HEAD 2>&1)" "$RAMA"
    chk "árbol de trabajo limpio" "$(git status --porcelain | wc -l | tr -d ' ')" 0
    chk "al día con origin/$RAMA (delante|detrás)" "$(git rev-list --left-right --count "HEAD...origin/$RAMA" 2>&1 | tr '\t' '|')" "0|0"
    B=$(git rev-parse "origin/$RAMA")
    chk "cabeza de la rama" "$(corto "$B")" "$P2_CORTO"
    corte "repo"
    echo "== 2. 14.0 y la rama (M2: sin conflictos posibles)"
    chk "origin/14.0" "$(corto "$(git rev-parse -q --verify origin/14.0)")" "$P1_CORTO"
    chk "14.0 local = origin/14.0 (delante|detrás)" "$(git rev-list --left-right --count 'refs/heads/14.0...origin/14.0' 2>&1 | tr '\t' '|')" "0|0"
    chk "origin/14.0 es antecesor de la rama" "$(si git merge-base --is-ancestor origin/14.0 "$B")" si
    chk "commits de origin/14.0 fuera de la rama" "$(git rev-list --count "$B..origin/14.0")" 0
    chk "commits de la rama que entran en 14.0" "$(git rev-list --count "origin/14.0..$B")" "$N_RAMA"
    chk "$C14_VPS (14.0 del clon del VPS) es antecesor de origin/14.0" "$(si git merge-base --is-ancestor "$C14_VPS" origin/14.0)" si
    chk "el desplegado ($(corto "$COMMIT_DESPLEGADO")) es antecesor de la rama" "$(si git merge-base --is-ancestor "$COMMIT_DESPLEGADO" "$B")" si
    chk "archivos fuera de docs/ que cambian del desplegado a la rama" "$(git diff --name-only "$COMMIT_DESPLEGADO" "$B" -- . ':(exclude)docs' | una)" ""
    git archive "$B" pns_base pns_ai_mcp pns_ai_chatboo | tar -x -C "$T" || echo "FALLO   git archive"
    chk "árbol de los módulos de la rama (archivos y huella)" "$(arbol "$T" | una)" "$ARBOL_RAMA"
    fin "Abre el PR (base 14.0, origen $RAMA) y fusiona con «Create a merge commit», sin «Delete branch»."
    ;;
  despues)
    echo "== 1. Repo (antes: «Fetch origin»; en Desktop, rama 14.0 y «Pull»)"
    UA=$(ultima "$DM/lm_e-antes-*.txt")
    chk "último «antes» (${UA##*/}) con TODO OK" "$(marca "$UA" "== LM E antes: TODO OK. Abre el PR (base 14.0, origen $RAMA) y fusiona con «Create a merge commit», sin «Delete branch».")" 1
    chk "rama actual" "$(git rev-parse --abbrev-ref HEAD 2>&1)" 14.0
    chk "árbol de trabajo limpio" "$(git status --porcelain | wc -l | tr -d ' ')" 0
    chk "14.0 local = origin/14.0 (delante|detrás)" "$(git rev-list --left-right --count 'HEAD...origin/14.0' 2>&1 | tr '\t' '|')" "0|0"
    corte "repo"
    echo "== 2. El merge commit"
    M=$(git rev-parse origin/14.0)
    PADRES=$(git rev-list --parents -n 1 "$M" | cut -d' ' -f2-)
    P1=$(printf '%s' "$PADRES" | cut -d' ' -f1); P2=$(printf '%s' "$PADRES" | cut -s -d' ' -f2)
    echo "   merge: $(git log -1 --format='%H %ci %s' "$M")"
    chk "número de padres" "$(printf '%s' "$PADRES" | wc -w | tr -d ' ')" 2
    chk "padre 1 (14.0 de antes) | padre 2 (la rama)" "$(corto "$P1")|$(corto "$P2")" "$P1_CORTO|$P2_CORTO"
    chk "origin/$RAMA sigue en GitHub, en el padre 2 (sin «Delete branch»)" "$(git rev-parse -q --verify "origin/$RAMA" 2>&1)" "$P2"
    chk "$RAMA local en el padre 2" "$(git rev-parse -q --verify "refs/heads/$RAMA" 2>&1)" "$P2"
    chk "árbol del merge = árbol de la rama" "$(git rev-parse "$M^{tree}")" "$(git rev-parse "$P2^{tree}")"
    chk "commits que entran en 14.0 con el merge" "$(git rev-list --count "$P1..$M")" "$((N_RAMA + 1))"
    chk "archivos fuera de docs/ que cambian del desplegado al merge" "$(git diff --name-only "$COMMIT_DESPLEGADO" "$M" -- . ':(exclude)docs' | una)" ""
    git archive "$M" pns_base pns_ai_mcp pns_ai_chatboo | tar -x -C "$T" || echo "FALLO   git archive"
    chk "árbol de los módulos del merge (archivos y huella)" "$(arbol "$T" | una)" "$ARBOL_RAMA"
    corte "merge"
    printf '%s %s %s\n' "$M" "$P1" "$P2" > "$DM/merge.txt"
    echo "guardado: $DM/merge.txt (SHA-256 $(sha256sum "$DM/merge.txt" | cut -d' ' -f1))"
    fin "Vuelve a $RAMA en Desktop, pasa U0 v3 y después lm_e.sh enviar."
    ;;
  enviar)
    echo "== 1. Comprobaciones previas (equipo)"
    UD=$(ultima "$DM/lm_e-despues-*.txt")
    chk "último «despues» (${UD##*/}) con TODO OK" "$(marca "$UD" "== LM E despues: TODO OK. Vuelve a $RAMA en Desktop, pasa U0 v3 y después lm_e.sh enviar.")" 1
    chk "merge.txt: tres hashes" "$(grep -cxE '[0-9a-f]{40} [0-9a-f]{40} [0-9a-f]{40}' "$DM/merge.txt" 2>/dev/null || echo 0)" 1
    chk "merge.txt = origin/14.0 de ahora" "$(cut -d' ' -f1 "$DM/merge.txt" 2>/dev/null)" "$(git rev-parse -q --verify origin/14.0)"
    chk "lm_v.sh junto a esta tanda (SHA-256)" "$(sha256sum "$D/lm_v.sh" 2>/dev/null | cut -d' ' -f1)" "$LMV_SHA"
    corte "comprobaciones previas"
    echo "== 2. [ALTERA el VPS] $LM (700) con lm_v.sh y merge.txt"
    chk "$LM no existe aún en el VPS" "$(vps "test -e $LM && echo existe || echo no" 2>&1)" no
    corte "carpeta"
    vps "mkdir -m 700 $LM" 2>&1 | sed 's/^/   /'
    scp -q -P "$VPS_PORT" "$D/lm_v.sh" "$DM/merge.txt" "$VPS_DEST:$LM/" 2>&1 | sed 's/^/   /'
    ESP="$(cd "$D" && sha256sum lm_v.sh) $(cd "$DM" && sha256sum merge.txt)"
    chk "huellas en el VPS" "$(vps "cd $LM && sha256sum lm_v.sh merge.txt" 2>&1 | una)" "$(printf '%s\n' "$ESP" | una)"
    chk "permisos de $LM y archivos" "$(vps "stat -c '%a' $LM; ls -A $LM | wc -l" 2>&1 | una)" "700 2"
    fin "En la sesión SSH del VPS: bash $LM/lm_v.sh comprobar"
    ;;
  recoger)
    echo "== 1. Comprobaciones previas"
    chk "$DM/vps no existe aún" "$( [ -e "$DM/vps" ] && echo existe || echo no)" no
    LV=$(vps "ls -1 $LM 2>/dev/null" 2>&1)
    echo "   en el VPS: $(printf '%s\n' "$LV" | una)"
    UAP=$(printf '%s\n' "$LV" | grep -E '^lm_v-APLICAR-' | sort | tail -1)
    chk "un APLICAR en el VPS con TODO OK (${UAP:-ninguno})" "$( [ -n "$UAP" ] && vps "grep -cx '== LM V APLICAR: TODO OK. Clon en 14.0 (merge). Pega la salida. Después, U0 v4 en el equipo.' $LM/$UAP" 2>&1 || echo 0)" 1
    corte "comprobaciones previas"
    echo "== 2. Copia de $LM a $DM/vps"
    mkdir -m 700 "$DM/vps" || exit 1
    scp -q -P "$VPS_PORT" "$VPS_DEST:$LM/*" "$DM/vps/" 2>&1 | sed 's/^/   /'
    RS=$(vps "cd $LM && sha256sum * | LC_ALL=C sort -k2" 2>&1)
    chk "huellas copiadas = las del VPS" "$(cd "$DM/vps" && sha256sum * | LC_ALL=C sort -k2 | una)" "$(printf '%s\n' "$RS" | una)"
    chk "archivos copiados" "$(ls -A "$DM/vps" | wc -l | tr -d ' ')" "$(printf '%s\n' "$LV" | grep -c . || true)"
    corte "copia"
    echo "== 3. [ALTERA el VPS] borrado de $LM (con la misma lista)"
    chk "lista del VPS sin cambios" "$(vps "ls -1 $LM" 2>&1 | una)" "$(printf '%s\n' "$LV" | una)"
    corte "lista"
    vps "rm -rf -- $LM" 2>&1 | sed 's/^/   /'
    chk "$LM borrada" "$(vps "test -e $LM && echo existe || echo no" 2>&1)" no
    fin "Pega la salida. Después, los commits."
    ;;
  esac
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
lm_e "$@"
