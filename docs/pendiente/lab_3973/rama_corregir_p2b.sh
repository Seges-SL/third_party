#!/usr/bin/env bash
# Pruebas con toda la rama, P-2 (b): corrección a mano de los dos crons de
# NUEVO-2 en una BD que llegó a 3.1.973 sin el parche 35 (el post-migrate no se
# ejecuta en el -u a la rama porque la versión ya es 3.1.973).
# Hace lo mismo que pns_ai_mcp/migrations/14.0.3.1.973/post-migrate.py, y nada
# más: busca los crons por XML ID (:20-23 y :31), compara el code con strip()
# (:35, D35) y solo si es exactamente OLD_CODE = 'model.gc_expired()' (:18)
# escribe NEW_CODE = 'model._gc_expired()' (:19) con el ORM, cron.write (:41,
# D37). Un code distinto de los dos no se toca.
#
# Primero muestra el code de los dos crons (solo lectura) y después, tras
# «s/N», escribe y hace commit.
#
# Uso: bash rama_corregir_p2b.sh --bd lab_p2b_879_14
#      (contexto de odoo-dev 14: lab_pns_ai_3973; contenedor web parado)
# Códigos: 0 corregidos (o ya estaban bien); 1 no se corrigió (nada escrito) o
# un code inesperado; 10 respuesta distinta de «s»; 11 web en marcha o docker no
# responde; 12 argumentos no válidos; 13 falta la carpeta del laboratorio;
# 14 el contexto activo no es lab_pns_ai_3973.
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
[ "$BD" = lab_p2b_879_14 ] || { echo "Uso: rama_corregir_p2b.sh --bd lab_p2b_879_14 (solo el caso b)"; exit 12; }
cd "$LAB" 2>/dev/null || { echo "No existe $LAB."; exit 13; }
[ "$(sed -n 's/^REPO=//p' "$ESTADO" 2>/dev/null)" = "$LAB" ] || {
    echo "El contexto activo de odoo-dev 14 no es $LAB_NOMBRE (ver $ESTADO): no se hace nada."; exit 14; }
NOMBRES=$(docker ps --format '{{.Names}}' 2>/dev/null) || { echo "«docker ps» no responde."; exit 11; }
if printf '%s\n' "$NOMBRES" | grep -qx 'odoo-dev-14-web-1'; then
    echo "El contenedor odoo-dev-14-web-1 está en marcha: primero «Al acabar» y «odoo-dev 14 parar»."; exit 11
fi

COMUN=$(cat <<'PY'
import json

# Los mismos valores que pns_ai_mcp/migrations/14.0.3.1.973/post-migrate.py:18-23.
OLD_CODE = 'model.gc_expired()'
NEW_CODE = 'model._gc_expired()'
CRON_XMLIDS = (
    'pns_ai_mcp.ir_cron_ai_fetch_cache_gc',
    'pns_ai_mcp.ir_cron_ai_api_result_cache_gc',
)
if env.cr.dbname != BD:
    print('RAMA ERROR: la BD del shell no es ' + BD)
    raise SystemExit(1)
crons = {}
for xmlid in CRON_XMLIDS:
    cron = env.ref(xmlid, raise_if_not_found=False)
    if not cron or cron._name != 'ir.cron':
        print('RAMA ERROR: %s no existe' % xmlid)
        raise SystemExit(1)
    code = (cron.code or '').strip()
    print('RAMA %s: code %s' % (xmlid, json.dumps(code)))
    if code not in (OLD_CODE, NEW_CODE):
        print('RAMA ERROR: %s tiene un code inesperado; no se toca' % xmlid)
        raise SystemExit(1)
    crons[xmlid] = (cron, code)
print('RAMA por corregir: %d' % sum(1 for _c, code in crons.values() if code == OLD_CODE))
PY
)

LECTURA=$({ printf 'BD = "%s"\n' "$BD"; echo "$COMUN"; } | odoo-dev 14 shell --bd "$BD" 2>&1)
echo "$LECTURA" | grep '^RAMA ' || echo "Sin líneas «RAMA»: el shell no ejecutó el script."
echo "$LECTURA" | grep -q '^RAMA ERROR' && exit 1
echo "$LECTURA" | grep -q '^RAMA por corregir: ' || { echo "La lectura no terminó (nada escrito)."; exit 1; }
if echo "$LECTURA" | grep -qx 'RAMA por corregir: 0'; then
    echo "Los dos crons ya tienen model._gc_expired(): no hay nada que corregir."; exit 0
fi
read -rp "Esto ESCRIBE en $BD: pone model._gc_expired() en los crons que tienen model.gc_expired() y hace commit. ¿Seguir? (s/N) " RESP
[ "$RESP" = "s" ] || { echo "No se corrige nada."; exit 10; }

SALIDA=$({ printf 'BD = "%s"\n' "$BD"; echo "$COMUN"; cat <<'PY'; } | odoo-dev 14 shell --bd "$BD" 2>&1
hechos = 0
for xmlid, (cron, code) in crons.items():
    if code == OLD_CODE:
        cron.write({'code': NEW_CODE})
        hechos += 1
env.cr.commit()
print('RAMA CORREGIDOS %d; ahora: %s' % (hechos, ', '.join(
    '%s %s' % (x, json.dumps((env.ref(x).code or '').strip())) for x in CRON_XMLIDS)))
PY
)
echo "$SALIDA" | grep '^RAMA \(ERROR\|CORREGIDOS\)' || echo "Sin línea «RAMA»: el shell no ejecutó el script."
echo "$SALIDA" | grep -q '^RAMA CORREGIDOS ' && exit 0
echo "No se corrigió (nada escrito). Errores del shell, solo el tipo: $(echo "$SALIDA" | grep -oE '^[A-Za-z_.]+(Error|Exception)' | sort -u | paste -sd, -)"
exit 1
