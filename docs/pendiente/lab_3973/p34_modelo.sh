#!/usr/bin/env bash
# Laboratorio L2 del parche 34 (17/11/2026): modelo del proveedor 2 («Gemini lab»).
# La cuota gratuita de Gemini es de 20 peticiones al día por modelo: L2 se hace
# con otro modelo del mismo proveedor (decisiones de Sergio del 17/11: primero
# gemini-3.5-flash; después, agotada también, gemini-3.5-flash-lite).
# ai.provider.model_name es related de model_id.name: solo se cambia model_id
# (30 = models/gemini-3.6-flash, el de siempre; 24 = models/gemini-3.5-flash;
# 25 = models/gemini-3.5-flash-lite).
#
# Uso (con el contenedor web parado):
#   bash p34_modelo.sh estado         solo lee: modelo actual del proveedor 2
#   bash p34_modelo.sh poner lite     ESCRIBE: → gemini-3.5-flash-lite
#   bash p34_modelo.sh poner flash    ESCRIBE: → gemini-3.5-flash
#   bash p34_modelo.sh devolver       ESCRIBE: → gemini-3.6-flash (el de siempre)
# Solo cambia desde uno de los tres modelos conocidos.
# Solo toca model_id del proveedor 2: ni roles, ni clave, ni URL. Si ya está en el
# modelo pedido, no escribe.
# Códigos: 0 hecho, ya estaba o estado leído; 1 no se cambió (nada escrito);
# 10 respuesta distinta de «s»; 12 orden no válida; 13 falta la carpeta del laboratorio.
set -uo pipefail

LAB=~/GitHub/lab_pns_ai_3973
CONOCIDOS="models/gemini-3.6-flash models/gemini-3.5-flash models/gemini-3.5-flash-lite"

ORDEN=${1:-}
USO="Uso: bash p34_modelo.sh estado | poner lite | poner flash | devolver"
case "$ORDEN ${2:-}" in
    "estado ") HASTA="" ;;
    "poner lite") HASTA=models/gemini-3.5-flash-lite ;;
    "poner flash") HASTA=models/gemini-3.5-flash ;;
    "devolver ") HASTA=models/gemini-3.6-flash ;;
    *) echo "$USO"; exit 12 ;;
esac
DESDE=$CONOCIDOS
cd "$LAB" 2>/dev/null || { echo "No existe $LAB."; exit 13; }
if [ "$ORDEN" != estado ]; then
    read -rp "Esto ESCRIBE en lab_pns_ai_3973_14: el modelo del proveedor 2 pasa a $HASTA. ¿Seguir? (s/N) " RESP
    [ "$RESP" = "s" ] || { echo "No se cambia."; exit 10; }
fi

SALIDA=$({ printf 'ORDEN = "%s"\nDESDE = "%s"\nHASTA = "%s"\n' "$ORDEN" "$DESDE" "$HASTA"; cat <<'PY'; } | odoo-dev 14 shell 2>&1
def fallo(motivo):
    # Sin commit: no queda nada escrito.
    print('P34 ERROR: ' + motivo)
    raise SystemExit(1)


if env.cr.dbname != 'lab_pns_ai_3973_14':
    fallo('la BD del contexto no es lab_pns_ai_3973_14')
p = env['ai.provider'].browse(2).exists()
if not p or not p.active or p.name != 'Gemini lab':
    fallo('el proveedor 2 no existe, no está activo o no es «Gemini lab»')
if ORDEN == 'estado':
    print('P34 MODELO estado proveedor=2 modelo=%s model_id=%d' % (p.model_id.name or '-', p.model_id.id or 0))
    raise SystemExit(0)
destino = env['ai.provider.model'].search([('provider_id', '=', 2), ('name', '=', HASTA)])
if len(destino) != 1:
    fallo('no hay exactamente un modelo %s del proveedor 2 (hay %d)' % (HASTA, len(destino)))
if p.model_id.name == HASTA:
    print('P34 MODELO ya estaba: %s model_id=%d' % (HASTA, p.model_id.id))
    raise SystemExit(0)
antes = p.model_id.name
if antes not in DESDE.split():
    fallo('el modelo actual no es uno de los conocidos')
try:
    p.write({'model_id': destino.id})
    if p.model_name != HASTA:
        fallo('model_name no siguió a model_id')
except SystemExit:
    raise
except Exception as exc:
    fallo('al escribir: %s' % type(exc).__name__)
env.cr.commit()
print('P34 MODELO antes=%s ahora=%s model_id=%d' % (antes, p.model_id.name, p.model_id.id))
PY
)
echo "$SALIDA" | grep '^P34 ' || echo "Sin línea «P34»: el shell no ejecutó el script."
echo "$SALIDA" | grep -q '^P34 MODELO ' && exit 0
echo "No se cambió (nada escrito). Errores del shell, solo el tipo: $(echo "$SALIDA" | grep -oE '^[A-Za-z_.]+(Error|Exception)' | sort -u | paste -sd, -)"
exit 1
