ld_e0() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD E0"
  REPO=~/GitHub/third_party
  BASE_DOC=c6ec077
  STAGING=5d0559b
  mkdir -p "$DE" && chmod 700 "$DE" || exit 1
  O=$(nueva "$DE/e0" .txt) || exit 1
  T=$(mktemp -d /tmp/ld_e0.XXXXXX) || exit 1
  trap 'rm -rf -- "$T"' EXIT
  {
  cd "$REPO" || exit 1
  echo "== $TANDA (equipo, solo lectura del repo; extracción temporal en $T, se borra al acabar): $(date '+%F %T')"
  echo "== 1. Repo y commit que se despliega (D58: HEAD de la rama en el commit del documento)"
  chk "rama" "$(git rev-parse --abbrev-ref HEAD)" "$RAMA"
  chk "árbol de trabajo limpio" "$(git status --porcelain | wc -l | tr -d ' ')" 0
  echo "copia local de la remota (haz «Fetch origin» en GitHub Desktop antes): $(git log -1 --format='%h %ci' '@{u}' 2>&1)"
  chk "al día con su rama remota (delante|detrás)" "$(git rev-list --left-right --count 'HEAD...@{u}' 2>&1 | tr '\t' '|')" "0|0"
  C=$(git rev-parse HEAD)
  echo "commit a desplegar: $(git log -1 --format='%H %s' "$C")"
  chk "$BASE_DOC es antecesor del commit" "$(git merge-base --is-ancestor "$BASE_DOC" "$C" && echo si || echo no)" si
  chk "archivos fuera de docs/ que cambian de $BASE_DOC al commit" "$(git diff --name-only "$BASE_DOC" "$C" -- . ':(exclude)docs' | una)" ""
  chk "$COMMIT_ANTES (montado en LIYBEN) es antecesor del commit" "$(git merge-base --is-ancestor "$COMMIT_ANTES" "$C" && echo si || echo no)" si
  corte "repo"

  echo "== 2. Módulos del commit (= $STAGING, lo validado en el staging y en el ensayo)"
  chk "commits posteriores a $STAGING que tocan los módulos" "$(git rev-list --count "$STAGING..$C" -- pns_base pns_ai_mcp pns_ai_chatboo)" 0
  git archive "$C" pns_base pns_ai_mcp pns_ai_chatboo | tar -x -C "$T" || { echo "FALLO   git archive"; F=$((F + 1)); corte "git archive"; }
  chk "árbol de los módulos (archivos y huella)" "$(arbol "$T" | una)" "$ARBOL_RAMA"
  chk "versiones" "$(for m in pns_base pns_ai_mcp pns_ai_chatboo; do grep -oE "'version': *'[^']+'" "$T/$m/__manifest__.py" | grep -oE "[0-9][0-9.]+"; done | una)" "14.0.1.2.69 14.0.3.1.973 14.0.2.1.587"
  DF=$(git diff --no-renames --name-status "$COMMIT_ANTES" "$C" -- pns_ai_mcp/ai pns_ai_chatboo/ai | LC_ALL=C sort)
  chk "cambios en ai/ de $COMMIT_ANTES al commit, por tipo (Y4 A)" "$(printf '%s\n' "$DF" | cut -f1 | LC_ALL=C sort | uniq -c | awk '{printf "%s %s ", $2, $1}' | sed 's/ $//')" "A 15 D 12 M 19"
  chk "huella de esa lista (= la del fabricante de 3.1.782 a 3.1.973)" "$(printf '%s\n' "$DF" | sha256sum | cut -d' ' -f1)" f413c755fcfaf6e0ed7b1f51feb7a62b621323173496d3218f6b43715d8438d4
  chk "archivos fuera de pns_* y docs/ que cambian de $COMMIT_ANTES al commit (el clon de LIYBEN tiene todo third_party)" "$(git diff --name-only "$COMMIT_ANTES" "$C" -- . ':(exclude)pns_base' ':(exclude)pns_ai_mcp' ':(exclude)pns_ai_chatboo' ':(exclude)docs' | una)" "CLAUDE.md"
  corte "módulos"

  echo "== 3. Tandas del despliegue en el commit (docs/pendiente/liyben_3973/)"
  chk "tandas del commit = las de la copia de trabajo" "$(git diff --name-only "$C" -- docs/pendiente/liyben_3973 | wc -l | tr -d ' ')" 0
  printf '%s\n' "$C" > "$DE/commit.txt"
  echo "guardado: $DE/commit.txt ($C)"
  fin "Sigue con E1."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_e0
