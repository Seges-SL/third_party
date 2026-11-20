lm_main() (
  # Deshace el PR #1 fusionado por error en main (opción B, Sergio 20/11/2026 14:02): devuelve main de GitHub a su
  # commit de antes (0447995, «Initial commit») con un push forzado con compuerta (--force-with-lease: solo si main
  # sigue en el merge fb2e878) y la main local de Sergio al mismo commit (update-ref con valor previo). No toca 14.0 ni
  # la rama 14.0-pns-ai-3973. Modos: comprobar (solo lectura; consulta GitHub con ls-remote) y APLICAR.
  # Se lanza con: bash ~/Descargas/lm_main.sh comprobar|APLICAR (antes, «Fetch origin» en GitHub Desktop).
  set -u
  umask 077
  MODO=${1:-}
  TANDA="LM MAIN ${MODO}"
  REPO=~/GitHub/third_party
  DM=~/pns_ai_3973/liyben/merge
  MERGE_MAL=fb2e8785a35f4b450f28e1c334459b4bc1808f22
  MAIN_ANTES_CORTO=0447995
  MAIN_ANTES_ASUNTO="Initial commit"
  RAMA=14.0-pns-ai-3973
  RAMA_CORTO=2b2f5e7
  C14_CORTO=59bd6af
  export GIT_TERMINAL_PROMPT=0
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  una() { tr '\n' ' ' | sed 's/ *$//'; }
  corte() { [ "$F" = 0 ] || { echo "== $TANDA: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  fin() { if [ "$F" = 0 ]; then echo "== $TANDA: TODO OK.${1:+ $1}"; else echo "== $TANDA: $F FALLO(S). No sigas: pega la salida."; fi; }
  corto() { printf '%.7s' "$1"; }
  remoto() { git ls-remote origin "refs/heads/$1" 2>&1 | awk '{print $1}' | una; }
  case "$MODO" in comprobar|APLICAR) ;; *) echo "Uso: bash $0 comprobar|APLICAR"; exit 1 ;; esac
  mkdir -p "$DM" && chmod 700 "$DM" || exit 1
  O="$DM/lm_main-$MODO-$(date +%Y%m%d-%H%M%S).txt"
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== $TANDA (equipo: main de GitHub y la local, de vuelta a $MAIN_ANTES_CORTO; $MODO): $(date '+%F %T')"
  cd "$REPO" || { echo "FALLO   no existe $REPO"; exit 1; }
  echo "== 1. Comprobaciones previas (repo local; haz «Fetch origin» en GitHub Desktop antes)"
  if [ "$MODO" = APLICAR ]; then
    UC=$(ls -t "$DM"/lm_main-comprobar-*.txt 2>/dev/null | head -1)
    chk "último comprobar (${UC##*/}) con TODO OK" "$( [ -n "$UC" ] && grep -cx '== LM MAIN comprobar: TODO OK. Corte: pega la salida. Después, APLICAR antes de una hora.' "$UC" || echo 0)" 1
    chk "comprobar de hace menos de una hora (si no, repítelo)" "$( [ -n "$UC" ] && [ $(( $(date +%s) - $(stat -c %Y "$UC") )) -lt 3600 ] && echo si || echo no)" si
  fi
  CUR=$(git rev-parse --abbrev-ref HEAD 2>&1)
  chk "rama actual: no es main (14.0 o $RAMA)" "$(case "$CUR" in 14.0|"$RAMA") echo si ;; *) echo "no ($CUR)" ;; esac)" si
  chk "árbol de trabajo limpio" "$(git status --porcelain | wc -l | tr -d ' ')" 0
  chk "origin/main (tu copia) = el merge por error" "$(git rev-parse -q --verify refs/remotes/origin/main 2>&1)" "$MERGE_MAL"
  chk "main local = el merge por error" "$(git rev-parse -q --verify refs/heads/main 2>&1)" "$MERGE_MAL"
  PADRES=$(git rev-list --parents -n 1 "$MERGE_MAL" 2>/dev/null | cut -d' ' -f2-)
  MA=$(printf '%s' "$PADRES" | cut -d' ' -f1); P2=$(printf '%s' "$PADRES" | cut -s -d' ' -f2)
  chk "padres del merge (main de antes | la rama)" "$(corto "$MA")|$(corto "$P2")|$(printf '%s' "$PADRES" | wc -w | tr -d ' ')" "$MAIN_ANTES_CORTO|$RAMA_CORTO|2"
  chk "main de antes: asunto" "$(git log -1 --format=%s "$MA" 2>&1)" "$MAIN_ANTES_ASUNTO"
  chk "main de antes: commits en su historia (solo él)" "$(git rev-list --count "$MA" 2>&1)" 1
  corte "repo local"
  echo "   main de antes: $MA"
  echo "== 2. GitHub en este momento (ls-remote, solo lectura; sin pedir contraseña)"
  chk "main en GitHub = el merge por error" "$(remoto main)" "$MERGE_MAL"
  chk "14.0 en GitHub (sin cambios)" "$(corto "$(remoto 14.0)")" "$C14_CORTO"
  chk "$RAMA en GitHub (sin cambios)" "$(remoto "$RAMA")" "$P2"
  corte "GitHub"
  [ "$MODO" = comprobar ] && { fin "Corte: pega la salida. Después, APLICAR antes de una hora."; exit 0; }

  echo "== 3. [ALTERA GitHub] main al commit de antes, con --force-with-lease (solo si sigue en el merge)"
  git push --force-with-lease="refs/heads/main:$MERGE_MAL" origin "$MA:refs/heads/main" 2>&1 | sed 's/^/   /'
  chk "main en GitHub = main de antes" "$(remoto main)" "$MA"
  corte "push"
  echo "== 4. [ALTERA el repo local: solo referencias] fetch y main local al commit de antes (update-ref con valor previo)"
  git fetch -q origin 2>&1 | sed 's/^/   /'
  git update-ref -m "lm_main: main de vuelta a $MAIN_ANTES_CORTO" refs/heads/main "$MA" "$MERGE_MAL" 2>&1 | sed 's/^/   /'
  echo "== 5. Después (solo lectura)"
  chk "origin/main (tu copia) = main de antes" "$(git rev-parse -q --verify refs/remotes/origin/main 2>&1)" "$MA"
  chk "main local = main de antes" "$(git rev-parse -q --verify refs/heads/main 2>&1)" "$MA"
  chk "main local frente a origin/main (delante|detrás)" "$(git rev-list --left-right --count 'main...origin/main' 2>&1 | tr '\t' '|')" "0|0"
  chk "el merge ya no está en main" "$(git merge-base --is-ancestor "$MERGE_MAL" refs/heads/main 2>/dev/null && echo si || echo no)" no
  chk "14.0 en GitHub y en tu copia (sin cambios)" "$(corto "$(remoto 14.0)")|$(corto "$(git rev-parse origin/14.0)")" "$C14_CORTO|$C14_CORTO"
  chk "$RAMA en GitHub y en tu copia (sin cambios)" "$(remoto "$RAMA")|$(git rev-parse "origin/$RAMA")" "$P2|$P2"
  chk "rama actual y árbol limpio (sin cambios)" "$(git rev-parse --abbrev-ref HEAD)|$(git status --porcelain | wc -l | tr -d ' ')" "$CUR|0"
  fin "main deshecho. Pega la salida. Después, «Fetch origin» en Desktop y otra vez lm_e.sh antes."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
lm_main "$@"
