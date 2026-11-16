#!/usr/bin/env bash
# Prueba de lab_auto.sh sin Odoo, sin Docker y sin Chrome.
#
# Uso: bash prueba_lab_auto.sh   (en la carpeta de lab_auto.sh y lab_cdp.py)
#
# Ejecuta una copia de lab_auto.sh con HOME en una carpeta temporal y con dos
# dobles: un «odoo-dev» falso en el PATH (no arranca, no para y no lee nada
# real) y un lab_cdp.py falso cuyo «navegar» sale con el código pedido. «c» y
# «rutas» van al lab_cdp.py real. No toca ~/GitHub, ~/odoo-dev ni Docker:
# todo queda en la carpeta temporal, que se borra al acabar.
set -u

AQUI=$(cd "$(dirname "$0")" && pwd)
REAL_CDP="$AQUI/lab_cdp.py"
[ -f "$AQUI/lab_auto.sh" ] && [ -f "$REAL_CDP" ] || { echo "Faltan lab_auto.sh o lab_cdp.py junto a este script."; exit 2; }
T=$(mktemp -d /tmp/prueba_lab_auto.XXXXXX)
trap 'rm -rf "$T"' EXIT

mkdir -p "$T/bin" "$T/scripts" "$T/home/GitHub/lab_pns_ai_3973" "$T/home/odoo-dev/14.0/logs"
cp "$AQUI/lab_auto.sh" "$T/scripts/lab_auto.sh"

# Doble de odoo-dev: anota cada llamada y responde según STUB_*.
cat > "$T/bin/odoo-dev" <<'DOBLE'
#!/usr/bin/env bash
echo "$*" >> "$STUB_LLAMADAS"
case "$2" in
    arrancar) exit "${STUB_ARRANCAR:-0}" ;;
    parar) exit "${STUB_PARAR:-0}" ;;
    log)
        case "${STUB_LOG:-bueno}" in
            bueno) printf 'web-1  | 2026-11-16 10:00:00,001 1 INFO ? odoo: Odoo version 14.0\nweb-1  | 2026-11-16 10:00:01,001 1 INFO lab_pns_ai_3973_14 odoo.modules.loading: loading\n' ;;
            malo) printf 'web-1  | 2026-11-16 10:00:01,001 1 INFO otra_14 odoo.modules.loading: loading\n' ;;
            vacio) : ;;
            falla) exit 1 ;;
        esac ;;
esac
exit 0
DOBLE
chmod +x "$T/bin/odoo-dev"

# Doble de lab_cdp.py: navegar sale con STUB_NAV (y espera STUB_NAV_ESPERA s).
cat > "$T/scripts/lab_cdp.py" <<'DOBLE'
import os, subprocess, sys, time
if sys.argv[1:2] == ['navegar']:
    time.sleep(float(os.environ.get('STUB_NAV_ESPERA', '0')))
    sys.exit(int(os.environ.get('STUB_NAV', '0')))
sys.exit(subprocess.call([sys.executable, '-I', os.environ['REAL_CDP']] + sys.argv[1:]))
DOBLE

FALLOS=0
N=0
# caso <nombre> <código esperado> <¿arranca? s/n> <respuesta> [VAR=valor...] -- [argumentos]
caso() {
    local nombre=$1 esperado=$2 arranca=$3 respuesta=$4
    shift 4
    local vars=()
    while [ $# -gt 0 ] && [ "$1" != "--" ]; do vars+=("$1"); shift; done
    [ "${1:-}" = "--" ] && shift
    : > "$T/llamadas"
    rm -rf "$T/home/salida"
    local salida rc
    salida=$(printf '%s\n' "$respuesta" | env -i PATH="$T/bin:/usr/bin:/bin" HOME="$T/home" \
        REAL_CDP="$REAL_CDP" STUB_LLAMADAS="$T/llamadas" LAB_LOGIN=prueba LAB_PASSWORD=clave \
        "${vars[@]}" bash "$T/scripts/lab_auto.sh" "$@" 2>&1)
    rc=$?
    local ok=1 detalle=""
    [ "$rc" = "$esperado" ] || { ok=0; detalle="código $rc"; }
    if [ "$arranca" = s ]; then
        grep -qx "14 arrancar" "$T/llamadas" && grep -qx "14 parar" "$T/llamadas" \
            && grep -qx "14 log all" "$T/llamadas" || { ok=0; detalle="$detalle; sin arrancar/log/parar"; }
        echo "$salida" | grep -q "^Código final $esperado: " || { ok=0; detalle="$detalle; sin «Código final $esperado»"; }
    else
        [ ! -s "$T/llamadas" ] || { ok=0; detalle="$detalle; llamó a odoo-dev: $(paste -sd, "$T/llamadas")"; }
    fi
    N=$((N + 1))
    if [ "$ok" = 1 ]; then echo "PASA   $nombre → $esperado"; else echo "FALLA  $nombre → $esperado ($detalle)"; FALLOS=$((FALLOS + 1)); fi
}

R=(-- "$T/home/salida" --descarga /chatboo/canvas/8/download /chatboo/canvas/8)
caso "todo bien"                          0 s s STUB_NAV=0 "${R[@]}"
caso "incidencias de medición"            1 s s STUB_NAV=1 "${R[@]}"
caso "navegación bien, log con otra BD"   3 s s STUB_NAV=0 STUB_LOG=malo "${R[@]}"
caso "incidencias y log con otra BD"      3 s s STUB_NAV=1 STUB_LOG=malo "${R[@]}"
caso "log guardado vacío"                 7 s s STUB_NAV=1 STUB_LOG=vacio "${R[@]}"
caso "no se pudo guardar el log"          7 s s STUB_NAV=0 STUB_LOG=falla "${R[@]}"
caso "otra BD pero falla parar"           7 s s STUB_NAV=0 STUB_LOG=malo STUB_PARAR=1 "${R[@]}"
caso "falla parar"                        7 s s STUB_NAV=0 STUB_PARAR=1 "${R[@]}"
caso "el servidor no responde"            4 s s STUB_NAV=4 "${R[@]}"
caso "falla el login"                     5 s s STUB_NAV=5 "${R[@]}"
caso "error de Chrome"                    6 s s STUB_NAV=6 "${R[@]}"
caso "error interno de lab_cdp.py"       20 s s STUB_NAV=20 "${R[@]}"
caso "falla arrancar (log vacío)"        14 s s STUB_ARRANCAR=1 STUB_LOG=vacio "${R[@]}"
caso "falla arrancar (log con otra BD)"   3 s s STUB_ARRANCAR=1 STUB_LOG=malo "${R[@]}"
caso "respuesta distinta de s"           10 n n "${R[@]}"
caso "sin credenciales"                  11 n s LAB_LOGIN= "${R[@]}"
caso "ruta a /web/database"              12 n s -- "$T/home/salida" /web/database/selector
caso "ruta con otra BD"                  12 n s -- "$T/home/salida" "/web/login?db=otra"
caso "sin argumentos"                    12 n s --
caso "falta la carpeta del laboratorio"  13 n s HOME="$T/vacio" "${R[@]}"

# TERM mientras navega: el trap guarda el log, hace C, para y sale con 130.
: > "$T/llamadas"
printf 's\n' | env -i PATH="$T/bin:/usr/bin:/bin" HOME="$T/home" REAL_CDP="$REAL_CDP" \
    STUB_LLAMADAS="$T/llamadas" LAB_LOGIN=prueba LAB_PASSWORD=clave STUB_NAV=0 STUB_NAV_ESPERA=3 \
    bash "$T/scripts/lab_auto.sh" "${R[@]:1}" > "$T/salida_term" 2>&1 &
PID=$!
sleep 1
kill -TERM "$PID"
wait "$PID"
RC=$?
N=$((N + 1))
if [ "$RC" = 130 ] && grep -qx "14 parar" "$T/llamadas" && grep -q "^Código final 130: " "$T/salida_term"; then
    echo "PASA   TERM durante la navegación → 130 (con log, C y parar)"
else
    echo "FALLA  TERM durante la navegación → 130 (código $RC)"; FALLOS=$((FALLOS + 1))
fi

echo
if [ "$FALLOS" = 0 ]; then echo "Prueba de lab_auto.sh: $N PASA"; exit 0; fi
echo "Prueba de lab_auto.sh: $FALLOS FALLA de $N"; exit 1
