ld_f1() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD F1"
  [ -n "${VPS_PORT:-}" ] && [ -n "${VPS_DEST:-}" ] || { echo "Faltan VPS_PORT y VPS_DEST: lánzalas con la línea read de antes"; exit 1; }
  vps() { ssh -T -p "$VPS_PORT" "$VPS_DEST" "$@"; }
  V="$DE/vps"
  O=$(nueva "$DE/f1" .txt) || exit 1
  {
  echo "== $TANDA (equipo: copia de las salidas de $LD del VPS a $V; en el VPS no escribe nada): $(date '+%F %T')"
  echo "== 1. Comprobaciones previas"
  chk "$V no existe aún" "$(test -e "$V" && echo existe || echo no)" no
  chk "en el VPS: última L8 con TODO OK" "$(vps "grep -cx '== LD L8: TODO OK. Sigue con F1 (equipo).' \$(ls -t $LD/l8-*.txt | head -1)" 2>&1)" 1
  corte "comprobaciones previas"
  R=$(vps "cd $LD && find . -maxdepth 1 -type f -printf '%f\n' | LC_ALL=C sort | xargs -d '\n' sha256sum" 2>&1)
  echo "archivos en el VPS: $(printf '%s\n' "$R" | grep -c . || true)"
  echo "== 2. [ALTERA solo $V] scp"
  mkdir -m 700 "$V" || exit 1
  scp -q -P "$VPS_PORT" "$VPS_DEST:$LD/*" "$V/"
  chk "scp" "$?" 0
  chk "huellas de la copia = las del VPS" "$(cd "$V" && find . -maxdepth 1 -type f -printf '%f\n' | LC_ALL=C sort | xargs -d '\n' sha256sum)" "$R"
  chk "archivos de la copia sin permisos para otros" "$(find "$V" -type f -perm /077 | wc -l | tr -d ' ')" 0
  HL=$(printf '%s\n' "$R" | sha256sum | cut -d' ' -f1)
  echo "huella de la lista (para F2): $HL"
  fin "Sigue con F2 en el VPS: bash $LD/ld_f2.sh $HL"
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_f1
