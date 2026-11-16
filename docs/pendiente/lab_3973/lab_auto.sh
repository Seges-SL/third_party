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
#
# Códigos de salida (un código por causa; los de 1 a 7, 11, 12 y 20 son los
# de lab_cdp.py):
#    0 todo como se espera            10 respuesta distinta de «s» (no arranca)
#    1 incidencias de medición        11 faltan LAB_LOGIN o LAB_PASSWORD (no arranca)
#    3 otra BD                        12 argumentos o rutas no válidos (no arranca)
#    4 el servidor no responde        13 no existe ~/GitHub/lab_pns_ai_3973 (no arranca)
#    5 falla el login                 14 falla «odoo-dev 14 arrancar»
#    6 error de Chrome (CDP)          20 error interno de lab_cdp.py
#    7 «Al acabar» incompleto        130 Ctrl+C o TERM
# Prioridad si coinciden: 7, después 3, después el código de la navegación.
set -uo pipefail

AQUI=$(cd "$(dirname "$0")" && pwd)
LAB=~/GitHub/lab_pns_ai_3973

motivo() {
    case "$1" in
        0) echo "todo como se espera" ;;
        1) echo "incidencias de medición (detalle por ruta en la salida)" ;;
        3) echo "otra BD (seguir «Si aparece otra BD»)" ;;
        4) echo "el servidor no responde" ;;
        5) echo "falla el login" ;;
        6) echo "error de Chrome (CDP)" ;;
        7) echo "«Al acabar» incompleto (log no guardado, sin líneas de Odoo o falla parar)" ;;
        10) echo "respuesta distinta de «s»: no se arranca" ;;
        11) echo "faltan LAB_LOGIN o LAB_PASSWORD: no se arranca" ;;
        12) echo "argumentos o rutas no válidos: no se arranca" ;;
        13) echo "no existe $LAB: no se arranca" ;;
        14) echo "falla «odoo-dev 14 arrancar»" ;;
        20) echo "error interno de lab_cdp.py" ;;
        130) echo "Ctrl+C o TERM" ;;
        *) echo "código no previsto" ;;
    esac
}

[ $# -ge 1 ] || { echo "Uso: lab_auto.sh <carpeta de salida> [--descarga RUTA]... RUTA..."; exit 12; }
SALIDA=$1
shift
[ -n "${LAB_LOGIN:-}" ] && [ -n "${LAB_PASSWORD:-}" ] || {
    echo "Faltan LAB_LOGIN y LAB_PASSWORD (exportadas en esta terminal)."; exit 11; }
# Las guardas de las rutas, antes de preguntar y de arrancar nada.
python3 -I "$AQUI/lab_cdp.py" rutas "$@"
RC=$?
[ "$RC" = 0 ] || exit "$RC"
mkdir -p "$SALIDA" || exit 12
cd "$LAB" 2>/dev/null || { echo "No existe $LAB."; exit 13; }

read -rp "¿«odoo-dev 14 estado» mostró el contenedor web PARADO? (s/N) " RESP
[ "$RESP" = "s" ] || { echo "No se arranca: primero «Al acabar» del laboratorio anterior."; exit 10; }

HECHO=0
al_acabar() {
    local rc=$?
    [ "$HECHO" = 1 ] && return
    HECHO=1
    local acabar_ok=1 rc_c final
    echo
    echo "== Al acabar: guardar el log, C y parar"
    LOG_LAB=~/odoo-dev/14.0/logs/servidor-$(date +%Y%m%d-%H%M%S).log
    if odoo-dev 14 log all > "$LOG_LAB"; then
        wc -l "$LOG_LAB"
    else
        echo "No se pudo guardar el log."
        acabar_ok=0
    fi
    python3 -I "$AQUI/lab_cdp.py" c < "$LOG_LAB"
    rc_c=$?
    if [ "$rc" = 14 ] && [ "$rc_c" = 7 ]; then
        # Si «arrancar» falló, que el log no tenga líneas de Odoo es lo esperable.
        echo "(Log sin líneas de Odoo tras el fallo de arrancar: no cuenta como «Al acabar» incompleto.)"
        rc_c=0
    fi
    odoo-dev 14 parar || { echo "Falló «odoo-dev 14 parar»."; acabar_ok=0; }
    echo "Log guardado: $(basename "$LOG_LAB") (no se imprime ni se copia a la documentación)"
    final=$rc
    if [ "$acabar_ok" = 0 ] || [ "$rc_c" = 7 ]; then
        final=7
    elif [ "$rc_c" = 3 ]; then
        final=3
    elif [ "$rc_c" != 0 ] && [ "$final" = 0 ]; then
        final=$rc_c
    fi
    echo "Navegación: $rc ($(motivo "$rc")) · C del log guardado: $rc_c"
    echo "Código final $final: $(motivo "$final")"
    exit "$final"
}
trap al_acabar EXIT
trap 'exit 130' INT TERM

echo "== Arranque"
odoo-dev 14 arrancar || exit 14
python3 -I "$AQUI/lab_cdp.py" navegar --salida "$SALIDA" "$@"
CODIGO=$?
echo "lab_cdp.py terminó con el código $CODIGO ($(motivo "$CODIGO"))"
exit "$CODIGO"
