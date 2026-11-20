#!/usr/bin/env bash
# Pruebas con toda la rama, D46 (17/11/2026): _require_settings
# (pns_ai_mcp/models/ai_system_action.py:123-128) con y sin el parche 32.
# En odoo-dev 14 shell, SIN commit, cada caso en un savepoint que se deshace.
#
# Por caso: crea (dentro del savepoint) el proponente (AI Administrator, sin o
# con Ajustes), un administrador de Ajustes que confirma y una vista de prueba
# de res.partner con el campo comment (el «modelo de prueba», como
# test_seges_user_groups.py:165-203). Pasa el plan por validate_safe_plan como
# el proponente (informativo), crea la operación con create_verification, la
# confirma el administrador de Ajustes (_confirm_by_user) y la ejecuta como la
# ejecuta el servidor: entorno del proponente (safe_operation.py:1441-1445) con
# el contexto del diario (:1477-1486) y execute_safe_plan. No usa
# _resolve_execute porque hace commit (safe_operation.py:948 y :957).
#   campo: paso field_required → _apply_field_set_required
#          (safe_plan_execute.py:112-128; ai_system_action.py:389-391);
#   vista: paso action view.set_field_readonly → _apply_view_modifier
#          (trusted_actions_system.xml:27-35; ai_system_action.py:437-444 y :218-221).
# Esperado: AI Administrator sin Ajustes → AccessError de _require_settings
# («needs the Settings administrator role») en los dos; con Ajustes → ok.
# La propuesta de field_required sin Ajustes ya la rechaza la validación
# (safe_plan_validate.py:198-202): se informa y la operación se crea igualmente
# para probar la barrera al ejecutar.
# execute_safe_plan (safe_plan_execute.py:60-242) no captura errores: los lanza
# (el único except, :108, es de las etiquetas de api_call) y, si va bien,
# devuelve la lista results (:242). «ok» exige el valor de éxito (ok True en el
# dict de la fila) y el efecto, mirado dentro del savepoint antes de deshacerlo:
#   campo: required del campo comment en el registro, de no a sí
#          (ai_system_action.py:410-412); ir.model.fields no se persiste en un
#          campo de módulo (ir_model.py:924-927 de la imagen; nota en :408), y
#          se informa;
#   vista: comment readonly en la arquitectura de la vista de prueba
#          (fields_view_get), de no a sí, con las vistas heredadas de ella.
# Si no, «ok SIN EFECTO» (DISTINTO). Un error devuelto en vez de lanzado se
# clasifica como la excepción: «AccessError de _require_settings» si lleva el
# mensaje, «error devuelto (otro)» si no.
#
# --sin-32: la misma pasada con la neutralización N32 (_check_settings_admin no
# comprueba nada; pns_ai_mcp/models/ai_trusted_action.py:89), con el método de
# siempre: SHA-256, copia, cambio, pasada, restauración y SHA-256 igual. El
# archivo debe estar sin cambios en git antes de empezar. Esperado: el mismo
# resultado (el 32 cubre create/write/unlink de ai.trusted.action, no _apply).
#
# Uso: bash rama_require_settings.sh [--sin-32]
#      (contexto de odoo-dev 14: lab_pns_ai_3973; BD lab_pns_ai_3973_14;
#      contenedor web parado)
# Códigos: 0 como se espera; 1 algún caso distinto de lo esperado o el shell no
# terminó; 11 web en marcha o docker no responde; 12 argumentos no válidos;
# 13 falta la carpeta del laboratorio o el repo; 14 el contexto activo no es
# lab_pns_ai_3973; 17 --sin-32: el archivo tiene cambios antes de empezar, la
# neutralización no se aplicó o la restauración no da el SHA-256 de antes.
set -uo pipefail

LAB_NOMBRE=lab_pns_ai_3973
LAB=~/GitHub/$LAB_NOMBRE
REPO=~/GitHub/third_party
ARCHIVO_32=pns_ai_mcp/models/ai_trusted_action.py
ESTADO=~/odoo-dev/14.0/estado
BD=lab_pns_ai_3973_14
SIN_32=0
while [ $# -gt 0 ]; do
    case "$1" in
        --sin-32) SIN_32=1; shift ;;
        *) echo "Argumento no válido: $1"; exit 12 ;;
    esac
done
cd "$LAB" 2>/dev/null || { echo "No existe $LAB."; exit 13; }
[ -f "$REPO/$ARCHIVO_32" ] || { echo "No existe $REPO/$ARCHIVO_32."; exit 13; }
[ "$(sed -n 's/^REPO=//p' "$ESTADO" 2>/dev/null)" = "$LAB" ] || {
    echo "El contexto activo de odoo-dev 14 no es $LAB_NOMBRE (ver $ESTADO): no se hace nada."; exit 14; }
NOMBRES=$(docker ps --format '{{.Names}}' 2>/dev/null) || { echo "«docker ps» no responde."; exit 11; }
if printf '%s\n' "$NOMBRES" | grep -qx 'odoo-dev-14-web-1'; then
    echo "El contenedor odoo-dev-14-web-1 está en marcha: primero «Al acabar» y «odoo-dev 14 parar»."; exit 11
fi

RESTAURAR=0
COPIA=
SHA_ANTES=
restaurar() {
    [ "$RESTAURAR" = 1 ] || return 0
    RESTAURAR=0
    cp "$COPIA/ai_trusted_action.py" "$REPO/$ARCHIVO_32"
    local sha_despues
    sha_despues=$(sha256sum "$REPO/$ARCHIVO_32" | cut -d' ' -f1)
    rm -rf -- "$COPIA"
    if [ "$sha_despues" = "$SHA_ANTES" ]; then
        echo "N32 restaurada: SHA-256 $sha_despues, IGUAL al de antes"
    else
        echo "N32: ¡el SHA-256 tras restaurar ($sha_despues) NO es el de antes ($SHA_ANTES)!"
        exit 17
    fi
}
if [ "$SIN_32" = 1 ]; then
    git -C "$REPO" diff --quiet -- "$ARCHIVO_32" && git -C "$REPO" diff --cached --quiet -- "$ARCHIVO_32" || {
        echo "$ARCHIVO_32 tiene cambios en git: no se neutraliza."; exit 17; }
    SHA_ANTES=$(sha256sum "$REPO/$ARCHIVO_32" | cut -d' ' -f1)
    COPIA=$(mktemp -d /tmp/n32.XXXXXX)
    cp "$REPO/$ARCHIVO_32" "$COPIA/ai_trusted_action.py" || exit 17
    RESTAURAR=1
    trap 'restaurar' EXIT
    trap 'exit 130' INT TERM
    python3 -I - "$REPO/$ARCHIVO_32" <<'PY' || { echo "No se pudo aplicar N32."; exit 17; }
import sys
ruta = sys.argv[1]
texto = open(ruta, encoding='utf-8').read()
ancla = '        from ..utils.privilege_cusp import settings_admin_error\n'
metodo = '    def _check_settings_admin(self):\n'
if texto.count(ancla) != 1 or texto.count(metodo) != 1 or texto.index(metodo) > texto.index(ancla):
    sys.exit(1)
texto = texto.replace(ancla, '        return  # N32 (laboratorio): _check_settings_admin no comprueba nada\n' + ancla)
open(ruta, 'w', encoding='utf-8').write(texto)
PY
    SHA_N32=$(sha256sum "$REPO/$ARCHIVO_32" | cut -d' ' -f1)
    [ "$SHA_N32" != "$SHA_ANTES" ] || { echo "N32 no cambió el archivo."; exit 17; }
    echo "N32 aplicada: SHA-256 antes $SHA_ANTES, con N32 $SHA_N32"
fi

SALIDA=$({ printf 'BD = "%s"\nSIN_32 = %s\n' "$BD" "$([ "$SIN_32" = 1 ] && echo True || echo False)"; cat <<'PY'; } | odoo-dev 14 shell --bd "$BD" 2>&1
import inspect
import json

from lxml import etree
from odoo.exceptions import AccessError
from odoo.addons.pns_ai_mcp.controllers.safe_plan import execute_safe_plan, validate_safe_plan
from odoo.addons.pns_ai_mcp.utils.one_company import SCREEN_COMPANIES, one_company_context

if env.cr.dbname != BD:
    print('D46 ERROR: la BD del shell no es ' + BD)
    raise SystemExit(1)
neutralizado = 'N32 (laboratorio)' in inspect.getsource(type(env['ai.trusted.action'])._check_settings_admin)
print('D46 parche 32 %s en el código cargado' % ('NEUTRALIZADO (N32)' if neutralizado else 'activo'))
if neutralizado != SIN_32:
    print('D46 ERROR: el código cargado no es el esperado')
    raise SystemExit(1)
Users = env['res.users'].sudo().with_context(no_reset_password=True)
G = {x: env.ref(x).id for x in ('base.group_user', 'base.group_system', 'pns_ai_mcp.group_ai_admin')}
MSG = 'needs the Settings administrator role'


def usuario(login, ajustes):
    grupos = [G['base.group_user'], G['pns_ai_mcp.group_ai_admin']]
    if ajustes:
        grupos.append(G['base.group_system'])
    return Users.create({'name': login, 'login': login, 'groups_id': [(6, 0, grupos)]})


def pasos(plan, vista):
    if plan == 'campo':
        return [{'op': 'field_required', 'model': 'res.partner', 'field': 'comment', 'required': True}]
    return [{'op': 'action', 'action_code': 'view.set_field_readonly',
             'args': {'model': 'res.partner', 'field': 'comment', 'readonly': True,
                      'view_ids': [vista.id]}}]


def caso(con_ajustes, plan):
    prop = usuario('seges_d46_prop', con_ajustes)
    conf = usuario('seges_d46_ajustes', True)
    vista = env['ir.ui.view'].sudo().create({
        'name': 'seges.d46.partner.form', 'model': 'res.partner', 'type': 'form',
        'arch': '<?xml version="1.0"?><form><sheet><field name="name"/>'
                '<field name="comment"/></sheet></form>'})
    steps = pasos(plan, vista)
    try:
        ok, err = validate_safe_plan(steps, env(user=prop.id))
        propuesta = 'aceptada' if ok else 'rechazada en la validación'
    except Exception as e:  # solo el tipo
        propuesta = 'excepción ' + type(e).__name__
    titulo = 'Seges D46 %s' % plan
    plan_txt = ['%s res.partner.comment' % plan]
    op = env['ai.safe.operation'].sudo().create_verification(
        operation_type='action', model_name='res.partner', records_count=1,
        changes_info={'plan': plan_txt, 'danger_level': 'high'}, user_id=prop.id,
        tool_name='seges_lab46',
        operation_data={'plan_steps': steps, 'title': titulo, 'plan': plan_txt,
                        'danger_level': 'high'})
    op.with_user(conf)._confirm_by_user()
    data = op.get_operation_data() or {}
    # Como safe_operation.py:1441-1445 y :1477-1486.
    exec_env = env(user=op.user_id.id)
    exec_env = exec_env(context=one_company_context(
        exec_env, requested=data.get(SCREEN_COMPANIES) or ()))
    exec_env = exec_env(context=dict(
        exec_env.context or {},
        ai_journal_safe_operation_id=op.id,
        ai_journal_turn=op.turn or False,
        ai_journal_user_id=op.user_id.id,
        ai_journal_confirmed_by_uid=op.confirmed_by_uid.id or exec_env.uid,
        ai_journal_origin=op._resolve_log_origin(),
        ai_journal_note=(data.get('title') or '')[:500],
    ))
    antes = efecto_actual(plan, vista, None)
    try:
        filas = execute_safe_plan(exec_env, data.get('plan_steps') or [])
    except AccessError as e:
        return propuesta, op.status, (
            'AccessError de _require_settings' if MSG in str(e) else 'AccessError (otro)'), 'lanzado'
    except Exception as e:  # solo el tipo
        return propuesta, op.status, 'excepción ' + type(e).__name__, 'lanzado'
    resultado, detalle = resultado_devuelto(plan, filas, vista, antes)
    return propuesta, op.status, resultado, detalle


def interior(plan, filas):
    """El dict de éxito o de error de la única fila del plan.

    execute_safe_plan devuelve la lista results (safe_plan_execute.py:242) y no
    captura errores (los lanza). Campo: fila {'op': 'field_required', …,
    'orm': <dict de _apply_field_set_required>} (:122-133). Vista: fila
    {'op': 'action', 'action_code': …, 'result': <dict de _apply_view_modifier>}
    (:146-148).
    """
    if not isinstance(filas, list) or len(filas) != 1 or not isinstance(filas[0], dict):
        return None
    return filas[0].get('orm' if plan == 'campo' else 'result')


def efecto_actual(plan, vista, r):
    """Campo: comment obligatorio en el registro. Vista: comment readonly en la vista de prueba."""
    if plan == 'campo':
        return bool(env['res.partner']._fields['comment'].required)
    env['base'].flush()
    arch = env['res.partner'].sudo().fields_view_get(view_id=vista.id, view_type='form')['arch']
    nodos = etree.fromstring(arch.encode('utf-8')).xpath("//field[@name='comment']")

    def solo_lectura(nodo):
        if nodo.get('readonly') in ('1', 'True', 'true'):
            return True
        try:
            return json.loads(nodo.get('modifiers') or '{}').get('readonly') is True
        except ValueError:
            return False
    hijas = env['ir.ui.view'].sudo().browse((r or {}).get('ids') or []).exists()
    hereda = r is None or (bool(hijas) and all(h.inherit_id == vista for h in hijas))
    return bool(nodos) and all(solo_lectura(n) for n in nodos) and hereda


def resultado_devuelto(plan, filas, vista, antes):
    """«ok» solo con el valor de éxito y el efecto, mirado dentro del savepoint."""
    r = interior(plan, filas)
    if not isinstance(r, dict):
        return 'sin resultado reconocible', 'devuelto'
    if not r.get('ok'):
        # Un error devuelto se clasifica como la excepción.
        texto = json.dumps(r, default=str)
        return ('AccessError de _require_settings' if MSG in texto else 'error devuelto (otro)'), 'devuelto'
    ahora = efecto_actual(plan, vista, r)
    if plan == 'campo':
        # _apply_field_set_required (ai_system_action.py:389-422): intenta
        # Imf.write({'required': True}) (:395-409); en un campo de módulo, como
        # comment, ir.model.fields.write lanza UserError (odoo/addons/base/
        # models/ir_model.py:915 y :924-927 de la imagen), que queda en notes
        # («Could not persist …», :408); después pone required en el campo del
        # registro de este proceso (:410-412) y devuelve ok, required y notes
        # (:416-422).
        persistido = not any('Could not persist' in str(n) for n in (r.get('notes') or []))
        efecto = r.get('required') is True and ahora and not antes
        detalle = 'required en el registro: antes %s, después %s; ir.model.fields %s' % (
            'sí' if antes else 'no', 'sí' if ahora else 'no',
            'persistido' if persistido else 'no persistido (campo de módulo)')
    else:
        # _apply_view_modifier (ai_system_action.py:218-315) crea la vista
        # heredada (ids) y su política, y devuelve ok e ids (:283-287).
        efecto = ahora and not antes and bool(r.get('ids'))
        detalle = 'comment readonly en la vista de prueba: antes %s, después %s; vistas heredadas %d' % (
            'sí' if antes else 'no', 'sí' if ahora else 'no', len(r.get('ids') or []))
    return ('ok' if efecto else 'ok SIN EFECTO'), detalle


# El caso «con Ajustes, campo» va el último: deja res.partner.comment como
# obligatorio en el registro de este proceso (ai_system_action.py:410-412), y
# los casos siguientes crean usuarios (y con ellos contactos).
CASOS = ((False, 'campo'), (False, 'vista'), (True, 'vista'), (True, 'campo'))
bien = 0
for con_ajustes, plan in CASOS:
    esperado = 'ok' if con_ajustes else 'AccessError de _require_settings'
    env.cr.execute('SAVEPOINT seges_d46')
    try:
        propuesta, estado, resultado, detalle = caso(con_ajustes, plan)
    except Exception as e:  # solo el tipo
        propuesta, estado, resultado, detalle = '?', '?', 'excepción al preparar ' + type(e).__name__, '-'
    finally:
        env.cr.execute('ROLLBACK TO SAVEPOINT seges_d46')
        env.clear()
    bien += resultado == esperado
    print('D46 %s Ajustes, %s: propuesta %s; operación %s por un administrador de Ajustes; '
          'ejecución: %s (%s; esperado: %s) → %s' % (
              'con' if con_ajustes else 'sin', plan, propuesta, estado, resultado, detalle, esperado,
              'OK' if resultado == esperado else 'DISTINTO'))
env.cr.rollback()
print('D46 FIN %d/%d como se espera (%s; nada escrito: savepoints deshechos y rollback)' % (
    bien, len(CASOS), 'con N32' if SIN_32 else 'con el 32'))
PY
)
echo "$SALIDA" | grep '^D46 ' || echo "Sin líneas «D46»: el shell no ejecutó el script."
CODIGO=1
if echo "$SALIDA" | grep -q '^D46 FIN 4/4 '; then
    CODIGO=0
else
    echo "$SALIDA" | grep -q '^D46 FIN ' || echo "El shell no terminó. Errores, solo el tipo: $(echo "$SALIDA" | grep -oE '^[A-Za-z_.]+(Error|Exception)' | sort -u | paste -sd, -)"
fi
restaurar
trap - EXIT
echo "Resultado: $([ "$CODIGO" = 0 ] && echo 'como se espera' || echo FALLO)"
exit "$CODIGO"
