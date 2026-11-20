#!/usr/bin/env bash
# Pruebas con toda la rama, D47: borra lo que plantó tarjeta_plantar.sh: las
# operaciones con tool_name seges_lab47 (en cualquier estado) y el contacto
# «Seges P47 contacto de prueba».
#
# ESCRIBE en lab_pns_ai_3973_14 (tras «s/N»): borra esas filas y hace commit.
# No toca ai_change_journal (sus filas quedan con safe_operation_id vacío,
# ondelete='set null', ai_change_journal.py:75-77) ni ai_log.
# Más de una operación seges_lab47 o más de un contacto: no borra nada y se
# revisa a mano.
# Borrado: ai.safe.operation no tiene unlink propio (safe_operation.py no lo
# define y es el único archivo con _name/_inherit 'ai.safe.operation'; su
# write solo bloquea fuera de su, :557-562). Lo limitan las ACL
# (security/ir.model.access.csv:5, usuario 1,1,0,0; :47, AI Administrator
# 1,1,1,1) y las reglas (security/security.xml:93-115). El shell de Odoo (odoo/cli/shell.py:113-115 de la imagen)
# corre como superusuario y el script usa además sudo(): basta. La única FK
# hacia ai_safe_operation es la del diario (set null).
#
# Uso: bash tarjeta_borrar.sh   (contexto de odoo-dev 14: lab_pns_ai_3973; web parado)
# Códigos: 0 borrado o no había nada; 1 no se borró (nada escrito);
# 10 respuesta distinta de «s»; 11 web en marcha o docker no responde; 12 argumentos de más;
# 13 falta la carpeta del laboratorio; 14 el contexto activo no es lab_pns_ai_3973.
set -uo pipefail

LAB_NOMBRE=lab_pns_ai_3973
LAB=~/GitHub/$LAB_NOMBRE
ESTADO=~/odoo-dev/14.0/estado
BD=lab_pns_ai_3973_14

[ $# = 0 ] || { echo "Uso: bash tarjeta_borrar.sh (sin argumentos)"; exit 12; }
cd "$LAB" 2>/dev/null || { echo "No existe $LAB."; exit 13; }
[ "$(sed -n 's/^REPO=//p' "$ESTADO" 2>/dev/null)" = "$LAB" ] || {
    echo "El contexto activo de odoo-dev 14 no es $LAB_NOMBRE (ver $ESTADO): no se hace nada."; exit 14; }
NOMBRES=$(docker ps --format '{{.Names}}' 2>/dev/null) || { echo "«docker ps» no responde."; exit 11; }
if printf '%s\n' "$NOMBRES" | grep -qx 'odoo-dev-14-web-1'; then
    echo "El contenedor odoo-dev-14-web-1 está en marcha: primero «Al acabar» y «odoo-dev 14 parar»."; exit 11
fi
read -rp "Esto ESCRIBE en $BD: borra la operación y el contacto de prueba de D47. ¿Seguir? (s/N) " RESP
[ "$RESP" = "s" ] || { echo "No se borra."; exit 10; }

SALIDA=$({ printf 'BD = "%s"\n' "$BD"; cat <<'PY'; } | odoo-dev 14 shell --bd "$BD" 2>&1
LOGIN = 'seges_int@example.com'
TOOL = 'seges_lab47'
CONTACTO = 'Seges P47 contacto de prueba'


def fallo(motivo):
    # Sin commit: no queda nada escrito.
    print('P47 ERROR: ' + motivo)
    raise SystemExit(1)


if env.cr.dbname != BD:
    fallo('la BD del shell no es ' + BD)
ops = env['ai.safe.operation'].sudo().search([('tool_name', '=', TOOL)])
contactos = env['res.partner'].sudo().with_context(active_test=False).search([('name', '=', CONTACTO)])
if len(ops) > 1 or len(contactos) > 1:
    fallo('hay %d operaciones y %d contactos con esos nombres: se revisa a mano' % (len(ops), len(contactos)))
if any(o.user_id.login != LOGIN for o in ops):
    fallo('alguna operación %s no es de seges_int' % TOOL)
n_ops, n_contactos = len(ops), len(contactos)
ops.unlink()
contactos.unlink()
env.cr.commit()
print('P47 BORRADA operaciones=%d contactos=%d quedan=%d' % (
    n_ops, n_contactos,
    env['ai.safe.operation'].sudo().search_count([('tool_name', '=', TOOL)])
    + env['res.partner'].sudo().with_context(active_test=False).search_count([('name', '=', CONTACTO)])))
PY
)
echo "$SALIDA" | grep '^P47 \(ERROR\|BORRADA\)' || echo "Sin línea «P47»: el shell no ejecutó el script."
echo "$SALIDA" | grep -q '^P47 BORRADA .* quedan=0$' && exit 0
echo "No se borró (nada escrito). Errores del shell, solo el tipo: $(echo "$SALIDA" | grep -oE '^[A-Za-z_.]+(Error|Exception)' | sort -u | paste -sd, -)"
exit 1
