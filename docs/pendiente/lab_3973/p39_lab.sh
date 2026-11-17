#!/usr/bin/env bash
# Pruebas con toda la rama, bloque 3: el parche 39 (PNS-107) en el laboratorio,
# por la herramienta relaxaicode REAL, como un usuario interno
# (seges_int@example.com), en odoo-dev 14 shell y SIN commit.
#
# Cómo se llama a la herramienta (citado de la rama, no del scratchpad):
# tool_relaxaicode(controller, arguments) (pns_ai_mcp/controllers/
# tools_relaxaicode.py:104-107) con el controlador de los tests de Seges,
# _StubController(env) (pns_ai_mcp/tests/seges_common.py:15-43): la caja A real
# abre su propio cursor de solo lectura (get_readonly_env, :25-28) y lo deshace
# al cerrar.
#
# Clases de respuesta (nunca se imprime el texto; solo la clase):
#   requires_write   la respuesta es la de _read_only_response()
#                    (pns_ai_mcp/controllers/relaxaicode_prepare.py:400-416:
#                    {"success": false, "requires_write": true, …} en el texto).
#                    La da el AST antes de ejecutar: _detect_requires_write_from_ast
#                    (validators_checks.py:464-484, llamado en validators.py:466)
#                    marca toda llamada .m(...) cuyo nombre está en la lista global
#                    RELAXAICODE_SIDE_EFFECT_METHODS (validators_base.py:230; el 39
#                    añade sus 8 nombres en :304-314), y tools_relaxaicode.py:159-172
#                    devuelve _read_only_response().
#   bloqueado por el 39  "isError": true con el mensaje del parche 39 en ejecución:
#                    _read_attr (context_builder.py:330-334) llama a
#                    _seges_check_model_method (:309-327), que lanza
#                    AttributeError("Method '<nombre>' writes outside RelaxAICode's
#                    rollback and is not allowed here (use safe_plan_request for
#                    writes).") si <nombre> está en RELAXAICODE_SIDE_EFFECT_MODEL_METHODS
#                    del modelo (validators_base.py:324-333). La herramienta lo
#                    devuelve como «Error executing code: <mensaje>»
#                    (relaxaicode_failures.py:194-199). Marcador: «Method '<nombre>'
#                    writes outside RelaxAICode's rollback» con el nombre del caso.
#   otro error       "isError": true sin ese marcador: FALLO.
#   excepción        tool_relaxaicode lanzó una excepción: NO es un rechazo; el
#                    resultado es NO CONCLUYENTE (código 8).
#
# Casos (D40 y D40b a D40d), con su clase prevista:
#   iap.account.get('seges_lab39')                   bloqueado por el 39 ('get' no está
#       en la lista global, «dict.get»; validators_base.py:326)
#   iap.account.get_credits_url('seges_lab39')       requires_write (llamada con nombre
#       de la lista global, validators_base.py:307)
#   f = iap.account.get_config_account_url; f()      bloqueado por el 39 (lectura sin
#       llamada: el AST no la ve; validators_base.py:326)
#   sms.resend.new({}).action_buy_credits()          requires_write (validators_base.py:310)
# Una clase de rechazo distinta de la prevista también es FALLO (desmiente la
# lectura). Control: result = {'a': {'k': 1}.get('k'),
# 'n': iap.account.search_count([])} sin error.
# Antes y después, count(*) y max(id) de iap_account desde un cursor APARTE en
# solo lectura: sin cambios. Si el parche fallara, get crearía la cuenta y la
# confirmaría en su propio cursor aunque el shell no haga commit: eso es lo que
# detecta esta lectura.
# Antes de todo comprueba por SQL (solo lectura) que sms e iap están instalados;
# si falta alguno, sale con 16 sin llamar a la herramienta.
#
# No escribe nada: el cursor del shell se deshace al final. Solo imprime
# «rechazado»/«NO RECHAZADO», la clase de la respuesta y recuentos.
#
# Uso: bash p39_lab.sh [--bd lab_pns_ai_3973_14]
#      (contexto de odoo-dev 14: lab_pns_ai_3973)
# Códigos: 0 como se espera; 1 FALLO: algún caso con una clase distinta de la
# prevista («otro error», «sin error» u otro rechazo), el control falla,
# iap_account cambia o el shell no terminó; 8 NO CONCLUYENTE: alguna llamada
# lanzó una excepción y no hay ningún FALLO; 12 argumentos no válidos; 13 falta
# la carpeta del laboratorio; 14 el contexto activo no es lab_pns_ai_3973;
# 16 sms o iap no están instalados. Si coinciden, 1 va por delante de 8.
set -uo pipefail

LAB_NOMBRE=lab_pns_ai_3973
LAB=~/GitHub/$LAB_NOMBRE
ESTADO=~/odoo-dev/14.0/estado
BD=lab_pns_ai_3973_14
while [ $# -gt 0 ]; do
    case "$1" in
        --bd) [ $# -ge 2 ] || { echo "Falta el valor de --bd."; exit 12; }; BD=$2; shift 2 ;;
        *) echo "Argumento no válido: $1"; exit 12 ;;
    esac
done
[[ "$BD" =~ ^[a-z0-9_]+$ ]] || { echo "--bd no válida: $BD"; exit 12; }
cd "$LAB" 2>/dev/null || { echo "No existe $LAB."; exit 13; }
[ "$(sed -n 's/^REPO=//p' "$ESTADO" 2>/dev/null)" = "$LAB" ] || {
    echo "El contexto activo de odoo-dev 14 no es $LAB_NOMBRE (ver $ESTADO): no se hace nada."; exit 14; }

SALIDA=$({ printf 'BD = "%s"\n' "$BD"; cat <<'PY'; } | odoo-dev 14 shell --bd "$BD" 2>&1
import json

import odoo
from odoo.addons.pns_ai_mcp.controllers.relaxaicode_prepare import _read_only_response
from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import tool_relaxaicode
from odoo.addons.pns_ai_mcp.tests.seges_common import _StubController

LOGIN = 'seges_int@example.com'
BLOQUEO_39 = 'bloqueado por el 39'
# (nombre, código, clase prevista, método cuyo nombre lleva el mensaje del 39)
CASOS = (
    ("iap.account.get('seges_lab39')",
     "r = env['iap.account'].get('seges_lab39')\nresult = 1\n", BLOQUEO_39, 'get'),
    ("iap.account.get_credits_url('seges_lab39')",
     "r = env['iap.account'].get_credits_url('seges_lab39')\nresult = 1\n", 'requires_write', None),
    ("f = iap.account.get_config_account_url; f()",
     "f = env['iap.account'].get_config_account_url\nr = f()\nresult = 1\n", BLOQUEO_39,
     'get_config_account_url'),
    ("sms.resend.new({}).action_buy_credits()",
     "r = env['sms.resend'].new({}).action_buy_credits()\nresult = 1\n", 'requires_write', None),
)
CONTROL = "result = {'a': {'k': 1}.get('k'), 'n': env['iap.account'].search_count([])}\n"

if env.cr.dbname != BD:
    print('P39 ERROR: la BD del shell no es ' + BD)
    raise SystemExit(1)
env.cr.execute("SELECT name FROM ir_module_module WHERE name IN ('sms', 'iap') AND state = 'installed'")
faltan = sorted({'sms', 'iap'} - {r[0] for r in env.cr.fetchall()})
if faltan:
    print('P39 FALTAN %s (no se llama a la herramienta)' % ','.join(faltan))
    raise SystemExit(16)
asker = env['res.users'].sudo().search([('login', '=', LOGIN)])
if len(asker) != 1 or not asker.has_group('base.group_user'):
    print('P39 ERROR: %s no es un usuario interno' % LOGIN)
    raise SystemExit(1)
print('P39 usuario %d interno; AI Conversational %s' % (
    asker.id, 'sí' if asker.has_group('pns_ai_mcp.group_ai_conversational') else 'no'))


def iap_aparte():
    """count(*) y max(id) de iap_account desde otro cursor, en solo lectura."""
    with odoo.registry(BD).cursor() as cr2:
        cr2.execute('SET TRANSACTION READ ONLY')
        cr2.execute('SELECT count(*), coalesce(max(id), 0) FROM iap_account')
        fila = tuple(cr2.fetchone())
        cr2.rollback()
    return fila


def clase(resp, metodo):
    """Clase de la respuesta; el texto se mira solo para buscar marcadores."""
    if not isinstance(resp, dict):
        return 'otro error'
    if resp == _read_only_response():
        return 'requires_write'
    texto = json.dumps(resp, default=str)
    if resp.get('isError'):
        if metodo and ("Method %r writes outside RelaxAICode's rollback" % metodo) in texto:
            return BLOQUEO_39
        return 'otro error'
    try:
        interior = json.loads(resp['content'][0]['text'])
        if isinstance(interior, dict) and interior.get('requires_write') is True:
            return 'requires_write'
    except Exception:
        pass
    return 'sin error'


def run(code, metodo=None):
    try:
        return clase(tool_relaxaicode(_StubController(env(user=asker)), {'code': code}), metodo)
    except Exception as e:  # solo el tipo; no es un rechazo
        return 'excepción ' + type(e).__name__


antes = iap_aparte()
print('P39 iap_account antes: count %d, max(id) %d' % antes)
previstos = excepciones = 0
for nombre, code, prevista, metodo in CASOS:
    c = run(code, metodo)
    if c.startswith('excepción'):
        excepciones += 1
        veredicto = 'NO CONCLUYENTE'
    elif c == prevista:
        previstos += 1
        veredicto = 'rechazado como se prevé'
    else:
        veredicto = 'FALLO'
    print('P39 %-46s %s (previsto %s) → %s' % (nombre, c, prevista, veredicto))
c = run(CONTROL)
control_ok = c == 'sin error'
if c.startswith('excepción'):
    excepciones += 1
print('P39 %-46s %s → %s' % ('control {...}.get y search_count', c,
                              'OK' if control_ok else ('NO CONCLUYENTE' if c.startswith('excepción')
                                                       else 'FALLO')))
env.cr.rollback()
despues = iap_aparte()
iap_igual = despues == antes
print('P39 iap_account después: count %d, max(id) %d (%s)' % (
    despues + ('sin cambios' if iap_igual else 'CAMBIÓ',)))
fallo = (previstos + excepciones < len(CASOS) or not iap_igual
         or (not control_ok and not c.startswith('excepción')))
veredicto = 'FALLO' if fallo else ('NO_CONCLUYENTE' if excepciones else 'OK')
print('P39 FIN previstos %d/%d, excepciones %d, control %s, iap_account %s' % (
    previstos, len(CASOS), excepciones, 'OK' if control_ok else 'no', 'igual' if iap_igual else 'CAMBIÓ'))
print('P39 VEREDICTO ' + veredicto)
PY
)
echo "$SALIDA" | grep '^P39 ' || echo "Sin líneas «P39»: el shell no ejecutó el script."
echo "$SALIDA" | grep -q '^P39 FALTAN ' && exit 16
if echo "$SALIDA" | grep -qx 'P39 VEREDICTO OK'; then
    echo "Resultado: como se espera (nada escrito: el shell se deshace al salir)"; exit 0
fi
if echo "$SALIDA" | grep -qx 'P39 VEREDICTO NO_CONCLUYENTE'; then
    echo "Resultado: NO CONCLUYENTE: alguna llamada lanzó una excepción (no cuenta como rechazo)"; exit 8
fi
echo "$SALIDA" | grep -q '^P39 VEREDICTO ' || echo "El shell no terminó. Errores, solo el tipo: $(echo "$SALIDA" | grep -oE '^[A-Za-z_.]+(Error|Exception)' | sort -u | paste -sd, -)"
echo "Resultado: FALLO"; exit 1
