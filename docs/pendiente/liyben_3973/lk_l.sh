lk_l() (
  # Limpieza final (punto 4, D69), equipo, sin red: K5 (copia de Y1), K6 (tandas/ del ensayo, iguales a las del repo) y
  # K7 (laboratorio lab_liyben_3973 y su imagen). Las copias de L3 se conservan (K5: LIYBEN no tiene copia fuera del VPS).
  #   comprobar  (solo lectura)
  #   BORRAR     [BORRA] la copia de Y1, las 15 tandas de tandas/ (y la carpeta), ~/GitHub/lab_liyben_3973 y la imagen
  # Antes: el contexto de odoo-dev 14 ya no es lab_liyben_3973 (arrancar de lab_pns_ai_3973 y «Al acabar corto»).
  # Uso: bash ~/Descargas/lk_l.sh comprobar | BORRAR
  set -u
  umask 077
  MODO=${1:-}
  TANDA="LK L $MODO"
  LY=~/pns_ai_3973/liyben
  DL=$LY/limpieza
  REPO=~/GitHub/third_party
  LAB=~/GitHub/lab_liyben_3973
  IMG=odoo-dev:14-lab_liyben_3973
  ESTADO=~/odoo-dev/14.0/estado
  Y1=$LY/LIYBEN-20261119-124423.dump
  Y1_SHA=cb6ebff73e4d0e39030efbceccf5e2f2cf57474e8ea1b3484a2e4b4245418d30
  Y1_TAM=49307121
  L3="LIYBEN-antes-20261120-114331.dump|49300282 LIYBEN-filestore-antes-20261120-114331.tar|567234560"
  TANDAS="ly_e0.sh ly_i0.sh ly_rehacer.sh ly_y0.sh ly_y0b.sh ly_y0c.sh ly_y0r.sh ly_y1.sh ly_y2a.sh ly_y2b.sh ly_y3.sh ly_y4.sh ly_y5.sh ly_y6.sh ly_y7.sh"
  DOCKERFILE_SHA=7961c769ef8f7627e771723ad5d028ff7b12d4cd009c65fc330396a42412cd50
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  una() { tr '\n' ' ' | sed 's/ *$//'; }
  corte() { [ "$F" = 0 ] || { echo "== $TANDA: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  fin() { if [ "$F" = 0 ]; then echo "== $TANDA: TODO OK.${1:+ $1}"; else echo "== $TANDA: $F FALLO(S). No sigas: pega la salida."; fi; }
  l3() { for x in $L3; do printf '%s|%s\n' "${x%%|*}" "$(stat -c '%s|%a' "$LY/despliegue/${x%%|*}" 2>&1)"; done | una; }
  l3_esp() { for x in $L3; do printf '%s|%s|600\n' "${x%%|*}" "${x#*|}"; done | una; }
  otras_img() { docker image ls --format '{{.Repository}}:{{.Tag}} {{.ID}}' 2>&1 | grep -vx "$IMG .*" | LC_ALL=C sort; }
  lab_archivos() { ( cd "$LAB" 2>/dev/null && find . -path ./.git -prune -o -type f -print | LC_ALL=C sort | una ); }
  case "$MODO" in comprobar|BORRAR) ;; *) echo "Uso: bash $0 comprobar | BORRAR"; exit 1 ;; esac
  mkdir -p "$DL" && chmod 700 "$DL" || exit 1
  O="$DL/lk_l-$MODO-$(date +%Y%m%d-%H%M%S).txt"
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== $TANDA (equipo, limpieza final: K5, K6 y K7): $(date '+%F %T')"
  if [ "$MODO" = BORRAR ]; then
    UC=$(ls -t "$DL"/lk_l-comprobar-*.txt 2>/dev/null | head -1)
    chk "último comprobar (${UC##*/}) con TODO OK" "$( [ -n "$UC" ] && grep -cx "== LK L comprobar: TODO OK. Corte: pega la salida. Después, BORRAR." "$UC" || echo 0)" 1
  fi
  echo "== K5. Copias de LIYBEN"
  chk "copia de Y1 ($(basename "$Y1")): tamaño" "$(stat -c %s "$Y1" 2>&1)" "$Y1_TAM"
  chk "copia de Y1: SHA-256" "$(sha256sum "$Y1" 2>/dev/null | cut -d' ' -f1)" "$Y1_SHA"
  chk "copias de L3 (se conservan): nombre, tamaño y permisos" "$(l3)" "$(l3_esp)"
  echo "== K6. Tandas del ensayo fuera del repo ($LY/tandas)"
  chk "archivos de tandas/" "$(cd "$LY/tandas" 2>/dev/null && ls -A | LC_ALL=C sort | una)" "$(printf '%s\n' $TANDAS | LC_ALL=C sort | una)"
  N=0; for f in $TANDAS; do
    [ "$(git hash-object "$LY/tandas/$f" 2>/dev/null)" = "$(git -C "$REPO" rev-parse -q --verify "HEAD:docs/pendiente/liyben_3973/$f" 2>/dev/null)" ] && N=$((N + 1))
  done
  chk "tandas iguales byte a byte a las del commit HEAD del repo" "$N" 15
  echo "== K7. Laboratorio $LAB e imagen $IMG"
  R=$(sed -n 's/^REPO=//p' "$ESTADO" 2>/dev/null)
  chk "contexto activo de odoo-dev 14 ($R): no es lab_liyben_3973" "$( [ -n "$R" ] && [ "$R" != "$LAB" ] && echo otro || echo "lab_liyben_3973 o sin contexto")" otro
  chk "web del kit parado" "$(docker ps --format '{{.Names}}' | grep -c '^odoo-dev-14-web' || true)" 0
  chk "archivos del laboratorio (sin .git)" "$(lab_archivos)" "./.odoo-dev.conf ./CLAUDE.md ./infra/Dockerfile.14"
  chk "infra/Dockerfile.14 = Dockerfile.14.lab_liyben del repo" "$(sha256sum "$LAB/infra/Dockerfile.14" 2>/dev/null | cut -d' ' -f1)|$(sha256sum "$REPO/docs/pendiente/liyben_3973/Dockerfile.14.lab_liyben" 2>/dev/null | cut -d' ' -f1)" "$DOCKERFILE_SHA|$DOCKERFILE_SHA"
  chk "laboratorio sin remoto" "$(git -C "$LAB" remote 2>&1 | una)" ""
  chk "imagen $IMG existe" "$(docker image inspect -f ok "$IMG" 2>/dev/null || echo no)" ok
  chk "contenedores (también parados) con la imagen" "$(docker ps -a --filter ancestor="$IMG" --format '{{.Names}}' 2>&1 | una)" ""
  if docker ps --format '{{.Names}}' | grep -qx odoo-dev-14-db-1; then
    chk "BD lab_liyben_3973_14 (no llegó a crearse)" "$(docker exec odoo-dev-14-db-1 psql -U odoo -d postgres -X -At -c "SELECT count(*) FROM pg_database WHERE datname = 'lab_liyben_3973_14'" 2>&1)" 0
  else echo "INFO    PostgreSQL del kit parado: la BD lab_liyben_3973_14 no se mira (no existía a las 14:46)"; fi
  otras_img > "$DL/.otras_img"
  corte "comprobaciones"
  if [ "$MODO" = comprobar ]; then
    cp "$DL/.otras_img" "$DL/otras_imagenes.txt"
    fin "Corte: pega la salida. Después, BORRAR."; exit 0
  fi
  chk "las demás imágenes = las de comprobar" "$(cat "$DL/.otras_img")" "$(cat "$DL/otras_imagenes.txt" 2>&1)"
  corte "imágenes"
  echo "== [BORRA] copia de Y1, tandas/, $LAB e imagen $IMG, a las $(date +%T)"
  rm -f -- "$Y1"
  for f in $TANDAS; do rm -f -- "$LY/tandas/$f"; done; rmdir -- "$LY/tandas"
  rm -rf -- "$LAB"
  docker image rm "$IMG" 2>&1 | sed 's/^/   /'
  echo "== Después (solo lectura)"
  chk "copia de Y1 borrada" "$(test -e "$Y1" && echo existe || echo no)" no
  chk "tandas/ borrada" "$(test -e "$LY/tandas" && echo existe || echo no)" no
  chk "$LAB borrada" "$(test -e "$LAB" && echo existe || echo no)" no
  chk "imagen $IMG borrada" "$(docker image inspect -f ok "$IMG" 2>/dev/null || echo no)" no
  chk "las demás imágenes, sin cambios" "$(otras_img)" "$(cat "$DL/otras_imagenes.txt")"
  chk "copias de L3, intactas" "$(l3)" "$(l3_esp)"
  rm -f -- "$DL/.otras_img"
  du -sh "$LY" 2>/dev/null | sed 's/^/   ocupa ahora: /'
  fin "Siguiente: lk_g.sh comprobar (rama 14.0-pns-ai-3 de GitHub)."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
lk_l "$@"
