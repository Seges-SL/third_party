lk_m() (
  # Limpieza final (punto 4, D69, M7), equipo: segundo merge commit de 14.0-pns-ai-3973 en 14.0 (PR #3) y borrado de
  # la rama. El VPS no lo necesita (D68, M7): su clon sigue en d9b2e16. Modos, con corte entre cada uno:
  #   antes    (solo lectura; ls-remote sale a GitHub) antes de abrir el PR: 5 commits, solo docs/, sin conflictos.
  #   despues  (solo lectura) tras el PR, «Fetch origin» y, en Desktop, rama 14.0 (y «Pull» si sale): el merge commit
  #            y sus padres; guarda merge2.txt.
  #   BORRAR   [ALTERA GitHub] push de borrado de la rama con --force-with-lease al hash medido y git branch -d de la
  #            local, con Desktop en 14.0.
  # Uso: bash ~/Descargas/lk_m.sh antes | despues | BORRAR
  set -u
  umask 077
  MODO=${1:-}
  TANDA="LK M $MODO"
  DL=~/pns_ai_3973/liyben/limpieza
  REPO=~/GitHub/third_party
  RAMA=14.0-pns-ai-3973
  M1=d9b2e165b6d8069417b6b4e0329fa0f5be36c52b
  BASE_CORTO=2b2f5e7
  B_CORTO=3a9b111
  COMMITS="81a4609 1dc8395 1dbd6e1 2afd3ed 3a9b111"
  ARBOL_RAMA="688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
  ARCHIVOS="docs/pendiente/instalacion_liyben_pns_ai.md docs/pendiente/lab_procedimiento_3973.md docs/pendiente/liyben_3973.md docs/pendiente/liyben_3973/lk_e.sh docs/pendiente/liyben_3973/lk_g.sh docs/pendiente/liyben_3973/lk_l.sh docs/pendiente/liyben_3973/lk_v.sh docs/pendiente/liyben_3973/lm_e.sh docs/pendiente/liyben_3973/lm_main.sh docs/pendiente/liyben_3973/lm_v.sh docs/pendiente/liyben_3973/lu_u0_v4.sh docs/pendiente/plan_correccion_pns_ai.md docs/pendiente/plan_correccion_pns_ai_3973.md docs/pendiente/plan_staging_pns_ai.md docs/pendiente/staging_3973.md"
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  una() { tr '\n' ' ' | sed 's/ *$//'; }
  corte() { [ "$F" = 0 ] || { echo "== $TANDA: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  fin() { if [ "$F" = 0 ]; then echo "== $TANDA: TODO OK.${1:+ $1}"; else echo "== $TANDA: $F FALLO(S). No sigas: pega la salida."; fi; }
  g() { git -C "$REPO" "$@"; }
  corto() { printf '%.7s' "$1"; }
  si() { "$@" 2>/dev/null && echo si || echo no; }
  remota() { g ls-remote origin "refs/heads/$1" 2>&1 | awk '{print $1}'; }
  ref() { g rev-parse -q --verify "$1" 2>/dev/null; }
  ramas_gh() { g ls-remote --heads origin 2>&1 | grep -v "	refs/heads/$RAMA\$" | LC_ALL=C sort; }
  arbol() {
    ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l ) | tr -d ' '
    ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 \
        | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1 )
  }
  arbol_de() { local t; t=$(mktemp -d /tmp/lk_m.XXXXXX) || return; g archive "$1" pns_base pns_ai_mcp pns_ai_chatboo | tar -x -C "$t"; arbol "$t" | una; rm -rf -- "$t"; }
  ultima() { ls -t "$DL"/lk_m-"$1"-*.txt 2>/dev/null | head -1; }
  marca() { if [ -n "$1" ] && [ -f "$1" ]; then grep -cx -- "$2" "$1" || true; else echo 0; fi; }
  FIN_ANTES="Abre el PR #3 con compare/14.0...$RAMA (en la página: base 14.0, 5 commits, 15 archivos) y fusiona con «Create a merge commit», sin «Delete branch»."
  FIN_DESPUES="Corte: pega la salida. Desktop sigue en 14.0. Después, BORRAR."
  case "$MODO" in antes|despues|BORRAR) ;; *) echo "Uso: bash $0 antes | despues | BORRAR"; exit 1 ;; esac
  mkdir -p "$DL" && chmod 700 "$DL" || exit 1
  O="$DL/lk_m-$MODO-$(date +%Y%m%d-%H%M%S).txt"
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== $TANDA (equipo → GitHub: segundo merge de $RAMA en 14.0, M7): $(date '+%F %T')"
  chk "rama por defecto de GitHub" "$(g ls-remote --symref origin HEAD 2>&1 | awk '/^ref:/{print $2}')" refs/heads/14.0
  case "$MODO" in
  antes)
    echo "== 1. Repo (haz «Fetch origin» en GitHub Desktop antes)"
    chk "rama actual" "$(g rev-parse --abbrev-ref HEAD 2>&1)" "$RAMA"
    chk "árbol limpio" "$(g status --porcelain 2>&1 | wc -l | tr -d ' ')" 0
    B=$(ref HEAD)
    chk "cabeza de la rama" "$(corto "$B")" "$B_CORTO"
    chk "HEAD = origin/$RAMA = la rama en GitHub" "$(ref "refs/remotes/origin/$RAMA")|$(remota "$RAMA")" "$B|$B"
    chk "14.0 en GitHub, origin/14.0 y 14.0 local = el primer merge commit" "$(remota 14.0)|$(ref refs/remotes/origin/14.0)|$(ref refs/heads/14.0)" "$M1|$M1|$M1"
    corte "repo"
    echo "== 2. Lo que entra en 14.0 (sin conflictos posibles)"
    MB=$(g merge-base "$M1" "$B" 2>&1)
    chk "base común = la cabeza del primer merge" "$(corto "$MB")" "$BASE_CORTO"
    chk "árbol del primer merge = árbol de la base (14.0 no cambió nada desde ella)" "$(g rev-parse "$M1^{tree}" 2>&1)" "$(g rev-parse "$MB^{tree}" 2>&1)"
    chk "commits de 14.0 fuera de la rama (solo el primer merge)" "$(g rev-list "$B..$M1" 2>&1 | una)" "$M1"
    chk "commits de la rama que entran (en orden)" "$(g rev-list --reverse --abbrev=7 --abbrev-commit "$M1..$B" 2>&1 | una)" "$COMMITS"
    chk "archivos que cambian (todos en docs/)" "$(g diff --name-only "$MB" "$B" 2>&1 | LC_ALL=C sort | una)" "$ARCHIVOS"
    chk "árbol de los módulos de la rama (archivos y huella)" "$(arbol_de "$B")" "$ARBOL_RAMA"
    fin "$FIN_ANTES"
    ;;
  despues)
    echo "== 1. Repo (antes: «Fetch origin»; en Desktop, rama 14.0 y «Pull» si sale)"
    UA=$(ultima antes)
    chk "último antes (${UA##*/}) con TODO OK" "$(marca "$UA" "== LK M antes: TODO OK. $FIN_ANTES")" 1
    chk "rama actual" "$(g rev-parse --abbrev-ref HEAD 2>&1)" 14.0
    chk "árbol limpio" "$(g status --porcelain 2>&1 | wc -l | tr -d ' ')" 0
    M2=$(ref refs/remotes/origin/14.0)
    chk "14.0 local = origin/14.0 = 14.0 en GitHub" "$(ref HEAD)|$(remota 14.0)" "$M2|$M2"
    corte "repo"
    echo "== 2. El segundo merge commit"
    PADRES=$(g rev-list --parents -n 1 "$M2" | cut -d' ' -f2-)
    P1=$(printf '%s' "$PADRES" | cut -d' ' -f1); P2=$(printf '%s' "$PADRES" | cut -s -d' ' -f2)
    echo "   merge: $(g log -1 --format='%H %ci %s' "$M2")"
    chk "número de padres" "$(printf '%s' "$PADRES" | wc -w | tr -d ' ')" 2
    chk "padre 1 (el primer merge) | padre 2 (la rama)" "$P1|$(corto "$P2")" "$M1|$B_CORTO"
    chk "la rama sigue (sin «Delete branch»): GitHub, origin/ y local en el padre 2" "$(remota "$RAMA")|$(ref "refs/remotes/origin/$RAMA")|$(ref "refs/heads/$RAMA")" "$P2|$P2|$P2"
    chk "árbol del merge = árbol de la rama" "$(g rev-parse "$M2^{tree}")" "$(g rev-parse "$P2^{tree}")"
    chk "commits que entran en 14.0 con el merge" "$(g rev-list --count "$M1..$M2")" 6
    chk "archivos que cambian del primer merge al segundo (todos en docs/)" "$(g diff --name-only "$M1" "$M2" 2>&1 | LC_ALL=C sort | una)" "$ARCHIVOS"
    chk "árbol de los módulos del merge (archivos y huella)" "$(arbol_de "$M2")" "$ARBOL_RAMA"
    corte "merge"
    printf '%s %s %s\n' "$M2" "$P1" "$P2" > "$DL/merge2.txt"
    echo "   guardado: $DL/merge2.txt (SHA-256 $(sha256sum "$DL/merge2.txt" | cut -d' ' -f1))"
    fin "$FIN_DESPUES"
    ;;
  BORRAR)
    UD=$(ultima despues)
    chk "último despues (${UD##*/}) con TODO OK" "$(marca "$UD" "== LK M despues: TODO OK. $FIN_DESPUES")" 1
    chk "merge2.txt: tres hashes" "$(grep -cxE '[0-9a-f]{40} [0-9a-f]{40} [0-9a-f]{40}' "$DL/merge2.txt" 2>/dev/null || echo 0)" 1
    M2=$(cut -d' ' -f1 "$DL/merge2.txt" 2>/dev/null); P2=$(cut -s -d' ' -f3 "$DL/merge2.txt" 2>/dev/null)
    chk "repo en 14.0 (no en la que se borra) y limpio" "$(g rev-parse --abbrev-ref HEAD 2>&1)|$(g status --porcelain 2>&1 | wc -l | tr -d ' ')" "14.0|0"
    chk "14.0 en GitHub y local = el segundo merge" "$(remota 14.0)|$(ref HEAD)" "$M2|$M2"
    chk "$RAMA en GitHub, origin/ y local = el padre 2 medido" "$(remota "$RAMA")|$(ref "refs/remotes/origin/$RAMA")|$(ref "refs/heads/$RAMA")" "$P2|$P2|$P2"
    chk "$RAMA antecesora de 14.0 (git branch -d la aceptará)" "$(si g merge-base --is-ancestor "$P2" HEAD)" si
    OTRAS=$(ramas_gh)
    echo "   otras ramas de GitHub: $(printf '%s\n' "$OTRAS" | wc -l | tr -d ' ') (no se tocan)"
    corte "comprobaciones"
    echo "== [ALTERA GitHub] borrado de $RAMA con --force-with-lease=$RAMA:$(corto "$P2"), a las $(date +%T)"
    g push --force-with-lease="refs/heads/$RAMA:$P2" origin ":refs/heads/$RAMA" 2>&1 | sed 's/^/   /'
    g branch -d "$RAMA" 2>&1 | sed 's/^/   /'
    echo "== Después (solo lectura)"
    chk "$RAMA en GitHub" "$(remota "$RAMA")" ""
    chk "$RAMA local y su copia de origin" "$(ref "refs/heads/$RAMA")|$(ref "refs/remotes/origin/$RAMA")" "|"
    chk "14.0 de GitHub, sin cambios" "$(remota 14.0)" "$M2"
    chk "las otras ramas de GitHub, sin cambios" "$(ramas_gh)" "$OTRAS"
    chk "repo en 14.0 y limpio" "$(g rev-parse --abbrev-ref HEAD)|$(g status --porcelain | wc -l | tr -d ' ')" "14.0|0"
    chk "los commits de la rama siguen en 14.0" "$(si g merge-base --is-ancestor "$P2" HEAD)" si
    fin "En GitHub Desktop, «Fetch origin»: $RAMA ya no aparece. Pega la salida."
    ;;
  esac
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
lk_m "$@"
