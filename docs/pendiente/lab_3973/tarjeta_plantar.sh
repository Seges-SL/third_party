#!/usr/bin/env bash
# Pruebas con toda la rama, D47 (17/11/2026): planta la operación del
# reintento de la tarjeta. Sin sesión: la tarjeta no vive en la sesión, la pinta
# el panel de Chatboo al abrirse con las operaciones pendientes del usuario
# (chatboo_systray.js:409-411 → chatboo_component_v2.js:2162-2188 →
# /verification/pending).
#
# Crea, en lab_pns_ai_3973_14:
#   - el contacto de prueba «Seges P47 contacto de prueba»;
#   - una operación supervisada high, pendiente, de seges_int@example.com
#     (tool_name seges_lab47), con un paso inofensivo: escribir el comment de
#     ese contacto (formato de test_seges_verify_execute_40001.py:114-133).
# Antes comprueba que el plan pasa validate_safe_plan como seges_int y que
# seges_int puede escribir el contacto; si no, no escribe nada.
# create_verification caduca de paso las pendientes vencidas de la BD
# (cleanup_expired, safe_operation.py:495-503): lo mismo que en cualquier
# propuesta.
#
# La operación caduca a los 15 min (PENDING_OPERATION_TTL_MINUTES,
# pns_ai_mcp/constants.py:7): el escenario (lab_auto.sh … --escenario tarjeta)
# se lanza antes. El script imprime la hora de creación y la de caducidad.
#
# ESCRIBE en lab_pns_ai_3973_14 (tras «s/N»): el contacto y la operación, con
# commit. Se deshace con tarjeta_borrar.sh.
#
# Uso: bash tarjeta_plantar.sh   (contexto de odoo-dev 14: lab_pns_ai_3973; web parado)
# Códigos: 0 plantada; 1 no se plantó (nada escrito); 10 respuesta distinta de
# «s»; 11 web en marcha o docker no responde; 12 argumentos de más; 13 falta la carpeta del
# laboratorio; 14 el contexto activo no es lab_pns_ai_3973.
set -uo pipefail

LAB_NOMBRE=lab_pns_ai_3973
LAB=~/GitHub/$LAB_NOMBRE
ESTADO=~/odoo-dev/14.0/estado
BD=lab_pns_ai_3973_14

[ $# = 0 ] || { echo "Uso: bash tarjeta_plantar.sh (sin argumentos)"; exit 12; }
cd "$LAB" 2>/dev/null || { echo "No existe $LAB."; exit 13; }
[ "$(sed -n 's/^REPO=//p' "$ESTADO" 2>/dev/null)" = "$LAB" ] || {
    echo "El contexto activo de odoo-dev 14 no es $LAB_NOMBRE (ver $ESTADO): no se hace nada."; exit 14; }
NOMBRES=$(docker ps --format '{{.Names}}' 2>/dev/null) || { echo "«docker ps» no responde."; exit 11; }
if printf '%s\n' "$NOMBRES" | grep -qx 'odoo-dev-14-web-1'; then
    echo "El contenedor odoo-dev-14-web-1 está en marcha: primero «Al acabar» y «odoo-dev 14 parar»."; exit 11
fi
read -rp "Esto ESCRIBE en $BD: crea el contacto de prueba y una operación high pendiente de seges_int (D47); create_verification caduca de paso las pendientes vencidas de la BD. ¿Seguir? (s/N) " RESP
[ "$RESP" = "s" ] || { echo "No se planta."; exit 10; }

SALIDA=$({ printf 'BD = "%s"\n' "$BD"; cat <<'PY'; } | odoo-dev 14 shell --bd "$BD" 2>&1
from odoo.exceptions import AccessError
from odoo.addons.pns_ai_mcp.controllers.safe_plan import validate_safe_plan

LOGIN = 'seges_int@example.com'
TOOL = 'seges_lab47'
CONTACTO = 'Seges P47 contacto de prueba'
COMENTARIO = 'Seges P47 reintento'


def fallo(motivo):
    # Sin commit: no queda nada escrito.
    print('P47 ERROR: ' + motivo)
    raise SystemExit(1)


if env.cr.dbname != BD:
    fallo('la BD del shell no es ' + BD)
usuario = env['res.users'].sudo().search([('login', '=', LOGIN)])
if len(usuario) != 1:
    fallo('no hay un usuario %s' % LOGIN)
Ops = env['ai.safe.operation'].sudo()
Partners = env['res.partner'].sudo().with_context(active_test=False)
if Ops.search_count([('tool_name', '=', TOOL)]) or Partners.search_count([('name', '=', CONTACTO)]):
    fallo('ya hay algo plantado: bórralo antes con tarjeta_borrar.sh')
contacto = Partners.create({'name': CONTACTO})
try:
    contacto.with_user(usuario).check_access_rights('write')
    contacto.with_user(usuario).check_access_rule('write')
except AccessError:
    fallo('seges_int no puede escribir el contacto de prueba (res.partner): '
          'ver guia_rama.md, bloque 4, punto 4, «Requisito de D47»')
steps = [{'op': 'write', 'model': 'res.partner', 'ids': [contacto.id],
          'values': {'comment': COMENTARIO}}]
plan = ['write 1 res.partner']
ok, _err = validate_safe_plan(steps, env(user=usuario.id))
if not ok:
    fallo('el plan no pasa validate_safe_plan como seges_int')
op = Ops.create_verification(
    operation_type='write', model_name='res.partner', records_count=1,
    changes_info={'plan': plan, 'danger_level': 'high'}, user_id=usuario.id,
    tool_name=TOOL,
    operation_data={'plan_steps': steps, 'title': 'Seges P47 reintento de la tarjeta',
                    'plan': plan, 'danger_level': 'high'})
if op.danger_level != 'high' or op.status != 'pending' or op.user_id != usuario:
    fallo('la operación no quedó high, pendiente y de seges_int')
env.cr.commit()
print('P47 PLANTADA op=%d contacto=%d usuario=%d creada=%s caduca=%s' % (
    op.id, contacto.id, usuario.id, op.create_date.strftime('%Y-%m-%d %H:%M:%S'),
    op.expires_at.strftime('%Y-%m-%d %H:%M:%S')))
PY
)
echo "$SALIDA" | grep '^P47 \(ERROR\|PLANTADA\)' || echo "Sin línea «P47»: el shell no ejecutó el script."
LINEA=$(echo "$SALIDA" | grep '^P47 PLANTADA ')
if [ -n "$LINEA" ]; then
    CREADA=$(echo "$LINEA" | sed -n 's/.* creada=\([0-9-]* [0-9:]*\) caduca=.*/\1/p')
    CADUCA=$(echo "$LINEA" | sed -n 's/.* caduca=\([0-9-]* [0-9:]*\)$/\1/p')
    echo "Creada: $CREADA UTC ($(date -d "$CREADA UTC" '+%H:%M:%S') hora local)."
    echo "Caduca: $CADUCA UTC ($(date -d "$CADUCA UTC" '+%H:%M:%S') hora local): lanza el escenario antes (lab_auto.sh comprueba que queda al menos 1 min)."
    exit 0
fi
echo "No se plantó (nada escrito). Errores del shell, solo el tipo: $(echo "$SALIDA" | grep -oE '^[A-Za-z_.]+(Error|Exception)' | sort -u | paste -sd, -)"
exit 1
