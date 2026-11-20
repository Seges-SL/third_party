ld_e1() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD E1"
  REPO=~/GitHub/third_party
  # Archivos que van al VPS y su SHA-256 (los del commit del documento)
  ESPERADAS='7886e6c4cbbd08412b67eff196a7c6ae36a58e17d5126ecf8620ede02157511d  ld_comun.sh
ccd64ae7c568759ff8e6f9bafb5ff09287f73a39d4bae03bebd81e7614e3abe2  ld_l0.sh
dc6d69e02814f80033035bf2a7a8e2795deed25723c48569c3296b5b2f7a7387  ld_l2.sh
35716b0a7c0e9fff3bce59fdff714ba6c76dc081542b1e41a7677a156c42baa8  ld_l4.sh
2c5a0a06f717ddf1a2297d6931c27c4696dd4df366a8bc87de519f89158f3cfe  ld_l4b.sh
516ada0765906e7510b31d9640e0fd3b24dea59a23b06d918b22c28974fe7295  ld_l5.sh
832597e672eb8eec325f1b98b7f8ded1cb473ff6a5438be7eb71f54691c803e4  ld_l6.sh
9625216112d3954dcd893c299d385083e495f594801389052cf516638e76357c  ld_l8.sh
5b8e59578bc6038d5c545f9bbffb4831132df5ca7ad15d6418f03591ae3560cf  ld_f2.sh
85394c9767b647cefc977c1be57af555a0a5b7c6f0dbb16ddcacfd373eb3cf21  l0_b.sql
26d8194e3cbf43607420c60a312ac91a443e86741f7f33dc3b210c609b3e514c  l0_antes.sql
8b4ee8af026ee5c0117394f54858b9665c2abc5518d6ff11e4046cb2d7ee9c5b  l4b_estado.sql
d8102a5de47136b1d4e26360e0415fb831995afaa471dfd7fb4c7113effb533f  l4b_foto.sql
b7827d7dc172b9ea4caba42061a8276a72777ed61354bbfc293b3a55ed970c98  l4b.py
d58c9f7188422273f4ea1e88aaee88441b474cc6425a4a2dd1a63d5d23110fc0  l6_despues.sql
301a0dd070bc980455d75e4e701bf85f0e9d8036b319b94c5099587cc55a3797  d50_vaciar.sh
4e5939f65f3f414c7070b2d7d612b49d8e120a27f418b81e43f7175a8042284d  ly_i0.sh'
  [ -n "${VPS_PORT:-}" ] && [ -n "${VPS_DEST:-}" ] || { echo "Faltan VPS_PORT y VPS_DEST: lánzalas con la línea read de antes"; exit 1; }
  O=$(nueva "$DE/e1" .txt) || exit 1
  T=$(mktemp -d /tmp/ld_e1.XXXXXX) || exit 1
  trap 'rm -rf -- "$T"' EXIT
  {
  echo "== $TANDA (equipo: copia de las tandas al VPS, en $LD; en el VPS solo crea esa carpeta): $(date '+%F %T')"
  echo "== 1. Comprobaciones previas"
  E0=$(ultima "$DE/e0-*.txt")
  chk "última E0 (${E0##*/}) con TODO OK" "$(marca "$E0" '== LD E0: TODO OK. Sigue con E1.')" 1
  C=$(git -C "$REPO" rev-parse HEAD)
  chk "commit de E0 = HEAD del repo" "$(cat "$DE/commit.txt" 2>/dev/null)" "$C"
  chk "árbol de trabajo limpio" "$(git -C "$REPO" status --porcelain | wc -l | tr -d ' ')" 0
  corte "comprobaciones previas"
  git -C "$REPO" archive "$C" docs/pendiente/liyben_3973 | tar -x -C "$T" || { echo "FALLO   git archive"; F=$((F + 1)); corte "git archive"; }
  S="$T/docs/pendiente/liyben_3973"
  LISTA=$(printf '%s\n' "$ESPERADAS" | awk '{print $2}')
  H=$( cd "$S" && for f in $LISTA; do sha256sum "$f" 2>&1; done )
  chk "huellas de los $(printf '%s\n' "$LISTA" | wc -l | tr -d ' ') archivos del commit = las del documento" "$H" "$ESPERADAS"
  [ "$F" = 0 ] || printf '%s\n' "$H" | sed 's/^/   /'
  corte "huellas"
  cp "$DE/commit.txt" "$S/commit.txt"
  ( cd "$S" && sha256sum $LISTA commit.txt ) > "$T/huellas.txt"

  echo "== 2. [ALTERA el VPS: crea $LD] Copia por scp"
  ssh -T -p "$VPS_PORT" "$VPS_DEST" "test ! -e $LD && mkdir -m 700 $LD" || { echo "FALLO   $LD ya existe en el VPS o no se pudo crear: no se ha copiado nada"; F=$((F + 1)); corte "carpeta en el VPS"; }
  ( cd "$S" && scp -q -P "$VPS_PORT" $LISTA commit.txt "$T/huellas.txt" "$VPS_DEST:$LD/" )
  chk "scp" "$?" 0
  R=$(ssh -T -p "$VPS_PORT" "$VPS_DEST" "cd $LD && chmod 600 * && sha256sum -c --quiet huellas.txt && echo HUELLAS_OK; stat -c %a $LD; ls -1 | wc -l")
  chk "en el VPS: huellas, permisos de $LD y archivos" "$(printf '%s\n' "$R" | una)" "HUELLAS_OK 700 $(( $(printf '%s\n' "$LISTA" | wc -l) + 2 ))"
  echo "huella de la lista copiada: $(sha256sum "$T/huellas.txt" | cut -d' ' -f1)"
  cp "$T/huellas.txt" "$DE/huellas_vps.txt"
  fin "Sigue con L0 en el VPS."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_e1
