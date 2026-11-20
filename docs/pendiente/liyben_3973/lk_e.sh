lk_e() (
  # Limpieza final (punto 4, D69), equipo. Cada modo abre UNA sola conexión SSH (límite de conexiones del VPS):
  #   enviar            [ALTERA el VPS: crea /tmp/liyben_limpieza (700)] copia lk_v.sh y comprueba su huella allí.
  #   actualizar        [ALTERA el VPS: solo $LK/lk_v.sh] sustituye la versión anterior de lk_v.sh (la v3) por esta,
  #                     sin tocar las salidas ni la foto (D69, v4). Exige que en el VPS esté la v3.
  #   recoger <huella>  [ALTERA solo $DL/vps] trae /tmp/liyben_limpieza entera (salidas y salvar/) y exige que la
  #                     huella de la lista copiada sea la que dio «lk_v.sh lista» en el VPS. En el VPS no escribe.
  #                     Solo con TODO OK da el código que exige «lk_v.sh BORRAR».
  # Uso: bash ~/Descargas/lk_e.sh enviar | recoger <huella> (con VPS_PORT y VPS_DEST exportados, línea read de §1).
  set -u
  umask 077
  MODO=${1:-}
  TANDA="LK E $MODO"
  D=$(cd "$(dirname "$0")" && pwd)
  DL=~/pns_ai_3973/liyben/limpieza
  LK=/tmp/liyben_limpieza
  LKV_SHA=afa44c94e582544125634ca567383e4cb7bb4de3560e296ae48bc3db6faf817b
  LKV_SHA_ANTES=6f2b98815b259045dc5caeaef921fe8a3f3a105172b276bc67d7121105818841
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  corte() { [ "$F" = 0 ] || { echo "== $TANDA: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  fin() { if [ "$F" = 0 ]; then echo "== $TANDA: TODO OK.${1:+ $1}"; else echo "== $TANDA: $F FALLO(S). No sigas: pega la salida."; fi; }
  case "$MODO" in enviar|actualizar|recoger) ;; *) echo "Uso: bash $0 enviar | actualizar | recoger <huella>"; exit 1 ;; esac
  [ -n "${VPS_PORT:-}" ] && [ -n "${VPS_DEST:-}" ] || { echo "Faltan VPS_PORT y VPS_DEST: lánzalas con la línea read de §1"; exit 1; }
  HL=${2:-}
  if [ "$MODO" = recoger ]; then printf '%s' "$HL" | grep -qxE '[0-9a-f]{64}' || { echo "Uso: bash $0 recoger <huella que da lk_v.sh lista>"; exit 1; }; fi
  mkdir -p "$DL" && chmod 700 "$DL" || exit 1
  O="$DL/lk_e-$MODO-$(date +%Y%m%d-%H%M%S).txt"
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== $TANDA (equipo, limpieza final): $(date '+%F %T')"
  case "$MODO" in
  enviar)
    chk "lk_v.sh junto a esta tanda (SHA-256)" "$(sha256sum "$D/lk_v.sh" 2>/dev/null | cut -d' ' -f1)" "$LKV_SHA"
    corte "comprobaciones previas"
    echo "== [ALTERA el VPS] $LK (700) con lk_v.sh, en una sola conexión"
    R=$(tar -C "$D" -cf - lk_v.sh | ssh -T -p "$VPS_PORT" "$VPS_DEST" \
      "umask 077; if test -e $LK; then echo YA_EXISTE; exit 0; fi; mkdir -m 700 $LK && tar --no-same-permissions -x -C $LK && chmod 600 $LK/lk_v.sh && echo \"\$(stat -c %a $LK) \$(ls -A $LK | wc -l) \$(sha256sum < $LK/lk_v.sh | cut -d' ' -f1)\"" 2>&1)
    chk "$LK no existía en el VPS" "$(printf '%s\n' "$R" | grep -c YA_EXISTE || true)" 0
    chk "en el VPS: permisos, archivos y huella de lk_v.sh" "$R" "700 1 $LKV_SHA"
    fin "Abre la sesión SSH del VPS: bash $LK/lk_v.sh comprobar"
    ;;
  actualizar)
    chk "lk_v.sh junto a esta tanda (SHA-256)" "$(sha256sum "$D/lk_v.sh" 2>/dev/null | cut -d' ' -f1)" "$LKV_SHA"
    corte "comprobaciones previas"
    echo "== [ALTERA el VPS: solo $LK/lk_v.sh] de la v3 a esta versión, en una sola conexión"
    R=$(tar -C "$D" -cf - lk_v.sh | ssh -T -p "$VPS_PORT" "$VPS_DEST" \
      "umask 077; H=\$(sha256sum < $LK/lk_v.sh 2>/dev/null | cut -d' ' -f1); if [ \"\$H\" != $LKV_SHA_ANTES ]; then echo \"NO_ES_V3 \$H\"; exit 0; fi; T=\$(mktemp -d $LK/.nueva.XXXXXX) && tar --no-same-permissions -x -C \$T && chmod 600 \$T/lk_v.sh && mv -f \$T/lk_v.sh $LK/lk_v.sh && rmdir \$T && echo \"\$(sha256sum < $LK/lk_v.sh | cut -d' ' -f1) \$(stat -c %a $LK/lk_v.sh) \$(ls -A $LK | grep -c '^lk_v-')\"" 2>&1)
    chk "en el VPS estaba la v3 de lk_v.sh" "$(printf '%s\n' "$R" | grep -c NO_ES_V3 || true)" 0
    chk "en el VPS: huella y permisos de lk_v.sh nuevo" "$(printf '%s' "$R" | cut -d' ' -f1-2)" "$LKV_SHA 600"
    echo "   salidas de lk_v en $LK: $(printf '%s' "$R" | cut -d' ' -f3)"
    fin "En la sesión del VPS: bash $LK/lk_v.sh CERT"
    ;;
  recoger)
    V="$DL/vps"
    chk "$V no existe aún" "$(test -e "$V" && echo existe || echo no)" no
    chk "$V.parcial no existe" "$(test -e "$V.parcial" && echo existe || echo no)" no
    corte "comprobaciones previas"
    echo "== [ALTERA solo $V] copia de $LK, en una sola conexión"
    mkdir -m 700 "$V.parcial" || exit 1
    ssh -T -p "$VPS_PORT" "$VPS_DEST" "cd $LK && tar -cf - ." 2>"$DL/.recoger_err" | tar --no-same-permissions -x -C "$V.parcial"
    chk "ssh y tar sin errores" "$(cat "$DL/.recoger_err"; rm -f "$DL/.recoger_err")" ""
    N=$( cd "$V.parcial" && find . -type f | wc -l | tr -d ' ')
    H=$( cd "$V.parcial" && find . -type f -printf '%P\n' | LC_ALL=C sort | xargs -d '\n' sha256sum | sha256sum | cut -d' ' -f1)
    echo "   archivos copiados: $N"
    chk "huella de la lista copiada = la del VPS (lk_v.sh lista)" "$H" "$HL"
    chk "copia sin permisos para otros" "$(find "$V.parcial" -perm /077 ! -type d | wc -l | tr -d ' ')" 0
    chk "salvar/: originales = copias (17 + sitio de Nginx)" "$( cd "$V.parcial/salvar" 2>/dev/null && find pns_staging tmp -type f | LC_ALL=C sort | while read -r f; do printf '%s  %s\n' "$(sha256sum < "$f" | cut -d' ' -f1)" "$f"; done | diff - originales.sha256 >/dev/null && echo iguales || echo distintos)|$(test -f "$V.parcial/salvar/nginx/pns_liyben_com.conf" && echo sitio || echo sin_sitio)" "iguales|sitio"
    corte "copia"
    mv "$V.parcial" "$V" && chmod 700 "$V"
    chk "$V en su sitio" "$(test -d "$V" && echo si || echo no)" si
    CONF=$(printf '%s recogido\n' "$HL" | sha256sum | cut -d' ' -f1)
    [ "$F" = 0 ] && echo "   código para BORRAR: $CONF"
    fin "En la sesión del VPS: bash $LK/lk_v.sh BORRAR $CONF"
    ;;
  esac
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
lk_e "$@"
