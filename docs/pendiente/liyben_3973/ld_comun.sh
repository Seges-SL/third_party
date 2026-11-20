# Funciones comunes de las tandas del despliegue en LIYBEN (ld_*.sh). No se lanza: lo cargan las tandas con «.».
# Rutas del VPS (I0, 19/11/2026) y del equipo de Sergio.
LD=/tmp/liyben_3973
DE=~/pns_ai_3973/liyben/despliegue
COMPOSE=/opt/odoo
CLON=/opt/odoo/addons/custom/third_party
LOGF=/opt/odoo/logs/odoo-server.log
FS=/opt/odoo/odoo-web-data/.local/share/Odoo/filestore/LIYBEN
RAMA_ANTES=14.0-pns-ai-3
COMMIT_ANTES=578859b
RAMA=14.0-pns-ai-3973
ARBOL_RAMA="688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
VERS_RAMA="pns_ai_chatboo|installed|14.0.2.1.587 pns_ai_mcp|installed|14.0.3.1.973 pns_base|installed|14.0.1.2.69"
F=0
chk() {
  if [ "$2" = "$3" ]; then echo "OK      $1"
  elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
  else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
}
una() { tr '\n' ' ' | sed 's/ *$//'; }
sec() { printf '%s\n' "$1" | awk -v s="## $2" '/^## /{p = ($0 == s); next} p'; }
corte() { [ "$F" = 0 ] || { echo "== $TANDA: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
fin() { if [ "$F" = 0 ]; then echo "== $TANDA: TODO OK.${1:+ $1}"; else echo "== $TANDA: $F FALLO(S). No sigas: pega la salida."; fi; }
# PostgreSQL de LIYBEN en el VPS, sesión forzada a solo lectura (como I0)
lysql() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_db \
    sh -c 'psql -U "$POSTGRES_USER" -d LIYBEN -X -q -At -F "|"' 2>&1; }
# git del clon sin escribir (como ubuntu) y git que escribe (como el UID 101, §3.2 de la instalación)
g() { git --no-optional-locks -c safe.directory="$CLON" -C "$CLON" "$@"; }
g101() { sudo -n -u messagebus env HOME=/tmp git -c safe.directory="$CLON" -C "$CLON" "$@"; }
# archivos y huella de los tres pns_* de una carpeta (como E0 y T0 del staging)
arbol() {
  ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l ) | tr -d ' '
  ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 \
      | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1 )
}
web() { ( cd "$COMPOSE" && docker compose ps --status running --services 2>/dev/null | grep -cx web || true ); }
# última salida de una tanda (por nombre) y si termina con su marca
ultima() { ls -t $1 2>/dev/null | head -1; }
marca() { if [ -n "$1" ] && [ -f "$1" ]; then grep -cx -- "$2" "$1" || true; else echo 0; fi; }
# nombre de salida nuevo, sin pisar ninguno
nueva() { local o="$1-$(date +%Y%m%d-%H%M%S)$2"; [ ! -e "$o" ] || { echo "Ya existe $o: vuelve a lanzarla dentro de un segundo" >&2; return 1; }; printf '%s' "$o"; }
