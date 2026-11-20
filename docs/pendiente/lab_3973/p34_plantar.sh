#!/usr/bin/env bash
# Laboratorio L2 del parche 34 (D24): planta el lienzo de la sesión 11 de la
# 3879 (~/lab_e3p/p8ea_sesion11.html) en UNA sesión nueva de seges_int.
#
# ESCRIBE en lab_pns_ai_3973_14: crea una fila de chatboo_session y hace
# commit. No toca nada más. Se deshace con p34_borrar.sh.
#
# Uso: bash p34_plantar.sh        (con el contenedor web parado)
# Códigos: 0 plantada; 1 no se plantó (nada escrito); 10 respuesta distinta de
# «s»; 12 falta el HTML o su SHA-256 no es el previsto; 13 falta la carpeta
# del laboratorio.
set -uo pipefail

HTML=~/lab_e3p/p8ea_sesion11.html
SHA=4f3db19a1706c47816ff2f440e93c2b46ae2206892027ffbb31d8613ee81b6a9
LAB=~/GitHub/lab_pns_ai_3973

[ -f "$HTML" ] || { echo "No existe $HTML."; exit 12; }
echo "$SHA  $HTML" | sha256sum -c --quiet - >/dev/null 2>&1 \
    || { echo "El SHA-256 de $HTML no es el previsto: no se planta."; exit 12; }
cd "$LAB" 2>/dev/null || { echo "No existe $LAB."; exit 13; }
read -rp "Esto ESCRIBE en lab_pns_ai_3973_14: crea una sesión de seges_int con el lienzo de D24. ¿Seguir? (s/N) " RESP
[ "$RESP" = "s" ] || { echo "No se planta."; exit 10; }

SALIDA=$({ printf 'B64 = "%s"\nSHA = "%s"\n' "$(base64 -w0 "$HTML")" "$SHA"; cat <<'PY'; } | odoo-dev 14 shell 2>&1
import base64
import hashlib

NOMBRE = 'Seges P34 lienzo plantado (D24)'


def fallo(motivo):
    # Sin commit: no queda nada escrito.
    print('P34 ERROR: ' + motivo)
    raise SystemExit(1)


if env.cr.dbname != 'lab_pns_ai_3973_14':
    fallo('la BD del contexto no es lab_pns_ai_3973_14')
pagina = base64.b64decode(B64).decode('utf-8')
if hashlib.sha256(pagina.encode('utf-8')).hexdigest() != SHA:
    fallo('el lienzo recibido no tiene el SHA-256 previsto')
usuario = env['res.users'].search([('login', '=', 'seges_int@example.com')])
if len(usuario) != 1 or usuario.id != 12:
    fallo('seges_int@example.com no es el usuario 12')
sesiones = env['chatboo.session'].sudo()
if sesiones.search_count([('name', '=', NOMBRE)]):
    fallo('ya hay una sesión plantada: bórrala antes con p34_borrar.sh')
sesion = sesiones.create({
    'name': NOMBRE,
    'user_id': usuario.id,
    'canvas_open': True,
    'canvas_design': pagina,
    'canvas_rev': 1,
    'canvas_title': 'Seges P34',
})
env.cr.commit()
print('P34 PLANTADA id=%d usuario=%d canvas_rev=%d bytes=%d' % (
    sesion.id, sesion.user_id.id, sesion.canvas_rev, len(pagina.encode('utf-8'))))
PY
)
echo "$SALIDA" | grep '^P34 ' || echo "Sin línea «P34»: el shell no ejecutó el script."
echo "$SALIDA" | grep -q '^P34 PLANTADA ' && exit 0
echo "No se plantó (nada escrito). Errores del shell, solo el tipo: $(echo "$SALIDA" | grep -oE '^[A-Za-z_.]+(Error|Exception)' | sort -u | paste -sd, -)"
exit 1
