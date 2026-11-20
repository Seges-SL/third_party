ld_f0() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD F0"
  BD=liyben_ens_14
  L=~/GitHub/lab_liyben_3973
  MODO=${1:-comprobar}
  case "$MODO" in comprobar|BORRAR) ;; *) echo "Uso: bash ld_f0.sh [comprobar|BORRAR]"; exit 1 ;; esac
  pg() { docker exec -i odoo-dev-14-db-1 psql -U odoo -d postgres -X -q -At 2>&1; }
  mkdir -p "$DE" && chmod 700 "$DE" || exit 1
  O=$(nueva "$DE/f0-$MODO" .txt) || exit 1
  {
  echo "== $TANDA ($MODO; equipo: borrado de la copia del ensayo $BD, tras el commit del documento): $(date '+%F %T')"
  echo "== 1. Comprobaciones previas (solo lectura)"
  chk "web del kit parado" "$(docker ps --format '{{.Names}}' | grep -cE '^odoo-dev-14-web' || true)" 0
  chk "PostgreSQL del kit en marcha (si no: cd $L && odoo-dev 14 bd-lista)" "$(docker ps --format '{{.Names}}' | grep -cx odoo-dev-14-db-1 || true)" 1
  chk "carpeta del laboratorio $L" "$(test -d "$L" && echo si || echo no)" si
  corte "comprobaciones previas"
  chk "$BD existe" "$(pg <<< "SELECT count(*) FROM pg_database WHERE datname = '$BD';")" 1
  chk "conexiones abiertas a $BD (pg_stat_activity)" "$(pg <<< "SELECT count(*) FROM pg_stat_activity WHERE datname = '$BD';")" 0
  chk "el documento está en el repo (docs/pendiente/liyben_3973.md en HEAD)" "$(git -C ~/GitHub/third_party cat-file -e HEAD:docs/pendiente/liyben_3973.md 2>/dev/null && echo si || echo no)" si
  corte "compuertas"
  if [ "$MODO" = BORRAR ]; then
    echo "== 2. [BORRA $BD y su filestore] odoo-dev 14 bd-borrar $BD (en la terminal no pregunta)"
    ( cd "$L" && odoo-dev 14 bd-borrar "$BD" ) < /dev/null 2>&1 | sed 's/^/   /'
    chk "$BD ya no existe" "$(pg <<< "SELECT count(*) FROM pg_database WHERE datname = '$BD';")" 0
    fin
  else
    fin "Corte: si todo es OK, lanza bash ld_f0.sh BORRAR."
  fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_f0 "$@"
