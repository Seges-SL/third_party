lk_g() (
  # Limpieza final (punto 4, D69, K9), equipo: borra la rama 14.0-pns-ai-3 de GitHub y la local. Ya está integrada en
  # 14.0 (antecesora de d9b2e16). La 14.0-pns-ai-3973 se borra después del segundo merge commit (M7), con otra tanda.
  #   comprobar  (solo lectura; ls-remote sale a GitHub)
  #   BORRAR     [ALTERA GitHub] push de borrado con --force-with-lease al hash medido, y git branch -d de la local
  # Antes: «Fetch origin» en GitHub Desktop, y en GitHub, ningún PR abierto desde 14.0-pns-ai-3.
  # Uso: bash ~/Descargas/lk_g.sh comprobar | BORRAR
  set -u
  umask 077
  MODO=${1:-}
  TANDA="LK G $MODO"
  DL=~/pns_ai_3973/liyben/limpieza
  REPO=~/GitHub/third_party
  B=14.0-pns-ai-3
  B_HASH=884d33fd76c2488f4080a37bcd9e374600374fc0
  M=d9b2e165b6d8069417b6b4e0329fa0f5be36c52b
  RAMA=14.0-pns-ai-3973
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
  remota() { g ls-remote origin "refs/heads/$1" 2>&1 | awk '{print $1}'; }
  case "$MODO" in comprobar|BORRAR) ;; *) echo "Uso: bash $0 comprobar | BORRAR"; exit 1 ;; esac
  mkdir -p "$DL" && chmod 700 "$DL" || exit 1
  O="$DL/lk_g-$MODO-$(date +%Y%m%d-%H%M%S).txt"
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== $TANDA (equipo → GitHub: rama $B): $(date '+%F %T')"
  if [ "$MODO" = BORRAR ]; then
    UC=$(ls -t "$DL"/lk_g-comprobar-*.txt 2>/dev/null | head -1)
    chk "último comprobar (${UC##*/}) con TODO OK" "$( [ -n "$UC" ] && grep -cx "== LK G comprobar: TODO OK. Corte: mira en GitHub que no hay ningún PR abierto desde $B y pega la salida. Después, BORRAR." "$UC" || echo 0)" 1
  fi
  chk "repo en $RAMA (no en la que se borra)" "$(g rev-parse --abbrev-ref HEAD 2>&1)" "$RAMA"
  chk "árbol limpio" "$(g status --porcelain 2>&1 | wc -l | tr -d ' ')" 0
  chk "rama por defecto de GitHub" "$(g ls-remote --symref origin HEAD 2>&1 | awk '/^ref:/{print $2}')" refs/heads/14.0
  chk "14.0 de GitHub = el merge commit" "$(remota 14.0)" "$M"
  chk "$B en GitHub = el hash medido" "$(remota "$B")" "$B_HASH"
  chk "$B local y su copia de origin" "$(g rev-parse -q --verify "refs/heads/$B" 2>&1)|$(g rev-parse -q --verify "refs/remotes/origin/$B" 2>&1)" "$B_HASH|$B_HASH"
  chk "$B antecesora del merge commit (integrada en 14.0)" "$(g merge-base --is-ancestor "$B_HASH" "$M" 2>/dev/null && echo si || echo no)" si
  chk "$B antecesora de $RAMA (git branch -d la aceptará)" "$(g merge-base --is-ancestor "$B_HASH" HEAD 2>/dev/null && echo si || echo no)" si
  R3973=$(remota "$RAMA")
  echo "   $RAMA en GitHub: ${R3973:0:7} (no se toca)"
  corte "comprobaciones"
  if [ "$MODO" = comprobar ]; then fin "Corte: mira en GitHub que no hay ningún PR abierto desde $B y pega la salida. Después, BORRAR."; exit 0; fi
  echo "== [ALTERA GitHub] borrado de $B con --force-with-lease=$B:${B_HASH:0:7}, a las $(date +%T)"
  g push --force-with-lease="refs/heads/$B:$B_HASH" origin ":refs/heads/$B" 2>&1 | sed 's/^/   /'
  g branch -d "$B" 2>&1 | sed 's/^/   /'
  echo "== Después (solo lectura)"
  chk "$B en GitHub" "$(remota "$B")" ""
  chk "$B local y su copia de origin" "$(g rev-parse -q --verify "refs/heads/$B" 2>/dev/null)|$(g rev-parse -q --verify "refs/remotes/origin/$B" 2>/dev/null)" "|"
  chk "14.0 de GitHub, sin cambios" "$(remota 14.0)" "$M"
  chk "$RAMA de GitHub, sin cambios" "$(remota "$RAMA")" "$R3973"
  chk "repo en $RAMA y limpio" "$(g rev-parse --abbrev-ref HEAD)|$(g status --porcelain | wc -l | tr -d ' ')" "$RAMA|0"
  fin "En GitHub Desktop, «Fetch origin»: $B ya no aparece."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
lk_g "$@"
