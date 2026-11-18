#!/usr/bin/env bash
# Pruebas con toda la rama, D43 (17/11/2026): la «siguiente pasada» de P-2.
# Lanza a mano los dos crons de NUEVO-2 (pns_ai_mcp.ir_cron_ai_fetch_cache_gc y
# pns_ai_mcp.ir_cron_ai_api_result_cache_gc) con method_direct_trigger()
# (odoo/addons/base/models/ir_cron.py:80-85 de la imagen: ejecuta la acción como
# el usuario del cron y escribe lastcall), cada uno en su savepoint, y hace
# commit. Con el código antiguo (model.gc_expired()) safe_eval falla con
# ValueError (odoo/tools/safe_eval.py:347); con el corregido, no.
# Después cuenta «ValueError» en la salida del shell, que guarda en
# ~/odoo-dev/14.0/logs/rama_crons-<bd>-<fecha>.log: esperado 0.
#
# ESCRIBE en la BD indicada (tras «s/N»): lo que hagan los dos GC (borrar filas
# caducadas de las cachés) y lastcall de los dos crons. Nada más.
#
# Uso: bash rama_crons.sh --bd <bd>
#      (contexto de odoo-dev 14: lab_pns_ai_3973, la rama; contenedor web parado)
# Códigos: 0 los dos crons sin error y 0 ValueError; 1 algún cron falló, hay
# ValueError o el shell no terminó (lo que no llegó al commit no queda escrito);
# 10 respuesta distinta de «s»; 11 web en marcha o docker no responde;
# 12 argumentos no válidos; 13 falta la carpeta del laboratorio; 14 el contexto
# activo no es lab_pns_ai_3973.
set -uo pipefail

LAB_NOMBRE=lab_pns_ai_3973
LAB=~/GitHub/$LAB_NOMBRE
ESTADO=~/odoo-dev/14.0/estado
BD=
while [ $# -gt 0 ]; do
    case "$1" in
        --bd) [ $# -ge 2 ] || { echo "Falta el valor de --bd."; exit 12; }; BD=$2; shift 2 ;;
        *) echo "Argumento no válido: $1"; exit 12 ;;
    esac
done
[[ "$BD" =~ ^[a-z0-9_]+$ ]] || { echo "Uso: rama_crons.sh --bd <bd>"; exit 12; }
cd "$LAB" 2>/dev/null || { echo "No existe $LAB."; exit 13; }
[ "$(sed -n 's/^REPO=//p' "$ESTADO" 2>/dev/null)" = "$LAB" ] || {
    echo "El contexto activo de odoo-dev 14 no es $LAB_NOMBRE (ver $ESTADO): no se hace nada."; exit 14; }
NOMBRES=$(docker ps --format '{{.Names}}' 2>/dev/null) || { echo "«docker ps» no responde."; exit 11; }
if printf '%s\n' "$NOMBRES" | grep -qx 'odoo-dev-14-web-1'; then
    echo "El contenedor odoo-dev-14-web-1 está en marcha: primero «Al acabar» y «odoo-dev 14 parar»."; exit 11
fi
read -rp "Esto ESCRIBE en $BD: lanza los dos crons de NUEVO-2 (GC de cachés y lastcall) y hace commit. ¿Seguir? (s/N) " RESP
[ "$RESP" = "s" ] || { echo "No se lanza nada."; exit 10; }

mkdir -p ~/odoo-dev/14.0/logs
LOG_CRONS=~/odoo-dev/14.0/logs/rama_crons-$BD-$(date +%Y%m%d-%H%M%S).log
{ printf 'BD = "%s"\n' "$BD"; cat <<'PY'; } | odoo-dev 14 shell --bd "$BD" > "$LOG_CRONS" 2>&1
import json

CRONS = ('pns_ai_mcp.ir_cron_ai_fetch_cache_gc', 'pns_ai_mcp.ir_cron_ai_api_result_cache_gc')
if env.cr.dbname != BD:
    print('RAMA ERROR: la BD del shell no es ' + BD)
    raise SystemExit(1)
bien = 0
for x in CRONS:
    cron = env.ref(x, raise_if_not_found=False)
    if not cron:
        print('RAMA CRON %s: NO EXISTE' % x)
        continue
    print('RAMA CRON %s: code %s' % (x, json.dumps((cron.code or '').strip())))
    try:
        with env.cr.savepoint():
            cron.method_direct_trigger()
        bien += 1
        print('RAMA CRON %s: sin error' % x)
    except Exception as e:  # solo el tipo: el mensaje puede llevar datos
        print('RAMA CRON %s: falló con %s' % (x, type(e).__name__))
env.cr.commit()
print('RAMA CRONS sin error %d de %d (commit hecho)' % (bien, len(CRONS)))
PY
grep "^RAMA " "$LOG_CRONS"
N_VALUE=$(grep -c 'ValueError' "$LOG_CRONS")
echo "ValueError en la salida del shell: $N_VALUE (previsto 0 en una pasada normal) · salida guardada: $(basename "$LOG_CRONS") (no se copia a la documentación)"
if grep -qx 'RAMA CRONS sin error 2 de 2 (commit hecho)' "$LOG_CRONS" && [ "$N_VALUE" = 0 ]; then
    echo "Resultado: OK"; exit 0
fi
grep -q '^RAMA CRONS ' "$LOG_CRONS" || echo "El shell no llegó al commit: no queda nada escrito. Errores, solo el tipo: $(grep -oE '^[A-Za-z_.]+(Error|Exception)' "$LOG_CRONS" | sort -u | paste -sd, -)"
echo "Resultado: FALLO"; exit 1
