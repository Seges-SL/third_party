#!/usr/bin/env bash
# Laboratorio L2 del parche 34 (D24): borra la sesión plantada por
# p34_plantar.sh (y, con ella, sus mensajes, sus trabajos y sus adjuntos,
# por el unlink del propio módulo).
#
# ESCRIBE en lab_pns_ai_3973_14: borra esa sesión y hace commit. No toca
# ai_log ni ninguna otra sesión.
#
# Uso: bash p34_borrar.sh        (con el contenedor web parado)
# Códigos: 0 borrada o no había ninguna; 1 no se borró (nada escrito);
# 10 respuesta distinta de «s»; 13 falta la carpeta del laboratorio.
set -uo pipefail

LAB=~/GitHub/lab_pns_ai_3973

cd "$LAB" 2>/dev/null || { echo "No existe $LAB."; exit 13; }
read -rp "Esto ESCRIBE en lab_pns_ai_3973_14: borra la sesión plantada de D24. ¿Seguir? (s/N) " RESP
[ "$RESP" = "s" ] || { echo "No se borra."; exit 10; }

SALIDA=$(odoo-dev 14 shell 2>&1 <<'PY'
NOMBRE = 'Seges P34 lienzo plantado (D24)'


def fallo(motivo):
    # Sin commit: no queda nada escrito.
    print('P34 ERROR: ' + motivo)
    raise SystemExit(1)


if env.cr.dbname != 'lab_pns_ai_3973_14':
    fallo('la BD del contexto no es lab_pns_ai_3973_14')
sesiones = env['chatboo.session'].sudo()
plantadas = sesiones.search([('name', '=', NOMBRE)])
if len(plantadas) > 1:
    fallo('hay %d sesiones con ese nombre: se revisa a mano' % len(plantadas))
if any(s.user_id.id != 12 for s in plantadas):
    fallo('la sesión plantada no es del usuario 12')
borradas = len(plantadas)
plantadas.unlink()
env.cr.commit()
print('P34 BORRADA sesiones=%d quedan=%d' % (
    borradas, sesiones.search_count([('name', '=', NOMBRE)])))
PY
)
echo "$SALIDA" | grep '^P34 ' || echo "Sin línea «P34»: el shell no ejecutó el script."
echo "$SALIDA" | grep -q '^P34 BORRADA sesiones=[01] quedan=0$' && exit 0
echo "No se borró (nada escrito). Errores del shell, solo el tipo: $(echo "$SALIDA" | grep -oE '^[A-Za-z_.]+(Error|Exception)' | sort -u | paste -sd, -)"
exit 1
