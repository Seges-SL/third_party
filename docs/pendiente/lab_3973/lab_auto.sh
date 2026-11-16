#!/usr/bin/env bash
# Laboratorio automatizado de lab_pns_ai_3973 (procedimiento fijo:
# docs/pendiente/lab_procedimiento_3973.md). Arranca, entra con Chrome
# headless, hace C tras la entrada, visita las rutas y, pase lo que pase
# (también con Ctrl+C o un error), guarda el log, hace C sobre él y para.
#
# Uso (desde cualquier carpeta):
#   lab_auto.sh <salida> [--descarga RUTA]... RUTA...
# Requiere LAB_LOGIN y LAB_PASSWORD exportadas. «Antes de arrancar» (estado y
# bd-lista) se hace a mano antes de lanzarlo.
set -uo pipefail

AQUI=$(cd "$(dirname "$0")" && pwd)
LAB=~/GitHub/lab_pns_ai_3973
SALIDA=${1:?Uso: lab_auto.sh <carpeta de salida> [--descarga RUTA]... RUTA...}
shift
: "${LAB_LOGIN:?Exporta LAB_LOGIN}"
: "${LAB_PASSWORD:?Exporta LAB_PASSWORD}"
mkdir -p "$SALIDA"
cd "$LAB" || exit 1

read -rp "¿«odoo-dev 14 estado» mostró el contenedor web PARADO? (s/N) " RESP
[ "$RESP" = "s" ] || { echo "No se arranca: primero «Al acabar» del laboratorio anterior."; exit 1; }

HECHO=0
al_acabar() {
    [ "$HECHO" = 1 ] && return
    HECHO=1
    echo
    echo "== Al acabar: guardar el log, C y parar"
    LOG_LAB=~/odoo-dev/14.0/logs/servidor-$(date +%Y%m%d-%H%M%S).log
    odoo-dev 14 log all > "$LOG_LAB" && wc -l "$LOG_LAB"
    python3 -I "$AQUI/lab_cdp.py" c < "$LOG_LAB"
    odoo-dev 14 parar
    echo "Log guardado: $(basename "$LOG_LAB") (no se imprime ni se copia a la documentación)"
}
trap al_acabar EXIT
trap 'exit 130' INT TERM

echo "== Arranque"
odoo-dev 14 arrancar || exit 1
python3 -I "$AQUI/lab_cdp.py" navegar --salida "$SALIDA" "$@"
CODIGO=$?
echo "lab_cdp.py terminó con el código $CODIGO (0 bien, 1 incidencias, 2 abortado)"
exit "$CODIGO"
