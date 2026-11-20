ld_f2() (
  set -u
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD F2"
  HL=${1:-}
  [ "$(cd "$(dirname "$0")" && pwd)" = "$LD" ] || { echo "Lánzala desde $LD: bash $LD/ld_f2.sh <huella de F1>"; exit 1; }
  printf '%s' "$HL" | grep -qxE '[0-9a-f]{64}' || { echo "Uso: bash $LD/ld_f2.sh <huella de la lista que da F1>"; exit 1; }
  echo "== $TANDA (VPS: borra $LD, ya copiada al equipo por F1): $(date -u '+%F %T') UTC"
  echo "== 1. Comprobaciones previas"
  chk "huella de la lista de $LD = la de F1" "$(cd "$LD" && find . -maxdepth 1 -type f -printf '%f\n' | LC_ALL=C sort | xargs -d '\n' sha256sum | sha256sum | cut -d' ' -f1)" "$HL"
  chk "web en marcha" "$(web)" 1
  corte "comprobaciones previas"
  echo "== 2. [BORRA $LD]"
  rm -rf -- "$LD"
  chk "$LD borrada" "$(test -e "$LD" && echo existe || echo no)" no
  chk "código montado intacto (rama y árbol)" "$(g rev-parse --abbrev-ref HEAD)|$(arbol "$CLON" | una)" "$RAMA|$ARBOL_RAMA"
  df -h / | tail -1 | sed 's/^/   disco: /'
  fin
)
ld_f2 "$@"
